#!/usr/bin/env bash
# Shared tool list for GITCRAFT. Sourced by the other scripts.
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

GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
GITCRAFT_BIN="$GITCRAFT_HOME/bin"
GITCRAFT_SRC="$GITCRAFT_HOME/src"
GITCRAFT_TARGET="$GITCRAFT_HOME/target"
GITCRAFT_LOG="$GITCRAFT_HOME/logs"
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
