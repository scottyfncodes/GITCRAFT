# PIXELCRAFT audit: GITCRAFT Game Quality History (/games/)

Target: `forgecraft/ui/dist/games (Vercel build)` · method pixelcraft-1.0 · 2026-11-05T13:42:57+00:00 · commit `1530d7e950`

## 1. Overall PIXELCRAFT score: **84.8** / 100 (good)

Evidence coverage 100% · confidence **high** — only automatic journeys (no task-specific journeys with expected taps); browser emulation only (no physical-device evidence)

Coverage and confidence are reported separately from quality: an area with no evidence is *not tested*, never zero and never capped.

## 2. Category scores

| Category | Score | Coverage | Not tested |
|---|---|---|---|
| Visual Quality | **84.2** | 100% | — |
| Usability | **86.7** | 100% | — |
| Consistency | **83.6** | 100% | — |

### Visual Quality

| Area | Points | Awarded | Evidence | Weakest metric |
|---|---|---|---|---|
| Spacing and rhythm | 25 | 21.4 | measured ×120 | spacing values on a 4-px scale (54%) |
| Layout and composition | 25 | 25 | measured ×200 | no horizontal overflow (100%) |
| Typography and hierarchy | 20 | 14.5 | measured ×120 | a small set of font sizes (41%) |
| Buttons and controls | 20 | 13.3 | measured ×106 | neighbouring targets not crowded (25%) |
| Visual consistency | 10 | 10 | measured ×54 | few font families (100%) |

### Usability

| Area | Points | Awarded | Evidence | Weakest metric |
|---|---|---|---|---|
| Interaction efficiency | 25 | 25 | measured ×16 | journeys complete (100%) |
| Navigation and discoverability | 20 | 16 | measured ×19 | the current location is indicated (0%) |
| Mobile ergonomics | 25 | 25 | measured ×80 | responsive viewport meta (100%) |
| Feedback and interaction states | 15 | 8.5 | measured ×31 | controls react to hover (4%) |
| Accessibility | 15 | 12.3 | accessibility ×30, measured ×10 | axe-core WCAG 2.2 AA checks (54%) |

### Consistency

| Area | Points | Awarded | Evidence | Weakest metric |
|---|---|---|---|---|
| Cross-screen consistency | 25 | 21.2 | measured ×12 | headers, heading sizes and fonts match across screens (70%) |
| Component consistency | 25 | 25 | measured ×6 | few button variants (100%) |
| Responsive consistency | 20 | 20 | measured ×10 | the same content at every size (100%) |
| Design system adherence | 20 | 8.6 | measured ×24 | a small set of corner radii (0%) |
| State consistency | 10 | 8.7 | measured ×4 | pressed treatment applied consistently (76%) |

## 3. Strongest screens

- **home** — 90.9
- **fart-flight-arcade-78-medium-conf-genuin** — 87.3

## 4. Weakest screens

- **rockslide-mountain-patrol-simulation-exp** — 86.9
- **open-its-history** — 86.9
- **demo-day-physics-puzzle-destruction-spor** — 87.2

## 5. Critical usability defects

### Accessibility: Certain ARIA roles must contain particular children — critical · Accessibility (axe-core)

axe-core rule aria-required-children (wcag2a, wcag131): Certain ARIA roles must contain particular children.

**Fix:** See https://dequeuniversity.com/rules/axe/4.10/aria-required-children?application=axeAPI — Fix any of the following:   Element has children which are not allowed: button[tabindex]

Seen 24× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, iphone13, iphone17, landscape, narrow, tablet · priority 50.26 (fix now)

- `.tabs2` on open-its-history @ iphone17: axe="Fix any of the following:\n  Element has children which are not allowed: button[tabindex]", nodes_on_screen=1 — ![evidence](evidence/axe_aria-required-children_0.jpg)
- `.tabs2` on demo-day-physics-puzzle-destruction-spor @ iphone17: axe="Fix any of the following:\n  Element has children which are not allowed: button[tabindex]", nodes_on_screen=1 — ![evidence](evidence/axe_aria-required-children_1.jpg)
- `.tabs2` on rockslide-mountain-patrol-simulation-exp @ iphone17: axe="Fix any of the following:\n  Element has children which are not allowed: button[tabindex]", nodes_on_screen=1
### Accessibility: Elements must meet minimum color contrast ratio thresholds — major · Accessibility (axe-core)

axe-core rule color-contrast (wcag2aa, wcag143): Elements must meet minimum color contrast ratio thresholds.

**Fix:** See https://dequeuniversity.com/rules/axe/4.10/color-contrast?application=axeAPI — Fix any of the following:   Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), font weight: normal). Expected contrast rati

Seen 24× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, iphone13, iphone17, landscape, narrow, tablet · priority 30.16 (fix now)

- `.cat:nth-child(1) > .note` on open-its-history @ iphone17: axe="Fix any of the following:\n  Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), font", nodes_on_screen=13 — ![evidence](evidence/axe_color-contrast_0.jpg)
- `.cat:nth-child(2) > .note` on open-its-history @ iphone17: axe="Fix any of the following:\n  Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), font", nodes_on_screen=13 — ![evidence](evidence/axe_color-contrast_1.jpg)
- `.cat:nth-child(4) > .note` on open-its-history @ iphone17: axe="Fix any of the following:\n  Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), font", nodes_on_screen=13
### Accessibility: Scrollable region must have keyboard access — major · Accessibility (axe-core)

axe-core rule scrollable-region-focusable (wcag2a, wcag211, wcag213): Scrollable region must have keyboard access.

**Fix:** See https://dequeuniversity.com/rules/axe/4.10/scrollable-region-focusable?application=axeAPI — Fix any of the following:   Element should have focusable content   Element should be focusable

Seen 12× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: iphone13, iphone17, narrow · priority 19.26 (fix now)

- `.scroll` on open-its-history @ iphone17: axe="Fix any of the following:\n  Element should have focusable content\n  Element should be focusable", nodes_on_screen=1 — ![evidence](evidence/axe_scrollable-region-focusable_0.jpg)
- `.scroll` on demo-day-physics-puzzle-destruction-spor @ iphone17: axe="Fix any of the following:\n  Element should have focusable content\n  Element should be focusable", nodes_on_screen=1 — ![evidence](evidence/axe_scrollable-region-focusable_1.jpg)
- `.scroll` on rockslide-mountain-patrol-simulation-exp @ iphone17: axe="Fix any of the following:\n  Element should have focusable content\n  Element should be focusable", nodes_on_screen=1
### No pressed (active) state — major · Measured (rendered DOM)

Pressing this control changes nothing visually until the action completes; on touch screens there is no hover, so this is the only immediate confirmation of a tap.

**Fix:** Add an :active style (darker tone, scale 0.97, or ripple) to every button and link variant.

Seen 10× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, iphone17 · priority 17.29 (fix now)

- `header.bar > a.mark` on home @ iphone17: style_changed_when_pressed=false — ![evidence](evidence/states_no_pressed_0.jpg)
- `header.bar > nav > a` on home @ iphone17: style_changed_when_pressed=false — ![evidence](evidence/states_no_pressed_1.jpg)
- `#app > section.next > a.go` on home @ iphone17: style_changed_when_pressed=false

## 6. Spacing and layout defects

### Text is too small to read comfortably — minor · Measured (rendered DOM)

11-px text is below the 12-px minimum for phones; secondary information (dates, tags, captions) becomes hard to read.

**Fix:** Use at least 12 px (13-14 px preferred) for secondary text and keep hierarchy with weight and colour rather than very small sizes.

Seen 25× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: iphone13, iphone17, landscape, narrow, tablet · priority 20.69 (fix now)

- `a.cart:nth-of-type(1) > div.meta:nth-of-type(3) > div:nth-of-type(1) > span` on home @ iphone17: font_size_px=11 — ![evidence](evidence/type_too_small_0.jpg)
- `a.cart:nth-of-type(1) > div.meta:nth-of-type(3) > div:nth-of-type(2) > span` on home @ iphone17: font_size_px=11 — ![evidence](evidence/type_too_small_1.jpg)
- `a.cart:nth-of-type(1) > div.meta:nth-of-type(3) > div:nth-of-type(3) > span` on home @ iphone17: font_size_px=11
### Uneven spacing between related elements — major · Measured (rendered DOM)

Items of the same kind in one list or stack are separated by different gaps, which reads as grouping that isn't there and makes the list look broken.

**Fix:** Give the container one gap (flex/grid `gap`, or one margin rule for all items) instead of per-item margins.

Seen 13× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, iphone13, iphone17, landscape, narrow, tablet · priority 20.21 (fix now)

- `#app` on demo-day-physics-puzzle-destruction-spor @ iphone17: gaps_px=[16, 16, 0, 0], spread_px=16 — ![evidence](evidence/spacing_uneven_0.jpg)
- `#app` on rockslide-mountain-patrol-simulation-exp @ iphone17: gaps_px=[17, 16, 0, 0], spread_px=17 — ![evidence](evidence/spacing_uneven_1.jpg)
- `#app` on fart-flight-arcade-78-medium-conf-genuin @ iphone17: gaps_px=[16, 16, 0, 0], spread_px=16
### Lines of text are too long — minor · Measured (rendered DOM)

About 154 characters per line; beyond ~80 the eye loses its place.

**Fix:** Cap text columns at 60-75ch (max-width: 70ch).

Seen 11× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, landscape, tablet · priority 12.19 (fix now)

- `#flist > li:nth-of-type(4) > p` on open-its-history @ desktop: approx_chars_per_line=154 — ![evidence](evidence/type_line_length_0.jpg)
- `#foot > p:nth-of-type(1)` on home @ tablet: approx_chars_per_line=125 — ![evidence](evidence/type_line_length_1.jpg)
- `#foot > p:nth-of-type(3)` on home @ tablet: approx_chars_per_line=128
### Spacing does not follow a consistent scale — minor · Measured (rendered DOM)

Paddings, gaps and margins use many unrelated values, so the rhythm between elements looks accidental rather than designed.

**Fix:** Adopt a spacing scale (4/8-px steps: 4, 8, 12, 16, 24, 32) as tokens and replace one-off values with the nearest step.

Seen 9× — screens: fart-flight-arcade-78-medium-conf-genuin, home; viewports: desktop, iphone13, iphone17, landscape, narrow, tablet · priority 7.74 (next)

- `—` on home @ iphone17: on_scale_share=0.59, distinct_values=19, off_scale_values_px=[10, 6, 14, 18, 22, 34] — ![evidence](evidence/spacing_off_scale_0.jpg)
- `—` on home @ iphone13: on_scale_share=0.59, distinct_values=19, off_scale_values_px=[10, 6, 14, 18, 22, 34] — ![evidence](evidence/spacing_off_scale_1.jpg)
- `—` on home @ desktop: on_scale_share=0.58, distinct_values=18, off_scale_values_px=[10, 6, 14, 18, 22, 34, 30]
### Controls stretch across the desktop window — minor · Measured (rendered DOM)

A 1086-px-wide button on a 1440-px screen: the mobile full-width style was never adapted, so the control looks bloated and the eye travels far.

**Fix:** Cap form and button widths on desktop (max-width 480-560 px) or lay forms out in a constrained column.

Seen 1× — screens: home; viewports: desktop · priority 2.07 (polish)

- `#app > div.qa:nth-of-type(3) > details:nth-of-type(1) > summary` on home @ desktop: width_px=1086 — ![evidence](evidence/layout_stretched_control_0.jpg)
- `#app > div.qa:nth-of-type(3) > details:nth-of-type(2) > summary` on home @ desktop: width_px=1086 — ![evidence](evidence/layout_stretched_control_1.jpg)

## 7. Button and control defects

### Touch target is too small — major · Measured (rendered DOM)

202×41 px: under the 44×44 pt Apple HIG minimum (24 px is the WCAG 2.2 floor); thumbs miss and hit neighbours.

**Fix:** Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size.

Seen 24× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: iphone13, iphone17, landscape, narrow, tablet · priority 30.16 (fix now)

- `header.bar > a.mark` on home @ iphone17: width_px=202, height_px=41, minimum_px=44 — ![evidence](evidence/controls_small_target_0.jpg)
- `#app > section.panel:nth-of-type(1) > p.mono > a` on open-its-history @ iphone17: width_px=231, height_px=14, minimum_px=44 — ![evidence](evidence/controls_small_target_1.jpg)
- `#app > section.panel:nth-of-type(4) > div.tabs2 > button.on:nth-of-type(1)` on open-its-history @ iphone17: width_px=86, height_px=40, minimum_px=44
### No pressed (active) state — major · Measured (rendered DOM)

Pressing this control changes nothing visually until the action completes; on touch screens there is no hover, so this is the only immediate confirmation of a tap.

**Fix:** Add an :active style (darker tone, scale 0.97, or ripple) to every button and link variant.

Seen 10× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, iphone17 · priority 17.29 (fix now)

- `header.bar > a.mark` on home @ iphone17: style_changed_when_pressed=false — ![evidence](evidence/states_no_pressed_0.jpg)
- `header.bar > nav > a` on home @ iphone17: style_changed_when_pressed=false — ![evidence](evidence/states_no_pressed_1.jpg)
- `#app > section.next > a.go` on home @ iphone17: style_changed_when_pressed=false
### No hover state — minor · Measured (rendered DOM)

The pointer over this control changes nothing (colour, shadow, underline), so it does not signal that it is clickable.

**Fix:** Add a hover style (tone shift, underline, elevation) for every interactive component variant.

Seen 5× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop · priority 7.75 (next)

- `header.bar > a.mark` on home @ desktop: style_changed_on_hover=false — ![evidence](evidence/states_no_hover_0.jpg)
- `header.bar > nav > a` on home @ desktop: style_changed_on_hover=false — ![evidence](evidence/states_no_hover_1.jpg)
- `#app > section.next > a.go` on home @ desktop: style_changed_on_hover=false
### Click target is below 24 px — minor · Measured (rendered DOM)

231×14 px: under the WCAG 2.2 24×24 px minimum target size.

**Fix:** Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size.

Seen 3× — screens: fart-flight-arcade-78-medium-conf-genuin, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop · priority 5.69 (next)

- `#app > section.panel:nth-of-type(1) > p.mono > a` on open-its-history @ desktop: width_px=231, height_px=14, minimum_px=24 — ![evidence](evidence/controls_small_target_desktop_0.jpg)
- `#app > section.panel:nth-of-type(1) > p.mono > a` on rockslide-mountain-patrol-simulation-exp @ desktop: width_px=246, height_px=14, minimum_px=24 — ![evidence](evidence/controls_small_target_desktop_1.jpg)
- `#app > section.panel:nth-of-type(1) > p.mono > a` on fart-flight-arcade-78-medium-conf-genuin @ desktop: width_px=318, height_px=14, minimum_px=24
### Two primary actions compete — minor · Measured (rendered DOM)

'TIDEBREAKERS Survival Exploration / adventure 77 LOW CONF. C' and 'DEMO DAY Physics puzzle / destruction Sports 78 LOW CONF. ME' are both strongly filled, similar in size and side by side, so neither reads as the main action.

**Fix:** Keep one filled primary button per group; make the other secondary (outline or tonal).

Seen 2× — screens: home; viewports: desktop, tablet · priority 4.27 (polish)

- `#app > div.carts:nth-of-type(2) > a.cart:nth-of-type(1)` on home @ desktop: fill_a=[16, 41, 75, 1], fill_b=[16, 41, 75, 1], other="DEMO DAY Physics puzzle / destruction Sports 78 LOW CONF. ME" — ![evidence](evidence/controls_competing_primary_0.jpg)
- `#app > div.carts:nth-of-type(2) > a.cart:nth-of-type(1)` on home @ desktop: fill_a=[16, 41, 75, 1], fill_b=[16, 41, 75, 1], other="ROCKSLIDE: Mountain Patrol Simulation Exploration / adventur" — ![evidence](evidence/controls_competing_primary_1.jpg)
- `#app > div.carts:nth-of-type(2) > a.cart:nth-of-type(1)` on home @ tablet: fill_a=[16, 41, 75, 1], fill_b=[16, 41, 75, 1], other="DEMO DAY Physics puzzle / destruction Sports 78 LOW CONF. ME"

## 8. Mobile-specific findings

### Touch target is too small — major · Measured (rendered DOM)

202×41 px: under the 44×44 pt Apple HIG minimum (24 px is the WCAG 2.2 floor); thumbs miss and hit neighbours.

**Fix:** Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size.

Seen 24× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: iphone13, iphone17, landscape, narrow, tablet · priority 30.16 (fix now)

- `header.bar > a.mark` on home @ iphone17: width_px=202, height_px=41, minimum_px=44 — ![evidence](evidence/controls_small_target_0.jpg)
- `#app > section.panel:nth-of-type(1) > p.mono > a` on open-its-history @ iphone17: width_px=231, height_px=14, minimum_px=44 — ![evidence](evidence/controls_small_target_1.jpg)
- `#app > section.panel:nth-of-type(4) > div.tabs2 > button.on:nth-of-type(1)` on open-its-history @ iphone17: width_px=86, height_px=40, minimum_px=44
### Text is too small to read comfortably — minor · Measured (rendered DOM)

11-px text is below the 12-px minimum for phones; secondary information (dates, tags, captions) becomes hard to read.

**Fix:** Use at least 12 px (13-14 px preferred) for secondary text and keep hierarchy with weight and colour rather than very small sizes.

Seen 25× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, home, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: iphone13, iphone17, landscape, narrow, tablet · priority 20.69 (fix now)

- `a.cart:nth-of-type(1) > div.meta:nth-of-type(3) > div:nth-of-type(1) > span` on home @ iphone17: font_size_px=11 — ![evidence](evidence/type_too_small_0.jpg)
- `a.cart:nth-of-type(1) > div.meta:nth-of-type(3) > div:nth-of-type(2) > span` on home @ iphone17: font_size_px=11 — ![evidence](evidence/type_too_small_1.jpg)
- `a.cart:nth-of-type(1) > div.meta:nth-of-type(3) > div:nth-of-type(3) > span` on home @ iphone17: font_size_px=11
### Controls are too close together — minor · Measured (rendered DOM)

'Open 6' and 'Fixed 5' are 6 px apart and at least one is under 44 px: an easy mis-tap.

**Fix:** Keep at least 8 px between targets (more next to destructive actions), or merge rarely used actions into one overflow menu.

Seen 24× — screens: demo-day-physics-puzzle-destruction-spor, fart-flight-arcade-78-medium-conf-genuin, open-its-history, rockslide-mountain-patrol-simulation-exp; viewports: desktop, iphone13, iphone17, landscape, narrow, tablet · priority 20.11 (fix now)

- `#app > section.panel:nth-of-type(4) > div.tabs2 > button.on:nth-of-type(1)` on open-its-history @ iphone17: gap_px=6, neighbour="#app > section.panel:nth-of-type(4) > div.tabs2 > button:nth-of-type(2)" — ![evidence](evidence/controls_too_close_0.jpg)
- `#app > section.panel:nth-of-type(4) > div.tabs2 > button.on:nth-of-type(1)` on open-its-history @ iphone17: gap_px=6, neighbour="#app > section.panel:nth-of-type(4) > div.tabs2 > button:nth-of-type(3)" — ![evidence](evidence/controls_too_close_1.jpg)
- `#app > section.panel:nth-of-type(4) > div.tabs2 > button:nth-of-type(2)` on open-its-history @ iphone17: gap_px=6, neighbour="#app > section.panel:nth-of-type(4) > div.tabs2 > button:nth-of-type(3)"

## 9. Screenshot gallery

Browser emulation (Playwright + Chromium); safe-area insets emulated through CDP. No physical-device evidence.

- home @ iphone17: ![home](gallery/home__iphone17.jpg)
- open-its-history @ iphone17: ![open-its-history](gallery/open-its-history__iphone17.jpg)
- demo-day-physics-puzzle-destruction-spor @ iphone17: ![demo-day-physics-puzzle-destruction-spor](gallery/demo-day-physics-puzzle-destruction-spor__iphone17.jpg)
- rockslide-mountain-patrol-simulation-exp @ iphone17: ![rockslide-mountain-patrol-simulation-exp](gallery/rockslide-mountain-patrol-simulation-exp__iphone17.jpg)
- fart-flight-arcade-78-medium-conf-genuin @ iphone17: ![fart-flight-arcade-78-medium-conf-genuin](gallery/fart-flight-arcade-78-medium-conf-genuin__iphone17.jpg)
- home @ iphone13: ![home](gallery/home__iphone13.jpg)
- open-its-history @ iphone13: ![open-its-history](gallery/open-its-history__iphone13.jpg)
- demo-day-physics-puzzle-destruction-spor @ iphone13: ![demo-day-physics-puzzle-destruction-spor](gallery/demo-day-physics-puzzle-destruction-spor__iphone13.jpg)
- rockslide-mountain-patrol-simulation-exp @ iphone13: ![rockslide-mountain-patrol-simulation-exp](gallery/rockslide-mountain-patrol-simulation-exp__iphone13.jpg)
- fart-flight-arcade-78-medium-conf-genuin @ iphone13: ![fart-flight-arcade-78-medium-conf-genuin](gallery/fart-flight-arcade-78-medium-conf-genuin__iphone13.jpg)
- home @ desktop: ![home](gallery/home__desktop.jpg)
- open-its-history @ desktop: ![open-its-history](gallery/open-its-history__desktop.jpg)
- demo-day-physics-puzzle-destruction-spor @ desktop: ![demo-day-physics-puzzle-destruction-spor](gallery/demo-day-physics-puzzle-destruction-spor__desktop.jpg)
- rockslide-mountain-patrol-simulation-exp @ desktop: ![rockslide-mountain-patrol-simulation-exp](gallery/rockslide-mountain-patrol-simulation-exp__desktop.jpg)
- fart-flight-arcade-78-medium-conf-genuin @ desktop: ![fart-flight-arcade-78-medium-conf-genuin](gallery/fart-flight-arcade-78-medium-conf-genuin__desktop.jpg)
- home @ narrow: ![home](gallery/home__narrow.jpg)
- open-its-history @ narrow: ![open-its-history](gallery/open-its-history__narrow.jpg)
- demo-day-physics-puzzle-destruction-spor @ narrow: ![demo-day-physics-puzzle-destruction-spor](gallery/demo-day-physics-puzzle-destruction-spor__narrow.jpg)
- rockslide-mountain-patrol-simulation-exp @ narrow: ![rockslide-mountain-patrol-simulation-exp](gallery/rockslide-mountain-patrol-simulation-exp__narrow.jpg)
- fart-flight-arcade-78-medium-conf-genuin @ narrow: ![fart-flight-arcade-78-medium-conf-genuin](gallery/fart-flight-arcade-78-medium-conf-genuin__narrow.jpg)
- home @ tablet: ![home](gallery/home__tablet.jpg)
- open-its-history @ tablet: ![open-its-history](gallery/open-its-history__tablet.jpg)
- demo-day-physics-puzzle-destruction-spor @ tablet: ![demo-day-physics-puzzle-destruction-spor](gallery/demo-day-physics-puzzle-destruction-spor__tablet.jpg)
- rockslide-mountain-patrol-simulation-exp @ tablet: ![rockslide-mountain-patrol-simulation-exp](gallery/rockslide-mountain-patrol-simulation-exp__tablet.jpg)
- fart-flight-arcade-78-medium-conf-genuin @ tablet: ![fart-flight-arcade-78-medium-conf-genuin](gallery/fart-flight-arcade-78-medium-conf-genuin__tablet.jpg)
- home @ landscape: ![home](gallery/home__landscape.jpg)
- open-its-history @ landscape: ![open-its-history](gallery/open-its-history__landscape.jpg)
- demo-day-physics-puzzle-destruction-spor @ landscape: ![demo-day-physics-puzzle-destruction-spor](gallery/demo-day-physics-puzzle-destruction-spor__landscape.jpg)
- rockslide-mountain-patrol-simulation-exp @ landscape: ![rockslide-mountain-patrol-simulation-exp](gallery/rockslide-mountain-patrol-simulation-exp__landscape.jpg)
- fart-flight-arcade-78-medium-conf-genuin @ landscape: ![fart-flight-arcade-78-medium-conf-genuin](gallery/fart-flight-arcade-78-medium-conf-genuin__landscape.jpg)

## 10. Prioritised improvement plan

| # | Tier | Fix | Severity | Seen | Cost | Area |
|---|---|---|---|---|---|---|
| 1 | fix now | **Accessibility: Certain ARIA roles must contain particular children** — See https://dequeuniversity.com/rules/axe/4.10/aria-required-children?application=axeAPI — Fix any of the following:   Element has children which are not allowed: button[tabindex] | critical | 24× | low | accessibility |
| 2 | fix now | **Accessibility: Elements must meet minimum color contrast ratio thresholds** — See https://dequeuniversity.com/rules/axe/4.10/color-contrast?application=axeAPI — Fix any of the following:   Element has insufficient color contrast of 3.99 (foreground color: #6f88a8, background color: #10294b, font size: 9.0pt (12px), font weight: normal). Expected contrast rati | major | 24× | low | accessibility |
| 3 | fix now | **Touch target is too small** — Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size. | major | 24× | low | controls |
| 4 | fix now | **Text is too small to read comfortably** — Use at least 12 px (13-14 px preferred) for secondary text and keep hierarchy with weight and colour rather than very small sizes. | minor | 25× | low | typography |
| 5 | fix now | **Uneven spacing between related elements** — Give the container one gap (flex/grid `gap`, or one margin rule for all items) instead of per-item margins. | major | 13× | low | spacing |
| 6 | fix now | **Accessibility: Heading levels should only increase by one** — See https://dequeuniversity.com/rules/axe/4.10/heading-order?application=axeAPI — Fix any of the following:   Heading order invalid | minor | 24× | low | accessibility |
| 7 | fix now | **Controls are too close together** — Keep at least 8 px between targets (more next to destructive actions), or merge rarely used actions into one overflow menu. | minor | 24× | low | mobile |
| 8 | fix now | **Accessibility: Scrollable region must have keyboard access** — See https://dequeuniversity.com/rules/axe/4.10/scrollable-region-focusable?application=axeAPI — Fix any of the following:   Element should have focusable content   Element should be focusable | major | 12× | low | accessibility |
| 9 | fix now | **No pressed (active) state** — Add an :active style (darker tone, scale 0.97, or ripple) to every button and link variant. | major | 10× | low | feedback |
| 10 | fix now | **Lines of text are too long** — Cap text columns at 60-75ch (max-width: 70ch). | minor | 11× | low | typography |
| 11 | next | **The same heading level has different sizes on different screens** — Style headings once, globally, from the type scale. | minor | 6× | low | cross_screen |
| 12 | next | **Navigation does not show where you are** — Mark the current item with aria-current="page" and a visible active style. | minor | 6× | low | navigation |
| 13 | next | **No hover state** — Add a hover style (tone shift, underline, elevation) for every interactive component variant. | minor | 5× | low | feedback |
| 14 | next | **Spacing does not follow a consistent scale** — Adopt a spacing scale (4/8-px steps: 4, 8, 12, 16, 24, 32) as tokens and replace one-off values with the nearest step. | minor | 9× | medium | spacing |
| 15 | next | **Click target is below 24 px** — Enlarge the hit area to 44×44 (padding, min-height/min-width, or an ::after hit-area) while keeping the visible glyph size. | minor | 3× | low | controls |

Lower-priority items not listed: 2 (in audit.json).

## Journeys

| Journey | Viewport | Result | Taps | Expected | Confirmations | Feedback (ms) |
|---|---|---|---|---|---|---|
| reach open-its-history (auto) | iphone17 | ok | 1 | — | 0 | 130 |
| reach demo-day-physics-puzzle-destruction-spor (auto) | iphone17 | ok | 1 | — | 0 | 137 |
| reach rockslide-mountain-patrol-simulation-exp (auto) | iphone17 | ok | 1 | — | 0 | 150 |
| reach fart-flight-arcade-78-medium-conf-genuin (auto) | iphone17 | ok | 1 | — | 0 | 130 |
| reach open-its-history (auto) | desktop | ok | 1 | — | 0 | 112 |
| reach demo-day-physics-puzzle-destruction-spor (auto) | desktop | ok | 1 | — | 0 | 138 |
| reach rockslide-mountain-patrol-simulation-exp (auto) | desktop | ok | 1 | — | 0 | 126 |
| reach fart-flight-arcade-78-medium-conf-genuin (auto) | desktop | ok | 1 | — | 0 | 152 |

## Evidence and limits

- Every viewport is browser emulation (Playwright + Chromium 153.0.8010.12); iPhone sizes are CSS pixels and safe-area insets are emulated through CDP (Emulation.setSafeAreaInsetsOverride). Safari-specific rendering (WebKit), the real on-screen keyboard and physical reach are not reproduced.
- Browser chrome: the first screen is re-measured with the viewport shortened by 120 px (Safari's toolbars); dynamic toolbar collapse is not reproduced.
- Keyboard interference: fields that would zoom on focus (font-size < 16 px) are measured; whether the on-screen keyboard covers a field is not testable in emulation.
- Hover/pressed/focus states are sampled once per visual variant of control; focus visibility comes from real Tab presses (desktop).
- Canvas-drawn interfaces (games): the DOM does not describe what is drawn, so DOM-geometry metrics cover only the HTML overlay (HUD, menus); use judgements for the canvas.
- No physical-device evidence: findings are emulation results, not device results.
