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
  advisory      measured and non-blocking: a configuration-metadata mismatch (analytics found but not declared, a
                Pulse tag without data-app) or a deliberate design read in context (an intentionally public,
                read-only endpoint with wildcard CORS). Shown in every report; never fails the gate
  accepted      an advisory/review item a person accepted in the project's .gitcraft/accepted.json with the same
                evidence fingerprint; it is not raised again until the evidence changes. A failed check (a secret,
                SQL interpolation, credentials or writes open to every origin, leaked environment) can never be
                accepted
  n/a           does not apply to this project

attribution(project) measures the HaveAnApp byline (kit/haveanapp): visible text marked data-haveanapp, linked
only to the verified official URL. docs/app-standards.md is the human-readable version of this file."""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(HERE, "kit", "haveanapp")
SKIP = {".git", "node_modules", "dist", "build", ".next", "out", "__pycache__", ".venv", "venv", "gitcraft-out", ".cache", "coverage"}
# code shipped with a project that is not its product (kept in step with production/maturity.py)
NOT_OWN = re.compile(r"(^|/)(starters?|templates?|fixtures?|__fixtures__|examples?|boilerplates?|scaffolds?|tests?|__tests__|spec|vendor|third_party|acceptance)/")
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


PULSE_SRC = "https://haveanapp-pulse-collect.vercel.app/p.js"   # HaveAnApp Pulse, as HangarBook ships it (index.html)


# analytics Discovery recognises (repository discovery and the engineering standard read the same list)
ANALYTICS = {
    "pulse": ("HaveAnApp Pulse", r"haveanapp-pulse"),
    "vercel": ("Vercel Web Analytics", r"@vercel/analytics|/_vercel/insights/script\.js|@vercel/speed-insights"),
    "google": ("Google Analytics", r"googletagmanager\.com/gtag|google-analytics\.com/analytics|\bgtag\(\s*['\"]config"),
    "plausible": ("Plausible", r"plausible\.io/js"),
    "posthog": ("PostHog", r"posthog-js|posthog\.init\("),
    "umami": ("Umami", r"umami\.(?:is|js)|data-website-id"),
    "fathom": ("Fathom", r"cdn\.usefathom\.com"),
    "cloudflare": ("Cloudflare Web Analytics", r"static\.cloudflareinsights\.com"),
    "segment": ("Segment", r"cdn\.segment\.com|@segment/analytics"),
}


def discover_analytics(project, src=None, deps=None):
    """[{provider, name, where}] for every analytics integration already in the project (read-only)."""
    if src is None: src = {p: _read(p) for p in _files(project)}
    if deps is None:
        try:
            pj = json.load(open(os.path.join(project, "package.json"))); deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
        except (OSError, ValueError): deps = {}
    out = []
    for pid, (name, rx) in ANALYTICS.items():
        where = sorted({os.path.relpath(p, project) for p, t in src.items() if re.search(rx, t)})
        if any(re.search(rx, d) for d in deps): where.append("package.json")
        if where: out.append({"provider": pid, "name": name, "where": where[:5]})
    return out


def _fingerprint(cid, detail, project=None, files=()):
    """The evidence a finding rests on: its detail plus the content of the files it read. An acceptance holds only
    while this is unchanged."""
    import hashlib
    h = hashlib.sha256((cid + "\n" + json.dumps(detail, sort_keys=True, default=str)).encode())
    for f in files or ():
        h.update(b"\0" + f.encode() + b"\0" + _read(os.path.join(project, f), 2_000_000).encode(errors="ignore"))
    return h.hexdigest()[:12]


def accepted_decisions(project):
    """The person's accepted architectural decisions, committed in the project: .gitcraft/accepted.json
    [{check, fingerprint, reason, by?, at?}] (read-only; GITCRAFT never writes it)."""
    for rel in (".gitcraft/accepted.json", "gitcraft.accepted.json"):
        try:
            with open(os.path.join(project, rel)) as f: d = json.load(f)
            items = d.get("accepted", d) if isinstance(d, dict) else d
            return [dict(x, _file=rel) for x in items if isinstance(x, dict) and x.get("check") and str(x.get("reason") or "").strip()]
        except (OSError, ValueError, AttributeError): continue
    return []


def pulse_snippet(title):
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-") or "app"
    return f'<script defer src="{PULSE_SRC}" data-app="{slug}"></script>'


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
            okl = any(h.strip().rstrip("/") == cfg["url"].rstrip("/") or "COMPANY_URL" in h for h in hrefs)
            checks.append({"name": f"the byline links to the official HaveAnApp site ({cfg['url']})", "ok": okl, "detail": hrefs or "no link"})
        else:
            checks.append({"name": "the byline links nowhere unverified (no official HaveAnApp URL is verified yet)", "ok": not [h for h in hrefs if "haveanapp" in h.lower()],
                           "detail": hrefs or None})
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks, "found": [{k: v for k, v in f.items() if k != "raw"} for f in found[:5]], "outputs": []}


# ---------------------------------------------------------------- the engineering checks
SECRET = re.compile(r"(AKIA[0-9A-Z]{16}|sk_live_[0-9a-zA-Z]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|ghp_[0-9A-Za-z]{36}|"
                    r"xox[baprs]-[0-9A-Za-z-]{10,}|AIza[0-9A-Za-z_\-]{35}|eyJhbGciOi[0-9A-Za-z_\-]{20,}\.[0-9A-Za-z_\-]{20,}|"
                    r"(?:api[_-]?key|secret|password|token)\s*[:=]\s*[\"'][A-Za-z0-9_\-+/]{24,}[\"'])", re.I)


def _built_output(project):
    """The folder a deployment config builds the site into, when the entry page is not in the source."""
    try:
        v = json.load(open(os.path.join(project, "vercel.json")))
        if v.get("outputDirectory") and v.get("buildCommand"): return v["outputDirectory"]
    except (OSError, ValueError): pass
    m = re.search(r'^\s*publish\s*=\s*"([^"]+)"', _read(os.path.join(project, "netlify.toml")), re.M)
    return m.group(1) if m else None


def _check(cid, title, status, detail=None, profiles=PROFILES, files=None):
    c = {"id": cid, "name": title, "status": status, "ok": status != "failed", "detail": detail, "required_for": profiles}
    if files: c["evidence_files"] = list(files)[:20]   # what the check read: part of its evidence fingerprint
    return c


WRITE_ROUTE = re.compile(r"\b(?:app|router|server|fastify|api)\.(?:post|put|patch|delete|all)\s*\(|export\s+(?:async\s+)?function\s+(?:POST|PUT|PATCH|DELETE)\b|"
                         r"export\s+const\s+(?:POST|PUT|PATCH|DELETE)\b|method\s*[!=]==?\s*['\"](?:POST|PUT|PATCH|DELETE)|@app\.(?:post|put|patch|delete)\b|"
                         r"\breq(?:uest)?\.body\b|request\.json\(\)|Allow-Methods['\"]?\s*[,:]\s*['\"][^'\"]*(?:POST|PUT|PATCH|DELETE)|\b(?:INSERT|UPDATE|DELETE)\s+(?:INTO|FROM|\w+\s+SET)\b")
CREDENTIALS = re.compile(r"Allow-Credentials['\"]?\s*[,:]\s*['\"]?true|credentials\s*:\s*true|\bset-cookie\b|req\.cookies|cookies\(\)|req\.session|getServerSession|"
                         r"headers\.(?:get\(\s*)?['\"]?authorization", re.I)
ENV_LEAK = re.compile(r"(?:\.json|\.send|Response\.json|JSON\.stringify)\(\s*(?:\{\s*\.\.\.)?process\.env\b(?!\.)|jsonify\(\s*(?:dict\()?os\.environ\b")


def _cors_in_context(project, server, src, cors):
    """Wildcard CORS read with what the routes do → (status, detail). Only GET/HEAD/OPTIONS handlers without
    credentials are an intentionally public, read-only API (advisory, with what still matters: abuse exposure,
    caching); writes or credentials open to every origin are a vulnerability (failed)."""
    if not cors: return "ok", None
    wild = [p for p in server if re.search(r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*|\bcors\(\s*\)|cors['\"]\)\(\s*\)|origin\s*:\s*['\"]\*['\"]", src[p])] or server
    writes = sorted({os.path.relpath(p, project) for p in wild if WRITE_ROUTE.search(src[p])})
    creds = sorted({os.path.relpath(p, project) for p in wild if CREDENTIALS.search(src[p])})
    if writes or creds:
        return "failed", (f"every origin may call write routes ({', '.join(writes[:3])})" if writes else "") + ("; " if writes and creds else "") + \
            (f"every origin may call routes that use credentials/cookies ({', '.join(creds[:3])})" if creds else "")
    ro = sorted(os.path.relpath(p, project) for p in wild)
    upstream = [os.path.relpath(p, project) for p in wild if re.search(r"\bfetch\(|axios|got\(|requests\.get", src[p])]
    guarded = [os.path.relpath(p, project) for p in wild if re.search(r"Cache-Control|s-maxage|revalidate|rate.?limit|ratelimit|throttle", src[p], re.I)]
    exposed = [u for u in upstream if u not in guarded]
    return "advisory", ("intentionally public, read-only endpoint(s) " + ", ".join(ro[:4]) + ": GET-only, no credentials, so wildcard CORS exposes nothing "
                        "a browser could not already read" + (f"; abuse exposure: {', '.join(exposed[:3])} proxies an upstream service without caching or a rate limit "
                        "(add Cache-Control s-maxage or a rate limit)" if exposed else ""))


def check(project, profile="personal", deliverable="app", analytics=None, backend=None, analytics_decided=True, accepted=None):
    """→ {status, checks, review, advisories, profile}. A failed check required by the profile fails the gate; `review`
    items never pass silently; `advisory` items are reported and never fail. analytics_decided=False when nobody chose
    analytics for this project (an existing project, a review): analytics already in it are recognised, not failed.
    accepted: extra accepted decisions (beside the project's .gitcraft/accepted.json)."""
    out = []; allfiles = list(_files(project)); every = {p: _read(p) for p in allfiles}
    # the product's own code: tests, fixtures, starters, examples and vendored code hold deliberate samples (a fake key, a
    # wildcard CORS route under test) that are not the product's behaviour. Secrets are still looked for everywhere.
    codefiles = [p for p in allfiles if not NOT_OWN.search(os.path.relpath(p, project))]; src = {p: every[p] for p in codefiles}
    entry = _entry(project); etext = _read(entry) if entry else ""
    pkg = os.path.join(project, "package.json"); pj = {}
    if os.path.isfile(pkg):
        try: pj = json.load(open(pkg))
        except ValueError: out.append(_check("package_json", "package.json parses", "failed", "package.json is not valid JSON"))
    deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
    server = [p for p in codefiles if re.search(r"(^|/)(api|server|functions|routes)/", os.path.relpath(p, project)) or
              re.search(r"\b(express\(|createServer\(|fastify\(|Hono\(|export (async )?function (GET|POST|PUT|DELETE)\b|@app\.route|FastAPI\()", src[p])]
    tool = deliverable == "tool"   # a CLI, library or toolchain: no page, so the browser checks do not apply
    # mobile + accessibility basics (every profile)
    if tool: out.append(_check("entry", "an entry page exists", "n/a", "a tool (CLI, library, toolchain): no page to open"))
    elif entry and entry.endswith(".html"):
        out.append(_check("viewport", "the entry page sets a mobile viewport", "ok" if re.search(r'name=["\']?viewport', etext, re.I) else "failed"))
        out.append(_check("lang", "the entry page declares its language (<html lang>)", "ok" if re.search(r"<html\b[^>]*\blang=", etext, re.I) else "failed"))
        out.append(_check("title", "the entry page has a title", "ok" if re.search(r"<title>\s*[^<\s]", etext, re.I) else "failed"))
    elif entry: out.append(_check("viewport", "mobile viewport and <html lang> (framework layout)", "review", f"set in {os.path.relpath(entry, project)}"))
    elif _built_output(project):   # the deployed entry page is generated by the build (e.g. vercel.json outputDirectory): checked on the built site
        out.append(_check("entry", "an entry page exists", "review", f"generated at build time into {_built_output(project)}; measure the built site"))
    else: out.append(_check("entry", "an entry page exists", "failed", "no index.html or framework layout found"))
    # secrets (every profile)
    leaks, samples = [], []
    for p, t in every.items():
        for m in SECRET.finditer(t): (leaks if p in src else samples).append(f"{os.path.relpath(p, project)}: {m.group(0)[:12]}…")
    for envf in (".env", ".env.local", ".env.production"):
        ep = os.path.join(project, envf)
        if os.path.isfile(ep) and re.search(r"^[A-Z_]+=\S{8,}", _read(ep), re.M):
            ign = _read(os.path.join(project, ".gitignore"))
            if not re.search(r"^\.env", ign, re.M): leaks.append(f"{envf} holds values and is not git-ignored")
    out.append(_check("secrets", "no secrets in the source or committed env files", "failed" if leaks else "review" if samples else "ok",
                      leaks[:6] or ([f"in test or sample code, confirm each is a fake: {x}" for x in samples[:6]] if samples else None)))
    # transport: no insecure http:// subresources
    insecure = sorted({m for t in src.values() for m in re.findall(r"""(?:src|href)\s*=\s*["'](http://(?!localhost|127\.0\.0\.1|[\w.-]+\.local[/:])[^"']+)""", t)})
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
    if tool: out.append(_check("error_handling", "a global error handler or error boundary shows failures to the person", "n/a", "a tool reports failures on its own output and exit status"))
    else: out.append(_check("error_handling", "a global error handler or error boundary shows failures to the person", "ok" if has_handler else "review",
                      None if has_handler else "add window.addEventListener('error'/'unhandledrejection') or an error boundary with a friendly message",
                      ["public", "sensitive"]))
    # storage of secrets in the browser
    ls = sorted({os.path.relpath(p, project) for p, t in src.items() if re.search(r"localStorage\.setItem\(\s*[\"'`][^\"'`]*(token|password|secret|session|jwt|ssn|card)", t, re.I)})
    out.append(_check("browser_storage", "no tokens, passwords or personal data in localStorage", "n/a" if tool and not ls else "failed" if ls else "ok",
                      "a tool has no browser storage" if tool and not ls else ls[:5] or None, ["sensitive"]))
    # server-side (only when the project has server code)
    if server:
        stext = "\n".join(src[p] for p in server)
        cors = re.search(r"Access-Control-Allow-Origin['\"]?\s*[,:]\s*['\"]\*|\bcors\(\s*\)|cors['\"]\)\(\s*\)|origin\s*:\s*['\"]\*['\"]", stext)
        leak = sorted({os.path.relpath(p, project) for p in server if ENV_LEAK.search(src[p])})
        out.append(_check("env_leak", "server routes never return the process environment (secrets)", "failed" if leak else "ok", leak[:4] or None))
        cst, cdetail = _cors_in_context(project, server, src, cors)
        out.append(_check("cors", "the API does not allow every origin" + (" to write or use credentials" if cst == "advisory" else ""), cst,
                          f"{cors.group(0)}: {cdetail}" if cst == "failed" else cdetail, ["public", "sensitive"], files=[os.path.relpath(p, project) for p in server]))
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
            if NOT_OWN.search(os.path.relpath(f, project)): continue
            t = _read(f)
            if re.search(r"CREATE TABLE|model \w+ \{|pgTable\(", t): idx = idx or bool(re.search(r"CREATE (UNIQUE )?INDEX|@@index|@unique|\.index\(|index\(", t))
        if idx is not None: out.append(_check("indexes", "database tables declare indexes for their lookups", "ok" if idx else "review",
                                              None if idx else "tables defined without any index: add indexes for the columns queries filter or join on", ["public", "sensitive"]))
    else:
        out.append(_check("server", "server-side checks (auth, validation, rate limits, CORS, SQL)", "n/a", "no web server routes" if tool else "no server code: a static client app"))
    found = [] if tool and analytics is None else discover_analytics(project, src, deps)   # a tool ships no page to measure: its code names analytics, it does not run them
    if analytics == "pulse":   # chosen in the Decision Room (or found by Discovery): the counter is on the entry page, deferred, with this app's name
        m = re.search(r"""<script\b[^>]*src=["']""" + re.escape(PULSE_SRC) + r"""["'][^>]*>""", etext)
        if not m:
            out.append(_check("analytics", "HaveAnApp Pulse is on the entry page (deferred, with data-app)", "failed", "add " + pulse_snippet(os.path.basename(project.rstrip("/")))))
        else:   # the integration is there; a missing attribute is configuration metadata, not a broken integration
            miss = [a for a in ("defer", "data-app=") if a not in m.group(0)]
            out.append(_check("analytics", "HaveAnApp Pulse is on the entry page (deferred, with data-app)", "advisory" if miss else "ok",
                              f"the Pulse tag lacks {' and '.join(x.rstrip('=') for x in miss)}: " + pulse_snippet(os.path.basename(project.rstrip("/"))) if miss else None))
    elif analytics is None and analytics_decided and PULSE_SRC in etext:
        out.append(_check("analytics", "no analytics the blueprint did not approve", "failed", "HaveAnApp Pulse is on the page but the Decision Room chose no analytics"))
    elif analytics is None and found:   # nobody decided: recognise what the project already ships
        out.append(_check("analytics", "existing analytics are recognised and declared", "advisory",
                          "found " + "; ".join(f"{f['name']} ({', '.join(f['where'][:2])})" for f in found) +
                          ": not declared in the blueprint, recorded as discovered (declare it, or accept it in .gitcraft/accepted.json)",
                          files=sorted({w for f in found for w in f["where"]})))
    if backend == "postgres":
        has_mig = any(re.search(r"(^|/)(migrations?|db|schema|drizzle|prisma)(/|\.)", os.path.relpath(p, project)) for p in _files(project, (".sql", ".prisma", ".ts", ".js")))
        out.append(_check("migrations", "the database schema lives in the repository as migrations", "ok" if has_mig else "failed",
                          None if has_mig else "add the schema as migrations (e.g. migrations/001_init.sql) with its indexes"))
    # accepted architectural decisions: an advisory/review item with the same evidence is not raised again
    acc = accepted_decisions(project) + list(accepted or [])
    for c in out:
        c["fingerprint"] = _fingerprint(c["id"], c.get("detail"), project, c.get("evidence_files"))
        a = next((x for x in acc if x["check"] == c["id"]), None)
        if not a: continue
        if c["status"] == "failed":
            c["detail"] = f"{c['detail']} (an acceptance in {a.get('_file', 'the blueprint')} is ignored: a failed check is a blocker and cannot be accepted)"
        elif c["status"] in ("advisory", "review") and a.get("fingerprint") in (None, "", c["fingerprint"]):
            c.update(status="accepted", accepted={"reason": a["reason"], "by": a.get("by"), "at": a.get("at"), "file": a.get("_file")})
        elif c["status"] in ("advisory", "review"):
            c["detail"] = f"{c['detail']} — previously accepted ({a['reason']}), but the evidence changed since (fingerprint {c['fingerprint']}, accepted {a.get('fingerprint')})"
    req = [c for c in out if profile in c["required_for"]]
    failed = [c for c in req if c["status"] == "failed"]
    review = [c for c in req if c["status"] == "review"]
    for c in out:
        c["ok"] = not (c["status"] == "failed" and profile in c["required_for"])
        if c["status"] in ("advisory", "accepted"): c["category"] = "advisory"
    advisories = [c for c in out if c["status"] == "advisory"]
    return {"status": "failed" if failed else "ok", "profile": profile, "checks": out, "review": [f"{c['name']}: {c['detail']}" for c in review],
            "advisories": [f"{c['name']}: {c['detail']}" for c in advisories], "analytics_found": found,
            "outputs": [], "summary": {"measured": len([c for c in out if c["status"] in ("ok", "failed", "advisory")]), "failed": len(failed), "review": len(review),
                                       "advisory": len(advisories), "accepted": len([c for c in out if c["status"] == "accepted"]),
                                       "not_applicable": len([c for c in out if c["status"] == "n/a"])}}
