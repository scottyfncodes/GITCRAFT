#!/usr/bin/env bash
# Start one ArtCraft MCP server on stdio, headless, fenced to $GITCRAFT_ROOT.
#   scripts/mcp.sh photocraft
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"

name="${1:?usage: mcp.sh <tool>}"
shift
pkg=""
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r n _ p <<<"$entry"
  [[ "$n" == "$name" ]] && pkg="$p"
done
[[ -n "$pkg" ]] || { echo "gitcraft: unknown tool '$name'" >&2; exit 2; }

bin="$GITCRAFT_BIN/$pkg"
if [[ ! -x "$bin" ]]; then
  echo "gitcraft: $pkg isn't built yet. Run scripts/install.sh $name (or check ~/.gitcraft/logs)." >&2
  exit 1
fi

root="$GITCRAFT_ROOT"
mkdir -p "$root"
roots=(--automation-read-root "$root" --automation-write-root "$root")

case "$name" in
  photocraft)  exec "$bin" mcp "${roots[@]}" "$@" ;;
  vectorcraft) exec "$bin" mcp --headless "${roots[@]}" "$@" ;;
  designcraft) exec "$bin" mcp "${roots[@]}" "$@" ;;
  effectcraft) exec "$bin" mcp "${roots[@]}" "$@" ;;
  pdfcraft)    exec "$bin" mcp --root "$root" "${roots[@]}" "$@" ;;
  # These two don't support file roots; they run as a headless session.
  filmcraft)   exec "$bin" mcp "$@" ;;
  lightcraft)  exec "$bin" mcp --library "$GITCRAFT_HOME/lightcraft-library" "$@" ;;
esac
