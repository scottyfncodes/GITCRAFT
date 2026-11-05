#!/usr/bin/env python3
"""StudioCraft: the GITCRAFT Studio departments as one MCP server (stdio, JSON-RPC 2.0).

Started by scripts/mcp.sh behind the guard and the Landlock sandbox like every GITCRAFT tool.
Tools are generated from the department manifests: one `<department>_<action>` tool per action
(its input schema is the manifest's request schema), plus discovery and routing:

  studio_status        every department, its actions and whether each can run on this machine (why not)
  department_describe  one department's manifest: actions, request/output formats, dependencies, licences
  route                which department/action fits a brief (3D modelling goes to ForgeCraft)
  run                  run any department action by name (what ForgeCraft's department_run calls)

ForgeCraft exposes the same through `departments`, `department_route` and `department_run`.

Deferred start (like MeshCraft's, gitcraft3d/deferred.py): studiocraft is registered before its runtime is
installed, because Claude Code reads MCP servers only when a session starts. Without the studio venv the
launcher starts this server on the system Python; it answers at once with a single `studio_status` tool that
says how to install, watches for the install to finish, then sends `notifications/tools/list_changed` and runs
every department action through the venv (`cli.py --call`). The next session starts on the venv directly."""
import glob, json, os, platform, subprocess, sys, threading, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from core import STUDIO_HOME, VERSION, contract, routing, roots

VENV_PY = os.path.join(STUDIO_HOME, "venv", "bin", "python")
# this process is the Studio venv's Python (the system Python may have numpy too, but not the pinned runtime)
IN_VENV = os.path.realpath(sys.prefix) == os.path.realpath(os.path.dirname(os.path.dirname(VENV_PY)))


def runtime_ready():
    root = os.path.dirname(os.path.dirname(VENV_PY))
    return os.access(VENV_PY, os.X_OK) and bool(glob.glob(os.path.join(root, "lib", "python*", "site-packages", "numpy-*.dist-info")))


def deferred():
    """True while the Studio runtime is missing (this process lists only studio_status)."""
    return not IN_VENV and not runtime_ready()


INSTALL_HINT = ("The Studio runtime (~/.gitcraft/studio: numpy, Pillow, Node packages) isn't installed yet, so only this status "
                "tool is listed. Install it with `~/.gitcraft/runtime/scripts/install.sh studiocraft` (about a minute; the SessionStart "
                "hook also does it in the background). When it finishes, this server announces its full tool list "
                "(tools/list_changed) and this session sees the department tools without /mcp.")

COMMON = {"out_dir": {"type": "string", "description": "output folder inside a GITCRAFT root (default <root>/gitcraft-out/<department>/<name>)"},
          "name": {"type": "string", "description": "file stem for the outputs"}, "seed": {"type": "integer", "description": "deterministic seed"},
          "license": {"type": "string", "description": "override the output licence recorded in the catalogue (SPDX id)"},
          "tags": {"type": "array", "items": {"type": "string"}}}


def _hardware():
    import shutil
    mem = None
    try:
        mem = round(int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) / 1048576, 1)
    except Exception: pass
    return {"cpu_count": os.cpu_count(), "ram_gb": mem, "gpu": bool(shutil.which("nvidia-smi")), "platform": platform.platform()}


def tools():
    if deferred():
        return [("studio_status", "GITCRAFT Studio status. " + INSTALL_HINT, {"type": "object", "properties": {}})]
    out = [
        ("studio_status", "Every GITCRAFT Studio department (audiocraft, animcraft, worldcraft, fxcraft, materialcraft, levelcraft, cinematiccraft, testcraft, assetcraft, playcraft, pixelcraft), its actions and whether each can run on this machine, with the reason when not.", {"type": "object", "properties": {}}),
        ("department_describe", "One department's machine-readable manifest: actions with request schemas and outputs, dependencies with live status, acquired tools and licences, examples, limits.",
         {"type": "object", "required": ["department"], "properties": {"department": {"type": "string", "enum": contract.departments()}}}),
        ("route", "Which department and action fit a free-text brief, with proposed parameters. 3D modelling is pointed at ForgeCraft. Advice only.",
         {"type": "object", "required": ["brief"], "properties": {"brief": {"type": "string"}}}),
        ("run", "Run any department action: {department, action, params}. Same as the <department>_<action> tools.",
         {"type": "object", "required": ["department", "action"], "properties": {"department": {"type": "string", "enum": contract.departments()}, "action": {"type": "string"}, "params": {"type": "object"}}}),
    ]
    out += PRODUCTION_TOOLS
    for d in contract.departments():
        m = contract.manifest(d)
        for a, spec in m["actions"].items():
            schema = json.loads(json.dumps(spec.get("params", {"type": "object", "properties": {}})))
            schema.setdefault("properties", {}).update({k: v for k, v in COMMON.items() if k not in schema["properties"]})
            out.append((f"{d}_{a}", f"[{d}] {spec['summary']}", schema))
    return out


# ---- the Production Director (production/): one master prompt → a planned, coordinated, verified production
_P = lambda **p: {"type": "object", "properties": p}
_PID = {"type": "string", "description": "production id (from production_plan or production_list)"}
PRODUCTION_TOOLS = [
    ("production_plan", "START HERE for any substantial deliverable (a game, app, site, asset pack): give the whole master prompt. GITCRAFT interprets it "
     "(deliverable, platform, features, quality bar, acceptance criteria, assumptions, essential questions), inspects the project and what can run here, "
     "and plans every department's work as a dependency graph with parallel waves, hand-offs and quality gates. Returns the plan; then production_run.",
     {"type": "object", "required": ["prompt"], "properties": {"prompt": {"type": "string", "description": "the complete master prompt"},
      "project": {"type": "string", "description": "the project folder (default: a new folder in the workspace)"},
      "overrides": {"type": "object", "description": "corrections to the interpreted spec (deep-merged), e.g. {\"quality\": {\"playcraft_min\": 60}}"}}}),
    ("production_run", "Run (or resume) a production: every ready task on parallel workers, retries for execution failures, honest blocked states, "
     "quality gates with fix work orders and re-verification. Stops when the deliverable is ready or it waits on the agent (work orders) or a person (approvals).",
     _P(production=_PID, workers={"type": "integer", "description": "parallel workers (default 4)"}, wait={"type": "boolean", "description": "false: run in the background and poll production_status"})),
    ("production_status", "Where a production stands: every task's state (pending, in_progress, awaiting_agent, passed, failed, blocked, needs_approval), what is next and who must act.", _P(production=_PID)),
    ("production_submit", "Hand back an agent work order (WORK_ORDER.md in the task folder): the files made or changed. They are validated (exist, inside the roots, open as their format; a fix must change the project; a deployment needs evidence) before the task passes; then the run continues.",
     {"type": "object", "required": ["production", "task"], "properties": {"production": _PID, "task": {"type": "string"}, "files": {"type": "array", "items": {"type": "string"}, "description": "absolute paths of the files made or changed (inside the workspace)"},
      "notes": {"type": "string"}, "url": {"type": "string"}, "evidence": {"type": "string", "description": "deployment: a check record (.studio.json) that ran against the URL"},
      "license": {"type": "string"}, "continue": {"type": "boolean", "description": "run the production on after an accepted submission (default true)"}}}),
    ("production_approve", "A person's decision on a task that needs approval (deployment, replacing existing assets). Only call this when the person has said so.",
     {"type": "object", "required": ["production", "task", "approved"], "properties": {"production": _PID, "task": {"type": "string"}, "approved": {"type": "boolean"}, "note": {"type": "string"}}}),
    ("production_report", "The acceptance report: every criterion with its measured evidence, remediation history, blockers, and the verdict (READY / NOT READY).", _P(production=_PID)),
    ("production_list", "Every production in the store, newest first.", _P()),
    ("production_contracts", "Every department's contract: what it accepts and produces, what it requires, how success and failure are reported, where outputs go, how provenance and licences are recorded.", _P()),
]
_bg = {}


def _load_production():
    """production/ by its path: inside the sandbox the repo root is not listable, so sys.path cannot find it
    (the same reason ForgeCraft loads gitcraft3d by path)."""
    if "production" not in sys.modules:
        import importlib.util
        p = os.path.join(os.path.dirname(HERE), "production")
        spec = importlib.util.spec_from_file_location("production", os.path.join(p, "__init__.py"), submodule_search_locations=[p])
        mod = importlib.util.module_from_spec(spec); sys.modules["production"] = mod; spec.loader.exec_module(mod)


def _production(name, a):
    _load_production()
    from production import engine, store, report, contracts
    from production.cli import plan_summary
    if name == "production_plan": return plan_summary(engine.plan(a["prompt"], a.get("project"), a.get("overrides")))
    if name == "production_run":
        if a.get("wait") is False:
            pid = a["production"]
            if _bg.get(pid) and _bg[pid].is_alive(): return {"production": pid, "status": "already running in the background"}
            _bg[pid] = threading.Thread(target=engine.run, args=(pid,), kwargs={"max_workers": a.get("workers") or 4}, daemon=True); _bg[pid].start()
            return {"production": pid, "status": "started", "poll": "production_status"}
        return engine.run(a["production"], max_workers=a.get("workers") or 4)
    if name == "production_status": return engine.status(a["production"])
    if name == "production_submit":
        return engine.submit(a["production"], a["task"], a.get("files"), a.get("notes"), a.get("url"), a.get("evidence"), a.get("license"),
                             run_after=a.get("continue", True))
    if name == "production_approve": return engine.approve(a["production"], a["task"], approved=a["approved"], note=a.get("note"))
    if name == "production_report":
        pr = store.load(a["production"]); return {"production": pr["id"], "markdown": report.markdown(pr), "acceptance": report.acceptance(pr)}
    if name == "production_list": return {"productions": store.list_all()}
    if name == "production_contracts": return contracts.all_contracts()
    raise KeyError(name)


def call(name, args):
    args = dict(args or {})
    if deferred():
        if name == "studio_status": return {"studio": VERSION, "state": "waiting for the Studio runtime", "how_to_install": INSTALL_HINT}
        raise RuntimeError(INSTALL_HINT)
    if not IN_VENV:   # started before the runtime existed: run through the venv (same code, one process per call)
        r = subprocess.run([VENV_PY, os.path.join(HERE, "cli.py"), "--call", name, json.dumps(args)], capture_output=True, text=True,
                           timeout=7200, env=dict(os.environ))
        lines = r.stdout.strip().splitlines()
        if r.returncode != 0 or not lines: raise RuntimeError(f"studio {name} failed: {(r.stderr or '')[-1500:]}")
        return json.loads(lines[-1])
    if name == "studio_status":
        return {"studio": VERSION, "roots": roots(), "hardware": _hardware(), "sandbox": os.environ.get("GITCRAFT_SANDBOX"),
                "network": {"allowed_hosts": [h for h in (os.environ.get("GITCRAFT_NETGATE") or "").split(",") if h] or None,
                            "note": "HTTPS to these hosts only, through netgate" if os.environ.get("GITCRAFT_NETGATE") else "no network"},
                "departments": contract.overview()}
    if name.startswith("production_"):
        if not IN_VENV and args.get("wait") is False: args = dict(args, wait=True)   # one process per call here: no background thread survives it
        return _production(name, args)
    if name == "department_describe": return contract.describe(args["department"])
    if name == "route": return routing.route(args.get("brief", ""))
    if name == "run": return contract.run(args["department"], args["action"], args.get("params") or {})
    for d in contract.departments():
        if name.startswith(d + "_") and name[len(d) + 1:] in contract.manifest(d)["actions"]:
            return contract.run(d, name[len(d) + 1:], args)
    raise KeyError(f"unknown tool {name}")


def main():
    out = sys.stdout; lock = threading.Lock()
    real_stdout = sys.stdout; sys.stdout = sys.stderr   # nothing but JSON-RPC on the real stdout

    def send(m):
        with lock: real_stdout.write(json.dumps(m, default=str) + "\n"); real_stdout.flush()

    if deferred():   # announce the department tools once the runtime lands
        def watch():
            while not runtime_ready(): time.sleep(3)
            send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
        threading.Thread(target=watch, daemon=True).start()
    for line in sys.stdin:
        try: msg = json.loads(line)
        except ValueError: continue
        mid, method, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None: continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {"listChanged": True}},
                  "serverInfo": {"name": "studiocraft", "version": VERSION},
                  "instructions": "GITCRAFT Studio departments (audio, animation, worlds, FX, materials, levels, cinematics, QA, assets, PLAYCRAFT, PIXELCRAFT) and the Production Director. For a whole deliverable from one master prompt (a game, app, site), start with production_plan then production_run: it picks the departments, orders and parallelises them, gates every result and issues work orders for what only the agent can do (code, the 2D ArtCraft tools). For a single asset, start with studio_status or route; each <department>_<action> tool validates its request, reports `blocked` with the reason when a dependency is missing, validates and hashes every output, writes a .studio.json provenance record and registers outputs in the AssetCraft catalogue."}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s in tools()]}})
        elif method == "tools/call":
            def work(mid=mid, name=p.get("name"), a=p.get("arguments") or {}):
                try:
                    r = call(name, a)
                    err = isinstance(r, dict) and r.get("status") in ("failed", "blocked")
                    send({"jsonrpc": "2.0", "id": mid, "result": {"isError": err, "content": [{"type": "text", "text": json.dumps(r, indent=1, default=str)}]}})
                except Exception as e:
                    traceback.print_exc(file=sys.stderr)
                    hint = getattr(e, "hint", None)
                    send({"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}" + (f"\nhint: {hint}" if hint else "")}]}})
            threading.Thread(target=work, daemon=True).start()
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})


if __name__ == "__main__":
    main()
