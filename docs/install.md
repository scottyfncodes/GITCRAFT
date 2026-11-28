# Installing GITCRAFT

## Recommended: install before the session starts

Put this in the cloud environment's **setup script** (environment settings ▸ Setup script), or run it once on a workstation:

```bash
curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash
```

It is the whole setup script: nothing else belongs after it. It clones GITCRAFT to `~/.gitcraft/repo`, installs the seven ArtCraft tools and the Studio core runtime, copies the launcher and tool code to `~/.gitcraft/runtime`, registers all ten servers at user scope from that runtime, installs the GITCRAFT block in `~/.claude/CLAUDE.md` and the skills (`scripts/install-global.sh`), installs a user-level SessionStart hook in `~/.claude/settings.json` (`GITCRAFT_GLOBAL_HOOK=0` skips it), and prints `doctor.sh --brief`. Because this happens before Claude Code starts, the tools connect in the first turn of every session, **whichever repos are attached, including none**. See the README's "Use GITCRAFT in every project" for what each piece does, verification and troubleshooting; `tests/test_global.sh` proves it from a separate project in a fresh HOME.

### Setup always finishes fast

A cloud setup script that runs past its time limit is stopped mid-step (exit code -1), and everything after that step
never runs. Setup is therefore kept small, and it stays small whatever else a setup script asks for:

- **No 3D in setup.** `scripts/install.sh` (what `setup-env.sh` runs) installs no 3D component: no Blender (MeshCraft,
  ForgeCraft), Meshroom, TripoSR or Hunyuan3D, and it runs no 3D capability probe or report. The two 3D servers are
  registered and wait.
- **3D on demand.** A session whose work needs 3D runs `~/.gitcraft/runtime/scripts/install-3d.sh` itself (Blender,
  ~400 MB, a few minutes); `install-3d.sh meshroom` and `install-3d.sh ai weights` add photogrammetry and the AI
  runtimes only when a task needs them. The servers announce their tools when the install finishes. The global
  instructions and the `meshcraft_status` / `forgecraft_status` tools tell Claude the command.
- **A size guard.** During setup nothing over `GITCRAFT_SETUP_MAX_MB` (100) is downloaded. A step over the limit prints
  one line, `gitcraft: setup skipped <what> (~N MB, over the 100 MB setup limit): <how a session gets it>`, records it
  in `~/.gitcraft/logs/setup-skipped.log`, and exits 0. Direct downloads also carry curl's `--max-filesize`, so the
  limit holds on the real size, not only the declared one.
- **What "during setup" means.** `GITCRAFT_SETUP=1`, which `setup-env.sh` exports, and the time between `setup-env.sh`
  and the first session: `~/.gitcraft/setup-phase`, removed by the SessionStart hook. So a setup script that still has
  lines such as `install-3d.sh meshroom` or `install-studio.sh music` after the setup line gets one skip line for each
  instead of a timeout. The marker counts for an hour and never inside a Claude Code session or at a terminal.
  `GITCRAFT_SETUP=0 <command>` turns the guard off for that command.
- **The capability summary** is one line (`gitcraft-3d: ready: … | not installed or unavailable: …`), printed by
  `install-3d.sh` when it changes, never during setup. `doctor.sh` (full, not `--brief`) has the table.

| Component | Size | During setup | In a session |
|---|---|---|---|
| Seven ArtCraft tools | 17–40 MB each (one 204 MB fetch, ~8 s) | installed | |
| Studio core (numpy, Pillow, three, Phaser, glTF-Validator) | ~60 MB | installed | |
| Studio voice model | ~130 MB | skipped | the session hook, in the background |
| Blender (MeshCraft + ForgeCraft) | ~400 MB | skipped | `install-3d.sh` |
| Mocap (MediaPipe) | ~440 MB | skipped | `install-studio.sh mocap` |
| Meshroom | ~1.2 GB | skipped | `install-3d.sh meshroom` |
| TripoSR / Hunyuan3D runtimes, weights | ~5 GB, ~1.9 GB | skipped | `install-3d.sh ai weights` |
| ACE-Step music | ~10 GB | skipped | `install-studio.sh music` |

`python3 tests/test_setup_guard.py` checks all of this offline; `--timed` adds a clean run of the real setup (fresh
HOME, cold caches), which must finish in under a minute: about 30 seconds measured (28–33 s over three runs).

`scripts/install-later.sh install-3d.sh ai weights` still queues a large install for the SessionStart hook, which runs
it in the background inside the session (`scripts/run-later.sh`: one job at a time, at most 3 attempts, log in
`~/.gitcraft/logs/later.log`). Prefer installing on demand: a queued job runs in every new container whether the
session needs it or not.

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

## Pinning a cloud environment to a reviewed commit

The usual setup line runs whatever `main` holds when a container starts. Two things decide what runs, and both have to
be pinned to content someone reviewed:

| What runs at container start | Mutable (today) | Pinned |
|---|---|---|
| the bootstrap, `setup-env.sh` | downloaded from `.../GITCRAFT/main/...` | downloaded from `.../GITCRAFT/<commit>/...` and checked against its SHA-256 before it runs |
| the GITCRAFT it installs | the newest `main` | `GITCRAFT_REF=<the same commit>`: exactly that commit |

`scripts/setup-pin.sh <commit> [GITCRAFT_*=value ...]` prints the line for a commit, after checking that the commit is on
`main` and new enough to support pins (it changes nothing):

```
curl -fsSL -o /tmp/gitcraft-setup-env.sh https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/<commit>/scripts/setup-env.sh \
  && echo "<sha256 of that setup-env.sh>  /tmp/gitcraft-setup-env.sh" | sha256sum --check --quiet - \
  && GITCRAFT_REF=<commit> bash /tmp/gitcraft-setup-env.sh
```

It is the whole setup script, in place of the `curl ... | bash` line: nothing else belongs after it (large runtimes are installed on demand, in the session that needs them).

With a full 40-character commit, `setup-env.sh`:
- fetches `main`'s commit graph and refuses the commit unless it is on `main` (only reviewed, merged commits install),
- checks it out detached, verifies `HEAD` is exactly that commit, and removes any file that is not part of it,
- on any failure installs nothing and exits 1 (the session still starts, without the GITCRAFT tools). An abbreviated SHA
  is refused rather than guessed. Branches and tags (`GITCRAFT_REF=main`, a tag) install as before.

**Upgrading** a pinned environment is a reviewed change to the pin: run `scripts/setup-pin.sh <new main commit>` and replace
the line (new containers then install it). Within one container, `~/.gitcraft/gitcraft-update` still shows and applies a
newer `main`, but the next container goes back to the pin. **Rolling back** is the same edit with the earlier commit
(it must still be on `main`, which every merged commit is). Nothing updates by itself in either case.

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
