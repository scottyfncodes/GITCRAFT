"""Persistent production state: one folder per production.

  <store>/<production-id>/
    production.json     spec, discovery, plan (tasks with state, attempts, results, gates), decisions
    events.jsonl        append-only log of everything that happened (state changes, submissions, approvals)
    tasks/<task-id>/    each task's out_dir (department outputs, provenance records, work orders)
    handoffs/<id>.json  the structured hand-off each task received (upstream outputs with hashes)
    REPORT.md           the acceptance report (written by report.write)

Writes are atomic (temp file + rename) and one runner holds the production's lock at a time, so an
interrupted run leaves a readable record that `resume` continues from."""
import contextlib, datetime, fcntl, json, os, re, tempfile, uuid
from . import store_root, inside_roots, VERSION


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def slugify(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:n] or "production"


def new_id(title):
    return f"{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{slugify(title, 32)}-{uuid.uuid4().hex[:4]}"


def path(pid, *parts, root=None):
    base = os.path.realpath(root or store_root())
    p = os.path.realpath(os.path.join(base, os.path.basename(pid), *parts))
    if not (p == base or p.startswith(base + os.sep)): raise ValueError(f"path escapes the production store: {p}")
    return p


def write_json(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), prefix=".tmp-")
    with os.fdopen(fd, "w") as f: json.dump(data, f, indent=1, default=str)
    os.replace(tmp, p)


def create(prod, root=None):
    base = os.path.realpath(root or store_root())
    if not inside_roots(base):
        raise PermissionError(f"GITCRAFT policy: the production store {base} is outside the workspace roots")
    d = path(prod["id"], root=base); os.makedirs(os.path.join(d, "tasks"), exist_ok=True); os.makedirs(os.path.join(d, "handoffs"), exist_ok=True)
    prod.setdefault("store", d); prod.setdefault("created", now()); prod["updated"] = now(); prod["production_version"] = VERSION
    save(prod); event(prod, "created", title=prod["spec"].get("title"))
    return prod


def save(prod):
    prod["updated"] = now(); write_json(os.path.join(prod["store"], "production.json"), prod)


def load(pid, root=None):
    p = pid if os.path.isabs(pid) and pid.endswith(".json") else path(pid, "production.json", root=root)
    if not os.path.exists(p): raise KeyError(f"no production {pid!r} in {root or store_root()}")
    with open(p) as f: return json.load(f)


def event(prod, kind, **info):
    rec = {"at": now(), "event": kind, **{k: v for k, v in info.items() if v is not None}}
    with open(os.path.join(prod["store"], "events.jsonl"), "a") as f: f.write(json.dumps(rec, default=str) + "\n")
    return rec


def events(prod, limit=None):
    p = os.path.join(prod["store"], "events.jsonl")
    if not os.path.exists(p): return []
    with open(p) as f: lines = [json.loads(l) for l in f if l.strip()]
    return lines[-limit:] if limit else lines


@contextlib.contextmanager
def lock(prod, wait=False):
    """One runner per production. A second runner gets a clear refusal instead of racing the first."""
    f = open(os.path.join(prod["store"], ".lock"), "w")
    try:
        try: fcntl.flock(f, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            raise RuntimeError(f"production {prod['id']} is already running in another process (its lock is held); "
                               "wait for it or check production_status")
        yield
    finally:
        try: fcntl.flock(f, fcntl.LOCK_UN)
        finally: f.close()


def list_all(root=None):
    base = os.path.realpath(root or store_root())
    if not os.path.isdir(base): return []
    out = []
    for d in sorted(os.listdir(base), reverse=True):
        p = os.path.join(base, d, "production.json")
        if not os.path.exists(p): continue
        try:
            with open(p) as f: pr = json.load(f)
        except (OSError, ValueError): continue
        counts = {}
        for t in pr.get("tasks", {}).values(): counts[t["state"]] = counts.get(t["state"], 0) + 1
        out.append({"id": pr["id"], "title": pr["spec"].get("title"), "status": pr.get("status"), "updated": pr.get("updated"), "tasks": counts})
    return out
