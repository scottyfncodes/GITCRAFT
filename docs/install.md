# Installing GITCRAFT

## Recommended: install before the session starts

Put this in the cloud environment's **setup script** (environment settings ▸ Setup script), or run it once on a workstation:

```bash
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
```

It clones GITCRAFT to `~/.gitcraft/repo`, installs every tool, registers them at user scope from that stable path, and prints `doctor.sh --brief`. Because this happens before Claude Code starts, the tools connect in the first turn of every session, **whichever repos are attached**.

## Other ways

| Situation | What happens | What to do |
|---|---|---|
| GITCRAFT is the session's only repo | Its SessionStart hook installs anything missing in the background and registers the tools | Run `/mcp` once the build finishes (or start a new session) |
| Several repos attached | The session starts in their parent folder, so GITCRAFT's hook **does not run** | Use the setup script above, or run `GITCRAFT/scripts/install.sh` then `/mcp` |
| Tools installed mid-session | Servers registered after start-up don't connect until reconnect | `/mcp` (reconnect) or a new session |

## Commands

```
scripts/install.sh            install anything missing (prebuilt from the `bin` branch, source as fallback)
scripts/install.sh --update   refresh everything
scripts/doctor.sh             what's installed, registered, sandboxed and failing
scripts/mcp.sh <tool>         start one server by hand (behind the guard and sandbox)
tests/test_policy.py          end-to-end security check of every installed tool
```

## Requirements

- Linux x86_64 for the prebuilt ArtCraft binaries (source builds need Rust 1.95+ and crates.io).
- Python 3 (standard library only) for the guard, sandbox and doctor.
- Linux 5.13+ for the kernel sandbox (6.7+ for network denial).
- `~/.gitcraft/status.json` records the last install result per tool; `~/.gitcraft/logs/install.log` has the details.
