"""Helpers for the studio's Blender scripts (run in MeshCraft's bpy venv by core/runners.py)."""
import contextlib, json, math, os, sys, traceback

def request():
    return json.load(open(sys.argv[-1]))

def main(fn):
    """Run fn(req) -> dict and write the result JSON; any exception is reported, not raised."""
    req = request(); out = req["_result"]
    try:
        with contextlib.redirect_stdout(sys.stderr):
            res = fn(req) or {}
    except Exception as e:
        traceback.print_exc()
        res = {"error": f"{type(e).__name__}: {e}"}
    json.dump(res, open(out, "w"), default=str)

def reset():
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene

def import_any(path):
    import bpy
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"): bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=True)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".stl": bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".bvh": bpy.ops.import_anim.bvh(filepath=path, axis_forward="-Z", axis_up="Y", update_scene_fps=True)
    elif ext == ".blend":
        with bpy.data.libraries.load(path) as (src, dst): dst.objects = src.objects
        for o in dst.objects:
            if o: bpy.context.scene.collection.objects.link(o)
    else: raise ValueError(f"cannot import {ext}")
    return [o for o in bpy.data.objects if o not in before]

def export_glb(path, animations=True, selected=None):
    import bpy
    kw = dict(filepath=path, export_format="GLB", export_yup=True, export_apply=False, export_animations=animations)
    if selected is not None:
        bpy.ops.object.select_all(action="DESELECT")
        for o in selected: o.select_set(True)
        kw["use_selection"] = True
    if animations: kw.update(export_animation_mode="ACTIONS", export_force_sampling=True)
    bpy.ops.export_scene.gltf(**kw)
    return path

def bounds(objs):
    from mathutils import Vector
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type == "MESH" for c in o.bound_box]
    if not pts: return (Vector((0, 0, 0)), Vector((0, 0, 0)))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi

def cycles(scene, res=(640, 360), samples=16, transparent=False):
    scene.render.engine = "CYCLES"; scene.cycles.device = "CPU"; scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    try: scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    scene.render.resolution_x, scene.render.resolution_y = res; scene.render.resolution_percentage = 100
    scene.render.film_transparent = transparent; scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    scene.view_settings.view_transform = "AgX" if "AgX" in [v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"

def world_color(scene, rgb=(0.6, 0.75, 0.9), strength=1.0):
    import bpy
    w = scene.world or bpy.data.worlds.new("World"); scene.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background") or w.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = (*rgb, 1); bg.inputs[1].default_value = strength
    out = next((n for n in w.node_tree.nodes if n.type == "OUTPUT_WORLD"), None) or w.node_tree.nodes.new("ShaderNodeOutputWorld")
    w.node_tree.links.new(bg.outputs[0], out.inputs[0])
    return w

def look_at(obj, target):
    from mathutils import Vector
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
