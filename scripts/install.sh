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
        ver="$(grep "^$name " "$stage/MANIFEST.txt" 2>/dev/null | cut -d' ' -f3-)"
        echo "prebuilt ${ver:-unknown}" > "$GITCRAFT_BIN/$name.version"
        echo "gitcraft: $name installed (prebuilt $ver)"
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
    echo "source $(git -C "$src" rev-parse --short HEAD) $(date -u +%F)" > "$GITCRAFT_BIN/$name.version"
    echo "gitcraft: $name ready ($((SECONDS - start))s)"
  else
    echo "gitcraft: $name FAILED, see $GITCRAFT_LOG/$name.log" >&2
    failed+=("$name")
  fi
done

# 3) The 3D Department (meshcraft) installs its Python runtimes separately.
if ! ((${#want[@]})) || [[ " ${want[*]} " == *" meshcraft "* ]]; then
  if gitcraft_installed meshcraft x && ((update == 0)); then
    echo "gitcraft: meshcraft already installed"
  elif ! "$here/install-3d.sh" core; then
    failed+=("meshcraft")
  fi
fi

"$here/register.sh"

# Machine-readable result for doctor.sh and for anything orchestrating installs.
python3 - "$GITCRAFT_HOME/status.json" "$GITCRAFT_BIN" "${failed[*]:-}" "${GITCRAFT_TOOLS[@]}" <<'PY'
import json, os, sys, time
out, bindir, failed, tools = sys.argv[1], sys.argv[2], set(sys.argv[3].split()), sys.argv[4:]
st = {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tools": {}}
for e in tools:
    name, _, pkg = e.split(":")
    exe = os.path.join(mchome, "venv", "bin", "python") if name == "meshcraft" else os.path.join(bindir, pkg)
    ok = os.access(exe, os.X_OK) and name not in failed
    ver = open(os.path.join(bindir, name + ".version")).read().strip() if os.path.exists(os.path.join(bindir, name + ".version")) else None
    st["tools"][name] = {"state": "ok" if ok else "failed", "version": ver}
json.dump(st, open(out, "w"), indent=1)
PY

if ((${#failed[@]})); then
  echo "gitcraft: failed: ${failed[*]}" >&2
  exit 1
fi
echo "gitcraft: done"
