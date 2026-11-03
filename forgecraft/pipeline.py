"""ForgeCraft's orchestration pipeline (the 3D Department's front door).

  brief / reference image(s) / photos / a mesh / library assets
    1  route          gitcraft3d.routing: the right capability for the request on this machine
    2  generate       MeshCraft template · Blockbench (MeshCraft) · Meshroom / TripoSR / Hunyuan3D
                      (ForgeCraft runs these external generators, then hands the mesh to MeshCraft)
    3–8 MeshCraft     build or import → clean → materials/UVs → rig/animate → previews → export per
                      engine profile → validate (scene checks, glTF structure, Khronos) → library version
    9  deliverable    MeshCraft engine_check: the main GLB loaded and animated in three@0.170
   10  record         annotate the library version: routing, licences, provenance, previews, checks
   11  hand off       library_export into a workspace root (hash-verified) for other tools / games

ForgeCraft owns the job (one record per request, `children` = the MeshCraft jobs it started) and
never re-implements MeshCraft's work. MeshCraft retries its own stages down its fallback ladder;
job_retry re-runs a whole ForgeCraft job. A request nothing here can honour ends `blocked`."""
import fcntl, json, os, re, shutil, sys, threading, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import _gitcraft3d  # noqa: F401  (loads gitcraft3d by path; see _gitcraft3d.py)
from gitcraft3d import hardware, jobs, library, routing
import meshcraft as mc
from backends import meshroom, triposr, hunyuan3d

LICENSES = {
    "meshcraft": {"tool": "MeshCraft (GITCRAFT, Blender 5.2 bpy)", "license": "GITCRAFT code; Blender GPL-2.0-or-later (wheel GPL-3.0) does not extend to models, renders or .blend content"},
    "blockbench": {"tool": "Blockbench .bbmodel format (via MeshCraft)", "license": "Blockbench GPL-3.0; .bbmodel files you author are yours"},
    "mixamo": {"tool": "Mixamo (Adobe)", "license": "Royalty-free in commercial projects; do not redistribute raw Mixamo files standalone or use them to train AI"},
    "meshroom": {"tool": "Meshroom / AliceVision", "license": "MPL-2.0; reconstructions belong to whoever owns the photos"},
    "triposr": {"tool": "TripoSR", "license": "MIT (code and weights)"},
    "hunyuan3d": {"tool": "Hunyuan3D-2", "license": "Tencent Hunyuan 3D 2.0 Community License: not licensed in the EU, UK or South Korea; >1M MAU needs a Tencent licence; label outputs as AI-generated; outputs may not train other models"},
}
PALETTE = os.path.join(HERE, "palettes", "tidebreakers-palette.json")
DEFAULT_PROFILES = ["three-web-toon", "web-pbr", "unity-fbx", "obj-static"]
IMPORT_PROFILES = ["web-pbr", "unity-fbx", "obj-static"]
FORMAT_PROFILES = {"glb": ["three-web-toon", "web-pbr"], "gltf": ["web-pbr"], "fbx": ["unity-fbx"], "obj": ["obj-static"], "stl": ["stl-print"]}


class Blocked(Exception):
    """The request cannot be honoured with the tools available here (not a crash)."""


def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
def slugify(s): return re.sub(r"[^a-z0-9]+", "_", (s or "asset").lower()).strip("_")[:48] or "asset"


def _profiles(spec, default):
    if spec.get("profiles"): return list(spec["profiles"])
    if spec.get("formats"):
        out = []
        for f in spec["formats"]:
            for p in FORMAT_PROFILES.get(f, []):
                if p not in out: out.append(p)
        return out or default
    return list(default)


def _main_glb(res):
    glbs = [e for e in res.get("exports", []) if e.get("format") == "glb"]
    for p in ("web-pbr", "scene-glb", "three-web-toon", "three-web-atlas"):
        e = next((x for x in glbs if x.get("profile") == p), None)
        if e: return e
    return glbs[0] if glbs else None


def _sha(p):
    try: return library.sha256(p)
    except OSError: return None


def deliverable_status(summ, eng):
    """The deliverable's status. A successful build is not proof that the asset loads or plays:
    only an engine check that actually ran and passed can make it `passed`. When the check could
    not run (no GLB, MeshCraft's engine check unavailable or erroring, no checks returned) the
    status is `blocked`, never a pass."""
    if (summ or {}).get("fail") or eng.get("status") == "failed": return "failed"
    if eng.get("status") != "passed": return "blocked"
    return "passed-with-warnings" if (summ or {}).get("warn") else "passed"


def engine_verify(glb, main, chosen, res, work, log, rec=None):
    """Load the main GLB in three@0.170 through MeshCraft's engine_check and, when the asset has
    clips, play every clip on its own and require each to move the asset."""
    if not glb or not os.path.exists(glb):
        return {"status": "skipped", "reason": "no GLB export, so nothing could be loaded in three.js"}
    if rec: jobs.stage(rec, "engine_check", "running")
    build = res.get("build") or {}
    clips = build.get("actions") or [c["clip"] for c in res.get("clips", []) if isinstance(c, dict) and c.get("clip")]
    args = {"glb": glb, "material": "authored" if (main or {}).get("profile") in ("web-pbr", "scene-glb") or chosen != "meshcraft_template" else "game-toon",
            "size": 512, "out": os.path.join(work, "engine_check.png")}
    contract = dict(build.get("contract") or {})
    if clips:
        args.update(clip=clips[0], time=0.4, all_clips=True)
        contract["clips"] = sorted(set(contract.get("clips") or []) | set(clips))   # every expected clip must be in the file
    if contract: args["contract"] = contract
    try:
        e = mc.call("engine_check", args, log, 300, extra_roots=[work])
        checks = e.get("checks") or []
        if not checks:
            eng = {"status": "error", "reason": "the engine check returned no checks"}
        else:
            fails = [c for c in checks if c.get("level") == "fail"]
            eng = {"status": "passed" if not fails else "failed", "glb": os.path.relpath(glb, os.path.dirname(os.path.dirname(glb))), "three": e.get("three") or e.get("revision"),
                   "checks": checks[:60], "screenshot": args["out"],
                   "clips": [{"name": m["name"], "moves": m["max_delta"] > 1e-4, "max_delta": m["max_delta"]} for m in e.get("clip_motion") or []]}
            if fails: eng["reason"] = "; ".join(f"{c['check']}: {c.get('detail')}" for c in fails)[:600]
    except Exception as ex:
        eng = {"status": "error", "reason": f"the three.js engine check could not run: {ex}"[:600]}
    if rec: jobs.stage(rec, "engine_check", "done" if eng["status"] == "passed" else "failed", info={"status": eng["status"], "reason": eng.get("reason")})
    return eng


# ------------------------------------------------------------------ main entry
def run(spec, job_id=None, manual=None):
    """Run (or re-run) a ForgeCraft job synchronously. Returns the job record."""
    rec = jobs.create("generate", spec, asset_id=(spec or {}).get("asset_id"), job_id=job_id)
    spec = rec["request"]
    jobs.begin(rec, manual=bool(job_id) if manual is None else manual)
    work = os.path.join(jobs.jobs_dir(), rec["id"]); os.makedirs(work, exist_ok=True)
    log = os.path.join(work, "job.log")
    os.makedirs(library.ROOT, exist_ok=True)
    with open(library.path(".heavy.lock"), "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)     # one heavy job at a time on this machine
        try:
            status = _run(rec, spec, work, log)
            jobs.finish(rec, status)
        except Blocked as e:
            jobs.finish(rec, "blocked", str(e))
        except Exception as e:
            open(log, "a").write(traceback.format_exc())
            st = next((s for s in reversed(rec["attempts"][-1]["stages"]) if s["state"] == "running"), None)
            if st: jobs.stage(rec, st["stage"], "failed", error=f"{type(e).__name__}: {e}"[:600])
            jobs.finish(rec, "failed", f"{type(e).__name__}: {e}")
    return jobs.get(rec["id"])


def retry(job_id): return run(None, job_id, manual=True)


def start(spec):
    """Run in the background; returns the job id at once."""
    rec = jobs.create("generate", spec, asset_id=spec.get("asset_id"))
    threading.Thread(target=run, args=(None, rec["id"], False), daemon=True).start()
    return rec["id"]


def _run(rec, spec, work, log):
    roots = [r for r in os.environ.get("GITCRAFT_ROOTS", "").split(":") if r]
    probe = hardware.probe(roots); lim = probe["limits"]
    images = routing.expand_images(spec.get("images") or [])

    # 1. route
    jobs.stage(rec, "route", "running")
    tool = routing.canonical_tool(spec.get("tool"))
    if spec.get("input_mesh") or tool == "meshcraft_import":
        req = routing.parse(spec.get("brief") or spec.get("name") or "imported mesh", images)
        plan = {"request": req, "route": "import", "chosen": "meshcraft_import", "preferred": "meshcraft_import", "fallback_used": False,
                "candidates": [], "explanation": "an existing mesh: MeshCraft process_mesh"}
    elif tool in ("mixamo", "meshcraft_scene") and spec.get("character" if tool == "mixamo" else "items"):
        req = routing.parse(spec.get("brief") or spec.get("name") or tool, images)
        plan = {"request": req, "route": tool, "chosen": tool, "preferred": tool, "fallback_used": False, "candidates": [],
                "explanation": {"mixamo": "merge Mixamo clips: MeshCraft mixamo_apply", "meshcraft_scene": "compose a scene: MeshCraft compose_scene"}[tool]}
    else:
        plan = routing.route(spec.get("brief", ""), images, probe, prefer=tool, kind=spec.get("kind"), params=spec.get("params"),
                             template=spec.get("template"))
        req = plan["request"]
    chosen = plan["chosen"]
    rec["plan"] = plan
    rec["compute"] = {"tool": chosen, "needs": routing.RULES["tools"].get(chosen, {}).get("compute") if chosen else None,
                      "machine": {"cpu_threads": probe["cpu"]["threads"], "ram_gb": probe["ram"]["total_gb"], "gpus": probe["gpus"]}, "limits": lim}
    if not chosen:
        jobs.stage(rec, "route", "failed", error=plan["explanation"])
        raise Blocked(plan["explanation"])
    jobs.stage(rec, "route", "done", info={"chosen": chosen, "route": plan["route"], "fallback_used": plan["fallback_used"], "explanation": plan["explanation"]})

    name = spec.get("name") or req["name"]
    # a retried job versions the asset its first attempt created; a new job gets a fresh id
    asset_id = spec.get("asset_id") or rec.get("asset_id") or library.unique_id(slugify(spec.get("slug") or name))
    rec["asset_id"] = asset_id
    out = os.path.join(work, "meshcraft")
    common = {"asset_id": asset_id, "out_dir": out, "parent_job": rec["id"]}
    T = lim["timeouts_s"]["blender"]
    gen_info, sources, inputs = {}, [], [{"path": p, "sha256": _sha(p)} for p in images if os.path.isfile(p)]

    # 2–8. generate (external generator if needed) and MeshCraft production
    jobs.stage(rec, "generate", "running", info={"tool": chosen})
    if chosen == "meshcraft_template":
        tpl = req["template"]; meta = mc.templates()[tpl]
        params = {k: v for k, v in {**req["params"], **(spec.get("template_params") or {})}.items() if k in meta["params"]}
        brief = dict(common, template=tpl, params=params, palette=PALETTE, title=name, tags=spec.get("tags", []),
                     profiles=_profiles(spec, DEFAULT_PROFILES), preview={"size": int(spec.get("preview_size", 512)), "views": ["three_quarter", "front", "side", "top"]})
        if tpl == "deckhand": brief["preview"]["poses"] = [{"clip": "Attack", "at": "end"}]
        if spec.get("bake"): brief["bake"] = {"resolution": int(spec["bake"]), "fallbacks": [512]}
        res = mc.call("run_pipeline", {"brief": brief}, log, T)
        sources = ["meshcraft"]; gen_info = {"method": "meshcraft template", "template": tpl, "params": params, "palette": os.path.basename(PALETTE)}
    elif chosen == "blockbench":
        tpl = routing.blockbench_template(req)
        bb = os.path.join(work, f"{asset_id}.bbmodel")
        b = mc.call("blockbench_build", {"template": tpl, "out": bb, "palette": PALETTE}, log, 300)
        res = mc.call("blockbench_import", dict(common, path=bb, palette=PALETTE, profiles=_profiles(spec, DEFAULT_PROFILES)), log, T)
        sources = ["blockbench", "meshcraft"]; gen_info = {"method": "blockbench template", "template": tpl, "bbmodel": b}
        inputs.append({"path": bb, "sha256": _sha(bb)})
    elif chosen in ("meshroom", "triposr", "hunyuan3d", "meshcraft_import"):
        if chosen == "meshroom":
            g = meshroom.run(images, work, log, pipeline=spec.get("meshroom_pipeline"), overrides=spec.get("meshroom_overrides"))
        elif chosen == "triposr":
            g = triposr.run(images[0], work, log, resolution=int(spec.get("mc_resolution", 256)))
        elif chosen == "hunyuan3d":
            g = hunyuan3d.run(work, log, prompt=None if images else spec.get("brief"), image=images[0] if images else None, seed=req["params"].get("seed", 1234))
        else:
            g = {"mesh": spec["input_mesh"], "method": "import"}
            inputs.append({"path": g["mesh"], "sha256": _sha(g["mesh"])})
        jobs.stage(rec, "generate", "running", info={k: v for k, v in g.items() if k != "mesh"})
        pm = dict(common, path=g["mesh"], title=name, tags=spec.get("tags", []), profiles=_profiles(spec, IMPORT_PROFILES),
                  **{k: spec[k] for k in ("crop", "crop_floor", "target_size", "max_tris") if k in spec})
        res = mc.call("process_mesh", pm, log, T, extra_roots=[work, os.path.dirname(g["mesh"])])
        sources = ([chosen] if chosen != "meshcraft_import" else []) + ["meshcraft"]
        gen_info = dict({k: v for k, v in g.items() if k != "mesh"}, method=chosen, mesh=os.path.basename(g["mesh"]))
    elif chosen == "meshcraft_scene":
        items = [{k: v for k, v in it.items()} for it in spec["items"]]
        for it in items:
            if it.get("asset"): inputs.append({"asset": it["asset"], "version": it.get("version") or library.get(it["asset"])["version"]})
        sc = dict(common, items=items, tags=spec.get("tags", []), **{k: spec[k] for k in ("camera", "look_at", "lens", "sun", "sky", "samples", "resolution", "frame", "ocean_size") if k in spec})
        res = mc.call("compose_scene", sc, log, T)
        sources = ["meshcraft"]; gen_info = {"method": "scene composition", "items": [{k: v for k, v in i.items() if k != "file"} for i in res.get("placed", [])]}
    elif chosen == "mixamo":
        ch = spec["character"]
        if not os.path.isfile(ch):   # a library asset: merge onto its MeshCraft .blend, as a new version of it
            md0 = library.get(ch); common["asset_id"] = asset_id = rec["asset_id"] = md0["id"]
            ch = os.path.join(md0["dir"], next(f["path"] for f in md0["files"] if f["kind"] == "blend"))
            inputs.append({"asset": md0["id"], "version": md0["version"]})
        inputs += [{"path": a, "sha256": _sha(a)} for a in spec.get("animations", [])]
        res = mc.call("mixamo_apply", dict(common, character=ch, animations=spec.get("animations", []), profiles=_profiles(spec, ["three-web-toon", "web-pbr", "unity-fbx"])),
                      log, T, extra_roots=[os.path.dirname(a) for a in spec.get("animations", [])])
        sources = ["mixamo", "meshcraft"]; gen_info = {"method": "mixamo clip merge", "clips": res.get("clips"), "rejected": res.get("rejected")}
    else:
        raise Blocked(f"no runner for {chosen}")
    jobs.child(rec, (res.get("job") or {}).get("id"))
    lib = res.get("library") or {}
    if not lib.get("version"): raise RuntimeError(f"MeshCraft did not add a library version: {lib.get('error') or lib}")
    summ = (res.get("validation") or {}).get("summary") or {}
    jobs.stage(rec, "generate", "done", info={"meshcraft_job": (res.get("job") or {}).get("id"), "meshcraft_status": (res.get("job") or {}).get("status"),
                                               "fallback": (res.get("job") or {}).get("fallback"), "validation": summ, "library": {"asset": lib["asset"], "version": lib["version"]}})

    # 9. deliverable check in the engine
    md = library.get(lib["asset"], lib["version"])
    main = _main_glb(res)
    glb = os.path.join(md["dir"], "exports", os.path.basename(main["path"])) if main else None
    eng = engine_verify(glb, main, chosen, res, work, log, rec)
    deliv = deliverable_status(summ, eng)

    # 10. record: one library version, MeshCraft's record + ForgeCraft's orchestration
    jobs.stage(rec, "record", "running")
    prev = [f["path"] for f in md["files"] if f["kind"] == "preview"]
    thumb = next((p for p in prev if "three_quarter" in p and "-" not in os.path.basename(p).split("three_quarter")[-1]), prev[0] if prev else None)
    rt = main.get("roundtrip") if main else None
    objs = (res.get("build") or {}).get("objects") or []
    info = {"title": name, "kind": req.get("kind") or req.get("template") or ("scene" if chosen == "meshcraft_scene" else None),
            "source_tool": " → ".join(sources),
            "route": {k: plan.get(k) for k in ("route", "chosen", "preferred", "fallback_used", "explanation")},
            "license": {"asset": spec.get("license", "Owned by the project that commissioned it"), "tools": [LICENSES[s] for s in sources if s in LICENSES],
                        "ai_generated": chosen in ("triposr", "hunyuan3d")},
            "provenance": {"forgecraft_job": rec["id"], "meshcraft_job": (res.get("job") or {}).get("id"), "inputs": inputs,
                           "blender": probe["backends"]["blender"].get("version"), "machine": rec["compute"]["machine"], "recorded": _now()},
            "generation": dict(gen_info, request=spec.get("brief")),
            "rig": ({"armatures": rt["armatures"], "convention": "Mixamo skeleton (22 mixamorig:* bones)" if req.get("template") == "deckhand" or chosen == "mixamo"
                     else "MeshCraft rig"} if rt and rt.get("armatures") else None),
            "geometry": {"triangles": (rt or {}).get("triangles") or md.get("triangles"), "size_m": (rt or {}).get("size_m"), "meshes": (rt or {}).get("meshes")},
            "animations": [{"name": c} for c in (md.get("clips") or [])],
            "sockets": sorted(o for o in objs if o.startswith("socket_")),
            "previews": {"thumbnail": thumb, "views": prev},
            "engine_check": eng, "deliverable_validation": {"status": deliv, "meshcraft": summ, "engine_check": eng["status"]},
            "orchestration": {"forgecraft_job": rec["id"], "route": plan["route"], "tool": chosen},
            "tags": sorted(set(spec.get("tags", []) + [t for t in (req.get("kind"), req.get("template"), chosen) if t]))}
    if eng.get("screenshot") and os.path.exists(eng["screenshot"]):
        os.makedirs(os.path.join(md["dir"], "previews"), exist_ok=True)
        d = os.path.join(md["dir"], "previews", f"{asset_id}_engine_check.png"); shutil.copy2(eng["screenshot"], d)
        info["engine_check"] = dict(eng, screenshot=os.path.relpath(d, md["dir"]))
    library.annotate(lib["asset"], lib["version"], info)
    rec["asset"] = {"id": lib["asset"], "version": lib["version"], "name": name, "validation": deliv}
    jobs.stage(rec, "record", "done", info={"asset": lib["asset"], "version": lib["version"], "validation": deliv})

    # 11. hand off
    if spec.get("handoff_dir"):
        jobs.stage(rec, "handoff", "running")
        h = library.export(lib["asset"], spec["handoff_dir"], lib["version"]); rec["handoff"] = h["dir"]
        jobs.stage(rec, "handoff", "done", info={"dir": h["dir"], "verified": h["verified"]})
    if deliv == "failed": raise RuntimeError(f"deliverable failed validation: meshcraft {summ}, engine check {eng['status']}: {eng.get('reason', '')}")
    if deliv == "blocked":
        raise Blocked(f"built and recorded as {lib['asset']} v{lib['version']}, but NOT verified: {eng.get('reason') or eng['status']}. "
                      "A built asset is not proof that it loads or plays; install MeshCraft's engine check (scripts/install.sh meshcraft) and retry the job")
    return "done_with_fallback" if (res.get("job") or {}).get("status") == "done_with_fallback" else "done"


def summary(rec):
    """Compact view of a job for MCP replies."""
    out = {"job": rec["id"], "status": rec["status"], "error": rec.get("error"), "asset": rec.get("asset"),
           "route": {k: (rec.get("plan") or {}).get(k) for k in ("route", "chosen", "fallback_used", "explanation")},
           "children": rec.get("children", []),
           "stages": [f"{s['stage']}:{s['state']}" for s in (rec["attempts"][-1]["stages"] if rec.get("attempts") else [])]}
    if rec.get("asset"):
        md = library.get(rec["asset"]["id"], rec["asset"]["version"])
        out["files"] = {f["path"]: os.path.join(md["dir"], f["path"]) for f in md["files"] if f["kind"] in ("export", "blend")}
        th = (md.get("previews") or {}).get("thumbnail")
        out["thumbnail"] = os.path.join(md["dir"], th) if th else None
        out["geometry"] = md.get("geometry"); out["animations"] = [a["name"] for a in md.get("animations", [])]
        out["validation"] = (md.get("deliverable_validation") or {}).get("status")
    if rec.get("handoff"): out["handoff"] = rec["handoff"]
    if rec["status"] == "blocked": out["alternatives"] = (rec.get("plan") or {}).get("alternatives")
    return out
