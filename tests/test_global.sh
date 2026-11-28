#!/usr/bin/env bash
# Cross-repository acceptance test: GITCRAFT used from a SEPARATE project, in a FRESH environment,
# with no GITCRAFT checkout attached to that project.
#
#   tests/test_global.sh [workdir]
#
# 1. Fresh HOME (empty ~/.claude.json, ~/.claude, ~/.gitcraft), seeded with a user CLAUDE.md that
#    must survive, and a separate git project (sibling folder) with its own palette, an existing
#    asset and a project-scope .mcp.json that must keep working.
# 2. Runs the one-step setup script exactly as an environment's setup script does
#    (`curl … | bash`, here `bash < setup-env.sh`), cloning this checkout's committed branch. Setup is fast and
#    installs no 3D component; a later setup-script line asking for a large runtime is skipped with one line.
# 2b. A session starts (the user-level hook) and installs 3D on demand, as a session that needs 3D does:
#    scripts/install-3d.sh. The capability summary is one line, printed once.
# 3. From the other project: `claude mcp list` (the real CLI), then every server started with the
#    registered command, and real work through four tools with hand-offs (global_project_check.py).
#    With GITCRAFT_TEST_ASK_CLAUDE=1 (default when the CLI can answer) also asks a headless
#    Claude Code session in that project what it can see.
# 4. Re-runs setup (idempotent: one instruction block, user text kept) and doctor.
# Exit 1 on any failure. Downloads the prebuilt tools and, in step 2b, Blender (~400 MB) unless they are cached.
set -uo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
work="${1:-$(mktemp -d "${TMPDIR:-/tmp}/gitcraft-global-XXXX")}"
proj="${GITCRAFT_TEST_PROJECT:-$(dirname "$repo")/gitcraft-xrepo-test}"
branch="$(git -C "$repo" rev-parse --abbrev-ref HEAD)"
real_home="$HOME"
pass=0 fail=0
check() { if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }

[[ -z "$(git -C "$repo" status --porcelain -- scripts global tests/global_project_check.py tests/mcp_client.py)" ]] \
  || echo "note: uncommitted changes under scripts/ or global/ are NOT tested (the setup clones the committed branch $branch)"

# --- 1. fresh environment + separate project
# A long HOME on purpose: Unix-socket paths are capped at 107 bytes, and a launcher that put temp files under HOME
# made Chromium abort under long HOMEs only (#43). This keeps the fresh install honest wherever the test runs.
export HOME="$work/home-of-a-user-with-a-long-path"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$real_home/.cache/pip}" UV_CACHE_DIR="${UV_CACHE_DIR:-$real_home/.cache/uv}"
export PATH="$real_home/.local/bin:$PATH"
unset GITCRAFT_HOME GITCRAFT_ROOT GITCRAFT_ROOTS GITCRAFT_3D_LIBRARY GITCRAFT_MESHCRAFT_LIBRARY FORGECRAFT_LIBRARY FORGECRAFT_HOME \
      GITCRAFT_LIGHTCRAFT_LIBRARY CLAUDE_CONFIG_DIR CLAUDE_PROJECT_DIR
rm -rf "$HOME" "$proj"; mkdir -p "$HOME/.claude" "$proj/src" "$proj/assets/brand"
printf '# My own notes\n\nAlways use tabs in Makefiles.\n' > "$HOME/.claude/CLAUDE.md"
printf ':root {\n  --brand-primary: #1E3A8A;\n  --brand-accent: #F59E0B;\n  --brand-ink: #0F172A;\n  --brand-bg: #F8FAFC;\n}\n' > "$proj/src/theme.css"
printf '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="32" r="30" fill="#1E3A8A"/></svg>\n' > "$proj/assets/brand/logo-old.svg"
printf '{"mcpServers": {"orbit-docs": {"command": "python3", "args": ["-m", "http.server", "--help"]}}}\n' > "$proj/.mcp.json"
printf 'SECRET_TOKEN=orbit-project-only\n' > "$proj/.env"
printf '# Orbit\nLanding page for the Orbit app. Assets live in assets/, marketing in marketing/.\n' > "$proj/CLAUDE.md"
(cd "$proj" && git init -q && git add -A && git -c user.email=test@example.com -c user.name=test commit -qm "Orbit project") || exit 1
echo "fresh HOME: $HOME"; echo "project:    $proj (separate git repo, no GITCRAFT inside)"

check "fresh environment: no GITCRAFT install, no MCP servers" '[[ ! -e "$HOME/.gitcraft" && ! -e "$HOME/.claude.json" ]]'
check "the project contains no GITCRAFT code" '! grep -rqs -e mcp.sh -e gitcraft --exclude-dir=.git "$proj"'

# --- 2. the setup script, as an environment setup script runs it
# (run from inside a Claude Code session, this test must still look like a setup script: no session variables)
setup_env=(env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u GITCRAFT_SETUP -u GITCRAFT_MESHCRAFT GITCRAFT_REPO_URL="$repo" GITCRAFT_REF="$branch")
t0=$SECONDS
"${setup_env[@]}" bash < "$repo/scripts/setup-env.sh" > "$work/setup.out" 2>&1; rc=$?
setup_s=$((SECONDS - t0))
check "setup-env.sh (piped to bash) exits 0" '[[ $rc -eq 0 ]]'
gc="$HOME/.gitcraft"
state() { python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["tools"].get(sys.argv[2],{}).get("state",""))' "$gc/status.json" "$1" 2>/dev/null; }
no_3d() { [[ ! -e "$gc/meshcraft/venv" && ! -e "$gc/forgecraft/ai-venv" && ! -e "$gc/forgecraft/TripoSR" && ! -e "$gc/forgecraft/dl" ]] && ! compgen -G "$gc/forgecraft/Meshroom-*" >/dev/null; }
check "setup finishes fast: ${setup_s}s (limit ${GITCRAFT_TEST_SETUP_LIMIT:-120}s; a Blender or Meshroom download alone takes longer)" '((setup_s < ${GITCRAFT_TEST_SETUP_LIMIT:-120}))'
check "setup installs no 3D component (no Blender, Meshroom, TripoSR or Hunyuan3D): 3D is on demand" 'no_3d && [[ "$(state meshcraft)" == off && "$(state forgecraft)" == off ]]'
check "setup runs no 3D capability probe and prints no capability report" '[[ ! -e "$gc/forgecraft/probe.json" ]] && ! grep -qiE "gitcraft-3d:|capabilit" "$work/setup.out"'
check "setup still installs the seven tools and the Studio core" \
  '[[ $(ls "$gc/bin" | grep -c -- "-cli$") -eq 7 && "$(state studiocraft)" == ok ]]'
# a setup script's own extra lines (the ones that used to time setup out) are held to the same limit until a session starts
env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u GITCRAFT_SETUP "$gc/runtime/scripts/install-3d.sh" core meshroom ai weights > "$work/setup-extra.out" 2>&1 < /dev/null; rc=$?
env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u GITCRAFT_SETUP "$gc/runtime/scripts/install-studio.sh" mocap music >> "$work/setup-extra.out" 2>&1 < /dev/null; rc2=$?
check "setup-script lines for Blender, Meshroom, the AI runtimes, weights, mocap and music: each skipped with one line, exit 0, nothing downloaded" \
  '[[ $rc -eq 0 && $rc2 -eq 0 && $(grep -c "setup skipped" "$work/setup-extra.out") -eq 6 && $(wc -l < "$work/setup-extra.out") -eq 6 ]] && no_3d && [[ ! -e "$gc/studio/mocap-venv" && ! -e "$gc/studio/ace-step" ]]'
check "every skipped download is in the log" '[[ $(grep -c "setup skipped" "$gc/logs/setup-skipped.log") -ge 6 ]]'
check "runtime installed in ~/.gitcraft/runtime from the setup clone, not from the checkout" \
  '[[ -x "$HOME/.gitcraft/runtime/scripts/mcp.sh" ]] && grep -q "$HOME/.gitcraft/repo" "$HOME/.gitcraft/runtime/.gitcraft-source"'
check "nothing in the user config points at the GITCRAFT checkout" '! grep -qs "$repo" "$HOME/.claude.json" "$HOME/.claude/CLAUDE.md"'
check "global instructions added and the user's own CLAUDE.md text kept" \
  'grep -q "GITCRAFT:BEGIN" "$HOME/.claude/CLAUDE.md" && grep -q "Always use tabs in Makefiles" "$HOME/.claude/CLAUDE.md"'
check "gitcraft skill installed at user level" '[[ -f "$HOME/.claude/skills/gitcraft/SKILL.md" ]]'
check "playcraft skill installed at user level" '[[ -f "$HOME/.claude/skills/playcraft/SKILL.md" ]]'
check "pixelcraft skill installed at user level" '[[ -f "$HOME/.claude/skills/pixelcraft/SKILL.md" ]]'
check "ui-design skill installed at user level, with its phase references and the directions page builder" \
  '[[ -f "$HOME/.claude/skills/ui-design/SKILL.md" && -f "$HOME/.claude/skills/ui-design/references/craft.md" && -f "$HOME/.claude/skills/ui-design/references/games.md" && -x "$HOME/.claude/skills/ui-design/scripts/directions.py" ]] && grep -q "ui-design" "$HOME/.claude/CLAUDE.md"'
check "'Run GITCRAFT' is routed in every project: instructions and the produce skill name production_start" \
  'grep -q "Run GITCRAFT" "$HOME/.claude/CLAUDE.md" && grep -q "production_start" "$HOME/.claude/CLAUDE.md" && grep -q "^description:.*Run GITCRAFT" "$HOME/.claude/skills/produce/SKILL.md"'
check "the runtime the servers start from has the universal entry point" '[[ -f "$HOME/.gitcraft/runtime/production/entry.py" ]]'

# --- 2b. a session starts, and installs 3D itself because its work needs it
voice_was="$(state studiocraft-voice)"
(cd "$proj" && CLAUDECODE=1 "$gc/runtime/scripts/session-start.sh" --global) > "$work/session-start.out" 2>&1
check "session start ends the setup phase and does not start a Blender build" '[[ ! -e "$gc/setup-phase" ]] && ! grep -q "meshcraft" "$work/session-start.out"'
(cd "$proj" && CLAUDECODE=1 "$gc/runtime/scripts/install-3d.sh") > "$work/install-3d.out" 2>&1; rc=$?
check "in the session, install-3d.sh installs MeshCraft and ForgeCraft (exit 0, Blender in, both recorded ok)" \
  '[[ $rc -eq 0 && -x "$gc/meshcraft/venv/bin/python" && "$(state meshcraft)" == ok && "$(state forgecraft)" == ok ]]'
check "the capability summary is one line" '[[ $(grep -c "^gitcraft-3d: ready: " "$work/install-3d.out") -eq 1 ]] && grep -q "^gitcraft-3d: ready: .*blender" "$work/install-3d.out"'
(cd "$proj" && CLAUDECODE=1 "$gc/runtime/scripts/install-3d.sh") > "$work/install-3d-again.out" 2>&1
check "and it is printed once: a second run says nothing new" '! grep -q "^gitcraft-3d: ready: " "$work/install-3d-again.out"'
if [[ "$voice_was" == later ]]; then
  for _ in $(seq 60); do [[ "$(state studiocraft-voice)" == ok ]] && break; sleep 2; done
  check "the voice model setup left out (over the limit) was installed by the session hook in the background" \
    '[[ "$(state studiocraft-voice)" == ok && -f "$gc/studio/models/kokoro/voices-v1.0.bin" ]]'
fi

# --- 3. from the other project
if command -v claude >/dev/null; then
  (cd "$proj" && timeout 300 claude mcp list) > "$work/mcp-list.out" 2>&1
  n=$(grep -cE '^(photocraft|vectorcraft|designcraft|pdfcraft|lightcraft|filmcraft|effectcraft|meshcraft|forgecraft|studiocraft):.*/\.gitcraft/runtime/scripts/mcp\.sh .*Connected' "$work/mcp-list.out")
  check "claude mcp list in the other project: 10/10 GITCRAFT servers Connected from the runtime ($n)" '[[ $n -eq 10 ]]'
  check "the project's own .mcp.json server is still listed next to them" 'grep -q "^orbit-docs:" "$work/mcp-list.out"'
else
  echo "SKIP claude CLI not on PATH: the MCP-level checks below still run"
fi
(cd "$proj" && python3 "$repo/tests/global_project_check.py" "$proj" "$repo" "$work/project-report.json"); rc=$?
check "work in the other project (see the project checks above)" '[[ $rc -eq 0 ]]'
check "the project's secret file is not in any tool's audit record" '! grep -qs "orbit-project-only" "$HOME/.gitcraft/logs/audit.jsonl"'

if [[ "${GITCRAFT_TEST_ASK_CLAUDE:-1}" == 1 ]] && command -v claude >/dev/null; then
  (cd "$proj" && timeout 300 claude -p "Answer in exactly three lines without using tools. Line 1: the comma-separated names of MCP servers you have whose names end in 'craft'. Line 2: YES or NO: do your user-level instructions tell you to consider GITCRAFT before creative or asset work? Line 3: YES or NO: is a skill named gitcraft available? Line 4: if the person says Run GITCRAFT, which studiocraft tool do your instructions say to call first (just its name)?" --max-turns 2) > "$work/claude-ask.out" 2>&1
  if grep -qiE 'not logged in|invalid api key|authentication|please run /login' "$work/claude-ask.out"; then
    echo "SKIP headless Claude Code check: the CLI is not signed in in the fresh HOME ($(head -c 120 "$work/claude-ask.out"))"
  else
    check "headless Claude Code in the other project sees all ten servers" \
      '( for s in photocraft vectorcraft designcraft pdfcraft lightcraft filmcraft effectcraft meshcraft forgecraft studiocraft; do grep -q "$s" "$work/claude-ask.out" || exit 1; done )'
    check "headless Claude Code in the other project has the GITCRAFT instructions and skill" '[[ $(grep -c "YES" "$work/claude-ask.out") -ge 2 ]]'
    check "headless Claude Code knows 'Run GITCRAFT' starts with production_start" 'grep -q "production_start" "$work/claude-ask.out"'
  fi
fi

# --- 4. idempotent re-run + doctor
"${setup_env[@]}" bash < "$repo/scripts/setup-env.sh" > "$work/setup2.out" 2>&1
check "re-running setup keeps the installed 3D tools (still ok, nothing downloaded again)" '[[ "$(state meshcraft)" == ok ]] && ! grep -q "installing meshcraft" "$work/setup2.out"'
check "re-running setup keeps exactly one instruction block" '[[ $(grep -c "GITCRAFT:BEGIN" "$HOME/.claude/CLAUDE.md") -eq 1 ]]'
"$HOME/.gitcraft/runtime/scripts/doctor.sh" > "$work/doctor.out" 2>&1
check "doctor: registration all from the runtime, instructions and skill present" \
  'grep -q "all from the runtime" "$work/doctor.out" && grep -q "instructions: $HOME/.claude/CLAUDE.md" "$work/doctor.out" && grep -q "skill: *$HOME/.claude/skills" "$work/doctor.out"'

echo; echo "$pass/$((pass+fail)) checks passed (logs and reports in $work)"
[[ $fail -eq 0 ]]
