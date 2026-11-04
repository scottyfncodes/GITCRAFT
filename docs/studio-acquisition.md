# GITCRAFT Studio — free tool acquisition report

November 2026. Mission: find, verify, acquire and wire in the best **free** tools for the capabilities
GITCRAFT lacked (audio, animation, environments, effects, materials, levels, cinematics, QA, asset
management), without paid services, without silently adding restrictive licences, and with proof that
each capability works. Result: nine departments, 54 actions, all runnable on a CPU-only machine, every
one verified by `tests/test_studio.py` through the sandboxed launcher. See [studio.md](studio.md) for the
architecture and usage.

## 0. Audit of what existed (baseline)

| Area | State before | Baseline tests |
|---|---|---|
| 2D: PhotoCraft, VectorCraft, DesignCraft, PdfCraft, LightCraft, FilmCraft, EffectCraft | working (prebuilt ArtCraft CLIs, guarded + Landlock-sandboxed) | `test_policy.py` 16/16 |
| 3D: MeshCraft (Blender 5.2 bpy) + ForgeCraft (orchestrator) | working; templates, rigging (rigid), Mixamo hand-off, bake, library, jobs, engine check | `test_meshcraft.py` 59/59, `test_forgecraft.py` 40/40 |
| Audio, procedural worlds, VFX, materials, levels, cinematics (beyond FilmCraft/EffectCraft editing), QA, cross-project assets | **missing**. The 3D roadmap had listed "procedural SFX tool first" and "procedural environment generation: ready to build" | — |
| Open issues / PRs | none open; branch based on `main` @ 4ba1554 | — |

Partial capabilities reused instead of rebuilt: MeshCraft's Blender (one Blender for the whole studio), its
engine-check approach (GLTFLoader in headless Chromium), the guard/sandbox launcher, the 3D library (synced
into AssetCraft), FilmCraft/EffectCraft (hand-editing after CinematicCraft's scripted cuts).

**Network reality of this environment** (it decides what could be acquired here): PyPI, npm and GitHub
release downloads reachable; **huggingface.co unreachable**; no GPU. Every candidate that needs Hugging Face
weights or a CUDA GPU is DEFERRED with that reason, not faked.

## 1. Scoring

Weights: free core 20 · commercial use 20 · integration/automation 20 · output quality 15 · maintenance 10 ·
local execution 10 · install simplicity 5. ACQUIRE = integrated; ALT = useful secondary; DEFER = promising
but not practical here/now; REJECT = paid, restricted, abandoned, unsuitable or redundant. ⚠ = licence flag.

### A. AudioCraft — audio

| Candidate | Licence | Free | Comm. | Integ. | Qual. | Maint. | Local | Inst. | **Score** | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| FFmpeg (system) | LGPL/GPL build | 20 | 18 | 20 | 14 | 10 | 10 | 5 | **97** | **ACQUIRE** — conversion, loudnorm, x264/AAC, probing |
| Kokoro-82M v1.0 + kokoro-onnx | Apache-2.0 weights, MIT code; ⚠ espeak-ng/phonemizer GPL-3.0 | 20 | 17 | 18 | 13 | 8 | 10 | 4 | **90** | **ACQUIRE** — 54 voices, CPU, ~1 s/sentence; weights from the GitHub release (HF not needed) |
| GITCRAFT synth (own: sfxr-style SFX, ambience, music, loop finder) | GITCRAFT | 20 | 20 | 20 | 10 | 8 | 10 | 5 | **93** | **ACQUIRE (built)** — deterministic, sandbox-friendly; the roadmap's recommendation |
| ACE-Step 1.5 (music) | MIT (v1.5; earlier Apache-2.0) | 20 | 18 | 15 | 14 | 9 | 7 | 2 | 85 | **DEFER** — weights on Hugging Face (unreachable here); <4 GB VRAM GPU recommended, CPU impractically slow. Top next acquisition |
| Stable Audio Open 1.0 | ⚠ Stability AI Community License (commercial use < $1M revenue, otherwise paid); gated weights | 15 | 6 | 14 | 13 | 7 | 7 | 2 | 64 | **REJECT** for default — revenue-conditional licence; could be an opt-in for eligible projects |
| MusicGen / AudioGen (Meta AudioCraft) | ⚠ code MIT, **weights CC-BY-NC-4.0** | 15 | 0 | 14 | 13 | 6 | 7 | 2 | 57 | **REJECT** — non-commercial weights |
| Piper TTS | ⚠ now GPL-3.0 (piper1-gpl; rhasspy/piper archived Oct 2025); per-voice licences, voices on HF | 20 | 12 | 16 | 11 | 7 | 10 | 3 | 79 | **ALT** — Kokoro is better quality with clearer weight licence |
| espeak-ng alone | GPL-3.0 | 20 | 14 | 16 | 5 | 8 | 10 | 5 | 78 | ALT (fallback quality only); already present as Kokoro's phonemizer |
| SoX | GPL-2.0 | 20 | 14 | 16 | 11 | 4 | 10 | 5 | 80 | ALT — redundant with FFmpeg |
| Audacity | GPL-2.0+ | 20 | 16 | 4 | 14 | 10 | 10 | 3 | 77 | **REJECT** for automation — GUI app; mod-script-pipe needs a running GUI |
| ElevenLabs and other hosted TTS/SFX | paid / credits | 4 | 10 | 16 | 15 | 10 | 0 | 5 | 60 | **REJECT** — a hosted free tier is not a free acquisition |
| jsfxr / sfxr ports | MIT | 20 | 20 | 14 | 9 | 5 | 10 | 5 | 83 | ALT — the built synth covers the same model without a JS dependency |

### B. AnimCraft — rigging and animation

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| Blender 5.2 armatures, heat-map weights, Bullet, BVH/FBX/glTF I/O (MeshCraft's bpy) | GPL (outputs free) | **94** | **ACQUIRE** (reused; no second Blender) |
| GITCRAFT landmark rigger, procedural clips, world-space retargeter (own, in Blender) | GITCRAFT | **88** | **ACQUIRE (built)** |
| Rigify (bundled with Blender) | GPL | 78 | ALT — powerful but its generated control rigs are heavy for game export; landmark rigs export cleanly |
| UniRig (VAST-AI) | MIT | 70 | **DEFER** — CUDA GPU ≥ 8 GB, weights on HF; skinning checkpoints not fully released |
| Cascadeur | ⚠ proprietary; free tier **non-commercial**, Indie < $100k/yr | 35 | **REJECT** — not free for commercial use, no headless API |
| Mixamo | free with Adobe account, no API | 55 | existing hand-off kept (MeshCraft); retarget makes its clips reusable across rigs |
| FreeMoCap (video mocap) | ⚠ AGPL (commercial licence on request) | 60 | **DEFER** — AGPL obligations + multi-camera setup |
| MediaPipe Pose (video → keypoints) | Apache-2.0; model files from Google storage | 72 | **DEFER** — model download + pose→BVH solver to build; next acquisition for mocap |

### C. WorldCraft — procedural environments

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| GITCRAFT terrain stack (fBm/ridged/warp noise, stream-power + thermal erosion, biomes, Poisson scatter, marching squares, surface nets, Tessendorf FFT ocean) | GITCRAFT, numpy BSD | **90** | **ACQUIRE (built)** |
| Blender Nishita sky texture | GPL (outputs free) | **88** | **ACQUIRE** — physically based sky in ~1.5 s |
| Infinigen | BSD-3-Clause | 66 | **DEFER** — photoreal but hours per scene (3.5 h per 1080p stereo pair in the paper), large install; DEFER as a "hero environment" option |
| Blender Geometry Nodes | GPL | 75 | ALT — scatter is done in numpy so it also works without Blender |
| "LibreTerrain" | — | — | **Not found**: no project by that name exists; closest are Terra (GPL-3.0, pre-1.0), TerrainLib (LGPL, commercial needs a licence), libterrain (rendering, not generation) — all REJECT vs the built stack |

### D. FXCraft — visual effects

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| GITCRAFT particle/curl-noise flipbook simulator + `fxcraft-particles.js` three.js runtime | GITCRAFT | **88** | **ACQUIRE (built)** — exact loops, engine-agnostic atlases |
| Blender bmesh Voronoi fracture + Bullet rigid bodies | GPL (outputs free) | **86** | **ACQUIRE** |
| three.quarks | MIT | 80 | **ALT** — richer three.js particle engine; recommended when a game outgrows the runtime |
| Blender Mantaflow (smoke/fire) | GPL | 70 | **DEFER** — minutes per effect on CPU; flipbooks cover games' needs today |
| Effekseer | MIT | 68 | DEFER — GUI authoring; web runtime needs WASM integration |

### E. MaterialCraft — materials and shaders

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| GITCRAFT procedural PBR generators (21 materials, weathering, toon) + glTF material GLB + three.js check | GITCRAFT | **89** | **ACQUIRE (built)** |
| Material Maker 1.5 | MIT (code), CC0 (assets) | 74 | **DEFER** — the 1.5 CLI (`--export-material`) needs a real rendering context (no headless GPU here); best upgrade for node-graph materials on a desktop |
| ambientCG / Poly Haven scanned sets | CC0 | 70 | ALT (person downloads; site unreachable here) — MaterialCraft `seamless` + ORM packing handle them |
| Blender procedural shaders + bake | GPL | 80 | ALT — MeshCraft's `web-pbr` bake already covers baking onto assets |

### F. LevelCraft — levels and maps

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| GITCRAFT generators + solvers (BSP dungeon, CA cave, platformer reachability, overworld roads via A*, towns) | GITCRAFT | **90** | **ACQUIRE (built)** |
| Tiled TMJ format | format open (Tiled editor GPL-2.0) | **88** | **ACQUIRE** as the export format (Phaser, Godot, Unity via SuperTiled2Unity, Defold…) |
| Phaser 3.90 | MIT | **87** | **ACQUIRE** — engine-level load + collision check |
| LDtk | MIT (last release 1.5.3, Feb 2024) | 72 | **ALT/DEFER** — native LDtk project writer is the next step; LDtk can import from other editors |
| Tiled CLI (`--export-map`) | GPL-2.0 | 60 | REJECT for now — Qt app; the TMJ is written directly |

### G. CinematicCraft — cinematics and video

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| Blender Cycles + camera rigs (MeshCraft's bpy) | GPL (renders free) | **90** | **ACQUIRE** |
| FFmpeg (x264, xfade, loudnorm) | GPL build | **95** | **ACQUIRE** |
| Playwright video (gameplay capture) | Apache-2.0 | **88** | **ACQUIRE** (shared with TestCraft) |
| Kdenlive / MLT `melt` | GPL / LGPL | 66 | **REJECT** — redundant with FFmpeg scripting + FilmCraft (existing NLE) |
| EEVEE | GPL | 60 | DEFER — needs a GPU/OpenGL context headless |

### H. TestCraft — automated QA

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| Playwright + Chromium | Apache-2.0 / BSD | **96** | **ACQUIRE** (preinstalled) — viewports, device emulation, input, video, tracing |
| YIQ perceptual pixel diff (pixelmatch's metric, own numpy port) | GITCRAFT | 88 | **ACQUIRE (built)** — no extra dependency |
| pixelmatch | ISC | 82 | ALT — same metric in JS |
| Khronos glTF-Validator | Apache-2.0 | **92** | **ACQUIRE** (asset integrity) |
| Vitest / Jest | MIT | 80 | **ACQUIRE as a runner** of the project's own suite — never installed into a project |

### I. AssetCraft — asset management

| Candidate | Licence | Score | Verdict |
|---|---|---|---|
| SQLite catalogue on existing GITCRAFT infrastructure (+ 3D library sync, dHash, sidecars) | public domain / GITCRAFT | **92** | **ACQUIRE (built)** — no standalone application, as the brief asked |
| DVC / git-annex / Git LFS | Apache-2.0 / GPL / MIT | 60 | REJECT — versioning stores, not catalogues; projects may still use them alongside |
| Standalone DAM apps (e.g. Eagle, digiKam) | paid / GPL | 40 | REJECT — GUI apps, not automatable here |

## 2. What was acquired, integrated and tested

| Department | Acquired / built | Integration | Proof artifacts (tests/test_studio.py + acceptance/studio) |
|---|---|---|---|
| AudioCraft | FFmpeg, Kokoro-82M (kokoro-onnx, onnxruntime), GITCRAFT synth | 9 actions | measured SFX; seamless ambiences (all 9 kinds); 5-stem music + MIDI + adaptive manifest; Kokoro lines (4 voices incl. a blend); loop recovered with **0-sample error** from audio with an intro; −16 LUFS ±1; OGG/MP3/Opus |
| AnimCraft | Blender (reused), own rigger/clips/retargeter | 7 actions | heat weights: **0 unweighted vertices, 21/21 bones**; 5 humanoid clips, quadruped, chain and object clips that move in three.js; walk retargeted onto a 1.2 m Mixamo-named rig (21 bones mapped, hips scaled 0.667); physics drop settles; 4-direction sprite sheets |
| WorldCraft | numpy stack, Blender Nishita sky | 5 actions | 6 terrain presets with Khronos 0 errors + three.js renders; closed cave (99.95% manifold edges); FFT ocean loop error 1e-14; skies + seamless cubemaps |
| FXCraft | own simulator + runtime, Blender fracture/Bullet | 3 actions | 12 flipbooks; looping ones exactly periodic; emitters played in three.js; 14-piece crate destruction |
| MaterialCraft | own generators | 4 actions | 21 materials; seam ≤ 1.5× ordinary step on every map; unit normals; glTF sphere renders; seamless-izing (gradient 39× → 0.7×) |
| LevelCraft | own generators/solvers, Tiled TMJ, Phaser | 1 action, 5 kinds | dungeon/cave/platformer/overworld/town solved; every map loads in Phaser 3 with matching tile and collision counts; blockouts in three.js |
| CinematicCraft | Blender Cycles, FFmpeg, Playwright | 5 actions | island orbit + hero dolly shots with camera paths; storyboard PNG/PDF; title card; 7 s teaser with crossfades + music; gameplay capture |
| TestCraft | Playwright, Chromium, Khronos validator, own diff | 8 actions | smoke on desktop/phone/tablet; play with coin + wall-collision assertions and MP4 capture; 60 fps profile; baseline + regression detection; 133-file asset audit |
| AssetCraft | SQLite catalogue | 12 actions | scan; exact + near duplicates; unused; dependencies; NC licence flagged + ATTRIBUTION.md; versioning; refuses overwrite; 14 3D-library versions synced (197 files); HTML catalogue |
| AnimCraft (Nov 2026) | MediaPipe Pose Landmarker 1.2.2 (Apache-2.0), own BVH solver | `mocap` | 12-frame video → 21-joint BVH: own FK and Blender's importer both match the landmarks (0.0° limb error), retargeted onto the auto-rigged hero and played in three.js; single photo → eased pose clip |
| AudioCraft (Nov 2026) | ACE-Step 1.5 v0.1.8 (MIT), opt-in | `music_model` | reports `blocked` here (no HF access, no GPU); adapter follows the documented `generate_music` API, DiT only |
| AnimCraft (Nov 2026) | UniRig (MIT), GPU only | `autorig_ml` | reports `blocked` here (no NVIDIA GPU); runs UniRig's own skeleton/skin/merge scripts |
| FXCraft (Nov 2026) | three.quarks 0.16.0 (MIT) | `quarks` | systems serialised, reloaded with QuarksLoader and simulated in Chromium; usage snippet |
| LevelCraft (Nov 2026) | LDtk 1.5.3 JSON schema (MIT) | `formats: ["ldtk"]` | every level validates against the official schema and reads back to the same tiles, collision and entities |
| ForgeCraft | — | `departments`, `department_route`, `department_run` | discovers 9 departments, routes studio vs 3D, runs a department inside its own sandbox |

Existing capabilities after the change: `test_policy.py`, `test_meshcraft.py`, `test_forgecraft.py` re-run
(results in the PR).

## 3. Deferred (with the next-best alternative in place)

| Deferred | Why | In place now |
|---|---|---|
| ACE-Step 1.5 (now an opt-in action) | needs `install-studio.sh music` + huggingface.co; GPU recommended | procedural music with MIDI + stems |
| UniRig (now a GPU-only action) | CUDA ≥ 8 GB, HF weights | landmark rig + heat weights |
| FreeMoCap multi-camera mocap | AGPL | MediaPipe single-camera mocap (`animcraft_mocap`) |
| Infinigen | hours per scene, heavy install | numpy terrain + Blender sky |
| Mantaflow fluid sims | minutes per effect on CPU | particle flipbooks |
| Material Maker 1.5 CLI | its Linux build segfaulted exporting under Xvfb + Mesa (software GL) here; needs a desktop GPU context | procedural PBR generators |
| EEVEE renders | GPU context | Cycles CPU |

## 4. Rejected

Stable Audio Open (revenue-conditional licence), MusicGen/AudioGen (CC-BY-NC weights), Cascadeur
(non-commercial free tier, $100k cap on Indie, no API), hosted TTS/SFX services (paid credits), Audacity and
Kdenlive (GUI-only/redundant), "LibreTerrain" (does not exist), Tiled CLI and DAM apps (GUI, redundant).

## 5. Licensing concerns

- **GPL-3.0 in the voice runtime**: Kokoro needs phonemizer + espeak-ng (GPL-3.0). They live in a separate
  venv, are not committed, and GITCRAFT code only runs them as a child process. Generated speech is not
  covered. Shipping a product that *bundles* the voice runtime would bring GPL obligations for those parts.
- **FFmpeg** here is a GPL build (x264). Used as an external program; encoded media are not covered.
- **Blender** GPL does not extend to models, renders or .blend content (as MeshCraft already documents).
- No non-commercial, no-derivatives or paid component is used by default. AssetCraft flags any such asset
  that enters a project.

## 6. New dependencies and storage

| Item | Where | Size |
|---|---|---|
| studio venv (numpy, Pillow) | `~/.gitcraft/studio/venv` | ~70 MB |
| Node runtime (three 0.170.0, phaser 3.90.0, gltf-validator) | `~/.gitcraft/studio/node` | ~180 MB |
| voice venv (kokoro-onnx, onnxruntime, phonemizer, espeak-ng) | `~/.gitcraft/studio/voice-venv` | ~150 MB |
| Kokoro model files (int8 ONNX + voices) | `~/.gitcraft/studio/models/kokoro` | 115 MB |
| mocap venv (mediapipe, OpenCV) + pose models (full, heavy) | `~/.gitcraft/studio/mocap-venv`, `models/mediapipe` | ~400 MB + 40 MB |
| three.quarks (Node) | `~/.gitcraft/studio/node` | ~1 MB |
| ACE-Step (opt-in) | `~/.gitcraft/studio/ace-step` | ~10 GB with CUDA PyTorch and weights |
| UniRig (GPU only) | `~/.gitcraft/studio/unirig` | several GB |
| catalogue + thumbnails | `~/.gitcraft/assetcraft` | grows with assets (KBs per asset) |
| Repo additions | `studio/`, `tests/test_studio.py`, fixture game, docs, `acceptance/studio` (curated proofs) | code ~300 KB; acceptance package a few MB |

Blender (MeshCraft) and Playwright/Chromium/FFmpeg were already present; nothing new was added to any game project.

## 7. Recommended next acquisitions

Done in November 2026: MediaPipe mocap, the LDtk writer, three.quarks export, ACE-Step and UniRig as
opt-in/GPU actions, and per-host network allowances (netgate). Next:

1. **Material Maker 1.5** CLI on a desktop machine with a GPU (its export crashed under software GL here).
2. Run `audiocraft_music_model` and `animcraft_autorig_ml` end to end on a GPU machine with Hugging Face
   access, and add them to `tests/test_studio.py` there.
3. Multi-person and root-motion mocap (MediaPipe image-space hip track → root translation).

## Sources (licence/status checks, November 2026)

ACE-Step 1.5 licence/VRAM: [HF Space README](https://huggingface.co/spaces/MBLF/ACE-Step-1.5/blob/main/README.md), [AMD blog](https://www.amd.com/en/blogs/2026/commercial-grade-ai-music-generation-on-amd-ryzen-ai-and-radeon-ace-step-1-5.html) ·
Stable Audio licence: [stability.ai/license](https://stability.ai/license) ·
MusicGen weights: [audiocraft README mirror](https://huggingface.co/spaces/facebook/MusicGen/discussions/8) ·
Kokoro-82M: [model card](https://huggingface.co/hexgrad/Kokoro-82M) ·
Piper: [rhasspy/piper (archived)](https://github.com/rhasspy/piper) ·
UniRig: [arXiv 2504.12451](https://arxiv.org/html/2504.12451) ·
Cascadeur: [plans](https://cascadeur.com/plans), [education](https://cascadeur.com/education) ·
Material Maker CLI: [docs](https://rodzill4.github.io/material-maker/doc/command_line.html), [1.5 release](https://digitalproduction.com/2026/01/26/material-maker-1-5-adds-dds-fbx-cli-10-new-nodes/) ·
Infinigen: [docs](https://infinigen.cs.princeton.edu/docs/latest/), [arXiv 2306.09310](https://arxiv.org/abs/2306.09310) ·
LDtk: [Chocolatey listing](https://chocolatey.org/packages/ldtk), [1.5.3 JSON schema](https://ldtk.io/files/JSON_SCHEMA.json) ·
MediaPipe Pose Landmarker: [guide](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) ·
ACE-Step 1.5: [repo, v0.1.8](https://github.com/ace-step/ACE-Step-1.5) ·
UniRig: [repo](https://github.com/VAST-AI-Research/UniRig) ·
FreeMoCap: [PyPI](https://pypi.org/project/freemocap/1.2.1/) ·
terrain search ("LibreTerrain"): [Terra](https://github.com/open-terra/terra), [TerrainLib](https://terrainlib.readthedocs.io/en/develop/).
