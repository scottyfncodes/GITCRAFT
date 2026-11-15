"""Independent link checks, kept apart from what the catalogue claims (data/checks.json).

One GET of each API's documentation link, from wherever this runs (the scheduled workflow: the GITCRAFT sandbox has no
network). What it establishes is narrow and is reported as exactly that: on this date, from this machine, the link
answered (or did not), over TLS (or not), and ended on this host. It is not uptime, not reliability, not pricing, and a
refusal (403, 429, a bot wall) is "refused the check", never "down"."""
import concurrent.futures, json, os, ssl, time, urllib.error, urllib.parse, urllib.request
from . import DATA
from .catalog import now

CHECKS = os.path.join(DATA, "checks.json")
STATUS = {"reachable": "The documentation link answered", "moved": "The documentation link now leads to a different site",
          "refused": "The site refused the automated check (this says nothing about whether it works)", "missing": "The documentation link returned an error page",
          "unreachable": "The documentation link did not answer"}


def classify(code, start_host, final_host):
    """HTTP result → a status. 401/403/405/429 and other refusals are not evidence of anything."""
    reg = lambda h: ".".join((h or "").lower().split(":")[0].split(".")[-2:])
    if code is None: return "unreachable"
    if code in (401, 403, 405, 406, 409, 418, 429, 451, 999) or 520 <= code <= 530: return "refused"
    if code in (404, 410) or 500 <= code < 600: return "missing"
    if 200 <= code < 400: return "moved" if reg(start_host) != reg(final_host) else "reachable"
    return "refused"


def check_one(url, timeout=12, opener=None):
    """One documentation link → {status, http, final_host, tls, error}. Reads nothing but the status line and headers."""
    host = urllib.parse.urlsplit(url).netloc
    out = {"status": "unreachable", "http": None, "final_host": None, "tls": None, "error": None}
    req = urllib.request.Request(url, headers={"User-Agent": "gitcraft-api-discovery link check", "Accept": "text/html,application/json;q=0.9,*/*;q=0.5"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=timeout) as r:
            final = urllib.parse.urlsplit(r.geturl())
            out.update(http=r.status, final_host=final.netloc.lower(), tls=final.scheme == "https")
    except urllib.error.HTTPError as e:
        out.update(http=e.code, final_host=urllib.parse.urlsplit(e.geturl() or url).netloc.lower(), tls=str(e.geturl() or url).startswith("https"))
    except (urllib.error.URLError, ssl.SSLError, OSError, ValueError) as e:
        reason = getattr(e, "reason", e)
        out["error"] = f"{type(reason).__name__}: {str(reason)[:80]}"
        if isinstance(reason, ssl.SSLError) or "CERTIFICATE" in str(reason).upper(): out["tls"] = False; out["error"] = "TLS certificate problem: " + str(reason)[:80]
    out["status"] = classify(out["http"], host, out["final_host"])
    return out


def run(entries, workers=24, timeout=12, opener=None, limit=None):
    """Check every entry's link (or the first `limit`). → the checks document. One request per API, no retries."""
    todo = [e for e in entries if e.get("url")][:limit]
    res = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(check_one, e["url"], timeout, opener): e for e in todo}
        for f in concurrent.futures.as_completed(futs):
            e = futs[f]
            try: res[e["id"]] = dict(f.result(), url=e["url"])
            except Exception as x: res[e["id"]] = {"status": "unreachable", "http": None, "final_host": None, "tls": None, "error": f"{type(x).__name__}"[:80], "url": e["url"]}
    counts = {}
    for r in res.values(): counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"schema": 1, "checked": now(), "method": "one GET of the documentation link per API; status line and final address only",
            "means": "the link answered at that moment from the checking machine; not uptime, reliability, pricing or terms", "counts": counts, "of": len(todo), "results": res}


def load(path=None):
    try:
        C = json.load(open(path or CHECKS))
        if isinstance(C, dict) and isinstance(C.get("results"), dict): return C
    except (OSError, ValueError):
        pass
    return {"schema": 1, "checked": None, "counts": {}, "of": 0, "results": {}}


def save(C, path=None):
    p = path or CHECKS; os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w") as f: json.dump(C, f, separators=(",", ":"))
    os.replace(p + ".tmp", p)


def plausible(C):
    """A check run made without working network marks nearly everything unreachable: that is a fact about the checker,
    so such a run is never published over a good one."""
    n = C.get("of") or 0
    return n > 0 and (C["counts"].get("unreachable", 0) / n) < 0.5


def for_entry(C, e):
    """The check that belongs to this entry (same id and same link), or None."""
    r = (C.get("results") or {}).get(e["id"])
    return dict(r, checked=C.get("checked")) if r and r.get("url") == e["url"] else None
