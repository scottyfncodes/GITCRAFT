# Installing GITCRAFT

## Recommended: install before the session starts

Put this in the cloud environment's **setup script** (environment settings ▸ Setup script), or run it once on a workstation:

```bash
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
```

It clones GITCRAFT to `~/.gitcraft/repo`, installs every tool, copies the launcher and tool code to `~/.gitcraft/runtime`, registers all ten servers at user scope from that runtime, installs the GITCRAFT block in `~/.claude/CLAUDE.md` and the `gitcraft` skill (`scripts/install-global.sh`), installs a user-level SessionStart hook in `~/.claude/settings.json` that finishes anything setup deferred (`GITCRAFT_MESHCRAFT=later`) or didn't finish, in the background, in any project (`GITCRAFT_GLOBAL_HOOK=0` skips it), and prints `doctor.sh --brief`. Because this happens before Claude Code starts, the tools connect in the first turn of every session, **whichever repos are attached, including none**. See the README's "Use GITCRAFT in every project" for what each piece does, verification and troubleshooting; `tests/test_global.sh` proves it from a separate project in a fresh HOME.

### Heavy optional runtimes: keep the setup script inside its time limit

A cloud setup script that runs past its time limit is stopped mid-step, and everything after that step never runs.
One fresh container was stopped about 17 minutes in, during the ACE-Step install. Put quick, important steps in the
script and queue the slow optional ones for the session with `scripts/install-later.sh`:

```bash
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | GITCRAFT_MESHCRAFT=later bash
~/.gitcraft/runtime/scripts/install-3d.sh meshroom || true                    # ~3 min: early, so it always lands
~/.gitcraft/runtime/scripts/install-studio.sh mocap || true                   # ~1 min
~/.gitcraft/runtime/scripts/install-later.sh install-3d.sh ai weights         # TripoSR (~8 min): queued
~/.gitcraft/runtime/scripts/install-later.sh install-studio.sh music          # ACE-Step (very large): queued
```

The SessionStart hook runs the queue (`scripts/run-later.sh`) in the background inside the session, one job at a time
and after any Blender build, so nothing is left running in a setup script that is about to be stopped. A job leaves
the queue when it succeeds; a failed one is retried by the next sessions (at most 3 attempts). The log is
`~/.gitcraft/logs/later.log`; `scripts/install-later.sh --list` shows the queue.

MeshCraft's engine check packages (three@0.170, gltf-validator) are installed into
`~/.gitcraft/meshcraft/engine_check`, not into the runtime: each runtime update is a fresh copy of a checkout, and
packages installed inside it were lost on the next update. A developer checkout uses its own `npm ci` in
`meshcraft/engine_check` when it has one, or that installed copy (`meshcraft/engine/nodemods.py`).

## Other ways

| Situation | What happens | What to do |
|---|---|---|
| GITCRAFT is the session's only repo | Its SessionStart hook installs anything missing in the background and refreshes the runtime, registration and global instructions from this checkout | Run `/mcp` once the build finishes (or start a new session) |
| Several repos attached | The session starts in their parent folder, so GITCRAFT's hook **does not run** | Use the setup script above, or run `GITCRAFT/scripts/install.sh` then `/mcp` |
| Tools installed mid-session | Servers registered after start-up don't connect until reconnect | `/mcp` (reconnect) or a new session |

## Commands

```
scripts/install.sh            install anything missing (prebuilt from the `bin` branch, each checked against
                              scripts/bin.sha256 before it is unpacked; --source builds the pinned upstream commit)
scripts/install.sh --update   refresh everything
~/.gitcraft/gitcraft-update   review, then apply, a GITCRAFT update from main: --yes, --to <commit>, --rollback
                              (a copy of scripts/update.sh outside the clone, so it survives any rollback)
scripts/doctor.sh             what's installed, registered (from the runtime?), sandboxed and failing
scripts/install-global.sh     refresh ~/.gitcraft/runtime, user-scope registration, ~/.claude/CLAUDE.md block and skill
scripts/mcp.sh <tool>         start one server by hand (behind the guard and sandbox)
tests/test_policy.py          end-to-end security check of every installed tool
```

## Updating and rolling back

| To | Run |
|---|---|
| see what an update would change | `~/.gitcraft/gitcraft-update` (changes nothing) |
| apply the latest main | `~/.gitcraft/gitcraft-update --yes` |
| go back to the version before the last update | `~/.gitcraft/gitcraft-update --rollback --yes` |
| go to any commit on main (older or newer) | `~/.gitcraft/gitcraft-update --to <commit> --yes` |

Every applied update is logged in `~/.gitcraft/logs/update.log`. Running servers keep their version; new sessions (or
`/mcp`) use the new one. Rolling back to a GITCRAFT from before reviewed updates (before PR #92) brings back that
version's automatic pull-and-run at session start: set `GITCRAFT_AUTO_UPDATE=0` in the environment to stay on it, and
come forward again with `~/.gitcraft/gitcraft-update --to <commit> --yes`.

## Releases of the prebuilt tools

The seven ArtCraft CLIs are compiled from the upstream commits pinned in `scripts/tools.sh` (`gitcraft_upstream_sha`)
and installed only when their SHA-256 is pinned in `scripts/bin.sha256`. Both files change only by pull request.

1. **Bump (optional).** Change a pin in `scripts/tools.sh` after reviewing the upstream diff; open a pull request. CI
   builds it and runs the release gate; nothing is published.
2. **Build on main.** After merging (or with "Run workflow" on *Build ArtCraft CLIs*), the main build passes the gate
   and uploads `bin.sha256`: the candidate's checksums, naming its run. Its summary shows them.
3. **Pin it.** On a branch, replace `scripts/bin.sha256` with that file, open a pull request, review, merge (within 7
   days: the run's artifacts expire).
4. **Published.** The merge starts *Publish ArtCraft CLIs* (`publish-bin.yml`): it checks that the run is a successful
   main build, downloads its gated files, checks every checksum against the pins, and only then replaces `bin`.

A modified or unpinned binary is never installed: `install.sh` refuses it before unpacking, keeps the binary already
installed, and records `integrity: mismatch` in `~/.gitcraft/status.json`. Rolling back a release is the same pull
request with the previous `scripts/bin.sha256` (its run must still have its artifacts; otherwise rebuild that commit).

## Protecting main and bin

Two rulesets, ready to import (Settings > Rules > Rulesets > New ruleset > Import a ruleset): `docs/rulesets/main.json`
and `docs/rulesets/bin.json`. Nothing pushes `main` directly, so its ruleset never blocks publishing. `bin` is pushed by
`publish-bin.yml` only; its ruleset blocks every update except a **deploy key**, which the workflow uses when the
`BIN_DEPLOY_KEY` secret exists (without it, it falls back to the workflow token, which the ruleset would block). Do the
steps in this order so a release is never stranded:

1. **Key.** On your computer: `ssh-keygen -t ed25519 -N "" -C gitcraft-bin-publish -f gitcraft-bin`.
2. **Deploy key.** Settings > Deploy keys > Add: paste `gitcraft-bin.pub`, tick **Allow write access**.
3. **Environment.** Settings > Environments > New environment `release`; Deployment branches and tags: **Selected
   branches: `main`**. Add the secret `BIN_DEPLOY_KEY` = the contents of `gitcraft-bin` (the private key). Delete the key
   files from your computer afterwards; a lost key is replaced by adding a new one.
4. **Rulesets.** Import `main.json` and `bin.json` (both Active).
5. **Check.** Actions > *Publish ArtCraft CLIs* > Run workflow (on main). With `bin` already holding the pinned binaries
   it changes nothing and reports "nothing to publish"; the next real release pushes with the deploy key.

What they enforce: `main` changes only through a pull request whose **Tests** check is green, with no force-push or
deletion (the review count is 0 because one person cannot approve their own pull request; an agent working with your
account can still merge a green pull request, see docs/security.md). `bin` cannot be created, updated, force-pushed or
deleted by anyone but the deploy key, which only `main`'s publish job can use. `api-catalog` (the API Discovery data) is
left unprotected: it is data, and `/apis/` treats it as untrusted.

## Requirements

- Linux x86_64 for the prebuilt ArtCraft binaries (source builds need Rust 1.95+ and crates.io).
- Python 3 (standard library only) for the guard, sandbox and doctor.
- Linux 5.13+ for the kernel sandbox (6.7+ for network denial).
- `~/.gitcraft/status.json` records the last install result per tool; `~/.gitcraft/logs/install.log` has the details.
