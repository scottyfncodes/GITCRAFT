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

# Studio: finish a core install that was cut off ("pending"/"failed" and not complete), and install a voice model
# that setup deferred (GITCRAFT_STUDIO_VOICE=later) or didn't finish. A deferred voice model reaches the running
# studiocraft server on its next call (its dependency checks only cache what was found).
studio_last=$(python3 -c 'import json,os,sys;t=json.load(open(os.path.join(sys.argv[1],"status.json"))).get("tools",{});print(t.get("studiocraft",{}).get("state",""), t.get("studiocraft-voice",{}).get("state",""))' "$GITCRAFT_HOME" 2>/dev/null)
read -r studio_last voice_last <<<"$studio_last"
studio_voice=0
if [[ "$GITCRAFT_STUDIO" == 1 ]]; then
  if [[ "$studio_last" == pending || "$studio_last" == failed ]] && ! gitcraft_studio_ready; then missing+=(studiocraft); fi
  if [[ "$voice_last" == later || "$voice_last" == pending ]] && [[ ! -f "$GITCRAFT_STUDIO_HOME/models/kokoro/voices-v1.0.bin" ]]; then
    [[ " ${missing[*]} " == *" studiocraft "* ]] || missing+=(studiocraft); studio_voice=1
  fi
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
  # likewise a deferred voice model is installed now, not deferred again
  [[ $studio_voice == 1 || " ${missing[*]} " == *" studiocraft "* ]] && export GITCRAFT_STUDIO_VOICE=$([[ "$GITCRAFT_STUDIO_VOICE" == 0 ]] && echo 0 || echo 1)
  if command -v flock >/dev/null; then
    setsid nohup flock -n "$lock" "$here/install.sh" "${missing[@]}" >>"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  else
    setsid nohup "$here/install.sh" "${missing[@]}" >>"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  fi
  echo "GITCRAFT: building ${missing[*]} in the background (log: $GITCRAFT_LOG/install.log)."
fi
echo "GITCRAFT: MeshCraft and ForgeCraft announce their tools when their build finishes; a deferred voice model is picked up by studiocraft on its next call; other tools need /mcp."
