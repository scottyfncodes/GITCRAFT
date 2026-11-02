# ForgeCraft (3D Department): licensing, cost and infrastructure


The dependency and licensing audit for the whole 3D Department is [3d-licensing.md](3d-licensing.md). This page has the backend-by-backend detail: integration status, hardware, measured timings and sources. Since the consolidation, every Blender, Blockbench and Mixamo step below is done by MeshCraft on ForgeCraft's behalf (one implementation each); Meshroom, TripoSR and Hunyuan3D remain ForgeCraft backends whose output MeshCraft cleans up.

Researched 2026-11-02. Sources are listed at the end. **Free software is not free compute**, so each tool's licence and the hardware it needs are listed separately. Nothing large is committed to git. Every runtime and model weight is downloaded into `~/.gitcraft/forgecraft` by `scripts/install-3d.sh` or on first use.

## Integration status (what actually runs)

| Tool | How it is integrated | Ran in this cloud session? | Where it runs |
|---|---|---|---|
| **Blender 5.2.3 LTS** | `bpy` wheel (official, Blender Foundation, PyPI), headless, one process per job, installed once for MeshCraft. Procedural modelling, cleanup, decimation, UV, Cycles texture baking, rigging, animation, scene composition, Cycles rendering, GLB/glTF/FBX/OBJ/STL/.blend export, re-import validation. | **Yes**: every asset in the TIDEBREAKERS package | Local, CPU (Cycles can also use CUDA/OptiX) |
| **Blockbench** (format) | MeshCraft writes genuine `.bbmodel` projects (format 5.0, schema from Blockbench's own `js/formats/bbmodel.js`) and converts any `.bbmodel` to Blender → GLB etc. **The Blockbench app itself is not executed**: it has no headless/CLI/server mode (upstream issue #1764). | **Yes** (format + conversion). Opening the files in Blockbench is a manual step and was not done here. | Local, CPU |
| **Mixamo** | Supported manual workflow only. MeshCraft prepares the unrigged T-pose FBX for upload and merges downloaded FBX clips by Mixamo bone name (ForgeCraft's `mixamo_*` tools delegate to it). The deckhand template already uses the Mixamo skeleton names. No API calls and no scraping (there is no official API). | **Partly**: the import/merge path ran on Mixamo-layout FBX fixtures exported from our own rig. No real mixamo.com download was used (the site needs a person with an Adobe ID, and the host is blocked here). | Hosted (Adobe), by hand |
| **Meshroom 2023.3.0 / AliceVision** | `meshroom_batch` with hardware detection: full `photogrammetry` with an NVIDIA CUDA GPU, CPU `photogrammetryDraft` without one. Then MeshCraft's `process_mesh` crops to the subject, rescales, cleans, bakes and exports. | **Yes**: 36 photos → all 36 cameras solved → textured mesh, about 5 min on 4 CPU threads (draft quality). The photos were Cycles renders of a ForgeCraft asset, not camera photos. | Local, CPU draft / CUDA dense |
| **TripoSR** | Adapter runs upstream `run.py` from a checkout in an AI venv (CPU or CUDA), then MeshCraft's `process_mesh`. | **No.** Weights are on huggingface.co, which this environment's network policy blocks. PyTorch is also not installed. The adapter refuses with that reason. | Local, CPU (minutes) or GPU ~6 GB (seconds) |
| **Hunyuan3D-2** | Adapter: local `hy3dgen` on an NVIDIA GPU, or the public HF Space through `gradio_client`. Gated by a licence acknowledgement. | **No.** No GPU here, and huggingface.co / hf.space are blocked. The adapter refuses with that reason. The Space's endpoint signature is discovered at call time and was **not verified** in this environment. | Local GPU (≥6 GB shape, ≥16 GB texture) or hosted Space |

## Licences and commercial use

| Tool | Licence | Commercial use | Notes |
|---|---|---|---|
| Blender / `bpy` | GPL-2.0-or-later (source); binaries/wheel GPL-3.0; Cycles Apache-2.0 | Unrestricted for what you make | GPL covers the software, not your models, renders or `.blend` content. |
| Blockbench | GPL-3.0-or-later | Unrestricted for `.bbmodel`/exported content you author | Plugins may be proprietary per its README. ForgeCraft uses only the file format. |
| Mixamo | Adobe terms (free with an Adobe ID) | Characters and animations royalty-free in personal, commercial and non-profit projects; no attribution needed | Do not redistribute raw Mixamo files standalone, bulk-download, or use them to train ML models. Re-check Adobe's current General Terms. |
| Meshroom / AliceVision | MPL-2.0 (plus MIT and other bundled third-party code) | Unrestricted | If you modify MPL files, publish those files' source. Reconstructions belong to whoever owns the photos. |
| TripoSR | MIT (code and `stabilityai/TripoSR` weights) | Unrestricted with the MIT notice | The newer Stable Fast 3D is under the Stability Community License, not MIT. Not used. |
| Hunyuan3D-2 / 2mini / 2mv / 2.1 | Tencent Hunyuan 3D 2.0 / 2.1 Community License (one licence for code and weights) | **Restricted**: not licensed in the **EU, UK or South Korea**. More than **1M monthly active users** needs a separate Tencent licence. Outputs must be labelled as machine-generated when shown publicly. Outputs may not be used to improve other AI models. | ForgeCraft refuses to run it until `FORGECRAFT_HUNYUAN_LICENSE=accepted` is set, and marks its assets `ai_generated: true`. Hunyuan3D 2.5/3.0/3.1 are **hosted-only** (Tencent Cloud, paid) and are deliberately not wired in. |

## Hardware, compute and cost

| Tool | CPU-only? | GPU | RAM / disk | API cost |
|---|---|---|---|---|
| Blender (headless) | Yes (Cycles CPU) | Optional (CUDA/OptiX for Cycles) | ~400 MB wheel; 8 GB RAM is plenty for these assets | None |
| Blockbench format | Yes | — | negligible | None |
| Mixamo | n/a (Adobe servers) | — | — | Free (Adobe ID) |
| Meshroom | **Draft only** (sparse-cloud meshing; coarser) | NVIDIA CUDA for DepthMap / dense meshing (2023.x: CUDA 11, CC ≥3.5; 2025.1: CUDA 12, CC ≥5.0) | 2.1 GB install; ≥8 GB RAM enforced; scratch scales with photo count | None |
| TripoSR | Yes (minutes per image) | ~6 GB VRAM: ~1 s per image | ~5 GB PyTorch + 1.7 GB weights | None |
| Hunyuan3D-2 | **No official CPU path** | ≥6 GB VRAM shape (2mini / 2.0), ≥16 GB with texture; 2.1: ~10 GB shape, ~21 GB texture | 5–20 GB weights | Local: none. HF Space: free ZeroGPU with quotas. Tencent Cloud: paid credits, ~$0.30–0.50 per generation; **not used** |

**This cloud session:** 4 CPU threads, 15.7 GB RAM, no GPU. Measured timings for real assets:
- Sloop: about 7 s end to end.
- Island with a 2048² bake: about 25 s.
- Character with 6 clips: about 6 s.
- 36-photo Meshroom draft reconstruction: about 5 min.
- Rendering 36 photos at 1024² for the photogrammetry test: about 6 min.

## Running locally vs remotely

| | Local (any Linux x86_64 with Python 3.13) | Container | Hosted |
|---|---|---|---|
| Blender, Blockbench format, Mixamo import, Meshroom | ✔ | ✔ (Meshroom also has an official Docker image `alicevision/meshroom`) | — |
| TripoSR | ✔ CPU/GPU, once weights are reachable or seeded | ✔ | HF Space (not wired) |
| Hunyuan3D | ✔ with an NVIDIA GPU | ✔ with GPU passthrough | HF Space via `gradio_client` (needs `GITCRAFT_ALLOW_NET=1`) |

**To enable the AI backends:**
1. Run on a machine with an NVIDIA GPU, or allow `huggingface.co` in the environment's network policy.
2. Run `scripts/install-3d.sh ai weights`.
3. For the hosted Space, set `GITCRAFT_ALLOW_NET=1`. Its free quota applies.
4. For Hunyuan3D, also confirm the licence territory and set `FORGECRAFT_HUNYUAN_LICENSE=accepted`.

`scripts/doctor.sh` shows what is still missing.

## No large files in git

Meshroom, PyTorch and all model weights install into `~/.gitcraft/forgecraft`. The TIDEBREAKERS acceptance package in `acceptance/tidebreakers-3d/` is small game assets: low-poly GLBs and baked PNGs, about 1–4 MB per asset. Model weights are never committed.

## Sources

PyPI `bpy` (pypi.org/project/bpy) · blender.org/about/license · github.com/Tencent-Hunyuan/Hunyuan3D-2 and -2.1 (LICENSE files) · tencentcloud.com/document/product/1284/75281 · github.com/VAST-AI-Research/TripoSR (README, requirements.txt, run.py) · github.com/JannisX11/blockbench (package.json, js/formats/bbmodel.js, issue #1764) · helpx.adobe.com/creative-cloud/faq/mixamo-faq.html · community.adobe.com Mixamo licensing/API threads · github.com/alicevision/Meshroom (releases, COPYING.md, bin/meshroom_batch) · hub.docker.com/r/alicevision/meshroom.

Some of these hosts were unreachable from this session, so these items were taken from search snippets and should be re-checked:
- Blender's hardware page.
- Tencent Cloud pricing.
- The wording of the Hugging Face model cards.
- Adobe's current terms.
- Whether CPU draft mode works in Meshroom 2025.1. It was verified here on 2023.3.0.
