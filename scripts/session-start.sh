#!/usr/bin/env bash
# SessionStart hook. Fast: registers whatever is built, and if anything is
# missing kicks off the build in the background instead of blocking the session.
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

"$here/install-global.sh" >/dev/null 2>&1   # keeps ~/.gitcraft/runtime, user-scope registration and global instructions current

if ((${#missing[@]} == 0)); then
  "$here/doctor.sh" --brief
  exit 0
fi

if pgrep -f "gitcraft/scripts/install.sh" >/dev/null; then
  echo "GITCRAFT: build already running (log: $GITCRAFT_LOG/install.log)."
else
  setsid nohup "$here/install.sh" "${missing[@]}" >"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  echo "GITCRAFT: building ${missing[*]} in the background (log: $GITCRAFT_LOG/install.log)."
fi
echo "GITCRAFT: tools not built yet won't connect until the build finishes; run /mcp to reconnect after."
