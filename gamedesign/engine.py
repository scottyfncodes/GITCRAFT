"""The DESIGNCRAFT pipeline: evidence → model → departments → alternatives → score → assessment.

Evidence collection (extract/) never writes to the game repository and never runs its code. Deterministic
analysis (departments/, scoring.py) is separate from design judgement: every finding states its facts with
evidence levels, and the judgement about players is labelled `inferred` unless automated play (PLAYCRAFT,
`simulated`) or a recorded playtest backs it."""
import datetime, re
from . import VERSION, method_hash, model as _model, alternatives, scoring, playcraft_bridge
from .extract import repo as _repo
from .departments import run_all, REGISTRY
from .departments.base import SEV_RANK

SCHEMA = 1


def game_id(bundle):
    r = bundle.get("remote")
    if r: return r.replace("/", "--").lower()
    return re.sub(r"[^a-z0-9]+", "-", bundle["name"].lower()).strip("-")


def _trim(M):
    """The model as the web app needs it (no raw corpus, bounded sizes)."""
    keep = {}
    for k in ("missions", "places", "worlds", "characters", "story", "encounters", "progression", "stages"):
        keep[k] = M[k][:400]
    keep["collections"] = M["collections"]; keep["unclassified"] = M["unclassified"]; keep["limitations"] = M["limitations"]
    keep["maps"] = [{k: v for k, v in m.items() if k != "grid"} for m in M.get("maps", [])]
    keep["branching"] = M.get("branching", [])
    return keep


def assess(root, playcraft=True):
    t0 = datetime.datetime.now(datetime.timezone.utc)
    B = _repo.inspect(root)
    M = _model.build(B)
    sig = (B.get("playcraft_scan") or {}).get("signals") or {}
    pc = playcraft_bridge.latest(B["remote"].split("/")[-1] if B.get("remote") else B["name"]) if playcraft else None
    ctx = {"signals": sig, "docs": B["docs"], "title": B["title"], "playcraft": pc}
    R = run_all(M, ctx)
    findings = sorted([f for r in R.values() for f in r["findings"]], key=lambda f: (SEV_RANK[f["severity"]], f["dept"]))
    props, lab = alternatives.build(M, R, findings, B["title"])
    S = scoring.score(M, R, findings, pc)
    for f in findings:
        ps = [p for p in props if p["finding"] == f["id"]]
        f["proposals"] = [p["id"] for p in ps]
        f["priority"] = max((p["priority"] for p in ps), default=0)
    ranked = sorted([p for p in props], key=lambda p: -p["priority"])
    return {"schema": SCHEMA, "designcraft_version": VERSION, "method": method_hash(), "assessed_at": t0.isoformat(timespec="seconds"),
            "game": {"id": game_id(B), "name": B["name"], "title": B["title"], "pitch": B.get("pitch"), "remote": B.get("remote"),
                     "commit": (B.get("git") or {}).get("commit"), "content_sha256": B["content_sha256"],
                     "engine": ((B.get("playcraft_scan") or {}).get("engine") or {}).get("engines"),
                     "genres": [g["title"] for g in ((B.get("playcraft_scan") or {}).get("genres") or [])]},
            "inspection": {"counts": B["counts"], "files_read": B["files_read"], "collections": M["collections"], "unclassified": M["unclassified"],
                           "unsupported": B["unsupported_counts"], "limitations": M["limitations"], "docs": [{"file": d["file"], "title": d["title"]} for d in B["docs"]][:80],
                           "tests": [{"file": t["file"], "cases": t["cases"], "names": t["names"][:12]} for t in B["tests"]][:80], "screenshots": B["screenshots"],
                           "maps": [m["file"] for m in B["maps"]], "scripts": [s["file"] for s in B["scripts"]]},
            "model": _trim(M), "graph": _model.graph(M, B["title"]), "departments": {k: v for k, v in R.items()},
            "findings": findings, "proposals": ranked, "lab": lab, "score": S, "playcraft": pc,
            "departments_order": [d.NAME for d in REGISTRY]}
