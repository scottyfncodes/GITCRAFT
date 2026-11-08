"""ENGINEERING STANDARDS: proportionate quality checks for every app GITCRAFT makes, plus the HaveAnApp attribution.

Appropriate engineering, not maximum engineering. The intake picks a profile from what the prompt says about who
uses the app and what it holds; the Decision Room confirms it:

  personal    a private tool or game for a handful of people: no accounts, no sensitive data
  public      anyone can open it, or it has accounts/sign-in: input validation, dependency hygiene, no secrets
  sensitive   payments, health, financial or personal data: everything above, plus storage, auth and rate limits

Each check is measured statically on the project's files and reports one of:
  ok / failed   measured (failed gates qa.standards for the profiles that require it)
  review        the check applies but cannot be decided from files (it goes to the build work order and the report
                as an explicit review item, never as a pass)
  n/a           does not apply to this project

attribution(project) measures the HaveAnApp byline (kit/haveanapp): visible text marked data-haveanapp, linked
only to the verified official URL. docs/app-standards.md is the human-readable version of this file."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "kit", "haveanapp")
SKIP = {".git", "node_modules", "dist", "build", ".next", "out", "__pycache__", ".venv", "venv", "gitcraft-out", ".cache", "coverage"}
CODE = (".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".vue", ".svelte", ".astro", ".py", ".css")
PROFILES = ["personal", "public", "sensitive"]

# words in the prompt → profile (the strongest match wins; the Decision Room shows why)
PROFILE_WORDS = {
    "sensitive": ["payment", "payments", "credit card", "stripe", "checkout", "health", "medical", "patient", "financial", "bank", "banking",
                  "personal data", "pii", "passwords", "children", "kids' data", "insurance records", "hipaa", "gdpr", "ssn"],
    "public": ["login", "log in", "sign in", "sign-in", "sign up", "signup", "accounts", "user accounts", "users", "customers", "public",
               "multiplayer", "leaderboard", "community", "social", "marketplace", "saas", "clients", "subscribers", "database", "backend", "api"],
    "personal": ["for me", "for myself", "personal", "private", "my family", "my friends", "five friends", "a few friends", "just me", "internal", "hobby"],
}


def attribution_config():
    with open(os.path.join(KIT, "attribution.json")) as f: return json.load(f)


def profile_for(text, deliverable):
    """(profile, because-words). Sensitive beats public beats personal; with no signal: a site is public, others personal."""
    t = " " + " ".join(str(text).lower().split()) + " "
    for p in ("sensitive", "public", "personal"):
        hits = [w for w in PROFILE_WORDS[p] if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t)]
        if hits: return p, hits
    return ("public" if deliverable == "site" else "personal"), []


def instructions(profile, deliverable):
    """What the build work order asks for, scaled to the profile."""
    ins = ["Engineering standard (" + profile + "): " + {"personal": "keep it simple; no accounts, servers or paid services unless the blueprint says so.",
                                                       "public": "validate every input at the boundary, handle errors with a visible message (never a blank screen), pin dependencies with a lockfile, keep secrets out of the repo.",
                                                       "sensitive": "everything the public standard asks, plus: authenticate and authorise every server route, rate-limit sign-in and write routes, never store tokens or personal data in localStorage, log errors without personal data, and keep environments (dev/preview/production) separate."}[profile],
           "Mobile and access: <meta name=viewport>, <html lang>, touch targets ≥ 44 px, readable contrast, and it works with reduced motion.",
           "Performance: no unused heavy libraries; images and sounds sized for their use; nothing blocks first paint for longer than it must."]
    return ins


# ---------------------------------------------------------------- file walking
def _files(project, exts=CODE, limit=4000):
    n = 0
    for d, dirs, files in os.walk(project):
        dirs[:] = [x for x in dirs if x not in SKIP and not x.startswith(".")]
        for f in files:
            if f.endswith(exts) and not f.endswith((".min.js", ".map")):
                n += 1
                if n > limit: return
                yield os.path.join(d, f)


def _read(p, n=400000):
    try:
        with open(p, errors="ignore") as f: return f.read(n)
    except OSError: return ""


def _entry(project):
    for r in ("index.html", "public/index.html", "src/index.html", "dist/index.html", "app/layout.tsx", "src/app/layout.tsx", "pages/_document.tsx"):
        if os.path.isfile(os.path.join(project, r)): return os.path.join(project, r)
    return None


# ---------------------------------------------------------------- the HaveAnApp attribution
TAG = re.compile(r"<(?P<tag>[a-zA-Z][\w.-]*)\b(?P<attrs>[^<>]*?\bdata-haveanapp\b[^<>]*)>(?P<body>.*?)</(?P=tag)>", re.S)


def _strip_nonvisible(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"<(head|title|script|style|noscript)\b.*?</\1>", "", text, flags=re.S | re.I)
    return re.sub(r"<meta\b[^>]*>", "", text, flags=re.I)


def attribution(project, cfg=None):
    """→ {status, checks, found}. The byline is visible text in a source file of the app (any framework)."""
    cfg = cfg or attribution_config(); checks, found = [], []
    for p in _files(project, (".html", ".jsx", ".tsx", ".js", ".mjs", ".vue", ".svelte", ".astro")):
        txt = _strip_nonvisible(_read(p))
        for m in TAG.finditer(txt):
            body = re.sub(r"<[^>]+>|\{[^{}]*\}", " ", m.group("body"))
            found.append({"file": os.path.relpath(p, project), "text": " ".join(body.split())[:120], "attrs": m.group("attrs"), "raw": m.group(0)[:400]})
        if not found and re.search(r"\bdata-haveanapp\b", txt) and re.search(r"by\s+HaveAnApp", txt):
            found.append({"file": os.path.relpath(p, project), "text": "by HaveAnApp", "attrs": "data-haveanapp", "raw": "(built in script)"})
    checks.append({"name": "a HaveAnApp byline marked data-haveanapp is in the app's visible markup", "ok": bool(found),
                   "detail": None if found else "add the byline from production/kit/haveanapp (footer, About/Settings, or under the name on a launch/title screen)"})
    if found:
        f = found[0]
        checks.append({"name": "the byline reads 'by HaveAnApp'", "ok": bool(re.search(r"by\s+HaveAnApp", f["text"] + f["raw"])), "detail": f["text"]})
        hidden = re.search(r"\bhidden\b|aria-hidden\s*=\s*[\"']?true|display\s*:\s*none|visibility\s*:\s*hidden", f["attrs"], re.I)
        checks.append({"name": "the byline is not hidden", "ok": not hidden, "detail": hidden.group(0) if hidden else None})
        hrefs = re.findall(r"href\s*=\s*[\"'{]+([^\"'}]+)", f["raw"])
        if cfg.get("url") and cfg.get("url_verified"):
            checks.append({"name": f"the byline links to the verified HaveAnApp site ({cfg['url']})", "ok": cfg["url"] in hrefs or any("COMPANY_URL" in h for h in hrefs), "detail": hrefs or "no link"})
        else:
            checks.append({"name": "the byline links nowhere unverified (no official HaveAnApp URL is verified yet)", "ok": not [h for h in hrefs if "haveanapp" in h.lower()],
                           "detail": hrefs or None})
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks, "found": [{k: v for k, v in f.items() if k != "raw"} for f in found[:5]], "outputs": []}


# ---------------------------------------------------------------- the engineering checks
SECRET = re.compile(r"(AKIA[0-9A-Z]{16}|sk_live_[0-9a-zA-Z]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[0-9A-Za-z]{36}|"
                    r"xox[baprs]-[0-9A-Za-z-]{10,}|AIza[0-9A-Za-z_\-]{35}|eyJhbGciOi[0-9A-Za-z_\-]{20,}\.[0-9A-Za-z_\-]{20,}|"
                    r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*[\"'][A-Za-z0-9_\-+/]{24,}[\"'])", re.I)


def _check(cid, title, status, detail=None, profiles=PROFILES):
    return {"id": cid, "name": title, "status": status, "ok": status != "failed", "detail": detail, "required_for": profiles}


def check(project, profile="personal", deliverable="app"):
    """→ {status, checks, review, profile}. A failed check required by the profile fails the gate; `review` items never pass silently."""
    out = []; codefiles = list(_files(project)); src = {p: _read(p) for p in codefiles}
    entry = _entry(project); etext = _read(entry) if entry else ""
    pkg = os.path.join(project, "package.json"); pj = {}
    if os.path.isfile(pkg):
        try: pj = json.load(open(pkg))
        except ValueError: out.append(_check("package_json", "package.json parses", "failed", "package.json is not valid JSON"))
    deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
    server = [p for p in codefiles if re.search(r"(^|/)(api|server|functions|routes)/", os.path.relpath(p, project)) or
              re.search(r"\b(express\(|createServer\(|fastify\(|Hono\(|export (async )?function (GET|POST|PUT|DELETE)\b|@app\.route|FastAPI\()", src[p])]
    # mobile + accessibility basics (every profile)
    if entry and entry.endswith(".html"):
        out.append(_check("viewport", "the entry page sets a mobile viewport", "ok" if re.search(r'name=["\']?viewport', etext, re.I) else "failed"))
        out.append(_check("lang", "the entry page declares its language (<html lang>)", "ok" if re.search(r"<html\b[^>]*\blang=", etext, re.I) else "failed"))
        out.append(_check("title", "the entry page has a title", "ok" if re.search(r"<title>\s*[^<\s]", etext, re.I) else "failed"))
    elif entry: out.append(_check("viewport", "mobile viewport and <html lang> (framework layout)", "review", f"set in {os.path.relpath(entry, project)}"))
    else: out.append(_check("entry", "an entry page exists", "failed", "no index.html or framework layout found"))
    # secrets (every profile)
    leaks = []
    for p, t in src.items():
        for m in SECRET.finditer(t): leaks.append(f"{os.path.relpath(p, project)}: {m.group(0)[:12]}…")
    for envf in (".env", ".env.local", ".env.production"):
        ep = os.path.join(project, envf)
        if os.path.isfile(ep) and re.search(r"^[A-Z_]+=\S{8,}", _read(ep), re.M):
            ign = _read(os.path.join(project, ".gitignore"))
            if not re.search(r"^\.env", ign, re.M): leaks.append(f"{envf} holds values and is not git-ignored")
    out.append(_check("secrets", "no secrets in the source or committed env files", "failed" if leaks else "ok", leaks[:6] or None))
    # transport: no insecure http:// subresources
    insecure = sorted({m for t in src.values() for m in re.findall(r"""(?:src|href)\s*=\s*["'](http://(?!localhost|127\.0\.0\.1)[^"']+)""", t)})
    out.append(_check("https", "every script, style and image loads over HTTPS", "failed" if insecure else "ok", insecure[:5] or None))
    # reproducibility: dependencies pinned
    if deps:
        lock = any(os.path.isfile(os.path.join(project, f)) for f in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock"))
        out.append(_check("lockfile", "dependencies are pinned by a lockfile (reproducible builds)", "ok" if lock else "failed",
                          None if lock else "run the package manager once and commit its lockfile", ["public", "sensitive"]))
        loose = [k for k, v in deps.items() if str(v).strip() in ("*", "latest", "")]
        out.append(_check("dep_ranges", "no dependency is '*' or 'latest'", "failed" if loose else "ok", loose[:6] or None))
    else: out.append(_check("lockfile", "dependencies pinned", "n/a", "no package dependencies"))
    # error handling: a failure must show a message, not a blank screen
    js = "\n".join(t for p, t in src.items() if p.endswith((".js", ".mjs", ".ts", ".tsx", ".jsx", ".html", ".vue", ".svelte")))
    has_handler = bool(re.search(r"addEventListener\(\s*['\"](error|unhandledrejection)|window\.onerror|ErrorBoundary|componentDidCatch|onErrorCaptured|error\.(tsx|jsx|js)", js))
    out.append(_check("error_handling", "a global error handler or error boundary shows failures to the person", "ok" if has_handler else "review",
                      None if has_handler else "add window.addEventListener('error'/'unhandledrejection') or an error boundary with a friendly message",
                      ["public", "sensitive"]))
    # storage of secrets in the browser
    ls = sorted({os.path.relpath(p, project) for p, t in src.items() if re.search(r"localStorage\.setItem\(\s*[\"'`][^\"'`]*(token|password|secret|session|jwt|ssn|card)", t, re.I)})
    out.append(_check("browser_storage", "no tokens, passwords or personal data in localStorage", "failed" if ls else "ok", ls[:5] or None, ["sensitive"]))
    # server-side (only when the project has server code)
    if server:
        stext = "\n".join(src[p] for p in server)
        cors = re.search(r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*|\bcors\(\s*\)|cors['\"]\)\(\s*\)|origin\s*:\s*['\"]\*['\"]", stext)
        out.append(_check("cors", "the API does not allow every origin", "failed" if cors else "ok", cors.group(0) if cors else None, ["public", "sensitive"]))
        val = re.search(r"\b(zod|yup|joi|ajv|valibot|pydantic|express-validator|safeParse|validate\()", stext + json.dumps(deps))
        out.append(_check("input_validation", "server inputs are validated", "ok" if val else "review", None if val else "no validation library or validate() call in server code", ["public", "sensitive"]))
        auth = re.search(r"\b(auth|session|jwt|getServerSession|clerk|supabase\.auth|passport|bearer)\b", stext, re.I)
        out.append(_check("authorization", "server routes check who is calling", "ok" if auth else "review", None if auth else "no authentication in server code", ["sensitive"]))
        rl = re.search(r"rate.?limit|ratelimit|@upstash/ratelimit|express-rate-limit|slowapi|throttle", stext + json.dumps(deps), re.I)
        out.append(_check("rate_limit", "sign-in and write routes are rate limited", "ok" if rl else "review", None if rl else "no rate limiting found", ["sensitive"]))
        sql = sorted({os.path.relpath(p, project) for p in server if re.search(r"(query|execute|raw)\(\s*`[^`]*\b(SELECT|INSERT|UPDATE|DELETE)\b[^`]*\$\{", src[p], re.I)})
        out.append(_check("sql_injection", "no SQL built by string interpolation", "failed" if sql else "ok", sql[:5] or None))
        idx = None
        for f in _files(project, (".sql", ".prisma", ".ts", ".js")):
            t = _read(f)
            if re.search(r"CREATE TABLE|model \w+ \{|pgTable\(", t): idx = idx or bool(re.search(r"CREATE (UNIQUE )?INDEX|@@index|@unique|\.index\(|index\(", t))
        if idx is not None: out.append(_check("indexes", "database tables declare indexes for their lookups", "ok" if idx else "review",
                                              None if idx else "tables defined without any index: add indexes for the columns queries filter or join on", ["public", "sensitive"]))
    else:
        out.append(_check("server", "server-side checks (auth, validation, rate limits, CORS, SQL)", "n/a", "no server code: a static client app"))
    req = [c for c in out if profile in c["required_for"]]
    failed = [c for c in req if c["status"] == "failed"]
    review = [c for c in req if c["status"] == "review"]
    for c in out: c["ok"] = not (c["status"] == "failed" and profile in c["required_for"])
    return {"status": "failed" if failed else "ok", "profile": profile, "checks": out, "review": [f"{c['name']}: {c['detail']}" for c in review],
            "outputs": [], "summary": {"measured": len([c for c in out if c["status"] in ("ok", "failed")]), "failed": len(failed), "review": len(review),
                                       "not_applicable": len([c for c in out if c["status"] == "n/a"])}}
