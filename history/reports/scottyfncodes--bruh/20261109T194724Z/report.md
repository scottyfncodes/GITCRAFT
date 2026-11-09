# GITCRAFT report — Bruh

_Production Report_

`scottyfncodes--bruh/20261109T194724Z` · generated 2026-11-09T19:50:25+00:00 · refresh **full** · read-only · commit `a3933b9` · [scottyfncodes/bruh](https://github.com/scottyfncodes/bruh)

## Executive summary

- Bruh scores **63.3/100** (blocked, high confidence, 100% of the applicable weight evaluated; not compared with the previous report's 62.2: different departments were evaluated (+assetcraft, +playcraft, +testcraft), so no change is claimed).
- No production has run for this project, so there is no Director verdict or release gate.
- 6 department(s) evaluated.
- 1 unresolved blocker(s): resolve them before anything else.
- Highest-impact next action: Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled.
- 2 problem area(s) are flagged by several departments at once.

## Production identity

| Project | Run date | Release / version | Commit | Production | Director verdict |
|---|---|---|---|---|---|
| scottyfncodes/bruh | 2026-11-09 19:50 UTC | 0.1.0 | a3933b9 | none run | no verdict |

## Overall health

| Overall score | Band | Confidence | Evaluated departments | Coverage | vs previous |
|---|---|---|---|---|---|
| 63.3 | blocked | high | 6 of 6 applicable | 100% | not comparable: different departments were evaluated (+assetcraft, +playcraft, +testcraft) |

Basis: weighted mean of 6 evaluated department score(s) (production ×15, playcraft ×25, pixelcraft ×20, designcraft ×15, testcraft ×15, assetcraft ×5); coverage 100% of the applicable weight.

## Top 3 next actions

1. **Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled** — impact High, effort S (department estimate)<br>Do: See https://dequeuniversity.com/rules/axe/4.10/meta-viewport?application=axeAPI — Fix any of the following:   user-scalable=no on <meta> tag disables zooming on mobile devices
2. **Touch targets and mobile ergonomics: Browser gestures do not fight the game (touch-action, no zoom) (+3 related, playcraft, pixelcraft)** — impact High (corroborated by several departments), effort L (department estimate)<br>Do: Set touch-action: none on the play surface (and disable double-tap zoom) so swipes and pinches go to the game.
3. **Assets and licences: 4 asset(s) have no known licence** — impact High, effort not estimated (not estimated by the department)<br>Do: Add a <file>.license.json sidecar or re-register with the licence (assetcraft_license_report).

_Effort is the owning department's own estimate (PLAYCRAFT effort, PIXELCRAFT cost, DESIGNCRAFT complexity); none is invented._

## Department scorecards

| Department | Score | Previous | Delta | Weight | Rubric | Status | Findings |
|---|---|---|---|---|---|---|---|
| Production Director | 81.2 (Engineering standard) | 81.2 | +0.0 | 15 | `standard/1` | Refreshed now | 3 |
| PLAYCRAFT — game design and gameplay quality | 73 (Gameplay quality) | — | first score | 25 | `playcraft/1` | Current | 12 |
| PIXELCRAFT — visual quality, UI/UX and interface efficiency | 84.3 (Visual quality and usability) | 84.2 | +0.1 | 20 | `pixelcraft/1` | Refreshed now | 6 |
| DESIGNCRAFT — game-design intelligence | 14 (Game design) | 14 | +0 | 15 | `designcraft/1` | Refreshed now | 1 |
| TestCraft — automated QA | 71.4 (Automated QA) | — | first score | 15 | `testcraft/1` | Current | 1 |
| AssetCraft — asset management | 0.0 (Asset licensing) | — | first score | 5 | `assetcraft/1` | Current | 1 |

## Release gates and approvals

- No production has run for this project, so there is no Director verdict and no release gates.

Gates are pass/fail and never part of a quality score.

## Trends

- Overall: 62.2 (gitcraft-score/2) → 63.3 (gitcraft-score/2)
- Engineering standard: 81.2 → 81.2
- Gameplay quality: — → 73
- Visual quality and usability: 84.2 → 84.3
- Game design: 14 → 14
- Automated QA: — → 71.4
- Asset licensing: — → 0.0

## Major findings

- **critical** · Verified — Accessibility: Zooming and scaling must not be disabled (pixelcraft)
- **major** · Verified — 4 asset(s) have no known licence (assetcraft)
- **major** · Verified — Browser gestures do not fight the game (touch-action, no zoom) (playcraft)
- **major** · Verified — Text is legible on the target device (≥ 12 px) (playcraft)
- **major** · Verified — testcraft smoke failed (testcraft)
- **major** · Observed — Actions are acknowledged on screen within ~100 ms (playcraft)

## Regressions

- None measured.

No results for this project (nothing to report, nothing assumed): 3D Department (no data), AnimCraft (no data), AudioCraft (no data), CinematicCraft (no data), FXCraft (no data), LevelCraft (no data), MaterialCraft (no data), WorldCraft (no data).

### Production Director

Status: **Refreshed now** · score **81.2** (high confidence)

- Discovery: finished game (high confidence) — 136 files, 123 code files, ~29952 lines of code; entry index.html; kind game (medium confidence): game code: src/game/scoring.ts; game engine: three; 2D canvas in 3 file(s), with a game loop and input in src/ui/SlingScreen.tsx; 106 game words in code and README (comments and CSS excluded); the README calls it a game; app signals: react-dom; git: 90 commits, last 2026-10-29
- Analytics recognised: HaveAnApp Pulse (index.html).
- Engineering standard: 13/16 applicable checks pass.
- Refresh: Discovery and the engineering standard re-run read-only for this report
- **minor** · Inferred (assumption) — Engineering standard (review): server inputs are validated: no validation library or validate() call in server code
- **minor** · Inferred (assumption) — Engineering standard (review): server routes check who is calling: no authentication in server code
- **minor** · Inferred (assumption) — Engineering standard (review): sign-in and write routes are rate limited: no rate limiting found

### PLAYCRAFT — game design and gameplay quality

Status: **Current** · run `this report` (2026-11-09) · score **73** (low confidence)

- PLAYCRAFT played the existing build for this report on desktop, phone; measured for this report, not recorded in the Game Quality History.
- Low confidence: much of this rests on source evidence; record judgements from playing (playcraft_assess judgements) and point `evidence` at the project's own test reports.
- Refresh: ok
- Next: Record it in the Game Quality History with a full PLAYCRAFT pass (playcraft_pass) to track it over time.
- **major** · Verified — Browser gestures do not fight the game (touch-action, no zoom): play surface touch-action: auto; viewport: width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover
- **major** · Verified — Text is legible on the target device (≥ 12 px): smallest visible text 11 px ('Takes') on phone
- **major** · Verified — Touch targets ≥ 44 px: [{'text': '×', 'w': 32, 'h': 32, 'screen': 'after play'}]
- **major** · Observed — Actions are acknowledged on screen within ~100 ms: fastest visible response 416 ms after the input (median 525.0 ms; one frame here is 183.4 ms, so ≤ 367 ms passes)
- **major** · Observed — Each probed control produces a visible response: 2/5 desktop inputs responded; no visible response: key Enter, key KeyX, click centre (rendering under 10 fps here: re-check misses on real hardware)
- **major** · Observed — Playable quickly (load + start ≤ 3 s): 3310 ms from navigation to playing (load 103 ms + start 3207 ms; served locally)
- **major** · Observed — Touch input responds: 0/5 touch gestures changed the screen
- **minor** · Inferred (assumption) — Auto-pause when the page is hidden: not found in source: visibility_pause
- … 4 more in report.json

### PIXELCRAFT — visual quality, UI/UX and interface efficiency

Status: **Refreshed now** · run `now` (2026-11-09) · score **84.3** (low confidence)

- Refresh: ok
- **critical** · Verified — Accessibility: Zooming and scaling must not be disabled: axe-core rule meta-viewport (wcag2aa, wcag144): Zooming and scaling must not be disabled.
- **major** · Verified — Fixed bars take too much of the screen: Fixed or sticky bars cover 100% of the phone screen height, leaving little room for content.
- **minor** · Verified — Accessibility: All page content should be contained by landmarks: axe-core rule region (best practice): All page content should be contained by landmarks.
- **minor** · Verified — Content disappears at one screen size: At narrow, 'home' shows only 70% of the words other sizes show; hidden content on phones is a common source of 'where did it go?'.
- **minor** · Verified — No hover state: The pointer over this control changes nothing (colour, shadow, underline), so it does not signal that it is clickable.
- **minor** · Verified — Spacing does not follow a consistent scale: Paddings, gaps and margins use many unrelated values, so the rhythm between elements looks accidental rather than designed.

### DESIGNCRAFT — game-design intelligence

Status: **Refreshed now** · run `this report` (2026-11-09) · score **14** (low confidence)

- Refresh: re-analysed read-only; the game's design data changed (or no recorded run)
- **major** · Inferred (assumption) — 6 named characters are barely present in the writing: Chad, Melissa, Dyno Dave, Kevin and 2 more are defined as characters but appear in at most one authored line and never speak. (facts verified in source: 6)

### TestCraft — automated QA

Status: **Current** · run `smoke.studio.json` (2026-11-09) · score **71.4** (high confidence)

- TestCraft smoke-tested the existing build for this report.
- 1 run(s): smoke; 15/21 output checks passed.
- Refresh: ok
- **major** · Verified — testcraft smoke failed: failed checks: desktop: external service haveanapp-pulse-collect.vercel.app verified (blocked by the test harness (no network here; script): the integration is not verified here, which is not a defect; verify it in production (verify-live))

### AssetCraft — asset management

Status: **Current** · run `catalogue` (2026-11-09) · score **0.0** (high confidence)

- AssetCraft catalogued the project's assets for this report (4 files) in a private catalogue (the shared catalogue and the project were not written).
- 4 catalogued assets: 4 image
- Refresh: ok
- **major** · Verified — 4 asset(s) have no known licence: public/apple-touch-icon.png, public/favicon-32.png, public/icon-192.png, public/icon-512.png

## Critical issues and blockers

- Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled (pixelcraft; Verified; open since 2026-11-09)

## Cross-department findings

**Corroborated (one fix, several departments)**

- Feedback and game feel: pixelcraft, playcraft (4 findings)
- Touch targets and mobile ergonomics: pixelcraft, playcraft (5 findings)

**Conflicts**

- Progression: DESIGNCRAFT 17% vs PLAYCRAFT 70% — DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone.
- Variety: DESIGNCRAFT 17% vs PLAYCRAFT 66% — DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone.

**Dependencies**

- None.

**Gaps (no data)**

- None.

## Prioritized action plan

### P0 (1)

1. Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/meta-viewport?application=axeAPI — Fix any of the following:   user-scalable=no on <meta> tag disables zooming on mobile devices

### P1 (6)

2. Touch targets and mobile ergonomics: Browser gestures do not fight the game (touch-action, no zoom) (+3 related, playcraft, pixelcraft) — playcraft, pixelcraft · Verified<br>Do: Set touch-action: none on the play surface (and disable double-tap zoom) so swipes and pinches go to the game.
3. Assets and licences: 4 asset(s) have no known licence — assetcraft · Verified<br>Do: Add a <file>.license.json sidecar or re-register with the licence (assetcraft_license_report).
4. Text legibility and typography: Text is legible on the target device (≥ 12 px) — playcraft · Verified<br>Do: Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).
5. testcraft smoke failed — testcraft · Verified
6. Feedback and game feel: Actions are acknowledged on screen within ~100 ms — playcraft · Observed<br>Do: Acknowledge every input on the very next frame (a pose, a puff, a sound) even when the action itself takes time.
7. Performance and loading: Playable quickly (load + start ≤ 3 s) — playcraft · Observed<br>Do: Cut time to first play: show the start screen immediately, load heavy assets in the background.

### P2 (5)

8. Accessibility and contrast: Accessibility: All page content should be contained by landmarks — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/region?application=axeAPI — Fix any of the following:   Some page content is not contained by landmarks
9. Content disappears at one screen size — pixelcraft · Verified<br>Do: Reflow content instead of hiding it; move secondary content behind a disclosure rather than display: none.
10. Feedback and game feel: No hover state — pixelcraft · Verified<br>Do: Add a hover style (tone shift, underline, elevation) for every interactive component variant.
11. Layout, spacing and consistency: Spacing does not follow a consistent scale — pixelcraft · Verified<br>Do: Adopt a spacing scale (4/8-px steps: 4, 8, 12, 16, 24, 32) as tokens and replace one-off values with the nearest step.
12. Story, characters and world: 6 named characters are barely present in the writing — designcraft · Inferred (assumption)<br>Do: Give Chad, Melissa and Dyno Dave a voice: one line each where the player meets them, one more later.

### P3 (6)

13. Audio: Sound design and music — playcraft · Inferred (assumption)<br>Do: Add ambience and music that respond to the game state (intensity layers), not a single loop.
14. Engineering standard: Engineering standard (review): server inputs are validated — production · Inferred (assumption)
15. Feedback and game feel: Input forgiveness (buffering, deadzones, grace windows) — playcraft · Inferred (assumption)<br>Do: Buffer inputs pressed slightly early and add small grace windows; precise games feel fairer with them.
16. Onboarding and first-time experience: Auto-pause when the page is hidden — playcraft · Inferred (assumption)<br>Do: Pause on visibilitychange so a phone call or app switch never costs a run.
17. Player agency and choice: Run variety (procedural content, build choices) — playcraft · Inferred (assumption)<br>Do: Vary layouts and offer build-defining picks every few minutes.
18. Touch targets and mobile ergonomics: More than one input method (keyboard + pointer/touch, gamepad) — playcraft · Inferred (assumption)<br>Do: Support keyboard and pointer/touch for the same actions; add gamepad if the genre expects it.

## Changes since the previous report

Against `scottyfncodes--bruh/20261109T181255Z` (2026-11-09): health 62.2 → 63.3 (+1.1)

- production: re-measured, score unchanged
- playcraft: No data → Current; first score 73
- pixelcraft: score 84.2 → 84.3 (new measurement)
- designcraft: re-measured, score unchanged
- testcraft: No data → Current; first score 71.4
- assetcraft: No data → Current; first score 0.0
- 3d: re-measured, score unchanged
- animcraft: re-measured, score unchanged
- audiocraft: re-measured, score unchanged
- cinematiccraft: re-measured, score unchanged
- fxcraft: re-measured, score unchanged
- levelcraft: re-measured, score unchanged
- materialcraft: re-measured, score unchanged
- worldcraft: re-measured, score unchanged

New findings: 14 · resolved or no longer reported: 0

A finding disappears only when its department re-measured and no longer reports it, or the department's data is no longer available (see each department's status).

## Recommended next actions

1. [P0] Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled — See https://dequeuniversity.com/rules/axe/4.10/meta-viewport?application=axeAPI — Fix any of the following:   user-scalable=no on <meta> tag disables zooming on mobile devices
2. [P1] Touch targets and mobile ergonomics: Browser gestures do not fight the game (touch-action, no zoom) (+3 related, playcraft, pixelcraft) — Set touch-action: none on the play surface (and disable double-tap zoom) so swipes and pinches go to the game.
3. [P1] Assets and licences: 4 asset(s) have no known licence — Add a <file>.license.json sidecar or re-register with the licence (assetcraft_license_report).
4. [P1] Text legibility and typography: Text is legible on the target device (≥ 12 px) — Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).
5. Record it in the Game Quality History with a full PLAYCRAFT pass (playcraft_pass) to track it over time.
6. Report again after the changes land (Run GITCRAFT report) to measure progress against this report.

## Scoring method

Overall: `gitcraft-score/2`. Each department's score is its own measured result under the rubric below; the overall score is the weighted mean of the evaluated departments only. Not Evaluated departments carry no weight and are never filled in. A previous score is compared only under the same rubric and department method.

| Department | Score | Weight | Rubric | Source |
|---|---|---|---|---|
| Production Director | Engineering standard | 15 | `standard/1` | the engineering standard (docs/app-standards.md), checked read-only on the project |
| PLAYCRAFT | Gameplay quality | 25 | `playcraft/1` | PLAYCRAFT's own overall score from the Game Quality History, or measured for the report on the existing build (refresh=full, not recorded) |
| PIXELCRAFT | Visual quality and usability | 20 | `pixelcraft/1` | PIXELCRAFT's overall audit score (mean over audited UIs) |
| DESIGNCRAFT | Game design | 15 | `designcraft/1` | DESIGNCRAFT's 100-point design score |
| TestCraft | Automated QA | 15 | `testcraft/1` | share of TestCraft output checks that passed |
| AssetCraft | Asset licensing | 5 | `assetcraft/1` | the AssetCraft catalogue |

## Evidence and limits

- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).
- **Observed**: seen while playing or simulated, not a hard measurement.
- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.
- **Unavailable**: no data; nothing is filled in for it.

Report generation is read-only: it changed no code, merged nothing and deployed nothing.
