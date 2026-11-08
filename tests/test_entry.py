#!/usr/bin/env python3
""""Run GITCRAFT": the universal entry point, maturity-aware workflows and preservation (production/entry.py, maturity.py).

    python3 tests/test_entry.py        (~1 min; the server check at the end needs the Studio runtime)

Fixtures: a new idea; a partially built app; a nearly complete app; a finished app (deployed, tested); an existing
game with saves and assets; a repository URL with and without a local clone. Covers maturity + kind with evidence and
confidence, intent routing, read-only discovery, the Decision Room's existing-project defaults (no scaffolding,
rebranding, icon or redesign), the essential question for a finished app with no request, the approval gate,
preservation (deleted files, secrets, CI, game assets and saves) and invocation wiring (skill, global instructions,
the MCP tool)."""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-entry-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import entry, maturity, engine, store, executors
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


def write(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb" if isinstance(text, bytes) else "w") as f: f.write(text)
    subprocess.run(["git", "init", "-q", root], check=True)
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)
    subprocess.run(["git", "-C", root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
    return root


APP_JS = "\n".join(f"function step{i}(x) {{ return x + {i}; }}" for i in range(90))
PAGE = lambda body, extra="": f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>T</title></head><body>{body}<script src="app.js"></script>{extra}</body></html>'

partial = write(os.path.join(ws, "partial"), {
    "README.md": "# Budget Buddy\n\n## Roadmap\n- [x] Add an expense\n- [ ] Categories\n- [ ] Monthly chart\n- [ ] Export CSV\n- [ ] Settings screen\n",
    "index.html": PAGE("<main id=app></main>"),
    "app.js": "function addExpense(e) { list.push(e); }\nfunction chart() { throw new Error('not implemented'); }\n// TODO: categories\n"})
nearly = write(os.path.join(ws, "nearly"), {
    "README.md": "# Recipe Box\n\n## Features\n- Save recipes\n- Search\n- Shopping list\n\n## Roadmap\n- [x] Save recipes\n- [x] Search\n- [x] Shopping list\n- [ ] Print view\n",
    "index.html": PAGE("<main id=app></main>", '<img src="img/logo.png" alt="">'),
    "app.js": APP_JS + "\n// TODO: print view\n"})
finished = write(os.path.join(ws, "finished"), {
    "README.md": "# Tide Times\n\n## Features\n- Tide table for any port\n- Offline\n- Favourites\n",
    "index.html": PAGE("<main id=app></main>"), "app.js": APP_JS, "vercel.json": "{}",
    "tests/app.test.js": "test('ok', () => {});", ".github/workflows/ci.yml": "name: CI\n", ".env": "API_KEY=supersecretvalue123\n",
    ".gitignore": "node_modules\n"})
GAME = ("const cv = document.getElementById('game'), cx = cv.getContext('2d');\nlet player = {x: 0, y: 0, lives: 3}, score = 0, level = 1;\n"
        "const save = JSON.parse(localStorage.getItem('orbit_save') || '{}');\nfunction jump() { player.y -= 10; }\nfunction enemy() { return {x: 5}; }\n"
        "function win() { level++; score += 100; localStorage.setItem('orbit_save', JSON.stringify({level, score})); localStorage.setItem('orbit_best', score); }\n"
        + "\n".join(f"function tick{i}() {{ player.x += {i}; }}" for i in range(80)))
game = write(os.path.join(ws, "orbit"), {
    "README.md": "# Orbit Hopper\n\nA platformer game: jump between planets, collect stars, beat the boss. Saves your level and high score.\n",
    "index.html": PAGE('<canvas id="game"></canvas>').replace("app.js", "game.js"), "game.js": GAME,
    "assets/hero.png": b"\x89PNG\r\n\x1a\n" + b"\0" * 64, "assets/jump.ogg": b"OggS" + b"\0" * 64, "levels/1.json": '{"rows": ["....", "####"]}'})

# ---------------------------------------------------------------- maturity, with evidence and confidence
A = {n: maturity.assess(p) for n, p in (("partial", partial), ("nearly", nearly), ("finished", finished), ("game", game))}
check("assess: a new idea (no folder) is new", maturity.assess(os.path.join(ws, "nope"))["maturity"] == "new")
check("assess: open roadmap items and stubs → partial", A["partial"]["maturity"] == "partial", A["partial"]["evidence"])
check("assess: one open item and a missing file → nearly complete", A["nearly"]["maturity"] == "nearly_complete", A["nearly"]["evidence"])
check("assess: no open items, deploy config and tests → finished (high confidence)", A["finished"]["maturity"] == "finished" and A["finished"]["confidence"] == "high", A["finished"]["evidence"])
check("assess: the game is recognised as a game, with its save keys", A["game"]["kind"] == "game" and {"orbit_save", "orbit_best"} <= set(A["game"]["save_keys"]), A["game"])
inv = A["nearly"]["inventory"]
check("inventory: working vs unfinished vs defects, each with where it came from",
      any(w["what"] == "Search" for w in inv["working"]) and any("Print view" in u["what"] for u in inv["unfinished"])
      and any("img/logo.png" in d["what"] for d in inv["defects"]) and all(x.get("where") for x in inv["defects"] + inv["unfinished"]), inv)
check("inventory: a stub is unfinished, not a reason to rebuild", any("stub" in u["what"] for u in A["partial"]["inventory"]["unfinished"]))
check("assess: every reading carries evidence", all(len(a["evidence"]) >= 3 for a in A.values()))

# ---------------------------------------------------------------- intent
I = lambda t, m: maturity.intent(t, m)[0]
check("intent: build / continue / complete / update / fix / review", I("a habit tracker", "new") == "build" and I("keep building it", "partial") == "continue"
      and I("finish it and ship", "nearly_complete") == "complete" and I("add dark mode", "finished") == "update" and I("the save button is broken", "finished") == "fix"
      and I("review this repo", "finished") == "review")
check("intent: with no request, the maturity decides (partial → continue, nearly → complete, finished → update)",
      I("", "partial") == "continue" and I("", "nearly_complete") == "complete" and I("", "finished") == "update")

# ---------------------------------------------------------------- routing
r = entry.route("Run GITCRAFT on https://github.com/acme/widget please")
check("route: a repository URL without a local clone asks the agent to clone it (no network in the sandbox)", r.get("problem") == "needs_checkout" and "git clone https://github.com/acme/widget" in r["next"], r)
clone = write(os.path.join(ws, "widget"), {"README.md": "# Widget\n", "index.html": PAGE(""), "app.js": APP_JS})
subprocess.run(["git", "-C", clone, "remote", "add", "origin", "https://github.com/acme/widget.git"], check=True)
r = entry.route("Run GITCRAFT on https://github.com/acme/widget")
check("route: a repository URL finds its clone in the workspace by its git remote", r.get("project") == clone and not r.get("problem"), r)
check("route: a local path in the text is the project", entry.route(f"Run GITCRAFT {nearly}")["project"] == nearly)
check("route: 'Run GITCRAFT' is stripped from the request", entry.route("Run GITCRAFT: add dark mode")["request"] == "add dark mode")
check("start: a new project with no idea asks one question (what to make)", entry.start("Run GITCRAFT")["status"] == "needs_input")

# ---------------------------------------------------------------- the workflows (read-only until approved)
fps = {n: engine.fingerprint(p) for n, p in (("partial", partial), ("nearly", nearly), ("finished", finished), ("game", game))}
S = {}
S["new"] = entry.start("Run GITCRAFT: a calm breathing timer for my phone")
S["partial"] = entry.start("Run GITCRAFT", partial)
S["nearly"] = entry.start("Run GITCRAFT: finish it", nearly)
S["finished_vague"] = entry.start("Run GITCRAFT", finished)
S["finished"] = entry.start("Run GITCRAFT: add a dark mode toggle", finished)
S["game"] = entry.start("Run GITCRAFT: add a pause menu", game)
S["review"] = entry.start("Run GITCRAFT: review this game", game)
P = {k: store.load(v["production"]) for k, v in S.items() if v.get("production")}
check("discovery is read-only on every existing project (byte-identical; no folders made)", all(engine.fingerprint(p) == fps[n] for n, p in
      (("partial", partial), ("nearly", nearly), ("finished", finished), ("game", game))))
check("new idea → New Build (icon studio and attribution planned)", S["new"]["routing"]["workflow"] == "build" and "icon.concepts" in P["new"]["tasks"] and "qa.attribution" in P["new"]["tasks"])
check("partial → continue; nearly → complete; finished + request → update; game → update", S["partial"]["routing"]["workflow"] == "continue"
      and S["nearly"]["routing"]["workflow"] == "complete" and S["finished"]["routing"]["workflow"] == "update" and S["game"]["routing"]["workflow"] == "update",
      {k: v.get("routing", {}).get("workflow") for k, v in S.items()})
for k in ("partial", "nearly", "finished", "game"):
    pr = P[k]; T = pr["tasks"]
    check(f"{k}: no scaffolding, icon replacement, branding or identity is planned", T["foundation.scaffold"]["params"]["dirs"] == []
          and not any(t.startswith("icon.") for t in T) and "qa.attribution" not in T and "foundation.identity" not in T and not pr["spec"]["assets"].get("identity"), sorted(T))
    check(f"{k}: preservation is checked, the build never asks for a rebuild", "qa.preserve" in T and "preservation" in {c["id"] for c in pr["spec"]["acceptance"]}
          and not any("Implement a complete" in i for i in T["build"]["work_order"]["instructions"]))
    room = {d["id"]: d for d in pr["decision_room"]}
    check(f"{k}: Decision Room keeps the design, icon and branding by default", room["design"]["recommended"] == "keep" and room["app_icon"]["recommended"] == "leave"
          and room["attribution"]["recommended"] == "leave" and room["scope"]["recommended"] == pr["spec"]["mode"]["workflow"])
check("partial: the build work order carries the unfinished-feature inventory", P["partial"]["tasks"]["build"]["work_order"]["instructions"][0].startswith("This is a partially built")
      and "Discovery inventory" in P["partial"]["tasks"]["build"]["work_order"]["instructions"][0])
check("game: the work order protects gameplay, saves, assets and art direction", any("saved data and progression" in i for i in P["game"]["tasks"]["build"]["work_order"]["instructions"]))
check("game: architecture stays on its engine (alternatives flagged as migrations)", {d["id"]: d for d in P["game"]["decision_room"]}["architecture"]["recommended"] == "canvas"
      and all("migration" in o["tradeoff"] for o in {d["id"]: d for d in P["game"]["decision_room"]}["architecture"]["options"][1:]))
check("update/fix of an existing project: evaluator scores are advisory (reported, not imposed)", P["game"]["tasks"]["qa.playcraft"]["advisory"] and P["finished"]["tasks"]["qa.pixelcraft"]["advisory"]
      and not P["nearly"]["tasks"]["qa.pixelcraft"]["advisory"])
check("existing projects: the engineering standard is advisory (findings in existing code reported, not imposed)", P["finished"]["tasks"]["qa.standards"]["advisory"])
check("review → measured, nothing built: no build, integrate, scaffold or agent task", not any(t["kind"] == "agent" or t["id"] in ("build", "integrate.assets", "foundation.scaffold")
      for t in P["review"]["tasks"].values()) and "qa.smoke" in P["review"]["tasks"], sorted(P["review"]["tasks"]))
rep = open(P["partial"]["discovery_report"]).read()
check("Discovery Report: maturity, confidence, evidence and the working/unfinished/defects inventory", "Project state: partial" in rep and "confidence" in rep and "**Unfinished**" in rep
      and "evidence:" in rep)

# ---------------------------------------------------------------- asking only what is required, and the approval gate
fv = S["finished_vague"]
check("finished app, no change named: one essential question, and the plan cannot be approved yet", fv["status"] == "needs_input"
      and any(d["id"] == "request" for d in fv["decision_room"]) and raises(lambda: engine.decide(fv["production"], approve=True), ValueError))
v = engine.decide(fv["production"], {"request": "add a dark mode toggle"})
pr = store.load(fv["production"])
check("answering it re-plans with the request in the build work order", pr["spec"]["mode"]["request"] == "add a dark mode toggle" and "dark mode" in pr["tasks"]["build"]["work_order"]["instructions"][0])
check("nothing is built before approval (existing project)", "not approved" in str(engine.run(S["game"]["production"]).get("refused")))
v = engine.decide(S["game"]["production"], {"app_icon": "new"})
check("an icon for an existing game happens only when the person asks (Decision Room answer → icon studio planned)", "icon.concepts" in store.load(S["game"]["production"])["tasks"])
v = engine.decide(S["game"]["production"], {"app_icon": "leave"}, approve=True)
check("approval freezes the blueprint with the existing-project defaults", v["stage"] == "approved" and not any(t.startswith("icon.") for t in store.load(S["game"]["production"])["tasks"]))

# ---------------------------------------------------------------- preservation, measured
base = json.load(open(store.load(S["game"]["production"])["tasks"]["qa.preserve"]["params"]["baseline"]))
check("baseline: recorded in the production store at Discovery (hashes, saves, assets)", "game.js" in base["files"] and "orbit_save" in base["save_keys"] and "assets/hero.png" in base["assets"])
work = os.path.join(ws, "orbit-work"); shutil.copytree(game, work)
with open(os.path.join(work, "game.js"), "a") as f: f.write("\nfunction pause() { paused = !paused; }\n")
ok = maturity.preserve_check(work, base, kind="game")
check("preserve: a code change that keeps everything else passes", ok["status"] == "ok" and ok["changed"] == ["game.js"], ok)
open(os.path.join(work, "game.js"), "w").write(GAME.replace("orbit_save", "orbit_v2"))
os.remove(os.path.join(work, "assets", "jump.ogg")); open(os.path.join(work, "assets", "hero.png"), "wb").write(b"\x89PNG\r\n\x1a\nnew art")
bad = maturity.preserve_check(work, base, kind="game")
names = {c["name"]: c for c in bad["checks"]}
check("preserve: a lost save key, a deleted sound and replaced art are all caught", bad["status"] == "failed"
      and not names["saved data still loads: every existing save/progression key is still used"]["ok"]
      and not names["no existing file was deleted (unless approved)"]["ok"] and not names["existing game assets unchanged: art, audio, levels (unless approved)"]["ok"], bad["checks"])
check("preserve: an approved exception passes", maturity.preserve_check(work, base, allow=["assets/*", "assets/jump.ogg"], kind="game")["checks"][0]["ok"])
fb = json.load(open(store.load(S["finished"]["production"])["tasks"]["qa.preserve"]["params"]["baseline"]))
fw = os.path.join(ws, "finished-work"); shutil.copytree(finished, fw)
open(os.path.join(fw, ".env"), "w").write("API_KEY=overwritten\n"); open(os.path.join(fw, "vercel.json"), "w").write('{"x": 1}')
fr = maturity.preserve_check(fw, fb)
check("preserve: secrets (.env) and deployment config are never overwritten silently", fr["status"] == "failed" and not fr["checks"][1]["ok"] and not fr["checks"][2]["ok"], fr["checks"])

# ---------------------------------------------------------------- invocation wiring
skill = open(os.path.join(REPO, "global", "skills", "produce", "SKILL.md")).read()
block = open(os.path.join(REPO, "global", "CLAUDE.md")).read()
check("invocation: the produce skill triggers on 'Run GITCRAFT', repository URLs and existing projects",
      re.search(r"^description:.*Run GITCRAFT", skill, re.M) and "github.com" in skill.split("---")[1] and "production_start" in skill)
check("invocation: the global instructions (every project) route 'Run GITCRAFT' to production_start", "Run GITCRAFT" in block and "production_start" in block)
if executors.studio_python():
    from mcp_client import Client
    c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=dict(os.environ), log=os.path.join(ws, "studiocraft.log"))
    names = {t["name"] for t in c.tools()}
    ok, r = c.call("production_start", {"text": "Run GITCRAFT: add a pause menu", "project": game}, timeout=300)
    check("invocation: studiocraft serves production_start and routes an existing game through the sandbox", "production_start" in names and ok
          and r.get("routing", {}).get("workflow") == "update" and r.get("stage") == "decisions", r if not ok else r.get("routing"))
    c.p.kill()
else:
    print("SKIP the server check: the Studio runtime is not installed")

badl = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(badl)}/{len(results)} passed" + (f"; FAILED: {badl}" if badl else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if badl else 0)
