#!/usr/bin/env python3
"""Idea-to-Delivery lifecycle, App Icon Studio, HaveAnApp attribution and engineering standards (production/).

    python3 tests/test_lifecycle.py            (~1-2 min; the app production at the end needs the Studio runtime)

Covers: idea intake and briefs; standalone Recon (evidence rules, budget, promotion) and Recon in a New Build;
read-only Discovery; the Decision Room (answers re-plan, approval boundary, essential questions); the approved
blueprint; material vs non-material revisions (pause, approve, preserved work); legacy productions; the PNG/ICO
codec, icon inspection, concept and master validation, derivatives and verification; attribution and the
proportionate standards; and a real app production that goes concepts → a person's choice → master → icon set →
build with attribution → qa.icons / qa.attribution / qa.standards → release."""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-lifecycle-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import engine, store, intake, lifecycle, recon, icons, standards, executors, report
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


def art(path, size, fg, bg, shape="disc", alpha_bg=False):
    """A real test icon drawn in pure Python: a shape on a tile."""
    px = bytearray(size * size * 4); c = size / 2
    for y in range(size):
        for x in range(size):
            dx, dy = x - c, y - c
            inside = (dx * dx + dy * dy < (size * 0.3) ** 2) if shape == "disc" else (abs(dx) < size * 0.28 and abs(dy) < size * 0.16)
            col = fg if inside else bg
            i = (y * size + x) * 4; px[i:i + 3] = bytes(col); px[i + 3] = 0 if (alpha_bg and not inside) else 255
    return icons.encode(path, size, size, px)


# ---------------------------------------------------------------- briefs and the profile
b = lifecycle.brief("A habit tracker for me and my partner. It must work offline. No accounts. Should show streaks so that we keep going.")
check("brief: objective, requirements, constraints and outcome are the person's own sentences", b["objective"].startswith("A habit tracker")
      and any("offline" in r for r in b["requirements"]) and any("No accounts" in c for c in b["constraints"]) and "so that" in (b["outcome"] or ""), b)
check("brief: a GitHub URL is recognised as a repository", lifecycle.brief("Improve https://github.com/acme/widget for phones")["repository"] == "acme/widget")
check("brief: a one-liner is a sentence; a long paste is a master prompt", lifecycle.brief("A tiny timer app.")["kind"] == "sentence"
      and lifecycle.brief("Build it. " * 200)["kind"] == "master prompt")
check("profile: personal / public / sensitive from what the idea says", standards.profile_for("a recipe app for my family", "app")[0] == "personal"
      and standards.profile_for("a marketplace with user accounts and sign in", "app")[0] == "public"
      and standards.profile_for("a clinic app that stores patient health records and payments", "app")[0] == "sensitive"
      and standards.profile_for("a portfolio website", "site")[0] == "public")
sp = intake.parse("Build a mobile-first habit tracker web app for my family")
check("intake: web apps require an icon and the attribution, with criteria for both and the standard",
      sp["icon"]["required"] and sp["attribution"]["required"] and {"app_icon", "attribution", "engineering_standards"} <= {c["id"] for c in sp["acceptance"]})
pk = intake.parse("Make a sound pack with jump and coin sound effects", overrides={"deliverable": "asset_pack"})
check("intake: an asset pack carries no icon/attribution requirement", not pk["icon"]["required"] and not pk["attribution"]["required"]
      and not {"app_icon", "attribution"} & {c["id"] for c in pk["acceptance"]})

# ---------------------------------------------------------------- standalone Recon
idea = engine.idea("A cosy browser game about tending a lighthouse garden at night")
check("idea: saved at stage idea with no plan, nothing read", lifecycle.stage(store.load(idea["id"])) == "idea" and not idea["tasks"] and "discovery" not in idea)
check("idea: building an idea is refused (nothing approved)", engine.run(idea["id"]).get("refused"))
ro = engine.start_recon(idea["id"], "quick")
check("recon: a quick order carries its budget (cannot become an endless loop)", ro["stage"] == "recon" and ro["recon_order"]["budget"]["searches"] == 6)
check("recon: an unknown depth is refused", raises(lambda: engine.start_recon(idea["id"], "forever"), ValueError))
bad = {"reality_check": [{"claim": "It is feasible in a browser", "basis": "inference"}],
       "competition_radar": [{"name": "Garden Glow", "what": "a night garden game", "basis": "source"}],
       "identity_check": [{"claim": "lighthousegarden.com is available", "basis": "assumption"}],
       "zag": [{"claim": "one-thumb play", "basis": "inference"}], "recommendation": {"verdict": "build", "reasoning": "short"}}
r = engine.submit_recon(idea["id"], bad)
names = " ".join(c["name"] for c in r["checks"]) if isinstance(r["checks"], list) else ""
check("recon: invented evidence is refused (a 'source' competitor with no URL, a domain 'available' without a lookup, no uncertainties)",
      not r["recon_accepted"] and "cites the URL" in names and "verified lookup" in names and "uncertainties" in names, r["checks"])
good = {"reality_check": [{"claim": "Feasible as a canvas game", "basis": "inference"}, {"claim": "Cosy games are a growing niche", "basis": "source", "evidence": ["https://example.org/cosy-report"]}],
        "competition_radar": [{"name": "Garden Glow", "what": "a night garden game", "url": "https://example.org/garden-glow", "basis": "source"}],
        "identity_check": [{"claim": "the domain lighthousegarden.com: unverified", "basis": "assumption"}],
        "zag": [{"claim": "one-thumb play, five-minute sessions", "basis": "inference"}],
        "recommendation": {"verdict": "build", "reasoning": "small, original, fits a browser; no direct competitor found in the budget", "uncertainties": ["name not trademark-checked"]},
        "searches_used": 4}
r = engine.submit_recon(idea["id"], good)
pr = store.load(idea["id"])
check("recon: evidence-bound findings are saved with RECON.md, and the idea is back at stage idea", r["recon_accepted"] and pr["recon"]["recommendation"]["verdict"] == "build"
      and os.path.isfile(pr["recon"]["report"]) and lifecycle.stage(pr) == "idea" and "[source](https://example.org/garden-glow)" in open(pr["recon"]["report"]).read())
check("recon: over-budget findings are refused", not all(c["ok"] for c in recon.validate(dict(good, searches_used=9), "quick")))
pk2 = engine.idea("A pixel-art weather widget for my desk")
engine.discard(pk2["id"], park=True, reason="later")
check("idea: parked ideas can be revisited", lifecycle.stage(store.load(pk2["id"])) == "parked")
dd = engine.idea("A throwaway idea that goes nowhere at all"); engine.discard(dd["id"])
check("idea: discarded ideas are kept for the record, and cannot be promoted", lifecycle.stage(store.load(dd["id"])) == "discarded"
      and raises(lambda: engine.promote(dd["id"]), ValueError))

# ---------------------------------------------------------------- read-only Discovery and the Decision Room
existing = os.path.join(ws, "existing-app"); os.makedirs(os.path.join(existing, "public"))
open(os.path.join(existing, "index.html"), "w").write("<!doctype html><html><head><link rel=icon href=/vite.svg></head><body><div id=app></div></body></html>")
open(os.path.join(existing, "public", "vite.svg"), "w").write("<svg xmlns='http://www.w3.org/2000/svg'/>")
open(os.path.join(existing, "package.json"), "w").write(json.dumps({"name": "x", "dependencies": {"react": "18.3.1"}}))
fp0 = engine.fingerprint(existing)
promoted = engine.promote(idea["id"])
check("promote: the researched idea goes through Discovery to the Decision Room (recon carried into the spec)", lifecycle.stage(promoted) == "decisions"
      and promoted["spec"].get("recon", {}).get("verdict") == "build" and os.path.isfile(promoted["discovery_report"]))
check("discovery: a new project's folder is not created by Discovery", not os.path.exists(promoted["spec"]["project"]["path"]))
rep = open(promoted["discovery_report"]).read()
check("discovery report: the eight sections", all(f"## {i}." in rep for i in range(1, 9)) and "Recon (quick)" in rep)
ex = engine.plan("Improve this existing app for phones and release it", existing)
check("discovery: read-only on an existing project (every file byte-identical after planning)", engine.fingerprint(existing) == fp0)
room = {d["id"]: d for d in ex["decision_room"]}
check("decision room: material decisions only, each with a recommendation, options and trade-offs",
      {"scope", "architecture", "design", "app_icon", "engineering", "cost", "attribution"} <= set(room) and all(d["recommended"] is not None and d["options"] for d in room.values()), sorted(room))
check("decision room: existing code is reused (architecture recommends the detected engine)", room["architecture"]["recommended"] == "react")
check("decision room: an existing app's icon is inspected (a framework default is reported) but never replaced unless asked",
      ex["icon_state"]["status"] == "generic" and room["app_icon"]["recommended"] == "leave" and "new" in [o["value"] for o in room["app_icon"]["options"]])
check("approval boundary: Discovery approval is not build approval (run refused before the blueprint is approved)", "not approved" in str(engine.run(ex["id"]).get("refused")))
check("decision room: an answer that is not an option is refused", raises(lambda: engine.decide(ex["id"], {"engineering": "enterprise"}), ValueError))
v = engine.decide(ex["id"], {"engineering": "sensitive"})
pr = store.load(ex["id"])
check("decision room: an answer re-plans (sensitive standard in the spec and the standards task)", pr["spec"]["engineering"]["profile"] == "sensitive"
      and pr["tasks"]["qa.standards"]["params"]["profile"] == "sensitive" and v["stage"] == "decisions")
v = engine.decide(ex["id"], {"attribution": "leave"})
pr = store.load(ex["id"])
check("decision room: an existing app may leave the attribution out (no criterion, no check)", "qa.attribution" not in pr["tasks"] and "attribution" not in {c["id"] for c in pr["spec"]["acceptance"]})
check("decision room: answers survive the re-plan", {d["id"]: d["answer"] for d in pr["decision_room"]}.get("engineering") == "sensitive")
v = engine.decide(ex["id"], approve=True, note="go")
pr = store.load(ex["id"])
check("approval: the blueprint is frozen with every decision's answer (defaults filled from the recommendation)", v["stage"] == "approved"
      and pr["blueprint"]["status"] == "approved" and all(d["answer"] is not None for d in pr["blueprint"]["decisions"]) and pr["blueprint"]["hash"])
check("approval: the build is authorised now", engine._build_authorised(pr) is None)
check("approval: a settled decision is not reopened from the Decision Room", raises(lambda: engine.decide(ex["id"], {"engineering": "public"}), ValueError))

# ---------------------------------------------------------------- deviations
v = engine.revise(ex["id"], {"quality": {"max_rounds": 3}}, "one more fix round")
check("revision: a quality-only change is not material (applied, no new approval)", not v.get("material") and store.load(ex["id"])["spec"]["quality"]["max_rounds"] == 3
      and engine._build_authorised(store.load(ex["id"])) is None)
pr = store.load(ex["id"])   # pretend the scaffold already ran: finished work must survive an approved revision
pr["tasks"]["foundation.scaffold"].update(state="passed", attempts=[{"n": 1, "status": "ok"}]); store.save(pr)
v = engine.revise(ex["id"], {"features": {"deploy": True}}, "the person now wants it deployed")
pr = store.load(ex["id"])
check("revision: a scope change is material: the build pauses until a person approves", v["material"] and v["stage"] == "revision"
      and "waiting for a person" in str(engine._build_authorised(pr)))
v = engine.decide(ex["id"], approve=True)
pr = store.load(ex["id"])
check("revision: approving applies it (deploy task planned), keeps finished work, bumps the blueprint", "release.deploy" in pr["tasks"]
      and pr["tasks"]["foundation.scaffold"]["state"] == "passed" and pr["blueprint"]["version"] == 2 and engine._build_authorised(pr) is None,
      ("release.deploy" in pr["tasks"], pr["tasks"]["foundation.scaffold"]["state"], pr["blueprint"].get("version"), engine._build_authorised(pr)))
engine.revise(ex["id"], {"features": {"deploy": False}}, "changed mind again"); engine.decide(ex["id"], approve=False, note="keep the deploy")
check("revision: a declined revision changes nothing", "release.deploy" in store.load(ex["id"])["tasks"] and engine._build_authorised(store.load(ex["id"])) is None)
legacy = {"id": store.new_id("legacy"), "spec": {"title": "legacy", "authorisations": {}}, "tasks": {}, "order": []}
store.create(legacy)
check("compatibility: a production made before the lifecycle is not blocked by the new gate", engine._build_authorised(store.load(legacy["id"])) is None)
nb = engine.plan("Build a tiny arcade game called Comet Hop", os.path.join(ws, "comet"), recon="quick")
check("new build with recon: stops at Recon first", nb["stage"] == "recon" and nb.get("recon_order"))
pp = engine.promote(nb["production"])
check("new build: Recon is optional (promoting without findings is allowed and recorded)", lifecycle.stage(pp) == "decisions" and pp["lifecycle"].get("recon_skipped"))

# ---------------------------------------------------------------- the icon codec and checks
d = os.path.join(ws, "icons"); os.makedirs(d)
m = art(os.path.join(d, "m.png"), 1024, (242, 165, 65), (20, 18, 43))
w, h, px = icons.decode(m)
check("png: encode → decode round trip", (w, h) == (1024, 1024) and px[3] == 255 and tuple(px[(512 * 1024 + 512) * 4:][:3]) == (242, 165, 65))
check("png: area-average downscale keeps the colours", tuple(icons.resize(w, h, px, 4, 4)[0:3]) == (20, 18, 43))
dr = icons.derivatives(m, os.path.join(d, "set"), background="#14122B", name="Test App", prefix="assets/icons/")
files = {os.path.basename(o["path"]): o for o in dr["outputs"]}
check("derivatives: master, 512, 192, maskable 512, Apple 180, favicons 32/16 and .ico", dr["status"] == "ok" and {"icon-1024.png", "icon-512.png", "icon-192.png",
      "icon-maskable-512.png", "apple-touch-icon.png", "favicon-32.png", "favicon-16.png", "favicon.ico"} <= set(files), dr.get("checks"))
check("derivatives: exact sizes", all(icons.header(files[f]["path"])[:2] == (s, s) for f, s in (("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180), ("favicon-16.png", 16))))
tm = art(os.path.join(d, "t.png"), 1024, (200, 40, 40), (0, 0, 0), alpha_bg=True)
dt = icons.derivatives(tm, os.path.join(d, "tset"), background="#ffffff")
af = next(o["path"] for o in dt["outputs"] if o["path"].endswith("apple-touch-icon.png"))
check("derivatives: a transparent master gets an opaque Apple touch icon (on the palette background)", icons.opaque(icons.decode(af)[2]))
flat = icons.encode(os.path.join(d, "flat.png"), 1024, 1024, bytearray(b"\x80\x80\x80\xff") * (1024 * 1024))
fd = icons.derivatives(flat, os.path.join(d, "fset"))
check("derivatives: an icon with no visible shape at 32 px fails small-size clarity (measured)", fd["status"] == "failed" and any("clarity" in c["name"] and not c["ok"] for c in fd["checks"]))
check("derivatives: a master that is not 1024 is refused", icons.derivatives(art(os.path.join(d, "s.png"), 512, (1, 2, 3), (9, 9, 9)), os.path.join(d, "x"))["failure"] == "request")
cd = os.path.join(d, "concepts"); os.makedirs(cd)
art(os.path.join(cd, "a.png"), 1024, (242, 165, 65), (20, 18, 43)); art(os.path.join(cd, "b.png"), 1024, (63, 193, 201), (20, 18, 43), shape="bar")
json.dump({"concepts": [{"id": "a", "file": "a.png", "idea": "a glowing lantern disc"}, {"id": "b", "file": "b.png", "idea": "a drifting bar of light"}], "recommended": "a"},
          open(os.path.join(cd, "concepts.json"), "w"))
check("concepts: a valid set passes", all(c["ok"] for c in icons.validate_concepts(os.path.join(cd, "concepts.json"), cd)))
json.dump({"concepts": [{"id": "a", "file": "a.png", "idea": "only one idea here"}], "recommended": "z"}, open(os.path.join(cd, "one.json"), "w"))
check("concepts: one concept, or a recommendation that is not a concept, is refused", not all(c["ok"] for c in icons.validate_concepts(os.path.join(cd, "one.json"), cd)))
check("master: must be exactly 1024", not all(c["ok"] for c in icons.validate_master(os.path.join(d, "s.png"))) and all(c["ok"] for c in icons.validate_master(m)))
sheet = icons.comparison_sheet(json.load(open(os.path.join(cd, "concepts.json")))["concepts"], cd, os.path.join(d, "sheet", "concepts.html"), "Test", "a")
check("comparison sheet: every concept side by side at several sizes, the recommendation marked", open(sheet).read().count("<article>") == 2 and "Recommended" in open(sheet).read())

site = os.path.join(ws, "site"); os.makedirs(os.path.join(site, "assets", "icons"))
for o in dr["outputs"]:
    if o["role"] in ("icon", "favicon", "icon_master"): shutil.copy(o["path"], os.path.join(site, "assets", "icons"))
man = dict(dr["snippet"]["manifest"], description="Test App by HaveAnApp")
json.dump(man, open(os.path.join(site, "manifest.webmanifest"), "w"))
open(os.path.join(site, "index.html"), "w").write(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Test App</title>{dr['snippet']['head']}<meta name="author" content="HaveAnApp"></head><body><main>Hi</main>
<footer><p class="haveanapp-byline" data-haveanapp>Test App <a href="https://haveanapp.com">by HaveAnApp</a></p></footer>
<script>addEventListener('error', e => document.body.dataset.err = 1)</script></body></html>""")
vr = icons.verify(site)
check("verify: the wired icon set passes (favicon, Apple 180 opaque, manifest 192/512, maskable)", vr["status"] == "ok", [c for c in vr["checks"] if not c["ok"]])
os.remove(os.path.join(site, "assets", "icons", "icon-192.png"))
check("verify: a broken icon reference fails", any("192" in c["name"] and not c["ok"] for c in icons.verify(site)["checks"]))
check("inspect: a project with a 1024 icon is a candidate to keep", icons.inspect(site)["status"] == "candidate")
check("inspect: a framework default icon is generic", icons.inspect(existing)["status"] == "generic")
gen = icons.verify(existing, require_manifest=False)
check("verify: a framework default favicon fails", gen["status"] == "failed" and any("default icon" in c["name"] and not c["ok"] for c in gen["checks"]), gen["checks"])

# ---------------------------------------------------------------- attribution and the standards
ar = standards.attribution(site)
check("attribution: the visible, marked byline passes", ar["status"] == "ok", ar["checks"])
check("attribution: the official site is https://haveanapp.com (owner-confirmed)", standards.attribution_config()["url"] == "https://haveanapp.com"
      and standards.attribution_config()["url_verified"])
ig = os.path.join(ws, "ig"); os.makedirs(ig); open(os.path.join(ig, "index.html"), "w").write('<footer><p data-haveanapp>by <a href="https://www.instagram.com/haveanapphq">HaveAnApp</a></p></footer>')
check("attribution: a byline linked to HaveAnAppHQ (Instagram) instead of the site fails", standards.attribution(ig)["status"] == "failed")
nl = os.path.join(ws, "nl"); os.makedirs(nl); open(os.path.join(nl, "index.html"), "w").write('<footer><p data-haveanapp>by HaveAnApp</p></footer>')
check("attribution: an unlinked byline fails now that the site is confirmed", standards.attribution(nl)["status"] == "failed")
open(os.path.join(existing, "about.html"), "w").write("<html><head><meta name=author content=HaveAnApp><title>by HaveAnApp</title></head><body>About</body></html>")
check("attribution: metadata alone is not attribution", standards.attribution(existing)["status"] == "failed")
hid = os.path.join(ws, "hid"); os.makedirs(hid); open(os.path.join(hid, "index.html"), "w").write('<footer><p data-haveanapp hidden>by HaveAnApp</p></footer>')
check("attribution: a hidden byline fails", standards.attribution(hid)["status"] == "failed")
lk = os.path.join(ws, "lk"); os.makedirs(lk); open(os.path.join(lk, "index.html"), "w").write('<footer><a data-haveanapp href="https://haveanapp.example">by HaveAnApp</a></footer>')
check("attribution: a link to an unverified HaveAnApp URL fails", standards.attribution(lk)["status"] == "failed")
rx = os.path.join(ws, "rx"); os.makedirs(os.path.join(rx, "src"))
open(os.path.join(rx, "src", "Footer.tsx"), "w").write('export const F = () => <p className="haveanapp-byline" data-haveanapp="">{name} <a href={COMPANY_URL}>by HaveAnApp</a></p>;')
check("attribution: works in React components", standards.attribution(rx)["status"] == "ok")
st = standards.check(site, "personal")
check("standards: a small static app passes the personal standard (server checks n/a)", st["status"] == "ok" and any(c["status"] == "n/a" for c in st["checks"]), [c for c in st["checks"] if not c["ok"]])
api = os.path.join(ws, "api"); os.makedirs(os.path.join(api, "api"))
open(os.path.join(api, "index.html"), "w").write('<!doctype html><html lang=en><head><meta name=viewport content=x><title>A</title></head><body></body></html>')
open(os.path.join(api, "api", "login.js"), "w").write("const express=require('express');const app=express();app.use(require('cors')());\n"
                                                    "app.post('/login',(q,s)=>db.query(`SELECT * FROM users WHERE name='${q.body.name}'`));\nconst k='sk_live_" + "a" * 24 + "';")
open(os.path.join(api, "package.json"), "w").write(json.dumps({"dependencies": {"express": "latest", "cors": "2.8.5"}}))
sa = standards.check(api, "sensitive")
bad_ids = {c["id"] for c in sa["checks"] if not c["ok"]}
check("standards: the sensitive standard catches secrets, open CORS, SQL interpolation, no lockfile, 'latest' deps",
      sa["status"] == "failed" and {"secrets", "cors", "sql_injection", "lockfile", "dep_ranges"} <= bad_ids, bad_ids)
check("standards: what cannot be decided from files is a review item, never a pass", any("rate limit" in r for r in sa["review"]) and any("validated" in r for r in sa["review"]))
sp_ = standards.check(api, "personal")
check("standards: proportionate (the personal standard does not demand a lockfile or rate limits)", "lockfile" not in {c["id"] for c in sp_["checks"] if not c["ok"]} and not sp_["review"])

# ---------------------------------------------------------------- a real app production: the icon is chosen by a person, then built, wired and verified
if executors.studio_python():
    proj = os.path.join(ws, "tidepool")
    pr = engine.plan("Build a mobile-first tide timetable web app called Tidepool for my family, with an original visual identity", proj,
                     {"quality": {"pixelcraft": False}})   # PIXELCRAFT is covered by acceptance_production.py; TestCraft smoke runs here
    room = {d["id"] for d in pr["decision_room"]}
    check("app: planned with the App Icon Studio chain and the three standards checks", {"icon.concepts", "icon.select", "icon.master", "icon.derivatives", "qa.icons",
          "qa.attribution", "qa.standards"} <= set(pr["tasks"]) and "app_icon" in room, sorted(pr["tasks"]))
    engine.decide(pr["id"], approve=True)
    st = engine.run(pr["id"])
    check("app: the run stops at the identity work order (the blueprint approved)", "foundation.identity" in [t["id"] for t in st["tasks"] if t["state"] == "awaiting_agent"], st.get("refused") or st["counts"])
    order = json.load(open(os.path.join(pr["store"], "tasks", "foundation.identity", "work_order.json")))
    check("work orders carry the settled blueprint", order.get("blueprint", {}).get("decisions") and "settled" in order["blueprint"]["rule"])
    od = order["out_dir"]; json.dump({"background": "#0E2A3B", "primary": "#4FB3BF", "accent": "#F4D35E", "text": "#F7F7F2"}, open(os.path.join(od, "palette.json"), "w"))
    open(os.path.join(od, "logo.svg"), "w").write('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><rect width="200" height="60" fill="#0E2A3B"/></svg>')
    st = engine.submit(pr["id"], "foundation.identity", [os.path.join(od, f) for f in ("palette.json", "logo.svg")], "identity", run_after=True)
    co = json.load(open(os.path.join(pr["store"], "tasks", "icon.concepts", "work_order.json")))["out_dir"]
    art(os.path.join(co, "wave.png"), 1024, (79, 179, 191), (14, 42, 59)); art(os.path.join(co, "moon.png"), 1024, (244, 211, 94), (14, 42, 59), shape="bar")
    json.dump({"concepts": [{"id": "wave", "file": "wave.png", "idea": "a rising tide disc"}, {"id": "moon", "file": "moon.png", "idea": "a moonlit bar of water"}],
               "recommended": "wave"}, open(os.path.join(co, "concepts.json"), "w"))
    st = engine.submit(pr["id"], "icon.concepts", [os.path.join(co, "concepts.json")], "two concepts", run_after=True)
    t = store.load(pr["id"])["tasks"]["icon.select"]
    check("icon: the choice waits for a person, with a comparison sheet (never silently selected)", t["state"] == "needs_approval" and os.path.isfile(t["result"]["sheet"]), t["state"])
    check("icon: a choice that is not a concept is refused", raises(lambda: engine.approve(pr["id"], "icon.select", choice="sun"), ValueError))
    engine.approve(pr["id"], "icon.select", approved=False, note="warmer colours please")
    pr2 = store.load(pr["id"])
    check("icon: declining asks for new concepts with the feedback", pr2["tasks"]["icon.concepts"]["state"] == "pending"
          and "warmer colours please" in pr2["tasks"]["icon.concepts"]["work_order"]["feedback"])
    engine.run(pr["id"])
    engine.submit(pr["id"], "icon.concepts", [os.path.join(co, "concepts.json")], "revised", run_after=True)
    engine.approve(pr["id"], "icon.select", choice="moon", note="the moon one")
    st = engine.run(pr["id"])
    sel = store.load(pr["id"])["tasks"]["icon.select"]
    check("icon: the person's choice is recorded (selection.json)", sel["state"] == "passed" and sel["result"]["selection"]["choice"] == "moon")
    mo = json.load(open(os.path.join(pr["store"], "tasks", "icon.master", "work_order.json")))["out_dir"]
    art(os.path.join(mo, "icon-1024.png"), 1024, (244, 211, 94), (14, 42, 59), shape="bar")
    st = engine.submit(pr["id"], "icon.master", [os.path.join(mo, "icon-1024.png")], "master", run_after=True)
    prx = store.load(pr["id"])
    check("icon: derivatives made from the approved master and integrated into the project", prx["tasks"]["icon.derivatives"]["state"] == "passed"
          and os.path.isfile(os.path.join(proj, "assets", "icons", "apple-touch-icon.png")),
          {k: (prx["tasks"][k]["state"], prx["tasks"][k].get("reason") or prx["tasks"][k].get("error"), (prx["tasks"][k].get("result") or {}).get("checks"))
           for k in ("icon.master", "icon.derivatives", "integrate.assets")})
    bo = json.load(open(os.path.join(pr["store"], "tasks", "build", "work_order.json")))
    check("build work order: asks for the attribution, the icon set and the proportionate standard",
          any("HaveAnApp" in i for i in bo["instructions"]) and any("icons.snippet.json" in i for i in bo["instructions"]) and any("personal" in i for i in bo["instructions"]))
    snip = json.load(open(next(o["path"] for o in prx["tasks"]["icon.derivatives"]["outputs"] if o["role"] == "icon_snippet")))
    integrated = [m["dest_rel"] for m in prx["tasks"]["integrate.assets"]["result"]["integrated"]]
    json.dump(dict(snip["manifest"], description="Tidepool by HaveAnApp"), open(os.path.join(proj, "manifest.webmanifest"), "w"))
    page = lambda byline: f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tidepool</title>
{snip['head']}<meta name="author" content="HaveAnApp"><link rel="stylesheet" href="assets/brand/logo.svg"></head><body><img src="assets/brand/logo.svg" alt="Tidepool">
<main><h1>Tidepool</h1><p>High tide 06:12</p></main>{byline}<script>addEventListener('error', () => document.body.classList.add('err'))</script>
<!-- {' '.join(os.path.basename(i) for i in integrated)} --></body></html>"""
    open(os.path.join(proj, "index.html"), "w").write(page(""))
    check("starter: the new app started from the static-app starter (standards wired in)", os.path.isfile(os.path.join(proj, "app.js")) and os.path.isfile(os.path.join(proj, "tests", "gitcraft.features.json")))
    json.dump({"features": [{"name": "shows the next high tide", "requirement": "a tide timetable", "steps": [{"expect": "main p", "text": "High tide"}]}]},
              open(os.path.join(proj, "tests", "gitcraft.features.json"), "w"))
    st = engine.submit(pr["id"], "build", [os.path.join(proj, "index.html"), os.path.join(proj, "manifest.webmanifest"), os.path.join(proj, "tests", "gitcraft.features.json")],
                       "build without the byline", run_after=True)
    prx = store.load(pr["id"])
    check("qa.attribution: a build without the byline fails and becomes a fix work order", prx["tasks"]["qa.attribution"]["state"] == "failed"
          and "fix.qa.attribution.r1" in prx["tasks"], {k: (v["state"], v.get("error") or v.get("reason")) for k, v in prx["tasks"].items() if v["state"] != "passed"})
    check("qa.icons: the approved, wired icon set passes", engine.eff(prx, "qa.icons")["state"] == "passed", engine.eff(prx, "qa.icons").get("error"))
    check("qa.standards: the personal standard passes", engine.eff(prx, "qa.standards")["state"] == "passed", engine.eff(prx, "qa.standards").get("error"))
    open(os.path.join(proj, "index.html"), "w").write(page('<footer><p class="haveanapp-byline" data-haveanapp>Tidepool <a href="https://haveanapp.com">by HaveAnApp</a></p></footer>'))
    st = engine.submit(pr["id"], "fix.qa.attribution.r1", [os.path.join(proj, "index.html")], "added the byline", run_after=True)
    prx = store.load(pr["id"])
    acc = {a["id"]: a["status"] for a in report.acceptance(prx)}
    check("app: after the fix, the attribution re-verification passes", engine.eff(prx, "qa.attribution")["state"] == "passed", engine.eff(prx, "qa.attribution").get("error"))
    check("app: app_icon, attribution, engineering_standards and features_work criteria passed with evidence",
          all(acc.get(k) == "passed" for k in ("app_icon", "attribution", "engineering_standards", "features_work")), acc)
    check("app: the lifecycle reads delivered once the release passed", st["status"] == "passed" and st["stage"] == "delivered",
          (st["status"], st.get("stage"), {t["id"]: (t["state"], (t.get("reason") or t.get("error") or "")[:300]) for t in st["tasks"] if t["state"] not in ("passed", "skipped")}))
else:
    print("SKIP the app production: the Studio runtime is not installed (scripts/install-studio.sh)")

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
