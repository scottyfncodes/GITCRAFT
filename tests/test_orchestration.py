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
check("v2: the code build waits only for the foundation (scaffold + identity)", T2["build"]["depends_on"] == ["foundation.scaffold", "foundation.identity"], T2["build"]["depends_on"])
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
check("v2: no required criterion is dropped or downgraded (same criteria measured, none made advisory)",
      {t.get("criterion") for t in T1.values()} == {t.get("criterion") for t in T2.values()}
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
for tid in ("foundation.scaffold", "foundation.identity"): engine._set(P, P["tasks"][tid], PASSED)
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

shutil.rmtree(ws, ignore_errors=True)
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
