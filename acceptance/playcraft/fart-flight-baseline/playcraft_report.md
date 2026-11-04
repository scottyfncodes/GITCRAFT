# PLAYCRAFT assessment: Fart Flight

> He has gas. He has a dream.

**Genres:** Arcade (100%)
**Engine:** Canvas 2D (no engine)  ·  **Mobile:** yes  ·  **Played:** yes, desktop, phone

## Overall: 75/100 · confidence medium · coverage 100% · strong evidence 32%

| Category | Score | Confidence | Evidence (verified/observed/inferred/not tested) |
|---|---|---|---|
| Core gameplay | 83 `████████░░` | medium | 1/0/3/1 |
| Game feel | 76 `████████░░` | low | 0/1/10/0 |
| Controls and responsiveness | 75 `████████░░` | medium | 2/0/3/0 |
| Progression and rewards | 70 `███████░░░` (capped: inferred only) | low | 0/0/4/0 |
| Difficulty and balance | 67 `███████░░░` | low | 0/0/6/0 |
| Player experience | 80 `████████░░` | medium | 2/2/5/0 |
| Replayability | 70 `███████░░░` (capped: inferred only) | low | 0/0/5/0 |
| Technical gameplay quality | 73 `███████░░░` | high | 3/1/2/0 |
| Presentation and immersion | 77 `████████░░` | medium | 1/1/4/0 |
| Mobile experience | 82 `████████░░` | high | 6/1/3/0 |

Evidence levels: **verified** = measured on the running game by an automated check; **observed** = seen in the running game (approximate, or recorded by the player); **inferred** = from source/docs only; **not tested** = no evidence, not scored.

## What matters for this game

- **Arcade**: instant restart; readable score and near-miss feedback; tight, immediate controls; a difficulty ramp you can feel; one more go

## Highest-impact opportunities (10 total)

1. **Frame rate holds during play** — design, technical, observed · impact 4/5 · effort 3/5 · risk 1/3
   - Evidence: 17.2 fps, p95 100 ms (headless, software WebGL: real GPUs are faster)
   - Do: Frame rate drops during play; profile the hot path (draw calls, allocations per frame).
2. **Input forgiveness (buffering, deadzones, grace windows)** — design, controls, inferred · impact 3/5 · effort 2/5 · risk 1/3
   - Evidence: not found in source: input_buffer, deadzone
   - Do: Buffer inputs pressed slightly early and add small grace windows; precise games feel fairer with them.
3. **Effects can be calmed (reduced motion / shake setting)** — design, game feel, inferred · impact 2/5 · effort 1/5 · risk 1/3
   - Evidence: not found in source: reduced_motion
   - Do: Honour prefers-reduced-motion and offer a shake/flash toggle; juice must never cost readability.
4. **Automated tests exist** — design, technical, inferred · impact 3/5 · effort 2/5 · risk 1/3
   - Evidence: not found in source: tests
   - Do: Add tests for the rules that matter to play (scoring, physics limits, saves).
5. **Balance is measured (simulations, solvers, playtest bots)** — design, difficulty, inferred · impact 3/5 · effort 3/5 · risk 1/3
   - Evidence: not found in source: tune_tests
   - Do: Add a headless simulation/bot test that measures failure rate and pacing; balance by data, not by feel alone.
6. **Frame rate on the phone viewport** — design, mobile, observed · impact 3/5 · effort 3/5 · risk 1/3
   - Evidence: 7.8 fps on the phone viewport (software rendering)
   - Do: The phone viewport ran slowly; test on a real device and reduce per-frame cost.
7. **Text is legible on the target device (≥ 12 px)** — design, player experience, verified · impact 3/5 · effort 1/5 · risk 1/3
   - Evidence: smallest visible text 10 px ('DIGNITY') on phone
   - Do: Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).
8. **Control settings (sensitivity, remap, invert)** — design, controls, inferred · impact 2/5 · effort 2/5 · risk 1/3
   - Evidence: not found in source: sensitivity, input_remap
   - Do: Offer sensitivity and (for keyboards) remapping.
9. **Touch targets ≥ 44 px** — design, mobile, verified · impact 3/5 · effort 1/5 · risk 1/3
   - Evidence: [{"text": "II", "w": 36, "h": 32}]
   - Do: Enlarge the listed touch targets to at least 44×44 CSS px (Apple HIG) and keep them clear of each other.
10. **Atmosphere (lighting, fog, weather, post)** — design, presentation, inferred · impact 2/5 · effort 3/5 · risk 1/3
   - Evidence: not found in source: atmosphere
   - Do: Use light, fog and weather to set mood and to guide the eye.

## Implementation plan

**2. High-impact, low-effort feel and flow** — biggest player-visible gain for the least risk; each is reversible

- [playcraft] Input forgiveness (buffering, deadzones, grace windows) → Buffer inputs pressed slightly early and add small grace windows; precise games feel fairer with them.
- [playcraft] Automated tests exist → Add tests for the rules that matter to play (scoring, physics limits, saves).
- [playcraft] Text is legible on the target device (≥ 12 px) → Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).
- [playcraft] Touch targets ≥ 44 px → Enlarge the listed touch targets to at least 44×44 CSS px (Apple HIG) and keep them clear of each other.

**3. Deeper design work** — bigger changes: prototype behind a flag or in a branch and re-run PLAYCRAFT verify

- [playcraft] Frame rate holds during play → Frame rate drops during play; profile the hot path (draw calls, allocations per frame).
- [playcraft] Balance is measured (simulations, solvers, playtest bots) → Add a headless simulation/bot test that measures failure rate and pacing; balance by data, not by feel alone.
- [playcraft] Frame rate on the phone viewport → The phone viewport ran slowly; test on a real device and reduce per-frame cost.

## Disciplines

### Game Design Architect

- ✅ The intended experience is stated (pitch / how it plays) — _inferred_: He has gas. He has a dream.
- ✅ Clear player objectives — _inferred_: found levels, game_over, highscore, stars
- ✅ Meaningful decisions (choices with trade-offs) — _inferred_: found input_drag, unlocks

Questions to answer by playing:
- What is the core concept in one sentence, and is it this game's own?
- What is the primary loop, and what secondary loops feed it?
- Where does the player make a meaningful decision, and how often?
- Is the depth earned, or is complexity standing in for depth?
- Does the game have a compelling reason to exist next to its genre's best?

### Game Feel Engineer

- ✅ Actions are acknowledged on screen within ~100 ms — _observed_: fastest visible response 75 ms after the input (median 119.0 ms; one frame here is 50 ms, so ≤ 100 ms passes)
- ✅ Camera/screen shake for big impacts — _inferred_: found screen_shake
- ✅ Hit-stop / slow motion on key moments — _inferred_: found hitstop
- ✅ Particles on interactions — _inferred_: found particles
- ✅ Motion is eased (tweens, lerps, springs), not linear — _inferred_: found easing
- ✅ Anticipation, recoil, squash and stretch — _inferred_: found squash
- ✅ Sound effects on actions — _inferred_: found audio
- ✅ Rewards are announced where they happen — _inferred_: found popups
- ❌ Effects can be calmed (reduced motion / shake setting) — _inferred_: not found in source: reduced_motion
- ✅ Haptics on key moments (where supported) — _inferred_: found haptics
- ✅ Near-miss / close-call feedback — _inferred_: found pattern
- ✅ Score changes are celebrated where the player looks — _inferred_: found pattern

Questions to answer by playing:
- Does every press produce an immediate, visible acknowledgement?
- Do movement and collisions have weight (acceleration, impact, recovery)?
- Is feedback proportional (a big event feels bigger than a small one)?
- Is anything overdone (shake on every event, particle soup)?
- Does a near-miss feel like a near-miss (slow-mo, sound, callout)?
- Is every point scored visible where the eye already is?

### Gameplay Loop Designer

- ✅ Playing changes the game (inputs move the game state) — _verified_: 9/11 probed inputs changed the screen
- ⬜ Game state advances during play (exposed numbers change) — _not_tested_: the probe could not measure this
- ✅ Little dead time during play — _observed_: 0% of frames unchanged during 8.5 s of mixed inputs

Questions to answer by playing:
- What is the player doing every 5 seconds?
- What keeps them engaged after 60 seconds?
- What makes them want to play for 10 minutes?
- What creates longer-term motivation?
- Where does repetition become boredom?
- Where is the mastery?
- How many seconds from death to playing again?
- What changes between minute 1 and minute 3 of a run?

### Progression Architect

- ✅ Progress is saved — _inferred_: found save
- ✅ Unlocks or upgrades that change play — _inferred_: found unlocks
- ✅ Long-term goals (achievements, collections, ranks) — _inferred_: found achievements, collectibles, stars
- ✅ No generic retention systems bolted on — _inferred_: none of: daily_reward, battle_pass, energy_gate, lootbox

Questions to answer by playing:
- What does the player unlock, and does it change how they play?
- Is the reward cadence felt (not too sparse, not confetti for nothing)?
- Does progression come from the game itself rather than a bolted-on meta?

### Player Experience Designer

- ✅ Playable quickly (load + start ≤ 3 s) — _observed_: 1179 ms from navigation to playing (load 166 ms + start 1013 ms; served locally)
- ✅ Onboarding teaches by doing (hints, first-run guidance) — _inferred_: found tutorial
- ✅ Pause works, and the game pauses when hidden — _verified_: Escape: motion 0.0547 → 0.0126 while paused
- ✅ Auto-pause when the page is hidden — _inferred_: found visibility_pause
- ✅ Restart friction is low — _inferred_: found restart
- 🟡 Text is legible on the target device (≥ 12 px) — _verified_: smallest visible text 10 px ('DIGNITY') on phone
- ✅ Accessibility (reduced motion, ARIA, contrast, subtitles, mute) — _inferred_: found aria, subtitles, mute
- ✅ Instant restart after failure — _inferred_: found restart

Questions to answer by playing:
- Can a first-time player start and understand the goal without reading?
- Is the HUD readable at a glance on the target device?
- How fast is a restart after failure?
- Is the game accessible (motion, contrast, audio, text size)?

### Control & Device Specialist

- ✅ Each probed control produces a visible response — _verified_: 6/6 desktop inputs responded
- ✅ More than one input method (keyboard + pointer/touch, gamepad) — _inferred_: found input_keyboard, input_pointer, input_touch
- ❌ Input forgiveness (buffering, deadzones, grace windows) — _inferred_: not found in source: input_buffer, deadzone
- ❌ Control settings (sensitivity, remap, invert) — _inferred_: not found in source: sensitivity, input_remap
- ✅ Inputs never throw errors — _verified_: no errors while inputs were played
- ✅ Game loads on every tested viewport — _verified_: loaded on desktop, phone
- ✅ No runtime errors during play — _verified_: 0 page errors (console errors: 1)
- ✅ No missing files — _verified_: no missing files
- ❌ Frame rate holds during play — _observed_: 17.2 fps, p95 100 ms (headless, software WebGL: real GPUs are faster)
- ✅ Frame-rate-independent update (dt clamp / fixed step) — _inferred_: found fixed_step, dt_clamp
- ❌ Automated tests exist — _inferred_: not found in source: tests
- ✅ Renders on a phone viewport — _verified_: 1143
- ✅ Touch input responds — _verified_: 3/5 touch gestures changed the screen; fastest 123 ms
- ✅ Viewport meta set for phones — _verified_: width=device-width, initial-scale=1, maximum-scale=1, minimum-scale=1, user-scalable=no, viewport-fit=cover
- 🟡 Touch targets ≥ 44 px — _verified_: [{"text": "II", "w": 36, "h": 32}]
- ✅ No horizontal overflow on phones — _verified_: no horizontal overflow
- ✅ Browser gestures do not fight the game (touch-action, no zoom) — _verified_: play surface touch-action: none; viewport: width=device-width,initial-scale=1,maximum-scale=1,minimum-scale=1,user-scalable=no,viewport-fit=cover
- ✅ Safe areas respected (notch, home bar) — _inferred_: found safe_area
- ✅ Orientation handled — _inferred_: found orientation
- ❌ Frame rate on the phone viewport — _observed_: 7.8 fps on the phone viewport (software rendering)

Questions to answer by playing:
- Do controls respond within a frame or two on every target device?
- Are touch targets big enough and out of the thumb's way of the view?
- Does the game work in the orientation people hold the phone?

### Difficulty & Balance Specialist

- ✅ Difficulty progresses (levels, waves, ramp) — _inferred_: found ramp, levels, difficulty
- ✅ Tuning values are centralised — _inferred_: found tuning_config
- ❌ Balance is measured (simulations, solvers, playtest bots) — _inferred_: not found in source: tune_tests
- ✅ Failure has a recovery path (retry, checkpoint, respawn) — _inferred_: found restart
- ✅ Assist / difficulty options — _inferred_: found assist, difficulty
- ✅ Difficulty ramps within a run — _inferred_: found ramp

Questions to answer by playing:
- How often does a player fail, and is each failure their fault?
- Where are the spikes?
- What is the dominant strategy or exploit?

### Retention & Replayability Designer

- ✅ Variation between sessions (randomness, procedural content) — _inferred_: found randomness
- ✅ Mastery goals (best scores, ratings, records) — _inferred_: found highscore, stars
- ✅ Player expression (customisation, sandbox, styles) — _inferred_: found customization
- ✅ Shareable moments (share, replay, daily seed) — _inferred_: found share
- ✅ Persistent best score — _inferred_: found highscore, save

Questions to answer by playing:
- Why would someone play again tomorrow, legitimately?
- What is different next time (randomness, mastery, expression)?
- Is there a moment worth sharing?
- Is the best score always in view? Is there a reason to beat it (unlock, rank, grade)?

### Presentation & Immersion

- ✅ Sound design and music — _inferred_: found audio, music
- ✅ Animation — _inferred_: found animation
- ❌ Atmosphere (lighting, fog, weather, post) — _inferred_: not found in source: atmosphere
- ✅ Transitions between screens and states — _inferred_: found transitions
- ✅ The world moves when the player is idle — _observed_: share of the screen changing per frame with no input: 0.00878
- ✅ Screens have visual range (not blank or flat) — _verified_: {"desktop": 678, "phone": 1143}

Questions to answer by playing:
- Does the world feel alive when the player stands still?
- Do audio, animation and camera agree with what is happening?
- Are transitions and pacing deliberate?


_GITCRAFT PLAYCRAFT 1.0.0 · 2026-11-04T21:05:33+00:00_
