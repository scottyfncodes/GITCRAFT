#!/usr/bin/env bash
# Register every built ArtCraft tool with Claude Code at user scope, so the
# tools are available no matter which repo the session is working in.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"

if ! command -v claude >/dev/null; then
  echo "gitcraft: claude CLI not found; add them yourself with: claude mcp add <name> -- $here/mcp.sh <name>"
  exit 0
fi

for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  [[ -x "$GITCRAFT_BIN/$pkg" ]] || continue
  claude mcp remove -s user "$name" >/dev/null 2>&1
  if claude mcp add -s user "$name" -- "$here/mcp.sh" "$name" >/dev/null 2>&1; then
    echo "gitcraft: registered $name"
  else
    echo "gitcraft: couldn't register $name" >&2
  fi
done
