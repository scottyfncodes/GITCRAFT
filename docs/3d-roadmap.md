# GITCRAFT 3D roadmap

Status as of November 2026, after the MeshCraft foundation and the TIDEBREAKERS 3D pilot.

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

### 1. Immediate improvements (days)
1. **TIDEBREAKERS GLTFLoader adoption.** Behind a feature flag, load `tb_chest_*.glb` in `chestMesh()`, keeping the `{root, lid, glow}` API; the handoff in `creative/3d/HANDOFF.md` has the code. Engineering-owned.
2. **Ship-hull template** for the dinghy and sloop. It would be parametric from the 2D ship sheet (length, beam, sheer, bow rake) and reuse the sail, flag, lantern and figurehead parts. Then the 2D progression's Brig and Grand Tidebreaker become real 3D proposals.
3. **Environment-prop kit**: palm, rock, barrel, crate, hut, dock segment and bunting, matching `src/world/props.ts`, so islands can mix authored props with procedural terrain.
4. **Turntable and clip videos**: render the frames, then cut them in FilmCraft (the tool already exists) for review and marketing.

### 2. Required 3D infrastructure (weeks)
1. **Per-game profile files** checked into each game repo (scale, axis, budget, material mode), read by MeshCraft from the brief.
2. **Asset registry**: each game's `creative/3d/` manifest drives a typed loader manifest (`assets.json`) the game imports, so adding an asset needs no code.
3. **Texture painting path**: bake palette, AO and curvature into a hand-painted-style atlas (Blender bake on CPU), for games that want texture over vertex colour.
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
