# GITCRAFT

Seven open-source creative apps from [ArtCraft](https://github.com/storytold), wired into Claude Code as MCP tools:

PhotoCraft · VectorCraft · DesignCraft · PdfCraft · LightCraft · FilmCraft · EffectCraft · **MeshCraft** (3D, Blender)

## How it works

1. A GitHub Action builds each app's CLI (which includes its MCP server) and publishes them to the `bin` branch. It reruns weekly to pick up upstream changes, or on demand from the Actions tab.
2. Attach this repo to a Claude Code session. A SessionStart hook downloads the prebuilt binaries and registers all seven tools, so they're available in whatever repo the session is working on.
3. Ask Claude to use them: "make a poster in DesignCraft", "merge these PDFs", "cut this clip down to 30 seconds".

## 3D: MeshCraft

MeshCraft runs Blender 5.2 headless as an MCP server: creative brief + brand palette + 2D references → modelled, coloured, previewed, validated assets exported as GLB / FBX / OBJ, with a Three.js engine check. See [meshcraft/README.md](meshcraft/README.md).

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
```

Files are limited to `$GITCRAFT_ROOTS` (default `$GITCRAFT_ROOT`: `$HOME`, or the session workspace when it is outside `$HOME`), enforced by the kernel sandbox. Set them before starting a session to narrow or widen that.

If several repos are attached to a session, this repo's SessionStart hook doesn't run (the session starts in their parent folder). Run `scripts/install.sh` yourself, then `/mcp` to connect.

## Credits

All seven apps are by the ArtCraft team, MIT or Apache-2.0. This repo only builds and wires them up.
