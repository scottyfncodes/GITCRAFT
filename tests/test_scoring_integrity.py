#!/usr/bin/env python3
"""Scoring integrity: an evaluator that fails can never produce, lower or shape an overall score.

The defect this guards against (reproduced before the fix on a real game): the same build scored 71.8 with every
evaluator working and "57.1 (at full weight 42.9)" when the browser the evaluators share could not start, with the
broken evaluators listed as "No data" and a DESIGNCRAFT 0 (0 % of its rubric tested) averaged in as if measured.

  1. The state machine (production/scoring.py: validity): VALID only when every mandatory evaluator measured the
     current build and none failed; PARTIAL for incomplete coverage; INVALID when a mandatory evaluator failed.
     Only VALID has an overall score.
  2. Missing evidence is never a number: a rubric tested under MIN_COVERAGE, a gameplay score made without playing,
     and DESIGNCRAFT's untested criteria are "too little evidence", not low scores.
  3. Attribution: an evaluator failure is the evaluator's (status, reason, plan item); it leaves no finding, P0 or P1
     against the project. A project defect is still found and scored when the evaluators work.
  4. Determinism and recovery: the same inputs give the same report; once the evaluator works again the report is
     VALID again with the same score as before the failure.
  5. Gates: `project-report --require-valid` exits non-zero unless VALID; `production evaluators` exits non-zero when a
     dependency is broken.

Fast (the department calls are stand-ins that write what each department writes). The same behaviour with the real
evaluators, through the real launcher, is tests/certify_report.py."""
import json, os, re, sqlite3, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
WS = os.path.realpath(tempfile.mkdtemp(prefix="gcr-integrity-"))
os.environ.update(GITCRAFT_ROOTS=WS, GITCRAFT_REPORTS=os.path.join(WS, "reports"), GITCRAFT_PRODUCTION_HOME=os.path.join(WS, "prod"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(WS, "shared", "catalog.sqlite"), GITCRAFT_3D_LIBRARY=os.path.join(WS, "none-3d"),
                  GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(WS, "none-px"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(WS, "pc-history"))
from production import project_report as PR, scoring as SC, evalhealth as EH  # noqa: E402

fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  {str(detail)[:700]}"), flush=True)
    fails += 0 if cond else 1


# ---------------------------------------------------------------- 1. the state machine, on its own
def dept(i, value=None, status="current", conf="high", coverage=None, outcome=None, failure=None, played=None, applicable=True):
    sc = None if value is None and coverage is None else {"value": value, "confidence": conf, "coverage": coverage}
    if sc is not None and played is not None: sc["played"] = played
    D = {"id": i, "title": i.upper() + " — test", "status": status, "score": sc, "notes": [], "findings": [], "applicable": applicable, "next": None, "run": None}
    if i == "production": D["standard"] = {"passed": 9, "of": 10, "checks": ["ok"] * 9 + ["failed"]} if value is not None else None; D["score"] = None
    if outcome: D["outcome"] = outcome
    if failure: D["evaluator_failure"] = failure
    return SC.evaluate(D)


def state(ds, kind="game"):
    E = SC.validity(ds, kind); H = SC.overall(ds, evaluation=E)
    return E, H


good = lambda: [dept("production", 90), dept("playcraft", 80, coverage=1.0, played=True), dept("pixelcraft", 70, coverage=0.8), dept("testcraft", 100)]
E, H = state(good())
check("1 · VALID: every mandatory evaluator measured the current build → an overall score, with its state",
      E["state"] == "VALID" and E["score_shown"] and H["score"] is not None and H["state"] == "VALID" and not E["evaluator_failures"], (E, H))
ds = good(); ds[1] = dept("playcraft", status="evaluator_failed", outcome="evaluator_failed", failure="browserType.launch: Failed to launch")
E, H = state(ds)
check("1 · INVALID: a mandatory evaluator failed → NO overall score, the cause named, the other measured scores kept apart",
      E["state"] == "INVALID" and H["score"] is None and "No overall score" in H["headline"] and H["confidence"] == "none"
      and E["evaluator_failures"] == [{"id": "playcraft", "title": "PLAYCRAFT", "mandatory": True, "why": "browserType.launch: Failed to launch"}]
      and set(H["parts"]) == {"production", "pixelcraft", "testcraft"} and any("failure of the evaluator, not a finding about the project" in r for r in E["reasons"]), (E, H))
ds = good(); ds[2] = dept("pixelcraft", status="no_data")
E, H = state(ds)
check("1 · PARTIAL: a mandatory evaluator did not run → NO overall score; the measured departments stand on their own",
      E["state"] == "PARTIAL" and H["score"] is None and set(H["parts"]) == {"production", "playcraft", "testcraft"} and any("PIXELCRAFT (mandatory): not run" in r for r in E["reasons"]), (E, H))
ds = good(); ds[1] = dept("playcraft", 80, status="stale", coverage=1.0, played=True)
E, H = state(ds)
check("1 · PARTIAL: a mandatory score measured on an older build does not describe this build → no overall score", E["state"] == "PARTIAL" and H["score"] is None, E)
ds = good(); ds[3] = dept("testcraft", status="no_data", outcome="prerequisite_missing")
check("1 · PARTIAL: nothing to measure yet (no build) is neither a failure nor a score", state(ds)[0]["state"] == "PARTIAL" and not state(ds)[0]["evaluator_failures"], state(ds)[0])
ds = good() + [dept("designcraft", status="no_data"), dept("assetcraft", status="no_data")]
E, H = state(ds)
check("1 · VALID with optional departments not run: they carry no weight, are listed, and never count as 0",
      E["state"] == "VALID" and H["score"] == state(good())[1]["score"] and "designcraft" not in H["parts"] and H["coverage"] < 1, (E["state"], H))
ds = good() + [dept("assetcraft", status="evaluator_failed", outcome="evaluator_failed", failure="assetcraft_scan timed out")]
E, H = state(ds)
check("1 · an optional evaluator that failed is still said, and withholds the overall score (PARTIAL, never silently dropped)",
      E["state"] == "PARTIAL" and H["score"] is None and E["evaluator_failures"][0]["id"] == "assetcraft", E)
ds = good(); ds[1] = dept("playcraft", 80, coverage=1.0, played=True, failure="playcraft_assess timed out after 3600 s")
E, H = state(ds)
check("1 · a re-measurement that failed while an earlier measurement stands: PARTIAL, the failure said, no overall score",
      E["state"] == "PARTIAL" and H["score"] is None and any("could not be re-measured" in r for r in E["reasons"]), E)
E, H = state([dept("production", status="unavailable"), dept("playcraft", status="evaluator_failed", outcome="evaluator_failed", failure="x")])
check("1 · nothing measured at all → INVALID, no score", E["state"] == "INVALID" and H["score"] is None, (E, H))
check("1 · a project that is not checked out can never be VALID (no result can be tied to its current build)",
      SC.validity(good(), None, checked_out=False)["state"] == "PARTIAL")
check("1 · an app does not need PLAYCRAFT; a tool needs only the engineering standard",
      SC.validity([d for d in good() if d["id"] != "playcraft"], "app")["state"] == "VALID" and SC.validity([dept("production", 90)], "tool")["state"] == "VALID")

# ---------------------------------------------------------------- 2. missing evidence is never a number
thin = dept("designcraft", 0, conf="low", coverage=0.0)
check("2 · a rubric with 0% tested is 'too little evidence': Not Evaluated, no value, the reason said (never a 0 in the average)",
      thin["quality"]["evaluation"] == "not_evaluated" and thin["quality"]["value"] is None and thin["quality"]["reason"] == "insufficient_evidence"
      and "0% of its rubric" in thin["quality"]["why"], thin["quality"])
check("2 · the coverage floor is a floor: 49% is too little, 50% is scored",
      dept("pixelcraft", 80, coverage=0.49)["quality"]["evaluation"] == "not_evaluated" and dept("pixelcraft", 80, coverage=0.5)["quality"]["value"] == 80)
unplayed = dept("playcraft", 66, coverage=1.0, played=False)
check("2 · a gameplay score made without playing the build is not a gameplay measurement (Not Evaluated, so a game report cannot be VALID on it)",
      unplayed["quality"]["evaluation"] == "not_evaluated" and "not played" in unplayed["quality"]["why"]
      and SC.validity([dept("production", 90), unplayed, dept("pixelcraft", 70, coverage=0.8), dept("testcraft", 100)], "game")["state"] == "PARTIAL", unplayed["quality"])
E, H = state(good() + [thin])
check("2 · that 0 changes nothing: the overall score with the thin department equals the score without it", H["score"] == state(good())[1]["score"] and "designcraft" not in H["parts"], H)
lo = [dept("production", 90), dept("playcraft", 80, conf="low", coverage=1.0, played=True), dept("pixelcraft", 70, conf="low", coverage=0.8), dept("testcraft", 100)]
check("2 · mostly low-confidence department results cannot add up to a high-confidence overall score", state(lo)[1]["confidence"] != "high" and state(good())[1]["confidence"] == "high", state(lo)[1])

# ---------------------------------------------------------------- 3. the report: attribution, with stand-in departments
game = os.path.join(WS, "repos", "owner", "ember")
for d in ("src", "dist", "public/img"): os.makedirs(os.path.join(game, d))
open(os.path.join(game, "index.html"), "w").write("<!doctype html><html lang=en><head><meta name=viewport content='width=device-width'><title>Ember</title></head><body><canvas id=c></canvas><script type=module src=src/main.js></script></body></html>")
open(os.path.join(game, "src", "main.js"), "w").write("const player = {jump(){}, score: 0, lives: 3}; const enemies = []; let level = 1;\nfunction gameLoop(){ player.score++; requestAnimationFrame(gameLoop); }\naddEventListener('keydown', e => player.jump()); gameLoop();\n")
json.dump({"name": "ember", "scripts": {"build": "vite build"}, "dependencies": {"three": "^0.185.1"}}, open(os.path.join(game, "package.json"), "w"))
open(os.path.join(game, "README.md"), "w").write("# Ember\n\nA browser game: jump, score, beat each level.\n")
open(os.path.join(game, "dist", "index.html"), "w").write("<!doctype html><title>Ember</title><canvas></canvas>")
subprocess.run(["git", "init", "-q", game]); subprocess.run(["git", "-C", game, "add", "-A"])
subprocess.run(["git", "-C", game, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"])
HEAD = subprocess.run(["git", "-C", game, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
MODE = {}


def fake(action, args, timeout=3600, env=None):
    """What each department writes when it works; MODE[action] replaces one with a failure."""
    if action in MODE: return MODE[action]
    out = args.get("out_dir")
    if out: os.makedirs(out, exist_ok=True)
    if action == "playcraft_assess":
        json.dump({"method": "pc-1", "created": "2026-11-09T18:00:00+00:00", "git": {"head": HEAD}, "played": {"played": True, "viewports": ["desktop", "phone"]},
                   "overall": {"score": 73, "confidence": "high", "coverage": 1.0}, "categories": {"core_gameplay": {"title": "Core gameplay", "score": 88}},
                   "findings": [{"id": "mob.touch", "category": "mobile", "title": "Touch input responds", "type": "design", "status": "fail", "level": "observed", "evidence": "0/5", "impact": 5, "recommendation": "Handle touch."}]},
                  open(os.path.join(out, "playcraft.json"), "w"))
        return {"status": "ok"}, None
    if action == "pixelcraft_audit":
        json.dump({"method": "px-1", "created": "2026-11-09T18:00:30+00:00", "app": {"name": "ember", "git": {"head": HEAD}}, "overall": {"score": 84.0, "confidence": "high", "coverage": 0.8},
                   "categories": {"visual": {"score": 84}}, "findings": []}, open(os.path.join(out, "audit.json"), "w"))
        return {"status": "ok"}, None
    if action == "testcraft_smoke":
        json.dump({"department": "testcraft", "action": "smoke", "status": "ok", "created": "2026-11-09T18:01:00+00:00",
                   "checks": [{"name": "loads on phone", "ok": True}, {"name": "no console errors", "ok": True}]}, open(os.path.join(out, "smoke.studio.json"), "w"))
        return {"status": "ok"}, None
    if action == "assetcraft_scan":
        cat = env["GITCRAFT_ASSET_CATALOG"]; os.makedirs(os.path.dirname(cat), exist_ok=True); sqlite3.connect(cat).close()
        return {"status": "failed", "catalogued": 0, "error": "failed checks: assets catalogued"}, None   # what the real scan returns for a project with no asset files
    return None, f"{action}: not stubbed"


PR._studio_call = fake
EH.check = lambda timeout=90: {"ok": True, "checks": []}   # the dependency probe is exercised for real in part 5 and in tests/certify_report.py


def run(**kw):
    R = PR.generate(game, refresh="full", save="store", **kw)
    return R, {d["id"]: d for d in R["departments"]}, open(R["paths"]["markdown"]).read(), open(R["paths"]["html"]).read()


R0, D0, M0, H0 = run()
check("3 · healthy: every mandatory evaluator measured → VALID with an overall score, and the report says VALID where the score is",
      R0["evaluation"]["state"] == "VALID" and R0["health"]["score"] is not None and R0["summary"][0].startswith("Evaluation **VALID**") and "Evaluation VALID" in H0
      and "**VALID**" in M0, (R0["evaluation"], R0["health"]))
check("3 · DESIGNCRAFT read no design data from this game (under half its rubric): Not Evaluated with the reason, never a 0 in the score",
      D0["designcraft"]["quality"]["evaluation"] == "not_evaluated" and D0["designcraft"]["quality"]["reason"] == "insufficient_evidence" and "designcraft" not in R0["health"]["parts"],
      D0["designcraft"]["quality"])
check("3 · a project with no asset files: asset licensing does not apply (the scan's empty result is not a failure, not 'No data', not an evaluator failure)",
      D0["assetcraft"]["status"] == "not_applicable" and D0["assetcraft"]["quality"]["evaluation"] == "not_applicable" and not D0["assetcraft"].get("evaluator_failure")
      and not any("AssetCraft" in a["title"] for a in R0["actions"]), (D0["assetcraft"]["status"], D0["assetcraft"]["refresh"]))

# the browser evaluators break (what a Chromium that cannot start returns through studio/cli.py)
BROKEN = (None, "playcraft_assess failed: browser (playprobe.mjs): browserType.launch: Failed to launch: Error: spawn /opt/pw-browsers/chromium EACCES\nBrowser logs:\n<launching> …")
MODE.update(playcraft_assess=BROKEN, pixelcraft_audit=(None, BROKEN[1].replace("playcraft_assess", "pixelcraft_audit")), testcraft_smoke=(None, BROKEN[1].replace("playcraft_assess", "testcraft_smoke")))
R1, D1, M1, H1 = run()
broken = ("playcraft", "pixelcraft", "testcraft")
check("3 · broken evaluators: INVALID, and NO overall number anywhere (health, summary, Markdown table, HTML hero)",
      R1["evaluation"]["state"] == "INVALID" and R1["health"]["score"] is None and not any(re.search(r"\d\s*/\s*100", s) for s in R1["summary"])
      and "| **No overall score (INVALID evaluation)** |" in M1 and "<b>No score</b>" in H1 and "Evaluation INVALID" in H1, (R1["health"], R1["summary"][:2]))
check("3 · attribution: each broken department is 'Evaluator failed' with its actual error (one line, not the browser's launch log), never 'No data'",
      all(D1[i]["status"] == "evaluator_failed" and "Failed to launch" in D1[i]["evaluator_failure"] and "Browser logs" not in D1[i]["evaluator_failure"]
          and D1[i]["quality"]["reason"] == "evaluator_failed" and D1[i]["quality"]["value"] is None for i in broken)
      and "No data: " not in json.dumps([a["title"] for a in R1["actions"]]), {i: (D1[i]["status"], D1[i].get("evaluator_failure")) for i in broken})
check("3 · attribution: an evaluator failure leaves no finding, no P0 and no P1 against the project; it is planned as an evaluator repair",
      all(not D1[i]["findings"] for i in broken) and not any(set(a["departments"]) & set(broken) and a["priority"] in ("P0", "P1") for a in R1["actions"])
      and sum(1 for a in R1["actions"] if a["title"].startswith("Evaluator failed (not a project defect)")) == 3 and not R1["blockers"] and R1["health"]["band"] != "at risk",
      [(a["priority"], a["title"]) for a in R1["actions"]])
check("3 · what did measure is kept: the engineering standard keeps its own score and findings, listed apart and not called an overall score",
      R1["health"]["parts"] == {"production": D0["production"]["quality"]["value"]} and D1["production"]["quality"]["value"] == D0["production"]["quality"]["value"], R1["health"]["parts"])
check("3 · the tool's summary (what an agent reads back) carries the state and has no score to quote",
      __import__("production.entry", fromlist=["x"]).summary(R1)["evaluation"]["state"] == "INVALID" and __import__("production.entry", fromlist=["x"]).summary(R1)["health"]["score"] is None)
idx = [json.loads(l) for l in open(os.path.join(os.environ["GITCRAFT_REPORTS"], "index.jsonl"))]
check("3 · the report index records the state and no health number for an INVALID report", idx[-1]["evaluation"] == "INVALID" and idx[-1]["health"] is None and idx[-2]["evaluation"] == "VALID", idx[-1])
check("3 · no change is claimed between a VALID and an INVALID report (the failure is never a regression of the project)",
      R1["health"]["vs_previous"]["delta"] is None and not [x for x in R1["regressions"] if x["department"] in broken], (R1["health"]["vs_previous"], R1["regressions"]))

# one mandatory evaluator broken, the others fine
MODE.clear(); MODE["pixelcraft_audit"] = ({"status": "failed", "error": "probe crashed: Target closed"}, None)
R2, D2, M2, _ = run()
check("3 · one mandatory evaluator fails: INVALID, no overall score; PLAYCRAFT's and TestCraft's own results and findings are preserved",
      R2["evaluation"]["state"] == "INVALID" and R2["health"]["score"] is None and R2["health"]["parts"].get("playcraft") == 73 and R2["health"]["parts"].get("testcraft") == 100.0
      and any(f["id"] == "mob.touch" for f in D2["playcraft"]["findings"]) and [x["id"] for x in R2["evaluation"]["evaluator_failures"]] == ["pixelcraft"], (R2["evaluation"], R2["health"]["parts"]))

# a smoke test that stopped on its own error and checked nothing
def smoke_error(action, args, timeout=3600, env=None):
    os.makedirs(args["out_dir"], exist_ok=True)
    json.dump({"department": "testcraft", "action": "smoke", "status": "failed", "created": "2026-11-09T18:01:00+00:00", "checks": [], "error": "browser (testcraft.mjs): page.goto: Timeout 30000ms exceeded"},
              open(os.path.join(args["out_dir"], "smoke.studio.json"), "w"))
    return {"status": "failed", "error": "browser (testcraft.mjs): page.goto: Timeout 30000ms exceeded"}, None
MODE.clear(); real_fake = fake
PR._studio_call = lambda action, args, timeout=3600, env=None: smoke_error(action, args) if action == "testcraft_smoke" else real_fake(action, args, timeout, env)
R3, D3, _, _ = run()
check("3 · a smoke test that stopped on its own error measured nothing: an evaluator failure, no QA score, no finding against the project",
      D3["testcraft"]["status"] == "evaluator_failed" and D3["testcraft"]["quality"]["value"] is None and "Timeout" in D3["testcraft"]["evaluator_failure"]
      and R3["evaluation"]["state"] == "INVALID" and not [f for f in D3["testcraft"]["findings"] if f["severity"] in ("critical", "major")], (D3["testcraft"]["status"], D3["testcraft"]["findings"]))

# a real project defect, with every evaluator working
def defect(action, args, timeout=3600, env=None):
    if action != "testcraft_smoke": return real_fake(action, args, timeout, env)
    os.makedirs(args["out_dir"], exist_ok=True)
    json.dump({"department": "testcraft", "action": "smoke", "status": "failed", "created": "2026-11-09T18:01:00+00:00",
               "checks": [{"name": "loads on phone", "ok": True}, {"name": "no console errors", "ok": False, "detail": "TypeError: cfg is undefined at main.js:1"}]}, open(os.path.join(args["out_dir"], "smoke.studio.json"), "w"))
    return {"status": "failed"}, None
PR._studio_call = defect
R4, D4, _, _ = run()
check("3 · a project defect with working evaluators: VALID, a LOWER overall score than the healthy build, and a measured finding against the project",
      R4["evaluation"]["state"] == "VALID" and R4["health"]["score"] < R0["health"]["score"] and D4["testcraft"]["quality"]["value"] == 50.0 and not R4["evaluation"]["evaluator_failures"]
      and any(f["level"] == "verified" and f["severity"] == "major" and "TypeError" in (f.get("measured") or "") for f in D4["testcraft"]["findings"]), (R4["health"], D4["testcraft"]["findings"]))

# ---------------------------------------------------------------- 4. determinism and recovery
PR._studio_call = fake; MODE.clear()
R5, D5, _, _ = run()
R6, D6, _, _ = run()
sig = lambda R: (R["evaluation"]["state"], R["health"]["score"], R["health"]["parts"], sorted(f["key"] for d in R["departments"] for f in d["findings"]), [(a["priority"], a["title"]) for a in R["actions"]])
check("4 · recovery: once the evaluators work again the report is VALID again, with exactly the score it had before the failures", sig(R5) == sig(R0), (sig(R5)[:3], sig(R0)[:3]))
check("4 · repeat: the same inputs give the same state, score, department scores, findings and plan", sig(R6) == sig(R5))
check("4 · deltas are only ever between two VALID reports: R5 against the defect build's VALID report, R6 against R5 (0); the report after an INVALID one claims none",
      R6["health"]["vs_previous"]["delta"] == 0 and R5["health"]["vs_previous"]["delta"] == round(R5["health"]["score"] - R4["health"]["score"], 1)
      and R2["health"]["vs_previous"]["delta"] is None and R4["health"]["vs_previous"]["delta"] is None, (R4["health"]["vs_previous"], R5["health"]["vs_previous"], R6["health"]["vs_previous"]))

# ---------------------------------------------------------------- 5. gates (the real CLI, with the Studio runtime made unavailable)
env = dict(os.environ, GITCRAFT_STUDIO_HOME=os.path.join(WS, "no-studio"))
r = subprocess.run([sys.executable, "-m", "production", "evaluators", "--json"], cwd=REPO, env=env, capture_output=True, text=True)
check("5 · `production evaluators` exits 1 and names the missing runtime when the evaluators cannot run",
      r.returncode == 1 and json.loads(r.stdout)["ok"] is False and "install-studio" in json.loads(r.stdout)["checks"][0]["detail"], (r.returncode, r.stdout[:300], r.stderr[-300:]))
r = subprocess.run([sys.executable, "-m", "production", "project-report", game, "--refresh", "full", "--json", "--require-valid", "--out", os.path.join(WS, "gate")], cwd=REPO, env=env, capture_output=True, text=True)
try: G = json.loads(r.stdout)
except ValueError: G = {}
check("5 · `project-report --require-valid` exits 3 for an INVALID evaluation (real run, runtime unavailable): no score, every Studio evaluator named with the install command",
      r.returncode == 3 and G.get("evaluation", {}).get("state") == "INVALID" and G["health"]["score"] is None
      and {x["id"] for x in G["evaluation"]["evaluator_failures"]} >= {"playcraft", "pixelcraft", "testcraft"} and all("install-studio" in x["why"] for x in G["evaluation"]["evaluator_failures"])
      and G["evaluation"]["dependencies"]["ok"] is False, (r.returncode, r.stderr[-400:]))
r = subprocess.run([sys.executable, "-m", "production", "project-report", game, "--refresh", "quick", "--json", "--require-valid", "--out", os.path.join(WS, "gate2")], cwd=REPO, env=env, capture_output=True, text=True)
check("5 · `--require-valid` also refuses a report that is not VALID for any other reason (exit 3)", r.returncode == 3 and json.loads(r.stdout)["evaluation"]["state"] in ("PARTIAL", "INVALID"), r.returncode)

print("ALL PASSED" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
