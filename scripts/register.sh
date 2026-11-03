#!/usr/bin/env bash
# Register every built ArtCraft tool with Claude Code at user scope, so the
# tools are available no matter which repo the session is working in.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"

if ! command -v claude >/dev/null; then
  # Setup scripts can run before the CLI is on PATH: write the user-scope
  # entries straight into ~/.claude.json (the same place `claude mcp add -s user` writes).
  python3 - "$here" "$GITCRAFT_BIN" "$([[ "$GITCRAFT_MESHCRAFT" != none ]] && echo 1 || echo 0)" "${GITCRAFT_TOOLS[@]}" "${GITCRAFT_EXTRA_TOOLS[@]}" <<'PY'
import json, os, sys
here, bindir, mesh_wanted, tools = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4:]
cfg_path = os.path.expanduser("~/.claude.json")
try: cfg = json.load(open(cfg_path))
except Exception: cfg = {}
servers = cfg.setdefault("mcpServers", {})
for entry in tools:
    name, _, pkg = entry.split(":")
    if (mesh_wanted if name in ("meshcraft", "forgecraft") else os.access(os.path.join(bindir, pkg), os.X_OK)):
        servers[name] = {"type": "stdio", "command": os.path.join(here, "mcp.sh"), "args": [name], "env": {}}
        print(f"gitcraft: registered {name} (wrote ~/.claude.json)")
tmp = cfg_path + ".gitcraft.tmp"
json.dump(cfg, open(tmp, "w"), indent=2); os.replace(tmp, cfg_path)
PY
  exit 0
fi

for entry in "${GITCRAFT_TOOLS[@]}" "${GITCRAFT_EXTRA_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  # the 3D servers are registered before Blender is in: Claude Code only reads MCP servers when a session starts, and
  # they wait for the install and then announce their tools (gitcraft3d/deferred.py). GITCRAFT_MESHCRAFT=none: not at all.
  if [[ "$name" == meshcraft || "$name" == forgecraft ]]; then [[ "$GITCRAFT_MESHCRAFT" != none ]] || continue
  else [[ -x "$GITCRAFT_BIN/$pkg" ]] || continue; fi
  claude mcp remove -s user "$name" >/dev/null 2>&1
  if claude mcp add -s user "$name" -- "$here/mcp.sh" "$name" >/dev/null 2>&1; then
    echo "gitcraft: registered $name"
  else
    echo "gitcraft: couldn't register $name" >&2
  fi
done
