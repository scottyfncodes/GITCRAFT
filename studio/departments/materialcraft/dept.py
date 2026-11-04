"""MaterialCraft: tileable PBR materials (numpy generators in materials.py), weathering, toon
styling, seamless-izing of existing images, toon ramps. Every material ships as a glTF 2.0
metallic-roughness map set, a sample sphere GLB with the maps embedded (loads in any engine), and is
rendered in three.js r170 and checked for seams before it is reported."""
import io, json, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import materials as M
from core import media, noise as N, webpages
from core.contract import StudioError


def _save(a, path, mode=None): media.to_image(a, mode).save(path); return path


def seam_score(img):
    """Wrap-around step relative to the largest ordinary column/row steps in the same image
    (99th percentile). A real seam stands out; a mortar line that happens to sit on the edge
    does not, because the same step occurs wherever the pattern repeats. ≤ 1.5 = seamless."""
    a = np.asarray(img, float); a = a if a.ndim == 3 else a[..., None]
    worst = 0.0
    for ax in (0, 1):
        steps = np.abs(np.diff(a, axis=ax)).mean(axis=tuple(i for i in range(a.ndim) if i != ax))
        wrap = np.abs(np.take(a, 0, axis=ax) - np.take(a, -1, axis=ax)).mean()
        worst = max(worst, wrap / (np.percentile(steps, 99) + 1e-6))
    return float(worst)


def _tile_preview(alb, path):
    from PIL import Image
    im = media.to_image(alb); w, h = im.size; T = Image.new("RGB", (w * 2, h * 2))
    for i in range(2):
        for j in range(2): T.paste(im, (i * w, j * h))
    T = T.resize((min(1024, w * 2), min(1024, h * 2))); T.save(path); return path


def _ao(h, n):
    cav = N.blur(h, max(2, n // 48)) - h
    return np.clip(1 - np.clip(cav * 5, 0, 1) * 0.8, 0, 1)


def generate(ctx, p):
    ctx.used("studio_materials", "numpy"); n = p["resolution"]
    color = np.array(p["color"], float) / 255 if p.get("color") else None
    m = M.generate(p["material"], n, ctx.seed, p["scale"], color); ctx.stage("generated", material=p["material"])
    if any(p[k] for k in ("dirt", "moss", "wear", "wet")): m = M.weather(m, p["dirt"], p["moss"], p["wear"], p["wet"], ctx.seed); ctx.stage("weathered")
    if p["style"] == "toon": m = M.toonify(m, p["toon_bands"])
    stem = p.get("name") or p["material"]; outs = []
    add = lambda path, role, fmt="png": outs.append({"path": path, "role": role, "format": fmt})
    nrm = N.normal_map(m["height"], strength=p["normal_strength"], tile=True)
    if p["normal_convention"] == "directx": nrm[..., 1] = 1 - nrm[..., 1]
    ao = _ao(m["height"], n)
    add(_save(m["albedo"], ctx.path(f"{stem}_basecolor.png")), "basecolor")
    add(_save(nrm, ctx.path(f"{stem}_normal.png")), f"normal ({p['normal_convention']})")
    add(_save(m["roughness"], ctx.path(f"{stem}_roughness.png")), "roughness")
    add(_save(m["metallic"], ctx.path(f"{stem}_metallic.png")), "metallic")
    add(_save(ao, ctx.path(f"{stem}_ao.png")), "ao")
    add(media.save_png16(m["height"], ctx.path(f"{stem}_height16.png")), "height")
    orm = np.stack([ao, m["roughness"], m["metallic"]], -1)
    add(_save(orm, ctx.path(f"{stem}_orm.png")), "orm (R=AO G=roughness B=metallic, glTF)")
    if m["emission"] is not None: add(_save(m["emission"], ctx.path(f"{stem}_emission.png")), "emission")
    add(_tile_preview(m["albedo"], ctx.path(f"{stem}_tiled2x2.png")), "preview")
    # glTF material + three.js parameters
    mat = {"name": stem, "pbrMetallicRoughness": {"baseColorTexture": f"{stem}_basecolor.png", "metallicRoughnessTexture": f"{stem}_orm.png",
                                                    "metallicFactor": 1.0, "roughnessFactor": 1.0},
           "normalTexture": f"{stem}_normal.png", "occlusionTexture": f"{stem}_orm.png", "emissiveTexture": f"{stem}_emission.png" if m["emission"] is not None else None,
           "tiling_m": p["tile_meters"], "three": {"type": "MeshStandardMaterial", "map": f"{stem}_basecolor.png (SRGBColorSpace, RepeatWrapping)",
                                                  "normalMap": f"{stem}_normal.png", "roughnessMap": f"{stem}_orm.png", "metalnessMap": f"{stem}_orm.png", "aoMap": f"{stem}_orm.png",
                                                  "displacementMap": f"{stem}_height16.png (optional)", "emissiveMap": f"{stem}_emission.png" if m["emission"] is not None else None},
           "averages": {"basecolor_srgb": [round(float(v), 3) for v in m["albedo"].reshape(-1, 3).mean(0)], "roughness": round(float(m["roughness"].mean()), 3),
                        "metallic": round(float(m["metallic"].mean()), 3)}}
    jp = ctx.path(f"{stem}.material.json"); json.dump(mat, open(jp, "w"), indent=1); add(jp, "material", "json")
    # sample sphere GLB with every map embedded: the material as any engine will load it
    sph = media.uv_sphere(1.0); sph.update(name=stem, material={"texture": ctx.path(f"{stem}_basecolor.png"), "orm_texture": ctx.path(f"{stem}_orm.png"),
                                                                 "normal_texture": ctx.path(f"{stem}_normal.png"),
                                                                 "emissive_texture": ctx.path(f"{stem}_emission.png") if m["emission"] is not None else None})
    glb = media.write_glb(ctx.path(f"{stem}_sphere.glb"), [sph], name=stem); add(glb, "sample", "glb")
    shot = ctx.path(f"{stem}_render.png")
    checks, _, rep = webpages.glb_checks(glb, shot, "material sphere", size=(512, 512), camera=[0, 0.6, 2.9], target=[0, 0, 0], background="#3a3f47")
    ctx.used("three", "gltf_validator"); add(shot, "render")
    seams = {k: round(seam_score(v), 3) for k, v in (("basecolor", m["albedo"]), ("height", m["height"]), ("normal", nrm), ("roughness", m["roughness"]))}
    nv = nrm * 2 - 1; unit = float(np.abs(np.linalg.norm(nv, axis=-1) - 1).max())
    checks += [{"name": "tiles seamlessly (wrap step ≤ 1.5× the 99th-percentile ordinary step, every map)", "ok": max(seams.values()) <= 1.5, "detail": seams},
               {"name": "normal map vectors are unit length", "ok": unit < 0.02, "detail": round(unit, 4)},
               {"name": "maps are in range and not flat", "ok": float(m["albedo"].std()) > 0.005 and 0 <= m["roughness"].min() <= m["roughness"].max() <= 1, "detail": round(float(m["albedo"].std()), 4)}]
    return {"outputs": outs, "checks": checks, "material": mat}


def seamless(ctx, p):
    """Make an existing texture tileable: offset by half, blend the seams with a feathered copy."""
    from PIL import Image
    src = ctx.need(p["input"]); ctx.used("studio_materials")
    im = Image.open(src); mode = "RGBA" if im.mode in ("RGBA", "LA") else "RGB"
    a = np.asarray(im.convert(mode), float) / 255; h, w = a.shape[:2]
    before = seam_score(a)
    k = p["blend"]
    # two separable passes. Pass x: a copy rolled by half the width wraps seamlessly at the left/right
    # edges but has the old seam in its middle column; use the copy near the edges and the original
    # (continuous in its middle) near the centre, weighted by x only. Then the same in y on that result.
    def half_blend(img, axis):
        n = img.shape[axis]; rolled = np.roll(img, n // 2, axis)
        d = np.abs(np.arange(n) - n / 2) / (n * k / 2)                 # 0 at the centre line → 1 at k/2 of the size away
        wgt = np.clip(d, 0, 1); wgt = wgt * wgt * (3 - 2 * wgt)           # 0 on the centre line (original), 1 towards the edges (rolled)
        shape = [1] * img.ndim; shape[axis] = n; wgt = wgt.reshape(shape)
        return rolled * wgt + img * (1 - wgt)
    out = half_blend(half_blend(a, 1), 0)
    after = seam_score(out)
    stem = p.get("name") or os.path.splitext(os.path.basename(src))[0] + "_seamless"
    o = ctx.path(f"{stem}.png"); media.to_image(out, mode).save(o)
    return {"outputs": [{"path": o, "role": "texture", "format": "png"}, {"path": _tile_preview(out[..., :3], ctx.path(f"{stem}_tiled2x2.png")), "role": "preview", "format": "png"}],
            "seam": {"before": round(before, 3), "after": round(after, 3)},
            "checks": [{"name": "tiles seamlessly after processing", "ok": after <= 1.5, "detail": {"before": round(before, 3), "after": round(after, 3)}}]}


def toon_ramp(ctx, p):
    """A gradient map for toon shading (three.js MeshToonMaterial.gradientMap, Godot/Unity ramp shaders)."""
    ctx.used("studio_materials"); b = p["bands"]; w = p["width"]
    stops = np.linspace(p["shadow"], 1.0, b)
    row = np.repeat(stops, int(np.ceil(w / b)))[:w]
    if p["soft"]: row = N.blur(row[None, :].repeat(4, 0), max(1, w // (b * 8)), tile=False)[0]
    img = np.repeat(row[None, :], p["height"], 0)
    tint = np.array(p["tint"], float) / 255 if p.get("tint") else np.ones(3)
    rgb = np.clip(img[..., None] * tint, 0, 1)
    stem = p.get("name") or f"toon_ramp_{b}"
    o = ctx.path(f"{stem}.png"); _save(rgb, o)
    jp = ctx.path(f"{stem}.json"); json.dump({"bands": b, "shadow": p["shadow"], "soft": p["soft"],
                                               "three": "new THREE.MeshToonMaterial({ gradientMap: tex }) with tex.minFilter = tex.magFilter = THREE.NearestFilter"}, open(jp, "w"), indent=1)
    levels = len(np.unique(np.round(rgb[0, :, 0], 3)))
    return {"outputs": [{"path": o, "role": "gradient_map", "format": "png"}, {"path": jp, "role": "usage", "format": "json"}],
            "checks": [{"name": f"ramp has {b} bands", "ok": p["soft"] or levels == b, "detail": levels}]}


def library(ctx, p):
    """A swatch sheet of many materials at once (quick look-development)."""
    ctx.used("studio_materials"); tiles, labels, recs = [], [], []
    for k in p["materials"]:
        m = M.generate(k, p["resolution"], ctx.seed, 1.0)
        nrm = N.normal_map(m["height"], 4.0); shade = np.clip(nrm[..., 2:3] * 0.6 + nrm[..., :1] * 0.4, 0, 1)
        tiles.append(media.to_image(np.clip(m["albedo"] * (0.55 + 0.6 * shade), 0, 1))); labels.append(k)
    o = ctx.path((p.get("name") or "material_swatches") + ".png")
    media.contact_sheet(tiles, o, cols=min(6, len(tiles)), cell=p["resolution"], labels=labels, title="MaterialCraft swatches (albedo lit by its normal map)")
    return {"outputs": [{"path": o, "role": "preview", "format": "png"}], "checks": [{"name": "every material generated", "ok": len(tiles) == len(p["materials"])}]}


# ---------------------------------------------------------------- CC0 libraries (Poly Haven, ambientCG)
PH_MAPS = {"basecolor": ["Diffuse"], "normal_gl": ["nor_gl"], "normal_dx": ["nor_dx"], "roughness": ["Rough"], "ao": ["AO"],
           "height": ["Displacement"], "metallic": ["Metal"], "orm": ["arm"]}
ACG_MAPS = {"basecolor": "_Color", "normal_gl": "_NormalGL", "normal_dx": "_NormalDX", "roughness": "_Roughness", "ao": "_AmbientOcclusion",
            "height": "_Displacement", "metallic": "_Metalness"}


def _candidates(p):
    from core import sources as SRC
    src, q, n = p["source"], p.get("query") or "", p["candidates"]
    out = []
    if p.get("id"):
        if src in ("auto", "polyhaven") and not p["id"][0].isupper():
            info = SRC.polyhaven_info(p["id"])
            return [{"source": "polyhaven", "id": p["id"], "name": info.get("name"), "tags": info.get("tags", [])[:8], "categories": info.get("categories", []),
                     "authors": list((info.get("authors") or {}).keys()), "page": f"https://polyhaven.com/a/{p['id']}", "license": SRC.LICENSE}]
        found = [c for c in SRC.ambientcg_search(p["id"], limit=5) if c["id"].lower() == p["id"].lower()]
        if not found: raise StudioError(f"no material {p['id']!r} on {'ambientCG' if src != 'polyhaven' else 'Poly Haven'}")
        return found
    if src in ("auto", "polyhaven"): out += SRC.polyhaven_search("textures", q, n)
    if src in ("auto", "ambientcg"): out += SRC.ambientcg_search(q, n)
    out.sort(key=lambda c: (-c["score"], -c.get("downloads", 0)))
    if not out: raise StudioError(f"no CC0 material matches {q!r}", hint="try broader words (e.g. 'snow', 'rock', 'rusty metal') or list_only: true")
    return out[:n]


def fetch(ctx, p):
    """A CC0 PBR material from Poly Haven or ambientCG, normalised to MaterialCraft's map set and checked like a generated one."""
    from PIL import Image
    from core import sources as SRC
    ctx.used("cc0_sources"); cands = _candidates(p)
    short = [{k: c.get(k) for k in ("source", "id", "name", "tags", "page")} for c in cands]
    if p["list_only"]:
        jp = ctx.path((p.get("name") or "cc0_materials") + ".candidates.json"); json.dump(short, open(jp, "w"), indent=1)
        return {"outputs": [{"path": jp, "role": "candidates", "format": "json"}], "checks": [{"name": "found CC0 candidates", "ok": bool(short), "detail": len(short)}],
                "candidates": short, "output_license": SRC.LICENSE}
    c = cands[0]; res = p["resolution"]; stem = p.get("name") or re.sub(r"[^a-z0-9_]+", "_", c["id"].lower())
    raw = {}
    if c["source"] == "polyhaven":
        files = SRC.polyhaven_files(c["id"])
        for role, keys in PH_MAPS.items():
            for k in keys:
                byres = files.get(k) or {}
                if res not in byres: continue
                fmt = "jpg" if "jpg" in byres[res] else ("png" if "png" in byres[res] else None)
                if fmt: raw[role] = SRC.fetch_checked(byres[res][fmt])
        if not raw.get("basecolor"): raise StudioError(f"{c['id']} has no {res} colour map", hint="pick another resolution (1k, 2k, 4k)")
    else:
        attr = {"1k": "1K-JPG", "2k": "2K-JPG", "4k": "4K-JPG"}[res]
        z = c.get("zips", {}).get(attr)
        if not z: raise StudioError(f"{c['id']} has no {attr} download", hint="pick another resolution")
        if z.get("size", 0) > 256 * SRC.MB: raise StudioError(f"{c['id']} {attr} is too large ({z['size'] // SRC.MB} MB)")
        members = SRC.zip_images(SRC.get(z["url"], max_bytes=256 * SRC.MB, timeout=300))
        for role, suffix in ACG_MAPS.items():
            hit = next((b for n_, b in members.items() if re.search(re.escape(suffix) + r"\.(jpe?g|png)$", n_, re.I)), None)
            if hit: raw[role] = hit
        if not raw.get("basecolor"): raise StudioError(f"{c['id']}: no colour map in the download")
    ctx.stage("downloaded", source=c["source"], id=c["id"], maps=sorted(raw))
    load = lambda b, mode: np.asarray(Image.open(io.BytesIO(b)).convert(mode), float) / 255   # decode only through Pillow
    alb = load(raw["basecolor"], "RGB"); h_, w_ = alb.shape[:2]
    fit = lambda a: a if a.shape[:2] == (h_, w_) else np.asarray(media.to_image(a).resize((w_, h_)), float) / 255
    # normal: keep the requested convention (glTF/three.js use OpenGL, +Y up)
    want = "normal_gl" if p["normal_convention"] == "opengl" else "normal_dx"
    other = "normal_dx" if want == "normal_gl" else "normal_gl"
    if want in raw: nrm = fit(load(raw[want], "RGB"))
    elif other in raw: nrm = fit(load(raw[other], "RGB")); nrm[..., 1] = 1 - nrm[..., 1]
    else: nrm = None
    rough = fit(load(raw["roughness"], "L")) if "roughness" in raw else None
    ao = fit(load(raw["ao"], "L")) if "ao" in raw else None
    metal = fit(load(raw["metallic"], "L")) if "metallic" in raw else None
    if "orm" in raw:
        orm_src = fit(load(raw["orm"], "RGB")); ao = orm_src[..., 0] if ao is None else ao
        rough = orm_src[..., 1] if rough is None else rough; metal = orm_src[..., 2] if metal is None else metal
    if rough is None: raise StudioError(f"{c['id']} has no roughness map")
    ao = np.ones((h_, w_)) if ao is None else ao; metal = np.zeros((h_, w_)) if metal is None else metal
    outs = []; add = lambda path, role, fmt="png": outs.append({"path": path, "role": role, "format": fmt})
    ext = lambda b: "jpg" if b[:3] == b"\xff\xd8\xff" else "png"
    def keep(role, b, label):   # the library's own file, byte for byte (no recompression)
        path = ctx.path(f"{stem}_{role}.{ext(b)}"); open(path, "wb").write(b); add(path, label, "jpeg" if ext(b) == "jpg" else "png"); return path
    base = keep("basecolor", raw["basecolor"], "basecolor")
    nrm_path = None
    if nrm is not None:
        if want in raw: nrm_path = keep("normal", raw[want], f"normal ({p['normal_convention']})")
        else: nrm_path = _save(nrm, ctx.path(f"{stem}_normal.png")); add(nrm_path, f"normal ({p['normal_convention']}, converted)")
    add(_save(rough, ctx.path(f"{stem}_roughness.png")), "roughness")
    if "ao" in raw or "orm" in raw: add(_save(ao, ctx.path(f"{stem}_ao.png")), "ao")
    if "height" in raw: keep("height", raw["height"], "height")
    orm_path = _save(np.stack([ao, rough, metal], -1), ctx.path(f"{stem}_orm.png")); add(orm_path, "orm (R=AO G=roughness B=metallic, glTF)")
    add(_tile_preview(alb, ctx.path(f"{stem}_tiled2x2.png")), "preview")
    mat = {"name": stem, "source": {k: c.get(k) for k in ("source", "id", "name", "page", "authors")}, "license": SRC.LICENSE,
           "pbrMetallicRoughness": {"baseColorTexture": os.path.basename(base), "metallicRoughnessTexture": os.path.basename(orm_path), "metallicFactor": 1.0, "roughnessFactor": 1.0},
           "normalTexture": os.path.basename(nrm_path) if nrm_path else None, "occlusionTexture": os.path.basename(orm_path),
           "three": {"type": "MeshStandardMaterial", "map": f"{os.path.basename(base)} (SRGBColorSpace, RepeatWrapping)",
                     "normalMap": os.path.basename(nrm_path) if nrm_path else None, "roughnessMap": os.path.basename(orm_path),
                     "metalnessMap": os.path.basename(orm_path), "aoMap": os.path.basename(orm_path)},
           "averages": {"basecolor_srgb": [round(float(v), 3) for v in alb.reshape(-1, 3).mean(0)], "roughness": round(float(rough.mean()), 3), "metallic": round(float(metal.mean()), 3)}}
    jp = ctx.path(f"{stem}.material.json"); json.dump(mat, open(jp, "w"), indent=1); add(jp, "material", "json")
    sph = media.uv_sphere(1.0); sph.update(name=stem, material={"texture": base, "orm_texture": orm_path, "normal_texture": nrm_path})
    glb = media.write_glb(ctx.path(f"{stem}_sphere.glb"), [sph], name=stem); add(glb, "sample", "glb")
    shot = ctx.path(f"{stem}_render.png")
    checks, _, _ = webpages.glb_checks(glb, shot, "material sphere", size=(512, 512), camera=[0, 0.6, 2.9], target=[0, 0, 0], background="#3a3f47")
    ctx.used("three", "gltf_validator"); add(shot, "render")
    seams = {k: round(seam_score(v), 3) for k, v in (("basecolor", alb), ("roughness", rough)) + ((("normal", nrm),) if nrm is not None else ())}
    checks += [{"name": "tiles seamlessly (wrap step ≤ 1.5× the 99th-percentile ordinary step)", "ok": max(seams.values()) <= 1.5, "detail": seams},
               {"name": "maps decoded, in range and not flat", "ok": float(alb.std()) > 0.005 and 0 <= rough.min() <= rough.max() <= 1, "detail": {"maps": sorted(raw), "size": [w_, h_]}}]
    if nrm is not None:
        nv = nrm * 2 - 1; dev = float(np.abs(np.linalg.norm(nv, axis=-1) - 1).mean())
        checks.append({"name": "normal map vectors are unit length (JPEG tolerance)", "ok": dev < 0.1, "detail": round(dev, 4)})
    credit = f"{c.get('name') or c['id']} by {', '.join(c.get('authors') or ['unknown'])} ({c['page']}), CC0"
    return {"outputs": outs, "checks": checks, "material": mat, "candidates": short, "output_license": SRC.LICENSE, "attribution": credit}


ACTIONS = {"generate": generate, "seamless": seamless, "toon_ramp": toon_ramp, "library": library, "fetch": fetch}
