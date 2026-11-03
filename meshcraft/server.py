#!/usr/bin/env python3
"""MeshCraft MCP server (stdio, JSON-RPC 2.0). Runs inside Blender's Python (`bpy`).

Started by GITCRAFT's scripts/mcp.sh like every other tool, so it sits behind
the guard (path checks, audit log) and the Landlock sandbox (workspace roots
only, no network). Tools:

  meshcraft_status   versions, sandbox, roots, templates, profiles
  list_templates     templates with parameters and colour roles
  list_profiles      export profiles (engine targets)
  inspect_palette    read a palette (JSON/CSS/GPL/ASE) from a GITCRAFT brand package
  check_brief        validate a creative brief without building
  build_asset        brief → editable .blend
  render_preview     .blend → preview PNGs (+ animation poses) and a contact sheet
  validate_asset     .blend (+ exported files) → checks
  export_asset       .blend → files per export profile
  engine_check       exported .glb → load/animate/screenshot in three@0.170 (headless Chromium)
  run_pipeline       brief → build → preview → validate → export → validate → manifest → report
  run_script         run a Python modelling script from the workspace against a .blend (assisted modelling)
  inspect_file       .glb/.gltf/.fbx/.obj/.blend → counts, size, clips
  update_manifest    merge entries into a creative-package MANIFEST.json
  hardware_probe     CPU/RAM/GPU/disk and which 3D capabilities work here, with reasons (no Blender needed)
  blockbench_build   cube template → editable Blockbench project (.bbmodel), palette-coloured (no Blender needed)
  blockbench_inspect report a .bbmodel's format, elements, textures, problems (no Blender needed)
  blockbench_import  .bbmodel → MeshCraft .blend (+ optional exports with any profile, validated)
  mixamo_guide       the supported Mixamo workflow (Mixamo has no API; a person uses the site)
  mixamo_prepare_upload  character → mesh-only FBX for Mixamo's auto-rigger
  mixamo_apply       merge Mixamo animation downloads onto a Mixamo-skeleton character (+ optional exports)
  process_mesh       import a mesh made elsewhere (scan, AI, file): clean, decimate, rescale, bake, export, validate
  compose_scene      assemble finished assets (files or library ids) into a scene: sockets, ocean, sun, hero render, scene GLB
  route              which path fits a request on this machine (advice only; the 3D Department router decides)
  jobs_list / job_get / job_retry          job records: attempts, fallbacks, errors (run_pipeline,
                                           blockbench_import, mixamo_apply, compose_scene each run as a job)
  library_search / library_get / library_export   the versioned asset library (every job adds a version)

MeshCraft is the 3D Department's modelling specialist; ForgeCraft (forgecraft/) orchestrates it.
The library, job store, hardware probe and router are shared with ForgeCraft (gitcraft3d/).
`python server.py --call <tool> <json or @file>` runs one tool in-process and prints its JSON
result: that is how ForgeCraft calls MeshCraft (same code path as MCP, no second Blender).

run_pipeline, blockbench_import and mixamo_apply return what they always did, plus `job` and
`library` keys. A brief with "library": false skips the library.
"""
import io, json, os, subprocess, sys, traceback, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))   # gitcraft3d: the department's shared library, jobs, probe and router
os.environ.setdefault("BLENDER_USER_CONFIG", os.path.join(os.environ.get("XDG_CONFIG_HOME", "/tmp"), "blender"))
ROOTS = [os.path.realpath(r) for r in os.environ.get("GITCRAFT_ROOTS", os.environ.get("GITCRAFT_ROOT", os.getcwd())).split(":") if r]

# Blender (~1 GB) loads after the MCP handshake, but on the MAIN thread: bpy must be
# imported and used on the same thread (a background-thread import crashed on the first
# render). A reader thread queues messages; initialize / tools/list / ping never need
# Blender, so they are answered at once even while a cold import (session start, page
# cache empty, other servers starting) would outlast the client's connect timeout.
import queue, threading
from engine import blockbench, mixamo              # standard library only: usable before Blender loads
import _gitcraft3d  # noqa: F401  (loads gitcraft3d by path; see _gitcraft3d.py)
from gitcraft3d import hardware, library, jobs, routing, deferred
bpy = core = kit = Palette = None
_import_error = []

# How this process runs its Blender tools (see gitcraft3d/deferred.py):
#   "in-process": started on the MeshCraft venv's Python (the normal path)
#   "bridge":     started before Blender was installed; Blender calls go to the venv's one-shot `--call`
#   "waiting":    Blender isn't installed yet; only meshcraft_status is listed until it is
def _mode():
    vpy = deferred.blender_python()
    if vpy and os.path.realpath(sys.executable) == os.path.realpath(vpy): return "in-process"
    try:
        import importlib.util
        if importlib.util.find_spec("bpy") is not None: return "in-process"   # a bpy on this interpreter (dev setups)
    except Exception:
        pass
    return "bridge" if vpy else "waiting"
MODE = [_mode()]

def _load():
    global bpy, core, kit, Palette
    if bpy is not None or _import_error or MODE[0] != "in-process": return
    try:
        with contextlib.redirect_stdout(sys.stderr):   # bpy prints on import; stdout is the MCP channel
            import bpy as _bpy
            from engine import core as _core, kit as _kit
            from engine.palette import Palette as _P
        bpy, core, kit, Palette = _bpy, _core, _kit, _P
    except Exception as e:
        _import_error.append(f"{type(e).__name__}: {e}")


def _inside(p):
    rp = os.path.realpath(p)
    return any(rp == r or rp.startswith(r + os.sep) for r in ROOTS)


def _need(path, write=False):
    if not path: raise ValueError("path required")
    if not _inside(path):
        raise PermissionError(f"MeshCraft may only {'write' if write else 'read'} inside {', '.join(ROOTS)}: {path}")
    return path


def _brief(args):
    b = args.get("brief")
    if isinstance(b, str):
        b = json.load(open(_need(b)))
    if not isinstance(b, dict): raise ValueError("brief must be an object or a path to a JSON file")
    _need(b.get("out_dir", ""), write=True)
    for r in b.get("references", []): _need(r)
    if b.get("palette"): _need(b["palette"])
    if b.get("manifest"): _need(b["manifest"], write=True)
    return b


def engine_check(glb, out=None, clip=None, time=None, contract=None, material="game-toon", size=640, all_clips=False):
    _need(glb)
    script = os.path.join(HERE, "engine_check", "three_check.mjs")
    if not os.path.isdir(os.path.join(HERE, "engine_check", "node_modules", "three")):
        raise RuntimeError("engine check needs `npm ci` in meshcraft/engine_check (three@0.170, gltf-validator)")
    cmd = ["node", script, "--glb", glb, "--material", material, "--size", str(size)]
    if out: cmd += ["--out", _need(out, write=True)]
    if clip: cmd += ["--clip", clip, "--time", str(time if time is not None else 99)]
    if all_clips: cmd += ["--all-clips", "1"]
    cf = None
    if contract:
        cf = os.path.join(os.environ.get("TMPDIR", "/tmp"), "meshcraft_contract.json"); json.dump(contract, open(cf, "w"))
        cmd += ["--contract", cf]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 and not r.stdout.strip():
        raise RuntimeError(f"engine check failed: {r.stderr[-1500:]}")
    return json.loads(r.stdout)


def run_script(path, blend=None, save=True, args=None):
    """Assisted modelling: execute a workspace Python script inside Blender. The script sees
    `bpy`, `kit` (MeshCraft modelling kit), `palette`, `args`. Contained by the sandbox."""
    _need(path)
    if blend: core.open_blend(_need(blend))
    g = {"bpy": bpy, "kit": kit, "args": args or {}, "Palette": Palette}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(path, init_globals=g, run_name="__meshcraft__")
    out = {"stdout": buf.getvalue()[-4000:], "objects": sorted(o.name for o in bpy.context.scene.objects)}
    if blend and save:
        bpy.ops.wm.save_mainfile(filepath=blend); out["saved"] = blend
    return out


def _audit(a):
    from engine import audit
    for p in a.get("parts", []):
        if p.get("file"): _need(p["file"])
    if a.get("scene"): _need(a["scene"])
    return audit.run(a)


def _asset_id(a):
    aid = a.get("asset_id") or ""
    if not aid or not all(c.isalnum() or c in "_-" for c in aid): raise ValueError("`asset_id` is required and may only use letters, digits, _ and -")
    return aid


def _finish(blend, profiles, contract=None, preview=None):
    """Optional exports for imported assets, with the same checks run_pipeline makes, plus the
    same preview renders (so every library version has a thumbnail)."""
    if not profiles: return {}
    pv = preview if isinstance(preview, dict) else {"size": 512, "views": ["three_quarter", "front", "side"]}
    previews = [] if preview is False else core.render_views(blend, os.path.join(os.path.dirname(os.path.dirname(blend)), "previews"),
                                                              pv.get("size", 512), tuple(pv.get("views", ("three_quarter",))))
    exports = core.export(blend, profiles)
    b, r = core.open_blend(blend)
    checks = core.validate_scene(b, r, profiles)
    for e in exports:
        if e["format"] in ("glb", "gltf"):
            checks += [dict(c, file=os.path.basename(e["path"])) for c in core.validate_gltf(e["path"], contract or r.get("contract")) + core.khronos_validate(e["path"])]
    return {"exports": exports, "previews": previews, "validation": {"checks": checks, "summary": core.summarize(checks)}}


def _as_job(tool, args, fn, asset_id, ladder=(), meta=None, job_id=None, manual=False, to_library=True):
    """Run a producing tool as a job; add its result to the library; annotate the result."""
    b = args.get("brief"); parent = args.get("parent_job") or (b.get("parent_job") if isinstance(b, dict) else None)
    res, rec = jobs.run(tool, args, fn, asset_id=asset_id, ladder=ladder, job_id=job_id, manual=manual, parent=parent)
    info = {"id": rec["id"], "status": rec["status"], "attempts": len(rec["attempts"])}
    if rec.get("fallback"): info["fallback"] = rec["fallback"]
    if to_library:
        try:
            md = library.add_version(asset_id, res, dict(meta or {}, job=rec["id"]))
            lib = {"asset": asset_id, "version": md["version"], "dir": md["dir"], "same_as": md["same_as"], "files": len(md["files"])}
        except Exception as e:      # the deliverables exist in out_dir either way; say why the library copy failed
            lib = {"error": f"{type(e).__name__}: {e}"}
        jobs.attach(rec, library=lib)
        res["library"] = lib
    res["job"] = info
    return res


def run_pipeline(a, job_id=None, manual=False):
    brief = _brief(a)
    meta = {"tool": "run_pipeline", "template": brief.get("template"), "brief": brief, "tags": brief.get("tags", []),
            "inputs": [brief.get("palette")] + list(brief.get("references", []))}
    return _as_job("run_pipeline", {"brief": brief}, lambda x: core.run_pipeline(_brief(x)), brief["asset_id"],
                   jobs.pipeline_ladder(brief), meta, job_id, manual, brief.get("library", True) is not False)


def _blockbench_import(a):
    from engine import bbimport
    out_dir = _need(a["out_dir"], True)
    r = bbimport.import_bbmodel(_need(a["path"]), _asset_id(a), out_dir, a.get("material_prefix", "BB"),
                                _need(a["palette"]) if a.get("palette") else None, a.get("roles"))
    r.update(_finish(r["blend"], a.get("profiles", []), preview=a.get("preview")))
    return r


def blockbench_import(a, job_id=None, manual=False):
    meta = {"tool": "blockbench_import", "template": "bbmodel", "brief": a, "inputs": [a.get("path"), a.get("palette")]}
    return _as_job("blockbench_import", a, _blockbench_import, _asset_id(a), (), meta, job_id, manual, a.get("library", True) is not False)


def mixamo_apply(a, job_id=None, manual=False):
    meta = {"tool": "mixamo_apply", "template": "mixamo", "brief": a, "inputs": [a.get("character")] + list(a.get("animations", []))}
    return _as_job("mixamo_apply", a, _mixamo_apply, _asset_id(a), (), meta, job_id, manual, a.get("library", True) is not False)


def process_mesh(a, job_id=None, manual=False):
    """Import a mesh made elsewhere through the mesh_import template (a run_pipeline job)."""
    brief = {"asset_id": _asset_id(a), "template": "mesh_import", "out_dir": a["out_dir"], "title": a.get("title"),
             "params": {"path": _need(a["path"]), **{k: a[k] for k in ("crop", "crop_floor", "target_size", "max_tris", "recenter") if k in a}},
             "profiles": a.get("profiles") or ["web-pbr", "unity-fbx", "obj-static"], "preview": a.get("preview", {"size": 512, "views": ["three_quarter", "front", "side"]}),
             "tags": a.get("tags", []), "library": a.get("library", True)}
    if a.get("parent_job"): brief["parent_job"] = a["parent_job"]
    return run_pipeline({"brief": brief}, job_id, manual)


def compose_scene(a, job_id=None, manual=False):
    from engine import scene
    _need(a["out_dir"], True)
    for it in a["items"]:
        if it.get("file"): _need(it["file"])
    meta = {"tool": "compose_scene", "template": "scene", "brief": a, "tags": a.get("tags", []),
            "inputs": [it.get("file") for it in a["items"] if it.get("file")]}
    return _as_job("compose_scene", a, lambda x: scene.compose(x), _asset_id(a), (), meta, job_id, manual, a.get("library", True) is not False)


def job_retry(a):
    rec = jobs.get(a["job"])
    fn = {"run_pipeline": run_pipeline, "blockbench_import": blockbench_import, "mixamo_apply": mixamo_apply, "compose_scene": compose_scene}.get(rec["tool"])
    if fn is None: raise ValueError(f"job {rec['id']} ran {rec['tool']}, which cannot be retried")
    return fn(rec["request"], job_id=rec["id"], manual=True)


def library_export(a):
    return library.export(a["asset"], _need(a["dest"], True), a.get("version"), a.get("kinds"))


def _mixamo_apply(a):
    anims = [_need(p) for p in a.get("animations", [])]
    r = mixamo.apply(_need(a["character"]), anims, _need(a["out_dir"], True), _asset_id(a), a.get("material_prefix", "MX"))
    r.update(_finish(r["blend"]["path"], a.get("profiles", []), preview=a.get("preview")))
    return r


def status():
    sandbox = os.environ.get("GITCRAFT_SANDBOX", "not sandboxed")
    return {"meshcraft": "1.0", "blender": bpy.app.version_string, "python": sys.version.split()[0], "sandbox": sandbox, "roots": ROOTS,
            "templates": sorted(t["id"] for t in core.list_templates()), "profiles": sorted(core.load_profiles()),
            "engine_check": os.path.isdir(os.path.join(HERE, "engine_check", "node_modules", "three"))}


def S(props, req=()):  # tiny JSON-schema helper
    return {"type": "object", "properties": props, "required": list(req)}

STR, NUM, BOOL, OBJ, ARR = {"type": "string"}, {"type": "number"}, {"type": "boolean"}, {"type": "object"}, {"type": "array"}
STRS = {"type": "array", "items": {"type": "string"}}
BRIEF = {"description": "Creative brief object, or a path to a brief JSON file. Keys: asset_id, template, params, palette, roles, material_prefix, references, out_dir, profiles, preview{size,views,poses[{clip,at}]}, manifest, color_jitter.",
         "anyOf": [OBJ, STR]}

TOOLS = {
 "meshcraft_status": ("Blender version, sandbox status, authorized roots, templates and export profiles.", S({}), lambda a: status()),
 "list_templates": ("Every modelling template with its parameters, colour roles and triangle budget.", S({}), lambda a: core.list_templates()),
 "list_profiles": ("Export profiles (engine targets): format, vertex colours, atlas, animations, budget.", S({}), lambda a: core.load_profiles()),
 "inspect_palette": ("Read a palette file (JSON/CSS/GPL/ASE) from a GITCRAFT brand package.", S({"path": STR}, ["path"]),
                     lambda a: Palette.from_file(_need(a["path"])).colors),
 "check_brief": ("Validate a creative brief without building. Returns a list of problems (empty = OK).", S({"brief": BRIEF}, ["brief"]),
                 lambda a: core.check_brief(_brief(a))),
 "build_asset": ("Build the asset described by a brief and save an editable .blend (out_dir/source/<asset_id>.blend).", S({"brief": BRIEF}, ["brief"]),
                 lambda a: core.build(_brief(a))),
 "render_preview": ("Render orthographic preview PNGs of a .blend (views: three_quarter, front, side, top, back_three_quarter) and animation poses [{clip, at: start|mid|end|frame}].",
                    S({"blend": STR, "out_dir": STR, "size": NUM, "views": ARR, "poses": ARR}, ["blend", "out_dir"]),
                    lambda a: core.render_views(_need(a["blend"]), _need(a["out_dir"], True), int(a.get("size", 640)),
                                                tuple(a.get("views", ("three_quarter", "front", "side", "top"))), a.get("poses"))),
 "validate_asset": ("Validate a .blend (geometry, budget, origin, scale, materials, colours, clips, skinning) and optionally exported .glb files (structure, contract, Khronos validator).",
                    S({"blend": STR, "exports": ARR, "profiles": ARR}, ["blend"]),
                    lambda a: (lambda b, r: (lambda checks: {"checks": checks, "summary": core.summarize(checks)})(
                        core.validate_scene(b, r, a.get("profiles", [])) + sum([core.validate_gltf(_need(e), r.get("contract")) + core.khronos_validate(e) for e in a.get("exports", [])], [])))(*core.open_blend(_need(a["blend"])))),
 "export_asset": ("Export a .blend with one or more profiles (see list_profiles). Files go to out_dir (default <asset>/exports).",
                  S({"blend": STR, "profiles": ARR, "out_dir": STR}, ["blend", "profiles"]),
                  lambda a: core.export(_need(a["blend"]), a["profiles"], _need(a["out_dir"], True) if a.get("out_dir") else None)),
 "engine_check": ("Load an exported .glb into three@0.170 in headless Chromium the way a game would (optionally with the TIDEBREAKERS toon material), play a clip to a time, screenshot, and check a contract. "
                  "all_clips: also play every clip on its own and fail any clip that does not move the asset.",
                  S({"glb": STR, "out": STR, "clip": STR, "time": NUM, "contract": OBJ, "material": {"type": "string", "enum": ["game-toon", "authored"]}, "size": NUM, "all_clips": BOOL}, ["glb"]),
                  lambda a: engine_check(a["glb"], a.get("out"), a.get("clip"), a.get("time"), a.get("contract"), a.get("material", "game-toon"), int(a.get("size", 640)), bool(a.get("all_clips")))),
 "run_pipeline": ("The full workflow for one brief: build → preview → validate → export → validate exports (incl. Khronos) → contact sheet → manifest → report JSON.",
                  S({"brief": BRIEF}, ["brief"]), run_pipeline),
 "audit_overlaps": ("Overlap audit for an assembly: parts (model files, material/region/node subsets of one, or box/cylinder proxies, "
                    "each with a transform) or an assembled scene file, optional motion ranges for moving nodes, and contacts that touch on "
                    "purpose. Builds a BVH per part and reports every pair whose triangles intersect, sweeping every combination of the "
                    "motion poses (static pairs once). Coordinates: glTF (Y up, default) or Blender. See engine/audit.py and the README.",
                    S({"parts": ARR, "scene": STR, "motion": ARR, "contacts": ARR, "frame": {"type": "string", "enum": ["gltf", "blender"]},
                       "max_poses": NUM}),
                    lambda a: _audit(a)),
 "run_script": ("Assisted modelling: run a Python script from the workspace inside Blender (globals: bpy, kit, args, Palette), optionally against a .blend which is then saved. Runs inside the sandbox.",
                S({"path": STR, "blend": STR, "save": BOOL, "args": OBJ}, ["path"]),
                lambda a: run_script(a["path"], a.get("blend"), a.get("save", True), a.get("args"))),
 "inspect_file": ("Import a .glb/.gltf/.fbx/.obj/.blend and report objects, triangles, materials, clips and size (metres).", S({"path": STR}, ["path"]),
                  lambda a: core.inspect_file(_need(a["path"]))),
 "hardware_probe": ("What this machine can do for 3D: CPU, RAM, NVIDIA GPUs, free disk at the roots, sandbox/network, and each capability (Blender, texture bake, Blockbench, Mixamo, engine check, photogrammetry, image-to-3D) with the reason when unavailable. Answers without loading Blender.",
                    S({}), lambda a: hardware.probe(ROOTS)),
 "process_mesh": ("Import a mesh made elsewhere (photogrammetry scan, AI generation, download: GLB/glTF/FBX/OBJ/STL/PLY) through the mesh_import template: optional scan crop (floor, fragments, floating outliers), cleanup, decimation to max_tris, grounding at the origin, rescale to target_size metres; its own materials/textures/vertex colours are kept and baked by web-pbr. Then previews, validation, exports, library version.",
                  S({"path": STR, "asset_id": STR, "out_dir": STR, "crop": NUM, "crop_floor": BOOL, "target_size": NUM, "max_tris": NUM,
                     "profiles": STRS, "title": STR, "tags": STRS}, ["path", "asset_id", "out_dir"]), lambda a: process_mesh(a)),
 "compose_scene": ("Assemble finished assets into one scene: items [{file | asset (library id) [+ version], name, location[x,y,z], rotation[deg], scale, attach_to:'<item name>:<socket_*>'}], ocean plane, sun (elevation, tilt, azimuth), sky, camera/look_at, Cycles hero render; saves the .blend and exports a scene GLB with every clip, validated (Khronos).",
                   S({"asset_id": STR, "out_dir": STR, "items": ARR, "camera": ARR, "look_at": ARR, "lens": NUM, "sun": ARR, "sky": STR,
                      "samples": NUM, "resolution": ARR, "frame": NUM, "ocean_size": NUM, "tags": STRS}, ["asset_id", "out_dir", "items"]), lambda a: compose_scene(a)),
 "blockbench_build": ("Write an editable Blockbench project (.bbmodel, format 5.0) from a cube template: " + ", ".join(sorted(blockbench.TEMPLATES)) + ". "
                      "Colours come from the project's palette via `roles` {role: palette name or hex} (roles per template: see blockbench_inspect output or the error message). Open it in Blockbench to edit; bring it back with blockbench_import.",
                      S({"template": {"type": "string", "enum": sorted(blockbench.TEMPLATES)}, "out": STR, "name": STR, "palette": STR, "roles": OBJ, "seed": NUM}, ["template", "out"]),
                      lambda a: blockbench.build(a["template"], _need(a["out"], True), a.get("name"), _need(a["palette"]) if a.get("palette") else None,
                                                 a.get("roles"), int(a.get("seed", 1)))),
 "blockbench_inspect": ("Read a .bbmodel (made here or saved from Blockbench) and report format version, elements, textures, animations and problems.",
                        S({"path": STR}, ["path"]), lambda a: blockbench.inspect(_need(a["path"]))),
 "blockbench_import": ("Convert a .bbmodel (cubes and mesh elements, embedded textures kept, per-face colours baked for the toon pipeline) into a MeshCraft .blend at out_dir/source/<asset_id>.blend. "
                       "Then render_preview / validate_asset / export_asset / engine_check work as for any asset; or pass `profiles` to export and validate at once.",
                       S({"path": STR, "out_dir": STR, "asset_id": STR, "profiles": STRS, "palette": STR, "roles": OBJ, "material_prefix": STR}, ["path", "out_dir", "asset_id"]),
                       blockbench_import),
 "mixamo_guide": ("The supported Mixamo workflow step by step (Mixamo has no API: a person uploads and downloads at mixamo.com), the export settings to use, the core bone names MeshCraft matches, and the licence terms.",
                  S({}), lambda a: mixamo.guide()),
 "mixamo_prepare_upload": ("Export a character (GLB/FBX/OBJ or MeshCraft .blend, in T-pose or A-pose) as a mesh-only FBX with the rig removed: the file to upload to Mixamo's auto-rigger.",
                           S({"input": STR, "out": STR}, ["input", "out"]),
                           lambda a: mixamo.prepare_upload(_need(a["input"]), _need(a["out"], True))),
 "mixamo_apply": ("Merge Mixamo animation downloads (FBX, 'Without Skin') onto a character with a Mixamo skeleton (Mixamo's 'With Skin' FBX, or a .blend). Each file becomes a named clip; clips from a different skeleton are refused with the reason. "
                  "Saves out_dir/source/<asset_id>.blend; pass `profiles` (e.g. web-pbr, godot-glb) to export and validate at once.",
                  S({"character": STR, "animations": STRS, "out_dir": STR, "asset_id": STR, "profiles": STRS, "material_prefix": STR}, ["character", "animations", "out_dir", "asset_id"]),
                  mixamo_apply),
 "route": ("Advice only: which MeshCraft path fits a request on this machine (template, Blockbench, Mixamo, run_script, photogrammetry, image-to-3D), the tools to call, and why. "
           "Unavailable capabilities are reported as unavailable; alternatives are labelled when they would not be derived from the photos or image.",
           S({"request": STR, "images": NUM}, ["request"]), lambda a: routing.advice(a["request"], int(a.get("images", 0)), hardware.probe(ROOTS))),
 "jobs_list": ("Recent MeshCraft jobs (run_pipeline, blockbench_import, mixamo_apply): status (done, done_with_fallback, failed), attempts, library version.",
               S({"limit": NUM, "status": STR}), lambda a: jobs.list_jobs(a.get("limit", 20), a.get("status"))),
 "job_get": ("One job record: the request, every attempt (what was changed for it, timing, error), the pipeline steps and the library version.",
             S({"job": STR}, ["job"]), lambda a: jobs.get(a["job"])),
 "job_retry": ("Re-run a job with its original request, as a new attempt on the same record (automatic fallbacks apply again).",
               S({"job": STR}, ["job"]), job_retry),
 "library_search": ("Search the versioned 3D asset library by text (id, title, template, tool, tags), template, tool or validation status (pass / needs-fix).",
                    S({"query": STR, "template": STR, "tool": STR, "status": STR, "limit": NUM}),
                    lambda a: library.search(a.get("query", ""), a.get("template"), a.get("tool"), a.get("status"), a.get("limit", 50))),
 "library_get": ("Full record of one asset version (latest by default): every file with its SHA-256, inputs, brief, validation, clips, contract, job, and `same_as` when it matches the previous version.",
                 S({"asset": STR, "version": NUM}, ["asset"]), lambda a: library.get(a["asset"], a.get("version"))),
 "library_export": ("Copy an asset version (source .blend, exports, previews, asset.json) into dest/<asset>_v<N>/ inside a GITCRAFT root and verify every copy's SHA-256: the handoff to a game repo or another tool. `kinds` limits it (e.g. [\"export\", \"lod\", \"collision\"]).",
                    S({"asset": STR, "version": NUM, "dest": STR, "kinds": STRS}, ["asset", "dest"]), library_export),
 "update_manifest": ("Merge entries [{path, status, notes, ...}] into a creative-package MANIFEST.json (paths are stored relative to it).",
                     S({"manifest": STR, "items": ARR}, ["manifest", "items"]),
                     lambda a: core.update_manifest(_need(a["manifest"], True), [dict(i, path=_need(i["path"])) for i in a["items"]])),
}


NO_BLENDER = {"hardware_probe", "blockbench_build", "blockbench_inspect", "mixamo_guide", "route", "jobs_list", "job_get",
              "library_search", "library_get", "library_export"}


_send_lock = threading.Lock()
def send(msg):
    with _send_lock:   # the Blender watcher thread may send tools/list_changed
        sys.__stdout__.write(json.dumps(msg, default=str) + "\n"); sys.__stdout__.flush()


def call(name, args):
    """Run one tool in this process (ForgeCraft's bridge): same code path as tools/call."""
    if name not in TOOLS: raise ValueError(f"unknown tool {name}")
    if name not in NO_BLENDER:
        _load()
        if _import_error: raise RuntimeError("Blender failed to load: " + _import_error[0])
    with contextlib.redirect_stdout(sys.stderr):
        return TOOLS[name][2](args)


def _bridged(name, args):
    """Run a Blender tool through the venv's one-shot mode. Used only by a server that started before Blender was
    installed; the next session runs in-process."""
    py = deferred.blender_python()
    if not py: raise RuntimeError(deferred.install_hint("MeshCraft"))
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".json", prefix="meshcraft_call_"); os.close(fd)
    try:
        json.dump(args, open(path, "w"))
        r = subprocess.run([py, os.path.abspath(__file__), "--call", name, "@" + path], capture_output=True, text=True, timeout=6 * 3600)
        last = [l for l in r.stdout.splitlines() if l.strip().startswith("{")]
        if not last: raise RuntimeError(f"MeshCraft (bridge) gave no result: {r.stderr[-1500:]}")
        out = json.loads(last[-1])
        if not out.get("ok"): raise RuntimeError(out.get("error", "failed") + "\n" + out.get("trace", ""))
        return out["result"]
    finally:
        os.unlink(path)


def run_tool(name, args):
    """tools/call: in-process, or bridged when this server started before Blender was installed."""
    if name not in TOOLS: raise ValueError(f"unknown tool {name}")
    if MODE[0] == "waiting":
        if name == "meshcraft_status": return deferred.status("MeshCraft")
        raise RuntimeError(deferred.install_hint("MeshCraft"))
    if name in NO_BLENDER:
        with contextlib.redirect_stdout(sys.stderr):
            return TOOLS[name][2](args)
    if MODE[0] == "bridge":
        res = _bridged(name, args)
        if name == "meshcraft_status" and isinstance(res, dict):
            res["mode"] = "bridge: this server started before Blender was installed; new sessions run in-process"
        return res
    _load()
    if _import_error: raise RuntimeError("Blender failed to load: " + _import_error[0] + " (run scripts/doctor.sh)")
    with contextlib.redirect_stdout(sys.stderr):
        res = TOOLS[name][2](args)
    if name == "meshcraft_status" and isinstance(res, dict): res["mode"] = "in-process"
    return res


def tool_list():
    if MODE[0] == "waiting":
        return [{"name": "meshcraft_status", "description": "MeshCraft status. " + deferred.install_hint("MeshCraft"), "inputSchema": S({})}]
    return [{"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in TOOLS.items()]


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--call":
        raw = sys.argv[3] if len(sys.argv) > 3 else "{}"
        args = json.load(open(raw[1:])) if raw.startswith("@") else json.loads(raw)
        try:
            out = {"ok": True, "result": call(sys.argv[2], args)}
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=4)[-1500:]}
        sys.__stdout__.write("\n" + json.dumps(out, default=str) + "\n"); sys.__stdout__.flush()
        return
    inbox = queue.Queue()
    def reader():
        for line in sys.stdin: inbox.put(line)
        inbox.put(None)
    threading.Thread(target=reader, daemon=True).start()
    if MODE[0] == "waiting":
        def blender_arrived():
            MODE[0] = "bridge"
            send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
        deferred.Watcher(blender_arrived)
    while True:
        try:
            line = inbox.get(timeout=0.5)
        except queue.Empty:
            _load()          # quiet after the handshake: warm Blender up on the main thread
            continue
        if line is None: break
        try: msg = json.loads(line)
        except Exception: continue
        mid, method = msg.get("id"), msg.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {"listChanged": True}}, "serverInfo": {"name": "meshcraft", "title": "MeshCraft (Blender)", "version": "1.0.0"},
                  "instructions": "3D production for GITCRAFT. Start with meshcraft_status and list_templates; run_pipeline does the whole brief → deliverables workflow. Export profiles include three-web-toon (vertex-colour toon), web-pbr (baked texture maps) and stl-print. Blockbench (.bbmodel) and Mixamo hand-offs: blockbench_* and mixamo_* tools; hardware_probe says what this machine can do."}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": tool_list()}})
        elif method == "tools/call":
            p = msg.get("params", {}); name, args = p.get("name"), p.get("arguments") or {}
            try:
                res = run_tool(name, args)
                send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(res, default=str)}]}})
            except Exception as e:
                tb = traceback.format_exc(limit=4)
                send({"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}\n{tb[-1500:]}"}]}})
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}})


if __name__ == "__main__":
    main()
