#!/usr/bin/env bash
# Make GITCRAFT available in every Claude Code project, independent of any checkout.
#
#   scripts/install-global.sh            (install.sh and the SessionStart hook run this for you)
#
# 1. Runtime: copies this checkout's launcher, guard, sandbox and tool code into
#    ~/.gitcraft/runtime. The MCP servers start from there, so they keep working
#    when no GITCRAFT checkout is attached, cloned or open. Whichever checkout
#    installed last is the one that runs.
# 2. Registration: every installed tool at user scope (~/.claude.json), pointing
#    at ~/.gitcraft/runtime/scripts/mcp.sh. Project-scope (.mcp.json) and local
#    entries are left alone; Claude Code lets those override user scope.
# 3. Instructions: a managed block in ~/.claude/CLAUDE.md (loaded in every project)
#    and the `gitcraft` skill in ~/.claude/skills/gitcraft. Text outside the
#    block is never touched. GITCRAFT_GLOBAL_INSTRUCTIONS=0 skips this step.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$(dirname "$here")"
source "$here/tools.sh"
runtime="$GITCRAFT_HOME/runtime"
claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

# 1) runtime copy (no .git, no acceptance packages, no caches)
if [[ "$(cd "$src" && pwd -P)" != "$(mkdir -p "$runtime" && cd "$runtime" && pwd -P)" ]]; then
  ex=(.git acceptance __pycache__ '*.pyc' forgecraft/ui/dist .vercel)
  if command -v rsync >/dev/null; then
    rsync -a --delete $(printf -- "--exclude=%s " "${ex[@]}") "$src/" "$runtime/"
  else
    tmp="$runtime.new.$$"; rm -rf "$tmp"; mkdir -p "$tmp"
    tar -C "$src" $(printf -- "--exclude=%s " "${ex[@]}") -cf - . | tar -C "$tmp" -xf - && rm -rf "$runtime" && mv "$tmp" "$runtime"
  fi || { echo "gitcraft: couldn't copy the runtime to $runtime" >&2; exit 1; }
  git -C "$src" rev-parse --short HEAD 2>/dev/null > "$runtime/.gitcraft-source" || echo "unknown" > "$runtime/.gitcraft-source"
  echo "$src" >> "$runtime/.gitcraft-source"
  echo "gitcraft: runtime ready at $runtime (from $src @ $(head -1 "$runtime/.gitcraft-source"))"
fi

# 2) user-scope registration from the runtime
"$runtime/scripts/register.sh"

# 3) global instructions + skill
if [[ "${GITCRAFT_GLOBAL_INSTRUCTIONS:-1}" != 0 ]]; then
  mkdir -p "$claude_dir/skills"
  python3 - "$src/global/CLAUDE.md" "$claude_dir/CLAUDE.md" <<'PY'
import os, re, sys
block_src, dest = sys.argv[1], sys.argv[2]
BEGIN, END = "<!-- GITCRAFT:BEGIN (managed by GITCRAFT scripts/install-global.sh; edits inside are replaced) -->", "<!-- GITCRAFT:END -->"
block = f"{BEGIN}\n{open(block_src).read().strip()}\n{END}"
cur = open(dest).read() if os.path.exists(dest) else ""
pat = re.compile(r"<!-- GITCRAFT:BEGIN.*?-->.*?<!-- GITCRAFT:END -->", re.S)
new = pat.sub(lambda m: block, cur) if pat.search(cur) else (cur.rstrip() + "\n\n" if cur.strip() else "") + block + "\n"
if new != cur:
    tmp = dest + ".gitcraft.tmp"; open(tmp, "w").write(new); os.replace(tmp, dest)
print(f"gitcraft: global instructions {'updated' if new != cur else 'up to date'} in {dest}")
PY
  rm -rf "$claude_dir/skills/gitcraft" && cp -R "$src/global/skills/gitcraft" "$claude_dir/skills/gitcraft" \
    && echo "gitcraft: skill installed at $claude_dir/skills/gitcraft"
fi
