# GITCRAFT report — Bruh

_Production Report_

`scottyfncodes--bruh/20261109T181255Z` · generated 2026-11-09T18:15:40+00:00 · refresh **full** · read-only · commit `a3933b9` · [scottyfncodes/bruh](https://github.com/scottyfncodes/bruh)

## Executive summary

- Bruh scores **62.2/100** (blocked, medium confidence, 53% of the applicable weight evaluated).
- No production has run for this project, so there is no Director verdict or release gate.
- 3 department(s) evaluated, 3 applicable but not evaluated (playcraft, testcraft, assetcraft).
- 1 unresolved blocker(s): resolve them before anything else.
- Highest-impact next action: Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled.

## Production identity

| Project | Run date | Release / version | Commit | Production | Director verdict |
|---|---|---|---|---|---|
| scottyfncodes/bruh | 2026-11-09 18:15 UTC | 0.1.0 | a3933b9 | none run | no verdict |

## Overall health

| Overall score | Band | Confidence | Evaluated departments | Coverage | vs previous |
|---|---|---|---|---|---|
| 62.2 | blocked | medium | 3 of 6 applicable | 53% | first report |

Basis: weighted mean of 3 evaluated department score(s) (production ×15, pixelcraft ×20, designcraft ×15); 3 applicable department(s) not evaluated (playcraft, testcraft, assetcraft); coverage 53% of the applicable weight.

## Top 3 next actions

1. **Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled** — impact High, effort S (department estimate)<br>Do: See https://dequeuniversity.com/rules/axe/4.10/meta-viewport?application=axeAPI — Fix any of the following:   user-scalable=no on <meta> tag disables zooming on mobile devices
2. **Touch targets and mobile ergonomics: Fixed bars take too much of the screen** — impact High, effort M (department estimate)<br>Do: Shrink or hide bars on scroll, or merge them.
3. **Accessibility and contrast: Accessibility: All page content should be contained by landmarks** — impact Medium, effort S (department estimate)<br>Do: See https://dequeuniversity.com/rules/axe/4.10/region?application=axeAPI — Fix any of the following:   Some page content is not contained by landmarks

_Effort is the owning department's own estimate (PLAYCRAFT effort, PIXELCRAFT cost, DESIGNCRAFT complexity); none is invented._

## Department scorecards

| Department | Score | Previous | Delta | Weight | Rubric | Status | Findings |
|---|---|---|---|---|---|---|---|
| Production Director | 81.2 (Engineering standard) | — | first report | 15 | `standard/1` | Refreshed now | 3 |
| PLAYCRAFT — game design and gameplay quality | Not Evaluated (Gameplay quality) | — | first report | 25 | `playcraft/1` | No data | 0 |
| PIXELCRAFT — visual quality, UI/UX and interface efficiency | 84.2 (Visual quality and usability) | — | first report | 20 | `pixelcraft/1` | Refreshed now | 6 |
| DESIGNCRAFT — game-design intelligence | 14 (Game design) | — | first report | 15 | `designcraft/1` | Refreshed now | 1 |
| TestCraft — automated QA | Not Evaluated (Automated QA) | — | first report | 15 | `testcraft/1` | No data | 0 |
| AssetCraft — asset management | Not Evaluated (Asset licensing) | — | first report | 5 | `assetcraft/1` | No data | 0 |

## Release gates and approvals

- No production has run for this project, so there is no Director verdict and no release gates.

Gates are pass/fail and never part of a quality score.

## Trends

First report: trends start with the next one.

## Major findings

- **critical** · Verified — Accessibility: Zooming and scaling must not be disabled (pixelcraft)
- **major** · Verified — Fixed bars take too much of the screen (pixelcraft)
- **major** · Inferred (assumption) — 6 named characters are barely present in the writing (designcraft)

## Regressions

- First report: nothing to compare yet.

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

Status: **No data**

- PLAYCRAFT re-assessed the existing build for this report (not recorded in the Game Quality History).
- Refresh: ok
- Next: Run PLAYCRAFT on this game (studiocraft playcraft_pass) to measure how it plays.

### PIXELCRAFT — visual quality, UI/UX and interface efficiency

Status: **Refreshed now** · run `now` (2026-11-09) · score **84.2** (low confidence)

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

Status: **No data**

- No outputs from this department were found for this project (its .studio.json records live beside its outputs).
- Next: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### AssetCraft — asset management

Status: **No data**

- Next: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

## Critical issues and blockers

- Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled (pixelcraft; Verified; open since 2026-11-09)

## Cross-department findings

**Corroborated (one fix, several departments)**

- None.

**Conflicts**

- None found.

**Dependencies**

- None.

**Gaps (no data)**

- PLAYCRAFT — game design and gameplay quality — Run PLAYCRAFT on this game (studiocraft playcraft_pass) to measure how it plays.
- TestCraft — automated QA — Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.
- AssetCraft — asset management — Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

## Prioritized action plan

### P0 (1)

1. Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/meta-viewport?application=axeAPI — Fix any of the following:   user-scalable=no on <meta> tag disables zooming on mobile devices

### P1 (1)

2. Touch targets and mobile ergonomics: Fixed bars take too much of the screen — pixelcraft · Verified<br>Do: Shrink or hide bars on scroll, or merge them.

### P2 (8)

3. Accessibility and contrast: Accessibility: All page content should be contained by landmarks — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/region?application=axeAPI — Fix any of the following:   Some page content is not contained by landmarks
4. Content disappears at one screen size — pixelcraft · Verified<br>Do: Reflow content instead of hiding it; move secondary content behind a disclosure rather than display: none.
5. Feedback and game feel: No hover state — pixelcraft · Verified<br>Do: Add a hover style (tone shift, underline, elevation) for every interactive component variant.
6. Layout, spacing and consistency: Spacing does not follow a consistent scale — pixelcraft · Verified<br>Do: Adopt a spacing scale (4/8-px steps: 4, 8, 12, 16, 24, 32) as tokens and replace one-off values with the nearest step.
7. Story, characters and world: 6 named characters are barely present in the writing — designcraft · Inferred (assumption)<br>Do: Give Chad, Melissa and Dyno Dave a voice: one line each where the player meets them, one more later.
8. No data: AssetCraft — asset management — assetcraft · Unavailable<br>Do: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.
9. No data: PLAYCRAFT — game design and gameplay quality — playcraft · Unavailable<br>Do: Run PLAYCRAFT on this game (studiocraft playcraft_pass) to measure how it plays.
10. No data: TestCraft — automated QA — testcraft · Unavailable<br>Do: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### P3 (1)

11. Engineering standard: Engineering standard (review): server inputs are validated — production · Inferred (assumption)

## Changes since the previous report

This is the first GITCRAFT report for this project: future reports will compare against it.

## Recommended next actions

1. [P0] Accessibility and contrast: Accessibility: Zooming and scaling must not be disabled — See https://dequeuniversity.com/rules/axe/4.10/meta-viewport?application=axeAPI — Fix any of the following:   user-scalable=no on <meta> tag disables zooming on mobile devices
2. [P1] Touch targets and mobile ergonomics: Fixed bars take too much of the screen — Shrink or hide bars on scroll, or merge them.
3. Run PLAYCRAFT on this game (studiocraft playcraft_pass) to measure how it plays.
4. Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.
5. Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.
6. Report again after the changes land (Run GITCRAFT report) to measure progress against this report.

## Scoring method

Overall: `gitcraft-score/2`. Each department's score is its own measured result under the rubric below; the overall score is the weighted mean of the evaluated departments only. Not Evaluated departments carry no weight and are never filled in. A previous score is compared only under the same rubric and department method.

| Department | Score | Weight | Rubric | Source |
|---|---|---|---|---|
| Production Director | Engineering standard | 15 | `standard/1` | the engineering standard (docs/app-standards.md), checked read-only on the project |
| PLAYCRAFT | Gameplay quality | 25 | `playcraft/1` | PLAYCRAFT's own overall score from the Game Quality History |
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
