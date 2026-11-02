#!/usr/bin/env python3
"""Regenerate acceptance/<pkg>/README.md from its REPORT.json and library snapshot."""
import json, os, sys
pkg = sys.argv[1] if len(sys.argv) > 1 else "acceptance/tidebreakers-3d"
r = json.load(open(os.path.join(pkg, "REPORT.json"))); idx = json.load(open(os.path.join(pkg, "library", "index.json")))
rows = []
for a in sorted(idx["assets"], key=lambda a: a["updated"]):
    md = json.load(open(os.path.join(pkg, "library", "assets", a["id"], f"v{a['latest']}", "asset.json")))
    d = f"library/assets/{a['id']}/v{a['latest']}"
    rows.append(f"| {md['name']} | `{a['id']}` v{md['version']} | {md['source_tool']} | {md['geometry']['triangles']:,} | "
                f"{len(md['textures'])} | {', '.join(x['name'] for x in md['animations']) or '—'} | {', '.join(sorted(md['files']))} | "
                f"{md['validation']['status']} | [GLB]({d}/{md['files']['glb']['path']}) · [preview]({d}/{md['previews']['thumbnail']}) |")
hw = r["machine"]
open(os.path.join(pkg, "README.md"), "w").write(f"""# TIDEBREAKERS 3D acceptance package

Produced by `tests/acceptance_tidebreakers.py` with GITCRAFT's 3D Department (ForgeCraft, with MeshCraft as one of its backends). Every call went through the sandboxed MCP server, as Claude Code drives it. Result: **{r['result']}** ({r['started']} → {r['finished']}).
Machine: {hw['cpu_threads']} CPU threads, {hw['ram']['total_gb']} GB RAM, no GPU.

**Engine target:** TIDEBREAKERS (Vite + TypeScript + three.js r170). GLB, metres, Y-up, forward/bow = +Z, matching `src/ship/shipModel.ts`. Every GLB passed the Khronos glTF-Validator with 0 errors and loaded in three.js r170's GLTFLoader in Chromium.

## Assets (latest versions)

| Asset | ID | Made with | Triangles | Texture maps | Animations | Formats | Validation | Files |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + """

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
""")
print(len(rows), "assets")
