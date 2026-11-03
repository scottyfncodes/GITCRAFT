"""CinematicCraft's Blender work (MeshCraft's bpy): stage a scene, light it, move a camera and
render frames with Cycles. Modes: shot (frames + camera path), stills (one frame per storyboard shot)."""
import json, math, os, time
import studio_bpy as S


def stage(req):
    import bpy
    from mathutils import Vector
    sc = S.reset()
    for item in req["scene"]:
        objs = S.import_any(item["path"])
        top = [o for o in objs if o.parent is None]
        for o in top:
            o.location = Vector(item.get("location", (0, 0, 0))) + o.location
            if item.get("scale"): o.scale = [s * item["scale"] for s in o.scale]
            if item.get("rotation_z"): o.rotation_mode = "XYZ"; o.rotation_euler.z += math.radians(item["rotation_z"])
    # play every imported clip (first NLA strip of each animated object) so animated assets move in the shot
    for o in bpy.data.objects:
        ad = o.animation_data
        if ad and not ad.action and ad.nla_tracks:
            st = next((s for t in ad.nla_tracks for s in t.strips if s.action), None)
            if st:
                for t in ad.nla_tracks: t.mute = True
                ad.action = st.action
    bpy.context.view_layer.update()   # transforms set above reach matrix_world only after an update
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi = S.bounds(meshes); c = (lo + hi) / 2; r = max((hi - lo).length / 2, 0.5)
    if req.get("ground", True):
        bpy.ops.mesh.primitive_plane_add(size=r * 40, location=(c.x, c.y, lo.z - 0.001)); g = bpy.context.object
        m = bpy.data.materials.new("ground"); m.use_nodes = True; m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*req.get("ground_color", (0.32, 0.33, 0.3)), 1)
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9; g.data.materials.append(m)
    light(sc, req["lighting"], c, r, req.get("sky"))
    return sc, c, r, lo, hi


def light(sc, preset, c, r, sky=None):
    import bpy
    from mathutils import Vector
    def sun(rot, energy, col):
        L = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(L)
        L.rotation_euler = rot; L.data.energy = energy; L.data.color = col; L.data.angle = math.radians(3); return L
    def area(pos, energy, col, size):
        L = bpy.data.objects.new("area", bpy.data.lights.new("area", "AREA")); sc.collection.objects.link(L)
        L.location = c + Vector(pos) * r; S.look_at(L, c); L.data.energy = energy * r * r; L.data.color = col; L.data.size = size * r; return L
    if preset == "studio":
        area((-2, -2.5, 2.2), 260, (1, 0.97, 0.92), 1.2); area((2.5, -1.5, 1), 90, (0.85, 0.9, 1), 1.6); area((0.5, 3, 2.5), 160, (1, 1, 1), 0.8)
        S.world_color(sc, (0.18, 0.19, 0.21), 0.6)
    elif preset == "golden_hour":
        sun((math.radians(78), 0, math.radians(-50)), 3.2, (1.0, 0.72, 0.45)); S.world_color(sc, (0.55, 0.5, 0.48), 0.7)
    elif preset == "night":
        sun((math.radians(50), 0, math.radians(30)), 0.35, (0.55, 0.65, 1.0)); area((1.2, -1.2, 1.4), 120, (1.0, 0.65, 0.35), 0.3)
        S.world_color(sc, (0.02, 0.03, 0.06), 1.0)
    elif preset == "overcast":
        sun((math.radians(30), 0, math.radians(20)), 0.6, (0.95, 0.97, 1.0)); S.world_color(sc, (0.75, 0.78, 0.82), 1.1)
    elif preset == "dramatic":
        L = bpy.data.objects.new("spot", bpy.data.lights.new("spot", "SPOT")); sc.collection.objects.link(L)
        L.location = c + Vector((-1.2, -0.8, 3)) * r; S.look_at(L, c); L.data.energy = 900 * r * r; L.data.spot_size = math.radians(40); L.data.color = (1, 0.9, 0.8)
        area((2, 2, 0.6), 60, (0.4, 0.55, 1.0), 1); S.world_color(sc, (0.01, 0.01, 0.015), 1.0)
    else:   # daylight
        sun((math.radians(45), 0, math.radians(35)), 3.0, (1, 0.96, 0.9)); S.world_color(sc, (0.6, 0.72, 0.9), 0.9)
    if sky:
        w = sc.world; nt = w.node_tree; tex = nt.nodes.new("ShaderNodeTexEnvironment"); tex.image = bpy.data.images.load(sky)
        bg = next(n for n in nt.nodes if n.type == "BACKGROUND"); nt.links.new(tex.outputs[0], bg.inputs[0])


def camera_path(move, c, r, n, p):
    """[(position, target, lens)] per frame for a camera move around centre c and radius r."""
    from mathutils import Vector
    out = []; dist = r * p.get("distance", 3.0); h = r * p.get("height", 0.8); arc = math.radians(p.get("arc", 360 if move == "orbit" else 60))
    a0 = math.radians(p.get("start_angle", -30)); lens = p.get("lens", 35)
    ease = lambda t: t * t * (3 - 2 * t)
    for k in range(n):
        t = k / max(1, n - 1); e = ease(t)
        tgt = c.copy(); tgt.z += r * 0.1
        if move == "orbit":
            a = a0 + arc * t; pos = c + Vector((math.sin(a) * dist, -math.cos(a) * dist, h))
        elif move == "dolly_in":
            d = dist * (1.6 - 0.9 * e); pos = c + Vector((math.sin(a0) * d, -math.cos(a0) * d, h * (1.1 - 0.3 * e)))
        elif move == "dolly_out":
            d = dist * (0.7 + 0.9 * e); pos = c + Vector((math.sin(a0) * d, -math.cos(a0) * d, h * (0.8 + 0.4 * e)))
        elif move == "crane_up":
            pos = c + Vector((math.sin(a0) * dist, -math.cos(a0) * dist, r * 0.2 + (h + r * 2.2) * e)); tgt.z += r * 0.3 * e
        elif move == "flyby":
            x = (-1.6 + 3.2 * e) * dist; pos = c + Vector((x, -dist * 0.8, h)); tgt = c + Vector((x * 0.25, 0, r * 0.1))
        elif move == "push_in":
            pos = c + Vector((math.sin(a0) * dist, -math.cos(a0) * dist, h)); lens = p.get("lens", 35) * (1 + 1.2 * e)
        elif move == "handheld":
            j = lambda f, s: (math.sin(f * 2.1 + s) + 0.5 * math.sin(f * 5.3 + 2 * s)) * 0.012 * r
            f = k / 24 * 6; pos = c + Vector((math.sin(a0) * dist + j(f, 0), -math.cos(a0) * dist + j(f, 1), h + j(f, 2))); tgt = tgt + Vector((j(f, 3), j(f, 4), j(f, 5)))
        else:   # static
            pos = c + Vector((math.sin(a0) * dist, -math.cos(a0) * dist, h))
        out.append((pos, tgt, lens))
    return out


def run(req):
    import bpy
    t0 = time.time()
    sc, c, r, lo, hi = stage(req)
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.clip_end = r * 200; cam.data.sensor_width = 36
    S.cycles(sc, tuple(req["resolution"]), samples=req["samples"])
    sc.render.fps = req["fps"]
    if req["mode"] == "stills":
        outs = []
        for i, shot in enumerate(req["shots"]):
            path = camera_path(shot.get("move", "static"), c, r, 3, shot)
            pos, tgt, lens = path[1]
            cam.location = pos; S.look_at(cam, tgt); cam.data.lens = lens
            sc.frame_set(int(shot.get("frame", 1))); sc.render.filepath = os.path.join(req["out_dir"], f"_still_{i:02d}.png"); bpy.ops.render.render(write_still=True)
            outs.append(sc.render.filepath)
        return {"stills": outs, "seconds": round(time.time() - t0, 2)}
    n = int(req["duration"] * req["fps"]); path = camera_path(req["move"], c, r, n, req)
    sc.frame_start, sc.frame_end = 1, n
    keys = []
    for k, (pos, tgt, lens) in enumerate(path):
        cam.location = pos; S.look_at(cam, tgt); cam.data.lens = lens
        cam.keyframe_insert("location", frame=k + 1); cam.keyframe_insert("rotation_euler", frame=k + 1); cam.data.keyframe_insert("lens", frame=k + 1)
        # Y-up for engines: (x, z, -y)
        fov = math.degrees(2 * math.atan(cam.data.sensor_width / (2 * lens)) * (req["resolution"][1] / req["resolution"][0]))
        keys.append({"t": round(k / req["fps"], 4), "position": [round(pos.x, 4), round(pos.z, 4), round(-pos.y, 4)], "target": [round(tgt.x, 4), round(tgt.z, 4), round(-tgt.y, 4)],
                     "fov_deg": round(fov, 3)})
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"])
    frames = []
    step = max(1, req.get("render_every", 1))
    for k in range(1, n + 1, step):
        sc.frame_set(k); p = os.path.join(req["out_dir"], "_frames", f"f{len(frames):04d}.png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True); frames.append(p)
    return {"frames": frames, "camera_keys": keys, "centre": [c.x, c.z, -c.y], "radius": r, "seconds": round(time.time() - t0, 2)}


S.main(run)
