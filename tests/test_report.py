#!/usr/bin/env python3
""""Run GITCRAFT report": one read-only report across every department (production/project_report.py).

Checks: the department list comes from the code; recorded results are reported exactly as recorded (never invented);
nothing is written inside the project; reports are saved timestamped and compared with the previous one; the
reconciliation and the P0–P3 plan; the entry point and the MCP tool; the mobile HTML and the published site."""
import glob, hashlib, json, os, re, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
WS = tempfile.mkdtemp(prefix="gcr-test-")
os.environ.update(GITCRAFT_ROOTS=WS, GITCRAFT_REPORTS=os.path.join(WS, "reports"), GITCRAFT_PRODUCTION_HOME=os.path.join(WS, "prod"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(WS, "none", "catalog.sqlite"), GITCRAFT_3D_LIBRARY=os.path.join(WS, "none-3d"),
                  GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(WS, "none-px"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(WS, "none-pc"))
from production import project_report as PR, entry  # noqa: E402

fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  {str(detail)[:400]}"))
    fails += 0 if cond else 1


def tree_hash(root):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds.sort()
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
        h.update(("D" + os.path.relpath(d, root)).encode())
    return h.hexdigest()


# ---------------------------------------------------------------- 1. departments come from the code
D = PR.departments()
manifests = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(REPO, "studio", "departments", "*", "manifest.json")))
ids = [d["id"] for d in D]
check("departments: every Studio manifest, plus DESIGNCRAFT, the 3D Department and the Production Director, nothing invented",
      sorted(i for i in ids if i in manifests) == manifests and set(ids) - set(manifests) == {"designcraft", "3d", "production"} and len(ids) == len(set(ids)), ids)

# ---------------------------------------------------------------- 2. history-only report: exactly what was recorded
R = PR.generate("scottyfncodes--rockslide", save="none")
dd = {d["id"]: d for d in R["departments"]}
idx = [json.loads(l) for l in open(os.path.join(REPO, "history", "designcraft", "index.jsonl")) if l.strip()]
dc_latest = [x for x in idx if x["game"] == "scottyfncodes--rockslide"][-1]
check("history-only: DESIGNCRAFT score is the recorded latest run's", dd["designcraft"]["score"]["value"] == dc_latest["overall"], (dd["designcraft"]["score"], dc_latest["overall"]))
pc_runs = sorted(glob.glob(os.path.join(REPO, "history", "playcraft", "games", "scottyfncodes--rockslide", "runs", "*.json")))
pc_scores = {json.load(open(p))["run_id"]: json.load(open(p))["overall"]["score"] for p in pc_runs}
check("history-only: PLAYCRAFT score is a recorded run's, with its run id", pc_scores.get(dd["playcraft"]["run"]["id"]) == dd["playcraft"]["score"]["value"], dd["playcraft"]["run"])
check("history-only: departments without results have no score and status no_data/unavailable/not_applicable",
      all(d["score"] is None and d["status"] in ("no_data", "unavailable", "not_applicable") for i, d in dd.items() if i not in ("playcraft", "designcraft")),
      {i: (d["status"], d["score"]) for i, d in dd.items()})
from production import scoring as SC  # noqa: E402
wp, wd = SC.RUBRICS["playcraft"]["weight"], SC.RUBRICS["designcraft"]["weight"]
cw = lambda i, w: w * SC.CONFIDENCE_WEIGHT.get(str(dd[i]["quality"].get("confidence") or "medium").lower(), 0.75)   # weight scaled by the department's confidence
ep, ed = cw("playcraft", wp), cw("designcraft", wd)
check("history-only: the overall score is the confidence-weighted rubric mean of the evaluated scores only, with its basis and method",
      R["health"]["parts"] == {"playcraft": dd["playcraft"]["score"]["value"], "designcraft": dc_latest["overall"]} and R["health"]["method"] == SC.METHOD
      and abs(R["health"]["score"] - (dd["playcraft"]["score"]["value"] * ep + dc_latest["overall"] * ed) / (ep + ed)) < 0.06 and "weighted mean" in R["health"]["basis"], R["health"])
ne = [d for d in R["departments"] if d["quality"]["evaluation"] == "not_evaluated"]
check("Not Evaluated: applicable departments without a measured result have no value and no weight in the overall score",
      ne and all(d["quality"]["value"] is None and d["id"] not in R["health"]["parts"] and d["quality"].get("why") for d in ne), [(d["id"], d["quality"]) for d in ne])
check("coverage: evaluated weight ÷ applicable weight, shown beside the score (never folded in)",
      abs(R["health"]["coverage"] - (wp + wd) / sum(d["quality"]["weight"] for d in R["departments"] if d["quality"]["evaluation"] != "not_applicable")) < 0.01, R["health"])
check("every department has a rubric (label, weight, version, source, criteria)", all(d["quality"]["rubric"] and d["quality"]["criteria"] and d["quality"]["source"] for d in R["departments"]))
# method change, against the archived reports made before the rubrics (plain mean, report 1.0.0)
legacy_rs = sorted((json.load(open(p)) for p in glob.glob(os.path.join(REPO, "history", "reports", "scottyfncodes--rockslide", "*", "report.json"))), key=lambda x: x["generated"])
legacy_rs = [x for x in legacy_rs if not (x.get("health") or {}).get("method")]
vp = SC.overall_delta(legacy_rs[-1], R["health"])
check("method change: an archived plain-mean report is never compared as if it were the same method", legacy_rs and vp["delta"] is None and "method changed" in vp["compare"], vp)
cp = json.loads(json.dumps(R["departments"])); SC.deltas(legacy_rs[-1], cp); cq = {d["id"]: d["quality"] for d in cp}
check("method change: a department whose rubric is unchanged keeps its previous score; one whose rubric changed is not compared",
      cq["playcraft"]["previous"] is not None and cq["production"].get("delta") is None, (cq["playcraft"], cq["production"]))
T = SC.series(legacy_rs, R)
check("trend: every earlier report of the project, the method recorded per point", len(T) == len(legacy_rs) + 1 and T[-1]["method"] == SC.METHOD
      and all(p["method"] == SC.LEGACY_METHOD for p in T[:-1]), [(p["report_id"], p["method"]) for p in T])
check("trend chart: points from different methods are not joined (the plain-mean points and the weighted point are separate)",
      "method changed" in PR.chart_svg(T) and PR.chart_svg(T).count("<polyline") == (1 if len(legacy_rs) > 1 else 0), PR.chart_svg(T)[:300])
check("trend: the report's own trend reads the saved history (store + archive)", len(R["trend"]) >= 2 and R["trend"][-1]["report_id"] == R["report_id"])
check("top actions: three at most, impact from the priority rule, effort only from a department's own estimate",
      0 < len(R["top_actions"]) <= 3 and all(a["impact"].split()[0] == SC.IMPACT[a["priority"]] for a in R["top_actions"])
      and all((a["effort"] is None) == (a["effort_basis"] == "not estimated by the department") for a in R["top_actions"]), R["top_actions"])
fk = {f["key"]: f for d in R["departments"] for f in d["findings"]}
acts = {a["n"]: a for a in R["actions"]}
labels = lambda a: [SC.effort_label(fk[k].get("effort")) for k in acts[a["n"]]["findings"] if k in fk and SC.effort_label(fk[k].get("effort"))]
check("effort: taken from the action's own findings' department estimates, never attached when none gave one",
      all((a["effort"] is None and not labels(a)) or (a["effort"] in labels(a)) for a in R["top_actions"]), [(a["title"], a["effort"], labels(a)) for a in R["top_actions"]])
check("delta: two re-analyses (both 'this report') at different times are different measurements",
      not SC.same_measurement({"id": "this report", "at": "2026-11-08T19:42:45"}, {"id": "this report", "at": "2026-11-09T13:09:24"})
      and SC.same_measurement({"id": "r1", "at": "2026-11-04T23:46:23+00:00"}, {"id": "r1", "at": "2026-11-04T23:46:23+00:00"}))
check("gates: with no production there is no Director verdict and no gate (said plainly)", R["gates"]["verdict"] is None and "No production" in R["gates"]["note"])
check("identity: project, commit (from the department run, labelled), run date", R["identity"]["repo"] == "scottyfncodes/rockslide" and R["identity"]["commit"]
      and R["identity"]["commit_source"] == "latest department run", R["identity"])
# an older recorded measurement read after a re-analysed one is not a regression
prev_fake = {"report_id": "x/1", "generated": "2026-11-09T00:00:00+00:00", "health": {"score": 60, "method": SC.METHOD},
             "departments": [{"id": "designcraft", "quality": {"value": 99, "rubric": "designcraft/1", "method": dd["designcraft"]["quality"]["method"]}, "run": {"id": "other", "at": "2099-01-01T00:00:00"}}]}
cp = json.loads(json.dumps(R["departments"])); SC.deltas(prev_fake, cp)
q = {d["id"]: d for d in cp}["designcraft"]["quality"]
check("delta: a previous re-analysis newer than today's recorded run is not compared (no false regression)", q["delta"] is None and "older measurement" in q["compare"], q)
prev_fake["departments"][0]["run"]["at"] = "2000-01-01T00:00:00"; cp = json.loads(json.dumps(R["departments"])); SC.deltas(prev_fake, cp)
q = {d["id"]: d for d in cp}["designcraft"]["quality"]
check("delta: same rubric and method, newer measurement → a signed delta against the previous score", q["delta"] == round(dc_latest["overall"] - 99, 1) and q["compare"] == "new measurement", q)
check("history-only: what could not be refreshed is listed with the reason", any(x["department"] == "playcraft" and "not checked out" in x["why"] for x in R["not_refreshed"]), R["not_refreshed"])
check("every finding keeps an evidence level and a department", all(f["level"] in ("verified", "observed", "inferred") and f["department"] for d in R["departments"] for f in d["findings"]))
check("plan: P0–P3 only, numbered, each with its departments", R["actions"] and all(a["priority"] in ("P0", "P1", "P2", "P3") and a["departments"] for a in R["actions"])
      and [a["n"] for a in R["actions"]] == list(range(1, len(R["actions"]) + 1)))
check("plan: measured major findings outrank inferred ones", all(a["priority"] in ("P0", "P1") for a in R["actions"] if a["level"] in ("verified", "observed") and "Text" in a["title"]))
check("plan: gaps (no data) are listed as actions, not as results", any(a["level"] == "unavailable" and "PIXELCRAFT" in a["title"] for a in R["actions"]))
rc = R["reconciliation"]
check("reconciliation: corroborated areas name ≥2 departments; conflicts compare the same category", all(len(c["departments"]) >= 2 for c in rc["corroborated"])
      and all(len(c["departments"]) == 2 for c in rc["conflicts"]), rc)

# ---------------------------------------------------------------- 3. a local project: read-only, refreshed, saved, compared
game = os.path.join(WS, "orbit")
os.makedirs(os.path.join(game, "src")); os.makedirs(os.path.join(game, "qa"))
open(os.path.join(game, "index.html"), "w").write("<!doctype html><html lang=en><head><meta name=viewport content='width=device-width'><title>Orbit</title></head>"
                                                  "<body><canvas id=c></canvas><script src=src/main.js></script></body></html>")
open(os.path.join(game, "src", "main.js"), "w").write("const LEVELS=[{name:'One',goal:3},{name:'Two',goal:5}];\nfunction update(){ /* phaser-like loop: player jump score */ }\n")
json.dump({"department": "testcraft", "action": "smoke", "status": "ok", "created": "2026-11-01T10:00:00+00:00",
           "checks": [{"name": "loads without console errors", "ok": True}, {"name": "no horizontal scroll on phone", "ok": False, "detail": "scrollWidth 431 > 390"}]},
          open(os.path.join(game, "qa", "smoke.studio.json"), "w"))
subprocess.run(["git", "init", "-q", game]); subprocess.run(["git", "-C", game, "add", "-A"]); subprocess.run(["git", "-C", game, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"])
before = tree_hash(game)
# refresh=quick smoke-tests an existing build (tests/test_report_trust.py covers it): here the Studio is stubbed as absent so
# the records read are exactly the fixture's (deterministic with or without a browser)
PR._studio_call = lambda action, args, timeout=3600, env=None: (None, "the Studio runtime is not installed (stubbed in this test)")
R1 = PR.generate(game)
check("read-only: the project is byte-identical after a report (no files, no folders)", tree_hash(game) == before)
check("saved: report.json, report.md, report.html in a timestamped folder outside the project",
      all(os.path.isfile(R1["paths"][k]) for k in ("json", "markdown", "html")) and re.search(r"/\d{8}T\d{6}Z$", R1["paths"]["dir"]) and not R1["paths"]["dir"].startswith(game), R1["paths"])
t1 = {d["id"]: d for d in R1["departments"]}["testcraft"]
check("records: TestCraft's own record is read (1/2 checks → score 50, failed check is a verified finding)",
      t1["score"]["value"] == 50.0 and any(f["level"] == "verified" and "horizontal" in f["title"] for f in t1["findings"]), t1)
check("records: a record dated before the project's latest commit is Stale (low confidence, never P0/P1)",
      t1["status"] == "stale" and t1["score"]["confidence"] == "low" and all(f.get("stale") for f in t1["findings"])
      and all(a["priority"] not in ("P0", "P1") for a in R1["actions"] if set(a["findings"]) & {f["key"] for f in t1["findings"]}), (t1["status"], t1["score"]))
p1 = {d["id"]: d for d in R1["departments"]}["production"]
check("refresh: Discovery and the engineering standard re-ran (read-only)", p1["status"] == "refreshed" and any("Discovery" in n for n in p1["notes"]), p1["notes"])
check("first report says so", R1["changes"]["first"] is True)
R2 = PR.generate(game, refresh="none")
check("second report compares against the first (health, departments, findings)", R2["changes"]["first"] is False and R2["changes"]["against"] == R1["report_id"]
      and "health" in R2["changes"], R2["changes"])
q1 = {d["id"]: d for d in R1["departments"]}; q2 = {d["id"]: d for d in R2["departments"]}
check("production rubric: the engineering standard is the Production Director's quality score; acceptance criteria are gates, not a score",
      q1["production"]["quality"]["label"] == "Engineering standard" and (q1["production"]["quality"]["value"] is None) == (not (q1["production"].get("standard") or {}).get("checks")), q1["production"]["quality"])
check("delta: the second report compares each evaluated department under the same rubric (testcraft 50 → 50, same measurement)",
      q2["testcraft"]["quality"]["previous"] == 50.0 and q2["testcraft"]["quality"]["delta"] == 0 and "same measurement" in q2["testcraft"]["quality"]["compare"]
      and R2["health"]["vs_previous"]["delta"] is not None, (q2["testcraft"]["quality"], R2["health"]["vs_previous"]))
check("regressions: none claimed without a measured drop", R2["regressions"] == [], R2["regressions"])
check("refresh none: nothing is re-analysed", all(not d["refresh"].get("ok") or d["id"] == "production" for d in R2["departments"]))
lines = [json.loads(l) for l in open(os.path.join(os.environ["GITCRAFT_REPORTS"], "index.jsonl"))]
check("index.jsonl: one line per saved report (append-only)", [l["report_id"] for l in lines][-2:] == [R1["report_id"], R2["report_id"]], lines)
try:
    PR.generate(game, out_dir=os.path.join(game, "report")); inside = False
except PermissionError:
    inside = True
check("read-only: a report folder inside the project is refused", inside and not os.path.exists(os.path.join(game, "report")))
check("read-only: still byte-identical after three reports", tree_hash(game) == before)

# ---------------------------------------------------------------- 4. entry point and tool
E = entry.start("Run GITCRAFT report", game)
check("'Run GITCRAFT report' → the report (status report, markdown, paths)", E["status"] == "report" and E["markdown"].startswith("# GITCRAFT report") and E["report"]["paths"].get("html"), E.get("status"))
check("'Run GITCRAFT report' with no project asks which one", entry.start("Run GITCRAFT report")["status"] == "needs_input")
E2 = entry.start("Run GITCRAFT report on https://github.com/scottyfncodes/rockslide")
check("a repository that is not cloned is reported from history, with the clone hint", E2["status"] == "report" and "git clone" in (E2.get("note") or ""), E2.get("note"))
check("other requests are untouched ('Run GITCRAFT: add dark mode' is not a report)", not entry.REPORT.match(entry.route("Run GITCRAFT: add dark mode")["request"]))
check("studiocraft exposes production_project_report", '"production_project_report"' in open(os.path.join(REPO, "studio", "server.py")).read())
out = subprocess.run([sys.executable, "-m", "production", "project-report", game, "--save", "none"], cwd=REPO, capture_output=True, text=True)
check("CLI: python3 -m production project-report", out.returncode == 0 and "## Prioritized action plan" in out.stdout, out.stderr[-300:])

# ---------------------------------------------------------------- 4b. every production run ends with a Production Report
from production import engine, store as pstore  # noqa: E402
pl = engine.plan("Run GITCRAFT: review this game", project=game)
pid = pl.get("production") or pl.get("id")
prod = pstore.load(pid)
info = engine.production_report(prod)
check("run → Production Report: written outside the project, linked from the production and its status",
      info["status"] == "ok" and os.path.isfile(info["html"]) and not info["html"].startswith(game) and pstore.load(pid).get("production_report", {}).get("html") == info["html"]
      and engine.status(pstore.load(pid))["production_report"]["html"] == info["html"], info)
Rp = json.load(open(info["json"]))
check("run → the Director's verdict and the gates come from that production; gates never enter the quality score",
      Rp["gates"]["production"] == pid and Rp["gates"]["verdict"] and Rp["gates"]["criteria"] and Rp["identity"]["verdict"] == Rp["gates"]["verdict"]
      and Rp["health"]["parts"].get("production") == {d["id"]: d for d in Rp["departments"]}["production"]["quality"]["value"]
      and {d["id"]: d for d in Rp["departments"]}["production"]["quality"]["label"] == "Engineering standard", Rp["gates"])
src = open(os.path.join(REPO, "production", "engine.py")).read()
check("run → the engine makes the report at the end of every run, before REPORT.md", src.index("production_report(prod)\n        _report.write(prod)") > 0)
os.environ["GITCRAFT_PRODUCTION_REPORT"] = "0"
check("run → GITCRAFT_PRODUCTION_REPORT=0 turns it off", engine.production_report(prod) is None); del os.environ["GITCRAFT_PRODUCTION_REPORT"]
check("read-only: still byte-identical after the production report", tree_hash(game) == before)

# ---------------------------------------------------------------- 5. the report reads well on a phone, and publishes
H = open(R1["paths"]["html"]).read()
check("html: the Production Report sections (identity, verdict, next 3, departments with deltas, trends, gates, findings, scoring)",
      all(f"id='{s}'" in H for s in ("top", "trends", "gates", "findings", "method")) and "Release / version" in H and "Director verdict" in H)
Hn = PR.render_html(R)
check("html: a Not Evaluated department shows 'Not Evaluated', never a number", Hn.count("Not Evaluated</span>") == len(ne), (Hn.count("Not Evaluated</span>"), len(ne)))
legacy = json.load(open(sorted(glob.glob(os.path.join(REPO, "history", "reports", "scottyfncodes--rockslide", "*", "report.json")))[0]))
Lr = PR.upgrade(legacy)
check("legacy reports (plain mean) render under the new layout with their recorded number, labelled as the old method",
      Lr["health"]["score"] == legacy["health"]["score"] and Lr["health"]["method"] == SC.LEGACY_METHOD and "id='gates'" in PR.render_html(Lr) and "gitcraft_report" in legacy)
check("html: self-contained, mobile viewport, every section", "width=device-width" in H and not re.search(r"<(script|link)[^>]+(src|href)=['\"]https?:", H)
      and all(f"id='{s}'" in H for s in ("health", "depts", "p0", "cross", "plan", "changes", "next", "limits")))
M = open(R1["paths"]["markdown"]).read()
check("markdown: every required section", all(s in M for s in ("## Executive summary", "## Overall health", "## Department scorecards", "## Critical issues and blockers",
                                                                "## Cross-department findings", "## Prioritized action plan", "## Changes since the previous report", "## Recommended next actions")))
arch = os.path.join(WS, "archive"); shutil.copytree(os.environ["GITCRAFT_REPORTS"], arch)
n = PR.publish_site(arch, os.path.join(WS, "site"))
saved = len([l for l in open(os.path.join(arch, "index.jsonl")) if l.strip()])
check("site: an index of projects and one page per saved report (none overwritten)", n == saved >= 4 and os.path.isfile(os.path.join(WS, "site", "index.html"))
      and len(glob.glob(os.path.join(WS, "site", "*", "*", "index.html"))) == saved, (n, saved))
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto("file://" + R1["paths"]["html"])
        ov = pg.evaluate("document.documentElement.scrollWidth - innerWidth"); b.close()
    check("html: no horizontal scroll at iPhone width (390 px)", ov <= 0, ov)
except ImportError:   # the Node Playwright (the Studio's and CI's browser)
    js = ("const {chromium}=require('playwright');(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:390,height:844}});"
          f"await p.goto('file://{R1['paths']['html']}');console.log(await p.evaluate(()=>document.documentElement.scrollWidth-innerWidth));await b.close()}})()")
    root = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True, env=dict(os.environ, NODE_PATH=root), timeout=120)
    if r.returncode == 0: check("html: no horizontal scroll at iPhone width (390 px)", int(r.stdout.strip()) <= 0, r.stdout)
    else: print("SKIP browser check (no Playwright here):", r.stderr[-200:])

shutil.rmtree(WS, ignore_errors=True)
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
