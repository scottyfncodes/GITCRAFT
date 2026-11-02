# TIDEBREAKERS 3D acceptance package

Produced by `tests/acceptance_tidebreakers.py` with GITCRAFT's 3D Department (ForgeCraft, with MeshCraft as one of its backends). Every call went through the sandboxed MCP server, as Claude Code drives it. Result: **66/66 checks passed** (2026-11-02T19:54:53Z → 2026-11-02T20:03:02Z).
Machine: 4 CPU threads, 15.7 GB RAM, no GPU.

**Engine target:** TIDEBREAKERS (Vite + TypeScript + three.js r170). GLB, metres, Y-up, forward/bow = +Z, matching `src/ship/shipModel.ts`. Every GLB passed the Khronos glTF-Validator with 0 errors and loaded in three.js r170's GLTFLoader in Chromium.

## Assets (latest versions)

| Asset | ID | Made with | Triangles | Texture maps | Animations | Formats | Validation | Files |
|---|---|---|---|---|---|---|---|---|
| TIDEBREAKERS Coastal Sloop | `fc3d-9831ff542e` v1 | blender | 4,384 | 2 | — | blend, fbx, glb, gltf, obj, stl | passed | [GLB](library/assets/fc3d-9831ff542e/v1/tidebreakers_coastal_sloop.glb) · [preview](library/assets/fc3d-9831ff542e/v1/previews/tidebreakers_coastal_sloop_thumb.png) |
| Upgrade: Canvas Mainsail | `fc3d-6cca3f5f59` v1 | blender | 588 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-6cca3f5f59/v1/upgrade_canvas_mainsail.glb) · [preview](library/assets/fc3d-6cca3f5f59/v1/previews/upgrade_canvas_mainsail_thumb.png) |
| Upgrade: Lashed Cargo Crates | `fc3d-21a46a8062` v1 | blender | 492 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-21a46a8062/v1/upgrade_lashed_cargo_crates.glb) · [preview](library/assets/fc3d-21a46a8062/v1/previews/upgrade_lashed_cargo_crates_thumb.png) |
| Upgrade: Brass Compass | `fc3d-82b6135f47` v1 | blender | 698 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-82b6135f47/v1/upgrade_brass_compass.glb) · [preview](library/assets/fc3d-82b6135f47/v1/previews/upgrade_brass_compass_thumb.png) |
| Upgrade: Ship's Wheel & Ash Rudder | `fc3d-c75a7997c3` v1 | blender | 1,016 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-c75a7997c3/v1/upgrade_ship_s_wheel_ash_rudder.glb) · [preview](library/assets/fc3d-c75a7997c3/v1/previews/upgrade_ship_s_wheel_ash_rudder_thumb.png) |
| Upgrade: Copper-Banded Hull | `fc3d-0486db99be` v1 | blender | 1,912 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-0486db99be/v1/upgrade_copper_banded_hull.glb) · [preview](library/assets/fc3d-0486db99be/v1/previews/upgrade_copper_banded_hull_thumb.png) |
| Floating Salvage | `fc3d-0b2467cdb8` v1 | blender | 1,188 | 2 | float_bob | blend, fbx, glb | passed | [GLB](library/assets/fc3d-0b2467cdb8/v1/floating_salvage.glb) · [preview](library/assets/fc3d-0b2467cdb8/v1/previews/floating_salvage_thumb.png) |
| Turtle Cay | `fc3d-7e35f73ff8` v1 | blender | 10,340 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-7e35f73ff8/v1/turtle_cay.glb) · [preview](library/assets/fc3d-7e35f73ff8/v1/previews/turtle_cay_thumb.png) |
| Grand Treasure Chest (MeshCraft) | `fc3d-4d0ab4aea8` v1 | meshcraft → blender | 2,456 | 1 | lid_close, lid_open | blend, glb | passed | [GLB](library/assets/fc3d-4d0ab4aea8/v1/grand_treasure_chest_meshcraft.glb) · [preview](library/assets/fc3d-4d0ab4aea8/v1/previews/grand_treasure_chest_meshcraft_three_quarter.png) |
| Reef Crab (Blockbench) | `fc3d-46906d9596` v1 | blockbench → blender | 216 | 1 | — | bbmodel, blend, fbx, glb | passed | [GLB](library/assets/fc3d-46906d9596/v1/reef_crab_blockbench.glb) · [preview](library/assets/fc3d-46906d9596/v1/previews/reef_crab_blockbench_thumb.png) |
| Deckhand Pip | `fc3d-71fcc50dcd` v2 | mixamo → blender | 1,476 | 2 | Attack, Idle, Interact, Jump, MixamoLayout_Jump, MixamoLayout_Walk, Run, Walk | blend, fbx, glb | passed-with-warnings | [GLB](library/assets/fc3d-71fcc50dcd/v2/deckhand_pip.glb) · [preview](library/assets/fc3d-71fcc50dcd/v2/previews/deckhand_pip_thumb.png) |
| Salvage Raft (photogrammetry scan) | `fc3d-297ecf1de4` v1 | meshroom → blender | 1,141 | 2 | — | blend, fbx, glb | passed | [GLB](library/assets/fc3d-297ecf1de4/v1/salvage_raft_photogrammetry_scan.glb) · [preview](library/assets/fc3d-297ecf1de4/v1/previews/salvage_raft_photogrammetry_scan_thumb.png) |
| TIDEBREAKERS Turtle Cay Scene | `fc3d-232048523e` v1 | blender | 26,410 | 17 | Attack, float_bob, Idle, Interact, Jump, MixamoLayout_Jump, MixamoLayout_Walk, Run, Walk | blend, glb | passed-with-warnings | [GLB](library/assets/fc3d-232048523e/v1/tidebreakers_turtle_cay_scene.glb) · [preview](library/assets/fc3d-232048523e/v1/previews/tidebreakers_turtle_cay_scene_thumb.png) |

Notes on specific assets:

- **Deckhand Pip v2** is v1 plus two clips merged through the Mixamo import path. Those clips are **fixtures in Mixamo's download layout, exported from the character's own rig**, not files from mixamo.com.
- **"passed-with-warnings"** is the Khronos warning `NODE_SKINNED_MESH_NON_ROOT`. The skinned mesh sits under the asset's root node, which is harmless because that root has an identity transform.
- **The photogrammetry scan** was reconstructed by Meshroom 2023.3 from 36 **Cycles renders of the floating-salvage asset**, not from real camera photos. It used the CPU draft pipeline and solved all 36 cameras, so it is draft quality.
  - ForgeCraft's scan cleanup cropped it to the subject, dropped the floor, disconnected fragments and floating outliers, rescaled it to 2.4 m and rebaked it into PNG maps.
- **Grand Treasure Chest** was built by **MeshCraft's** chest template (TIDEBREAKERS palette, lid clips) and packaged by ForgeCraft without re-processing.

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

- `library/`: snapshot of the ForgeCraft library. `index.json`, `assets/<id>/v<N>/` (exports, textures, previews, `asset.json`) and `jobs/*.json` (routing, stages, timings, attempts). The deployed 3D Department UI is built from this folder.
- `handoffs/`: FilmCraft MP4, DesignCraft sheet, three.js import screenshot + report.
- `REPORT.json`: every check, asset and handoff from the acceptance run. Its `assets/<slug>_vN/` paths are the `library_export` handoff copies; they are not committed, because the same files are in `library/assets/`. `python3 forgecraft/cli.py export <id> <dir>` recreates them.

**Using an asset in TIDEBREAKERS:**

```ts
new GLTFLoader().load(url, (g) => scene.add(g.scene));
```

For the game's toon look, swap each `MeshStandardMaterial` for `MeshToonMaterial({ map: m.map, gradientMap: toonGradient() })`. To fit an upgrade, add it as a child of the boat's matching `socket_*` node.
