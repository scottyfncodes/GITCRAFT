#!/usr/bin/env python3
"""End-to-end certification of "Run GITCRAFT report": the real evaluators, on a real reference game, through the real
launcher (scripts/mcp.sh studiocraft: guard + Landlock sandbox), exactly as a session calls the tool. Nothing is stubbed.

  healthy      the reference game (tests/fixtures/playcraft/arcade_dodge)   → VALID, a score, every mandatory evaluator measured
  defect       the same game with a start-up crash and a missing file       → VALID, a lower score, the defects found and attributed to the game
  broken       the browser the evaluators share cannot start                → INVALID, no score, the evaluators named, nothing held against the game
  unavailable  the Studio runtime is not installed                          → INVALID, no score, the install command
  partial      refresh=quick (PLAYCRAFT and PIXELCRAFT are not run)         → PARTIAL, no overall score, the measured findings kept
  repeat       the healthy game again                                       → the same state and scores
  recovery     that repeat runs after the broken run, in the same store     → VALID again

  python3 tests/certify_report.py [--out <folder>]     writes certification.json and certification.md there

The exit code is 0 only when every scenario behaved as required. A scenario that could not be run is NOT VERIFIED (never
a pass), and the verdict is then NOT VERIFIED: this script does not certify what it did not run."""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from mcp_client import Client  # noqa: E402

OUT = os.path.abspath(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
WS = os.path.realpath(tempfile.mkdtemp(prefix="gc-cert-"))
ENV = dict(os.environ, GITCRAFT_ROOT=WS, GITCRAFT_ROOTS=WS, GITCRAFT_REPORTS=os.path.join(WS, "reports"), GITCRAFT_ASSET_CATALOG=os.path.join(WS, "catalog", "catalog.sqlite"),
           GITCRAFT_3D_LIBRARY=os.path.join(WS, "3d-library"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(WS, "pc-history"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(WS, "px-history"),
           GITCRAFT_PRODUCTION_HOME=os.path.join(WS, "productions"))
for k in ("CHROMIUM_PATH", "GITCRAFT_STUDIO_HOME"): ENV.pop(k, None)
SCEN, LOG = [], []
MANDATORY = ["production", "playcraft", "pixelcraft", "testcraft"]


def say(*a):
    print(*a, flush=True)


def tree_hash(root):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds[:] = sorted(x for x in ds if x != ".git")
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def make(name, mutate=None):
    g = os.path.join(WS, name)
    shutil.copytree(os.path.join(HERE, "fixtures", "playcraft", "arcade_dodge"), g)
    if mutate: mutate(g)
    subprocess.run(["git", "init", "-q", g], check=True); subprocess.run(["git", "-C", g, "add", "-A"], check=True)
    subprocess.run(["git", "-C", g, "-c", "user.email=cert@gitcraft", "-c", "user.name=cert", "commit", "-qm", name], check=True)
    return g


def inject_defect(g):
    """Two real defects: the game crashes while starting (so no input does anything), and the page references a file that is not there."""
    p = os.path.join(g, "game.js"); s = open(p).read()
    open(p, "w").write("const cfg = window.GAME_CONFIG.settings.speed;   // certification defect: GAME_CONFIG is never defined\n" + s)
    p = os.path.join(g, "index.html"); s = open(p).read()
    open(p, "w").write(s.replace("</body>", '<img src="sprites/hero.png" alt="hero">\n</body>'))


def report(project, refresh, env=None, label=""):
    """One real `production_project_report` call through the launcher. → (R or None, error or None, seconds, command)."""
    e = dict(ENV, **(env or {})); t = time.time()
    cmd = f"scripts/mcp.sh studiocraft → tools/call production_project_report {{project: {os.path.relpath(project, WS)}, refresh: {refresh}}}" + (f"  [env {' '.join(f'{k}={v}' for k, v in (env or {}).items())}]" if env else "")
    say(f"\n$ {cmd}")
    try:
        c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=e, log=os.path.join(WS, f"studiocraft-{label}.log"))
    except Exception as x:
        return None, f"the server did not start: {x}", round(time.time() - t), cmd
    try:
        ok, v = c.call("production_project_report", {"project": project, "refresh": refresh}, timeout=1800)
    except Exception as x:
        ok, v = False, f"{type(x).__name__}: {x}"
    finally:
        c.close()
    secs = round(time.time() - t)
    if not ok or not isinstance(v, dict) or not (v.get("paths") or {}).get("json"): return None, str(v)[:600], secs, cmd
    R = json.load(open(v["paths"]["json"])); R["_tool_summary"] = {k: v[k] for k in ("evaluation", "health", "summary")}; R["_markdown"] = v.get("markdown") or ""
    return R, None, secs, cmd


def facts(R):
    """What a report claimed, in one small record (the evidence kept for each scenario)."""
    if not R: return None
    D = {d["id"]: d for d in R["departments"]}
    return {"report": R["paths"]["dir"], "state": R["evaluation"]["state"], "overall_score": R["health"]["score"], "headline": R["health"]["headline"], "band": R["health"]["band"],
            "first_summary_line": R["summary"][0], "reasons": R["evaluation"]["reasons"],
            "departments": {i: {"status": D[i]["status"], "evaluation": D[i]["quality"]["evaluation"], "score": D[i]["quality"]["value"], "reason": D[i]["quality"].get("reason"),
                                "findings": len(D[i]["findings"])} for i in D if D[i]["quality"]["evaluation"] != "not_applicable"},
            "evaluator_failures": R["evaluation"]["evaluator_failures"], "dependencies": [(c["id"], c["ok"]) for c in (R["evaluation"].get("dependencies") or {}).get("checks") or []],
            "P0_P1": [f"{a['priority']} {a['title']}" for a in R["actions"] if a["priority"] in ("P0", "P1")][:8]}


def scenario(name, required, checks, R=None, err=None, secs=None, cmd=None, blocker=None):
    """checks: [(label, bool, detail)]. A scenario that could not run at all is NOT VERIFIED."""
    if blocker: res = "NOT VERIFIED"
    else: res = "PASS" if checks and all(c[1] for c in checks) else "FAIL"
    S = {"scenario": name, "required": required, "result": res, "blocker": blocker, "command": cmd, "seconds": secs, "error": err,
         "checks": [{"check": l, "ok": bool(ok), "detail": None if ok else str(d)[:600]} for l, ok, d in checks], "evidence": facts(R)}
    SCEN.append(S)
    say(f"== {name}: {res}" + (f" ({blocker})" if blocker else "") + (f" · {secs} s" if secs is not None else ""))
    for c in S["checks"]: say(("   PASS " if c["ok"] else "   FAIL ") + c["check"] + ("" if c["ok"] else f"  [{c['detail']}]"))
    return S


def no_number(R):
    """No overall number anywhere a person or an agent reads it: the health record, the summary, the Markdown table."""
    md = R["_markdown"]
    return (R["health"]["score"] is None and R["_tool_summary"]["health"]["score"] is None and not any(re.search(r"\d\s*/\s*100", s) for s in R["summary"])
            and re.search(r"\| \*\*No overall score \((PARTIAL|INVALID) evaluation\)\*\* \|", md) is not None)


# ---------------------------------------------------------------- preflight: can this machine run the real evaluators at all?
pre = subprocess.run([sys.executable, "-m", "production", "evaluators", "--json"], cwd=REPO, env=ENV, capture_output=True, text=True)
try: PRE = json.loads(pre.stdout)
except ValueError: PRE = {"ok": False, "checks": [{"id": "probe", "ok": False, "title": "evaluator probe", "detail": (pre.stderr or pre.stdout)[-300:]}]}
say("$ python3 -m production evaluators"); [say(f"   [{'ok' if c['ok'] else 'FAILED'}] {c['title']}: {c['detail']}") for c in PRE["checks"]]
BLOCK = None if PRE["ok"] else "the real evaluators cannot run on this machine: " + "; ".join(f"{c['title']}: {c['detail']}" for c in PRE["checks"] if not c["ok"])

healthy = make("reference"); broken_game = make("reference-defect", inject_defect); partial_game = make("reference-quick")
before = tree_hash(healthy)

# ---------------------------------------------------------------- 1. healthy reference app
R1 = None
if BLOCK: scenario("healthy", "complete, evidence-backed evaluation", [], blocker=BLOCK)
else:
    R1, err, secs, cmd = report(healthy, "full", label="healthy")
    D = {d["id"]: d for d in R1["departments"]} if R1 else {}
    scenario("healthy", "complete, evidence-backed evaluation", [
        ("the report was produced through the sandboxed launcher", R1 is not None, err),
        ("evaluation VALID, with an overall score", R1 and R1["evaluation"]["state"] == "VALID" and isinstance(R1["health"]["score"], (int, float)), R1 and (R1["evaluation"]["state"], R1["health"])),
        ("every mandatory evaluator measured this build (a score each, none stale)", R1 and all(D[i]["quality"]["evaluation"] == "evaluated" and D[i]["status"] in ("current", "refreshed") for i in MANDATORY),
         {i: (D[i]["status"], D[i]["quality"]["evaluation"]) for i in MANDATORY} if R1 else None),
        ("PLAYCRAFT really played the build (desktop and phone), not source reading", R1 and (D["playcraft"]["score"] or {}).get("played") is True and any("played the existing build" in n and "desktop" in n for n in D["playcraft"]["notes"]),
         D["playcraft"]["notes"] if R1 else None),
        ("evidence exists on disk for each measurement (PLAYCRAFT, PIXELCRAFT, TestCraft result files in the report's folder)",
         R1 and all(os.path.isfile(os.path.join(R1["paths"]["dir"], "refresh", p)) for p in ("playcraft/playcraft.json", "pixelcraft/audit.json", "testcraft/smoke.studio.json")), R1 and os.listdir(os.path.join(R1["paths"]["dir"], "refresh"))),
        ("no evaluator failed, and the dependency probe ran green", R1 and not R1["evaluation"]["evaluator_failures"] and (R1["evaluation"].get("dependencies") or {}).get("ok") is True, R1 and R1["evaluation"]),
        ("a department with no evidence (DESIGNCRAFT: 0% of its rubric) is Not Evaluated, never a 0 in the score",
         R1 and D["designcraft"]["quality"]["evaluation"] != "evaluated" and "designcraft" not in R1["health"]["parts"], D["designcraft"]["quality"] if R1 else None),
        ("the report changed nothing in the project", tree_hash(healthy) == before, "project files changed"),
    ], R1, err, secs, cmd)

# ---------------------------------------------------------------- 2. broken evaluator (the shared browser cannot start)
R3 = None
if BLOCK: scenario("broken evaluator", "identify the evaluator failure, not an application failure", [], blocker=BLOCK)
else:
    bad = os.path.join(WS, "bin", "chromium"); os.makedirs(os.path.dirname(bad)); open(bad, "w").write("#!/bin/sh\necho 'chromium: cannot start (certification)' >&2\nexit 127\n"); os.chmod(bad, 0o755)
    R3, err, secs, cmd = report(healthy, "full", env={"CHROMIUM_PATH": bad}, label="broken")
    D = {d["id"]: d for d in R3["departments"]} if R3 else {}
    br = ("playcraft", "pixelcraft", "testcraft")
    scenario("broken evaluator", "identify the evaluator failure, not an application failure", [
        ("the report was produced", R3 is not None, err),
        ("evaluation INVALID", R3 and R3["evaluation"]["state"] == "INVALID", R3 and R3["evaluation"]["state"]),
        ("NO overall score anywhere (health record, tool summary, summary lines, Markdown)", R3 and no_number(R3), R3 and (R3["health"], R3["summary"][:2])),
        ("each browser evaluator is reported as an evaluator failure with the real launch error", R3 and all(D[i]["status"] == "evaluator_failed" and re.search(r"launch|chromium|browser", D[i].get("evaluator_failure") or "", re.I) for i in br),
         {i: (D[i]["status"], D[i].get("evaluator_failure")) for i in br} if R3 else None),
        ("nothing is held against the game: no finding, P0 or P1 from the broken evaluators; the band is not 'at risk'",
         R3 and all(not D[i]["findings"] for i in br) and not any(set(a["departments"]) & set(br) and a["priority"] in ("P0", "P1") for a in R3["actions"]) and R3["health"]["band"] != "at risk",
         R3 and [(a["priority"], a["title"]) for a in R3["actions"]][:6]),
        ("the report says so in words (failure of the evaluator, not a finding about the project)", R3 and any("failure of the evaluator, not a finding about the project" in s for s in R3["summary"]), R3 and R3["summary"][:3]),
        ("the dependency probe independently found the broken browser", R3 and any(c["id"] == "browser" and not c["ok"] for c in (R3["evaluation"].get("dependencies") or {}).get("checks") or []), R3 and R3["evaluation"].get("dependencies")),
        ("what could still be measured is kept and identical to the healthy run (engineering standard)", R3 and R1 and R3["health"]["parts"] == {"production": R1["health"]["parts"]["production"]}, R3 and R3["health"]["parts"]),
    ], R3, err, secs, cmd)

# ---------------------------------------------------------------- 3 + 4. repeat, and recovery after the broken run
if BLOCK:
    scenario("repeat", "consistent results under equivalent conditions", [], blocker=BLOCK); scenario("recovery", "normal evaluation after the dependency is restored", [], blocker=BLOCK)
else:
    R6, err, secs, cmd = report(healthy, "full", label="repeat")
    same = R6 and R1 and {i: R6["health"]["parts"].get(i) for i in MANDATORY} == {i: R1["health"]["parts"].get(i) for i in MANDATORY}
    keys = lambda R: sorted(f["key"] for d in R["departments"] for f in d["findings"])
    scenario("repeat", "consistent results under equivalent conditions", [
        ("the second run was produced", R6 is not None, err),
        ("same evaluation state", R6 and R1 and R6["evaluation"]["state"] == R1["evaluation"]["state"], R6 and R6["evaluation"]["state"]),
        ("identical department scores (production, PLAYCRAFT, PIXELCRAFT, TestCraft) and identical overall score", bool(same) and R6["health"]["score"] == R1["health"]["score"],
         (R1 and R1["health"]["parts"], R6 and R6["health"]["parts"], R1 and R1["health"]["score"], R6 and R6["health"]["score"])),
        ("identical findings", R6 and R1 and keys(R6) == keys(R1), R6 and R1 and sorted(set(keys(R6)) ^ set(keys(R1)))[:10]),
    ], R6, err, secs, cmd)
    scenario("recovery", "normal evaluation after the dependency is restored", [
        ("the run after the broken one (same project, same report store) is VALID again", R6 and R3 and R3["evaluation"]["state"] == "INVALID" and R6["evaluation"]["state"] == "VALID", R6 and R6["evaluation"]["state"]),
        ("with the score it had before the failure", R6 and R1 and R6["health"]["score"] == R1["health"]["score"], (R1 and R1["health"]["score"], R6 and R6["health"]["score"])),
        ("the failure left no trace in it: no evaluator failure, no change claimed against the INVALID report", R6 and not R6["evaluation"]["evaluator_failures"] and R6["health"]["vs_previous"]["delta"] is None and not R6["regressions"],
         R6 and (R6["health"]["vs_previous"], R6["regressions"])),
    ], R6, None, None, "the repeat run above, made after the broken-evaluator run")

# ---------------------------------------------------------------- 5. known application defect
if BLOCK: scenario("known application defect", "detect the defect and attribute it to the application", [], blocker=BLOCK)
else:
    R2, err, secs, cmd = report(broken_game, "full", label="defect")
    D = {d["id"]: d for d in R2["departments"]} if R2 else {}
    F = [f for d in (R2 or {}).get("departments", []) for f in d["findings"]]
    scenario("known application defect", "detect the defect and attribute it to the application", [
        ("the report was produced", R2 is not None, err),
        ("evaluation VALID: the evaluators worked, so the result is about the game", R2 and R2["evaluation"]["state"] == "VALID" and not R2["evaluation"]["evaluator_failures"], R2 and R2["evaluation"]),
        ("the overall score is clearly lower than the healthy game's (at least 10 points)", R2 and R1 and R2["health"]["score"] <= R1["health"]["score"] - 10, (R1 and R1["health"]["score"], R2 and R2["health"]["score"])),
        ("the missing file is found by measurement and named (sprites/hero.png), by more than one department",
         len({f["department"] for f in F if "hero.png" in json.dumps(f) and f["level"] == "verified"}) >= 2, sorted({f["department"] for f in F if "hero.png" in json.dumps(f)})),
        ("the start-up crash is found by playing: the game does not react to input (a measured PLAYCRAFT finding)",
         any(f["department"] == "playcraft" and f["level"] == "verified" and re.search(r"0/\d+ .*(inputs|input)", str(f.get("measured") or f.get("evidence") or "")) for f in F),
         [f["title"] for f in F if f["department"] == "playcraft"][:8]),
        ("PLAYCRAFT's and TestCraft's scores fell against the healthy game", R2 and R1 and D["playcraft"]["quality"]["value"] < R1["health"]["parts"]["playcraft"] and D["testcraft"]["quality"]["value"] < R1["health"]["parts"]["testcraft"],
         R2 and R2["health"]["parts"]),
        ("the defects are blockers or P1 for the project", R2 and any(a["priority"] in ("P0", "P1") and "hero.png" in json.dumps(a) for a in R2["actions"]), R2 and [(a["priority"], a["title"]) for a in R2["actions"]][:6]),
    ], R2, err, secs, cmd)

# ---------------------------------------------------------------- 6. partial evaluation
if BLOCK: scenario("partial evaluation", "keep the valid findings, mark coverage incomplete, no overall score", [], blocker=BLOCK)
else:
    R5, err, secs, cmd = report(partial_game, "quick", label="partial")
    D = {d["id"]: d for d in R5["departments"]} if R5 else {}
    scenario("partial evaluation", "keep the valid findings, mark coverage incomplete, no overall score", [
        ("the report was produced", R5 is not None, err),
        ("evaluation PARTIAL", R5 and R5["evaluation"]["state"] == "PARTIAL", R5 and R5["evaluation"]["state"]),
        ("NO overall score anywhere", R5 and no_number(R5), R5 and R5["health"]),
        ("what was measured is kept with its own score (engineering standard and TestCraft's smoke test)", R5 and set(R5["health"]["parts"]) == {"production", "testcraft"} and D["testcraft"]["quality"]["value"] is not None, R5 and R5["health"]["parts"]),
        ("the evaluators that did not run are named as not run (not failed, not 0), with how to run them",
         R5 and all(D[i]["quality"]["reason"] == "not_run" and D[i]["quality"]["value"] is None for i in ("playcraft", "pixelcraft")) and not R5["evaluation"]["evaluator_failures"]
         and any('refresh: "full"' in str(x.get("why")) for x in R5["not_refreshed"]), {i: D[i]["quality"] for i in ("playcraft", "pixelcraft")} if R5 else None),
        ("coverage is stated", R5 and 0 < R5["health"]["coverage"] < 1 and R5["health"]["measured"] < R5["health"]["of"], R5 and R5["health"]),
    ], R5, err, secs, cmd)

# ---------------------------------------------------------------- 7. the evaluators' runtime is unavailable
missing = os.path.join(WS, "no-studio-runtime")
cmd = f"GITCRAFT_STUDIO_HOME={os.path.relpath(missing, WS)} python3 -m production project-report reference --refresh full --json --require-valid"
say(f"\n$ {cmd}"); t = time.time()
r = subprocess.run([sys.executable, "-m", "production", "project-report", healthy, "--refresh", "full", "--json", "--require-valid", "--out", os.path.join(WS, "reports-unavailable")],
                   cwd=REPO, env=dict(ENV, GITCRAFT_STUDIO_HOME=missing), capture_output=True, text=True)
try: R4 = json.loads(r.stdout)
except ValueError: R4 = None
if R4: R4["_tool_summary"] = {"health": R4["health"]}; R4["_markdown"] = open(R4["paths"]["markdown"]).read()
D = {d["id"]: d for d in R4["departments"]} if R4 else {}
scenario("unavailable evaluator runtime", "report an invalid evaluation, with no misleading score", [
    ("the report was produced", R4 is not None, r.stderr[-400:]),
    ("evaluation INVALID, and the gate refuses it (exit code 3)", R4 and R4["evaluation"]["state"] == "INVALID" and r.returncode == 3, (R4 and R4["evaluation"]["state"], r.returncode)),
    ("NO overall score anywhere", R4 and no_number(R4), R4 and R4["health"]),
    ("every Studio evaluator is an evaluator failure that names the missing runtime and its install command",
     R4 and all(D[i]["status"] == "evaluator_failed" and "install-studio" in D[i]["evaluator_failure"] for i in ("playcraft", "pixelcraft", "testcraft")), {i: D[i].get("evaluator_failure") for i in D} if R4 else None),
    ("nothing is held against the game", R4 and not any(a["priority"] in ("P0", "P1") and set(a["departments"]) & {"playcraft", "pixelcraft", "testcraft", "assetcraft"} for a in R4["actions"]), None),
], R4, None, round(time.time() - t), cmd)
# and through the launcher, the way a session meets it: the tool must not answer with a report
t = time.time(); Rl, errl, secs, cmdl = report(healthy, "full", env={"GITCRAFT_STUDIO_HOME": missing}, label="unavailable")
scenario("unavailable evaluator runtime (through the launcher)", "no score: the tool refuses, or reports INVALID", [
    ("the tool either refuses with the install instruction or returns an INVALID report with no score",
     (Rl is None and re.search(r"install|runtime|built", errl or "", re.I) is not None) or (Rl is not None and Rl["evaluation"]["state"] == "INVALID" and Rl["health"]["score"] is None), errl or (Rl and Rl["health"])),
], Rl, errl, secs, cmdl)

# ---------------------------------------------------------------- verdict
results = [s["result"] for s in SCEN]
verdict = "FAIL" if "FAIL" in results else "NOT VERIFIED" if "NOT VERIFIED" in results else "PASS"
head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
dirty = bool(subprocess.run(["git", "-C", REPO, "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
C = {"certification": "Run GITCRAFT report: scoring integrity, end to end", "verdict": verdict, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commit": head, "uncommitted_changes": dirty,
     "machine": {"evaluators": PRE}, "workspace": WS, "scenarios": SCEN}
md = [f"# Certification: Run GITCRAFT report (scoring integrity, end to end)", "", f"**Verdict: {verdict}** · {C['at']} · commit `{head[:12]}`" + (" + uncommitted changes" if dirty else ""), "",
      "Real evaluators on a real reference game, through `scripts/mcp.sh studiocraft` (guard + sandbox). Nothing is stubbed. Produced by `tests/certify_report.py`.", "",
      "| Scenario | Required behaviour | Result | State | Overall score | Seconds |", "|---|---|---|---|---|---|"]
for s in SCEN:
    e = s["evidence"] or {}
    md.append(f"| {s['scenario']} | {s['required']} | **{s['result']}** | {e.get('state') or '—'} | {e.get('overall_score') if e.get('overall_score') is not None else 'none'} | {s['seconds'] if s['seconds'] is not None else '—'} |")
for s in SCEN:
    e = s["evidence"] or {}
    md += ["", f"## {s['scenario']}: {s['result']}", ""] + ([f"Blocker: {s['blocker']}", ""] if s["blocker"] else []) + ([f"`{s['command']}`", ""] if s["command"] else [])
    md += [f"- {'PASS' if c['ok'] else 'FAIL'} — {c['check']}" + ("" if c["ok"] else f" — {c['detail']}") for c in s["checks"]]
    if e:
        md += ["", f"What the report said: _{e['first_summary_line']}_", "", "| Department | Status | Score | Why not scored | Findings |", "|---|---|---|---|---|"]
        md += [f"| {i} | {d['status']} | {d['score'] if d['score'] is not None else '—'} | {d['reason'] or '—'} | {d['findings']} |" for i, d in e["departments"].items()]
        if e["evaluator_failures"]: md += ["", "Evaluator failures reported:"] + [f"- {x['title']}: {x['why']}" for x in e["evaluator_failures"]]
    elif s["error"]: md += ["", f"Tool answer: `{s['error'][:400]}`"]
out = OUT or WS
os.makedirs(out, exist_ok=True)
json.dump(C, open(os.path.join(out, "certification.json"), "w"), indent=1, default=str); open(os.path.join(out, "certification.md"), "w").write("\n".join(md) + "\n")
say(f"\nCERTIFICATION: {verdict}  ({results.count('PASS')} passed, {results.count('FAIL')} failed, {results.count('NOT VERIFIED')} not verified)\nEvidence: {os.path.join(out, 'certification.md')}")
sys.exit(0 if verdict == "PASS" else 1)
