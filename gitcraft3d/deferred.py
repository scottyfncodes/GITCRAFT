"""Deferred 3D: MeshCraft and ForgeCraft are registered with Claude Code before Blender is installed.

Claude Code reads its MCP servers once, when a session starts. Blender (bpy, ~400 MB) is often not there yet:
- a setup script skipped it (GITCRAFT_MESHCRAFT=0) or ran out of time during the download;
- `scripts/install.sh meshcraft` is run during a session;
- the SessionStart hook is still building it in the background.

If the servers were only registered once Blender was in, such a session could never use them, even after the
install finished (that was the bug). So they are always registered (unless GITCRAFT_MESHCRAFT=none). While Blender
is missing, each server answers the handshake at once and lists a single status tool that says how to install. A
watcher notices when the install completes and sends `notifications/tools/list_changed`, and the full tool list
appears in the running session, with no /mcp and no restart.

A MeshCraft server that started before Blender existed runs on the system Python. Once Blender is in, it runs its
Blender tools through the venv's one-shot `server.py --call` (the "bridge"). The next session starts on the venv
Python and runs everything in-process, which is the normal path.
"""
import glob, os, threading, time

GITCRAFT_HOME = os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft")
LOG = os.path.join(GITCRAFT_HOME, "logs", "meshcraft.log")


def blender_python():
    """The MeshCraft venv's Python when the bpy install has finished (not a half-installed venv), else None."""
    py = os.environ.get("FORGECRAFT_BLENDER_PY") or os.path.join(GITCRAFT_HOME, "meshcraft", "venv", "bin", "python")
    venv = os.path.dirname(os.path.dirname(py))
    if os.access(py, os.X_OK) and glob.glob(os.path.join(venv, "lib", "python*", "site-packages", "bpy-*.dist-info")):
        return py
    return None


def ready():
    return blender_python() is not None


def install_hint(server):
    return (f"{server}'s Blender (bpy, ~400 MB) isn't installed yet, so only this status tool is listed. "
            "Install it with `~/.gitcraft/runtime/scripts/install.sh meshcraft forgecraft` (a few minutes; log: "
            f"{LOG}). When it finishes, this server announces its full tool list (tools/list_changed); "
            "this session sees the tools without /mcp.")


def status(server):
    return {"server": server, "state": "waiting for Blender", "blender_python": blender_python(),
            "how_to_install": install_hint(server)}


class Watcher:
    """Polls for a finished Blender install and calls `on_ready()` once (from a daemon thread)."""

    def __init__(self, on_ready, every=3.0):
        self.on_ready, self.every = on_ready, every
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while not ready():
            time.sleep(self.every)
        self.on_ready()
