"""MeshCraft Blender job runner. Runs in its own process with Blender's Python (`bpy`):

    <venv>/bin/python meshcraft/blender/run.py job.json

job.json: {"op": "generate"|"process"|"bbmodel"|"mixamo"|"scene"|"validate"|"photoset", "out_dir": ...,
           "slug": ..., ...op fields...}
Progress is appended to <out_dir>/_progress.jsonl (one line per stage) so the pipeline
monitor can show live stages; the final result is written to <out_dir>/_result.json.
"""
import base64, json, math, os, sys, time, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Matrix
import mc, gen

JOB = json.load(open(sys.argv[1]))
OUT = JOB["out_dir"]; os.makedirs(OUT, exist_ok=True)
PROG = open(os.path.join(OUT, "_progress.jsonl"), "a", buffering=1)
RESULT = {"op": JOB["op"], "stages": [], "ok": False}


def stage(name):
    def deco(fn):
        def wrapped(*a, **k):
            t0 = time.time()
            PROG.write(json.dumps({"stage": name, "state": "running", "t": time.time()}) + "\n")
            try:
                r = fn(*a, **k)
                rec = {"stage": name, "state": "done", "seconds": round(time.time() - t0, 2)}
                if isinstance(r, dict): rec["info"] = {k: v for k, v in r.items() if k != "paths"}
                RESULT["stages"].append(rec); PROG.write(json.dumps(rec) + "\n")
                return r
            except Exception as e:
                rec = {"stage": name, "state": "failed", "seconds": round(time.time() - t0, 2), "error": f"{type(e).__name__}: {e}"}
                RESULT["stages"].append(rec); PROG.write(json.dumps(rec) + "\n")
                raise
        return wrapped
    return deco


# ------------------------------------------------------------------ importers
def import_any(path):
    ext = os.path.splitext(path)[1].lower()
    before = set(bpy.data.objects)
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
        # drop the icosphere the importer creates as a bone display shape (not part of the asset)
        for a in [o for o in bpy.data.objects if o not in before and o.type == "ARMATURE"]:
            for pb in a.pose.bones:
                sh, pb.custom_shape = pb.custom_shape, None
                if sh and sh.name in bpy.data.objects: bpy.data.objects.remove(sh, do_unlink=True)
    elif ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    elif ext == ".stl": bpy.ops.wm.stl_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    elif ext == ".ply": bpy.ops.wm.ply_import(filepath=path, forward_axis="NEGATIVE_Z", up_axis="Y")
    elif ext == ".bbmodel": return import_bbmodel(path)
    else: raise ValueError(f"unsupported input format {ext}")
    return [o for o in bpy.data.objects if o not in before]


FACE_DIRS = {  # Blockbench face → (axis, sign) of the outward normal, Blockbench is Y-up
    "north": ("z", -1), "south": ("z", 1), "east": ("x", 1), "west": ("x", -1), "up": ("y", 1), "down": ("y", -1)}


def import_bbmodel(path):
    """Blockbench .bbmodel (format 4.x/5.x) → Blender meshes with UVs and embedded textures.
    Cubes only (Blockbench's 'mesh' elements are converted too). 16 Blockbench units = 1 m."""
    d = json.load(open(path))
    res = d.get("resolution", {"width": 16, "height": 16})
    imgs, mats = [], []
    tmp = os.path.join(OUT, "_bb_textures"); os.makedirs(tmp, exist_ok=True)
    for i, t in enumerate(d.get("textures", [])):
        src = t.get("source", "")
        if src.startswith("data:image/png;base64,"):
            p = os.path.join(tmp, f"{i}_{t.get('name', 'tex')}".replace("/", "_"))
            if not p.endswith(".png"): p += ".png"
            open(p, "wb").write(base64.b64decode(src.split(",", 1)[1]))
            img = bpy.data.images.load(p); img.pack()
        else:
            img = None
        imgs.append((img, t.get("uv_width", t.get("width", res["width"])), t.get("uv_height", t.get("height", res["height"]))))
        m = bpy.data.materials.new(f"BB_{t.get('name', i)}")
        if getattr(m, "node_tree", None) is None: m.use_nodes = True
        if img:
            n = m.node_tree.nodes.new("ShaderNodeTexImage"); n.image = img; n.interpolation = "Closest"
            m.node_tree.links.new(n.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
        mats.append(m)
    groups = {g["uuid"]: g for g in d.get("groups", []) if isinstance(g, dict)}
    objs = []
    U = 1 / 16.0
    for el in d.get("elements", []):
        if el.get("type", "cube") != "cube" or el.get("visibility") is False: continue
        f, t = Vector(el["from"]), Vector(el["to"])
        infl = el.get("inflate", 0); f -= Vector((infl,) * 3); t += Vector((infl,) * 3)
        verts, faces, uvs, fmat = [], [], [], []
        for fname, (ax, sg) in FACE_DIRS.items():
            fd = el.get("faces", {}).get(fname)
            if fd is None or fd.get("enabled") is False or fd.get("texture") is None and fname not in el.get("faces", {}): continue
            # four corners of the face in Blockbench space, ordered to match uv [u1,v1,u2,v2]
            x0, y0, z0 = f; x1, y1, z1 = t
            C = {"north": [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)],
                 "south": [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)],
                 "east": [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)],
                 "west": [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)],
                 "up": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
                 "down": [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)]}[fname]
            u1, v1, u2, v2 = fd.get("uv", [0, 0, 1, 1])
            ti = fd.get("texture"); ti = ti if isinstance(ti, int) and ti < len(imgs) else 0
            tw, th = (imgs[ti][1], imgs[ti][2]) if imgs else (res["width"], res["height"])
            quv = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
            rot = int(fd.get("rotation", 0)) // 90
            quv = quv[-rot:] + quv[:-rot] if rot else quv
            base = len(verts)
            verts += [Vector(c) for c in C]
            faces.append((base, base + 3, base + 2, base + 1))  # outward winding in Blender's Z-up after axis swap
            uvs.append([(quv[k][0] / tw, 1 - quv[k][1] / th) for k in (0, 3, 2, 1)])
            fmat.append(ti)
        if not faces: continue
        # element rotation around its origin (Blockbench degrees, XYZ)
        org = Vector(el.get("origin", [0, 0, 0])); r = el.get("rotation", [0, 0, 0])
        R = (Matrix.Rotation(math.radians(r[2]), 4, "Z") @ Matrix.Rotation(math.radians(r[1]), 4, "Y") @ Matrix.Rotation(math.radians(r[0]), 4, "X"))
        conv = lambda v: (R @ (v - org).to_4d()).to_3d() + org
        bl = [Vector((-p.x * U, p.z * U, p.y * U)) for p in map(conv, verts)]  # BB (x,y,z) Y-up, +Z south → Blender (x,-z?,y)
        o = mc.mesh_obj(el.get("name", "cube"), bl, faces)
        uvl = o.data.uv_layers.new(name="UVMap")
        for poly, puv, mi in zip(o.data.polygons, uvs, fmat):
            for li, uv in zip(poly.loop_indices, puv): uvl.data[li].uv = uv
            poly.material_index = mi
        for m in mats: o.data.materials.append(m)
        objs.append(o)
    if not objs: raise ValueError("bbmodel contains no visible cube elements")
    for o in objs: mc.select_only([o]); bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode="OBJECT")
    return objs


# ------------------------------------------------------------------ shared stages
@stage("cleanup")
def st_cleanup(o): return mc.cleanup(o)


@stage("optimize")
def st_decimate(o, budget): return mc.decimate(o, budget)


@stage("uv_unwrap")
def st_uv(o): return mc.uv_unwrap(o)


@stage("texture_bake")
def st_bake(o, slug, res): return mc.bake_textures(o, os.path.join(OUT, "textures"), slug, res)


@stage("rig_animate")
def st_rig(root, body, clips): arm, acts = gen.rig_character(root, body, clips); return {"armature": arm.name, "bones": len(arm.data.bones), "clips": [a.name for a in acts]}


@stage("preview_render")
def st_preview(root, slug, frames): return mc.previews([o for o in mc.mesh_objects(root)], os.path.join(OUT, "previews"), slug, frames)


@stage("export")
def st_export(root, slug, formats): return {"files": mc.export_all(root, OUT, slug, formats)}


def finish(root, slug, budget, bake_res, formats, frames, rig=None, already_textured=False):
    meshes = mc.mesh_objects(root)
    body = meshes[0] if len(meshes) == 1 else mc.join(meshes, f"{slug}_mesh")
    body.parent = root if body is not root else None
    st_cleanup(body)
    st_decimate(body, budget)
    if bake_res and not already_textured:
        st_uv(body)
        st_bake(body, slug, bake_res)
    if rig: st_rig(root, body, rig)
    mc.shade(body)
    prev = st_preview(root, slug, frames)
    if rig:  # pose the thumbnail mid-walk so the rig is visibly working
        pass
    files = st_export(root, slug, formats)["files"]
    RESULT.update({"files": files, "previews": prev, "stats": mc.stats(root)})
    tex_dir = os.path.join(OUT, "textures")
    RESULT["texture_files"] = sorted(os.path.join(tex_dir, f) for f in os.listdir(tex_dir)) if os.path.isdir(tex_dir) else []


def wrap_root(objs, slug):
    """Put imported objects under a single root empty, centred on the ground plane."""
    root = mc.empty(slug)
    meshes = [o for o in objs if o.type == "MESH"]
    for o in objs:
        if o.parent is None: o.parent = root
    lo, hi = mc.bounds(meshes)
    if JOB.get("recenter", True):
        off = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        for o in objs:
            if o.parent is root: o.location -= off
    if JOB.get("target_size"):
        s = float(JOB["target_size"]) / max((hi - lo)) if max(hi - lo) > 0 else 1
        root.scale = (s, s, s); mc.select_only([root]); bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        for o in root.children: o.select_set(True)
    for o in meshes:  # bake parent transforms into the mesh so joins are clean
        mc.select_only([o]); bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM"); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True); o.parent = root
    return root


# ------------------------------------------------------------------ ops
def op_generate():
    kind, slug = JOB["kind"], JOB["slug"]; params = dict(JOB.get("params", {}), slug=slug)
    mc.reset()

    @stage("model")
    def build():
        if kind == "character":
            root, body = gen.character(params); body.parent = root; return {"root": root.name, "rig": True}
        r = gen.BUILDERS[kind](params); return {"root": r.name}
    build()
    root = bpy.data.objects[slug]
    rig = JOB.get("clips", list(gen.ANIMS)) if kind == "character" else None
    finish(root, slug, JOB.get("max_tris", 20000), JOB.get("bake", 1024), JOB.get("formats", ["glb", "gltf", "fbx", "obj", "stl", "blend"]), JOB.get("turntable", 8), rig)


def op_process():
    """Import a mesh made elsewhere (TripoSR, Hunyuan3D, Meshroom, Blockbench, a download)
    and run it through the same clean → optimize → UV → bake → preview → export stages."""
    slug = JOB["slug"]; mc.reset()

    @stage("import")
    def imp():
        objs = import_any(JOB["input"])
        return {"objects": len(objs), "meshes": sum(o.type == "MESH" for o in objs), "triangles": mc.tri_count(objs)}
    imp()
    objs = [o for o in bpy.data.objects]
    if JOB.get("crop"):
        @stage("crop_to_subject")
        def crop():
            """Scans include the floor/surroundings: keep faces within `crop` × the half-extent of the
            scene around its centre (the capture rig keeps the subject centred), drop the rest."""
            import bmesh
            meshes = [o for o in objs if o.type == "MESH"]
            lo, hi = mc.bounds(meshes); c = (lo + hi) / 2; r = float(JOB["crop"]) * max(hi.x - lo.x, hi.y - lo.y) / 2
            removed = kept = 0
            for o in meshes:
                bm = bmesh.new(); bm.from_mesh(o.data); mw = o.matrix_world
                dead = [f for f in bm.faces if ((mw @ f.calc_center_median()) - c).xy.length > r]
                removed += len(dead); bmesh.ops.delete(bm, geom=dead, context="FACES"); kept += len(bm.faces)
                bm.to_mesh(o.data); bm.free()
            # drop the ground: faces at floor height that survived the radial crop
            if JOB.get("crop_floor", True):
                lo2, hi2 = mc.bounds(meshes); h = hi2.z - lo2.z; floor = lo2.z + 0.04 * h
                for o in meshes:
                    bm = bmesh.new(); bm.from_mesh(o.data); mw = o.matrix_world
                    dead = [f for f in bm.faces if all((mw @ v.co).z <= floor for v in f.verts)]
                    removed += len(dead); bmesh.ops.delete(bm, geom=dead, context="FACES"); bm.to_mesh(o.data); bm.free()
            # photogrammetry noise: drop disconnected fragments smaller than 3% of the largest piece
            fragments = 0
            for o in meshes:
                bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
                seen, islands = set(), []
                for f in bm.faces:
                    if f.index in seen: continue
                    stack, isl = [f], []
                    seen.add(f.index)
                    while stack:
                        g = stack.pop(); isl.append(g)
                        for e in g.edges:
                            for h in e.link_faces:
                                if h.index not in seen: seen.add(h.index); stack.append(h)
                    islands.append(isl)
                if islands:
                    big = max(len(i) for i in islands)
                    dead = [f for i in islands if len(i) < 0.03 * big for f in i]
                    fragments += sum(1 for i in islands if len(i) < 0.03 * big)
                    bmesh.ops.delete(bm, geom=dead, context="FACES"); removed += len(dead)
                bm.to_mesh(o.data); bm.free()
            # floating artefacts joined to the subject by slivers: a vertical gap in face heights wider
            # than 15% of the total height means everything above it is not resting on the subject
            floating = 0
            for o in meshes:
                bm = bmesh.new(); bm.from_mesh(o.data); mw = o.matrix_world
                zs = sorted(((mw @ f.calc_center_median()).z, f) for f in bm.faces)
                if len(zs) > 10:
                    H = zs[-1][0] - zs[0][0]
                    cut = next((zs[i][0] for i in range(len(zs) - 1) if zs[i + 1][0] - zs[i][0] > 0.15 * H), None)
                    if cut is not None:
                        dead = [f for z, f in zs if z > cut]; floating += len(dead)
                        bmesh.ops.delete(bm, geom=dead, context="FACES")
                bm.to_mesh(o.data); bm.free()
            removed += floating
            return {"radius": round(r, 3), "faces_removed": removed, "fragments_removed": fragments, "floating_faces_removed": floating}
        crop()
    root = wrap_root(objs, slug)
    textured = JOB.get("keep_materials", False)
    finish(root, slug, JOB.get("max_tris", 20000), 0 if textured else JOB.get("bake", 1024), JOB.get("formats", ["glb", "gltf", "fbx", "obj", "stl", "blend"]), JOB.get("turntable", 8),
           already_textured=textured)


def op_mixamo():
    """Combine a rigged character with Mixamo animation FBX downloads ("Without Skin").
    Clips are matched by bone name (mixamorig:*), so any Mixamo-skeleton character works,
    including MeshCraft's own rigged characters."""
    slug = JOB["slug"]; mc.reset()

    @stage("import_character")
    def ch():
        objs = import_any(JOB["character"])
        arms = [o for o in objs if o.type == "ARMATURE"]
        if not arms: raise ValueError("character file has no armature")
        return {"objects": len(objs), "bones": len(arms[0].data.bones)}
    ch()
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    names = {b.name for b in arm.data.bones}
    clips = []

    @stage("import_animations")
    def anims():
        for path in JOB.get("animations", []):
            before = set(bpy.data.objects); acts_before = set(bpy.data.actions)
            bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
            new_objs = [o for o in bpy.data.objects if o not in before]
            src = next((o for o in new_objs if o.type == "ARMATURE"), None)
            new_acts = [a for a in bpy.data.actions if a not in acts_before]
            if not src or not new_acts: raise ValueError(f"{os.path.basename(path)}: no armature animation found")
            src_names = {b.name for b in src.data.bones}
            shared = names & src_names
            if len(shared) < 10: raise ValueError(f"{os.path.basename(path)}: only {len(shared)} bones match the character's skeleton")
            act = src.animation_data.action
            act.name = os.path.splitext(os.path.basename(path))[0].replace(" ", "_")
            act.use_fake_user = True; act["mc_loop"] = True
            arm.animation_data_create()
            tr = arm.animation_data.nla_tracks.new(); tr.name = act.name
            st = tr.strips.new(act.name, int(act.frame_range[0]), act); tr.mute = True
            for o in new_objs: bpy.data.objects.remove(o, do_unlink=True)
            clips.append({"clip": act.name, "matched_bones": len(shared), "frames": [int(x) for x in act.frame_range]})
        return {"clips": clips}
    anims()
    for a in list(bpy.data.actions):
        if a.users == 0 and not a.use_fake_user: bpy.data.actions.remove(a)
    root = mc.empty(slug)
    for o in bpy.data.objects:
        if o.parent is None and o is not root: o.parent = root
    files = st_export(root, slug, JOB.get("formats", ["glb", "fbx", "blend"]))["files"]
    prev = st_preview(root, slug, JOB.get("turntable", 4))
    RESULT.update({"files": files, "previews": prev, "stats": mc.stats(root), "clips": clips})


def op_scene():
    """Compose a scene from library GLBs: placements with optional socket attachment,
    ocean plane, lighting, camera; render a hero shot; export scene GLB + .blend."""
    slug = JOB["slug"]; mc.reset()
    placed = []

    @stage("assemble")
    def assemble():
        for item in JOB["items"]:
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=item["file"])
            new = [o for o in bpy.data.objects if o not in before]
            top = [o for o in new if o.parent is None]
            holder = mc.empty(item.get("name", "item"))
            for o in top: o.parent = holder
            if item.get("attach_to"):
                host, sock = item["attach_to"].split(":")
                hobj = bpy.data.objects[host]
                s = next(o for o in hobj.children_recursive if o.name.split(".")[0] == sock)
                bpy.context.view_layer.update()
                holder.matrix_world = s.matrix_world.copy()
                holder.parent = hobj; holder.matrix_parent_inverse = hobj.matrix_world.inverted()
            else:
                holder.location = item.get("location", (0, 0, 0)); holder.rotation_euler = [math.radians(a) for a in item.get("rotation", (0, 0, 0))]
                holder.scale = [item.get("scale", 1)] * 3
            holder.name = item.get("name", holder.name)
            placed.append({"name": holder.name, "file": item["file"], "objects": len(new)})
        return {"items": len(placed)}
    assemble()

    @stage("environment")
    def env():
        size = JOB.get("ocean_size", 160)
        w = mc.prim("grid", "ocean", None, loc=(0, 0, 0), x_subdivisions=48, y_subdivisions=48, size=size)
        for v in w.data.vertices: v.co.z = 0.08 * math.sin(v.co.x * 0.4) * math.cos(v.co.y * 0.33)
        m = bpy.data.materials.new("M_ocean")
        if getattr(m, "node_tree", None) is None: m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (*mc.hex_rgb("sea"), 1); b.inputs["Roughness"].default_value = 0.08
        b.inputs["Coat Weight"].default_value = 0.4
        mc.assign(w, m); w.parent = bpy.data.objects.get(slug) or mc.empty(slug)
        return {"ocean": size}
    env()
    root = bpy.data.objects[slug]
    for o in list(bpy.data.objects):
        if o.parent is None and o is not root: o.parent = root

    @stage("render")
    def hero():
        s = bpy.context.scene
        wd = bpy.data.worlds.new("sky"); s.world = wd
        if getattr(wd, "node_tree", None) is None: wd.use_nodes = True
        wd.node_tree.nodes["Background"].inputs[0].default_value = (*mc.hex_rgb(JOB.get("sky", "sky")), 1)
        wd.node_tree.nodes["Background"].inputs[1].default_value = 1.0
        elev, tilt, az = JOB.get("sun", [48, 8, 140])   # elevation above the horizon, tilt, azimuth (degrees)
        sun = bpy.data.lights.new("sun", "SUN"); sun.energy = 1.2 + 2.6 * math.sin(math.radians(elev)); so = mc.link(bpy.data.objects.new("sun", sun))
        so.rotation_euler = (math.radians(90 - elev), math.radians(tilt), math.radians(az))
        cd = bpy.data.cameras.new("cam"); cd.lens = JOB.get("lens", 32); cam = mc.link(bpy.data.objects.new("cam", cd))
        cam.location = JOB.get("camera", (34, -38, 16)); s.camera = cam
        tgt = mc.empty("cam_target", JOB.get("look_at", (0, -8, 2)))
        tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
        s.render.resolution_x, s.render.resolution_y = JOB.get("resolution", (1280, 720))
        s.render.film_transparent = False; s.view_settings.view_transform = "Standard"
        s.frame_set(JOB.get("frame", 10))
        os.makedirs(os.path.join(OUT, "previews"), exist_ok=True)
        mc._cycles(s, JOB.get("samples", 32))
        s.render.image_settings.file_format = "PNG"; s.render.image_settings.color_mode = "RGB"
        s.render.filepath = os.path.join(OUT, "previews", f"{slug}_hero.png"); bpy.ops.render.render(write_still=True)
        s.render.resolution_x, s.render.resolution_y = 512, 512
        s.render.filepath = os.path.join(OUT, "previews", f"{slug}_thumb.png"); bpy.ops.render.render(write_still=True)
        for o in (so, cam, tgt): bpy.data.objects.remove(o, do_unlink=True)
        return {"hero": s.render.filepath}
    hero()
    files = st_export(root, slug, JOB.get("formats", ["glb", "blend"]))["files"]
    pv = os.path.join(OUT, "previews")
    RESULT.update({"files": files, "previews": {"thumbnail": os.path.join(pv, f"{slug}_thumb.png"), "hero": os.path.join(pv, f"{slug}_hero.png"), "turntable": []},
                   "stats": mc.stats(root), "placed": placed})


def op_validate():
    """Re-import an exported file in a clean scene and check it is real, usable geometry."""
    mc.reset()
    path = JOB["input"]
    objs = import_any(path)
    # Blender's glTF importer adds an icosphere as the display shape of armature bones: not asset geometry
    shapes = {pb.custom_shape for a in objs if a.type == "ARMATURE" for pb in a.pose.bones if pb.custom_shape}
    meshes = [o for o in objs if o.type == "MESH" and o not in shapes]
    import bmesh
    nonman = 0; zero = 0
    for o in meshes:
        bm = bmesh.new(); bm.from_mesh(o.data)
        nonman += sum(1 for e in bm.edges if not e.is_manifold)
        zero += sum(1 for f in bm.faces if f.calc_area() < 1e-10)
        bm.free()
    lo, hi = mc.bounds(meshes)
    imgs = sorted({n.image.name for o in meshes for m in o.data.materials if m for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image})
    arms = [o for o in objs if o.type == "ARMATURE"]
    r = {"file": path, "bytes": os.path.getsize(path), "objects": len(objs), "meshes": len(meshes), "triangles": mc.tri_count(meshes),
         "vertices": sum(len(o.data.vertices) for o in meshes), "dimensions_m": [round(v, 3) for v in hi - lo],
         "textures": imgs, "bones": len(arms[0].data.bones) if arms else 0,
         "animations": sorted(a.name for a in bpy.data.actions), "non_manifold_edges": nonman, "degenerate_faces": zero}
    problems = []
    if not meshes or r["triangles"] == 0: problems.append("no geometry")
    if max(hi - lo) <= 0 or max(hi - lo) > 2000: problems.append("implausible size")
    for k, want in (JOB.get("expect") or {}).items():
        have = r.get(k)
        if k == "triangles" and abs(have - want) > max(4, 0.02 * want): problems.append(f"triangles {have} != {want}")
        if k == "animations" and have and len(have) < want: problems.append(f"only {len(have)} animations, expected {want}")
        if k == "textures" and len(have) < want: problems.append(f"only {len(have)} textures, expected {want}")
    r["problems"] = problems
    RESULT.update({"validation": r})


def op_photoset():
    """Render a ring of photos around an asset (synthetic capture for photogrammetry tests)."""
    mc.reset(); objs = import_any(JOB["input"])
    meshes = [o for o in objs if o.type == "MESH"]
    lo, hi = mc.bounds(meshes); c = (lo + hi) / 2; size = (hi - lo).length
    s = bpy.context.scene
    g = mc.prim("plane", "floor", mc.mat("#8f8a80", "rock", 0.9), loc=(c.x, c.y, lo.z - 0.002), scale=(size * 2, size * 2, 1))
    w = bpy.data.worlds.new("w"); s.world = w
    if getattr(w, "node_tree", None) is None: w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.2
    sun = mc.link(bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))); sun.data.energy = 3; sun.rotation_euler = (0.6, 0.2, 0.8)
    cam = mc.link(bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))); cam.data.lens = 35; s.camera = cam
    tgt = mc.empty("t", c)
    tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    n = JOB.get("views", 36); rings = JOB.get("rings", [18, 40]); res = JOB.get("resolution", 1024)
    s.render.resolution_x = s.render.resolution_y = res; mc._cycles(s, JOB.get("samples", 16))
    s.render.image_settings.file_format = "JPEG"; s.render.film_transparent = False
    shots = []
    for ri, elev in enumerate(rings):
        for i in range(n // len(rings)):
            a = 2 * math.pi * i / (n // len(rings)) + ri * 0.3; d = size * 1.25
            cam.location = (c.x + d * math.cos(a) * math.cos(math.radians(elev)), c.y + d * math.sin(a) * math.cos(math.radians(elev)), c.z + d * math.sin(math.radians(elev)))
            s.render.filepath = os.path.join(OUT, f"view_{ri}_{i:02d}.jpg"); bpy.ops.render.render(write_still=True); shots.append(s.render.filepath)
    RESULT.update({"photos": shots})


def op_mixamo_prep():
    """Character → unrigged T-pose FBX (mesh only), the file Mixamo's auto-rigger accepts."""
    mc.reset(); objs = import_any(JOB["input"])
    for a in [o for o in objs if o.type == "ARMATURE"]:
        for pb in a.pose.bones: pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    meshes = [o for o in objs if o.type == "MESH"]
    for o in meshes:
        mc.select_only([o])
        for m in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=m.name)
        bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM"); o.vertex_groups.clear()
    for o in objs:
        if o.type != "MESH": bpy.data.objects.remove(o, do_unlink=True)
    body = mc.join(meshes, JOB["slug"]) if len(meshes) > 1 else meshes[0]
    p = os.path.join(OUT, JOB["slug"] + "_mixamo_upload.fbx"); mc.select_only([body])
    bpy.ops.export_scene.fbx(filepath=p, use_selection=True, bake_anim=False, add_leaf_bones=False, path_mode="COPY", embed_textures=True, axis_forward="-Z", axis_up="Y")
    RESULT.update({"files": {"fbx": p}, "triangles": mc.tri_count([body])})


def op_split_clips():
    """Write one armature-only FBX per animation clip ("Without Skin", 30 fps), the same layout
    as Mixamo downloads. Used to exercise the Mixamo import path offline; not Mixamo data."""
    mc.reset(); objs = import_any(JOB["input"])
    arm = next(o for o in objs if o.type == "ARMATURE")
    for o in objs:
        if o.type == "MESH": bpy.data.objects.remove(o, do_unlink=True)
    arm.animation_data_create()
    for tr in list(arm.animation_data.nla_tracks): arm.animation_data.nla_tracks.remove(tr)
    out = []
    for act in [a for a in bpy.data.actions if a.name in JOB.get("clips", [a.name for a in bpy.data.actions])]:
        arm.animation_data.action = act
        sc = bpy.context.scene; sc.frame_start, sc.frame_end = int(act.frame_range[0]), int(act.frame_range[1])
        try: arm.animation_data.action_slot = act.slots[0]
        except Exception: pass
        p = os.path.join(OUT, f"{JOB.get('prefix', '')}{act.name}.fbx")
        mc.select_only([arm])
        bpy.ops.export_scene.fbx(filepath=p, use_selection=True, object_types={"ARMATURE"}, add_leaf_bones=False, bake_anim=True,
                                 bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, axis_forward="-Z", axis_up="Y")
        out.append(p)
    RESULT.update({"files": {"clips": out}})


OPS = {"split_clips": op_split_clips, "mixamo_prep": op_mixamo_prep, "generate": op_generate, "process": op_process, "bbmodel": op_process, "mixamo": op_mixamo, "scene": op_scene,
       "validate": op_validate, "photoset": op_photoset}
try:
    OPS[JOB["op"]]()
    RESULT["ok"] = True
except Exception as e:
    RESULT["error"] = f"{type(e).__name__}: {e}"
    RESULT["traceback"] = traceback.format_exc()[-3000:]
json.dump(RESULT, open(os.path.join(OUT, "_result.json"), "w"), indent=1, default=str)
PROG.close()
sys.exit(0 if RESULT["ok"] else 1)
