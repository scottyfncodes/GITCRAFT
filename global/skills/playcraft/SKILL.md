---
name: playcraft
description: Run PLAYCRAFT, GITCRAFT's game-design and gameplay-quality department, on the current game repository: discover the game and its genres, play the build in a real browser (desktop + phone), score 10 categories with evidence levels, rank the highest-impact improvements, implement them in the game, verify against the baseline and report before/after. Use when asked to "run PLAYCRAFT", "run the full GITCRAFT + PLAYCRAFT pass", review, playtest, score or improve how a game plays or feels (game feel, controls, touch controls, onboarding, progression, difficulty, balance, replayability, fun).
---

# The PLAYCRAFT pass

PLAYCRAFT is a GITCRAFT Studio department: `studiocraft` tools `playcraft_discover`, `playcraft_play`,
`playcraft_assess`, `playcraft_pass`, `playcraft_verify`, `playcraft_full_pass`, `playcraft_genres`
(also ForgeCraft `department_run {department: "playcraft", …}`). It runs sandboxed: it reads the game repo
and writes reports to `<repo>/gitcraft-out/playcraft/` (never into the game's source). The game is changed
by you, in the game repo, following its conventions.

Two requests, two entry points:

| Request | Do |
|---|---|
| "Run PLAYCRAFT on this game" | phases 1-7 below with `playcraft_pass` |
| "Run the full GITCRAFT + PLAYCRAFT pass" | the same with `playcraft_full_pass` (adds TestCraft smoke on every target viewport + asset integrity; one plan, engineering defects first, one owner per item) |

## Phase 1-4: discover, play, diagnose, design

1. Read the repo's README/CLAUDE.md yourself; the game's identity is the constraint for everything after.
2. Build it with the project's own toolchain, outside the sandbox (it needs the package registry):
   e.g. `npm ci && npm run build` (static games need no build). Note the output folder (`dist/`).
   If the build fails, that is finding #1: report it, do not score around it.
3. `playcraft_pass {project: <repo>, target: <repo>/dist}` (or `playcraft_full_pass`). If the title screen
   needs a specific click to start, pass `start_steps` (e.g. `[{text: "Play"}]`); for phones the default
   viewports are desktop + iPhone 13.
4. LOOK at the outputs: `play_contact_sheet.png` (what the probe saw), `playcraft_report.md` (scores,
   evidence, ranked findings, plan). Check the probe really got into gameplay; if it sat on a menu, rerun
   with `start_steps`. Never treat a menu screenshot as gameplay evidence.
5. Play it yourself where you can (screenshots/captures with `testcraft_play`, the game's own scripted
   playtests) and record design judgements: `playcraft_assess` with `judgements`
   (`{category, status, evidence}`; levels `observed`/`inferred` only) and the loop answers
   (`loop_answers`: every_5_seconds, after_60_seconds, ten_minutes, long_term, boredom_point, mastery).
   Point `evidence` at the project's own test/simulation reports to add verified evidence.
6. Separate defects (verified failures) from design preferences. Choose the work: highest player impact
   first, low risk, consistent with the genre priorities and the pitch. Say what you are not doing and why.

## Phase 5: implement (in the game repo)

- Branch first (never main). One improvement per commit, small and reversible.
- Preserve the creative identity: tune and add feel/feedback; do not replace mechanics, art style or tone.
- Never: remove features to simplify, touch deployment settings, secrets or production data, rewrite a
  working game, bolt on generic retention systems (daily rewards, battle passes, energy timers, loot boxes).
- Use the other departments for assets (audiocraft for SFX, fxcraft for particles, animcraft…), outputs
  into the game's own asset folders.
- Run the game's own tests, typecheck and build after each change.

## Phase 6-7: verify and report

- Rebuild, then `playcraft_verify {baseline: <out>/playcraft.json, changes: [{title, why, files}]}`.
  It replays with the same probe, compares scores and measured metrics, lists resolved/new issues and
  regressions, and checks the git diff (no deleted source, no deployment/secret/data changes, on a branch).
  A `failed` verify means a regression or a guardrail: fix it, do not explain it away.
- Report (use `pass_report.md`): what was wrong, what changed, why it matters, what was verified (and at
  which evidence level), what remains. Say plainly what was not tested (e.g. real-device performance:
  headless Chromium renders WebGL in software).
- Open a PR in the game repo if that is the project's workflow; do not merge or deploy without permission.

## Reading the scores

0-100 per category: core gameplay, game feel, controls, progression, difficulty/balance, player experience,
replayability, technical, presentation, mobile (only for games meant for phones). Evidence levels:
verified (automated, on the running game), observed (seen running; approximate or recorded by a player),
inferred (source/docs only), not tested. Categories with only inferred evidence are capped at 70; an
unplayed game is never high-confidence. A build that compiles earns nothing by itself.
