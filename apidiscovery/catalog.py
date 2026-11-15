"""The public-apis catalogue as a normalised local index.

The upstream is one Markdown README: `### Category` headings, each followed by a five-column table
(API | Description | Auth | HTTPS | CORS). It also carries a sponsor's block, sponsored rows with tracking links at
the top of some categories, and an MCP-servers table: none of those are catalogue entries.

Nothing here trusts the upstream. Every row is parsed defensively, a row that does not fit is listed in `skipped` with
the reason, values outside the known vocabulary become "unknown" (never a guess), duplicates are merged, and a refresh
that returns something that is not a plausible catalogue leaves the working copy exactly as it was."""
import hashlib, json, os, re, time, urllib.parse, urllib.request
from . import DATA, UPSTREAM, SOURCE

CATALOG = os.path.join(DATA, "catalog.json")
MIN_ENTRIES = 500          # the upstream has well over a thousand: fewer than this is a broken fetch, not a catalogue
ROW = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)\s]+)\)\s*\|")
TRACKING = re.compile(r"^(utm_[a-z]+|ref|referrer|source|campaign)$", re.I)
AUTH = {"": "none", "no": "none", "apikey": "apiKey", "oauth": "oauth", "x-mashape-key": "header", "user-agent": "header"}


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def clean_url(u):
    """(url without tracking parameters, had_tracking) or (None, False) when it is not an http(s) link."""
    u = (u or "").strip()
    try: p = urllib.parse.urlsplit(u)
    except ValueError: return None, False
    if p.scheme not in ("http", "https") or not p.netloc or re.search(r"[\s<>\"'`]", u): return None, False
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    kept = [(k, v) for k, v in q if not TRACKING.match(k)]
    return urllib.parse.urlunsplit((p.scheme, p.netloc.lower(), p.path, urllib.parse.urlencode(kept), "")), len(kept) != len(q)


def _text(s, n=300):
    """Catalogue text as plain text: no Markdown, no markup, no control characters, bounded."""
    s = re.sub(r"\[([^\]]*)\]\((?:[^()]|\([^()]*\))*\)", r"\1", s or "")
    s = re.sub(r"<[^>]*>", "", s).replace("`", "")
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f]", " ", s)).strip()[:n]


def _tri(v):
    v = _text(v, 20).lower()
    return "yes" if v == "yes" else "no" if v == "no" else "unknown"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60]


def parse(markdown):
    """README text → {"entries": [...], "skipped": [...], "categories": [...]}. Never raises on bad input."""
    entries, skipped, cats, cat, in_index = [], [], [], None, False
    for n, line in enumerate(str(markdown or "").splitlines(), 1):
        if line.startswith("## "):
            in_index = line.strip().lower() == "## index"; cat = None; continue
        if line.startswith("### "):
            cat = _text(line[4:], 60) if in_index else None
            if cat and cat not in cats: cats.append(cat)
            continue
        if not line.startswith("|") or line.startswith("|:") or line.startswith("| API"): continue
        m = ROW.match(line)
        if not cat:
            if m: skipped.append({"line": n, "name": _text(m.group(1), 60), "why": "outside a category (sponsor block or another table)"})
            continue
        if not m: skipped.append({"line": n, "why": "not a catalogue row", "text": _text(line, 80)}); continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5: skipped.append({"line": n, "name": _text(m.group(1), 60), "why": f"{len(cells)} columns, expected 5"}); continue
        url, tracked = clean_url(m.group(2))
        name = _text(m.group(1), 80)
        if not url or not name: skipped.append({"line": n, "name": name, "why": "no usable http(s) link" if name else "no name"}); continue
        raw_auth = _text(cells[2], 30)
        auth = AUTH.get(raw_auth.lower(), "unknown")
        https = _tri(cells[3])
        entries.append({"id": slug(f"{cat}-{name}"), "name": name, "description": _text(cells[1]), "category": cat, "url": url,
                        "auth": auth, "auth_raw": raw_auth or "No", "https": https, "cors": _tri(cells[4]),
                        "sponsored": tracked, "also_in": []})
    return {"entries": dedupe(entries), "skipped": skipped, "categories": cats}


def dedupe(entries):
    """One entry per API: the same link, or the same name in the same category, listed twice is one API. The first
    listing is kept, a sponsored listing never replaces a plain one, and the other categories are remembered."""
    out, by_url, by_name = [], {}, {}
    for e in entries:
        ku = re.sub(r"^https?://(www\.)?", "", e["url"]).rstrip("/").lower()
        kn = (e["category"].lower(), e["name"].lower())
        first = by_url.get(ku) or by_name.get(kn)
        if first is None:
            by_url[ku] = by_name[kn] = e; out.append(e); continue
        first["duplicates"] = first.get("duplicates", 0) + 1
        if e["category"] != first["category"] and e["category"] not in first["also_in"]: first["also_in"].append(e["category"])
        if first["sponsored"] and not e["sponsored"]: first["sponsored"] = False
    ids = {}
    for e in out:   # ids stay unique even when two names slug alike
        ids[e["id"]] = ids.get(e["id"], 0) + 1
        if ids[e["id"]] > 1: e["id"] += f"-{ids[e['id']]}"
    return out


def build(markdown, fetched=None, origin=UPSTREAM):
    P = parse(markdown)
    return {"schema": 1, "source": dict(SOURCE, origin=origin), "fetched": fetched or now(), "sha256": hashlib.sha256(str(markdown or "").encode()).hexdigest(),
            "counts": {"entries": len(P["entries"]), "categories": len(P["categories"]), "skipped": len(P["skipped"]),
                       "sponsored": sum(1 for e in P["entries"] if e["sponsored"]), "merged_duplicates": sum(e.get("duplicates", 0) for e in P["entries"])},
            "categories": P["categories"], "skipped": P["skipped"][:200], "entries": P["entries"]}


def valid(C):
    """A plausible catalogue: the shape this tool wrote, with enough entries to be the real thing."""
    return (isinstance(C, dict) and isinstance(C.get("entries"), list) and len(C["entries"]) >= MIN_ENTRIES
            and all(isinstance(e, dict) and e.get("id") and e.get("name") and str(e.get("url", "")).startswith(("http://", "https://")) for e in C["entries"]))


def load(path=None):
    """The working catalogue, or an empty one with the reason (a missing or damaged file never raises)."""
    p = path or CATALOG
    try:
        C = json.load(open(p))
    except (OSError, ValueError) as e:
        return {"schema": 1, "source": SOURCE, "fetched": None, "counts": {"entries": 0}, "categories": [], "entries": [], "skipped": [],
                "problem": f"no usable catalogue at {p}: {type(e).__name__}"}
    if not isinstance(C, dict) or not isinstance(C.get("entries"), list):
        return {"schema": 1, "source": SOURCE, "fetched": None, "counts": {"entries": 0}, "categories": [], "entries": [], "skipped": [], "problem": f"{p} is not a catalogue"}
    return C


def fetch(url=UPSTREAM, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "gitcraft-api-discovery"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(8 * 2**20).decode("utf-8", "replace")


def refresh(path=None, url=UPSTREAM, fetcher=None):
    """Replace the working catalogue with the upstream's, or keep the working one and say why.
    → {"status": "updated" | "unchanged" | "kept", "why", "entries", "fetched"}"""
    p = path or CATALOG
    old = load(p)
    keep = lambda why: {"status": "kept", "why": why, "entries": len(old["entries"]), "fetched": old.get("fetched"),
                        "usable": bool(old["entries"])}
    try:
        md = (fetcher or fetch)(url)
    except Exception as e:   # offline, blocked, timed out, rate-limited: the working copy stays
        return keep(f"the upstream could not be fetched ({type(e).__name__}: {str(e)[:120]}); the working catalogue is unchanged")
    new = build(md, origin=url)
    if not valid(new):
        return keep(f"the upstream did not parse as a catalogue ({new['counts']['entries']} entries, at least {MIN_ENTRIES} expected); the working catalogue is unchanged")
    if old.get("sha256") == new["sha256"] and valid(old):
        return {"status": "unchanged", "why": "the upstream has not changed since the last fetch", "entries": len(old["entries"]), "fetched": old.get("fetched"), "usable": True}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(new, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)   # atomic: a reader never sees half a catalogue
    return {"status": "updated", "why": f"{new['counts']['entries']} APIs in {new['counts']['categories']} categories "
            f"({new['counts']['skipped']} rows skipped, {new['counts']['merged_duplicates']} duplicates merged)", "entries": len(new["entries"]), "fetched": new["fetched"], "usable": True}
