#!/usr/bin/env python3
"""Resuming a production that stopped for GITCRAFT's own reasons (from the FOXTAIL polish pass, which stalled four times
on the tool rather than on the game):

  1. a check blocked on an unbuilt app      "run the build, then run again" now works: once dist/ exists the blocked
                                            checks run, and whatever waited behind them is released; still unbuilt, they
                                            stay blocked. No plan revision that swaps a check for a copy of itself.
  2. a work order's own task folder         the agent is told to write its task files in the production's task folder.
                                            With the project as the only workspace root that folder is in GITCRAFT's
                                            isolated home: a submission from there is accepted, anything else outside
                                            the roots is still refused.
  3. hand-offs follow a replaced check      `replaces` moved the dependency but left {"$from": <old id>} behind; the
                                            run died resolving it. The reference follows the replacement, a reference
                                            to a task that is not in the plan is a plan problem, and at run time it is
                                            a hand-off error for that one task.
  4. a run that dies says so                one task's crash fails that task; a crash of the run itself (a background
                                            thread) is written to the production, which no longer reads "running".

Departments that open a browser are recording fakes.

    python3 tests/test_resume.py        (~15 s)"""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-resume-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_PRODUCTION_ISOLATED=os.path.join(ws, "isolated-home"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"), GITCRAFT_PRODUCTION_REPORT="0")
os.environ.pop("GITCRAFT_PRODUCTION_HOME", None)
from production import engine, entry, executors, store, artifacts, planner
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:500]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


PAGE = lambda src: f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Sky Patrol</title></head><body><canvas></canvas><script type=module src="{src}"></script></body></html>\n'
MAIN = ("// the game: player, enemies, score, level, lives\nconst c=document.querySelector('canvas');const x=c.getContext('2d');let score=0,lives=3,level=1;"
        "function f(){x.fillRect(0,0,9,9);requestAnimationFrame(f)};f();\n")


def build(g):
    """What `npm run build` leaves behind."""
    os.makedirs(os.path.join(g, "dist", "assets"), exist_ok=True)
    open(os.path.join(g, "dist", "index.html"), "w").write(PAGE("assets/index.js"))
    open(os.path.join(g, "dist", "assets", "index.js"), "w").write(MAIN)


def game(name, built=True):
    """A small Vite game: the source index.html loads /src/main.ts; dist/ is the build (absent when built=False)."""
    g = os.path.join(ws, name); os.makedirs(os.path.join(g, "src"))
    shutil.copytree(os.path.join(HERE, "fixtures", "designcraft", "patrol_ts", "src"), os.path.join(g, "src"), dirs_exist_ok=True)
    open(os.path.join(g, "README.md"), "w").write("# Sky Patrol\n\nA small arcade game: the player dodges enemy drones, collects stars for score, "
                                                   "and clears each level. Three lives; the high score is kept.\n")
    json.dump({"name": name, "scripts": {"build": "vite build"}, "devDependencies": {"vite": "^5.4.0"}}, open(os.path.join(g, "package.json"), "w"))
    open(os.path.join(g, "index.html"), "w").write(PAGE("/src/main.ts"))
    open(os.path.join(g, "src", "main.ts"), "w").write(MAIN)
    if built: build(g)
    return g


CALLS = []


def fake_studio(dept, action, params, timeout=1800):
    CALLS.append({"dept": dept, "action": action, "name": params.get("name"), "baseline": params.get("baseline")})
    out = params["out_dir"]; os.makedirs(out, exist_ok=True)
    rep = os.path.join(out, f"{params.get('name') or action}.json"); json.dump({"dept": dept, "action": action}, open(rep, "w"))
    json.dump({"department": dept, "action": action, "status": "ok"}, open(os.path.join(out, f"{params.get('name') or action}.studio.json"), "w"))
    return {"status": "ok", "out_dir": out, "outputs": [{"path": rep, "role": "audit" if dept == "pixelcraft" else "report", "format": "json"}],
            "summary": {"overall": {"score": 90}}, "checks": [{"name": f"{dept}.{action} measured", "ok": True}]}


executors.studio_run = fake_studio


def start(text, g):
    CALLS.clear()
    pid = entry.start(text, g)["production"]
    engine.decide(pid, approve=True)
    return pid


T = lambda pid: store.load(pid)["tasks"]
events = lambda pid: [json.loads(l) for l in open(os.path.join(store.load(pid)["store"], "events.jsonl"))]

# =============================================================== 1. a check blocked on an unbuilt app runs once it is built
g1 = game("unbuilt-game", built=False)
pid = start("Run GITCRAFT: polish it", g1)
st = engine.run(pid, max_seconds=60)
t = T(pid)
check("unbuilt: both baselines are blocked with the build command, and nothing was measured",
      all(t[b]["state"] == "blocked" and t[b].get("install") == ["npm run build"] and t[b].get("blocked_on") == "target" for b in ("baseline.pixelcraft", "baseline.playcraft"))
      and not CALLS, ({b: (t[b]["state"], t[b].get("install"), t[b].get("blocked_on")) for b in ("baseline.pixelcraft", "baseline.playcraft")}, CALLS))
check("unbuilt: a blocked check still cannot be retried (retry is for failures that measured nothing)",
      raises(lambda: engine.retry(pid, ["baseline.pixelcraft"], "built now")))
st = engine.run(pid, max_seconds=60)
check("unbuilt: running again without building changes nothing (still blocked, still nothing measured)",
      T(pid)["baseline.pixelcraft"]["state"] == "blocked" and not CALLS and not [e for e in events(pid) if e["event"] == "target_built"])
build(g1)
st = engine.run(pid, max_seconds=60)
t = T(pid)
check("built: the same run command now measures both baselines (no plan revision, no copy of the check)",
      t["baseline.pixelcraft"]["state"] == "passed" and t["baseline.playcraft"]["state"] == "passed"
      and sorted(c["name"] for c in CALLS) == ["pixelcraft_before", "playcraft_before"] and "baseline.pixelcraft.built" not in t,
      ({b: t[b]["state"] for b in ("baseline.pixelcraft", "baseline.playcraft")}, CALLS))
check("built: what waited behind them is released (the direction work order is issued)",
      t["design.direction"]["state"] == "awaiting_agent" and st["status"] == "awaiting_agent", (t["design.direction"]["state"], st["status"]))
check("built: the release is recorded, and the stale build hint is gone from the task",
      [e for e in events(pid) if e["event"] == "target_built" and set(e["tasks"]) == {"baseline.pixelcraft", "baseline.playcraft"}]
      and not t["baseline.pixelcraft"].get("install") and not t["baseline.pixelcraft"].get("blocked_on"), t["baseline.pixelcraft"].get("install"))

g1b = game("unbuilt-legacy", built=False)
pid = start("Run GITCRAFT: polish it", g1b)
engine.run(pid, max_seconds=60)
pr = store.load(pid)
for b in ("baseline.pixelcraft", "baseline.playcraft"): pr["tasks"][b].pop("blocked_on", None)   # as recorded before the reason was kept
pr["tasks"]["qa.designcraft"]["state"] = "blocked"; pr["tasks"]["qa.designcraft"]["install"] = ["pip install something"]; pr["tasks"]["qa.designcraft"]["reason"] = "a runtime is missing"
store.save(pr); build(g1b)
engine.run(pid, max_seconds=60)
t = T(pid)
check("built: a production recorded before the reason was kept is recognised by its build command",
      t["baseline.pixelcraft"]["state"] == "passed" and t["baseline.playcraft"]["state"] == "passed", {b: t[b]["state"] for b in ("baseline.pixelcraft", "baseline.playcraft")})
check("built: a check blocked for another reason (a missing runtime) is not touched",
      t["qa.designcraft"]["state"] == "blocked" and t["qa.designcraft"]["install"] == ["pip install something"], t["qa.designcraft"])

# =============================================================== 2. the agent's own task folder is accepted
g2 = game("only-root-game")
os.environ.update(GITCRAFT_ROOT=g2, GITCRAFT_ROOTS=g2)   # the cloud single-repo case: the game is the only workspace root
pid = start("Run GITCRAFT: the game feels boring, make it more fun", g2)
engine.run(pid, max_seconds=60)
pr = store.load(pid); wo = pr["tasks"]["design.direction"]
tdir = os.path.dirname(wo["work_order_path"])
check("task folder: with the game as the only root, the work order's folder is outside the roots (GITCRAFT's isolated home)",
      wo["state"] == "awaiting_agent" and not engine.inside_roots(tdir) and artifacts.inside(tdir, artifacts.isolated_home()), tdir)
elsewhere = os.path.join(ws, "elsewhere"); os.makedirs(elsewhere)
stray = os.path.join(elsewhere, "direction.json"); shutil.copy(os.path.join(REPO, "acceptance", "assignments", "improve-game", "direction.json"), stray)
r = engine.submit(pid, "design.direction", files=[stray])["submission"]
check("task folder: a file outside the roots and outside GITCRAFT's own folders is still refused",
      not r["accepted"] and any("inside the workspace roots" in c["name"] and not c["ok"] and c["detail"] == stray for c in r["checks"]), r["checks"])
mine = os.path.join(tdir, "direction.json"); shutil.copy(stray, mine)
r = engine.submit(pid, "design.direction", files=[mine])["submission"]
check("task folder: the file the work order asked for, where it asked for it, is accepted",
      r["accepted"] and not [c for c in r["checks"] if "inside the workspace roots" in c["name"]] and T(pid)["design.direction"]["state"] == "passed",
      [c for c in r["checks"] if not c["ok"]])
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws)

# =============================================================== 3. hand-offs follow a replaced check
g3 = game("replaced-game")
pid = start("Run GITCRAFT: polish it", g3)
SAME = lambda tid: {k: v for k, v in T(pid)[tid].items() if k in ("department", "action", "params")}
extra = [dict(SAME("baseline.pixelcraft"), id="baseline.pixelcraft.again", depends_on=["foundation.scaffold"], replaces="baseline.pixelcraft"),
         dict(SAME("baseline.playcraft"), id="baseline.playcraft.again", depends_on=["foundation.scaffold"], replaces="baseline.playcraft")]
rv = engine.revise(pid, {"extra_tasks": extra}, "the same baselines, re-issued")
check("replaces: the revision is material and has no problems", rv["status"] == "paused" and not rv["revision"]["problems"], rv.get("revision"))
engine.decide(pid, approve=True)
t = T(pid)
check("replaces: the before/after checks depend on the replacements...",
      "baseline.pixelcraft.again" in t["qa.pixelcraft"]["depends_on"] and "baseline.playcraft.again" in t["qa.playcraft"]["depends_on"] and "baseline.pixelcraft" not in t)
check("replaces: ...and read their baseline from them (the hand-off follows the replacement)",
      t["qa.pixelcraft"]["params"]["baseline"]["$from"] == "baseline.pixelcraft.again" and t["qa.playcraft"]["params"]["baseline"]["$from"] == "baseline.playcraft.again",
      (t["qa.pixelcraft"]["params"]["baseline"], t["qa.playcraft"]["params"]["baseline"]))
check("replaces: no hand-off in the plan names a task that is not in it",
      not [(k, r) for k, x in t.items() for r in planner._from_refs(x.get("params")) if r not in t])
st = engine.run(pid, max_seconds=60)
check("replaces: the run reaches the direction work order", st["status"] == "awaiting_agent" and T(pid)["design.direction"]["state"] == "awaiting_agent", st["status"])

pid2 = start("Run GITCRAFT: polish it", game("dangling-game"))
rv = engine.revise(pid2, {"extra_tasks": [{"id": "qa.look", "department": "pixelcraft", "action": "verify", "depends_on": ["build"],
                                           "params": {"baseline": {"$from": "baseline.nowhere", "role": "audit", "format": "json"}, "target": "$target", "name": "look"}}]},
                   "a comparison against a baseline that is not planned")
check("dangling: a hand-off from a task that is not in the plan is a plan problem, shown before approval",
      any("hands on from baseline.nowhere" in p for p in rv["revision"]["problems"]) and raises(lambda: engine.decide(pid2, approve=True)), rv["revision"]["problems"])
engine.decide(pid2, approve=False)

pr = store.load(pid)   # a record made before the fix: the reference still names the replaced check
pr["tasks"]["qa.pixelcraft"]["params"]["baseline"]["$from"] = "baseline.pixelcraft"
check("stale record: resolving it is a hand-off error, not a KeyError",
      "not a task in this plan" in str(raises(lambda: engine.resolve(pr, pr["tasks"]["qa.pixelcraft"]["params"]), engine.HandoffError)))

# =============================================================== 4. a run that dies says so
g4 = game("crash-game")
pid = start("Run GITCRAFT: polish it", g4)
real_resolve = engine.resolve


def flaky(prod, v):
    if isinstance(v, dict) and v.get("name") == "pixelcraft_before": raise RuntimeError("boom in the hand-off")
    return real_resolve(prod, v)


engine.resolve = flaky
st = engine.run(pid, max_seconds=60)
engine.resolve = real_resolve
t = T(pid)
check("task crash: the task that crashed fails by itself, with the error",
      t["baseline.pixelcraft"]["state"] == "failed" and "boom in the hand-off" in str(t["baseline.pixelcraft"].get("error")), (t["baseline.pixelcraft"]["state"], t["baseline.pixelcraft"].get("error")))
check("task crash: the rest of the run went on, and the run ended normally",
      t["baseline.playcraft"]["state"] == "passed" and st["status"] != "running" and [e for e in events(pid) if e["event"] == "run_stopped"], (t["baseline.playcraft"]["state"], st["status"]))
check("task crash: it measured nothing, so it can be retried", engine.retry(pid, ["baseline.pixelcraft"], "the hand-off is fixed") and T(pid)["baseline.pixelcraft"]["state"] == "pending")

real_ready = engine._ready_tasks
engine._ready_tasks = lambda prod: (_ for _ in ()).throw(RuntimeError("the run loop itself broke"))
out = engine.run_recorded(pid, max_seconds=60)
engine._ready_tasks = real_ready
pr = store.load(pid); st = engine.status(pid)
check("run crash: the background run reports it instead of vanishing", out.get("status") == "crashed" and "the run loop itself broke" in out.get("error", ""), out)
check("run crash: the production no longer reads 'running', and nothing is left in progress",
      pr["status"] != "running" and not [x for x in pr["tasks"].values() if x["state"] == "in_progress"], pr["status"])
check("run crash: the error is in the record, the event log and production_status",
      "the run loop itself broke" in pr["crash"]["error"] and [e for e in events(pid) if e["event"] == "run_crashed"]
      and "the run loop itself broke" in st["crash"]["error"] and any("error in GITCRAFT itself" in n for n in st["next"]), st.get("next"))
st = engine.run_recorded(pid, max_seconds=60)
check("run crash: the next run resumes, measures what was pending, and clears the note",
      "crash" not in st and "crash" not in store.load(pid) and T(pid)["baseline.pixelcraft"]["state"] == "passed", (st.get("crash"), T(pid)["baseline.pixelcraft"]["state"]))

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
