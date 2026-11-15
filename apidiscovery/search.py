"""A described need → ranked catalogue entries, with the reasons.

The ranking is a transparent heuristic, not a quality score: it orders candidates by how well their catalogue text
matches the need, then by the stated constraints. Every result says why it matched, and the number used for ordering is
never shown as a rating. The /apis/ page implements the same rules (apidiscovery/web/app.js); tests/test_api_discovery.py
runs both on the same queries and requires the same order.

  topic words     name match 6, category 4, description 3; a synonym counts 0.6 of that; a use-case suggestion 0.5
  coverage first  an entry matching more of the need's words outranks one matching fewer, whatever the weights
  constraints     "free"/"no key" prefers no-auth entries, "browser" prefers CORS yes, "https"/"mobile" prefers HTTPS
  demotions       sponsored listings, and links a check found missing or unreachable, sort lower (never hidden)

Hard filters (category, auth, https, cors, docs) remove entries; a constraint read from the sentence only reorders them,
because "free" is not something the catalogue knows."""
import re, unicodedata
from . import lexicon as L

W_NAME, W_CAT, W_DESC, W_SYN, W_USE = 6.0, 4.0, 3.0, 0.6, 0.5


def tokens(text):
    t = unicodedata.normalize("NFKD", str(text or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", t)


def stem(w):
    if len(w) > 4 and w.endswith("ies"): return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"): return w[:-1]
    return w


def index(e):
    """The stemmed word sets of one entry (cached on the entry under _ix)."""
    ix = e.get("_ix")
    if ix is None:
        ix = e["_ix"] = {"n": {stem(t) for t in tokens(e["name"])}, "c": {stem(t) for t in tokens(e["category"] + " " + " ".join(e.get("also_in") or []))},
                         "d": {stem(t) for t in tokens(e.get("description"))}}
    return ix


def understand(query):
    """The need, read: topic terms (with their variants), use cases, and the constraints stated in the sentence."""
    q = " " + " ".join(tokens(query)) + " "
    prefer = set()
    for ph, p in L.PHRASES.items():
        k = " " + " ".join(tokens(ph)) + " "
        if k in q: prefer.add(p); q = q.replace(k, " ")
    terms, uses = [], []
    flat = {w: p for p, ws in L.PREFER.items() for w in ws}
    for t in q.split():
        if t in flat: prefer.add(flat[t]); continue
        if t in L.STOP or len(t) < 2: continue
        if t in L.USE_CASES and t not in uses: uses.append(t)
        if t not in [x["term"] for x in terms]:
            var = {stem(t): (1.0, None)}
            for s in L.SYNONYMS.get(t, []) + L.SYNONYMS.get(stem(t), []):
                for st in (stem(x) for x in tokens(s)):
                    var.setdefault(st, (W_SYN, s))
            terms.append({"term": t, "variants": var, "suggested": False})
    for u in uses:   # what such a project usually needs, at half weight and labelled as a suggestion
        for s in L.USE_CASES[u]["terms"]:
            if s not in [x["term"] for x in terms]:
                var = {}
                for w in [s] + L.SYNONYMS.get(s, []):
                    for st in (stem(x) for x in tokens(w)): var.setdefault(st, (W_USE, s))
                terms.append({"term": s, "variants": var, "suggested": True, "use_case": u})
    if "mobile" in prefer: prefer.add("https")   # iOS and Android block plain HTTP by default
    return {"terms": terms, "use_cases": uses, "prefer": sorted(prefer)}


def match(e, U):
    """(score, covered stated terms, why) for one entry against an understood need."""
    ix = index(e); score = 0.0; covered = 0; why = []
    for T in U["terms"]:
        best = None
        for v, (w, via) in T["variants"].items():
            for field, fw in (("n", W_NAME), ("c", W_CAT), ("d", W_DESC)):
                if v in ix[field] and (best is None or fw * w > best[0]): best = (fw * w, field, via)
        if best:
            score += best[0]
            if not T["suggested"]: covered += 1
            why.append({"term": T["term"], "in": {"n": "name", "c": "category", "d": "description"}[best[1]], "via": best[2], "suggested": T["suggested"]})
    cats = {c for u in U["use_cases"] for c in L.USE_CASES[u]["categories"]}
    if score and e["category"] in cats: score += 1.5
    return score, covered, why


def adjust(e, prefer, check=None):
    """The constraint and demotion part of the order, and the notes that explain it."""
    a = 0.0
    if "no_auth" in prefer and e["auth"] == "none": a += 2
    if "browser" in prefer: a += 2 if e["cors"] == "yes" else -1 if e["cors"] == "no" else 0
    if "https" in prefer: a += 1 if e["https"] == "yes" else -2 if e["https"] == "no" else 0
    if e.get("sponsored"): a -= 1
    st = (check or {}).get("status")
    if st in ("missing", "unreachable"): a -= 3
    elif st == "moved": a -= 1
    return a


def passes(e, f, check=None):
    f = f or {}
    if f.get("category") and f["category"] not in [e["category"]] + (e.get("also_in") or []): return False
    if f.get("auth") and e["auth"] != f["auth"]: return False
    if f.get("https") and e["https"] != "yes": return False
    if f.get("cors") and e["cors"] != "yes": return False
    if f.get("docs") and (check or {}).get("status") != "reachable": return False
    return True


def search(entries, query="", filters=None, checks=None, limit=12, _related=True):
    """→ {"understood", "results": [{entry, why, check}], "total", "notes"}"""
    from . import checks as CK
    U = understand(query); stated = [t for t in U["terms"] if not t["suggested"]]
    rows = []
    for e in entries:
        ck = CK.for_entry(checks, e) if checks else None
        if not passes(e, filters, ck): continue
        s, cov, why = match(e, U) if U["terms"] else (0.0, 0, [])
        if stated and not cov: continue          # a use-case suggestion alone never makes a result
        if U["terms"] and not stated and not s: continue
        rows.append((-cov, -(s + adjust(e, U["prefer"], ck)), e["name"].lower(), e, why, ck))
    rows.sort(key=lambda r: r[:3])
    notes = []
    if "no_auth" in U["prefer"]:
        notes.append("\"Free\" is not in the catalogue. APIs that need no key are listed first; whether any API is free, and within what limits, is on its own pricing page.")
    if "browser" in U["prefer"]: notes.append("APIs the catalogue lists with CORS support come first. That column is the catalogue's claim, not a test.")
    if "mobile" in U["prefer"]: notes.append("HTTPS APIs come first: iOS and Android block plain HTTP by default. An API key must not ship inside a mobile app: call the API from your server.")
    for u in U["use_cases"]: notes.append(f"Read as {L.USE_CASES[u]['label']}: also looked for " + ", ".join(L.USE_CASES[u]["terms"]) + ".")
    if stated and not rows: notes.append("Nothing in the catalogue matches those words. Try the thing itself (\"weather\", \"flights\", \"currency\") or pick a category.")
    related = []
    for t in [t["term"] for t in U["terms"] if t["suggested"]] if _related else []:   # what the use case usually needs besides what was asked
        sub = search(entries, t + (" free" if "no_auth" in U["prefer"] else ""), filters, checks, 3, _related=False)
        got = {r["entry"]["id"] for r in rows[:limit] for r in [{"entry": r[3]}]}
        hits = [r for r in sub["results"] if r["entry"]["id"] not in got]
        if hits: related.append({"need": t, "results": hits})
    return {"understood": {"terms": [t["term"] for t in stated], "suggested": [t["term"] for t in U["terms"] if t["suggested"]], "use_cases": U["use_cases"], "prefer": U["prefer"]},
            "results": [{"entry": {k: v for k, v in r[3].items() if k != "_ix"}, "why": r[4], "check": r[5]} for r in rows[:limit]], "total": len(rows), "notes": notes,
            "related": related}


def alternatives(entries, e, checks=None, limit=6):
    """Other entries that do the same job as `e`: same category, sharing its distinctive description words."""
    words = [t for t in tokens(e.get("description")) if t not in L.STOP and len(t) > 2][:8]
    R = search([x for x in entries if x["id"] != e["id"]], " ".join(words), {"category": e["category"]}, checks, limit)
    if not R["results"]: R = search([x for x in entries if x["id"] != e["id"]], "", {"category": e["category"]}, checks, limit)
    return R
