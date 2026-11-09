"""RUN GITCRAFT REPORT: one project report from the latest analysis of every GITCRAFT department.

  generate(project, refresh="quick", save="store") → the report (dict), written as report.json, report.md and
  report.html under <store>/<project_id>/<stamp>/ so later runs can compare progress.

This is a reader. It never re-implements a department and never invents one: the department list comes from the
code (the Studio manifests in studio/departments/*/manifest.json, DESIGNCRAFT in gamedesign/, the 3D Department in
gitcraft3d/, and the Production Director in production/). Each department's latest result is read from where that
department already keeps it:

  PLAYCRAFT        the Game Quality History (studio/departments/playcraft/history.py: local store + committed archive)
  PIXELCRAFT       its audit history (history/pixelcraft + $GITCRAFT_PIXELCRAFT_HISTORY): audit.json per run
  DESIGNCRAFT      history/designcraft (gamedesign/history.py); refreshed read-only by gamedesign.engine.assess
  TestCraft and the production departments (AudioCraft, AnimCraft, WorldCraft, FXCraft, MaterialCraft, LevelCraft,
                   CinematicCraft)   their <name>.studio.json provenance records for this project
  AssetCraft       the AssetCraft catalogue (SQLite, opened read-only)
  3D Department    the shared job store ($GITCRAFT_3D_LIBRARY/jobs)
  Production Director   the production store (acceptance verdicts) + Discovery (maturity.assess) + the engineering
                   standard (standards.check), both read-only, re-run on every report

Rules
  * Read-only. Nothing is written inside the project, nothing is built, committed, merged or deployed. The store
    must be outside the project. Refreshes that need a build or a browser (PLAYCRAFT, PIXELCRAFT) run only with
    refresh="full", only against a build folder that already exists, and never record into their histories.
  * Never manufactured. A department without data is reported as "no data" with the command that would produce it;
    a missing runtime is "unavailable" with its reason. Every finding keeps its department's evidence level
    (verified / observed / inferred) and source file. The health score is the mean of the department scores that
    were actually measured, with its coverage beside it, never a guess for the rest.
  * Comparable. Each report stores the run ids it used, so a later report says whether a department changed because
    it was re-measured or because nothing new was recorded."""
import datetime, glob, gzip, hashlib, html, importlib.util, json, os, re, sqlite3, subprocess, sys
from . import REPO, roots, scoring, creative

VERSION = "2.0.0"
STALE_DAYS = 14
SEVERITIES = ("critical", "major", "minor", "info")
LEVEL_LABEL = {"verified": "Verified", "observed": "Observed", "inferred": "Inferred (assumption)", "unavailable": "Unavailable"}
STATUS_LABEL = {"current": "Current", "refreshed": "Refreshed now", "stale": "Stale", "unverified": "Unverified (commit not compared)", "no_data": "No data", "not_applicable": "Not applicable",
                "unavailable": "Unavailable", "failed": "Failed"}
MAKERS = ("audiocraft", "animcraft", "worldcraft", "fxcraft", "materialcraft", "levelcraft", "cinematiccraft")
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", ".next", ".cache", ".vercel", "target", "gitcraft-out"}

# Themes: how findings from different departments are matched to each other (reconciliation), by their words.
THEMES = [
    ("text", "Text legibility and typography", r"\b(text|font|typograph|legib|line[- ]height|readab)"),
    ("touch", "Touch targets and mobile ergonomics", r"\b(touch|tap|tap target|thumb|safe[- ]area|mobile|phone|sideways|horizontal overflow)"),
    ("a11y", "Accessibility and contrast", r"\b(contrast|axe|accessib|aria|screen reader|focus|wcag|label)"),
    ("perf", "Performance and loading", r"\b(fps|frame rate|perform|heap|load|playable quickly|latency|first input)"),
    ("onboard", "Onboarding and first-time experience", r"\b(onboard|tutorial|first[- ]time|first run|how to play|start screen|hint)"),
    ("difficulty", "Difficulty and balance", r"\b(difficult|balance|challeng|way to fail|fail state|assist)"),
    ("progression", "Progression and rewards", r"\b(progress|reward|unlock|upgrade|milestone|economy|xp)"),
    ("agency", "Player agency and choice", r"\b(agency|choice|optional|alternative|decide)"),
    ("story", "Story, characters and world", r"\b(story|narrat|character|dialog|lore|world|ending)"),
    ("audio", "Audio", r"\b(audio|sound|music|sfx|voice)"),
    ("feel", "Feedback and game feel", r"\b(feedback|juice|feel|hit[- ]?stop|shake|haptic|respon|pressed|hover)"),
    ("layout", "Layout, spacing and consistency", r"\b(spacing|align|layout|consisten|overflow|grid|component|button)"),
    ("assets", "Assets and licences", r"\b(licen[cs]e|asset|attribution|duplicate|unused)"),
    ("release", "Release and deployment", r"\b(deploy|release|live|ci\b|build)"),
]
# DESIGNCRAFT and PLAYCRAFT categories that measure the same thing (a large disagreement between them is a conflict)
SAME_CATEGORY = [("progression", "progression"), ("difficulty", "difficulty"), ("variety", "replayability")]


# ---------------------------------------------------------------- helpers
def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _age(ts):
    try:
        t = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None: t = t.replace(tzinfo=datetime.timezone.utc)
        return round((datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 86400, 1)
    except (TypeError, ValueError):
        return None


def _load(path):
    spec = importlib.util.spec_from_file_location("gcr_" + re.sub(r"\W", "_", os.path.relpath(path, REPO)), path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def _json(p, default=None):
    try:
        with (gzip.open(p, "rt") if p.endswith(".gz") else open(p)) as f: return json.load(f)
    except (OSError, ValueError):
        return default


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-") or "project"


# each department's own structured category/area → theme (used when the finding's title names no theme)
CATEGORY_THEME = {"game_feel": "feel", "controls": "feel", "progression": "progression", "difficulty": "difficulty", "technical": "perf", "mobile": "touch",
                  "presentation": "layout", "replayability": "variety", "core_gameplay": "core", "player_experience": "onboard",
                  "accessibility": "a11y", "typography": "text", "feedback": "feel", "spacing": "layout", "layout": "layout", "component": "layout",
                  "cross_screen": "layout", "efficiency": "layout", "levelcraft": "level", "missioncraft": "missions", "storycraft": "story",
                  "progressioncraft": "progression", "experiencecraft": "experience"}


def theme_of(title, category=None):
    """A finding's problem area: from its title's words, else from its department's own category or area."""
    t = str(title or "").lower()
    for tid, _, rx in THEMES:
        if re.search(rx + r"\w*\b", t): return tid
    return CATEGORY_THEME.get(str(category or "").lower(), "other")


EXTRA_THEMES = {"engineering": "Engineering standard", "variety": "Variety and replayability", "core": "Core gameplay", "level": "Level design", "missions": "Mission design", "experience": "Player experience"}


def theme_title(tid):
    return next((t for i, t, _ in THEMES if i == tid), EXTRA_THEMES.get(tid, "Other"))


def _level(raw):
    raw = (raw or "").lower()
    if raw in ("verified", "measured", "accessibility", "source_verified"): return "verified"
    if raw in ("observed", "simulated"): return "observed"
    return "inferred"


def _finding(dept, fid, title, severity, level, evidence=None, recommendation=None, source=None, theme=None, kind=None, extra=None, effort=None, impact=None):
    """effort / impact: the owning department's own estimate when it makes one (never filled in here)."""
    f = {"key": f"{dept}:{fid}", "department": dept, "id": fid, "title": title, "severity": severity if severity in SEVERITIES else "minor",
         "level": level, "evidence": evidence, "recommendation": recommendation, "source": source, "kind": kind,
         "theme": theme or theme_of(title, extra), "effort": effort, "impact": impact}
    return f


def _dept(did, title, family, role, summary=""):
    return {"id": did, "title": title, "family": family, "role": role, "summary": summary, "applicable": True, "applies_because": None,
            "status": "no_data", "score": None, "run": None, "age_days": None, "findings": [], "strengths": [], "notes": [],
            "refresh": {"attempted": False, "ok": None, "detail": None}, "next": None}


# ---------------------------------------------------------------- the departments, from the code
def departments():
    """Every department GITCRAFT defines, read from the code (never a hard-coded list of names)."""
    out = []
    for p in sorted(glob.glob(os.path.join(REPO, "studio", "departments", "*", "manifest.json"))):
        m = _json(p, {})
        if m.get("name"): out.append({"id": m["name"], "title": m.get("title", m["name"]), "family": "Studio", "summary": m.get("summary", ""),
                                      "actions": sorted(m.get("actions") or {})})
    if os.path.isdir(os.path.join(REPO, "gamedesign", "departments")):
        subs = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(REPO, "gamedesign", "departments")) if f.endswith(".py") and f not in ("__init__.py", "base.py"))
        out.append({"id": "designcraft", "title": "DESIGNCRAFT — game-design intelligence", "family": "DESIGNCRAFT", "summary": "levels, missions, story, progression and experience, from the game's own data", "actions": subs})
    if os.path.isdir(os.path.join(REPO, "gitcraft3d")):
        out.append({"id": "3d", "title": "3D Department — ForgeCraft + MeshCraft", "family": "3D Department", "summary": "3D assets: route, generate, engine-check, library", "actions": []})
    out.append({"id": "production", "title": "Production Director", "family": "Production", "summary": "Discovery, engineering standard, productions and their acceptance verdicts", "actions": []})
    return out


# ---------------------------------------------------------------- the project
def resolve(project):
    """A local folder, a GitHub URL / owner/repo, or a history id (owner--repo) → identity (+ path when local)."""
    p = str(project or "").strip()
    out = {"input": p, "path": None, "id": None, "repo": None, "name": None, "title": None, "head": None, "branch": None, "dirty": None}
    if p and os.path.isdir(p):
        out["path"] = os.path.realpath(p)
        ph = _load(os.path.join(REPO, "studio", "departments", "playcraft", "history.py"))
        ident = ph.identity(out["path"])
        out.update(id=ident["id"], repo=ident.get("repo"), url=ident.get("url"), name=os.path.basename(out["path"]))
        out["head"] = _git(out["path"], "rev-parse", "HEAD"); out["branch"] = _git(out["path"], "rev-parse", "--abbrev-ref", "HEAD")
        st = _git(out["path"], "status", "--porcelain")
        out["dirty"] = bool(st) if st is not None else None
    else:
        m = re.search(r"github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", p) or re.match(r"^([\w.-]+)/([\w.-]+)$", p)
        if m: out.update(id=f"{m.group(1).lower()}--{m.group(2).lower()}", repo=f"{m.group(1)}/{m.group(2)}", name=m.group(2).lower())
        elif "--" in p: out.update(id=p.lower(), repo=p.replace("--", "/", 1), name=p.split("--", 1)[1])
        elif p: out.update(id=slug(p), name=slug(p))
        if out["repo"]: out["url"] = f"https://github.com/{out['repo']}"
    out["name"] = (out["name"] or out["id"] or "project").lower()
    return out


def _studio_records(P, ctx):
    """Every .studio.json provenance record that belongs to this project: in its own tree, and in the production
    store's task folders of its productions (read-only)."""
    found, seen = [], set()
    def take(path):
        rp = os.path.realpath(path)
        if rp in seen: return
        seen.add(rp); r = _json(rp)
        if isinstance(r, dict) and r.get("department"): found.append(dict(r, _path=rp))
    if P["path"]:
        for d, ds, fs in os.walk(P["path"]):
            ds[:] = [x for x in ds if x not in SKIP and not x.startswith(".")]
            if d.count(os.sep) - P["path"].count(os.sep) > 8: ds[:] = []
            for f in fs:
                if f.endswith(".studio.json"): take(os.path.join(d, f))
    for pr in ctx["productions"]:
        for base in dict.fromkeys([pr["_dir"], pr.get("_outputs") or pr["_dir"]]):
            for p in glob.glob(os.path.join(base, "tasks", "*", "**", "*.studio.json"), recursive=True): take(p)
    return found


def _productions(P):
    from . import store_roots, artifacts
    out, seen = [], set()
    if not P["path"]: return out
    for base in store_roots():
        if not os.path.isdir(base): continue
        for d in sorted(os.listdir(base)):
            pr = _json(os.path.join(base, d, "production.json"))
            if not pr or pr.get("id") in seen: continue
            pp = ((pr.get("spec") or {}).get("project") or {}).get("path")
            if pp and os.path.realpath(pp) == P["path"]:
                seen.add(pr.get("id")); sd = os.path.join(base, d)
                out.append(dict(pr, _dir=sd, _outputs=artifacts.output_root(pr.get("id") or d, sd, pp, create=False)))
    return sorted(out, key=lambda x: x.get("updated") or "")


def _build_dir(path):
    for b in ("dist", "build", "out", "public", "docs", "."):
        if os.path.isfile(os.path.join(path, b, "index.html")): return os.path.realpath(os.path.join(path, b)) if b != "." else path
    return None


def _stale(D, ctx, commit):
    """stale when older than STALE_DAYS or measured on a different commit than the project's HEAD."""
    why = []
    if D["age_days"] is not None and D["age_days"] > STALE_DAYS: why.append(f"{D['age_days']} days old (stale after {STALE_DAYS})")
    head = ctx["project"].get("head")
    if head and commit and not head.startswith(commit[:7]) and not str(commit).startswith(head[:7]):
        why.append(f"measured on {str(commit)[:7]}, the project is now at {head[:7]}")
    if why:
        D["status"] = "stale"; D["notes"].append("Stale: " + "; ".join(why))
    elif not head and commit:
        # "current" is a claim about the commit; without a checkout it cannot be made (a report with the checkout
        # seconds later called the same score stale)
        if D["status"] == "current": D["status"] = "unverified"
        D["notes"].append("Unverified: the project is not checked out here, so the analysed commit could not be compared with the current one. Clone it and report again.")
    return D


def _studio_call(action, args, timeout=3600):
    """A Studio action through studio/cli.py --call in the Studio venv (the same contract and checks as the MCP tool)."""
    home = os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "studio")
    py = os.path.join(home, "venv", "bin", "python")
    if not os.path.exists(py): return None, f"the Studio runtime is not installed ({py}); scripts/install-studio.sh"
    try:
        r = subprocess.run([py, os.path.join(REPO, "studio", "cli.py"), "--call", action, json.dumps(args)], capture_output=True, text=True,
                           timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return None, f"{action} timed out after {timeout} s"
    lines = (r.stdout or "").strip().splitlines()
    if r.returncode != 0 or not lines: return None, f"{action} failed: {(r.stderr or '')[-400:]}"
    try: return json.loads(lines[-1]), None
    except ValueError: return None, f"{action} returned no JSON"


# ---------------------------------------------------------------- collectors (one per department)
def c_playcraft(D, ctx):
    P = ctx["project"]
    D["applicable"] = ctx["kind"] in (None, "game"); D["applies_because"] = "PLAYCRAFT scores games" if ctx["kind"] == "game" else None
    ph = _load(os.path.join(REPO, "studio", "departments", "playcraft", "history.py"))
    stores = []
    for root in (ph.store_root(), ph.archive_root()):
        if os.path.isdir(os.path.join(root, "games", P["id"] or "-")): stores.append((root, ph.Store(root, archive="", sync=False)))
    best = None
    for root, st in stores:
        G = ph.game_report(st, P["id"])
        if G and (not best or (G["timeline"][-1]["at"] or "") > (best[1]["timeline"][-1]["at"] or "")): best = (root, G, st)
    if ctx["refresh"] == "full" and P["path"] and ctx["kind"] == "game":
        b = _build_dir(P["path"]); D["refresh"]["attempted"] = True
        if not b: D["refresh"].update(ok=False, detail="not refreshed: no build folder with index.html (GITCRAFT never builds the project while reporting)")
        else:
            res, err = _studio_call("playcraft_assess", {"project": P["path"], "out_dir": os.path.join(ctx["run_dir"], "refresh", "playcraft"), "record_history": False})
            D["refresh"].update(ok=bool(res and res.get("status") == "ok"), detail=err or (res or {}).get("status"))
            if res and res.get("status") == "ok": D["notes"].append("PLAYCRAFT re-assessed the existing build for this report (not recorded in the Game Quality History).")
    if not best:
        if D["applicable"]: D["next"] = "Run PLAYCRAFT on this game (studiocraft playcraft_pass) to measure how it plays."
        else: D["status"] = "not_applicable"
        return D
    root, G, st = best
    latest = next(r for r in st.runs(P["id"]) if r["run_id"] == G["latest"])
    ls = G["latest_summary"]; ov = ls["overall"]
    D.update(status="current", age_days=G["age_days"],
             run={"id": G["latest"], "at": latest.get("assessed_at"), "commit": ((latest.get("commit") or {}).get("head") or "")[:12] or None,
                  "method": latest.get("method"), "runs": G["runs"], "source": os.path.relpath(root, REPO) if root.startswith(REPO) else root},
             score={"value": ov.get("score"), "label": "Gameplay quality", "confidence": ov.get("confidence"), "coverage": ov.get("coverage"),
                    "verified_only": (ls.get("verified") or {}).get("overall"),
                    "categories": {k: v.get("score") for k, v in (latest.get("categories") or {}).items()}})
    ev = ls.get("evidence") or {}
    D["notes"].append(f"Evidence: {ev.get('verified', 0)} verified, {ev.get('observed', 0)} observed, {ev.get('inferred', 0)} inferred, {ev.get('not_tested', 0)} not tested; "
                      + ("the game was played" if ls.get("played") else "the game was NOT played (source evidence only)") + ".")
    vb = G.get("vs_baseline") or {}
    if vb: D["notes"].append(f"Against its baseline: {vb.get('verdict')}.")
    dep = G.get("deployment") or {}
    if dep.get("level"): D["notes"].append(f"Deployment: {dep.get('level')}" + (f" at {dep.get('url')}" if dep.get("url") else ""))
    run_f = {f["id"]: f for f in latest.get("findings") or []}
    for f in G["findings"]:
        if f["state"] != "open": continue
        rf = run_f.get(f["id"], {}); lvl = _level(f.get("level")); imp = f.get("impact") or 0
        sev = "critical" if f.get("type") == "defect" and lvl != "inferred" else "major" if imp >= 3 and lvl != "inferred" else "minor"
        D["findings"].append(_finding("playcraft", f["id"], f["title"], sev, lvl, f.get("evidence"), rf.get("recommendation"), f"{D['run']['source']}/games/{P['id']}",
                                      kind=f.get("type"), extra=f.get("category"), effort=scoring.playcraft_effort(f["id"]), impact=f.get("impact")))
    for r in G.get("recurring_regressions") or []:
        D["findings"].append(_finding("playcraft", "regression:" + slug(r.get("what")), f"Recurring regression: {r.get('what')}", "major", "verified", json.dumps(r)[:200]))
    ctx["playcraft_categories"] = D["score"]["categories"]
    D["strengths"] = [f"{v.get('title', k)}: {v.get('score')}" for k, v in (latest.get("categories") or {}).items() if (v.get("score") or 0) >= 85][:5]
    if dep.get("assessed_is_main") is False: D["notes"].append(f"main moved to {dep.get('main_commit')} after this assessment.")
    _stale(D, ctx, D["run"]["commit"])
    if dep.get("assessed_is_main") is False and D["status"] != "stale":
        D["status"] = "stale"; D["notes"].append("Stale: the Game Quality History records newer commits on main than the latest assessment.")
    if D["status"] == "stale": D["next"] = "Re-run PLAYCRAFT (playcraft_pass) on the current build to refresh the gameplay score."
    return D


def _pixel_runs(P):
    roots_ = [os.environ.get("GITCRAFT_PIXELCRAFT_HISTORY") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "pixelcraft", "history"),
              os.path.join(REPO, "history", "pixelcraft")]
    names = {x for x in (P.get("name"), (P.get("repo") or "").split("/")[-1].lower(), (P.get("id") or "").split("--")[-1]) if x}
    runs = {}
    for root in roots_:
        if not os.path.isdir(root): continue
        for app in os.listdir(root):
            if not os.path.isdir(os.path.join(root, app)): continue
            if not any(app == n or app.startswith(n + "-") for n in names): continue
            for run in os.listdir(os.path.join(root, app)):
                p = os.path.join(root, app, run, "audit.json")
                if os.path.isfile(p) and (app, run) not in runs: runs[(app, run)] = p
    return runs


def c_pixelcraft(D, ctx):
    P = ctx["project"]
    D["applies_because"] = "PIXELCRAFT audits the rendered HTML UI of apps, sites and games"
    runs = _pixel_runs(P)
    if ctx["refresh"] == "full" and P["path"]:
        b = _build_dir(P["path"]); D["refresh"]["attempted"] = True
        if not b: D["refresh"].update(ok=False, detail="not refreshed: no build folder with index.html (GITCRAFT never builds the project while reporting)")
        else:
            out = os.path.join(ctx["run_dir"], "refresh", "pixelcraft")
            res, err = _studio_call("pixelcraft_audit", {"project": P["path"], "target": b, "out_dir": out, "record": False})
            ok = bool(res and res.get("status") == "ok" and os.path.isfile(os.path.join(out, "audit.json")))
            D["refresh"].update(ok=ok, detail=err or (res or {}).get("status"))
            if ok: runs[("refresh", "now")] = os.path.join(out, "audit.json")
    if not runs:
        D["next"] = "Run PIXELCRAFT on the built app (studiocraft pixelcraft_audit) to measure its visual quality and usability."
        return D
    # per app: the newest audit/verify run (PIXELCRAFT's own order: run ids start with the time)
    apps = {}
    for (app, run), p in runs.items():
        A = _json(p)
        if A: apps.setdefault(app, []).append((A.get("created") or run, run, p, A))
    scores, D["apps"] = [], []
    for app, rs in sorted(apps.items()):
        rs.sort(); at, run, p, A = rs[-1]
        ov = A.get("overall") or {}; cats = {k: v.get("score") for k, v in (A.get("categories") or {}).items()}
        D["apps"].append({"app": app, "name": (A.get("app") or {}).get("name"), "run": run, "at": at, "overall": ov.get("score"), "categories": cats, "coverage": ov.get("coverage"), "method": A.get("method"),
                          "confidence": ov.get("confidence"), "commit": ((A.get("app") or {}).get("git") or {}).get("head", "")[:12] or None, "runs": len(rs)})
        scores.append(ov.get("score"))
        for f in A.get("findings") or []:
            lvl = _level(f.get("evidence"))
            D["findings"].append(_finding("pixelcraft", f"{app}:{f['id']}", f.get("title"), f.get("severity"), lvl, (f.get("explanation") or "")[:240],
                                          (f.get("recommendation") or "")[:240], os.path.relpath(p, REPO) if p.startswith(REPO) else p, extra=f.get("area"),
                                          effort=f.get("cost"), impact=f.get("impact")))
    newest = max(D["apps"], key=lambda a: a["at"])
    D.update(status="current", age_days=_age(newest["at"]),
             run={"id": newest["run"], "at": newest["at"], "commit": newest["commit"], "method": newest.get("method") or "pixelcraft", "runs": sum(a["runs"] for a in D["apps"]), "apps": len(D["apps"])},
             score={"value": round(sum(scores) / len(scores), 1) if scores else None, "label": "Visual quality and usability" + (f" (mean of {len(scores)} UIs)" if len(scores) > 1 else ""),
                    "confidence": newest["confidence"], "coverage": newest["coverage"], "categories": newest["categories"]})
    if ("refresh", "now") in runs: D["status"] = "refreshed"
    else: _stale(D, ctx, newest["commit"])
    if D["status"] == "stale": D["next"] = "Re-run PIXELCRAFT (pixelcraft_audit) on the current build."
    return D


def c_designcraft(D, ctx):
    P = ctx["project"]
    D["applicable"] = ctx["kind"] in (None, "game"); D["applies_because"] = "DESIGNCRAFT analyses game design" if ctx["kind"] == "game" else None
    gh = _load(os.path.join(REPO, "gamedesign", "history.py"))
    runs = gh.runs(P["id"]) if P["id"] else []
    A, fresh = (runs[-1] if runs else None), None
    if ctx["refresh"] in ("quick", "full") and P["path"] and ctx["kind"] in (None, "game"):
        D["refresh"]["attempted"] = True
        try:
            sys.path.insert(0, REPO) if REPO not in sys.path else None
            from gamedesign import engine as gde
            fresh = gde.assess(P["path"])
            os.makedirs(os.path.join(ctx["run_dir"], "refresh"), exist_ok=True)
            with open(os.path.join(ctx["run_dir"], "refresh", "designcraft.json"), "w") as f: json.dump(fresh, f, default=str)
            same = A and A["game"].get("content_sha256") == fresh["game"].get("content_sha256") and A.get("method") == fresh.get("method")
            D["refresh"].update(ok=True, detail="re-analysed read-only; " + ("content and method unchanged since the recorded run" if same else "the game's design data changed (or no recorded run)"))
            if not same: A = fresh
            else: fresh = None
        except Exception as e:   # a game DESIGNCRAFT cannot read is reported, never papered over
            D["refresh"].update(ok=False, detail=f"DESIGNCRAFT could not analyse the project: {e}"[:300])
    if not A:
        if D["applicable"]: D["next"] = "Run DESIGNCRAFT (python3 -m gamedesign assess <repo> --record) to analyse the game's design."
        else: D["status"] = "not_applicable"
        return D
    S = A["score"]
    D.update(status="refreshed" if fresh else "current", age_days=_age(A["assessed_at"]),
             run={"id": A.get("run_id") or "this report", "at": A["assessed_at"], "commit": (A["game"].get("commit") or "")[:12] or None, "method": A.get("method"),
                  "runs": len(runs), "source": f"history/designcraft/{P['id']}" if not fresh else "refreshed for this report"},
             score={"value": S["overall"], "label": "Game design", "confidence": S.get("confidence"), "coverage": S.get("coverage"), "ceiling": S.get("ceiling"),
                    "categories": {k: round(100 * v["score"] / v["max"], 1) if v.get("max") else v.get("score") for k, v in S["categories"].items()}})
    props = {}
    for pr in A.get("proposals") or []:
        if pr.get("finding") and pr.get("variant") in (None, "conservative"): props.setdefault(pr["finding"], pr)
    for f in A.get("findings") or []:
        facts = [e for e in f.get("evidence") or [] if e.get("level") == "source_verified"]
        pr = props.get(f["id"])
        src = next((f"{e['file']}:{e['line']}" if e.get("line") else e["file"] for e in f.get("evidence") or [] if e.get("file")), None)
        D["findings"].append(_finding("designcraft", f["id"], f["title"], f.get("severity"), _level(f.get("level")),
                                      (f.get("summary") or "") + (f" (facts verified in source: {len(facts)})" if facts else ""),
                                      (pr or {}).get("proposal") or (pr or {}).get("label"), src, extra=f.get("dept"), effort=(pr or {}).get("complexity"), impact=(pr or {}).get("impact")))
    ctx["designcraft_categories"] = D["score"]["categories"]
    if D["status"] != "refreshed": _stale(D, ctx, D["run"]["commit"])
    return D


def c_records(D, ctx):
    """TestCraft and the production departments: their provenance records for this project."""
    recs = [r for r in ctx["records"] if r.get("department") == D["id"]]
    D["applicable"] = True
    if not recs:
        D["status"] = "no_data"
        D["notes"].append("No outputs from this department were found for this project (its .studio.json records live beside its outputs).")
        D["next"] = None if D["id"] != "testcraft" else "Run TestCraft (testcraft_smoke / testcraft_play) on the build for automated QA evidence."
        return D
    recs.sort(key=lambda r: r.get("created") or "")
    checks = [c for r in recs for c in r.get("checks") or []]
    ok = sum(1 for c in checks if c.get("ok")); failed = [r for r in recs if r.get("status") != "ok"]
    last = recs[-1]
    D.update(status="current", age_days=_age(last.get("created")),
             run={"id": os.path.basename(last["_path"]), "at": last.get("created"), "runs": len(recs), "source": last["_path"]})
    D["checks"] = {"passed": ok, "of": len(checks)}
    if D["id"] == "testcraft" and checks:
        D["score"] = {"value": round(100 * ok / len(checks), 1), "label": "QA checks passed", "confidence": "high", "coverage": None}
    D["notes"].append(f"{len(recs)} run(s): " + ", ".join(sorted({r.get('action') for r in recs})) + f"; {ok}/{len(checks)} output checks passed.")
    for r in failed:
        D["findings"].append(_finding(D["id"], f"{r.get('action')}:{os.path.basename(r['_path'])}", f"{D['id']} {r.get('action')} failed",
                                      "major", "verified", (r.get("error") or "")[:240], r.get("hint"), r["_path"]))
    for r in recs:
        for c in r.get("checks") or []:
            if not c.get("ok") and r.get("status") == "ok":
                D["findings"].append(_finding(D["id"], f"{r.get('action')}:{slug(c.get('name'))}", c.get("name"), "major" if D["id"] == "testcraft" else "minor", "verified",
                                              str(c.get("detail"))[:240], None, r["_path"]))
    return D


def c_assetcraft(D, ctx):
    P = ctx["project"]
    cat = os.environ.get("GITCRAFT_ASSET_CATALOG") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "assetcraft", "catalog.sqlite")
    if not P["path"]:
        D["notes"].append("The project is not checked out here, so its catalogue entries (keyed by folder) cannot be matched.")
        D["status"] = "unavailable"; return D
    if not os.path.isfile(cat):
        D["next"] = "Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files."; return D
    try:
        c = sqlite3.connect(f"file:{cat}?mode=ro", uri=True)
        rows = c.execute("SELECT kind, license, valid, updated, rel FROM assets WHERE current=1 AND (project=? OR path LIKE ?)", (P["path"], P["path"] + os.sep + "%")).fetchall()
        c.close()
    except sqlite3.Error as e:
        D["status"] = "unavailable"; D["notes"].append(f"catalogue unreadable: {e}"); return D
    if not rows:
        D["next"] = "Catalogue the project's assets (studiocraft assetcraft_scan) for licences, duplicates and unused files."; return D
    kinds = {}
    for k, *_ in rows: kinds[k] = kinds.get(k, 0) + 1
    unknown = [r for r in rows if not r[1] or r[1] == "UNKNOWN"]; invalid = [r for r in rows if r[2] == 0]
    last = max((r[3] or "") for r in rows)
    D.update(status="current", age_days=_age(last), run={"id": "catalogue", "at": last, "runs": len(rows), "source": cat},
             score={"value": round(100 * (len(rows) - len(unknown)) / len(rows), 1), "label": "Assets with a known licence", "confidence": "high", "coverage": None})
    D["notes"].append(f"{len(rows)} catalogued assets: " + ", ".join(f"{v} {k}" for k, v in sorted(kinds.items())))
    if unknown: D["findings"].append(_finding("assetcraft", "unknown-licence", f"{len(unknown)} asset(s) have no known licence", "major", "verified",
                                              ", ".join(r[4] for r in unknown[:5]), "Add a <file>.license.json sidecar or re-register with the licence (assetcraft_license_report).", cat, theme="assets"))
    if invalid: D["findings"].append(_finding("assetcraft", "invalid", f"{len(invalid)} asset(s) failed format validation", "major", "verified",
                                              ", ".join(r[4] for r in invalid[:5]), "Re-export or replace them (assetcraft_verify).", cat, theme="assets"))
    return D


def c_3d(D, ctx):
    P = ctx["project"]
    lib = os.environ.get("GITCRAFT_3D_LIBRARY") or os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "3d-library")
    jd = os.path.join(lib, "jobs")
    keys = [k for k in (P["path"], P["id"]) if k]
    jobs = []
    if os.path.isdir(jd):
        for f in os.listdir(jd):
            if not f.endswith(".json"): continue
            try: txt = open(os.path.join(jd, f)).read()
            except OSError: continue
            if any(k in txt for k in keys):
                r = _json(os.path.join(jd, f), {})
                jobs.append({k: r.get(k) for k in ("id", "tool", "asset_id", "status", "created", "updated", "error")})
    jobs += [{"id": os.path.basename(r["_path"]), "status": "succeeded" if r.get("status") == "ok" else r.get("status"), "created": r.get("created")}
             for r in ctx["records"] if r.get("department") in ("meshcraft", "forgecraft")]
    D["applicable"] = True
    if not jobs:
        D["notes"].append("No 3D Department jobs reference this project.")
        return D
    jobs.sort(key=lambda j: j.get("created") or "")
    bad = [j for j in jobs if j.get("status") in ("failed", "blocked")]
    D.update(status="current", age_days=_age(jobs[-1].get("created")), run={"id": jobs[-1]["id"], "at": jobs[-1].get("created"), "runs": len(jobs), "source": jd})
    D["jobs"] = {s: sum(1 for j in jobs if j.get("status") == s) for s in ("succeeded", "failed", "blocked")}
    D["notes"].append(f"{len(jobs)} job(s): " + ", ".join(f"{s} {sum(1 for j in jobs if j.get('status') == s)}" for s in sorted({str(j.get('status')) for j in jobs})))
    for j in bad:
        D["findings"].append(_finding("3d", j["id"], f"3D job {j.get('asset_id') or j['id']} {j.get('status')}", "major", "verified", (j.get("error") or "")[:240],
                                      "Inspect it with forgecraft job_get and retry or re-route (job_retry / route).", jd, theme="assets"))
    return D


def c_production(D, ctx):
    from . import maturity, standards, report as acc
    P = ctx["project"]
    if P["path"]:
        a = ctx["assessment"]
        D["refresh"].update(attempted=True, ok=True, detail="Discovery and the engineering standard re-run read-only for this report")
        D["notes"].append(f"Discovery: {a.get('maturity')} {a.get('kind') or 'project'} ({a.get('confidence')} confidence) — " + "; ".join(a.get("evidence", [])[:3]))
        inv = a.get("inventory") or {}
        for i, d in enumerate(inv.get("defects") or []):
            D["findings"].append(_finding("production", f"defect:{slug(d['what'])[:60]}", d["what"], "major", "verified", d.get("evidence"), "Fix or remove the reference.", d.get("where"), theme="assets"))
        if inv.get("unfinished"):
            D["findings"].append(_finding("production", "unfinished", f"{len(inv['unfinished'])} unfinished item(s) (stubs, TODOs, open roadmap items)", "minor", "verified",
                                          "; ".join(f"{u['what']} ({u['where']})" for u in inv["unfinished"][:4]), "Finish or remove them before release.", None, theme="release"))
        try:
            found = a.get("analytics") or []   # Discovery's analytics: recognised, never "undeclared" failures
            sc = standards.check(P["path"], deliverable=a.get("kind") or "app", analytics="pulse" if any(f["provider"] == "pulse" for f in found) else None,
                                 analytics_decided=False)
            checks = sc.get("checks") or []; rel = [c for c in checks if c["status"] != "n/a"]
            ok = [c for c in rel if c["status"] in ("ok", "accepted")]
            D["standard"] = {"passed": len(ok), "of": len(rel), "status": sc.get("status"), "advisory": len([c for c in rel if c["status"] == "advisory"]),
                             "accepted": len([c for c in rel if c["status"] == "accepted"]), "checks": [c["status"] for c in rel]}
            if rel: D["score"] = {"value": scoring._std_score(D["standard"]), "label": "Engineering standard", "confidence": "high", "coverage": None}
            if found: D["notes"].append("Analytics recognised: " + ", ".join(f"{f['name']} ({', '.join(f['where'][:2])})" for f in found) + ".")
            for c in rel:
                if c["status"] == "failed":
                    D["findings"].append(_finding("production", f"standard:{c['id']}", f"Engineering standard: {c['name']}", "major", "verified", str(c.get("detail") or "")[:200], None, "docs/app-standards.md", theme="engineering"))
                elif c["status"] == "advisory":   # measured, non-blocking (accepted decisions are not raised again)
                    D["findings"].append(_finding("production", f"standard:{c['id']}", f"Engineering standard (advisory): {c['name']}", "info", "verified", str(c.get("detail") or "")[:240],
                                                  f"Non-blocking. To stop it being raised again, accept it in .gitcraft/accepted.json with fingerprint {c.get('fingerprint')}.", "docs/app-standards.md", theme="engineering", kind="advisory"))
                elif c["status"] == "review":
                    D["findings"].append(_finding("production", f"standard:{c['id']}", f"Engineering standard (review): {c['name']}", "minor", "inferred", str(c.get("detail") or "")[:200], None, "docs/app-standards.md", theme="engineering"))
            D["notes"].append(f"Engineering standard: {len(ok)}/{len(rel)} applicable checks pass.")
        except Exception as e:
            D["notes"].append(f"Engineering standard not checked: {e}"[:200])
    prods = ctx["productions"]
    if prods:
        pr = prods[-1]; A = acc.acceptance(pr); v = acc.verdict(A)
        passed = sum(1 for x in A if x["status"] == "passed")
        ran = any(t.get("state") not in ("pending", None) for t in (pr.get("tasks") or {}).values())
        try: reasons = acc.final(pr)["reasons"]
        except Exception: reasons = []
        from . import lifecycle
        try: stage = lifecycle.summary(pr)["stage"]
        except Exception: stage = None
        D["production"] = {"id": pr["id"], "status": pr.get("status"), "verdict": v, "reasons": reasons[:8], "criteria": len(A), "passed": passed, "updated": pr.get("updated"),
                           "ran": ran, "stage": stage, "title": (pr.get("spec") or {}).get("title"),
                           "criteria_list": [{"id": x["id"], "title": x.get("title") or x.get("text") or x["id"], "status": x["status"]} for x in A]}
        D["notes"].append(f"Production {pr['id']}: {pr.get('status')}, verdict {v}, {passed}/{len(A)} acceptance criteria passed.")
        if not ran: D["notes"].append("That production is planned but has not run yet: its criteria are unmeasured, so it has no score and no findings.")
        # acceptance criteria are release gates (pass/fail), shown as gates and never averaged into a quality score
        D["run"] = {"id": pr["id"], "at": pr.get("updated"), "runs": len(prods), "source": pr["_dir"]}
        D["age_days"] = _age(pr.get("updated"))
        from . import verification
        rs = verification.release_summary(pr, A)
        D["production"]["release_status"] = rs["release_status"]
        D["notes"].append(f"Release: {rs['release_status']} — deployment {rs['deployment']['label']}; functional {rs['functional']}; security {rs['security']}; "
                          f"visual {rs['visual']}; {len(rs['unverified'])} unverified, {len(rs['advisories'])} advisory.")
        for x in (A if ran else []):
            if x["status"] == "failed":   # measured and failed: a confirmed blocker
                D["findings"].append(_finding("production", f"criterion:{x['id']}", f"Acceptance criterion failed: {x.get('title') or x['id']}", "critical",
                                              "verified", "; ".join(x.get("why") or [])[:240], None, os.path.join(pr["_dir"], "REPORT.md"), kind="blocker", theme="release"))
            elif x["status"] in ("blocked", "unverified", "not_planned"):   # verification incomplete: never presented as an application failure
                D["findings"].append(_finding("production", f"criterion:{x['id']}", f"Verification incomplete ({x['status'].replace('_', ' ')}): {x.get('title') or x['id']}", "major",
                                              "verified", "; ".join(x.get("why") or [])[:240], "Complete the verification (run it where the dependency is reachable, or verify in production); "
                                              "this is not evidence of an application defect.", os.path.join(pr["_dir"], "REPORT.md"), kind="unverified", theme="release"))
            elif x["status"] == "needs_approval":
                D["findings"].append(_finding("production", f"approval:{x['id']}", f"Waiting for a person's approval: {x.get('title') or x['id']}", "major", "verified",
                                              "; ".join(x.get("why") or [])[:240], "Approve or decline it (production_approve); reporting never approves.", None, kind="approval", theme="release"))
    if P["path"] or prods: D["status"] = "refreshed" if P["path"] else "current"
    else:
        D["status"] = "unavailable"; D["notes"].append("The project is not checked out here: Discovery and the engineering standard need its files (clone it and report again).")
    return D


COLLECTORS = {"playcraft": c_playcraft, "pixelcraft": c_pixelcraft, "designcraft": c_designcraft, "assetcraft": c_assetcraft, "3d": c_3d,
              "production": c_production, "testcraft": c_records, **{m: c_records for m in MAKERS}}
ROLE = {"playcraft": "scored", "pixelcraft": "scored", "designcraft": "scored", "testcraft": "qa", "assetcraft": "catalogue", "3d": "maker",
        "production": "director", **{m: "maker" for m in MAKERS}}


# ---------------------------------------------------------------- reconciliation
def reconcile(depts, ctx):
    findings = [f for d in depts for f in d["findings"]]
    by_theme = {}
    for f in findings: by_theme.setdefault(f["theme"], []).append(f)
    out = {"corroborated": [], "conflicts": [], "dependencies": [], "gaps": []}
    for tid, fs in sorted(by_theme.items()):
        ds = sorted({f["department"] for f in fs})
        if len(ds) >= 2 and tid != "other":
            out["corroborated"].append({"theme": tid, "title": theme_title(tid), "departments": ds, "count": len(fs),
                                        "findings": [{"department": f["department"], "title": f["title"], "level": f["level"], "severity": f["severity"]} for f in fs[:8]],
                                        "note": "The same problem area is flagged by more than one department: one fix should address all of these, so they are one action."})
    pc, dc = ctx.get("playcraft_categories") or {}, ctx.get("designcraft_categories") or {}
    for dk, pk in SAME_CATEGORY:
        a, b = dc.get(dk), pc.get(pk)
        if a is not None and b is not None and abs(a - b) >= 35:
            out["conflicts"].append({"title": f"{dk.capitalize()}: DESIGNCRAFT {a:.0f}% vs PLAYCRAFT {b:.0f}%", "departments": ["designcraft", "playcraft"],
                                     "detail": "DESIGNCRAFT reads the design data (source); PLAYCRAFT measures the played build. A large gap means the design intent and the played experience disagree. "
                                               "Trust measured play for how it plays today, and the design analysis for what the data allows; confirm in a playtest before acting on either alone."})
    D = {d["id"]: d for d in depts}
    pcv = (D.get("playcraft") or {}).get("score") or {}
    pxf = [f for f in (D.get("pixelcraft") or {}).get("findings", []) if f["theme"] in ("touch", "text") and f["severity"] in ("critical", "major")]
    if pxf and (pcv.get("categories") or {}).get("mobile", 0) >= 85:
        out["conflicts"].append({"title": "Mobile: PLAYCRAFT scores mobile high, PIXELCRAFT reports major mobile UI problems", "departments": ["playcraft", "pixelcraft"],
                                 "detail": f"PLAYCRAFT mobile {pcv['categories']['mobile']}; PIXELCRAFT: " + "; ".join(f["title"] for f in pxf[:3]) +
                                           ". PLAYCRAFT measures the canvas and controls, PIXELCRAFT the HTML UI: both can be right. Fix the PIXELCRAFT items, then re-run both."})
    for d in depts:
        if d["status"] == "stale" and d["id"] in ("playcraft", "pixelcraft"):
            out["dependencies"].append({"title": f"{d['title'].split(' — ')[0]} is stale", "departments": [d["id"]], "detail": "Its score describes an older build. Re-measuring needs a current build; "
                                        "GITCRAFT never builds while reporting, so build first, then run the department (or report with refresh=full)."})
    if (D.get("designcraft") or {}).get("status") in ("current", "refreshed", "stale", "unverified") and (D.get("playcraft") or {}).get("status") == "stale":
        out["dependencies"].append({"title": "DESIGNCRAFT's experience analysis reads PLAYCRAFT", "departments": ["designcraft", "playcraft"],
                                    "detail": "experiencecraft uses PLAYCRAFT runs as simulated evidence, so refresh PLAYCRAFT first, then DESIGNCRAFT."})
    prodD = D.get("production") or {}
    if (prodD.get("production") or {}).get("verdict", "").startswith("NOT READY"):
        out["dependencies"].append({"title": "Release is blocked by the production's acceptance criteria", "departments": ["production"],
                                    "detail": "Every failed or blocked criterion must pass (with a measurement) before the verdict can be READY."})
    for d in depts:
        if d["applicable"] and d["status"] == "no_data" and d["next"]:
            out["gaps"].append({"department": d["id"], "title": d["title"], "detail": d["next"]})
    if not any(d["status"] in ("current", "refreshed", "stale", "unverified") for d in depts if d["id"] == "testcraft"):
        if not any(g["department"] == "testcraft" for g in out["gaps"]):
            out["gaps"].append({"department": "testcraft", "title": "TestCraft — automated QA", "detail": "No automated QA evidence for this project."})
    return out


def plan(depts, rec):
    """P0–P3: one action per problem area, merged across departments, ranked by severity and evidence."""
    items, seen = [], {}
    for d in depts:
        for f in d["findings"]:
            sev, lvl = f["severity"], f["level"]
            if sev == "critical" or f.get("kind") == "blocker": pr = "P0" if lvl != "inferred" else "P1"
            elif sev == "major": pr = "P1" if lvl in ("verified", "observed") else "P2"
            elif sev == "minor": pr = "P2" if lvl != "inferred" else "P3"
            else: pr = "P3"
            gk = (f["theme"], pr) if f["theme"] != "other" else (f["key"], pr)
            if gk in seen:
                it = seen[gk]; it["findings"].append(f["key"])
                if f["department"] not in it["departments"]: it["departments"].append(f["department"])
                continue
            it = {"priority": pr, "theme": f["theme"], "title": f["title"] if f["theme"] == "other" else f"{theme_title(f['theme'])}: {f['title']}",
                  "departments": [f["department"]], "findings": [f["key"]], "level": lvl, "why": f.get("evidence"), "do": f.get("recommendation")}
            seen[gk] = it; items.append(it)
    for it in items:
        if len(it["departments"]) > 1: it["title"] += f" (+{len(it['findings']) - 1} related, {', '.join(it['departments'])})"
        if len(it["departments"]) > 1 and it["priority"] in ("P2", "P3"): it["priority"] = {"P2": "P1", "P3": "P2"}[it["priority"]]; it["raised"] = "corroborated by several departments"
    for g in rec["gaps"]:
        items.append({"priority": "P2", "theme": "coverage", "title": f"No data: {g['title']}", "departments": [g["department"]], "findings": [], "level": "unavailable", "why": "this department has never analysed the project", "do": g["detail"]})
    for dp in rec["dependencies"]:
        if "stale" in dp["title"]:
            nx = next((d.get("next") for d in depts if d["id"] == dp["departments"][0]), None)
            items.append({"priority": "P1", "theme": "coverage", "title": f"Refresh: {dp['title']}", "departments": dp["departments"], "findings": [], "level": "verified", "why": dp["detail"], "do": nx})
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    lv = {"verified": 0, "observed": 1, "inferred": 2, "unavailable": 3}
    items.sort(key=lambda i: (order[i["priority"]], -len(i["departments"]), lv.get(i["level"], 9), i["title"]))
    for n, it in enumerate(items, 1): it["n"] = n
    return items


def health(depts, actions):
    """The overall quality score: the weighted mean of the evaluated departments' rubric scores (scoring.overall).
    Release gates and approvals are kept apart (scoring.gates)."""
    for d in depts:
        if "quality" not in d: scoring.evaluate(d)
    stale = [d["id"] for d in depts if d["status"] in ("stale", "unverified") and d["quality"]["evaluation"] == "evaluated"]
    return scoring.overall(depts, p0=sum(1 for a in actions if a["priority"] == "P0"), stale=stale)


# ---------------------------------------------------------------- store + comparison
def store_root():
    return os.path.realpath(os.environ.get("GITCRAFT_REPORTS") or os.path.join(roots()[0], "gitcraft-out", "reports"))


def archive_root():
    return os.path.join(REPO, "history", "reports")


def history(pid, roots_=None, before=None):
    """Every earlier report of this project (store + archive, oldest first, one per report id)."""
    seen = {}
    for r in roots_ or (store_root(), archive_root()):
        for p in glob.glob(os.path.join(r, pid or "-", "*", "report.json")):
            R = _json(p)
            if R and R.get("report_id") and (before is None or R["generated"] < before): seen.setdefault(R["report_id"], R)
    return sorted(seen.values(), key=lambda R: R["generated"])


def previous(pid, roots_=None):
    h = history(pid, roots_)
    return h[-1] if h else None


def compare(prev, cur):
    if not prev: return {"first": True, "note": "This is the first GITCRAFT report for this project: future reports will compare against it."}
    pd = {d["id"]: d for d in prev["departments"]}
    out = {"first": False, "against": prev["report_id"], "at": prev["generated"], "health": {"from": prev["health"].get("score"), "to": cur["health"].get("score")}, "departments": [],
           "new_actions": [], "resolved_actions": []}
    if out["health"]["from"] is not None and out["health"]["to"] is not None: out["health"]["delta"] = round(out["health"]["to"] - out["health"]["from"], 1)
    for d in cur["departments"]:
        p = pd.get(d["id"])
        if not p: out["departments"].append({"id": d["id"], "change": "new department since the previous report"}); continue
        a, b = (p.get("score") or {}).get("value"), (d.get("score") or {}).get("value")
        same_run = scoring.same_measurement(p.get("run"), d.get("run"))
        ch = None
        if p["status"] != d["status"]: ch = f"{STATUS_LABEL.get(p['status'])} → {STATUS_LABEL.get(d['status'])}"
        if a != b and a is not None and b is not None:
            ch = (ch + "; " if ch else "") + f"score {a} → {b}" + (" (same run: the method or reading changed, not the project)" if same_run else " (new measurement)")
        elif a is None and b is not None: ch = (ch + "; " if ch else "") + f"first score {b}"
        if ch or not same_run: out["departments"].append({"id": d["id"], "change": ch or "re-measured, score unchanged", "same_run": same_run})
    pk = {f["key"] for d in prev["departments"] for f in d["findings"]}; ck = {f["key"] for d in cur["departments"] for f in d["findings"]}
    out["new_findings"] = sorted(ck - pk)[:40]; out["resolved_findings"] = sorted(pk - ck)[:40]
    pa = {a["title"] for a in prev["actions"]}; ca = {a["title"] for a in cur["actions"]}
    out["new_actions"] = sorted(ca - pa)[:20]; out["resolved_actions"] = sorted(pa - ca)[:20]
    out["note"] = "A finding disappears only when its department re-measured and no longer reports it, or the department's data is no longer available (see each department's status)."
    return out


# ---------------------------------------------------------------- the report
def generate(project, refresh="quick", save="store", out_dir=None, store=None):
    if refresh not in ("none", "quick", "full"): raise ValueError("refresh must be none, quick or full")
    P = resolve(project)
    if not P["id"]: raise ValueError("which project? give its folder, its GitHub URL (owner/repo) or its history id (owner--repo)")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.path.realpath(store or (archive_root() if save == "archive" else store_root()))
    if not out_dir:   # reports are never overwritten: two in the same second get distinct folders
        n = 1
        while os.path.exists(os.path.join(base, P["id"], stamp)):
            n += 1; stamp = stamp.split("-")[0] + f"-{n}"
    run_dir = os.path.realpath(out_dir or os.path.join(base, P["id"], stamp))
    if P["path"] and (run_dir == P["path"] or run_dir.startswith(P["path"] + os.sep)) and not (save == "archive" and P["path"] == os.path.realpath(REPO)):
        raise PermissionError(f"GITCRAFT report is read-only: the report folder {run_dir} is inside the project; set GITCRAFT_REPORTS to a folder outside it")
    from . import maturity
    assessment = maturity.assess(P["path"]) if P["path"] else None
    ctx = {"project": P, "refresh": refresh, "run_dir": run_dir, "assessment": assessment, "kind": (assessment or {}).get("kind") or None}
    # a game: the game departments already know it, or Discovery reads it as a game with a playable entry point
    # (a toolchain that only contains game fixtures, like GITCRAFT itself, is not one)
    hist_game = any(os.path.isdir(os.path.join(r, P["id"])) for r in (os.path.join(REPO, "history", "playcraft", "games"), os.path.join(REPO, "history", "designcraft")))
    if hist_game or (ctx["kind"] == "game" and (assessment or {}).get("entry")): ctx["kind"] = "game"
    elif ctx["kind"] == "game": ctx["kind"] = "toolkit"; ctx["kind_note"] = "Discovery saw game engines but no playable entry point, so the game departments do not apply"
    elif not P["path"]: ctx["kind"] = None
    ctx["productions"] = _productions(P)
    ctx["records"] = _studio_records(P, ctx)
    depts = []
    for spec in departments():
        D = _dept(spec["id"], spec["title"], spec["family"], ROLE.get(spec["id"], "maker"), spec["summary"])
        fn = COLLECTORS.get(spec["id"], c_records)
        try: fn(D, ctx)
        except Exception as e:   # one department's failure never hides the others, and is never reported as data
            D["status"] = "failed"; D["notes"].append(f"Could not read this department's results: {type(e).__name__}: {e}"[:300])
        if D["refresh"]["attempted"] is False and refresh != "none" and spec["id"] in ("playcraft", "pixelcraft") and D["status"] != "not_applicable":
            D["refresh"]["detail"] = ("not refreshed: needs a browser session on an existing build; report with refresh=full, or run the department itself"
                                      if P["path"] else "not refreshed: the project is not checked out here")
        if D["status"] == "no_data" and not D["applicable"]: D["status"] = "not_applicable"
        D["findings"].sort(key=lambda f: (SEVERITIES.index(f["severity"]), f["level"] != "verified", f["title"] or ""))
        depts.append(D)
    first = ["production", "playcraft", "pixelcraft", "designcraft", "testcraft", "assetcraft", "3d"]
    depts.sort(key=lambda d: first.index(d["id"]) if d["id"] in first else len(first))
    if ctx.get("kind_note"): next(d for d in depts if d["id"] == "production")["notes"].append(ctx["kind_note"] + ".")
    rec = reconcile(depts, ctx)
    actions = plan(depts, rec)
    H = health(depts, actions)
    earlier = history(P["id"])
    prev = earlier[-1] if earlier else None
    scoring.deltas(prev, depts)
    H["vs_previous"] = scoring.overall_delta(prev, H)
    R = {"gitcraft_report": VERSION, "report_id": f"{P['id']}/{stamp}", "generated": now(), "refresh": refresh, "read_only": True,
         "project": {k: P.get(k) for k in ("id", "repo", "url", "name", "path", "head", "branch", "dirty")} | {
             "kind": ctx["kind"], "maturity": (assessment or {}).get("maturity")},
         "health": H, "departments": depts, "reconciliation": rec, "actions": actions,
         "levels": {lv: sum(1 for d in depts for f in d["findings"] if f["level"] == lv) for lv in ("verified", "observed", "inferred")},
         "unavailable": [{"department": d["id"], "status": d["status"], "why": (d["notes"] or [d.get("next") or ""])[-1]} for d in depts if d["status"] in ("unavailable", "failed")],
         "not_refreshed": [{"department": d["id"], "why": d["refresh"]["detail"]} for d in depts if d["refresh"].get("detail") and not d["refresh"].get("ok")]}
    R["title"] = _title(R, ctx)
    R["gates"] = scoring.gates(depts)
    R["identity"] = identity(P, depts, R["gates"], ctx)
    R["changes"] = compare(prev, R)
    R["trend"] = scoring.series(earlier[-11:], R)
    R["top_actions"] = scoring.top_actions(actions, {f["key"]: f for d in depts for f in d["findings"]})
    R["major_findings"] = major_findings(depts)
    R["regressions"] = regressions(R)
    R["blockers"] = blockers(R, earlier)
    R["summary"] = executive(R)
    R["next_actions"] = next_actions(R)
    # the Creative Review is read last and feeds nothing above: no score, gate, verdict, priority, plan or trend reads it
    try: R["creative"] = creative.for_report(P)
    except Exception as e: R["creative"] = {"status": "unavailable", "why": [f"{type(e).__name__}: {e}"[:200]]}
    R["paths"] = {"dir": run_dir}
    if save != "none":
        os.makedirs(run_dir, exist_ok=True)
        R["paths"].update(json=os.path.join(run_dir, "report.json"), markdown=os.path.join(run_dir, "report.md"), html=os.path.join(run_dir, "report.html"))
        with open(R["paths"]["json"], "w") as f: json.dump(R, f, indent=1, default=str)
        with open(R["paths"]["markdown"], "w") as f: f.write(markdown(R))
        with open(R["paths"]["html"], "w") as f: f.write(render_html(R))
        line = {"report_id": R["report_id"], "generated": R["generated"], "project": P["id"], "title": R["title"], "health": H.get("score"), "method": H.get("method"), "band": H.get("band"),
                "verdict": R["gates"].get("verdict"),
                "confidence": H.get("confidence"), "p": {p: sum(1 for a in actions if a["priority"] == p) for p in ("P0", "P1", "P2", "P3")},
                "departments": {d["id"]: {"status": d["status"], "score": d["quality"]["value"], "evaluation": d["quality"]["evaluation"], "rubric": d["quality"]["rubric"]} for d in depts},
                "dir": os.path.relpath(run_dir, base)}
        idx = os.path.join(os.path.dirname(os.path.dirname(run_dir)) if not out_dir else run_dir, "index.jsonl")
        with open(idx, "a") as f: f.write(json.dumps(line) + "\n")
    return R


def identity(P, depts, G, ctx):
    """Who and what this report is about: project, release/version, commit, Director verdict, production status.
    Every field comes from the project's files, git or a department record; absent ones stay None."""
    version, vsrc = None, None
    if P.get("path"):
        pk = _json(os.path.join(P["path"], "package.json"), {}) or {}
        if pk.get("version"): version, vsrc = pk["version"], "package.json"
        tag = _git(P["path"], "describe", "--tags", "--always", "--dirty")
        if tag and not version: version, vsrc = tag, "git describe"
        elif tag: vsrc += f" · git {tag}"
    commits = [(d["run"].get("at") or "", d["run"].get("commit")) for d in depts if d.get("run") and d["run"].get("commit")]
    commit = (P.get("head") or "")[:12] or (max(commits)[1] if commits else None)
    return {"name": P.get("name"), "repo": P.get("repo"), "url": P.get("url"), "kind": ctx.get("kind"), "maturity": (ctx.get("assessment") or {}).get("maturity"),
            "branch": P.get("branch"), "commit": commit, "commit_source": "project checkout" if P.get("head") else ("latest department run" if commit else None),
            "version": version, "version_source": vsrc, "production": G.get("production"), "verdict": G.get("verdict"), "production_status": G.get("status"),
            "release_status": G.get("release_status")}


def major_findings(depts, n=6):
    """The strongest findings: critical and major, measured before inferred, one per problem area."""
    fs = [f for d in depts for f in d["findings"] if f["severity"] in ("critical", "major") and f.get("kind") not in ("unverified", "approval")]
    fs.sort(key=lambda f: (SEVERITIES.index(f["severity"]), {"verified": 0, "observed": 1}.get(f["level"], 2), f["title"] or ""))
    out, themes = [], set()
    for f in fs:
        k = f["theme"] if f["theme"] != "other" else f["key"]
        if k in themes: continue
        themes.add(k); out.append(f)
        if len(out) >= n: break
    return out


def regressions(R):
    """Measured regressions only: a comparable department score that fell on a new measurement, PLAYCRAFT's recurring
    regressions, and critical/major measured findings that are new since the previous report."""
    out = []
    for d in R["departments"]:
        q = d["quality"]
        if q.get("delta") is not None and q["delta"] < 0 and q.get("compare") == "new measurement":
            out.append({"department": d["id"], "title": f"{q['label']} fell {q['previous']} → {q['value']} ({q['delta']:+})", "level": "verified", "kind": "score"})
        for f in d["findings"]:
            if f["id"].startswith("regression:"): out.append({"department": d["id"], "title": f["title"], "level": f["level"], "kind": "recurring"})
    if not R["changes"].get("first"):
        new = set(R["changes"].get("new_findings") or [])
        for d in R["departments"]:
            for f in d["findings"]:
                if f["key"] in new and f["severity"] in ("critical", "major") and f["level"] != "inferred" and not f["id"].startswith("regression:"):
                    out.append({"department": d["id"], "title": f"New since the previous report: {f['title']}", "level": f["level"], "kind": "new_finding"})
    return out


def blockers(R, earlier):
    """Unresolved blockers: P0 actions, each with the first report it appeared in (from the report history)."""
    out = []
    for a in R["actions"]:
        if a["priority"] != "P0": continue
        since = next((E["generated"] for E in earlier if any(f["key"] in a["findings"] for d in E.get("departments") or [] for f in d.get("findings") or [])), None)
        out.append({"title": a["title"], "departments": a["departments"], "level": a["level"], "do": a.get("do"), "why": a.get("why"), "open_since": since or R["generated"],
                    "first_seen_now": since is None})
    return out


def _title(R, ctx):
    t = None
    if R["project"].get("path"):   # a checkout names itself (a renamed game keeps its old title in older histories)
        from . import vision
        t = vision._readme_pitch(R["project"]["path"])[0]
    try:
        ph = _load(os.path.join(REPO, "studio", "departments", "playcraft", "history.py"))
        for root in (ph.store_root(), ph.archive_root()):
            g = _json(os.path.join(root, "games", R["project"]["id"], "game.json"))
            if g and g.get("title") and not t: t = g["title"]; break
    except Exception:
        pass
    if not t:
        for r in glob.glob(os.path.join(REPO, "history", "designcraft", R["project"]["id"], "*.json"))[-1:]:
            t = (_json(r) or {}).get("game", {}).get("title")
    return t or (R["project"].get("repo") or R["project"]["name"])


def executive(R):
    H = R["health"]; ds = R["departments"]; G = R["gates"]
    ev = [d for d in ds if d["quality"]["evaluation"] == "evaluated"]; ne = [d for d in ds if d["quality"]["evaluation"] == "not_evaluated"]
    s = []
    if H["score"] is None: s.append(f"{R['title']} has no overall score yet: no applicable department has a measured result.")
    else:
        vp = H.get("vs_previous") or {}
        tail = (f", {vp['delta']:+} since the previous report" if vp.get("delta") is not None else
                f"; the previous report's {vp['previous']} used another method, so no change is claimed" if vp.get("previous") is not None and "not comparable" in (vp.get("compare") or "") else "")
        s.append(f"{R['title']} scores **{H['score']}/100** ({H['band']}, {H['confidence']} confidence, {round(100 * H['coverage'])}% of the applicable weight evaluated{tail}).")
    if G.get("verdict"): s.append(f"Director verdict: **{G['verdict']}** for production `{G['production']}` ({G.get('status')})" + (f"; release {G['release_status']}" if G.get("release_status") else "") + ".")
    else: s.append("No production has run for this project, so there is no Director verdict or release gate.")
    s.append(f"{len(ev)} department(s) evaluated" + (f", {len(ne)} applicable but not evaluated ({', '.join(d['id'] for d in ne)})" if ne else "") + ".")
    if R["blockers"]: s.append(f"{len(R['blockers'])} unresolved blocker(s): resolve them before anything else.")
    if R["regressions"]: s.append(f"{len(R['regressions'])} measured regression(s) since the previous report.")
    if R["top_actions"]: s.append(f"Highest-impact next action: {R['top_actions'][0]['title']}.")
    if R["reconciliation"]["corroborated"]: s.append(f"{len(R['reconciliation']['corroborated'])} problem area(s) are flagged by several departments at once.")
    return s


def next_actions(R):
    out = []
    for a in R["actions"]:
        if a["priority"] in ("P0", "P1") and len(out) < 4: out.append(f"[{a['priority']}] {a['title']}" + (f" — {a['do']}" if a.get("do") else ""))
    for d in R["departments"]:
        if d.get("next") and len(out) < 7: out.append(d["next"])
    appr = [f for d in R["departments"] for f in d["findings"] if f.get("kind") == "approval"]
    if appr: out.append(f"{len(appr)} decision(s) wait for a person (approval is never automatic).")
    out.append("Report again after the changes land (Run GITCRAFT report) to measure progress against this report.")
    return out


# ---------------------------------------------------------------- Markdown
def markdown(R):
    H = R["health"]; P = R["project"]
    L = [f"# GITCRAFT report — {R['title']}", "", "_Production Report_", "",
         f"`{R['report_id']}` · generated {R['generated']} · refresh **{R['refresh']}** · read-only" +
         (f" · commit `{(P.get('head') or '')[:7]}`" if P.get("head") else "") + (f" · [{P['repo']}]({P['url']})" if P.get("url") else ""), "",
         "## Executive summary", ""] + [f"- {s}" for s in R["summary"]] + [""]
    I = R.get("identity") or {}; G = R.get("gates") or {}; vp = H.get("vs_previous") or {}
    L += ["## Production identity", "", "| Project | Run date | Release / version | Commit | Production | Director verdict |", "|---|---|---|---|---|---|",
          f"| {I.get('repo') or I.get('name') or '—'} | {R['generated'][:16].replace('T', ' ')} UTC | {I.get('version') or 'not recorded'} | {(I.get('commit') or '—')[:7]} | "
          f"{(I.get('production') or 'none run') + (' (' + str(I.get('production_status')) + ')' if I.get('production_status') else '')} | {G.get('verdict') or 'no verdict'} |", ""]
    L += ["## Overall health", "", "| Overall score | Band | Confidence | Evaluated departments | Coverage | vs previous |", "|---|---|---|---|---|---|",
          f"| {H['score'] if H['score'] is not None else '—'} | {H['band']} | {H['confidence']} | {H['measured']} of {H['of']} applicable | {round(100 * (H.get('coverage') or 0))}% | "
          f"{(format(vp['delta'], '+') + ' vs ' + str(vp['previous'])) if vp.get('delta') is not None else (vp.get('compare') or '—')} |", "", f"Basis: {H['basis']}.", ""]
    L += ["## Top 3 next actions", ""] + ([f"{i}. **{a['title']}** — impact {a['impact']}, effort {a['effort'] or 'not estimated'} ({a['effort_basis']})" + (f"<br>Do: {a['do']}" if a.get("do") else "")
                                         for i, a in enumerate(R.get("top_actions") or [], 1)] or ["- None."]) + ["", f"_{scoring.EFFORT_NOTE}_", ""]
    L += ["## Department scorecards", "", "| Department | Score | Previous | Delta | Weight | Rubric | Status | Findings |", "|---|---|---|---|---|---|---|---|"]
    for d in R["departments"]:
        q = d["quality"]
        if q["evaluation"] == "not_applicable": continue
        L.append(f"| {d['title']} | {q['value'] if q['evaluation'] == 'evaluated' else 'Not Evaluated'} ({q['label']}) | {q['previous'] if q.get('previous') is not None else '—'} | "
                 f"{format(q['delta'], '+') if q.get('delta') is not None else (q.get('compare') or '—')} | {q['weight']} | `{q['rubric']}` | {STATUS_LABEL[d['status']]} | {len(d['findings'])} |")
    L.append("")
    L += ["## Release gates and approvals", ""] + ([f"- {c['title']}: **{c['status'].replace('_', ' ')}**" for c in G.get("criteria") or []] or [f"- {G.get('note') or 'None recorded.'}"]) + \
         ["", "Gates are pass/fail and never part of a quality score.", ""]
    T = R.get("trend") or []
    L += ["## Trends", ""] + (["First report: trends start with the next one."] if len(T) < 2 else
                              [f"- Overall: " + " → ".join(f"{'—' if p['overall'] is None else p['overall']} ({p['method']})" for p in T)]
                              + [f"- {d['quality']['label']}: " + " → ".join('—' if (p['departments'].get(d['id']) or {}).get('value') is None else str(p['departments'][d['id']]['value']) for p in T)
                                 for d in R["departments"] if d["quality"]["evaluation"] == "evaluated"]) + [""]
    L += ["## Major findings", ""] + ([f"- **{f['severity']}** · {LEVEL_LABEL[f['level']]} — {f['title']} ({f['department']})" for f in R.get("major_findings") or []] or ["- None."]) + [""]
    L += ["## Regressions", ""] + ([f"- {x['title']} ({x['department']}, {LEVEL_LABEL.get(x['level'], x['level'])})" for x in R.get("regressions") or []]
                                 or ["- First report: nothing to compare yet." if R["changes"].get("first") else "- None measured."]) + [""]
    quiet = [d for d in R["departments"] if d["status"] in ("no_data", "not_applicable") and not d["findings"] and not d.get("next")]
    if quiet: L += ["No results for this project (nothing to report, nothing assumed): " + ", ".join(d["title"].split(" — ")[0] + f" ({STATUS_LABEL[d['status']].lower()})" for d in quiet) + ".", ""]
    for d in R["departments"]:
        if d in quiet: continue
        L += [f"### {d['title']}", "", f"Status: **{STATUS_LABEL[d['status']]}**" + (f" · run `{d['run']['id']}` ({(d['run'].get('at') or '')[:10]})" if d.get("run") else "")
              + (f" · score **{d['score']['value']}** ({d['score'].get('confidence')} confidence)" if d.get("score") and d["score"].get("value") is not None else ""), ""]
        for n in d["notes"]: L.append(f"- {n}")
        if d["refresh"].get("detail"): L.append(f"- Refresh: {d['refresh']['detail']}")
        if d.get("next"): L.append(f"- Next: {d['next']}")
        for f in d["findings"][:8]:
            L.append(f"- **{f['severity']}** · {LEVEL_LABEL[f['level']]} — {f['title']}" + (f": {f['evidence']}" if f.get("evidence") else ""))
        if len(d["findings"]) > 8: L.append(f"- … {len(d['findings']) - 8} more in report.json")
        L.append("")
    L += ["## Critical issues and blockers", ""] + ([f"- {b['title']} ({', '.join(b['departments'])}; {LEVEL_LABEL.get(b['level'], b['level'])}; open since {b['open_since'][:10]})" for b in R.get("blockers") or []]
                                                   or ["- None measured."]) + [""]
    rc = R["reconciliation"]
    L += ["## Cross-department findings", ""]
    L += ["**Corroborated (one fix, several departments)**", ""] + ([f"- {c['title']}: {', '.join(c['departments'])} ({c['count']} findings)" for c in rc["corroborated"]] or ["- None."]) + [""]
    L += ["**Conflicts**", ""] + ([f"- {c['title']} — {c['detail']}" for c in rc["conflicts"]] or ["- None found."]) + [""]
    L += ["**Dependencies**", ""] + ([f"- {c['title']} — {c['detail']}" for c in rc["dependencies"]] or ["- None."]) + [""]
    L += ["**Gaps (no data)**", ""] + ([f"- {g['title']} — {g['detail']}" for g in rc["gaps"]] or ["- None."]) + [""]
    L += ["## Prioritized action plan", ""]
    for p in ("P0", "P1", "P2", "P3"):
        its = [a for a in R["actions"] if a["priority"] == p]
        L += [f"### {p} ({len(its)})", ""] + ([f"{a['n']}. {a['title']} — {', '.join(a['departments'])} · {LEVEL_LABEL[a['level']]}" + (f"<br>Do: {a['do']}" if a.get("do") else "") for a in its[:25]] or ["- None."]) + [""]
    C = R["changes"]
    L += ["## Changes since the previous report", ""]
    if C.get("first"): L += [C["note"], ""]
    else:
        h = C["health"]
        L += [f"Against `{C['against']}` ({C['at'][:10]}): health {h.get('from')} → {h.get('to')}" + (f" ({h['delta']:+})" if h.get("delta") is not None else ""), ""]
        L += [f"- {x['id']}: {x['change']}" for x in C["departments"]] or ["- No department changed."]
        L += ["", f"New findings: {len(C['new_findings'])} · resolved or no longer reported: {len(C['resolved_findings'])}", "", C["note"], ""]
    L += ["## Recommended next actions", ""] + [f"{i}. {s}" for i, s in enumerate(R["next_actions"], 1)] + [""]
    L += ["## Scoring method", "", f"Overall: `{H.get('method')}`. Each department's score is its own measured result under the rubric below; the overall score is the weighted mean "
          "of the evaluated departments only. Not Evaluated departments carry no weight and are never filled in. A previous score is compared only under the same rubric and department method.", "",
          "| Department | Score | Weight | Rubric | Source |", "|---|---|---|---|---|"] + \
         [f"| {d['title'].split(' — ')[0]} | {d['quality']['label']} | {d['quality']['weight']} | `{d['quality']['rubric']}` | {d['quality']['source']} |" for d in R["departments"] if d["quality"]["evaluation"] != "not_applicable"] + [""]
    L += _creative_md(R.get("creative"))
    L += ["## Evidence and limits", "", "- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).",
          "- **Observed**: seen while playing or simulated, not a hard measurement.", "- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.",
          "- **Unavailable**: no data; nothing is filled in for it."] + [f"- Not refreshed — {x['department']}: {x['why']}" for x in R["not_refreshed"]] + \
         [f"- {x['department']}: {x['status']} — {x['why']}" for x in R["unavailable"]] + ["", "Report generation is read-only: it changed no code, merged nothing and deployed nothing.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- HTML (self-contained, mobile-first)
CSS = """
:root{--bg:#f4f5f2;--card:#fff;--ink:#16191a;--mute:#5d6663;--line:#e1e4df;--accent:#1d6f66;--accent-2:#9fd3cb;--chip:#ebeeea;
--ok:#1e7a46;--ok-bg:#e3f2e8;--warn:#9a6212;--warn-bg:#f8eedb;--bad:#b3261e;--bad-bg:#f9e3e1;--p0:#b3261e;--p1:#c46510;--p2:#2b62c4;--p3:#6b7280;
--serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Charter,Georgia,serif;--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0e1211;--card:#161b1a;--ink:#e6ebe9;--mute:#9ba6a2;--line:#27302e;--accent:#5cc2b5;--accent-2:#2c5d57;--chip:#1f2725;
--ok:#6ad19a;--ok-bg:#16301f;--warn:#e5b062;--warn-bg:#33291a;--bad:#f08a80;--bad-bg:#3a1f1d;color-scheme:dark}}
:root[data-theme=dark]{--bg:#0e1211;--card:#161b1a;--ink:#e6ebe9;--mute:#9ba6a2;--line:#27302e;--accent:#5cc2b5;--accent-2:#2c5d57;--chip:#1f2725;
--ok:#6ad19a;--ok-bg:#16301f;--warn:#e5b062;--warn-bg:#33291a;--bad:#f08a80;--bad-bg:#3a1f1d;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--sans);-webkit-text-size-adjust:100%;font-variant-numeric:tabular-nums}
main{max-width:960px;margin:0 auto;padding:12px max(16px,env(safe-area-inset-right)) calc(48px + env(safe-area-inset-bottom)) max(16px,env(safe-area-inset-left))}
a{color:var(--accent)}code{font:12px var(--mono);overflow-wrap:anywhere}
header.top{padding:18px 0 6px}.k{font:600 11px/1 var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
h1{font:600 32px/1.12 var(--serif);margin:8px 0 12px;text-wrap:balance;letter-spacing:-.01em}
h2{font:600 21px/1.25 var(--serif);margin:36px 0 12px;text-wrap:balance}h3{font-size:15px;margin:0;line-height:1.3}
.ident{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:2px 16px;margin:0;font-size:13px}
.ident div{min-width:0;padding:6px 0;border-top:1px solid var(--line)}.ident dt{color:var(--mute);font-size:11px;letter-spacing:.06em;text-transform:uppercase}.ident dd{margin:0;overflow-wrap:anywhere}
nav.jump{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;display:flex;gap:6px;overflow-x:auto;padding:10px 0;margin:8px 0 0;background:var(--bg);scrollbar-width:none}
nav.jump::-webkit-scrollbar{display:none}nav.jump a{flex:none;font-size:13px;padding:8px 13px;border-radius:99px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;min-height:36px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:10px 0}
.hero{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:12px}
.hero .card{margin:0}.big{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap}.big b{font:600 64px/0.9 var(--serif);letter-spacing:-.02em}.big span{color:var(--mute);font-size:15px;padding-bottom:6px}
.bar{position:relative;height:8px;border-radius:9px;background:var(--chip);margin:14px 0 8px}.bar i{position:absolute;inset:0 auto 0 0;border-radius:9px;background:var(--accent)}
.bar s{position:absolute;top:-4px;width:2px;height:16px;background:var(--ink);opacity:.55;text-decoration:none}
.chips{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.chip{display:inline-flex;align-items:center;font-size:12px;font-weight:600;padding:3px 9px;border-radius:99px;background:var(--chip);color:var(--mute);max-width:100%}
.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.warn{background:var(--warn-bg);color:var(--warn)}.chip.bad{background:var(--bad-bg);color:var(--bad)}.chip.acc{color:var(--accent)}
.verdict{display:flex;flex-direction:column;gap:8px}.verdict .v{font:600 26px/1.1 var(--serif)}.verdict.ok{border-color:var(--ok)}.verdict.bad{border-color:var(--bad)}.verdict.warn{border-color:var(--warn)}
.verdict.ok .v{color:var(--ok)}.verdict.bad .v{color:var(--bad)}.verdict.warn .v{color:var(--warn)}
ul.sum{margin:14px 0 0;padding-left:18px}ul.sum li{margin:5px 0;max-width:72ch}
.small{font-size:13px;color:var(--mute)}.top3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.top3 .card{margin:0;display:flex;flex-direction:column;gap:8px}
.top3 .n{font:600 13px var(--mono);color:var(--accent)}.top3 h3{font-size:15px}
.drow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:4px 14px;padding:14px 0;border-top:1px solid var(--line)}.drow:first-child{border-top:0;padding-top:4px}
.drow .nm{min-width:0}.drow .fam{font-size:11px;color:var(--mute);text-transform:uppercase;letter-spacing:.06em}.drow .val{text-align:right}
.drow .val b{font:600 26px/1 var(--serif)}.drow .val .ne{font-size:13px;font-weight:600;color:var(--mute)}.drow .meta{grid-column:1/-1}.drow .bar{margin:6px 0 4px}
.delta{font-size:12px;font-weight:600}.delta.up{color:var(--ok)}.delta.down{color:var(--bad)}.delta.flat{color:var(--mute)}
details{margin-top:6px}summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--accent);min-height:44px;display:flex;align-items:center;list-style:none}
summary::-webkit-details-marker{display:none}summary::before{content:"\\25B8";margin-right:6px}details[open]>summary::before{content:"\\25BE"}
.f{border-top:1px solid var(--line);padding:9px 0;font-size:14px}.f:first-child{border-top:0}
.tag{display:inline-block;font-size:11px;font-weight:600;padding:1px 7px;border-radius:6px;margin-right:4px;background:var(--chip);color:var(--mute)}
.tag.critical{color:#fff;background:var(--p0)}.tag.major{color:#fff;background:var(--p1)}.tag.verified{color:var(--ok)}.tag.observed{color:var(--p2)}.tag.inferred{color:var(--warn)}
.act{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--line)}.act:first-child{border-top:0}.pr{flex:none;font-size:12px;font-weight:700;color:#fff;border-radius:6px;padding:2px 7px;height:fit-content}
.pr.P0{background:var(--p0)}.pr.P1{background:var(--p1)}.pr.P2{background:var(--p2)}.pr.P3{background:var(--p3)}.act .do{font-size:13px;color:var(--mute);margin-top:2px}
.x{padding:8px 0;border-top:1px solid var(--line)}.x:first-of-type{border-top:0}ol.next li{margin:6px 0}
.chart{width:100%;height:auto;display:block}.chart text{font:11px var(--sans);fill:var(--mute)}.chart .g{stroke:var(--line);stroke-width:1}
.chart .ln{fill:none;stroke:var(--accent);stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}.chart .pt{fill:var(--card);stroke:var(--accent);stroke-width:2}
.chart .last{fill:var(--accent)}.chart .mc{stroke:var(--warn);stroke-dasharray:3 3}.chart .mct{fill:var(--warn)}
.multi{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}.multi .card{margin:0;padding:12px 14px}
.gate{display:flex;justify-content:space-between;gap:10px;align-items:center;padding:9px 0;border-top:1px solid var(--line);font-size:14px}.gate:first-child{border-top:0}
.cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.cols .card{margin:0}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:7px 10px;border-bottom:1px solid var(--line)}th{color:var(--mute);font-weight:600}
footer{color:var(--mute);font-size:12px;margin-top:36px;text-align:center}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.narrow{display:none}
@media (max-width:720px){.hero,.top3,.cols{grid-template-columns:1fr}.wide{display:none}.narrow{display:block}}
@media (max-width:520px){h1{font-size:26px}.big b{font-size:52px}.card{padding:15px}}
"""


def _e(s): return html.escape(str("—" if s is None else s))


def _delta_html(q):
    d = q.get("delta")
    if d is None: return f"<span class='delta flat'>{_e(q.get('compare') or '')}</span>"
    cls = "up" if d > 0 else "down" if d < 0 else "flat"
    return f"<span class='delta {cls}'>{d:+} vs {_e(q['previous'])}</span>" + (f" <span class='small'>· {_e(q['compare'])}</span>" if q.get("compare") else "")


def _verdict_cls(v):
    v = str(v or "")
    return "ok" if v.startswith("READY") else "bad" if v.startswith("NOT READY") else "warn" if v else ""


def chart_svg(points, key=None, w=640, h=180, label=True):
    """A 0–100 line chart of report points (oldest first). The line breaks where a value is missing or the scoring
    method changed between two points; a method change is marked. Pure SVG, no script."""
    vals = []
    for p in points:
        if key is None: vals.append((p.get("overall"), p.get("method")))
        else:
            d = (p.get("departments") or {}).get(key) or {}
            vals.append((d.get("value"), d.get("rubric")))
    padl, padr, padt, padb = (30, 12, 12, 22) if label else (4, 4, 6, 6)
    iw, ih = w - padl - padr, h - padt - padb
    n = len(vals)
    X = lambda i: padl + (iw * (i / (n - 1)) if n > 1 else iw / 2)
    Y = lambda v: padt + ih * (1 - v / 100)
    o = [f"<svg class='chart' viewBox='0 0 {w} {h}' role='img' aria-label='{'Overall' if key is None else _e(key)} score by report, 0 to 100'>"]
    for g in (0, 50, 100) if label else (50,):
        o.append(f"<line class='g' x1='{padl}' x2='{w - padr}' y1='{Y(g):.1f}' y2='{Y(g):.1f}'/>")
        if label: o.append(f"<text x='{padl - 6}' y='{Y(g) + 4:.1f}' text-anchor='end'>{g}</text>")
    seg = []
    for i, (v, m) in enumerate(vals):
        if i and vals[i - 1][1] != m and v is not None:
            o.append(f"<line class='mc' x1='{(X(i - 1) + X(i)) / 2:.1f}' x2='{(X(i - 1) + X(i)) / 2:.1f}' y1='{padt}' y2='{h - padb}'/>")
            if label:
                mx = (X(i - 1) + X(i)) / 2; right = mx + 100 > w - padr   # keep the label inside the chart
                o.append(f"<text class='mct' x='{mx + (-4 if right else 4):.1f}' y='{padt + 10}' text-anchor='{'end' if right else 'start'}'>method changed</text>")
            if len(seg) > 1: o.append("<polyline class='ln' points='" + " ".join(seg) + "'/>")
            seg = []
        if v is None:
            if len(seg) > 1: o.append("<polyline class='ln' points='" + " ".join(seg) + "'/>")
            seg = []; continue
        seg.append(f"{X(i):.1f},{Y(v):.1f}")
    if len(seg) > 1: o.append("<polyline class='ln' points='" + " ".join(seg) + "'/>")
    for i, (v, m) in enumerate(vals):
        if v is None: continue
        last = i == n - 1
        o.append(f"<circle class='{'pt last' if last else 'pt'}' cx='{X(i):.1f}' cy='{Y(v):.1f}' r='{4 if label else 3}'><title>{_e(points[i]['at'][:16].replace('T', ' '))}: {v}</title></circle>")
        if label and (last or i == 0): o.append(f"<text x='{X(i):.1f}' y='{Y(v) - 9:.1f}' text-anchor='middle' style='fill:var(--ink);font-weight:600'>{v}</text>")
    if label and n:
        o.append(f"<text x='{X(0):.1f}' y='{h - 5}' text-anchor='{'start' if n > 1 else 'middle'}'>{_e(points[0]['at'][:10])}</text>")
        if n > 1: o.append(f"<text x='{X(n - 1):.1f}' y='{h - 5}' text-anchor='end'>{_e(points[-1]['at'][:10])}</text>")
    o.append("</svg>")
    return "".join(o)


def render_html(R, back=None, downloads=True, evidence_base=None):
    H = R["health"]; P = R["project"]; G = R.get("gates") or {}; I = R.get("identity") or {}
    md = lambda s: re.sub(r"`(.+?)`", r"<code>\1</code>", re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _e(s)))
    band = slug(H["band"]); bcls = {"healthy": "ok", "needs-attention": "warn", "at-risk": "bad", "blocked": "bad"}.get(band, "")
    o = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>",
         f"<title>{_e(R['title'])} · Production Report</title><meta name='description' content='GITCRAFT Production Report for {_e(R['title'])}: department scores, release gates and next actions.'>"
         f"<style>{CSS}</style></head><body><main>"]
    if back: o.append(f"<p class='small' style='margin:8px 0 0'><a href='{_e(back)}'>← All reports</a></p>")
    run_date = R["generated"][:16].replace("T", " ") + " UTC"
    o.append("<header class='top'><div class='k'>GITCRAFT · Production Report</div>"
             f"<h1>{_e(R['title'])}</h1><dl class='ident'>"
             + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in (
                 ("Project", f"<a href='{_e(I.get('url'))}'>{_e(I.get('repo'))}</a>" if I.get("url") else _e(I.get("repo") or I.get("name"))),
                 ("Run date", _e(run_date)),
                 ("Release / version", _e(I.get("version") or "not recorded") + (f" <span class='small'>({_e(I['version_source'])})</span>" if I.get("version_source") else "")),
                 ("Commit", (f"<code>{_e((I.get('commit') or '')[:7])}</code> <span class='small'>{_e(I.get('commit_source'))}</span>") if I.get("commit") else "not recorded"),
                 ("Production", _e(I.get("production") or "none run") + (f" · {_e(I.get('production_status'))}" if I.get("production_status") else "")),
                 ("Report", f"<code>{_e(R['report_id'].split('/')[-1])}</code>" + (" · <a href='report.json'>JSON</a> · <a href='report.md'>Markdown</a>" if downloads else ""))))
             + "</dl></header>")
    o.append("<nav class='jump' aria-label='Sections'>" + "".join(f"<a href='#{i}'>{t}</a>" for i, t in (("health", "Summary"), ("top", "Next 3"), ("depts", "Departments"), ("trends", "Trends"),
             ("gates", "Release gates"), ("findings", "Findings"), ("p0", "Blockers"), ("plan", "Action plan"), ("method", "Scoring"), ("limits", "Evidence")) + ((("creative", "Creative (advisory)"),) if R.get("creative") else ())) + "</nav>")
    # hero: the quality score and, apart from it, the Director's verdict (a gate)
    vp = H.get("vs_previous") or {}
    sc = H["score"]
    o.append("<section id='health' class='hero'><div class='card'><div class='k'>Overall quality score</div>"
             f"<div class='big'><b>{_e(sc if sc is not None else '—')}</b><span>/ 100</span></div>"
             + (f"<div class='bar'><i style='width:{max(0, min(100, sc))}%'></i>" + (f"<s style='left:calc({vp['previous']}% - 1px)' title='previous {vp['previous']}'></s>" if vp.get("delta") is not None else "") + "</div>" if sc is not None else "")
             + f"<div class='chips'><span class='chip {bcls}'>{_e(H['band'].capitalize())}</span><span class='chip'>{_e(H['confidence'])} confidence</span>"
             f"<span class='chip'>{H['measured']} of {H['of']} departments evaluated · {round(100 * (H.get('coverage') or 0))}% weight</span></div>"
             f"<p class='small' style='margin:10px 0 0'>{_delta_html({'delta': vp.get('delta'), 'previous': vp.get('previous'), 'compare': vp.get('compare')})}</p></div>")
    vc = _verdict_cls(G.get("verdict"))
    if G.get("verdict"):
        np_ = sum(1 for c in G.get("criteria") or [] if c["status"] in ("passed", "advisory"))
        o.append(f"<div class='card verdict {vc}'><div class='k'>Director verdict · release gate</div><div class='v'>{_e(G['verdict'])}</div>"
                 f"<div class='chips'><span class='chip'>{np_}/{len(G.get('criteria') or [])} gates passed</span>"
                 + (f"<span class='chip'>{_e(G.get('status'))}</span>" if G.get("status") else "") + (f"<span class='chip'>release {_e(G.get('release_status'))}</span>" if G.get("release_status") else "")
                 + (f"<span class='chip warn'>{len(G['approvals'])} awaiting approval</span>" if G.get("approvals") else "") + "</div>"
                 + "".join(f"<div class='small'>{_e(r)}</div>" for r in (G.get("reasons") or [])[:3]) + "</div>")
    else:
        o.append(f"<div class='card verdict'><div class='k'>Director verdict · release gate</div><div class='v' style='color:var(--mute)'>No verdict</div><div class='small'>{_e(G.get('note'))}</div></div>")
    o.append("</section><div class='card'><div class='k'>Executive summary</div><ul class='sum'>" + "".join(f"<li>{md(s)}</li>" for s in R["summary"]) + "</ul></div>")
    if R.get("creative"): o.append(_creative_card(R["creative"]))
    # the three highest-impact next actions
    o.append("<h2 id='top'>Three highest-impact next actions</h2>")
    if R.get("top_actions"):
        o.append("<div class='top3'>")
        for i, a in enumerate(R["top_actions"], 1):
            ic = "bad" if a["impact"].startswith("High") else "warn" if a["impact"].startswith("Medium") else ""
            o.append(f"<article class='card'><span class='n'>{i:02d} · {a['priority']}</span><h3>{_e(a['title'])}</h3>"
                     f"<div class='chips'><span class='chip {ic}' title='{_e(a['impact_basis'])}'>Impact: {_e(a['impact'])}</span>"
                     f"<span class='chip' title='{_e(a['effort_basis'])}'>Effort: {_e(a['effort'] or 'not estimated')}</span><span class='tag {a['level']}'>{_e(LEVEL_LABEL.get(a['level'], a['level']))}</span></div>"
                     + (f"<div class='small'>{_e(a['why'])}</div>" if a.get("why") else "") + (f"<div class='small'><b>Do:</b> {_e(a['do'])}</div>" if a.get("do") else "")
                     + f"<div class='small'>{_e(', '.join(a['departments']))}</div></article>")
        o.append("</div><p class='small'>Impact follows the priority rule (P0/P1 high, P2 medium, P3 low). " + _e(scoring.EFFORT_NOTE) + "</p>")
    else: o.append("<div class='card small'>No actions: no department reported a finding.</div>")
    # department scores
    o.append("<h2 id='depts'>Department scores</h2><div class='card'>")
    shown = [d for d in R["departments"] if d["quality"]["evaluation"] != "not_applicable"]
    shown.sort(key=lambda d: (d["quality"]["evaluation"] != "evaluated", -(d["quality"]["weight"] or 0)))
    for d in shown:
        q = d["quality"]; title, _, sub = d["title"].partition(" — ")
        o.append(f"<div class='drow'><div class='nm'><div class='fam'>{_e(q['label'])} · weight {q['weight']}</div><h3>{_e(title)}</h3><div class='small'>{_e(sub or d['summary'])}</div></div>")
        if q["evaluation"] == "evaluated":
            o.append(f"<div class='val'><b>{_e(q['value'])}</b><div>{_delta_html(q)}</div></div><div class='meta'><div class='bar'><i style='width:{max(0, min(100, q['value']))}%'></i>"
                     + (f"<s style='left:calc({q['previous']}% - 1px)' title='previous {q['previous']}'></s>" if q.get("previous") is not None and q.get("delta") is not None else "") + "</div>")
        else:
            o.append(f"<div class='val'><span class='ne'>Not Evaluated</span></div><div class='meta'><div class='small'>{_e(q.get('why'))}</div>")
        bits = [f"<span class='chip {'ok' if d['status'] in ('current', 'refreshed') else 'warn' if d['status'] in ('stale', 'unverified') else ''}'>{_e(STATUS_LABEL[d['status']])}</span>"]
        if d.get("run") and d["run"].get("at"): bits.append(f"<span class='small'>measured {_e(str(d['run']['at'])[:10])}</span>")
        if q.get("confidence") and q["evaluation"] == "evaluated": bits.append(f"<span class='small'>{_e(q['confidence'])} confidence</span>")
        if q.get("coverage") is not None and q["evaluation"] == "evaluated": bits.append(f"<span class='small'>coverage {round(100 * q['coverage']) if q['coverage'] <= 1 else q['coverage']}%</span>")
        o.append("<div class='chips' style='margin-top:4px'>" + "".join(bits) + "</div>")
        o.append("<details><summary>Criteria, evidence and findings</summary>"
                 f"<p class='small' style='margin:2px 0'><b>Rubric</b> <code>{_e(q['rubric'])}</code> — {_e(q['source'])}</p><ul class='small' style='margin:4px 0;padding-left:18px'>"
                 + "".join(f"<li>{_e(c)}</li>" for c in q["criteria"]) + "</ul>"
                 + (f"<p class='small' style='margin:4px 0'><b>Basis:</b> {_e(q['basis'])}</p>" if q.get("basis") else "")
                 + "".join(f"<p class='small' style='margin:4px 0'>{_e(n)}</p>" for n in d["notes"])
                 + (f"<p class='small' style='margin:4px 0'>Refresh: {_e(d['refresh']['detail'])}</p>" if d["refresh"].get("detail") else "")
                 + (f"<p class='small' style='margin:4px 0'><b>Next:</b> {_e(d['next'])}</p>" if d.get("next") else ""))
        for f in d["findings"][:10]:
            o.append(f"<div class='f'><span class='tag {f['severity']}'>{f['severity']}</span><span class='tag {f['level']}'>{_e(LEVEL_LABEL[f['level']])}</span> {_e(f['title'])}"
                     + (f"<div class='small'>{_e(f['evidence'])}</div>" if f.get("evidence") else "") + "</div>")
        if len(d["findings"]) > 10: o.append(f"<p class='small'>… {len(d['findings']) - 10} more in report.json</p>")
        o.append("</details></div></div>")
    na = [d for d in R["departments"] if d["quality"]["evaluation"] == "not_applicable"]
    o.append("</div>" + (f"<p class='small'>Not applicable to this project (nothing made or asked for): {_e(', '.join(d['title'].split(' — ')[0] for d in na))}.</p>" if na else ""))
    # trends
    T = R.get("trend") or []
    o.append("<h2 id='trends'>Trends</h2>")
    if len(T) < 2: o.append("<div class='card small'>This is the first report for this project: trends start with the next one.</div>")
    else:
        o.append(f"<div class='card'><div class='k'>Overall score · {len(T)} reports</div><div class='wide'>{chart_svg(T)}</div><div class='narrow'>{chart_svg(T, w=340, h=190)}</div><p class='small' style='margin:4px 0 0'>Points from different scoring methods are never joined; a dashed line marks a method change.</p></div><div class='multi'>")
        for d in shown:
            if d["quality"]["evaluation"] != "evaluated" and not any(((p["departments"].get(d["id"]) or {}).get("value") is not None) for p in T): continue
            vs = [(p["departments"].get(d["id"]) or {}).get("value") for p in T]
            o.append(f"<div class='card'><div class='small'><b style='color:var(--ink)'>{_e(d['quality']['label'])}</b> · {sum(v is not None for v in vs)} measured</div>{chart_svg(T, d['id'], w=220, h=56, label=False)}"
                     f"<div class='small'>{' → '.join('—' if v is None else str(v) for v in vs[-5:])}</div></div>")
        o.append("</div>")
    # release gates and approvals (pass/fail, never averaged)
    o.append("<h2 id='gates'>Release gates and approvals</h2><div class='card'>")
    if G.get("criteria"):
        stc = {"passed": "ok", "advisory": "ok", "failed": "bad", "not_planned": "bad", "needs_approval": "warn", "blocked": "warn", "unverified": "warn", "pending": ""}
        for c in G["criteria"]:
            o.append(f"<div class='gate'><span>{_e(c['title'])}</span><span class='chip {stc.get(c['status'], '')}'>{_e(c['status'].replace('_', ' '))}</span></div>")
        o.append("<p class='small'>Gates are pass/fail. They decide the Director's verdict and never add to or subtract from a quality score.</p>")
    else: o.append(f"<p class='small' style='margin:0'>{_e(G.get('note') or 'No release gates recorded.')}</p>")
    o.append("</div>")
    # findings, regressions, blockers
    o.append("<h2 id='findings'>Major findings, regressions and blockers</h2><div class='cols'>")
    o.append("<div class='card'><div class='k'>Major findings</div>" + ("".join(
        f"<div class='f'><span class='tag {f['severity']}'>{f['severity']}</span><span class='tag {f['level']}'>{_e(LEVEL_LABEL[f['level']])}</span> {_e(f['title'])}<div class='small'>{_e(f['department'])}</div></div>"
        for f in R.get("major_findings") or []) or "<p class='small'>No critical or major findings.</p>") + "</div>")
    o.append("<div class='card'><div class='k'>Regressions</div>" + ("".join(
        f"<div class='f'>{_e(x['title'])}<div class='small'>{_e(x['department'])} · {_e(LEVEL_LABEL.get(x['level'], x['level']))}</div></div>" for x in R.get("regressions") or [])
        or ("<p class='small'>First report: nothing to compare yet.</p>" if R["changes"].get("first") else "<p class='small'>No measured regression since the previous report.</p>")) + "</div>")
    o.append("<div class='card' id='p0'><div class='k'>Unresolved blockers</div>" + ("".join(
        f"<div class='f'><span class='pr P0'>P0</span> {_e(b['title'])}<div class='small'>{_e(', '.join(b['departments']))} · open since {_e(b['open_since'][:10])}</div></div>" for b in R.get("blockers") or [])
        or "<p class='small'>No measured blockers.</p>") + "</div></div>")
    # cross-department + full plan + changes (the earlier report's sections, kept)
    rc = R["reconciliation"]
    o.append("<h2 id='cross'>Cross-department findings</h2><div class='card'>")
    for key, label, empty in (("corroborated", "Corroborated — one fix, several departments", "None."), ("conflicts", "Conflicts", "None found."),
                              ("dependencies", "Dependencies", "None."), ("gaps", "Gaps — no data", "None.")):
        o.append(f"<h3 style='margin:8px 0 4px'>{label}</h3>")
        if not rc[key]: o.append(f"<p class='small' style='margin:0'>{empty}</p>")
        for c in rc[key]:
            if key == "corroborated":
                o.append(f"<div class='x'><b>{_e(c['title'])}</b> <span class='small'>· {_e(', '.join(c['departments']))} · {c['count']} findings</span><div class='small'>" +
                         "; ".join(_e(f"{x['department']}: {x['title']}") for x in c["findings"][:4]) + "</div></div>")
            else: o.append(f"<div class='x'><b>{_e(c['title'])}</b><div class='small'>{_e(c['detail'])}</div></div>")
    o.append("</div><h2 id='plan'>Prioritized action plan</h2>")
    for p in ("P0", "P1", "P2", "P3"):
        its = [a for a in R["actions"] if a["priority"] == p]
        o.append(f"<details class='card' {'open' if p in ('P0', 'P1') else ''}><summary>{p} · {len(its)} action(s)</summary>" + ("".join(_act(a) for a in its[:30]) or "<p class='small'>None.</p>")
                 + (f"<p class='small'>… {len(its) - 30} more in report.json</p>" if len(its) > 30 else "") + "</details>")
    C = R["changes"]
    o.append("<h2 id='changes'>Changes since the previous report</h2><div class='card'>")
    if C.get("first"): o.append(f"<p class='small' style='margin:0'>{_e(C['note'])}</p>")
    else:
        o.append(f"<p style='margin:0 0 8px'>Against <code>{_e(C['against'])}</code> ({_e(C['at'][:10])}): {_delta_html({'delta': vp.get('delta'), 'previous': vp.get('previous'), 'compare': vp.get('compare')})}</p>")
        for x in C["departments"]: o.append(f"<div class='x small'><b>{_e(x['id'])}</b>: {_e(x['change'])}</div>")
        o.append(f"<p class='small'>{len(C['new_findings'])} new finding(s), {len(C['resolved_findings'])} resolved or no longer reported. {_e(C['note'])}</p>")
    o.append("</div><h2 id='next'>Recommended next actions</h2><div class='card'><ol class='next'>" + "".join(f"<li>{_e(s)}</li>" for s in R["next_actions"]) + "</ol></div>")
    # scoring method
    o.append("<h2 id='method'>How the scores work</h2><div class='card'><p style='margin-top:0'>Each department's 0–100 score is its own measured result under a published rubric. "
             f"The overall score is the weighted mean of the <b>evaluated</b> departments only (method <code>{_e(H.get('method'))}</code>); departments that apply but have no measured result are "
             "<b>Not Evaluated</b>, carry no weight and are never filled in. Coverage shows how much of the applicable weight was evaluated. Release gates and approvals are separate pass/fail states. "
             "A previous score is compared only when the rubric and the department's own method are unchanged.</p><div class='tbl'><table><tr><th>Department</th><th>Score</th><th>Weight</th><th>Rubric</th><th>Source</th></tr>"
             + "".join(f"<tr><td>{_e(d['title'].split(' — ')[0])}</td><td>{_e(d['quality']['label'])}</td><td>{d['quality']['weight']}</td><td><code>{_e(d['quality']['rubric'])}</code></td><td>{_e(d['quality']['source'])}</td></tr>" for d in shown)
             + f"</table></div><p class='small' style='margin-bottom:0'>{_e(H['basis'])}.</p></div>")
    if R.get("creative"): o.append(_creative_section(R["creative"], evidence_base))
    o.append("<h2 id='limits'>Evidence and limits</h2><div class='card small'><p style='margin-top:0'><span class='tag verified'>Verified</span> measured by a department tool · "
             "<span class='tag observed'>Observed</span> seen in play or simulated · <span class='tag inferred'>Inferred (assumption)</span> a judgement to confirm · "
             "<b>Not Evaluated</b> no measured result, nothing filled in.</p>" + "".join(f"<p>Not refreshed — {_e(x['department'])}: {_e(x['why'])}</p>" for x in R["not_refreshed"])
             + "".join(f"<p>{_e(x['department'])}: {_e(STATUS_LABEL.get(x['status']))} — {_e(x['why'])}</p>" for x in R["unavailable"])
             + "<p style='margin-bottom:0'>Report generation is read-only: it changed no code, merged nothing and deployed nothing.</p></div>")
    o.append(f"<footer>GITCRAFT Production Report {VERSION} · <code>{_e(R['report_id'])}</code></footer></main></body></html>")
    return "".join(o)


BASIS_CLS = {"observed_render": "observed", "observed_interaction": "observed", "source_analysis": "verified", "hypothesis_playtest": "inferred"}


def _basis(b):
    return f"<span class='tag {BASIS_CLS.get(b, '')}'>{_e(creative.BASES.get(b, b))}</span>"


def _creative_head(C):
    B = C.get("bound_to") or {}
    return (f"Judgement by {_e(C.get('reviewer'))} · {_e(str(C.get('created'))[:10])} · commit <code>{_e(str(B.get('commit') or '')[:7])}</code> · "
            f"vision v{_e(B.get('vision_version'))} " + ("<span class='chip warn'>unapproved draft</span>" if B.get("vision_status") != "approved" else "<span class='chip ok'>approved</span>"))


def _creative_card(C):
    """The advisory Creative Opportunity summary near the top: only a current review's content, never a stale one's."""
    o = ["<section class='card' style='border-style:dashed'><div class='k'>Creative opportunities · advisory judgement, not scored</div>"]
    if C["status"] != "current":
        o.append(f"<p class='small' style='margin:8px 0 0'>A Creative Review exists ({_e(C.get('review_id'))}) but it is <b>{_e(C['status'])}</b>, so it is not shown as a current assessment: "
                 + _e("; ".join(C.get("why") or [])) + ". Run a new Creative Review to refresh it.</p></section>")
        return "".join(o)
    o.append(f"<p class='small' style='margin:6px 0'>{_creative_head(C)}</p>")
    if C.get("vision_summary"): o.append(f"<p style='margin:6px 0 10px;max-width:72ch'>{_e(C['vision_summary'])}</p>")
    for x in (C.get("opportunities") or [])[:3]:
        o.append(f"<div class='f'><span class='tag'>{_e(x.get('tier'))}</span>{_basis(x.get('basis'))}"
                 + ("<span class='chip warn'>proposal · needs your approval</span> " if x.get("needs_approval") else "") + f"<b>{_e(x.get('title'))}</b>"
                 f"<div class='small'>{_e(x.get('recommendation'))}</div></div>")
    o.append("<p class='small' style='margin:8px 0 0'>Advisory only: it does not change any score, release gate, the Director's verdict or the technical action plan. "
             "<a href='#creative'>Full Creative Review</a></p></section>")
    return "".join(o)


def _creative_section(C, evidence_base=None):
    o = ["<h2 id='creative'>Creative Review (advisory)</h2>"]
    if C["status"] != "current":
        return o[0] + f"<div class='card small'>Not shown: the latest review is {_e(C['status'])} — {_e('; '.join(C.get('why') or []))}.</div>"
    ev = C.get("evidence") or {}
    cite = lambda ids: " · ".join(f"<code>{_e(i)}</code>" for i in ids or []) or "—"
    o.append(f"<div class='card'><p class='small' style='margin-top:0'>{_creative_head(C)}</p>"
             "<p class='small'>This is a model's judgement against the project's vision, with every claim labelled by what it rests on. It carries no score, is never compared "
             "run to run, and does not affect department scores, the overall score, release gates, the Director's verdict, P0–P3 or the technical top three. "
             "Recommendations marked as proposals need your approval before anyone acts on them.</p>")
    va = C.get("vision_assessment") or {}
    o.append(f"<h3>Assessment against the vision</h3><p style='max-width:72ch'>{_e(va.get('summary'))}</p>")
    for part, label in (("delivers", "Delivers"), ("gaps", "Falls short")):
        for c in va.get(part) or []:
            o.append(f"<div class='f'><span class='tag'>{label}</span><span class='tag'>{_e(c.get('clause'))}</span>{_basis(c.get('basis'))} {_e(c.get('assessment'))}"
                     f"<div class='small'>Evidence: {cite(c.get('evidence'))}</div></div>")
    o.append("<h3 style='margin-top:16px'>Opportunities</h3>")
    for x in C.get("opportunities") or []:
        o.append(f"<div class='f'><span class='tag'>{_e(x.get('tier'))}</span>{_basis(x.get('basis'))}"
                 + ("<span class='chip warn'>beyond the vision · proposal</span> " if x.get("beyond_vision") else "")
                 + ("<span class='chip warn'>needs your approval</span> " if x.get("needs_approval") else "") + f"<b>{_e(x.get('title'))}</b>"
                 f"<div class='small'><b>Seen:</b> {_e(x.get('observation'))}</div><div class='small'><b>Why it matters:</b> {_e(x.get('why_it_matters'))}</div>"
                 f"<div class='small'><b>Change:</b> {_e(x.get('recommendation'))}</div><div class='small'><b>Expected:</b> {_e(x.get('expected_improvement'))}"
                 + (f" <b>Playtest:</b> {_e(x.get('playtest'))}" if x.get("playtest") else "") + "</div>"
                 f"<div class='small'>Effort {_e(x.get('effort'))} · risk {_e(x.get('risk'))} · confidence {_e(x.get('confidence'))} · "
                 + (f"vision clause <code>{_e(x.get('vision_clause'))}</code> · " if x.get("vision_clause") else "") + f"evidence {cite(x.get('evidence'))}</div></div>")
    o.append("<h3 style='margin-top:16px'>What works</h3>")
    if not C.get("strengths"): o.append(f"<p class='small'>{_e(C.get('strengths_note') or 'None earned yet.')}</p>")
    for x in C.get("strengths") or []:
        o.append(f"<div class='f'>{_basis(x.get('basis'))}<b>{_e(x.get('title'))}</b><div class='small'>{_e(x.get('observation'))} {_e(x.get('why_it_works'))}</div>"
                 + (f"<div class='small'><b>Protect:</b> {_e(x.get('protect'))}</div>" if x.get("protect") else "") + f"<div class='small'>Evidence: {cite(x.get('evidence'))}</div></div>")
    G = C.get("gameplay")
    if G:
        o.append("<h3 style='margin-top:16px'>Gameplay</h3>")
        for k, label in (("observed", "Observed in automated play"), ("source_based", "From source and design data"), ("hypotheses", "Hypotheses for a human playtest")):
            o.append(f"<p class='small' style='margin:10px 0 2px'><b>{label}</b></p>")
            for c in G.get(k) or []:
                o.append(f"<div class='f'>{_e(c.get('claim'))}" + (f"<div class='small'><b>Playtest:</b> {_e(c.get('playtest'))}</div>" if c.get("playtest") else "")
                         + f"<div class='small'>Evidence: {cite(c.get('evidence'))}</div></div>")
            if not G.get(k): o.append("<p class='small'>None.</p>")
    shots = [e for e in (C.get("evidence") or {}).values() if e.get("file")]
    if shots:   # what the reviewer looked at, so a reader can check every observed claim
        base = evidence_base if evidence_base is not None else (C.get("dir") or "") + "/"
        o.append("<h3 style='margin-top:16px'>Captures the review cites</h3><div class='multi' style='grid-template-columns:repeat(auto-fill,minmax(150px,1fr))'>"
                 + "".join(f"<figure style='margin:0'><img src='{_e(base + e['file'])}' alt='{_e(e['id'])}' loading='lazy' style='width:100%;border-radius:8px;border:1px solid var(--line)'>"
                           f"<figcaption class='small'><code>{_e(e['id'])}</code></figcaption></figure>" for e in shots) + "</div>")
    cov = C.get("coverage") or {}
    o.append(f"<p class='small' style='margin-bottom:0'>Coverage: {len(cov.get('viewed') or [])} captures viewed of {(cov.get('pack_counts') or {}).get('screenshot', 0)} screenshots and "
             f"{(cov.get('pack_counts') or {}).get('play_frame', 0)} play frames. " + _e(cov.get("not_seen") or "") + f" Review <code>{_e(C['review_id'])}</code>; cited images are kept with it.</p></div>")
    return "".join(o)


def _creative_md(C):
    if not C: return []
    L = ["## Creative Review (advisory, not scored)", ""]
    if C["status"] != "current":
        return L + [f"The latest review ({C.get('review_id')}) is **{C['status']}** and is not shown as a current assessment: " + "; ".join(C.get("why") or []) + ".", ""]
    B = C["bound_to"]
    L += [f"Judgement by {C.get('reviewer')} · commit `{str(B.get('commit') or '')[:7]}` · vision v{B.get('vision_version')} ({'approved' if B.get('vision_status') == 'approved' else 'unapproved draft'}). "
          "It does not change any score, gate, verdict, priority or the technical plan.", "", f"**Assessment against the vision:** {(C.get('vision_assessment') or {}).get('summary')}", ""]
    L += [f"- **{x.get('tier')}** · {creative.BASES.get(x.get('basis'), x.get('basis'))}" + (" · proposal, needs approval" if x.get("needs_approval") else "") + f" — {x.get('title')}: {x.get('recommendation')}"
          for x in C.get("opportunities") or []] + [""]
    L += ["What works:", ""] + ([f"- {x.get('title')}: {x.get('why_it_works')}" for x in C.get("strengths") or []] or [f"- {C.get('strengths_note') or 'None earned yet.'}"]) + [""]
    if C.get("gameplay"):
        for k, label in (("observed", "Observed in automated play"), ("source_based", "From source and design data"), ("hypotheses", "Hypotheses for a human playtest")):
            L += [f"{label}:", ""] + ([f"- {c.get('claim')}" for c in C["gameplay"].get(k) or []] or ["- None."]) + [""]
    return L


def _act(a):
    return (f"<div class='act'><span class='pr {a['priority']}'>{a['priority']}</span><div><div>{_e(a['title'])}</div>"
            f"<div class='do'>{_e(', '.join(a['departments']))} · {_e(LEVEL_LABEL.get(a['level'], a['level']))}" + (f" · {a['raised']}" if a.get("raised") else "") + "</div>"
            + (f"<div class='do'>Do: {_e(a['do'])}</div>" if a.get("do") else "") + "</div></div>")


# ---------------------------------------------------------------- the published site (/reports/)
def upgrade(R):
    """A report saved before the Production Report (v1: plain-mean health, no rubrics) → the fields the current
    layout reads. Scores are kept as recorded; nothing is re-measured and nothing is filled in."""
    if all(d.get("quality") for d in R.get("departments") or []) and "gates" in R: return R
    R = json.loads(json.dumps(R))
    for d in R["departments"]:
        d.setdefault("notes", []); d.setdefault("findings", []); d.setdefault("refresh", {})
        scoring.evaluate(d); d["quality"].update(previous=None, delta=None, compare="report made before department rubrics")
    R["health"].setdefault("method", scoring.LEGACY_METHOD); R["health"].setdefault("coverage", round(R["health"].get("measured", 0) / max(1, R["health"].get("of") or 1), 2))
    R["health"].setdefault("vs_previous", {"compare": f"{scoring.LEGACY_METHOD}: plain mean of department scores (before weighted rubrics)"})
    R["gates"] = scoring.gates(R["departments"])
    R["identity"] = {"name": R["project"].get("name"), "repo": R["project"].get("repo"), "url": R["project"].get("url"), "commit": R["project"].get("head"),
                     "commit_source": "project checkout" if R["project"].get("head") else None, "production": R["gates"].get("production"), "verdict": R["gates"].get("verdict")}
    R.setdefault("top_actions", scoring.top_actions(R.get("actions") or [], {f["key"]: f for d in R["departments"] for f in d["findings"]}))
    R.setdefault("major_findings", major_findings(R["departments"])); R.setdefault("regressions", [])
    R.setdefault("blockers", [{"title": a["title"], "departments": a["departments"], "level": a["level"], "open_since": R["generated"]} for a in R.get("actions") or [] if a["priority"] == "P0"])
    R["summary"] = list(R.get("summary") or []) + [f"Made with GITCRAFT report {R.get('gitcraft_report', '1')}: the overall number is the earlier plain mean ({scoring.LEGACY_METHOD}), not the weighted score."]
    return R


def publish_site(archive, dist):
    """Every archived report (history/reports/<project>/<stamp>/report.json) → dist: an index of projects with their
    health trend, and each report page. Standard library only (runs in the Vercel build). Returns the report count."""
    import shutil
    if os.path.isdir(dist): shutil.rmtree(dist)
    os.makedirs(dist)
    projects = {}
    for p in sorted(glob.glob(os.path.join(archive, "*", "*", "report.json"))):
        R = _json(p)
        if not R: continue
        projects.setdefault(R["project"]["id"], []).append((R["generated"], os.path.basename(os.path.dirname(p)), upgrade(R), p))
    for pid, rs in projects.items():
        rs.sort(key=lambda x: x[0])
        for i, (g, stamp, R, p) in enumerate(rs):
            R["trend"] = scoring.series([x[2] for x in rs[max(0, i - 11):i]], R)   # the archive's own history, as published
            out = os.path.join(dist, pid, stamp); os.makedirs(out, exist_ok=True)
            C = R.get("creative") or {}
            src = os.path.join(REPO, os.path.relpath(C["dir"], C["dir"][:C["dir"].index("history/creative")])) if "history/creative" in str(C.get("dir") or "") else None
            for e in (C.get("evidence") or {}).values() if C.get("status") == "current" and src else []:
                if e.get("file") and os.path.isfile(os.path.join(src, e["file"])):
                    os.makedirs(os.path.join(out, "creative", os.path.dirname(e["file"])), exist_ok=True)
                    shutil.copy(os.path.join(src, e["file"]), os.path.join(out, "creative", e["file"]))
            with open(os.path.join(out, "index.html"), "w") as f: f.write(render_html(R, back="../../", evidence_base="creative/"))
            shutil.copy(p, os.path.join(out, "report.json"))
            md = os.path.join(os.path.dirname(p), "report.md")
            if os.path.isfile(md): shutil.copy(md, os.path.join(out, "report.md"))
    projects = {pid: [(g, st, R) for g, st, R, _ in rs] for pid, rs in projects.items()}
    rows = []
    for pid, rs in sorted(projects.items(), key=lambda kv: kv[1][-1][0], reverse=True):
        g, stamp, R = rs[-1]; H = R["health"]; G = R.get("gates") or {}
        bcls = {"healthy": "ok", "needs attention": "warn", "at risk": "bad", "blocked": "bad"}.get(H["band"], "")
        when = lambda st: f"{st[4:6]}/{st[6:8]} {st[9:11]}:{st[11:13]}" + (f" #{st.split('-')[1]}" if "-" in st else "")
        T = R.get("trend") or []
        rows.append(f"<article class='card'><div class='small'>{_e(R['project'].get('repo') or pid)}</div>"
                    f"<h3 style='font:600 19px/1.25 var(--serif);margin:4px 0 8px'><a href='{_e(pid)}/{_e(stamp)}/' style='color:inherit'>{_e(R['title'])}</a></h3>"
                    f"<div class='big'><b style='font-size:44px'>{_e(H['score'])}</b><span>/ 100 · {_e(H.get('method'))}</span></div>"
                    + (chart_svg(T, w=320, h=60, label=False) if len(T) > 1 else "")
                    + f"<div class='chips' style='margin-top:8px'><span class='chip {bcls}'>{_e(H['band'])}</span><span class='chip {_verdict_cls(G.get('verdict'))}'>{_e(G.get('verdict') or 'no verdict')}</span>"
                    f"<span class='chip'>{len(rs)} report(s)</span></div>"
                    "<div class='small' style='margin-top:8px'>Reports (UTC): " + " · ".join(f"<a href='{_e(pid)}/{_e(s)}/' style='display:inline-block;padding:8px 0'>{_e(when(s))}</a>" for _, s, _ in reversed(rs[-5:])) + "</div></article>")
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'><title>GITCRAFT Production Reports</title>"
            f"<meta name='description' content='Every GITCRAFT Production Report: department scores, release gates and trends per project.'><style>{CSS}</style></head><body><main><p class='small' style='margin:8px 0 0'><a href='../'>← GITCRAFT</a></p>"
            "<header class='top'><div class='k'>GITCRAFT</div><h1>Production Reports</h1><p class='small' style='max-width:68ch'>One report per run, built from the latest measured results of every GITCRAFT department. "
            "Reports are timestamped and kept, so progress is compared report to report under the same scoring method. Read-only: reporting never changes code, merges or deploys.</p></header>"
            + ("<div class='multi' style='grid-template-columns:repeat(auto-fill,minmax(280px,1fr))'>" + "".join(rows) + "</div>" if rows else "<div class='card small'>No reports archived yet.</div>")
            + f"<footer>GITCRAFT Production Report {VERSION}</footer></main></body></html>")
    with open(os.path.join(dist, "index.html"), "w") as f: f.write(page)
    return sum(len(v) for v in projects.values())
