"""Where MeshCraft's engine check finds its Node packages (three@0.170, gltf-validator).

The packages are pinned in meshcraft/engine_check/package.json. They are looked up, in order, in:
  1. $MESHCRAFT_NODE_MODULES                                  (an explicit override)
  2. meshcraft/engine_check/node_modules next to this code    (a developer checkout after `npm ci`)
  3. $GITCRAFT_HOME/meshcraft/engine_check/node_modules       (where scripts/install.sh installs them)

The installed copy lives outside the code on purpose: the runtime is a fresh copy of a checkout on every update
(scripts/install-runtime.sh), and a checkout or a runtime copy has no node_modules, so packages installed inside one
were lost on the next update. A folder is used only when it holds exactly the pinned versions.
Standard library only: imported by the server and inside Blender.
"""
import json, os

ENGINE_CHECK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine_check")
INSTALL_HINT = "scripts/install.sh meshcraft (npm ci into $GITCRAFT_HOME/meshcraft/engine_check)"


def pinned():
    try:
        return json.load(open(os.path.join(ENGINE_CHECK, "package.json"))).get("dependencies", {})
    except (OSError, ValueError):
        return {}


def candidates():
    home = os.environ.get("GITCRAFT_HOME") or os.path.join(os.path.expanduser("~"), ".gitcraft")
    out = [os.environ.get("MESHCRAFT_NODE_MODULES"), os.path.join(ENGINE_CHECK, "node_modules"),
           os.path.join(home, "meshcraft", "engine_check", "node_modules")]
    return [c for i, c in enumerate(out) if c and c not in out[:i]]


def _version(mods, pkg):
    try:
        return json.load(open(os.path.join(mods, pkg, "package.json"))).get("version")
    except (OSError, ValueError):
        return None


def find(pkgs=("three", "gltf-validator")):
    """The first node_modules folder with every package in `pkgs` at its pinned version, or None."""
    pins = pinned()
    for mods in candidates():
        if all(_version(mods, p) is not None and _version(mods, p) == pins.get(p, _version(mods, p)) for p in pkgs):
            return os.path.realpath(mods)
    return None


def env(mods):
    """The environment for a node process that should use `mods` (the .mjs scripts read MESHCRAFT_NODE_MODULES)."""
    return dict(os.environ, MESHCRAFT_NODE_MODULES=mods)
