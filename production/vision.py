"""The product vision contract: what a project promises, to whom, and what makes it distinct.

A reference for the Creative Review, never a constraint and never a gate: no score, verdict or plan reads it.

  draft(project, fields)            a new version, status "draft" (prefilled from the README when a field is not given)
  approve(project, version, by)     a new version, status "approved", copying that draft; only on a person's word
  latest(pid) / versions(pid)       read

Versions are append-only files `history/vision/<owner--repo>/vN.json` (the committed history when this is a GITCRAFT
checkout; $GITCRAFT_VISION_DIR overrides; an installed runtime without a checkout writes ~/.gitcraft/vision). Nothing is
ever written inside the project. Every clause has an id (promise, audience, context, identity, pillar:N,
differentiator:N, non_goal:N, success:N) that reviews cite."""
import datetime, glob, hashlib, json, os, re
from . import REPO

SINGLE = ("promise", "audience", "context", "identity")
LISTS = {"pillars": "pillar", "differentiators": "differentiator", "non_goals": "non_goal", "success_signals": "success"}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def write_root():
    if os.environ.get("GITCRAFT_VISION_DIR"): return os.path.realpath(os.environ["GITCRAFT_VISION_DIR"])
    if os.path.isdir(os.path.join(REPO, ".git")): return os.path.join(REPO, "history", "vision")
    return os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "vision")


def read_roots():
    if os.environ.get("GITCRAFT_VISION_DIR"): return [write_root()]
    return list(dict.fromkeys([write_root(), os.path.join(REPO, "history", "vision"),
                               os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "vision")]))


def versions(pid):
    seen = {}
    for r in read_roots():
        for p in glob.glob(os.path.join(r, pid or "-", "v*.json")):
            try: V = json.load(open(p))
            except (OSError, ValueError): continue
            seen.setdefault(V.get("version"), dict(V, _path=p))
    return [seen[k] for k in sorted(k for k in seen if isinstance(k, int))]


def latest(pid):
    v = versions(pid)
    return v[-1] if v else None


def clauses(V):
    """{clause id: text} for every stated clause of a vision version."""
    out = {}
    F = (V or {}).get("fields") or {}
    for k in SINGLE:
        t = (F.get(k) or {}).get("text") if isinstance(F.get(k), dict) else F.get(k)
        if t: out[k] = t
    for k, pre in LISTS.items():
        for i, x in enumerate(F.get(k) or [], 1):
            t = x.get("text") if isinstance(x, dict) else x
            if t: out[f"{pre}:{i}"] = t
    return out


def _sha(fields, status):
    return hashlib.sha256(json.dumps({"fields": fields, "status": status}, sort_keys=True).encode()).hexdigest()[:16]


def _readme_pitch(path):
    """(title, first paragraph) of the project's README, read-only; None when there is none."""
    for f in ("README.md", "readme.md", "README"):
        p = os.path.join(path or "", f)
        if os.path.isfile(p):
            txt = open(p, errors="replace").read(20000)
            t = re.search(r"^#\s+(.+)$", txt, re.M)
            paras = [x.strip() for x in re.split(r"\n\s*\n", re.sub(r"^#.*$", "", txt, flags=re.M)) if x.strip() and not x.strip().startswith(("|", "```", "!", "<"))]
            return (t.group(1).strip() if t else None), (re.sub(r"\s+", " ", paras[0])[:600] if paras else None), f
    return None, None, None


def _norm(fields):
    """Accept {"promise": "…"} or {"promise": {"text": "…"}}; lists of strings or {"text": …}. Unknown keys are refused."""
    out = {}
    for k, v in (fields or {}).items():
        if k in SINGLE:
            t = v.get("text") if isinstance(v, dict) else v
            if t: out[k] = {"text": str(t).strip(), "source": (v.get("source") if isinstance(v, dict) else None) or "stated"}
        elif k in LISTS:
            out[k] = [{"text": str(x.get("text") if isinstance(x, dict) else x).strip(), "source": (x.get("source") if isinstance(x, dict) else None) or "stated"}
                      for x in (v or []) if (x.get("text") if isinstance(x, dict) else x)]
        elif k == "open_questions": out[k] = [str(x) for x in v or []]
        else: raise ValueError(f"unknown vision field {k!r}; fields are {', '.join(SINGLE + tuple(LISTS) + ('open_questions',))}")
    return out


def _save(pid, V):
    d = os.path.join(write_root(), pid); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"v{V['version']}.json")
    if os.path.exists(p): raise FileExistsError(f"vision {pid} v{V['version']} already exists (versions are never rewritten)")
    with open(p, "w") as f: json.dump(V, f, indent=1)
    return dict(V, _path=p)


def draft(project, fields=None, by=None, note=None):
    """A new draft version. Fields not given are prefilled from the README where possible (labelled with their source)
    and otherwise listed as open questions. Never approved here."""
    from . import project_report
    P = project_report.resolve(project)
    if not P["id"]: raise ValueError("which project? give its folder, GitHub owner/repo or history id")
    F = _norm(fields)
    title, pitch, src = _readme_pitch(P.get("path"))
    if "promise" not in F and pitch: F["promise"] = {"text": pitch, "source": f"{src} (first paragraph; drafted, not stated by a person)"}
    missing = [k for k in SINGLE + tuple(LISTS) if not F.get(k)]
    F["open_questions"] = list(dict.fromkeys((F.get("open_questions") or []) + [f"{k.replace('_', ' ')}: not stated yet" for k in missing]))
    prev = latest(P["id"])
    V = {"schema": "gitcraft-vision/1", "project": P["id"], "repo": P.get("repo"), "title": title, "version": (prev["version"] + 1) if prev else 1,
         "status": "draft", "based_on": prev["version"] if prev else None, "created": _now(), "by": by or "GITCRAFT (drafted)", "note": note, "fields": F}
    V["sha256"] = _sha(F, "draft")
    return _save(P["id"], V)


def approve(project, version, approved_by, note=None):
    """A person's approval of a draft: a new version (status approved) with the same fields. `approved_by` must say who
    approved it; it is recorded as given. Call only when the person has said so."""
    from . import project_report
    pid = project_report.resolve(project)["id"]
    if not str(approved_by or "").strip(): raise ValueError("approval needs approved_by: who approved it (a person's own word)")
    src = next((V for V in versions(pid) if V["version"] == int(version)), None)
    if not src: raise ValueError(f"no vision v{version} for {pid}")
    if src["status"] == "approved": raise ValueError(f"v{version} is already approved")
    prev = latest(pid)
    V = {k: src[k] for k in ("schema", "project", "repo", "title", "fields")}
    V.update(version=prev["version"] + 1, status="approved", approves=src["version"], based_on=src["version"], created=_now(), by=str(approved_by).strip(), note=note)
    V["sha256"] = _sha(V["fields"], "approved")
    return _save(pid, V)


def summary(V):
    if not V: return None
    return {"version": V["version"], "status": V["status"], "sha256": V["sha256"], "title": V.get("title"), "clauses": clauses(V),
            "open_questions": (V.get("fields") or {}).get("open_questions") or [], "path": V.get("_path")}
