#!/usr/bin/env bash
# Install a GITCRAFT checkout as the runtime the MCP servers start from, without disturbing servers that are
# already running.
#
#   scripts/install-runtime.sh [SRC]        SRC defaults to this checkout
#
# Every install is a new, complete folder, $GITCRAFT_HOME/runtimes/<sha>-<time>, and $GITCRAFT_HOME/runtime is a
# symlink that is switched to it in one rename. Nothing in a version folder is ever changed or deleted while it
# may be in use, because a running server depends on it twice over:
#   - its sandbox (scripts/sandbox.py, Landlock) grants read access to the runtime's folders by inode when the
#     server starts. Replacing those folders (the old `rm -rf runtime && mv new runtime`) left every running
#     server denied (EACCES) on the whole runtime;
#   - Python imports modules lazily. Overwriting files in place (the old `rsync --delete`) let a running server
#     import new modules next to old ones already loaded (ImportError: cannot import name ...).
# The session-start self-update installs while that session's servers are starting, so both happened in practice.
# A server keeps the version it started with; the next session (or /mcp) starts from the new one.
#
# A runtime that is still a plain folder (installed before this script) is moved, not copied, into runtimes/:
# a rename keeps its inodes, so servers running from it keep working.
# Pruning keeps the current version, the one before it, and anything younger than GITCRAFT_RUNTIME_KEEP_DAYS (7).
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$(cd "${1:-$(dirname "$here")}" && pwd -P)"
GITCRAFT_HOME="${GITCRAFT_HOME:-$HOME/.gitcraft}"
runtime="$GITCRAFT_HOME/runtime"
versions="$GITCRAFT_HOME/runtimes"
keep_days="${GITCRAFT_RUNTIME_KEEP_DAYS:-7}"
mkdir -p "$versions"

# already running from the installed runtime: nothing to copy
if [[ -e "$runtime" && "$src" == "$(cd "$runtime" && pwd -P)" ]]; then exit 0; fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
sha="$(git -C "$src" rev-parse --short HEAD 2>/dev/null || echo unknown)"

# a runtime installed as a plain folder: move it aside whole (same inodes) so the symlink can take its place.
# Not while anything runs from it: those processes name files by the path "$runtime/...", so whatever takes that
# name next (the symlink) would break them. Then the update waits for an install with nothing running from it
# (setup-env.sh runs before any server; locally, the next session after the servers stop).
if [[ -d "$runtime" && ! -L "$runtime" ]]; then
  busy=0
  for f in /proc/[0-9]*/cmdline; do
    [[ "$f" == "/proc/$$/cmdline" ]] && continue
    cmd="$(tr '\0' ' ' < "$f" 2>/dev/null)"   # matched in bash: no helper process carries the path in its own arguments
    if [[ "$cmd" == *"$runtime/"* || " $cmd" == *" $runtime "* ]]; then busy=1; break; fi
  done
  if ((busy)); then
    echo "gitcraft: runtime update deferred: servers are running from $runtime (installed before versioned runtimes); it is applied by the next install with no server running from it"
    exit 0
  fi
  legacy="$versions/legacy-$stamp-$$"
  mv "$runtime" "$legacy" || { echo "gitcraft: couldn't move the old runtime aside" >&2; exit 1; }
  ln -s "$legacy" "$runtime"
fi

# the new version, complete before anything points at it
new="$versions/$sha-$stamp-$$"
tmp="$new.partial"
rm -rf "$tmp"; mkdir -p "$tmp"
ex=(.git acceptance __pycache__ '*.pyc' forgecraft/ui/dist .vercel)
if ! tar -C "$src" $(printf -- "--exclude=%s " "${ex[@]}") -cf - . | tar -C "$tmp" -xf -; then
  rm -rf "$tmp"; echo "gitcraft: couldn't copy the runtime from $src" >&2; exit 1
fi
printf '%s\n%s\n' "$sha" "$src" > "$tmp/.gitcraft-source"
mv "$tmp" "$new"

# switch: a new symlink renamed over the old one (atomic; no moment without a runtime)
ln -sfn "$new" "$runtime.link.$$" && mv -T "$runtime.link.$$" "$runtime" \
  || { rm -f "$runtime.link.$$"; echo "gitcraft: couldn't switch the runtime to $new" >&2; exit 1; }
echo "gitcraft: runtime ready at $runtime -> $new (from $src @ $sha)"

# prune: never the current or the previous version, never one younger than keep_days
current="$(readlink "$runtime")"
mapfile -t all < <(ls -1dt "$versions"/*/ 2>/dev/null | sed 's#/$##')
n=0
for v in "${all[@]}"; do
  [[ "$v" == *.partial ]] && continue
  n=$((n + 1))
  [[ "$v" == "$current" ]] && continue
  ((n <= 2)) && continue
  if [[ -n "$(find "$v" -maxdepth 0 -mtime "+$keep_days" 2>/dev/null)" ]]; then rm -rf "$v"; fi
done
exit 0
