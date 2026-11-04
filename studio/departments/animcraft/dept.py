"""AnimCraft: rigging and animation in Blender (MeshCraft's bpy, bpy_anim.py), verified in three.js.
Every animated GLB is played clip by clip in three.js r170 and must visibly move; rigs report how many
vertices ended up weighted and by which method."""
import json, os, shutil, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from core import media, runners, webpages, validate as V
from core.contract import StudioError
from core import STUDIO_HOME

BPY = os.path.join(HERE, "bpy_anim.py")
MANIFEST = json.load(open(os.path.join(HERE, "manifest.json")))
VIDEO = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif", ".m4v")
IMAGE = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
# MediaPipe skeleton for the overlay (landmark index pairs)
EDGES = [(11, 12), (11, 13), (13, 15), (12, 14), (14, 16), (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 31), (24, 26), (26, 28), (28, 32), (0, 7), (0, 8)]


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


def _frames(ctx, src, fps, max_frames):
    """Video → PNG frames at fps (ffmpeg); a folder → its images in name order; an image → one frame."""
    if os.path.isdir(src):
        fs = sorted(os.path.join(src, f) for f in os.listdir(src) if f.lower().endswith(IMAGE))
        if not fs: raise StudioError(f"no images in {src}")
        return fs[:max_frames], fps
    ext = os.path.splitext(src)[1].lower()
    if ext in IMAGE: return [src], fps
    if ext not in VIDEO: raise StudioError(f"mocap input must be a video ({', '.join(VIDEO)}), an image or a folder of images, not {ext}")
    import subprocess
    d = ctx.path("_frames"); os.makedirs(d, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"fps={fps}", "-frames:v", str(max_frames), os.path.join(d, "f_%05d.png")],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0: raise StudioError(f"ffmpeg could not read {src}: {r.stderr[-400:]}")
    fs = sorted(os.path.join(d, f) for f in os.listdir(d))
    if not fs: raise StudioError(f"no frames decoded from {src}")
    return fs, fps


def _overlay(frames, det, picks, P, bvh_path, out, cell=240):
    """Top row: the detected landmarks drawn on the source frames. Bottom row: the written BVH (its own FK), front view."""
    from PIL import Image, ImageDraw
    import mocap_bvh as B
    pos, F, _ = B.fk(bvh_path); shots, labels = [], []
    for k in picks:
        im = Image.open(frames[k]).convert("RGB"); im.thumbnail((cell, cell)); dr = ImageDraw.Draw(im); w, h = im.size
        if det[k]:
            pts = [(x * w, y * h) for x, y in det[k]["image"]]
            for a, b in EDGES: dr.line([pts[a], pts[b]], fill=(255, 64, 160), width=3)
            for x, y in pts[11:29]: dr.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=(255, 230, 0))
        shots.append(im); labels.append(f"frame {k + 1}")
    allp = np.concatenate([v for v in pos.values()]); lo, hi = allp[:, :2].min(0), allp[:, :2].max(0); span = float((hi - lo).max()) * 1.15 or 1
    J, _, _, _ = B.read(bvh_path); names = [j["name"] or (J[j["parent"]]["name"] + "_end") for j in J]
    for k in picks:
        f = min(k, F - 1); im = Image.new("RGB", (cell, cell), (24, 26, 31)); dr = ImageDraw.Draw(im)
        xy = lambda q: (cell / 2 + (q[0] - (lo[0] + hi[0]) / 2) / span * cell, cell / 2 - (q[1] - (lo[1] + hi[1]) / 2) / span * cell)
        for ji, j in enumerate(J):
            if j["parent"] is None: continue
            c = (90, 200, 255) if "Left" in (names[ji] + names[j["parent"]]) else (255, 150, 60) if "Right" in (names[ji] + names[j["parent"]]) else (230, 230, 230)
            dr.line([xy(pos[names[j["parent"]]][f]), xy(pos[names[ji]][f])], fill=c, width=4)
        shots.append(im); labels.append(f"BVH frame {f + 1}")
    media.contact_sheet(shots, out, cols=len(picks), cell=cell, labels=labels, title="MediaPipe landmarks (top) and the written BVH, front view (bottom)")
    return out


def mocap(ctx, p):
    """Monocular motion capture: video/images → MediaPipe Pose world landmarks → smoothed humanoid BVH
    (checked by its own forward kinematics and by Blender's importer) → optional retarget onto a rig."""
    import mocap_bvh as B
    from core import deps
    src = ctx.need(p["input"]); stem = p.get("name") or os.path.splitext(os.path.basename(src.rstrip("/")))[0] + "_mocap"
    d = deps.check_one("mediapipe", MANIFEST["dependencies"]["mediapipe"]); ctx.used("mediapipe", "studio_mocap")
    frames, fps = _frames(ctx, src, p["fps"], p["max_frames"])
    if len(frames) > 1 or os.path.splitext(src)[1].lower() in VIDEO: ctx.used("ffmpeg")
    model = os.path.join(STUDIO_HOME, "models", "mediapipe", f"pose_landmarker_{p['model']}.task")
    if not os.path.isfile(model): raise StudioError(f"MediaPipe model missing: {model}", hint="scripts/install-studio.sh mocap")
    r = runners.venv(d["python"], os.path.join(HERE, "mp_pose.py"), {"model": model, "frames": frames, "fps": fps}, timeout=3600,
                     install="scripts/install-studio.sh mocap")
    det = r["frames"]; found = sum(f is not None for f in det); rate = found / len(det)
    ctx.stage("landmarks", frames=len(det), detected=found)
    if not found: raise StudioError("MediaPipe found no person in the input", hint="a full body in view, facing roughly towards the camera, works best")
    A = B.fill_and_smooth([np.array(f["world"]) if f else None for f in det], p["smoothing"] if len(det) > 1 else 1)
    P = B.to_bvh_axes(A[:, :, :3])
    out = ctx.path(f"{stem}.bvh"); single = len(det) == 1
    info = B.write(out, P, fps, hold=int(round(fps * p["hold_seconds"])) if single else None)
    lj = ctx.path(f"{stem}.landmarks.json")
    json.dump({"source": src, "fps": fps, "model": os.path.basename(model), "axes": "MediaPipe world: metres, hip-centred, x right, y down, z away from camera",
               "frames": [None if f is None else f["world"] for f in det]}, open(lj, "w"))
    # the written file, read back by our own BVH reader: limb bones must follow the landmark segments
    err = B.segment_errors(out, P) if not single else {k: v[-1:] for k, v in B.segment_errors(out, np.repeat(P, info["frames"], 0)).items()}
    worst = max(float(v.max()) for v in err.values()); mean = float(np.mean([v.mean() for v in err.values()]))
    vis = float(np.mean(A[:, 11:29, 3]))
    checks = [{"name": "a person is detected in ≥ 80 % of frames", "ok": rate >= 0.8, "detail": {"detected": found, "frames": len(det)}},
              {"name": "body landmarks are visible (mean visibility ≥ 0.5)", "ok": vis >= 0.5, "detail": round(vis, 3)},
              {"name": "BVH forward kinematics follow the landmarks (limb bones within 3°)", "ok": worst < 3.0, "detail": {"mean_deg": round(mean, 3), "max_deg": round(worst, 3)}}]
    # Blender's own BVH importer reads it, with the same bones moving the same way
    ctx.used("blender")
    names = {"LeftArm": "LeftForeArm", "LeftForeArm": "LeftHand", "RightArm": "RightForeArm", "RightForeArm": "RightHand",
             "LeftUpLeg": "LeftLeg", "LeftLeg": "LeftFoot", "RightUpLeg": "RightLeg", "RightLeg": "RightFoot"}
    bi = runners.blender(BPY, {"mode": "bvh_info", "input": out, "bones": list(names)}, timeout=600)
    pos, F, _ = B.fk(out); berr = []
    for j, c in names.items():
        if j not in bi["directions"]: continue
        u = np.array(bi["directions"][j]); u = B._n(np.stack([u[:, 0], u[:, 2], -u[:, 1]], 1))   # Blender Z-up, -Y forward → BVH axes
        v = B._n(pos[c] - pos[j])[:len(u)]; berr.append(float(np.degrees(np.arccos(np.clip(np.sum(u * v, -1), -1, 1))).max()))
    checks += [{"name": "Blender imports the BVH: humanoid bones recognised for retargeting", "ok": len(bi["canonical"]) >= 15 and bi["frames"] == info["frames"],
                "detail": {"bones": bi["bones"], "recognised": len(bi["canonical"]), "frames": bi["frames"]}},
               {"name": "Blender's pose matches the solver's (limb directions within 2°)", "ok": bool(berr) and max(berr) < 2.0, "detail": round(max(berr), 3) if berr else None}]
    picks = sorted({int(round(i)) for i in np.linspace(0, len(det) - 1, min(6, len(det)))})
    sheet = _overlay(frames, det, picks if not single else [0], P, out, ctx.path(f"{stem}_overlay.png"))
    if not single:   # motion: the take is not a still
        motion = float(np.degrees(max(np.arccos(np.clip(np.sum(B._n(P[:, b] - P[:, a])[:1] * B._n(P[:, b] - P[:, a]), -1), -1, 1)).max() for _, a, b in B.SEGMENTS)))
        checks.append({"name": "the take moves (some limb turns ≥ 5° over the clip)", "ok": motion >= 5.0, "detail": round(motion, 2)})
    if os.path.isdir(ctx.path("_frames")): shutil.rmtree(ctx.path("_frames"))
    outs = [{"path": out, "role": "animation", "format": "bvh"}, {"path": lj, "role": "landmarks", "format": "json"}, {"path": sheet, "role": "preview", "format": "png"}]
    res = {"bvh": info, "detected_frames": found, "frames": len(det), "model": p["model"]}
    if single: ctx.note(f"single image: the clip eases from the rest pose into the detected pose over {p['hold_seconds']} s")
    ctx.note("monocular capture: world landmarks are hip-centred, so the root does not travel; height follows the lowest foot")
    if p.get("target"):
        rt = retarget(ctx, {"source": out, "target": p["target"], "min_bones": 10, "clip_name": p.get("clip_name") or stem, "name": stem + "_on_" + os.path.splitext(os.path.basename(p["target"]))[0]})
        outs += rt["outputs"]; checks += [dict(c, name="retarget: " + c["name"]) for c in rt["checks"]]; res["retarget"] = rt["retarget"]
    return {"outputs": outs, "checks": checks, "mocap": res}


def autorig_ml(ctx, p):
    """UniRig (MIT): predicted skeleton (+ skin weights) for any mesh, merged onto the original and checked in three.js.
    Runs UniRig's own launch scripts in its venv, offline from the checkpoint the installer fetched."""
    import subprocess
    from core import deps
    src = ctx.need(p["input"]); stem = p.get("name") or os.path.splitext(os.path.basename(src))[0] + "_unirig"
    d = deps.check_one("unirig", MANIFEST["dependencies"]["unirig"]); ctx.used("unirig", "blender")
    root = os.path.join(STUDIO_HOME, "unirig"); venv_bin = os.path.dirname(d["python"])
    env = dict(os.environ, PATH=venv_bin + os.pathsep + os.environ.get("PATH", ""), VIRTUAL_ENV=os.path.dirname(venv_bin),
               HF_HOME=os.path.join(root, "hf-cache"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    def sh(script, *args):
        r = subprocess.run(["bash", os.path.join("launch", "inference", script), *args], cwd=root, env=env, capture_output=True, text=True, timeout=p["timeout"])
        if r.returncode != 0: raise StudioError(f"UniRig {script} failed (exit {r.returncode}): {(r.stderr or r.stdout)[-1200:]}")
    skel = ctx.path(f"{stem}_skeleton.fbx"); sh("generate_skeleton.sh", "--input", src, "--output", skel, "--seed", str(ctx.seed))
    ctx.stage("skeleton predicted")
    source = skel
    if p["skin"]:
        skin = ctx.path(f"_{stem}_skin.fbx"); sh("generate_skin.sh", "--input", skel, "--output", skin); source = skin; ctx.stage("skin predicted")
    glb = ctx.path(f"{stem}.glb"); sh("merge.sh", "--source", source, "--target", src, "--output", glb)
    if p["skin"] and os.path.exists(source): os.remove(source)
    shot = ctx.path(f"{stem}_engine.png"); checks, _, _ = webpages.glb_checks(glb, shot, "UniRig GLB"); ctx.used("three", "gltf_validator")
    g, _ = V.glb_json(glb); skins = g.get("skins", [])
    checks.append({"name": "skinned (glTF skin with joints)", "ok": bool(skins) and len(skins[0].get("joints", [])) >= 2, "detail": len(skins[0]["joints"]) if skins else 0})
    return {"outputs": [{"path": glb, "role": "rigged_mesh", "format": "glb"}, {"path": skel, "role": "skeleton", "format": "fbx"},
                        {"path": shot, "role": "engine_screenshot", "format": "png"}], "checks": checks}


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


ACTIONS = {"demo_character": demo_character, "autorig": autorig, "animate": animate, "retarget": retarget, "mocap": mocap, "autorig_ml": autorig_ml, "physics": physics, "spritesheet": spritesheet, "verify": verify}
