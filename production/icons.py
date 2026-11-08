"""APP ICON STUDIO: inspect, choose, derive and verify an app's icon, as part of every production.

Standard library only (the Production Director runs in the studiocraft sandbox and on a plain python3), so it
carries a small PNG codec: decode 8-bit (and 16-bit) non-interlaced PNGs of every colour type, area-average
downscaling, and an RGBA encoder. Artwork is made by the agent with the 2D ArtCraft tools (VectorCraft,
PhotoCraft); this module never draws an icon, it only measures, resizes and checks what was approved.

  inspect(project)            what icon the project has now: none, generic framework art, or a candidate
  validate_concepts(path)     an icon.concepts submission: 2-5 distinct square concepts and a recommendation
  validate_master(path)       the approved master: exactly 1024 x 1024 PNG
  comparison_sheet(...)       concepts.html: every concept at 1024/180/64/32 px on light and dark, side by side
  derivatives(master, ...)    the platform set (PWA 192/512, maskable, Apple touch 180 opaque, favicons, .ico)
  verify(project, ...)        what the shipped build references, at the right sizes, formats and opacity

The planner turns these into tasks (icon.concepts → icon.select (a person picks) → icon.master →
icon.derivatives → integrate → qa.icons); docs/app-standards.md describes the whole workflow."""
import hashlib, html, json, os, re, struct, zlib

SIG = b"\x89PNG\r\n\x1a\n"
# icon files a framework scaffold ships: never acceptable as an app's final icon
GENERIC = {"vite.svg", "react.svg", "vue.svg", "next.svg", "vercel.svg", "svelte.svg", "angular.svg", "logo192.png", "logo512.png",
           "nuxt.svg", "astro.svg", "solid.svg", "favicon-default.ico"}
DERIVATIVES = [
    # file, size, opaque, purpose, role
    ("icon-512.png", 512, False, "any", "icon"),
    ("icon-192.png", 192, False, "any", "icon"),
    ("icon-maskable-512.png", 512, True, "maskable", "icon"),
    ("apple-touch-icon.png", 180, True, "apple", "icon"),
    ("favicon-32.png", 32, False, "favicon", "favicon"),
    ("favicon-16.png", 16, False, "favicon", "favicon"),
]


# ---------------------------------------------------------------- PNG codec
class PNGError(ValueError): pass


def _chunks(data):
    if data[:8] != SIG: raise PNGError("not a PNG file")
    i = 8
    while i + 8 <= len(data):
        n, t = struct.unpack(">I4s", data[i:i + 8]); yield t, data[i + 8:i + 8 + n]; i += 12 + n


def header(path):
    """(width, height, bit_depth, colour_type, interlace) from IHDR without decoding the image."""
    with open(path, "rb") as f: d = f.read(33)
    if d[:8] != SIG or d[12:16] != b"IHDR": raise PNGError("not a PNG file")
    w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", d[16:29])
    return w, h, bd, ct, il


def _paeth(a, b, c):
    p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def decode(path):
    """→ (width, height, rgba bytearray). 8/16-bit, every colour type; interlaced and low bit depths refused."""
    data = open(path, "rb").read()
    ihdr, idat, plte, trns = None, [], None, None
    for t, c in _chunks(data):
        if t == b"IHDR": ihdr = struct.unpack(">IIBBBBB", c)
        elif t == b"IDAT": idat.append(c)
        elif t == b"PLTE": plte = c
        elif t == b"tRNS": trns = c
        elif t == b"IEND": break
    if not ihdr: raise PNGError("PNG has no IHDR")
    w, h, bd, ct, _, _, il = ihdr
    if il: raise PNGError("interlaced PNGs are not supported: export without interlacing")
    if bd not in (8, 16) and not (ct == 3 and bd == 8): raise PNGError(f"PNG bit depth {bd} is not supported: export 8-bit")
    ch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    bpp = ch * (bd // 8); stride = w * bpp
    raw = zlib.decompress(b"".join(idat))
    out = bytearray(w * h * 4); prev = bytearray(stride); pos = 0
    for y in range(h):
        ft = raw[pos]; line = bytearray(raw[pos + 1:pos + 1 + stride]); pos += 1 + stride
        if ft == 1:
            for i in range(bpp, stride): line[i] = (line[i] + line[i - bpp]) & 255
        elif ft == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride): line[i] = (line[i] + ((line[i - bpp] if i >= bpp else 0) + prev[i]) // 2) & 255
        elif ft == 4:
            for i in range(stride): line[i] = (line[i] + _paeth(line[i - bpp] if i >= bpp else 0, prev[i], prev[i - bpp] if i >= bpp else 0)) & 255
        prev = line
        px = line if bd == 8 else line[0::2]   # 16-bit: keep the high byte
        o = y * w * 4
        if ct == 6: out[o:o + w * 4] = px
        elif ct == 2:
            out[o:o + w * 4] = bytes(b for i in range(w) for b in (px[3 * i], px[3 * i + 1], px[3 * i + 2], 255))
            if trns and len(trns) >= 6:
                key = (trns[1], trns[3], trns[5])
                for i in range(w):
                    if tuple(out[o + 4 * i:o + 4 * i + 3]) == key: out[o + 4 * i + 3] = 0
        elif ct == 0:
            out[o:o + w * 4] = bytes(b for v in px[:w] for b in (v, v, v, 255))
        elif ct == 4:
            out[o:o + w * 4] = bytes(b for i in range(w) for b in (px[2 * i], px[2 * i], px[2 * i], px[2 * i + 1]))
        elif ct == 3:
            if not plte: raise PNGError("palette PNG without PLTE")
            for i in range(w):
                k = px[i]; out[o + 4 * i:o + 4 * i + 3] = plte[3 * k:3 * k + 3]
                out[o + 4 * i + 3] = trns[k] if trns and k < len(trns) else 255
    return w, h, out


def encode(path, w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    ck = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    data = SIG + ck(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + ck(b"IDAT", zlib.compress(raw, 9)) + ck(b"IEND", b"")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f: f.write(data)
    return path


def resize(w, h, rgba, nw, nh):
    """Area-average (box) resampling with premultiplied alpha: clean edges when an icon is shrunk."""
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        y0, y1 = y * h / nh, (y + 1) * h / nh
        for x in range(nw):
            x0, x1 = x * w / nw, (x + 1) * w / nw
            acc = [0.0, 0.0, 0.0, 0.0]; tot = 0.0
            sy = int(y0)
            while sy < y1 and sy < h:
                wy = min(sy + 1, y1) - max(sy, y0); sx = int(x0)
                while sx < x1 and sx < w:
                    wt = wy * (min(sx + 1, x1) - max(sx, x0)); i = (sy * w + sx) * 4; a = rgba[i + 3] / 255.0
                    acc[0] += rgba[i] * a * wt; acc[1] += rgba[i + 1] * a * wt; acc[2] += rgba[i + 2] * a * wt; acc[3] += a * wt; tot += wt
                    sx += 1
                sy += 1
            o = (y * nw + x) * 4; a = acc[3] / tot if tot else 0
            if a > 0: out[o:o + 3] = bytes(min(255, int(round(c / acc[3]))) for c in acc[:3])
            out[o + 3] = int(round(a * 255))
    return out


def flatten(w, h, rgba, bg):
    """Composite onto an opaque background (Apple touch icons and maskable art must be opaque)."""
    out = bytearray(rgba)
    for i in range(0, len(out), 4):
        a = out[i + 3] / 255.0
        for k in range(3): out[i + k] = int(round(out[i + k] * a + bg[k] * (1 - a)))
        out[i + 3] = 255
    return out


def pad(w, h, rgba, scale, bg):
    """The art shrunk to `scale` of the tile, centred on an opaque background (the maskable safe zone)."""
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    small = resize(w, h, rgba, nw, nh)
    out = bytearray(bytes(bg[:3]) + b"\xff") * (w * h)
    ox, oy = (w - nw) // 2, (h - nh) // 2
    for y in range(nh):
        for x in range(nw):
            i = (y * nw + x) * 4; o = ((y + oy) * w + x + ox) * 4; a = small[i + 3] / 255.0
            for k in range(3): out[o + k] = int(round(small[i + k] * a + bg[k] * (1 - a)))
    return out


def opaque(rgba): return all(rgba[i] == 255 for i in range(3, len(rgba), 4))


def contrast(w, h, rgba):
    """Luminance standard deviation (0-255) over visible pixels: a proxy for "is there a readable shape at this size"."""
    vals = []
    for i in range(0, len(rgba), 4):
        a = rgba[i + 3] / 255.0
        vals.append((0.2126 * rgba[i] + 0.7152 * rgba[i + 1] + 0.0722 * rgba[i + 2]) * a + 255 * (1 - a) * 0.5)
    m = sum(vals) / len(vals)
    return (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5


def write_ico(path, pngs):
    """A .ico holding PNG images (every modern browser and Windows reads PNG-in-ICO)."""
    entries, blobs, off = [], [], 6 + 16 * len(pngs)
    for size, data in pngs:
        s = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", s, s, 0, 0, 1, 32, len(data), off)); blobs.append(data); off += len(data)
    with open(path, "wb") as f: f.write(struct.pack("<HHH", 0, 1, len(pngs)) + b"".join(entries) + b"".join(blobs))
    return path


def _hex(c):
    if isinstance(c, (list, tuple)): return [int(x) for x in c[:3]]
    c = str(c or "").lstrip("#")
    if len(c) == 3: c = "".join(x * 2 for x in c)
    return [int(c[i:i + 2], 16) for i in (0, 2, 4)] if re.fullmatch(r"[0-9a-fA-F]{6}", c) else None


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


# ---------------------------------------------------------------- discovery: what icon the project has now
def _links(text):
    """<link rel=... href=...> tags in an HTML file, as (rels, href, sizes)."""
    out = []
    for tag in re.findall(r"<link\b[^>]*>", text, re.I):
        rel, href, sizes = (re.search(r"\b" + a + r"""\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", tag, re.I) for a in ("rel", "href", "sizes"))
        rel, href, sizes = ((m and next(g for g in m.groups() if g is not None)) for m in (rel, href, sizes))
        if rel and href: out.append((rel.lower().split(), href, sizes))
    return out


def _resolve(project, entry_dir, href):
    """A referenced URL → a file in the project (query/hash stripped; root-absolute → the web roots)."""
    h = re.sub(r"[?#].*$", "", href)
    if re.match(r"^[a-z]+:", h) or h.startswith("//"): return None   # remote (data:, https:)
    h = h.replace("%BASE_URL%", "/")
    cands = ([os.path.join(entry_dir, h.lstrip("/")), os.path.join(project, "public", h.lstrip("/")), os.path.join(project, h.lstrip("/"))]
             if h.startswith("/") else [os.path.normpath(os.path.join(entry_dir, h)), os.path.join(project, "public", h)])
    return next((c for c in cands if os.path.isfile(c)), cands[0])


def inspect(project):
    """{status: none | generic | candidate | weak, files, best, reason}: the icon a project has before any change."""
    if not project or not os.path.isdir(project): return {"status": "none", "reason": "new project: no icon yet", "files": []}
    found = []
    for d, dirs, files in os.walk(project):
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "dist", "build", ".next", "out", "gitcraft-out") and not x.startswith(".")]
        for f in files:
            lf = f.lower()
            if (re.search(r"(icon|favicon|logo|apple-touch)", lf) and lf.endswith((".png", ".svg", ".ico"))) or lf in GENERIC:
                p = os.path.join(d, f); rel = os.path.relpath(p, project); row = {"path": rel, "generic": lf in GENERIC}
                if lf.endswith(".png"):
                    try: w, h, *_ = header(p); row.update(width=w, height=h)
                    except (OSError, PNGError) as e: row["error"] = str(e)
                found.append(row)
    if not found: return {"status": "none", "reason": "no icon, favicon or logo file found", "files": []}
    real = [r for r in found if not r["generic"] and "error" not in r]
    big = [r for r in real if r.get("width") and r["width"] == r.get("height") and r["width"] >= 512]
    svg = [r for r in real if r["path"].lower().endswith(".svg") and "icon" in r["path"].lower()]
    if big or svg:
        best = sorted(big, key=lambda r: -r["width"])[0] if big else svg[0]
        return {"status": "candidate", "best": best["path"], "files": found[:20],
                "reason": f"{best['path']} could serve as the master (inspect it: keep it if it is good, refine it otherwise)"}
    if real: return {"status": "weak", "files": found[:20], "reason": "only small or non-square icon files: too small to derive a full set from"}
    return {"status": "generic", "files": found[:20], "reason": "only a framework's default icon (" + ", ".join(r["path"] for r in found[:4]) + ")"}


# ---------------------------------------------------------------- agent submissions
def validate_concepts(path, base):
    """The icon.concepts submission. → [check]"""
    checks = []
    try: data = json.load(open(path))
    except (OSError, ValueError) as e: return [{"name": "concepts.json reads as JSON", "ok": False, "detail": str(e)}]
    cs = data.get("concepts") or []
    checks.append({"name": "2 to 5 concepts (a small set of real alternatives)", "ok": 2 <= len(cs) <= 5, "detail": f"{len(cs)} concepts"})
    ids, hashes = [], set()
    for c in cs:
        cid = str(c.get("id") or ""); ids.append(cid)
        p = c.get("file") or ""; p = p if os.path.isabs(p) else os.path.join(base, p)
        if not os.path.isfile(p): checks.append({"name": f"concept {cid}: file exists", "ok": False, "detail": c.get("file")}); continue
        try: w, h, *_ = header(p)
        except PNGError as e: checks.append({"name": f"concept {cid}: opens as PNG", "ok": False, "detail": str(e)}); continue
        checks.append({"name": f"concept {cid}: square, at least 512 px", "ok": w == h and w >= 512, "detail": f"{w}x{h}"})
        checks.append({"name": f"concept {cid}: says what the idea is", "ok": len(str(c.get("idea") or "")) >= 8, "detail": None if c.get("idea") else "no idea text"})
        hashes.add(sha(p))
    checks.append({"name": "concepts are different files", "ok": len(hashes) == len(cs), "detail": None if len(hashes) == len(cs) else "two concepts are the same image"})
    checks.append({"name": "concept ids are unique", "ok": len(set(ids)) == len(ids) and all(ids)})
    checks.append({"name": "a recommended concept is named", "ok": data.get("recommended") in ids, "detail": data.get("recommended")})
    return checks


def validate_master(path, base=None):
    try: w, h, bd, ct, il = header(path)
    except (OSError, PNGError) as e: return [{"name": "the master opens as PNG", "ok": False, "detail": str(e)}]
    return [{"name": "the master is exactly 1024 x 1024", "ok": (w, h) == (1024, 1024), "detail": f"{w}x{h}"},
            {"name": "the master is decodable (8/16-bit, not interlaced)", "ok": il == 0 and bd in (8, 16) or ct == 3, "detail": f"bit depth {bd}, interlace {il}"}]


def validate_features(path, base=None):
    """tests/gitcraft.features.json: named features, each ending in something a person can see (expect/assert)."""
    try: data = json.load(open(path))
    except (OSError, ValueError) as e: return [{"name": "the feature file reads as JSON", "ok": False, "detail": str(e)}]
    fs = data.get("features") or []
    bad = [f.get("name") or f"#{i}" for i, f in enumerate(fs, 1) if not f.get("name") or not any(("expect" in st or "assert" in st) for st in f.get("steps") or [])]
    return [{"name": "at least one feature is listed", "ok": bool(fs), "detail": f"{len(fs)} features"},
            {"name": "every feature ends in an observable outcome (expect or assert)", "ok": not bad, "detail": bad[:8] or None}]


SECRETISH = re.compile(r"(postgres(?:ql)?://[^\s\"']*:[^\s\"'@]+@|npg_[A-Za-z0-9]{8,}|sk_(?:live|test)_[A-Za-z0-9]{8,}|eyJhbGciOi|password\"\s*:\s*\"[^\"]{4,})", re.I)


def validate_no_secrets(path, base=None):
    t = open(path, errors="ignore").read()
    m = SECRETISH.search(t)
    return [{"name": f"{os.path.basename(path)} holds names only, no secret values", "ok": not m, "detail": "a connection string, key or password is in the file: remove it" if m else None}]


VALIDATORS = {"icon_concepts": validate_concepts, "icon_master": validate_master, "features": validate_features, "no_secrets": validate_no_secrets}


# ---------------------------------------------------------------- the comparison sheet a person chooses from
def comparison_sheet(concepts, base, out_path, title, recommended=None):
    def rel(p):
        p = p if os.path.isabs(p) else os.path.join(base, p); return os.path.relpath(p, os.path.dirname(out_path))
    cards = []
    for c in concepts:
        src = html.escape(rel(c["file"]))
        rec = '<span class="rec">Recommended</span>' if c.get("id") == recommended else ""
        sizes = "".join(f'<figure><img src="{src}" width="{s}" height="{s}" alt=""><figcaption>{s}px</figcaption></figure>' for s in (180, 64, 32))
        cards.append(f'''<article><h2>{html.escape(str(c.get("id")))} {rec}</h2><img class="big" src="{src}" alt="{html.escape(str(c.get("idea", "")))}">
<p>{html.escape(str(c.get("idea", "")))}</p>{f'<p class="why">{html.escape(str(c.get("rationale")))}</p>' if c.get("rationale") else ""}
<div class="row light">{sizes}</div><div class="row dark">{sizes}</div></article>''')
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}: icon concepts</title><style>
body{{font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;background:#f4f4f2;color:#1b1b1b}}h1{{font-size:20px}}
main{{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}}article{{background:#fff;border-radius:14px;padding:14px}}
h2{{font-size:16px;margin:0 0 8px}}.rec{{background:#1f6f43;color:#fff;font-size:12px;border-radius:99px;padding:2px 8px;margin-left:6px}}
.big{{width:100%;max-width:256px;aspect-ratio:1;border-radius:22%;display:block}}.row{{display:flex;gap:12px;align-items:end;padding:10px;border-radius:10px;margin-top:8px}}
.row img{{border-radius:22%}}.light{{background:#e9e9e6}}.dark{{background:#16161a;color:#ddd}}figure{{margin:0;text-align:center;font-size:11px}}.why{{color:#555}}
</style></head><body><h1>{html.escape(title)}: choose an app icon</h1><p>Each concept at full size, then at home-screen (180), list (64) and tab (32) size on light and dark.
Reply with the concept id to approve, or ask for revisions.</p><main>{"".join(cards)}</main></body></html>'''
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").write(doc)
    return out_path


# ---------------------------------------------------------------- the platform set from the approved master
def href_prefix(asset_dir):
    """How the build refers to <asset_dir>/icons. public/ is served from the site root by Vite/Next (which add the
    configured base path), so it is root-absolute; a static site uses relative URLs, which also work under a
    GitHub Pages subpath."""
    a = (asset_dir or "").strip("/")
    if a == "public": return "/icons/"
    if a.startswith("public/"): return "/" + a[len("public/"):] + "/icons/"
    return (a + "/icons/") if a else "icons/"


ANDROID = [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)]


def native_sets(w, h, px, bg, out_dir, platforms):
    """iOS: a single-size 1024 asset catalog (opaque: the App Store rejects alpha). Android: legacy mipmaps plus an
    adaptive icon (108 dp foreground with the art in the 66 dp safe zone, over a solid background colour)."""
    outs, checks = [], []
    if "ios" in platforms:
        d = os.path.join(out_dir, "ios", "AppIcon.appiconset"); os.makedirs(d, exist_ok=True)
        p = encode(os.path.join(d, "AppIcon-1024.png"), w, h, flatten(w, h, px, bg))
        json.dump({"images": [{"filename": "AppIcon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}], "info": {"author": "gitcraft", "version": 1}},
                  open(os.path.join(d, "Contents.json"), "w"), indent=1)
        outs += [{"path": p, "rel": "ios/AppIcon.appiconset/AppIcon-1024.png", "role": "icon_native", "format": "png"},
                 {"path": os.path.join(d, "Contents.json"), "rel": "ios/AppIcon.appiconset/Contents.json", "role": "icon_native", "format": "json"}]
        checks.append({"name": "iOS: 1024 x 1024 opaque App Store icon + Contents.json", "ok": opaque(decode(p)[2])})
    if "android" in platforms:
        hexbg = "#%02x%02x%02x" % tuple(bg)
        flat, safe = flatten(w, h, px, bg), pad(w, h, px, 66 / 108, bg)   # once, then resized per density
        for dens, size in ANDROID:
            d = os.path.join(out_dir, "android", "res", f"mipmap-{dens}")
            p = encode(os.path.join(d, "ic_launcher.png"), size, size, resize(w, h, flat, size, size))
            outs.append({"path": p, "rel": f"android/res/mipmap-{dens}/ic_launcher.png", "role": "icon_native", "format": "png"})
            fg = os.path.join(d, "ic_launcher_foreground.png")
            encode(fg, size * 9 // 4, size * 9 // 4, resize(w, h, safe, size * 9 // 4, size * 9 // 4))
            outs.append({"path": fg, "rel": f"android/res/mipmap-{dens}/ic_launcher_foreground.png", "role": "icon_native", "format": "png"})
        ad = os.path.join(out_dir, "android", "res", "mipmap-anydpi-v26"); os.makedirs(ad, exist_ok=True)
        open(os.path.join(ad, "ic_launcher.xml"), "w").write('<?xml version="1.0" encoding="utf-8"?>\n<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
                                                             '  <background android:drawable="@color/ic_launcher_background"/>\n  <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n</adaptive-icon>\n')
        vd = os.path.join(out_dir, "android", "res", "values"); os.makedirs(vd, exist_ok=True)
        open(os.path.join(vd, "ic_launcher_background.xml"), "w").write(f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n  <color name="ic_launcher_background">{hexbg}</color>\n</resources>\n')
        outs += [{"path": os.path.join(ad, "ic_launcher.xml"), "rel": "android/res/mipmap-anydpi-v26/ic_launcher.xml", "role": "icon_native", "format": "text"},
                 {"path": os.path.join(vd, "ic_launcher_background.xml"), "rel": "android/res/values/ic_launcher_background.xml", "role": "icon_native", "format": "text"}]
        checks.append({"name": "Android: mipmaps 48-192 px + adaptive icon (foreground in the safe zone, background colour)",
                       "ok": all(header(o["path"])[:2] == (s2, s2) for o, (_, s2) in zip([o for o in outs if o["rel"].endswith("/ic_launcher.png")], ANDROID))})
    return outs, checks


def derivatives(master, out_dir, background=None, name="App", theme=None, prefix="icons/", source_svg=None, platforms=()):
    """→ {status, outputs, checks, snippet}. Writes the PWA, Apple, maskable and favicon set beside a copy of the master."""
    os.makedirs(out_dir, exist_ok=True)
    w, h, px = decode(master)
    checks = [{"name": "master is 1024 x 1024", "ok": (w, h) == (1024, 1024), "detail": f"{w}x{h}"}]
    if (w, h) != (1024, 1024): return {"status": "failed", "failure": "request", "error": f"the master must be 1024 x 1024 (it is {w}x{h})", "checks": checks, "outputs": []}
    bg = _hex(background) or (list(px[0:3]) if px[3] == 255 else [255, 255, 255])
    outs = []
    mpath = os.path.join(out_dir, "icon-1024.png"); encode(mpath, w, h, px)
    outs.append({"path": mpath, "role": "icon_master", "format": "png"})
    if source_svg and os.path.isfile(source_svg):
        sp = os.path.join(out_dir, "icon.svg"); open(sp, "wb").write(open(source_svg, "rb").read()); outs.append({"path": sp, "role": "icon", "format": "svg"})
    ico = []
    for fname, size, must_opaque, purpose, role in DERIVATIVES:
        if purpose == "maskable": img = resize(w, h, pad(w, h, px, 0.8, bg), size, size)
        else:
            img = resize(w, h, px, size, size)
            if must_opaque: img = flatten(size, size, img, bg)
        p = encode(os.path.join(out_dir, fname), size, size, img)
        outs.append({"path": p, "role": role, "format": "png"})
        ok = (not must_opaque) or opaque(img)
        checks.append({"name": f"{fname}: {size}x{size}" + (", opaque" if must_opaque else ""), "ok": ok})
    for s in (16, 32, 48):
        tmp = encode(os.path.join(out_dir, f".ico-{s}.png"), s, s, resize(w, h, px, s, s)); ico.append((s, open(tmp, "rb").read())); os.remove(tmp)
    outs.append({"path": write_ico(os.path.join(out_dir, "favicon.ico"), ico), "role": "favicon", "format": "ico"})
    if platforms:
        n_outs, n_checks = native_sets(w, h, px, bg, out_dir, platforms); outs += n_outs; checks += n_checks
    small = resize(w, h, px, 32, 32); c32 = round(contrast(32, 32, small), 1)
    checks.append({"name": "small-size clarity: the 32 px icon has a visible shape (luminance spread ≥ 12)", "ok": c32 >= 12, "measured": c32,
                   "detail": None if c32 >= 12 else "at 32 px the icon is nearly one flat tone: simplify the mark or raise its contrast"})
    theme_hex = "#%02x%02x%02x" % tuple(_hex(theme) or bg)
    p = prefix
    has_svg = any(o["path"].endswith("icon.svg") for o in outs)
    head = "\n".join(([f'<link rel="icon" href="{p}icon.svg" type="image/svg+xml">'] if has_svg else []) + [
        f'<link rel="icon" href="{p}favicon.ico" sizes="48x48">',
        f'<link rel="icon" href="{p}favicon-32.png" type="image/png" sizes="32x32">',
        f'<link rel="icon" href="{p}favicon-16.png" type="image/png" sizes="16x16">',
        f'<link rel="apple-touch-icon" href="{p}apple-touch-icon.png" sizes="180x180">',
        '<link rel="manifest" href="manifest.webmanifest">' if not p.startswith("/") else '<link rel="manifest" href="/manifest.webmanifest">',
        f'<meta name="theme-color" content="{theme_hex}">',
        f'<meta name="apple-mobile-web-app-title" content="{html.escape(name)}">'])
    manifest_icons = [{"src": f"{p}icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                      {"src": f"{p}icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                      {"src": f"{p}icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
    snippet = {"head": head, "manifest": {"name": name, "short_name": name[:12], "icons": manifest_icons, "theme_color": theme_hex,
                                          "background_color": "#%02x%02x%02x" % tuple(bg), "display": "standalone", "start_url": "."},
               "note": "icon URLs are relative to index.html (static site; works under a subpath) or root-absolute under public/ "
                       "(Vite/Next add their configured base). Put the manifest beside index.html (or in public/)."}
    sp = os.path.join(out_dir, "icons.snippet.json"); json.dump(snippet, open(sp, "w"), indent=1)
    outs.append({"path": sp, "role": "icon_snippet", "format": "json"})
    for o in outs: o["sha256"] = sha(o["path"])
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "outputs": outs, "checks": checks, "snippet": snippet,
            "background": "#%02x%02x%02x" % tuple(bg)}


# ---------------------------------------------------------------- verification of the shipped build
def _entry(project):
    for d in ("dist", "build", "out"):
        if os.path.isfile(os.path.join(project, d, "index.html")): return os.path.join(project, d, "index.html")
    for r in ("index.html", "public/index.html", "src/index.html"):
        if os.path.isfile(os.path.join(project, r)): return os.path.join(project, r)
    return None


def verify(project, require_manifest=True, decision=None):
    """→ {status, checks, findings}. Measures the build's icon references; reports what it could not check."""
    checks, info = [], {}
    entry = _entry(project)
    if not entry: return {"status": "failed", "checks": [{"name": "an entry index.html exists", "ok": False}], "outputs": []}
    ed = os.path.dirname(entry); text = open(entry, errors="ignore").read()
    links = _links(text); info["entry"] = os.path.relpath(entry, project)

    def png_check(label, href, size=None, need_opaque=False):
        p = _resolve(project, ed, href)
        if not p or not os.path.isfile(p):
            checks.append({"name": f"{label}: {href} exists", "ok": False, "detail": "missing (broken icon reference)"}); return None
        if os.path.basename(p).lower() in GENERIC:
            checks.append({"name": f"{label}: not a framework's default icon", "ok": False, "detail": os.path.basename(p)}); return p
        if p.lower().endswith(".png"):
            try: w, h, px = decode(p)
            except PNGError as e: checks.append({"name": f"{label}: {href} opens as PNG", "ok": False, "detail": str(e)}); return p
            if size: checks.append({"name": f"{label}: {size}x{size}", "ok": (w, h) == (size, size), "detail": f"{w}x{h}"})
            if need_opaque: checks.append({"name": f"{label}: opaque (iOS fills transparency with black)", "ok": opaque(px)})
            if size and size <= 32 or label == "favicon":
                c = round(contrast(w, h, px), 1); checks.append({"name": f"{label}: visible shape at small size (luminance spread ≥ 12)", "ok": c >= 12, "measured": c})
        elif p.lower().endswith(".ico"):
            d = open(p, "rb").read(6); checks.append({"name": f"{label}: {href} is an ICO file", "ok": d[:4] == b"\x00\x00\x01\x00"})
        elif p.lower().endswith(".svg"):
            checks.append({"name": f"{label}: {href} is an SVG", "ok": "<svg" in open(p, errors="ignore").read(4000)})
        return p

    icons = [l for l in links if "icon" in l[0] and "apple-touch-icon" not in l[0]]
    apple = [l for l in links if "apple-touch-icon" in l[0]]
    man = [l for l in links if "manifest" in l[0]]
    checks.append({"name": "a favicon is linked from the entry page", "ok": bool(icons), "detail": None if icons else "no <link rel=icon>: browsers fall back to /favicon.ico"})
    for _, href, _s in icons[:4]: png_check("favicon", href)
    checks.append({"name": "an Apple touch icon is linked (iPhone Home Screen)", "ok": bool(apple)})
    for _, href, _s in apple[:1]: png_check("apple-touch-icon", href, 180, need_opaque=True)
    if require_manifest or man:
        checks.append({"name": "a web app manifest is linked", "ok": bool(man)})
        if man:
            mp = _resolve(project, ed, man[0][1])
            try:
                mj = json.load(open(mp)); ms = mj.get("icons") or []
                checks.append({"name": "the manifest names the app", "ok": bool(mj.get("name") or mj.get("short_name"))})
                for want in (192, 512):
                    e = next((i for i in ms if f"{want}x{want}" in str(i.get("sizes")) and "maskable" not in str(i.get("purpose", "any"))), None)
                    checks.append({"name": f"the manifest lists a {want}x{want} icon", "ok": bool(e)})
                    if e: png_check(f"manifest {want}", _rel_to(e["src"], mp, ed), want)
                mk = next((i for i in ms if "maskable" in str(i.get("purpose"))), None)
                info["maskable"] = bool(mk)
                if mk: png_check("manifest maskable", _rel_to(mk["src"], mp, ed), None, need_opaque=True)
            except (OSError, ValueError, TypeError) as e:
                checks.append({"name": "the manifest reads as JSON", "ok": False, "detail": f"{man[0][1]}: {e}"})
    title = re.search(r"apple-mobile-web-app-title", text, re.I)
    info["metadata"] = {"apple_title": bool(title), "theme_color": bool(re.search(r'name=["\']theme-color', text, re.I))}
    if decision: info["decision"] = decision
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks, "info": info, "outputs": [],
            "not_checked": ["the deployed URLs serve these files (checked by the deployment evidence against the live URL)"]}


def _rel_to(src, manifest_path, entry_dir):
    """Manifest icon URLs are relative to the manifest; express them relative to the entry page for _resolve."""
    if re.match(r"^[a-z]+:|^/", src): return src
    return os.path.relpath(os.path.normpath(os.path.join(os.path.dirname(manifest_path), src)), entry_dir)
