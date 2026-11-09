# Build: the craft floor

Read once before editing UI. The project's identity overrides any default here; only accessibility and the
mobile-ergonomics lines are hard rules. Check each item on the rendered result, in one batched look, not as intentions.

## Tokens first

- Colour: ground, surface(s), text, muted text, one accent, plus state colours (danger, success) tuned to the palette.
  Secondary text on a coloured surface is a tint of that surface or of the text colour, never neutral grey.
- Type scale: a few steps with obvious ratios (e.g. 13 / 16 / 20 / 28 / 40); body 16 px on phones; line height
  ~1.45 for text, ~1.1 for display; measure 45–75 characters; letter-spacing no tighter than -0.04em on display.
- Spacing scale (4 or 8 based); tight inside a group, generous between groups, more space above a heading than below.
- Radii, borders and shadows: one family each. A shadow has an offset and a soft blur in a tint of its surface.
- Durations and easing: see `motion.md`.

## Type with a voice

- A display face that belongs to the product's world, and a text face chosen for reading; numbers in tables, scores
  and timers use tabular figures (`font-variant-numeric: tabular-nums`).
- Self-host the font files with their licence; set `font-display: swap` and size-adjusted fallbacks so text does not
  jump. The closest system font is a fallback, not a choice.
- Hierarchy from size and weight steps, not from colour alone; one h1 per screen; headings balanced (`text-wrap: balance`).

## Layout and hierarchy

- One focal point per screen. Ask what the person must see first, second, third, and make the sizes say so.
- Align to a few edges; equal left and right margins on phones (16–24 px); no orphan elements floating mid-gutter.
- Containers only where they add structure: a list does not need cards; a card never sits inside a card.
- Real content at every breakpoint: long names, empty lists, 3-digit numbers, translated strings. Fix what overflows.

## Mobile Safari (hard rules)

- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`; respect
  `env(safe-area-inset-*)` for anything pinned to an edge (tab bars, HUD buttons, toasts).
- Heights in `dvh`/`svh`, not `100vh`; the first screen still works when the toolbar takes ~120 px.
- Touch targets ≥ 44×44 px with ≥ 8 px between them; inputs ≥ 16 px font (or iOS zooms); no hover-only affordances.
- `touch-action` and `-webkit-tap-highlight-color` set deliberately; `overscroll-behavior` on scroll containers and
  game surfaces; no horizontal page scroll at 320–430 px.

## States and surfaces

- Every control: default, hover (pointer devices only, `@media (hover: hover)`), pressed, focus-visible, disabled,
  loading. Every view: loading, empty, error, success. Errors name the problem and the way out.
- The parts nobody draws still carry the design: focus rings, text selection, caret, scrollbars, link underline offset,
  placeholder colour, autofill, the browser's `theme-color`.
- Copy in the product's own voice; buttons name their action ("Log a haul", not "Submit").

## Refuse by default (the brief can earn any of these back)

Gradient text · purple/violet-to-blue gradients · glow halos as depth · glass and blur as decoration · a 3 px+ coloured
stripe down one side of cards or alerts · cards in cards · three equal icon-tile cards as page structure · an eyebrow
label over every heading · numbered sections (01/02/03) that carry no order · emoji as an icon system · one default sans
for everything · monospace as a "technical" costume · a modal where inline would do · hard zero-blur offset shadows
outside a world that chose them. PIXELCRAFT raises the measurable ones as tells.

## Accessibility (hard rules)

Contrast ≥ 4.5:1 for text, ≥ 3:1 for large text and UI boundaries; visible focus; labels on inputs; alt text; respects
`prefers-reduced-motion` and `prefers-color-scheme` where the product supports both; nothing conveyed by colour alone.
