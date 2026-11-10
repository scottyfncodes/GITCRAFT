"""CREATIVE DIRECTION: decided before anything is built, and held to.

A build work order that says "implement a complete game" gets a game that runs. What makes it worth playing or
looking at (one idea for the look, one loop that is satisfying to repeat, feedback for every action, a curve) has
to be decided first and built to, not scored afterwards. So a production that builds or reshapes a product starts
with `design.direction`: the agent writes direction.json for THIS product, a gate checks it is complete, specific
and legible, the build depends on it, and the release lists the questions only a person can answer by playing.

  scope(spec)            which parts this production needs: art, play, interaction (or None: no direction task)
  work_order(spec)       the agent's brief, instructions and expected file
  validate(path, base)   the gate: measurable checks only (completeness, placeholder text, contrast, numbers).
                         It cannot judge taste and does not pretend to: a passing direction is a decided one, not
                         a good one. PIXELCRAFT, PLAYCRAFT and a person judge the result.
  build_lines(spec)      what the build work order says about building to it
  human_checks(d)        the questions the release hands to a person (fun is never claimed from automation)

There is no house style: nothing here names a palette, a typeface or a genre. docs/direction.md."""
import json, re

PLACEHOLDER = re.compile(r"^\s*(todo|tbd|n/?a|none|\.\.\.|lorem\b.*|placeholder|example|string|text)\s*$", re.I)
# a look described only in these words has not been decided: it describes every product, so it directs none
GENERIC = re.compile(r"^\W*(?:(?:a|an|the|very|and|with|but|yet|feel|look|design|style|aesthetic|ui|interface|simple|clean|modern|sleek|minimal|minimalist|"
                     r"minimalistic|professional|elegant|beautiful|polished|intuitive|user[- ]friendly|fresh|nice|cool|fun|engaging|vibrant|colou?rful|"
                     r"stylish|slick|crisp|smooth|contemporary|premium|high[- ]quality|visually appealing|appealing)\W*)+$", re.I)
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def scope(spec):
    """→ sorted list of parts, or None. New games, apps and sites get a full direction; an existing project gets one only
    for the part the person asked to reshape (a redesign decides the look again; a gameplay pass decides the play)."""
    d, mode = spec.get("deliverable"), spec.get("mode") or {}
    if d not in ("game", "app", "site"): return None
    if mode.get("existing"):
        f = mode.get("focus")
        if mode.get("workflow") != "update": return None
        if f == "visual": return ["art"]
        if f == "gameplay" and d == "game": return ["play"]
        if f == "polish": return ["art", "play"] if d == "game" else ["art"]
        return None
    return ["art", "play"] if d == "game" else ["art", "interaction"]


def work_order(spec):
    parts, d, mode = scope(spec), spec["deliverable"], spec.get("mode") or {}
    existing = bool(mode.get("existing"))
    mobile = spec["platform"].get("mobile_first")
    ins = ["Write direction.json for THIS product before any code. Every choice must follow from what the product is, who uses it and where; "
           "a sentence that would fit any other product is not a decision. Read docs/direction.md for the format and a worked example."]
    if existing:
        ins.append("This project exists. Read it first (its screens or a play session, its tokens, art bible, README). State what is kept and what changes: "
                   "`keeps` lists what stays exactly as it is, and the direction changes only what was asked"
                   + (f" ({mode['request']})." if mode.get("request") else "."))
    ins.append("product: {promise, audience, context}: what it gives someone, who they are, and the moment they use it (on a phone on a train, "
               "at a desk all day, five minutes between things).")
    if "art" in parts:
        ins += ["art.concept: ONE idea the whole look comes from, taken from the product's own world (a harbour chart at night; a baker's order pad). "
                "Not adjectives: 'clean and modern' is refused.",
                "art.palette: background, surface, primary, accent, text as #rrggbb, each with a job; text on background ≥ 4.5:1 and primary on background ≥ 3:1 "
                "(checked). art.type: display and body faces with why they suit it. art.shape: the shape language (radii, line weight, silhouettes). "
                "art.motion: what moves, how fast, and what never moves. art.avoid: at least two things this must never look like.",
                "Use the ui-design skill's Explore phase (three genuinely different directions, pick one and say why) when the project has no look yet"
                + ("; keep the established identity where the request does not change it." if existing else ".")]
    if "play" in parts:
        ins += ["play.pillars: two to four things this game is about; every mechanic must serve one, and a feature that serves none is cut.",
                "play.loop: {verb, challenge, feedback, reward, seconds}: what the player does, what resists, what they see/hear/feel the instant they act, "
                "what they earn, and how many seconds one turn of the loop takes (≤ 60; the first turn must be reachable within 10 s of loading).",
                "play.controls: {desktop" + (", touch" if mobile or not existing else "") + "}: the inputs, sized for a thumb on a phone. play.feel: the numbers that make it feel "
                "right (speeds, accelerations, jump height and time, input buffering, coyote time, hit-stop, shake) with units; tune them by playing, then record the values kept.",
                "play.feedback: at least four {event, response} pairs: every player action and every outcome answers on screen and in sound within a frame. "
                "play.curve: at least three {at_seconds, introduces} steps: what gets harder or new, and when. play.fail: why losing feels fair (telegraphed, readable) "
                "and how fast the retry is. play.mastery: what a skilled player does that a new one cannot.",
                "play.playtest: at least three questions a person must answer by playing (\"did you want another go?\"). Automation cannot answer these; "
                "they are handed to a person at release and never reported as passed."]
    if "interaction" in parts:
        ins += ["interaction.primary_task: the one thing most visits are for, and interaction.taps_to_value: how many taps from opening to having done it "
                "(design for the smallest honest number). interaction.screens: every screen, each with its one job.",
                "interaction.states: what empty, loading, error and success look like (at least three), designed, not left to defaults. "
                "interaction.feedback: at least three {event, response} pairs: what the person sees the instant they act."]
    ins.append("done_when: at least three observable statements that would make you call this finished, beyond 'it runs'.")
    keys = ["product", "done_when"] + [p for p in ("art", "play", "interaction") if p in parts]
    return {"brief": ("The creative direction for " + spec["title"] + ": " + spec["prompt"][:400]) if not existing else
                     (f"The direction for this change to {spec['title']}: " + (mode.get("request") or spec["prompt"])[:400]),
            "tools": ["the ui-design skill (Explore, references/games.md for a game's interface)", "vectorcraft / photocraft for look tests, when a sketch settles a choice"],
            "instructions": ins,
            "expected": [{"path": "direction.json", "format": "json", "keys": keys, "validate": "direction", "role": "direction"}],
            "license": "owned by the project"}


def _lum(h):
    v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def _said(v, n=12):
    return isinstance(v, str) and len(v.strip()) >= n and not PLACEHOLDER.match(v)


def _pairs(v, a, b):
    return [x for x in v or [] if isinstance(x, dict) and _said(x.get(a), 3) and _said(x.get(b), 6)] if isinstance(v, list) else []


def validate(path, base=None):
    """→ [{name, ok, detail}]. Only what can be measured; the same file always gets the same answer."""
    try: D = json.load(open(path))
    except (OSError, ValueError) as e: return [{"name": "direction.json opens as JSON", "ok": False, "detail": str(e)}]
    out = []
    add = lambda name, ok, detail=None: out.append({"name": name, "ok": bool(ok), "detail": detail})
    P = D.get("product") if isinstance(D.get("product"), dict) else {}
    add("product: promise, audience and context are stated", all(_said(P.get(k)) for k in ("promise", "audience", "context")),
        [k for k in ("promise", "audience", "context") if not _said(P.get(k))] or None)
    dw = [x for x in D.get("done_when") or [] if _said(x)] if isinstance(D.get("done_when"), list) else []
    add("done_when: at least three observable statements", len(dw) >= 3, f"{len(dw)} found")
    if "art" in D:
        A = D["art"] if isinstance(D["art"], dict) else {}
        c = A.get("concept")
        add("art.concept: one idea from this product's world, not adjectives", _said(c, 16) and not GENERIC.match(c or ""),
            "missing" if not _said(c, 16) else f"'{c}' describes any product" if GENERIC.match(c) else None)
        pal = A.get("palette") if isinstance(A.get("palette"), dict) else {}
        need = ("background", "surface", "primary", "accent", "text")
        bad = [k for k in need if not HEX.match(str(pal.get(k) or ""))]
        add("art.palette: background, surface, primary, accent and text as #rrggbb", not bad, bad or None)
        if not bad:
            ct, cp = contrast(pal["text"], pal["background"]), contrast(pal["primary"], pal["background"])
            add("art.palette: text on background is legible (≥ 4.5:1)", ct >= 4.5, f"{ct}:1")
            add("art.palette: primary stands out from the background (≥ 3:1)", cp >= 3, f"{cp}:1")
            add("art.palette: accent is not the primary again", pal["accent"].lower() != pal["primary"].lower() and len({pal[k].lower() for k in need}) >= 4,
                "fewer than four distinct colours" if len({pal[k].lower() for k in need}) < 4 else None)
        ty = A.get("type") if isinstance(A.get("type"), dict) else {}
        add("art.type: display and body faces, with why", _said(ty.get("display"), 3) and _said(ty.get("body"), 3) and _said(ty.get("why")), None)
        add("art.shape and art.motion are decided", _said(A.get("shape")) and _said(A.get("motion")), None)
        av = [x for x in A.get("avoid") or [] if _said(x, 4)] if isinstance(A.get("avoid"), list) else []
        add("art.avoid: at least two things it must never look like", len(av) >= 2, f"{len(av)} found")
    if "play" in D:
        Y = D["play"] if isinstance(D["play"], dict) else {}
        pl = [x for x in Y.get("pillars") or [] if _said(x, 6)] if isinstance(Y.get("pillars"), list) else []
        add("play.pillars: two to four", 2 <= len(pl) <= 4, f"{len(pl)} found")
        L = Y.get("loop") if isinstance(Y.get("loop"), dict) else {}
        add("play.loop: verb, challenge, feedback and reward", all(_said(L.get(k), 4) for k in ("verb", "challenge", "feedback", "reward")),
            [k for k in ("verb", "challenge", "feedback", "reward") if not _said(L.get(k), 4)] or None)
        sec = L.get("seconds")
        add("play.loop.seconds: one turn of the loop takes ≤ 60 s", isinstance(sec, (int, float)) and not isinstance(sec, bool) and 0 < sec <= 60, sec)
        C = Y.get("controls") if isinstance(Y.get("controls"), dict) else {}
        add("play.controls: the inputs are named", any(_said(v, 4) for v in C.values()), None)
        F = Y.get("feel") if isinstance(Y.get("feel"), dict) else {}
        nums = [k for k, v in F.items() if isinstance(v, (int, float)) and not isinstance(v, bool) or isinstance(v, str) and re.search(r"\d", v)]
        add("play.feel: at least three tuned numbers (with units)", len(nums) >= 3, f"{len(nums)} found")
        fb = _pairs(Y.get("feedback"), "event", "response")
        add("play.feedback: at least four event → response pairs", len(fb) >= 4, f"{len(fb)} found")
        cv = [x for x in Y.get("curve") or [] if isinstance(x, dict) and isinstance(x.get("at_seconds"), (int, float)) and _said(x.get("introduces"), 6)] if isinstance(Y.get("curve"), list) else []
        ts = [x["at_seconds"] for x in cv]
        add("play.curve: at least three steps, later each time", len(cv) >= 3 and ts == sorted(ts) and len(set(ts)) == len(ts), ts or "none")
        add("play.fail and play.mastery are decided", _said(Y.get("fail")) and _said(Y.get("mastery")), None)
        pt = [x for x in Y.get("playtest") or [] if _said(x) and x.strip().endswith("?")] if isinstance(Y.get("playtest"), list) else []
        add("play.playtest: at least three questions for a person who plays it", len(pt) >= 3, f"{len(pt)} found")
    if "interaction" in D:
        I = D["interaction"] if isinstance(D["interaction"], dict) else {}
        add("interaction.primary_task is stated", _said(I.get("primary_task")), None)
        n = I.get("taps_to_value")
        add("interaction.taps_to_value: a number", isinstance(n, int) and not isinstance(n, bool) and 0 <= n <= 12, n)
        sc = [x for x in I.get("screens") or [] if isinstance(x, dict) and _said(x.get("name"), 2) and _said(x.get("job"), 8)] if isinstance(I.get("screens"), list) else []
        add("interaction.screens: every screen has its one job", len(sc) >= 1 and len(sc) == len(I.get("screens") or []), f"{len(sc)} of {len(I.get('screens') or [])}")
        st = I.get("states") if isinstance(I.get("states"), dict) else {}
        add("interaction.states: at least three designed states (empty, loading, error, success)", len([k for k, v in st.items() if _said(v)]) >= 3, sorted(st) or "none")
        add("interaction.feedback: at least three event → response pairs", len(_pairs(I.get("feedback"), "event", "response")) >= 3, None)
    if "keeps" in D:
        add("keeps: what stays exactly as it is", isinstance(D["keeps"], list) and any(_said(x, 6) for x in D["keeps"]), None)
    return out


VALIDATORS = {"direction": validate}


def build_lines(spec):
    """What the build is told. The floor below is how a game feels responsive and an interface feels made; the direction
    decides everything above the floor."""
    parts = scope(spec)
    if not parts: return []
    d = spec["deliverable"]
    L = ["Build to the approved creative direction (direction.json from design.direction, in the hand-off). It is the specification for how this looks"
         + (" and plays" if "play" in parts else " and behaves") + ": use its palette as named tokens (CSS custom properties or one constants module), its type, shape "
         "and motion rules, and nothing from art.avoid. A deliberate departure goes in your submission notes with the reason."]
    if "play" in parts:
        L += ["Game feel is built in, not added later: implement every play.feedback pair (the action answers on screen and in sound in the same frame), "
              "the play.feel numbers as named constants in one place, and the play.curve steps at their times. Input is read every frame and never dropped; "
              "a fail is telegraphed before it lands; retry is one input and under a second.",
              "The first ten seconds teach by play: the player acts within three seconds of starting, with at most one line of instruction. No tutorial wall.",
              "Expose the run's state for measurement: window.__game = {state: 'title'|'playing'|'over', score, time, ...numbers that change during play}. "
              "PLAYCRAFT reads it; without it the play session is scored from pixels alone.",
              "Play it yourself at phone and desktop size before submitting, and tune play.feel by playing. Record the values you kept in direction.json's play.feel "
              "if they changed. Fun is not claimed: the play.playtest questions go to a person at release."]
    if "interaction" in parts:
        L += ["Design every state in interaction.states (empty, loading, error, success): none is left to a browser default or a blank screen.",
              "The primary task takes interaction.taps_to_value taps from opening the app; each interaction.feedback pair answers within 100 ms "
              "(pressed states, optimistic updates, focus that stays where the person is)."]
    if d in ("app", "site") or "art" in parts:
        L.append("Craft floor (ui-design skill, references/craft.md): one type scale, one spacing scale, touch targets ≥ 44 px, safe areas, visible focus, "
                 "reduced-motion respected, no layout shift on load. Look at it at iPhone and desktop size before submitting.")
    return L


def human_checks(D):
    """What only a person can answer. Listed at release under 'Needs a person'; never counted as passed."""
    out = []
    for q in ((D.get("play") or {}).get("playtest") or []):
        if isinstance(q, str) and q.strip(): out.append({"kind": "playtest", "question": q.strip()})
    if D.get("art"): out.append({"kind": "look", "question": "Does it look like the direction's concept (" + str((D["art"] or {}).get("concept"))[:90] + "), and like nothing in its avoid list?"})
    for x in D.get("done_when") or []:
        if isinstance(x, str) and x.strip(): out.append({"kind": "done", "question": x.strip()})
    return out
