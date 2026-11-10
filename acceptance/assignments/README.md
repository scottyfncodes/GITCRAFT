# Representative assignments

What GITCRAFT does with twelve different requests, from the real entry point (`production_start`), and two of them
carried through to real output. Produced on 2026-11-10 at the commit that introduced `production/understanding.py`
and `production/direction.py`.

## What was run, and how far

| Assignment | Request | How far it was taken | Result |
|---|---|---|---|
| Improve a working game | "Improve how it plays: it feels flat and unfair. Deaths come out of nowhere, there is no sound and no way to pause." (BLIP) | **End to end**: baseline play, direction, real code changes, real QA, two failed gates fixed, release | READY. PLAYCRAFT 61 → 71, no regressions. `improve-game/` |
| Assets alone | "I need a jump sound effect and a coin pickup sound" | **End to end**: routed, both sounds made by AudioCraft, validated | two WAV + OGG pairs with provenance. `assets-alone/` |
| New game, new app, new tool | see `routing.json` | **Planned only**: read, discovered, planned with the real planner | direction first; a tool gets `qa.tests` and no icon |
| Continue a partial game, a targeted app change, a repair, an asset to integrate, a redesign | see `routing.json` | **Planned only** | each a different plan; see the table below |
| Audit, rebuild | see `routing.json` | **Planned only** | the audit has no work order; the rebuild cannot be approved until its question is answered |

"Planned only" means exactly that: the plan is real, nothing was built. A new game and a new app were **not** built in
this run.

## The twelve readings (`routing.json`)

| Request | Assignment | Decided first | Gates | Asks first |
|---|---|---|---|---|
| A cozy lighthouse keeper game… | build (game) | `design.direction` | smoke, PLAYCRAFT, PIXELCRAFT, icon, credit, standards, assets, licences, request | |
| Build a habit tracker for my phone | build (app) | `design.direction` | smoke, PIXELCRAFT, features, icon, credit, standards, request | |
| Make a CLI utility that renames photos by EXIF date | build (tool) | | `qa.tests` | |
| I need a jump sound effect and a coin pickup sound | asset | | none: two `audiocraft_sfx` steps, no production | |
| keep going (partial game) | continue | | smoke, PLAYCRAFT, PIXELCRAFT, preserve | |
| The game feels boring, make it more fun | gameplay | `baseline.playcraft`, `design.direction` | smoke, PLAYCRAFT before/after, preserve | |
| Redesign the visuals, it looks dated | redesign | `baseline.pixelcraft`, `design.direction` | smoke, PIXELCRAFT before/after, preserve | |
| The player falls through the floor sometimes | repair | | smoke, preserve | |
| Make an explosion sound and put it in the game | integrate | | smoke, preserve, assets, licences | |
| Rebuild this from scratch in Phaser | rebuild | | smoke, preserve | what may be thrown away |
| Add dark mode (finished app) | feature | | smoke, preserve | |
| Is this ready to launch? | audit | | smoke (read-only) | |

Before this change the same requests read as: an app with an icon and a maker's credit (the sounds, the texture, the
logo, the CLI); "continue building" (the falling-through-the-floor bug, "is this any good?", "rebuild from scratch",
"polish it"); and one undifferentiated "update" with advisory scores (the redesign and the gameplay pass).

## Improve a working game (`improve-game/`)

- `direction.json`: the direction written before any code. `play-pass.patch`: what changed in the game.
- `before_play.jpg`, `after_play.jpg`: PLAYCRAFT's contact sheets from the baseline and the verification (same probe).
- `after_phone_*.jpg`, `after_desktop_4_over.jpg`: the ready, playing, paused and result screens.
- `REPORT.md`: the production's report, verdict READY, with **Needs a person**.
- `ACCEPTANCE.json`: the scores per category, what was resolved, and the two gates that failed first.

What the numbers do and do not show:

- Overall 61 → 71; game feel 44 → 73; mobile 69 → 90; player experience 55 → 71; presentation 47 → 65. Controls,
  progression, difficulty, replayability and technical did not move.
- The share of strong (measured) evidence stayed at 32%. Much of the gain is PLAYCRAFT finding in the source what was
  not there before (sound, hit-stop, shake, easing). The measured parts are the pause (motion while paused), touch
  targets, `touch-action`, and no regression under the same probe.
- Nobody has played it. Whether it is more fun is the four open questions in `REPORT.md`.
- Two gates failed on the first submission and were fixed, not waived: the sounds were loaded through a built path
  instead of literal references, and the work had been done on the default branch against the work order.
