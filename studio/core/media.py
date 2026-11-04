"""Media helpers shared by departments: WAV I/O (with loop points), FFmpeg conversion, a
dependency-free glTF 2.0 binary (GLB) writer, image previews (waveforms, atlases, GIFs, contact
sheets). numpy + Pillow only; FFmpeg is called as an external program."""
import json, os, shutil, struct, subprocess, wave
import numpy as np

# ---------------------------------------------------------------- audio
def write_wav(path, x, sr=44100, loop=None, cue=None):
    """x: float array (n,) mono or (n, ch); written as 16-bit PCM. loop=(start, end) in samples
    adds a RIFF `smpl` chunk (read by game engines, samplers, FMOD/Wwise importers)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1: x = x[:, None]
    pcm = (np.clip(x, -1, 1) * 32767).round().astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(pcm.shape[1]); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())
    if loop:
        s, e = int(loop[0]), int(loop[1])
        smpl = struct.pack("<IIIIIIIII", 0, 0, int(1e9 / sr), 60, 0, 0, 0, 1, 0) + struct.pack("<IIIIII", 0, 0, s, e - 1, 0, 0)
        data = bytearray(open(path, "rb").read())
        data += b"smpl" + struct.pack("<I", len(smpl)) + smpl
        data[4:8] = struct.pack("<I", len(data) - 8)
        open(path, "wb").write(bytes(data))
    return path


def read_audio(path, sr=44100, mono=False):
    """Any audio FFmpeg can read → float array (n, ch), at `sr`."""
    if path.lower().endswith(".wav"):
        try:
            with wave.open(path) as w:
                if w.getsampwidth() == 2 and w.getframerate() == sr:
                    a = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, w.getnchannels()) / 32768.0
                    return a.mean(1, keepdims=True) if mono else a
        except wave.Error:
            pass
    ch = 1 if mono else 2
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", str(ch), "-ar", str(sr), "-"], capture_output=True, timeout=300)
    if r.returncode != 0: raise RuntimeError(f"ffmpeg could not read {path}: {r.stderr.decode()[-300:]}")
    return np.frombuffer(r.stdout, "<f4").reshape(-1, ch).astype(np.float64)


def encode(wav_path, fmt, out_path=None, loop=None, quality=None, sr=44100):
    """WAV → ogg (Vorbis) / mp3 (LAME) / opus / flac with FFmpeg. OGG gets LOOPSTART/LOOPLENGTH
    comments (the RPG Maker / Godot / many engines' convention)."""
    out_path = out_path or os.path.splitext(wav_path)[0] + "." + fmt
    codec = {"ogg": ["-c:a", "libvorbis", "-q:a", str(quality or 5)], "mp3": ["-c:a", "libmp3lame", "-q:a", str(quality or 2)],
             "opus": ["-c:a", "libopus", "-b:a", "96k"], "flac": ["-c:a", "flac"], "wav": ["-c:a", "pcm_s16le"]}[fmt]
    meta = []
    if loop and fmt in ("ogg", "opus", "flac"):
        meta = ["-metadata", f"LOOPSTART={int(loop[0])}", "-metadata", f"LOOPLENGTH={int(loop[1] - loop[0])}"]
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav_path, *codec, *meta, out_path], capture_output=True, text=True, timeout=300)
    if r.returncode != 0: raise RuntimeError(f"ffmpeg {fmt} encode failed: {r.stderr[-400:]}")
    return out_path


def loudness(path):
    """Integrated loudness (LUFS), true peak and LRA from FFmpeg's EBU R128 meter."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, timeout=300)
    t = r.stderr; j = t[t.rfind("{"):t.rfind("}") + 1]
    d = json.loads(j)
    return {"lufs": float(d["input_i"]), "true_peak_db": float(d["input_tp"]), "lra": float(d["input_lra"])}


def waveform_png(x, path, w=800, h=160, color=(46, 125, 178), bg=(245, 247, 250), loop=None, sr=44100):
    from PIL import Image, ImageDraw
    x = np.asarray(x); x = x.mean(1) if x.ndim == 2 else x
    im = Image.new("RGB", (w, h), bg); d = ImageDraw.Draw(im)
    n = len(x); cols = np.array_split(np.abs(x), w) if n >= w else [np.abs(x)] * w
    for i, c in enumerate(cols):
        a = float(c.max()) if len(c) else 0; y = int(a * (h / 2 - 4))
        d.line([(i, h // 2 - y), (i, h // 2 + y)], fill=color)
    d.line([(0, h // 2), (w, h // 2)], fill=(200, 205, 212))
    if loop:
        for s in loop: xx = int(s / max(n, 1) * w); d.line([(xx, 0), (xx, h)], fill=(220, 80, 60), width=2)
    im.save(path); return path


# ---------------------------------------------------------------- glTF 2.0 binary writer
def write_glb(path, meshes, animations=None, name="gitcraft"):
    """meshes: [{"name", "positions" (n,3), "indices" (m,3), "normals"?, "colors"? (n,3|4 linear 0..1),
    "uvs"?, "material"?: {"color": [r,g,b,a], "metallic", "roughness", "texture": png_path?, "double_sided"},
    "translation"?}]. Y-up metres. Returns the path. Validated by the Khronos validator in tests."""
    bin_ = bytearray(); views, accs, gmeshes, nodes, mats, images, textures, samplers = [], [], [], [], [], [], [], []

    def add(arr, target=None, comp=5126, typ="VEC3", minmax=False):
        arr = np.ascontiguousarray(arr)
        while len(bin_) % 4: bin_.append(0)
        off = len(bin_); bin_.extend(arr.tobytes())
        v = {"buffer": 0, "byteOffset": off, "byteLength": arr.nbytes}
        if target: v["target"] = target
        views.append(v)
        a = {"bufferView": len(views) - 1, "componentType": comp, "count": int(arr.shape[0]), "type": typ}
        if minmax: a["min"] = arr.min(0).tolist(); a["max"] = arr.max(0).tolist()
        accs.append(a); return len(accs) - 1

    for mi, m in enumerate(meshes):
        P = np.asarray(m["positions"], np.float32); I = np.asarray(m["indices"], np.uint32).reshape(-1)
        attrs = {"POSITION": add(P, 34962, minmax=True)}
        N = m.get("normals")
        if N is None: N = vertex_normals(P, I.reshape(-1, 3))
        attrs["NORMAL"] = add(np.asarray(N, np.float32), 34962)
        if m.get("colors") is not None:
            C = np.asarray(m["colors"], np.float32)
            attrs["COLOR_0"] = add(C, 34962, typ="VEC4" if C.shape[1] == 4 else "VEC3")
        if m.get("uvs") is not None: attrs["TEXCOORD_0"] = add(np.asarray(m["uvs"], np.float32), 34962, typ="VEC2")
        comp = 5125 if P.shape[0] > 65535 else 5123
        idx = add(I.astype(np.uint32 if comp == 5125 else np.uint16), 34963, comp=comp, typ="SCALAR")
        mat = m.get("material") or {}
        pbr = {"baseColorFactor": mat.get("color", [1, 1, 1, 1]), "metallicFactor": mat.get("metallic", 0.0), "roughnessFactor": mat.get("roughness", 0.9)}
        gm = {"name": m.get("name", f"mat{mi}"), "pbrMetallicRoughness": pbr}
        if mat.get("double_sided"): gm["doubleSided"] = True
        def tex(png):
            data = open(png, "rb").read()
            while len(bin_) % 4: bin_.append(0)
            off = len(bin_); bin_.extend(data); views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data)})
            images.append({"bufferView": len(views) - 1, "mimeType": "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"})
            if not samplers: samplers.append({"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497})
            textures.append({"sampler": 0, "source": len(images) - 1}); return {"index": len(textures) - 1}
        if mat.get("texture"): pbr["baseColorTexture"] = tex(mat["texture"])
        if mat.get("orm_texture"):
            t = tex(mat["orm_texture"]); pbr["metallicRoughnessTexture"] = t; gm["occlusionTexture"] = dict(t)
            pbr["metallicFactor"] = 1.0; pbr["roughnessFactor"] = 1.0
        if mat.get("normal_texture"): gm["normalTexture"] = tex(mat["normal_texture"])
        if mat.get("emissive_texture"): gm["emissiveTexture"] = tex(mat["emissive_texture"]); gm["emissiveFactor"] = [1.0, 1.0, 1.0]
        mats.append(gm)
        gmeshes.append({"name": m.get("name", f"mesh{mi}"), "primitives": [{"attributes": attrs, "indices": idx, "material": mi}]})
        node = {"name": m.get("name", f"mesh{mi}"), "mesh": mi}
        if m.get("translation") is not None: node["translation"] = [float(v) for v in m["translation"]]
        nodes.append(node)
    gl = {"asset": {"version": "2.0", "generator": "GITCRAFT Studio"}, "scene": 0,
          "scenes": [{"name": name, "nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": gmeshes, "materials": mats,
          "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": 0}]}
    if images: gl.update(images=images, textures=textures, samplers=samplers)
    while len(bin_) % 4: bin_.append(0)
    gl["buffers"][0]["byteLength"] = len(bin_)
    js = json.dumps(gl, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    open(path, "wb").write(out); return path


def vertex_normals(P, F):
    P = np.asarray(P, np.float64); F = np.asarray(F)
    n = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    N = np.zeros_like(P)
    for k in range(3): np.add.at(N, F[:, k], n)
    L = np.linalg.norm(N, axis=1, keepdims=True); L[L == 0] = 1
    return (N / L).astype(np.float32)


def grid_mesh(height, cell, colors=None, y_scale=1.0):
    """Heightfield (h, w) → positions/indices/uvs, centred on the origin, Y up."""
    h, w = height.shape
    xs = (np.arange(w) - (w - 1) / 2) * cell; zs = (np.arange(h) - (h - 1) / 2) * cell
    X, Z = np.meshgrid(xs, zs)
    P = np.stack([X, height * y_scale, Z], -1).reshape(-1, 3)
    i = np.arange(h * w).reshape(h, w)
    a, b, c, d = i[:-1, :-1].ravel(), i[:-1, 1:].ravel(), i[1:, :-1].ravel(), i[1:, 1:].ravel()
    F = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    U, V = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
    m = {"positions": P, "indices": F, "uvs": np.stack([U, V], -1).reshape(-1, 2)}
    if colors is not None: m["colors"] = colors.reshape(-1, colors.shape[-1])
    return m


def uv_sphere(radius=1.0, seg=64, rings=32):
    th = np.linspace(0, np.pi, rings + 1); ph = np.linspace(0, 2 * np.pi, seg + 1)
    T, P = np.meshgrid(th, ph, indexing="ij")
    N = np.stack([np.sin(T) * np.cos(P), np.cos(T), -np.sin(T) * np.sin(P)], -1).reshape(-1, 3)
    uv = np.stack([P / (2 * np.pi) * 2, T / np.pi], -1).reshape(-1, 2)   # texture repeats twice around
    i = np.arange((rings + 1) * (seg + 1)).reshape(rings + 1, seg + 1)
    a, b, c, d = i[:-1, :-1].ravel(), i[:-1, 1:].ravel(), i[1:, :-1].ravel(), i[1:, 1:].ravel()
    F = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    return {"positions": N * radius, "normals": N.astype(np.float32), "uvs": uv, "indices": F}


def srgb_to_linear(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


# ---------------------------------------------------------------- images
def to_image(a, mode=None):
    from PIL import Image
    a = np.asarray(a)
    if a.dtype != np.uint8: a = (np.clip(a, 0, 1) * 255).round().astype(np.uint8)
    return Image.fromarray(a, mode) if mode else Image.fromarray(a)


def save_png16(a, path):
    """Single-channel 0..1 → 16-bit greyscale PNG (heightmaps)."""
    from PIL import Image
    v = (np.clip(a, 0, 1) * 65535).round().astype(np.uint16)
    Image.fromarray(v).save(path); return path


def atlas(frames, cols=None, pad=0):
    """List of equal-size RGBA arrays/images → (atlas image, grid)."""
    from PIL import Image
    ims = [f if hasattr(f, "size") else to_image(f) for f in frames]
    w, h = ims[0].size; n = len(ims); cols = cols or int(np.ceil(np.sqrt(n))); rows = int(np.ceil(n / cols))
    A = Image.new("RGBA", (cols * (w + pad), rows * (h + pad)), (0, 0, 0, 0))
    rects = []
    for i, im in enumerate(ims):
        x, y = (i % cols) * (w + pad), (i // cols) * (h + pad); A.paste(im.convert("RGBA"), (x, y)); rects.append((x, y, w, h))
    return A, {"cols": cols, "rows": rows, "frame_width": w, "frame_height": h, "frames": n, "rects": rects}


def phaser_atlas_json(image_name, grid, prefix="frame"):
    """TexturePacker 'JSON Hash' — loaded by Phaser (load.atlas), PixiJS (Spritesheet) and others."""
    frames = {f"{prefix}_{i:03d}": {"frame": {"x": x, "y": y, "w": w, "h": h}, "rotated": False, "trimmed": False,
                                     "spriteSourceSize": {"x": 0, "y": 0, "w": w, "h": h}, "sourceSize": {"w": w, "h": h}}
              for i, (x, y, w, h) in enumerate(grid["rects"])}
    W = grid["cols"] * grid["frame_width"]; H = grid["rows"] * grid["frame_height"]
    return {"frames": frames, "meta": {"app": "GITCRAFT Studio", "version": "1.0", "image": image_name, "format": "RGBA8888",
                                        "size": {"w": W, "h": H}, "scale": "1"}}


def gif(frames, path, fps=12, bg=(30, 32, 38)):
    from PIL import Image
    out = []
    for f in frames:
        im = f if hasattr(f, "size") else to_image(f)
        if im.mode == "RGBA":
            b = Image.new("RGBA", im.size, bg + (255,)); b.alpha_composite(im); im = b
        out.append(im.convert("RGB").convert("P", palette=Image.ADAPTIVE))
    out[0].save(path, save_all=True, append_images=out[1:], duration=int(1000 / fps), loop=0, disposal=2); return path


def contact_sheet(paths_or_images, path, cols=4, cell=256, labels=None, bg=(24, 26, 31), title=None):
    from PIL import Image, ImageDraw
    ims = [Image.open(p) if isinstance(p, str) else p for p in paths_or_images]
    rows = int(np.ceil(len(ims) / cols)); top = 28 if title else 0; lab = 18 if labels else 0
    S = Image.new("RGB", (cols * cell, top + rows * (cell + lab)), bg); d = ImageDraw.Draw(S)
    if title: d.text((8, 8), title, fill=(235, 235, 235))
    for i, im in enumerate(ims):
        im = im.convert("RGBA"); im.thumbnail((cell, cell))
        x, y = (i % cols) * cell, top + (i // cols) * (cell + lab)
        tile = Image.new("RGBA", (cell, cell), (44, 47, 54, 255)); tile.alpha_composite(im, ((cell - im.width) // 2, (cell - im.height) // 2))
        S.paste(tile.convert("RGB"), (x, y))
        if labels: d.text((x + 4, y + cell + 3), str(labels[i])[:40], fill=(200, 200, 200))
    S.save(path); return path


def video_from_frames(pattern, out, fps=24, crf=20):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-i", pattern, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", str(crf), "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-movflags", "+faststart", out], capture_output=True, text=True, timeout=900)
    if r.returncode != 0: raise RuntimeError(f"ffmpeg encode failed: {r.stderr[-400:]}")
    return out


def have_ffmpeg(): return bool(shutil.which("ffmpeg"))
