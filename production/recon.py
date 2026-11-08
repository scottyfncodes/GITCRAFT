"""RECON: an optional, bounded look at an idea before anything is built.

GITCRAFT's sandbox has no network, so research is the agent's work order (web search and fetch with the agent's own
tools), and this module holds the line on evidence: every claim names its source or says it is an assumption, a
domain or name is never "available" without a check that says so, and Recon ends with one recommendation.

  order(depth)        the work order: Quick (≤ 6 searches, ~10 minutes) or Deep (≤ 20 searches); the budget is part
                      of the order so Recon cannot become an endless research loop
  validate(findings)  → [check]: the five sections, evidence on every finding, the verdict, its uncertainties
  markdown(findings)  RECON.md, the report a person reads

Sections: reality_check (feasibility, usefulness, constraints, weaknesses), competition_radar (existing products and
alternatives), identity_check (name, brand and domain conflicts: verified vs assumed), zag (differentiation,
simplification), recommendation {verdict: build | pivot | park, reasoning, uncertainties}."""
import re

BUDGET = {"quick": {"searches": 6, "minutes": 10, "competitors": "the 3 closest"},
          "deep": {"searches": 20, "minutes": 45, "competitors": "up to 8, with pricing and positioning"}}
SECTIONS = ["reality_check", "competition_radar", "identity_check", "zag", "recommendation"]
BASIS = {"verified", "source", "assumption", "inference"}
URL = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.I)


def order(prod, depth):
    if depth not in BUDGET: raise ValueError(f"recon depth must be quick or deep, not {depth!r}")
    b = BUDGET[depth]; brief = prod.get("brief") or {}
    return {"depth": depth, "budget": b, "idea": brief.get("text") or prod["spec"]["prompt"],
            "brief": "Reality-check this idea before it is built, with evidence. Stop at the budget and recommend.",
            "instructions": [
                f"Use at most {b['searches']} web searches/fetches (~{b['minutes']} minutes). Stop when the budget is spent, even if questions remain: list them as uncertainties.",
                "reality_check: is it feasible here (GITCRAFT, a browser app), is it useful, what constrains it, what is weak about it.",
                f"competition_radar: {b['competitors']} existing products or approaches. Each needs a source URL you actually opened; otherwise basis 'assumption'.",
                "identity_check: the working name against existing products, trademarks and domains. A domain is 'available' only if a registrar or WHOIS lookup you ran says so (basis 'verified' with its URL); otherwise say 'unverified'.",
                "zag: where this could be meaningfully different, simpler or better than what exists.",
                "recommendation: verdict build, pivot or park, the reasoning, and the uncertainties that could change it.",
                "Never invent a competitor, a price, a statistic, a domain status or a validation result."],
            "format": {"reality_check": [{"claim": "…", "basis": "source|verified|assumption|inference", "evidence": ["https://…"]}],
                       "competition_radar": [{"name": "…", "what": "…", "url": "https://…", "basis": "source|assumption"}],
                       "identity_check": [{"claim": "the name X is used by …", "basis": "verified|source|assumption", "evidence": ["https://…"], "conflict": True}],
                       "zag": [{"claim": "…", "basis": "inference"}],
                       "recommendation": {"verdict": "build|pivot|park", "reasoning": "…", "uncertainties": ["…"]},
                       "searches_used": 0},
            "submit": f"production_recon {{\"production\": \"{prod['id']}\", \"findings\": {{…}}}}"}


def _item_checks(sec, items):
    out = []
    if not isinstance(items, list) or not items:
        return [{"name": f"{sec}: at least one finding", "ok": False}]
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict): out.append({"name": f"{sec} #{i} is an object", "ok": False}); continue
        basis = it.get("basis"); ev = it.get("evidence") or ([it["url"]] if it.get("url") else [])
        out.append({"name": f"{sec} #{i}: basis is one of {sorted(BASIS)}", "ok": basis in BASIS, "detail": basis})
        if basis in ("source", "verified"):
            good = [e for e in ev if isinstance(e, str) and URL.match(e)]
            out.append({"name": f"{sec} #{i}: a {basis} finding cites the URL it came from", "ok": bool(good), "detail": None if good else "no evidence URL: mark it 'assumption'"})
        txt = " ".join(str(it.get(k, "")) for k in ("claim", "what", "name")).lower()
        if sec == "identity_check" and re.search(r"\bavailable\b", txt) and basis != "verified":
            out.append({"name": f"identity_check #{i}: a domain or name is called available only with a verified lookup", "ok": False,
                        "detail": "say 'unverified' or run the lookup and cite it"})
        if sec == "competition_radar":
            out.append({"name": f"competition_radar #{i}: names the product", "ok": bool(it.get("name"))})
    return out


def validate(findings, depth="quick"):
    if not isinstance(findings, dict): return [{"name": "findings is an object", "ok": False}]
    checks = [{"name": f"section {s} present", "ok": s in findings} for s in SECTIONS]
    for s in ("reality_check", "competition_radar", "identity_check", "zag"):
        if s in findings: checks += _item_checks(s, findings[s])
    r = findings.get("recommendation") or {}
    checks.append({"name": "recommendation verdict is build, pivot or park", "ok": str(r.get("verdict", "")).lower() in ("build", "pivot", "park"), "detail": r.get("verdict")})
    checks.append({"name": "the recommendation explains its reasoning", "ok": len(str(r.get("reasoning") or "")) >= 20})
    checks.append({"name": "the recommendation lists its uncertainties", "ok": isinstance(r.get("uncertainties"), list)})
    used = findings.get("searches_used")
    if isinstance(used, int):
        checks.append({"name": f"stayed within the {depth} budget ({BUDGET[depth]['searches']} searches)", "ok": used <= BUDGET[depth]["searches"], "detail": f"{used} used"})
    return checks


def markdown(title, rec):
    f = rec["findings"]; r = f.get("recommendation", {})
    L = [f"# Recon: {title}", "", f"Depth: {rec['depth']} · {rec['at']} · verdict **{str(r.get('verdict', '')).upper()}**", "", r.get("reasoning", ""), ""]
    names = {"reality_check": "Reality Check", "competition_radar": "Competition Radar", "identity_check": "Identity Check", "zag": "The Zag"}
    for s, h in names.items():
        L += [f"## {h}", ""]
        for it in f.get(s) or []:
            ev = it.get("evidence") or ([it["url"]] if it.get("url") else [])
            head = f"**{it['name']}** — {it.get('what', '')}" if it.get("name") else it.get("claim", "")
            L.append(f"- {head} _({it.get('basis')})_" + (" " + " ".join(f"[source]({e})" for e in ev) if ev else ""))
        L.append("")
    L += ["## Uncertainties", ""] + [f"- {u}" for u in r.get("uncertainties") or ["none listed"]]
    return "\n".join(L) + "\n"
