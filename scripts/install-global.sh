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
# 4. Session hook: a user-level SessionStart hook in ~/.claude/settings.json (every project) that finishes
#    deferred or interrupted installs in the background, e.g. Blender after GITCRAFT_MESHCRAFT=later. The repo's
#    own .claude/settings.json hook only runs when GITCRAFT is the session's project. Other settings are left as
#    they are. GITCRAFT_GLOBAL_HOOK=0 skips this step.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="$(dirname "$here")"
source "$here/tools.sh"
runtime="$GITCRAFT_HOME/runtime"
claude_dir="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

# 1) runtime copy (no .git, no acceptance packages, no caches): a new version folder behind the runtime symlink,
#    so servers already running keep the complete version they started with (scripts/install-runtime.sh)
GITCRAFT_HOME="$GITCRAFT_HOME" "$here/install-runtime.sh" "$src" || exit 1

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
  for skill in "$src"/global/skills/*/; do   # gitcraft (tool selection), playcraft (the game-design pass)
    s=$(basename "$skill")
    rm -rf "$claude_dir/skills/$s" && cp -R "$src/global/skills/$s" "$claude_dir/skills/$s" \
      && echo "gitcraft: skill installed at $claude_dir/skills/$s"
  done
fi

# 4) user-level SessionStart hook (every project): background-finish what setup deferred or didn't finish
if [[ "${GITCRAFT_GLOBAL_HOOK:-1}" != 0 ]]; then
  mkdir -p "$claude_dir"
  python3 - "$claude_dir/settings.json" "$runtime/scripts/session-start.sh" <<'PY'
import json, os, sys
dest, script = sys.argv[1], sys.argv[2]
try: cfg = json.load(open(dest))
except FileNotFoundError: cfg = {}
except ValueError:
    print(f"gitcraft: {dest} isn't valid JSON; session hook not installed (fix it and re-run install-global.sh)"); sys.exit(0)
groups = cfg.setdefault("hooks", {}).setdefault("SessionStart", [])
mine = {"type": "command", "command": f'"{script}" --global', "timeout": 30}
# drop an older copy of our entry (matched by the script path), keep everything else
for g in groups: g["hooks"] = [h for h in g.get("hooks", []) if "/.gitcraft/runtime/scripts/session-start.sh" not in h.get("command", "") and script not in h.get("command", "")]
groups[:] = [g for g in groups if g.get("hooks")]
groups.append({"hooks": [mine]})
new = json.dumps(cfg, indent=2) + "\n"
cur = open(dest).read() if os.path.exists(dest) else ""
if new != cur:
    tmp = dest + ".gitcraft.tmp"; open(tmp, "w").write(new); os.replace(tmp, dest)
print(f"gitcraft: session hook {'installed' if new != cur else 'up to date'} in {dest}")
PY
fi

# 5) network allowance for StudioCraft's CC0 library actions (materialcraft_fetch, worldcraft_hdri, worldcraft_fetch_model):
#    HTTPS to these hosts only, through netgate (docs/security.md). GITCRAFT_CC0_SOURCES=0 leaves them out. Only GITCRAFT's
#    own marked block is touched; anything else in ~/.gitcraft/allow-hosts stays as it is.
allow="$GITCRAFT_HOME/allow-hosts"
if [[ "${GITCRAFT_CC0_SOURCES:-1}" != 0 ]] && ! grep -q "^# gitcraft:cc0-sources" "$allow" 2>/dev/null; then
  { echo "# gitcraft:cc0-sources (Poly Haven + ambientCG, CC0 assets for studiocraft; remove this block to revoke)"
    for h in api.polyhaven.com dl.polyhaven.org ambientcg.com acg-download.struffelproductions.com; do echo "studiocraft: $h"; done
    echo "# gitcraft:cc0-sources end"; } >> "$allow"
  echo "gitcraft: studiocraft may reach the CC0 libraries (Poly Haven, ambientCG) over HTTPS ($allow)"
fi
