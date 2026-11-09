"""LAYERED QA: whether the work was done, whether it fits together, and whether the product is what was asked for.

Three layers, each a view over checks the production already runs (plus the two checks plan v2 adds). Nothing here
routes, retries or decides a verdict: failures go through the engine's one remediation path (planner criteria,
optionality, the owning department, DEPARTMENT_ROUNDS / max_rounds, escalation) and the verdict stays
report.verdict() over the acceptance criteria.

  department    each deliverable checked by its own department before hand-off: the department's own checks
                (status_ok) and, in plan v2, `deliverables` (the files integration will ship exist and validate).
                A failure goes back to that department.
  integration   the assembled product: transactional integration, the final manifest, every integrated asset opens and
                is referenced (qa.assets), licences, the app icon wired in, the build loads with no missing file
                (qa.smoke). A defective department file goes to that department; wiring is the agent's.
  product       the finished product against the request: qa.request (below), feature checks, PIXELCRAFT, PLAYCRAFT,
                DESIGNCRAFT, performance, the engineering standard, preservation, attribution, the final regression.

qa.request (plan v2, builtin check_request) reads the project's source, never runs it, and makes no model call:
  objective     the entry page exists and names the product; every requested feature that has a necessary, machine-
                checkable signal shows it (requested sound → the build plays audio; requested accounts → a sign-in
                surface; mobile → a viewport, and touch or pointer input in a game; accessibility → a page language and
                alt text on every image). A missing signal is a BLOCKER (a missing requested feature).
  advisory      unrequested additions (audio nobody asked for, a password field in an app without accounts) and
                coherence suggestions (the product's name on its page, the identity palette in the styles, leftover
                TODO / lorem ipsum text). Taste is never a blocker: these are listed, routed nowhere, never block READY.

findings(prod) is the structured list the reports show: layer, criterion, required, severity, owner, routed to,
evidence, resolution status and retry / escalation status."""
import json, os, re
from . import gates, verification as V

LAYERS = ("department", "integration", "product")
LABEL = {"department": "Department QA", "integration": "Integration QA", "product": "Product QA"}
INTEGRATION = {"qa.smoke", "qa.assets", "qa.licences", "qa.icons", "integrate.assets", "integrate.final"}
PRODUCT = {"qa.request", "qa.features", "qa.pixelcraft", "qa.playcraft", "qa.designcraft", "qa.perf", "qa.standards", "qa.preserve",
           "qa.attribution", "release.regression"}
NOT_QA = {"release.report", "release.deploy"}   # the verdict and the deployment have their own sections


def root(t):
    """The task a chain started from: a re-verification, a department rework and a re-integration report under it."""
    return t.get("reintegrates") or t.get("rework_of") or t.get("chain") or t["id"]


def layer_of(t):
    """department | integration | product, or None (a fix work order, an escalation, the release report, the deployment)."""
    if t.get("fix_for") or t.get("escalates") or t.get("action") == "escalate": return None
    r = root(t)
    if r in NOT_QA: return None
    if r in INTEGRATION or r.startswith("integrate."): return "integration"
    if r in PRODUCT: return "product"
    return "department"


# ---------------------------------------------------------------- Product QA: the finished product against the request
SIGNALS = {
    "sound": ("the build plays audio (Audio, AudioContext or an <audio> element)", re.compile(r"new\s+Audio\s*\(|AudioContext|<audio\b|\bHowl\s*\(|createBufferSource", re.I)),
    "accounts": ("the build has a sign-in surface (a password field or a sign-in call)", re.compile(r"type\s*=\s*[\"']?password|sign[-_ ]?in|log[-_ ]?in|\bauth[A-Za-z]*\s*\(", re.I)),
    "password": ("a password field", re.compile(r"type\s*=\s*[\"']?password", re.I)),
    "viewport": ("a mobile viewport is declared", re.compile(r"<meta[^>]+name\s*=\s*[\"']?viewport", re.I)),
    "touch": ("touch or pointer input is handled", re.compile(r"touchstart|touchend|pointerdown|pointerup|onpointer|ontouch|PointerEvent|TouchEvent", re.I)),
    "lang": ("the page declares its language (<html lang>)", re.compile(r"<html[^>]*\blang\s*=", re.I)),
}
UNFINISHED = re.compile(r"lorem ipsum|\bTODO\b|\bFIXME\b", re.I)


def requested(spec):
    """What the person asked for that the product itself must show (and only what was stated: an extra GITCRAFT implied, a
    person may make optional, so it is never a request here). Deterministic: from the parsed spec, never a model."""
    f, assum = spec.get("features") or {}, " ".join(spec.get("assumptions") or [])
    out = []
    if f.get("music") or f.get("voice") or (f.get("sound") and "'polished' game: sound effects included" not in assum): out.append("sound")
    if f.get("backend"): out.append("accounts")
    if (spec.get("platform") or {}).get("mobile_stated"): out.append("mobile")
    if f.get("accessibility"): out.append("accessibility")
    return out


def params_for(spec):
    a = spec.get("assets") or {}
    return {"title": spec.get("title"), "deliverable": spec.get("deliverable"), "requested": requested(spec),
            "sound_planned": bool(a.get("sfx") or a.get("music") or a.get("voice") or a.get("ambience")),
            "identity": bool(a.get("identity")), "entry": (spec.get("project") or {}).get("entry") or "index.html"}


def _read(p, n=2_000_000):
    try: return open(p, errors="ignore").read(n)
    except OSError: return None


def evaluate_request(project, p, integrated=()):
    """[categorised check] for the request matrix (pure: the builtin and the tests call this)."""
    checks = []
    entry = os.path.join(project, p.get("entry") or "index.html")
    html = _read(entry)
    checks.append(V.make("request: the entry page exists", V.PASS if html is not None else V.BLOCKER, None if html is not None else f"no {p.get('entry') or 'index.html'}",
                         kind="objective", feature="deliverable"))
    if html is None: return checks
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    named = bool(m and m.group(1).strip())
    checks.append(V.make("request: the entry page names the product (<title>)", V.PASS if named else V.BLOCKER, None if named else "empty or missing <title>",
                         kind="objective", feature="deliverable"))
    src = gates._source_text(project, strict=True)
    has = lambda k: bool(SIGNALS[k][1].search(src))
    want = set(p.get("requested") or [])

    def need(feature, key, label=None):
        ok = has(key)
        checks.append(V.make(f"requested {feature}: {label or SIGNALS[key][0]}", V.PASS if ok else V.BLOCKER,
                             None if ok else f"missing requested feature: {feature} (no sign of it in the build's code)", kind="objective", feature=feature, signal=key))
    if "sound" in want: need("sound", "sound")
    if "accounts" in want: need("accounts", "accounts")
    if "mobile" in want:
        need("mobile", "viewport")
        if p.get("deliverable") == "game": need("mobile", "touch", "touch or pointer controls are handled")
    if "accessibility" in want:
        need("accessibility", "lang")
        imgs = re.findall(r"<img\b[^>]*>", src, re.I)
        bare = [i[:80] for i in imgs if not re.search(r"\balt\s*=", i, re.I)]
        checks.append(V.make("requested accessibility: every image has alt text", V.BLOCKER if bare else V.PASS, bare[:5] or None, kind="objective", feature="accessibility"))
    # unrequested additions: listed for a person, never a blocker
    if "sound" not in want and not p.get("sound_planned") and has("sound"):
        checks.append(V.make("unrequested addition: the build plays audio, which was not asked for", V.ADVISORY, "keep it, or remove it if it was not wanted", kind="unrequested"))
    if "accounts" not in want and has("password"):
        checks.append(V.make("unrequested addition: a password field, but accounts were not asked for", V.ADVISORY,
                             "collecting credentials needs the accounts decision (backend) or should be removed", kind="unrequested"))
    # coherence: suggestions, never blockers
    title = (p.get("title") or "").strip()
    if title and title.lower() not in html.lower():
        checks.append(V.make("coherence: the product's name is on its entry page", V.ADVISORY, f"'{title}' does not appear in {p.get('entry') or 'index.html'}", kind="suggestion"))
    if p.get("identity"):
        pal = next((m_ for m_ in integrated or () if os.path.basename(m_.get("dest_rel") or "") == "palette.json"), None)
        cols = []
        if pal:
            try: cols = [v.lower() for v in json.load(open(pal.get("dest") or os.path.join(project, pal["dest_rel"]))).values() if isinstance(v, str) and v.startswith("#")]
            except (OSError, ValueError, AttributeError): cols = []
        if cols and not any(c in src.lower() for c in cols):
            checks.append(V.make("coherence: the identity palette is used by the styles", V.ADVISORY, f"none of {', '.join(cols[:4])} appears in the build's code", kind="suggestion"))
    left = sorted(set(x.group(0) for x in UNFINISHED.finditer(gates._strip_comments(html))))
    if left: checks.append(V.make("coherence: no unfinished text on the entry page", V.ADVISORY, left[:4], kind="suggestion"))
    return checks


def check_request(ctx):
    """Builtin (qa.request): the request matrix as a measured check with its evidence file."""
    from . import builtins
    checks = evaluate_request(ctx["project"], ctx["params"], ctx.get("integrated") or [])
    st = V.status_of(checks)
    r = {"status": "ok" if st == "ok" else "failed", "checks": checks, "requested": ctx["params"].get("requested") or [],
         "summary": V.summary(checks)}
    return builtins._with_report(ctx, r, "request.json")


# ---------------------------------------------------------------- the structured findings every report shows
def _eff(prod, tid):
    t = prod["tasks"][tid]; seen = set()
    while t.get("superseded_by") and t["id"] not in seen: seen.add(t["id"]); t = prod["tasks"][t["superseded_by"]]
    return t


def _evidence(t):
    ev = [f"{g['condition']}: " + str(g.get("detail") if g.get("detail") not in (None, "", []) else g.get("measured"))[:220] for g in t.get("gate_results") or [] if not g["ok"]]
    if not ev and (t.get("error") or t.get("reason")): ev.append(str(t.get("error") or t.get("reason"))[:300])
    rec = (t.get("result") or {}).get("record")
    if rec: ev.append(f"record: {rec}")
    return ev[:6]


def findings(prod):
    """[{layer, task, latest, criterion, required, severity, owner, routed_to, evidence, status, retry}], deterministic (plan order)."""
    spec = prod.get("spec") or {}
    req = {c["id"]: c.get("required", True) for c in spec.get("acceptance") or []}
    maxr = (spec.get("quality") or {}).get("max_rounds", 2)
    from .engine import DEPARTMENT_ROUNDS
    chains = {}
    for tid in prod.get("order") or []:
        t = prod["tasks"][tid]
        if layer_of(t) is None: continue
        chains.setdefault(root(t), []).append(t)
    esc = {t.get("origin"): t for t in prod["tasks"].values() if t.get("escalates")}
    esc_by_task = {t["escalates"]: t for t in prod["tasks"].values() if t.get("escalates")}
    out = []
    for r, ts in chains.items():
        base = prod["tasks"].get(r) or ts[0]
        lay = layer_of(base)
        bad = [t for t in ts if t["state"] == "failed" or t["state"] == "blocked" and not t.get("blocked_by")]
        advisory_checks = [c for t in ts[-1:] for c in ((t.get("result") or {}).get("checks") or []) if c.get("category") == V.ADVISORY]
        latest = _eff(prod, r) if r in prod["tasks"] else ts[-1]
        crit = base.get("criterion") or latest.get("criterion")
        required = req.get(crit, True) if crit else True
        if bad:
            last = bad[-1]
            routed = next((t.get("routed") for t in reversed(ts) if t.get("routed")), None) or {}
            dept_rounds = sum(1 for t in ts if t.get("rework_of"))
            qa_rounds = max([t.get("round") or 0 for t in ts if t.get("reverifies") and not t.get("rework_of")] or [0])
            to = routed.get("to") or []
            limit = DEPARTMENT_ROUNDS if to and to != ["agent"] else maxr
            rounds = dept_rounds or qa_rounds
            e = esc_by_task.get(r) or next((esc[x["id"]] for x in ts if x["id"] in esc), None) \
                or next((esc_by_task[p] for p in routed.get("producers") or [] if p in esc_by_task), None)
            if latest["state"] == "passed": status = f"resolved (round {rounds})" if rounds else "resolved"
            elif e and e["state"] == "needs_approval": status = "escalated: waiting for a person"
            elif e and e["state"] == "skipped": status = "declined by a person: stays failed"
            elif latest["state"] == "blocked" and latest.get("unavailable"): status = "unavailable here (a capability is missing; not a defect)"
            elif latest["state"] == "blocked" and latest.get("unverified"): status = "unverified (could not be completed; not a defect)"
            elif crit and not required and latest["state"] in ("failed", "blocked", "skipped"): status = "not delivered (optional)"
            elif latest["state"] in ("failed", "blocked"): status = "open" + (": retries exhausted" if latest.get("exhausted") or rounds >= limit else "")
            else: status = f"being fixed (round {rounds or 1})"
            if base.get("advisory") or latest.get("advisory"): sev = "advisory"
            elif crit and not required: sev = "optional"
            elif last["state"] == "blocked": sev = "incomplete"
            else: sev = "blocker"
            retry = ("escalated to a person" if e else f"{rounds}/{limit} re-run(s)" + (" — exhausted" if rounds >= limit and latest["state"] != "passed" else "")) \
                if (rounds or to or e) else "no re-run (" + ("advisory" if sev == "advisory" else "not a defect" if sev == "incomplete" else "review only" if (spec.get("mode") or {}).get("workflow") == "review" else "not routed") + ")"
            out.append({"layer": lay, "task": r, "latest": latest["id"], "criterion": crit, "required": required, "severity": sev, "kind": "defect" if sev in ("blocker", "optional") else sev,
                        "owner": base.get("owner"), "routed_to": ", ".join(to) or None, "evidence": _evidence(last), "status": status, "retry": retry})
        for c in advisory_checks:   # suggestions and unrequested additions: listed, never routed, never blocking
            out.append({"layer": lay, "task": r, "latest": ts[-1]["id"], "criterion": crit, "required": False, "severity": "advisory", "kind": c.get("kind") or "suggestion",
                        "owner": base.get("owner"), "routed_to": None, "evidence": [f"{c['name']}: {str(c.get('detail'))[:200]}" if c.get("detail") else c["name"]],
                        "status": "listed (advisory)", "retry": "never re-run (not a defect)"})
    return out


def layers(prod):
    """{layer: {status, checks, passed, open}}: passed | failed | incomplete | pending | not run. Advisory and optional work never fail a layer."""
    spec = prod.get("spec") or {}
    req = {c["id"]: c.get("required", True) for c in spec.get("acceptance") or []}
    roots = {}
    for tid in prod.get("order") or []:
        t = prod["tasks"][tid]
        lay = layer_of(t)
        if lay and root(t) == tid: roots.setdefault(lay, []).append(_eff(prod, tid))
    F = findings(prod)
    out = {}
    for lay in LAYERS:
        ts = roots.get(lay) or []
        hard = [t for t in ts if not t.get("advisory") and not t.get("optional") and (not t.get("criterion") or req.get(t["criterion"], True))]
        # a check that failed and is being fixed reads failed until its re-verification passes (not "pending")
        st = ["failed" if t["state"] not in ("passed", "skipped", "blocked", "needs_approval") and prod["tasks"][root(t)]["state"] == "failed" else t["state"] for t in hard]
        if not ts: s = "not run"
        elif any(x == "failed" for x in st): s = "failed"
        elif all(x in ("passed", "skipped") for x in st): s = "passed"
        elif any(x == "blocked" or x == "needs_approval" for x in st): s = "incomplete"
        else: s = "pending"
        out[lay] = {"status": s, "checks": len(ts), "passed": sum(1 for t in ts if t["state"] == "passed"),
                    "open": sum(1 for f in F if f["layer"] == lay and f["severity"] in ("blocker", "incomplete") and not f["status"].startswith("resolved"))}
    return out


def assurance(prod):
    """Built vs verified, in one line: a build that completed is not yet a product that was verified."""
    L = layers(prod)
    built = L["department"]["status"] == "passed"   # every deliverable, the code build and its wiring included, passed its own QA
    verified = all(L[x]["status"] in ("passed", "not run") for x in LAYERS) and L["product"]["status"] == "passed"
    if verified and built: line = "BUILT · PRODUCT VERIFIED"
    elif built: line = "BUILT · NOT VERIFIED (" + ", ".join(f"{LABEL[x]} {L[x]['status']}" for x in LAYERS if L[x]["status"] not in ("passed", "not run")) + ")"
    else: line = "NOT BUILT (" + ", ".join(f"{LABEL[x]} {L[x]['status']}" for x in LAYERS if L[x]["status"] not in ("passed", "not run")) + ")"
    return {"built": built, "verified": verified and built, "line": line, "layers": L}


def markdown(prod):
    A = assurance(prod); F = findings(prod)
    if not any(v["checks"] for v in A["layers"].values()): return []
    L = ["## Quality assurance (three layers)", "", f"**{A['line']}** — the verdict is the acceptance criteria's; this explains it.", "",
         "| Layer | Status | Checks passed | Open |", "|---|---|---|---|"]
    for x in LAYERS:
        v = A["layers"][x]; L.append(f"| {LABEL[x]} | **{v['status']}** | {v['passed']}/{v['checks']} | {v['open']} |")
    L.append("")
    if F:
        L += ["| Layer | Criterion | Severity | Owner | Routed to | Evidence | Resolution | Retry / escalation |", "|---|---|---|---|---|---|---|---|"]
        for f in F[:60]:
            ev = "; ".join(f["evidence"])[:240].replace("|", "/").replace("\n", " ")
            L.append(f"| {LABEL[f['layer']]} | {f['criterion'] or '—'}{'' if f['required'] else ' (optional)'} | {f['severity']} | {f['owner']} | {f['routed_to'] or '—'} | "
                     f"{ev or '—'} | {f['status']} | {f['retry']} |")
        L.append("")
    return L
