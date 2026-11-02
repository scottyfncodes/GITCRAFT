# GITCRAFT

This repo gives Claude Code seven creative tools from the ArtCraft suite
(github.com/storytold) plus the two servers of its 3D Department: ForgeCraft
(the orchestrator: routes across MeshCraft templates, Blockbench, Mixamo,
Meshroom, TripoSR and Hunyuan3D, then engine-checks, records and hands off) and
MeshCraft (the specialist: headless Blender for every modelling, cleanup, bake,
rig, export and validation step), each running as a headless MCP server. When this repo is
attached to a session, a SessionStart hook installs them into `~/.gitcraft/bin`
and registers them at user scope, so they work no matter which repo you're
working in.

## The tools

| MCP server    | What it is                                  | Use it for |
|---------------|---------------------------------------------|------------|
| `photocraft`  | Raster image editor (Photoshop-style), reads/writes PSD | Editing images, layers, masks, adjustments, text on images, exporting PNG/JPG/PSD |
| `vectorcraft` | Vector illustration (Illustrator-style)     | Logos, icons, SVG work, vector art |
| `designcraft` | Page layout and desktop publishing          | Flyers, posters, multi-page layouts, print-ready PDF/X |
| `pdfcraft`    | PDF workbench (repo name: printcraft)       | Merge, split, reorder, inspect, secure, and render PDFs |
| `lightcraft`  | Photo library and raw developer (Lightroom-style) | Batch photo grading, raw development, exports |
| `filmcraft`   | Non-linear video editor                     | Cutting, trimming, color, audio, exporting video |
| `effectcraft` | Motion graphics and compositing (After Effects-style) | Animated titles, keyframes, effects, render queue |
| `meshcraft`   | 3D production: Blender 5.2 headless (`meshcraft/`) | Game-ready 3D assets from a brief: model, palette materials, previews, validation, GLB/FBX/OBJ/STL export (toon or baked PBR), Three.js engine check, Blockbench and Mixamo hand-offs, the shared versioned asset library (`$GITCRAFT_3D_LIBRARY`, default `~/.gitcraft/3d-library`) and job records. The 3D Department's specialist: does every Blender step |
| `forgecraft`  | 3D Department orchestrator (`forgecraft/`)  | Any 3D request: routes to MeshCraft templates, Blockbench, Mixamo, Meshroom, TripoSR or Hunyuan3D, has MeshCraft do the Blender work, engine-checks, records licence/provenance, hands off; same library and jobs as MeshCraft |

## How to use them

- Every app exposes its full command registry (hundreds of commands) through
  MCP. Start by listing or describing commands instead of guessing ids.
- They run headless: there's no window, so check results by exporting
  (PNG/PDF/MP4) and looking at the file.
- Every tool runs inside a kernel sandbox (Landlock) started by `scripts/mcp.sh`:
  it can read and write only the folders in `$GITCRAFT_ROOTS` (default
  `$GITCRAFT_ROOT`: `$HOME`, or the session workspace when that is outside
  `$HOME`, as in cloud sessions where repos live in `/home/user`), plus its own
  state folder, and it has no network. Keep inputs and outputs under the roots.
  A refused call says `GITCRAFT policy: …`; copy the file into the workspace
  rather than widening the roots. Details: `docs/security.md`.
- Every call is logged with the hashes of the files it touched in
  `~/.gitcraft/logs/audit.jsonl`. `scripts/doctor.sh` summarises health.
- lightcraft keeps a persistent library at `~/.gitcraft/lightcraft-library`.
- lightcraft and pdfcraft run in compact mode: a short list of helper tools,
  with every other command reachable through their list/run command tools.
- These projects are young. If a command fails, say so plainly and try another
  route rather than faking a result.

## 3D work (MeshCraft)

- Start with `meshcraft_status` and `list_templates`. `run_pipeline` takes a
  brief (template, params, palette from the project's brand package, 2D
  references, out_dir, export profiles, manifest) and produces the .blend,
  previews, validation report and exports. See `meshcraft/README.md`.
- Use the project's own palette file and 2D references as the source of truth;
  never redesign a game to fit what a template can make. Extend a template or
  use `run_script` (custom Blender Python in the workspace) instead.
- Always look at the contact sheet and run `engine_check` on GLBs before
  calling an asset game-ready. Never write exports into a game's source or
  public folders without being asked.

## 3D Department (ForgeCraft)

- Call `hardware_probe` or `route` first. `generate` runs the whole pipeline
  and returns real files; `library_export` hands assets to other tools or a game
  repo. ForgeCraft orchestrates and MeshCraft does every Blender step (as a
  child job of the ForgeCraft job); both write one library and job store
  (`gitcraft3d/`, `$GITCRAFT_3D_LIBRARY`). Ownership matrix: `docs/3d-department.md`.
- A `blocked` job means no tool here can honour the request: report its reason
  and alternatives, and never substitute a 2D image. TripoSR and Hunyuan3D need
  a GPU or network access to huggingface.co (blocked in default cloud sessions).
- Mixamo has no API: a person uploads/downloads at mixamo.com; MeshCraft
  prepares and merges the files (ForgeCraft's `mixamo_*` tools delegate to it).
- Details: `docs/3d-department.md`; licences: `docs/3d-licensing.md`.
- Never add Blender code to `forgecraft/`: it belongs in `meshcraft/engine/`.
  Shared library/jobs/probe/routing code belongs in `gitcraft3d/`.

## If a tool won't connect

0. `scripts/doctor.sh` shows what's missing, unregistered or failing.
1. `cat ~/.gitcraft/logs/install.log` to see whether the install is still
   running or failed.
2. `scripts/install.sh` to install anything missing, then `/mcp` to reconnect.
3. In a session with several repos attached, the session starts in their
   parent folder, so this repo's SessionStart hook never runs and nothing is
   installed. Run `scripts/install.sh` from this repo, then `/mcp` (or start a
   new session). To avoid this entirely, use `scripts/setup-env.sh` as the
   environment's setup script (`docs/install.md`).
4. If the `bin` branch doesn't exist yet, the "Build ArtCraft CLIs" GitHub
   Action hasn't finished. Run it from the Actions tab.

## Working on this repo

- `tests/test_policy.py` must pass after any change to the launcher, guard or
  sandbox.
- Tool list lives in `scripts/tools.sh`; the workflow matrix and
  `scripts/mcp.sh` need updating to match if you add one.
- `tests/test_forgecraft.py` must pass after any change under `forgecraft/` or `gitcraft3d/`
  (and `tests/test_meshcraft.py` after any change under `meshcraft/`).
- Never commit model weights or Meshroom: they install into
  `~/.gitcraft/forgecraft` (`scripts/install-3d.sh`).
- Don't commit binaries to `main`. The workflow owns the `bin` branch.
