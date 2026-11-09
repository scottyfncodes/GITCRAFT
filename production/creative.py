"""Creative Review: an advisory, evidence-cited judgement of a product against its vision, kept apart from every
score, gate, verdict and plan.

  pack(project, captures)   index the evidence that already exists (department screenshots, play frames, probe metrics,
                            department findings), each with an id and a SHA-256; write pack.json + BRIEF.md (no model call)
  submit(pack, review)      validate a review written by the agent against the pack and the rules below; store it
  for_report(P)             the latest review for a project with its status (current / stale / unverified)

The judgement itself is done only when someone explicitly asks for it (the `creative-review` skill): a Production
Report never triggers one. Separation rules (tests/test_creative.py holds them):
  1. No score: a review carries no number; any score/rating/points key is refused. Nothing here touches
     scoring.RUBRICS, the overall score, band or confidence.
  2. Not a gate: it never changes an acceptance criterion or the Director's verdict, and never becomes a work order.
  3. Not in the plan: creative findings stay out of P0–P3 and the technical top three.
  4. Labelled: every claim has a basis (observed_render, observed_interaction, source_analysis, hypothesis_playtest).
     "Observed" needs a captured screenshot, frame or probe metric from the pack. Claims that something is fun or
     engaging are hypotheses for a human playtest, never observations.
  5. No deltas or trends: reviews are never compared or charted; each is bound to a commit, a vision version and its
     evidence fingerprints, and is stale once any of them changes.
  6. Wording: "assessment against the vision", never "verdict".
"""
import datetime, glob, hashlib, json, os, re, shutil
from . import REPO, roots, vision

METHOD = "creative-review/1"
TIERS = ("transformative", "substantial", "polish")
BASES = {"observed_render": "Observed in a rendered screen", "observed_interaction": "Observed in automated play",
         "source_analysis": "From source and design data", "hypothesis_playtest": "Hypothesis: needs a human playtest"}
APPROVAL_AREAS = {"mechanic", "identity", "scope", "vision", "audience", "monetisation"}
MAX_POLISH, MAX_OPPORTUNITIES = 5, 12
# claims about how play feels: only ever a playtest hypothesis (screenshots and probe metrics cannot show fun)
FEEL = re.compile(r"\b(fun|engag\w*|enjoy\w*|satisf\w*|addict\w*|compelling|delight\w*|boring|tedious|exciting|thrill\w*|immersive|rewarding|frustrat\w*)\b", re.I)
IMG = (".png", ".jpg", ".jpeg", ".webp")
SCORE_KEYS = re.compile(r"^(score|scores|rating|ratings|points|grade|stars)$", re.I)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def _json(p, d=None):
    try: return json.load(open(p))
    except (OSError, ValueError): return d


def write_root():
    if os.environ.get("GITCRAFT_CREATIVE_DIR"): return os.path.realpath(os.environ["GITCRAFT_CREATIVE_DIR"])
    if os.path.isdir(os.path.join(REPO, ".git")): return os.path.join(REPO, "history", "creative")
    return os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "creative")


def read_roots():
    if os.environ.get("GITCRAFT_CREATIVE_DIR"): return [write_root()]
    return list(dict.fromkeys([write_root(), os.path.join(REPO, "history", "creative"),
                               os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "creative")]))


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


# ---------------------------------------------------------------- the evidence pack (no model call, no new capture)
def _capture_kind(d):
    """Which department wrote a capture folder, from the files it always writes."""
    if os.path.isfile(os.path.join(d, "audit.json")): return "pixelcraft"
    if glob.glob(os.path.join(d, "playcraft*.json")) or os.path.isfile(os.path.join(d, "play", "play.json")) or os.path.isfile(os.path.join(d, "play.json")): return "playcraft"
    return None


def _capture_commit(d, kind):
    if kind == "pixelcraft": return (((_json(os.path.join(d, "audit.json"), {}) or {}).get("app") or {}).get("git") or {}).get("head")
    for p in [os.path.join(d, "playcraft.json")] + glob.glob(os.path.join(d, "*", "playcraft.json")):
        J = _json(p, {}) or {}
        c = J.get("git") or J.get("commit") or {}
        if c: return c.get("head") if isinstance(c, dict) else c
    return None


def _play_metrics(d):
    out = {}
    for p in [os.path.join(d, "play", "play.json"), os.path.join(d, "play.json")]:
        J = _json(p)
        if not J: continue
        for k, v in (J.get("metrics") or {}).items():
            if isinstance(v, (int, float, str, bool)) or v is None: out[k] = v
        for vp in J.get("viewports") or []:
            for k, v in (vp.get("metrics") or {}).items():
                if isinstance(v, (int, float, str, bool)): out[f"{vp.get('name', 'vp')}.{k}"] = v
        break
    return out


def pack(project, captures, out_dir=None, max_images=60):
    """Index existing department captures and findings into an evidence pack. Returns the pack dict."""
    from . import project_report
    P = project_report.resolve(project)
    if not P["id"]: raise ValueError("which project? give its folder, GitHub owner/repo or history id")
    V = vision.latest(P["id"])
    if not V: raise ValueError(f"no vision for {P['id']}: draft one first (production_vision action=draft); a draft is enough to review against")
    items, warnings = [], []
    for d in captures or []:
        d = os.path.realpath(d)
        kind = _capture_kind(d)
        if not kind: warnings.append(f"{d}: not a PLAYCRAFT or PIXELCRAFT output folder (skipped)"); continue
        commit = _capture_commit(d, kind)
        if P.get("head") and commit and not P["head"].startswith(commit[:7]) and not str(commit).startswith(P["head"][:7]):
            warnings.append(f"{kind} capture was made on {str(commit)[:7]}, the project is at {P['head'][:7]}: a review on it is stale from the start")
        imgs = []
        for root, ds, fs in os.walk(d):
            ds[:] = [x for x in ds if x not in ("diff", "refresh")]
            for f in sorted(fs):
                if f.lower().endswith(IMG): imgs.append(os.path.join(root, f))
        for p in sorted(imgs)[:max_images]:
            rel = os.path.relpath(p, d)
            items.append({"id": f"{'shot' if kind == 'pixelcraft' else 'frame'}:{kind}/{os.path.splitext(rel)[0]}",
                          "kind": "screenshot" if kind == "pixelcraft" else "play_frame", "department": kind, "path": p, "sha256": _sha(p),
                          "bytes": os.path.getsize(p), "commit": commit})
        if len(imgs) > max_images: warnings.append(f"{kind}: {len(imgs)} images, the first {max_images} indexed")
        # the capture's own findings (so the review builds on them instead of repeating them)
        src = _json(os.path.join(d, "audit.json" if kind == "pixelcraft" else "playcraft.json"), {}) or {}
        for f in src.get("findings") or []:
            if kind == "playcraft" and f.get("status") not in ("fail", "partial"): continue
            lvl = str(f.get("level") or f.get("evidence") or "")
            items.append({"id": f"finding:{kind}-capture:{f.get('id')}", "kind": "measured_finding" if lvl in ("verified", "observed", "measured", "accessibility") else "source_finding",
                          "department": kind, "title": f.get("title"), "level": lvl, "severity": f.get("severity") or f.get("type"),
                          "evidence": (f.get("evidence") if kind == "playcraft" else f.get("explanation")), "commit": commit,
                          "sha256": hashlib.sha256(json.dumps([kind, f.get("id"), f.get("title")]).encode()).hexdigest()})
        if kind == "playcraft":
            for k, v in _play_metrics(d).items():
                items.append({"id": f"metric:playcraft/{k}", "kind": "probe_metric", "department": "playcraft", "value": v, "commit": commit,
                              "sha256": hashlib.sha256(json.dumps([k, v]).encode()).hexdigest()})
    R = project_report.generate(P["path"] or P["id"], refresh="none", save="none")   # department findings as recorded (no re-measurement)
    for d in R["departments"]:
        for f in d["findings"]:
            items.append({"id": f"finding:{f['key']}", "kind": "measured_finding" if f["level"] in ("verified", "observed") else "source_finding",
                          "department": d["id"], "title": f["title"], "level": f["level"], "severity": f["severity"], "evidence": f.get("evidence"),
                          "sha256": hashlib.sha256(json.dumps([f["key"], f["title"], f.get("evidence")]).encode()).hexdigest()})
    kind = R["project"].get("kind")
    vs = vision.summary(V)
    fp = hashlib.sha256(json.dumps([P.get("head"), vs["version"], vs["sha256"], sorted(i["sha256"] for i in items)]).encode()).hexdigest()[:16]
    stamp = _now().strftime("%Y%m%dT%H%M%SZ")
    base = os.path.join(roots()[0], "gitcraft-out", "creative", P["id"])
    out, n = os.path.realpath(out_dir or os.path.join(base, stamp)), 1
    while not out_dir and os.path.exists(out): n += 1; out = os.path.realpath(os.path.join(base, f"{stamp}-{n}"))   # packs are never overwritten
    if P.get("path") and (out == P["path"] or out.startswith(P["path"] + os.sep)): raise PermissionError("the pack folder must be outside the project (read-only)")
    K = {"schema": "gitcraft-creative-pack/1", "method": METHOD, "project": {k: P.get(k) for k in ("id", "repo", "url", "name", "path", "head")}, "title": R["title"],
         "kind": kind, "vision": vs, "fingerprint": fp, "created": _now().isoformat(timespec="seconds"), "items": items, "warnings": warnings,
         "counts": {k: sum(1 for i in items if i["kind"] == k) for k in ("screenshot", "play_frame", "probe_metric", "measured_finding", "source_finding")}}
    os.makedirs(out, exist_ok=True)
    K["paths"] = {"dir": out, "pack": os.path.join(out, "pack.json"), "brief": os.path.join(out, "BRIEF.md")}
    with open(K["paths"]["pack"], "w") as f: json.dump(K, f, indent=1, default=str)
    with open(K["paths"]["brief"], "w") as f: f.write(brief(K))
    return K


def brief(K):
    """The reviewer's instructions: what to look at, the vision, the questions and the output schema."""
    vs = K["vision"]; game = K.get("kind") == "game"
    imgs = [i for i in K["items"] if i["kind"] in ("screenshot", "play_frame")]
    L = [f"# Creative Review brief — {K['title']}", "",
         f"Project `{K['project']['id']}` at `{(K['project'].get('head') or 'unknown')[:7]}` · pack `{K['fingerprint']}` · vision v{vs['version']} (**{vs['status']}**)", "",
         "This review is advisory and carries no score. It never changes a department score, the overall score, a release gate, the Director's verdict or the",
         "P0–P3 plan. Write it to a JSON file and submit it with `production_creative action=submit`.", "",
         "## The vision (a reference, not a constraint)", ""]
    L += [f"- `{k}`: {t}" for k, t in vs["clauses"].items()] or ["- (no clauses stated yet)"]
    if vs["status"] != "approved": L += ["", f"This vision is a **{vs['status']}**, not approved by a person: say so where it matters."]
    if vs["open_questions"]: L += ["", "Open questions: " + "; ".join(vs["open_questions"])]
    L += ["", "## Look at the evidence first", "", f"{len(imgs)} images. Open each one you cite (and list it in `coverage.viewed`). "
          "What you did not open, you did not see.", ""]
    L += [f"- `{i['id']}` — {i['path']}" for i in imgs[:80]]
    m = [i for i in K["items"] if i["kind"] == "probe_metric"]
    if m: L += ["", "Probe metrics (automated play, not a person): " + "; ".join(f"`{i['id']}` = {i['value']}" for i in m[:40])]
    L += ["", f"Department findings already in the Production Report ({sum(1 for i in K['items'] if i['id'].startswith('finding:'))}): cite them as context; do not repeat them as new opportunities.", ""]
    L += [f"- `{i['id']}` ({i['level']}, {i['severity']}): {i['title']}" for i in K["items"] if i["id"].startswith("finding:")][:60]
    L += ["", "## Questions", "", "1. Does the product deliver each vision clause? Where, and where not? (`vision_assessment`)",
          "2. What are the highest-impact opportunities, including ones beyond the stated vision? (`opportunities`; `beyond_vision: true` + `needs_approval: true` for those)",
          "3. What genuinely works, and must be protected? (`strengths`, with evidence)"]
    if game: L += ["4. Gameplay: separate what automated play observed, what the source and design data show, and what only a person playing can answer (`gameplay`)."]
    L += ["", "## Rules (the validator enforces them)", "",
          "- No scores, ratings or points anywhere.",
          "- Every claim has a `basis`: " + ", ".join(f"`{k}` ({v})" for k, v in BASES.items()) + ".",
          "- `observed_render` cites a screenshot or frame; `observed_interaction` cites a play frame or probe metric; `hypothesis_playtest` says how a playtest would check it (`playtest`).",
          "- Fun, engaging, satisfying, boring and similar are hypotheses for a playtest, never observations: screenshots and probe metrics cannot show them.",
          f"- Tiers: {', '.join(TIERS)}. At most {MAX_POLISH} polish items, {MAX_OPPORTUNITIES} opportunities in all. \"No transformative opportunity\" is a valid answer.",
          "- Anything that changes a mechanic, the identity, scope, audience or the vision itself needs `needs_approval: true`.",
          "- Strengths need evidence like weaknesses do. An empty list is allowed with `strengths_note`.", "",
          "## Schema", "", "```json", json.dumps(example(game), indent=1), "```", ""]
    return "\n".join(L)


def example(game=True):
    E = {"reviewer": "Claude Code session (model judgement)", "coverage": {"viewed": ["shot:pixelcraft/…"], "not_seen": "what was not captured"},
         "vision_assessment": {"summary": "two or three sentences", "delivers": [{"clause": "pillar:1", "assessment": "…", "evidence": ["shot:…"], "basis": "observed_render"}],
                               "gaps": [{"clause": "promise", "assessment": "…", "evidence": ["finding:…"], "basis": "source_analysis"}]},
         "opportunities": [{"tier": "substantial", "area": "onboarding", "title": "…", "observation": "…", "evidence": ["frame:…"], "basis": "observed_interaction",
                            "why_it_matters": "…", "recommendation": "…", "expected_improvement": "…", "effort": "M", "risk": "low", "confidence": "medium",
                            "needs_approval": False, "vision_clause": "pillar:2", "beyond_vision": False}],
         "strengths": [{"title": "…", "observation": "…", "evidence": ["shot:…"], "basis": "observed_render", "why_it_works": "…", "protect": "…"}]}
    if game: E["gameplay"] = {"observed": [{"claim": "…", "evidence": ["metric:playcraft/…"], "basis": "observed_interaction"}],
                              "source_based": [{"claim": "…", "evidence": ["finding:designcraft:…"], "basis": "source_analysis"}],
                              "hypotheses": [{"claim": "…", "evidence": [], "basis": "hypothesis_playtest", "playtest": "how a person would check it"}]}
    return E


# ---------------------------------------------------------------- validation
def _walk_keys(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{path}.{k}" if path else k, k
            yield from _walk_keys(v, f"{path}.{k}" if path else k)
    elif isinstance(o, list):
        for i, v in enumerate(o): yield from _walk_keys(v, f"{path}[{i}]")


def validate(review, K):
    """Every problem with a review against its pack, as a list of plain sentences (empty = valid)."""
    E = []
    ids = {i["id"]: i for i in K["items"]}
    clauses = K["vision"]["clauses"]
    game = K.get("kind") == "game"
    if not isinstance(review, dict): return ["the review must be a JSON object"]
    for p, k in _walk_keys(review):
        if SCORE_KEYS.match(str(k)): E.append(f"{p}: creative reviews carry no scores, ratings or points")
    viewed = set((review.get("coverage") or {}).get("viewed") or [])
    for v in viewed:
        if v not in ids: E.append(f"coverage.viewed: {v} is not in the pack")
    if not str(review.get("reviewer") or "").strip(): E.append("reviewer: say who made the judgement")

    def claim(where, c, text_keys, need_evidence=True):
        b = c.get("basis")
        if b not in BASES: E.append(f"{where}: basis must be one of {', '.join(BASES)}"); return
        ev = c.get("evidence") or []
        for e in ev:
            if e not in ids: E.append(f"{where}: evidence {e} is not in the pack")
        kinds = {ids[e]["kind"] for e in ev if e in ids}
        if b == "observed_render" and not kinds & {"screenshot", "play_frame"}: E.append(f"{where}: observed_render needs a cited screenshot or play frame")
        if b == "observed_interaction" and not kinds & {"play_frame", "probe_metric"}: E.append(f"{where}: observed_interaction needs a cited play frame or probe metric")
        if b in ("observed_render", "observed_interaction"):
            for e in ev:
                if e in ids and ids[e]["kind"] in ("screenshot", "play_frame") and e not in viewed: E.append(f"{where}: {e} is cited as seen but is not in coverage.viewed")
        if b != "hypothesis_playtest" and need_evidence and not ev: E.append(f"{where}: a {b} claim needs evidence from the pack")
        if b != "hypothesis_playtest":
            for k in text_keys:
                m = FEEL.search(str(c.get(k) or ""))
                if m: E.append(f"{where}.{k}: '{m.group(0)}' describes how play feels; that is a hypothesis for a human playtest (basis hypothesis_playtest), not an observation")

    va = review.get("vision_assessment") or {}
    if not str(va.get("summary") or "").strip(): E.append("vision_assessment.summary: say how well the product delivers its vision")
    if re.search(r"\bverdict\b", str(va.get("summary") or ""), re.I): E.append("vision_assessment.summary: say 'assessment', not 'verdict' (the Director's verdict is a release gate)")
    for part in ("delivers", "gaps"):
        for n, c in enumerate(va.get(part) or []):
            if c.get("clause") not in clauses: E.append(f"vision_assessment.{part}[{n}]: clause {c.get('clause')!r} is not in vision v{K['vision']['version']}")
            claim(f"vision_assessment.{part}[{n}]", c, ("assessment",))
    ops = review.get("opportunities") or []
    if len(ops) > MAX_OPPORTUNITIES: E.append(f"opportunities: at most {MAX_OPPORTUNITIES} (keep the ones that matter)")
    if sum(1 for o in ops if o.get("tier") == "polish") > MAX_POLISH: E.append(f"opportunities: at most {MAX_POLISH} polish items")
    for n, o in enumerate(ops):
        w = f"opportunities[{n}]"
        if o.get("tier") not in TIERS: E.append(f"{w}: tier must be one of {', '.join(TIERS)}")
        for k in ("title", "observation", "why_it_matters", "recommendation", "expected_improvement"):
            if not str(o.get(k) or "").strip(): E.append(f"{w}: {k} is required")
        if o.get("effort") not in ("S", "M", "L"): E.append(f"{w}: effort S, M or L")
        if o.get("risk") not in ("low", "medium", "high"): E.append(f"{w}: risk low, medium or high")
        if o.get("confidence") not in ("low", "medium", "high"): E.append(f"{w}: confidence low, medium or high")
        if o.get("beyond_vision"):
            if not o.get("needs_approval"): E.append(f"{w}: an opportunity beyond the vision is a proposal and needs needs_approval: true")
        elif o.get("vision_clause") not in clauses: E.append(f"{w}: vision_clause {o.get('vision_clause')!r} is not in the vision (or mark beyond_vision: true)")
        if str(o.get("area") or "").lower() in APPROVAL_AREAS and not o.get("needs_approval"): E.append(f"{w}: a change to {o.get('area')} needs needs_approval: true")
        if o.get("basis") == "hypothesis_playtest" and not str(o.get("playtest") or "").strip(): E.append(f"{w}: a hypothesis says how a playtest would check it (playtest)")
        claim(w, o, ("observation", "why_it_matters"))
    st = review.get("strengths")
    if not st and not str(review.get("strengths_note") or "").strip(): E.append("strengths: list what works (with evidence), or say why none is earned yet (strengths_note)")
    for n, s in enumerate(st or []):
        for k in ("title", "observation", "why_it_works"):
            if not str(s.get(k) or "").strip(): E.append(f"strengths[{n}]: {k} is required")
        if s.get("basis") == "hypothesis_playtest": E.append(f"strengths[{n}]: a strength is something shown by evidence; put a playtest hypothesis under gameplay.hypotheses")
        claim(f"strengths[{n}]", s, ("observation", "why_it_works"))
    G = review.get("gameplay")
    if game and not isinstance(G, dict): E.append("gameplay: required for a game (observed, source_based, hypotheses)")
    if not game and G: E.append("gameplay: this project does not read as a game; leave gameplay out")
    if isinstance(G, dict):
        want = {"observed": ("observed_interaction", "observed_render"), "source_based": ("source_analysis",), "hypotheses": ("hypothesis_playtest",)}
        for k in G:
            if k not in want: E.append(f"gameplay.{k}: sections are observed, source_based, hypotheses")
        for k, ok in want.items():
            for n, c in enumerate(G.get(k) or []):
                if c.get("basis") not in ok: E.append(f"gameplay.{k}[{n}]: basis must be {' or '.join(ok)}")
                if k == "hypotheses" and not str(c.get("playtest") or "").strip(): E.append(f"gameplay.hypotheses[{n}]: say how a playtest would check it (playtest)")
                claim(f"gameplay.{k}[{n}]", c, ("claim",), need_evidence=k != "hypotheses")
    return E


# ---------------------------------------------------------------- submit, read, status
def submit(pack_path, review, reviewer=None):
    """Validate and store a review: history/creative/<project>/<review id>/review.json plus copies of the cited images
    (so the citations stay checkable after the capture folder is gone). Refused with every problem listed."""
    K = _json(pack_path)
    if not K: raise ValueError(f"cannot read the pack {pack_path}")
    if isinstance(review, str): review = _json(review) if os.path.isfile(review) else json.loads(review)
    if reviewer and not review.get("reviewer"): review["reviewer"] = reviewer
    errs = validate(review, K)
    if errs: raise ValueError("the review was not accepted:\n- " + "\n- ".join(errs))
    ids = {i["id"]: i for i in K["items"]}
    for i in K["items"]:   # the evidence must still be what was packed
        if i["kind"] in ("screenshot", "play_frame") and (not os.path.isfile(i["path"]) or _sha(i["path"]) != i["sha256"]):
            raise ValueError(f"evidence {i['id']} changed or disappeared since the pack was made; make a new pack")
    cited = sorted(_cited(review))
    pid = K["project"]["id"]; rid = _now().strftime("%Y%m%dT%H%M%SZ")
    d = os.path.join(write_root(), pid, rid)
    n = 1
    while os.path.exists(d): n += 1; d = os.path.join(write_root(), pid, f"{rid}-{n}")
    os.makedirs(os.path.join(d, "evidence"))
    ev = []
    for e in cited:
        it = ids[e]; rec = {"id": e, "kind": it["kind"], "sha256": it["sha256"]}
        if it["kind"] in ("screenshot", "play_frame"):
            fn = _slug(e)[:120] + os.path.splitext(it["path"])[1].lower()
            shutil.copyfile(it["path"], os.path.join(d, "evidence", fn)); rec["file"] = f"evidence/{fn}"
        else: rec.update({k: it.get(k) for k in ("value", "title", "level", "department")})
        ev.append(rec)
    vs = K["vision"]
    Rv = {"schema": "gitcraft-creative-review/1", "method": METHOD, "review_id": os.path.basename(d), "created": _now().isoformat(timespec="seconds"),
          "project": K["project"]["id"], "repo": K["project"].get("repo"), "title": K["title"], "kind": K.get("kind"), "advisory": True, "scored": False,
          "bound_to": {"commit": K["project"].get("head"), "vision_version": vs["version"], "vision_status": vs["status"], "vision_sha256": vs["sha256"],
                       "pack_fingerprint": K["fingerprint"], "evidence": {r["id"]: r["sha256"] for r in ev}},
          "coverage": dict(review.get("coverage") or {}, pack_counts=K["counts"]), "review": review, "evidence": ev, "pack_warnings": K.get("warnings") or []}
    with open(os.path.join(d, "review.json"), "w") as f: json.dump(Rv, f, indent=1)
    with open(os.path.join(write_root(), pid, "index.jsonl"), "a") as f:
        f.write(json.dumps({"review_id": Rv["review_id"], "created": Rv["created"], "commit": (Rv["bound_to"]["commit"] or "")[:12],
                            "vision": f"v{vs['version']} {vs['status']}", "opportunities": len(review.get("opportunities") or [])}) + "\n")
    return dict(Rv, _dir=d)


def _cited(review):
    out = set()
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "evidence" and isinstance(v, list): out.update(x for x in v if isinstance(x, str))
                else: walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(review)
    return out


def reviews(pid):
    seen = {}
    for r in read_roots():
        for p in glob.glob(os.path.join(r, pid or "-", "*", "review.json")):
            Rv = _json(p)
            if Rv and Rv.get("review_id"): seen.setdefault(Rv["review_id"], dict(Rv, _dir=os.path.dirname(p)))
    return sorted(seen.values(), key=lambda x: x["created"])


def status(Rv, head, V):
    """current | stale | unverified, with every reason. Never current unless the commit, the vision version and every
    evidence copy are exactly what the review was bound to."""
    why = []
    B = Rv["bound_to"]
    if not head: why.append("the project is not checked out here, so the reviewed commit could not be compared with the current one")
    elif not B.get("commit") or not head.startswith(B["commit"][:12]): why.append(f"reviewed commit {str(B.get('commit'))[:7]}, the project is now at {head[:7]}")
    if not V: why.append("the vision it was written against is no longer found")
    elif V["version"] != B["vision_version"] or V["sha256"] != B["vision_sha256"]: why.append(f"written against vision v{B['vision_version']}, the vision is now v{V['version']} ({V['status']})")
    for e in Rv.get("evidence") or []:
        if e.get("file"):
            p = os.path.join(Rv["_dir"], e["file"])
            if not os.path.isfile(p) or _sha(p) != e["sha256"]: why.append(f"evidence {e['id']} is missing or changed")
    st = "unverified" if not head else ("current" if not why else "stale")
    return st, why


def for_report(P):
    """The newest review for a report: {status, why, …} or None. Only a current review's content is shown as an assessment."""
    rs = reviews(P.get("id"))
    if not rs: return None
    Rv = rs[-1]
    V = vision.latest(P.get("id"))
    st, why = status(Rv, P.get("head"), V)
    out = {"status": st, "why": why, "review_id": Rv["review_id"], "created": Rv["created"], "reviewer": Rv["review"].get("reviewer"), "bound_to": Rv["bound_to"],
           "dir": Rv["_dir"], "count": len(rs)}
    if st == "current":
        r = Rv["review"]
        order = {t: i for i, t in enumerate(TIERS)}
        out.update(vision_summary=(r.get("vision_assessment") or {}).get("summary"), vision_assessment=r.get("vision_assessment"),
                   opportunities=sorted(r.get("opportunities") or [], key=lambda o: (order.get(o.get("tier"), 9), bool(o.get("beyond_vision")))),
                   strengths=r.get("strengths") or [], strengths_note=r.get("strengths_note"), gameplay=r.get("gameplay"), coverage=Rv.get("coverage"),
                   evidence={e["id"]: e for e in Rv.get("evidence") or []})
    return out
