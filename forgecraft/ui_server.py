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
import json, os, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hardware, routing
from backends import blockbench, mixamo

UI = os.path.join(HERE, "ui")
JOB_KEYS = ("id", "spec", "status", "created", "updated", "attempts", "stages", "error", "asset", "plan", "compute")


def state(lib_root, base_url, probe=None, mode="live", source=""):
    idx = json.load(open(os.path.join(lib_root, "index.json"))) if os.path.exists(os.path.join(lib_root, "index.json")) else {"assets": []}
    assets = []
    for e in idx["assets"]:
        vs = {}
        for v in e["versions"]:
            p = os.path.join(lib_root, "assets", e["id"], f"v{v}", "asset.json")
            if not os.path.exists(p): continue
            md = json.load(open(p)); md["base"] = f"{base_url}assets/{e['id']}/v{v}/"
            vs[str(v)] = md
        if vs: assets.append({"id": e["id"], "latest": str(max(map(int, vs))), "versions": vs})
    jobs = []
    jd = os.path.join(lib_root, "jobs")
    if os.path.isdir(jd):
        for f in sorted(os.listdir(jd), reverse=True):
            if f.endswith(".json"):
                try:
                    j = json.load(open(os.path.join(jd, f)))
                    if j.get("spec") and j["spec"].get("uploads"): j["spec"] = dict(j["spec"], uploads=f"{len(j['spec']['uploads'])} file(s)")
                    jobs.append({k: j.get(k) for k in JOB_KEYS})
                except ValueError: pass
    return {"mode": mode, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": source,
            "probe": probe or hardware.probe(), "rules": routing.RULES, "bb_templates": sorted(blockbench.TEMPLATES),
            "mixamo": {"steps": mixamo.GUIDE, "bones": ["mixamorig:" + b for b in mixamo.MIXAMO_CORE]}, "assets": assets, "jobs": jobs}


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
