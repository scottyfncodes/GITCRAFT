# TIDEBREAKERS 3D acceptance package

Produced by `tests/acceptance_tidebreakers.py` with GITCRAFT's consolidated 3D Department: **ForgeCraft orchestrates** (routing, engine check, licence and provenance records, hand-off) and **MeshCraft does every Blender step** as a child job, both writing one shared library. Every call went through the sandboxed MCP servers, as Claude Code drives them. Result: **110/110 checks passed** (2026-11-02T21:25:32Z → 2026-11-02T21:36:44Z).
Machine: 4 CPU threads, 15.7 GB RAM, no GPU.

**Engine target:** TIDEBREAKERS (Vite + TypeScript + three.js r170). GLB, metres, Y-up, forward/bow = +Z, matching `src/ship/shipModel.ts`. Every main GLB passed the Khronos glTF-Validator, a Blender re-import, MeshCraft's geometry checks and a three.js r170 `GLTFLoader` load in Chromium (the engine check; its screenshot is in each version's `previews/`).

## Assets (latest versions)

| Asset | ID | Made with | Triangles | Texture maps | Animations | Export profiles | Validation | Files |
|---|---|---|---|---|---|---|---|---|
| TIDEBREAKERS Coastal Sloop | `tidebreakers_coastal_sloop` v1 | meshcraft_template | 4,392 | 7 | — | godot-glb.glb, obj-static.obj, stl-print.stl, three-web-atlas.glb, three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/tidebreakers_coastal_sloop/v1/exports/tidebreakers_coastal_sloop.web-pbr.glb) · [preview](library/assets/tidebreakers_coastal_sloop/v1/previews/tidebreakers_coastal_sloop_three_quarter.png) |
| Upgrade: Canvas Mainsail | `upgrade_canvas_mainsail` v1 | meshcraft_template | 588 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed-with-warnings / engine passed | [GLB](library/assets/upgrade_canvas_mainsail/v1/exports/upgrade_canvas_mainsail.web-pbr.glb) · [preview](library/assets/upgrade_canvas_mainsail/v1/previews/upgrade_canvas_mainsail_three_quarter.png) |
| Upgrade: Lashed Cargo Crates | `upgrade_lashed_cargo_crates` v1 | meshcraft_template | 492 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/upgrade_lashed_cargo_crates/v1/exports/upgrade_lashed_cargo_crates.web-pbr.glb) · [preview](library/assets/upgrade_lashed_cargo_crates/v1/previews/upgrade_lashed_cargo_crates_three_quarter.png) |
| Upgrade: Brass Compass | `upgrade_brass_compass` v1 | meshcraft_template | 698 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/upgrade_brass_compass/v1/exports/upgrade_brass_compass.web-pbr.glb) · [preview](library/assets/upgrade_brass_compass/v1/previews/upgrade_brass_compass_three_quarter.png) |
| Upgrade: Ship's Wheel & Ash Rudder | `upgrade_ship_s_wheel_ash_rudder` v1 | meshcraft_template | 1,016 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/upgrade_ship_s_wheel_ash_rudder/v1/exports/upgrade_ship_s_wheel_ash_rudder.web-pbr.glb) · [preview](library/assets/upgrade_ship_s_wheel_ash_rudder/v1/previews/upgrade_ship_s_wheel_ash_rudder_three_quarter.png) |
| Upgrade: Copper-Banded Hull | `upgrade_copper_banded_hull` v1 | meshcraft_template | 1,912 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/upgrade_copper_banded_hull/v1/exports/upgrade_copper_banded_hull.web-pbr.glb) · [preview](library/assets/upgrade_copper_banded_hull/v1/previews/upgrade_copper_banded_hull_three_quarter.png) |
| Floating Salvage | `floating_salvage` v1 | meshcraft_template | 1,188 | 3 | float_bob | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/floating_salvage/v1/exports/floating_salvage.web-pbr.glb) · [preview](library/assets/floating_salvage/v1/previews/floating_salvage_three_quarter.png) |
| Turtle Cay | `turtle_cay` v1 | meshcraft_template | 10,732 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed-with-warnings / engine passed | [GLB](library/assets/turtle_cay/v1/exports/turtle_cay.web-pbr.glb) · [preview](library/assets/turtle_cay/v1/previews/turtle_cay_three_quarter.png) |
| Grand Treasure Chest | `grand_treasure_chest` v1 | meshcraft_template | 2,456 | 3 | lid_close, lid_open | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/grand_treasure_chest/v1/exports/grand_treasure_chest.web-pbr.glb) · [preview](library/assets/grand_treasure_chest/v1/previews/grand_treasure_chest_three_quarter.png) |
| Reef Crab (Blockbench) | `reef_crab_blockbench` v1 | blockbench | 216 | 3 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed / engine passed | [GLB](library/assets/reef_crab_blockbench/v1/exports/reef_crab_blockbench.web-pbr.glb) · [preview](library/assets/reef_crab_blockbench/v1/previews/reef_crab_blockbench_three_quarter.png) |
| Deckhand Pip | `deckhand_pip` v2 | mixamo | 1,488 | 3 | Walking, Sneak_Walk | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed-with-warnings / engine passed | [GLB](library/assets/deckhand_pip/v2/exports/deckhand_pip.web-pbr.glb) · [preview](library/assets/deckhand_pip/v2/previews/deckhand_pip_three_quarter.png) |
| Salvage Raft (photogrammetry scan) | `salvage_raft_photogrammetry_scan` v1 | meshroom | 1,163 | 2 | — | three-web-toon.glb, unity-fbx.fbx, web-pbr.glb | passed-with-warnings / engine passed | [GLB](library/assets/salvage_raft_photogrammetry_scan/v1/exports/salvage_raft_photogrammetry_scan.web-pbr.glb) · [preview](library/assets/salvage_raft_photogrammetry_scan/v1/previews/salvage_raft_photogrammetry_scan_three_quarter.png) |
| TIDEBREAKERS Turtle Cay Scene | `tidebreakers_turtle_cay_scene` v1 | meshcraft_scene | 26,742 | 0 | Attack, Idle, Interact, Jump, Run, Sneak_Walk, Walk, Walking, float_bob | scene.glb | passed-with-warnings / engine passed | [GLB](library/assets/tidebreakers_turtle_cay_scene/v1/exports/tidebreakers_turtle_cay_scene.scene.glb) · [preview](library/assets/tidebreakers_turtle_cay_scene/v1/previews/tidebreakers_turtle_cay_scene_three_quarter.png) |

Each row's job column is in `asset.json` → `provenance`: the ForgeCraft job that ordered it and the MeshCraft job that built it. `library/jobs/` has both records.

Notes on specific assets:

- **Deckhand Pip v2** is v1 plus two clips merged through the Mixamo path (ForgeCraft `mixamo_apply` → MeshCraft). Those clips are **fixtures in Mixamo's download layout written by `tests/fixtures/mixamo_fixture.py`**, not files from mixamo.com.
- **"passed-with-warnings"** means MeshCraft's validation passed with warnings (e.g. a rigged mesh under the asset's root node); there were no failures.
- **The photogrammetry scan** was reconstructed by Meshroom 2023.3 (ForgeCraft backend, CPU draft pipeline) from 36 **Cycles renders of a salvage asset**, not real camera photos, so it is draft quality. MeshCraft's `process_mesh` cropped it to the subject, dropped the floor, fragments and floating outliers, rescaled it to 2.4 m, decimated it and baked PBR maps.
- **Grand Treasure Chest** is MeshCraft's chest template (TIDEBREAKERS palette, lid clips), ordered by ForgeCraft.
- **Reef Crab** was routed to Blockbench: MeshCraft wrote the `.bbmodel` (included) and imported it into Blender.

## Required deliverables

| Requirement | Delivered |
|---|---|
| Recognisable 3D player boat | TIDEBREAKERS Coastal Sloop (MeshCraft `boat` template): lofted hull ported from `shipModel.ts`, deck, cabin, mast, boom, striped mainsail, jib, rails, tiller, lantern, flag; `socket_*` attachment nodes; all seven export profiles |
| Modular upgrade components | Canvas Mainsail, Lashed Cargo Crates, Brass Compass, Ship's Wheel & Ash Rudder, Copper-Banded Hull: the five TIDEBREAKERS upgrade slots, each modelled at its socket origin (`boat_upgrade`) |
| Floating salvage object | Lashed crate, barrel, chest and buoy on driftwood, with a looping `float_bob` animation |
| Island / environmental structure | Turtle Cay: heightfield island with palms, rocks, stilt hut, dock; `socket_dock` / `socket_spawn` |
| Animated character or creature | Deckhand Pip: 22-bone Mixamo-named rig; Idle, Walk, Run, Jump, Interact, Attack (+2 merged clips in v2). Reef Crab via Blockbench |
| Composed 3D scene | TIDEBREAKERS Turtle Cay Scene (MeshCraft `compose_scene`): the four hull/deck upgrades attached to the sloop's sockets (the canvas mainsail replaces the base sail in game), the deckhand on the dock socket, the crab on the spawn socket, salvage, ocean, sun, sky, hero render; scene GLB + `.blend` |
| Real geometry, GLB, textures, previews, metadata | Every asset: baked PNG base-colour + ORM maps (`web-pbr`), vertex-colour toon GLB, FBX, `.blend`, Cycles previews, and `asset.json` (files with SHA-256, routing, licence, provenance, validation, engine check) |
| Downstream handoffs | `library_export` into the workspace (hash-verified), then **FilmCraft** cut the preview renders into `handoffs/tidebreakers_3d_review_reel.mp4`, and **DesignCraft** laid out `handoffs/tidebreakers_3d_asset_sheet.png` (+ `.designcraft`) |
| Imported into a real 3D scene | (1) Blender scene composition; (2) three.js r170 loads the scene GLB (boat, upgrades, island, salvage, deckhand, crab) in `GLTFLoader`: `handoffs/threejs_r170_scene.png` / `.json` |

## Layout

- `library/`: snapshot of the shared 3D library: `index.json`, `assets/<id>/v<N>/` (exports, textures, previews, `source/*.blend`, `asset.json`), `jobs/*.json` (ForgeCraft jobs and their MeshCraft child jobs) and `probe.json`. The deployed 3D Department UI is built from this folder.
- `handoffs/`: FilmCraft MP4, DesignCraft sheet, three.js scene screenshot + report.
- `REPORT.json`: every check, asset and handoff from the run. Its `assets/<id>_vN/` export copies are not committed (the same files are in `library/assets/`); `python3 forgecraft/cli.py export <id> <dir>` recreates them.

**Using an asset in TIDEBREAKERS:**

```ts
new GLTFLoader().load(url, (g) => scene.add(g.scene));
```

The `three-web-toon` GLB carries vertex colours for the game's toon look; the `web-pbr` GLB carries baked maps. To fit an upgrade, add it as a child of the boat's matching `socket_*` node.
