"""Blockbench .bbmodel → a MeshCraft .blend (needs bpy).

The result has the same layout as a template build (out_dir/source/<asset_id>.blend with the
brief stored in the scene), so render_preview, validate_asset, export_asset and engine_check
work on it unchanged, with every export profile:

  * cubes and Blockbench "mesh" elements become meshes; element rotation is applied around
    its origin; 16 Blockbench px = 1 m;
  * axes follow Blockbench's own glTF export (glTF = Blockbench coordinates), so a model's
    south (+Z) face is the front in glTF/three.js, -Y in Blender, MeshCraft's convention;
  * embedded PNG textures are kept (nearest-neighbour) with per-face UVs;
  * each face's texel colour is also written to the `Color` attribute (linear), so the
    vertex-colour profiles (three-web-toon) render the model the way the game renders its
    own procedural geometry;
  * projects written by blockbench.build carry palette roles, which become MeshCraft role
    materials; other projects get one material per texture.
Groups/bones and Blockbench animations are not converted (reported in the result).
"""
import base64, json, math, os, time
import bpy
from mathutils import Matrix, Vector
from . import kit
from .palette import Palette, srgb_to_linear

U = 1 / 16.0
FACE_CORNERS = {  # Blockbench face → corners (TL, TR, BR, BL as seen from outside), matching uv [u1,v1,u2,v2]
    "north": lambda x0, y0, z0, x1, y1, z1: [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)],
    "south": lambda x0, y0, z0, x1, y1, z1: [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)],
    "east":  lambda x0, y0, z0, x1, y1, z1: [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)],
    "west":  lambda x0, y0, z0, x1, y1, z1: [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)],
    "up":    lambda x0, y0, z0, x1, y1, z1: [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
    "down":  lambda x0, y0, z0, x1, y1, z1: [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
}


def _to_blender(p):            # Blockbench px (Y up, +Z south) → Blender metres (Z up, -Y front)
    return Vector((p[0] * U, -p[2] * U, p[1] * U))


def _rotation(el):
    r = el.get("rotation") or [0, 0, 0]
    if isinstance(r, (int, float)): r = [0, 0, r]
    return (Matrix.Rotation(math.radians(r[2]), 4, "Z") @ Matrix.Rotation(math.radians(r[1]), 4, "Y")
            @ Matrix.Rotation(math.radians(r[0]), 4, "X"))


class _Tex:
    def __init__(self, i, t, res, tmp):
        self.w = t.get("uv_width", t.get("width", res["width"])) or 16
        self.h = t.get("uv_height", t.get("height", res["height"])) or 16
        self.name = t.get("name", f"texture_{i}"); self.img = None; self.px = None
        src = t.get("source", "")
        if src.startswith("data:image/png;base64,"):
            p = os.path.join(tmp, f"{i}_{os.path.basename(self.name)}")
            if not p.lower().endswith(".png"): p += ".png"
            with open(p, "wb") as fh: fh.write(base64.b64decode(src.split(",", 1)[1]))
            self.img = bpy.data.images.load(p); self.img.pack(); self.img.filepath = ""
            self.iw, self.ih = self.img.size; self.px = list(self.img.pixels)  # sRGB-encoded bytes as floats, bottom row first

    def texel(self, u, v):
        """Linear RGB at Blockbench uv (px, origin top-left)."""
        if not self.px: return (0.8, 0.8, 0.8)
        x = min(self.iw - 1, max(0, int(u / self.w * self.iw))); y = min(self.ih - 1, max(0, int(v / self.h * self.ih)))
        o = ((self.ih - 1 - y) * self.iw + x) * 4
        return tuple(srgb_to_linear(c) for c in self.px[o:o + 3])

    def average_hex(self):
        if not self.px: return "#CCCCCC"
        n = len(self.px) // 4; vis = [i for i in range(n) if self.px[i * 4 + 3] > 0.5] or range(n)
        return "#" + "".join("%02X" % round(255 * sum(self.px[i * 4 + c] for i in vis) / len(vis)) for c in range(3))


def _cube_faces(el):
    f, t = list(el["from"]), list(el["to"])
    inf = el.get("inflate", 0) or 0
    f = [a - inf for a in f]; t = [b + inf for b in t]
    out = []
    for fname, corners in FACE_CORNERS.items():
        fd = (el.get("faces") or {}).get(fname)
        if fd is None or fd.get("enabled") is False or fd.get("texture") is None: continue
        u1, v1, u2, v2 = fd.get("uv", [0, 0, 16, 16])
        quv = [(u1, v1), (u2, v1), (u2, v2), (u1, v2)]
        rot = int(fd.get("rotation", 0) or 0) // 90 % 4
        if rot: quv = quv[-rot:] + quv[:-rot]
        out.append((corners(*f, *t), quv, fd.get("texture")))
    return out


def _mesh_faces(el):
    verts = el.get("vertices", {}); out = []
    for fd in (el.get("faces") or {}).values():
        keys = fd.get("vertices", [])
        if len(keys) < 3 or fd.get("texture") is None: continue
        uv = fd.get("uv", {})
        out.append(([tuple(verts[k]) for k in keys], [tuple(uv.get(k, (0, 0))) for k in keys], fd.get("texture")))
    return out


def import_bbmodel(path, asset_id, out_dir, material_prefix="BB", palette=None, roles=None):
    t0 = time.time()
    with open(path) as fh: d = json.load(fh)
    kit.reset()
    res = d.get("resolution", {"width": 16, "height": 16})
    tmp = os.path.join(out_dir, "source", "_bbmodel_textures"); os.makedirs(tmp, exist_ok=True)
    texs = [_Tex(i, t, res, tmp) for i, t in enumerate(d.get("textures", []))]
    gc = d.get("gitcraft") or {}
    pal = Palette.from_file(palette) if palette else Palette({})

    # materials: palette roles when the project carries them, else one per texture
    role_hex = dict(gc.get("roles") or {})
    for r, ref in (roles or {}).items(): role_hex[r] = pal.get(ref)
    mats = kit.Materials(Palette({}), {}, prefix=material_prefix)
    for r, hx in sorted(role_hex.items()): mats.add(r, hx, rough=0.8)
    tex_mats = []
    for i, tx in enumerate(texs):
        m = mats.add(f"tex{i}", tx.average_hex(), rough=0.8)
        if tx.img:
            nt = m.node_tree; n = nt.nodes.new("ShaderNodeTexImage"); n.image = tx.img; n.interpolation = "Closest"
            nt.links.new(n.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
        tex_mats.append(m)

    root = kit.empty(asset_id)
    objs, skipped = [], []
    for el in d.get("elements", []):
        kind = el.get("type", "cube")
        if el.get("visibility") is False or el.get("export") is False: continue
        if kind == "cube" and "from" in el: faces = _cube_faces(el)
        elif kind == "mesh": faces = _mesh_faces(el)
        else: skipped.append(f"{kind}:{el.get('name')}"); continue
        if not faces: continue
        org = Vector(el.get("origin", [0, 0, 0])); R = _rotation(el)
        off = org if kind == "cube" else Vector((0, 0, 0))   # mesh vertices are already relative to the origin
        verts, polys, uvs, cols, mids = [], [], [], [], []
        role = el.get("gitcraft_role")
        for corners, quv, ti in faces:
            ti = ti if isinstance(ti, int) and 0 <= ti < len(texs) else 0
            tx = texs[ti] if texs else None
            base = len(verts)
            for c in corners:
                p = Vector(c) - off
                verts.append(_to_blender((R @ p.to_4d()).to_3d() + org))
            n = len(corners)
            polys.append(tuple(base + k for k in ([0] + list(range(n - 1, 0, -1)))))   # outward winding after the axis change
            uvs.append([(u / tx.w, 1 - v / tx.h) if tx else (0, 0) for (u, v) in [quv[0]] + quv[:0:-1]])
            cu = sum(u for u, _ in quv) / n; cv = sum(v for _, v in quv) / n
            cols.append(tx.texel(cu, cv) if tx else (0.8, 0.8, 0.8))
            mids.append(mats.mats[role] if role in mats.mats else (tex_mats[ti] if tex_mats else None))
        me = bpy.data.meshes.new(el.get("name", "cube")); me.from_pydata([tuple(v) for v in verts], [], polys); me.update()
        o = kit.link(bpy.data.objects.new(el.get("name", "cube"), me), root); o["bb_kind"] = kind
        slots = []
        for m in mids:
            if m is not None and m not in slots: slots.append(m)
        for m in slots: me.materials.append(m)
        uvl = me.uv_layers.new(name="UVMap")
        attr = me.color_attributes.new("Color", "FLOAT_COLOR", "CORNER")
        for poly, puv, col, m in zip(me.polygons, uvs, cols, mids):
            poly.material_index = slots.index(m) if m in slots else 0
            for li, uv in zip(poly.loop_indices, puv):
                uvl.data[li].uv = uv; attr.data[li].color = (*col, 1.0)
        me.color_attributes.active_color = attr
        try: me.color_attributes.render_color_index = me.color_attributes.find("Color")
        except Exception: pass
        kit.shade(o)
        objs.append(o)
    if not objs: raise ValueError("the .bbmodel has no visible cube or mesh elements")
    import bmesh
    for o in objs:   # weld each element's corners (UVs and colours are per corner, so they survive)
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        if o.get("bb_kind") == "mesh": bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # free-form meshes: winding unknown
        bm.to_mesh(o.data); bm.free()

    brief = {"asset_id": asset_id, "template": "bbmodel", "out_dir": out_dir, "source": path, "material_prefix": material_prefix,
             "params": {}, "palette": palette or "", "roles": roles or {}}
    s = bpy.context.scene
    s["gitcraft_brief"] = json.dumps(brief); s["gitcraft_result"] = json.dumps({}); s["gitcraft_template"] = "bbmodel"
    blend = os.path.join(out_dir, "source", f"{asset_id}.blend"); os.makedirs(os.path.dirname(blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend, compress=True)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)
    return {"blend": blend, "source": path, "objects": len(objs), "triangles": tris, "materials": sorted(m.name for m in mats.mats.values()),
            "textures": [{"name": t.name, "embedded": bool(t.img)} for t in texs], "skipped_elements": skipped,
            "not_converted": {"groups": len(d.get("groups", [])), "animations": len(d.get("animations", []))},
            "seconds": round(time.time() - t0, 2)}
