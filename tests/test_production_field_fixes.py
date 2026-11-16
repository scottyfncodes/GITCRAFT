#!/usr/bin/env python3
"""Regressions found by a real production (RECLAIM, a new game built from one master prompt), fast and offline:

  1. a revision made after the scaffold exists re-planned the new build as an *existing* project and stopped
     measuring its asset, licensing and deployment criteria;
  2. a check that ended "verification incomplete" (blocked, nothing conclusive measured) could never run again;
  3. "ecosystem health" in a game brief selected the *sensitive data* engineering standard;
  4. "the player is not a heroic human ... music should be atmospheric, understated" planned heroic music;
  5. levels the build designs itself left an `asset_levels` criterion that no task measures (never READY);
  6. submitting project files from a shell whose roots do not include the project was refused;
  7. product QA read GITCRAFT's own reports under <project>/gitcraft-out as the product's source.

    python3 tests/test_production_field_fixes.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-prod-field-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PRODUCTION_HOME=os.path.join(ws, "productions"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import intake, engine, store, standards, BLOCKED, PENDING, FAILED
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


GAME = ("Build a mobile-first browser game called Verge about a vine restoring an abandoned city intersection, with sound, music, "
        "an ecosystem health indicator and deployment. The player is not a heroic human. Music should be atmospheric and understated.")

# ---- 3. engineering standard: a game's health bar is not health data
check("standards: 'ecosystem health indicator' is not sensitive data", standards.profile_for("a game with an ecosystem health indicator and soil health", "game")[0] == "personal")
check("standards: a health bar or player health is not sensitive data", standards.profile_for("the player has a health bar and loses health when hit", "game")[0] == "personal")
for text in ("an app that stores patient health records", "track my health data and medication", "a healthcare booking app", "a mental health journal", "a medical intake form"):
    check(f"standards: still sensitive: {text}", standards.profile_for(text, "app")[0] == "sensitive", standards.profile_for(text, "app"))
check("standards: payments stay sensitive", standards.profile_for("a shop with stripe checkout", "app")[0] == "sensitive")

# ---- 4. music mood: what the brief says about the music wins; a negated word is not a choice
s = intake.parse(GAME)
check("intake: 'not a heroic human' + 'music should be atmospheric and understated' → calm, not heroic", s["assets"]["music"]["mood"] == "calm", s["assets"]["music"])
check("intake: a named mood still wins", intake.parse("Build an arcade game with epic heroic music and sound")["assets"]["music"]["mood"] == "heroic")
check("intake: a mood named for the music beats an earlier mood word about something else",
      intake.parse("Build a dark dungeon roguelike game. The soundtrack should be calm and relaxing, with sound effects.")["assets"]["music"]["mood"] == "calm")
check("intake: 'never tense' does not pick tense", intake.parse("Build a cozy farming game with sound and music, never tense or scary")["assets"]["music"]["mood"] == "calm")
check("intake: no mood named → the genre default, listed as an assumption",
      any("music mood not named" in a for a in intake.parse("Build a platformer game with sound and three levels")["assumptions"]))

# ---- 5. levels the build designs are not an integrated-asset criterion
lv = intake.parse("Build a strategy game with sound and three levels")
ids = {c["id"] for c in lv["acceptance"]}
check("intake: levels with no LevelCraft kind add no asset_levels criterion (the build designs them)",
      not lv["assets"]["levels"]["by_levelcraft"] and "asset_levels" not in ids, (lv["assets"]["levels"], sorted(ids)))
pf = intake.parse("Build a platformer game with sound and three levels")
check("intake: LevelCraft levels keep their criterion", pf["assets"]["levels"]["by_levelcraft"] and "asset_levels" in {c["id"] for c in pf["acceptance"]})
off = intake.parse("Build a platformer game with sound and three levels", overrides={"assets": {"levels": {"by_levelcraft": False}}})
check("intake: turning LevelCraft off by override drops the criterion with it", "asset_levels" not in {c["id"] for c in off["acceptance"]})

# ---- 1. a new build stays a new build when it is re-planned after its scaffold exists
proj = os.path.join(ws, "verge")
p = engine.plan(GAME, proj)
pid = p["production"] if "production" in p else p["id"]
prod = store.load(pid)
before_unmeasured = set(prod.get("unmeasured_criteria") or [])
before_tasks = set(prod["tasks"])
check("plan: the new game plans asset, licensing and deployment work", {"audio.music", "qa.assets", "qa.licences"} <= before_tasks and not prod["spec"]["mode"].get("existing"), sorted(before_tasks))
engine.decide(pid, answers={k["id"]: k["recommended"] for k in prod["decision_room"] if k.get("recommended")})
engine.decide(pid, approve=True)
os.makedirs(os.path.join(proj, "assets", "audio"), exist_ok=True)   # what the scaffold and the first integrations leave behind
os.makedirs(os.path.join(proj, "assets", "icons"), exist_ok=True)
own = [("index.html", "<!doctype html><html lang=en><title>Verge</title>"), ("game.js", "// build"), ("assets/audio/music.ogg", "x"), ("assets/icons/icon-192.png", "x"),
       ("assets/icons/favicon.ico", "x")] + [(f"assets/audio/{s}.ogg", "x") for s in prod["spec"]["assets"]["sfx"]]   # every planned sound, integrated
for rel, body in own:
    with open(os.path.join(proj, rel), "w") as f: f.write(body)
before_defs = {k: json.dumps({d: v.get(d) for d in engine.TASK_DEF}, sort_keys=True) for k, v in prod["tasks"].items()}
extra = {"extra_tasks": [{"id": "audio.ambience.night", "department": "audiocraft", "action": "ambience", "params": {"kind": "night", "name": "ambience_night"},
                          "ship": {"dest": "$project/assets/audio", "roles": ["*"], "formats": ["ogg"]}}]}
r = engine.revise(pid, extra, "the brief asks for insects at night")
rev = r.get("revision") or {}
check("revise: the preview loses no criterion for a build whose scaffold now exists", not rev.get("would_lose") and not rev.get("problems"), rev)
engine.decide(pid, approve=True)
prod = store.load(pid)
check("revise: applied: still a new build", not prod["spec"]["mode"].get("existing"), prod["spec"]["mode"])
check("revise: applied: every earlier task is still planned, plus the new one", before_tasks | {"audio.ambience.night"} <= set(prod["tasks"]), sorted(before_tasks - set(prod["tasks"])))
check("revise: applied: the production's own integrated sounds are not 'reused' (their tasks stay)", {f"audio.sfx.{x}" for x in prod["spec"]["assets"]["sfx"]} <= set(prod["tasks"]),
      sorted(k for k in before_tasks if k.startswith("audio.sfx") and k not in prod["tasks"]))
redefined = sorted(k for k, v in before_defs.items() if k in prod["tasks"] and json.dumps({d: prod["tasks"][k].get(d) for d in engine.TASK_DEF}, sort_keys=True) != v)
check("revise: applied: adding one task redefines only what now waits for it (integrate.final); the scaffold keeps its starter, nothing else is redone",
      set(redefined) <= {"integrate.final"}, redefined)
check("revise: applied: the project reading is the first one (no files of its own, no asset stems)", not prod["discovery"]["project"].get("asset_stems"), prod["discovery"]["project"].get("asset_stems"))
check("revise: applied: nothing newly unmeasured", set(prod.get("unmeasured_criteria") or []) <= before_unmeasured, prod.get("unmeasured_criteria"))
ex = os.path.join(ws, "existing"); os.makedirs(ex)
with open(os.path.join(ex, "index.html"), "w") as f: f.write("<!doctype html><title>Old</title>")
pe = engine.plan("Add a dark mode toggle to this habit tracker app", ex)
check("plan: a project that existed before its production is still read as existing", store.load(pe.get("production") or pe.get("id"))["spec"]["mode"].get("existing"))

# ---- 2. "verification incomplete" can be measured again; a measured failure still cannot
CHK = "qa.perf" if "qa.perf" in prod["tasks"] else "qa.smoke"
with store.lock(prod):
    t = prod["tasks"][CHK]
    t.update(state=BLOCKED, unverified=[{"check": "desktop: average FPS ≥ 20", "cause": "environment_limited"}], blocked_by=None,
             reason="verification incomplete (not an application failure): desktop: average FPS ≥ 20 [environment_limited]")
    t["attempts"] = [{"n": 1, "outcome": "unverified"}]
    dep = next(x for x in prod["tasks"].values() if CHK in x["depends_on"])
    dep.update(state=BLOCKED, blocked_by=[CHK], reason=f"upstream did not pass: {CHK} (blocked)")
    store.save(prod)
check("retry: needs a reason", raises(lambda: engine.retry(pid, [CHK], ""), ValueError))
check("retry: a check blocked by an upstream task is not retried directly (it names what to retry)",
      CHK in str(raises(lambda: engine.retry(pid, [dep["id"]], "why not"), ValueError)), raises(lambda: engine.retry(pid, [dep["id"]], "why not"), ValueError))
engine.retry(pid, [CHK], "the renderer was optimised; measure the current build")
prod = store.load(pid)
check("retry: an unverified (blocked) check waits to run again", prod["tasks"][CHK]["state"] == PENDING and not prod["tasks"][CHK].get("unverified"), prod["tasks"][CHK]["state"])
check("retry: what was blocked behind it waits again too", prod["tasks"][dep["id"]]["state"] == PENDING, prod["tasks"][dep["id"]]["state"])
check("retry: the request is on the record", any((a.get("retry_requested") or {}).get("reason") for a in prod["tasks"][CHK]["attempts"]))
OTHER = "qa.assets"
with store.lock(prod):
    from production import evaluator   # a real attempt records the evaluator that measured it (tests/test_evaluator_correction.py)
    t = prod["tasks"][OTHER]; t.update(state=FAILED, failure="quality", blocked_by=None); t["attempts"] = [{"n": 1, "outcome": "quality", "evaluator": evaluator.identity(t)}]; store.save(prod)
check("retry: a measured quality failure is still refused", raises(lambda: engine.retry(pid, [OTHER], "please"), ValueError))

# ---- 7. GITCRAFT's own output folder inside the project is not the product's source
from production import gates, qa, artifacts as _art
check("gates: the output-folder names match production/artifacts.py", set(gates.OWN_OUTPUT_DIRS) == set(_art.NAMES), (gates.OWN_OUTPUT_DIRS, _art.NAMES))
site = os.path.join(ws, "site"); os.makedirs(os.path.join(site, "gitcraft-out", "testcraft", "perf"))
with open(os.path.join(site, "index.html"), "w") as f: f.write('<!doctype html><html lang="en"><title>Site</title><img src="a.png" alt="a">')
with open(os.path.join(site, "gitcraft-out", "testcraft", "perf", "perf_report.html"), "w") as f: f.write("<html><img src='data:image/jpeg;base64,AAAA'><script>new Audio('x')</script>")
alt = lambda: next(c for c in qa.evaluate_request(site, {"requested": ["accessibility"], "deliverable": "site"}) if "alt text" in c["name"])
check("qa.request: a report under gitcraft-out/ is not read as the product (no alt-text blocker from it)", alt()["category"] == "pass", alt())
check("gates: ...and its scripts are not the build's source", "new Audio" not in gates._source_text(site, strict=True))
with open(os.path.join(site, "about.html"), "w") as f: f.write("<img src='b.png'>")
check("qa.request: an image without alt text in the product itself is still a blocker", alt()["category"] == "blocker", alt())

# ---- 6. the production's own project is always a valid place for the agent's files
from production import artifacts
os.environ["GITCRAFT_ROOTS"] = os.environ["GITCRAFT_ROOT"] = os.path.join(ws, "elsewhere")   # e.g. the CLI run from another folder
check("submit: a file in the production's project is accepted when the shell's roots are elsewhere", engine._submit_allowed(prod, os.path.join(proj, "index.html")))
check("submit: a file outside the project, the store and the roots is still refused", not engine._submit_allowed(prod, "/etc/passwd") and not engine._submit_allowed(prod, os.path.join(ws, "existing", "index.html")))
os.environ["GITCRAFT_ROOTS"] = os.environ["GITCRAFT_ROOT"] = ws

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
