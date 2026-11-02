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
# Folder the tools may read from and write to. Defaults to the whole session home.
GITCRAFT_ROOT="${GITCRAFT_ROOT:-$HOME}"
