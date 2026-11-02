#!/usr/bin/env bash
# GITCRAFT control room: a local web UI for every GITCRAFT tool.
#   scripts/ui.sh [--port 8765]        serve on 127.0.0.1; prints a one-time link (with its token)
#   scripts/ui.sh --snapshot DIR       write a read-only snapshot (real data, actions disabled)
# Every action runs through scripts/mcp.sh, so the guard and the Landlock sandbox apply as usual.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"
export GITCRAFT_HOME GITCRAFT_ROOT GITCRAFT_ROOTS GITCRAFT_SANDBOX GITCRAFT_ALLOW_NET
exec python3 "$here/../ui/server.py" "$@"
