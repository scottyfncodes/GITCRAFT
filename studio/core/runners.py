"""Run work in the departments' external runtimes, each a child process inside the same sandbox:

  blender(script, args)   a bpy script in MeshCraft's Blender venv (the GITCRAFT Blender; no second copy)
  node(script, args)      a Node script with Playwright + Chromium resolved (TestCraft, engine checks)
  venv(python, script)    a script in another isolated venv (e.g. the Kokoro voice runtime)

Scripts get their request as a JSON file and write their result as JSON; stdout/stderr are kept
for the error message only."""
import json, os, subprocess, tempfile
from . import STUDIO, STUDIO_HOME
from .contract import StudioError, Blocked
from . import deps

BPY_DIR = os.path.join(STUDIO, "core", "bpy")
WEB_DIR = os.path.join(STUDIO, "core", "web")


def _tmp():
    return tempfile.mkdtemp(prefix="studio-", dir=os.environ.get("TMPDIR"))


def _run(cmd, args, timeout, label, env=None):
    d = _tmp(); req = os.path.join(d, "request.json"); res = os.path.join(d, "result.json")
    json.dump(dict(args, _result=res), open(req, "w"), default=str)
    e = dict(os.environ, **(env or {}))
    try:
        r = subprocess.run(cmd + [req], capture_output=True, text=True, timeout=timeout, env=e)
    except subprocess.TimeoutExpired:
        raise StudioError(f"{label} timed out after {timeout} s", hint="lower the resolution/frame count or raise timeout")
    if not os.path.exists(res):
        tail = (r.stderr or r.stdout or "")[-1500:]
        raise StudioError(f"{label} failed (exit {r.returncode}): {tail}")
    out = json.load(open(res))
    if out.get("error"): raise StudioError(f"{label}: {out['error']}", hint=out.get("hint"))
    return out


def blender(script, args, timeout=900):
    py = deps.blender_python()
    if not os.access(py, os.X_OK): raise Blocked("MeshCraft's Blender (bpy) is not installed", install="scripts/install.sh meshcraft")
    env = {"BLENDER_USER_CONFIG": os.path.join(os.environ.get("XDG_CONFIG_HOME", "/tmp"), "blender"), "PYTHONPATH": BPY_DIR}
    path = script if os.path.isabs(script) else os.path.join(BPY_DIR, script)
    return _run([py, path], args, timeout, f"Blender ({os.path.basename(script)})", env)


def node(script, args, timeout=300):
    pw, chrome = deps.resolve_playwright()
    env = {"PLAYWRIGHT_MODULE": pw or "", "CHROMIUM_PATH": chrome or "", "STUDIO_NODE_MODULES": os.path.join(STUDIO_HOME, "node", "node_modules")}
    return _run(["node", os.path.join(WEB_DIR, script)], args, timeout, f"browser ({script})", env)


def venv(python, script, args, timeout=600, install="scripts/install-studio.sh voice"):
    if not os.access(python, os.X_OK): raise Blocked(f"runtime {python} is not installed", install=install)
    return _run([python, "-I", script], args, timeout, os.path.basename(script))
