"""ForgeCraft's bridge to the GITCRAFT Studio departments (studio/): discovery, routing and runs.

ForgeCraft stays stdlib-only: it runs the Studio's CLI (`studio/cli.py --call`) in the Studio's own
venv as a child process, inside ForgeCraft's sandbox, exactly as it runs MeshCraft for Blender work.
The departments' code, manifests and validation are the one implementation StudioCraft also serves."""
import json, os, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CLI = os.path.join(REPO, "studio", "cli.py")


def python():
    home = os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "studio")
    return os.path.join(home, "venv", "bin", "python")


def available():
    py = python()
    if not os.access(py, os.X_OK): return False, f"the Studio runtime is not installed ({py}): scripts/install-studio.sh"
    if not os.path.exists(CLI): return False, f"studio/ is missing from {REPO}"
    return True, None


def call(tool, args, timeout=3600):
    ok, why = available()
    if not ok: return {"status": "blocked", "reason": why, "install": ["scripts/install-studio.sh"]}
    r = subprocess.run([python(), CLI, "--call", tool, json.dumps(args)], capture_output=True, text=True, timeout=timeout)
    out = r.stdout.strip().splitlines()
    if r.returncode != 0 or not out:
        return {"status": "failed", "error": f"studio {tool} exited {r.returncode}: {(r.stderr or '')[-1500:]}"}
    return json.loads(out[-1])
