#!/usr/bin/env python3
"""A server-rendered app as the evaluation target (VINO NOTA: Next.js behind sign-in, no static entry page), and
two PIXELCRAFT verifier follow-ups from the same production.

  1. opt-in only          a project is evaluated at a running URL only when it declares it in .gitcraft/evaluation.json;
                          a project without the file is planned exactly as before (build folder or source); a malformed
                          or non-local declaration is refused with its reason, never guessed around
  2. never a folder       nothing answering at the URL blocks the checks with the project's own start command; they never
                          fall back to a folder, and no index.html is expected of the project
  3. the same checks      the plan hands the URL and the declared landing page to smoke, the regression, the icon check,
                          the request and standards checks, and the declared screens to PIXELCRAFT; the build work order
                          expects the declared source entry
  4. measured as served   the icon check fetches the page and every linked icon from the local server; Pulse injected by a
                          framework's script component is recognised from the page it serves; the request check reads the
                          served page
  5. a real browser       TestCraft's smoke opens a running local app, reports a file its server answers 404 for, and
                          refuses a non-local address
  6. verifier             touching siblings that round to a 1 px overlap are still measured for even spacing (coverage is
                          not lost to rounding); a documented exclusion covers exactly one metric on one screen at one
                          viewport, with a reason, and is refused when vague and failed when stale

    python3 tests/test_served_target.py        (~30 s; the browser part needs the Studio runtime, else it is skipped)"""
import http.server, json, os, shutil, struct, subprocess, sys, tempfile, threading, zlib
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "studio"))
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-served-"))
os.environ.update(GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_PRODUCTION_ISOLATED=os.path.join(ws, "isolated-home"),
                  GITCRAFT_ASSET_CATALOG=os.path.join(ws, "catalog.sqlite"))
os.environ.pop("GITCRAFT_PRODUCTION_HOME", None)
from production import artifacts, builtins, discovery, executors, icons, live, maturity, planner, qa, standards
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:500]}]" if detail and not cond else ""), flush=True)


def raises(fn, text=""):
    try: fn()
    except Exception as e: return text in str(e)
    return False


def png(size, rgb=(110, 31, 43), mark=(243, 238, 227)):
    """An opaque PNG with a visible shape (a light block on a dark field), as an icon check expects."""
    rows = b""
    for y in range(size):
        rows += b"\x00" + b"".join(bytes(mark if size // 4 <= x < 3 * size // 4 and size // 4 <= y < 3 * size // 4 else rgb) for x in range(size))
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


PULSE = standards.PULSE_SRC
PAGE = ('<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1"><title>Cellar Book</title>'
        '<link rel="icon" href="/icon.png?abc123" type="image/png" sizes="32x32"><link rel="apple-touch-icon" href="/apple-icon.png?abc123" sizes="180x180">'
        '<link rel="manifest" href="/manifest.webmanifest"><meta name="theme-color" content="#6e1f2b"><meta name="apple-mobile-web-app-title" content="Cellar Book">'
        f'<link rel="preload" href="{PULSE}" as="script"></head><body><main><h1>Cellar Book</h1><p>Sign in to open your journal.</p></main>'
        '<script>(self.__next_f=self.__next_f||[]).push([1,"{\\"src\\":\\"' + PULSE + '\\",\\"data-app\\":\\"cellar-book\\",\\"strategy\\":\\"afterInteractive\\"}"])</script></body></html>')
MANIFEST = {"name": "Cellar Book", "icons": [{"src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                                             {"src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
ROUTES = {"/": (PAGE.encode(), "text/html"), "/sign-in": (PAGE.encode(), "text/html"), "/icon.png": (png(32), "image/png"), "/apple-icon.png": (png(180), "image/png"),
          "/manifest.webmanifest": (json.dumps(MANIFEST).encode(), "application/manifest+json"), "/icons/icon-192.png": (png(192), "image/png"),
          "/icons/icon-512.png": (png(512), "image/png"), "/icons/icon-maskable-512.png": (png(512), "image/png"),
          "/broken": (b'<!doctype html><html lang="en"><head><title>Broken</title></head><body><h1>Broken</h1><img src="/missing.png" alt=""></body></html>', "text/html")}


class App(http.server.BaseHTTPRequestHandler):
    """A stand-in for a server-rendered app: pages and icons exist only as routes, never as files in a project."""
    def do_GET(self):
        body, ctype = ROUTES.get(self.path.split("?")[0], (None, None))
        self.send_response(200 if body is not None else 404); self.send_header("content-type", ctype or "text/plain")
        self.send_header("content-length", str(len(body or b"not found"))); self.end_headers(); self.wfile.write(body or b"not found")

    def log_message(self, *a): pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), App); PORT = srv.server_address[1]; URL = f"http://127.0.0.1:{PORT}"
threading.Thread(target=srv.serve_forever, daemon=True).start()


def project(name, declaration=None, next_app=True):
    """A Next.js-shaped project with no index.html anywhere (route groups, a root layout, a build script)."""
    p = os.path.join(ws, name); os.makedirs(os.path.join(p, "src", "app", "(app)"))
    open(os.path.join(p, "src", "app", "layout.tsx"), "w").write("export default function Root({ children }) { return <html lang=\"en\"><body>{children}</body></html>; }\n" * 3)
    open(os.path.join(p, "src", "app", "(app)", "page.tsx"), "w").write("export default function Home() { return <main>Journal</main>; }\n")
    open(os.path.join(p, "package.json"), "w").write(json.dumps({"name": name, "scripts": {"build": "next build", "start": "next start"}, "dependencies": {"next": "16.0.0", "react": "19.0.0"} if next_app else {}}))
    if declaration is not None:
        os.makedirs(os.path.join(p, ".gitcraft")); open(os.path.join(p, ".gitcraft", "evaluation.json"), "w").write(declaration if isinstance(declaration, str) else json.dumps(declaration))
    return p


DECL = {"target": "server", "url": URL, "entry": "src/app/layout.tsx", "page": "/sign-in", "start": "npm run build && npm run start", "prepare": "npm run seed",
        "pixelcraft": {"screens": [{"name": "Sign in", "path": "/sign-in"}], "accept_tells": ["eyebrow"], "exclusions": []}}

# ---------------------------------------------------------------- 1. opt-in only
plain = project("plain")
pol = artifacts.target_policy({}, plain)
check("a Next.js project with no declaration is planned as before (its build folder, never a URL)", pol["chosen"] == "build" and pol["dir"] == "out" and "url" not in pol, pol)
check("with no declaration there is nothing declared and discovery records no served app", artifacts.declared(plain) == {} and "served" not in discovery.project(plain))
check("evaluation.target=server without a declaration is refused", raises(lambda: artifacts.target_policy({"evaluation": {"target": "server"}}, plain), ".gitcraft/evaluation.json"))
served = project("served", DECL)
pol = artifacts.target_policy({}, served)
check("a declared server-rendered app is evaluated at its running URL", pol["chosen"] == "server" and pol["url"] == URL and pol["page"] == "/sign-in" and pol["dir"] is None, pol)
check("an explicit build or source policy still wins over the declaration", artifacts.target_policy({"evaluation": {"target": "build"}}, served)["chosen"] == "build"
      and artifacts.target_policy({"evaluation": {"target": "source"}}, served)["chosen"] == "source")
for label, bad, why in (("a deployed URL", dict(DECL, url="https://example.com"), "local address"), ("a missing entry file", dict(DECL, entry="src/app/nope.tsx"), "entry must name"),
                        ("an entry outside the project", dict(DECL, entry="../x.tsx"), "entry must name"), ("no start command", {k: v for k, v in DECL.items() if k != "start"}, "start is required"),
                        ("another target", dict(DECL, target="build"), 'target must be "server"'), ("a page that is not a path", dict(DECL, page="sign-in"), "page must be a path")):
    p = project("bad-" + label.replace(" ", "-"), bad)
    check(f"a declaration with {label} is refused with its reason", raises(lambda: artifacts.target_policy({}, p), why) and "served" not in discovery.project(p), artifacts.declared(p).get("problems"))
check("a declaration that is not JSON is reported, never guessed around", raises(lambda: artifacts.target_policy({}, project("bad-json", "{not json")), "does not read as JSON"))

# ---------------------------------------------------------------- 2. never a folder
target, why = artifacts.resolve_target(served, pol)
check("a running app resolves to its URL", target == URL and why is None, why)
dead = dict(pol, url="http://127.0.0.1:9")   # the discard port: nothing answers
target, why = artifacts.resolve_target(served, dead)
check("nothing answering blocks the checks with the project's own start command (never a folder)",
      target is None and "npm run build && npm run start" in why and "npm run seed" in why and "never fall back to a folder" in why, why)
check("no index.html is expected of the project", not os.path.exists(os.path.join(served, "index.html")) and not os.path.isdir(os.path.join(served, "out")))

# ---------------------------------------------------------------- 3. the same checks, pointed at the app
info = discovery.project(served)
check("discovery records the declared entry and the served app", info["entry"] == "src/app/layout.tsx" and info["served"]["url"] == URL and info["served"]["page"] == "/sign-in", info.get("served"))
check("maturity reads the declared entry (a served app is not 'no entry point')", maturity.assess(served)["entry"] == "src/app/layout.tsx")
check("maturity is unchanged for a project with no declaration", maturity.assess(plain)["entry"] is None)
check("the build work order expects the declared source entry, as text", planner._entry_expected(info) == {"path": "$project/src/app/layout.tsx", "format": "text"})
check("a static project's build work order still expects index.html", planner._entry_expected(discovery.project(plain)) == {"path": "$project/index.html", "format": "html"})
check("smoke opens the declared landing page", planner._page(info) == {"entry": "/sign-in"} and planner._page(discovery.project(plain)) == {})
check("source-reading checks are handed the URL and page", planner._served_page(info) == {"target": "$target", "page": "/sign-in"} and planner._served_page(discovery.project(plain)) == {})
check("PIXELCRAFT gets the declared screens (they sit behind sign-in and cannot be discovered)",
      planner._px(info, "screens", "accept_tells", "exclusions") == {"screens": DECL["pixelcraft"]["screens"], "accept_tells": ["eyebrow"]} and planner._px(discovery.project(plain), "screens") == {})

# ---------------------------------------------------------------- 4. measured as served
r = icons.verify(served, served=icons.Served(URL, "/sign-in"))
check("the icon check passes on the page and icons the app serves", r["status"] == "ok" and r["info"]["entry"] == URL + "/sign-in" and len(r["checks"]) >= 10, [c for c in r["checks"] if not c["ok"]])
check("a favicon the server does not serve is a broken reference", any(not c["ok"] and "exists" in c["name"] for c in icons.verify(served, served=type("S", (icons.Served,), {"text": lambda self: (PAGE.replace("/icon.png", "/gone.png"), None)})(URL, "/sign-in"))["checks"]))
check("an entry page that does not answer fails with its reason", icons.verify(served, served=icons.Served("http://127.0.0.1:9", "/"))["status"] == "failed")
check("a non-local address is never fetched", icons.Served("https://example.com", "/").text()[0] is None)
check("a static project's icon check is unchanged (it needs an entry index.html)", icons.verify(plain)["checks"][0]["name"] == "an entry index.html exists")
page, why = builtins.served_page({"target": URL, "page": "/sign-in"})
check("the served entry page is fetched for source-reading checks", page == PAGE and why is None)
check("a folder target fetches nothing", builtins.served_page({"target": "/tmp/x"}) == (None, None) and builtins.served_page({}) == (None, None))
check("Pulse injected after load by a framework's script component is recognised, complete", standards._pulse_served(PAGE) == [])
check("its missing attributes are named", standards._pulse_served(PAGE.replace('\\"data-app\\":\\"cellar-book\\",', "")) == ["data-app="] and standards._pulse_served("<html></html>") is None)
st = standards.check(served, analytics="pulse", page=PAGE)
check("the standards check reads the served page: Pulse is found on it, where the static check finds none",
      next(c for c in st["checks"] if c["id"] == "analytics")["status"] == "ok"
      and next(c for c in standards.check(served, analytics="pulse")["checks"] if c["id"] == "analytics")["status"] == "failed", [c for c in st["checks"] if c["id"] == "analytics"])
rq = qa.evaluate_request(served, {"html": PAGE})
check("the request check reads the served page (no index.html asked for)", rq[0]["name"] == "request: the entry page exists" and rq[0].get("category", rq[0].get("status")) != "blocker" and all("no index.html" not in str(c.get("detail")) for c in rq), rq[:2])
check("without a served page it still reads the project's entry file", "no index.html" in str(qa.evaluate_request(served, {})[0].get("detail")))
# verify-live: the app's own sign-in page is the app; a host's authentication wall is still a wall
check("live: a declared app's own sign-in page is not a login wall", live.own_sign_in(served, "https://app.example/", "https://app.example/sign-in", PAGE))
check("live: a redirect to the host's authentication is still a wall", not live.own_sign_in(served, "https://app.example/", "https://vercel.com/sso-api?url=x", "<title>Login</title>"))
check("live: the host's authentication page on the same address is still a wall", not live.own_sign_in(served, "https://app.example/", "https://app.example/", "<title>Authentication Required</title>Vercel Authentication"))
check("live: a project with no declaration keeps the old reading (a sign-in title is a wall)", not live.own_sign_in(plain, "https://app.example/", "https://app.example/sign-in", PAGE))
found = []
live._get, real_get = (lambda u, *a, **k: (200, b"/* pulse */", u)), live._get
live._analytics({"analytics": {"provider": "pulse"}}, PAGE, found.append)
live._analytics({"analytics": {"provider": "pulse"}}, "<html><title>x</title></html>", found.append)
live._get = real_get
check("live: Pulse injected after load is found on the live page", found[0]["category"] == "pass" and "injected" in str(found[0].get("measured")), found[:1])
check("live: a page with no Pulse at all is still a blocker", found[-1]["category"] == "blocker", found[-1:])

# ---------------------------------------------------------------- 5. a real browser on a running app
if executors.studio_python():
    def smoke(params):
        r = subprocess.run([executors.studio_python(), os.path.join(REPO, "studio", "cli.py"), "--call", "run",
                            json.dumps({"department": "testcraft", "action": "smoke", "params": dict({"viewports": ["phone"], "wait_ms": 300, "expect_canvas": False, "register": False}, **params)})],
                           capture_output=True, text=True, timeout=300, env=dict(os.environ, GITCRAFT_ROOTS=ws))
        try: return json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError): return {"status": "crash", "error": (r.stderr or r.stdout)[-600:]}
    r = smoke({"target": URL, "entry": "/sign-in", "out_dir": os.path.join(ws, "smoke-ok"), "name": "served"})
    names = {c["name"]: c for c in r.get("checks", [])}
    check("smoke opens a running local app at the declared page", names.get("phone: no page errors", {}).get("ok") and names.get("phone: no missing files", {}).get("ok")
          and names.get("phone: renders something (not a blank screen)", {}).get("ok"), r.get("error") or [c for c in r.get("checks", []) if not c["ok"]])
    check("an external script is still blocked and listed as unverified, exactly as for a folder",
          any(c.get("category") == "unverified" and "haveanapp-pulse-collect.vercel.app" in c["name"] for c in r.get("checks", [])), list(names))
    r = smoke({"target": URL, "entry": "/broken", "out_dir": os.path.join(ws, "smoke-broken"), "name": "broken"})
    miss = next((c for c in r.get("checks", []) if c["name"] == "phone: no missing files"), {})
    check("a file the app's own server answers 404 for is a missing file", miss.get("ok") is False and "/missing.png" in str(miss.get("detail")), r.get("error") or miss)
    r = smoke({"target": "https://example.com", "out_dir": os.path.join(ws, "smoke-remote"), "name": "remote"})
    check("smoke refuses a non-local address", r.get("status") != "ok" and "not a local address" in json.dumps(r), r)
    os.makedirs(os.path.join(ws, "static")); open(os.path.join(ws, "static", "index.html"), "w").write("<!doctype html><html lang='en'><title>s</title><body style='background:#135'><h1 style='color:#fff'>static</h1></body></html>")
    r = smoke({"target": os.path.join(ws, "static"), "out_dir": os.path.join(ws, "smoke-static"), "name": "static"})
    check("a folder target is served and smoke-tested as before", r.get("status") == "ok" and all(c["ok"] for c in r.get("checks", [])), r.get("error") or [c for c in r.get("checks", []) if not c["ok"]])
else:
    print("SKIP the browser checks: the Studio runtime is not installed here", flush=True)

# ---------------------------------------------------------------- 6. the PIXELCRAFT verifier
import importlib.util


def load(name):
    spec = importlib.util.spec_from_file_location("gitcraft_px_" + name, os.path.join(REPO, "studio", "departments", "pixelcraft", name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


try:
    M = load("measure")
    def cap(heights_and_tops):
        els = [{"i": 0, "p": None, "r": [16, 100, 288, 400], "tag": "ol", "sel": "main > ol.list", "disp": "block"}]
        for n, (top, h) in enumerate(heights_and_tops, 1):
            els.append({"i": n, "p": 0, "r": [16, top, 288, h], "tag": "li", "sel": f"main > ol.list > li:nth-of-type({n})", "disp": "list-item", "t": "row"})
        return M.Capture({"screen": "List", "viewport": "narrow", "dom": {"els": els, "vw": 320, "vh": 568}}, {"name": "narrow", "width": 320, "height": 568, "mobile": True})
    def evenness(c):
        C = M.Collector(); M.spacing(c, C)
        return next((m for m in C.metrics if m["id"] == "spacing.evenness"), None)
    flush = evenness(cap([(100, 80), (180, 80), (260, 80)]))
    rounded = evenness(cap([(100, 115), (214, 115), (329, 133)]))   # touching rows whose rounded rectangles overlap by 1 px
    uneven = evenness(cap([(100, 80), (180, 80), (300, 80)]))
    check("touching siblings are measured for even spacing", flush is not None and flush["value"] == 1.0, flush)
    check("a 1 px rounding overlap no longer drops the group from the measurement", rounded is not None and rounded["value"] == 1.0, rounded)
    check("genuinely uneven gaps are still found", uneven is not None and uneven["value"] == 0.0, uneven)
    D = load("dept")
    def metric(i, screen, vp): return {"area": i.split(".")[0], "id": i, "title": i, "value": 1.0, "samples": 1, "evidence": "measured", "screen": screen, "viewport": vp}
    before = {"method": "m", "findings": [], "gallery": [], "metrics": [metric("controls.primary", "Compendium", "narrow"), metric("spacing.scale", "Atlas", "desktop"), metric("layout.alignment", "Settings", "desktop")]}
    after = {"method": "m", "findings": [], "gallery": [], "metrics": [metric("spacing.scale", "Atlas", "desktop"), metric("layout.alignment", "Settings", "desktop")]}
    reason = "At 320 px the form is taller than the first screen, so no filled action is in view for this metric."
    out = os.path.join(ws, "cmp")
    c0 = D.compare(before, after, out)
    check("a metric that is gone is lost coverage", c0["coverage_lost"] == ["controls.primary (Compendium @ narrow)"] and c0["coverage_excluded"] == [])
    c1 = D.compare(before, after, out, [{"metric": "controls.primary", "screen": "Compendium", "viewport": "narrow", "reason": reason}])
    check("a documented exclusion lists it as excluded, with its reason, instead of lost", c1["coverage_lost"] == [] and c1["coverage_excluded"] == [{"check": "controls.primary (Compendium @ narrow)", "reason": reason}])
    c2 = D.compare(before, after, out, [{"metric": "controls.primary", "screen": "Compendium", "viewport": "desktop", "reason": reason}])
    check("an exclusion covers one viewport only: another stays lost and the exclusion is stale", c2["coverage_lost"] == ["controls.primary (Compendium @ narrow)"] and c2["exclusions_stale"] == ["controls.primary (Compendium @ desktop)"])
    c3 = D.compare(before, before, out, [{"metric": "controls.primary", "screen": "Compendium", "viewport": "narrow", "reason": reason}])
    check("an exclusion for a metric that is measured again is stale", c3["exclusions_stale"] == ["controls.primary (Compendium @ narrow)"] and c3["coverage_lost"] == [])
    c4 = D.compare(before, after, out, [{"metric": "controls.primary", "screen": "Compendium", "viewport": "narrow", "reason": "n/a"}, {"metric": "controls.primary", "reason": reason}, "controls.primary"])
    check("a vague, wildcard or malformed exclusion is refused and excuses nothing", len(c4["exclusions_refused"]) == 3 and c4["coverage_lost"] == ["controls.primary (Compendium @ narrow)"], c4["exclusions_refused"])
except ImportError as e:
    print(f"SKIP the verifier checks: {e} (they need the Studio runtime's numpy and Pillow)", flush=True)

srv.shutdown(); shutil.rmtree(ws, ignore_errors=True)
bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
