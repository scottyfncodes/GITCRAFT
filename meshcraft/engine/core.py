"""MeshCraft engine: brief → build → preview → validate → export → manifest.

Runs inside Blender's Python (the `bpy` module). Every function takes and
returns plain JSON-able data so the MCP server can expose them directly.
"""
import json, math, os, time, hashlib, random, zlib
import bpy
from mathutils import Vector
from . import kit, templates, bake
from .palette import Palette

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(os.path.dirname(HERE), "profiles")
LINE = (0.0048, 0.0437, 0.1356)  # Deep Tide #0E3B66 in linear


# ------------------------------------------------------------------ helpers
def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def _file(path, kind, **extra):
    return {"path": path, "kind": kind, "bytes": os.path.getsize(path), "sha256": _sha(path), **extra}


def load_profiles():
    out = {}
    for f in sorted(os.listdir(PROFILES_DIR)):
        if f.endswith(".json"):
            p = json.load(open(os.path.join(PROFILES_DIR, f))); out[p["id"]] = p
    return out


def list_templates():
    return [templates.describe(m) for m in templates.registry().values()]


class Ctx:
    def __init__(self, brief, palette, mats):
        self.brief, self.params, self.palette, self.mats = brief, brief.get("params", {}), palette, mats


# ------------------------------------------------------------------ brief
REQUIRED = ("asset_id", "template", "out_dir")


def check_brief(brief):
    errs = [f"missing `{k}`" for k in REQUIRED if not brief.get(k)]
    reg = templates.registry()
    if brief.get("template") and brief["template"] not in reg:
        errs.append(f"unknown template `{brief['template']}` (have: {', '.join(sorted(reg))})")
    if brief.get("asset_id") and not all(c.isalnum() or c in "_-" for c in brief["asset_id"]):
        errs.append("`asset_id` may only use letters, digits, _ and -")
    profs = load_profiles()
    for p in brief.get("profiles", []):
        if p not in profs: errs.append(f"unknown export profile `{p}` (have: {', '.join(profs)})")
    for r in brief.get("references", []):
        if not os.path.exists(r): errs.append(f"reference not found: {r}")
    if brief.get("palette") and not os.path.exists(brief["palette"]): errs.append(f"palette not found: {brief['palette']}")
    if brief.get("template") in reg:
        meta = reg[brief["template"]].META
        for k, v in brief.get("params", {}).items():
            spec = meta["params"].get(k)
            if spec is None: errs.append(f"template `{brief['template']}` has no parameter `{k}`")
            elif "enum" in spec and v not in spec["enum"]: errs.append(f"`{k}` must be one of {spec['enum']}")
    return errs


def paths(brief):
    d = brief["out_dir"]; a = brief["asset_id"]
    return {"dir": d, "blend": os.path.join(d, "source", f"{a}.blend"), "exports": os.path.join(d, "exports"),
            "previews": os.path.join(d, "previews"), "report": os.path.join(d, f"{a}.meshcraft.json")}


# ------------------------------------------------------------------ build
def build(brief):
    errs = check_brief(brief)
    if errs: raise ValueError("brief problems: " + "; ".join(errs))
    reg = templates.registry(); mod = reg[brief["template"]]
    params = {k: v.get("default") for k, v in mod.META["params"].items()}; params.update(brief.get("params", {}))
    brief = dict(brief, params=params)
    pal = Palette.from_file(brief["palette"]) if brief.get("palette") else Palette({})
    roles = mod.default_roles(params); roles.update(brief.get("roles", {}))
    kit.reset()
    mats = kit.Materials(pal, roles, prefix=brief.get("material_prefix", "GC"))
    ctx = Ctx(brief, pal, mats)
    t0 = time.time()
    res = mod.build(ctx)
    for o in bpy.context.scene.objects:
        if o.type == "MESH" and o.data.materials:
            kit.bake_vertex_colors(o, mats, jitter=brief.get("color_jitter", 0.04), seed=zlib.crc32(o.name.encode()) & 0xffff)  # stable across runs (hash() is salted per process)
    for i, ref in enumerate(brief.get("references", [])):
        kit.add_reference(ref, f"ref_{i}_{os.path.basename(ref)}", loc=(0, 3 + i, 1), size=2.0)
    scene = bpy.context.scene
    scene["gitcraft_brief"] = json.dumps(brief)
    scene["gitcraft_result"] = json.dumps({k: v for k, v in res.items() if k in ("expect", "contract")})
    scene["gitcraft_template"] = brief["template"]
    P = paths(brief); os.makedirs(os.path.dirname(P["blend"]), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=P["blend"], compress=True)
    return {"blend": _file(P["blend"], "blend"), "seconds": round(time.time() - t0, 2), "roles": {r: mats.hex[r] for r in mats.hex},
            "objects": sorted(o.name for o in bpy.data.objects), "actions": sorted(a.name for a in bpy.data.actions),
            "contract": res.get("contract"), "expect": res.get("expect")}


def open_blend(path):
    bpy.ops.wm.open_mainfile(filepath=path)
    s = bpy.context.scene
    return json.loads(s.get("gitcraft_brief", "{}")), json.loads(s.get("gitcraft_result", "{}"))


def _meshes(): return [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]


def world_bbox(objs=None):
    pts = []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in objs or _meshes():
        ev = o.evaluated_get(dg)
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    if not pts: return None
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def _activate(obj, action_name):
    """Assign an action (from the NLA stash) as active; returns the frame range."""
    act = bpy.data.actions.get(action_name)
    if act is None or obj.animation_data is None: return None
    for tr in obj.animation_data.nla_tracks: tr.mute = True
    obj.animation_data.action = act
    try:
        if not obj.animation_data.action_slot and len(act.slots): obj.animation_data.action_slot = act.slots[0]
    except Exception:
        pass
    return act.frame_range


def set_pose(clip, at="end"):
    """Put every object that owns `clip` at its start/end/middle frame."""
    rng = None
    owners = list(bpy.context.scene.objects) + [o.data.shape_keys for o in bpy.context.scene.objects if o.type == "MESH" and o.data.shape_keys]
    for o in owners:
        if o.animation_data and any(st.action and st.action.name == clip for tr in o.animation_data.nla_tracks for st in tr.strips):
            rng = _activate(o, clip)
    if rng is None: return None
    f = {"start": rng[0], "end": rng[1], "mid": (rng[0] + rng[1]) / 2}.get(at, at)
    bpy.context.scene.frame_set(int(round(float(f))))
    return f


# ------------------------------------------------------------------ preview
VIEWS = {"three_quarter": (35, 28), "front": (0, 6), "side": (90, 6), "top": (0, 89), "back_three_quarter": (215, 24)}  # (yaw from -Y, pitch above)


def _setup_render(size, transparent):
    s = bpy.context.scene
    s.render.engine = "CYCLES"; s.cycles.device = "CPU"; s.cycles.samples = 24; s.cycles.use_denoising = True
    try: s.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception: pass
    s.render.resolution_x = s.render.resolution_y = size; s.render.film_transparent = transparent
    s.view_settings.view_transform = "Standard"
    s.render.use_freestyle = True; s.render.line_thickness_mode = "ABSOLUTE"; s.render.line_thickness = max(1.2, size / 300)
    vl = s.view_layers[0]; vl.use_freestyle = True
    fs = vl.freestyle_settings
    ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("outline")
    ls.select_by_visibility = True; ls.select_silhouette = True; ls.select_border = True; ls.select_crease = True
    if ls.linestyle is None: ls.linestyle = bpy.data.linestyles.new("gc_outline")
    ls.linestyle.color = LINE; ls.linestyle.thickness = max(1.2, size / 320)
    w = bpy.data.worlds.get("gc_world") or bpy.data.worlds.new("gc_world"); s.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background"); bg.inputs[0].default_value = (0.42, 0.62, 0.66, 1); bg.inputs[1].default_value = 0.55
    for o in [o for o in s.objects if o.name.startswith("gc_preview_")]: bpy.data.objects.remove(o)
    key = bpy.data.objects.new("gc_preview_key", bpy.data.lights.new("gc_preview_key", "SUN")); s.collection.objects.link(key)
    key.data.energy = 3.2; key.data.color = (1.0, 0.86, 0.66); key.data.angle = math.radians(8)
    key.rotation_euler = (math.radians(50), 0, math.radians(-40))
    rim = bpy.data.objects.new("gc_preview_rim", bpy.data.lights.new("gc_preview_rim", "SUN")); s.collection.objects.link(rim)
    rim.data.energy = 1.4; rim.data.color = (1.0, 0.82, 0.4); rim.rotation_euler = (math.radians(-60), 0, math.radians(150))
    return s


def _camera(bb, yaw, pitch, margin=1.25):
    s = bpy.context.scene
    cam = bpy.data.objects.get("gc_preview_cam") or bpy.data.objects.new("gc_preview_cam", bpy.data.cameras.new("gc_preview_cam"))
    if cam.name not in s.collection.objects: s.collection.objects.link(cam)
    mn, mx = bb; c = (mn + mx) / 2; r = (mx - mn).length / 2 * margin
    cam.data.type = "ORTHO"; cam.data.ortho_scale = r * 2.05
    yaw_r, pitch_r = math.radians(yaw), math.radians(pitch)
    d = Vector((math.sin(yaw_r) * math.cos(pitch_r), -math.cos(yaw_r) * math.cos(pitch_r), math.sin(pitch_r)))  # target -> camera
    cam.location = c + d * (r * 6)
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = r * 20; s.camera = cam


def render_views(blend, out_dir, size=640, views=("three_quarter", "front", "side", "top"), poses=None, transparent=True):
    """Render orthographic views (and animation poses) of a .blend; returns file records."""
    brief, _ = open_blend(blend)
    os.makedirs(out_dir, exist_ok=True); aid = brief.get("asset_id", os.path.splitext(os.path.basename(blend))[0])
    s = _setup_render(size, transparent)
    for o in s.objects:
        if o.type == "EMPTY" and o.empty_display_type == "IMAGE": o.hide_render = True
    files = []
    shots = [(v, None, None) for v in views] + [("three_quarter", p.get("clip"), p.get("at", "end")) for p in (poses or [])]
    for view, clip, at in shots:
        if clip: set_pose(clip, at)
        else: s.frame_set(0)
        bb = world_bbox()
        yaw, pitch = VIEWS[view]
        _camera(bb, yaw, pitch)
        name = f"{aid}_{view}" + (f"_{clip}-{at}" if clip else "") + ".png"
        s.render.filepath = os.path.join(out_dir, name)
        bpy.ops.render.render(write_still=True)
        files.append(_file(s.render.filepath, "preview", view=view, clip=clip, pose=at, size=size))
    return files


def contact_sheet(brief, renders, out_path, validation=None):
    """Compose renders + 2D references + palette chips into one review sheet (PNG)."""
    from PIL import Image, ImageDraw, ImageFont
    W = 1800; pad = 28
    cream, tide, gold = (246, 234, 208), (14, 59, 102), (244, 197, 66)
    refs = [r for r in brief.get("references", []) if os.path.exists(r)]
    def font(sz, bold=True):
        for f in ("/root/.local/share/fonts/Nunito-Black.ttf", os.path.expanduser("~/.local/share/fonts/Nunito-Black.ttf"),
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try: return ImageFont.truetype(f, sz)
            except Exception: pass
        return ImageFont.load_default()
    tiles = [Image.open(r["path"]).convert("RGBA") for r in renders]
    cell = (W - pad * (len(tiles) + 1)) // max(1, len(tiles))
    H = 150 + cell + 60 + (360 if refs else 0) + 120
    sheet = Image.new("RGB", (W, H), cream); d = ImageDraw.Draw(sheet)
    d.rectangle([0, 0, W, 10], fill=gold)
    d.text((pad, 30), f"{brief.get('asset_id')}  ·  MeshCraft", fill=tide, font=font(44))
    sub = f"template {brief.get('template')}  ·  {json.dumps(brief.get('params', {}))[:120]}"
    d.text((pad, 88), sub, fill=(62, 90, 120), font=font(22))
    y = 140
    for i, (t, r) in enumerate(zip(tiles, renders)):
        x = pad + i * (cell + pad)
        bg = Image.new("RGB", (cell, cell), (214, 236, 238)); t2 = t.copy(); t2.thumbnail((cell, cell)); bg.paste(t2, ((cell - t2.width) // 2, (cell - t2.height) // 2), t2)
        sheet.paste(bg, (x, y))
        lab = r.get("view", "") + (f" · {r['clip']} {r['pose']}" if r.get("clip") else "")
        d.text((x, y + cell + 8), lab, fill=tide, font=font(20))
    y += cell + 60
    if refs:
        d.text((pad, y), "2D references (GITCRAFT creative package)", fill=tide, font=font(24)); y += 40
        x = pad
        for r in refs:
            im = Image.open(r).convert("RGBA"); im.thumbnail((520, 300))
            bg = Image.new("RGB", (im.width, im.height), (214, 236, 238)); bg.paste(im, (0, 0), im)
            sheet.paste(bg, (x, y)); x += im.width + pad
        y += 320
    x = pad
    mats = sorted({(m.get("gitcraft_role"), m.get("gitcraft_color")) for m in bpy.data.materials if m.get("gitcraft_color")})
    for role, hx in mats:
        c = tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5))
        d.rounded_rectangle([x, y, x + 34, y + 34], 8, fill=c, outline=tide, width=2)
        d.text((x + 42, y + 6), role, fill=tide, font=font(18)); x += 42 + int(d.textlength(role, font=font(18))) + 26
    if validation:
        v = validation["summary"]
        d.text((pad, H - 50), f"validation: {v['pass']} pass · {v['warn']} warn · {v['fail']} fail", fill=(47, 143, 78) if v["fail"] == 0 else (192, 57, 43), font=font(24))
    os.makedirs(os.path.dirname(out_path), exist_ok=True); sheet.save(out_path, optimize=True)
    return _file(out_path, "contact_sheet")


# ------------------------------------------------------------------ validation
def _chk(results, level, name, detail, **data):
    results.append({"check": name, "level": level, "detail": detail, **data})


def validate_scene(brief, result, profile_ids=()):
    """Checks on the open .blend. Levels: pass / warn / fail / info."""
    R = []; s = bpy.context.scene
    meshes = _meshes(); profiles = load_profiles()
    budget = max([profiles[p].get("budget_tris", 10**9) for p in profile_ids if p in profiles] + [0]) or 10**9
    tmpl = templates.registry().get(brief.get("template"))
    if tmpl: budget = min(budget, tmpl.META.get("budget_tris", budget))
    _chk(R, "pass" if meshes else "fail", "has_meshes", f"{len(meshes)} mesh objects")
    dg = bpy.context.evaluated_depsgraph_get()
    tris = 0; degenerate = 0; nonmanifold = 0
    import bmesh
    for o in meshes:
        me = o.evaluated_get(dg).to_mesh()
        tris += sum(len(p.vertices) - 2 for p in me.polygons)
        degenerate += sum(1 for p in me.polygons if p.area < 1e-9)
        bm = bmesh.new(); bm.from_mesh(me); nonmanifold += sum(1 for e in bm.edges if not e.is_manifold); bm.free()
        o.evaluated_get(dg).to_mesh_clear()
    _chk(R, "pass" if tris <= budget else ("warn" if tris <= budget * 2 else "fail"), "triangle_budget", f"{tris} triangles (budget {budget})", tris=tris)
    _chk(R, "pass" if degenerate == 0 else "warn", "degenerate_faces", f"{degenerate} zero-area faces")
    _chk(R, "info", "non_manifold_edges", f"{nonmanifold} non-manifold edges (expected for kit-bashed props built from closed parts)")
    bad_scale = [o.name for o in meshes if any(abs(c - 1) > 1e-4 for c in o.scale)]
    _chk(R, "pass" if not bad_scale else "warn", "applied_scale", "all mesh scales are 1" if not bad_scale else f"unapplied scale on {bad_scale}")
    defaults = [o.name for o in s.objects if any(o.name.startswith(p) for p in ("Cube", "Sphere", "Cylinder", "Plane", "Empty", "Armature."))]
    _chk(R, "pass" if not defaults else "warn", "naming", "no default object names" if not defaults else f"default names: {defaults}")
    s.frame_set(0)
    for o in s.objects:
        if o.animation_data: o.animation_data.action = None
    bb = world_bbox()
    exp = result.get("expect") or {}
    if bb:
        mn, mx = bb; size = [round(v, 3) for v in (mx - mn)]
        if exp.get("top_z") is not None:
            off = abs(mx.z - exp["top_z"])
            _chk(R, "pass" if off < 0.02 else "fail", "origin_top", f"highest point at z={mx.z:.3f} m (expected {exp['top_z']}; hangs from its origin)")
        if exp.get("base_z") is not None:
            off = abs(mn.z - exp["base_z"])
            _chk(R, "pass" if off < 0.02 else "fail", "origin_base", f"lowest point at z={mn.z:.3f} m (expected {exp['base_z']}; the asset sits on its origin)", min_z=round(mn.z, 4))
        cx, cy = (mn.x + mx.x) / 2, (mn.y + mx.y) / 2
        if exp.get("centered", True):
            _chk(R, "pass" if abs(cx) < 0.05 * max(size) + 0.01 and abs(cy) < 0.1 * max(size) + 0.02 else "warn", "origin_centered", f"footprint centre ({cx:.3f}, {cy:.3f})")
        if "size" in exp:
            tol = exp.get("tolerance", 0.15)
            ok = all(abs(a - b) <= tol * max(b, 0.05) for a, b in zip(size, exp["size"]))
            _chk(R, "pass" if ok else "warn", "dimensions", f"{size[0]} × {size[1]} × {size[2]} m (W×D×H, expected ≈ {[round(v, 3) for v in exp['size']]})", size=size)
    unassigned = [o.name for o in meshes if not o.data.materials or any(m is None for m in o.data.materials)]
    _chk(R, "pass" if not unassigned else "fail", "materials_assigned", "every mesh has materials" if not unassigned else f"missing materials on {unassigned}")
    nocol = [o.name for o in meshes if "Color" not in o.data.color_attributes]
    _chk(R, "pass" if not nocol else "warn", "vertex_colors", "every mesh carries a 'Color' attribute (glTF COLOR_0)" if not nocol else f"no colour attribute on {nocol}")
    missing_img = [i.name for i in bpy.data.images if i.source == "FILE" and not i.packed_file and not os.path.exists(bpy.path.abspath(i.filepath)) and not i.name.startswith("ref_")]
    _chk(R, "pass" if not missing_img else "fail", "textures_resolvable", "no missing texture files" if not missing_img else f"missing: {missing_img}")
    acts = sorted(a.name for a in bpy.data.actions)
    want = [c for c in ((result.get("contract") or {}).get("clips") or [])] or [v.get("clip") for v in (result.get("contract") or {}).values() if isinstance(v, dict) and v.get("clip")]
    missing = [c for c in want if c not in acts]
    _chk(R, "pass" if not missing else "fail", "animation_clips", f"actions: {acts}" if not missing else f"missing clips {missing}", clips=acts)
    for a in bpy.data.armatures:
        arm = next(o for o in s.objects if o.data == a)
        skinned = [o for o in meshes if any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)]
        over4 = unweighted = 0
        for o in skinned:
            names = {b.name for b in a.bones}
            for v in o.data.vertices:
                ws = [g for g in v.groups if o.vertex_groups[g.group].name in names and g.weight > 0]
                over4 += len(ws) > 4; unweighted += len(ws) == 0
        _chk(R, "pass" if skinned and not over4 and not unweighted else "fail", f"skinning:{arm.name}",
             f"{len(a.bones)} bones, {len(skinned)} skinned meshes, {unweighted} unweighted verts, {over4} verts with >4 influences")
    return R


def validate_gltf(path, contract=None):
    """Structural checks on an exported .glb/.gltf (pygltflib) + contract node names."""
    import pygltflib
    R = []
    g = pygltflib.GLTF2().load(path)
    names = {n.name for n in g.nodes}
    _chk(R, "pass" if g.asset.version == "2.0" else "fail", "gltf_version", f"glTF {g.asset.version}, generator {g.asset.generator}")
    prims = [p for m in g.meshes for p in m.primitives]
    has_col = all(p.attributes.COLOR_0 is not None for p in prims)
    textured = bool(prims) and not any(p.attributes.COLOR_0 is not None for p in prims) and all(
        p.material is not None and g.materials[p.material].pbrMetallicRoughness and g.materials[p.material].pbrMetallicRoughness.baseColorTexture
        for p in prims)
    if textured:   # PBR-baked exports (web-pbr) shade from textures, not vertex colours
        _chk(R, "pass", "gltf_basecolor_texture", "every primitive uses a baseColor texture (no COLOR_0 by design)")
    else:
        _chk(R, "pass" if has_col else "warn", "gltf_color0", "every primitive has COLOR_0" if has_col else "some primitives lack COLOR_0")
    _chk(R, "info", "gltf_counts", f"{len(g.nodes)} nodes, {len(g.meshes)} meshes, {len(prims)} primitives, {len(g.materials)} materials, {len(g.animations)} animations, {len(g.skins)} skins, {len(g.images)} images",
         animations=[a.name for a in g.animations])
    if contract and contract.get("nodes"):
        miss = [v for v in contract["nodes"].values() if v not in names]
        _chk(R, "pass" if not miss else "fail", "contract_nodes", f"nodes present: {sorted(contract['nodes'].values())}" if not miss else f"missing nodes {miss}")
    return R


def khronos_validate(path):
    """Run the official Khronos glTF-Validator (npm gltf-validator) when available."""
    import subprocess
    script = os.path.join(os.path.dirname(HERE), "engine_check", "validate.mjs")
    nm = os.path.join(os.path.dirname(HERE), "engine_check", "node_modules", "gltf-validator")
    if not os.path.isdir(nm):
        return [{"check": "khronos_validator", "level": "info", "detail": "gltf-validator not installed (meshcraft/engine_check: npm ci)"}]
    try:
        out = subprocess.run(["node", script, path], capture_output=True, text=True, timeout=120)
        rep = json.loads(out.stdout)
        iss = rep.get("issues", {})
        lvl = "pass" if iss.get("numErrors", 1) == 0 else "fail"
        return [{"check": "khronos_validator", "level": lvl, "detail": f"{iss.get('numErrors')} errors, {iss.get('numWarnings')} warnings, {iss.get('numInfos')} infos",
                 "messages": [m.get("message") for m in iss.get("messages", [])[:12]]}]
    except Exception as e:
        return [{"check": "khronos_validator", "level": "warn", "detail": f"validator failed to run: {e}"}]


def summarize(checks):
    return {"pass": sum(c["level"] == "pass" for c in checks), "warn": sum(c["level"] == "warn" for c in checks),
            "fail": sum(c["level"] == "fail" for c in checks), "info": sum(c["level"] == "info" for c in checks)}


# ------------------------------------------------------------------ export
def export(blend, profile_ids, out_dir=None):
    profiles = load_profiles(); files = []
    brief, result = open_blend(blend)
    aid = brief.get("asset_id", "asset"); out_dir = out_dir or paths(brief)["exports"]
    os.makedirs(out_dir, exist_ok=True)
    for pid in profile_ids:
        prof = profiles[pid]
        open_blend(blend)
        s = bpy.context.scene
        for o in list(s.objects):  # references never ship
            if o.type == "EMPTY" and o.empty_display_type == "IMAGE": bpy.data.objects.remove(o)
        meshes = _meshes()
        for o in meshes:
            if prof.get("vertex_colors", True) and "Color" not in o.data.color_attributes:
                kit.bake_vertex_colors(o, None, 0)
        atlas_note = None
        if prof.get("atlas") and not any(m.get("gitcraft_role") and m.get("gitcraft_color") for m in bpy.data.materials):
            atlas_note = "palette atlas skipped: no palette-role materials (imported asset); its own materials are exported"
        elif prof.get("atlas"):
            # rebuild a Materials-like view from material custom props
            class _M: pass
            mm = _M(); mm.mats = {}; mm.hex = {}
            for m in bpy.data.materials:
                if m.get("gitcraft_role") and m.get("gitcraft_color"): mm.mats[m["gitcraft_role"]] = m; mm.hex[m["gitcraft_role"]] = m["gitcraft_color"]
            img, cells = kit.palette_atlas(mm, name=f"{aid}_atlas", cell=prof.get("atlas_cell", 16))
            # FBX/OBJ embed/copy textures from disk: write the atlas next to the export
            img.filepath_raw = os.path.join(out_dir, f"{aid}.{pid}.atlas.png"); img.file_format = "PNG"; img.save()
            amat = kit.atlas_material(img, name=f"{brief.get('material_prefix', 'GC')}_Atlas")
            for o in meshes: kit.apply_atlas(o, cells, amat)
        fmt = prof["format"]; base = os.path.join(out_dir, f"{aid}.{pid}")
        baked = None
        if prof.get("bake"):   # web-pbr: bake to texture maps and swap in one PBR material
            for o in meshes:
                if "Color" not in o.data.color_attributes and any(m and m.get("gitcraft_role") for m in o.data.materials):
                    kit.bake_vertex_colors(o, None, 0)
            bk = prof["bake"]
            baked = bake.bake_pbr(meshes, out_dir, os.path.basename(base), bk.get("resolution", 1024), tuple(bk.get("fallbacks", [512])),
                                  material_name=f"{brief.get('material_prefix', 'GC')}_Baked")
        textured = bool(prof.get("atlas") or baked) or any(n.type == "TEX_IMAGE" and n.image for o in meshes for m in o.data.materials
                                                             if m and m.use_nodes for n in m.node_tree.nodes)
        if fmt in ("glb", "gltf"):
            path = base + (".glb" if fmt == "glb" else ".gltf")
            bpy.ops.export_scene.gltf(filepath=path, export_format="GLB" if fmt == "glb" else "GLTF_SEPARATE", export_yup=True,
                                      export_apply=True, export_vertex_color=prof.get("gltf_vertex_color", "ACTIVE"),
                                      export_all_vertex_colors=False, export_materials="EXPORT", export_texcoords=textured,
                                      export_animations=prof.get("animations", True), export_animation_mode="ACTIONS",
                                      export_merge_animation="ACTION", export_skins=True, export_morph=True,
                                      export_image_format="AUTO", export_extras=True,
                                      export_draco_mesh_compression_enable=prof.get("draco", False))
        elif fmt == "fbx":
            path = base + ".fbx"
            bpy.ops.export_scene.fbx(filepath=path, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
                                     use_mesh_modifiers=True, mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=prof.get("animations", True),
                                     bake_anim_use_all_actions=True, bake_anim_use_nla_strips=False, path_mode="COPY", embed_textures=True,
                                     colors_type="SRGB")
        elif fmt == "stl":   # one watertight-agnostic triangle soup, rest pose, Z up, scaled (mm by default)
            path = base + ".stl"
            for a in [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]: a.data.pose_position = "REST"
            for o in bpy.context.scene.objects: o.select_set(o in meshes)
            bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=prof.get("scale", 1000.0), apply_modifiers=True,
                                  forward_axis="Y", up_axis="Z", ascii_format=False)
        elif fmt == "obj":
            path = base + ".obj"
            bpy.ops.wm.obj_export(filepath=path, export_materials=True, export_colors=True, apply_modifiers=True, forward_axis="NEGATIVE_Z", up_axis="Y",
                                  export_animation=False, path_mode="COPY")
        else:
            raise ValueError(f"profile {pid}: unknown format {fmt}")
        rec = _file(path, "export", profile=pid, format=fmt, engine=prof.get("engine"))
        if baked: rec["bake"] = baked
        if atlas_note: rec["note"] = atlas_note
        if fmt in ("glb", "gltf") and (prof.get("lods") or prof.get("collision")):
            rec["extras"] = _lods_and_collision(prof, base, meshes)
        sidecars = [os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.startswith(os.path.basename(base)) and f != os.path.basename(path)]
        if sidecars: rec["sidecars"] = [_file(p, "sidecar") for p in sorted(sidecars)]
        files.append(rec)
    return files


def _gltf_static(path, objs):
    for o in bpy.context.scene.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_yup=True, export_apply=True,
                              export_animations=False, export_vertex_color="ACTIVE", export_materials="EXPORT")


def _lods_and_collision(prof, base, meshes):
    """Extra deliverables next to a GLB: decimated LODs and a convex collision hull (separate files)."""
    import bmesh
    out = []
    dg = bpy.context.evaluated_depsgraph_get()
    statics = [o for o in meshes if not any(m.type == "ARMATURE" for m in o.modifiers)]
    if prof.get("lods") and len(statics) < len(meshes):
        out.append({"kind": "lod", "skipped": "asset has skinned meshes; decimating them would break their weights (author LODs by hand or per template)"})
    for ratio in (prof.get("lods", []) if len(statics) == len(meshes) else []):
        copies = []
        for o in statics:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
            c = bpy.data.objects.new(f"{o.name}_lod", me); bpy.context.scene.collection.objects.link(c); c.matrix_world = o.matrix_world.copy()
            mod = c.modifiers.new("decimate", "DECIMATE"); mod.ratio = ratio; mod.use_collapse_triangulate = True
            kit.apply_modifiers(c); copies.append(c)
        p = f"{base}.lod{int(ratio * 100)}.glb"; _gltf_static(p, copies)
        tris = sum(sum(len(f.vertices) - 2 for f in c.data.polygons) for c in copies)
        out.append(_file(p, "lod", ratio=ratio, triangles=tris))
        for c in copies: bpy.data.objects.remove(c)
    if prof.get("collision") == "convex":
        bm = bmesh.new()
        for o in meshes:  # rest pose, skinned meshes included
            me = o.evaluated_get(dg).to_mesh()
            for v in me.vertices: bm.verts.new(o.matrix_world @ v.co)
            o.evaluated_get(dg).to_mesh_clear()
        bmesh.ops.convex_hull(bm, input=bm.verts)
        for v in [v for v in bm.verts if not v.link_faces]: bm.verts.remove(v)
        me = bpy.data.meshes.new("collision"); bm.to_mesh(me); bm.free()
        col = bpy.data.objects.new("collision", me); bpy.context.scene.collection.objects.link(col)
        col["gitcraft_collision"] = "convex"
        p = f"{base}.collision.glb"; _gltf_static(p, [col])
        out.append(_file(p, "collision", shape="convex_hull", triangles=sum(len(f.vertices) - 2 for f in me.polygons)))
        bpy.data.objects.remove(col)
    return out


# ------------------------------------------------------------------ inspect / manifest
def inspect_file(path):
    ext = os.path.splitext(path)[1].lower()
    kit.reset()
    if ext in (".glb", ".gltf"): bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx": bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj": bpy.ops.wm.obj_import(filepath=path)
    elif ext == ".stl": bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".blend": open_blend(path)
    else: raise ValueError(f"cannot inspect {ext}")
    shapes = {pb.custom_shape for a in bpy.context.scene.objects if a.type == "ARMATURE" for pb in a.pose.bones if pb.custom_shape}
    meshes = [o for o in _meshes() if o not in shapes and not o.hide_get()]   # skip the importer's bone display shapes
    bb = world_bbox(meshes)
    dg = bpy.context.evaluated_depsgraph_get()
    tris = sum(sum(len(p.vertices) - 2 for p in o.evaluated_get(dg).to_mesh().polygons) for o in meshes)
    return {"path": path, "objects": sorted(f"{o.name} ({o.type})" for o in bpy.context.scene.objects),
            "triangles": tris, "materials": sorted(m.name for m in bpy.data.materials),
            "actions": sorted(a.name for a in bpy.data.actions), "armatures": len(bpy.data.armatures),
            "size_m": [round(v, 3) for v in (bb[1] - bb[0])] if bb else None,
            "min_z": round(bb[0].z, 4) if bb else None}


def update_manifest(manifest_path, items, tool="MeshCraft (Blender)"):
    """Merge items into a creative-package manifest (TIDEBREAKERS MANIFEST.json shape)."""
    base = os.path.dirname(manifest_path)
    data = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {"items": []}
    by = {it["path"]: it for it in data.get("items", [])}
    for it in items:
        rel = os.path.relpath(it["path"], base)
        e = by.get(rel, {"path": rel})
        e.update({"bytes": it.get("bytes", os.path.getsize(it["path"])), "tools": it.get("tools", tool), "status": it.get("status", "game-ready"),
                  "notes": it.get("notes", "")})
        for k in ("sha256", "triangles", "profile", "format", "engine", "clips", "dimensions_m"):
            if k in it: e[k] = it[k]
        by[rel] = e
    data["items"] = sorted(by.values(), key=lambda e: e["path"]); data["files"] = len(data["items"])
    data["updated"] = time.strftime("%Y-%m-%d")
    json.dump(data, open(manifest_path, "w"), indent=1)
    return {"manifest": manifest_path, "items": len(data["items"])}


# ------------------------------------------------------------------ pipeline
def run_pipeline(brief):
    """brief → build → preview → validate → export → validate exports → manifest → report."""
    t0 = time.time(); P = paths(brief); report = {"asset_id": brief.get("asset_id"), "brief": brief, "steps": []}
    def step(name, fn):
        t = time.time()
        try:
            out = fn(); report["steps"].append({"step": name, "ok": True, "seconds": round(time.time() - t, 2)}); return out
        except Exception as e:
            report["steps"].append({"step": name, "ok": False, "error": f"{type(e).__name__}: {e}"}); raise
    try:
        b = step("build", lambda: build(brief)); report["build"] = b
        prev = brief.get("preview", {})
        renders = step("preview", lambda: render_views(P["blend"], P["previews"], size=prev.get("size", 640),
                                                       views=prev.get("views", ("three_quarter", "front", "side", "top")), poses=prev.get("poses")))
        report["previews"] = renders
        bb, result = open_blend(P["blend"])
        checks = step("validate_scene", lambda: validate_scene(bb, result, brief.get("profiles", [])))
        exports = step("export", lambda: export(P["blend"], brief.get("profiles", ["three-web-toon"])))
        report["exports"] = exports
        for e in exports:
            if e["format"] in ("glb", "gltf"):
                checks += [dict(c, file=os.path.basename(e["path"])) for c in validate_gltf(e["path"], result.get("contract"))]
                checks += [dict(c, file=os.path.basename(e["path"])) for c in khronos_validate(e["path"])]
                info = inspect_file(e["path"])
                e["roundtrip"] = info
                bz = (result.get("expect") or {}).get("base_z")
                _chk(checks, "pass" if info["triangles"] and (bz is None or abs((info["min_z"] or 0) - bz) < 0.02) else "warn",
                     "roundtrip_reimport", f"re-imported {os.path.basename(e['path'])}: {info['triangles']} tris, size {info['size_m']} m, clips {info['actions']}", file=os.path.basename(e["path"]))
            elif e["format"] == "stl":
                info = inspect_file(e["path"]); e["roundtrip"] = info
                _chk(checks, "pass" if info["triangles"] else "fail", "roundtrip_reimport",
                     f"re-imported {os.path.basename(e['path'])}: {info['triangles']} tris, size {info['size_m']} (file units)", file=os.path.basename(e["path"]))
        report["validation"] = {"checks": checks, "summary": summarize(checks)}
        open_blend(P["blend"])
        sheet = step("contact_sheet", lambda: contact_sheet(brief, [r for r in renders], os.path.join(P["previews"], f"{brief['asset_id']}_sheet.png"), report["validation"]))
        report["previews"].append(sheet)
        if brief.get("manifest"):
            items = [dict(P_, tools="MeshCraft (Blender)", status="source", notes="Editable Blender source") for P_ in [b["blend"]]]
            for e in exports:
                items.append({**e, "status": "game-ready" if report["validation"]["summary"]["fail"] == 0 else "needs-fix",
                              "notes": f"{e['profile']} export ({e.get('engine')})", "triangles": next((c.get("tris") for c in checks if c["check"] == "triangle_budget"), None),
                              "clips": b["actions"]})
                items += [dict(sc, status="game-ready", notes=f"{e['profile']} sidecar") for sc in e.get("sidecars", [])]
                items += [dict(x, status="game-ready", notes=f"{e['profile']} {x['kind']}" + (f" ({int(x['ratio'] * 100)}% triangles)" if x.get("ratio") else " (convex hull)")) for x in e.get("extras", []) if "path" in x]
            items += [dict(r, status="preview", notes="MeshCraft preview render") for r in report["previews"]]
            report["manifest"] = step("manifest", lambda: update_manifest(brief["manifest"], items))
    finally:
        report["seconds"] = round(time.time() - t0, 1)
        os.makedirs(P["dir"], exist_ok=True)
        json.dump(report, open(P["report"], "w"), indent=1, default=str)
    report["report"] = P["report"]
    return report
