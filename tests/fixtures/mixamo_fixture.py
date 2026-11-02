"""Test fixture, run inside MeshCraft with run_script: writes Mixamo-layout FBX files.

  args.out      folder for the files
  args.kind     "character"  rigged, skinned T-pose character ("With Skin" download)
                "clip"       armature-only walk cycle ("Without Skin" download), saved as args.clip_name
                "foreign"    armature-only clip on a non-Mixamo skeleton (must be refused)
                "apose"      Mixamo names but arms down (rest pose differs: must be refused)
  args.prefix   bone name prefix (default "mixamorig:"; Mixamo also ships "mixamorig1:")
  args.scale    skeleton size factor (default 1)
These stand in for real mixamo.com downloads, which need a person with an Adobe ID.
"""
import os
import bpy

out = args["out"]; kind = args.get("kind", "character"); P = args.get("prefix", "mixamorig:"); S = float(args.get("scale", 1.0))
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene; scene.render.fps = 30

arm_down = kind == "apose"
J = {  # bone: (head, tail, parent)   metres, Z up, character faces -Y
    "Hips": ((0, 0, 1.0), (0, 0, 1.1), None), "Spine": ((0, 0, 1.1), (0, 0, 1.2), "Hips"), "Spine1": ((0, 0, 1.2), (0, 0, 1.3), "Spine"),
    "Spine2": ((0, 0, 1.3), (0, 0, 1.42), "Spine1"), "Neck": ((0, 0, 1.42), (0, 0, 1.52), "Spine2"), "Head": ((0, 0, 1.52), (0, 0, 1.75), "Neck"),
    "LeftUpLeg": ((0.1, 0, 1.0), (0.1, 0, 0.55), "Hips"), "LeftLeg": ((0.1, 0, 0.55), (0.1, 0, 0.1), "LeftUpLeg"),
    "LeftFoot": ((0.1, 0, 0.1), (0.1, -0.12, 0.02), "LeftLeg"), "LeftToeBase": ((0.1, -0.12, 0.02), (0.1, -0.2, 0.02), "LeftFoot"),
    "RightUpLeg": ((-0.1, 0, 1.0), (-0.1, 0, 0.55), "Hips"), "RightLeg": ((-0.1, 0, 0.55), (-0.1, 0, 0.1), "RightUpLeg"),
    "RightFoot": ((-0.1, 0, 0.1), (-0.1, -0.12, 0.02), "RightLeg"), "RightToeBase": ((-0.1, -0.12, 0.02), (-0.1, -0.2, 0.02), "RightFoot"),
}
for side, sx in (("Left", 1), ("Right", -1)):
    if arm_down:
        J.update({f"{side}Shoulder": ((0.05 * sx, 0, 1.4), (0.18 * sx, 0, 1.4), "Spine2"), f"{side}Arm": ((0.18 * sx, 0, 1.4), (0.2 * sx, 0, 1.12), f"{side}Shoulder"),
                  f"{side}ForeArm": ((0.2 * sx, 0, 1.12), (0.21 * sx, 0, 0.88), f"{side}Arm"), f"{side}Hand": ((0.21 * sx, 0, 0.88), (0.21 * sx, 0, 0.78), f"{side}ForeArm")})
    else:
        J.update({f"{side}Shoulder": ((0.05 * sx, 0, 1.4), (0.18 * sx, 0, 1.4), "Spine2"), f"{side}Arm": ((0.18 * sx, 0, 1.4), (0.46 * sx, 0, 1.4), f"{side}Shoulder"),
                  f"{side}ForeArm": ((0.46 * sx, 0, 1.4), (0.72 * sx, 0, 1.4), f"{side}Arm"), f"{side}Hand": ((0.72 * sx, 0, 1.4), (0.82 * sx, 0, 1.4), f"{side}ForeArm")})
name = (lambda b: f"Bone_{sorted(J).index(b):02d}") if kind == "foreign" else (lambda b: P + b)

ad = bpy.data.armatures.new("Armature"); arm = bpy.data.objects.new("Armature", ad); scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm; arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
for b, (h, t, par) in J.items():
    eb = ad.edit_bones.new(name(b)); eb.head = [v * S for v in h]; eb.tail = [v * S for v in t]
for b, (h, t, par) in J.items():
    if par: ad.edit_bones[name(b)].parent = ad.edit_bones[name(par)]; ad.edit_bones[name(b)].use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")

if kind == "character":
    import bmesh
    from mathutils import Vector
    bm = bmesh.new(); groups = []
    for b, (h, t, par) in J.items():
        h, t = Vector(h) * S, Vector(t) * S; c = (h + t) / 2; d = t - h
        size = Vector((max(abs(d.x), 0.08 * S), max(abs(d.y), 0.08 * S), max(abs(d.z), 0.08 * S)))
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r["verts"]: v.co = Vector((v.co.x * size.x, v.co.y * size.y, v.co.z * size.z)) + c
        groups.append((name(b), [v.index for v in bm.verts][-8:]))
    me = bpy.data.meshes.new("Body"); bm.to_mesh(me); bm.free()
    body = bpy.data.objects.new("Body", me); scene.collection.objects.link(body)
    mat = bpy.data.materials.new("Skin"); mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.45, 0.3, 1); me.materials.append(mat)
    for gname, idx in groups: body.vertex_groups.new(name=gname).add(idx, 1.0, "REPLACE")
    body.parent = arm; body.modifiers.new("Armature", "ARMATURE").object = arm
    for o in scene.objects: o.select_set(True)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, "character.fbx"), use_selection=True, bake_anim=False, add_leaf_bones=False,
                             axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_UNITS")
    print("wrote", os.path.join(out, "character.fbx"))
else:
    arm.animation_data_create(); act = bpy.data.actions.new("mixamo.com"); arm.animation_data.action = act
    for pb in arm.pose.bones: pb.rotation_mode = "XYZ"
    for f, ph in ((1, 0.0), (8, 1.0), (16, 0.0), (23, -1.0), (31, 0.0)):
        for b, k in (("LeftUpLeg", 0.5), ("RightUpLeg", -0.5), ("LeftArm", -0.3), ("RightArm", 0.3)):
            pb = arm.pose.bones[name(b)]; pb.rotation_euler = (k * ph, 0, 0); pb.keyframe_insert("rotation_euler", frame=f)
        hp = arm.pose.bones[name("Hips")]; hp.location = (0, 0.03 * abs(ph) * S, 0); hp.keyframe_insert("location", frame=f)
    scene.frame_start, scene.frame_end = 1, 31
    for o in scene.objects: o.select_set(o is arm)
    fn = {"clip": args.get("clip_name", "Walking.fbx"), "foreign": "Foreign_Walk.fbx", "apose": "APose_Walk.fbx"}[kind]
    bpy.ops.export_scene.fbx(filepath=os.path.join(out, fn), use_selection=True, bake_anim=True, bake_anim_use_all_actions=False,
                             bake_anim_use_nla_strips=False, add_leaf_bones=False, axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_UNITS")
    print("wrote", os.path.join(out, fn))
