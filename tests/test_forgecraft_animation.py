#!/usr/bin/env python3
"""Regression test: ForgeCraft character animation survives export, and is really checked.

Builds the rigged character through the full ForgeCraft pipeline (routing → MeshCraft/Blender rig and
clips → bake → export → validate) and checks, against the source .blend:
  * rig      the GLB skin has the 22 Mixamo-named joints; the FBX re-imports with the same 22 bones
  * actions  the 6 clips exist by name in the GLB and the FBX
  * keys     every GLB clip animates rig joints with at least 2 keyframes, real motion (values change)
             and the source action's duration; every FBX action has keyframes
  * playback three.js r170 loads all 6 clips and every one of them moves the rig
Also covers the two causes of the earlier failure (engine check silently skipped on a standard
install, and a skipped check reported as "passed-with-warnings"):
  * the engine check finds its pinned modules on a standard install (MeshCraft's engine_check)
  * when no matching modules exist the asset is "unverified", never "passed*"

    tests/test_forgecraft_animation.py
"""
import json, os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); FC = os.path.join(HERE, "..", "forgecraft")
TMP = tempfile.mkdtemp(prefix="forgecraft-anim-")
os.environ["FORGECRAFT_LIBRARY"] = os.path.join(TMP, "lib")
sys.path.insert(0, FC)
import hardware, library, pipeline
from backends import blockbench

BLENDER_PY = hardware.BLENDER_PY
CLIPS = {"Attack", "Idle", "Interact", "Jump", "Run", "Walk"}
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:600]}]"), flush=True)


def glb(path):
    b = open(path, "rb").read(); n = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + n]); binc = b[20 + n + 8:]
    def acc(i):
        a = j["accessors"][i]; bv = j["bufferViews"][a["bufferView"]]
        comps = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
        if a["componentType"] != 5126: raise ValueError("animation data is not float")
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0); stride = bv.get("byteStride") or 4 * comps
        return [struct.unpack_from(f"<{comps}f", binc, off + k * stride) for k in range(a["count"])]
    return j, acc


def blender(code, *args):
    r = subprocess.run([BLENDER_PY, "-c", code, *args], capture_output=True, text=True, timeout=600)
    line = [l for l in r.stdout.splitlines() if l.startswith("@@")]
    if not line: raise RuntimeError(r.stderr[-800:] or r.stdout[-800:])
    return json.loads(line[-1][2:])


SRC = r'''
import bpy, json, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[1]); s = bpy.context.scene; fps = s.render.fps / s.render.fps_base
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
def curves(a):
    try: return list(a.fcurves)
    except Exception: return [c for l in a.layers for st in l.strips for cb in st.channelbags for c in cb.fcurves]
print("@@" + json.dumps({"fps": fps, "bones": sorted(b.name for a in arms for b in a.data.bones),
  "actions": {a.name: {"frames": list(a.frame_range), "curves": len(curves(a)), "keys": sum(len(c.keyframe_points) for c in curves(a))} for a in bpy.data.actions}}))
'''
FBX = r'''
import bpy, json, sys
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.fbx(filepath=sys.argv[1])
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
def curves(a):
    try: return list(a.fcurves)
    except Exception: return [c for l in a.layers for st in l.strips for cb in st.channelbags for c in cb.fcurves]
print("@@" + json.dumps({"bones": sorted(b.name for a in arms for b in a.data.bones),
  "actions": {a.name: {"curves": len(curves(a)), "keys": sum(len(c.keyframe_points) for c in curves(a))} for a in bpy.data.actions}}))
'''

# ---------------------------------------------------------------- the engine check can run on a standard install
mods, why = pipeline.web_modules()
check("engine check finds three.js + gltf-validator at the pinned versions", mods is not None, why)

# ---------------------------------------------------------------- the character, end to end
r = pipeline.run(dict(bake=256, turntable=1, formats=["glb", "fbx", "blend"], brief="animated pirate character", name="anim char"))
md = library.get(r["asset"]["id"], r["asset"]["version"]) if r.get("asset") else None
check("character job finishes and is validated", md and r["status"] == "done" and md["validation"]["status"] in ("passed", "passed-with-warnings"),
      (r.get("error"), md and md["validation"].get("status")))
if md:
    d = md.get("dir") or library.path("assets", md["id"], f"v{md['version']}")
    glb_path = os.path.join(d, md["files"]["glb"]["path"]); fbx_path = os.path.join(d, md["files"]["fbx"]["path"])
    blend_path = os.path.join(d, md["files"]["blend"]["path"])
    src = blender(SRC, blend_path)
    src_clips = {k: v for k, v in src["actions"].items() if k in CLIPS}
    check("source .blend: 22 Mixamo bones and the 6 clips with keyframes",
          len(src["bones"]) == 22 and all(b.startswith("mixamorig:") for b in src["bones"]) and set(src_clips) == CLIPS and all(v["keys"] > 0 for v in src_clips.values()),
          {"bones": len(src["bones"]), "actions": src["actions"]})

    j, acc = glb(glb_path)
    joints = [j["nodes"][i]["name"] for i in (j.get("skins") or [{}])[0].get("joints", [])]
    check("GLB rig: skin with the same 22 Mixamo joints", sorted(joints) == src["bones"], joints)
    anims = {a["name"]: a for a in j.get("animations", [])}
    check("GLB actions: the 6 clips by name", set(anims) >= CLIPS, sorted(anims))
    joint_nodes = set((j.get("skins") or [{}])[0].get("joints", []))
    bad = {}
    for name in CLIPS & set(anims):
        a = anims[name]; on_joints = [c for c in a["channels"] if c["target"].get("node") in joint_nodes]
        times = [acc(a["samplers"][c["sampler"]]["input"]) for c in on_joints]
        moving = sum(1 for c in on_joints if len({tuple(round(x, 5) for x in v) for v in acc(a["samplers"][c["sampler"]]["output"])}) > 1)
        dur = max((t[-1][0] for t in times), default=0)
        f0, f1 = src_clips[name]["frames"]; want = (f1 - f0) / src["fps"]
        problems = []
        if not on_joints: problems.append("no channels on rig joints")
        if any(len(t) < 2 for t in times): problems.append("a channel with < 2 keyframes")
        if moving == 0: problems.append("no channel changes value (no motion)")
        if abs(dur - want) > 1.5 / src["fps"]: problems.append(f"duration {dur:.3f}s, source {want:.3f}s")
        if problems: bad[name] = problems
    check("GLB keyframes: every clip animates rig joints, has motion and keeps the source duration", not bad and set(anims) >= CLIPS, bad)

    fb = blender(FBX, fbx_path)
    fbx_clips = {n for n in fb["actions"] if any(n == c or n.endswith("|" + c) for c in CLIPS)}
    check("FBX rig: re-imports with the same 22 bones", sorted(fb["bones"]) == src["bones"], fb["bones"])
    check("FBX actions + keyframes: the 6 clips re-import with keyframes",
          {c for c in CLIPS if any(n == c or n.endswith("|" + c) for n in fbx_clips)} == CLIPS and all(fb["actions"][n]["keys"] > 0 for n in fbx_clips),
          fb["actions"])

    eng = md["validation"].get("engine", {}); f = (eng.get("files") or {}).get(os.path.basename(glb_path), {})
    check("three.js r170 playback: engine check ran (not skipped) and loaded all 6 clips", eng.get("status") == "passed" and f.get("three_clips", 0) >= 6, eng)
    check("three.js r170 playback: every clip moves the rig", f.get("three_clips", 0) >= 6 and f.get("three_clips_static") == [], f)

# ---------------------------------------------------------------- a check that cannot run is never a pass
bb = os.path.join(TMP, "crate.bbmodel"); blockbench.build("crate", "crate", bb)
os.environ["FORGECRAFT_WEB_MODULES"] = os.path.join(TMP, "no-modules-here")
try:
    r2 = pipeline.run(dict(brief="crate bbmodel", input_mesh=bb, name="unverified crate", turntable=1, formats=["glb"]))
finally:
    os.environ.pop("FORGECRAFT_WEB_MODULES")
m2 = library.get(r2["asset"]["id"], r2["asset"]["version"]) if r2.get("asset") else None
v2 = (m2 or {}).get("validation", {})
check("no engine-check modules → asset is 'unverified', not passed, with the reason", r2["status"] == "done" and v2.get("status") == "unverified"
      and v2.get("engine", {}).get("status") == "skipped" and "no node_modules" in v2.get("engine", {}).get("reason", ""), (r2.get("error"), v2.get("status"), v2.get("engine")))

print(f"\n{sum(results)}/{len(results)} checks passed   ({TMP})")
sys.exit(0 if all(results) else 1)
