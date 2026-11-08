# GITCRAFT report — scottyfncodes/gitcraft

`scottyfncodes--gitcraft/20261108T194251Z` · generated 2026-11-08T19:42:52+00:00 · refresh **quick** · read-only · commit `198322a` · [scottyfncodes/gitcraft](https://github.com/scottyfncodes/gitcraft)

## Executive summary

- scottyfncodes/gitcraft scores **87.7/100** overall (blocked, medium confidence): mean of 2 measured department score(s) (pixelcraft, testcraft); 1 applicable department(s) have no score; 1 stale.
- 10 of 14 departments have results for this project; 8 current, 1 refreshed now, 1 stale, 2 no data, 2 not applicable.
- Action plan: 2 P0, 8 P1, 9 P2, 1 P3. Findings by evidence: 53 verified, 0 observed, 1 inferred.
- There are P0 blockers: resolve them before shipping anything else.

## Overall health

| Health | Band | Confidence | Measured departments |
|---|---|---|---|
| 87.7 | blocked | medium | 2 of 3 applicable |

Basis: mean of 2 measured department score(s) (pixelcraft, testcraft); 1 applicable department(s) have no score; 1 stale.

## Department scorecards

| Department | Status | Score | Latest run | Findings |
|---|---|---|---|---|
| Production Director | Refreshed now | — | — | 15 |
| PLAYCRAFT — game design and gameplay quality | Not applicable | — | — | 0 |
| PIXELCRAFT — visual quality, UI/UX and interface efficiency | Stale | 75.3 (Visual quality and usability (mean of 2 UIs)) | 2026-11-05 | 39 |
| DESIGNCRAFT — game-design intelligence | Not applicable | — | — | 0 |
| TestCraft — automated QA | Current | 100.0 (QA checks passed) | 2026-11-03 | 0 |
| AssetCraft — asset management | No data | — | — | 0 |
| 3D Department — ForgeCraft + MeshCraft | No data | — | — | 0 |
| AnimCraft — rigging and animation | Current | — | 2026-11-03 | 0 |
| AudioCraft — game audio | Current | — | 2026-11-03 | 0 |
| CinematicCraft — cinematics and video | Current | — | 2026-11-03 | 0 |
| FXCraft — visual effects | Current | — | 2026-11-03 | 0 |
| LevelCraft — levels and maps | Current | — | 2026-11-03 | 0 |
| MaterialCraft — PBR materials and shaders | Current | — | 2026-11-03 | 0 |
| WorldCraft — procedural environments | Current | — | 2026-11-03 | 0 |

No results for this project (nothing to report, nothing assumed): PLAYCRAFT (not applicable), DESIGNCRAFT (not applicable), 3D Department (no data).

### Production Director

Status: **Refreshed now**

- Discovery: partial game (high confidence) — 1252 files, 246 code files, ~45517 lines of code; no entry point found; kind game: engine phaser, three, 32 game words; git: 149 commits, last 2026-11-08
- Engineering standard: 4/10 applicable checks pass.
- Discovery saw game engines but no playable entry point, so the game departments do not apply.
- Refresh: Discovery and the engineering standard re-run read-only for this report
- **major** · Verified — Engineering standard: an entry page exists: no index.html or framework layout found
- **major** · Verified — Engineering standard: every script, style and image loads over HTTPS: ['http://gc.local/phaser/dist/phaser.min.js']
- **major** · Verified — Engineering standard: no SQL built by string interpolation: ['tests/test_lifecycle.py']
- **major** · Verified — Engineering standard: no secrets in the source or committed env files: ["tests/test_playcraft.py: API_KEY='sk-…"]
- **major** · Verified — Engineering standard: the API does not allow every origin: cors')()
- **major** · Verified — references a missing file: /assets/icons/apple-touch-icon.png
- **major** · Verified — references a missing file: /assets/icons/favicon.ico
- **major** · Verified — references a missing file: /manifest.webmanifest
- … 7 more in report.json

### PIXELCRAFT — visual quality, UI/UX and interface efficiency

Status: **Stale** · run `20261105T134644Z-audit` (2026-11-05) · score **75.3** (medium confidence)

- Stale: measured on 1530d7e, the project is now at 198322a
- Refresh: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself
- Next: Re-run PIXELCRAFT (pixelcraft_audit) on the current build.
- **critical** · Verified — Accessibility: Certain ARIA roles must contain particular children: axe-core rule aria-required-children (wcag2a, wcag131): Certain ARIA roles must contain particular children.
- **critical** · Verified — Page scrolls sideways (horizontal overflow): The page is 331 px wide in a 320 px viewport: content is cut off and the whole page wobbles sideways when scrolled with a thumb.
- **major** · Verified — Accessibility: Elements must meet minimum color contrast ratio thresholds: axe-core rule color-contrast (wcag2aa, wcag143): Elements must meet minimum color contrast ratio thresholds.
- **major** · Verified — Accessibility: Scrollable region must have keyboard access: axe-core rule scrollable-region-focusable (wcag2a, wcag211, wcag213): Scrollable region must have keyboard access.
- **major** · Verified — Accessibility: Scrollable region must have keyboard access: axe-core rule scrollable-region-focusable (wcag2a, wcag211, wcag213): Scrollable region must have keyboard access.
- **major** · Verified — Buttons side by side have different heights: Buttons in one row are 64, 85 px tall; equivalent controls look like different components and the row looks unbalanced.
- **major** · Verified — Clickable element is not a real control: This element responds to clicks (pointer cursor) but is not a button or link, so keyboard and screen-reader users cannot use it.
- **major** · Verified — Focusing a field zooms the page on iPhone: The field's font-size is 15 px; iOS Safari zooms in on any input under 16 px and leaves the page zoomed after typing.
- … 31 more in report.json

### TestCraft — automated QA

Status: **Current** · run `world_assets.studio.json` (2026-11-03) · score **100.0** (high confidence)

- 4 run(s): assets, perf, play, smoke; 26/26 output checks passed.

### AssetCraft — asset management

Status: **No data**

- Next: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

### AnimCraft — rigging and animation

Status: **Current** · run `drop.studio.json` (2026-11-03)

- 11 run(s): animate, autorig, demo_character, physics, retarget, spritesheet; 46/46 output checks passed.

### AudioCraft — game audio

Status: **Current** · run `theme_16lufs.studio.json` (2026-11-03)

- 13 run(s): ambience, loop, music, process, sfx, voice; 23/23 output checks passed.

### CinematicCraft — cinematics and video

Status: **Current** · run `gameplay.studio.json` (2026-11-03)

- 5 run(s): assemble, capture, shot, storyboard, title_card; 13/13 output checks passed.

### FXCraft — visual effects

Status: **Current** · run `crate_shatter.studio.json` (2026-11-03)

- 12 run(s): destruction, emitter, flipbook; 39/39 output checks passed.

### LevelCraft — levels and maps

Status: **Current** · run `settlement.studio.json` (2026-11-03)

- 5 run(s): generate; 31/31 output checks passed.

### MaterialCraft — PBR materials and shaders

Status: **Current** · run `swatches.studio.json` (2026-11-03)

- 7 run(s): generate, library; 31/31 output checks passed.

### WorldCraft — procedural environments

Status: **Current** · run `ocean.studio.json` (2026-11-03)

- 9 run(s): caves, ocean, sky, terrain; 39/39 output checks passed.

## Critical issues and blockers

- Accessibility and contrast: Accessibility: Certain ARIA roles must contain particular children (pixelcraft; Verified)
- Touch targets and mobile ergonomics: Page scrolls sideways (horizontal overflow) (pixelcraft; Verified)

## Cross-department findings

**Corroborated (one fix, several departments)**

- None.

**Conflicts**

- None found.

**Dependencies**

- PIXELCRAFT is stale — Its score describes an older build. Re-measuring needs a current build; GITCRAFT never builds while reporting, so build first, then run the department (or report with refresh=full).

**Gaps (no data)**

- AssetCraft — asset management — Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

## Prioritized action plan

### P0 (2)

1. Accessibility and contrast: Accessibility: Certain ARIA roles must contain particular children — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/aria-required-children?application=axeAPI — Fix any of the following:   Element has children which are not allowed: button[tabindex]
2. Touch targets and mobile ergonomics: Page scrolls sideways (horizontal overflow) — pixelcraft · Verified<br>Do: Let the offending element shrink (max-width: 100%, min-width: 0 on flex children) or scroll it inside its own container (overflow-x: auto).

### P1 (8)

3. Accessibility and contrast: Accessibility: Elements must meet minimum color contrast ratio thresholds — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/color-contrast?application=axeAPI — Fix any of the following:   Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), f
4. Assets and licences: references a missing file: /assets/icons/apple-touch-icon.png — production · Verified<br>Do: Fix or remove the reference.
5. Engineering standard: Engineering standard: an entry page exists — production · Verified
6. Feedback and game feel: No pressed (active) state — pixelcraft · Verified<br>Do: Add an :active style (darker tone, scale 0.97, or ripple) to every button and link variant.
7. Layout, spacing and consistency: Buttons side by side have different heights — pixelcraft · Verified<br>Do: Use one button size per row (a size token: e.g. 44 px on mobile) and change emphasis with fill/outline, not padding.
8. Refresh: PIXELCRAFT is stale — pixelcraft · Verified<br>Do: Re-run PIXELCRAFT (pixelcraft_audit) on the current build.
9. Text legibility and typography: Text is too small to read comfortably — pixelcraft · Verified<br>Do: Use at least 12 px (13-14 px preferred) for secondary text and keep hierarchy with weight and colour rather than very small sizes.
10. Touch targets and mobile ergonomics: Touch target is too small — pixelcraft · Verified<br>Do: Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size.

### P2 (9)

11. Accessibility and contrast: Accessibility: Heading levels should only increase by one — pixelcraft · Verified<br>Do: See https://dequeuniversity.com/rules/axe/4.10/heading-order?application=axeAPI — Fix any of the following:   Heading order invalid
12. Content disappears at one screen size — pixelcraft · Verified<br>Do: Reflow content instead of hiding it; move secondary content behind a disclosure rather than display: none.
13. Feedback and game feel: Click target is below 24 px — pixelcraft · Verified<br>Do: Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size.
14. Layout, spacing and consistency: Controls stretch across the desktop window — pixelcraft · Verified<br>Do: Cap form and button widths on desktop (max-width 480-560 px) or lay forms out in a constrained column.
15. Navigation does not show where you are — pixelcraft · Verified<br>Do: Mark the current item with aria-current="page" and a visible active style.
16. Release and deployment: 9 unfinished item(s) (stubs, TODOs, open roadmap items) — production · Verified<br>Do: Finish or remove them before release.
17. Text legibility and typography: Lines of text are too long — pixelcraft · Verified<br>Do: Cap text columns at 60-75ch (max-width: 70ch).
18. Touch targets and mobile ergonomics: Controls are too close together — pixelcraft · Verified<br>Do: Keep at least 8 px between targets (more next to destructive actions), or merge rarely used actions into one overflow menu.
19. No data: AssetCraft — asset management — assetcraft · Unavailable<br>Do: Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.

### P3 (1)

20. Engineering standard: Engineering standard (review): server routes check who is calling — production · Inferred (assumption)

## Changes since the previous report

This is the first GITCRAFT report for this project: future reports will compare against it.

## Recommended next actions

1. [P0] Accessibility and contrast: Accessibility: Certain ARIA roles must contain particular children — See https://dequeuniversity.com/rules/axe/4.10/aria-required-children?application=axeAPI — Fix any of the following:   Element has children which are not allowed: button[tabindex]
2. [P0] Touch targets and mobile ergonomics: Page scrolls sideways (horizontal overflow) — Let the offending element shrink (max-width: 100%, min-width: 0 on flex children) or scroll it inside its own container (overflow-x: auto).
3. [P1] Accessibility and contrast: Accessibility: Elements must meet minimum color contrast ratio thresholds — See https://dequeuniversity.com/rules/axe/4.10/color-contrast?application=axeAPI — Fix any of the following:   Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), f
4. [P1] Assets and licences: references a missing file: /assets/icons/apple-touch-icon.png — Fix or remove the reference.
5. Re-run PIXELCRAFT (pixelcraft_audit) on the current build.
6. Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files.
7. Report again after the changes land (Run GITCRAFT report) to measure progress against this report.

## Evidence and limits

- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).
- **Observed**: seen while playing or simulated, not a hard measurement.
- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.
- **Unavailable**: no data; nothing is filled in for it.
- Not refreshed — pixelcraft: not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself

Report generation is read-only: it changed no code, merged nothing and deployed nothing.
