#!/usr/bin/env python3
"""PLAYCRAFT test: the game-design department through the real launcher (scripts/mcp.sh studiocraft: guard +
Landlock sandbox, no network), against three fixture games of different genres, plus the scoring rules.

    tests/test_playcraft.py              everything (~5 min: three games played in Chromium, a verify cycle)
    tests/test_playcraft.py --quick      rules, discovery, genres and one played game
    GITCRAFT_PLAYCRAFT_PROOF=<dir>       keep the outputs there (default: a temp workspace)

Checks: repository discovery, genre identification (physics / survival-exploration / arcade), genre-specific
criteria and recommendations, scoring behaviour (evidence levels, inferred-only cap, unplayed confidence), the
play probe really playing (responses, pause, touch targets), the staged plan, the verify cycle on a git repo
(an improvement is detected with no regressions; a bad change trips the guardrails), the combined
GITCRAFT + PLAYCRAFT pass, and routing. Exit 1 on any failure."""
import json, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
try:
    import numpy, PIL  # noqa: F401
except ImportError:
    _vpy = os.path.join(os.environ.get("GITCRAFT_STUDIO_HOME") or os.path.expanduser("~/.gitcraft/studio"), "venv", "bin", "python")
    if os.access(_vpy, os.X_OK) and os.path.realpath(sys.prefix) != os.path.realpath(os.path.dirname(os.path.dirname(_vpy))):
        os.execv(_vpy, [_vpy] + sys.argv)
    raise
sys.path.insert(0, HERE)
from mcp_client import Client

QUICK = "--quick" in sys.argv
ws = os.path.abspath(os.environ.get("GITCRAFT_PLAYCRAFT_PROOF") or tempfile.mkdtemp(prefix="gitcraft-playcraft-"))
os.makedirs(ws, exist_ok=True)
FIX = os.path.join(HERE, "fixtures", "playcraft")
GAMES = {}
for g in ("physics_tower", "survival_raft", "arcade_dodge"):
    d = os.path.join(ws, g); shutil.rmtree(d, ignore_errors=True); shutil.copytree(os.path.join(FIX, g), d); GAMES[g] = d
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog", "catalog.sqlite"),
           GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "history"), GITCRAFT_PLAYCRAFT_ARCHIVE=os.path.join(ws, "no-archive"))   # never the real history
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


# ---------------------------------------------------------------- scoring rules (pure, no browser)
sys.path.insert(0, os.path.join(REPO, "studio"))
import importlib.util
spec = importlib.util.spec_from_file_location("pc_rubric", os.path.join(REPO, "studio", "departments", "playcraft", "rubric.py"))
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
mk = lambda cat, st, lv, imp=3: {"id": f"x.{cat}.{st}.{lv}", "category": cat, "discipline": "game_feel", "title": "t", "status": st, "level": lv, "impact": imp, "effort": 2, "risk": 1, "recommendation": "r"}
cats, ov = R.score([mk("game_feel", "pass", "inferred")] * 5, {}, False, played=False)
check("rules: source-only evidence is capped at 70 and low confidence", cats["game_feel"]["score"] == 70 and cats["game_feel"]["capped_inferred_only"] and ov["confidence"] == "low", cats["game_feel"])
cats, ov = R.score([mk("game_feel", "pass", "verified")] * 4, {}, False)
check("rules: verified passes can score high", cats["game_feel"]["score"] == 100 and cats["game_feel"]["confidence"] == "high", cats["game_feel"])
check("rules: a category with no evidence is 'not tested', not zero", cats["core_gameplay"]["score"] is None and cats["core_gameplay"]["confidence"] == "none")
check("rules: mobile is not scored for a non-mobile game", cats["mobile"]["applicable"] is False)
cats, _ = R.score([mk("technical", "fail", "verified", 5), mk("technical", "pass", "inferred", 5)], {}, False)
check("rules: a verified failure outweighs an inferred pass", cats["technical"]["score"] < 40, cats["technical"])
F = R.findings([mk("technical", "fail", "verified", 5), mk("game_feel", "fail", "inferred", 3)], {})
check("rules: verified technical failures rank first as defects", F[0]["type"] == "defect" and F[1]["type"] == "design", [(f["id"], f["type"]) for f in F])

# ---------------------------------------------------------------- through the sandboxed MCP server
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=env, log=os.path.join(ws, "studiocraft.log"))
tools = {t["name"] for t in c.tools()}
want = {f"playcraft_{a}" for a in ("discover", "play", "assess", "pass", "verify", "full_pass", "genres")}
check("studiocraft lists every PLAYCRAFT action as a tool", want <= tools, sorted(want - tools))
ok, st = c.call("studio_status")
pc = next((d for d in st["departments"] if d["department"] == "playcraft"), None)
check("playcraft is discovered as a Studio department, actions ready", pc and all(v == "ready" for v in pc["actions"].values()), pc)
ok, r = c.call("playcraft_genres", {"out_dir": f"{ws}/genres"})
check("genres: 15 genre profiles with criteria, priorities and testing strategies", ok and r["status"] == "ok" and len(r["genres"]) == 15, r.get("error") if isinstance(r, dict) else r)
ok, r = c.call("route", {"brief": "make my game feel better and more fun to play"})
check("routing: a game-feel brief goes to playcraft", ok and r["chosen"] and r["chosen"]["department"] == "playcraft", r.get("chosen") if isinstance(r, dict) else r)
ok, r = c.call("playcraft_assess", {"project": GAMES["arcade_dodge"], "play": False, "judgements": [{"category": "game_feel", "status": "pass", "evidence": "x", "level": "verified"}], "out_dir": f"{ws}/bad"})
check("judgements cannot claim 'verified'", not ok and "verified" in str(r), r)
ok, r = c.call("playcraft_discover", {"project": "/root", "out_dir": f"{ws}/bad2"})
check("a project outside the workspace roots is refused (GITCRAFT policy)", not ok and "GITCRAFT policy" in str(r), r)

EXPECT = {"physics_tower": "physics_puzzle", "survival_raft": "survival", "arcade_dodge": "arcade"}
for g, genre in EXPECT.items():
    ok, r = c.call("playcraft_discover", {"project": GAMES[g], "out_dir": f"{ws}/out/{g}/discover"})
    gs = [x["genre"] for x in r.get("genre", {}).get("genres", [])] if isinstance(r, dict) else []
    check(f"discover {g}: repo read, primary genre {genre}", ok and r["status"] == "ok" and r["genre"]["primary"] == genre, gs or r)
    if g == "survival_raft": check("discover survival_raft: exploration recognised as a second genre", "exploration" in gs, gs)

ok, r = c.call("playcraft_assess", {"project": GAMES["physics_tower"], "play": False, "out_dir": f"{ws}/out/physics_tower/unplayed"})
cards = json.load(open(os.path.join(r["out_dir"], "playcraft.json"))) if ok else {}
check("unplayed assessment: no category above 70, confidence low, every probe criterion 'not tested'",
      ok and all((v.get("score") or 0) <= 70 for v in cards["categories"].values()) and cards["overall"]["confidence"] == "low" and
      all(x["level"] == "not_tested" for x in cards["results"] if x["kind"] == "probe"), cards.get("overall"))


def run_pass(g, extra, label):
    t = time.time(); ok, r = c.call("playcraft_pass", dict({"project": GAMES[g], "target": GAMES[g], "play_seconds": 3, "out_dir": f"{ws}/out/{g}/pass"}, **extra), timeout=900)
    good = ok and isinstance(r, dict) and r.get("status") == "ok"
    check(f"{label} ({time.time() - t:.0f} s)", good, (r.get("error") if isinstance(r, dict) else r))
    return json.load(open(os.path.join(r["out_dir"], "playcraft.json"))) if good else None


def res(card, cid): return next((x for x in card["results"] if x["id"] == cid), {})


games = ["arcade_dodge"] if QUICK else ["arcade_dodge", "physics_tower", "survival_raft"]
cards = {}
for g in games:
    cards[g] = run_pass(g, {"viewports": ["desktop", "phone"]} if g == "arcade_dodge" else {"viewports": ["desktop"]}, f"pass {g}: discover → play → assess → plan")
a = cards.get("arcade_dodge")
if a:
    check("arcade: the game was played (verified response to Space)", a["played"]["played"] and any(x["responded"] and x["input"] == "key Space" for x in a["metrics"]["responses"]), a["metrics"]["responses"][:3])
    check("arcade: touch input verified on the phone viewport", res(a, "mob.touch").get("status") == "pass" and res(a, "mob.touch").get("level") == "verified", res(a, "mob.touch"))
    check("arcade: the 28 px mute button is caught as a small touch target", res(a, "mob.targets").get("status") in ("partial", "fail"), res(a, "mob.targets"))
    check("arcade: genre criteria applied (instant restart, high score, ramp) from the arcade profile",
          all(res(a, i).get("status") == "pass" and res(a, i).get("genre") == "arcade" for i in ("ar.instant_restart", "ar.high_score", "ar.ramp")), [res(a, i) for i in ("ar.instant_restart", "ar.high_score", "ar.ramp")])
    check("arcade: missing pause is a finding with a recommendation", any(f["id"] in ("px.auto_pause", "px.pause") for f in a["findings"]), [f["id"] for f in a["findings"]][:10])
    check("arcade: every criterion carries an evidence level; verified ones exist", {x["level"] for x in a["results"]} >= {"verified", "inferred"})
    check("arcade: scores are bounded and the overall is not inflated", all(v.get("score") is None or 0 <= v["score"] <= 100 for v in a["categories"].values()) and a["overall"]["score"] < 90, a["overall"])
    check("arcade: report written (markdown + html) with the plan", os.path.exists(os.path.join(ws, "out/arcade_dodge/pass/playcraft_report.md")) and "Implementation plan" in open(os.path.join(ws, "out/arcade_dodge/pass/playcraft_report.md")).read())
p = cards.get("physics_tower")
if p:
    check("physics: physics-puzzle criteria pass from source (fixed step, chain reactions, destruction, aim preview)",
          all(res(p, i).get("status") == "pass" for i in ("pp.fixed_step", "pp.chain_reactions", "pp.destruction", "pp.aim_preview")), [res(p, i).get("status") for i in ("pp.fixed_step", "pp.chain_reactions", "pp.destruction", "pp.aim_preview")])
    check("physics: drag-to-shoot verified on the running game", any(x["responded"] and "drag" in x["input"] for x in p["metrics"]["responses"]), p["metrics"]["responses"])
    check("physics: game state advanced during play (shots/score read from window.game)", any(k.startswith("game.") for k in p["metrics"].get("state_changed") or []), p["metrics"].get("state_changed"))
    check("physics: weights favour game feel and technical consistency", p["weights"]["game_feel"] > 1.2 and p["weights"]["technical"] > 1.2, p["weights"])
s = cards.get("survival_raft")
if s:
    check("survival: start button pressed and the boat responds to the arrow keys", (s["metrics"]["responses"] and any(x["responded"] and "Arrow" in x["input"] for x in s["metrics"]["responses"])), s["metrics"]["responses"])
    check("survival: survival criteria (resource pressure, warning before failure) found", res(s, "sv.resources").get("status") == "pass" and res(s, "sv.warning").get("status") == "pass", [res(s, "sv.resources"), res(s, "sv.warning")])
    check("survival: genre focus names survival tension and navigation", any("tension" in " ".join(x["priorities"]) for x in s["genre_focus"]))

# ---------------------------------------------------------------- verify: a real improvement, then a bad change
if a:
    g = GAMES["arcade_dodge"]; git = lambda *x: subprocess.run(["git", "-C", g, *x], capture_output=True, text=True)
    git("init", "-q", "-b", "main"); git("-c", "user.email=t@t", "-c", "user.name=t", "add", "."); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base")
    git("checkout", "-qb", "playcraft/pause-and-targets")
    run_pass("arcade_dodge", {"viewports": ["desktop", "phone"]}, "verify cycle: baseline pass on a git repo")
    base = os.path.join(ws, "out/arcade_dodge/pass/playcraft.json")
    js = open(os.path.join(g, "game.js")).read()
    js = js.replace("addEventListener('keyup',", "addEventListener('keydown', (e) => { if (e.code === 'KeyP' || e.code === 'Escape') paused = !paused; });\n"
                    "document.addEventListener('visibilitychange', () => { if (document.hidden) paused = true; });\naddEventListener('keyup',", 1)
    open(os.path.join(g, "game.js"), "w").write(js)
    css = open(os.path.join(g, "style.css")).read().replace("width: 28px; height: 28px;", "width: 44px; height: 44px;"); open(os.path.join(g, "style.css"), "w").write(css)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "pause (P/Esc, auto when hidden); 44 px mute button")
    ok, r = c.call("playcraft_verify", {"baseline": base, "play_seconds": 3, "out_dir": f"{ws}/out/arcade_dodge/verify",
                                        "changes": [{"title": "Pause", "why": "no way to stop a run", "files": [os.path.join(g, "game.js")]}, {"title": "44 px mute button", "why": "touch target", "files": [os.path.join(g, "style.css")]}]}, timeout=900)
    good = ok and r.get("status") == "ok"
    check("verify: improvement passes (no regressions, guardrails clean)", good, (r.get("error"), r.get("compare", {}).get("regressions")) if isinstance(r, dict) else r)
    if good:
        cmp = r["compare"]
        check("verify: the fixed issues are reported as resolved", any("Touch targets" in x for x in cmp["resolved"]) and any("pause" in x.lower() for x in cmp["resolved"]), cmp["resolved"])
        check("verify: before/after report written", os.path.exists(os.path.join(r["out_dir"], "pass_report.md")) and "Before and after" in open(os.path.join(r["out_dir"], "pass_report.md")).read())
    # a bad change: delete a source file, touch deployment settings, add a secret
    os.remove(os.path.join(g, "style.css")); open(os.path.join(g, "vercel.json"), "w").write('{"cleanUrls": true}')
    open(os.path.join(g, ".env"), "w").write("API_KEY='sk-live-0123456789abcdefghijklmnop'\n")
    git("add", "-A"); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "bad")
    ok, r = c.call("playcraft_verify", {"baseline": base, "play_seconds": 2, "viewports": ["desktop"], "out_dir": f"{ws}/out/arcade_dodge/verify_bad"}, timeout=900)
    failed = {x["name"] for x in r.get("checks", []) if not x["ok"]} if isinstance(r, dict) else set()
    check("verify: guardrails catch a deleted source file, deployment change and an added secret",
          isinstance(r, dict) and r.get("status") == "failed" and {"no source files deleted (features kept)", "deployment settings unchanged", "no secret files or secrets added"} <= failed, failed or r)

if not QUICK and s:
    t = time.time(); ok, r = c.call("playcraft_full_pass", {"project": GAMES["survival_raft"], "target": GAMES["survival_raft"], "viewports": ["desktop"], "play_seconds": 3, "out_dir": f"{ws}/out/survival_raft/full"}, timeout=1200)
    check(f"full GITCRAFT + PLAYCRAFT pass: engineering + gameplay, one plan ({time.time() - t:.0f} s)",
          ok and r["status"] == "ok" and r["engineering"].get("smoke") and r["engineering"].get("assets") and r["plan"], r.get("error") if isinstance(r, dict) else r)

c.close()
n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed; outputs in {ws}")
sys.exit(1 if n_fail else 0)
