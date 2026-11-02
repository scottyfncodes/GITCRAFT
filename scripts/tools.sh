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

# Tools GITCRAFT builds itself (not ArtCraft binaries): MeshCraft is a Blender
# (bpy) MCP server living in meshcraft/ with its own venv in ~/.gitcraft/meshcraft.
# ForgeCraft is the 3D Department pipeline in forgecraft/: routing across Blender procedural,
# MeshCraft templates, Blockbench, Mixamo, Meshroom, TripoSR and Hunyuan3D, plus a versioned
# asset library. It drives MeshCraft's Blender venv; its own runtimes live in ~/.gitcraft/forgecraft.
GITCRAFT_EXTRA_TOOLS=(meshcraft:meshcraft:meshcraft forgecraft:forgecraft:forgecraft)
GITCRAFT_MESHCRAFT="${GITCRAFT_MESHCRAFT:-1}"   # 0 skips installing MeshCraft (it downloads Blender, ~400 MB)

GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
GITCRAFT_BIN="$GITCRAFT_HOME/bin"
GITCRAFT_SRC="$GITCRAFT_HOME/src"
GITCRAFT_TARGET="$GITCRAFT_HOME/target"
GITCRAFT_LOG="$GITCRAFT_HOME/logs"
GITCRAFT_STATE="$GITCRAFT_HOME/state"   # per-tool config/cache/tmp, writable inside the sandbox
FORGECRAFT_HOME="${FORGECRAFT_HOME:-$GITCRAFT_HOME/forgecraft}"               # Meshroom, AI venv, model cache
FORGECRAFT_LIBRARY="${FORGECRAFT_LIBRARY:-$GITCRAFT_HOME/forgecraft-library}" # 3D asset library + job records

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
