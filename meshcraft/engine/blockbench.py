"""Blockbench projects (.bbmodel) for MeshCraft. Standard library only (no Blender needed).

Blockbench (GPL-3.0, github.com/JannisX11/blockbench) is an Electron/web app with no
headless mode, CLI or server API, so MeshCraft works with it at the file level:

  * build():   write a genuine Blockbench project (format 5.0, "free" model) from a cube
               template, with an embedded pixel texture coloured from the project's palette.
               Open it in Blockbench to keep editing by hand.
  * inspect(): read any .bbmodel (ours or one a person saved from Blockbench) and report its
               format, elements, textures, animations and problems.
  * importing a .bbmodel into Blender is engine/bbimport.py (needs bpy).

Units: 16 Blockbench px = 1 m (one block). Blockbench is Y-up with north = -Z = the front.
Ported from the 3D Department proposal (GITCRAFT PR #9) and made palette-driven.
"""
import base64, json, os, random, struct, uuid, zlib
try:
    from .palette import Palette
except ImportError:          # imported as a top-level module
    from palette import Palette

UNIT = 16
FORMAT_VERSION = "5.0"

# role -> default colour when the brief gives no palette / role mapping (TIDEBREAKERS-like warm set)
DEFAULT_ROLES = {"timber": "#9A5A2E", "deep_timber": "#5E331B", "honey": "#D9954F", "gold": "#F4C542", "crimson": "#C0392B",
                 "coral": "#FF6B4A", "cream": "#F6EAD0", "black": "#1B1B1F", "iron": "#4A4F57", "sea": "#1A7FA8",
                 "amber": "#FF9F2E"}

# cube = (name, from[x,y,z], to[x,y,z], role, origin?, rotation?) in Blockbench px
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


def _boat():
    c = [("keel", [-8, 0, -32], [8, 4, 30], "timber"), ("deck", [-14, 4, -26], [14, 6, 26], "honey"),
         ("bow", [-6, 4, -38], [6, 10, -26], "timber"), ("stern", [-12, 6, 24], [12, 12, 28], "timber"),
         ("seat", [-12, 8, -2], [12, 10, 4], "deep_timber"), ("mast", [-1, 6, -12], [1, 60, -10], "deep_timber"),
         ("sail", [-0.5, 18, -9], [0.5, 56, 14], "cream"), ("stripe", [-0.75, 34, -9], [0.75, 40, 12], "crimson")]
    for s in (-1, 1):
        c.append((f"side_{s}", [min(s * 14, s * 16), 4, -26], [max(s * 14, s * 16), 12, 26], "sea"))
        c.append((f"rail_{s}", [min(s * 13, s * 17), 12, -24], [max(s * 13, s * 17), 13, 24], "gold"))
    return c


def _south(fn):
    """Templates are written front-to-north; mirror them so the front faces south (+Z), which is the
    front in glTF / three.js once Blockbench coordinates are exported (and -Y in Blender)."""
    def mirrored():
        out = []
        for c in fn():
            nm, f, t, role = c[:4]
            m = [nm, [f[0], f[1], -t[2]], [t[0], t[1], -f[2]], role]
            if len(c) > 4: m.append([c[4][0], c[4][1], -c[4][2]])
            if len(c) > 5: m.append([-c[5][0], -c[5][1], c[5][2]])
            out.append(tuple(m))
        # centre the footprint on the origin (x/z), keep the base on y = 0
        xs = [v for c in out for v in (c[1][0], c[2][0])]; zs = [v for c in out for v in (c[1][2], c[2][2])]
        dx, dz = -(min(xs) + max(xs)) / 2, -(min(zs) + max(zs)) / 2
        sh = lambda p: [p[0] + dx, p[1], p[2] + dz]
        return [tuple([c[0], sh(c[1]), sh(c[2]), c[3]] + ([sh(c[4])] if len(c) > 4 else []) + list(c[5:])) for c in out]
    return mirrored


TEMPLATES = {k: _south(f) for k, f in {"crate": _crate, "chest": _chest, "crab": _crab, "lantern": _lantern, "boat": _boat}.items()}


def list_templates():
    out = []
    for k, fn in TEMPLATES.items():
        cubes = fn()
        out.append({"id": k, "cubes": len(cubes), "roles": sorted({c[3] for c in cubes})})
    return out


def _png(w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b"")


def _rgb(hx):
    hx = hx.lstrip("#"); return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def resolve_roles(template, palette=None, roles=None):
    """role -> '#RRGGBB'. `roles` maps a role to a palette name or hex; a palette alone keeps the defaults."""
    pal = Palette.from_file(palette) if palette else Palette({})
    used = {c[3] for c in TEMPLATES[template]()}
    out = {}
    for r in sorted(used):
        ref = (roles or {}).get(r)
        out[r] = pal.get(ref) if ref else DEFAULT_ROLES[r]
    return out


def build(template, out_path, name=None, palette=None, roles=None, seed=1):
    """Write a Blockbench project (.bbmodel) for `template`. Deterministic for a given seed."""
    if template not in TEMPLATES: raise ValueError(f"unknown Blockbench template {template!r}; have {sorted(TEMPLATES)}")
    name = name or template
    colours = resolve_roles(template, palette, roles)
    cubes = TEMPLATES[template]()
    rnd = random.Random(seed)
    cell = 16; cols = 8; rows = (len(cubes) + cols - 1) // cols
    W, H = cell * cols, cell * max(rows, 1)
    pix = bytearray(W * H * 4)
    elements = []
    for i, cube in enumerate(cubes):
        nm, f, t, role = cube[:4]
        origin = cube[4] if len(cube) > 4 else [(a + b) / 2 for a, b in zip(f, t)]
        rot = cube[5] if len(cube) > 5 else None
        cx, cy = (i % cols) * cell, (i // cols) * cell
        r, g, b = _rgb(colours[role])
        for y in range(cell):          # one hand-painted 16 px cell per cube: darker rim, slight noise
            for x in range(cell):
                edge = x in (0, cell - 1) or y in (0, cell - 1)
                k = (0.82 if edge else 1.0) * rnd.uniform(0.92, 1.05)
                o = ((cy + y) * W + cx + x) * 4
                pix[o:o + 4] = bytes((min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), 255))
        uv = [cx + 0.5, cy + 0.5, cx + cell - 0.5, cy + cell - 0.5]
        el = {"name": nm, "box_uv": False, "rescale": False, "locked": False, "render_order": "default", "allow_mirror_modeling": True,
              "from": f, "to": t, "autouv": 0, "color": i % 8, "origin": origin,
              "faces": {d: {"uv": uv, "texture": 0} for d in ("north", "east", "south", "west", "up", "down")},
              "type": "cube", "uuid": str(uuid.UUID(int=rnd.getrandbits(128), version=4)), "gitcraft_role": role}
        if rot: el["rotation"] = rot
        elements.append(el)
    tex = {"path": "", "name": f"{name}_texture.png", "folder": "", "namespace": "", "id": "0", "width": W, "height": H,
           "uv_width": W, "uv_height": H, "particle": False, "use_as_default": False, "layers_enabled": False,
           "render_mode": "default", "render_sides": "auto", "frame_time": 1, "frame_order_type": "loop", "frame_order": "",
           "frame_interpolate": False, "visible": True, "internal": True, "saved": False, "uuid": str(uuid.UUID(int=rnd.getrandbits(128), version=4)),
           "source": "data:image/png;base64," + base64.b64encode(_png(W, H, pix)).decode()}
    group = {"name": name, "origin": [0, 0, 0], "color": 0, "uuid": str(uuid.UUID(int=rnd.getrandbits(128), version=4)), "export": True,
             "mirror_uv": False, "isOpen": True, "locked": False, "visibility": True, "autouv": 0}
    model = {"meta": {"format_version": FORMAT_VERSION, "model_format": "free", "box_uv": False},
             "name": name, "model_identifier": "", "visible_box": [1, 1, 0], "variable_placeholders": "", "variable_placeholder_buttons": [],
             "timeline_setups": [], "unhandled_root_fields": {}, "resolution": {"width": W, "height": H},
             "elements": elements, "groups": [group],
             "outliner": [{"uuid": group["uuid"], "isOpen": True, "children": [e["uuid"] for e in elements]}],
             "textures": [tex], "gitcraft": {"tool": "MeshCraft", "template": template, "roles": colours}}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as fh: json.dump(model, fh, indent=1)
    return {"bbmodel": out_path, "template": template, "cubes": len(elements), "texture": [W, H], "roles": colours,
            "bytes": os.path.getsize(out_path)}


def inspect(path):
    """Read and sanity-check a .bbmodel (ours or one saved by Blockbench)."""
    with open(path) as fh: d = json.load(fh)
    if not isinstance(d, dict) or not ("meta" in d or "elements" in d or "cubes" in d):
        raise ValueError("not a Blockbench project: a .bbmodel has `meta` and `elements` at the top level")
    meta = d.get("meta", {})
    els = d.get("elements", d.get("cubes", []))
    problems = []
    if "format_version" not in meta: problems.append("meta.format_version missing")
    for e in els:
        if e.get("type", "cube") == "cube" and not ("from" in e and "to" in e): problems.append(f"cube {e.get('name')} lacks from/to")
    tex = d.get("textures", [])
    if not tex: problems.append("no textures: faces will import untextured")
    for t in tex:
        if not str(t.get("source", "")).startswith("data:image") and not t.get("path"):
            problems.append(f"texture {t.get('name')} is neither embedded nor linked")
    return {"format_version": meta.get("format_version"), "model_format": meta.get("model_format"), "name": d.get("name"),
            "elements": len(els), "cubes": sum(1 for e in els if e.get("type", "cube") == "cube"),
            "meshes": sum(1 for e in els if e.get("type") == "mesh"),
            "textures": [{"name": t.get("name"), "embedded": str(t.get("source", "")).startswith("data:image"),
                          "size": [t.get("width"), t.get("height")]} for t in tex],
            "animations": [a.get("name") for a in d.get("animations", [])], "problems": problems}
