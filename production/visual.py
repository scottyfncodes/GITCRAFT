"""VISUAL DIRECTION: picture-first, before anything is built (plan v3).

The person does three things: give references if they have them, pick a style, pick a design. Everything else is
GITCRAFT's. docs/visual-direction.md is the guide.

  atlas()                    the style atlas (production/kit/atlas): looks GITCRAFT produces well, each rendered as the same
                             two samples. A menu of what is possible, never a house style.
  named_style(text)          a style the request already names ("neon vector arcade", "like atlas look 7 but warmer")
  scope(spec)                which picks this production needs: style + design, design only (style named), or none
                             (an existing identity kept: its current best screen is the target)
  art_dir(project)           where the project keeps its art direction (references/, target/, shots.json live there)
  references(project)        the person's reference images (<art_dir>/references/)
  styles / designs / direction / moment / review / fix work orders, and their validators
  style_pick, design_pick    the two approvals: comparison pages, the recorded choice, the chosen frame saved as the target
  review_pack, review_gaps   the automatic visual review after the build: evidence pack, then gaps → work orders (≤ ROUNDS)
  look_page                  the chosen frame beside the shipped shots

The review is advisory judgement with teeth: its gaps become work orders, at most ROUNDS rounds, then what remains is
listed for the person with the screenshots. It never produces or changes a score, a release gate or the verdict, and
"observed" needs a capture it cites and viewed. Standard library only."""
import datetime, hashlib, html, json, os, re, shutil
from . import REPO

ATLAS_DIR = os.path.join(REPO, "production", "kit", "atlas")
IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif")
SHORTLIST = (6, 8)            # styles shown at the style pick
BROWSER = (390, 664)          # an iPhone 13 browser with its toolbars up: the real size a web product's first screen is seen at
DESIGNS = 3                   # designs shown at the design pick (two per style when two styles are compared)
MOMENTS = (2, 3)              # signature moments
ROUNDS = 2                    # visual review → work order rounds before the rest is listed for the person
ART_DIRS = ("docs/art-direction", "art-direction", "docs/art", "docs/brand")   # the first that exists wins
DEFAULT_ART_DIR = "art-direction"
SHOT_KINDS = ("title", "play", "moment", "fail", "results", "screen", "other")
STEP_KEYS = {"click", "tap", "selector", "fill", "press", "hold", "goto", "back", "wait", "expect", "eval", "text", "settle_ms"}
TELLS = {"gradient_text", "violet_gradient", "glow_shadow", "accent_stripe", "nested_cards", "emoji_icons", "eyebrow", "default_type"}
NEW_LOOK = re.compile(r"\b(new|fresh|different)\s+(look|style|visual|aesthetic|art direction)\b|\bredesign|\brestyle|\bre-skin|\breskin", re.I)
SCORE_KEYS = re.compile(r"^(score|scores|rating|ratings|points|grade|stars)$", re.I)
FEEL = re.compile(r"\b(fun|engag\w*|enjoy\w*|satisf\w*|addict\w*|compelling|delight\w*|boring|tedious|exciting|thrill\w*|immersive|rewarding|frustrat\w*)\b", re.I)
AGAINST = re.compile(r"^(target|style|moment:[a-z0-9-]+|reference:.+)$")


def _now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _json(p, d=None):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError, TypeError): return d


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def _said(v, n=10): return isinstance(v, str) and len(v.strip()) >= n


def _slug(s): return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


# ---------------------------------------------------------------- the atlas
def atlas():
    return _json(os.path.join(ATLAS_DIR, "atlas.json"), {"looks": [], "cannot": []})


def look(q):
    """A look by id, number or name (None if the atlas has no such look)."""
    for L in atlas()["looks"]:
        if str(q).strip().lower() in (L["id"], str(L["n"]), L["name"].lower()): return L
    return None


def named_style(text):
    """The atlas look a request already names, or None. Only an explicit name counts: the look's name, its number
    ("atlas look 7", "style #3"), or one of its `named_by` phrases. A subject word that happens to be a keyword ("a map
    app") does not name a style. → {look, n, name, modifier, matched}"""
    t = " " + (text or "").lower() + " "
    hit = None
    m = re.search(r"\b(?:atlas\s+)?(?:look|style)\s*(?:no\.?|number|#)?\s*(\d{1,2})\b", t)
    if m and look(m.group(1)): hit = (look(m.group(1)), m.group(0).strip(), m.end())
    if not hit:
        best = None
        for L in atlas()["looks"]:
            for ph in [L["name"].lower()] + [p.lower() for p in L.get("named_by") or []]:
                i = t.find(ph)
                if i >= 0 and re.match(r"\W", t[i - 1]) and re.match(r"\W", t[i + len(ph)]) and (best is None or len(ph) > len(best[1])):
                    best = (L, ph, i + len(ph))
        hit = best
    if not hit: return None
    L, matched, end = hit
    mod = re.match(r"\s*(?:look|style|aesthetic)?\s*,?\s*(?:but|only|just|and)\s+([^.;!?\n]{2,80})", t[end:])
    return {"look": L["id"], "n": L["n"], "name": L["name"], "matched": matched, "modifier": mod.group(1).strip() if mod else None}


def families(ids):
    by = {L["id"]: L["family"] for L in atlas()["looks"]}
    return {by[i] for i in ids if i in by}


# ---------------------------------------------------------------- where the project keeps its art direction
def art_dir(project):
    """The project-relative folder that holds the art direction: an existing one, else art-direction/."""
    for d in ART_DIRS:
        if project and os.path.isdir(os.path.join(project, d)): return d
    return DEFAULT_ART_DIR


def references(project):
    """The person's reference images: <art_dir>/references/ (one level of subfolders), each with its hash. A note per
    image may sit in references/notes.json ({file: note})."""
    if not project: return []
    d = os.path.join(project, art_dir(project), "references")
    if not os.path.isdir(d): return []
    notes = _json(os.path.join(d, "notes.json"), {}) or {}
    out = []
    for root, ds, fs in os.walk(d):
        if os.path.relpath(root, d).count(os.sep) >= 1: ds[:] = []
        for f in sorted(fs):
            if f.lower().endswith(IMG):
                p = os.path.join(root, f); rel = os.path.relpath(p, project)
                out.append({"file": rel, "sha256": sha(p), "note": notes.get(os.path.relpath(p, d)) or notes.get(f)})
    return out


def add_reference(project, image, note=None):
    """Save one reference image (pasted in chat, or any file) into <art_dir>/references/, never overwriting another picture:
    the same bytes are kept once, a different picture with the same name gets a numbered name. → the project-relative path."""
    if not os.path.isfile(image) or not image.lower().endswith(IMG) or not _img_size(image) and not image.lower().endswith(".gif"):
        raise ValueError(f"{image} is not an image file GITCRAFT can read (png, jpg, webp, gif)")
    d = os.path.join(project, art_dir(project), "references"); os.makedirs(d, exist_ok=True)
    h = sha(image)
    for f in os.listdir(d):
        if os.path.isfile(os.path.join(d, f)) and sha(os.path.join(d, f)) == h: dest = os.path.join(d, f); break
    else:
        stem, ext = os.path.splitext(os.path.basename(image)); dest, n = os.path.join(d, stem + ext.lower()), 1
        while os.path.exists(dest): n += 1; dest = os.path.join(d, f"{stem}-{n}{ext.lower()}")
        shutil.copyfile(image, dest)
    if note:
        notes = _json(os.path.join(d, "notes.json"), {}) or {}; notes[os.path.basename(dest)] = note
        with open(os.path.join(d, "notes.json"), "w") as f: json.dump(notes, f, indent=1)
    return os.path.relpath(dest, project)


# ---------------------------------------------------------------- scope
def scope(spec):
    """→ None (no visual stage), or {mode: pick|named|keep, pick_style, designs, named, art_dir}.
    pick:  a new product, a redesign or a "new look": six to eight styles, then three designs (two picks)
    named: the request names a style: no style pick, three designs in it (one pick)
    keep:  an existing project with an identity and no new look asked: no picks; its current best screen is the target"""
    from . import direction
    parts = direction.scope(spec) or []
    if "art" not in parts: return None
    mode = spec.get("mode") or {}
    text = " ".join(x for x in (mode.get("request"), spec.get("prompt")) if x)
    existing = bool(mode.get("existing"))
    proj = (spec.get("project") or {}).get("path")
    base = {"art_dir": art_dir(proj)}
    if existing and mode.get("focus") != "visual" and not NEW_LOOK.search(text):
        return dict(base, mode="keep", pick_style=False, designs=False, named=None)
    named = named_style(text)
    return dict(base, mode="named" if named else "pick", pick_style=not named, designs=True, named=named)


def product_kind(spec): return "game" if spec.get("deliverable") == "game" else "app"


# ---------------------------------------------------------------- work orders
def styles_work_order(spec, vs):
    game = product_kind(spec) == "game"
    rel = vs["art_dir"]
    return {
        "brief": f"The style pick for {spec['title']}: six to eight looks from the GITCRAFT style atlas, each rendered as the same key scene from THIS product.",
        "tools": ["the style atlas (production/kit/atlas: atlas.json, SCENE.md, render.mjs; the atlas page on the GITCRAFT site)",
                  "the look painters (canvas), MeshCraft for the 3D look (looks/low-poly-3d.sh)"],
        "instructions": [
            "Read the atlas: every look's name, what it suits, what is hard in it, and its two samples. The atlas is a menu of what GITCRAFT can do well, "
            "never a house style.",
            ("Write the product's key scene as scene.json in the atlas scene format (SCENE.md): a moment of play from THIS game (its hero, its world, its "
             "hazards and pickups, its HUD), not the atlas's runner." if game else
             "Write the product's main screen as scene.json in the atlas scene format (SCENE.md, the `app` fields): its real name, its real first-screen "
             "content and its real actions, not the atlas's ferry app."),
            f"Choose {SHORTLIST[0]} to {SHORTLIST[1]} looks that suit this product AND span different parts of the atlas: at least three families "
            "(vector, raster, type, 3d, shader). Do not pad the list with near-identical looks.",
            "Render each look with your scene: `node production/kit/atlas/render.mjs <this task folder>/styles <id,id,...> " + ("game" if game else "app")
            + " <this task folder>/scene.json` (the 3D look: render it with MeshCraft first, as looks/low-poly-3d.sh says). Open every render and look at it; "
            "replace a look whose render does not suit this product rather than showing it.",
            "Mark one as recommended with a one-line reason that names this product, and one as the wildcard: the look a 'surprise me' gets (the most unexpected "
            "look that could still work, never the recommended one).",
            f"References: the hand-off lists the person's reference images ({rel}/references/). For each, say what it suggests for the shortlist "
            "(`takes`) and what you leave out (`leaves`). Never copy a reference's layout or assets. No references is fine.",
            'Write styles.json: {"product": "' + ("game" if game else "app") + '", "scene": "scene.json", "recommended": "<look id>", "reason": "…", '
            '"wildcard": "<look id>", "styles": [{"look": "<id>", "image": "styles/<id>/' + ("game" if game else "app") + '.png", "why": "why it suits this product"}], '
            '"references": [{"file": "…", "takes": "…", "leaves": "…"}]}.'],
        "expected": [{"path": "styles.json", "format": "json", "keys": ["styles", "recommended", "reason", "wildcard"], "validate": "visual_styles", "role": "styles"}],
        "license": "owned by the project (rendered with GITCRAFT's atlas painters)"}


def designs_work_order(spec, vs):
    game = product_kind(spec) == "game"
    first = "the title screen (the first screen a player sees)" if game else "the main screen (the first screen a person uses)"
    return {
        "brief": f"Three genuinely different designs of {first} of {spec['title']}, inside the chosen style.",
        "tools": ["the ui-design skill (references/explore.md, craft.md, games.md)", "the atlas look's painter and fonts (production/kit/atlas)",
                  "vectorcraft / photocraft for marks, icons and textures", "production/kit/atlas/shoot.mjs (phone and desktop renders of an HTML file)"],
        "instructions": [
            "The chosen style is in the hand-off (style_selection.json): its atlas look, and the person's note if any. A named style may carry a modifier "
            "('but warmer'): honour it.",
            "Make three designs (two in each style when two styles are being compared) of the REAL first screen with real content: its real name, real "
            "text, real controls. They must differ in composition, type, palette and flavour, not just colour: any two share at most one of those four.",
            "Each design is one self-contained HTML file (inline CSS; fonts as files beside it, e.g. copied from production/kit/atlas/fonts with their notice) "
            "rendered as a phone really shows it (browser.png: 390x664, an iPhone browser with its toolbars up; design for THIS size first), full screen (phone.png, 390x844) and "
            "desktop (1440x900): `node production/kit/atlas/shoot.mjs <design>/index.html <design>` writes all three."
            + (" Also a play frame: the same design during play (play.png, at least 960x540), e.g. the atlas painter with this design's palette, or the HTML in a play state." if game else ""),
            "Follow the craft floor (ui-design references/craft.md): one type scale, one spacing scale, 44 px targets, safe areas, text contrast 4.5:1.",
            "Range is the point: three colourways of one layout are one design. Before you show them, shrink each title and each play frame to about 120 px wide in "
            "grayscale and compare (python3 -m production same-picture <a.png> <b.png>): if two read as the same picture, replace one. The gate measures this (layout "
            f"correlation below {SAME_PICTURE}) and also requires any two designs to differ in composition AND type AND palette.",
            "Give each design a plain name (two or three words a person would say) and a one-line idea; both are shown on the page.",
            "Look at every render at full size. If one design is clearly weaker, replace it rather than padding the choice. Recommend one, with a reason."]
            + (["App icon: draw one to three icon options FROM each design (its palette, its shapes, its idea), each a square PNG of at least 512 px (1024 preferred) that reads "
                "at 32 px: no tiny text, no screenshot. They are shown beside the design, and the person picks the look and the icon together (choice \"a:<icon id>\"). "
                'Add "icons": [{"id": "kite", "file": "a/icon-kite.png", "idea": "…"}] to each design and "icons_required": true to designs.json.'] if (spec.get("icon") or {}).get("required") and (spec.get("icon") or {}).get("mode") != "keep" else []) + [
            'Write designs.json: {"product": "' + ("game" if game else "app") + '", "style": "<look id>" (or one per design when comparing two), '
            '"recommended": "a", "reason": "…", "designs": [{"id": "a", "style": "<look id>", "name": "…", "idea": "one sentence from this product\'s world", '
            '"composition": "what leads, where the eye lands, the grid", "type": {"display": "…", "body": "…"}, '
            '"palette": {"background": "#rrggbb", "surface": "#rrggbb", "primary": "#rrggbb", "accent": "#rrggbb", "text": "#rrggbb"}, "flavor": "the feeling, in this product\'s words", '
            '"html": "a/index.html", "browser": "a/browser.png", "phone": "a/phone.png", "desktop": "a/desktop.png"' + (', "play": "a/play.png"' if game else "") + "}]}."],
        "expected": [{"path": "designs.json", "format": "json", "keys": ["designs", "recommended"], "validate": "visual_designs", "role": "designs"}],
        "license": "owned by the project"}


def direction_lines(spec, vs):
    """What the v3 direction work order adds: the direction is written FROM the chosen design and records where it came from."""
    rel = vs["art_dir"]
    game = product_kind(spec) == "game"
    keep = vs["mode"] == "keep"
    L = []
    if keep:
        L.append(f"This project keeps its established identity (no new look was asked for): its current best screen is the target. Build or serve it, capture that "
                 f"screen at phone and desktop size into {rel}/target/ (phone.png, desktop.png" + (", play.png" if game else "") + ") and write "
                 f"{rel}/target/target.json (which screen, and why it is the best), then write art.style as {{\"from\": \"kept\", \"look\": null, \"name\": \"the project's own identity\"}}.")
    else:
        L.append("Write the direction FROM the chosen design (design_selection.json in the hand-off, with the frame in the project's " + rel + "/target/): its palette, type, "
                 "composition and flavour become art.palette, art.type, art.shape and art.motion. Where the person said what they liked in the other designs "
                 "(the selection's note), fold that in and say where.")
    L += ["art.style: {look, name, design, from: picked|named|kept, modifier?}: the atlas look and the chosen design it came from. art.target: the target frame's "
          f"path in the project ({rel}/target/phone.png).",
          "art.references: one entry per reference image in the hand-off, {file, takes, leaves}: what the direction takes from it and what it leaves. "
          "Never copy a reference's layout or assets. [] when there are none.",
          "art.accept_tells: the PIXELCRAFT generic-design tells this style makes deliberate, each {id, reason} (the atlas lists the ones its look chooses, "
          "e.g. glow in a neon look, one mono face in a terminal look). The audit then lists them as accepted instead of questioning them. Only tells the "
          "style really uses.",
          f"art.moments: {MOMENTS[0]} or {MOMENTS[1]} signature moments for THIS product, each {{id, name, what, why}} (for example the title reveal, the "
          "first " + ("win" if game else "success") + ", the results screen). Each gets its own work order and its own capture.",
          f"The shot list: write {rel}/shots.json in the project (the format is in docs/visual-direction.md): named shots with the scripted steps that "
          "reach each one and a wait for REAL content (a selector, text or a JS condition such as window.__game.state === 'playing'), never a fixed delay "
          "over a loading screen. " + ("At least: title fully loaded, mid-play, one shot per moment, fail, results." if game else
                                         "At least: the main screens, one shot per moment, and an empty or error state.")
          + " PIXELCRAFT, PLAYCRAFT and the visual review all use it; a shot that cannot be reached is reported as not seen, never judged."]
    return L


def direction_expected(vs):
    return [{"path": f"$project/{vs['art_dir']}/shots.json", "format": "json", "keys": ["shots"], "validate": "visual_shots", "role": "shots"}]


def moment_work_order(spec, m, shot):
    return {"brief": f"Signature moment: {m.get('name')} — {m.get('what')}",
            "instructions": [f"Build this moment so it is unmistakable and made for {spec['title']}: {m.get('what')} (why it matters: {m.get('why')}).",
                             "Hold it to the art direction (direction.json and the target frame in the hand-off): palette, type, shape and motion.",
                             f"It is captured as shot `{shot or m.get('id')}` from the shot list; make sure the shot's steps still reach it and its wait still "
                             "matches real content. Submit the files you changed."],
            "expected": [], "license": "owned by the project"}


def review_work_order(spec, rnd):
    return {"brief": f"Visual review{' (round ' + str(rnd) + ')' if rnd else ''}: does the built product look like what was chosen?",
            "tools": ["the pack (pack.json + BRIEF.md in the hand-off)", "the Read tool, to open every image you cite"],
            "instructions": [
                "Read BRIEF.md. Open the chosen frame, the style sample, the references and every reached shot, and compare the shots against them: the "
                "chosen frame first, then the style, the references and each signature moment.",
                "A shot that was not reached is listed as not seen: never judge it, and never cite its image.",
                "Open EVERY reached shot, every round, at full size, and answer the four checks for each (`checks`): text readable on textured or hatched ground; nothing "
                "rotated, clipped or tiny without a reason from the style; the thing the player controls never hidden by the HUD; credits and bylines somewhere deliberate.",
                "Judge each signature moment from its sequence (before, peak, after), as an event at phone size (`moments`): a small label appearing is not a moment. "
                "If it does not land, that is a gap against moment:<id>.",
                "After a round of fixes every shot has been shot again: say for each earlier gap whether it is closed (`previous`), and look for new gaps the fixes caused.",
                "List what matches (with evidence) and every visible gap as {id, shot, against, gap, fix, evidence, basis: observed_render, severity: major|minor}. "
                "A gap is something a person would see in the screenshot (a colour that is not the palette, type that is not the chosen face, a composition "
                "that lost its focal point, a moment that does not read). The fix says what to change in the project.",
                "No scores, ratings or points. Fun, engaging and similar are playtest hypotheses, never observations. Say 'assessment', never 'verdict'.",
                "Write review.json and submit it."],
            "expected": [{"path": "review.json", "format": "json", "keys": ["reviewer", "coverage", "summary", "checks", "matches", "gaps"], "validate": "visual_review", "role": "review"}],
            "license": "advisory judgement (no score)"}


def fix_work_order(gaps, rnd, art_rel):
    return {"brief": f"Close the visual gaps the review found (round {rnd} of {ROUNDS}).",
            "findings": [f"[{g.get('severity', 'minor')}] {g.get('shot')} vs {g.get('against')}: {g.get('gap')} — fix: {g.get('fix')}" for g in gaps],
            "instructions": ["Change the project so each gap closes; keep every feature and the art direction (direction.json, " + art_rel + "/target/).",
                             "The shot list is captured again and reviewed after your submission. Submit the files you changed."],
            "expected": [], "license": "owned by the project"}


# ---------------------------------------------------------------- validators (gates.check_expected: fn(path, base[, project]))
def _check(out, name, ok, detail=None): out.append({"name": name, "ok": bool(ok), "detail": detail})


def _png_size(p):
    try:
        with open(p, "rb") as f: d = f.read(24)
        if d[:8] == b"\x89PNG\r\n\x1a\n": return int.from_bytes(d[16:20], "big"), int.from_bytes(d[20:24], "big")
    except OSError: pass
    return None


def _img_size(p):
    s = _png_size(p)
    if s: return s
    try:
        with open(p, "rb") as f: d = f.read()
        if d[:2] == b"\xff\xd8":   # JPEG: walk to the first SOF marker
            i = 2
            while i < len(d) - 9:
                if d[i] != 0xFF: i += 1; continue
                mk = d[i + 1]; ln = int.from_bytes(d[i + 2:i + 4], "big")
                if mk in (0xC0, 0xC1, 0xC2): return int.from_bytes(d[i + 7:i + 9], "big"), int.from_bytes(d[i + 5:i + 7], "big")
                i += 2 + ln
        if d[:4] == b"RIFF" and d[8:12] == b"WEBP" and d[12:16] == b"VP8X": return 1 + int.from_bytes(d[24:27], "little"), 1 + int.from_bytes(d[27:30], "little")
    except OSError: pass
    return None


def _abs(base, p): return p if os.path.isabs(p) else os.path.join(base, p)


def validate_styles(path, base=None):
    out = []
    D = _json(path)
    if not isinstance(D, dict): return [{"name": "styles.json opens as a JSON object", "ok": False, "detail": None}]
    base = base or os.path.dirname(path)
    S = [s for s in D.get("styles") or [] if isinstance(s, dict)]
    ids = [s.get("look") for s in S]
    _check(out, f"{SHORTLIST[0]} to {SHORTLIST[1]} styles", SHORTLIST[0] <= len(S) <= SHORTLIST[1], f"{len(S)} found")
    unknown = [i for i in ids if not look(i) or look(i)["id"] != i]
    _check(out, "every style is an atlas look (by id)", not unknown, unknown or None)
    _check(out, "no look twice", len(set(ids)) == len(ids), None)
    fam = families(ids)
    _check(out, "the shortlist spans at least three atlas families", len(fam) >= 3, sorted(fam))
    bad, hashes = [], {}
    for s in S:
        p = _abs(base, str(s.get("image") or ""))
        sz = _img_size(p) if os.path.isfile(p) else None
        if not sz or sz[0] < 640: bad.append(f"{s.get('look')}: {s.get('image')} " + ("missing" if not os.path.isfile(p) else f"too small {sz}"))
        else: hashes.setdefault(sha(p), []).append(s.get("look"))
    _check(out, "every style has its render of this product's scene (≥ 640 px wide)", not bad, bad or None)
    dup = [v for v in hashes.values() if len(v) > 1]
    _check(out, "every render is a different picture", not dup, dup or None)
    _check(out, "every style says why it suits this product", all(_said(s.get("why"), 12) for s in S), [s.get("look") for s in S if not _said(s.get("why"), 12)] or None)
    _check(out, "one recommendation, with a one-line reason", D.get("recommended") in ids and _said(D.get("reason"), 12), D.get("recommended"))
    _check(out, "a wildcard for 'surprise me' that is not the recommendation", D.get("wildcard") in ids and D.get("wildcard") != D.get("recommended"), D.get("wildcard"))
    refs = D.get("references") or []
    _check(out, "every reference says what it takes and what it leaves", all(isinstance(r, dict) and _said(r.get("takes"), 6) and _said(r.get("leaves"), 4) for r in refs), None)
    return out


def _palette(d):
    p = d.get("palette") if isinstance(d.get("palette"), dict) else {}
    return {k: str(p.get(k) or "").lower() for k in ("background", "surface", "primary", "accent", "text")}


def _cdist(a, b):
    try: return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (1, 3, 5))
    except (ValueError, TypeError): return 0


def _words(s): return set(re.findall(r"[a-z]{3,}", str(s or "").lower()))


def _differs(a, b):
    """The four axes two designs can differ on, each measured from what the designs declare."""
    pa, pb = _palette(a), _palette(b)
    pal = max(_cdist(pa["background"], pb["background"]), _cdist(pa["primary"], pb["primary"])) >= 90
    ta, tb = a.get("type") or {}, b.get("type") or {}
    typ = str(ta.get("display") or "").lower().strip() != str(tb.get("display") or "").lower().strip()
    wa, wb = _words(a.get("composition")), _words(b.get("composition"))
    comp = bool(wa and wb) and len(wa & wb) / max(1, len(wa | wb)) < 0.5
    fa, fb = _words(a.get("flavor")), _words(b.get("flavor"))
    flav = bool(fa and fb) and len(fa & fb) / max(1, len(fa | fb)) < 0.5
    return {"composition": comp, "type": typ, "palette": pal, "flavor": flav}


def _thumb_diff(pa, pb):
    """Mean absolute difference (0..1) of two renders shrunk to 24x48: the pictures themselves must differ, not only their notes."""
    try:
        from . import icons
        A, B = icons.decode(pa), icons.decode(pb)
        ra, rb = icons.resize(A[0], A[1], A[2], 24, 48), icons.resize(B[0], B[1], B[2], 24, 48)
        return round(sum(abs(ra[i] - rb[i]) for i in range(len(ra)) if i % 4 != 3) / (24 * 48 * 3 * 255), 3)
    except Exception: return None


SAME_PICTURE = 0.6   # ink-layout correlation at 120 px grayscale above which two frames read as the same picture


def ink_layout(p, w=120, cell=10):
    """Where the ink is, whatever the colours: the frame shrunk to 120 px wide in grayscale, each pixel's distance from the
    frame's own median grey (so a light and a dark colourway of one layout give the same map), averaged over 10 px cells."""
    from . import icons
    W, H, px = icons.decode(p); h = max(cell, round(H * w / W)); r = icons.resize(W, H, px, w, h)
    g = [(0.299 * r[i] + 0.587 * r[i + 1] + 0.114 * r[i + 2]) / 255 for i in range(0, len(r), 4)]
    med = sorted(g)[len(g) // 2]
    d = [abs(x - med) for x in g]
    return [sum(d[(cy * cell + y) * w + cx * cell + x] for y in range(cell) for x in range(cell)) / (cell * cell)
            for cy in range(h // cell) for cx in range(w // cell)]


def same_picture(pa, pb):
    """Correlation (−1..1) of two frames' ink layouts, or None when a frame cannot be read. ≥ SAME_PICTURE: one picture, recoloured."""
    try: A, B = ink_layout(pa), ink_layout(pb)
    except Exception: return None
    n = min(len(A), len(B)); A, B = A[:n], B[:n]
    if not n: return None
    ma, mb = sum(A) / n, sum(B) / n
    va, vb = sum((x - ma) ** 2 for x in A) / n, sum((x - mb) ** 2 for x in B) / n
    if va < 1e-9 or vb < 1e-9: return 1.0 if va < 1e-9 and vb < 1e-9 else 0.0
    return round(sum((x - ma) * (y - mb) for x, y in zip(A, B)) / n / (va * vb) ** 0.5, 2)


def validate_designs(path, base=None):
    out = []
    D = _json(path)
    if not isinstance(D, dict): return [{"name": "designs.json opens as a JSON object", "ok": False, "detail": None}]
    base = base or os.path.dirname(path)
    game = D.get("product") == "game"
    X = [d for d in D.get("designs") or [] if isinstance(d, dict)]
    ids = [d.get("id") for d in X]
    _check(out, "three designs (four when two styles are compared)", len(X) in (DESIGNS, 4), f"{len(X)} found")
    _check(out, "every design has its own id", len(set(ids)) == len(ids) and all(ids), ids)
    _check(out, "every design names its atlas style", all(look(d.get("style") or D.get("style")) for d in X), None)
    miss = []
    for d in X:
        for k in ("phone", "browser", "desktop") + (("play",) if game else ()):
            p = _abs(base, str(d.get(k) or ""))
            sz = _img_size(p) if d.get(k) and os.path.isfile(p) else None
            if not sz: miss.append(f"{d.get('id')}.{k}"); continue
            if k in ("phone", "browser") and not sz[1] > sz[0]: miss.append(f"{d.get('id')}.{k} is not portrait {sz}")
            if k == "browser" and abs(sz[1] / sz[0] - BROWSER[1] / BROWSER[0]) > 0.03: miss.append(f"{d.get('id')}.browser is not {BROWSER[0]}x{BROWSER[1]} {sz}")
            if k in ("desktop", "play") and not sz[0] > sz[1]: miss.append(f"{d.get('id')}.{k} is not landscape {sz}")
        if not os.path.isfile(_abs(base, str(d.get("html") or ""))): miss.append(f"{d.get('id')}.html")
    _check(out, f"every design: its HTML, a full-screen phone render, the same screen in a real phone browser ({BROWSER[0]}x{BROWSER[1]}, toolbars up) and a desktop render"
           + (", and a play frame" if game else ""), not miss, miss or None)
    _check(out, "every design has a plain name and a one-line idea", all(_said(d.get("name"), 3) and _said(d.get("idea"), 12) and len(str(d.get("idea"))) <= 160 for d in X),
           [d.get("id") for d in X if not (_said(d.get("name"), 3) and _said(d.get("idea"), 12) and len(str(d.get("idea"))) <= 160)] or None)
    _check(out, "every design states its idea, composition, type, palette and flavour",
           all(_said(d.get("idea"), 12) and _said(d.get("composition"), 12) and (d.get("type") or {}).get("display") and _said(d.get("flavor"), 6)
               and all(re.fullmatch(r"#[0-9a-f]{6}", v) for v in _palette(d).values()) for d in X), None)
    weak = []
    for i in range(len(X)):
        for j in range(i + 1, len(X)):
            if (X[i].get("style") or D.get("style")) != (X[j].get("style") or D.get("style")): continue   # two styles compared: different by construction
            ax = _differs(X[i], X[j])
            if not (ax["composition"] and ax["type"] and ax["palette"]): weak.append(f"{ids[i]}/{ids[j]} share {[k for k in ('composition', 'type', 'palette') if not ax[k]]}")
    _check(out, "any two designs differ in composition AND type AND palette (a colourway is not a design)", not weak, weak or None)
    for k, label in (("phone", "title"),) + ((("play", "play frame"),) if game else ()):   # shrunk to 120 px, in grayscale: do two read as one picture?
        same = []
        fr = [(d.get("id"), _abs(base, str(d.get(k) or ""))) for d in X]
        for i in range(len(fr)):
            for j in range(i + 1, len(fr)):
                if os.path.isfile(fr[i][1]) and os.path.isfile(fr[j][1]):
                    v = same_picture(fr[i][1], fr[j][1]); t = _thumb_diff(fr[i][1], fr[j][1])
                    if (v is not None and v >= SAME_PICTURE) or (t is not None and t < 0.06): same.append(f"{fr[i][0]}/{fr[j][0]}: layout correlation {v}")
        _check(out, f"at 120 px in grayscale no two {label}s read as the same picture (below {SAME_PICTURE})", not same, same or None)
    ic = [(d.get("id"), i) for d in X for i in d.get("icons") or []]
    need_icons = bool(D.get("icons_required")) or bool(ic)
    if need_icons:
        bad = []
        for d in X:
            opts = d.get("icons") or []
            if not 1 <= len(opts) <= 3: bad.append(f"{d.get('id')}: {len(opts)} icon option(s)")
            for o in opts:
                ip = _abs(base, str((o or {}).get("file") or "")); sz = _img_size(ip) if os.path.isfile(ip) else None
                if not sz or sz[0] != sz[1] or sz[0] < 512 or not (o.get("id") and _said(o.get("idea"), 6)): bad.append(f"{d.get('id')}/{(o or {}).get('id')}: {sz or 'missing'}")
        _check(out, "every design brings one to three app icon options drawn from it (square, at least 512 px, each with an id and its idea)", not bad, bad or None)
        hs = {}
        for d in X:
            for o in d.get("icons") or []:
                ip = _abs(base, str((o or {}).get("file") or ""))
                if os.path.isfile(ip): hs.setdefault(sha(ip), []).append(f"{d.get('id')}/{o.get('id')}")
        _check(out, "every icon option is its own picture", not [v for v in hs.values() if len(v) > 1], [v for v in hs.values() if len(v) > 1] or None)
    _check(out, "one recommendation with a reason", D.get("recommended") in ids and _said(D.get("reason"), 12), D.get("recommended"))
    sel = _json(os.path.join(base, "style_selection.json"))
    if sel and sel.get("styles"):   # the person's pick, handed on beside the work
        picked = list(sel["styles"]); per = {st: sum(1 for d in X if (d.get("style") or D.get("style")) == st) for st in picked}
        want = {picked[0]: DESIGNS} if len(picked) == 1 else {st: 2 for st in picked}
        _check(out, "the designs are in the picked style" + ("s, two each" if len(picked) > 1 else ", three of them"),
               per == want and all((d.get("style") or D.get("style")) in picked for d in X), per)
    return out


def validate_shots(path, base=None):
    out = []
    D = _json(path)
    if not isinstance(D, dict): return [{"name": "shots.json opens as a JSON object", "ok": False, "detail": None}]
    S = [s for s in D.get("shots") or [] if isinstance(s, dict)]
    ids = [s.get("id") for s in S]
    _check(out, "shot ids are unique slugs", all(isinstance(i, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", i) for i in ids) and len(set(ids)) == len(ids), ids)
    _check(out, "every shot has a name and a kind", all(_said(s.get("name"), 3) and s.get("kind") in SHOT_KINDS for s in S),
           [s.get("id") for s in S if s.get("kind") not in SHOT_KINDS] or None)
    bad = [s.get("id") for s in S if not isinstance(s.get("steps", []), list) or any(not isinstance(x, dict) or not set(x) <= STEP_KEYS for x in s.get("steps", []))]
    _check(out, "steps use the shared vocabulary (" + ", ".join(sorted(STEP_KEYS)) + ")", not bad, bad or None)
    nowait = [s.get("id") for s in S if not isinstance(s.get("wait_for"), dict) or not any(_said(s["wait_for"].get(k), 2) for k in ("selector", "text", "js"))]
    _check(out, "every shot waits for real content (a selector, text or JS condition), not a fixed delay", not nowait, nowait or None)
    kinds = {s.get("kind") for s in S}
    need = {"title", "play", "fail", "results"} if D.get("product") == "game" else {"screen"}
    _check(out, "the shots a " + ("game" if D.get("product") == "game" else "product") + " needs: " + ", ".join(sorted(need)), need <= kinds, sorted(need - kinds) or None)
    fl, rs = [s for s in S if s.get("kind") == "fail"], [s for s in S if s.get("kind") == "results"]
    if fl and rs:
        _check(out, "the fail shot waits for the instant of failing, not for the results screen (its wait_for differs from every results shot's)",
               all(f.get("wait_for") != r.get("wait_for") for f in fl for r in rs), [f.get("id") for f in fl if any(f.get("wait_for") == r.get("wait_for") for r in rs)] or None)
    return out


def validate_direction(path, base=None, project=None):
    """The direction gate (production/direction.py) plus what a picture-first direction records."""
    from . import direction
    out = direction.validate(path, base)
    D = _json(path) or {}
    A = D.get("art") if isinstance(D.get("art"), dict) else {}
    st = A.get("style") if isinstance(A.get("style"), dict) else {}
    kept = st.get("from") == "kept"
    _check(out, "art.style: the atlas look and the design it came from (or the kept identity)",
           st.get("from") in ("picked", "named", "kept") and (kept or (look(st.get("look") or "") and st.get("design"))), st or None)
    tgt = A.get("target")
    tp = os.path.join(project or "", tgt) if tgt and not os.path.isabs(tgt) else tgt
    _check(out, "art.target: the chosen frame is saved in the project", bool(tp) and os.path.isfile(tp) and bool(_img_size(tp)), tgt)
    refs = A.get("references")
    _check(out, "art.references: what is taken from and left out of each reference ([] if none)",
           isinstance(refs, list) and all(isinstance(r, dict) and r.get("file") and _said(r.get("takes"), 6) and _said(r.get("leaves"), 4) for r in refs), None)
    if project:
        have = {r["file"] for r in references(project)}
        named = {r.get("file") for r in refs or [] if isinstance(r, dict)}
        _check(out, "art.references covers every reference image in the project", have <= named, sorted(have - named) or None)
    acc = A.get("accept_tells") or []
    _check(out, "art.accept_tells: known PIXELCRAFT tells, each with the reason the style chooses it",
           isinstance(acc, list) and all(isinstance(t, dict) and t.get("id") in TELLS and _said(t.get("reason"), 8) for t in acc), None)
    M = [m for m in A.get("moments") or [] if isinstance(m, dict) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(m.get("id") or "")) and _said(m.get("name"), 3) and _said(m.get("what"), 12)]
    _check(out, f"art.moments: {MOMENTS[0]} or {MOMENTS[1]} signature moments, each with an id, a name and what happens",
           MOMENTS[0] <= len(M) == len(A.get("moments") or []) <= MOMENTS[1], f"{len(M)} found")
    if project:
        sp = os.path.join(project, A.get("shots") or os.path.join(art_dir(project), "shots.json"))
        shots = (_json(sp) or {}).get("shots") or []
        missing = [m["id"] for m in M if not any(s.get("moment") == m["id"] for s in shots if isinstance(s, dict))]
        _check(out, "the shot list has a shot for every moment", os.path.isfile(sp) and not missing, missing or (None if os.path.isfile(sp) else f"{sp} missing"))
    return out


validate_direction.wants_project = True


def validate_review(path, base=None):
    """The in-production visual review against its pack: the Creative Review's rules plus visual gaps."""
    R = _json(path)
    K = _json(os.path.join(base or os.path.dirname(path), "pack.json")) or _json((R or {}).get("pack") or "")
    if not isinstance(R, dict): return [{"name": "review.json opens as a JSON object", "ok": False, "detail": None}]
    if not K: return [{"name": "the review's pack (pack.json beside it, or `pack`) can be read", "ok": False, "detail": None}]
    errs = review_errors(R, K)
    return [{"name": "the review follows the visual review rules (no scores; observed needs a viewed capture; unreached shots are never judged)",
             "ok": not errs, "detail": errs[:12] or None}]


VALIDATORS = {"visual_styles": validate_styles, "visual_designs": validate_designs, "visual_shots": validate_shots,
              "direction_visual": validate_direction, "visual_review": validate_review}


# ---------------------------------------------------------------- pages (neutral frame: the candidates are the only colour)
CSS = """:root{color-scheme:light dark;--bg:#f3f2ee;--fg:#1c1c1a;--muted:#62625c;--line:#d8d7d1;--card:#fff;--pick:#1c1c1a}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--fg:#ecebe6;--muted:#a3a29b;--line:#34332f;--card:#1f1f1d;--pick:#ecebe6}}
:root[data-theme=dark]{--bg:#151514;--fg:#ecebe6;--muted:#a3a29b;--line:#34332f;--card:#1f1f1d;--pick:#ecebe6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1240px;margin:0 auto;padding:28px 16px 64px}
h1{font-size:28px;line-height:1.15;margin:0 0 6px;letter-spacing:-.01em}h2{font-size:19px;margin:0 0 4px}
.lede{color:var(--muted);max-width:68ch;margin:0 0 22px}.meta{color:var(--muted);font-size:14px;margin:0}
a{color:inherit}.crumbs{font-size:14px;color:var(--muted);margin-bottom:14px}.crumbs a{color:var(--muted)}
.grid{display:grid;gap:22px;grid-template-columns:repeat(auto-fill,minmax(min(100%,340px),1fr))}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.card img{display:block;width:100%;height:auto;background:#000}.card .body{padding:14px 16px 16px;display:grid;gap:8px}.card .body p{margin:0}
.card.chosen{outline:3px solid var(--pick);outline-offset:3px}
.tag{display:inline-block;font-size:12px;font-weight:650;padding:2px 8px;border:1px solid currentColor;border-radius:99px;margin-right:6px;vertical-align:2px;white-space:nowrap}
.sw{display:inline-block;width:20px;height:20px;border-radius:5px;margin-right:4px;border:1px solid rgba(127,127,127,.35);vertical-align:-4px}
.pair{display:grid;gap:14px;grid-template-columns:minmax(0,1fr) minmax(0,2.2fr);align-items:start}
.pair figure{margin:0}.pair img{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--line)}
figcaption{font-size:13px;color:var(--muted);margin-top:6px}
.frames{display:grid;gap:14px;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,2.1fr);align-items:start;margin-top:12px}.frames figure{margin:0}
.frames img{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--line)}.idea{font-size:18px;margin:2px 0 6px}
.sub{font-size:14px;margin:18px 0 8px;color:var(--muted);font-weight:650}.icons{display:flex;flex-wrap:wrap;gap:18px}
.icon{margin:0;display:grid;grid-template-columns:96px 32px;gap:10px;align-items:end;max-width:260px}.icon img{width:96px;height:96px;border-radius:22%;border:1px solid var(--line)}
.icon img.small{width:32px;height:32px}.icon figcaption{grid-column:1/-1}
@media (max-width:700px){.frames{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.frames>div{grid-column:1/-1}}
.seq{grid-column:1/-1;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;max-width:640px}.seq figure{margin:0}
.design{border-top:1px solid var(--line);padding:26px 0}.design:first-of-type{border-top:0}
.compare{display:grid;gap:18px;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;margin:14px 0 6px}
.compare h3{font-size:14px;margin:0 0 8px;color:var(--muted);font-weight:650}.compare img{width:100%;height:auto;display:block;border-radius:10px;border:1px solid var(--line)}
.notseen{display:grid;place-items:center;aspect-ratio:9/19;border:1px dashed var(--line);border-radius:10px;color:var(--muted);font-size:14px;padding:16px;text-align:center}
.status{border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:0 0 22px;background:var(--card)}
ul.gaps{padding-left:18px}ul.gaps li{margin:0 0 8px}
@media (max-width:700px){.pair,.compare{grid-template-columns:minmax(0,1fr)}h1{font-size:24px}}"""


def _page(title, body, desc=""):
    e = html.escape
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>"
            f"<title>{e(title)}</title><meta name=description content='{e(desc)}'><style>{CSS}</style></head><body><main>{body}</main></body></html>\n")


def _copy(src, dest_dir, name):
    os.makedirs(dest_dir, exist_ok=True)
    d = os.path.join(dest_dir, name)
    if os.path.realpath(src) != os.path.realpath(d): shutil.copyfile(src, d)
    return d


def _swatches(pal):
    return "".join(f"<span class=sw style='background:{html.escape(v)}' title='{html.escape(k)} {html.escape(v)}'></span>"
                   for k, v in (pal or {}).items() if re.fullmatch(r"#[0-9a-fA-F]{6}", str(v)))


def style_page(styles, base, out_dir, title, chosen=None, how=None, crumbs=""):
    """The style pick: every shortlisted look rendered as this product's scene, the recommendation marked with its reason."""
    e = html.escape
    rec, wild = styles.get("recommended"), styles.get("wildcard")
    cards = []
    for s in styles.get("styles") or []:
        L = look(s["look"]) or {"name": s["look"], "n": "?", "family": "", "suits": "", "hard": ""}
        img = _abs(base, s["image"]); ext = os.path.splitext(img)[1]
        rel = os.path.relpath(_copy(img, os.path.join(out_dir, "styles"), f"{s['look']}{ext}"), out_dir)
        tags = (f"<span class=tag>recommended</span>" if s["look"] == rec else "") + (f"<span class=tag>surprise me</span>" if s["look"] == wild else "") \
            + (f"<span class=tag>picked</span>" if chosen and s["look"] in chosen else "")
        cards.append(f"<article class='card{' chosen' if chosen and s['look'] in chosen else ''}' id='{e(s['look'])}'><img src='{e(rel)}' alt='{e(title)} in {e(L['name'])}' loading=lazy>"
                     f"<div class=body><h2>{e(str(L['n']))} · {e(L['name'])} {tags}</h2><p>{e(s.get('why') or '')}</p>"
                     f"<p class=meta>Atlas: {e(L.get('suits') or '')}</p><p class=meta>Hard: {e(L.get('hard') or '')}</p></div></article>")
    status = (f"<p class=status><b>Picked:</b> {', '.join(e((look(c) or {}).get('name', c)) for c in chosen)}"
              f"{' (' + e(how) + ')' if how else ''}</p>") if chosen else \
        (f"<p class=status><b>Recommended:</b> {e((look(rec) or {}).get('name', str(rec)))}. {e(styles.get('reason') or '')}<br>"
         f"Pick one, or two to compare, or say “surprise me” ({e((look(wild) or {}).get('name', str(wild)))}).</p>")
    refs = styles.get("references") or []
    rs = ("<h2 style='margin-top:30px'>References</h2><ul class=gaps>" + "".join(f"<li><b>{e(r['file'])}</b>: takes {e(r['takes'])}; leaves {e(r['leaves'])}</li>" for r in refs) + "</ul>") if refs else ""
    body = (f"{crumbs}<h1>{e(title)}: pick a style</h1><p class=lede>{len(styles.get('styles') or [])} looks from the GITCRAFT style atlas, each rendered as the "
            f"same moment from this product. Nothing is built until a design is picked.</p>{status}<div class=grid>{''.join(cards)}</div>{rs}")
    p = os.path.join(out_dir, "index.html")
    with open(p, "w") as f: f.write(_page(f"{title} style pick", body, "Style pick: the shortlist from the GITCRAFT style atlas"))
    return p


def split_design_choice(choice, designs):
    """A design choice: "a" (the design with its first icon) or "a:kite" (the design with that icon option). → (design, icon option or None)"""
    did, _, iid = str(choice or designs.get("recommended") or "").partition(":")
    d = next((x for x in designs.get("designs") or [] if x.get("id") == did.strip()), None)
    if not d: raise ValueError(f"{choice!r} is not one of the designs {[x.get('id') for x in designs.get('designs') or []]}")
    opts = d.get("icons") or []
    ic = next((o for o in opts if o.get("id") == iid.strip()), None) if iid.strip() else (opts[0] if opts else None)
    if iid.strip() and not ic: raise ValueError(f"design {did} has no icon option {iid!r} (its icons: {[o.get('id') for o in opts]})")
    return d, ic


def design_page(designs, base, out_dir, title, chosen=None, note=None, crumbs="", icon=None):
    """The design pick: three designs of the real first screen, each with a plain name and its one-line idea, shown as a phone
    really shows it (browser toolbars up), full screen, at desktop size, during play (a game), and with the app icon options
    drawn from it: the look and the icon are chosen together."""
    e = html.escape
    rec = designs.get("recommended")
    secs = []
    for d in designs.get("designs") or []:
        L = look(d.get("style") or designs.get("style")) or {"name": d.get("style")}
        dd = os.path.join(out_dir, d["id"])
        cp = lambda k: os.path.relpath(_copy(_abs(base, d[k]), dd, k + os.path.splitext(d[k])[1]), out_dir) if d.get(k) else None
        ph, br, dk, pl = cp("phone"), cp("browser"), cp("desktop"), cp("play")
        ty = d.get("type") or {}
        tags = ("<span class=tag>recommended</span>" if d["id"] == rec else "") + ("<span class=tag>picked</span>" if chosen == d["id"] else "")
        icons = ""
        if d.get("icons"):
            cells = []
            for o in d["icons"]:
                rel = os.path.relpath(_copy(_abs(base, o["file"]), os.path.join(dd, "icons"), o["id"] + os.path.splitext(o["file"])[1]), out_dir)
                mark = " <span class=tag>picked</span>" if chosen == d["id"] and icon == o["id"] else ""
                cells.append(f"<figure class=icon><img src='{e(rel)}' alt='App icon {e(o['id'])} for design {e(d['id'])}' loading=lazy><img class=small src='{e(rel)}' alt=''>"
                             f"<figcaption><b>{e(d['id'])}:{e(o['id'])}</b>{mark}<br>{e(o.get('idea') or '')}</figcaption></figure>")
            icons = "<h3 class=sub>App icon, drawn from this design</h3><div class=icons>" + "".join(cells) + "</div>"
        secs.append(f"<section class='design' id='{e(d['id'])}'><h2>{e(d['id'].upper())} · {e(d.get('name') or '')} {tags}</h2>"
                    f"<p class=idea>{e(d.get('idea') or '')}</p><p class=meta>Composition: {e(d.get('composition') or '')}</p>"
                    f"<p class=meta>Type: {e(str(ty.get('display') or ''))} / {e(str(ty.get('body') or ''))} · Flavour: {e(d.get('flavor') or '')} · Style: {e(L.get('name') or '')} · {_swatches(d.get('palette'))}</p>"
                    "<div class=frames>"
                    + (f"<figure><img src='{e(br)}' alt='Design {e(d['id'])} in a phone browser' loading=lazy><figcaption>On a phone, as the browser shows it ({BROWSER[0]}×{BROWSER[1]})</figcaption></figure>" if br else "")
                    + (f"<figure><img src='{e(ph)}' alt='Design {e(d['id'])} full screen on a phone' loading=lazy><figcaption>Full screen (390×844)</figcaption></figure>" if ph else "")
                    + "<div style='display:grid;gap:14px'>"
                    + (f"<figure><img src='{e(pl)}' alt='Design {e(d['id'])} during play' loading=lazy><figcaption>During play</figcaption></figure>" if pl else "")
                    + (f"<figure><img src='{e(dk)}' alt='Design {e(d['id'])} at desktop size' loading=lazy><figcaption>Desktop 1440×900</figcaption></figure>" if dk else "")
                    + f"</div></div>{icons}</section>")
    has_icons = any(d.get("icons") for d in designs.get("designs") or [])
    status = (f"<p class=status><b>Picked:</b> design {e(chosen.upper())}" + (f" with icon {e(icon)}" if icon else "") + (f". What they liked in the others: {e(note)}" if note else "") + "</p>") if chosen else \
        (f"<p class=status><b>Recommended:</b> design {e(str(rec).upper())}. {e(designs.get('reason') or '')}<br>Pick one" + (" and its icon (for example “a:kite”)" if has_icons else "")
         + ", and say what you liked in the others. That is the approval: the build starts from it.</p>")
    body = (f"{crumbs}<h1>{e(title)}: pick a design</h1><p class=lede>Three designs of the real first screen inside the chosen style. They differ in composition, "
            f"type and palette, on the title and during play" + ("; each brings its own app icon" if has_icons else "") + f".</p>{status}{''.join(secs)}")
    p = os.path.join(out_dir, "index.html")
    with open(p, "w") as f: f.write(_page(f"{title} design pick", body, "Design pick: three designs of the first screen"))
    return p


def look_page(target, shots, out_dir, title, style=None, live_url=None, remaining=None, crumbs=""):
    """The chosen frame beside the shipped screens. target: {phone, desktop, play?} paths; shots: shot report (reached and not)."""
    e = html.escape
    os.makedirs(out_dir, exist_ok=True)
    tg = {k: os.path.relpath(_copy(v, os.path.join(out_dir, "target"), k + os.path.splitext(v)[1]), out_dir) for k, v in (target or {}).items() if v and os.path.isfile(v)}
    rows = []
    for s in shots.get("shots") or []:
        imgs = []
        for c in s.get("captures") or []:
            if c.get("reached") and c.get("image") and os.path.isfile(c["image"]):
                rel = os.path.relpath(_copy(c["image"], os.path.join(out_dir, "shipped"), f"{s['id']}@{c['viewport']}.png"), out_dir)
                imgs.append(f"<figure><img src='{e(rel)}' alt='{e(s.get('name') or s['id'])} at {e(c['viewport'])}' loading=lazy><figcaption>{e(c['viewport'])}</figcaption></figure>")
            else:
                imgs.append(f"<div class=notseen>Not seen at {e(c.get('viewport') or '?')}: {e(c.get('reason') or 'the shot could not be reached')}</div>")
        for c in s.get("captures") or []:   # a moment's sequence: before → peak → after, on the phone
            q = c.get("sequence") or {}
            if c.get("reached") and c.get("viewport") == "phone" and all(q.get(k) and os.path.isfile(q[k]) for k in ("before", "peak", "after")):
                fr = [os.path.relpath(_copy(q[k], os.path.join(out_dir, "shipped"), f"{s['id']}@phone.{k}.png"), out_dir) for k in ("before", "peak", "after")]
                imgs.append("<div class=seq>" + "".join(f"<figure><img src='{e(f)}' alt='{e(s.get('name') or s['id'])}: {k}' loading=lazy><figcaption>{k}</figcaption></figure>"
                                                         for f, k in zip(fr, ("before", "peak", "after"))) + "</div>")
        rows.append(f"<section class=design><h2>{e(s.get('name') or s['id'])}</h2><p class=meta>{e(s.get('kind') or '')}"
                    f"{' · moment ' + e(s['moment']) if s.get('moment') else ''}</p><div class=compare>{''.join(imgs)}</div></section>")
    hero = []
    first = tg.get("browser") or tg.get("phone")   # the frame drawn at the real phone browser size is the one a phone capture can match
    if first:
        main = next((s for s in shots.get("shots") or [] if s.get("kind") in ("title", "screen")), None)
        cap = next((c for c in (main or {}).get("captures") or [] if c.get("reached") and c.get("viewport") in ("phone", "iphone13", "iphone17")), None)
        ship = (os.path.relpath(os.path.join(out_dir, "shipped", f"{main['id']}@{cap['viewport']}.png"), out_dir) if cap else None)
        note = "" if tg.get("browser") else " (drawn full screen: the browser's toolbars take their share of the shipped height)"
        hero.append("<div class=compare><div><h3>Chosen frame, on a phone" + note + "</h3><img src='" + e(first) + "' alt='The chosen design at phone size'></div><div><h3>Shipped, on a phone</h3>"
                    + (f"<img src='{e(ship)}' alt='The shipped first screen at phone size'>" if ship else "<div class=notseen>The first screen was not captured</div>") + "</div></div>")
    rest = {k: v for k, v in tg.items() if k not in ("phone", "browser") or (k == "phone" and tg.get("browser"))}
    labels = {"phone": "full screen", "desktop": "desktop", "play": "play frame", "icon": "app icon"}
    if rest:
        hero.append("<div class=compare>" + "".join(f"<div><h3>Chosen {labels.get(k, k)}</h3><img src='{e(v)}' alt='The chosen {e(k)} frame'" + (" style='max-width:160px;border-radius:22%'" if k == "icon" else "") + "></div>"
                                                    for k, v in rest.items()) + "</div>")
    rem = ""
    if remaining:
        rem = ("<h2 style='margin-top:30px'>Still open after the review rounds</h2><ul class=gaps>"
               + "".join(f"<li><b>{e(g.get('shot') or '')}</b> vs {e(g.get('against') or '')}: {e(g.get('gap') or '')}</li>" for g in remaining) + "</ul>")
    body = (f"{crumbs}<h1>{e(title)}: the look, chosen and shipped</h1><p class=lede>The frame picked before anything was built, next to the shipped screens"
            + (f" (style: {e(style)})" if style else "") + ". Every shipped image is a capture of the real build; a shot that could not be reached is shown as not seen.</p>"
            + (f"<p class=status><b>Live:</b> <a href='{e(live_url)}'>{e(live_url if live_url.startswith('http') else 'play the shipped build')}</a></p>" if live_url else "")
            + "".join(hero) + rem + "<h2 style='margin-top:34px'>Every shot</h2>" + "".join(rows))
    p = os.path.join(out_dir, "index.html")
    with open(p, "w") as f: f.write(_page(f"{title} look", body, "The chosen frame beside the shipped screens"))
    return p


# ---------------------------------------------------------------- the picks (called by production/builtins.py)
def parse_choice(choice, styles):
    """A style choice: one look, two looks to compare ("a,b" or "a and b"), or "surprise" (the wildcard). None → the recommendation."""
    ids = [s["look"] for s in styles.get("styles") or []]
    if choice is None or str(choice).strip() == "": return [styles.get("recommended")], "recommended"
    c = str(choice).strip().lower()
    if c in ("surprise", "surprise me", "surprise-me"): return [styles.get("wildcard")], "surprise me"
    parts = [p.strip() for p in re.split(r",|\band\b|\bvs\b|/", c) if p.strip()]
    got = []
    for p in parts:
        L = look(p)
        got.append(L["id"] if L and L["id"] in ids else p)
    bad = [g for g in got if g not in ids]
    if bad or not 1 <= len(got) <= 2: raise ValueError(f"choose one or two of {ids}, or 'surprise' (got {choice!r})")
    return got, "compare" if len(got) == 2 else "picked"


def valid_choice(result, choice):
    kind = (result or {}).get("approval")
    if kind == "style":
        parse_choice(choice, result.get("styles") or {})
    elif kind == "design" and choice is not None and choice not in (result.get("options") or []):
        raise ValueError(f"{choice!r} is not one of {result.get('options')}")


def save_target(project, art_rel, design, base, meta):
    """The chosen frame saved in the project as the target. An earlier target that differs is moved to target/replaced-<time>/,
    never silently overwritten. → (paths, replaced)"""
    tdir = os.path.join(project, art_rel, "target")
    os.makedirs(tdir, exist_ok=True)
    files = {k: _abs(base, design[k]) for k in ("phone", "browser", "desktop", "play") if design.get(k)}
    if meta.get("icon_file"): files["icon"] = _abs(base, meta.pop("icon_file"))
    new = {f"{k}{os.path.splitext(v)[1].lower()}": v for k, v in files.items()}
    replaced = []
    old = [f for f in os.listdir(tdir) if os.path.isfile(os.path.join(tdir, f))]
    if any(f in new and sha(os.path.join(tdir, f)) != sha(new[f]) for f in old) or (old and "target.json" in old and _json(os.path.join(tdir, "target.json"), {}).get("design") != design.get("id")):
        keep = os.path.join(tdir, "replaced-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        os.makedirs(keep)
        for f in old: shutil.move(os.path.join(tdir, f), os.path.join(keep, f)); replaced.append(os.path.relpath(os.path.join(keep, f), project))
    paths = {}
    for name, src in new.items():
        shutil.copyfile(src, os.path.join(tdir, name)); paths[name.split(".")[0]] = os.path.join(tdir, name)
    tj = dict(meta, design=design.get("id"), name=design.get("name"), idea=design.get("idea"), palette=design.get("palette"), type=design.get("type"),
              composition=design.get("composition"), flavor=design.get("flavor"), files={k: os.path.relpath(v, project) for k, v in paths.items()}, saved=_now())
    with open(os.path.join(tdir, "target.json"), "w") as f: json.dump(tj, f, indent=1)
    paths["json"] = os.path.join(tdir, "target.json")
    return paths, replaced


# ---------------------------------------------------------------- the review pack and its rules
def review_pack(project, shots_report, out_dir, target=None, style_image=None, refs=None, moments=None, direction=None, rnd=0, previous=None):
    """Index the evidence for the visual review: the chosen frame, the style sample, the references and every reached shot,
    each with an id and a SHA-256. Shots that were not reached are listed as not seen and are not citable."""
    items, not_seen = [], []
    def add(i, kind, p, **kw):
        if p and os.path.isfile(p): items.append(dict({"id": i, "kind": kind, "path": p, "sha256": sha(p)}, **kw))
    for k, p in (target or {}).items(): add(f"target:{k}", "target", p)
    if style_image: add("style:sample", "style", style_image)
    for r in refs or []: add(f"reference:{r['file']}", "reference", os.path.join(project, r["file"]), note=r.get("note"))
    for s in (shots_report or {}).get("shots") or []:
        for c in s.get("captures") or []:
            if c.get("reached"):
                add(f"shot:{s['id']}@{c['viewport']}", "screenshot", c.get("image"), shot=s["id"], moment=s.get("moment"), shot_kind=s.get("kind"), viewport=c["viewport"])
                for part in ("before", "after"):   # a moment's sequence: before, peak (the shot itself), after
                    fp = (c.get("sequence") or {}).get(part)
                    if fp: add(f"shot:{s['id']}@{c['viewport']}#{part}", "screenshot", fp, shot=s["id"], moment=s.get("moment"), shot_kind=s.get("kind"), viewport=c["viewport"], frame=part)
            else: not_seen.append({"shot": s["id"], "viewport": c.get("viewport"), "reason": c.get("reason")})
    by = {i["id"]: i["path"] for i in items}
    same = []   # the instant of failing must be its own picture: a fail shot that IS the results screen shows nothing of the fail
    for vp in sorted({i.get("viewport") for i in items if i.get("shot_kind") == "fail"}):
        for f in [i for i in items if i.get("shot_kind") == "fail" and i.get("viewport") == vp and not i.get("frame")]:
            for r in [i for i in items if i.get("shot_kind") == "results" and i.get("viewport") == vp and not i.get("frame")]:
                v = same_picture(f["path"], r["path"])
                if f["sha256"] == r["sha256"] or (v is not None and v >= 0.9): same.append({"fail": f["id"], "results": r["id"], "layout_correlation": v})
    K = {"schema": "gitcraft-visual-pack/2", "project": project, "created": _now(), "items": items, "not_seen": not_seen, "round": int(rnd or 0),
         "previous_gaps": [{k: g.get(k) for k in ("id", "shot", "against", "gap", "fix")} for g in previous or []], "fail_same_as_results": same,
         "moments": moments or [], "style": ((direction or {}).get("art") or {}).get("style"), "concept": ((direction or {}).get("art") or {}).get("concept"),
         "fingerprint": hashlib.sha256(json.dumps(sorted(i["sha256"] for i in items)).encode()).hexdigest()[:16]}
    os.makedirs(out_dir, exist_ok=True)
    K["paths"] = {"pack": os.path.join(out_dir, "pack.json"), "brief": os.path.join(out_dir, "BRIEF.md")}
    with open(K["paths"]["pack"], "w") as f: json.dump(K, f, indent=1)
    with open(K["paths"]["brief"], "w") as f: f.write(review_brief(K))
    return K


CHECKS = {"text_readable": "every piece of text is readable where it sits; text on textured, hatched or busy ground has the contrast or the backing it needs",
          "geometry_deliberate": "nothing is rotated, clipped, cut off or tiny unless the style gives a reason (name the reason if something is)",
          "player_visible": "the thing the player controls (or the main content) is never hidden by the HUD, a panel or a backing",
          "credits_placed": "credits and bylines sit somewhere deliberate (a footer, a corner, the pause screen), never floating under a control"}


def shots_in(K):
    """The reached shots of a pack, by shot id → its item ids (every viewport, every frame of a sequence)."""
    out = {}
    for i in K.get("items") or []:
        if i.get("kind") == "screenshot" and i.get("shot"): out.setdefault(i["shot"], []).append(i["id"])
    return out


def moment_sequences(K):
    """moment id → [[before, peak, after] per viewport] for the moments whose sequence was captured."""
    out = {}
    ids = {i["id"]: i for i in K.get("items") or []}
    for i in K.get("items") or []:
        if i.get("moment") and not i.get("frame") and f"{i['id']}#before" in ids and f"{i['id']}#after" in ids:
            out.setdefault(i["moment"], []).append([f"{i['id']}#before", i["id"], f"{i['id']}#after"])
    return out


def review_brief(K):
    L = ["# Visual review brief" + (f" (round {K.get('round')})" if K.get("round") else ""), "",
         "Compare the built product with what the person chose. Advisory judgement: no score. Its gaps become work orders "
         f"(at most {ROUNDS} rounds); what remains is listed for the person with the screenshots.", "",
         f"Style: {json.dumps(K.get('style'))}", f"Concept: {K.get('concept')}", ""]
    L += ["## What was chosen (open these first)", ""] + [f"- `{i['id']}` — {i['path']}" for i in K["items"] if i["kind"] in ("target", "style", "reference")]
    L += ["", "## The shipped shots (open every one: each must be in coverage.viewed)", ""] + [
        f"- `{i['id']}` ({i.get('shot_kind')}{', moment ' + i['moment'] if i.get('moment') else ''}) — {i['path']}" for i in K["items"] if i["kind"] == "screenshot"]
    if K["not_seen"]: L += ["", "## Not seen (never judge these)", ""] + [f"- {n['shot']} @ {n['viewport']}: {n['reason']}" for n in K["not_seen"]]
    L += ["", "## The bar: answer these four checks for EVERY shot, every round (`checks`)", ""] + [f"- `{k}`: {v}" for k, v in CHECKS.items()]
    L += ["", "Look at the phone captures at full size. A check that fails is a gap (with the fix); `ok: true` needs a note saying what you looked at."]
    seqs = moment_sequences(K)
    if K["moments"]:
        L += ["", "## Signature moments: judged as events, not stills (`moments`)", "",
              "Each moment was captured as before → peak → after. Open all three at phone size and answer: does it read as an EVENT (something visibly happens, at a size "
              "a thumb-holding person notices)? A small label appearing is not a moment. If it does not land, that is a gap against `moment:<id>` with what would make it land.", ""]
        L += [f"- `moment:{m.get('id')}` {m.get('name')}: {m.get('what')} — frames: " + ("; ".join(" → ".join(f"`{x}`" for x in t) for t in seqs.get(m.get("id"), [])) or "NOT SEEN (do not judge)")
              for m in K["moments"]]
    if K.get("fail_same_as_results"):
        L += ["", "## The fail shot is the results screen", "", "The fail capture shows the same picture as the results capture: the instant of failing is not visible. That is a gap on the fail shot."]
    if K.get("previous_gaps"):
        L += ["", "## After the fixes: every earlier gap, and anything the fixes broke (`previous`)", "",
              "Every shot was shot again. Say for each earlier gap whether it is closed, and look at every shot for NEW gaps the fixes caused.", ""]
        L += [f"- `{g['id']}` ({g.get('shot')} vs {g.get('against')}): {g.get('gap')}" for g in K["previous_gaps"]]
    ex_shot = next(iter(shots_in(K)), "title")
    L += ["", "## Schema", "", "```json", json.dumps({
        "reviewer": "Claude Code session (model judgement)", "coverage": {"viewed": ["target:phone", f"shot:{ex_shot}@phone"], "not_seen": ["fail@desktop"]},
        "summary": "an assessment against the chosen frame, the style and the moments",
        "checks": [{"shot": ex_shot, **{k: {"ok": True, "note": "what you looked at"} for k in CHECKS}}],
        "moments": [{"id": "first-win", "reads_as_event": False, "why": "what happens across the three frames, and why it does or does not land", "evidence": ["shot:x@phone#before", "shot:x@phone", "shot:x@phone#after"]}],
        "previous": [{"id": "g1", "closed": True, "note": "what the new shot shows"}],
        "matches": [{"against": "target", "claim": "…", "evidence": [f"shot:{ex_shot}@phone", "target:phone"], "basis": "observed_render"}],
        "gaps": [{"id": "g1", "shot": ex_shot, "against": "target", "gap": "…", "fix": "…", "evidence": [f"shot:{ex_shot}@phone", "target:phone"], "basis": "observed_render", "severity": "major"}]}, indent=1), "```", ""]
    return "\n".join(L)


def review_errors(R, K):
    """Every problem with a visual review, as plain sentences (empty = valid). The Creative Review's rules hold here too."""
    E = []
    ids = {i["id"]: i for i in K.get("items") or []}
    def walk(o, p=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if SCORE_KEYS.match(str(k)): E.append(f"{p}{k}: a visual review carries no scores, ratings or points")
                walk(v, f"{p}{k}.")
        elif isinstance(o, list):
            for n, v in enumerate(o): walk(v, f"{p}{n}.")
    walk(R)
    if not _said(R.get("reviewer"), 3): E.append("reviewer: say who made the judgement")
    viewed = set((R.get("coverage") or {}).get("viewed") or [])
    for v in viewed:
        if v not in ids: E.append(f"coverage.viewed: {v} is not in the pack (a shot that was not reached cannot be viewed)")
    if not _said(R.get("summary"), 12): E.append("summary: the assessment against the chosen frame, style and moments")
    if re.search(r"\bverdict\b", str(R.get("summary") or ""), re.I): E.append("summary: say 'assessment', not 'verdict' (the verdict is a release gate)")
    unseen = {n["shot"] for n in K.get("not_seen") or []}
    def claim(w, c, text):
        if c.get("basis") not in ("observed_render", "source_analysis", "hypothesis_playtest"): E.append(f"{w}: basis observed_render, source_analysis or hypothesis_playtest"); return
        ev = c.get("evidence") or []
        for x in ev:
            if x not in ids: E.append(f"{w}: evidence {x} is not in the pack")
            elif ids[x]["kind"] == "screenshot" and x not in viewed: E.append(f"{w}: {x} is cited as seen but is not in coverage.viewed")
        if c.get("basis") == "observed_render" and not any(x in ids and ids[x]["kind"] == "screenshot" for x in ev): E.append(f"{w}: observed_render needs a cited shot")
        if c.get("basis") != "hypothesis_playtest":
            m = FEEL.search(" ".join(str(c.get(k) or "") for k in text))
            if m: E.append(f"{w}: '{m.group(0)}' describes how it feels to play; that is a playtest hypothesis, not an observation")
    for n, c in enumerate(R.get("matches") or []):
        if not AGAINST.match(str(c.get("against") or "")): E.append(f"matches[{n}]: against is target, style, moment:<id> or reference:<file>")
        claim(f"matches[{n}]", c, ("claim",))
    gids, gaps = set(), [g for g in R.get("gaps") or [] if isinstance(g, dict)]
    for n, g in enumerate(gaps):
        w = f"gaps[{n}]"
        if not g.get("id") or g["id"] in gids: E.append(f"{w}: a unique id")
        gids.add(g.get("id"))
        if g.get("shot") in unseen and not any(x.startswith(f"shot:{g.get('shot')}@") for x in g.get("evidence") or [] if x in ids):
            E.append(f"{w}: shot {g.get('shot')} was not seen; it cannot be judged")
        if not AGAINST.match(str(g.get("against") or "")): E.append(f"{w}: against is target, style, moment:<id> or reference:<file>")
        for k in ("gap", "fix"):
            if not _said(g.get(k), 8): E.append(f"{w}: {k} is required")
        if g.get("severity") not in ("major", "minor"): E.append(f"{w}: severity major or minor")
        if g.get("basis") != "observed_render": E.append(f"{w}: a visual gap is something seen in a shot (basis observed_render)")
        claim(w, g, ("gap",))
    # ---- the bar: four checks on every reached shot, every round; every frame of every shot opened
    reached = shots_in(K)
    for sid, items in reached.items():
        miss = [x for x in items if x not in viewed]
        if miss: E.append(f"coverage.viewed: shot {sid} has captures that were not opened ({', '.join(miss[:4])}); every shot is looked at every round")
    C = {c.get("shot"): c for c in R.get("checks") or [] if isinstance(c, dict)}
    for sid in reached:
        c = C.get(sid)
        if not c: E.append(f"checks: shot {sid} has no entry (answer {', '.join(CHECKS)} for every shot)"); continue
        for k in CHECKS:
            a = c.get(k)
            if not isinstance(a, dict) or not isinstance(a.get("ok"), bool) or not _said(a.get("note"), 8): E.append(f"checks[{sid}].{k}: {{ok: true|false, note: what you saw}}"); continue
            if not a["ok"] and not any(g.get("shot") == sid for g in gaps): E.append(f"checks[{sid}].{k} failed, but no gap names shot {sid}: a failed check is a gap with its fix")
    for sid in C:
        if sid not in reached: E.append(f"checks: shot {sid} was not seen; it cannot be checked")
    # ---- moments are judged as events, from their sequence
    seqs = moment_sequences(K)
    M = {m.get("id"): m for m in R.get("moments") or [] if isinstance(m, dict)}
    for mid, frames in seqs.items():
        m = M.get(mid)
        if not m or not isinstance(m.get("reads_as_event"), bool) or not _said(m.get("why"), 20): E.append(f"moments: say whether moment {mid} reads as an event at phone size, and why (reads_as_event, why)"); continue
        ev = set(m.get("evidence") or [])
        if not any(set(t) <= ev and set(t) <= viewed for t in frames): E.append(f"moments[{mid}]: cite and open its whole sequence (before, peak, after), e.g. {frames[0]}")
        if not m["reads_as_event"] and not any(g.get("against") == f"moment:{mid}" for g in gaps): E.append(f"moments[{mid}] does not read as an event, but no gap is against moment:{mid}: a moment that does not land is a work order")
        fm = FEEL.search(str(m.get("why") or ""))
        if fm: E.append(f"moments[{mid}].why: '{fm.group(0)}' is a playtest hypothesis; say what is visible in the frames")
    for mid in M:
        if mid not in seqs: E.append(f"moments: {mid} has no captured sequence; it was not seen and cannot be judged")
    if K.get("fail_same_as_results") and not any(g.get("shot") in {ids[x["fail"]].get("shot") for x in K["fail_same_as_results"] if x["fail"] in ids} for g in gaps):
        E.append("the fail shot shows the same picture as the results screen: that is a gap on the fail shot (the instant of failing must be visible)")
    # ---- after a round of fixes: every earlier gap answered; a gap still open is a gap again
    P = {x.get("id"): x for x in R.get("previous") or [] if isinstance(x, dict)}
    for g in K.get("previous_gaps") or []:
        a = P.get(g["id"])
        if not a or not isinstance(a.get("closed"), bool) or not _said(a.get("note"), 8): E.append(f"previous: say whether earlier gap {g['id']} is closed in the new shots ({{id, closed, note}})"); continue
        if not a["closed"] and not any(x.get("shot") == g.get("shot") for x in gaps): E.append(f"previous[{g['id']}] is still open, but no gap names shot {g.get('shot')}")
    return E


def gaps_of(R): return [g for g in (R or {}).get("gaps") or [] if isinstance(g, dict)]
