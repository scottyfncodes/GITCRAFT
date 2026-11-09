#!/usr/bin/env python3
"""Release verification: a broken application is never confused with a broken or incomplete verification.

    python3 tests/test_release_verification.py        (~1 min; the browser parts need the Studio runtime / Playwright)

Regression scenario: POW NOW PR #40 (https://snownow.vercel.app). GITCRAFT returned NOT READY for a release with a
successful Vercel deployment, green CI, 664 passing tests and passing visual and feature checks, because
  * it compared the local build's content-hashed JavaScript names with Vercel's,
  * the sandbox could not reach api.weather.gov / Open-Meteo and that read as a defect,
  * a public, read-only, GET-only API with wildcard CORS read as a vulnerability,
  * HaveAnApp Pulse, which the project already shipped, read as "analytics the blueprint did not approve",
  * an advisory task's findings turned into a failed acceptance criterion.
The fixture below is a small project with the same shape (Vite build, /api/forecast proxy, Pulse). Proven here:
  1. different Vercel-generated asset names do not on their own fail verification
  2. blocked sandbox network access is UNVERIFIED, never a confirmed production defect
  3. public read-only APIs are judged in context (writes, credentials, leaked env still fail)
  4. existing analytics are discovered and classified accurately
  5. real critical failures still block release
  6. mandatory unverified checks prevent READY (DEPLOYED · VERIFICATION INCOMPLETE)
  7. advisory-only findings do not block release
plus: console-error exceptions are narrow and documented; accepted decisions are not re-raised until evidence changes."""
import functools, http.server, json, os, shutil, subprocess, sys, tempfile, threading
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "studio"))
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-relver-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"),
                  GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
from production import engine, store, intake, standards, maturity, live, gates, report, verification as V, executors
from core import netclass
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:500]}]" if detail and not cond else ""), flush=True)


def cats(rec): return {c["name"]: c.get("category") for c in rec["checks"]}
def by(rec, cat): return [c for c in rec["checks"] if c.get("category") == cat]


# ---------------------------------------------------------------- the POW NOW-shaped fixture
pow_ = os.path.join(ws, "pow-now")
PULSE = '<script defer src="https://haveanapp-pulse-collect.vercel.app/p.js" data-app="pow-now"></script>'


def page(js, css, extra=""):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>POW NOW</title><link rel="stylesheet" href="/assets/{css}">{PULSE}</head>'
            f'<body><main id="app"><h1>POW NOW</h1><p id="snow">Loading the forecast…</p></main><script type="module" src="/assets/{js}"></script>{extra}</body></html>')


APP_JS = ("const el=document.getElementById('snow');"
          "fetch(%s).then(r=>r.json()).then(d=>{el.textContent='Snow: '+d.inches}).catch(e=>{console.error('forecast unavailable: '+e);el.textContent='Forecast unavailable right now'});")
os.makedirs(os.path.join(pow_, "dist", "assets")); os.makedirs(os.path.join(pow_, "api")); os.makedirs(os.path.join(pow_, "src")); os.makedirs(os.path.join(pow_, "tests"))
open(os.path.join(pow_, "index.html"), "w").write(page("main.js", "main.css").replace("/assets/main.js", "/src/main.js"))
open(os.path.join(pow_, "src", "main.js"), "w").write(APP_JS % "'https://api.weather.gov/points/39.6,-106.4'")
open(os.path.join(pow_, "dist", "index.html"), "w").write(page("index-Dk3sL9aQ.js", "index-B7xQ2mPa.css"))
open(os.path.join(pow_, "dist", "assets", "index-Dk3sL9aQ.js"), "w").write(APP_JS % "'https://api.weather.gov/points/39.6,-106.4'")
open(os.path.join(pow_, "dist", "assets", "index-B7xQ2mPa.css"), "w").write("body{font:16px system-ui}")
open(os.path.join(pow_, "api", "forecast.js"), "w").write(
    "export default async function handler(req, res) {\n  if (req.method !== 'GET') return res.status(405).end();\n"
    "  res.setHeader('Access-Control-Allow-Origin', '*');\n  res.setHeader('Cache-Control', 's-maxage=600, stale-while-revalidate');\n"
    "  const r = await fetch('https://api.open-meteo.com/v1/forecast?latitude=39.6&longitude=-106.4&daily=snowfall_sum');\n"
    "  res.status(r.ok ? 200 : 502).json(r.ok ? await r.json() : { error: 'upstream unavailable' });\n}\n")
open(os.path.join(pow_, "package.json"), "w").write(json.dumps({"name": "pow-now", "scripts": {"build": "vite build", "test": "vitest run"}, "devDependencies": {"vite": "5.4.0"}}))
open(os.path.join(pow_, "package-lock.json"), "w").write("{}")
open(os.path.join(pow_, "vercel.json"), "w").write(json.dumps({"buildCommand": "vite build", "outputDirectory": "dist"}))
open(os.path.join(pow_, "tests", "app.test.js"), "w").write("test('x',()=>{})\n")
open(os.path.join(pow_, "README.md"), "w").write("# POW NOW\n\nSnow forecasts.\n")
open(os.path.join(pow_, "src", "errors.js"), "w").write("window.addEventListener('error', e => alert(e.message));\n")
g = lambda *a: subprocess.run(["git", "-C", pow_, *a], capture_output=True, text=True)
g("init", "-q"); g("-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"); g("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "PR #40")
HEAD = g("rev-parse", "HEAD").stdout.strip()

# the "Vercel" deployment: the same commit built on another machine → different content-hash names
vercel = os.path.join(ws, "vercel-deploy"); os.makedirs(os.path.join(vercel, "assets"))
open(os.path.join(vercel, "index.html"), "w").write(page("index-Vx91LmQe.js", "index-C2pRt8Wn.css"))
shutil.copy(os.path.join(pow_, "dist", "assets", "index-Dk3sL9aQ.js"), os.path.join(vercel, "assets", "index-Vx91LmQe.js"))
open(os.path.join(vercel, "assets", "index-C2pRt8Wn.css"), "w").write("body{font:16px system-ui}\n")   # not byte-identical, and that is fine


def serve(d):
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type("Q", (http.server.SimpleHTTPRequestHandler,), {"log_message": lambda *a: None}), directory=d))
    threading.Thread(target=s.serve_forever, daemon=True).start(); return s, f"http://127.0.0.1:{s.server_address[1]}/"


os.environ["GITCRAFT_LIVE_ALLOW_LOCAL"] = "1"
servers = []
def prod_for(pid, **spec):
    p = {"id": pid, "store": os.path.join(ws, "store-" + pid), "spec": dict({"project": {"path": pow_}, "attribution": {}, "analytics": {}}, **spec)}
    os.makedirs(p["store"], exist_ok=True); return p


# ---------------------------------------------------------------- 1. hashed asset names
s1, u1 = serve(vercel); servers.append(s1)
P1 = prod_for("hash")
rec = live.verify(P1, u1, browser=False)
check("1. different Vercel-generated asset names do not fail verification (no blocker)", rec["status"] == "ok" and not by(rec, V.BLOCKER), by(rec, V.BLOCKER) + by(rec, V.UNVERIFIED))
check("1. the live page is recognised as this release once content hashes are masked", any("content-hashed names are masked" in n and c == V.PASS for n, c in cats(rec).items()), cats(rec))
check("1. every file the LIVE page references is checked for availability (not the local build's names)",
      any(c["name"].startswith("every file the live page references loads") and c["category"] == V.PASS and "2 references" in str(c.get("measured")) for c in rec["checks"]), rec["checks"])
check("1. masking: hashed names masked, stable names kept", live.unhash('<script src="/assets/index-Dk3sL9aQ.js">') == live.unhash('<script src="/assets/index-Vx91LmQe.js">')
      and live.unhash('<link href="/styles-mobile.css">') != live.unhash('<link href="/styles-tablet.css">') and live.is_hashed("/assets/index-Dk3sL9aQ.js") and not live.is_hashed("/app.js"))
rec = live.verify(P1, u1, browser=False, deployed_commit=HEAD[:9])
check("1. build provenance: the deployment's commit equals the release commit → PASS", any(n.startswith("build provenance") and c == V.PASS for n, c in cats(rec).items())
      and rec["deployment"]["serving"] is True, cats(rec))

# ---------------------------------------------------------------- 5. real failures still block (live)
rec = live.verify(P1, u1, browser=False, deployed_commit="0123456789abcdef0123456789abcdef01234567")
check("5. a deployment built from another commit is a BLOCKER (older deployment)", rec["status"] == "failed"
      and any(n.startswith("build provenance") and c == V.BLOCKER for n, c in cats(rec).items()), cats(rec))
broken = os.path.join(ws, "broken-deploy"); shutil.copytree(vercel, broken); os.remove(os.path.join(broken, "assets", "index-Vx91LmQe.js"))
s2, u2 = serve(broken); servers.append(s2)
rec = live.verify(P1, u2, browser=False)
check("5. a required asset the live page references that does not load is a BLOCKER", rec["status"] == "failed"
      and any(c["name"].startswith("every file the live page references") and c["category"] == V.BLOCKER and "index-Vx91LmQe.js" in str(c["detail"]) for c in rec["checks"]), rec["checks"])
older = os.path.join(ws, "older-deploy"); shutil.copytree(vercel, older)
open(os.path.join(older, "index.html"), "w").write(page("index-Vx91LmQe.js", "index-C2pRt8Wn.css").replace("<title>POW NOW</title>", "<title>Snow Now (beta)</title>").replace("<h1>", "<h2>"))
s3, u3 = serve(older); servers.append(s3)
rec = live.verify(P1, u3, browser=False)
check("5. a live page with a different title (an older or different deployment) is a BLOCKER", rec["status"] == "failed" and any("older or different deployment" in str(c.get("detail")) for c in by(rec, V.BLOCKER)), rec["checks"])
check("5. the live record of a confirmed failure reads NOT READY", rec["release_status"] == "NOT READY")

# no provenance at all: differing beyond hashes, same title → UNVERIFIED, never READY, never a defect
drift = os.path.join(ws, "drift-deploy"); shutil.copytree(vercel, drift)
open(os.path.join(drift, "index.html"), "w").write(page("index-Vx91LmQe.js", "index-C2pRt8Wn.css", extra='<div id="banner">New!</div>'))
s4, u4 = serve(drift); servers.append(s4)
rec = live.verify(P1, u4, browser=False)
check("6. a live page that differs and has no commit provenance is UNVERIFIED (cause no_provenance), status incomplete",
      rec["status"] == "incomplete" and any(c.get("cause") == "no_provenance" for c in by(rec, V.UNVERIFIED)) and not by(rec, V.BLOCKER), rec["checks"])
rec = live.verify(P1, u4, browser=False, deployed_commit=HEAD)
check("6. ...and with the deployment's commit given it is this release (the difference is an ADVISORY)", rec["status"] == "ok" and by(rec, V.ADVISORY), rec["checks"])

# ---------------------------------------------------------------- 2. sandbox network vs production failure (classification)
c_ = netclass.classify_request(*netclass.parse_failed("failed https://api.weather.gov/points/39.6,-106.4 (net::ERR_TUNNEL_CONNECTION_FAILED)"), origin_host="snownow.vercel.app")
check("2. a third-party request the proxy/sandbox refused is UNVERIFIED (sandbox_network), not a defect", c_["category"] == V.UNVERIFIED and c_["cause"] == "sandbox_network", c_)
c_ = netclass.classify_request(*netclass.parse_failed("failed https://api.open-meteo.com/v1/forecast (net::ERR_NAME_NOT_RESOLVED)"), origin_host="snownow.vercel.app")
check("2. DNS failure for an external API is a sandbox limitation", c_["cause"] == "sandbox_network" and c_["category"] == V.UNVERIFIED, c_)
c_ = netclass.classify_request(*netclass.parse_failed("503 https://api.weather.gov/points/x"), origin_host="snownow.vercel.app")
check("2. an external service answering 503 is an external outage (UNVERIFIED), distinct from the sandbox", c_["cause"] == "external_service" and c_["category"] == V.UNVERIFIED, c_)
c_ = netclass.classify_request(*netclass.parse_failed("404 https://snownow.vercel.app/assets/index-Vx91LmQe.js"), origin_host="snownow.vercel.app")
check("5. the app's own asset failing is a BLOCKER", c_["category"] == V.BLOCKER and c_["party"] == "first", c_)
c_ = netclass.classify_request(*netclass.parse_failed("404 https://api.weather.gov/pointz/x"), origin_host="snownow.vercel.app")
check("5. an external API answering 404 (a wrong URL in the app) is a BLOCKER", c_["category"] == V.BLOCKER, c_)
blocked = ["https://api.weather.gov/points/39.6,-106.4"]
cc = netclass.classify_console(["Failed to load resource: net::ERR_FAILED", "forecast unavailable: TypeError: Failed to fetch", "Uncaught ReferenceError: snow is not defined"],
                               ["https://api.weather.gov/points/39.6,-106.4", "https://snownow.vercel.app/assets/index.js", "https://snownow.vercel.app/assets/index.js"], blocked,
                               [{"pattern": r"^forecast unavailable: TypeError: Failed to fetch$", "reason": "the app's own message when the weather API is unreachable", "host": "api.weather.gov"}])
check("5/smoke. console: the browser's report of a blocked request is explained; the app's documented message is excepted; a real error stays",
      len(cc["sandbox"]) == 1 and len(cc["excepted"]) == 1 and cc["unexplained"] == ["Uncaught ReferenceError: snow is not defined"], cc)
cc = netclass.classify_console(["forecast unavailable: TypeError: Failed to fetch"], [""], [], [{"pattern": r"^forecast unavailable", "reason": "weather blocked", "host": "api.weather.gov"}])
check("smoke. a host-scoped exception does not apply in a run where that host was reachable", cc["unexplained"] and not cc["excepted"], cc)
_, refused = netclass.validate_exceptions([{"pattern": ".*", "reason": "ignore everything"}, {"pattern": "error", "reason": ""}, {"pattern": "Failed to fetch"}])
check("smoke. global or undocumented exceptions are refused (.*, no reason)", len(refused) == 3, refused)

# ---------------------------------------------------------------- 3. public read-only APIs in context
sc = standards.check(pow_, "public", "app", analytics="pulse", analytics_decided=False)
cors = next(c for c in sc["checks"] if c["id"] == "cors")
check("3. a GET-only, credential-free public API with wildcard CORS is an ADVISORY, not a failure", cors["status"] == "advisory" and cors["ok"] and sc["status"] == "ok",
      [(c["id"], c["status"], c["detail"]) for c in sc["checks"] if c["status"] not in ("ok", "n/a")])
check("3. ...and it still names what matters (read-only, no credentials)", "read-only" in str(cors["detail"]) and "no credentials" in str(cors["detail"]), cors)
api2 = os.path.join(ws, "api-proxy"); shutil.copytree(pow_, api2)
open(os.path.join(api2, "api", "forecast.js"), "w").write("export default async function h(req,res){res.setHeader('Access-Control-Allow-Origin','*');"
                                                          "const r=await fetch('https://api.open-meteo.com/v1/x');res.json(await r.json())}\n")
c2 = next(c for c in standards.check(api2, "public")["checks"] if c["id"] == "cors")
check("3. a public proxy without caching or rate limiting is flagged for abuse exposure (still advisory)", c2["status"] == "advisory" and "abuse exposure" in str(c2["detail"]), c2)
open(os.path.join(api2, "api", "forecast.js"), "w").write("export default function h(req,res){res.setHeader('Access-Control-Allow-Origin','*');if(req.method==='POST'){save(req.body)}res.json({})}\n")
c2 = next(c for c in standards.check(api2, "public")["checks"] if c["id"] == "cors")
check("3. wildcard CORS on a route that writes still fails", c2["status"] == "failed", c2)
open(os.path.join(api2, "api", "forecast.js"), "w").write("export default function h(req,res){res.setHeader('Access-Control-Allow-Origin','*');res.setHeader('Access-Control-Allow-Credentials','true');res.json({u:req.cookies.id})}\n")
check("3. wildcard CORS with credentials/cookies still fails", next(c for c in standards.check(api2, "public")["checks"] if c["id"] == "cors")["status"] == "failed")
open(os.path.join(api2, "api", "forecast.js"), "w").write("export default function h(req,res){res.setHeader('Access-Control-Allow-Origin','*');res.json(process.env)}\n")
sl = standards.check(api2, "personal")
check("3/5. a public endpoint that returns the process environment fails for every profile (sensitive data leak)",
      sl["status"] == "failed" and any(c["id"] == "env_leak" and c["status"] == "failed" for c in sl["checks"]), [(c["id"], c["status"]) for c in sl["checks"]])

# ---------------------------------------------------------------- 4. existing analytics
a = maturity.assess(pow_)
check("4. Discovery recognises the analytics the project already ships (Pulse, in its pages)", any(f["provider"] == "pulse" for f in a.get("analytics") or []), a.get("analytics"))
sp = intake.parse("Run GITCRAFT on POW NOW: verify PR #40 for release", pow_)
check("4. an existing project's spec declares the discovered analytics (source: discovered)", (sp.get("analytics") or {}).get("provider") == "pulse"
      and sp["analytics"].get("source") == "discovered", sp.get("analytics"))
sc0 = standards.check(pow_, "public", analytics=None, analytics_decided=False)
an = next(c for c in sc0["checks"] if c["id"] == "analytics")
check("4. undeclared existing analytics are an ADVISORY (recognised), never 'not approved'", an["status"] == "advisory" and an["ok"] and "HaveAnApp Pulse" in an["detail"], an)
check("4. preserved: when the Decision Room chose no analytics, Pulse on the page still fails",
      any(c["id"] == "analytics" and c["status"] == "failed" for c in standards.check(pow_, "public", analytics=None)["checks"]))
nodata = os.path.join(ws, "pulse-meta"); shutil.copytree(pow_, nodata)
open(os.path.join(nodata, "index.html"), "w").write(open(os.path.join(pow_, "index.html")).read().replace(' data-app="pow-now"', ""))
check("4. a Pulse tag without data-app is a configuration-metadata ADVISORY, not an integration failure",
      next(c for c in standards.check(nodata, "public", analytics="pulse")["checks"] if c["id"] == "analytics")["status"] == "advisory")
gone = os.path.join(ws, "pulse-gone"); shutil.copytree(pow_, gone)
open(os.path.join(gone, "index.html"), "w").write(open(os.path.join(pow_, "index.html")).read().replace(PULSE, ""))
check("4. preserved: declared Pulse absent from the entry page fails", next(c for c in standards.check(gone, "public", analytics="pulse")["checks"] if c["id"] == "analytics")["status"] == "failed")

# accepted architectural decisions
acc_dir = os.path.join(ws, "accepted"); shutil.copytree(pow_, acc_dir)
fp = next(c for c in standards.check(acc_dir, "public")["checks"] if c["id"] == "cors")["fingerprint"]
os.makedirs(os.path.join(acc_dir, ".gitcraft"))
json.dump({"accepted": [{"check": "cors", "fingerprint": fp, "reason": "forecast API is intentionally public and read-only", "by": "owner"},
                        {"check": "secrets", "reason": "trying to accept a blocker"}]}, open(os.path.join(acc_dir, ".gitcraft", "accepted.json"), "w"))
ca = next(c for c in standards.check(acc_dir, "public")["checks"] if c["id"] == "cors")
check("4. an accepted decision with the same evidence is not raised again (status accepted)", ca["status"] == "accepted" and ca["accepted"]["reason"].startswith("forecast"), ca)
open(os.path.join(acc_dir, "api", "forecast.js"), "a").write("// v2\nexport const config = { runtime: 'edge', note: 'now proxies two upstreams' };\nfetch('https://api.weather.gov/x');\n")
ca = next(c for c in standards.check(acc_dir, "public")["checks"] if c["id"] == "cors")
check("4. ...until the circumstances change (new evidence → raised again, saying it was accepted before)", ca["status"] == "advisory" and "evidence changed" in ca["detail"], ca)
open(os.path.join(acc_dir, "src", "key.js"), "w").write("const k='sk_live_" + "b" * 24 + "';\n")
cs = next(c for c in standards.check(acc_dir, "public")["checks"] if c["id"] == "secrets")
check("5. a security failure can never be accepted away", cs["status"] == "failed" and "cannot be accepted" in cs["detail"], cs)

# ---------------------------------------------------------------- verdicts: 5, 6, 7 on productions
def synth(pid, tasks, crits, live_rec=None):
    p = {"id": pid, "store": os.path.join(ws, "store-" + pid), "spec": {"title": "POW NOW", "prompt": "verify", "project": {"path": pow_}, "features": {"deploy": bool(live_rec)},
                                                                         "deliverable": "app", "dimension": "2d", "platform": {"mobile_first": True}, "quality": {"level": "standard"},
                                                                         "acceptance": [{"id": c, "text": c} for c in crits]}, "order": [t["id"] for t in tasks],
         "tasks": {t["id"]: dict({"attempts": [], "stage": "qa", "owner": "x"}, **t) for t in tasks}}
    os.makedirs(p["store"], exist_ok=True)
    if live_rec: json.dump(live_rec, open(os.path.join(store.task_dir(p, "release.deploy"), "live-check.json"), "w"))
    return p


live_ok = {"status": "ok", "request": {"url": "https://snownow.vercel.app/"}, "checks": [V.make("the live URL answers 200", V.PASS)],
           "deployment": {"answers": True, "serving": True, "evidence": "entry page equal modulo content hashes"}, "hosts_ok": ["api.weather.gov", "api.open-meteo.com"]}
live_inc = dict(live_ok, status="incomplete", hosts_ok=[], checks=live_ok["checks"] + [V.make("phone: external service api.weather.gov verified live", V.UNVERIFIED, "proxy", cause="sandbox_network", host="api.weather.gov")])
base = [{"id": "qa.smoke", "state": "passed", "criterion": "loads"}, {"id": "qa.features", "state": "passed", "criterion": "features"},
        {"id": "qa.pixelcraft", "state": "passed", "criterion": "interface_quality"}]
adv = synth("adv", base + [{"id": "qa.standards", "state": "failed", "advisory": True, "criterion": "engineering_standards",
                            "result": {"checks": [{"name": "the API does not allow every origin", "ok": True, "category": "advisory", "detail": "public read-only"}]}}],
            ["loads", "features", "interface_quality", "engineering_standards"])
A = report.acceptance(adv)
check("7. a criterion measured only by an advisory task that flagged findings is 'advisory', not 'failed'", {a["id"]: a["status"] for a in A}["engineering_standards"] == "advisory", A)
check("7. advisory-only findings do not block: the verdict is READY", report.verdict(A) == "READY", report.verdict(A))
rs = V.release_summary(adv, A)
check("7. ...and the release summary lists them as advisories", rs["release_status"] == "READY" and rs["advisories"] and not rs["blockers"], rs)

unv = synth("unv", [dict(base[0], state="blocked", unverified=[{"check": "phone: external service api.weather.gov verified", "cause": "sandbox_network", "host": "api.weather.gov"}],
                         reason="verification incomplete")] + base[1:], ["loads", "features", "interface_quality"])
A = report.acceptance(unv)
check("6. a check blocked only by the sandbox network is 'unverified' (cause named), never 'failed'", A[0]["status"] == "unverified" and A[0]["cause"] == "sandbox_network", A[0])
check("6. a mandatory unverified check prevents READY (INCOMPLETE, not NOT READY)", report.verdict(A) == "INCOMPLETE", report.verdict(A))
unv_live = synth("unv-live", [dict(t) for t in unv["tasks"].values()], ["loads", "features", "interface_quality", "deployment"], live_inc)
unv_live["tasks"]["release.deploy"] = {"id": "release.deploy", "state": "awaiting_agent", "criterion": "deployment", "attempts": [], "stage": "release", "owner": "agent"}
unv_live["order"].append("release.deploy")
rs = V.release_summary(unv_live)
check("6. deployed and serving this release, with mandatory checks unverified → DEPLOYED · VERIFICATION INCOMPLETE",
      rs["release_status"] == "DEPLOYED · VERIFICATION INCOMPLETE" and rs["deployment"]["status"] == "deployed_incomplete" and not rs["blockers"], rs)
check("6. the summary reports deployment, functional, security, visual, unverified causes and advisories separately",
      {"deployment", "functional", "security", "visual", "unverified", "advisories", "release_status"} <= set(rs) and any(u["cause"] == "sandbox_network" for u in rs["unverified"]), rs)
md = report.markdown(unv_live)
check("6. the report leads with the release summary and the status line", "## Release summary" in md and "DEPLOYED · VERIFICATION INCOMPLETE" in md, md[:600])
res_live = synth("res-live", [dict(t) for t in unv["tasks"].values()], ["loads", "features", "interface_quality"], live_ok)
A = report.acceptance(res_live)
check("2/6. independent production verification resolves it: the live check reached the host the sandbox could not → passed",
      A[0]["status"] == "passed" and report.verdict(A) == "READY", A[0])
mocked = synth("mocked", [dict(t) for t in unv["tasks"].values()], ["loads", "features", "interface_quality"], dict(live_ok, hosts_ok=["127.0.0.1"]))
check("2. a resilience pass (or a mock) is never presented as proof of the live integration", report.acceptance(mocked)[0]["status"] == "unverified")

failed = synth("failed", [dict(base[0], state="failed", error="phone: no page errors (Uncaught TypeError)")] + base[1:], ["loads", "features", "interface_quality"], live_ok)
A = report.acceptance(failed)
check("5. a measured failure still blocks: NOT READY, and the summary names a blocker", report.verdict(A) == "NOT READY" and V.release_summary(failed, A)["release_status"] == "NOT READY"
      and V.release_summary(failed, A)["blockers"], A[0])
mixed = synth("mixed", [dict(base[0], state="failed")] + [dict(base[1], state="blocked", unverified=[{"check": "x", "cause": "sandbox_network", "host": "a.b"}])] + base[2:],
              ["loads", "features", "interface_quality"])
check("5. a blocker is not hidden by an unverified check next to it", report.verdict(report.acceptance(mixed)) == "NOT READY")
json.dump(live_inc, open(os.path.join(ws, "inc.json"), "w"))
r = engine._verify_deploy("https://snownow.vercel.app/", os.path.join(ws, "inc.json"))
check("6. the deployment gate never records an incomplete live check as verified", r["ok"] is False, r)
check("6. ...it says DEPLOYED · VERIFICATION INCOMPLETE and names what is unverified", r.get("incomplete") and "DEPLOYED · VERIFICATION INCOMPLETE" in r["detail"] and "api.weather.gov" in r["detail"], r)

# gates: unverified-only failures are not quality failures to "fix"
res = {"status": "failed", "outputs": [{"path": "x"}], "checks": [{"name": "phone: no page errors", "ok": True},
                                                                 {"name": "phone: external service api.weather.gov verified", "ok": False, "category": "unverified", "cause": "sandbox_network", "host": "api.weather.gov"}]}
gr = gates.evaluate({"gate": [{"type": "status_ok"}]}, res, {"project": pow_})
check("2. gate: a result whose only failing checks are unverified is reported unverified (no remediation)", gr[0].get("category") == "unverified" and gr[0]["unverified"][0]["host"] == "api.weather.gov", gr)
res["checks"].append({"name": "phone: no page errors during play", "ok": False, "detail": ["Uncaught TypeError"]})
check("5. gate: a page error next to it keeps the gate a plain failure", "category" not in gates.evaluate({"gate": [{"type": "status_ok"}]}, res, {"project": pow_})[0])

# engine: an unverified-only result is recorded as blocked (verification incomplete) and never gets a fix work order
ep = synth("engine", [{"id": "qa.smoke", "state": "in_progress", "criterion": "loads", "kind": "studio", "department": "testcraft", "action": "smoke",
                       "gate": [{"type": "status_ok"}], "attempts": [{"n": 1}], "retries": 1, "params": {}, "resources": [], "timeout": 60}], ["loads"])
ep["spec"]["quality"] = {"level": "standard", "max_rounds": 2}; ep["spec"]["mode"] = {"workflow": "build"}
res_e = {"status": "failed", "verification": "incomplete", "error": "unverified checks (not failures): x", "outputs": [{"path": os.path.join(pow_, "README.md"), "role": "report"}],
         "checks": [{"name": "phone: no page errors", "ok": True}, {"name": "phone: external service api.weather.gov verified", "ok": False, "category": "unverified",
                                                                  "cause": "sandbox_network", "host": "api.weather.gov"}]}
engine._finish(ep, ep["tasks"]["qa.smoke"], dict(res_e))
t_ = ep["tasks"]["qa.smoke"]
check("engine: unverified-only → BLOCKED with the unverified checks recorded, no fix work order", t_["state"] == "blocked" and t_.get("unverified")
      and "not an application failure" in t_.get("reason", "") and not any(k.startswith("fix.") for k in ep["tasks"]), (t_["state"], t_.get("reason"), list(ep["tasks"])))
check("engine: ...and the production verdict is INCOMPLETE, the release summary VERIFICATION INCOMPLETE", report.verdict(report.acceptance(ep)) == "INCOMPLETE"
      and V.release_summary(ep)["release_status"] == "VERIFICATION INCOMPLETE")

# ---------------------------------------------------------------- the real browser: TestCraft smoke + live check with an unreachable weather API
if executors.studio_python():
    r = executors.studio_run("testcraft", "smoke", {"target": os.path.join(pow_, "dist"), "viewports": ["phone"], "expect_canvas": False, "wait_ms": 800, "name": "smoke",
                                                    "console_error_exceptions": [{"pattern": r"^forecast unavailable: TypeError: Failed to fetch$", "host": "api.weather.gov",
                                                                                  "reason": "POW NOW logs this when the weather API is unreachable; the page shows 'Forecast unavailable'"}]})
    cs = {c["name"]: c for c in r.get("checks", [])}
    check("smoke: page errors and missing files still pass/fail on their own (no global ignore)", cs.get("phone: no page errors", {}).get("ok") and cs.get("phone: no missing files", {}).get("ok"), r.get("checks") or r)
    check("smoke: console errors from the blocked weather API are explained, not failures", cs.get("phone: no console errors", {}).get("ok"), cs.get("phone: no console errors"))
    check("smoke: the weather integration is UNVERIFIED (sandbox_network), not passed and not failed",
          cs.get("phone: external service api.weather.gov verified", {}).get("category") == "unverified", list(cs))
    gr = gates.evaluate({"gate": [{"type": "status_ok"}]}, r, {"project": pow_})
    check("smoke → gate: verification incomplete, not a quality failure", gr[0].get("category") == "unverified" and gates.classify(r) == "quality", gr)
    r2 = executors.studio_run("testcraft", "smoke", {"target": os.path.join(pow_, "dist"), "viewports": ["phone"], "expect_canvas": False, "wait_ms": 800, "name": "smoke2"})
    cs2 = {c["name"]: c for c in r2.get("checks", [])}
    check("smoke: without the documented exception, the app's own console.error is still reported as a failure", not cs2.get("phone: no console errors", {}).get("ok"), cs2.get("phone: no console errors"))
    # live: the deployed page calls an API this verifier cannot reach (an unresolvable host stands in for a blocked one)
    unreach = os.path.join(ws, "unreachable"); shutil.copytree(vercel, unreach)
    open(os.path.join(unreach, "assets", "index-Vx91LmQe.js"), "w").write(APP_JS % "'https://api.weather.invalid/points/39.6,-106.4'")
    s5, u5 = serve(unreach); servers.append(s5)
    rec = live.verify(prod_for("unreach", verification={"console_error_exceptions": [{"pattern": r"^forecast unavailable", "reason": "weather unreachable", "host": "api.weather.invalid"}]}),
                      u5, deployed_commit=HEAD)
    names = cats(rec)
    check("live: the app's own page and assets PASS; the unreachable weather API is UNVERIFIED with its cause",
          not by(rec, V.BLOCKER) and any("api.weather.invalid" in c["name"] and c.get("cause") in ("sandbox_network", "no_answer") for c in by(rec, V.UNVERIFIED)), rec["checks"])
    check("live: resilience is recorded separately and never as proof of the integration",
          any("resilience" in n and c == V.PASS for n, c in names.items()) and any("not proof" in str(c.get("detail")) for c in rec["checks"] if "resilience" in c["name"]), names)
    check("live: DEPLOYED · VERIFICATION INCOMPLETE, not NOT READY and not READY", rec["status"] == "incomplete" and rec["release_status"] == "DEPLOYED · VERIFICATION INCOMPLETE", rec["release_status"])
    thrower = os.path.join(ws, "thrower"); shutil.copytree(vercel, thrower)
    open(os.path.join(thrower, "assets", "index-Vx91LmQe.js"), "w").write("snow.inches.toFixed()")
    s6, u6 = serve(thrower); servers.append(s6)
    rec = live.verify(prod_for("thrower"), u6, deployed_commit=HEAD)
    check("5. live: a page exception is a BLOCKER even when the deployment is this release", rec["status"] == "failed"
          and any("page errors" in c["name"] for c in by(rec, V.BLOCKER)), rec["checks"])
else:
    print("SKIP browser checks: the Studio runtime is not installed")

for s_ in servers: s_.shutdown()
os.environ.pop("GITCRAFT_LIVE_ALLOW_LOCAL", None)
bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed")
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
