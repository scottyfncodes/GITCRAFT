#!/usr/bin/env python3
"""PIXELCRAFT test: the visual-quality evaluator through the real launcher (scripts/mcp.sh studiocraft: guard +
Landlock sandbox, no network), against the Taskboard sample app (a mobile-first SPA with known UI defects) and its
fixed version, plus the scoring rules.

    tests/test_pixelcraft.py              everything (~8 min: full audit at six viewports, verify cycle, live URL, a game)
    tests/test_pixelcraft.py --quick      rules + one audit at three viewports + the verify cycle
    GITCRAFT_PIXELCRAFT_PROOF=<dir>       keep the outputs there (default: a temp workspace)

Checks: the scoring rules (independent categories, nothing capped, untested ≠ zero, coverage/confidence separate,
journeys and judgements), the known defects of the sample app are found with screen, viewport, selector,
measurements and an annotated screenshot (safe area, input zoom, overflow, small/crowded targets, uneven spacing,
invisible focus, double confirmation, a dead Save button, disabled look-alike, axe contrast), no false positive
on the fixed app's corrected areas, the report has all ten sections, verify proves the fixes (resolved findings,
higher scores on the same metrics, screenshot diffs) and refuses a score that rose because coverage was lost, a
running localhost app is opened (port allowance) and refused without it, history is append-only, the site page
publishes, routing. Exit 1 on any failure."""
import json, os, shutil, socket, subprocess, sys, tempfile, threading, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
try:
    import numpy, PIL  # noqa: F401
except ImportError:
    _vpy = os.path.join(os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.expanduser("~/.gitcraft/studio"), "venv", "bin", "python")
    if os.access(_vpy, os.X_OK) and os.path.realpath(sys.prefix) != os.path.realpath(os.path.dirname(os.path.dirname(_vpy))):
        os.execv(_vpy, [_vpy] + sys.argv)
    raise
sys.path.insert(0, HERE)
from mcp_client import Client

QUICK = "--quick" in sys.argv
ws = os.path.abspath(os.environ.get("GITCRAFT_PIXELCRAFT_PROOF") or tempfile.mkdtemp(prefix="gitcraft-pixelcraft-"))
os.makedirs(ws, exist_ok=True)
FIX = os.path.join(HERE, "fixtures", "pixelcraft")
APP = os.path.join(ws, "taskboard"); shutil.rmtree(APP, ignore_errors=True); shutil.copytree(os.path.join(FIX, "taskboard"), APP)
JOURNEYS = json.load(open(os.path.join(FIX, "taskboard.journeys.json")))
HIST = os.path.join(ws, "history")
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog", "catalog.sqlite"),
           GITCRAFT_PIXELCRAFT_HISTORY=HIST, GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "pc-history"), GITCRAFT_PLAYCRAFT_ARCHIVE=os.path.join(ws, "no-archive"))
env.pop("GITCRAFT_ALLOW_LOCAL_PORTS", None)
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:500]}]" if detail and not cond else ""), flush=True)


def load(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"px_{name}", os.path.join(REPO, "studio", "departments", "pixelcraft", f"{name}.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


# ---------------------------------------------------------------- scoring rules (pure, no browser)
sys.path.insert(0, os.path.join(REPO, "studio"))
R = load("rubric"); M = load("measure")
# evidence for an element outside its screenshot (zero-size, or below a viewport shot) never fails the audit
# (an audit of the GITCRAFT Reports pages died at the report stage: "Coordinate 'right' is less than 'left'")
try:
    from PIL import Image as _I
    RP = load("report"); _shot = os.path.join(ws, "ev_shot.png"); _I.new("RGB", (400, 300), (255, 255, 255)).save(_shot)
    _caps = [{"screen": "s", "viewport": "iphone17", "shot": _shot, "full": _shot, "dom": {"vw": 400, "vh": 300, "sw": 400}}]
    _f = [{"id": "x.off", "occurrences": [{"screen": "s", "viewport": "iphone17", "rect": [900, 40, 80, 16], "fixed": True},
                                          {"screen": "s", "viewport": "iphone17", "rect": [10, 20, 0, 0], "fixed": True}]}]
    made = RP.annotate(_f, _caps, os.path.join(ws, "ev"))
    check("evidence: an element outside its screenshot gets the screen as evidence, never a crashed audit",
          len(made) == 2 and _f[0]["occurrences"][0].get("evidence_note"), made)
except ImportError:
    print("SKIP evidence crop: Pillow not in this Python (run with the Studio venv)")
mk = lambda area, mid, v, ev="measured", **k: dict(area=area, id=mid, title=mid, value=v, samples=1, evidence=ev, **k)
areas = R.area_scores([mk("spacing", "a", 1.0), mk("layout", "b", 1.0)])
cats, ov = R.categories(areas, {"screens": 1, "viewports": 1})
check("rules: an area with no evidence is 'not tested' (None), never zero", areas["typography"]["score"] is None and areas["typography"]["awarded"] is None)
check("rules: scores are not capped — perfect measured evidence scores 100", cats["visual"]["score"] == 100.0, cats["visual"])
check("rules: coverage is reported separately (visual 50%, usability 0%) and drives confidence, not the score",
      cats["visual"]["coverage"] == 0.5 and cats["usability"]["score"] is None and ov["confidence"] == "low", (cats["visual"]["coverage"], ov))
check("rules: categories are independent (a missing category does not lower another)", cats["consistency"]["score"] is None and cats["visual"]["score"] == 100)
a2 = R.area_scores([mk("layout", "layout.overflow", 0.0, screen="s1"), *[mk("layout", "layout.alignment", 1.0, screen=f"s{i}") for i in range(10)]])
check("rules: one critical overflow weighs more than ten clean alignment samples", a2["layout"]["score"] < 0.5, a2["layout"]["score"])
a3 = R.area_scores([mk("layout", "x", 0.2, screen="a"), mk("layout", "x", 1.0, screen="b"), mk("layout", "x", 1.0, screen="c")])
check("rules: a defect on one screen pulls the metric down (mean pulled towards the worst)", a3["layout"]["score"] < 0.8, a3["layout"]["score"])
F = R.prioritise({"x": {"id": "x", "impact": 5, "cost": 1, "severity": "critical", "occurrences": [{"screen": s, "viewport": "v"} for s in "abc"]},
                  "y": {"id": "y", "impact": 1, "cost": 3, "severity": "cosmetic", "occurrences": [{"screen": "a", "viewport": "v"}]}}, 3)
check("rules: findings are grouped (frequency) and ranked by impact x frequency / cost", F[0]["id"] == "x" and F[0]["frequency"] == 3 and F[0]["tier"] == "fix now" and F[1]["tier"] == "polish", [(f["id"], f["priority"]) for f in F])
# geometry: a 573-px page on a 402-px phone profile overflows even though innerWidth grew with it
cap = {"screen": "s", "viewport": "iphone17", "dom": {"els": [{"i": 0, "p": None, "tag": "table", "sel": "table.wide", "r": [13, 300, 560, 100], "d": 3, "disp": "table"}], "vw": 573, "vh": 874, "sw": 573, "cw": 402}}
caps, C = M.analyse({"captures": [cap], "screens": [], "journeys": []}, [{"name": "iphone17", "width": 402, "height": 874, "mobile": True}])
check("measure: overflow uses the profile's CSS width and names the culprit element", "layout.overflow" in C.findings and C.findings["layout.overflow"]["occurrences"][0]["selector"] == "table.wide", list(C.findings))
els = [{"i": 0, "p": None, "tag": "p", "sel": "p", "r": [0, 0, 300, 40], "d": 2, "t": "Read the full terms of service before you continue", "tl": 70, "fs": 15},
       {"i": 1, "p": 0, "tag": "a", "sel": "p > a", "r": [100, 0, 40, 18], "d": 3, "inter": 1, "k": "link", "name": "terms", "t": "terms", "tl": 5, "fs": 15}]
caps, C = M.analyse({"captures": [{"screen": "s", "viewport": "iphone17", "dom": {"els": els, "vw": 402, "vh": 874, "sw": 402, "cw": 402}}], "screens": [], "journeys": []},
                    [{"name": "iphone17", "width": 402, "height": 874, "mobile": True}])
check("measure: an inline text link is exempt from the 44-px target rule (WCAG 2.5.8)", "controls.small_target" not in C.findings, list(C.findings))
D = load("dept")
before = {"method": R.METHOD, "metrics": [mk("accessibility", "a11y.axe", 0.4, "accessibility", screen="home", viewport="iphone17"), mk("layout", "layout.overflow", 1.0, screen="home", viewport="iphone17")], "findings": [], "gallery": []}
after = {"method": R.METHOD, "metrics": [mk("layout", "layout.overflow", 1.0, screen="home", viewport="iphone17")], "findings": [], "gallery": []}
cmp = D.compare(before, after, os.path.join(ws, "cmp"))
check("verify rules: a score cannot rise because a check was removed (lost coverage is reported, deltas use shared metrics only)",
      cmp["coverage_lost"] and cmp["scores"]["usability"]["delta"] is None and cmp["scores"]["visual"]["delta"] == 0, cmp)
cmp2 = D.compare(dict(before, method="pixelcraft-0.9"), after, os.path.join(ws, "cmp"))
check("verify rules: a different method is not comparable", cmp2["comparable"] is False)
TL = load("tells")
caps_t = [{"screen": "home", "viewport": v, "tells": {"glow_shadow": {"count": 2, "examples": [{"sel": "a.cta", "text": "Go"}]}, "gradient_text": {"count": 1, "examples": []}}} for v in ("iphone17", "desktop")]
T1 = TL.aggregate(caps_t, [{"id": "glow_shadow", "reason": "neon arcade HUD"}])
check("tells rules: advisory and unscored; an accepted tell is listed as accepted with its reason, not raised",
      T1["advisory"] and T1["scored"] is False and [r["id"] for r in T1["raised"]] == ["gradient_text"] and T1["accepted"][0]["accepted"] == "neon arcade HUD"
      and T1["accepted"][0]["count"] == 4 and len(T1["accepted"][0]["examples"]) == 1, T1)
tc = TL.compare(T1, TL.aggregate(caps_t[:1], []))
check("tells rules: before/after is informational (resolved/persisting/new), never a regression", tc == {"resolved": [], "persisting": ["gradient_text"], "new": ["glow_shadow"], "checked_before": True}, tc)
cmp3 = D.compare(dict(before, tells=T1), dict(after, tells=TL.aggregate(caps_t, [])), os.path.join(ws, "cmp"))
check("tells rules: a new tell adds no regression to verify", not any("glow" in x.lower() or "tell" in x.lower() for x in cmp3["regressions"]), cmp3["regressions"])

# ---------------------------------------------------------------- through the sandboxed MCP server
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=env, log=os.path.join(ws, "studiocraft.log"))
tools = {t["name"] for t in c.tools()}
want = {f"pixelcraft_{a}" for a in ("profiles", "discover", "audit", "verify", "history")}
check("studiocraft lists every PIXELCRAFT action as a tool", want <= tools, sorted(want - tools))
ok, st = c.call("studio_status")
px = next((d for d in st["departments"] if d["department"] == "pixelcraft"), None)
check("pixelcraft is discovered as a Studio department, actions ready", px and all(v == "ready" for v in px["actions"].values()), px)
ok, r = c.call("pixelcraft_profiles", {"out_dir": f"{ws}/profiles"})
check("profiles: iPhone 17 is 402x874 and iPhone 13 390x844 CSS px; three 100-point categories",
      ok and r["viewports"]["iphone17"]["width"] == 402 and r["viewports"]["iphone17"]["height"] == 874 and r["viewports"]["iphone13"]["width"] == 390
      and all(sum(a["points"] for a in cat["areas"].values()) == 100 for cat in r["categories"].values()), r if not ok else "")
ok, r = c.call("route", {"brief": "audit my app's spacing, button sizes and mobile layout"})
check("routing: a UI/spacing brief goes to pixelcraft", ok and r["chosen"] and r["chosen"]["department"] == "pixelcraft", r.get("chosen") if isinstance(r, dict) else r)
ok, r = c.call("pixelcraft_audit", {"target": "/root", "out_dir": f"{ws}/bad"})
check("a target outside the workspace roots is refused (GITCRAFT policy)", not ok and "GITCRAFT policy" in str(r), r)
ok, r = c.call("pixelcraft_audit", {"target": APP, "viewports": ["desktop"], "out_dir": f"{ws}/bad2"})
check("iPhone-first is mandatory: a desktop-only audit is refused", not ok and "iPhone" in str(r), r)
ok, r = c.call("pixelcraft_audit", {"target": APP, "judgements": [{"area": "layout", "score": 0.5, "evidence": "measured"}], "out_dir": f"{ws}/bad3"})
check("judgements cannot claim 'measured' evidence", not ok and "measured" in str(r), r)

# ---------------------------------------------------------------- the audit
VPS = ["iphone17", "iphone13", "desktop"] if QUICK else None
t = time.time()
ok, r = c.call("pixelcraft_audit", dict({"project": APP, "target": APP, "app": "Taskboard", "journeys": JOURNEYS, "out_dir": f"{ws}/audit"}, **({"viewports": VPS} if VPS else {})), timeout=1500)
good = ok and r.get("status") == "ok"
check(f"audit: Taskboard audited ({time.time() - t:.0f} s)", good, r.get("error") if isinstance(r, dict) else r)
A = json.load(open(f"{ws}/audit/audit.json")) if good else None
if A:
    F = {f["id"]: f for f in A["findings"]}
    names = [v["name"] for v in A["viewports"]]
    check("audit: discovered the four screens (task detail template counted once)", [s["name"] for s in A["screens"]] == ["home", "task-item", "projects", "settings"], [s["name"] for s in A["screens"]])
    check("audit: real screenshots for every screen at every viewport", all(os.path.exists(os.path.join(ws, "audit", g["shot"])) for g in A["gallery"]) and len(A["gallery"]) == 4 * len(names), len(A["gallery"]))
    expect = {"mobile.home_indicator": "tab bar under the home indicator (safe area emulated)", "mobile.input_zoom": "13-px inputs zoom on iPhone",
              "layout.overflow": "the projects table overflows the phone", "controls.small_target": "16-30 px targets", "controls.too_close": "icon buttons 3 px apart",
              "spacing.uneven": "list gaps 6/14/3 px", "keyboard.no_focus": "outline removed", "journey.confirmations": "two confirmations to delete",
              "journey.no_feedback": "Save does nothing", "states.disabled_lookalike": "disabled Reset looks enabled", "axe.color-contrast": "pale grey text",
              "controls.competing_primary": "two filled primaries side by side", "type.too_small": "10-px metadata"}
    for fid, what in expect.items():
        check(f"audit finds: {what} ({fid})", fid in F, sorted(F))
    ov = F.get("layout.overflow", {}).get("occurrences", [{}])[0]
    check("finding evidence: overflow names screen, viewport, selector and the measured widths",
          ov.get("screen") == "projects" and ov.get("viewport") in ("iphone17", "iphone13", "narrow") and "table" in (ov.get("selector") or "") and ov["measured"].get("overflow_px", 0) > 100, ov)
    hi = F.get("mobile.home_indicator", {}).get("occurrences", [{}])[0]
    check("finding evidence: safe-area finding carries the emulated inset and an annotated screenshot crop",
          hi.get("measured", {}).get("safe_area_bottom_px") == 34 and hi.get("evidence") and os.path.exists(os.path.join(ws, "audit", hi["evidence"])), hi)
    check("every finding has severity, evidence kind, explanation, recommendation and located occurrences",
          all(f["severity"] in M.SEV and f["evidence"] in ("measured", "accessibility", "screenshot", "source") and f["explanation"] and f["recommendation"] and f["occurrences"]
              and all(o.get("viewport") for o in f["occurrences"]) for f in A["findings"]))
    check("findings are grouped, not dozens of duplicates (< 40 findings for 4 screens x all viewports)", len(A["findings"]) < 40, len(A["findings"]))
    jr = {(j["name"], j["viewport"]): j for j in A["journeys"]}
    cj = jr.get(("complete a task", "iphone17"))
    check("journey: 'complete a task' measured taps (2) and confirmations (2) with feedback times", cj and cj["taps"] == 2 and cj["confirmations"] == 2 and all(s.get("feedback_ms") is not None for s in cj["steps"] if s.get("tap")), cj)
    o, cs = A["overall"], A["categories"]
    check("scores: three independent categories with coverage, sample app scores fair-to-weak (55-80)", all(cs[k]["score"] is not None for k in cs) and 55 <= o["score"] <= 80, {k: cs[k]["score"] for k in cs} | {"overall": o["score"]})
    check("confidence is separate from the score and says emulation-only", "browser emulation only (no physical-device evidence)" in o["confidence_reasons"], o)
    rep = open(f"{ws}/audit/report.md").read(); html = open(f"{ws}/audit/report.html").read()
    secs = ["1. Overall PIXELCRAFT score", "2. Category scores", "3. Strongest screens", "4. Weakest screens", "5. Critical usability defects", "6. Spacing and layout defects",
            "7. Button and control defects", "8. Mobile-specific findings", "9. Screenshot gallery", "10. Prioritised improvement plan"]
    check("report.md has the ten sections", all(s in rep for s in secs), [s for s in secs if s not in rep])
    check("report.html renders the same sections with images", all(s.split(". ", 1)[1] in html for s in secs) and html.count("<img") > 10)
    check("measured, accessibility and source/screenshot kinds are kept apart in the metrics", {"measured", "accessibility"} <= set(A["evidence_mix"]), A["evidence_mix"])
    check("tells: checked on every capture, kept out of metrics, findings and the plan", A.get("tells") and A["tells"]["captures_checked"] == len(A["gallery"])
          and not any(m["id"].startswith("tell") for m in A["metrics"]) and not any(f["id"].startswith("tell") for f in A["findings"]), (A.get("tells") or {}).get("captures_checked"))

# ---------------------------------------------------------------- generic design tells on rendered pages
TV = ["iphone17", "iphone13", "desktop"]
for name in ("tells_generic", "tells_crafted"):
    shutil.rmtree(os.path.join(ws, name), ignore_errors=True); shutil.copytree(os.path.join(FIX, name), os.path.join(ws, name))
ok, r = c.call("pixelcraft_audit", {"target": f"{ws}/tells_generic", "viewports": TV, "record": False, "out_dir": f"{ws}/tells_generic_out"}, timeout=900)
TG = json.load(open(f"{ws}/tells_generic_out/audit.json"))["tells"] if ok and r.get("status") == "ok" else {}
raised = {x["id"] for x in TG.get("raised", [])}
check("tells: every generic default on the fixture is raised from the rendered page", raised == set(TL.ORDER), sorted(set(TL.ORDER) ^ raised))
gt = next((x for x in TG.get("raised", []) if x["id"] == "gradient_text"), {})
check("tells: each raised tell names the element, screen and viewport, and asks a question", gt.get("examples") and gt["examples"][0]["sel"] == "span.grad" and gt["examples"][0]["viewport"] in TV and gt.get("ask"), gt)
rep_t = open(f"{ws}/tells_generic_out/report.md").read() if ok else ""
check("tells: report.md has the advisory section, separate from the scored ones", "Generic design tells (advisory, not scored)" in rep_t)
ok, r = c.call("pixelcraft_audit", {"target": f"{ws}/tells_crafted", "viewports": TV, "record": False, "out_dir": f"{ws}/tells_crafted_out"}, timeout=900)
TC = json.load(open(f"{ws}/tells_crafted_out/audit.json"))["tells"] if ok and r.get("status") == "ok" else None
check("tells: no false positive on a page with a decided identity (serif display, offset shadows, own palette)", TC is not None and TC["raised"] == [] and TC["captures_checked"] == 3, TC)
ok, r = c.call("pixelcraft_audit", {"target": f"{ws}/tells_generic", "viewports": TV, "record": False, "out_dir": f"{ws}/tells_accept_out",
                                    "accept_tells": [{"id": "glow_shadow", "reason": "the brand's signature halo"}, "default_type"]}, timeout=900)
TA = json.load(open(f"{ws}/tells_accept_out/audit.json")) if ok and r.get("status") == "ok" else {}
G0 = json.load(open(f"{ws}/tells_generic_out/audit.json")) if os.path.exists(f"{ws}/tells_generic_out/audit.json") else {}
check("tells: accept_tells moves a chosen tell to 'accepted' and leaves every score unchanged",
      TA and {x["id"] for x in TA["tells"]["accepted"]} == {"glow_shadow", "default_type"} and "glow_shadow" not in {x["id"] for x in TA["tells"]["raised"]}
      and TA["overall"]["score"] == G0.get("overall", {}).get("score") and TA["replay"]["accept_tells"], (TA.get("tells", {}).get("accepted"), TA.get("overall"), G0.get("overall")))

# ---------------------------------------------------------------- verify: the fixed app on a git repo
if A:
    git = lambda *x: subprocess.run(["git", "-C", APP, "-c", "user.email=t@t", "-c", "user.name=t", *x], capture_output=True, text=True)
    git("init", "-q", "-b", "main"); git("add", "."); git("commit", "-qm", "taskboard first cut")
    git("checkout", "-qb", "pixelcraft/fixes")
    for f in os.listdir(os.path.join(FIX, "taskboard_fixed")): shutil.copyfile(os.path.join(FIX, "taskboard_fixed", f), os.path.join(APP, f))
    git("commit", "-qam", "PIXELCRAFT fixes")
    t = time.time()
    ok, v = c.call("pixelcraft_verify", {"baseline": f"{ws}/audit/audit.json", "project": APP, "out_dir": f"{ws}/verify",
                                         "changes": [{"title": "spacing scale, 44-px targets, safe areas, states", "files": [os.path.join(APP, "app.css"), os.path.join(APP, "app.js")]}]}, timeout=1500)
    check(f"verify: replayed the baseline on the fixed app ({time.time() - t:.0f} s)", ok and v.get("status") == "ok", (v.get("error") if isinstance(v, dict) else v))
    if ok and os.path.exists(f"{ws}/verify/comparison.json"):
        cmpj = json.load(open(f"{ws}/verify/comparison.json")); V = json.load(open(f"{ws}/verify/audit.json"))
        res = {x["id"] for x in cmpj["resolved"]}
        check("verify: the overall score rose by more than 15 on the same metrics", (cmpj["scores"]["overall"]["delta"] or 0) > 15, cmpj["scores"])
        check("verify: every category improved", all((cmpj["scores"][k]["delta"] or 0) > 0 for k in ("visual", "usability", "consistency")), cmpj["scores"])
        for fid in ("mobile.home_indicator", "mobile.input_zoom", "layout.overflow", "spacing.uneven", "keyboard.no_focus", "journey.confirmations", "journey.no_feedback", "axe.color-contrast"):
            check(f"verify: {fid} resolved", fid in res, sorted(res))
        check("verify: same screens, viewports and journeys as the baseline", [s["name"] for s in V["screens"]] == [s["name"] for s in A["screens"]] and
              [v_["name"] for v_ in V["viewports"]] == [v_["name"] for v_ in A["viewports"]] and {j["name"] for j in V["journeys"]} == {j["name"] for j in A["journeys"]})
        check("verify: no coverage lost and no regressions", not cmpj["coverage_lost"] and not cmpj["regressions"], (cmpj["coverage_lost"], cmpj["regressions"]))
        check("verify: screenshot diffs for every screen x viewport", len(cmpj["screens"]) == len(A["gallery"]) and all(os.path.exists(os.path.join(ws, "verify", d["diff"])) for d in cmpj["screens"]), len(cmpj["screens"]))
        check("verify: the commit of the fixed app is recorded", (V["app"].get("git") or {}).get("branch") == "pixelcraft/fixes")
    # a regression must fail verify: break the fixed app's safe-area padding and restore a tiny button
    css = open(os.path.join(APP, "app.css")).read().replace("padding: 0 env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);", "")
    open(os.path.join(APP, "app.css"), "w").write(css)
    ok, v2 = c.call("pixelcraft_verify", {"baseline": f"{ws}/verify/audit.json", "project": APP, "out_dir": f"{ws}/verify_regress", "record": False}, timeout=1500)
    check("verify: a change that reintroduces the home-indicator overlap fails with a regression",
          isinstance(v2, dict) and v2.get("status") == "failed" and "regression" in str(v2.get("error")) and "home indicator" in str(v2.get("error")).lower(), (v2.get("error") if isinstance(v2, dict) else v2))

# ---------------------------------------------------------------- a running app (localhost)
def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


port = free_port()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", os.path.join(FIX, "taskboard")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.0)
try:
    ok, r = c.call("pixelcraft_discover", {"target": f"http://127.0.0.1:{port}/", "out_dir": f"{ws}/url_blocked"})
    check("a localhost app is blocked by the sandbox until its port is allowed (and the result says how)", isinstance(r, dict) and r.get("status") == "blocked" and "GITCRAFT_ALLOW_LOCAL_PORTS" in json.dumps(r), r)
    c2 = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=dict(env, GITCRAFT_ALLOW_LOCAL_PORTS=str(port)), log=os.path.join(ws, "studiocraft2.log"))
    ok, r = c2.call("pixelcraft_discover", {"target": f"http://127.0.0.1:{port}/", "out_dir": f"{ws}/url"}, timeout=600)
    check("a running app (http://127.0.0.1:<port>) is opened and its screens discovered", ok and r.get("status") == "ok" and len(r["screens"]) == 4, (r.get("error") if isinstance(r, dict) else r))
finally:
    srv.terminate()

# ---------------------------------------------------------------- a page two links deep: its journey starts at the entry
# (the journey to the Game Quality History's game page was replayed from the 3D home with only its last click, "Open its
# history", and reported as a critical "journey cannot be completed")
deep = os.path.join(ws, "deep_site"); os.makedirs(os.path.join(deep, "section"), exist_ok=True)
page = lambda title, body: f"<!doctype html><html lang=en><head><meta name=viewport content='width=device-width, initial-scale=1'><title>{title}</title></head><body><main><h1>{title}</h1>{body}</main></body></html>"
open(os.path.join(deep, "index.html"), "w").write(page("Home", "<p>Start here and pick a section to read.</p><a href='section/'>Section</a>"))
open(os.path.join(deep, "section", "index.html"), "w").write(page("Section", "<p>This section lists one detail page.</p><a href='detail.html'>Open detail</a>"))
open(os.path.join(deep, "section", "detail.html"), "w").write(page("Detail", "<p>The detail page, two links from the entry.</p>"))
ok, r = c.call("pixelcraft_discover", {"target": deep, "viewports": ["iphone17", "iphone13", "desktop"], "out_dir": f"{ws}/deep"}, timeout=600)
D = {s["name"]: s for s in (r.get("screens") or [])} if ok and isinstance(r, dict) else {}
two = next((s for s in D.values() if s.get("depth") == 2), None)
check("discover: a page two links deep keeps the whole path from the entry (both clicks), not only the last",
      two is not None and [x.get("click") for x in two.get("link_steps", [])] == ["Section", "Open detail"], {k: (v.get("depth"), v.get("link_steps")) for k, v in D.items()} or r)

# ---------------------------------------------------------------- a canvas game: measured as a game, not a form
if not QUICK:
    game = os.path.join(ws, "arcade_dodge"); shutil.rmtree(game, ignore_errors=True); shutil.copytree(os.path.join(HERE, "fixtures", "playcraft", "arcade_dodge"), game)
    ok, r = c.call("pixelcraft_audit", {"target": game, "viewports": ["iphone17", "iphone13", "desktop"], "out_dir": f"{ws}/game"}, timeout=900)
    G = json.load(open(f"{ws}/game/audit.json")) if ok else None
    check("game: a canvas game is audited and its confidence notes the canvas", G and "canvas-rendered screens: the DOM does not describe what is drawn" in G["overall"]["confidence_reasons"], (r.get("error") if isinstance(r, dict) else r))
    if G:
        check("game: the 28-px mute button is caught as a small touch target", any(f["id"] == "controls.small_target" for f in G["findings"]), [f["id"] for f in G["findings"]])
        check("game: no layout-density or utilisation penalty for a full-screen canvas", not any(f["id"] in ("layout.narrow_desktop", "spacing.void", "layout.misaligned") for f in G["findings"]), [f["id"] for f in G["findings"]])

# ---------------------------------------------------------------- history + site
ok, h = c.call("pixelcraft_history", {"out_dir": f"{ws}/hist_out"})
runs = [json.loads(l) for l in open(os.path.join(HIST, "index.jsonl"))] if os.path.exists(os.path.join(HIST, "index.jsonl")) else []
check("history: audit and verify runs recorded (append-only index + report folders)", ok and {"audit", "verify"} <= {x["kind"] for x in runs} and all(os.path.exists(os.path.join(HIST, x["app"], x["run"], "report.html")) for x in runs), runs[-3:])
check("history: the non-recorded regression check left no record", not any("verify_regress" in json.dumps(x) for x in runs))
S = load("site")
n = S.publish_site(HIST, os.path.join(ws, "site"))
page = open(os.path.join(ws, "site", "index.html")).read() if n else ""
check("site: the PIXELCRAFT audits page publishes every recorded run with links to the reports", n == len(runs) and "Taskboard" in page and "report.html" in page, n)

c.close() if hasattr(c, "close") else None
bad = [l for l, ok_ in results if not ok_]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; outputs in {ws}" if bad or os.environ.get("GITCRAFT_PIXELCRAFT_PROOF") else ""))
sys.exit(1 if bad else 0)
