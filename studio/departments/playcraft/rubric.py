"""PLAYCRAFT scoring: criteria, evidence levels, category scores, findings and priorities.

Evidence levels (every criterion result carries one):
  verified    measured by an automated check on the running game (the play probe, or a project report file
              the caller points at, which is hashed into the record)
  observed    seen in the running game but not asserted exactly (software-rendered FPS, latency to the
              nearest frame), or recorded by the person/agent who played it, with what they saw
  inferred    from the source and docs only (a system exists; how it feels is unknown)
  not_tested  no evidence; the criterion does not count towards the score

Category score: weighted mean of criterion values (pass 1, partial 0.5, fail 0), each weighted by its importance
and its evidence level (verified 1, observed 0.85, inferred 0.45), then shrunk towards 50 by how much of it rests on
inferred evidence: score = 50 + (raw - 50) * (0.5 + 0.5 * strong), strong = share of the weight that is verified or
observed. A category with no verified/observed evidence is capped at 70: source code alone cannot earn a high score,
and building successfully earns nothing. A category with no evidence at all has no score (not tested).
Overall: genre-weighted mean of the scored categories; confidence from evidence strength and coverage."""
import math

CATEGORIES = {
    "core_gameplay": "Core gameplay", "game_feel": "Game feel", "controls": "Controls and responsiveness", "progression": "Progression and rewards",
    "difficulty": "Difficulty and balance", "player_experience": "Player experience", "replayability": "Replayability",
    "technical": "Technical gameplay quality", "presentation": "Presentation and immersion", "mobile": "Mobile experience"}
DISCIPLINES = {
    "design_architect": "Game Design Architect", "game_feel": "Game Feel Engineer", "loop_designer": "Gameplay Loop Designer",
    "progression": "Progression Architect", "player_experience": "Player Experience Designer", "controls_device": "Control & Device Specialist",
    "difficulty_balance": "Difficulty & Balance Specialist", "retention_replay": "Retention & Replayability Designer", "presentation": "Presentation & Immersion"}
LEVEL_W = {"verified": 1.0, "observed": 0.85, "inferred": 0.45}
VALUE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}

DISCIPLINE_QUESTIONS = {
    "design_architect": ["What is the core concept in one sentence, and is it this game's own?", "What is the primary loop, and what secondary loops feed it?", "Where does the player make a meaningful decision, and how often?", "Is the depth earned, or is complexity standing in for depth?", "Does the game have a compelling reason to exist next to its genre's best?"],
    "game_feel": ["Does every press produce an immediate, visible acknowledgement?", "Do movement and collisions have weight (acceleration, impact, recovery)?", "Is feedback proportional (a big event feels bigger than a small one)?", "Is anything overdone (shake on every event, particle soup)?"],
    "loop_designer": ["What is the player doing every 5 seconds?", "What keeps them engaged after 60 seconds?", "What makes them want to play for 10 minutes?", "What creates longer-term motivation?", "Where does repetition become boredom?", "Where is the mastery?"],
    "progression": ["What does the player unlock, and does it change how they play?", "Is the reward cadence felt (not too sparse, not confetti for nothing)?", "Does progression come from the game itself rather than a bolted-on meta?"],
    "player_experience": ["Can a first-time player start and understand the goal without reading?", "Is the HUD readable at a glance on the target device?", "How fast is a restart after failure?", "Is the game accessible (motion, contrast, audio, text size)?"],
    "controls_device": ["Do controls respond within a frame or two on every target device?", "Are touch targets big enough and out of the thumb's way of the view?", "Does the game work in the orientation people hold the phone?"],
    "difficulty_balance": ["How often does a player fail, and is each failure their fault?", "Where are the spikes?", "What is the dominant strategy or exploit?"],
    "retention_replay": ["Why would someone play again tomorrow, legitimately?", "What is different next time (randomness, mastery, expression)?", "Is there a moment worth sharing?"],
    "presentation": ["Does the world feel alive when the player stands still?", "Do audio, animation and camera agree with what is happening?", "Are transitions and pacing deliberate?"]}

LOOP_ANSWERS = ["every_5_seconds", "after_60_seconds", "ten_minutes", "long_term", "boredom_point", "mastery"]


def C(id, category, discipline, title, kind, recommendation, impact=3, effort=2, risk=1, **kw):
    return dict(id=id, category=category, discipline=discipline, title=title, kind=kind, recommendation=recommendation, impact=impact, effort=effort, risk=risk, **kw)


# kind: signal (signals any / all), probe (a metric), judgement (only from recorded play), bolted (absence is good)
CORE = [
    # ---- core gameplay
    C("cg.pitch", "core_gameplay", "design_architect", "The intended experience is stated (pitch / how it plays)", "doc", "Write the one-sentence pitch and the core loop at the top of the README; every later decision is checked against it.", 2, 1),
    C("cg.goals", "core_gameplay", "design_architect", "Clear player objectives", "signal", "Give the player a visible objective at every moment (a target, a score to beat, a mission marker).", 4, 2, signals=["levels", "game_over", "highscore", "stars"], partial_at=1),
    C("cg.decisions", "core_gameplay", "design_architect", "Meaningful decisions (choices with trade-offs)", "signal", "Add a choice with a trade-off to the core loop (risk vs reward, spend vs save, route A vs B).", 4, 3, signals=["upgrades", "input_drag", "currency", "unlocks"], partial_at=1),
    C("cg.responds", "core_gameplay", "loop_designer", "Playing changes the game (inputs move the game state)", "probe", "The game did not visibly react to any probed input. Check that the first screen accepts input and that controls are discoverable.", 5, 2, metric="any_response"),
    C("cg.state", "core_gameplay", "loop_designer", "Game state advances during play (exposed numbers change)", "probe", "Expose a read-only debug object (e.g. window.__game = {score, state}) so automated playtests can verify the loop.", 2, 1, metric="state_changed"),
    # ---- game feel
    C("gf.response", "game_feel", "game_feel", "Actions are acknowledged on screen within ~100 ms", "probe", "Acknowledge every input on the very next frame (a pose, a puff, a sound) even when the action itself takes time.", 5, 2, metric="response_ms"),
    C("gf.shake", "game_feel", "game_feel", "Camera/screen shake for big impacts", "signal", "Add trauma-based shake (decays, scaled by impulse, capped) for big events only, with a setting to turn it off.", 3, 1, signals=["screen_shake"]),
    C("gf.hitstop", "game_feel", "game_feel", "Hit-stop / slow motion on key moments", "signal", "Freeze or slow time for 40-120 ms on the most important impacts so the eye can register them.", 3, 2, signals=["hitstop"]),
    C("gf.particles", "game_feel", "game_feel", "Particles on interactions", "signal", "Spawn a small, short-lived burst on contacts, landings and pickups; keep counts proportional to the event.", 3, 2, signals=["particles"]),
    C("gf.easing", "game_feel", "game_feel", "Motion is eased (tweens, lerps, springs), not linear", "signal", "Ease UI and camera motion (ease-out for arrivals, springs for bounces) instead of linear moves.", 3, 1, signals=["easing"]),
    C("gf.anticipation", "game_feel", "game_feel", "Anticipation, recoil, squash and stretch", "signal", "Add a short wind-up before actions and recoil/squash after them; it reads as weight.", 2, 2, signals=["squash"]),
    C("gf.audio", "game_feel", "game_feel", "Sound effects on actions", "signal", "Every player action and every impact needs a sound; vary pitch slightly so repeats do not grate.", 4, 2, signals=["audio"]),
    C("gf.popups", "game_feel", "game_feel", "Rewards are announced where they happen", "signal", "Pop a short callout or number where the reward was earned.", 2, 1, signals=["popups"]),
    C("gf.restraint", "game_feel", "game_feel", "Effects can be calmed (reduced motion / shake setting)", "signal", "Honour prefers-reduced-motion and offer a shake/flash toggle; juice must never cost readability.", 2, 1, signals=["reduced_motion"]),
    # ---- controls
    C("ctl.responds", "controls", "controls_device", "Each probed control produces a visible response", "probe", "Some controls produced no visible change. Make every bound input do something visible, or remove the binding.", 4, 2, metric="response_rate"),
    C("ctl.methods", "controls", "controls_device", "More than one input method (keyboard + pointer/touch, gamepad)", "signal", "Support keyboard and pointer/touch for the same actions; add gamepad if the genre expects it.", 3, 2, signals=["input_keyboard", "input_pointer", "input_touch", "input_gamepad"], partial_at=2, pass_at=3),
    C("ctl.forgiveness", "controls", "controls_device", "Input forgiveness (buffering, deadzones, grace windows)", "signal", "Buffer inputs pressed slightly early and add small grace windows; precise games feel fairer with them.", 3, 2, signals=["input_buffer", "deadzone"]),
    C("ctl.settings", "controls", "controls_device", "Control settings (sensitivity, remap, invert)", "signal", "Offer sensitivity and (for keyboards) remapping.", 2, 2, signals=["sensitivity", "input_remap"]),
    C("ctl.errors", "controls", "controls_device", "Inputs never throw errors", "probe", "Inputs during play raised page errors; fix them first, they usually break the action silently.", 5, 1, metric="input_errors"),
    # ---- progression
    C("pr.save", "progression", "progression", "Progress is saved", "signal", "Persist progress (localStorage is enough) and restore it on load.", 4, 1, signals=["save"]),
    C("pr.unlocks", "progression", "progression", "Unlocks or upgrades that change play", "signal", "Unlock new options (tools, modes, abilities) that change how the player plays, not just bigger numbers.", 3, 3, signals=["unlocks", "upgrades"]),
    C("pr.goals", "progression", "progression", "Long-term goals (achievements, collections, ranks)", "signal", "Give long-term goals that come from the game (a collection to complete, ranks, medals for mastery).", 3, 2, signals=["achievements", "collectibles", "xp", "stars"], partial_at=1, pass_at=2),
    C("pr.no_bolt_on", "progression", "progression", "No generic retention systems bolted on", "bolted", "Remove or rethink generic retention systems (daily login rewards, battle passes, energy timers, loot boxes) unless they come from the game's own fiction and loop.", 3, 2, signals=["daily_reward", "battle_pass", "energy_gate", "lootbox"]),
    # ---- difficulty and balance
    C("db.ramp", "difficulty", "difficulty_balance", "Difficulty progresses (levels, waves, ramp)", "signal", "Introduce a difficulty progression the player can feel (levels that teach then test, or a ramp that plateaus).", 4, 2, signals=["ramp", "levels", "difficulty"], partial_at=1, pass_at=2),
    C("db.tuning", "difficulty", "difficulty_balance", "Tuning values are centralised", "signal", "Move tuning numbers (speeds, spawn rates, costs) into one config so balance passes are quick and safe.", 2, 2, signals=["tuning_config"]),
    C("db.evidence", "difficulty", "difficulty_balance", "Balance is measured (simulations, solvers, playtest bots)", "signal", "Add a headless simulation/bot test that measures failure rate and pacing; balance by data, not by feel alone.", 3, 3, signals=["tune_tests"]),
    C("db.recovery", "difficulty", "difficulty_balance", "Failure has a recovery path (retry, checkpoint, respawn)", "signal", "Make failure cheap: retry in place, checkpoints, or keep partial progress.", 4, 2, signals=["restart", "checkpoint"]),
    C("db.assist", "difficulty", "difficulty_balance", "Assist / difficulty options", "signal", "Offer an assist or easier option for players who are stuck.", 2, 2, signals=["assist", "difficulty"]),
    # ---- player experience
    C("px.loads", "player_experience", "player_experience", "Playable quickly (load + start ≤ 3 s)", "probe", "Cut time to first play: show the start screen immediately, load heavy assets in the background.", 4, 3, metric="time_to_play"),
    C("px.onboarding", "player_experience", "player_experience", "Onboarding teaches by doing (hints, first-run guidance)", "signal", "Teach the first action in context (a pulsing hint on the control, a safe first encounter) instead of a text screen.", 4, 2, signals=["tutorial"]),
    C("px.pause", "player_experience", "player_experience", "Pause works, and the game pauses when hidden", "probe", "Pause on Escape/P and automatically when the tab/app is hidden.", 3, 1, metric="pause"),
    C("px.auto_pause", "player_experience", "player_experience", "Auto-pause when the page is hidden", "signal", "Pause on visibilitychange so a phone call or app switch never costs a run.", 3, 1, signals=["visibility_pause"]),
    C("px.restart", "player_experience", "player_experience", "Restart friction is low", "signal", "Let the player retry from the fail screen with one press.", 4, 1, signals=["restart"]),
    C("px.text", "player_experience", "player_experience", "Text is legible on the target device (≥ 12 px)", "probe", "Raise the smallest visible text to at least 12 CSS px on phones (14+ for anything the player must read in play).", 3, 1, metric="min_font"),
    C("px.accessibility", "player_experience", "player_experience", "Accessibility (reduced motion, ARIA, contrast, subtitles, mute)", "signal", "Add reduced motion, a mute toggle, readable contrast and labelled controls.", 3, 2, signals=["reduced_motion", "aria", "colorblind", "subtitles", "mute"], partial_at=2, pass_at=3),
    C("px.dead_time", "player_experience", "loop_designer", "Little dead time during play", "probe", "Large stretches of play show no change on screen. Cut waits (settling, transitions, travel) or give the player something to do during them.", 3, 3, metric="dead_time"),
    # ---- replayability
    C("rp.variety", "replayability", "retention_replay", "Variation between sessions (randomness, procedural content)", "signal", "Vary something every run (layouts, spawns, conditions) so sessions differ.", 3, 3, signals=["randomness", "procedural"]),
    C("rp.mastery", "replayability", "retention_replay", "Mastery goals (best scores, ratings, records)", "signal", "Record a best (score, time, fewest shots) and show it next to the current attempt.", 4, 1, signals=["highscore", "stars"]),
    C("rp.expression", "replayability", "retention_replay", "Player expression (customisation, sandbox, styles)", "signal", "Give players a way to express themselves (cosmetics earned in play, a sandbox, style scoring).", 2, 3, signals=["customization", "sandbox_mode"]),
    C("rp.share", "replayability", "retention_replay", "Shareable moments (share, replay, daily seed)", "signal", "Make a great moment shareable (a share card, a replay, a daily seed everyone plays).", 2, 3, signals=["share", "daily_challenge"]),
    # ---- technical
    C("tech.loads", "technical", "controls_device", "Game loads on every tested viewport", "probe", "The game failed to load on a tested viewport; fix that before anything else.", 5, 2, metric="loaded"),
    C("tech.errors", "technical", "controls_device", "No runtime errors during play", "probe", "Fix the runtime errors raised during play.", 5, 2, metric="page_errors"),
    C("tech.missing", "technical", "controls_device", "No missing files", "probe", "Files requested by the game are missing from the build.", 4, 1, metric="missing"),
    C("tech.fps", "technical", "controls_device", "Frame rate holds during play", "probe", "Frame rate drops during play; profile the hot path (draw calls, allocations per frame).", 4, 3, metric="fps"),
    C("tech.timestep", "technical", "controls_device", "Frame-rate-independent update (dt clamp / fixed step)", "signal", "Clamp dt and step simulation at a fixed rate so behaviour does not change with frame rate (120 Hz phones, slow devices).", 4, 2, signals=["fixed_step", "dt_clamp"]),
    C("tech.tests", "technical", "controls_device", "Automated tests exist", "signal", "Add tests for the rules that matter to play (scoring, physics limits, saves).", 3, 2, signals=["tests"]),
    # ---- presentation
    C("pres.audio", "presentation", "presentation", "Sound design and music", "signal", "Add ambience and music that respond to the game state (intensity layers), not a single loop.", 4, 3, signals=["audio", "music"], all=True),
    C("pres.animation", "presentation", "presentation", "Animation", "signal", "Animate characters and UI states (idle, move, react) rather than snapping.", 3, 3, signals=["animation"]),
    C("pres.atmosphere", "presentation", "presentation", "Atmosphere (lighting, fog, weather, post)", "signal", "Use light, fog and weather to set mood and to guide the eye.", 2, 3, signals=["atmosphere"]),
    C("pres.transitions", "presentation", "presentation", "Transitions between screens and states", "signal", "Fade or wipe between screens and states; hard cuts read as unfinished.", 2, 1, signals=["transitions"]),
    C("pres.alive", "presentation", "presentation", "The world moves when the player is idle", "probe", "The screen is completely still without input. Add idle motion (ambient animation, particles, a breathing character).", 2, 2, metric="idle_motion"),
    C("pres.visual", "presentation", "presentation", "Screens have visual range (not blank or flat)", "probe", "Screens rendered nearly flat or blank on a tested viewport.", 3, 2, metric="visual"),
    # ---- mobile (only when the game is meant for phones)
    C("mob.renders", "mobile", "controls_device", "Renders on a phone viewport", "probe", "The phone render was blank or broken.", 5, 2, metric="phone_renders", mobile=True),
    C("mob.touch", "mobile", "controls_device", "Touch input responds", "probe", "No probed touch gesture changed the screen on the phone. Touch must not be an afterthought for a mobile game.", 5, 3, metric="touch_response", mobile=True),
    C("mob.meta", "mobile", "controls_device", "Viewport meta set for phones", "probe", "Add <meta name=viewport content=\"width=device-width, initial-scale=1, viewport-fit=cover\">.", 3, 1, metric="viewport_meta", mobile=True),
    C("mob.targets", "mobile", "controls_device", "Touch targets ≥ 44 px", "probe", "Enlarge the listed touch targets to at least 44×44 CSS px (Apple HIG) and keep them clear of each other.", 3, 1, metric="touch_targets", mobile=True),
    C("mob.overflow", "mobile", "controls_device", "No horizontal overflow on phones", "probe", "The page scrolls sideways on a phone; constrain widths to the viewport.", 3, 1, metric="phone_overflow", mobile=True),
    C("mob.gestures", "mobile", "controls_device", "Browser gestures do not fight the game (touch-action, no zoom)", "probe", "Set touch-action: none on the play surface (and disable double-tap zoom) so swipes and pinches go to the game.", 3, 1, metric="gestures", mobile=True),
    C("mob.safe_area", "mobile", "controls_device", "Safe areas respected (notch, home bar)", "signal", "Pad HUD and controls with env(safe-area-inset-*) and use viewport-fit=cover.", 3, 1, signals=["safe_area"], mobile=True),
    C("mob.orientation", "mobile", "controls_device", "Orientation handled", "signal", "Support or explicitly ask for the intended orientation; re-layout on rotation.", 2, 2, signals=["orientation"], mobile=True),
    C("mob.fps", "mobile", "controls_device", "Frame rate on the phone viewport", "probe", "The phone viewport ran slowly; test on a real device and reduce per-frame cost.", 3, 3, metric="phone_fps", mobile=True),
    C("mob.haptics", "mobile", "game_feel", "Haptics on key moments (where supported)", "signal", "Add a short vibration on big impacts (navigator.vibrate) where the platform supports it.", 1, 1, signals=["haptics"], mobile=True),
]


# ---------------------------------------------------------------- evaluation
def _signal(c, sig, gsig):
    ids = c.get("signals") or []
    found = [s for s in ids if (sig.get(s) or {}).get("count", 0) > 0]
    if c.get("patterns") is not None or c["id"] in gsig:
        g = gsig.get(c["id"]) or {}
        if g.get("count"): found.append("pattern")
        where = g.get("where", [])
    else:
        where = []
    for s in found:
        if s in sig: where += sig[s].get("where", [])[:2]
    if c["kind"] == "bolted":
        return ("fail" if found else "pass"), "inferred", (f"found: {', '.join(found)}" if found else "none of: " + ", ".join(ids)), where[:4]
    if c.get("all"):   # every listed signal (and the genre patterns, if any) must be present; some = partial
        need, partial_at = len(ids) + (1 if c.get("patterns") else 0), 1
    else:
        need, partial_at = c.get("pass_at", 1), c.get("partial_at")
    if len(found) >= need: st = "pass"
    elif partial_at and len(found) >= partial_at: st = "partial"
    else: st = "fail"
    detail = (f"found {', '.join(found)}" if found else "not found in source: " + ", ".join(ids + (["genre patterns"] if c.get("patterns") else [])))
    return st, "inferred", detail, where[:4]


def _probe(c, m, profile):
    """(status, level, detail) from the play metrics; None when the probe could not measure it."""
    if not m: return None
    k = c["metric"]
    if k == "loaded":
        bad = [v for v, x in m["viewports"].items() if not x["loaded"]]
        return ("fail" if bad else "pass"), "verified", ("failed on " + ", ".join(bad)) if bad else f"loaded on {', '.join(m['viewports'])}"
    if not m.get("loaded_any"): return None
    if k == "page_errors":
        n = len(m["page_errors"]); return ("pass" if n == 0 else "fail"), "verified", (m["page_errors"][:3] if n else "0 page errors (console errors: %d)" % len(m["console_errors"]))
    if k == "missing":
        n = len(m["missing"]); return ("pass" if n == 0 else "fail"), "verified", (m["missing"][:5] if n else "no missing files")
    if k == "fps":
        f = m.get("fps")
        if f is None: return None
        return ("pass" if f >= 50 else "partial" if f >= 28 else "fail"), "observed", f"{f} fps, p95 {m.get('frame_p95')} ms (headless, software WebGL: real GPUs are faster)"
    if k == "phone_fps":
        f = m.get("phone_fps")
        if f is None: return None
        return ("pass" if f >= 45 else "partial" if f >= 25 else "fail"), "observed", f"{f} fps on the phone viewport (software rendering)"
    if k == "any_response":
        r = m.get("responses") or []
        if not r: return None
        n = sum(x["responded"] for x in r); return ("pass" if n else "fail"), "verified", f"{n}/{len(r)} probed inputs changed the screen"
    if k == "response_rate":
        r = [x for x in (m.get("responses") or []) if x["kind"] == "key" or not x["touch"]]
        if not r: return None
        n = sum(x["responded"] for x in r); share = n / len(r)
        silent = [x["input"] for x in r if not x["responded"]]
        slow = any(x.get("slow") for x in r)   # under 10 fps (software WebGL) a missed response may be the probe's, not the game's
        return ("pass" if share >= 0.75 else "partial" if share >= 0.4 else "fail"), ("observed" if slow and share < 0.75 else "verified"), \
            f"{n}/{len(r)} desktop inputs responded" + (f"; no visible response: {', '.join(silent[:6])}" if silent else "") + (" (rendering under 10 fps here: re-check misses on real hardware)" if slow and silent else "")
    if k == "response_ms":
        ms = m.get("best_response_ms")
        if ms is None: return ("fail", "verified", "no probed input produced a visible change") if m.get("responses") else None
        fr = m.get("frame_p50") or 16.7   # the probe sees a change one frame late at best: allow two frames when rendering is slow
        ok, okish = max(100, 2 * fr), max(200, 4 * fr)
        return ("pass" if ms <= ok else "partial" if ms <= okish else "fail"), "observed", f"fastest visible response {ms} ms after the input (median {m.get('median_response_ms')} ms; one frame here is {fr} ms, so ≤ {round(ok)} ms passes)"
    if k == "state_changed":
        if not m.get("hooks_found"): return None
        ch = m.get("state_changed") or []
        return ("pass" if ch else "partial"), "verified", (f"changed during play: {', '.join(ch[:8])}" if ch else "exposed objects found but no value changed during play")
    if k == "input_errors":
        e = m.get("input_errors") or []
        return ("pass" if not e else "fail"), "verified", (e[:3] if e else "no errors while inputs were played")
    if k == "time_to_play":
        t = m.get("time_to_play_ms")
        if t is None: return None
        return ("pass" if t <= 3000 else "partial" if t <= 6000 else "fail"), "observed", f"{t} ms from navigation to playing (load {m.get('load_ms')} ms + start {m.get('start_ms')} ms; served locally)"
    if k == "pause":
        p = m.get("pause")
        if p is None: return None
        if p["works"] is None: return None
        # motion stopping is measured; that the game was mid-play when paused is inferred from the motion, so a miss is observed
        return ("pass", "verified", p["detail"]) if p["works"] else ("fail", "observed", p["detail"] + " (pressed during play, right after an input)")
    if k == "min_font":
        f = m.get("min_font_px")
        if f is None: return None
        return ("pass" if f >= 12 else "partial" if f >= 10 else "fail"), "verified", f"smallest visible text {f} px ({m.get('min_font_text')!r}) on {m.get('min_font_viewport')}"
    if k == "dead_time":
        d = m.get("dead_time")
        if d is None: return None
        lim = profile.get("dead_time_ok", 0.25)
        return ("pass" if d <= lim else "partial" if d <= lim * 2 else "fail"), "observed", f"{round(d * 100)}% of frames unchanged during {m.get('monkey_s')} s of mixed inputs"
    if k == "idle_motion":
        v = m.get("idle_motion")
        if v is None: return None
        return ("pass" if v > 0.002 else "partial" if v > 0.0003 else "fail"), "observed", f"share of the screen changing per frame with no input: {v}"
    if k == "visual":
        bad = [v for v, x in m["viewports"].items() if x.get("blank")]
        return ("fail" if bad else "pass"), "verified", ("blank on " + ", ".join(bad)) if bad else {v: x.get("colours") for v, x in m["viewports"].items()}
    ph = m.get("phone")
    if not ph: return None
    if k == "phone_renders":
        return ("fail" if ph.get("blank") or not ph.get("loaded") else "pass"), "verified", ph.get("colours")
    if k == "touch_response":
        r = [x for x in (m.get("responses") or []) if x["touch"]]
        if not r: return None
        n = sum(x["responded"] for x in r)
        slow = any(x.get("slow") for x in r)
        return ("pass" if n >= 2 else "partial" if n == 1 else "fail"), ("observed" if slow and n < 2 else "verified"), f"{n}/{len(r)} touch gestures changed the screen" + (f"; fastest {m.get('touch_best_response_ms')} ms" if n else "")
    if k == "viewport_meta":
        v = ph.get("viewport_meta")
        ok = bool(v and "width=device-width" in v.replace(" ", ""))
        return ("pass" if ok else "fail"), "verified", v or "no viewport meta"
    if k == "touch_targets":
        n = ph.get("small_target_count", 0)
        return ("pass" if n == 0 else "partial" if n <= 2 else "fail"), "verified", (ph.get("small_targets")[:6] if n else f"all {ph.get('interactive')} visible controls ≥ 44 px")
    if k == "phone_overflow":
        o = ph.get("overflow_px", 0)
        return ("pass" if o <= 1 else "fail"), "verified", f"page is {o} px wider than the screen" if o > 1 else "no horizontal overflow"
    if k == "gestures":
        ta = ph.get("canvas_touch_action") or ph.get("body_touch_action"); v = (ph.get("viewport_meta") or "").replace(" ", "")
        ok_ta = ta in ("none", "pinch-zoom", "manipulation") ; no_zoom = "user-scalable=no" in v or "maximum-scale=1" in v
        return ("pass" if ok_ta else "partial" if no_zoom else "fail"), "verified", f"play surface touch-action: {ta}; viewport: {v or None}"
    return None


def evaluate(scan_info, metrics, criteria, profile, judgements, evidence, mobile):
    sig, gsig = scan_info["signals"], scan_info.get("genre_signals", {})
    out = []
    for c in criteria:
        if c.get("mobile") and not mobile:
            continue
        r = {k: c[k] for k in ("id", "category", "discipline", "title", "kind", "impact", "effort", "risk") if k in c}
        r["recommendation"] = profile.get("overrides", {}).get(c["id"], c["recommendation"]); r["genre"] = c.get("genre")
        if c.get("genre_share") is not None and c["genre_share"] < 1:   # a secondary genre's checks count less
            r["impact"] = max(1, round(c["impact"] * c["genre_share"]))
        if c["kind"] in ("signal", "bolted"):
            st, lv, det, where = _signal(c, sig, gsig); r.update(status=st, level=lv, detail=det, where=where)
        elif c["kind"] == "doc":
            ok = bool(scan_info.get("pitch")) and scan_info.get("docs_chars", 0) > 400
            r.update(status="pass" if ok else "fail", level="inferred", detail=scan_info.get("pitch") or "no README pitch found", where=scan_info.get("docs", [])[:3])
        elif c["kind"] == "probe":
            p = _probe(c, metrics, profile)
            if p is None: r.update(status="unknown", level="not_tested", detail="not measured (game not played on this run)" if not metrics else "the probe could not measure this")
            else: r.update(status=p[0], level=p[1], detail=p[2])
        out.append(r)
    # judgements recorded by whoever played (the agent or a person): observed or inferred, with what they saw
    for j in judgements or []:
        out.append({"id": j.get("criterion") or f"judgement.{j['category']}.{len(out)}", "category": j["category"], "discipline": j.get("discipline") or _disc(j["category"]),
                    "title": j.get("title") or "Recorded playtest judgement", "kind": "judgement", "status": j["status"], "level": j.get("level", "observed"),
                    "detail": j["evidence"], "recommendation": j.get("recommendation") or "", "impact": j.get("impact", 3), "effort": j.get("effort", 2), "risk": j.get("risk", 1)})
    # project evidence files (test reports, simulations): verified, hashed by the caller
    for e in evidence or []:
        out.append({"id": e.get("id") or f"evidence.{len(out)}", "category": e["category"], "discipline": e.get("discipline") or _disc(e["category"]),
                    "title": e.get("title") or e["source"], "kind": "evidence", "status": e["status"], "level": "verified", "detail": e.get("detail") or e["source"],
                    "source": e["source"], "sha256": e.get("sha256"), "recommendation": e.get("recommendation") or "", "impact": e.get("impact", 3), "effort": e.get("effort", 2), "risk": 1})
    return out


def _disc(cat):
    return {"core_gameplay": "design_architect", "game_feel": "game_feel", "controls": "controls_device", "progression": "progression", "difficulty": "difficulty_balance",
            "player_experience": "player_experience", "replayability": "retention_replay", "technical": "controls_device", "presentation": "presentation", "mobile": "controls_device"}[cat]


def score(results, weights, mobile, played=True):
    cats = {}
    for cat in CATEGORIES:
        if cat == "mobile" and not mobile:
            cats[cat] = {"title": CATEGORIES[cat], "score": None, "applicable": False, "confidence": None, "evidence": "not a mobile game (no mobile intent in docs or code)"}
            continue
        rs = [r for r in results if r["category"] == cat]
        known = [r for r in rs if r["level"] in LEVEL_W and r["status"] in VALUE]
        levels = {lv: sum(1 for r in rs if r["level"] == lv) for lv in ("verified", "observed", "inferred", "not_tested")}
        if not known:
            cats[cat] = {"title": CATEGORIES[cat], "score": None, "applicable": True, "confidence": "none", "levels": levels, "evidence": "not tested"}
            continue
        w = lambda r: r.get("impact", 3) * LEVEL_W[r["level"]]
        raw = sum(w(r) * VALUE[r["status"]] for r in known) / sum(w(r) for r in known) * 100
        strong_w = sum(r.get("impact", 3) for r in known if r["level"] in ("verified", "observed"))
        strong = strong_w / sum(r.get("impact", 3) for r in known)
        s = 50 + (raw - 50) * (0.5 + 0.5 * strong)
        capped = False
        if strong == 0 and s > 70: s, capped = 70.0, True
        coverage = len(known) / max(1, len(rs))
        conf = "high" if strong >= 0.6 and coverage >= 0.7 and len(known) >= 3 else "medium" if strong >= 0.3 and len(known) >= 2 else "low"
        cats[cat] = {"title": CATEGORIES[cat], "score": round(s), "raw": round(raw), "applicable": True, "confidence": conf, "strong_evidence_share": round(strong, 2),
                     "coverage": round(coverage, 2), "levels": levels, "capped_inferred_only": capped,
                     "passed": [r["id"] for r in known if r["status"] == "pass"], "failed": [r["id"] for r in known if r["status"] == "fail"], "partial": [r["id"] for r in known if r["status"] == "partial"]}
    scored = {k: v for k, v in cats.items() if v.get("score") is not None}
    tw = sum(weights.get(k, 1.0) for k in scored)
    overall = round(sum(v["score"] * weights.get(k, 1.0) for k, v in scored.items()) / tw) if tw else None
    applicable = [k for k, v in cats.items() if v.get("applicable")]
    cov = sum(weights.get(k, 1) for k in scored) / max(1e-9, sum(weights.get(k, 1) for k in applicable))
    strong = sum(v["strong_evidence_share"] * weights.get(k, 1) for k, v in scored.items()) / tw if tw else 0
    conf = "high" if strong >= 0.55 and cov >= 0.9 else "medium" if strong >= 0.3 and cov >= 0.7 else "low"
    return cats, {"score": overall, "confidence": conf, "coverage": round(cov, 2), "strong_evidence_share": round(strong, 2),
                  "note": None if conf != "low" else ("Mostly inferred from source: build the game and pass target=<build> so it is played." if not played else
                          "Low confidence: much of this rests on source evidence; record judgements from playing (playcraft_assess judgements) and point `evidence` at the project's own test reports.")}


def findings(results, weights):
    """Failed/partial criteria → ranked opportunities. Verified failures are defects; the rest are design opportunities."""
    out = []
    for r in results:
        if r["status"] not in ("fail", "partial") or r["level"] == "not_tested": continue
        if not r.get("recommendation"): continue
        defect = r["level"] == "verified" and r["category"] in ("technical", "mobile", "controls") and r["status"] == "fail"
        imp = r.get("impact", 3) * (1 if r["status"] == "fail" else 0.6)
        wt = weights.get(r["category"], 1.0)
        prio = round(imp * wt * 2 - r.get("effort", 2) - 0.5 * r.get("risk", 1) + (2 if defect else 0) + (0.5 if r["level"] in ("verified", "observed") else 0), 2)
        out.append({"id": r["id"], "category": r["category"], "discipline": r["discipline"], "title": r["title"], "type": "defect" if defect else "design",
                    "status": r["status"], "level": r["level"], "evidence": r.get("detail"), "where": r.get("where", []), "recommendation": r["recommendation"],
                    "impact": r.get("impact", 3), "effort": r.get("effort", 2), "risk": r.get("risk", 1), "priority": prio, "genre": r.get("genre")})
    out.sort(key=lambda f: -f["priority"])
    for i, f in enumerate(out): f["rank"] = i + 1
    return out


def blend_weights(genres, profiles):
    """Category weights for a (possibly multi-genre) game: genre profiles blended by genre score share."""
    acc, tot = {}, 0.0
    for g in genres:
        share = g.get("share") or 0.5
        for cat in CATEGORIES:
            acc[cat] = acc.get(cat, 0) + share * profiles[g["genre"]].get("weights", {}).get(cat, 1.0)
        tot += share
    return {k: round(v / tot, 2) for k, v in acc.items()} if tot else {k: 1.0 for k in CATEGORIES}
