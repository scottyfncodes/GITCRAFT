#!/usr/bin/env bash
# Install the GITCRAFT Studio runtimes (the department layer: audio, animation, worlds, FX, materials,
# levels, cinematics, QA, assets) into ~/.gitcraft/studio. Nothing large is committed to git.
#
#   scripts/install-studio.sh            core: Python venv (numpy, Pillow) + Node runtime (three, Phaser, glTF-Validator)
#   scripts/install-studio.sh voice      + AudioCraft voice: Kokoro-82M (Apache-2.0) via kokoro-onnx in its own venv,
#                                          model files (~120 MB) from the kokoro-onnx GitHub release, SHA-256 checked
#   scripts/install-studio.sh mocap      + AnimCraft mocap: MediaPipe Pose Landmarker (Apache-2.0) in its own venv, the pose
#                                          models (~40 MB) from storage.googleapis.com (pinned v1), SHA-256 checked; needs the
#                                          system EGL/GLES libraries (apt-get install libegl1 libgles2)
#   scripts/install-studio.sh music      opt-in, large: ACE-Step 1.5 (MIT) at a pinned tag with its own uv venv (CUDA PyTorch on
#                                          Linux, ~10 GB) and its checkpoints from huggingface.co (the environment must allow it)
#   scripts/install-studio.sh unirig     GPU machines only: UniRig (MIT) with CUDA PyTorch, spconv, torch_scatter/cluster, flash-attn,
#                                          checkpoint from huggingface.co; refuses without nvidia-smi
#   scripts/install-studio.sh all        core + voice + mocap (music and unirig are never implied)
#
# Blender-based departments (animcraft, cinematiccraft, worldcraft sky, fxcraft destruction) use
# MeshCraft's Blender (scripts/install.sh meshcraft); they report `blocked` with that command until it exists.
# FFmpeg and Playwright/Chromium are system tools: departments that need them report what is missing.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(dirname "$here")"
source "$here/tools.sh"
SH="${GITCRAFT_STUDIO_HOME:-$GITCRAFT_HOME/studio}"
mkdir -p "$SH" "$GITCRAFT_LOG"
log="$GITCRAFT_LOG/studio.log"
want=("${@:-core}")
[[ " ${want[*]} " == *" all "* ]] && want=(core voice mocap)
fail=0
py=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)

# Each download step has a time limit: a stalled mirror must not eat a cloud setup script's budget (one fresh
# setup spent 5.5 minutes in a stalled `pip install numpy`). A step that times out fails, install.sh records it,
# and the SessionStart hook retries it in the background.
STEP_LIMIT="${GITCRAFT_STUDIO_STEP_TIMEOUT:-120}"
limit() { if command -v timeout >/dev/null; then timeout "$STEP_LIMIT" "$@"; else "$@"; fi; }
mkvenv() {   # mkvenv <dir> <requirements>
  if command -v uv >/dev/null; then uv venv -q --allow-existing -p "$py" "$1" && VIRTUAL_ENV="$1" limit uv pip install -q -r "$2"
  else { [[ -x "$1/bin/python" ]] || "$py" -m venv "$1"; } && limit "$1/bin/pip" install -q -r "$2"; fi
}

core() {
  echo "gitcraft-studio: core venv (numpy, Pillow) → $SH/venv"
  mkvenv "$SH/venv" "$repo/studio/requirements.txt" >>"$log" 2>&1 || { echo "gitcraft-studio: core venv FAILED or timed out after ${STEP_LIMIT}s (see $log)" >&2; return 1; }
  if command -v npm >/dev/null; then
    mkdir -p "$SH/node"; cp "$repo/studio/node/package.json" "$repo/studio/node/package-lock.json" "$SH/node/"
    if (cd "$SH/node" && limit npm ci --silent --no-audit --no-fund) >>"$log" 2>&1; then echo "gitcraft-studio: node runtime ready (three 0.170.0, phaser 3.90.0, gltf-validator)"
    else echo "gitcraft-studio: npm ci failed; engine checks will report blocked (see $log)" >&2; fi
  else
    echo "gitcraft-studio: npm not found; engine checks (three.js, Phaser) will report blocked" >&2
  fi
  command -v ffmpeg >/dev/null || echo "gitcraft-studio: ffmpeg not found: audio conversion and video encoding will report blocked (apt-get install ffmpeg)" >&2
  echo "studio $(cd "$repo" && git rev-parse --short HEAD 2>/dev/null) $(date -u +%F)" > "$GITCRAFT_BIN/studiocraft.version"
}

KOKORO_URL="https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
KOKORO_FILES=("kokoro-v1.0.int8.onnx:6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb"
              "voices-v1.0.bin:bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d")
voice() {
  echo "gitcraft-studio: voice venv (kokoro-onnx, onnxruntime) → $SH/voice-venv"
  mkvenv "$SH/voice-venv" "$repo/studio/requirements-voice.txt" >>"$log" 2>&1 || { echo "gitcraft-studio: voice venv FAILED or timed out after ${STEP_LIMIT}s (see $log)" >&2; return 1; }
  mkdir -p "$SH/models/kokoro"
  for e in "${KOKORO_FILES[@]}"; do
    f=${e%%:*}; sum=${e##*:}; dst="$SH/models/kokoro/$f"
    if [[ -f "$dst" ]] && echo "$sum  $dst" | sha256sum -c --quiet 2>/dev/null; then continue; fi
    echo "gitcraft-studio: downloading $f"
    curl -fsSL --retry 3 --max-time "$STEP_LIMIT" -o "$dst.part" "$KOKORO_URL/$f" || { echo "gitcraft-studio: download of $f failed (GitHub release blocked?)" >&2; rm -f "$dst.part"; return 1; }
    echo "$sum  $dst.part" | sha256sum -c --quiet || { echo "gitcraft-studio: $f checksum mismatch; not installed" >&2; rm -f "$dst.part"; return 1; }
    mv "$dst.part" "$dst"
  done
  echo "gitcraft-studio: voice ready (Kokoro-82M v1.0 int8, 54 voices)"
}

MP_URL="https://storage.googleapis.com/mediapipe-models/pose_landmarker"
MP_FILES=("full:5134a3aad27a58b93da0088d431f366da362b44e3ccfbe3462b3827a839011b1"
          "heavy:64437af838a65d18e5ba7a0d39b465540069bc8aae8308de3e318aad31fcbc7b")
mocap() {
  echo "gitcraft-studio: mocap venv (mediapipe) → $SH/mocap-venv"
  mkvenv "$SH/mocap-venv" "$repo/studio/requirements-mocap.txt" >>"$log" 2>&1 || { echo "gitcraft-studio: mocap venv FAILED or timed out after ${STEP_LIMIT}s (see $log)" >&2; return 1; }
  if ! ldconfig -p 2>/dev/null | grep -q 'libEGL.so.1'; then
    # MediaPipe loads the system EGL/GLES libraries. As root with apt (cloud containers), install them; a fresh
    # container has an empty package index, so update it first.
    if [[ $(id -u) == 0 ]] && command -v apt-get >/dev/null; then
      echo "gitcraft-studio: installing the system EGL/GLES libraries for MediaPipe (libegl1, libgles2)"
      { limit apt-get update -qq && DEBIAN_FRONTEND=noninteractive limit apt-get install -y -qq libegl1 libgles2; } >>"$log" 2>&1 ||
        echo "gitcraft-studio: apt-get could not install libegl1/libgles2 (see $log); animcraft_mocap will report blocked" >&2
    fi
    ldconfig -p 2>/dev/null | grep -q 'libEGL.so.1' ||
      echo "gitcraft-studio: libEGL.so.1 not found: MediaPipe cannot load until the system EGL libraries are installed (apt-get install libegl1 libgles2)" >&2
  fi
  mkdir -p "$SH/models/mediapipe"
  for e in "${MP_FILES[@]}"; do
    m=${e%%:*}; sum=${e##*:}; dst="$SH/models/mediapipe/pose_landmarker_$m.task"
    if [[ -f "$dst" ]] && echo "$sum  $dst" | sha256sum -c --quiet 2>/dev/null; then continue; fi
    echo "gitcraft-studio: downloading pose_landmarker_$m.task"
    curl -fsSL --retry 3 --max-time "$STEP_LIMIT" -o "$dst.part" "$MP_URL/pose_landmarker_$m/float16/1/pose_landmarker_$m.task" || { echo "gitcraft-studio: download of pose_landmarker_$m failed" >&2; rm -f "$dst.part"; return 1; }
    echo "$sum  $dst.part" | sha256sum -c --quiet || { echo "gitcraft-studio: pose_landmarker_$m checksum mismatch; not installed" >&2; rm -f "$dst.part"; return 1; }
    mv "$dst.part" "$dst"
  done
  echo "gitcraft-studio: mocap ready (MediaPipe Pose Landmarker full + heavy)"
}

BIG_LIMIT="${GITCRAFT_STUDIO_BIG_TIMEOUT:-3600}"   # music/unirig pull PyTorch and multi-GB weights
ACE_REPO="https://github.com/ace-step/ACE-Step-1.5"; ACE_TAG="v0.1.8"
fetch_repo() {   # fetch_repo <url> <ref> <dir>: shallow checkout of a pinned tag or commit
  mkdir -p "$3" && git -C "$3" init -q 2>/dev/null && { git -C "$3" remote add origin "$1" 2>/dev/null || git -C "$3" remote set-url origin "$1"; } &&
    timeout "$BIG_LIMIT" git -C "$3" fetch -q --depth 1 origin "$2" && git -C "$3" checkout -q --force FETCH_HEAD
}
need_hf() {
  curl -fsS -o /dev/null --max-time 20 https://huggingface.co/api/models/"$1" 2>/dev/null && return 0
  echo "gitcraft-studio: huggingface.co is not reachable from this environment, so the $1 weights cannot be downloaded." >&2
  echo "  Allow huggingface.co (and *.hf.co, cdn-lfs.huggingface.co) in the environment's network policy, then run this again (docs/security.md)." >&2
  return 1
}
music() {
  command -v uv >/dev/null || { echo "gitcraft-studio: music needs uv (pip install uv)" >&2; return 1; }
  need_hf ACE-Step/Ace-Step1.5 || return 1
  echo "gitcraft-studio: ACE-Step 1.5 $ACE_TAG → $SH/ace-step (PyTorch + weights: this takes a while)"
  fetch_repo "$ACE_REPO" "$ACE_TAG" "$SH/ace-step" >>"$log" 2>&1 || { echo "gitcraft-studio: could not fetch $ACE_REPO@$ACE_TAG (see $log)" >&2; return 1; }
  (cd "$SH/ace-step" && timeout "$BIG_LIMIT" uv sync -q) >>"$log" 2>&1 || { echo "gitcraft-studio: ACE-Step uv sync failed (see $log)" >&2; return 1; }
  (cd "$SH/ace-step" && HF_HOME="$SH/ace-step/hf-cache" timeout "$BIG_LIMIT" .venv/bin/python -m acestep.model_downloader) >>"$log" 2>&1 ||
    { echo "gitcraft-studio: ACE-Step checkpoint download failed (see $log)" >&2; return 1; }
  command -v nvidia-smi >/dev/null || echo "gitcraft-studio: no NVIDIA GPU: audiocraft_music_model will run on CPU (minutes per 30 s)" >&2
  echo "gitcraft-studio: music ready (ACE-Step 1.5 turbo; audiocraft_music_model)"
}
UNIRIG_REPO="https://github.com/VAST-AI-Research/UniRig"; UNIRIG_REF="6793c6640ff01c8fb389f3993434124bb43d2933"
unirig() {
  command -v nvidia-smi >/dev/null && nvidia-smi -L >/dev/null 2>&1 || { echo "gitcraft-studio: UniRig needs an NVIDIA GPU (≥ 8 GB VRAM); not installed. animcraft_autorig works on CPU." >&2; return 1; }
  need_hf VAST-AI/UniRig || return 1
  echo "gitcraft-studio: UniRig @ ${UNIRIG_REF:0:7} → $SH/unirig"
  fetch_repo "$UNIRIG_REPO" "$UNIRIG_REF" "$SH/unirig" >>"$log" 2>&1 || { echo "gitcraft-studio: could not fetch UniRig (see $log)" >&2; return 1; }
  local cu; cu=$(nvidia-smi | sed -n 's/.*CUDA Version: \([0-9]*\)\.\([0-9]*\).*/cu\1\2/p' | head -1)
  local u=(uv pip install -q --python "$SH/unirig/.venv/bin/python")
  ( set -e; cd "$SH/unirig"; uv venv -q --allow-existing -p 3.11 .venv
    timeout "$BIG_LIMIT" "${u[@]}" torch torchvision
    timeout "$BIG_LIMIT" "${u[@]}" -r requirements.txt
    tv=$(.venv/bin/python -c 'import torch;print(torch.__version__.split("+")[0])'); tc=$(.venv/bin/python -c 'import torch;print("cu"+torch.version.cuda.replace(".",""))')
    timeout "$BIG_LIMIT" "${u[@]}" "spconv-${tc:0:4}" || timeout "$BIG_LIMIT" "${u[@]}" "spconv-${cu:-cu120}"
    timeout "$BIG_LIMIT" "${u[@]}" torch_scatter torch_cluster -f "https://data.pyg.org/whl/torch-${tv}+${tc}.html"
    timeout "$BIG_LIMIT" "${u[@]}" numpy==1.26.4
    HF_HOME="$SH/unirig/hf-cache" timeout "$BIG_LIMIT" .venv/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("VAST-AI/UniRig")'
  ) >>"$log" 2>&1 || { echo "gitcraft-studio: UniRig install failed (flash-attn/spconv builds are the usual cause; see $log)" >&2; return 1; }
  echo "gitcraft-studio: UniRig ready (animcraft_autorig_ml)"
}

for w in "${want[@]}"; do
  case "$w" in core|voice|mocap|music|unirig) "$w" || fail=1 ;; *) echo "unknown component $w" >&2; fail=1 ;; esac
done
exit $fail
