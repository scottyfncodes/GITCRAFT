# Game Quality History: acceptance screenshots

These iPhone 13 screenshots (Playwright device emulation) were taken from the deployed Vercel preview of this
branch (`meshcraft-ex6g5cbb3-haveanapp.vercel.app/games/`). That preview was built by the unchanged Vercel build
command (`forgecraft/ui_server.py --publish`) from the committed archive `history/playcraft/`.

The archive holds 21 recorded PLAYCRAFT runs of DEMO DAY, TIDEBREAKERS, ROCKSLIDE and Fart Flight. They come from:

- **Imported cards:** the PLAYCRAFT build session's own runs.
- **Fresh passes:** run from each game's own folder through the user-scope studiocraft and recorded automatically,
  including a repeat on the same commit to measure noise.
- **Re-measurements:** each baseline commit re-assessed with the current PLAYCRAFT, as the controlled comparison.

The archive also holds events: main heads (`git ls-remote`), ROCKSLIDE and TIDEBREAKERS deployments live-verified
against builds of their main commits, Fart Flight deploy-reported from its Pages run, and Fart Flight PR #30.
DEMO DAY's deployment was refused for lack of evidence.

- `iphone-preview.jpg`: the portfolio, Fart Flight (genuine improvement), ROCKSLIDE (within noise) and
  TIDEBREAKERS (code changed, unverified).
- `*-top.jpg` / `*-mid.jpg`: the individual screens.
