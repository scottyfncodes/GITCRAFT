# GITCRAFT report — TIDEBREAKERS

`scottyfncodes--tidebreakers/20261108T194251Z` · generated 2026-11-08T19:42:51+00:00 · refresh **quick** · read-only · [scottyfncodes/tidebreakers](https://github.com/scottyfncodes/tidebreakers)

## Executive summary

- TIDEBREAKERS scores **51.0/100** overall (at risk, low confidence): mean of 2 measured department score(s) (playcraft, designcraft); 3 applicable department(s) have no score.
- 2 of 14 departments have results for this project; 2 current, 10 no data, 2 unavailable.
- Action plan: 0 P0, 3 P1, 4 P2, 4 P3. Findings by evidence: 2 verified, 2 observed, 6 inferred.
- 1 problem area(s) are flagged by several departments at once — the strongest signals in this report.

## Overall health

| Health | Band | Confidence | Measured departments |
|---|---|---|---|
| 51.0 | at risk | low | 2 of 5 applicable |

Basis: mean of 2 measured department score(s) (playcraft, designcraft); 3 applicable department(s) have no score.

## Department scorecards

| Department | Status | Score | Latest run | Findings |
|---|---|---|---|---|
| Production Director | Unavailable | — | — | 0 |
| PLAYCRAFT — game design and gameplay quality | Current | 77 (Gameplay quality) | 2026-11-04 | 6 |
| PIXELCRAFT — visual quality, UI/UX and interface efficiency | No data | — | — | 0 |
| DESIGNCRAFT — game-design intelligence | Current | 25 (Game design) | 2026-11-05 | 4 |
| TestCraft — automated QA | No data | — | — | 0 |
| AssetCraft — asset management | Unavailable | — | — | 0 |
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

Status: **Unavailable**

- The project is not checked out here: Discovery and the engineering standard need its files (clone it and report again).

### PLAYCRAFT — game design and gameplay quality

Status: **Current** · run `20261104235147-pass-0e51229d` (2026-11-04) · score **77** (low confidence)

- Evidence: 16 verified, 3 observed, 49 inferred, 3 not tested; the game was played.
- Against its baseline: code changed; not verified by measurement.
- Deployment: live-verified at https://tidebreakers.vercel.app/
- The project is not checked out here, so the analysed commit could not be compared with the current one.
- Refresh: not refreshed: the project is not checked out here
- **major** · Verified — Browser gestures do not fight the game (touch-action, no zoom): play surface touch-action: auto; viewport: width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover
- **major** · Verified — Text is legible on the target device (≥ 12 px): smallest visible text 9 px ('CATALOG') on phone
- **major** · Observed — Playable quickly (load + start ≤ 3 s): 8036 ms from navigation to playing (load 502 ms + start 7534 ms; served locally)
- **minor** · Inferred (assumption) — Effects can be calmed (reduced motion / shake setting): not found in source: reduced_motion
- **minor** · Inferred (assumption) — Input forgiveness (buffering, deadzones, grace windows): not found in source: input_buffer, deadzone
- **minor** · Inferred (assumption) — More than one input method (keyboard + pointer/touch, gamepad): found input_keyboard, input_pointer

### PIXELCRAFT — visual quality, UI/UX and interface efficiency

Status: **No data**

- Refresh: not refreshed: the project is not checked out here
- Next: Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.

### DESIGNCRAFT — game-design intelligence

Status: **Current** · run `20261105T151235Z-a8065959` (2026-11-05) · score **25** (low confidence)

- The project is not checked out here, so the analysed commit could not be compared with the current one.
- **major** · Inferred (assumption) — 14 named characters are barely present in the writing: Juno Vale, Tomas Reyes, Kai, Mara Okonkwo and 10 more are defined as characters but appear in at most one authored line and never speak. (facts verified in source: 6)
- **minor** · Inferred (assumption) — 53% of the mapped area holds nothing to find or do: Dividing the playable extent (1125×1800 units) into a 6×6 grid, 19 cells contain no placed location and no mission target; the emptiest quarter is the north-west (6 of 9 cells empty). (facts verified in source: 1)
- **minor** · Observed — PLAYCRAFT measured 8.6 s from load to first input: In PLAYCRAFT run 20261105001617-pass-7fe56aea the game took 8.6 s before it accepted play (software renderer; real devices are usually faster).
- **minor** · Inferred (assumption) — The guided chain First Voyage is 13 steps long: First Voyage walks the player through 13 sequential steps (Learn to steer, Sail out of Driftholm, Sail to the atoll to the west, Drop anchor near the beach…). (facts verified in source: 1)

### TestCraft — automated QA

Status: **No data**

- No outputs from this department were found for this project (its .studio.json records live beside its outputs).
- Next: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### AssetCraft — asset management

Status: **Unavailable**

- The project is not checked out here, so its catalogue entries (keyed by folder) cannot be matched.

## Critical issues and blockers

- None measured.

## Cross-department findings

**Corroborated (one fix, several departments)**

- Performance and loading: designcraft, playcraft (2 findings)

**Conflicts**

- Progression: DESIGNCRAFT 33% vs PLAYCRAFT 70% — DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone.
- Difficulty: DESIGNCRAFT 0% vs PLAYCRAFT 70% — DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone.
- Variety: DESIGNCRAFT 17% vs PLAYCRAFT 70% — DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone.

**Dependencies**

- None.

**Gaps (no data)**

- PIXELCRAFT — visual quality, UI/UX and interface efficiency — Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
- TestCraft — automated QA — Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

## Prioritized action plan

### P0 (0)

- None.

### P1 (3)

1. Text legibility and typography: Text is legible on the target device (≥ 12 px) — playcraft · Verified
2. Touch targets and mobile ergonomics: Browser gestures do not fight the game (touch-action, no zoom) — playcraft · Verified
3. Performance and loading: Playable quickly (load + start ≤ 3 s) — playcraft · Observed

### P2 (4)

4. Performance and loading: PLAYCRAFT measured 8.6 s from load to first input — designcraft · Observed<br>Do: Let the player act during loading.
5. Story, characters and world: 14 named characters are barely present in the writing — designcraft · Inferred (assumption)<br>Do: Give Juno Vale, Tomas Reyes and Kai a voice: one line each where the player meets them, one more later.
6. No data: PIXELCRAFT — visual quality, UI/UX and interface efficiency — pixelcraft · Unavailable<br>Do: Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
7. No data: TestCraft — automated QA — testcraft · Unavailable<br>Do: Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.

### P3 (4)

8. Feedback and game feel: Effects can be calmed (reduced motion / shake setting) — playcraft · Inferred (assumption)
9. Level design: 53% of the mapped area holds nothing to find or do — designcraft · Inferred (assumption)<br>Do: Add landmarks and small finds to the north-west of the map.
10. Player experience: The guided chain First Voyage is 13 steps long — designcraft · Inferred (assumption)<br>Do: Cut First Voyage to its first five steps; teach the rest in context.
11. Touch targets and mobile ergonomics: More than one input method (keyboard + pointer/touch, gamepad) — playcraft · Inferred (assumption)

## Changes since the previous report

This is the first GITCRAFT report for this project: future reports will compare against it.

## Recommended next actions

1. [P1] Text legibility and typography: Text is legible on the target device (≥ 12 px)
2. [P1] Touch targets and mobile ergonomics: Browser gestures do not fight the game (touch-action, no zoom)
3. [P1] Performance and loading: Playable quickly (load + start ≤ 3 s)
4. Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability.
5. Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence.
6. Report again after the changes land (Run GITCRAFT report) to measure progress against this report.

## Evidence and limits

- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).
- **Observed**: seen while playing or simulated, not a hard measurement.
- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.
- **Unavailable**: no data; nothing is filled in for it.
- Not refreshed — playcraft: not refreshed: the project is not checked out here
- Not refreshed — pixelcraft: not refreshed: the project is not checked out here
- production: unavailable — The project is not checked out here: Discovery and the engineering standard need its files (clone it and report again).
- assetcraft: unavailable — The project is not checked out here, so its catalogue entries (keyed by folder) cannot be matched.

Report generation is read-only: it changed no code, merged nothing and deployed nothing.
