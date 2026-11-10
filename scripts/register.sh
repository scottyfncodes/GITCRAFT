#!/usr/bin/env bash
# Register every built ArtCraft tool with Claude Code at user scope, so the
# tools are available no matter which repo the session is working in.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"

if ! command -v claude >/dev/null; then
  # Setup scripts can run before the CLI is on PATH: write the user-scope
  # entries straight into ~/.claude.json (the same place `claude mcp add -s user` writes).
  python3 - "$here" "$GITCRAFT_BIN" "$([[ "$GITCRAFT_MESHCRAFT" != none ]] && echo 1 || echo 0)" "$([[ "$GITCRAFT_STUDIO" != 0 ]] && echo 1 || echo 0)" "${GITCRAFT_TOOLS[@]}" "${GITCRAFT_EXTRA_TOOLS[@]}" <<'PY'
import json, os, sys
here, bindir, mesh_wanted, studio_wanted, tools = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4] == "1", sys.argv[5:]
cfg_path = os.path.expanduser("~/.claude.json")
try: cfg = json.load(open(cfg_path))
except Exception: cfg = {}
servers = cfg.setdefault("mcpServers", {})
for entry in tools:
    name, _, pkg = entry.split(":")
    ready = mesh_wanted if name in ("meshcraft", "forgecraft") else studio_wanted if name == "studiocraft" else os.access(os.path.join(bindir, pkg), os.X_OK)
    if ready:
        servers[name] = {"type": "stdio", "command": os.path.join(here, "mcp.sh"), "args": [name], "env": {}}
        print(f"gitcraft: registered {name} (wrote ~/.claude.json)")
tmp = cfg_path + ".gitcraft.tmp"
json.dump(cfg, open(tmp, "w"), indent=2); os.replace(tmp, cfg_path)
PY
  exit 0
fi

# Two SessionStart hooks (the repo's and the global one) can run this at the same moment. Each run removes and
# re-adds every server, so without a lock one run's remove lands between the other's remove and add, and that add
# fails although the server ends up registered: the log said "couldn't register" for servers that were connected.
lockdir="${GITCRAFT_HOME:-$HOME/.gitcraft}"; mkdir -p "$lockdir"
exec 9>"$lockdir/register.lock"
command -v flock >/dev/null && flock -w 120 9
for entry in "${GITCRAFT_TOOLS[@]}" "${GITCRAFT_EXTRA_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  # the 3D servers are registered before Blender is in: Claude Code only reads MCP servers when a session starts, and
  # they wait for the install and then announce their tools (gitcraft3d/deferred.py). GITCRAFT_MESHCRAFT=none: not at all.
  if [[ "$name" == meshcraft || "$name" == forgecraft ]]; then [[ "$GITCRAFT_MESHCRAFT" != none ]] || continue
  # studiocraft likewise: registered before its runtime is in (it waits and announces its tools); GITCRAFT_STUDIO=0: not at all
  elif [[ "$name" == studiocraft ]]; then [[ "$GITCRAFT_STUDIO" != 0 ]] || continue
  else [[ -x "$GITCRAFT_BIN/$pkg" ]] || continue; fi
  # Already registered with this launcher: leave it alone. The second install pass (after Blender lands, install.sh)
  # used to remove and re-add every server in the middle of a live session; removing a server's entry is a config
  # change the running session acts on, so the 3D servers that were waiting for that very build could be dropped (#12).
  cur="$(claude mcp get "$name" 2>/dev/null)"
  if grep -qE "^ *Scope: User" <<<"$cur" && grep -qxF "  Command: $here/mcp.sh" <<<"$cur" && grep -qxF "  Args: $name" <<<"$cur"; then
    echo "gitcraft: registered $name (unchanged)"; continue
  fi
  claude mcp remove -s user "$name" >/dev/null 2>&1
  if claude mcp add -s user "$name" -- "$here/mcp.sh" "$name" >/dev/null 2>&1; then
    echo "gitcraft: registered $name"
  elif claude mcp get "$name" 2>/dev/null | grep -qF "$here/mcp.sh"; then
    echo "gitcraft: registered $name (already registered with this launcher)"
  else
    echo "gitcraft: couldn't register $name" >&2
  fi
done
