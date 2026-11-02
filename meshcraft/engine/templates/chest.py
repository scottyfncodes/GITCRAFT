"""Treasure chest with a hinged, animated lid.

Contract (matches TIDEBREAKERS `chestMesh()` in src/game/fx.ts, so it can replace it):
  root `chest_<tier>` at the base centre (y = 0 after export), front facing +Z (Three.js);
  `chest_body` (mesh), `chest_lid` (mesh, origin on the hinge at (0, 0.8·s, -0.45·s) in Y-up),
  `glow_anchor` (empty at (0, 1.2·s, 0)); animation clips `lid_open` (lid rotation.x 0 → -1.9 rad)
  and `lid_close`. s = 1 small, 1.5 grand, 1.1 sea.
"""
import math, random
from .. import kit

META = {
    "id": "chest",
    "title": "Treasure chest (hinged lid)",
    "category": "prop",
    "description": "Pebble & Sail treasure chest: bevelled planks, banding, rivets, pebble feet, Grinning Sun lock plate, treasure inside, animated lid.",
    "params": {
        "tier": {"type": "string", "enum": ["small", "grand", "sea"], "default": "small"},
        "fill": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.8, "description": "how full the chest is"},
        "seed": {"type": "integer", "default": 7},
        "lid_open_rad": {"type": "number", "default": -1.9},
        "open_seconds": {"type": "number", "default": 0.75},
    },
    "roles": ["wood", "plank", "band", "trim", "rivet", "gold", "gem", "gem2", "pearl", "dark", "barnacle", "weed"],
    "budget_tris": 6000,
}
TIER_SCALE = {"small": 1.0, "grand": 1.5, "sea": 1.1}
ROLES = {
    "small": {"wood": "Honey Timber", "plank": "Timber", "band": "Deep Tide", "trim": "Doubloon Gold", "rivet": "Gold Deep",
              "gold": "Doubloon Gold", "gem": "#2ECC71", "gem2": "Hibiscus", "pearl": "Sailcloth Cream", "dark": "Midnight Swell",
              "barnacle": "Sailcloth Cream", "weed": "Palm Green"},
    "grand": {"wood": "Deep Tide", "plank": "Midnight Swell", "band": "Doubloon Gold", "trim": "Sunlit Amber", "rivet": "Gold Deep",
              "gold": "Doubloon Gold", "gem": "#2ECC71", "gem2": "Hibiscus", "pearl": "Sailcloth Cream", "dark": "Midnight Swell",
              "barnacle": "Sailcloth Cream", "weed": "Palm Green"},
    "sea":   {"wood": "#5A7A8A", "plank": "Deep Tide", "band": "Gold Deep", "trim": "Lagoon Teal", "rivet": "Deep Tide",
              "gold": "Doubloon Gold", "gem": "#2ECC71", "gem2": "Shallows Aqua", "pearl": "Sailcloth Cream", "dark": "Midnight Swell",
              "barnacle": "Sailcloth Cream", "weed": "Jungle Deep"},
}


def default_roles(params):
    return dict(ROLES[params.get("tier", "small")])


def build(ctx):
    p = ctx.params; tier = p.get("tier", "small"); s = TIER_SCALE[tier]
    M = ctx.mats; rng = random.Random(p.get("seed", 7))
    W, D, H = 1.4 * s, 0.9 * s, 0.8 * s          # width (X), depth (Y), body height (Z)
    root = kit.empty(f"chest_{tier}", (0, 0, 0), kind="CUBE", size=0.1)
    parts = []
    # --- body: chunky bevelled box, a touch wider at the top (handcrafted wonk)
    body = kit.box("body", (W * 0.98, D * 0.98, H - 0.05 * s), (0, 0, (H + 0.05 * s) / 2), M["wood"], bevel=0.035 * s, segs=2, taper=-0.02)
    parts.append(body)
    # plank lines (slightly proud strips) on front/back/sides
    for frac in (0.4, 0.7):
        zz = frac * H
        for sgn in (-1, 1):
            parts.append(kit.box("plank_fb", (W * 0.97, 0.012, 0.022 * s), (0, sgn * D * 0.495, zz), M["plank"]))
            parts.append(kit.box("plank_lr", (0.012, D * 0.95, 0.022 * s), (sgn * W * 0.495, 0, zz), M["plank"]))
    # base trim + feet (pebbles)
    parts.append(kit.box("base_trim", (W * 1.02, D * 1.02, 0.09 * s), (0, 0, 0.09 * s), M["band"], bevel=0.02 * s))
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(kit.ico("foot", 0.08 * s, (sx * W * 0.42, sy * D * 0.38, 0.055 * s), M["plank"], sub=1, scale=(1.2, 1.2, 0.7), seed=rng.randint(0, 999), wobble=0.08))
    # vertical bands with rivets
    for bx in (-0.32, 0.32):
        band = kit.box("band_v", (0.12 * s, D * 1.025, H * 0.97), (bx * W, 0, H * 0.5 + 0.02 * s), M["band"], bevel=0.012 * s, segs=1)
        parts.append(band)
        for frac in (0.375, 0.69):
            for sgn in (-1, 1):
                parts.append(kit.sphere("rivet", 0.022 * s, (bx * W, sgn * D * 0.515, frac * H), M["rivet"], segs=8, rings=5))
    # rim trim
    parts.append(kit.box("rim", (W * 1.01, D * 1.01, 0.05 * s), (0, 0, H - 0.01 * s), M["trim"], bevel=0.01 * s, segs=1))
    # Grinning Sun lock plate on the front (-Y)
    fy = -D * 0.5 - 0.02 * s; lz = H * 0.66
    parts.append(kit.cylinder("lock_disc", 0.11 * s, 0.03 * s, (0, fy, lz), axis="Y", verts=18, mat=M["trim"]))
    rays = [(math.cos(a) * r, math.sin(a) * r) for i in range(16) for a, r in [(i * math.pi / 8, 0.17 * s if i % 2 == 0 else 0.115 * s)]]
    parts.append(kit.prism("lock_rays", rays, 0.02 * s, (0, fy + 0.006 * s, lz), axis="Y", mat=M["trim"]))
    parts.append(kit.cylinder("keyhole", 0.022 * s, 0.035 * s, (0, fy - 0.004 * s, lz - 0.01 * s), axis="Y", verts=10, mat=M["dark"]))
    parts.append(kit.box("keyslot", (0.016 * s, 0.036 * s, 0.05 * s), (0, fy - 0.004 * s, lz - 0.045 * s), M["dark"]))
    parts.append(kit.cylinder("eye", 0.014 * s, 0.035 * s, (0.045 * s, fy - 0.004 * s, lz + 0.04 * s), axis="Y", verts=8, mat=M["dark"]))
    parts.append(kit.box("patch", (0.04 * s, 0.036 * s, 0.032 * s), (-0.045 * s, fy - 0.004 * s, lz + 0.04 * s), M["dark"]))
    # treasure inside (seen when the lid opens)
    f = max(0.0, min(1.0, p.get("fill", 0.8)))
    if f > 0:
        pile_h = (0.12 + 0.22 * f) * s
        parts.append(kit.ico("gold_pile", 1.0, (0, 0, H - 0.06 * s), M["gold"], sub=2, scale=(W * 0.44, D * 0.4, pile_h), seed=3, wobble=0.06))
        for i in range(int(10 + 14 * f)):
            x = rng.uniform(-W * 0.38, W * 0.38); y = rng.uniform(-D * 0.32, D * 0.32)
            zt = H - 0.06 * s + pile_h * max(0.05, 1 - (x / (W * 0.44)) ** 2 - (y / (D * 0.4)) ** 2) ** 0.5
            c = kit.cylinder("coin", 0.05 * s, 0.012 * s, (x, y, zt), verts=10, mat=M["gold"])
            kit.set_origin(c, (x, y, zt))
            c.rotation_euler = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), 0); parts.append(c)
        for i, role in enumerate(("gem", "gem2", "pearl")):
            x = (-0.22 + 0.22 * i) * W; y = rng.uniform(-0.1, 0.1) * D
            zt = H - 0.06 * s + pile_h * 0.9
            parts.append(kit.ico(role, 0.06 * s if role != "pearl" else 0.045 * s, (x, y, zt), M[role], sub=0 if role != "pearl" else 1, seed=i))
    if tier == "sea":
        for i in range(14):
            sx = rng.choice((-1, 1))
            pos = (rng.uniform(-W * 0.45, W * 0.45), sx * D * 0.5, rng.uniform(0.12, 0.5) * H)
            parts.append(kit.ico("barnacle", rng.uniform(0.025, 0.045) * s, pos, M["barnacle"], sub=0, scale=(1, 0.6, 1), seed=i))
        for i in range(4):
            x = rng.uniform(-W * 0.4, W * 0.4)
            parts.append(kit.prism("weed", [(-0.02 * s, 0), (0.02 * s, 0), (0.035 * s, -0.22 * s), (0, -0.3 * s), (-0.03 * s, -0.2 * s)], 0.01 * s, (x, -D * 0.515, H), axis="Y", mat=M["weed"]))
    body = kit.join(parts, "chest_body")
    kit.shade(body)
    body.parent = root

    # --- lid: a vault on the hinge line, banded to match
    hinge = (0, D * 0.5, H)
    lid_parts = [kit.cylinder("vault", D * 0.5, W * 0.99, (0, 0, H), axis="X", verts=12, mat=M["wood"], arc=(0, math.pi))]
    for bx in (-0.32, 0.32):
        lid_parts.append(kit.cylinder("lid_band", D * 0.515, 0.12 * s, (bx * W, 0, H), axis="X", verts=12, mat=M["band"], arc=(0, math.pi)))
    for sgn in (-1, 1):
        lid_parts.append(kit.cylinder("lid_cap", D * 0.53, 0.05 * s, (sgn * W * 0.5, 0, H), axis="X", verts=12, mat=M["band"], arc=(0, math.pi)))
    lid_parts.append(kit.box("lid_lip", (W * 1.0, D * 1.0, 0.04 * s), (0, 0, H + 0.015 * s), M["plank"], bevel=0.008 * s, segs=1))
    lid_parts.append(kit.box("hasp", (0.08 * s, 0.03 * s, 0.14 * s), (0, -D * 0.5 - 0.035 * s, H - 0.03 * s), M["band"], bevel=0.01 * s, segs=1))
    lid = kit.join(lid_parts, "chest_lid")
    kit.shade(lid)
    kit.set_origin(lid, hinge)
    lid.parent = root
    glow = kit.empty("glow_anchor", (0, 0, 1.2 * s), parent=root, kind="SPHERE", size=0.1)

    fps = 30; n = max(2, round(p.get("open_seconds", 0.75) * fps)); ang = p.get("lid_open_rad", -1.9)
    kit.keyframes(lid, "rotation_euler", [(1, (0.0, None, None)), (n + 1, (ang, None, None))], "lid_open", interp="BEZIER", easing="EASE_OUT")
    kit.keyframes(lid, "rotation_euler", [(1, (ang, None, None)), (n + 1, (0.0, None, None))], "lid_close", interp="BEZIER", easing="EASE_IN")

    return {
        "root": root,
        "meshes": [body, lid],
        "expect": {"base_z": 0.0, "size": [W * 1.04, D * 1.1, H + D * 0.53 + 0.02 * s], "tolerance": 0.2},
        "contract": {
            "engine": "TIDEBREAKERS chestMesh() replacement",
            "nodes": {"root": f"chest_{tier}", "body": "chest_body", "lid": "chest_lid", "glow": "glow_anchor"},
            "lid_hinge_yup": [0, round(H, 4), round(-D * 0.5, 4)],
            "lid_open": {"axis": "x", "radians": ang, "clip": "lid_open"},
            "glow_anchor_yup": [0, round(1.2 * s, 4), 0],
            "scale": s,
        },
    }
