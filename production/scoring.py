"""Production Report scoring: one transparent rubric per department, an overall weighted score, and release gates
kept apart from quality scores.

Rules (tests/test_report.py holds them):
  * A department's 0–100 score is always a measured number taken from that department's own result (PLAYCRAFT's
    gameplay score, PIXELCRAFT's audit score, …) or a ratio of measured checks. Nothing here estimates a score.
  * A department that applies to the project but has no measured result is Not Evaluated: no score, no weight.
  * The overall score is the weighted mean of the evaluated departments only. Its coverage (evaluated weight ÷
    applicable weight) is shown next to it and never folded into it.
  * Release gates (acceptance criteria, the Director's verdict) and approvals are pass/fail states. They are shown
    as gates and never averaged into a quality score.
  * Every rubric has a version. A previous score is compared (delta) only when the rubric version and the
    department's own method are the same; otherwise the report says the method changed and shows no delta.
"""
import json, os

METHOD = "gitcraft-score/2"          # the overall weighted score; reports before it used "mean/1" (plain mean)
LEGACY_METHOD = "mean/1"

# id → rubric. `version` changes whenever what the number means changes.
#  legacy: the rubric version a report made before METHOD existed is treated as (None = not comparable).
RUBRICS = {
    "playcraft": {"label": "Gameplay quality", "weight": 25, "version": "playcraft/1", "legacy": "playcraft/1",
                  "source": "PLAYCRAFT's own overall score from the Game Quality History",
                  "criteria": ["10 categories (core gameplay, game feel, controls, progression, difficulty, player experience, replayability, "
                               "technical, presentation, mobile), genre-weighted",
                               "Each criterion pass/partial/fail, weighted by evidence: verified 1, observed 0.85, inferred 0.45",
                               "A category with no played (verified/observed) evidence is capped at 70; untested criteria count for nothing"]},
    "pixelcraft": {"label": "Visual quality and usability", "weight": 20, "version": "pixelcraft/1", "legacy": "pixelcraft/1",
                   "source": "PIXELCRAFT's overall audit score (mean over audited UIs)",
                   "criteria": ["Visual Quality, Usability and Consistency, 100 points each, measured in Chromium at iPhone 17, iPhone 13 and desktop",
                                "Each metric scored 0.6 × mean + 0.4 × worst screen, so one bad screen counts",
                                "Areas without evidence are not tested and are excluded (coverage shown beside the score)"]},
    "designcraft": {"label": "Game design", "weight": 15, "version": "designcraft/1", "legacy": "designcraft/1",
                    "source": "DESIGNCRAFT's 100-point design score",
                    "criteria": ["Level 15 · Mission 15 · Narrative 15 · Progression 15 · Agency 10 · Difficulty 10 · Worldbuilding 10 · Variety 10",
                                 "Untested criteria score 0 and raise the ceiling; having code earns nothing"]},
    "testcraft": {"label": "Automated QA", "weight": 15, "version": "testcraft/1", "legacy": "testcraft/1",
                  "source": "share of TestCraft output checks that passed",
                  "criteria": ["Every check recorded in TestCraft's .studio.json records for this project", "score = passed checks ÷ all checks × 100"]},
    "production": {"label": "Engineering standard", "weight": 15, "version": "standard/1", "legacy": None,
                   "source": "the engineering standard (docs/app-standards.md), checked read-only on the project",
                   "criteria": ["Applicable checks only (n/a excluded)", "ok or accepted = 1, advisory (measured, non-blocking) = 0.5, review or failed = 0",
                                "Acceptance criteria are release gates, not part of this score"]},
    "assetcraft": {"label": "Asset licensing", "weight": 5, "version": "assetcraft/1", "legacy": "assetcraft/1",
                   "source": "the AssetCraft catalogue",
                   "criteria": ["score = catalogued assets with a known licence ÷ all catalogued assets × 100"]},
    "3d": {"label": "3D jobs succeeded", "weight": 5, "version": "jobs/1", "legacy": None,
           "source": "the 3D Department's job store",
           "criteria": ["score = succeeded jobs ÷ finished jobs × 100", "Only applies when the 3D Department worked on this project"]},
}
MAKER_RUBRIC = {"label": "Output checks passed", "weight": 5, "version": "outputs/1", "legacy": None,
                "source": "the department's .studio.json records (every output validated and hashed)",
                "criteria": ["score = output checks passed ÷ all output checks × 100", "Only applies when the department made outputs for this project"]}


def rubric(did):
    return RUBRICS.get(did) or dict(MAKER_RUBRIC)


def _std_score(st):
    """The engineering standard's score from its checks, or None without checks."""
    rel = (st or {}).get("checks") or []
    if not rel: return None
    val = {"ok": 1.0, "accepted": 1.0, "advisory": 0.5}
    return round(100 * sum(val.get(c, 0.0) for c in rel) / len(rel), 1)


def evaluate(D):
    """Annotate one department of a report with its rubric, evaluation state and quality score (in place).
    evaluation: evaluated | not_evaluated | not_applicable."""
    rb = rubric(D["id"]); sc = D.get("score") or {}
    val, basis = None, None
    if D["id"] == "production":
        val = _std_score(D.get("standard")); basis = (f"{D['standard']['passed']}/{D['standard']['of']} applicable checks pass" if D.get("standard") else None)
    elif D["id"] == "3d":
        j = D.get("jobs") or {}
        fin = j.get("succeeded", 0) + j.get("failed", 0) + j.get("blocked", 0)
        if fin: val = round(100 * j.get("succeeded", 0) / fin, 1); basis = f"{j.get('succeeded', 0)}/{fin} finished jobs succeeded"
    elif D["id"] in RUBRICS:
        val = sc.get("value")
    else:
        c = D.get("checks") or {}
        if c.get("of"): val = round(100 * c["passed"] / c["of"], 1); basis = f"{c['passed']}/{c['of']} output checks passed"
    applicable = D.get("applicable", True) and D["status"] != "not_applicable"
    if D["id"] not in RUBRICS and D["id"] != "production" and D["status"] in ("no_data",):
        applicable = False   # a maker department only applies when it made something for this project
    if D["id"] == "3d" and D["status"] == "no_data": applicable = False
    if D["id"] == "assetcraft" and D["status"] == "unavailable" and not D.get("score"): pass
    ev = "not_applicable" if not applicable else ("evaluated" if val is not None and D["status"] not in ("failed",) else "not_evaluated")
    if ev != "evaluated": val = None
    D["quality"] = {"evaluation": ev, "value": val, "label": rb["label"], "weight": rb["weight"] if applicable else 0, "rubric": rb["version"],
                    "method": (D.get("run") or {}).get("method"), "source": rb["source"], "criteria": rb["criteria"], "basis": basis or (sc.get("label") if val is not None else None),
                    "confidence": sc.get("confidence") if D["id"] in RUBRICS else ("high" if val is not None else None), "coverage": sc.get("coverage")}
    if ev == "not_evaluated":
        D["quality"]["why"] = (D.get("next") or (D["notes"][-1] if D["notes"] else "no measured result for this project"))
    return D


def overall(depts, p0=0, stale=()):
    """The weighted overall score over evaluated departments only, with coverage and confidence."""
    ev = [d for d in depts if d["quality"]["evaluation"] == "evaluated"]
    app = [d for d in depts if d["quality"]["evaluation"] != "not_applicable"]
    wa = sum(d["quality"]["weight"] for d in app)
    if not ev:
        return {"score": None, "method": METHOD, "band": "insufficient data", "confidence": "none", "measured": 0, "of": len(app), "coverage": 0.0,
                "stale": list(stale), "p0": p0, "parts": {}, "weights": {}, "basis": "No applicable department has a measured score yet, so there is no overall score."}
    we = sum(d["quality"]["weight"] for d in ev)
    v = round(sum(d["quality"]["value"] * d["quality"]["weight"] for d in ev) / we, 1)
    cov = round(we / wa, 2) if wa else 0.0
    conf = "high" if cov >= 0.75 and not stale else "medium" if cov >= 0.5 and len(stale) <= 1 else "low"
    band = "blocked" if p0 else "healthy" if v >= 80 else "needs attention" if v >= 60 else "at risk"
    missing = [d["id"] for d in app if d["quality"]["evaluation"] == "not_evaluated"]
    return {"score": v, "method": METHOD, "band": band, "confidence": conf, "measured": len(ev), "of": len(app), "coverage": cov, "stale": list(stale), "p0": p0,
            "parts": {d["id"]: d["quality"]["value"] for d in ev}, "weights": {d["id"]: d["quality"]["weight"] for d in ev},
            "basis": f"weighted mean of {len(ev)} evaluated department score(s) (" + ", ".join(f"{d['id']} ×{d['quality']['weight']}" for d in ev) + ")"
                     + (f"; {len(missing)} applicable department(s) not evaluated ({', '.join(missing)})" if missing else "")
                     + f"; coverage {round(cov * 100)}% of the applicable weight" + (f"; {len(stale)} stale" if stale else "")}


def gates(depts):
    """Release gates and approvals: pass/fail states from the latest production, never averaged into a score."""
    D = next((d for d in depts if d["id"] == "production"), None) or {}
    pr = D.get("production")
    if not pr:
        return {"production": None, "verdict": None, "status": None, "release_status": None, "criteria": [], "approvals": [],
                "note": "No production has run for this project, so there is no Director verdict and no release gates."}
    return {"production": pr["id"], "verdict": (pr.get("verdict") or {}).get("verdict") if isinstance(pr.get("verdict"), dict) else pr.get("verdict"),
            "reasons": (pr.get("verdict") or {}).get("reasons") if isinstance(pr.get("verdict"), dict) else None,
            "status": pr.get("status"), "release_status": pr.get("release_status"), "criteria": pr.get("criteria_list") or [],
            "passed": pr.get("passed"), "of": pr.get("criteria"), "approvals": [c for c in pr.get("criteria_list") or [] if c["status"] == "needs_approval"], "ran": pr.get("ran")}


def _dept_comparable(prev_d, cur_d, prev_method):
    """(comparable, why) for one department across two reports."""
    pq = prev_d.get("quality") or {}
    cq = cur_d["quality"]
    prub = pq.get("rubric") if pq else (rubric(cur_d["id"]).get("legacy") if prev_method == LEGACY_METHOD else None)
    if prub != cq["rubric"]: return False, "scoring rubric changed"
    pm = pq.get("method") if pq else (prev_d.get("run") or {}).get("method")
    if pm and cq.get("method") and pm != cq["method"]: return False, "the department's own scoring method changed"
    return True, None


def _prev_value(prev_d, prev_method):
    if not prev_d: return None
    pq = prev_d.get("quality")
    if pq: return pq.get("value")
    return (prev_d.get("score") or {}).get("value") if prev_method == LEGACY_METHOD else None


def same_measurement(a, b):
    """Two department runs are the same measurement when they have the same id and time (a re-analysis made for a
    report is always called "this report", so the id alone is not enough)."""
    a, b = a or {}, b or {}
    return bool(a.get("id")) and a.get("id") == b.get("id") and str(a.get("at") or "")[:19] == str(b.get("at") or "")[:19]


def deltas(prev, depts):
    """Per department: previous score, delta (only when comparable), and why not."""
    pm = ((prev or {}).get("health") or {}).get("method") or (LEGACY_METHOD if prev else None)
    pd = {d["id"]: d for d in (prev or {}).get("departments") or []}
    for d in depts:
        q = d["quality"]; p = pd.get(d["id"])
        q["previous"] = None; q["delta"] = None; q["compare"] = "first report" if not prev else "not in the previous report" if not p else None
        if not p: continue
        pv = _prev_value(p, pm)
        q["previous"] = pv
        if pv is None and q["value"] is None: q["compare"] = "not evaluated in either report"; continue
        if pv is None: q["compare"] = "first score"; continue
        if q["value"] is None: q["compare"] = "not evaluated now"; continue
        ok, why = _dept_comparable(p, d, pm)
        if not ok: q["compare"] = f"not comparable: {why}"; continue
        same_run = same_measurement(p.get("run"), d.get("run"))
        pa, ca = str((p.get("run") or {}).get("at") or ""), str((d.get("run") or {}).get("at") or "")
        if not same_run and pa and ca and ca[:19] < pa[:19]:
            q["compare"] = "not comparable: this report reads an older measurement than the previous report did"; continue
        q["delta"] = round(q["value"] - pv, 1)
        q["compare"] = "same measurement as before (no new run)" if same_run else "new measurement"
    return depts


def overall_delta(prev, H):
    if not prev: return {"previous": None, "delta": None, "compare": "first report"}
    ph = prev.get("health") or {}
    pv = ph.get("score"); pm = ph.get("method") or LEGACY_METHOD
    if pv is None or H.get("score") is None: return {"previous": pv, "delta": None, "compare": "no overall score in one of the two reports"}
    if pm != H["method"]: return {"previous": pv, "previous_method": pm, "delta": None, "compare": f"not comparable: the overall method changed ({pm} → {H['method']})"}
    pp, cp = set((ph.get("parts") or {})), set((H.get("parts") or {}))
    if ph.get("parts") is not None and pp != cp:   # a different set of departments is a different average, not a change in quality
        diff = ", ".join([f"+{x}" for x in sorted(cp - pp)] + [f"-{x}" for x in sorted(pp - cp)])
        return {"previous": pv, "delta": None, "compare": f"not comparable: different departments were evaluated ({diff})"}
    return {"previous": pv, "delta": round(H["score"] - pv, 1), "compare": "same method"}


def series(history, cur):
    """Trend points per report (oldest first): overall and every department, each with its method so a chart can
    break the line where the method changed. `history` is a list of earlier report dicts."""
    pts = []
    for R in sorted(history, key=lambda r: r["generated"]) + [cur]:
        h = R.get("health") or {}
        pm = h.get("method") or LEGACY_METHOD
        dep = {}
        for d in R.get("departments") or []:
            q = d.get("quality")
            if q: dep[d["id"]] = {"value": q.get("value"), "rubric": q.get("rubric")}
            elif pm == LEGACY_METHOD:
                v = (d.get("score") or {}).get("value"); lg = rubric(d["id"]).get("legacy")
                dep[d["id"]] = {"value": v if lg else None, "rubric": lg}
        pts.append({"report_id": R["report_id"], "at": R["generated"], "overall": h.get("score"), "method": pm, "departments": dep})
    return pts


IMPACT = {"P0": "High", "P1": "High", "P2": "Medium", "P3": "Low"}
EFFORT_NOTE = "Effort is the owning department's own estimate (PLAYCRAFT effort, PIXELCRAFT cost, DESIGNCRAFT complexity); none is invented."


def effort_label(raw):
    """A department's effort/cost/complexity → S / M / L, or None."""
    if raw is None: return None
    if isinstance(raw, str): return {"low": "S", "small": "S", "medium": "M", "high": "L", "large": "L"}.get(raw.lower())
    try: v = float(raw)
    except (TypeError, ValueError): return None
    return "S" if v <= 1 else "M" if v <= 2 else "L"


def top_actions(actions, findings_by_key, n=3):
    """The n highest-impact actions: improvement actions first (coverage gaps only to fill), with impact from the
    priority rule and effort from the departments' own estimates."""
    real = [a for a in actions if a.get("theme") != "coverage"]
    pick = (real + [a for a in actions if a.get("theme") == "coverage"])[:n]
    out = []
    for a in pick:
        efs = [effort_label((findings_by_key.get(k) or {}).get("effort")) for k in a.get("findings") or []]
        efs = [e for e in efs if e]
        eff = max(efs, key="SML".index) if efs else None
        out.append({"n": a["n"], "priority": a["priority"], "title": a["title"], "do": a.get("do"), "why": a.get("why"), "departments": a["departments"], "level": a["level"],
                    "impact": IMPACT[a["priority"]] + (" (corroborated by several departments)" if len(a["departments"]) > 1 else ""),
                    "impact_basis": f"{a['priority']}: " + {"P0": "a measured blocker", "P1": "a measured major finding or one several departments flag",
                                                           "P2": "an inferred major finding, a measured minor one or a gap", "P3": "a minor or inferred finding"}[a["priority"]],
                    "effort": eff, "effort_basis": "department estimate" if eff else "not estimated by the department"})
    return out


_PC_EFFORT = None


def playcraft_effort(fid):
    """PLAYCRAFT's own effort estimate for a criterion id (core rubric + genre criteria), or None."""
    global _PC_EFFORT
    if _PC_EFFORT is None:
        _PC_EFFORT = {}
        from . import REPO
        try:
            import importlib.util
            p = os.path.join(REPO, "studio", "departments", "playcraft", "rubric.py")
            spec = importlib.util.spec_from_file_location("gcr_pc_rubric", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
            for c in m.CORE: _PC_EFFORT[c["id"]] = c.get("effort")
            g = json.load(open(os.path.join(REPO, "studio", "departments", "playcraft", "genres.json")))["genres"]
            for gp in g.values():
                for c in gp.get("criteria") or []: _PC_EFFORT.setdefault(c["id"], c.get("effort"))
        except Exception:
            pass
    return _PC_EFFORT.get(fid)
