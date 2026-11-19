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

# Updates (global hook only). By default nothing new is ever run: the hook fetches the clone setup-env.sh made
# (~/.gitcraft/repo) in the background WITHOUT checking anything out, and says when main has moved. A person applies
# an update with ~/.gitcraft/gitcraft-update (scripts/update.sh), which shows the commits and changed files first and installs only with --yes.
# GITCRAFT_AUTO_UPDATE=1 restores the old behaviour (pull, then run the new code unreviewed at session start); it is
# off by default because a compromised main would otherwise execute in every session with the session's credentials.
repo_clone="$GITCRAFT_HOME/repo"
if ((global)) && [[ "${GITCRAFT_AUTO_UPDATE:-0}" != 1 && -d "$repo_clone/.git" ]]; then
  notice="$GITCRAFT_HOME/update-available"
  if [[ -s "$notice" ]]; then echo "GITCRAFT: $(head -c 300 "$notice") Nothing was installed; a person can review and apply it with $GITCRAFT_HOME/gitcraft-update"; fi
  setsid nohup bash -c '
    timeout 60 git -C "$1" fetch -q origin main 2>/dev/null || exit 0
    n=$(git -C "$1" rev-list --count HEAD..FETCH_HEAD 2>/dev/null || echo 0)
    if [[ "$n" -gt 0 ]]; then echo "an update is available: $n new commit(s) on main ($(git -C "$1" rev-parse --short HEAD) -> $(git -C "$1" rev-parse --short FETCH_HEAD))." > "$2"
    else rm -f "$2"; fi
  ' _ "$repo_clone" "$notice" >>"$GITCRAFT_LOG/update.log" 2>&1 < /dev/null &
fi
if ((global)) && [[ "${GITCRAFT_AUTO_UPDATE:-0}" == 1 && -z "${GITCRAFT_UPDATED:-}" && -d "$repo_clone/.git" ]]; then
  setsid nohup bash -c '
    before=$(git -C "$1" rev-parse HEAD 2>/dev/null)
    timeout 60 git -C "$1" pull -q --ff-only 2>/dev/null || exit 0
    after=$(git -C "$1" rev-parse HEAD 2>/dev/null)
    [[ "$before" == "$after" ]] && exit 0
    echo "gitcraft: updated $1 ${before:0:7} -> ${after:0:7} $(date -u +%FT%TZ)"
    "$1/scripts/install-global.sh" && GITCRAFT_UPDATED=1 "$2/scripts/session-start.sh" --global
  ' _ "$repo_clone" "$GITCRAFT_HOME/runtime" >>"$GITCRAFT_LOG/update.log" 2>&1 < /dev/null &
fi

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
# Blender is in but the engine check's Node packages are not (lost with an older runtime copy, or a new lockfile):
# install.sh meshcraft keeps Blender and only runs npm ci
elif gitcraft_mesh_ready && command -v npm >/dev/null && ! gitcraft_engine_check_ready "$(dirname "$here")"; then
  missing+=(meshcraft)
fi

# Studio: finish a core install that was cut off ("pending"/"failed" and not complete), and install a voice model
# that setup deferred (GITCRAFT_STUDIO_VOICE=later) or didn't finish. A deferred voice model reaches the running
# studiocraft server on its next call (its dependency checks only cache what was found).
studio_last=$(python3 -c 'import json,os,sys;t=json.load(open(os.path.join(sys.argv[1],"status.json"))).get("tools",{});print(t.get("studiocraft",{}).get("state",""), t.get("studiocraft-voice",{}).get("state",""))' "$GITCRAFT_HOME" 2>/dev/null)
read -r studio_last voice_last <<<"$studio_last"
studio_voice=0
if [[ "$GITCRAFT_STUDIO" == 1 ]]; then
  # any state but a deliberate off: cut off ("pending"), failed, never attempted, or a runtime removed since
  if [[ "$studio_last" != off ]] && ! gitcraft_studio_ready; then missing+=(studiocraft); fi
  if [[ "$voice_last" == later || "$voice_last" == pending ]] && [[ ! -f "$GITCRAFT_STUDIO_HOME/models/kokoro/voices-v1.0.bin" ]]; then
    [[ " ${missing[*]} " == *" studiocraft "* ]] || missing+=(studiocraft); studio_voice=1
  fi
fi

# Mocap (opt-in: install-studio.sh mocap): finish an install that stopped part-way (models or the system EGL library
# missing), in the background, at most one at a time.
if [[ -d "$GITCRAFT_STUDIO_HOME/mocap-venv" ]] && { ! ls "$GITCRAFT_STUDIO_HOME"/models/mediapipe/pose_landmarker_full.task >/dev/null 2>&1 || { [[ $(uname) == Linux ]] &&
     ! { ldconfig -p 2>/dev/null | grep -q libEGL.so.1; }; }; }; then
  mlock="$GITCRAFT_HOME/mocap.lock"
  if command -v flock >/dev/null; then
    setsid nohup flock -n "$mlock" "$here/install-studio.sh" mocap >>"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  else
    setsid nohup "$here/install-studio.sh" mocap >>"$GITCRAFT_LOG/install.log" 2>&1 < /dev/null &
  fi
fi

# Heavy optional installs a setup script queued instead of running (scripts/install-later.sh: TripoSR, ACE-Step):
# in the background, one runner at a time, after any Blender build (scripts/run-later.sh).
if compgen -G "$GITCRAFT_HOME/later/*.job" >/dev/null; then
  setsid nohup "$here/run-later.sh" >>"$GITCRAFT_LOG/later.log" 2>&1 < /dev/null &
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
echo "GITCRAFT: MeshCraft and ForgeCraft announce their tools when their build finishes; StudioCraft announces its department tools when its runtime lands, and picks up a deferred voice model on its next call; other tools need /mcp."
