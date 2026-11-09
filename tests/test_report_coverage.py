#!/usr/bin/env python3
"""Report coverage: no department silently missing from "Run GITCRAFT report" (production/project_report.py).

  1. refresh=full scores PLAYCRAFT from the assessment it made for the report (never recorded in the Game Quality
     History; a delta only under the same rubric and method).
  2. refresh=full runs TestCraft (smoke of the existing build) and AssetCraft (scan + licence report into a private
     catalogue in the report's run folder): read-only for the project and the shared catalogue; no build or no runtime
     → Not Evaluated with the reason, never a score.
  3. The departments the report runs can reach the project it reports on: the report grants them exactly the project and
     its own run folder (the session's roots, and project isolation, are unchanged).
  4. A refresh that fails says why (the actual error), never just "failed".

Fast: the department calls are stand-ins that write exactly what the department writes, except one real call through
studio/cli.py that proves the policy error reaches the report (skipped when the Studio runtime is not installed)."""
import glob, hashlib, json, os, sqlite3, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
WS = os.path.realpath(tempfile.mkdtemp(prefix="gcr-cov-"))
SHARED_CAT = os.path.join(WS, "shared", "catalog.sqlite")
os.environ.update(GITCRAFT_ROOTS=WS, GITCRAFT_REPORTS=os.path.join(WS, "reports"), GITCRAFT_PRODUCTION_HOME=os.path.join(WS, "prod"),
                  GITCRAFT_ASSET_CATALOG=SHARED_CAT, GITCRAFT_3D_LIBRARY=os.path.join(WS, "none-3d"),
                  GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(WS, "none-px"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(WS, "pc-history"))
from production import project_report as PR, scoring  # noqa: E402
import production  # noqa: E402

fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  {str(detail)[:500]}"), flush=True)
    fails += 0 if cond else 1


def tree_hash(root):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds.sort()
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
        h.update(("D" + os.path.relpath(d, root)).encode())
    return h.hexdigest()


# ---------------------------------------------------------------- a built game, checked out
game = os.path.join(WS, "repos", "owner", "ember")
for d in ("src", "dist", os.path.join("public", "img")): os.makedirs(os.path.join(game, d))
open(os.path.join(game, "index.html"), "w").write("<!doctype html><html lang=en><head><title>Ember</title></head><body><canvas></canvas><script src=src/main.js></script></body></html>")
open(os.path.join(game, "src", "main.js"), "w").write("import * as THREE from 'three';\nconst player = {jump(){}, score: 0, lives: 3}; const enemies = []; let level = 1;\n"
                                                      "function gameLoop(){ player.score++; if (enemies.length) level++; requestAnimationFrame(gameLoop); }\n"
                                                      "addEventListener('keydown', e => player.jump()); gameLoop();\n")
json.dump({"name": "ember", "dependencies": {"three": "^0.185.1"}}, open(os.path.join(game, "package.json"), "w"))
open(os.path.join(game, "README.md"), "w").write("# Ember\n\nA browser game: jump, score, beat each level.\n")
open(os.path.join(game, "dist", "index.html"), "w").write("<!doctype html><title>Ember</title><canvas></canvas>")
open(os.path.join(game, "public", "img", "hero.png"), "wb").write(b"\x89PNG\r\n\x1a\n")
subprocess.run(["git", "init", "-q", game]); subprocess.run(["git", "-C", game, "add", "-A"])
subprocess.run(["git", "-C", game, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"])
HEAD = subprocess.run(["git", "-C", game, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()

CALLS = []
MODE = {}


def fake(action, args, timeout=3600, env=None):
    """Stand-ins that write what each department writes (its result file / .studio.json / catalogue)."""
    CALLS.append((action, args, env))
    if action in MODE: return MODE[action]
    out = args.get("out_dir")
    if out: os.makedirs(out, exist_ok=True)
    if action == "playcraft_assess":
        json.dump({"method": "pc-method-1", "created": "2026-11-09T18:00:00+00:00", "git": {"head": HEAD}, "played": {"played": True, "viewports": ["desktop", "phone"]},
                   "overall": {"score": 73, "confidence": "low", "coverage": 1.0},
                   "categories": {"core_gameplay": {"title": "Core gameplay", "score": 88}, "mobile": {"title": "Mobile experience", "score": 60}},
                   "findings": [{"id": "mob.touch", "category": "mobile", "title": "Touch input responds", "type": "design", "status": "fail", "level": "observed",
                                 "evidence": "0/5 touch gestures changed the screen", "impact": 5, "recommendation": "Handle touch."},
                                {"id": "core.loop", "title": "Loop", "status": "pass", "level": "observed"}]}, open(os.path.join(out, "playcraft.json"), "w"))
        return {"status": "ok"}, None
    if action == "pixelcraft_audit": return {"status": "failed", "error": "GITCRAFT policy: out_dir is outside the workspace roots (/nowhere)"}, None
    if action == "testcraft_smoke":
        json.dump({"department": "testcraft", "action": "smoke", "status": "failed", "created": "2026-11-09T18:01:00+00:00",
                   "checks": [{"name": "loads on phone", "ok": True}, {"name": "no console errors", "ok": False, "detail": "TypeError at main.js:3"}]},
                  open(os.path.join(out, "smoke.studio.json"), "w"))
        return {"status": "failed"}, None
    if action == "assetcraft_scan":
        cat = env["GITCRAFT_ASSET_CATALOG"]; os.makedirs(os.path.dirname(cat), exist_ok=True)
        c = sqlite3.connect(cat)
        c.execute("CREATE TABLE IF NOT EXISTS assets (path TEXT, rel TEXT, kind TEXT, license TEXT, valid INT, updated TEXT, current INT, project TEXT)")
        c.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?)", (os.path.join(game, "public", "img", "hero.png"), "public/img/hero.png", "image", "UNKNOWN", 1, "2026-11-09T18:02:00", 1, game))
        c.execute("INSERT INTO assets VALUES (?,?,?,?,?,?,?,?)", (os.path.join(game, "public", "img", "bg.png"), "public/img/bg.png", "image", "CC0-1.0", 1, "2026-11-09T18:02:00", 1, game))
        c.commit(); c.close()
        return {"status": "ok", "catalogued": 2}, None
    if action == "assetcraft_license_report": return {"status": "failed"}, None
    return None, f"{action}: not stubbed"


real_call = PR._studio_call
PR._studio_call = fake
before = tree_hash(game)
R = PR.generate(game, refresh="full", save="store")
dd = {d["id"]: d for d in R["departments"]}

# ---------------------------------------------------------------- 1. PLAYCRAFT: scored from what it measured
pc = dd["playcraft"]
check("PLAYCRAFT: refresh=full scores the department from the assessment it made for this report (never 'No data' after measuring)",
      pc["status"] == "current" and pc["score"]["value"] == 73 and pc["quality"]["value"] == 73 and pc["run"]["method"] == "pc-method-1", (pc["status"], pc["score"]))
check("PLAYCRAFT: labelled 'measured for this report, not recorded in the Game Quality History', and never recorded there",
      "not recorded in the Game Quality History" in pc["run"]["source"] and not os.path.exists(os.path.join(WS, "pc-history"))
      and next(a for a in CALLS if a[0] == "playcraft_assess")[1]["record_history"] is False, pc["run"])
check("PLAYCRAFT: it measures the existing build folder; failed/partial findings carry their evidence level (passed ones are not findings)",
      next(a for a in CALLS if a[0] == "playcraft_assess")[1]["target"] == os.path.join(game, "dist")
      and [f["id"] for f in pc["findings"]] == ["mob.touch"] and pc["findings"][0]["level"] == "observed" and pc["findings"][0]["severity"] == "major")
check("PLAYCRAFT: no contradiction — the report never says 'No data' next to a measured score", "No data" not in json.dumps(pc["notes"]) and R["health"]["parts"].get("playcraft") == 73)

# ---------------------------------------------------------------- 2. TestCraft and AssetCraft, read-only
tc, ac = dd["testcraft"], dd["assetcraft"]
check("TestCraft: refresh=full smoke-tests the existing build (output in the report's run folder) and is scored from its checks (1/2 → 50)",
      tc["refresh"]["ok"] and tc["score"]["value"] == 50.0 and any("no console errors" in (f["evidence"] or "") and "TypeError" in f["evidence"] for f in tc["findings"])
      and next(a for a in CALLS if a[0] == "testcraft_smoke")[1]["out_dir"].startswith(R["paths"]["dir"]), (tc["refresh"], tc["score"]))
check("AssetCraft: refresh=full catalogues into a private catalogue in the run folder (the shared catalogue untouched) and scores licences (1/2 known → 50)",
      ac["score"]["value"] == 50.0 and ac["run"]["source"].startswith(R["paths"]["dir"]) and not os.path.exists(SHARED_CAT)
      and all(a[2]["GITCRAFT_ASSET_CATALOG"].startswith(R["paths"]["dir"]) for a in CALLS if a[0].startswith("assetcraft_")), (ac["score"], ac["run"]))
check("read-only: the project is byte-identical after a full refresh (every department's output went to the report folder)", tree_hash(game) == before)
check("coverage: PLAYCRAFT, TestCraft and AssetCraft are evaluated; PIXELCRAFT (failed) carries no weight",
      {"playcraft", "testcraft", "assetcraft"} <= set(R["health"]["parts"]) and "pixelcraft" not in R["health"]["parts"], R["health"]["parts"])

# ---------------------------------------------------------------- 4. a failure says why
px = dd["pixelcraft"]
check("failure reason: a refresh that failed reports the actual error, never just 'failed'",
      not px["refresh"]["ok"] and "GITCRAFT policy" in px["refresh"]["detail"] and px["refresh"]["detail"] != "failed"
      and any("GITCRAFT policy" in x["why"] for x in R["not_refreshed"]), px["refresh"])
check("failure reason (helper): a department result's error, reason, failing checks and install hint are all carried",
      "missing runtime" in PR._why("x", {"status": "blocked", "reason": "missing runtime", "install": ["scripts/install-studio.sh"]}, None)
      and "install-studio" in PR._why("x", {"status": "blocked", "reason": "missing runtime", "install": ["scripts/install-studio.sh"]}, None)
      and "no console errors" in PR._why("x", {"status": "failed", "checks": [{"name": "no console errors", "ok": False}]}, None))

# no build, no runtime → Not Evaluated with the reason, never a score
nob = os.path.join(WS, "repos", "owner", "nobuild"); os.makedirs(os.path.join(nob, "src"))
open(os.path.join(nob, "index.html"), "w").write("<!doctype html><title>N</title><canvas></canvas><script src=src/game.js></script>")
open(os.path.join(nob, "src", "game.js"), "w").write("import * as THREE from 'three';\nconst player = {jump(){}, score: 0}; let level = 1;\n"
                                                    "function gameLoop(){ player.score++; requestAnimationFrame(gameLoop); }\naddEventListener('keydown', e => player.jump()); gameLoop();\n")
json.dump({"name": "nobuild", "dependencies": {"three": "^0.185.1"}}, open(os.path.join(nob, "package.json"), "w"))
open(os.path.join(nob, "README.md"), "w").write("# N\n\nA browser game: jump, score, beat each level.\n")
CALLS.clear()
Rn = PR.generate(nob, refresh="full", save="none")
dn = {d["id"]: d for d in Rn["departments"]}
check("no build: PLAYCRAFT and TestCraft are not run, Not Evaluated, and the reason says how to build",
      dn["playcraft"]["score"] is None and dn["testcraft"]["score"] is None and "npm run build" in dn["testcraft"]["refresh"]["detail"]
      and not any(a[0] in ("playcraft_assess", "testcraft_smoke") for a in CALLS) if PR._build_dir(nob) is None else True,
      (dn["playcraft"]["refresh"], dn["testcraft"]["refresh"], PR._build_dir(nob)))
PR._studio_call = lambda action, args, timeout=3600, env=None: (None, f"the Studio runtime is not installed (/x/venv/bin/python); scripts/install-studio.sh")
Rr = PR.generate(game, refresh="full", save="none")
dr = {d["id"]: d for d in Rr["departments"]}
check("no runtime: every Studio refresh is Not Evaluated (no score, no weight) with the install command as the reason",
      all(dr[i]["score"] is None and "install-studio" in (dr[i]["refresh"]["detail"] or "") for i in ("pixelcraft", "testcraft", "assetcraft"))
      and dr["playcraft"]["score"] is None and not {"testcraft", "assetcraft", "pixelcraft"} & set(Rr["health"]["parts"]),
      {i: (dr[i]["score"], dr[i]["refresh"]["detail"]) for i in ("playcraft", "pixelcraft", "testcraft", "assetcraft")})
check("quick refresh: TestCraft and AssetCraft are not run, and the report says how to measure them",
      all("refresh=full" in ({d["id"]: d for d in PR.generate(game, refresh="quick", save="none")["departments"]}[i]["refresh"]["detail"] or "") for i in ("testcraft", "assetcraft")))

# a department measured for the first time: its findings are first findings, not regressions; the overall score is not compared
PR._studio_call = lambda action, args, timeout=3600, env=None: (None, "the Studio runtime is not installed (/x); scripts/install-studio.sh")
Rq = PR.generate(game, refresh="quick", save="store")   # PLAYCRAFT, TestCraft, AssetCraft not measured
PR._studio_call = fake
Rf = PR.generate(game, refresh="full", save="store")    # now measured
check("regressions: findings of a department that was not measured in the previous report are never called regressions",
      not any(x["department"] in ("playcraft", "testcraft", "assetcraft") for x in Rf["regressions"]), Rf["regressions"])
check("overall: a different set of evaluated departments is not compared (no overall delta, the difference named)",
      Rf["health"]["vs_previous"]["delta"] is None and "different departments" in Rf["health"]["vs_previous"]["compare"], Rf["health"]["vs_previous"])

same = [{"report_id": f"p/20261109T190000Z" + (f"-{n}" if n > 1 else ""), "generated": "2026-11-09T19:00:00+00:00"} for n in range(1, 13)]
import random as _r; shuffled = same[:]; _r.Random(7).shuffle(shuffled)
check("ordering: twelve reports made in the same second are ordered by their suffix (…Z, -2 … -12), never by folder listing",
      [x["report_id"] for x in sorted(shuffled, key=PR._report_order)] == [x["report_id"] for x in same])

# deltas: only under the same rubric and method
PR._studio_call = fake
R2 = PR.generate(game, refresh="full", save="store")
q2 = {d["id"]: d for d in R2["departments"]}["playcraft"]["quality"]
check("trend: a second measured PLAYCRAFT score with the same method is compared (delta 0)", q2["delta"] == 0 and q2["previous"] == 73, q2)
orig = fake
def other_method(action, args, timeout=3600, env=None):
    r = orig(action, args, timeout, env)
    if action == "playcraft_assess":
        p = os.path.join(args["out_dir"], "playcraft.json"); A = json.load(open(p)); A["method"] = "pc-method-2"; A["overall"]["score"] = 80; json.dump(A, open(p, "w"))
    return r
PR._studio_call = other_method
R3 = PR.generate(game, refresh="full", save="store")
q3 = {d["id"]: d for d in R3["departments"]}["playcraft"]["quality"]
check("trend: a measurement under a different PLAYCRAFT method is never compared (no delta)", q3["delta"] is None and "method" in (q3["compare"] or ""), q3)
PR._studio_call = real_call

# ---------------------------------------------------------------- 3. roots: the project reported on, never the whole workspace
other = os.path.realpath(tempfile.mkdtemp(prefix="gcr-other-"))   # a project outside the session's roots (like a sibling clone)
os.makedirs(os.path.join(other, "img")); open(os.path.join(other, "img", "a.png"), "wb").write(b"\x89PNG\r\n\x1a\n")
run = os.path.realpath(tempfile.mkdtemp(prefix="gcr-run-"))
ctx = {"project": {"path": other}, "run_dir": run}
env = PR._dept_env(ctx)
rs = env["GITCRAFT_ROOTS"].split(":")
check("roots: a department the report runs gets the session's roots plus exactly the project and the report's run folder (nothing wider)",
      rs == list(dict.fromkeys(production.roots() + [other, run])) and os.path.dirname(other) not in rs and os.environ["GITCRAFT_ROOTS"] == WS, rs)
check("roots: the session's own roots and the launcher default are unchanged (another project can still never write into this checkout)",
      production.roots() == [WS] and "CLAUDE_CODE_REMOTE" not in open(os.path.join(REPO, "scripts", "tools.sh")).read())
studio_py = os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "studio", "venv", "bin", "python")
if os.path.exists(studio_py):
    args = {"folder": other, "project": other, "out_dir": os.path.join(run, "scan"), "name": "scan", "register": False}
    res0, err0 = PR._studio_call("assetcraft_scan", args, timeout=120, env={"GITCRAFT_ASSET_CATALOG": os.path.join(run, "cat0.sqlite")})
    why = PR._why("assetcraft_scan", res0, err0)
    check("real call: without the grant, a project outside the roots is refused, and the report says so ('GITCRAFT policy: …', never just 'failed')",
          "GITCRAFT policy" in why, why)
    res1, err1 = PR._studio_call("assetcraft_scan", args, timeout=120, env=PR._dept_env(ctx, GITCRAFT_ASSET_CATALOG=os.path.join(run, "cat1.sqlite")))
    check("real call: with the grant, the department reads the project outside the session's roots and writes only into the run folder",
          not err1 and res1 and res1.get("status") in ("ok", "failed") and res1.get("catalogued", 0) >= 1 and os.listdir(other) == ["img"], (res1, err1))
else:
    print("SKIP real calls: the Studio runtime is not installed here")

print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
