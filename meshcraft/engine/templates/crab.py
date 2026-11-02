"""Biscuit, the teacup hermit crab: a small rigged character (skeletal animation demo).

Contract: root `biscuit` at the saucer base; armature `biscuit_rig` with bones
root, body, eye_L, eye_R, arm_L, claw_L, arm_R, claw_R; one skinned mesh
`biscuit_mesh` (rigid parts, one bone each); clips `idle` (loop), `wave`, `snap`.
"""
import math
from .. import kit

META = {"id": "crab", "title": "Biscuit the teacup crab (rigged)", "category": "character",
        "description": "Mascot from the TIDEBREAKERS cast: crab in a teacup, 8-bone rig, idle / wave / snap clips.",
        "params": {"scale": {"type": "number", "default": 0.6, "description": "overall height in metres"}},
        "roles": ["shell", "shell_dark", "cup", "cup_band", "eye", "pupil", "saucer"], "budget_tris": 6000}


def default_roles(params):
    return {"shell": "Coral Flame", "shell_dark": "#C4472A", "cup": "Sailcloth Cream", "cup_band": "Hibiscus", "eye": "#FFFFFF",
            "pupil": "Deep Tide", "saucer": "Sailcloth Cream"}


def build(ctx):
    M = ctx.mats; s = ctx.params["scale"] / 0.6
    root = kit.empty("biscuit", (0, 0, 0), kind="PLAIN_AXES", size=0.1)
    parts = []
    # teacup (root bone) + saucer + handle
    parts.append(kit.tag(kit.cylinder("saucer", 0.26 * s, 0.03 * s, (0, 0, 0.015 * s), verts=24, mat=M["saucer"], r2=0.2 * s), "root"))
    parts.append(kit.tag(kit.cylinder("cup", 0.2 * s, 0.22 * s, (0, 0, 0.14 * s), verts=24, mat=M["cup"], r2=0.14 * s), "root"))
    parts.append(kit.tag(kit.cylinder("cup_band", 0.198 * s, 0.035 * s, (0, 0, 0.2 * s), verts=24, mat=M["cup_band"], r2=0.19 * s), "root"))
    for a in (0.4, 1.6, 2.8, 4.0, 5.2):
        parts.append(kit.tag(kit.sphere("dot", 0.022 * s, (math.cos(a) * 0.17 * s, math.sin(a) * 0.17 * s, 0.12 * s), M["cup_band"], segs=8, rings=5, scale=(1, 1, 1)), "root"))
    parts.append(kit.tag(kit.torus("handle", 0.07 * s, 0.018 * s, (0.21 * s, 0, 0.15 * s), axis="Y", mat=M["cup"], major=14, minor=5), "root"))
    # body: shell dome peeking out of the cup
    parts.append(kit.tag(kit.sphere("shell", 0.17 * s, (0, 0, 0.25 * s), M["shell"], segs=16, rings=10, scale=(1, 0.9, 0.7)), "body"))
    smile = [(math.cos(t) * 0.05 * s, math.sin(t) * 0.035 * s) for t in [math.pi + k * math.pi / 8 for k in range(9)]]
    smile += [(math.cos(t) * 0.05 * s, math.sin(t) * 0.012 * s) for t in [2 * math.pi - k * math.pi / 8 for k in range(1, 8)]]
    parts.append(kit.tag(kit.prism("smile", smile, 0.02 * s, (0, -0.15 * s, 0.25 * s), axis="Y", mat=M["pupil"]), "body"))
    for side, sx in (("L", 1), ("R", -1)):
        # eye stalks
        parts.append(kit.tag(kit.cylinder(f"stalk_{side}", 0.018 * s, 0.14 * s, (sx * 0.07 * s, -0.02 * s, 0.37 * s), verts=8, mat=M["shell"]), f"eye_{side}"))
        parts.append(kit.tag(kit.sphere(f"eye_{side}", 0.05 * s, (sx * 0.07 * s, -0.03 * s, 0.46 * s), M["eye"], segs=12, rings=8), f"eye_{side}"))
        parts.append(kit.tag(kit.sphere(f"pupil_{side}", 0.025 * s, (sx * 0.07 * s, -0.07 * s, 0.465 * s), M["pupil"], segs=8, rings=6), f"eye_{side}"))
        # arms + pincers
        parts.append(kit.tag(kit.cylinder(f"arm_{side}", 0.028 * s, 0.16 * s, (sx * 0.2 * s, -0.02 * s, 0.3 * s), axis="X", verts=8, mat=M["shell"]), f"arm_{side}"))
        parts.append(kit.tag(kit.sphere(f"claw_{side}", 0.075 * s, (sx * 0.32 * s, -0.02 * s, 0.34 * s), M["shell"], segs=12, rings=8, scale=(1.1, 0.7, 0.85)), f"claw_{side}"))
        parts.append(kit.tag(kit.prism(f"pincer_{side}", [(0, 0), (0.09 * s, 0.03 * s), (0.08 * s, -0.01 * s), (0.01 * s, -0.03 * s)], 0.05 * s,
                                       (sx * 0.36 * s if sx > 0 else -0.45 * s, -0.02 * s, 0.38 * s), axis="Y", mat=M["shell_dark"]), f"claw_{side}"))
        for k in range(2):
            parts.append(kit.tag(kit.cylinder(f"leg_{side}{k}", 0.014 * s, 0.1 * s, (sx * 0.19 * s, (0.04 - k * 0.08) * s, 0.22 * s), axis="X", verts=6, mat=M["shell_dark"]), "body"))
    mesh = kit.join(parts, "biscuit_mesh"); kit.shade(mesh, 40)
    B = lambda x, y, z: (x * s, y * s, z * s)
    arm = kit.armature("biscuit_rig", [
        ("root", B(0, 0, 0), B(0, 0, 0.12), None),
        ("body", B(0, 0, 0.2), B(0, 0, 0.32), "root"),
        ("eye_L", B(0.07, -0.02, 0.32), B(0.07, -0.02, 0.48), "body"),
        ("eye_R", B(-0.07, -0.02, 0.32), B(-0.07, -0.02, 0.48), "body"),
        ("arm_L", B(0.12, -0.02, 0.3), B(0.27, -0.02, 0.32), "body"),
        ("claw_L", B(0.27, -0.02, 0.32), B(0.4, -0.02, 0.38), "arm_L"),
        ("arm_R", B(-0.12, -0.02, 0.3), B(-0.27, -0.02, 0.32), "body"),
        ("claw_R", B(-0.27, -0.02, 0.32), B(-0.4, -0.02, 0.38), "arm_R"),
    ], parent=root)
    kit.skin_rigid(mesh, arm, {b: b for b in ("root", "body", "eye_L", "eye_R", "arm_L", "claw_L", "arm_R", "claw_R")})
    r = math.radians
    kit.pose_keyframes(arm, "idle", {1: {"body": {"loc": (0, 0, 0)}, "eye_L": {"rot": (0, 0, 0)}, "eye_R": {"rot": (0, 0, 0)}},
                                     31: {"body": {"loc": (0, 0.02 * s, 0)}, "eye_L": {"rot": (0, r(8), 0)}, "eye_R": {"rot": (0, r(-8), 0)}},
                                     61: {"body": {"loc": (0, 0, 0)}, "eye_L": {"rot": (0, 0, 0)}, "eye_R": {"rot": (0, 0, 0)}}})
    # Bone Y runs along the bone (twist); +X lifts the arm/claw tip on both sides (measured), Z swings it sideways.
    up = r(70)
    kit.pose_keyframes(arm, "wave", {1: {"arm_L": {"rot": (0, 0, 0)}, "claw_L": {"rot": (0, 0, 0)}},
                                     8: {"arm_L": {"rot": (up, 0, 0)}, "claw_L": {"rot": (r(20), 0, r(-30))}},
                                     14: {"arm_L": {"rot": (up, 0, 0)}, "claw_L": {"rot": (r(20), 0, r(30))}},
                                     20: {"arm_L": {"rot": (up, 0, 0)}, "claw_L": {"rot": (r(20), 0, r(-30))}},
                                     26: {"arm_L": {"rot": (up, 0, 0)}, "claw_L": {"rot": (r(20), 0, r(30))}},
                                     34: {"arm_L": {"rot": (0, 0, 0)}, "claw_L": {"rot": (0, 0, 0)}}})
    kit.pose_keyframes(arm, "snap", {1: {"arm_L": {"rot": (0, 0, 0)}, "arm_R": {"rot": (0, 0, 0)}, "claw_L": {"rot": (0, 0, 0)}, "claw_R": {"rot": (0, 0, 0)}},
                                     5: {"arm_L": {"rot": (r(25), 0, 0)}, "arm_R": {"rot": (r(25), 0, 0)}, "claw_L": {"rot": (r(40), 0, 0)}, "claw_R": {"rot": (r(40), 0, 0)}},
                                     9: {"arm_L": {"rot": (r(10), 0, 0)}, "arm_R": {"rot": (r(10), 0, 0)}, "claw_L": {"rot": (r(-10), 0, 0)}, "claw_R": {"rot": (r(-10), 0, 0)}},
                                     13: {"arm_L": {"rot": (r(25), 0, 0)}, "arm_R": {"rot": (r(25), 0, 0)}, "claw_L": {"rot": (r(40), 0, 0)}, "claw_R": {"rot": (r(40), 0, 0)}},
                                     17: {"arm_L": {"rot": (0, 0, 0)}, "arm_R": {"rot": (0, 0, 0)}, "claw_L": {"rot": (0, 0, 0)}, "claw_R": {"rot": (0, 0, 0)}}})
    return {"root": root, "expect": {"base_z": 0.0, "centered": True},
            "contract": {"nodes": {"root": "biscuit", "rig": "biscuit_rig", "mesh": "biscuit_mesh"}, "clips": ["idle", "wave", "snap"],
                         "bones": ["root", "body", "eye_L", "eye_R", "arm_L", "claw_L", "arm_R", "claw_R"]}}
