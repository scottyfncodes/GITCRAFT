#!/usr/bin/env python3
"""Deploy + live verification, feature checks, backend, starters, GitHub issues, native icons, HaveAnApp Pulse.

    python3 tests/test_gaps.py        (~2 min; the browser checks need the Studio runtime / Playwright)

  starters      a new app/game/React app gets its starter (standards wired in); never into a non-empty folder
  decisions     deployment target (existing pipeline preferred), backend (accounts → Postgres), analytics (Pulse for public),
                native icons; approving the recommendations applies them to the plan
  backend       provisioning needs a person's approval ("infrastructure"); a record holding a secret is refused
  features      tests/gitcraft.features.json is required for new apps; qa.features runs it in Chromium (pass and fail)
  native icons  iOS asset catalog (1024, opaque) + Android mipmaps/adaptive icon, integrated keeping their folders
  issues        open GitHub issues become defects/requests in the Discovery inventory
  verify-live   a local server with this build passes; changed bytes and a login wall fail; a real login-walled Vercel URL fails"""
import functools, http.server, json, os, shutil, subprocess, sys, tempfile, threading
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-gaps-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import engine, store, intake, icons, standards, builtins, executors, entry, live, planner
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def raises(fn, exc=Exception):
    try: fn()
    except exc as e: return str(e) or True
    return False


def ctx(proj, params, upstream=(), out=None):
    out = out or tempfile.mkdtemp(dir=ws)
    return {"prod": {"id": "t"}, "task": {}, "project": proj, "params": params, "out_dir": out, "upstream": list(upstream), "auth": {}, "approved": False,
            "inside_roots": lambda p: True, "previous_manifest": None, "spec": {"title": "T", "project": {"asset_dir": "assets"}}}


# ---------------------------------------------------------------- starters
for name in ("static-app", "canvas-game", "vite-react"):
    d = os.path.join(ws, f"s-{name}")
    r = builtins.scaffold(ctx(d, {"dirs": [], "starter": name, "title": "Tide Pool"}))
    idx = open(os.path.join(d, "index.html")).read()
    check(f"starter {name}: copied into the new project with the title filled in", r["status"] == "ok" and "Tide Pool" in idx and "{{" not in idx and os.path.isfile(os.path.join(d, "tests", "gitcraft.features.json")))
    if name != "vite-react":
        st, at = standards.check(d, "public", "app"), standards.attribution(d)
        check(f"starter {name}: already meets the public standard and the attribution standard", st["status"] == "ok" and at["status"] == "ok",
              [c for c in st["checks"] + at["checks"] if not c["ok"]])
busy = os.path.join(ws, "busy"); os.makedirs(busy); open(os.path.join(busy, "notes.txt"), "w").write("mine")
builtins.scaffold(ctx(busy, {"dirs": [], "starter": "static-app", "title": "X"}))
check("starter: never copied into a folder that already has files", sorted(os.listdir(busy)) == ["notes.txt"])
P = lambda prompt, proj=None, ov=None: engine.plan(prompt, proj or os.path.join(ws, store.slugify(prompt)[:20]), ov)
pa = P("Build a recipe app for my family")
pg = P("Make a small arcade game called Dot Hop")
pr_ = P("Build a React dashboard app for my running club")
check("planner: the starter follows the deliverable and engine", pa["tasks"]["foundation.scaffold"]["params"]["starter"] == "static-app"
      and pg["tasks"]["foundation.scaffold"]["params"]["starter"] == "canvas-game" and pr_["tasks"]["foundation.scaffold"]["params"]["starter"] == "vite-react"
      and pr_["spec"]["project"]["asset_dir"] == "public/assets", (pa["tasks"]["foundation.scaffold"]["params"], pr_["spec"]["project"]))

# ---------------------------------------------------------------- the Decision Room's new choices
room = lambda pr: {d["id"]: d for d in pr["decision_room"]}
ps = P("Build a public website for a bakery, deployed to Vercel")
check("deployment: asked for → recommended Vercel; not asked → recommended no deploy; every web project is offered the choice",
      room(ps)["deployment"]["recommended"] == "vercel" and room(pa)["deployment"]["recommended"] == "no_deploy")
check("analytics: a public site is recommended HaveAnApp Pulse, a private app none", room(ps)["analytics"]["recommended"] == "pulse" and room(pa)["analytics"]["recommended"] == "none")
v = engine.decide(ps["id"], approve=True); pr = store.load(ps["id"])
check("approving the recommendations applies them (Pulse in the spec, the build instruction and the standards check)", pr["spec"]["analytics"]["provider"] == "pulse"
      and any("haveanapp-pulse" in i for i in pr["tasks"]["build"]["work_order"]["instructions"]) and pr["tasks"]["qa.standards"]["params"]["analytics"] == "pulse")
check("deploy work order: the approved target and the verify-live proof", any("Vercel" in i for i in pr["tasks"]["release.deploy"]["work_order"]["instructions"])
      and any("verify-live" in i for i in pr["tasks"]["release.deploy"]["work_order"]["instructions"]))
exist = os.path.join(ws, "has-pipeline"); os.makedirs(exist); open(os.path.join(exist, "index.html"), "w").write("<html lang=en><title>x</title></html>")
open(os.path.join(exist, "vercel.json"), "w").write("{}")
check("deployment: an existing project's own pipeline is recommended", room(P("Fix the footer in this site", exist))["deployment"]["recommended"] == "existing")
pb = P("Build a shared shopping list app for my family with user accounts and sync")
check("backend: accounts/sync → the hosted Postgres decision (recommended), on-device as the alternative", room(pb)["backend"]["recommended"] == "postgres"
      and "local" in [o["value"] for o in room(pb)["backend"]["options"]])
engine.decide(pb["id"], approve=True); pr = store.load(pb["id"])
check("backend: approved → backend.provision is planned, needs the 'infrastructure' approval; plan v2: the build runs on a local mock and "
      "backend.wire (after the approved provisioning) switches it before wiring and QA",
      pr.get("plan_version") == 2 and "backend.provision" in pr["tasks"] and pr["tasks"]["backend.provision"]["work_order"]["approval"] == "infrastructure"
      and "backend.provision" not in pr["tasks"]["build"]["depends_on"] and pr["tasks"]["backend.wire"]["depends_on"] == ["backend.provision", "build"]
      and "backend.wire" in pr["tasks"]["build.wire"]["depends_on"] and "backend" in {c["id"] for c in pr["spec"]["acceptance"]})
from production import planner as _pl   # plan v1 (existing records) keeps the build waiting for the provisioning
_v1 = _pl.build(pr["spec"], pr["discovery"], version=1)
check("backend: plan v1 unchanged (the build waits for backend.provision)", "backend.provision" in _v1["tasks"]["build"]["depends_on"] and "backend.wire" not in _v1["tasks"])
st = engine.run(pb["id"])
check("backend: provisioning is never pre-authorised (the run stops for a person)", "backend.provision" in [t["id"] for t in st["tasks"] if t["state"] == "needs_approval"], st["counts"])
bj = os.path.join(ws, "backend.json")
json.dump({"provider": "neon", "environments": {"development": "dev", "production": "main"}, "env_vars": ["DATABASE_URL"],
           "url": "postgresql://app:hunter2secret@ep-x.neon.tech/db"}, open(bj, "w"))
check("backend: a record holding a connection string with its password is refused", not icons.validate_no_secrets(bj)[0]["ok"])
json.dump({"provider": "neon", "environments": {"development": "dev", "production": "main"}, "env_vars": ["DATABASE_URL"]}, open(bj, "w"))
check("backend: names only pass", icons.validate_no_secrets(bj)[0]["ok"])
pn = P("Build a native iPhone app and Android app for logging tides")
check("native: an iOS/Android request plans both icon sets (Decision Room choice)", pn["spec"]["platform"]["native"] == ["android", "ios"] and "native" in room(pn))

# ---------------------------------------------------------------- Pulse, measured
pulse = os.path.join(ws, "pulse"); shutil.copytree(os.path.join(ws, "s-static-app"), pulse)
check("standards: Pulse chosen but missing fails", any(c["id"] == "analytics" and not c["ok"] for c in standards.check(pulse, "public", analytics="pulse")["checks"]))
h = open(os.path.join(pulse, "index.html")).read().replace("</head>", standards.pulse_snippet("Tide Pool") + "\n</head>"); open(os.path.join(pulse, "index.html"), "w").write(h)
check("standards: Pulse chosen and present passes", standards.check(pulse, "public", analytics="pulse")["status"] == "ok")
check("standards: Pulse present but not approved fails", any(c["id"] == "analytics" and not c["ok"] for c in standards.check(pulse, "public", analytics=None)["checks"]))

# ---------------------------------------------------------------- native icon sets
m = os.path.join(ws, "m.png"); px = bytearray(b"\x10\x20\x30\x00") * (1024 * 1024)
for y in range(300, 724):
    for x in range(300, 724): i = (y * 1024 + x) * 4; px[i:i + 4] = b"\xf0\xa0\x40\xff"
icons.encode(m, 1024, 1024, px)
nd = os.path.join(ws, "native"); r = icons.derivatives(m, nd, background="#102030", platforms=["ios", "android"])
nat = {o["rel"]: o["path"] for o in r["outputs"] if o.get("rel")}
check("native: iOS 1024 opaque icon + Contents.json; Android mipmaps 48-192 + adaptive icon", r["status"] == "ok" and "ios/AppIcon.appiconset/Contents.json" in nat
      and icons.opaque(icons.decode(nat["ios/AppIcon.appiconset/AppIcon-1024.png"])[2])
      and icons.header(nat["android/res/mipmap-xxxhdpi/ic_launcher.png"])[:2] == (192, 192) and "android/res/mipmap-anydpi-v26/ic_launcher.xml" in nat, r["checks"])
proj = os.path.join(ws, "nat-proj"); os.makedirs(proj)
res = builtins.integrate(dict(ctx(proj, {}), upstream=[{"id": "icon.derivatives", "state": "passed", "outputs": r["outputs"],
      "ship": {"dest": "$project/assets/icons", "roles": ["icon", "favicon", "icon_master", "icon_native"], "role_dest": {"icon_native": "$project/native-icons"},
               "folder_licence_roles": ["icon_native"]}}]))
check("native: integrated keeping its folders, in native-icons/, with no stray files inside Android res/", res["status"] == "ok"
      and os.path.isfile(os.path.join(proj, "native-icons", "android", "res", "mipmap-hdpi", "ic_launcher.png"))
      and not [f for d, _, fs in os.walk(os.path.join(proj, "native-icons", "android", "res")) for f in fs if f.endswith(".json") and "values" not in d]
      and os.path.isfile(os.path.join(proj, "assets", "icons", "icon-192.png")), res.get("checks"))

# ---------------------------------------------------------------- GitHub issues
gp = os.path.join(ws, "issues-proj"); os.makedirs(gp)
open(os.path.join(gp, "index.html"), "w").write("<!doctype html><html lang=en><head><title>x</title></head><body><script src=app.js></script></body></html>")
open(os.path.join(gp, "app.js"), "w").write("\n".join(f"function f{i}(){{}}" for i in range(100)))
r = entry.start("Run GITCRAFT: fix the open bugs", gp, issues=[{"number": 7, "title": "Crash when the list is empty", "labels": [{"name": "bug"}]},
                                                             {"number": 9, "title": "Add dark mode", "labels": ["enhancement"]}])
pi = store.load(r["production"]); inv = pi["maturity"]["inventory"]
check("issues: bugs become defects, the rest requests, in the Discovery Report", any("#7" in d["what"] for d in inv["defects"]) and any("#9" in q["what"] for q in inv["requests"])
      and "Open GitHub issues: read" in open(pi["discovery_report"]).read())

# ---------------------------------------------------------------- browser checks (features, live)
if executors.studio_python():
    app = os.path.join(ws, "list-app"); os.makedirs(os.path.join(app, "tests"))
    open(os.path.join(app, "index.html"), "w").write('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width"><title>List</title></head><body>'
        '<input id="item" aria-label="Item"><button id="add">Add</button><ul id="list"></ul>'
        '<script>document.getElementById("add").onclick=()=>{const li=document.createElement("li");li.textContent=document.getElementById("item").value;document.getElementById("list").append(li)}</script></body></html>')
    good = {"features": [{"name": "add an item", "requirement": "a shopping list", "steps": [{"fill": "#item", "value": "Milk"}, {"click": "#add"}, {"expect": "#list li", "text": "Milk"}]}]}
    json.dump(good, open(os.path.join(app, "tests", "gitcraft.features.json"), "w"))
    r = builtins.check_features(ctx(app, {"file": os.path.join(app, "tests", "gitcraft.features.json"), "required": True, "viewports": ["phone"]}))
    check("features: a feature that works passes in Chromium (fill, click, expect)", r["status"] == "ok", r["checks"])
    bad = {"features": [{"name": "delete an item", "requirement": "remove items", "steps": [{"click": "#add"}, {"click": "#delete", "timeout": 800}, {"expect": "#list li", "text": "gone", "timeout": 800}]}]}
    json.dump(bad, open(os.path.join(app, "tests", "gitcraft.features.json"), "w"))
    r = builtins.check_features(ctx(app, {"file": os.path.join(app, "tests", "gitcraft.features.json"), "required": True}))
    check("features: a feature that doesn't exist fails, naming the feature", r["status"] == "failed" and any("delete an item" in c["name"] and not c["ok"] for c in r["checks"]), r["checks"])
    json.dump({"features": [{"name": "nothing checked", "steps": [{"click": "#add"}]}]}, open(os.path.join(app, "tests", "gitcraft.features.json"), "w"))
    check("features: a check with no observable outcome is refused", builtins.check_features(ctx(app, {"file": os.path.join(app, "tests", "gitcraft.features.json"), "required": True}))["status"] == "failed")
    check("features: required for a new app and missing → fails", builtins.check_features(ctx(app, {"file": os.path.join(app, "nope.json"), "required": True}))["status"] == "failed")

    # verify-live against a local server (explicitly allowed for the test only)
    site = os.path.join(ws, "s-static-app")
    for o in icons.derivatives(m, os.path.join(ws, "site-icons"))["outputs"]:   # the release as it ships: starter + its icon set
        if o["role"] in ("icon", "favicon"): os.makedirs(os.path.join(site, "assets", "icons"), exist_ok=True); shutil.copy(o["path"], os.path.join(site, "assets", "icons"))
    os.environ["GITCRAFT_LIVE_ALLOW_LOCAL"] = "1"
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    fake = {"id": "live-test", "store": os.path.join(ws, "store-live"), "spec": {"project": {"path": site}, "attribution": {"required": True}, "analytics": {}}}
    os.makedirs(fake["store"])
    rec = live.verify(fake, url)
    check("verify-live: the server with this build passes (same page, same files, phone + desktop, byline visible)", rec["status"] == "ok", [c for c in rec["checks"] if not c["ok"]])
    other = os.path.join(ws, "deployed-copy"); shutil.copytree(site, other)
    open(os.path.join(other, "styles.css"), "a").write("/* changed */")
    srv2 = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=other)); threading.Thread(target=srv2.serve_forever, daemon=True).start()
    rec = live.verify(fake, f"http://127.0.0.1:{srv2.server_address[1]}/", browser=False)
    check("verify-live: a deployment serving different file bytes fails", rec["status"] == "failed" and any("byte-identical" in c["name"] and not c["ok"] for c in rec["checks"]), rec["checks"])
    wall = os.path.join(ws, "wall"); os.makedirs(wall); open(os.path.join(wall, "index.html"), "w").write("<html><head><title>Login – Vercel</title></head><body>Log in</body></html>")
    srv3 = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=wall)); threading.Thread(target=srv3.serve_forever, daemon=True).start()
    rec = live.verify(fake, f"http://127.0.0.1:{srv3.server_address[1]}/", browser=False)
    check("verify-live: a login wall is named as deployment protection, not passed", rec["status"] == "failed" and any("login wall" in str(c.get("detail")) for c in rec["checks"]), rec["checks"])
    os.environ.pop("GITCRAFT_LIVE_ALLOW_LOCAL")
    check("verify-live: plain http is refused outside the explicit local test", live.verify(fake, url, browser=False)["status"] == "failed")
    wall_url = "https://meshcraft-git-claude-festive-ritchie-dh7r9m-haveanapp.vercel.app/"   # a real preview behind Vercel deployment protection
    rec = live.verify(fake, wall_url, browser=False)
    if any(c["name"].startswith("the live URL answers") and c["ok"] for c in rec["checks"]):
        check("verify-live: a real Vercel URL behind deployment protection is reported as a login wall", rec["status"] == "failed" and any("login wall" in str(c.get("detail")) for c in rec["checks"]), rec["checks"])
    else:
        print("SKIP the real-URL check: no network here")
    for s_ in (srv, srv2, srv3): s_.shutdown()
else:
    print("SKIP browser checks: the Studio runtime is not installed")

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
