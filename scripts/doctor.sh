#!/usr/bin/env bash
# Health check for GITCRAFT: what's installed, registered, sandboxed and failing.
#   scripts/doctor.sh          full report, exit 1 if anything needs attention
#   scripts/doctor.sh --brief  one line per problem (used by the session hook)
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/tools.sh"
brief=0; [[ "${1:-}" == --brief ]] && brief=1
problems=()
say() { ((brief)) || echo "$@"; }

say "GITCRAFT doctor"
say "  scripts:  $here"
say "  roots:    $GITCRAFT_ROOTS"
abi=$(python3 -c 'import ctypes;l=ctypes.CDLL(None);l.syscall.restype=ctypes.c_long;print(l.syscall(444,None,0,1))' 2>/dev/null)
if [[ "$GITCRAFT_SANDBOX" == off ]]; then
  say "  sandbox:  OFF (GITCRAFT_SANDBOX=off)"; problems+=("sandbox disabled by GITCRAFT_SANDBOX=off")
elif [[ "${abi:--1}" -gt 0 ]]; then
  say "  sandbox:  Landlock ABI $abi, network $([[ $GITCRAFT_ALLOW_NET == 1 ]] && echo allowed || echo denied)"
else
  say "  sandbox:  Landlock UNAVAILABLE on this kernel; only the guard and native roots apply"
  problems+=("Landlock unavailable: tools run without the kernel sandbox")
fi

registered=$(python3 -c 'import json,os;print(" ".join(json.load(open(os.path.expanduser("~/.claude.json"))).get("mcpServers",{})))' 2>/dev/null)
say ""
say "  tool          installed  registered  build"
for entry in "${GITCRAFT_TOOLS[@]}" ${GITCRAFT_EXTRA_TOOLS[@]+"${GITCRAFT_EXTRA_TOOLS[@]}"}; do
  IFS=: read -r name _ pkg <<<"$entry"
  if [[ "$name" == meshcraft || "$name" == forgecraft ]]; then
    inst=$([[ -x "$GITCRAFT_HOME/meshcraft/venv/bin/python" ]] && echo yes || echo NO)
  else
    inst=$([[ -x "$GITCRAFT_BIN/$pkg" ]] && echo yes || echo NO)
  fi
  reg=$([[ " $registered " == *" $name "* ]] && echo yes || echo NO)
  build=$(cat "$GITCRAFT_BIN/$name.version" 2>/dev/null || echo "-")
  if [[ "$name" == meshcraft && "$build" == - && $inst == yes ]]; then
    # installed before the version file existed: read the wheel's metadata (no Blender start-up) and record it
    di=$(ls -d "$GITCRAFT_HOME"/meshcraft/venv/lib/python*/site-packages/bpy-*.dist-info 2>/dev/null | head -1)
    if [[ -n "$di" ]]; then
      v=${di##*/bpy-}; build="blender ${v%.dist-info} (bpy wheel)"
      echo "$build" > "$GITCRAFT_BIN/meshcraft.version" 2>/dev/null || true
    fi
  fi
  say "$(printf '  %-13s %-10s %-11s %s' "$name" "$inst" "$reg" "$build")"
  [[ $inst == yes ]] || problems+=("$name is not installed: run scripts/install.sh $name")
  [[ $reg == yes ]] || problems+=("$name is not registered: run scripts/register.sh, then /mcp")
done

# Global availability: the servers must start from ~/.gitcraft/runtime, not from a checkout that
# may not be attached next session; the instructions and skill make every project consider them.
say ""
say "  global (every project):"
runtime="$GITCRAFT_HOME/runtime"
if [[ -x "$runtime/scripts/mcp.sh" ]]; then
  say "    runtime:      $runtime (from $(tail -1 "$runtime/.gitcraft-source" 2>/dev/null) @ $(head -1 "$runtime/.gitcraft-source" 2>/dev/null))"
else
  say "    runtime:      MISSING"; problems+=("no runtime in $runtime: run scripts/install-global.sh")
fi
while IFS= read -r line; do
  say "    $line"; [[ "$line" == *"NOT"* || "$line" == *"missing"* ]] && problems+=("${line# *}")
done < <(python3 - "$runtime" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" <<'PY'
import json, os, sys
runtime, cdir = sys.argv[1], sys.argv[2]
cfg = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~")), ".claude.json")
try: servers = json.load(open(cfg)).get("mcpServers", {})
except Exception: servers = {}
mine = {k: v for k, v in servers.items() if str(v.get("command", "")).endswith("/scripts/mcp.sh")}
bad = sorted(k for k, v in mine.items() if not str(v["command"]).startswith(runtime + "/") or not os.access(v["command"], os.X_OK))
print(f"registration: {len(mine)} user-scope servers" + (f"; NOT from the runtime or not runnable: {', '.join(bad)} (run scripts/install-global.sh)" if bad else ", all from the runtime"))
md = os.path.join(cdir, "CLAUDE.md")
print("instructions: " + (md if os.path.exists(md) and "GITCRAFT:BEGIN" in open(md).read() else f"missing from {md} (run scripts/install-global.sh)"))
sk = os.path.join(cdir, "skills", "gitcraft", "SKILL.md")
print("skill:        " + (sk if os.path.exists(sk) else f"missing: {sk} (run scripts/install-global.sh)"))
PY
)

if [[ -x "$GITCRAFT_HOME/meshcraft/venv/bin/python" ]]; then
  say ""
  say "  3D Department capabilities (meshcraft + forgecraft):"
  while IFS= read -r line; do say "    $line"; done < <(python3 - "$here/.." <<'PY'
import sys; sys.path.insert(0, sys.argv[1])
from gitcraft3d import hardware, library
d = hardware.probe()
hw = d["hardware"]
print(f"library: {library.ROOT}")
print(f"machine: {hw['cpu_threads']} CPU threads, {hw['ram']['total_gb']} GB RAM, GPU: {', '.join(g['name'] for g in hw['gpus']) or 'none (CPU only)'}")
for k, v in d["backends"].items():
    det = v.get("version") or (", ".join(v["templates"]) if v.get("templates") else None) or v.get("reason") or v.get("mode") or ""
    print(f"{k:11s} {'available  ' if v.get('available') else 'unavailable'} {det[:110]}")
PY
)
fi

audit="$GITCRAFT_LOG/audit.jsonl"
if [[ -f "$audit" ]]; then
  read -r calls fails refused < <(python3 - "$audit" <<'PY'
import json, sys
c = f = r = 0
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except Exception: continue
    c += 1; f += (not e.get("ok", True)); r += bool(e.get("refused"))
print(c, f, r)
PY
)
  say ""
  say "  audit:    $calls tool calls logged, $fails failed, $refused refused by policy ($audit)"
fi
if [[ -f "$GITCRAFT_HOME/status.json" ]]; then
  bad=$(python3 -c 'import json,os;s=json.load(open(os.path.expanduser("~/.gitcraft/status.json")));print(" ".join(k for k,v in s.get("tools",{}).items() if v.get("state")!="ok"))' 2>/dev/null)
  [[ -n "$bad" ]] && problems+=("last install reported failures for: $bad (see $GITCRAFT_LOG/install.log)")
fi

if ((${#problems[@]})); then
  ((brief)) && printf 'GITCRAFT: %s\n' "${problems[@]}" || { echo; echo "Needs attention:"; printf '  - %s\n' "${problems[@]}"; }
  exit 1
fi
((brief)) && echo "GITCRAFT: all tools installed, registered and sandboxed." || { echo; echo "All good."; }
