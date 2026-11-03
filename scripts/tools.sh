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

# Tools GITCRAFT builds itself (not ArtCraft binaries): the 3D Department.
#   meshcraft   modelling specialist: Blender (bpy) MCP server in meshcraft/, venv in ~/.gitcraft/meshcraft
#               (the department's only Blender)
#   forgecraft  orchestrator: routing, Meshroom/TripoSR/Hunyuan3D, jobs, hand-offs, UI (forgecraft/);
#               does its Blender work through MeshCraft; runtimes in ~/.gitcraft/forgecraft
# Both share gitcraft3d/ (library, jobs, probe, router) and one asset library ($GITCRAFT_3D_LIBRARY).
GITCRAFT_EXTRA_TOOLS=(meshcraft:meshcraft:meshcraft forgecraft:forgecraft:forgecraft)
# 3D tools (MeshCraft's Blender is a ~400 MB download):
#   1      install now (default)
#   later  register now, build Blender in the background when a session starts (for setup scripts with a time limit)
#   0      don't install; still registered, so `scripts/install.sh meshcraft forgecraft` works in a running session
#   none   no 3D tools at all (not registered)
GITCRAFT_MESHCRAFT="${GITCRAFT_MESHCRAFT:-1}"

GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
GITCRAFT_BIN="$GITCRAFT_HOME/bin"
GITCRAFT_SRC="$GITCRAFT_HOME/src"
GITCRAFT_TARGET="$GITCRAFT_HOME/target"
GITCRAFT_LOG="$GITCRAFT_HOME/logs"
GITCRAFT_STATE="$GITCRAFT_HOME/state"   # per-tool config/cache/tmp, writable inside the sandbox
FORGECRAFT_HOME="${FORGECRAFT_HOME:-$GITCRAFT_HOME/forgecraft}"               # Meshroom, AI venv, model cache
# The 3D asset library + job records shared by meshcraft and forgecraft. Older variables still work;
# a pre-consolidation ~/.gitcraft/meshcraft-library is used in place (same format).
if [[ -z "${GITCRAFT_3D_LIBRARY:-}" ]]; then
  GITCRAFT_3D_LIBRARY="${GITCRAFT_MESHCRAFT_LIBRARY:-${FORGECRAFT_LIBRARY:-}}"
  if [[ -z "$GITCRAFT_3D_LIBRARY" ]]; then
    GITCRAFT_3D_LIBRARY="$GITCRAFT_HOME/3d-library"
    [[ -d "$GITCRAFT_HOME/meshcraft-library" && ! -d "$GITCRAFT_3D_LIBRARY" ]] && GITCRAFT_3D_LIBRARY="$GITCRAFT_HOME/meshcraft-library"
  fi
fi

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

# MeshCraft (and ForgeCraft, which rides on its Blender) counts as installed only when the venv
# holds a finished bpy install. A venv alone is what an interrupted install leaves behind
# (e.g. a setup script that ran out of time mid-download), and registering that would show a
# server that can't start. Checks the wheel's metadata, so it never starts Blender.
gitcraft_mesh_ready() {
  [[ -x "$GITCRAFT_HOME/meshcraft/venv/bin/python" ]] || return 1
  compgen -G "$GITCRAFT_HOME/meshcraft/venv/lib/python*/site-packages/bpy-*.dist-info" >/dev/null
}
