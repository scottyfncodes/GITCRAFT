#!/usr/bin/env bash
# Install the 3D Department, on demand. Nothing here is part of the default install or of a setup script: a session
# that needs 3D runs this itself, and the registered MeshCraft and ForgeCraft servers announce their tools when it
# finishes (no /mcp). Blender and the engine check are MeshCraft's; Meshroom, the AI venv and weights go to
# ~/.gitcraft/forgecraft.
#
#   scripts/install-3d.sh                 core: MeshCraft + ForgeCraft (Blender bpy 5.2 ~400 MB, engine check; a few minutes)
#   scripts/install-3d.sh meshroom        + Meshroom 2023.3 / AliceVision (GitHub release, ~1.2 GB download, 2.1 GB on disk)
#   scripts/install-3d.sh ai              + TripoSR code, PyTorch and Hunyuan3D-2 client libraries in a separate venv (~5 GB)
#   scripts/install-3d.sh all
#
# Nothing large is committed to git: every runtime and every model weight is downloaded
# here, into ~/.gitcraft. Model weights (TripoSR ~1.7 GB, Hunyuan3D 5–20 GB) are fetched
# from Hugging Face on first use, or pre-seeded with `scripts/install-3d.sh weights`.
#
# During setup (scripts/tools.sh, "Setup guard") every component here is over the download limit: it is skipped with
# one line and the script exits 0. The capability summary is one line, printed when it changes, never during setup.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(dirname "$here")"
source "$here/tools.sh"
MC="${FORGECRAFT_HOME:-$GITCRAFT_HOME/forgecraft}"
MESHROOM_VERSION="${FORGECRAFT_MESHROOM_VERSION:-2023.3.0}"
mkdir -p "$MC" "$GITCRAFT_LOG"
want=("${@:-core}")
[[ " ${want[*]} " == *" all "* ]] && want=(core meshroom ai)
fail=0

later="a session that needs it runs ~/.gitcraft/runtime/scripts/install-3d.sh"
core() {
  # Blender: ForgeCraft uses MeshCraft's bpy venv, installed by scripts/install.sh meshcraft.
  if ! [[ -x "$GITCRAFT_HOME/meshcraft/venv/bin/python" ]] || ! "$GITCRAFT_HOME/meshcraft/venv/bin/python" -c "import bpy" 2>/dev/null; then
    gitcraft_setup_allows "MeshCraft and ForgeCraft (Blender)" 400 "$later" || return 0
    echo "gitcraft-3d: installing MeshCraft's Blender (scripts/install.sh meshcraft forgecraft)"
    # install.sh records both tools, registers them and comes back here for ForgeCraft once Blender is in. One install
    # at a time: it waits for a background install the SessionStart hook may have started (the same lock), so the two
    # never download Blender twice or overwrite each other's status record.
    local lock=(); command -v flock >/dev/null && lock=(flock "$GITCRAFT_HOME/install.lock")
    GITCRAFT_MESHCRAFT=1 ${lock[@]+"${lock[@]}"} "$here/install.sh" meshcraft forgecraft; return
  fi
  echo "gitcraft-3d: Blender $("$GITCRAFT_HOME/meshcraft/venv/bin/python" -c 'import bpy;print(bpy.app.version_string)' 2>/dev/null | tail -1) (shared with MeshCraft)"
  # the engine check (three@0.170 + Khronos validator) is MeshCraft's: installed with it by install.sh
  gitcraft_engine_check_ready "$repo" || echo "gitcraft-3d: MeshCraft's engine check is not installed (scripts/install.sh meshcraft)" >&2
  echo "forgecraft $(cd "$repo" && git rev-parse --short HEAD 2>/dev/null) $(date -u +%F)" > "$GITCRAFT_BIN/forgecraft.version"
}

meshroom() {
  if ls "$MC"/Meshroom-*/meshroom_batch >/dev/null 2>&1; then echo "gitcraft-3d: Meshroom already installed"; return 0; fi
  gitcraft_setup_allows "Meshroom (photogrammetry)" 1200 "$later meshroom" || return 0
  local url="https://github.com/alicevision/Meshroom/releases/download/v$MESHROOM_VERSION/Meshroom-$MESHROOM_VERSION-linux.tar.gz"
  echo "gitcraft-3d: downloading Meshroom $MESHROOM_VERSION (~1.2 GB)"
  mkdir -p "$MC/dl"
  curl -fL --retry 3 $(gitcraft_curl_cap) -o "$MC/dl/meshroom.tar.gz" "$url" && tar -xzf "$MC/dl/meshroom.tar.gz" -C "$MC" && rm -f "$MC/dl/meshroom.tar.gz" \
    || { echo "gitcraft-3d: Meshroom download/extract failed ($url)" >&2; return 1; }
  echo "gitcraft-3d: Meshroom ready ($(ls -d "$MC"/Meshroom-*))"
}

ai() {
  [[ -x "$MC/ai-venv/bin/python" && -d "$MC/TripoSR/.git" ]] || gitcraft_setup_allows "the 3D AI runtimes (PyTorch, TripoSR, Hunyuan3D)" 5000 "$later ai" || return 0
  [[ -d "$MC/TripoSR/.git" ]] || git clone -q --depth 1 https://github.com/VAST-AI-Research/TripoSR "$MC/TripoSR" || return 1
  [[ -x "$MC/ai-venv/bin/python" ]] || python3 -m venv "$MC/ai-venv" || return 1
  # No NVIDIA GPU: the CPU build of PyTorch (~200 MB) instead of the default CUDA build (~4 GB of GPU libraries
  # that cannot be used here).
  if ! { command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; }; then
    echo "gitcraft-3d: no NVIDIA GPU: installing the CPU build of PyTorch"
    "$MC/ai-venv/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu || { echo "gitcraft-3d: CPU PyTorch install failed" >&2; return 1; }
  fi
  echo "gitcraft-3d: installing PyTorch + TripoSR/Hunyuan3D dependencies (large)"
  "$MC/ai-venv/bin/pip" install -q torch omegaconf einops trimesh "rembg[cpu]" huggingface-hub "transformers<5" xatlas "imageio[ffmpeg]" moderngl gradio_client \
    || { echo "gitcraft-3d: AI dependencies failed; see pip output" >&2; return 1; }
  # torchmcubes (TripoSR's mesh extraction) builds against the PyTorch installed above: no build isolation
  if ! "$MC/ai-venv/bin/python" -c "import torchmcubes" 2>/dev/null; then
    "$MC/ai-venv/bin/pip" install -q scikit-build-core pybind11 cmake ninja &&
    "$MC/ai-venv/bin/pip" install -q --no-build-isolation "git+https://github.com/tatsy/torchmcubes.git" \
      || { echo "gitcraft-3d: torchmcubes build failed (needs a C++ compiler); see pip output" >&2; return 1; }
  fi
  # Hunyuan3D-2 runs locally only on an NVIDIA GPU (its remote mode needs just gradio_client, installed above)
  if ! { command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1; }; then
    echo "gitcraft-3d: no NVIDIA GPU: skipping the local Hunyuan3D-2 install (TripoSR runs on CPU)"; return 0
  fi
  if [[ ! -d "$MC/Hunyuan3D-2/.git" ]]; then git clone -q --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2 "$MC/Hunyuan3D-2" || return 1; fi
  "$MC/ai-venv/bin/pip" install -q -e "$MC/Hunyuan3D-2" || echo "gitcraft-3d: hy3dgen install failed (needs a CUDA toolchain for its extensions on GPU machines)" >&2
}

weights() {
  gitcraft_setup_allows "the 3D model weights (TripoSR, DINO, u2net)" 1900 "$later weights" || return 0
  HF_HOME="$MC/hf-cache" "$MC/ai-venv/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
for repo in ("stabilityai/TripoSR", "facebook/dino-vitb16"):   # TripoSR loads the DINO ViT-B/16 encoder (Apache-2.0)
    print("gitcraft-3d: fetched", snapshot_download(repo))
PY
  # rembg's background-removal model (u2net, ~170 MB, GitHub release) for TripoSR's photo preprocessing
  U2NET_HOME="$MC/u2net" "$MC/ai-venv/bin/python" -c 'import rembg; rembg.new_session("u2net"); print("gitcraft-3d: rembg u2net model ready")' 
}

for w in "${want[@]}"; do
  case "$w" in core|meshroom|ai|weights) "$w" || fail=1 ;; *) echo "unknown component $w" >&2; fail=1 ;; esac
done
"$here/register.sh" >/dev/null 2>&1
# What this machine can do in 3D now: saved for the tools ($MC/probe.json), and said in one line when it differs from
# the last line shown. Never during setup: nothing is probed or reported there (scripts/doctor.sh has the full table).
if ! gitcraft_in_setup && python3 "$repo/gitcraft3d/hardware.py" > "$MC/probe.json.tmp" 2>/dev/null && mv -f "$MC/probe.json.tmp" "$MC/probe.json"; then
  line="$(python3 - "$MC/probe.json" <<'PY'
import json, sys
b = json.load(open(sys.argv[1]))["backends"]
on = [k + (" " + str(v["version"]) if v.get("version") else "") for k, v in b.items() if v.get("available")]
off = [k for k, v in b.items() if not v.get("available")]
print("gitcraft-3d: ready: " + (", ".join(on) or "nothing yet") + (" | not installed or unavailable: " + ", ".join(off) if off else ""))
PY
)"
  if [[ -n "$line" && "$line" != "$(cat "$MC/capabilities.shown" 2>/dev/null)" ]]; then echo "$line"; echo "$line" > "$MC/capabilities.shown"; fi
fi
rm -f "$MC/probe.json.tmp"
exit $fail
