"""Modelling kit shared by MeshCraft templates (Blender 5.x, background mode).

Conventions (match glTF/Three.js after export with +Y up):
  * metres; Blender Z-up, front of an asset faces -Y (becomes +Z in Three.js);
  * every material is a palette *role* (e.g. "wood", "band") named
    "<prefix>_<Role>", with the role and palette colour stored as custom props;
  * colours also baked to a CORNER colour attribute "Color" (glTF COLOR_0, linear)
    so engines that shade with vertex colours (TIDEBREAKERS' toon material) match.
"""
import math, random
import bpy, bmesh
from mathutils import Vector, Matrix
from .palette import hex_to_linear

# ---------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"; s.unit_settings.scale_length = 1.0
    s.render.fps = 30
    return s


def link(obj, parent=None):
    bpy.context.scene.collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


def empty(name, loc=(0, 0, 0), parent=None, kind="PLAIN_AXES", size=0.2):
    e = bpy.data.objects.new(name, None); e.empty_display_type = kind; e.empty_display_size = size
    e.location = loc
    return link(e, parent)


# ---------------------------------------------------------------- materials
class Materials:
    def __init__(self, palette, roles: dict, prefix="GC"):
        """roles: {"wood": "Honey Timber", ...} -> palette names or hex."""
        self.palette, self.prefix, self.mats, self.hex = palette, prefix, {}, {}
        for role, ref in roles.items(): self.add(role, ref)

    def add(self, role, ref, rough=0.75, metal=0.0, emit=0.0):
        hx = self.palette.get(ref)
        name = f"{self.prefix}_{role[0].upper()}{role[1:]}"
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        lin = hex_to_linear(hx)
        bsdf.inputs["Base Color"].default_value = (*lin, 1)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if emit:
            bsdf.inputs["Emission Color"].default_value = (*lin, 1)
            bsdf.inputs["Emission Strength"].default_value = emit
        m.diffuse_color = (*lin, 1)
        m["gitcraft_role"] = role; m["gitcraft_color"] = hx; m["gitcraft_palette_ref"] = ref
        self.mats[role], self.hex[role] = m, hx
        return m

    def __getitem__(self, role): return self.mats[role]


def assign(obj, mat):
    obj.data.materials.clear(); obj.data.materials.append(mat)
    return obj


# ---------------------------------------------------------------- geometry
def _canonical(bm):
    """Same geometry, fixed element order. Some bmesh primitives (create_uvsphere) emit faces in a
    different order / starting corner from run to run, which made exports differ between identical
    builds. Faces are re-created in sorted order, each starting at its lowest vertex index."""
    bm.verts.index_update()
    faces = []
    for f in bm.faces:
        idx = [v.index for v in f.verts]; k = idx.index(min(idx))
        faces.append((tuple(idx[k:] + idx[:k]), f.material_index, f.smooth))
    loose = sorted(tuple(sorted(v.index for v in e.verts)) for e in bm.edges if not e.link_faces)
    out = bmesh.new()
    vs = [out.verts.new(v.co) for v in bm.verts]
    for idx, mi, sm in sorted(faces):
        f = out.faces.new([vs[i] for i in idx]); f.material_index = mi; f.smooth = sm
    for a, b in loose: out.edges.new((vs[a], vs[b]))
    bm.free()
    return out


def _mesh_obj(name, bm, mat=None, parent=None):
    bm = _canonical(bm)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = link(bpy.data.objects.new(name, me), parent)
    if mat is not None: assign(o, mat)
    return o


def box(name, size, loc=(0, 0, 0), mat=None, bevel=0.0, segs=2, parent=None, taper=0.0):
    """Axis-aligned box centred on loc. taper > 0 shrinks the top face (handcrafted wonk)."""
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
        if taper and v.co.z > 0: v.co.x *= (1 - taper); v.co.y *= (1 - taper)
        v.co += Vector(loc)
    o = _mesh_obj(name, bm, mat, parent)
    if bevel: apply_bevel(o, bevel, segs)
    return o


def cylinder(name, r, depth, loc=(0, 0, 0), axis="Z", verts=16, mat=None, bevel=0.0, segs=2, parent=None, r2=None, arc=None):
    """Cylinder/cone along an axis; arc=(start, end) radians gives a partial (vault) shape, capped."""
    bm = bmesh.new()
    if arc is None:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    else:
        # partial vault built directly in its plane: angle 0 = +second axis, pi/2 = up (+Z, or +Y for axis Z)
        a0, a1 = arc; ring = []
        def P(a, w):
            c, sn = math.cos(a) * r, math.sin(a) * r
            return {"X": (w, c, sn), "Y": (c, w, sn), "Z": (c, sn, w)}[axis]
        for w in (-depth / 2, depth / 2):
            ring.append([bm.verts.new(P(a0 + (a1 - a0) * i / (verts - 1), w)) for i in range(verts)])
        for i in range(verts - 1):
            bm.faces.new((ring[0][i], ring[0][i + 1], ring[1][i + 1], ring[1][i]))
        bm.faces.new(ring[0][::-1]); bm.faces.new(ring[1])
        bm.faces.new((ring[0][-1], ring[0][0], ring[1][0], ring[1][-1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
        o = _mesh_obj(name, bm, mat, parent)
        if bevel: apply_bevel(o, bevel, segs)
        return o
    rot = {"Z": Matrix(), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(loc) @ rot, verts=bm.verts)
    o = _mesh_obj(name, bm, mat, parent)
    if bevel: apply_bevel(o, bevel, segs)
    return o


def sphere(name, r, loc=(0, 0, 0), mat=None, segs=12, rings=8, scale=(1, 1, 1), parent=None):
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co.x *= scale[0]; v.co.y *= scale[1]; v.co.z *= scale[2]; v.co += Vector(loc)
    return _mesh_obj(name, bm, mat, parent)


def ico(name, r, loc=(0, 0, 0), mat=None, sub=1, scale=(1, 1, 1), parent=None, seed=0, wobble=0.0):
    bm = bmesh.new(); bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    rng = random.Random(seed)
    for v in bm.verts:
        f = 1 + (rng.uniform(-wobble, wobble) if wobble else 0)
        v.co.x *= scale[0] * f; v.co.y *= scale[1] * f; v.co.z *= scale[2] * f; v.co += Vector(loc)
    return _mesh_obj(name, bm, mat, parent)


def torus(name, R, r, loc=(0, 0, 0), axis="Z", mat=None, major=16, minor=6, parent=None):
    bm = bmesh.new(); ring = []
    for i in range(major):
        a = 2 * math.pi * i / major
        ring.append([bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b)))
                     for b in (2 * math.pi * j / minor for j in range(minor))])
    for i in range(major):
        for j in range(minor):
            bm.faces.new((ring[i][j], ring[(i + 1) % major][j], ring[(i + 1) % major][(j + 1) % minor], ring[i][(j + 1) % minor]))
    rot = {"Z": Matrix(), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(loc) @ rot, verts=bm.verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _mesh_obj(name, bm, mat, parent)


def prism(name, outline, depth, loc=(0, 0, 0), axis="Y", mat=None, parent=None, bevel=0.0):
    """Extrude a 2D outline [(u, v), ...] by depth. axis = extrusion axis (Y: outline in XZ plane)."""
    bm = bmesh.new()
    def P(u, v, w):
        return {"Y": (u, w, v), "Z": (u, v, w), "X": (w, u, v)}[axis]
    a = [bm.verts.new(P(u, v, -depth / 2)) for u, v in outline]
    b = [bm.verts.new(P(u, v, depth / 2)) for u, v in outline]
    n = len(outline)
    bm.faces.new(a[::-1]); bm.faces.new(b)
    for i in range(n): bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    o = _mesh_obj(name, bm, mat, parent)
    if bevel: apply_bevel(o, bevel, 1)
    return o


def apply_bevel(o, width, segs=2, angle=40):
    mod = o.modifiers.new("bevel", "BEVEL"); mod.width = width; mod.segments = segs
    mod.limit_method = "ANGLE"; mod.angle_limit = math.radians(angle)
    apply_modifiers(o)


def apply_modifiers(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    o.modifiers.clear(); old = o.data; o.data = me
    bpy.data.meshes.remove(old)


def deform(o, fn):
    """fn(Vector) -> Vector applied to every vertex (object space)."""
    for v in o.data.vertices: v.co = fn(v.co.copy())
    o.data.update()


def join(objs, name, parent=None):
    objs = [o for o in objs if o is not None]
    ctx = bpy.context
    for o in ctx.scene.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    ctx.view_layer.objects.active = objs[0]
    with ctx.temp_override(active_object=objs[0], selected_editable_objects=objs, selected_objects=objs):
        bpy.ops.object.join()
    o = objs[0]; o.name = name; o.data.name = name
    if parent is not None:
        mw = o.matrix_world.copy(); o.parent = parent; o.matrix_world = mw
    return o


def set_origin(o, world_point):
    """Move the object origin to world_point without moving the geometry."""
    wp = Vector(world_point)
    local = o.matrix_world.inverted() @ wp
    o.data.transform(Matrix.Translation(-local))
    o.matrix_world = o.matrix_world @ Matrix.Translation(local)


def shade(o, smooth_angle=None):
    """Flat by default (low-poly look); smooth_angle (deg) smooths soft forms."""
    for p in o.data.polygons: p.use_smooth = smooth_angle is not None
    if smooth_angle is not None:
        try:
            o.data.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except Exception:
            pass



# ---------------------------------------------------------------- structural pieces (timber, steel, snow)
def beam(name, a, b, t, mat=None, parent=None, depth=None):
    """A square (t x t, or t x depth) bar from point a to point b: braces, rafters, guy wires, struts."""
    a, b = Vector(a), Vector(b)
    d = b - a
    o = box(name, (t, depth or t, d.length), (0, 0, 0), mat, parent=parent)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    o.location = (a + b) / 2
    return o


def mound(name, w, h, d, loc=(0, 0, 0), mat=None, segs=10, rings=4, parent=None):
    """The top half of a squashed sphere, w (x) by d (y) at its base and h high, base at loc: a snow
    drift, a spoil or tailings heap, a hay pile, a sand bank. Closed underneath."""
    bm = bmesh.new()
    top = bm.verts.new((0, 0, h))
    rows = []
    for j in range(rings, 0, -1):
        a = (math.pi / 2) * j / (rings + 1)
        rows.append([bm.verts.new((math.cos(t) * math.cos(a) * w / 2, math.sin(t) * math.cos(a) * d / 2, math.sin(a) * h))
                     for t in (2 * math.pi * i / segs for i in range(segs))])
    rows.append([bm.verts.new((math.cos(t) * w / 2, math.sin(t) * d / 2, 0)) for t in (2 * math.pi * i / segs for i in range(segs))])
    for i in range(segs):
        bm.faces.new((top, rows[0][i], rows[0][(i + 1) % segs]))
    for r0, r1 in zip(rows, rows[1:]):
        for i in range(segs):
            bm.faces.new((r0[i], r1[i], r1[(i + 1) % segs], r0[(i + 1) % segs]))
    bm.faces.new(rows[-1][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.translate(bm, vec=Vector(loc), verts=bm.verts)
    return _mesh_obj(name, bm, mat, parent)


def log_wall(name, length, height, loc=(0, 0, 0), axis="X", r=0.17, mats=(None, None), grain=None, openings=(), half=False, verts=7, parent=None):
    """A log wall: round logs of radius r stacked to `height` along `axis` ("X" or "Y"), centred on loc
    with its foot at loc's z. mats alternates two log materials course by course; grain, if given, caps
    each log with an end-grain disc. openings are (u0, u1, z0, z1) holes in wall coordinates (u along the
    wall from its centre, z up from its foot) for doors and windows: logs are cut short either side.
    half raises every course by r (the cross wall of a notched corner). Returns the list of objects."""
    n = max(2, round(height / (r * 2)))
    out = []
    lx, ly, lz = loc
    for i in range(n):
        z = lz + r + i * r * 2 + (r if half else 0)
        zz = z - lz
        spans = [(-length / 2, length / 2)]
        for u0, u1, z0, z1 in openings:
            if z0 - r < zz < z1 + r:
                nxt = []
                for a, b in spans:
                    if u1 <= a or u0 >= b:
                        nxt.append((a, b))
                    else:
                        if u0 > a: nxt.append((a, u0))
                        if u1 < b: nxt.append((u1, b))
                spans = nxt
        m = mats[i % 2] if mats[i % 2] is not None else mats[0]
        for a, b in spans:
            if b - a < 0.05:
                continue
            c = (a + b) / 2
            p = (lx + c, ly, z) if axis == "X" else (lx, ly + c, z)
            out.append(cylinder(f"{name}_{i}", r, b - a, p, axis=axis, verts=verts, mat=m, parent=parent))
        if grain is not None:
            for e in (-1, 1):
                u = e * (length / 2 + 0.02)
                p = (lx + u, ly, z) if axis == "X" else (lx, ly + u, z)
                out.append(cylinder(f"{name}_end", r * 0.9, 0.04, p, axis=axis, verts=verts, mat=grain, parent=parent))
    return out

# ---------------------------------------------------------------- colour bake + atlas
def bake_vertex_colors(o, mats: Materials, jitter=0.04, seed=1, per_role_jitter=None):
    """Write each face's material colour into the 'Color' corner attribute (linear float).
    jitter: +/- value variation per face for a hand-painted feel (deterministic)."""
    me = o.data
    if "Color" in me.color_attributes: me.color_attributes.remove(me.color_attributes["Color"])
    attr = me.color_attributes.new("Color", "FLOAT_COLOR", "CORNER")
    rng = random.Random(seed)
    for p in me.polygons:
        m = me.materials[p.material_index] if me.materials else None
        role = m.get("gitcraft_role", "") if m else ""
        base = hex_to_linear(m["gitcraft_color"]) if m and "gitcraft_color" in m else (0.8, 0.8, 0.8)
        j = (per_role_jitter or {}).get(role, jitter)
        k = 1 + rng.uniform(-j, j)
        col = (min(1, base[0] * k), min(1, base[1] * k), min(1, base[2] * k), 1.0)
        for li in p.loop_indices: attr.data[li].color = col
    me.color_attributes.active_color = attr
    try: me.color_attributes.render_color_index = me.color_attributes.find("Color")
    except Exception: pass


def palette_atlas(mats: Materials, name="GC_Atlas", cell=16, cols=4):
    """A small hand-painted swatch atlas: one cell per role with a soft vertical
    gradient (lighter top, cooler bottom) so flat colours read as painted."""
    roles = list(mats.mats)
    rows = math.ceil(len(roles) / cols)
    W, H = cols * cell, rows * cell
    img = bpy.data.images.new(name, W, H, alpha=False)
    px = [0.0] * (W * H * 4)
    cells = {}
    for i, role in enumerate(roles):
        cx, cy = i % cols, rows - 1 - i // cols
        r, g, b = hex_to_linear(mats.hex[role])
        for y in range(cell):
            t = y / (cell - 1)
            k = 0.86 + 0.24 * t  # bottom darker, top lighter
            cool = (1 - t) * 0.04
            for x in range(cell):
                o = ((cy * cell + y) * W + cx * cell + x) * 4
                px[o:o + 4] = [min(1, r * k), min(1, g * k), min(1, b * k + cool), 1.0]
        cells[role] = ((cx + 0.5) / cols, (cy + 0.5) / rows, 0.35 / cols, 0.35 / rows)
    img.pixels = px
    img.colorspace_settings.name = "sRGB"
    img.pack()
    return img, cells


def atlas_material(img, name="GC_Atlas"):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.interpolation = "Closest"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.8
    m["gitcraft_role"] = "atlas"
    return m


def apply_atlas(o, cells, atlas_mat):
    """Point every face's UVs into its role's atlas cell, then use the single atlas material.
    The vertical position inside the cell follows face height for the painted gradient."""
    me = o.data
    uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    zs = [v.co.z for v in me.vertices] or [0]
    z0, z1 = min(zs), max(zs) or 1
    for p in me.polygons:
        m = me.materials[p.material_index] if me.materials else None
        role = m.get("gitcraft_role") if m else None
        cu, cv, hu, hv = cells.get(role, (0.5, 0.5, 0, 0))
        for li in p.loop_indices:
            z = me.vertices[me.loops[li].vertex_index].co.z
            t = (z - z0) / ((z1 - z0) or 1)
            uv.data[li].uv = (cu, cv - hv + 2 * hv * t)
    me.materials.clear(); me.materials.append(atlas_mat)


# ---------------------------------------------------------------- animation
def _fcurves(action, obj=None):
    try:
        return list(action.fcurves)
    except Exception:
        pass
    curves = []
    for layer in getattr(action, "layers", []):
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                curves += list(cb.fcurves)
    return curves


def keyframes(obj, data_path, keys, name, index=-1, interp="BEZIER", easing="AUTO", stash=True):
    """keys: [(frame, value or tuple)]. Builds a named action and stashes it on an NLA
    track so glTF export writes it as its own animation clip."""
    if obj.animation_data is None: obj.animation_data_create()
    rest = obj.path_resolve(data_path)
    rest = tuple(rest) if hasattr(rest, "__len__") else rest
    act = bpy.data.actions.new(name)
    obj.animation_data.action = act
    for f, val in keys:
        if isinstance(val, (tuple, list)):
            target = getattr(obj, data_path) if "." not in data_path and not data_path.startswith("pose") else None
            for i, comp in enumerate(val):
                if comp is None: continue
                obj.path_resolve(data_path)[i] = comp
                obj.keyframe_insert(data_path, index=i, frame=f)
        else:
            if index >= 0:
                obj.path_resolve(data_path)[index] = val
            else:
                exec_path = data_path.rsplit(".", 1)
                setattr(obj.path_resolve(exec_path[0]) if len(exec_path) > 1 else obj, exec_path[-1], val)
            obj.keyframe_insert(data_path, index=index, frame=f)
    for fc in _fcurves(act, obj):
        for kp in fc.keyframe_points:
            kp.interpolation = interp; kp.easing = easing
    act.use_fake_user = True
    if stash:
        tr = obj.animation_data.nla_tracks.new(); tr.name = name
        st = tr.strips.new(name, int(keys[0][0]), act); st.name = name
        tr.mute = True
        obj.animation_data.action = None
    # restore the value from before keyframing, so the saved/exported rest pose is unchanged
    if isinstance(rest, tuple):
        target = obj.path_resolve(data_path)
        for i, comp in enumerate(rest): target[i] = comp
    else:
        parts = data_path.rsplit(".", 1)
        setattr(obj.path_resolve(parts[0]) if len(parts) > 1 else obj, parts[-1], rest)
    return act


def pose_keyframes(arm, name, frames, stash=True):
    """frames: {frame: {bone: {"rot": (x, y, z) radians euler, "loc": (x, y, z)}}}"""
    if arm.animation_data is None: arm.animation_data_create()
    act = bpy.data.actions.new(name); arm.animation_data.action = act
    for pb in arm.pose.bones: pb.rotation_mode = "XYZ"
    for f in sorted(frames):
        for bone, ch in frames[f].items():
            pb = arm.pose.bones[bone]
            if "rot" in ch:
                pb.rotation_euler = ch["rot"]; pb.keyframe_insert("rotation_euler", frame=f)
            if "loc" in ch:
                pb.location = ch["loc"]; pb.keyframe_insert("location", frame=f)
    act.use_fake_user = True
    if stash:
        tr = arm.animation_data.nla_tracks.new(); tr.name = name
        st = tr.strips.new(name, int(min(frames)), act); st.name = name
        tr.mute = True
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_euler = (0, 0, 0); pb.location = (0, 0, 0)
    return act


# ---------------------------------------------------------------- rigging
def armature(name, bones, parent=None, loc=(0, 0, 0)):
    """bones: [(name, head, tail, parent_name or None)] in armature space."""
    data = bpy.data.armatures.new(name)
    arm = link(bpy.data.objects.new(name, data), parent)
    arm.location = loc
    bpy.context.view_layer.objects.active = arm
    with bpy.context.temp_override(active_object=arm, object=arm):
        bpy.ops.object.mode_set(mode="EDIT")
        eb = data.edit_bones
        for bn, h, t, par in bones:
            b = eb.new(bn); b.head = h; b.tail = t
            if par: b.parent = eb[par]
        bpy.ops.object.mode_set(mode="OBJECT")
    return arm


def skin_rigid(mesh_obj, arm, part_bones):
    """Bind a joined mesh to an armature: part_bones maps material-independent
    vertex-group names (created by `tag`) to bones. Each vertex gets weight 1."""
    for vg_name, bone in part_bones.items():
        vg = mesh_obj.vertex_groups.get(vg_name)
        if vg is not None: vg.name = bone
    # glTF ignores a skinned mesh's parent transforms (validator: NODE_SKINNED_MESH_NON_ROOT),
    # so the mesh stays at the scene root; only the modifier binds it to the armature.
    mw = mesh_obj.matrix_world.copy()
    mesh_obj.parent = None; mesh_obj.matrix_world = mw
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE"); mod.object = arm


def tag(o, group):
    """Put every vertex of o in a vertex group (survives join) for rigid skinning."""
    vg = o.vertex_groups.new(name=group)
    vg.add([v.index for v in o.data.vertices], 1.0, "REPLACE")
    return o


def skin_gradient(mesh_obj, arm, chain, axis=0, start=0.0, length=1.0):
    """Smooth weights along a bone chain by position on one axis (flags, ropes)."""
    n = len(chain)
    groups = [mesh_obj.vertex_groups.get(b) or mesh_obj.vertex_groups.new(name=b) for b in chain]
    for v in mesh_obj.data.vertices:
        t = max(0.0, min(0.9999, (v.co[axis] - start) / length)) * n
        i = int(t); f = t - i
        groups[i].add([v.index], 1 - f, "REPLACE")
        if i + 1 < n: groups[i + 1].add([v.index], f, "REPLACE")
    mw = mesh_obj.matrix_world.copy(); mesh_obj.parent = None; mesh_obj.matrix_world = mw  # skinned meshes at the root (glTF)
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE"); mod.object = arm


# ---------------------------------------------------------------- references
def add_reference(path, name, loc=(0, 2, 1), size=2.0):
    """Attach a 2D reference image as an image empty (assisted-modelling workflows)."""
    img = bpy.data.images.load(path, check_existing=True)
    e = bpy.data.objects.new(name, None); e.empty_display_type = "IMAGE"; e.data = img
    e.empty_display_size = size; e.location = loc; e.rotation_euler = (math.pi / 2, 0, 0)
    e.hide_render = True; e["gitcraft_reference"] = path
    return link(e)
