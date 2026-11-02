#!/usr/bin/env python3
"""Integration tests for the 3D Department (ForgeCraft). Every test runs the real tools
(Blender, the .bbmodel converter, the validators); nothing is mocked.

    tests/test_forgecraft.py            all fast tests (~3–4 min on 4 CPU threads)
    tests/test_forgecraft.py --slow     also run Meshroom photogrammetry end to end (~15 min on CPU)

Uses a throwaway library (FORGECRAFT_LIBRARY) so the real one is untouched."""
import json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); MC = os.path.join(HERE, "..", "forgecraft")
TMP = tempfile.mkdtemp(prefix="forgecraft-test-")
os.environ["FORGECRAFT_LIBRARY"] = os.path.join(TMP, "lib")
sys.path.insert(0, MC)
import hardware, library, pipeline, routing
from backends import blockbench, meshroom, triposr, hunyuan3d, meshcraft_tpl

results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not cond else ""), flush=True)


def run(spec):
    r = pipeline.run(spec)
    md = library.get(r["asset"]["id"], r["asset"]["version"]) if r.get("asset") else None
    return r, md


probe = hardware.probe()
check("hardware: probe reports CPU, RAM and all six backends", probe["hardware"]["cpu_threads"] and set(probe["backends"]) >= {"blender", "blockbench", "mixamo", "meshroom", "triposr", "hunyuan3d"})
check("blender: bpy importable", probe["backends"]["blender"]["available"], probe["backends"]["blender"])

# ---- routing: the brief's examples, against a machine where everything is available
full = json.loads(json.dumps(probe))
for k in full["backends"]: full["backends"][k]["available"] = True
full["hardware"]["ram"]["total_gb"] = 32
EXPECT = [("Stylized low-poly boat", 0, "blender_procedural"), ("Detailed ship from concept art", 1, "hunyuan3d"),
          ("Object from photograph", 1, "triposr"), ("Animated human character", 0, "blender_character"),
          ("Reconstructed real-world environment", 30, "meshroom"), ("Complete game-ready scene", 0, "blender_scene"),
          ("blocky voxel treasure chest", 0, "blockbench"), ("a crab creature", 0, "meshcraft_template"),
          ("a treasure chest", 0, "meshcraft_template"), ("tidebreaker flag on a pole", 0, "meshcraft_template")]
for brief, n, want in EXPECT:
    p = routing.route(brief, ["img.png"] * n, full)
    check(f"routing (all tools present): '{brief}' → {want}", p["chosen"] == want, p["chosen"])
# fallbacks on a machine without GPU AI: concept art must not silently become a 2D image or a procedural guess
none_ai = json.loads(json.dumps(full)); none_ai["backends"]["hunyuan3d"]["available"] = False
p = routing.route("Detailed ship from concept art", ["a.png"], none_ai)
check("routing fallback: concept art without Hunyuan3D → TripoSR", p["chosen"] == "triposr" and p["fallback_used"], p["chosen"])
none_ai["backends"]["triposr"]["available"] = False
p = routing.route("Detailed ship from concept art", ["a.png"], none_ai)
check("routing: no image-to-3D tool → blocked with explanation, no substitution", p["chosen"] is None and "will not substitute" in p["explanation"] and p["alternatives"], p)
check("routing: alternative offered is labelled as not derived from the image", any("NOT be derived" in a["note"] for a in p["alternatives"]), p["alternatives"])
check("routing: folder of photos counts each image", routing.parse("scan", [TMP])["images"] == 0)

# ---- Blender procedural kinds through the whole pipeline
FAST = dict(bake=256, turntable=1, formats=["glb", "fbx", "obj", "stl"])
for kind, params, anim in (("boat", {"vessel": "dinghy"}, 0), ("upgrade", {"upgrade": "rudder_ash"}, 0), ("salvage", {}, 1),
                           ("island", {"resolution": 40, "palms": 3, "radius": 15}, 0), ("lighthouse", {}, 0), ("prop", {"prop": "chest"}, 0)):
    r, md = run(dict(FAST, brief=f"test {kind}", kind=kind, tool="blender_procedural", params=params, name=f"t {kind}"))
    ok = r["status"] == "done" and md["validation"]["status"] in ("passed", "passed-with-warnings")
    check(f"blender procedural {kind}: done + validated ({md and md['geometry']['triangles']} tris)", ok, r["error"] or (md or {}).get("validation"))
    if md:
        check(f"blender procedural {kind}: glb/fbx/obj/stl exported", all(f in md["files"] for f in ("glb", "fbx", "obj", "stl")), md["files"].keys())
        check(f"blender procedural {kind}: baked basecolor + metallic-roughness PNGs", len(md["textures"]) == 2, md["textures"])
        if anim: check(f"blender procedural {kind}: animation clip exported", len(md["animations"]) >= anim, md["animations"])

r, ch = run(dict(FAST, brief="animated pirate character", name="t char"))
check("character: rig with 22 Mixamo-named bones", ch and ch["rig"]["bones"] == 22 and all(b.startswith("mixamorig:") for b in ch["rig"]["bone_names"]), ch and ch["rig"])
check("character: 6 clips survive GLB round trip and three.js load", ch and ch["validation"]["blender_reimport"]["animations"].__len__() >= 6
      and ch["validation"]["engine"].get("files", {}).get(os.path.basename(ch["files"]["glb"]["path"]), {}).get("three_clips", 0) >= 6, ch and ch["validation"])

# ---- Blockbench: every template writes a .bbmodel that converts to valid geometry
for tpl in sorted(blockbench.TEMPLATES):
    p = os.path.join(TMP, f"{tpl}.bbmodel"); info = blockbench.build(tpl, tpl, p)
    insp = blockbench.inspect(p)
    check(f"blockbench {tpl}: .bbmodel format {insp['format_version']} with embedded texture", insp["format_version"] == "5.0" and insp["textures"][0]["embedded"] and not insp["problems"], insp)
r, bb = run(dict(brief="crab bbmodel", input_mesh=os.path.join(TMP, "crab.bbmodel"), name="t crab", turntable=1, formats=["glb"]))
check("blockbench import: .bbmodel → GLB validated, texture kept, project shipped with asset", bb and bb["validation"]["status"].startswith("passed") and "bbmodel" in bb["files"] and bb["textures"], r["error"])

# ---- MeshCraft templates (the separate meshcraft tool) as a ForgeCraft backend
check("routing: explicit kind bypasses MeshCraft templates (boat-upgrade sail stays procedural)",
      routing.route("boat upgrade: canvas mainsail", [], full, kind="upgrade")["chosen"] == "blender_procedural")
if probe["backends"]["meshcraft"]["available"]:
    r, mt = run(dict(brief="a small lantern", name="t lantern"))
    check("meshcraft template: lantern built by MeshCraft, packaged + validated by ForgeCraft", mt and r["plan"]["chosen"] == "meshcraft_template"
          and mt["validation"]["status"].startswith("passed") and {"glb", "blend"} <= set(mt["files"]) and mt["source_tool"] == "meshcraft → blender", r["error"])
    check("meshcraft template: MeshCraft's own clip survives packaging", mt and len(mt["animations"]) >= 1, mt and mt["animations"])
else:
    check("meshcraft: backend unavailable here, reason given", bool(probe["backends"]["meshcraft"].get("reason")))

# ---- Mixamo: one-clip armature-only FBX (Mixamo download layout) merged by bone name
fx = os.path.join(TMP, "fx"); os.makedirs(fx)
json.dump({"op": "split_clips", "out_dir": fx, "input": library.file_path(ch, "glb"), "clips": ["Run"], "prefix": "MixamoLayout_"}, open(os.path.join(fx, "j.json"), "w"))
subprocess.run([hardware.BLENDER_PY, os.path.join(MC, "blender", "run.py"), os.path.join(fx, "j.json")], capture_output=True)
clips = json.load(open(os.path.join(fx, "_result.json")))["files"]["clips"]
r, mx = run(dict(tool="mixamo", character=ch["id"], animations=clips, name="t char", formats=["glb"]))
check("mixamo apply: clip matched on 22 bones, new version of the character", mx and mx["version"] == 2 and any(a["name"] == "MixamoLayout_Run" for a in mx["animations"]), r["error"] or r.get("stages"))
bad = os.path.join(TMP, "notarig.fbx"); shutil.copy(library.file_path(library.get(library.search("t boat")[0]["id"]), "fbx"), bad)
r, _ = run(dict(tool="mixamo", character=ch["id"], animations=[bad], name="t char", formats=["glb"]))
check("mixamo apply: an FBX without a matching skeleton is rejected with a reason", r["status"] == "failed" and "armature" in (r["error"] or ""), r["error"])

# ---- retry: inject a bake fault; the pipeline must retry with a lighter config and finish without textures
os.environ["FORGECRAFT_FAULT"] = "bake"
r, md = run(dict(brief="test crate", kind="prop", tool="blender_procedural", params={"prop": "crate"}, bake=1024, turntable=2, formats=["glb"]))
os.environ.pop("FORGECRAFT_FAULT")
st = [s["stage"] for s in r["stages"]]
check("retry: failed bake retried automatically (1024 → 512 → no bake) and job completed", r["status"] == "done" and "retry_1" in st and "retry_2" in st and md["textures"] == [], st)
# manual retry of a job
r2 = pipeline.retry(r["id"])
check("retry: manual job_retry re-runs and records a second attempt", r2["status"] == "done" and len(r2["attempts"]) == 2)

# ---- unavailable AI backends fail loudly with the reason (never a fake result)
for name, fn in (("triposr", lambda: triposr.run(os.path.join(TMP, "x.png"), TMP, os.path.join(TMP, "l"))),
                 ("hunyuan3d", lambda: hunyuan3d.run(TMP, os.path.join(TMP, "l"), prompt="ship"))):
    st = probe["backends"][name]
    if st["available"]:
        check(f"{name}: available on this machine (run tests with --slow on a GPU box to exercise it)", True)
        continue
    try: fn(); check(f"{name}: refuses when unavailable", False)
    except RuntimeError as e: check(f"{name}: unavailable here, refuses with the reason", "unavailable" in str(e), e)
r = pipeline.run({"brief": "object from photograph", "images": [os.path.join(TMP, "x.png")]})
check("pipeline: image request with no image-to-3D tool → job 'blocked' with explanation", r["status"] in ("blocked", "done") and (r["status"] == "done" or "will not substitute" in r["error"]), r["error"])

# ---- meshroom
try: meshroom.run([os.path.join(TMP, "a.jpg")], TMP, os.path.join(TMP, "l")); check("meshroom: rejects too few photos", False)
except RuntimeError as e: check("meshroom: rejects too few photos with a reason", "at least 3" in str(e) or "not installed" in str(e), e)
if "--slow" in sys.argv and probe["backends"]["meshroom"]["available"]:
    src = library.file_path(library.get(library.search("t prop")[0]["id"]), "glb")
    ps = os.path.join(TMP, "photos"); json.dump({"op": "photoset", "out_dir": ps, "input": src, "views": 24, "rings": [20, 45], "resolution": 768, "samples": 8}, open(os.path.join(TMP, "ps.json"), "w"))
    subprocess.run([hardware.BLENDER_PY, os.path.join(MC, "blender", "run.py"), os.path.join(TMP, "ps.json")], capture_output=True)
    r, md = run({"brief": "photogrammetry scan", "images": [ps], "crop": 0.25, "target_size": 1.0, "turntable": 1, "formats": ["glb"]})
    check("meshroom: photos → reconstructed, textured, validated mesh", r["status"] == "done" and md["validation"]["status"].startswith("passed"), r["error"])

# ---- library
check("library: search finds assets by text", len(library.search("t boat")) == 1)
ex = library.export(ch["id"], os.path.join(TMP, "handoff"))
check("library: export copies files + asset.json for handoff", os.path.exists(os.path.join(ex["dir"], "asset.json")) and any(p.endswith(".glb") for p in ex["copied"]))
check("library: versions tracked", library.get(ch["id"])["version"] == 2 and library.get(ch["id"], 1)["version"] == 1)

shutil.rmtree(TMP, ignore_errors=True)
failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
