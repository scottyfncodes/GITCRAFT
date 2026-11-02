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
"""
import io, json, os, subprocess, sys, traceback, contextlib, runpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("BLENDER_USER_CONFIG", os.path.join(os.environ.get("XDG_CONFIG_HOME", "/tmp"), "blender"))
ROOTS = [os.path.realpath(r) for r in os.environ.get("GITCRAFT_ROOTS", os.environ.get("GITCRAFT_ROOT", os.getcwd())).split(":") if r]

# Blender (~1 GB) is imported in the background so the MCP handshake answers at once:
# at session start, a cold import alongside the other servers can outlast the client's
# connect timeout. Tool calls wait for the import to finish.
import threading
bpy = core = kit = Palette = None
_ready = threading.Event(); _import_error = []

def _load():
    global bpy, core, kit, Palette
    try:
        with contextlib.redirect_stdout(sys.stderr):   # bpy prints on import; stdout is the MCP channel
            import bpy as _bpy
            from engine import core as _core, kit as _kit
            from engine.palette import Palette as _P
        bpy, core, kit, Palette = _bpy, _core, _kit, _P
    except Exception as e:
        _import_error.append(f"{type(e).__name__}: {e}")
    finally:
        _ready.set()

threading.Thread(target=_load, daemon=True).start()


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


def engine_check(glb, out=None, clip=None, time=None, contract=None, material="game-toon", size=640):
    _need(glb)
    script = os.path.join(HERE, "engine_check", "three_check.mjs")
    if not os.path.isdir(os.path.join(HERE, "engine_check", "node_modules", "three")):
        raise RuntimeError("engine check needs `npm ci` in meshcraft/engine_check (three@0.170, gltf-validator)")
    cmd = ["node", script, "--glb", glb, "--material", material, "--size", str(size)]
    if out: cmd += ["--out", _need(out, write=True)]
    if clip: cmd += ["--clip", clip, "--time", str(time if time is not None else 99)]
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


def status():
    sandbox = os.environ.get("GITCRAFT_SANDBOX", "not sandboxed")
    return {"meshcraft": "1.0", "blender": bpy.app.version_string, "python": sys.version.split()[0], "sandbox": sandbox, "roots": ROOTS,
            "templates": sorted(t["id"] for t in core.list_templates()), "profiles": sorted(core.load_profiles()),
            "engine_check": os.path.isdir(os.path.join(HERE, "engine_check", "node_modules", "three"))}


def S(props, req=()):  # tiny JSON-schema helper
    return {"type": "object", "properties": props, "required": list(req)}

STR, NUM, BOOL, OBJ, ARR = {"type": "string"}, {"type": "number"}, {"type": "boolean"}, {"type": "object"}, {"type": "array"}
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
 "engine_check": ("Load an exported .glb into three@0.170 in headless Chromium the way a game would (optionally with the TIDEBREAKERS toon material), play a clip to a time, screenshot, and check a contract.",
                  S({"glb": STR, "out": STR, "clip": STR, "time": NUM, "contract": OBJ, "material": {"type": "string", "enum": ["game-toon", "authored"]}, "size": NUM}, ["glb"]),
                  lambda a: engine_check(a["glb"], a.get("out"), a.get("clip"), a.get("time"), a.get("contract"), a.get("material", "game-toon"), int(a.get("size", 640)))),
 "run_pipeline": ("The full workflow for one brief: build → preview → validate → export → validate exports (incl. Khronos) → contact sheet → manifest → report JSON.",
                  S({"brief": BRIEF}, ["brief"]), lambda a: core.run_pipeline(_brief(a))),
 "run_script": ("Assisted modelling: run a Python script from the workspace inside Blender (globals: bpy, kit, args, Palette), optionally against a .blend which is then saved. Runs inside the sandbox.",
                S({"path": STR, "blend": STR, "save": BOOL, "args": OBJ}, ["path"]),
                lambda a: run_script(a["path"], a.get("blend"), a.get("save", True), a.get("args"))),
 "inspect_file": ("Import a .glb/.gltf/.fbx/.obj/.blend and report objects, triangles, materials, clips and size (metres).", S({"path": STR}, ["path"]),
                  lambda a: core.inspect_file(_need(a["path"]))),
 "update_manifest": ("Merge entries [{path, status, notes, ...}] into a creative-package MANIFEST.json (paths are stored relative to it).",
                     S({"manifest": STR, "items": ARR}, ["manifest", "items"]),
                     lambda a: core.update_manifest(_need(a["manifest"], True), [dict(i, path=_need(i["path"])) for i in a["items"]])),
}


def send(msg):
    sys.__stdout__.write(json.dumps(msg, default=str) + "\n"); sys.__stdout__.flush()


def main():
    for line in sys.stdin:
        try: msg = json.loads(line)
        except Exception: continue
        mid, method = msg.get("id"), msg.get("method")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                  "capabilities": {"tools": {}}, "serverInfo": {"name": "meshcraft", "title": "MeshCraft (Blender)", "version": "1.0.0"},
                  "instructions": "3D production for GITCRAFT. Start with meshcraft_status and list_templates; run_pipeline does the whole brief → deliverables workflow."}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in TOOLS.items()]}})
        elif method == "tools/call":
            p = msg.get("params", {}); name, args = p.get("name"), p.get("arguments") or {}
            try:
                if name not in TOOLS: raise ValueError(f"unknown tool {name}")
                if not _ready.wait(600): raise RuntimeError("Blender is still loading; try again shortly")
                if _import_error: raise RuntimeError("Blender failed to load: " + _import_error[0] + " (run scripts/doctor.sh)")
                with contextlib.redirect_stdout(sys.stderr):
                    res = TOOLS[name][2](args)
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
