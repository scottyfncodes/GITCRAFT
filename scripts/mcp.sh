#!/usr/bin/env bash
# Start one GITCRAFT MCP server on stdio, headless, behind the central policy:
#
#   Claude Code ⇄ guard.py (path checks, deny list, audit log)
#             ⇄ sandbox.py (Landlock: only the workspace roots + the tool's own state are writable,
#                           no other files readable outside system dirs, no network)
#             ⇄ the tool's own MCP server (with its native file roots where it has them)
#
#   scripts/mcp.sh photocraft
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"

name="${1:?usage: mcp.sh <tool>}"
shift
repo="$(dirname "$here")"
pkg=""
[[ "$name" == meshcraft || "$name" == forgecraft ]] && pkg="$name"
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r n _ p <<<"$entry"
  [[ "$n" == "$name" ]] && pkg="$p"
done
[[ -n "$pkg" ]] || { echo "gitcraft: unknown tool '$name'" >&2; exit 2; }

bin="$GITCRAFT_BIN/$pkg"
[[ "$name" == meshcraft || "$name" == forgecraft ]] && bin="$GITCRAFT_HOME/meshcraft/venv/bin/python"   # ForgeCraft drives MeshCraft's Blender
if [[ ! -x "$bin" ]]; then
  echo "gitcraft: $pkg isn't built yet. Run scripts/install.sh $name (or check ~/.gitcraft/logs)." >&2
  exit 1
fi

IFS=: read -r -a roots <<<"$GITCRAFT_ROOTS"
root="$GITCRAFT_ROOT"
mkdir -p "$root" "$GITCRAFT_LOG"
state="$GITCRAFT_STATE/$name"
mkdir -p "$state/tmp" "$state/config" "$state/cache" "$state/data"
export TMPDIR="$state/tmp" XDG_CONFIG_HOME="$state/config" XDG_CACHE_HOME="$state/cache" XDG_DATA_HOME="$state/data"
# XDG_DATA_HOME moved, so point the tool's user-font folder back at the real one (read-only in the sandbox);
# without this, tools silently fall back to default fonts.
for fd in "$HOME/.local/share/fonts" "$HOME/.fonts"; do
  [[ -d "$fd" ]] && { ln -sfn "$fd" "$state/data/fonts"; break; }
done

native=(--automation-read-root "$root" --automation-write-root "$root")
case "$name" in
  photocraft)  cmd=("$bin" mcp "${native[@]}") ;;
  vectorcraft) cmd=("$bin" mcp --headless "${native[@]}") ;;
  designcraft) cmd=("$bin" mcp "${native[@]}") ;;
  effectcraft) cmd=("$bin" mcp "${native[@]}") ;;
  pdfcraft)    cmd=("$bin" mcp --compact --root "$root" "${native[@]}") ;;
  # These two have no file-root flags of their own; the sandbox is their fence.
  filmcraft)   cmd=("$bin" mcp) ;;
  lightcraft)  mkdir -p "$GITCRAFT_HOME/lightcraft-library"
               cmd=("$bin" mcp --compact --library "$GITCRAFT_HOME/lightcraft-library") ;;
  # Blender in-process; enforces the roots itself as well as through the sandbox below.
  meshcraft)   export GITCRAFT_ROOTS GITCRAFT_ROOT
               cmd=("$bin" "$repo/meshcraft/server.py") ;;
  # The 3D Department pipeline (stdlib Python); spawns Blender, Meshroom and the AI backends as children.
  forgecraft)  mkdir -p "$FORGECRAFT_LIBRARY" "$FORGECRAFT_HOME/hf-cache"
               export GITCRAFT_HOME GITCRAFT_ROOTS GITCRAFT_ROOT GITCRAFT_ALLOW_NET FORGECRAFT_HOME FORGECRAFT_LIBRARY HF_HOME="$FORGECRAFT_HOME/hf-cache"
               # HOME inside the sandbox is the tool's state folder (Chromium and Blender write caches there)
               cmd=(env HOME="$state/data" python3 "$repo/forgecraft/server.py") ;;
esac
# the tools with repeatable native roots also get the extra roots
case "$name" in vectorcraft|designcraft|effectcraft)
  for r in "${roots[@]:1}"; do cmd+=(--automation-read-root "$r" --automation-write-root "$r"); done ;;
esac
cmd+=("$@")

writable=("${roots[@]}" "$state")
[[ "$name" == lightcraft ]] && writable+=("$GITCRAFT_HOME/lightcraft-library")
[[ "$name" == forgecraft ]] && writable+=("$FORGECRAFT_LIBRARY" "$FORGECRAFT_HOME/hf-cache")
if [[ "$GITCRAFT_SANDBOX" != off ]]; then
  policy=()
  for d in /usr /lib /lib64 /lib32 /bin /sbin /opt "$GITCRAFT_BIN"; do policy+=(--rx "$d"); done
  [[ "$name" == meshcraft ]] && policy+=(--rx "$GITCRAFT_HOME/meshcraft" --rx "$repo/meshcraft")
  [[ "$name" == forgecraft ]] && policy+=(--rx "$repo/forgecraft" --rx "$FORGECRAFT_HOME" --rx "$GITCRAFT_HOME/meshcraft" --rx "$repo/meshcraft")
  for d in /etc /proc /sys /var/cache/fontconfig /usr/share/fonts "$HOME/.local/share/fonts" "$HOME/.fonts"; do policy+=(--ro "$d"); done
  policy+=(--rw /dev)
  for d in "${writable[@]}"; do policy+=(--rw "$d"); done
  [[ "$GITCRAFT_ALLOW_NET" == 1 ]] || policy+=(--no-net)
  [[ "$GITCRAFT_SANDBOX" == require ]] && policy+=(--require)
  cmd=(python3 "$here/sandbox.py" "${policy[@]}" -- "${cmd[@]}")
fi

guard=(--tool "$name")
for d in "${writable[@]}"; do guard+=(--root "$d"); done
for t in $(gitcraft_denied "$name"); do guard+=(--deny "$t"); done
exec python3 "$here/guard.py" "${guard[@]}" -- "${cmd[@]}"
