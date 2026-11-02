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
   ┌───────────┬────────────┼────────────┬────────────┬────────────┬────────────┐
 photocraft vectorcraft designcraft   pdfcraft    lightcraft   filmcraft   effectcraft
   raster     vector      layout        PDF         photo        video       motion
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
| `tests/` | MCP test client and the end-to-end policy test |

## How tools hand off work

Tools never talk to each other directly. A handoff is a **file in an authorized root**: one tool exports (SVG, PNG, PSD, PDF, MP4, …), the next imports it. Claude Code chooses formats and paths. The audit log records each file's SHA-256 at both ends, so every handoff is traceable. Package-level metadata (what each deliverable is, which tools made it, its status) lives in the project's own manifest, e.g. TIDEBREAKERS `creative/MANIFEST.json`.

## Session lifecycle

1. **Before the session:** `setup-env.sh` (environment setup script) installs, registers and reports health.
2. **Session start:** Claude Code reads `~/.claude.json` and connects every registered server. In single-repo sessions the SessionStart hook also checks and repairs.
3. **Each server start:** `mcp.sh` resolves the roots, creates the tool's state folder, applies the sandbox and starts the guard.
4. **Failures:** a refused call returns a readable `GITCRAFT policy:` error; tool errors pass through unchanged; both land in the audit log. `doctor.sh` and `status.json` report install problems.

See `docs/security.md` for the permission model and `docs/install.md` for setup.
