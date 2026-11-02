# The 3D Department

GITCRAFT's 3D Department is two MCP servers sharing one foundation:

- **ForgeCraft** (`forgecraft`) is the **orchestrator**. It takes a request, decides how to make it on this machine, coordinates the tools, checks the deliverable in the game engine, records routing, licence and provenance, and hands the asset off.
- **MeshCraft** (`meshcraft`) is the **modelling and asset specialist**. It does every Blender step: procedural modelling, mesh import and cleanup, materials and UVs, PBR baking, rigging and animation, previews, geometry validation, export per engine profile and the three.js engine check. Its templates give deterministic builds.
- **gitcraft3d/** is the shared foundation: **one** asset library, **one** job store, **one** hardware probe and **one** router, imported by both servers.

Blender is installed once (`~/.gitcraft/meshcraft/venv`, the `bpy` 5.2.3 wheel) and used only by MeshCraft. The consolidation that produced this layout, with what moved where and what was removed, is in [3d-consolidation.md](3d-consolidation.md). Licences, hardware and cost are in [3d-licensing.md](3d-licensing.md) and [forgecraft-licensing.md](forgecraft-licensing.md).

## 1. Architecture

```
                    Claude Code ── MCP ──┬───────────────────────────────┬──────────────
                                         │                               │
          scripts/mcp.sh forgecraft (guard + Landlock)    scripts/mcp.sh meshcraft (guard + Landlock)
                    ┌────────▼─────────┐                       ┌─────────▼──────────┐
                    │    ForgeCraft     │  meshcraft.call()     │      MeshCraft      │
                    │  orchestrator     │ ─────────────────────►│  Blender 5.2 (bpy)  │
                    │  stdlib Python    │  server.py --call     │  templates, import, │
                    │  route · engine   │  (child process, same │  bake, rig, export, │
                    │  check · record · │   sandbox, parent_job)│  validate, scenes   │
                    │  hand-off · UI    │                       │                     │
                    └──┬─────────┬──────┘                       └─────────┬───────────┘
                       │ backends│ (external generators)                 │
          Meshroom · TripoSR · Hunyuan3D                                 │
                       │                                                  │
                       └───────────────► gitcraft3d/ ◄────────────────────┘
                                 library · jobs · hardware · routing (+ rules.json)
                                 one library: $GITCRAFT_3D_LIBRARY (~/.gitcraft/3d-library)
```

**How ForgeCraft calls MeshCraft.** `forgecraft/meshcraft.py` runs `meshcraft/server.py --call <tool> @args.json` with MeshCraft's Blender Python. That is the same code path as MeshCraft's MCP `tools/call`, in a child process that inherits ForgeCraft's sandbox. ForgeCraft passes `parent_job`, so MeshCraft's job record points back at the ForgeCraft job, and MeshCraft adds the library version. ForgeCraft then annotates that same version with routing, licence, provenance, engine-check results and orchestration info. There is no second copy of the asset.

**Sandbox.** Both servers start through `scripts/mcp.sh` behind `guard.py` and Landlock:

| Server | Can write | Can read/execute (besides the roots) | Network |
|---|---|---|---|
| meshcraft | roots, `$GITCRAFT_3D_LIBRARY`, own state | `~/.gitcraft/meshcraft` (Blender venv), `meshcraft/`, `gitcraft3d/`, `~/.gitcraft/forgecraft` | none |
| forgecraft | roots, `$GITCRAFT_3D_LIBRARY`, model cache, own state | `forgecraft/`, `gitcraft3d/`, `meshcraft/`, MeshCraft's Blender venv, `~/.gitcraft/forgecraft` (Meshroom, AI venv) | none, unless `GITCRAFT_ALLOW_NET=1` |

The repo root itself is not readable inside the sandbox, so both servers load `gitcraft3d` by path (`_gitcraft3d.py`).

**Library location.** `$GITCRAFT_3D_LIBRARY`, set by `scripts/tools.sh`. The default is `~/.gitcraft/3d-library`. An existing `~/.gitcraft/meshcraft-library` (same format) is used in place when no 3d-library exists, and `GITCRAFT_MESHCRAFT_LIBRARY` / `FORGECRAFT_LIBRARY` are still honoured. ForgeCraft 1.0's `~/.gitcraft/forgecraft-library` used a different record format; it is left untouched and not read.

## 2. Capability ownership

One implementation per capability. "Entry points" are the MCP tools; tools marked *delegates* keep their ForgeCraft 1.0 names but call MeshCraft.

| Capability | Owner | Implementation | Entry points |
|---|---|---|---|
| Request intake, routing, fallbacks, refusals | ForgeCraft (rules shared) | `gitcraft3d/routing.py` + `rules.json` | forgecraft `route`, `generate`; meshcraft `route` (advice, same decision) |
| Hardware / backend probe, job limits | shared | `gitcraft3d/hardware.py` | `hardware_probe` on both |
| Job records, attempts, retries, parent/child links | shared | `gitcraft3d/jobs.py` | `jobs_list`, `job_get`, `job_retry` on both |
| Versioned asset library, search, verified export | shared | `gitcraft3d/library.py` | `library_search/get/export` on both |
| Procedural modelling (templates) | MeshCraft | `meshcraft/engine/templates/*` (chest, crab, flag, lantern, sail, sun_figurehead, boat, boat_upgrade, salvage, island, lighthouse, prop, deckhand) + `engine/procedural/` | meshcraft `run_pipeline`, `build_asset`; forgecraft `generate` |
| Mesh import, scan crop, cleanup, decimation, rescale | MeshCraft | `templates/mesh_import.py` | meshcraft `process_mesh`; forgecraft `process_mesh`, `photogrammetry` |
| Materials, palette roles, vertex colours, UVs | MeshCraft | `engine/kit.py`, `engine/palette.py`, `engine/core.py` | all builds |
| PBR texture baking | MeshCraft | `engine/bake.py` (Cycles) | `web-pbr` export profile |
| Rigging and animation clips | MeshCraft | `templates/deckhand.py` (Mixamo-named rig, 6 clips), template clips | builds |
| Blockbench (`.bbmodel` write, inspect, import) | MeshCraft | `engine/blockbench.py`, `engine/bbimport.py` | meshcraft `blockbench_*`; forgecraft `blockbench_build/_inspect` (*delegates*), `generate` (voxel route) |
| Mixamo (prepare upload, merge clips) | MeshCraft | `engine/mixamo.py` | meshcraft `mixamo_*`; forgecraft `mixamo_*` (*delegates*) |
| Scene composition (sockets, ocean, sky, hero render) | MeshCraft | `engine/scene.py` | meshcraft `compose_scene`; forgecraft `compose_scene` |
| Previews, contact sheets | MeshCraft | `engine/core.py` (Cycles CPU) | builds |
| Geometry validation, Khronos validator, Blender re-import | MeshCraft | `engine/core.py`, `engine_check/validate.mjs` | `validate_asset`, builds |
| Export profiles (GLB toon/atlas/PBR, FBX, OBJ, STL, Godot) | MeshCraft | `meshcraft/profiles/*.json` + `engine/core.py` | `export_asset`, builds |
| Engine check (three.js r170 in Chromium) | MeshCraft (ForgeCraft orders it per deliverable) | `engine_check/three_check.mjs` | meshcraft `engine_check`; forgecraft `generate` stage |
| Photogrammetry | ForgeCraft (generator) → MeshCraft (cleanup) | `forgecraft/backends/meshroom.py` | forgecraft `photogrammetry` |
| Image/text → 3D (AI) | ForgeCraft (generator) → MeshCraft (cleanup) | `forgecraft/backends/triposr.py`, `hunyuan3d.py` | forgecraft `generate` |
| Licence, provenance, deliverable validation records | ForgeCraft | `forgecraft/pipeline.py` → `library.annotate` | `generate` and every ForgeCraft job |
| Hand-off to games and other GITCRAFT tools | shared | `library.export` (hash-verified) | `library_export`, `handoff_dir` |
| Department UI | ForgeCraft | `forgecraft/ui/`, `ui_server.py` | `ui_server.py`, `cli.py serve` |

## 3. The pipeline

Every ForgeCraft request is a job with these stages. Each stage is recorded with timing and errors (`job_get`).

| # | Stage | Who | What happens |
|---|---|---|---|
| 1 | Brief intake | ForgeCraft | Brief, reference images or photo folder, options (name, template params, triangle budget, bake size, export profiles, hand-off folder). |
| 2 | Method selection | ForgeCraft | `routing.route` matches the request to a route, checks each candidate on *this* machine, picks the first available and records fallbacks and reasons. If nothing can honour it, the job ends **blocked** with alternatives, each labelled with how it differs (e.g. "will NOT be derived from your image"). A 2D image is never substituted. |
| 3 | Generation | MeshCraft or a generator | MeshCraft template · Blockbench project via MeshCraft · Meshroom · TripoSR · Hunyuan3D · an existing mesh · Mixamo merge · scene composition. |
| 4 | Cleanup and validation | MeshCraft | Imported meshes: scan crop, floor/fragment/outlier removal, merge doubles, degenerate geometry, normals, decimation to budget, grounding and rescale (`process_mesh`). Every build: geometry, budget, origin, scale, colours, clips and skinning checks. |
| 5 | Materials and textures | MeshCraft | Palette roles and vertex colours; atlas or Cycles-baked PBR maps (base colour, ORM) per profile. |
| 6 | Rigging and animation | MeshCraft | Template rigs and clips (deckhand: 22-bone Mixamo-named skeleton, Idle/Walk/Run/Jump/Interact/Attack); Mixamo clips merged by bone name. |
| 7 | Export | MeshCraft | Per profile: `three-web-toon`, `three-web-atlas`, `web-pbr`, `unity-fbx`, `obj-static`, `stl-print`, `godot-glb`, plus the `.blend` source and previews. Khronos validator + Blender re-import on every GLB. |
| 8 | Deliverable validation | ForgeCraft orders, MeshCraft runs | The main GLB from the library copy loads in three.js r170 `GLTFLoader` in Chromium with the asset's contract (ground contact, clips, mixed materials for scenes); the screenshot is stored with the version. |
| 9 | Provenance, licensing, dependencies | ForgeCraft | `library.annotate`: route, every tool's licence, AI-generated flag, ForgeCraft and MeshCraft job ids, inputs with SHA-256, Blender version, machine, geometry, sockets, animations, previews, engine check. |
| 10 | Hand-off | shared | `handoff_dir` or `library_export`: copies the version into a workspace root and re-verifies every hash. FilmCraft, DesignCraft or a game repo take it from there. |

**Retries.** MeshCraft retries a failed build with lighter settings (smaller previews and bake, then no bake) and marks the job `done_with_fallback`. `job_retry` on a ForgeCraft job re-runs the same request as a new attempt and adds the next version of the same asset; on a MeshCraft job it re-runs in MeshCraft. A re-run whose exports match the previous version is marked `same_as`.

**Engine conventions** (TIDEBREAKERS `src/ship/shipModel.ts`): metres, glTF Y-up, forward = +Z. Boats expose `socket_*` empties (sail, storage, navigation, steering, hull, flag) where the modular upgrades attach; islands expose `socket_dock` and `socket_spawn`.

## 4. Routing

`gitcraft3d/rules.json` drives the router, MeshCraft's `route` advice and the UI, so they always agree. ForgeCraft 1.0 tool ids (`blender_procedural`, `blender_character`, `blender_scene`, `import`) are accepted as aliases.

| Request | Route | Tool order (first available wins) |
|---|---|---|
| Photo set (8+ photos, or "photogrammetry"/"scan" with photos) | photogrammetry | Meshroom → TripoSR → Hunyuan3D |
| Detailed asset from concept art (image) | concept_image | Hunyuan3D → TripoSR |
| Object from a photograph | photo_image | TripoSR → Hunyuan3D |
| Complete scene | scene | MeshCraft scene composition |
| Blocky / voxel anything | voxel | Blockbench (via MeshCraft) → MeshCraft template |
| Anything a MeshCraft template makes: chest, crab, flag, lantern, sail, figurehead, boat, upgrade, salvage, island, lighthouse, barrel/crate/rock/palm prop, character | template | MeshCraft template → Blockbench (via MeshCraft) → Hunyuan3D |
| Other creatures | creature | Blockbench (via MeshCraft) → Hunyuan3D |
| Free-form description with no template | detailed_text | Hunyuan3D → MeshCraft template → Blockbench |

Routes are tried in that order; the first whose condition matches decides. On a machine with no GPU and no Hugging Face access, a free-form brief therefore ends at a MeshCraft template or Blockbench, and an image request ends **blocked**.

## 5. The interface

`forgecraft/ui/` reads the unified library and job store:
- **Asset Factory:** brief + images, a live routing plan, generate, recent assets.
- **Character Studio:** rigged characters with a clip player, a create form and the Mixamo workflow.
- **World Builder:** scene hero renders and viewer, island/lighthouse generators, a scene composer.
- **Asset Library:** search, a 3D viewer, files with hashes, provenance, licence, validation and engine check, versions.
- **Pipeline Monitor:** ForgeCraft jobs with the MeshCraft jobs they started ("Delegated to MeshCraft"), stage timelines, attempts, errors, retry, and machine/backend availability.

Live (`python3 forgecraft/ui_server.py`, 127.0.0.1 only) buttons run real jobs. The published snapshot (`ui_server.py --publish <library> <dist>`, deployed to Vercel from `acceptance/tidebreakers-3d/library`) shows the real assets and job records of the acceptance run; there, action buttons show the exact MCP call instead.

## 6. Operating the department

```bash
scripts/install.sh meshcraft forgecraft  # Blender (bpy) + engine check, ForgeCraft; the setup script / SessionStart hook do this
scripts/install-3d.sh meshroom           # + photogrammetry (~2 GB)
scripts/install-3d.sh ai                 # + TripoSR / Hunyuan3D runtimes (useful with an NVIDIA GPU or network)
scripts/doctor.sh                        # every 3D backend, why any is unavailable, the library path
```

**From Claude Code:** `hardware_probe` or `route` first; `generate {"brief": …}` for anything; `compose_scene`, `photogrammetry`, `process_mesh`, `mixamo_*` for the specific paths; `library_export` to hand off. Use MeshCraft directly (`run_pipeline` with a brief) when you want full control of a template build, its profiles and the project manifest; the result lands in the same library.

**From a terminal:** `python3 forgecraft/cli.py generate "small tropical island"`, `cli.py jobs`, `cli.py retry <job>`, `cli.py serve`.

**Tests:** `tests/test_policy.py` (sandbox, all nine tools), `tests/test_meshcraft.py`, `tests/test_forgecraft.py` (`--slow` adds Meshroom), `tests/test_fresh_install.sh` (install into an empty home), `tests/acceptance_tidebreakers.py` (the TIDEBREAKERS package).
