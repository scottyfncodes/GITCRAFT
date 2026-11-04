"""MaterialCraft: tileable PBR materials (numpy generators in materials.py), weathering, toon
styling, seamless-izing of existing images, toon ramps. Every material ships as a glTF 2.0
metallic-roughness map set, a sample sphere GLB with the maps embedded (loads in any engine), and is
rendered in three.js r170 and checked for seams before it is reported."""
import json, os, sys
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


ACTIONS = {"generate": generate, "seamless": seamless, "toon_ramp": toon_ramp, "library": library}
