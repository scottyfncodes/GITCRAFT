#!/usr/bin/env python3
"""Layered QA (orchestration PR 3): department QA before hand-off, integration QA of the assembled product, Product QA
against the request. Every failure goes through the one remediation path (PR 2: owner, optionality, bounded rounds,
escalation); the verdict stays the acceptance criteria's; suggestions and unrequested additions never block.

Fast and deterministic: no department runs. Product QA runs for real on real project files; the engine's routing,
rounds and verdicts run on real planned production records."""
import copy, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-lqa-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"), GITCRAFT_PRODUCTION_REPORT="0",
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import intake, planner, gates, engine, store, report, qa, verification, builtins
from production import PASSED, PENDING, NEEDS_APPROVAL, BLOCKED, FAILED
fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  [{str(detail)[:500]}]"), flush=True)
    fails += 0 if cond else 1


DISC = {"project": {"exists": False}, "runtimes": {"studio": {"departments": []}}}
GAME = "Build a polished mobile platformer game called Ember Run with three levels"
APP = "Build a mobile habit tracker app called Streakly with user accounts and sound effects"


def new(prompt, folder, overrides=None):
    p = engine.plan(prompt, os.path.join(ws, folder), overrides)
    return store.load(p.get("id") or p.get("production"))


def finish(P, tid, res):
    t = engine.eff(P, tid); t["attempts"] = [{"n": len(t["attempts"]) + 1, "started": "x"}]
    engine._finish(P, t, json.loads(json.dumps(res)))
    return t


def pass_all(P, keep=()):
    for tid in P["order"]:
        t = P["tasks"][tid]
        if tid in keep or t.get("superseded_by") or t["state"] in (BLOCKED, NEEDS_APPROVAL) or tid == "release.deploy": continue
        engine._set(P, t, PASSED)


def F(P, task=None, layer=None):
    return [f for f in qa.findings(P) if (task is None or f["task"] == task) and (layer is None or f["layer"] == layer)]


# ---------------------------------------------------------------- 1. the plan: three layers, v2 only
sp = intake.parse(GAME); sp["project"]["path"] = os.path.join(ws, "p")
p1 = planner.build(copy.deepcopy(sp), DISC, version=1); p2 = planner.build(copy.deepcopy(sp), DISC, version=2)
T1, T2 = p1["tasks"], p2["tasks"]
check("plan v2: Product QA (qa.request) measures request_fulfilled after the final wired build; the regression and the release wait for it",
      T2["qa.request"]["criterion"] == "request_fulfilled" and T2["qa.request"]["depends_on"] == ["build.wire"] and "qa.request" in T2["release.regression"]["depends_on"]
      and "qa.request" in T2["release.report"]["depends_on"] and planner.validate(p2) == [], T2["qa.request"]["depends_on"])
ship = [t for t in T2.values() if t["stage"] == "production" and (t.get("ship") or {}).get("roles")]
check("plan v2: department QA — every shipping department task checks its own deliverables (ship roles + formats) before hand-off",
      ship and all(any(g["type"] == "deliverables" and g["roles"] == t["ship"]["roles"] and g.get("formats") == t["ship"].get("formats") for g in t["gate"]) for t in ship),
      [t["id"] for t in ship if not any(g["type"] == "deliverables" for g in t["gate"])])
check("backward compatibility: a v1 plan gets neither qa.request nor the deliverables gate (byte-identical behaviour for old records)",
      "qa.request" not in T1 and not any(g["type"] == "deliverables" for t in T1.values() for g in t["gate"] or []))
lay = {tid: qa.layer_of(t) for tid, t in T2.items()}
check("layers: deliverables are department QA, integration and the assembled-build checks are integration QA, request/features/evaluators are product QA",
      lay["audio.sfx.jump"] == "department" and lay["levels.1"] == "department" and lay["build"] == "department" and lay["build.wire"] == "department"
      and lay["integrate.levels.1"] == "integration" and lay["integrate.final"] == "integration" and lay["qa.assets"] == "integration" and lay["qa.smoke"] == "integration"
      and lay["qa.request"] == "product" and lay["qa.playcraft"] == "product" and lay["release.regression"] == "product" and lay["release.report"] is None, lay)
check("layers: every check in a QA layer carries a criterion or is advisory — no QA runs without deciding something",
      all(t.get("criterion") or t.get("advisory") for tid, t in T2.items() if lay[tid] in ("integration", "product")),
      [tid for tid, t in T2.items() if lay[tid] in ("integration", "product") and not (t.get("criterion") or t.get("advisory"))])
P = new(GAME, "g1")
crit = {c["id"]: c for c in P["spec"]["acceptance"]}
check("criterion: request_fulfilled is added only because a task measures it, required, and cannot be made optional",
      crit["request_fulfilled"]["required"] and crit["request_fulfilled"]["source"] == "standard" and not P["warnings"]
      and new(GAME, "g1b", {"optional_criteria": ["request_fulfilled"]})["spec"]["optional_refused"] == ["request_fulfilled"])
L1 = store.load(P["id"]); L1["plan_version"] = 1; L1["tasks"] = {}; L1["order"] = []
L1 = engine._discover_and_plan(L1)
check("backward compatibility: a v1 record re-planned keeps the v1 graph and gets no request_fulfilled criterion",
      "qa.request" not in L1["tasks"] and "request_fulfilled" not in {c["id"] for c in L1["spec"]["acceptance"]})

# ---------------------------------------------------------------- 2. Product QA on real project files
proj = os.path.join(ws, "prod"); os.makedirs(proj)
def page(html, js=""):
    shutil.rmtree(proj); os.makedirs(proj)
    open(os.path.join(proj, "index.html"), "w").write(html)
    if js: open(os.path.join(proj, "game.js"), "w").write(js)
def rq(params, integrated=()):
    return {c["name"]: c for c in qa.evaluate_request(proj, params, list(integrated))}
GOOD = ("<!doctype html><html lang=en><head><meta name=viewport content='width=device-width'><title>Streakly</title></head>"
        "<body><h1>Streakly</h1><form><input type=password></form><script src=game.js></script></body></html>")
page(GOOD, "const s = new Audio('assets/audio/tap.ogg'); el.addEventListener('pointerdown', () => s.play())")
pa = qa.params_for(intake.parse(APP))
c = rq(pa)
check("Product QA: requested features are read from the stated request (accounts, sound, mobile), never from a model",
      set(pa["requested"]) == {"accounts", "sound", "mobile"}, pa["requested"])
check("Product QA (success): every requested feature shows in the build; no blocker, no advisory",
      all(x["category"] == verification.PASS for x in c.values()) and verification.status_of(list(c.values())) == "ok", [k for k, x in c.items() if x["category"] != "pass"])
page(GOOD.replace("<input type=password>", ""), "el.addEventListener('pointerdown', go)")
c = rq(pa)
bad = [x for x in c.values() if x["category"] == verification.BLOCKER]
check("Product QA (failure): a missing requested feature is an objective BLOCKER, named with what is missing (sound; accounts)",
      {x["feature"] for x in bad} == {"sound", "accounts"} and all("missing requested feature" in x["detail"] for x in bad), [(x["name"], x["detail"]) for x in bad])
page("<!doctype html><html lang=en><meta name=viewport content=x><title>Other</title><p>lorem ipsum</p><input type=password>", "new Audio('a.ogg'); onpointerdown=f")
c = rq({"title": "Streakly", "deliverable": "app", "requested": ["mobile"], "sound_planned": False, "entry": "index.html"})
adv = {x["kind"] for x in c.values() if x["category"] == verification.ADVISORY}
check("Product QA: unrequested additions (unasked audio, a password field without accounts) and coherence notes (name, unfinished text) are ADVISORY, never blockers",
      adv == {"unrequested", "suggestion"} and not any(x["category"] == verification.BLOCKER for x in c.values()) and verification.status_of(list(c.values())) == "ok"
      and sum(1 for x in c.values() if x["kind"] == "unrequested") == 2 and sum(1 for x in c.values() if x["kind"] == "suggestion") == 2, sorted(c))
check("Product QA: an extra GITCRAFT implied ('polished' sound) is not a request — never a missing-feature blocker",
      "sound" not in qa.requested(intake.parse(GAME)) and "sound" in qa.requested(intake.parse(GAME + " with sound effects")))
page("<!doctype html><html><meta name=viewport content=x><title>A</title><img src=a.png>")
c = rq({"title": "A", "deliverable": "site", "requested": ["accessibility"], "entry": "index.html"})
check("Product QA: requested accessibility → page language and alt text are objective checks",
      {x["feature"] for x in c.values() if x["category"] == verification.BLOCKER} == {"accessibility"}
      and sum(1 for x in c.values() if x["category"] == verification.BLOCKER) == 2)
pal = os.path.join(proj, "palette.json"); json.dump({"primary": "#ff5500", "accent": "#00aaff"}, open(pal, "w"))
page("<!doctype html><title>A</title><style>body{color:#123456}</style>")
json.dump({"primary": "#ff5500", "accent": "#00aaff"}, open(pal, "w"))
c = rq({"title": "A", "deliverable": "site", "requested": [], "identity": True, "entry": "index.html"}, [{"dest": pal, "dest_rel": "palette.json"}])
check("Product QA: coherence — an identity palette the styles never use is a suggestion, not a blocker",
      any(x["kind"] == "suggestion" and "palette" in x["name"] for x in c.values()) and verification.status_of(list(c.values())) == "ok")
page("<!doctype html><title></title>")
c = rq({"title": "A", "requested": [], "entry": "index.html"})
check("Product QA: an unnamed entry page is objective (BLOCKER); a missing entry page stops the check with one BLOCKER",
      c["request: the entry page names the product (<title>)"]["category"] == verification.BLOCKER
      and [x["category"] for x in qa.evaluate_request(os.path.join(ws, "nope"), {"requested": ["sound"]})] == [verification.BLOCKER])

# ---------------------------------------------------------------- 3. routing through PR 2's machinery (one path, bounded)
APPP = new(APP, "a1")
out = os.path.join(ws, "rq"); os.makedirs(out)
page(GOOD.replace("<input type=password>", ""), "")
res = qa.check_request({"project": proj, "params": APPP["tasks"]["qa.request"]["params"], "out_dir": out, "integrated": []})
check("check_request: a measured result with its evidence file (status failed, categorised checks, report output)",
      res["status"] == "failed" and os.path.isfile(res["outputs"][0]["path"]) and res["summary"]["blocker"] == 2 and gates.classify(res) == "quality")
t = finish(APPP, "qa.request", res)
fx = APPP["tasks"].get("fix.qa.request.r1")
check("product failure → the agent (code): one fix work order with the missing features, then qa.request again; no department rework",
      t["state"] == FAILED and fx and fx["routed_to"] == "agent" and APPP["tasks"]["qa.request.r1"]["reverifies"] == "qa.request"
      and any("missing requested feature: sound" in x for x in fx["work_order"]["findings"]) and not any(k.endswith(".r1") and k.startswith("audio") for k in APPP["tasks"]))
f = F(APPP, "qa.request")[0]
check("finding: layer, criterion, severity, owner, routed to, evidence, resolution and retry status are all reported",
      f["layer"] == "product" and f["criterion"] == "request_fulfilled" and f["required"] and f["severity"] == "blocker" and f["owner"] == "Production Director"
      and f["routed_to"] == "agent" and any("missing requested feature" in e for e in f["evidence"]) and f["status"].startswith("being fixed") and f["retry"].startswith("1/2"), f)
mr = APPP["spec"]["quality"].get("max_rounds", 2)
for n in range(mr): finish(APPP, "qa.request", res)
last = engine.eff(APPP, "qa.request")
f = F(APPP, "qa.request")[0]
check("retry exhaustion (agent): after max_rounds the chain stops — no further fix, the finding reads exhausted, the verdict is NOT READY",
      last.get("exhausted") and f"fix.qa.request.r{mr + 1}" not in APPP["tasks"] and "exhausted" in f["status"] and "exhausted" in f["retry"]
      and report.verdict(report.acceptance(APPP)) == "NOT READY", (f, [k for k in APPP["tasks"] if "qa.request" in k]))
page(GOOD, "new Audio('x.ogg'); onpointerdown = f")
ok = qa.check_request({"project": proj, "params": APPP["tasks"]["qa.request"]["params"], "out_dir": out, "integrated": []})
B = new(APP, "a2"); finish(B, "qa.request", res); finish(B, "qa.request", ok)
f = F(B, "qa.request")[0]
check("resolution: when the re-verification passes, the finding is resolved (with its round) and drops out of the open list",
      engine.eff(B, "qa.request")["state"] == PASSED and f["status"] == "resolved (round 1)" and not any(x["task"] == "qa.request" for x in engine._qa_view(B)["findings"]), f)

# department QA: a department that ran 'ok' but produced nothing shippable fails its own gate, and goes back to it
G = new(GAME, "g2")
wav = os.path.join(ws, "jump.wav"); open(wav, "wb").write(b"RIFF")
t = finish(G, "audio.sfx.jump", {"status": "ok", "checks": [], "outputs": [{"path": wav, "role": "sfx", "format": "wav"}]})
r1 = G["tasks"].get("audio.sfx.jump.r1")
check("department failure: an ok result with no shippable deliverable (wav, ship wants ogg) fails department QA and goes back to AudioCraft (seed varied)",
      t["state"] == FAILED and any(g["condition"].startswith("department QA") and not g["ok"] for g in t["gate_results"]) and r1 and r1["routed_to"] == "Studio · audiocraft"
      and r1["params"]["seed"] == engine.REWORK_SEED, t.get("gate_results"))
ogg = os.path.join(ws, "jump.ogg"); open(ogg, "wb").write(b"OggS")
check("department QA: the deliverables gate passes on a validated output with the ship role and format",
      all(g["ok"] for g in gates.evaluate(G["tasks"]["audio.sfx.jump"], {"status": "ok"}, {"outputs": [{"path": ogg, "role": "sfx", "format": "ogg"}]})))
f = F(G, "audio.sfx.jump")[0]
check("finding (department): owner and route are the department's, never the agent's",
      f["layer"] == "department" and f["routed_to"] == "Studio · audiocraft" and f["owner"] == "Studio · audiocraft" and f["criterion"] == "asset_sfx", f)
for n in range(2): finish(G, "audio.sfx.jump", {"status": "ok", "checks": [], "outputs": [{"path": wav, "role": "sfx", "format": "wav"}]})
f = F(G, "audio.sfx.jump")[0]
check("retry exhaustion (department): two re-runs, then a person decides (escalation), never a third automatic run",
      "audio.sfx.jump.r3" not in G["tasks"] and G["tasks"]["escalate.audio.sfx.jump"]["state"] == NEEDS_APPROVAL and f["status"] == "escalated: waiting for a person"
      and f["retry"] == "escalated to a person", f)

# integration failure: a defective integrated file → its department; an unwired asset → the agent
V = new(GAME, "g3")
for tid in V["order"]:
    if V["tasks"][tid]["stage"] in ("foundation", "production"): engine._set(V, V["tasks"][tid], PASSED)
iv = V["tasks"]["integrate.audio.sfx.jump"]
iv["result"] = {"integrated": [{"dest": "/p/assets/audio/jump.ogg", "dest_rel": "assets/audio/jump.ogg", "sha256": "a", "role": "sfx", "format": "ogg", "task": "audio.sfx.jump", "replaced": False}]}
engine._set(V, iv, PASSED)
finish(V, "qa.assets", {"status": "failed", "checks": [{"name": "assets open", "ok": False, "detail": [{"path": "audio/jump.ogg", "ok": False, "error": "truncated"}]}],
                        "outputs": [{"path": "/r.json", "role": "report", "format": "json"}]})
f = F(V, "qa.assets")[0]
check("integration failure: a defective integrated file is routed to the department that made it (AudioCraft), reported in Integration QA",
      f["layer"] == "integration" and f["routed_to"] == "Studio · audiocraft" and f["severity"] == "blocker" and "audio.sfx.jump.r1" in V["tasks"]
      and not any(k.startswith("fix.qa.assets") for k in V["tasks"]), f)
W = new(GAME, "g4")
finish(W, "qa.assets", {"status": "ok", "checks": [], "outputs": [{"path": "/r.json", "role": "report", "format": "json"}]})
check("integration failure: an integrated asset the build never loads (referenced gate) is wiring — the agent's",
      W["tasks"]["qa.assets"]["state"] in (FAILED, PASSED) and (W["tasks"]["qa.assets"]["state"] == PASSED or W["tasks"]["fix.qa.assets.r1"]["routed_to"] == "agent"))

# ---------------------------------------------------------------- 4. required vs optional, unavailable, verdicts
O = new(GAME, "g5", {"optional_criteria": ["asset_music"]})
for n in range(3): finish(O, "audio.music", {"status": "failed", "checks": [{"name": "loops cleanly", "ok": False}], "outputs": [{"path": "/m.ogg", "role": "music", "format": "ogg"}]})
pass_all(O, keep=[t for t in O["tasks"] if t.startswith("audio.music") or t == "integrate.audio.music"])
engine._set(O, O["tasks"]["integrate.audio.music"], BLOCKED, reason="upstream did not pass", blocked_by=["audio.music.r2"])
f = F(O, "audio.music")[0]
check("optional: a failed optional extra is 'not delivered (optional)', severity optional, never escalated; the verdict can be READY and Department QA is not failed by it",
      f["status"] == "not delivered (optional)" and f["severity"] == "optional" and "escalate.audio.music" not in O["tasks"]
      and report.verdict(report.acceptance(O)).startswith("READY") and qa.layers(O)["department"]["status"] == "passed", (f, report.verdict(report.acceptance(O)), qa.layers(O)))
U = new(GAME, "g6")
pass_all(U, keep=["audio.sfx.jump"])
finish(U, "audio.sfx.jump", {"status": "blocked", "reason": "AudioCraft runtime not installed", "install": ["scripts/install-studio.sh"]})
f = F(U, "audio.sfx.jump")[0]
check("unavailable tool: a missing runtime is 'unavailable', severity incomplete, never a defect or a re-run; the verdict is INCOMPLETE",
      f["severity"] == "incomplete" and f["status"].startswith("unavailable") and "audio.sfx.jump.r1" not in U["tasks"] and report.verdict(report.acceptance(U)) == "INCOMPLETE"
      and qa.layers(U)["department"]["status"] == "incomplete", (f, report.verdict(report.acceptance(U))))
X = new(APP, "a3")
t = finish(X, "qa.features", {"status": "blocked", "reason": "TestCraft browser missing", "install": ["playwright"]})
check("unavailable tool (builtin): a builtin whose department is missing (install given) is recorded unavailable, not a product failure",
      t["state"] == BLOCKED and t.get("unavailable") and not any(k.startswith("fix.qa.features") for k in X["tasks"]))

# successful three layers vs built-but-not-verified
S = new(APP, "a4"); pass_all(S)
A = qa.assurance(S)
check("success: all three layers passed → BUILT · PRODUCT VERIFIED, and the verdict (the criteria's) is READY",
      A["line"] == "BUILT · PRODUCT VERIFIED" and all(A["layers"][x]["status"] == "passed" for x in qa.LAYERS) and report.verdict(report.acceptance(S)).startswith("READY"), A)
N = new(APP, "a5"); pass_all(N, keep=["qa.request"]); finish(N, "qa.request", res)
A = qa.assurance(N)
check("built but not verified: every deliverable passed, Product QA failed → 'BUILT · NOT VERIFIED (Product QA failed)'; never READY (INCOMPLETE while its fix is in flight)",
      A["built"] and not A["verified"] and A["line"] == "BUILT · NOT VERIFIED (Product QA failed)" and report.verdict(report.acceptance(N)) == "INCOMPLETE", A["line"])
M = new(APP, "a6"); pass_all(M, keep=["qa.request"])
page("<!doctype html><html lang=en><meta name=viewport content=x><title>Streakly</title><p>TODO</p><input type=password>", "new Audio('a'); onpointerdown=f")
adv = qa.check_request({"project": proj, "params": M["tasks"]["qa.request"]["params"], "out_dir": out, "integrated": []})
finish(M, "qa.request", adv)
fa = F(M, "qa.request")
check("advisory only: suggestions pass the gate and the verdict stays READY; they are listed as advisory, routed nowhere, never re-run",
      M["tasks"]["qa.request"]["state"] == PASSED and report.verdict(report.acceptance(M)).startswith("READY") and fa
      and all(x["severity"] == "advisory" and x["routed_to"] is None and x["status"] == "listed (advisory)" for x in fa) and "fix.qa.request.r1" not in M["tasks"], fa)
md = report.markdown(N); st = engine.status(N)
check("report: a three-layer section with every finding's layer, criterion, severity, owner, route, evidence, resolution and retry status; status() carries it",
      "## Quality assurance (three layers)" in md and "| Layer | Criterion | Severity | Owner | Routed to | Evidence | Resolution | Retry / escalation |" in md
      and "Product QA" in md and st["qa"]["line"].startswith("BUILT · NOT VERIFIED") and st["qa"]["findings"][0]["criterion"] == "request_fulfilled")
check("review-only productions: no Product QA task and no fix orders (measure, change nothing)",
      "qa.request" not in planner.build(intake.parse("Run GITCRAFT: review this game", overrides={"mode": {"existing": True, "workflow": "review"}}), DISC, version=2)["tasks"])

# ---------------------------------------------------------------- 5. determinism
def run_once(folder):
    Z = new(APP, folder); finish(Z, "qa.request", res)
    finish(Z, "audio.sfx.tap" if "audio.sfx.tap" in Z["tasks"] else next(t for t in Z["order"] if t.startswith("audio.sfx.")),
           {"status": "ok", "checks": [], "outputs": [{"path": wav, "role": "sfx", "format": "wav"}]})
    strip = lambda f: {k: (v.replace(Z["store"], "<store>") if isinstance(v, str) else [x.replace(Z["store"], "<store>") for x in v] if isinstance(v, list) else v) for k, v in f.items()}
    return json.dumps([strip(f) for f in qa.findings(Z)], sort_keys=True), json.dumps(qa.layers(Z), sort_keys=True), [k for k in Z["order"]]
check("deterministic: the same failures on two identical productions give the same findings, layer states and task order", run_once("d1") == run_once("d2"))

shutil.rmtree(ws, ignore_errors=True)
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
