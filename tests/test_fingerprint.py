#!/usr/bin/env python3
"""Source-change fingerprints: running a QA check never invalidates the other checks.

The production engine re-measures a passed QA check when the project changed after it was measured. That is only
correct if "the project" means its source. Anything a check (or the tools it runs) writes while measuring must not
count, or one check's output makes every other check stale, they all re-run, write again, and so on.

Seen in practice: a fingerprint walk written as `for d, dirs, files in sorted(os.walk(project))` reads the whole
tree before the loop body can prune `dirs`, so the skip list never applied and every report a check wrote in
<game>/gitcraft-out re-triggered every other check. This file pins down:

  1. the walk prunes: a skipped folder is never opened at all
  2. what is not source: version control, dependencies and virtualenvs, tool caches, test-run reports and
     evaluation artifacts never change the fingerprint; source and build output (dist/) do
  3. end to end: a review whose departments write into those folders on every call runs each check exactly once,
     with no stale re-measurement, and ends with a verdict

    python3 tests/test_fingerprint.py      (~10 s, no browser)"""
import builtins, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-fp-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_PRODUCTION_ISOLATED=os.path.join(ws, "isolated-home"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"))
os.environ.pop("GITCRAFT_PRODUCTION_HOME", None)
from production import engine, entry, executors, store, artifacts
results = []


def check(label, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def write(p, text="x"):
    os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(text)


def game(name):
    """A small Vite-shaped game: source index.html loads /src/main.ts; dist/ is the build."""
    g = os.path.join(ws, name)
    shutil.copytree(os.path.join(HERE, "fixtures", "designcraft", "patrol_ts", "src"), os.path.join(g, "src"))
    write(os.path.join(g, "README.md"), "# Sky Patrol\n\nA small arcade game: dodge drones, collect stars, clear levels. Three lives.\n")
    json.dump({"name": name, "scripts": {"build": "vite build"}, "devDependencies": {"vite": "^5.4.0"}}, open(os.path.join(g, "package.json"), "w"))
    page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sky Patrol</title></head><body><canvas></canvas><script src="{}"></script></body></html>\n'
    write(os.path.join(g, "index.html"), page.format("/src/main.ts"))
    write(os.path.join(g, "src", "main.ts"), "let score = 0, lives = 3, level = 1;\n")
    write(os.path.join(g, "dist", "index.html"), page.format("assets/index.js"))
    write(os.path.join(g, "dist", "assets", "index.js"), "let score=0;\n")
    write(os.path.join(g, "node_modules", "vite", "package.json"), "{}")
    return g


# what checks and the tools they run leave in a project while measuring it (none of it is source)
NOISE = [".git/index", ".git/objects/ab/cdef", "node_modules/.vite/deps/_metadata.json", "node_modules/.cache/x.json",
         ".venv/lib/site.py", "venv/bin/activate", "__pycache__/m.cpython-313.pyc", ".pytest_cache/v/cache/lastfailed",
         ".mypy_cache/3.13/m.json", ".ruff_cache/content", ".parcel-cache/data.mdb", ".turbo/cookies/1", ".cache/fonts.json",
         ".sass-cache/a", ".tox/py/log", "coverage/lcov.info", ".nyc_output/out.json", "test-results/results.json",
         "playwright-report/index.html", "gitcraft-out/playcraft/pass.json", ".gitcraft-work/tmp.json",
         "src/__pycache__/deep.pyc", "packages/ui/node_modules/react/index.js"]

# =============================================================== 1. the walk prunes
g = game("prune-game")
for n in NOISE: write(os.path.join(g, n))
opened, real_open = [], builtins.open
def counting_open(p, *a, **k):
    opened.append(str(p)); return real_open(p, *a, **k)
builtins.open = counting_open
try: snap = artifacts.snapshot(g)
finally: builtins.open = real_open
skipped = [p for p in opened if any(f"{os.sep}{d}{os.sep}" in p for d in artifacts.VCS_AND_CACHE | artifacts.NAMES)]
check("walk: no file inside a skipped folder is ever opened (pruning happens during the walk, not after it)", not skipped, skipped[:5])
check("walk: ...and none is listed in the snapshot", not [k for k in snap if any(part in artifacts.VCS_AND_CACHE | artifacts.NAMES for part in k.split(os.sep))],
      sorted(snap)[:8])
check("walk: source and the build are in the snapshot", {"src/main.ts", "index.html", "dist/index.html", "package.json"} <= set(snap), sorted(snap)[:12])

# =============================================================== 2. what is not source
f0 = engine.fingerprint(g)
for n in NOISE: write(os.path.join(g, n), "changed")
for n in ("coverage/new-run/lcov.info", "test-results/new.json", "node_modules/.vite/deps/chunk.js"): write(os.path.join(g, n), "new")
check("not source: rewriting VCS, dependencies, virtualenvs, caches, test reports and evaluation output leaves the fingerprint as it was",
      engine.fingerprint(g) == f0)
write(os.path.join(g, "src", "main.ts"), "let score = 0, lives = 3, level = 2;\n")
f1 = engine.fingerprint(g)
check("source: an edit to the game's source changes the fingerprint", f1 != f0)
write(os.path.join(g, "dist", "assets", "index.js"), "let score=1;\n")
check("source: a rebuild (dist/ changed) changes the fingerprint: the browser checks measure the build", engine.fingerprint(g) != f1)
write(os.path.join(g, "src", "coverage.ts"), "export const c = 1;\n")
check("source: a source FILE whose name looks like a skipped folder still counts", engine.fingerprint(g) != f1)

# =============================================================== 3. end to end: one check's output never invalidates another
CALLS = []


def noisy_studio(dept, action, params, timeout=1800):
    """A department that, like real tools, leaves caches and reports in the project on every call."""
    CALLS.append(f"{dept}.{action}")
    out = params.get("out_dir") or os.path.join(ws, "loose"); os.makedirs(out, exist_ok=True)
    rep = os.path.join(out, f"{params.get('name') or action}.json"); json.dump({"dept": dept}, open(rep, "w"))
    tgt = params.get("project") or params.get("target") or ""
    proj = os.path.dirname(tgt) if tgt.endswith("dist") else tgt
    if proj:
        n = len(CALLS)
        for rel in (f"gitcraft-out/{dept}/{n}.json", f"node_modules/.vite/deps/{n}.js", f"test-results/{n}.json",
                    f"coverage/{n}/lcov.info", f".pytest_cache/{n}", f".cache/{n}"):
            write(os.path.join(proj, rel), str(n))
    return {"status": "ok", "out_dir": out, "outputs": [{"path": rep, "role": "report", "format": "json"}],
            "summary": {"overall": {"score": 90}}, "checks": [{"name": f"{dept}.{action} measured", "ok": True}]}


def quiet_designcraft(project, out_json, timeout=900):
    CALLS.append("designcraft.assess")
    json.dump({"score": {"overall": 70}}, open(out_json, "w"))
    return {"status": "ok", "outputs": [{"path": out_json, "role": "assessment", "format": "json", "ok": True}], "checks": [{"name": "read", "ok": True}]}


executors.studio_run = noisy_studio
executors.designcraft_assess = quiet_designcraft
g3 = game("e2e-game")
r = entry.start("Run GITCRAFT: review this game", g3)
pid = r["production"]
engine.decide(pid, approve=True)
st = engine.run(pid, max_seconds=120)
pr = store.load(pid)
ev = store.events(pr)
stale = [e for e in ev if e["event"] in ("stale_evidence", "evaluation_unstable")]
qa = {k: t for k, t in pr["tasks"].items() if t["stage"] in ("qa", "release")}
check("e2e: departments wrote caches and reports into the game on every call (the scenario is real)",
      os.path.isdir(os.path.join(g3, "test-results")) and len(os.listdir(os.path.join(g3, "test-results"))) >= 2, CALLS)
check("e2e: no check was invalidated by another check's output (no stale re-measurement)", not stale, stale[:3])
check("e2e: every QA and release check ran exactly once", qa and all(len(t["attempts"]) == 1 for t in qa.values()),
      {k: len(t["attempts"]) for k, t in qa.items()})
check("e2e: the run terminated with a verdict", st["status"] in ("passed", "failed", "blocked") and st.get("verdict") in ("READY", "NOT READY", "INCOMPLETE"),
      (st["status"], st.get("verdict")))
n = len(CALLS)
engine.run(pid)
check("e2e: running the finished evaluation again measures nothing", len(CALLS) == n, CALLS[n:])

shutil.rmtree(ws, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
