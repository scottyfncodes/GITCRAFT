# 3D Department: dependency and licensing audit

Every dependency the 3D Department (MeshCraft + ForgeCraft + `gitcraft3d/`) uses or can use, what each licence allows, where it installs and what it costs. Audited 2 November 2026 during the consolidation; re-check vendor terms before relying on them commercially. Backend-by-backend details, measured timings and sources are in [forgecraft-licensing.md](forgecraft-licensing.md).

**The consolidation changed no licence, added no dependency and added no paid service.** It removed duplicates: ForgeCraft's own Blender scripts, Blockbench writer, Mixamo merger and three.js/Khronos check are gone, and ForgeCraft now uses MeshCraft's. Every dependency below was already present on `main` before the consolidation.

## Runtime dependencies

| Dependency | Version (pinned) | Used by | Installed by / where | Licence | Commercial use of what you make | Cost |
|---|---|---|---|---|---|---|
| Blender (`bpy` wheel) | 5.2.3 LTS | MeshCraft only (ForgeCraft calls MeshCraft) | `scripts/install.sh meshcraft` → `~/.gitcraft/meshcraft/venv` (one copy) | GPL-2.0-or-later (wheel GPL-3.0); Cycles Apache-2.0 | Unrestricted: the GPL covers the software, not models, renders or `.blend` content | None (~400 MB) |
| pygltflib | 1.16.3 | MeshCraft validation | same venv | MIT | Unrestricted | None |
| numpy | 2.5.4 | MeshCraft | same venv | BSD-3-Clause | Unrestricted | None |
| Pillow | 11.3.0 | MeshCraft contact sheets, textures | same venv | MIT-CMU | Unrestricted | None |
| three | 0.170.0 | MeshCraft engine check (npm); UI viewer (vendored copy in `forgecraft/ui/vendor/three`, MIT notice included) | `npm ci` in `meshcraft/engine_check` | MIT | Unrestricted | None |
| gltf-validator (Khronos) | 2.0.0-dev.3.10 | MeshCraft validation | same npm install | Apache-2.0 | Unrestricted | None |
| Chromium + Playwright | pre-installed in cloud containers | engine check | not installed by GITCRAFT | BSD-3-Clause / Apache-2.0 | Unrestricted | None |
| Python stdlib | 3.13 | ForgeCraft, `gitcraft3d/` | system | PSF | Unrestricted | None |

ForgeCraft and `gitcraft3d/` have **no third-party Python dependencies**.

## Workflow integrations (no software installed)

| Tool | How it is used | Licence / terms | Notes |
|---|---|---|---|
| Blockbench | MeshCraft reads and writes the `.bbmodel` 5.0 format and imports it into Blender. The app is never run (it has no headless mode). | GPL-3.0-or-later | Unrestricted for projects and exports you author |
| Mixamo (Adobe) | Manual: MeshCraft prepares the upload FBX and merges downloaded clips by bone name. Nothing contacts mixamo.com. | Adobe General Terms, free with an Adobe ID | Characters and animations are royalty-free in personal, commercial and non-profit projects. Don't redistribute raw Mixamo files on their own, bulk-download, or use them to train AI models |

## Optional generators (ForgeCraft backends, opt-in installs)

| Tool | Version | Installed by / where | Licence | Commercial use | Hardware | Cost |
|---|---|---|---|---|---|---|
| Meshroom / AliceVision | 2023.3.0 | `scripts/install-3d.sh meshroom` → `~/.gitcraft/forgecraft` (GitHub release, 2.1 GB) | MPL-2.0 (+ bundled MIT etc.) | Unrestricted; reconstructions belong to the photos' owner | CPU: draft meshing only; dense reconstruction needs an NVIDIA CUDA GPU | None |
| TripoSR | upstream `main` | `scripts/install-3d.sh ai weights` → `~/.gitcraft/forgecraft` (PyTorch, deps, weights from Hugging Face) | MIT (code and weights) | Unrestricted with the MIT notice | CPU: minutes per image; ~6 GB VRAM: about a second | None locally (~5 GB PyTorch + 1.7 GB weights) |
| Hunyuan3D-2 | upstream `main` | same, plus `FORGECRAFT_HUNYUAN_LICENSE=accepted` | Tencent Hunyuan 3D Community Licence | **Restricted:** not licensed in the EU, UK or South Korea; >1M monthly active users needs a Tencent licence; outputs must be labelled AI-generated; outputs may not train other models | NVIDIA GPU, ≥6 GB VRAM shape, ≥16 GB with texture; or the public HF Space (`GITCRAFT_ALLOW_NET=1`) | Local GPU time; HF Space free quota. Tencent's paid hosted API is **not** wired in |

Hunyuan3D assets are recorded with `ai_generated: true` in their licence block. Model weights and large runtimes are never committed to git.

## How licences are recorded per asset

Every library version carries a `license` block written by ForgeCraft: the asset's ownership statement, each tool that touched it with its licence and the note on whether that licence extends to the output, and the AI-generated flag. `provenance` lists the ForgeCraft and MeshCraft job ids, input files with SHA-256, Blender version and machine. Assets built directly with MeshCraft's `run_pipeline` keep MeshCraft's own record (brief, inputs with hashes, job); ForgeCraft adds the licence block only to the work it orchestrates.
