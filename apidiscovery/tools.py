"""The API Discovery tools, as the MCP server (studio/server.py) and the command line (python3 -m apidiscovery) call them.

Every answer carries `catalogue` (where the data came from and how old it is) and keeps catalogue claims, checked facts
and unknowns apart. Read-only: nothing here fetches from the network, changes a project, signs up for anything or
handles a secret. Refreshing the catalogue is a separate, explicit command (refresh / check) run where there is network."""
from . import SOURCE, catalog, checks as CK, guide as G, intel, project, search as S

TOOLS = [
    ("api_discovery_search", "API DISCOVERY: find external APIs for a described need (\"a free weather API for a mobile hiking app\"), from the public-apis catalogue. "
     "Returns ranked candidates with why each matched, what the catalogue claims (auth, HTTPS, CORS: unverified), what was checked (the documentation link, with its date) and what is unknown "
     "(pricing, limits, reliability, licence: never guessed). Optional hard filters. Read-only; nothing is installed or called.",
     {"type": "object", "required": ["need"], "properties": {
         "need": {"type": "string", "description": "the feature or data you need, in words"}, "category": {"type": "string", "description": "a catalogue category, e.g. Weather (api_discovery_status lists them)"},
         "auth": {"type": "string", "enum": ["none", "apiKey", "oauth"], "description": "only APIs with this authentication"}, "https": {"type": "boolean", "description": "only APIs listed with HTTPS"},
         "cors": {"type": "boolean", "description": "only APIs listed with CORS support"}, "docs": {"type": "boolean", "description": "only APIs whose documentation link answered the last check"},
         "limit": {"type": "integer", "description": "how many to return (default 8, at most 25)"}}}),
    ("api_discovery_compare", "API DISCOVERY: compare 2 to 4 candidate APIs (ids or names from api_discovery_search) on eight criteria: feature fit, documentation, authentication, pricing, "
     "reliability, integration effort, security, licence. No scores: each cell is a statement with its basis (catalogue / checked / heuristic / unknown), plus the trade-offs between them. "
     "Pass one API to get its assessment and the alternatives to it.",
     {"type": "object", "required": ["apis"], "properties": {"apis": {"type": "array", "items": {"type": "string"}, "description": "API ids or names"}, "need": {"type": "string", "description": "the need they are being compared for (optional)"}}}),
    ("api_discovery_guide", "API DISCOVERY: integration guidance for one API in the project's language: documentation, authentication, environment variables, where the call must run "
     "(a key never reaches browser or app code), rate limits, error handling, caching, security, and an example request. Endpoints and limits are not in the catalogue and are never invented. "
     "Give `project` to use its language and platform. It registers nothing, buys nothing and reads no secrets.",
     {"type": "object", "required": ["api"], "properties": {"api": {"type": "string", "description": "API id or name"}, "language": {"type": "string", "enum": list(G.LANGS)},
                                                           "platform": {"type": "string", "enum": ["server", "browser", "mobile"]}, "project": {"type": "string", "description": "a project folder to take the language and platform from"}}}),
    ("api_discovery_recommend", "API DISCOVERY for a project: reads the project read-only (manifest, README, source hostnames; never environment or secret files) and recommends APIs for what it "
     "seems to need, plus alternatives to catalogue APIs it already appears to call. Advice only: no dependency is added, no service is introduced, no file is written.",
     {"type": "object", "required": ["project"], "properties": {"project": {"type": "string", "description": "the project folder"}, "need": {"type": "string", "description": "a specific need to recommend for (optional)"}}}),
    ("api_discovery_status", "API DISCOVERY status: the catalogue's source, licence, size, categories and age, when its links were last checked, and how to refresh it.",
     {"type": "object", "properties": {}}),
]


def freshness(C, K):
    return {"source": SOURCE["url"], "license": SOURCE["license"], "fetched": C.get("fetched"), "apis": len(C["entries"]), "links_checked": K.get("checked"),
            "problem": C.get("problem"),
            "read": "auth, HTTPS and CORS are the catalogue's claims (unverified); `check` is this tool's own link check with its date; pricing, limits, reliability and licence terms are unknown"}


def find(C, ref):
    """An entry by id, exact name, or unique name fragment. → (entry, None) or (None, why)."""
    r = str(ref or "").strip().lower()
    if not r: return None, "no API named"
    for key in ("id", "name"):
        hit = [e for e in C["entries"] if e[key].lower() == r]
        if hit: return hit[0], None
    part = [e for e in C["entries"] if r in e["name"].lower()]
    if len(part) == 1: return part[0], None
    if part: return None, f"\"{ref}\" matches several APIs: " + ", ".join(f"{e['name']} ({e['id']})" for e in part[:8])
    return None, f"no API called \"{ref}\" in the catalogue (api_discovery_search finds candidates)"


def _card(r):
    e, ck = r["entry"], r.get("check")
    return {"id": e["id"], "name": e["name"], "description": e["description"], "category": e["category"], "documentation": e["url"],
            "catalogue": {"auth": intel.AUTH_LABEL[e["auth"]], "https": e["https"], "cors": e["cors"], "sponsored_listing": bool(e.get("sponsored")), "status": "unverified: as listed by public-apis"},
            "checked": ({"documentation_link": ck["status"], "meaning": CK.STATUS[ck["status"]], "on": ck.get("checked")} if ck else {"documentation_link": "not checked"}),
            "why": [f"{w['term']} → {w['in']}" + (f" (as {w['via']})" if w.get("via") and w["via"] != w["term"] else "") + (" [use-case suggestion]" if w.get("suggested") else "") for w in r.get("why") or []],
            **intel.summary(e, ck), "unknown": ["pricing and free tier", "rate limits", "reliability and maintenance", "licence and commercial use"]}


def call(name, a, C=None, K=None):
    a = dict(a or {})
    C = C or catalog.load(); K = K or CK.load()
    fresh = freshness(C, K)
    if not C["entries"] and name != "api_discovery_status":
        return {"status": "unavailable", "why": C.get("problem") or "the catalogue is empty", "fix": "python3 -m apidiscovery refresh (needs network)", "catalogue": fresh}
    if name == "api_discovery_status":
        return {"status": "ok" if C["entries"] else "unavailable", "catalogue": fresh, "counts": C.get("counts"), "categories": C.get("categories"), "link_checks": {k: K.get(k) for k in ("checked", "counts", "of", "means")},
                "attribution": SOURCE["note"], "refresh": "python3 -m apidiscovery refresh (catalogue) / check (links); the scheduled workflow api-catalog.yml does both and publishes the result for the /apis/ page",
                "not_a_department": "API Discovery scores nothing and is not part of any GITCRAFT report, verdict or evaluation."}
    if name == "api_discovery_search":
        f = {k: a.get(k) for k in ("category", "auth", "https", "cors", "docs") if a.get(k)}
        if f.get("category"):
            m = [c for c in C.get("categories") or [] if c.lower() == str(f["category"]).lower()] or [c for c in C.get("categories") or [] if str(f["category"]).lower() in c.lower()]
            if not m: return {"status": "no_such_category", "categories": C.get("categories"), "catalogue": fresh}
            f["category"] = m[0]
        R = S.search(C["entries"], a.get("need") or "", f, K, max(1, min(int(a.get("limit") or 8), 25)))
        return {"status": "ok" if R["results"] else "no_match", "understood": R["understood"], "filters": f, "total_matches": R["total"], "notes": R["notes"],
                "results": [_card(r) for r in R["results"]], "also_consider": [{"need": g["need"], "results": [_card(r) for r in g["results"]]} for g in R.get("related") or []],
                "ranking": "ordered by how well the catalogue text matches the need, then by the constraints in the sentence; an order, not a quality score",
                "next": "api_discovery_compare {apis: [...]} to weigh candidates, api_discovery_guide {api} to integrate one", "catalogue": fresh}
    if name == "api_discovery_compare":
        es, missing = [], []
        for ref in (a.get("apis") or [])[:4]:
            e, why = find(C, ref)
            (es.append(e) if e else missing.append(why))
        if not es: return {"status": "not_found", "why": missing, "catalogue": fresh}
        whys = {}
        if a.get("need"):
            U = S.understand(a["need"])
            whys = {e["id"]: S.match(e, U)[2] for e in es}
        cmp_ = intel.compare(es, K, whys)
        out = {"status": "ok", "method": cmp_["method"], "basis": cmp_["basis"], "tradeoffs": cmp_["tradeoffs"], "not_found": missing,
               "apis": [{"id": c["entry"]["id"], "name": c["entry"]["name"], "documentation": c["entry"]["url"], **c["summary"],
                         "criteria": [{"criterion": x["title"], "finding": x["finding"], "basis": x["basis"]} for x in c["criteria"]]} for c in cmp_["columns"]], "catalogue": fresh}
        if len(es) == 1:
            out["alternatives"] = [_card(r) for r in S.alternatives(C["entries"], es[0], K, 5)["results"]]
        return out
    if name == "api_discovery_guide":
        e, why = find(C, a.get("api"))
        if not e: return {"status": "not_found", "why": why, "catalogue": fresh}
        lang, plat, ctx = a.get("language"), a.get("platform"), None
        if a.get("project"):
            ctx = project.context(a["project"]); lang = lang or ctx["language"]; plat = plat or ctx["platform"]
        g = G.guide(e, lang or "javascript", plat or "server", CK.for_entry(K, e))
        return {"status": "ok", "guide": g, "markdown": G.text(g), "project": {k: ctx[k] for k in ("name", "language", "platform", "evidence")} if ctx else None,
                "did_not": "create an account, choose a plan, call the API, read or send any secret, or change the project", "catalogue": fresh}
    if name == "api_discovery_recommend":
        R = project.recommend(a["project"], C["entries"], K, a.get("need"))
        return {"status": "ok" if R["needs"] or R["already_using"] else "no_needs_found", "project": R["project"], "note": R["note"], "changed": R["changed"],
                "recommendations": [{"need": g["need"], "matches": g["total"], "notes": g["notes"], "results": [_card(r) for r in g["results"]]} for g in R["needs"]],
                "already_using": [{"api": u["using"]["entry"]["name"], "seen": f"{u['using']['host']} in {u['using']['file']}", "lead": "shares a domain with this API's documentation; not proof the project calls it",
                                   "alternatives": [_card(r) for r in u["alternatives"]]} for u in R["already_using"]],
                "example_language": R["example_language"], "example_platform": R["example_platform"], "catalogue": fresh}
    raise KeyError(name)
