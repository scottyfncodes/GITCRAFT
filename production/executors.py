"""Who does the work. The Production Director never re-implements a department; each executor calls the
department's own entry point and returns its own result unchanged:

  studio      Studio departments: studio/cli.py --call run (the department contract: validated request,
              dependency check → `blocked`, validated + hashed outputs, .studio.json provenance, catalogue)
  forgecraft  the 3D Department: forgecraft/cli.py call <tool> (route → MeshCraft → engine check → library)
  designcraft DESIGNCRAFT game-design assessment: python -m gamedesign assess (reads the game, never runs it)
  builtin     the Director's own steps (scaffold, integrate, release report): production/builtins.py
  agent       work only Claude can do (game/app code, wiring assets in, the 2D ArtCraft MCP tools):
              a work order; Claude does it and submits the files, which are then validated

Each department runs as a child process: a crash, a hang (timeout) or a bad request in one task cannot take
down the run or another task, and tasks run truly in parallel."""
import importlib.util, json, os, re, subprocess, sys
from . import REPO

STUDIO_CLI = os.path.join(REPO, "studio", "cli.py")
FORGE_CLI = os.path.join(REPO, "forgecraft", "cli.py")


def studio_python():
    home = os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "studio")
    py = os.path.join(home, "venv", "bin", "python")
    return py if os.access(py, os.X_OK) else None


def _env(extra=None):
    """The child's environment. The isolated evaluation home (production/artifacts.py: where a production's output goes
    when every workspace root is inside the evaluated project) is appended to the child's roots so departments may write
    their outputs there; the first root, and so every default, is unchanged."""
    from .artifacts import isolated_home
    e = dict(os.environ, **(extra or {}))
    from . import default_root
    rs = [r for r in (e.get("GITCRAFT_ROOTS") or e.get("GITCRAFT_ROOT") or default_root(e)).split(":") if r]
    iso = isolated_home()
    if os.path.isdir(iso) and iso not in rs: e["GITCRAFT_ROOTS"] = ":".join(rs + [iso])
    return e


def _child(cmd, timeout, env=None):
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, env=_env(env))
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": f"timed out after {timeout} s", "failure": "timeout"}
    except OSError as e:
        return {"status": "blocked", "reason": f"cannot start {cmd[0]}: {e}"}
    lines = r.stdout.strip().splitlines()
    try: res = json.loads(lines[-1]) if lines else None
    except ValueError: res = None
    if res is None:
        tail = (r.stderr or r.stdout or "")[-1500:].strip()
        # the department refused the request before running (bad parameter, unknown action): not retryable
        kind = "request" if any(s in tail for s in ("StudioError", "is required", "unknown parameter", "is not one of", "must be ", "has no action", "GITCRAFT policy")) else "crash"
        return {"status": "failed", "error": tail.splitlines()[-1] if tail else f"exit {r.returncode} with no output", "failure": kind, "stderr": tail}
    return res


def studio_status(timeout=300):
    py = studio_python()
    if not py: return {"status": "blocked", "reason": "the Studio runtime is not installed (~/.gitcraft/studio/venv)", "install": ["scripts/install-studio.sh"]}
    return _child([py, STUDIO_CLI, "--call", "studio_status", "{}"], timeout)


def studio_run(dept, action, params, timeout=1800):
    py = studio_python()
    if not py: return {"status": "blocked", "reason": "the Studio runtime is not installed (~/.gitcraft/studio/venv)", "install": ["scripts/install-studio.sh"]}
    return _child([py, STUDIO_CLI, "--call", "run", json.dumps({"department": dept, "action": action, "params": params})], timeout)


def forgecraft_call(tool, args, timeout=7200):
    if not os.path.exists(FORGE_CLI): return {"status": "blocked", "reason": f"ForgeCraft is missing from {REPO}"}
    return _child(["python3", FORGE_CLI, "call", tool, json.dumps(args)], timeout)


def designcraft_assess(project, out_json, timeout=900):
    if not os.path.isdir(os.path.join(REPO, "gamedesign")): return {"status": "blocked", "reason": "gamedesign/ (DESIGNCRAFT) is missing"}
    rp, rj = os.path.realpath(project), os.path.realpath(out_json)
    if rj == rp or rj.startswith(rp.rstrip(os.sep) + os.sep):   # the engine routes output outside the game; never hand DESIGNCRAFT a path in it
        return {"status": "failed", "failure": "request", "error": f"DESIGNCRAFT output {out_json} is inside the game {project}: evaluation output must live outside it (store.output_root)"}
    # gamedesign is loaded by its path (inside the sandbox the repo root is not listable, so -m/PYTHONPATH cannot find it)
    boot = ("import importlib.util,sys;p=sys.argv[1];s=importlib.util.spec_from_file_location('gamedesign',p+'/__init__.py',submodule_search_locations=[p]);"
            "m=importlib.util.module_from_spec(s);sys.modules['gamedesign']=m;s.loader.exec_module(m);from gamedesign.cli import main;sys.exit(main(sys.argv[2:]))")
    r = _child_raw(["python3", "-c", boot, os.path.join(REPO, "gamedesign"), "assess", project, "--out", out_json, "--no-playcraft"], timeout, {})
    if r.get("status"): return r
    try: A = json.load(open(out_json))
    except (OSError, ValueError) as e: return {"status": "failed", "error": f"DESIGNCRAFT wrote no assessment: {e}", "failure": "crash"}
    return {"status": "ok", "outputs": [{"path": out_json, "role": "assessment", "format": "json", "ok": True}],
            "summary": {"overall": A["score"]["overall"], "coverage": A["score"].get("coverage"), "confidence": A["score"].get("confidence")},
            "findings": len(A.get("findings", [])), "proposals": [{"id": p.get("id"), "title": p.get("title"), "priority": p.get("priority")} for p in A.get("proposals", [])[:8]],
            "checks": [{"name": "DESIGNCRAFT read the game", "ok": A["inspection"]["counts"].get("source", 0) > 0 if isinstance(A["inspection"].get("counts"), dict) else True}]}


def _child_raw(cmd, timeout, env):
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout, env=_env(env))
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": f"timed out after {timeout} s", "failure": "timeout"}
    if r.returncode != 0: return {"status": "failed", "error": (r.stderr or r.stdout)[-1500:], "failure": "crash"}
    return {}


# ---------------------------------------------------------------- output validation (the department contract's own checker)
_validate = None


def validate_file(path, expect=None):
    """Open a file the way a consumer would (studio/core/validate.py). Falls back to existence + non-empty when
    Pillow is unavailable to this interpreter, and says so."""
    global _validate
    if _validate is None:
        spec = importlib.util.spec_from_file_location("gitcraft_production_validate", os.path.join(REPO, "studio", "core", "validate.py"))
        _validate = importlib.util.module_from_spec(spec); spec.loader.exec_module(_validate)
    if not os.path.isfile(path): return {"ok": False, "error": "missing"}
    try:
        r = _validate.check(path, expect=expect)
        # check() reports a missing library as a failed file; that is this interpreter's limit, not the file's
        if r.get("ok") or not re.match(r"(ImportError|ModuleNotFoundError)\b", str(r.get("error") or "")): return r
        e = r["error"]
    except ImportError as ex:
        e = str(ex)
    fmt = expect or _validate.sniff(path)
    if fmt == "png":   # the Production Director's own standard-library PNG reader
        from . import icons
        try:
            w, h, *_ = icons.header(path)
            return {"ok": True, "format": "png", "width": w, "height": h, "note": "opened with the standard-library PNG reader (Pillow is not available here)"}
        except (OSError, icons.PNGError) as pe:
            return {"ok": False, "format": "png", "error": str(pe)}
    ok = os.path.getsize(path) > 0
    return {"ok": ok, "format": fmt, "note": f"format not opened ({e}); checked non-empty only", **({} if ok else {"error": "empty file"})}
