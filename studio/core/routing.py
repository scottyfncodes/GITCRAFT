"""Department routing: which department and action fit a free-text request.

Scores every department by its manifest keywords and every action by its name, summary words
and the enum values of its parameters (e.g. "explosion" is an sfx preset and an fxcraft effect),
and proposes parameters from matched enum values. 3D modelling requests are pointed at the 3D
Department (ForgeCraft `route`/`generate`). Advice only: the caller decides."""
import re
from . import contract

THREE_D = ["3d model", "3d", "mesh", "glb", "low-poly model", "model of", "sculpt", "character model", "prop model", "fbx", "blender model"]
# game design (missions, story, systems, balance) is DESIGNCRAFT (gamedesign/), not a Studio department: pointed at, like 3D
GAME_DESIGN = ["game design", "design review", "mission design", "quest design", "narrative design", "story review", "level design review",
               "game balance", "economy balance", "progression design", "pacing", "designcraft"]
STOP = {"a", "an", "the", "for", "of", "to", "and", "with", "my", "me", "make", "create", "generate", "some", "that", "in", "on", "it", "is", "from", "this", "game"}


def _spans(text, w):
    return [m.span() for m in re.finditer(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", text)]


def _hits(text, words, phrases=()):
    """Words found in the text, ignoring a hit that only occurs inside a longer phrase some manifest names
    ("capture" inside "motion capture" is not a vote for gameplay capture)."""
    out = []
    for w in words:
        sp = _spans(text, w)
        if sp and any(not any(a <= s and e <= b and (b - a) > (e - s) for a, b in phrases) for s, e in sp): out.append(w)
    return out


def route(brief, limit=5):
    t = (brief or "").lower()
    cands = []
    phrases = sorted({sp for d in contract.departments() for kw in contract.manifest(d).get("keywords", []) +
                      [k for spec in contract.manifest(d)["actions"].values() for k in spec.get("keywords", [])] if " " in kw for sp in _spans(t, kw)})
    for d in contract.departments():
        m = contract.manifest(d)
        dk = _hits(t, m.get("keywords", []), phrases)
        for a, spec in m["actions"].items():
            words = [a.replace("_", " ")] + spec.get("keywords", [])
            ak = _hits(t, words, phrases)
            params, enum_hits = {}, []
            for pn, ps in spec.get("params", {}).get("properties", {}).items():
                found = []
                for v in ps.get("enum", []) if isinstance(ps.get("enum"), list) else []:
                    if not isinstance(v, str) or len(v) <= 2: continue
                    # word forms: rust → rusty / rusted, sunset → sunsets
                    hit = re.search(r"(?<![a-z0-9])" + re.escape(v.replace("_", " ").lower()) + r"(?:s|es|y|ed|ing)?(?![a-z0-9])", t)
                    if hit: found.append((hit.start(), v))
                if found:
                    params[pn] = min(found)[1]; enum_hits += [v for _, v in found]   # the value named first in the brief
            summary_words = {w for w in re.findall(r"[a-z]{4,}", spec["summary"].lower())} - STOP
            sk = [w for w in summary_words if re.search(r"(?<![a-z])" + w + r"(?![a-z])", t)]
            score = 3 * len(dk) + 4 * len(ak) + 3 * len(enum_hits) + 0.5 * len(sk)
            if score > 0:
                cands.append({"department": d, "action": a, "score": round(score, 1), "params": params,
                              "why": {"department_keywords": dk, "action_words": ak, "parameter_values": enum_hits, "summary_words": sk[:6]}})
    cands.sort(key=lambda c: -c["score"])
    three = _hits(t, THREE_D)
    res = {"brief": brief, "suggestions": cands[:limit]}
    if three:
        res["three_d"] = {"matched": three, "use": "forgecraft route / generate (the 3D Department)"}
    design = _hits(t, GAME_DESIGN)
    if design:
        res["game_design"] = {"matched": design, "use": "DESIGNCRAFT: python3 -m gamedesign assess <game-repo> (or a production's qa.designcraft); docs/designcraft.md"}
    res["chosen"] = cands[0] if cands and not ((three or design) and cands[0]["score"] < 6) else None
    if not res["chosen"]:
        res["note"] = "3D modelling request: use ForgeCraft" if three else "game-design review: use DESIGNCRAFT (gamedesign/)" if design else "no department matched; describe the deliverable (sound, terrain, material, level, effect, cinematic, test, asset)"
    return res
