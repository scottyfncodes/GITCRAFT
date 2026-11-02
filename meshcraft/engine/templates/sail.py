"""Square sail with a wind 'billow' morph target (TIDEBREAKERS cosmetic sail patterns).

Contract: root `sail` origin at the yard centre; `sail_yard` (static), `sail_cloth`
(mesh with shape key/morph target `billow`, 0 = slack, 1 = full); clip `fill`
(0 → 1) and `luff` (loop). Games can also drive the morph weight from wind.
"""
import math
import bmesh
from .. import kit

META = {"id": "sail", "title": "Square sail with billow morph", "category": "ship component",
        "description": "Yard + square sail; patterns plain / stripe / sunset / shells from the canon cosmetics; `billow` morph target for wind.",
        "params": {"pattern": {"type": "string", "enum": ["plain", "stripe", "sunset", "shells"], "default": "stripe"},
                   "width": {"type": "number", "default": 2.4}, "height": {"type": "number", "default": 1.9},
                   "billow": {"type": "number", "default": 0.45, "description": "metres of belly at full wind"}},
        "roles": ["cloth", "accent", "yard", "rope"], "budget_tris": 4000}

PATTERNS = {"plain": ("#F1E6CC", "#F1E6CC"), "stripe": ("#F1E6CC", "#C0392B"), "sunset": ("#FFCF7A", "#FF6B4A"), "shells": ("#F1E6CC", "#E0607E")}


def default_roles(params):
    c, a = PATTERNS[params.get("pattern", "stripe")]
    return {"cloth": c, "accent": a, "yard": "Timber", "rope": "Honey Timber"}


def build(ctx):
    import bpy
    p = ctx.params; M = ctx.mats; W, H = p["width"], p["height"]; pat = p["pattern"]
    root = kit.empty("sail", (0, 0, 0), kind="PLAIN_AXES", size=0.2)
    yard = kit.join([kit.cylinder("yard", 0.05, W * 1.12, (0, 0, 0), axis="X", verts=10, mat=M["yard"]),
                     kit.sphere("yard_end", 0.07, (W * 0.56, 0, 0), M["rope"], segs=8, rings=5),
                     kit.sphere("yard_end", 0.07, (-W * 0.56, 0, 0), M["rope"], segs=8, rings=5)], "sail_yard")
    kit.shade(yard, 40); yard.parent = root
    nx, nz = 14, 12
    bm = bmesh.new()
    g = [[bm.verts.new(((i / nx - 0.5) * W * (1 - 0.08 * (j / nz)), 0, -0.06 - H * (j / nz))) for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            f = bm.faces.new((g[i][j], g[i][j + 1], g[i + 1][j + 1], g[i + 1][j]))
            u, v = (i + 0.5) / nx, (j + 0.5) / nz; role = "cloth"
            if pat == "stripe" and 0.42 < v < 0.6: role = "accent"
            elif pat == "sunset" and (0.2 < v < 0.33 or 0.58 < v < 0.72): role = "accent"
            elif pat == "shells" and ((i + (j // 3) % 2) % 3 == 1 and j % 3 == 1): role = "accent"
            f.material_index = 0 if role == "cloth" else 1
    me = bpy.data.meshes.new("sail_cloth"); bm.to_mesh(me); bm.free()
    cloth = kit.link(bpy.data.objects.new("sail_cloth", me), root)
    cloth.data.materials.append(M["cloth"]); cloth.data.materials.append(M["accent"])
    sol = cloth.modifiers.new("solidify", "SOLIDIFY"); sol.thickness = 0.015; kit.apply_modifiers(cloth)
    kit.shade(cloth, 60)
    cloth.shape_key_add(name="Basis")
    sk = cloth.shape_key_add(name="billow", from_mix=False)
    for i, v in enumerate(cloth.data.vertices):
        x, z = v.co.x, v.co.z
        u = (x / (W / 2)); t = (-z - 0.06) / H                    # u -1..1 across, t 0 (yard) .. 1 (foot)
        belly = p["billow"] * (1 - u * u) * math.sin(math.pi * min(1, max(0, t)) * 0.9 + 0.15)
        sk.data[i].co = (x * (1 - 0.04 * belly), v.co.y - belly, z + 0.08 * belly * t)
    keyb = cloth.data.shape_keys
    def morph_clip(name, keys):
        if keyb.animation_data is None: keyb.animation_data_create()
        act = bpy.data.actions.new(name); keyb.animation_data.action = act
        for f, val in keys:
            keyb.key_blocks["billow"].value = val; keyb.key_blocks["billow"].keyframe_insert("value", frame=f)
        act.use_fake_user = True
        tr = keyb.animation_data.nla_tracks.new(); tr.name = name; st = tr.strips.new(name, int(keys[0][0]), act); tr.mute = True
        keyb.animation_data.action = None; keyb.key_blocks["billow"].value = 0.0
    morph_clip("fill", [(1, 0.0), (19, 1.0)])
    morph_clip("luff", [(1, 1.0), (16, 0.72), (31, 1.0)])
    return {"root": root, "expect": {"top_z": None, "centered": True},
            "contract": {"ground": False, "nodes": {"root": "sail", "yard": "sail_yard", "cloth": "sail_cloth"}, "clips": ["fill", "luff"], "morph_targets": ["billow"],
                         "origin": "yard centre; cloth hangs down -Y, belly toward +Z (downwind = forward)"}}
