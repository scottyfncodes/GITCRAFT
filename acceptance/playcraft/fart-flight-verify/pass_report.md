# PLAYCRAFT pass report

Game: **Fart Flight** · baseline 2026-11-04T21:05:33+00:00 · now 2026-11-04T21:52:18+00:00

Changed: 5 files changed, 21 insertions(+), 13 deletions(-)

## Before and after

| Category | Before | After | Change |
|---|---|---|---|
| Core gameplay | 83 | 83 | 0 |
| Game feel | 76 | 79 | +3 |
| Controls and responsiveness | 75 | 75 | 0 |
| Progression and rewards | 70 | 70 | 0 |
| Difficulty and balance | 67 | 67 | 0 |
| Player experience | 80 | 85 | +5 |
| Replayability | 70 | 70 | 0 |
| Technical gameplay quality | 73 | 73 | 0 |
| Presentation and immersion | 77 | 77 | 0 |
| Mobile experience | 82 | 87 | +5 |
| **Overall** | **75** | **77** | **+2** |

Measured on the running game (same probe, same machine):

- FPS (desktop, software rendering): 17.2 → 19.6
- FPS (phone, software rendering): 7.8 → 7.5
- fastest visible response (ms): 75 → 22
- touch response (ms): 123 → 87
- dead time during play: 0.0 → 0.0
- time to play (ms): 1179 → 1087
- page errors: 0 → 0
- missing files: 0 → 0
- input errors: 0 → 0
- probed inputs with a visible response: 9/11 → 11/11
- intermittent controls (responded in some trials only, not used for regressions): key Space (desktop), key KeyW (desktop), drag / pull back (desktop), hold centre (phone), tap right third (phone) → 

**Fixed since the baseline:**

- Effects can be calmed (reduced motion / shake setting) (inferred → now passing)
- Text is legible on the target device (≥ 12 px) (verified → now passing)
- Touch targets ≥ 44 px (verified → now passing)

No regressions detected by the probe.

**What changed and why:**

- **44 px pause button** — the in-run pause was 36x32 px on a phone (`styles.css`)
- **No text under 12 px** — the DIGNITY meter label was 10 px, menu stat labels 9 px (`styles.css`)
- **Reduced motion calms shake and flash** — accessibility without removing feedback (`src/utils.js`, `src/fx.js`, `src/game.js`)
- **44 px Sound/Music/Quit/Home/Share** — HOME and SHARE on the game-over card were 31 px tall (`styles.css`)
- **Service worker cache v14** — refresh the offline copy (`sw.js`)

**Guardrails on the diff:**

- ✅ no source files deleted (features kept): none
- ✅ deployment settings unchanged: none
- ✅ no secret files or secrets added: none
- ✅ no production data touched: none
- ✅ work is on a branch, not the default branch: claude/playcraft-pass

**Still open (top):**

- Frame rate holds during play (design, observed)
- Input forgiveness (buffering, deadzones, grace windows) (design, inferred)
- Automated tests exist (design, inferred)
- Balance is measured (simulations, solvers, playtest bots) (design, inferred)
- Frame rate on the phone viewport (design, observed)
- Control settings (sensitivity, remap, invert) (design, inferred)
- Atmosphere (lighting, fog, weather, post) (design, inferred)

