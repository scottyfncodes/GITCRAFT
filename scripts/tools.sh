#!/usr/bin/env bash
# Shared tool list and policy for GITCRAFT. Sourced by the other scripts.
# Format: <server name>:<storytold repo>:<cargo package / binary name>
GITCRAFT_TOOLS=(
  photocraft:photocraft:photocraft-cli
  vectorcraft:vectorcraft:vectorcraft-cli
  filmcraft:filmcraft:filmcraft-cli
  lightcraft:lightcraft:lightcraft-cli
  pdfcraft:printcraft:pdfcraft-cli
  effectcraft:effectcraft:effectcraft-cli
  designcraft:designcraft:designcraft-cli
)

# Tools that are not ArtCraft binaries (no CI build). Same format; installed by their own script.
#   meshcraft: the 3D Department (Blender, Blockbench, Mixamo, Meshroom, TripoSR, Hunyuan3D),
#              a Python MCP server in meshcraft/, runtimes installed by scripts/install-3d.sh
GITCRAFT_EXTRA_TOOLS=(
  meshcraft:-:meshcraft
)

GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
GITCRAFT_BIN="$GITCRAFT_HOME/bin"
GITCRAFT_SRC="$GITCRAFT_HOME/src"
GITCRAFT_TARGET="$GITCRAFT_HOME/target"
GITCRAFT_LOG="$GITCRAFT_HOME/logs"
GITCRAFT_STATE="$GITCRAFT_HOME/state"   # per-tool config/cache/tmp, writable inside the sandbox
MESHCRAFT_HOME="${MESHCRAFT_HOME:-$GITCRAFT_HOME/meshcraft}"             # Blender venv, Meshroom, AI venv, model cache
MESHCRAFT_LIBRARY="${MESHCRAFT_LIBRARY:-$GITCRAFT_HOME/meshcraft-library}" # 3D asset library + job records

# Is a tool installed? (ArtCraft binary, or MeshCraft's Blender venv)
gitcraft_installed() {
  case "$1" in
    meshcraft) [[ -x "$MESHCRAFT_HOME/venv/bin/python" ]] ;;
    *) [[ -x "$GITCRAFT_BIN/$2" ]] ;;
  esac
}

# Folder the tools may read from and write to. Defaults to the session home, or
# to the workspace when it lives outside home (cloud sessions check repos out to
# /home/user while HOME is /root, which would otherwise fence every repo out).
if [[ -z "${GITCRAFT_ROOT:-}" ]]; then
  GITCRAFT_ROOT="$HOME"
  _gc_ws="${CLAUDE_PROJECT_DIR:-$PWD}"
  case "$_gc_ws/" in
    "$HOME"/*) ;;
    /?*) [[ -d "$_gc_ws" && "$_gc_ws" != / ]] && GITCRAFT_ROOT="$_gc_ws" ;;
  esac
  unset _gc_ws
fi
# Extra authorized folders, colon-separated (e.g. one per repo). The sandbox
# allows every root; tools with a single native root flag get GITCRAFT_ROOT.
GITCRAFT_ROOTS="${GITCRAFT_ROOTS:-$GITCRAFT_ROOT}"

# Sandbox policy (enforced centrally by scripts/mcp.sh for every tool):
#   GITCRAFT_SANDBOX=landlock (default) | require (refuse to start without it) | off
#   GITCRAFT_ALLOW_NET=1 lets tools open network connections (denied by default)
GITCRAFT_SANDBOX="${GITCRAFT_SANDBOX:-landlock}"
GITCRAFT_ALLOW_NET="${GITCRAFT_ALLOW_NET:-0}"
# Tool commands refused by the guard, per server (space-separated).
gitcraft_denied() {
  case "$1" in
    effectcraft) echo "run_script" ;;   # arbitrary JavaScript; also refused natively when roots are set
    photocraft)  echo "control_call" ;; # raw bridge protocol, bypasses the MCP surface
    *) echo "" ;;
  esac
}
