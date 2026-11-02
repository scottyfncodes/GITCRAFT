"""MeshCraft Blender helpers. Imported by scripts that run inside Blender's Python
(the official `bpy` module from PyPI, run headless in its own process).

Conventions shared by every MeshCraft asset:
  * metres, Z up in Blender. glTF export converts to Y up; Blender -Y becomes glTF +Z,
    so "forward" for vehicles and characters is Blender -Y = glTF/three.js +Z
    (TIDEBREAKERS' shipModel puts the bow at +Z).
  * every asset is collected under one root object named after the asset slug.
  * rendering uses Cycles on the CPU: EEVEE and Workbench need an OpenGL/EGL
    context and abort the process on headless machines.
"""
import math, os, json, random
import bpy, bmesh
from mathutils import Vector, Matrix

# TIDEBREAKERS palette (creative/branding/palette/tidebreakers-palette.json) plus neutrals.
PALETTE = {
    "lagoon": "#1FB5B0", "aqua": "#7FE3D6", "sea": "#1A7FA8", "deep": "#0E3B66", "midnight": "#0A2142",
    "gold": "#F4C542", "gold_deep": "#C98A12", "amber": "#FF9F2E", "coral": "#FF6B4A", "crimson": "#C0392B",
    "hibiscus": "#E0607E", "cream": "#F6EAD0", "parchment": "#ECDAB4", "palm": "#3FA55A", "jungle": "#1E6B4E",
    "honey": "#D9954F", "timber": "#9A5A2E", "deep_timber": "#5E331B", "plum": "#3B2350", "dusk": "#6A4C93",
    "sky": "#7CCBF2", "sky_high": "#CFF1FF", "sand": "#F7D9A0", "foam": "#E9FBF6",
    "iron": "#4A4F57", "copper": "#C77B4A", "stone": "#8C8A86", "rope": "#C9A46B", "skin": "#E8B48A",
    "white": "#F4F4F0", "black": "#1B1B1F",
}


def hex_rgb(h):
    h = PALETTE.get(h, h).lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(lin(c) for c in srgb)


# ---------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.render.fps = 30
    return s


def link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.3
    e.location = loc
    link(e)
    if parent: e.parent = parent
    return e


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT") if bpy.context.view_layer.objects else None
    for o in objs: o.select_set(True)
    if objs: bpy.context.view_layer.objects.active = objs[0]


# ---------------------------------------------------------------- materials
_mats = {}


def mat(color, kind="plain", rough=0.65, metal=0.0, emit=0.0, name=None):
    """Principled material with an optional procedural detail layer (wood grain, cloth
    weave, sand speckle...). The detail is real shader texture that the bake stage turns
    into PNG texture maps."""
    key = (color, kind, rough, metal, emit)
    if key in _mats and _mats[key].name in bpy.data.materials: return _mats[key]
    m = bpy.data.materials.new(name or f"M_{kind}_{str(color).strip('#')}")
    if getattr(m, "node_tree", None) is None: m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    base = hex_rgb(color) + (1.0,)
    bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if emit:
        bsdf.inputs["Emission Color"].default_value = base
        bsdf.inputs["Emission Strength"].default_value = emit
    m["mc_kind"], m["mc_rough"], m["mc_metal"] = kind, rough, metal
    if kind != "plain":
        tc = nt.nodes.new("ShaderNodeTexCoord")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        dark = tuple(c * 0.62 for c in base[:3]) + (1.0,)
        light = tuple(min(1.0, c * 1.18) for c in base[:3]) + (1.0,)
        ramp.color_ramp.elements[0].color = dark if kind != "sand" else base
        ramp.color_ramp.elements[1].color = light
        if kind in ("wood", "plank"):
            wave = nt.nodes.new("ShaderNodeTexWave")
            wave.wave_type = "BANDS"; wave.bands_direction = "Z" if kind == "plank" else "X"
            wave.inputs["Scale"].default_value = 3.0 if kind == "plank" else 1.2
            wave.inputs["Distortion"].default_value = 6.0
            wave.inputs["Detail"].default_value = 3.0
            nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
            nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
            ramp.color_ramp.elements[0].position = 0.25
        else:
            noise = nt.nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = {"cloth": 40.0, "sand": 60.0, "rock": 4.0, "grass": 12.0,
                                                   "metal": 20.0, "skin": 6.0}.get(kind, 10.0)
            noise.inputs["Detail"].default_value = 6.0
            nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
            nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
            ramp.color_ramp.elements[0].position = {"sand": 0.55, "cloth": 0.42}.get(kind, 0.35)
            ramp.color_ramp.elements[1].position = {"sand": 0.75, "cloth": 0.6}.get(kind, 0.7)
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs[6].default_value = base
        nt.links.new(ramp.outputs["Color"], mix.inputs[7])
        # keep the palette colour dominant: multiply against a ramp centred on white
        ramp.color_ramp.elements[0].color = (0.72, 0.72, 0.72, 1) if kind not in ("rock",) else (0.6, 0.6, 0.6, 1)
        ramp.color_ramp.elements[1].color = (1.08, 1.08, 1.08, 1)
        nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    _mats[key] = m
    return m


def assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


# ---------------------------------------------------------------- geometry builders
def mesh_obj(name, verts, faces, material=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(); me.update()
    o = link(bpy.data.objects.new(name, me))
    if material: assign(o, material)
    for p in me.polygons: p.use_smooth = smooth
    return o


def prim(kind, name, material=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1), **kw):
    ops = {"cube": bpy.ops.mesh.primitive_cube_add, "cyl": bpy.ops.mesh.primitive_cylinder_add,
           "cone": bpy.ops.mesh.primitive_cone_add, "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
           "ico": bpy.ops.mesh.primitive_ico_sphere_add, "torus": bpy.ops.mesh.primitive_torus_add,
           "plane": bpy.ops.mesh.primitive_plane_add, "grid": bpy.ops.mesh.primitive_grid_add}
    ops[kind](location=loc, rotation=rot, **kw)
    o = bpy.context.active_object
    o.name = name
    o.scale = scale
    if material: assign(o, material)
    apply_xf(o)
    return o


def apply_xf(o):
    select_only([o])
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return o


def shade(o, smooth_angle=None):
    select_only([o])
    if smooth_angle is None:
        bpy.ops.object.shade_flat()
    else:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle))
    return o


def join(objs, name):
    objs = [o for o in objs if o and o.type == "MESH"]
    select_only(objs)
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = name; o.data.name = name
    return o


def solidify(o, t):
    m = o.modifiers.new("solid", "SOLIDIFY"); m.thickness = t; m.offset = 0
    select_only([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return o


def bevel(o, w=0.02, seg=1):
    m = o.modifiers.new("bev", "BEVEL"); m.width = w; m.segments = seg; m.limit_method = "ANGLE"
    select_only([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return o


# ---------------------------------------------------------------- processing stages
def mesh_objects(root):
    out = [root] if root.type == "MESH" else []
    for c in root.children_recursive:
        if c.type == "MESH": out.append(c)
    return out


def tri_count(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs if o.type == "MESH")


def cleanup(o, merge=0.0005):
    """Merge duplicate vertices, drop loose geometry and degenerate faces, make normals consistent."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge)
    loose = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bmesh.ops.dissolve_degenerate(bm, dist=merge * 0.1, edges=bm.edges)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    after = len(bm.verts)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    return {"merged_vertices": before - after}


def decimate(o, max_tris):
    t = tri_count([o])
    if t <= max_tris: return {"tris_before": t, "tris_after": t, "ratio": 1.0}
    ratio = max_tris / t
    m = o.modifiers.new("dec", "DECIMATE"); m.ratio = ratio; m.use_collapse_triangulate = True
    select_only([o]); bpy.ops.object.modifier_apply(modifier=m.name)
    return {"tris_before": t, "tris_after": tri_count([o]), "ratio": round(ratio, 4)}


def uv_unwrap(o, margin=0.012):
    """Unwrap into a new UV layer (MC_UV). Existing image textures keep sampling their original
    UVs through explicit UV Map nodes, so the bake can transfer them (e.g. photogrammetry textures)."""
    me = o.data
    orig = me.uv_layers.active.name if me.uv_layers else None
    if orig:
        for m in [m for m in me.materials if m]:
            nt = m.node_tree
            for n in [n for n in nt.nodes if n.type == "TEX_IMAGE" and not n.inputs["Vector"].is_linked]:
                uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = orig
                nt.links.new(uvn.outputs["UV"], n.inputs["Vector"])
    new = me.uv_layers.new(name="MC_UV")
    me.uv_layers.active = new; new.active_render = True
    select_only([o])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=margin, area_weight=0.6)
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"uv_layers": len(o.data.uv_layers), "source_uv": orig}


def _cycles(s, samples=16):
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    try: s.cycles.use_denoising = True
    except Exception: pass


def bake_textures(o, out_dir, slug, res=1024):
    """Bake every material on `o` into two PNG maps (base colour, glTF metallic-roughness)
    and replace them with one textured material: one draw call, real texture maps."""
    if os.environ.get("MESHCRAFT_FAULT") == "bake" and res >= 512:   # fault injection for tests/test_meshcraft.py
        raise RuntimeError(f"injected bake fault at {res}px")
    s = bpy.context.scene
    _cycles(s, 4)
    s.cycles.use_denoising = False
    os.makedirs(out_dir, exist_ok=True)
    imgs = {}
    for kind in ("basecolor", "metalrough"):
        img = bpy.data.images.new(f"{slug}_{kind}", res, res, alpha=False)
        img.colorspace_settings.name = "sRGB" if kind == "basecolor" else "Non-Color"
        imgs[kind] = img
    mats = [m for m in o.data.materials if m]
    if not mats:
        mats = [mat("#cccccc")]; o.data.materials.append(mats[0])
    # meshes from AI generators carry vertex colours: feed them into the base colour so the bake keeps them
    if o.data.color_attributes:
        for m in mats:
            nt = m.node_tree; bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if bsdf and not bsdf.inputs["Base Color"].is_linked:
                vc = nt.nodes.new("ShaderNodeVertexColor"); vc.layer_name = o.data.color_attributes[0].name
                nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    temp = []

    def set_target(img):
        for m in mats:
            nt = m.node_tree
            n = nt.nodes.get("mc_bake") or nt.nodes.new("ShaderNodeTexImage")
            n.name = "mc_bake"; n.image = img
            nt.nodes.active = n

    select_only([o])
    set_target(imgs["basecolor"])
    s.render.bake.margin = 6
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=6)
    # metallic-roughness: temporarily route (0, roughness, metallic) to an emission shader
    for m in mats:
        nt = m.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        comb = nt.nodes.new("ShaderNodeCombineColor")
        comb.inputs[0].default_value = 0.0
        comb.inputs[1].default_value = bsdf.inputs["Roughness"].default_value
        comb.inputs[2].default_value = bsdf.inputs["Metallic"].default_value
        em = nt.nodes.new("ShaderNodeEmission")
        nt.links.new(comb.outputs[0], em.inputs["Color"])
        old = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        temp.append((m, comb, em, out, old))
    set_target(imgs["metalrough"])
    bpy.ops.object.bake(type="EMIT", margin=6)
    for m, comb, em, out, old in temp:
        nt = m.node_tree
        if old: nt.links.new(old, out.inputs["Surface"])
        nt.nodes.remove(comb); nt.nodes.remove(em)
    paths = {}
    for kind, img in imgs.items():
        p = os.path.join(out_dir, f"{slug}_{kind}.png")
        img.filepath_raw = p; img.file_format = "PNG"; img.save()
        paths[kind] = p
    # single baked material
    nm = bpy.data.materials.new(f"M_{slug}")
    if getattr(nm, "node_tree", None) is None: nm.use_nodes = True
    nt = nm.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t1 = nt.nodes.new("ShaderNodeTexImage"); t1.image = imgs["basecolor"]
    t2 = nt.nodes.new("ShaderNodeTexImage"); t2.image = imgs["metalrough"]
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t1.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(t2.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    # emissive bits (lanterns) keep a little glow
    emit = max((m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value
                for m in mats if "Principled BSDF" in m.node_tree.nodes), default=0)
    o.data.materials.clear(); o.data.materials.append(nm)
    if "MC_UV" in o.data.uv_layers:   # the source UVs were only needed for the transfer
        for l in [l for l in o.data.uv_layers if l.name != "MC_UV"]: o.data.uv_layers.remove(l)
    return {"maps": {k: os.path.basename(v) for k, v in paths.items()}, "resolution": res, "emission_dropped": emit > 0,
            "paths": paths}


# ---------------------------------------------------------------- previews
def bounds(objs):
    pts = []
    for o in objs:
        if o.type != "MESH": continue
        dg = bpy.context.evaluated_depsgraph_get()
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        pts += [ev.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    if not pts: return Vector((0, 0, 0)), Vector((1, 1, 1))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def setup_stage(objs, transparent=True, ground=False, world=(0.62, 0.78, 0.86)):
    s = bpy.context.scene
    lo, hi = bounds(objs)
    c = (lo + hi) / 2; size = max((hi - lo).length, 0.5)
    w = bpy.data.worlds.new("mc_world"); s.world = w
    if getattr(w, "node_tree", None) is None: w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (*world, 1); bg.inputs[1].default_value = 0.9
    sun = bpy.data.lights.new("mc_sun", "SUN"); sun.energy = 3.2; sun.angle = math.radians(8)
    so = link(bpy.data.objects.new("mc_sun", sun)); so.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
    fill = bpy.data.lights.new("mc_fill", "SUN"); fill.energy = 0.8
    fo = link(bpy.data.objects.new("mc_fill", fill)); fo.rotation_euler = (math.radians(70), 0, math.radians(-150))
    if ground:
        g = prim("plane", "mc_ground", mat("#9cc9d6"), loc=(c.x, c.y, lo.z - 0.001), scale=(size * 3, size * 3, 1))
        g["mc_stage"] = True
    rig = empty("mc_orbit", loc=c)
    cam_d = bpy.data.cameras.new("mc_cam"); cam_d.lens = 50
    cam = link(bpy.data.objects.new("mc_cam", cam_d))
    cam.parent = rig
    dist = size * 1.3
    cam.location = (0, -dist * math.cos(math.radians(24)) , dist * math.sin(math.radians(24)))
    tr = cam.constraints.new("TRACK_TO"); tr.target = rig; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
    rig.rotation_euler = (0, 0, math.radians(-35))
    s.camera = cam
    s.render.film_transparent = transparent
    s.view_settings.view_transform = "Standard"
    return rig, [so, fo, cam, rig]


def render(path, res=512, samples=24):
    s = bpy.context.scene
    _cycles(s, samples)
    s.render.resolution_x = s.render.resolution_y = res
    s.render.image_settings.file_format = "PNG"
    s.render.image_settings.color_mode = "RGBA" if s.render.film_transparent else "RGB"
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def previews(objs, out_dir, slug, frames=8, res=512, anim_frame=None):
    os.makedirs(out_dir, exist_ok=True)
    rig, helpers = setup_stage(objs)
    if anim_frame is not None: bpy.context.scene.frame_set(anim_frame)
    out = {"thumbnail": render(os.path.join(out_dir, f"{slug}_thumb.png"), res, 24), "turntable": []}
    base = rig.rotation_euler.z
    for i in range(frames):
        rig.rotation_euler.z = base + i * 2 * math.pi / frames
        out["turntable"].append(render(os.path.join(out_dir, f"{slug}_turn_{i:02d}.png"), 256, 8))
    rig.rotation_euler.z = base
    for h in helpers: bpy.data.objects.remove(h, do_unlink=True)
    return out


# ---------------------------------------------------------------- export + stats
def export_all(root, out_dir, slug, formats=("glb", "gltf", "fbx", "obj", "stl", "blend"), animations=True):
    os.makedirs(out_dir, exist_ok=True)
    objs = [root] + list(root.children_recursive)
    select_only(objs)
    files = {}
    if "glb" in formats or "gltf" in formats:
        for fmt in [f for f in ("glb", "gltf") if f in formats]:
            d = out_dir if fmt == "glb" else os.path.join(out_dir, "gltf")
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, f"{slug}.{fmt}")
            select_only(objs)
            bpy.ops.export_scene.gltf(filepath=p, export_format="GLB" if fmt == "glb" else "GLTF_SEPARATE",
                                      use_selection=True, export_apply=True, export_yup=True,
                                      export_animations=animations, export_animation_mode="ACTIONS",
                                      export_extras=True, export_image_format="AUTO")
            files[fmt] = p
    if "fbx" in formats:
        p = os.path.join(out_dir, f"{slug}.fbx"); select_only(objs)
        bpy.ops.export_scene.fbx(filepath=p, use_selection=True, add_leaf_bones=False, bake_anim=animations,
                                 path_mode="COPY", embed_textures=True, axis_forward="-Z", axis_up="Y")
        files["fbx"] = p
    if "obj" in formats:
        d = os.path.join(out_dir, "obj"); os.makedirs(d, exist_ok=True)
        p = os.path.join(d, f"{slug}.obj"); select_only(objs)
        bpy.ops.wm.obj_export(filepath=p, export_selected_objects=True, export_materials=True, path_mode="COPY",
                              forward_axis="NEGATIVE_Z", up_axis="Y")
        files["obj"] = p
    if "stl" in formats:
        p = os.path.join(out_dir, f"{slug}.stl"); select_only(objs)
        bpy.ops.wm.stl_export(filepath=p, export_selected_objects=True, forward_axis="NEGATIVE_Z", up_axis="Y")
        files["stl"] = p
    if "blend" in formats:
        p = os.path.join(out_dir, f"{slug}.blend")
        bpy.ops.wm.save_as_mainfile(filepath=p, compress=True, copy=True)
        files["blend"] = p
    return files


def stats(root):
    objs = [root] + list(root.children_recursive)
    meshes = [o for o in objs if o.type == "MESH"]
    lo, hi = bounds(meshes)
    imgs = {}
    mats = set()
    for o in meshes:
        for m in o.data.materials:
            if not m: continue
            mats.add(m.name)
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image:
                    imgs[n.image.name] = {"name": n.image.name, "size": list(n.image.size),
                                          "colorspace": n.image.colorspace_settings.name}
    arm = [o for o in objs if o.type == "ARMATURE"]
    acts = []
    for a in bpy.data.actions:
        if a.users == 0 and not a.use_fake_user: continue
        fr = a.frame_range
        acts.append({"name": a.name, "frames": [int(fr[0]), int(fr[1])],
                     "seconds": round((fr[1] - fr[0]) / bpy.context.scene.render.fps, 3),
                     "loop": bool(a["mc_loop"]) if "mc_loop" in a else not any(k in a.name.lower() for k in ("jump", "attack", "interact", "slash", "death"))})
    sockets = [{"name": o.name, "location": [round(v, 4) for v in o.matrix_world.translation]}
               for o in objs if o.type == "EMPTY" and o.name.startswith("socket_")]
    return {
        "triangles": tri_count(meshes),
        "vertices": sum(len(o.data.vertices) for o in meshes),
        "meshes": len(meshes),
        "materials": sorted(mats),
        "textures": list(imgs.values()),
        "dimensions_m": [round(v, 3) for v in (hi - lo)],
        "bounds_min": [round(v, 3) for v in lo], "bounds_max": [round(v, 3) for v in hi],
        "rig": {"bones": len(arm[0].data.bones), "bone_names": [b.name for b in arm[0].data.bones],
                "convention": arm[0].get("mc_convention", "")} if arm else None,
        "animations": acts,
        "sockets": sockets,
    }
