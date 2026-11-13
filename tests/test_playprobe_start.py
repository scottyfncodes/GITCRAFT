#!/usr/bin/env python3
"""The play probe gets past a title screen whose way in is not called "play" or "start".

Seen on FOXTAIL ("Step Outside"): with no start wording the probe falls back to the dominant button on the title
screen, the one at least twice the area of any other. On a phone the game's 74 px action button, in the page but
lying underneath the title overlay, was counted as a rival, so no button was dominant, the probe never left the
title, and every touch gesture was reported as "touch input does not respond" on a game whose touch controls work.
A control a tap cannot reach is not a way to start: it is no longer a candidate.

The real probe (Playwright + Chromium) plays a fixture; it needs the Studio browser runtime.

    python3 tests/test_playprobe_start.py      (~40 s)"""
import os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "studio"))
from core import runners
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-probe-start-"))
game = os.path.join(ws, "covered_start"); shutil.copytree(os.path.join(HERE, "fixtures", "playcraft", "covered_start"), game)
req = {"root": game, "entry": "index.html", "out_dir": os.path.join(ws, "play"),
       "viewports": [{"name": "desktop", "width": 1280, "height": 720}, {"name": "phone", "device": "iPhone 13"}],
       "wait_ms": 500, "keys": ["ArrowRight", "ArrowDown"], "pointer": True, "start_steps": [], "auto_start": True, "monkey_ms": 1500, "trials": 1,
       "hooks": ["__game"], "pause_keys": []}
res = {r["viewport"]: r for r in runners.node(os.path.join(REPO, "studio", "departments", "playcraft", "playprobe.mjs"), req, timeout=300)["results"]}
for vp in ("desktop", "phone"):
    s = res[vp].get("start") or {}
    check(f"{vp}: the title's own button is found without any start wording", s.get("method") == "button" and s.get("text") == "Step Outside", s)
    check(f"{vp}: the probe is in the game afterwards (the run's state says so)", "__game.steps" in (res[vp].get("state_changed") or [])
          or (res[vp].get("hooks_after") or {}).get("__game.state") == "playing" or res[vp].get("hooks_found"), {k: res[vp].get(k) for k in ("state_changed", "hooks_found")})
check("phone: the covered action button did not make the probe give up", (res["phone"].get("start") or {}).get("method") != "none", res["phone"].get("start"))

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
