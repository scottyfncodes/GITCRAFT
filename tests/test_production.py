#!/usr/bin/env python3
"""Production Director tests (fast): intake, planning, validation, gates, persistence, locking, resume,
fingerprints, the report verdict, contracts, and a small real production through the sandboxed MCP server.

    python3 tests/test_production.py           (~1 min; the full master-prompt run is tests/acceptance_production.py)"""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-prod-unit-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import intake, planner, gates, engine, store, report, contracts, executors
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


# ---- intake
s = intake.parse("Build a polished, mobile-first, original platformer game called Lantern Drift with sound, music, five levels and deployment.")
check("intake: game, platformer, mobile-first, title", s["deliverable"] == "game" and s["genres"][0] == "platformer" and s["platform"]["mobile_first"] and s["title"] == "Lantern Drift")
check("intake: five levels by LevelCraft, sound + music, polished bar", s["assets"]["levels"]["count"] == 5 and s["assets"]["levels"]["kind"] == "platformer"
      and s["assets"]["sfx"] and s["assets"]["music"] and s["quality"]["level"] == "polished")
check("intake: deployment is never pre-authorised", s["features"]["deploy"] and not s["authorisations"]["deploy"])
check("intake: every default is a listed assumption", any("music mood" in a for a in s["assumptions"]))
app = intake.parse("Build a mobile-first habit tracker web app with an original brand and a polished interface")
check("intake: an app gets PIXELCRAFT, not PLAYCRAFT or DESIGNCRAFT", app["deliverable"] == "app" and app["quality"]["pixelcraft"] and not app["quality"]["playcraft"]
      and not app["quality"]["designcraft"] and app["assets"].get("identity"), app["quality"])
three = intake.parse("Make a low-poly 3D exploration game on a volcano island with wooden and stone textures at sunset")
check("intake: 3D → materials and world, sky preset from the prompt", three["dimension"] == "3d" and {"wood", "stone"} <= set(three["assets"]["materials"])
      and three["assets"]["world"]["terrain"] == "volcano" and three["assets"]["world"]["sky"] == "sunset", three["assets"])
check("intake: too short a prompt is refused", raises(lambda: intake.parse("game"), ValueError))
lp = intake.parse("Make a platformer level pack with five levels and music", overrides={"deliverable": "asset_pack"})
check("intake: a deliverable override re-derives its quality bar (no PLAYCRAFT/PIXELCRAFT criteria for an asset pack)",
      not lp["quality"]["playcraft"] and not lp["quality"]["pixelcraft"] and not {"gameplay_quality", "interface_quality", "design_review"} & {c["id"] for c in lp["acceptance"]},
      [c["id"] for c in lp["acceptance"]])
lq = intake.parse("Make a platformer level pack with five levels and music", overrides={"deliverable": "asset_pack", "quality": {"pixelcraft": True}})
check("intake: ...unless the override sets that bar explicitly (then it stays, and is measured or NOT PLANNED)", lq["quality"]["pixelcraft"] and "interface_quality" in {c["id"] for c in lq["acceptance"]})
o = intake.parse("Build a small arcade game", overrides={"quality": {"playcraft_min": 70}})
check("intake: overrides deep-merge into the spec", o["quality"]["playcraft_min"] == 70 and "max_rounds" in o["quality"])

# ---- planning and validation (no runtime needed: discovery is passed in)
disc = {"project": {"exists": False}, "runtimes": {"studio": {"departments": []}}}
spec = intake.parse("Build a polished mobile platformer game called Ember Run with sound, music, three levels and an original visual identity")
spec["project"]["path"] = os.path.join(ws, "ember")
pl = planner.build(spec, disc)
check("plan: valid as built", planner.validate(pl) == [], planner.validate(pl))
w = {t: i for i, g in enumerate(pl["parallel_groups"]) for t in g}
check("plan: build after integration after every asset; QA after build; release last",
      max(w[t] for t in pl["tasks"] if t.startswith(("audio.", "levels."))) < w["integrate.assets"] < w["build"] < w["qa.smoke"] < w["release.regression"] < w["release.report"])
check("plan: QA tasks in one parallel wave", len({w[t] for t in pl["tasks"] if t.startswith("qa.")}) == 1)
bad = json.loads(json.dumps(pl)); bad["tasks"]["build"]["depends_on"].append("qa.smoke")
check("plan: a dependency cycle is refused", any("cycle" in p for p in planner.validate(bad)))
bad = json.loads(json.dumps(pl)); bad["tasks"]["audio.music"]["params"]["mood"] = "dubstep"
check("plan: a request the department would refuse is a problem before running", any("audio.music" in p for p in planner.validate(bad)))
bad = json.loads(json.dumps(pl)); bad["tasks"]["build"]["depends_on"].append("nope")
check("plan: an unknown dependency is refused", any("unknown dependency" in p for p in planner.validate(bad)))
check("plan: readiness reports what cannot run here", planner.readiness(pl, {"runtimes": {"studio": {"status": "blocked", "reason": "no runtime"}}}).get("audio.music") == "no runtime")

# ---- gates
check("gates: department ok + checks → status_ok", gates.evaluate({"gate": [{"type": "status_ok"}]}, {"status": "ok", "checks": [{"name": "x", "ok": True}]}, {})[0]["ok"])
mg = gates.evaluate({"gate": [{"type": "min", "path": "summary.overall.score", "min": 60}]}, {"status": "ok"}, {})[0]
check("gates: a missing measurement fails a minimum (never assumed)", not mg["ok"] and mg["detail"] == "not measured")
check("gates: measured below the bar fails", not gates.evaluate({"gate": [{"type": "min", "path": "s", "min": 60}]}, {"s": 59}, {})[0]["ok"])
check("gates: classify quality vs execution vs request vs blocked",
      gates.classify({"status": "failed", "checks": [{"ok": False}], "outputs": [{}]}) == "quality" and gates.classify({"status": "failed", "error": "x"}) == "execution"
      and gates.classify({"status": "failed", "failure": "request"}) == "request" and gates.classify({"status": "blocked"}) == "blocked")
rem = gates.remediation({"department": "playcraft"}, {"plan": ["1. Fix defects: x"], "summary": {"top_findings": ["1. y"]}}, [{"condition": "PLAYCRAFT ≥ 55", "ok": False, "detail": "measured 50"}])
check("gates: a failed QA gate becomes actionable findings", any("measured 50" in r for r in rem) and any("Fix defects" in r for r in rem), rem)

# ---- fingerprints, store, lock
proj = os.path.join(ws, "fp"); os.makedirs(proj); open(os.path.join(proj, "a.js"), "w").write("1")
f1 = engine.fingerprint(proj); open(os.path.join(proj, "a.js"), "w").write("2")
check("fingerprint changes when a project file changes", f1 != engine.fingerprint(proj))
prod = {"id": store.new_id("lock test"), "spec": {"title": "lock"}, "tasks": {}, "order": []}
store.create(prod)
with store.lock(prod):
    check("lock: a second runner is refused while one holds the production", raises(lambda: store.lock(prod).__enter__(), RuntimeError))
check("store: a production id cannot address anything outside the store", store.path("../../etc", "x").startswith(store.store_root() + os.sep)
      and raises(lambda: store.path("ok", "..", "..", "x"), ValueError))
check("report: verdicts", report.verdict([{"id": "a", "status": "passed"}]) == "READY" and report.verdict([{"id": "a", "status": "failed"}]) == "NOT READY"
      and report.verdict([{"id": "a", "status": "passed"}, {"id": "deployment", "status": "needs_approval"}]).startswith("READY — deployment"))
check("report: a NOT PLANNED criterion makes the verdict NOT READY even when everything else passed",
      report.verdict([{"id": "a", "status": "passed"}, {"id": "b", "status": "not_planned"}, {"id": "release_ready", "status": "passed"}]) == "NOT READY")

# ---- acceptance criteria are never dropped (regression: PR #42 review)
gp = engine.plan("Build a polished mobile platformer game called Keeper with sound, music and three levels", os.path.join(ws, "keeper"),
                 {"skip_tasks": ["qa.licences"]})
ids = [c["id"] for c in gp["spec"]["acceptance"]]
check("criteria: skipping the only task that measures a criterion keeps the criterion in the spec", "licensing" in ids, ids)
check("criteria: the plan names it as unmeasured with a warning", gp["unmeasured_criteria"] == ["licensing"] and any("licensing" in w for w in gp["warnings"]),
      (gp["unmeasured_criteria"], gp["warnings"]))
for t in gp["tasks"].values():   # force every planned task to have passed: READY must still be impossible
    t["state"] = "passed"; t["gate_results"] = [{"condition": "forced for the test", "ok": True}]
acc = {a["id"]: a for a in report.acceptance(gp)}
check("criteria: the unmeasured criterion reports NOT PLANNED in the acceptance report", acc["licensing"]["status"] == "not_planned"
      and "NOT PLANNED" in str(acc["licensing"]["why"]), acc["licensing"])
check("criteria: with every task passed, the production is still NOT READY", report.verdict(list(acc.values())) == "NOT READY"
      and acc["release_ready"]["status"] != "passed" and "NOT PLANNED" in report.markdown(gp), report.verdict(list(acc.values())))
ok_plan = engine.plan("Build a polished mobile platformer game called Keeper Two with sound, music and three levels", os.path.join(ws, "keeper2"))
check("criteria: a normal plan measures every criterion", ok_plan["unmeasured_criteria"] == [] and
      {"loads_everywhere", "gameplay_quality", "interface_quality", "asset_integrity", "licensing", "release_ready"} <= {c["id"] for c in ok_plan["spec"]["acceptance"]})
con = contracts.all_contracts()
check("contracts: all eleven Studio departments + 3D, DESIGNCRAFT, agent, built-ins", len(con["studio"]) == 11 and {"forgecraft", "designcraft", "agent", "builtin"} <= set(con))

# ---- a small real production through the sandboxed server (AudioCraft + LevelCraft; plan, run, resume)
if executors.studio_python():
    from mcp_client import Client
    c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=dict(os.environ), log=os.path.join(ws, "studiocraft.log"))
    ok, p = c.call("production_plan", {"prompt": "Make a sound pack with jump and coin sound effects and calm music", "project": os.path.join(ws, "pack"),
                                       "overrides": {"deliverable": "asset_pack"}}, timeout=300)
    check("server: production_plan inside the sandbox", ok and p["status"] == "planned" and {"audio.sfx.jump", "audio.sfx.coin", "audio.music"} <= {t["id"] for t in p["tasks"]}, p)
    ok, r = c.call("production_run", {"production": p["production"]}, timeout=120)
    check("server: nothing is built before the blueprint is approved", ok and "not approved" in str(r.get("refused")) and p["stage"] == "decisions", r)
    ok, d = c.call("production_decide", {"production": p["production"], "approve": True}, timeout=120)
    check("server: production_decide approves the blueprint", ok and d["stage"] == "approved", d)
    ok, r = c.call("production_run", {"production": p["production"]}, timeout=600)
    check("server: a real run passes every task and the release gate", ok and r["status"] == "passed" and r["counts"].get("passed") == len(p["tasks"]), r.get("counts"))
    pr = store.load(p["production"])
    check("server: outputs recorded with hashes and provenance", all(o.get("sha256") for t in pr["tasks"].values() for o in t.get("outputs", []))
          and os.path.exists(pr["tasks"]["audio.music"]["result"]["record"]))
    n = {t: len(x["attempts"]) for t, x in pr["tasks"].items()}
    c.call("production_run", {"production": p["production"]}, timeout=300)
    check("server: running a finished production again redoes nothing", n == {t: len(x["attempts"]) for t, x in store.load(p["production"])["tasks"].items()})
    os.remove(next(o["path"] for o in pr["tasks"]["audio.sfx.jump"]["outputs"] if o["path"].endswith(".ogg")))
    ok, r = c.call("production_run", {"production": p["production"]}, timeout=300)
    pr2 = store.load(p["production"])
    check("server: a deleted department output is detected on resume and that task (only) is redone",
          len(pr2["tasks"]["audio.sfx.jump"]["attempts"]) == 2 and len(pr2["tasks"]["audio.sfx.coin"]["attempts"]) == 1 and r["status"] == "passed", r.get("counts"))
    # regression (PR #42 review): a requirement whose task was removed can never end READY, in a real run
    ok, p = c.call("production_plan", {"prompt": "Make a sound pack with jump and coin sound effects and calm music", "project": os.path.join(ws, "pack2"),
                                       "overrides": {"deliverable": "asset_pack", "skip_tasks": ["audio.music"]}}, timeout=300)
    c.call("production_decide", {"production": p["production"], "approve": True}, timeout=120)
    check("server: the music criterion stays in the plan as unmeasured", ok and p["unmeasured_criteria"] == ["asset_music"]
          and "asset_music" in {x["id"] for x in p["acceptance"]}, p.get("unmeasured_criteria"))
    ok, r = c.call("production_run", {"production": p["production"]}, timeout=600)
    pr = store.load(p["production"])
    ok2, rep = c.call("production_report", {"production": p["production"]}, timeout=120)
    st = {x["id"]: x["status"] for x in rep["acceptance"]}
    check("server: every remaining task passed, but the release gate failed on the NOT PLANNED criterion",
          all(pr["tasks"][t]["state"] == "passed" for t in pr["tasks"] if t != "release.report") and pr["tasks"]["release.report"]["state"] == "failed"
          and any("asset_music" in c["name"] and not c["ok"] and "NOT PLANNED" in str(c.get("detail")) for c in pr["tasks"]["release.report"]["result"]["checks"]), pr["tasks"]["release.report"].get("error"))
    check("server: status failed, report NOT READY with the criterion NOT PLANNED", r["status"] == "failed" and st["asset_music"] == "not_planned"
          and "NOT READY" in rep["markdown"] and "NOT PLANNED" in rep["markdown"], (r["status"], st))
    c.p.kill()
else:
    print("SKIP server checks: the Studio runtime is not installed (scripts/install-studio.sh)")

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
