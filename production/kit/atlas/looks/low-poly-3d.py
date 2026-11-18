"""Low-Poly 3D (atlas look 8): build an atlas scene (SCENE.md) in 3D with MeshCraft's Blender and render it.

    looks/low-poly-3d.sh <scene.json> <out_dir> [samples]          (MeshCraft run_script, sandboxed)
    MCP:  meshcraft run_script {"path": ".../looks/low-poly-3d.py", "args": {"scene": "<scene.json>", "out": "<out_dir>"}}
    bpy:  <meshcraft venv>/bin/python looks/low-poly-3d.py -- <scene.json> <out_dir>
    args / env: scene (LP3D_SCENE), out (LP3D_OUT), samples (LP3D_SAMPLES, 48), scale (LP3D_SCALE, 1.0 = 1920x1080),
                only ("game" | "hero"; default both)

Writes <out>/game3d.png (1920x1080, the 960x540 scene at 2x), <out>/hero3d.png (800x800, transparent, 3/4 view) and
<out>/render3d.json (engine, samples, seconds, scene sha256). Deterministic: no clock or random state is read, every
variation comes from a seeded RNG, and Cycles runs with a fixed seed.

Layout contract: the camera is an off-axis perspective camera looking straight down +Y with a lens shift, so the
gameplay plane (Y = 0) maps linearly onto the 960x540 scene (1 scene px = 1 cm; scene x -> Blender X, scene y -> -Z).
Every layer behind it (mid blocks, ridge, sun, sky) is scaled about the eye so its front face projects exactly where
the 2D scene puts it: the HUD and the composition line up with the 2D looks, and the eye sits above the frame, so
tops and sides of the blocks show their depth.
"""
import bpy, bmesh, hashlib, json, math, os, re, sys, tempfile, time
from mathutils import Vector, Matrix

U = 0.01          # metres per scene px
D = 22.0          # eye distance to the gameplay plane (m)
EYE = -120.0      # eye height in scene px (above the top edge)

# ---------------------------------------------------------------- inputs

def _inputs():
    a = dict(globals().get("args") or {})
    rest = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if rest: a.setdefault("scene", rest[0])
    if len(rest) > 1: a.setdefault("out", rest[1])
    a.setdefault("scene", os.environ.get("LP3D_SCENE"))
    a.setdefault("out", os.environ.get("LP3D_OUT"))
    a.setdefault("samples", int(os.environ.get("LP3D_SAMPLES", "48")))
    a.setdefault("scale", float(os.environ.get("LP3D_SCALE", "1.0")))
    a.setdefault("only", os.environ.get("LP3D_ONLY", ""))
    if not a["scene"] or not a["out"]: raise SystemExit("low-poly-3d: need a scene json and an out dir")
    return a

def rng(seed):   # mulberry32, the same generator lib.js uses
    s = [seed & 0xFFFFFFFF]
    def r():
        s[0] = (s[0] + 0x6D2B79F5) & 0xFFFFFFFF; t = s[0]
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return r

# ---------------------------------------------------------------- palettes (mood-driven)

PAL = {
    "dusk": dict(city=True,
        sky=[(0, "#26305e"), (0.30, "#5b4f8f"), (0.56, "#d77b86"), (0.74, "#ffa784"), (1, "#ffd2a4")],
        ridge="#a35d82", ridge2="#d58593", shelf="#2f3c6b", mid="#3e4f86", mid2="#4c64a0", window="#ffcf7a",
        body="#203259", cap="#2fb0a3", cap2="#258f86", hazard="#ff5560", hazard2="#8a2846", coin="#ffc23c",
        hero="#fff4e6", accent="#ff6152", eye="#1a2140", trail="#fff1e2", string="#2a3458", line="#fff5ea",
        sun="#ffefb8", halo="#ffb48c", cloud="#ffc4b0", haze="#e98a8c",
        key=("#ffcaa0", 3.4), fill=("#5f74c2", 0.55), world=("#59629e", 0.5)),
    "night": dict(city=True,
        sky=[(0, "#0d1330"), (0.5, "#1f2a5c"), (1, "#3b3f7a")],
        ridge="#2a3266", ridge2="#3a4380", shelf="#151c3d", mid="#222c5a", mid2="#2b376c", window="#ffd77f",
        body="#141c3a", cap="#3a6fb0", cap2="#2c568c", hazard="#ff5560", hazard2="#6a2040", coin="#ffc23c",
        hero="#f2f4ff", accent="#ff6152", eye="#0d1330", trail="#dfe6ff", string="#c9d2ff", line="#dfe6ff",
        sun="#f4f2e0", halo="#7c86c8", cloud="#3b4686", haze="#3a4380",
        key=("#b8c6ff", 2.6), fill=("#3a4aa0", 0.5), world=("#2a3470", 0.45)),
    "day": dict(city=False,
        sky=[(0, "#3c98e6"), (0.45, "#7cc6f4"), (0.8, "#c8ecff"), (1, "#e8f8ff")],
        ridge="#6fb4a6", ridge2="#a7d6dc", shelf="#5aa66f", mid="#3f9e62", mid2="#2f8452", window="#ffe7a0",
        body="#c98652", cap="#67c25f", cap2="#4fa64b", hazard="#ff5a5f", hazard2="#a3303f", coin="#ffc23c",
        hero="#ff6a55", accent="#fff4e6", eye="#1a2140", trail="#ffffff", string="#33405e", line="#ffffff",
        sun="#fff4bf", halo="#fffbe0", cloud="#ffffff", haze="#cfeaf5",
        key=("#fff0da", 3.8), fill=("#93c8ff", 0.6), world=("#a6d2ff", 0.65)),
    "dawn": dict(city=False,
        sky=[(0, "#6b8fd6"), (0.5, "#f2b0b6"), (1, "#ffe2c4")],
        ridge="#9a8fb8", ridge2="#c8b3cc", shelf="#6f9c7c", mid="#5a9a70", mid2="#467f5c", window="#ffe7a0",
        body="#b9805a", cap="#79bf6c", cap2="#5fa358", hazard="#ff5a5f", hazard2="#9a3040", coin="#ffc23c",
        hero="#fff4e6", accent="#ff6152", eye="#1a2140", trail="#ffffff", string="#3a4766", line="#ffffff",
        sun="#fff0c0", halo="#ffd0b0", cloud="#ffe8e4", haze="#f0c8c8",
        key=("#ffd8b8", 3.4), fill=("#8aa8ff", 0.6), world=("#a9b6ea", 0.6)),
}

def lin(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple((x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4) for x in c) + (1.0,)

def mixhex(a, b, t):
    A = [int(a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]; B = [int(b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(A, B))

_MATS = {}
def mat(color, rough=0.82, emit=0.0, metal=0.0, alpha=1.0, spec=0.35):
    key = (color, rough, emit, metal, alpha, spec)
    if key in _MATS: return _MATS[key]
    m = bpy.data.materials.new(f"LP_{color[1:]}_{len(_MATS)}"); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = lin(color); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if "Specular IOR Level" in p.inputs: p.inputs["Specular IOR Level"].default_value = spec
    if emit:
        p.inputs["Emission Color"].default_value = lin(color); p.inputs["Emission Strength"].default_value = emit
    if alpha < 1: p.inputs["Alpha"].default_value = alpha
    _MATS[key] = m
    return m

def emissive(color, strength=1.0, alpha=1.0):
    key = ("emit", color, strength, alpha)
    if key in _MATS: return _MATS[key]
    m = bpy.data.materials.new(f"LPE_{color[1:]}"); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = lin(color); em.inputs["Strength"].default_value = strength
    if alpha < 1:
        tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
        mx.inputs["Fac"].default_value = alpha
        nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2]); nt.links.new(mx.outputs[0], out.inputs[0])
    else:
        nt.links.new(em.outputs[0], out.inputs[0])
    _MATS[key] = m
    return m

# ---------------------------------------------------------------- mapping

def k_at(d): return (D + d) / D
CX = 0.0; CZ = 0.0
def P(px, py, d=0.0):
    """world point at depth d that projects onto scene pixel (px, py)"""
    k = k_at(d)
    return Vector((CX + (px * U - CX) * k, d, CZ + (-py * U - CZ) * k))

# ---------------------------------------------------------------- mesh helpers

COLL = None
def obj_from_bm(bm, name, m, smooth=False):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me); COLL.objects.link(ob)
    ob.data.materials.append(m)
    return ob

def box_world(x0, x1, y0, y1, z0, z1, m, name="box", bevel=0.0, seg=1):
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    idx = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for f in idx: bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = obj_from_bm(bm, name, m)
    if bevel > 0:
        md = ob.modifiers.new("bevel", "BEVEL"); md.width = min(bevel, (x1 - x0) * 0.45, (z1 - z0) * 0.45, (y1 - y0) * 0.45)
        md.segments = seg; md.limit_method = "ANGLE"
    return ob

def box_scene(px, py, pw, ph, d, y0, y1, m, name="box", bevel=0.05):
    """an axis-aligned box whose face at depth d covers scene rect (px,py,pw,ph); it spans Y in [y0, y1]"""
    a = P(px, py, d); b = P(px + pw, py + ph, d)
    return box_world(a.x, b.x, y0, y1, b.z, a.z, m, name, bevel)

def ico(center, r, m, sub=1, scale=(1, 1, 1), name="ico", rot=None):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    ob = obj_from_bm(bm, name, m); ob.location = center; ob.scale = scale
    if rot: ob.rotation_euler = rot
    return ob

def cone(center, r1, r2, depth, verts, m, name="cone", rot=(0, 0, 0)):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts, radius1=r1, radius2=r2, depth=depth)
    ob = obj_from_bm(bm, name, m); ob.location = center; ob.rotation_euler = rot
    return ob

def tube(points, radius, m, name="tube", res=2):
    cu = bpy.data.curves.new(name, "CURVE"); cu.dimensions = "3D"; cu.bevel_depth = radius; cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY"); sp.points.add(len(points) - 1)
    for p, v in zip(sp.points, points): p.co = (v.x, v.y, v.z, 1)
    ob = bpy.data.objects.new(name, cu); COLL.objects.link(ob); ob.data.materials.append(m)
    return ob

def catmull(pts, n=10):
    out = []
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]; p1, p2 = pts[i], pts[i + 1]; p3 = pts[i + 2] if i + 2 < len(pts) else p2
        for s in range(n):
            t = s / n; t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                               + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(tuple(pts[-1])); return out

# ---------------------------------------------------------------- SVG paths -> extruded low-poly meshes

def split_subpaths(d):
    parts = [p.strip() for p in re.split(r"(?=M)", d) if p.strip()]
    return parts or [d]

def _area(ob):
    me = ob.data; return sum(p.area for p in me.polygons) if hasattr(me, "polygons") else 0

def svg_solids(paths, box, place, thick, mats, res=3, bevel=0.02, name="svg"):
    """paths: [(d, thickness_half, material)] in a box (bw, bh) SVG space; place(sx, sy) -> world (x, z) linear;
    each path becomes a separate filled, extruded, chamfered solid (so overlapping subpaths never cut holes)."""
    import addon_utils
    addon_utils.enable("io_curve_svg", default_set=False)
    bw, bh = box
    body = "".join(f'<path d="{d}"/>' for d, _, _ in paths)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw}" height="{bh}" viewBox="0 0 {bw} {bh}">'
           f'<path d="M0 0H{bw}V{bh}H0Z"/>{body}</svg>')
    fd, fn = tempfile.mkstemp(suffix=".svg"); os.write(fd, svg.encode()); os.close(fd)
    before = set(bpy.data.objects)
    bpy.ops.import_curve.svg(filepath=fn); os.remove(fn)
    new = [o for o in bpy.data.objects if o not in before and o.type == "CURVE"]
    new.sort(key=lambda o: o.name)
    cal, objs = new[0], new[1:]
    bb = [cal.matrix_world @ Vector(c) for c in cal.bound_box]
    lx0, lx1 = min(v.x for v in bb), max(v.x for v in bb); ly0, ly1 = min(v.y for v in bb), max(v.y for v in bb)
    a = (lx1 - lx0) / bw                      # local units per svg unit; svg (sx, sy) = ((lx-lx0)/a, (ly1-ly)/a)
    (wx0, wz0), (wx1, wz1) = place(0, 0), place(bw, bh)
    sxw = (wx1 - wx0) / bw; szw = (wz1 - wz0) / bh   # world per svg unit (szw < 0: y down)
    out = []
    for ob, (d, half, m) in zip(objs, paths):
        # world = Mw @ local: X = sxw*(lx-lx0)/a + wx0 ; Z = szw*(ly1-ly)/a + wz0 ; Y = ±s*lz
        s = abs(sxw) / a
        M = Matrix(((sxw / a, 0, 0, wx0 - sxw * lx0 / a),
                    (0, 0, -s, 0),
                    (0, -szw / a, 0, wz0 + szw * ly1 / a),
                    (0, 0, 0, 1)))
        if M.to_3x3().determinant() < 0: M[1][2] = s
        ob.matrix_world = M @ ob.matrix_world
        cu = ob.data; cu.dimensions = "2D"; cu.fill_mode = "BOTH"; cu.resolution_u = res
        cu.extrude = max(half - bevel, 0.002) / s; cu.bevel_depth = bevel / s; cu.bevel_resolution = 0
        for sp in cu.splines: sp.resolution_u = res
        cu.materials.clear(); cu.materials.append(m)
        out.append(ob)
    for o in [cal]: bpy.data.objects.remove(o, do_unlink=True)
    # convert to meshes, flat shaded, into our collection
    meshes = []
    for ob in out:
        dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev); me.transform(ob.matrix_world)
        for p in me.polygons: p.use_smooth = False
        mo = bpy.data.objects.new(name, me); COLL.objects.link(mo)
        meshes.append(mo); bpy.data.objects.remove(ob, do_unlink=True)
    for c in list(bpy.data.collections):
        if c is not COLL and not c.objects and c.name != COLL.name: bpy.data.collections.remove(c)
    return meshes

# ---------------------------------------------------------------- scene parts

def build_sky(S, C, W, H):
    d = 80.0; a = P(-60, -60, d); b = P(W + 60, H + 60, d)
    bm = bmesh.new()
    v = [bm.verts.new((a.x, d, a.z)), bm.verts.new((b.x, d, a.z)), bm.verts.new((b.x, d, b.z)), bm.verts.new((a.x, d, b.z))]
    bm.faces.new(v)
    m = bpy.data.materials.new("LP_sky"); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); ramp = nt.nodes.new("ShaderNodeValToRGB")
    em = nt.nodes.new("ShaderNodeEmission"); out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    els = ramp.color_ramp.elements
    stops = C["sky"]
    # t: 0 top .. 1 bottom of the frame; generated Z: 0 bottom .. 1 top. Elements re-sort when moved, so add them
    # in ascending position order and set each colour right after its position.
    seq = sorted(((1 - (60 + t * H) / (H + 120), col) for t, col in stops))
    while len(els) > 1: els.remove(els[-1])
    els[0].position = seq[0][0]; els[0].color = lin(seq[0][1])
    for pos, col in seq[1:]:
        e = els.new(pos); e.color = lin(col)
    ob = obj_from_bm(bm, "sky", m)
    ob.visible_shadow = False
    ob.visible_diffuse = False
    return ob

def build_sun(S, C):
    s = S["sun"]; d = 60.0; k = k_at(d); c = P(s["x"], s["y"], d); r = s["r"] * U * k
    ico(c, r, emissive(C["sun"], 1.6), sub=2, name="sun")
    for i, (f, al) in enumerate(((1.4, 0.22), (1.85, 0.10))):
        bm = bmesh.new(); bmesh.ops.create_circle(bm, cap_ends=True, segments=14, radius=r * f)
        ob = obj_from_bm(bm, "halo", emissive(C["halo"], 1.0, al)); ob.location = c + Vector((0, 1 + i, 0))
        ob.rotation_euler = (math.pi / 2, 0, math.pi / 14 * i); ob.visible_shadow = False
    for o in bpy.data.objects:
        if o.name.startswith(("sun", "halo")): o.visible_shadow = False

def ridge(pts, W, H, depth, color, seed, jitter=0.18, rows=4, back=1.5):
    r = rng(seed)
    # resample the polyline every ~32 px so the facets are small and even
    res = []
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]; n = max(1, round(math.hypot(x1 - x0, y1 - y0) / 32))
        for j in range(n): t = j / n; res.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    res.append(tuple(pts[-1]))
    res = [(-40, res[0][1])] + res + [(W + 40, res[-1][1])]
    crest = [P(x, y, depth) for x, y in res]
    base_z = P(0, H + 40, depth - 3.0).z
    bm = bmesh.new(); grid = []
    for row in range(rows + 1):                     # row 0 behind the crest, 1 = crest, ... rows = foot (toward the eye)
        line = []
        for i, c in enumerate(crest):
            if row == 0:
                v = (c.x, depth + back, c.z - 0.35)
            elif row == 1:
                v = (c.x, depth, c.z)
            else:
                t = (row - 1) / (rows - 1)
                y = depth - 3.0 * t
                z = c.z + (base_z - c.z) * (t ** 0.8)
                edge = 0 if i in (0, len(crest) - 1) else 1
                v = (c.x + (r() - 0.5) * jitter * 1.6 * edge, y + (r() - 0.5) * 0.6, z + (r() - 0.5) * jitter * edge * (1 - t * 0.3))
            line.append(bm.verts.new(v))
        grid.append(line)
    for row in range(rows):
        for i in range(len(crest) - 1):
            a, b, c, d = grid[row][i], grid[row][i + 1], grid[row + 1][i + 1], grid[row + 1][i]
            if (i + row) % 2: bm.faces.new((a, b, c)); bm.faces.new((a, c, d))
            else: bm.faces.new((a, b, d)); bm.faces.new((b, c, d))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        if f.normal.y > 0: f.normal_flip()
    return obj_from_bm(bm, "ridge", mat(color, 0.95))

def build_far(S, C, W, H):
    far = S["far"]
    # a hazier second range behind, derived from the scene's polyline (phase-shifted, lifted), for aerial depth
    r = rng(11); back = []
    for i, (x, y) in enumerate(far):
        back.append((x + 60, y - 46 - 22 * math.sin(i * 1.7) - r() * 10))
    ridge(sorted(back), W, H, 30.0, C["ridge2"], 5, jitter=0.35, rows=3, back=3)
    ridge(far, W, H, 14.0, C["ridge"], 7)

def build_clouds(S, C, W, H):
    r = rng(23); n = 3 if not C["city"] else 2
    hero = S["hero"]; sun = S.get("sun")
    cands = [(250, 170), (560, 80), (110, 235), (880, 215), (420, 120)]
    placed = 0
    for (x, y) in cands:
        if placed >= n: break
        if sun and math.hypot(x - sun["x"], y - sun["y"]) < sun["r"] + 120: continue
        if hero["x"] - 120 < x < hero["x"] + hero["size"] + 120 and hero["y"] - 80 < y < hero["y"] + hero["size"] + 60: continue
        if any(abs(x - p[0]) < 200 and abs(y - p[1]) < 70 for p in (S.get("pickups") or [{"x": -999, "y": -999}]) for p in [(p["x"], p["y"])]): continue
        d = 24.0; k = k_at(d); c = P(x, y, d); m = mat(C["cloud"], 0.95, emit=0.25)
        w = (60 + r() * 30) * U * k
        for j, (ox, oz, rr) in enumerate(((-0.7, -0.08, 0.36), (-0.15, 0.1, 0.52), (0.45, 0.02, 0.44), (0.95, -0.1, 0.3))):
            ico(c + Vector((ox * w, -0.3 * j, oz * w)), rr * w, m, sub=1, scale=(1.4, 0.8, 0.6), name="cloud",
                rot=(0.2 * j, 0.3 * j, 0.5 * j))
        placed += 1

def build_mid(S, C, W, H):
    mids = S.get("mid") or []
    if not mids: return
    gy = S.get("ground_y", H); d = 5.0
    # the street / meadow shelf the blocks stand on
    sc = mixhex(C["shelf"], C["ridge"], 0.35)
    box_scene(-80, gy + 8, W + 160, H - gy + 80, d - 0.8, d - 0.8, d + 2.4, mat(sc, 0.9), "shelf", 0.04)
    box_scene(-80, gy, W + 160, 10, d - 0.8, d - 0.9, d + 2.4, mat(mixhex(sc, "#ffffff", 0.22), 0.85), "kerb", 0.02)
    r = rng(31)
    for i, (x, w, h) in enumerate(mids):
        if C["city"]:
            col = C["mid"] if i % 2 == 0 else C["mid2"]
            dd = d + (i % 3) * 0.35                         # staggered depth: a street, not a wall
            body = box_scene(x, gy - h, w, h, dd, dd, dd + 1.2, mat(col, 0.85), "building", 0.035)
            box_scene(x - 3, gy - h - 7, w + 6, 8, dd, dd - 0.06, dd + 1.26, mat(mixhex(col, "#ffffff", 0.18), 0.8), "roof", 0.02)
            # lit windows: small emissive panes set just proud of the front face
            wm = emissive(C["window"], 2.2); dm = mat(mixhex(col, "#000000", 0.25), 0.9)
            cols = max(1, int((w - 14) // 15)); rows_ = max(1, int((h - 24) // 22))
            for ry in range(rows_):
                for cx in range(cols):
                    px = x + 8 + cx * ((w - 16) / cols) + 2; py = gy - h + 14 + ry * 22
                    lit = r() < 0.42
                    a = P(px, py, dd); b = P(px + 7, py + 10, dd)
                    box_world(a.x, b.x, dd - 0.015, dd + 0.01, b.z, a.z, wm if lit else dm, "window")
            if r() < 0.45:   # a rooftop tank or antenna
                top = P(x + w * (0.3 + r() * 0.4), gy - h - 7, dd)
                if r() < 0.5:
                    cone(top + Vector((0, 0.6, 0.12)), 0.11, 0.11, 0.24, 7, mat(C["mid2"], 0.8), "tank")
                else:
                    cone(top + Vector((0, 0.6, 0.25)), 0.012, 0.012, 0.5, 4, mat(C["mid2"], 0.8), "antenna")
        else:
            dd = d + (i % 3) * 0.4; base = P(x + w / 2, gy, dd); k = k_at(dd)
            if w > h * 1.15:                                     # a rock
                ico(base + Vector((0, 0.6, h * U * k * 0.35)), w * U * k * 0.5, mat("#9aa6b8", 0.9), sub=1,
                    scale=(1, 0.7, h / w * 1.3), name="rock", rot=(0.3, 0.2 + i, 0.4))
            elif i % 2 == 0:                                     # a round tree
                trunk_h = h * 0.32
                cone(base + Vector((0, 0.6, trunk_h * U * k / 2)), w * U * k * 0.09, w * U * k * 0.07, trunk_h * U * k, 5, mat("#8a5a3c", 0.9), "trunk")
                ico(base + Vector((0, 0.6, (trunk_h + (h - trunk_h) / 2) * U * k)), w * U * k * 0.5, mat(C["mid"] if i % 4 else C["mid2"], 0.85),
                    sub=1, scale=(1, 0.85, (h - trunk_h) / w), name="crown", rot=(0.4, 0.3 * i, 0.2))
            else:                                                # a stacked pine
                cone(base + Vector((0, 0.6, h * 0.08 * U * k)), w * U * k * 0.07, w * U * k * 0.07, h * 0.16 * U * k, 5, mat("#8a5a3c", 0.9), "trunk")
                for j in range(3):
                    hh = h * (0.42 - j * 0.06); zz = h * (0.16 + j * 0.25) + hh / 2
                    cone(base + Vector((0, 0.6, zz * U * k)), w * U * k * (0.55 - j * 0.13), 0, hh * U * k, 6,
                         mat(C["mid2"] if j % 2 else C["mid"], 0.85), "pine", rot=(0, 0, 0.5 * j + i))

def build_haze(S, C, W, H):
    """aerial haze between the mid blocks and the gameplay plane: thickest at the bottom, so gaps read as distance"""
    if not S.get("mid"): return
    gy = S.get("ground_y", H); d = 3.2
    a = P(-80, gy - 90, d); b = P(W + 80, H + 40, d)
    bm = bmesh.new()
    v = [bm.verts.new((a.x, d, a.z)), bm.verts.new((b.x, d, a.z)), bm.verts.new((b.x, d, b.z)), bm.verts.new((a.x, d, b.z))]
    bm.faces.new(v)
    m = bpy.data.materials.new("LP_haze")
    m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    tc = nt.nodes.new("ShaderNodeTexCoord"); sep = nt.nodes.new("ShaderNodeSeparateXYZ"); ramp = nt.nodes.new("ShaderNodeValToRGB")
    em = nt.nodes.new("ShaderNodeEmission"); tr = nt.nodes.new("ShaderNodeBsdfTransparent"); mx = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs[0].default_value = lin(C["haze"])
    nt.links.new(tc.outputs["Generated"], sep.inputs[0]); nt.links.new(sep.outputs["Z"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
    nt.links.new(mx.outputs[0], out.inputs[0])
    e = ramp.color_ramp.elements; e[0].position = 0.0; e[0].color = (0.62, 0.62, 0.62, 1); e[1].position = 0.85; e[1].color = (0, 0, 0, 1)
    ob = obj_from_bm(bm, "haze", m)
    ob.visible_shadow = False; ob.visible_diffuse = False; ob.visible_glossy = False

def build_platforms(S, C, W, H):
    r = rng(41)
    for i, (x, y, w, h) in enumerate(S.get("platforms") or []):
        y0, y1 = -0.7, 0.9
        if h >= 50:            # a solid block of ground (a rooftop in the city, earth and grass outside)
            box_scene(x, y + 10, w, h - 10, 0, y0, y1, mat(C["body"], 0.86), "platform", 0.05)
            box_scene(x - 4, y, w + 8, 14, 0, y0 - 0.06, y1 + 0.02, mat(C["cap"], 0.75), "cap", 0.04)
            if C["city"]:
                wm = emissive(C["window"], 2.0); dm = mat(mixhex(C["body"], "#000000", 0.3), 0.9)
                cols = max(1, int((w - 30) // 34)); rows_ = max(1, int((h - 44) // 34))
                for ry in range(rows_):
                    for cx in range(cols):
                        px = x + 20 + cx * ((w - 40) / cols) + 6; py = y + 34 + ry * 34
                        if px + 12 > W + 10 or py + 16 > H + 4: continue
                        a = P(px, py, y0); b = P(px + 12, py + 16, y0)
                        box_world(a.x, b.x, y0 - 0.02, y0 + 0.02, b.z, a.z, wm if r() < 0.5 else dm, "window")
                # rooftop vents at the back, clear of the gameplay plane
                for j in range(1 if w < 240 else 2):
                    vx = x + w * (0.22 + 0.5 * j) + r() * 30
                    a = P(vx, y - 16, 0); b = P(vx + 26, y, 0)
                    box_world(a.x, b.x, 0.45, 0.82, b.z, a.z, mat(C["cap2"], 0.7), "vent", 0.03)
            else:
                # grass tufts and pebbles along the cap, and stones set into the earth face
                for j in range(int(w // 46)):
                    tx = x + 20 + j * 46 + r() * 20; base = P(tx, y, 0)
                    cone(base + Vector((0, 0.55 + r() * 0.25, 0.06)), 0.07, 0, 0.16 + r() * 0.08, 4, mat(C["cap2"], 0.8), "tuft", rot=(0, 0, r()))
                for j in range(int(w // 120)):
                    sx = x + 50 + j * 120 + r() * 60; sy = y + 30 + r() * max(4, h - 50)
                    c = P(sx, sy, y0)
                    ico(c + Vector((0, 0.0, 0)), 0.09 + r() * 0.06, mat(mixhex(C["body"], "#ffffff", 0.25), 0.9), sub=1,
                        scale=(1.3, 0.5, 0.8), name="stone", rot=(0.2, 0.1, r()))
        else:                  # a floating slab
            box_scene(x, y, w, h, 0, y0 + 0.1, y1 - 0.1, mat(C["cap"], 0.75), "slab", 0.05)
            box_scene(x + 8, y + h, w - 16, max(8, h * 0.5), 0, y0 + 0.25, y1 - 0.25, mat(C["cap2"], 0.8), "slab_under", 0.03)

def build_hazards(S, C, W, H):
    for hz in S.get("hazards") or []:
        k = hz.get("kind")
        if k == "spikes":
            n = max(3, round(hz["w"] / 22)); sw = hz["w"] / n
            box_scene(hz["x"], hz["y"] + hz["h"] - 8, hz["w"], 12, 0, -0.5, 0.6, mat(C["hazard2"], 0.7), "spike_base", 0.02)
            for row, (yy, off) in enumerate(((-0.25, 0.0), (0.35, 0.5))):
                for i in range(n - (1 if off else 0)):
                    cx = hz["x"] + (i + 0.5 + off) * sw; base = P(cx, hz["y"] + hz["h"] - 6, 0)
                    hh = (hz["h"] - 4) * U * (1.0 if row == 0 else 0.85)
                    cone(Vector((base.x, yy, base.z + hh / 2)), sw * U * 0.5, 0, hh, 4, mat(C["hazard"], 0.45, metal=0.1), "spike",
                         rot=(0, 0, math.pi / 4))
        elif k == "path" and hz.get("path"):
            bw, bh = hz.get("box") or [hz["w"], hz["h"]]
            def place(sx, sy, hz=hz, bw=bw, bh=bh):
                p = P(hz["x"] + sx * hz["w"] / bw, hz["y"] + sy * hz["h"] / bh, 0); return (p.x, p.z)
            parts = [(d, 0.07 - 0.008 * j, mat(C["hazard"], 0.5)) for j, d in enumerate(split_subpaths(hz["path"]))]
            svg_solids(parts, (bw, bh), place, None, None, res=2, bevel=0.015, name="hazard")
        else:
            box_scene(hz["x"], hz["y"], hz["w"], hz["h"], 0, -0.25, 0.25, mat(C["hazard"], 0.55), "hazard_block", 0.03)
            for j in range(int(hz["h"] // 34)):                  # warning stripes
                yy = hz["y"] + 12 + j * 34
                box_scene(hz["x"] - 1.5, yy, hz["w"] + 3, 12, 0, -0.27, 0.27, mat(C["hazard2"], 0.6), "stripe", 0.01)

def build_pickups(S, C):
    m = mat(C["coin"], 0.35, emit=0.25, metal=0.2, spec=0.6); r = rng(53)
    for i, p in enumerate(S.get("pickups") or []):
        rr = p.get("r", 11); c = P(p["x"], p["y"], 0); spin = (-0.32, -0.12, 0.12, 0.3, -0.22)[i % 5]
        if S.get("pickup_path"):
            def place(sx, sy, p=p, rr=rr):
                q = P(p["x"] - rr + sx * rr / 12, p["y"] - rr + sy * rr / 12, 0); return (q.x, q.z)
            obs = svg_solids([(d, 0.05, m) for d in split_subpaths(S["pickup_path"])], (24, 24), place, None, None, res=3, bevel=0.012, name="pickup")
            for o in obs:
                me = o.data; me.transform(Matrix.Translation(-c)); me.transform(Matrix.Rotation(spin, 4, "Z")); me.transform(Matrix.Translation(c))
            continue
        shape = S.get("pickup_shape", "circle")
        if shape == "diamond":
            for sgn in (1, -1):
                cone(c + Vector((0, 0, sgn * rr * U * 0.62)), rr * U, 0, rr * U * 1.25, 6, m, "gem", rot=(0 if sgn > 0 else math.pi, 0, spin))
        elif shape == "star":
            bm = bmesh.new(); vs = []
            for j in range(10):
                a = -math.pi / 2 + j * math.pi / 5; R = rr * U * (0.48 if j % 2 else 1.15)
                vs.append(bm.verts.new((math.cos(a) * R, 0, -math.sin(a) * R)))
            f = bm.faces.new(vs); ext = bmesh.ops.extrude_face_region(bm, geom=[f])
            bmesh.ops.translate(bm, vec=(0, 0.09, 0), verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            ob = obj_from_bm(bm, "star", m); ob.location = c - Vector((0, 0.045, 0)); ob.rotation_euler = (0, 0, spin)
        else:
            ob = cone(c, rr * U * 1.1, rr * U * 1.1, 0.07, 10, m, "coin", rot=(math.pi / 2, 0, spin))
            cone(c + Vector((0, 0, 0)), rr * U * 0.62, rr * U * 0.62, 0.09, 10, mat(mixhex(C["coin"], "#ffffff", 0.35), 0.3, metal=0.3), "coin_face",
                 rot=(math.pi / 2, 0, spin))

def build_trail(S, C):
    t = S.get("trail") or []
    if len(t) < 2: return
    pts = catmull(t, 12)
    if S.get("trail_kind") == "string":
        tube([P(x, y, 0) for x, y in pts], 1.4 * U, mat(C["string"], 0.6), "string", res=1)
    else:
        m = mat(C["trail"], 0.6, emit=0.35)
        n = len(t) * 3; L = len(pts) - 1
        for j in range(n - 1):
            x, y = pts[round(j / (n - 1) * L)]
            ico(P(x, y, 0), (2.2 + j * 0.42) * U, m, sub=1, name="trail")

def build_lines(S, C):
    m = mat(C["line"], 0.6, emit=0.6)
    for ln in S.get("lines") or []:
        tube([P(x, y, 0.2) for x, y in catmull(ln, 10)], 2.6 * U, m, "line", res=1)

def build_hero(S, C, at=None):
    h = dict(S["hero"]); k = h["size"] / 64; f = -1 if h.get("facing", 1) < 0 else 1
    def place(sx, sy):
        px = h["x"] + (h["size"] - sx * k if f < 0 else sx * k); p = P(px, h["y"] + sy * k, 0); return (p.x, p.z)
    T = h["size"] * U                                       # hero size in metres
    subs = split_subpaths(h["path"]); acc = split_subpaths(h["accent"]) if h.get("accent") else []
    body_m = mat(C["hero"], 0.62, spec=0.45); acc_m = mat(C["accent"], 0.55, spec=0.45)
    base = T * 0.25
    # thickness by order: the first subpath is the main body; the rest sit a little behind its face, staggered so no
    # two faces are coplanar; accents sit proud of the body
    parts = [(d, base if j == 0 else base * 0.7 - 0.006 * j, body_m) for j, d in enumerate(subs)]
    parts += [(d, base + 0.025 + 0.004 * j, acc_m) for j, d in enumerate(acc)]
    obs = svg_solids(parts, (64, 64), place, None, None, res=3, bevel=min(0.03, T * 0.04), name="hero")
    eye = h.get("eye", [40, 38, 3.5]) if "eye" in h else [40, 38, 3.5]
    if eye is not None:
        ex, ey, er = eye
        px = h["x"] + (h["size"] - ex * k if f < 0 else ex * k); c = P(px, h["y"] + ey * k, 0)
        R = er * k * U * 1.25
        e = ico(c + Vector((0, -base - R * 0.15, 0)), R, mat(C["eye"], 0.25, spec=0.8), sub=2, name="hero_eye", scale=(1, 0.6, 1.15))
        ico(c + Vector((f * R * 0.35, -base - R * 0.7, R * 0.4)), R * 0.32, emissive("#ffffff", 2.0), sub=1, name="hero_glint")
        obs.append(e)
    return obs

# ---------------------------------------------------------------- lights, world, render

def look_at_rot(direction):
    return Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()

def lights(C, hero_center=None, hero_energy=60):
    sc = bpy.context.scene
    kd = bpy.data.lights.new("key", "SUN"); kd.color = lin(C["key"][0])[:3]; kd.energy = C["key"][1]; kd.angle = math.radians(5)
    ko = bpy.data.objects.new("key", kd); COLL.objects.link(ko); ko.rotation_euler = look_at_rot((-0.42, 0.62, -0.66))
    fd = bpy.data.lights.new("fill", "SUN"); fd.color = lin(C["fill"][0])[:3]; fd.energy = C["fill"][1]; fd.angle = math.radians(20)
    fd.use_shadow = False
    fo = bpy.data.objects.new("fill", fd); COLL.objects.link(fo); fo.rotation_euler = look_at_rot((0.7, 0.45, -0.25))
    if hero_center is not None:      # a soft key on the hero so it is the brightest, cleanest thing in frame
        ad = bpy.data.lights.new("hero_key", "AREA"); ad.size = 1.6; ad.energy = hero_energy; ad.color = lin("#fff1e0")[:3]
        ao = bpy.data.objects.new("hero_key", ad); COLL.objects.link(ao)
        ao.location = hero_center + Vector((0.9, -2.4, 1.3)); ao.rotation_euler = look_at_rot(hero_center - ao.location)
    w = bpy.data.worlds.new("lp_world"); sc.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = lin(C["world"][0]); bg.inputs[1].default_value = C["world"][1]

def render_setup(x, y, samples, transparent=False):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples; sc.cycles.seed = 0
    sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    try: sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    sc.cycles.max_bounces = 4; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 2; sc.cycles.transmission_bounces = 2
    sc.cycles.transparent_max_bounces = 8
    sc.cycles.sample_clamp_indirect = 4.0
    sc.render.resolution_x = x; sc.render.resolution_y = y; sc.render.resolution_percentage = 100
    sc.render.film_transparent = transparent
    sc.render.image_settings.file_format = "PNG"; sc.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    sc.view_settings.view_transform = "Standard"; sc.view_settings.look = "None"
    sc.view_settings.exposure = 0; sc.view_settings.gamma = 1
    for attr in dir(sc.render):      # no date/time/render-time metadata in the PNG: the same scene gives the same bytes
        if attr.startswith("use_stamp") and isinstance(getattr(sc.render, attr), bool):
            try: setattr(sc.render, attr, False)
            except Exception: pass

def strip_png_text(path):
    """drop the tEXt chunks Cycles writes (render and sync times), so the same scene gives byte-identical files"""
    import struct
    d = open(path, "rb").read(); out = [d[:8]]; i = 8
    while i < len(d):
        n = struct.unpack(">I", d[i:i + 4])[0]; t = d[i + 4:i + 8]
        if t not in (b"tEXt", b"zTXt", b"iTXt"): out.append(d[i:i + 12 + n])
        i += 12 + n
    open(path, "wb").write(b"".join(out))

def reset():
    global COLL
    _MATS.clear()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    COLL = bpy.context.scene.collection

def render_game(S, out, samples, scale):
    global CX, CZ
    W, H = S["world"]; C = PAL.get(S.get("mood", "day"), PAL["day"])
    reset()
    CX = W / 2 * U; CZ = -EYE * U
    cd = bpy.data.cameras.new("cam"); cd.type = "PERSP"; cd.sensor_fit = "HORIZONTAL"; cd.sensor_width = 36
    cd.lens = 36 * D / (W * U); cd.shift_y = (EYE - H / 2) / W * (1 if W >= H else W / H); cd.clip_start = 0.5; cd.clip_end = 300
    cam = bpy.data.objects.new("cam", cd); COLL.objects.link(cam); cam.location = (CX, -D, CZ); cam.rotation_euler = (math.pi / 2, 0, 0)
    bpy.context.scene.camera = cam
    build_sky(S, C, W, H)
    if S.get("sun"): build_sun(S, C)
    if S.get("far"): build_far(S, C, W, H)
    build_clouds(S, C, W, H)
    build_mid(S, C, W, H)
    build_haze(S, C, W, H)
    build_platforms(S, C, W, H)
    build_hazards(S, C, W, H)
    build_lines(S, C)
    build_trail(S, C)
    build_pickups(S, C)
    hero = S["hero"]
    build_hero(S, C)
    lights(C, P(hero["x"] + hero["size"] / 2, hero["y"] + hero["size"] / 2, 0))
    render_setup(round(W * 2 * scale), round(H * 2 * scale), samples)
    sc = bpy.context.scene; sc.render.filepath = os.path.join(out, "game3d.png")
    t = time.perf_counter(); bpy.ops.render.render(write_still=True); strip_png_text(sc.render.filepath)
    return time.perf_counter() - t

def render_hero(S, out, samples, scale):
    global CX, CZ
    C = PAL.get(S.get("mood", "day"), PAL["day"])
    reset(); CX = CZ = 0.0
    h = dict(S["hero"]); h["x"], h["y"] = -h["size"] / 2, -h["size"] / 2; S2 = dict(S); S2["hero"] = h
    obs = build_hero(S2, C)
    pts = [o.matrix_world @ v.co for o in obs for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    ctr = (lo + hi) / 2; rad = max((p - ctr).length for p in pts)
    # a shadow catcher under the hero: the card gets a soft contact shadow and nothing else
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=rad * 3)
    fl = obj_from_bm(bm, "floor", mat("#ffffff")); fl.location = (ctr.x, ctr.y, lo.z); fl.is_shadow_catcher = True
    cd = bpy.data.cameras.new("cam"); cd.lens = 70; cd.sensor_width = 36
    cam = bpy.data.objects.new("cam", cd); COLL.objects.link(cam)
    f = -1 if h.get("facing", 1) < 0 else 1
    direc = Vector((f * 0.62, -1.0, 0.36)).normalized(); dist = rad / math.tan(math.atan(18 / 70)) * 1.22
    cam.location = ctr + direc * dist; cam.rotation_euler = look_at_rot(ctr - cam.location)
    bpy.context.scene.camera = cam
    lights(dict(C, key=(mixhex(C["key"][0], "#ffffff", 0.6), 3.2)), ctr, 14)   # a neutral key: the portrait shows the true colours
    rim = bpy.data.lights.new("rim", "AREA"); rim.size = 1.0; rim.energy = 22; rim.color = lin(C["halo"])[:3]
    ro = bpy.data.objects.new("rim", rim); COLL.objects.link(ro); ro.location = ctr + Vector((-f * 1.2, 1.6, 1.0)); ro.rotation_euler = look_at_rot(ctr - ro.location)
    n = round(800 * scale); render_setup(n, n, samples, transparent=True)
    sc = bpy.context.scene; sc.render.filepath = os.path.join(out, "hero3d.png")
    t = time.perf_counter(); bpy.ops.render.render(write_still=True); strip_png_text(sc.render.filepath)
    return time.perf_counter() - t

def main():
    a = _inputs()
    raw = open(a["scene"], "rb").read(); scene = json.loads(raw); S = scene.get("game", scene)
    out = a["out"]; os.makedirs(out, exist_ok=True)
    rec = {"look": "low-poly-3d", "scene": os.path.abspath(a["scene"]), "scene_sha256": hashlib.sha256(raw).hexdigest(),
           "title": S.get("title"), "mood": S.get("mood"), "blender": bpy.app.version_string, "engine": "CYCLES (CPU, OIDN denoise)",
           "samples": a["samples"], "scale": a["scale"], "seconds": {}}
    if a["only"] in ("", "game"): rec["seconds"]["game"] = round(render_game(S, out, a["samples"], a["scale"]), 1); rec["game"] = "game3d.png"
    if a["only"] in ("", "hero"): rec["seconds"]["hero"] = round(render_hero(S, out, a["samples"], a["scale"]), 1); rec["hero"] = "hero3d.png"
    json.dump(rec, open(os.path.join(out, "render3d.json"), "w"), indent=1)
    print(json.dumps(rec))
    return rec

main()
