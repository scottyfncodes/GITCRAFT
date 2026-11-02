# GITCRAFT control room (local web UI)

A visual front end for all eight GITCRAFT tools, built for phones first. It is an **extra interface**: Claude Code, the MCP servers, `scripts/mcp.sh` and the CLIs work exactly as before, and the UI adds no new engine.

```
scripts/ui.sh                    # serves http://127.0.0.1:8765/#token=… (prints the link; Ctrl-C stops it)
scripts/ui.sh --port 9000        # another port (0 = any free port)
scripts/ui.sh --snapshot DIR     # read-only snapshot with real data (for sharing a preview)
```

Open the printed link once. The page keeps the token for that tab and removes it from the address bar.

## What it does

| Page | What you can do |
|---|---|
| **Home** | Health at a glance: Landlock sandbox and network state, workspace roots, the audit-log counters, each tool's install/registration/version and how many MCP tools it exposes (**Discover all** connects to every server), and which 3D capabilities this machine has, with the reason for any that is missing |
| **Run · Pipeline** | A MeshCraft brief as a form: template and its parameters, palette and 2D references (picked from the workspace), output folder, export profiles, preview size, library on/off. Shows checks, exports, previews, the job and the library version when it finishes |
| **Run · Advice** | `route`, explained. **Recommended · available here** (green, with the tool steps), **What you asked for · not available here** (amber, with the reason), and **Alternative · not the same thing** (dashed, saying it is not derived from your photos or images) are visually distinct |
| **Run · Any tool** | Every tool on every server, with a form generated from its input schema. Results show images inline and the full JSON. Commands GITCRAFT policy blocks are marked and cannot be run |
| **Jobs** | Every MeshCraft job, filterable by status. A job shows each attempt (what was changed for a retry, timing, the error), the pipeline steps, a plain explanation of any fallback, a link to the library version, and **Retry** |
| **Library** | The versioned 3D library: search, check-status filter, thumbnails. An asset shows its versions (with *identical to vN*), previews, an interactive 3D viewer for its GLBs, the check results (problems first), every file with its SHA-256, the inputs it came from, and **Export and verify** into a workspace root |
| **Tools** | The eight servers and their discovered tool lists, searchable; tap a tool to run it |

## How it stays inside GITCRAFT's security model

- **Every action is an MCP call through `scripts/mcp.sh`.** The guard (path checks, deny list, audit log) and the Landlock sandbox (roots only, no network) apply to the UI exactly as they do to Claude Code. A path outside the roots or a blocked command is refused by the guard, and the UI shows the guard's message. MeshCraft browsing and advice use a second MeshCraft connection, so they stay responsive while a pipeline runs.
- **Reads that need no tool are read-only file reads**: job records, the library index and asset records, the audit counters, `status.json`. Folder browsing is limited to the workspace roots.
- **Local only.** It binds `127.0.0.1`. Each launch makes a random token. Every `/api` request must carry it, come from this origin (Origin is checked) and use `127.0.0.1`/`localhost` as Host (this blocks DNS rebinding). Posts must be `application/json` (no simple cross-site form posts) and at most 1 MB.
- **File previews** are served only from the workspace roots and the MeshCraft library, only for an allowlist of media types (PNG/JPEG/WebP/GIF/SVG/GLB/glTF/JSON/text/PDF/MP4; never HTML), after resolving symlinks, with a `sandbox` Content-Security-Policy so a hostile SVG cannot run script. They need a session cookie (`HttpOnly`, `SameSite=Strict`, path `/files`) that the page gets in exchange for the token.
- **The page itself** has a strict CSP: scripts only from the UI itself, no framing, no form submission, no third-party connections. It builds every element with the DOM API (no `innerHTML`), so tool output cannot inject markup.
- **No downloads, services or paid dependencies.** The server is Python standard library. The front end is plain HTML/CSS/JS with no build step. The 3D viewer uses the `three@0.170` that MeshCraft's engine check already installed. Logs: `~/.gitcraft/logs/ui-access.log` and `ui-tools.log`.
- **Licences unchanged.** The UI only displays what MeshCraft records (for example, Mixamo sources are hashed, never copied). The P3 photogrammetry and P5 AI-generation capabilities show as unavailable, with the reason.

## Read-only snapshot

`scripts/ui.sh --snapshot DIR` writes the same UI as one self-contained `index.html` plus `data/*.json` and preview images, with real data: tool lists, jobs, library records, hardware probe and sample advice. Every action is disabled and labelled. It is for showing the control room somewhere that cannot reach your machine, such as a phone. GLB files are left out because many static hosts refuse them; the 3D viewer is in the live control room.

## Using it from an iPhone

The control room listens on `127.0.0.1` only, so it is never on your network. To use it from an iPhone, reach that machine securely, for example with an SSH tunnel from a terminal app (`ssh -L 8765:127.0.0.1:8765 you@machine`), then open the printed link in Safari. Add it to the Home Screen for a full-screen app. Do not bind it to `0.0.0.0`.

## Tests

`tests/test_ui.py` starts the UI on a free port with a scratch workspace and library. It checks:
- the security gates;
- that the guard and audit log still apply to UI calls;
- discovery of all eight servers;
- MeshCraft pipelines, jobs (done, fallback, failed), library versions, verified export, a refused export outside the roots, and advice;
- the browser flow at iPhone size (`tests/ui_browser.js`, Playwright: home, library, asset with 3D viewer and export, jobs, advice, pipeline form, tools, dark mode, desktop, no horizontal scroll, no page errors);
- the snapshot.
