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

Builds are **reproducible**: the same brief gives byte-identical GLB content in any server process (only the brief stored in the scene, which names the `out_dir`, differs). FBX files embed a timestamp and random object IDs, so compare those by content.

## Jobs and the asset library

`run_pipeline`, `process_mesh`, `compose_scene`, `blockbench_import` and `mixamo_apply` each run as a **job** and add a **version** to the asset library. They return what they always did, plus `job` and `library` keys; a brief with `"library": false` skips the library.

- **Library**: the 3D Department's one shared library, `$GITCRAFT_3D_LIBRARY` (default `~/.gitcraft/3d-library`; an existing `~/.gitcraft/meshcraft-library` is used in place, and `GITCRAFT_MESHCRAFT_LIBRARY` is still honoured). ForgeCraft writes the same library and adds routing, licence, provenance and engine-check records to MeshCraft's versions. The code lives in `gitcraft3d/` (library, jobs, hardware probe, router), shared with ForgeCraft; the sandbox gives MeshCraft read-write access to the library. Each version keeps the `.blend`, exports, LODs, collision, bake maps, previews and report, with every file's SHA-256, the inputs' hashes (palette, references, source files), the brief, validation, clips, contract and job. A re-run whose exports match the previous version is marked `same_as`. Source files from Mixamo are hashed, not copied.
- **Tools**: `library_search` (text, template, tool, status), `library_get` (one version), `library_export` (copies a version into a root and re-verifies every hash: the handoff to a game repo).
- **Jobs**: `jobs_list`, `job_get` (every attempt: what changed, timing, error, pipeline steps), `job_retry` (re-run the original request as new attempts on the same record).
- **Automatic retries** only for failures a lighter setting can fix. For `run_pipeline`: (1) previews ≤ 320 px and a 512 px bake; (2) previews 256 px, one view, texture-bake profiles dropped. The job is then `done_with_fallback` and says what changed. A bad request (unknown template, missing file, path outside the roots) fails at once with the reason.
- **`route`** (advice only): which path fits a request on this machine: a template, Blockbench, a scene, `run_script`, or photogrammetry / image-to-3D (ForgeCraft runs those generators). It is the same decision ForgeCraft's router makes (`gitcraft3d/rules.json`). Alternatives that would not come from the photos or image say so.
- **Called by ForgeCraft**: `python server.py --call <tool> '<json>'|@args.json` runs one tool exactly as MCP `tools/call` does and prints `{"ok": …, "result"|"error": …}` as its last line. ForgeCraft uses it (inside its own sandbox) for every Blender step, passing `parent_job` so the MeshCraft job links back to the ForgeCraft job.

## Blockbench, Mixamo and the machine

| Tool | Needs Blender | What it does |
|---|---|---|
| `hardware_probe` | no | CPU, RAM, NVIDIA GPUs, free disk at the roots, sandbox and network state, and each capability (Blender, texture bake, Blockbench, Mixamo, engine check, photogrammetry, image-to-3D) with the reason when it is unavailable |
| `blockbench_build` | no | Writes an editable Blockbench project (`.bbmodel`, format 5.0, `free` model) from a cube template (`crate`, `chest`, `crab`, `lantern`, `boat`) with an embedded pixel texture. Colours come from the project's palette through `roles`. Fronts face south (+Z), the glTF front |
| `blockbench_inspect` | no | Format version, elements, textures (embedded or linked), animations and problems of any `.bbmodel` |
| `blockbench_import` | yes | `.bbmodel` → `out_dir/source/<asset_id>.blend`: cubes and mesh elements, element rotation, embedded textures (nearest-neighbour), and each face's texel colour baked into `Color` so the toon profile renders it like the game's own geometry. Pass `profiles` to export and validate at once. Groups/bones and Blockbench animations are reported, not converted |
| `mixamo_guide` | no | The supported Mixamo workflow, export settings, core bone names and licence terms |
| `mixamo_prepare_upload` | yes | A character (GLB/FBX/OBJ/.blend) → a mesh-only FBX with the rig removed, for Mixamo's auto-rigger |
| `mixamo_apply` | yes | Mixamo downloads (FBX, *Without Skin*) → clips on a Mixamo-skeleton character, matched by bone name (`mixamorig:`/`mixamorig1:` ignored). Refuses, with the reason, a clip from a non-Mixamo skeleton or a skeleton whose rest pose differs; rescales hip motion for a different-size character |

**Blockbench** has no headless mode, CLI or server API, so MeshCraft never runs the app: it reads and writes the project format, and people edit the files in Blockbench. **Mixamo** has no API and scripted use of the site is not a supported access method, so MeshCraft never contacts mixamo.com: a person uploads and downloads, and MeshCraft prepares and merges the files. See `docs/3d-licensing.md`.

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
| `boat` | vehicle | Coastal Sloop / dinghy: lofted hull, deck, cabin, mast, sails, rails; `socket_*` empties for every upgrade slot | — |
| `boat_upgrade` | ship component | The five TIDEBREAKERS upgrades (canvas mainsail, cargo crates, brass compass, wheel & ash rudder, copper-sheathed hull), each modelled at its socket origin | — |
| `salvage` | prop | Lashed crate, barrel, chest and buoy on driftwood | `float_bob` loop |
| `island` | environment | Noise heightfield island with palms, rocks, stilt hut, dock; `socket_dock`, `socket_spawn` | — |
| `lighthouse` | environment | Lighthouse on a rock base, emissive lamp | — |
| `prop` | prop | Barrel, crate, rock or palm | — |
| `deckhand` | character | Humanoid crew member, 22-bone **Mixamo-named** skeleton | `Idle`, `Walk`, `Run`, `Jump`, `Interact`, `Attack` (**rigged**) |
| `mesh_import` | import | Not a model: imports a GLB/glTF/FBX/OBJ/STL/PLY made elsewhere (scan, AI, download) and cleans it: scan crop, fragment/outlier removal, cleanup, decimation, grounding, rescale. Run it with `process_mesh` | kept from the source |

The seven templates from `boat` to `deckhand` came from ForgeCraft in the 3D Department consolidation; their builders live in `engine/procedural/` and use the same palette roles, vertex colours, export profiles and validation as the others.

Templates are Python modules in `engine/templates/` with `META` (params, roles, triangle budget), `default_roles(params)` and `build(ctx)`, using the modelling kit in `engine/kit.py`:
- primitives with bevels;
- palette-role materials;
- the vertex-colour bake;
- the palette atlas;
- keyframed clips stashed for glTF;
- armatures with rigid or gradient skinning;
- reference images.

A template returns a **contract** (node names, pivots, clips) that validation and the engine check enforce. `engine_check` with `all_clips: true` also plays every clip on its own (rest pose restored before each) and fails any clip that changes neither node transforms nor morph-target weights (a sail's `billow` counts as movement); without it the check behaves as before.

**Scenes:** `compose_scene` places library assets or files (`attach_to: "<item>:<socket_*>"` snaps one asset to another's socket), adds ocean, sky and sun, renders a hero shot and exports a scene GLB and `.blend`, validated like any asset.

**Not everything should be a template.** For one-off or hand-directed work, use `run_script`: write a Blender Python script in the workspace (globals: `bpy`, `kit`, `args`, `Palette`), run it against a `.blend`, then preview, validate and export as usual. That covers assisted modelling, where Claude iterates on geometry script by script.

## Export profiles (`profiles/*.json`)

| Profile | Format | Colour | Animation | For |
|---|---|---|---|---|
| `three-web-toon` | GLB | COLOR_0 vertex colours + PBR fallback materials | named clips | Three.js games that shade with vertex colours (13 portfolio games use Three.js; TIDEBREAKERS uses `MeshToonMaterial({vertexColors})`) |
| `three-web-atlas` | GLB | one material + hand-painted palette atlas (+ COLOR_0) | named clips | texture-based glTF engines |
| `godot-glb` | GLB | atlas | clips → AnimationPlayer | Godot 4 |
| `unity-fbx` | FBX (-Z fwd, Y up, unit scale applied) | embedded atlas | all actions baked | Unity / Unreal |
| `obj-static` | OBJ + MTL | atlas PNG | none | DCC interchange |
| `web-pbr` | GLB | baked maps in one shared UV layout: basecolor (sRGB), metallic-roughness, emissive when something glows; one PBR material; no COLOR_0 | named clips | glTF engines with standard PBR materials (three.js `MeshStandardMaterial`, Babylon.js, PlayCanvas, Godot, glTFast). Bakes at 1024 px (Cycles EMIT bakes, CPU) and retries at 512 px |
| `stl-print` | binary STL | none | none (rest pose) | 3D printing: Z up, millimetres. Kit-bashed parts overlap, so let the slicer union them |

Assets without palette roles (Blockbench projects saved by people, Mixamo characters) keep their own materials in the atlas profiles; the export result says so.

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
- glTF 2.0 structure with `COLOR_0` on every primitive (or, for `web-pbr`, a base colour texture on every primitive);
- contract nodes present;
- the **Khronos glTF-Validator**;
- **re-import round-trip**: size, base height and clips survive (STL: triangle count).

**Engine check.** The GLB is loaded with `three@0.170` GLTFLoader in headless Chromium, using the game's own toon material. A clip is played and screenshotted, and the contract is checked: hinge position, end rotation, nodes, vertex colours. With `material: "authored"` it checks base colour maps (`web-pbr`) or the file's own materials instead of `COLOR_0`.

## Limits

- Procedural and template modelling suits props, ship parts, modular kits and simple characters. Organic sculpting, retopology and hand-painted textures still need an artist in Blender. `run_script` and the `.blend` sources make that hand-off clean.
- The PyPI `bpy` build has no Draco or meshoptimizer, so compressed glTF is unavailable. Exports are uncompressed (small assets: 100–250 KB).
- Previews use Cycles on CPU (2–5 s per view at 640 px). There is no EEVEE without a GPU.
- Character rigs are rigid (one bone per part). Skinned organic deformation with weight painting is not automated.

## License

`meshcraft/` imports Blender's `bpy` module (GPL-2.0-or-later), and the Blender Foundation treats code built on its Python API as GPL. Treat everything under `meshcraft/` as **GPL-3.0-or-later**, and keep it a separate directory from GITCRAFT's other scripts. **Assets MeshCraft produces are not affected**: Blender's licence does not apply to its output. Dependencies: three.js (MIT), Khronos glTF-Validator (Apache-2.0), pygltflib (MIT), Pillow (MIT-CMU), numpy (BSD-3-Clause). Blockbench (GPL-3.0) is not bundled or run; only its file format is used. Mixamo terms: `docs/3d-licensing.md`.
