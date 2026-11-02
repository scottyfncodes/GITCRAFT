# 3D Department consolidation report

**Goal:** one coherent 3D Department with ForgeCraft orchestrating and MeshCraft specialising, without duplicated implementations or regressions.

**Starting point:** `main` at `1506bd3`, the merge of PR #9 (ForgeCraft, the 3D Department) into a `main` that already had MeshCraft. Both tools worked, side by side, and each had its own copy of most of the 3D stack.

## 1. What was duplicated (audit on `main` 1506bd3)

| Capability | MeshCraft had | ForgeCraft had | Canonical now |
|---|---|---|---|
| Blender integration | `engine/` (kit, core, bake, templates), run in its server process | `blender/run.py` + `mc.py` + `gen.py`: its own job runner, stages, procedural builders, cleanup, bake, rig, export, validation (1,666 lines) | **MeshCraft.** ForgeCraft's builders were ported into MeshCraft templates (`engine/procedural/`); its runner and stages were removed |
| Blender install | `~/.gitcraft/meshcraft/venv` | used MeshCraft's venv | unchanged: **one** `bpy` install |
| Blockbench | `engine/blockbench.py` (`.bbmodel` 5.0 writer/reader) + `bbimport.py` | `backends/blockbench.py` (another writer) | **MeshCraft's**; ForgeCraft's `blockbench_*` tools delegate |
| Mixamo | `engine/mixamo.py` (prepare upload, merge, refusals for foreign/A-pose skeletons) | `backends/mixamo.py` + stages in `run.py` | **MeshCraft's** (it was the stricter one); ForgeCraft's `mixamo_*` tools delegate |
| Mesh import / scan cleanup | — | `run.py` import + crop stages | **MeshCraft** `mesh_import` template + new `process_mesh` tool |
| Scene composition | — | `run.py` compose stage | **MeshCraft** `engine/scene.py` + new `compose_scene` tool |
| Engine check | `engine_check/three_check.mjs` (three@0.170 + Khronos) | `web-check/check.mjs` (three r170 + Khronos) | **MeshCraft's**, with a new `mixed_materials` contract flag for scenes; ForgeCraft orders it per deliverable |
| Asset library | `engine/library.py` (`~/.gitcraft/meshcraft-library`) | `library.py` (`~/.gitcraft/forgecraft-library`, other format) | **`gitcraft3d/library.py`**, one library `$GITCRAFT_3D_LIBRARY`; MeshCraft's format, plus `annotate` for ForgeCraft's records |
| Jobs | `engine/jobs.py` (attempts, retry ladder) | inside `pipeline.py` | **`gitcraft3d/jobs.py`**, one job store; ForgeCraft jobs get stages, MeshCraft jobs record `parent` |
| Hardware probe | `engine/hardware.py` | `hardware.py` | **`gitcraft3d/hardware.py`**, merged: MeshCraft's capability view and ForgeCraft's backend view from one probe |
| Routing | `engine/route.py` (advice) | `routing.py` + `rules.json` | **`gitcraft3d/routing.py` + `rules.json`**; MeshCraft's `route` returns advice from the same decision |
| Meshroom, TripoSR, Hunyuan3D | reported unavailable | `backends/*.py` | **ForgeCraft** (they are generators, not Blender work); their meshes go through MeshCraft `process_mesh` |

## 2. What changed

**ForgeCraft (orchestrator).** `pipeline.py` now runs: route → generate (MeshCraft for every Blender step, or an external generator followed by MeshCraft `process_mesh`) → engine check (MeshCraft's three.js check on the library copy of the main GLB, with the asset's contract) → record (licence, provenance, routing, geometry, sockets, animations, previews, engine check, deliverable validation, orchestration info written onto MeshCraft's library version) → hand-off. `meshcraft.py` is the bridge: it runs `meshcraft/server.py --call` in a child process inside ForgeCraft's sandbox and passes `parent_job`. ForgeCraft contains no Blender code (a test enforces it).

**MeshCraft (specialist).** Seven templates ported from ForgeCraft's builders: `boat`, `boat_upgrade`, `salvage`, `island`, `lighthouse`, `prop`, `deckhand`, using MeshCraft's palette roles, vertex colours, export profiles and validation. New `mesh_import` template and `process_mesh` tool (scan crop, cleanup, decimation, grounding, rescale, bake), new `compose_scene` tool (sockets, ocean, sky, sun, hero render, scene GLB), `--call` entry point, previews for imported assets, deterministic primitive face order for the ported builders.

**Shared (`gitcraft3d/`).** Library, jobs, hardware, routing and rules, loaded by path inside the sandbox (the repo root is not readable there).

**Launcher and install.** `scripts/tools.sh` computes `GITCRAFT_3D_LIBRARY`; `scripts/mcp.sh` gives both servers write access to it and read access to `gitcraft3d/` (and ForgeCraft read access to `meshcraft/` and MeshCraft's venv). `install-3d.sh core` relies on MeshCraft's install for Blender and the engine check. `doctor.sh` reports the shared library.

**UI.** Reads the unified library and job store; the Pipeline Monitor shows each ForgeCraft job with the MeshCraft jobs it started.

**Size.** 56 files changed under `forgecraft/`, `meshcraft/`, `gitcraft3d/`, `scripts/`, `tests/`: +2,150 / −3,092 lines (net −942) while adding two MeshCraft tools and seven templates.

## 3. Compatibility

- **MCP tool names:** all 17 ForgeCraft 1.0 tools and all 28 MeshCraft tools on `main` still exist with the same names and arguments. MeshCraft adds `process_mesh` and `compose_scene`. ForgeCraft 1.0 tool ids in requests (`blender_procedural`, `blender_character`, `blender_scene`, `import`) are accepted as aliases.
- **MeshCraft builds:** the existing templates (chest, crab, flag, lantern, sail, sun_figurehead) and export profiles are unchanged; `test_meshcraft.py`'s determinism checks still pass.
- **Library:** an existing `~/.gitcraft/meshcraft-library` is used in place (same format); `GITCRAFT_MESHCRAFT_LIBRARY` and `FORGECRAFT_LIBRARY` are honoured. ForgeCraft 1.0's `~/.gitcraft/forgecraft-library` (different format, `fc3d-…` ids) is **not migrated or deleted**; it was only ever populated by PR #9's acceptance run. Regenerating an asset puts it in the new library.
- **Asset ids:** ForgeCraft assets now use readable ids (`tidebreakers_coastal_sloop`) instead of `fc3d-…` hashes.

## 4. Guardrails

| Guardrail | How it was kept |
|---|---|
| Don't modify unrelated tools | The seven ArtCraft tools, `guard.py` and `sandbox.py` are untouched. `mcp.sh` changed only in the meshcraft and forgecraft branches. |
| Don't regress | Every MCP tool name kept; MeshCraft's existing tests and determinism checks pass; policy test passes for all nine tools. |
| Don't remove working integrations without a verified replacement | Each removed ForgeCraft module has a replacement exercised by a test: Blockbench (`test_forgecraft` voxel crab, `blockbench_build/_inspect`), Mixamo (`mixamo_apply`, `mixamo_prepare_upload`), Blender stages (every template through `generate`), scan import (`process_mesh`, `photogrammetry` in acceptance), scenes (`compose_scene`), engine check (every `generate`). |
| Licensing | No dependency added or removed; no paid service. **One classification to note:** ForgeCraft's Blender builders (which import `bpy`) now live under `meshcraft/`, whose README says to treat its contents as GPL-3.0-or-later because they are built on Blender's Python API. They imported `bpy` before too; the move makes that explicit. Assets are unaffected. See [3d-licensing.md](3d-licensing.md). |
| Keep Blender shared | One `bpy` venv; `test_fresh_install.sh` checks nothing Blender-related is installed under ForgeCraft's home. |
| Preserve sandbox isolation | ForgeCraft's MeshCraft calls are child processes inside ForgeCraft's Landlock domain; both servers keep no network. Two read-only additions: both servers can read `gitcraft3d/`, and MeshCraft can read `~/.gitcraft/forgecraft` so its `hardware_probe` reports Meshroom/AI availability (it never runs them). The only new write access is the shared library, which each server could already write in its own form. `test_policy.py` checks kernel-only escapes for both. |
| No success from mocks | Every test drives the real servers through `scripts/mcp.sh`; Blender, Meshroom and the three.js check run for real. Mixamo clips and photogrammetry photos are fixtures (stated wherever they appear) because mixamo.com needs a person and no camera is available. |

## 5. Test results

All run on this branch (main 1506bd3 + the consolidation), on 4 CPU threads, 15.7 GB RAM, no GPU. Every test drives the real servers through `scripts/mcp.sh` (guard + Landlock).

| Suite | Result | Covers |
|---|---|---|
| `tests/test_policy.py` | **28/28** | Security policy for all nine tools: handshakes, path refusals, deny list, kernel-only escapes (ForgeCraft and MeshCraft included), audit hashes |
| `tests/test_meshcraft.py` | **59/59** | MeshCraft templates (old and ported), determinism, profiles, validation, engine check, Blockbench, Mixamo, library/jobs, `process_mesh`, `compose_scene`, a hostile `run_script` blocked by the kernel (no read, write or network outside the workspace); `--call` is exercised by every ForgeCraft test |
| `tests/test_forgecraft.py` | **37/37** | One implementation per capability, routing and fallbacks, refusals, MCP orchestration, ForgeCraft → MeshCraft child jobs, shared library record, retry → next version, `same_as`, delegated Blockbench/Mixamo/scene/process_mesh, honest blocked jobs |
| `tests/test_fresh_install.sh` | **pass** (10 checks) | Empty HOME → `install.sh meshcraft forgecraft` → one Blender → status, registration, doctor → first real job through both sandboxed servers |
| `tests/acceptance_tidebreakers.py` | **110/110** | The TIDEBREAKERS package: boat (7 profiles, sockets), 5 upgrades, salvage, island, deckhand (6 clips) + Mixamo merge, chest, Blockbench crab, Meshroom scan → `process_mesh`, composed scene, hand-offs to FilmCraft and DesignCraft, three.js r170 scene load with a non-blank screenshot |

Found and fixed during the final runs: the engine check's camera clipped scenes larger than 100 m, so the scene screenshot was blank while the load checks passed. The far plane now scales with the asset, and the acceptance test fails on a blank screenshot.

Not exercised here: TripoSR and Hunyuan3D (no GPU, Hugging Face blocked; they refuse with the reason, tested), real mixamo.com downloads (fixtures in Mixamo's layout), real camera photos (Cycles renders).
