#!/usr/bin/env bash
# One-step GITCRAFT setup for a fresh Claude Code environment: every tool, available in every project.
#
# Cloud: paste this line into the environment's *Setup script* (cloud environment menu ▸ Edit ▸
# Setup script). It runs whenever a new container is built, before Claude Code starts, so every
# session in that environment has the tools, whichever repos are attached (none needed):
#
#   curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
#
# Workstation: run the same line once; ~/.claude.json and ~/.claude persist, so every later
# session in every project inherits it. Re-run it to update.
#
# What it does: clones GITCRAFT to ~/.gitcraft/repo, installs the seven ArtCraft tools
# (prebuilt), the Studio departments (StudioCraft), MeshCraft (Blender bpy) and ForgeCraft, copies the
# launcher and tool code to ~/.gitcraft/runtime, registers all ten MCP servers at user scope from that runtime,
# installs the GITCRAFT instruction block in ~/.claude/CLAUDE.md and the `gitcraft` skill,
# then prints a health check.
#
#   GITCRAFT_REF=<branch|tag>         install that ref instead of the default branch
#   GITCRAFT_REPO_URL=<url|path>      install from a fork or local clone
#   GITCRAFT_GLOBAL_INSTRUCTIONS=0    skip the CLAUDE.md block and the skill
#   GITCRAFT_MESHCRAFT=0              skip the 3D tools (Blender is ~400 MB)
#   GITCRAFT_STUDIO=0                 skip the Studio departments
#   GITCRAFT_STUDIO_VOICE=later|0     voice model in the background at the first session / not at all
#   extra arguments go to install.sh  (e.g. --update, or tool names)
set -uo pipefail
repo_url="${GITCRAFT_REPO_URL:-https://github.com/scottyfncodes/GITCRAFT}"
home="${GITCRAFT_HOME:-$HOME/.gitcraft}"
dest="$home/repo"
ref="${GITCRAFT_REF:-}"
mkdir -p "$home/logs"
if [[ -d "$dest/.git" ]]; then
  if [[ -n "$ref" ]]; then git -C "$dest" fetch -q --depth 1 origin "$ref" && git -C "$dest" checkout -q -B "$ref" FETCH_HEAD
  else git -C "$dest" pull -q --ff-only; fi || echo "gitcraft: couldn't update $dest; using the copy on disk" >&2
else
  git clone -q --depth 1 ${ref:+--branch "$ref"} "$repo_url" "$dest" || { echo "gitcraft: clone of $repo_url failed" >&2; exit 1; }
fi
"$dest/scripts/install.sh" "$@" 2>&1 | tee "$home/logs/install.log"
status=${PIPESTATUS[0]}
"$home/runtime/scripts/doctor.sh" --brief 2>/dev/null || "$dest/scripts/doctor.sh" --brief || true
exit "$status"
