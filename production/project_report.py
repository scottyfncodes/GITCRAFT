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
from . import REPO, roots

VERSION = "1.0.0"
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


def _finding(dept, fid, title, severity, level, evidence=None, recommendation=None, source=None, theme=None, kind=None, extra=None):
    f = {"key": f"{dept}:{fid}", "department": dept, "id": fid, "title": title, "severity": severity if severity in SEVERITIES else "minor",
         "level": level, "evidence": evidence, "recommendation": recommendation, "source": source, "kind": kind,
         "theme": theme or theme_of(title, extra)}
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
                                      kind=f.get("type"), extra=f.get("category")))
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
        D["apps"].append({"app": app, "name": (A.get("app") or {}).get("name"), "run": run, "at": at, "overall": ov.get("score"), "categories": cats, "coverage": ov.get("coverage"),
                          "confidence": ov.get("confidence"), "commit": ((A.get("app") or {}).get("git") or {}).get("head", "")[:12] or None, "runs": len(rs)})
        scores.append(ov.get("score"))
        for f in A.get("findings") or []:
            lvl = _level(f.get("evidence"))
            D["findings"].append(_finding("pixelcraft", f"{app}:{f['id']}", f.get("title"), f.get("severity"), lvl, (f.get("explanation") or "")[:240],
                                          (f.get("recommendation") or "")[:240], os.path.relpath(p, REPO) if p.startswith(REPO) else p, extra=f.get("area")))
    newest = max(D["apps"], key=lambda a: a["at"])
    D.update(status="current", age_days=_age(newest["at"]),
             run={"id": newest["run"], "at": newest["at"], "commit": newest["commit"], "method": "pixelcraft", "runs": sum(a["runs"] for a in D["apps"]), "apps": len(D["apps"])},
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
                                      (pr or {}).get("proposal") or (pr or {}).get("label"), src, extra=f.get("dept")))
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
            sc = standards.check(P["path"], deliverable=a.get("kind") or "app")
            checks = sc.get("checks") or []; rel = [c for c in checks if c["status"] != "n/a"]
            ok = [c for c in rel if c["status"] == "ok"]
            D["standard"] = {"passed": len(ok), "of": len(rel), "status": sc.get("status")}
            for c in rel:
                if c["status"] == "failed":
                    D["findings"].append(_finding("production", f"standard:{c['id']}", f"Engineering standard: {c['name']}", "major", "verified", str(c.get("detail") or "")[:200], None, "docs/app-standards.md", theme="engineering"))
                elif c["status"] not in ("ok",):
                    D["findings"].append(_finding("production", f"standard:{c['id']}", f"Engineering standard (review): {c['name']}", "minor", "inferred", str(c.get("detail") or "")[:200], None, "docs/app-standards.md", theme="engineering"))
            D["notes"].append(f"Engineering standard: {len(ok)}/{len(rel)} applicable checks pass.")
        except Exception as e:
            D["notes"].append(f"Engineering standard not checked: {e}"[:200])
    prods = ctx["productions"]
    if prods:
        pr = prods[-1]; A = acc.acceptance(pr); v = acc.verdict(A)
        passed = sum(1 for x in A if x["status"] == "passed")
        D["production"] = {"id": pr["id"], "status": pr.get("status"), "verdict": v, "criteria": len(A), "passed": passed, "updated": pr.get("updated")}
        D["notes"].append(f"Production {pr['id']}: {pr.get('status')}, verdict {v}, {passed}/{len(A)} acceptance criteria passed.")
        ran = any(t.get("state") not in ("pending", None) for t in (pr.get("tasks") or {}).values())
        if not ran: D["notes"].append("That production is planned but has not run yet: its criteria are unmeasured, so it has no score and no findings.")
        D["score"] = {"value": round(100 * passed / len(A), 1), "label": "Acceptance criteria passed", "confidence": "high", "coverage": None} if A and ran else None
        D["run"] = {"id": pr["id"], "at": pr.get("updated"), "runs": len(prods), "source": pr["_dir"]}
        D["age_days"] = _age(pr.get("updated"))
        for x in (A if ran else []):
            if x["status"] in ("failed", "blocked", "not_planned"):
                D["findings"].append(_finding("production", f"criterion:{x['id']}", f"Acceptance criterion {x['status']}: {x.get('title') or x['id']}", "critical" if x["status"] == "failed" else "major",
                                              "verified", "; ".join(x.get("why") or [])[:240], None, os.path.join(pr["_dir"], "REPORT.md"), kind="blocker", theme="release"))
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
    sc = [(d["id"], d["score"]["value"]) for d in depts if d.get("score") and d["score"].get("value") is not None and d["status"] in ("current", "refreshed", "stale", "unverified")]
    applicable_scored = [d for d in depts if d["applicable"] and d["role"] in ("scored", "qa", "director") and d["status"] != "not_applicable"]
    stale = [d["id"] for d in depts if d["status"] in ("stale", "unverified")]   # unverified: not compared with the current commit
    p0 = sum(1 for a in actions if a["priority"] == "P0")
    if not sc:
        return {"score": None, "band": "insufficient data", "confidence": "none", "measured": 0, "of": len(applicable_scored), "stale": stale, "p0": p0,
                "basis": "No department has measured this project yet."}
    v = round(sum(x for _, x in sc) / len(sc), 1)
    cov = len(sc) / max(1, len(applicable_scored))
    conf = "high" if cov >= 0.75 and not stale else "medium" if cov >= 0.5 and len(stale) <= 1 else "low"
    band = "blocked" if p0 else "healthy" if v >= 80 else "needs attention" if v >= 60 else "at risk"
    return {"score": v, "band": band, "confidence": conf, "measured": len(sc), "of": len(applicable_scored), "stale": stale, "p0": p0, "parts": dict(sc),
            "basis": f"mean of {len(sc)} measured department score(s) ({', '.join(i for i, _ in sc)}); {len(applicable_scored) - len(sc)} applicable department(s) have no score"
                     + (f"; {len(stale)} stale" if stale else "")}


# ---------------------------------------------------------------- store + comparison
def store_root():
    return os.path.realpath(os.environ.get("GITCRAFT_REPORTS") or os.path.join(roots()[0], "gitcraft-out", "reports"))


def archive_root():
    return os.path.join(REPO, "history", "reports")


def previous(pid, roots_=None):
    best = None
    for r in roots_ or (store_root(), archive_root()):
        for p in glob.glob(os.path.join(r, pid or "-", "*", "report.json")):
            R = _json(p)
            if R and (not best or R["generated"] > best["generated"]): best = R
    return best


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
        same_run = (p.get("run") or {}).get("id") == (d.get("run") or {}).get("id")
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
    R = {"gitcraft_report": VERSION, "report_id": f"{P['id']}/{stamp}", "generated": now(), "refresh": refresh, "read_only": True,
         "project": {k: P.get(k) for k in ("id", "repo", "url", "name", "path", "head", "branch", "dirty")} | {
             "kind": ctx["kind"], "maturity": (assessment or {}).get("maturity")},
         "health": H, "departments": depts, "reconciliation": rec, "actions": actions,
         "levels": {lv: sum(1 for d in depts for f in d["findings"] if f["level"] == lv) for lv in ("verified", "observed", "inferred")},
         "unavailable": [{"department": d["id"], "status": d["status"], "why": (d["notes"] or [d.get("next") or ""])[-1]} for d in depts if d["status"] in ("unavailable", "failed")],
         "not_refreshed": [{"department": d["id"], "why": d["refresh"]["detail"]} for d in depts if d["refresh"].get("detail") and not d["refresh"].get("ok")]}
    R["title"] = _title(R, ctx)
    R["summary"] = executive(R)
    R["next_actions"] = next_actions(R)
    R["changes"] = compare(previous(P["id"]), R)
    R["paths"] = {"dir": run_dir}
    if save != "none":
        os.makedirs(run_dir, exist_ok=True)
        R["paths"].update(json=os.path.join(run_dir, "report.json"), markdown=os.path.join(run_dir, "report.md"), html=os.path.join(run_dir, "report.html"))
        with open(R["paths"]["json"], "w") as f: json.dump(R, f, indent=1, default=str)
        with open(R["paths"]["markdown"], "w") as f: f.write(markdown(R))
        with open(R["paths"]["html"], "w") as f: f.write(render_html(R))
        line = {"report_id": R["report_id"], "generated": R["generated"], "project": P["id"], "title": R["title"], "health": H.get("score"), "band": H.get("band"),
                "confidence": H.get("confidence"), "p": {p: sum(1 for a in actions if a["priority"] == p) for p in ("P0", "P1", "P2", "P3")},
                "departments": {d["id"]: {"status": d["status"], "score": (d.get("score") or {}).get("value")} for d in depts}, "dir": os.path.relpath(run_dir, base)}
        idx = os.path.join(os.path.dirname(os.path.dirname(run_dir)) if not out_dir else run_dir, "index.jsonl")
        with open(idx, "a") as f: f.write(json.dumps(line) + "\n")
    return R


def _title(R, ctx):
    t = None
    try:
        ph = _load(os.path.join(REPO, "studio", "departments", "playcraft", "history.py"))
        for root in (ph.store_root(), ph.archive_root()):
            g = _json(os.path.join(root, "games", R["project"]["id"], "game.json"))
            if g and g.get("title"): t = g["title"]; break
    except Exception:
        pass
    if not t:
        for r in glob.glob(os.path.join(REPO, "history", "designcraft", R["project"]["id"], "*.json"))[-1:]:
            t = (_json(r) or {}).get("game", {}).get("title")
    return t or (R["project"].get("repo") or R["project"]["name"])


def executive(R):
    H = R["health"]; ds = R["departments"]
    have = [d for d in ds if d["status"] in ("current", "refreshed", "stale", "unverified")]
    pc = {p: sum(1 for a in R["actions"] if a["priority"] == p) for p in ("P0", "P1", "P2", "P3")}
    s = []
    if H["score"] is None: s.append(f"No department has a measured score for {R['title']} yet, so there is no health score. {len(have)} department(s) have any data.")
    else: s.append(f"{R['title']} scores **{H['score']}/100** overall ({H['band']}, {H['confidence']} confidence): {H['basis']}.")
    s.append(f"{len(have)} of {len(ds)} departments have results for this project; " + ", ".join(f"{sum(1 for d in ds if d['status'] == k)} {STATUS_LABEL[k].lower()}"
             for k in STATUS_LABEL if any(d["status"] == k for d in ds)) + ".")
    s.append(f"Action plan: {pc['P0']} P0, {pc['P1']} P1, {pc['P2']} P2, {pc['P3']} P3. Findings by evidence: {R['levels']['verified']} verified, {R['levels']['observed']} observed, {R['levels']['inferred']} inferred.")
    if pc["P0"]: s.append("There are P0 blockers: resolve them before shipping anything else.")
    if R["reconciliation"]["corroborated"]: s.append(f"{len(R['reconciliation']['corroborated'])} problem area(s) are flagged by several departments at once — the strongest signals in this report.")
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
    L = [f"# GITCRAFT report — {R['title']}", "",
         f"`{R['report_id']}` · generated {R['generated']} · refresh **{R['refresh']}** · read-only" +
         (f" · commit `{(P.get('head') or '')[:7]}`" if P.get("head") else "") + (f" · [{P['repo']}]({P['url']})" if P.get("url") else ""), "",
         "## Executive summary", ""] + [f"- {s}" for s in R["summary"]] + [""]
    L += ["## Overall health", "", "| Health | Band | Confidence | Measured departments |", "|---|---|---|---|",
          f"| {H['score'] if H['score'] is not None else '—'} | {H['band']} | {H['confidence']} | {H['measured']} of {H['of']} applicable |", "", f"Basis: {H['basis']}.", ""]
    L += ["## Department scorecards", "", "| Department | Status | Score | Latest run | Findings |", "|---|---|---|---|---|"]
    for d in R["departments"]:
        sc = d.get("score") or {}
        L.append(f"| {d['title']} | {STATUS_LABEL[d['status']]} | {sc.get('value') if sc.get('value') is not None else '—'}{' (' + sc['label'] + ')' if sc.get('label') else ''} | "
                 f"{((d.get('run') or {}).get('at') or '—')[:10]} | {len(d['findings'])} |")
    L.append("")
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
    crit = [a for a in R["actions"] if a["priority"] == "P0"]
    L += ["## Critical issues and blockers", ""] + ([f"- {a['title']} ({', '.join(a['departments'])}; {LEVEL_LABEL[a['level']]})" for a in crit] or ["- None measured."]) + [""]
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
    L += ["## Evidence and limits", "", "- **Verified**: measured by a department tool (a played build, a rendered UI, a parsed source fact, a check).",
          "- **Observed**: seen while playing or simulated, not a hard measurement.", "- **Inferred (assumption)**: a department's judgement from indirect evidence; confirm before acting alone.",
          "- **Unavailable**: no data; nothing is filled in for it."] + [f"- Not refreshed — {x['department']}: {x['why']}" for x in R["not_refreshed"]] + \
         [f"- {x['department']}: {x['status']} — {x['why']}" for x in R["unavailable"]] + ["", "Report generation is read-only: it changed no code, merged nothing and deployed nothing.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- HTML (self-contained, mobile-first)
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#14171f;--mute:#5b6372;--line:#e3e6eb;--accent:#1f7a75;--p0:#c62828;--p1:#d9730d;--p2:#2f6fd6;--p3:#6b7280;--ok:#1f8a4c;--warn:#b7791f;--bad:#c62828;--chip:#eef1f4}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1216;--card:#171b21;--ink:#e8ebf0;--mute:#9aa3b2;--line:#2a3039;--accent:#4fc1b9;--chip:#222831}}
:root[data-theme=dark]{--bg:#0f1216;--card:#171b21;--ink:#e8ebf0;--mute:#9aa3b2;--line:#2a3039;--accent:#4fc1b9;--chip:#222831}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;-webkit-text-size-adjust:100%}
main{max-width:920px;margin:0 auto;padding:16px 16px calc(40px + env(safe-area-inset-bottom))}
header.top{padding:20px 0 8px}header.top .k{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-size:26px;line-height:1.2;margin:4px 0 6px}h2{font-size:19px;margin:28px 0 10px}h3{font-size:16px;margin:0}
.meta{color:var(--mute);font-size:13px;word-break:break-word}.meta code{font-size:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:10px 0}
.hero{display:flex;gap:16px;align-items:center;flex-wrap:wrap}.ring{--v:0;width:112px;height:112px;border-radius:50%;flex:none;display:grid;place-items:center;
background:conic-gradient(var(--c,var(--accent)) calc(var(--v)*1%),var(--chip) 0)}.ring b{display:grid;place-items:center;width:88px;height:88px;border-radius:50%;background:var(--card);font-size:28px}
.ring b small{display:block;font-size:11px;color:var(--mute);font-weight:500;margin-top:-6px}.hero .t{flex:1;min-width:200px}
.band{display:inline-block;padding:3px 10px;border-radius:99px;font-size:13px;font-weight:600;background:var(--chip)}
.band.healthy{color:var(--ok)}.band.blocked,.band.at-risk{color:var(--bad)}.band.needs-attention{color:var(--warn)}
ul.sum{margin:12px 0 0;padding-left:18px}ul.sum li{margin:4px 0}
.counts{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}.counts div{background:var(--chip);border-radius:10px;padding:8px;text-align:center}
.counts b{display:block;font-size:20px}.counts span{font-size:12px;color:var(--mute)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.dept{margin:0}.dept .h{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.dept .fam{font-size:11px;color:var(--mute);text-transform:uppercase;letter-spacing:.06em}
.score{font-size:24px;font-weight:700;line-height:1}.score small{font-size:12px;color:var(--mute);font-weight:500}
.st{font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px;background:var(--chip);white-space:nowrap}
.st.current,.st.refreshed{color:var(--ok)}.st.stale,.st.unverified{color:var(--warn)}.st.failed,.st.unavailable{color:var(--bad)}.st.no_data,.st.not_applicable{color:var(--mute)}
.bar{height:6px;border-radius:9px;background:var(--chip);margin:10px 0 6px;overflow:hidden}.bar i{display:block;height:100%;background:var(--accent)}
.small{font-size:13px;color:var(--mute)}details{margin-top:8px}summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--accent);min-height:44px;display:flex;align-items:center;list-style:none}
summary::-webkit-details-marker{display:none}summary::before{content:"▸";margin-right:6px}details[open]>summary::before{content:"▾"}
.f{border-top:1px solid var(--line);padding:8px 0;font-size:14px}.f .tags{margin-bottom:2px}
.tag{display:inline-block;font-size:11px;font-weight:600;padding:1px 7px;border-radius:6px;margin-right:4px;background:var(--chip);color:var(--mute)}
.tag.critical{color:#fff;background:var(--p0)}.tag.major{color:#fff;background:var(--p1)}.tag.verified{color:var(--ok)}.tag.observed{color:var(--p2)}.tag.inferred{color:var(--warn)}
.act{display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--line)}.act:first-child{border-top:0}.pr{flex:none;font-size:12px;font-weight:700;color:#fff;border-radius:6px;padding:2px 7px;height:fit-content}
.pr.P0{background:var(--p0)}.pr.P1{background:var(--p1)}.pr.P2{background:var(--p2)}.pr.P3{background:var(--p3)}.act .do{font-size:13px;color:var(--mute);margin-top:2px}
.x{padding:8px 0;border-top:1px solid var(--line)}.x:first-of-type{border-top:0}ol.next li{margin:6px 0}
.delta.up{color:var(--ok)}.delta.down{color:var(--bad)}nav.jump{display:flex;gap:6px;overflow-x:auto;padding:4px 0 10px;scrollbar-width:none}
nav.jump a{flex:none;font-size:13px;padding:8px 12px;border-radius:99px;background:var(--card);border:1px solid var(--line);color:var(--ink);text-decoration:none;min-height:36px}
a{color:var(--accent)}footer{color:var(--mute);font-size:12px;margin-top:32px;text-align:center}
@media (max-width:520px){h1{font-size:22px}.ring{width:96px;height:96px}.ring b{width:76px;height:76px;font-size:24px}.counts b{font-size:18px}}
"""


def _e(s): return html.escape(str("—" if s is None else s))


def render_html(R, back=None):
    H = R["health"]; P = R["project"]; pc = {p: sum(1 for a in R["actions"] if a["priority"] == p) for p in ("P0", "P1", "P2", "P3")}
    band = slug(H["band"])
    col = {"healthy": "var(--ok)", "needs-attention": "var(--warn)", "at-risk": "var(--bad)", "blocked": "var(--bad)"}.get(band, "var(--mute)")
    md = lambda s: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _e(s))
    o = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>",
         f"<title>{_e(R['title'])} report</title><meta name='description' content='GITCRAFT report for {_e(R['title'])}'><style>{CSS}</style></head><body><main>"]
    if back: o.append(f"<p class='small' style='margin:8px 0 0'><a href='{_e(back)}'>← All reports</a></p>")
    o.append(f"<header class='top'><div class='k'>GITCRAFT report</div><h1>{_e(R['title'])}</h1><div class='meta'>{_e(R['generated'][:16].replace('T', ' '))} UTC · refresh {_e(R['refresh'])} · read-only"
             + (f" · commit <code>{_e((P.get('head') or '')[:7])}</code>" if P.get("head") else "") + (f" · <a href='{_e(P['url'])}'>{_e(P['repo'])}</a>" if P.get("url") else "") + "</div></header>")
    o.append("<nav class='jump'>" + "".join(f"<a href='#{i}'>{t}</a>" for i, t in (("health", "Health"), ("depts", "Departments"), ("p0", "Blockers"), ("cross", "Cross-dept"),
                                                                                   ("plan", "Action plan"), ("changes", "Changes"), ("next", "Next"), ("limits", "Evidence"))) + "</nav>")
    v = H["score"] if H["score"] is not None else 0
    o.append(f"<section id='health' class='card'><div class='hero'><div class='ring' style='--v:{v};--c:{col}'><b>{_e(H['score'] if H['score'] is not None else '—')}<small>/ 100</small></b></div>"
             f"<div class='t'><span class='band {band}'>{_e(H['band'].capitalize())}</span> <span class='small'>{_e(H['confidence'])} confidence · {H['measured']} of {H['of']} departments measured</span>"
             "</div></div><ul class='sum'>" + "".join(f"<li>{md(s)}</li>" for s in R["summary"]) + "</ul>"
             "<div class='counts'>" + "".join(f"<div><b style='color:var(--{p.lower()})'>{pc[p]}</b><span>{p}</span></div>" for p in pc) + "</div></section>")
    o.append("<h2 id='depts'>Department scorecards</h2><div class='grid'>")
    order = {"refreshed": 0, "current": 0, "unverified": 1, "stale": 1, "failed": 2, "unavailable": 3, "no_data": 4, "not_applicable": 5}
    quiet = [d for d in R["departments"] if d["status"] in ("no_data", "not_applicable") and not d["findings"] and not d.get("next")]
    for d in sorted(R["departments"], key=lambda d: (order[d["status"]], d["score"] is None)):
        if d in quiet: continue
        sc = d.get("score") or {}; val = sc.get("value")
        title, _, sub = d["title"].partition(" — ")
        o.append(f"<article class='card dept'><div class='h'><div><div class='fam'>{_e(d['family'])}</div><h3>{_e(title)}</h3><div class='small'>{_e(sub or d['summary'])}</div></div>"
                 f"<span class='st {d['status']}'>{_e(STATUS_LABEL[d['status']])}</span></div>")
        if val is not None:
            o.append(f"<div style='margin-top:10px' class='score'>{_e(val)}<small> {_e(sc.get('label'))}</small></div><div class='bar'><i style='width:{max(0, min(100, val))}%'></i></div>")
        bits = []
        if d.get("run"): bits.append(f"latest {_e((d['run'].get('at') or '')[:10])}" + (f" · {d['run'].get('runs')} run(s)" if d["run"].get("runs") else ""))
        if sc.get("confidence"): bits.append(f"{_e(sc['confidence'])} confidence")
        if d["findings"]: bits.append(f"{len(d['findings'])} finding(s)")
        if bits: o.append(f"<div class='small'>{' · '.join(bits)}</div>")
        if d["notes"] or d["findings"] or d.get("next") or d["refresh"].get("detail"):
            o.append("<details><summary>Evidence and findings</summary>")
            for n in d["notes"]: o.append(f"<p class='small' style='margin:4px 0'>{_e(n)}</p>")
            if d["refresh"].get("detail"): o.append(f"<p class='small' style='margin:4px 0'>Refresh: {_e(d['refresh']['detail'])}</p>")
            if d.get("next"): o.append(f"<p class='small' style='margin:4px 0'><b>Next:</b> {_e(d['next'])}</p>")
            for f in d["findings"][:12]:
                o.append(f"<div class='f'><div class='tags'><span class='tag {f['severity']}'>{f['severity']}</span><span class='tag {f['level']}'>{_e(LEVEL_LABEL[f['level']])}</span></div>"
                         f"{_e(f['title'])}" + (f"<div class='small'>{_e(f['evidence'])}</div>" if f.get("evidence") else "") + "</div>")
            if len(d["findings"]) > 12: o.append(f"<p class='small'>… {len(d['findings']) - 12} more in report.json</p>")
            o.append("</details>")
        o.append("</article>")
    if quiet:
        o.append("<article class='card dept'><div class='h'><div><div class='fam'>No results for this project</div><h3>Nothing to report, nothing assumed</h3></div>"
                 f"<span class='st no_data'>{len(quiet)}</span></div><p class='small'>These departments have no outputs or analysis for this project:</p><div>"
                 + "".join(f"<span class='tag' style='margin:0 4px 6px 0;padding:4px 8px'>{_e(d['title'].split(' — ')[0])}"
                           + (" · n/a" if d["status"] == "not_applicable" else "") + "</span>" for d in quiet) + "</div></article>")
    o.append("</div>")
    crit = [a for a in R["actions"] if a["priority"] == "P0"]
    o.append("<h2 id='p0'>Critical issues and blockers</h2><div class='card'>" + ("".join(_act(a) for a in crit) or "<p class='small' style='margin:0'>No measured blockers.</p>") + "</div>")
    rc = R["reconciliation"]
    o.append("<h2 id='cross'>Cross-department findings</h2><div class='card'>")
    for key, label, empty in (("corroborated", "Corroborated — one fix, several departments", "None."), ("conflicts", "Conflicts", "None found."),
                              ("dependencies", "Dependencies", "None."), ("gaps", "Gaps — no data", "None.")):
        o.append(f"<h3 style='margin:6px 0'>{label}</h3>")
        if not rc[key]: o.append(f"<p class='small'>{empty}</p>")
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
        h = C["health"]; dl = h.get("delta")
        o.append(f"<p style='margin:0 0 8px'>Health {_e(h.get('from'))} → <b>{_e(h.get('to'))}</b>" + (f" <span class='delta {'up' if dl > 0 else 'down' if dl < 0 else ''}'>({dl:+})</span>" if dl is not None else "")
                 + f" <span class='small'>vs {_e(C['at'][:10])}</span></p>")
        for x in C["departments"]: o.append(f"<div class='x small'><b>{_e(x['id'])}</b>: {_e(x['change'])}</div>")
        o.append(f"<p class='small'>{len(C['new_findings'])} new finding(s), {len(C['resolved_findings'])} resolved or no longer reported. {_e(C['note'])}</p>")
    o.append("</div><h2 id='next'>Recommended next actions</h2><div class='card'><ol class='next'>" + "".join(f"<li>{_e(s)}</li>" for s in R["next_actions"]) + "</ol></div>")
    o.append("<h2 id='limits'>Evidence and limits</h2><div class='card small'><p style='margin-top:0'><span class='tag verified'>Verified</span> measured by a department tool · "
             "<span class='tag observed'>Observed</span> seen in play or simulated · <span class='tag inferred'>Inferred (assumption)</span> a judgement to confirm · "
             "<b>Unavailable</b> no data, nothing filled in.</p>" + "".join(f"<p>Not refreshed — {_e(x['department'])}: {_e(x['why'])}</p>" for x in R["not_refreshed"])
             + "".join(f"<p>{_e(x['department'])}: {_e(STATUS_LABEL.get(x['status']))} — {_e(x['why'])}</p>" for x in R["unavailable"])
             + "<p style='margin-bottom:0'>Report generation is read-only: it changed no code, merged nothing and deployed nothing.</p></div>")
    o.append(f"<footer>GITCRAFT report {VERSION} · <code>{_e(R['report_id'])}</code></footer></main></body></html>")
    return "".join(o)


def _act(a):
    return (f"<div class='act'><span class='pr {a['priority']}'>{a['priority']}</span><div><div>{_e(a['title'])}</div>"
            f"<div class='do'>{_e(', '.join(a['departments']))} · {_e(LEVEL_LABEL.get(a['level'], a['level']))}" + (f" · {a['raised']}" if a.get("raised") else "") + "</div>"
            + (f"<div class='do'>Do: {_e(a['do'])}</div>" if a.get("do") else "") + "</div></div>")


# ---------------------------------------------------------------- the published site (/reports/)
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
        pid, stamp = R["project"]["id"], os.path.basename(os.path.dirname(p))
        out = os.path.join(dist, pid, stamp); os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w") as f: f.write(render_html(R, back="../../"))
        shutil.copy(p, os.path.join(out, "report.json"))
        md = os.path.join(os.path.dirname(p), "report.md")
        if os.path.isfile(md): shutil.copy(md, os.path.join(out, "report.md"))
        projects.setdefault(pid, []).append((R["generated"], stamp, R))
    rows = []
    for rs in projects.values(): rs.sort(key=lambda x: x[0])
    for pid, rs in sorted(projects.items(), key=lambda kv: kv[1][-1][0], reverse=True):
        g, stamp, R = rs[-1]; H = R["health"]
        trend = " → ".join(str(x[2]["health"].get("score") if x[2]["health"].get("score") is not None else "—") for x in rs[-6:])
        pc = {p: sum(1 for a in R["actions"] if a["priority"] == p) for p in ("P0", "P1")}
        when = lambda st: f"{st[4:6]}/{st[6:8]} {st[9:11]}:{st[11:13]}" + (f" #{st.split('-')[1]}" if "-" in st else "")
        rows.append(f"<article class='card dept'><div class='h'><div><div class='fam'>{_e(R['project'].get('repo') or pid)}</div>"
                    f"<h3><a href='{_e(pid)}/{_e(stamp)}/' style='color:inherit'>{_e(R['title'])}</a></h3></div><span class='st {'current' if H['band'] == 'healthy' else 'stale' if H['band'] == 'needs attention' else 'failed' if H['score'] is not None else 'no_data'}'>{_e(H['band'])}</span></div>"
                    f"<div style='margin-top:10px' class='score'>{_e(H['score'])}<small> / 100 · {_e(H['confidence'])} confidence</small></div>"
                    f"<div class='bar'><i style='width:{H['score'] or 0}%'></i></div><div class='small'>{len(rs)} report(s) · latest {_e(g[:10])} · trend {_e(trend)} · {pc['P0']} P0, {pc['P1']} P1</div>"
                    "<div class='small' style='margin-top:6px'>Reports (UTC): " + " · ".join(f"<a href='{_e(pid)}/{_e(s)}/' style='display:inline-block;padding:6px 0'>{_e(when(s))}</a>" for _, s, _ in reversed(rs[-5:])) + "</div></article>")
    page = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'><title>GITCRAFT reports</title>"
            f"<meta name='description' content='Every GITCRAFT project report: one view across all departments.'><style>{CSS}</style></head><body><main><p class='small' style='margin:8px 0 0'><a href='../'>← GITCRAFT</a></p>"
            "<header class='top'><div class='k'>Run GITCRAFT report</div><h1>Project reports</h1><div class='meta'>One report per run, built from the latest analysis of every GITCRAFT department. "
            "Each report is timestamped and kept, so progress is measured report to report. Read-only: reporting never changes code, merges or deploys.</div></header>"
            + ("<div class='grid'>" + "".join(rows) + "</div>" if rows else "<div class='card small'>No reports archived yet.</div>")
            + f"<footer>GITCRAFT report {VERSION}</footer></main></body></html>")
    with open(os.path.join(dist, "index.html"), "w") as f: f.write(page)
    return sum(len(v) for v in projects.values())
