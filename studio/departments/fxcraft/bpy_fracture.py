"""Blender (MeshCraft's bpy): Voronoi-fracture a mesh into convex cells, simulate the pieces with
Bullet rigid bodies (an outward impulse + gravity onto a ground plane), bake to keyframes and export
an animated GLB (one node per piece, one scene animation). Works on convex-ish solids (crates,
pillars, rocks, walls); concave inputs are fractured per convex cell of their bounding volume."""
import math, random, time
import studio_bpy as S


def run(req):
    import bpy, bmesh
    from mathutils import Vector
    t0 = time.time(); sc = S.reset(); rnd = random.Random(req["seed"])
    if req.get("input"):
        objs = [o for o in S.import_any(req["input"]) if o.type == "MESH"]
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs: o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1: bpy.ops.object.join()
        src = bpy.context.view_layer.objects.active
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    else:
        s = req["size"]
        if req["shape"] == "pillar": bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=s * 0.3, depth=s * 2, location=(0, 0, s))
        elif req["shape"] == "wall": bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, s * 0.75)); bpy.context.object.scale = (s * 2, s * 0.25, s * 1.5)
        elif req["shape"] == "rock": bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=s * 0.6, location=(0, 0, s * 0.6))
        else: bpy.ops.mesh.primitive_cube_add(size=s, location=(0, 0, s / 2))
        src = bpy.context.object; bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    mw = src.matrix_world.copy()
    lo, hi = S.bounds([src])
    seeds = [Vector((rnd.uniform(lo.x, hi.x), rnd.uniform(lo.y, hi.y), rnd.uniform(lo.z, hi.z))) for _ in range(req["pieces"])]
    base = bmesh.new(); base.from_mesh(src.data); base.transform(mw)
    col = req.get("color") or [150, 120, 95]
    mat = bpy.data.materials.new("Fragment"); mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF"); bsdf.inputs["Base Color"].default_value = (*[(c / 255) ** 2.2 for c in col], 1); bsdf.inputs["Roughness"].default_value = 0.85
    inner = bpy.data.materials.new("FragmentInner"); inner.use_nodes = True
    inner.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (*[min(1, (c / 255) ** 2.2 * 0.55) for c in col], 1)
    pieces = []
    for i, sd in enumerate(seeds):
        bm = base.copy()
        for j, other in enumerate(seeds):
            if i == j: continue
            n = (other - sd).normalized(); mid = (sd + other) / 2
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=mid, plane_no=n, clear_outer=True)
            cut = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
            if cut:
                try: bmesh.ops.holes_fill(bm, edges=cut, sides=0)
                except Exception: pass
            if not bm.verts: break
        if len(bm.verts) < 4: bm.free(); continue
        me = bpy.data.meshes.new(f"piece_{i:02d}"); bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(f"piece_{i:02d}", me); sc.collection.objects.link(ob)
        ob.data.materials.append(mat); ob.data.materials.append(inner)
        for poly in me.polygons:   # faces created by cuts (not on the original surface) use the inner material
            if len(poly.vertices) > 4: poly.material_index = 1
        bpy.context.view_layer.objects.active = ob; ob.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS"); ob.select_set(False)
        pieces.append(ob)
    bpy.data.objects.remove(src)
    # simulation
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0)); ground = bpy.context.object; ground.name = "ground"
    sc.frame_start, sc.frame_end = 1, req["frames"]; sc.render.fps = req["fps"]
    bpy.context.view_layer.objects.active = ground; bpy.ops.rigidbody.world_add(); sc.rigidbody_world.point_cache.frame_end = req["frames"]
    ground.select_set(True); bpy.ops.rigidbody.object_add(type="PASSIVE"); ground.select_set(False)
    centre = sum((o.location for o in pieces), Vector()) / max(1, len(pieces))
    for o in pieces:
        bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.rigidbody.object_add(type="ACTIVE"); o.select_set(False)
        o.rigid_body.collision_shape = "CONVEX_HULL"; o.rigid_body.mass = max(0.05, o.dimensions.x * o.dimensions.y * o.dimensions.z * 600)
        o.rigid_body.friction = 0.6; o.rigid_body.restitution = 0.2
        # outward impulse: animate the piece kinematically over the first frames, then hand it to Bullet
        d = (o.location - centre); d.z = abs(d.z) + 0.3; d = d.normalized() * req["force"] * rnd.uniform(0.7, 1.2)
        o.rigid_body.kinematic = True; o.keyframe_insert("location", frame=1); o.keyframe_insert("rotation_euler", frame=1)
        o.keyframe_insert("rigid_body.kinematic", frame=1)
        o.location = o.location + d * (2 / req["fps"]); o.rotation_euler = [r + rnd.uniform(-0.3, 0.3) for r in o.rotation_euler]
        o.keyframe_insert("location", frame=3); o.keyframe_insert("rotation_euler", frame=3)
        o.rigid_body.kinematic = False; o.keyframe_insert("rigid_body.kinematic", frame=4)
    def spread():
        ps = [o.matrix_world.translation for o in pieces]; c = sum(ps, Vector()) / len(ps)
        return sum((p - c).length for p in ps) / len(ps)
    # run the simulation frame by frame and record every piece's world transform
    track = {o.name: [] for o in pieces}
    for f in range(1, req["frames"] + 1):
        sc.frame_set(f)
        if f == 1: s0 = spread()
        for o in pieces: track[o.name].append(o.matrix_world.copy())
    s1 = spread()
    # bake: turn the simulation off and keyframe the recorded transforms (no UI context needed)
    sc.rigidbody_world.enabled = False
    for o in pieces:
        o.animation_data_clear(); o.rotation_mode = "QUATERNION"
        for f, m in enumerate(track[o.name], start=1):
            loc, rot, scl = m.decompose()
            o.location = loc; o.rotation_quaternion = rot
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_quaternion", frame=f)
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"])
    # preview: a few frames side by side
    try:
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
        r = max(2.0, s1 * 2.5 + 1.5); cam.location = (r * 1.2, -r * 1.6, r * 0.9); S.look_at(cam, (0, 0, 0.4))
        sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun); sun.rotation_euler = (0.8, 0.2, 0.6); sun.data.energy = 3
        S.world_color(sc, (0.55, 0.62, 0.7), 0.8); S.cycles(sc, (320, 240), samples=8)
        from PIL import Image
        shots = []
        for f in (1, req["frames"] // 4, req["frames"] // 2, req["frames"]):
            sc.frame_set(f); p = req["preview"].replace(".png", f"_{f}.png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True); shots.append(p)
        W = Image.new("RGB", (320 * len(shots), 240))
        for k, p in enumerate(shots): W.paste(Image.open(p).convert("RGB"), (320 * k, 0))
        W.save(req["preview"])
        import os
        for p in shots: os.remove(p)
    except Exception as e:
        print("preview failed:", e)
    bpy.data.objects.remove(ground)
    if bpy.data.objects.get("cam"): bpy.data.objects.remove(bpy.data.objects["cam"])
    if bpy.data.objects.get("sun"): bpy.data.objects.remove(bpy.data.objects["sun"])
    bpy.ops.export_scene.gltf(filepath=req["glb"], export_format="GLB", export_yup=True, export_animations=True, export_animation_mode="SCENE", export_force_sampling=True)
    return {"pieces": len(pieces), "spread_start": round(s0, 4), "spread_end": round(s1, 4), "seconds": round(time.time() - t0, 2)}


S.main(run)
