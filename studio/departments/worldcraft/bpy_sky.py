"""Blender: render Blender's Nishita physical sky (Rayleigh + Mie + ozone) to an equirectangular
image with a panoramic Cycles camera. Runs in MeshCraft's bpy venv."""
import math, time
import studio_bpy as S

def run(req):
    import bpy
    t0 = time.time(); sc = S.reset()
    w = bpy.data.worlds.new("Sky"); sc.world = w; w.use_nodes = True; nt = w.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    sky = nt.nodes.new("ShaderNodeTexSky")
    for t in ("NISHITA", "SINGLE_SCATTERING", "MULTIPLE_SCATTERING"):   # name changed across Blender versions
        try: sky.sky_type = t; break
        except TypeError: continue
    sky.sun_elevation = math.radians(req["elevation"]); sky.sun_rotation = math.radians(req["azimuth"])
    for attr, key in (("air_density", "air"), ("dust_density", "dust"), ("ozone_density", "ozone")):
        if hasattr(sky, attr): setattr(sky, attr, req[key])
    if hasattr(sky, "sun_disc"): sky.sun_disc = req["elevation"] > -1
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs[1].default_value = req["strength"]
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(sky.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])
    cam_data = bpy.data.cameras.new("Pano"); cam_data.type = "PANO"
    try: cam_data.panorama_type = "EQUIRECTANGULAR"
    except Exception: cam_data.cycles.panorama_type = "EQUIRECTANGULAR"
    cam = bpy.data.objects.new("Pano", cam_data); sc.collection.objects.link(cam); sc.camera = cam
    cam.rotation_euler = (math.radians(90), 0, math.radians(-90))   # looking at -Y... centre the image on north
    S.cycles(sc, (req["width"], req["height"]), samples=4)
    sc.cycles.use_denoising = False
    sc.view_settings.view_transform = "AgX" if any(v.identifier == "AgX" for v in sc.view_settings.bl_rna.properties["view_transform"].enum_items) else "Filmic"
    sc.render.filepath = req["out"]; bpy.ops.render.render(write_still=True)
    res = {"out": req["out"], "seconds": round(time.time() - t0, 2), "sky_type": sky.sky_type}
    if req.get("exr"):
        sc.render.image_settings.file_format = "OPEN_EXR"; sc.render.image_settings.color_depth = "32"
        sc.view_settings.view_transform = "Standard"
        sc.render.filepath = req["exr"]; bpy.ops.render.render(write_still=True); res["exr"] = req["exr"]
    return res

S.main(run)
