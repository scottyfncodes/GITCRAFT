"""Imported mesh: bring a mesh made elsewhere into MeshCraft's pipeline.

For photogrammetry (Meshroom), AI generation (TripoSR, Hunyuan3D), downloads or hand-made
files: import (GLB/glTF/FBX/OBJ/STL/PLY), optionally clean a scan (crop to the subject, drop
the floor, disconnected fragments and floating outliers), clean geometry, decimate to a triangle
budget, put it on the ground at the origin and rescale. Its own materials, textures and vertex
colours are kept; the web-pbr profile bakes them into PBR maps. Moved here from ForgeCraft's
Blender runner in the 3D Department consolidation (MeshCraft owns all Blender mesh work).
The MCP tool `process_mesh` runs this template through run_pipeline.
"""
import os
import bpy, bmesh
from mathutils import Vector
from .. import kit

META = {"id": "mesh_import", "title": "Imported mesh (scan, AI or external file)", "category": "import",
        "description": "Import + clean a mesh made elsewhere: scan crop, fragment/outlier removal, cleanup, decimation, grounding, rescale. Keeps its own materials.",
        "params": {"path": {"type": "string", "default": "", "description": "mesh file inside a GITCRAFT root (glb, gltf, fbx, obj, stl, ply)"},
                   "crop": {"type": "number", "default": 0, "description": "scans: keep faces within crop × the scene half-width of the centre (0 = off)"},
                   "crop_floor": {"type": "boolean", "default": True, "description": "with crop: also drop the floor"},
                   "target_size": {"type": "number", "default": 0, "description": "rescale so the largest side is this many metres (0 = keep)"},
                   "max_tris": {"type": "integer", "default": 20000}, "recenter": {"type": "boolean", "default": True}},
        "roles": [], "budget_tris": 200000}


def default_roles(params):
    return {}


def _import(path):
    ext = os.path.splitext(path)[1].lower(); before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    elif ext == ".stl": bpy.ops.wm.stl_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    elif ext == ".ply": bpy.ops.wm.ply_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    else: raise ValueError(f"mesh_import: unsupported format {ext} (glb, gltf, fbx, obj, stl, ply)")
    new = [o for o in bpy.data.objects if o not in before]
    for a in [o for o in new if o.type == "ARMATURE"]:   # the glTF importer's bone display shapes are not geometry
        for pb in a.pose.bones:
            sh, pb.custom_shape = pb.custom_shape, None
            if sh and sh.name in bpy.data.objects: bpy.data.objects.remove(sh, do_unlink=True); new = [o for o in new if o != sh]
    return new


def _bounds(meshes):
    pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _edit(o, fn):
    bm = bmesh.new(); bm.from_mesh(o.data); n = fn(bm, o.matrix_world); bm.to_mesh(o.data); bm.free(); o.data.update(); return n


def crop_scan(meshes, crop, floor=True):
    """Scans include the floor and surroundings around a centred subject."""
    lo, hi = _bounds(meshes); c = (lo + hi) / 2; r = crop * max(hi.x - lo.x, hi.y - lo.y) / 2
    report = {"radius": round(r, 3)}

    def radial(bm, mw):
        dead = [f for f in bm.faces if ((mw @ f.calc_center_median()) - c).xy.length > r]
        bmesh.ops.delete(bm, geom=dead, context="FACES"); return len(dead)
    report["outside_radius"] = sum(_edit(o, radial) for o in meshes)
    if floor:
        lo2, hi2 = _bounds(meshes); fl = lo2.z + 0.04 * (hi2.z - lo2.z)

        def floor_fn(bm, mw):
            dead = [f for f in bm.faces if all((mw @ v.co).z <= fl for v in f.verts)]
            bmesh.ops.delete(bm, geom=dead, context="FACES"); return len(dead)
        report["floor"] = sum(_edit(o, floor_fn) for o in meshes)

    def fragments(bm, mw):   # disconnected pieces smaller than 3% of the largest
        bm.faces.ensure_lookup_table(); seen, islands = set(), []
        for f in bm.faces:
            if f.index in seen: continue
            stack, isl = [f], []; seen.add(f.index)
            while stack:
                g = stack.pop(); isl.append(g)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen: seen.add(h.index); stack.append(h)
            islands.append(isl)
        if not islands: return 0
        big = max(len(i) for i in islands); dead = [f for i in islands if len(i) < 0.03 * big for f in i]
        bmesh.ops.delete(bm, geom=dead, context="FACES"); return len(dead)
    report["fragments"] = sum(_edit(o, fragments) for o in meshes)

    def floating(bm, mw):    # joined by slivers: a vertical gap > 15% of the height means the rest floats
        zs = sorted((((mw @ f.calc_center_median()).z, f) for f in bm.faces), key=lambda t: t[0])
        if len(zs) < 10: return 0
        H = zs[-1][0] - zs[0][0]
        cut = next((zs[i][0] for i in range(len(zs) - 1) if zs[i + 1][0] - zs[i][0] > 0.15 * H), None)
        if cut is None: return 0
        dead = [f for z, f in zs if z > cut]; bmesh.ops.delete(bm, geom=dead, context="FACES"); return len(dead)
    report["floating"] = sum(_edit(o, floating) for o in meshes)
    return report


def build(ctx):
    p = ctx.params; path = p.get("path")
    if not path or not os.path.isfile(path): raise ValueError(f"mesh_import: `path` must be an existing mesh file (got {path!r})")
    root = kit.empty(ctx.brief["asset_id"], (0, 0, 0))
    objs = _import(path)
    meshes = [o for o in objs if o.type == "MESH"]
    if not meshes: raise ValueError(f"mesh_import: {os.path.basename(path)} contains no mesh")
    stats = {"imported_objects": len(objs), "imported_triangles": sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in meshes)}
    for o in meshes:   # bake parent transforms into the meshes so cleanup and grounding work in world space
        kit.link(o) if o.name not in bpy.context.scene.objects else None
        for x in bpy.context.selected_objects: x.select_set(False)
        o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM"); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if p.get("crop"): stats["crop"] = crop_scan(meshes, float(p["crop"]), p.get("crop_floor", True))
    merged = 0
    for o in meshes:   # merge doubles, drop loose and degenerate geometry, consistent normals
        def clean(bm, mw):
            n = len(bm.verts)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_edges], context="VERTS")
            bmesh.ops.dissolve_degenerate(bm, dist=0.00005, edges=bm.edges)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces); return n - len(bm.verts)
        merged += _edit(o, clean)
    stats["merged_vertices"] = merged
    meshes = [o for o in meshes if o.data.polygons]
    tris = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in meshes); budget = int(p.get("max_tris") or 20000)
    if tris > budget:
        for o in meshes:
            m = o.modifiers.new("decimate", "DECIMATE"); m.ratio = budget / tris; m.use_collapse_triangulate = True
            bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier=m.name)
    stats["triangles"] = sum(sum(len(f.vertices) - 2 for f in o.data.polygons) for o in meshes)
    lo, hi = _bounds(meshes)
    if p.get("recenter", True):
        off = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        for o in meshes: o.data.transform(__import__("mathutils").Matrix.Translation(-off))
        lo, hi = lo - off, hi - off
    if p.get("target_size"):
        k = float(p["target_size"]) / max(hi - lo)
        for o in meshes: o.data.transform(__import__("mathutils").Matrix.Scale(k, 4))
        stats["scale"] = round(k, 5)
    for o in meshes:
        if not o.data.materials:   # something to bake and export
            m = bpy.data.materials.new("GC_Imported"); o.data.materials.append(m)
        for m in [m for m in o.data.materials if m]:   # vertex colours (AI meshes) feed the base colour the bake reads
            if o.data.color_attributes and m.use_nodes:
                b = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if b and not b.inputs["Base Color"].is_linked:
                    vc = m.node_tree.nodes.new("ShaderNodeVertexColor"); vc.layer_name = o.data.color_attributes[0].name
                    m.node_tree.links.new(vc.outputs["Color"], b.inputs["Base Color"])
        o.parent = root
    for o in [o for o in objs if o.type not in ("MESH", "ARMATURE") and o.name in bpy.data.objects]:
        bpy.data.objects.remove(o, do_unlink=True)   # importer cameras/lights/empties are not the asset
    return {"root": root.name, "contract": {"root": root.name}, "expect": {"base_z": 0.0} if p.get("recenter", True) else {},
            "import": dict(stats, source=os.path.basename(path))}
