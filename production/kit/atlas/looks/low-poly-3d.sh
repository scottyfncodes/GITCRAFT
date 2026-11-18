#!/usr/bin/env bash
# Render one atlas scene in the Low-Poly 3D look with MeshCraft (GITCRAFT's headless Blender), through MeshCraft's
# own sandboxed launcher (scripts/mcp.sh: guard + Landlock, no network), exactly as the MCP tool run_script does.
#
#   looks/low-poly-3d.sh <scene.json> <out_dir> [samples=48] [scale=1.0]
#   -> <out_dir>/game3d.png (1920x1080), <out_dir>/hero3d.png (800x800, transparent), <out_dir>/render3d.json
#
# The look module reads looks/_renders/<scene title slug>/ by default (e.g. rooftop-run, kite-line), or the stage
# URL's ?render3d= / ?hero3d= parameters. From an MCP client: meshcraft run_script with
#   {"path": "<atlas>/looks/low-poly-3d.py", "args": {"scene": "<scene.json>", "out": "<out_dir>", "samples": 48}}
set -euo pipefail
scene="$(realpath "${1:?usage: low-poly-3d.sh <scene.json> <out_dir> [samples] [scale]}")"
mkdir -p "${2:?out_dir}"; out="$(realpath "$2")"
samples="${3:-48}"; scale="${4:-1.0}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
gc="${GITCRAFT_HOME:-$HOME/.gitcraft}"
launcher="$gc/runtime/scripts/mcp.sh"; [[ -x "$launcher" ]] || launcher="$(cd "$here/../../../.." && pwd)/scripts/mcp.sh"
# MeshCraft may read and write only its roots: the script, the scene and the output folder
roots=$(printf '%s\n' "$here" "$(dirname "$scene")" "$out" | sort -u | paste -sd: -)
argf="$(mktemp "$out/.lp3d-args.XXXXXX.json")"; trap 'rm -f "$argf"' EXIT
printf '{"path": "%s", "args": {"scene": "%s", "out": "%s", "samples": %d, "scale": %s}}\n' \
  "$here/low-poly-3d.py" "$scene" "$out" "$samples" "$scale" > "$argf"
GITCRAFT_ROOTS="$roots" GITCRAFT_ROOT="${roots%%:*}" "$launcher" meshcraft --call run_script "@$argf" </dev/null | tail -n 1
