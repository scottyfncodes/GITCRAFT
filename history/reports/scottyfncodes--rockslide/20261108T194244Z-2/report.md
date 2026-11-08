# GITCRAFT report — ROCKSLIDE: Mountain Patrol

`scottyfncodes--rockslide/20261108T194244Z-2` · generated 2026-11-08T19:42:51+00:00 · refresh **quick** · read-only · commit `667ad97` · [scottyfncodes/rockslide](https://github.com/scottyfncodes/rockslide)

## Executive summary

- ROCKSLIDE: Mountain Patrol scores **68.5/100** overall (needs attention, low confidence): mean of 2 measured department score(s) (playcraft, designcraft); 3 applicable department(s) have no score; 1 stale.
- 3 of 14 departments have results for this project; 2 refreshed now, 1 stale, 11 no data.
- Action plan: 0 P0, 3 P1, 7 P2, 6 P3. Findings by evidence: 1 verified, 2 observed, 14 inferred.
- 2 problem area(s) are flagged by several departments at once — the strongest signals in this report.

## Overall health

| Health | Band | Confidence | Measured departments |
|---|---|---|---|
| 68.5 | needs attention | low | 2 of 5 applicable |

Basis: mean of 2 measured department score(s) (playcraft, designcraft); 3 applicable department(s) have no score; 1 stale.

## Department scorecards

| Department | Status | Score | Latest run | Findings |
|---|---|---|---|---|
| Production Director | Refreshed now | — | — | 0 |
| PLAYCRAFT — game design and gameplay quality | Stale | 79 (Gameplay quality) | 2026-11-04 | 5 |
| PIXELCRAFT — visual quality, UI/UX and interface efficiency | No data | — | — | 0 |
| DESIGNCRAFT — game-design intelligence | Refreshed now | 58 (Game design) | 2026-11-08 | 12 |
| TestCraft — automated QA | No data | — | — | 0 |
| AssetCraft — asset management | No data | — | — | 0 |
| 3D Department — ForgeCraft + MeshCraft | No data | — | — | 0 |
| AnimCraft — rigging and animation | No data | — | — | 0 |
| AudioCraft — game audio | No data | — | — | 0 |
| CinematicCraft — cinematics and video | No data | — | — | 0 |
| FXCraft — visual effects | No data | — | — | 0 |
| LevelCraft — levels and maps | No data | — | — | 0 |
| MaterialCraft — PBR materials and shaders | No data | — | — | 0 |
| WorldCraft — procedural environments | No data | — | — | 0 |

No results for this project (nothing to report, nothing assumed): 3D Department (no data), AnimCraft (no data), AudioCraft (no data), CinematicCraft (no data), FXCraft (no data), LevelCraft (no data), MaterialCraft (no data), WorldCraft (no data).

### Production Director

Status: **Refreshed now**

- Discovery: finished game (high confidence) — 500 files, 127 code files, ~30167 lines of code; entry index.html; kind game: engine three, 39 game words; git: 1 commits, last 2026-11-08
- Engineering standard: 9/9 applicable checks pass.
- Refresh: Discovery and the engineering standard re-run read-only for this report

### PLAYCRAFT — game design and gameplay quality

Status: **Stale** · run `20261104234623-pass-b8cfea83` (2026-11-04) · score **79** (medium confidence)

- Evidence: 15 verified, 4 observed, 46 inferred, 3 not tested; the game was played.
- Against its baseline: no measured change (within noise).
- Deployment: live-verified at https://rockslide-game.vercel.app/
- Stale: measured on 2f70374, the project is now at 667ad97
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

Status: **Refreshed now** · run `this report` (2026-11-08) · score **58** (medium confidence)

- Refresh: re-analysed read-only; the game's design data changed (or no recorded run)
- **major** · Inferred (assumption) — 2 missions share the same structure: mount → travel → scan → travel: Eyes on Kessel Bowl and Kessel Bowl Has Reloaded have an identical sequence of objective types. 6 of 10 missions repeat a structure another mission already uses. (facts verified in source: 2)
- **major** · Inferred (assumption) — One story path: no endings, choices or branches in the data: No ending definitions and no scripted choices were found, although the docs talk about choice or consequence 11 times. (facts verified in source: 1)
- **major** · Inferred (assumption) — Only 0 of 46 objectives offer more than one way to complete them: Almost every objective has exactly one target and one method in its definition. (facts verified in source: 5)
- **major** · Inferred (assumption) — The player decides how fast, never what or how: No objective offers alternatives, none is optional, and the story has no endings or choices in the data; free play exists (14 references) but is separate from the missions. (facts verified in source: 1)
- **minor** · Inferred (assumption) — 20 of 45 named places are never a mission destination: No mission objective targets Tannberg Base, Fernhut Cabin, Slope A, Slope B, Slope C and 15 more. They exist in the world data but the mission structure never asks the player to go there. (facts verified in source: 6)
- **minor** · Inferred (assumption) — 56% of the mapped area holds nothing to find or do: Dividing the playable extent (1720×1305 units) into a 6×6 grid, 20 cells contain no placed location and no mission target; the emptiest quarter is the north-east (6 of 9 cells empty). (facts verified in source: 1)
- **minor** · Inferred (assumption) — 7 of 10 missions mention no character: The briefs, objectives and completion text of Eyes on Kessel Bowl, Controlled Release, Firewood for the Kettle, Kessel Bowl Has Reloaded and 3 more name none of the 7 characters. (facts verified in source: 5)
- **minor** · Inferred (assumption) — Buying everything costs 5.1× what the campaign pays: The non-repeating missions pay 1390 funds in total; the 35 priced unlocks cost 7100. The gap is meant to be filled by 4 repeatable mission(s) (Kessel Bowl Has Reloaded, Bring Down the Bowl, Tree Down on the Pass and Stuck in the Drift). (facts verified in source: 2)
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

### P2 (7)

4. Difficulty and balance: Assist / difficulty options (+1 related, playcraft, designcraft) — playcraft, designcraft · Inferred (assumption)
5. Performance and loading: PLAYCRAFT measured 5.1 s from load to first input — designcraft · Observed<br>Do: Let the player act during loading.
6. Mission design: 2 missions share the same structure: mount → travel → scan → travel — designcraft · Inferred (assumption)<br>Do: Give each of Eyes on Kessel Bowl and Kessel Bowl Has Reloaded one objective the others do not have.
7. Player agency and choice: One story path: no endings, choices or branches in the data — designcraft · Inferred (assumption)<br>Do: Add one decision with two outcomes at the story's midpoint.
8. No data: AssetCraft — asset management — assetcraft · Unavailable<br>Do: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.
9. No data: PIXELCRAFT — visual quality, UI/UX and interface efficiency — pixelcraft · Unavailable<br>Do: Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
10. No data: TestCraft — automated QA — testcraft · Unavailable<br>Do: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### P3 (6)

11. Feedback and game feel: Haptics on key moments (where supported) — playcraft · Inferred (assumption)
12. Level design: 20 of 45 named places are never a mission destination — designcraft · Inferred (assumption)<br>Do: Route existing missions through the unused places.
13. Mission design: 2 briefings run past 45 words — designcraft · Inferred (assumption)
14. Player agency and choice: No optional or bonus objectives — designcraft · Inferred (assumption)<br>Do: Add one optional bonus objective to each mission.
15. Progression and rewards: Buying everything costs 5.1× what the campaign pays — designcraft · Inferred (assumption)<br>Do: Bring prices and income closer: raise campaign rewards or lower top prices.
16. Story, characters and world: 7 of 10 missions mention no character — designcraft · Inferred (assumption)<br>Do: Put a person in Eyes on Kessel Bowl, Controlled Release and Firewood for the Kettle: who asked, who is helped.

## Changes since the previous report

Against `scottyfncodes--rockslide/20261108T194244Z` (2026-11-08): health 68.0 → 68.5 (+0.5)

- production: Unavailable → Refreshed now
- playcraft: Current → Stale
- designcraft: Current → Refreshed now; score 57 → 58 (new measurement)
- assetcraft: Unavailable → No data

New findings: 2 · resolved or no longer reported: 2

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

## Evidence and limits

- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).
- **Observed**: seen while playing or simulated, not a hard measurement.
- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.
- **Unavailable**: no data; nothing is filled in for it.
- Not refreshed — playcraft: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself
- Not refreshed — pixelcraft: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself

Report generation is read-only: it changed no code, merged nothing and deployed nothing.
