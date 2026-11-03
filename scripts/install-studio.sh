#!/usr/bin/env bash
# Install the GITCRAFT Studio runtimes (the department layer: audio, animation, worlds, FX, materials,
# levels, cinematics, QA, assets) into ~/.gitcraft/studio. Nothing large is committed to git.
#
#   scripts/install-studio.sh            core: Python venv (numpy, Pillow) + Node runtime (three, Phaser, glTF-Validator)
#   scripts/install-studio.sh voice      + AudioCraft voice: Kokoro-82M (Apache-2.0) via kokoro-onnx in its own venv,
#                                          model files (~120 MB) from the kokoro-onnx GitHub release, SHA-256 checked
#   scripts/install-studio.sh all
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
[[ " ${want[*]} " == *" all "* ]] && want=(core voice)
fail=0
py=$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)

mkvenv() {   # mkvenv <dir> <requirements>
  if command -v uv >/dev/null; then uv venv -q --allow-existing -p "$py" "$1" && VIRTUAL_ENV="$1" uv pip install -q -r "$2"
  else { [[ -x "$1/bin/python" ]] || "$py" -m venv "$1"; } && "$1/bin/pip" install -q -r "$2"; fi
}

core() {
  echo "gitcraft-studio: core venv (numpy, Pillow) → $SH/venv"
  mkvenv "$SH/venv" "$repo/studio/requirements.txt" >>"$log" 2>&1 || { echo "gitcraft-studio: core venv FAILED (see $log)" >&2; return 1; }
  if command -v npm >/dev/null; then
    mkdir -p "$SH/node"; cp "$repo/studio/node/package.json" "$repo/studio/node/package-lock.json" "$SH/node/"
    if (cd "$SH/node" && npm ci --silent --no-audit --no-fund) >>"$log" 2>&1; then echo "gitcraft-studio: node runtime ready (three 0.170.0, phaser 3.90.0, gltf-validator)"
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
  mkvenv "$SH/voice-venv" "$repo/studio/requirements-voice.txt" >>"$log" 2>&1 || { echo "gitcraft-studio: voice venv FAILED (see $log)" >&2; return 1; }
  mkdir -p "$SH/models/kokoro"
  for e in "${KOKORO_FILES[@]}"; do
    f=${e%%:*}; sum=${e##*:}; dst="$SH/models/kokoro/$f"
    if [[ -f "$dst" ]] && echo "$sum  $dst" | sha256sum -c --quiet 2>/dev/null; then continue; fi
    echo "gitcraft-studio: downloading $f"
    curl -fsSL --retry 3 -o "$dst.part" "$KOKORO_URL/$f" || { echo "gitcraft-studio: download of $f failed (GitHub release blocked?)" >&2; rm -f "$dst.part"; return 1; }
    echo "$sum  $dst.part" | sha256sum -c --quiet || { echo "gitcraft-studio: $f checksum mismatch; not installed" >&2; rm -f "$dst.part"; return 1; }
    mv "$dst.part" "$dst"
  done
  echo "gitcraft-studio: voice ready (Kokoro-82M v1.0 int8, 54 voices)"
}

for w in "${want[@]}"; do
  case "$w" in core|voice) "$w" || fail=1 ;; *) echo "unknown component $w" >&2; fail=1 ;; esac
done
exit $fail
