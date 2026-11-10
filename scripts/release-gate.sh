#!/usr/bin/env bash
# Release gate for the prebuilt ArtCraft CLIs. Nothing reaches the `bin` branch unless it passes here
# (.github/workflows/build.yml runs it between the build and publish jobs).
#
#   scripts/release-gate.sh <candidate-dir> [workdir]
#
# <candidate-dir> holds exactly what publish would push: <pkg>.gz and <name>.manifest for every tool in
# scripts/tools.sh. The gate never changes those files; on success it adds SHA256SUMS, which publish checks.
#
#   1. Complete: every tool is present and was built in this run (no partial release, no older carry-over).
#   2. glibc ceiling: each binary's highest GLIBC_* symbol version is at most $GITCRAFT_GLIBC_CEILING (2.39: the
#      Tests runner and Claude Code cloud sessions are Ubuntu 24.04).
#   3. Fresh install of THESE binaries: a throwaway clone of this checkout gets a local, never-pushed `bin` branch
#      holding them, and tests/test_global.sh installs from it into a fresh HOME. GITCRAFT_BIN_REPO points nowhere,
#      so the published builds can never be substituted.
#   4. Evidence: the installed binaries are byte-identical to the candidates; the test passed with no FAIL; the
#      `claude mcp list` checks ran; at least $GITCRAFT_GATE_MIN_CHECKS top-level and $GITCRAFT_GATE_MIN_PROJECT
#      cross-project checks passed. (The three headless-Claude checks need a signed-in, billed session: they run only
#      when ANTHROPIC_API_KEY is set, i.e. a manual dispatch with claude_session ticked, see docs/costs.md.)
#
# GITCRAFT_GATE_SELFTEST=glibc|broken-binary injects a controlled fault into a staging copy (never into the
# candidates) to prove the gate fails closed. Exit 0 only when every step passes.
set -uo pipefail
cand="$(cd "${1:?usage: release-gate.sh <candidate-dir> [workdir]}" && pwd)"
work="${2:-$(mktemp -d "${TMPDIR:-/tmp}/gitcraft-gate-XXXX")}"; mkdir -p "$work"; work="$(cd "$work" && pwd)"
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ceiling="${GITCRAFT_GLIBC_CEILING:-2.39}"
min_checks="${GITCRAFT_GATE_MIN_CHECKS:-18}" min_project="${GITCRAFT_GATE_MIN_PROJECT:-15}"
fault="${GITCRAFT_GATE_SELFTEST:-}"
source "$repo/scripts/tools.sh"
fail() { echo "GATE FAIL: $*" >&2; echo "::error::release gate: $*"; exit 1; }
step() { echo; echo "== $*"; }

case "$fault" in "" | glibc | broken-binary) ;; *) fail "unknown GITCRAFT_GATE_SELFTEST=$fault" ;; esac
[[ -n "$fault" ]] && echo "SELF-TEST: injecting fault '$fault' into the staging copy (the candidates are not changed)"
[[ "$fault" == glibc ]] && ceiling=2.30

step "1. every tool is present"
stage="$work/stage"; rm -rf "$stage"; mkdir -p "$stage"
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  [[ -s "$cand/$pkg.gz" && -s "$cand/$name.manifest" ]] || fail "$name: $pkg.gz or $name.manifest missing from the candidates"
  cp "$cand/$pkg.gz" "$cand/$name.manifest" "$stage/"
  gunzip -c "$stage/$pkg.gz" > "$stage/$pkg" || fail "$name: $pkg.gz does not decompress"
  echo "ok   $name  $(cut -d' ' -f3- "$stage/$name.manifest")"
done

step "2. glibc ceiling $ceiling"
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  need=$(objdump -T "$stage/$pkg" 2>/dev/null | grep -o 'GLIBC_[0-9][0-9.]*' | sed 's/GLIBC_//' | sort -uV | tail -1)
  [[ -n "$need" ]] || fail "$pkg: no GLIBC symbol versions found (not a dynamically linked Linux binary?)"
  [[ "$(printf '%s\n' "$need" "$ceiling" | sort -V | tail -1)" == "$ceiling" ]] || fail "$pkg needs glibc $need, newer than $ceiling"
  echo "ok   $pkg needs glibc $need"
done

if [[ "$fault" == broken-binary ]]; then   # a binary that cannot start, as a bad upstream build would be
  printf '#!/bin/sh\necho "gate self-test: broken binary" >&2\nexit 1\n' > "$stage/vectorcraft-cli"
  gzip -9 -c "$stage/vectorcraft-cli" > "$stage/vectorcraft-cli.gz"
fi

step "3. fresh install of these binaries (tests/test_global.sh)"
clone="$work/GITCRAFT"; rm -rf "$clone"
git clone -q --no-hardlinks "$repo" "$clone" || fail "cannot clone $repo"
branch="$(git -C "$clone" rev-parse --abbrev-ref HEAD)"
[[ "$branch" != HEAD ]] || fail "the checkout is on a detached HEAD: check out a named branch first (git checkout -B <name>)"
bin="$work/bin-candidate"; rm -rf "$bin"; mkdir -p "$bin"
for entry in "${GITCRAFT_TOOLS[@]}"; do IFS=: read -r name _ pkg <<<"$entry"; cp "$stage/$pkg.gz" "$stage/$name.manifest" "$bin/"; done
cat "$bin"/*.manifest | sort > "$bin/MANIFEST.txt"
git -C "$bin" init -q -b bin && git -C "$bin" add -A \
  && git -C "$bin" -c user.name=release-gate -c user.email=release-gate@localhost commit -qm "release candidate" || fail "cannot stage the candidates"
git -C "$clone" fetch -q "$bin" +bin:refs/heads/bin || fail "cannot create the local bin branch"
echo "local bin branch $(git -C "$clone" rev-parse --short bin) in $clone (not pushed anywhere)"
export GITCRAFT_BIN_REPO="$work/no-published-builds"   # the installer's fallback to the published builds goes nowhere
command -v claude >/dev/null || fail "the claude CLI is not on PATH: the 'claude mcp list' checks would be skipped"
out="$work/test_global.out"
GITCRAFT_TEST_PROJECT="$work/gitcraft-xrepo-test" bash "$clone/tests/test_global.sh" "$work/global" 2>&1 | tee "$out"
rc=${PIPESTATUS[0]}

step "4. evidence"
installed="$work/global/home-of-a-user-with-a-long-path/.gitcraft/bin"
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  want=$(sha256sum < "$stage/$pkg" | cut -d' ' -f1); have=$(sha256sum < "$installed/$pkg" 2>/dev/null | cut -d' ' -f1)
  [[ "$want" == "$have" ]] || fail "$pkg installed by the fresh install is not the candidate (installed ${have:-nothing}, candidate $want)"
  echo "ok   $pkg installed = candidate (${want:0:12})"
done
[[ $rc -eq 0 ]] || fail "tests/test_global.sh failed (exit $rc): $(grep '^FAIL' "$out" | head -5 | tr '\n' ';')"
! grep -q '^FAIL' "$out" || fail "tests/test_global.sh reported a FAIL"
grep -q '^PASS claude mcp list in the other project' "$out" || fail "the 'claude mcp list' checks did not run"
read -r p t < <(sed -nE 's#^([0-9]+)/([0-9]+) checks passed.*#\1 \2#p' "$out" | tail -1)
[[ -n "${p:-}" && "$p" == "$t" && "$p" -ge "$min_checks" ]] || fail "fresh install passed ${p:-?}/${t:-?} checks (need all, at least $min_checks)"
read -r pp pt < <(sed -nE 's#^([0-9]+)/([0-9]+) project checks passed.*#\1 \2#p' "$out" | tail -1)
[[ -n "${pp:-}" && "$pp" == "$pt" && "$pp" -ge "$min_project" ]] || fail "cross-project checks ${pp:-?}/${pt:-?} (need all, at least $min_project)"
[[ -z "$fault" ]] || fail "self-test '$fault' was injected but the gate did not catch it"

(cd "$cand" && sha256sum *.gz *.manifest > SHA256SUMS)
echo; echo "GATE PASS: ${#GITCRAFT_TOOLS[@]} tools, glibc <= $ceiling, fresh install $p/$t, cross-project $pp/$pt, installed = candidates"
