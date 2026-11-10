"""REQUEST INTAKE: a master prompt → a production spec.

Deterministic and inspectable: every decision names the words that caused it (`because`), every
default the intake had to choose is listed in `assumptions`, and only questions whose answer would
change what gets built *and* that have no safe default are `essential`. The agent (Claude) reads the
spec, may correct any field with `overrides`, and the planner works from the corrected spec.

Spec fields:
  title, prompt, deliverable (game | app | site | tool | asset_pack | media), dimension (2d | 3d),
  platform {mobile_first, viewports, engine}, genres (PLAYCRAFT profiles), features {...},
  assets {sfx, music, ambience, voice, levels, vfx, materials, world, models, identity, trailer},
  quality {level, gates...}, project {path, exists}, authorisations, acceptance [...],
  assumptions [...], questions [...]"""
import copy, json, os, re
from . import standards, maturity, understanding

RULES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json")))


def _w(text, words):
    """Words/phrases from `words` present in text (word boundaries; simple plural/verb forms)."""
    out = []
    for w in words:
        if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?:s|es|ed|ing|y)?(?![a-z0-9])", text): out.append(w)
    return out


def _first(text, table):
    """The table key whose words appear earliest in the text."""
    best = None
    for key, words in table.items():
        for w in words:
            m = re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?:s|es|ed|ing)?(?![a-z0-9])", text)
            if m and (best is None or m.start() < best[0]): best = (m.start(), key, w)
    return (best[1], best[2]) if best else (None, None)


def _title(prompt, t):
    m = re.search(r"(?:called|named|titled)\s+[\"“']?([A-Z][\w' -]{1,40}?)[\"”']?(?:[,.;:]|\s+(?:for|that|with|where|in)\b|$)", prompt)
    if m: return m.group(1).strip()
    m = re.search(r"[\"“]([^\"”]{2,40})[\"”]", prompt)
    if m: return m.group(1).strip()
    return None


def parse(prompt, project=None, overrides=None):
    if not prompt or len(prompt.strip()) < 12:
        raise ValueError("the master prompt is empty or too short to plan from: describe the deliverable")
    t = " ".join(prompt.lower().split())
    because, assumptions, questions = {}, [], []
    # an existing project gets only what was asked for: no implied sounds, identity, icon or branding
    existing = bool((overrides or {}).get("mode", {}).get("existing")) or maturity.is_existing(project)

    # ---- deliverable
    deliverable, w = _first(t, RULES["deliverables"])
    if deliverable is None:
        deliverable = "app"; assumptions.append("no deliverable type named: treated as a web app")
    else: because["deliverable"] = w
    # assets and nothing else ("a jump sound and a coin sound", "a 3D model of a barrel for my game"): the pack of exactly
    # those assets, never a game or an app scaffolded around them
    alone = None if existing or deliverable == "media" else understanding.standalone(prompt)
    if alone:
        deliverable = "asset_pack"; because["deliverable"] = alone["because"]
        assumptions.append("a request for assets alone: only what is named is made; nothing is scaffolded, branded or deployed around it")
    dimension = "3d" if _w(t, RULES["three_d_words"]) else "2d"
    if dimension == "3d": because["dimension"] = _w(t, RULES["three_d_words"])
    elif deliverable == "game": assumptions.append("2D: the prompt names no 3D look or engine")

    # ---- platform
    mobile = bool(_w(t, RULES["mobile_words"]))
    desktop_only = bool(_w(t, ["desktop only", "desktop-only", "pc only"]))
    engine, ew = _first(t, RULES["engines"])
    if engine: because["engine"] = ew
    elif deliverable == "game": engine = "three" if dimension == "3d" else "canvas"; assumptions.append(f"engine not named: {engine} (no framework dependency added)")
    viewports = ["phone", "desktop", "tablet"] if mobile else (["desktop"] if desktop_only else ["desktop", "phone"])
    native = sorted({p for p, words in RULES["native_words"].items() if _w(t, words)})
    native = ["android", "ios"] if "both" in native else native
    # mobile_stated: what the person said (True mobile, False desktop only, None nothing): evaluators detect the rest
    platform = {"mobile_first": mobile or bool(native), "viewports": viewports, "engine": engine, "web": True, "native": native,
                "mobile_stated": True if (mobile or native) else (False if desktop_only else None)}
    if native: because["native"] = native

    # ---- genres (PLAYCRAFT profiles) for games
    genres = [g for g, words in RULES["genres"].items() if _w(t, words)] if deliverable == "game" else []
    genres_assumed = deliverable == "game" and not genres
    if genres_assumed: genres = ["arcade"]; assumptions.append("genre not named: arcade")

    # ---- features
    feats = {k: bool(_w(t, v)) for k, v in RULES["features"].items()}
    polished = bool(_w(t, RULES["polish_words"]))
    if deliverable == "game":
        feats["gameplay_loop"] = True; feats["controls"] = True
        if polished and not feats["sound"] and not existing: feats["sound"] = True; assumptions.append("'polished' game: sound effects included")
    feats["deploy"] = bool(_w(t, RULES["deploy_words"]))

    # ---- assets the departments make
    assets = {}
    if feats["sound"] or feats["music"]:
        presets = [p for p, words in RULES["sfx_presets"].items() if _w(t, words)]
        if not presets:
            presets = list(RULES["default_sfx"].get(genres[0] if genres else "app", RULES["default_sfx"]["arcade"]))
            assumptions.append(f"sound effects not listed: {', '.join(presets)} (genre defaults)")
        for g in genres:
            for p in RULES["default_sfx"].get(g, []):
                if p not in presets and len(presets) < 6: presets.append(p)
        if feats["sound"] or not alone: assets["sfx"] = presets[:8]
        mood, mw = _first(t, RULES["music_moods"])
        if feats["sound"] and not mood:
            mood = RULES["default_mood"].get(genres[0] if genres else "arcade", "playful")
            assumptions.append(f"music mood not named: {mood}")
        if feats["music"] or not alone: assets["music"] = {"mood": mood or "playful", "bars": 16}
        amb = [k for k, words in RULES["ambience"].items() if _w(t, words)]
        if amb: assets["ambience"] = amb[:2]
    if feats["voice"]: assets["voice"] = True
    if feats["levels"] or (deliverable == "game" and _w(t, ["level", "stage"])):
        kind, kw = _first(t, RULES["level_kinds"])
        if not kind:
            kind = next((RULES["genre_level_kind"][g] for g in genres if g in RULES["genre_level_kind"]), None)
        m = re.search(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:hand-?crafted\s+|unique\s+|distinct\s+)?(?:levels|stages|worlds|maps)", t)
        nums = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        count = (int(m.group(1)) if m.group(1).isdigit() else nums[m.group(1)]) if m else 3
        if not m: assumptions.append("level count not named: 3")
        if count > 6: assumptions.append(f"{count} levels asked: LevelCraft generates 6 now (seeds recorded) and the rest follow the same recipe")
        assets["levels"] = {"kind": kind, "count": min(count, 6), "requested": count, "by_levelcraft": bool(kind)}
        if not kind: assumptions.append("level layouts don't fit a LevelCraft kind (dungeon, cave, platformer, overworld, settlement): the agent designs them as data")
    vfx = [e for e, words in RULES["vfx"].items() if _w(t, words)]
    if vfx or (feats["effects"] and deliverable == "game"):
        assets["vfx"] = vfx[:4] or RULES["default_vfx"]
    if alone and feats["materials"]:   # "a stone texture": a material, whatever the dimension of the game it is for
        assets["materials"] = [m for m, words in RULES["materials"].items() if _w(t, words)][:4] or ["stone"]
    if dimension == "3d":
        mats = [m for m, words in RULES["materials"].items() if _w(t, words)]
        if (mats or feats["materials"]) and not alone: assets["materials"] = mats[:4] or ["stone", "wood"]
        terr, tw = _first(t, RULES["terrain"])
        if terr or feats["world"]: assets["world"] = {"terrain": terr or "island", "sky": _first(t, RULES["sky"])[0] or "morning", "ocean": bool(_w(t, ["ocean", "sea", "waves"]))}
        models = re.findall(r"(?:3d model|model) of (?:an? |the )?([a-z][a-z \-]{2,30}?)(?:[,.;]| and |$)", t)
        if models: assets["models"] = models[:4]
        # animated characters: AnimCraft rigs and animates the model, TestCraft proves the clips move. Only when asked:
        # autorig replaces an existing armature, and ForgeCraft's character templates already ship rigged clips
        if models and _w(t, ["animated", "animation", "animations", "rigged", "walk cycle", "walking", "animate"]):
            anim = []
            for i, brief in enumerate(assets["models"], 1):
                b = brief.lower()
                rig = ("chain" if re.search(r"\b(snake|serpent|tentacle|eel|worm|tail|vine|rope)\b", b) else
                       "quadruped" if re.search(r"\b(dog|cat|horse|wolf|fox|deer|cow|pig|sheep|bear|lion|tiger|quadruped|hound|goat)\b", b) else
                       "humanoid" if re.search(r"\b(character|hero|heroine|person|man|woman|kid|knight|pirate|sailor|deckhand|robot|villager|npc|soldier|wizard|zombie|crew|humanoid)\b", b) else None)
                if rig: anim.append({"model": i, "rig": rig, "clips": {"humanoid": ["idle", "walk", "run"], "quadruped": ["idle", "walk"], "chain": ["slither", "sway"]}[rig]})
            if anim: assets["animate"] = anim
            else: assumptions.append("animation asked, but no model brief names a character or creature: models are left static (AnimCraft can animate props with bob/spin/hover on request)")
    if feats["identity"] or (deliverable in ("game", "app", "site") and polished and not existing):
        assets["identity"] = True
        if not feats["identity"]: assumptions.append("'polished': an original visual identity (logo, icon, palette) is included")
    if feats["trailer"]: assets["trailer"] = True

    # ---- quality bar
    level = "polished" if polished else "standard"
    q = copy.deepcopy(RULES["quality"][level])
    q["level"] = level; q["viewports"] = viewports
    q["playcraft"] = deliverable == "game"; q["pixelcraft"] = deliverable in ("game", "app", "site")
    q["designcraft"] = deliverable == "game"; q["perf"] = bool(polished or feats["performance"])

    # ---- the project
    proj = {"path": os.path.abspath(project) if project else None}
    if not project and deliverable in ("game", "app", "site", "tool"):
        assumptions.append("no project folder given: a new one is created in the workspace")
    # ---- what may be done without asking
    auth = {"write_project": True, "replace_assets": False, "deploy": False, "merge": False, "spend": False, "network": False}
    if feats["deploy"]:
        questions.append({"id": "deploy_target", "essential": False, "question": "Where should the release be deployed, and may it be deployed without a further check-in?",
                          "default": "the release is prepared and verified locally; deployment waits for approval (production_approve)"})
    if deliverable == "game" and not genres:
        questions.append({"id": "genre", "essential": False, "question": "What kind of game is it?", "default": "arcade"})

    title = _title(prompt, t) or (deliverable.title() + " production")
    # ---- engineering standard (proportionate: personal / public / sensitive), icon and attribution standards
    prof, pw = standards.profile_for(t, deliverable)
    if not pw: assumptions.append(f"nobody named who uses it or what it holds: the {prof} engineering standard")
    web = deliverable in ("game", "app", "site")
    spec = {"title": title, "prompt": prompt, "deliverable": deliverable, "dimension": dimension, "platform": platform,
            "genres": genres, "genres_assumed": genres_assumed, "features": feats, "assets": assets, "quality": q, "project": proj, "authorisations": auth,
            "engineering": {"profile": prof, "because": pw}, "icon": {"mode": None, "required": web and not existing},
            "attribution": {"required": web and not existing}, "mode": _mode(prompt, project, existing, overrides),
            "deploy": {"target": None}, "analytics": {"provider": None},
            "evaluation": {"target": "auto"},   # source-vs-build policy for every browser check: auto | build | source
            "backend": {"provider": None, "needed": bool(feats.get("backend")), "because": _w(t, RULES["features"]["backend"])}, "because": because, "assumptions": assumptions, "questions": questions, "optional_criteria": []}
    if overrides:
        spec = merge(spec, overrides)
        # what follows from the deliverable is re-derived when an override changed it (unless also overridden), so
        # the quality bar matches what is actually being made, e.g. a "level pack" re-classified as an asset pack
        d, qo = spec["deliverable"], (overrides.get("quality") or {})
        for k, v in (("playcraft", d == "game"), ("pixelcraft", d in ("game", "app", "site")), ("designcraft", d == "game")):
            if k not in qo: spec["quality"][k] = v
        if "genres" not in overrides and d != "game": spec["genres"] = []
        w = d in ("game", "app", "site")
        ex = spec.get("mode", {}).get("existing")
        if "icon" not in overrides: spec["icon"]["required"] = w and not ex
        if "attribution" not in overrides: spec["attribution"]["required"] = w and not ex
    if spec.get("mode", {}).get("existing") and proj["path"] and os.path.isdir(proj["path"]) and not (overrides or {}).get("analytics"):
        found = standards.discover_analytics(proj["path"])   # Discovery recognises what the project already ships
        if found:
            spec["analytics"] = {"provider": "pulse" if any(f["provider"] == "pulse" for f in found) else None, "source": "discovered", "found": found}
            assumptions.append("existing analytics recognised: " + ", ".join(f["name"] for f in found))
    spec["acceptance"] = acceptance(spec)
    return spec


def _mode(prompt, project, existing, overrides):
    """New projects build. An existing one is read (read-only) for its maturity, and the request picks the workflow, the
    same way production_start does, unless the overrides already say (production_start passes its own reading)."""
    if not existing: return {"existing": False, "workflow": "build"}
    given = (overrides or {}).get("mode") or {}
    if given.get("workflow") and given.get("maturity"): return {"existing": True}
    a = maturity.assess(project) if project else {"maturity": "nearly_complete", "kind": None, "confidence": "low"}
    wf, because = maturity.intent(prompt, a["maturity"])
    return {"existing": True, "maturity": a["maturity"], "kind": a.get("kind"), "confidence": a.get("confidence"), "workflow": wf, "because": because,
            "kind_confidence": a.get("kind_confidence"), "kind_evidence": a.get("kind_evidence"),
            "request": prompt if wf in ("update", "fix", "complete", "continue") else None}


def merge(a, b):
    """Deep-merge overrides into the spec (dicts merge; everything else replaces)."""
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def acceptance(spec):
    """Measurable acceptance criteria, each naming the task kind whose evidence decides it."""
    q, a, d = spec["quality"], spec["assets"], spec["deliverable"]
    out = []
    add = lambda i, text, by: out.append({"id": i, "text": text, "measured_by": by})
    if d in ("game", "app", "site"):
        add("loads_everywhere", f"Loads with no page errors, console errors or missing files on {', '.join(q['viewports'])}", "qa.smoke")
    if q.get("perf"): add("performance", f"Holds ≥ {q['min_fps']} fps (p95 frame ≤ {q['max_p95_ms']} ms) in headless Chromium (relative: SwiftShader)", "qa.perf")
    m0 = spec.get("mode") or {}
    focus = m0.get("focus") if m0.get("existing") and m0.get("workflow") == "update" else None
    if q.get("playcraft"):
        add("gameplay_quality", "PLAYCRAFT plays the game before and after the change with the same probe: no gameplay regression (score change reported)"
            if focus in ("gameplay", "polish") else f"PLAYCRAFT overall ≥ {q['playcraft_min']} with the game actually played", "qa.playcraft")
    if q.get("pixelcraft"):
        add("interface_quality", "PIXELCRAFT measures the same screens before and after the change at iPhone 17, iPhone 13 and desktop: no regression (score change reported)"
            if focus in ("visual", "polish") else f"PIXELCRAFT overall ≥ {q['pixelcraft_min']} at iPhone 17, iPhone 13 and desktop", "qa.pixelcraft")
    if d == "tool" and m0.get("workflow") != "review":
        add("tests_pass", "The tool's own tests pass, run the way the project runs them" + ("" if m0.get("existing") else " (a new tool ships with tests)"), "qa.tests")
    if q.get("designcraft"): add("design_review", "DESIGNCRAFT assessment recorded (structural design findings reviewed)", "qa.designcraft")
    web = d in ("game", "app", "site")
    for kind in ("sfx", "music", "ambience", "voice", "levels", "vfx", "materials", "world", "models", "identity"):
        if a.get(kind): add(f"asset_{kind}", f"{kind} produced by its department, validated" + (", and integrated into the project" if web else ""), "integrate" if web else "production")
    if a.get("animate"):
        add("asset_animation", "Every animated character is rigged and animated by AnimCraft, and TestCraft shows each clip really moves", "animation")
    if a.get("trailer"):
        add("asset_trailer", "A trailer cut from the running build (title card + gameplay capture" + (" + the music" if a.get("music") else "") + "), validated as video", "trailer")
    if web and any(a.get(k) for k in ("sfx", "music", "ambience", "voice", "levels", "vfx", "materials", "world", "models", "identity")):
        # only when the deliverable ships assets into a build; a project's own existing assets add these at planning
        add("asset_integrity", "Every integrated asset opens as its format and is referenced by the build", "qa.assets")
        add("licensing", "Every shipped asset has a recorded licence; nothing non-commercial or no-derivatives", "qa.licences")
    if web and spec.get("icon", {}).get("required"):
        add("app_icon", "An approved app icon (or an inspected, kept existing one) is wired in: favicon, Apple touch 180 (opaque), manifest 192/512 and "
            "maskable, correct sizes and formats, readable at 32 px, no generic framework or broken icon", "qa.icons")
    if web and spec.get("attribution", {}).get("required"):
        add("attribution", "The quiet 'by HaveAnApp' maker's credit is visible in the app (marked data-haveanapp), linked only to the verified HaveAnApp site", "qa.attribution")
    if web:
        add("engineering_standards", f"The {spec.get('engineering', {}).get('profile', 'personal')} engineering standard's measured checks pass (mobile basics, secrets, "
            "HTTPS, reproducible dependencies; auth, validation and rate limits for public/sensitive apps); review items listed", "qa.standards")
    mode = spec.get("mode") or {}
    if d in ("app", "site") and not mode.get("existing"):
        add("features_work", "Every planned feature works in a browser (tests/gitcraft.features.json, run on a phone)", "qa.features")
    if (spec.get("backend") or {}).get("provider") == "postgres":
        add("backend", "Hosted Postgres set up for development and production (approved), with no secret in the repository", "backend.provision")
    if (web or d == "tool") and mode.get("existing") and mode.get("workflow") != "review":
        add("preservation", "Existing work preserved: no file deleted, secrets, CI and deployment untouched"
            + (", game art/audio/levels and saved progress intact" if d == "game" else "") + " (unless approved)", "qa.preserve")
    if spec["features"].get("deploy"): add("deployment", "Deployed and the live URL verified (needs approval)", "release.deploy")
    add("release_ready", "Release report written with every criterion's evidence measured on the final build", "release.report")
    return requirements(spec, out)


def implied(spec):
    """Asset criteria GITCRAFT added on its own (the quality bar or a default), not named in the prompt: the only ones a
    person may make optional. Everything stated, and every standard GITCRAFT holds a release to, stays required."""
    a, f, assum = spec["assets"], spec.get("features") or {}, " ".join(spec.get("assumptions") or [])
    out = set()
    if a.get("sfx") and "'polished' game: sound effects included" in assum: out.add("asset_sfx")
    if a.get("music") and not f.get("music"): out.add("asset_music")   # added because sound was asked or implied
    if a.get("identity") and not f.get("identity"): out.add("asset_identity")
    return out


def requirements(spec, crits):
    """Each criterion carries `required` and `source` (stated | implied | standard). A criterion becomes optional only when the
    person made it so (spec optional_criteria, set by the Decision Room's 'extras' decision) and only if it was implied;
    an optional request for anything else is refused (spec optional_refused, a plan problem), never applied silently."""
    imp = implied(spec)
    stated = {c for c in ("asset_sfx", "asset_music", "asset_ambience", "asset_voice", "asset_levels", "asset_vfx", "asset_materials", "asset_world",
                          "asset_models", "asset_identity", "asset_animation", "asset_trailer", "backend", "deployment", "features_work")} - imp
    want = set(spec.get("optional_criteria") or [])
    spec["optional_refused"] = sorted(want - imp)
    for c in crits:
        c["source"] = "implied" if c["id"] in imp else "stated" if c["id"] in stated else "standard"
        c["required"] = not (c["id"] in want and c["id"] in imp)
    return crits
