#!/usr/bin/env python3
"""PLAYCRAFT is told only what the person said about the game; the rest it detects from the game.

Seen on SNOW PATROL ("Run GITCRAFT: review this game"): intake's defaults (genre not named → arcade; no mobile
words → mobile_first False) were passed to PLAYCRAFT as facts. An exploration / simulation game was scored with
the arcade profile and its mobile category was not scored at all ("not a mobile game"), although PLAYCRAFT on its
own detects the genres and scores mobile 95 for the same build.

    python3 tests/test_playcraft_hints.py      (< 5 s)"""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-hints-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_PRODUCTION_ISOLATED=os.path.join(ws, "isolated-home"))
from production import intake, planner, engine
results = []


def check(label, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (f"  [{detail}]" if detail and not cond else ""))


def hints(prompt):
    return planner._playcraft_hints(intake.parse(prompt))


h = hints("Run GITCRAFT: review this game")
check("nothing said about genre or platform: PLAYCRAFT detects both (no genres, no mobile flag)", h == {"genres": None, "mobile": None}, h)
s = intake.parse("Run GITCRAFT: review this game")
check("...the intake default is still recorded, as an assumption", s["genres"] == ["arcade"] and s["genres_assumed"]
      and any("genre not named" in a for a in s.get("assumptions", [])), (s["genres"], s.get("genres_assumed")))

h = hints("Build a mobile racing game with touch controls")
check("a stated genre and mobile intent are passed on", h["genres"] and "racing" in h["genres"] and h["mobile"] is True, h)

h = hints("Make a desktop only puzzle game")
check("'desktop only' is stated: mobile is off", h["mobile"] is False, h)

old = {"genres": ["arcade"], "platform": {"mobile_first": False}}
check("a spec made before this change: a mobile 'no' was never stated, so it is detected", planner._playcraft_hints(old)["mobile"] is None,
      planner._playcraft_hints(old))

# end to end through the planner: the PLAYCRAFT task of a review carries no assumed hints
game = os.path.join(ws, "g"); os.makedirs(os.path.join(game, "src"))
open(os.path.join(game, "index.html"), "w").write('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><title>G</title></head>'
                                               '<body><canvas></canvas><script src="main.js"></script></body></html>\n')
open(os.path.join(game, "main.js"), "w").write("let score=0;requestAnimationFrame(function f(){requestAnimationFrame(f)});\n")
pr = engine.plan("Run GITCRAFT: review this game", game)
pc = (pr.get("tasks") or {}).get("qa.playcraft") if isinstance(pr.get("tasks"), dict) else None
if pc is None:
    from production import store
    pc = store.load(pr["production"] if "production" in pr else pr["id"])["tasks"].get("qa.playcraft")
check("review plan: the PLAYCRAFT task is not handed the assumed genre or a mobile 'no'", pc and pc["params"].get("genres") is None
      and pc["params"].get("mobile") is None, pc and pc["params"])

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
