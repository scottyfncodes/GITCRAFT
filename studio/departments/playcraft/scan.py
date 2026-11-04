"""PLAYCRAFT discovery (phase 1): understand a game repository without running it.

Reads the docs (README, CLAUDE.md, docs/*.md: the intended experience), the package manifest (engine, build,
tests), and the source (every signal below, with file:line evidence), then identifies the genres from the docs
first and the code second. Everything found here is evidence level `inferred`: code that exists is not proof
that the game feels good, only that a system is there."""
import json, math, os, re

SKIP_DIRS = {"node_modules", "dist", "build", ".git", "coverage", ".next", ".vercel", "out", "vendor", ".cache", "gitcraft-out", ".gitcraft-work",
             "playwright-report", "test-results", "__pycache__", ".venv", "venv", "Library", "Temp", ".godot", "public/assets", "acceptance"}
SRC_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".html", ".css", ".gd", ".cs", ".lua", ".py"}
AUDIO_EXT = {".wav", ".ogg", ".mp3", ".m4a", ".flac", ".opus"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
MODEL_EXT = {".glb", ".gltf", ".fbx", ".obj"}
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|e2e|spec)/|\.(test|spec)\.[a-z]+$")
MAX_FILE = 1_500_000
MAX_FILES = 5000

# id: (regex, what it means). Matched case-insensitively against source (tests excluded unless noted).
SIGNALS = {
    # input
    "input_keyboard": (r"keydown|keyup|onkeydown|\bKey[A-Z]\b|ArrowLeft|ArrowRight", "keyboard input"),
    "input_pointer": (r"pointerdown|mousedown|onclick|pointerup|mouseup|\bclick\b['\"]?\s*,", "mouse/pointer input"),
    "input_touch": (r"touchstart|touchmove|touchend|pointerType\s*===?\s*['\"]touch|maxTouchPoints|ontouchstart", "touch input"),
    "input_gamepad": (r"getGamepads|gamepadconnected", "gamepad input"),
    "input_drag": (r"pointermove|touchmove|drag|pull ?back|slingshot|swipe", "drag/swipe/pull gestures"),
    "input_buffer": (r"coyote|jump ?buffer|input ?buffer|buffer(ed)? ?(time|ms|frames)|grace ?time", "input forgiveness (coyote time, buffering)"),
    "deadzone": (r"dead ?zone", "stick deadzone"),
    "input_remap": (r"remap|rebind|key ?bind|bindings", "control remapping"),
    "sensitivity": (r"sensitivity|invert ?(y|look)", "control sensitivity settings"),
    "virtual_stick": (r"joystick|virtual ?stick|thumb ?stick|d-?pad|floating stick", "virtual stick / d-pad"),
    # game feel
    "screen_shake": (r"shake|trauma", "screen shake"),
    "hitstop": (r"hit ?stop|hit_stop|freeze ?frame|slow ?-?mo|bullet ?time|time ?scale|timeScale", "hit-stop / slow motion"),
    "particles": (r"particle|emitter|sparks?\b|confetti|puff|dust", "particles"),
    "easing": (r"\bease[A-Z(]|easing|tween|\blerp|smoothstep|damp\(|spring", "easing / tweening / smoothing"),
    "camera_smooth": (r"camera[\w.]*\s*[\w.]*(lerp|damp|follow|smooth)|(lerp|damp|smooth)\w*\(\s*camera", "smoothed camera follow"),
    "squash": (r"squash|stretch|anticipation|wind ?up|recoil|knock ?back", "squash/stretch, anticipation, recoil"),
    "haptics": (r"navigator\.vibrate|haptic", "haptics"),
    "flash": (r"hit ?flash|flash(ing)?\b|white ?flash|blink", "flash feedback"),
    "popups": (r"popup|floating ?text|damage ?number|score ?pop|toast|callout|headline", "pop-up feedback text"),
    # audio
    "webaudio": (r"AudioContext|webkitAudioContext|OscillatorNode|createOscillator|createBufferSource", "Web Audio"),
    "audio_lib": (r"howler|new Howl|Tone\.|new Audio\(|<audio", "audio library / <audio>"),
    "music": (r"music|soundtrack|\bbgm\b|theme ?song|melody|oompah", "music"),
    "mute": (r"\bmute|volume", "mute / volume"),
    # physics and simulation
    "physics_engine": (r"rapier|matter-js|Matter\.Engine|cannon(-es)?|planck|box2d|ammo\.js|oimo|havok|p2\.World", "physics engine"),
    "fixed_step": (r"fixed ?(time)?step|fixed ?dt|FIXED_DT|fixedDelta|accumulator|step ?size|1\s*/\s*(60|120|240)\b", "fixed-step update"),
    "dt_clamp": (r"Math\.min\(\s*(dt|delta)|Math\.min\(\s*[\d.]+\s*,\s*\(?\s*\w*(dt|delta|now|time|\bt\b)\w*\s*-|(dt|delta)\s*=\s*Math\.min|clamp\(\s*(dt|delta)|max ?(delta|dt)|MAX_DT|MAX_FRAME", "frame-time clamp"),
    "determinism": (r"determinis|seeded|mulberry|xorshift|seedrandom|\bprng\b|\brng\(|randomSeed", "seeded / deterministic randomness"),
    "chain_reaction": (r"chain|cascade|domino|combo", "chains / combos"),
    "destruction": (r"destruct|fracture|shatter|debris|collapse|voronoi|rubble|crumble|demolish", "destruction"),
    # progression
    "save": (r"localStorage|indexedDB|IDBDatabase|save ?game|saveState|persist", "saving progress"),
    "unlocks": (r"unlock", "unlocks"),
    "upgrades": (r"upgrade|perk|skill ?tree|tech ?tree", "upgrades"),
    "achievements": (r"achievement|badge|trophy|medal|milestone", "achievements / badges"),
    "collectibles": (r"collectible|secret|hidden|pickup|treasure|\bfind(s)?\b", "collectibles / secrets"),
    "currency": (r"\bcoins?\b|currency|\bgold\b|\bfunds\b|\bgems\b|credits", "currency"),
    "xp": (r"\bxp\b|experience ?points|level ?up|rank", "XP / ranks"),
    "levels": (r"levels?\[|\blevel ?\d|levelIndex|currentLevel|stage|chapter|campaign", "levels / stages"),
    "stars": (r"\bstars?\b|grade|rating|\bpar\b", "ratings / stars / par"),
    # possibly bolted-on retention systems
    "daily_reward": (r"daily ?reward|login ?bonus|daily ?bonus|streak ?reward", "daily login rewards"),
    "battle_pass": (r"battle ?pass|season ?pass", "battle pass"),
    "energy_gate": (r"energy ?(timer|refill)|lives ?refill|stamina ?refill|wait ?to ?play", "energy / wait timers"),
    "lootbox": (r"loot ?box|gacha", "loot boxes"),
    # difficulty
    "difficulty": (r"difficulty|hard ?mode|easy ?mode", "difficulty settings/levels"),
    "ramp": (r"\bramp|speed ?up|spawn ?(rate|interval|delay)|\bwaves?\b|escalat|intensity|difficultyAt|harder", "difficulty ramp"),
    "tuning_config": (r"config\.|tuning|\bbalance\b|constants", "central tuning values"),
    "assist": (r"\bassist|skip ?level|god ?mode|accessibility ?mode", "assist options"),
    # failure / restart / flow
    "game_over": (r"game ?over|gameOver|you ?died|defeat|\bcrash(ed)?\b|failed", "fail state"),
    "restart": (r"restart|retry|try ?again|play ?again|respawn|reset ?run|newRun", "restart / retry"),
    "checkpoint": (r"checkpoint", "checkpoints"),
    "tutorial": (r"tutorial|onboard|how ?to ?play|howToPlay|coach|first ?run|firstTime|\bhint|tooltip|guided|ready-?prompt|(hold|tap|press|swipe|drag|touch|click) (to|and) [a-z]+|let go to", "onboarding / hints / control prompts"),
    "pause": (r"\bpause", "pause"),
    "visibility_pause": (r"visibilitychange|document\.hidden|pagehide", "auto-pause when hidden"),
    "settings": (r"settings|options ?menu", "settings"),
    "transitions": (r"transition|fade ?(in|out)|crossfade|wipe", "transitions"),
    # accessibility
    "reduced_motion": (r"prefers-reduced-motion|reduced ?motion|reduce ?motion", "reduced-motion support"),
    "aria": (r"aria-|role=", "ARIA semantics"),
    "colorblind": (r"colou?r ?blind|daltoni|high ?contrast", "colour-blind / contrast options"),
    "subtitles": (r"subtitle|caption", "subtitles"),
    # mobile
    "viewport_meta": (r"<meta[^>]+name=[\"']viewport", "viewport meta"),
    "safe_area": (r"safe-area-inset|viewport-fit\s*=\s*cover", "safe-area insets"),
    "touch_action": (r"touch-action", "touch-action CSS"),
    "orientation": (r"orientation|landscape|portrait", "orientation handling"),
    "pwa": (r"serviceWorker|webmanifest|apple-mobile-web-app", "installable (PWA)"),
    "no_select": (r"user-select:\s*none|-webkit-touch-callout|-webkit-tap-highlight", "no text selection / callouts"),
    "pinch": (r"pinch|gesturechange|two-?finger", "pinch / two-finger gestures"),
    # replay
    "randomness": (r"Math\.random|\brandom\(|\brng\b", "randomness"),
    "daily_challenge": (r"daily ?(demo|challenge|run|seed|puzzle)|seed ?of ?the ?day", "daily challenge"),
    "highscore": (r"high ?score|best ?score|personal ?best|\bbest\b|leaderboard|record", "high score / best"),
    "share": (r"navigator\.share|share|replay|ghost|screenshot", "sharing / replays"),
    "customization": (r"cosmetic|skin|costume|outfit|paint|customi[sz]|wardrobe", "customisation"),
    "sandbox_mode": (r"sandbox|free ?play|free ?patrol|creative ?mode|level ?editor", "sandbox / free play"),
    "procedural": (r"procedural|generate(Level|Map|World|Dungeon)|noise2D|simplex|perlin", "procedural generation"),
    # presentation
    "animation": (r"AnimationMixer|animation|keyframe|sprite ?sheet|\banim\b|gait", "animation"),
    "atmosphere": (r"\bfog\b|Fog\(|weather|day ?night|time ?of ?day|bloom|EffectComposer|post ?process|vignette|ambient", "atmosphere (fog, weather, lighting, post)"),
    "day_night": (r"day ?night|day/night|time ?of ?day|sunset|night", "day/night"),
    "storytelling": (r"\blore\b|journal|\blog ?entr|story|dialog(ue)?|\bnpc\b|radio", "story / dialogue / lore"),
    "survival_resources": (r"hunger|thirst|\bfuel\b|oxygen|stamina|\bhull\b|\bfood\b|scarcit|warmth|cold", "survival resources"),
    "exploration": (r"explor|discover|minimap|fog ?of ?war|landmark|waypoint|compass", "exploration / discovery"),
}

KEY_RE = re.compile(r"['\"`](Space|Arrow(?:Up|Down|Left|Right)|Key[A-Z]|Enter|Escape|Shift(?:Left|Right)?|Digit\d|Tab)['\"`]")
PROP_KEY_RE = re.compile(r"\b(?:keys?|held|pressed|down|input|controls?)\s*(?:\.|\[\s*['\"])(Arrow(?:Up|Down|Left|Right)|Key[A-Z]|Space|Enter|Shift(?:Left|Right)?)\b")   # keys.ArrowRight, held['KeyW']
SHORT_KEY_RE = re.compile(r"(?:e|ev|event|evt)\.key\s*===?\s*['\"]([ a-zA-Z])['\"]")
HOOK_RE = re.compile(r"(?:window|globalThis)\s*(?:\.|\[\s*['\"])(\w{2,40})['\"]?\s*\]?\s*=(?!=)")
HOOK_SKIP = {"onload", "onresize", "onerror", "onbeforeunload", "location", "name", "requestAnimFrame", "AudioContext", "onkeydown", "onkeyup", "onblur", "onfocus", "dataLayer", "requestAnimationFrame", "cancelAnimationFrame", "devicePixelRatio", "__t0"}


def _read(p, limit=MAX_FILE):
    try:
        if os.path.getsize(p) > limit: return ""
        return open(p, encoding="utf-8", errors="ignore").read()
    except OSError: return ""


def _walk(root):
    n = 0
    for d, dirs, files in os.walk(root):
        rel_d = os.path.relpath(d, root)
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith(".") and os.path.join(rel_d, x).lstrip("./") not in SKIP_DIRS)
        for f in sorted(files):
            n += 1
            if n > MAX_FILES * 4: return
            yield os.path.join(d, f)


def docs_text(root):
    """README, CLAUDE.md, design docs: the intended experience (capped)."""
    picks = []
    for f in sorted(os.listdir(root)):
        if re.match(r"(readme|claude|game|design|gdd|pitch|concept)[^/]*\.(md|txt)$", f, re.I): picks.append(os.path.join(root, f))
    for sub in ("docs", "doc", "design"):
        d = os.path.join(root, sub)
        if os.path.isdir(d):
            for dd, _, files in os.walk(d):
                for f in sorted(files):
                    if f.lower().endswith(".md"): picks.append(os.path.join(dd, f))
    text, used, budget = "", [], 260_000
    for p in picks[:60]:
        t = _read(p, 400_000)[:60_000]
        if not t: continue
        used.append(os.path.relpath(p, root)); text += "\n" + t
        if len(text) > budget: break
    return text, used


def pitch(root):
    for f in sorted(os.listdir(root)):
        if f.lower().startswith("readme"):
            t = _read(os.path.join(root, f), 300_000)
            title = next((l.lstrip("# ").strip() for l in t.splitlines() if l.startswith("#")), None)
            paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip() and not p.strip().startswith(("#", "!", "[", "|", "```", "-", "*", ">"))]
            return title, (paras[0][:500] if paras else None)
    return None, None


def detect_engine(root, pkg, src_text_sample):
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    names = {"three": "three.js", "phaser": "Phaser", "pixi.js": "PixiJS", "@babylonjs/core": "Babylon.js", "babylonjs": "Babylon.js", "kaboom": "Kaboom", "kaplay": "KAPLAY",
             "excalibur": "Excalibur", "playcanvas": "PlayCanvas", "@react-three/fiber": "react-three-fiber", "melonjs": "melonJS", "littlejsengine": "LittleJS"}
    physics = {"@dimforge/rapier3d": "Rapier", "@dimforge/rapier3d-compat": "Rapier", "@dimforge/rapier3d-deterministic-compat": "Rapier (deterministic)", "@dimforge/rapier2d": "Rapier 2D",
               "@dimforge/rapier2d-compat": "Rapier 2D", "matter-js": "Matter.js", "cannon-es": "cannon-es", "cannon": "cannon.js", "planck": "Planck.js", "planck-js": "Planck.js", "ammo.js": "ammo.js", "p2": "p2.js"}
    eng = [v for k, v in names.items() if k in deps]
    phys = [v for k, v in physics.items() if k in deps]
    if os.path.exists(os.path.join(root, "project.godot")): eng.append("Godot")
    if os.path.isdir(os.path.join(root, "ProjectSettings")) and os.path.isdir(os.path.join(root, "Assets")): eng.append("Unity")
    if not eng:
        if re.search(r"getContext\(\s*['\"]2d", src_text_sample): eng.append("Canvas 2D (no engine)")
        elif re.search(r"getContext\(\s*['\"]webgl", src_text_sample): eng.append("WebGL (no engine)")
        elif re.search(r"from ['\"]three['\"]|THREE\.", src_text_sample): eng.append("three.js")
        else: eng.append("DOM / unknown")
    return {"engines": eng, "physics": phys, "dependencies": sorted(deps)[:80]}


def detect_build(root, pkg):
    scripts = pkg.get("scripts") or {}
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    bundler = next((b for b in ("vite", "webpack", "parcel", "esbuild", "rollup", "next") if b in deps), None)
    out = "dist" if bundler in ("vite", "parcel", "rollup", "esbuild") else "build" if bundler == "webpack" else None
    for f in ("vite.config.ts", "vite.config.js", "vite.config.mjs"):
        t = _read(os.path.join(root, f))
        m = re.search(r"outDir\s*:\s*['\"]([^'\"]+)", t)
        if m: out = m.group(1)
    pm = "pnpm" if os.path.exists(os.path.join(root, "pnpm-lock.yaml")) else "yarn" if os.path.exists(os.path.join(root, "yarn.lock")) else "npm"
    static = os.path.exists(os.path.join(root, "index.html")) and not bundler
    playable = None
    if static: playable = root
    elif out and os.path.exists(os.path.join(root, out, "index.html")): playable = os.path.join(root, out)
    return {"bundler": bundler, "package_manager": pm, "static_site": static, "output_dir": out, "build_command": (f"{pm} run build" if "build" in scripts else None),
            "install_command": (f"{pm} install" if pkg else None), "test_command": (f"{pm} test" if "test" in scripts else None), "scripts": scripts,
            "playable_dir": playable, "built": bool(playable),
            "note": None if playable else (f"not built yet: run `{pm} install && {pm} run build` in the project (outside the sandbox: needs the package registry), then pass target={out or 'dist'}" if bundler else "no index.html found")}


def scan(root, extra_patterns=None):
    root = os.path.abspath(root)
    pkg = {}
    try: pkg = json.load(open(os.path.join(root, "package.json")))
    except Exception: pass
    sigs = {k: {"count": 0, "files": set(), "where": []} for k in SIGNALS}
    extra = {k: re.compile("|".join(f"(?:{p})" for p in pats), re.I) for k, pats in (extra_patterns or {}).items()}
    xs = {k: {"count": 0, "files": set(), "where": []} for k in extra}
    comp = {k: re.compile(v[0], re.I) for k, v in SIGNALS.items()}
    counts = {"source": 0, "tests": 0, "audio": 0, "images": 0, "models": 0, "lines": 0}
    keys, hooks, sample, test_text = {}, {}, "", ""
    for p in _walk(root):
        rel = os.path.relpath(p, root); ext = os.path.splitext(p)[1].lower()
        if ext in AUDIO_EXT: counts["audio"] += 1; continue
        if ext in IMAGE_EXT: counts["images"] += 1; continue
        if ext in MODEL_EXT: counts["models"] += 1; continue
        if ext not in SRC_EXT or counts["source"] + counts["tests"] > MAX_FILES: continue
        t = _read(p)
        if not t or (ext in (".js", ".mjs") and "\n" not in t[:5000] and len(t) > 20000): continue   # minified bundle
        is_test = bool(TEST_RE.search(rel.replace(os.sep, "/")))
        if is_test or rel.startswith(("scripts/", "tools/")) and re.search(r"tune|solver|simulat|balance|\bpar\b|playtest|bot", t, re.I):
            counts["tests" if is_test else "source"] += 1; test_text += "\n" + rel + "\n" + t[:20000]
            if is_test: continue
        else: counts["source"] += 1
        counts["lines"] += t.count("\n")
        if len(sample) < 400_000: sample += t[:40_000]
        lines = None
        for k, rx in list(comp.items()) + [(k, v) for k, v in extra.items()]:
            store = sigs if k in sigs else xs
            ms = list(rx.finditer(t))
            if not ms: continue
            s = store[k]; s["count"] += len(ms); s["files"].add(rel)
            if len(s["where"]) < 4:
                if lines is None: lines = t.split("\n")
                ln = t.count("\n", 0, ms[0].start()) + 1
                s["where"].append(f"{rel}:{ln}: {lines[ln - 1].strip()[:110]}")
        for m in KEY_RE.finditer(t): keys[m.group(1)] = keys.get(m.group(1), 0) + 1
        for m in PROP_KEY_RE.finditer(t): keys[m.group(1)] = keys.get(m.group(1), 0) + 1
        for m in SHORT_KEY_RE.finditer(t):
            c = m.group(1); k = "Space" if c == " " else "Key" + c.upper()
            keys[k] = keys.get(k, 0) + 1
        for m in HOOK_RE.finditer(t):
            n = m.group(1)
            if n not in HOOK_SKIP and not n.startswith("on"): hooks[n] = hooks.get(n, 0) + 1
    for store in (sigs, xs):
        for v in store.values(): v["files"] = len(v["files"])
    sigs["audio"] = {"count": sigs["webaudio"]["count"] + sigs["audio_lib"]["count"] + counts["audio"], "files": counts["audio"],
                     "where": sigs["webaudio"]["where"][:2] + sigs["audio_lib"]["where"][:1] + ([f"{counts['audio']} audio files"] if counts["audio"] else [])}
    sigs["tests"] = {"count": counts["tests"], "files": counts["tests"], "where": [f"{counts['tests']} test files"] if counts["tests"] else []}
    tt = re.findall(r"tune|solver|solvable|simulat|balance|\bpar\b|playtest|bot\b|win ?rate", test_text, re.I)
    sigs["tune_tests"] = {"count": len(tt), "files": 0, "where": sorted(set(re.findall(r"^\S+\.(?:ts|js|mjs|py)$", test_text, re.M)))[:4] if tt else []}
    docs, doc_files = docs_text(root)
    title, pt = pitch(root)
    engine = detect_engine(root, pkg, sample)
    build = detect_build(root, pkg)
    mob_doc = re.findall(r"\b(iphone|ipad|mobile|phone|touch|ios|android|home screen|safari|thumb)\b", docs, re.I)
    html = _read(os.path.join(root, "index.html"))
    mobile_reasons = []
    if len(mob_doc) >= 2: mobile_reasons.append(f"docs mention mobile/touch {len(mob_doc)} times")
    if sigs["input_touch"]["count"]: mobile_reasons.append("touch input in source")
    if re.search(r"name=[\"']viewport", html): mobile_reasons.append("viewport meta in index.html")
    mobile = len(mob_doc) >= 2 or (sigs["input_touch"]["count"] > 0 and bool(re.search(r"name=[\"']viewport", html)))
    ordered_keys = [k for k, _ in sorted(keys.items(), key=lambda kv: -kv[1])]
    return {"root": root, "name": pkg.get("name") or os.path.basename(root), "title": title, "pitch": pt, "description": pkg.get("description"),
            "docs": doc_files, "docs_chars": len(docs), "engine": engine, "build": build, "counts": counts,
            "signals": sigs, "genre_signals": xs, "keys": ordered_keys[:16],
            "hooks": [h for h, _ in sorted(hooks.items(), key=lambda kv: -kv[1])][:12],
            "mobile": {"intended": mobile, "reasons": mobile_reasons}, "_docs": docs, "_code": sample}


def detect_genres(info, profiles):
    """Multi-label: docs count fully, code keywords at 40 %. Every genre within 45 % of the best (and with real
    evidence) is kept; three or more strong genres also mark the game hybrid."""
    docs, code = info.get("_docs", "").lower(), info.get("_code", "").lower()
    title = " ".join(filter(None, [info.get("title"), info.get("pitch"), info.get("description")])).lower()
    scores = {}
    for gid, g in profiles.items():
        s, why = 0.0, []
        for kw in g.get("doc_keywords", []):
            n = len(re.findall(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", docs))
            n_t = len(re.findall(r"(?<![a-z0-9])" + re.escape(kw.lower()) + r"(?![a-z0-9])", title))
            if n or n_t:
                s += 1 + math.log1p(n) + 2.0 * min(n_t, 2); why.append(f"{kw}×{n + n_t}")
        for kw in g.get("code_keywords", []):
            n = len(re.findall(re.escape(kw.lower()), code))
            if n: s += 0.4 * (1 + math.log1p(n)); why.append(f"code:{kw}")
        scores[gid] = (round(s, 2), why[:10])
    best = max((v[0] for v in scores.values()), default=0)
    picked = sorted([(g, v) for g, v in scores.items() if best and g != "hybrid_experimental" and (v[0] == best or (v[0] >= 0.45 * best and v[0] >= 5))], key=lambda x: -x[1][0])[:4]
    out = [{"genre": g, "title": profiles[g]["title"], "score": v[0], "share": round(v[0] / best, 2), "evidence": v[1]} for g, v in picked]
    strong = [x for x in out if x["share"] >= 0.6]
    hybrid = len(strong) >= 3 or scores.get("hybrid_experimental", (0,))[0] >= max(3, 0.6 * best)
    hybrid = hybrid or not out
    if hybrid:
        out.append({"genre": "hybrid_experimental", "title": profiles["hybrid_experimental"]["title"], "score": scores.get("hybrid_experimental", (0,))[0],
                    "share": None, "evidence": ["three or more genres score strongly" if hybrid else "no genre matched clearly"]})
    return {"genres": out, "primary": out[0]["genre"], "hybrid": hybrid, "all_scores": {g: v[0] for g, v in sorted(scores.items(), key=lambda kv: -kv[1][0])}}
