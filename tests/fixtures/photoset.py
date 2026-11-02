"""Test fixture, run inside MeshCraft with run_script: renders a ring of photos around an asset,
a synthetic capture for photogrammetry tests (Meshroom needs real overlapping views).

  args.input       GLB to photograph
  args.out         folder for the JPEGs
  args.views       number of photos (default 36), split over args.rings elevations
  args.rings       camera elevations in degrees (default [20, 45])
  args.resolution  pixels (default 1024); args.samples Cycles samples (default 16)
The photos are renders, not camera photos: tests built on them say so.
"""
import math, os
import bpy
from mathutils import Vector

out = args["out"]; os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args["input"])
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ v.co for o in meshes for v in o.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
c = (lo + hi) / 2; size = (hi - lo).length
s = bpy.context.scene
bpy.ops.mesh.primitive_plane_add(size=size * 4, location=(c.x, c.y, lo.z - 0.002))
floor = bpy.context.active_object; m = bpy.data.materials.new("floor"); m.use_nodes = True
noise = m.node_tree.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 40
m.node_tree.links.new(noise.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"]); floor.data.materials.append(m)
w = bpy.data.worlds.new("w"); s.world = w; w.use_nodes = True; w.node_tree.nodes["Background"].inputs[1].default_value = 1.2
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); s.collection.objects.link(sun); sun.data.energy = 3; sun.rotation_euler = (0.6, 0.2, 0.8)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); s.collection.objects.link(cam); cam.data.lens = 35; s.camera = cam
tgt = bpy.data.objects.new("t", None); s.collection.objects.link(tgt); tgt.location = c
tr = cam.constraints.new("TRACK_TO"); tr.target = tgt; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
n = int(args.get("views", 36)); rings = args.get("rings", [20, 45]); res = int(args.get("resolution", 1024))
s.render.engine = "CYCLES"; s.cycles.device = "CPU"; s.cycles.samples = int(args.get("samples", 16))
s.render.resolution_x = s.render.resolution_y = res; s.render.image_settings.file_format = "JPEG"
shots = []
for ri, elev in enumerate(rings):
    k = n // len(rings)
    for i in range(k):
        a = 2 * math.pi * i / k + ri * 0.3; d = size * 1.25
        cam.location = (c.x + d * math.cos(a) * math.cos(math.radians(elev)), c.y + d * math.sin(a) * math.cos(math.radians(elev)), c.z + d * math.sin(math.radians(elev)))
        s.render.filepath = os.path.join(out, f"view_{ri}_{i:02d}.jpg"); bpy.ops.render.render(write_still=True); shots.append(s.render.filepath)
print({"photos": len(shots), "out": out})
