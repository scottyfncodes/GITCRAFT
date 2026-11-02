#!/usr/bin/env python3
"""TIDEBREAKERS 3D acceptance test: builds a real game asset package with the 3D Department,
driving MeshCraft exactly as Claude Code does (MCP over stdio, through scripts/mcp.sh, so
the guard and Landlock sandbox apply), then hands the results to FilmCraft and DesignCraft.

    GITCRAFT_ROOT=<workspace> tests/acceptance_tidebreakers.py <out_dir> [--photogrammetry <images_dir>]

Writes <out_dir>/assets/<slug>_v<N>/ (GLB, glTF, FBX, OBJ, STL, .blend, textures, previews,
asset.json), <out_dir>/scene/, <out_dir>/handoffs/ and <out_dir>/REPORT.json.
TIDEBREAKERS' engine is three.js r170 (Vite + TypeScript): GLB, metres, Y up, bow at +Z."""
import json, os, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from mcp_client import Client

out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "acceptance/tidebreakers-3d")
photos = sys.argv[sys.argv.index("--photogrammetry") + 1] if "--photogrammetry" in sys.argv else None
os.makedirs(out, exist_ok=True)
env = dict(os.environ)
env.setdefault("GITCRAFT_ROOT", os.path.dirname(out)); env.setdefault("GITCRAFT_ROOTS", env["GITCRAFT_ROOT"])
MCP = os.path.join(REPO, "scripts", "mcp.sh")
report = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "engine": "three.js r170 (TIDEBREAKERS package.json)", "assets": {}, "checks": [], "handoffs": {}}


def check(label, ok, detail=""):
    report["checks"].append({"check": label, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:200]}]" if detail and not ok else ""), flush=True)


mc = Client([MCP, "meshcraft"], env=env, log=os.path.join(out, "meshcraft.stderr.log"))
ok, probe = mc.call("hardware_probe")
report["machine"] = probe["hardware"]; report["backends"] = {k: {"available": v.get("available"), "detail": v.get("version") or v.get("reason") or v.get("mode")} for k, v in probe["backends"].items()}


def gen(key, args, expect_anim=0):
    t0 = time.time()
    ok, r = mc.call("generate", dict(args, tags=["tidebreakers"]), timeout=1800)
    check(f"{key}: generated ({(r or {}).get('route', {}).get('chosen') if isinstance(r, dict) else r})", ok and r.get("status") == "done", r if not ok else r.get("error"))
    if not ok: return None
    a = r["asset"]
    ok2, md = mc.call("library_get", {"asset": a["id"]})
    g = md["geometry"]
    check(f"{key}: real geometry ({g['triangles']} tris, {g['dimensions_m']} m)", g["triangles"] > 50)
    check(f"{key}: GLB passes Blender re-import + Khronos validator + three.js r170 load", md["validation"]["status"] in ("passed", "passed-with-warnings"), md["validation"]["status"])
    check(f"{key}: preview rendered", bool(md["previews"]["thumbnail"]))
    if args.get("bake", 1) and "bbmodel" not in md["files"]:
        check(f"{key}: PNG texture maps baked", len(md["textures"]) >= 2, md["textures"])
    if expect_anim: check(f"{key}: {expect_anim}+ animation clips", len(md["animations"]) >= expect_anim, [x["name"] for x in md["animations"]])
    report["assets"][key] = {"id": md["id"], "version": md["version"], "name": md["name"], "route": md["route"], "triangles": g["triangles"],
                             "dimensions_m": g["dimensions_m"], "textures": [t["name"] for t in md["textures"]], "animations": [x["name"] for x in md["animations"]],
                             "sockets": [s["name"] for s in md["sockets"]], "validation": md["validation"]["status"], "seconds": round(time.time() - t0, 1),
                             "files": sorted(md["files"])}
    return md


STD = ["glb", "fbx", "blend"]   # the player boat ships every format; the rest GLB (engine) + FBX (DCC) + .blend (source)

# 1. the player boat (the Coastal Sloop), with sockets for every upgrade slot
boat = gen("player_boat", {"brief": "stylized low-poly player boat: the Coastal Sloop, seafoam hull, red stripe sails", "name": "TIDEBREAKERS Coastal Sloop",
                           "max_tris": 12000, "bake": 1024, "turntable": 24, "formats": ["glb", "gltf", "fbx", "obj", "stl", "blend"]})
if boat: check("player_boat: has upgrade sockets", {"socket_sail", "socket_storage", "socket_navigation", "socket_steering", "socket_hull"} <= {s["name"] for s in boat["sockets"]})
# 2. modular upgrade components (TIDEBREAKERS src/data/ship.ts slots: sail, storage, navigation, steering, hull)
UPG = {"sail_canvas": "Canvas Mainsail", "cargo_crate": "Lashed Cargo Crates", "compass_brass": "Brass Compass", "rudder_ash": "Ship's Wheel & Ash Rudder",
       "hull_copper": "Copper-Banded Hull"}
ups = {}
for u, nm in UPG.items():
    ups[u] = gen(f"upgrade_{u}", {"brief": f"boat upgrade component: {nm}", "name": f"Upgrade: {nm}", "kind": "upgrade", "params": {"upgrade": u},
                                  "max_tris": 6000, "bake": 512, "turntable": 8, "formats": STD})
# 3. floating salvage (with a looping bob animation)
salv = gen("salvage", {"brief": "floating salvage: lashed crate, barrel and buoy on driftwood", "name": "Floating Salvage", "max_tris": 6000, "bake": 1024, "formats": STD}, expect_anim=1)
# 4. island environment
isl = gen("island", {"brief": "small tropical island with palms, rocks, a stilt hut and a dock", "name": "Turtle Cay", "max_tris": 40000, "bake": 1024, "formats": STD,
                     "params": {"seed": 7}})
# 5. animated character (Mixamo-named rig) + a creature through Blockbench
crew = gen("character", {"brief": "animated pirate deckhand character, coral bandana, crimson vest", "name": "Deckhand Pip", "max_tris": 6000, "bake": 1024, "formats": STD}, expect_anim=6)
crab = gen("creature", {"brief": "blocky voxel reef crab creature", "name": "Reef Crab (Blockbench)", "bake": 0, "formats": STD})

# 6. Mixamo path: one-clip armature-only FBX files in Mixamo's download layout (generated from the
#    character's own clips: a fixture, not Mixamo data) merged back by bone name into a new version.
if crew:
    import subprocess, tempfile
    fx = os.path.join(out, "work", "mixamo_fixture"); os.makedirs(fx, exist_ok=True)
    jf = os.path.join(fx, "job.json")
    json.dump({"op": "split_clips", "out_dir": fx, "input": os.path.join(os.path.expanduser(env.get("MESHCRAFT_LIBRARY", "~/.gitcraft/meshcraft-library")), "assets", crew["id"], f"v{crew['version']}", crew["files"]["glb"]["path"]),
               "clips": ["Walk", "Jump"], "prefix": "MixamoLayout_"}, open(jf, "w"))
    subprocess.run([os.path.expanduser("~/.gitcraft/meshcraft/venv/bin/python"), os.path.join(REPO, "meshcraft", "blender", "run.py"), jf], capture_output=True)
    clips = json.load(open(os.path.join(fx, "_result.json")))["files"]["clips"]
    ok, r = mc.call("mixamo_apply", {"character": crew["id"], "animations": clips, "name": "Deckhand Pip", "tags": ["tidebreakers"]}, timeout=1200)
    check("mixamo: FBX clips merged by bone name into a new character version", ok and r["status"] == "done" and r["asset"]["version"] == 2, r)
    if ok: report["assets"]["character_mixamo_merge"] = {"id": r["asset"]["id"], "version": r["asset"]["version"], "animations": r.get("animations"),
                                                         "note": "clips are Mixamo-layout fixtures exported from the character's own rig, not downloads from mixamo.com"}
    ok, r = mc.call("mixamo_prepare_upload", {"asset": crew["id"], "out": os.path.join(fx, "deckhand_pip_mixamo_upload.fbx")})
    check("mixamo: unrigged T-pose FBX ready for mixamo.com upload", ok and os.path.getsize(r["fbx"]) > 10000, r)

# 7. photogrammetry (optional: needs a photo set; copied into the workspace so the sandboxed tool can read it)
if photos:
    dst = os.path.join(out, "work", "photos"); shutil.copytree(photos, dst, dirs_exist_ok=True); photos = dst
    ok, r = mc.call("photogrammetry", {"images": [photos], "name": "Salvage Raft (photogrammetry scan)", "wait": True, "max_tris": 20000, "formats": STD,
                                       "meshroom_overrides": ["CameraInit:defaultFieldOfView=54.4"], "crop": 0.22, "target_size": 2.4,
                                       "tags": ["tidebreakers", "scan"]}, timeout=7200)
    check("meshroom: reconstructed mesh from photos", ok and r["status"] == "done", r)
    if ok: report["assets"]["photogrammetry_scan"] = {"id": r["asset"]["id"], "geometry": r["geometry"]}

# 8. composed scene: island, boat with all five upgrades attached at their sockets, salvage, crew on the dock, crab on the beach
if all([boat, isl, salv, crew]):
    items = [{"asset": isl["id"], "name": "turtle_cay"},
             {"asset": boat["id"], "name": "player_sloop", "location": [9, -27, 0.15], "rotation": [0, 0, 28]}]
    # the canvas mainsail replaces the sloop's base sail in game, so the scene shows the other four upgrades fitted
    items += [{"asset": ups[u]["id"], "name": f"upg_{u}"} for u in ups if ups[u] and u != "sail_canvas"]
    for it in items[2:]:
        u = it["name"][4:]
        it["attach_to"] = "player_sloop:" + {"sail_canvas": "socket_sail", "cargo_crate": "socket_storage", "compass_brass": "socket_navigation",
                                             "rudder_ash": "socket_steering", "hull_copper": "socket_hull"}[u]
    items += [{"asset": salv["id"], "name": "salvage", "location": [-7, -30, 0]},
              {"asset": crew["id"], "name": "deckhand", "attach_to": "turtle_cay:socket_dock"}]
    if crab: items.append({"asset": crab["id"], "name": "crab", "attach_to": "turtle_cay:socket_spawn"})
    ok, r = mc.call("compose_scene", {"name": "TIDEBREAKERS Turtle Cay Scene", "items": items, "camera": [30, -62, 14], "look_at": [0, -20, 2],
                                       "samples": 48, "tags": ["tidebreakers"]}, timeout=2400)
    check("scene: composed in Blender from library GLBs (imported into a real 3D scene)", ok and r["status"] == "done", r)
    if ok:
        ok2, md = mc.call("library_get", {"asset": r["asset"]["id"]})
        report["assets"]["scene"] = {"id": md["id"], "items": len(items), "triangles": md["geometry"]["triangles"], "animations": [a["name"] for a in md["animations"]],
                                     "validation": md["validation"]["status"]}
        check("scene: scene GLB validates and loads in three.js r170", md["validation"]["status"] in ("passed", "passed-with-warnings"), md["validation"]["status"])

# 9. hand off: export everything into the workspace, then FilmCraft + DesignCraft consume the files
ok, lib = mc.call("library_search", {"query": "", "status": None})
mine = [a for a in lib if "tidebreakers" in a.get("tags", [])]
exported = {}
for a in mine:
    ok, r = mc.call("library_export", {"asset": a["id"], "dest": os.path.join(out, "assets")})
    if ok: exported[a["slug"]] = r["dir"]
check(f"handoff: {len(exported)} assets exported into the workspace", len(exported) >= 9, list(exported))
mc.close()

# FilmCraft: boat turntable frames → MP4
try:
    bdir = exported.get(boat["slug"]) if boat else None
    frames = sorted(os.path.join(bdir, "previews", f) for f in os.listdir(os.path.join(bdir, "previews")) if "_turn_" in f)
    fc = Client([MCP, "filmcraft"], env=env, log=os.path.join(out, "filmcraft.stderr.log"))
    run = lambda i, **p: fc.call("command_run", {"id": i, "params": p})
    run("file.newProject")
    ok, r = fc.call("media_import", {"paths": frames}); items = r["items"]
    run("file.newSequence", name="Coastal Sloop turntable", width=256, height=256, fps=24)
    t = 0.0
    for _ in range(2):
        for it in items:
            run("timeline.place", item=it, track="V1", seconds=t, duration={"seconds": 1 / 12}, audio=False); t += 1 / 12
    os.makedirs(os.path.join(out, "handoffs"), exist_ok=True)
    mp4 = os.path.join(out, "handoffs", "coastal_sloop_turntable.mp4")
    ok, r = run("file.exportMedia", path=mp4, format="h264", crf=20, wait=True, audio=False)
    fc.close()
    check("handoff → FilmCraft: turntable frames edited into an MP4", ok and os.path.exists(mp4) and os.path.getsize(mp4) > 5000, r)
    report["handoffs"]["filmcraft"] = {"input_frames": len(frames), "output": mp4, "bytes": os.path.getsize(mp4) if os.path.exists(mp4) else 0}
except Exception as e:
    check("handoff → FilmCraft", False, e)

# DesignCraft: asset sheet from every thumbnail
try:
    dc = Client([MCP, "designcraft"], env=env, log=os.path.join(out, "designcraft.stderr.log"))
    ok, r = dc.call("new_document", {"width": 1600, "height": 1000, "pages": 1, "title": "TIDEBREAKERS 3D asset sheet", "margins": 0, "facingPages": False})
    thumbs = []
    for slug, d in sorted(exported.items()):
        tp = [os.path.join(d, "previews", f) for f in os.listdir(os.path.join(d, "previews")) if f.endswith(("_thumb.png",))]
        if tp: thumbs.append((slug, tp[0]))
    cols = 5; cw = 1600 / cols
    for i, (slug, p) in enumerate(thumbs[:15]):
        x, y = (i % cols) * cw + 20, (i // cols) * 330 + 20
        ok_i, _ = dc.call("place_image", {"path": p, "x": x, "y": y, "width": cw - 40})
        dc.call("execute", {"command": "frame.create", "params": {"rect": [x, y + cw - 30, x + cw - 40, y + cw + 10], "content": "text", "text": slug.replace("_", " ")}})
    os.makedirs(os.path.join(out, "handoffs"), exist_ok=True)
    sheet = os.path.join(out, "handoffs", "tidebreakers_3d_asset_sheet.png")
    ok, r = dc.call("export_png", {"page": 0, "path": sheet, "scale": 1})
    dc.call("save_document", {"path": os.path.join(out, "handoffs", "tidebreakers_3d_asset_sheet.designcraft")})
    dc.close()
    check("handoff → DesignCraft: asset sheet laid out from the preview renders", ok and os.path.exists(sheet), r)
    report["handoffs"]["designcraft"] = {"thumbnails": len(thumbs), "output": sheet}
except Exception as e:
    check("handoff → DesignCraft", False, e)

# three.js r170 (TIDEBREAKERS' engine): load the exported scene, boat and character GLBs into one scene
try:
    import glob, subprocess
    pick = [glob.glob(os.path.join(exported[k], "*.glb"))[0] for k in exported if any(w in k for w in ("scene", "coastal_sloop", "deckhand"))]
    shot = os.path.join(out, "handoffs", "threejs_r170_import.png"); rep = os.path.join(out, "handoffs", "threejs_r170_import.json")
    r = subprocess.run(["node", os.path.join(REPO, "meshcraft", "web-check", "check.mjs"), rep, shot, *pick], capture_output=True, text=True, timeout=600)
    d = json.load(open(rep))
    check(f"three.js r170: {len(pick)} exported GLBs load into one engine scene (clips play, Khronos 0 errors)", d["ok"], r.stdout[-300:])
    report["handoffs"]["threejs"] = {"files": [os.path.relpath(p, out) for p in pick], "screenshot": os.path.relpath(shot, out),
                                     "per_file": {os.path.basename(k): {"triangles": v["three"]["triangles"], "clips": [c["name"] for c in v["three"]["clips"]],
                                                                        "khronos_errors": v["validator"]["errors"]} for k, v in d["files"].items()}}
except Exception as e:
    check("three.js r170 import", False, e)

report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
fails = [c for c in report["checks"] if not c["ok"]]
report["result"] = f"{len(report['checks']) - len(fails)}/{len(report['checks'])} checks passed"
json.dump(report, open(os.path.join(out, "REPORT.json"), "w"), indent=1)
print("\n" + report["result"])
sys.exit(1 if fails else 0)
