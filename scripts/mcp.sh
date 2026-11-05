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
[[ "$name" == meshcraft || "$name" == forgecraft || "$name" == studiocraft ]] && pkg="$name"
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r n _ p <<<"$entry"
  [[ "$n" == "$name" ]] && pkg="$p"
done
[[ -n "$pkg" ]] || { echo "gitcraft: unknown tool '$name'" >&2; exit 2; }

bin="$GITCRAFT_BIN/$pkg"
# MeshCraft runs on its Blender venv's Python. Before Blender is installed it starts on the system Python, answers
# the handshake and waits for the install (gitcraft3d/deferred.py), so a session that began first still gets it.
# ForgeCraft always runs on the system Python and drives MeshCraft's Blender per job.
if [[ "$name" == meshcraft ]]; then
  if gitcraft_mesh_ready; then bin="$GITCRAFT_HOME/meshcraft/venv/bin/python"; else bin="$(command -v python3)"; fi
elif [[ "$name" == forgecraft ]]; then bin="$(command -v python3)"; fi
# StudioCraft runs on its venv; before that exists it starts on the system Python, lists a status tool and announces
# its department tools when the install lands (studio/server.py), so a session that began first still gets them.
if [[ "$name" == studiocraft ]]; then
  if gitcraft_studio_ready; then bin="$GITCRAFT_STUDIO_HOME/venv/bin/python"; else bin="$(command -v python3)"; fi
fi
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
# LightCraft locks its library to one process; GITCRAFT_LIGHTCRAFT_LIBRARY lets tests use their own.
lc_library="${GITCRAFT_LIGHTCRAFT_LIBRARY:-$GITCRAFT_HOME/lightcraft-library}"
# Another session (e.g. one in a different project) holding the shared library would stop this one
# from starting; in that case this project gets its own library instead of failing.
if [[ "$name" == lightcraft && -z "${GITCRAFT_LIGHTCRAFT_LIBRARY:-}" && -e "$lc_library/catalog.lock" ]] &&
   ! python3 -c 'import fcntl,sys; fcntl.flock(open(sys.argv[1]), fcntl.LOCK_EX | fcntl.LOCK_NB)' "$lc_library/catalog.lock" 2>/dev/null; then
  lc_library="$GITCRAFT_HOME/lightcraft-libraries/$(basename "$root")-$(printf %s "$root" | sha256sum | cut -c1-8)"
  echo "gitcraft: the shared LightCraft library is open in another session; using $lc_library for this project" >&2
fi
# The 3D library ($GITCRAFT_3D_LIBRARY, from tools.sh) is shared by meshcraft and forgecraft, outside the workspace like LightCraft's
case "$name" in
  photocraft)  cmd=("$bin" mcp "${native[@]}") ;;
  vectorcraft) cmd=("$bin" mcp --headless "${native[@]}") ;;
  designcraft) cmd=("$bin" mcp "${native[@]}") ;;
  effectcraft) cmd=("$bin" mcp "${native[@]}") ;;
  pdfcraft)    cmd=("$bin" mcp --compact --root "$root" "${native[@]}") ;;
  # These two have no file-root flags of their own; the sandbox is their fence.
  filmcraft)   cmd=("$bin" mcp) ;;
  lightcraft)  mkdir -p "$lc_library"
               cmd=("$bin" mcp --compact --library "$lc_library") ;;
  # Blender in-process; enforces the roots itself as well as through the sandbox below.
  meshcraft)   mkdir -p "$GITCRAFT_3D_LIBRARY"; export GITCRAFT_HOME GITCRAFT_ROOTS GITCRAFT_ROOT GITCRAFT_3D_LIBRARY FORGECRAFT_HOME
               cmd=("$bin" "$repo/meshcraft/server.py") ;;
  # The 3D Department pipeline (stdlib Python); spawns Blender, Meshroom and the AI backends as children.
  forgecraft)  mkdir -p "$GITCRAFT_3D_LIBRARY" "$FORGECRAFT_HOME/hf-cache" "$(dirname "$GITCRAFT_ASSET_CATALOG")" "$GITCRAFT_PLAYCRAFT_HISTORY"
               export GITCRAFT_HOME GITCRAFT_ROOTS GITCRAFT_ROOT GITCRAFT_ALLOW_NET FORGECRAFT_HOME GITCRAFT_3D_LIBRARY HF_HOME="$FORGECRAFT_HOME/hf-cache" \
                      GITCRAFT_STUDIO_HOME GITCRAFT_ASSET_CATALOG GITCRAFT_PLAYCRAFT_HISTORY
               # HOME inside the sandbox is the tool's state folder (Chromium and Blender write caches there)
               cmd=(env HOME="$state/data" python3 "$repo/forgecraft/server.py") ;;
  # The Studio departments (studio/): Python in the studio venv; spawns Blender (MeshCraft's), Node/Chromium,
  # FFmpeg and the voice venv as children, all inside this sandbox.
  studiocraft) mkdir -p "$GITCRAFT_3D_LIBRARY" "$(dirname "$GITCRAFT_ASSET_CATALOG")" "$GITCRAFT_PLAYCRAFT_HISTORY"
               export GITCRAFT_HOME GITCRAFT_ROOTS GITCRAFT_ROOT GITCRAFT_STUDIO_HOME GITCRAFT_ASSET_CATALOG GITCRAFT_3D_LIBRARY GITCRAFT_PLAYCRAFT_HISTORY
               cmd=(env HOME="$state/data" "$bin" "$repo/studio/server.py") ;;
esac
# the tools with repeatable native roots also get the extra roots
case "$name" in vectorcraft|designcraft|effectcraft)
  for r in "${roots[@]:1}"; do cmd+=(--automation-read-root "$r" --automation-write-root "$r"); done ;;
esac
cmd+=("$@")

writable=("${roots[@]}" "$state")
[[ "$name" == lightcraft ]] && writable+=("$lc_library")
[[ "$name" == meshcraft ]] && writable+=("$GITCRAFT_3D_LIBRARY")
[[ "$name" == forgecraft ]] && writable+=("$GITCRAFT_3D_LIBRARY" "$FORGECRAFT_HOME/hf-cache" "$(dirname "$GITCRAFT_ASSET_CATALOG")" "$GITCRAFT_PLAYCRAFT_HISTORY")
[[ "$name" == studiocraft ]] && writable+=("$GITCRAFT_3D_LIBRARY" "$(dirname "$GITCRAFT_ASSET_CATALOG")" "$GITCRAFT_PLAYCRAFT_HISTORY")
# Landlock can only fence paths that exist when the sandbox starts (sandbox.py skips a missing one). The 3D servers
# may start before Blender is installed, so create its folder now: the install fills it in later and the running
# server can then read and run it (gitcraft3d/deferred.py).
[[ "$name" == meshcraft || "$name" == forgecraft ]] && mkdir -p "$GITCRAFT_HOME/meshcraft" "$FORGECRAFT_HOME"
[[ "$name" == studiocraft ]] && mkdir -p "$GITCRAFT_STUDIO_HOME" "$GITCRAFT_HOME/meshcraft"   # same: fenced before the install fills them
if [[ "$GITCRAFT_SANDBOX" != off ]]; then
  policy=()
  for d in /usr /lib /lib64 /lib32 /bin /sbin /opt "$GITCRAFT_BIN"; do policy+=(--rx "$d"); done
  # meshcraft: its code + Blender venv + the shared 3D code; ForgeCraft's runtimes only to probe them (hardware_probe)
  [[ "$name" == meshcraft ]] && policy+=(--rx "$GITCRAFT_HOME/meshcraft" --rx "$repo/meshcraft" --rx "$repo/gitcraft3d" --rx "$FORGECRAFT_HOME")
  # forgecraft: its code + generators, and MeshCraft (code + Blender), which it runs as a child for all Blender work
  [[ "$name" == forgecraft ]] && policy+=(--rx "$repo/forgecraft" --rx "$repo/gitcraft3d" --rx "$FORGECRAFT_HOME" --rx "$GITCRAFT_HOME/meshcraft" --rx "$repo/meshcraft"
                                          --rx "$repo/studio" --rx "$GITCRAFT_STUDIO_HOME")   # department_* tools run the Studio
  # studiocraft: its code + runtimes (venvs, voice models, Node packages) + MeshCraft's Blender for its Blender actions
  [[ "$name" == studiocraft ]] && policy+=(--rx "$repo/studio" --rx "$GITCRAFT_STUDIO_HOME" --rx "$GITCRAFT_HOME/meshcraft")
  # the committed Game Quality History (PLAYCRAFT imports it into its store): read-only, runs never write it
  [[ ( "$name" == studiocraft || "$name" == forgecraft ) && -d "$repo/history" ]] && policy+=(--ro "$repo/history")
  for d in /etc /proc /sys /var/cache/fontconfig /usr/share/fonts "$HOME/.local/share/fonts" "$HOME/.fonts"; do policy+=(--ro "$d"); done
  policy+=(--rw /dev)
  for d in "${writable[@]}"; do policy+=(--rw "$d"); done
  [[ "$GITCRAFT_ALLOW_NET" == 1 ]] || policy+=(--no-net)
  # Per-host allowances (scripts/netgate.py): GITCRAFT_ALLOW_HOSTS_<TOOL>, else GITCRAFT_ALLOW_HOSTS, else the
  # ~/.gitcraft/allow-hosts file (one pattern per line, `tool: pattern` for one tool). Landlock then allows TCP to
  # the local netgate port only, and netgate lets through only those hosts (HTTPS, port 443), logged in net.jsonl.
  allow_var="GITCRAFT_ALLOW_HOSTS_${name^^}"; allow_hosts="${!allow_var:-${GITCRAFT_ALLOW_HOSTS:-}}"
  if [[ -z "$allow_hosts" && -f "$GITCRAFT_HOME/allow-hosts" ]]; then
    allow_hosts=$(sed -e 's/#.*//' "$GITCRAFT_HOME/allow-hosts" | awk -v t="$name" 'NF==0{next} /:/{split($0,a,":"); gsub(/ /,"",a[1]); if (a[1]==t) {gsub(/ /,"",a[2]); print a[2]}; next} {gsub(/ /,""); print}' | paste -sd, -)
  fi
  if [[ -n "$allow_hosts" && "$GITCRAFT_ALLOW_NET" != 1 ]]; then
    pf="$state/netgate.port"; rm -f "$pf"
    NETGATE_UPSTREAM="${HTTPS_PROXY:-${https_proxy:-}}" GITCRAFT_HOME="$GITCRAFT_HOME" \
      python3 "$here/netgate.py" --allow "$allow_hosts" --tool "$name" --parent $$ --port-file "$pf" </dev/null >/dev/null 2>>"$GITCRAFT_LOG/netgate.log" &
    for _ in $(seq 50); do [[ -s "$pf" ]] && break; sleep 0.1; done
    if [[ -s "$pf" ]]; then
      gate="http://127.0.0.1:$(cat "$pf")"; policy+=(--allow-connect "$(cat "$pf")")
      export HTTPS_PROXY="$gate" https_proxy="$gate" HTTP_PROXY="$gate" http_proxy="$gate" ALL_PROXY="$gate" NO_PROXY="" no_proxy=""
      export GITCRAFT_NETGATE="$allow_hosts"
    else
      echo "gitcraft: netgate did not start (see $GITCRAFT_LOG/netgate.log); $name runs with no network" >&2
    fi
  fi
  [[ "$GITCRAFT_SANDBOX" == require ]] && policy+=(--require)
  cmd=(python3 "$here/sandbox.py" "${policy[@]}" -- "${cmd[@]}")
fi

guard=(--tool "$name")
for d in "${writable[@]}"; do guard+=(--root "$d"); done
for t in $(gitcraft_denied "$name"); do guard+=(--deny "$t"); done
exec python3 "$here/guard.py" "${guard[@]}" -- "${cmd[@]}"
