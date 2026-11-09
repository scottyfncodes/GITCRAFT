---
name: ui-design
description: Design, build or refine the interface of an app, site or game (screens, menus, HUD, title and pause screens, onboarding, settings) so it looks decided rather than generated. Explore distinct visual directions when a project has none, build with a craft floor (type, spacing, colour, layout, mobile Safari, states, motion), audit the rendered result with PIXELCRAFT (including its generic-design tells), and refine what is actually wrong. Use when asked to design, redesign, restyle, polish or "make it look good", to pick a visual direction, when a UI looks generic, templated or "AI-made", or before building new UI screens. Always defers to the project's own art direction.
---

# Interface design: Explore → Build → Audit → Refine

Load only the reference for the phase you are in: `references/explore.md`, `references/craft.md` (Build),
`references/motion.md` (any animation), `references/games.md` (any game). This file is the whole workflow.

## 0. Whose taste wins (read before anything)

1. **The person's words** in this request.
2. **The project's own identity**, wherever it lives. Look before you design:
   `CLAUDE.md`/`AGENTS.md` visual rules, art bibles and style guides (`docs/art-direction*`, `docs/brand*`, `STYLE-GUIDE.md`,
   `DESIGN.md`), tokens (`:root` CSS variables, theme files, palette JSON such as GITCRAFT's `brand/palette.json`), fonts in use,
   and anything marked retired or never-again. Retired means retired: do not bring it back.
3. An approved GITCRAFT vision (`production_vision`) and the production's identity (`foundation.identity`).
4. This skill's floor and defaults. They fill gaps; they never override 1–3.

An existing identity is **refined, never replaced**, unless the person explicitly asks for a redesign. "Polish",
"fix", "improve" and "make it better" are refinement. Never introduce a second visual language next to the first one.
There is no GITCRAFT house style: every product gets its own.

## 1. Pick the phase

| Situation | Start at |
|---|---|
| New product, no identity yet; or the person asks for a new direction or a redesign | **Explore** |
| Identity exists; new screens or features to build | **Build** (from the project's tokens and components) |
| "Does this look good?", a review, before a release | **Audit** |
| Audit or the person named concrete problems | **Refine** |

## 2. Explore (only when there is no direction to follow)

Read `references/explore.md`. In short: 2–3 directions that are genuinely different (composition, type, colour,
imagery or material: any two share at most one), each rooted in something concrete from the product's own world,
each rendered as the same real screen at phone and desktop size, shown side by side on one page
(`python3 <this skill>/scripts/directions.py <folder>`). Recommend one; the person chooses. Record the choice in
the project (`DESIGN.md`, or where it already keeps its art direction) as tokens plus a few rules, including what is
ruled out. Never pick silently for them.

## 3. Build

Read `references/craft.md` once before editing UI (and `references/motion.md` before adding animation). Build from
tokens (colour, type scale, spacing scale, radii, shadows, durations) and the project's own components; fix a component,
not each instance. Phone first: iPhone 13/17 widths, safe areas, 44 px targets, 16 px inputs, the toolbar-shrunk viewport.
Every visible state ships: hover, pressed, focus, disabled, loading, empty, error.

## 4. Audit the rendered result, not the code

1. Build or serve the app and run PIXELCRAFT (`pixelcraft_audit`, the `pixelcraft` skill). It measures spacing,
   layout, type, controls, mobile ergonomics, states, accessibility and journeys, and lists **generic design tells**
   (advisory, unscored: gradient text, violet gradients, glow halos, stripe-bordered cards, nested cards, emoji icons,
   eyebrow labels, one default sans). A tell the project chose on purpose goes in `accept_tells: [{id, reason}]`.
2. Open the screenshots (contact sheet, then the phone captures at full size) and judge what measurement cannot:
   hierarchy, whether it looks made for this product, whether one moment is memorable. Record taste problems as
   PIXELCRAFT `judgements` (screenshot evidence), never as measurements.
3. Motion: check it against `references/motion.md` in the running app, with reduced motion on and off.
4. Games: PLAYCRAFT owns how it plays and feels; PIXELCRAFT measures the HTML UI; judge the canvas from screenshots
   (`references/games.md`).

## 5. Refine, then stop

- Work the audit top-down: broken (overflow, clipping, unreachable or tiny targets, unreadable text) → usability →
  consistency → generic tells → polish. One commit per theme, in the project's conventions.
- Fix what was measured or seen. Do not restyle a working, coherent interface to taste, and do not loop:
  one refine pass, `pixelcraft_verify` against the baseline, then at most one more pass on what is still open.
  A verify that fails on a regression you caused is yours to fix before you report.
- Report before → after with the evidence (scores, resolved findings, tells resolved, screenshots), what you left
  alone on purpose, and anything that needs the person's decision.

## Tools, not dependencies

No design skill or package is installed into the project for this. Icons, marks and illustrations come from
VectorCraft (SVG in the project's stroke and palette), raster work from PhotoCraft, icons for apps from the App Icon
Studio. Fonts are self-hosted files with licences the project can ship. Sources and credits: `NOTICE.md`.
