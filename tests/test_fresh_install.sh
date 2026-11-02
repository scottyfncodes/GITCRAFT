#!/usr/bin/env bash
# Fresh-session install test for the 3D Department: an empty HOME (so an empty ~/.gitcraft and
# ~/.claude.json), then exactly what a new session's setup does: install.sh meshcraft forgecraft,
# registration, doctor, and a real job through both sandboxed MCP servers.
#
#   tests/test_fresh_install.sh [workdir]       (~3 min with a warm pip/uv cache; downloads bpy otherwise)
#
# The package caches of the real HOME are reused so the bpy wheel is not downloaded twice.
set -uo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="${1:-$(mktemp -d "${TMPDIR:-/tmp}/gitcraft-fresh-XXXX")}"
real_home="$HOME"
pass=0 fail=0
check() { if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }

export HOME="$work/home" GITCRAFT_ROOT="$work/ws" GITCRAFT_ROOTS="$work/ws"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$real_home/.cache/pip}" UV_CACHE_DIR="${UV_CACHE_DIR:-$real_home/.cache/uv}"
export PATH="$real_home/.local/bin:$PATH"
unset GITCRAFT_HOME GITCRAFT_3D_LIBRARY GITCRAFT_MESHCRAFT_LIBRARY FORGECRAFT_LIBRARY FORGECRAFT_HOME FORGECRAFT_BLENDER_PY
rm -rf "$work/home" "$work/ws"; mkdir -p "$HOME" "$GITCRAFT_ROOT"
echo "fresh HOME: $HOME"

check "nothing installed before (empty ~/.gitcraft, no ~/.claude.json)" '[[ ! -e "$HOME/.gitcraft" && ! -e "$HOME/.claude.json" ]]'
"$repo/scripts/install.sh" meshcraft forgecraft >"$work/install.out" 2>&1; rc=$?
check "install.sh meshcraft forgecraft exits 0" '[[ $rc -eq 0 ]]'
check "one Blender: MeshCraft's bpy venv, and nothing Blender-related under ForgeCraft's home" \
  '"$HOME/.gitcraft/meshcraft/venv/bin/python" -c "import bpy" 2>/dev/null && ! find "$HOME/.gitcraft/forgecraft" -name "bpy*" 2>/dev/null | grep -q .'
check "status.json: meshcraft ok, forgecraft ok" \
  'python3 -c "import json,sys; s=json.load(open(\"$HOME/.gitcraft/status.json\")); sys.exit(0 if s[\"tools\"][\"meshcraft\"][\"state\"]==\"ok\" and s[\"tools\"][\"forgecraft\"][\"state\"]==\"ok\" else 1)"'
check "both servers registered at user scope (~/.claude.json)" \
  'python3 -c "import json,sys; c=json.load(open(\"$HOME/.claude.json\")); m=c.get(\"mcpServers\",{}); sys.exit(0 if {\"meshcraft\",\"forgecraft\"}<=set(m) else 1)"'
"$repo/scripts/doctor.sh" >"$work/doctor.out" 2>&1
check "doctor reports the shared 3D library at the new default (~/.gitcraft/3d-library)" 'grep -q "$HOME/.gitcraft/3d-library" "$work/doctor.out"'

python3 - "$repo" "$work" <<'PY'
import json, os, sys
repo, work = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(repo, "tests"))
from mcp_client import Client
mcp = os.path.join(repo, "scripts", "mcp.sh"); res = []
def check(label, ok, detail=""):
    res.append(ok); print(("PASS " if ok else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not ok else ""), flush=True)
lib = os.path.join(os.environ["HOME"], ".gitcraft", "3d-library")
fc = Client([mcp, "forgecraft"], env=dict(os.environ), log=os.path.join(work, "forgecraft.log"))
mc = Client([mcp, "meshcraft"], env=dict(os.environ), log=os.path.join(work, "meshcraft.log"))
ok, p = fc.call("hardware_probe")
check("forgecraft handshake + probe in the fresh install (Blender found via MeshCraft)", ok and p["backends"]["meshcraft"]["available"], p.get("backends", {}).get("meshcraft") if ok else p)
ok, r = fc.call("generate", {"brief": "a wooden crate", "name": "Fresh Crate", "profiles": ["three-web-toon"]}, timeout=1200)
check("first job on a fresh install: ForgeCraft → MeshCraft → engine check → library", ok and r["status"] == "done" and "record:done" in r["stages"]
      and os.path.isdir(os.path.join(lib, "assets", r["asset"]["id"])), r)
ok, g = mc.call("library_get", {"asset": "fresh_crate"})
check("MeshCraft reads the same record from the same library", ok and g["provenance"]["forgecraft_job"] == r.get("job"), g if not ok else "")
fc.close(); mc.close()
sys.exit(0 if all(res) else 1)
PY
rc=$?; check "MCP checks on the fresh install" '[[ $rc -eq 0 ]]'

echo; echo "$pass/$((pass+fail)) checks passed"
[[ $fail -eq 0 ]]
