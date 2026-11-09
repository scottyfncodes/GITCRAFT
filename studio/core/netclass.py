"""Who broke: the application, the external service, or the verifier's own network?

Shared by TestCraft (smoke tests, served locally with every other host blocked) and the Production Director's
live check (production/live.py, through the session's proxy). Standard library only.

A browser check sees three kinds of trouble that look alike and mean different things:

  sandbox_network        the verifier could not reach a host: the harness aborted it (TestCraft serves only the
                         game's own folder), the proxy refused it, DNS failed, the tunnel failed. Nothing about the
                         application is known: the integration is UNVERIFIED, never a defect.
  external_service       the external host answered with 5xx (or 429): the service is failing or throttling right
                         now. Not an application defect; the integration is UNVERIFIED.
  application            the application's own origin failed (a missing script, a 404 on its own asset), a page
                         exception, or an external call that the host answered with a client error (4xx other than
                         auth/throttling): a BLOCKER.

Console errors follow the same split. A console error is explained (not a failure) only when it is
  * the browser's own report of a request that the verifier blocked (same URL, or names a blocked host), or
  * matched by an explicit, documented exception: {pattern, reason[, host]}: a regex that cannot match everything,
    with a reason a person wrote; with `host`, it applies only in a run where that host was unreachable.
    Exceptions never apply to page exceptions or to failed required assets.
Everything else stays a console error (TestCraft fails on it unless the caller downgrades it to an advisory).
"""
import re
import urllib.parse

SANDBOX = re.compile(r"ERR_FAILED|ERR_TUNNEL_CONNECTION_FAILED|ERR_PROXY_CONNECTION_FAILED|ERR_NAME_NOT_RESOLVED|ERR_NAME_RESOLUTION_FAILED|"
                     r"ERR_INTERNET_DISCONNECTED|ERR_ADDRESS_UNREACHABLE|ERR_BLOCKED_BY_CLIENT|ERR_CONNECTION_REFUSED|ERR_CONNECTION_RESET|"
                     r"ERR_CERT_AUTHORITY_INVALID|NS_ERROR_UNKNOWN_HOST|request blocked|no rule allows host|Tunnel connection failed|"
                     r"Name or service not known|getaddrinfo|EAI_AGAIN|ENOTFOUND|Temporary failure in name resolution|"
                     r"blocked by the (?:sandbox|verifier|harness)", re.I)
BROWSER_NET_MSG = re.compile(r"^Failed to load resource|net::ERR_|Failed to fetch|NetworkError when attempting to fetch|Load failed|"
                             r"TypeError: (?:Failed to fetch|NetworkError|Load failed)|ERR_FAILED", re.I)
REQUIRED_EXT = re.compile(r"\.(?:m?js|css|wasm|html?)(?:$|\?)", re.I)


def host(url):
    try: return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError: return ""


def classify_request(url, status=None, error=None, origin_host="", proxied=True):
    """One failed request → {url, host, party, cause, category}.
    status: HTTP status when the host answered; error: the browser's/urllib's failure text when it did not."""
    h = host(url); first = bool(h) and (h == origin_host or h.endswith("." + origin_host) or origin_host.endswith("." + h)) if origin_host else False
    party = "first" if first else "third"
    if status is None:   # no answer: was it the verifier's network?
        cause = "sandbox_network" if SANDBOX.search(str(error or "")) else "no_answer"
    elif status in (401, 403, 407) and not first and proxied: cause = "sandbox_network"   # a proxy refusal reads as 403/407
    elif status == 429 or status >= 500: cause = "external_service" if not first else "application"
    else: cause = "application"
    if first: cat = "blocker" if cause == "application" or REQUIRED_EXT.search(url) and cause != "sandbox_network" else "unverified"
    else: cat = "blocker" if cause == "application" else "unverified"
    return {"url": url[:300], "host": h, "party": party, "status": status, "error": (str(error)[:160] if error else None), "cause": cause, "category": cat}


def parse_failed(line):
    """verify_live.mjs / TestCraft strings: '404 https://x/y' or 'failed https://x/y (net::ERR_FAILED)' → (url, status, error)."""
    m = re.match(r"^(\d{3}) (\S+)", line)
    if m: return m.group(2), int(m.group(1)), None
    m = re.match(r"^failed (\S+)(?: \((.*)\))?", line)
    if m: return m.group(1), None, m.group(2) or "request failed"
    return line, None, "unknown"


def validate_exceptions(exceptions):
    """→ (valid, refused). An exception needs a pattern that compiles and does not match everything, and a reason."""
    ok, bad = [], []
    for e in exceptions or []:
        if not isinstance(e, dict) or not e.get("pattern") or not str(e.get("reason") or "").strip():
            bad.append({"exception": e, "why": "an exception needs a pattern and a written reason"}); continue
        try: rx = re.compile(e["pattern"], re.I)
        except re.error as x: bad.append({"exception": e, "why": f"pattern does not compile: {x}"}); continue
        if rx.search("") is not None or rx.search("any error at all 0123") or rx.search("Uncaught TypeError: x is undefined"):
            bad.append({"exception": e, "why": "pattern is too broad (it matches any message): exceptions must name a specific error"}); continue
        ok.append(dict(e, _rx=rx))
    return ok, bad


def classify_console(errors, sources=None, blocked=None, exceptions=None):
    """Console errors → {unexplained, sandbox, excepted, refused_exceptions}.
    errors: texts; sources: the URL each error came from (same order, may be shorter); blocked: URLs the verifier
    blocked or that failed for network reasons; exceptions: [{pattern, reason, host?}]."""
    sources = list(sources or []); blocked = list(blocked or [])
    bhosts = {host(u) for u in blocked if host(u)}
    exc, refused = validate_exceptions(exceptions)
    out = {"unexplained": [], "sandbox": [], "excepted": [], "refused_exceptions": refused}
    for i, text in enumerate(errors or []):
        src = sources[i] if i < len(sources) else ""
        named = [h for h in bhosts if h and h in text]
        if (src and (src in blocked or host(src) in bhosts) and BROWSER_NET_MSG.search(text)) or named or (bhosts and BROWSER_NET_MSG.search(text) and SANDBOX.search(text)):
            out["sandbox"].append({"text": text, "source": src or None, "hosts": named or ([host(src)] if src else sorted(bhosts))}); continue
        # a host-scoped exception applies only in a run where that host really was unreachable
        hit = next((e for e in exc if e["_rx"].search(text) and (not e.get("host") or str(e["host"]).lower() in bhosts)), None)
        if hit: out["excepted"].append({"text": text, "reason": hit["reason"], "pattern": hit["pattern"], "host": hit.get("host")}); continue
        out["unexplained"].append(text)
    return out
