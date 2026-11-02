# GITCRAFT

Seven open-source creative apps from [ArtCraft](https://github.com/storytold), wired into Claude Code as MCP tools:

PhotoCraft · VectorCraft · DesignCraft · PdfCraft · LightCraft · FilmCraft · EffectCraft

## How it works

1. A GitHub Action builds each app's CLI (which includes its MCP server) and publishes them to the `bin` branch. It reruns weekly to pick up upstream changes, or on demand from the Actions tab.
2. Attach this repo to a Claude Code session. A SessionStart hook downloads the prebuilt binaries and registers all seven tools, so they're available in whatever repo the session is working on.
3. Ask Claude to use them: "make a poster in DesignCraft", "merge these PDFs", "cut this clip down to 30 seconds".

## Manual commands

```
scripts/install.sh            # install anything missing
scripts/install.sh --update   # pull the latest builds
scripts/install.sh --source   # compile from source instead (slow, needs crates.io)
scripts/mcp.sh photocraft     # start one server by hand
```

Files are fenced to `$GITCRAFT_ROOT` (default `$HOME`). Set it before starting a session to narrow that.

## Credits

All seven apps are by the ArtCraft team, MIT or Apache-2.0. This repo only builds and wires them up.
