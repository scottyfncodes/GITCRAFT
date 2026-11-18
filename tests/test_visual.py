#!/usr/bin/env python3
"""Visual direction, picture-first (plan v3, production/visual.py, docs/visual-direction.md).

  1. the atlas: 12–16 looks, every look rendered (two samples), named phrases, the cannot-do list
  2. scope: a new product gets two picks; a named style skips the style pick; an existing identity with no new look skips both
  3. validators: the shortlist, the designs (differ on composition, type, palette and flavour; pictures differ), the shot list,
     the direction (style, target, references, accepted tells, moments, a shot per moment), the review rules
  4. the engine, end to end on a tiny real game: style pick (never chosen silently; one, two or surprise), design pick (the
     build waits for it), the chosen frame saved as the target, moments expanded into work orders, the shot list captured in
     Chromium (an unreachable shot is NOT SEEN), the automatic review's gap → a work order → a fresh capture and review, the
     look page; and the verdict, the criteria and every score untouched by all of it
  5. plan v2 records keep the v2 graph; nothing here runs in a v1 or v2 plan

Fast: no department but TestCraft's shot capture and smoke run (Chromium)."""
import copy, json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-visual-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"), GITCRAFT_PRODUCTION_REPORT="0",
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import intake, planner, engine, store, visual, icons, report, direction
from production import PASSED, PENDING, NEEDS_APPROVAL, AWAITING_AGENT
fails = 0
QUICK = "--quick" in sys.argv


def check(label, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + label + ("" if cond else f"  [{str(detail)[:500]}]"), flush=True)
    fails += 0 if cond else 1


def png(path, w, h, rgb, stripe=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    px = bytearray()
    for y in range(h):
        for x_ in range(w):
            c = stripe if stripe and (x_ // 20 + y // 20) % 2 else rgb
            px += bytes(c) + b"\xff"
    icons.encode(path, w, h, px)
    return path


# ---------------------------------------------------------------- 1. the atlas
A = visual.atlas()
looks = A["looks"]
check("atlas: 12 to 16 looks, numbered 1..n, unique ids", 12 <= len(looks) <= 16 and [l["n"] for l in looks] == list(range(1, len(looks) + 1))
      and len({l["id"] for l in looks}) == len(looks), len(looks))
check("atlas: every look has a plain name, what it suits, an honest 'hard' note, a family and fonts",
      all(l["name"] and len(l["suits"]) > 20 and len(l["hard"]) > 20 and l["family"] in A["families"] and l["fonts"] for l in looks))
check("atlas: the looks span every family (2D vector, raster, type, 3D, shader)", {l["family"] for l in looks} == set(A["families"]), {l["family"] for l in looks})
check("atlas: a section for looks we cannot do well, each with why", len(A["cannot"]) >= 4 and all(len(c["why"]) > 40 for c in A["cannot"])
      and {"Painterly", "Photoreal", "Detailed characters", "Frame-by-frame animation"} <= {c["name"] for c in A["cannot"]})
check("atlas: every look has its painter", all(os.path.isfile(os.path.join(visual.ATLAS_DIR, "looks", l["id"] + ".js")) for l in looks),
      [l["id"] for l in looks if not os.path.isfile(os.path.join(visual.ATLAS_DIR, "looks", l["id"] + ".js"))])
samples = os.path.join(visual.ATLAS_DIR, "samples")
check("atlas: every look is rendered as the same two samples (game scene, phone app screen)",
      all(os.path.isfile(os.path.join(samples, l["id"], f)) for l in looks for f in ("game.webp", "app.webp")),
      [l["id"] for l in looks if not os.path.isfile(os.path.join(samples, l["id"], "game.webp"))])
check("atlas: accepted tells name real PIXELCRAFT tells, with a reason", all(t["id"] in visual.TELLS and len(t["reason"]) > 10 for l in looks for t in l["tells"]))

# ---------------------------------------------------------------- 2. named styles and scope
ns = visual.named_style
check("named: 'neon vector arcade' names Neon Vector", (ns("a neon vector arcade shooter") or {}).get("look") == "neon-vector")
check("named: 'like atlas look 7 but warmer' → look 7 with the modifier", (ns("like atlas look 7 but warmer") or {}) .get("n") == 7 and ns("like atlas look 7 but warmer")["modifier"] == "warmer")
check("named: a subject word is not a style ('a map app for hikers', 'a game about blocks')", ns("a map app for hikers") is None and ns("a game about blocks") is None)
DISC = {"project": {}}
Q = {"quality": {"playcraft": False, "pixelcraft": False, "perf": False, "designcraft": False}, "icon": {"required": False}, "attribution": {"required": False},
     "assets": {"identity": False, "sfx": [], "music": None}}
def plan(prompt, version=3, **over):
    sp = intake.parse(prompt, overrides=dict(copy.deepcopy(Q), **over)); return planner.build(sp, DISC, version=version), sp
p3, _ = plan("Make a tiny one-button game called Kite Line")
T3 = p3["tasks"]
check("plan v3: a new game gets the style pick and the design pick before the direction, and the build waits for both",
      {"design.styles", "design.style_pick", "design.designs", "design.design_pick"} <= set(T3) and "design.design_pick" in T3["design.direction"]["depends_on"]
      and {"design.style_pick", "design.design_pick"} <= set(T3["build"]["depends_on"]), T3["build"]["depends_on"])
check("plan v3: after the build, moments, the shot capture, the review and its gaps; QA waits for the review; the look page last",
      all(k in T3 for k in ("design.moments", "capture.shots", "review.pack", "review.creative", "review.gaps", "release.shots", "release.look"))
      and "review.gaps" in T3["qa.smoke"]["depends_on"] and p3["order"][-1] == "release.look")
check("plan v3: every visual step after the build is advisory (never a criterion or a gate on the verdict)",
      all(T3[k]["advisory"] and not T3[k]["criterion"] for k in ("capture.shots", "review.pack", "review.creative", "review.gaps", "release.shots", "release.look")))
check("plan v3: the two picks are the only visual approvals (no more questions)", [k for k, t in T3.items() if t.get("action") in ("style_pick", "design_pick")] == ["design.style_pick", "design.design_pick"])
check("plan v3: validates (every department request accepted)", not planner.validate(p3), planner.validate(p3))
pn, _ = plan("Make a neon vector arcade game about bees")
check("plan v3: a named style skips the style pick (recorded from the request), the design pick stays",
      "design.styles" not in pn["tasks"] and pn["tasks"]["design.style_pick"]["params"]["named"]["look"] == "neon-vector" and "design.design_pick" in pn["tasks"])
pa, _ = plan("Build a tide times app for my beach")
check("plan v3: a new app gets both picks too", {"design.styles", "design.design_pick"} <= set(pa["tasks"]))
sp_keep = intake.parse("Polish this game: tighten the HUD", overrides=dict(copy.deepcopy(Q), mode={"existing": True, "workflow": "update", "focus": "polish"}))
vk = visual.scope(sp_keep)
check("scope: an existing identity with no new look asked for skips both picks (its current best screen is the target)", vk and vk["mode"] == "keep" and not vk["designs"], vk)
sp_red = intake.parse("Give this game a new look", overrides=dict(copy.deepcopy(Q), mode={"existing": True, "workflow": "update", "focus": "visual"}))
check("scope: a redesign of an existing project gets both picks", (visual.scope(sp_red) or {}).get("mode") == "pick")
p2, _ = plan("Make a tiny one-button game called Kite Line", version=2)
check("plan v2: unchanged (no visual task; the direction keeps its v2 gate)", not any(k.startswith(("design.style", "design.design", "capture.", "review.", "release.look")) for k in p2["tasks"])
      and p2["tasks"]["design.direction"]["work_order"]["expected"][0]["validate"] == "direction")
check("engine: a new production is plan v3", planner.PLAN_VERSION == 3)

# ---------------------------------------------------------------- 3. validators
vd = os.path.join(ws, "val"); os.makedirs(vd)
ids6 = ["flat-geometric", "neon-vector", "pixel-art", "swiss-grid", "low-poly-3d", "topographic"]
cols = [(230, 80, 60), (20, 220, 240), (90, 160, 60), (240, 240, 240), (60, 80, 200), (200, 170, 110), (120, 20, 120), (10, 10, 10)]
for i, l in enumerate(ids6): png(os.path.join(vd, "styles", l, "game.png"), 640, 360, cols[i])
S = {"product": "game", "scene": "scene.json", "recommended": "flat-geometric", "reason": "bright silhouettes read on a small phone in a moving train",
     "wildcard": "topographic", "styles": [{"look": l, "image": f"styles/{l}/game.png", "why": "suits a wind-driven kite world for this reason"} for l in ids6], "references": []}
json.dump(S, open(os.path.join(vd, "styles.json"), "w"))
ok = lambda r: all(c["ok"] for c in r)
check("shortlist: six looks across families, each rendered, a recommendation and a wildcard: accepted", ok(visual.validate_styles(os.path.join(vd, "styles.json"), vd)),
      [c for c in visual.validate_styles(os.path.join(vd, "styles.json"), vd) if not c["ok"]])
bad = dict(S, styles=S["styles"][:4]); json.dump(bad, open(os.path.join(vd, "s2.json"), "w"))
check("shortlist: fewer than six refused", not ok(visual.validate_styles(os.path.join(vd, "s2.json"), vd)))
bad = dict(S, wildcard=S["recommended"]); json.dump(bad, open(os.path.join(vd, "s3.json"), "w"))
check("shortlist: a wildcard that is the recommendation refused", not ok(visual.validate_styles(os.path.join(vd, "s3.json"), vd)))
bad = copy.deepcopy(S); bad["styles"][1]["image"] = bad["styles"][0]["image"]; json.dump(bad, open(os.path.join(vd, "s4.json"), "w"))
check("shortlist: the same picture shown twice refused", not ok(visual.validate_styles(os.path.join(vd, "s4.json"), vd)))
bad = copy.deepcopy(S); bad["styles"] = [dict(s, look=l) for s, l in zip(S["styles"], ["flat-geometric", "blueprint", "linocut", "isometric", "notebook", "neon-vector"])]
for s in bad["styles"]: png(os.path.join(vd, "styles", s["look"], "game.png"), 640, 360, cols[bad["styles"].index(s) + 1]); s["image"] = f"styles/{s['look']}/game.png"
json.dump(bad, open(os.path.join(vd, "s5.json"), "w"))
check("shortlist: one corner of the atlas (two families) refused", not ok(visual.validate_styles(os.path.join(vd, "s5.json"), vd)),
      visual.families([s["look"] for s in bad["styles"]]))

def design(i, style, **over):
    d = {"id": "abc"[i], "style": style, "name": f"Design {i}", "idea": ["a kite festival poster pasted on a pier wall", "a wind gauge on a coastguard hut", "a child's paper kite flown at dusk"][i],
         "composition": ["giant title stacked left, kite cutting the corner diagonally", "centred dial gauge with the play button at its needle", "full-bleed sky photo-like gradient with a tiny kite at the bottom right"][i],
         "type": {"display": ["Outfit", "Barlow Condensed", "Fraunces"][i], "body": "Overpass"},
         "palette": [{"background": "#f6e7c8", "surface": "#fff8ea", "primary": "#e4572e", "accent": "#2e86ab", "text": "#20323f"},
                     {"background": "#0f2a3a", "surface": "#173b50", "primary": "#ffd166", "accent": "#06d6a0", "text": "#f1f7fa"},
                     {"background": "#2b1d3a", "surface": "#3c2a50", "primary": "#ff9f80", "accent": "#9ad1d4", "text": "#fbeee6"}][i],
         "flavor": ["loud festival bunting", "calm instrument precision", "quiet evening nostalgia"][i],
         "html": f"{'abc'[i]}/index.html", "phone": f"{'abc'[i]}/phone.png", "desktop": f"{'abc'[i]}/desktop.png", "play": f"{'abc'[i]}/play.png"}
    d.update(over); return d
def write_designs(base, D, colours=((246, 231, 200), (15, 42, 58), (230, 120, 170))):
    for i, d in enumerate(D["designs"]):
        os.makedirs(os.path.join(base, d["id"]), exist_ok=True); open(os.path.join(base, d["html"]), "w").write("<!doctype html><title>x</title>")
        png(os.path.join(base, d["phone"]), 96, 200, colours[i % 3]); png(os.path.join(base, d["desktop"]), 200, 125, colours[i % 3]); png(os.path.join(base, d["play"]), 200, 112, colours[i % 3])
    json.dump(D, open(os.path.join(base, "designs.json"), "w"))
    return os.path.join(base, "designs.json")
dd = os.path.join(ws, "designs-ok"); D3 = {"product": "game", "style": "flat-geometric", "recommended": "a", "reason": "the poster reads at thumbnail size on a phone",
                                          "designs": [design(i, "flat-geometric") for i in range(3)]}
check("designs: three that differ in composition, type, palette and flavour, each with phone, desktop and play renders: accepted",
      ok(visual.validate_designs(write_designs(dd, D3), dd)), [c for c in visual.validate_designs(os.path.join(dd, "designs.json"), dd) if not c["ok"]])
dc = os.path.join(ws, "designs-colour"); Dc = copy.deepcopy(D3)
for d in Dc["designs"]: d.update(composition=D3["designs"][0]["composition"], type=D3["designs"][0]["type"], flavor=D3["designs"][0]["flavor"])
check("designs: colour swaps of one design refused (they must differ in composition, type and flavour too)", not ok(visual.validate_designs(write_designs(dc, Dc), dc)))
ds = os.path.join(ws, "designs-same")
check("designs: three identical pictures refused, whatever their notes say",
      not ok(visual.validate_designs(write_designs(ds, copy.deepcopy(D3), colours=((200, 200, 200),) * 3), ds)))
json.dump({"styles": ["flat-geometric", "pixel-art"], "how": "compare"}, open(os.path.join(dd, "style_selection.json"), "w"))
check("designs: when two styles are compared, two designs in each are required", not ok(visual.validate_designs(os.path.join(dd, "designs.json"), dd)))
os.remove(os.path.join(dd, "style_selection.json"))
SH = {"product": "game", "shots": [
    {"id": "title", "name": "Title, fully loaded", "kind": "title", "steps": [], "wait_for": {"selector": "#title[data-ready]"}},
    {"id": "play", "name": "Mid-play", "kind": "play", "steps": [{"press": "Space"}], "wait_for": {"js": "window.__game.state === 'playing' && window.__game.time > 0.3"}},
    {"id": "first-ribbon", "name": "The first ribbon", "kind": "moment", "moment": "first-ribbon", "steps": [{"press": "Space"}], "wait_for": {"js": "window.__game.score >= 1"}},
    {"id": "fail", "name": "Grounded", "kind": "fail", "steps": [{"press": "Space"}], "wait_for": {"js": "window.__game.state === 'over'"}},
    {"id": "results", "name": "Results", "kind": "results", "steps": [{"press": "Space"}], "wait_for": {"selector": "#results"}},
    {"id": "title-reveal", "name": "The title reveal", "kind": "moment", "moment": "title-reveal", "steps": [], "wait_for": {"selector": "#title[data-ready]"}}]}
sp_ = os.path.join(vd, "shots.json"); json.dump(SH, open(sp_, "w"))
check("shots: named shots with steps and a wait for real content: accepted", ok(visual.validate_shots(sp_)), [c for c in visual.validate_shots(sp_) if not c["ok"]])
bad = copy.deepcopy(SH); bad["shots"][1]["wait_for"] = {}; bad["shots"][1]["steps"].append({"wait": 2000}); json.dump(bad, open(os.path.join(vd, "sh2.json"), "w"))
check("shots: a fixed delay instead of a wait for real content refused", not ok(visual.validate_shots(os.path.join(vd, "sh2.json"))))
bad = copy.deepcopy(SH); bad["shots"] = [s for s in bad["shots"] if s["kind"] != "fail"]; json.dump(bad, open(os.path.join(vd, "sh3.json"), "w"))
check("shots: a game's list without a fail shot refused", not ok(visual.validate_shots(os.path.join(vd, "sh3.json"))))

# review rules
K = {"items": [{"id": "target:phone", "kind": "target", "path": "x", "sha256": "1"}, {"id": "shot:title@phone", "kind": "screenshot", "path": "y", "sha256": "2", "shot": "title"}],
     "not_seen": [{"shot": "results", "viewport": "phone", "reason": "timeout"}]}
good = {"reviewer": "test", "coverage": {"viewed": ["shot:title@phone", "target:phone"]}, "summary": "an assessment of the title against the chosen frame",
        "matches": [{"against": "target", "claim": "the title keeps the stacked composition", "evidence": ["shot:title@phone", "target:phone"], "basis": "observed_render"}],
        "gaps": [{"id": "g1", "shot": "title", "against": "target", "gap": "the title face is the system font, not Outfit", "fix": "load the Outfit file and set it on h1",
                  "evidence": ["shot:title@phone"], "basis": "observed_render", "severity": "major"}]}
check("review: a cited, viewed, unscored review is valid", not visual.review_errors(good, K), visual.review_errors(good, K))
b = copy.deepcopy(good); b["gaps"][0]["score"] = 3
check("review: any score key refused", any("no scores" in e for e in visual.review_errors(b, K)))
b = copy.deepcopy(good); b["gaps"][0]["shot"] = "results"; b["gaps"][0]["evidence"] = []
check("review: a shot that was not seen cannot be judged", any("not seen" in e for e in visual.review_errors(b, K)))
b = copy.deepcopy(good); b["coverage"]["viewed"] = ["target:phone"]
check("review: 'observed' needs the cited shot to have been viewed", any("coverage.viewed" in e for e in visual.review_errors(b, K)))
b = copy.deepcopy(good); b["matches"][0]["claim"] = "the title screen is fun and engaging"
check("review: fun / engaging is a playtest hypothesis, never an observation", any("playtest hypothesis" in e for e in visual.review_errors(b, K)))
b = copy.deepcopy(good); b["summary"] = "verdict: it matches"
check("review: 'assessment', never 'verdict'", any("verdict" in e for e in visual.review_errors(b, K)))

# ---------------------------------------------------------------- 4. the engine, end to end
proj = os.path.join(ws, "kite-line")
pr = engine.plan("Make a tiny one-button game called Kite Line", proj, overrides=copy.deepcopy(Q))
pid = pr.get("production") or pr.get("id")
os.makedirs(os.path.join(proj, "art-direction", "references"), exist_ok=True)
png(os.path.join(proj, "art-direction", "references", "festival.png"), 120, 80, (230, 120, 40))
engine.decide(pid, approve=True)
st = engine.run(pid)
P = store.load(pid)
check("engine: the first thing that happens is the style shortlist (nothing is built)", P["tasks"]["design.styles"]["state"] == AWAITING_AGENT
      and P["tasks"]["build"]["state"] == PENDING, {k: P["tasks"][k]["state"] for k in ("design.styles", "build")})
wo = json.load(open(os.path.join(store.task_dir(P, "design.styles"), "work_order.json")))
check("hand-off: the styles work order lists the person's references and the atlas", wo["handoff"]["visual"]["references"][0]["file"] == "art-direction/references/festival.png"
      and wo["handoff"]["visual"]["atlas"].endswith("kit/atlas"), wo["handoff"].get("visual"))
od = store.task_dir(P, "design.styles")
for i, l in enumerate(ids6): png(os.path.join(od, "styles", l, "game.png"), 640, 360, cols[i])
json.dump(dict(S, references=[{"file": "art-direction/references/festival.png", "takes": "warm bunting orange", "leaves": "the poster layout and its photo"}]),
          open(os.path.join(od, "styles.json"), "w"))
st = engine.submit(pid, "design.styles", files=[os.path.join(od, "styles.json")], run_after=True)
P = store.load(pid)
sp = P["tasks"]["design.style_pick"]
check("style pick: waits for a person with the comparison page (never chosen silently)", sp["state"] == NEEDS_APPROVAL and os.path.isfile((sp.get("result") or {}).get("sheet") or ""), sp["state"])
page = open(sp["result"]["sheet"]).read()
check("style pick page: six looks, the recommendation marked with its reason, the 'surprise me' look named",
      page.count("<article") == 6 and "recommended" in page and "surprise me" in page and "bright silhouettes" in page)
try: engine.approve(pid, "design.style_pick", True, choice="blueprint"); bad_choice = False
except ValueError: bad_choice = True
check("style pick: a look that is not on the shortlist is refused", bad_choice)
st = engine.approve(pid, "design.style_pick", True, note="the bright one", choice="surprise")
st = engine.run(pid)
P = store.load(pid)
sel = P["tasks"]["design.style_pick"]["result"]["selection"]
check("style pick: 'surprise me' gets the wildcard, recorded as such", sel["styles"] == ["topographic"] and sel["how"] == "surprise me", sel)
check("design pick: the designs are the agent's next work order", P["tasks"]["design.designs"]["state"] == AWAITING_AGENT)
od = store.task_dir(P, "design.designs")
check("hand-off: the style selection sits beside the design work", os.path.isfile(os.path.join(od, "style_selection.json")))
Dd = {"product": "game", "style": "topographic", "recommended": "b", "reason": "the gauge makes wind the hero, as the game does", "designs": [design(i, "topographic") for i in range(3)]}
write_designs(od, Dd)
st = engine.submit(pid, "design.designs", files=[os.path.join(od, "designs.json")])
check("designs: accepted at submission", st["submission"]["accepted"], [c for c in st["submission"]["checks"] if not c["ok"]])
engine.run(pid)
P = store.load(pid)
dp = P["tasks"]["design.design_pick"]
check("design pick: waits for a person; the build has not started", dp["state"] == NEEDS_APPROVAL and P["tasks"]["build"]["state"] == PENDING and P["tasks"]["design.direction"]["state"] == PENDING,
      {k: P["tasks"][k]["state"] for k in ("design.design_pick", "design.direction", "build")})
dpage = open(dp["result"]["sheet"]).read()
check("design pick page: each design at phone and desktop size, with its play frame", dpage.count("class='design'") == 3 and dpage.count("Phone 390") == 3 and dpage.count("Play frame") == 3)
st = engine.approve(pid, "design.design_pick", True, note="I liked the bunting colours of A", choice="b")
st = engine.run(pid)
P = store.load(pid)
tdir = os.path.join(proj, "art-direction", "target")
tj = json.load(open(os.path.join(tdir, "target.json")))
check("design pick: the chosen frame is saved in the project as the target, with the style and what they liked in the others",
      all(os.path.isfile(os.path.join(tdir, f)) for f in ("phone.png", "desktop.png", "play.png")) and tj["design"] == "b" and tj["style"] == "topographic"
      and tj["liked_in_others"] == "I liked the bunting colours of A", tj)
check("design pick: the direction is next, written from the chosen design", P["tasks"]["design.direction"]["state"] == AWAITING_AGENT)
od = store.task_dir(P, "design.direction")
wo = json.load(open(os.path.join(od, "work_order.json")))
check("hand-off: the direction gets the design selection", any(os.path.basename(o["path"]) == "design_selection.json" for u in wo["handoff"]["upstream"] for o in u["outputs"]))
sys.path.insert(0, HERE)
import production_agent as agent
dj = json.load(open(agent.direction({"out_dir": od})[0]))
dj["art"].update(style={"look": "topographic", "name": "Topographic Map", "design": "b", "from": "picked"}, target="art-direction/target/phone.png",
                 references=[], accept_tells=[{"id": "default_type", "reason": "one condensed face for every label, as on a chart"}],
                 moments=[{"id": "title-reveal", "name": "Title reveal", "what": "the contour lines draw in before the title lands", "why": "it says map before it says game"},
                          {"id": "first-ribbon", "name": "First ribbon", "what": "the first ribbon unfurls and the gauge needle jumps", "why": "the first reward"}],
                 shots="art-direction/shots.json")
json.dump(dj, open(os.path.join(od, "direction.json"), "w"))
json.dump(SH, open(os.path.join(proj, "art-direction", "shots.json"), "w"))
st = engine.submit(pid, "design.direction", files=[os.path.join(od, "direction.json")])
sub = st["submission"]
check("direction gate: a reference image in the project that the direction does not account for is refused",
      not sub["accepted"] and any("covers every reference" in c["name"] and not c["ok"] for c in sub["checks"]), [c for c in sub["checks"] if not c["ok"]])
dj["art"]["references"] = [{"file": "art-direction/references/festival.png", "takes": "the bunting orange as the accent", "leaves": "its photo and its layout"}]
json.dump(dj, open(os.path.join(od, "direction.json"), "w"))
st = engine.submit(pid, "design.direction", files=[os.path.join(od, "direction.json")]); engine.run(pid)
check("direction gate: style, target, references, accepted tells, moments and a shot per moment: accepted", st["submission"]["accepted"],
      [c for c in st["submission"]["checks"] if not c["ok"]])
P = store.load(pid)
mt = [k for k in P["order"] if k.startswith("build.moment.")]
check("moments: each signature moment became its own work order, and the shot capture waits for them",
      sorted(mt) == ["build.moment.first-ribbon", "build.moment.title-reveal"] and set(mt) <= set(P["tasks"]["capture.shots"]["depends_on"]), mt)
check("the build is issued only now (after both picks and the direction)", P["tasks"]["build"]["state"] == AWAITING_AGENT)
shutil.copyfile(os.path.join(HERE, "fixtures", "visual", "game.html"), os.path.join(proj, "index.html"))
engine.submit(pid, "build", files=[os.path.join(proj, "index.html")]); engine.run(pid)
P = store.load(pid)
check("moments: their work orders are issued once the build exists", all(P["tasks"][k]["state"] == AWAITING_AGENT for k in mt), {k: P["tasks"][k]["state"] for k in mt})
for k in mt: engine.submit(pid, k, files=[os.path.join(proj, "index.html")])
P = store.load(pid)
if "build.wire" in P["tasks"] and P["tasks"]["build.wire"]["state"] == AWAITING_AGENT: engine.submit(pid, "build.wire", files=[os.path.join(proj, "index.html")])
st = engine.run(pid)
P = store.load(pid)
cs = P["tasks"]["capture.shots"]
rep = json.load(open(next(o["path"] for o in cs["outputs"] if o["role"] == "shots_report"))) if cs.get("outputs") else {}
reached = {(s["id"], c["viewport"]) for s in rep.get("shots") or [] for c in s["captures"] if c.get("reached")}
check("shot list: every shot reached in Chromium at phone and desktop, after real content appeared (not the loading title)",
      cs["state"] == PASSED and len(reached) == 12, (cs["state"], cs.get("error"), sorted(reached), [c.get("reason") for s in rep.get("shots", []) for c in s["captures"] if not c.get("reached")]))
check("review: the evidence pack is built and the review is the agent's work order", P["tasks"]["review.pack"]["state"] == PASSED and P["tasks"]["review.creative"]["state"] == AWAITING_AGENT,
      {k: (P["tasks"][k]["state"], P["tasks"][k].get("error")) for k in ("review.pack", "review.creative")})
pack = next(o["path"] for o in P["tasks"]["review.pack"]["outputs"] if o["role"] == "pack")
K = json.load(open(pack))
check("pack: the chosen frame, the style sample, the reference and every reached shot, each hashed", {"target:phone", "style:sample", "reference:art-direction/references/festival.png", "shot:title@phone"} <= {i["id"] for i in K["items"]}
      and all(len(i["sha256"]) == 64 for i in K["items"]), [i["id"] for i in K["items"]])
od = store.task_dir(P, "review.creative")
r0 = dict(copy.deepcopy(good), pack=pack); r0["coverage"]["viewed"] = ["shot:title@phone", "target:phone"]
json.dump(r0, open(os.path.join(od, "review.json"), "w"))
st = engine.submit(pid, "review.creative", files=[os.path.join(od, "review.json")], run_after=True)
P = store.load(pid)
check("review → work order: the gap became round 1's fix work order; QA waits for the visual rounds",
      P["tasks"].get("fix.visual.r1", {}).get("state") == AWAITING_AGENT and P["tasks"]["review.gaps"].get("superseded_by") == "review.gaps.r1"
      and P["tasks"]["qa.smoke"]["state"] == PENDING, {k: P["tasks"][k]["state"] for k in P["order"] if k.startswith(("fix.", "review.", "qa.smoke"))})
fwo = json.load(open(os.path.join(store.task_dir(P, "fix.visual.r1"), "work_order.json")))
check("fix work order: carries the gap, the shot and the fix", "the title face is the system font" in json.dumps(fwo["findings"]))
html_ = open(os.path.join(proj, "index.html")).read().replace("font:16px/1.4 ui-sans-serif", "font:16px/1.4 Outfit, ui-sans-serif")
open(os.path.join(proj, "index.html"), "w").write(html_)
st = engine.submit(pid, "fix.visual.r1", files=[os.path.join(proj, "index.html")], run_after=True)
P = store.load(pid)
check("round 1: a fresh capture and a fresh review after the fix", P["tasks"]["capture.shots.r1"]["state"] == PASSED and P["tasks"]["review.creative.r1"]["state"] == AWAITING_AGENT,
      {k: (P["tasks"][k]["state"], P["tasks"][k].get("error")) for k in ("capture.shots.r1", "review.pack.r1", "review.creative.r1")})
pack1 = next(o["path"] for o in P["tasks"]["review.pack.r1"]["outputs"] if o["role"] == "pack")
od = store.task_dir(P, "review.creative.r1")
r1 = dict(copy.deepcopy(good), pack=pack1, gaps=[], summary="an assessment after round 1: the title now carries the chosen face")
json.dump(r1, open(os.path.join(od, "review.json"), "w"))
st = engine.submit(pid, "review.creative.r1", files=[os.path.join(od, "review.json")], run_after=True)
P = store.load(pid)
check("no gap left: the chain ends without another round, and QA runs", P["tasks"]["review.gaps.r1"]["state"] == PASSED and "fix.visual.r2" not in P["tasks"]
      and P["tasks"]["qa.smoke"]["state"] not in (PENDING,), {k: P["tasks"][k]["state"] for k in ("review.gaps.r1", "qa.smoke")})
lk = P["tasks"]["release.look"]
look_html = next((o["path"] for o in lk.get("outputs") or [] if o["role"] == "look_page"), None)
check("look page: the chosen frame beside the shipped shots, made after the release", lk["state"] == PASSED and look_html and "Chosen frame" in open(look_html).read()
      and "Shipped" in open(look_html).read(), (lk["state"], lk.get("error"), lk.get("blocked_by")))
md = open(os.path.join(P["store"], "REPORT.md")).read() if os.path.isfile(os.path.join(P["store"], "REPORT.md")) else report.markdown(P)
sec = md[md.find("## Visual direction"):]; sec = sec[:sec.find("\n## ", 5)]
check("report: the visual direction section links the picks and the look page", "## Visual direction (advisory)" in md and look_html in sec
      and "1 fix round(s)" in sec and "style-pick/index.html" in sec, sec[-500:])
crit = {c["id"] for c in P["spec"].get("acceptance") or []}
check("verdict untouched: no visual task carries a criterion, and no criterion names one", not any(P["tasks"][k].get("criterion") for k in P["order"]
      if k.startswith(("design.style", "design.design", "design.moments", "capture.", "review.", "fix.visual", "release.shots", "release.look", "build.moment"))))

# the last round lists what remains, with the screenshots, and adds nothing
from production import builtins
rd = os.path.join(ws, "lastround"); os.makedirs(rd)
img = png(os.path.join(rd, "t.png"), 40, 80, (10, 10, 10))
K2 = {"items": [{"id": "shot:title@phone", "kind": "screenshot", "path": img, "sha256": visual.sha(img)}], "not_seen": []}
json.dump(K2, open(os.path.join(rd, "pack.json"), "w")); json.dump(good, open(os.path.join(rd, "review.json"), "w"))
r = builtins.visual_gaps({"upstream": [{"outputs": [{"path": os.path.join(rd, "review.json"), "role": "review"}]}], "params": {"round": visual.ROUNDS}, "out_dir": rd,
                          "spec": {"title": "Kite Line"}, "task": {"id": "review.gaps.r2"}})
check(f"after {visual.ROUNDS} rounds: no new work order; the gap is listed for the person with its screenshot",
      "expand" not in r and r["remaining"] and any(o["role"] == "remaining_page" for o in r["outputs"]) and os.path.isfile(os.path.join(rd, "remaining", "shot_title@phone.png")), r)

# an unreachable shot is NOT SEEN, never captured as evidence
from importlib import import_module
sys.path.insert(0, os.path.join(REPO, "studio"))
from core import shots as SHOTS
res = SHOTS.capture({"root": proj, "entry": "index.html"}, [{"id": "secret", "name": "A screen that does not exist", "kind": "screen", "steps": [],
                                                             "wait_for": {"selector": "#no-such-screen", "timeout_ms": 1200}}], [{"name": "desktop", "width": 800, "height": 600}], os.path.join(ws, "unseen"))
c = res[0]["captures"][0]
check("shot runner: a shot whose content never appears is NOT SEEN with the reason, and only a diagnostic image is kept",
      not c["reached"] and "no-such-screen" in (c.get("reason") or "") and not c.get("image") and os.path.isfile(c.get("diagnostic") or ""), c)

print(f"\n{'OK' if not fails else 'FAILED'}: test_visual ({fails} failure(s))")
sys.exit(1 if fails else 0)
