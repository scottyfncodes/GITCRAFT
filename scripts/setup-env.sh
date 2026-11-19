#!/usr/bin/env bash
# One-step GITCRAFT setup for a fresh Claude Code environment: every tool, available in every project.
#
# Cloud: paste this line into the environment's *Setup script* (cloud environment menu ▸ Edit ▸
# Setup script). It runs whenever a new container is built, before Claude Code starts, so every
# session in that environment has the tools, whichever repos are attached (none needed):
#
#   curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
#
# Workstation: run the same line once; ~/.claude.json and ~/.claude persist, so every later
# session in every project inherits it. Re-run it to update.
#
# What it does: clones GITCRAFT to ~/.gitcraft/repo, installs the seven ArtCraft tools
# (prebuilt), the Studio departments (StudioCraft), MeshCraft (Blender bpy) and ForgeCraft, copies the
# launcher and tool code to ~/.gitcraft/runtime, registers all ten MCP servers at user scope from that runtime,
# installs the GITCRAFT instruction block in ~/.claude/CLAUDE.md and the `gitcraft` skill,
# then prints a health check.
#
#   GITCRAFT_REF=<branch|tag>         install that ref instead of the default branch
#   GITCRAFT_REF=<full commit SHA>    install exactly that commit, which must be on the repository's main (reviewed):
#                                     fetched, checked out detached, verified and cleaned before anything runs; any
#                                     failure stops the setup (nothing is installed). docs/install.md, "Pinning"
#   GITCRAFT_REPO_URL=<url|path>      install from a fork or local clone
#   GITCRAFT_GLOBAL_INSTRUCTIONS=0    skip the CLAUDE.md block and the skill
#   GITCRAFT_MESHCRAFT=0              skip the 3D tools (Blender is ~400 MB)
#   GITCRAFT_STUDIO=0                 skip the Studio departments
#   GITCRAFT_STUDIO_VOICE=later|0     voice model in the background at the first session / not at all
#   extra arguments go to install.sh  (e.g. --update, or tool names)
set -uo pipefail
repo_url="${GITCRAFT_REPO_URL:-https://github.com/scottyfncodes/GITCRAFT}"
home="${GITCRAFT_HOME:-$HOME/.gitcraft}"
dest="$home/repo"
ref="${GITCRAFT_REF:-}"
reviewed="${GITCRAFT_REVIEWED_BRANCH:-main}"   # a pinned commit must be contained in this branch of the repository
mkdir -p "$home/logs"
pin_fail() { echo "gitcraft: pinned install REFUSED: $*. Nothing was installed." >&2; exit 1; }
if [[ "$ref" =~ ^[0-9a-fA-F]{7,39}$ ]]; then
  pin_fail "GITCRAFT_REF=$ref looks like an abbreviated commit; pin the full 40-character commit SHA"
elif [[ "$ref" =~ ^[0-9a-fA-F]{40}$ ]]; then
  # A commit pin: the exact, content-addressed revision, never a branch or tag that can move. Fail closed at every step.
  pin="${ref,,}"
  if [[ ! -d "$dest/.git" ]]; then mkdir -p "$dest" && git -C "$dest" init -q || pin_fail "cannot create $dest"; fi
  git -C "$dest" remote remove origin 2>/dev/null; git -C "$dest" remote add origin "$repo_url" || pin_fail "cannot set the remote $repo_url"
  # the whole commit graph of the reviewed branch (commits only; file contents come with the checkout), unshallowing a
  # clone an earlier setup made, so an older pin (a rollback) is still found on it
  unshallow=(); [[ "$(git -C "$dest" rev-parse --is-shallow-repository 2>/dev/null)" == true ]] && unshallow=(--unshallow)
  git -C "$dest" fetch -q "${unshallow[@]}" --filter=tree:0 origin "+refs/heads/$reviewed:refs/remotes/origin/$reviewed" 2>/dev/null \
    || git -C "$dest" fetch -q "${unshallow[@]}" origin "+refs/heads/$reviewed:refs/remotes/origin/$reviewed" \
    || pin_fail "cannot fetch $reviewed from $repo_url"
  [[ "$(git -C "$dest" rev-parse -q --verify "$pin^{commit}")" == "$pin" ]] \
    || pin_fail "commit $pin is not on $reviewed of $repo_url (or does not exist): only reviewed, merged commits are installed"
  git -C "$dest" merge-base --is-ancestor "$pin" "refs/remotes/origin/$reviewed" \
    || pin_fail "commit $pin is not on $reviewed of $repo_url: only reviewed, merged commits are installed"
  git -C "$dest" -c advice.detachedHead=false checkout -q --force --detach "$pin" || pin_fail "cannot check out $pin"
  git -C "$dest" clean -q -ffdx || pin_fail "cannot clean $dest"
  [[ "$(git -C "$dest" rev-parse HEAD)" == "$pin" && -z "$(git -C "$dest" status --porcelain)" ]] \
    || pin_fail "$dest is not exactly $pin after checkout"
  echo "gitcraft: pinned to $pin (verified on $reviewed of $repo_url)"
elif [[ -d "$dest/.git" ]]; then
  if [[ -n "$ref" ]]; then git -C "$dest" fetch -q --depth 1 origin "$ref" && git -C "$dest" checkout -q -B "$ref" FETCH_HEAD
  else git -C "$dest" pull -q --ff-only; fi || echo "gitcraft: couldn't update $dest; using the copy on disk" >&2
else
  git clone -q --depth 1 ${ref:+--branch "$ref"} "$repo_url" "$dest" || { echo "gitcraft: clone of $repo_url failed" >&2; exit 1; }
fi
"$dest/scripts/install.sh" "$@" 2>&1 | tee "$home/logs/install.log"
status=${PIPESTATUS[0]}
"$home/runtime/scripts/doctor.sh" --brief 2>/dev/null || "$dest/scripts/doctor.sh" --brief || true
exit "$status"
