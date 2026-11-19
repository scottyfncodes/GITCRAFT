#!/usr/bin/env bash
# Print the immutable setup line for a cloud environment pinned to one reviewed GITCRAFT commit.
#
#   scripts/setup-pin.sh <full commit SHA> [VAR=value ...]     e.g. scripts/setup-pin.sh 1a2b...  GITCRAFT_MESHCRAFT=later
#
# Both halves are pinned to that commit, so nothing that runs at container start can change after review:
#   1. the bootstrap (setup-env.sh) is downloaded from the commit-addressed URL and checked against its SHA-256
#      before it runs (a mismatch stops the line: nothing runs);
#   2. GITCRAFT_REF=<the same SHA> makes setup-env.sh install exactly that commit, which must be on main.
# The commit must be on origin/main and new enough to support commit pins; otherwise nothing is printed (exit 1).
# Prints only; it changes nothing. Paste the line into the environment's setup script (docs/install.md, "Pinning").
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(dirname "$here")"
sha="${1:-}"; shift || true
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "usage: setup-pin.sh <full 40-character commit SHA> [VAR=value ...]" >&2; exit 2; }
for v in "$@"; do [[ "$v" =~ ^GITCRAFT_[A-Z0-9_]+=[A-Za-z0-9._:/-]*$ ]] || { echo "setup-pin.sh: refusing extra argument '$v' (only GITCRAFT_*=value)" >&2; exit 2; }; done
url="$(git -C "$repo" config --get remote.origin.url)"   # as configured (a test may redirect the fetches with insteadOf)
slug="$(sed -nE 's#^(https://github\.com/|git@github\.com:)([^/]+/[^/.]+)(\.git)?/?$#\2#p' <<<"$url")"
[[ -n "$slug" ]] || { echo "setup-pin.sh: origin ($url) is not a GitHub repository" >&2; exit 1; }
git -C "$repo" fetch -q origin main || { echo "setup-pin.sh: cannot fetch origin main" >&2; exit 1; }
main_tip="$(git -C "$repo" rev-parse FETCH_HEAD)"   # recorded now: a later fetch moves FETCH_HEAD
git -C "$repo" cat-file -e "$sha^{commit}" 2>/dev/null || git -C "$repo" fetch -q origin "$sha" 2>/dev/null
git -C "$repo" merge-base --is-ancestor "$sha" "$main_tip" 2>/dev/null \
  || { echo "setup-pin.sh: $sha is not on $slug main: only reviewed, merged commits are pinned" >&2; exit 1; }
git -C "$repo" cat-file -e "$sha:scripts/setup-env.sh" 2>/dev/null || { echo "setup-pin.sh: $sha has no scripts/setup-env.sh" >&2; exit 1; }
git -C "$repo" cat-file blob "$sha:scripts/setup-env.sh" | grep -q 'pinned install REFUSED' \
  || { echo "setup-pin.sh: setup-env.sh at $sha predates commit pins; pin a newer commit" >&2; exit 1; }
sum="$(git -C "$repo" cat-file blob "$sha:scripts/setup-env.sh" | sha256sum | cut -d' ' -f1)"   # the file exactly as stored
extra=""; for v in "$@"; do extra+="$v "; done
cat <<EOF
curl -fsSL -o /tmp/gitcraft-setup-env.sh https://raw.githubusercontent.com/$slug/$sha/scripts/setup-env.sh \\
  && echo "$sum  /tmp/gitcraft-setup-env.sh" | sha256sum --check --quiet - \\
  && GITCRAFT_REF=$sha ${extra}bash /tmp/gitcraft-setup-env.sh
EOF
