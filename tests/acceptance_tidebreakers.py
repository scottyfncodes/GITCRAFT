#!/usr/bin/env python3
"""TIDEBREAKERS 3D acceptance test for the consolidated 3D Department.

ForgeCraft (orchestrator) and MeshCraft (Blender specialist) are driven exactly as Claude Code
drives them: MCP over stdio through scripts/mcp.sh, so the guard and the Landlock sandbox apply.
Every Blender step ForgeCraft orders is done by MeshCraft as a child job; results land in the one
shared library. Then FilmCraft and DesignCraft consume the exported files.

    GITCRAFT_ROOT=<workspace> tests/acceptance_tidebreakers.py <out_dir> [--photogrammetry <images_dir>]

Uses its own library (GITCRAFT_3D_LIBRARY, default ~/.gitcraft/3d-library-tidebreakers, emptied
first) and snapshots it into <out_dir>/library; writes <out_dir>/handoffs/ and <out_dir>/REPORT.json.
TIDEBREAKERS' engine is three.js r170 (Vite + TypeScript): GLB, metres, Y up, bow at +Z."""
import json, os, shutil, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, REPO)

out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "acceptance/tidebreakers-3d")
photos = sys.argv[sys.argv.index("--photogrammetry") + 1] if "--photogrammetry" in sys.argv else None
os.makedirs(out, exist_ok=True)
LIB = os.path.expanduser(os.environ.get("GITCRAFT_3D_LIBRARY") or "~/.gitcraft/3d-library-tidebreakers")
if os.path.isdir(LIB): shutil.rmtree(LIB)
os.environ["GITCRAFT_3D_LIBRARY"] = LIB
os.environ.setdefault("GITCRAFT_ROOT", os.path.dirname(out)); os.environ.setdefault("GITCRAFT_ROOTS", os.environ["GITCRAFT_ROOT"])
from mcp_client import Client
from gitcraft3d import library
env = dict(os.environ)
MCP = os.path.join(REPO, "scripts", "mcp.sh")
report = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "engine": "three.js r170 (TIDEBREAKERS package.json)",
          "architecture": "ForgeCraft orchestrates (route, engine check, record, hand-off); MeshCraft does every Blender step; one shared library",
          "assets": {}, "checks": [], "handoffs": {}}


def check(label, ok, detail=""):
    report["checks"].append({"check": label, "ok": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:200]}]" if detail and not ok else ""), flush=True)


fc = Client([MCP, "forgecraft"], env=env, log=os.path.join(out, "forgecraft.stderr.log"))
mc = Client([MCP, "meshcraft"], env=env, log=os.path.join(out, "meshcraft.stderr.log"))
ok, probe = fc.call("hardware_probe")
report["machine"] = probe["hardware"]
report["backends"] = {k: {"available": v.get("available"), "detail": v.get("version") or v.get("reason") or v.get("mode")} for k, v in probe["backends"].items()}
ok, mprobe = mc.call("hardware_probe")
check("one probe: MeshCraft and ForgeCraft report the same backends", ok and mprobe["backends"].keys() == probe["backends"].keys())

ALL = ["three-web-toon", "three-web-atlas", "web-pbr", "unity-fbx", "obj-static", "stl-print", "godot-glb"]
STD = ["three-web-toon", "web-pbr", "unity-fbx"]   # engine (toon + PBR GLB) + DCC (FBX); the .blend source always ships



sname = lambda s: s["name"] if isinstance(s, dict) else s


def gen(key, args, expect_anim=0, tool="generate", expect_route=None):
    t0 = time.time()
    ok, r = fc.call(tool, dict(args, tags=["tidebreakers"] + args.get("tags", [])), timeout=7200)
    chosen = (r or {}).get("route", {}).get("chosen") if isinstance(r, dict) else None
    check(f"{key}: generated via {chosen}", ok and r.get("status") in ("done", "done_with_fallback"), r if not ok else r.get("error"))
    if not ok: return None
    if expect_route: check(f"{key}: routed to {expect_route}", chosen == expect_route, chosen)
    check(f"{key}: ForgeCraft delegated the Blender work to a MeshCraft child job", bool(r.get("children")), r.get("children"))
    ok, md = fc.call("library_get", {"asset": r["asset"]["id"]})
    g = md.get("geometry") or {}
    exports = [f["path"] for f in md["files"] if f["kind"] == "export"]
    textures = [f["path"] for f in md["files"] if f["path"].endswith(".png") and f["kind"] != "preview"]
    check(f"{key}: real geometry ({g.get('triangles')} tris, {g.get('size_m')} m)", (g.get("triangles") or 0) > 50, g)
    check(f"{key}: MeshCraft validation + Khronos + three.js r170 engine check", (md.get("deliverable_validation") or {}).get("status") in ("passed", "passed-with-warnings")
          and (md.get("engine_check") or {}).get("status") == "passed", (md.get("deliverable_validation"), (md.get("engine_check") or {}).get("status")))
    check(f"{key}: previews rendered", bool((md.get("previews") or {}).get("thumbnail")))
    check(f"{key}: provenance, licence and routing recorded", md.get("provenance", {}).get("forgecraft_job") == r["job"] and md.get("license", {}).get("tools") and md.get("route"))
    check(f"{key}: every file hashed (SHA-256)", all(len(f["sha256"]) == 64 for f in md["files"]))
    if expect_anim: check(f"{key}: {expect_anim}+ animation clips", len(md.get("animations", [])) >= expect_anim, [x["name"] for x in md.get("animations", [])])
    report["assets"][key] = {"id": md["id"], "version": md["version"], "title": md.get("title"), "route": chosen, "source_tool": md.get("source_tool"),
                             "forgecraft_job": r["job"], "meshcraft_jobs": r.get("children"), "triangles": g.get("triangles"), "size_m": g.get("size_m"),
                             "textures": textures, "animations": [x["name"] for x in md.get("animations", [])], "sockets": [sname(s) for s in md.get("sockets", [])],
                             "validation": (md.get("deliverable_validation") or {}).get("status"), "seconds": round(time.time() - t0, 1), "exports": exports}
    return md


# 1. the player boat (the Coastal Sloop), with sockets for every upgrade slot, in every export profile
boat = gen("player_boat", {"brief": "stylized low-poly player boat: the Coastal Sloop, seafoam hull, red stripe sails", "name": "TIDEBREAKERS Coastal Sloop",
                           "bake": 1024, "profiles": ALL}, expect_route="meshcraft_template")
if boat:
    check("player_boat: has upgrade sockets", {"socket_sail", "socket_storage", "socket_navigation", "socket_steering", "socket_hull"} <= {sname(s) for s in boat.get("sockets", [])},
          boat.get("sockets"))
    check("player_boat: all seven MeshCraft export profiles", all(any(f".{p}." in f["path"] for f in boat["files"]) for p in ALL), [f["path"] for f in boat["files"] if f["kind"] == "export"])
# 2. modular upgrade components (TIDEBREAKERS src/data/ship.ts slots: sail, storage, navigation, steering, hull)
UPG = {"sail_canvas": "Canvas Mainsail", "cargo_crate": "Lashed Cargo Crates", "compass_brass": "Brass Compass", "rudder_ash": "Ship's Wheel & Ash Rudder",
       "hull_copper": "Copper-Banded Hull"}
ups = {}
for u, nm in UPG.items():
    ups[u] = gen(f"upgrade_{u}", {"brief": f"boat upgrade component: {nm}", "name": f"Upgrade: {nm}", "kind": "upgrade", "template_params": {"upgrade": u},
                                  "bake": 512, "profiles": STD})
# 3. floating salvage (looping bob animation)
salv = gen("salvage", {"brief": "floating salvage: lashed crate, barrel and buoy on driftwood", "name": "Floating Salvage", "bake": 1024, "profiles": STD}, expect_anim=1)
# 4. island environment
isl = gen("island", {"brief": "small tropical island with palms, rocks, a stilt hut and a dock", "name": "Turtle Cay", "bake": 1024, "profiles": STD,
                     "template_params": {"seed": 7}})
# 5. animated character (Mixamo-named rig), a MeshCraft template prop and a Blockbench creature
crew = gen("character", {"brief": "animated pirate deckhand character, coral bandana, crimson vest", "name": "Deckhand Pip", "bake": 1024, "profiles": STD},
           expect_anim=6, expect_route="meshcraft_template")
chest = gen("meshcraft_chest", {"brief": "grand treasure chest", "name": "Grand Treasure Chest", "template_params": {"tier": "grand"}, "profiles": STD}, expect_anim=1)
crab = gen("creature", {"brief": "blocky voxel reef crab creature", "name": "Reef Crab (Blockbench)", "profiles": STD}, expect_route="blockbench")

# 6. Mixamo path: MeshCraft's fixture writes armature-only FBX clips in Mixamo's download layout (fixtures, not
#    mixamo.com data); ForgeCraft orders the merge, MeshCraft merges by bone name into a new character version.
if crew:
    fx = os.path.join(out, "work", "mixamo"); os.makedirs(fx, exist_ok=True)
    fixture = os.path.join(out, "work", "mixamo_fixture.py"); shutil.copy(os.path.join(HERE, "fixtures", "mixamo_fixture.py"), fixture)
    clips = []
    for nm in ("Walking", "Sneak Walk"):
        okf, _ = mc.call("run_script", {"path": fixture, "args": {"kind": "clip", "out": fx, "clip_name": f"{nm}.fbx"}}, timeout=600)
        p = os.path.join(fx, f"{nm}.fbx")
        if okf and os.path.exists(p): clips.append(p)
    ok, r = fc.call("mixamo_apply", {"character": crew["id"], "animations": clips, "name": "Deckhand Pip", "tags": ["tidebreakers"]}, timeout=1800)
    check("mixamo: FBX clips merged by bone name into a new character version", ok and r["status"] == "done" and r["asset"]["version"] == 2, r)
    if ok: report["assets"]["character_mixamo_merge"] = {"id": r["asset"]["id"], "version": r["asset"]["version"], "animations": r.get("animations"),
                                                         "note": "clips are Mixamo-layout fixtures written by tests/fixtures/mixamo_fixture.py, not downloads from mixamo.com"}
    ok, r = fc.call("mixamo_prepare_upload", {"asset": crew["id"], "out": os.path.join(fx, "deckhand_pip_mixamo_upload.fbx")}, timeout=900)
    check("mixamo: mesh-only T-pose FBX ready for mixamo.com upload", ok and os.path.getsize(os.path.join(fx, "deckhand_pip_mixamo_upload.fbx")) > 10000, r)

# 7. photogrammetry: Meshroom (ForgeCraft backend) → MeshCraft process_mesh (crop, cleanup, rescale, bake)
if photos:
    dst = os.path.join(out, "work", "photos"); shutil.copytree(photos, dst, dirs_exist_ok=True)
    gen("photogrammetry_scan", {"images": [dst], "name": "Salvage Raft (photogrammetry scan)", "wait": True, "max_tris": 20000, "profiles": STD,
                                "meshroom_overrides": ["CameraInit:defaultFieldOfView=54.4"], "crop": 0.22, "target_size": 2.4, "tags": ["scan"]},
        tool="photogrammetry", expect_route="meshroom")

# 8. composed scene: island, boat with four upgrades on its sockets, salvage, crew on the dock, crab on the beach
if all([boat, isl, salv, crew]):
    SOCK = {"cargo_crate": "socket_storage", "compass_brass": "socket_navigation", "rudder_ash": "socket_steering", "hull_copper": "socket_hull"}
    items = [{"asset": isl["id"], "name": "turtle_cay"}, {"asset": boat["id"], "name": "player_sloop", "location": [9, -27, 0.15], "rotation": [0, 0, 28]}]
    # the canvas mainsail replaces the sloop's base sail in game, so the scene shows the other four upgrades fitted
    items += [{"asset": ups[u]["id"], "name": f"upg_{u}", "attach_to": f"player_sloop:{s}"} for u, s in SOCK.items() if ups.get(u)]
    items += [{"asset": salv["id"], "name": "salvage", "location": [-7, -30, 0]}, {"asset": crew["id"], "name": "deckhand", "attach_to": "turtle_cay:socket_dock"}]
    if crab: items.append({"asset": crab["id"], "name": "crab", "attach_to": "turtle_cay:socket_spawn"})
    scene = gen("scene", {"name": "TIDEBREAKERS Turtle Cay Scene", "items": items, "camera": [30, -62, 14], "look_at": [0, -20, 2], "samples": 48}, tool="compose_scene",
                expect_route="meshcraft_scene")
    if scene: report["assets"]["scene"]["items"] = len(items)

# 9. hand off: export everything into the workspace (hash-verified), then FilmCraft + DesignCraft consume the files
ok, lib = fc.call("library_search", {"query": "tidebreakers"})
exported = {}
for a in (lib if ok else []):
    ok, r = fc.call("library_export", {"asset": a["id"], "dest": os.path.join(out, "assets")})
    if ok: exported[a["id"]] = r["dir"]
check(f"handoff: {len(exported)} assets exported into the workspace with verified hashes", len(exported) >= 11, list(exported))
ok, jl = fc.call("jobs_list", {"limit": 200})
tools = sorted({j["tool"] for j in jl["jobs"]}) if ok else []
check("jobs: ForgeCraft jobs and the MeshCraft child jobs they started share one job store", {"generate", "run_pipeline", "compose_scene"} <= set(tools), tools)
report["jobs"] = {"count": len(jl["jobs"]) if ok else 0, "tools": tools}
fc.close(); mc.close()
os.makedirs(os.path.join(out, "handoffs"), exist_ok=True)

# FilmCraft: a review reel from every asset's preview views → MP4
try:
    frames = []
    for aid, d in sorted(exported.items()):
        pv = os.path.join(d, "previews")
        frames += sorted(os.path.join(pv, f) for f in os.listdir(pv) if f.endswith(".png") and "engine_check" not in f and "_anim" not in f)[:4] if os.path.isdir(pv) else []
    fm = Client([MCP, "filmcraft"], env=env, log=os.path.join(out, "filmcraft.stderr.log"))
    run = lambda i, **p: fm.call("command_run", {"id": i, "params": p})
    run("file.newProject")
    ok, r = fm.call("media_import", {"paths": frames}); items = r["items"]
    run("file.newSequence", name="TIDEBREAKERS 3D review reel", width=512, height=512, fps=24)
    t = 0.0
    for it in items:
        run("timeline.place", item=it, track="V1", seconds=t, duration={"seconds": 0.5}, audio=False); t += 0.5
    mp4 = os.path.join(out, "handoffs", "tidebreakers_3d_review_reel.mp4")
    ok, r = run("file.exportMedia", path=mp4, format="h264", crf=20, wait=True, audio=False)
    fm.close()
    check(f"handoff → FilmCraft: {len(frames)} preview renders edited into an MP4 review reel", ok and os.path.exists(mp4) and os.path.getsize(mp4) > 5000, r)
    report["handoffs"]["filmcraft"] = {"input_frames": len(frames), "output": os.path.relpath(mp4, out), "bytes": os.path.getsize(mp4) if os.path.exists(mp4) else 0}
except Exception as e:
    check("handoff → FilmCraft", False, e)

# DesignCraft: asset sheet from every thumbnail
try:
    dc = Client([MCP, "designcraft"], env=env, log=os.path.join(out, "designcraft.stderr.log"))
    ok, r = dc.call("new_document", {"width": 1600, "height": 1100, "pages": 1, "title": "TIDEBREAKERS 3D asset sheet", "margins": 0, "facingPages": False})
    thumbs = []
    for aid, d in sorted(exported.items()):
        md = json.load(open(os.path.join(d, "asset.json"))); th = (md.get("previews") or {}).get("thumbnail")
        if th and os.path.exists(os.path.join(d, th)): thumbs.append((md.get("title") or aid, os.path.join(d, th)))
    cols = 5; cw = 1600 / cols
    for i, (title, p) in enumerate(thumbs[:15]):
        x, y = (i % cols) * cw + 20, (i // cols) * 360 + 20
        dc.call("place_image", {"path": p, "x": x, "y": y, "width": cw - 40})
        dc.call("execute", {"command": "frame.create", "params": {"rect": [x, y + cw - 30, x + cw - 40, y + cw + 10], "content": "text", "text": title}})
    sheet = os.path.join(out, "handoffs", "tidebreakers_3d_asset_sheet.png")
    ok, r = dc.call("export_png", {"page": 0, "path": sheet, "scale": 1})
    dc.call("save_document", {"path": os.path.join(out, "handoffs", "tidebreakers_3d_asset_sheet.designcraft")})
    dc.close()
    check(f"handoff → DesignCraft: asset sheet laid out from {len(thumbs)} preview renders", ok and os.path.exists(sheet), r)
    report["handoffs"]["designcraft"] = {"thumbnails": len(thumbs), "output": os.path.relpath(sheet, out)}
except Exception as e:
    check("handoff → DesignCraft", False, e)

# three.js r170 (TIDEBREAKERS' engine): the scene GLB, which contains the boat, upgrades, island, salvage, deckhand and crab,
# was loaded by MeshCraft's engine check in Chromium; keep its screenshot and report as the engine import evidence
try:
    sc = report["assets"].get("scene")
    md = library.get(sc["id"], sc["version"]); ec = md["engine_check"]
    shot = os.path.join(out, "handoffs", "threejs_r170_scene.png"); shutil.copy2(os.path.join(md["dir"], ec["screenshot"]), shot)
    json.dump(ec, open(os.path.join(out, "handoffs", "threejs_r170_scene.json"), "w"), indent=1)
    check("three.js r170: the composed scene GLB loads in GLTFLoader with every check passing", ec["status"] == "passed", ec.get("checks"))
    report["handoffs"]["threejs"] = {"glb": ec.get("glb"), "screenshot": os.path.relpath(shot, out), "checks": [c["check"] for c in ec.get("checks", [])]}
except Exception as e:
    check("three.js r170 scene import", False, e)

# snapshot the library (the deployed department UI is built from it)
snap = library.snapshot(os.path.join(out, "library"), probe)
report["library"] = {"path": "library/", "assets": snap["assets"], "bytes": snap["bytes"]}
report["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
fails = [c for c in report["checks"] if not c["ok"]]
report["result"] = f"{len(report['checks']) - len(fails)}/{len(report['checks'])} checks passed"
json.dump(report, open(os.path.join(out, "REPORT.json"), "w"), indent=1)
print("\n" + report["result"])
sys.exit(1 if fails else 0)
