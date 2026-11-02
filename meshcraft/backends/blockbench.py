"""Blockbench integration through its project format.

Blockbench (GPL-3.0, Electron/web app) has no headless mode, CLI or server API (upstream
issue #1764 is still open), so MeshCraft integrates at the file level:
  * write: stylized cube-built assets are authored as genuine `.bbmodel` projects
    (format 5.0, schema taken from Blockbench's js/formats/bbmodel.js) with an embedded
    pixel-art texture. Open them in Blockbench to keep editing by hand.
  * read: any `.bbmodel` (from these templates or made by a person in Blockbench) is
    converted by MeshCraft's Blender importer (blender/run.py import_bbmodel) and then runs
    through the normal clean → bake → preview → GLB/FBX/OBJ export stages.
Standard library only."""
import base64, json, os, random, struct, uuid, zlib

UNIT = 16  # Blockbench units per metre (one block = 16 px = 1 m)
PAL = {"timber": (154, 90, 46), "deep_timber": (94, 51, 27), "honey": (217, 149, 79), "gold": (244, 197, 66),
       "crimson": (192, 57, 43), "coral": (255, 107, 74), "cream": (246, 234, 208), "black": (27, 27, 31),
       "iron": (74, 79, 87), "sea": (26, 127, 168), "lagoon": (31, 181, 176), "amber": (255, 159, 46), "white": (244, 244, 240),
       "palm": (63, 165, 90), "sand": (247, 217, 160), "skin": (232, 180, 138)}


def png(w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b"")


# cube = (name, from[x,y,z], to[x,y,z], colour, origin?, rotation?)  units: Blockbench px, Y up, -Z = north = front
def _crate():
    c = [("box", [-8, 0, -8], [8, 16, 8], "honey")]
    for z in (-8.5, 7.5):
        c += [(f"slat_{z}", [-8, 3, z], [8, 5, z + 1], "deep_timber"), (f"slat2_{z}", [-8, 11, z], [8, 13, z + 1], "deep_timber")]
    return c


def _chest():
    return [("base", [-10, 0, -6], [10, 9, 6], "timber"), ("lid", [-10, 9, -6], [10, 14, 6], "crimson"),
            ("band_l", [-7, 0, -6.5], [-5, 14.5, 6.5], "gold"), ("band_r", [5, 0, -6.5], [7, 14.5, 6.5], "gold"),
            ("lock", [-1.5, 7, -7], [1.5, 11, -6], "gold")]


def _crab():
    c = [("body", [-6, 2, -5], [6, 7, 5], "coral"), ("shell_top", [-5, 7, -4], [5, 8, 4], "crimson")]
    for s in (-1, 1):
        c += [(f"eyestalk_{s}", [s * 2 - 0.5, 7, -5], [s * 2 + 0.5, 10, -4], "coral"), (f"eye_{s}", [s * 2 - 1, 10, -5.5], [s * 2 + 1, 12, -3.5], "black"),
              (f"arm_{s}", [min(s * 6, s * 9), 3, -6], [max(s * 6, s * 9), 5, -3], "coral"),
              (f"claw_{s}", [min(s * 8, s * 12), 2, -10], [max(s * 8, s * 12), 7, -5], "crimson"),
              (f"pincer_{s}", [min(s * 8, s * 10), 4, -12], [max(s * 8, s * 10), 6, -10], "crimson")]
        for i, z in enumerate((-2, 1, 4)):
            c.append((f"leg_{s}_{i}", [min(s * 6, s * 10), 0, z - 0.75], [max(s * 6, s * 10), 2, z + 0.75], "coral", [s * 6, 2, z], [0, 0, -20 * s]))
    return c


def _lantern():
    return [("base", [-4, 0, -4], [4, 2, 4], "iron"), ("glass", [-3, 2, -3], [3, 9, 3], "amber"), ("cap", [-4, 9, -4], [4, 11, 4], "iron"),
            ("handle", [-0.5, 11, -2], [0.5, 14, 2], "iron")] + [(f"bar_{i}", [x - 0.5, 2, z - 0.5], [x + 0.5, 9, z + 0.5], "iron")
                                                                   for i, (x, z) in enumerate([(-3, -3), (3, -3), (-3, 3), (3, 3)])]


def _dinghy():
    c = [("keel", [-8, 0, -32], [8, 4, 30], "timber"), ("deck", [-14, 4, -26], [14, 6, 26], "honey"),
         ("bow", [-6, 4, -38], [6, 10, -26], "timber"), ("stern", [-12, 6, 24], [12, 12, 28], "timber"),
         ("seat", [-12, 8, -2], [12, 10, 4], "deep_timber"), ("mast", [-1, 6, -12], [1, 60, -10], "deep_timber"),
         ("sail", [-0.5, 18, -9], [0.5, 56, 14], "cream"), ("stripe", [-0.75, 34, -9], [0.75, 40, 12], "crimson")]
    for s in (-1, 1):
        c.append((f"side_{s}", [min(s * 14, s * 16), 4, -26], [max(s * 14, s * 16), 12, 26], "sea"))
        c.append((f"rail_{s}", [min(s * 13, s * 17), 12, -24], [max(s * 13, s * 17), 13, 24], "gold"))
    return c


TEMPLATES = {"crate": _crate, "chest": _chest, "crab": _crab, "lantern": _lantern, "boat": _dinghy}


def template_for(req):
    p = req.get("params", {}); k = req.get("kind")
    if p.get("bb_template") in TEMPLATES: return p["bb_template"]
    if k == "boat": return "boat"
    if k == "prop": return {"crate": "crate", "chest": "chest", "barrel": "crate"}.get(p.get("prop"))
    if k == "salvage": return "crate"
    t = (req.get("brief") or "").lower()
    return next((n for n in TEMPLATES if n in t), None)


def build(template, name, out_path, seed=1):
    """Write a Blockbench project (.bbmodel) for `template`. Returns summary."""
    cubes = TEMPLATES[template]()
    rnd = random.Random(seed)
    cell = 16; cols = 8; rows = (len(cubes) + cols - 1) // cols
    W, H = cell * cols, cell * max(rows, 1)
    pix = bytearray(W * H * 4)
    elements = []
    for i, cube in enumerate(cubes):
        nm, f, t, colname = cube[:4]
        origin = cube[4] if len(cube) > 4 else [(a + b) / 2 for a, b in zip(f, t)]
        rot = cube[5] if len(cube) > 5 else None
        cx, cy = (i % cols) * cell, (i // cols) * cell
        r, g, b = PAL[colname]
        for y in range(cell):
            for x in range(cell):
                edge = x in (0, cell - 1) or y in (0, cell - 1)
                k = (0.82 if edge else 1.0) * rnd.uniform(0.9, 1.06)
                o = ((cy + y) * W + cx + x) * 4
                pix[o:o + 4] = bytes((min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), 255))
        uv = [cx + 0.5, cy + 0.5, cx + cell - 0.5, cy + cell - 0.5]
        el = {"name": nm, "box_uv": False, "rescale": False, "locked": False, "render_order": "default", "allow_mirror_modeling": True,
              "from": f, "to": t, "autouv": 0, "color": i % 8, "origin": origin,
              "faces": {d: {"uv": uv, "texture": 0} for d in ("north", "east", "south", "west", "up", "down")},
              "type": "cube", "uuid": str(uuid.uuid4())}
        if rot: el["rotation"] = rot
        elements.append(el)
    tex = {"path": "", "name": f"{name}_texture.png", "folder": "", "namespace": "", "id": "0", "width": W, "height": H,
           "uv_width": W, "uv_height": H, "particle": False, "use_as_default": False, "layers_enabled": False,
           "render_mode": "default", "render_sides": "auto", "frame_time": 1, "frame_order_type": "loop", "frame_order": "",
           "frame_interpolate": False, "visible": True, "internal": True, "saved": False, "uuid": str(uuid.uuid4()),
           "source": "data:image/png;base64," + base64.b64encode(png(W, H, pix)).decode()}
    group = {"name": name, "origin": [0, 0, 0], "color": 0, "uuid": str(uuid.uuid4()), "export": True, "mirror_uv": False,
             "isOpen": True, "locked": False, "visibility": True, "autouv": 0}
    model = {"meta": {"format_version": "5.0", "model_format": "free", "box_uv": False},
             "name": name, "model_identifier": "", "visible_box": [1, 1, 0], "variable_placeholders": "", "variable_placeholder_buttons": [],
             "timeline_setups": [], "unhandled_root_fields": {}, "resolution": {"width": W, "height": H},
             "elements": elements, "groups": [group],
             "outliner": [{"uuid": group["uuid"], "isOpen": True, "children": [e["uuid"] for e in elements]}],
             "textures": [tex]}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    json.dump(model, open(out_path, "w"), indent=1)
    return {"bbmodel": out_path, "template": template, "cubes": len(elements), "texture": [W, H]}


def inspect(path):
    """Read and sanity-check a .bbmodel (ours or one saved by Blockbench)."""
    d = json.load(open(path))
    meta = d.get("meta", {})
    els = d.get("elements", d.get("cubes", []))
    problems = []
    if "format_version" not in meta: problems.append("meta.format_version missing")
    for e in els:
        if e.get("type", "cube") == "cube" and not ("from" in e and "to" in e): problems.append(f"cube {e.get('name')} lacks from/to")
    tex = d.get("textures", [])
    return {"format_version": meta.get("format_version"), "model_format": meta.get("model_format"), "elements": len(els),
            "cubes": sum(1 for e in els if e.get("type", "cube") == "cube"), "meshes": sum(1 for e in els if e.get("type") == "mesh"),
            "textures": [{"name": t.get("name"), "embedded": str(t.get("source", "")).startswith("data:image"), "size": [t.get("width"), t.get("height")]} for t in tex],
            "animations": len(d.get("animations", [])), "problems": problems}
