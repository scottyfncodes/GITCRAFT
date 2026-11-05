"""Historical assessments: history/designcraft/<game_id>/<run_id>.json, append-only, plus index.jsonl.

A change between two runs is a *measured change* only when both used the same analysis method (method hash)
and the game's content changed (content hash). Same content + same method = a control re-run; different
method = not comparable, reported as such."""
import datetime, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def store():
    return os.environ.get("GITCRAFT_DESIGNCRAFT_HISTORY") or os.path.join(REPO, "history", "designcraft")


def runs(game_id, root=None):
    d = os.path.join(root or store(), game_id)
    if not os.path.isdir(d): return []
    out = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and f != "game.json":
            try: out.append(json.load(open(os.path.join(d, f))))
            except ValueError: continue
    return out


def summary(A):
    S = A["score"]
    return {"run_id": A.get("run_id"), "assessed_at": A["assessed_at"], "method": A["method"], "commit": A["game"].get("commit"), "content": A["game"]["content_sha256"][:12],
            "overall": S["overall"], "ceiling": S["ceiling"], "coverage": S["coverage"], "confidence": S["confidence"],
            "categories": {k: v["score"] for k, v in S["categories"].items()}, "findings": len(A["findings"]),
            "severity": {s: sum(1 for f in A["findings"] if f["severity"] == s) for s in ("critical", "major", "minor", "info")}}


def compare(prev, cur):
    if not prev: return None
    a, b = summary(prev), summary(cur)
    same_method = a["method"] == b["method"]; same_content = a["content"] == b["content"]
    kind = "control" if same_method and same_content else "measured" if same_method else "method_changed"
    pf = {f["id"] for f in prev["findings"]}; cf = {f["id"] for f in cur["findings"]}
    return {"against": a["run_id"], "kind": kind, "overall": {"from": a["overall"], "to": b["overall"], "delta": b["overall"] - a["overall"]},
            "categories": {k: {"from": a["categories"].get(k), "to": v, "delta": round(v - (a["categories"].get(k) or 0), 1)} for k, v in b["categories"].items()},
            "resolved": sorted(pf - cf), "new": sorted(cf - pf),
            "note": {"control": "Same game content and same method: differences would be noise (none expected; the analysis is deterministic).",
                     "measured": "Same method, changed game content: score changes are measured.",
                     "method_changed": "The analysis method changed between runs: scores are not directly comparable."}[kind]}


def record(A, root=None):
    root = root or store()
    gid = A["game"]["id"]; d = os.path.join(root, gid); os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.fromisoformat(A["assessed_at"]).strftime("%Y%m%dT%H%M%SZ")
    A["run_id"] = f"{ts}-{A['game']['content_sha256'][:8]}"
    prev = runs(gid, root)
    A["compare"] = compare(prev[-1], A) if prev else None
    p = os.path.join(d, A["run_id"] + ".json")
    if os.path.exists(p): raise FileExistsError(f"run {A['run_id']} already recorded; history is append-only")
    with open(p, "w") as fh: json.dump(A, fh, separators=(",", ":"), default=str)
    with open(os.path.join(root, "index.jsonl"), "a") as fh:
        fh.write(json.dumps(dict(summary(A), game=gid, title=A["game"]["title"])) + "\n")
    return p
