# GITCRAFT Studio — the department layer

GITCRAFT already had the 2D tools (PhotoCraft, VectorCraft, DesignCraft, PdfCraft, LightCraft, FilmCraft,
EffectCraft) and the 3D Department (ForgeCraft orchestrating MeshCraft). The Studio adds ten
departments for everything else a game or app needs, served by one MCP server, **`studiocraft`**, and
reachable from ForgeCraft through `departments`, `department_route` and `department_run`.

| Department | What it makes | Built on (acquired) |
|---|---|---|
| **AudioCraft** | SFX (14 presets, seeded variations), seamless ambiences (9), adaptive multi-stem music + MIDI, character dialogue (54 voices), loop-point detection, trim/fade/EBU R128 normalisation, layering, WAV/OGG/MP3/Opus/FLAC | GITCRAFT synth (numpy), **Kokoro-82M** via kokoro-onnx (CPU), **FFmpeg** |
| **AnimCraft** | Auto-rigging (humanoid, quadruped, chain) with heat-map weights, Mixamo naming, procedural clips (13), world-space retargeting (BVH/FBX/GLB), rigid-body physics, sprite sheets (N directions), playback verification | **Blender 5.2** (MeshCraft's bpy), three.js |
| **WorldCraft** | Eroded terrains (8 presets), biomes, 16-bit heightmaps, normal/splat/biome maps, masks, vegetation + rock scatter, coastlines, terrain GLB; caves; physical skies + cubemaps; time-looping FFT oceans | numpy, **Blender Nishita sky**, three.js, Khronos validator |
| **FXCraft** | Flipbooks (12 effects; loops repeat exactly), Phaser/PixiJS atlases, emitter presets + a three.js runtime, Voronoi destruction with baked physics | numpy, FFmpeg, three.js, **Blender (Bullet)** |
| **MaterialCraft** | 21 seamless PBR materials, dirt/moss/wear/wet weathering, toon style, glTF map sets + ORM, sample sphere GLB, seamless-izing, toon ramps, swatches | numpy, three.js, Khronos validator |
| **LevelCraft** | Dungeons, caves, completable platformers, overworlds with roads, towns; Tiled TMJ + tileset, entity/collision/nav layers, JSON, blockout GLB | numpy, **Phaser 3** (load check), three.js |
| **CinematicCraft** | Camera moves (8) with lighting presets (6), Cycles renders → MP4 + .blend + engine camera path; storyboards (PNG/PDF); title cards; trailer assembly with crossfades + music; gameplay capture | **Blender Cycles**, FFmpeg (x264, xfade, loudnorm), Playwright |
| **TestCraft** | Smoke tests on desktop/phone/tablet, scripted gameplay with state assertions and video, FPS/frame-time/heap profiles, visual regression, asset integrity, animation playback, Vitest/Jest, HTML reports | **Playwright + Chromium**, Khronos validator |
| **AssetCraft** | One catalogue for every project: auto-registration of every output, scan, search, versions, exact + perceptual duplicates, unused assets, dependencies, licence report + ATTRIBUTION.md, verify, safe integration, 3D-library sync, HTML catalogue | SQLite (stdlib), Pillow, FFmpeg |
| **PLAYCRAFT** | Game design and gameplay quality: discovery + genre identification (15 profiles), a Chromium play probe (per-control response, dead time, FPS, pause, touch targets, text size), 10-category scorecard with evidence levels, ranked plan, verify with regressions + git-diff guardrails, combined GITCRAFT + PLAYCRAFT pass. See [playcraft.md](playcraft.md) | Playwright + Chromium, numpy, Pillow |

How the tools were chosen, scored, and what was deferred or rejected: [studio-acquisition.md](studio-acquisition.md).

## Architecture

```
 Claude Code ──MCP──► scripts/mcp.sh studiocraft ──► guard.py ──► sandbox.py (Landlock: roots + state, no network)
                                                                    └─► studio/server.py  (studio venv: numpy, Pillow)
                                                                          │  one tool per department action, generated from manifests
                                                                          ├─► core/contract.py  validate request → check deps → run → validate outputs → record → catalogue
                                                                          ├─► Blender  (MeshCraft's bpy venv; scripts in studio/**/bpy_*.py)
                                                                          ├─► Node + Chromium (core/web/harness.mjs, testcraft.mjs; three, Phaser, glTF-Validator)
                                                                          ├─► FFmpeg
                                                                          └─► voice venv (Kokoro-82M, onnxruntime)
 ForgeCraft ── departments / department_route / department_run ──► studio/cli.py --call (same code, inside ForgeCraft's sandbox)
```

```
studio/
  server.py            MCP server (stdio JSON-RPC, like ForgeCraft's)
  cli.py               CLI + the --call entry ForgeCraft uses
  core/contract.py     the department contract (below)
  core/deps.py         dependency checks (never start a runtime: wheel metadata, binaries, files)
  core/validate.py     format validation of every output (images, audio, video, GLB, Tiled, MIDI, PDF, …)
  core/catalog.py      AssetCraft's SQLite catalogue
  core/routing.py      brief → department/action (+ proposed parameters)
  core/media.py        WAV with loop chunks, FFmpeg, GLB writer, atlases, GIF/MP4, contact sheets
  core/noise.py        tileable gradient/fBm/ridged/Worley/value noise, normal maps
  core/runners.py      Blender / Node / other-venv child processes
  core/webpages.py     three.js checks (GLTFLoader load + render, Khronos validator)
  core/bpy/            shared Blender helpers
  core/web/            harness.mjs (generic page runner), testcraft.mjs, gltf_validate.mjs
  departments/<name>/  manifest.json + dept.py (+ generators, bpy_*.py)
  node/                package.json + lock for the Node runtime (installed to ~/.gitcraft/studio/node)
```

Runtimes live outside the repo in `~/.gitcraft/studio` (`$GITCRAFT_STUDIO_HOME`): `venv/` (numpy, Pillow;
~70 MB), `voice-venv/` (kokoro-onnx, onnxruntime, phonemizer, espeak-ng; ~150 MB), `models/kokoro/` (~115 MB),
`node/` (three, Phaser, glTF-Validator; ~180 MB). Each department imports only what it needs; heavy
runtimes are separate and optional, and nothing is committed to git.

## The department contract

Every department provides, and `core/contract.py` enforces:

| Requirement | Where |
|---|---|
| Machine-readable capability manifest | `departments/<name>/manifest.json`: `actions` (summary, `params` JSON schema, `requires`, `outputs`, `keywords`), `dependencies` (kind, licence, install command, alternatives), `tools` (acquired tools with licences), `keywords`, `examples`, `limits`, `output_license` |
| Documented request format | each action's `params` schema; the MCP tool's `inputSchema` is generated from it. Common to all: `out_dir`, `name`, `seed`, `license`, `tags` |
| Callable entry point | MCP `<department>_<action>` (studiocraft), `run`; CLI `studio/cli.py run <dept> <action> '<json>'`; ForgeCraft `department_run` |
| Dependency checks | `requires` is checked before running; a missing dependency returns `status: "blocked"`, the reason, the install command and alternatives. **No substitute output is ever produced.** `studio_status` reports every action as ready/blocked |
| Input validation | types, enums, ranges, required fields, unknown parameters refused; input paths must be inside the GITCRAFT roots (the shared 3D library is readable) |
| Output validation | every output is opened by format (`core/validate.py`) and SHA-256 hashed; departments add domain checks (seamless loop, solvable level, Khronos 0 errors, renders in three.js, clip moves the model, …). One failed check ⇒ `status: "failed"` with the reason |
| Error reporting | `failed` with `error`, `hint` and the stage it failed at; `blocked` with `reason`, `install`, `alternatives` |
| Previews | waveforms, contact sheets, GIF/MP4 previews, engine screenshots (three.js/Phaser) |
| Source/editable outputs | `.blend`, `.mid`, `.tmj`, `.fx.json`, `.camera.json`, 16-bit heightmaps, layer manifests |
| Licence + attribution metadata | `<out_dir>/<name>.studio.json`: request, tools used with licences, output licence, attribution, outputs with hashes, checks, stage timings; outputs registered in the AssetCraft catalogue |
| Automated smoke tests | `tests/test_studio.py` (every department, through the sandboxed launcher) |

Result format (all actions):

```json
{"department": "audiocraft", "action": "sfx", "status": "ok | failed | blocked", "out_dir": "...",
 "outputs": [{"path": "coin_01.wav", "role": "sfx", "format": "wav", "ok": true, "seconds": 0.28, "sha256": "...", "bytes": 24748}],
 "checks": [{"name": "coin_01.wav is audible and unclipped", "ok": true, "detail": "..."}],
 "tools": {"studio_synth": {"name": "...", "license": "..."}, "ffmpeg": {...}},
 "output_license": "...", "attribution": null, "stages": [...], "record": ".../coin.studio.json", "catalog": {"registered": 3}}
```

## Install

`scripts/install.sh` (and therefore `scripts/setup-env.sh` and the SessionStart hook) installs the Studio
after the 2D tools are registered and before the Blender download, then registers `studiocraft` at user
scope. A cut-off or timed-out Studio step is recorded in `status.json`, named by `doctor.sh`, and finished
in the background by the user-level SessionStart hook:

```bash
scripts/install-studio.sh            # core: studio venv + Node runtime
scripts/install-studio.sh voice      # + Kokoro voice (pip + ~115 MB GitHub release download, SHA-256 checked)
scripts/install-studio.sh mocap      # + MediaPipe Pose for animcraft_mocap (pip + ~40 MB pinned models, SHA-256 checked;
                                     #   as root it also apt-installs the EGL/GLES libraries MediaPipe loads)
scripts/install-studio.sh music      # opt-in: ACE-Step 1.5 for audiocraft_music_model (~8 GB with CPU PyTorch; huggingface.co,
                                     #   download.pytorch.org and download-r2.pytorch.org must be allowed)
scripts/install-studio.sh unirig     # GPU machines only: UniRig for animcraft_autorig_ml (CUDA, weights from huggingface.co)
scripts/install.sh meshcraft         # Blender, for animcraft / cinematiccraft / worldcraft sky / fxcraft destruction
GITCRAFT_STUDIO=0                    # no Studio
GITCRAFT_STUDIO_VOICE=later | 0      # voice model in the background at the first session / not at all
scripts/doctor.sh                    # shows every department's ready/blocked actions
```

`studiocraft` is registered on the first install pass, before its runtime exists (Claude Code reads MCP
servers only at session start). Until the runtime lands it lists only `studio_status`, which says how to
install; when the install finishes it sends `notifications/tools/list_changed` and the session sees every
department tool without `/mcp`.

`music` and `unirig` need huggingface.co. Default cloud environments block it: allow `huggingface.co`,
`*.hf.co` and `cdn-lfs.huggingface.co` in the environment's network policy for the install, and, for a tool
that must reach a host at run time, give it a per-host allowance with netgate (`GITCRAFT_ALLOW_HOSTS_<TOOL>`,
see [security.md](security.md#per-host-network-allowances-netgate)).

System tools used when present: FFmpeg (`apt-get install ffmpeg`), Playwright + Chromium (preinstalled in
Claude Code cloud containers; otherwise `npm i -g playwright && npx playwright install chromium`).

## Hardware

Everything runs on CPU. Measured on the 4-thread, 16 GB, no-GPU cloud container used for this work:

| Work | Time |
|---|---|
| SFX, music (8 bars), ambience (20 s) | 0.3–2 s |
| Voice line (Kokoro int8, CPU) | ~1 s per sentence after a 1 s model load |
| Terrain 257² + erosion + GLB + three.js check | ~7 s |
| PBR material 512² + render check | ~3 s |
| Level + Phaser check + blockout | ~3–6 s |
| Flipbook (32 frames, 128 px) | ~1 s |
| Auto-rig / clips / retarget / physics / destruction (Blender) | 2–20 s |
| Cinematic shot, Cycles 640×360, 12 samples | ~1–2 s per frame |
| Browser tests (per viewport) | 3–8 s |

RAM peaks around 1.5 GB (Blender + Chromium together). No department needs a GPU; the GPU-only candidates
are deferred (see the acquisition report).

## Example Claude Code requests

- "Make three coin pickup sounds and a 30-second ocean loop for the beach level" → `audiocraft_sfx`, `audiocraft_ambience`
- "Voice the captain and the parrot for the intro" → `audiocraft_voice` with a `cast`
- "Give the game an adventure theme that gets more intense in fights" → `audiocraft_music` (use the `.layers.json` intensity levels)
- "Rig this character, give it idle/walk/run, and make 8-direction sprites of the walk" → `animcraft_autorig` → `animcraft_animate` → `animcraft_spritesheet`
- "Put this Mixamo walk on my character" → `animcraft_retarget`
- "Turn this dance video into an animation for my hero" → `animcraft_mocap` with `target` (MediaPipe → BVH → retarget)
- "A three.quarks magic burst I can load in my three.js game" → `fxcraft_quarks`
- "An LDtk project for a cave level" → `levelcraft_generate` (writes `.ldtk` next to the `.tmj`)
- "A tropical island, a sunset skybox and animated sea normals" → `worldcraft_terrain`, `worldcraft_sky`, `worldcraft_ocean`
- "A looping torch fire and a crate that shatters" → `fxcraft_emitter`, `fxcraft_destruction`
- "Mossy cobblestone and rusty metal at 1K" → `materialcraft_generate`
- "Real photo-scanned snow and rock materials, an alpine HDRI sky, a CC0 crate model" → `materialcraft_fetch`, `worldcraft_hdri`,
  `worldcraft_fetch_model` (Poly Haven / ambientCG, CC0; `list_only: true` to see the matches first)
- "A roguelike floor and a completable platformer level for a 3-tile jump" → `levelcraft_generate`
- "A golden-hour orbit of the island, a title card, and cut them into a teaser with the theme" → `cinematiccraft_shot`, `_title_card`, `_assemble`
- "Smoke-test the build on phone and desktop, then check it holds 30 fps" → `testcraft_smoke`, `testcraft_perf`
- "What assets are unused, and write the credits file" → `assetcraft_unused`, `assetcraft_license_report`
- Not sure which? `route` (studiocraft) or `department_route` (ForgeCraft).

Outputs go to `<root>/gitcraft-out/<department>/<name>` unless `out_dir` says otherwise; nothing is written
into a project's source tree unless asked, and `assetcraft_integrate` never overwrites a different file
without `replace: true`.

## Verification

```bash
python3 tests/test_studio.py           # every department through scripts/mcp.sh studiocraft (sandboxed), + ForgeCraft's tools (~3 min)
python3 tests/test_studio.py --quick   # without the Blender actions
GITCRAFT_STUDIO_PROOF=dir python3 tests/test_studio.py   # keep the artifacts
```

Each department produces and checks real artifacts: a measured SFX, a seamless ambience, aligned music stems
with an exact loop recovered from audio with an intro, a Kokoro voice line, an eroded island rendered in
three.js, a closed cave mesh, a time-looping ocean, a sky cubemap, a weathered material on a glTF sphere, a
non-tiling image made seamless, three solved levels loaded in Phaser 3, an exactly-looping fire and an
explosion played by the three.js runtime, smoke/play/perf/visual-regression/asset reports against a fixture
game, a heat-weighted rig with clips that move in three.js and a walk retargeted across naming schemes,
sprite sheets, a settled physics drop, a Voronoi destruction, a rendered orbit with its camera path, a title
card, a teaser with music, a gameplay capture, and the catalogue's versioning, duplicates, licence flags
and safe integration. A curated set from the acceptance run is in `acceptance/studio/`.

## Licence inventory

| Component | Licence | Notes |
|---|---|---|
| Studio code (`studio/`) | same as GITCRAFT | own code: synth, generators, solvers, runtime, contract |
| NumPy 2.5.4, Pillow 11.3.0 | BSD-3-Clause, MIT-CMU | studio venv |
| FFmpeg (system) | LGPL-2.1+; this build `--enable-gpl` (x264) ⇒ GPL-2.0+ | external program; does not extend to media it writes |
| Kokoro-82M v1.0 weights | Apache-2.0 | trained on permissive/non-copyrighted audio per the model card |
| kokoro-onnx 0.6.1, onnxruntime 1.31 | MIT, MIT | voice venv |
| phonemizer 3.6, espeak-ng (espeakng-loader) | GPL-3.0 | **copyleft**: used as a runtime library in a separate venv, not committed, not linked into GITCRAFT code; generated speech carries no obligation. Distributing a product that bundles the voice venv would bring GPL-3.0 obligations for those parts |
| Blender 5.2 (bpy wheel) | GPL-2.0-or-later (wheel GPL-3.0) | already MeshCraft's; does not extend to models, renders or .blend content |
| three.js 0.170.0 | MIT | Node runtime + checks |
| Phaser 3.90.0 | MIT | Node runtime (Tiled load check) |
| Khronos glTF-Validator 2.0.0-dev.3.10 | Apache-2.0 | Node runtime |
| Playwright, Chromium | Apache-2.0, BSD-3-Clause | system (preinstalled) |
| SQLite | public domain | Python stdlib |
| `fxcraft-particles.js` | same as GITCRAFT | copied next to each emitter; may be shipped in games |

Generated outputs are owned by the requesting project (recorded per run); retargeted motion and assembled
edits keep the licences of their inputs. AssetCraft's `license_report` flags NC/ND/proprietary assets and
copyleft/share-alike ones.

## Known limitations

- Default music is procedural (solid, loopable, editable via MIDI). `audiocraft_music_model` (ACE-Step 1.5,
  MIT) is opt-in: it needs `install-studio.sh music` with Hugging Face access and is slow without a GPU. Its
  adapter is tested end to end on CPU (no GPU): 10 s of music in about 40–70 s, run in bfloat16 so it fits in 16 GB of RAM.
- `animcraft_mocap` is monocular: one person, no root travel (hip-centred landmarks), no fingers or face.
- `animcraft_autorig_ml` (UniRig) needs an NVIDIA GPU; its installer and adapter are untested on CPU-only machines.
- AnimCraft rigs from landmarks: expects a T/A-pose humanoid facing forward, a level quadruped, or a straight
  chain; clips are clean procedural blocking, retargeted mocap gives natural motion.
- Terrain erosion is a fast stream-power approximation; flipbooks are 2D particle simulations (no volumetric
  fluid sim); materials are procedural (scanned CC0 sets can be made seamless and packed).
- Cycles renders on CPU only; EEVEE needs a GPU context.
- TestCraft serves local folders through request interception: games that need a live backend show as
  blocked requests; WebGL runs on SwiftShader so FPS is relative.
- LDtk output is a single level per project with IntGrid collision, an auto tile layer and entities; it is
  validated against the official 1.5.3 schema, not opened in the LDtk app.
