# GITCRAFT

Seven open-source creative apps from [ArtCraft](https://github.com/storytold), wired into Claude Code as MCP tools:

PhotoCraft · VectorCraft · DesignCraft · PdfCraft · LightCraft · FilmCraft · EffectCraft · **MeshCraft** (3D, Blender) · **ForgeCraft** (3D Department orchestrator)

## How it works

1. A GitHub Action builds each app's CLI (which includes its MCP server) and publishes them to the `bin` branch. It reruns weekly to pick up upstream changes, or on demand from the Actions tab.
2. Attach this repo to a Claude Code session. A SessionStart hook downloads the prebuilt binaries and registers all seven tools, so they're available in whatever repo the session is working on.
3. Ask Claude to use them: "make a poster in DesignCraft", "merge these PDFs", "cut this clip down to 30 seconds".

## 3D: MeshCraft

MeshCraft runs Blender 5.2 headless as an MCP server: creative brief + brand palette + 2D references → modelled, coloured, previewed, validated assets exported as GLB / FBX / OBJ, with a Three.js engine check. See [meshcraft/README.md](meshcraft/README.md).

## 3D Department: ForgeCraft

ForgeCraft orchestrates the 3D Department. It routes each request to the best available method (a MeshCraft template, Blockbench, Mixamo, Meshroom photogrammetry, TripoSR, Hunyuan3D), with fallbacks, and has **MeshCraft** do every Blender step: modelling or import, cleanup, materials and baked textures, rigging and animation, previews, export per engine profile and validation. ForgeCraft then checks the deliverable in three.js r170, records routing, licence and provenance, and hands it off. Both servers share one versioned asset library and job store (`gitcraft3d/`). It never substitutes a 2D image for a 3D model.

- Docs: [docs/3d-department.md](docs/3d-department.md) (architecture, ownership matrix, pipeline); [docs/3d-licensing.md](docs/3d-licensing.md) (dependency and licensing audit); [docs/3d-consolidation.md](docs/3d-consolidation.md) (consolidation report).
- The TIDEBREAKERS 3D package is in `acceptance/tidebreakers-3d/`.
- ForgeCraft uses MeshCraft's Blender. `scripts/install-3d.sh [meshroom|ai|all]` adds photogrammetry and the AI runtimes.

## Control room

`scripts/ui.sh` opens a local, phone-friendly web UI for every tool: health, discovery, MeshCraft pipelines, jobs with their retries, the versioned 3D library with fingerprints and verified exports, and routing advice. It listens on 127.0.0.1 only, needs its one-time link, and acts only through `scripts/mcp.sh`, so the sandbox and guard apply. See [docs/ui.md](docs/ui.md).

## Install before your session (recommended)

Use this as the cloud environment's setup script so the tools are ready in every session, whichever repos are attached:

```
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
```

## Security

Every tool runs in a Landlock kernel sandbox: it can only read and write your workspace roots and its own state folder, and has no network. A guard in front of each server gives readable refusals and keeps an audit log with file hashes of every handoff. See [docs/security.md](docs/security.md).

## Manual commands

```
scripts/install.sh            # install anything missing
scripts/install.sh --update   # pull the latest builds
scripts/install.sh --source   # compile from source instead (slow, needs crates.io)
scripts/mcp.sh photocraft     # start one server by hand (sandboxed)
scripts/doctor.sh             # health report
tests/test_policy.py          # end-to-end security test
tests/test_meshcraft.py       # MeshCraft pipeline + sandbox test
tests/test_forgecraft.py      # ForgeCraft: routing, delegation to MeshCraft, jobs, library, refusals
scripts/ui.sh                     # the GITCRAFT control room (all tools, incl. ForgeCraft) on 127.0.0.1
```

Files are limited to `$GITCRAFT_ROOTS` (default `$GITCRAFT_ROOT`: `$HOME`, or the session workspace when it is outside `$HOME`), enforced by the kernel sandbox. Set them before starting a session to narrow or widen that.

If several repos are attached to a session, this repo's SessionStart hook doesn't run (the session starts in their parent folder). Run `scripts/install.sh` yourself, then `/mcp` to connect.

## Credits

All seven apps are by the ArtCraft team, MIT or Apache-2.0. This repo only builds and wires them up.
