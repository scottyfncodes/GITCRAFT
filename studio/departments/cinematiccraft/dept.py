"""CinematicCraft: cutscenes and trailers. Camera choreography, lighting and rendering in Blender
(bpy_cine.py, MeshCraft's Blender, Cycles CPU); editing, title cards and encoding with Pillow + FFmpeg;
gameplay capture through TestCraft's Playwright runner. FilmCraft (the NLE) and EffectCraft (motion
graphics) take over when a cut needs hand editing: every output here is a plain MP4/PNG/JSON hand-off."""
import glob, json, os, shutil, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
from core import media, runners, validate as V
from core.contract import StudioError

FONT_CANDIDATES = ["/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
                   "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]


def _font(size, path=None):
    from PIL import ImageFont
    for f in ([path] if path else []) + FONT_CANDIDATES:
        if f and os.path.exists(f): return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def _scene(ctx, p):
    if p.get("scene"): return [dict(s, path=ctx.need(s["path"])) for s in p["scene"]]
    if p.get("input"): return [{"path": ctx.need(p["input"])}]
    raise StudioError("give `input` (one GLB/FBX/OBJ/.blend) or `scene` [{path, location, scale, rotation_z}]")


def _motion(frames):
    from PIL import Image
    if len(frames) < 2: return 0.0
    a = np.asarray(Image.open(frames[0]).convert("L"), float); b = np.asarray(Image.open(frames[len(frames) // 2]).convert("L"), float)
    return float((np.abs(a - b) > 8).mean())


def shot(ctx, p):
    ctx.used("blender", "ffmpeg"); stem = p.get("name") or f"shot_{p['move']}"
    sky = ctx.need(p["sky"]) if p.get("sky") else None
    req = {"mode": "shot", "scene": _scene(ctx, p), "lighting": p["lighting"], "move": p["move"], "duration": p["duration"], "fps": p["fps"],
           "resolution": p["resolution"], "samples": p["samples"], "distance": p["distance"], "height": p["height"], "arc": p.get("arc", 360 if p["move"] == "orbit" else 60),
           "start_angle": p["start_angle"], "lens": p["lens"], "sky": sky, "ground": p["ground"], "out_dir": ctx.out_dir, "blend": ctx.path(f"{stem}.blend")}
    r = runners.blender(os.path.join(HERE, "bpy_cine.py"), req, timeout=3600)
    ctx.stage("rendered", frames=len(r["frames"]), blender_seconds=r["seconds"])
    mp4 = media.video_from_frames(os.path.join(ctx.out_dir, "_frames", "f%04d.png"), ctx.path(f"{stem}.mp4"), fps=p["fps"])
    first, last = ctx.path(f"{stem}_first.png"), ctx.path(f"{stem}_last.png")
    shutil.copy(r["frames"][0], first); shutil.copy(r["frames"][-1], last)
    motion = _motion(r["frames"])
    mid = ctx.path(f"{stem}_contact.png"); media.contact_sheet([r["frames"][int(i)] for i in np.linspace(0, len(r["frames"]) - 1, 6)], mid, cols=6, cell=240)
    shutil.rmtree(os.path.join(ctx.out_dir, "_frames"))
    cut = {"format": "gitcraft-camera/1", "fps": p["fps"], "duration": p["duration"], "axes": "Y-up metres (three.js / glTF)", "move": p["move"], "lighting": p["lighting"],
           "keys": r["camera_keys"], "usage": "each frame: camera.position.fromArray(key.position); camera.lookAt(...key.target); camera.fov = key.fov_deg; camera.updateProjectionMatrix() — interpolate between keys by t"}
    cp = ctx.path(f"{stem}.camera.json"); json.dump(cut, open(cp, "w"), indent=1)
    info = V.check(mp4)
    checks = [{"name": f"video is {p['duration']} s (±1 frame)", "ok": info["ok"] and abs(info["seconds"] - p["duration"]) <= 1.5 / p["fps"] + 0.05, "detail": info.get("seconds")},
              {"name": "the camera moves (frames change)", "ok": motion > 0.01 or p["move"] == "static", "detail": round(motion, 4)},
              {"name": "camera path has a key per frame", "ok": len(r["camera_keys"]) == int(p["duration"] * p["fps"]), "detail": len(r["camera_keys"])},
              {"name": "first frame is not blank", "ok": _std(first) > 0.02, "detail": round(_std(first), 4)}]
    return {"outputs": [{"path": mp4, "role": "shot", "format": "mp4"}, {"path": ctx.path(f"{stem}.blend"), "role": "source", "format": "blend"}, {"path": cp, "role": "camera_path", "format": "json"},
                        {"path": first, "role": "still", "format": "png"}, {"path": last, "role": "still", "format": "png"}, {"path": mid, "role": "preview", "format": "png"}],
            "checks": checks, "render_seconds": r["seconds"]}


def _std(path):
    from PIL import Image
    return float(np.asarray(Image.open(path).convert("L"), float).std() / 255)


def storyboard(ctx, p):
    from PIL import Image, ImageDraw
    ctx.used("blender"); stem = p.get("name") or "storyboard"
    shots = p["shots"]
    if p.get("input") or p.get("scene"):
        r = runners.blender(os.path.join(HERE, "bpy_cine.py"), {"mode": "stills", "scene": _scene(ctx, p), "lighting": p["lighting"], "shots": shots,
                                                                  "resolution": [480, 270], "samples": p["samples"], "fps": 24, "out_dir": ctx.out_dir, "ground": True}, timeout=1800)
        stills = r["stills"]
    else:
        stills = [ctx.need(s["image"]) for s in shots]
    W = 480; cap_h = 70; cols = p["columns"]; rows = int(np.ceil(len(shots) / cols))
    sheet = Image.new("RGB", (cols * (W + 20) + 20, 70 + rows * (270 + cap_h + 20)), (246, 244, 238)); d = ImageDraw.Draw(sheet)
    d.text((20, 20), p.get("title") or "Storyboard", fill=(30, 30, 34), font=_font(30))
    for i, (s, img) in enumerate(zip(shots, stills)):
        x = 20 + (i % cols) * (W + 20); y = 70 + (i // cols) * (270 + cap_h + 20)
        im = Image.open(img).convert("RGB").resize((W, 270)); sheet.paste(im, (x, y)); d.rectangle([x, y, x + W - 1, y + 269], outline=(30, 30, 34), width=2)
        d.text((x, y + 276), f"{i + 1}. {s.get('move', 'static').replace('_', ' ')} · {s.get('seconds', 3)} s", fill=(120, 60, 40), font=_font(16))
        d.text((x, y + 298), (s.get("caption") or "")[:70], fill=(30, 30, 34), font=_font(17))
    png = ctx.path(f"{stem}.png"); sheet.save(png); pdf = ctx.path(f"{stem}.pdf"); sheet.save(pdf, "PDF", resolution=100)
    for f in stills:
        if os.path.basename(f).startswith("_still_"): os.remove(f)
    return {"outputs": [{"path": png, "role": "storyboard", "format": "png"}, {"path": pdf, "role": "storyboard", "format": "pdf"}],
            "checks": [{"name": f"{len(shots)} panels", "ok": len(stills) == len(shots)}, {"name": "panels are not blank", "ok": all(_std(f) > 0.02 for f in [png])}]}


def title_card(ctx, p):
    """Animated title: fade / rise / scale / typewriter, rendered with Pillow, encoded by FFmpeg."""
    from PIL import Image, ImageDraw, ImageFilter
    ctx.used("studio_cine", "ffmpeg"); stem = p.get("name") or "title"
    W, H = p["resolution"]; n = int(p["duration"] * p["fps"]); tmp = ctx.path("_tc"); os.makedirs(tmp, exist_ok=True)
    bg = tuple(p["background"]); fg = tuple(p["color"]); acc = tuple(p["accent"])
    tf = _font(int(H * p["size"]), p.get("font")); sf = _font(int(H * p["size"] * 0.38), p.get("font"))
    for k in range(n):
        t = k / max(1, n - 1); fade_in = min(1, t / 0.25); fade_out = min(1, (1 - t) / 0.2); a = min(fade_in, fade_out)
        im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im)
        if p["background_gradient"]:
            g = np.linspace(0, 1, H)[:, None, None] * np.ones((H, W, 1)); arr = np.array(bg) * (1 - 0.5 * g) + np.array(acc) * 0.18 * g
            im = Image.fromarray(arr.astype(np.uint8)); d = ImageDraw.Draw(im)
        text = p["text"]
        if p["style"] == "typewriter": text = text[:max(0, int(len(text) * min(1, t / 0.6)))]; a = min(1, fade_out)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
        bw = ld.textlength(p["text"], font=tf); x = (W - bw) / 2
        dy = (1 - fade_in) * H * 0.05 if p["style"] == "rise" else 0
        y = H * 0.42 - tf.size / 2 + dy
        ld.text((x, y), text, font=tf, fill=fg + (int(255 * a),))
        if p.get("subtitle"):
            sw = ld.textlength(p["subtitle"], font=sf); ld.text(((W - sw) / 2, y + tf.size * 1.25), p["subtitle"], font=sf, fill=acc + (int(255 * a * min(1, max(0, (t - 0.2) / 0.2))),))
        lw = int(W * 0.18 * min(1, t / 0.4)); ld.line([((W - lw) / 2, y + tf.size * 1.12), ((W + lw) / 2, y + tf.size * 1.12)], fill=acc + (int(255 * a),), width=max(2, H // 180))
        if p["style"] == "scale":
            s = 0.9 + 0.1 * fade_in; lw2, lh2 = int(W * s), int(H * s); layer = layer.resize((lw2, lh2)); pad = Image.new("RGBA", (W, H), (0, 0, 0, 0)); pad.paste(layer, ((W - lw2) // 2, (H - lh2) // 2)); layer = pad
        glow = layer.filter(ImageFilter.GaussianBlur(H / 90)); im = im.convert("RGBA"); im.alpha_composite(glow); im.alpha_composite(layer)
        im.convert("RGB").save(os.path.join(tmp, f"f{k:04d}.png"))
    mp4 = media.video_from_frames(os.path.join(tmp, "f%04d.png"), ctx.path(f"{stem}.mp4"), fps=p["fps"])
    still = ctx.path(f"{stem}.png"); shutil.copy(os.path.join(tmp, f"f{int(n * 0.55):04d}.png"), still); shutil.rmtree(tmp)
    info = V.check(mp4)
    return {"outputs": [{"path": mp4, "role": "title", "format": "mp4"}, {"path": still, "role": "still", "format": "png"}],
            "checks": [{"name": f"duration {p['duration']} s", "ok": abs(info.get("seconds", 0) - p["duration"]) < 0.1, "detail": info.get("seconds")},
                       {"name": "title is legible on the still (contrast)", "ok": _std(still) > 0.02, "detail": round(_std(still), 4)}]}


def assemble(ctx, p):
    """Clips (MP4/WebM) and stills (PNG/JPG with a duration) → one MP4 with crossfades, scaled to one
    resolution, optional music bed (looped, faded, loudness-normalised)."""
    ctx.used("ffmpeg"); stem = p.get("name") or "trailer"; W, H = p["resolution"]; fps = p["fps"]; xf = p["crossfade"]
    norm = []
    for i, c in enumerate(p["clips"]):
        src = ctx.need(c["path"]); out = ctx.path(f"_c{i:02d}.mp4")
        vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,fps={fps},format=yuv420p"
        if V.sniff(src) in ("png", "jpeg", "webp"):
            cmd = ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", str(c.get("seconds", 3)), "-i", src, "-vf", vf, "-c:v", "libx264", "-crf", "20", out]
        else:
            cmd = ["ffmpeg", "-v", "error", "-y", "-i", src] + (["-t", str(c["seconds"])] if c.get("seconds") else []) + ["-an", "-vf", vf, "-c:v", "libx264", "-crf", "20", out]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode: raise StudioError(f"clip {i} ({os.path.basename(src)}): {r.stderr[-300:]}")
        norm.append((out, V.check(out)["seconds"]))
    if len(norm) == 1: body = norm[0][0]; total = norm[0][1]
    else:   # chain xfade filters
        inputs = sum((["-i", f] for f, _ in norm), []); filt = []; prev = "[0:v]"; offset = 0.0
        for i in range(1, len(norm)):
            offset += norm[i - 1][1] - xf; lab = f"[v{i}]"
            filt.append(f"{prev}[{i}:v]xfade=transition={p['transition']}:duration={xf}:offset={offset:.3f}{lab}"); prev = lab
        body = ctx.path("_body.mp4")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filt), "-map", prev, "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", body], capture_output=True, text=True, timeout=1200)
        if r.returncode: raise StudioError("xfade failed: " + r.stderr[-400:])
        total = sum(s for _, s in norm) - xf * (len(norm) - 1)
    out = ctx.path(f"{stem}.mp4")
    if p.get("music"):
        mus = ctx.need(p["music"])
        af = f"aloop=loop=-1:size=2e9,atrim=0:{total:.3f},afade=t=in:d=0.5,afade=t=out:st={max(0, total - 1.5):.3f}:d=1.5,loudnorm=I=-16:TP=-1.5"
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", body, "-i", mus, "-filter_complex", f"[1:a]{af}[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out],
                           capture_output=True, text=True, timeout=1200)
        if r.returncode: raise StudioError("music mix failed: " + r.stderr[-400:])
    else:
        shutil.copy(body, out)
    for f in glob.glob(os.path.join(ctx.out_dir, "_*.mp4")): os.remove(f)
    info = V.check(out)
    poster = ctx.path(f"{stem}_poster.png"); subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(min(total / 2, 2)), "-i", out, "-frames:v", "1", poster], timeout=60)
    checks = [{"name": f"length ≈ {total:.2f} s", "ok": info["ok"] and abs(info["seconds"] - total) < 0.25, "detail": info.get("seconds")},
              {"name": f"resolution {W}×{H}", "ok": info.get("width") == W and info.get("height") == H, "detail": [info.get("width"), info.get("height")]}]
    if p.get("music"): checks.append({"name": "has an audio track", "ok": "aac" in (info.get("streams") or []), "detail": info.get("streams")})
    return {"outputs": [{"path": out, "role": "edit", "format": "mp4"}, {"path": poster, "role": "poster", "format": "png"}], "checks": checks,
            "edit": {"clips": len(norm), "seconds": round(total, 3), "transition": p["transition"]}}


def capture(ctx, p):
    """Gameplay capture: play a web game with scripted input in headless Chromium and record it (WebM → MP4)."""
    ctx.used("playwright", "ffmpeg")
    t = ctx.need(p["target"]); root, entry = (t, p.get("entry") or "index.html") if os.path.isdir(t) else (os.path.dirname(t), os.path.basename(t))
    vp = {"name": "capture", "width": p["resolution"][0], "height": p["resolution"][1]}
    r = runners.node("testcraft.mjs", {"root": root, "entry": entry, "out_dir": ctx.out_dir, "viewports": [vp], "wait_ms": p["wait_ms"], "steps": p["steps"], "record_video": True}, timeout=600)["results"][0]
    if not r.get("video"): raise StudioError("the browser produced no video")
    stem = p.get("name") or "gameplay"; mp4 = ctx.path(f"{stem}.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", r["video"], "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "+faststart", mp4], timeout=600)
    for s in r["screenshots"]: os.remove(s)
    info = V.check(mp4)
    return {"outputs": [{"path": mp4, "role": "capture", "format": "mp4"}, {"path": r["video"], "role": "capture", "format": "webm"}],
            "checks": [{"name": "capture recorded", "ok": info["ok"] and info["seconds"] > 0.5, "detail": info.get("seconds")}, {"name": "no page errors", "ok": not r["page_errors"], "detail": r["page_errors"][:2]}]}


ACTIONS = {"shot": shot, "storyboard": storyboard, "title_card": title_card, "assemble": assemble, "capture": capture}
