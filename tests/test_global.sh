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
#    (`curl … | bash`, here `bash < setup-env.sh`), cloning this checkout's committed branch.
# 3. From the other project: `claude mcp list` (the real CLI), then every server started with the
#    registered command, and real work through four tools with hand-offs (global_project_check.py).
#    With GITCRAFT_TEST_ASK_CLAUDE=1 (default when the CLI can answer) also asks a headless
#    Claude Code session in that project what it can see.
# 4. Re-runs setup (idempotent: one instruction block, user text kept) and doctor.
# Exit 1 on any failure. Downloads the prebuilt tools (~400 MB) unless they are cached.
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
export HOME="$work/home"
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
GITCRAFT_REPO_URL="$repo" GITCRAFT_REF="$branch" bash < "$repo/scripts/setup-env.sh" > "$work/setup.out" 2>&1; rc=$?
check "setup-env.sh (piped to bash) exits 0" '[[ $rc -eq 0 ]]'
check "runtime installed in ~/.gitcraft/runtime from the setup clone, not from the checkout" \
  '[[ -x "$HOME/.gitcraft/runtime/scripts/mcp.sh" ]] && grep -q "$HOME/.gitcraft/repo" "$HOME/.gitcraft/runtime/.gitcraft-source"'
check "nothing in the user config points at the GITCRAFT checkout" '! grep -qs "$repo" "$HOME/.claude.json" "$HOME/.claude/CLAUDE.md"'
check "global instructions added and the user's own CLAUDE.md text kept" \
  'grep -q "GITCRAFT:BEGIN" "$HOME/.claude/CLAUDE.md" && grep -q "Always use tabs in Makefiles" "$HOME/.claude/CLAUDE.md"'
check "gitcraft skill installed at user level" '[[ -f "$HOME/.claude/skills/gitcraft/SKILL.md" ]]'
check "playcraft skill installed at user level" '[[ -f "$HOME/.claude/skills/playcraft/SKILL.md" ]]'
check "pixelcraft skill installed at user level" '[[ -f "$HOME/.claude/skills/pixelcraft/SKILL.md" ]]'
check "'Run GITCRAFT' is routed in every project: instructions and the produce skill name production_start" \
  'grep -q "Run GITCRAFT" "$HOME/.claude/CLAUDE.md" && grep -q "production_start" "$HOME/.claude/CLAUDE.md" && grep -q "^description:.*Run GITCRAFT" "$HOME/.claude/skills/produce/SKILL.md"'
check "the runtime the servers start from has the universal entry point" '[[ -f "$HOME/.gitcraft/runtime/production/entry.py" ]]'

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
GITCRAFT_REPO_URL="$repo" GITCRAFT_REF="$branch" bash < "$repo/scripts/setup-env.sh" > "$work/setup2.out" 2>&1
check "re-running setup keeps exactly one instruction block" '[[ $(grep -c "GITCRAFT:BEGIN" "$HOME/.claude/CLAUDE.md") -eq 1 ]]'
"$HOME/.gitcraft/runtime/scripts/doctor.sh" > "$work/doctor.out" 2>&1
check "doctor: registration all from the runtime, instructions and skill present" \
  'grep -q "all from the runtime" "$work/doctor.out" && grep -q "instructions: $HOME/.claude/CLAUDE.md" "$work/doctor.out" && grep -q "skill: *$HOME/.claude/skills" "$work/doctor.out"'

echo; echo "$pass/$((pass+fail)) checks passed (logs and reports in $work)"
[[ $fail -eq 0 ]]
