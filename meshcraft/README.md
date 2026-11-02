# MeshCraft: GITCRAFT's 3D tool

MeshCraft is GITCRAFT's 3D production tool: **Blender 5.2 LTS running headless as an MCP server**. It turns a structured creative brief, and the 2D direction GITCRAFT already produces, into game-ready 3D assets: modelled, coloured from the brand palette, previewed, validated, exported per engine profile, and recorded in the project's manifest.

It is started by `scripts/mcp.sh meshcraft` like every other GITCRAFT tool, so it runs behind the same guard and **Landlock sandbox**: it can only read and write the workspace roots, has no network, and anything it runs, including `run_script`, is contained.

## Install

`scripts/install.sh` (or `scripts/setup-env.sh`) installs it automatically:

| Dependency | How it's installed | Notes |
|---|---|---|
| Blender 5.2.3 LTS | `bpy` wheel from PyPI into `~/.gitcraft/meshcraft/venv` (~400 MB) | needs Python 3.13 (or 3.11 with an older bpy); no GPU needed, renders with Cycles on CPU |
| pygltflib, numpy, Pillow | same venv (`meshcraft/requirements.txt`, pinned) | glTF structure checks, contact sheets |
| three@0.170.0, gltf-validator | `npm ci` in `meshcraft/engine_check` | optional: engine check + Khronos validator |
| Chromium + Playwright | pre-installed in Claude Code cloud containers | optional: engine check |

Skip it with `GITCRAFT_MESHCRAFT=0`. `scripts/doctor.sh` shows its state.

## The workflow

```
creative brief ──► build_asset ──► render_preview ──► validate_asset ──► export_asset ──► engine_check ──► update_manifest
 (JSON)            template +        Cycles + navy        geometry, budget,    per profile:      three@0.170 +        creative package
 + 2D refs         palette roles     outlines, poses,     origin, scale,       GLB / FBX / OBJ   game toon material,  MANIFEST.json
 + palette         → .blend          contact sheet with   colours, clips,      + atlas PNG       clips, contract
                                     the 2D references    skinning, Khronos
```

`run_pipeline` does all of it for one brief and writes `<out_dir>/<asset_id>.meshcraft.json` (every step, timing, check, file and SHA-256).

## Brief

```json
{
  "asset_id": "tb_chest_small",            // file stem; letters, digits, _ -
  "template": "chest",                     // see list_templates
  "params": {"tier": "small"},             // template parameters
  "palette": ".../tidebreakers-palette.json", // GITCRAFT palette: .json .css .gpl .ase
  "roles": {"band": "Deep Tide"},          // optional: override a colour role (palette name or #hex)
  "material_prefix": "TB",                 // materials are named TB_Wood, TB_Band, ...
  "references": [".../cargo.png"],         // 2D references: attached as image empties + on the contact sheet
  "out_dir": ".../creative/3d/chest",
  "profiles": ["three-web-toon", "unity-fbx"],
  "preview": {"size": 640, "views": ["three_quarter","front","side","top"], "poses": [{"clip": "lid_open", "at": "end"}]},
  "manifest": ".../creative/MANIFEST.json" // optional: record the deliverables
}
```

Output layout: `source/<id>.blend` (editable), `exports/<id>.<profile>.<ext>` (+ atlas PNG / MTL sidecars), `previews/*.png` + `<id>_sheet.png`, `<id>.meshcraft.json`.

## Templates

| id | Category | What it makes | Animation |
|---|---|---|---|
| `chest` | prop | Treasure chest in 3 tiers; drop-in for TIDEBREAKERS `chestMesh()` (same hinge, same −1.9 rad lid) | `lid_open`, `lid_close` (object) |
| `lantern` | ship component | Hanging lantern, emissive glass and flame, light anchor | `swing` loop (object) |
| `sun_figurehead` | ship component | The Grinning Sun emblem as a carved bow figurehead | — |
| `flag` | ship component | Swallowtail flag on a pole; designs: tidebreaker, harbor, wren | `wave` loop (**skeletal**, 4-bone chain) |
| `sail` | ship component | Square sail + yard; patterns plain, stripe, sunset, shells | `fill`, `luff` (**morph target** `billow`) |
| `crab` | character | Biscuit the teacup crab | `idle`, `wave`, `snap` (**rigged**, 8 bones) |

Templates are Python modules in `engine/templates/` with `META` (params, roles, triangle budget), `default_roles(params)` and `build(ctx)`, using the modelling kit in `engine/kit.py`:
- primitives with bevels;
- palette-role materials;
- the vertex-colour bake;
- the palette atlas;
- keyframed clips stashed for glTF;
- armatures with rigid or gradient skinning;
- reference images.

A template returns a **contract** (node names, pivots, clips) that validation and the engine check enforce.

**Not everything should be a template.** For one-off or hand-directed work, use `run_script`: write a Blender Python script in the workspace (globals: `bpy`, `kit`, `args`, `Palette`), run it against a `.blend`, then preview, validate and export as usual. That covers assisted modelling, where Claude iterates on geometry script by script.

## Export profiles (`profiles/*.json`)

| Profile | Format | Colour | Animation | For |
|---|---|---|---|---|
| `three-web-toon` | GLB | COLOR_0 vertex colours + PBR fallback materials | named clips | Three.js games that shade with vertex colours (13 portfolio games use Three.js; TIDEBREAKERS uses `MeshToonMaterial({vertexColors})`) |
| `three-web-atlas` | GLB | one material + hand-painted palette atlas (+ COLOR_0) | named clips | texture-based glTF engines |
| `godot-glb` | GLB | atlas | clips → AnimationPlayer | Godot 4 |
| `unity-fbx` | FBX (-Z fwd, Y up, unit scale applied) | embedded atlas | all actions baked | Unity / Unreal |
| `obj-static` | OBJ + MTL | atlas PNG | none | DCC interchange |

Profiles are data: add a JSON file to target another engine. Exports **never overwrite game assets**: they go only to the brief's `out_dir`, and integrating them into a game is a separate, reviewed change.

## Validation

**Scene checks.** Each check reports pass, warn, fail or info, and is recorded in the report:
- triangle budget (template and profile), and degenerate faces;
- non-manifold edges (info only);
- applied scale and default names;
- origin on the ground (or at the hang point);
- footprint centring and dimensions against expectations;
- materials assigned, `Color` attribute present, textures resolvable;
- expected clips present;
- skinning: no unweighted vertices and at most 4 influences.

**Export checks.**
- glTF 2.0 structure with `COLOR_0` on every primitive;
- contract nodes present;
- the **Khronos glTF-Validator**;
- **re-import round-trip**: size, base height and clips survive.

**Engine check.** The GLB is loaded with `three@0.170` GLTFLoader in headless Chromium, using the game's own toon material. A clip is played and screenshotted, and the contract is checked: hinge position, end rotation, nodes, vertex colours.

## Limits

- Procedural and template modelling suits props, ship parts, modular kits and simple characters. Organic sculpting, retopology and hand-painted textures still need an artist in Blender. `run_script` and the `.blend` sources make that hand-off clean.
- The PyPI `bpy` build has no Draco or meshoptimizer, so compressed glTF is unavailable. Exports are uncompressed (small assets: 100–250 KB).
- Previews use Cycles on CPU (2–5 s per view at 640 px). There is no EEVEE without a GPU.
- Character rigs are rigid (one bone per part). Skinned organic deformation with weight painting is not automated.

## License

`meshcraft/` imports Blender's `bpy` module (GPL-2.0-or-later), and the Blender Foundation treats code built on its Python API as GPL. Treat everything under `meshcraft/` as **GPL-3.0-or-later**, and keep it a separate directory from GITCRAFT's other scripts. **Assets MeshCraft produces are not affected**: Blender's licence does not apply to its output. Dependencies: three.js (MIT), Khronos glTF-Validator (Apache-2.0), pygltflib (MIT), Pillow (MIT-CMU), numpy (BSD-3-Clause).
