"""Skinned flag on a pole (skeletal animation demo; canon TIDEBREAKERS flag designs).

Contract: root `flag` at the pole base; `flag_pole` (static mesh), `flag_rig`
(armature, bones flag_0..flag_3 along the fly), `flag_cloth` (skinned mesh);
clip `wave` loops. Designs: tidebreaker (navy, cream sun, lagoon wave stripe),
harbor (Saltwhistle Pennant), wren (Colors of the Wren).
"""
import math
import bmesh
from mathutils import Vector
from .. import kit

META = {"id": "flag", "title": "Skinned flag on a pole", "category": "ship component",
        "description": "Swallowtail flag on a 4-bone chain with a looping wave clip; designs from the TIDEBREAKERS cosmetics.",
        "params": {"design": {"type": "string", "enum": ["tidebreaker", "harbor", "wren"], "default": "tidebreaker"},
                   "width": {"type": "number", "default": 1.2}, "height": {"type": "number", "default": 0.75},
                   "pole": {"type": "number", "default": 2.2}, "wave_seconds": {"type": "number", "default": 1.2}},
        "roles": ["field", "emblem", "stripe", "pole", "finial"], "budget_tris": 4000}

DESIGNS = {"tidebreaker": {"field": "Deep Tide", "emblem": "Sailcloth Cream", "stripe": "Lagoon Teal"},
           "harbor": {"field": "#3A86FF", "emblem": "#FFFFFF", "stripe": "#FFFFFF"},
           "wren": {"field": "#1C1C22", "emblem": "#EFE6D2", "stripe": "#1C1C22"}}


def default_roles(params):
    return {**DESIGNS[params.get("design", "tidebreaker")], "pole": "Timber", "finial": "Doubloon Gold"}


def build(ctx):
    p = ctx.params; M = ctx.mats; W, H, P = p["width"], p["height"], p["pole"]; design = p["design"]
    root = kit.empty("flag", (0, 0, 0), kind="PLAIN_AXES", size=0.2)
    pole = kit.join([kit.cylinder("pole", 0.03, P, (0, 0, P / 2), verts=10, mat=M["pole"]),
                     kit.sphere("finial", 0.06, (0, 0, P + 0.04), M["finial"], segs=10, rings=6)], "flag_pole")
    kit.shade(pole, 40); pole.parent = root
    # cloth: grid in the XZ plane, top edge at the pole top, fly to +X; swallowtail notch at the fly
    nx, nz = 36, 20; z0 = P - 0.05 - H
    bm = bmesh.new(); grid = [[bm.verts.new((W * i / nx + 0.035, 0, z0 + H * j / nz)) for j in range(nz + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            cx = (i + 0.5) / nx; cz = (j + 0.5) / nz
            if design != "harbor" and cx > 0.82 and abs(cz - 0.5) < (cx - 0.82) * 1.9: continue  # swallowtail notch
            if design == "harbor" and abs(cz - 0.5) > 0.5 - 0.5 * cx * 0.9: continue           # pennant taper
            f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            role = "field"
            if design == "tidebreaker":
                if cz < 0.2: role = "stripe"
                else:
                    dx, dz = (cx - 0.38) * W / H, cz - 0.58           # sun disc + 8 flame rays, in flag-height units
                    d, a = math.hypot(dx, dz), math.atan2(dz, dx)
                    if d < 0.13 or (d < 0.24 and math.cos(8 * a) > 0.55 - (0.24 - d) * 2): role = "emblem"
            elif design == "harbor" and 0.38 < cz < 0.62: role = "stripe"
            elif design == "wren":
                dx, dz = (cx - 0.42) * W / H, cz - 0.55
                if (dx / 0.24) ** 2 + (dz / 0.13) ** 2 < 1 or (-0.4 < dx < -0.2 and abs(dz - 0.04 + (dx + 0.2) * 0.6) < 0.05): role = "emblem"  # wren body + tail
            f.material_index = ["field", "emblem", "stripe"].index(role)
    for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
    me = bpy_mesh = None
    import bpy
    me = bpy.data.meshes.new("flag_cloth"); bm.to_mesh(me); bm.free()
    cloth = kit.link(bpy.data.objects.new("flag_cloth", me))
    for r in ("field", "emblem", "stripe"): cloth.data.materials.append(M[r])
    sol = cloth.modifiers.new("solidify", "SOLIDIFY"); sol.thickness = 0.012; kit.apply_modifiers(cloth)
    kit.shade(cloth, 50)
    chain = [f"flag_{i}" for i in range(4)]
    zc = z0 + H / 2
    arm = kit.armature("flag_rig", [(chain[i], (W * i / 4 + 0.035, 0, zc), (W * (i + 1) / 4 + 0.035, 0, zc), chain[i - 1] if i else None) for i in range(4)], parent=root)
    kit.skin_gradient(cloth, arm, chain, axis=0, start=0.035, length=W)
    fps = 30; T = round(p["wave_seconds"] * fps)
    frames = {}
    for k in range(5):
        ph = 2 * math.pi * k / 4
        frames[1 + T * k / 4] = {b: {"rot": (0.06 * math.sin(ph + i * 1.1), 0.0, 0.32 * math.sin(ph + i * 1.25) * (0.5 + i * 0.25))} for i, b in enumerate(chain)}
    kit.pose_keyframes(arm, "wave", frames)
    return {"root": root, "expect": {"base_z": 0.0, "centered": False},
            "contract": {"nodes": {"root": "flag", "pole": "flag_pole", "rig": "flag_rig", "cloth": "flag_cloth"}, "clips": ["wave"],
                         "bones": chain, "origin": "pole base"}}
