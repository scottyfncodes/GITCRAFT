#!/usr/bin/env bash
# Install the GITCRAFT 3D Department (ForgeCraft) runtimes into ~/.gitcraft/forgecraft.
#
#   scripts/install-3d.sh                 core: Blender (MeshCraft's bpy 5.2 venv) + engine check (three.js, glTF validator)
#   scripts/install-3d.sh meshroom        + Meshroom 2023.3 / AliceVision (GitHub release, ~1.2 GB download, 2.1 GB on disk)
#   scripts/install-3d.sh ai              + TripoSR code, PyTorch and Hunyuan3D-2 client libraries in a separate venv (~5 GB)
#   scripts/install-3d.sh all
#
# Nothing large is committed to git: every runtime and every model weight is downloaded
# here, into ~/.gitcraft. Model weights (TripoSR ~1.7 GB, Hunyuan3D 5–20 GB) are fetched
# from Hugging Face on first use, or pre-seeded with `scripts/install-3d.sh weights`.
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

core() {
  # Blender: ForgeCraft uses MeshCraft's bpy venv, installed by scripts/install.sh meshcraft.
  if ! [[ -x "$GITCRAFT_HOME/meshcraft/venv/bin/python" ]] || ! "$GITCRAFT_HOME/meshcraft/venv/bin/python" -c "import bpy" 2>/dev/null; then
    echo "gitcraft-3d: MeshCraft's Blender is missing; installing it via scripts/install.sh meshcraft"
    GITCRAFT_MESHCRAFT=1 "$here/install.sh" meshcraft || { echo "gitcraft-3d: Blender (meshcraft) install failed" >&2; return 1; }
  fi
  echo "gitcraft-3d: Blender $("$GITCRAFT_HOME/meshcraft/venv/bin/python" -c 'import bpy;print(bpy.app.version_string)' 2>/dev/null | tail -1) (shared with MeshCraft)"
  if command -v npm >/dev/null; then
    (cd "$repo/forgecraft/web-check" && npm ci -q --no-audit --no-fund >/dev/null 2>&1) \
      && echo "gitcraft-3d: engine check ready (three.js r170 + Khronos glTF-Validator)" \
      || echo "gitcraft-3d: npm ci for forgecraft/web-check failed; ForgeCraft falls back to MeshCraft's engine_check install (same versions), else assets are marked unverified" >&2
  else
    echo "gitcraft-3d: npm not found; validation will skip the three.js / glTF-Validator check" >&2
  fi
  node -e "require('playwright')" 2>/dev/null || echo "gitcraft-3d: playwright not found; the three.js load check needs it (npm i -g playwright && npx playwright install chromium)" >&2
  echo "forgecraft $(cd "$repo" && git rev-parse --short HEAD 2>/dev/null) $(date -u +%F)" > "$GITCRAFT_BIN/forgecraft.version"
}

meshroom() {
  if ls "$MC"/Meshroom-*/meshroom_batch >/dev/null 2>&1; then echo "gitcraft-3d: Meshroom already installed"; return 0; fi
  local url="https://github.com/alicevision/Meshroom/releases/download/v$MESHROOM_VERSION/Meshroom-$MESHROOM_VERSION-linux.tar.gz"
  echo "gitcraft-3d: downloading Meshroom $MESHROOM_VERSION (~1.2 GB)"
  mkdir -p "$MC/dl"
  curl -fL --retry 3 -o "$MC/dl/meshroom.tar.gz" "$url" && tar -xzf "$MC/dl/meshroom.tar.gz" -C "$MC" && rm -f "$MC/dl/meshroom.tar.gz" \
    || { echo "gitcraft-3d: Meshroom download/extract failed ($url)" >&2; return 1; }
  echo "gitcraft-3d: Meshroom ready ($(ls -d "$MC"/Meshroom-*))"
}

ai() {
  [[ -d "$MC/TripoSR/.git" ]] || git clone -q --depth 1 https://github.com/VAST-AI-Research/TripoSR "$MC/TripoSR" || return 1
  [[ -x "$MC/ai-venv/bin/python" ]] || python3 -m venv "$MC/ai-venv" || return 1
  echo "gitcraft-3d: installing PyTorch + TripoSR/Hunyuan3D dependencies (large)"
  "$MC/ai-venv/bin/pip" install -q torch omegaconf einops trimesh rembg huggingface-hub "transformers<5" xatlas imageio gradio_client \
    "git+https://github.com/tatsy/torchmcubes.git" || { echo "gitcraft-3d: AI dependencies failed; see pip output" >&2; return 1; }
  if [[ ! -d "$MC/Hunyuan3D-2/.git" ]]; then git clone -q --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2 "$MC/Hunyuan3D-2" || return 1; fi
  "$MC/ai-venv/bin/pip" install -q -e "$MC/Hunyuan3D-2" || echo "gitcraft-3d: hy3dgen install failed (needs a CUDA toolchain for its extensions on GPU machines)" >&2
}

weights() {
  HF_HOME="$MC/hf-cache" "$MC/ai-venv/bin/python" - <<'PY'
from huggingface_hub import snapshot_download
for repo in ("stabilityai/TripoSR",):
    print("gitcraft-3d: fetched", snapshot_download(repo))
PY
}

for w in "${want[@]}"; do
  case "$w" in core|meshroom|ai|weights) "$w" || fail=1 ;; *) echo "unknown component $w" >&2; fail=1 ;; esac
done
"$here/register.sh" >/dev/null 2>&1
python3 "$repo/forgecraft/hardware.py" > "$MC/probe.json" 2>/dev/null && python3 - "$MC/probe.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for k, v in d["backends"].items():
    print(f"  {k:11s} {'available' if v.get('available') else 'unavailable'}  {v.get('version') or v.get('mode') or v.get('reason') or ''}"[:160])
PY
exit $fail
