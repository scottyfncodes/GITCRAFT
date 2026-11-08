"""LIVE VERIFICATION: is the deployed URL serving this release, and does it work for a visitor?

    python3 -m production verify-live <production> <url> [--submit]

Run by the agent from its own shell, outside the tool sandbox, after it deployed (the sandbox has no network).
Through the session's HTTPS proxy when there is one; TLS is always verified.

  same build      the live entry page is byte-for-byte the released entry page (whitespace-normalised), and every
                  local file it references (scripts, styles, icons, manifest) is served with the same bytes. A page
                  behind a login wall (e.g. Vercel deployment protection) or an older deployment fails here.
  icons           the manifest and the icons it lists are reachable at their sizes (App Icon Studio, deployed)
  analytics       HaveAnApp Pulse is in the live page and its script answers, when the blueprint chose it
  in a browser    Chromium on phone and desktop: it loads, no page errors, no failed requests, the byline is visible
                  when attribution is required

The record (tasks/release.deploy/live-check.json) has the shape production_submit's deployment gate accepts:
{department, action, status, request: {url}, checks}. A deployment is recorded live only when it passes."""
import hashlib, json, os, re, shutil, subprocess, tempfile, time, urllib.error, urllib.parse, urllib.request
from . import HERE, store, icons

UA = "GITCRAFT-live-check/1.0"


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e: return e.code, e.read() or b"", url
    except (urllib.error.URLError, OSError) as e: return None, str(e).encode(), url


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


def verify(prod, url, browser=True):
    proj = prod["spec"]["project"]["path"]
    out_dir = os.path.join(prod["store"], "tasks", "release.deploy"); os.makedirs(out_dir, exist_ok=True)
    checks = []
    add = lambda name, ok, detail=None, **kw: checks.append(dict({"name": name, "ok": bool(ok), "detail": detail}, **kw))
    local_ok = os.environ.get("GITCRAFT_LIVE_ALLOW_LOCAL") == "1" and re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?/", url or "")
    if not (re.match(r"^https://", url or "") or local_ok): add("the URL is an https:// address", False, url)
    entry = _entry(proj) if proj else None
    status, body, final = _get(url)
    add("the live URL answers 200", status == 200, f"HTTP {status}" + (f" (redirected to {final})" if final != url else ""))
    if entry and status == 200:
        local = open(entry, "rb").read()
        same = _norm(local) == _norm(body)
        why = None
        if not same:
            t = re.search(rb"<title>(.*?)</title>", body, re.I | re.S)
            title = t.group(1).decode(errors="ignore").strip()[:80] if t else ""
            why = (f"the live page is a login wall ('{title}'): deployment protection is on, so visitors don't get the app" if re.search(r"log ?in|sign ?in|authenticat", title, re.I)
                   else f"the live page differs from the released {os.path.relpath(entry, proj)} (live title '{title}'): an older or different deployment")
        add(f"serves this release: the live page equals {os.path.relpath(entry, proj)}", same, why)
        if same:
            refs, bad = _refs(local.decode(errors="ignore")), []
            for ref in refs[:40]:
                lp = _local(proj, entry, ref)
                if not lp: continue
                st, data, _ = _get(urllib.parse.urljoin(final, ref))
                if st != 200: bad.append(f"{ref}: HTTP {st}")
                elif hashlib.sha256(data).hexdigest() != hashlib.sha256(open(lp, "rb").read()).hexdigest(): bad.append(f"{ref}: different bytes")
            add("every file the page references is served, byte-identical", not bad, bad[:10] or None, measured=f"{len(refs)} references")
            man = next((r for r in re.findall(r"""<link\b[^>]*rel=["']?manifest[^>]*>""", local.decode(errors="ignore"), re.I)), None)
            if man:
                href = re.search(r"""href=["']?([^"'\s>]+)""", man).group(1)
                st, data, murl = _get(urllib.parse.urljoin(final, href))
                try:
                    mj = json.loads(data); missing = []
                    for ic in mj.get("icons", []):
                        s2, png, _ = _get(urllib.parse.urljoin(murl, ic["src"]))
                        if s2 != 200: missing.append(f"{ic['src']}: HTTP {s2}"); continue
                        want = str(ic.get("sizes", "")).split("x")[0]
                        if png[:8] == icons.SIG and want.isdigit():
                            w = int.from_bytes(png[16:20], "big")
                            if w != int(want): missing.append(f"{ic['src']}: {w}px, manifest says {want}")
                    add("the deployed manifest and its icons are reachable at their sizes", st == 200 and not missing, missing or None)
                except ValueError: add("the deployed manifest reads as JSON", False, f"HTTP {st}")
    elif not entry:
        add("a released entry page exists to compare with", False, "no index.html in the project or its build folder")
    if (prod["spec"].get("analytics") or {}).get("provider") == "pulse":
        m = re.search(rb"""<script[^>]+src=["']([^"']*haveanapp-pulse[^"']*)["']""", body or b"")
        st = _get(m.group(1).decode())[0] if m else None
        add("HaveAnApp Pulse is on the live page and its script answers", bool(m) and st == 200, None if m else "no Pulse script tag", measured=f"HTTP {st}" if m else None)
    if browser:
        b = browser_check(url, out_dir)
        if b.get("error"): add("opened in a real browser (phone and desktop)", False, b["error"])
        for v in b.get("viewports", []):
            add(f"{v['viewport']}: loads with no page errors or failed requests", not v.get("error") and v.get("status") == 200 and not v["page_errors"] and not v["failed"],
                v.get("error") or (v["page_errors"] + v["failed"])[:6] or None, screenshot=v.get("screenshot"))
            if (prod["spec"].get("attribution") or {}).get("required"):
                add(f"{v['viewport']}: the HaveAnApp byline is visible", bool(v.get("byline")), v.get("byline"))
    rec = {"department": "production", "action": "verify_live", "status": "ok" if checks and all(c["ok"] for c in checks) else "failed",
           "request": {"url": url}, "checks": checks, "at": store.now(), "production": prod["id"]}
    p = os.path.join(out_dir, "live-check.json")
    with open(p, "w") as f: json.dump(rec, f, indent=1)
    rec["record"] = p
    return rec
