"""ForgeCraft → MeshCraft bridge.

ForgeCraft never models, cleans, bakes or exports meshes itself: it calls MeshCraft's tools.
call() runs `meshcraft/server.py --call <tool>` with MeshCraft's Blender (the one shared bpy
venv), i.e. exactly the code path of MeshCraft's MCP tools/call, in a child process that stays
inside ForgeCraft's sandbox. MeshCraft records its own job (linked to ForgeCraft's job through
`parent_job`) and its library version; ForgeCraft then annotates that version."""
import json, os, subprocess, sys, tempfile, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import _gitcraft3d  # noqa: F401  (loads gitcraft3d by path; see _gitcraft3d.py)
from gitcraft3d import hardware, library

SERVER = os.path.join(REPO, "meshcraft", "server.py")
PALETTES = os.path.join(HERE, "palettes")
NO_BLENDER = {"hardware_probe", "blockbench_build", "blockbench_inspect", "mixamo_guide", "route", "jobs_list", "job_get",
              "library_search", "library_get", "library_export"}


class MeshCraftError(RuntimeError):
    pass


def _roots(extra=()):
    """MeshCraft's own path checks: the session roots plus the shared library and ForgeCraft's palettes."""
    roots = [r for r in os.environ.get("GITCRAFT_ROOTS", os.environ.get("GITCRAFT_ROOT", "")).split(":") if r]
    return ":".join(dict.fromkeys(roots + [library.ROOT, PALETTES] + list(extra)))


def call(tool, args, log=None, timeout=1800, extra_roots=()):
    if not os.access(hardware.BLENDER_PY, os.X_OK):
        raise MeshCraftError(f"MeshCraft's Blender is not installed ({hardware.BLENDER_PY}): scripts/install.sh meshcraft")
    tmpdir = os.environ.get("TMPDIR") or tempfile.gettempdir(); os.makedirs(tmpdir, exist_ok=True)
    argf = os.path.join(tmpdir, f"forgecraft_call_{uuid.uuid4().hex[:8]}.json")
    json.dump(args, open(argf, "w"), default=str)
    env = dict(os.environ, GITCRAFT_ROOTS=_roots(extra_roots), GITCRAFT_3D_LIBRARY=library.ROOT)
    py = hardware.BLENDER_PY if tool not in NO_BLENDER else sys.executable   # no Blender needed for these
    lf = open(log, "a") if log else subprocess.DEVNULL
    try:
        if log: lf.write(f"$ meshcraft {tool} {json.dumps(args, default=str)[:600]}\n"); lf.flush()
        r = subprocess.run([py, SERVER, "--call", tool, "@" + argf], stdout=subprocess.PIPE, stderr=lf, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise MeshCraftError(f"MeshCraft {tool} exceeded the {timeout}s job limit")
    finally:
        if log: lf.close()
        try: os.remove(argf)
        except OSError: pass
    lines = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
    if not lines: raise MeshCraftError(f"MeshCraft {tool} exited {r.returncode} without a result" + (f"; see {log}" if log else ""))
    out = json.loads(lines[-1])
    if not out.get("ok"): raise MeshCraftError(f"MeshCraft {tool}: {out.get('error')}")
    return out["result"]


_templates = None


def templates():
    """MeshCraft's template catalogue (ids, params, budgets); cached per process."""
    global _templates
    if _templates is None: _templates = {t["id"]: t for t in call("list_templates", {}, timeout=300)}
    return _templates
