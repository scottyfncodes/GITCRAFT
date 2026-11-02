# The 3D Department (ForgeCraft)

`forgecraft` is GITCRAFT's 3D Department: a pipeline server that sits alongside MeshCraft (`meshcraft`, the Blender template tool) and uses it as one of its backends. It brings six 3D capabilities into one pipeline that produces, processes, packages and hands off real game assets. The capabilities are Blender, Blockbench, Mixamo, Meshroom/AliceVision, TripoSR and Hunyuan3D. Licensing, cost and hardware details are in [forgecraft-licensing.md](forgecraft-licensing.md).

## 1. Architecture assessment (before any change)

**What GITCRAFT was:** a toolbox, not an application. Seven ArtCraft apps (Rust CLIs) run as headless MCP servers. Claude Code is the orchestrator and art director.

| Concern | What existed | Consequence for 3D |
|---|---|---|
| Orchestration | Claude Code calls tools over MCP. No scheduler or queue. | The 3D Department is another MCP server. Multi-stage work is a *pipeline inside that server*, not a new orchestrator. |
| Launch / security | `scripts/mcp.sh` puts every server behind `guard.py` (path checks, deny list, audit log with SHA-256 of every file) and `sandbox.py` (Landlock: workspace roots + own state, no network). | ForgeCraft runs behind the same launcher with no exceptions. Its runtimes are read-only/executable; its library is writable; network stays off unless `GITCRAFT_ALLOW_NET=1`. |
| Asset handoff | "A handoff is a file in an authorized root." Tools never talk to each other. The audit log hashes both ends. | 3D assets are files too: `library_export` copies an asset into a root. FilmCraft, DesignCraft and the other tools pick it up from there. |
| Storage | Per-tool state in `~/.gitcraft/state/<tool>`. LightCraft keeps a persistent library in `~/.gitcraft/lightcraft-library`. | ForgeCraft mirrors LightCraft: `~/.gitcraft/forgecraft-library` (versioned assets + job records). |
| Job management / reporting | None beyond the audit log, `status.json` and `doctor.sh`. | Added job records (stages, attempts, errors, compute) and a Pipeline Monitor. `doctor.sh` now lists 3D backends. |
| Artifact formats / metadata | Project manifests such as TIDEBREAKERS `creative/MANIFEST.json`. | Every 3D asset carries an `asset.json` (ID, version, provenance, licence, stats, validation). |
| Install / deploy | Prebuilt Rust binaries from the `bin` branch (CI matrix in `scripts/tools.sh`), with registration at user scope. | Blender etc. are not ArtCraft binaries, so they are not in the CI matrix. `GITCRAFT_EXTRA_TOOLS` + `scripts/install-3d.sh` install them from their official sources. |
| UI | **There was no GITCRAFT UI.** The "interface" was Claude Code itself. | The department's UI is a static snapshot of a run (published to Vercel). Jobs run through the MCP tools, the CLI or the GITCRAFT control room (`scripts/ui.sh`). It follows the TIDEBREAKERS palette that the GITCRAFT pilot established. |

**Hardware and runtime found in the cloud session:** 4 CPU threads, 15.7 GB RAM, **no GPU**, Python 3.13, Node 22, Chromium + Playwright, Linux 6.18 with Landlock. **Network policy:** PyPI, npm and GitHub downloads are allowed; `download.blender.org`, `huggingface.co` (all model weights), `*.hf.space` and `download.pytorch.org` are **denied** by the egress proxy.

**Decisions that followed:**
- Blender is the official `bpy` 5.2.3 LTS wheel from PyPI (download.blender.org is blocked), shared with MeshCraft: ForgeCraft drives MeshCraft's venv (`~/.gitcraft/meshcraft/venv`), so Blender is installed once. It is real Blender, headless, rendering with Cycles on the CPU. EEVEE needs an OpenGL/EGL context and aborts headless, so it is never used.
- Every Blender job runs in its own process, so a crash cannot take down the MCP server.
- AI generation (TripoSR, Hunyuan3D) is integrated as hardware- and network-aware backends. On this machine they report *unavailable, with the exact reason*, and they are never faked.
- No new infrastructure: no database, no queue service, no web backend in the cloud. JSON files + a file lock + the existing sandbox.

## 1b. ForgeCraft and MeshCraft

Both 3D tools were built in parallel and now run side by side:

| | MeshCraft (`meshcraft`) | ForgeCraft (`forgecraft`) |
|---|---|---|
| Job | A hand-tuned asset from a structured brief: one of its templates (chest, Biscuit the crab, flag, lantern, sail, sun figurehead), brand-palette materials, LODs, collision, per-engine export profiles, manifest updates | The department: decide *how* to make any requested asset, make it with the right tool, then package, version and hand it off |
| Runs | Inside Blender's Python | Stdlib Python that spawns Blender, Meshroom, MeshCraft and the AI backends |
| Relationship | — | MeshCraft is one of ForgeCraft's backends. Requests that match a MeshCraft template route to it. ForgeCraft packages MeshCraft's own validated export without re-processing it. |

Use MeshCraft directly when you want its brief, profile and manifest control for a known template. Use ForgeCraft for everything else: open-ended briefs, characters, environments, scans, AI generation, scenes, the asset library and the UI.

## 2. Components

```
forgecraft/
  server.py         MCP server (stdio, stdlib only): 17 tools
  pipeline.py       job runner: route → generate → Blender stages → validate → package → hand off; retries, job records
  routing.py        tool selection + fallbacks from rules.json (shared with the UI)
  rules.json        intents, kinds, routes, per-tool requirements
  hardware.py       CPU/RAM/GPU/network probe, backend availability (with reasons), job limits
  library.py        versioned asset library, search, export (handoff)
  backends/         meshcraft_tpl.py (MeshCraft templates) · blockbench.py (.bbmodel writer/reader) · meshroom.py · triposr.py · hunyuan3d.py · mixamo.py
  blender/          run.py (job runner inside Blender) · mc.py (stages) · gen.py (procedural models, rig, animation)
  web-check/        Khronos glTF-Validator + three.js r170 load test in headless Chromium (no sockets: works in the sandbox)
  ui/, ui_server.py the 3D Department interface (static snapshot publisher; no live server)
  cli.py            command line for the same operations
scripts/install-3d.sh   ensures MeshCraft's Blender, installs the engine check, Meshroom, the AI venv and weights
```

## 3. The unified pipeline

Each request is a **job** (`~/.gitcraft/forgecraft-library/jobs/<job>.json`).

| # | Stage | What happens |
|---|---|---|
| 1 | Receive | A brief, optional reference image(s) or photo folder, and options (name, triangle budget, bake size, formats). |
| 2 | Route | `routing.py` matches the request to a route, checks each candidate tool on *this* machine, picks the first available one and records the fallbacks and reasons. |
| 3 | Generate / import | Blender procedural modelling · Blockbench `.bbmodel` · TripoSR · Hunyuan3D · Meshroom · import of an existing mesh · Mixamo FBX merge · scene composition. |
| 4 | Process in Blender | Import, and for scans **crop to subject** and **rescale**. |
| 5 | Clean | Merge doubles, drop loose/degenerate geometry, recalculate normals. |
| 6 | Optimise | Decimate to the triangle budget (capped by the machine's job limit). |
| 7 | UV | Smart UV project. |
| 8 | Textures | Cycles bakes every procedural material into **two PNG maps** (base colour, glTF metallic-roughness) on one material. That gives real texture maps and one draw call. |
| 9 | Rig / animate | Characters: a 22-bone skeleton with Mixamo bone names, rigid skinning, and clips Idle, Walk, Run, Jump, Interact and Attack. Props: e.g. a looping `float_bob` for salvage. |
| 10 | Preview | Cycles thumbnail + turntable frames (transparent PNG). Scenes also get a hero render. |
| 11 | Export | GLB, glTF (+ .bin + textures), FBX (embedded textures), OBJ (+ .mtl), STL and `.blend`. Blockbench assets also ship their `.bbmodel`. |
| 12 | Validate | Re-import in a clean Blender and compare triangles/animations/textures. Then the Khronos glTF-Validator, then a **three.js r170 GLTFLoader load in Chromium** (TIDEBREAKERS' engine version). |
| 13 | Package | Copy into the library as asset `fc3d-…` version N, with `asset.json`. |
| 14 | Hand off | Optional `handoff_dir`, or `library_export` later: copy into a workspace root for FilmCraft, DesignCraft, a game repo, etc. |

**Every asset's `asset.json`** has: `id`, `version`, `name`, `slug`, `kind`, `brief`, `tags`, `source_tool`, `generation` (method + parameters + seed), `route` (chosen tool, fallback, explanation), `license` (asset rights + every tool's licence + AI-generated flag), `provenance` (job, inputs with SHA-256, Blender version, machine), `geometry` (triangles, vertices, dimensions), `materials`, `textures`, `rig`, `animations` (name, frames, seconds, loop), `sockets`, `previews`, `files` (path, bytes, SHA-256 per format), `validation` and `engine` conventions.

**Engine conventions** come from TIDEBREAKERS' `src/ship/shipModel.ts`: metres, glTF Y-up, forward = **+Z** (bow at +Z), right-handed. Boats expose `socket_*` nodes (sail, storage, navigation, steering, hull, flag) at the exact positions where the modular upgrades attach.

**Retries and limits:**
- If a Blender stage fails, the job retries automatically. It first halves the bake and cuts preview frames, then tries again without baking. Each retry is recorded as a `retry_N` stage.
- `job_retry` re-runs any job by hand and appends a new attempt.
- One heavy job runs at a time (file lock).
- Per-backend timeouts apply: Blender 20 min, Meshroom 90 min on CPU, TripoSR 30 min on CPU.
- Bake size and triangle budgets are capped by RAM. Photogrammetry is capped at 120 images on CPU.
- **Blocked ≠ failed.** If no tool on this machine can honour a request, the job ends `blocked` with the reasons and the alternatives. Each alternative is labelled with how it differs from the request (e.g. "will NOT be derived from your image").

## 4. Intelligent routing

`rules.json` is used by both `routing.py` and the UI, so they always agree.

| Request | Route | Tool order (first available wins) |
|---|---|---|
| Treasure chest, flag, lantern, sail, figurehead, crab creature | meshcraft_template | MeshCraft template → Blender procedural → Blockbench |
| Stylized low-poly boat | procedural | Blender procedural → Blockbench → Hunyuan3D |
| Detailed ship from concept art (image) | concept_image | Hunyuan3D → TripoSR |
| Object from photograph (1 image) | photo_image | TripoSR → Hunyuan3D |
| Animated human character | character | Blender (Mixamo-named rig + clips) → Hunyuan3D |
| Reconstructed real-world environment (photos) | photogrammetry | Meshroom → TripoSR → Hunyuan3D |
| Complete game-ready scene | scene | Blender scene composition |
| Blocky / voxel anything, creatures | voxel / creature | Blockbench → Blender procedural / Hunyuan3D |
| Free-form description with no template | detailed_text | Hunyuan3D → Blender procedural → Blockbench |

A 2D image is never substituted for a 3D model. On this machine, "detailed ship from concept art" ends `blocked`. The job explains that Hunyuan3D needs an NVIDIA GPU or network access to the HF Space, and that TripoSR's weights are unreachable. It then offers the Blender procedural sloop as a labelled alternative.

## 5. The interface

Five sections:
- **Asset Factory:** brief + images, a live routing plan, generate, recent assets.
- **Character Studio:** rigged characters with a clip player, a create form and the Mixamo workflow.
- **World Builder:** scene hero renders + viewer, island/lighthouse generators, a scene composer with sun and sky settings.
- **Asset Library:** search/filter, a 3D viewer, overview/files/provenance/validation, downloads, versions, regenerate.
- **Pipeline Monitor:** jobs, stage timelines, errors, attempts, retry, machine + backend availability + limits.

It is mobile-first: on phones the navigation becomes a bottom tab bar.

- **No live mode.** The live server was removed for security: it ran jobs outside the guard and Landlock sandbox and accepted unauthenticated, cross-site and DNS-rebinding requests (`tests/test_forgecraft_web.py`). To run jobs from a browser, use the GITCRAFT control room (`scripts/ui.sh`: 127.0.0.1, per-launch token, Origin/Host checks, every call through `scripts/mcp.sh`).
- **Snapshot** (`ui_server.py --publish <library> <dist>`): a static site of the real assets and job records from a run, deployed to Vercel. Action buttons show the exact MCP call, CLI command and control-room route.

## 6. Operating the department

```bash
# install (once per machine; the setup script / SessionStart hook also does the core)
scripts/install-3d.sh                 # MeshCraft's Blender 5.2 (bpy) + engine check
scripts/install-3d.sh meshroom        # + photogrammetry
scripts/install-3d.sh ai              # + TripoSR / Hunyuan3D runtimes (useful on an NVIDIA GPU or with network)
scripts/doctor.sh                     # shows every 3D backend and why any is unavailable
```

**From Claude Code** (tools on the `forgecraft` MCP server):
1. `hardware_probe`: what this machine can do.
2. `route {"brief": "...", "images": [...]}`: preview the decision.
3. `generate {"brief": "stylized low-poly boat with a red hull", "name": "...", "handoff_dir": "<repo>/assets/3d"}`.
4. `library_search`, `library_get`, `library_export`: browse and hand off.
5. Characters: `generate {"brief": "animated pirate character"}`, then optionally `mixamo_prepare_upload` → mixamo.com → `mixamo_apply`.
6. Scans: `photogrammetry {"images": ["<root>/photos"], "crop": 0.25, "target_size": 2}`. It runs in the background; poll `job_get`.
7. Scenes: `compose_scene {"items": [{"asset": "...", "location": [...]}, {"asset": "...", "attach_to": "boat:socket_sail"}]}`.
8. `jobs_list`, `job_get`, `job_retry`.

**From a terminal:** `python3 forgecraft/cli.py generate "small tropical island"`, `cli.py jobs`, `cli.py retry <job>`, `cli.py serve`.

**Tests:**
- `tests/test_forgecraft.py`: every integration, routing, retries and refusals (add `--slow` to include Meshroom).
- `tests/test_policy.py`: the sandbox for all eight tools.
- `tests/acceptance_tidebreakers.py`: the TIDEBREAKERS package.
