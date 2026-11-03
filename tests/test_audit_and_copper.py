"""MeshCraft overlap audit + the copper sheathing's fit, through scripts/mcp.sh (MCP, sandboxed).

audit_overlaps:
  * a static assembly whose parts don't touch is clean;
  * a moving arm swept through its range hits a block only at the angle where it reaches it, and the report says
    which pose;
  * declared contacts are not reported;
  * proxies (cylinder/box) and material filters work; an empty filtered part is reported, not silently passed.
Copper sheathing (boat_upgrade hull_copper) built from the CURRENT templates with the boat (sloop):
  * along the hull loft's outward normal, the copper's outer skin is outside the sloop's planking skin at EVERY
    sample point (positive offset), so a template change can't bury it under the hull.

  python3 tests/test_audit_and_copper.py
"""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(__file__)); from mcp_client import Client
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ws = os.environ.get("GITCRAFT_ROOT") or tempfile.mkdtemp(prefix="meshcraft-audit-")
os.makedirs(ws, exist_ok=True)
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_MESHCRAFT_LIBRARY=os.path.join(ws, "library"))
res = []
def check(label, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail != "" else ""), flush=True)

c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "meshcraft"], env=env)

# ---------------------------------------------------------------- audit_overlaps on a small rig
rig = os.path.join(ws, "make_rig.py")
open(rig, "w").write('''import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_format="GLB")
# an arm on a pivot at the origin, pointing glTF +Z (Blender -Y), 0.2..1.2 m out
pivot = bpy.data.objects.new("arm_pivot", None); bpy.context.scene.collection.objects.link(pivot)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.7, 0)); arm = bpy.context.active_object; arm.name = "arm"
arm.scale = (0.1, 1.0, 0.1); bpy.ops.object.transform_apply(scale=True); arm.parent = pivot
mat = bpy.data.materials.new("GC_Steel"); arm.data.materials.append(mat)
export([pivot, arm], args["arm"])
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
# a block 0.8 m out along glTF +X: the arm reaches it only when turned 90 degrees about Y
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0.8, 0, 0)); blk = bpy.context.active_object; blk.name = "block"
blk.data.materials.append(bpy.data.materials.new("GC_Red"))
export([blk], args["block"])
''')
arm, block = os.path.join(ws, "arm.glb"), os.path.join(ws, "block.glb")
ok, r = c.call("run_script", {"path": rig, "args": {"arm": arm, "block": block}}, timeout=300)
check("rig: arm + block GLBs written", ok and os.path.exists(arm) and os.path.exists(block), r if not ok else "")

parts = [{"name": "arm", "file": arm}, {"name": "block", "file": block}]
ok, r = c.call("audit_overlaps", {"parts": parts}, timeout=300)
check("audit: static parts that don't touch are clean", ok and r["clean"] and r["pairs"] == 1, r)

sweep = {"part": "arm", "node": "arm_pivot", "axis": "y", "from": 0, "to": 90, "steps": 4}
ok, r = c.call("audit_overlaps", {"parts": parts, "motion": [sweep]}, timeout=300)
hit = (r.get("overlaps") or {}).get("arm x block", {}) if ok else {}
angles = [list(p.values())[0] for p in hit.get("poses", [])]
check("audit: a swept arm hits the block, and only at 90 degrees", ok and not r["clean"] and r["poses"] == 4 and angles == [90.0], r)

ok, r = c.call("audit_overlaps", {"parts": parts, "motion": [sweep], "contacts": [["arm", "block"]]}, timeout=300)
check("audit: declared contacts are not reported", ok and r["clean"], r)

proxy = {"name": "post", "cylinder": {"radius": 0.15, "height": 1.0}, "transform": {"location": [0.8, -0.5, 0]}}
ok, r = c.call("audit_overlaps", {"parts": [parts[1], proxy]}, timeout=300)
check("audit: a block buried inside a proxy cylinder is reported (contained, no surface crossing)",
      ok and r.get("overlaps", {}).get("block x post", {}).get("contained") == "block inside post", r)
ok, r = c.call("audit_overlaps", {"parts": [parts[1], dict(proxy, name="pole", cylinder={"radius": 0.05, "height": 1.0})]}, timeout=300)
check("audit: a thin pole through the block is reported (surfaces cross)", ok and r.get("overlaps", {}).get("block x pole", {}).get("triangles", 0) > 0, r)

ok, r = c.call("audit_overlaps", {"parts": [{"name": "arm_steel", "file": arm, "materials": ["GC_Steel"]},
                                            {"name": "nothing", "file": block, "materials": ["GC_NoSuchMaterial"]}]}, timeout=300)
check("audit: material filters select faces, and an empty part is reported", ok and r["empty_parts"] == ["nothing"], r)

# a Meshopt-compressed copy of the arm (tests/fixtures/arm_meshopt.glb, made with glTF-Transform): Blender can't
# import EXT_meshopt_compression, so the audit decodes it first; the result must match the uncompressed arm's
import shutil
arm_mo = os.path.join(ws, "arm_meshopt.glb"); shutil.copy(os.path.join(HERE, "fixtures", "arm_meshopt.glb"), arm_mo)
ok, r = c.call("audit_overlaps", {"parts": [{"name": "arm", "file": arm_mo}, parts[1]], "motion": [sweep]}, timeout=300)
hit = (r.get("overlaps") or {}).get("arm x block", {}) if ok else {}
check("audit: a Meshopt-compressed GLB is decoded and swept like the original (hit at 90 degrees only)",
      ok and [list(p.values())[0] for p in hit.get("poses", [])] == [90.0], r)

ok, r = c.call("audit_overlaps", {"parts": [{"name": "x", "file": "/etc/hostname"}]}, timeout=60)
check("audit: files outside the roots are refused", not ok and "may only read" in str(r), r)

# ---------------------------------------------------------------- the copper sheathing sits outside the planking
def build(aid, template, params):
    brief = {"asset_id": aid, "template": template, "params": params, "out_dir": os.path.join(ws, aid), "profiles": ["three-web-toon"], "library": False}
    ok, b = c.call("build_asset", {"brief": brief}, timeout=900)
    if not ok: return None, b
    ok, e = c.call("export_asset", {"blend": b["blend"]["path"], "profiles": ["three-web-toon"]}, timeout=900)
    return (next(x["path"] for x in e if x["format"] == "glb") if ok else None), e

boat, eb = build("test_sloop", "boat", {"vessel": "sloop"})
copper, ec = build("test_copper", "boat_upgrade", {"upgrade": "hull_copper"})
check("copper: sloop + copper sheathing built from the current templates", bool(boat and copper), "" if boat and copper else (eb, ec))

measure = os.path.join(ws, "measure_copper.py")
open(measure, "w").write('''import json, bpy
from mathutils import Vector
from engine.procedural.builders import HULLS, hull_point
bpy.ops.wm.read_factory_settings(use_empty=True)
objs = {}
for k, path in args["glbs"].items():
    before = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=path)
    objs[k] = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
def first_hit(meshes, origin, d):
    best = None
    for o in meshes:
        inv = o.matrix_world.inverted()
        ok, loc, n, i = o.ray_cast(inv @ origin, (inv.to_3x3() @ d).normalized())
        if ok:
            dist = (o.matrix_world @ loc - origin).length
            best = dist if best is None or dist < best else best
    return best
h = HULLS["sloop"]; rows = []
for u in [0.08 + 0.06 * i for i in range(15)]:
    for v in (0.95, 0.85, 0.7, 0.5, 0.3, 0.1, -0.1, -0.3, -0.5, -0.7, -0.85, -0.95):
        p = hull_point(h, u, v)
        if p.z > 0.5: continue                      # the sheathing covers the hull below z 0.55
        a, b = hull_point(h, u + 0.01, v), hull_point(h, u, v + (0.02 if v >= 0 else -0.02))
        n = (a - p).cross(b - p).normalized()
        if (n.x < 0) != (v < 0): n = -n
        origin = p + n * 1.0
        hull, cu = first_hit(objs["sloop"], origin, -n), first_hit(objs["copper"], origin, -n)
        rows.append({"u": round(u, 3), "v": v, "z": round(p.z, 3), "hull": hull, "copper": cu,
                     "proud_mm": None if hull is None or cu is None else round((hull - cu) * 1000, 2)})
json.dump(rows, open(args["out"], "w"))   # (run_script's stdout is capped; the rows go to a file)
print(len(rows), "samples")
''')
if boat and copper:
    rows_path = os.path.join(ws, "copper_rows.json")
    ok, r = c.call("run_script", {"path": measure, "args": {"glbs": {"sloop": boat, "copper": copper}, "out": rows_path}}, timeout=600)
    rows = json.load(open(rows_path)) if ok and os.path.exists(rows_path) else []
    measured = [x for x in rows if x["proud_mm"] is not None]
    missing = [x for x in rows if x["proud_mm"] is None]
    buried = [x for x in measured if x["proud_mm"] <= 0]
    mm = [x["proud_mm"] for x in measured]
    check(f"copper: measured at {len(measured)} points along the hull normal, both sides", ok and len(measured) >= 60 and not missing, missing[:3] or r)
    check(f"copper: outside the planking at every point (min {min(mm) if mm else '?'} mm, max {max(mm) if mm else '?'} mm)",
          bool(mm) and not buried, buried[:5])

c.p.kill()
print(f"{sum(res)}/{len(res)} passed")
sys.exit(0 if all(res) else 1)
