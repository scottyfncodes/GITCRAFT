# PLAYCRAFT assessment: TIDEBREAKERS

> A mobile-first, stylized 3D survival adventure on a flooded Earth, built for iPhone Safari and Home Screen install.
The look is Waterworld-inspired ocean survival: everything salvaged, patched and fought over, scrap atolls and outposts
in an immense dark sea, and **green means alive**: living plants are the rarest, most valuable thing in the world
(see `docs/waterworld-pass/`, and `docs/grimy-pass/` for the weathering foundation).
Civilization is under the sea. You start in a patchwork skiff at 

**Genres:** Survival (100%), Exploration / adventure (83%)
**Engine:** three.js  ·  **Mobile:** yes  ·  **Played:** yes, desktop, phone

## Overall: 76/100 · confidence low · coverage 100% · strong evidence 28%

_Low confidence: much of this rests on source evidence; record judgements from playing (playcraft_assess judgements) and point `evidence` at the project's own test reports._

| Category | Score | Confidence | Evidence (verified/observed/inferred/not tested) |
|---|---|---|---|
| Core gameplay | 83 `████████░░` | medium | 2/0/4/0 |
| Game feel | 76 `████████░░` | low | 0/1/8/0 |
| Controls and responsiveness | 76 `████████░░` | medium | 2/0/3/0 |
| Progression and rewards | 70 `███████░░░` (capped: inferred only) | low | 0/0/6/0 |
| Difficulty and balance | 65 `██████░░░░` | low | 0/0/5/0 |
| Player experience | 57 `██████░░░░` | low | 1/1/7/2 |
| Replayability | 70 `███████░░░` (capped: inferred only) | low | 0/0/5/0 |
| Technical gameplay quality | 92 `█████████░` | high | 3/0/2/1 |
| Presentation and immersion | 81 `████████░░` | low | 1/1/6/0 |
| Mobile experience | 89 `█████████░` | high | 6/0/3/1 |

Evidence levels: **verified** = measured on the running game by an automated check; **observed** = seen in the running game (approximate, or recorded by the player); **inferred** = from source/docs only; **not tested** = no evidence, not scored.

## What matters for this game

- **Survival**: survival tension from real resource pressure; scarcity that forces choices; exploration that pays off; environmental storytelling; meaningful navigation (landmarks, not just markers); fair, telegraphed failure
- **Exploration / adventure**: traversal that feels good on its own; landmarks and curiosity; discoveries that are logged and rewarded; a world that reacts; secrets

## Highest-impact opportunities (7 total)

1. **Playable quickly (load + start ≤ 3 s)** — design, player experience, observed · impact 4/5 · effort 3/5 · risk 1/3
   - Evidence: 8045 ms from navigation to playing (load 434 ms + start 7611 ms; served locally)
   - Do: Cut time to first play: show the start screen immediately, load heavy assets in the background.
2. **Text is legible on the target device (≥ 12 px)** — design, player experience, verified · impact 3/5 · effort 1/5 · risk 1/3
   - Evidence: smallest visible text 9 px ('CATALOG') on phone
   - Do: Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).
3. **Input forgiveness (buffering, deadzones, grace windows)** — design, controls, inferred · impact 3/5 · effort 2/5 · risk 1/3
   - Evidence: not found in source: input_buffer, deadzone
   - Do: Buffer inputs pressed slightly early and add small grace windows; precise games feel fairer with them.
4. **Balance is measured (simulations, solvers, playtest bots)** — design, difficulty, inferred · impact 3/5 · effort 3/5 · risk 1/3
   - Evidence: not found in source: tune_tests
   - Do: Add a headless simulation/bot test that measures failure rate and pacing; balance by data, not by feel alone.
5. **Browser gestures do not fight the game (touch-action, no zoom)** — design, mobile, verified · impact 3/5 · effort 1/5 · risk 1/3
   - Evidence: play surface touch-action: auto; viewport: width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover
   - Do: Set touch-action: none on the play surface (and disable double-tap zoom) so swipes and pinches go to the game.
6. **Effects can be calmed (reduced motion / shake setting)** — design, game feel, inferred · impact 2/5 · effort 1/5 · risk 1/3
   - Evidence: not found in source: reduced_motion
   - Do: Honour prefers-reduced-motion and offer a shake/flash toggle; juice must never cost readability.
7. **More than one input method (keyboard + pointer/touch, gamepad)** — design, controls, inferred · impact 3/5 · effort 2/5 · risk 1/3
   - Evidence: found input_keyboard, input_pointer (creative/3d/integration/chestGLB.ts:40: return [...templates.keys()];; creative/3d-characters/scripts/optimize_char.mjs:1: // Mobile delivery pass for skinned characters: keep smooth NORMALs, 8-bit RGB COLOR_0, resample animation key)
   - Do: Support keyboard and pointer/touch for the same actions; add gamepad if the genre expects it.

## Implementation plan

**2. High-impact, low-effort feel and flow** — biggest player-visible gain for the least risk; each is reversible

- [playcraft] Text is legible on the target device (≥ 12 px) → Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).
- [playcraft] Input forgiveness (buffering, deadzones, grace windows) → Buffer inputs pressed slightly early and add small grace windows; precise games feel fairer with them.
- [playcraft] Browser gestures do not fight the game (touch-action, no zoom) → Set touch-action: none on the play surface (and disable double-tap zoom) so swipes and pinches go to the game.
- [playcraft] More than one input method (keyboard + pointer/touch, gamepad) → Support keyboard and pointer/touch for the same actions; add gamepad if the genre expects it.

**3. Deeper design work** — bigger changes: prototype behind a flag or in a branch and re-run PLAYCRAFT verify

- [playcraft] Playable quickly (load + start ≤ 3 s) → Cut time to first play: show the start screen immediately, load heavy assets in the background.
- [playcraft] Balance is measured (simulations, solvers, playtest bots) → Add a headless simulation/bot test that measures failure rate and pacing; balance by data, not by feel alone.

## Disciplines

### Game Design Architect

- ✅ The intended experience is stated (pitch / how it plays) — _inferred_: A mobile-first, stylized 3D survival adventure on a flooded Earth, built for iPhone Safari and Home Screen install.
The look is Waterworld-inspired ocean survival: everything salvaged, patched and fought over, scrap atolls and outposts
in a…
- ✅ Clear player objectives — _inferred_: found levels, game_over, highscore, stars
- ✅ Meaningful decisions (choices with trade-offs) — _inferred_: found upgrades, input_drag, currency, unlocks
- ✅ Resource pressure exists — _inferred_: found survival_resources

Questions to answer by playing:
- What is the core concept in one sentence, and is it this game's own?
- What is the primary loop, and what secondary loops feed it?
- Where does the player make a meaningful decision, and how often?
- Is the depth earned, or is complexity standing in for depth?
- Does the game have a compelling reason to exist next to its genre's best?
- What does the player have to give up to get what they need? If nothing, there is no tension.
- Does the world tell its story through places and finds?

### Game Feel Engineer

- ✅ Actions are acknowledged on screen within ~100 ms — _observed_: fastest visible response 797 ms after the input (median 821 ms; one frame here is 866.7 ms, so ≤ 1733 ms passes)
- ✅ Camera/screen shake for big impacts — _inferred_: found screen_shake
- ✅ Hit-stop / slow motion on key moments — _inferred_: found hitstop
- ✅ Particles on interactions — _inferred_: found particles
- ✅ Motion is eased (tweens, lerps, springs), not linear — _inferred_: found easing
- ✅ Anticipation, recoil, squash and stretch — _inferred_: found squash
- ✅ Sound effects on actions — _inferred_: found audio
- ✅ Rewards are announced where they happen — _inferred_: found popups
- ❌ Effects can be calmed (reduced motion / shake setting) — _inferred_: not found in source: reduced_motion
- ✅ Haptics on key moments (where supported) — _inferred_: found haptics

Questions to answer by playing:
- Does every press produce an immediate, visible acknowledgement?
- Do movement and collisions have weight (acceleration, impact, recovery)?
- Is feedback proportional (a big event feels bigger than a small one)?
- Is anything overdone (shake on every event, particle soup)?

### Gameplay Loop Designer

- ✅ Playing changes the game (inputs move the game state) — _verified_: 10/10 probed inputs changed the screen
- ✅ Game state advances during play (exposed numbers change) — _verified_: changed during play: __game.atmo.flashT, __game.atmo.sunIntensity, __game.boat.heading, __game.cacheTimer, __game.goalTimer, __game.islandTimer, __game.proxTimer, __game.raiders.boltLife
- ⬜ Little dead time during play — _not_tested_: the probe could not measure this

Questions to answer by playing:
- What is the player doing every 5 seconds?
- What keeps them engaged after 60 seconds?
- What makes them want to play for 10 minutes?
- What creates longer-term motivation?
- Where does repetition become boredom?
- Where is the mastery?
- Is there a moment every few minutes where the player must decide to push further or turn back?
- What makes the player turn off the road? Can they see something interesting from where they stand?

### Progression Architect

- ✅ Progress is saved — _inferred_: found save
- ✅ Unlocks or upgrades that change play — _inferred_: found unlocks, upgrades
- ✅ Long-term goals (achievements, collections, ranks) — _inferred_: found achievements, collectibles, stars
- ✅ No generic retention systems bolted on — _inferred_: none of: daily_reward, battle_pass, energy_gate, lootbox
- ✅ Exploration pays off (discoveries, finds, catalogue) — _inferred_: found exploration, collectibles
- ✅ Discoveries are logged (catalogue, journal, map) — _inferred_: found pattern

Questions to answer by playing:
- What does the player unlock, and does it change how they play?
- Is the reward cadence felt (not too sparse, not confetti for nothing)?
- Does progression come from the game itself rather than a bolted-on meta?

### Player Experience Designer

- ❌ Playable quickly (load + start ≤ 3 s) — _observed_: 8045 ms from navigation to playing (load 434 ms + start 7611 ms; served locally)
- ✅ Onboarding teaches by doing (hints, first-run guidance) — _inferred_: found tutorial
- ⬜ Pause works, and the game pauses when hidden — _not_tested_: the probe could not measure this
- ✅ Auto-pause when the page is hidden — _inferred_: found visibility_pause
- ✅ Restart friction is low — _inferred_: found restart
- ❌ Text is legible on the target device (≥ 12 px) — _verified_: smallest visible text 9 px ('CATALOG') on phone
- ✅ Accessibility (reduced motion, ARIA, contrast, subtitles, mute) — _inferred_: found aria, subtitles, mute
- ✅ Failure is telegraphed (low-resource warnings) — _inferred_: found pattern
- ✅ Navigation aids (map, compass, landmarks) — _inferred_: found pattern
- ✅ Map / orientation — _inferred_: found pattern

Questions to answer by playing:
- Can a first-time player start and understand the goal without reading?
- Is the HUD readable at a glance on the target device?
- How fast is a restart after failure?
- Is the game accessible (motion, contrast, audio, text size)?
- Can the player navigate by landmarks and the map, or only by following a marker?

### Control & Device Specialist

- ✅ Each probed control produces a visible response — _verified_: 5/5 desktop inputs responded
- 🟡 More than one input method (keyboard + pointer/touch, gamepad) — _inferred_: found input_keyboard, input_pointer
- ❌ Input forgiveness (buffering, deadzones, grace windows) — _inferred_: not found in source: input_buffer, deadzone
- ✅ Control settings (sensitivity, remap, invert) — _inferred_: found input_remap
- ✅ Inputs never throw errors — _verified_: no errors while inputs were played
- ✅ Game loads on every tested viewport — _verified_: loaded on desktop, phone
- ✅ No runtime errors during play — _verified_: 0 page errors (console errors: 1)
- ✅ No missing files — _verified_: no missing files
- ⬜ Frame rate holds during play — _not_tested_: not representative: the browser rendered on ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver) (software), measured 1.1 fps; identical builds vary 2-3x between runs here. Test frame rate on a real d…
- ✅ Frame-rate-independent update (dt clamp / fixed step) — _inferred_: found dt_clamp
- ✅ Automated tests exist — _inferred_: found tests
- ✅ Renders on a phone viewport — _verified_: 1474
- ✅ Touch input responds — _verified_: 5/5 touch gestures changed the screen; fastest 595 ms
- ✅ Viewport meta set for phones — _verified_: width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover
- ✅ Touch targets ≥ 44 px — _verified_: all 7 visible controls ≥ 44 px
- ✅ No horizontal overflow on phones — _verified_: no horizontal overflow
- 🟡 Browser gestures do not fight the game (touch-action, no zoom) — _verified_: play surface touch-action: auto; viewport: width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover
- ✅ Safe areas respected (notch, home bar) — _inferred_: found safe_area
- ✅ Orientation handled — _inferred_: found orientation
- ⬜ Frame rate on the phone viewport — _not_tested_: not representative: the browser rendered on ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver) (software), measured 1.9 fps; identical builds vary 2-3x between runs here. Test frame rate on a real d…

Questions to answer by playing:
- Do controls respond within a frame or two on every target device?
- Are touch targets big enough and out of the thumb's way of the view?
- Does the game work in the orientation people hold the phone?

### Difficulty & Balance Specialist

- ✅ Difficulty progresses (levels, waves, ramp) — _inferred_: found ramp, levels, difficulty
- ✅ Tuning values are centralised — _inferred_: found tuning_config
- ❌ Balance is measured (simulations, solvers, playtest bots) — _inferred_: not found in source: tune_tests
- ✅ Failure has a recovery path (retry, checkpoint, respawn) — _inferred_: found restart
- ✅ Assist / difficulty options — _inferred_: found difficulty

Questions to answer by playing:
- How often does a player fail, and is each failure their fault?
- Where are the spikes?
- What is the dominant strategy or exploit?
- Can the player run out of the critical resource, and do they see it coming?
- Is the early game too generous (no pressure) or too punishing (death before learning)?

### Retention & Replayability Designer

- ✅ Variation between sessions (randomness, procedural content) — _inferred_: found randomness, procedural
- ✅ Mastery goals (best scores, ratings, records) — _inferred_: found highscore, stars
- ✅ Player expression (customisation, sandbox, styles) — _inferred_: found customization, sandbox_mode
- ✅ Shareable moments (share, replay, daily seed) — _inferred_: found share
- ✅ Secrets and hidden things — _inferred_: found collectibles

Questions to answer by playing:
- Why would someone play again tomorrow, legitimately?
- What is different next time (randomness, mastery, expression)?
- Is there a moment worth sharing?

### Presentation & Immersion

- ✅ Sound design and music — _inferred_: found audio, music
- ✅ Animation — _inferred_: found animation
- ✅ Atmosphere (lighting, fog, weather, post) — _inferred_: found atmosphere
- ✅ Transitions between screens and states — _inferred_: found transitions
- ✅ The world moves when the player is idle — _observed_: share of the screen changing per frame with no input: 0.28672
- ✅ Screens have visual range (not blank or flat) — _verified_: {"desktop": 1060, "phone": 1474}
- ✅ Day/night or weather that changes play — _inferred_: found day_night
- ✅ Environmental storytelling — _inferred_: found storytelling

Questions to answer by playing:
- Does the world feel alive when the player stands still?
- Do audio, animation and camera agree with what is happening?
- Are transitions and pacing deliberate?
- Does the world move and react (wind, wildlife, weather) when the player stands still?


_GITCRAFT PLAYCRAFT 1.0.0 · 2026-11-04T22:45:13+00:00_
