"""Evaluation artifacts vs the project being evaluated: what is source, what is output, and what is measured.

Three rules, the same for every game, app and site:

  1. Evaluation output is never project source. A folder is an evaluation artifact when it is named
     `gitcraft-out` / `.gitcraft-work` (where the departments write by default) or holds the marker file
     `.gitcraft-artifacts` (written into every production store and task folder). Change detection
     (`snapshot`, `fingerprint`) skips them, so writing a report can never make the project look changed
     and so can never start another evaluation round.
  2. Evaluation output lives outside the evaluated project. `store_root_for(project)` picks a production
     store that is not inside the project: the configured store, else `gitcraft-out/production` in a
     workspace root that is not inside the project, else the isolated home `$GITCRAFT_HOME/productions`.
     Read-only evaluators (DESIGNCRAFT) refuse output paths inside the game; they never see one.
  3. One evaluation target. Every browser check (smoke, features, performance, PLAYCRAFT, PIXELCRAFT, the
     final regression) measures the same thing, chosen by an explicit policy (`evaluation.target`):
       build   the built app (dist/ or the bundler's configured outDir); missing build → blocked, never source
       source  the project folder as it is (a static site with index.html at its root)
       auto    build when package.json has a build script and a bundler, else source (the default)
     Structural review (DESIGNCRAFT, standards, preservation, asset folders) reads the source by design."""
import hashlib, json, os, re

MARKER = ".gitcraft-artifacts"
NAMES = {"gitcraft-out", ".gitcraft-work"}
# Folders that are never the project's source, wherever they sit: version control, installed dependencies and
# virtualenvs, tool caches, and test-run reports (written by running a test suite, not by editing the project).
# Build output (dist/, build/) is deliberately NOT here: it is what the browser checks measure, so a rebuild must
# count as a change.
VCS_AND_CACHE = {
    ".git", ".hg", ".svn",                                                       # version control
    "node_modules", "bower_components", ".venv", "venv", ".tox",                 # installed dependencies
    "__pycache__", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache",      # tool caches
    ".parcel-cache", ".turbo", ".sass-cache",
    "coverage", ".nyc_output", "test-results", "playwright-report",            # test-run reports
}
BUNDLERS = ("vite", "webpack", "parcel", "esbuild", "rollup", "next", "@sveltejs/kit", "astro", "react-scripts")
POLICIES = ("auto", "build", "source")


def _real(p): return os.path.realpath(p)


def inside(path, root):
    p, r = _real(path), _real(root).rstrip(os.sep)
    return p == r or p.startswith(r + os.sep)


# ---------------------------------------------------------------- 1. what is an artifact
def mark(folder):
    """Mark a folder as evaluation output (idempotent). Change detection skips it wherever it sits."""
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, MARKER)
    if not os.path.exists(p):
        try:
            with open(p, "w") as f: f.write("GITCRAFT evaluation output: not project source; change detection ignores this folder.\n")
        except OSError: pass
    return folder


def is_artifact_dir(path):
    return os.path.basename(path.rstrip(os.sep)) in NAMES or os.path.isfile(os.path.join(path, MARKER))


def snapshot(project, exclude=()):
    """{relative path: sha256} of every project file that is source (artifacts, VCS and caches skipped)."""
    if not project or not os.path.isdir(project): return None
    ex = [_real(e) for e in exclude if e]
    out = {}
    for d, dirs, files in os.walk(project):
        keep = []
        for x in sorted(dirs):
            full = os.path.join(d, x)
            if x in VCS_AND_CACHE or is_artifact_dir(full) or any(inside(full, e) for e in ex): continue
            keep.append(x)
        dirs[:] = keep
        for f in sorted(files):
            if f == MARKER: continue
            p = os.path.join(d, f)
            try:
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    for b in iter(lambda: fh.read(1 << 20), b""): h.update(b)
                out[os.path.relpath(p, project)] = h.hexdigest()
            except OSError: pass
    return out


def digest(snap):
    if snap is None: return None
    h = hashlib.sha256()
    for k in sorted(snap): h.update(k.encode() + b"\0" + snap[k].encode() + b"\n")
    return h.hexdigest()


def diff(a, b):
    """Paths that differ between two snapshots (changed, added, removed)."""
    a, b = a or {}, b or {}
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


# ---------------------------------------------------------------- 2. where output goes
def isolated_home():
    home = os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft")
    return _real(os.environ.get("GITCRAFT_PRODUCTION_ISOLATED") or os.path.join(home, "productions"))


def store_root_for(project, configured, roots):
    """(store root, why): a production store that is never inside the evaluated project."""
    if not project: return configured, None
    if not inside(configured, project): return configured, None
    for r in roots:
        cand = os.path.join(r, "gitcraft-out", "production")
        if not inside(cand, project): return _real(cand), f"the default store {configured} is inside the project; evaluation output goes to {cand}"
    iso = isolated_home()
    return iso, f"every workspace root is inside the project; evaluation output goes to the isolated home {iso}"


OUTPUTS_SUFFIX = "-outputs"


def output_root(prod_id, store, project, create=True):
    """Where a production's task output (every department's out_dir, work orders, evidence) is written.

    The store itself when it is outside the evaluated project. A store inside the project (a production made
    before store_root_for existed, or one opened with an explicit store inside the project) keeps its record
    where it is, but its task output goes to `<isolated home>/<id>-outputs`, so a read-only evaluator
    (DESIGNCRAFT) is never handed a path inside the game. The folder is marked as evaluation output."""
    if not project or not inside(store, project): return store
    d = os.path.join(isolated_home(), os.path.basename(prod_id) + OUTPUTS_SUFFIX)
    return mark(d) if create else d


# ---------------------------------------------------------------- 3. what is evaluated
def _read(p):
    try:
        with open(p, errors="ignore") as f: return f.read()
    except OSError: return ""


def build_info(project):
    """What the project needs to be served: its bundler, build script and output folder (read-only)."""
    pkg = {}
    try: pkg = json.load(open(os.path.join(project, "package.json")))
    except (OSError, ValueError): pass
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
    scripts = pkg.get("scripts") or {}
    bundler = next((b for b in BUNDLERS if b in deps), None)
    out = {"vite": "dist", "parcel": "dist", "rollup": "dist", "esbuild": "dist", "webpack": "dist", "react-scripts": "build", "astro": "dist",
           "@sveltejs/kit": "build", "next": "out"}.get(bundler)
    for f in ("vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.mts"):
        m = re.search(r"outDir\s*:\s*['\"]([^'\"]+)", _read(os.path.join(project, f)))
        if m: out = m.group(1).strip("./") or out
    if not out:
        out = next((d for d in ("dist", "build", "out") if os.path.isfile(os.path.join(project, d, "index.html"))), None)
    pm = "pnpm" if os.path.exists(os.path.join(project, "pnpm-lock.yaml")) else "yarn" if os.path.exists(os.path.join(project, "yarn.lock")) else "npm"
    needs_build = bool(bundler and "build" in scripts)
    return {"bundler": bundler, "needs_build": needs_build, "build_dir": out, "build_command": f"{pm} run build" if "build" in scripts else None}


def target_policy(spec, project):
    """The source-vs-build decision for this production: {policy, chosen, dir, why, build_command}."""
    want = ((spec.get("evaluation") or {}).get("target") or "auto").lower()
    if want not in POLICIES: raise ValueError(f"evaluation.target must be one of {POLICIES}, not {want!r}")
    info = build_info(project) if project and os.path.isdir(project) else {"bundler": None, "needs_build": False, "build_dir": None, "build_command": None}
    if want == "source":
        return {"policy": want, "chosen": "source", "dir": ".", "why": "evaluation.target=source: the project folder is served as it is", **info}
    if want == "build" or info["needs_build"]:
        d = info["build_dir"] or "dist"
        why = (f"evaluation.target=build" if want == "build" else f"{info['bundler']} project with a build script") + f": every check measures the built app in {d}/"
        return {"policy": want, "chosen": "build", "dir": d, "why": why, **info}
    return {"policy": want, "chosen": "source", "dir": ".", "why": "no bundler build: the project folder is the app (static)", **info}


def resolve_target(project, pol):
    """(absolute folder, None) or (None, why it cannot be evaluated)."""
    d = os.path.normpath(os.path.join(project, pol["dir"]))
    if os.path.isfile(os.path.join(d, "index.html")): return d, None
    if pol["chosen"] == "build":
        cmd = pol.get("build_command") or "the project's build"
        return None, (f"the evaluation target {pol['dir']}/ has no index.html: the app is not built. Run `{cmd}` in the project, then run again "
                      "(the policy is build: checks never fall back to the unbuilt source)")
    return None, f"no index.html at the project root ({project}) to serve"
