"""PROJECT MATURITY: what state an existing project is in, with evidence, read-only.

  assess(project)    → {maturity, kind, confidence, evidence, inventory, preserve, deploy, tests, ...}
                       maturity: new | partial | nearly_complete | finished
                       kind:     game | app | site
                       inventory: working (features the project already has), unfinished (TODOs, unchecked
                       roadmap items, stubs), defects (references to files that do not exist), improvements
                       (optional: no tests, no deploy config, ...). Every item names the file it came from.
  intent(text, maturity)  what the person asked for: build | continue | complete | update | fix | review
  baseline(project)  what must be preserved (hashes of every existing file, save keys, env/CI/deploy files),
                     written into the production store (never into the project) for qa.preserve

Nothing here writes to the project or runs its code. A heuristic is labelled as one: `confidence` says how many
independent signals agree, and the Decision Room lets the person correct the reading."""
import hashlib, json, os, re, subprocess

SKIP = {".git", "node_modules", "dist", "build", ".next", "out", "__pycache__", ".venv", "venv", "gitcraft-out", ".cache", "coverage", ".vercel"}
CODE = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".astro", ".py", ".gd", ".cs", ".html", ".css")
ASSET = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".wav", ".ogg", ".mp3", ".glb", ".gltf", ".json", ".tmj", ".ldtk", ".ttf", ".woff2")
DEPLOY = ["vercel.json", "netlify.toml", "CNAME", "firebase.json", "fly.toml", "render.yaml", "wrangler.toml", "Dockerfile", "app.yaml", ".github/workflows"]
SENSITIVE = re.compile(r"(^|/)(\.env(\..+)?|.*\.pem|.*\.key|id_rsa.*|credentials.*\.json|secrets?\..*)$", re.I)
GAME_WORDS = re.compile(r"\b(game|player|level|score|enemy|enemies|jump|platformer|sprite|highscore|high score|lives|boss|gameplay)\b", re.I)
# Stubs come from code only, never from words inside a string literal or a document ("illustrative mockup: layout
# concept, not implemented UI" in a manifest is prose, not a stub). Each pattern must START in code (scan below).
STUB = re.compile(r"(raise\s+NotImplementedError\b|throw\s+new\s+Error\(\s*['\"`](?:todo|not (?:yet )?implemented|unimplemented)[^'\"`]*['\"`]\s*\)|"
                  r"\btodo!\(\)|\bunimplemented!\(\))", re.I)
TODO = re.compile(r"(?://+|#+|<!--|/\*+|^\s*\*)\s*(TODO|FIXME|HACK|XXX)\b[:\s]*(.{0,90})", re.I | re.M)
PASS_BODY = re.compile(r"^([ \t]*)def\s+(\w+)\s*\([^)]*\)[^:\n]*:[ \t]*\n(?:[ \t]*\n)*([ \t]+)(?:pass|\.\.\.)[ \t]*$", re.M)


_SPAN_JS = re.compile(r"//[^\n]*|/\*.*?\*/|<!--.*?-->|`(?:\\.|[^`\\])*`|\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*'", re.S)
_SPAN_PY = re.compile(r"#[^\n]*|\"\"\"(?:\\.|.)*?\"\"\"|'\'\'(?:\\.|.)*?'\'\'|[rbfuRBFU]{0,2}\"(?:\\.|[^\"\\\n])*\"|[rbfuRBFU]{0,2}'(?:\\.|[^'\\\n])*'", re.S)


def spans(path, text):
    """[(start, end, 'string' | 'comment')] of a source file's string literals and comments (a light lexer: enough to
    tell code from prose; regex literals in JS are read as code)."""
    rx = _SPAN_PY if path.endswith((".py", ".gd")) else _SPAN_JS
    out = []
    for m in rx.finditer(text):
        g = m.group(0)
        out.append((m.start(), m.end(), "comment" if g.startswith(("#", "//", "/*", "<!--")) else "string"))
    return out


def _kind_at(sp, i):
    import bisect
    k = bisect.bisect_right([a for a, _, _ in sp], i) - 1
    return sp[k][2] if k >= 0 and sp[k][0] <= i < sp[k][1] else "code"


def code_signals(path, text):
    """('todo' | 'stub', what) found in CODE: TODO/FIXME comments (the marker is in a comment, not a string), stubs that
    start in code (raise NotImplementedError, throw new Error("not implemented")), and Python functions whose whole body
    is `pass` or `...` (abstract methods excepted). Words inside string literals and documents never count."""
    sp = spans(path, text); out = []
    for m in TODO.finditer(text):
        if _kind_at(sp, m.start(1)) == "comment": out.append(("todo", f"{m.group(1).upper()}: {m.group(2).strip().rstrip('*/->').strip()}"))
    for m in STUB.finditer(text):
        if _kind_at(sp, m.start()) == "code": out.append(("stub", f"stub: {m.group(0)[:60]}"))
    if path.endswith(".py"):
        for m in PASS_BODY.finditer(text):
            if _kind_at(sp, m.start(2)) != "code" or len(m.group(3)) <= len(m.group(1)): continue
            before = text[:m.start()].rstrip().rsplit("\n", 1)[-1]
            if "abstract" in before or "overload" in before: continue
            nxt = re.match(r"\n*([ \t]*)\S", text[m.end():])
            if nxt and len(nxt.group(1)) > len(m.group(1)): continue   # more body follows: not a stub
            out.append(("stub", f"stub: def {m.group(2)}(): pass"))
    return out


def _walk(root, limit=6000):
    n = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP and not (x.startswith(".") and x != ".github")]
        for f in files:
            n += 1
            if n > limit: return
            yield os.path.join(d, f)


def _read(p, n=200000):
    try:
        with open(p, errors="ignore") as f: return f.read(n)
    except OSError: return ""


def _git(root, *a):
    try:
        r = subprocess.run(["git", "-C", root, *a], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired): return None


def _sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def is_existing(project):
    """A folder with at least one file of its own (an empty or missing folder is a new project)."""
    return bool(project and os.path.isdir(project) and next(iter(_walk(project, 50)), None))


def _readme(project):
    for n in ("README.md", "readme.md", "README", "README.txt", "docs/README.md"):
        p = os.path.join(project, n)
        if os.path.isfile(p): return n, _read(p)
    return None, ""


def _features(readme):
    """Feature bullets under a Features/Roadmap/TODO heading, and every checkbox anywhere."""
    done, todo, listed = [], [], []
    for m in re.finditer(r"^\s*[-*]\s*\[( |x|X)\]\s*(.+)$", readme, re.M):
        (done if m.group(1).lower() == "x" else todo).append(m.group(2).strip()[:120])
    sec = re.search(r"^#{1,4}\s*(features|what it does|highlights)\s*$(.*?)(?=^#{1,4}\s|\Z)", readme, re.I | re.M | re.S)
    if sec:
        listed = [re.sub(r"^\[[ xX]\]\s*", "", m.strip())[:120] for m in re.findall(r"^\s*[-*]\s+(.+)$", sec.group(2), re.M)]
    return done, todo, listed


def _refs(html):
    out = []
    for m in re.finditer(r"""<(?:script|img|link|audio|source|video)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"'#?]+)""", html, re.I):
        u = m.group(1)
        if not re.match(r"^[a-z]+:|^//|^data:|^\{|^\$", u, re.I): out.append(u)
    for m in re.finditer(r"""(?:fetch|new Audio|loadImage|load\.(?:image|audio|json))\(\s*["']([^"'#?]+\.(?:json|png|jpg|ogg|wav|mp3|svg|webp))["']""", html):
        out.append(m.group(1))
    return out


VITE_CONFIG = re.compile(r"(^|/)vite(\.[\w-]+)*\.config\.(m?[jt]s|c[jt]s)$|(^|/)vite\.[\w-]+\.(m?[jt]s|c[jt]s)$")


def _vite_roots(project, rel):
    """Every Vite (or Vite-like) config in the project → the folder it serves: its `root:` option, resolved from the
    config's own folder, else that folder. A page is served from the nearest of these roots that contains it."""
    out = []
    for r in rel:
        if not VITE_CONFIG.search(r): continue
        cdir = os.path.dirname(os.path.join(project, r))
        m = re.search(r"""\broot\s*:\s*['"`]([^'"`]+)['"`]""", _read(os.path.join(project, r), 20000))
        root = os.path.normpath(os.path.join(cdir, m.group(1))) if m else cdir
        out.append(os.path.realpath(root))
    return sorted(set(out), key=len, reverse=True)


def _serve_roots(project, page, vite):
    """The folders a root-absolute URL (/x) in `page` can be served from, nearest first: the Vite roots that contain
    the page, the page's own folder, and the project root; each with its public/ folder (Vite serves both)."""
    pdir = os.path.realpath(os.path.dirname(os.path.join(project, page)))
    cands = [v for v in vite if pdir == v or pdir.startswith(v + os.sep)] + [pdir, os.path.realpath(project)]
    out = []
    for c in cands:
        for x in (c, os.path.join(c, "public")):
            if x not in out: out.append(x)
    return out


def _resolves(project, page, u, vite):
    """A reference resolves when any plausible root has the file (flag it missing only when none does)."""
    rel_u = u.split("?")[0]
    if not rel_u.startswith("/"):
        return os.path.exists(os.path.normpath(os.path.join(project, os.path.dirname(page), rel_u))) or \
               os.path.exists(os.path.join(project, "public", rel_u))
    parts = [x for x in rel_u.split("/") if x]
    # the path as written, and without its first segment: a page built from a copy (a kit whose README copies it into
    # src/) or for a sub-path (Vite base '/GAME/') asks for /src/x or /GAME/x; TestCraft serves builds the same way
    tries = [parts] + ([parts[1:]] if len(parts) > 1 else [])
    return any(os.path.exists(os.path.join(root, *t)) for root in _serve_roots(project, page, vite) for t in tries)


def _shipped_pages(project, rel, entry):
    """The pages the project ships: its entry page and the inputs of the main build config. Other pages (a test
    harness, a verification page served by its own config) rank lower: a broken reference there does not reach players."""
    out = {r for r in (entry, "index.html") if r and r.endswith(".html")}
    for r in rel:
        if VITE_CONFIG.search(r) and os.path.dirname(r) == "" :
            for m in re.finditer(r"""['"`]([\w./-]+\.html)['"`]""", _read(os.path.join(project, r), 20000)): out.add(os.path.normpath(m.group(1)).lstrip("./"))
    return out


TEMPLATE_DIR = re.compile(r"(^|/)(starters?|templates?|fixtures?|__fixtures__|examples?|boilerplates?|scaffolds?)/")
GAME_ENGINES = (("phaser", r"from ['\"]phaser['\"]|new Phaser\.Game|\bPhaser\.(Scene|Game)\b"), ("pixi", r"from ['\"]pixi\.js['\"]|\bPIXI\.Application\b"),
                ("kaboom", r"from ['\"]kaboom['\"]|\bkaboom\(\s*\{"), ("godot", r"extends (Node2D|KinematicBody2?D?|CharacterBody[23]D)"),
                ("three", r"\bTHREE\.|from ['\"]three['\"]"))
GAME_DEPS = {"phaser": "phaser", "pixi.js": "pixi", "kaboom": "kaboom", "kaplay": "kaboom", "three": "three", "excalibur": "excalibur",
             "melonjs": "melonjs", "@babylonjs/core": "babylon", "babylonjs": "babylon", "playcanvas": "playcanvas", "matter-js": "matter"}
# what an application has and a game rarely does: a UI framework, a data layer, forms and routes
APP_DEPS = ("next", "react-dom", "vue", "nuxt", "svelte", "@sveltejs/kit", "@angular/core", "@remix-run/react", "solid-js", "astro",
            "dexie", "idb", "prisma", "@prisma/client", "@supabase/supabase-js", "firebase", "drizzle-orm", "mongoose", "express", "@tanstack/react-query")
APP_CODE = re.compile(r"<form\b|\bonSubmit\b|addEventListener\(\s*['\"]submit|\buseRouter\b|\bnext/navigation\b|\bindexedDB\b|\bfetch\(\s*['\"`]/api/")
_COMMENTS = re.compile(r"/\*.*?\*/|<!--.*?-->|(?<![:\"'\w])//[^\n]*|^\s*#[^\n]*", re.S | re.M)


def _kind(src, readme, deps, scripts, rel):
    """game | app | site, with its own confidence and evidence. Game words count only in code (comments and
    stylesheets left out, where 'level', 'lives' and 'score' are ordinary English) and in the README; a 2D canvas
    alone is not a game engine (readers, charts and editors draw on canvases too); app signals count against."""
    code = {r: _COMMENTS.sub(" ", t) for r, t in src.items() if not r.endswith(".css")}
    text = " ".join(code.values())[:400000]
    strong = sorted({e for e, pat in GAME_ENGINES if re.search(pat, text)} | {v for k, v in GAME_DEPS.items() if k in deps})
    canvas_files = [r for r, t in code.items() if re.search(r"getContext\(\s*['\"]2d", t)]
    # a canvas counts as a game engine only with a game loop and player input in the same file
    canvas_loop = [r for r in canvas_files if re.search(r"requestAnimationFrame|setInterval\(", code[r]) and
                   re.search(r"key(down|up)|\bpointerdown\b|\btouchstart\b|\bgamepad", code[r], re.I)]
    words = GAME_WORDS.findall(text[:200000]) + GAME_WORDS.findall(readme)
    hits = len(words)
    readme_game = bool(re.search(r"\b(a|an|the|this)\s+(?:[\w-]+\s+){0,3}(game|platformer|roguelike|shooter|puzzler)\b", readme, re.I))
    app_sig = sorted({d for d in APP_DEPS if d in deps} | ({"app routes"} if any(r.startswith(("app/", "pages/", "src/app/", "src/pages/")) and r.endswith((".tsx", ".jsx")) for r in rel) else set())
                     | ({"forms / data layer in code"} if APP_CODE.search(text) else set()))
    game_files = [r for r in rel if re.search(r"(\.tscn|(^|/)project\.godot|\.tmj|\.tmx|\.ldtk|\.yarn)$", r)]
    game_entry = [r for r in rel if re.search(r"(^|/)(game|main_game)\.(ts|js|mjs)$|(^|/)src/game/", r)]
    if any(r.endswith(".tscn") or r.endswith("project.godot") for r in game_files) and "godot" not in strong: strong.append("godot")
    engines = strong + (["canvas"] if canvas_files else [])
    ev = []
    if game_files: ev.append(f"game project files: {', '.join(game_files[:3])}" + (f" (+{len(game_files) - 3})" if len(game_files) > 3 else ""))
    if game_entry: ev.append(f"game code: {game_entry[0]}")
    if strong: ev.append(f"game engine: {', '.join(strong)}")
    if canvas_files: ev.append(f"2D canvas in {len(canvas_files)} file(s)" + (f", with a game loop and input in {canvas_loop[0]}" if canvas_loop else " (no game loop with player input: not counted as a game engine)"))
    ev.append(f"{hits} game words in code and README (comments and CSS excluded)")
    if readme_game: ev.append("the README calls it a game")
    if app_sig: ev.append(f"app signals: {', '.join(app_sig[:6])}")
    game_score = (3 if game_files else 0) + (1 if game_entry else 0) + (3 if strong and (hits >= 3 or game_files) else 0) + (2 if canvas_loop else 0) + (2 if readme_game else 0) + (1 if canvas_files and hits >= 6 else 0) + (2 if hits >= 25 else 0)
    app_score = len(app_sig)
    if game_score >= 3 and game_score > app_score:
        kind = "game"
        conf = "high" if game_score >= 5 and app_score == 0 else "medium" if game_score - app_score >= 2 else "low"
    else:
        kind = "site" if not scripts.get("dev") and not app_sig and not re.search(r"\b(useState|localStorage|fetch\()", text) else "app"
        conf = "high" if game_score == 0 and hits < 6 else "medium" if game_score <= 2 else "low"
    return kind, conf, engines, ev


def kind(project):
    """game | app | site for a project folder, with confidence and evidence (read-only; PLAYCRAFT uses it to refuse
    scoring something that is not a game)."""
    files = list(_walk(project)); rel = [os.path.relpath(f, project) for f in files]
    src = {os.path.relpath(f, project): _read(f) for f in [f for f in files if f.endswith(CODE)][:400]}
    pkg = {}
    try: pkg = json.load(open(os.path.join(project, "package.json")))
    except (OSError, ValueError): pass
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    k, conf, engines, ev = _kind(src, _readme(project)[1], deps, pkg.get("scripts") or {}, rel)
    return {"kind": k, "confidence": conf, "engines": engines, "evidence": ev}


def assess(project):
    """Read-only maturity assessment with evidence. Never runs the project."""
    if not is_existing(project):
        return {"maturity": "new", "kind": None, "confidence": "high", "evidence": ["no project folder, or it is empty"], "inventory": {}, "existing": False}
    files = list(_walk(project)); rel = [os.path.relpath(f, project) for f in files]
    code = [f for f in files if f.endswith(CODE)]
    lines = sum(_read(f).count("\n") for f in code[:400])
    src = {os.path.relpath(f, project): _read(f) for f in code[:400]}
    rname, readme = _readme(project)
    done, todo_boxes, listed = _features(readme)
    ev, inv = [], {"working": [], "unfinished": [], "defects": [], "improvements": []}
    # entry and build
    entry = next((r for r in ("index.html", "public/index.html", "src/index.html", "src/main.tsx", "src/main.ts", "src/main.js", "app/page.tsx", "pages/index.tsx", "main.py") if r in rel), None)
    pkg = {}
    if "package.json" in rel:
        try: pkg = json.load(open(os.path.join(project, "package.json")))
        except ValueError: inv["defects"].append({"what": "package.json is not valid JSON", "where": "package.json"})
    scripts = pkg.get("scripts") or {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    ev.append(f"{len(files)} files, {len(code)} code files, ~{lines} lines of code" + (f"; entry {entry}" if entry else "; no entry point found"))
    # kind
    kind, kind_conf, engines, kind_ev = _kind(src, readme, deps, scripts, rel)
    ev.append(f"kind {kind} ({kind_conf} confidence): " + "; ".join(kind_ev))
    # what works (evidence: the README's own feature list and checked boxes)
    inv["working"] += [{"what": f, "where": rname, "evidence": "checked in the README"} for f in done]
    inv["working"] += [{"what": f, "where": rname, "evidence": "listed as a feature in the README (not run)"} for f in listed if f not in done and f not in todo_boxes]
    if entry: inv["working"].append({"what": f"entry point {entry}", "where": entry, "evidence": "exists"})
    # unfinished
    inv["unfinished"] += [{"what": t, "where": rname, "evidence": "unchecked in the README"} for t in todo_boxes]
    todos = []
    for r, t in src.items():
        for kind_, what in code_signals(r, t):
            (todos if kind_ == "todo" else inv["unfinished"]).append({"what": what, "where": r})
    inv["unfinished"] += todos[:40]
    # defects: references to files that are not there
    vite = _vite_roots(project, rel)
    shipped = _shipped_pages(project, rel, entry)
    for r, t in src.items():
        # template folders (a starter kit, fixtures, examples) hold placeholders a build fills in: not the project's own pages
        if not r.endswith(".html") or TEMPLATE_DIR.search(r): continue
        for u in _refs(t):
            if not _resolves(project, r, u, vite):
                inv["defects"].append({"what": f"references a missing file: {u}", "where": r, "entry": r in shipped,
                                       "roots": [os.path.relpath(x, project) for x in _serve_roots(project, r, vite)][:6]})
    # tests, deploy, CI, git
    tests = [r for r in rel if re.search(r"(^|/)(tests?|__tests__|spec)/|\.(test|spec)\.[jt]sx?$|^test_.*\.py$", r)]
    deploy = [d for d in DEPLOY if os.path.exists(os.path.join(project, d))]
    if not tests: inv["improvements"].append({"what": "no automated tests", "where": None})
    if not deploy: inv["improvements"].append({"what": "no deployment configuration found", "where": None})
    commits = _git(project, "rev-list", "--count", "HEAD"); last = _git(project, "log", "-1", "--format=%cs")
    if commits: ev.append(f"git: {commits} commits, last {last}")
    ev.append(f"README: {len(done)} done, {len(todo_boxes)} open checkboxes; code: {len(todos)} TODO/FIXME, "
              f"{sum(1 for x in inv['unfinished'] if x['what'].startswith('stub'))} stubs; {len(inv['defects'])} missing references; "
              f"{len(tests)} test files; deploy: {', '.join(deploy) or 'none'}")
    # maturity: independent signals, each votes
    open_items = len(todo_boxes) + sum(1 for x in inv["unfinished"] if x["what"].startswith("stub"))
    votes = []
    if not entry or lines < 80: votes.append(("partial", "no entry point or under 80 lines of code"))
    if open_items and open_items >= max(3, len(done)): votes.append(("partial", f"{open_items} open roadmap items/stubs vs {len(done)} done"))
    elif 0 < open_items <= 3 or (0 < len(todos) <= 8 and not inv["defects"]): votes.append(("nearly_complete", f"a few open items ({open_items} roadmap/stubs, {len(todos)} TODOs)"))
    if inv["defects"]: votes.append(("nearly_complete" if entry and lines >= 80 else "partial", f"{len(inv['defects'])} missing file references"))
    if entry and lines >= 80 and not open_items and not inv["defects"] and len(todos) <= 2:
        votes.append(("finished", "an entry point, no open roadmap items, stubs or missing files"))
        if deploy: votes.append(("finished", f"deployment configured ({', '.join(deploy)})"))
        if tests: votes.append(("finished", f"{len(tests)} test files"))
    tally = {}
    for m, _ in votes: tally[m] = tally.get(m, 0) + 1
    order = ["partial", "nearly_complete", "finished"]
    maturity = max(tally, key=lambda m: (tally[m], -order.index(m))) if tally else "nearly_complete"
    agree, total = tally.get(maturity, 0), len(votes)
    confidence = "high" if agree >= 2 and agree == total else "medium" if agree >= max(1, total - agree) else "low"
    if not votes: ev.append("no strong signal either way: read as nearly complete (low confidence)"); confidence = "low"
    ev += [f"{m}: {why}" for m, why in votes]
    return {"existing": True, "maturity": maturity, "kind": kind, "kind_confidence": kind_conf, "kind_evidence": kind_ev, "engines": engines,
            "confidence": confidence, "evidence": ev, "inventory": inv,
            "entry": entry, "tests": tests[:20], "deploy": deploy, "test_script": scripts.get("test"), "readme": rname,
            "analytics": _analytics(project), "save_keys": save_keys(src), "git": {"commits": commits, "last": last, "branch": _git(project, "rev-parse", "--abbrev-ref", "HEAD"),
                                                  "remote": _git(project, "remote", "get-url", "origin"), "dirty": bool(_git(project, "status", "--porcelain"))}}


def _analytics(project):
    """Analytics the project already ships (HaveAnApp Pulse, Vercel, Google, Plausible…): recognised, not imposed."""
    from . import standards
    try: return standards.discover_analytics(project)
    except Exception: return []


def save_keys(src):
    """localStorage / IndexedDB keys the code reads or writes: a game's saves and progression live there."""
    keys = set()
    for t in src.values():
        keys |= set(re.findall(r"localStorage\.(?:getItem|setItem|removeItem)\(\s*['\"`]([^'\"`]{1,60})['\"`]", t))
        keys |= set(re.findall(r"indexedDB\.open\(\s*['\"`]([^'\"`]{1,60})['\"`]", t))
    return sorted(keys)


# ---------------------------------------------------------------- what the person asked for
INTENTS = [
    ("review", r"\b(review|audit|assess|evaluate|what state|how complete|inspect)\b(?!.*\b(fix|add|build|implement|finish)\b)"),
    ("fix", r"\b(fix|bug|broken|crash|error|doesn'?t work|not working|repair|regression)\b"),
    ("complete", r"\b(finish|complete|ship|launch|release|get it (?:done|live)|ready for (?:release|launch)|polish (?:it )?for release)\b"),
    ("continue", r"\b(continue|keep (?:building|going|working)|pick up where|carry on|next steps?|remaining features)\b"),
    ("update", r"\b(add|change|update|improve|tweak|adjust|replace|remove|rename|redesign|support|make it|implement|upgrade|migrate)\b"),
]


def intent(text, maturity):
    t = " ".join((text or "").lower().split())
    if maturity == "new": return "build", "a new project"
    for name, pat in INTENTS:
        m = re.search(pat, t)
        if m: return name, f"'{m.group(0)}'"
    return {"partial": "continue", "nearly_complete": "complete", "finished": "update"}.get(maturity, "update"), f"no request named: the {maturity.replace('_', ' ')} default"


WORKFLOW = {
    "build": "new build: optional Recon → Discovery → Decision Room → build → verify → deliver",
    "continue": "continue a partially built project: finish the unfinished features in priority order; never rebuild what works",
    "complete": "finish a nearly complete project: fix the genuine blockers, meet the completion criteria, verify",
    "update": "change a finished project: only the requested change and the fixes it needs",
    "fix": "fix what is broken: the defect and a regression check; nothing else changes",
    "review": "review only: the Discovery Report, no changes to the project",
}


# ---------------------------------------------------------------- the preservation baseline (stored in the production store)
def baseline(project):
    """Every existing file's hash, plus what is never changed without approval. Read-only on the project."""
    files = {}
    for f in _walk(project, 20000):
        r = os.path.relpath(f, project)
        try: files[r] = _sha(f)
        except OSError: pass
    # .env and other secrets are skipped by _walk only when inside dot-folders; include top-level dotfiles explicitly
    for f in os.listdir(project):
        p = os.path.join(project, f)
        if f.startswith(".") and os.path.isfile(p) and SENSITIVE.search(f): files[f] = _sha(p)
    src = {r: _read(os.path.join(project, r)) for r in files if r.endswith(CODE)}
    return {"files": files, "save_keys": save_keys(src),
            "sensitive": sorted(r for r in files if SENSITIVE.search(r)),
            "infra": sorted(r for r in files if r in DEPLOY or r.startswith(".github/workflows/") or r in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")),
            "assets": sorted(r for r in files if r.endswith(ASSET) and not r.endswith(("package.json", "package-lock.json", "tsconfig.json", "manifest.json")))}


def preserve_check(project, base, allow=(), kind="app"):
    """→ {status, checks, changed, added, removed}: what the build changed against the baseline."""
    allow = set(allow or ())
    now = {}
    for f in _walk(project, 20000):
        r = os.path.relpath(f, project)
        try: now[r] = _sha(f)
        except OSError: pass
    for f in os.listdir(project):
        if f.startswith(".") and os.path.isfile(os.path.join(project, f)) and SENSITIVE.search(f): now[f] = _sha(os.path.join(project, f))
    was = base["files"]
    removed = sorted(r for r in was if r not in now)
    changed = sorted(r for r in was if r in now and now[r] != was[r])
    added = sorted(r for r in now if r not in was)
    ok_ = lambda rs: [r for r in rs if r not in allow and not any(r.startswith(a.rstrip("*")) for a in allow if a.endswith("*"))]
    checks = [{"name": "no existing file was deleted (unless approved)", "ok": not ok_(removed), "detail": ok_(removed)[:20] or None},
              {"name": "secrets and env files untouched", "ok": not [r for r in base["sensitive"] if r in changed or r in removed],
               "detail": [r for r in base["sensitive"] if r in changed or r in removed] or None},
              {"name": "CI, deployment and lockfiles unchanged (unless approved)", "ok": not ok_([r for r in base["infra"] if r in changed or r in removed]),
               "detail": ok_([r for r in base["infra"] if r in changed or r in removed]) or None}]
    if kind == "game":
        checks.append({"name": "existing game assets unchanged: art, audio, levels (unless approved)", "ok": not ok_([r for r in base["assets"] if r in changed or r in removed]),
                       "detail": ok_([r for r in base["assets"] if r in changed or r in removed])[:20] or None})
    if base.get("save_keys"):
        src = " ".join(_read(f) for f in _walk(project) if f.endswith(CODE))
        lost = [k for k in base["save_keys"] if k not in src]
        checks.append({"name": "saved data still loads: every existing save/progression key is still used", "ok": not lost, "detail": lost or None,
                       "measured": f"{len(base['save_keys']) - len(lost)}/{len(base['save_keys'])} keys"})
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks,
            "changed": changed[:200], "added": added[:200], "removed": removed[:200]}
