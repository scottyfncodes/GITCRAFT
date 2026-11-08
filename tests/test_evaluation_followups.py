#!/usr/bin/env python3
"""Evaluation follow-ups from the WAR-BALLOON production (NOT READY for two GITCRAFT-side defects):

  5. artifact isolation for EVERY production   a production whose record sits inside the evaluated game (made before
                                                store_root_for existed, or opened with an explicit store there) still
                                                writes every task's output outside the game: the real DESIGNCRAFT runs,
                                                its assessment is the criterion's evidence, the project report finds it,
                                                and nothing in the game changes
  6. criterion evidence for an approved        a check that stands in for a planned one (`replaces`) measures the
     replacement check                          original's criterion; the approver sees which criteria a revision would
                                                leave NOT PLANNED; approval is still required; an inequivalent stand-in
                                                cannot be approved; nothing earlier is rewritten and nothing is assumed

Departments that open a browser are recording fakes; DESIGNCRAFT is the real one.

    python3 tests/test_evaluation_followups.py        (~20 s)"""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-eval2-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_PRODUCTION_ISOLATED=os.path.join(ws, "isolated-home"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"))
os.environ.pop("GITCRAFT_PRODUCTION_HOME", None)
from production import engine, entry, executors, store, artifacts, project_report, report
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def raises(fn, text=""):
    try: fn()
    except Exception as e: return text in str(e)
    return False


def game(name):
    """A small built Vite game (source index.html loads /src/main.ts; dist/ is the build)."""
    g = os.path.join(ws, name); os.makedirs(os.path.join(g, "src"))
    shutil.copytree(os.path.join(HERE, "fixtures", "designcraft", "patrol_ts", "src"), os.path.join(g, "src"), dirs_exist_ok=True)
    open(os.path.join(g, "README.md"), "w").write("# Sky Patrol\n\nA small arcade game: the player dodges enemy drones, collects stars for score, "
                                                   "and clears each level. Three lives; the high score is kept.\n")
    main = ("// the game: player, enemies, score, level, lives\nconst c=document.querySelector('canvas');const x=c.getContext('2d');let score=0,lives=3,level=1;"
            "function f(){x.fillRect(0,0,9,9);requestAnimationFrame(f)};f();\n")
    page = lambda src: f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Sky Patrol</title></head><body><canvas></canvas><script type=module src="{src}"></script></body></html>\n'
    json.dump({"name": name, "scripts": {"build": "vite build"}, "devDependencies": {"vite": "^5.4.0"}}, open(os.path.join(g, "package.json"), "w"))
    open(os.path.join(g, "index.html"), "w").write(page("/src/main.ts"))
    open(os.path.join(g, "src", "main.ts"), "w").write(main)
    os.makedirs(os.path.join(g, "dist", "assets"))
    open(os.path.join(g, "dist", "index.html"), "w").write(page("assets/index.js"))
    open(os.path.join(g, "dist", "assets", "index.js"), "w").write(main)
    return g


def tree(p, skip=None):
    out = {}
    for d, ds, fs in os.walk(p):
        if skip: ds[:] = [x for x in ds if not artifacts.inside(os.path.join(d, x), skip)]
        for f in fs: out[os.path.relpath(os.path.join(d, f), p)] = open(os.path.join(d, f), "rb").read()
    return out


CALLS = []


def fake_studio(dept, action, params, timeout=1800):
    CALLS.append({"dept": dept, "action": action, "target": params.get("target"), "out_dir": params.get("out_dir")})
    out = params["out_dir"]; os.makedirs(out, exist_ok=True)
    rep = os.path.join(out, f"{params.get('name') or action}.json"); json.dump({"dept": dept, "action": action}, open(rep, "w"))
    json.dump({"department": dept, "action": action, "status": "ok"}, open(os.path.join(out, f"{params.get('name') or action}.studio.json"), "w"))
    return {"status": "ok", "out_dir": out, "outputs": [{"path": rep, "role": "report", "format": "json"}],
            "summary": {"overall": {"score": 90}}, "checks": [{"name": f"{dept}.{action} measured", "ok": True}]}


real_designcraft = executors.designcraft_assess
DC = []


def recording_designcraft(project, out_json, timeout=900):
    DC.append(out_json)
    return real_designcraft(project, out_json, timeout=timeout)


executors.studio_run = fake_studio
executors.designcraft_assess = recording_designcraft


def review(g, store_dir=None):
    CALLS.clear(); DC.clear()
    pid = entry.start("Run GITCRAFT: review this game", g, store_dir=store_dir)["production"]
    engine.decide(pid, approve=True, store_dir=store_dir)
    return engine.run(pid, max_seconds=120, store_dir=store_dir), pid


# =============================================================== 5. artifact isolation for every production
g5 = game("legacy-store-game")
legacy = os.path.join(g5, "gitcraft-out", "production")   # where every production lived before store_root_for (WAR-BALLOON's)
before = tree(g5)
st, pid = review(g5, store_dir=legacy)
pr = store.load(pid, legacy)
check("isolation: the production record stays where it was created (inside the game, as legacy productions are)",
      artifacts.inside(pr["store"], g5), pr["store"])
out_root = store.output_root(pr)
check("isolation: ...but its task output goes to the isolated GITCRAFT home, outside the game",
      not artifacts.inside(out_root, g5) and artifacts.inside(out_root, artifacts.isolated_home()) and artifacts.is_artifact_dir(out_root), out_root)
dc = pr["tasks"]["qa.designcraft"]
check("isolation: DESIGNCRAFT ran for real on a production whose store is inside the game (no refusal)",
      DC and dc["state"] == "passed" and "inside the game" not in str(dc.get("error")), (dc["state"], dc.get("error")))
check("isolation: DESIGNCRAFT was handed an output path outside the game, and its assessment is there",
      DC and not artifacts.inside(DC[0], g5) and os.path.isfile(DC[0]) and json.load(open(DC[0])).get("score"), DC)
check("isolation: every department's out_dir was outside the game", CALLS and all(not artifacts.inside(c["out_dir"], g5) for c in CALLS),
      [c["out_dir"] for c in CALLS])
check("isolation: no file of the game changed, apart from the legacy production record itself", tree(g5, skip=legacy) == {
      k: v for k, v in before.items()}, sorted(set(tree(g5, skip=legacy)) ^ set(before)))
acc = {a["id"]: a for a in report.acceptance(pr)}
check("isolation: the design_review criterion is decided by DESIGNCRAFT's measured assessment (passed, with evidence)",
      acc["design_review"]["status"] == "passed" and dc.get("outputs") and not artifacts.inside(dc["outputs"][0]["path"], g5), acc["design_review"])
check("isolation: the release report, status and listing still find the production by id", engine.status(pid, store_dir=legacy)["production"] == pid
      and any(x["id"] == pid for x in store.list_all(legacy)))
P = {"path": os.path.realpath(g5)}
ctx = {"productions": [dict(store.load(pid, legacy), _dir=pr["store"], _outputs=out_root)]}
recs = project_report._studio_records(P, ctx)
check("isolation: the project report collects the department records from the isolated output folder",
      any(r["_path"].startswith(out_root) for r in recs), [r["_path"] for r in recs][:4])
os.environ["GITCRAFT_PRODUCTION_HOME"] = legacy
found = project_report._productions(P)
os.environ.pop("GITCRAFT_PRODUCTION_HOME")
check("isolation: project_report finds the production and its output root", found and found[0].get("_outputs") == out_root, found and found[0].get("_outputs"))
# the executor itself refuses a path inside the game with a reason, before DESIGNCRAFT is started (defence in depth)
r = real_designcraft(g5, os.path.join(g5, "designcraft.json"))
check("isolation: a DESIGNCRAFT output path inside the game is refused by the executor, naming the rule",
      r["status"] == "failed" and "outside" in r["error"] and not os.path.exists(os.path.join(g5, "designcraft.json")), r)
# a store outside the game is still used as is (nothing moves for current productions)
st2, pid2 = review(game("current-store-game"))
pr2 = store.load(pid2)
check("isolation: a production whose store is outside the game writes its task output in its own store, as before",
      store.output_root(pr2) == pr2["store"] and pr2["tasks"]["qa.designcraft"]["state"] == "passed")

# =============================================================== 6. an approved replacement check measures the original's criterion
g6 = game("replace-game")
st, pid = review(g6)
pr = store.load(pid)
check("mapping: the planned smoke check measures loads_everywhere", pr["tasks"]["qa.smoke"]["criterion"] == "loads_everywhere")


def acc_of(pid): return {a["id"]: a["status"] for a in report.acceptance(store.load(pid))}


SMOKE_DIST = {"id": "qa.smoke.dist", "department": "testcraft", "action": "smoke", "params": {"target": "$target", "viewports": ["desktop"], "expect_canvas": True, "name": "smoke"}}

# (a) the WAR-BALLOON failure, reproduced: skip + an extra check with no stated relation → NOT PLANNED, and now the approver is told
rv = engine.revise(pid, {"skip_tasks": ["qa.smoke"], "extra_tasks": [dict(SMOKE_DIST)]}, "point smoke at the build")
rev = store.load(pid)["lifecycle"]["revision"]
check("mapping: a revision that skips a criterion's only check is material (needs a person's approval)", rv["material"] and rv["status"] == "paused", rv.get("material"))
check("mapping: ...and the approver is shown that loads_everywhere would become NOT PLANNED", "loads_everywhere" in rev.get("would_lose", []), rev)
check("mapping: the preview did not touch the production's store or plan", "qa.smoke" in store.load(pid)["tasks"]
      and os.path.isfile(os.path.join(store.load(pid)["store"], "DISCOVERY.md")))
engine.decide(pid, approve=True)
engine.run(pid, max_seconds=60)
check("mapping: an extra check without `replaces` measures nothing it did not name (loads_everywhere NOT PLANNED, never assumed)",
      acc_of(pid)["loads_everywhere"] == "not_planned" and store.load(pid)["tasks"]["qa.smoke.dist"]["state"] == "passed", acc_of(pid))
history_before = [d for d in store.load(pid)["decisions"] if d.startswith(engine.DECISION_HISTORY)]; bp_before = store.load(pid)["blueprint"]
check("mapping: the first approved revision is on the record", any(d.startswith("approved revision: point smoke at the build") for d in history_before), history_before)

# (b) the fix: the same check, declared as the replacement → inherits the criterion, still needs approval, measured afresh
n = len(CALLS)
rv = engine.revise(pid, {"skip_tasks": [], "extra_tasks": [dict(SMOKE_DIST, replaces="qa.smoke")]}, "qa.smoke.dist replaces qa.smoke")
rev = store.load(pid)["lifecycle"]["revision"]
check("mapping: declaring `replaces` is still a material change: the build pauses for approval", rv["material"] and rv["status"] == "paused")
check("mapping: ...the approver sees it would measure loads_everywhere again and lose nothing",
      rev.get("would_measure") == ["loads_everywhere"] and not rev.get("would_lose") and not rev.get("problems"), rev)
check("mapping: nothing runs before the person approves", raises(lambda: engine.run(pid, max_seconds=30)) or len(CALLS) == n, len(CALLS) - n)
engine.decide(pid, approve=True)
pr = store.load(pid)
t = pr["tasks"]["qa.smoke.dist"]
check("mapping: the replacement inherits the original's criterion, stage and dependants", t["criterion"] == "loads_everywhere" and t["stage"] == "qa"
      and t.get("replaces") == "qa.smoke" and "qa.smoke" not in pr["tasks"] and "qa.smoke.dist" in pr["tasks"]["release.report"]["depends_on"], t)
check("mapping: its definition changed, so its earlier pass is not reused (it is measured again)", t["state"] == "pending", t["state"])
engine.run(pid, max_seconds=60)
pr = store.load(pid)
check("mapping: the replacement ran against the build", [c for c in CALLS[n:] if c["action"] == "smoke" and c["target"] == os.path.join(g6, "dist")],
      CALLS[n:])
acc = {a["id"]: a for a in report.acceptance(pr)}
check("mapping: loads_everywhere is decided by the replacement's own measured evidence", acc["loads_everywhere"]["status"] == "passed"
      and any(e.get("task") == "qa.smoke.dist" for e in acc["loads_everywhere"]["evidence"]), acc["loads_everywhere"])
check("mapping: earlier approvals and decisions are kept as they were (appended to, never rewritten)",
      pr["decisions"][:len(history_before)] == history_before and pr["blueprint"]["version"] == bp_before["version"] + 1
      and (pr.get("blueprint_history") or [None])[-1] == bp_before
      and any("qa.smoke.dist replaces qa.smoke" in d for d in pr["decisions"]))

# (c) a stand-in that is not the same check cannot carry the criterion, and the revision cannot be approved
rv = engine.revise(pid, {"skip_tasks": [], "extra_tasks": [{"id": "qa.look", "department": "pixelcraft", "action": "audit",
                                                             "params": {"target": "$target", "name": "look"}, "replaces": "qa.smoke"}]}, "swap smoke for a visual audit")
rev = store.load(pid)["lifecycle"]["revision"]
check("mapping: a `replaces` that is not the same check is a plan problem shown before approval",
      any("not the same check" in p for p in rev.get("problems", [])), rev.get("problems"))
check("mapping: ...and approving it is refused (the revision stays pending)", raises(lambda: engine.decide(pid, approve=True), "problems")
      and store.load(pid)["lifecycle"].get("revision"))
engine.decide(pid, approve=False, note="not equivalent")
rv = engine.revise(pid, {"skip_tasks": [], "extra_tasks": [dict(SMOKE_DIST, replaces="qa.smoke", criterion="performance")]}, "mislabel the criterion")
check("mapping: a replacement that names a different criterion than the original is refused",
      any("names criterion performance" in p for p in store.load(pid)["lifecycle"]["revision"].get("problems", [])))
engine.decide(pid, approve=False)
rv = engine.revise(pid, {"skip_tasks": [], "extra_tasks": [dict(SMOKE_DIST, replaces="qa.nothing")]}, "replace a task that does not exist")
check("mapping: replacing a task that is not in the plan is refused", any("not in the plan" in p for p in store.load(pid)["lifecycle"]["revision"].get("problems", [])))
engine.decide(pid, approve=False)
check("mapping: declined revisions leave the approved plan as it was", acc_of(pid)["loads_everywhere"] == "passed" and "qa.look" not in store.load(pid)["tasks"])

# =============================================================== 7. recovering a production that failed on the old framework
# WAR-BALLOON's state: DESIGNCRAFT refused (output path inside the game) and failed after its retry; the release failed
# on it and the deploy is blocked. After the framework fix, the person retries that check explicitly; it runs for real.
g7 = game("recover-game")
legacy7 = os.path.join(g7, "gitcraft-out", "production")


def old_refusal(project, out_json, timeout=900):   # what the previous framework produced (executors._child_raw on exit 2)
    return {"status": "failed", "failure": "crash", "error": f"refused: {out_json} is inside the game repository; DESIGNCRAFT keeps the game read-only\n"}


executors.designcraft_assess = old_refusal
st, pid = review(g7, store_dir=legacy7)
pr = store.load(pid, legacy7)
dc = pr["tasks"]["qa.designcraft"]
check("recover: reproduced: DESIGNCRAFT failed by refusal (an execution failure, no measurement)", dc["state"] == "failed"
      and dc["attempts"][-1]["outcome"] in engine.RETRYABLE and {a["id"]: a["status"] for a in report.acceptance(pr)}["design_review"] == "failed", dc.get("failure"))
check("recover: ...and the evaluation is not READY", st["verdict"] != "READY", st["verdict"])
executors.designcraft_assess = recording_designcraft
check("recover: a retry needs a reason", raises(lambda: engine.retry(pid, ["qa.designcraft"], "", store_dir=legacy7), "reason"))
passed7 = next(k for k, v in pr["tasks"].items() if v["state"] == "passed")
check("recover: a check that passed cannot be 'retried'", raises(lambda: engine.retry(pid, [passed7], "x", store_dir=legacy7), "only a failed check"))
n_att = len(dc["attempts"])
engine.retry(pid, ["qa.designcraft"], "GITCRAFT fix: task output is isolated from the game", store_dir=legacy7)
pr = store.load(pid, legacy7)
check("recover: the retried check and the release waiting on it are pending again, with the reason recorded",
      pr["tasks"]["qa.designcraft"]["state"] == "pending" and pr["tasks"]["release.report"]["state"] == "pending"
      and "retry requested" in pr["tasks"]["qa.designcraft"]["reason"] and any(e["event"] == "retry_requested" for e in store.events(pr)))
DC.clear()
st = engine.run(pid, max_seconds=120, store_dir=legacy7)
pr = store.load(pid, legacy7)
dc = pr["tasks"]["qa.designcraft"]
check("recover: DESIGNCRAFT then runs for real, outside the game, and its assessment decides design_review",
      DC and not artifacts.inside(DC[0], g7) and dc["state"] == "passed" and {a["id"]: a["status"] for a in report.acceptance(pr)}["design_review"] == "passed",
      (dc["state"], dc.get("error"), DC))
check("recover: the failed attempts stay in its history (nothing rewritten)", len(dc["attempts"]) == n_att + 1
      and dc["attempts"][n_att - 1].get("retry_requested") and dc["attempts"][0]["status"] == "failed", [a.get("status") for a in dc["attempts"]])
check("recover: the release ran again and the run ends with a verdict", pr["tasks"]["release.report"]["state"] in ("passed", "failed") and st["verdict"] in ("READY", "NOT READY", "INCOMPLETE"),
      (pr["tasks"]["release.report"]["state"], st["verdict"]))
# a check that measured the project and failed its gate is never retried: it is fixed in the project
g7q = game("quality-game")
st, pidq = review(g7q)
prq = store.load(pidq)
t = next(iter(prq["tasks"].values()))
t["state"] = "failed"; t["failure"] = "quality"; t["attempts"] = [{"outcome": "quality", "status": "ok"}]; store.save(prq)
check("recover: a measured (quality) failure is refused: retry cannot turn a measured failure into a pass",
      raises(lambda: engine.retry(pidq, [t["id"]], "try again"), "never retried"))

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
