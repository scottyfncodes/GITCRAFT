#!/usr/bin/env python3
"""MeshCraft's structural helpers (engine/kit.py log_wall, mound, beam) through scripts/mcp.sh
(guard + Landlock sandbox): a log wall stacks its courses to height and leaves its door open, a mound
sits on its base at its size, a beam runs exactly from one point to the other.

These came from ROCKSLIDE (its lodge, the working mountain's fences, drifts, guy wires and braces),
where they were written once per script; now any project gets them from the kit.

    tests/test_meshcraft_structural.py
"""
import json, os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__)); from mcp_client import Client
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ws = os.environ.get("GITCRAFT_ROOT") or tempfile.mkdtemp(prefix="meshcraft-structural-")
os.makedirs(ws, exist_ok=True)
pal = os.path.join(ws, "palette.json"); json.dump({"Log": "#7D6150"}, open(pal, "w"))
script = os.path.join(ws, "structural_kit.py"); shutil.copyfile(os.path.join(HERE, "fixtures", "structural_kit.py"), script)
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_MESHCRAFT_LIBRARY=os.path.join(ws, "library"))
res = []
def check(label, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:400]}]"))

c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "meshcraft"], env=env)
ok, out = c.call("run_script", {"path": script, "args": {"palette": pal}, "save": False}, 600)
check("run_script builds the structural pieces", ok, out)
if ok:
    line = [l for l in (out.get("stdout", "") if isinstance(out, dict) else str(out)).splitlines() if l.startswith("{")][-1]
    r = json.loads(line)
    w = r["wall"]
    check("log_wall stacks round logs to its height (9 courses of 0.34 m)", abs(w["max"][2] - 3.06) < 0.02 and abs(w["min"][2]) < 0.02, w)
    check("log_wall spans its length plus the end grain", abs(w["max"][0] - 3.04) < 0.01 and abs(w["min"][0] + 3.04) < 0.01, w)
    check("log_wall leaves its opening clear (no log across the door)", r["logs_in_door"] == 0, r["logs_in_door"])
    d = r["drift"]
    # (a 10-sided base: its x extent is exact, its y extent cos(18 deg) of the half-depth)
    check("mound stands on its base at its size", abs(d["min"][2]) < 1e-3 and abs(d["max"][2] - 0.6) < 1e-3 and abs(d["max"][0] - 3.0) < 1e-3
          and abs(d["min"][0] + 1.0) < 1e-3 and abs(d["max"][1] - 2.0 - 0.951) < 2e-3, d)
    b = r["brace"]
    check("beam runs exactly from a to b", abs(r["brace_len"] - 2 * 2 ** 0.5) < 1e-3 and abs(b["max"][2] - 2.0) < 0.08 and abs(b["min"][2]) < 0.08, r)
c.close()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
