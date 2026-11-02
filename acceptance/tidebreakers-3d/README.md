# TIDEBREAKERS 3D acceptance package

Produced by `tests/acceptance_tidebreakers.py` with GITCRAFT's 3D Department (meshcraft). Every call went through the sandboxed MCP server, as Claude Code drives it. Result: **61/61 checks passed** (2026-11-02T18:56:23Z → 2026-11-02T19:04:18Z).
Machine: 4 CPU threads, 15.7 GB RAM, no GPU.

**Engine target:** TIDEBREAKERS (Vite + TypeScript + three.js r170). GLB, metres, Y-up, forward/bow = +Z, matching `src/ship/shipModel.ts`. Every GLB passed the Khronos glTF-Validator with 0 errors and loaded in three.js r170's GLTFLoader in Chromium.

## Assets (latest versions)

| Asset | ID | Made with | Triangles | Texture maps | Animations | Formats | Validation | Files |
|---|---|---|---|---|---|---|---|---|
| TIDEBREAKERS Coastal Sloop | `mc3d-a3772b915c` v1 | blender | 4,384 | 2 | — | blend, fbx, glb, gltf, obj, stl | passed | [GLB](library/assets/mc3d-a3772b915c/v1/tidebreakers_coastal_sloop.glb) · [preview](library/assets/mc3d-a3772b915c/v1/previews/tidebreakers_coastal_sloop_thumb.png) |
| Upgrade: Canvas Mainsail | `mc3d-19d66f8164` v1 | blender | 588 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-19d66f8164/v1/upgrade_canvas_mainsail.glb) · [preview](library/assets/mc3d-19d66f8164/v1/previews/upgrade_canvas_mainsail_thumb.png) |
| Upgrade: Lashed Cargo Crates | `mc3d-d2a99fe45f` v1 | blender | 492 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-d2a99fe45f/v1/upgrade_lashed_cargo_crates.glb) · [preview](library/assets/mc3d-d2a99fe45f/v1/previews/upgrade_lashed_cargo_crates_thumb.png) |
| Upgrade: Brass Compass | `mc3d-1ebf521f89` v1 | blender | 698 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-1ebf521f89/v1/upgrade_brass_compass.glb) · [preview](library/assets/mc3d-1ebf521f89/v1/previews/upgrade_brass_compass_thumb.png) |
| Upgrade: Ship's Wheel & Ash Rudder | `mc3d-85d92f89e5` v1 | blender | 1,016 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-85d92f89e5/v1/upgrade_ship_s_wheel_ash_rudder.glb) · [preview](library/assets/mc3d-85d92f89e5/v1/previews/upgrade_ship_s_wheel_ash_rudder_thumb.png) |
| Upgrade: Copper-Banded Hull | `mc3d-4a16a43440` v1 | blender | 1,912 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-4a16a43440/v1/upgrade_copper_banded_hull.glb) · [preview](library/assets/mc3d-4a16a43440/v1/previews/upgrade_copper_banded_hull_thumb.png) |
| Floating Salvage | `mc3d-c5eb5774ee` v1 | blender | 1,188 | 2 | float_bob | blend, fbx, glb | passed | [GLB](library/assets/mc3d-c5eb5774ee/v1/floating_salvage.glb) · [preview](library/assets/mc3d-c5eb5774ee/v1/previews/floating_salvage_thumb.png) |
| Turtle Cay | `mc3d-42b31cb7ed` v1 | blender | 10,340 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-42b31cb7ed/v1/turtle_cay.glb) · [preview](library/assets/mc3d-42b31cb7ed/v1/previews/turtle_cay_thumb.png) |
| Reef Crab (Blockbench) | `mc3d-90b9eb629d` v1 | blockbench → blender | 216 | 1 | — | bbmodel, blend, fbx, glb | passed | [GLB](library/assets/mc3d-90b9eb629d/v1/reef_crab_blockbench.glb) · [preview](library/assets/mc3d-90b9eb629d/v1/previews/reef_crab_blockbench_thumb.png) |
| Deckhand Pip | `mc3d-901dd35510` v2 | mixamo → blender | 1,476 | 2 | Attack, Idle, Interact, Jump, MixamoLayout_Jump, MixamoLayout_Walk, Run, Walk | blend, fbx, glb | passed-with-warnings | [GLB](library/assets/mc3d-901dd35510/v2/deckhand_pip.glb) · [preview](library/assets/mc3d-901dd35510/v2/previews/deckhand_pip_thumb.png) |
| TIDEBREAKERS Turtle Cay Scene | `mc3d-d5190393ef` v1 | blender | 26,410 | 17 | Attack, float_bob, Idle, Interact, Jump, MixamoLayout_Jump, MixamoLayout_Walk, Run, Walk | blend, glb | passed-with-warnings | [GLB](library/assets/mc3d-d5190393ef/v1/tidebreakers_turtle_cay_scene.glb) · [preview](library/assets/mc3d-d5190393ef/v1/previews/tidebreakers_turtle_cay_scene_thumb.png) |
| Salvage Raft (photogrammetry scan) | `mc3d-1356f6cb3f` v3 | meshroom → blender | 1,194 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/mc3d-1356f6cb3f/v3/salvage_raft_photogrammetry_scan.glb) · [preview](library/assets/mc3d-1356f6cb3f/v3/previews/salvage_raft_photogrammetry_scan_thumb.png) |

Notes on specific assets:

- **Deckhand Pip v2** is v1 plus two clips merged through the Mixamo import path. Those clips are **fixtures in Mixamo's download layout, exported from the character's own rig**, not files from mixamo.com.
- **"passed-with-warnings"** is the Khronos warning `NODE_SKINNED_MESH_NON_ROOT`. The skinned mesh sits under the asset's root node, which is harmless because that root has an identity transform.
- **The photogrammetry scan** was reconstructed by Meshroom 2023.3 from 36 **Cycles renders of the floating-salvage asset**, not from real camera photos. It used the CPU draft pipeline and solved all 36 cameras, so it is draft quality.
  - v1 is from the acceptance run.
  - v2 and v3 are `job_retry` re-runs. They reused Meshroom's cache and added fragment removal and floating-outlier removal to the scan cleanup stage.

## Required deliverables

| Requirement | Delivered |
|---|---|
| Recognisable 3D player boat | TIDEBREAKERS Coastal Sloop: lofted hull ported from `shipModel.ts`, deck, cabin, mast, boom, striped mainsail, jib, rails, tiller, lantern, flag. Six `socket_*` attachment nodes. All six formats (GLB, glTF, FBX, OBJ, STL, .blend). |
| Modular upgrade components | Canvas Mainsail, Lashed Cargo Crates, Brass Compass, Ship's Wheel & Ash Rudder, Copper-Banded Hull. These are the five TIDEBREAKERS upgrade slots, each modelled at its socket origin. |
| Floating salvage object | Lashed crate, barrel, chest and buoy on driftwood, with a looping `float_bob` animation |
| Island / environmental structure | Turtle Cay: noise heightfield (sand, grass, rock), palms, rocks, stilt hut, dock, summit flag. `socket_dock` / `socket_spawn` nodes. |
| Animated character or creature | Deckhand Pip: 22-bone Mixamo-named rig; Idle, Walk, Run, Jump, Interact, Attack (+2 merged clips). Reef Crab built through Blockbench (`.bbmodel` included). |
| Composed 3D scene | TIDEBREAKERS Turtle Cay Scene, assembled in Blender from library GLBs. The four hull/deck upgrades are attached to the sloop's sockets (the canvas mainsail replaces the base sail in game). The deckhand stands on the dock socket and the crab at the spawn socket. Ocean, sun, sky and a hero render. Exported as scene GLB + .blend. |
| Real geometry, GLB/glTF, textures, previews, metadata | Every asset: baked PNG base-colour + metallic-roughness maps (Blockbench: its pixel-art texture), a Cycles thumbnail + turntable, and `asset.json` (ID, provenance, licence, stats, validation) |
| Downstream handoffs | `library_export` into the workspace (exports were hashed in the audit log), then: **FilmCraft** cut 24 turntable frames into `handoffs/coastal_sloop_turntable.mp4`; **DesignCraft** laid out `handoffs/tidebreakers_3d_asset_sheet.png` (+ `.designcraft`) from every preview |
| Imported into a real 3D scene | (1) Blender scene composition; (2) three.js r170 loads the scene, boat and character GLBs into one engine scene, with clips playing: `handoffs/threejs_r170_import.png` / `.json` |

## Layout

- `library/`: snapshot of the MeshCraft library. `index.json`, `assets/<id>/v<N>/` (exports, textures, previews, `asset.json`) and `jobs/*.json` (routing, stages, timings, attempts). The deployed 3D Department UI is built from this folder.
- `handoffs/`: FilmCraft MP4, DesignCraft sheet, three.js import screenshot + report.
- `REPORT.json`: every check, asset and handoff from the acceptance run. Its `assets/<slug>_vN/` paths are the `library_export` handoff copies; they are not committed, because the same files are in `library/assets/`. `python3 meshcraft/cli.py export <id> <dir>` recreates them.

**Using an asset in TIDEBREAKERS:**

```ts
new GLTFLoader().load(url, (g) => scene.add(g.scene));
```

For the game's toon look, swap each `MeshStandardMaterial` for `MeshToonMaterial({ map: m.map, gradientMap: toonGradient() })`. To fit an upgrade, add it as a child of the boat's matching `socket_*` node.
