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
                                                              "production_approve", "production_report", "production_contracts"} <= names)
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
    check("5 order: assets → integrate → build → QA → regression → release report → deploy",
          max(pos[t] for t in T if t.startswith(("audio.", "levels.", "vfx."))) < pos["integrate.assets"] < pos["build"]
          < min(pos[t] for t in T if t.startswith("qa.")) <= max(pos[t] for t in T if t.startswith("qa.")) < pos["release.regression"] < pos["release.report"] < pos["release.deploy"])
    check("5 hand-off dependency: palette-tinted effects wait for the identity", "foundation.identity" in T["vfx.dust"]["depends_on"] and T["vfx.dust"]["params"]["color"]["$from"] == "foundation.identity")
    check("6 parallel plan: ≥ 8 tasks in one wave", max(len(g) for g in plan["parallel_groups"]) >= 8, [len(g) for g in plan["parallel_groups"]])

    # ---- run: production departments, then the identity work order
    st = call(c, "production_run", {"production": pid})
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
    check("agent: VectorCraft drew and exported the logo (SVG) and icon (PNG)", all(os.path.getsize(f) > 1000 for f in files if not f.endswith(".json")) and len(files) == 3)
    st = call(c, "production_submit", {"production": pid, "task": "foundation.identity", "files": files, "notes": "VectorCraft identity"})
    check("identity accepted; production continued to the build work order", st["status"] == "awaiting_agent" and "build" in tasks_in(st, "awaiting_agent"), st["counts"])
    prod = load(pid)
    h = json.load(open(os.path.join(prod["store"], "handoffs", "vfx.dust.json")))
    check("7 hand-off: FXCraft received the identity's accent colour", h["params"].get("color") == [63, 193, 201], h["params"])
    man = prod["tasks"]["integrate.assets"]["result"]["integrated"]
    proj = prod["spec"]["project"]["path"]
    check("8 integration: every shipped asset copied into the project, hash-verified, with a licence sidecar",
          len(man) >= 20 and all(os.path.exists(m["dest"]) and os.path.exists(m["dest"] + ".license.json") for m in man), len(man))
    bo = json.load(open(os.path.join(prod["store"], "tasks", "build", "work_order.json")))
    check("build work order lists every integrated asset", len(bo["handoff"]["integrated_assets"]) == len(man))

    # ---- build (with a real defect), QA, remediation
    changed = agent.build(bo, defect=True); git_commit(proj, "Lantern Drift: first build")
    st = call(c, "production_submit", {"production": pid, "task": "build", "files": [os.path.join(proj, f) for f in changed], "notes": "first build"}, timeout=2400)
    prod = load(pid)
    sm = prod["tasks"]["qa.smoke"]
    check("9 real testing: TestCraft found the missing script on load (gate failed)", sm["state"] == "failed" and sm.get("failure") == "quality"
          and "missing-boot.js" in json.dumps(sm.get("gate_results")), sm.get("error"))
    check("9 a failed gate became a fix work order + a re-verification", "fix.qa.smoke.r1" in prod["tasks"] and prod["tasks"]["qa.smoke"].get("superseded_by") == "qa.smoke.r1")
    ran = {t: prod["tasks"][t]["state"] for t in ("qa.playcraft", "qa.pixelcraft", "qa.perf", "qa.assets", "qa.licences", "qa.designcraft")}
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
                                    "overrides": {"extra_tasks": extra, "assets": {"sfx": ["click"], "music": None}, "quality": {"playcraft": False, "pixelcraft": False, "designcraft": False, "perf": False}}})
    pid = p["production"]
    check("B1 missing runtime known before production starts", "anim.gpu" in p["blocked_up_front"], p["blocked_up_front"])
    st = call(c, "production_run", {"production": pid})
    prod = load(pid); T = prod["tasks"]
    check("B1 missing runtime → blocked with the reason and install command, no substitute output",
          T["anim.gpu"]["state"] == "blocked" and T["anim.gpu"].get("reason") and not T["anim.gpu"].get("outputs"), T["anim.gpu"].get("reason"))
    check("B1 blocked propagates to dependents", T["after.gpu"]["state"] == "blocked" and T["after.gpu"].get("blocked_by") == ["anim.gpu"])
    check("B2 failed department: retried once, then failed with its error", T["audio.broken"]["state"] == "failed" and len(T["audio.broken"]["attempts"]) == 2, T["audio.broken"].get("error"))
    check("B independent tasks still completed", T["audio.sfx.click"]["state"] == "passed" and T["audio.coin_a"]["state"] == "passed" and T["audio.coin_b"]["state"] == "passed")
    check("B2 integration does not start on a failed upstream (blocked, nothing copied)", T["integrate.assets"]["state"] == "blocked"
          and not os.path.exists(os.path.join(ws, "neg", "assets", "audio", "pickup.ogg")))
    check("B production status is honest (blocked/failed, not passed)", st["status"] in ("failed", "blocked"), st["status"])
    # the conflict on its own (no failed upstream): two different files → one path
    p = call(c, "production_plan", {"prompt": "Build a small arcade game with sound", "project": os.path.join(ws, "neg2"),
                                    "overrides": {"extra_tasks": extra[2:4], "assets": {"sfx": [], "music": None}, "quality": {"playcraft": False, "pixelcraft": False, "designcraft": False, "perf": False}}})
    call(c, "production_run", {"production": p["production"]})
    T = load(p["production"])["tasks"]
    check("B3 integration conflict: two different files for one path → failed, nothing copied", T["integrate.assets"]["state"] == "failed"
          and T["integrate.assets"].get("failure") == "conflict" and not os.path.exists(os.path.join(ws, "neg2", "assets", "audio", "pickup.ogg")), T["integrate.assets"].get("error"))
    check("B3 conflict blocks the build", T["build"]["state"] == "blocked")
    # an existing different asset is never overwritten without approval
    proj = os.path.join(ws, "neg3"); os.makedirs(os.path.join(proj, "assets", "fx"))
    tiny_png(os.path.join(proj, "assets", "fx", "sparks_flipbook.png"))   # the project's own (different) art
    p = call(c, "production_plan", {"prompt": "Build a small arcade game with sparks effects", "project": proj,
                                    "overrides": {"assets": {"sfx": [], "music": None, "vfx": ["sparks"]}, "quality": {"playcraft": False, "pixelcraft": False, "designcraft": False, "perf": False}}})
    st = call(c, "production_run", {"production": p["production"]})
    check("B existing different asset → integrate needs approval, file untouched", "integrate.assets" in tasks_in(st, "needs_approval")
          and open(os.path.join(proj, "assets", "fx", "sparks_flipbook.png"), "rb").read()[:4] == b"\x89PNG", st["counts"])

    # B4: an interrupted run resumes without redoing passed work
    p = call(c, "production_plan", {"prompt": "Make a platformer level pack with five levels and music", "project": os.path.join(ws, "pack5"),
                                    "overrides": {"deliverable": "asset_pack", "assets": {"sfx": []}}})
    pid = p["production"]
    runner = subprocess.Popen([sys.executable, "-m", "production", "run", pid, "--workers", "1"], cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 120:
        time.sleep(0.5)
        try: pr = load(pid)
        except (OSError, ValueError): continue
        if sum(1 for t in pr["tasks"].values() if t["state"] == "passed") >= 3: break
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
                                    "overrides": {"assets": {"sfx": [], "music": None, "vfx": [], "identity": False},
                                                  "quality": {"playcraft_min": 99, "max_rounds": 1, "pixelcraft": False, "designcraft": False, "perf": False, "require_known_licences": False}}})
    pid = p["production"]
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
    finally:
        c.p.kill()
    bad = [l for l, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""), flush=True)
    print(f"workspace: {ws}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
