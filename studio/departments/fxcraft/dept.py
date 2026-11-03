"""FXCraft: real-time game effects. Flipbook atlases come from small particle simulations (fx.py);
emitters are a portable preset (.fx.json) plus a dependency-free three.js runtime
(fxcraft-particles.js) that a game can copy; destruction is a Blender Voronoi fracture with a baked
rigid-body simulation exported as an animated GLB. Every effect is played in three.js r170."""
import json, os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import fx as FX
from core import media, runners, webpages, validate as V
from core.contract import StudioError

PRESETS = {   # emitter defaults per effect (metres, seconds) — tuned for a 1-unit-tall effect
    "fire": dict(rate=26, lifetime=[0.6, 1.0], speed=[0.6, 1.1], direction=[0, 1, 0], spread_deg=12, gravity=[0, 0.6, 0], size=[0.9, 0.4], alpha=[0.0, 1.0, 0.0], area=[0.25, 0.05, 0.25], blending="additive"),
    "smoke": dict(rate=10, lifetime=[2.2, 3.2], speed=[0.3, 0.55], direction=[0, 1, 0], spread_deg=14, gravity=[0.08, 0.1, 0], size=[0.8, 2.2], alpha=[0.0, 0.7, 0.0], drag=0.3, random_rotation=True, area=[0.2, 0.05, 0.2], blending="normal"),
    "magic": dict(rate=18, lifetime=[0.8, 1.4], speed=[0.2, 0.5], direction=[0, 1, 0], spread_deg=60, gravity=[0, 0.3, 0], size=[0.4, 0.15], alpha=[0, 1, 0], area=[0.6, 0.2, 0.6], blending="additive"),
    "energy": dict(rate=2, lifetime=[1.5, 1.5], speed=[0, 0], direction=[0, 1, 0], spread_deg=0, size=[1.6, 1.6], alpha=[0.6, 1, 0.6], blending="additive"),
    "rain": dict(rate=60, lifetime=[0.8, 0.8], speed=[6, 7], direction=[0, -1, 0], spread_deg=3, size=[0.5, 0.5], alpha=[0.8, 0.8, 0.6], area=[6, 0.1, 6], blending="normal"),
    "snow": dict(rate=30, lifetime=[4, 5], speed=[0.4, 0.7], direction=[0, -1, 0], spread_deg=20, size=[0.5, 0.5], alpha=[0.9, 0.9, 0.7], area=[6, 0.1, 6], blending="normal"),
    "explosion": dict(rate=0, burst=1, lifetime=[1.2, 1.2], speed=[0, 0], direction=[0, 1, 0], size=[2.5, 2.5], alpha=[1, 1, 1], blending="normal"),
    "sparks": dict(rate=0, burst=1, lifetime=[0.8, 0.8], speed=[0, 0], direction=[0, 1, 0], size=[1.6, 1.6], alpha=[1, 1, 1], blending="additive"),
    "dust": dict(rate=0, burst=1, lifetime=[1.0, 1.0], speed=[0, 0], direction=[0, 1, 0], size=[1.8, 1.8], alpha=[1, 1, 1], blending="normal"),
    "splash": dict(rate=0, burst=1, lifetime=[0.9, 0.9], speed=[0, 0], direction=[0, 1, 0], size=[1.6, 1.6], alpha=[1, 1, 1], blending="normal"),
    "lightning": dict(rate=0, burst=1, lifetime=[0.5, 0.5], speed=[0, 0], direction=[0, 1, 0], size=[3, 3], alpha=[1, 1, 1], blending="additive"),
    "debris": dict(rate=0, burst=1, lifetime=[1.0, 1.0], speed=[0, 0], direction=[0, 1, 0], size=[1.8, 1.8], alpha=[1, 1, 1], blending="normal"),
}


def _frame_diff(a, b): return float(np.abs(a - b).mean())


def flipbook(ctx, p, extra_checks=True):
    ctx.used("studio_fx", "numpy"); eff = p["effect"]; S, n = p["frame_size"], p["frames"]
    frames, loops = FX.simulate(eff, S, n, ctx.seed, p.get("color"), p["intensity"], extra=1 if FX.EFFECTS[eff] else 0)
    nextf = frames[n] if len(frames) > n else None; frames = frames[:n]
    ctx.stage("simulated", effect=eff, frames=len(frames))
    stem = p.get("name") or eff; outs = []
    A, grid = media.atlas([media.to_image(f, "RGBA") for f in frames], cols=p.get("columns"))
    ap = ctx.path(f"{stem}_flipbook.png"); A.save(ap); outs.append({"path": ap, "role": "flipbook", "format": "png"})
    meta = {"image": os.path.basename(ap), "frames": len(frames), "cols": grid["cols"], "rows": grid["rows"], "frame_width": S, "frame_height": S,
            "fps": p["fps"], "loop": loops, "blending": PRESETS[eff]["blending"], "alpha": "straight (not premultiplied)"}
    jp = ctx.path(f"{stem}_flipbook.json"); json.dump(meta, open(jp, "w"), indent=1); outs.append({"path": jp, "role": "flipbook_meta", "format": "json"})
    pa = ctx.path(f"{stem}_atlas.json"); json.dump(media.phaser_atlas_json(os.path.basename(ap), grid, eff), open(pa, "w"), indent=1)
    outs.append({"path": pa, "role": "atlas (TexturePacker hash: Phaser, PixiJS)", "format": "json"})
    outs.append({"path": media.gif([media.to_image(f, "RGBA") for f in frames], ctx.path(f"{stem}_preview.gif"), fps=p["fps"]), "role": "preview", "format": "gif"})
    # MP4 preview over a dark background
    tmp = ctx.path("_frames"); os.makedirs(tmp, exist_ok=True)
    from PIL import Image
    for i, f in enumerate(frames * (3 if loops else 1)):
        bg = Image.new("RGBA", (S, S), (24, 26, 32, 255)); bg.alpha_composite(media.to_image(f, "RGBA")); bg.convert("RGB").resize((S * 2, S * 2)).save(os.path.join(tmp, f"f{i:04d}.png"))
    mp4 = media.video_from_frames(os.path.join(tmp, "f%04d.png"), ctx.path(f"{stem}_preview.mp4"), fps=p["fps"]); shutil.rmtree(tmp); ctx.used("ffmpeg")
    outs.append({"path": mp4, "role": "preview", "format": "mp4"})
    alphas = [float(f[..., 3].max()) for f in frames]; diffs = [_frame_diff(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]
    checks = [{"name": "every frame has visible content" if loops else "effect is visible (peak frame alpha)", "ok": (min(alphas) > 0.05) if loops else max(alphas) > 0.3, "detail": [round(min(alphas), 3), round(max(alphas), 3)]},
              {"name": "frames animate (consecutive frames differ)", "ok": min(diffs) > 1e-4, "detail": round(min(diffs), 5)}]
    if loops and nextf is not None:
        err = _frame_diff(nextf, frames[0])
        checks.append({"name": "loops exactly (frame N equals frame 0)", "ok": err < 1e-6, "detail": err})
    elif not loops:
        checks.append({"name": "one-shot fades out (last frame ≤ 25% of peak alpha)", "ok": float(frames[-1][..., 3].mean()) <= 0.25 * max(float(f[..., 3].mean()) for f in frames) + 1e-6,
                       "detail": round(float(frames[-1][..., 3].mean()), 4)})
    return {"outputs": outs, "checks": checks, "flipbook": meta}


def emitter(ctx, p):
    fb = flipbook(ctx, p); eff = p["effect"]; stem = p.get("name") or eff
    pr = dict(PRESETS[eff]); pr.update(p.get("overrides") or {})
    blending = pr.pop("blending")
    preset = {"format": "gitcraft-fx/1", "effect": eff, "blending": blending, "max_particles": p["max_particles"],
              "flipbook": dict(fb["flipbook"], image=fb["flipbook"]["image"]), "emitter": pr,
              "runtime": "fxcraft-particles.js (three.js) — or read this JSON in any engine: emitter = spawn rules, flipbook = atlas animation"}
    pp = ctx.path(f"{stem}.fx.json"); json.dump(preset, open(pp, "w"), indent=1)
    rt = ctx.path("fxcraft-particles.js"); shutil.copy(os.path.join(HERE, "fxcraft-particles.js"), rt)
    outs = fb["outputs"] + [{"path": pp, "role": "emitter_preset", "format": "json"}, {"path": rt, "role": "runtime", "format": "text"}]
    # engine check: the runtime plays the preset in three.js r170; screenshot after 1.2 s of simulated time
    shot = ctx.path(f"{stem}_engine.png")
    html = f"""<!doctype html><html><head>{webpages.IMPORTMAP}</head><body style="margin:0;background:#1b1e24"><canvas id="c" width="640" height="480"></canvas>
<script type="module">
import * as THREE from 'three';
import {{ FXEmitter }} from {json.dumps(webpages.file_url(rt))};
const R = {{ ok: false }};
try {{
  const r = new THREE.WebGLRenderer({{ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true }}); r.setSize(640, 480, false); r.setClearColor(0x1b1e24);
  const scene = new THREE.Scene(); const cam = new THREE.PerspectiveCamera(45, 640 / 480, 0.05, 100); cam.position.set(0, 0.9, 3.6); cam.lookAt(0, 0.7, 0);
  const grid = new THREE.GridHelper(4, 8, 0x444a55, 0x30353d); scene.add(grid);
  const fx = await FXEmitter.load(THREE, {json.dumps(webpages.file_url(pp))}); scene.add(fx.object); fx.object.position.y = 0.3;
  let peak = 0; const steps = {p['check_seconds']} * 60; const shotAt = Math.round(steps * 0.35);
  for (let i = 0; i < steps; i++) {{ fx.update(1 / 60, cam); peak = Math.max(peak, fx.alive); if (i === shotAt) break; }}
  r.render(scene, cam);
  const gl = r.getContext(); const px = new Uint8Array(4 * 200 * 200); gl.readPixels(220, 140, 200, 200, gl.RGBA, gl.UNSIGNED_BYTE, px);
  let lit = 0; for (let i = 0; i < px.length; i += 4) if (Math.abs(px[i] - 0x1b) + Math.abs(px[i+1] - 0x1e) + Math.abs(px[i+2] - 0x24) > 30) lit++;
  Object.assign(R, {{ ok: true, alive: fx.alive, peak_alive: peak, lit_pixels: lit }});
}} catch (e) {{ R.error = String(e); }}
window.__report = R; window.__done = true;
</script></body></html>"""
    r = webpages.run(html, shot, (640, 480)); rep = r.get("report") or {}; ctx.used("three")
    outs.append({"path": shot, "role": "engine_screenshot", "format": "png"})
    checks = fb["checks"] + [{"name": "plays in three.js r170 with fxcraft-particles.js (particles alive, pixels drawn)", "ok": bool(rep.get("ok")) and rep.get("peak_alive", 0) > 0 and rep.get("lit_pixels", 0) > 50 and not r.get("errors"),
                              "detail": {k: rep.get(k) for k in ("alive", "peak_alive", "lit_pixels", "error")} | {"errors": (r.get("errors") or [])[:2]}}]
    return {"outputs": outs, "checks": checks, "preset": preset, "engine": rep}


def destruction(ctx, p):
    ctx.used("blender")
    src = ctx.need(p["input"]) if p.get("input") else None
    stem = p.get("name") or "destruction"
    r = runners.blender(os.path.join(HERE, "bpy_fracture.py"), {"input": src, "shape": p["shape"], "size": p["size"], "pieces": p["pieces"], "seed": ctx.seed,
                                                                   "force": p["force"], "frames": p["frames"], "fps": p["fps"], "color": p.get("color"),
                                                                   "glb": ctx.path(f"{stem}.glb"), "blend": ctx.path(f"{stem}.blend"), "preview": ctx.path(f"{stem}_contact.png")}, timeout=1200)
    ctx.stage("fractured + simulated", pieces=r.get("pieces"))
    glb = ctx.path(f"{stem}.glb"); outs = [{"path": glb, "role": "animated_mesh", "format": "glb"}, {"path": ctx.path(f"{stem}.blend"), "role": "source", "format": "blend"}]
    if os.path.exists(ctx.path(f"{stem}_contact.png")): outs.append({"path": ctx.path(f"{stem}_contact.png"), "role": "preview", "format": "png"})
    shot = ctx.path(f"{stem}_engine.png")
    checks, _, rep = webpages.glb_checks(glb, shot, "destruction GLB", play=p["frames"] / p["fps"] * 0.6)
    ctx.used("three", "gltf_validator"); outs.append({"path": shot, "role": "engine_screenshot", "format": "png"})
    info = V.check(glb)
    checks += [{"name": f"fractured into {p['pieces']} pieces (±30%)", "ok": abs((r.get("pieces") or 0) - p["pieces"]) <= max(2, p["pieces"] * 0.3), "detail": r.get("pieces")},
               {"name": "pieces fly apart (bounds grow in the simulation)", "ok": (r.get("spread_end", 0) > r.get("spread_start", 1) * 1.3), "detail": [r.get("spread_start"), r.get("spread_end")]},
               {"name": "animation exported", "ok": bool(info.get("animations")), "detail": info.get("animations")}]
    return {"outputs": outs, "checks": checks, "simulation": r}


ACTIONS = {"flipbook": flipbook, "emitter": emitter, "destruction": destruction}
