#!/usr/bin/env python3
"""Evaluation orchestration regressions (WAR-BALLOON PR #11): four failure modes, each proven fixed.

  1. self-triggering loops   evaluation output (gitcraft-out/, marked folders, the production store) is never a
                             source change, so writing it cannot start another evaluation round; a project whose
                             source really keeps changing stops after a bounded number of re-measures (INCOMPLETE)
  2. one test target         smoke, features, PLAYCRAFT, PIXELCRAFT, performance and the final regression all measure
                             the same folder, picked by an explicit source-vs-build policy; a missing build is a
                             reasoned blocked state, never a silent test of the unbuilt source
  3. isolated artifacts      the production store is never inside the evaluated game, so DESIGNCRAFT (which refuses
                             output inside a game) runs, and the game folder is left exactly as it was
  4. a final verdict         every run ends READY, NOT READY or INCOMPLETE, with reasons when it is not READY

Departments are replaced by recording fakes (no browser needed); DESIGNCRAFT is the real one.

    python3 tests/test_evaluation.py        (~20 s)"""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-eval-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_PRODUCTION_ISOLATED=os.path.join(ws, "isolated-home"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"))
os.environ.pop("GITCRAFT_PRODUCTION_HOME", None)
import production
from production import engine, entry, executors, planner, intake, report, store, artifacts
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def game(name, built=True, static=False):
    """A small existing game. Vite-shaped (source index.html loads /src/main.ts; dist/ is the build) unless static."""
    g = os.path.join(ws, name); os.makedirs(os.path.join(g, "src"))
    shutil.copytree(os.path.join(HERE, "fixtures", "designcraft", "patrol_ts", "src"), os.path.join(g, "src"), dirs_exist_ok=True)
    open(os.path.join(g, "README.md"), "w").write("# Sky Patrol\n\nA small arcade game: the player dodges enemy drones, collects stars for score, "
                                                   "and clears each level. Three lives; the high score is kept.\n")
    main = ("// the game: player, enemies, score, level, lives\nconst c=document.querySelector('canvas');const x=c.getContext('2d');let score=0,lives=3,level=1;"
            "function f(){x.fillRect(0,0,9,9);requestAnimationFrame(f)};f();\n")
    page = lambda src, mod: ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                             f'<title>Sky Patrol</title></head><body><canvas></canvas><script{" type=module" if mod else ""} src="{src}"></script></body></html>\n')
    if static:
        open(os.path.join(g, "index.html"), "w").write(page("main.js", False))
        open(os.path.join(g, "main.js"), "w").write(main)
        return g
    json.dump({"name": name, "scripts": {"build": "vite build", "dev": "vite"}, "devDependencies": {"vite": "^5.4.0"}}, open(os.path.join(g, "package.json"), "w"))
    json.dump({"name": name, "lockfileVersion": 3, "packages": {}}, open(os.path.join(g, "package-lock.json"), "w"))
    open(os.path.join(g, "index.html"), "w").write(page("/src/main.ts", True))
    open(os.path.join(g, "src", "main.ts"), "w").write(main)
    if built:
        os.makedirs(os.path.join(g, "dist", "assets"))
        open(os.path.join(g, "dist", "index.html"), "w").write(page("assets/index.js", False))
        open(os.path.join(g, "dist", "assets", "index.js"), "w").write(main)
    return g


def tree(p):
    return {os.path.relpath(os.path.join(d, f), p): os.path.getmtime(os.path.join(d, f)) for d, _, fs in os.walk(p) for f in fs}


# ---- recording fakes for the departments that open a browser
CALLS = []
BEHAVIOUR = {"write_into_project": None, "smoke_fails": False}
real_designcraft = executors.designcraft_assess


def fake_studio(dept, action, params, timeout=1800):
    CALLS.append({"dept": dept, "action": action, "target": params.get("target"), "project": params.get("project")})
    out = params.get("out_dir") or os.path.join(ws, "loose"); os.makedirs(out, exist_ok=True)
    rep = os.path.join(out, f"{params.get('name') or action}.json"); json.dump({"dept": dept, "action": action}, open(rep, "w"))
    proj = params.get("project") or (os.path.dirname(params["target"]) if params.get("target", "").endswith("dist") else params.get("target"))
    w = BEHAVIOUR["write_into_project"]
    if w and proj:   # what departments do when called directly: reports in <repo>/gitcraft-out (or, for the control, in source)
        p = os.path.join(proj, w.format(n=len(CALLS))); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(str(len(CALLS)))
    ok = not (BEHAVIOUR["smoke_fails"] and action == "smoke")
    return {"status": "ok" if ok else "failed", "out_dir": out, "outputs": [{"path": rep, "role": "report", "format": "json"}],
            "summary": {"overall": {"score": 90}}, "checks": [{"name": f"{dept}.{action} measured", "ok": ok, "detail": None if ok else "console error"}]}


def fake_designcraft(project, out_json, timeout=900):
    CALLS.append({"dept": "designcraft", "action": "assess", "target": None, "project": project})
    json.dump({"score": {"overall": 70}}, open(out_json, "w"))
    return {"status": "ok", "outputs": [{"path": out_json, "role": "assessment", "format": "json", "ok": True}], "checks": [{"name": "read the game", "ok": True}]}


executors.studio_run = fake_studio
executors.designcraft_assess = fake_designcraft   # sections 1, 2 and 4; section 3 runs the real DESIGNCRAFT


def review(g, store_dir=None, overrides=None, max_seconds=120):
    CALLS.clear()
    r = entry.start("Run GITCRAFT: review this game", g, store_dir=store_dir, overrides=overrides)
    pid = r["production"]
    engine.decide(pid, approve=True, store_dir=store_dir)
    st = engine.run(pid, max_seconds=max_seconds, store_dir=store_dir)
    return st, store.load(pid, store_dir)


VERDICTS = {"READY", "NOT READY", "INCOMPLETE"}

# =============================================================== 1. no self-triggering evaluation loop
g1 = game("loop-game")
f0 = engine.fingerprint(g1)
os.makedirs(os.path.join(g1, "gitcraft-out", "playcraft")); open(os.path.join(g1, "gitcraft-out", "playcraft", "pass.json"), "w").write("{}")
check("change detection: a report in <game>/gitcraft-out/ is not a source change", engine.fingerprint(g1) == f0)
artifacts.mark(os.path.join(g1, "qa-results")); open(os.path.join(g1, "qa-results", "r.json"), "w").write("{}")
check("change detection: any folder marked .gitcraft-artifacts is skipped (a general mechanism, not a path list)", engine.fingerprint(g1) == f0)
open(os.path.join(g1, "src", "main.ts"), "a").write("// edit\n")
check("change detection: a real source edit still changes the fingerprint", engine.fingerprint(g1) != f0)

# a production whose store sits inside the game (the old default when the game is the only root) and departments that
# also drop reports into <game>/gitcraft-out on every call: every write is evaluation output, so nothing re-runs
inner = os.path.join(g1, "eval-store")   # an ordinary name: excluded only because store.create marks it
BEHAVIOUR.update(write_into_project="gitcraft-out/run-{n}.json", smoke_fails=False)
st, pr = review(g1, store_dir=inner)
ev = store.events(pr)
check("loop: writing evaluation output does not start another evaluation cycle (no stale re-measure)",
      not [e for e in ev if e["event"] in ("stale_evidence", "evaluation_unstable")], [e for e in ev if "stale" in e["event"]])
check("loop: every check ran exactly once and the run terminated", all(len(t["attempts"]) == 1 for t in pr["tasks"].values()) and st["status"] == "passed",
      ({k: len(t["attempts"]) for k, t in pr["tasks"].items()}, st["status"]))
check("loop: ...and the release gate accepted the evidence as measured on the released build",
      pr["tasks"]["release.report"]["state"] == "passed" and st["verdict"] in VERDICTS, pr["tasks"]["release.report"].get("error"))
n_calls = len(CALLS)
st2 = engine.run(pr["id"], store_dir=inner)
check("loop: running the finished evaluation again measures nothing new", len(CALLS) == n_calls and st2["status"] == "passed", len(CALLS) - n_calls)

# control: a department that writes into the game's SOURCE on every call really does change the project. Re-measuring
# is bounded: the run still terminates, INCOMPLETE, naming the file that kept changing
g1b = game("loop-control")
BEHAVIOUR.update(write_into_project="src/generated-{n}.ts")
st, pr = review(g1b)
stale = [e for e in store.events(pr) if e["event"] == "stale_evidence"]
check("loop guard: source that keeps changing is re-measured at most STALE_ROUNDS times, then the run stops",
      len(stale) == engine.STALE_ROUNDS and pr.get("unstable") and st["status"] in ("failed", "blocked"), (len(stale), st["status"]))
check("loop guard: the verdict is INCOMPLETE and names what kept changing", st["verdict"] == "INCOMPLETE"
      and any("src/generated-" in r for r in st["verdict_reasons"] or []), (st["verdict"], st["verdict_reasons"]))
BEHAVIOUR.update(write_into_project=None)

# =============================================================== 2. one evaluation target, explicit source-vs-build policy
g2 = game("target-game")
st, pr = review(g2)
browser = [c for c in CALLS if c["dept"] in ("testcraft", "playcraft", "pixelcraft")]
check("target: every browser check (smoke, PLAYCRAFT, PIXELCRAFT, regression) measured the same folder",
      browser and len({c["target"] for c in browser}) == 1, {(c["dept"], c["action"]): c["target"] for c in browser})
check("target: a Vite project is measured as its build (dist/), never its unbuilt source index.html",
      browser and browser[0]["target"] == os.path.join(g2, "dist") and pr["evaluation"]["chosen"] == "build", browser[:1])
check("target: the policy is recorded in the plan and the report", any("evaluation target: the built app dist/" in d for d in pr["decisions"])
      and "Evaluation target:" in open(os.path.join(pr["store"], "REPORT.md")).read())
check("target: the release checks that every browser check used one target",
      any("same target" in c["name"] and c["ok"] for c in pr["tasks"]["release.report"]["result"]["checks"]))
spec = intake.parse("Build a mobile-first habit tracker web app with an original brand"); spec["project"]["path"] = os.path.join(ws, "new-app")
pl = planner.build(spec, {"project": {"exists": False}, "runtimes": {"studio": {"departments": []}}})
br = {t["id"]: t["params"].get("target") for t in pl["tasks"].values() if t.get("department") in ("testcraft", "playcraft", "pixelcraft") and t.get("action") != "assets"
      or t.get("action") == "check_features"}
check("target: a new build plans smoke, features, PIXELCRAFT and the final regression on $target",
      {"qa.smoke", "qa.features", "qa.pixelcraft", "release.regression"} <= set(br) and set(br.values()) == {"$target"}, br)
st, pr = review(g2, overrides={"evaluation": {"target": "source"}})
check("target: evaluation.target=source measures the project folder itself, for every check",
      {c["target"] for c in CALLS if c["dept"] in ("testcraft", "playcraft", "pixelcraft")} == {g2}, {c["target"] for c in CALLS})
g2s = game("static-game", static=True)
st, pr = review(g2s)
check("target: auto on a static game (no bundler) measures the project folder", pr["evaluation"]["chosen"] == "source"
      and {c["target"] for c in CALLS if c["dept"] in ("testcraft", "playcraft", "pixelcraft")} == {g2s})
g2u = game("unbuilt-game", built=False)
st, pr = review(g2u)
check("target: an unbuilt bundler project is never tested from source (no browser check ran)",
      not [c for c in CALLS if c["dept"] in ("testcraft", "playcraft", "pixelcraft")], CALLS)
check("target: ...its browser checks are blocked with the reason and the build command",
      pr["tasks"]["qa.smoke"]["state"] == "blocked" and "npm run build" in str(pr["tasks"]["qa.smoke"].get("reason")), pr["tasks"]["qa.smoke"].get("reason"))
check("target: ...and the evaluation ends INCOMPLETE, saying why", st["verdict"] == "INCOMPLETE" and any("not built" in r for r in st["verdict_reasons"]),
      (st["verdict"], st["verdict_reasons"]))

# =============================================================== 3. evaluation artifacts are isolated from the game
g3 = game("isolated-game")
before = tree(g3)
os.environ.update(GITCRAFT_ROOT=g3, GITCRAFT_ROOTS=g3)   # the cloud single-repo case: the game is the only workspace root
check("isolation: with the game as the only root, the default store would be inside it", artifacts.inside(production.store_root(), g3))
root, why = production.store_root_for(g3)
check("isolation: the production store is chosen outside the game", not artifacts.inside(root, g3) and why, root)
executors.designcraft_assess = real_designcraft
st, pr = review(g3)
check("isolation: the production (store, task folders, reports) lives outside the game", not artifacts.inside(pr["store"], g3), pr["store"])
dc = pr["tasks"]["qa.designcraft"]
check("isolation: DESIGNCRAFT runs (no 'inside the game repository' refusal) and passes", dc["state"] == "passed"
      and "inside the game" not in str(dc.get("error")), (dc["state"], dc.get("error")))
check("isolation: the evaluated game folder is exactly as it was (nothing added or changed)", tree(g3) == before,
      sorted(set(tree(g3)) ^ set(before)))
check("isolation: the production is found again by id from its isolated store", store.load(pr["id"])["id"] == pr["id"]
      and any(x["id"] == pr["id"] for x in store.list_all()))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)
executors.designcraft_assess = fake_designcraft

# =============================================================== 4. every evaluation ends with a final verdict
V = report.verdict
check("verdict: all measured and passed → READY", V([{"id": "a", "status": "passed"}, {"id": "release_ready", "status": "passed"}]) == "READY")
check("verdict: a measured failure → NOT READY", V([{"id": "a", "status": "failed"}, {"id": "b", "status": "blocked"}]) == "NOT READY")
check("verdict: a check that could not run → INCOMPLETE (not NOT READY, not READY)", V([{"id": "a", "status": "passed"}, {"id": "b", "status": "blocked"},
                                                                                    {"id": "release_ready", "status": "failed"}]) == "INCOMPLETE")
check("verdict: a check still pending or waiting for a person → INCOMPLETE", V([{"id": "a", "status": "pending"}]) == "INCOMPLETE"
      and V([{"id": "a", "status": "needs_approval"}]) == "INCOMPLETE")
check("verdict: everything passed but the release gate itself failed → NOT READY",
      V([{"id": "a", "status": "passed"}, {"id": "release_ready", "status": "failed"}]) == "NOT READY")
g4 = game("verdict-game")
BEHAVIOUR.update(smoke_fails=True)
st, pr = review(g4)
check("verdict: a review whose smoke test fails orders no fix work (review changes nothing) and terminates",
      not [t for t in pr["tasks"] if t.startswith("fix.")] and st["status"] in ("failed", "blocked"), (list(pr["tasks"]), st["status"]))
check("verdict: ...NOT READY, with the failed check as the reason", st["verdict"] == "NOT READY" and any("loads_everywhere failed" in r for r in st["verdict_reasons"]),
      (st["verdict"], st["verdict_reasons"]))
BEHAVIOUR.update(smoke_fails=False)
check("verdict: the run result, the stored production and REPORT.md carry the same verdict",
      pr["verdict"]["verdict"] == st["verdict"] and f"verdict **{st['verdict']}**" in open(os.path.join(pr["store"], "REPORT.md")).read()
      and "## Why NOT READY" in open(os.path.join(pr["store"], "REPORT.md")).read())
st, pr = review(game("passing-game"))
check("verdict: a clean review of an existing game can end READY", st["verdict"] == "READY" and not st["verdict_reasons"], (st["verdict"], st["verdict_reasons"]))
nb = engine.plan("Build a small arcade game called Pocket Comet with a score and a restart button", os.path.join(ws, "comet"))
engine.decide(nb["id"], approve=True)
st = engine.run(nb["id"], max_seconds=60)
check("verdict: a build stopped at an agent work order ends INCOMPLETE, naming the work order", st["verdict"] == "INCOMPLETE"
      and any("waiting for the agent" in r for r in st["verdict_reasons"]), (st["verdict"], st["verdict_reasons"]))
check("verdict: production_status always reports one of READY / NOT READY / INCOMPLETE", engine.status(nb["id"])["verdict"] in VERDICTS)

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
