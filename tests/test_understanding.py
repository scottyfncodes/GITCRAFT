#!/usr/bin/env python3
"""Understanding the assignment, and deciding before building (production/understanding.py, direction.py).

    python3 tests/test_understanding.py        (~20 s; no browser, no Blender)

Twelve different assignments must be read as twelve different jobs: a new game, app, site or tool; assets alone; and,
for a project that exists, continue / complete / one feature / a repair / a redesign / a gameplay pass / polish / an
asset to integrate / an audit / a rebuild. Covers the reading (with the words that caused it), what each plans and
preserves, the essential question before anything destructive, the creative direction gate, the before/after
comparison a redesign or gameplay pass is judged by, the tool build path with its tests, and that v1 plans are untouched."""
import json, os, re, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-understanding-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import entry, intake, engine, planner, understanding, direction, builtins, report, store, discovery
import production_agent
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:500]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


def repo(name, src):
    dst = os.path.join(ws, name); shutil.copytree(src, dst)
    subprocess.run(["git", "init", "-q", dst], check=True); subprocess.run(["git", "-C", dst, "add", "-A"], check=True)
    subprocess.run(["git", "-C", dst, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], check=True)
    return dst


# ---------------------------------------------------------------- the reading: an existing project
C = lambda t, m="finished": understanding.classify(t, m)
A = lambda t, m="finished": (C(t, m)["assignment"], C(t, m)["workflow"], C(t, m)["focus"])
READ = [
    ("keep going", "partial", ("continue", "continue", None)),
    ("finish it and get it live", "nearly_complete", ("complete", "complete", None)),
    ("add dark mode", "finished", ("feature", "update", None)),
    ("add a boss enemy at the end", "partial", ("feature", "update", None)),
    ("the save button is broken", "finished", ("repair", "fix", None)),
    ("the player falls through the floor sometimes", "partial", ("repair", "fix", None)),
    ("the save button does nothing on mobile", "finished", ("repair", "fix", None)),
    ("it won't load on my phone", "finished", ("repair", "fix", None)),
    ("redesign the visuals, it looks ugly", "finished", ("redesign", "update", "visual")),
    ("make it look more professional", "finished", ("redesign", "update", "visual")),
    ("the game feels boring, make it more fun", "finished", ("gameplay", "update", "gameplay")),
    ("improve the controls and game feel", "partial", ("gameplay", "update", "gameplay")),
    ("it's too easy after the first minute", "finished", ("gameplay", "update", "gameplay")),
    ("polish it", "partial", ("polish", "update", "polish")),
    ("make an explosion sound and put it in the game", "partial", ("integrate", "update", "asset")),
    ("I need a new logo", "finished", ("integrate", "update", "asset")),
    ("audit this before launch", "finished", ("audit", "review", None)),
    ("is this any good?", "partial", ("audit", "review", None)),
    ("how far along is it?", "partial", ("audit", "review", None)),
    ("rebuild this from scratch in Phaser", "partial", ("rebuild", "update", None)),
]
wrong = [(t, A(t, m), want) for t, m, want in READ if A(t, m) != want]
check(f"reading: {len(READ)} requests of an existing project are {len({w[0] for _, _, w in READ})} different assignments", not wrong, wrong)
check("reading: every reading quotes the words that decided it", all(C(t, m)["because"] for t, m, _ in READ) and C("it looks dated")["because"] == "'looks dated'")
check("reading: a question is a request for a judgement, never for changes; 'can you add…' is still a request",
      A("should I ship this?")[1] == "review" and A("can you add a settings page?") == ("feature", "update", None), (A("should I ship this?"), A("can you add a settings page?")))
check("reading: 'make the animation smoother' is a change to how it feels, not a new asset", A("make the animation smoother")[0] != "integrate", A("make the animation smoother"))
check("reading: with nothing asked, the maturity decides and says so",
      [A("", m)[1] for m in ("partial", "nearly_complete", "finished")] == ["continue", "complete", "update"] and "default" in C("", "partial")["because"])
check("reading: a rebuild is never a default and carries its question", C("start over")["question"] and "thrown away" in C("start over")["question"] and A("", "partial")[0] != "rebuild")
m = understanding.model("redesign it", {"existing": True, "maturity": "finished", "kind": "game", "save_keys": ["dodge.best"], "deploy": ["vercel.json"],
                                         "inventory": {"working": [{"what": "Pause"}], "unfinished": [], "defects": []}})
check("model: current state, desired state, what is preserved, what done means and how it is proven",
      m["current"]["working"] == ["Pause"] and m["desired"] == "redesign it" and any("dodge.best" in p for p in m["preserve"]) and any("vercel.json" in p for p in m["preserve"])
      and "before and after" in m["done_when"] and "PIXELCRAFT" in m["proof"], m)

# ---------------------------------------------------------------- the reading: nothing exists yet
S = understanding.standalone
alone = ["I need a jump sound effect and a coin pickup sound", "Create a logo for my bakery called Crumb", "A 3D model of a wooden barrel for my game",
         "Make a stone texture", "some background music for my podcast", "generate a skybox"]
check("standalone: a request for assets alone is recognised (where it is going is not what to build)", all(S(t) for t in alone), [t for t in alone if not S(t)])
product = ["A cozy lighthouse keeper game where you guide ships through fog", "Build a habit tracker with sound effects", "a platformer with a jump sound and 3 levels",
           "Make a landing page with a logo for my bakery"]
check("standalone: a product that has assets is still a product", not any(S(t) for t in product), [t for t in product if S(t)])
P = intake.parse
s = P("I need a jump sound effect and a coin pickup sound")
check("intake: sounds alone are a pack of exactly those sounds (no app, icon, credit, music or interface audit)",
      s["deliverable"] == "asset_pack" and list(s["assets"]) == ["sfx"] and {"jump", "coin"} <= set(s["assets"]["sfx"]) and not s["icon"]["required"]
      and not s["attribution"]["required"] and [c["id"] for c in s["acceptance"]] == ["asset_sfx", "release_ready"], (s["deliverable"], s["assets"], [c["id"] for c in s["acceptance"]]))
s = P("A 3D model of a wooden barrel for my game")
check("intake: 'a 3D model … for my game' is the model, not a new game", s["deliverable"] == "asset_pack" and list(s["assets"]) == ["models"] and not s["genres"], (s["deliverable"], s["assets"]))
check("intake: a texture is a material whatever the dimension", P("Make a stone texture")["assets"].get("materials") == ["stone"], P("Make a stone texture")["assets"])
s = P("Make a CLI utility that renames photos by EXIF date")
check("intake: a command-line tool is a tool: no icon, credit, interface audit or gameplay score; its tests are the criterion",
      s["deliverable"] == "tool" and not s["icon"]["required"] and not s["attribution"]["required"] and not s["quality"]["pixelcraft"] and not s["quality"]["playcraft"]
      and [c["id"] for c in s["acceptance"]] == ["tests_pass", "release_ready"], (s["deliverable"], [c["id"] for c in s["acceptance"]]))
s = P("A cozy lighthouse keeper game where you guide ships through fog at night")
check("intake: 'guide ships' is not 'ship it' (no polished bar, no implied sound or identity)", s["quality"]["level"] == "standard" and not s["assets"], (s["quality"]["level"], s["assets"]))
check("intake: 'ship it' still asks for the release bar", P("Build a tide table app, polished and ready to ship")["quality"]["level"] == "polished")

sd = os.path.join(ws, "store")
r = entry.start("Run GITCRAFT: I need a jump sound effect and a coin pickup sound", store_dir=sd)
check("start: assets alone go straight to their department (no production, nothing scaffolded)",
      r["status"] == "direct" and r["routing"]["assignment"] == "asset" and any(st["tool"] == "audiocraft_sfx" for st in r["steps"]) and not os.path.isdir(sd), (r["status"], r.get("steps")))
r = entry.start("A 3D model of a wooden barrel for my game", store_dir=sd)
check("start: one step per named asset, and no guesses (a department's keyword alone is not a route)",
      [(st["tool"], st["params"]) for st in entry.start("I need a jump sound effect and a coin pickup sound", store_dir=sd)["steps"]]
      == [("audiocraft_sfx", {"preset": "coin"}), ("audiocraft_sfx", {"preset": "jump"})])
check("start: a 3D asset is the 3D Department's, and only its", r["status"] == "direct" and len(r["steps"]) == 1 and r["steps"][0]["tool"].startswith("forgecraft"), r.get("steps"))
r = entry.start("Create a logo for my bakery called Crumb", store_dir=sd)
check("start: a logo goes to VectorCraft (the 2D tools are routed too)", r["status"] == "direct" and [st["tool"] for st in r["steps"]] == ["vectorcraft"], r.get("steps"))

# ---------------------------------------------------------------- an existing game: each assignment plans a different job
game = repo("dodge", os.path.join(HERE, "fixtures", "playcraft", "arcade_dodge"))
before = subprocess.run(["git", "-C", game, "status", "--porcelain"], capture_output=True, text=True).stdout
G = lambda text: entry.start(text, game, store_dir=sd)
T = lambda r: store.load(r["production"], sd)["tasks"]
r = G("redesign the visuals, it looks dated"); t = T(r); sp = store.load(r["production"], sd)["spec"]
check("redesign: the interface is measured before anything changes, and the look is decided before the build",
      t["baseline.pixelcraft"]["action"] == "audit" and t["baseline.pixelcraft"]["advisory"] and t["design.direction"]["work_order"]["expected"][0]["keys"] == ["product", "done_when", "art"]
      and {"design.direction", "baseline.pixelcraft"} <= set(t["build"]["depends_on"]) and "baseline.pixelcraft" in t["design.direction"]["depends_on"], sorted(t))
check("redesign: judged by the before/after comparison (a gate), not by an absolute score; gameplay is not gated",
      t["qa.pixelcraft"]["action"] == "verify" and t["qa.pixelcraft"]["params"]["baseline"] == {"$from": "baseline.pixelcraft", "role": "audit", "format": "json"}
      and not t["qa.pixelcraft"]["advisory"] and t["qa.playcraft"]["action"] == "pass" and t["qa.playcraft"]["advisory"] and "baseline.playcraft" not in t, t["qa.pixelcraft"])
check("redesign: the brief changes presentation only, and the criterion says how it is proven",
      "What it does stays exactly as it is" in t["build"]["work_order"]["instructions"][0] and "never the play" in " ".join(t["build"]["work_order"]["instructions"])
      and any("before and after" in c["text"] for c in sp["acceptance"] if c["id"] == "interface_quality") and "qa.preserve" in t, t["build"]["work_order"]["instructions"][:1])
check("redesign: the understanding travels with the plan (assignment, focus, what is preserved, what done means)",
      r["understanding"]["assignment"] == "redesign" and r["routing"]["focus"] == "visual" and sp["mode"]["preserve"] and "PIXELCRAFT" in sp["mode"]["done_when"]
      and "Redesign how it looks" in next(d for d in r["decision_room"] if d["id"] == "scope")["question"], r["understanding"])
r = G("the game feels boring, make it more fun"); t = T(r)
check("gameplay: the game is played before the change and compared after it; the direction is about play; the look is not gated",
      t["baseline.playcraft"]["action"] == "pass" and t["qa.playcraft"]["action"] == "verify" and not t["qa.playcraft"]["advisory"]
      and t["design.direction"]["work_order"]["expected"][0]["keys"] == ["product", "done_when", "play"] and "baseline.pixelcraft" not in t and t["qa.pixelcraft"]["advisory"]
      and "Find the cause in play" in t["build"]["work_order"]["instructions"][0], sorted(t))
r = G("polish it"); t = T(r)
check("polish: both comparisons, no new features", {"baseline.pixelcraft", "baseline.playcraft"} <= set(t) and t["qa.pixelcraft"]["action"] == t["qa.playcraft"]["action"] == "verify"
      and "No new features" in t["build"]["work_order"]["instructions"][0], sorted(t))
r = G("the player falls through the floor sometimes"); t = T(r)
check("repair: a described defect is a fix (no direction, no baseline, nothing redesigned)", r["routing"]["workflow"] == "fix" and r["routing"]["assignment"] == "repair"
      and not any(k.startswith(("design.", "baseline.")) for k in t) and "Fix the reported problem" in t["build"]["work_order"]["instructions"][0], sorted(t))
r = G("add a boss enemy at the end"); t = T(r)
check("feature: one named change (no direction, no baseline; scores advisory)", r["routing"]["assignment"] == "feature" and not any(k.startswith(("design.", "baseline.")) for k in t)
      and t["qa.playcraft"]["advisory"] and t["qa.playcraft"]["action"] == "pass", sorted(t))
r = G("make an explosion sound and put it in the game"); t = T(r)
check("integrate: the asset is made by its department and wired in beside what exists", r["routing"]["assignment"] == "integrate" and any(k.startswith("audio.sfx") for k in t)
      and "replace nothing without approval" in t["build"]["work_order"]["instructions"][0], t["build"]["work_order"]["instructions"][0])
r = G("is this any good?"); t = T(r)
check("audit: a question measures and reports; no build, no work order, nothing changed", r["routing"]["workflow"] == "review" and "build" not in t
      and not any(x["kind"] == "agent" for x in t.values()), sorted(t))
r = G("rebuild this from scratch in Phaser"); pid = r["production"]
room = {d["id"]: d for d in r["decision_room"]}
check("rebuild: nothing is replaced on a guess: one essential question, and approval is refused until it is answered",
      r["routing"]["assignment"] == "rebuild" and "carry_over" in room and "essential" in room["carry_over"]["why"]
      and "carry_over" in str(raises(lambda: engine.decide(pid, approve=True, store_dir=sd), ValueError)), sorted(room))
engine.decide(pid, answers={"carry_over": "keep the best score and the sprites; the code may go"}, store_dir=sd)
ins = " ".join(store.load(pid, sd)["tasks"]["build"]["work_order"]["instructions"])
check("rebuild: the person's answer is in the work order, and bounds what may be replaced", "keep the best score and the sprites" in ins and "replace only that" in ins, ins[:300])
check("read-only: planning six assignments changed nothing in the project", subprocess.run(["git", "-C", game, "status", "--porcelain"], capture_output=True, text=True).stdout == before)

app = repo("taskboard", os.path.join(HERE, "fixtures", "pixelcraft", "taskboard"))
r = entry.start("the controls feel sluggish", app, store_dir=sd); t = T(r)
check("an app is never given a gameplay pass: 'the controls feel sluggish' is about its interface", r["routing"]["focus"] == "visual" and "baseline.playcraft" not in t
      and "qa.playcraft" not in t and "baseline.pixelcraft" in t, (r["routing"], sorted(t)))

# ---------------------------------------------------------------- new builds: direction first; v1 untouched
spec = P("Build a small mobile-first arcade game called Lantern Drift with sound")
disc = {"project": {"exists": False, "path": None}, "runtimes": {}}
p1, p2 = planner.build(json.loads(json.dumps(spec)), disc, version=1), planner.build(json.loads(json.dumps(spec)), disc, version=2)
check("new game (v2): the direction covers the look and the play, and the build is held to it",
      p2["tasks"]["design.direction"]["work_order"]["expected"][0]["keys"] == ["product", "done_when", "art", "play"] and "design.direction" in p2["tasks"]["build"]["depends_on"]
      and any("window.__game" in i for i in p2["tasks"]["build"]["work_order"]["instructions"]) and any("play.feedback" in i for i in p2["tasks"]["build"]["work_order"]["instructions"]),
      p2["tasks"]["build"]["depends_on"])
check("v1 plans are exactly what they were: no direction task, no direction lines", "design.direction" not in p1["tasks"]
      and not any("direction.json" in i for i in p1["tasks"]["build"]["work_order"]["instructions"]))
check("no house style: the direction's brief names no palette, typeface or genre of its own",
      not re.search(r"#[0-9a-f]{6}|\b(inter|roboto|poppins|purple|violet|gradient|glassmorphism|neon)\b", json.dumps(direction.work_order(spec)).lower()))
tool = P("Make a CLI utility that renames photos by EXIF date")
pt = planner.build(json.loads(json.dumps(tool)), disc, version=2)
check("new tool: built to its brief and proven by its own tests (no scaffolded web app, no direction, no icon)",
      pt["tasks"]["build"]["kind"] == "agent" and pt["tasks"]["qa.tests"]["action"] == "check_tests" and "qa.tests" in pt["tasks"]["release.report"]["depends_on"]
      and not any(k.startswith(("design.", "icon.", "qa.pixelcraft", "qa.smoke")) for k in pt["tasks"]) and planner.validate(pt) == [], sorted(pt["tasks"]))

# ---------------------------------------------------------------- the direction gate measures; it does not judge taste
od = os.path.join(ws, "dir"); os.makedirs(od)
V = lambda **over: {c["name"]: c["ok"] for c in direction.validate(production_agent.direction({"out_dir": od}, **over)[0])}
good = V()
check("direction: a complete, specific direction passes every check", all(good.values()) and len(good) >= 18, [k for k, v in good.items() if not v])
bad = lambda v: [k for k, ok in v.items() if not ok]
art, play = production_agent.DIRECTION_ART, production_agent.DIRECTION_PLAY
check("direction: adjectives are not a concept", bad(V(art=dict(art, concept="A clean, modern, minimalist and professional look"))) == ["art.concept: one idea from this product's world, not adjectives"])
check("direction: illegible text is refused with the measured ratio",
      any("≥ 4.5" in k for k in bad(V(art=dict(art, palette=dict(art["palette"], text="#3A3760"))))))
check("direction: a game without feedback, a curve or playtest questions is not decided",
      {k.split(":")[0] for k in bad(V(play=dict(play, feedback=play["feedback"][:2], curve=[], playtest=["fun"])))} == {"play.feedback", "play.curve", "play.playtest"})
check("direction: placeholders are not decisions", "product: promise, audience and context are stated" in bad(V(product={"promise": "TODO", "audience": "tbd", "context": "..."})))
hc = direction.human_checks(json.load(open(production_agent.direction({"out_dir": od})[0])))
check("direction: fun is handed to a person, never claimed", [q["kind"] for q in hc].count("playtest") == 3 and any(q["kind"] == "look" for q in hc))
prod = {"tasks": {"design.direction": {"id": "design.direction", "outputs": [{"path": os.path.join(od, "direction.json"), "role": "direction"}]}}}
md = "\n".join(report.needs_a_person(prod))
check("report: 'Needs a person' lists the playtest questions as open, not passed", "## Needs a person" in md and "- [ ] Did you start a second run without being asked?" in md
      and "cannot tell whether it is fun" in md, md[:300])
check("report: a production without a direction has no such section", report.needs_a_person({"tasks": {}}) == [])

# ---------------------------------------------------------------- a tool's tests are really run
tp = os.path.join(ws, "renamer"); os.makedirs(os.path.join(tp, "tests"))
open(os.path.join(tp, "renamer.py"), "w").write("def slug(s):\n    return s.strip().lower().replace(' ', '-')\n")
open(os.path.join(tp, "tests", "test_renamer.py"), "w").write("import os, sys, unittest\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\nimport renamer\n\n"
     "class T(unittest.TestCase):\n    def test_slug(self): self.assertEqual(renamer.slug(' A B '), 'a-b')\n\nif __name__ == '__main__': unittest.main()\n")
ctx = lambda req=True: {"project": tp, "params": {"required": req}, "out_dir": od, "task": {"timeout": 120}}
ok = builtins.check_tests(ctx())
check("tool tests: run the way the project runs them, and pass", ok["status"] == "ok" and ok["exit_code"] == 0 and os.path.isfile(os.path.join(od, "tests.json")), ok)
open(os.path.join(tp, "renamer.py"), "w").write("def slug(s):\n    return s\n")
ko = builtins.check_tests(ctx())
check("tool tests: a failing test fails the check, with the output", ko["status"] == "failed" and "AssertionError" in ko["output_tail"], ko.get("output_tail", "")[-200:])
shutil.rmtree(os.path.join(tp, "tests"))
check("tool tests: a new tool with no tests is not done; an existing one without tests is unverified, never passed off as tested",
      builtins.check_tests(ctx())["status"] == "failed" and builtins.check_tests(ctx(False))["checks"][0].get("category") == "unverified")

fails = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(fails)}/{len(results)} passed" + ("" if not fails else "\nFAILED:\n  " + "\n  ".join(fails)))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if fails else 0)
