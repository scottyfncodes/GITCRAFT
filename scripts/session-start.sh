#!/usr/bin/env bash
# SessionStart hook. Fast: registers whatever is built, and if anything is
# missing kicks off the build in the background instead of blocking the session.
#   session-start.sh            the repo's hook (.claude/settings.json, when GITCRAFT is the project)
#   session-start.sh --global   the user-level hook install-global.sh adds (every project): only starts a
#                               background build when something is missing, and is silent otherwise
global=0; [[ "${1:-}" == --global ]] && global=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"
mkdir -p "$GITCRAFT_LOG"

missing=()
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  [[ -x "$GITCRAFT_BIN/$pkg" ]] || missing+=("$name")
done
# 3D: finish a Blender install the setup deferred (GITCRAFT_MESHCRAFT=later) or that was cut off (still "pending").
# The servers are already registered and pick the tools up as soon as it lands (gitcraft3d/deferred.py).
mesh_last=$(python3 -c 'import json,os,sys;print(json.load(open(os.path.join(sys.argv[1],"status.json"))).get("tools",{}).get("meshcraft",{}).get("state",""))' "$GITCRAFT_HOME" 2>/dev/null)
if [[ "$GITCRAFT_MESHCRAFT" != none && ( "$mesh_last" == later || "$mesh_last" == pending ) ]] && ! gitcraft_mesh_ready; then
  missing+=(meshcraft forgecraft)
fi

((global)) || "$here/install-global.sh" >/dev/null 2>&1   # keeps ~/.gitcraft/runtime, user-scope registration and global instructions current

if ((${#missing[@]} == 0)); then
  ((global)) || "$here/doctor.sh" --brief
  exit 0
fi

# one background build at a time, whichever hook (project or global) gets here first
lock="$GITCRAFT_HOME/install.lock"
if command -v flock >/dev/null && ! flock -n "$lock" true; then
  echo "GITCRAFT: build already running (log: $GITCRAFT_LOG/install.log)."
elif pgrep -f "gitcraft/(runtime/)?scripts/install.sh" >/dev/null || pgrep -f "\.gitcraft/runtime/scripts/install.sh" >/dev/null; then
  echo "GITCRAFT: build already running (log: $GITCRAFT_LOG/install.log)."
else
  { echo "gitcraft: background build started $(date -u +%FT%TZ) by the $( ((global)) && echo "global " )SessionStart hook: ${missing[*]}"; } >"$GITCRAFT_LOG/install.log"
  # this hook's job is to install: a session-wide GITCRAFT_MESHCRAFT=later/0 must not make install.sh skip Blender again
  export GITCRAFT_MESHCRAFT=$([[ "$GITCRAFT_MESHCRAFT" == none ]] && echo none || echo 1)
  if command -v flock >/dev/null; then
    setsid nohup flock -n "$lock" "$here/install.sh" "${missing[@]}" >>"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  else
    setsid nohup "$here/install.sh" "${missing[@]}" >>"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  fi
  echo "GITCRAFT: building ${missing[*]} in the background (log: $GITCRAFT_LOG/install.log)."
fi
echo "GITCRAFT: MeshCraft and ForgeCraft announce their tools when their build finishes; other tools need /mcp."
