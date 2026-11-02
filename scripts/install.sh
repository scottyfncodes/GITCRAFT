#!/usr/bin/env bash
# Install the ArtCraft CLIs into ~/.gitcraft/bin and register them with Claude Code.
#
#   scripts/install.sh                 install anything missing (prebuilt first, source as fallback)
#   scripts/install.sh --update        refresh everything
#   scripts/install.sh --source        skip prebuilts, compile from source
#   scripts/install.sh photocraft ...  only these tools
#
# Prebuilts come from this repo's `bin` branch, which the "Build ArtCraft CLIs"
# GitHub Action keeps up to date. Compiling from source needs Rust 1.95+,
# access to crates.io, and a lot of patience.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname "$here")"
source "$here/tools.sh"

update=0 source_only=0
want=()
for a in "$@"; do
  case "$a" in
    --update) update=1 ;;
    --source) source_only=1 ;;
    -h|--help) sed -n 2,12p "$0"; exit 0 ;;
    *) want+=("$a") ;;
  esac
done

mkdir -p "$GITCRAFT_BIN" "$GITCRAFT_SRC" "$GITCRAFT_LOG"

todo=()
for entry in "${GITCRAFT_TOOLS[@]}"; do
  IFS=: read -r name _ pkg <<<"$entry"
  if ((${#want[@]})) && [[ ! " ${want[*]} " =~ " $name " ]]; then continue; fi
  if [[ -x "$GITCRAFT_BIN/$pkg" && $update -eq 0 ]]; then
    echo "gitcraft: $name already installed"
  else
    todo+=("$entry")
  fi
done

# 1) Prebuilt binaries from the bin branch.
if ((${#todo[@]})) && ((source_only == 0)); then
  stage="$(mktemp -d)"
  if git -C "$repo_dir" fetch -q --depth 1 origin bin 2>/dev/null &&
     git -C "$repo_dir" archive FETCH_HEAD | tar -x -C "$stage"; then
    left=()
    for entry in "${todo[@]}"; do
      IFS=: read -r name _ pkg <<<"$entry"
      if [[ -f "$stage/$pkg.gz" ]] && gunzip -c "$stage/$pkg.gz" > "$GITCRAFT_BIN/$pkg.tmp"; then
        chmod 755 "$GITCRAFT_BIN/$pkg.tmp" && mv "$GITCRAFT_BIN/$pkg.tmp" "$GITCRAFT_BIN/$pkg"
        echo "gitcraft: $name installed (prebuilt $(grep "^$name " "$stage/MANIFEST.txt" 2>/dev/null | cut -d' ' -f3-))"
      else
        rm -f "$GITCRAFT_BIN/$pkg.tmp"
        left+=("$entry")
      fi
    done
    todo=("${left[@]}")
  else
    echo "gitcraft: no prebuilt bin branch yet; falling back to source"
  fi
  rm -rf "$stage"
fi

# 2) Anything still missing gets compiled.
failed=()
if ((${#todo[@]})); then
  if ! command -v cargo >/dev/null; then
    echo "gitcraft: cargo not found, can't build: ${todo[*]%%:*}" >&2
    failed+=("${todo[@]%%:*}")
    todo=()
  fi
  export CARGO_TARGET_DIR="$GITCRAFT_TARGET"
fi
for entry in "${todo[@]}"; do
  IFS=: read -r name repo pkg <<<"$entry"
  src="$GITCRAFT_SRC/$repo"
  if [[ -d "$src/.git" ]]; then
    git -C "$src" pull -q --ff-only
  else
    echo "gitcraft: cloning storytold/$repo"
    GIT_LFS_SKIP_SMUDGE=1 git clone -q --depth 1 "https://github.com/storytold/$repo" "$src" || { failed+=("$name"); continue; }
  fi
  echo "gitcraft: building $pkg from source (log: $GITCRAFT_LOG/$name.log)"
  start=$SECONDS
  if (cd "$src" && cargo build --release --locked -p "$pkg") >"$GITCRAFT_LOG/$name.log" 2>&1; then
    install -m 755 "$GITCRAFT_TARGET/release/$pkg" "$GITCRAFT_BIN/$pkg"
    echo "gitcraft: $name ready ($((SECONDS - start))s)"
  else
    echo "gitcraft: $name FAILED, see $GITCRAFT_LOG/$name.log" >&2
    failed+=("$name")
  fi
done

"$here/register.sh"

if ((${#failed[@]})); then
  echo "gitcraft: failed: ${failed[*]}" >&2
  exit 1
fi
echo "gitcraft: done"
