# GITCRAFT architecture

GITCRAFT is a creative production department for Claude Code: specialised apps run as headless MCP servers, and Claude Code acts as art director and pipeline manager, moving files between them.

```
                     ┌──────────── Claude Code session ────────────┐
                     │  creative brief → plan → tool calls → QC    │
                     └───────┬─────────────────────────────────────┘
                             │ MCP (stdio, JSON-RPC), one server per tool
             scripts/mcp.sh  │  (central launcher: policy, roots, state dirs)
                     ┌───────▼────────┐
                     │   guard.py     │  path checks · deny list · audit + handoff hashes
                     └───────┬────────┘
                     ┌───────▼────────┐
                     │  sandbox.py    │  Landlock: workspace roots + own state only, no network
                     └───────┬────────┘
   ┌───────────┬────────────┼────────────┬────────────┬────────────┬────────────┬────────────┐
 photocraft vectorcraft designcraft   pdfcraft    lightcraft   filmcraft   effectcraft   forgecraft ──► meshcraft
   raster     vector      layout        PDF         photo        video       motion     3D orchestrator  3D specialist (Blender)
                                                                                              └──── gitcraft3d/ ────┘
                                                                                         shared library · jobs · probe · router
```

## Components

| Path | Role |
|---|---|
| `scripts/tools.sh` | The tool list (also drives the CI build matrix), roots, sandbox policy, per-tool deny list |
| `scripts/install.sh` | Installs prebuilt binaries from the `bin` branch (source fallback), registers servers, writes `~/.gitcraft/status.json` |
| `scripts/setup-env.sh` | Pre-session installer for environment setup scripts; stable clone at `~/.gitcraft/repo` |
| `scripts/register.sh` | Registers every installed tool at user scope (`claude mcp add -s user`, or `~/.claude.json` directly when the CLI isn't on PATH) |
| `scripts/session-start.sh` | SessionStart hook for single-repo sessions: background install of anything missing, health line |
| `scripts/mcp.sh` | Starts one server behind guard + sandbox with its native roots and a private state folder |
| `scripts/guard.py` | MCP proxy: refusals with readable errors, deny list, `~/.gitcraft/logs/audit.jsonl` |
| `scripts/sandbox.py` | Landlock launcher (filesystem + network) |
| `scripts/doctor.sh` | Health report |
| `.github/workflows/build.yml` | Builds the ArtCraft CLIs weekly / on demand into the `bin` branch |
| `forgecraft/` | ForgeCraft, the 3D Department orchestrator: MCP server, job pipeline (route → generate → engine check → record → hand-off), the MeshCraft bridge, external generators (Meshroom, TripoSR, Hunyuan3D), UI. No Blender code. See `docs/3d-department.md` |
| `meshcraft/` | MeshCraft, the 3D modelling specialist: MCP server (`server.py`, also `--call` for ForgeCraft), engine (`engine/`: kit, templates, procedural builders, mesh import, bake, scene composition, Blockbench, Mixamo, preview, validation, export), export profiles, engine check (three.js r170 + Khronos) |
| `gitcraft3d/` | Shared by both 3D servers: the asset library, job store, hardware probe and router (`rules.json`) |
| `tests/` | MCP test client, the policy test, the MeshCraft and ForgeCraft tests, the TIDEBREAKERS 3D acceptance test |

## How tools hand off work

Tools never talk to each other directly. A handoff is a **file in an authorized root**: one tool exports (SVG, PNG, PSD, PDF, MP4, …), the next imports it. Claude Code chooses formats and paths. The audit log records each file's SHA-256 at both ends, so every handoff is traceable. Package-level metadata (what each deliverable is, which tools made it, its status) lives in the project's own manifest, e.g. TIDEBREAKERS `creative/MANIFEST.json`.

## 2D → 3D

MeshCraft consumes what the 2D tools produce:
- **palettes** (VectorCraft ASE/CSS/GPL/JSON exports) become its material roles;
- **reference images** (PNG/JPG from any tool) are attached to the `.blend` and shown on its contact sheet next to the renders;
- its previews are PNGs the 2D tools can lay out (DesignCraft) or composite (PhotoCraft);
- its manifest updates use the same `MANIFEST.json` the creative package uses.

ForgeCraft sits one level up as the orchestrator: it routes a request to a MeshCraft template, Blockbench, Mixamo, Meshroom, TripoSR or Hunyuan3D, has MeshCraft do every Blender step, checks the result in three.js, and records routing, licence and provenance in the shared library. `library_export` hands assets to the other tools. Both 3D servers write one library (`$GITCRAFT_3D_LIBRARY`) and one job store.

## Session lifecycle

1. **Before the session:** `setup-env.sh` (environment setup script) installs, registers and reports health.
2. **Session start:** Claude Code reads `~/.claude.json` and connects every registered server. In single-repo sessions the SessionStart hook also checks and repairs.
3. **Each server start:** `mcp.sh` resolves the roots, creates the tool's state folder, applies the sandbox and starts the guard.
4. **Failures:** a refused call returns a readable `GITCRAFT policy:` error; tool errors pass through unchanged; both land in the audit log. `doctor.sh` and `status.json` report install problems.

See `docs/security.md` for the permission model and `docs/install.md` for setup.
