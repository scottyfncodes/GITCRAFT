"""What is known about a candidate API, criterion by criterion, each statement with its basis.

No scores. A number would have to be made from the three columns the catalogue has and a link check, and would read as
a measurement of quality that nobody made. Instead: eight criteria, one plain statement each, and for each the basis:

  catalogue   public-apis lists it so; nobody here verified it
  checked     this tool measured it, on the date shown (only the documentation link, see checks.py)
  heuristic   advice that follows from the catalogue fields, labelled as such
  unknown     not in the catalogue and not measurable from outside: pricing, limits, licence terms, reliability

`compare` lines several candidates up on the same criteria and names the trade-offs between them."""
from . import checks as CK

BASIS = {"catalogue": "Catalogue (unverified)", "checked": "Checked", "heuristic": "Heuristic", "unknown": "Unknown"}
CRITERIA = [("suitability", "Feature fit"), ("documentation", "Documentation"), ("auth", "Authentication"), ("pricing", "Pricing and free tier"),
            ("reliability", "Reliability and maintenance"), ("integration", "Integration effort"), ("security", "Security"), ("licensing", "Licence and commercial use")]
AUTH_LABEL = {"none": "No key", "apiKey": "API key", "oauth": "OAuth", "header": "Custom header", "unknown": "Not stated"}


def _f(key, text, basis, tone=None):
    return {"criterion": key, "title": dict(CRITERIA)[key], "finding": text, "basis": basis, "tone": tone}


def assess(e, check=None, why=None):
    """The eight criteria for one entry. `why` (from search) makes feature fit specific to the need."""
    out = []
    if why:
        stated = [w for w in why if not w.get("suggested")]
        bits = [f"\"{w['term']}\" in its {w['in']}" + (f" (as \"{w['via']}\")" if w.get("via") and w["via"] != w["term"] else "") for w in (stated or why)[:4]]
        out.append(_f("suitability", "Matches " + ", ".join(bits) + ". Matched on the catalogue's one-line description, so confirm the endpoints you need in its documentation.", "heuristic"))
    else:
        out.append(_f("suitability", f"Listed under {e['category']}: {e.get('description') or 'no description in the catalogue'}.", "catalogue"))
    if check:
        day = str(check.get("checked") or "")[:10]
        st = check["status"]
        txt = {"reachable": f"The documentation link answered on {day}.",
               "moved": f"On {day} the documentation link led to a different site ({check.get('final_host')}). The API may have moved, been renamed or been retired.",
               "refused": f"On {day} the site refused the automated check. That says nothing about the documentation: open the link.",
               "missing": f"On {day} the documentation link returned an error page (HTTP {check.get('http')}). The API may have moved or shut down.",
               "unreachable": f"On {day} the documentation link did not answer" + (f" ({check['error']})" if check.get("error") else "") + ". The API may be gone; check before building on it."}[st]
        out.append(_f("documentation", txt + " Whether the documentation is complete or current was not assessed.", "checked", {"reachable": "good", "refused": None}.get(st, "bad")))
    else:
        out.append(_f("documentation", "The catalogue links to its documentation. The link has not been checked.", "unknown"))
    a = e["auth"]
    out.append(_f("auth", {"none": "No key or sign-up is listed: you can try it immediately.",
                           "apiKey": "Needs an API key: sign up with the provider, then keep the key on your server.",
                           "oauth": "Uses OAuth: register an application with the provider and implement the token flow. The most setup of the three.",
                           "header": f"Needs a specific request header ({e.get('auth_raw')}).",
                           "unknown": "The catalogue does not say how it authenticates."}[a], "catalogue" if a != "unknown" else "unknown",
                  {"none": "good", "oauth": "caution"}.get(a)))
    out.append(_f("pricing", ("No key is listed, which usually means no charge, and usually means anonymous rate limits. " if a == "none" else "") +
                  "Pricing, free-tier limits and quotas are not in the catalogue: read the provider's pricing page before you depend on it.", "unknown"))
    if check and check["status"] in ("missing", "unreachable", "moved"):
        out.append(_f("reliability", "Its documentation link failed the last check (see Documentation), which is a warning sign. Uptime, maintenance and support are otherwise unknown.", "checked", "bad"))
    else:
        out.append(_f("reliability", "Uptime, maintenance activity and support are not in the catalogue and cannot be measured from outside. "
                      + ("A documentation link that answers is not evidence of a reliable API. " if check else "") + "Look for a status page, a changelog and recent releases.", "unknown"))
    steps = {"none": 1, "apiKey": 2, "header": 2, "oauth": 4, "unknown": 2}[a] + (1 if e["cors"] != "yes" else 0)
    out.append(_f("integration", {1: "Low: one unauthenticated request, callable from a browser if the CORS listing is right.",
                                  2: "Low to moderate: " + ("a key held on your server and one route that forwards the call." if a != "none" else "no key, but call it from your server (CORS is not listed as supported)."),
                                  3: "Moderate: a key held on your server and a server route, since CORS is not listed as supported.",
                                  4: "Higher: an OAuth application, a token exchange and token refresh.",
                                  5: "Higher: an OAuth application, token handling, and a server route since CORS is not listed as supported."}[steps], "heuristic"))
    sec = []
    if e["https"] == "no": sec.append("Listed as HTTP only: requests and responses travel unencrypted, browsers on HTTPS pages will block it, and it is unsuitable for anything personal or authenticated.")
    elif e["https"] == "yes": sec.append("Listed with HTTPS.")
    else: sec.append("HTTPS support is not stated.")
    if a in ("apiKey", "header", "oauth"): sec.append("Its credential is a secret: never put it in browser or mobile-app code, a public repository or a client-visible environment variable.")
    sec.append("Treat every response as untrusted input: validate it and never render it as HTML.")
    out.append(_f("security", " ".join(sec), "catalogue" if e["https"] != "unknown" else "unknown", "bad" if e["https"] == "no" else None))
    out.append(_f("licensing", "Terms of use, attribution requirements and whether commercial use is allowed are not in the catalogue. Read the provider's terms before shipping.", "unknown"))
    return out


def summary(e, check=None):
    """Strengths and cautions that follow from what is known. Unknowns are listed as unknown, never as either."""
    good, bad = [], []
    if e["auth"] == "none": good.append("no key needed")
    if e["https"] == "yes": good.append("HTTPS")
    if e["cors"] == "yes": good.append("callable from a browser (per the catalogue)")
    if check and check["status"] == "reachable": good.append("documentation link answered when checked")
    if e["https"] == "no": bad.append("HTTP only")
    if e["auth"] == "oauth": bad.append("OAuth setup")
    if e["cors"] == "no": bad.append("no CORS: needs a server route")
    if check and check["status"] in ("missing", "unreachable"): bad.append("documentation link failed the last check")
    if check and check["status"] == "moved": bad.append("documentation link leads elsewhere")
    if e.get("sponsored"): bad.append("a sponsored listing in the catalogue")
    return {"strengths": good, "cautions": bad, "unknown": ["pricing and limits", "reliability", "licence terms"]}


def compare(entries, checks=None, whys=None):
    """Several candidates on the same criteria, and the trade-offs between them (2 to 4 entries)."""
    es = list(entries)[:4]
    cols = []
    for e in es:
        ck = CK.for_entry(checks, e) if checks else None
        cols.append({"entry": {k: v for k, v in e.items() if k != "_ix"}, "check": ck, "criteria": assess(e, ck, (whys or {}).get(e["id"])), "summary": summary(e, ck)})
    trade = []
    names = lambda f: ", ".join(e["name"] for e in es if f(e))
    if len({e["auth"] for e in es}) > 1:
        if names(lambda e: e["auth"] == "none"): trade.append(f"{names(lambda e: e['auth'] == 'none')} can be called without signing up; {names(lambda e: e['auth'] != 'none')} cannot. "
                                                              "Keyless APIs are the quickest to try and typically the most tightly rate-limited.")
        if names(lambda e: e["auth"] == "oauth"): trade.append(f"{names(lambda e: e['auth'] == 'oauth')} needs an OAuth flow, the largest integration cost here.")
    if len({e["cors"] for e in es}) > 1 and names(lambda e: e["cors"] == "yes"):
        trade.append(f"Only {names(lambda e: e['cors'] == 'yes')} is listed as callable straight from a browser; the others need a server route (which you want anyway if a key is involved).")
    if names(lambda e: e["https"] == "no"): trade.append(f"{names(lambda e: e['https'] == 'no')} is listed as HTTP only: rule it out for production unless you proxy it and the data is not sensitive.")
    bad = [c["entry"]["name"] for c in cols if c["check"] and c["check"]["status"] in ("missing", "unreachable", "moved")]
    if bad: trade.append(f"The documentation link of {', '.join(bad)} failed the last check: confirm it still exists before comparing further.")
    trade.append("Pricing, limits, reliability and licence terms are unknown for all of them: those decide the choice, and only each provider's own pages answer them.")
    return {"columns": cols, "criteria": [{"key": k, "title": t} for k, t in CRITERIA], "tradeoffs": trade, "basis": BASIS,
            "method": "No scores: each cell is a statement with its basis. Catalogue values are public-apis' claims; only the documentation link is checked by this tool."}
