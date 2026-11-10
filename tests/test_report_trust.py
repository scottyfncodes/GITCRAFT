#!/usr/bin/env python3
""""Run GITCRAFT report" is correct, runnable and trustworthy: one regression test per item of the scrap-tide review
(report 20261110T050223Z on scottyfncodes/scrap-tide @ ef93877).

   1  the report runs with the project as the first root and no env var (it saves outside the project)
   2  a root-absolute reference is resolved against the page's own serve roots (no false "missing file")
   3  stubs come from code only, never from words inside a string or a document
   4  a result measured before the project's latest commit is Stale: low confidence, out of the Top 3 and P0/P1
   5  two runs of the same check give one finding; Top 3 holds distinct items
   6  a frame rate drawn by software WebGL is environment-limited (UNVERIFIED), not a failure, not scored
   7  a console error names the failing URL; a request the sandbox blocked is environment, not a project defect
   8  a visual diff gives a diff image, the changed regions and a "Do: accept as new baseline if intended" line
   9  every finding has a human title, the measured value, a Do line and the evidence path (contract)
  10  file validity is not quality; low confidence carries less weight; the headline carries its coverage
  11  refresh=quick smoke-tests an existing build; with no build it names the build command and the refresh=full call
  12  ForgeCraft never drops its status tool when its build lands; register.sh leaves an unchanged registration alone;
      doctor.sh reports the 3D servers

Fast and offline: department calls are stand-ins that write exactly what the department writes."""
import glob, hashlib, json, os, re, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "tests"))
WS = os.path.realpath(tempfile.mkdtemp(prefix="gcr-trust-"))
for k in [k for k in os.environ if k.startswith("GITCRAFT_")]: del os.environ[k]
os.environ.update(GITCRAFT_HOME=os.path.join(WS, "home"), GITCRAFT_PRODUCTION_HOME=os.path.join(WS, "prod"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(WS, "none", "catalog.sqlite"), GITCRAFT_3D_LIBRARY=os.path.join(WS, "none-3d"),
                  GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(WS, "none-px"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(WS, "none-pc"))
from production import project_report as PR, scoring as SC, maturity  # noqa: E402

fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  {str(detail)[:600]}"), flush=True)
    fails += 0 if cond else 1


def tree_hash(root):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds.sort()
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def git(root, *a, env=None):
    return subprocess.run(["git", "-C", root, *a], capture_output=True, text=True, env=dict(os.environ, **(env or {}))).stdout.strip()


def commit(root, when):
    git(root, "add", "-A")
    git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c", env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})


def W(root, rel, text):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    (open(p, "wb").write(text) if isinstance(text, bytes) else open(p, "w").write(text if isinstance(text, str) else json.dumps(text)))
    return p


# ---------------------------------------------------------------- a game shaped like scrap-tide
game = os.path.join(WS, "scottyfncodes", "scrap-tide")
W(game, "index.html", "<!doctype html><html><head><title>Scrap Tide</title></head><body><canvas></canvas><script type=module src=/src/main.ts></script></body></html>")
W(game, "src/main.ts", "import * as THREE from 'three';\nconst player = {jump(){}, score: 0, lives: 3}; const enemies = []; let level = 1;\n"
                       "function gameLoop(){ player.score++; requestAnimationFrame(gameLoop); }\naddEventListener('keydown', () => player.jump()); gameLoop();\n")
W(game, "package.json", {"name": "scrap-tide", "scripts": {"build": "vite build"}, "dependencies": {"three": "^0.170.0"}})
W(game, "vercel.json", {"buildCommand": "npm run build", "outputDirectory": "dist", "framework": "vite"})
W(game, "README.md", "# Scrap Tide\n\nA browser game: salvage, upgrade your boat, beat each level.\n")
W(game, "vite.config.ts", "export default { build: { outDir: 'dist' } };\n")
# item 2: a verification kit with its own Vite config; its page loads /src/harness.ts, which sits beside it
W(game, "creative/3d/integration/verify/harness.html", "<!doctype html><canvas id=c></canvas><script type=module src=/src/harness.ts></script>")
W(game, "creative/3d/integration/verify/harness.ts", "export const ok = true;\n")
W(game, "creative/3d/integration/verify/vite.harness.mjs", "export default { root: '.', build: { outDir: 'dist', rollupOptions: { input: 'harness.html' } } };\n")
# a real missing reference in a non-entry page (kept, ranked lower) and in the entry page's folder
W(game, "tools/preview/page.html", "<!doctype html><script src='/src/nowhere.ts'></script>")
# item 3: prose that says "not implemented" inside a string
W(game, "creative/pipeline/manifest.py", 'STATUS = "Status key: **illustrative mockup**: layout concept, not implemented UI"\n'
                                         '"""A doc string: TODO is just a word here; raise NotImplementedError is prose too."""\n')
# TestCraft records from an older checkout (another path), made before the project's latest commit, no commit recorded
old = "/home/user/TIDEBREAKERS"
SW = ["Headless Chromium renders WebGL in software (SwiftShader): absolute FPS is lower than on a real GPU; compare runs on the same machine."]
for tag, when, fps in (("baseline", "2026-11-04T17:32:02+00:00", 1), ("after", "2026-11-04T18:37:37+00:00", 1.1)):
    W(game, f"docs/gitcraft-pass/{tag}/{tag}_perf.studio.json", {
        "department": "testcraft", "action": "perf", "status": "failed", "out_dir": f"{old}/docs/gitcraft-pass/{tag}", "created": when, "notes": SW,
        "request": {"target": f"{old}/dist", "viewports": ["phone"], "name": f"{tag}_perf", "min_fps": 30, "max_p95_ms": 50},
        "checks": [{"name": "phone: average FPS ≥ 30", "ok": False, "detail": fps}, {"name": "phone: p95 frame time ≤ 50 ms", "ok": False, "detail": 1783.2},
                   {"name": "phone: no page errors", "ok": True, "detail": []}], "perf": {"phone": {"fps": fps}}})
    W(game, f"docs/gitcraft-pass/{tag}/{tag}_smoke.studio.json", {
        "department": "testcraft", "action": "smoke", "status": "failed", "out_dir": f"{old}/docs/gitcraft-pass/{tag}", "created": when,
        "request": {"target": f"{old}/dist", "viewports": ["phone"], "name": f"{tag}_smoke"},
        "notes": ["phone: blocked external requests (no network in tests): ['https://fonts.googleapis.com/css2?family=Saira']"],
        "results": [{"viewport": "phone", "blocked": ["https://fonts.googleapis.com/css2?family=Saira"], "console_errors": ["Failed to load resource: net::ERR_FAILED"]}],
        "checks": [{"name": "phone: no page errors", "ok": True, "detail": []}, {"name": "phone: no console errors", "ok": False, "detail": ["Failed to load resource: net::ERR_FAILED"]},
                   {"name": "phone: renders something (not a blank screen)", "ok": True}]})
W(game, "docs/gitcraft-pass/after/diff_title_phone.studio.json", {
    "department": "testcraft", "action": "visual_diff", "status": "failed", "out_dir": f"{old}/docs/gitcraft-pass/after", "created": "2026-11-04T19:01:18+00:00",
    "request": {"baseline": f"{old}/docs/gitcraft-pass/baseline/phone_final.png", "current": f"{old}/docs/gitcraft-pass/after/phone_final.png", "max_mismatch": 0.05},
    "checks": [{"name": "phone_final.png matches baseline (≤ 5.00% pixels differ)", "ok": False, "detail": {"same_size": True, "mismatch": 0.111987, "pixels": 261002}}]})
W(game, "docs/gitcraft-pass/baseline/phone_final.png", b"\x89PNG\r\n\x1a\nbase"); W(game, "docs/gitcraft-pass/after/phone_final.png", b"\x89PNG\r\n\x1a\nafter")
# a maker department: valid files, not quality
W(game, "creative/audio/sfx/hit.studio.json", {"department": "audiocraft", "action": "sfx", "status": "ok", "created": "2026-11-04T10:00:00+00:00",
                                               "outputs": [{"path": "hit.wav", "ok": True}, {"path": "hit.ogg", "ok": True}], "checks": [{"name": "audio is not silent", "ok": True}]})
git(game, "init", "-q"); commit(game, "2026-11-09T22:03:16-07:00")
HEAD = git(game, "rev-parse", "HEAD")

CALLS = []


def fake(action, args, timeout=3600, env=None):
    CALLS.append((action, args, env))
    out = args.get("out_dir"); os.makedirs(out, exist_ok=True) if out else None
    if action == "testcraft_visual_diff":
        d = os.path.join(out, "diff_phone_final.png"); open(d, "wb").write(b"\x89PNG\r\n\x1a\ndiff")
        return {"status": "failed", "comparisons": [{"same_size": True, "mismatch": 0.111987, "pixels": 261002, "regions": [[0, 240, 585, 416], [112, 768, 368, 96]],
                                                     "diff": d, "baseline": args["baseline"], "current": args["current"]}]}, None
    if action == "testcraft_smoke":
        W(out, "smoke.studio.json", {"department": "testcraft", "action": "smoke", "status": "ok", "created": PR.now(), "request": args,
                                     "measured": {"commit": HEAD}, "checks": [{"name": "phone: no page errors", "ok": True}]})
        return {"status": "ok"}, None
    return None, f"{action}: the Studio runtime is not installed (stubbed)"


PR._studio_call = fake
before = tree_hash(game)

# ---------------------------------------------------------------- 1. runnable: the project is the first root, no env var
os.environ["GITCRAFT_ROOTS"] = game   # a cloud session: roots()[0] IS the project; GITCRAFT_REPORTS is not set
R = PR.generate(game, refresh="quick")
check("1 · the report saves with the project as the first root and no GITCRAFT_REPORTS (outside the project, under GITCRAFT_HOME/reports)",
      os.path.isfile(R["paths"]["json"]) and R["paths"]["dir"].startswith(os.path.join(WS, "home", "reports") + os.sep) and not R["paths"]["dir"].startswith(game), R["paths"])
check("1 · read-only: the project is byte-identical after the report", tree_hash(game) == before)
try: PR.generate(game, out_dir=os.path.join(game, "rep"), save="none"); refused = False
except PermissionError: refused = True
check("1 · an explicit folder inside the project is still refused", refused and not os.path.exists(os.path.join(game, "rep")))
mcp = open(os.path.join(REPO, "scripts", "mcp.sh")).read()
check("1 · the studiocraft sandbox can write GITCRAFT's default report folder ($GITCRAFT_HOME/reports)",
      any(l.startswith('[[ "$name" == studiocraft ]] && writable+=') and '"$GITCRAFT_HOME/reports"' in l for l in mcp.splitlines()) and '"$GITCRAFT_HOME/reports"' in mcp.split("studiocraft) mkdir -p", 1)[1].split("export", 1)[0])
legacy = os.path.join(game, "gitcraft-out", "reports")
check("1 · earlier reports in the old default (<root>/gitcraft-out/reports) are still read for comparison", legacy in PR.read_roots(), PR.read_roots())

D = {d["id"]: d for d in R["departments"]}
F = [f for d in R["departments"] for f in d["findings"]]

# ---------------------------------------------------------------- 2. missing-file references
a = maturity.assess(game)
defects = a["inventory"]["defects"]
check("2 · /src/harness.ts in a page served by its own Vite config (the file beside it) is not a missing file",
      not any("harness.ts" in d["what"] for d in defects) and not any("harness.ts" in f["title"] for f in F), defects)
miss = [d for d in defects if "nowhere.ts" in d["what"]]
check("2 · a file no plausible root has is still reported, with the roots that were tried", miss and miss[0]["roots"] and miss[0]["entry"] is False, defects)
mf = [f for f in D["production"]["findings"] if "nowhere.ts" in f["title"]]
check("2 · a reference from a page that is not the shipped entry ranks lower (minor, not major) than the entry page would",
      mf and mf[0]["severity"] == "minor" and all(a["priority"] not in ("P0", "P1") for a in R["actions"] if mf[0]["key"] in a["findings"]), [(f["title"], f["severity"]) for f in mf])
site = os.path.join(WS, "site"); W(site, "index.html", "<!doctype html><script src='/src/nowhere.ts'></script>"); W(site, "src/ok.ts", "1")
ed = maturity.assess(site)["inventory"]["defects"]
check("2 · the same missing file in the shipped entry page is flagged as the entry's (major in the report)", [d["entry"] for d in ed] == [True], ed)

# ---------------------------------------------------------------- 3. stubs from code only
uf = a["inventory"]["unfinished"]
check("3 · prose inside a string ('not implemented UI') and a docstring are never stubs or TODOs",
      not any(u["where"] == "creative/pipeline/manifest.py" for u in uf) and not any("manifest.py" in str(f.get("evidence")) for f in F), uf)
sig = lambda path, text: [k + ":" + w for k, w in maturity.code_signals(path, text)]
check("3 · code stubs are found: raise NotImplementedError, throw new Error('not implemented'), a pass-only function, TODO/FIXME comments",
      sig("a.py", "def f():\n    raise NotImplementedError\n") == ["stub:stub: raise NotImplementedError"]
      and sig("a.ts", "function f(){ throw new Error('not implemented'); }\n") == ["stub:stub: throw new Error('not implemented')"]
      and sig("a.py", "def g():\n    pass\n") == ["stub:stub: def g(): pass"] and sig("a.ts", "// TODO: wire the boss\n") == ["todo:TODO: wire the boss"]
      and sig("a.py", "class A:\n    @abstractmethod\n    def h(self):\n        ...\n") == [] and sig("a.py", "def f(x):\n    pass\n    return x\n") == []
      and sig("a.ts", "const s = 'throw new Error(\"not implemented\") // TODO no';\n") == [], [sig("a.ts", "const s = 'throw new Error(\"not implemented\") // TODO no';\n")])

# ---------------------------------------------------------------- 4. stale evidence
tc = D["testcraft"]
check("4 · TestCraft results measured before the project's latest commit are Stale, with the measured date and what re-runs them",
      tc["status"] == "stale" and all(f.get("stale", "").startswith("Stale (measured at an unrecorded commit, 2026-11-04") for f in tc["findings"])
      and "testcraft_smoke" in (tc["next"] or "") and "npm run build" in (tc["next"] or ""), (tc["status"], [f.get("stale") for f in tc["findings"]], tc["next"]))
check("4 · stale results have low confidence and never reach P0/P1 or the Top 3", tc["score"]["confidence"] == "low"
      and all(a["priority"] not in ("P0", "P1") for a in R["actions"] if a.get("stale"))
      and not any(k.startswith("testcraft:") for a in R["top_actions"] for k in next(x for x in R["actions"] if x["n"] == a["n"])["findings"]), R["top_actions"])
check("4 · a record from another checkout says so", any("another checkout" in n for n in tc["notes"]), tc["notes"])
ctx = {"project": {"head": HEAD, "path": game}, "head_at": PR._utc("2026-11-10T05:03:16+00:00"), "run_dir": os.path.join(WS, "rd")}
check("4 · a record with a recorded commit: Stale (measured at <sha>, <date>) when the project moved on, current at HEAD",
      PR._rec_stale({"created": "2026-11-09T10:00:00+00:00", "measured": {"commit": "abc1234def"}}, ctx)["label"] == "Stale (measured at abc1234, 2026-11-09)"
      and PR._rec_stale({"created": "2026-11-10T06:00:00+00:00", "measured": {"commit": HEAD}}, ctx) is None
      and PR._rec_stale({"created": "2026-11-01T00:00:00+00:00", "_path": os.path.join(WS, "rd", "x.studio.json")}, ctx) is None)
sys.path.insert(0, os.path.join(REPO, "studio"))
from core import contract  # noqa: E402
ms = contract.measured_subject({"target": os.path.join(game, "src")})
check("4 · every .studio.json records what it measured: the path, its content hash and the repository's commit (date, local changes)",
      ms and ms["commit"] == HEAD and ms["committed_at"] and len(ms["content_sha256"]) == 64 and ms["dirty"] is False and "record[\"measured\"] = measured_subject(params)" in open(contract.__file__).read(), ms)

# ---------------------------------------------------------------- 5. duplicates
titles = [f["title"] for f in tc["findings"]]
check("5 · two runs of the same check (baseline + after) give one finding per failed criterion, the latest run's",
      len(titles) == len(set(titles)) == 4 and any("1.1 FPS" in f["measured"] for f in tc["findings"]) and not any(re.search(r"(?<![\d.])1 FPS average", f["measured"]) for f in tc["findings"]), titles)
check("5 · the superseded runs are said, not hidden", any("2 earlier run(s) of the same checks superseded" in n for n in tc["notes"]), tc["notes"])
check("5 · Top 3 holds distinct items", len({(a["title"], a.get("do")) for a in R["top_actions"]}) == len(R["top_actions"]), R["top_actions"])

# ---------------------------------------------------------------- 6. software WebGL
fps = next(f for f in tc["findings"] if "frame rate" in f["title"])
check("6 · a phone FPS drawn by SwiftShader is environment-limited / UNVERIFIED (info, not failed), and not scored",
      fps["kind"] == "unverified" and fps["severity"] == "info" and "environment-limited" in fps["title"] and tc["checks"]["environment_limited"] >= 2
      and tc["score"]["value"] == round(100 * tc["checks"]["passed"] / tc["checks"]["of"], 1), (fps, tc["checks"]))
TF = PR._load(os.path.join(REPO, "studio", "departments", "testcraft", "findings.py"))
hw = TF.describe({"name": "phone: average FPS ≥ 30", "ok": False, "detail": 12}, {"action": "perf", "perf": {"phone": {"gpu": {"renderer": "ANGLE (NVIDIA GeForce RTX 3060)"}}}})
sw = TF.describe({"name": "phone: average FPS ≥ 30", "ok": False, "detail": 12}, {"action": "perf", "perf": {"phone": {"gpu": {"renderer": "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)))"}}}})
check("6 · only a hardware-rendered run can fail a perf gate", hw["category"] == "project" and hw["title"] == "Phone frame rate below 30 FPS"
      and hw["measured"] == "12 FPS average (threshold ≥ 30)" and sw["category"] == "environment", (hw, sw))
mjs = open(os.path.join(REPO, "studio", "core", "web", "testcraft.mjs")).read(); dpy = open(os.path.join(REPO, "studio", "departments", "testcraft", "dept.py")).read()
check("6 · testcraft perf records the WebGL renderer (WEBGL_debug_renderer_info) and marks software runs environment_limited",
      "UNMASKED_RENDERER_WEBGL" in mjs and "R.perf.gpu" in mjs and '"cause": "environment_limited"' in dpy)

# ---------------------------------------------------------------- 7. console errors name their URL
con = next(f for f in tc["findings"] if "console" in f["title"])
check("7 · the console finding names the failing URL and classes a sandbox-blocked host as environment, not a project defect",
      "https://fonts.googleapis.com/css2" in con["measured"] and con["kind"] == "unverified" and "fonts.googleapis.com" in con["title"] and "Nothing to fix in the project" in con["recommendation"], con)
proj = TF.describe({"name": "phone: no console errors", "ok": False, "detail": ["Failed to load resource: the server responded with a status of 404 (Not Found)"]},
                   {"action": "smoke", "results": [{"viewport": "phone", "failed_requests": [{"url": "http://game.local/assets/hero.png", "method": "GET", "status": 404}]}]})
prox = TF.describe({"name": "phone: no console errors", "ok": False, "detail": ["Failed to load resource: net::ERR_TUNNEL_CONNECTION_FAILED"]},
                   {"action": "smoke", "results": [{"viewport": "phone", "failed_requests": [{"url": "https://api.example.com/x", "method": "POST", "failure": "net::ERR_TUNNEL_CONNECTION_FAILED"}]}]})
check("7 · a project 404 is a project defect with its URL and method; a proxy refusal is environment",
      proj["category"] == "project" and "GET http://game.local/assets/hero.png (404)" in proj["measured"] and "hero.png" in proj["do"]
      and prox["category"] == "environment" and "POST https://api.example.com/x" in prox["measured"], (proj, prox))
check("7 · the browser runner records every failed request (requestfailed) and every HTTP error response (≥ 400)",
      "page.on('requestfailed'" in mjs and "r.status() >= 400" in mjs and '"requests": [' in dpy)

# ---------------------------------------------------------------- 8. visual diff with context
vd = next(f for f in tc["findings"] if "Visual change" in f["title"])
check("8 · the visual-diff finding links a diff image (made in the report folder from the recorded images), its changed regions and a Do line",
      vd.get("diff", "").startswith(R["paths"]["dir"]) and vd["regions"] == [[0, 240, 585, 416], [112, 768, 368, 96]] and "x0 y240 585×416" in vd["measured"]
      and "11.2% of pixels differ (threshold ≤ 5%)" in vd["measured"] and "accept it as the new baseline" in vd["recommendation"] and "otherwise fix" in vd["recommendation"]
      and next(c for c in CALLS if c[0] == "testcraft_visual_diff")[1]["baseline"] == os.path.join(game, "docs/gitcraft-pass/baseline/phone_final.png"), vd)
try:
    import numpy as np
    from PIL import Image  # noqa: F401
    spec = __import__("importlib").util.spec_from_file_location("tcdept", os.path.join(REPO, "studio", "departments", "testcraft", "dept.py"))
    os.environ.setdefault("STUDIO_DIR", os.path.join(REPO, "studio"))
    tcd = __import__("importlib").util.module_from_spec(spec); spec.loader.exec_module(tcd)
    m = np.zeros((100, 200), bool); m[10:20, 10:30] = True; m[60:90, 150:190] = True
    check("8 · TestCraft's diff gives the bounding boxes of the changed regions, largest first", tcd.changed_regions(m) == [[144, 48, 48, 48], [0, 0, 32, 32]], tcd.changed_regions(m))
except Exception as e:
    print(f"SKIP region boxes (needs the Studio's numpy/PIL here: {type(e).__name__}: {e})")

# ---------------------------------------------------------------- 9. the finding contract
bad = [(f["department"], f["title"], PR.finding_problems(f)) for d in R["departments"] for f in d["findings"] if PR.finding_problems(f)]
check("9 · every finding of every department has a human title, the measured value, a Do line and the evidence path", not bad and F, bad)
check("9 · the contract rejects a finding missing them ('testcraft perf failed', no Do, no value, no path)",
      len(PR.finding_problems({"title": "testcraft perf failed"})) == 4 and PR.finding_problems({"title": "Phone frame rate below 30 FPS", "measured": "1 FPS (≥ 30)", "recommendation": "x", "source": "y"}) == [])
check("9 · no title reads like '<department> <action> failed'", not any(PR.GENERIC_TITLE.match(f["title"]) for f in F), [f["title"] for f in F])
M = open(R["paths"]["markdown"]).read(); H = open(R["paths"]["html"]).read()
check("9 · the report shows Measured and Do for findings (Markdown and HTML)", "Measured:" in M and "Do:" in M and "<b>Measured:</b>" in H and "<b>Do:</b>" in H)

# ---------------------------------------------------------------- 10. scoring
Hh = R["health"]; au = D["audiocraft"]["quality"]
check("10 · a maker department is Asset validity (N/N files valid), never averaged into the quality score",
      au["evaluation"] == "validity" and au["validity"] == {"valid": 2, "of": 2} and "audiocraft" not in Hh["parts"] and Hh["validity"]["of"] >= 2
      and any("Asset validity: 2/2 files valid" in s for s in R["summary"]), (au, Hh["parts"]))


def dept(i, v, conf, w):
    return {"id": i, "status": "current", "quality": {"evaluation": "evaluated", "value": v, "weight": w, "confidence": conf}}


O = SC.overall([dept("production", 86.7, "high", 15), dept("designcraft", 31, "low", 15), dept("testcraft", 63.2, "high", 15),
                {"id": "playcraft", "status": "no_data", "quality": {"evaluation": "not_evaluated", "value": None, "weight": 25}},
                {"id": "pixelcraft", "status": "no_data", "quality": {"evaluation": "not_evaluated", "value": None, "weight": 20}}])
check("10 · a low-confidence department carries half its weight (DESIGNCRAFT 31 at low confidence no longer counts as 15)",
      O["weights"]["designcraft"] == 7.5 and O["score"] == round((86.7 * 15 + 31 * 7.5 + 63.2 * 15) / 37.5, 1) and O["at_full_weight"] == round((86.7 + 31 + 63.2) / 3, 1), O)
check("10 · the headline carries the coverage at the same prominence ('72.5 (57% measured)') and the band is provisional under 70% coverage",
      O["headline"] == f"{O['score']} (50% measured)" and O["band"] == "provisional" and f"({round(100 * Hh['coverage'])}% measured)" in R["summary"][0]
      and "% measured)</b>" in H, (O["headline"], O["band"], R["summary"][0]))
check("10 · a high, fully covered score keeps its band; an at-risk score is not softened to provisional",
      SC.overall([dept("production", 90, "high", 15)])["band"] == "healthy"
      and SC.overall([dept("production", 40, "high", 15), {"id": "p", "status": "no_data", "quality": {"evaluation": "not_evaluated", "value": None, "weight": 25}}])["band"] == "at risk")
check("10 · the overall method changed, so no delta is claimed against a report scored the old way", SC.METHOD == "gitcraft-score/3"
      and SC.overall_delta({"health": {"score": 72.5, "method": "gitcraft-score/2"}}, O)["delta"] is None)

# ---------------------------------------------------------------- 11. refresh=quick
check("11 · no build: TestCraft says to run the project's build command (`npm run build`), never 'no data'",
      "`npm run build`" in tc["refresh"]["detail"] and not any(c[0] == "testcraft_smoke" for c in CALLS), tc["refresh"])
check("11 · the summary names the exact refresh=full call", any('refresh: "full"' in s and "npm run build" in s for s in R["summary"]), R["summary"])
check("11 · a Vite project's source index.html is not a build", PR._build_dir(game) is None)
W(game, "dist/index.html", "<!doctype html><canvas></canvas>")
CALLS.clear(); Rq = PR.generate(game, refresh="quick", save="none"); Dq = {d["id"]: d for d in Rq["departments"]}
sm = [c for c in CALLS if c[0] == "testcraft_smoke"]
check("11 · with a build (dist/), refresh=quick runs the cheap TestCraft smoke (phone only) and reads it as current",
      len(sm) == 1 and sm[0][1]["viewports"] == ["phone"] and sm[0][1]["target"] == os.path.join(game, "dist") and Dq["testcraft"]["refresh"]["ok"]
      and any("smoke-tested the existing build" in n for n in Dq["testcraft"]["notes"]), (sm, Dq["testcraft"]["refresh"]))
check("11 · PLAYCRAFT / PIXELCRAFT say which call measures them (refresh=full)", 'refresh: "full"' in Dq["playcraft"]["refresh"]["detail"], Dq["playcraft"]["refresh"])
os.remove(os.path.join(game, "dist", "index.html")); os.rmdir(os.path.join(game, "dist"))
check("read-only: the project is byte-identical after every report (only the test added and removed dist/)", tree_hash(game) == before)

# ---------------------------------------------------------------- 12. ForgeCraft survives its own build
from mcp_client import Client  # noqa: E402
env = dict(os.environ, GITCRAFT_ROOTS=WS, PYTHONPATH=REPO, FORGECRAFT_BLENDER_PY=os.path.join(WS, "no-blender", "bin", "python"))
c = Client([sys.executable, os.path.join(REPO, "forgecraft", "server.py")], env=env)
waiting = [t["name"] for t in c.tools()]; ok, st = c.call("forgecraft_status"); c.close()
fake_venv = os.path.join(WS, "venv"); os.makedirs(os.path.join(fake_venv, "bin")); os.makedirs(os.path.join(fake_venv, "lib", "python3.13", "site-packages", "bpy-5.2.3.dist-info"))
os.symlink(sys.executable, os.path.join(fake_venv, "bin", "python"))
c = Client([sys.executable, os.path.join(REPO, "forgecraft", "server.py")], env=dict(env, FORGECRAFT_BLENDER_PY=os.path.join(fake_venv, "bin", "python")))
ready = [t["name"] for t in c.tools()]; ok2, st2 = c.call("forgecraft_status"); c.close()
check("12 · forgecraft_status stays listed once Blender lands (a tool that vanishes reads as the server disconnecting)",
      waiting == ["forgecraft_status"] and "forgecraft_status" in ready and len(ready) > 5 and ok and ok2 and st2.get("state") == "ready", (waiting, ready[:4], st2))
reg = open(os.path.join(REPO, "scripts", "register.sh")).read()
check("12 · register.sh leaves an unchanged registration alone (no remove/add of a live server mid-session)",
      reg.index('grep -qxF "  Command: $here/mcp.sh"') < reg.index('claude mcp remove -s user "$name"') and "registered $name (unchanged)" in reg)
doc = subprocess.run(["bash", os.path.join(REPO, "scripts", "doctor.sh")], capture_output=True, text=True, timeout=300).stdout
dsrc = open(os.path.join(REPO, "scripts", "doctor.sh")).read()
check("12 · doctor.sh reports whether each registered 3D server is running, and how it started (before or after Blender)",
      "registered but NOT running in this session" in dsrc and "started before Blender was built" in dsrc and "waiting for Blender" in dsrc)

# ---------------------------------------------------------------- found on the acceptance run: DESIGNCRAFT through the MCP tool
# inside the studiocraft sandbox the repo root is not listable, so `import gamedesign` failed and DESIGNCRAFT dropped out of every
# report made through production_start. The server loads production/ by path; the report must load gamedesign/ the same way.
code = ("import importlib.util, sys, os; sys.path = [p for p in sys.path if os.path.realpath(p or '.') != os.path.realpath(sys.argv[1])]; "
        "p = os.path.join(sys.argv[1], 'production'); spec = importlib.util.spec_from_file_location('production', os.path.join(p, '__init__.py'), submodule_search_locations=[p]); "
        "m = importlib.util.module_from_spec(spec); sys.modules['production'] = m; spec.loader.exec_module(m)\n"
        "from production import project_report as PR\n"
        "try:\n    import gamedesign; print('repo on sys.path')\nexcept ImportError: pass\n"
        "print('engine' if hasattr(PR._package('gamedesign').engine, 'assess') else 'no engine')")
r = subprocess.run([sys.executable, "-I", "-c", code, REPO], capture_output=True, text=True, cwd="/")
check("acceptance · DESIGNCRAFT loads by path when the repo root is not importable (the MCP sandbox)", r.stdout.strip() == "engine", (r.stdout, r.stderr[-400:]))

subprocess.run(["rm", "-rf", WS])
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
