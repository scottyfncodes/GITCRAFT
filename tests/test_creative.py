#!/usr/bin/env python3
"""Creative Review (production/creative.py, production/vision.py) and its place in the Production Report.

Checks: the vision is versioned, drafted honestly and approved only by a person; the evidence pack indexes existing
captures with fingerprints and never writes into the project; the validator refuses scores, uncited or over-claimed
observations, "fun" stated as fact, unapproved vision challenges and padding; a review is bound to its commit, vision
version and evidence and is never shown as current once any of them changes; and the same technical inputs give the
same scores, verdicts, gates, priorities, plans and trends with and without a Creative Review."""
import copy, hashlib, json, os, shutil, struct, subprocess, sys, tempfile, zlib

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
WS = tempfile.mkdtemp(prefix="gcc-test-")
os.environ.update(GITCRAFT_ROOTS=WS, GITCRAFT_REPORTS=os.path.join(WS, "reports"), GITCRAFT_PRODUCTION_HOME=os.path.join(WS, "prod"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(WS, "none", "catalog.sqlite"), GITCRAFT_3D_LIBRARY=os.path.join(WS, "none-3d"),
                  GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(WS, "none-px"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(WS, "none-pc"),
                  GITCRAFT_VISION_DIR=os.path.join(WS, "vision"), GITCRAFT_CREATIVE_DIR=os.path.join(WS, "creative"))
from production import project_report as PR, creative as CR, vision as VI, scoring as SC  # noqa: E402

fails = 0


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  {str(detail)[:500]}"))
    fails += 0 if cond else 1


def raises(fn, exc=Exception, text=None):
    try: fn()
    except exc as e: return text is None or text in str(e)
    return False


def tree_hash(root):
    h = hashlib.sha256()
    for d, ds, fs in sorted(os.walk(root)):
        ds.sort()
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(os.path.relpath(p, root).encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


def png(path, rgb=(30, 120, 200), w=8, h=8):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def git(*a): return subprocess.run(["git", "-C", game, *a], capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------- a small game with recorded department outputs
game = os.path.join(WS, "orbit")
os.makedirs(os.path.join(game, "src")); os.makedirs(os.path.join(game, "qa"))
open(os.path.join(game, "README.md"), "w").write("# ORBIT\n\nORBIT is an arcade game: a one-thumb orbital dodger for phones: two-minute runs, one more try.\n\n## How to play\n\nTap to flip orbit.\n")
open(os.path.join(game, "index.html"), "w").write("<!doctype html><html lang=en><head><meta name=viewport content='width=device-width'><title>Orbit</title></head>"
                                                  "<body><canvas id=c></canvas><script src=src/main.js></script></body></html>")
open(os.path.join(game, "src", "main.js"), "w").write("const LEVELS=[{name:'One',goal:3},{name:'Two',goal:5}];\nconst c=document.getElementById('c').getContext('2d');\n"
    "let player={x:0,y:0}, score=0, enemies=[], gameOver=false;\nfunction update(){ score++; for (const e of enemies) if (hit(player,e)) gameOver=true; }\n"
    "function hit(a,b){return Math.abs(a.x-b.x)<4}\nfunction loop(){ update(); c.fillRect(player.x,player.y,4,4); requestAnimationFrame(loop); }\n"
    "addEventListener('keydown', e => { if (e.key===' ') player.y = -player.y; });\naddEventListener('pointerdown', () => { player.y = -player.y; });\nrequestAnimationFrame(loop);\n")
json.dump({"department": "testcraft", "action": "smoke", "status": "ok", "created": "2026-11-01T10:00:00+00:00",
           "checks": [{"name": "loads without console errors", "ok": True}, {"name": "no horizontal scroll on phone", "ok": False, "detail": "scrollWidth 431 > 390"}]},
          open(os.path.join(game, "qa", "smoke.studio.json"), "w"))
subprocess.run(["git", "init", "-q", game]); git("add", "-A"); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
HEAD = git("rev-parse", "HEAD")
cap = os.path.join(WS, "capture")
pc, px = os.path.join(cap, "playcraft"), os.path.join(cap, "pixelcraft")
os.makedirs(pc); os.makedirs(px)
json.dump({"git": {"head": HEAD}, "overall": {"score": 70}}, open(os.path.join(pc, "playcraft.json"), "w"))
json.dump({"metrics": {"dead_time": 0.12, "time_to_play_ms": 2100, "fps": 30.0, "viewports": {"x": 1}}}, open(os.path.join(pc, "play.json"), "w"))
png(os.path.join(pc, "play", "phone_playing.png")); png(os.path.join(pc, "play", "phone_loaded.png"), (200, 40, 40))
json.dump({"app": {"git": {"head": HEAD}}}, open(os.path.join(px, "audit.json"), "w"))
png(os.path.join(px, "gallery", "iphone17-home.png"), (240, 240, 240))
before = tree_hash(game)

# ---------------------------------------------------------------- 1. the vision contract
check("vision: no review can be packed before a vision exists (a draft is enough)", raises(lambda: CR.pack(game, [pc, px]), ValueError, "draft one first"))
V1 = VI.draft(game, {"pillars": ["one-thumb control", "runs short enough for a bus stop"], "audience": "phone players with two minutes"})
check("vision: a draft is version 1, status draft, the promise prefilled from the README with its source, missing fields listed as open questions",
      V1["version"] == 1 and V1["status"] == "draft" and "one-thumb orbital dodger" in V1["fields"]["promise"]["text"] and "README.md" in V1["fields"]["promise"]["source"]
      and any("differentiators" in q for q in V1["fields"]["open_questions"]), V1)
check("vision: clause ids are stable and citable (promise, audience, pillar:N)", set(VI.clauses(V1)) == {"promise", "audience", "pillar:1", "pillar:2"}, VI.clauses(V1))
check("vision: approval needs a person's word", raises(lambda: VI.approve(game, 1, ""), ValueError, "approved_by"))
check("vision: unknown fields are refused, not guessed", raises(lambda: VI.draft(game, {"vibe": "cool"}), ValueError, "unknown vision field"))
v1_bytes = open(V1["_path"], "rb").read()
check("vision: nothing is written inside the project", tree_hash(game) == before)

# ---------------------------------------------------------------- 2. the evidence pack
K = CR.pack(game, [pc, px])
ids = {i["id"]: i for i in K["items"]}
check("pack: screenshots, play frames and probe metrics from existing department outputs, each with a fingerprint",
      "shot:pixelcraft/gallery/iphone17-home" in ids and "frame:playcraft/play/phone_playing" in ids and ids["metric:playcraft/dead_time"]["value"] == 0.12
      and ids["frame:playcraft/play/phone_playing"]["sha256"] == hashlib.sha256(open(os.path.join(pc, "play", "phone_playing.png"), "rb").read()).hexdigest(), sorted(ids))
check("pack: only scalar metrics (nested probe data is not flattened into claims)", "metric:playcraft/viewports" not in ids)
check("pack: department findings as recorded, labelled measured or source (TestCraft's failed check)",
      any(i["kind"] == "measured_finding" and "horizontal" in i["title"] for i in K["items"]), [i["id"] for i in K["items"] if i["id"].startswith("finding:")])
check("pack: bound to the project's commit and the vision version; read-only; written outside the project",
      K["project"]["head"] == HEAD and K["vision"]["version"] == 1 and K["vision"]["status"] == "draft" and not K["paths"]["dir"].startswith(game) and tree_hash(game) == before)
B = open(K["paths"]["brief"]).read()
check("brief: says the vision is an unapproved draft, that the review is advisory and unscored, and lists the evidence to open",
      "**draft**" in B and "carries no score" in B and "frame:playcraft/play/phone_playing" in B and "hypothesis" in B)
check("pack: a folder that is not a PLAYCRAFT or PIXELCRAFT output is skipped with a warning", any("skipped" in w for w in CR.pack(game, [game, pc])["warnings"]))

# ---------------------------------------------------------------- 3. the validator
GOOD = {
    "reviewer": "test reviewer",
    "coverage": {"viewed": ["frame:playcraft/play/phone_playing", "shot:pixelcraft/gallery/iphone17-home"], "not_seen": "no tablet capture"},
    "vision_assessment": {"summary": "The one-thumb promise shows on the phone frame; the short-run promise is unproven.",
                          "delivers": [{"clause": "pillar:1", "assessment": "a single control on screen", "evidence": ["frame:playcraft/play/phone_playing"], "basis": "observed_render"}],
                          "gaps": [{"clause": "pillar:2", "assessment": "run length is not shown anywhere", "evidence": ["metric:playcraft/time_to_play_ms"], "basis": "observed_interaction"}]},
    "opportunities": [
        {"tier": "substantial", "area": "onboarding", "title": "Show the run timer", "observation": "no timer in the captured phone frame", "evidence": ["frame:playcraft/play/phone_playing"],
         "basis": "observed_render", "why_it_matters": "the promise is short runs", "recommendation": "a run clock in the HUD", "expected_improvement": "players see the promise",
         "effort": "S", "risk": "low", "confidence": "medium", "needs_approval": False, "vision_clause": "pillar:2"},
        {"tier": "transformative", "area": "mechanic", "title": "Daily seeded orbit", "observation": "every run uses the same two levels", "evidence": [], "basis": "hypothesis_playtest",
         "playtest": "five players, a week, count returns", "why_it_matters": "a reason to come back", "recommendation": "one shared seed per day", "expected_improvement": "a daily habit",
         "effort": "M", "risk": "medium", "confidence": "low", "needs_approval": True, "beyond_vision": True}],
    "strengths": [{"title": "Clear single-colour HUD", "observation": "one flat colour behind the play area", "evidence": ["shot:pixelcraft/gallery/iphone17-home"], "basis": "observed_render",
                   "why_it_works": "nothing competes with the orbit", "protect": "keep the HUD this quiet"}],
    "gameplay": {"observed": [{"claim": "the screen changes on every probe input (dead time 0.12)", "evidence": ["metric:playcraft/dead_time"], "basis": "observed_interaction"}],
                 "source_based": [{"claim": "two levels in LEVELS", "evidence": ["finding:testcraft:smoke:no-horizontal-scroll-on-phone"], "basis": "source_analysis"}],
                 "hypotheses": [{"claim": "flipping orbit may feel satisfying", "evidence": [], "basis": "hypothesis_playtest", "playtest": "watch five first runs"}]}}
GOOD["gameplay"]["source_based"][0]["evidence"] = [next(i["id"] for i in K["items"] if i["id"].startswith("finding:testcraft"))]
check("validator: a well-formed review passes", CR.validate(GOOD, K) == [], CR.validate(GOOD, K))


def bad(mut, needle, label):
    r = copy.deepcopy(GOOD); mut(r); errs = CR.validate(r, K)
    check("validator refuses: " + label, any(needle in e for e in errs), errs)


bad(lambda r: r["opportunities"][0].update(score=7), "no scores", "any score, rating or points")
bad(lambda r: r.update(rating={"overall": 4}), "no scores", "a nested rating")
bad(lambda r: r["opportunities"][0].update(evidence=[]), "needs a cited screenshot", "an observation with no captured image")
bad(lambda r: r["opportunities"][0].update(evidence=["shot:pixelcraft/never-taken"]), "not in the pack", "evidence that is not in the pack")
bad(lambda r: r["coverage"].update(viewed=["shot:pixelcraft/gallery/iphone17-home"]), "not in coverage.viewed", "an image cited as seen but not viewed")
bad(lambda r: r["strengths"][0].update(why_it_works="the loop is fun"), "hypothesis for a human playtest", "'fun' as an observation")
bad(lambda r: r["gameplay"]["observed"][0].update(claim="the controls feel satisfying"), "hypothesis for a human playtest", "'satisfying' from probe metrics")
bad(lambda r: r["opportunities"][1].update(needs_approval=False), "needs needs_approval", "a vision challenge without approval")
bad(lambda r: r["opportunities"][0].update(area="identity"), "needs needs_approval", "an identity change without approval")
bad(lambda r: r["opportunities"][0].update(vision_clause="pillar:9"), "is not in the vision", "a clause the vision does not have")
bad(lambda r: r["opportunities"].extend([dict(r["opportunities"][0], tier="polish") for _ in range(6)]), "polish", "more than five polish items")
bad(lambda r: r.pop("gameplay"), "required for a game", "a game review without the gameplay split")
bad(lambda r: r["gameplay"]["hypotheses"][0].pop("playtest"), "playtest", "a hypothesis that says nothing about how to test it")
bad(lambda r: r["gameplay"]["observed"][0].update(basis="source_analysis"), "basis must be", "source analysis filed as observed play")
bad(lambda r: r["vision_assessment"].update(summary="Verdict: it delivers."), "not 'verdict'", "calling the assessment a verdict")
bad(lambda r: r["strengths"][0].update(basis="hypothesis_playtest"), "strength is something shown", "a hypothesis passed off as a strength")
bad(lambda r: r.update(strengths=[]), "strengths", "no strengths and no note")

# ---------------------------------------------------------------- 4. the Production Report: identical technical output with and without a review
os.environ["GITCRAFT_CREATIVE_DIR"] = os.path.join(WS, "empty-creative")
R0 = PR.generate(game, refresh="none", save="none")
os.environ["GITCRAFT_CREATIVE_DIR"] = os.path.join(WS, "creative")
Rv = CR.submit(K["paths"]["pack"], GOOD)
check("submit: stored with its bindings (commit, vision version and status, pack fingerprint) and copies of the cited images",
      Rv["bound_to"]["commit"] == HEAD and Rv["bound_to"]["vision_version"] == 1 and Rv["bound_to"]["vision_status"] == "draft" and Rv["advisory"] and Rv["scored"] is False
      and all(os.path.isfile(os.path.join(Rv["_dir"], e["file"])) for e in Rv["evidence"] if e.get("file")) and not Rv["_dir"].startswith(game), Rv["bound_to"])
check("submit: an invalid review is refused with every problem listed, and nothing is stored",
      raises(lambda: CR.submit(K["paths"]["pack"], dict(GOOD, score=1)), ValueError, "no scores") and len(CR.reviews(K["project"]["id"])) == 1)
R1 = PR.generate(game, refresh="none", save="none")


def technical(R):
    T = {k: R[k] for k in ("health", "gates", "actions", "top_actions", "major_findings", "regressions", "blockers", "summary", "next_actions", "reconciliation", "levels", "identity")}
    T["departments"] = [{k: d[k] for k in ("id", "status", "score", "quality", "findings")} for d in R["departments"]]
    T["trend"] = [{k: p[k] for k in ("overall", "method", "departments")} for p in R["trend"]]
    return json.loads(json.dumps(T, default=str))


check("separation: same technical inputs → identical scores, confidence, gates, verdict, P0–P3, top three, findings, trends and summary with and without a review",
      R0.get("creative") is None and R1["creative"]["status"] == "current" and technical(R0) == technical(R1),
      [k for k in technical(R0) if technical(R0)[k] != technical(R1)[k]])
check("separation: Creative Review is not a department, has no rubric and no weight", "creative" not in SC.RUBRICS and all(d["id"] != "creative" for d in R1["departments"])
      and "creative" not in R1["health"]["parts"])
check("separation: the review carries no number into the report (no score field anywhere)", not any(CR.SCORE_KEYS.match(k) for _, k in CR._walk_keys(R1["creative"].get("opportunities"))))
H1 = PR.render_html(R1); H0 = PR.render_html(R0)
check("report: an advisory Creative Opportunity card near the top (after the summary, before the technical top three, which is unchanged)",
      "Creative opportunities · advisory judgement, not scored" in H1 and H1.index("Creative opportunities") < H1.index("id='top'") and "unapproved draft" in H1
      and "proposal · needs your approval" in H1 and H0.count("Three highest-impact next actions") == H1.count("Three highest-impact next actions") == 1)
check("report: the full section separates observed play, source analysis and playtest hypotheses", all(s in H1 for s in ("id='creative'", "Observed in automated play",
      "From source and design data", "Hypotheses for a human playtest", "beyond the vision · proposal")))
check("report: without a review, nothing creative is rendered", "Creative opportunities" not in H0 and "id='creative'" not in H0)
M1 = PR.markdown(R1)
check("markdown: the Creative Review section says it is advisory and changes nothing", "## Creative Review (advisory, not scored)" in M1 and "does not change any score" in M1)

# ---------------------------------------------------------------- 5. never automatic
calls = []
orig = (CR.pack, CR.submit)
CR.pack = lambda *a, **k: calls.append("pack"); CR.submit = lambda *a, **k: calls.append("submit")
from production import engine  # noqa: E402
PR.generate(game, refresh="quick", save="store")
CR.pack, CR.submit = orig
check("never automatic: a Production Report (refresh quick, saved) reads reviews but never packs or submits one", calls == [], calls)
src = open(os.path.join(REPO, "production", "project_report.py")).read() + open(os.path.join(REPO, "production", "engine.py")).read()
check("never automatic: the report and the engine never call pack or submit", "creative.pack(" not in src and "creative.submit(" not in src)

# ---------------------------------------------------------------- 6. staleness
st = lambda: PR.generate(game, refresh="none", save="none")["creative"]
ev0 = next(e for e in Rv["evidence"] if e.get("file")); p0 = os.path.join(Rv["_dir"], ev0["file"]); keep = open(p0, "rb").read()
open(p0, "ab").write(b"x")
C = st()
check("stale: a changed evidence copy makes the review stale (not current)", C["status"] == "stale" and any("missing or changed" in w for w in C["why"]), C)
open(p0, "wb").write(keep)
check("current again once the evidence matches its fingerprint", st()["status"] == "current")
V2 = VI.approve(game, 1, "test person, in this test")
check("vision: approval is a new version (v2 approved, approves v1); v1 is never rewritten",
      V2["version"] == 2 and V2["status"] == "approved" and V2["approves"] == 1 and open(V1["_path"], "rb").read() == v1_bytes)
C = st()
check("stale: a new vision version makes the review stale", C["status"] == "stale" and any("vision is now v2" in w for w in C["why"]), C)
Hs = PR.render_html(PR.generate(game, refresh="none", save="none"))
check("stale: the report says so and shows none of its opportunities as a current assessment",
      "is <b>stale</b>, so it is not shown as a current assessment" in Hs and "Show the run timer" not in Hs and "Daily seeded orbit" not in Hs)
K2 = CR.pack(game, [pc, px])
Rv2 = CR.submit(K2["paths"]["pack"], GOOD)
check("a new review against the approved vision is current and says 'approved'", st()["status"] == "current" and "<span class='chip ok'>approved</span>" in PR.render_html(PR.generate(game, refresh="none", save="none")))
open(os.path.join(game, "src", "main.js"), "a").write("// change\n"); git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "change")
C = st()
check("stale: a new commit makes the review stale", C["status"] == "stale" and any("now at" in w for w in C["why"]), C)
C = CR.for_report({"id": K["project"]["id"], "head": None})
check("unverified: without a checkout the commit cannot be compared, so it is not current", C["status"] == "unverified" and "opportunities" not in C, C)

# ---------------------------------------------------------------- 6b. ordering: many reviews in one second (suffixes -2 … -12)
od = os.path.join(WS, "order-creative"); pid_o = "test--order"
for rid in ["20261109T143852Z"] + [f"20261109T143852Z-{n}" for n in range(2, 13)]:
    os.makedirs(os.path.join(od, pid_o, rid))
    json.dump({"review_id": rid, "created": "2026-11-09T14:38:52+00:00"}, open(os.path.join(od, pid_o, rid, "review.json"), "w"))
_cd = os.environ["GITCRAFT_CREATIVE_DIR"]; os.environ["GITCRAFT_CREATIVE_DIR"] = od
ordered = [r["review_id"] for r in CR.reviews(pid_o)]
os.environ["GITCRAFT_CREATIVE_DIR"] = _cd
check("ordering: 12 reviews in the same second come out in creation order and the newest (-12, double-digit suffix) is latest",
      ordered == ["20261109T143852Z"] + [f"20261109T143852Z-{n}" for n in range(2, 13)] and ordered[-1].endswith("-12"), ordered)

# ---------------------------------------------------------------- 7. the tools
sys.path.insert(0, os.path.join(REPO, "studio"))
import server  # noqa: E402
names = [n for n, _, _ in server.PRODUCTION_TOOLS]
check("studiocraft exposes production_vision and production_creative (pack/submit/show; no tool runs a judgement)",
      "production_vision" in names and "production_creative" in names and "only when the person asks" in dict((n, d) for n, d, _ in server.PRODUCTION_TOOLS)["production_creative"])
out = subprocess.run([sys.executable, "-m", "production", "creative", "show", game], cwd=REPO, capture_output=True, text=True, env=dict(os.environ))
check("CLI: python3 -m production creative show", out.returncode == 0 and '"status"' in out.stdout, out.stderr[-300:])
check("skill: the creative-review skill exists and says reviews run only when asked", os.path.isfile(os.path.join(REPO, "global", "skills", "creative-review", "SKILL.md"))
      and "only when" in open(os.path.join(REPO, "global", "skills", "creative-review", "SKILL.md")).read())

shutil.rmtree(WS, ignore_errors=True)
print(f"\n{'ALL PASSED' if not fails else f'{fails} FAILED'}")
sys.exit(1 if fails else 0)
