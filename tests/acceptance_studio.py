#!/usr/bin/env python3
"""Build acceptance/studio: one curated, reproducible proof set per department, made by the final
code through the Studio CLI (fixed seeds), with an index (README.md + index.json) listing every
artifact, its checks and the tools/licences recorded for it. Large intermediates are not kept.

    tests/acceptance_studio.py [out_dir]      (default acceptance/studio; needs MeshCraft's Blender for the Blender rows)"""
import json, os, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "acceptance", "studio"))
WORK = os.path.join(os.environ.get("TMPDIR", "/tmp"), "gitcraft-studio-acceptance")
PY = os.path.join(os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.expanduser("~/.gitcraft/studio"), "venv", "bin", "python")
shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK); shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
env = dict(os.environ, GITCRAFT_ROOT=WORK, GITCRAFT_ROOTS=f"{WORK}:{OUT}:{REPO}", GITCRAFT_ASSET_CATALOG=os.path.join(WORK, "catalog.sqlite"))
GAME = os.path.join(REPO, "tests", "fixtures", "studio", "mini_game")
index = []


def run(dept, action, params, keep, title):
    """keep: list of output-path suffixes to copy into the package (plus the .studio.json record)."""
    out = os.path.join(WORK, dept, params.get("name") or action); params = dict(params, out_dir=out)
    t = time.time()
    r = subprocess.run([PY, os.path.join(REPO, "studio", "cli.py"), "run", dept, action, json.dumps(params)], capture_output=True, text=True, env=env, timeout=3600)
    try: rec = json.loads(r.stdout)
    except Exception: rec = {"status": "failed", "error": (r.stderr or r.stdout)[-500:]}
    dest = os.path.join(OUT, dept, params.get("name") or action); os.makedirs(dest, exist_ok=True)
    kept = []
    for o in rec.get("outputs", []):
        if any(o["path"].endswith(k) for k in keep):
            src = o["path"] if os.path.isabs(o["path"]) else os.path.join(out, o["path"])
            d = os.path.join(dest, os.path.basename(src)); shutil.copy(src, d); kept.append(os.path.relpath(d, OUT))
    if rec.get("record") and os.path.exists(rec["record"]):
        r2 = json.load(open(rec["record"])); r2["out_dir"] = os.path.relpath(dest, OUT); r2["request"]["out_dir"] = "(acceptance)"
        json.dump(r2, open(os.path.join(dest, os.path.basename(rec["record"])), "w"), indent=1)
    row = {"department": dept, "action": action, "title": title, "status": rec.get("status"), "seconds": round(time.time() - t, 1),
           "checks": [{"name": c["name"], "ok": c["ok"]} for c in rec.get("checks", [])], "files": kept,
           "tools": {k: v.get("license") for k, v in (rec.get("tools") or {}).items()}, "error": rec.get("error") or rec.get("reason")}
    index.append(row); print(f"{row['status']:8s} {dept}.{action}: {title} ({row['seconds']} s){'  ' + str(row['error'])[:200] if row['error'] else ''}", flush=True)
    return rec


A = "audiocraft"
run(A, "sfx", {"preset": "coin", "variations": 3, "name": "coin", "formats": ["ogg"]}, [".ogg", "_waveform.png"], "coin pickup ×3 variations")
for p in ("explosion", "laser", "jump", "footstep", "splash", "magic"):
    run(A, "sfx", {"preset": p, "name": p, "formats": ["ogg"]}, [".ogg", "_waveform.png"], f"{p} SFX")
run(A, "ambience", {"kind": "ocean", "seconds": 12, "name": "ocean_loop", "formats": ["ogg"]}, [".ogg", "_waveform.png"], "12 s seamless ocean loop (OGG LOOPSTART/LOOPLENGTH)")
run(A, "ambience", {"kind": "forest", "seconds": 12, "name": "forest_loop", "formats": ["ogg"]}, [".ogg"], "12 s seamless forest loop")
music = run(A, "music", {"mood": "adventure", "key": "D", "bars": 8, "name": "adventure_theme", "formats": ["ogg"]}, [".ogg", ".mid", ".layers.json", "_waveform.png"], "adventure theme: mix, MIDI, adaptive layers manifest")
run(A, "voice", {"name": "harbour_scene", "cast": {"captain": "bm_george", "parrot": "af_sky", "narrator": "af_heart"}, "formats": ["ogg"],
                 "lines": [{"id": "captain_01", "character": "captain", "text": "Hoist the sails, the tide waits for no one!"},
                           {"id": "parrot_01", "character": "parrot", "text": "Squawk! No one! No one!", "speed": 1.25},
                           {"id": "narrator_01", "character": "narrator", "text": "And so the little ship slipped out of the harbour before dawn."}]},
    [".ogg", ".dialogue.json"], "three voiced lines (Kokoro-82M, CPU)")
mix = os.path.join(WORK, A, "adventure_theme", "adventure_theme.wav")
if os.path.exists(mix):
    intro = os.path.join(WORK, "intro_theme.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", "1.3", "-i", "sine=f=220:sample_rate=44100", "-i", mix, "-i", mix, "-filter_complex",
                    "[0]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.3[a];[a][1][2]concat=n=3:v=0:a=1", "-t", "60", intro], check=True, timeout=120)
    run(A, "loop", {"input": intro, "min_seconds": 8, "name": "theme_with_intro", "formats": ["ogg"]}, [".loop.json", "_marked.ogg"], "loop point recovered from audio with a 1.3 s intro")
    run(A, "process", {"input": mix, "lufs": -16, "name": "theme_-16LUFS", "formats": ["ogg"]}, [".ogg"], "EBU R128 normalised to −16 LUFS")

W = "worldcraft"
for preset, climate in (("island", "tropical"), ("archipelago", "tropical"), ("mountains", "cold"), ("canyon", "arid")):
    run(W, "terrain", {"preset": preset, "climate": climate, "seed": 7, "name": preset}, ["_engine.png", "_preview.png", "_splat.png", "_height16.png", ".terrain.json"] + ([".glb", "_scatter.json", "_coastline.json"] if preset == "island" else []), f"{preset} terrain ({climate})")
run(W, "caves", {"seed": 3, "name": "cave"}, [".glb", "_engine.png", "_slices.png"], "cave system (closed surface-nets mesh)")
for s in ("sunset", "noon", "night"):
    run(W, "sky", {"preset": s, "width": 1024, "hdr": False, "name": f"sky_{s}"}, ["_equirect.png", "_cubemap_sheet.png", ".sky.json"], f"{s} sky (Blender Nishita) + cubemap")
run(W, "ocean", {"name": "ocean"}, ["_normal_flipbook.png", "_normals.gif", "_engine.png", ".ocean.json"], "FFT ocean (loops in time and space)")

M = "materialcraft"
for mat, extra in (("cobblestone", {"moss": 0.5, "dirt": 0.3}), ("rust", {"wear": 0.4}), ("planks", {"dirt": 0.2}), ("lava", {}), ("brick", {"style": "toon"}), ("ice", {})):
    run(M, "generate", dict({"material": mat, "resolution": 512, "name": mat}, **extra), ["_render.png", "_basecolor.png", "_normal.png", "_orm.png", "_tiled2x2.png", ".material.json"], f"{mat} PBR material")
run(M, "library", {"name": "swatches", "materials": ["stone", "cobblestone", "brick", "tiles", "wood", "planks", "bark", "metal", "brushed_metal", "rust", "fabric", "leather", "sand", "grass", "dirt", "ice", "lava", "water", "marble", "concrete", "snow"]},
    [".png"], "all 21 materials")

L = "levelcraft"
for kind, size in (("dungeon", (64, 48)), ("cave", (72, 48)), ("platformer", (160, 24)), ("overworld", (128, 96)), ("settlement", (64, 48))):
    run(L, "generate", {"kind": kind, "width": size[0], "height": size[1], "seed": 4, "name": kind}, [".tmj", "_tileset.png", "_preview.png", "_phaser.png", "_blockout.png", "_blockout.glb"], f"{kind} level (Tiled + Phaser check + blockout)")

F = "fxcraft"
for e in ("fire", "smoke", "magic", "energy", "explosion", "sparks", "dust", "splash", "lightning", "snow"):
    run(F, "flipbook", {"effect": e, "frames": 24, "name": e}, ["_flipbook.png", "_flipbook.json", "_preview.gif"], f"{e} flipbook")
run(F, "emitter", {"effect": "fire", "name": "torch"}, [".fx.json", "_engine.png", "fxcraft-particles.js", "_flipbook.png"], "torch emitter played in three.js")
run(F, "destruction", {"shape": "crate", "pieces": 14, "color": [150, 105, 60], "name": "crate_shatter"}, [".glb", "_contact.png", "_engine.png"], "crate Voronoi destruction with physics")

N = "animcraft"
run(N, "demo_character", {"name": "hero_mesh"}, [".glb"], "demo humanoid mesh")
hero = os.path.join(WORK, N, "hero_mesh", "hero_mesh.glb")
if os.path.exists(hero):
    run(N, "autorig", {"input": hero, "name": "hero_rig"}, [".glb", "_engine.png"], "auto-rig (heat weights)")
    run(N, "animate", {"input": os.path.join(WORK, N, "hero_rig", "hero_rig.glb"), "clips": ["idle", "walk", "run", "wave", "jump"], "name": "hero_anim"}, [".glb", "_clips.png"], "5 clips, each verified moving in three.js")
    run(N, "demo_character", {"height": 1.2, "name": "kid_mesh"}, [".glb"], "1.2 m demo humanoid")
    run(N, "autorig", {"input": os.path.join(WORK, N, "kid_mesh", "kid_mesh.glb"), "naming": "mixamo", "name": "kid_mixamo"}, [".glb"], "Mixamo-named rig")
    run(N, "retarget", {"source": os.path.join(WORK, N, "hero_anim", "hero_anim.glb"), "clip": "walk", "target": os.path.join(WORK, N, "kid_mixamo", "kid_mixamo.glb"), "name": "kid_walk"}, [".glb", "_clips.png"], "walk retargeted 1.8 m → 1.2 m across bone naming schemes")
    run(N, "spritesheet", {"input": os.path.join(WORK, N, "hero_anim", "hero_anim.glb"), "clips": ["walk"], "directions": 4, "frames": 8, "name": "hero"}, [".png", ".json", ".gif"], "4-direction walk sprite sheets")
run(N, "demo_character", {"kind": "quadruped", "name": "dog_mesh"}, [".glb"], "demo quadruped")
run(N, "autorig", {"input": os.path.join(WORK, N, "dog_mesh", "dog_mesh.glb"), "rig": "quadruped", "name": "dog_rig"}, [".glb"], "quadruped rig")
run(N, "animate", {"input": os.path.join(WORK, N, "dog_rig", "dog_rig.glb"), "clips": ["walk", "idle"], "name": "dog_anim"}, [".glb", "_clips.png"], "quadruped walk + idle")
run(N, "physics", {"count": 8, "name": "drop"}, [".glb", "_engine.png"], "rigid-body drop")

C = "cinematiccraft"
island = os.path.join(WORK, W, "island", "island.glb"); sky = os.path.join(WORK, W, "sky_sunset", "sky_sunset_equirect.png")
run(C, "title_card", {"text": "GITCRAFT STUDIO", "subtitle": "Free tools, wired in", "name": "title"}, [".mp4", ".png"], "animated title card")
if os.path.exists(island):
    run(C, "shot", {"scene": [{"path": island, "scale": 0.01}], "move": "orbit", "arc": 120, "lighting": "golden_hour", "duration": 3, "fps": 12, "distance": 1.6, "height": 0.6,
                    "sky": sky, "ground": False, "name": "island_orbit"}, [".mp4", ".camera.json", "_contact.png"], "golden-hour island orbit (Cycles) + camera path")
hero_anim = os.path.join(WORK, N, "hero_anim", "hero_anim.glb")
if os.path.exists(hero_anim):
    run(C, "storyboard", {"input": hero_anim, "title": "Hero intro", "lighting": "studio", "name": "storyboard",
                          "shots": [{"caption": "Wide: the hero waits", "move": "static", "distance": 4}, {"caption": "Push in", "move": "push_in", "lens": 70},
                                    {"caption": "Low angle, heroic", "move": "static", "height": 0.1, "start_angle": 40}]}, [".png", ".pdf"], "storyboard sheet")
clips = [{"path": os.path.join(WORK, C, "title", "title.mp4")}] + ([{"path": os.path.join(WORK, C, "island_orbit", "island_orbit.mp4")}] if os.path.exists(island) else []) + \
        [{"path": os.path.join(WORK, L, "overworld", "overworld_preview.png"), "seconds": 2}]
run(C, "assemble", {"clips": clips, "music": os.path.join(WORK, A, "adventure_theme", "adventure_theme.ogg"), "name": "teaser"}, [".mp4", "_poster.png"], "teaser: title → orbit → map, music bed")
run(C, "capture", {"target": GAME, "steps": [{"hold": "ArrowRight", "ms": 1500}, {"wait": 500}], "name": "gameplay"}, [".mp4"], "gameplay capture of the fixture game")

T = "testcraft"
run(T, "smoke", {"target": GAME, "name": "smoke"}, ["_report.html", "desktop_loaded.png", "phone_loaded.png", "tablet_loaded.png"], "smoke test on desktop, phone, tablet")
run(T, "play", {"target": GAME, "name": "play", "steps": [{"hold": "ArrowRight", "ms": 1500}, {"screenshot": "after_move"}, {"assert": "window.game.score >= 2", "name": "collects both coins"},
                                                           {"hold": "ArrowRight", "ms": 2500}, {"assert": "window.game.x < 420", "name": "the wall blocks the player (collision)"}]},
    ["_report.html", "desktop_after_move.png"], "scripted gameplay with state assertions")
run(T, "perf", {"target": GAME, "seconds": 3, "name": "perf"}, ["_report.html"], "FPS / frame-time profile")
run(T, "assets", {"folder": os.path.join(WORK, W), "name": "world_assets"}, ["_report.html"], "asset integrity of every WorldCraft output")

S = "assetcraft"
run(S, "scan", {"folder": WORK, "default_license": "Generated by GITCRAFT", "name": "scan"}, [".json"], "catalogue every acceptance output")
run(S, "license_report", {"name": "licenses"}, ["ATTRIBUTION.md", "licenses.json"], "licence inventory + ATTRIBUTION.md")
run(S, "catalog_page", {"name": "catalog", "limit": 400}, [".html"], "browsable HTML catalogue")

ok = sum(r["status"] == "ok" for r in index)
json.dump({"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commit": subprocess.run(["git", "-C", REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip(),
           "runs": index}, open(os.path.join(OUT, "index.json"), "w"), indent=1)
lines = ["# GITCRAFT Studio acceptance package", "", f"Made by `tests/acceptance_studio.py` with fixed seeds: **{ok}/{len(index)} runs ok**, "
         f"{sum(len(r['checks']) for r in index)} checks. Each folder holds selected outputs and the run's `.studio.json` record (tools, licences, hashes, checks).", ""]
for d in sorted({r["department"] for r in index}):
    lines += [f"## {d}", "", "| Run | Status | Checks | Files |", "|---|---|---|---|"]
    for r in (x for x in index if x["department"] == d):
        lines.append(f"| {r['title']} | {r['status']} | {sum(c['ok'] for c in r['checks'])}/{len(r['checks'])} | " + ", ".join(f"[{os.path.basename(f)}]({f})" for f in r["files"][:6]) + " |")
    lines.append("")
open(os.path.join(OUT, "README.md"), "w").write("\n".join(lines) + "\n")
print(f"\n{ok}/{len(index)} runs ok → {OUT}")
sys.exit(0 if ok == len(index) else 1)
