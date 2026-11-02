#!/usr/bin/env python3
"""End-to-end MeshCraft test through scripts/mcp.sh (guard + Landlock sandbox).

  * every template runs the full pipeline (build → preview → validate → export →
    Khronos + round-trip) with no failed checks;
  * the chest GLB passes the Three.js engine check against its contract;
  * a hostile run_script cannot read ~/.claude.json, write outside the
    workspace, or open a network connection (the kernel sandbox stops it).

    tests/test_meshcraft.py [template ...]
"""
import json, os, sys, tempfile, shutil
sys.path.insert(0, os.path.dirname(__file__)); from mcp_client import Client
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ws = os.environ.get("GITCRAFT_ROOT") or tempfile.mkdtemp(prefix="meshcraft-ws-")
os.makedirs(ws, exist_ok=True)
pal = os.path.join(ws, "palette.json")
json.dump({"Honey Timber": "#D9954F", "Timber": "#9A5A2E", "Deep Tide": "#0E3B66", "Midnight Swell": "#0A2142", "Doubloon Gold": "#F4C542",
           "Gold Deep": "#C98A12", "Sunlit Amber": "#FF9F2E", "Hibiscus": "#E0607E", "Sailcloth Cream": "#F6EAD0", "Palm Green": "#3FA55A",
           "Jungle Deep": "#1E6B4E", "Lagoon Teal": "#1FB5B0", "Shallows Aqua": "#7FE3D6", "Coral Flame": "#FF6B4A"}, open(pal, "w"))
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
res = []
def check(label, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:400]}]"))

c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "meshcraft"], env=env)
ok, st = c.call("meshcraft_status"); check("meshcraft starts sandboxed", ok and st.get("sandbox", "").startswith("landlock"), st)
templates = sys.argv[1:] or st["templates"]
CLIPS = {"chest": ("lid_open", "end"), "lantern": ("swing", "mid"), "flag": ("wave", "mid"), "sail": ("fill", "end"), "crab": ("wave", 14)}
for t in templates:
    clip = CLIPS.get(t)
    brief = {"asset_id": f"test_{t}", "template": t, "palette": pal, "out_dir": os.path.join(ws, t), "profiles": ["three-web-toon", "unity-fbx"],
             "preview": {"size": 256, "views": ["three_quarter"], "poses": [{"clip": clip[0], "at": clip[1]}] if clip else []}}
    ok, r = c.call("run_pipeline", {"brief": brief}, timeout=900)
    s = r["validation"]["summary"] if ok else {}
    check(f"{t}: pipeline with no failed checks", ok and s.get("fail") == 0, s if ok else r)
    if ok and t == "chest":
        glb = next(e["path"] for e in r["exports"] if e["format"] == "glb")
        ok2, e = c.call("engine_check", {"glb": glb, "clip": "lid_open", "time": 5, "contract": r["build"]["contract"], "size": 256}, timeout=300)
        check("chest: three@0.170 engine check passes its contract", ok2 and all(x["level"] == "pass" for x in e["checks"]), e if not ok2 else [x for x in e["checks"] if x["level"] != "pass"])

hostile = os.path.join(ws, "hostile.py")
open(hostile, "w").write('''
import os, socket
out = {}
try: open(os.path.expanduser("~/.claude.json")).read(10); out["read_home"] = "LEAKED"
except Exception as e: out["read_home"] = type(e).__name__
try: open("/tmp/meshcraft_escape.txt", "w").write("x"); out["write_tmp"] = "ESCAPED"
except Exception as e: out["write_tmp"] = type(e).__name__
try: socket.create_connection(("151.101.0.223", 443), timeout=5); out["net"] = "CONNECTED"
except Exception as e: out["net"] = type(e).__name__
print(out)
''')
ok, r = c.call("run_script", {"path": hostile})
out = r.get("stdout", "") if ok else str(r)
check("run_script cannot read outside the workspace", "PermissionError" in out.split("read_home")[1][:30] if "read_home" in out else False, out)
check("run_script cannot write outside the workspace", "'write_tmp': 'PermissionError'" in out, out)
check("run_script has no network", "'net': 'PermissionError'" in out, out)
ok, r = c.call("inspect_palette", {"path": os.path.expanduser("~/.claude.json")})
check("guard refuses paths outside the workspace", not ok and "GITCRAFT policy" in str(r), r)
c.close()
print(f"\n{sum(res)}/{len(res)} checks passed"); sys.exit(0 if all(res) else 1)
