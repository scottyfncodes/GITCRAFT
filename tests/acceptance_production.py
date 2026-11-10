#!/usr/bin/env python3
"""Master-prompt acceptance test for the GITCRAFT Production Director.

One substantial master prompt → a finished, verified game, through the real MCP server (scripts/mcp.sh
studiocraft: guard + Landlock sandbox, no network). Every department runs for real: AudioCraft, LevelCraft,
FXCraft, TestCraft, PLAYCRAFT, PIXELCRAFT, DESIGNCRAFT, AssetCraft, and VectorCraft for the identity (driven by
the agent stand-in, tests/production_agent.py, which also writes the game code Claude would write from the
work order). Nothing reports success it did not measure; mocked results are never used as evidence.

Part A (the master prompt): interpretation, discovery, architecture, department selection, dependency order,
measured parallelism, hand-offs (palette → tinted effects), integration, real QA, a failed gate → fix →
re-verification on the modified files, release report, deployment held for approval and never recorded as
live without evidence, persistent history, idempotent resume.

Part B (negative): a plan the departments would refuse; a missing runtime (blocked + propagation); a failed
department (retried, then failed); an invalid agent output; an integration conflict; an existing asset that
would be overwritten (needs approval); an interrupted run resumed without redoing passed work; a quality gate
that stays failed after its remediation rounds (NOT READY).

    python3 tests/acceptance_production.py             # everything (~6 min)
    python3 tests/acceptance_production.py --part A|B
    GITCRAFT_PRODUCTION_PROOF=<dir>                    # keep the workspace (default: a temp folder)"""
import json, os, shutil, signal, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, REPO)
from mcp_client import Client
import production_agent as agent

PART = sys.argv[sys.argv.index("--part") + 1] if "--part" in sys.argv else "AB"
ws = os.path.realpath(os.environ.get("GITCRAFT_PRODUCTION_PROOF") or tempfile.mkdtemp(prefix="gitcraft-production-"))
os.makedirs(ws, exist_ok=True)
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog", "catalog.sqlite"),
           GITCRAFT_3D_LIBRARY=os.path.join(ws, "3d-library"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "playcraft-history"),
           GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pixelcraft-history"))
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond)))
    print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)
    return bool(cond)


def server():
    return Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=env, log=os.path.join(ws, "studiocraft.log"))


def call(c, tool, args, timeout=1500):
    ok, r = c.call(tool, args, timeout=timeout)
    if not ok and not isinstance(r, dict): raise RuntimeError(f"{tool}: {r}")
    return r


def load(pid):
    return json.load(open(os.path.join(ws, "gitcraft-out", "production", pid, "production.json")))


def tasks_in(st, state): return [t["id"] for t in st["tasks"] if t["state"] == state]


def approve_blueprint(c, pid):
    """The person approves the Decision Room's blueprint (the acceptance test stands in for them). Refused plans stay refused."""
    ok, r = c.call("production_decide", {"production": pid, "approve": True}, timeout=300)
    return r if ok else {"refused": r}


# Part B exercises the engine's negative paths, so its small games leave the icon and attribution standards out (explicitly)
NO_STD = {"icon": {"required": False}, "attribution": {"required": False}}


def git_commit(proj, msg):
    if not os.path.isdir(os.path.join(proj, ".git")): subprocess.run(["git", "init", "-q", "-b", "claude/production", proj], check=True)
    subprocess.run(["git", "-C", proj, "add", "-A"], check=True)
    subprocess.run(["git", "-C", proj, "-c", "user.email=agent@gitcraft.local", "-c", "user.name=agent", "commit", "-qm", msg, "--allow-empty"], check=True)


def tiny_png(path, size=8):
    import struct, zlib
    raw = b"".join(b"\x00" + bytes([200, 60, 40]) * size for _ in range(size))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def max_concurrency(prod, ids):
    iv = [(a["t0"], a["t1"]) for i in ids for a in prod["tasks"][i]["attempts"] if a.get("t0") and a.get("t1")]
    pts = sorted([(s, 1) for s, _ in iv] + [(e, -1) for _, e in iv])
    cur = best = 0
    for _, d in pts: cur += d; best = max(best, cur)
    return best


MASTER = ("Build a polished, mobile-first, original platformer game called Lantern Drift with a complete gameplay loop, progression, "
          "an original visual identity, sound, music, three levels, sparks and dust effects, responsive touch controls and production-ready deployment.")


def part_a(c):
    print("\n== A. one master prompt → a verified release ==", flush=True)
    names = {t["name"] for t in c.tools()}
    check("studiocraft serves the Production Director tools", {"production_plan", "production_run", "production_status", "production_submit",
                                                              "production_approve", "production_report", "production_contracts", "production_idea",
                                                              "production_recon", "production_promote", "production_decide", "production_revise"} <= names)
    con = call(c, "production_contracts", {})
    check("every department has a contract (accepts, produces, requires, success, failure, storage, provenance)",
          all(all(k in v for k in ("accepts", "requires", "success", "failure", "storage", "provenance")) for v in list(con["studio"].values()) + [con[k] for k in ("forgecraft", "designcraft", "agent", "builtin")])
          and len(con["studio"]) == 11, sorted(con["studio"]))

    # ---- 1. interpretation
    plan = call(c, "production_plan", {"prompt": MASTER})
    pid, spec = plan["production"], plan["spec"]
    a = spec["assets"]
    check("1 interpretation: a 2D mobile-first platformer game titled Lantern Drift", spec["deliverable"] == "game" and spec["dimension"] == "2d"
          and spec["platform"]["mobile_first"] and spec["genres"][:1] == ["platformer"] and spec["title"] == "Lantern Drift", spec)
    check("1 interpretation: sound, music, three platformer levels, effects, identity, polished quality bar",
          "jump" in a.get("sfx", []) and a.get("music") and a["levels"]["count"] == 3 and a["levels"]["kind"] == "platformer"
          and {"sparks", "dust"} <= set(a.get("vfx", [])) and a.get("identity") and spec["quality"]["level"] == "polished", a)
    check("1 interpretation: deployment asked for → not authorised up front, a non-essential question with a safe default",
          not spec["authorisations"]["deploy"] and any(q["id"] == "deploy_target" and not q["essential"] for q in spec["questions"]))
    crit = {x["id"] for x in plan["acceptance"]}
    check("1 measurable acceptance criteria derived", {"loads_everywhere", "gameplay_quality", "interface_quality", "licensing", "asset_integrity",
                                                       "deployment", "release_ready"} <= crit, crit)
    # ---- 2–4. discovery, architecture, department selection
    prod = load(pid)
    check("2 discovery: the project folder did not exist; every department's readiness was asked", not prod["discovery"]["project"]["exists"]
          and len(prod["discovery"]["runtimes"]["studio"].get("departments", [])) == 11)
    check("2 discovery: nothing in this plan is blocked on this machine", plan["blocked_up_front"] == {}, plan["blocked_up_front"])
    T = prod["tasks"]
    depts = {t["department"] for t in T.values() if t["kind"] == "studio"}
    check("4 departments selected: audio, levels, effects, testing, gameplay, interface", {"audiocraft", "levelcraft", "fxcraft", "testcraft", "playcraft", "pixelcraft"} <= depts, depts)
    check("4 DESIGNCRAFT (advisory) and the agent's work orders (identity, build) are in the plan",
          T["qa.designcraft"]["kind"] == "designcraft" and T["foundation.identity"]["kind"] == "agent" and T["build"]["kind"] == "agent")
    check("4 nothing irrelevant planned (no 3D, no voice, no terrain for a 2D platformer)", not any(k in T for k in ("audio.voice", "world.terrain", "models.1")))
    check("3 plan validated before running (every request is one its department accepts)", plan["problems"] == [], plan["problems"])
    check("3 every acceptance criterion is measured by a planned task", plan["unmeasured_criteria"] == [], plan["unmeasured_criteria"])
    # ---- 5. dependency order
    pos = {t: i for i, g in enumerate(plan["parallel_groups"]) for t in g}
    check("5 order (plan v2): foundation → build (beside the assets) ; assets → integrate.<asset> → integrate.final → build.wire → QA → regression → release report → deploy",
          load(pid).get("plan_version") == 2 and pos["foundation.identity"] < pos["build"] and set(T["build"]["depends_on"]) == {"foundation.scaffold", "foundation.identity", "design.direction"}
          and all(pos[t] < pos[f"integrate.{t}"] < pos["integrate.final"] for t in T if t.startswith(("audio.", "levels.", "vfx.")))
          and max(pos["build"], pos["integrate.final"]) < pos["build.wire"] < min(pos[t] for t in T if t.startswith("qa."))
          <= max(pos[t] for t in T if t.startswith("qa.")) < pos["release.regression"] < pos["release.report"] < pos["release.deploy"])
    from production import planner as _pl
    _p1 = _pl.build(load(pid)["spec"], load(pid)["discovery"], version=1); _w = {t: i for i, g in enumerate(_p1["parallel_groups"]) for t in g}
    check("5 order (plan v1, existing records): assets → integrate → build → QA, unchanged",
          max(_w[t] for t in _p1["tasks"] if t.startswith(("audio.", "levels.", "vfx."))) < _w["integrate.assets"] < _w["build"] < min(_w[t] for t in _p1["tasks"] if t.startswith("qa.")))
    check("5 hand-off dependency: palette-tinted effects wait for the identity", "foundation.identity" in T["vfx.dust"]["depends_on"] and T["vfx.dust"]["params"]["color"]["$from"] == "foundation.identity")
    check("6 parallel plan: ≥ 8 tasks in one wave", max(len(g) for g in plan["parallel_groups"]) >= 8, [len(g) for g in plan["parallel_groups"]])
    check("lifecycle: the plan waits in the Decision Room with a Discovery Report (icon, engineering, deployment decisions)", plan["stage"] == "decisions"
          and os.path.isfile(plan["discovery_report"]) and {"app_icon", "engineering", "deployment"} <= {d["id"] for d in plan["decision_room"]})
    check("lifecycle: building before approval is refused", "not approved" in str(call(c, "production_run", {"production": pid}).get("refused")))
    check("lifecycle: the person approves the blueprint", approve_blueprint(c, pid).get("stage") == "approved")

    # ---- run: production departments, then the identity work order
    st = call(c, "production_run", {"production": pid})
    check("direction first: the run stops at the creative direction, before the identity or any code",
          st["status"] == "awaiting_agent" and tasks_in(st, "awaiting_agent") == ["design.direction"], tasks_in(st, "awaiting_agent"))
    dorder = json.load(open(os.path.join(load(pid)["store"], "tasks", "design.direction", "work_order.json")))
    st = call(c, "production_submit", {"production": pid, "task": "design.direction", "files": agent.direction(dorder), "notes": "Lantern Drift: look and play"})
    check("run stops at the agent's identity work order", st["status"] == "awaiting_agent" and "foundation.identity" in tasks_in(st, "awaiting_agent"), st["counts"])
    prod = load(pid)
    first_wave = [t for t in prod["tasks"] if t.startswith(("audio.", "levels.")) or t == "vfx.sparks"]
    check("department tasks passed their gates", all(prod["tasks"][t]["state"] == "passed" for t in first_wave), {t: prod["tasks"][t]["state"] for t in first_wave})
    mc = max_concurrency(prod, first_wave)
    check("6 measured parallelism: department tasks really overlapped", mc >= 2, mc)
    check("department provenance: every output has a .studio.json record with hashes",
          all((prod["tasks"][t]["result"] or {}).get("record") and os.path.exists(prod["tasks"][t]["result"]["record"]) and all(o.get("sha256") for o in prod["tasks"][t]["outputs"]) for t in first_wave))

    order = json.load(open(os.path.join(prod["store"], "tasks", "foundation.identity", "work_order.json")))
    # negative: an invalid agent output is refused and the work order stays open
    open(os.path.join(order["out_dir"], "palette.json"), "w").write(json.dumps({"background": "#000000"}))
    open(os.path.join(order["out_dir"], "icon-512.png"), "wb").write(b"this is not a png")
    r = call(c, "production_submit", {"production": pid, "task": "foundation.identity", "files": [os.path.join(order["out_dir"], f) for f in ("palette.json", "icon-512.png")]})
    check("B invalid output: a corrupt PNG and a palette missing keys are rejected; the work order stays open",
          not r["submission"]["accepted"] and "foundation.identity" in tasks_in(r, "awaiting_agent"), r["submission"])
    files = agent.identity(order, env)
    check("agent: VectorCraft drew and exported the logo (SVG)", all(os.path.getsize(f) > 1000 for f in files if not f.endswith(".json")) and len(files) == 2)
    st = call(c, "production_submit", {"production": pid, "task": "foundation.identity", "files": files, "notes": "VectorCraft identity"})
    check("identity accepted; the App Icon Studio asks for concepts", st["status"] == "awaiting_agent" and "icon.concepts" in tasks_in(st, "awaiting_agent"), st["counts"])
    check("plan v2: the code build is issued beside the icon concepts, before any icon choice", "build" in tasks_in(st, "awaiting_agent")
          and load(pid)["tasks"]["icon.select"]["state"] == "pending", tasks_in(st, "awaiting_agent"))
    # ---- App Icon Studio: concepts (VectorCraft) → a person chooses → the master → the platform set
    co = json.load(open(os.path.join(prod["store"], "tasks", "icon.concepts", "work_order.json")))
    st = call(c, "production_submit", {"production": pid, "task": "icon.concepts", "files": agent.icon_concepts(co, env), "notes": "three VectorCraft concepts"})
    check("icon: three concepts accepted; the choice waits for a person (never silently selected)", "icon.select" in tasks_in(st, "needs_approval"), st["counts"])
    sel = load(pid)["tasks"]["icon.select"]
    check("icon: the comparison sheet shows every concept", os.path.isfile(sel["result"]["sheet"]) and open(sel["result"]["sheet"]).read().count("<article>") == 3)
    call(c, "production_approve", {"production": pid, "task": "icon.select", "approved": True, "choice": "lantern", "note": "acceptance test: the person picks the lantern"})
    st = call(c, "production_run", {"production": pid})
    mo = json.load(open(os.path.join(prod["store"], "tasks", "icon.master", "work_order.json")))
    st = call(c, "production_submit", {"production": pid, "task": "icon.master", "files": agent.icon_master(mo, env), "notes": "the approved lantern, 1024 master"})
    prod = load(pid)
    check("icon: the platform set was derived from the approved master", prod["tasks"]["icon.derivatives"]["state"] == "passed", prod["tasks"]["icon.derivatives"].get("error"))
    check("identity and icons done; production continued to the build work order", st["status"] == "awaiting_agent" and "build" in tasks_in(st, "awaiting_agent"), st["counts"])
    prod = load(pid)
    h = json.load(open(os.path.join(prod["store"], "handoffs", "vfx.dust.json")))
    check("7 hand-off: FXCraft received the identity's accent colour", h["params"].get("color") == [63, 193, 201], h["params"])
    man = [m for i in prod["order"] if prod["tasks"][i]["kind"] == "builtin" and prod["tasks"][i].get("action") == "integrate" and prod["tasks"][i]["state"] == "passed"
           for m in prod["tasks"][i]["result"]["integrated"]]
    proj = prod["spec"]["project"]["path"]
    check("8 integration: every shipped asset committed into the project, hash-verified, with a licence sidecar",
          len(man) >= 20 and all(os.path.exists(m["dest"]) and (os.path.exists(m["dest"] + ".license.json") or m["role"] in ("icon_native",)) for m in man), len(man))
    am = json.load(open(os.path.join(proj, "gitcraft.assets.json")))["assets"]
    check("8 integration: the asset manifest lists exactly the committed files and hashes (owned by integration)", {m["dest_rel"]: m["sha256"] for m in man} == {k: v["sha256"] for k, v in am.items()})
    bo = json.load(open(os.path.join(prod["store"], "tasks", "build", "work_order.json")))
    ships = {t for t in prod["tasks"] if prod["tasks"][t].get("ship")}
    check("build work order lists every planned asset (placeholders until build.wire)", {a["task"] for a in bo["handoff"]["planned_assets"]} == ships)

    # ---- build (with a real defect), QA, remediation
    changed = agent.build(bo, defect=True); git_commit(proj, "Lantern Drift: first build")
    st = call(c, "production_submit", {"production": pid, "task": "build", "files": [os.path.join(proj, f) for f in changed], "notes": "first build"}, timeout=2400)
    check("build.wire follows the build and the final integration; QA has not started", "build.wire" in tasks_in(st, "awaiting_agent")
          and load(pid)["tasks"]["qa.smoke"]["state"] == "pending", st["counts"])
    wo = json.load(open(os.path.join(prod["store"], "tasks", "build.wire", "work_order.json")))
    check("build.wire work order lists every integrated asset and the approved icon set", len(wo["handoff"]["integrated_assets"]) == len(man) and wo["handoff"].get("icon_snippet"))
    changed = agent.wire(wo, defect=True); git_commit(proj, "Lantern Drift: assets and icon wired")
    st = call(c, "production_submit", {"production": pid, "task": "build.wire", "files": [os.path.join(proj, f) for f in changed], "notes": "wired"}, timeout=2400)
    prod = load(pid)
    sm = prod["tasks"]["qa.smoke"]
    check("9 real testing: TestCraft found the missing script on load (gate failed)", sm["state"] == "failed" and sm.get("failure") == "quality"
          and "missing-boot.js" in json.dumps(sm.get("gate_results")), sm.get("error"))
    check("9 a failed gate became a fix work order + a re-verification", "fix.qa.smoke.r1" in prod["tasks"] and prod["tasks"]["qa.smoke"].get("superseded_by") == "qa.smoke.r1")
    ran = {t: prod["tasks"][t]["state"] for t in ("qa.playcraft", "qa.pixelcraft", "qa.perf", "qa.assets", "qa.licences", "qa.designcraft", "qa.icons", "qa.attribution", "qa.standards")}
    check("9 every QA department measured the build", all(s in ("passed", "failed") for s in ran.values()), ran)
    pc = (prod["tasks"]["qa.playcraft"].get("result") or {}).get("summary", {}).get("overall", {}).get("score")
    check("9 PLAYCRAFT score is a measurement in the record", isinstance(pc, (int, float)), pc)
    check("release did not start while QA was failing", prod["tasks"]["release.report"]["state"] == "pending")
    rounds = 0
    while True:
        st = call(c, "production_status", {"production": pid})
        fixes = [t for t in tasks_in(st, "awaiting_agent") if t.startswith("fix.")]
        if not fixes or rounds > 4: break
        rounds += 1
        for f in fixes:
            o = json.load(open(os.path.join(prod["store"], "tasks", f, "work_order.json")))
            if "smoke" in f: ch = agent.fix(o)
            elif "playcraft" in f and "coyote" not in open(os.path.join(proj, "js", "game.js")).read(): ch = agent.improve(o)
            else: ch = []
            if not ch:   # no honest remedy available to the stand-in: the work order stays open (the production cannot be READY)
                print(f"   agent has no fix for {f}; leaving it open", flush=True); continue
            git_commit(proj, f"fix: {f}")
            call(c, "production_submit", {"production": pid, "task": f, "files": [os.path.join(proj, x) for x in ch], "notes": "fixed per findings"}, timeout=2400)
        if all(not (("smoke" in f) or ("playcraft" in f)) for f in fixes): break
    prod = load(pid)
    rv = prod["tasks"].get("qa.smoke.r1", {})
    check("10 re-verification measured the modified project and passed", rv.get("state") == "passed" and rv.get("measured_fingerprint") != sm.get("measured_fingerprint"))
    if "qa.playcraft.r1" in prod["tasks"]:
        before = prod["tasks"]["qa.playcraft"]["result"]["summary"]["overall"]["score"]
        after = ((prod["tasks"]["qa.playcraft.r1"].get("result") or {}).get("summary") or {}).get("overall", {}).get("score")
        check(f"10 PLAYCRAFT re-measured after its fix ({before} → {after})", prod["tasks"]["qa.playcraft.r1"]["state"] == "passed", after)
    st = call(c, "production_status", {"production": pid})
    prod = load(pid)
    perf_iv = [(a["t0"], a["t1"]) for t, x in prod["tasks"].items() if t.startswith("qa.perf") for a in x["attempts"] if a.get("t0") and a.get("t1")]
    other_iv = [(a["t0"], a["t1"]) for t, x in prod["tasks"].items() if not t.startswith("qa.perf") for a in x["attempts"] if a.get("t0") and a.get("t1")]
    check("frame-rate measurements ran with the machine to themselves (no other task overlapped qa.perf)", perf_iv and
          not any(s0 < e1 and s1 < e0 for s0, e0 in perf_iv for s1, e1 in other_iv), perf_iv)
    fp_rel = prod["tasks"]["release.report"].get("result", {}).get("fingerprint")
    final_qa = [e for e in (prod["tasks"][i] for i in prod["order"]) if e["kind"] != "agent" and e["stage"] in ("qa", "release") and e["state"] == "passed" and e.get("measured_fingerprint")]
    check("11 release: every QA result was measured on the exact build released", fp_rel and all(q["measured_fingerprint"] == fp_rel for q in final_qa if not q.get("superseded_by")),
          [(q["id"], q["measured_fingerprint"][:8]) for q in final_qa])
    check("11 release report passed; deployment waits for a person", prod["tasks"]["release.report"]["state"] == "passed" and st["status"] == "needs_approval"
          and "release.deploy" in tasks_in(st, "needs_approval"), st["counts"])
    rep = call(c, "production_report", {"production": pid})
    acc = {x["id"]: x["status"] for x in rep["acceptance"]}
    check("11 the app icon, HaveAnApp attribution and engineering standard were measured and passed", all(acc.get(k) == "passed" for k in ("app_icon", "attribution", "engineering_standards")), acc)
    check("11 every acceptance criterion passed except deployment (needs approval)", all(v == "passed" for k, v in acc.items() if k != "deployment") and acc["deployment"] == "needs_approval", acc)
    check("11 the report shows measured evidence (scores) and says READY — deployment needs approval", "READY — deployment needs approval" in rep["markdown"] and "PLAYCRAFT overall" in rep["markdown"])
    # the deployment: approved by "the person" here, but never recorded live without evidence
    st = call(c, "production_approve", {"production": pid, "task": "release.deploy", "approved": True, "note": "acceptance test"})
    check("approved deployment becomes an agent work order", "release.deploy" in tasks_in(st, "awaiting_agent") or call(c, "production_run", {"production": pid})["status"] == "awaiting_agent")
    r = call(c, "production_submit", {"production": pid, "task": "release.deploy", "url": "https://lantern-drift.example.invalid", "notes": "claimed deployed"})
    check("a deployment claimed without a check against the live URL is refused", not r["submission"]["accepted"], r["submission"])
    # ---- 12. persistence, idempotent resume
    prod = load(pid)
    n_before = {t: len(x["attempts"]) for t, x in prod["tasks"].items()}
    st = call(c, "production_run", {"production": pid})
    prod = load(pid)
    rerun = [t for t, x in prod["tasks"].items() if len(x["attempts"]) != n_before[t]]
    check("12 resume: running again redoes no passed work", not rerun, rerun)
    ev = open(os.path.join(prod["store"], "events.jsonl")).read().splitlines()
    check("12 persistent history: event log, report, handoffs, work orders on disk", len(ev) > 50 and os.path.exists(os.path.join(prod["store"], "REPORT.md"))
          and len(os.listdir(os.path.join(prod["store"], "handoffs"))) >= 20)
    check("12 production_list shows it", any(p["id"] == pid for p in call(c, "production_list", {})["productions"]))
    print(f"   production: {prod['store']}\n   project: {proj}", flush=True)
    return pid


def part_b(c):
    print("\n== B. negative paths ==", flush=True)
    # B0: a request a department would refuse is caught at planning, before anything runs
    p = call(c, "production_plan", {"prompt": "Make a sound pack of retro arcade sound effects", "project": os.path.join(ws, "pack0"),
                                    "overrides": {"extra_tasks": [{"id": "audio.bad", "department": "audiocraft", "action": "sfx", "params": {"preset": "kazoo"}}]}})
    check("B a plan with problems cannot be approved", "refused" in approve_blueprint(c, p["production"]))
    check("B plan-time validation: a request the department would refuse is a plan problem", p["status"] == "needs_input" and any("audio.bad" in x for x in p["problems"]), p["problems"])
    r = call(c, "production_run", {"production": p["production"]})
    check("B a plan with problems does not run", "refused" in r)

    # B1–B3: missing runtime, failed department, integration conflict — and independent work still completes
    bad = os.path.join(ws, "corrupt.wav"); open(bad, "wb").write(b"RIFF....WAVEfmt definitely not audio")
    extra = [{"id": "anim.gpu", "department": "animcraft", "action": "autorig_ml", "params": {"input": os.path.join(ws, "none.glb")}},
             {"id": "audio.broken", "department": "audiocraft", "action": "process", "params": {"input": bad}, "ship": {"dest": "$project/assets/audio", "roles": ["*"]}},
             {"id": "audio.coin_a", "department": "audiocraft", "action": "sfx", "params": {"preset": "coin", "name": "pickup"}, "ship": {"dest": "$project/assets/audio", "roles": ["sfx"], "formats": ["ogg"]}},
             {"id": "audio.coin_b", "department": "audiocraft", "action": "sfx", "params": {"preset": "laser", "name": "pickup"}, "ship": {"dest": "$project/assets/audio", "roles": ["sfx"], "formats": ["ogg"]}},
             {"id": "after.gpu", "department": "audiocraft", "action": "sfx", "params": {"preset": "blip"}, "depends_on": ["anim.gpu"]}]
    p = call(c, "production_plan", {"prompt": "Build a small arcade game with sound", "project": os.path.join(ws, "neg"),
                                    "overrides": dict(NO_STD, extra_tasks=extra, assets={"sfx": ["click"], "music": None}, quality={"playcraft": False, "pixelcraft": False, "designcraft": False, "perf": False})})
    pid = p["production"]; approve_blueprint(c, pid)
    check("B1 missing runtime known before production starts", "anim.gpu" in p["blocked_up_front"], p["blocked_up_front"])
    st = call(c, "production_run", {"production": pid})
    prod = load(pid); T = prod["tasks"]
    check("B1 missing runtime → blocked with the reason and install command, no substitute output",
          T["anim.gpu"]["state"] == "blocked" and T["anim.gpu"].get("reason") and not T["anim.gpu"].get("outputs"), T["anim.gpu"].get("reason"))
    check("B1 blocked propagates to dependents", T["after.gpu"]["state"] == "blocked" and T["after.gpu"].get("blocked_by") == ["anim.gpu"])
    check("B2 failed department: retried once, then failed with its error", T["audio.broken"]["state"] == "failed" and len(T["audio.broken"]["attempts"]) == 2, T["audio.broken"].get("error"))
    check("B independent tasks still completed", T["audio.sfx.click"]["state"] == "passed" and T["audio.coin_a"]["state"] == "passed" and T["audio.coin_b"]["state"] == "passed")
    check("B2 integration of a failed asset does not start (blocked, nothing copied); the final integration is blocked, the code build is not",
          T["integrate.audio.broken"]["state"] == "blocked" and T["integrate.final"]["state"] == "blocked" and T["build"]["state"] == "awaiting_agent"
          and not os.path.exists(os.path.join(ws, "neg", "assets", "audio", "corrupt.wav")), {k: T[k]["state"] for k in ("integrate.audio.broken", "integrate.final", "build")})
    rep_ = call(c, "production_report", {"production": pid})
    check("B production status is honest: never passed while an asset failed (plan v2 keeps building, so it is awaiting the agent), and not READY",
          st["status"] in ("failed", "blocked", "awaiting_agent") and st["status"] != "passed" and not rep_["markdown"].split("verdict **")[1].startswith("READY"),
          (st["status"], rep_["markdown"][:300]))
    # the conflict on its own (no failed upstream): two different files → one path
    p = call(c, "production_plan", {"prompt": "Build a small arcade game with sound", "project": os.path.join(ws, "neg2"),
                                    "overrides": dict(NO_STD, extra_tasks=extra[2:4], assets={"sfx": [], "music": None}, quality={"playcraft": False, "pixelcraft": False, "designcraft": False, "perf": False})})
    approve_blueprint(c, p["production"])
    call(c, "production_run", {"production": p["production"]})
    T = load(p["production"])["tasks"]
    ab = [T["integrate.audio.coin_a"], T["integrate.audio.coin_b"]]
    loser = next((x for x in ab if x["state"] == "failed"), {})
    check("B3 integration conflict: the second file for one path fails as a conflict naming both tasks; nothing of it is copied",
          loser.get("failure") == "conflict" and "audio.coin_" in (loser.get("error") or "") and sorted(x["state"] for x in ab) == ["failed", "passed"]
          and json.load(open(os.path.join(ws, "neg2", "gitcraft.assets.json")))["assets"]["assets/audio/pickup.ogg"]["task"] in ("audio.coin_a", "audio.coin_b"),
          [(x["id"], x["state"], x.get("error")) for x in ab])
    check("B3 conflict blocks the final integration and the release, not the code build", T["integrate.final"]["state"] == "blocked" and T["build"]["state"] == "awaiting_agent")
    # an existing different asset is never overwritten without approval
    proj = os.path.join(ws, "neg3"); os.makedirs(os.path.join(proj, "assets", "fx"))
    tiny_png(os.path.join(proj, "assets", "fx", "sparks_flipbook.png"))   # the project's own (different) art
    p = call(c, "production_plan", {"prompt": "Build a small arcade game with sparks effects", "project": proj,
                                    "overrides": dict(NO_STD, assets={"sfx": [], "music": None, "vfx": ["sparks"]}, quality={"playcraft": False, "pixelcraft": False, "designcraft": False, "perf": False})})
    approve_blueprint(c, p["production"])
    st = call(c, "production_run", {"production": p["production"]})
    check("B existing different asset → one consolidated replace_assets request listing exactly that file; file untouched",
          "integrate.vfx.sparks" in tasks_in(st, "needs_approval") and st["replace_assets"] and st["replace_assets"]["ready"]
          and [f["file"] for f in st["replace_assets"]["files"]] == ["assets/fx/sparks_flipbook.png"] and sum("replace_assets" in n for n in st["next"]) == 1
          and open(os.path.join(proj, "assets", "fx", "sparks_flipbook.png"), "rb").read()[:4] == b"\x89PNG", (st["counts"], st.get("replace_assets")))

    # B4: an interrupted run resumes without redoing passed work
    p = call(c, "production_plan", {"prompt": "Make a platformer level pack with five levels and music", "project": os.path.join(ws, "pack5"),
                                    "overrides": {"deliverable": "asset_pack", "assets": {"sfx": []}}})
    pid = p["production"]; approve_blueprint(c, pid)
    runner = subprocess.Popen([sys.executable, "-m", "production", "run", pid, "--workers", "1"], cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 120:
        time.sleep(0.5)
        try: pr = load(pid)
        except (OSError, ValueError): continue
        # kill in the state the check below asserts: some passed AND one running. Breaking on "3 passed" alone
        # could land in the gap after a task passes and before the next is marked in_progress (seen in CI)
        if (sum(1 for t in pr["tasks"].values() if t["state"] == "passed") >= 3
                and any(t["state"] == "in_progress" for t in pr["tasks"].values())): break
    os.killpg(runner.pid, signal.SIGKILL); runner.wait()
    pr = load(pid)
    passed_before = {t: len(x["attempts"]) for t, x in pr["tasks"].items() if x["state"] == "passed"}
    interrupted = [t for t, x in pr["tasks"].items() if x["state"] == "in_progress"]
    check("B4 the run was killed mid-production (some passed, one in progress)", passed_before and interrupted, {"passed": list(passed_before), "running": interrupted})
    st = call(c, "production_run", {"production": pid})
    pr = load(pid)
    check("B4 resume: passed tasks were not redone", all(len(pr["tasks"][t]["attempts"]) == n for t, n in passed_before.items()))
    check("B4 resume: the interrupted task ran again and passed", all(pr["tasks"][t]["state"] == "passed" and pr["tasks"][t]["attempts"][0].get("status") == "interrupted" for t in interrupted),
          {t: (pr["tasks"][t]["state"], [a.get("status") for a in pr["tasks"][t]["attempts"]]) for t in interrupted})
    check("B4 the resumed production finished", st["status"] == "passed", st["counts"])

    # B5: a quality gate that stays failed after its remediation rounds
    game = os.path.join(ws, "mini"); shutil.copytree(os.path.join(HERE, "fixtures", "studio", "mini_game"), game); git_commit(game, "mini game")
    p = call(c, "production_plan", {"prompt": "Improve this existing arcade game for release", "project": game,
                                    "overrides": dict(NO_STD, skip_tasks=["qa.standards"], assets={"sfx": [], "music": None, "vfx": [], "identity": False},
                                                  quality={"playcraft_min": 99, "max_rounds": 1, "pixelcraft": False, "designcraft": False, "perf": False, "require_known_licences": False})})
    pid = p["production"]; approve_blueprint(c, pid)
    call(c, "production_run", {"production": pid})
    st = call(c, "production_submit", {"production": pid, "task": "build", "files": [os.path.join(game, "index.html")], "notes": "existing game"}, timeout=1500)
    check("B5 PLAYCRAFT gate failed against a 99 bar → fix work order", "fix.qa.playcraft.r1" in tasks_in(st, "awaiting_agent"), st["counts"])
    r = call(c, "production_submit", {"production": pid, "task": "fix.qa.playcraft.r1", "files": [os.path.join(game, "index.html")], "notes": "nothing changed", "continue": False})
    check("B5 a fix submitted without changing the project is refused; the work order stays open", not r["submission"]["accepted"]
          and "fix.qa.playcraft.r1" in tasks_in(r, "awaiting_agent"), r["submission"])
    with open(os.path.join(game, "index.html"), "a") as f: f.write("\n<!-- tuned -->\n")
    git_commit(game, "tune")
    st = call(c, "production_submit", {"production": pid, "task": "fix.qa.playcraft.r1", "files": [os.path.join(game, "index.html")], "notes": "a change that cannot reach 99"}, timeout=1500)
    pr = load(pid)
    check("B5 re-verification measured again and still failed; rounds exhausted", pr["tasks"]["qa.playcraft.r1"]["state"] == "failed" and pr["tasks"]["qa.playcraft.r1"].get("exhausted"))
    check("B5 release blocked; production failed; report says NOT READY", pr["tasks"]["release.report"]["state"] == "blocked" and st["status"] == "failed"
          and "NOT READY" in call(c, "production_report", {"production": pid})["markdown"], st["status"])


def main():
    c = server()
    try:
        if "A" in PART: part_a(c)
        if "B" in PART: part_b(c)
    except Exception:
        # an unexpected exception (e.g. "server exited") is a failure, never a pass: show why the server stopped
        rc = c.p.poll()
        print(f"\nERROR: the run stopped on an unexpected exception; studiocraft server exit status: {rc}"
              + (f" (killed by signal {-rc})" if rc is not None and rc < 0 else ""), flush=True)
        try: print("---- studiocraft.log (server + guard stderr), last 6000 chars ----\n" + open(os.path.join(ws, "studiocraft.log"), errors="replace").read()[-6000:], flush=True)
        except OSError as e: print(f"(no server log: {e})", flush=True)
        raise
    finally:
        c.p.kill()
    bad = [l for l, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""), flush=True)
    print(f"workspace: {ws}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
