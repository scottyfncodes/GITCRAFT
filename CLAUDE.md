# GITCRAFT

This repo gives Claude Code seven creative tools from the ArtCraft suite
(github.com/storytold), each running as a headless MCP server, plus `meshcraft`,
the 3D Department (Blender, Blockbench, Mixamo, Meshroom, TripoSR, Hunyuan3D). When this repo is
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
| `meshcraft`   | 3D Department: Blender pipeline + Blockbench, Mixamo, Meshroom, TripoSR, Hunyuan3D | 3D models from briefs/images/photos, rigged + animated characters, scenes, GLB/FBX/OBJ export, 3D asset library |

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
- meshcraft: call `hardware_probe` or `route` first. `generate` runs the whole
  pipeline and returns real files; `library_export` hands assets to other tools or a
  game repo. A `blocked` job means no tool here can honour the request: report its
  reason and alternatives, never substitute a 2D image. TripoSR/Hunyuan3D need a GPU
  or network to huggingface.co (blocked in default cloud sessions). Mixamo has no API:
  a person uploads/downloads at mixamo.com, MeshCraft prepares and merges the files.
  Details: `docs/3d-department.md`, licences: `docs/3d-licensing.md`.

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
  `scripts/mcp.sh` need updating to match if you add one. Non-ArtCraft tools
  (meshcraft) go in `GITCRAFT_EXTRA_TOOLS` and install via their own script.
- `tests/test_meshcraft.py` must pass after any change under `meshcraft/`.
- Never commit model weights, the bpy wheel or Meshroom: they install into
  `~/.gitcraft/meshcraft` (`scripts/install-3d.sh`).
- Don't commit binaries to `main`. The workflow owns the `bin` branch.
