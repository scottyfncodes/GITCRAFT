#!/usr/bin/env python3
"""ForgeCraft deliverable verification: regression tests for the engine-check status and per-clip playback.

A built asset is not proof that it loads or plays. These tests prove:
  1  three.js could not execute (no GLB, MeshCraft's engine check unavailable or erroring, no checks
     returned) → the deliverable is `blocked` and the job is `blocked` with the reason; never `passed*`
  2  an invalid or unloadable GLB fails
  3  every clip is played on its own (a clip frozen alone fails alone; the others still pass)
  4  every clip must move the asset (all clips frozen → all fail)
  5  existing successful jobs keep their behaviour: an animated character, an animated MeshCraft
     template and a static asset still finish `done` and validated, through scripts/mcp.sh
Real runs: three@0.170 in headless Chromium via MeshCraft's engine_check, Blender via MeshCraft. Only
case 1's "cannot execute" is injected, at ForgeCraft's MeshCraft call, with MeshCraft's own errors.

    tests/test_forgecraft_engine.py
"""
import json, os, shutil, struct, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "forgecraft"))
from mcp_client import Client

ws = tempfile.mkdtemp(prefix="forgecraft-engine-ws-")
lib = os.path.join(ws, "3d-library"); os.environ.update(GITCRAFT_3D_LIBRARY=lib, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
from gitcraft3d import library
import pipeline, meshcraft as mc

results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:600]}]"), flush=True)

CLIPS = ["Attack", "Idle", "Interact", "Jump", "Run", "Walk"]
PASSING = ("passed", "passed-with-warnings")

# ---------------------------------------------------------------- 1a: the status rule itself
ds = pipeline.deliverable_status
table = {
    "engine passed, no warnings → passed": ds({"fail": 0, "warn": 0}, {"status": "passed"}) == "passed",
    "engine passed, MeshCraft warnings → passed-with-warnings": ds({"fail": 0, "warn": 2}, {"status": "passed"}) == "passed-with-warnings",
    "engine skipped → blocked": ds({"fail": 0, "warn": 0}, {"status": "skipped"}) == "blocked",
    "engine error → blocked": ds({"fail": 0, "warn": 1}, {"status": "error"}) == "blocked",
    "engine status missing → blocked": ds({}, {}) == "blocked",
    "engine failed → failed": ds({"fail": 0}, {"status": "failed"}) == "failed",
    "MeshCraft failure → failed even if the engine passed": ds({"fail": 1}, {"status": "passed"}) == "failed",
}
check("status rule: only an engine check that ran and passed can pass", all(table.values()), {k: v for k, v in table.items() if not v})

# ---------------------------------------------------------------- 5: existing jobs, real, through scripts/mcp.sh (guard + Landlock)
fc = Client([os.path.join(REPO, "scripts", "mcp.sh"), "forgecraft"], env=dict(os.environ))
ok, d = fc.call("generate", {"brief": "animated pirate deckhand, coral bandana", "name": "Engine Crew"}, timeout=1500)
md = library.get(d["asset"]["id"], d["asset"]["version"]) if ok and d.get("asset") else {}
eng = md.get("engine_check") or {}
check("existing job: animated character still finishes done and validated", ok and d["status"] == "done" and d.get("validation") in PASSING, d)
names = sorted(c["name"] for c in eng.get("clips", []))
checks = {c["check"]: c for c in eng.get("checks", [])}
check("all six animations are played, each on its own", names == CLIPS and checks.get("engine_all_clips_played", {}).get("level") == "pass"
      and all(f"engine_clip_motion:{n}" in checks for n in CLIPS), (names, list(checks)))
check("each of the six animations moves the rig in three.js", len(eng.get("clips", [])) == 6 and all(c["moves"] and c["max_delta"] > 1e-4 for c in eng["clips"]), eng.get("clips"))
check("every expected clip is required to be present in the GLB", all(checks.get(f"engine_clip:{n}", {}).get("level") == "pass" for n in CLIPS), list(checks))
glb = os.path.join(md.get("dir", ""), eng.get("glb", "")) if md else ""

ok, t = fc.call("generate", {"brief": "a treasure chest", "name": "Engine Chest"}, timeout=1500)
tm = library.get(t["asset"]["id"], t["asset"]["version"]) if ok and t.get("asset") else {}
te = tm.get("engine_check") or {}
check("existing job: animated MeshCraft template (chest) still done, its clips each move", ok and t["status"] == "done" and t.get("validation") in PASSING
      and te.get("clips") and all(c["moves"] for c in te["clips"]), (t, te.get("clips")))
ok, s = fc.call("generate", {"brief": "a wooden barrel", "name": "Engine Barrel"}, timeout=1500)
sm = library.get(s["asset"]["id"], s["asset"]["version"]) if ok and s.get("asset") else {}
check("existing job: static asset (no clips) still done and validated in three.js", ok and s["status"] == "done" and s.get("validation") in PASSING
      and (sm.get("engine_check") or {}).get("status") == "passed" and not (sm.get("engine_check") or {}).get("clips"), s)
fc.close()

# ---------------------------------------------------------------- 3 + 4: per-clip motion, with the real engine
def freeze(src, dst, only=None):
    """Copy a GLB with every animation channel (or only clip `only`'s) held at its first keyframe."""
    b = bytearray(open(src, "rb").read()); n = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + n]); base = 20 + n + 8
    for a in j["animations"]:
        if only and a["name"] != only: continue
        for smp in a["samplers"]:
            acc = j["accessors"][smp["output"]]; bv = j["bufferViews"][acc["bufferView"]]
            comps = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[acc["type"]]; off = base + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
            stride = bv.get("byteStride") or 4 * comps; first = bytes(b[off:off + 4 * comps])
            for k in range(1, acc["count"]): b[off + k * stride: off + k * stride + 4 * comps] = first
    open(dst, "wb").write(b)

work = os.path.join(ws, "engine-work"); os.makedirs(work, exist_ok=True); log = os.path.join(work, "log.txt")
res = {"build": {"actions": CLIPS}}
main = {"profile": "web-pbr" if "web-pbr" in os.path.basename(glb) else "three-web-toon"}   # the profile the pipeline checked
def only_motion_fails(e):   # the failure must come from clip motion alone, not from some unrelated check
    return all(c["check"].startswith("engine_clip_motion:") for c in e.get("checks", []) if c["level"] == "fail")
def verify(path): return pipeline.engine_verify(path, main, "meshcraft_template", res, work, log)
if os.path.exists(glb):
    g = os.path.join(work, "character.glb"); shutil.copy(glb, g)
    e = verify(g)
    check("real character GLB: engine check passes with six moving clips", e["status"] == "passed" and sum(c["moves"] for c in e["clips"]) == 6, e)
    fz = os.path.join(work, "frozen_all.glb"); freeze(g, fz); e = verify(fz)
    check("all keyframes frozen → every clip reported static and the deliverable fails", e["status"] == "failed" and len(e["clips"]) == 6
          and not any(c["moves"] for c in e["clips"]) and only_motion_fails(e) and pipeline.deliverable_status({}, e) == "failed", e.get("reason"))
    fj = os.path.join(work, "frozen_jump.glb"); freeze(g, fj, only="Jump"); e = verify(fj)
    static = [c["name"] for c in e.get("clips", []) if not c["moves"]]
    check("only Jump frozen → only Jump fails: clips are tested independently", e["status"] == "failed" and static == ["Jump"] and only_motion_fails(e)
          and "engine_clip_motion:Jump" in e.get("reason", ""), (static, e.get("reason")))
else:
    check("character GLB available for the per-clip tests", False, glb)

# ---------------------------------------------------------------- 2: invalid or unloadable assets cannot pass
trunc = os.path.join(work, "truncated.glb"); open(trunc, "wb").write(open(glb, "rb").read()[:600] if os.path.exists(glb) else b"glTF")
junk = os.path.join(work, "not_a_model.glb"); open(junk, "wb").write(b"this is not a glTF file\n" * 20)
for label, path in (("truncated GLB", trunc), ("non-glTF file named .glb", junk)):
    e = verify(path); st = pipeline.deliverable_status({"fail": 0, "warn": 0}, e)
    check(f"{label} cannot pass (status {st})", st in ("failed", "blocked") and st not in PASSING, e)

# ---------------------------------------------------------------- 1b: three.js could not execute
e = pipeline.engine_verify(None, None, "meshcraft_template", res, work, log)
check("no GLB export → engine check skipped → deliverable blocked, with the reason", e["status"] == "skipped" and pipeline.deliverable_status({}, e) == "blocked" and e.get("reason"), e)
real_call = mc.call
def unavailable(tool, args, *a, **k):
    if tool == "engine_check": raise mc.MeshCraftError("MeshCraft engine_check: RuntimeError: engine check needs `npm ci` in meshcraft/engine_check (three@0.170, gltf-validator)")
    return real_call(tool, args, *a, **k)
def empty(tool, args, *a, **k):
    if tool == "engine_check": return {"ok": True}
    return real_call(tool, args, *a, **k)
for label, stub in (("MeshCraft's engine check unavailable", unavailable), ("engine check returns no checks", empty)):
    mc.call = stub
    try: e = verify(glb if os.path.exists(glb) else junk)
    finally: mc.call = real_call
    check(f"{label} → deliverable blocked, not passed", e["status"] == "error" and pipeline.deliverable_status({"fail": 0, "warn": 0}, e) == "blocked" and e.get("reason"), e)

# the whole pipeline: a real MeshCraft build whose engine check cannot run ends `blocked`, with the reason
mc.call = unavailable
try: rec = pipeline.run({"brief": "a treasure chest", "name": "Unverified Chest"})
finally: mc.call = real_call
um = library.get(rec["asset"]["id"], rec["asset"]["version"]) if rec.get("asset") else {}
check("full job whose engine check cannot run → job blocked with the reason, library says blocked, never passed",
      rec["status"] == "blocked" and "NOT verified" in (rec.get("error") or "") and "npm ci" in (rec.get("error") or "")
      and (um.get("deliverable_validation") or {}).get("status") == "blocked" and rec["asset"].get("validation") == "blocked",
      (rec["status"], rec.get("error"), (um.get("deliverable_validation") or {}).get("status")))

print(f"\n{sum(results)}/{len(results)} checks passed   (workspace: {ws})")
sys.exit(0 if all(results) else 1)
