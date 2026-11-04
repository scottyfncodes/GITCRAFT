# Game Quality History

PLAYCRAFT keeps a permanent record of every game it assesses. Every `assess`, `pass`, `verify` and `full_pass` is
saved automatically and filed under the right game. Each run is compared with that game's pinned baseline, and the
history can then answer questions about one game or about the whole portfolio. It is part of the PLAYCRAFT
department (`studio/departments/playcraft/history.py`): there is no separate service, database server or dashboard
backend.

## Asking it

| Request | Tool |
|---|---|
| "Which games need attention next?" / "which improved, which declined?" | `playcraft_history` (no `game`): the portfolio |
| "How has TIDEBREAKERS changed since its first assessment?" | `playcraft_history {game: "scottyfncodes/tidebreakers"}` (id, `owner/repo`, title or repo path) |
| "Add the runs we already have" | `playcraft_history_import {paths: [...]}`: existing `playcraft.json` / `verify.json`, with their own timestamps |
| "It's deployed" / "main is at X" / "this run belongs to PR 7" | `playcraft_history_record {game, event: deployment \| main \| pr \| note, ...}` |
| "Save the history in git" | `playcraft_history_export {dest: <GITCRAFT>/history/playcraft}`, then commit |

Every PLAYCRAFT run's result has a `history` block (game id, run id, baseline, verdict against the baseline, new
findings). It also writes a `history.md` next to its report.

## What is recorded

Each run file is `games/<game id>/runs/<run id>.json`. It holds:

- **Run details:** kind, assessment time, recording time, who recorded it, and the commit. The commit is recorded at
  run time; for older cards it is taken from the card's baseline field or supplied by the caller, and labelled
  with its source.
- **Method fingerprint:** a hash of PLAYCRAFT's measuring and scoring code.
- **Scores:** genres, the overall score and all 10 category scores, plus two narrower views:
  - a **verified-only** score, recomputed from verified criteria alone;
  - a **measured** score (verified + observed).
- **Evidence:** counts per evidence level, every criterion's status, level and detail, and the findings.
- **Metrics:** response, FPS (with the renderer), time to play, errors, touch targets, text size, pause, and the
  start-prompt chain.
- **For verify runs:** the before/after comparison, regressions, the confirmation replay, guardrails and the
  changes made.

The full PLAYCRAFT card is kept byte for byte (`<run id>.card.json.gz`), and its SHA-256 is in the run.
`game.json` holds the identity (from the git `origin`, so every clone of a repo is the same game, including a
session's loopback git proxy), the paths seen and the **baseline run**. `events.jsonl` is an append-only log of
deployments, main heads, PRs and notes.

Runs are content-addressed and immutable: recording the same card twice is a no-op, and an existing file is never
rewritten. The baseline is pinned when a game's first run is recorded. An older run imported later is kept as
history, but it never replaces the baseline.

## Telling improvement from noise

| Situation | Classification |
|---|---|
| Two runs of the **same commit** (ignoring PLAYCRAFT's own `gitcraft-out/`) | everything that moved is **measurement**: the game did not change |
| A criterion flipped between runs of the same commit, even if the endpoints' commits differ | **measurement** (step attribution) |
| A criterion only measured in one run (`not tested`, added or removed) | **coverage** (e.g. FPS stopped being scored on software rendering) |
| Status changed between different commits, verified/observed on both sides | **improved** / **regressed** (verified or observed): the only class that counts as genuine |
| Status changed between different commits, from source only | **code change (unverified)**: reported, never credited as an improvement |

Each game gets a verdict: genuine improvement, genuine regression, mixed, measurement only (same commit),
code changed but not verified, no measured change (within noise), or score moved without a measured criterion
change (method or coverage).

The **noise band** is measured per game: the largest overall move between two runs of the same commit made with the
same PLAYCRAFT method. Until a game has such a pair, the band is a declared default of ±3. Fixed findings are
credited only when fixed by a change. A finding that "resolves" on an unchanged commit is shown as not credited.

On the page, a score change is coloured only when the verdict is real. Category moves without a measured criterion
change in that category are grey and labelled.

## Portfolio questions

`playcraft_history` answers each question from recorded runs only, naming the runs and evidence:

- **Improved most:** genuine verdicts, ranked by the number of criteria improved at verified/observed level.
- **Declined:** genuine regressions or mixed results.
- **Not assessed recently:** older than `stale_days` (14 by default), or main has moved past the last assessed commit.
- **Unresolved defects** and **recurring regressions:** the same criterion regressed twice or more.
- **Improvements with measurable results:** verify runs whose resolved findings were measured.
- **Needs attention next:** a ranking with its reasons. The reasons are open defects, regressions, staleness, a low-confidence or
  unplayed latest run, open measured issues, main moving past the last assessment, missing deployment evidence and no improvement pass yet.

Games are never ranked on raw scores across genres. Each game is compared with its own baseline under its own
genre profile and weights.

## Merged, deployed, live

| Level | Means | Needs |
|---|---|---|
| `main` event | the default branch head, as observed | `commit` + `evidence` (e.g. `git ls-remote origin refs/heads/main`) |
| `deploy-reported` | the hosting or CI reported success for that commit | `evidence` (e.g. the workflow run and its conclusion) |
| `live-verified` | PLAYCRAFT compared the live page with the local build of that commit and they match | `live_html` (fetched by the caller, saved in the workspace) and `build_dir` |

A deployment without evidence is refused. The live check runs inside the sandbox, which has no network. The caller
fetches the page; PLAYCRAFT compares its fingerprinted script and style references (Vite/webpack content hashes) with
the build's `index.html`. Identical file names without fingerprints are not enough, unless the whole page is identical.

## Where it lives, and why it survives

- **Store:** `$GITCRAFT_PLAYCRAFT_HISTORY`, default `~/.gitcraft/playcraft/history`. It sits beside the AssetCraft
  catalogue and outside `~/.gitcraft/runtime`, which `install-global.sh` replaces on every upgrade.
  `scripts/mcp.sh` gives studiocraft and forgecraft write access to it, exactly like the catalogue.
- **Archive:** `history/playcraft/` in this repo, in the same format. Cloud containers are ephemeral, so git is the
  durable copy. Every session imports the archive into the store automatically and idempotently (runs it already
  has are skipped; the archive's original baseline wins). Export with `playcraft_history_export` and commit the
  folder through a PR.
- **Games page:** `forgecraft/ui_server.py --publish` (the Vercel build) writes `games/` from the archive. It is a
  static page: it shows recorded runs and measures nothing.

## The page

The page is at `/games/` on the GITCRAFT site, linked from the 3D Department header. It has two views:

- **Portfolio:** the game that needs attention next and why; one card per game with its score trail (overall and
  verified-only), verdict stamp, change since baseline, deployment level and warnings; and the portfolio questions.
- **One game:** where the code is (baseline → last assessed → main → deployed); baseline vs latest with the verdict
  and the change classes; score progression against the measured noise band; category progression; every criterion
  change with its class and evidence levels; findings (open, fixed, not measured); improvement passes;
  regression history; and runs with provenance.

## Limitations

- History before this feature has no method fingerprint. Those runs are labelled `unrecorded`, and pairs involving
  them never count towards the noise band.
- The live check needs the caller to fetch the page. Hosts blocked by the environment's network policy (e.g.
  `github.io` here) can only be recorded as `deploy-reported` from CI evidence.
- Commits are only as good as the working tree. Runs on a dirty tree are never treated as the same commit
  (GITCRAFT's own `gitcraft-out/` is ignored).
- PR links are recorded when the caller passes `pr`. PLAYCRAFT does not query GitHub from inside the sandbox.
