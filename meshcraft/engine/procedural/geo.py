"""Geometry helpers for MeshCraft's procedural builders (moved from ForgeCraft's Blender
runner during the 3D Department consolidation). Runs inside Blender's Python.

Conventions: metres, Z up in Blender; glTF export converts to Y up, so Blender -Y is the
glTF/three.js forward (+Z), matching TIDEBREAKERS' shipModel.ts (bow at +Z).
Materials come from the template's palette roles (kit.Materials) through mat(): see
engine/procedural/__init__.py. Rendering, baking and export are MeshCraft core's job."""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
# TIDEBREAKERS palette (creative/branding/palette/tidebreakers-palette.json) plus neutrals.
PALETTE = {
    "lagoon": "#1FB5B0", "aqua": "#7FE3D6", "sea": "#1A7FA8", "deep": "#0E3B66", "midnight": "#0A2142",
    "gold": "#F4C542", "gold_deep": "#C98A12", "amber": "#FF9F2E", "coral": "#FF6B4A", "crimson": "#C0392B",
    "hibiscus": "#E0607E", "cream": "#F6EAD0", "parchment": "#ECDAB4", "palm": "#3FA55A", "jungle": "#1E6B4E",
    "honey": "#D9954F", "timber": "#9A5A2E", "deep_timber": "#5E331B", "plum": "#3B2350", "dusk": "#6A4C93",
    "sky": "#7CCBF2", "sky_high": "#CFF1FF", "sand": "#F7D9A0", "foam": "#E9FBF6",
    "iron": "#4A4F57", "copper": "#C77B4A", "stone": "#8C8A86", "rope": "#C9A46B", "skin": "#E8B48A",
    "white": "#F4F4F0", "black": "#1B1B1F",
}


def hex_rgb(h):
    h = PALETTE.get(h, h).lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(c) for c in srgb)


# ---------------------------------------------------------------- scene
def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.3
    e.location = loc
    link(e)
    if parent: e.parent = parent
    return e


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT") if bpy.context.view_layer.objects else None
    for o in objs: o.select_set(True)
    if objs: bpy.context.view_layer.objects.active = objs[0]


# ---------------------------------------------------------------- materials
MATERIALS = None   # set by procedural.build(): a function (color, kind, rough, metal, emit) -> bpy material


def mat(color, kind="plain", rough=0.65, metal=0.0, emit=0.0, name=None):
    """A palette-role material for `color` (a PALETTE name or #hex). `kind` (wood, cloth, rock…)
    names the role; MeshCraft paints the colour into vertex colours and bakes PBR maps from it."""
    if MATERIALS is None: raise RuntimeError("procedural builders run inside a MeshCraft template (procedural.build)")
    return MATERIALS(PALETTE.get(color, color), kind, rough, metal, emit)


def assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


# ---------------------------------------------------------------- geometry builders
def mesh_obj(name, verts, faces, material=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(); me.update()
    o = link(bpy.data.objects.new(name, me))
    if material: assign(o, material)
    for p in me.polygons: p.use_smooth = smooth
    return o


def prim(kind, name, material=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), **kw):
    ops = {"cube": bpy.ops.mesh.primitive_cube_add, "cyl": bpy.ops.mesh.primitive_cylinder_add,
           "cone": bpy.ops.mesh.primitive_cone_add, "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
           "ico": bpy.ops.mesh.primitive_ico_sphere_add, "torus": bpy.ops.mesh.primitive_torus_add,
           "plane": bpy.ops.mesh.primitive_plane_add, "grid": bpy.ops.mesh.primitive_grid_add}
    ops[kind](location=loc, rotation=rot, **kw)
    o = bpy.context.active_object
    o.name = name
    _canonical(o)
    o.scale = scale
    if material: assign(o, material)
    apply_xf(o)
    return o


def _canonical(o):
    """Fixed element order (MeshCraft kit._canonical): Blender's sphere/ico primitive operators emit
    faces in a varying order between runs, which made identical builds export different GLBs."""
    from ..kit import _canonical as canon
    bm = bmesh.new(); bm.from_mesh(o.data); out = canon(bm); out.to_mesh(o.data); out.free(); o.data.update()


def apply_xf(o):
    select_only([o])
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return o


def shade(o, smooth_angle=None):
    select_only([o])
    if smooth_angle is None:
        bpy.ops.object.shade_flat()
    else:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle))
    return o


def join(objs, name):
    objs = [o for o in objs if o and o.type == "MESH"]
    select_only(objs)
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = name; o.data.name = name
    return o


def solidify(o, t):
    m = o.modifiers.new("solid", "SOLIDIFY"); m.thickness = t; m.offset = 0
    select_only([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return o


def bevel(o, w=0.02, seg=1):
    m = o.modifiers.new("bev", "BEVEL"); m.width = w; m.segments = seg; m.limit_method = "ANGLE"
    select_only([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return o


# ---------------------------------------------------------------- processing stages
def mesh_objects(root):
    out = [root] if root.type == "MESH" else []
    for c in root.children_recursive:
        if c.type == "MESH": out.append(c)
    return out


def tri_count(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == "MESH")


def cleanup(o, merge=0.0005):
    """Merge duplicate vertices, drop loose geometry and degenerate faces, make normals consistent."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    loose = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.dissolve_degenerate(bm, dist=merge * 0.1, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    after = len(bm.verts)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    return {"merged_vertices": before - after}


def decimate(o, max_tris):
    t = tri_count([o])
    if t <= max_tris: return {"tris_before": t, "tris_after": t, "ratio": 1.0}
    ratio = max_tris / t
    m = o.modifiers.new("dec", "DECIMATE"); m.ratio = ratio; m.use_collapse_triangulate = True
    select_only([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return {"tris_before": t, "tris_after": tri_count([o]), "ratio": round(ratio, 4)}


def bounds(objs):
    pts = []
    for o in objs:
        if o.type != "MESH": continue
        dg = bpy.context.evaluated_depsgraph_get()
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        pts += [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    if not pts: return Vector((0, 0, 0)), Vector((1, 1, 1))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi
