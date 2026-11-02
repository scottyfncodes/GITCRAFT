# GITCRAFT

Seven open-source creative apps from [ArtCraft](https://github.com/storytold), wired into Claude Code as MCP tools:

PhotoCraft · VectorCraft · DesignCraft · PdfCraft · LightCraft · FilmCraft · EffectCraft

…plus a **3D Department** (`meshcraft`) that produces real 3D game assets: Blender, Blockbench, Mixamo, Meshroom/AliceVision, TripoSR and Hunyuan3D behind one pipeline. It routes each request, generates or imports a model, then cleans, optimises, UV-unwraps, bakes textures, rigs and animates it, renders previews, exports GLB/glTF/FBX/OBJ/STL/.blend, validates the result (including a three.js load test), and packages it in a versioned library. See [docs/3d-department.md](docs/3d-department.md) and [docs/3d-licensing.md](docs/3d-licensing.md).

## How it works

1. A GitHub Action builds each app's CLI (which includes its MCP server) and publishes them to the `bin` branch. It reruns weekly to pick up upstream changes, or on demand from the Actions tab.
2. Attach this repo to a Claude Code session. A SessionStart hook downloads the prebuilt binaries and registers all seven tools, so they're available in whatever repo the session is working on.
3. Ask Claude to use them: "make a poster in DesignCraft", "merge these PDFs", "cut this clip down to 30 seconds".

## Install before your session (recommended)

Use this as the cloud environment's setup script so the tools are ready in every session, whichever repos are attached:

```
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
```

## Security

Every tool runs in a Landlock kernel sandbox: it can only read and write your workspace roots and its own state folder, and has no network. A guard in front of each server gives readable refusals and keeps an audit log with file hashes of every handoff. See [docs/security.md](docs/security.md).

## 3D Department quick start

```
scripts/install-3d.sh [meshroom|ai|all]   # Blender 5.2 (bpy) core; optional photogrammetry / AI runtimes
python3 meshcraft/cli.py generate "stylized low-poly boat with a red hull"
python3 meshcraft/ui_server.py            # the department UI, live on http://127.0.0.1:8765
tests/test_meshcraft.py                   # integration tests for every 3D tool
tests/acceptance_tidebreakers.py out/     # the TIDEBREAKERS 3D asset package
```

The TIDEBREAKERS acceptance package (real GLBs, textures, previews, metadata, scene, handoffs) is in `acceptance/tidebreakers-3d/`.

## Manual commands

```
scripts/install.sh            # install anything missing
scripts/install.sh --update   # pull the latest builds
scripts/install.sh --source   # compile from source instead (slow, needs crates.io)
scripts/mcp.sh photocraft     # start one server by hand (sandboxed)
scripts/doctor.sh             # health report
tests/test_policy.py          # end-to-end security test
```

Files are limited to `$GITCRAFT_ROOTS` (default `$GITCRAFT_ROOT`: `$HOME`, or the session workspace when it is outside `$HOME`), enforced by the kernel sandbox. Set them before starting a session to narrow or widen that.

If several repos are attached to a session, this repo's SessionStart hook doesn't run (the session starts in their parent folder). Run `scripts/install.sh` yourself, then `/mcp` to connect.

## Credits

All seven apps are by the ArtCraft team, MIT or Apache-2.0. This repo only builds and wires them up. The 3D Department's tools keep their own licences (Blender GPL, Blockbench GPL, Meshroom MPL-2.0, TripoSR MIT, Hunyuan3D Tencent Community License with territory limits, Mixamo Adobe terms); see [docs/3d-licensing.md](docs/3d-licensing.md).
