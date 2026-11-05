"""PIXELCRAFT rubric: three independently scored categories of 100 points.

Each area's score is the sample-weighted mean of its metrics (measure.py), each metric 0..1 measured on the
rendered app. Category = sum over scored areas of (area points x area score), rescaled to 100 over the areas that
had evidence. Scores are never capped and never awarded for code existing: an area with no evidence is "not tested"
and is reported in coverage, which (with the evidence mix) gives the confidence. Confidence is separate from quality.

METHOD is the version of the measurement + scoring: before/after comparisons are only made under the same method."""
import math

METHOD = "pixelcraft-1.0"

CATEGORIES = {
    "visual": {"title": "Visual Quality", "areas": {
        "spacing": ("Spacing and rhythm", 25), "layout": ("Layout and composition", 25), "typography": ("Typography and hierarchy", 20),
        "controls": ("Buttons and controls", 20), "consistency_v": ("Visual consistency", 10)}},
    "usability": {"title": "Usability", "areas": {
        "efficiency": ("Interaction efficiency", 25), "navigation": ("Navigation and discoverability", 20), "mobile": ("Mobile ergonomics", 25),
        "feedback": ("Feedback and interaction states", 15), "accessibility": ("Accessibility", 15)}},
    "consistency": {"title": "Consistency", "areas": {
        "cross_screen": ("Cross-screen consistency", 25), "component": ("Component consistency", 25), "responsive": ("Responsive consistency", 20),
        "design_system": ("Design system adherence", 20), "state": ("State consistency", 10)}},
}
AREA_CATEGORY = {a: c for c, spec in CATEGORIES.items() for a in spec["areas"]}
EVIDENCE_WEIGHT = {"measured": 1.0, "accessibility": 1.0, "screenshot": 0.8, "source": 0.3}


# how much one metric weighs inside its area (default 1): defects that block or hurt everyone weigh more
IMPORTANCE = {"layout.overflow": 3, "controls.target_size": 2, "controls.spacing": 1.5, "layout.unobscured": 2, "layout.stability": 1.5,
              "mobile.safe_area": 2, "mobile.input_zoom": 1.5, "mobile.viewport_meta": 3, "mobile.toolbar": 1.5, "keyboard.focus_visible": 2,
              "a11y.axe": 2, "journey.completes": 3, "journey.feedback": 2, "nav.no_dead_ends": 2, "states.pressed": 1.5, "type.min_size": 1.5,
              "spacing.evenness": 1.5, "resp.no_overflow": 2, "component.buttons": 1.5}


def _aggregate(ms):
    """One metric over screens/viewports: the mean, pulled towards the worst sample, so a defect on one screen counts."""
    vals = [m["value"] for m in ms]
    return 0.6 * sum(vals) / len(vals) + 0.4 * min(vals)


def area_scores(metrics):
    out = {}
    for cat, spec in CATEGORIES.items():
        for area, (title, pts) in spec["areas"].items():
            ms = [m for m in metrics if m["area"] == area]
            if not ms:
                out[area] = {"category": cat, "title": title, "points": pts, "score": None, "awarded": None, "metrics": 0, "samples": 0, "evidence": {}}
                continue
            by = {}
            for m in ms: by.setdefault(m["id"], []).append(m)
            detail, num, den = [], 0.0, 0.0
            for k, v in by.items():
                agg = _aggregate(v); w = IMPORTANCE.get(k, 1.0) * EVIDENCE_WEIGHT.get(v[0]["evidence"], 0.5)
                num += agg * w; den += w
                worst = min(v, key=lambda x: x["value"])
                detail.append({"id": k, "title": v[0]["title"], "value": round(agg, 3), "mean": round(sum(x["value"] for x in v) / len(v), 3), "n": len(v), "weight": w,
                               "evidence": v[0]["evidence"], "worst": worst.get("screen") or worst.get("journey"), "worst_viewport": worst.get("viewport")})
            s = num / den
            ev = {}
            for m in ms: ev[m["evidence"]] = ev.get(m["evidence"], 0) + 1
            out[area] = {"category": cat, "title": title, "points": pts, "score": round(s, 4), "awarded": round(pts * s, 1), "metrics": len(ms),
                         "samples": sum(m["samples"] for m in ms), "evidence": ev, "detail": sorted(detail, key=lambda d: d["value"])}
    return out


def categories(areas, context):
    cats = {}
    for cat, spec in CATEGORIES.items():
        scored = [a for a in spec["areas"] if areas[a]["score"] is not None]
        pts = sum(areas[a]["points"] for a in scored)
        score = round(100 * sum(areas[a]["points"] * areas[a]["score"] for a in scored) / pts, 1) if pts else None
        cats[cat] = {"title": spec["title"], "score": score, "coverage": round(pts / 100, 2), "untested": [areas[a]["title"] for a in spec["areas"] if a not in scored],
                     "areas": {a: areas[a] for a in spec["areas"]}}
    scored = [c["score"] for c in cats.values() if c["score"] is not None]
    overall = round(sum(scored) / len(scored), 1) if scored else None
    cov = round(sum(c["coverage"] for c in cats.values()) / 3, 2)
    conf, why = confidence(cov, context)
    return cats, {"score": overall, "coverage": cov, "confidence": conf, "confidence_reasons": why, "grade": grade(overall)}


def confidence(coverage, ctx):
    why = []
    if coverage < 0.7: why.append(f"only {round(coverage * 100)}% of the rubric had evidence")
    if ctx.get("screens", 0) < 2: why.append("one screen audited")
    if ctx.get("viewports", 0) < 3: why.append("fewer than three viewports")
    if not ctx.get("journeys"): why.append("no user journeys ran")
    elif ctx.get("auto_journeys_only"): why.append("only automatic journeys (no task-specific journeys with expected taps)")
    if not ctx.get("axe"): why.append("axe-core did not run")
    if ctx.get("canvas_heavy"): why.append("canvas-rendered screens: the DOM does not describe what is drawn")
    why.append("browser emulation only (no physical-device evidence)" if not ctx.get("physical") else "physical-device evidence attached")
    hard = [w for w in why if not w.startswith("browser emulation") and not w.startswith("physical") and not w.startswith("only automatic")]
    level = "high" if coverage >= 0.9 and not hard else ("medium" if coverage >= 0.7 and len(hard) <= 1 else "low")
    return level, why


def grade(s):
    if s is None: return "not tested"
    return "excellent" if s >= 90 else "good" if s >= 80 else "fair" if s >= 65 else "weak" if s >= 50 else "poor"


def prioritise(findings, n_captures):
    """Rank by user impact x frequency / cost; verified evidence first among equals."""
    out = []
    for f in findings.values():
        places = {(o.get("screen"), o.get("viewport")) for o in f["occurrences"]} or {("?", "?")}
        f["frequency"] = len(places)
        f["screens"] = sorted({str(p[0]) for p in places}); f["viewports"] = sorted({str(p[1]) for p in places})
        reach = min(1.0, f["frequency"] / max(1, n_captures))
        f["priority"] = round(f["impact"] * (1 + math.log2(f["frequency"])) * (1 + reach) / (0.6 + 0.4 * f["cost"]), 2)
        f["tier"] = "fix now" if f["severity"] == "critical" or f["priority"] >= 9 else "next" if f["priority"] >= 4.5 else "polish"
        out.append(f)
    return sorted(out, key=lambda f: (-f["priority"], f["id"]))


def screen_scores(metrics):
    """Per screen: the mean of its visual/usability metrics (strongest and weakest screens)."""
    by = {}
    for m in metrics:
        if m.get("screen") and AREA_CATEGORY.get(m["area"]) in ("visual", "usability"):
            by.setdefault(m["screen"], []).append(m["value"])
    return sorted(({"screen": s, "score": round(100 * sum(v) / len(v), 1), "metrics": len(v)} for s, v in by.items()), key=lambda x: -x["score"])
