#!/usr/bin/env python3
"""3D Department UI: static snapshot publisher (standard library only).

  python3 forgecraft/ui_server.py --publish <library> <dist> [--source LABEL]
                                  static site (UI + data/state.json + asset files), e.g. for the Vercel preview

There is no live mode any more. The old live server ran pipeline jobs in its own process,
outside the guard and the Landlock sandbox, and accepted unauthenticated, cross-site and
DNS-rebinding requests (PR #9 security audit). ForgeCraft never needed it: every action it
offered is a ForgeCraft MCP tool (generate, compose_scene, job_retry, mixamo_prepare_upload).
Run them from Claude Code, from `forgecraft/cli.py`, or from the GITCRAFT control room
(`scripts/ui.sh`: local, token-protected, every call through scripts/mcp.sh)."""
import json, os, re, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(os.path.dirname(HERE), "meshcraft"))
import _gitcraft3d  # noqa: F401
from gitcraft3d import hardware, jobs as jobstore, library, routing
from engine import blockbench, mixamo     # MeshCraft's (stdlib parts): template list and the Mixamo guide

UI = os.path.join(HERE, "ui")


def _asset_view(md, base):
    """One library version (MeshCraft's record + ForgeCraft's annotations) → what the UI renders."""
    files, companions, textures = {}, [], []
    main = (md.get("engine_check") or {}).get("glb")
    for f in md.get("files", []):
        rec = {"path": f["path"], "bytes": f["bytes"], "sha256": f["sha256"]}
        name = os.path.basename(f["path"])
        if f["kind"] == "export":
            m = re.match(r".+?\.([a-z0-9-]+)\.([a-z0-9]+)$", name)
            files[f"{m.group(1)}.{m.group(2)}" if m else name] = rec
        elif f["kind"] == "blend": files["blend"] = rec
        elif f["kind"] in ("lod", "collision"): files[f"{f['kind']}: {name}"] = rec
        elif f["kind"] == "sidecar":
            companions.append(f["path"])
            if name.endswith(".png"): textures.append({"name": name, "size": [], "colorspace": "map"})
        elif f["kind"] == "report": companions.append(f["path"])
    glbs = [f for f in md.get("files", []) if f["kind"] == "export" and f["path"].endswith(".glb")]
    pick = main or next((f["path"] for p in ("web-pbr", "scene", "three-web-toon") for f in glbs if f".{p}." in f["path"]), glbs[0]["path"] if glbs else None)
    if pick: files["glb"] = next({"path": f["path"], "bytes": f["bytes"], "sha256": f["sha256"]} for f in md["files"] if f["path"] == pick)
    pv = md.get("previews") or {}
    views = pv.get("views") or [f["path"] for f in md.get("files", []) if f["kind"] == "preview"]
    thumb = pv.get("thumbnail") or next((v for v in views if "three_quarter" in v), views[0] if views else None)
    hero = next((v for v in views if v.endswith("_hero.png")), None)
    geo = md.get("geometry") or {}
    brief = md.get("brief") if isinstance(md.get("brief"), dict) else {}
    dv = md.get("deliverable_validation") or {}
    return {"id": md["id"], "version": md["version"], "name": md.get("title") or brief.get("title") or md["id"],
            "kind": md.get("kind") or md.get("template"), "template": md.get("template"),
            "brief": (md.get("generation") or {}).get("request") or (f"MeshCraft {md.get('tool')} · template {md.get('template')}"),
            "tags": md.get("tags", []), "source_tool": md.get("source_tool") or f"meshcraft ({md.get('tool')})",
            "route": md.get("route") or {"chosen": md.get("tool"), "explanation": "made directly with MeshCraft"},
            "geometry": {"triangles": geo.get("triangles") or md.get("triangles"), "dimensions_m": geo.get("size_m") or [], "vertices": None},
            "materials": [], "textures": textures,
            "rig": md.get("rig"), "animations": md.get("animations") or [{"name": c} for c in md.get("clips") or []],
            "sockets": [{"name": n} for n in md.get("sockets", [])], "generation": md.get("generation") or {"template": md.get("template"), "params": brief.get("params")},
            "previews": {"thumbnail": thumb, "hero": hero, "turntable": [v for v in views if v not in (thumb, hero) and "engine_check" not in v]},
            "engine_shot": (md.get("engine_check") or {}).get("screenshot"),
            "files": files, "companion_files": companions,
            "validation": dict(md.get("validation") or {}, status=dv.get("status") or {"pass": "passed", "needs-fix": "failed"}.get((md.get("validation") or {}).get("status"), "not run"),
                               meshcraft=md.get("validation"), engine_check=md.get("engine_check"), same_as=md.get("same_as")),
            "license": md.get("license") or {"asset": "Owned by the project that commissioned it", "tools": [{"tool": "MeshCraft (Blender)", "license": "GPL software; outputs unrestricted"}]},
            "provenance": dict(md.get("provenance") or {}, created=md.get("created"), inputs=(md.get("provenance") or {}).get("inputs") or md.get("inputs")),
            "job": (md.get("provenance") or {}).get("forgecraft_job") or md.get("job"),
            "stages": [], "base": base}


def _job_view(j):
    """A job record (ForgeCraft orchestration or MeshCraft tool job) → the Pipeline Monitor's view."""
    req = j.get("request") or {}
    brief = req.get("brief") if isinstance(req.get("brief"), dict) else None
    name = req.get("name") or (brief or {}).get("title") or (req.get("brief") if isinstance(req.get("brief"), str) else None) or j.get("asset_id") or j["id"]
    stages = []
    for i, a in enumerate(j.get("attempts", [])):
        for s in a.get("stages", []):
            stages.append({"stage": s["stage"], "attempt": i, "state": s["state"], "seconds": s.get("seconds"), "error": s.get("error"), "started": s.get("started"), "finished": s.get("finished")})
        for s in a.get("steps", []):
            stages.append({"stage": "meshcraft:" + s["step"], "attempt": i, "state": "done" if s.get("ok") else "failed", "seconds": s.get("seconds"), "error": s.get("error")})
        if not a.get("stages") and not a.get("steps"):
            stages.append({"stage": j.get("tool"), "attempt": i, "state": a.get("status", "running"), "seconds": a.get("seconds"), "error": a.get("error")})
    lib = j.get("library") or {}
    asset = j.get("asset") or ({"id": lib["asset"], "version": lib["version"]} if lib.get("version") else None)
    return {"id": j["id"], "tool": j.get("tool"), "spec": {"name": name, "brief": name, "tool": j.get("tool")}, "status": j.get("status"),
            "created": j.get("created"), "updated": j.get("updated"), "attempts": [{"status": a.get("status"), "error": a.get("error"), "change": a.get("change")} for a in j.get("attempts", [])],
            "stages": stages, "error": j.get("error"), "asset": asset, "plan": j.get("plan"), "compute": j.get("compute"),
            "parent": j.get("parent"), "children": j.get("children", [])}


def state(lib_root, base_url, probe=None, mode="live", source=""):
    idx = json.load(open(os.path.join(lib_root, "index.json"))) if os.path.exists(os.path.join(lib_root, "index.json")) else {"assets": []}
    assets = []
    for e in idx["assets"]:
        vs = {}
        for v in e["versions"]:
            p = os.path.join(lib_root, "assets", e["id"], f"v{v}", "asset.json")
            if os.path.exists(p): vs[str(v)] = _asset_view(json.load(open(p)), f"{base_url}assets/{e['id']}/v{v}/")
        if vs: assets.append({"id": e["id"], "latest": str(max(map(int, vs))), "versions": vs})
    jl = []
    jd = os.path.join(lib_root, "jobs")
    for f in sorted(os.listdir(jd) if os.path.isdir(jd) else [], reverse=True):
        if f.endswith(".json"):
            try: jl.append(_job_view(json.load(open(os.path.join(jd, f)))))
            except (ValueError, KeyError): pass
    return {"mode": mode, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": source,
            "probe": probe or hardware.probe(), "rules": routing.RULES, "bb_templates": sorted(blockbench.TEMPLATES),
            "templates": (probe or hardware.probe())["backends"]["meshcraft"].get("templates", []),
            "mixamo": {"steps": [s["step"] if isinstance(s, dict) else s for s in mixamo.guide()["steps"]], "bones": mixamo.guide().get("core_bones", [])},
            "assets": assets, "jobs": jl}


def publish(lib_root, dist, source=""):
    """Write a static snapshot: UI + data/state.json + the library's asset files (no job work dirs)."""
    if os.path.isdir(dist): shutil.rmtree(dist)
    shutil.copytree(UI, dist, ignore=shutil.ignore_patterns("dist"))
    data = os.path.join(dist, "data"); os.makedirs(data)
    if os.path.isdir(os.path.join(lib_root, "assets")): shutil.copytree(os.path.join(lib_root, "assets"), os.path.join(data, "assets"))
    probe_file = os.path.join(lib_root, "probe.json")
    probe = json.load(open(probe_file)) if os.path.exists(probe_file) else hardware.probe()
    st = state(lib_root, "data/", probe, mode="snapshot", source=source)
    json.dump(st, open(os.path.join(data, "state.json"), "w"), default=str)
    total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dist) for f in fs)
    print(f"published {len(st['assets'])} assets, {len(st['jobs'])} jobs to {dist} ({total / 2**20:.1f} MB)")


NO_LIVE = """ForgeCraft's live web server was removed (it ran jobs outside GITCRAFT's sandbox and accepted
cross-site requests). Use one of the supported routes instead:
  * Claude Code: the forgecraft MCP tools (generate, compose_scene, job_retry, mixamo_prepare_upload, ...)
  * terminal:    python3 forgecraft/cli.py generate "a wooden crate"
  * web UI:      scripts/ui.sh   (GITCRAFT control room on 127.0.0.1: token-protected, every call through scripts/mcp.sh)
  * snapshot:    python3 forgecraft/ui_server.py --publish <library> <dist>   (static site, no API)"""


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--publish" in a:
        i = a.index("--publish"); src = a[a.index("--source") + 1] if "--source" in a else ""
        publish(a[i + 1], a[i + 2], src)
    else:
        print(NO_LIVE, file=sys.stderr); sys.exit(2)
