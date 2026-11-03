"""Overlap audit: do any two parts of an assembly intersect, including while their moving parts move?

Give it the parts of an assembled model (a ship and its upgrades, a character and its props, a scene); it builds a
BVH tree per part and reports every pair whose triangles intersect. Moving parts (a crane, a turret, a rotor) are
swept through their motion ranges, every combination of poses, and static pairs are tested once.

A part is one of:
  {"name": "boat", "file": "boat.glb"}                       a whole model file (GLB/glTF/FBX/OBJ/STL/PLY/.blend)
  {"name": "sails", "file": "boat.glb", "materials": [...], "min": [x,y,z], "max": [x,y,z]}
                                                             only the faces of those materials / inside that box
  {"name": "turret", "file": "turret.glb", "node": "mount"}  only the subtree of one node
  {"name": "captain", "cylinder": {"radius": 0.24, "height": 1.85}}   a proxy volume (also "box": {"size": [x,y,z]})
each with an optional "transform": {"location": [x,y,z], "rotation": [deg x,y,z], "scale": s | [x,y,z]}.
Parts that name the same file with the same transform share one import, so filters can split a model into pieces.

Motion: [{"part": "turret", "node": "mount", "axis": "y", "from": 0, "to": 330, "steps": 12}, ...] rotates that node
about its own origin (degrees, added to its rest rotation). Contacts: [["turret", "deck"], ...] pairs that touch on
purpose (bolted, resting, lashed) and are not reported.

Coordinates are glTF/three.js (Y up, +Z forward: "frame": "gltf", the default) or Blender's (Z up: "frame": "blender").
Mesh-level results: a pair "overlaps" when any of its triangles intersect (Blender BVHTree.overlap), or when one
part sits entirely inside the other ("contained": no surfaces cross, so the triangle test alone can't see it; checked
by ray parity along three axes from a few of its vertices).
"""
import itertools, json, math, os
import bpy
from mathutils import Vector, Matrix, Quaternion, Euler
from mathutils.bvhtree import BVHTree

AXES_GLTF = {"x": Vector((1, 0, 0)), "y": Vector((0, 0, 1)), "z": Vector((0, -1, 0))}
AXES_BLENDER = {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}


def _to_b(v, frame):
    return Vector((v[0], -v[2], v[1])) if frame == "gltf" else Vector(v)


def _from_b(v, frame):
    return (v.x, v.z, -v.y) if frame == "gltf" else (v.x, v.y, v.z)


def _meshopt_plain(path):
    """Blender's importer can't read EXT_meshopt_compression (the bpy wheel has no meshopt bridge): decode such a
    GLB first with engine_check/meshopt_decode.mjs (three's decoder) into a temp GLB. Other files pass through."""
    if not path.lower().endswith(".glb"): return path
    import struct, subprocess, tempfile
    with open(path, "rb") as f:
        head = f.read(20); n = struct.unpack("<I", head[12:16])[0]; j = json.loads(f.read(n))
    if "EXT_meshopt_compression" not in (j.get("extensionsUsed") or []): return path
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(tempfile.mkdtemp(prefix="audit_meshopt_"), os.path.basename(path))
    r = subprocess.run(["node", os.path.join(here, "engine_check", "meshopt_decode.mjs"), path, out], capture_output=True, text=True, timeout=120)
    if r.returncode != 0: raise RuntimeError(f"audit: couldn't decode meshopt GLB {path}: {r.stderr[-800:]}")
    return out


def _import(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"): bpy.ops.import_scene.gltf(filepath=_meshopt_plain(path))
    elif ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".stl": bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".ply": bpy.ops.wm.ply_import(filepath=path)
    elif ext == ".blend":
        with bpy.data.libraries.load(path, link=False) as (src, dst): dst.objects = list(src.objects)
        for o in dst.objects:
            if o is not None: bpy.context.scene.collection.objects.link(o)
    else: raise ValueError(f"audit: unsupported file type {ext}")
    return [o for o in bpy.data.objects if o not in before]


def _transform(objs, t, frame):
    if not t: return
    loc = _to_b(t.get("location", (0, 0, 0)), frame)
    rx, ry, rz = (math.radians(a) for a in t.get("rotation", (0, 0, 0)))
    rot = Euler((rx, -rz, ry)) if frame == "gltf" else Euler((rx, ry, rz))
    sc = t.get("scale", 1)
    sc = Vector((sc, sc, sc)) if isinstance(sc, (int, float)) else (Vector((sc[0], sc[2], sc[1])) if frame == "gltf" else Vector(sc))
    m = Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal((*sc, 1))
    for o in objs:
        if o.parent is None: o.matrix_world = m @ o.matrix_world
    bpy.context.view_layer.update()


def _proxy(p, frame):
    if "cylinder" in p:
        c = p["cylinder"]
        bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=c["radius"], depth=c["height"], location=(0, 0, c["height"] / 2))
    else:
        s = p["box"]["size"]
        bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
        o = bpy.context.active_object
        o.scale = (s[0], s[2], s[1]) if frame == "gltf" else tuple(s)
        o.location = (0, 0, (s[1] if frame == "gltf" else s[2]) / 2)
    o = bpy.context.active_object
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return [o]


def _subtree(objs, node):
    if not node: return objs
    root = next((o for o in objs if o.name == node or o.name.split(".")[0] == node), None)
    if root is None: raise ValueError(f"audit: node {node!r} not found")
    return [root, *root.children_recursive]


def _faces(objs, p, frame):
    """World-space polygons of the meshes in objs that pass the part's material / region filters."""
    mats = set(p.get("materials") or [])
    lo, hi = p.get("min"), p.get("max")
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in objs:
        if o.type != "MESH": continue
        ev = o.evaluated_get(dg); me = ev.to_mesh(); mw = o.matrix_world
        for poly in me.polygons:
            if mats:
                slot = o.material_slots[poly.material_index] if poly.material_index < len(o.material_slots) else None
                if not slot or not slot.material or slot.material.name.split(".")[0] not in mats: continue
            pts = [mw @ me.vertices[i].co for i in poly.vertices]
            if lo or hi:
                c = _from_b(sum(pts, Vector()) / len(pts), frame)
                if lo and any(c[k] < lo[k] for k in range(3)): continue
                if hi and any(c[k] > hi[k] for k in range(3)): continue
            base = len(verts); verts += pts; polys.append(tuple(range(base, base + len(pts))))
        ev.to_mesh_clear()
    return verts, polys


_DIRS = (Vector((1, 0, 0.0123)).normalized(), Vector((0.0117, 1, 0)).normalized(), Vector((0.0131, 0, 1)).normalized())


def _inside(tree, p):
    """Ray parity along three skewed axes: odd crossings on all three = inside a closed surface."""
    for d in _DIRS:
        n, o = 0, p.copy()
        for _ in range(64):
            hit = tree.ray_cast(o, d)
            if hit[0] is None: break
            n += 1; o = hit[0] + d * 1e-4
        if n % 2 == 0: return False
    return True


def _contained(a, b):
    """Is part a (verts) inside part b (tree)? Sampled at a few spread vertices; all must agree."""
    va, tb = a, b
    if not va or tb is None: return False
    idx = sorted({0, len(va) // 3, (2 * len(va)) // 3, len(va) - 1})
    return all(_inside(tb, va[i]) for i in idx)


def run(spec):
    frame = spec.get("frame", "gltf")
    axes = AXES_GLTF if frame == "gltf" else AXES_BLENDER
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts, imports = {}, {}
    if spec.get("scene") and not spec.get("parts"):     # an assembled scene: one part per top-level object
        objs = _import(spec["scene"])
        for o in objs:
            if o.parent is None: parts[o.name] = {"spec": {"name": o.name}, "objs": [o, *o.children_recursive]}
    for p in spec.get("parts", []):
        if "file" in p:
            key = (os.path.realpath(p["file"]), json.dumps(p.get("transform") or {}, sort_keys=True))
            if key not in imports:
                imports[key] = _import(p["file"]); _transform(imports[key], p.get("transform"), frame)
            objs = _subtree(imports[key], p.get("node"))
        else:
            objs = _proxy(p, frame); _transform(objs, p.get("transform"), frame)
        parts[p["name"]] = {"spec": p, "objs": objs}
    contacts = {frozenset(c) for c in spec.get("contacts", [])}
    motion = spec.get("motion", [])
    for m in motion:
        if m["part"] not in parts: raise ValueError(f"audit: motion on unknown part {m['part']!r}")
        node = _subtree(parts[m["part"]]["objs"], m["node"])[0]
        node.rotation_mode = "QUATERNION"
        m["_node"], m["_rest"] = node, node.rotation_quaternion.copy()
        m["_angles"] = [m["from"] + (m["to"] - m["from"]) * i / max(1, m.get("steps", 1) - 1) for i in range(max(1, m.get("steps", 1)))]
    moving = {m["part"] for m in motion}
    poses = list(itertools.product(*[m["_angles"] for m in motion])) or [()]
    if len(poses) > spec.get("max_poses", 5000): raise ValueError(f"audit: {len(poses)} poses (max_poses {spec.get('max_poses', 5000)})")

    verts = {}
    def tree(name):
        v, f = _faces(parts[name]["objs"], parts[name]["spec"], frame)
        verts[name] = v
        return BVHTree.FromPolygons(v, f) if f else None

    static = {n: tree(n) for n in parts if n not in moving}
    names = sorted(parts)
    pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:] if frozenset((a, b)) not in contacts]
    hits, tested = {}, 0
    for k, pose in enumerate(poses):
        for m, ang in zip(motion, pose):
            m["_node"].rotation_quaternion = m["_rest"] @ Quaternion(axes[m["axis"]], math.radians(ang))
        bpy.context.view_layer.update()
        trees = dict(static); trees.update({n: tree(n) for n in moving})
        for a, b in pairs:
            if k and a not in moving and b not in moving: continue      # static pairs: once
            tested += 1
            if trees[a] is None or trees[b] is None: continue
            n = len(trees[a].overlap(trees[b]))
            inside = None
            if not n:
                inside = f"{a} inside {b}" if _contained(verts[a], trees[b]) else (f"{b} inside {a}" if _contained(verts[b], trees[a]) else None)
            if n or inside:
                h = hits.setdefault(f"{a} x {b}", {"parts": [a, b], "triangles": 0, "poses": []})
                h["triangles"] = max(h["triangles"], n)
                if inside: h["contained"] = inside
                if motion and len(h["poses"]) < 8:
                    h["poses"].append({m["part"] + ":" + m["node"]: round(ang, 2) for m, ang in zip(motion, pose)})
    empty = [n for n in names if n not in moving and static[n] is None]
    return {"clean": not hits, "parts": names, "moving": sorted(moving), "poses": len(poses), "pairs": len(pairs),
            "pair_tests": tested, "contacts_skipped": [sorted(c) for c in contacts], "empty_parts": empty, "overlaps": hits}
