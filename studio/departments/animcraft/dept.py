"""AnimCraft: rigging and animation in Blender (MeshCraft's bpy, bpy_anim.py), verified in three.js.
Every animated GLB is played clip by clip in three.js r170 and must visibly move; rigs report how many
vertices ended up weighted and by which method."""
import json, os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
from core import media, runners, webpages, validate as V
from core.contract import StudioError

BPY = os.path.join(HERE, "bpy_anim.py")


def _clip_motion(ctx, glb, stem):
    """Render each clip at its start and middle in three.js; pixels must change (the clip moves the model)."""
    from PIL import Image
    info = V.check(glb); clips = info.get("animations") or []; checks, shots = [], []
    for i, clip in enumerate(clips):
        a, b = ctx.path(f"_check_{i}_a.png"), ctx.path(f"_check_{i}_b.png")
        js = lambda t: f"if (gltf.animations.length) {{ const mx = new THREE.AnimationMixer(gltf.scene); const ac = mx.clipAction(gltf.animations[{i}]); ac.play(); mx.update({t}); gltf.scene.updateMatrixWorld(true); }}"
        r0 = webpages.glb_view(glb, a, size=(400, 400), extra_js=js(0.0))
        dur = next((c[1] for c in (r0.get("report") or {}).get("clips", []) if c[0] == clip), 1.0)
        best = 0.0
        for frac in (0.13, 0.37, 0.5):   # off-grid times: symmetric objects look identical at 90°/180°
            webpages.glb_view(glb, b, size=(400, 400), extra_js=js(dur * frac))
            A = np.asarray(Image.open(a).convert("L"), float); B = np.asarray(Image.open(b).convert("L"), float)
            best = max(best, float((np.abs(A - B) > 6).mean()))
        checks.append({"name": f"clip '{clip}' plays in three.js r170 (model moves)", "ok": best > 0.002, "detail": {"changed_pixels": round(best, 4), "seconds": dur}})
        if i < 6: shots.append(b)
        os.remove(a)
    sheet = None
    if shots:
        sheet = ctx.path(f"{stem}_clips.png"); media.contact_sheet(shots, sheet, cols=min(6, len(shots)), cell=240, labels=clips[:6], bg=(206, 227, 234))
    for s in shots: os.remove(s)
    for f in os.listdir(ctx.out_dir):
        if f.startswith("_check_"): os.remove(os.path.join(ctx.out_dir, f))
    return checks, sheet, clips


def demo_character(ctx, p):
    ctx.used("blender"); stem = p.get("name") or f"demo_{p['kind']}"
    r = runners.blender(BPY, {"mode": "demo", "kind": p["kind"], "height": p["height"], "glb": ctx.path(f"{stem}.glb")})
    glb = ctx.path(f"{stem}.glb"); shot = ctx.path(f"{stem}_engine.png")
    checks, _, _ = webpages.glb_checks(glb, shot, "demo mesh"); ctx.used("three", "gltf_validator")
    return {"outputs": [{"path": glb, "role": "mesh", "format": "glb"}, {"path": shot, "role": "engine_screenshot", "format": "png"}], "checks": checks, "mesh": r}


def autorig(ctx, p):
    src = ctx.need(p["input"]); ctx.used("blender"); stem = p.get("name") or os.path.splitext(os.path.basename(src))[0] + "_rigged"
    r = runners.blender(BPY, {"mode": "autorig", "input": src, "rig": p["rig"], "naming": p["naming"], "segments": p["segments"],
                              "glb": ctx.path(f"{stem}.glb"), "blend": ctx.path(f"{stem}.blend")}, timeout=900)
    ctx.stage("rigged", bones=len(r["bones"]), weighting=r["weighting"])
    glb = ctx.path(f"{stem}.glb"); shot = ctx.path(f"{stem}_engine.png")
    checks, _, rep = webpages.glb_checks(glb, shot, "rigged GLB"); ctx.used("three", "gltf_validator")
    g, _ = V.glb_json(glb); skins = g.get("skins", [])
    checks += [{"name": "skinned (glTF skin with joints)", "ok": bool(skins) and len(skins[0]["joints"]) == len(r["bones"]), "detail": len(skins[0]["joints"]) if skins else 0},
               {"name": "every vertex is weighted to a bone", "ok": r["unweighted_vertices"] == 0, "detail": {"unweighted": r["unweighted_vertices"], "of": r["vertices"], "method": r["weighting"]}},
               {"name": "every bone influences the mesh", "ok": r["bones_with_weights"] >= len(r["bones"]) - (4 if p["rig"] == "humanoid" else 2), "detail": f"{r['bones_with_weights']}/{len(r['bones'])}"}]
    if r["weighting"] != "heat": ctx.note(f"weighting fell back: {r['weighting']}")
    return {"outputs": [{"path": glb, "role": "rigged_mesh", "format": "glb"}, {"path": ctx.path(f"{stem}.blend"), "role": "source", "format": "blend"},
                        {"path": shot, "role": "engine_screenshot", "format": "png"}], "checks": checks, "rig": r}


def animate(ctx, p):
    src = ctx.need(p["input"]); ctx.used("blender"); stem = p.get("name") or os.path.splitext(os.path.basename(src))[0] + "_animated"
    r = runners.blender(BPY, {"mode": "animate", "input": src, "clips": p["clips"], "frames": p["frames"], "fps": p["fps"],
                              "glb": ctx.path(f"{stem}.glb"), "blend": ctx.path(f"{stem}.blend")}, timeout=900)
    glb = ctx.path(f"{stem}.glb"); ctx.stage("animated", clips=r["clips"], rig=r["rig"])
    kh = webpages.khronos(glb); ctx.used("three", "gltf_validator")
    checks = [{"name": "Khronos glTF-Validator, 0 errors", "ok": kh.get("errors") == 0, "detail": kh.get("messages", [])[:3]}]
    mc, sheet, clips = _clip_motion(ctx, glb, stem); checks += mc
    checks.append({"name": "every requested clip exported", "ok": set(p["clips"]) <= set(clips), "detail": clips})
    outs = [{"path": glb, "role": "animated_mesh", "format": "glb"}, {"path": ctx.path(f"{stem}.blend"), "role": "source", "format": "blend"}]
    if sheet: outs.append({"path": sheet, "role": "preview", "format": "png"})
    return {"outputs": outs, "checks": checks, "animation": r}


def retarget(ctx, p):
    src, tgt = ctx.need(p["source"]), ctx.need(p["target"]); ctx.used("blender"); stem = p.get("name") or os.path.splitext(os.path.basename(tgt))[0] + "_retargeted"
    r = runners.blender(BPY, {"mode": "retarget", "source": src, "target": tgt, "clip": p.get("clip"), "map": p.get("bone_map"), "name": p.get("clip_name"),
                              "glb": ctx.path(f"{stem}.glb"), "blend": ctx.path(f"{stem}.blend")}, timeout=1200)
    glb = ctx.path(f"{stem}.glb"); ctx.stage("retargeted", bones=r["mapped_bones"], frames=r["frames"])
    kh = webpages.khronos(glb); ctx.used("three", "gltf_validator")
    checks = [{"name": "Khronos glTF-Validator, 0 errors", "ok": kh.get("errors") == 0, "detail": kh.get("messages", [])[:3]},
              {"name": "core bones mapped (≥ 10)", "ok": r["mapped_bones"] >= min(10, p["min_bones"]), "detail": r["mapped_bones"]}]
    mc, sheet, _ = _clip_motion(ctx, glb, stem); checks += mc
    outs = [{"path": glb, "role": "animated_mesh", "format": "glb"}, {"path": ctx.path(f"{stem}.blend"), "role": "source", "format": "blend"}]
    if sheet: outs.append({"path": sheet, "role": "preview", "format": "png"})
    return {"outputs": outs, "checks": checks, "retarget": r}


def physics(ctx, p):
    ctx.used("blender"); stem = p.get("name") or "physics_drop"
    inputs = [ctx.need(x) for x in p.get("inputs") or []]
    r = runners.blender(BPY, {"mode": "physics", "inputs": inputs, "count": p["count"], "shape": p["shape"], "spread": p["spread"], "bounce": p["bounce"],
                              "frames": p["frames"], "fps": p["fps"], "seed": ctx.seed, "glb": ctx.path(f"{stem}.glb"), "blend": ctx.path(f"{stem}.blend")}, timeout=900)
    glb = ctx.path(f"{stem}.glb"); shot = ctx.path(f"{stem}_engine.png")
    checks, _, _ = webpages.glb_checks(glb, shot, "physics GLB", play=p["frames"] / p["fps"]); ctx.used("three", "gltf_validator")
    settled = all(e < s - 0.3 for s, e in zip(r["start_heights"], r["end_heights"])) and all(e > -0.05 for e in r["end_heights"])
    checks.append({"name": "bodies fell and came to rest on the ground (not through it)", "ok": settled, "detail": {"start": r["start_heights"][:6], "end": r["end_heights"][:6]}})
    return {"outputs": [{"path": glb, "role": "animated_mesh", "format": "glb"}, {"path": ctx.path(f"{stem}.blend"), "role": "source", "format": "blend"},
                        {"path": shot, "role": "engine_screenshot", "format": "png"}], "checks": checks, "simulation": r}


def spritesheet(ctx, p):
    """3D clip → sprite sheets (orthographic, N directions), or a folder of PNG frames → one sheet."""
    from PIL import Image
    stem = p.get("name") or "sprites"; outs = []; checks = []
    if p.get("frames_dir"):
        d = ctx.need(p["frames_dir"]); files = sorted(f for f in os.listdir(d) if f.lower().endswith(".png"))
        if not files: raise StudioError("no PNG frames in frames_dir")
        seqs = {stem: [os.path.join(d, f) for f in files]}; ctx.used("studio_anim")
    else:
        src = ctx.need(p["input"]); ctx.used("blender")
        r = runners.blender(BPY, {"mode": "sprites", "input": src, "clips": p.get("clips"), "directions": p["directions"], "frames": p["frames"],
                                  "size": p["size"], "elevation": p["elevation"], "samples": p["samples"], "out_dir": ctx.out_dir}, timeout=1800)
        seqs = r["sequences"]
    for name, paths in seqs.items():
        ims = [Image.open(x).convert("RGBA") for x in paths]
        A, grid = media.atlas(ims, cols=p.get("columns") or len(ims) if len(ims) <= 16 else None)
        png = ctx.path(f"{stem}_{name}.png" if name != stem else f"{stem}.png"); A.save(png)
        js = os.path.splitext(png)[0] + ".json"; json.dump(media.phaser_atlas_json(os.path.basename(png), grid, name), open(js, "w"), indent=1)
        gif = media.gif(ims, os.path.splitext(png)[0] + ".gif", fps=p["fps"])
        outs += [{"path": png, "role": "spritesheet", "format": "png"}, {"path": js, "role": "atlas (TexturePacker hash: Phaser, PixiJS)", "format": "json"}, {"path": gif, "role": "preview", "format": "gif"}]
        arr = [np.asarray(i, float) for i in ims]
        diffs = [float(np.abs(arr[k] - arr[k + 1]).mean()) for k in range(len(arr) - 1)]
        checks += [{"name": f"{name}: no empty frames", "ok": all(a[..., 3].max() > 0 for a in arr), "detail": len(arr)},
                   {"name": f"{name}: frames animate", "ok": bool(diffs) and max(diffs) > 0.05, "detail": round(max(diffs), 3) if diffs else None}]
        if not p.get("frames_dir"):
            for x in paths: os.remove(x)
    return {"outputs": outs, "checks": checks, "sheets": list(seqs)}


def verify(ctx, p):
    src = ctx.need(p["input"]); stem = os.path.splitext(os.path.basename(src))[0]; ctx.used("three", "gltf_validator")
    kh = webpages.khronos(src); checks = [{"name": "Khronos glTF-Validator, 0 errors", "ok": kh.get("errors") == 0, "detail": kh.get("messages", [])[:3]}]
    mc, sheet, clips = _clip_motion(ctx, src, stem); checks += mc
    if not clips: checks.append({"name": "has animation clips", "ok": False})
    rp = ctx.path(f"{stem}_verify.json"); json.dump({"clips": clips, "checks": checks}, open(rp, "w"), indent=1)
    return {"outputs": [{"path": rp, "role": "report", "format": "json"}] + ([{"path": sheet, "role": "preview", "format": "png"}] if sheet else []), "checks": checks}


ACTIONS = {"demo_character": demo_character, "autorig": autorig, "animate": animate, "retarget": retarget, "physics": physics, "spritesheet": spritesheet, "verify": verify}
