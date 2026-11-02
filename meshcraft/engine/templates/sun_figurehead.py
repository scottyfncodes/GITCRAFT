"""The Grinning Sun, carved as a ship's bow figurehead (the TIDEBREAKERS emblem in 3D).

Contract: root `figurehead` with its origin at the mounting point on the bow
(back of the bracket); the face looks along +Z in Three.js (-Y in Blender).
"""
import math
from .. import kit

META = {"id": "sun_figurehead", "title": "Grinning Sun figurehead", "category": "ship component",
        "description": "Gap-toothed, eye-patched sun with flame rays on a timber bow bracket, built from the 2D emblem's proportions.",
        "params": {"diameter": {"type": "number", "default": 0.9}, "rays": {"type": "integer", "default": 12}, "tilt_deg": {"type": "number", "default": 12}},
        "roles": ["face", "rays", "ink", "tooth", "cheek", "bracket", "eye_hi"], "budget_tris": 8000}


def default_roles(params):
    return {"face": "Doubloon Gold", "rays": "Sunlit Amber", "ink": "Deep Tide", "tooth": "Sailcloth Cream", "cheek": "Hibiscus",
            "bracket": "Timber", "eye_hi": "#FFFFFF"}


def build(ctx):
    p = ctx.params; M = ctx.mats; R = p["diameter"] / 2 * 0.62      # face radius (rays reach the diameter)
    root = kit.empty("figurehead", (0, 0, 0), kind="SINGLE_ARROW", size=0.2)
    cz = R * 1.65; fy = -R * 0.45          # face centre height, face plane (front = -Y)
    parts = []
    parts.append(kit.cylinder("face", R, R * 0.32, (0, fy + R * 0.16, cz), axis="Y", verts=28, mat=M["face"], bevel=R * 0.06, segs=2))
    parts.append(kit.cylinder("rim", R * 1.04, R * 0.2, (0, fy + R * 0.26, cz), axis="Y", verts=28, mat=M["rays"]))
    n = p["rays"]
    for i in range(n):
        a = 2 * math.pi * i / n + math.pi / 2
        L = R * (1.62 if i % 2 == 0 else 1.38); w = math.radians(15 if i % 2 == 0 else 12)
        b0 = (math.cos(a - w) * R * 0.92, math.sin(a - w) * R * 0.92); b1 = (math.cos(a + w) * R * 0.92, math.sin(a + w) * R * 0.92)
        mid = (math.cos(a + w * 0.4) * (R + (L - R) * 0.55), math.sin(a + w * 0.4) * (R + (L - R) * 0.55))  # flame curl
        tip = (math.cos(a) * L, math.sin(a) * L)
        parts.append(kit.prism("ray", [b0, mid, tip, b1], R * 0.18, (0, fy + R * 0.3, cz), axis="Y", mat=M["rays"], bevel=R * 0.02))
    fz = fy - R * 0.02
    # open eye (viewer's right = +X) with highlight, raised brow
    ex, ez = R * 0.36, cz + R * 0.1
    parts.append(kit.sphere("eye", R * 0.14, (ex, fz, ez), M["ink"], segs=12, rings=8, scale=(0.85, 0.45, 1.15)))
    parts.append(kit.sphere("eye_hi", R * 0.045, (ex - R * 0.04, fz - R * 0.06, ez + R * 0.06), M["eye_hi"], segs=8, rings=5))
    parts.append(kit.torus("brow", R * 0.2, R * 0.03, (ex, fz + R * 0.02, ez + R * 0.12), axis="Y", mat=M["ink"], major=16, minor=5))
    # eyepatch + strap
    parts.append(kit.sphere("patch", R * 0.2, (-R * 0.36, fz, cz + R * 0.1), M["ink"], segs=14, rings=8, scale=(1.1, 0.35, 0.9)))
    parts.append(kit.prism("strap", [(-R * 0.97, R * 0.2), (R * 0.95, R * 0.5), (R * 0.93, R * 0.6), (-R * 0.99, R * 0.3)], R * 0.06, (0, fz + R * 0.05, cz), axis="Y", mat=M["ink"]))
    # crooked grin + gold tooth + cheeks
    low = [(math.cos(t) * R * 0.5, math.sin(t) * R * 0.36 - R * 0.2) for t in [math.pi + k * math.pi / 12 for k in range(13)]]
    up = [(math.cos(t) * R * 0.5, math.sin(t) * R * 0.1 - R * 0.2) for t in [2 * math.pi - k * math.pi / 12 for k in range(1, 12)]]
    grin = [(x, z + x * 0.22) for x, z in low + up]  # crooked: the right side lifts
    parts.append(kit.prism("grin", grin, R * 0.1, (0, fz, cz), axis="Y", mat=M["ink"]))
    parts.append(kit.box("tooth", (R * 0.13, R * 0.08, R * 0.13), (R * 0.12, fz - R * 0.03, cz - R * 0.33), M["tooth"], bevel=R * 0.02, segs=1))
    for sx in (-1, 1):
        parts.append(kit.cylinder("cheek", R * 0.15, R * 0.04, (sx * R * 0.6, fz + R * 0.03, cz - R * 0.18), axis="Y", verts=14, mat=M["cheek"]))
    # timber bow bracket behind (mounting point at origin)
    parts.append(kit.box("bracket", (R * 0.7, R * 0.5, R * 1.3), (0, R * 0.25, R * 0.8), M["bracket"], bevel=R * 0.06, segs=2, taper=0.15))
    parts.append(kit.cylinder("bracket_scroll", R * 0.22, R * 0.6, (0, R * 0.05, R * 0.22), axis="X", verts=12, mat=M["bracket"]))
    body = kit.join(parts, "figurehead_mesh"); kit.shade(body, smooth_angle=35); body.parent = root
    root.rotation_euler = (math.radians(-p["tilt_deg"]), 0, 0)
    return {"root": root, "expect": {"base_z": None, "centered": True},
            "contract": {"nodes": {"root": "figurehead", "mesh": "figurehead_mesh"}, "origin": "mounting point on the bow; face looks +Z"}}
