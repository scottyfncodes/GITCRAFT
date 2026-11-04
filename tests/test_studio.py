#!/usr/bin/env python3
"""GITCRAFT Studio test: every department through the real launcher (scripts/mcp.sh studiocraft:
guard + Landlock sandbox, no network), plus the contract, routing, the catalogue and ForgeCraft's
department tools. Each department produces and verifies at least one real artifact.

    tests/test_studio.py                 everything (Blender actions too when MeshCraft's Blender is installed)
    tests/test_studio.py --quick         skip the slow Blender/Chromium-heavy actions
    GITCRAFT_STUDIO_PROOF=<dir>          keep the outputs there (default: a temp workspace)

Actions whose runtime is not installed must report `blocked` (never a fake result); they are listed
as SKIP with the reason, not counted as passes. Exit 1 on any failure."""
import json, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
# the harness itself makes and compares images (Pillow, numpy): use the Studio's venv when this Python lacks them
try:
    import numpy, PIL  # noqa: F401
except ImportError:
    _vpy = os.path.join(os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.expanduser("~/.gitcraft/studio"), "venv", "bin", "python")
    # compare prefixes: a venv's python is a symlink to the same interpreter binary
    if os.access(_vpy, os.X_OK) and os.path.realpath(sys.prefix) != os.path.realpath(os.path.dirname(os.path.dirname(_vpy))):
        os.execv(_vpy, [_vpy] + sys.argv)
    raise
sys.path.insert(0, HERE)
from mcp_client import Client

QUICK = "--quick" in sys.argv
ws = os.path.abspath(os.environ.get("GITCRAFT_STUDIO_PROOF") or tempfile.mkdtemp(prefix="gitcraft-studio-"))
os.makedirs(ws, exist_ok=True)
GAME = os.path.join(ws, "mini_game"); shutil.rmtree(GAME, ignore_errors=True); shutil.copytree(os.path.join(HERE, "fixtures", "studio", "mini_game"), GAME)
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog", "catalog.sqlite"),
           GITCRAFT_3D_LIBRARY=os.path.join(ws, "3d-library"))
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not cond else ""), flush=True)


def skip(label, why): print(f"SKIP {label}: {why}", flush=True)


c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=env, log=os.path.join(ws, "studiocraft.log"))
tools = {t["name"]: t for t in c.tools()}
check("studiocraft lists discovery tools and one tool per department action", {"studio_status", "department_describe", "route", "run"} <= set(tools) and len(tools) >= 50, len(tools))
ok, st = c.call("studio_status")
depts = {d["department"]: d for d in st["departments"]}
check("nine departments discovered", set(depts) == {"audiocraft", "animcraft", "worldcraft", "fxcraft", "materialcraft", "levelcraft", "cinematiccraft", "testcraft", "assetcraft"}, sorted(depts))
ready = lambda d, a: depts[d]["actions"].get(a) == "ready"
ok, man = c.call("department_describe", {"department": "audiocraft"})
check("manifest: request schemas, dependencies with live status, licensed tools", ok and all(k in man for k in ("actions", "dependencies_status", "tools", "examples", "limits")) and
      all(v.get("license") for v in man["tools"].values()))

# ---- contract: input validation and policy
ok, r = c.call("audiocraft_sfx", {"preset": "no-such-preset", "out_dir": f"{ws}/x"})
check("bad request refused with a readable message", not ok and "preset" in str(r), r)
ok, r = c.call("audiocraft_sfx", {"preset": "coin", "frobnicate": 1, "out_dir": f"{ws}/x"})
check("unknown parameter refused", not ok and "frobnicate" in str(r), r)
ok, r = c.call("audiocraft_sfx", {"preset": "coin", "out_dir": "/root/elsewhere"})
check("output outside the workspace refused by the GITCRAFT policy", not ok and "GITCRAFT policy" in str(r), r)


def run(tool, args, label, need=None, timeout=1800, expect_checks=True):
    d, a = tool.split("_", 1)
    if need and not ready(d, a): skip(label, depts[d]["actions"].get(a)); return None
    t = time.time(); ok, r = c.call(tool, args, timeout=timeout)
    if isinstance(r, dict) and r.get("status") == "blocked": skip(label, r.get("reason")); return None
    good = ok and isinstance(r, dict) and r.get("status") == "ok" and r.get("outputs") and all(o.get("ok") and o.get("sha256") for o in r["outputs"])
    if expect_checks: good = good and r.get("checks") and all(x["ok"] for x in r["checks"])
    check(f"{label} ({time.time() - t:.1f} s)", good, (r.get("error") if isinstance(r, dict) else r) or [x for x in (r.get("checks") or []) if not x["ok"]])
    if good and not os.path.exists(r["record"]): check(f"{label}: provenance record written", False)
    return r if good else None


def mocap_take(target):
    """AnimCraft mocap on a real photo (MediaPipe's own test image, fetched at test time) turned into a short
    swaying clip: landmarks → BVH → Blender import → retarget onto the auto-rigged hero."""
    if not ready("animcraft", "mocap"): return skip("animcraft: mocap", depts["animcraft"]["actions"].get("mocap"))
    import subprocess, urllib.request
    d = f"{ws}/anim/mocap_src"; os.makedirs(d, exist_ok=True); jpg = f"{d}/pose.jpg"
    try: urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-assets/pose.jpg", jpg)
    except Exception as e: return skip("animcraft: mocap", f"test photo unreachable ({e})")
    for i, a in enumerate([0, 4, 8, 12, 8, 4, 0, -4, -8, -12, -8, -4]):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", jpg, "-vf", f"rotate={a}*PI/180:fillcolor=white,scale=640:-2", f"{d}/f_{i:02d}.png"], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "12", "-i", f"{d}/f_%02d.png", "-pix_fmt", "yuv420p", f"{d}/take.mp4"], check=True)
    r = run("animcraft_mocap", {"input": f"{d}/take.mp4", "fps": 12, "target": target, "out_dir": f"{ws}/anim/mocap", "name": "take"},
            "animcraft: mocap video → BVH (FK + Blender checked) → retargeted onto the hero", need=True)
    if r: check("animcraft: mocap BVH has every frame", r["mocap"]["bvh"]["frames"] == 12 and r["mocap"]["detected_frames"] >= 10, r["mocap"])
    run("animcraft_mocap", {"input": jpg, "out_dir": f"{ws}/anim/mocap_still", "name": "still"}, "animcraft: mocap from a single photo (eased pose clip)", need=True)


# ---- AudioCraft
r = run("audiocraft_sfx", {"preset": "coin", "variations": 2, "out_dir": f"{ws}/audio/sfx"}, "audiocraft: sfx (2 variations, WAV + OGG, measured)", need=True)
if r: check("audiocraft: sfx registered in the catalogue", r.get("catalog", {}).get("registered", 0) >= 4, r.get("catalog"))
r = run("audiocraft_ambience", {"kind": "ocean", "seconds": 6, "out_dir": f"{ws}/audio/amb"}, "audiocraft: seamless ambience loop", need=True)
if r: check("audiocraft: WAV carries smpl loop points", any(o.get("loop") for o in r["outputs"] if o["format"] == "wav"))
r = run("audiocraft_music", {"mood": "heroic", "bars": 4, "out_dir": f"{ws}/audio/music", "name": "theme"}, "audiocraft: adaptive music (aligned stems, MIDI, loop)", need=True)
theme = f"{ws}/audio/music/theme.wav"
run("audiocraft_voice", {"lines": [{"id": "l1", "text": "The tide waits for no one."}], "voice": "bm_george", "out_dir": f"{ws}/audio/voice"}, "audiocraft: Kokoro voice line", need=True)
if os.path.exists(theme):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", "0.9", "-i", "anullsrc=r=44100:cl=stereo", "-i", theme, "-i", theme,
                    "-filter_complex", "[0][1][2]concat=n=3:v=0:a=1", "-t", "60", f"{ws}/audio/intro_theme.wav"], check=True, timeout=120)
    r = run("audiocraft_loop", {"input": f"{ws}/audio/intro_theme.wav", "min_seconds": 4, "out_dir": f"{ws}/audio/loop"}, "audiocraft: loop point found in audio with an intro", need=True)
    if r:
        period = json.load(open(f"{ws}/audio/music/theme.layers.json"))["loop"]["end"]
        check("audiocraft: detected loop length equals the true period", abs((r["loop"]["end"] - r["loop"]["start"]) - period) <= 2, (r["loop"], period))
    run("audiocraft_process", {"input": theme, "lufs": -16, "out_dir": f"{ws}/audio/proc"}, "audiocraft: EBU R128 normalisation to -16 LUFS", need=True)
    run("audiocraft_convert", {"input": theme, "formats": ["ogg", "mp3"], "out_dir": f"{ws}/audio/conv"}, "audiocraft: convert to OGG + MP3", need=True)

# ---- WorldCraft
run("worldcraft_terrain", {"preset": "island", "resolution": 129, "mesh_resolution": 65, "out_dir": f"{ws}/world/island"}, "worldcraft: eroded island (maps, scatter, coastline, GLB in three.js)", need=True)
run("worldcraft_caves", {"resolution": 40, "out_dir": f"{ws}/world/cave"}, "worldcraft: closed cave mesh", need=True)
run("worldcraft_ocean", {"resolution": 64, "frames": 8, "out_dir": f"{ws}/world/ocean"}, "worldcraft: time-looping FFT ocean", need=True)
run("worldcraft_sky", {"preset": "sunset", "width": 512, "cube_size": 128, "out_dir": f"{ws}/world/sky"}, "worldcraft: sky + cubemap", need=True)

# ---- MaterialCraft
run("materialcraft_generate", {"material": "cobblestone", "resolution": 256, "moss": 0.4, "out_dir": f"{ws}/mat/cobble"}, "materialcraft: weathered PBR set, seamless, sphere in three.js", need=True)
from PIL import Image
import numpy as np
g = np.zeros((128, 128, 3), np.uint8); g[..., 0] = np.linspace(0, 255, 128)[None, :]; g[..., 2] = np.linspace(255, 0, 128)[:, None]
Image.fromarray(g).save(f"{ws}/gradient.png")
r = run("materialcraft_seamless", {"input": f"{ws}/gradient.png", "out_dir": f"{ws}/mat/seamless"}, "materialcraft: make a non-tiling image seamless", need=True)
if r: check("materialcraft: seam got smaller", r["seam"]["after"] < r["seam"]["before"], r["seam"])

# ---- LevelCraft
for kind, size in (("dungeon", (48, 36)), ("platformer", (96, 20)), ("overworld", (64, 48))):
    r = run("levelcraft_generate", {"kind": kind, "width": size[0], "height": size[1], "seed": 3, "out_dir": f"{ws}/levels/{kind}"},
            f"levelcraft: {kind} solved, Tiled TMJ loads in Phaser 3, LDtk validates + reads back, blockout GLB", need=True)
    if r: check(f"levelcraft: {kind} LDtk project written", any(o["path"].endswith(".ldtk") for o in r["outputs"]), [o["path"] for o in r["outputs"]])

# ---- FXCraft
r = run("fxcraft_flipbook", {"effect": "fire", "frames": 16, "frame_size": 64, "out_dir": f"{ws}/fx/fire"}, "fxcraft: fire flipbook loops exactly", need=True)
run("fxcraft_emitter", {"effect": "explosion", "frames": 16, "frame_size": 64, "out_dir": f"{ws}/fx/boom"}, "fxcraft: explosion emitter plays in three.js", need=True)
r = run("fxcraft_quarks", {"effect": "magic", "frames": 16, "frame_size": 64, "out_dir": f"{ws}/fx/quarks"}, "fxcraft: three.quarks system reloads with QuarksLoader and simulates", need=True)
if r: check("fxcraft: three.quarks JSON + usage written", {".quarks.json", ".quarks.usage.json"} <= {o["path"][o["path"].index(".quarks"):] for o in r["outputs"] if ".quarks" in o["path"]})

# ---- TestCraft
run("testcraft_smoke", {"target": GAME, "viewports": ["desktop", "phone"], "out_dir": f"{ws}/qa/smoke"}, "testcraft: smoke test on desktop + phone", need=True)
run("testcraft_play", {"target": GAME, "steps": [{"hold": "ArrowRight", "ms": 1500}, {"assert": "window.game.score >= 2", "name": "collects both coins"},
                                                  {"hold": "ArrowRight", "ms": 2000}, {"assert": "window.game.x < 420", "name": "the wall blocks the player"}], "out_dir": f"{ws}/qa/play"},
    "testcraft: scripted gameplay with state assertions", need=True)
run("testcraft_perf", {"target": GAME, "seconds": 2, "min_fps": 20, "out_dir": f"{ws}/qa/perf"}, "testcraft: FPS profile", need=True)
r = run("testcraft_visual_diff", {"target": GAME, "baseline_dir": f"{ws}/qa/baseline", "out_dir": f"{ws}/qa/vd1"}, "testcraft: visual baseline created", need=True)
run("testcraft_visual_diff", {"target": GAME, "baseline_dir": f"{ws}/qa/baseline", "out_dir": f"{ws}/qa/vd2"}, "testcraft: unchanged game matches its baseline", need=True)
if os.path.exists(f"{ws}/qa/play/desktop_loaded.png") and os.path.exists(f"{ws}/qa/play/desktop_final.png"):
    ok, r = c.call("testcraft_visual_diff", {"baseline": f"{ws}/qa/play/desktop_loaded.png", "current": f"{ws}/qa/play/desktop_final.png", "out_dir": f"{ws}/qa/vd3"})
    check("testcraft: a changed screen is reported as a regression", isinstance(r, dict) and r.get("status") == "failed" and r["comparisons"][0]["mismatch"] > 0, r if not isinstance(r, dict) else r.get("comparisons"))
run("testcraft_assets", {"folder": f"{ws}/world", "out_dir": f"{ws}/qa/assets"}, "testcraft: asset integrity (incl. Khronos on GLBs)", need=True)

# ---- Blender departments
if not QUICK:
    r = run("animcraft_demo_character", {"out_dir": f"{ws}/anim/demo"}, "animcraft: demo humanoid", need=True)
    if r:
        r = run("animcraft_autorig", {"input": f"{ws}/anim/demo/demo_humanoid.glb", "out_dir": f"{ws}/anim/rig", "name": "hero"}, "animcraft: auto-rig with heat weights", need=True)
    if r:
        r = run("animcraft_animate", {"input": f"{ws}/anim/rig/hero.glb", "clips": ["idle", "walk"], "out_dir": f"{ws}/anim/clips", "name": "hero_anim"}, "animcraft: idle + walk clips play in three.js", need=True)
    if r:
        run("animcraft_autorig", {"input": f"{ws}/anim/demo/demo_humanoid.glb", "naming": "mixamo", "out_dir": f"{ws}/anim/rig", "name": "hero_mixamo"}, "animcraft: Mixamo-named rig", need=True)
        run("animcraft_retarget", {"source": f"{ws}/anim/clips/hero_anim.glb", "clip": "walk", "target": f"{ws}/anim/rig/hero_mixamo.glb", "out_dir": f"{ws}/anim/retarget"},
            "animcraft: retarget walk across bone naming schemes", need=True)
        mocap_take(f"{ws}/anim/rig/hero.glb")
        run("animcraft_spritesheet", {"input": f"{ws}/anim/clips/hero_anim.glb", "clips": ["walk"], "directions": 2, "frames": 4, "size": 64, "samples": 4, "out_dir": f"{ws}/anim/sprites"},
            "animcraft: sprite sheets from a 3D clip", need=True)
    run("animcraft_physics", {"count": 4, "frames": 48, "out_dir": f"{ws}/anim/physics"}, "animcraft: rigid-body drop settles on the ground", need=True)
    run("fxcraft_destruction", {"pieces": 8, "frames": 36, "out_dir": f"{ws}/fx/destruction"}, "fxcraft: Voronoi destruction with baked physics", need=True)
    run("cinematiccraft_shot", {"input": f"{ws}/world/island/terrain_island.glb", "move": "orbit", "arc": 90, "duration": 1, "fps": 12, "resolution": [320, 180], "samples": 4, "out_dir": f"{ws}/cine/orbit"},
        "cinematiccraft: rendered orbit shot + camera path", need=True)
run("cinematiccraft_title_card", {"text": "GITCRAFT", "duration": 1.5, "fps": 12, "resolution": [640, 360], "out_dir": f"{ws}/cine/title"}, "cinematiccraft: animated title card", need=True)
clips = [{"path": f"{ws}/cine/title/title.mp4"}] + ([{"path": f"{ws}/cine/orbit/shot_orbit.mp4"}] if os.path.exists(f"{ws}/cine/orbit/shot_orbit.mp4") else [{"path": f"{ws}/world/island/terrain_island_preview.png", "seconds": 1.5}])
run("cinematiccraft_assemble", {"clips": clips, "music": theme, "resolution": [640, 360], "out_dir": f"{ws}/cine/teaser"}, "cinematiccraft: teaser with crossfade and music", need=True)
run("cinematiccraft_capture", {"target": GAME, "steps": [{"hold": "ArrowRight", "ms": 800}], "resolution": [640, 360], "out_dir": f"{ws}/cine/capture"}, "cinematiccraft: gameplay capture", need=True)

# ---- AssetCraft (over everything above)
r = run("assetcraft_scan", {"folder": ws, "default_license": "CC0-1.0", "out_dir": f"{ws}/assets/scan"}, "assetcraft: scan the workspace", need=True)
shutil.copy(f"{ws}/gradient.png", f"{ws}/gradient_copy.png")
run("assetcraft_register", {"files": [f"{ws}/gradient_copy.png"], "out_dir": f"{ws}/assets/reg"}, "assetcraft: register a file", need=True)
ok, r = c.call("assetcraft_duplicates", {"out_dir": f"{ws}/assets/dup"})
check("assetcraft: exact duplicate found", ok and any(f"{ws}/gradient_copy.png" in g for g in r["duplicates"]["exact"]), r.get("duplicates") if isinstance(r, dict) else r)
Image.fromarray(g).resize((96, 96)).save(f"{ws}/gradient_small.jpg"); c.call("assetcraft_register", {"files": [f"{ws}/gradient_small.jpg"], "out_dir": f"{ws}/assets/reg2"})
ok, r = c.call("assetcraft_duplicates", {"out_dir": f"{ws}/assets/dup2"})
check("assetcraft: resized JPEG found as a near duplicate", ok and any(f"{ws}/gradient_small.jpg" in g for g in r["duplicates"]["near"]), r.get("duplicates", {}).get("near") if isinstance(r, dict) else r)
ok, r = c.call("assetcraft_search", {"department": "levelcraft", "out_dir": f"{ws}/assets/search"})
check("assetcraft: department outputs are discoverable with provenance", ok and r["results"] > 0)
Image.fromarray(g[::-1]).save(f"{ws}/gradient.png"); c.call("assetcraft_register", {"files": [f"{ws}/gradient.png"], "out_dir": f"{ws}/assets/reg3"})
ok, r = c.call("assetcraft_get", {"asset": f"{ws}/gradient.png", "out_dir": f"{ws}/assets/get"})
check("assetcraft: a changed file becomes version 2 with history", ok and r["asset"]["version"] == 2 and len(r["asset"]["history"]) == 2, r.get("asset", {}).get("history") if isinstance(r, dict) else r)
json.dump({"license": "CC-BY-NC-4.0", "attribution": "Someone"}, open(f"{ws}/gradient_copy.png.license.json", "w"))
os.remove(f"{ws}/gradient_copy.png"); shutil.copy(f"{ws}/gradient_small.jpg", f"{ws}/gradient_copy.png")
c.call("assetcraft_register", {"files": [f"{ws}/gradient_copy.png"], "out_dir": f"{ws}/assets/reg4"})
ok, r = c.call("assetcraft_license_report", {"out_dir": f"{ws}/assets/lic"})
check("assetcraft: non-commercial licence flagged and ATTRIBUTION.md written", isinstance(r, dict) and r.get("status") == "failed" and "CC-BY-NC-4.0" in r["licenses"]["restricted"]
      and os.path.exists(f"{ws}/assets/lic/ATTRIBUTION.md"), r)
os.makedirs(f"{ws}/project/assets", exist_ok=True); open(f"{ws}/project/assets/theme.wav", "w").write("different")
ok, r = c.call("assetcraft_integrate", {"assets": [theme], "dest": f"{ws}/project/assets", "out_dir": f"{ws}/assets/int"})
check("assetcraft: integrate refuses to overwrite a different file", isinstance(r, dict) and r.get("status") == "failed" and open(f"{ws}/project/assets/theme.wav").read() == "different", r)
run("assetcraft_catalog_page", {"out_dir": f"{ws}/assets/page"}, "assetcraft: HTML catalogue page", need=True)
c.close()

# ---- routing (no runtime needed)
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=env)
for brief, want in (("a seamless rain ambience", ("audiocraft", "ambience")), ("mossy cobblestone texture", ("materialcraft", "generate")), ("explosion sprite sheet for phaser", ("fxcraft", "flipbook")),
                    ("rig my character", ("animcraft", "autorig")), ("motion capture from a video of me dancing", ("animcraft", "mocap")), ("record gameplay video of my game", ("cinematiccraft", "capture")), ("check fps on mobile", ("testcraft", "perf")), ("golden hour orbit cutscene", ("cinematiccraft", "shot")),
                    ("a roguelike dungeon level", ("levelcraft", "generate")), ("find unused assets", ("assetcraft", "unused")), ("sunset skybox", ("worldcraft", "sky"))):
    ok, r = c.call("route", {"brief": brief}); ch = r.get("chosen") or {}
    check(f"route: {brief!r} → {want[0]}.{want[1]}", (ch.get("department"), ch.get("action")) == want, (ch.get("department"), ch.get("action")))
ok, r = c.call("route", {"brief": "a low-poly treasure chest 3d model"})
check("route: 3D modelling is sent to the 3D Department", r.get("three_d") and not r.get("chosen"), r.get("chosen"))
c.close()

# ---- ForgeCraft discovers and runs departments (needs MeshCraft's Blender to be registered at all)
if os.access(os.path.expanduser("~/.gitcraft/meshcraft/venv/bin/python"), os.X_OK):
    f = Client([os.path.join(REPO, "scripts", "mcp.sh"), "forgecraft"], env=env, log=os.path.join(ws, "forgecraft.log"))
    names = {t["name"] for t in f.tools()}
    check("forgecraft exposes departments / department_route / department_run", {"departments", "department_route", "department_run"} <= names)
    ok, r = f.call("departments"); check("forgecraft: departments lists all nine", ok and len(r["departments"]) == 9)
    ok, r = f.call("department_route", {"brief": "footstep sound effects"}); check("forgecraft: department_route picks audiocraft.sfx", ok and r["use"] == "studio" and r["studio"]["chosen"]["action"] == "sfx", r.get("next"))
    ok, r = f.call("department_route", {"brief": "a 3d model of a lighthouse"}); check("forgecraft: department_route keeps 3D models in the 3D pipeline", ok and r["use"] == "3d", r.get("next"))
    ok, r = f.call("department_run", {"department": "audiocraft", "action": "sfx", "params": {"preset": "footstep", "out_dir": f"{ws}/forge/sfx"}})
    check("forgecraft: department_run produces a verified artifact (inside ForgeCraft's sandbox)", ok and r["status"] == "ok" and all(o["ok"] for o in r["outputs"]), r if not ok else r.get("error"))
    f.close()
else:
    skip("forgecraft department tools", "MeshCraft's Blender is not installed, so ForgeCraft is not registered")

# ---- deferred start: studiocraft registered before its runtime exists (a cut-off or not-yet-run Studio install)
early = os.path.join(ws, "studio-home-early"); shutil.rmtree(early, ignore_errors=True); os.makedirs(early)
envd = dict(env, GITCRAFT_STUDIO_HOME=early)
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=envd, log=os.path.join(ws, "studiocraft-early.log"))
names = [t["name"] for t in c.tools()]
check("deferred: without its runtime studiocraft starts and lists only studio_status", names == ["studio_status"], names)
ok, r = c.call("studio_status"); check("deferred: studio_status says how to install", ok and "install.sh studiocraft" in r.get("how_to_install", ""), r)
real = os.path.join(os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.expanduser("~/.gitcraft/studio"), "venv")
subprocess.run(["cp", "-a", real, os.path.join(early, "venv.part")], check=True); os.rename(os.path.join(early, "venv.part"), os.path.join(early, "venv"))
note, end = None, time.time() + 30
while time.time() < end and note is None:
    try: m = c.q.get(timeout=2)
    except Exception: continue
    if m and m.get("method") == "notifications/tools/list_changed": note = m
check("deferred: announces tools/list_changed when the runtime lands", note is not None)
names = [t["name"] for t in c.tools()]
check("deferred: the same server now lists every department tool", "audiocraft_sfx" in names and len(names) >= 50, len(names))
ok, r = c.call("audiocraft_sfx", {"preset": "blip", "out_dir": f"{ws}/deferred/sfx"})
check("deferred: the same server runs a department action through the new runtime", ok and r.get("status") == "ok", r if not ok else r.get("error"))
c.close(); shutil.rmtree(early, ignore_errors=True)

n_ok = sum(ok for _, ok in results)
print(f"\n{n_ok}/{len(results)} checks passed (outputs in {ws})")
sys.exit(0 if n_ok == len(results) else 1)
