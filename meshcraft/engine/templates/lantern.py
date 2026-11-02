"""Ship lantern that hangs from its hook and swings.

Contract: root `lantern` origin at the hang point (top of the hook), the lantern
hangs down -Y in Three.js; mesh `lantern_body`; empty `lantern_light` at the
flame (attach a PointLight there); clip `swing` loops (first frame = last).
"""
import math
from .. import kit

META = {"id": "lantern", "title": "Hanging ship lantern", "category": "ship component",
        "description": "Brass-framed hexagonal lantern with navy cap, emissive amber glass and flame, hook ring; looping swing clip.",
        "params": {"height": {"type": "number", "default": 0.42}, "sides": {"type": "integer", "default": 6},
                   "swing_deg": {"type": "number", "default": 9}, "swing_seconds": {"type": "number", "default": 2.0}},
        "roles": ["cap", "frame", "glass", "flame", "base"], "budget_tris": 3000}


def default_roles(params):
    return {"cap": "Deep Tide", "frame": "Gold Deep", "glass": "Sunlit Amber", "flame": "Sailcloth Cream", "base": "Deep Tide"}


def build(ctx):
    p = ctx.params; M = ctx.mats; h = p["height"]; n = p["sides"]; r = h * 0.3
    # glass and flame glow (exported as glTF emissive)
    M.add("glass", M["glass"]["gitcraft_palette_ref"], rough=0.3, emit=2.5)
    M.add("flame", M["flame"]["gitcraft_palette_ref"], rough=0.5, emit=6.0)
    root = kit.empty("lantern", (0, 0, 0), kind="SPHERE", size=0.03)
    top = -0.06 * h / 0.42  # below the hook
    hr = 0.042 * h / 0.42
    parts = [kit.torus("hook", hr, 0.008, (0, 0, -(hr + 0.008)), axis="Y", mat=M["frame"], major=12, minor=5)]
    cap_h = h * 0.22; body_h = h * 0.5; z_cap_top = top - 0.02
    parts.append(kit.cylinder("cap", r * 0.25, cap_h, (0, 0, z_cap_top - cap_h / 2), verts=n, mat=M["cap"], r2=None))
    cone = kit.cylinder("roof", r * 1.15, cap_h, (0, 0, z_cap_top - cap_h * 0.55), verts=n, mat=M["cap"], r2=r * 0.22)
    parts.append(cone)
    z_body_top = z_cap_top - cap_h * 1.05
    parts.append(kit.cylinder("top_ring", r * 1.08, h * 0.04, (0, 0, z_body_top), verts=n, mat=M["frame"]))
    parts.append(kit.cylinder("glass", r * 0.92, body_h, (0, 0, z_body_top - body_h / 2), verts=n, mat=M["glass"]))
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        parts.append(kit.box("post", (h * 0.03, h * 0.03, body_h * 1.02), (math.cos(a) * r, math.sin(a) * r, z_body_top - body_h / 2), M["frame"]))
    zb = z_body_top - body_h
    parts.append(kit.cylinder("bottom_ring", r * 1.08, h * 0.05, (0, 0, zb), verts=n, mat=M["frame"]))
    parts.append(kit.cylinder("base", r * 0.95, h * 0.08, (0, 0, zb - h * 0.06), verts=n, mat=M["base"], r2=r * 0.55))
    parts.append(kit.sphere("finial", h * 0.035, (0, 0, zb - h * 0.13), M["frame"], segs=8, rings=5))
    flame_z = z_body_top - body_h * 0.55
    parts.append(kit.ico("flame", h * 0.06, (0, 0, flame_z), M["flame"], sub=1, scale=(0.7, 0.7, 1.4)))
    body = kit.join(parts, "lantern_body"); kit.shade(body); body.parent = root
    light = kit.empty("lantern_light", (0, 0, flame_z), parent=root, kind="SPHERE", size=0.03)
    fps = 30; T = round(p["swing_seconds"] * fps); a = math.radians(p["swing_deg"])
    keys = [(1 + T * k / 4, (a * math.sin(2 * math.pi * k / 4), a * 0.35 * math.cos(2 * math.pi * k / 4), None)) for k in range(5)]
    kit.keyframes(root, "rotation_euler", keys, "swing", interp="BEZIER", easing="AUTO")
    total = 0.03 + 0.02 + cap_h * 1.05 + body_h + h * 0.17
    return {"root": root, "expect": {"top_z": 0.0, "size": [r * 2.3, r * 2.3, total], "tolerance": 0.35, "centered": True},
            "contract": {"ground": False, "nodes": {"root": "lantern", "body": "lantern_body", "light": "lantern_light"}, "clips": ["swing"],
                         "origin": "hang point (top of hook); hangs down -Y", "light_anchor_yup": [0, round(flame_z, 4), 0]}}
