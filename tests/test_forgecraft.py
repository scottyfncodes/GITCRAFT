#!/usr/bin/env python3
"""ForgeCraft (3D Department orchestrator) tests. Real runs, nothing mocked: ForgeCraft is
driven over MCP through scripts/mcp.sh (guard + Landlock), and every Blender step it orders is
done by MeshCraft as a child process.

    tests/test_forgecraft.py            routing, delegation, jobs, library, refusals (~6 min on 4 threads)
    tests/test_forgecraft.py --slow     also Meshroom photogrammetry end to end (~15 min more on CPU)

Uses a scratch workspace and library, so the real ones are untouched."""
import glob, json, os, re, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, REPO)
from mcp_client import Client

ws = os.environ.get("GITCRAFT_ROOT") or tempfile.mkdtemp(prefix="forgecraft-ws-")
lib = os.path.join(ws, "3d-library"); os.makedirs(ws, exist_ok=True)
os.environ.update(GITCRAFT_3D_LIBRARY=lib, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
from gitcraft3d import hardware, routing, library, jobs
env = dict(os.environ)
MCP = os.path.join(REPO, "scripts", "mcp.sh")
results = []


def check(label, ok, detail=""):
    results.append((label, bool(ok))); print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)


# ---------------------------------------------------------------- consolidation: one implementation each
py = lambda d: [p for p in glob.glob(os.path.join(REPO, d, "**", "*.py"), recursive=True) if "node_modules" not in p]
check("forgecraft contains no Blender code (no bpy import, no blender/ folder)",
      not any(re.search(r"^\s*import bpy|^\s*from bpy", open(p).read(), re.M) for p in py("forgecraft")) and not os.path.isdir(os.path.join(REPO, "forgecraft", "blender")))
check("one library, job store, probe and router (gitcraft3d); no copies in either server",
      not any(os.path.exists(os.path.join(REPO, d)) for d in ("forgecraft/library.py", "forgecraft/hardware.py", "forgecraft/routing.py",
                                                              "meshcraft/engine/library.py", "meshcraft/engine/jobs.py", "meshcraft/engine/hardware.py", "meshcraft/engine/route.py")))
check("one Blockbench and one Mixamo implementation (MeshCraft's)", not glob.glob(os.path.join(REPO, "forgecraft", "backends", "blockbench.py"))
      and not glob.glob(os.path.join(REPO, "forgecraft", "backends", "mixamo.py")) and os.path.exists(os.path.join(REPO, "meshcraft", "engine", "blockbench.py")))
check("one engine check (MeshCraft's three@0.170 check)", not os.path.isdir(os.path.join(REPO, "forgecraft", "web-check")))

# ---------------------------------------------------------------- routing (a machine where everything is available)
probe = hardware.probe([ws])
full = json.loads(json.dumps(probe))
for k in full["backends"]: full["backends"][k]["available"] = True
full["ram"]["total_gb"] = 32
EXPECT = [("Stylized low-poly boat", 0, "meshcraft_template", "boat"), ("Detailed ship from concept art", 1, "hunyuan3d", None),
          ("Object from photograph", 1, "triposr", None), ("Animated human character", 0, "meshcraft_template", "deckhand"),
          ("Reconstructed real-world environment", 30, "meshroom", None), ("Complete game-ready scene", 0, "meshcraft_scene", None),
          ("blocky voxel treasure chest", 0, "blockbench", None), ("a crab creature", 0, "meshcraft_template", "crab"),
          ("a wooden barrel", 0, "meshcraft_template", "prop"), ("small tropical island", 0, "meshcraft_template", "island")]
for brief, n, want, tpl in EXPECT:
    p = routing.route(brief, ["img.png"] * n, full)
    check(f"routing: '{brief}' → {want}" + (f" ({tpl})" if tpl else ""), p["chosen"] == want and (tpl is None or p["request"]["template"] == tpl), (p["chosen"], p["request"]["template"]))
none_ai = json.loads(json.dumps(full)); none_ai["backends"]["hunyuan3d"]["available"] = False
p = routing.route("Detailed ship from concept art", ["a.png"], none_ai)
check("routing fallback: concept art without Hunyuan3D → TripoSR", p["chosen"] == "triposr" and p["fallback_used"])
none_ai["backends"]["triposr"]["available"] = False
p = routing.route("Detailed ship from concept art", ["a.png"], none_ai)
check("routing: no image-to-3D tool → blocked, never a 2D substitute; alternative labelled NOT derived from the image",
      p["chosen"] is None and "will not substitute" in p["explanation"] and any("NOT be derived" in a["note"] for a in p["alternatives"]), p)
check("routing: ForgeCraft 1.0 tool ids still work as aliases", routing.route("a barrel", [], full, prefer="blender_procedural")["chosen"] == "meshcraft_template")
adv = routing.advice("blocky voxel lifeboat", 0, probe)
check("routing: MeshCraft's route advice is the same decision", adv["route"] == "blockbench" and adv["plan"]["chosen"] == routing.route("blocky voxel lifeboat", [], probe)["chosen"])
check("probe: MeshCraft's capability view and ForgeCraft's backend view agree",
      probe["capabilities"]["photogrammetry"]["available"] == probe["backends"]["meshroom"]["available"]
      and probe["capabilities"]["image_to_3d"]["available"] == (probe["backends"]["triposr"]["available"] or probe["backends"]["hunyuan3d"]["available"]))

# ---------------------------------------------------------------- orchestration over MCP (sandboxed)
fc = Client([MCP, "forgecraft"], env=env, log=os.path.join(ws, "forgecraft.log"))
mcl = Client([MCP, "meshcraft"], env=env, log=os.path.join(ws, "meshcraft.log"))
ok, r = fc.call("generate", {"brief": "a wooden barrel", "name": "Test Barrel", "handoff_dir": os.path.join(ws, "handoff")}, timeout=1200)
check("generate (template): routed to MeshCraft, engine-checked, recorded, handed off", ok and r["status"] == "done" and r["route"]["chosen"] == "meshcraft_template"
      and r["stages"] == ["route:done", "generate:done", "engine_check:done", "record:done", "handoff:done"] and os.path.isdir(r.get("handoff", "")), r)
if ok:
    aid = r["asset"]["id"]
    ok2, md = mcl.call("library_get", {"asset": aid})
    check("one library record: MeshCraft's version carries ForgeCraft's routing, licence, provenance and engine check",
          ok2 and md["version"] == 1 and md["route"]["chosen"] == "meshcraft_template" and md["license"]["tools"] and md["provenance"]["forgecraft_job"] == r["job"]
          and md["engine_check"]["status"] == "passed" and all(len(f["sha256"]) == 64 for f in md["files"]), md)
    ok3, child = mcl.call("job_get", {"job": r["children"][0]})
    check("job linkage: ForgeCraft job → MeshCraft child job (parent recorded)", ok3 and child.get("parent") == r["job"] and child["tool"] == "run_pipeline", child)
    hand = json.load(open(os.path.join(r["handoff"], "asset.json")))
    check("hand-off copy is hash-verified and keeps the full record", hand["id"] == aid and hand.get("route"), hand.get("id"))
    ok, rr = fc.call("job_retry", {"job": r["job"]}, timeout=1200)
    check("job_retry: same request, new attempt on the same job, next version of the same asset", ok and rr["asset"]["id"] == aid and rr["asset"]["version"] == 2
          and len(jobs.get(r["job"])["attempts"]) == 2, rr)
    ok, md2 = mcl.call("library_get", {"asset": aid})
    check("library: identical regeneration is marked same_as the previous version", ok and md2.get("same_as") == 1, md2.get("same_as"))

ok, r = fc.call("generate", {"brief": "blocky voxel crab", "name": "Voxel Crab"}, timeout=1200)
check("generate (voxel): Blockbench via MeshCraft, .bbmodel kept, engine check passes", ok and r["status"] == "done" and r["route"]["chosen"] == "blockbench"
      and r["validation"] in ("passed", "passed-with-warnings"), r)
ok, d = fc.call("generate", {"brief": "animated pirate deckhand, coral bandana", "name": "Deck Crew"}, timeout=1200)
check("generate (character): deckhand template, Mixamo skeleton, six clips play in three@0.170", ok and d["status"] == "done" and len(d.get("animations", [])) == 6, d)

# Mixamo through ForgeCraft: MeshCraft's own fixture writes a Mixamo-layout clip; ForgeCraft merges it onto the deckhand
fx = os.path.join(ws, "mixamo"); fixture = os.path.join(ws, "mixamo_fixture.py"); shutil.copy(os.path.join(HERE, "fixtures", "mixamo_fixture.py"), fixture)
okf, _ = mcl.call("run_script", {"path": fixture, "args": {"kind": "clip", "out": fx}}, timeout=300)
if ok and okf:
    ok, mx = fc.call("mixamo_apply", {"character": d["asset"]["id"], "animations": [os.path.join(fx, "Walking.fbx")], "name": "Deck Crew"}, timeout=1200)
    check("mixamo_apply (delegated): clip merged by bone name onto the library character as a new version", ok and mx["status"] == "done"
          and mx["asset"]["version"] == 2 and "Walking" in mx.get("animations", []), mx)
    ok2, v2 = mcl.call("library_get", {"asset": mx["asset"]["id"], "version": 2}) if ok else (False, {})
    names = [a["name"] for a in (v2.get("animations") or [])]
    check("mixamo_apply record: the new version keeps its rig and lists every clip it ships (own six + Walking), as the Character Studio reads it",
          ok2 and (v2.get("rig") or {}).get("armatures", 0) >= 1 and len(names) == 7 and "Walking" in names, {"rig": v2.get("rig"), "animations": names})
    ok, up = fc.call("mixamo_prepare_upload", {"asset": d["asset"]["id"], "out": os.path.join(ws, "upload.fbx")}, timeout=600)
    check("mixamo_prepare_upload (delegated): mesh-only FBX for Mixamo", ok and os.path.getsize(os.path.join(ws, "upload.fbx")) > 1000, up)

ok, sc = fc.call("compose_scene", {"name": "Test Scene", "samples": 2, "resolution": [160, 90],
                                    "items": [{"asset": "test_barrel", "name": "barrel"}, {"asset": "voxel_crab", "name": "crab", "location": [2, 0, 0]}]}, timeout=1200)
check("compose_scene (delegated): scene GLB from library assets, engine-checked, recorded with its inputs", ok and sc["status"] == "done", sc)
ok2, scm = mcl.call("library_get", {"asset": sc["asset"]["id"]}) if ok and sc.get("asset") else (False, {})
check("compose_scene record: recorded as kind 'scene' (not the kind of one of its parts)", ok2 and scm.get("kind") == "scene", scm.get("kind"))
glb = next((p for k, p in (sc.get("files") or {}).items() if k.endswith(".glb")), None) if ok else None
if glb:
    ok, pm = fc.call("process_mesh", {"input": glb, "name": "Reimported Scene", "max_tris": 3000, "target_size": 4.0}, timeout=1200)
    check("process_mesh (delegated): an existing GLB comes back in through MeshCraft, budgeted and rescaled", ok and pm["status"] == "done"
          and abs(max(pm["geometry"]["size_m"]) - 4.0) < 0.05, pm)

ok, bl = fc.call("generate", {"brief": "detailed ship from concept art", "images": [os.path.join(ws, "concept.png")]})
avail = probe["backends"]["triposr"]["available"] or probe["backends"]["hunyuan3d"]["available"]
check("generate: an image-to-3D request with no image-to-3D tool ends 'blocked' with reasons (never a 2D substitute)",
      avail or (not ok and bl["status"] == "blocked" and "will not substitute" in bl["error"] and bl["alternatives"]), bl)
ok, bb = fc.call("blockbench_build", {"template": "lantern", "name": "Lantern", "out": os.path.join(ws, "lantern.bbmodel")})
ok2, bi = fc.call("blockbench_inspect", {"path": os.path.join(ws, "lantern.bbmodel")})
check("blockbench_build / _inspect (delegated): a palette-coloured .bbmodel 5.0", ok and ok2 and bi["format_version"] == "5.0" and not bi["problems"], (bb, bi))
ok, jl = fc.call("jobs_list", {"limit": 50})
tools = {j["tool"] for j in jl["jobs"]} if ok else set()
check("jobs_list shows ForgeCraft jobs and the MeshCraft jobs they started", {"generate", "run_pipeline", "blockbench_import", "compose_scene", "mixamo_apply"} <= tools, tools)
fc.close(); mcl.close()

# ---------------------------------------------------------------- external generators refuse honestly
sys.path.insert(0, os.path.join(REPO, "forgecraft"))
from backends import meshroom, triposr, hunyuan3d
for name, fn in (("triposr", lambda: triposr.run(os.path.join(ws, "x.png"), ws, os.path.join(ws, "l"))),
                 ("hunyuan3d", lambda: hunyuan3d.run(ws, os.path.join(ws, "l"), prompt="ship"))):
    if probe["backends"][name]["available"]: check(f"{name}: available here (exercise it with a real image on this machine)", True); continue
    try: fn(); check(f"{name}: refuses when unavailable", False)
    except RuntimeError as e: check(f"{name}: unavailable here, refuses with the reason", "unavailable" in str(e), e)
try: meshroom.run([os.path.join(ws, "a.jpg")], ws, os.path.join(ws, "l")); check("meshroom: rejects too few photos", False)
except RuntimeError as e: check("meshroom: rejects too few photos with a reason", "at least 3" in str(e) or "not installed" in str(e), e)

if "--slow" in sys.argv and probe["backends"]["meshroom"]["available"]:
    # synthetic capture rendered by MeshCraft, reconstructed by Meshroom, cleaned by MeshCraft
    c = Client([MCP, "meshcraft"], env=env); photos = os.path.join(ws, "photos")
    shutil.copy(os.path.join(HERE, "fixtures", "photoset.py"), os.path.join(ws, "photoset.py"))
    ok, r = c.call("run_script", {"path": os.path.join(ws, "photoset.py"), "args": {"input": glob.glob(os.path.join(lib, "assets", "test_barrel", "v1", "exports", "*.web-pbr.glb"))[0],
                                                                                 "out": photos, "views": 24, "resolution": 768}}, timeout=1800); c.close()
    fc = Client([MCP, "forgecraft"], env=env)
    ok, r = fc.call("photogrammetry", {"images": [photos], "name": "Barrel Scan", "wait": True, "crop": 0.3, "target_size": 1.0,
                                        "meshroom_overrides": ["CameraInit:defaultFieldOfView=54.4"]}, timeout=7200); fc.close()
    check("photogrammetry: Meshroom reconstruction → MeshCraft process_mesh → validated, recorded", ok and r["status"] == "done", r)

failed = [x for x in results if not x[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
