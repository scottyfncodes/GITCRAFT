"""LIVE VERIFICATION: is the deployed URL serving this release, and does it work for a visitor?

    python3 -m production verify-live <production> <url> [--submit]

Run by the agent from its own shell, outside the tool sandbox, after it deployed (the sandbox has no network).
Through the session's HTTPS proxy when there is one; TLS is always verified.

  this release    build provenance, not file names. Bundlers name files by content hash and two build machines can
                  legitimately produce different bundles, so a hashed name that differs between the local build and
                  the deployment is never a failure by itself. Evidence, strongest first:
                    * the deployment's commit (--commit, e.g. Vercel's githubCommitSha, or a commit/version meta tag in
                      the live page) equals the project's HEAD: PASS; a different commit: BLOCKER (older deployment)
                    * the live entry page equals the released one once content-hashed names are masked: PASS
                    * it differs and nothing proves which commit is live: UNVERIFIED (never READY, never a defect);
                      a different <title>: BLOCKER. A login wall (deployment protection): BLOCKER.
  assets          every same-origin file the LIVE page references loads (200, not empty): a failure is a BLOCKER.
                  Files with stable names that the release ships verbatim (public/, or an unbuilt site) must be
                  byte-identical; build outputs are compared only when that is meaningful.
  icons           the manifest and the icons it lists are reachable at their sizes (App Icon Studio, deployed)
  analytics       HaveAnApp Pulse is in the live page and its script answers, when the blueprint chose (or Discovery
                  found) it; a missing data-app is a metadata mismatch (ADVISORY), a missing script a BLOCKER
  in a browser    Chromium on phone and desktop: it loads, no page errors, no failed required requests, the byline
                  is visible when attribution is required. A third-party host the verifier cannot reach (proxy, DNS)
                  or that answers 5xx is UNVERIFIED with its cause (studio/core/netclass.py), never an application
                  failure; whether the app stayed usable without it is recorded separately (resilience), and is never
                  presented as proof that the live integration works. Console errors are recorded: those the blocked
                  hosts explain or a documented exception covers (spec.verification.console_error_exceptions) are
                  listed as such; the rest are ADVISORY here (page exceptions and failed required assets are BLOCKERS).

Every check carries a category (production/verification.py): BLOCKER, UNVERIFIED, ADVISORY or PASS. The record's
status is ok (nothing blocking or unverified), failed (a BLOCKER) or incomplete (DEPLOYED · VERIFICATION INCOMPLETE
when the URL is serving this release).

The record (tasks/release.deploy/live-check.json) has the shape production_submit's deployment gate accepts:
{department, action, status, request: {url}, checks, deployment, hosts_ok}. A deployment is recorded live only when it
passes."""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request
from . import HERE, store, icons, verification as V

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "studio")) if os.path.join(os.path.dirname(HERE), "studio") not in sys.path else None
from core import netclass  # noqa: E402  (studio/core/netclass.py: standard library only)

UA = "GITCRAFT-live-check/1.0"


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e: return e.code, e.read() or b"", url
    except (urllib.error.URLError, OSError, ValueError) as e: return None, str(e).encode(), url


def _norm(b):
    return re.sub(rb"\s+", b" ", b).strip()


def _entry(project):
    for d in ("dist", "build", "out", "public", ""):
        p = os.path.join(project, d, "index.html")
        if os.path.isfile(p): return p
    return None


def _refs(html):
    out = []
    for m in re.finditer(r"""<(?:script|link|img)\b[^>]*?\b(?:src|href)\s*=\s*["']([^"'#]+)""", html, re.I):
        u = m.group(1)
        if not re.match(r"^[a-z]+:|^//|^data:", u, re.I): out.append(u)
    return out


def _local(project, entry, ref):
    clean = urllib.parse.unquote(ref.split("?")[0])
    base = os.path.dirname(entry)
    cands = [os.path.join(base, clean.lstrip("/")), os.path.join(project, "public", clean.lstrip("/")), os.path.join(project, clean.lstrip("/"))] \
        if clean.startswith("/") else [os.path.normpath(os.path.join(base, clean))]
    return next((c for c in cands if os.path.isfile(c)), None)


def _playwright():
    """(module, chromium) the way the Studio finds them (studio/core/deps.py: env, studio runtime, /opt, the global npm root)."""
    import importlib, sys
    sd = os.path.join(os.path.dirname(HERE), "studio")
    if sd not in sys.path: sys.path.insert(0, sd)
    try: return importlib.import_module("core.deps").resolve_playwright()
    except Exception: return None, None


def browser_check(url, out_dir):
    """Chromium on phone + desktop (production/web/verify_live.mjs)."""
    if not shutil.which("node"): return {"error": "node is not installed here"}
    pw, chrome = _playwright()
    d = tempfile.mkdtemp(prefix="gitcraft-live-"); reqp, resp = os.path.join(d, "req.json"), os.path.join(d, "res.json")
    json.dump({"url": url, "out_dir": out_dir, "_result": resp}, open(reqp, "w"))
    try:
        env = dict(os.environ, **{k: v for k, v in (("PLAYWRIGHT_MODULE", pw), ("CHROMIUM_PATH", chrome)) if v})
        subprocess.run(["node", os.path.join(HERE, "web", "verify_live.mjs"), reqp], capture_output=True, text=True, timeout=240, env=env)
        return json.load(open(resp))
    except (subprocess.TimeoutExpired, OSError, ValueError) as e:
        return {"error": f"the browser check did not finish: {e}"}
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------- build provenance (not file names)
_HASHSEG = re.compile(r"(?<=[._-])[A-Za-z0-9_]{6,}(?=\.[a-z0-9]{1,6}(?:[?#\"'\s]|$))")
_IDSEG = re.compile(r"(?<=/)[A-Za-z0-9_-]{8,}(?=/)")


def _hashy(tok):
    return len(tok) >= 6 and (bool(re.search(r"\d", tok)) or (bool(re.search(r"[a-z]", tok)) and bool(re.search(r"[A-Z]", tok))))


def unhash(text):
    """Mask content-hashed file names (index-BxY3k2Qa.js, main.3f2a1b9c.css) and build-id path segments
    (/_next/static/<buildId>/): two legitimate builds of one commit can differ exactly there."""
    text = _HASHSEG.sub(lambda m: "*" if _hashy(m.group(0)) else m.group(0), text)
    text = _IDSEG.sub(lambda m: "*" if _hashy(m.group(0)) and re.search(r"\d", m.group(0)) else m.group(0), text)
    text = re.sub(r"""\s(?:nonce|integrity)=["'][^"']*["']""", "", text)   # per-build/per-request attributes
    return re.sub(r"\s+", " ", text).strip()


def is_hashed(ref):
    name = os.path.basename(urllib.parse.urlsplit(ref).path)
    m = re.search(r"[._-]([A-Za-z0-9_]{6,})\.[a-z0-9]{1,6}$", name)
    return bool(m and _hashy(m.group(1)))


def _git_head(project):
    try:
        r = subprocess.run(["git", "-C", project, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
        return r.stdout.strip() if r.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", r.stdout.strip()) else None
    except (OSError, subprocess.SubprocessError): return None


def page_commit(html):
    """A commit SHA the deployment publishes about itself (<meta name="commit|git-commit|build-commit|version|revision">)."""
    m = re.search(r"""<meta\b[^>]*name=["'](?:git[-_]?commit|build[-_]?commit|commit(?:[-_]sha)?|revision|version|vercel[-_]git[-_]commit[-_]sha)["'][^>]*>""", html, re.I)
    if not m: return None
    c = re.search(r"""content=["']([0-9a-f]{7,40})["']""", m.group(0), re.I)
    return c.group(1).lower() if c else None


def _same_commit(a, b):
    a, b = (a or "").lower(), (b or "").lower()
    return len(a) >= 7 and len(b) >= 7 and (a.startswith(b) or b.startswith(a))


def _title(b):
    t = re.search(rb"<title>(.*?)</title>", b or b"", re.I | re.S)
    return t.group(1).decode(errors="ignore").strip()[:80] if t else ""


def _unreachable(status, body, url, what):
    """A request that got no usable answer: UNVERIFIED when the verifier's network is the cause, else BLOCKER."""
    if status is None and netclass.SANDBOX.search(body.decode(errors="ignore") if isinstance(body, bytes) else str(body)):
        return V.make(what, V.UNVERIFIED, f"the verifier could not reach {url}: {body[:160].decode(errors='ignore') if isinstance(body, bytes) else body}",
                      cause="sandbox_network", host=netclass.host(url))
    return V.make(what, V.BLOCKER, f"HTTP {status}" if status is not None else (body[:160].decode(errors="ignore") if isinstance(body, bytes) else str(body)))


def verify(prod, url, browser=True, deployed_commit=None):
    spec = prod["spec"]; proj = spec["project"]["path"]
    out_dir = store.task_dir(prod, "release.deploy")
    policy = spec.get("verification") or {}
    checks, dep, hosts_ok = [], {"answers": None, "serving": None, "evidence": None}, set()
    add = checks.append
    local_ok = os.environ.get("GITCRAFT_LIVE_ALLOW_LOCAL") == "1" and re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?/", url or "")
    if not (re.match(r"^https://", url or "") or local_ok): add(V.make("the URL is an https:// address", V.BLOCKER, url))
    entry = _entry(proj) if proj else None
    status, body, final = _get(url)
    if status == 200:
        dep["answers"] = True
        add(V.make("the live URL answers 200", V.PASS, "HTTP 200" + (f" (redirected to {final})" if final != url else "")))
    else:
        c = _unreachable(status, body, url, "the live URL answers 200"); add(c)
        dep.update(answers=False, cause=c.get("cause"), detail=c.get("detail"))
    live_html = body.decode(errors="ignore") if status == 200 else ""
    if status == 200:
        title = _title(body)
        if re.search(r"log ?in|sign ?in|authenticat", title, re.I) and not (entry and _title(open(entry, "rb").read()) == title):
            add(V.make("the live page is the app, not a login wall", V.BLOCKER,
                       f"the live page is a login wall ('{title}'): deployment protection is on, so visitors don't get the app"))
            dep["serving"] = False
        else:
            _provenance(proj, entry, body, title, deployed_commit, add, dep)
            _assets(proj, entry, final, live_html, dep, add)
            _manifest(final, live_html, add)
    _analytics(spec, live_html, add)
    if browser and status == 200:
        _browser(prod, spec, url, out_dir, policy, add, hosts_ok)
    elif browser:
        add(V.make("opened in a real browser (phone and desktop)", V.UNVERIFIED if dep.get("cause") == "sandbox_network" else V.BLOCKER,
                   "the URL did not answer, so no browser check ran", cause=dep.get("cause")))
    st = V.status_of(checks)
    if st == "ok" and dep.get("serving") is None: dep["serving"] = True
    rec = {"department": "production", "action": "verify_live", "status": st, "request": {"url": url}, "checks": checks, "at": store.now(),
           "production": prod["id"], "deployment": dep, "hosts_ok": sorted(hosts_ok), "summary": V.summary(checks),
           "release_status": "NOT READY" if st == "failed" else ("DEPLOYED · VERIFICATION INCOMPLETE" if dep.get("serving") else "VERIFICATION INCOMPLETE")
           if st == "incomplete" else "LIVE · VERIFIED"}
    p = os.path.join(out_dir, "live-check.json")
    with open(p, "w") as f: json.dump(rec, f, indent=1)
    rec["record"] = p
    return rec


def _provenance(proj, entry, body, title, deployed_commit, add, dep):
    head = _git_head(proj) if proj else None
    live_commit = (deployed_commit or "").strip().lower() or page_commit(body.decode(errors="ignore"))
    commit_ok = None
    if head and live_commit:
        commit_ok = _same_commit(head, live_commit)
        add(V.make("build provenance: the deployment was built from this release's commit", V.PASS if commit_ok else V.BLOCKER,
                   f"deployed {live_commit[:12]}, release {head[:12]}" + ("" if commit_ok else ": an older or different deployment"),
                   measured=live_commit[:12]))
        dep["commit"] = {"deployed": live_commit[:40], "release": head, "source": "--commit" if deployed_commit else "page meta"}
        if not commit_ok: dep["serving"] = False; return
    if not entry:
        if commit_ok: dep.update(serving=True, evidence=f"commit {live_commit[:12]}")
        else: add(V.make("a released entry page or commit provenance identifies this release", V.UNVERIFIED,
                         "no index.html in the project or its build folder, and no deployed commit to compare (pass --commit)", cause="no_provenance"))
        return
    local = open(entry, "rb").read(); rel = os.path.relpath(entry, proj)
    if _norm(local) == _norm(body):
        add(V.make(f"serves this release: the live page equals {rel}", V.PASS)); dep.update(serving=True, evidence=f"entry page identical to {rel}"); return
    lu, bu = unhash(local.decode(errors="ignore")), unhash(body.decode(errors="ignore"))
    if lu == bu:
        n = len(set(_refs(local.decode(errors="ignore"))) ^ set(_refs(body.decode(errors="ignore"))))
        add(V.make(f"serves this release: the live page equals {rel} once content-hashed names are masked", V.PASS,
                   f"{n // 2 or n} hashed asset name(s) differ between the local and the deployed build (nondeterministic bundling): not a failure by itself"))
        dep.update(serving=True, evidence=f"entry page equal to {rel} modulo content hashes" + (f"; commit {live_commit[:12]}" if commit_ok else "")); return
    if commit_ok:
        add(V.make(f"the live page matches the local {rel}", V.ADVISORY, "differs from the local build, but the deployment was built from this commit "
                   "(build environments legitimately differ: environment variables, bundler versions)"))
        dep.update(serving=True, evidence=f"commit {live_commit[:12]}"); return
    ltitle = _title(local)
    if ltitle and title and ltitle != title:
        add(V.make(f"serves this release: the live page equals {rel}", V.BLOCKER,
                   f"the live page differs from the released {rel} (live title '{title}', release '{ltitle}'): an older or different deployment"))
        dep["serving"] = False; return
    add(V.make(f"serves this release: the live page equals {rel}", V.UNVERIFIED,
               f"the live page differs from the local {rel} beyond content hashes and no deployed commit was given to prove which build is live "
               "(pass --commit with the deployment's commit SHA)", cause="no_provenance"))


def _assets(proj, entry, final, live_html, dep, add):
    refs = list(dict.fromkeys(_refs(live_html)))[:60]
    built = bool(entry) and os.path.basename(os.path.dirname(entry)) in ("dist", "build", "out")
    fails, unv, diff_verbatim, diff_build, same = [], [], [], [], 0
    for ref in refs:
        st, data, _ = _get(urllib.parse.urljoin(final, ref))
        if st != 200 or not data:
            if st is None and netclass.SANDBOX.search(data.decode(errors="ignore")): unv.append(f"{ref}: {data[:100].decode(errors='ignore')}")
            else: fails.append(f"{ref}: HTTP {st}" + (" (empty)" if st == 200 else ""))
            continue
        if is_hashed(ref) or not proj: continue   # the name carries the content hash: availability is the evidence
        lp = _local(proj, entry, ref) if entry else None
        if not lp: continue
        if hashlib.sha256(data).digest() == hashlib.sha256(open(lp, "rb").read()).digest(): same += 1; continue
        verbatim = not built or os.path.isfile(os.path.join(proj, "public", urllib.parse.unquote(ref.split("?")[0]).lstrip("/")))
        (diff_verbatim if verbatim else diff_build).append(f"{ref}: different bytes")
    add(V.make("every file the live page references loads (200, not empty)", V.BLOCKER if fails else V.UNVERIFIED if unv else V.PASS,
               (fails + unv)[:10] or None, measured=f"{len(refs)} references", **({"cause": "sandbox_network"} if unv and not fails else {})))
    if diff_verbatim or same:
        add(V.make("files with stable names are byte-identical to the release", V.BLOCKER if diff_verbatim else V.PASS, diff_verbatim[:10] or None,
                   measured=f"{same} identical"))
    if diff_build:
        add(V.make("build outputs with stable names match the local build", V.ADVISORY if dep.get("serving") else V.UNVERIFIED, diff_build[:10],
                   **({} if dep.get("serving") else {"cause": "no_provenance"})))


def _manifest(final, live_html, add):
    man = next(iter(re.findall(r"""<link\b[^>]*rel=["']?manifest[^>]*>""", live_html, re.I)), None)
    if not man: return
    href = re.search(r"""href=["']?([^"'\s>]+)""", man).group(1)
    st, data, murl = _get(urllib.parse.urljoin(final, href))
    if st != 200: add(_unreachable(st, data, murl, "the deployed manifest is reachable")); return
    try: mj = json.loads(data)
    except ValueError: add(V.make("the deployed manifest reads as JSON", V.BLOCKER, f"HTTP {st}")); return
    missing = []
    for ic in mj.get("icons", []):
        s2, png, _ = _get(urllib.parse.urljoin(murl, ic["src"]))
        if s2 != 200: missing.append(f"{ic['src']}: HTTP {s2}"); continue
        want = str(ic.get("sizes", "")).split("x")[0]
        if png[:8] == icons.SIG and want.isdigit():
            w = int.from_bytes(png[16:20], "big")
            if w != int(want): missing.append(f"{ic['src']}: {w}px, manifest says {want}")
    add(V.make("the deployed manifest and its icons are reachable at their sizes", V.BLOCKER if missing else V.PASS, missing or None))


def _analytics(spec, live_html, add):
    if (spec.get("analytics") or {}).get("provider") != "pulse" or not live_html: return
    tag = re.search(r"""<script\b[^>]*src=["']([^"']*haveanapp-pulse[^"']*)["'][^>]*>""", live_html)
    if not tag:
        add(V.make("HaveAnApp Pulse is on the live page and its script answers", V.BLOCKER, "no Pulse script tag (the declared analytics integration is missing)")); return
    st, data, _ = _get(tag.group(1))
    if st == 200: add(V.make("HaveAnApp Pulse is on the live page and its script answers", V.PASS, measured="HTTP 200"))
    else: add(_unreachable(st, data, tag.group(1), "HaveAnApp Pulse is on the live page and its script answers"))
    if "data-app=" not in tag.group(0):
        add(V.make("the Pulse tag names the app (data-app)", V.ADVISORY, "configuration metadata: counts arrive unlabelled; add data-app"))


def _browser(prod, spec, url, out_dir, policy, add, hosts_ok):
    b = browser_check(url, out_dir)
    if b.get("error"):   # Playwright or Chromium missing, or it did not finish: the verifier's limitation, not the app's
        add(V.make("opened in a real browser (phone and desktop)", V.UNVERIFIED, b["error"], cause="verifier_unavailable")); return
    origin = netclass.host(url)
    for v in b.get("viewports", []):
        vp = v["viewport"]
        hosts_ok.update(h for h in v.get("hosts_ok") or [] if h and h != origin)
        if v.get("error"):
            cause = "sandbox_network" if netclass.SANDBOX.search(v["error"]) else None
            add(V.make(f"{vp}: loads with no page errors or failed required requests", V.UNVERIFIED if cause else V.BLOCKER, v["error"], cause=cause)); continue
        req = [netclass.classify_request(*netclass.parse_failed(f), origin_host=origin) for f in v.get("failed") or []]
        bad = [r for r in req if r["category"] == V.BLOCKER]
        unv = [r for r in req if r["category"] == V.UNVERIFIED]
        ok_load = v.get("status") == 200 and not v["page_errors"] and not bad
        add(V.make(f"{vp}: loads with no page errors or failed required requests", V.PASS if ok_load else V.BLOCKER,
                   None if ok_load else (v["page_errors"] + [f"{r['status'] or r['error']} {r['url']}" for r in bad])[:6] or f"HTTP {v.get('status')}",
                   screenshot=v.get("screenshot")))
        for cause in sorted({r["cause"] for r in unv}):
            hs = sorted({r["host"] for r in unv if r["cause"] == cause})
            why = {"sandbox_network": "the verifier's network could not reach them (proxy/DNS/sandbox): not evidence about the app",
                   "external_service": "the external service answered with an error or throttled: a third-party outage, not an application defect",
                   "no_answer": "no answer and no network explanation: re-check from an unrestricted network"}.get(cause, cause)
            for h in hs:
                add(V.make(f"{vp}: external service {h} verified live", V.UNVERIFIED, why, cause=cause, host=h))
        if unv and ok_load and (v.get("text") or "").strip():
            add(V.make(f"{vp}: stays usable while {', '.join(sorted({r['host'] for r in unv}))[:120]} is unreachable (resilience)", V.PASS,
                       "no page exception, the page rendered text; this shows resilience only and is not proof that the live integration works"))
        cons = netclass.classify_console(v.get("console_errors") or [], v.get("console_error_sources"), [r["url"] for r in unv],
                                         policy.get("console_error_exceptions"))
        if cons["unexplained"]:
            add(V.make(f"{vp}: no unexplained console errors", V.ADVISORY, cons["unexplained"][:4]))
        if cons["excepted"] or cons["sandbox"]:
            add(V.make(f"{vp}: console errors explained by unreachable services or documented exceptions", V.PASS,
                       [f"{e['text'][:120]} — {e.get('reason') or 'blocked host ' + ', '.join(e.get('hosts') or [])}" for e in cons["sandbox"] + cons["excepted"]][:6]))
        if cons["refused_exceptions"]:
            add(V.make("console-error exceptions are narrow and documented", V.ADVISORY, [r["why"] for r in cons["refused_exceptions"]][:4]))
        if (spec.get("attribution") or {}).get("required"):
            add(V.make(f"{vp}: the HaveAnApp byline is visible", V.PASS if v.get("byline") else V.BLOCKER, v.get("byline")))
