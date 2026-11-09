"""GITCRAFT Studio: the department layer (audio, animation, worlds, FX, materials, levels,
cinematics, QA, asset management) beside the 2D tools and the 3D Department.

Every department follows one contract (studio/core/contract.py): a machine-readable manifest,
validated requests, dependency checks that report what can really run here, validated outputs
with hashes, a provenance + licence record next to the outputs, and registration in the
AssetCraft catalogue. Departments run headless and locally; nothing here needs a paid service."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO = os.path.dirname(HERE)
REPO = os.path.dirname(STUDIO)
GITCRAFT_HOME = os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft")
STUDIO_HOME = os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.join(GITCRAFT_HOME, "studio")
VERSION = "1.0.0"


def default_root(env=None, cwd=None):
    """scripts/tools.sh's default for GITCRAFT_ROOT (keep the two identical): the home folder, or the workspace when it
    lives outside home; in a cloud session (CLAUDE_CODE_REMOTE=true) a workspace that is one repository checkout gives
    way to its parent, the folder that holds every cloned repository."""
    env = os.environ if env is None else env
    home = os.path.realpath(env.get("HOME") or os.path.expanduser("~"))
    ws = os.path.realpath(env.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd())
    if ws == home or ws.startswith(home.rstrip(os.sep) + os.sep) or ws == os.sep or not os.path.isdir(ws): return home
    up = os.path.dirname(ws)
    if env.get("CLAUDE_CODE_REMOTE") == "true" and os.path.exists(os.path.join(ws, ".git")) and up != os.sep: return up
    return ws


def roots():
    rs = os.environ.get("GITCRAFT_ROOTS") or os.environ.get("GITCRAFT_ROOT") or default_root()
    return [os.path.realpath(r) for r in rs.split(":") if r]


def inside_roots(path):
    rp = os.path.realpath(path)
    return any(rp == r or rp.startswith(r.rstrip(os.sep) + os.sep) for r in roots())
