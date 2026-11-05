"""Phase 2, evidence collection: read a game repository without changing or running it.

What is read (and nothing is written to the repository):
  * JavaScript / TypeScript source: the literal values of top-level declarations and builder calls (jsparse)
  * JSON data files, Tiled maps (.tmj / .json with layers + tilewidth), LDtk projects (.ldtk)
  * Dialogue scripts: Ink (.ink), Yarn Spinner (.yarn), plain-text scripts in a dialogue/ folder
  * Design documentation: README, CLAUDE.md, docs/**/*.md
  * Tests (names and what they cover: listed as evidence that exists, never as results DESIGNCRAFT ran)
  * Screenshots / captures (visual evidence inventory)
  * Engine scene formats DESIGNCRAFT cannot read yet (Godot .tscn, Unity .unity/.prefab, Unreal .umap) are
    counted and reported as limitations, never guessed at.
PLAYCRAFT's discovery scanner (studio/departments/playcraft/scan.py) is reused when it is present for the
engine, genres and system signals, so the two products agree on what a game is."""
import hashlib, importlib.util, json, os, re
from . import jsparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SKIP_DIRS = {"node_modules", "dist", "build", ".git", "coverage", ".next", ".vercel", "out", "vendor", ".cache", "gitcraft-out",
             ".gitcraft-work", "playwright-report", "test-results", "__pycache__", ".venv", "venv", "Library", "Temp", ".godot",
             "e2e", "__screenshots__", ".designcraft"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|e2e|spec)/|\.(test|spec)\.[a-z]+$")
UNSUPPORTED = {".tscn": "Godot scene", ".tres": "Godot resource", ".unity": "Unity scene", ".prefab": "Unity prefab",
               ".umap": "Unreal map", ".uasset": "Unreal asset", ".rmxp": "RPG Maker", ".gmx": "GameMaker", ".yy": "GameMaker"}
SHOT_RE = re.compile(r"(screenshot|screen-?shot|capture|evidence|playtest|shot[-_]|preview|frame)", re.I)
MAX_FILE = 1_500_000
MAX_FILES = 4000


def _walk(root):
    n = 0
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith(".") and not (rel == "." and x == "public" and False))
        for f in sorted(files):
            n += 1
            if n > MAX_FILES * 4: return
            yield os.path.join(d, f)


def _read(p):
    try:
        if os.path.getsize(p) > MAX_FILE: return None
        with open(p, encoding="utf-8", errors="replace") as fh: return fh.read()
    except OSError:
        return None


def _rel(root, p): return os.path.relpath(p, root).replace(os.sep, "/")


def _playcraft_scan():
    p = os.path.join(REPO, "studio", "departments", "playcraft", "scan.py")
    if not os.path.isfile(p): return None
    try:
        spec = importlib.util.spec_from_file_location("designcraft_playcraft_scan", p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    except Exception:
        return None


def _genres(info):
    """PLAYCRAFT's genre profiles, when available."""
    p = os.path.join(REPO, "studio", "departments", "playcraft", "genres.json")
    sc = _playcraft_scan()
    if not sc or not os.path.isfile(p): return None
    try:
        prof = json.load(open(p)); prof = prof.get("genres", prof)
        return sc.detect_genres(info, prof)
    except Exception:
        return None


# ------------------------------------------------------------------------- collections
def _collections_from_module(rel, mod):
    out = []
    for name, d in mod["decls"].items():
        v = d["value"]
        if d.get("depth", 0) > 0 and not d["exported"]: continue
        base = {"symbol": name, "file": rel, "line": d["line"], "doc": d.get("doc"), "type": d.get("type"), "exported": d["exported"]}
        if isinstance(v, list):
            items = [(i, x) for i, x in enumerate(v) if isinstance(x, dict) and "$call" not in x and "$ref" not in x and "$expr" not in x]
            if items: out.append(dict(base, kind="array", items=items))
            elif v and all(isinstance(x, str) for x in v): out.append(dict(base, kind="strings", items=list(enumerate(v))))
            elif v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v): out.append(dict(base, kind="numbers", items=list(enumerate(v))))
        elif isinstance(v, dict) and "$call" not in v and "$ref" not in v and "$expr" not in v:
            vals = [(k, x) for k, x in v.items() if not k.startswith(("_", "$")) and isinstance(x, dict) and "$call" not in x and "$ref" not in x and "$expr" not in x]
            if len(vals) >= 2 and len(vals) >= 0.6 * len([k for k in v if not k.startswith(("_", "$"))]):
                out.append(dict(base, kind="record", items=vals))
            else:
                out.append(dict(base, kind="object", items=[("", v)]))
        elif isinstance(v, (str, int, float)) and not isinstance(v, bool):
            out.append(dict(base, kind="scalar", items=[("", v)]))
    return out


def _json_collections(rel, data):
    out = []
    if isinstance(data, dict) and "tilewidth" in data and "layers" in data:
        return [], {"format": "tiled", "file": rel, "map": _tiled_summary(data)}
    if isinstance(data, dict) and ("__header__" in data or "jsonVersion" in data) and "levels" in data:
        return [], {"format": "ldtk", "file": rel, "map": _ldtk_summary(data)}
    def visit(name, v, depth=0):
        if depth > 3: return
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            out.append({"symbol": name, "file": rel, "line": None, "doc": None, "type": None, "exported": True, "kind": "array", "items": list(enumerate(v))})
        elif isinstance(v, dict):
            vals = [(k, x) for k, x in v.items() if isinstance(x, dict)]
            if len(vals) >= 2 and len(vals) == len(v):
                out.append({"symbol": name, "file": rel, "line": None, "doc": None, "type": None, "exported": True, "kind": "record", "items": vals})
            else:
                for k, x in v.items(): visit(k, x, depth + 1)
    visit(os.path.splitext(os.path.basename(rel))[0], data)
    return out, None


def _tiled_summary(d):
    layers, objects, w, h = [], [], d.get("width"), d.get("height")
    def walk(ls):
        for L in ls or []:
            if L.get("type") == "group": walk(L.get("layers")); continue
            info = {"name": L.get("name"), "type": L.get("type")}
            if L.get("type") == "tilelayer" and isinstance(L.get("data"), list):
                data = L["data"]; info["filled"] = sum(1 for x in data if x); info["cells"] = len(data)
                info["grid"] = data if len(data) <= 40000 else None
            if L.get("type") == "objectgroup":
                for o in L.get("objects", []):
                    objects.append({"name": o.get("name") or o.get("type") or o.get("class"), "type": o.get("type") or o.get("class") or L.get("name"),
                                    "x": o.get("x"), "y": o.get("y"), "props": {p.get("name"): p.get("value") for p in o.get("properties", []) if isinstance(p, dict)}})
                info["objects"] = len(L.get("objects", []))
            layers.append(info)
    walk(d.get("layers"))
    return {"width": w, "height": h, "tile": [d.get("tilewidth"), d.get("tileheight")], "layers": layers, "objects": objects}


def _ldtk_summary(d):
    levels = []
    for lv in d.get("levels", []):
        ents = []
        for L in lv.get("layerInstances") or []:
            for e in L.get("entityInstances", []):
                ents.append({"name": e.get("__identifier"), "type": e.get("__identifier"), "x": (e.get("px") or [None, None])[0], "y": (e.get("px") or [None, None])[1],
                             "props": {f.get("__identifier"): f.get("__value") for f in e.get("fieldInstances", [])}})
        levels.append({"name": lv.get("identifier"), "x": lv.get("worldX"), "y": lv.get("worldY"), "w": lv.get("pxWid"), "h": lv.get("pxHei"), "objects": ents})
    return {"levels": levels}


def _ink(rel, text):
    """Ink: knots (=== name ===), stitches, choices (* / +), speaker lines (Name: text), diverts (-> target)."""
    nodes, cur = [], None
    for i, ln in enumerate(text.split("\n"), 1):
        s = ln.strip()
        m = re.match(r"^={2,}\s*(\w+)", s)
        if m:
            cur = {"id": m.group(1), "line": i, "lines": [], "choices": [], "links": []}; nodes.append(cur); continue
        if cur is None:
            cur = {"id": "start", "line": i, "lines": [], "choices": [], "links": []}; nodes.append(cur)
        for t in re.findall(r"->\s*(\w+)", s): cur["links"].append(t)
        if re.match(r"^[*+]", s): cur["choices"].append(re.sub(r"^[*+\s]+|\[|\]|->.*$", "", s).strip()); continue
        s2 = re.sub(r"->.*$", "", s).strip()
        if s2 and not s2.startswith(("~", "//", "VAR", "CONST", "INCLUDE", "-")):
            m = re.match(r"^([A-Z][\w .'-]{0,30}):\s*(.+)$", s2)
            cur["lines"].append({"speaker": m.group(1) if m else None, "text": m.group(2) if m else s2, "line": i})
    return {"format": "ink", "file": rel, "nodes": nodes}


def _yarn(rel, text):
    nodes, cur, body = [], None, False
    for i, ln in enumerate(text.split("\n"), 1):
        s = ln.strip()
        if not body:
            m = re.match(r"^title:\s*(\S+)", s)
            if m: cur = {"id": m.group(1), "line": i, "lines": [], "choices": [], "links": []}
            if s == "---" and cur is not None: body = True; nodes.append(cur)
            continue
        if s == "===": body = False; cur = None; continue
        for t in re.findall(r"<<jump\s+(\w+)>>|\[\[(?:[^|\]]*\|)?(\w+)\]\]", s):
            cur["links"].append(t[0] or t[1])
        if s.startswith("->"): cur["choices"].append(s[2:].strip()); continue
        if s and not s.startswith("<<"):
            m = re.match(r"^([A-Z][\w .'-]{0,30}):\s*(.+)$", s)
            cur["lines"].append({"speaker": m.group(1) if m else None, "text": m.group(2) if m else s, "line": i})
    return {"format": "yarn", "file": rel, "nodes": nodes}


def _doc_info(rel, text):
    heads = re.findall(r"^#{1,3}\s+(.+)$", text, re.M)
    return {"file": rel, "title": heads[0] if heads else os.path.basename(rel), "headings": heads[:40], "chars": len(text), "text": text[:60000]}


def inspect(root):
    """-> the raw evidence bundle of a repository (JSON-safe except collection values, which keep jsparse markers)."""
    root = os.path.abspath(root)
    if not os.path.isdir(root): raise FileNotFoundError(f"not a folder: {root}")
    pkg = {}
    try: pkg = json.load(open(os.path.join(root, "package.json")))
    except Exception: pass
    collections, calls, maps, scripts, docs, tests, shots, unsupported, files_read = [], [], [], [], [], [], [], {}, []
    symbols = {}
    counts = {"code": 0, "json": 0, "docs": 0, "tests": 0, "images": 0, "audio": 0, "models": 0, "skipped_large": 0}
    for p in _walk(root):
        rel = _rel(root, p); ext = os.path.splitext(p)[1].lower(); low = rel.lower()
        if ext in UNSUPPORTED: unsupported.setdefault(UNSUPPORTED[ext], []).append(rel); continue
        if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            counts["images"] += 1
            if SHOT_RE.search(low) or low.startswith(("docs/", "screenshots/", "acceptance/")): shots.append(rel)
            continue
        if ext in (".wav", ".ogg", ".mp3", ".m4a", ".flac"): counts["audio"] += 1; continue
        if ext in (".glb", ".gltf", ".fbx", ".obj", ".blend"): counts["models"] += 1; continue
        is_test = bool(TEST_RE.search(low))
        if ext in CODE_EXT:
            t = _read(p)
            if t is None: counts["skipped_large"] += 1; continue
            if "\n" not in t[:5000] and len(t) > 20000: continue   # minified bundle
            if is_test:
                counts["tests"] += 1
                names = re.findall(r"\b(?:it|test|describe)\(\s*['\"`]([^'\"`]{3,140})", t)
                tests.append({"file": rel, "cases": len(names), "names": names[:60]}); continue
            if low.startswith(("scripts/", "tools/", "art/", "design/")) and ext in (".cjs", ".mjs"): continue
            counts["code"] += 1; files_read.append(rel)
            try:
                mod = jsparse.parse_module(t)
            except Exception as e:   # one unreadable file never stops the inspection
                unsupported.setdefault("unparsed source", []).append(f"{rel}: {type(e).__name__}"); continue
            for c in _collections_from_module(rel, mod): collections.append(c)
            for name, d in mod["decls"].items():
                if d["exported"] or d.get("depth", 0) == 0: symbols.setdefault(name, []).append((rel, d["value"]))
            for c in mod["calls"]: calls.append(dict(c, file=rel))
        elif ext in (".json", ".tmj", ".ldtk"):
            base = os.path.basename(low)
            if base in ("package.json", "package-lock.json", "tsconfig.json", "vercel.json", "manifest.json", "jsconfig.json") or base.endswith((".studio.json", ".webmanifest")) \
                    or "/logs/" in low or "verify" in base or low.startswith(("docs/", "art/", "creative/")) and ext == ".json": continue
            t = _read(p)
            if t is None: counts["skipped_large"] += 1; continue
            try: data = json.loads(t)
            except ValueError: continue
            counts["json"] += 1; files_read.append(rel)
            cols, mp = _json_collections(rel, data)
            collections.extend(cols)
            if mp: maps.append(mp)
        elif ext in (".ink", ".yarn"):
            t = _read(p) or ""; files_read.append(rel)
            scripts.append(_ink(rel, t) if ext == ".ink" else _yarn(rel, t))
        elif ext in (".md", ".markdown") and not is_test:
            if low.startswith(("node_modules",)): continue
            t = _read(p) or ""
            if len(t) < 80: continue
            counts["docs"] += 1; docs.append(_doc_info(rel, t))
    # PLAYCRAFT's scanner: engine, genres, system signals (reused, not duplicated)
    pc = None
    sc = _playcraft_scan()
    if sc:
        try:
            info = sc.scan(root)
            g = _genres(info)
            pc = {"title": info.get("title"), "pitch": info.get("pitch"), "engine": info.get("engine"),
                  "signals": {k: {"count": v["count"], "where": v["where"][:2]} for k, v in info["signals"].items() if v.get("count")},
                  "genres": g["genres"] if g else None, "mobile": info.get("mobile")}
        except Exception as e:
            pc = {"error": f"{type(e).__name__}: {e}"}
    title = (pc or {}).get("title") or _readme_title(root) or pkg.get("name") or os.path.basename(root)
    h = hashlib.sha256()
    for rel in files_read:
        try: h.update(rel.encode()); h.update(open(os.path.join(root, rel), "rb").read())
        except OSError: pass
    return {"root": root, "name": os.path.basename(root.rstrip("/")), "title": title, "pitch": (pc or {}).get("pitch"),
            "package": {"name": pkg.get("name"), "description": pkg.get("description"), "scripts": sorted((pkg.get("scripts") or {}).keys())},
            "collections": collections, "calls": calls, "symbols": symbols, "maps": maps, "scripts": scripts, "docs": docs, "tests": tests,
            "screenshots": shots[:60], "unsupported": {k: v[:20] for k, v in unsupported.items()}, "unsupported_counts": {k: len(v) for k, v in unsupported.items()},
            "counts": counts, "playcraft_scan": pc, "content_sha256": h.hexdigest(), "files_read": len(files_read), "git": _git(root), "remote": remote(root)}


def _readme_title(root):
    for n in ("README.md", "readme.md", "README"):
        t = _read(os.path.join(root, n))
        if t:
            m = re.search(r"^#\s+(.+)$", t, re.M)
            if m: return m.group(1).strip()
    return None


def _git(root):
    """HEAD commit read from .git files directly (no subprocess, no writes)."""
    g = os.path.join(root, ".git")
    try:
        if os.path.isfile(g):
            g = os.path.join(root, open(g).read().split("gitdir:")[1].strip())
        head = open(os.path.join(g, "HEAD")).read().strip()
        if head.startswith("ref:"):
            ref = head[4:].strip(); p = os.path.join(g, ref)
            if os.path.isfile(p): return {"commit": open(p).read().strip(), "ref": ref}
            packed = os.path.join(g, "packed-refs")
            if os.path.isfile(packed):
                for ln in open(packed):
                    if ln.strip().endswith(ref): return {"commit": ln.split()[0], "ref": ref}
            return {"commit": None, "ref": ref}
        return {"commit": head, "ref": None}
    except Exception:
        return None


def remote(root):
    """owner/repo from .git/config's origin url, if present (read only)."""
    try:
        g = os.path.join(root, ".git")
        if os.path.isfile(g): g = os.path.join(root, open(g).read().split("gitdir:")[1].strip())
        cfg = open(os.path.join(g, "config")).read()
        m = re.search(r'\[remote "origin"\][^\[]*?url\s*=\s*(\S+)', cfg)
        if not m: return None
        u = re.sub(r"\.git$", "", m.group(1))
        m2 = re.search(r"[/:]([^/:]+)/([^/]+)$", u)
        return f"{m2.group(1)}/{m2.group(2)}" if m2 else None
    except Exception:
        return None
