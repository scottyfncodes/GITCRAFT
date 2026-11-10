#!/usr/bin/env bash
# Queue a heavy optional install for the next session instead of running it in a cloud setup script.
#
#   scripts/install-later.sh install-3d.sh ai weights      TripoSR + PyTorch venv and weights (~8 min, ~5 GB)
#   scripts/install-later.sh install-studio.sh music       ACE-Step 1.5 (large; does not fit a setup script's time limit)
#   scripts/install-later.sh --list                        what is queued
#
# A setup script that runs past its time limit is stopped mid-step (a fresh container was stopped ~17 min in, during
# `install-studio.sh music`), and anything after that step never runs. Queued here, the step returns at once; the
# SessionStart hook (scripts/session-start.sh) then runs the queue in the background inside the session, one job at
# a time, after Blender. A job leaves the queue when it succeeds; a failed one is retried by later sessions, at most
# GITCRAFT_LATER_TRIES (3) times. Both install scripts skip what is already installed, so re-running one is cheap.
# Only install-3d.sh and install-studio.sh can be queued.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"
q="$GITCRAFT_HOME/later"
mkdir -p "$q"

if [[ "${1:-}" == --list ]]; then
  for f in "$q"/*.job; do [[ -e "$f" ]] && echo "$(basename "$f" .job): $(cat "$f")"; done; exit 0
fi
script="${1:-}"; shift || true
case "$script" in install-3d.sh|install-studio.sh) ;; *) echo "usage: install-later.sh install-3d.sh|install-studio.sh <components...>" >&2; exit 2 ;; esac
(($#)) || { echo "install-later.sh: name the components to install (e.g. ai weights)" >&2; exit 2; }
for c in "$@"; do [[ "$c" =~ ^[a-z0-9-]+$ ]] || { echo "install-later.sh: bad component '$c'" >&2; exit 2; }; done

name="${script%.sh}-$(IFS=-; echo "$*")"
echo "$script $*" > "$q/$name.job"
: > "$q/$name.tries"   # a fresh queue entry starts its attempt count again
echo "gitcraft: queued $script $* for the SessionStart hook (log: $GITCRAFT_LOG/later.log)"
