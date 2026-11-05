#!/usr/bin/env python3
"""DESIGNCRAFT test: parser, repository inspection, the five departments, alternatives, scoring, history,
reports, the PLAYCRAFT bridge, the published web app and (unless --quick) the app in Chromium.

    tests/test_designcraft.py            everything (~1 min)
    tests/test_designcraft.py --quick    skip the browser checks

Fixtures (tests/fixtures/designcraft): patrol_ts (TypeScript data with known defects: a dangling prerequisite,
return-to-hub legs, a spawn spike, a doc/data contradiction, an economy gap), tiled_yarn (Tiled map + Yarn
dialogue with one broken jump), empty_repo (docs only) and godot_only (an unsupported engine). Exit 1 on any failure."""
import hashlib, json, os, shutil, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
QUICK = "--quick" in sys.argv
FIX = os.path.join(HERE, "fixtures", "designcraft")
ws = tempfile.mkdtemp(prefix="designcraft-test-")
os.environ["GITCRAFT_DESIGNCRAFT_HISTORY"] = os.path.join(ws, "history")
os.environ["GITCRAFT_PLAYCRAFT_ARCHIVE"] = os.path.join(ws, "no-archive")
from gamedesign.extract import jsparse
from gamedesign import engine, history, report, site, scoring, playcraft_bridge

results = []


def check(name, ok, detail=None):
    ok = bool(ok); results.append(ok); print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"   -> {str(detail)[:300]}"))


def tree_hash(root):
    h = hashlib.sha256()
    for d, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            p = os.path.join(d, f); h.update(p.encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


# ------------------------------------------------------------------ parser
src = """
/** The missions. */
export const A: Thing[] = [ { id: 'a', n: 1_000, t: `x ${y}`, neg: -2.5, hex: 0xff, re: /ab+c/g, f: (x) => x * 2, ...rest, }, ];
const B = { 'k-1': true, k2: null, nested: { arr: [1, 2, 3] }, calc: 60 * 2, ref: A, call: P('station'), } as const;
// a comment with a ' quote
b.person('mara', 'Mara Okonjo', 'Board shop', pt(1, 2), { visible: false });
"""
m = jsparse.parse_module(src)
A = jsparse.plain(m["decls"]["A"]["value"]); B = jsparse.plain(m["decls"]["B"]["value"])
check("parser: array of objects with numeric separators, templates, negatives, hex", A[0]["n"] == 1000 and A[0]["t"] == "x ${y}" and A[0]["neg"] == -2.5 and A[0]["hex"] == 255, A)
check("parser: regex, arrow functions and spreads become markers, not guesses", "$expr" in A[0]["re"] and "$expr" in A[0]["f"] and "$spreads" in A[0], A[0])
check("parser: quoted keys, booleans, null, nested arrays, folded arithmetic, refs, calls, `as const`",
      B["k-1"] is True and B["k2"] is None and B["nested"]["arr"] == [1, 2, 3] and B["calc"] == 120 and B["ref"] == {"$ref": "A"} and B["call"]["$call"] == "P", B)
check("parser: doc comments and source lines are kept", m["decls"]["A"]["doc"] == "The missions." and m["decls"]["A"]["line"] == 3 and A[0]["_L"] == 3, m["decls"]["A"])
check("parser: builder calls with literal arguments", m["calls"] and m["calls"][0]["method"] == "person" and m["calls"][0]["args"][1] == "Mara Okonjo", m["calls"])

# ------------------------------------------------------------------ patrol_ts: known defects
before = tree_hash(os.path.join(FIX, "patrol_ts"))
P = engine.assess(os.path.join(FIX, "patrol_ts"), playcraft=False)
check("read-only: assessing a game leaves every file byte-identical", tree_hash(os.path.join(FIX, "patrol_ts")) == before)
kinds = {f["kind"]: f for f in P["findings"]}
check("model: missions, places, stage curves and upgrades recognised", len(P["model"]["missions"]) == 4 and len(P["model"]["places"]) == 8 and len(P["model"]["stages"]) == 6 and len(P["model"]["progression"]) == 6,
      {k: len(v) for k, v in P["model"].items() if isinstance(v, list)})
d = kinds.get("dangling_requires")
check("missioncraft: dangling prerequisite found, source verified, cites the right file and line",
      d and d["level"] == "source_verified" and d["severity"] == "critical" and "ghost_mission" in d["title"] and d["evidence"][0]["file"] == "src/missions.ts" and d["evidence"][0]["line"] == 15, d)
r = kinds.get("return_leg")
check("levelcraft: every mission ending with a return to the hub is detected", r and "4 of 4" in r["title"] and "Harbour Office" in r["title"], r and r["title"])
check("levelcraft: places reached by missions measured (5 of 8; below the 40% unused threshold, so no finding)", P["departments"]["levelcraft"]["metrics"]["named_places_used_by_missions"] == "5/8" and "unused_space" not in kinds, P["departments"]["levelcraft"]["metrics"])
sp = kinds.get("difficulty_spike")
check("progressioncraft: spawn spike in WAVES located (5 → 6), intro step not counted", sp and sp["data"]["from"].endswith("5") and sp["data"]["to"].endswith("6"), sp and sp["title"])
dc = kinds.get("doc_contradiction")
check("storycraft: README count vs data contradiction (12 stated, 4 defined)", dc and dc["data"]["stated"] == 12 and dc["data"]["actual"] == 4 and dc["level"] == "source_verified", dc and dc["title"])
check("progressioncraft: economy gap measured from real rewards and prices", "economy_gap" in kinds and kinds["economy_gap"]["data"]["income"] == 400 and kinds["economy_gap"]["data"]["prices"] == 7100, kinds.get("economy_gap", {}).get("data"))
check("missioncraft: repeated structure names the missions that share it", "skeleton_repetition" in kinds and "First Shift" in kinds["skeleton_repetition"]["summary"], kinds.get("skeleton_repetition", {}).get("summary"))
check("experiencecraft: a cross-system finding needing two departments (travel + reward friction)", "friction_stack" in kinds and kinds["friction_stack"]["dept"] == "experiencecraft", list(kinds))
check("every finding has facts with evidence levels and a claim level", all(f["evidence"] and all(e["level"] in ("source_verified", "simulated", "playtested", "inferred", "untested") for e in f["evidence"]) and f["level"] for f in P["findings"]))
check("no inferred judgement is labelled as observed play (no simulated/playtested without PLAYCRAFT)", not any(f["level"] in ("simulated", "playtested") or any(e["level"] in ("simulated", "playtested") for e in f["evidence"]) for f in P["findings"]))
# alternatives
need = ("existing", "problem", "why", "proposal", "experience", "complexity", "tradeoffs", "validation")
sig = [f for f in P["findings"] if f["severity"] != "info"]
props = {p["id"]: p for p in P["proposals"]}
check("alternatives: three (conservative, ambitious, wild card) for every significant finding",
      all(sorted(props[i]["variant"] for i in f["proposals"]) == ["ambitious", "conservative", "wildcard"] for f in sig), [(f["id"], f["proposals"]) for f in sig if len(f["proposals"]) != 3][:3])
check("alternatives: every proposal carries all eight required parts and a measurable validation",
      all(all(p.get(k) for k in need) and all(p["validation"].get(k) for k in ("metric", "current", "target", "method")) for p in P["proposals"]))
rl = [props[i] for i in kinds["return_leg"]["proposals"]]
check("alternatives reference the game's actual content (mission names, hub)", all("Harbour Office" in (p["proposal"] + " ".join(p["changes"])) for p in rl) and "First Shift" in " ".join(rl[0]["changes"]), rl[0]["changes"])
check("alternatives: expected outcomes are labelled inferred", all(p["evidence_level"] == "inferred" for p in P["proposals"]))
check("design lab: three alternatives for every mission, original kept as 'existing'", all(len(v) == 3 and v[0]["existing"].startswith(next(m["title"] for m in P["model"]["missions"] if m["id"] == k)) for k, v in P["lab"].items()))
# scoring
S = P["score"]
check("scoring: categories are 15/15/15/15/10/10/10/10 = 100", [c["max"] for c in S["categories"].values()] == [15, 15, 15, 15, 10, 10, 10, 10])
check("scoring: every score ≤ its ceiling ≤ its maximum, coverage in [0,1]", all(0 <= c["score"] <= c["ceiling"] + 1e-9 <= c["max"] + 1e-9 and 0 <= c["coverage"] <= 1 for c in S["categories"].values()) and S["overall"] <= S["ceiling"])
check("scoring: every category has score, evidence, weaknesses, confidence and criteria", all(set(("score", "criteria", "weaknesses", "confidence", "evidence_levels")) <= set(c) for c in S["categories"].values()))
check("scoring: no high confidence without simulated or playtested evidence", all(c["confidence"] != "high" for c in S["categories"].values()))
P2 = engine.assess(os.path.join(FIX, "patrol_ts"), playcraft=False)
check("scoring is deterministic (same repo → same score and findings)", P2["score"]["overall"] == S["overall"] and [f["id"] for f in P2["findings"]] == [f["id"] for f in P["findings"]])

# ------------------------------------------------------------------ tiled + yarn
T = engine.assess(os.path.join(FIX, "tiled_yarn"), playcraft=False)
names = {c["name"] for c in T["model"]["characters"]}
check("tiled: map objects become places and encounters (with properties)", any(p["name"] == "Old Chest" for p in T["model"]["places"]) and any(e["name"] == "Skeleton" and e["stats"].get("hp") == 12 for e in T["model"]["encounters"]), T["model"]["encounters"])
check("yarn: speakers become characters and choices are counted", {"Warden", "Ivy"} <= names and T["departments"]["storycraft"]["metrics"]["scripted_choices"] == 2, (names, T["departments"]["storycraft"]["metrics"]))
br = [f for f in T["findings"] if f["kind"] == "dangling_reference"]
check("yarn: only the broken jump (to 'Missing') is reported", len(br) == 1 and br[0]["data"]["missing"] == "Missing", [f["title"] for f in br])

# ------------------------------------------------------------------ missing and unsupported data
E = engine.assess(os.path.join(FIX, "empty_repo"), playcraft=False)
G = engine.assess(os.path.join(FIX, "godot_only"), playcraft=False)
check("missing data: an empty repository gets no invented findings and no proposals", not E["findings"] and not E["proposals"], [f["title"] for f in E["findings"]])
check("missing data: score 0, low confidence, coverage ≈ 0, limitations explain why", E["score"]["overall"] == 0 and E["score"]["confidence"] == "low" and E["score"]["coverage"] <= 0.05 and len(E["inspection"]["limitations"]) >= 4)
check("unsupported engine: Godot scenes are counted and reported, not guessed", G["inspection"]["unsupported"].get("Godot scene") == 2 and any("Godot scene" in l["text"] for l in G["inspection"]["limitations"]) and not G["findings"], G["inspection"]["unsupported"])
check("departments with no data say so instead of scoring it", all(G["departments"][k].get("note") for k in ("levelcraft", "missioncraft", "storycraft")))

# ------------------------------------------------------------------ CLI read-only guard
cli = subprocess.run([sys.executable, "-m", "gamedesign", "assess", os.path.join(FIX, "patrol_ts"), "--no-playcraft", "--out", os.path.join(FIX, "patrol_ts", "x.json")], cwd=REPO, capture_output=True, text=True)
check("cli: refuses to write outputs inside the game repository", cli.returncode == 2 and not os.path.exists(os.path.join(FIX, "patrol_ts", "x.json")), cli.stderr)
cli = subprocess.run([sys.executable, "-m", "gamedesign", "assess", os.path.join(FIX, "patrol_ts"), "--no-playcraft", "--out", os.path.join(ws, "a.json"), "--report", os.path.join(ws, "r.md")], cwd=REPO, capture_output=True, text=True, env=os.environ)
check("cli: assess writes the assessment and the report", cli.returncode == 0 and os.path.exists(os.path.join(ws, "a.json")) and json.loads(cli.stdout)["overall"] == S["overall"], cli.stderr[-300:])

# ------------------------------------------------------------------ reports and specs
md = report.assessment_md(P)
check("report: overall, categories, evidence, priorities, every department, proposals, validation", all(s in md for s in ("## Overall", "## Evidence and limitations", "## Priorities", "## LEVELCRAFT", "## MISSIONCRAFT", "## STORYCRAFT", "## PROGRESSIONCRAFT", "## EXPERIENCECRAFT", "A · Conservative", "B · Ambitious", "C · Wild card", "*Validate:*")))
spec = report.spec_md(P, rl[0]["id"])
check("spec export: implementation-ready sections, cites evidence", all(s in spec for s in ("## Existing design (preserved)", "## Evidence", "## Change", "## Validation", "## Acceptance")) and "src/missions.ts" in spec)

# ------------------------------------------------------------------ history
p1 = history.record(engine.assess(os.path.join(FIX, "patrol_ts"), playcraft=False))
import time; time.sleep(1.1)
A2 = engine.assess(os.path.join(FIX, "patrol_ts"), playcraft=False); p2 = history.record(A2)
check("history: a re-run of unchanged content under the same method is a control", A2["compare"]["kind"] == "control" and A2["compare"]["overall"]["delta"] == 0, A2["compare"])
try:
    history.record(json.load(open(p2))); dup = False
except FileExistsError:
    dup = True
check("history: append-only (an existing run cannot be overwritten)", dup)
A3 = json.load(open(p2)); A3["method"] = "different"; A3["game"]["content_sha256"] = "f" * 64
check("history: a different method is reported as not comparable", history.compare(json.load(open(p1)), A3)["kind"] == "method_changed")
idx = [json.loads(l) for l in open(os.path.join(history.store(), "index.jsonl"))]
check("history: index lists every recorded run", len(idx) == 2 and idx[-1]["game"] == "patrol-ts")

# ------------------------------------------------------------------ PLAYCRAFT bridge
arc = os.path.join(ws, "pc-archive", "games", "someone--patrol-ts", "runs"); os.makedirs(arc)
json.dump({"game_id": "someone--patrol-ts", "run_id": "r1", "criteria": {"df.ramp": {"s": "fail", "l": "verified", "c": "difficulty", "t": "Difficulty ramps", "d": "spikes at wave 6"},
                                                                          "pg.loop": {"s": "pass", "l": "inferred", "c": "progression", "t": "Loop"}}, "metrics": {"time_to_play_ms": 1200}, "overall": {"score": 70}},
          open(os.path.join(arc, "20260101-pass.json"), "w"))
os.environ["GITCRAFT_PLAYCRAFT_ARCHIVE"] = os.path.join(ws, "pc-archive")
B = engine.assess(os.path.join(FIX, "patrol_ts"), playcraft=True)
check("playcraft bridge: verified/observed criteria imported as simulated, inferred ones ignored", B["playcraft"] and [c["id"] for c in B["playcraft"]["criteria"]] == ["df.ramp"] and B["playcraft"]["criteria"][0]["level"] == "simulated", B["playcraft"])
check("playcraft bridge: the simulated difficulty check feeds its scoring criterion", next(c for c in B["score"]["categories"]["difficulty"]["criteria"] if c["id"] == "difficulty.simulated")["level"] == "simulated")
check("playcraft bridge: nothing is ever imported as playtested", not any(e["level"] == "playtested" for f in B["findings"] for e in f["evidence"]))
os.environ["GITCRAFT_PLAYCRAFT_ARCHIVE"] = os.path.join(ws, "no-archive")

# ------------------------------------------------------------------ site
dist = os.path.join(ws, "dist"); history.record(T)
n = site.publish(history.store(), dist)
ix = json.load(open(os.path.join(dist, "data", "index.json")))
check("site: publishes the app, an index, per-game data and reports", n == 2 and all(os.path.exists(os.path.join(dist, f)) for f in ("index.html", "app.js", "app.css", "data/patrol-ts.json", "data/patrol-ts.report.md")) and len(ix["games"]) == 2)
check("site: per-game data carries its history", len(json.load(open(os.path.join(dist, "data", "patrol-ts.json")))["history"]) == 2)
node_ok = subprocess.run(["node", "--check", os.path.join(dist, "app.js")], capture_output=True).returncode == 0
check("site: app.js is valid JavaScript", node_ok)

# ------------------------------------------------------------------ browser
if not QUICK:
    out = subprocess.run(["node", os.path.join(HERE, "designcraft_browser.js"), dist, "patrol-ts", ""], capture_output=True, text=True, timeout=300)
    try: R = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception: R = None
    check("browser: ran", R is not None, out.stderr[-500:])
    if R:
        C = R["checks"]
        check("browser: no page or console errors (iPhone 13 + desktop)", not R["errors"], R["errors"])
        check("browser: no horizontal overflow on any tab", not R["overflow"], R["overflow"])
        check("browser: all nine tabs render a heading on both devices", all(v["h1"] for v in R["tabs"].values()) and len(R["tabs"]) == 18, {k: v for k, v in R["tabs"].items() if not v["h1"]})
        check("browser: visualisations render (map, level layout, dependencies, curves, journey)", all(R["tabs"][f"desktop:{t}"]["svgs"] >= 1 for t in ("map", "levelcraft", "missioncraft", "progression", "experience")), R["tabs"])
        for dev in ("phone", "desktop"):
            check(f"browser {dev}: portfolio, criteria sheet, finding with three alternatives, map detail", C[dev + "_portfolio_lists_games"] == 2 and C[dev + "_criteria_sheet"] >= 4 and C[dev + "_finding_alternatives"] == 3 and C[dev + "_map_detail"], C)
            check(f"browser {dev}: lab refine makes v1, says what changed, admits what it cannot do", "Done:" in C[dev + "_refine_reply"] and "rule-based" in C[dev + "_refine_unknown_reply"] and C[dev + "_refined_chip"] >= 1, (C[dev + "_refine_reply"], C[dev + "_refine_unknown_reply"]))
            check(f"browser {dev}: original design unchanged; save persists; compare; spec export", C[dev + "_original_unchanged"] and C[dev + "_saved_persists"] == 1 and C[dev + "_compare_columns"] == 3 and C[dev + "_spec_sections"], C)

shutil.rmtree(ws, ignore_errors=True)
n_ok = sum(results)
print(f"\n{n_ok}/{len(results)} checks passed")
sys.exit(0 if n_ok == len(results) else 1)
