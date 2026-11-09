"""QUALITY GATES: whether a task's result is good enough for dependent work to start.

A department returning `ok` makes a task `complete`; the gate decides `passed`. Gate conditions:

  status_ok             the department's own status is ok (its outputs validated by format, its checks passed)
  min {path, min}       a measured number in the result (e.g. PLAYCRAFT summary.overall.score) is at least min;
                        a missing measurement fails (never assumed)
  referenced            every asset integrated into the project is referenced by the project's source
  expected              (agent) every expected file exists inside the roots and opens as its format
  changed               (fix) the project's files differ from what the failed check measured
  advisory              recorded, never blocks (DESIGNCRAFT's design review)

classify() separates a quality failure (the department ran and measured a problem: remediate) from an
execution failure (crash/timeout: retry) and a request failure (bad parameters: fix the plan, never retry)."""
import json, os, re
from . import executors


SOURCE_ROLES = {"icon_master", "icon_native", "model_source"}   # kept in the project, not referenced by the web build (a model's .blend, previews, record)


def get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d: return None
        d = d[k]
    return d


def classify(res):
    s = res.get("status")
    if s == "ok": return "ok"
    if s == "blocked": return "blocked"
    if res.get("failure") in ("request",): return "request"
    if res.get("failure") in ("timeout", "crash"): return "execution"
    if any(not c.get("ok") for c in res.get("checks", [])) and res.get("outputs"): return "quality"
    return "execution"


def evaluate(task, res, ctx):
    """[{condition, ok, detail}] for every gate condition (empty gate = status_ok for department tasks)."""
    out = []
    for g in task.get("gate") or []:
        ty = g["type"]
        if ty == "status_ok":
            bad = [c["name"] + (f" ({str(c.get('detail'))[:160]})" if c.get("detail") not in (None, "", [], {}) else "") for c in res.get("checks", []) if not c.get("ok")]
            out.append({"condition": "the department reports ok (outputs validated, its checks passed)", "ok": res.get("status") == "ok",
                        "detail": res.get("error") or (bad[:8] if bad else None)})
        elif ty == "min":
            v = get(res, g["path"])
            ok = isinstance(v, (int, float)) and v >= g["min"]
            out.append({"condition": f"{g.get('label', g['path'])} ≥ {g['min']}", "ok": ok, "measured": v,
                        "detail": None if ok else ("not measured" if v is None else f"measured {v}")})
        elif ty == "referenced":
            man = ctx.get("integrated") or []
            src = _source_text(ctx["project"])
            # an icon master is preserved source artwork (the derivatives are what the build references)
            missing = [m["dest_rel"] for m in man if m.get("role") not in SOURCE_ROLES and os.path.basename(m["dest_rel"]) not in src]
            out.append({"condition": "every integrated asset is referenced by the build", "ok": not missing, "detail": missing[:20] or None,
                        "measured": f"{len(man) - len(missing)}/{len(man)} referenced"})
        elif ty == "advisory":
            out.append({"condition": "advisory (recorded, does not block)", "ok": True})
    return out


def _source_text(project):
    buf = []
    for d, dirs, files in os.walk(project):
        dirs[:] = [x for x in dirs if x not in (".git", "node_modules")]
        for f in files:
            if f.endswith((".js", ".mjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".webmanifest", ".vue", ".svelte")) and "assets" not in os.path.relpath(d, project).split(os.sep)[:2]:
                try: buf.append(open(os.path.join(d, f), errors="ignore").read(2_000_000))
                except OSError: pass
    return "\n".join(buf)


def check_expected(expected, base, project, roots_ok):
    """Agent submissions: each expected file exists, is inside the roots, and opens as its format."""
    res, outs = [], []
    for e in expected:
        p = e["path"].replace("$project", project or "")
        p = p if os.path.isabs(p) else os.path.join(base, p)
        if not roots_ok(p):
            res.append({"name": f"{e['path']} is inside the workspace roots", "ok": False, "detail": p}); continue
        v = executors.validate_file(p, e.get("format"))
        ok = v.get("ok", False)
        if ok and e.get("keys"):
            try:
                data = json.load(open(p)); miss = [k for k in e["keys"] if k not in data]
                if miss: ok, v = False, {"ok": False, "error": f"missing keys {miss}"}
            except ValueError as ex: ok, v = False, {"ok": False, "error": str(ex)}
        res.append({"name": f"{e['path']} exists and opens as {e.get('format') or v.get('format')}", "ok": ok, "detail": v.get("error") or v.get("note")})
        if ok and e.get("validate"):   # a content check beyond the format (e.g. the icon concepts, the 1024 master)
            from . import icons
            extra = icons.VALIDATORS[e["validate"]](p, base)
            res += extra; ok = all(c["ok"] for c in extra)
        if ok: outs.append({"path": p, "role": e.get("role") or os.path.splitext(os.path.basename(p))[0], "format": v.get("format"), "ok": True})
    return res, outs


# ---------------------------------------------------------------- remediation: what a failed QA gate asks to be fixed
def _pixel_item(f):
    """A PIXELCRAFT finding as one readable instruction (it arrives as a dict: title, severity, frequency, evidence, fix)."""
    if not isinstance(f, dict): return f"PIXELCRAFT finding: {f}"
    ev = f.get("evidence")
    if isinstance(ev, dict): ev = ", ".join(f"{k} {v}" for k, v in list(ev.items())[:4] if not isinstance(v, (dict, list)))
    elif isinstance(ev, list): ev = "; ".join(str(x) for x in ev[:3])
    head = ", ".join(str(x) for x in (f.get("severity"), f.get("frequency")) if x)
    return (f"PIXELCRAFT finding ({head}): {f.get('title')}" if head else f"PIXELCRAFT finding: {f.get('title')}") \
        + (f" (evidence: {str(ev)[:200]})" if ev else "") + (f". Fix: {f['fix']}" if f.get("fix") else "")


def remediation(task, res, gate_results, design=None):
    """The findings a fix work order carries. `design`: DESIGNCRAFT's proposals for the same game (its review is
    advisory and never blocks, so its findings reach the agent through the gameplay fix instead of being dropped)."""
    items = []
    for g in gate_results:
        if not g["ok"] and g.get("detail"):
            d = g["detail"]
            items += [f"{g['condition']}: {x}" for x in d] if isinstance(d, list) else [f"{g['condition']}: {d}"]
    dept = task.get("department")
    if dept == "playcraft":
        items += [f"PLAYCRAFT plan: {x}" for x in (res.get("plan") or [])[:5]]
        items += [f"PLAYCRAFT finding: {x}" for x in (get(res, "summary.top_findings") or [])[:6]]
        items += [f"DESIGNCRAFT proposal ({p.get('priority') or 'unranked'}): {p.get('title')}" for p in (design or [])[:5] if p.get("title")]
    elif dept == "pixelcraft":
        items += [_pixel_item(x) for x in (get(res, "summary.top_findings") or [])[:8]]
        r = get(res, "summary.overall.confidence_reasons")
        if r: items.append("PIXELCRAFT coverage: " + "; ".join(r[:4]))
    if res.get("record"): items.append(f"evidence: {res['record']}")
    seen, out = set(), []
    for i in items:
        if i not in seen: seen.add(i); out.append(i)
    return out[:20] or [res.get("error") or "the gate failed; see the task's result"]
