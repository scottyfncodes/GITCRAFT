#!/usr/bin/env bash
# Run the installs queued by scripts/install-later.sh (the SessionStart hook starts this in the background).
# One runner at a time ($GITCRAFT_HOME/later.lock); it waits for a Blender build in progress ($GITCRAFT_HOME/install.lock)
# so the two don't compete for the CPU and disk. A job is removed when it succeeds; a failed one stays for the next
# session, up to GITCRAFT_LATER_TRIES (3) attempts, then is dropped with its reason in the log.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"
q="${GITCRAFT_HOME:?}/later"; tries_max="${GITCRAFT_LATER_TRIES:-3}"
compgen -G "$q/*.job" >/dev/null || exit 0
if command -v flock >/dev/null; then
  exec 8>"$GITCRAFT_HOME/later.lock"; flock -n 8 || exit 0             # another runner has the queue
  flock -w 3600 "$GITCRAFT_HOME/install.lock" true 2>/dev/null || true  # Blender first, if it is being built
fi
for job in "$q"/*.job; do
  [[ -f "$job" ]] || continue
  read -r script args < "$job"
  t="${job%.job}.tries"
  case "$script" in install-3d.sh|install-studio.sh) ;; *) echo "gitcraft-later: dropped $job (unknown script '$script')"; rm -f -- "$job" "$t"; continue ;; esac
  n=$(( $(cat "$t" 2>/dev/null || true) + 1 )); echo "$n" > "$t"
  start=$(date +%s); echo "gitcraft-later: $script $args (attempt $n/$tries_max) started $(date -u +%FT%TZ)"
  # shellcheck disable=SC2086  # components are single words ([a-z0-9-]+), checked by install-later.sh
  if "$here/$script" $args; then
    rm -f -- "$job" "$t"; echo "gitcraft-later: $script $args done in $(( $(date +%s) - start ))s"
  elif (( n >= tries_max )); then
    rm -f -- "$job" "$t"; echo "gitcraft-later: $script $args failed $n times; dropped (run scripts/$script $args by hand)"
  else
    echo "gitcraft-later: $script $args failed after $(( $(date +%s) - start ))s; the next session retries it"
  fi
done
