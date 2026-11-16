#!/usr/bin/env python3
"""Evaluator corrections: a measured failure runs again only when the evaluator that measured it has changed.

  - a genuine product failure (same evaluator, same project) is still refused: it is fixed in the project;
  - a failure measured by an evaluator that has since changed can be measured again, on the record, by `retry`;
  - nothing is converted: the check waits to run, and passes or fails on what it measures then;
  - the earlier result, its attempt and the work order it opened stay in the history.

    python3 tests/test_evaluator_correction.py"""
import copy, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-evalcorr-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PRODUCTION_HOME=os.path.join(ws, "productions"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import engine, store, evaluator, PENDING, FAILED, SKIPPED, PASSED, AWAITING_AGENT
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=ValueError):
    try: fn()
    except exc as e: return str(e) or True
    return False


# ---- identity
req = {"id": "qa.request", "kind": "builtin", "action": "check_request"}
smoke = {"id": "qa.smoke", "kind": "studio", "department": "testcraft", "action": "smoke"}
play = {"id": "qa.playcraft", "kind": "studio", "department": "playcraft", "action": "pass"}
i1, i2 = evaluator.identity(req), evaluator.identity(req)
check("identity: a builtin check has a name, a fingerprint and files", i1 and i1["name"] == "production.check_request" and len(i1["fingerprint"]) == 16 and i1["files"] == len(evaluator.BUILTIN), i1)
check("identity: the same code gives the same fingerprint", i1 == i2)
check("identity: different departments are different evaluators", evaluator.identity(smoke)["fingerprint"] != evaluator.identity(play)["fingerprint"])
check("identity: an agent's work order is not an evaluator", evaluator.identity({"id": "build", "kind": "agent"}) is None)
copy_root = os.path.join(ws, "gitcraft-copy")
for d in ("production", "studio/core", "studio/departments/testcraft", "studio/departments/playcraft", "gamedesign"):
    shutil.copytree(os.path.join(REPO, d), os.path.join(copy_root, d), ignore=shutil.ignore_patterns("__pycache__", "node_modules", "*.pyc"))
base = {k: evaluator.identity(t, copy_root)["fingerprint"] for k, t in (("req", req), ("smoke", smoke), ("play", play))}
check("identity: a copy of the same sources has the same fingerprint", base["req"] == i1["fingerprint"], (base["req"], i1["fingerprint"]))
with open(os.path.join(copy_root, "production", "gates.py"), "a") as f: f.write("\n# corrected\n")
evaluator._cache.clear()
after = {k: evaluator.identity(t, copy_root)["fingerprint"] for k, t in (("req", req), ("smoke", smoke), ("play", play))}
check("identity: changing the production gate changes every check that it gates", all(after[k] != base[k] for k in base), (base, after))
with open(os.path.join(copy_root, "studio", "departments", "playcraft", "dept.py"), "a") as f: f.write("\n# corrected\n")
evaluator._cache.clear()
again = {k: evaluator.identity(t, copy_root)["fingerprint"] for k, t in (("req", req), ("smoke", smoke), ("play", play))}
check("identity: changing one department changes only that department's checks", again["play"] != after["play"] and again["smoke"] == after["smoke"] and again["req"] == after["req"], (after, again))
with open(os.path.join(copy_root, "production", "planner.py"), "a") as f: f.write("\n# scheduling, not measuring\n")
with open(os.path.join(copy_root, "production", "README.txt"), "w") as f: f.write("notes")
os.makedirs(os.path.join(copy_root, "production", "__pycache__"), exist_ok=True)
with open(os.path.join(copy_root, "production", "__pycache__", "x.py"), "w") as f: f.write("x")
evaluator._cache.clear()
check("identity: the planner, notes and caches are not the evaluator", evaluator.identity(req, copy_root)["fingerprint"] == again["req"])
evaluator._cache.clear()
now = evaluator.identity(req)
check("changed: same fingerprint → not changed", evaluator.changed(dict(now), req)[0] is False)
check("changed: another fingerprint → changed, and says from what to what", evaluator.changed({"name": now["name"], "fingerprint": "0" * 16}, req)[0] is True
      and now["fingerprint"] in evaluator.changed({"name": now["name"], "fingerprint": "0" * 16}, req)[2])
check("changed: no recorded identity → measured by an older GITCRAFT", evaluator.changed(None, req)[0] is True and "before evaluator identity was tracked" in evaluator.changed(None, req)[2])

# ---- a production with a failed product check and its open fix chain
p = engine.plan("Build a mobile-first arcade game called Pebble with sound, music and deployment", os.path.join(ws, "pebble"))
pid = p.get("production") or p.get("id")
prod = store.load(pid)
engine.decide(pid, answers={k["id"]: k["recommended"] for k in prod["decision_room"] if k.get("recommended")}); engine.decide(pid, approve=True)
CHK = "qa.request"


def fail_quality(prod, tid, ev, rnd_note="image without alt text"):
    """What _finish leaves after a gate failure: a finished attempt with the evaluator that measured it, the failure, the fix chain."""
    t = prod["tasks"][tid]
    t["attempts"].append({"n": len(t["attempts"]) + 1, "started": store.now(), "finished": store.now(), "status": "ok", "outcome": "quality", **({"evaluator": ev} if ev else {})})
    t.update(state=FAILED, failure="quality", error=f"requested accessibility: {rnd_note}", measured_fingerprint="fp-" + str(len(t["attempts"])),
             gate_results=[{"ok": False, "condition": "status_ok", "detail": rnd_note}], result={"status": "ok", "checks": [{"name": rnd_note, "ok": False}]})
    engine._remediate(prod, t, {"status": "ok", "checks": [{"name": rnd_note, "ok": False}]}, t["gate_results"])
    return t


with store.lock(prod):
    prod = store.load(pid)
    t = fail_quality(prod, CHK, evaluator.identity(prod["tasks"][CHK])); store.save(prod)
check("setup: the failed check opened a fix work order and a re-verification", {"fix.qa.request.r1", "qa.request.r1"} <= set(prod["tasks"]) and prod["tasks"][CHK].get("superseded_by") == "qa.request.r1")

# ---- prohibited: the same evaluator on the same project is a plain retry of a measured failure
msg = raises(lambda: engine.retry(pid, [CHK], "please run it again"))
check("refused: a measured failure with the same evaluator is never retried", msg and "never retried" in msg and "would measure the same thing again" in msg, msg)
prod = store.load(pid)
check("refused: nothing changed (still failed, fix order still open, no re-evaluation recorded)", prod["tasks"][CHK]["state"] == FAILED and prod["tasks"]["fix.qa.request.r1"]["state"] != SKIPPED
      and not prod["tasks"][CHK].get("reevaluations"))
check("refused: a reason is still required", raises(lambda: engine.retry(pid, [CHK], "")))

# ---- permitted: the evaluator that measured the failure is not the one installed now
with store.lock(prod):
    prod = store.load(pid)
    prod["tasks"][CHK]["attempts"][-1]["evaluator"] = {"name": "production.check_request", "fingerprint": "feedfacefeedface", "files": 20}; store.save(prod)
before = copy.deepcopy(store.load(pid)["tasks"][CHK])
engine.retry(pid, [CHK], "GITCRAFT's reader counted its own report as the product; fixed upstream")
prod = store.load(pid); t = prod["tasks"][CHK]
check("permitted: the check waits to be measured again (not passed, not failed)", t["state"] == PENDING, t["state"])
check("permitted: it is not converted: no result, no gate result until it runs", not t.get("result") and not t.get("gate_results"))
check("history: every earlier attempt is kept, with the evaluator that measured it", len(t["attempts"]) == len(before["attempts"]) and t["attempts"][-1].get("evaluator", {}).get("fingerprint") == "feedfacefeedface"
      and t["attempts"][-1].get("outcome") == "quality")
rv = (t.get("reevaluations") or [{}])[-1]
check("history: the re-evaluation records why, both evaluator identities and the previous result",
      rv.get("reason") and rv.get("evaluator_before", {}).get("fingerprint") == "feedfacefeedface" and rv.get("evaluator_after", {}).get("fingerprint") == evaluator.identity(t)["fingerprint"]
      and rv.get("previous", {}).get("error") == before["error"] and rv["previous"].get("gate_results") == before["gate_results"] and rv["previous"].get("measured_fingerprint") == before["measured_fingerprint"], rv)
check("history: the fix work order and re-verification it opened are closed, not deleted", prod["tasks"]["fix.qa.request.r1"]["state"] == SKIPPED and prod["tasks"]["qa.request.r1"]["state"] == SKIPPED
      and rv.get("closed") == ["fix.qa.request.r1", "qa.request.r1"], rv.get("closed"))
events = [json.loads(l) for l in open(os.path.join(prod["store"], "events.jsonl")) if l.strip()]
check("history: an evaluator_correction event names the task and both fingerprints", any(e.get("event") == "evaluator_correction" or e.get("type") == "evaluator_correction" or "evaluator_correction" in json.dumps(e) for e in events))
check("permitted: what waited behind the failed check waits again", all(prod["tasks"][d["id"]]["state"] == PENDING for d in prod["tasks"].values() if CHK in d["depends_on"] and d["kind"] != "agent" and not d.get("chain")))

# ---- the re-measurement decides: a pass comes only from a real result; a second failure opens a new, separate chain
with store.lock(prod):
    prod = store.load(pid); t = prod["tasks"][CHK]
    t["attempts"].append({"n": len(t["attempts"]) + 1, "started": store.now(), "t0": 0})
    engine._finish(prod, t, {"status": "ok", "checks": []}); store.save(prod)
prod = store.load(pid); t = prod["tasks"][CHK]
check("_finish: a finished attempt records the evaluator installed now", t["attempts"][-1].get("evaluator") == evaluator.identity(t), t["attempts"][-1])
check("_finish: the corrected evaluator's own measurement passes the check", t["state"] == PASSED, (t["state"], t.get("error")))
with store.lock(prod):
    prod = store.load(pid); fail_quality(prod, CHK, evaluator.identity(prod["tasks"][CHK]), "a real missing alt text"); store.save(prod)
prod = store.load(pid)
check("re-failure: a new fix chain with its own ids; the closed one is still on the record", {"fix.qa.request.e1.r1", "qa.request.e1.r1", "fix.qa.request.r1", "qa.request.r1"} <= set(prod["tasks"])
      and prod["tasks"]["fix.qa.request.r1"]["state"] == SKIPPED and prod["tasks"]["fix.qa.request.e1.r1"]["state"] in (PENDING, AWAITING_AGENT), sorted(k for k in prod["tasks"] if "qa.request" in k))
check("re-failure: measured by the current evaluator, so it is a product failure again: refused", raises(lambda: engine.retry(pid, [CHK], "once more")))

# ---- the latest measurement of a chain is the one to act on
with store.lock(prod):
    prod = store.load(pid)
    prod["tasks"][CHK]["attempts"][-1]["evaluator"] = {"name": "x", "fingerprint": "0" * 16}
    r1 = prod["tasks"]["qa.request.e1.r1"]; r1["attempts"].append({"n": 1, "outcome": "quality", "evaluator": {"name": "x", "fingerprint": "0" * 16}})
    r1.update(state=FAILED, failure="quality", error="still missing"); store.save(prod)
msg = raises(lambda: engine.retry(pid, [CHK], "evaluator changed"))
check("refused: an older result of the chain, when a later check measured the project after it (it names that check)", msg and "qa.request.e1.r1" in msg, msg)
engine.retry(pid, ["qa.request.e1.r1"], "evaluator changed")
check("permitted: the latest failed re-verification, when its evaluator changed", store.load(pid)["tasks"]["qa.request.e1.r1"]["state"] == PENDING)

# ---- legacy records and other kinds of failure
with store.lock(prod):
    prod = store.load(pid); fail_quality(prod, "qa.standards", None); store.save(prod)
engine.retry(pid, ["qa.standards"], "recorded by a GITCRAFT without evaluator identity")
prod = store.load(pid)
check("legacy: a failure recorded before identity was tracked can be measured again, and says so", prod["tasks"]["qa.standards"]["state"] == PENDING
      and "before evaluator identity was tracked" in prod["tasks"]["qa.standards"]["reevaluations"][-1]["why"])
with store.lock(prod):
    prod = store.load(pid); a = prod["tasks"]["audio.music"]
    a["attempts"].append({"n": 1, "outcome": "quality"}); a.update(state=FAILED, failure="quality", error="clipping"); store.save(prod)
msg = raises(lambda: engine.retry(pid, ["audio.music"], "evaluator changed"))
check("refused: a department's own output failing its gate is reworked by the department, not re-evaluated", msg and "only a QA or release check" in msg, msg)
with store.lock(prod):
    prod = store.load(pid); s = prod["tasks"]["qa.smoke"]
    s["attempts"].append({"n": 1, "outcome": "execution"}); s.update(state=FAILED, failure="execution", error="chromium did not start"); store.save(prod)
engine.retry(pid, ["qa.smoke"], "chromium is installed now")
check("unchanged: an execution failure is still retried as before, with no evaluator question", store.load(pid)["tasks"]["qa.smoke"]["state"] == PENDING and not store.load(pid)["tasks"]["qa.smoke"].get("reevaluations"))

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
