# Motion

Motion explains change: where something came from, what responded, what state it is in. Values below are starting
points from Emil Kowalski's published standards (see NOTICE.md); a project's own motion tokens win.

## Should it move at all?

| How often it is seen | Motion |
|---|---|
| Hundreds of times a day (keyboard shortcuts, list navigation, a HUD counter ticking) | none, or instant |
| Tens of times (hover, tabs, toggles) | minimal: colour/opacity, ≤ 150 ms |
| Occasionally (sheets, dialogs, toasts, menus) | standard: 180–300 ms |
| Rarely (first run, a level cleared, a purchase, a record) | the one authored moment; can be longer and richer |

One memorable moment per product beats an entrance animation on every section. Never animate keyboard-initiated actions.

## Curves and durations

- Entering/exiting: ease-out. Moving on screen: ease-in-out. Colour/hover: ease. Constant motion: linear.
  Never ease-in for UI. Built-in curves are weak; use tokens such as
  `--ease-out: cubic-bezier(.23, 1, .32, 1)`, `--ease-in-out: cubic-bezier(.77, 0, .175, 1)`,
  `--ease-sheet: cubic-bezier(.32, .72, 0, 1)`.
- Press feedback 100–160 ms; tooltips 125–200 ms; menus 150–250 ms; dialogs and sheets 200–400 ms. UI motion stays
  under ~300 ms unless it is the authored moment.
- Asymmetric: slow where the person decides (hold-to-confirm), fast where the system answers (release, dismiss).

## Physical, interruptible, cheap

- Nothing appears from `scale(0)`: start at 0.95–0.97 with opacity 0. Popovers scale from their trigger
  (`transform-origin`); dialogs from the centre.
- Pressables: `transform: scale(.97)` on `:active` with a ~150 ms transition.
- Use transitions (interruptible) for anything that can be re-triggered; keyframes for one-shot sequences;
  `@starting-style` for entry without JavaScript. Springs (bounce 0.1–0.3) for drag and gestures; momentum dismiss by
  velocity, with resistance past an edge.
- Animate `transform`, `opacity` (and, sparingly, `clip-path`, `filter`); never `width`/`height`/`top`/`left`/`margin`.
  Set transforms on the moving element, not through a CSS variable on its parent. Keep blur under ~20 px (Safari).
- Stagger lists by 30–60 ms, capped so the last item lands within ~400 ms.

## Always

- `@media (prefers-reduced-motion: reduce)`: replace movement with a short fade or nothing; keep the state change visible.
- Check on a phone-sized viewport and with CPU throttling; a dropped frame on a button press is worse than no animation.
- Games: game-feel motion (hit-stop, screen shake, squash, camera) is PLAYCRAFT's territory and the game's identity;
  apply this file to its HTML menus, HUD panels and transitions between them.
