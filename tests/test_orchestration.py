#!/usr/bin/env python3
"""Production orchestration, plan v2 (PR 1 of the orchestration overhaul): the dependency graph, transactional
integration, disjoint write ownership, the consolidated replace_assets approval, strict asset references, recovery,
and compatibility with v1 records and the review-only plan.

Fast and deterministic: no department runs. Integration and the gates are exercised for real on real files; the
engine's scheduling and approval logic on a real planned production record."""
import copy, hashlib, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-orch-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"), GITCRAFT_PRODUCTION_REPORT="0",
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import intake, planner, gates, engine, store, builtins, report
from production import PASSED, PENDING, NEEDS_APPROVAL, IN_PROGRESS, BLOCKED, AWAITING_AGENT
fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  [{str(detail)[:400]}]"), flush=True)
    fails += 0 if cond else 1


def tree(root):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds.sort()
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def upstream_of(T, tid, seen=None):
    seen = set() if seen is None else seen
    for d in T[tid]["depends_on"]:
        if d not in seen: seen.add(d); upstream_of(T, d, seen)
    return seen


DISC = {"project": {"exists": False}, "runtimes": {"studio": {"departments": []}}}
GAME = "Build a polished mobile platformer game called Ember Run with sound, music, three levels and an original visual identity"


def plan(prompt=GAME, version=2, **extra):
    spec = intake.parse(prompt); spec["project"]["path"] = os.path.join(ws, "p")
    for k, v in extra.items(): spec[k] = v
    return planner.build(spec, DISC, version=version), spec


# ---------------------------------------------------------------- 1. the graph: v1 unchanged, v2 restructured
p1, _ = plan(version=1); p2, _ = plan(version=2)
T1, T2 = p1["tasks"], p2["tasks"]
check("v1: unchanged graph (build waits for integrate.assets and the icon set; QA waits for build; no v2 tasks)",
      set(T1["build"]["depends_on"]) >= {"integrate.assets", "icon.derivatives"} and T1["qa.smoke"]["depends_on"] == ["build"]
      and not any(t in T1 for t in ("integrate.final", "build.wire")) and p1["plan_version"] == 1, T1["build"]["depends_on"])
check("v2: valid as built (no unknown dependency, no cycle, every request one its department accepts)", planner.validate(p2) == [], planner.validate(p2))
check("v2: the code build waits only for the foundation (scaffold + identity) and the creative direction it is held to",
      T2["build"]["depends_on"] == ["foundation.scaffold", "foundation.identity", "design.direction"], T2["build"]["depends_on"])
check("v2: the direction is decided before the identity and the build, and is an agent work order with a validated file",
      T2["design.direction"]["depends_on"] == ["foundation.scaffold"] and "design.direction" in T2["foundation.identity"]["depends_on"]
      and T2["design.direction"]["work_order"]["expected"][0]["validate"] == "direction", T2["design.direction"]["depends_on"])
check("v1: no direction task (v1 stays exactly what it was)", "design.direction" not in T1)
up = upstream_of(T2, "build")
check("v2: no asset, no icon step and no integration is upstream of the code build", not any(t.startswith(("audio.", "levels.", "icon.", "integrate.")) for t in up), sorted(up))
ship = [t for t in T2 if T2[t].get("ship")]
check("v2: the build consumes (never waits for) every shipped asset", sorted(T2["build"]["consumes"]) == sorted(ship))
check("v2: one integration per shipped task, depending only on it, measuring asset_integrity, one integration writer at a time",
      all(T2[f"integrate.{s}"]["depends_on"] == [s] and T2[f"integrate.{s}"]["criterion"] == "asset_integrity" and T2[f"integrate.{s}"]["resources"] == ["integration"]
          and T2[f"integrate.{s}"]["params"] == {"v2": True} for s in ship) and "integrate.assets" not in T2)
check("v2: integrate.final waits for every integration; build.wire for the build and the final integration",
      sorted(T2["integrate.final"]["depends_on"]) == sorted(f"integrate.{s}" for s in ship) and T2["build.wire"]["depends_on"] == ["build", "integrate.final"])
qa = [t for t in T2 if T2[t]["stage"] in ("qa", "release") and t != "trailer.title"]
check("v2: every QA and release task measures the final wired build (build.wire and integrate.final upstream)",
      all({"build.wire", "integrate.final"} <= upstream_of(T2, t) for t in qa), [t for t in qa if not {"build.wire", "integrate.final"} <= upstream_of(T2, t)])
check("v2: the icon choice is off the code path but on the release path (qa.icons and release depend on icon.select)",
      "icon.select" not in up and "icon.select" in upstream_of(T2, "qa.icons") and "icon.select" in upstream_of(T2, "release.report"))
check("v2: no required criterion is dropped or downgraded (every v1 criterion measured, none made advisory; v2 adds only Product QA's request_fulfilled)",
      {t.get("criterion") for t in T2.values()} - {t.get("criterion") for t in T1.values()} == {"request_fulfilled"}
      and {t.get("criterion") for t in T1.values()} <= {t.get("criterion") for t in T2.values()}
      and {t.get("criterion") for t in T1.values() if t.get("advisory")} == {t.get("criterion") for t in T2.values() if t.get("advisory")})
check("v2: qa.assets checks real references (strict), never the manifest", any(g.get("type") == "referenced" and g.get("strict") for g in T2["qa.assets"]["gate"]))
check("v2: the build work order builds on placeholders and leaves the icon and the manifest alone; build.wire wires both",
      any("placeholders" in i for i in T2["build"]["work_order"]["instructions"]) and not any("icons.snippet.json" in i for i in T2["build"]["work_order"]["instructions"])
      and any("icons.snippet.json" in i for i in T2["build.wire"]["work_order"]["instructions"]) and any(planner.MANIFEST in i for i in T2["build.wire"]["work_order"]["instructions"]))
pd, _ = plan(extra_tasks=[{"id": "design.game", "kind": "agent", "stage": "design", "title": "Game design", "depends_on": ["foundation.scaffold"],
                           "work_order": {"brief": "design", "expected": []}}])
check("v2: the design hook: a design-stage task becomes a dependency of the code build (PR 4)", "design.game" in pd["tasks"]["build"]["depends_on"], pd["tasks"]["build"]["depends_on"])
pb, _ = plan(backend={"provider": "postgres"})
TB = pb["tasks"]
check("v2: the database is off the code path (build uses a mock); backend.wire switches it after the approved provisioning, before wiring",
      "backend.provision" not in upstream_of(TB, "build") and TB["backend.wire"]["depends_on"] == ["backend.provision", "build"]
      and "backend.wire" in TB["build.wire"]["depends_on"] and TB["backend.provision"]["criterion"] == "backend", TB["build"]["depends_on"])
cyc = copy.deepcopy(p2); cyc["tasks"]["audio.music"]["depends_on"] = ["build"]
check("v2: a consumes edge that would close a cycle is refused", any("cycle" in x for x in planner.validate(cyc)), planner.validate(cyc))
bad = copy.deepcopy(p2); bad["tasks"]["build"]["consumes"] = ["nope"]
check("v2: consuming an unknown task is refused", any("unknown task nope" in x for x in planner.validate(bad)))
rv1, _ = plan("Run GITCRAFT: review this game", version=1, mode={"existing": True, "workflow": "review"})
rv2, _ = plan("Run GITCRAFT: review this game", version=2, mode={"existing": True, "workflow": "review"})
check("review-only: the same plan in v1 and v2 (measure, change nothing)",
      json.dumps(rv1["tasks"], sort_keys=True) == json.dumps(rv2["tasks"], sort_keys=True) and not any(t["kind"] == "agent" for t in rv2["tasks"].values()))

# ---------------------------------------------------------------- 2. transactional integration (real files)
proj = os.path.join(ws, "game"); os.makedirs(proj); src = os.path.join(ws, "dept"); os.makedirs(src)
open(os.path.join(proj, "index.html"), "w").write("<!doctype html><title>g</title>")
for n, body in (("jump.ogg", b"OggS-jump"), ("coin.ogg", b"OggS-coin")): open(os.path.join(src, n), "wb").write(body)
def up(tid, files, dest="$project/assets/audio"):
    return {"id": tid, "state": "passed", "ship": {"dest": dest, "roles": ["sfx"], "formats": ["ogg"]}, "license": "CC0-1.0",
            "outputs": [{"path": os.path.join(src, f), "role": "sfx", "format": "ogg", "sha256": builtins.sha256(os.path.join(src, f))} for f in files], "result": {}}
def ctx(u, out, **kw):
    os.makedirs(out, exist_ok=True)
    return dict({"prod": {"id": "p"}, "project": proj, "upstream": [u], "out_dir": out, "params": {"v2": True}, "replace_auth": {}}, **kw)

r = builtins.integrate(ctx(up("audio.sfx.jump", ["jump.ogg"]), os.path.join(ws, "t1")))
man = builtins.read_manifest(proj)["assets"]
check("integrate: committed, hash-verified, with its licence sidecar and an exact manifest entry",
      r["status"] == "ok" and open(os.path.join(proj, "assets/audio/jump.ogg"), "rb").read() == b"OggS-jump" and os.path.isfile(os.path.join(proj, "assets/audio/jump.ogg.license.json"))
      and man == {"assets/audio/jump.ogg": {"task": "audio.sfx.jump", "role": "sfx", "format": "ogg", "sha256": builtins.sha256(os.path.join(src, "jump.ogg"))}}
      and r["manifest_sha256"] == builtins.sha256(os.path.join(proj, planner.MANIFEST)), (r, man))
before = tree(proj)
r = builtins.integrate(ctx(up("audio.sfx.coin", ["coin.ogg"]), os.path.join(ws, "t2"), _fail_after=1))
check("integrate: a failure in the middle of the commit is rolled back — the project is byte-identical to its previous valid state",
      r["status"] == "failed" and "rolled back" in r["error"] and tree(proj) == before and not os.path.exists(os.path.join(ws, "t2", builtins.JOURNAL)), r.get("error"))
orig = builtins.integrate_recover
builtins.integrate_recover = lambda out: []   # a crash: nothing rolls back in the process itself
builtins.integrate(ctx(up("audio.sfx.coin", ["coin.ogg"]), os.path.join(ws, "t3"), _fail_after=1))
builtins.integrate_recover = orig
crashed = tree(proj) != before and os.path.exists(os.path.join(ws, "t3", builtins.JOURNAL))
done = builtins.integrate_recover(os.path.join(ws, "t3"))
check("recovery: an interrupted commit leaves a journal; integrate_recover restores the previous valid state", crashed and done and tree(proj) == before, done)
r = builtins.integrate(ctx(up("audio.sfx.coin", ["coin.ogg"]), os.path.join(ws, "t4")))
check("integrate: a second asset is added beside the first; the manifest lists both", r["status"] == "ok" and set(builtins.read_manifest(proj)["assets"]) == {"assets/audio/jump.ogg", "assets/audio/coin.ogg"})
os.makedirs(os.path.join(src, "x"), exist_ok=True); open(os.path.join(src, "x", "jump.ogg"), "wb").write(b"OggS-other")
other = {"id": "audio.sfx.other", "state": "passed", "ship": {"dest": "$project/assets/audio", "roles": ["sfx"]}, "result": {},
         "outputs": [{"path": os.path.join(src, "x", "jump.ogg"), "role": "sfx", "format": "ogg", "sha256": builtins.sha256(os.path.join(src, "x", "jump.ogg"))}]}
b2 = tree(proj); r = builtins.integrate(ctx(other, os.path.join(ws, "t5")))
check("integrate: another task's integrated file at the same path is a conflict — nothing is written", r["status"] == "failed" and r["failure"] == "conflict" and tree(proj) == b2, r.get("error"))
open(os.path.join(proj, "assets/audio/hit.ogg"), "wb").write(b"the project's own hit sound")
open(os.path.join(src, "hit.ogg"), "wb").write(b"OggS-hit")
b3 = tree(proj); r = builtins.integrate(ctx(up("audio.sfx.hit", ["hit.ogg"]), os.path.join(ws, "t6")))
check("integrate: replacing the project's own file asks for the consolidated approval, listing exactly that file and content — nothing written",
      r["status"] == "needs_approval" and r["consolidated"] and r["files"] == [{"file": "assets/audio/hit.ogg", "sha256": builtins.sha256(os.path.join(src, "hit.ogg")), "task": "audio.sfx.hit"}]
      and tree(proj) == b3, r)
r = builtins.integrate(ctx(up("audio.sfx.hit", ["hit.ogg"]), os.path.join(ws, "t7"), replace_auth={"assets/audio/hit.ogg": "0" * 64}))
check("integrate: an approval for different content does not authorise this overwrite", r["status"] == "needs_approval")
r = builtins.integrate(ctx(up("audio.sfx.hit", ["hit.ogg"]), os.path.join(ws, "t8"), replace_auth={"assets/audio/hit.ogg": builtins.sha256(os.path.join(src, "hit.ogg"))}))
check("integrate: the authorised overwrite proceeds and is recorded as a replacement", r["status"] == "ok" and r["replaced"] == ["assets/audio/hit.ogg"], r)
led = [m for d in ("t1", "t4", "t8") for m in json.load(open(os.path.join(ws, d, "integrated.json")))]
f = builtins.integrate_final({"project": proj, "integrated": led})
check("integrate_final: the ledger, the files and the manifest agree", f["status"] == "ok", f["checks"])
open(os.path.join(proj, "assets/audio/coin.ogg"), "wb").write(b"edited"); f = builtins.integrate_final({"project": proj, "integrated": led})
check("integrate_final: a changed integrated file fails it", f["status"] == "failed" and not f["checks"][0]["ok"])
shutil.copy(os.path.join(src, "coin.ogg"), os.path.join(proj, "assets/audio/coin.ogg"))
m = builtins.read_manifest(proj); m["assets"]["assets/audio/ghost.ogg"] = {"task": "x", "sha256": "1"}; json.dump(m, open(os.path.join(proj, planner.MANIFEST), "w"))
f = builtins.integrate_final({"project": proj, "integrated": led})
check("integrate_final: a manifest entry with no committed file fails it", f["status"] == "failed" and "ghost" in str(f["checks"][1]["detail"]))

# an existing project an earlier production made: the manifest it already carries is the project's, not this production's
projx = os.path.join(ws, "made-before"); os.makedirs(os.path.join(projx, "assets", "audio"))
open(os.path.join(projx, "index.html"), "w").write("<!doctype html><title>made before</title><script>new Audio('assets/audio/old.ogg')</script>")
open(os.path.join(projx, "assets/audio/old.ogg"), "wb").write(b"OggS-old")
was = {"assets/audio/old.ogg": {"task": "audio.sfx.old", "role": "sfx", "format": "ogg", "sha256": builtins.sha256(os.path.join(projx, "assets/audio/old.ogg"))}}
builtins._atomic_json(os.path.join(projx, planner.MANIFEST), {"schema": "gitcraft-assets/1", "owner": "integration", "assets": dict(was)})
inh = {k: {"task": v["task"], "sha256": v["sha256"]} for k, v in was.items()}
f = builtins.integrate_final({"project": projx, "integrated": [], "inherited": inh})
check("integrate_final: a project's earlier manifest, unchanged, passes a production that integrated nothing", f["status"] == "ok", f["checks"])
f = builtins.integrate_final({"project": projx, "integrated": []})
check("integrate_final: with no record of what was inherited it stays strict", f["status"] == "failed" and "old.ogg" in str(f["checks"][1]["detail"]))
r = builtins.integrate(ctx(up("audio.sfx.coin", ["coin.ogg"]), os.path.join(ws, "tx1"), project=projx)); ledx = json.load(open(os.path.join(ws, "tx1", "integrated.json")))
f = builtins.integrate_final({"project": projx, "integrated": ledx, "inherited": inh})
check("integrate_final: new assets beside inherited ones: the manifest lists both, and passes", r["status"] == "ok" and f["status"] == "ok"
      and set(builtins.read_manifest(projx)["assets"]) == {"assets/audio/old.ogg", "assets/audio/coin.ogg"}, f["checks"])
m = builtins.read_manifest(projx); keep = copy.deepcopy(m); m["assets"]["assets/audio/old.ogg"]["sha256"] = "0" * 64; json.dump(m, open(os.path.join(projx, planner.MANIFEST), "w"))
f = builtins.integrate_final({"project": projx, "integrated": ledx, "inherited": inh})
check("integrate_final: an inherited entry that was edited fails it", f["status"] == "failed" and f["checks"][1]["detail"] == ["assets/audio/old.ogg"])
m = copy.deepcopy(keep); del m["assets"]["assets/audio/old.ogg"]; json.dump(m, open(os.path.join(projx, planner.MANIFEST), "w"))
f = builtins.integrate_final({"project": projx, "integrated": ledx, "inherited": inh})
check("integrate_final: an inherited entry that was removed fails it", f["status"] == "failed" and f["checks"][1]["detail"] == ["assets/audio/old.ogg"])
json.dump(keep, open(os.path.join(projx, planner.MANIFEST), "w"))
check("expected manifest: a task integrated again replaces its inherited entries as a set (as integrate() does)",
      builtins.expected_manifest([{"dest_rel": "assets/audio/new.ogg", "sha256": "n", "task": "audio.sfx.old"}], inh) == {"assets/audio/new.ogg": "n"}
      and builtins.expected_manifest([], inh) == {"assets/audio/old.ogg": was["assets/audio/old.ogg"]["sha256"]} and builtins.expected_manifest([], None) == {})
# the same through the engine: planning records what the project carried, and the agent's submission is judged against it
projy = os.path.join(ws, "made-before-2"); shutil.copytree(projx, projy); os.remove(os.path.join(projy, "assets/audio/coin.ogg"))
builtins._atomic_json(os.path.join(projy, planner.MANIFEST), {"schema": "gitcraft-assets/1", "owner": "integration", "assets": dict(was)})
for extra in ("coin.ogg.license.json",):
    if os.path.exists(os.path.join(projy, "assets/audio", extra)): os.remove(os.path.join(projy, "assets/audio", extra))
fpy = engine.fingerprint(projy)
E = engine.plan("Add a pause menu to this existing game", projy); E = store.load(E["id"])
check("planning an existing project records the manifest it already carries, and writes nothing to it",
      E.get("inherited_assets") == inh and engine.fingerprint(projy) == fpy, E.get("inherited_assets"))
check("ownership: an untouched earlier manifest is no violation for a production that integrated nothing",
      engine._scope_violations(E, [os.path.join(projy, "index.html")]) == [], engine._scope_violations(E, [os.path.join(projy, "index.html")]))
check("ownership: submitting the earlier manifest is still refused", engine._scope_violations(E, [os.path.join(projy, planner.MANIFEST)]))
old_record = copy.deepcopy(E); del old_record["inherited_assets"]
check("a record planned before this was recorded recovers it from the Discovery baseline while the manifest is untouched",
      os.path.isfile(os.path.join(E["store"], "baseline.json")) and engine._scope_violations(old_record, []) == [] and old_record.get("inherited_assets") == inh,
      engine._scope_violations(copy.deepcopy({k: v for k, v in E.items() if k != "inherited_assets"}), []))
m = builtins.read_manifest(projy); m["assets"]["assets/audio/ghost.ogg"] = {"task": "x", "sha256": "1"}; json.dump(m, open(os.path.join(projy, planner.MANIFEST), "w"))
check("ownership: an edited earlier manifest is refused", any(planner.MANIFEST in v for v in engine._scope_violations(E, [])))
old_record = copy.deepcopy(E); del old_record["inherited_assets"]
check("an older record whose manifest no longer matches the baseline recovers nothing: it stays strict",
      any(planner.MANIFEST in v for v in engine._scope_violations(old_record, [])) and "inherited_assets" not in old_record)
# Tornado Hunter's state: integrate.final failed without measuring anything, everything below it was blocked, down to the
# agent's deploy two steps under the release report. Retrying the check must release the whole chain, the agent's task too
builtins._atomic_json(os.path.join(projy, planner.MANIFEST), {"schema": "gitcraft-assets/1", "owner": "integration", "assets": dict(was)})
R = engine.plan("Add a pause menu to this existing game and deploy it", projy); engine.decide(R["id"], approve=True); R = store.load(R["id"])
check("retry: the plan has the chain (integrate.final → QA → release.report → the agent's release.deploy)",
      R["tasks"]["release.deploy"]["kind"] == "agent" and R["tasks"]["release.deploy"]["depends_on"] == ["release.report"] and "integrate.final" in R["tasks"]["qa.smoke"]["depends_on"])
engine._set(R, R["tasks"]["foundation.scaffold"], PASSED)
fi = R["tasks"]["integrate.final"]; fi["attempts"] = [{"n": 1, "status": "failed", "outcome": "execution"}]; engine._set(R, fi, "failed", failure="execution")
for _ in range(6): engine._ready_tasks(R)
check("retry: reproduced: the failed check blocks everything below it, the deploy included",
      R["tasks"]["release.deploy"]["state"] == BLOCKED and R["tasks"]["release.deploy"]["blocked_by"] == ["release.report"] and R["tasks"]["qa.smoke"]["state"] == BLOCKED)
store.save(R); engine.retry(R["id"], ["integrate.final"], "GITCRAFT fix: an earlier manifest is inherited"); R = store.load(R["id"])
left = sorted(k for k, t in R["tasks"].items() if t["state"] == BLOCKED)
check("retry: the whole chain waits again, the agent's deploy too: nothing is left blocked",
      R["tasks"]["integrate.final"]["state"] == PENDING and R["tasks"]["release.deploy"]["state"] == PENDING and left == [], left)
own = R["tasks"]["release.deploy"]; engine._set(R, own, BLOCKED, reason="verification incomplete (not an application failure)")   # blocked for its own reason: no blocked_by
check("release: a task blocked for its own reason (no upstream named) is not released", engine._release_blocked(R) == 0 and own["state"] == BLOCKED)
engine._set(R, own, PENDING); engine._set(R, R["tasks"]["integrate.final"], "failed", failure="execution")
for _ in range(6): engine._ready_tasks(R)
check("release: a task whose upstream is still dead stays blocked", R["tasks"]["release.deploy"]["state"] == BLOCKED and R["tasks"]["qa.smoke"]["state"] == BLOCKED)
engine._set(R, R["tasks"]["integrate.final"], PASSED)
for _ in range(6): engine._ready_tasks(R)
check("release: once the upstream has passed, what it blocked waits again (a record left blocked heals on the next run)",
      not [k for k, t in R["tasks"].items() if t["state"] == BLOCKED], [k for k, t in R["tasks"].items() if t["state"] == BLOCKED])

# ---------------------------------------------------------------- 3. strict references: real loads, not filenames in comments or the manifest
rp = os.path.join(ws, "refs"); os.makedirs(rp)
integ = [{"dest_rel": "assets/audio/jump.ogg", "role": "sfx"}]
def ref(html, extra=None, strict=True):
    shutil.rmtree(rp); os.makedirs(rp); open(os.path.join(rp, "index.html"), "w").write(html)
    for n, t in (extra or {}).items(): open(os.path.join(rp, n), "w").write(t)
    return gates.evaluate({"gate": [{"type": "referenced", "strict": strict}]}, {}, {"project": rp, "integrated": integ})[0]["ok"]
check("strict: a real load counts", ref("<script>new Audio('assets/audio/jump.ogg')</script>"))
check("strict: a filename in an HTML comment does not count (v1, non-strict, still does: unchanged)",
      not ref("<!-- assets/audio/jump.ogg --><script>1</script>") and ref("<!-- assets/audio/jump.ogg -->", strict=False))
check("strict and v1: the asset manifest never counts as a reference",
      not ref("<p>x</p>", {planner.MANIFEST: '{"assets": {"assets/audio/jump.ogg": {}}}'}) and not ref("<p>x</p>", {planner.MANIFEST: '{"assets": {"assets/audio/jump.ogg": {}}}'}, strict=False))
check("strict: a JSON file the code loads counts; one nothing loads does not",
      ref("<script>fetch('sounds.json')</script>", {"sounds.json": '["assets/audio/jump.ogg"]'}) and not ref("<p>x</p>", {"sounds.json": '["assets/audio/jump.ogg"]'}))

# ---------------------------------------------------------------- 4. the engine: plan version, scheduling around approvals, ownership, recovery
pr = engine.plan(GAME, os.path.join(ws, "ember"))
P = store.load(pr.get("id") or pr.get("production"))
check("engine: a new production is plan_version 2", P["plan_version"] == 2 and "build.wire" in P["tasks"])
legacy = store.load(P["id"]); legacy.pop("plan_version"); engine._discover_and_plan(legacy)
check("engine: a record without plan_version (v1) is re-planned as v1, never silently converted", "integrate.assets" in legacy["tasks"] and "build.wire" not in legacy["tasks"])
for tid in ("foundation.scaffold", "design.direction", "foundation.identity"): engine._set(P, P["tasks"][tid], PASSED)
engine._set(P, P["tasks"]["icon.concepts"], PASSED); engine._set(P, P["tasks"]["icon.select"], NEEDS_APPROVAL, reason="a person chooses")
ready = [t["id"] for t in engine._ready_tasks(P)]
check("scheduling: the code build is ready while the icon choice waits for a person; unrelated assets run too",
      "build" in ready and any(t.startswith("audio.") for t in ready) and "icon.master" not in ready, ready)
check("scheduling: a person's wait is not a failure (nothing downstream of icon.select is blocked)", P["tasks"]["icon.master"]["state"] == PENDING
      and not any(t["state"] == BLOCKED for t in P["tasks"].values()))
# consolidated replace_assets: presented only when the overwrite set is complete
ship = [t for t in P["order"] if P["tasks"][t].get("ship")]
hold = ship[-1]   # one asset still being produced
for t in ship:
    if t != hold: engine._set(P, P["tasks"][t], PASSED)
a, b = f"integrate.{ship[1]}", f"integrate.{ship[2]}"
for tid, f, h in ((a, "assets/audio/a.ogg", "aa"), (b, "assets/audio/b.ogg", "bb")):
    P["tasks"][tid]["attempts"] = [{"n": 1, "started": "x"}]
    engine._finish(P, P["tasks"][tid], {"status": "needs_approval", "approval": "replace_assets", "consolidated": True, "files": [{"file": f, "sha256": h, "task": tid[len("integrate."):]}]})
store.save(P)
rq = engine.replace_assets_request(P)
check("replace_assets: not presented while an asset is still being produced (the set is incomplete)", rq and not rq["ready"] and hold in rq["waiting_on"], rq)
try: engine.approve(P["id"], "replace_assets"); inc = False
except ValueError as e: inc = "not complete" in str(e)
check("replace_assets: approving before the set is complete is refused", inc)
P = store.load(P["id"]); engine._set(P, P["tasks"][hold], PASSED)
for t in [x for x in P["order"] if P["tasks"][x]["kind"] == "builtin" and P["tasks"][x].get("action") == "integrate" and x not in (a, b)]: engine._set(P, P["tasks"][t], PASSED)
store.save(P)
st = engine.status(P)
check("replace_assets: one consolidated request listing every file, once the set is complete; no per-task prompts",
      st["replace_assets"]["ready"] and [f["file"] for f in st["replace_assets"]["files"]] == ["assets/audio/a.ogg", "assets/audio/b.ogg"]
      and sum("replace_assets" in n for n in st["next"]) == 1 and not any(n.startswith(f"person: approve or decline {a}") for n in st["next"]), st["next"])
engine.approve(P["id"], "replace_assets", note="ok")
P = store.load(P["id"])
check("replace_assets: approval authorises exactly the listed files and content, and releases both integrations",
      P["replace_assets"]["authorized"] == {"assets/audio/a.ogg": "aa", "assets/audio/b.ogg": "bb"} and P["tasks"][a]["state"] == PENDING and P["tasks"][b]["state"] == PENDING
      and P["replace_assets"]["history"][-1]["files"] and not engine.replace_assets_request(P))
engine._finish(P, P["tasks"][a], {"status": "needs_approval", "approval": "replace_assets", "consolidated": True, "files": [{"file": "assets/audio/a.ogg", "sha256": "a2", "task": ship[1]}]})
check("replace_assets: an unexpected overwrite (new content for an approved file) needs a new authorisation", engine.replace_assets_request(P)["files"] == [{"file": "assets/audio/a.ogg", "sha256": "a2", "task": ship[1]}])
# write ownership
proj2 = P["spec"]["project"]["path"]; os.makedirs(os.path.join(proj2, "assets", "audio"), exist_ok=True)
open(os.path.join(proj2, "assets/audio/jump.ogg"), "wb").write(b"j")
it = P["tasks"][f"integrate.{ship[0]}"]
it["result"] = {"integrated": [{"dest": os.path.join(proj2, "assets/audio/jump.ogg"), "dest_rel": "assets/audio/jump.ogg", "sha256": builtins.sha256(os.path.join(proj2, "assets/audio/jump.ogg")),
                                "role": "sfx", "format": "ogg", "task": ship[0], "replaced": False}]}
engine._set(P, it, PASSED)
builtins._atomic_json(os.path.join(proj2, planner.MANIFEST), {"schema": "gitcraft-assets/1", "owner": "integration", "assets": {"assets/audio/jump.ogg": {"task": ship[0], "sha256": it["result"]["integrated"][0]["sha256"]}}})
check("ownership: nothing integration-owned touched → no violation", engine._scope_violations(P, [os.path.join(proj2, "index.html")]) == [])
check("ownership: submitting an integration-owned file is refused", engine._scope_violations(P, [os.path.join(proj2, planner.MANIFEST)]))
open(os.path.join(proj2, "assets/audio/jump.ogg"), "wb").write(b"agent edit")
check("ownership: an integrated file changed by someone else is refused", any("changed after integration" in v for v in engine._scope_violations(P, [])))
open(os.path.join(proj2, "assets/audio/jump.ogg"), "wb").write(b"j")
m = builtins.read_manifest(proj2); m["assets"]["x.ogg"] = {"sha256": "1"}; json.dump(m, open(os.path.join(proj2, planner.MANIFEST), "w"))
check("ownership: an edited asset manifest is refused", any(planner.MANIFEST in v for v in engine._scope_violations(P, [])))
# recovery of an interrupted integration through the engine
iv = P["tasks"][f"integrate.{ship[3]}"]; d = store.task_dir(P, iv["id"]); os.makedirs(d, exist_ok=True)
victim = os.path.join(proj2, "assets", "audio", "victim.ogg"); open(victim, "wb").write(b"half-committed")
json.dump({"status": "committing", "entries": [{"dest": victim, "backup": None, "staged": None}]}, open(os.path.join(d, builtins.JOURNAL), "w"))
engine._set(P, iv, IN_PROGRESS); iv["attempts"] = [{"n": 1, "started": "x"}]
engine._recover(P)
check("recovery: the engine rolls back an interrupted integration and runs it again", not os.path.exists(victim) and iv["state"] == PENDING
      and not os.path.exists(os.path.join(d, builtins.JOURNAL)))

# ---------------------------------------------------------------- 5. PR 2: optional criteria (D3/D4), unavailable capabilities, routing to owners (D5)
from production import lifecycle, verification
POL = "Build a polished mobile platformer game called Ember Run with three levels"
sp = intake.parse(POL)
imp = intake.implied(sp)
check("criteria: every one carries required + source; implied extras are exactly what GITCRAFT added (sound, music, identity), all required by default",
      imp == {"asset_sfx", "asset_music", "asset_identity"} and all(c["required"] for c in sp["acceptance"])
      and {c["id"]: c["source"] for c in sp["acceptance"]}["asset_levels"] == "stated" and {c["id"]: c["source"] for c in sp["acceptance"]}["loads_everywhere"] == "standard", imp)
so = intake.parse(POL, overrides={"optional_criteria": ["asset_music", "asset_levels", "loads_everywhere"]})
req = {c["id"]: c["required"] for c in so["acceptance"]}
check("criteria: only an implied extra can be made optional; a stated or standard one stays required and the request is refused (never silent)",
      req["asset_music"] is False and req["asset_levels"] and req["loads_everywhere"] and so["optional_refused"] == ["asset_levels", "loads_everywhere"], (req, so["optional_refused"]))
room = {d["id"]: d for d in lifecycle.decisions(sp, DISC)}
check("Decision Room (D3): an 'extras' decision lists the implied extras, recommended required; 'optional' sets exactly them",
      room["extras"]["recommended"] == "required" and room["extras"]["sets"]["optional"] == {"optional_criteria": sorted(imp)} and room["extras"]["sets"]["required"] == {"optional_criteria": []})
check("Decision Room: no extras decision when nothing was implied", "extras" not in {d["id"] for d in lifecycle.decisions(intake.parse("Build a mobile platformer game called Ember Run with sound, music, an original visual identity and three levels"), DISC)})
check("blueprint: making a criterion optional after approval is a material change (needs a person); none vs an empty list is not",
      "optional_criteria" in lifecycle.material(sp, so) and lifecycle.material({k: v for k, v in sp.items() if k != "optional_criteria"}, sp) == [])
spo = intake.parse(POL, overrides={"optional_criteria": ["asset_music"]}); spo["project"]["path"] = os.path.join(ws, "p")
po = planner.build(spo, DISC, version=2); TO = po["tasks"]
check("graph: an optional asset's integration settles the final integration (never required); required ones stay hard dependencies",
      planner.validate(po) == [] and "integrate.audio.music" not in TO["integrate.final"]["depends_on"] and TO["integrate.final"]["settles"] == ["integrate.audio.music"]
      and TO["audio.music"].get("optional") and "integrate.levels.1" in TO["integrate.final"]["depends_on"]
      and TO["integrate.audio.music"]["criterion"] == "asset_music" and TO["integrate.levels.1"]["criterion"] == "asset_integrity", (TO["integrate.final"]["depends_on"], TO["integrate.final"].get("settles")))
bad = copy.deepcopy(po); bad["tasks"]["integrate.final"]["settles"] = ["nope"]
check("graph: a settles edge to an unknown task is refused", any("settles on an unknown task" in x for x in planner.validate(bad)))
bad = copy.deepcopy(po); bad["tasks"]["integrate.audio.music"]["depends_on"].append("integrate.final")
check("graph: a settles edge that closes a cycle is refused", any("cycle" in x for x in planner.validate(bad)), planner.validate(bad))

pr = engine.plan(POL, os.path.join(ws, "opt"), {"optional_criteria": ["asset_music"]}); Q = store.load(pr.get("id") or pr.get("production"))
for tid in Q["order"]:
    t = Q["tasks"][tid]
    if tid not in ("integrate.final", "build.wire", "audio.music", "integrate.audio.music") and t["stage"] in ("foundation", "production", "integration"): engine._set(Q, t, PASSED)
check("readiness: the final integration waits while the optional asset is still being made", "integrate.final" not in [t["id"] for t in engine._ready_tasks(Q)])
engine._set(Q, Q["tasks"]["audio.music"], BLOCKED, unavailable=True, reason="music runtime not installed")
ready = [t["id"] for t in engine._ready_tasks(Q)]
check("readiness: an unavailable optional asset (its integration blocked) does not block the final integration",
      Q["tasks"]["integrate.audio.music"]["state"] == BLOCKED and "integrate.final" in ready, (Q["tasks"]["integrate.audio.music"]["state"], ready))
for tid in Q["order"]:
    if Q["tasks"][tid]["state"] not in (BLOCKED,) and tid not in ("release.deploy",): engine._set(Q, Q["tasks"][tid], PASSED)
acc = {a["id"]: a for a in report.acceptance(Q)}
rs = verification.release_summary(Q)
check("report (D4): the optional, unavailable asset is optional_missing; the verdict is READY and the release summary lists it, verification complete",
      acc["asset_music"]["status"] == "optional_missing" and report.verdict(report.acceptance(Q)).startswith("READY") and rs["optional_not_delivered"][0]["criterion"] == "asset_music"
      and rs["verification_complete"] and "## Optional, not delivered" in report.markdown(Q), (acc["asset_music"]["status"], report.verdict(report.acceptance(Q)), rs["release_status"]))
R = store.load(Q["id"]); R["spec"]["acceptance"] = [dict(c, required=True) if c["id"] == "asset_music" else c for c in R["spec"]["acceptance"]]
for tid in R["order"]:
    if R["tasks"][tid]["state"] != BLOCKED and tid != "release.deploy": engine._set(R, R["tasks"][tid], PASSED)
engine._set(R, R["tasks"]["audio.music"], BLOCKED, unavailable=True, reason="music runtime not installed")
accR = {a["id"]: a for a in report.acceptance(R)}
rsR = verification.release_summary(R)
check("report: a REQUIRED criterion whose department is unavailable is 'unavailable' → INCOMPLETE (never READY, never NOT READY as a defect)",
      accR["asset_music"]["status"] == "unavailable" and report.verdict(report.acceptance(R)) == "INCOMPLETE" and any(u["criterion"] == "asset_music" for u in rsR["unverified"]),
      (accR["asset_music"]["status"], report.verdict(report.acceptance(R))))

# routing (D5)
pr = engine.plan(POL, os.path.join(ws, "route")); S = store.load(pr.get("id") or pr.get("production"))
lvl = S["tasks"]["levels.1"]; lvl["attempts"] = [{"n": 1, "started": "x"}]
fail = {"status": "failed", "checks": [{"name": "the level is solvable", "ok": False}], "outputs": [{"path": "/x.json", "role": "level_data", "format": "json"}]}
engine._finish(S, lvl, json.loads(json.dumps(fail)))
r1 = S["tasks"].get("levels.1.r1")
check("routing: a department's own failed gate goes back to that department (re-run, seed varied deterministically), not to the agent",
      r1 and r1["department"] == "levelcraft" and r1["params"]["seed"] == (lvl["params"].get("seed") or 0) + engine.REWORK_SEED and r1["routed_to"] == lvl["owner"]
      and "own output failed its gate" in r1["routed_because"] and lvl["superseded_by"] == "levels.1.r1" and not any(k.startswith("fix.levels") for k in S["tasks"]), r1)
check("routing: the asset's integration now waits for the re-run (eff), not for the failed attempt", engine.eff(S, "levels.1")["id"] == "levels.1.r1")
r1["attempts"] = [{"n": 1, "started": "x"}]; engine._finish(S, r1, json.loads(json.dumps(fail)))
r2 = S["tasks"]["levels.1.r2"]; r2["attempts"] = [{"n": 1, "started": "x"}]; engine._finish(S, r2, json.loads(json.dumps(fail)))
check("routing: bounded — after max_rounds (2) re-runs a REQUIRED criterion is escalated to a person; no third automatic re-run",
      "levels.1.r3" not in S["tasks"] and S["tasks"]["escalate.levels.1"]["state"] == NEEDS_APPROVAL and S["tasks"]["escalate.levels.1"]["origin"] in ("levels.1.r2",), list(S["tasks"])[-4:])
check("escalation: a person's wait, not a failure — unrelated tasks still schedule", "foundation.scaffold" in [t["id"] for t in engine._ready_tasks(S)])
store.save(S); engine.approve(S["id"], "escalate.levels.1", note="try once more")
S = store.load(S["id"])
check("escalation approved: exactly one more re-run, recorded as a person's decision; the escalation itself is not a pass of the criterion",
      "levels.1.r3" in S["tasks"] and S["tasks"]["escalate.levels.1"]["state"] == PASSED and S["tasks"]["escalate.levels.1"]["criterion"] is None
      and engine.eff(S, "levels.1")["id"] == "levels.1.r3")
pr = engine.plan(POL, os.path.join(ws, "route2"), {"optional_criteria": ["asset_music"]}); U = store.load(pr.get("id") or pr.get("production"))
mus = U["tasks"]["audio.music"]
for n in range(3):
    t = engine.eff(U, "audio.music"); t["attempts"] = [{"n": 1, "started": "x"}]
    engine._finish(U, t, {"status": "failed", "checks": [{"name": "loops cleanly", "ok": False}], "outputs": [{"path": "/m.ogg", "role": "music", "format": "ogg"}]})
check("routing: an OPTIONAL criterion is not escalated after its rounds — recorded as not delivered (no approval bottleneck)",
      "escalate.audio.music" not in U["tasks"] and any("optional not delivered: asset_music" in d for d in U["decisions"]) and "audio.music.r3" not in U["tasks"])
# QA finding a defective department file → that department, re-integration, re-verification
pr = engine.plan(POL, os.path.join(ws, "route3")); V = store.load(pr.get("id") or pr.get("production"))
for tid in V["order"]:
    if V["tasks"][tid]["stage"] in ("foundation", "production"): engine._set(V, V["tasks"][tid], PASSED)
iv = V["tasks"]["integrate.audio.sfx.jump"]
iv["result"] = {"integrated": [{"dest": "/p/assets/audio/jump.ogg", "dest_rel": "assets/audio/jump.ogg", "sha256": "a", "role": "sfx", "format": "ogg", "task": "audio.sfx.jump", "replaced": False}]}
engine._set(V, iv, PASSED)
qa_ = V["tasks"]["qa.assets"]; qa_["attempts"] = [{"n": 1, "started": "x"}]
engine._finish(V, qa_, {"status": "failed", "checks": [{"name": "3 assets open and validate", "ok": False, "detail": [{"path": "audio/jump.ogg", "ok": False, "error": "truncated"}]}],
                         "outputs": [{"path": "/r.json", "role": "report", "format": "json"}]})
check("routing: qa.assets finding a defective file goes to the department that made it (AudioCraft re-run → re-integration → qa.assets again); no agent fix",
      "audio.sfx.jump.r1" in V["tasks"] and V["tasks"]["integrate.audio.sfx.jump.r1"]["depends_on"] == ["audio.sfx.jump"] and V["tasks"]["qa.assets.r1"]["depends_on"] == ["integrate.audio.sfx.jump.r1"]
      and qa_["superseded_by"] == "qa.assets.r1" and V["tasks"]["audio.sfx.jump.r1"]["routed_to"] == "Studio · audiocraft" and not any(k.startswith("fix.qa.assets") for k in V["tasks"]),
      [k for k in V["tasks"] if ".r1" in k])
W = store.load(V["id"]); qw = W["tasks"]["qa.assets"]; qw.pop("superseded_by", None); qw["state"] = PENDING; qw["attempts"] = [{"n": 1, "started": "x"}]
engine._finish(W, qw, {"status": "failed", "checks": [{"name": "assets open", "ok": False, "detail": [{"path": "audio/handmade.ogg", "ok": False}]}], "outputs": [{"path": "/r", "role": "report"}]})
check("routing: a defective file no department produced is the agent's (fix work order, routed and recorded)",
      W["tasks"]["fix.qa.assets.r1"]["routed_to"] == "agent" and "audio.sfx.jump.r1" not in W["tasks"])
X = store.load(V["id"]); X["plan_version"] = 1; lv = X["tasks"]["levels.2"]; lv["attempts"] = [{"n": 1, "started": "x"}]
engine._finish(X, lv, json.loads(json.dumps(fail)))
check("v1 records: unchanged — a department's failed gate is not re-routed (no rework task)", "levels.2.r1" not in X["tasks"] and lv["state"] == "failed")
def rework_of(folder):
    p_ = engine.plan(POL, os.path.join(ws, folder)); Z = store.load(p_.get("id") or p_.get("production")); z = Z["tasks"]["levels.1"]; z["attempts"] = [{"n": 1, "started": "x"}]
    engine._finish(Z, z, json.loads(json.dumps(fail)))
    r = Z["tasks"]["levels.1.r1"]
    return json.dumps({k: r[k] for k in ("id", "params", "depends_on", "department", "action", "routed_to", "routed_because")}, sort_keys=True), Z["order"].index("levels.1.r1")
check("deterministic: the same failure on two identical productions produces the same rework (id, params, deps, owner, position)",
      rework_of("det1") == rework_of("det2"))

shutil.rmtree(ws, ignore_errors=True)
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
