"""Evaluator identity: which GITCRAFT code produced a check's result.

A measured failure is fixed in the project, never retried: running the same evaluator on the same project again
cannot honestly change the answer. One case is different: the evaluator itself was wrong and has since been
corrected (it read GITCRAFT's own report as the product's source; it counted a file it should have skipped). The
project has nothing to fix, so the fix work order can never be satisfied, and the old result is no longer what
GITCRAFT would measure.

So every finished attempt of a check records the identity of what measured it: a name and a fingerprint of that
evaluator's source files. `engine.retry` lets a quality failure run again only when the fingerprint recorded with
the failure differs from the evaluator installed now. The check is measured again; nothing is converted. It can
pass, fail again (a new fix work order) or be incomplete, and the earlier result stays in the task's history.

What counts as "the evaluator" of a task (the code whose change can change its verdict):
  studio        the department's folder, the Studio core it runs on, and the production gate that reads its result
  designcraft   gamedesign/, and the production gate
  builtin       the production modules that read the project and decide (BUILTIN below), and the rules file
An attempt recorded before identity was tracked has none: it was measured by an older GITCRAFT, which is by
definition not the evaluator installed now (see `changed`)."""
import hashlib, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTS = (".py", ".mjs", ".js", ".json")
SKIP_DIRS = {"__pycache__", "node_modules", "history", "data", "fixtures", "kit", "web"}
# the production package's own checks (qa.request, standards, icons, licences, attribution, live): the modules that read the
# project and decide. The engine, planner and reports schedule and present results; they do not measure
BUILTIN = ["production/builtins.py", "production/gates.py", "production/qa.py", "production/standards.py", "production/verification.py",
           "production/icons.py", "production/live.py", "production/artifacts.py", "production/direction.py", "production/maturity.py",
           "production/rules.json"]
_cache = {}


def _sources(t):
    """(name, [paths relative to the GITCRAFT root]) for a task's evaluator, or None when the task evaluates nothing
    (an agent's work order, an approval)."""
    kind, dept = t.get("kind"), t.get("department")
    gate = ["production/gates.py", "production/verification.py"]
    if kind == "studio" and dept: return dept, [f"studio/departments/{dept}", "studio/core"] + gate
    if kind == "designcraft": return "designcraft", ["gamedesign"] + gate
    if kind == "builtin": return f"production.{t.get('action')}", BUILTIN
    return None


def _files(rel, root):
    p = os.path.join(root, rel)
    if os.path.isfile(p): return [rel]
    out = []
    for d, dirs, files in os.walk(p):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        out += [os.path.relpath(os.path.join(d, f), root) for f in sorted(files) if f.endswith(EXTS)]
    return out


def identity(t, root=None):
    """{"name", "fingerprint", "files"} for the evaluator of task `t` as installed now, or None."""
    src = _sources(t)
    if not src: return None
    root = root or REPO
    name, paths = src
    key = (root, name, tuple(paths))
    if key not in _cache:
        h, n = hashlib.sha256(), 0
        for rel in sorted({f for p in paths for f in _files(p, root)}):
            try:
                with open(os.path.join(root, rel), "rb") as f: body = f.read()
            except OSError: continue
            h.update(rel.replace(os.sep, "/").encode()); h.update(b"\0"); h.update(hashlib.sha256(body).digest()); n += 1
        _cache[key] = {"name": name, "fingerprint": h.hexdigest()[:16], "files": n}
    return dict(_cache[key])


def changed(recorded, t, root=None):
    """(changed, now, why). `recorded` is the identity stored with the attempt that failed."""
    now = identity(t, root)
    if not now: return False, None, "this task has no evaluator (it is not a check)"
    if not recorded or not recorded.get("fingerprint"):
        return True, now, "the failure was recorded before evaluator identity was tracked, by an older GITCRAFT"
    if recorded["fingerprint"] != now["fingerprint"]:
        return True, now, f"the {now['name']} evaluator changed since it measured this ({recorded['fingerprint']} → {now['fingerprint']})"
    return False, now, f"the {now['name']} evaluator is the one that measured this ({now['fingerprint']})"
