"""Mixamo (Adobe) character animation through its supported manual workflow. Needs bpy
(except GUIDE / guide()).

Mixamo has no public API and scripted use of its website is not a supported access method,
so MeshCraft never contacts mixamo.com. It covers the two file hand-offs around the
person who uses the site:

  * prepare_upload: a character → an unrigged, mesh-only FBX for Mixamo's auto-rigger.
  * apply:          animation FBX files downloaded from Mixamo ("Without Skin") → merged onto
                    a character with a Mixamo skeleton, each download kept as its own named
                    clip, saved as a MeshCraft .blend (then exported with any profile).

Bones are matched by name with the `mixamorig:` / `mixamorig1:` prefixes ignored. A clip is
refused, with the reason, when too few core bones match or when the two skeletons' rest
poses differ (a clip made for another skeleton would play distorted). Hip motion is rescaled
when the character is a different size from the skeleton the clip was downloaded with.
Licence: Mixamo characters and animations are royalty-free in personal, commercial and
non-profit projects; do not redistribute the raw Mixamo files on their own (see
docs/3d-licensing.md).
Ported from the 3D Department proposal (GITCRAFT PR #9), with the skeleton checks added.
"""
import json, math, os, re, time

GUIDE = [
    "1. Run mixamo_prepare_upload on the character (any GLB/FBX/OBJ/.blend in the workspace, standing in a T-pose or A-pose).",
    "2. Sign in at https://www.mixamo.com with an Adobe ID, choose Upload Character, upload the FBX and place the rig markers if asked.",
    "3. Download the rigged character once: Format FBX Binary, Skin: With Skin, T-pose. This is the `character` for mixamo_apply.",
    "4. Pick animations (Idle, Walking, Running, Jump, ...). Tick 'In Place' for locomotion the game moves itself.",
    "5. Download each as Format: FBX Binary (.fbx), Skin: Without Skin, Frames per Second: 30, Keyframe Reduction: none.",
    "6. Put the files inside a GITCRAFT root (e.g. <repo>/art/mixamo/) and run mixamo_apply with the character and the animation files.",
    "7. MeshCraft keeps each file as its own clip (named after the file), saves a .blend and exports the profiles you ask for.",
]
CORE = ["Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand",
        "RightShoulder", "RightArm", "RightForeArm", "RightHand", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase",
        "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"]
MIN_CORE = 12          # matched core bones needed before a clip is accepted
MAX_REST_DEV = 0.08    # mean rest-pose joint offset, as a fraction of the hips→head length
MAX_REST_ANGLE = 20.0  # mean rest-pose bone direction difference, degrees
PREFIX = re.compile(r"^mixamorig\d*[:_]", re.I)


def guide():
    return {"steps": GUIDE, "core_bones": CORE, "bone_prefixes": ["mixamorig:", "mixamorig1:", "mixamorig_"],
            "network": "MeshCraft never contacts mixamo.com; a person does the upload and downloads.",
            "licence": "Royalty-free for games (personal, commercial, non-profit); do not redistribute raw Mixamo files standalone or use them to train models."}


def key(name):
    return PREFIX.sub("", name).replace(" ", "").lower()


def _import(path):
    import bpy
    before = set(bpy.data.objects); acts = set(bpy.data.actions)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False, ignore_leaf_bones=False)  # Mixamo *_End leaf bones are harmless; True drops real leaves
    elif ext in (".glb", ".gltf"): bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path)
    else: raise ValueError(f"cannot import {ext}; use FBX, GLB/glTF or OBJ")
    return [o for o in bpy.data.objects if o not in before], [a for a in bpy.data.actions if a not in acts]


def prepare_upload(src, out):
    """Character → mesh-only FBX (modifiers applied, rig and weights removed) for Mixamo's auto-rigger."""
    import bpy
    from . import kit, core
    t0 = time.time()
    if src.lower().endswith(".blend"):
        core.open_blend(src); objs = list(bpy.context.scene.objects)
    else:
        kit.reset(); objs, _ = _import(src)
    for a in [o for o in objs if o.type == "ARMATURE"]: a.data.pose_position = "REST"
    for o in list(bpy.context.scene.objects):   # references and helpers never ship
        if o.type == "EMPTY" and o.empty_display_type == "IMAGE": bpy.data.objects.remove(o)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]
    if not meshes: raise ValueError("no meshes to upload")
    dg = bpy.context.evaluated_depsgraph_get(); baked = []
    for o in meshes:   # freeze the rest-pose shape in world space
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
        n = bpy.data.objects.new(o.name + "_upload", me); bpy.context.scene.collection.objects.link(n); baked.append(n)
    for o in list(bpy.context.scene.objects):
        if o not in baked: bpy.data.objects.remove(o)
    body = kit.join(baked, "character") if len(baked) > 1 else baked[0]
    body.vertex_groups.clear()
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    for o in bpy.context.scene.objects: o.select_set(o is body)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, bake_anim=False, add_leaf_bones=False, path_mode="COPY",
                             embed_textures=True, axis_forward="-Z", axis_up="Y", apply_scale_options="FBX_SCALE_UNITS")
    dims = [round(v, 3) for v in body.dimensions]
    return {"fbx": core._file(out, "mixamo_upload"), "triangles": sum(len(p.vertices) - 2 for p in body.data.polygons),
            "size_m": dims, "seconds": round(time.time() - t0, 2),
            "note": "Upload this file at mixamo.com (Upload Character). It must stand in a T-pose or A-pose; Mixamo asks for rig markers if it cannot place them."}


def _rest(arm):
    """key -> (head in armature space, unit direction) for every bone."""
    return {key(b.name): (b.head_local.copy(), (b.tail_local - b.head_local).normalized()) for b in arm.data.bones}


def _compare(tgt, src):
    shared = sorted(set(tgt) & set(src))
    core_hit = [c for c in CORE if c.lower() in shared]
    if len(core_hit) < MIN_CORE:
        return {"shared": len(shared), "core": len(core_hit), "ok": False,
                "reason": f"only {len(core_hit)} of the {len(CORE)} Mixamo core bones match (need {MIN_CORE}); is this a Mixamo skeleton?"}
    if "hips" not in shared or "head" not in shared:
        return {"shared": len(shared), "core": len(core_hit), "ok": False, "reason": "both skeletons need Hips and Head bones"}
    th, sh = tgt["hips"][0], src["hips"][0]
    tl = (tgt["head"][0] - th).length or 1; sl = (src["head"][0] - sh).length or 1
    dev = sum((((tgt[k][0] - th) / tl) - ((src[k][0] - sh) / sl)).length for k in shared) / len(shared)
    ang = sum(math.degrees(tgt[k][1].angle(src[k][1], 0)) for k in shared) / len(shared)
    ok = len(core_hit) >= MIN_CORE and dev <= MAX_REST_DEV and ang <= MAX_REST_ANGLE
    reason = None
    if len(core_hit) < MIN_CORE: reason = f"only {len(core_hit)} of the {len(CORE)} Mixamo core bones match (need {MIN_CORE}); is this a Mixamo skeleton?"
    elif dev > MAX_REST_DEV or ang > MAX_REST_ANGLE:
        reason = (f"rest poses differ (joint offset {dev:.2f} of body height, bone direction {ang:.0f}°): download the clip from Mixamo "
                  "with this character uploaded, so Mixamo retargets it, instead of reusing a clip made for another skeleton")
    return {"shared": len(shared), "core": len(core_hit), "rest_offset": round(dev, 3), "rest_angle_deg": round(ang, 1),
            "scale": round(tl / sl, 4), "ok": ok, "reason": reason}


def apply(character, animations, out_dir, asset_id, material_prefix="MX"):
    """Merge Mixamo animation downloads onto a Mixamo-skeleton character; save out_dir/source/<asset_id>.blend."""
    import bpy
    from . import kit, core
    t0 = time.time()
    if not animations: raise ValueError("give at least one animation FBX")
    if character.lower().endswith(".blend"):
        core.open_blend(character); objs = list(bpy.context.scene.objects)
    else:
        kit.reset(); objs, _ = _import(character)
    arms = [o for o in objs if o.type == "ARMATURE"]
    if not arms: raise ValueError("the character has no armature: rig it at mixamo.com first (mixamo_prepare_upload)")
    arm = max(arms, key=lambda a: len(a.data.bones))
    names = {key(b.name): b.name for b in arm.data.bones}
    trest = _rest(arm)
    if arm.animation_data is None: arm.animation_data_create()
    arm.animation_data.action = None    # a "With Skin" download carries its own take: not a clip (existing NLA clips are kept)
    clips, rejected = [], []
    for path in animations:
        clip = re.sub(r"[^A-Za-z0-9_]+", "_", os.path.splitext(os.path.basename(path))[0]).strip("_") or "clip"
        new_objs, new_acts = _import(path)
        src = next((o for o in new_objs if o.type == "ARMATURE"), None)
        act = (src.animation_data.action if src and src.animation_data and src.animation_data.action else (new_acts[0] if new_acts else None))
        cmp = _compare(trest, _rest(src)) if src else {"ok": False, "reason": "the file has no armature"}
        if src and not act: cmp = dict(cmp, ok=False, reason="the file has no animation")
        if not cmp["ok"]:
            rejected.append({"file": path, **cmp})
        else:
            mapped = dropped = 0
            for fc in kit._fcurves(act, src):
                m = re.match(r'pose\.bones\["(.+?)"\]\.(\w+)', fc.data_path)
                if not m: continue
                tgt = names.get(key(m.group(1)))
                if tgt is None: dropped += 1; continue
                fc.data_path = f'pose.bones["{tgt}"].{m.group(2)}'; mapped += 1
                if m.group(2) == "location" and abs(cmp["scale"] - 1) > 1e-3:
                    for kp in fc.keyframe_points:
                        kp.co.y *= cmp["scale"]; kp.handle_left.y *= cmp["scale"]; kp.handle_right.y *= cmp["scale"]
            act.name = clip; act.use_fake_user = True
            tr = arm.animation_data.nla_tracks.new(); tr.name = clip
            st = tr.strips.new(clip, int(act.frame_range[0]), act); st.name = clip; tr.mute = True
            try:
                if len(act.slots): st.action_slot = act.slots[0]
            except Exception: pass
            clips.append({"clip": clip, "file": path, "frames": [int(act.frame_range[0]), int(act.frame_range[1])],
                          "curves": mapped, "unmatched_curves": dropped, "matched_bones": cmp["shared"], "rest_offset": cmp["rest_offset"],
                          "rest_angle_deg": cmp["rest_angle_deg"], "hip_scale": cmp["scale"]})
        for o in new_objs:
            if o.name in bpy.data.objects: bpy.data.objects.remove(o)
    if not clips:
        raise ValueError("no animation could be applied: " + "; ".join(f"{os.path.basename(r['file'])}: {r['reason']}" for r in rejected))
    # only real clips ship: drop the FBX takes ("Armature|Scene", the T-pose of a With Skin download, rejected files)
    stashed = {st.action for o in bpy.data.objects if o.animation_data for tr in o.animation_data.nla_tracks for st in tr.strips if st.action}
    for a in list(bpy.data.actions):
        if a not in stashed: bpy.data.actions.remove(a)
    root = next((o for o in bpy.context.scene.objects if o.type == "EMPTY" and o.parent is None and o.name == asset_id), None)
    if root is None:
        root = kit.empty(asset_id)
        for o in bpy.context.scene.objects:
            if o.parent is None and o is not root: mw = o.matrix_world.copy(); o.parent = root; o.matrix_world = mw
    s = bpy.context.scene
    prev = json.loads(s.get("gitcraft_brief", "{}")) if character.lower().endswith(".blend") else {}
    brief = dict(prev, asset_id=asset_id, out_dir=out_dir, template=prev.get("template", "mixamo"), source=character,
                 mixamo={"character": character, "animations": animations}, material_prefix=prev.get("material_prefix", material_prefix))
    brief.setdefault("params", {})
    result = json.loads(s.get("gitcraft_result", "{}")) if prev else {}
    contract = dict(result.get("contract") or {}); contract["clips"] = sorted(set((contract.get("clips") or []) + [c["clip"] for c in clips]))
    result["contract"] = contract
    s["gitcraft_brief"] = json.dumps(brief); s["gitcraft_result"] = json.dumps(result); s["gitcraft_template"] = brief["template"]
    blend = os.path.join(out_dir, "source", f"{asset_id}.blend"); os.makedirs(os.path.dirname(blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    return {"blend": core._file(blend, "blend"), "armature": arm.name, "bones": len(arm.data.bones), "clips": clips, "rejected": rejected,
            "seconds": round(time.time() - t0, 2)}
