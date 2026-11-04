# PLAYCRAFT acceptance: real games

Every run below was made from the game's own repository, with GITCRAFT not attached and no GITCRAFT
variables set. Each one started the user-scope `studiocraft` registration (`~/.gitcraft/runtime`), exactly as
Claude Code does in any project, via `tests/acceptance_playcraft.py <repo> <build>`. The builds came from each
game's own toolchain (`npm run build` / `pnpm build`; Fart Flight is static). Each folder holds the report, the
probe's contact sheet (what the game looked like while it was played) and `ACCEPTANCE.json`.

| Game | Genres detected | Engine | Played (desktop + iPhone 13) | Overall | Notable verified findings |
|---|---|---|---|---|---|
| DEMO DAY | physics puzzle, sports (golf) | three.js | START → golf tee; SEAM SHOT landed on the phone | 76 (medium) | every probed control responds; pause verified; one 12×2 hidden label wrongly counted as a target (fixed in PLAYCRAFT) |
| TIDEBREAKERS | survival, exploration | three.js | SET SAIL → LET’S GO → sailing (in-game clock advanced, boat turned) | see report | smallest text 9 px (`CATALOG`) on the phone |
| ROCKSLIDE | simulation, exploration (+ physics puzzle, sports) | three.js + Rapier (deterministic) | lodge → patrol | 76 (low) | smallest text 8.5 px (`Map`); pause verified |
| Fart Flight (before) | arcade | Canvas 2D | FART → runs, crashes, game-over cards | 75 (medium) | pause 36×32 px, HOME/SHARE 31 px, DIGNITY label 10 px |
| Fart Flight (after, merged) | arcade | Canvas 2D | same | 78 (medium) | those resolved; verify: no reproducible regressions, guardrails clean |

## The improvement pass (Fart Flight, PR scottyfncodes/Fart-Flight#30, merged)

`fart-flight-verify/pass_report.md` is the before/after report, and `phone_after.png` shows the changed screens.
The changes are a 44 px pause button, 44 px Sound/Music/Quit/Home/Share buttons, no text under 12 px, and
reduced motion that calms the shake and flashes rather than removing them. Verify replays the game with the
baseline's probe. It confirms noise-prone regressions with a second replay, and it checks the git diff for
deleted source, deployment, secret and data changes.

## What these runs taught PLAYCRAFT (fixed during the build)

- Software-rendered FPS is not representative. Identical Fart Flight builds measured 10.4 and 26.1 fps back to
  back. On SwiftShader, FPS is now shown but not scored, and verify never fails on it.
- Some controls respond only intermittently to a generic probe. A short drag on Fart Flight responded in 1/12
  and 3/12 trials on identical builds. Verify now requires a control to have responded in every baseline trial
  before it can count as "lost".
- Latency is quantised by the frame time. At about 8 fps one frame is 125 ms, so a latency regression must
  exceed two frames.
- Title screens lead to intro cards. The probe now follows a chain of start prompts, including `LET’S GO`
  with a typographic apostrophe. Before this fix, the first TIDEBREAKERS run evaluated the intro card, not
  sailing. That was caught by looking at the contact sheet.
- Games read keys as properties (`keys.ArrowRight`), teach controls with prompts (`HOLD TO FART`), and clamp
  dt with `Math.min(0.05, …)`. Discovery recognises all three now.
- Game-over cards have their own buttons, so touch targets are audited after play too.

## Limits seen here

The three 3D games render at 1–5 fps in headless software WebGL. Their play evidence covers reaching play,
control response, pause and the DOM (targets, text). It does not cover feel at speed. The probe plays
generically and never plays to win: level completion and balance need the games' own playtests passed as
`evidence`, or recorded `judgements`.
