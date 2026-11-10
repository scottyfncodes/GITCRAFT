# GITCRAFT 3D roadmap

Status as of November 2026, after the MeshCraft foundation, the TIDEBREAKERS 3D pilot, the ForgeCraft 3D Department (PR #9) and the consolidation of both into one department (ForgeCraft orchestrates, MeshCraft specialises; see [3d-consolidation.md](3d-consolidation.md)).

**Guiding rule:** GITCRAFT adapts to each game; games are never redesigned or downgraded to fit the tooling. When a game needs something MeshCraft can't make yet, the answer is a new template, a `run_script` workflow or a new integration. A simpler game is never the answer.

## Portfolio survey (what the exports must serve)

A GitHub code search across the portfolio found **13 games built on Three.js**: TIDEBREAKERS, ROCKSLIDE, NIGHT-WATCH, SKYRUSH, SKYTRACE, KNUCKLE-HUCK, BONSAI, Bruh, BACKYARD-LAB, DEMO-DAY, DETECTOR, DOWNTOWN-DERBY and Diamond-Pinball. No game uses Phaser, Babylon.js, Pixi, React-Three-Fiber, Godot or Unity, and **none loads glTF files yet**: every game builds its geometry procedurally in code. That made the priorities:
1. **GLB for Three.js**, with baked vertex colours (`three-web-toon`), so assets drop into vertex-coloured toon pipelines like TIDEBREAKERS'.
2. Atlas-textured GLB, FBX and OBJ as configurable profiles for any future engine, not hard-coded assumptions.
3. A one-time **GLTFLoader integration** per game is the first engineering step to use any 3D deliverable (see the TIDEBREAKERS handoff).

## Prioritized plan

### Done (this work)
| Item | Where |
|---|---|
| Kernel sandbox (Landlock, filesystem + network) for every tool, central launcher, guard with audit log and handoff hashes | GITCRAFT PR #4 |
| FilmCraft and LightCraft fenced (they had no file roots) | PR #4 |
| Pre-session install (`setup-env.sh`), multi-repo fix, doctor, `status.json` | PR #4 |
| MeshCraft: Blender 5.2 MCP server, brief schema, palette loader (JSON/CSS/GPL/ASE), modelling kit, 6 templates (prop, ship parts, skeletal flag, morph sail, rigged character), previews and contact sheets with 2D references, validation, 5 export profiles, LODs, convex collision, Khronos validator, Three.js engine check, manifest updates, `run_script` | MeshCraft PR |
| TIDEBREAKERS 3D pilot: drop-in chest (3 tiers), lantern, figurehead, flags, sails, Biscuit; engine-verified against `chestMesh()` | TIDEBREAKERS PR |
| **P0 hardening**: the guard also hashes files a tool names only in its result (`outputs` in `audit.jsonl`); MeshCraft builds are reproducible (stable colour seeds, canonical primitive face order); doctor reads MeshCraft's version on upgraded installs; tests for the 2 s MeshCraft handshake and the audit outputs | P0/P1 PR |
| **P1 from the 3D Department proposal (PR #9)**, added beside the existing 14 tools: `hardware_probe`, `blockbench_build` / `_inspect` / `_import`, `mixamo_guide` / `_prepare_upload` / `_apply`; `web-pbr` (baked texture maps) and `stl-print` profiles. The 9 TIDEBREAKERS briefs export identical files before and after | P0/P1 PR |

| **3D Department (PR #9)**: ForgeCraft pipeline server, routing with honest refusals, Meshroom photogrammetry, TripoSR/Hunyuan3D adapters, department UI, TIDEBREAKERS acceptance package | PR #9 |
| **Consolidation**: one library, job store, probe and router (`gitcraft3d/`); every Blender step in MeshCraft (7 templates, `mesh_import`/`process_mesh`, `compose_scene` ported from ForgeCraft); ForgeCraft as orchestrator with parent/child jobs, engine check per deliverable, licence and provenance records; duplicate Blockbench, Mixamo, Blender runner and engine-check code removed; all ForgeCraft 1.0 tool names kept | consolidation PR |

### Next phases (from the PR #9 assessment)
- **P2 (done)** jobs and a versioned asset library: job records with a retry ladder, `job_retry`, library search/get/export with re-verified hashes, `same_as` for identical re-runs, `route` as advice only. Re-running all 9 TIDEBREAKERS briefs gives identical exports and a `same_as` version for each.
- **P3 (done)** Meshroom photogrammetry as an optional install, inside the sandbox (ForgeCraft backend; MeshCraft `process_mesh` cleans the scan).
- **P4 (done)** the GITCRAFT control room (`scripts/ui.sh`, `docs/ui.md`): a local, phone-first UI for every tool that acts only through the guarded launcher, with a per-launch token, origin/host checks and a read-only snapshot for previews. The 3D Department UI (`forgecraft/ui_server.py`) is now a static snapshot publisher only: its live server, which ran jobs outside the sandbox, was removed, every action it offered is a ForgeCraft MCP tool run through the launcher, and `tests/test_forgecraft_web.py` guards against its return. A static snapshot of the acceptance library is published.
- **P5 (adapters done, not exercised)** AI generation (TripoSR, then Hunyuan3D) is opt-in and refuses with the reason when unavailable. Still to do: run both on a GPU machine or with Hugging Face access, per-host network allowances instead of `GITCRAFT_ALLOW_NET=1`, and approval of cost, data sharing and licence territory.
- **P6 (next, from the consolidation)** stream MeshCraft progress into ForgeCraft's job record while a child runs (today stages update when the child finishes); migrate ForgeCraft 1.0 `~/.gitcraft/forgecraft-library` records if anyone still has them; a CI job running `test_meshcraft.py`, `test_forgecraft.py` and `test_policy.py` on every PR.

### 1. Immediate improvements (days)
1. **TIDEBREAKERS GLTFLoader adoption.** Behind a feature flag, load `tb_chest_*.glb` in `chestMesh()`, keeping the `{root, lid, glow}` API; the handoff in `creative/3d/HANDOFF.md` has the code. Engineering-owned.
2. **Ship-hull template** for the dinghy and sloop. It would be parametric from the 2D ship sheet (length, beam, sheer, bow rake) and reuse the sail, flag, lantern and figurehead parts. Then the 2D progression's Brig and Grand Tidebreaker become real 3D proposals.
3. **Environment-prop kit**: palm, rock, barrel, crate, hut, dock segment and bunting, matching `src/world/props.ts`, so islands can mix authored props with procedural terrain.
4. **Turntable and clip videos**: render the frames, then cut them in FilmCraft (the tool already exists) for review and marketing.

### 2. Required 3D infrastructure (weeks)
1. **Per-game profile files** checked into each game repo (scale, axis, budget, material mode), read by MeshCraft from the brief.
2. **Asset registry**: each game's `creative/3d/` manifest drives a typed loader manifest (`assets.json`) the game imports, so adding an asset needs no code.
3. **Texture painting path**: the `web-pbr` bake (shipped) covers colour, roughness, metalness and emission; next, bake AO and curvature into a hand-painted-style atlas.
4. **Weighted skinning** for organic characters: automatic weights (Blender heat) plus clip retargeting between characters sharing a skeleton.
5. **CI for assets**: a GitHub Action that runs `tests/test_meshcraft.py` and re-validates committed GLBs (Khronos + engine check) on every PR.

### 3. Optional advanced capabilities
| Capability | Feasibility now | Notes |
|---|---|---|
| Automated LOD generation | **Production-ready** (shipped) | Decimate ratios per profile (`lods`) |
| Collision mesh generation | **Production-ready** (shipped, convex hull) | Next: per-part hulls (V-HACD-style decomposition) for concave props |
| Procedural environment generation | Ready to build | Blender geometry nodes / Python scatter over a heightfield; TIDEBREAKERS already generates islands in code, so MeshCraft should author *props* and *set pieces*, not replace the game's terrain system |
| Integrated animation preview | **Ready** (engine_check plays clips in three@0.170) | Add a video turntable via FilmCraft |
| Character generation | Template-based: ready (Biscuit) | Stylised humanoids need a modular body kit + shared skeleton; organic sculpts need an artist or AI (below) |

### 4. Experimental integrations
| Capability | What exists | Dependencies and cost | Recommendation |
|---|---|---|---|
| **Image-to-3D** (2D concept → mesh) | Hosted APIs (e.g. Meshy, Tripo, Rodin); open-weight models (e.g. TRELLIS, Hunyuan3D, Stable Fast 3D) | Hosted: paid per generation (credits/subscription), sends art to a third party, needs a network exception to the sandbox. Open-weight: free licences (check each; some restrict commercial use), but need an NVIDIA GPU (roughly 8–24 GB VRAM) we don't have in these containers | Pilot on one prop with a hosted API **only with explicit approval** of cost and data sharing. Treat output as a blockout: retopologise and recolour with MeshCraft to keep the Pebble & Sail look |
| **Text-to-3D** | Same vendors | Same | Lower value than image-to-3D for us: our 2D package already defines the look |
| **AI texturing** | Hosted and open models | GPU or paid API | Not needed for the vertex-colour/flat style; revisit for games with painted textures |
| **Audio / SFX** | TIDEBREAKERS already synthesises audio procedurally (WebAudio). Free: procedural SFX generators (sfxr-style), open-weight audio models (GPU). Paid: hosted SFX/music APIs | Procedural: none. Models: GPU or paid API | Add a small procedural SFX tool to GITCRAFT first (deterministic, free, sandbox-friendly). Licensed or generated music needs a budget decision |

**Nothing here was added with a paid service.** Every capability in this work runs locally on CPU, using Blender (GPL; the tool's licence doesn't extend to its output), three.js (MIT), the Khronos glTF-Validator (Apache-2.0), pygltflib (MIT), Pillow (MIT-CMU) and numpy (BSD).

## Known limits
- No Draco or meshoptimizer compression in the PyPI `bpy` build.
- CPU-only rendering (Cycles), at 2–5 s per preview view.
- Rigid rigs only (no automatic weights yet).
- Landlock needs Linux 5.13+. Other hosts get the guard and native roots only, and `doctor.sh` says so.
