"""CC0 asset libraries: Poly Haven (textures, HDRIs, models) and ambientCG (PBR materials).

Both publish everything under CC0 1.0 (public domain: no attribution required, commercial use allowed); GITCRAFT
still records the source page and authors as a courtesy credit. Plain HTTPS through urllib, which honours
HTTPS_PROXY: under the sandbox the launcher points that at netgate, which lets studiocraft reach only HOSTS
(GITCRAFT's setup adds them to ~/.gitcraft/allow-hosts; the environment's network policy must allow them too).

Downloads are untrusted data: every response is size-capped, Poly Haven files are checked against the API's md5,
ambientCG zips are read member by member (nothing is extracted to a path from the archive), and images are only
ever decoded by Pillow."""
import hashlib, io, json, os, re, socket, urllib.error, urllib.parse, urllib.request, zipfile
from .contract import Blocked, StudioError

UA = "GITCRAFT/1.0 (+https://github.com/scottyfncodes/GITCRAFT)"
HOSTS = ["api.polyhaven.com", "dl.polyhaven.org", "ambientcg.com", "acg-download.struffelproductions.com"]
LICENSE = "CC0-1.0"
MB = 1 << 20
_cache = {}


REDIRECTS = {"ambientcg.com": "acg-download.struffelproductions.com"}   # ambientCG's /get downloads redirect here


def _blocked(url, why):
    host = urllib.parse.urlparse(url).hostname
    if host in REDIRECTS and "/get" in url: host = REDIRECTS[host]   # the download host, not the API host, was refused
    return Blocked(f"cannot reach {host} ({why})",
                   install=(f"allow {host} for studiocraft: add `studiocraft: {host}` to ~/.gitcraft/allow-hosts (GITCRAFT's setup adds "
                            f"the CC0 library hosts), and allow it in the environment's network policy, then start a new session"),
                   alternatives=["materialcraft_generate (procedural PBR materials, no network)", "worldcraft_sky (procedural or Blender sky)"])


def get(url, max_bytes=64 * MB, timeout=60):
    """GET with the GITCRAFT User-Agent; a network refusal (sandbox, netgate, environment policy) is a Blocked."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            n = int(r.headers.get("Content-Length") or 0)
            if n > max_bytes: raise StudioError(f"{url} is {n // MB} MB, over the {max_bytes // MB} MB limit for this request")
            data = r.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        if e.code in (403, 407) and "GITCRAFT policy" in (e.read(400) or b"").decode(errors="replace"): raise _blocked(url, "not in this tool's network allowance")
        if e.code == 404: raise StudioError(f"not found: {url}")
        raise StudioError(f"{url}: HTTP {e.code}")
    except urllib.error.URLError as e:
        r = e.reason
        if isinstance(r, (PermissionError, ConnectionRefusedError)) or "Tunnel connection failed" in str(r) or "403" in str(r):
            raise _blocked(url, "network not allowed")
        raise StudioError(f"{url}: {r}")
    except (PermissionError, socket.timeout) as e:
        raise _blocked(url, type(e).__name__)
    if len(data) > max_bytes: raise StudioError(f"{url} exceeds the {max_bytes // MB} MB limit for this request")
    return data


def get_json(url):
    if url not in _cache: _cache[url] = json.loads(get(url, max_bytes=40 * MB))
    return _cache[url]


def _words(q): return [w for w in re.findall(r"[a-z0-9]+", (q or "").lower()) if len(w) > 1]


def _stem(w):
    for suf in ("ies", "es", "s", "y", "ing", "ed"):
        if w.endswith(suf) and len(w) - len(suf) >= 3: return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def _score(words, *fields):
    """Whole word 3, word stem (snowy ~ snow, trees ~ tree) 2, substring 1; plus 4 per distinct word matched, so an
    asset matching every word outranks one matching a single word many times."""
    text = " ".join(" ".join(f) if isinstance(f, (list, tuple)) else str(f or "") for f in fields).lower()
    total = hits = 0
    for w in words:
        s = 3 if re.search(r"\b" + re.escape(w) + r"\b", text) else 2 if re.search(r"\b" + re.escape(_stem(w)), text) else 1 if w in text else 0
        total += s; hits += s > 0
    return total + 4 * hits


# ---------------------------------------------------------------- Poly Haven
PH_TYPES = {"textures": "textures", "hdris": "hdris", "models": "models"}


def polyhaven_search(kind, query, limit=8):
    assets = get_json(f"https://api.polyhaven.com/assets?t={PH_TYPES[kind]}")
    words = _words(query); out = []
    for aid, a in assets.items():
        s = _score(words, aid.replace("_", " "), a.get("name"), a.get("tags", []), a.get("categories", []), a.get("description"))
        if words and s == 0: continue
        out.append({"source": "polyhaven", "id": aid, "name": a.get("name"), "score": s, "downloads": a.get("download_count", 0),
                    "tags": a.get("tags", [])[:8], "categories": a.get("categories", []), "authors": list((a.get("authors") or {}).keys()),
                    "page": f"https://polyhaven.com/a/{aid}", "license": LICENSE})
    out.sort(key=lambda c: (-c["score"], -c["downloads"]))
    return out[:limit]


def polyhaven_info(aid): return get_json(f"https://api.polyhaven.com/info/{urllib.parse.quote(aid)}")
def polyhaven_files(aid): return get_json(f"https://api.polyhaven.com/files/{urllib.parse.quote(aid)}")


def fetch_checked(entry, max_bytes=256 * MB):
    """A Poly Haven file entry {url, size, md5} → bytes, verified."""
    if entry.get("size", 0) > max_bytes: raise StudioError(f"{entry['url']} is {entry['size'] // MB} MB, over the limit; pick a lower resolution")
    data = get(entry["url"], max_bytes=max_bytes, timeout=300)
    if entry.get("md5") and hashlib.md5(data).hexdigest() != entry["md5"]: raise StudioError(f"checksum mismatch for {entry['url']}")
    return data


# ---------------------------------------------------------------- ambientCG
def ambientcg_search(query, limit=8, data_type="Material"):
    q = urllib.parse.urlencode({"type": data_type, "q": query or "", "include": "downloadData,tagData,displayData", "limit": max(1, min(limit, 30)), "sort": "Popular"})
    d = get_json(f"https://ambientcg.com/api/v2/full_json?{q}")
    words = _words(query); out = []
    for a in d.get("foundAssets", []):
        dl = (((a.get("downloadFolders") or {}).get("default") or {}).get("downloadFiletypeCategories") or {}).get("zip", {}).get("downloads", [])
        out.append({"source": "ambientcg", "id": a["assetId"], "name": a.get("displayName") or a["assetId"],
                    "score": _score(words, a["assetId"], a.get("displayName"), a.get("tags", []), a.get("displayCategory")),
                    "downloads": a.get("downloadCount", 0), "tags": (a.get("tags") or [])[:8], "categories": [a.get("displayCategory")] if a.get("displayCategory") else [],
                    "authors": ["ambientCG (Lennart Demes)"], "page": f"https://ambientcg.com/view?id={a['assetId']}", "license": LICENSE,
                    "zips": {x["attribute"]: {"url": x["downloadLink"], "size": x.get("size", 0)} for x in dl}})
    out.sort(key=lambda c: (-c["score"], -c["downloads"]))
    return out[:limit]


def zip_images(data, max_members=40, max_member_bytes=96 * MB):
    """Image members of a zip, by basename → bytes. Names are only used as dictionary keys, never as paths."""
    out = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        infos = [i for i in z.infolist() if not i.is_dir()][:max_members]
        for i in infos:
            name = os.path.basename(i.filename)
            if not re.search(r"\.(jpe?g|png|exr|tiff?)$", name, re.I): continue
            if i.file_size > max_member_bytes: raise StudioError(f"zip member {name} is too large")
            out[name] = z.read(i)
    return out
