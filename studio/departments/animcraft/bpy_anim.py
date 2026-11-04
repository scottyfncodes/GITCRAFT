"""AnimCraft's Blender work (MeshCraft's bpy). One script, several modes (req["mode"]):

  demo       build a T-pose test character (or quadruped / tentacle) as one manifold mesh
  autorig    landmarks from the mesh → armature (humanoid, quadruped, chain) → heat-map weights
             (envelope fallback, reported) → .blend + GLB
  animate    procedural clips on an autorig skeleton or on a plain object → one action per clip
  retarget   copy motion from a source armature (BVH/FBX/GLB) onto a target armature by bone map,
             in world space, with hip translation scaled by leg length
  physics    drop/scatter objects onto a ground with Bullet rigid bodies, baked to keyframes
  sprites    render each clip from N directions with an orthographic camera (sprite sheets)

Clips are actions stashed in muted NLA tracks and exported with export_animation_mode=ACTIONS (one
glTF animation per clip), the same pattern MeshCraft uses."""
import math, os, time
import studio_bpy as S

HUMANOID = ["hips", "spine", "chest", "neck", "head", "shoulder.L", "upper_arm.L", "forearm.L", "hand.L", "shoulder.R", "upper_arm.R", "forearm.R", "hand.R",
            "thigh.L", "shin.L", "foot.L", "toe.L", "thigh.R", "shin.R", "foot.R", "toe.R"]
MIXAMO = {"hips": "Hips", "spine": "Spine", "chest": "Spine2", "neck": "Neck", "head": "Head", "shoulder.L": "LeftShoulder", "upper_arm.L": "LeftArm",
          "forearm.L": "LeftForeArm", "hand.L": "LeftHand", "shoulder.R": "RightShoulder", "upper_arm.R": "RightArm", "forearm.R": "RightForeArm", "hand.R": "RightHand",
          "thigh.L": "LeftUpLeg", "shin.L": "LeftLeg", "foot.L": "LeftFoot", "toe.L": "LeftToeBase", "thigh.R": "RightUpLeg", "shin.R": "RightLeg", "foot.R": "RightFoot", "toe.R": "RightToeBase"}
SYN = {"pelvis": "hips", "hip": "hips", "root": "hips", "spine1": "spine", "spine2": "chest", "spine3": "chest", "chest": "chest", "upperchest": "chest",
       "neck": "neck", "neck1": "neck", "head": "head", "leftshoulder": "shoulder.L", "lshoulder": "shoulder.L", "leftclavicle": "shoulder.L", "lcollar": "shoulder.L",
       "leftarm": "upper_arm.L", "leftupperarm": "upper_arm.L", "lshldr": "upper_arm.L", "lupperarm": "upper_arm.L", "leftforearm": "forearm.L", "leftlowerarm": "forearm.L", "lforearm": "forearm.L",
       "lefthand": "hand.L", "lhand": "hand.L", "rightshoulder": "shoulder.R", "rshoulder": "shoulder.R", "rightclavicle": "shoulder.R", "rcollar": "shoulder.R",
       "rightarm": "upper_arm.R", "rightupperarm": "upper_arm.R", "rshldr": "upper_arm.R", "rupperarm": "upper_arm.R", "rightforearm": "forearm.R", "rightlowerarm": "forearm.R", "rforearm": "forearm.R",
       "righthand": "hand.R", "rhand": "hand.R", "leftupleg": "thigh.L", "leftthigh": "thigh.L", "lthigh": "thigh.L", "leftupperleg": "thigh.L", "leftleg": "shin.L", "leftshin": "shin.L", "lshin": "shin.L",
       "leftlowerleg": "shin.L", "leftfoot": "foot.L", "lfoot": "foot.L", "lefttoebase": "toe.L", "lefttoe": "toe.L", "rightupleg": "thigh.R", "rightthigh": "thigh.R", "rthigh": "thigh.R",
       "rightupperleg": "thigh.R", "rightleg": "shin.R", "rightshin": "shin.R", "rshin": "shin.R", "rightlowerleg": "shin.R", "rightfoot": "foot.R", "rfoot": "foot.R",
       "righttoebase": "toe.R", "righttoe": "toe.R"}


def canon(name):
    n = name.split(":")[-1].replace("mixamorig", "").replace("_", "").replace(" ", "").replace("-", "").lower()
    n2 = n.replace(".l", "l_").replace(".r", "r_")
    if n in SYN: return SYN[n]
    for h in HUMANOID:
        if h.replace(".", "").lower() == n: return h
    if n.endswith("l") and n[:-1] in ("upperarm", "forearm", "hand", "thigh", "shin", "foot", "toe", "shoulder"): return n[:-1].replace("upperarm", "upper_arm") + ".L"
    if n.endswith("r") and n[:-1] in ("upperarm", "forearm", "hand", "thigh", "shin", "foot", "toe", "shoulder"): return n[:-1].replace("upperarm", "upper_arm") + ".R"
    return None


# ---------------------------------------------------------------- helpers
def mesh_objects():
    import bpy
    return [o for o in bpy.data.objects if o.type == "MESH"]


def join_meshes(objs, name):
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active; o.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return o


def material(name, rgb):
    import bpy
    m = bpy.data.materials.new(name); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*[(c / 255) ** 2.2 for c in rgb], 1)
    return m


def build_demo(kind, h=1.8):
    import bpy
    parts = []
    def add(op, **kw):
        op(**kw); parts.append(bpy.context.object); return bpy.context.object
    if kind == "humanoid":
        add(bpy.ops.mesh.primitive_cube_add, size=1, location=(0, 0, 0.62 * h)); parts[-1].scale = (0.3 * h / 1.8 * 1.0, 0.18 * h / 1.8, 0.36 * h / 1.8 * 1.0)
        add(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.12 * h / 1.8, location=(0, 0, 0.9 * h))
        for sx in (1, -1):
            add(bpy.ops.mesh.primitive_cylinder_add, radius=0.045 * h / 1.8, depth=0.62 * h / 1.8, location=(sx * 0.42 * h / 1.8, 0, 0.77 * h), rotation=(0, math.pi / 2, 0))
            add(bpy.ops.mesh.primitive_cylinder_add, radius=0.065 * h / 1.8, depth=0.86 * h / 1.8, location=(sx * 0.085 * h / 1.8, 0, 0.25 * h), rotation=(0, 0, 0))
            add(bpy.ops.mesh.primitive_cube_add, size=1, location=(sx * 0.085 * h / 1.8, -0.05 * h / 1.8, 0.025 * h)); parts[-1].scale = (0.1 * h / 1.8, 0.22 * h / 1.8, 0.05 * h / 1.8)
        col = (90, 150, 210)
    elif kind == "quadruped":
        add(bpy.ops.mesh.primitive_cube_add, size=1, location=(0, 0, 0.55)); parts[-1].scale = (0.35, 1.0, 0.32)
        add(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.2, location=(0, -0.68, 0.82))
        add(bpy.ops.mesh.primitive_cylinder_add, radius=0.04, depth=0.5, location=(0, 0.72, 0.62), rotation=(math.radians(70), 0, 0))
        for sx in (1, -1):
            for sy in (1, -1):
                add(bpy.ops.mesh.primitive_cylinder_add, radius=0.07, depth=0.42, location=(sx * 0.14, sy * 0.38, 0.21))
        col = (190, 140, 90)
    else:   # chain: a tentacle / tail / snake standing up along Z
        add(bpy.ops.mesh.primitive_cone_add, vertices=16, radius1=0.12, radius2=0.03, depth=1.6, location=(0, 0, 0.8))
        bpy.ops.object.modifier_add(type="SUBSURF"); col = (170, 90, 180)
    o = join_meshes(parts, f"demo_{kind}")
    # one manifold skin: voxel remesh (heat-map weighting needs a closed mesh)
    m = o.modifiers.new("remesh", "REMESH"); m.mode = "VOXEL"; m.voxel_size = (0.025 * h / 1.8) if kind == "humanoid" else (0.03 if kind == "quadruped" else 0.025)
    bpy.ops.object.modifier_apply(modifier=m.name)
    for md in list(o.modifiers): bpy.ops.object.modifier_apply(modifier=md.name)
    sm = o.modifiers.new("smooth", "SMOOTH"); sm.iterations = 4; bpy.ops.object.modifier_apply(modifier=sm.name)
    o.data.materials.append(material(f"{kind}_skin", col))
    bpy.ops.object.shade_smooth()
    return o


def landmarks_humanoid(o):
    from mathutils import Vector
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    zmin = min(v.z for v in vs); zmax = max(v.z for v in vs); H = zmax - zmin
    band = lambda a, b: [v for v in vs if zmin + a * H <= v.z <= zmin + b * H]
    torso = band(0.55, 0.68); w = max(abs(v.x) for v in torso) if torso else 0.12 * H
    arms = band(0.72, 0.86); tip = max(abs(v.x) for v in arms) if arms else 0.45 * H
    yc = sum(v.y for v in vs) / len(vs)
    z = lambda f: zmin + f * H
    sh = z(0.82); L = {}
    L["hips"] = (Vector((0, yc, z(0.5))), Vector((0, yc, z(0.6))))
    L["spine"] = (L["hips"][1], Vector((0, yc, z(0.7))))
    L["chest"] = (L["spine"][1], Vector((0, yc, z(0.8))))
    L["neck"] = (L["chest"][1], Vector((0, yc, z(0.86))))
    L["head"] = (L["neck"][1], Vector((0, yc, zmax)))
    for s, sx in (("L", 1), ("R", -1)):
        sx_w = sx * w; wrist = sx * (tip - 0.07 * H)
        L[f"shoulder.{s}"] = (Vector((sx * 0.02 * H, yc, z(0.8))), Vector((sx_w * 0.95, yc, sh)))
        L[f"upper_arm.{s}"] = (L[f"shoulder.{s}"][1], Vector(((sx_w * 0.95 + wrist) / 2, yc, sh)))
        L[f"forearm.{s}"] = (L[f"upper_arm.{s}"][1], Vector((wrist, yc, sh)))
        L[f"hand.{s}"] = (L[f"forearm.{s}"][1], Vector((sx * tip, yc, sh)))
        lx = sx * w * 0.5
        L[f"thigh.{s}"] = (Vector((lx, yc, z(0.5))), Vector((lx, yc, z(0.27))))
        L[f"shin.{s}"] = (L[f"thigh.{s}"][1], Vector((lx, yc, z(0.05))))
        L[f"foot.{s}"] = (L[f"shin.{s}"][1], Vector((lx, yc - 0.08 * H, z(0.015))))
        L[f"toe.{s}"] = (L[f"foot.{s}"][1], Vector((lx, yc - 0.13 * H, z(0.015))))
    parents = {"spine": "hips", "chest": "spine", "neck": "chest", "head": "neck"}
    for s in "LR":
        parents.update({f"shoulder.{s}": "chest", f"upper_arm.{s}": f"shoulder.{s}", f"forearm.{s}": f"upper_arm.{s}", f"hand.{s}": f"forearm.{s}",
                        f"thigh.{s}": "hips", f"shin.{s}": f"thigh.{s}", f"foot.{s}": f"shin.{s}", f"toe.{s}": f"foot.{s}"})
    return [(b, L[b][0], L[b][1], parents.get(b)) for b in HUMANOID], H


def landmarks_quadruped(o):
    from mathutils import Vector
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))); hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    H = hi.z - lo.z; Lg = hi.y - lo.y; back = lo.z + 0.78 * H; front = lo.y + 0.18 * Lg; rear = hi.y - 0.2 * Lg; wx = (hi.x - lo.x) * 0.3
    B = [("hips", Vector((0, rear, back)), Vector((0, rear - 0.2 * Lg, back)), None), ("spine", Vector((0, rear - 0.2 * Lg, back)), Vector((0, front + 0.1 * Lg, back)), "hips"),
         ("neck", Vector((0, front + 0.1 * Lg, back)), Vector((0, front - 0.02 * Lg, lo.z + 0.92 * H)), "spine"), ("head", Vector((0, front - 0.02 * Lg, lo.z + 0.92 * H)), Vector((0, lo.y, lo.z + 0.95 * H)), "neck"),
         ("tail", Vector((0, rear, back)), Vector((0, hi.y, back - 0.1 * H)), "hips")]
    for nm, y, par in (("front", front + 0.1 * Lg, "spine"), ("back", rear, "hips")):
        for s, sx in (("L", 1), ("R", -1)):
            B += [(f"{nm}_upper.{s}", Vector((sx * wx, y, back - 0.1 * H)), Vector((sx * wx, y, lo.z + 0.3 * H)), par),
                  (f"{nm}_lower.{s}", Vector((sx * wx, y, lo.z + 0.3 * H)), Vector((sx * wx, y - 0.02, lo.z + 0.02 * H)), f"{nm}_upper.{s}")]
    return B, H


def landmarks_chain(o, n=6):
    from mathutils import Vector
    vs = [o.matrix_world @ v.co for v in o.data.vertices]
    lo = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs))); hi = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
    ext = hi - lo; ax = max(range(3), key=lambda i: ext[i]); c = (lo + hi) / 2
    pts = []
    for k in range(n + 1):
        p = c.copy(); p[ax] = lo[ax] + ext[ax] * k / n; pts.append(p)
    return [(f"seg_{k:02d}", pts[k], pts[k + 1], f"seg_{k - 1:02d}" if k else None) for k in range(n)], ext[ax]


def make_armature(bones, name="rig"):
    import bpy
    data = bpy.data.armatures.new(name); arm = bpy.data.objects.new(name, data); bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="EDIT")
    eb = {}
    for b, head, tail, par in bones:
        e = data.edit_bones.new(b); e.head = head; e.tail = tail; e.roll = 0
        if par: e.parent = eb[par]; e.use_connect = (e.parent.tail - e.head).length < 1e-4
        eb[b] = e
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def bind(mesh, arm):
    """Heat-map automatic weights; envelope weights if heat fails. Returns (method, unweighted vertex count)."""
    import bpy
    bpy.ops.object.select_all(action="DESELECT"); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
    method = "heat"
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except Exception:
        method = "envelope"
    def unweighted():
        return sum(1 for v in mesh.data.vertices if not any(g.weight > 1e-4 for g in v.groups))
    n = unweighted()
    if n > 0.02 * len(mesh.data.vertices):
        for g in list(mesh.vertex_groups): mesh.vertex_groups.remove(g)
        mesh.parent = None; mesh.modifiers.clear()
        bpy.ops.object.select_all(action="DESELECT"); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type="ARMATURE_ENVELOPE"); method = "envelope (heat weighting left vertices unweighted)"; n = unweighted()
    return method, n


def rename_mixamo(arm):
    for b in arm.data.bones:
        if b.name in MIXAMO: b.name = "mixamorig:" + MIXAMO[b.name]


def find_bone(arm, canonical):
    for pb in arm.pose.bones:
        if pb.name == canonical or canon(pb.name) == canonical: return pb
    return None


# ---------------------------------------------------------------- procedural clips
def world_rot(pb, q_world):
    """A rotation given in armature space, expressed in the bone's local rest frame."""
    R = pb.bone.matrix_local.to_quaternion()
    pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = R.inverted() @ q_world @ R


def Q(axis, ang):
    from mathutils import Quaternion, Vector
    return Quaternion(Vector(axis), ang)


def humanoid_pose(arm, clip, ph, H):
    """ph: 0..1 cycle phase. Arms come down from the T-pose to the sides first (A-pose)."""
    s = math.sin(2 * math.pi * ph); c = math.cos(2 * math.pi * ph)
    amp = {"walk": 1.0, "run": 1.6}.get(clip, 0.0)
    pose = {}
    down = 1.25
    pose["upper_arm.L"] = Q((0, 1, 0), down); pose["upper_arm.R"] = Q((0, 1, 0), -down)
    if clip in ("walk", "run"):
        pose["thigh.L"] = Q((1, 0, 0), 0.42 * amp * s); pose["thigh.R"] = Q((1, 0, 0), -0.42 * amp * s)
        pose["shin.L"] = Q((1, 0, 0), -0.55 * amp * max(0, -c)); pose["shin.R"] = Q((1, 0, 0), -0.55 * amp * max(0, c))
        pose["upper_arm.L"] = Q((1, 0, 0), -0.35 * amp * s) @ pose["upper_arm.L"]; pose["upper_arm.R"] = Q((1, 0, 0), 0.35 * amp * s) @ pose["upper_arm.R"]
        pose["forearm.L"] = Q((1, 0, 0), 0.3 * amp); pose["forearm.R"] = Q((1, 0, 0), 0.3 * amp)
        pose["spine"] = Q((1, 0, 0), 0.06 * amp + (0.12 if clip == "run" else 0)); pose["hips"] = Q((0, 0, 1), 0.08 * amp * s)
        loc = (0, 0, -0.012 * H * amp * abs(c))
    elif clip == "idle":
        pose["chest"] = Q((1, 0, 0), 0.03 * s); pose["head"] = Q((0, 0, 1), 0.06 * math.sin(2 * math.pi * ph * 1))
        pose["upper_arm.L"] = Q((0, 1, 0), down - 0.03 * s); pose["upper_arm.R"] = Q((0, 1, 0), -down + 0.03 * s)
        loc = (0, 0, -0.004 * H * (1 + s))
    elif clip == "wave":
        pose["upper_arm.R"] = Q((0, 1, 0), 0.5); pose["forearm.R"] = Q((0, 1, 0), 0.9 + 0.45 * s)
        pose["head"] = Q((0, 1, 0), -0.08); loc = (0, 0, 0)
    elif clip == "jump":
        crouch = max(0, math.sin(math.pi * min(1, ph / 0.3))) if ph < 0.3 else (max(0, math.sin(math.pi * (ph - 0.8) / 0.2)) if ph > 0.8 else 0)
        air = math.sin(math.pi * (ph - 0.3) / 0.5) if 0.3 <= ph <= 0.8 else 0
        pose["thigh.L"] = pose["thigh.R"] = Q((1, 0, 0), 0.9 * crouch + 0.3 * air); pose["shin.L"] = pose["shin.R"] = Q((1, 0, 0), -1.5 * crouch - 0.4 * air)
        pose["spine"] = Q((1, 0, 0), 0.35 * crouch); pose["upper_arm.L"] = Q((1, 0, 0), -1.2 * air) @ pose["upper_arm.L"]; pose["upper_arm.R"] = Q((1, 0, 0), -1.2 * air) @ pose["upper_arm.R"]
        loc = (0, 0, -0.18 * H * crouch + 0.35 * H * air)
    else:
        loc = (0, 0, 0)
    return pose, loc


def quadruped_pose(clip, ph):
    s = math.sin(2 * math.pi * ph); amp = {"walk": 0.4, "run": 0.7}.get(clip, 0.0)
    pose = {}
    if clip in ("walk", "run"):
        for nm, phase in (("front_upper.L", 0), ("back_upper.R", 0), ("front_upper.R", 0.5), ("back_upper.L", 0.5)):
            pose[nm] = Q((1, 0, 0), amp * math.sin(2 * math.pi * (ph + phase)))
            pose[nm.replace("upper", "lower")] = Q((1, 0, 0), -amp * 0.8 * max(0, math.cos(2 * math.pi * (ph + phase))))
        pose["spine"] = Q((0, 0, 1), 0.05 * s); pose["neck"] = Q((1, 0, 0), 0.08 * math.sin(4 * math.pi * ph))
    pose["tail"] = Q((0, 0, 1), 0.35 * math.sin(2 * math.pi * ph) * (1 if clip != "idle" else 0.5))
    if clip == "idle": pose["head"] = Q((0, 0, 1), 0.2 * s); pose["spine"] = Q((1, 0, 0), 0.02 * s)
    return pose, (0, 0, -0.015 * abs(math.cos(2 * math.pi * ph)) * (amp > 0))


def chain_pose(arm, clip, ph):
    pose = {}; n = len(arm.pose.bones)
    for k, pb in enumerate(arm.pose.bones):
        lag = k / max(1, n - 1)
        if clip in ("wave", "slither"): pose[pb.name] = Q((0, 0, 1) if clip == "slither" else (1, 0, 0), 0.35 * math.sin(2 * math.pi * (ph - lag * 0.8)))
        elif clip == "sway": pose[pb.name] = Q((0, 1, 0), 0.18 * math.sin(2 * math.pi * (ph - lag * 0.4)))
        elif clip == "curl": pose[pb.name] = Q((1, 0, 0), 0.5 * (0.5 - 0.5 * math.cos(2 * math.pi * ph)) * lag)
    return pose, (0, 0, 0)


def bake_clip(arm, name, frames, fn):
    import bpy
    if arm.animation_data is None: arm.animation_data_create()
    act = bpy.data.actions.new(name); arm.animation_data.action = act
    for f in range(frames + 1):
        ph = f / frames
        pose, loc = fn(ph)
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
        for b, q in pose.items():
            pb = arm.pose.bones.get(b) or find_bone(arm, b)
            if pb: world_rot(pb, q)
        root = arm.pose.bones[0]
        # root translation: armature-space offset → bone-local
        from mathutils import Vector
        root.location = root.bone.matrix_local.to_3x3().inverted() @ Vector(loc)
        for pb in arm.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=f + 1)
        root.keyframe_insert("location", frame=f + 1)
    act.use_fake_user = True
    tr = arm.animation_data.nla_tracks.new(); tr.name = name; st = tr.strips.new(name, 1, act); st.name = name; tr.mute = True
    arm.animation_data.action = None
    for pb in arm.pose.bones: pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    return act


def object_clip(o, name, frames, clip, size):
    import bpy
    if o.animation_data is None: o.animation_data_create()
    act = bpy.data.actions.new(name); o.animation_data.action = act
    if o.rotation_mode != "XYZ":   # glTF imports use quaternions; Euler keys would be ignored
        e = o.matrix_basis.to_euler("XYZ"); o.rotation_mode = "XYZ"; o.rotation_euler = e
    base_loc = o.location.copy(); base_rot = o.rotation_euler.copy(); base_scale = o.scale.copy()
    for f in range(frames + 1):
        ph = f / frames; s = math.sin(2 * math.pi * ph)
        o.location = base_loc; o.rotation_euler = base_rot; o.scale = base_scale
        if clip == "bob": o.location = (base_loc.x, base_loc.y, base_loc.z + 0.08 * size * s)
        elif clip == "spin": o.rotation_euler = (base_rot.x, base_rot.y, base_rot.z + 2 * math.pi * ph)
        elif clip == "hover": o.location = (base_loc.x, base_loc.y, base_loc.z + 0.12 * size * s); o.rotation_euler = (base_rot.x + 0.08 * math.cos(2 * math.pi * ph), base_rot.y, base_rot.z + 0.15 * s)
        elif clip == "squash":
            k = 1 + 0.18 * s; o.scale = (base_scale.x / math.sqrt(k), base_scale.y / math.sqrt(k), base_scale.z * k)
        elif clip == "shake": o.rotation_euler = (base_rot.x, base_rot.y + 0.12 * math.sin(6 * math.pi * ph) * (1 - ph), base_rot.z)
        for path in ("location", "rotation_euler", "scale"): o.keyframe_insert(path, frame=f + 1)
    act.use_fake_user = True
    tr = o.animation_data.nla_tracks.new(); tr.name = name; st = tr.strips.new(name, 1, act); st.name = name; tr.mute = True
    o.animation_data.action = None; o.location = base_loc; o.rotation_euler = base_rot; o.scale = base_scale


def export(req, objs=None):
    import bpy
    kw = dict(filepath=req["glb"], export_format="GLB", export_yup=True, export_animations=True, export_animation_mode="ACTIONS",
              export_skins=True, export_force_sampling=True)
    bpy.ops.export_scene.gltf(**kw)


def rig_type_of(arm):
    names = {canon(b.name) or b.name for b in arm.data.bones}
    if {"thigh.L", "upper_arm.L"} <= names: return "humanoid"
    if any("front_upper" in n for n in names): return "quadruped"
    return "chain"


# ---------------------------------------------------------------- modes
def mode_demo(req):
    import bpy
    S.reset(); o = build_demo(req["kind"], req.get("height", 1.8)); bpy.ops.export_scene.gltf(filepath=req["glb"], export_format="GLB", export_yup=True)
    return {"vertices": len(o.data.vertices), "dimensions": list(o.dimensions)}


def mode_autorig(req):
    import bpy
    S.reset(); objs = [o for o in S.import_any(req["input"]) if o.type == "MESH"]
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE": bpy.data.objects.remove(o)
    mesh = join_meshes(objs, "body")
    for g in list(mesh.vertex_groups): mesh.vertex_groups.remove(g)
    kind = req["rig"]
    bones, size = landmarks_humanoid(mesh) if kind == "humanoid" else landmarks_quadruped(mesh) if kind == "quadruped" else landmarks_chain(mesh, req["segments"])
    arm = make_armature(bones)
    method, unweighted = bind(mesh, arm)
    if req["naming"] == "mixamo" and kind == "humanoid": rename_mixamo(arm)
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"])
    bpy.ops.export_scene.gltf(filepath=req["glb"], export_format="GLB", export_yup=True, export_skins=True, export_animations=False)
    groups = {g.name for g in mesh.vertex_groups}
    return {"bones": [b.name for b in arm.data.bones], "weighting": method, "unweighted_vertices": unweighted, "vertices": len(mesh.data.vertices),
            "bones_with_weights": len(groups & {b.name for b in arm.data.bones}), "size": round(size, 3), "rig": kind}


def mode_animate(req):
    import bpy
    S.reset(); objs = S.import_any(req["input"])
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    for o in bpy.data.objects:
        if o.animation_data:
            for tr in list(o.animation_data.nla_tracks): o.animation_data.nla_tracks.remove(tr)
            o.animation_data.action = None
    made = []
    if arm:
        for pb in arm.pose.bones: pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
        kind = rig_type_of(arm); meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        lo, hi = S.bounds(meshes) if meshes else (None, None); H = (hi.z - lo.z) if meshes else 1.8
        for clip in req["clips"]:
            frames = req["frames"].get(clip) if isinstance(req["frames"], dict) else req["frames"]
            if kind == "humanoid": fn = lambda ph, c=clip: humanoid_pose(arm, c, ph, H)
            elif kind == "quadruped": fn = lambda ph, c=clip: quadruped_pose(c, ph)
            else: fn = lambda ph, c=clip: chain_pose(arm, c, ph)
            bake_clip(arm, clip, frames, fn); made.append(clip)
    else:
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
        top = [o for o in bpy.data.objects if o.parent is None and o.type in ("MESH", "EMPTY")] or meshes
        for o in bpy.data.actions: o.use_fake_user = False
        for a in list(bpy.data.actions): bpy.data.actions.remove(a)   # the input's own clips are replaced
        lo, hi = S.bounds(meshes); size = max(hi - lo)
        if len(top) > 1:   # one root, so each clip is one action (one glTF animation)
            root = bpy.data.objects.new("root", None); bpy.context.scene.collection.objects.link(root)
            for o in top: o.parent = root
            top = [root]
        for clip in req["clips"]:
            object_clip(top[0], clip, req["frames"] if isinstance(req["frames"], int) else 24, clip, size)
            made.append(clip)
        kind = "object"
    bpy.context.scene.render.fps = req["fps"]
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"]); export(req)
    return {"clips": made, "rig": kind}


def mode_retarget(req):
    """World-space retarget: for every mapped bone and frame, the source bone's rotation relative to
    its rest orientation is applied to the target bone relative to the target's rest orientation;
    the root's translation is scaled by the ratio of leg (hip height) lengths."""
    import bpy
    from mathutils import Matrix, Vector
    S.reset()
    src_objs = S.import_any(req["source"]); src = next(o for o in src_objs if o.type == "ARMATURE"); src.name = "SRC"
    tgt_objs = S.import_any(req["target"]); tgt = next(o for o in tgt_objs if o.type == "ARMATURE" and o != src); tgt.name = "TGT"
    # the source clip: the active action, or the first NLA strip
    ad = src.animation_data; act = ad.action if ad and ad.action else None
    if act is None and ad:
        for tr in ad.nla_tracks:
            for st in tr.strips: act = act or st.action
        for tr in list(ad.nla_tracks): tr.mute = True
        ad.action = act
    if act is None and req["source"].lower().endswith(".bvh") is False: raise RuntimeError("source has no animation")
    if req.get("clip"):
        cand = bpy.data.actions.get(req["clip"]) or next((a for a in bpy.data.actions if a.name.startswith(req["clip"])), None)
        if cand: act = cand; src.animation_data.action = cand
    src_clip = act.name.split(".")[0] if act else "retarget"
    f0, f1 = (int(act.frame_range[0]), int(act.frame_range[1])) if act else (bpy.context.scene.frame_start, bpy.context.scene.frame_end)
    if tgt.animation_data:
        for tr in list(tgt.animation_data.nla_tracks): tgt.animation_data.nla_tracks.remove(tr)
        tgt.animation_data.action = None
    mapping = {}
    for tb in tgt.pose.bones:
        cn = canon(tb.name) or tb.name
        sb = next((b for b in src.pose.bones if (canon(b.name) or b.name) == cn), None)
        if sb: mapping[tb.name] = sb.name
    for k, v in (req.get("map") or {}).items(): mapping[k] = v
    if not mapping: raise RuntimeError("no bones could be matched between source and target")
    order = [b.name for b in tgt.pose.bones if b.name in mapping]   # parents before children
    def rest_world(arm, b): return arm.matrix_world.to_quaternion() @ arm.data.bones[b].matrix_local.to_quaternion()
    hips_t = next((b for b in order if canon(b) == "hips"), order[0]); hips_s = mapping[hips_t]
    hs = (src.matrix_world @ src.data.bones[hips_s].head_local).z; ht = (tgt.matrix_world @ tgt.data.bones[hips_t].head_local).z
    scale = ht / hs if hs > 1e-6 else 1.0
    sc = bpy.context.scene
    if tgt.animation_data is None: tgt.animation_data_create()
    out = bpy.data.actions.new(req.get("name") or (act.name if act else "retarget")); tgt.animation_data.action = out
    src_hip_rest = src.matrix_world @ src.data.bones[hips_s].head_local
    for k, f in enumerate(range(f0, f1 + 1)):
        sc.frame_set(f); bpy.context.view_layer.update()
        for b in order:
            sb = src.pose.bones[mapping[b]]
            sw = (src.matrix_world @ sb.matrix).to_quaternion()      # current world rotation of the source bone
            delta = sw @ rest_world(src, mapping[b]).inverted()          # world-space change from its rest
            tw = delta @ rest_world(tgt, b)                              # same change on the target's rest
            tb = tgt.pose.bones[b]
            parent_w = (tgt.matrix_world @ tb.parent.matrix).to_quaternion() if tb.parent else tgt.matrix_world.to_quaternion()
            parent_rest = (tgt.matrix_world.to_quaternion() @ tb.parent.bone.matrix_local.to_quaternion()) if tb.parent else tgt.matrix_world.to_quaternion()
            # local = rest_local^-1 * parent_w^-1 * tw  with rest_local relative to the parent's rest
            rest_local = (parent_rest.inverted() @ rest_world(tgt, b))
            tb.rotation_mode = "QUATERNION"; tb.rotation_quaternion = rest_local.inverted() @ parent_w.inverted() @ tw
            bpy.context.view_layer.update()
            tb.keyframe_insert("rotation_quaternion", frame=k + 1)
        # hips translation, scaled
        sh = src.matrix_world @ src.pose.bones[hips_s].head
        d = (sh - src_hip_rest) * scale
        th = tgt.pose.bones[hips_t]
        th.location = (tgt.matrix_world.to_3x3() @ th.bone.matrix_local.to_3x3()).inverted() @ d
        th.keyframe_insert("location", frame=k + 1)
    out.use_fake_user = True
    tr = tgt.animation_data.nla_tracks.new(); tr.name = out.name; st = tr.strips.new(out.name, 1, out); st.name = out.name; tr.mute = True
    tgt.animation_data.action = None
    for o in list(bpy.data.objects):   # drop the source from the export
        if o == src or o.parent == src: bpy.data.objects.remove(o)
    for a in list(bpy.data.actions):
        if a != out and not any(st.action == a for o in bpy.data.objects if o.animation_data for tr in o.animation_data.nla_tracks for st in tr.strips): bpy.data.actions.remove(a)
    out.name = req.get("name") or src_clip   # the source's action is gone: take its name
    for tr in tgt.animation_data.nla_tracks:
        for st in tr.strips: st.name = out.name
        tr.name = out.name
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"]); export(req)
    return {"mapped_bones": len(mapping), "map": mapping, "frames": f1 - f0 + 1, "hip_scale": round(scale, 4), "clip": out.name}


def mode_physics(req):
    import bpy, random
    from mathutils import Vector
    S.reset(); rnd = random.Random(req["seed"]); sc = bpy.context.scene
    objs = []
    if req.get("inputs"):
        for i, p in enumerate(req["inputs"]):
            imported = [o for o in S.import_any(p) if o.type == "MESH"]; o = join_meshes(imported, f"body_{i:02d}"); objs.append(o)
    else:
        for i in range(req["count"]):
            kind = req["shape"] if req["shape"] != "mixed" else rnd.choice(["crate", "ball", "barrel"])
            if kind == "ball": bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25)
            elif kind == "barrel": bpy.ops.mesh.primitive_cylinder_add(radius=0.22, depth=0.6)
            else: bpy.ops.mesh.primitive_cube_add(size=0.45)
            o = bpy.context.object; o.name = f"{kind}_{i:02d}"; o.data.materials.append(material(kind, (rnd.randint(80, 220), rnd.randint(80, 200), rnd.randint(60, 180)))); objs.append(o)
    for i, o in enumerate(objs):
        o.location = (rnd.uniform(-1, 1) * req["spread"], rnd.uniform(-1, 1) * req["spread"], 1.0 + i * 0.6)
        o.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), rnd.uniform(0, 3))
    bpy.ops.mesh.primitive_plane_add(size=40); ground = bpy.context.object
    sc.frame_start, sc.frame_end = 1, req["frames"]; sc.render.fps = req["fps"]
    bpy.context.view_layer.objects.active = ground; bpy.ops.rigidbody.world_add(); sc.rigidbody_world.point_cache.frame_end = req["frames"]
    ground.select_set(True); bpy.ops.rigidbody.object_add(type="PASSIVE"); ground.select_set(False)
    for o in objs:
        bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.rigidbody.object_add(type="ACTIVE"); o.select_set(False)
        o.rigid_body.collision_shape = "CONVEX_HULL" if "ball" not in o.name else "SPHERE"; o.rigid_body.restitution = req["bounce"]; o.rigid_body.friction = 0.6
    track = {o.name: [] for o in objs}
    for f in range(1, req["frames"] + 1):
        sc.frame_set(f)
        for o in objs: track[o.name].append(o.matrix_world.copy())
    sc.rigidbody_world.enabled = False
    rest_h = [m.translation.z for m in (track[o.name][-1] for o in objs)]
    for o in objs:
        o.animation_data_clear(); o.rotation_mode = "QUATERNION"
        if o.animation_data is None: o.animation_data_create()
        act = bpy.data.actions.new("drop"); o.animation_data.action = act
        for f, m in enumerate(track[o.name], start=1):
            loc, rot, _ = m.decompose(); o.location = loc; o.rotation_quaternion = rot
            o.keyframe_insert("location", frame=f); o.keyframe_insert("rotation_quaternion", frame=f)
    bpy.data.objects.remove(ground)
    bpy.ops.wm.save_as_mainfile(filepath=req["blend"])
    bpy.ops.export_scene.gltf(filepath=req["glb"], export_format="GLB", export_yup=True, export_animations=True, export_animation_mode="SCENE", export_force_sampling=True)
    return {"bodies": len(objs), "start_heights": [round(t[0].translation.z, 3) for t in track.values()], "end_heights": [round(h, 3) for h in rest_h]}


def mode_sprites(req):
    import bpy
    from mathutils import Vector
    S.reset(); S.import_any(req["input"]); sc = bpy.context.scene
    arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
    holders = [o for o in bpy.data.objects if o.animation_data and o.animation_data.nla_tracks]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi = S.bounds(meshes); c = (lo + hi) / 2; size = max(hi - lo) * 1.35
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.type = "ORTHO"; cam.data.ortho_scale = size
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sc.collection.objects.link(sun); sun.rotation_euler = (0.7, 0.2, 0.8); sun.data.energy = 3.5
    S.world_color(sc, (0.7, 0.75, 0.8), 0.9); S.cycles(sc, (req["size"], req["size"]), samples=req["samples"], transparent=True)
    clips = req.get("clips") or sorted({st.action.name for o in holders for tr in o.animation_data.nla_tracks for st in tr.strips if st.action})
    out = {}
    for clip in clips:
        for o in holders:
            a = next((st.action for tr in o.animation_data.nla_tracks for st in tr.strips if st.action and st.action.name.startswith(clip)), None)
            for tr in o.animation_data.nla_tracks: tr.mute = True
            o.animation_data.action = a
        act = next((o.animation_data.action for o in holders if o.animation_data.action), None)
        if act is None: continue
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1]); n = req["frames"]
        frames = [round(f0 + (f1 - f0) * k / n) for k in range(n)]
        for d in range(req["directions"]):
            ang = 2 * math.pi * d / req["directions"]; dist = size * 3
            el = math.radians(req["elevation"])
            cam.location = c + Vector((math.sin(ang) * dist * math.cos(el), -math.cos(ang) * dist * math.cos(el), dist * math.sin(el)))
            S.look_at(cam, c)
            paths = []
            for k, f in enumerate(frames):
                sc.frame_set(f); p = os.path.join(req["out_dir"], f"_{clip}_d{d}_{k:03d}.png"); sc.render.filepath = p; bpy.ops.render.render(write_still=True); paths.append(p)
            out[f"{clip}_dir{d}"] = paths
    return {"sequences": out}


MODES = {"demo": mode_demo, "autorig": mode_autorig, "animate": mode_animate, "retarget": mode_retarget, "physics": mode_physics, "sprites": mode_sprites}
S.main(lambda req: dict(MODES[req["mode"]](req), seconds=None))
