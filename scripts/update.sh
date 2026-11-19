#!/usr/bin/env bash
# Update GITCRAFT deliberately: nothing new runs until a person has seen what changed and said yes.
# Installed as ~/.gitcraft/gitcraft-update (by install-global.sh), which survives a rollback to an older GITCRAFT.
#
#   scripts/update.sh                  show what an update to origin/main would change (installs nothing)
#   scripts/update.sh --yes            apply it: check out that commit, refresh the runtime, registration and
#                                      instructions from it, and reinstall the prebuilt tools whose pinned checksum changed
#   scripts/update.sh --to <commit|tag> [--yes]   the same for an older or specific commit (it must be on main)
#   scripts/update.sh --rollback [--yes]          back to the commit this clone was on before the last update
#
#   --repo <dir>   the clone to update (default: ~/.gitcraft/repo, the one setup-env.sh made)
#
# Safety rules: only commits contained in origin/main are accepted (no fork, unmerged branch or arbitrary ref);
# the security-relevant files that change (scripts/, global/, .claude/, .github/, scripts/bin.sha256) are listed
# before anything runs; every applied update is logged in ~/.gitcraft/logs/update.log with from -> to, which is
# what --rollback reads. Prebuilt binaries are still checked against scripts/bin.sha256 by install.sh.
set -uo pipefail
GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
repo="$GITCRAFT_HOME/repo" target="" yes=0 rollback=0
while (($#)); do
  case "$1" in
    --yes) yes=1 ;;
    --to) target="${2:?--to needs a commit or tag}"; shift ;;
    --rollback) rollback=1 ;;
    --repo) repo="${2:?--repo needs a directory}"; shift ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) echo "update.sh: unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done
log="$GITCRAFT_HOME/logs/update.log"; mkdir -p "$(dirname "$log")"
[[ -d "$repo/.git" ]] || { echo "update.sh: $repo is not a GITCRAFT clone (run setup-env.sh first, or pass --repo)" >&2; exit 2; }
g() { git -C "$repo" "$@"; }

# full history of main, so "is this commit on main" can be answered (setup-env.sh clones with --depth 1)
if [[ "$(g rev-parse --is-shallow-repository)" == true ]]; then g fetch -q --unshallow origin main 2>/dev/null || g fetch -q origin main
else g fetch -q origin main; fi || { echo "update.sh: could not fetch origin main" >&2; exit 1; }
main="$(g rev-parse FETCH_HEAD)"

if ((rollback)); then
  target="$(sed -nE 's/^.* applied ([0-9a-f]{40}) -> [0-9a-f]{40}.*/\1/p' "$log" 2>/dev/null | tail -1)"
  [[ -n "$target" ]] || { echo "update.sh: no applied update in $log to roll back" >&2; exit 2; }
fi
target="$(g rev-parse --verify -q "${target:-$main}^{commit}")" || { echo "update.sh: unknown commit or tag" >&2; exit 2; }
g merge-base --is-ancestor "$target" "$main" || { echo "update.sh: REFUSED: $target is not on origin/main (only reviewed, merged commits are installed)" >&2; exit 3; }

cur="$(g rev-parse HEAD)"
if [[ "$cur" == "$target" ]]; then echo "update.sh: already at ${target:0:12}"; exit 0; fi
echo "GITCRAFT update: ${cur:0:12} -> ${target:0:12}"
if g merge-base --is-ancestor "$cur" "$target"; then
  echo; echo "Commits:"; g log --format='  %h %ad %s' --date=short "$cur..$target" | head -60
else
  echo "(this goes back to an older commit)"
fi
echo; echo "Security-relevant files that change (scripts, global instructions and skills, hooks, workflows, binary pins):"
g diff --stat "$cur" "$target" -- scripts global .claude .github | sed 's/^/  /' | tail -40
pins_changed=0; g diff --quiet "$cur" "$target" -- scripts/bin.sha256 || pins_changed=1
((pins_changed)) && echo "  ! scripts/bin.sha256 changes: the prebuilt tools will be reinstalled (each checked against the new pins)"
if ((yes == 0)); then
  echo; echo "Nothing was changed. Review the above, then apply it with: $0 --to $target --yes"
  exit 3
fi

g checkout -q -B main "$target" || { echo "update.sh: checkout failed" >&2; exit 1; }
echo "$(date -u +%FT%TZ) applied $cur -> $target by ${USER:-$(id -un)}$( ((rollback)) && echo ' (rollback)')" >> "$log"
"$repo/scripts/install-global.sh" || { echo "update.sh: install-global.sh failed; roll back with $0 --rollback --yes" >&2; exit 1; }
if ((pins_changed)); then
  # shellcheck source=tools.sh
  source "$repo/scripts/tools.sh"
  names=(); for e in "${GITCRAFT_TOOLS[@]}"; do names+=("${e%%:*}"); done
  "$repo/scripts/install.sh" --update "${names[@]}" || echo "update.sh: some prebuilt tools were not reinstalled (see above); the previous binaries stay in place" >&2
fi
rm -f "$GITCRAFT_HOME/update-available"
echo "update.sh: GITCRAFT is at ${target:0:12}. Running servers keep their version; new sessions (or /mcp) use it."
