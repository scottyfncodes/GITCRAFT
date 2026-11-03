"""The universal asset catalogue (AssetCraft's store), SQLite from the standard library.

One catalogue for every project on the machine ($GITCRAFT_ASSET_CATALOG, default
~/.gitcraft/assetcraft/catalog.sqlite). Each row is one version of one file: path, project,
SHA-256, validated format details, licence + attribution, where it came from (department run,
3D library, sidecar, scan), a thumbnail and a perceptual hash for near-duplicate images.
A file whose bytes change gets a new version; the old row stays as history.

Licences come from, in order: the department run that made the file, a `<file>.license.json`
sidecar ({"license": "CC0-1.0", "attribution": "...", "source": "..."}), the 3D library record,
or a scan's `default_license`; otherwise the asset is listed as `UNKNOWN` by license_report."""
import datetime, json, os, re, sqlite3, subprocess
from . import GITCRAFT_HOME
from . import validate as V

CATALOG = os.environ.get("GITCRAFT_ASSET_CATALOG") or os.path.join(GITCRAFT_HOME, "assetcraft", "catalog.sqlite")
KINDS = {"png": "image", "jpeg": "image", "webp": "image", "gif": "image", "svg": "image", "exr": "image", "hdr": "image",
         "wav": "audio", "ogg": "audio", "mp3": "audio", "flac": "audio", "midi": "audio",
         "mp4": "video", "webm": "video", "glb": "model", "gltf": "model", "fbx": "model", "obj": "model", "blend": "model", "bvh": "animation",
         "tiled": "map", "pdf": "document", "json": "data", "csv": "data"}
ASSET_FORMATS = set(KINDS) - {"json", "csv"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".cache", ".vercel", "target"}


def _db():
    os.makedirs(os.path.dirname(CATALOG), exist_ok=True)
    c = sqlite3.connect(CATALOG, timeout=30); c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS assets(
      id INTEGER PRIMARY KEY, project TEXT, path TEXT, rel TEXT, kind TEXT, format TEXT, sha256 TEXT, bytes INTEGER,
      version INTEGER, current INTEGER DEFAULT 1, valid INTEGER, info TEXT, license TEXT, attribution TEXT, source TEXT,
      tags TEXT, thumb TEXT, phash TEXT, created TEXT, updated TEXT, UNIQUE(path, sha256));
    CREATE INDEX IF NOT EXISTS ix_sha ON assets(sha256); CREATE INDEX IF NOT EXISTS ix_path ON assets(path);
    CREATE INDEX IF NOT EXISTS ix_project ON assets(project);""")
    return c


def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def project_of(path):
    d = os.path.dirname(os.path.abspath(path))
    while d and d != os.path.dirname(d):
        if os.path.isdir(os.path.join(d, ".git")): return d
        d = os.path.dirname(d)
    from . import roots
    rp = os.path.realpath(path)
    return next((r for r in roots() if rp.startswith(r + os.sep)), os.path.dirname(os.path.abspath(path)))


def _sha(p):
    from .contract import sha256; return sha256(p)


def dhash(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            g = im.convert("L").resize((9, 8))
            px = list(g.getdata())
        bits = "".join("1" if px[r * 9 + c] > px[r * 9 + c + 1] else "0" for r in range(8) for c in range(8))
        return f"{int(bits, 2):016x}"
    except Exception:
        return None


def thumbnail(path, sha, fmt):
    tdir = os.path.join(os.path.dirname(CATALOG), "thumbs", sha[:2]); os.makedirs(tdir, exist_ok=True)
    out = os.path.join(tdir, sha + ".png")
    if os.path.exists(out): return out
    try:
        from PIL import Image
        kind = KINDS.get(fmt)
        if kind == "image" and fmt not in ("svg", "exr", "hdr"):
            with Image.open(path) as im:
                im = im.convert("RGBA"); im.thumbnail((160, 160)); im.save(out)
        elif kind == "audio" and fmt != "midi":
            from .media import read_audio, waveform_png
            waveform_png(read_audio(path, sr=8000, mono=True), out, w=160, h=48)
        elif kind == "video":
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", path, "-frames:v", "1", "-vf", "scale=160:-2", out], timeout=60)
        elif kind == "model":
            # a preview next to it, as MeshCraft / departments write them
            stem = os.path.splitext(path)[0]
            for cand in (stem + "_preview.png", stem + ".png", os.path.join(os.path.dirname(path), "preview.png")):
                if os.path.exists(cand):
                    with Image.open(cand) as im:
                        im = im.convert("RGBA"); im.thumbnail((160, 160)); im.save(out)
                    break
        return out if os.path.exists(out) else None
    except Exception:
        return None


def _sidecar(path):
    for s in (path + ".license.json", os.path.join(os.path.dirname(path), "LICENSE.assets.json")):
        if os.path.exists(s):
            try:
                d = json.load(open(s))
                if s.endswith("LICENSE.assets.json"): d = d.get(os.path.basename(path)) or d.get("*") or {}
                return d
            except Exception: pass
    return {}


def register(path, license=None, attribution=None, source=None, tags=None, project=None):
    path = os.path.abspath(path); fmt = V.sniff(path)
    v = V.check(path); sha = _sha(path)
    side = _sidecar(path)
    license = license or side.get("license"); attribution = attribution or side.get("attribution")
    if side and not source: source = {"type": "sidecar", **{k: side[k] for k in side if k not in ("license", "attribution")}}
    project = project or project_of(path)
    c = _db()
    with c:
        row = c.execute("SELECT * FROM assets WHERE path=? AND sha256=?", (path, sha)).fetchone()
        if row:
            upd = {"updated": now(), "current": 1}
            if license and (not row["license"] or row["license"] == "UNKNOWN"): upd["license"] = license
            if attribution and not row["attribution"]: upd["attribution"] = attribution
            if source and not row["source"]: upd["source"] = json.dumps(source)
            if tags: upd["tags"] = ",".join(sorted(set((row["tags"] or "").split(",") + list(tags)) - {""}))
            c.execute("UPDATE assets SET current=0 WHERE path=? AND id<>?", (path, row["id"]))
            c.execute(f"UPDATE assets SET {', '.join(k + '=?' for k in upd)} WHERE id=?", (*upd.values(), row["id"]))
            return _row(c.execute("SELECT * FROM assets WHERE id=?", (row["id"],)).fetchone())
        prev = c.execute("SELECT MAX(version) v FROM assets WHERE path=?", (path,)).fetchone()["v"] or 0
        c.execute("UPDATE assets SET current=0 WHERE path=?", (path,))
        cur = c.execute("""INSERT INTO assets(project, path, rel, kind, format, sha256, bytes, version, current, valid, info, license,
                           attribution, source, tags, thumb, phash, created, updated) VALUES(?,?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?,?,?)""",
                        (project, path, os.path.relpath(path, project), KINDS.get(fmt, "other"), fmt, sha, os.path.getsize(path), prev + 1,
                         1 if v["ok"] else 0, json.dumps(v), license or "UNKNOWN", attribution, json.dumps(source) if source else None,
                         ",".join(tags or []), thumbnail(path, sha, fmt), dhash(path) if KINDS.get(fmt) == "image" else None, now(), now()))
        return _row(c.execute("SELECT * FROM assets WHERE id=?", (cur.lastrowid,)).fetchone())


def _row(r):
    if r is None: return None
    d = dict(r)
    for k in ("info", "source"):
        if d.get(k): d[k] = json.loads(d[k])
    d["tags"] = [t for t in (d.get("tags") or "").split(",") if t]
    d["exists"] = os.path.exists(d["path"])
    return d


def register_run(record):
    """Register a department run's outputs (called by contract.run)."""
    ids = []
    for o in record.get("outputs", []):
        p = o["path"] if os.path.isabs(o["path"]) else os.path.join(record["out_dir"], o["path"])
        if V.sniff(p) not in ASSET_FORMATS and o.get("role") not in ("data", "map", "manifest"): continue
        r = register(p, license=record.get("output_license"), attribution=record.get("attribution"),
                     source={"type": "department", "department": record["department"], "action": record["action"],
                             "record": record.get("record") or os.path.join(record["out_dir"], ""), "tools": record.get("tools")},
                     tags=[record["department"], record["action"]] + list(record.get("request", {}).get("tags") or []))
        ids.append(r["id"])
    return {"registered": len(ids), "ids": ids, "catalog": CATALOG}


def scan(folder, default_license=None, project=None, formats=None):
    out, errors = [], []
    for d, dirs, files in os.walk(folder):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for f in sorted(files):
            p = os.path.join(d, f); fmt = V.sniff(p)
            if fmt not in ASSET_FORMATS or (formats and fmt not in formats) or f.endswith(".license.json"): continue
            try: out.append(register(p, license=None, project=project))
            except Exception as e: errors.append({"path": p, "error": f"{type(e).__name__}: {e}"})
    if default_license:
        c = _db()
        with c:
            for r in out:
                if r["license"] == "UNKNOWN":
                    c.execute("UPDATE assets SET license=? WHERE id=?", (default_license, r["id"])); r["license"] = default_license
    return out, errors


def search(query="", kind=None, license=None, project=None, department=None, include_history=False, limit=100):
    q = "SELECT * FROM assets WHERE 1=1"; a = []
    if not include_history: q += " AND current=1"
    if query: q += " AND (path LIKE ? OR tags LIKE ? OR source LIKE ?)"; a += [f"%{query}%"] * 3
    if kind: q += " AND kind=?"; a.append(kind)
    if license: q += " AND license LIKE ?"; a.append(f"%{license}%")
    if project: q += " AND project=?"; a.append(os.path.abspath(project))
    if department: q += " AND source LIKE ?"; a.append(f'%"department": "{department}"%')
    q += " ORDER BY updated DESC LIMIT ?"; a.append(limit)
    return [_row(r) for r in _db().execute(q, a).fetchall()]


def get(ident):
    c = _db()
    r = c.execute("SELECT * FROM assets WHERE id=?", (int(ident),)).fetchone() if str(ident).isdigit() else \
        c.execute("SELECT * FROM assets WHERE path=? AND current=1", (os.path.abspath(ident),)).fetchone()
    if not r: return None
    d = _row(r)
    d["history"] = [dict(id=h["id"], version=h["version"], sha256=h["sha256"], created=h["created"])
                    for h in c.execute("SELECT id, version, sha256, created FROM assets WHERE path=? ORDER BY version", (d["path"],))]
    return d


def duplicates(project=None, near=True, threshold=5):
    rows = search(project=project, limit=100000)
    rows = [r for r in rows if r["exists"]]
    by = {}
    for r in rows: by.setdefault(r["sha256"], []).append(r)
    exact = [[x["path"] for x in g] for g in by.values() if len(g) > 1]
    near_groups = []
    if near:
        imgs = [r for r in rows if r.get("phash")]
        seen = set()
        for i, a in enumerate(imgs):
            if a["id"] in seen: continue
            grp = [a]
            for b in imgs[i + 1:]:
                if b["id"] in seen or b["sha256"] == a["sha256"]: continue
                if bin(int(a["phash"], 16) ^ int(b["phash"], 16)).count("1") <= threshold: grp.append(b); seen.add(b["id"])
            if len(grp) > 1: near_groups.append([g["path"] for g in grp]); seen.add(a["id"])
    return {"exact": exact, "near": near_groups, "checked": len(rows)}


REF_EXT = (".js", ".mjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".tmj", ".gltf", ".md", ".vue", ".svelte", ".py", ".gd", ".tscn", ".cs", ".lua")


def references(project_dir):
    """Every file name referenced by the project's source (by basename), and which file refers to it."""
    refs = {}
    for d, dirs, files in os.walk(project_dir):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        for f in files:
            if not f.endswith(REF_EXT) or f.endswith(".studio.json") or f.endswith(".license.json"): continue
            p = os.path.join(d, f)
            try: t = open(p, encoding="utf-8", errors="ignore").read(2_000_000)
            except Exception: continue
            for m in re.finditer(r"[\w\-./@]+\.(png|jpe?g|webp|gif|svg|wav|ogg|mp3|flac|mp4|webm|glb|gltf|fbx|obj|tmj|json|bvh|hdr|exr)\b", t, re.I):
                refs.setdefault(os.path.basename(m.group(0)), set()).add(os.path.relpath(p, project_dir))
    return refs


def unused(project_dir):
    refs = references(project_dir)
    rows = [r for r in search(project=project_dir, limit=100000) if r["exists"] and r["format"] in ASSET_FORMATS]
    return [{"path": r["rel"], "id": r["id"], "kind": r["kind"], "bytes": r["bytes"]} for r in rows if os.path.basename(r["path"]) not in refs]


def dependencies(path):
    """What an asset needs to load: glTF buffers/images, Tiled tilesets/images, HTML/CSS urls."""
    fmt = V.sniff(path); base = os.path.dirname(path); out = []
    try:
        if fmt == "glb" or fmt == "gltf":
            g = V.glb_json(path)[0] if fmt == "glb" else json.load(open(path))
            out = [x["uri"] for x in g.get("buffers", []) + g.get("images", []) if x.get("uri") and not x["uri"].startswith("data:")]
        elif fmt == "tiled":
            m = json.load(open(path))
            out = [t["source"] for t in m.get("tilesets", []) if "source" in t] + [t["image"] for t in m.get("tilesets", []) if "image" in t]
            out += [L["image"] for L in m.get("layers", []) if L.get("type") == "imagelayer" and L.get("image")]
        elif fmt in ("html", "text", "css") or path.endswith(".css"):
            t = open(path, encoding="utf-8", errors="ignore").read()
            out = sorted(set(re.findall(r"(?:src|href|url\()\s*=?\s*[\"']?([^\"')\s>]+\.(?:png|jpe?g|svg|webp|gif|wav|ogg|mp3|glb|gltf|js|css|json))", t)))
    except Exception as e:
        return {"path": path, "error": f"{type(e).__name__}: {e}"}
    res = [{"ref": r, "resolved": os.path.normpath(os.path.join(base, r)), "exists": os.path.exists(os.path.join(base, r))} for r in out]
    return {"path": path, "format": fmt, "dependencies": res, "missing": [r["ref"] for r in res if not r["exists"]]}


def license_report(project=None):
    rows = [r for r in search(project=project, limit=100000) if r["exists"]]
    by = {}
    for r in rows: by.setdefault(r["license"] or "UNKNOWN", []).append(r["rel"] if project else r["path"])
    restricted = {k: v for k, v in by.items() if re.search(r"NC|NonCommercial|ND|Proprietary|Research", k, re.I)}
    copyleft = {k: v for k, v in by.items() if re.search(r"GPL|SA|MPL", k)}
    attrib = sorted({(r["rel"] if project else r["path"], r["attribution"]) for r in rows if r.get("attribution")})
    return {"total": len(rows), "by_license": {k: len(v) for k, v in by.items()}, "unknown": by.get("UNKNOWN", []),
            "restricted": restricted, "copyleft": copyleft, "attributions": [{"path": p, "attribution": a} for p, a in attrib]}


def verify(project=None):
    rows = search(project=project, limit=100000); missing, changed, ok = [], [], 0
    for r in rows:
        if not os.path.exists(r["path"]): missing.append(r["path"]); continue
        if _sha(r["path"]) != r["sha256"]: changed.append(r["path"])
        else: ok += 1
    return {"ok": ok, "missing": missing, "changed": changed}
