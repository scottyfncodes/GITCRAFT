"""Texture baking for the PBR export profiles (web-pbr). Needs bpy.

Bakes every mesh of the open scene into one shared UV layout and three maps:

  basecolor  sRGB  what the material shows: the painted vertex colours (`Color`) for palette
                   role materials, or the material's own texture / colour otherwise
  orm        linear glTF metallicRoughness packing: G = roughness, B = metallic
  emissive   sRGB  only when a material emits (lantern glass, flames)

Each map is an EMIT bake (Cycles, 1 sample), so the result is the exact surface colour with no
lighting baked in. The scene is then given one material that uses the maps, which the glTF
exporter writes as a standard PBR material. Runs on a scene opened only for export: nothing is
saved back to the .blend. Skinned meshes are baked in their rest pose and keep their weights.
"""
import os
import bpy


def _principled(m):
    return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m and m.use_nodes else None


def _output(m):
    nt = m.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
    return out or nt.nodes.new("ShaderNodeOutputMaterial")


def _source(nt, socket):
    """(linked output socket or None, default value) of an input socket."""
    return (socket.links[0].from_socket if socket.is_linked else None), socket.default_value


def _feed(nt, dst, src):
    s, val = src
    if s is not None: nt.links.new(s, dst)
    else:
        try: dst.default_value = val
        except TypeError: dst.default_value = (val, val, val, 1.0)


def _uv_layout(meshes, margin):
    """One shared, non-overlapping UV map ("BakeUV") across all meshes, made the active (bake) map;
    the meshes' own maps stay the render map so their textures are still sampled correctly."""
    for o in bpy.context.scene.objects: o.select_set(False)
    for o in meshes:
        uv = o.data.uv_layers.get("BakeUV") or o.data.uv_layers.new(name="BakeUV")
        o.data.uv_layers.active = uv; o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def _bake(meshes, image, wire):
    """Bake one EMIT pass into `image`; wire(material, nodetree, emission_node) feeds the emission colour."""
    mats = {m for o in meshes for m in o.data.materials if m}
    saved = []
    for m in mats:
        nt = m.node_tree; out = _output(m)
        prev = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].is_linked else None
        em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Strength"].default_value = 1.0
        wire(m, nt, em); nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        tgt = nt.nodes.new("ShaderNodeTexImage"); tgt.image = image
        for n in nt.nodes: n.select = False
        tgt.select = True; nt.nodes.active = tgt
        saved.append((m, out, prev, [em, tgt]))
    for o in bpy.context.scene.objects: o.select_set(o in meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.bake(type="EMIT", margin=4, use_clear=True, target="IMAGE_TEXTURES")
    for m, out, prev, added in saved:
        nt = m.node_tree
        for n in added: nt.nodes.remove(n)
        if prev is not None: nt.links.new(prev, out.inputs["Surface"])


def _wire_base(m, nt, em):
    p = _principled(m)
    if m.get("gitcraft_role"):            # palette materials: the painted per-face colours
        ca = nt.nodes.new("ShaderNodeVertexColor"); ca.layer_name = "Color"; ca.label = "gc_bake_tmp"
        nt.links.new(ca.outputs["Color"], em.inputs["Color"])
        tex = next((l.from_socket for l in (p.inputs["Base Color"].links if p else [])), None)
        if tex is not None and getattr(tex.node, "type", "") == "TEX_IMAGE":   # textured (Blockbench) materials keep texels
            nt.links.new(tex, em.inputs["Color"])
    elif p is not None: _feed(nt, em.inputs["Color"], _source(nt, p.inputs["Base Color"]))
    else: em.inputs["Color"].default_value = (*m.diffuse_color[:3], 1)


def _wire_orm(m, nt, em):
    p = _principled(m); cc = nt.nodes.new("ShaderNodeCombineColor"); cc.label = "gc_bake_tmp"
    cc.inputs[0].default_value = 1.0       # R (occlusion) = 1
    if p is not None:
        _feed(nt, cc.inputs[1], _source(nt, p.inputs["Roughness"]))
        _feed(nt, cc.inputs[2], _source(nt, p.inputs["Metallic"]))
    else:
        cc.inputs[1].default_value = m.roughness; cc.inputs[2].default_value = m.metallic
    nt.links.new(cc.outputs["Color"], em.inputs["Color"])


def _emits(m):
    p = _principled(m)
    return p is not None and p.inputs["Emission Strength"].default_value > 0 and any(p.inputs["Emission Color"].default_value[:3])


def _wire_emit(m, nt, em):
    p = _principled(m)
    if p is not None and _emits(m):
        _feed(nt, em.inputs["Color"], _source(nt, p.inputs["Emission Color"]))
        em.inputs["Strength"].default_value = p.inputs["Emission Strength"].default_value
    else:
        em.inputs["Color"].default_value = (0, 0, 0, 1)


def _image(name, res, non_color):
    img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def bake_pbr(meshes, out_dir, base_name, resolution=1024, fallbacks=(512,), material_name="GC_Baked"):
    """Bake and swap in one PBR material. Returns {maps, resolution, attempts}. Raises if every size fails."""
    s = bpy.context.scene
    s.render.engine = "CYCLES"; s.cycles.device = "CPU"; s.cycles.samples = 1
    try: s.cycles.use_denoising = False
    except AttributeError: pass
    arms = [o for o in s.objects if o.type == "ARMATURE"]
    for a in arms: a.data.pose_position = "REST"
    for o in meshes:
        if o.data.shape_keys: o.active_shape_key_index = 0; o.show_only_shape_key = True
    attempts = []
    for res in [resolution, *fallbacks]:
        try:
            _uv_layout(meshes, margin=2.0 / res * 4)
            maps = {}
            for kind, wire, nc in (("basecolor", _wire_base, False), ("orm", _wire_orm, True), ("emissive", _wire_emit, False)):
                if kind == "emissive" and not any(_emits(m) for o in meshes for m in o.data.materials if m): continue
                img = _image(f"{base_name}.{kind}", res, nc)
                _bake(meshes, img, wire)
                path = os.path.join(out_dir, f"{base_name}.{kind}.png")
                img.filepath_raw = path; img.file_format = "PNG"; img.save()
                maps[kind] = (img, path)
            attempts.append({"resolution": res, "ok": True})
            break
        except Exception as e:      # out of memory / bake failure: retry smaller
            attempts.append({"resolution": res, "ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
            if bpy.context.object and bpy.context.object.mode != "OBJECT": bpy.ops.object.mode_set(mode="OBJECT")
    else:
        raise RuntimeError(f"texture bake failed at every size: {attempts}")
    for a in arms: a.data.pose_position = "POSE"
    for o in meshes:
        if o.data.shape_keys: o.show_only_shape_key = False

    m = bpy.data.materials.new(material_name); m.use_nodes = True; nt = m.node_tree
    p = _principled(m); uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "BakeUV"
    def tex(kind, nc):
        n = nt.nodes.new("ShaderNodeTexImage"); n.image = maps[kind][0]; n.interpolation = "Linear"
        nt.links.new(uvn.outputs["UV"], n.inputs["Vector"]); return n
    nt.links.new(tex("basecolor", False).outputs["Color"], p.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(tex("orm", True).outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], p.inputs["Roughness"]); nt.links.new(sep.outputs["Blue"], p.inputs["Metallic"])
    if "emissive" in maps:
        nt.links.new(tex("emissive", False).outputs["Color"], p.inputs["Emission Color"]); p.inputs["Emission Strength"].default_value = 1.0
    for o in meshes:
        o.data.materials.clear(); o.data.materials.append(m)
        for poly in o.data.polygons: poly.material_index = 0
        for uv in [u for u in o.data.uv_layers if u.name != "BakeUV"]: o.data.uv_layers.remove(uv)
        bake_uv = o.data.uv_layers["BakeUV"]; o.data.uv_layers.active = bake_uv; bake_uv.active_render = True
        if "Color" in o.data.color_attributes: o.data.color_attributes.remove(o.data.color_attributes["Color"])
    return {"maps": {k: v[1] for k, v in maps.items()}, "resolution": attempts[-1]["resolution"], "attempts": attempts}
