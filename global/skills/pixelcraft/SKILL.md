---
name: pixelcraft
description: Run PIXELCRAFT, GITCRAFT's visual quality, UI/UX and interface-efficiency evaluator, on the current app or site: open the rendered app (built folder or running localhost URL) in Chromium at iPhone 17, iPhone 13, desktop, narrow, tablet and landscape, discover its screens, measure spacing, alignment, typography, touch targets, button consistency, safe areas, overflow, states, accessibility (axe-core) and user journeys, score Visual Quality / Usability / Consistency with evidence, fix the top items in the project, then verify against the baseline. Use when asked to "run PIXELCRAFT", audit or review a UI, UX, layout, spacing, buttons, mobile ergonomics, polish, "does this look good", or to check a visual fix or a visual regression. Works for React, Vite, Next.js, static sites and browser games (with PLAYCRAFT for gameplay).
---

# The PIXELCRAFT pass

PIXELCRAFT is a GITCRAFT Studio department: `studiocraft` tools `pixelcraft_profiles`, `pixelcraft_discover`,
`pixelcraft_audit`, `pixelcraft_verify`, `pixelcraft_history` (also ForgeCraft
`department_run {department: "pixelcraft", …}` and `studio/cli.py run pixelcraft <action> '<json>'`). It looks
at the RENDERED app, never edits it, and writes to `<repo>/gitcraft-out/pixelcraft/<name>/`.

## 1. Get the app rendering

- Static / Vite / CRA / Next `output: 'export'`: build with the project's own toolchain (outside the sandbox),
  then `target: "<repo>/dist"` (or `build/`, `out/`). The folder is served inside the sandbox with an SPA fallback.
- Next.js server apps, apps with an API: start them (`npm run dev`, `next start`) and pass
  `target: "http://localhost:<port>"`. Inside the sandbox the port must be allowed:
  `GITCRAFT_ALLOW_LOCAL_PORTS=<port>` in the environment that starts Claude Code (a `blocked` result says so).
- A build failure is finding #1: report it, do not audit around it.

## 2. Audit

```
pixelcraft_audit {project: "<repo>", target: "<repo>/dist",
                  journeys: [{name: "create invoice", expected_taps: 3,
                              steps: [{click: "New"}, {fill: {label: "Amount", value: "120"}}, {click: "Save"}, {expect: "Saved"}]}]}
```

- Viewports default to all six; iPhone 17 (402×874), iPhone 13 (390×844) and desktop (1440×900) are mandatory.
- Screens are discovered (links, nav, tabs; templates like /item/1, /item/2 count once). Pass `screens` when
  something needs steps to reach (a modal, a logged-in view).
- Write 2-4 journeys for the app's real tasks with `expected_taps`; without them only automatic "reach each
  screen" journeys run and the report says so.

## 3. Look, then judge

Open `report.html` (or `report.md`) and `contact_sheet.png`. Check that the probe saw real screens (not an error
or a login wall). Measurements cannot see taste: if a screen looks generic, unfinished or incoherent, record it:
`judgements: [{area: "layout", score: 0.4, screen: "home", viewport: "iphone17", title: "Hero looks unfinished",
note: "…", recommendation: "…"}]` — recorded as screenshot evidence, never as measured. Do not penalise bold
colour, large type, playful or dense game HUDs that are intentional, coherent and readable.

## 4. Fix (in the project, on a branch)

Work the plan top-down (`fix now` → `next` → `polish`), one commit per theme, following the project's own
components and tokens (fix the component, not each instance). Never weaken a test or hide a screen to gain points.

## 5. Verify

Rebuild, then `pixelcraft_verify {baseline: "<out>/audit.json"}` (add `target` if the build moved). It replays the
same screens, viewports and journeys with the same method, compares scores on metrics measured in both runs,
lists resolved / persisting / new findings and screenshot diffs, and FAILS on regressions or lost coverage.
A regression your change introduced is yours to fix before you report.

## 6. Report

Lead with the three scores before → after, coverage and confidence (emulation, not a physical device, unless
`device_evidence` was given), the fixes with their evidence, anything still open, and the report path. Never
claim a check that did not run. `pixelcraft_history` shows every app's recorded runs.
