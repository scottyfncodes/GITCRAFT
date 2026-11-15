"""Read-only project context for API Discovery: the language and platform to write examples for, what the project
seems to need, and which catalogue APIs it already calls.

It reads the manifest files, the README and a bounded sample of source files. It never reads environment files or
anything that looks like a secret store, never writes into the project, never adds a dependency and never calls any
API. Discovery of the project's kind is the Production Director's (production/maturity.py), reused when available."""
import json, os, re
from . import lexicon as L
from .search import tokens, stem

SKIP_DIRS = {".git", "node_modules", "dist", "build", "out", ".next", ".venv", "venv", "__pycache__", "vendor", "target", ".vercel", "coverage"}
SOURCE_EXT = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".py", ".html", ".vue", ".svelte", ".go", ".rb", ".php", ".swift", ".kt", ".dart")
SECRET_FILE = re.compile(r"(^\.env)|(\.pem$)|(\.key$)|(secret)|(credential)", re.I)
MOBILE = ("react-native", "expo", "@capacitor/core", "@ionic/react", "nativescript")
SERVER = ("next", "express", "fastify", "koa", "hono", "@nestjs/core", "nuxt", "@sveltejs/kit", "remix", "astro")
MAX_FILES, MAX_BYTES = 400, 200_000


def _read(p, n=MAX_BYTES):
    try:
        with open(p, "r", errors="replace") as f: return f.read(n)
    except OSError: return ""


def _json(p):
    try: return json.load(open(p))
    except (OSError, ValueError): return {}


def context(path):
    """→ {path, name, language, platform, frameworks, kind, needs, use_cases, hosts, evidence}. Every field says where
    it came from in `evidence`; a field that could not be read is None, never guessed."""
    root = os.path.realpath(path)
    if not os.path.isdir(root): raise ValueError(f"not a folder: {path}")
    ev, out = [], {"path": root, "name": os.path.basename(root), "language": None, "platform": None, "frameworks": [], "kind": None, "needs": [], "use_cases": [], "hosts": []}
    pk = _json(os.path.join(root, "package.json"))
    deps = {**(pk.get("dependencies") or {}), **(pk.get("devDependencies") or {})} if isinstance(pk, dict) else {}
    if pk:
        out["language"] = "javascript"; ev.append("language: package.json")
        if pk.get("name"): out["name"] = str(pk["name"])[:60]
        out["frameworks"] = sorted(d for d in deps if d in MOBILE + SERVER + ("react", "vue", "svelte", "three", "phaser", "vite"))
        if any(d in deps for d in MOBILE): out["platform"] = "mobile"; ev.append("platform: a mobile framework in package.json")
        elif any(d in deps for d in SERVER): out["platform"] = "server"; ev.append("platform: a server framework in package.json")
        else: out["platform"] = "browser"; ev.append("platform: a JavaScript project with no server framework (treated as browser code)")
    elif any(os.path.isfile(os.path.join(root, f)) for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile")):
        out["language"] = "python"; out["platform"] = "server"; ev.append("language: a Python manifest; platform: server")
    elif os.path.isfile(os.path.join(root, "index.html")):
        out["language"] = "javascript"; out["platform"] = "browser"; ev.append("language and platform: a static index.html")
    try:   # the Director's own reading of the project, when this runs beside it
        from production import maturity
        a = maturity.assess(root); out["kind"] = a.get("kind"); out["name"] = a.get("name") or out["name"]; ev.append(f"kind: Discovery ({a.get('kind_confidence') or a.get('confidence')} confidence)")
    except Exception:
        pass
    readme = next((os.path.join(root, f) for f in ("README.md", "README", "readme.md", "README.txt") if os.path.isfile(os.path.join(root, f))), None)
    text = (_read(readme, 6000) if readme else "") + " " + str(pk.get("description") or "") if isinstance(pk, dict) else ""
    seen = [stem(t) for t in tokens(text)]
    topics = {stem(k): k for k in L.SYNONYMS}
    counts = {}
    for t in seen:
        if t in topics: counts[topics[t]] = counts.get(topics[t], 0) + 1
    out["needs"] = [k for k, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) if n >= 2][:6]   # one passing mention ("press space") is not a need
    out["use_cases"] = [u for u in L.USE_CASES if stem(u) in seen][:3]
    if out["kind"] == "game" and "game" not in out["use_cases"]: out["use_cases"].append("game")
    if out["needs"] or out["use_cases"]: ev.append("needs: words in the README" + (" and package description" if pk else ""))
    hosts, n = {}, 0
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in SKIP_DIRS and not x.startswith(".")]
        for f in fs:
            if n >= MAX_FILES: break
            if not f.endswith(SOURCE_EXT) or SECRET_FILE.search(f): continue
            n += 1
            for h in re.findall(r"https?://([a-z0-9.-]+\.[a-z]{2,})", _read(os.path.join(d, f)), re.I):
                hosts.setdefault(h.lower(), os.path.relpath(os.path.join(d, f), root))
    out["hosts"] = [{"host": h, "file": f} for h, f in sorted(hosts.items())][:80]
    out["evidence"] = ev + [f"hosts: {n} source file(s) scanned (environment and secret files are never read)"]
    return out


def _reg(host):
    return ".".join(host.lower().split(":")[0].split(".")[-2:])


def in_use(ctx, entries):
    """Catalogue entries whose documentation site shares a domain with a host the project's source mentions. A shared
    domain is a lead, not proof that the project calls that API."""
    import urllib.parse
    shared = {"github.com", "github.io", "herokuapp.com", "netlify.app", "vercel.app", "rapidapi.com", "google.com", "googleapis.com", "readthedocs.io", "gitlab.com", "apilayer.com", "com.au", "co.uk"}
    by = {}
    for e in entries:
        r = _reg(urllib.parse.urlsplit(e["url"]).netloc)
        if r not in shared: by.setdefault(r, []).append(e)
    out = []
    for h in ctx["hosts"]:
        for e in by.get(_reg(h["host"]), [])[:2]:
            if e["id"] not in [x["entry"]["id"] for x in out]: out.append({"entry": {k: v for k, v in e.items() if k != "_ix"}, "host": h["host"], "file": h["file"]})
    return out[:10]


def recommend(path, entries, checks=None, need=None, limit=5):
    """What this project could use: per need, the best-matching candidates; and for each API it seems to use already,
    the alternatives. Advice only: nothing is installed, called or changed."""
    from . import search as S
    ctx = context(path)
    pref = {"browser": " in the browser", "mobile": " for a mobile app"}.get(ctx["platform"], "")
    needs = [need] if need else (ctx["needs"] or [L.USE_CASES[u]["terms"][0] for u in ctx["use_cases"]])
    groups = []
    for n in needs[:6]:
        R = S.search(entries, f"{n}{pref}", None, checks, limit, _related=bool(need))
        if R["results"]: groups.append({"need": n, "results": R["results"], "total": R["total"], "notes": R["notes"], "related": R.get("related") or []})
    used = in_use(ctx, entries)
    alts = [{"using": u, "alternatives": S.alternatives(entries, next(e for e in entries if e["id"] == u["entry"]["id"]), checks, 4)["results"]} for u in used[:4]]
    return {"project": ctx, "needs": groups, "already_using": alts, "example_language": ctx["language"] or "javascript", "example_platform": ctx["platform"] or "server",
            "changed": "nothing: no dependency was added, no API was called, no file was written",
            "note": None if groups or need else "No topical words were found in the project's README. Describe the need in words (api_discovery_search)."}
