#!/usr/bin/env bash
# Install GITCRAFT before a Claude Code session starts.
#
# Paste this into the cloud environment's *setup script* (environment settings ▸
# Setup script), or run it once on a workstation:
#
#   curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
#
# Why: a repo's SessionStart hook only runs when that repo is the session's
# working folder (never in multi-repo sessions), and MCP servers registered
# after a session starts don't connect until /mcp or a new session. Running
# here, before the session, means every tool is installed and registered from a
# stable location (~/.gitcraft/repo) no matter which repos are attached.
set -uo pipefail
repo_url="${GITCRAFT_REPO_URL:-https://github.com/scottyfncodes/GITCRAFT}"
home="${GITCRAFT_HOME:-$HOME/.gitcraft}"
dest="$home/repo"
mkdir -p "$home/logs"
if [[ -d "$dest/.git" ]]; then
  git -C "$dest" pull -q --ff-only || echo "gitcraft: couldn't update $dest; using the copy on disk" >&2
else
  git clone -q --depth 1 "$repo_url" "$dest" || { echo "gitcraft: clone of $repo_url failed" >&2; exit 1; }
fi
"$dest/scripts/install.sh" "$@" 2>&1 | tee "$home/logs/install.log"
status=${PIPESTATUS[0]}
"$dest/scripts/doctor.sh" --brief || true
exit "$status"
