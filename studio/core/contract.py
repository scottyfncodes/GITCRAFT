"""The GITCRAFT department contract.

A department is a folder studio/departments/<name>/ with:
  manifest.json  machine-readable capabilities: actions (request schema, outputs, required
                 dependencies), dependencies (how each is checked and installed), the acquired
                 tools with their licences, routing keywords and example requests
  dept.py        ACTIONS = {"<action>": fn(ctx, params) -> {"outputs": [...], ...}}

run(department, action, params) is the only entry point (MCP server, CLI, ForgeCraft):
  1. the request is validated against the action's schema (types, enums, ranges, required)
  2. the action's dependencies are checked; a missing one gives status "blocked" with the
     reason, the install command and the alternatives, never a substitute result
  3. the action runs with a Context (output folder inside the GITCRAFT roots, seed, helpers)
  4. every output is validated by format (core/validate.py) and hashed; one invalid output
     makes the run "failed": nothing unverified is reported as done
  5. a provenance record (<out_dir>/<slug>.studio.json) lists request, tools and licences,
     outputs with SHA-256, timings; outputs are registered in the AssetCraft catalogue
"""
import datetime, hashlib, importlib.util, json, os, re, sys, time, traceback
from . import STUDIO, VERSION, inside_roots, roots
from . import deps as _deps, validate as _validate

DEPT_DIR = os.path.join(STUDIO, "departments")
_cache = {}


class StudioError(Exception):
    """A failure the caller can act on (bad input, tool failure). `hint` says what to do."""
    def __init__(self, message, hint=None, stage=None):
        super().__init__(message); self.hint, self.stage = hint, stage


class Blocked(Exception):
    """The request cannot be honoured on this machine. Never substitute something else."""
    def __init__(self, reason, install=None, alternatives=None):
        super().__init__(reason); self.install, self.alternatives = install, alternatives or []


def departments():
    return sorted(d for d in os.listdir(DEPT_DIR) if os.path.isfile(os.path.join(DEPT_DIR, d, "manifest.json")))


def manifest(name):
    if name not in departments(): raise StudioError(f"unknown department {name!r}", hint=f"one of: {', '.join(departments())}")
    return json.load(open(os.path.join(DEPT_DIR, name, "manifest.json")))


def module(name):
    if name not in _cache:
        path = os.path.join(DEPT_DIR, name, "dept.py")
        spec = importlib.util.spec_from_file_location(f"gitcraft_studio_{name}", path)
        mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
        _cache[name] = mod
    return _cache[name]


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")[:48] or "asset"


# ---------------------------------------------------------------- request validation
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}


def validate_params(schema, params, where="params"):
    """A small JSON-Schema subset (type, enum, minimum, maximum, required, default, items,
    properties) — enough to refuse bad requests with a readable message."""
    params = dict(params or {})
    props = schema.get("properties", {})
    for req in schema.get("required", []):
        if req not in params: raise StudioError(f"{where}.{req} is required", hint=props.get(req, {}).get("description"))
    unknown = sorted(set(params) - set(props) - {"out_dir", "name", "seed", "register", "license", "attribution", "tags"})
    if unknown and not schema.get("additionalProperties", False):
        raise StudioError(f"{where}: unknown parameter(s) {', '.join(unknown)}", hint=f"accepted: {', '.join(sorted(props))}")
    for k, spec in props.items():
        if k not in params:
            if "default" in spec: params[k] = spec["default"]
            continue
        v = params[k]; t = spec.get("type")
        if t:
            ok = isinstance(v, _TYPES[t]) and not (t in ("integer", "number") and isinstance(v, bool))
            if t == "number" and isinstance(v, bool): ok = False
            if not ok: raise StudioError(f"{where}.{k} must be {t}, got {type(v).__name__}")
        if "enum" in spec and v not in spec["enum"]:
            raise StudioError(f"{where}.{k}={v!r} is not one of {spec['enum']}")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if "minimum" in spec and v < spec["minimum"]: raise StudioError(f"{where}.{k}={v} is below {spec['minimum']}")
            if "maximum" in spec and v > spec["maximum"]: raise StudioError(f"{where}.{k}={v} is above {spec['maximum']}")
        if t == "array" and "items" in spec and spec["items"].get("type") == "object" and "properties" in spec["items"]:
            params[k] = [validate_params(spec["items"], it, f"{where}.{k}[{i}]") for i, it in enumerate(v)]
    return params


# ---------------------------------------------------------------- context given to actions
class Context:
    def __init__(self, dept, action, params, out_dir):
        self.dept, self.action, self.params, self.out_dir = dept, action, params, out_dir
        self.seed = int(params.get("seed", 0) or 0)
        self.tools_used, self.stages, self.notes = [], [], []
        self._t = time.time()

    def path(self, filename):
        p = os.path.join(self.out_dir, filename); os.makedirs(os.path.dirname(p), exist_ok=True); return p

    def need(self, path, kind="input"):
        """An input file: must exist and be inside the GITCRAFT roots."""
        if not path: raise StudioError(f"{kind} path is empty")
        p = os.path.abspath(os.path.expanduser(path))
        if not inside_roots(p) and not _allowed_read(p):
            raise StudioError(f"GITCRAFT policy: {kind} {p} is outside the workspace roots ({':'.join(roots())})",
                              hint="copy the file into the workspace")
        if not os.path.exists(p): raise StudioError(f"{kind} not found: {p}")
        return p

    def used(self, *tool_ids):
        for t in tool_ids:
            if t not in self.tools_used: self.tools_used.append(t)

    def stage(self, name, **info):
        now = time.time(); rec = {"stage": name, "seconds": round(now - self._t, 2)}
        rec.update({(k if k not in rec else f"{k}_reported"): v for k, v in info.items()}); self.stages.append(rec); self._t = now

    def note(self, msg): self.notes.append(msg)


def _allowed_read(p):
    """Read-only sources outside the workspace that departments may use: the shared 3D library."""
    lib = os.environ.get("GITCRAFT_3D_LIBRARY")
    return bool(lib) and os.path.realpath(p).startswith(os.path.realpath(lib) + os.sep)


def resolve_out_dir(dept, action, params):
    out = params.get("out_dir")
    if not out:
        out = os.path.join(roots()[0], "gitcraft-out", dept, slugify(params.get("name") or action))
    out = os.path.abspath(os.path.expanduser(out))
    if not inside_roots(out):
        raise StudioError(f"GITCRAFT policy: out_dir {out} is outside the workspace roots ({':'.join(roots())})")
    os.makedirs(out, exist_ok=True)
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


SUBJECT_KEYS = ("target", "project", "folder", "current", "input", "baseline")


def _git(cwd, *a):
    import subprocess
    try:
        r = subprocess.run(["git", "-C", cwd, *a], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def content_hash(path, max_files=5000, max_bytes=300 << 20):
    """SHA-256 over a file, or over a folder's relative paths and contents (sorted; .git and node_modules skipped).
    None when the folder is too large to hash quickly (the commit still identifies it)."""
    h = hashlib.sha256(); n = size = 0
    if os.path.isfile(path): return sha256(path)
    for d, ds, fs in os.walk(path):
        ds[:] = sorted(x for x in ds if x not in (".git", "node_modules", "__pycache__"))
        for f in sorted(fs):
            fp = os.path.join(d, f); n += 1
            try: size += os.path.getsize(fp)
            except OSError: continue
            if n > max_files or size > max_bytes: return None
            h.update(os.path.relpath(fp, path).encode() + b"\0")
            with open(fp, "rb") as fh:
                for b in iter(lambda: fh.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def measured_subject(params):
    """What a run measured, so a later reader can tell whether the result still describes the project: the measured
    path, its content hash, and the git commit (with its date and whether the tree had local changes) of the repository
    that holds it. A report marks a result Stale when the project has moved on since (production/project_report.py)."""
    for k in SUBJECT_KEYS:
        v = params.get(k)
        if isinstance(v, str) and v and os.path.exists(os.path.expanduser(v)):
            p = os.path.realpath(os.path.expanduser(v)); d = p if os.path.isdir(p) else os.path.dirname(p)
            top = _git(d, "rev-parse", "--show-toplevel")
            out = {"param": k, "path": p, "content_sha256": content_hash(p), "repo": top}
            if top:
                out.update(commit=_git(top, "rev-parse", "HEAD"), committed_at=_git(top, "log", "-1", "--format=%cI"),
                           dirty=bool(_git(top, "status", "--porcelain", "--untracked-files=no")))
            return out
    return None


# ---------------------------------------------------------------- the entry point
def run(dept, action, params=None, register=None):
    t0 = time.time()
    m = manifest(dept)
    if action not in m["actions"]:
        raise StudioError(f"{dept} has no action {action!r}", hint=f"actions: {', '.join(m['actions'])}")
    spec = m["actions"][action]
    params = validate_params(spec.get("params", {}), params)
    status = _deps.check(m, spec.get("requires", []))
    missing = {k: v for k, v in status.items() if not v["available"]}
    base = {"department": dept, "action": action, "studio": VERSION}
    if missing:
        alts = spec.get("alternatives", []) + [a for d in missing.values() for a in d.get("alternatives", [])]
        return dict(base, status="blocked", reason="; ".join(f"{k}: {v['reason']}" for k, v in missing.items()),
                    install=sorted({v["install"] for v in missing.values() if v.get("install")}), alternatives=alts,
                    dependencies=status)
    out_dir = resolve_out_dir(dept, action, params)
    ctx = Context(dept, action, params, out_dir)
    fn = module(dept).ACTIONS[action]
    try:
        res = fn(ctx, params) or {}
    except Blocked as e:
        return dict(base, status="blocked", reason=str(e), install=[e.install] if e.install else [], alternatives=e.alternatives)
    except StudioError as e:
        return dict(base, status="failed", error=str(e), hint=e.hint, stage=e.stage or (ctx.stages[-1]["stage"] if ctx.stages else None),
                    stages=ctx.stages)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return dict(base, status="failed", error=f"{type(e).__name__}: {e}", stages=ctx.stages)
    # ---- output validation: every file is checked by format and hashed
    outputs, bad = [], []
    for o in res.pop("outputs", []):
        o = dict(o); p = o["path"]
        v = _validate.check(p, expect=o.get("format"))
        o.update(v); o["path"] = os.path.relpath(p, out_dir) if p.startswith(out_dir + os.sep) else p
        if v["ok"]: o["sha256"] = sha256(p); o["bytes"] = os.path.getsize(p)
        else: bad.append(f"{o['path']}: {v.get('error')}")
        outputs.append(o)
    checks = [dict(c, ok=bool(c.get("ok"))) for c in res.pop("checks", [])]   # numpy bools → real booleans
    failed_checks = [c for c in checks if not c.get("ok")]
    ok = not bad and not failed_checks and outputs
    tools = {t: m["tools"].get(t, {"name": t}) for t in ctx.tools_used}
    record = dict(base, status="ok" if ok else "failed", out_dir=out_dir, request=params,
                  created=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                  seconds=round(time.time() - t0, 2), outputs=outputs, checks=checks,
                  tools={k: {"name": v.get("name"), "license": v.get("license"), "version": v.get("version")} for k, v in tools.items()},
                  # an action that fetched existing assets (e.g. CC0 libraries) reports their real licence and credit
                  output_license=params.get("license") or res.pop("output_license", None) or m.get("output_license", "Generated by GITCRAFT; owned by the requesting project"),
                  attribution=params.get("attribution") or res.pop("attribution", None) or _attribution(tools),
                  stages=ctx.stages, notes=ctx.notes, **res)
    if not outputs: record["error"] = "the action produced no output files"
    if bad: record["error"] = "invalid output: " + "; ".join(bad)
    if failed_checks: record["error"] = "failed checks: " + "; ".join(c["name"] + (f" ({c.get('detail')})" if c.get("detail") else "") for c in failed_checks)
    if failed_checks and outputs and not bad and all(c.get("category") == "unverified" for c in failed_checks):
        # it ran and found nothing wrong; some checks could not be completed (e.g. no network here): incomplete, not a defect
        record["verification"] = "incomplete"
        record["error"] = "unverified checks (not failures): " + "; ".join(f"{c['name']} [{c.get('cause') or 'unverified'}]" for c in failed_checks)
    record["measured"] = measured_subject(params)
    rec_path = os.path.join(out_dir, f"{slugify(params.get('name') or action)}.studio.json")
    json.dump(record, open(rec_path, "w"), indent=1, default=str)
    record["record"] = rec_path
    if (register if register is not None else params.get("register", True)) and ok and dept != "assetcraft" and m.get("register_outputs", True):
        try:
            from . import catalog
            record["catalog"] = catalog.register_run(record)
        except Exception as e:   # the catalogue is a convenience; never fail a good run on it
            record["catalog"] = {"error": f"{type(e).__name__}: {e}"}
    return record


def _attribution(tools):
    req = [f"{v['name']} ({v['license']})" for v in tools.values() if v.get("attribution_required")]
    return ("Made with " + ", ".join(req)) if req else None


def describe(name):
    m = manifest(name)
    m["dependencies_status"] = _deps.check(m, list(m.get("dependencies", {})))
    m["actions_available"] = {a: all(m["dependencies_status"][d]["available"] for d in s.get("requires", [])) for a, s in m["actions"].items()}
    return m


def overview():
    out = []
    for d in departments():
        m = describe(d)
        out.append({"department": d, "title": m["title"], "summary": m["summary"],
                    "actions": {a: ("ready" if ok else "blocked: " + "; ".join(
                        f"{r}: {m['dependencies_status'][r]['reason']}" for r in m["actions"][a].get("requires", [])
                        if not m["dependencies_status"][r]["available"])) for a, ok in m["actions_available"].items()}})
    return out
