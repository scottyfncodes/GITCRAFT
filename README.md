# GITCRAFT

Seven open-source creative apps from [ArtCraft](https://github.com/storytold), wired into Claude Code as MCP tools:

PhotoCraft · VectorCraft · DesignCraft · PdfCraft · LightCraft · FilmCraft · EffectCraft · **MeshCraft** (3D, Blender) · **ForgeCraft** (3D Department orchestrator)

## How it works

1. A GitHub Action builds each app's CLI (which includes its MCP server) and publishes them to the `bin` branch. It reruns weekly to pick up upstream changes, or on demand from the Actions tab.
2. One setup script installs the tools and makes them **global**: every Claude Code project can use them, without GITCRAFT being attached, cloned or opened there (see below).
3. Claude considers them by itself for creative work in any project (a global instruction and skill tell it to), or you ask directly: "make a poster in DesignCraft", "merge these PDFs", "cut this clip down to 30 seconds".

## 3D: MeshCraft

MeshCraft runs Blender 5.2 headless as an MCP server: creative brief + brand palette + 2D references → modelled, coloured, previewed, validated assets exported as GLB / FBX / OBJ, with a Three.js engine check. See [meshcraft/README.md](meshcraft/README.md).

## 3D Department: ForgeCraft

ForgeCraft orchestrates the 3D Department. It routes each request to the best available method (a MeshCraft template, Blockbench, Mixamo, Meshroom photogrammetry, TripoSR, Hunyuan3D), with fallbacks, and has **MeshCraft** do every Blender step: modelling or import, cleanup, materials and baked textures, rigging and animation, previews, export per engine profile and validation. ForgeCraft then checks the deliverable in three.js r170, records routing, licence and provenance, and hands it off. Both servers share one versioned asset library and job store (`gitcraft3d/`). It never substitutes a 2D image for a 3D model.

- Docs: [docs/3d-department.md](docs/3d-department.md) (architecture, ownership matrix, pipeline); [docs/3d-licensing.md](docs/3d-licensing.md) (dependency and licensing audit); [docs/3d-consolidation.md](docs/3d-consolidation.md) (consolidation report).
- The TIDEBREAKERS 3D package is in `acceptance/tidebreakers-3d/`.
- ForgeCraft uses MeshCraft's Blender. `scripts/install-3d.sh [meshroom|ai|all]` adds photogrammetry and the AI runtimes.

## Control room

`scripts/ui.sh` opens a local, phone-friendly web UI for every tool: health, discovery, MeshCraft pipelines, jobs with their retries, the versioned 3D library with fingerprints and verified exports, and routing advice. It listens on 127.0.0.1 only, needs its one-time link, and acts only through `scripts/mcp.sh`, so the sandbox and guard apply. See [docs/ui.md](docs/ui.md).

## Use GITCRAFT in every project (global install)

### Fresh cloud environment (recommended)

Paste this one line into the environment's **Setup script** (cloud environment menu in the session's title bar ▸ Edit ▸ Setup script):

```
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
```

Every new container in that environment runs it before Claude Code starts, so **every session, in any repo (or none), starts with all nine tools connected** and the GITCRAFT instructions loaded. Nothing has to be attached. It takes a few minutes on a new container (the tools are ~400 MB prebuilt; MeshCraft's Blender is another ~400 MB, skip it with `GITCRAFT_MESHCRAFT=0`).

### Workstation

Run the same line once in a terminal. `~/.claude.json` and `~/.claude/` persist, so every later session in every project inherits it; run it again to update. Requirements: Linux x86_64 (prebuilt binaries), Python 3 (3.11/3.13 for MeshCraft), Node/npm (optional, for the 3D engine check), Linux 5.13+ for the kernel sandbox.

### What the setup installs, and how Claude Code finds it

| Piece | Where | Purpose |
|---|---|---|
| GITCRAFT clone | `~/.gitcraft/repo` | Source the setup installs from (`GITCRAFT_REF=<branch>` for another branch, `GITCRAFT_REPO_URL` for a fork) |
| Tool binaries, Blender venv | `~/.gitcraft/bin`, `~/.gitcraft/meshcraft` | The nine tools |
| **Runtime** | `~/.gitcraft/runtime` | Copy of the launcher, guard, sandbox and tool code. The servers start from here, never from a checkout, so they work when no GITCRAFT checkout exists |
| **MCP registration** | `~/.claude.json` → `mcpServers` (user scope) | Claude Code connects user-scope servers in **every** project. Each entry runs `~/.gitcraft/runtime/scripts/mcp.sh <tool>` |
| **Global instructions** | a managed block in `~/.claude/CLAUDE.md` | Loaded in every project: consider GITCRAFT for creative work, pick tools that fit, hand files between them, integrate into the current project, validate, keep projects isolated. Your own text in that file is kept |
| **`gitcraft` skill** | `~/.claude/skills/gitcraft/` | The tool-selection guide Claude loads on demand |

Project configuration still wins: a project's `.mcp.json`, `.claude/settings.json` and `CLAUDE.md` work as before, and a project-scope server with the same name overrides the user-scope one. GITCRAFT adds nothing to your projects.

**Project isolation:** each tool's kernel sandbox is limited to the session's workspace (in cloud sessions, the project folder; in multi-repo sessions, their parent folder; on a workstation `$HOME` unless you set `GITCRAFT_ROOTS`), so it cannot write into GITCRAFT or other folders. GITCRAFT registers the tools with no environment variables of their own and the sandbox gives them no network, so they cannot send a project's files or secrets anywhere; the instructions also tell Claude never to pass one project's secrets or private paths into work for another. The global instructions tell Claude to land outputs in the current project's asset folders, never overwrite assets without a reason, and follow the project's art direction.

### Verify

```
~/.gitcraft/runtime/scripts/doctor.sh      # tools, registration (all from the runtime?), instructions, skill, sandbox
cd <any project> && claude mcp list         # nine *craft servers: Connected
tests/test_global.sh                        # full cross-repository acceptance test (fresh HOME + separate project)
```

In a session, `/mcp` lists the servers; asking Claude "which GITCRAFT tools and skills do you have?" should name the nine servers and the `gitcraft` skill.

### Troubleshooting

| Symptom | Fix |
|---|---|
| No `*craft` tools in a session | `~/.gitcraft/runtime/scripts/doctor.sh`. Not installed: run the setup line. Installed but the session started first: `/mcp` to reconnect, or a new session |
| Cloud: tools gone in a new session | The container is new; the setup script isn't set for that environment. Add the line above to its Setup script |
| `doctor` says registrations are not from the runtime | They point at an old checkout: `~/.gitcraft/runtime/scripts/install-global.sh` (or any checkout's `scripts/install-global.sh`) |
| One tool missing | `~/.gitcraft/repo/scripts/install.sh <tool>`, then `/mcp`. `cat ~/.gitcraft/logs/install.log` shows why it failed |
| `GITCRAFT policy:` refusal | The file is outside the workspace: copy it into the project rather than widening `GITCRAFT_ROOTS` |
| LightCraft says its library is open elsewhere | Another session holds the shared library; the launcher now gives this project its own (`~/.gitcraft/lightcraft-libraries/`). Set `GITCRAFT_LIGHTCRAFT_LIBRARY` to choose one |
| Don't want the global instructions | `GITCRAFT_GLOBAL_INSTRUCTIONS=0` when running the setup, and delete the GITCRAFT block from `~/.claude/CLAUDE.md` and `~/.claude/skills/gitcraft` |
| Setup script failed when the container was built | Its output is in `~/.gitcraft/logs/install.log`; fix the cause and edit the environment's Setup script. New sessions run the fixed script |

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
tests/test_global.sh          # global install used from a separate project
scripts/install-global.sh     # refresh the runtime, user-scope registration and global instructions
python3 forgecraft/ui_server.py   # the 3D Department UI, live on http://127.0.0.1:8765
```

Files are limited to `$GITCRAFT_ROOTS` (default `$GITCRAFT_ROOT`: `$HOME`, or the session workspace when it is outside `$HOME`), enforced by the kernel sandbox. Set them before starting a session to narrow or widen that.

When this repo is the session's only repo, its SessionStart hook also installs anything missing and refreshes the runtime, registration and instructions from this checkout. With several repos attached the hook doesn't run (the session starts in their parent folder); the global install above covers that case.

## Credits

All seven apps are by the ArtCraft team, MIT or Apache-2.0. This repo only builds and wires them up.
