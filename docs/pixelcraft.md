# PIXELCRAFT — visual quality, UI/UX and interface efficiency

PIXELCRAFT is the GITCRAFT department that answers *is this interface actually good?* — not whether it works
(TestCraft), not how a game plays (PLAYCRAFT), but whether the rendered screens are well spaced, aligned,
readable, easy to tap, consistent, efficient to use and finished.

It looks at the **rendered application in a real browser**, never at its source alone, and it never edits the app.
It is a Studio department (`studio/departments/pixelcraft/`): same contract, launcher, Landlock sandbox, global
install and discovery as the other ten, so it works from every HaveAnApp project without GITCRAFT attached.

## Invoking it

| Say | What happens |
|---|---|
| **Run PIXELCRAFT on this app.** | The `pixelcraft` skill: build/start the app, `pixelcraft_audit`, look at the report, fix the plan on a branch, `pixelcraft_verify`, report before/after |
| "Audit the UI / spacing / buttons / mobile layout" | `pixelcraft_audit` (routing sends UI/UX briefs here) |
| "I fixed it — did it work?" | `pixelcraft_verify {baseline: <out>/audit.json}` |

Tools (studiocraft MCP server; also ForgeCraft `department_run {department: "pixelcraft", …}` and
`studio/cli.py run pixelcraft <action> '<json>'`):

| Tool | What it does |
|---|---|
| `pixelcraft_profiles` | Viewport profiles and the rubric |
| `pixelcraft_discover` | Opens the app, finds its screens (links, nav, tabs, tab bars; breadth first, depth 2) and how many taps each takes |
| `pixelcraft_audit` | Discover → capture every viewport → measure → axe-core → states → journeys → scores, findings, plan, `report.html`, `report.md`, `audit.json`, contact sheet; recorded in the history |
| `pixelcraft_verify` | Replays a baseline exactly (screens + steps, viewports, journeys, state sampling, method), compares, diffs screenshots, fails on regressions or lost coverage |
| `pixelcraft_history` | Every recorded audit/verify per app (append-only) |

### Setup

Nothing to install beyond GITCRAFT's Studio runtime: Playwright + Chromium (preinstalled in cloud sessions),
numpy + Pillow (Studio venv) and **axe-core 4.10.2**, which `scripts/install-studio.sh` adds to the Studio Node
runtime (`~/.gitcraft/studio/node`). Nothing is added to the audited project.

```bash
scripts/install.sh studiocraft          # or: scripts/install-studio.sh  (the SessionStart hook does it)
tests/test_pixelcraft.py --quick        # proves it on the sample app
```

### Targets

| App | Pass |
|---|---|
| Vite / CRA / static / Next.js `output: 'export'` | `target: "<repo>/dist"` (`build/`, `out/`) — served inside the sandbox at `http://app.local/` with SPA fallback (`/settings` → `index.html`, Next's `/about` → `about.html`, Vite `base` sub-paths) |
| Next.js server, apps with an API, anything running | `target: "http://localhost:<port>"` (`npm run dev`, `vite preview`, `next start`). Inside the sandbox allow the port: `GITCRAFT_ALLOW_LOCAL_PORTS=5173` in the environment that starts Claude Code. Without it the call is `blocked` and says so |
| Browser games | the build folder; PIXELCRAFT measures the HTML UI (menus, HUD, buttons) and notes that the canvas is not DOM; pair with PLAYCRAFT |

Only the app's origin loads; every other request is blocked and listed (no network).

### Repeatable commands

```bash
# audit (CLI, same as the MCP tool)
studio/cli.py run pixelcraft audit '{"project": ".", "target": "./dist",
  "journeys": [{"name": "add item", "expected_taps": 2, "steps": [{"click": "New"}, {"fill": {"label": "Name", "value": "x"}}, {"click": "Save"}, {"expect": "Saved"}]}]}'
# after fixing and rebuilding
studio/cli.py run pixelcraft verify '{"baseline": "gitcraft-out/pixelcraft/audit/audit.json"}'
studio/cli.py run pixelcraft history '{}'
```

## Viewports (iPhone-first, mandatory)

| Profile | CSS px | Safe areas (emulated) | Notes |
|---|---|---|---|
| `iphone17` | 402 × 874 | top 62, bottom 34 | primary; journeys + states run here |
| `iphone13` | 390 × 844 | top 47, bottom 34 | |
| `desktop` | 1440 × 900 | — | hover + keyboard Tab traversal run here |
| `narrow` | 320 × 568 | top 20 | iPhone SE 1st gen |
| `tablet` | 820 × 1180 | top 24, bottom 20 | iPad Air |
| `landscape` | 874 × 402 | left/right 62, bottom 21 | iPhone 17 landscape |

`iphone17`, `iphone13` and `desktop` cannot be dropped (`allow_without_iphone: true` for a desktop-only tool;
the report says so). Safe-area insets are applied through CDP (`Emulation.setSafeAreaInsetsOverride`), so
`env(safe-area-inset-*)` resolves like on the phone. The first mobile screen is re-measured with the viewport
shortened by 120 px (Safari's toolbars). All of this is **browser emulation**; real-device screenshots can be
attached as `device_evidence` and are shown separately, labelled physical.

## What it measures

For every screen × viewport the probe (`probe.mjs`) takes a viewport and a full-page screenshot and a geometry
snapshot of every visible element: rect, text rect (the real glyph box), icon rect, font size/weight/line height,
colours and the colour behind, padding, margin, gap, radius, border, position (fixed/sticky), the element really
hit at the control's centre, clipped text, label hit areas; plus layout shift (CLS) while loading, page overflow,
viewport meta, axe-core (WCAG 2.0-2.2 A/AA + best practice), hover and pressed styles (mouse down then away, so
nothing is clicked) and disabled styles on one control per visual variant, and real Tab presses.

| Area | Measured on the rendered page |
|---|---|
| Spacing and rhythm | spacing values on a 4-px scale, evenness of gaps between related siblings, text cramped against its box, unexplained empty bands |
| Layout and composition | horizontal overflow (and the culprit element), truncated text, near-miss alignment (1-6 px off a shared edge), controls covered by other elements (re-checked after scrolling them to centre), use of width (desktop phone-column, stretched controls), layout shift, nesting |
| Typography and hierarchy | text under 12 px on phones, number of font sizes, heading/body ratio, inverted heading levels, line height and line length of paragraphs |
| Buttons and controls | target size (44 px phones / 24 px WCAG floor; inline text links exempt; label hit areas count), neighbouring targets under 8 px apart (worse next to destructive actions), label/icon centring, equal heights in a row, competing primary actions |
| Visual consistency | radii and fills of controls, font families |
| Interaction efficiency | journeys: completion, taps vs `expected_taps`, confirmation dialogs (native `confirm()` and modal "Are you sure"), taps with no effect |
| Navigation and discoverability | taps to reach each screen, persistent navigation, current location marked, dead ends |
| Mobile ergonomics | viewport meta, iOS input zoom (fields under 16 px), safe areas (fixed bars and their controls), thumb reach of main actions, fixed chrome height, toolbar shortening |
| Feedback and interaction states | hover, pressed, disabled look-alikes, feedback after each journey tap (DOM mutation or navigation) and its time |
| Accessibility | axe-core violations weighted by impact, focus visible on Tab, controls reachable by Tab, clickable non-controls |
| Cross-screen / component / responsive / design system / state consistency | header and heading sizes across screens, primary button variants, number of button and input variants, content parity and overflow across viewports, spacing grid, palette size, type scale, radii, hover/pressed/focus applied consistently |

**Design principles.** Nothing rewards minimalism for its own sake: bold colour, large type, playful or dense
layouts are not penalised; only measurable problems are (unreadable, untappable, inconsistent, overflowing,
unreachable). Canvas-dominated screens skip density/alignment/width metrics (the DOM does not describe the
canvas). Taste — "looks generic", "unfinished" — is recorded by whoever looked at the screenshots as
`judgements` (screenshot evidence), never as measured.

## Scoring

Three independent categories, 100 points each:

| Visual Quality | | Usability | | Consistency | |
|---|---|---|---|---|---|
| Spacing and rhythm | 25 | Interaction efficiency | 25 | Cross-screen consistency | 25 |
| Layout and composition | 25 | Navigation and discoverability | 20 | Component consistency | 25 |
| Typography and hierarchy | 20 | Mobile ergonomics | 25 | Responsive consistency | 20 |
| Buttons and controls | 20 | Feedback and interaction states | 15 | Design system adherence | 20 |
| Visual consistency | 10 | Accessibility | 15 | State consistency | 10 |

- Each metric is 0..1 per screen × viewport; across samples it is `0.6 × mean + 0.4 × worst`, so a defect on one
  screen counts. An area is the importance-weighted mean of its metrics (overflow, journeys completing,
  viewport meta weigh 3; targets, safe areas, focus, axe 2…). Category = points-weighted over areas with evidence.
- **Nothing is capped, nothing is awarded for code existing.** An area without evidence is *not tested* and the
  category is scored over the areas that were; **coverage** (share of rubric points with evidence) and
  **confidence** (coverage, screens, viewports, journeys, axe, canvas, emulation vs device) are reported beside the
  score, never folded into it.
- Evidence kinds are kept apart: **measured** (rendered DOM/geometry/interactions), **accessibility** (axe-core),
  **screenshot** (visual judgements, screenshot diffs), **source** (CSS-only observations, weighted 0.3, never used
  to claim a visual result).

## Findings and the plan

Each finding: title, severity (critical/major/minor/cosmetic), evidence kind, explanation with the numbers,
recommended correction, and every occurrence with screen, viewport, selector, rect and measurements; the first
two occurrences get an annotated crop (`evidence/*.png`, red box on the screenshot). The same problem on six
screens is one finding seen 6×. Priority = impact × (1 + log₂ frequency) × (1 + reach) / cost, tiered **fix now**
(critical or priority ≥ 9), **next**, **polish**; the plan lists the top 15 non-cosmetic items.

The report (`report.html`, `report.md`) has: 1 overall score, 2 category scores with area breakdown,
3 strongest screens, 4 weakest screens, 5 critical usability defects, 6 spacing and layout defects, 7 button and
control defects, 8 mobile-specific findings, 9 screenshot gallery, 10 prioritised improvement plan; then
journeys, evidence and limits, and (verify) before/after.

## Re-evaluation (verify)

`pixelcraft_verify` replays the baseline's `replay` block: the same screens with their steps, the same viewports,
the same journeys, the same state sampling and method. It then:

- compares category scores **on the metrics measured in both runs only**, so a removed or weakened check can
  never raise a score; any metric the baseline had and the re-run lacks is listed as **coverage lost** and fails
  the run;
- refuses to compare across methods (`METHOD` in `rubric.py`);
- lists resolved, persisting and new findings; new major/critical findings and metric drops over 15 points are
  **regressions** and fail the run;
- diffs every screen × viewport screenshot (`diff/*.jpg`, changed pixels in red, % changed);
- records the run in the history with the baseline's commit and the new commit.

## History and the live page

Every run is copied (audit.json, reports, gallery, evidence, diffs; not the raw probe) to
`$GITCRAFT_PIXELCRAFT_HISTORY` (default `~/.gitcraft/pixelcraft/history/<app>/<run>/`) with one line per run in
`index.jsonl`. Runs are never rewritten. The committed archive `history/pixelcraft/` is published by the Vercel
build (`forgecraft/ui_server.py --publish`, stdlib `site.py`) at **`/pixelcraft/`**: each app's latest scores,
coverage, confidence, run history and the full reports.

## Sample audit

`tests/fixtures/pixelcraft/taskboard/` is a small hash-routed task app with real-world defects (tab bar under the
home indicator, 13-px inputs, a table that overflows phones, 16-30-px targets 3 px apart, uneven list gaps,
removed focus outlines, double delete confirmation, a Save button with no feedback, a disabled button that looks
enabled, pale text). `taskboard_fixed/` is the same app after the PIXELCRAFT plan. `tests/test_pixelcraft.py`
audits the first, verifies the second against it (every listed defect resolved, all three scores up, no
regressions), then breaks the safe-area padding again and checks verify fails. The archived runs under
`history/pixelcraft/` include this before/after and audits of GITCRAFT's own published pages.

## Limits

- Chromium emulation, not Safari/WebKit and not a phone in a hand; attach `device_evidence` for physical results.
- The on-screen keyboard is not emulated (input zoom is; keyboard overlap is not).
- Builds run outside the sandbox with the project's own toolchain.
- Canvas content is not DOM: use judgements (and PLAYCRAFT for play).
- Automatic journeys only reach screens; task efficiency needs journeys with `expected_taps`.
