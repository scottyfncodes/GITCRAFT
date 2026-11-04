# PLAYCRAFT — game design and gameplay quality

PLAYCRAFT is the GITCRAFT department that makes games better to play. It reads a game repository, plays the
built game in a real browser on desktop and phone, scores how it plays across ten categories with the evidence
behind every number, ranks the improvements that matter most for *this* game's genre, and, after the changes are
made, plays it again to prove they worked and broke nothing.

It is a Studio department (`studio/departments/playcraft/`), so it uses the same contract, launcher, sandbox,
global install and discovery as the other nine: no separate installation, no separate framework.

## Invoking it

From any game repository (GITCRAFT does not need to be attached; the tools are user-scope):

| Say | What happens |
|---|---|
| **Run PLAYCRAFT on this game.** | The `playcraft` skill: build the game, `playcraft_pass`, look at what the probe saw, implement the plan on a branch, `playcraft_verify`, report |
| **Run the full GITCRAFT + PLAYCRAFT pass.** | The same with `playcraft_full_pass`: TestCraft engineering checks and the PLAYCRAFT pass in one run, one deduplicated plan |

The tools (studiocraft MCP server; also ForgeCraft `department_run {department: "playcraft", action, params}` and
`studio/cli.py run playcraft <action> '<json>'`):

| Tool | Phase | What it does |
|---|---|---|
| `playcraft_discover` | 1 Discover | Intent (README/CLAUDE.md/docs), engine and physics, build (bundler, output folder, whether it is built), controls (keys in the source, touch, gamepad), exposed game objects, ~70 systems with `file:line` evidence, mobile intent, genres |
| `playcraft_play` | 2 Play | Plays the build in Chromium (desktop 1280×720 + iPhone 13 by default): presses the start button, probes every control, a seeded mixed-input session, a clean frame-timing window, pause; screenshots and a contact sheet |
| `playcraft_assess` | 3 Diagnose | Scorecard: 10 categories, evidence level per criterion, confidence, genre-specific criteria, ranked findings (defects vs design), discipline reports. Takes recorded `judgements`, verified `evidence` files and `loop_answers` |
| `playcraft_pass` | 1-4 | discover + play + assess + a staged plan (defects → quick high-impact wins → deeper design work); saves the baseline (`playcraft.json`, with the git HEAD) |
| (you) | 5 Implement | In the game repo, on a branch, following the plan and the project's conventions |
| `playcraft_verify` | 6-7 Verify, Report | Replays with the baseline's probe, compares scores and measured metrics, lists resolved/new issues and regressions, checks guardrails on the git diff, writes `pass_report.md` (before/after) |
| `playcraft_full_pass` | all | TestCraft smoke (desktop/phone/tablet) + asset integrity + the PLAYCRAFT pass, one plan with one owner per item |
| `playcraft_genres` | — | The genre intelligence as Markdown/JSON |

Typical session in a game repo:

```text
npm ci && npm run build                                   # the game's own toolchain (needs the registry; not sandboxed)
playcraft_pass   {project: ".", target: "./dist"}         # → gitcraft-out/playcraft/pass/playcraft_report.md, play_contact_sheet.png
# look at the contact sheet: did the probe reach gameplay? if not, add start_steps: [{text: "Play"}]
playcraft_assess {project: ".", play_report: ".../play.json",
                  judgements: [{category: "core_gameplay", status: "partial", evidence: "after 3 runs every run plays the same"}],
                  loop_answers: {every_5_seconds: "threading a gap", after_60_seconds: "speed ramps", ten_minutes: "nothing new"}}
git checkout -b playcraft/feel-pass ; …implement, test, build…
playcraft_verify {baseline: ".../playcraft.json", changes: [{title: "coyote time", why: "missed ledge jumps", files: ["src/player.ts"]}]}
```

## What it measures on the running game

The probe (`playprobe.mjs`, Playwright + Chromium, served from the build folder with no network) injects a
sampler that reads the game's main canvas as a 64×36 grey thumbnail on animation frames (WebGL contexts are
created with `preserveDrawingBuffer`) and counts DOM mutations. With that:

| Measurement | How | Evidence |
|---|---|---|
| Response to each control | Idle curve first, then the input; the response is the first frame (within 800 ms) where the screen differs from what idling would have shown, or the DOM reacts | verified that it responds; latency observed (±1 frame) |
| Controls probed | Keys found in the source (play keys, not pause/menu keys), click and drag on desktop; tap, hold, swipe/pull-back, left/right taps on touch | verified |
| Dead time | Share of frames with no change during a seeded mixed-input session | observed |
| Idle motion | Mean frame-to-frame change with no input (is the world alive?) | observed |
| Frame rate | rAF timing in a clean window with no canvas reads (FPS, p50, p95) | observed (software WebGL) |
| Pause | A primary action, then the pause key: does motion stop? Tested last so a pause menu cannot swallow other probes | verified (works) / observed (did not stop) |
| Game state | Numbers on exposed objects (`window.game`, globals the source assigns) before and after play | verified |
| Phone DOM | viewport meta, `touch-action` on the play surface, visible controls under 44 px, smallest visible text, horizontal overflow | verified |
| Errors | page errors, console errors, missing files, errors raised by inputs | verified |

## Scoring

Ten categories, 0-100: core gameplay, game feel, controls and responsiveness, progression and rewards,
difficulty and balance, player experience, replayability, technical gameplay quality, presentation and
immersion, mobile experience (only when the docs or code show the game is meant for phones).

Each category is a set of criteria: core ones (`rubric.py`, ~60) plus the genre profiles' own. Each result is
pass / partial / fail / unknown with an **evidence level**:

- **verified** — measured by an automated check on the running game, or a project report file passed as
  `evidence` (hashed into the record)
- **observed** — seen in the running game but approximate (software FPS, latency to a frame), or recorded by
  whoever played it (`judgements`, which can never be `verified`)
- **inferred** — from the source and docs only: a system exists; how it feels is unknown
- **not tested** — no evidence; excluded from the score

Category score = importance- and evidence-weighted mean (verified 1, observed 0.85, inferred 0.45), shrunk
towards 50 by the share of inferred evidence; **a category with no verified/observed evidence is capped at 70**,
and building successfully earns nothing. Overall = genre-weighted mean of scored categories. Confidence comes
from the share of strong evidence and the coverage; an unplayed game is never high-confidence.

Findings: every failed/partial criterion with its evidence (`file:line` or measurement) and a recommendation,
ranked by `impact × genre weight × 2 − effort − risk/2`, +2 for verified defects. Verified technical/mobile/control
failures are **defects**; the rest are **design opportunities**. A secondary genre's criteria count in proportion to
how strongly the game matches it.

## Genre intelligence

`genres.json` has 15 profiles: physics puzzle, arcade, platformer, survival, simulation, strategy,
roguelike/roguelite, incremental, racing, exploration, sandbox, action, sports, management/builder,
hybrid/experimental. Each has detection keywords (docs first, code second), category weights, priorities,
genre questions per discipline, genre criteria with genre-specific recommendations, testing strategies and a
list of systems that do not belong. Games get every genre within reach of the best match (multi-label); three
strong matches mark the game hybrid. `genres: [...]` overrides the detection when you know better.

Detected on real repositories during development:

| Game | Detected | Engine |
|---|---|---|
| DEMO DAY (golf-powered demolition) | physics puzzle + sports | three.js |
| TIDEBREAKERS (flooded-world boat survival) | survival + exploration | three.js |
| ROCKSLIDE (mountain patrol, avalanche physics) | simulation + exploration (+ physics puzzle, sports) | three.js + Rapier (deterministic) |
| Fart Flight (one-button flyer) | arcade | Canvas 2D |
| SKYRUSH (aircraft racing and tuning) | racing + exploration + simulation, hybrid | three.js |

## The specialist disciplines

Each criterion belongs to one discipline; the report groups results, findings and the questions only play can
answer per discipline:

| Discipline | Looks at | Automated evidence |
|---|---|---|
| Game Design Architect | concept, objectives, decisions, identity | docs pitch, objectives/decision systems, playing changes the state |
| Game Feel Engineer | response, weight, impact, shake, particles, easing, audio, restraint | response latency, shake/hit-stop/particles/easing/audio/reduced-motion in source |
| Gameplay Loop Designer | the 5 s / 60 s / 10 min / long-term loop, dead time, mastery | dead time, state changes; `loop_answers` |
| Progression Architect | saves, unlocks, long-term goals; flags bolted-on daily rewards / battle passes / energy / loot boxes | source |
| Player Experience Designer | time to play, onboarding, pause, restart, text size, accessibility | time to play, pause, smallest text |
| Control & Device Specialist | input methods, forgiveness, touch, targets, safe areas, orientation, gestures, device FPS, errors | touch responses, targets, meta, overflow, touch-action, FPS, errors |
| Difficulty & Balance Specialist | ramp, tuning, measured balance, recovery, assists | source; project solver/simulation reports as `evidence` |
| Retention & Replayability Designer | variety, mastery, expression, sharing | source |
| Presentation & Immersion | audio, music, animation, atmosphere, transitions, idle life | idle motion, visual range |

## The combined pass

`playcraft_full_pass` runs TestCraft (`smoke` on every target viewport, `assets` on the build) and the
PLAYCRAFT pass in one out_dir and merges them into one plan:

- **Stage 0, engineering** (TestCraft failures) lands first; PLAYCRAFT items that duplicate them (errors,
  missing files, overflow, blank phone) are dropped so each symptom has one owner.
- Frame rate and input are measured once, by PLAYCRAFT's probe; load errors per viewport and asset validity by TestCraft.
- Each item names its owner (`playcraft`, `playcraft + audiocraft`, `playcraft + fxcraft`, `engineering (testcraft)`…);
  items touching the same files go in one commit.

## Guardrails (verify)

`playcraft_verify` fails when the diff since the baseline commit:

- deletes source files (features removed) — unless listed in `allow_deletions` and justified in `changes`
- changes deployment settings (`vercel.json`, `netlify.toml`, `.github/workflows/`, `CNAME`, `Dockerfile`, …) — unless `allow_deploy_changes`
- adds secret files (`.env`, keys) or secret-looking strings
- touches production data (`*.sqlite`, `prod*/`, …)
- is on `main`/`master`

and when the replay shows a regression: new page/missing/input errors, a control that no longer responds,
FPS down >25 %, response time up by >50 ms and 1.5×, dead time up by >15 points, time-to-play up by 1.5×.

## Integration

| Where | What |
|---|---|
| `studio/departments/playcraft/` | `manifest.json` (actions, schemas, dependencies, limits), `dept.py`, `scan.py`, `rubric.py`, `genres.json`, `report.py`, `playprobe.mjs` |
| `studio/core/web/gamepage.mjs` | Chromium launch + local game server shared with TestCraft (serves Vite builds made for a sub-path, e.g. `base: '/GAME/'`) |
| `studio/core/contract.py` | `register_outputs: false` keeps reports out of the asset catalogue |
| studiocraft / ForgeCraft | tools generated from the manifest; `route` and `department_route` send game-feel/design briefs here |
| `global/skills/playcraft/` | the skill, installed to `~/.claude/skills/playcraft` by `install-global.sh` with the `gitcraft` skill |
| `global/CLAUDE.md` | the two invocation phrases, in every project |
| `tests/test_playcraft.py` | rules, three fixture games (physics, survival/exploration, arcade), verify cycle with guardrails, full pass, routing |
| `tests/acceptance_playcraft.py` | the pass on real game repositories through the user-scope registration, from the game's folder |

## Limitations

- Builds are not run inside the sandbox (no package registry): build with the game's own toolchain and pass `target`.
- Headless Chromium renders WebGL in software: absolute FPS is far below a real phone's GPU and is scored as
  observed; never claim device performance from it.
- The probe plays generically. It gets past a title screen with a start button (or `start_steps`), but it does
  not play to win: level completion, balance and progression pacing need exposed state, the project's own
  scripted playtests/solvers (`evidence`), or recorded `judgements`.
- Latency is measured from the screen against an idle baseline: frame-accurate for games that wait for input,
  approximate for constantly animated scenes, and capped to an 800 ms window.
- Source signals are keyword evidence: they find systems, not quality, which is why they are capped and labelled inferred.
- Design quality (is the loop compelling, is the identity distinctive) is judgement: PLAYCRAFT structures it
  (questions per discipline, `judgements` with evidence) but never invents it.
- PLAYCRAFT does not edit games; implementation is done by the agent or a person in the game's repository.

## Verification

```bash
python3 tests/test_playcraft.py           # ~5 min: rules, three fixture games played, verify cycle, full pass
python3 tests/test_playcraft.py --quick   # rules, discovery, one game
python3 tests/acceptance_playcraft.py <game repo> [<build dir>] [<out>]   # real games, user-scope server, from the game's folder
```
