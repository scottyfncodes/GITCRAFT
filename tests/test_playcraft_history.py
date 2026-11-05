#!/usr/bin/env python3
"""PLAYCRAFT Game Quality History test.

Part 1, rules (pure Python, synthetic cards): identity across clone URLs, immutable content-addressed runs, the pinned
baseline, same-commit = measurement, step attribution, verified-only scores kept apart, the measured noise band,
findings resolved/reopened (and resolutions on an unchanged commit not credited), recurring regressions, the live
check, archive export/import.

Part 2, end to end through the real launcher (scripts/mcp.sh studiocraft: guard + Landlock, no network) with a private
store: two fixture games tracked independently, repeated passes on one commit (measurement only), an improvement
committed and verified (an improvement pass with measurable results), a pass on the new commit (genuine improvement),
deployment evidence rules, portfolio answers, export to an archive and automatic import into a fresh store.

    tests/test_playcraft_history.py            (~4 min)
    tests/test_playcraft_history.py --rules    part 1 only (seconds)
Exit 1 on any failure."""
import copy, gzip, importlib.util, json, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
try:
    import numpy, PIL  # noqa: F401  (the MCP part's fixtures are served by the studio; the harness itself needs only stdlib)
except ImportError:
    pass
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("pc_history", os.path.join(REPO, "studio", "departments", "playcraft", "history.py"))
H = importlib.util.module_from_spec(spec); spec.loader.exec_module(H)
results = []


def check(label, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


ws = os.path.abspath(os.environ.get("GITCRAFT_HISTORY_PROOF") or tempfile.mkdtemp(prefix="gitcraft-history-"))
os.makedirs(ws, exist_ok=True)

# ---------------------------------------------------------------- part 1: rules
check("identity: https, .git, ssh and proxy remotes of one repo are one game",
      len({H.normalize_remote(u) for u in ("https://github.com/Owner/Game.git", "git@github.com:owner/game.git", "https://github.com/owner/game", "http://127.0.0.1:4567/git/owner/game")}) == 1,
      [H.normalize_remote(u) for u in ("https://github.com/Owner/Game.git", "git@github.com:owner/game.git", "http://127.0.0.1:4567/git/owner/game")])


def repo(name):
    d = os.path.join(ws, "repos", name); os.makedirs(d, exist_ok=True)
    g = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)
    if not os.path.isdir(os.path.join(d, ".git")):
        g("init", "-q", "-b", "main"); g("remote", "add", "origin", f"https://github.com/acme/{name}.git")
    return d, g


def commit(d, g, msg):
    open(os.path.join(d, "f.txt"), "a").write(msg + "\n"); g("add", "."); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg)
    return g("rev-parse", "HEAD").stdout.strip()


def card(root, head, at, crit, genre="arcade", method="m1"):
    res = [{"id": cid, "category": cat, "discipline": "game_feel", "title": cid, "kind": "probe", "status": st, "level": lv, "impact": 4, "effort": 2, "risk": 1, "recommendation": "do it", "detail": "d"}
           for cid, (cat, st, lv) in crit.items()]
    import importlib.util as u
    rs = u.spec_from_file_location("r", os.path.join(REPO, "studio", "departments", "playcraft", "rubric.py")); R = u.module_from_spec(rs); rs.loader.exec_module(R)
    cats, overall = R.score(res, {}, False)
    finds = R.findings(res, {})
    return json.dumps({"version": "1.0.0", "created": at, "git": {"head": head, "branch": "main", "dirty": [], "source": "recorded"}, "method": method,
                       "game": {"name": os.path.basename(root), "title": os.path.basename(root).title(), "root": root, "engine": {"engines": ["Canvas 2D"]}, "mobile": {"intended": False}},
                       "genre": {"genres": [{"genre": genre, "title": genre.title(), "share": 1.0}], "hybrid": False}, "weights": {}, "played": {"played": True, "viewports": ["desktop"]},
                       "overall": overall, "categories": cats, "results": res, "findings": finds}, sort_keys=True).encode()


store_dir = os.path.join(ws, "rules-store")
S = H.Store(store_dir, archive="", sync=False)
d, g = repo("blip"); c1 = commit(d, g, "one")
A = {"t.touch": ("mobile", "fail", "verified"), "t.text": ("player_experience", "partial", "verified"), "t.code": ("game_feel", "fail", "inferred"), "t.fps": ("technical", "fail", "observed")}
r1 = S.record(card(d, c1, "2026-01-01T10:00:00+00:00", A), "pass", root=d)
r1b = S.record(card(d, c1, "2026-01-01T10:00:00+00:00", A), "pass", root=d)
check("recording the same card twice is a no-op (content-addressed run id)", r1["new"] and not r1b["new"] and r1["run_id"] == r1b["run_id"])
B = dict(A, **{"t.text": ("player_experience", "pass", "verified"), "t.code": ("game_feel", "pass", "inferred")})   # flips on the same commit
r2 = S.record(card(d, c1, "2026-01-01T11:00:00+00:00", B), "pass", root=d)
c2 = commit(d, g, "fix touch")
C = dict(B, **{"t.touch": ("mobile", "pass", "verified"), "t.fps": ("technical", "unknown", "not_tested")})
r3 = S.record(card(d, c2, "2026-01-02T10:00:00+00:00", C), "pass", root=d)
G = H.game_report(S, r1["game_id"])
check("baseline is the first run and stays pinned after more runs", G["baseline"] == r1["run_id"] and S.game(r1["game_id"])["baseline_run"] == r1["run_id"], G["baseline"])
step1 = G["steps"][0]
check("same commit: every change is measurement, verdict says so", step1["same_commit"] and step1["verdict"].startswith("measurement only") and all(c["class"] in ("measurement",) for c in step1["changes"]), step1)
vb = G["vs_baseline"]; cls = {c["id"]: c["class"] for c in vb["changes"]}
check("baseline vs latest: the verified fix on a new commit is a genuine improvement", vb["verdict"] == "genuine improvement" and cls["t.touch"] == "improved (verified)", cls)
check("baseline vs latest: flips that happened on the unchanged commit stay measurement (step attribution)", cls["t.text"] == "measurement" and cls["t.code"] == "measurement", cls)
check("a criterion that stopped being measured is coverage, not improvement", cls["t.fps"] == "coverage", cls)
v0 = S.runs(r1["game_id"])[0]["verified"]
check("verified-only score is separate from the overall and ignores inferred/observed evidence", v0["criteria"] == 2 and v0["overall"] is not None, v0)
check("measured noise band comes from this game's same-commit runs", G["noise"]["measured"] and G["noise"]["samples"] == 1, G["noise"])
F = {f["id"]: f for f in G["findings"]}
check("findings: fixed by a code change is credited; fixed on an unchanged commit is not",
      F["t.touch"]["state"] == "resolved" and F["t.touch"]["resolved_by"] == "change" and F["t.text"]["resolved_by"].startswith("measurement"), {k: (v["state"], v.get("resolved_by")) for k, v in F.items()})
check("findings: an unmeasured one is 'not measured in latest', not fixed", F["t.fps"]["state"] == "not measured in latest", F["t.fps"])
c3 = commit(d, g, "break touch")
D = dict(C, **{"t.touch": ("mobile", "fail", "verified")})
S.record(card(d, c3, "2026-01-03T10:00:00+00:00", D), "pass", root=d)
c4 = commit(d, g, "fix again"); S.record(card(d, c4, "2026-01-04T10:00:00+00:00", C), "pass", root=d)
c5 = commit(d, g, "break again"); S.record(card(d, c5, "2026-01-05T10:00:00+00:00", D), "pass", root=d)
G = H.game_report(S, r1["game_id"]); F = {f["id"]: f for f in G["findings"]}
check("findings: a fixed finding that comes back is reopened (counted)", F["t.touch"]["state"] == "open" and F["t.touch"]["reopened"] == 2, F["t.touch"])
check("regression history: measured regressions between commits, recurring ones flagged", sum(1 for x in G["regressions"] if x.get("criterion") == "t.touch") == 2 and G["recurring_regressions"] and G["recurring_regressions"][0]["times"] == 2, G["recurring_regressions"])
# an earlier-dated run recorded later never moves the baseline
S.record(card(d, c1, "2025-12-31T10:00:00+00:00", A), "assess", root=d)
check("an earlier run imported later never overwrites the baseline", S.game(r1["game_id"])["baseline_run"] == r1["run_id"])
before = open(os.path.join(S.gdir(r1["game_id"]), "runs", r1["run_id"] + ".json"), "rb").read()
S.record(card(d, c1, "2026-01-01T10:00:00+00:00", A), "pass", root=d)
check("run files are never rewritten", open(os.path.join(S.gdir(r1["game_id"]), "runs", r1["run_id"] + ".json"), "rb").read() == before)
check("the full card is kept byte-for-byte (provenance)", gzip.open(os.path.join(S.gdir(r1["game_id"]), "runs", r1["run_id"] + ".card.json.gz")).read() == card(d, c1, "2026-01-01T10:00:00+00:00", A))
# a second game, other genre: independent history
d2, g2 = repo("tower"); k1 = commit(d2, g2, "one")
S.record(card(d2, k1, "2026-01-02T09:00:00+00:00", {"p.fixed_step": ("technical", "pass", "inferred")}, genre="physics_puzzle"), "pass", root=d2)
P, games = H.portfolio(S)
check("two games tracked independently, each with its own genre", {r["title"] for r in P["games"]} == {"Blip", "Tower"} and {tuple(x["genre"] for x in r["genres"]) for r in P["games"]} == {("arcade",), ("physics_puzzle",)})
check("portfolio: recurring regressions and the attention ranking are grounded in recorded runs",
      P["answers"]["recurring_regressions"] and P["answers"]["recurring_regressions"][0]["game"] == "Blip" and P["answers"]["needs_attention_next"][0]["game"] == "Blip",
      P["answers"]["needs_attention_next"][:2])
check("portfolio never ranks raw scores across genres (improved_most only lists genuine verdicts)", all(x["verdict"] == "genuine improvement" for x in P["answers"]["improved_most"]))
# a PLAYCRAFT method change between commits: unconfirmed until the baseline commit is re-measured with the new method
d3, g3 = repo("drift"); m1 = commit(d3, g3, "one")
X = {"x.time": ("player_experience", "pass", "observed"), "x.touch": ("mobile", "fail", "verified")}
q1 = S.record(card(d3, m1, "2026-02-01T10:00:00+00:00", X, method="old"), "pass", root=d3)
m2 = commit(d3, g3, "two")
Y = {"x.time": ("player_experience", "partial", "observed"), "x.touch": ("mobile", "pass", "verified")}
S.record(card(d3, m2, "2026-02-02T10:00:00+00:00", Y, method="new"), "pass", root=d3)
vb = H.game_report(S, q1["game_id"])["vs_baseline"]
check("method changed between commits: measured flips are 'unconfirmed', never genuine", vb["verdict"].startswith("unconfirmed") and vb["counts"]["improved"] == 0 and vb["counts"]["unconfirmed"] == 2, vb["counts"])
# re-measure the baseline commit with the new method: the touch fix reproduces, the time 'regression' does not
g3("checkout", "-q", m1)
S.record(card(d3, m1, "2026-02-03T10:00:00+00:00", {"x.time": ("player_experience", "partial", "observed"), "x.touch": ("mobile", "fail", "verified")}, method="new"), "pass", root=d3)
g3("checkout", "-q", "main")
S.record(card(d3, m2, "2026-02-04T10:00:00+00:00", Y, method="new"), "pass", root=d3)
G3 = H.game_report(S, q1["game_id"]); cls = {c["id"]: c["class"] for c in G3["vs_baseline"]["changes"]}
check("controlled comparison (baseline commit re-measured, same method) confirms the real fix and exposes the method artefact",
      G3["vs_baseline"]["verdict"] == "genuine improvement" and cls["x.touch"].startswith("improved") and cls["x.time"] == "method" and G3["vs_baseline"].get("controlled"), (G3["vs_baseline"]["verdict"], cls))
check("the baseline stays the original run after a re-measurement", G3["baseline"] == q1["run_id"])
# a worktree whose repository git cannot read is refused, never filed under an invented identity
wtd = os.path.join(ws, "worktree-like"); os.makedirs(wtd, exist_ok=True); open(os.path.join(wtd, ".git"), "w").write("gitdir: /nowhere/.git/worktrees/x\n")
try: H.identity(wtd); refused = False
except ValueError as e: refused = "worktree" in str(e)
check("a git worktree with an unreadable repository is refused (no invented 'local' game)", refused)
# live check
b = os.path.join(ws, "build"); os.makedirs(b, exist_ok=True)
open(os.path.join(b, "index.html"), "w").write('<script type="module" src="/assets/index-Ab12Cd34.js"></script><link rel="stylesheet" href="/assets/index-Zz99Yy88.css">')
open(os.path.join(ws, "live_ok.html"), "w").write('<html><script type="module" crossorigin src="/assets/index-Ab12Cd34.js"></script><link rel="stylesheet" crossorigin href="/assets/index-Zz99Yy88.css"></html>')
open(os.path.join(ws, "live_other.html"), "w").write('<script type="module" src="/assets/index-Other999.js"></script><link rel="stylesheet" href="/assets/index-Zz99Yy88.css">')
check("live check: matching fingerprinted assets = this build is live", H.verify_live(os.path.join(ws, "live_ok.html"), b)[0])
check("live check: different assets = not this build", not H.verify_live(os.path.join(ws, "live_other.html"), b)[0])
# archive round trip
arch = os.path.join(ws, "archive"); ex = S.export(arch)
fresh = H.Store(os.path.join(ws, "fresh-store"), archive=arch)
check("export → fresh store imports the archive automatically (same games, runs and baseline)",
      fresh.games() == S.games() and all(len(fresh.runs(x)) == len(S.runs(x)) for x in S.games()) and fresh.game(r1["game_id"])["baseline_run"] == r1["run_id"], ex)
check("the default store lives outside the runtime GITCRAFT upgrades replace",
      not os.path.realpath(H.store_root()).startswith(os.path.realpath(os.path.expanduser("~/.gitcraft/runtime"))), H.store_root())

if "--rules" in sys.argv:
    print(f"\n{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)

# ---------------------------------------------------------------- part 2: end to end through the sandboxed launcher
from mcp_client import Client
hist = os.path.join(ws, "store"); arch2 = os.path.join(ws, "archive2")
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog", "c.sqlite"), GITCRAFT_PLAYCRAFT_HISTORY=hist,
           GITCRAFT_PLAYCRAFT_ARCHIVE=os.path.join(ws, "no-archive"))
GAME = os.path.join(ws, "arcade"); TOWER = os.path.join(ws, "physics")
for src, dst, name in ((os.path.join(HERE, "fixtures", "playcraft", "arcade_dodge"), GAME, "blip"), (os.path.join(HERE, "fixtures", "playcraft", "physics_tower"), TOWER, "topple")):
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(src, dst)
    gg = lambda *a, dst=dst: subprocess.run(["git", "-C", dst, *a], capture_output=True, text=True)
    gg("init", "-q", "-b", "main"); gg("remote", "add", "origin", f"https://github.com/acme/{name}"); gg("add", "."); gg("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
git = lambda *a: subprocess.run(["git", "-C", GAME, *a], capture_output=True, text=True)
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=env, log=os.path.join(ws, "studiocraft.log"))
tools = {t["name"] for t in c.tools()}
check("studiocraft lists the history tools", {"playcraft_history", "playcraft_history_import", "playcraft_history_record", "playcraft_history_export"} <= tools)


def run(tool, args, label, timeout=900):
    t = time.time(); ok, r = c.call(tool, args, timeout=timeout)
    good = ok and isinstance(r, dict) and r.get("status") == "ok"
    check(f"{label} ({time.time() - t:.0f} s)", good, (r.get("error") if isinstance(r, dict) else r))
    return r if good else {}


P0 = dict(project=GAME, target=GAME, viewports=["desktop", "phone"], play_seconds=3, trials=1)
a = run("playcraft_pass", dict(P0, out_dir=f"{ws}/out/p1"), "pass 1 on the arcade fixture is recorded automatically")
check("pass 1 is the baseline of acme--blip, written to the private store", (a.get("history") or {}).get("game_id") == "acme--blip" and a["history"]["vs_baseline"] == "this run is the baseline"
      and os.path.isdir(os.path.join(hist, "games", "acme--blip")), a.get("history"))
b2 = run("playcraft_pass", dict(P0, out_dir=f"{ws}/out/p2"), "pass 2 on the same commit")
check("pass 2 on the same commit: measurement only, baseline unchanged", ((b2.get("history") or {}).get("vs_baseline") or {}).get("verdict") == "measurement only (same commit)"
      and b2["history"]["baseline_run"] == a["history"]["run_id"], b2.get("history"))
check("history.md written beside the report", os.path.exists(f"{ws}/out/p2/history.md") and "Baseline vs latest" in open(f"{ws}/out/p2/history.md").read())
run("playcraft_pass", dict(project=TOWER, target=TOWER, viewports=["desktop"], play_seconds=3, trials=1, out_dir=f"{ws}/out/t1"), "a second game (physics fixture) is recorded separately")
# an improvement: pause + 44 px button, committed on a branch, verified against pass 1
git("checkout", "-qb", "feel")
js = open(os.path.join(GAME, "game.js")).read().replace("addEventListener('keyup',", "addEventListener('keydown', (e) => { if (e.code === 'KeyP' || e.code === 'Escape') paused = !paused; });\n"
                                                         "document.addEventListener('visibilitychange', () => { if (document.hidden) paused = true; });\naddEventListener('keyup',", 1)
open(os.path.join(GAME, "game.js"), "w").write(js)
open(os.path.join(GAME, "style.css"), "w").write(open(os.path.join(GAME, "style.css")).read().replace("width: 28px; height: 28px;", "width: 44px; height: 44px;"))
git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "pause + 44 px button")
v = run("playcraft_verify", dict(baseline=f"{ws}/out/p1/playcraft.json", play_seconds=3, trials=1, out_dir=f"{ws}/out/v1", pr="https://github.com/acme/blip/pull/7",
                                 changes=[{"title": "Pause", "why": "no pause"}, {"title": "44 px mute", "why": "touch target"}]), "verify of the improvement is recorded")
git("checkout", "-q", "main"); git("merge", "-q", "--ff-only", "feel")
p3 = run("playcraft_pass", dict(P0, out_dir=f"{ws}/out/p3"), "pass 3 on the improved commit")
ok, h = c.call("playcraft_history", {"game": "acme/blip", "out_dir": f"{ws}/out/h1"})
rep = json.load(open(f"{ws}/out/h1/history_acme--blip.json")) if ok and h.get("status") == "ok" else {}
check("game history: 4 runs (3 passes + 1 verify), baseline pinned to pass 1", rep.get("runs") == 4 and rep.get("baseline") == a["history"]["run_id"], (rep.get("runs"), rep.get("baseline")))
check("baseline vs latest: genuine improvement from verified criteria (touch target)",
      (rep.get("vs_baseline") or {}).get("verdict") == "genuine improvement" and any(x["id"] == "mob.targets" and x["class"].startswith("improved") for x in rep["vs_baseline"]["changes"]),
      (rep.get("vs_baseline") or {}).get("verdict"))
check("improvement pass recorded with its PR and measurable results", rep.get("improvement_passes") and rep["improvement_passes"][0]["pr"] == "https://github.com/acme/blip/pull/7"
      and any("Touch targets" in x for x in rep["improvement_passes"][0]["measurable"]), rep.get("improvement_passes"))
check("findings tracked across runs: the touch-target finding is fixed by a change", any(f["id"] == "mob.targets" and f["state"] == "resolved" and f["resolved_by"] == "change" for f in rep.get("findings", [])))
check("commits recorded at run time", all(t["commit"] for t in rep.get("timeline", [])), [t["commit"] for t in rep.get("timeline", [])])
# deployments: evidence rules
head = git("rev-parse", "HEAD").stdout.strip()
ok, r = c.call("playcraft_history_record", {"game": "acme/blip", "event": "deployment", "url": "https://blip.example/", "commit": head, "out_dir": f"{ws}/out/d0"})
check("a deployment without evidence is refused (never claimed live)", not ok and "evidence" in str(r), r)
open(os.path.join(ws, "live.html"), "w").write(open(os.path.join(GAME, "index.html")).read())
run("playcraft_history_record", {"game": "acme/blip", "event": "deployment", "url": "https://blip.example/", "commit": head, "live_html": os.path.join(ws, "live.html"), "build_dir": GAME,
                                  "out_dir": f"{ws}/out/d1"}, "a deployment whose live page matches the build is recorded")
run("playcraft_history_record", {"game": "acme/blip", "event": "main", "commit": head, "evidence": "git ls-remote origin refs/heads/main", "out_dir": f"{ws}/out/d2"}, "main head recorded")
ok, h = c.call("playcraft_history", {"game": "acme/blip", "out_dir": f"{ws}/out/h2"})
dep = json.load(open(f"{ws}/out/h2/history_acme--blip.json"))["deployment"] if ok else {}
check("deployment: live-verified (the live page is identical to the build), and the assessed commit is both deployed and main",
      dep.get("level") in ("live-verified",) and dep.get("assessed_is_deployed") is True and dep.get("assessed_is_main") is True, dep)
ok, P = c.call("playcraft_history", {"out_dir": f"{ws}/out/port"})
check("portfolio answers: improved_most names the arcade game with measured criteria", ok and P["answers"]["improved_most"] and P["answers"]["improved_most"][0]["game"] == "BLIP", (P.get("answers") or {}).get("improved_most"))
check("portfolio answers: measurable improvements list the verify pass", ok and any(x["game"] == "BLIP" for x in P["answers"]["measurable_improvements"]))
run("playcraft_history_export", {"dest": arch2, "out_dir": f"{ws}/out/x"}, "export the store to an archive folder")
c.close()
fresh = H.Store(os.path.join(ws, "fresh2"), archive=arch2)
check("a fresh store (new session, upgraded GITCRAFT) imports the archive with every run and the same baseline",
      set(fresh.games()) == {"acme--blip", "acme--topple"} and len(fresh.runs("acme--blip")) == 4 and fresh.game("acme--blip")["baseline_run"] == a["history"]["run_id"]
      and len(fresh.events("acme--blip")) == 2, (fresh.games(), len(fresh.runs("acme--blip"))))
print(f"\n{sum(results)}/{len(results)} passed; outputs in {ws}")
sys.exit(0 if all(results) else 1)
