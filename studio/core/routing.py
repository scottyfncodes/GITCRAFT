"""Department routing: which department and action fit a free-text request.

Scores every department by its manifest keywords and every action by its name, summary words
and the enum values of its parameters (e.g. "explosion" is an sfx preset and an fxcraft effect),
and proposes parameters from matched enum values. 3D modelling requests are pointed at the 3D
Department (ForgeCraft `route`/`generate`). Advice only: the caller decides."""
import re
from . import contract

THREE_D = ["3d model", "3d", "mesh", "glb", "low-poly model", "model of", "sculpt", "character model", "prop model", "fbx", "blender model"]
STOP = {"a", "an", "the", "for", "of", "to", "and", "with", "my", "me", "make", "create", "generate", "some", "that", "in", "on", "it", "is", "from", "this", "game"}


def _hits(text, words):
    return [w for w in words if re.search(r"(?<![a-z0-9])" + re.escape(w.lower()) + r"(?![a-z0-9])", text)]


def route(brief, limit=5):
    t = (brief or "").lower()
    cands = []
    for d in contract.departments():
        m = contract.manifest(d)
        dk = _hits(t, m.get("keywords", []))
        for a, spec in m["actions"].items():
            words = [a.replace("_", " ")] + spec.get("keywords", [])
            ak = _hits(t, words)
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
    res["chosen"] = cands[0] if cands and not (three and cands[0]["score"] < 6) else None
    if not res["chosen"]:
        res["note"] = "3D modelling request: use ForgeCraft" if three else "no department matched; describe the deliverable (sound, terrain, material, level, effect, cinematic, test, asset)"
    return res
