"""MeshCraft asset library: versioned, searchable, with full provenance per asset.

Layout ($MESHCRAFT_LIBRARY, default ~/.gitcraft/meshcraft-library):
  index.json                         one summary per asset (search reads only this)
  assets/<asset_id>/v<N>/asset.json  full metadata for that version
  assets/<asset_id>/v<N>/...         exports (glb, gltf/, fbx, obj/, stl, blend), textures/, previews/
  jobs/<job_id>.json                 pipeline job records (see pipeline.py)
The library lives outside the workspace like LightCraft's; `export()` copies an asset into
an authorized root so other GITCRAFT tools can pick it up (a handoff)."""
import fcntl, hashlib, json, os, re, shutil, time, uuid

GITCRAFT_HOME = os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft"))
ROOT = os.environ.get("MESHCRAFT_LIBRARY", os.path.join(GITCRAFT_HOME, "meshcraft-library"))
ENGINE = {"units": "metres", "up": "+Y (glTF)", "forward": "+Z (glTF / three.js)", "handedness": "right"}


def path(*p): return os.path.join(ROOT, *p)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def slugify(s): return re.sub(r"[^a-z0-9]+", "_", (s or "asset").lower()).strip("_")[:48] or "asset"


class _Lock:
    def __enter__(self):
        os.makedirs(ROOT, exist_ok=True); self.f = open(path(".index.lock"), "w"); fcntl.flock(self.f, fcntl.LOCK_EX); return self
    def __exit__(self, *a): fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()


def load_index():
    try: return json.load(open(path("index.json")))
    except (OSError, ValueError): return {"assets": []}


def _save_index(idx):
    tmp = path("index.json.tmp"); json.dump(idx, open(tmp, "w"), indent=1); os.replace(tmp, path("index.json"))


def new_id(): return "mc3d-" + uuid.uuid4().hex[:10]


def add(src_dir, result, meta, asset_id=None):
    """Copy a finished Blender job directory into the library as a new asset (or a new
    version of `asset_id`) and write asset.json. Returns the asset metadata."""
    with _Lock():
        idx = load_index()
        entry = next((a for a in idx["assets"] if a["id"] == asset_id), None) if asset_id else None
        aid = entry["id"] if entry else (asset_id or new_id())
        ver = (entry["latest"] + 1) if entry else 1
        dest = path("assets", aid, f"v{ver}")
        os.makedirs(dest, exist_ok=True)
        for name in os.listdir(src_dir):
            if name.startswith("_") and name not in ("_result.json",): continue
            s = os.path.join(src_dir, name); d = os.path.join(dest, name)
            (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, d)
        rel = lambda p: os.path.relpath(p.replace(src_dir, dest), dest) if p else None
        files = {}
        for fmt, p in (result.get("files") or {}).items():
            q = p.replace(src_dir, dest)
            if os.path.exists(q): files[fmt] = {"path": os.path.relpath(q, dest), "bytes": os.path.getsize(q), "sha256": sha256(q)}
        # companion files of multi-file formats (gltf .bin + textures, obj .mtl + textures)
        extras = []
        for sub in ("gltf", "obj", "textures"):
            for root, _, fs in os.walk(os.path.join(dest, sub)):
                for f in fs: extras.append(os.path.relpath(os.path.join(root, f), dest))
        prev = result.get("previews") or {}
        st = result.get("stats") or {}
        md = {
            "id": aid, "version": ver, "name": meta.get("name") or aid, "slug": meta.get("slug"),
            "kind": meta.get("kind"), "brief": meta.get("brief"), "tags": meta.get("tags", []),
            "source_tool": meta.get("source_tool"), "pipeline": meta.get("pipeline", []),
            "generation": meta.get("generation", {}), "route": meta.get("route"),
            "license": meta.get("license", {}), "provenance": dict(meta.get("provenance", {}), created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            "geometry": {k: st.get(k) for k in ("triangles", "vertices", "meshes", "dimensions_m", "bounds_min", "bounds_max")},
            "materials": st.get("materials", []), "textures": st.get("textures", []),
            "rig": st.get("rig"), "animations": st.get("animations", []), "sockets": st.get("sockets", []),
            "previews": {"thumbnail": rel(prev.get("thumbnail")), "hero": rel(prev.get("hero")), "turntable": [rel(p) for p in prev.get("turntable", [])]},
            "files": files, "companion_files": sorted(extras),
            "validation": meta.get("validation", {"status": "not run"}), "engine": ENGINE,
            "job": meta.get("job"), "stages": result.get("stages", []),
        }
        json.dump(md, open(os.path.join(dest, "asset.json"), "w"), indent=1)
        summary = {"id": aid, "name": md["name"], "slug": md["slug"], "kind": md["kind"], "source_tool": md["source_tool"],
                   "latest": ver, "versions": (entry["versions"] if entry else []) + [ver], "tags": md["tags"],
                   "thumbnail": f"assets/{aid}/v{ver}/{md['previews']['thumbnail']}" if md["previews"]["thumbnail"] else None,
                   "triangles": md["geometry"]["triangles"], "animations": len(md["animations"]),
                   "validation": md["validation"].get("status"), "updated": md["provenance"]["created"], "brief": md["brief"]}
        idx["assets"] = [a for a in idx["assets"] if a["id"] != aid] + [summary]
        _save_index(idx)
        return md


def get(asset_id, version=None):
    idx = load_index()
    e = next((a for a in idx["assets"] if a["id"] == asset_id or a["slug"] == asset_id), None)
    if not e: raise KeyError(f"no asset {asset_id}")
    v = version or e["latest"]
    md = json.load(open(path("assets", e["id"], f"v{v}", "asset.json")))
    md["dir"] = path("assets", e["id"], f"v{v}")
    return md


def file_path(md, fmt):
    f = md["files"].get(fmt)
    if not f: raise KeyError(f"{md['id']} v{md['version']} has no {fmt} export (has {', '.join(md['files'])})")
    return os.path.join(md["dir"], f["path"])


def search(query="", kind=None, tool=None, status=None, limit=50):
    q = (query or "").lower().split()
    out = []
    for a in load_index()["assets"]:
        hay = " ".join(str(a.get(k) or "") for k in ("id", "name", "slug", "kind", "source_tool", "brief")).lower() + " " + " ".join(a.get("tags", []))
        if q and not all(w in hay for w in q): continue
        if kind and a.get("kind") != kind: continue
        if tool and tool not in (a.get("source_tool") or ""): continue
        if status and a.get("validation") != status: continue
        out.append(a)
    return sorted(out, key=lambda a: a["updated"], reverse=True)[:limit]


def snapshot(dest, probe=None):
    """Copy the whole library (index, every asset version, job records, machine probe) to `dest`,
    without the per-job scratch folders. Used to publish or archive a run."""
    if os.path.isdir(dest): shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, "jobs"))
    shutil.copy2(path("index.json"), dest)
    shutil.copytree(path("assets"), os.path.join(dest, "assets"))
    for f in os.listdir(path("jobs")):
        if f.endswith(".json"): shutil.copy2(path("jobs", f), os.path.join(dest, "jobs"))
    if probe is not None: json.dump(probe, open(os.path.join(dest, "probe.json"), "w"), indent=1)
    return {"dest": dest, "assets": len(load_index()["assets"]),
            "bytes": sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dest) for f in fs)}


def export(asset_id, dest, version=None, formats=None):
    """Copy an asset (exports + textures + previews + asset.json) into `dest`/<slug>_v<N>/."""
    md = get(asset_id, version)
    out = os.path.join(dest, f"{md['slug']}_v{md['version']}")
    os.makedirs(out, exist_ok=True)
    copied = []
    want = formats or list(md["files"])
    for fmt in want:
        if fmt not in md["files"]: continue
        src = file_path(md, fmt)
        if fmt in ("gltf", "obj"):
            d = os.path.join(out, fmt); shutil.copytree(os.path.dirname(src), d, dirs_exist_ok=True); copied.append(d)
        else:
            shutil.copy2(src, out); copied.append(os.path.join(out, os.path.basename(src)))
    for sub in ("textures", "previews"):
        s = os.path.join(md["dir"], sub)
        if os.path.isdir(s): shutil.copytree(s, os.path.join(out, sub), dirs_exist_ok=True); copied.append(os.path.join(out, sub))
    shutil.copy2(os.path.join(md["dir"], "asset.json"), out)
    return {"asset": md["id"], "version": md["version"], "dir": out, "copied": copied}
