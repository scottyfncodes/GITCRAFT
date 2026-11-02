"""Scene composition: assemble finished assets into one 3D scene. Needs bpy.

compose(spec) imports GLBs (files, or library assets resolved to their GLB export), places
them (location/rotation/scale) or attaches them to another item's socket_* empty
("boat:socket_sail"), adds an ocean plane, sun and sky, renders a hero image and a thumbnail
with Cycles, saves the .blend and exports the scene as one GLB (all clips kept), then validates
the GLB (structure + Khronos). The result has the same shape as run_pipeline's, so it is a job
and a library version like any other MeshCraft deliverable.
Moved here from ForgeCraft's Blender runner in the 3D Department consolidation.
"""
import json, math, os, time
import bpy
from mathutils import Vector
from . import core, kit

PREFER = ("web-pbr", "three-web-atlas", "three-web-toon", "godot-glb")   # which export of a library asset goes into a scene


def resolve(item):
    """An item's GLB: its `file`, or the best GLB export of library asset `asset` (version optional)."""
    if item.get("file"): return item["file"]
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import _gitcraft3d  # noqa: F401
    from gitcraft3d import library
    md = library.get(item["asset"], item.get("version"))
    glbs = [f for f in md["files"] if f["kind"] == "export" and f["path"].endswith(".glb")]
    if not glbs: raise ValueError(f"library asset `{item['asset']}` has no GLB export")
    rank = lambda f: next((i for i, p in enumerate(PREFER) if f".{p}." in f["path"]), len(PREFER))
    return os.path.join(md["dir"], sorted(glbs, key=rank)[0]["path"])


def _hex(h):
    h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


SKY = {"sky": "#7CCBF2", "golden": "#FFB27A", "dusk": "#3B2350"}


def compose(spec):
    aid = spec["asset_id"]; out = spec["out_dir"]; t0 = time.time()
    paths = {"blend": os.path.join(out, "source", f"{aid}.blend"), "exports": os.path.join(out, "exports"), "previews": os.path.join(out, "previews")}
    for d in (os.path.dirname(paths["blend"]), paths["exports"], paths["previews"]): os.makedirs(d, exist_ok=True)
    kit.reset()
    root = kit.empty(aid, (0, 0, 0)); placed = []
    for item in spec["items"]:
        f = resolve(item); before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=f)
        new = [o for o in bpy.data.objects if o not in before]
        for a in [o for o in new if o.type == "ARMATURE"]:     # importer bone display shapes
            for pb in a.pose.bones:
                sh, pb.custom_shape = pb.custom_shape, None
                if sh and sh.name in bpy.data.objects: new.remove(sh); bpy.data.objects.remove(sh, do_unlink=True)
        holder = kit.empty(item.get("name") or os.path.splitext(os.path.basename(f))[0])
        for o in new:
            if o.parent is None: o.parent = holder
        if item.get("attach_to"):
            host, sock = item["attach_to"].split(":")
            hobj = bpy.data.objects.get(host)
            if hobj is None: raise ValueError(f"attach_to: no item named `{host}` placed before `{holder.name}`")
            s = next((o for o in hobj.children_recursive if o.name.split(".")[0] == sock), None)
            if s is None: raise ValueError(f"attach_to: `{host}` has no `{sock}` (sockets: {[o.name for o in hobj.children_recursive if o.name.startswith('socket_')]})")
            bpy.context.view_layer.update()
            holder.matrix_world = s.matrix_world.copy(); holder.parent = hobj; holder.matrix_parent_inverse = hobj.matrix_world.inverted()
        else:
            holder.location = item.get("location", (0, 0, 0)); holder.rotation_euler = [math.radians(a) for a in item.get("rotation", (0, 0, 0))]
            holder.scale = [item.get("scale", 1)] * 3
            holder.parent = root
        placed.append({"name": holder.name, "file": f, "asset": item.get("asset"), "objects": len(new), "attach_to": item.get("attach_to")})
    # ocean
    size = spec.get("ocean_size", 160)
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=48, y_subdivisions=48, size=size)
    w = bpy.context.active_object; w.name = "ocean"
    for v in w.data.vertices: v.co.z = 0.08 * math.sin(v.co.x * 0.4) * math.cos(v.co.y * 0.33)
    m = bpy.data.materials.new("GC_Ocean"); m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*_hex("#1A7FA8"), 1); b.inputs["Roughness"].default_value = 0.08
    w.data.materials.append(m); w.parent = root
    # light, sky, camera, render
    s = bpy.context.scene
    wd = bpy.data.worlds.new("GC_Sky"); s.world = wd; wd.use_nodes = True
    bg = wd.node_tree.nodes["Background"]; bg.inputs[0].default_value = (*_hex(SKY.get(spec.get("sky", "sky"), spec.get("sky", "#7CCBF2"))), 1)
    elev, tilt, az = spec.get("sun", [48, 8, 140])
    sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 1.2 + 2.6 * math.sin(math.radians(elev))
    so = bpy.data.objects.new("sun", sun); s.collection.objects.link(so); so.rotation_euler = (math.radians(90 - elev), math.radians(tilt), math.radians(az))
    cd = bpy.data.cameras.new("cam"); cd.lens = spec.get("lens", 32); cam = bpy.data.objects.new("cam", cd); s.collection.objects.link(cam)
    cam.location = spec.get("camera", (34, -38, 16)); s.camera = cam
    tgt = kit.empty("cam_target", spec.get("look_at", (0, -8, 2)))
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    s.render.engine = "CYCLES"; s.cycles.device = "CPU"; s.cycles.samples = int(spec.get("samples", 32))
    try: s.cycles.use_denoising = True
    except Exception: pass
    s.render.film_transparent = False; s.view_settings.view_transform = "Standard"
    s.render.image_settings.file_format = "PNG"; s.render.image_settings.color_mode = "RGB"
    s.frame_set(int(spec.get("frame", 10)))
    previews = []
    for name, (rx, ry) in (("hero", spec.get("resolution", (1280, 720))), ("three_quarter", (512, 512))):
        s.render.resolution_x, s.render.resolution_y = rx, ry
        s.render.filepath = os.path.join(paths["previews"], f"{aid}_{name}.png"); bpy.ops.render.render(write_still=True)
        previews.append(core._file(s.render.filepath, "preview", view=name))
    for o in (so, cam, tgt): bpy.data.objects.remove(o, do_unlink=True)
    s.frame_set(0)
    s["gitcraft_brief"] = json.dumps({"asset_id": aid, "template": "scene", "items": spec["items"]}, default=str)
    bpy.ops.wm.save_as_mainfile(filepath=paths["blend"], compress=True)
    glb = os.path.join(paths["exports"], f"{aid}.scene.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", export_yup=True, export_apply=True, export_materials="EXPORT",
                              export_animations=True, export_animation_mode="ACTIONS", export_skins=True, export_extras=False, export_image_format="AUTO")
    checks = core.validate_gltf(glb) + core.khronos_validate(glb)
    info = core.inspect_file(glb)
    checks.append({"level": "pass" if info["triangles"] else "fail", "check": "roundtrip_reimport",
                   "detail": f"re-imported scene: {info['triangles']} tris, size {info['size_m']} m, clips {info['actions']}"})
    actions = sorted({a for p in placed for a in []} | set(info["actions"]))
    return {"asset_id": aid, "build": {"blend": core._file(paths["blend"], "blend"), "actions": actions, "contract": {"root": aid, "ground": False, "mixed_materials": True}},
            "previews": previews, "exports": [dict(core._file(glb, "export", profile="scene-glb", format="glb", engine="any glTF engine"), roundtrip=info)],
            "validation": {"checks": checks, "summary": core.summarize(checks)}, "placed": placed, "seconds": round(time.time() - t0, 1)}
