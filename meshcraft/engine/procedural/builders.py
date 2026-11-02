"""Procedural builders behind MeshCraft's boat, boat_upgrade, salvage, island, lighthouse, prop
and deckhand templates (moved here from ForgeCraft during the 3D Department consolidation).
Each builder returns a root object with the meshes under it. Blender -Y is forward
(glTF/three.js +Z). Materials come from geo.mat(), i.e. the template's palette roles."""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix, Euler, Quaternion
from . import geo as mc
from .geo import mat, prim, mesh_obj, join, empty, solidify, shade


# ====================================================================== boats
HULLS = {
    "dinghy": dict(L=4.4, W=0.92, D=0.75, sheer=0.55, bowRise=0.3, transom=0.72),
    "sloop": dict(L=10.0, W=1.9, D=1.5, sheer=1.2, bowRise=0.7, transom=0.65),
}


def hull_point(h, u, v):
    """Port of TIDEBREAKERS shipModel.ts hull loft. u: 0 stern → 1 bow, v: -1 port → 1 starboard."""
    if u < 0.45:
        width = h["W"] * (h["transom"] + (1 - h["transom"]) * math.sin((u / 0.45) * math.pi * 0.5))
    else:
        width = h["W"] * math.cos(((u - 0.45) / 0.55) * math.pi * 0.5) ** 0.85
    sheer = h["sheer"] + h["bowRise"] * u ** 3 + 0.08 * (1 - u) ** 2
    keel = h["D"] * (1 - 0.6 * (max(0, u - 0.6) / 0.4) ** 2) * (0.85 + 0.15 * math.sin(u * math.pi))
    a = abs(v)
    x = width * math.copysign(a ** 0.75, v) if v else 0.0
    z = sheer - keel * (1 - a ** 2.2)
    y = -(u - 0.5) * h["L"]
    return Vector((x, y, z))


def hull_surface(h, name, material, nu=26, nv=14, v_range=(-1, 1), offset=0.0):
    verts, faces = [], []
    v0, v1 = v_range
    for i in range(nu + 1):
        u = min(i / nu, 0.999)
        for j in range(nv + 1):
            v = v0 + (v1 - v0) * j / nv
            p = hull_point(h, u, v)
            if offset:
                p.x += math.copysign(offset, p.x) if abs(p.x) > 1e-4 else 0
                p.z -= offset * (1 - abs(v)) * 0.6
            verts.append(p)
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    return mesh_obj(name, verts, faces, material)


def boat(p):
    vessel = p.get("vessel", "sloop")
    h = HULLS[vessel]
    paint = p.get("paint", ["#4fb39a", "#f2ead8"])          # Seafoam Green by default
    sail_cols = p.get("sail_colors", ["#f1e6cc", "#c0392b"])  # Red Stripe
    root = empty(p["slug"])
    parts = []
    hull = hull_surface(h, "hull", mat(paint[0], "plank", 0.7))
    # trim band near the gunwale
    trim_l = hull_surface(h, "trim_l", mat(paint[1], "wood", 0.6), nv=2, v_range=(-1, -0.86), offset=0.012)
    trim_r = hull_surface(h, "trim_r", mat(paint[1], "wood", 0.6), nv=2, v_range=(0.86, 1), offset=0.012)
    for o in (hull, trim_l, trim_r): solidify(o, 0.05)
    parts += [hull, trim_l, trim_r]
    # transom board
    ring = [hull_point(h, 0, -1 + 2 * j / 12) for j in range(13)]
    c = Vector((0, ring[0].y, (ring[0].z + hull_point(h, 0, 0).z) / 2))
    tv = [c] + ring
    parts.append(solidify(mesh_obj("transom", tv, [(0, j + 1, j + 2) for j in range(12)], mat(paint[0], "plank")), 0.06))
    # deck
    nu = 26; dv, df = [], []
    deck_drop = 0.16 * h["L"] / 10
    for i in range(nu + 1):
        u = min(i / nu, 0.985)
        for side in (-0.97, 0.97):
            q = hull_point(h, u, side); q.z -= deck_drop; dv.append(q)
    for i in range(nu):
        a = i * 2; df.append((a, a + 1, a + 3, a + 2))
    deck = mesh_obj("deck", dv, df, mat("honey", "plank", 0.75))
    parts.append(solidify(deck, 0.05))
    deck_z = hull_point(h, 0.5, 0).z + h["D"] * 0  # placeholder
    mid = hull_point(h, 0.5, 0.97); deck_z = mid.z - deck_drop
    S = h["L"] / 10  # scale relative to the sloop
    wood = mat("timber", "wood", 0.7); dark = mat("deep_timber", "wood", 0.7)
    # gunwale posts + rail
    for side in (-1, 1):
        for i in range(3, 24, 3):
            u = i / 26; q = hull_point(h, u, side * 0.93)
            parts.append(prim("cyl", f"post_{side}_{i}", dark, loc=(q.x, q.y, q.z + 0.18 * S), vertices=6, radius=0.04 * S, depth=0.36 * S))
        pts = [hull_point(h, i / 26, side * 0.93) + Vector((0, 0, 0.36 * S)) for i in range(2, 25)]
        for a, b in zip(pts, pts[1:]):
            d = b - a; m = (a + b) / 2
            r = prim("cyl", "rail", wood, loc=m, vertices=6, radius=0.035 * S, depth=d.length)
            r.rotation_euler = d.to_track_quat("Z", "Y").to_euler(); mc.apply_xf(r); parts.append(r)
    # mast, boom, bowsprit
    mast_u = 0.6; mp = hull_point(h, mast_u, 0); mast_h = 9.0 * S
    mast_y = mp.y
    parts.append(prim("cyl", "mast", wood, loc=(0, mast_y, deck_z + mast_h / 2), vertices=10, radius=0.13 * S, depth=mast_h))
    parts.append(prim("cyl", "mast_cap", dark, loc=(0, mast_y, deck_z + mast_h), vertices=10, radius=0.17 * S, depth=0.2 * S))
    boom_len = 4.6 * S; boom_z = deck_z + 1.4 * S
    parts.append(prim("cyl", "boom", wood, loc=(0, mast_y + boom_len / 2, boom_z), rot=(math.pi / 2, 0, 0), vertices=8, radius=0.08 * S, depth=boom_len))
    bow = hull_point(h, 0.999, 0)
    parts.append(prim("cyl", "bowsprit", wood, loc=(0, bow.y - 1.0 * S, bow.z + 0.15 * S), rot=(math.pi / 2 - 0.25, 0, 0), vertices=8, radius=0.07 * S, depth=2.6 * S))
    # mainsail: billowed quad patch between mast and boom with stripes in separate material
    sail_mats = [mat(sail_cols[0], "cloth", 0.85), mat(sail_cols[1], "cloth", 0.85)]
    nx, nz = 8, 10; sv, sf, sm = [], [], []
    top = deck_z + mast_h * 0.93
    for i in range(nz + 1):
        t = i / nz; z = boom_z + 0.12 * S + (top - boom_z - 0.12 * S) * t
        width = boom_len * (1 - t) * 0.95 + 0.4 * S * t
        for j in range(nx + 1):
            s = j / nx
            belly = math.sin(s * math.pi) * math.sin(max(t, 0.05) * math.pi * 0.9 + 0.1) * 0.45 * S
            sv.append((belly, mast_y + 0.15 * S + width * s, z))
    for i in range(nz):
        for j in range(nx):
            a = i * (nx + 1) + j
            sf.append((a, a + 1, a + nx + 2, a + nx + 1)); sm.append(1 if i in (3, 4) else 0)
    sail = mesh_obj("mainsail", sv, sf)
    for m in sail_mats: sail.data.materials.append(m)
    for poly, mi in zip(sail.data.polygons, sm): poly.material_index = mi
    parts.append(solidify(sail, 0.025))
    # jib
    jv = [(0, mast_y - 0.2 * S, deck_z + mast_h * 0.85), (0.15 * S, bow.y - 1.9 * S, bow.z + 0.5 * S), (0.05 * S, mast_y - 0.4 * S, deck_z + 0.6 * S)]
    parts.append(solidify(mesh_obj("jib", jv, [(0, 1, 2)], sail_mats[0]), 0.025))
    # cabin aft
    cab_u = 0.24; cp = hull_point(h, cab_u, 0)
    parts.append(prim("cube", "cabin", mat(paint[1], "plank", 0.7), loc=(0, cp.y, deck_z + 0.45 * S), scale=(1.0 * S, 1.1 * S, 0.45 * S)))
    parts.append(prim("cube", "cabin_roof", mat("deep_timber", "plank"), loc=(0, cp.y, deck_z + 0.95 * S), scale=(1.12 * S, 1.22 * S, 0.06 * S)))
    for side in (-1, 1):
        parts.append(prim("cyl", "porthole", mat("gold", "metal", 0.35, 0.9), loc=(side * 1.01 * S, cp.y, deck_z + 0.5 * S),
                          rot=(0, math.pi / 2, 0), vertices=12, radius=0.16 * S, depth=0.04 * S))
    # tiller at the stern (base steering; the wheel upgrade replaces it visually)
    st = hull_point(h, 0.04, 0)
    parts.append(prim("cube", "rudder", dark, loc=(0, st.y + 0.05 * S, st.z - 0.4 * S), scale=(0.05 * S, 0.35 * S, 0.7 * S)))
    parts.append(prim("cyl", "tiller", wood, loc=(0, st.y - 0.6 * S, deck_z + 0.55 * S), rot=(math.pi / 2 - 0.2, 0, 0), vertices=6, radius=0.04 * S, depth=1.3 * S))
    # stern lantern + flag
    parts.append(prim("cyl", "lantern", mat("amber", "plain", 0.3, emit=2.0), loc=(0, st.y - 0.1 * S, deck_z + 1.25 * S), vertices=8, radius=0.12 * S, depth=0.28 * S))
    fl = mesh_obj("flag", [(0, mast_y, top + 0.3 * S), (0, mast_y + 1.2 * S, top + 0.15 * S), (0, mast_y + 1.2 * S, top - 0.45 * S), (0, mast_y, top - 0.35 * S)],
                  [(0, 1, 2, 3)], mat("midnight", "cloth"))
    parts.append(solidify(fl, 0.02))
    body = join(parts, f"{p['slug']}_mesh"); body.parent = root
    # attachment sockets for modular upgrades (empties export as glTF nodes)
    socks = {"socket_sail": (0, mast_y, boom_z), "socket_storage": (0, hull_point(h, 0.45, 0).y, deck_z),
             "socket_navigation": (0, cp.y - 1.0 * S, deck_z), "socket_steering": (0, st.y + 0.2 * S, deck_z),
             "socket_hull": (0, 0, 0), "socket_flag": (0, mast_y, top + 0.3 * S)}
    for n, loc in socks.items(): empty(n, loc, root)
    root["mc_forward"] = "+Z (glTF) / -Y (Blender)"
    return root


def upgrade(p):
    """Modular boat upgrades for the Coastal Sloop, modelled at their socket origin."""
    kind = p.get("upgrade", "cargo_crate")
    h = HULLS["sloop"]; S = 1.0
    root = empty(p["slug"]); parts = []
    if kind == "hull_copper":   # copper sheathing over the underwater hull of the sloop + brass rub-strips
        band = hull_surface(h, "sheathing", mat("copper", "metal", 0.35, 0.85), nu=26, nv=14, v_range=(-1, 1), offset=0.03)
        bm = bmesh.new(); bm.from_mesh(band.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().z > 0.55], context="FACES")
        bm.to_mesh(band.data); bm.free()
        parts.append(solidify(band, 0.03))
        for side in (-1, 1):   # brass rub-strip along the top edge of the sheathing
            pts = []
            for k in range(1, 26):
                u = k / 26
                v = min((x / 40 for x in range(41)), key=lambda vv: abs(hull_point(h, u, side * vv).z - 0.55))
                q = hull_point(h, u, side * v); q.x += side * 0.05; pts.append(q)
            for a, b in zip(pts, pts[1:]):
                d = b - a
                r = prim("cyl", "rub", mat("gold_deep", "metal", 0.3, 0.9), loc=(a + b) / 2, vertices=6, radius=0.04, depth=d.length * 1.02)
                r.rotation_euler = d.to_track_quat("Z", "Y").to_euler(); mc.apply_xf(r); parts.append(r)
        attach = "socket_hull"
    elif kind == "cargo_crate":
        wood = mat("honey", "plank", 0.75); rope = mat("rope", "cloth")
        for i, (x, y, z, s) in enumerate([(-0.45, 0, 0.35, 0.7), (0.45, 0.1, 0.3, 0.6), (0, -0.05, 0.95, 0.5)]):
            c = prim("cube", f"crate{i}", wood, loc=(x, y, z), scale=(s / 2, s / 2, s / 2)); mc.bevel(c, 0.02); parts.append(c)
            for k in (-1, 1):
                parts.append(prim("cube", "slat", mat("deep_timber", "wood"), loc=(x, y + k * s * 0.505, z), scale=(s * 0.52, 0.015, 0.06)))
        parts.append(prim("torus", "lash", rope, loc=(0, 0, 0.55), rot=(math.pi / 2, 0, 0), major_radius=0.85, minor_radius=0.03, major_segments=24, minor_segments=6))
        attach = "socket_storage"
    elif kind == "compass_brass":
        brass = mat("gold", "metal", 0.3, 0.95)
        parts.append(prim("cyl", "binnacle", mat("timber", "wood"), loc=(0, 0, 0.5), vertices=8, radius=0.22, depth=1.0))
        parts.append(prim("sphere", "dome", mat("sky_high", "plain", 0.05), loc=(0, 0, 1.06), segments=16, ring_count=8, radius=0.2))
        parts.append(prim("torus", "ring", brass, loc=(0, 0, 1.02), major_radius=0.22, minor_radius=0.035, major_segments=20, minor_segments=6))
        parts.append(prim("cone", "needle", mat("crimson", "plain"), loc=(0, -0.08, 1.06), rot=(math.pi / 2, 0, 0), vertices=4, radius1=0.03, depth=0.16))
        for k in (-1, 1):
            parts.append(prim("sphere", "corrector", mat("crimson", "metal", 0.4, 0.6), loc=(k * 0.3, 0, 0.9), segments=10, ring_count=6, radius=0.09))
        attach = "socket_navigation"
    elif kind == "rudder_ash":   # ship's wheel + ash rudder
        wood = mat("honey", "wood", 0.6)
        parts.append(prim("cube", "pedestal", mat("timber", "wood"), loc=(0, 0, 0.45), scale=(0.12, 0.12, 0.45)))
        parts.append(prim("torus", "wheel_rim", wood, loc=(0, -0.15, 1.1), rot=(math.pi / 2, 0, 0), major_radius=0.45, minor_radius=0.04, major_segments=24, minor_segments=6))
        for k in range(8):
            a = k * math.pi / 4
            sp = prim("cyl", "spoke", wood, loc=(math.cos(a) * 0.3, -0.15, 1.1 + math.sin(a) * 0.3), rot=(0, math.pi / 2 - a, 0), vertices=6, radius=0.025, depth=0.75)
            parts.append(sp)
            parts.append(prim("sphere", "handle", mat("deep_timber", "wood"), loc=(math.cos(a) * 0.57, -0.15, 1.1 + math.sin(a) * 0.57), segments=8, ring_count=5, radius=0.04))
        parts.append(prim("cyl", "hub", mat("gold", "metal", 0.3, 0.9), loc=(0, -0.15, 1.1), rot=(math.pi / 2, 0, 0), vertices=12, radius=0.08, depth=0.1))
        attach = "socket_steering"
    elif kind == "sail_canvas":  # tall canvas mainsail with yard, reef points and a patch
        cloth = mat(p.get("color", "cream"), "cloth", 0.85)
        nx, nz = 8, 12; sv, sf = [], []
        for i in range(nz + 1):
            t = i / nz; z = 0.15 + 7.2 * t; w = 4.4 * (1 - t) * 0.95 + 0.5 * t
            for j in range(nx + 1):
                s = j / nx; sv.append((math.sin(s * math.pi) * 0.55 * math.sin(t * math.pi * 0.9 + 0.1), 0.15 + w * s, z))
        for i in range(nz):
            for j in range(nx):
                a = i * (nx + 1) + j; sf.append((a, a + 1, a + nx + 2, a + nx + 1))
        parts.append(solidify(mesh_obj("canvas", sv, sf, cloth), 0.025))
        parts.append(prim("cyl", "yard", mat("timber", "wood"), loc=(0.05, 0.4, 7.4), rot=(math.pi / 2, 0, 0), vertices=8, radius=0.07, depth=1.2))
        for k in range(6):
            parts.append(prim("cyl", "reef", mat("rope", "cloth"), loc=(math.sin((k + 0.5) / 6 * math.pi) * 0.45 + 0.03, 0.5 + k * 0.6, 1.6), vertices=5, radius=0.015, depth=0.3))
        attach = "socket_sail"
    else:
        raise ValueError(f"unknown upgrade {kind}")
    body = join(parts, f"{p['slug']}_mesh"); body.parent = root
    root["mc_attach_to"] = attach
    return root


# ====================================================================== props
def _barrel(name, loc, r=0.35, hgt=0.9, col="timber"):
    parts = [prim("cyl", name, mat(col, "plank", 0.75), loc=loc, vertices=14, radius=r, depth=hgt)]
    # bulge via scaling mid ring
    o = parts[0]; bm = bmesh.new(); bm.from_mesh(o.data)
    for v in bm.verts:
        dz = (v.co.z) / (hgt / 2) if hgt else 0
        k = 1 + 0.12 * (1 - dz * dz)
        v.co.x *= k; v.co.y *= k
    bm.to_mesh(o.data); bm.free()
    for z in (-0.32, 0.32):
        parts.append(prim("torus", "hoop", mat("iron", "metal", 0.5, 0.8), loc=(loc[0], loc[1], loc[2] + z * hgt), major_radius=r * 1.07, minor_radius=0.025, major_segments=20, minor_segments=4))
    return parts


def salvage(p):
    """Floating salvage: lashed crate and barrel on a driftwood raft with a marker buoy.
    Includes a looping bob animation on its root."""
    root = empty(p["slug"]); parts = []
    for i in range(5):
        pl = prim("cube", f"plank{i}", mat("honey", "plank", 0.8), loc=(0, -0.9 + i * 0.45, 0.05), rot=(0, 0, random.uniform(-0.06, 0.06)),
                  scale=(1.15 + random.uniform(-0.15, 0.15), 0.2, 0.06))
        mc.bevel(pl, 0.02); parts.append(pl)
    parts.append(prim("cube", "cross", mat("deep_timber", "wood"), loc=(0, 0, 0.14), scale=(0.12, 1.2, 0.04)))
    c = prim("cube", "crate", mat("timber", "plank"), loc=(-0.35, -0.3, 0.5), rot=(0, 0, 0.3), scale=(0.33, 0.33, 0.33)); mc.bevel(c, 0.02); parts.append(c)
    parts += _barrel("barrel", (0.4, 0.35, 0.5))
    parts.append(prim("sphere", "buoy", mat("coral", "plain", 0.4), loc=(0.55, -0.75, 0.35), segments=14, ring_count=8, radius=0.26))
    parts.append(prim("cyl", "buoy_pole", mat("cream"), loc=(0.55, -0.75, 0.85), vertices=6, radius=0.03, depth=0.8))
    parts.append(solidify(mesh_obj("pennant", [(0.55, -0.75, 1.22), (0.55, -0.35, 1.12), (0.55, -0.75, 1.0)], [(0, 1, 2)], mat("gold", "cloth")), 0.02))
    parts.append(prim("torus", "rope", mat("rope", "cloth"), loc=(0, 0, 0.42), rot=(0, 0, 0), major_radius=0.62, minor_radius=0.025, major_segments=28, minor_segments=5))
    parts.append(prim("cyl", "chest", mat("crimson", "plank"), loc=(-0.2, 0.55, 0.32), rot=(0, math.pi / 2, 0), vertices=10, radius=0.17, depth=0.5))
    body = join(parts, f"{p['slug']}_mesh"); body.parent = root
    if p.get("animate", True):
        act = bpy.data.actions.new("float_bob"); act["mc_loop"] = True
        root.animation_data_create(); root.animation_data.action = act
        for f in range(0, 61, 10):
            t = f / 60 * 2 * math.pi
            root.location = (0, 0, 0.06 * math.sin(t)); root.keyframe_insert("location", frame=f)
            root.rotation_euler = (0.05 * math.sin(t + 1), 0.04 * math.cos(t), 0.02 * math.sin(t)); root.keyframe_insert("rotation_euler", frame=f)
        root.location = (0, 0, 0); root.rotation_euler = (0, 0, 0)
    return root


# ====================================================================== environment
def _noise2(x, y, seed):
    # value noise, deterministic
    def h(ix, iy):
        n = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xffffffff
        n = (n ^ (n >> 13)) * 1274126177 & 0xffffffff
        return ((n ^ (n >> 16)) & 0xffff) / 65535.0
    ix, iy = math.floor(x), math.floor(y); fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = h(ix, iy) + (h(ix + 1, iy) - h(ix, iy)) * sx
    b = h(ix, iy + 1) + (h(ix + 1, iy + 1) - h(ix, iy + 1)) * sx
    return a + (b - a) * sy


def fbm(x, y, seed, octaves=4):
    s, a, f = 0, 0.5, 1
    for _ in range(octaves):
        s += a * _noise2(x * f, y * f, seed); a *= 0.5; f *= 2
    return s


def palm(name, base, height=5.0, lean=0.35, seed=0):
    rnd = random.Random(seed); parts = []
    segs = 7; prev = Vector(base)
    dirv = Vector((math.cos(seed) * lean, math.sin(seed) * lean, 1)).normalized()
    pts = [prev]
    for i in range(1, segs + 1):
        t = i / segs
        p = Vector(base) + Vector((dirv.x * height * t * t, dirv.y * height * t * t, height * t))
        pts.append(p)
    trunk = mat("honey", "wood", 0.8)
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        d = b - a
        r = prim("cyl", f"{name}_trunk{i}", trunk if i % 2 == 0 else mat("timber", "wood"), loc=(a + b) / 2, vertices=7,
                 radius=0.2 * (1 - 0.06 * i), depth=d.length * 1.05)
        r.rotation_euler = d.to_track_quat("Z", "Y").to_euler(); mc.apply_xf(r); parts.append(r)
    top = pts[-1]
    leaf = mat("palm", "grass", 0.7)
    for k in range(7):
        a = k * 2 * math.pi / 7 + rnd.uniform(-0.2, 0.2); L = 2.6 + rnd.uniform(-0.3, 0.3)
        v = []; f = []
        n = 6
        for i in range(n + 1):
            t = i / n; w = math.sin(t * math.pi) * 0.45
            droop = -1.4 * t * t
            cx, cy = math.cos(a) * L * t, math.sin(a) * L * t
            px, py = -math.sin(a) * w, math.cos(a) * w
            v += [(top.x + cx + px, top.y + cy + py, top.z + droop + 0.25 * t), (top.x + cx - px, top.y + cy - py, top.z + droop + 0.25 * t)]
        for i in range(n): f.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
        parts.append(solidify(mesh_obj(f"{name}_leaf{k}", v, f, leaf), 0.03))
    for k in range(3):
        a = k * 2.1
        parts.append(prim("sphere", "coconut", mat("deep_timber", "plain"), loc=(top.x + math.cos(a) * 0.22, top.y + math.sin(a) * 0.22, top.z - 0.2), segments=8, ring_count=5, radius=0.14))
    return parts


def rock(name, loc, size=1.0, seed=0, color="stone"):
    r = prim("ico", name, mat(color, "rock", 0.9), loc=loc, subdivisions=2, radius=size)
    rnd = random.Random(seed)
    for v in r.data.vertices:
        v.co *= 1 + rnd.uniform(-0.22, 0.18)
        v.co.z *= 0.7
    return r


def island(p):
    """Small tropical island: noise heightfield (sand → grass → rock by height and slope),
    palms, rocks, a hut on stilts and a dock. Sea level is z = 0."""
    seed = int(p.get("seed", 7)); radius = float(p.get("radius", 22)); peak = float(p.get("peak", 6.5))
    random.seed(seed)
    n = int(p.get("resolution", 72))
    root = empty(p["slug"]); parts = []
    mats = [mat("sand", "sand", 0.9), mat("palm", "grass", 0.85), mat("jungle", "grass", 0.85), mat("stone", "rock", 0.9), mat("#d8c08a", "sand", 0.9)]
    verts, faces, fm = [], [], []
    ext = radius * 1.35

    def height(x, y):
        r = math.hypot(x, y) / radius
        ang = math.atan2(y, x)
        r *= 1 + 0.18 * (fbm(math.cos(ang) * 1.5 + 3, math.sin(ang) * 1.5 + 3, seed, 3) - 0.5) * 2
        base = max(0.0, 1 - r * r) ** 1.4
        hill = fbm(x / radius * 2.2 + 10, y / radius * 2.2 + 10, seed + 1, 4)
        hgt = base * (peak * (0.55 + 0.75 * hill)) - 1.6 * min(1, r) ** 2 + 0.6
        return max(hgt, -2.2)
    for i in range(n + 1):
        for j in range(n + 1):
            x = -ext + 2 * ext * i / n; y = -ext + 2 * ext * j / n
            verts.append(Vector((x, y, height(x, y))))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j; q = (a, a + n + 1, a + n + 2, a + 1)
            zs = [verts[k].z for k in q]
            if max(zs) < -0.7: continue  # open water / flat seabed: no geometry (the game draws its own ocean)
            faces.append(q)
            zc = sum(zs) / 4; slope = max(zs) - min(zs)
            fm.append(4 if zc < 0.0 else 0 if zc < 0.9 else 3 if slope > 1.1 * (2 * ext / n) else 1 if zc < 3.4 else 2)
    terrain = mesh_obj("terrain", verts, faces)
    for m in mats: terrain.data.materials.append(m)
    for poly, mi in zip(terrain.data.polygons, fm): poly.material_index = mi
    parts.append(terrain)
    rnd = random.Random(seed)
    # palms on grass, rocks on shore
    placed = 0; tries = 0
    while placed < int(p.get("palms", 7)) and tries < 400:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(0.15, 0.72) * radius
        x, y = math.cos(a) * r, math.sin(a) * r; z = height(x, y)
        if 1.0 < z < 4.5:
            parts += palm(f"palm{placed}", (x, y, z - 0.1), rnd.uniform(4.2, 6.0), 0.3, seed=placed * 3 + seed); placed += 1
    for k in range(9):
        a = rnd.uniform(0, 2 * math.pi); r = rnd.uniform(0.75, 0.98) * radius
        x, y = math.cos(a) * r, math.sin(a) * r
        parts.append(rock(f"rock{k}", (x, y, height(x, y)), rnd.uniform(0.5, 1.4), seed + k))
    # dock heading out on -Y side + hut on stilts
    dock_y0 = -radius * 0.78; dz = 0.9
    for i in range(10):
        parts.append(prim("cube", f"dock{i}", mat("honey", "plank", 0.8), loc=(0, dock_y0 - i * 0.62, dz), scale=(1.1, 0.28, 0.06)))
    for i in range(0, 10, 3):
        for s in (-1, 1):
            parts.append(prim("cyl", "piling", mat("deep_timber", "wood"), loc=(s * 1.0, dock_y0 - i * 0.62, dz - 1.2), vertices=6, radius=0.1, depth=2.8))
    hx, hy = radius * 0.25, -radius * 0.45; hz = height(hx, hy)
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(prim("cyl", "stilt", mat("deep_timber", "wood"), loc=(hx + sx * 1.3, hy + sy * 1.1, hz + 0.5), vertices=6, radius=0.1, depth=1.6))
    parts.append(prim("cube", "hut_floor", mat("honey", "plank"), loc=(hx, hy, hz + 1.3), scale=(1.6, 1.4, 0.08)))
    parts.append(prim("cube", "hut_walls", mat("parchment", "plank", 0.8), loc=(hx, hy, hz + 2.2), scale=(1.3, 1.1, 0.85)))
    roof = prim("cone", "hut_roof", mat("#c9a24a", "grass", 0.9), loc=(hx, hy, hz + 3.6), vertices=4, radius1=2.5, depth=1.9)
    roof.rotation_euler = (0, 0, math.pi / 4); mc.apply_xf(roof); parts.append(roof)
    parts.append(prim("cube", "hut_door", mat("deep_timber", "wood"), loc=(hx, hy - 1.11, hz + 2.0), scale=(0.35, 0.03, 0.6)))
    # treasure flag on the summit
    parts.append(prim("cyl", "flagpole", mat("cream"), loc=(0, 0, height(0, 0) + 1.2), vertices=6, radius=0.05, depth=2.4))
    parts.append(solidify(mesh_obj("flag", [(0, 0, height(0, 0) + 2.4), (0.9, 0, height(0, 0) + 2.2), (0, 0, height(0, 0) + 1.9)], [(0, 1, 2)], mat("crimson", "cloth")), 0.02))
    body = join(parts, f"{p['slug']}_mesh"); body.parent = root
    empty("socket_dock", (0, dock_y0 - 9 * 0.62, dz + 0.06), root)
    empty("socket_spawn", (hx, hy - 2.0, hz), root)
    return root


def lighthouse(p):
    root = empty(p["slug"]); parts = []
    parts.append(rock("base", (0, 0, 0), 3.2, 3))
    for i in range(6):
        col = "white" if i % 2 == 0 else "crimson"
        parts.append(prim("cyl", f"tier{i}", mat(col, "plank", 0.7), loc=(0, 0, 1.5 + i * 1.2), vertices=12, radius=1.2 - i * 0.09, depth=1.2))
    parts.append(prim("cyl", "gallery", mat("iron", "metal", 0.5, 0.7), loc=(0, 0, 8.7), vertices=12, radius=1.15, depth=0.15))
    parts.append(prim("cyl", "lamp", mat("gold", "plain", 0.2, emit=3.0), loc=(0, 0, 9.3), vertices=12, radius=0.6, depth=1.0))
    parts.append(prim("cone", "cap", mat("crimson", "plain"), loc=(0, 0, 10.3), vertices=12, radius1=0.9, depth=1.0))
    body = join(parts, f"{p['slug']}_mesh"); body.parent = root
    return root


def prop(p):
    kind = p.get("prop", "barrel"); root = empty(p["slug"])
    if kind == "barrel": parts = _barrel("barrel", (0, 0, 0.45))
    elif kind == "crate":
        c = prim("cube", "crate", mat("honey", "plank"), loc=(0, 0, 0.4), scale=(0.4, 0.4, 0.4)); mc.bevel(c, 0.02); parts = [c]
    elif kind == "rock": parts = [rock("rock", (0, 0, 0.3), 0.8, int(p.get("seed", 1)))]
    elif kind == "palm": parts = palm("palm", (0, 0, 0), 5.0, 0.3, int(p.get("seed", 1)))
    else: raise ValueError(f"unknown prop {kind}")
    body = join(parts, f"{p['slug']}_mesh"); body.parent = root
    return root


# ====================================================================== characters
MIXAMO = "mixamorig:"
# bone: (head, tail, parent) in metres, T-pose, facing -Y (glTF +Z). Names follow Mixamo's skeleton so
# animations downloaded from mixamo.com ("Without Skin") retarget by name.
SKELETON = {
    "Hips": ((0, 0, 0.95), (0, 0, 1.05), None),
    "Spine": ((0, 0, 1.05), (0, 0, 1.17), "Hips"),
    "Spine1": ((0, 0, 1.17), (0, 0, 1.29), "Spine"),
    "Spine2": ((0, 0, 1.29), (0, 0, 1.42), "Spine1"),
    "Neck": ((0, 0, 1.42), (0, 0, 1.5), "Spine2"),
    "Head": ((0, 0, 1.5), (0, 0, 1.75), "Neck"),
    "LeftShoulder": ((0.05, 0, 1.38), (0.18, 0, 1.38), "Spine2"),
    "LeftArm": ((0.18, 0, 1.38), (0.45, 0, 1.38), "LeftShoulder"),
    "LeftForeArm": ((0.45, 0, 1.38), (0.7, 0, 1.38), "LeftArm"),
    "LeftHand": ((0.7, 0, 1.38), (0.8, 0, 1.38), "LeftForeArm"),
    "LeftUpLeg": ((0.1, 0, 0.92), (0.1, 0, 0.52), "Hips"),
    "LeftLeg": ((0.1, 0, 0.52), (0.1, 0, 0.1), "LeftUpLeg"),
    "LeftFoot": ((0.1, 0, 0.1), (0.1, -0.12, 0.03), "LeftLeg"),
    "LeftToeBase": ((0.1, -0.12, 0.03), (0.1, -0.2, 0.03), "LeftFoot"),
}
for k, (h, t, par) in list(SKELETON.items()):
    if k.startswith("Left"):
        SKELETON["Right" + k[4:]] = ((-h[0], h[1], h[2]), (-t[0], t[1], t[2]), par.replace("Left", "Right") if par and par.startswith("Left") else par)


def _part(bone, objs):
    for o in objs:
        vg = o.vertex_groups.new(name=MIXAMO + bone)
        vg.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
    return objs


def _limb(name, a, b, r1, r2, material, verts=8):
    a, b = Vector(a), Vector(b); d = b - a
    o = prim("cone", name, material, loc=(a + b) / 2, vertices=verts, radius1=r1, radius2=r2, depth=d.length)
    o.rotation_euler = d.to_track_quat("Z", "Y").to_euler(); mc.apply_xf(o)
    return o


def character(p):
    """Low-poly deckhand: rigid-skinned to a Mixamo-named armature, with idle/walk/run/jump/
    interact/attack clips authored as Blender actions."""
    cols = p.get("colors", {})
    skin = mat(cols.get("skin", "skin"), "skin", 0.6); shirt = mat(cols.get("shirt", "cream"), "cloth", 0.85)
    vest = mat(cols.get("vest", "crimson"), "cloth", 0.8); pants = mat(cols.get("pants", "deep"), "cloth", 0.85)
    boot = mat("deep_timber", "plain", 0.6); band = mat(cols.get("bandana", "coral"), "cloth", 0.8)
    root = empty(p["slug"]); parts = []
    S = SKELETON
    parts += _part("Hips", [prim("cyl", "pelvis", pants, loc=(0, 0, 0.98), vertices=10, radius=0.17, depth=0.2)])
    parts += _part("Spine", [prim("cyl", "belly", shirt, loc=(0, 0, 1.12), vertices=10, radius=0.165, depth=0.14)])
    parts += _part("Spine1", [prim("cyl", "belt", mat("deep_timber", "plain"), loc=(0, 0, 1.06), vertices=10, radius=0.172, depth=0.05),
                              prim("cube", "buckle", mat("gold", "metal", 0.3, 0.9), loc=(0, -0.172, 1.06), scale=(0.04, 0.01, 0.03))])
    parts += _part("Spine2", [_limb("chest", (0, 0, 1.18), (0, 0, 1.44), 0.17, 0.19, vest, 10),
                              prim("cube", "shirt_v", shirt, loc=(0, -0.175, 1.36), scale=(0.06, 0.02, 0.08))])
    parts += _part("Neck", [prim("cyl", "neck", skin, loc=(0, 0, 1.47), vertices=8, radius=0.06, depth=0.08)])
    head = [prim("sphere", "head", skin, loc=(0, 0, 1.6), segments=14, ring_count=9, radius=0.14),
            prim("sphere", "bandana", band, loc=(0, 0.01, 1.65), segments=14, ring_count=9, radius=0.148),
            prim("cone", "knot", band, loc=(0, 0.16, 1.66), rot=(-math.pi / 2, 0, 0), vertices=6, radius1=0.05, depth=0.12),
            prim("sphere", "nose", skin, loc=(0, -0.14, 1.59), segments=8, ring_count=5, radius=0.028)]
    for s in (-1, 1):
        head.append(prim("sphere", "eye", mat("black", "plain", 0.2), loc=(s * 0.05, -0.125, 1.63), segments=8, ring_count=5, radius=0.02))
    # trim bandana to the top half
    bm = bmesh.new(); bm.from_mesh(head[1].data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < 0.02], context="VERTS"); bm.to_mesh(head[1].data); bm.free()
    parts += _part("Head", head)
    for side, sgn in (("Left", 1), ("Right", -1)):
        sh = S[side + "Arm"][0]; el = S[side + "ForeArm"][0]; wr = S[side + "Hand"][0]
        parts += _part(side + "Shoulder", [prim("sphere", "shoulder", vest, loc=(sgn * 0.17, 0, 1.38), segments=10, ring_count=6, radius=0.08)])
        parts += _part(side + "Arm", [_limb("upper", sh, el, 0.065, 0.055, shirt)])
        parts += _part(side + "ForeArm", [_limb("fore", el, wr, 0.05, 0.042, skin)])
        hand = [prim("sphere", "hand", skin, loc=(sgn * 0.75, 0, 1.38), segments=8, ring_count=6, radius=0.055)]
        if side == "Right" and p.get("weapon", True):   # cutlass held in the right hand, blade forward
            hand += [_limb("grip", (-0.75, 0.0, 1.32), (-0.75, 0.0, 1.44), 0.018, 0.018, mat("deep_timber", "plain")),
                     prim("torus", "guard", mat("gold", "metal", 0.3, 0.9), loc=(-0.75, 0, 1.44), major_radius=0.05, minor_radius=0.012, major_segments=12, minor_segments=4),
                     _limb("blade", (-0.75, 0, 1.45), (-0.75, -0.05, 2.05), 0.025, 0.006, mat("white", "metal", 0.25, 1.0), 4)]
        parts += _part(side + "Hand", hand)
        hip = S[side + "UpLeg"][0]; kn = S[side + "Leg"][0]; an = S[side + "Foot"][0]
        parts += _part(side + "UpLeg", [_limb("thigh", hip, kn, 0.085, 0.07, pants)])
        parts += _part(side + "Leg", [_limb("shin", kn, an, 0.07, 0.06, pants)])
        parts += _part(side + "Foot", [prim("cube", "boot", boot, loc=(sgn * 0.1, -0.05, 0.05), scale=(0.07, 0.12, 0.05))])
        parts += _part(side + "ToeBase", [prim("cube", "toe", boot, loc=(sgn * 0.1, -0.17, 0.035), scale=(0.065, 0.05, 0.035))])
    body = join(parts, f"{p['slug']}_mesh")
    return root, body


def rig_character(root, body, clips=("Idle", "Walk", "Run", "Jump", "Interact", "Attack")):
    arm_d = bpy.data.armatures.new("rig")
    arm = mc.link(bpy.data.objects.new(root.name + "_rig", arm_d))
    arm.parent = root
    arm["mc_convention"] = "mixamo"
    mc.select_only([arm]); bpy.ops.object.mode_set(mode="EDIT")
    for name, (h, t, par) in SKELETON.items():
        b = arm_d.edit_bones.new(MIXAMO + name); b.head = h; b.tail = t; b.roll = 0
    for name, (h, t, par) in SKELETON.items():
        if par: arm_d.edit_bones[MIXAMO + name].parent = arm_d.edit_bones[MIXAMO + par]; arm_d.edit_bones[MIXAMO + name].use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    body.parent = arm
    mod = body.modifiers.new("Armature", "ARMATURE"); mod.object = arm
    acts = [ANIMS[c](arm) for c in clips]
    return arm, acts


# --- animation authoring: rotations are given about rest-pose (armature space) axes
def _rot(arm, bone, axis_angles, frame):
    pb = arm.pose.bones[MIXAMO + bone]
    B = pb.bone.matrix_local.to_3x3()
    R = Matrix.Identity(3)
    for axis, deg in axis_angles:   # applied in order (first one first)
        R = Matrix.Rotation(math.radians(deg), 3, axis) @ R
    q = (B.inverted() @ R @ B).to_quaternion()
    pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = q
    pb.keyframe_insert("rotation_quaternion", frame=frame, group=pb.name)


def _loc(arm, bone, world_offset, frame):
    pb = arm.pose.bones[MIXAMO + bone]
    pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(world_offset)
    pb.keyframe_insert("location", frame=frame, group=pb.name)


ARMS_DOWN = 72


def _new_action(arm, name, loop=True):
    act = bpy.data.actions.new(name); act["mc_loop"] = loop; act.use_fake_user = True
    arm.animation_data_create(); arm.animation_data.action = act
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    return act


def _finish(arm, act):
    tr = arm.animation_data.nla_tracks.new(); tr.name = act.name
    tr.strips.new(act.name, int(act.frame_range[0]), act)
    tr.mute = True
    arm.animation_data.action = None
    return act


def _cycle(arm, name, n, pose_fn, loop=True, step=2):
    act = _new_action(arm, name, loop)
    for f in range(0, n + 1, step):
        pose_fn(f / n, f)
    return _finish(arm, act)


def a_idle(arm):
    def pose(t, f):
        s = math.sin(t * 2 * math.pi)
        _loc(arm, "Hips", (0, 0, -0.01 + 0.01 * s), f)
        _rot(arm, "Spine1", [("X", 2 * s)], f); _rot(arm, "Head", [("Z", 6 * math.sin(t * 2 * math.pi + 1))], f)
        _rot(arm, "LeftArm", [("Y", ARMS_DOWN), ("X", 3 * s)], f); _rot(arm, "RightArm", [("Y", -ARMS_DOWN), ("X", -3 * s)], f)
        _rot(arm, "LeftForeArm", [("Z", 10)], f); _rot(arm, "RightForeArm", [("Z", -10)], f)
    return _cycle(arm, "Idle", 60, pose, step=5)


def _gait(arm, name, n, swing, knee, arm_swing, bob, lean):
    def pose(t, f):
        ph = t * 2 * math.pi; s = math.sin(ph); c = math.cos(ph)
        _loc(arm, "Hips", (0, 0, bob * abs(math.cos(ph)) - bob * 0.5), f)
        _rot(arm, "Spine", [("X", -lean)], f); _rot(arm, "Spine2", [("Z", 6 * s)], f)
        _rot(arm, "LeftUpLeg", [("X", -swing * s)], f); _rot(arm, "RightUpLeg", [("X", swing * s)], f)
        _rot(arm, "LeftLeg", [("X", knee * max(0, math.sin(ph + 1.6)))], f); _rot(arm, "RightLeg", [("X", knee * max(0, math.sin(ph + 1.6 + math.pi)))], f)
        _rot(arm, "LeftFoot", [("X", -10 * c)], f); _rot(arm, "RightFoot", [("X", 10 * c)], f)
        _rot(arm, "LeftArm", [("Y", ARMS_DOWN), ("X", arm_swing * s)], f); _rot(arm, "RightArm", [("Y", -ARMS_DOWN), ("X", -arm_swing * s)], f)
        _rot(arm, "LeftForeArm", [("Z", 15 + 10 * max(0, s))], f); _rot(arm, "RightForeArm", [("Z", -15 - 10 * max(0, -s))], f)
    return _cycle(arm, name, n, pose)


def a_walk(arm): return _gait(arm, "Walk", 32, 28, 40, 24, 0.04, 3)
def a_run(arm): return _gait(arm, "Run", 20, 48, 85, 50, 0.08, 14)


def a_jump(arm):
    act = _new_action(arm, "Jump", loop=False)
    keys = [(0, 0, 0, 0), (8, -0.18, 35, 1), (12, 0.05, -5, 0.2), (20, 0.45, 10, 0.4), (28, 0.05, 20, 0.8), (32, -0.12, 30, 1), (40, 0, 0, 0)]
    for f, dz, crouch, armsup in keys:
        _loc(arm, "Hips", (0, 0, dz), f)
        _rot(arm, "LeftUpLeg", [("X", -crouch)], f); _rot(arm, "RightUpLeg", [("X", -crouch)], f)
        _rot(arm, "LeftLeg", [("X", crouch * 1.8)], f); _rot(arm, "RightLeg", [("X", crouch * 1.8)], f)
        _rot(arm, "LeftFoot", [("X", -crouch * 0.8)], f); _rot(arm, "RightFoot", [("X", -crouch * 0.8)], f)
        _rot(arm, "Spine", [("X", -crouch * 0.5)], f)
        _rot(arm, "LeftArm", [("Y", ARMS_DOWN * (1 - armsup) + 10 * armsup), ("X", -40 * armsup)], f)
        _rot(arm, "RightArm", [("Y", -ARMS_DOWN * (1 - armsup) - 10 * armsup), ("X", -40 * armsup)], f)
    return _finish(arm, act)


def a_interact(arm):  # wave hello / signal the crew
    def pose(t, f):
        w = math.sin(t * 6 * math.pi)
        up = min(1, t * 5) * min(1, (1 - t) * 5)
        _rot(arm, "LeftArm", [("Y", ARMS_DOWN)], f)
        _rot(arm, "RightArm", [("Y", -ARMS_DOWN + (ARMS_DOWN + 70) * up)], f)
        _rot(arm, "RightForeArm", [("Y", -40 * up), ("Z", 25 * w * up)], f)
        _rot(arm, "Head", [("Z", -10 * up)], f); _rot(arm, "Spine2", [("Y", 4 * up)], f)
    return _cycle(arm, "Interact", 48, pose, loop=False)


def a_attack(arm):  # overhead cutlass slash
    act = _new_action(arm, "Attack", loop=False)
    for f, raise_, cut, lunge in [(0, 0, 0, 0), (8, 1, 0, 0), (12, 1, 0.2, 0.3), (16, 0.2, 1, 1), (22, 0, 0.8, 0.7), (30, 0, 0, 0)]:
        _rot(arm, "LeftArm", [("Y", ARMS_DOWN)], f)
        _rot(arm, "RightArm", [("Y", -ARMS_DOWN + 150 * raise_), ("X", -60 * cut)], f)
        _rot(arm, "RightForeArm", [("Z", -30 * raise_)], f)
        _rot(arm, "Spine2", [("X", -12 * lunge), ("Z", -15 * cut)], f)
        _rot(arm, "LeftUpLeg", [("X", -25 * lunge)], f); _rot(arm, "LeftLeg", [("X", 25 * lunge)], f)
        _rot(arm, "RightUpLeg", [("X", 15 * lunge)], f)
        _loc(arm, "Hips", (0, -0.15 * lunge, -0.06 * lunge), f)
    return _finish(arm, act)


ANIMS = {"Idle": a_idle, "Walk": a_walk, "Run": a_run, "Jump": a_jump, "Interact": a_interact, "Attack": a_attack}

BUILDERS = {"boat": boat, "upgrade": upgrade, "salvage": salvage, "island": island, "lighthouse": lighthouse, "prop": prop}
