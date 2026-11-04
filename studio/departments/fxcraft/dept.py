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


QUARKS_IMPORTMAP = ('<script type="importmap">{"imports":{"three":"http://gc.local/three/build/three.module.js",'
                    '"three.quarks":"http://gc.local/nm/three.quarks/dist/three.quarks.esm.js","quarks.core":"http://gc.local/nm/quarks.core/dist/quarks.core.esm.js"}}</script>')


def quarks(ctx, p):
    """The effect as a three.quarks (MIT) particle system: built with three.quarks' own API from the emitter
    preset in headless Chromium, serialised by `emitter.toJSON()` (the format QuarksLoader and the three.quarks
    editor read), then reloaded with QuarksLoader and simulated to prove the file plays."""
    fb = flipbook(ctx, p); eff = p["effect"]; stem = p.get("name") or eff
    pr = dict(PRESETS[eff]); pr.update(p.get("overrides") or {})
    meta = fb["flipbook"]; atlas = ctx.path(meta["image"])
    cfg = {"preset": pr, "cols": meta["cols"], "rows": meta["rows"], "frames": meta["frames"], "loop": meta["loop"], "texture": webpages.file_url(atlas),
           "max": p["max_particles"], "seconds": p["check_seconds"]}
    html = f"""<!doctype html><html><head>{QUARKS_IMPORTMAP}</head><body style="margin:0;background:#1b1e24"><canvas id="c" width="640" height="480"></canvas>
<script type="module">
import * as THREE from 'three';
import {{ BatchedRenderer, ParticleSystem, QuarksLoader, QuarksUtil, RenderMode, ConstantValue, IntervalValue, ConeEmitter, PointEmitter, ConstantColor,
         ColorOverLife, Gradient, SizeOverLife, PiecewiseBezier, Bezier, FrameOverLife, ApplyForce, Vector3 as QV3, Vector4 }} from 'three.quarks';
const C = {json.dumps(cfg)}; const P = C.preset; const R = {{ ok: false }};
try {{
  const renderer = new THREE.WebGLRenderer({{ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true }}); renderer.setSize(640, 480, false); renderer.setClearColor(0x1b1e24);
  const scene = new THREE.Scene(); const cam = new THREE.PerspectiveCamera(45, 640 / 480, 0.05, 100); cam.position.set(0, 0.9, 3.6); cam.lookAt(0, 0.7, 0);
  const tex = await new THREE.TextureLoader().loadAsync(C.texture); tex.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.MeshBasicMaterial({{ map: tex, transparent: true, depthWrite: false, blending: P.blending === 'additive' ? THREE.AdditiveBlending : THREE.NormalBlending }});
  const lerp = (a) => Array.isArray(a) ? (a[0] === a[1] ? new ConstantValue(a[0]) : new IntervalValue(a[0], a[1])) : new ConstantValue(a);
  const al = P.alpha || [1, 1, 0], sz = P.size || [1, 1];
  const behaviors = [
    new ColorOverLife(new Gradient([[new QV3(1, 1, 1), 0], [new QV3(1, 1, 1), 1]], [[al[0], 0], [al[1], 0.5], [al[2], 1]])),
    new SizeOverLife(new PiecewiseBezier([[new Bezier(1, 1 + (sz[1] / sz[0] - 1) / 3, 1 + 2 * (sz[1] / sz[0] - 1) / 3, sz[1] / sz[0]), 0]])),
    new FrameOverLife(new PiecewiseBezier([[new Bezier(0, (C.frames - 1) / 3, 2 * (C.frames - 1) / 3, C.frames - 1), 0]])),
  ];
  const g = P.gravity || [0, 0, 0], gm = Math.hypot(...g);
  if (gm > 0) behaviors.push(new ApplyForce(new QV3(g[0] / gm, g[1] / gm, g[2] / gm), new ConstantValue(gm)));
  const area = P.area || [0, 0, 0], spread = (P.spread_deg || 0) * Math.PI / 180;
  const system = new ParticleSystem({{
    duration: Math.max(1, (P.lifetime || [1, 1])[1]), looping: !!(P.rate), prewarm: false, worldSpace: true,
    shape: (area[0] > 0 || spread > 0) ? new ConeEmitter({{ radius: Math.max(0.001, area[0] / 2), angle: Math.max(0.001, spread), thickness: 1 }}) : new PointEmitter(),
    startLife: lerp(P.lifetime || 1), startSpeed: lerp(P.speed || 0), startSize: new ConstantValue(sz[0]), startColor: new ConstantColor(new Vector4(1, 1, 1, 1)),
    emissionOverTime: new ConstantValue(P.rate || 0),
    emissionBursts: P.burst ? [{{ time: 0, count: new ConstantValue(Math.max(1, P.burst)), cycle: 1, interval: 0.01, probability: 1 }}] : [],
    material, renderMode: RenderMode.BillBoard, uTileCount: C.cols, vTileCount: C.rows, startTileIndex: new ConstantValue(0), behaviors,
  }});
  // three.quarks' cone emits along local +Z: turn it to the preset's direction
  const d = new THREE.Vector3(...(P.direction || [0, 1, 0])).normalize();
  system.emitter.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), d); system.emitter.position.y = 0.3;
  system.emitter.name = 'gitcraft-' + {json.dumps(eff)};
  // serialise from a parent Group: as the root object, three.js would extract materials/textures before the
  // emitter adds its own (they would be lost); this is also how the three.quarks editor exports
  const root = new THREE.Group(); root.name = 'gitcraft-fx'; root.add(system.emitter);
  const json = root.toJSON();
  // reload exactly what a game would load, and play it
  const batch = new BatchedRenderer(); scene.add(batch);
  const loaded = await new Promise((res, rej) => new QuarksLoader().parse(json, res, rej));
  QuarksUtil.addToBatchRenderer(loaded, batch); scene.add(loaded);
  let systems = 0; loaded.traverse((o) => {{ if (o.system) systems++; }});
  let peak = 0; const steps = Math.round(C.seconds * 60 * 0.35); let found = null;
  loaded.traverse((o) => {{ if (o.system) found = o.system; }});
  for (let i = 0; i < steps; i++) {{ batch.update(1 / 60); peak = Math.max(peak, found ? found.particleNum : 0); }}
  renderer.render(scene, cam);
  const gl = renderer.getContext(); const px = new Uint8Array(4 * 200 * 200); gl.readPixels(220, 140, 200, 200, gl.RGBA, gl.UNSIGNED_BYTE, px);
  let lit = 0; for (let i = 0; i < px.length; i += 4) if (Math.abs(px[i] - 0x1b) + Math.abs(px[i+1] - 0x1e) + Math.abs(px[i+2] - 0x24) > 30) lit++;
  const ps = json.object.children && json.object.children[0] && json.object.children[0].ps;
  Object.assign(R, {{ ok: true, json, systems, peak_particles: peak, lit_pixels: lit, version: ps && ps.version, materials: (json.materials || []).length, textures: (json.textures || []).length }});
}} catch (e) {{ R.error = String(e && e.stack || e); }}
window.__report = R; window.__done = true;
</script></body></html>"""
    shot = ctx.path(f"{stem}_quarks.png"); r = webpages.run(html, shot, (640, 480)); rep = r.get("report") or {}
    ctx.used("three", "three_quarks")
    outs = fb["outputs"] + [{"path": shot, "role": "engine_screenshot", "format": "png"}]
    checks = list(fb["checks"])
    if rep.get("json"):
        qp = ctx.path(f"{stem}.quarks.json"); json.dump(rep["json"], open(qp, "w"))
        outs.append({"path": qp, "role": "three.quarks emitter (QuarksLoader JSON, texture embedded)", "format": "json"})
    checks.append({"name": "three.quarks: emitter.toJSON() reloads with QuarksLoader and emits particles that render",
                   "ok": bool(rep.get("ok")) and rep.get("systems", 0) >= 1 and rep.get("peak_particles", 0) > 0 and rep.get("lit_pixels", 0) > 50 and not r.get("errors"),
                   "detail": {k: rep.get(k) for k in ("systems", "peak_particles", "lit_pixels", "version", "materials", "textures", "error")} | {"errors": (r.get("errors") or [])[:2]}})
    usage = {"load": "new QuarksLoader().parse(json, (obj) => { QuarksUtil.addToBatchRenderer(obj, batchRenderer); scene.add(obj); })",
             "update": "batchRenderer.update(delta) every frame", "library": "three.quarks 0.16 (MIT), three >= 0.165"}
    up = ctx.path(f"{stem}.quarks.usage.json"); json.dump(usage, open(up, "w"), indent=1); outs.append({"path": up, "role": "usage", "format": "json"})
    return {"outputs": outs, "checks": checks, "quarks": {k: rep.get(k) for k in ("systems", "peak_particles", "version")}}


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


ACTIONS = {"flipbook": flipbook, "emitter": emitter, "quarks": quarks, "destruction": destruction}
