"""The unified 3D pipeline:

  brief / reference image(s)
    → route (routing.py: pick the tool for the request and the machine, with fallbacks)
    → generate or import (Blender procedural · Blockbench .bbmodel · TripoSR · Hunyuan3D · Meshroom)
    → Blender: clean geometry → optimise polygon budget → UV unwrap → bake PBR texture maps
               → rig + animate (characters) → preview renders → GLB/glTF/FBX/OBJ/STL/.blend export
    → validate (Blender re-import + Khronos glTF-Validator + three.js r170 load in Chromium)
    → package into the asset library with ID, version, provenance, licence, stats
    → hand off (copy into a workspace root for the other GITCRAFT tools)

Every run is a job record (library/jobs/<job>.json) with per-stage state, timings, errors
and attempts. Failed Blender stages retry automatically with a lighter configuration
(smaller bake, fewer preview frames, then no bake); `retry(job_id)` re-runs a job by hand.
One heavy job runs at a time (file lock), with per-backend timeouts from hardware.limits()."""
import fcntl, json, os, shutil, subprocess, sys, threading, time, traceback, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hardware, library, routing
from backends import blockbench, meshroom, triposr, hunyuan3d, meshcraft_tpl

BLENDER_RUN = os.path.join(HERE, "blender", "run.py")
WEB_CHECK = os.path.join(HERE, "web-check", "check.mjs")
ALL_FORMATS = ["glb", "gltf", "fbx", "obj", "stl", "blend"]

LICENSES = {
    "blender": {"tool": "Blender 5.2 (bpy)", "license": "GPL-2.0-or-later (binaries GPL-3.0); outputs belong to you, no restrictions"},
    "blockbench": {"tool": "Blockbench .bbmodel format", "license": "Blockbench is GPL-3.0; .bbmodel files you create are yours"},
    "triposr": {"tool": "TripoSR", "license": "MIT (code and weights); free for commercial use with the MIT notice"},
    "hunyuan3d": {"tool": "Hunyuan3D-2", "license": "Tencent Hunyuan 3D 2.0 Community License: not licensed in the EU, UK or South Korea; >1M MAU needs a Tencent licence; label outputs as AI-generated; outputs may not train other models"},
    "meshroom": {"tool": "Meshroom / AliceVision", "license": "MPL-2.0; reconstructions belong to whoever owns the photos"},
    "meshcraft": {"tool": "MeshCraft templates (GITCRAFT, Blender)", "license": "GITCRAFT code; Blender GPL does not extend to outputs; colours from the project's own brand palette"},
    "mixamo": {"tool": "Mixamo (Adobe)", "license": "Royalty-free in commercial projects; do not redistribute raw Mixamo files standalone"},
}


def jobs_dir(): return library.path("jobs")


def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Job:
    def __init__(self, spec, job_id=None):
        self.id = job_id or f"job-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        self.file = os.path.join(jobs_dir(), self.id + ".json")
        os.makedirs(jobs_dir(), exist_ok=True)
        if job_id and os.path.exists(self.file):
            self.rec = json.load(open(self.file))
        else:
            self.rec = {"id": self.id, "spec": spec, "status": "queued", "created": _now(), "attempts": [], "stages": [], "error": None,
                        "asset": None, "plan": None, "compute": None}
        self.work = os.path.join(jobs_dir(), self.id)
        os.makedirs(self.work, exist_ok=True)
        self.log = os.path.join(self.work, "job.log")
        self.lock = threading.Lock()

    def save(self):
        with self.lock:
            self.rec["updated"] = _now()
            tmp = self.file + ".tmp"; json.dump(self.rec, open(tmp, "w"), indent=1, default=str); os.replace(tmp, self.file)

    def stage(self, name, state, **info):
        att = len(self.rec["attempts"]) - 1   # 0-based index of the current attempt
        st = next((s for s in self.rec["stages"] if s["stage"] == name and s.get("attempt") == att), None)
        if not st:
            st = {"stage": name, "attempt": att, "state": state, "started": _now()}
            self.rec["stages"].append(st)
        st["state"] = state; st.update(info)
        if state in ("done", "failed", "skipped"): st["finished"] = _now()
        self.save()


# ------------------------------------------------------------------ helpers
def _blender(job, op, out_dir, timeout, **fields):
    """Run one Blender job in its own process; mirror its stage progress into the job record."""
    spec = dict(op=op, out_dir=out_dir, **fields)
    jf = os.path.join(job.work, f"blender_{op}_{max(0, len(job.rec['attempts']) - 1)}_{uuid.uuid4().hex[:4]}.json")
    json.dump(spec, open(jf, "w"), indent=1)
    shutil.rmtree(out_dir, ignore_errors=True); os.makedirs(out_dir, exist_ok=True)
    env = dict(os.environ, TMPDIR=os.path.join(job.work, "tmp")); os.makedirs(env["TMPDIR"], exist_ok=True)
    prog = os.path.join(out_dir, "_progress.jsonl")
    with open(job.log, "a") as lf:
        lf.write(f"$ blender {op} {jf}\n"); lf.flush()
        p = subprocess.Popen([hardware.BLENDER_PY, BLENDER_RUN, jf], stdout=lf, stderr=subprocess.STDOUT, env=env)
        seen, t0 = 0, time.time()
        while p.poll() is None:
            time.sleep(0.5)
            seen = _mirror(job, prog, seen, f"blender:")
            if time.time() - t0 > timeout:
                p.kill(); raise RuntimeError(f"Blender {op} exceeded the {timeout}s job limit")
        _mirror(job, prog, seen, "blender:")
    rp = os.path.join(out_dir, "_result.json")
    if not os.path.exists(rp): raise RuntimeError(f"Blender {op} crashed (exit {p.returncode}) before writing a result; see {job.log}")
    res = json.load(open(rp))
    if not res.get("ok"): raise RuntimeError(f"Blender {op}: {res.get('error')}")
    return res


def _mirror(job, prog, seen, prefix):
    try: lines = open(prog).read().splitlines()
    except OSError: return seen
    for line in lines[seen:]:
        try: e = json.loads(line)
        except ValueError: continue
        info = {k: v for k, v in e.items() if k in ("seconds", "error", "info")}
        job.stage(prefix + e["stage"], e["state"], **info)
    return len(lines)


def _installed(mods, pkg):
    try:
        with open(os.path.join(mods, pkg, "package.json")) as f: return json.load(f).get("version")
    except (OSError, ValueError):
        return None


def web_modules():
    """(node_modules dir, None) for the engine check, or (None, reason). ForgeCraft pins the same
    three.js and gltf-validator as MeshCraft's engine check, which the standard installer always
    installs; so it uses its own install when present, else MeshCraft's, and only if every pinned
    version matches exactly. FORGECRAFT_WEB_MODULES overrides the search."""
    with open(os.path.join(HERE, "web-check", "package.json")) as f: pins = json.load(f)["dependencies"]
    env = os.environ.get("FORGECRAFT_WEB_MODULES")
    cands = [env] if env else [os.path.join(HERE, "web-check", "node_modules"),
                               os.path.join(os.path.dirname(HERE), "meshcraft", "engine_check", "node_modules")]
    seen = []
    for d in cands:
        got = {p: _installed(d, p) for p in pins}
        if got == pins: return d, None
        seen.append(f"{d}: {got}")
    return None, f"no node_modules with {pins} ({'; '.join(seen)}); run scripts/install.sh (MeshCraft engine check) or scripts/install-3d.sh"


def _web_check(job, files):
    mods, why = web_modules()
    if not shutil.which("node") or not mods:
        return {"status": "skipped", "reason": why or "node is not installed"}
    out = os.path.join(job.work, "web_check.json"); shot = os.path.join(job.work, "web_check.png")
    r = subprocess.run(["node", WEB_CHECK, out, shot, *files], capture_output=True, text=True, timeout=300,
                       env=dict(os.environ, FORGECRAFT_WEB_MODULES=mods))
    if not os.path.exists(out): return {"status": "error", "reason": (r.stderr or r.stdout)[-600:]}
    d = json.load(open(out))
    return {"status": "passed" if d.get("ok") else "failed", "three_revision": d["three"]["revision"], "screenshot": shot, "modules": mods,
            "files": {os.path.basename(k): {"khronos_errors": v["validator"]["errors"], "khronos_warnings": v["validator"]["warnings"],
                                            "khronos_messages": v["validator"]["messages"], "three_loaded": (v.get("three") or {}).get("ok"),
                                            "three_clips": len((v.get("three") or {}).get("clips") or []),
                                            "three_clips_static": [c["name"] for c in (v.get("three") or {}).get("clips") or [] if not c.get("moves")]}
                      for k, v in d["files"].items()}}


# ------------------------------------------------------------------ main entry
def run(spec, job_id=None):
    """Run (or re-run) a job synchronously. Returns the job record."""
    job = Job(spec, job_id)
    spec = job.rec["spec"]
    if job_id and job.rec.get("asset") and not spec.get("asset_id"):
        spec["asset_id"] = job.rec["asset"]["id"]   # re-running a job that made an asset → next version of it
    probe = hardware.probe()
    lim = probe["limits"]
    job.rec["attempts"].append({"started": _now()})
    job.rec["status"] = "queued"; job.rec["error"] = None; job.save()
    os.makedirs(library.ROOT, exist_ok=True)
    with open(library.path(".heavy.lock"), "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)    # one heavy job at a time on this machine
        job.rec["status"] = "running"; job.save()
        try:
            _run(job, spec, probe, lim)
            job.rec["status"] = "done"
        except Blocked as e:
            job.rec["status"] = "blocked"; job.rec["error"] = str(e)
        except Exception as e:
            job.rec["status"] = "failed"; job.rec["error"] = f"{type(e).__name__}: {e}"
            with open(job.log, "a") as lf: lf.write(traceback.format_exc())
        job.rec["attempts"][-1].update(finished=_now(), status=job.rec["status"], error=job.rec["error"])
        job.save()
    return job.rec


class Blocked(Exception):
    """The request cannot be honoured with the tools available here (not a crash)."""


def _run(job, spec, probe, lim):
    images = routing.expand_images(spec.get("images") or [])
    # 1. route
    job.stage("route", "running")
    if spec.get("input_mesh") or spec.get("tool") == "mixamo":   # explicit import / Mixamo merge: no routing decision to make
        t = "mixamo" if spec.get("tool") == "mixamo" else "import"
        req = routing.parse(spec.get("brief") or spec.get("name") or "imported asset", images)
        plan = {"request": req, "route": t, "why": routing.RULES["tools"][t]["label"], "candidates": [{"tool": t, "available": probe["backends"]["blender"]["available"],
                "label": routing.RULES["tools"][t]["label"], "detail": "explicit"}], "chosen": t if probe["backends"]["blender"]["available"] else None,
                "preferred": t, "fallback_used": False, "explanation": "explicit " + t}
        if plan["chosen"] is None: plan["explanation"] = "Blender is not installed: " + probe["backends"]["blender"].get("reason", "")
    else:
        plan = routing.route(spec.get("brief", ""), images, probe, prefer=spec.get("tool"), kind=spec.get("kind"), params=spec.get("params"))
    req = plan["request"]
    if spec.get("kind"): req["kind"] = spec["kind"]
    req["params"].update(spec.get("params") or {})
    job.rec["plan"] = plan
    tool = plan["chosen"]
    job.rec["compute"] = {"tool": tool, "needs": routing.RULES["tools"][tool]["compute"] if tool else None,
                          "machine": {"cpu_threads": probe["hardware"]["cpu_threads"], "ram_gb": probe["hardware"]["ram"]["total_gb"],
                                      "gpus": probe["hardware"]["gpus"]}, "limits": lim}
    if not tool:
        job.stage("route", "failed", error=plan["explanation"])
        raise Blocked(plan["explanation"])
    job.stage("route", "done", info={"chosen": tool, "route": plan["route"], "fallback_used": plan["fallback_used"], "explanation": plan["explanation"]})

    name = spec.get("name") or req["name"]
    slug = library.slugify(spec.get("slug") or name)
    out = os.path.join(job.work, "out")
    budget = min(int(spec.get("max_tris", 20000)), lim["max_triangles"])
    bake = min(int(spec.get("bake", 1024)), lim["max_bake_resolution"])
    formats = spec.get("formats") or ALL_FORMATS
    frames = int(spec.get("turntable", 8))
    gen_info, source_tools, inputs = {}, [], []
    for p in images:
        if os.path.isfile(p): inputs.append({"path": p, "sha256": library.sha256(p)})

    def blender_stage(op, **fields):
        # automatic retry with degradation: full → half bake & 4 frames → no bake & 2 frames
        tries = [dict(bake=bake, turntable=frames), dict(bake=max(256, bake // 2), turntable=min(frames, 4)), dict(bake=0, turntable=2)]
        last = None
        for i, cfg in enumerate(tries[: 1 + int(spec.get("auto_retries", 2))]):
            try:
                if i: job.stage(f"retry_{i}", "done", info={"reason": last, "config": cfg})
                return _blender(job, op, out, lim["timeouts_s"]["blender"], slug=slug, max_tris=budget, formats=formats, **{**fields, **cfg}), cfg
            except Exception as e:
                last = str(e)[:400]
        raise RuntimeError(last)

    # 2. generate / import, 3–9. Blender processing
    if tool in ("blender_procedural", "blender_character"):
        kind = req["kind"] if tool == "blender_procedural" else "character"
        job.stage("generate", "running", info={"tool": tool, "kind": kind})
        res, cfg = blender_stage("generate", kind=kind, params=req["params"], clips=spec.get("clips") or ["Idle", "Walk", "Run", "Jump", "Interact", "Attack"])
        job.stage("generate", "done")
        source_tools = ["blender"]; gen_info = {"method": "procedural", "kind": kind, "params": req["params"], "blender_config": cfg}
    elif tool == "blockbench":
        tpl = blockbench.template_for(req)
        job.stage("generate", "running", info={"tool": "blockbench", "template": tpl})
        bb = blockbench.build(tpl, slug, os.path.join(job.work, f"{slug}.bbmodel"), seed=req["params"].get("seed", 1))
        job.stage("generate", "done", info=bb)
        res, cfg = blender_stage("bbmodel", input=bb["bbmodel"], keep_materials=True, recenter=True)
        shutil.copy2(bb["bbmodel"], out)  # ship the editable Blockbench project with the asset
        res["files"]["bbmodel"] = os.path.join(out, os.path.basename(bb["bbmodel"]))
        source_tools = ["blockbench", "blender"]; gen_info = {"method": "blockbench template", "template": tpl, "bbmodel": blockbench.inspect(bb["bbmodel"])}
    elif tool in ("triposr", "hunyuan3d", "meshroom"):
        job.stage("generate", "running", info={"tool": tool})
        if tool == "triposr":
            g = triposr.run(images[0], job.work, job.log, resolution=int(spec.get("mc_resolution", 256)))
        elif tool == "hunyuan3d":
            g = hunyuan3d.run(job.work, job.log, prompt=None if images else spec.get("brief"), image=images[0] if images else None,
                              seed=req["params"].get("seed", 1234))
        else:
            g = meshroom.run(images, job.work, job.log, pipeline=spec.get("meshroom_pipeline"), overrides=spec.get("meshroom_overrides"))
        job.stage("generate", "done", info=g)
        res, cfg = blender_stage("process", input=g["mesh"], keep_materials=bool(g.get("textured")) and not spec.get("rebake", True),
                                 target_size=spec.get("target_size"), crop=spec.get("crop"), crop_floor=spec.get("crop_floor", True))
        source_tools = [tool, "blender"]; gen_info = dict(g, method=tool)
    elif tool == "meshcraft_template":
        tpl = req["template"]
        job.stage("generate", "running", info={"tool": "meshcraft", "template": tpl})
        g = meshcraft_tpl.run(tpl, spec.get("template_params") or {}, slug, job.work, job.log, timeout=lim["timeouts_s"]["blender"])
        job.stage("generate", "done", info={k: g[k] for k in ("template", "clips", "meshcraft_validation", "seconds")})
        # MeshCraft already built, validated and exported: keep its geometry, rig and clips exactly; package them
        shutil.rmtree(out, ignore_errors=True); os.makedirs(os.path.join(out, "previews"))
        files = {"glb": os.path.join(out, f"{slug}.glb"), "blend": os.path.join(out, f"{slug}.blend")}
        shutil.copy2(g["glb"], files["glb"]); shutil.copy2(g["blend"], files["blend"])
        pv = []
        for p in g["previews"]:
            d = os.path.join(out, "previews", os.path.basename(p)); shutil.copy2(p, d); pv.append(d)
        thumb = next((p for p in pv if "three_quarter" in p), pv[0] if pv else None)
        v = _blender(job, "validate", os.path.join(job.work, "stats"), 300, input=files["glb"])["validation"]
        res = {"files": files, "previews": {"thumbnail": thumb, "turntable": [p for p in pv if p != thumb and "_sheet" not in p]},
               "stages": [{"stage": "meshcraft:" + s["step"], "state": "done" if s["ok"] else "failed", "seconds": s.get("seconds")} for s in json.load(open(g["report"]))["steps"]],
               "stats": {"triangles": v["triangles"], "vertices": v["vertices"], "meshes": v["meshes"], "dimensions_m": v["dimensions_m"],
                         "materials": [], "textures": [{"name": t, "size": [], "colorspace": ""} for t in v["textures"]],
                         "rig": {"bones": v["bones"], "bone_names": [], "convention": "meshcraft"} if v["bones"] else None,
                         "animations": [{"name": a, "frames": [], "seconds": None, "loop": None} for a in v["animations"]], "sockets": []}}
        source_tools = ["meshcraft", "blender"]
        gen_info = {"method": "meshcraft template", "template": tpl, "params": g["params"], "palette": g["palette"],
                    "meshcraft_validation": g["meshcraft_validation"], "profile": meshcraft_tpl.PROFILE}
    elif tool == "import":
        src = spec["input_mesh"]
        job.stage("generate", "running", info={"tool": "import", "input": src})
        inputs.append({"path": src, "sha256": library.sha256(src)})
        if src.endswith(".bbmodel"): gen_info = {"method": "blockbench import", "bbmodel": blockbench.inspect(src)}; source_tools = ["blockbench", "blender"]
        else: gen_info = {"method": "import", "input": os.path.basename(src)}; source_tools = ["blender"]
        job.stage("generate", "done")
        res, cfg = blender_stage("process", input=src, keep_materials=bool(spec.get("keep_materials", src.endswith(".bbmodel"))), target_size=spec.get("target_size"))
        if src.endswith(".bbmodel"):
            shutil.copy2(src, out); res["files"]["bbmodel"] = os.path.join(out, os.path.basename(src))
    elif tool == "mixamo":
        char = spec["character"]
        if not os.path.isfile(char):
            md0 = library.get(char); char = library.file_path(md0, "glb"); spec.setdefault("asset_id", md0["id"])
            inputs.append({"asset": md0["id"], "version": md0["version"]})
        for a in spec.get("animations", []): inputs.append({"path": a, "sha256": library.sha256(a)})
        job.stage("generate", "running", info={"tool": "mixamo", "animations": len(spec.get("animations", []))})
        res = _blender(job, "mixamo", out, lim["timeouts_s"]["blender"], slug=slug, character=char, animations=spec.get("animations", []),
                       formats=spec.get("formats") or ["glb", "fbx", "blend"], turntable=4)
        job.stage("generate", "done", info={"clips": res.get("clips")})
        source_tools = ["mixamo", "blender"]; gen_info = {"method": "mixamo animation merge", "clips": res.get("clips")}
    elif tool == "blender_scene":
        items = spec.get("items")
        if not items: raise Blocked("scene composition needs `items`: [{asset, location, rotation, scale, attach_to}] referring to library assets")
        job.stage("generate", "running", info={"tool": tool, "items": len(items)})
        resolved = []
        for it in items:
            md = library.get(it["asset"], it.get("version"))
            resolved.append(dict(it, file=library.file_path(md, "glb"), name=it.get("name") or md["slug"]))
            inputs.append({"asset": md["id"], "version": md["version"], "sha256": md["files"]["glb"]["sha256"]})
        res = _blender(job, "scene", out, lim["timeouts_s"]["blender"], slug=slug, items=resolved, formats=spec.get("formats") or ["glb", "blend"],
                       camera=spec.get("camera", [34, -38, 16]), look_at=spec.get("look_at", [0, -8, 2]), samples=int(spec.get("samples", 32)),
                       resolution=spec.get("resolution", [1280, 720]), frame=int(spec.get("frame", 10)),
                       sun=spec.get("sun", [48, 8, 140]), sky=spec.get("sky", "sky"))
        job.stage("generate", "done")
        source_tools = ["blender"]; gen_info = {"method": "scene composition", "items": [{k: v for k, v in r.items() if k != "file"} for r in resolved]}
    else:
        raise Blocked(f"no runner for {tool}")

    # 10. validate
    job.stage("validate", "running")
    glb = res["files"].get("glb")
    val = {"status": "not run"}
    if glb:
        exp = {"triangles": res["stats"]["triangles"], "animations": len(res["stats"]["animations"]), "textures": len(res["stats"]["textures"])}
        vres = _blender(job, "validate", os.path.join(job.work, "validate"), 300, input=glb, expect=exp)["validation"]
        web = _web_check(job, [glb])
        ok = not vres["problems"] and web["status"] in ("passed", "skipped")
        warn = any(f.get("khronos_warnings") for f in web.get("files", {}).values())
        # a skipped engine check is not a pass: the asset was never loaded or played in three.js
        val = {"status": "failed" if not ok else "unverified" if web["status"] == "skipped" else "passed-with-warnings" if warn else "passed",
               "blender_reimport": vres, "engine": web}
    job.stage("validate", "done" if val["status"] != "failed" else "failed", info={"status": val["status"]})

    # 11. package
    job.stage("package", "running")
    meta = {"name": name, "slug": slug, "kind": req["kind"] or ("scene" if tool == "blender_scene" else None), "brief": spec.get("brief"),
            "tags": sorted(set(spec.get("tags", []) + [t for t in [req["kind"], tool] if t] + req["intents"])),
            "source_tool": " → ".join(source_tools), "pipeline": [s["stage"] for s in res.get("stages", [])],
            "generation": gen_info, "route": {k: plan[k] for k in ("route", "chosen", "preferred", "fallback_used", "explanation")},
            "license": {"asset": spec.get("license", "Owned by the project that generated it"), "tools": [LICENSES[t] for t in source_tools if t in LICENSES],
                        "ai_generated": tool in ("triposr", "hunyuan3d")},
            "provenance": {"job": job.id, "inputs": inputs, "blender": probe["backends"]["blender"].get("version"), "machine": job.rec["compute"]["machine"]},
            "validation": val, "job": job.id}
    md = library.add(out, res, meta, asset_id=spec.get("asset_id"))
    job.rec["asset"] = {"id": md["id"], "version": md["version"], "name": md["name"], "validation": val["status"]}
    job.stage("package", "done", info={"asset": md["id"], "version": md["version"]})

    # 12. hand off
    if spec.get("handoff_dir"):
        job.stage("handoff", "running")
        h = library.export(md["id"], spec["handoff_dir"], md["version"])
        job.rec["handoff"] = h
        job.stage("handoff", "done", info={"dir": h["dir"]})
    if val["status"] == "failed":
        raise RuntimeError("validation failed: " + json.dumps(val.get("blender_reimport", {}).get("problems")))


def retry(job_id):
    return run(None, job_id)


def jobs(limit=30):
    out = []
    if not os.path.isdir(jobs_dir()): return out
    for f in sorted(os.listdir(jobs_dir()), reverse=True):
        if f.endswith(".json"):
            try: out.append(json.load(open(os.path.join(jobs_dir(), f))))
            except ValueError: pass
        if len(out) >= limit: break
    return out


def get_job(job_id): return json.load(open(os.path.join(jobs_dir(), job_id + ".json")))
