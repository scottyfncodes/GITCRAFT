"""Format validation for department outputs (and AssetCraft scans). Each check opens the file
the way a consumer would and returns {"ok", "format", ...details} or {"ok": False, "error"}."""
import json, os, shutil, struct, subprocess, wave, xml.etree.ElementTree as ET

EXT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp", ".gif": "gif", ".wav": "wav", ".ogg": "ogg", ".mp3": "mp3",
       ".flac": "flac", ".opus": "ogg", ".mp4": "mp4", ".webm": "webm", ".glb": "glb", ".gltf": "gltf", ".json": "json", ".tmj": "tiled",
       ".tsj": "json", ".svg": "svg", ".pdf": "pdf", ".blend": "blend", ".mid": "midi", ".midi": "midi", ".html": "html", ".fbx": "fbx",
       ".obj": "obj", ".bvh": "bvh", ".csv": "csv", ".txt": "text", ".md": "text", ".js": "text", ".mjs": "text", ".exr": "exr", ".hdr": "hdr"}


def sniff(path):
    return EXT.get(os.path.splitext(path)[1].lower(), "binary")


def check(path, expect=None):
    if not os.path.isfile(path): return {"ok": False, "format": expect, "error": "file missing"}
    if os.path.getsize(path) == 0: return {"ok": False, "format": expect, "error": "empty file"}
    fmt = expect or sniff(path)
    try:
        fn = CHECKS.get(fmt)
        info = fn(path) if fn else {}
        return dict(ok=True, format=fmt, **info)
    except Exception as e:
        return {"ok": False, "format": fmt, "error": f"{type(e).__name__}: {e}"}


def _image(path):
    from PIL import Image
    with Image.open(path) as im: im.verify()
    with Image.open(path) as im:
        im.load(); info = {"width": im.width, "height": im.height, "mode": im.mode}
        if getattr(im, "n_frames", 1) > 1: info["frames"] = im.n_frames
        return info


def _wav(path):
    with wave.open(path) as w:
        n, sr = w.getnframes(), w.getframerate()
        if n == 0: raise ValueError("no audio frames")
        info = {"seconds": round(n / sr, 4), "sample_rate": sr, "channels": w.getnchannels(), "bits": w.getsampwidth() * 8}
    loops = read_smpl_loops(path)
    if loops: info["loop"] = loops[0]
    return info


def read_smpl_loops(path):
    data = open(path, "rb").read(); i = 12; loops = []
    while i + 8 <= len(data):
        cid, size = data[i:i + 4], struct.unpack("<I", data[i + 4:i + 8])[0]
        if cid == b"smpl" and size >= 36:
            n = struct.unpack("<I", data[i + 8 + 28:i + 8 + 32])[0]
            for k in range(n):
                o = i + 8 + 36 + 24 * k
                _, _, s, e, _, _ = struct.unpack("<IIIIII", data[o:o + 24]); loops.append({"start": s, "end": e})
        i += 8 + size + (size & 1)
    return loops


def _ffprobe(path):
    if not shutil.which("ffprobe"): return {"note": "ffprobe unavailable; header not checked"}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,format_name:stream=codec_type,codec_name,width,height,sample_rate,channels",
                        "-of", "json", path], capture_output=True, text=True, timeout=60)
    if r.returncode != 0: raise ValueError(r.stderr.strip()[:300] or "ffprobe failed")
    d = json.loads(r.stdout); st = d.get("streams", [])
    if not st: raise ValueError("no streams")
    dur = float(d.get("format", {}).get("duration") or 0)
    if dur <= 0: raise ValueError("zero duration")
    info = {"seconds": round(dur, 3), "container": d["format"].get("format_name"), "streams": [s.get("codec_name") for s in st]}
    v = next((s for s in st if s.get("codec_type") == "video"), None)
    if v: info.update(width=v.get("width"), height=v.get("height"))
    a = next((s for s in st if s.get("codec_type") == "audio"), None)
    if a: info.update(sample_rate=int(a.get("sample_rate") or 0), channels=a.get("channels"))
    return info


def glb_json(path):
    data = open(path, "rb").read()
    magic, ver, length = struct.unpack("<III", data[:12])
    if magic != 0x46546C67: raise ValueError("not a GLB (bad magic)")
    if ver != 2: raise ValueError(f"glTF version {ver}, expected 2")
    if length != len(data): raise ValueError(f"length header {length} != file size {len(data)}")
    clen, ctype = struct.unpack("<II", data[12:20])
    if ctype != 0x4E4F534A: raise ValueError("first chunk is not JSON")
    return json.loads(data[20:20 + clen]), data


def _glb(path):
    g, data = glb_json(path)
    tris = 0
    for m in g.get("meshes", []):
        for p in m["primitives"]:
            if "indices" in p: tris += g["accessors"][p["indices"]]["count"] // 3
            else: tris += g["accessors"][p["attributes"]["POSITION"]]["count"] // 3
    return {"meshes": len(g.get("meshes", [])), "nodes": len(g.get("nodes", [])), "triangles": tris,
            "animations": [a.get("name") for a in g.get("animations", [])], "materials": len(g.get("materials", []))}


def _json(path):
    d = json.load(open(path)); return {"keys": sorted(d)[:20]} if isinstance(d, dict) else {"items": len(d)}


def _tiled(path):
    d = json.load(open(path))
    for k in ("width", "height", "tilewidth", "tileheight", "layers"):
        if k not in d: raise ValueError(f"Tiled map lacks {k}")
    for L in d["layers"]:
        if L["type"] == "tilelayer" and len(L["data"]) != L["width"] * L["height"]:
            raise ValueError(f"layer {L['name']}: {len(L['data'])} tiles for {L['width']}x{L['height']}")
    return {"width": d["width"], "height": d["height"], "layers": [L["name"] for L in d["layers"]], "tiled_version": d.get("tiledversion")}


def _svg(path):
    r = ET.parse(path).getroot()
    if not r.tag.endswith("svg"): raise ValueError("root element is not <svg>")
    return {}


def _pdf(path):
    h = open(path, "rb").read(8)
    if not h.startswith(b"%PDF-"): raise ValueError("not a PDF")
    return {"version": h[5:8].decode(errors="replace")}


def _blend(path):
    h = open(path, "rb").read(12)
    if not (h.startswith(b"BLENDER") or h[:2] == b"\x1f\x8b" or h[:4] == b"\x28\xb5\x2f\xfd"): raise ValueError("not a .blend")
    return {}


def _midi(path):
    d = open(path, "rb").read()
    if d[:4] != b"MThd": raise ValueError("not a Standard MIDI File")
    fmt, ntrk, div = struct.unpack(">HHH", d[8:14]); return {"tracks": ntrk, "ppq": div, "smf_format": fmt}


def _bvh(path):
    t = open(path).read(4096)
    if not t.startswith("HIERARCHY"): raise ValueError("not a BVH")
    return {}


def _text(path):
    open(path, encoding="utf-8").read(); return {}


def _html(path):
    t = open(path, encoding="utf-8").read()
    if "<html" not in t.lower(): raise ValueError("no <html> element")
    return {}


def _fbx(path):
    h = open(path, "rb").read(23)
    if not (h.startswith(b"Kaydara FBX Binary") or b"FBX" in open(path, "rb").read(200)): raise ValueError("not an FBX")
    return {}


CHECKS = {"png": _image, "jpeg": _image, "webp": _image, "gif": _image, "wav": _wav, "ogg": _ffprobe, "mp3": _ffprobe, "flac": _ffprobe,
          "mp4": _ffprobe, "webm": _ffprobe, "glb": _glb, "json": _json, "tiled": _tiled, "svg": _svg, "pdf": _pdf, "blend": _blend,
          "midi": _midi, "bvh": _bvh, "text": _text, "csv": _text, "html": _html, "fbx": _fbx, "obj": _text}
