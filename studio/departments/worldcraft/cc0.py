"""WorldCraft helpers for CC0 library assets: a Radiance .hdr (RGBE) decoder, filmic tone mapping, and a glTF → GLB
packer that embeds a downloaded model's buffers and textures (only bytes fetched through core.sources; uris are
looked up in the API's file list, never opened as paths)."""
import io, json, math, struct, urllib.parse
import numpy as np


def read_hdr(data):
    """Radiance RGBE (.hdr, new-style RLE or flat) → float32 (H, W, 3) linear radiance."""
    f = io.BytesIO(data)
    first = f.readline()
    if not first.startswith((b"#?RADIANCE", b"#?RGBE")): raise ValueError("not a Radiance .hdr")
    while True:
        line = f.readline()
        if not line: raise ValueError("truncated .hdr header")
        if line.strip() == b"": break
        if line.startswith(b"FORMAT=") and b"32-bit_rle_rgbe" not in line: raise ValueError("unsupported .hdr format " + line.decode(errors="replace"))
    dims = f.readline().split()
    if len(dims) != 4 or dims[0] != b"-Y" or dims[2] != b"+X": raise ValueError("unsupported .hdr orientation")
    H, W = int(dims[1]), int(dims[3])
    if not (0 < W <= 16384 and 0 < H <= 8192): raise ValueError("unreasonable .hdr size")
    buf = memoryview(data)[f.tell():]; pos = 0
    out = np.empty((H, W, 4), np.uint8)
    for y in range(H):
        if 8 <= W < 32768 and buf[pos] == 2 and buf[pos + 1] == 2 and ((buf[pos + 2] << 8) | buf[pos + 3]) == W:
            pos += 4
            for c in range(4):
                x = 0; row = out[y, :, c]
                while x < W:
                    n = buf[pos]; pos += 1
                    if n > 128:
                        n -= 128; row[x:x + n] = buf[pos]; pos += 1
                    else:
                        if n == 0 or x + n > W: raise ValueError("bad .hdr run")
                        row[x:x + n] = np.frombuffer(buf[pos:pos + n], np.uint8); pos += n
                    x += n
        else:   # flat scanline
            out[y] = np.frombuffer(buf[pos:pos + W * 4], np.uint8).reshape(W, 4); pos += W * 4
    e = out[..., 3].astype(np.int32)
    scale = np.where(e > 0, np.ldexp(1.0, e - 136), 0.0).astype(np.float32)
    return out[..., :3].astype(np.float32) * scale[..., None]


def tonemap(E, exposure=0.0):
    """Linear radiance → display sRGB [0, 1]: auto key (0.18 at the log-average luminance), ACES filmic fit, gamma."""
    L = 0.2126 * E[..., 0] + 0.7152 * E[..., 1] + 0.0722 * E[..., 2]
    key = 0.18 / max(1e-6, float(np.exp(np.mean(np.log(L + 1e-4)))))
    x = E * key * (2.0 ** exposure)
    y = np.clip((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0, 1)
    return np.clip(y ** (1 / 2.2), 0, 1)


def brightest_direction(E):
    """Direction (Y up, -Z forward at the image centre, as WorldCraft's skies) of the brightest region: the sun."""
    H, W = E.shape[:2]; L = E.sum(-1)
    k = max(1, W // 128); h2, w2 = H // k, W // k
    Ls = L[:h2 * k, :w2 * k].reshape(h2, k, w2, k).mean((1, 3))
    y, x = np.unravel_index(int(np.argmax(Ls)), Ls.shape)
    u, v = (x + 0.5) / w2, (y + 0.5) / h2
    lat, lon = (0.5 - v) * math.pi, (u - 0.5) * 2 * math.pi
    d = [math.cos(lat) * math.sin(lon), math.sin(lat), -math.cos(lat) * math.cos(lon)]
    return [round(c, 4) for c in d], round(math.degrees(lat), 2), float(Ls.max() / (np.median(Ls) + 1e-6))


def pack_glb(gltf_bytes, fetch):
    """glTF JSON + external buffers/images (fetch(uri) → bytes) → one GLB (bytes)."""
    g = json.loads(gltf_bytes)
    bin_ = bytearray(); offs = []
    pad = lambda b, ch: b + ch * ((4 - len(b) % 4) % 4)
    for b in g.get("buffers", []):
        data = fetch(urllib.parse.unquote(b["uri"])) if b.get("uri") else b""
        bin_ = bytearray(pad(bytes(bin_), b"\0")); offs.append(len(bin_)); bin_ += data
    for v in g.get("bufferViews", []):
        v["byteOffset"] = v.get("byteOffset", 0) + offs[v["buffer"]]; v["buffer"] = 0
    for img in g.get("images", []):
        if not img.get("uri"): continue
        data = fetch(urllib.parse.unquote(img["uri"]))
        bin_ = bytearray(pad(bytes(bin_), b"\0"))
        g.setdefault("bufferViews", []).append({"buffer": 0, "byteOffset": len(bin_), "byteLength": len(data)}); bin_ += data
        img["bufferView"] = len(g["bufferViews"]) - 1
        img["mimeType"] = "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
        del img["uri"]
    bin_ = pad(bytes(bin_), b"\0")
    g["buffers"] = [{"byteLength": len(bin_)}]
    js = pad(json.dumps(g, separators=(",", ":")).encode(), b" ")
    total = 12 + 8 + len(js) + 8 + len(bin_)
    return struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(bin_), 0x004E4942) + bin_
