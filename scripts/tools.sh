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

# The upstream commit each ArtCraft CLI is built from (CI and `install.sh --source`). Reviewed pins, never a moving
# branch: a change upstream reaches GITCRAFT only through a pull request that bumps one of these (review the upstream
# diff first). The prebuilt binaries those builds produce are pinned by checksum in scripts/bin.sha256.
gitcraft_upstream_sha() {
  case "$1" in
    photocraft)  echo 02e9907f683bcda0e8a3de4865a914f6aa9280c1 ;;
    vectorcraft) echo 1cb78a0ccf26d81584b876af2db520f308eb31a0 ;;
    filmcraft)   echo 3f137a7ed420cac79b32145f5243b7f98b31f71c ;;
    lightcraft)  echo aa08a77060c0cca737dcc29b5db814cbc07ae611 ;;
    pdfcraft)    echo efd265563edfe1b5a3261b184fbc4c83f67f4364 ;;
    effectcraft) echo 60e2cbbbe3d73c0a9074c25a1a615ccfec18721c ;;
    designcraft) echo 47ef1ec411d53e98a31c576d80a1d0e20ef5eb04 ;;
    *) return 1 ;;
  esac
}

# The SHA-256 a prebuilt <pkg>.gz must have (scripts/bin.sha256, reviewed in main). Empty when it is not pinned:
# an unpinned prebuilt is never installed. gitcraft_expected_sha256 <pkg> [pin file]
gitcraft_expected_sha256() {
  local f="${2:-$(dirname "${BASH_SOURCE[0]}")/bin.sha256}"
  [[ -f "$f" ]] || return 0
  awk -v want="$1.gz" '$1 ~ /^[0-9a-f]{64}$/ && $2 == want {print $1; exit}' "$f"
}

# Tools GITCRAFT builds itself (not ArtCraft binaries): the 3D Department.
#   meshcraft   modelling specialist: Blender (bpy) MCP server in meshcraft/, venv in ~/.gitcraft/meshcraft
#               (the department's only Blender)
#   forgecraft  orchestrator: routing, Meshroom/TripoSR/Hunyuan3D, jobs, hand-offs, UI (forgecraft/);
#               does its Blender work through MeshCraft; runtimes in ~/.gitcraft/forgecraft
# Both share gitcraft3d/ (library, jobs, probe, router) and one asset library ($GITCRAFT_3D_LIBRARY).
#   studiocraft the Studio departments (studio/): audiocraft, animcraft, worldcraft, fxcraft, materialcraft,
#               levelcraft, cinematiccraft, testcraft, assetcraft, playcraft — one MCP server; runtimes in ~/.gitcraft/studio
#               (needs no Blender; its Blender actions use MeshCraft's and report `blocked` without it)
GITCRAFT_EXTRA_TOOLS=(meshcraft:meshcraft:meshcraft forgecraft:forgecraft:forgecraft studiocraft:studio:studiocraft)
# 3D tools (MeshCraft's Blender is a ~400 MB download). On demand by default: a session that needs 3D installs it
# itself with scripts/install-3d.sh (the registered servers then announce their tools, no /mcp).
#   0      on demand (default): registered, nothing downloaded until install-3d.sh (or install.sh meshcraft forgecraft)
#   later  register now, build Blender in the background when a session starts
#   1      install with everything else (never inside a setup script: the setup guard below skips it there)
#   none   no 3D tools at all (not registered)
GITCRAFT_MESHCRAFT="${GITCRAFT_MESHCRAFT:-0}"
# Studio departments (studiocraft): 1 installs the core runtime (venv + Node packages, ~250 MB), 0 skips it.
GITCRAFT_STUDIO="${GITCRAFT_STUDIO:-1}"
# Studio voice runtime (Kokoro model ~115 MB + onnxruntime): 1 install now, later = in the background when a
# session starts (the global SessionStart hook), 0 = not at all (audiocraft_voice reports blocked).
GITCRAFT_STUDIO_VOICE="${GITCRAFT_STUDIO_VOICE:-1}"

GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
GITCRAFT_BIN="$GITCRAFT_HOME/bin"
GITCRAFT_SRC="$GITCRAFT_HOME/src"
GITCRAFT_TARGET="$GITCRAFT_HOME/target"
GITCRAFT_LOG="$GITCRAFT_HOME/logs"
GITCRAFT_STATE="$GITCRAFT_HOME/state"   # per-tool config/cache/tmp, writable inside the sandbox
GITCRAFT_STUDIO_HOME="${GITCRAFT_STUDIO_HOME:-$GITCRAFT_HOME/studio}"         # studio venvs, voice models, Node runtime
GITCRAFT_ASSET_CATALOG="${GITCRAFT_ASSET_CATALOG:-$GITCRAFT_HOME/assetcraft/catalog.sqlite}"   # AssetCraft catalogue (all projects)

# Setup guard. A cloud environment's setup script has a time limit, and a run cut off mid-download leaves every later
# step undone. So during setup nothing over GITCRAFT_SETUP_MAX_MB (100) is downloaded: the step is skipped with one
# line saying how a session gets it. "During setup" is GITCRAFT_SETUP=1 (setup-env.sh exports it), or the time between
# setup-env.sh and the first session: $GITCRAFT_HOME/setup-phase, which setup-env.sh writes and the SessionStart hook
# removes. That catches install lines a setup script runs after setup-env.sh. The marker counts for an hour, and never
# inside a Claude Code session or at a terminal, where an install was asked for. GITCRAFT_SETUP=0 turns the guard off.
GITCRAFT_SETUP_MAX_MB="${GITCRAFT_SETUP_MAX_MB:-100}"
gitcraft_in_setup() {
  case "${GITCRAFT_SETUP:-}" in 1) return 0 ;; 0) return 1 ;; esac
  [[ -z "${CLAUDECODE:-}${CLAUDE_CODE_SESSION_ID:-}" && ! -t 1 ]] || return 1
  [[ -n "$(find "$GITCRAFT_HOME/setup-phase" -mmin -60 2>/dev/null)" ]]
}
# gitcraft_setup_allows <what> <approximate MB> <how a session gets it>: false, with one line printed and logged, when
# this is setup and the download is over the limit. True everywhere else.
gitcraft_setup_allows() {
  gitcraft_in_setup && (( $2 > GITCRAFT_SETUP_MAX_MB )) || return 0
  local note="gitcraft: setup skipped $1 (~$2 MB, over the $GITCRAFT_SETUP_MAX_MB MB setup limit): $3"
  echo "$note"; mkdir -p "$GITCRAFT_LOG" && echo "$(date -u +%FT%TZ) $note" >> "$GITCRAFT_LOG/setup-skipped.log"
  return 1
}
# The same limit on a direct download's real size, as curl arguments (empty outside setup): curl $(gitcraft_curl_cap) ...
gitcraft_curl_cap() { if gitcraft_in_setup; then echo "--max-filesize $((GITCRAFT_SETUP_MAX_MB * 1024 * 1024))"; fi; }
# PLAYCRAFT's Game Quality History (all games): outside the runtime, so upgrades never touch it; the committed
# archive <GITCRAFT>/history/playcraft is imported into it automatically
GITCRAFT_PLAYCRAFT_HISTORY="${GITCRAFT_PLAYCRAFT_HISTORY:-$GITCRAFT_HOME/playcraft/history}"
# PIXELCRAFT's audit history (every app's visual-quality runs; never rewritten)
GITCRAFT_PIXELCRAFT_HISTORY="${GITCRAFT_PIXELCRAFT_HISTORY:-$GITCRAFT_HOME/pixelcraft/history}"
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

# Folder the tools may read from and write to: the workspace (the project Claude Code opened, else the current
# folder), never the home folder. A workspace that is $HOME, contains it, or is / falls back to ~/gitcraft-work.
# (Until November 2026 the default was $HOME, which made ~/.claude, ~/.ssh and shell start-up files writable from
# inside the sandbox.) scripts/mcp.sh refuses any root that would expose such control files (gitcraft3d/policy.py).
if [[ -z "${GITCRAFT_ROOT:-}" ]]; then
  _gc_ws="$(cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null && pwd -P)"
  _gc_h="$(cd "$HOME" 2>/dev/null && pwd -P)"
  case "$_gc_h/" in "$_gc_ws"/*) _gc_ws="" ;; esac   # the workspace is $HOME, or a folder that contains it
  [[ "$_gc_ws" == / ]] && _gc_ws=""
  GITCRAFT_ROOT="${_gc_ws:-$HOME/gitcraft-work}"
  unset _gc_ws _gc_h
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

# MeshCraft's engine check (three@0.170, gltf-validator) is installed into $GITCRAFT_HOME/meshcraft/engine_check, outside
# the runtime: every runtime update is a fresh copy of a checkout without node_modules (meshcraft/engine/nodemods.py).
# Ready when that copy was installed from this lockfile (gitcraft_engine_check_ready <repo>).
gitcraft_engine_check_ready() {
  local ec="$GITCRAFT_HOME/meshcraft/engine_check"
  [[ -f "$ec/node_modules/three/package.json" && -f "$ec/node_modules/gltf-validator/package.json" ]] || return 1
  cmp -s "$ec/.installed-lock" "$1/meshcraft/engine_check/package-lock.json"   # written only after npm ci succeeded
}

# StudioCraft counts as installed when its core venv has numpy (checked from metadata, no import).
gitcraft_studio_ready() {
  [[ -x "$GITCRAFT_STUDIO_HOME/venv/bin/python" ]] || return 1
  compgen -G "$GITCRAFT_STUDIO_HOME/venv/lib/python*/site-packages/numpy-*.dist-info" >/dev/null
}

# Is an extra tool ready to register? (ArtCraft tools: their binary exists.)
gitcraft_extra_ready() {
  case "$1" in
    meshcraft|forgecraft) gitcraft_mesh_ready ;;
    studiocraft) gitcraft_studio_ready ;;
    *) return 1 ;;
  esac
}
