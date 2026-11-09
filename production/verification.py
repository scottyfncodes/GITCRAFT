"""RELEASE VERIFICATION: tell a broken application apart from a broken or incomplete verification.

Every check a release depends on lands in exactly one of four categories:

  BLOCKER      a confirmed application failure, security vulnerability, broken functionality, or a violated
               mandatory release requirement. Blocks release: NOT READY.
  UNVERIFIED   the check could not be completed: the verifier's network was restricted (sandbox, proxy), an
               external service was down, a runtime was missing, or the evidence is insufficient. Never READY while
               a mandatory check is unverified, and never reported as an application failure.
  ADVISORY     a non-blocking improvement, a configuration-metadata mismatch, or an accepted architectural
               decision. Recorded and shown; never blocks.
  PASS         verified with appropriate evidence.

A check is a dict {name, ok, detail, ...}; `category` says which of the four it is. A check without one is PASS
when ok and BLOCKER when not (the strict default: nothing is downgraded without saying why).

Three things are kept apart and reported separately:
  deployment status       is the URL live, and is it serving this release (commit/build provenance)?
  verification complete   did every mandatory check actually run with evidence?
  release readiness       READY only when deployed-or-not-required, complete, and no blocker.

The release status line (release_summary) is one of:
  READY                                   every mandatory check passed with evidence (and the deployment, if any, verified)
  NOT READY                               at least one BLOCKER
  DEPLOYED · VERIFICATION INCOMPLETE      the live URL serves this release, no blocker, mandatory checks unverified
  VERIFICATION INCOMPLETE                 no blocker, mandatory checks unverified, not (verifiably) deployed
"""
import json, os

PASS, BLOCKER, UNVERIFIED, ADVISORY = "pass", "blocker", "unverified", "advisory"
CATEGORIES = (BLOCKER, UNVERIFIED, ADVISORY, PASS)
LABEL = {PASS: "PASS", BLOCKER: "BLOCKER", UNVERIFIED: "UNVERIFIED", ADVISORY: "ADVISORY"}

# acceptance criteria → release dimensions (anything not listed is functional)
SECURITY = {"engineering_standards"}
VISUAL = {"interface_quality", "app_icon", "visual_identity"}
NOT_DIMENSION = {"deployment", "release_ready"}


def category(check):
    c = (check or {}).get("category")
    if c in CATEGORIES: return c
    return PASS if (check or {}).get("ok") else BLOCKER


def make(name, cat, detail=None, cause=None, **kw):
    """A categorised check. ok is True for PASS and ADVISORY (they never fail a gate on their own)."""
    assert cat in CATEGORIES, cat
    d = {"name": name, "ok": cat in (PASS, ADVISORY), "category": cat, "detail": detail}
    if cause: d["cause"] = cause
    d.update(kw); return d


def split(checks):
    out = {c: [] for c in CATEGORIES}
    for c in checks or []: out[category(c)].append(c)
    return out


def status_of(checks):
    """ok (all PASS/ADVISORY), failed (any BLOCKER), incomplete (no BLOCKER, some UNVERIFIED)."""
    s = split(checks)
    if s[BLOCKER]: return "failed"
    if s[UNVERIFIED]: return "incomplete"
    return "ok" if checks else "incomplete"


def summary(checks):
    s = split(checks)
    return {k: len(v) for k, v in s.items()}


def worst(cats):
    for c in (BLOCKER, UNVERIFIED, ADVISORY, PASS):
        if c in cats: return c
    return None


# ---------------------------------------------------------------- the release summary
def live_record(prod):
    """The latest live check (production/live.py) for this production, whether or not it was submitted."""
    from . import store
    p = os.path.join(store.task_dir(prod, "release.deploy"), "live-check.json")
    try:
        with open(p) as f: r = json.load(f)
        r["record"] = p; return r
    except (OSError, ValueError): return None


def deployment_status(prod, rec=None):
    """{status, label, url, detail}. status: not_requested | not_deployed | live_verified | deployed_incomplete | not_serving | unreachable."""
    spec = prod.get("spec") or {}
    wanted = bool((spec.get("features") or {}).get("deploy")) or "release.deploy" in (prod.get("tasks") or {})
    rec = rec if rec is not None else live_record(prod)
    if not rec:
        return {"status": "not_requested" if not wanted else "not_deployed", "label": "not requested" if not wanted else "NOT DEPLOYED (no live check recorded)", "url": None}
    url = (rec.get("request") or {}).get("url"); dep = rec.get("deployment") or {}
    if dep.get("serving") is True and rec.get("status") == "ok":
        return {"status": "live_verified", "label": "DEPLOYED · verified live", "url": url, "detail": dep.get("evidence")}
    if dep.get("serving") is True:
        return {"status": "deployed_incomplete" if rec.get("status") == "incomplete" else "deployed_with_blockers",
                "label": "DEPLOYED" + (" · verification incomplete" if rec.get("status") == "incomplete" else " · live checks found blockers"), "url": url, "detail": dep.get("evidence")}
    if dep.get("answers") is False and dep.get("cause") == "sandbox_network":
        return {"status": "unreachable", "label": "UNVERIFIED (the verifier could not reach the URL)", "url": url, "detail": dep.get("detail")}
    return {"status": "not_serving", "label": "NOT SERVING THIS RELEASE", "url": url, "detail": dep.get("detail")}


def release_summary(prod, acc=None):
    """The release summary every report leads with: deployment, functional, security, visual, unverified (with
    causes), advisories, and the release status line."""
    from . import report
    acc = acc if acc is not None else report.acceptance(prod)
    rec = live_record(prod)
    dep = deployment_status(prod, rec)
    dims = {"functional": [], "security": [], "visual": []}
    unverified, advisories, blockers, optional = [], [], [], []
    for a in acc:
        if a["id"] in NOT_DIMENSION: continue
        if a["status"] == "optional_missing":   # optional by a person's decision: listed, never a blocker, never "incomplete"
            optional.append({"criterion": a["id"], "detail": "; ".join(map(str, a.get("why") or []))[:300]}); continue
        cat = {"passed": PASS, "advisory": ADVISORY, "failed": BLOCKER, "not_planned": UNVERIFIED}.get(a["status"], UNVERIFIED)
        dim = "security" if a["id"] in SECURITY else "visual" if a["id"] in VISUAL else "functional"
        dims[dim].append(cat)
        why = "; ".join(map(str, a.get("why") or []))[:300]
        if cat == BLOCKER: blockers.append({"criterion": a["id"], "detail": why})
        elif cat == UNVERIFIED: unverified.append({"criterion": a["id"], "cause": a.get("cause") or a["status"], "detail": why or a["status"]})
        elif cat == ADVISORY: advisories.append({"criterion": a["id"], "detail": why})
        for x in a.get("advisories") or []: advisories.append({"criterion": a["id"], "detail": x})
    # the live check's own findings
    for c in (rec or {}).get("checks") or []:
        k = category(c)
        if k == BLOCKER: blockers.append({"criterion": "deployment", "detail": f"{c['name']}: {str(c.get('detail'))[:200]}"})
        elif k == UNVERIFIED: unverified.append({"criterion": "deployment", "cause": c.get("cause") or "unverified", "detail": f"{c['name']}: {str(c.get('detail'))[:200]}"})
        elif k == ADVISORY: advisories.append({"criterion": "deployment", "detail": f"{c['name']}: {str(c.get('detail'))[:200]}"})
    st = {d: (LABEL[worst(v)] if v else "NOT MEASURED") for d, v in dims.items()}
    if "security" in st and not dims["security"]: st["security"] = "NOT MEASURED"
    v = report.verdict(acc)
    if blockers or v == "NOT READY": line = "NOT READY"
    elif unverified or v == "INCOMPLETE":
        line = "DEPLOYED · VERIFICATION INCOMPLETE" if dep["status"] in ("live_verified", "deployed_incomplete") else "VERIFICATION INCOMPLETE"
    else: line = v   # READY, or READY — deployment <state> (the release passed; the deploy is still owed or unverified)
    return {"deployment": dep, "functional": st["functional"], "security": st["security"], "visual": st["visual"],
            "blockers": blockers, "unverified": unverified, "advisories": advisories, "optional_not_delivered": optional, "verdict": v, "release_status": line,
            "verification_complete": not unverified and v != "INCOMPLETE"}


def markdown(rs):
    L = ["## Release summary", "", "| | |", "|---|---|",
         f"| Deployment | {rs['deployment']['label']}" + (f" — {rs['deployment']['url']}" if rs['deployment'].get('url') else "") + " |",
         f"| Functional verification | {rs['functional']} |", f"| Security / blockers | {rs['security']} · {len(rs['blockers'])} blocker(s) |",
         f"| Visual audit | {rs['visual']} |", f"| Verification complete | {'yes' if rs['verification_complete'] else 'no'} |",
         f"| **Release** | **{rs['release_status']}** |", ""]
    if rs["blockers"]: L += ["**Blockers** (confirmed failures)", ""] + [f"- {b['criterion']}: {b['detail']}" for b in rs["blockers"][:20]] + [""]
    if rs["unverified"]: L += ["**Unverified** (could not be verified; not application failures)", ""] + [f"- {u['criterion']} [{u['cause']}]: {u['detail']}" for u in rs["unverified"][:20]] + [""]
    if rs["advisories"]: L += ["**Advisories** (non-blocking)", ""] + [f"- {a['criterion']}: {a['detail']}" for a in rs["advisories"][:20]] + [""]
    if rs.get("optional_not_delivered"): L += ["**Optional, not delivered** (made optional by a person; listed, not blocking)", ""] + \
                                             [f"- {o['criterion']}: {o['detail']}" for o in rs["optional_not_delivered"][:20]] + [""]
    return L
