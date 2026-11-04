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
  # this clone's origin first; a fork or local clone without a `bin` branch uses the main repo's builds
  bin_repo="${GITCRAFT_BIN_REPO:-https://github.com/scottyfncodes/GITCRAFT}"
  if { git -C "$repo_dir" fetch -q --depth 1 origin bin 2>/dev/null || git -C "$repo_dir" fetch -q --depth 1 "$bin_repo" bin 2>/dev/null; } &&
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

# Machine-readable result for doctor.sh and for anything orchestrating installs. meshcraft, forgecraft,
# studiocraft and studiocraft-voice are ok | failed | off | later | pending (written before their step, so a run
# cut off during a download says so); "skipped" (not part of this run) keeps the previous record.
status_before=$(cat "$GITCRAFT_HOME/status.json" 2>/dev/null)   # what earlier runs recorded (kept for tools this run skips)
write_status() {
python3 - "$GITCRAFT_HOME/status.json" "$GITCRAFT_BIN" "${failed[*]:-}" "$mesh_state" "$forge_state" "$studio_state" "$voice_state" "$status_before" "${GITCRAFT_TOOLS[@]}" <<'PY'
import json, os, sys, time
out, bindir, failed, mesh, forge, studio, voice, before, tools = sys.argv[1], sys.argv[2], set(sys.argv[3].split()), sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], sys.argv[9:]
try: prev = json.loads(before).get("tools", {})
except Exception: prev = {}
st = {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tools": {}}
for e in tools:
    name, _, pkg = e.split(":")
    ok = os.access(os.path.join(bindir, pkg), os.X_OK) and name not in failed
    ver = open(os.path.join(bindir, name + ".version")).read().strip() if os.path.exists(os.path.join(bindir, name + ".version")) else None
    st["tools"][name] = {"state": "ok" if ok else "failed", "version": ver}
for name, state in (("meshcraft", mesh), ("forgecraft", forge), ("studiocraft", studio), ("studiocraft-voice", voice)):
    if state == "skipped":   # not part of this run: keep what an earlier run recorded
        if name in prev: st["tools"][name] = prev[name]
    else:
        v = os.path.join(bindir, name + ".version")
        st["tools"][name] = {"state": state, "version": open(v).read().strip() if os.path.exists(v) else None}
tmp = out + ".tmp"
json.dump(st, open(tmp, "w"), indent=1); os.replace(tmp, out)
PY
}

# Register the 2D tools before anything slow. Blender is a ~400 MB download and the Studio runtimes another
# ~250 MB (+ the voice model); when a run is cut off during them (a cloud setup script past its time limit, a
# closed terminal), the seven tools above are already in the runtime, registered and documented.
mesh_state=skipped forge_state=skipped studio_state=skipped voice_state=skipped
want_studio=1; ((${#want[@]})) && [[ ! " ${want[*]} " =~ " studiocraft " ]] && want_studio=0
if [[ "$GITCRAFT_STUDIO" != 1 ]]; then studio_state=off voice_state=off
elif ((want_studio)); then
  studio_state=pending   # written before the Studio step, so a run cut off during it says so
  voice_present() { [[ -f "$GITCRAFT_STUDIO_HOME/models/kokoro/voices-v1.0.bin" && -f "$GITCRAFT_STUDIO_HOME/models/kokoro/kokoro-v1.0.int8.onnx" ]]; }
  case "$GITCRAFT_STUDIO_VOICE" in
    0) voice_state=off ;;
    later) voice_present && [[ $update -eq 0 ]] && voice_state=ok || voice_state=later ;;   # the SessionStart hook installs it
    *) voice_present && [[ $update -eq 0 ]] && voice_state=ok || voice_state=pending ;;
  esac
fi
want_mesh=1; ((${#want[@]})) && [[ ! " ${want[*]} " =~ " meshcraft " && ! " ${want[*]} " =~ " forgecraft " ]] && want_mesh=0   # forgecraft needs MeshCraft's Blender
if [[ "$GITCRAFT_MESHCRAFT" == later ]]; then mesh_state=later forge_state=later   # the SessionStart hook builds it
elif [[ "$GITCRAFT_MESHCRAFT" != 1 ]]; then mesh_state=off forge_state=off
elif ((want_mesh)); then mesh_state=pending forge_state=pending; fi
"$here/install-global.sh"   # runtime copy in ~/.gitcraft/runtime, user-scope registration, global instructions
write_status

# 2b) GITCRAFT Studio (the departments): no Blender needed. studiocraft is already registered by the pass above:
#     until its venv lands it lists a status tool, then announces its department tools (studio/server.py). The second
#     install-global pass refreshes the runtime copy; the voice model (the slowest part) comes after that, or later.
if [[ $studio_state == pending ]]; then
  if gitcraft_studio_ready && [[ $update -eq 0 ]]; then echo "gitcraft: studiocraft already installed"; studio_state=ok
  # not fatal: the seven 2D tools are registered already, status.json records it and the SessionStart hook retries it
  else "$here/install-studio.sh" core && studio_state=ok || { studio_state=failed; echo "gitcraft: studiocraft not installed this time (recorded; the SessionStart hook retries it, or run scripts/install.sh studiocraft)" >&2; }; fi
  if [[ $studio_state == ok ]]; then
    # version on every install (installs from before the file existed get one too): commit of the code it runs
    echo "studio $(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null || echo unknown) $(date -u +%F)" > "$GITCRAFT_BIN/studiocraft.version"
    "$here/install-global.sh" >/dev/null && echo "gitcraft: studiocraft registered"
  fi
  write_status
  if [[ $studio_state == ok && $voice_state == pending ]]; then
    if "$here/install-studio.sh" voice; then voice_state=ok
    else voice_state=failed; echo "gitcraft: studio voice runtime not installed; audiocraft_voice will report blocked (scripts/install-studio.sh voice)" >&2; fi
    write_status
  elif [[ $voice_state == later ]]; then
    echo "gitcraft: studio voice model deferred (GITCRAFT_STUDIO_VOICE=later): the SessionStart hook installs it in the background"
  fi
fi

# 3) MeshCraft: Blender as a Python module (bpy from PyPI) in its own venv,
#    plus the Node packages its engine check uses. No compiled GitHub artifact needed.
[[ $mesh_state == pending ]] && mesh_state=skipped
if [[ "$GITCRAFT_MESHCRAFT" == 1 && $want_mesh == 1 ]]; then
  venv="$GITCRAFT_HOME/meshcraft/venv"
  if [[ -x "$venv/bin/python" && $update -eq 0 ]] && "$venv/bin/python" -c "import bpy" 2>/dev/null; then
    echo "gitcraft: meshcraft already installed"; mesh_state=ok
    [[ -f "$GITCRAFT_BIN/meshcraft.version" ]] || echo "blender $("$venv/bin/python" -c 'import bpy;print(bpy.app.version_string)' 2>/dev/null)" > "$GITCRAFT_BIN/meshcraft.version"
  else
    echo "gitcraft: installing meshcraft (Blender bpy wheel, ~400 MB; log: $GITCRAFT_LOG/meshcraft.log)"
    py=$(command -v python3.13 || command -v python3.11 || command -v python3)
    mkdir -p "$GITCRAFT_HOME/meshcraft"
    if { if command -v uv >/dev/null; then uv venv -q --allow-existing -p "$py" "$venv" && VIRTUAL_ENV="$venv" uv pip install -q -r "$repo_dir/meshcraft/requirements.txt";
         else "$py" -m venv "$venv" && "$venv/bin/pip" install -q -r "$repo_dir/meshcraft/requirements.txt"; fi; } >"$GITCRAFT_LOG/meshcraft.log" 2>&1 \
       && "$venv/bin/python" -c "import bpy; print('blender', bpy.app.version_string)" >>"$GITCRAFT_LOG/meshcraft.log" 2>&1; then
      echo "blender $("$venv/bin/python" -c 'import bpy;print(bpy.app.version_string)' 2>/dev/null)" > "$GITCRAFT_BIN/meshcraft.version"
      echo "gitcraft: meshcraft ready ($(cat "$GITCRAFT_BIN/meshcraft.version"))"; mesh_state=ok
    else
      echo "gitcraft: meshcraft FAILED (bpy needs Python 3.11/3.13 matching a published wheel; see $GITCRAFT_LOG/meshcraft.log)" >&2
      failed+=(meshcraft); mesh_state=failed
    fi
  fi
  if command -v npm >/dev/null; then
    (cd "$repo_dir/meshcraft/engine_check" && npm ci --silent --no-audit --no-fund >>"$GITCRAFT_LOG/meshcraft.log" 2>&1) \
      && echo "gitcraft: meshcraft engine check ready (three@0.170, gltf-validator)" \
      || echo "gitcraft: meshcraft engine check unavailable (npm ci failed); exports still validate with pygltflib" >&2
  else
    echo "gitcraft: npm not found; meshcraft's engine check is disabled" >&2
  fi
fi

# 4) ForgeCraft (3D Department) rides on MeshCraft's Blender; its core extra is the engine check.
[[ $forge_state == pending ]] && forge_state=skipped
if [[ $mesh_state == ok ]] && { ! ((${#want[@]})) || [[ " ${want[*]} " =~ " forgecraft " ]]; }; then
  "$here/install-3d.sh" core && forge_state=ok || { forge_state=failed; failed+=(forgecraft); }
fi

# Second pass registers MeshCraft and ForgeCraft once Blender is in (the runtime copy is an rsync).
[[ $mesh_state == ok ]] && "$here/install-global.sh"
write_status

if ((${#failed[@]})); then
  echo "gitcraft: failed: ${failed[*]}" >&2
  exit 1
fi
echo "gitcraft: done"
