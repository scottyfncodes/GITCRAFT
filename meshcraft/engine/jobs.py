"""MeshCraft job records and retries. Standard library only.

Every run_pipeline, blockbench_import and mixamo_apply call is a job: a JSON record in the
library's jobs/ folder with the request, each attempt (time, outcome, error, what was changed
for it), the pipeline steps, and where the result went in the library.

A failed attempt is retried automatically down a ladder of lighter settings, only for failures
that a lighter setting can fix (a texture bake or render running out of room). Problems with the
request itself (bad brief, missing file, path outside the roots) fail at once with the reason.
For run_pipeline the ladder is:
  1. smaller previews (≤ 320 px) and a 512 px bake with no further fallback
  2. previews 256 px, one view, and the texture-bake profiles (web-pbr) dropped: the job is
     then `done_with_fallback` and says which deliverables were dropped
job_retry re-runs a job by hand with its original request, as a new attempt on the same record.
"""
import copy, json, os, time, traceback, uuid
from . import library

NO_RETRY = (ValueError, KeyError, PermissionError, FileNotFoundError, NotADirectoryError, TypeError)


def jobs_dir():
    d = library.path("jobs"); os.makedirs(d, exist_ok=True); return d


def _now(): return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _save(rec):
    library._write_json(os.path.join(jobs_dir(), rec["id"] + ".json"), rec)


def get(job_id):
    p = os.path.join(jobs_dir(), os.path.basename(job_id) + ".json")
    if not os.path.exists(p): raise KeyError(f"no job `{job_id}`")
    with open(p) as f: return json.load(f)


def list_jobs(limit=20, status=None):
    recs = []
    for f in os.listdir(jobs_dir()):
        if not f.endswith(".json"): continue
        try:
            with open(os.path.join(jobs_dir(), f)) as fh: r = json.load(fh)
        except (OSError, ValueError):
            continue
        if status and r.get("status") != status: continue
        recs.append({k: r.get(k) for k in ("id", "tool", "asset_id", "status", "created", "updated", "error")} |
                    {"attempts": len(r.get("attempts", [])), "library": r.get("library")})
    return {"jobs": sorted(recs, key=lambda r: r["created"], reverse=True)[:int(limit)]}


def pipeline_ladder(brief):
    """Lighter variants of a run_pipeline request, in order."""
    prev = brief.get("preview", {}) or {}
    bake_profiles = [p for p in brief.get("profiles", []) if p == "web-pbr"]
    s1 = copy.deepcopy(brief)
    s1["preview"] = dict(prev, size=min(int(prev.get("size", 640)), 320))
    s1["bake"] = {"resolution": 512, "fallbacks": []}
    s2 = copy.deepcopy(s1)
    s2["preview"] = dict(s1["preview"], size=256, views=["three_quarter"])
    s2["profiles"] = [p for p in brief.get("profiles", []) if p not in bake_profiles] or ["three-web-toon"]
    s2.pop("bake", None)
    return [({"brief": s1}, "previews ≤ 320 px and a 512 px bake"),
            ({"brief": s2}, "previews 256 px; dropped " + (", ".join(bake_profiles) or "nothing") + " (texture bake)")]


def run(tool, args, fn, asset_id=None, ladder=(), job_id=None, manual=False):
    """Run fn(args) as a job (or as a new attempt of job_id). Returns (result, job record)."""
    if job_id:
        rec = get(job_id)
    else:
        rec = {"id": f"job-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{uuid.uuid4().hex[:6]}", "tool": tool,
               "asset_id": asset_id, "request": args, "status": "queued", "created": _now(), "attempts": [], "error": None}
    variants = [(args, None)] + list(ladder)
    result, last = None, None
    for i, (a, change) in enumerate(variants):
        att = {"n": len(rec["attempts"]) + 1, "started": _now(), "change": change, "manual": manual and i == 0}
        rec["attempts"].append(att); rec["status"] = "running"; rec["updated"] = _now(); _save(rec)
        t0 = time.time()
        try:
            result = fn(a)
            att.update(status="done", seconds=round(time.time() - t0, 1))
            if isinstance(result, dict) and result.get("steps"): att["steps"] = result["steps"]
            rec["status"] = "done" if i == 0 else "done_with_fallback"; rec["error"] = None
            if change: rec["fallback"] = change
            break
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            att.update(status="failed", seconds=round(time.time() - t0, 1), error=last[:2000], trace=traceback.format_exc(limit=3)[-1500:])
            rec["status"] = "failed"; rec["error"] = last[:2000]
            if isinstance(e, NO_RETRY):
                att["retry"] = "not retried: the request itself is the problem"; break
        finally:
            att["finished"] = _now(); rec["updated"] = _now(); _save(rec)
    if rec["status"] == "failed":
        _save(rec)
        raise RuntimeError(f"job {rec['id']} failed after {len(rec['attempts'])} attempt(s): {last}")
    return result, rec


def attach(rec, **info):
    rec.update(info); rec["updated"] = _now(); _save(rec); return rec
