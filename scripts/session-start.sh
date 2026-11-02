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
