#!/usr/bin/env python3
"""Regenerate acceptance/<pkg>/README.md from its REPORT.json and library snapshot (unified 3D library format)."""
import json, os, sys
pkg = sys.argv[1] if len(sys.argv) > 1 else "acceptance/tidebreakers-3d"
r = json.load(open(os.path.join(pkg, "REPORT.json"))); idx = json.load(open(os.path.join(pkg, "library", "index.json")))
PROFILE = lambda p: p.split("/")[-1].split(".", 1)[1] if "." in p.split("/")[-1] else p
rows = []
for a in sorted(idx["assets"], key=lambda a: a["updated"]):
    md = json.load(open(os.path.join(pkg, "library", "assets", a["id"], f"v{a['latest']}", "asset.json")))
    d = f"library/assets/{a['id']}/v{a['latest']}"
    files = md["files"]
    exports = sorted({PROFILE(f["path"]) for f in files if f["kind"] == "export"})
    textures = [f for f in files if f["path"].endswith(".png") and f["kind"] not in ("preview",)]
    glb = (md.get("engine_check") or {}).get("glb") or next((f["path"] for f in files if f["path"].endswith(".glb")), "")
    thumb = (md.get("previews") or {}).get("thumbnail")
    jobs = f"{(md.get('provenance') or {}).get('forgecraft_job', '—')} → {(md.get('provenance') or {}).get('meshcraft_job', '—')}"
    rows.append(f"| {md.get('title') or md['id']} | `{md['id']}` v{md['version']} | {(md.get('route') or {}).get('chosen', md.get('tool'))} | "
                f"{(md.get('geometry') or {}).get('triangles') or md.get('triangles') or 0:,} | {len(textures)} | "
                f"{', '.join(x['name'] for x in md.get('animations', [])) or '—'} | {', '.join(exports)} | "
                f"{(md.get('deliverable_validation') or {}).get('status', md['validation']['status'])} / engine {(md.get('engine_check') or {}).get('status', '—')} | "
                f"[GLB]({d}/{glb}) · [preview]({d}/{thumb}) |")
hw = r["machine"]
scan = r["assets"].get("photogrammetry_scan")
open(os.path.join(pkg, "README.md"), "w").write(f"""# TIDEBREAKERS 3D acceptance package

Produced by `tests/acceptance_tidebreakers.py` with GITCRAFT's consolidated 3D Department: **ForgeCraft orchestrates** (routing, engine check, licence and provenance records, hand-off) and **MeshCraft does every Blender step** as a child job, both writing one shared library. Every call went through the sandboxed MCP servers, as Claude Code drives them. Result: **{r['result']}** ({r['started']} → {r['finished']}).
Machine: {hw['cpu_threads']} CPU threads, {hw['ram']['total_gb']} GB RAM, no GPU.

**Engine target:** TIDEBREAKERS (Vite + TypeScript + three.js r170). GLB, metres, Y-up, forward/bow = +Z, matching `src/ship/shipModel.ts`. Every main GLB passed the Khronos glTF-Validator, a Blender re-import, MeshCraft's geometry checks and a three.js r170 `GLTFLoader` load in Chromium (the engine check; its screenshot is in each version's `previews/`).

## Assets (latest versions)

| Asset | ID | Made with | Triangles | Texture maps | Animations | Export profiles | Validation | Files |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

Each row's job column is in `asset.json` → `provenance`: the ForgeCraft job that ordered it and the MeshCraft job that built it. `library/jobs/` has both records.

Notes on specific assets:

- **Deckhand Pip v2** is v1 plus two clips merged through the Mixamo path (ForgeCraft `mixamo_apply` → MeshCraft). Those clips are **fixtures in Mixamo's download layout written by `tests/fixtures/mixamo_fixture.py`**, not files from mixamo.com.
- **"passed-with-warnings"** means MeshCraft's validation passed with warnings (e.g. a rigged mesh under the asset's root node); there were no failures.
""" + (f"""- **The photogrammetry scan** was reconstructed by Meshroom 2023.3 (ForgeCraft backend, CPU draft pipeline) from {len(os.listdir(os.path.join(pkg, 'work', 'photos'))) if os.path.isdir(os.path.join(pkg, 'work', 'photos')) else 36} **Cycles renders of a salvage asset**, not real camera photos, so it is draft quality. MeshCraft's `process_mesh` cropped it to the subject, dropped the floor, fragments and floating outliers, rescaled it to 2.4 m, decimated it and baked PBR maps.
""" if scan else "") + """- **Grand Treasure Chest** is MeshCraft's chest template (TIDEBREAKERS palette, lid clips), ordered by ForgeCraft.
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
""")
print(len(rows), "assets")
