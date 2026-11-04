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
# State the last install recorded per tool (status.json), e.g. "off" when GITCRAFT_MESHCRAFT=0 skipped 3D.
last_state() { python3 -c 'import json,os,sys;print(json.load(open(os.path.join(sys.argv[1],"status.json"))).get("tools",{}).get(sys.argv[2],{}).get("state",""))' "$GITCRAFT_HOME" "$1" 2>/dev/null; }
off_note=0
say ""
say "  tool          installed  registered  build"
for entry in "${GITCRAFT_TOOLS[@]}" ${GITCRAFT_EXTRA_TOOLS[@]+"${GITCRAFT_EXTRA_TOOLS[@]}"}; do
  IFS=: read -r name _ pkg <<<"$entry"
  if [[ "$name" == meshcraft || "$name" == forgecraft ]]; then
    if gitcraft_mesh_ready; then inst=yes
    elif [[ "$(last_state "$name")" == off || "$(last_state "$name")" == later || ( "$GITCRAFT_MESHCRAFT" != 1 && ! -e "$GITCRAFT_HOME/meshcraft/venv" ) ]]; then
      # turned off on purpose: report it, don't count it as a problem (still registered unless =none: it waits for Blender)
      reg=$([[ " $registered " == *" $name "* ]] && echo yes || echo no)
      say "$(printf '  %-13s %-10s %-11s %s' "$name" off "$reg" "not installed (GITCRAFT_MESHCRAFT=${GITCRAFT_MESHCRAFT}); waits for Blender")"; off_note=1; continue
    elif [[ -e "$GITCRAFT_HOME/meshcraft/venv" ]]; then
      inst=PARTIAL
      if [[ "$(last_state meshcraft)" == failed ]]; then
        problems+=("$name: the Blender install failed (see $GITCRAFT_LOG/meshcraft.log; often no access to pypi.org or no matching Python). Fix that and run scripts/install.sh meshcraft, or set GITCRAFT_MESHCRAFT=0")
      else   # status still "pending": the run stopped during the download
        problems+=("$name: the Blender install didn't finish (often a setup script that ran out of time). Run scripts/install.sh meshcraft, or set GITCRAFT_MESHCRAFT=0 in the setup script")
      fi
    else inst=NO; fi
  elif [[ "$name" == studiocraft ]]; then
    if gitcraft_studio_ready; then inst=yes
    elif [[ "$(last_state studiocraft)" == off || "$GITCRAFT_STUDIO" != 1 ]]; then
      say "$(printf '  %-13s %-10s %-11s %s' "$name" off off "skipped (GITCRAFT_STUDIO=0)")"; continue
    elif [[ "$(last_state studiocraft)" == pending || "$(last_state studiocraft)" == failed ]]; then
      inst=PARTIAL   # registered anyway: it lists a status tool until the runtime lands, then announces its tools
      if [[ "$(last_state studiocraft)" == failed ]]; then
        problems+=("studiocraft: the Studio install failed (see $GITCRAFT_LOG/studio.log). Fix that and run scripts/install.sh studiocraft, or set GITCRAFT_STUDIO=0")
      else
        problems+=("studiocraft: the Studio install didn't finish (often a setup script that ran out of time); the 2D tools are unaffected. studiocraft is registered and announces its tools once the SessionStart hook finishes it in the background, or run scripts/install.sh studiocraft")
      fi
    else inst=NO; fi
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
  [[ $inst == yes || $inst == PARTIAL ]] || problems+=("$name is not installed: run scripts/install.sh $name")
  [[ $reg == yes || $inst == PARTIAL ]] || problems+=("$name is not registered: run scripts/register.sh, then /mcp")
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

if ((off_note)); then
  say ""
  say "  3D tools aren't installed. Run scripts/install.sh meshcraft forgecraft: the registered servers pick them up in the"
  say "  running session (tools/list_changed). In a setup script with a time limit, use GITCRAFT_MESHCRAFT=later."
fi
if gitcraft_mesh_ready; then
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

if gitcraft_studio_ready; then
  say ""
  say "  Studio departments (studiocraft; also ForgeCraft departments / department_run):"
  case "$(last_state studiocraft-voice)" in
    ok) say "    voice model:    installed (Kokoro-82M)" ;;
    later) say "    voice model:    deferred (GITCRAFT_STUDIO_VOICE=later): the SessionStart hook installs it in the background" ;;
    pending) say "    voice model:    install didn't finish: the SessionStart hook retries it, or run scripts/install-studio.sh voice" ;;
    failed) say "    voice model:    install failed (see $GITCRAFT_LOG/studio.log): scripts/install-studio.sh voice"; problems+=("studio voice model: install failed (see $GITCRAFT_LOG/studio.log)") ;;
    off) say "    voice model:    off (GITCRAFT_STUDIO_VOICE=0)" ;;
  esac
  studio_json=$(GITCRAFT_STUDIO_HOME="$GITCRAFT_STUDIO_HOME" "$GITCRAFT_STUDIO_HOME/venv/bin/python" "$here/../studio/cli.py" --call studio_status '{}' 2>/dev/null)
  while IFS= read -r line; do say "    $line"; done < <(python3 - "$studio_json" <<'PY'
import json, sys
try: d = json.loads(sys.argv[1])
except Exception: print("could not read the studio status (run studio/cli.py list)"); sys.exit()
for x in d["departments"]:
    acts = x["actions"]; ready = [a for a, v in acts.items() if v == "ready"]; blocked = {a: v for a, v in acts.items() if v != "ready"}
    line = f"{x['department']:15s} {len(ready)}/{len(acts)} actions ready"
    if blocked: line += "; blocked: " + "; ".join(f"{a} ({v[9:][:70]})" for a, v in list(blocked.items())[:3])
    print(line)
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
  # "later" is a deliberate deferral (the SessionStart hook installs it), not a failure
  bad=$(python3 -c 'import json,os,sys;s=json.load(open(os.path.join(sys.argv[1],"status.json")));print(" ".join(k for k,v in s.get("tools",{}).items() if v.get("state") not in ("ok","off","later") and not k.startswith("studiocraft")))' "$GITCRAFT_HOME" 2>/dev/null)
  # (studiocraft and its voice model have their own messages above)
  [[ -n "$bad" ]] && problems+=("last install reported failures for: $bad (see $GITCRAFT_LOG/install.log)")
fi

if ((${#problems[@]})); then
  ((brief)) && printf 'GITCRAFT: %s\n' "${problems[@]}" || { echo; echo "Needs attention:"; printf '  - %s\n' "${problems[@]}"; }
  exit 1
fi
((brief)) && echo "GITCRAFT: all tools installed, registered and sandboxed." || { echo; echo "All good."; }
