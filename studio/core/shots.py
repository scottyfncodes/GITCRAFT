"""The shot list, shared by TestCraft (capture), PIXELCRAFT (its screens) and PLAYCRAFT (evidence beside its play frames).

A product's shot list (<art-direction>/shots.json, docs/visual-direction.md) names the screens that matter and how to
reach each with real content on screen. capture() runs core/web/shots.mjs; a shot that is never reached is reported
NOT SEEN with its reason and is never offered as evidence. Nothing here scores anything."""
import json, os
from . import runners
from .contract import StudioError

PROBE_STEPS = {"click", "tap", "selector", "fill", "press", "goto", "back", "wait", "expect", "text", "settle_ms"}   # PIXELCRAFT's journey vocabulary


def load(path):
    try: spec = json.load(open(path))
    except (OSError, ValueError) as e: raise StudioError(f"cannot read the shot list {path}: {e}")
    shots = [s for s in spec.get("shots") or [] if isinstance(s, dict) and s.get("id")]
    if not shots: raise StudioError(f"the shot list {path} has no shots")
    return spec, shots


def capture(where, shots, viewports, out_dir, timeout=None):
    """where: {root, entry} or {url, entry}; viewports: [{name, width, height, mobile?} | {name, device}] → [{id, name, kind, moment, captures: [...]}]"""
    os.makedirs(out_dir, exist_ok=True)
    return runners.node("shots.mjs", {**where, "out_dir": out_dir, "viewports": viewports, "shots": shots},
                        timeout=timeout or 90 + len(shots) * len(viewports) * 40)["shots"]


def summary(res):
    return {"reached": [f"{s['id']}@{c['viewport']}" for s in res for c in s["captures"] if c.get("reached")],
            "not_seen": [{"shot": s["id"], "viewport": c["viewport"], "reason": c.get("reason")} for s in res for c in s["captures"] if not c.get("reached")]}
