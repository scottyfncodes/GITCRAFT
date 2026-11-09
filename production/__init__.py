"""GITCRAFT Production: one master prompt → a coordinated, verified production.

The Production Director sits above the departments. It never re-implements one:

  intake      the master prompt → a production spec (deliverable, platform, features, quality bar,
              authorisations, acceptance criteria, assumptions, the few questions that matter)
  discovery   the project (existing code, engine, assets, tests, git), and what can really run here
              (every Studio action ready/blocked, the 3D Department's probe)
  planner     spec + discovery → a task graph: stages, dependencies, handoffs, gates, parallel groups
  engine      dependency-aware scheduling with parallel workers, retries, failure propagation,
              quality gates, remediation loops, persistent state and resume
  executors   who does each task: Studio departments (studio/core/contract.py), the 3D Department
              (ForgeCraft), DESIGNCRAFT (gamedesign/), built-ins (scaffold, integrate, release), and the
              agent (Claude: code, integration, the 2D ArtCraft tools) through work orders it submits back
  report      the acceptance report: every criterion with its evidence, what is still blocked, and
              whether the deliverable is genuinely ready

Standard library only: it runs inside the studiocraft sandbox (studio venv) and on a plain python3."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
VERSION = "1.0.0"

# Task states. A tool returning successfully makes a task `complete`; only its gate makes it `passed`.
PENDING, IN_PROGRESS, AWAITING_AGENT, COMPLETE, PASSED, FAILED, BLOCKED, NEEDS_APPROVAL, SKIPPED = (
    "pending", "in_progress", "awaiting_agent", "complete", "passed", "failed", "blocked", "needs_approval", "skipped")
TERMINAL = {PASSED, FAILED, BLOCKED, SKIPPED}
STATES = [PENDING, IN_PROGRESS, AWAITING_AGENT, COMPLETE, PASSED, FAILED, BLOCKED, NEEDS_APPROVAL, SKIPPED]
STAGES = ["intake", "discovery", "foundation", "production", "integration", "qa", "release"]


def default_root(env=None, cwd=None):
    """The default GITCRAFT_ROOT, identical to scripts/tools.sh and studio/core default_root(): home, or the workspace when
    it lives outside home; in a cloud session (CLAUDE_CODE_REMOTE=true) a workspace that is one repository checkout gives
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


def store_root():
    """Where productions live: $GITCRAFT_PRODUCTION_HOME, else <first root>/gitcraft-out/production."""
    return os.path.realpath(os.environ.get("GITCRAFT_PRODUCTION_HOME") or os.path.join(roots()[0], "gitcraft-out", "production"))


def store_root_for(project):
    """(store root, why or None): the store for a production of `project`, never inside that project (production/artifacts.py)."""
    from . import artifacts
    return artifacts.store_root_for(project, store_root(), roots())


def store_roots():
    """Every place a production can live: the configured store, each root's default store, the isolated home."""
    from . import artifacts
    out = []
    for r in [store_root()] + [os.path.realpath(os.path.join(x, "gitcraft-out", "production")) for x in roots()] + [artifacts.isolated_home()]:
        if r not in out: out.append(r)
    return out
