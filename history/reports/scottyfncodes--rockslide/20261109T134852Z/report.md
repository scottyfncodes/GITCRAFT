# GITCRAFT report — SNOW PATROL

_Production Report_

`scottyfncodes--rockslide/20261109T134852Z` · generated 2026-11-09T13:49:02+00:00 · refresh **quick** · read-only · commit `4cf2ea7` · [scottyfncodes/rockslide](https://github.com/scottyfncodes/rockslide)

## Executive summary

- SNOW PATROL scores **78.7/100** (needs attention, medium confidence, 58% of the applicable weight evaluated, +0.0 since the previous report).
- No production has run for this project, so there is no Director verdict or release gate.
- 3 department(s) evaluated, 3 applicable but not evaluated (pixelcraft, testcraft, assetcraft).
- Highest-impact next action: Text legibility and typography: Text is legible on the target device (≥ 12 px).
- 2 problem area(s) are flagged by several departments at once.

## Production identity

| Project | Run date | Release / version | Commit | Production | Director verdict |
|---|---|---|---|---|---|
| scottyfncodes/rockslide | 2026-11-09 13:49 UTC | 0.1.0 | 4cf2ea7 | none run | no verdict |

## Overall health

| Overall score | Band | Confidence | Evaluated departments | Coverage | vs previous |
|---|---|---|---|---|---|
| 78.7 | needs attention | medium | 3 of 6 applicable | 58% | +0.0 vs 78.7 |

Basis: weighted mean of 3 evaluated department score(s) (production ×15, playcraft ×25, designcraft ×15); 3 applicable department(s) not evaluated (pixelcraft, testcraft, assetcraft); coverage 58% of the applicable weight; 1 stale.

## Top 3 next actions

1. **Text legibility and typography: Text is legible on the target device (≥ 12 px)** — impact High, effort S (department estimate)
2. **Performance and loading: Playable quickly (load + start ≤ 3 s)** — impact High, effort L (department estimate)
3. **Difficulty and balance: Assist / difficulty options (+1 related, playcraft, designcraft)** — impact Medium (corroborated by several departments), effort M (department estimate)

_Effort is the owning department's own estimate (PLAYCRAFT effort, PIXELCRAFT cost, DESIGNCRAFT complexity); none is invented._

## Department scorecards

| Department | Score | Previous | Delta | Weight | Rubric | Status | Findings |
|---|---|---|---|---|---|---|---|
| Production Director | 100.0 (Engineering standard) | 100.0 | +0.0 | 15 | `standard/1` | Refreshed now | 0 |
| PLAYCRAFT — game design and gameplay quality | 79 (Gameplay quality) | 79 | +0 | 25 | `playcraft/1` | Stale | 5 |
| PIXELCRAFT — visual quality, UI/UX and interface efficiency | Not Evaluated (Visual quality and usability) | — | not evaluated in either report | 20 | `pixelcraft/1` | No data | 0 |
| DESIGNCRAFT — game-design intelligence | 57 (Game design) | 57 | +0 | 15 | `designcraft/1` | Refreshed now | 12 |
| TestCraft — automated QA | Not Evaluated (Automated QA) | — | not evaluated in either report | 15 | `testcraft/1` | No data | 0 |
| AssetCraft — asset management | Not Evaluated (Asset licensing) | — | not evaluated in either report | 5 | `assetcraft/1` | No data | 0 |

## Release gates and approvals

- No production has run for this project, so there is no Director verdict and no release gates.

Gates are pass/fail and never part of a quality score.

## Trends

- Overall: 68.0 (mean/1) → 68.5 (mean/1) → 78.7 (gitcraft-score/2) → 78.7 (gitcraft-score/2)
- Engineering standard: — → — → 100.0 → 100.0
- Gameplay quality: 79 → 79 → 79 → 79
- Game design: 57 → 58 → 57 → 57

## Major findings

- **major** · Verified — Text is legible on the target device (≥ 12 px) (playcraft)
- **major** · Observed — Playable quickly (load + start ≤ 3 s) (playcraft)
- **major** · Inferred (assumption) — 2 missions share the same structure: mount → travel → scan → travel (designcraft)
- **major** · Inferred (assumption) — 37 of 58 named places are never a mission destination (designcraft)
- **major** · Inferred (assumption) — One story path: no endings, choices or branches in the data (designcraft)

## Regressions

- None measured.

No results for this project (nothing to report, nothing assumed): 3D Department (no data), AnimCraft (no data), AudioCraft (no data), CinematicCraft (no data), FXCraft (no data), LevelCraft (no data), MaterialCraft (no data), WorldCraft (no data).

### Production Director

Status: **Refreshed now** · score **100.0** (high confidence)

- Discovery: finished game (high confidence) — 631 files, 157 code files, ~39955 lines of code; entry index.html; kind game (high confidence): game code: src/game/feel.ts; game engine: three; 2D canvas in 6 file(s), with a game loop and input in src/game/game.ts; 44 game words in code and README (comments and CSS excluded); the README calls it a game; git: 1 commits, last 2026-11-09
- Engineering standard: 9/9 applicable checks pass.
- Refresh: Discovery and the engineering standard re-run read-only for this report

### PLAYCRAFT — game design and gameplay quality

Status: **Stale** · run `20261104234623-pass-b8cfea83` (2026-11-04) · score **79** (medium confidence)

- Evidence: 15 verified, 4 observed, 46 inferred, 3 not tested; the game was played.
- Against its baseline: no measured change (within noise).
- Deployment: live-verified at https://rockslide-game.vercel.app/
- Stale: measured on 2f70374, the project is now at 4cf2ea7
- Refresh: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself
- Next: Re-run PLAYCRAFT (playcraft_pass) on the current build to refresh the gameplay score.
- **major** · Verified — Text is legible on the target device (≥ 12 px): smallest visible text 8.5 px ('Map') on phone
- **major** · Observed — Playable quickly (load + start ≤ 3 s): 5498 ms from navigation to playing (load 899 ms + start 4599 ms; served locally)
- **minor** · Inferred (assumption) — Assist / difficulty options: not found in source: assist, difficulty
- **minor** · Inferred (assumption) — Haptics on key moments (where supported): not found in source: haptics
- **minor** · Inferred (assumption) — Hit-stop / slow motion on key moments: not found in source: hitstop

### PIXELCRAFT — visual quality, UI/UX and interface efficiency

Status: **No data**

- Refresh: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself
- Next: Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.

### DESIGNCRAFT — game-design intelligence

Status: **Refreshed now** · run `this report` (2026-11-09) · score **57** (medium confidence)

- Refresh: re-analysed read-only; the game's design data changed (or no recorded run)
- **major** · Inferred (assumption) — 2 missions share the same structure: mount → travel → scan → travel: Eyes on Kessel Bowl and Kessel Bowl Has Reloaded have an identical sequence of objective types. 6 of 10 missions repeat a structure another mission already uses. (facts verified in source: 2)
- **major** · Inferred (assumption) — 37 of 58 named places are never a mission destination: No mission objective targets lodge-dusk, lodge-night, Tannberg Headwall, West Face, Lift Line Gully and 32 more. They exist in the world data but the mission structure never asks the player to go there. (facts verified in source: 6)
- **major** · Inferred (assumption) — One story path: no endings, choices or branches in the data: No ending definitions and no scripted choices were found, although the docs talk about choice or consequence 3 times. (facts verified in source: 1)
- **major** · Inferred (assumption) — Only 0 of 46 objectives offer more than one way to complete them: Almost every objective has exactly one target and one method in its definition. (facts verified in source: 5)
- **major** · Inferred (assumption) — The player decides how fast, never what or how: No objective offers alternatives, none is optional, and the story has no endings or choices in the data; free play exists (20 references) but is separate from the missions. (facts verified in source: 1)
- **minor** · Inferred (assumption) — 56% of the mapped area holds nothing to find or do: Dividing the playable extent (1720×1192 units) into a 6×6 grid, 20 cells contain no placed location and no mission target; the emptiest quarter is the south-west (6 of 9 cells empty). (facts verified in source: 1)
- **minor** · Inferred (assumption) — 7 of 10 missions mention no character: The briefs, objectives and completion text of Eyes on Kessel Bowl, Controlled Release, Firewood for the Kettle, Kessel Bowl Has Reloaded and 3 more name none of the 7 characters. (facts verified in source: 5)
- **minor** · Inferred (assumption) — Buying everything costs 5.6× what the campaign pays: The non-repeating missions pay 1390 funds in total; the 38 priced unlocks cost 7750. The gap is meant to be filled by 4 repeatable mission(s) (Kessel Bowl Has Reloaded, Bring Down the Bowl, Tree Down on the Pass and Stuck in the Drift). (facts verified in source: 2)
- … 4 more in report.json

### TestCraft — automated QA

Status: **No data**

- No outputs from this department were found for this project (its .studio.json records live beside its outputs).
- Next: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### AssetCraft — asset management

Status: **No data**

- Next: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

## Critical issues and blockers

- None measured.

## Cross-department findings

**Corroborated (one fix, several departments)**

- Difficulty and balance: designcraft, playcraft (2 findings)
- Performance and loading: designcraft, playcraft (2 findings)

**Conflicts**

- Difficulty: DESIGNCRAFT 10% vs PLAYCRAFT 68% — DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone.

**Dependencies**

- PLAYCRAFT is stale — Its score describes an older build. Re-measuring needs a current build; GITCRAFT never builds while reporting, so build first, then run the department (or report with refresh=full).
- DESIGNCRAFT's experience analysis reads PLAYCRAFT — experiencecraft uses PLAYCRAFT runs as simulated evidence, so refresh PLAYCRAFT first, then DESIGNCRAFT.

**Gaps (no data)**

- PIXELCRAFT — visual quality, UI/UX and interface efficiency — Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
- TestCraft — automated QA — Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.
- AssetCraft — asset management — Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

## Prioritized action plan

### P0 (0)

- None.

### P1 (3)

1. Refresh: PLAYCRAFT is stale — playcraft · Verified<br>Do: Re-run PLAYCRAFT (playcraft_pass) on the current build to refresh the gameplay score.
2. Text legibility and typography: Text is legible on the target device (≥ 12 px) — playcraft · Verified
3. Performance and loading: Playable quickly (load + start ≤ 3 s) — playcraft · Observed

### P2 (8)

4. Difficulty and balance: Assist / difficulty options (+1 related, playcraft, designcraft) — playcraft, designcraft · Inferred (assumption)
5. Performance and loading: PLAYCRAFT measured 5.1 s from load to first input — designcraft · Observed<br>Do: Let the player act during loading.
6. Level design: 37 of 58 named places are never a mission destination — designcraft · Inferred (assumption)<br>Do: Route existing missions through the unused places.
7. Mission design: 2 missions share the same structure: mount → travel → scan → travel — designcraft · Inferred (assumption)<br>Do: Give each of Eyes on Kessel Bowl and Kessel Bowl Has Reloaded one objective the others do not have.
8. Player agency and choice: One story path: no endings, choices or branches in the data — designcraft · Inferred (assumption)<br>Do: Add one decision with two outcomes at the story's midpoint.
9. No data: AssetCraft — asset management — assetcraft · Unavailable<br>Do: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.
10. No data: PIXELCRAFT — visual quality, UI/UX and interface efficiency — pixelcraft · Unavailable<br>Do: Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
11. No data: TestCraft — automated QA — testcraft · Unavailable<br>Do: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### P3 (6)

12. Feedback and game feel: Haptics on key moments (where supported) — playcraft · Inferred (assumption)
13. Level design: 56% of the mapped area holds nothing to find or do — designcraft · Inferred (assumption)<br>Do: Add landmarks and small finds to the south-west of the map.
14. Mission design: 2 briefings run past 45 words — designcraft · Inferred (assumption)
15. Player agency and choice: No optional or bonus objectives — designcraft · Inferred (assumption)<br>Do: Add one optional bonus objective to each mission.
16. Progression and rewards: Buying everything costs 5.6× what the campaign pays — designcraft · Inferred (assumption)<br>Do: Bring prices and income closer: raise campaign rewards or lower top prices.
17. Story, characters and world: 7 of 10 missions mention no character — designcraft · Inferred (assumption)<br>Do: Put a person in Eyes on Kessel Bowl, Controlled Release and Firewood for the Kettle: who asked, who is helped.

## Changes since the previous report

Against `scottyfncodes--rockslide/20261109T130958Z` (2026-11-09): health 78.7 → 78.7 (+0.0)

- production: re-measured, score unchanged
- pixelcraft: re-measured, score unchanged
- designcraft: re-measured, score unchanged
- testcraft: re-measured, score unchanged
- assetcraft: re-measured, score unchanged
- 3d: re-measured, score unchanged
- animcraft: re-measured, score unchanged
- audiocraft: re-measured, score unchanged
- cinematiccraft: re-measured, score unchanged
- fxcraft: re-measured, score unchanged
- levelcraft: re-measured, score unchanged
- materialcraft: re-measured, score unchanged
- worldcraft: re-measured, score unchanged

New findings: 0 · resolved or no longer reported: 0

A finding disappears only when its department re-measured and no longer reports it, or the department's data is no longer available (see each department's status).

## Recommended next actions

1. [P1] Refresh: PLAYCRAFT is stale — Re-run PLAYCRAFT (playcraft_pass) on the current build to refresh the gameplay score.
2. [P1] Text legibility and typography: Text is legible on the target device (≥ 12 px)
3. [P1] Performance and loading: Playable quickly (load + start ≤ 3 s)
4. Re-run PLAYCRAFT (playcraft_pass) on the current build to refresh the gameplay score.
5. Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
6. Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.
7. Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.
8. Report again after the changes land (Run GITCRAFT report) to measure progress against this report.

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

## Creative Review (advisory, not scored)

Judgement by Claude Code session (model judgement), requested by the person · commit `4cf2ea7` · vision v1 (unapproved draft). It does not change any score, gate, verdict, priority or the technical plan.

**Assessment against the vision:** Against an unapproved draft of the vision: the title screen and the HUD deliver the place and the patrol identity clearly, and Koda is a first-class control from the first frame. But the first playable frames captured are indoors under an overhead camera, so 'the mountain is the world' is sold on the title screen and not yet in play, and from that camera Koda's defining look does not read. Avalanche control and rescue (pillar 2) and travel across the valley (pillar 4) were not reached by the automated session and remain unassessed.

- **substantial** · Observed in a rendered screen — Hand over control with the mountain in view: Start day one on the lodge porch facing Kessel Bowl with the dispatch on the radio and the mission table one step inside, or ease the camera from the title view down to Vince before handing over control. Keep the roof-lift interior for every later morning.
- **substantial** · Observed in a rendered screen · proposal, needs approval — Make Koda recognisable from the play camera: Give Koda a top-down silhouette: contrasting white mask and chest, a curled tail, and the one dropped ear exaggerated so it reads from above; consider a slightly lower camera pitch when Vince stands still near Koda.
- **substantial** · Hypothesis: needs a human playtest · proposal, needs approval — Proposal: one shared mountain a day: Expose the day seed: everyone plays the same forecast and calls; at the bunk, show zones controlled, natural releases and people found, and a share card for the day.
- **polish** · Observed in a rendered screen — The move/look hint runs into the Stay button on iPhone: Lift the hint above the button row, or fade it out after the first drag on each side.
- **polish** · Observed in a rendered screen — A 'READY' label shows under the compass on desktop: Hide the READY label once the compass appears, or give it its own row.

What works:

- The title screen sells the place: It states the fantasy (you look after this valley) and the toolkit in one screen, in the game's own voice, with a single clear action.
- A field-notebook HUD: The interface looks like patrol paperwork rather than a generic game HUD, so even the numbers carry the identity.
- Koda has buttons of their own: Making the companion a permanent control, not a menu item, delivers pillar 3 in the interface itself.
- Assists are real and opt-in: Players who need help can get it without the default game being softened.

Observed in automated play:

- Every probe input changed the screen (dead time 0.0); the best touch response was 295 ms and the median 636 ms, measured on software WebGL at 2.6 to 6 fps, so responsiveness on a real phone is not measured.
- The pause menu shows three opt-in assists and a vibration setting, so PLAYCRAFT's 'assist or difficulty options not found in source' and 'haptics not found in source' do not hold for this build.
- The automated session stayed in the lodge for the whole run: every play frame on both devices is the interior, so traversal, avalanche control and rescue were not exercised.

From source and design data:

- DESIGNCRAFT's 'the player decides how fast, never what or how' reads only mission data. The README describes free patrol, four ways to travel, tricks and a seeded daily snowpack, so the player's 'how' lives in traversal and avalanche work that mission data does not describe.
- PLAYCRAFT scored this build against a physics-puzzle criterion ('Skill shots are recognised'), which does not fit a patrol simulation; its genre mix pulled in a criterion the game does not aim for.

Hypotheses for a human playtest:

- Whether the rescue procedure (signal, coarse and fine search, probe, dig) stays tense and rewarding on the third rescue or becomes tedious.
- Whether starting indoors and walking to the mission table delays the mountain long enough to lose a first-time player.
- Whether the snowmobile's weight and the ski carving feel as described in the README on a phone GPU.

## Evidence and limits

- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).
- **Observed**: seen while playing or simulated, not a hard measurement.
- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.
- **Unavailable**: no data; nothing is filled in for it.
- Not refreshed — playcraft: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself
- Not refreshed — pixelcraft: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself

Report generation is read-only: it changed no code, merged nothing and deployed nothing.
