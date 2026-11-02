"""The 3D Department's versioned asset library: one library for MeshCraft and ForgeCraft.
Standard library only.

Location: $GITCRAFT_3D_LIBRARY (scripts/tools.sh sets it for both servers; the sandbox gives
both read-write access). Older variables still work: GITCRAFT_MESHCRAFT_LIBRARY,
FORGECRAFT_LIBRARY. Default ~/.gitcraft/3d-library, or ~/.gitcraft/meshcraft-library when that
exists from before the consolidation (same format, so it is used in place, never copied).
Layout:

  index.json                              one summary per asset (search reads only this)
  assets/<asset_id>/v<N>/asset.json       full record of that version: files with SHA-256,
                                          inputs, brief, validation, job, provenance
  assets/<asset_id>/v<N>/{source,exports,previews}/...
  jobs/<job_id>.json                      job records (engine/jobs.py)

Every run_pipeline / blockbench_import / mixamo_apply adds a version. A version whose content
matches the previous one says so (`same_as`), so a re-run is visibly a no-op. `export()` copies a
version into an authorized root and re-hashes every copied file: the handoff to a game repo.
Every version is written by the tool that produced it (a MeshCraft job); ForgeCraft adds its
orchestration record to the same version with annotate() (routing decision, backend, licences,
provenance, previews, geometry), so each asset has exactly one record.
"""
import fcntl, hashlib, json, os, shutil, struct, time

def _default_root():
    home = os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft"))
    new, legacy = os.path.join(home, "3d-library"), os.path.join(home, "meshcraft-library")
    return legacy if os.path.isdir(legacy) and not os.path.isdir(new) else new


ROOT = os.path.expanduser(os.environ.get("GITCRAFT_3D_LIBRARY") or os.environ.get("GITCRAFT_MESHCRAFT_LIBRARY")
                          or os.environ.get("FORGECRAFT_LIBRARY") or _default_root())
ANNOTATION_KEYS = ("title", "kind", "source_tool", "route", "license", "provenance", "generation", "engine", "geometry",
                   "previews", "animations", "rig", "sockets", "textures", "orchestration", "engine_check", "deliverable_validation")
SUBDIR = {"blend": "source", "export": "exports", "lod": "exports", "collision": "exports", "sidecar": "exports",
          "preview": "previews", "contact_sheet": "previews", "report": "."}


def path(*p): return os.path.join(ROOT, *p)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def content_hash(p):
    """Hash that ignores what legitimately varies between identical builds: the brief stored in a
    GLB's scene extras (it names the out_dir). FBX embeds a timestamp and random ids: size only."""
    if p.endswith(".glb"):
        b = open(p, "rb").read()
        try:
            n = struct.unpack("<I", b[12:16])[0]; j = json.loads(b[20:20 + n])
            for sc in j.get("scenes", []): sc.pop("extras", None)
            return hashlib.sha256(json.dumps(j, sort_keys=True).encode() + b[20 + n:]).hexdigest()
        except Exception:
            pass
    if p.endswith(".fbx"): return f"fbx-size:{os.path.getsize(p)}"
    return sha256(p)


class _Lock:
    def __enter__(self):
        os.makedirs(ROOT, exist_ok=True); self.f = open(path(".lock"), "w"); fcntl.flock(self.f, fcntl.LOCK_EX); return self
    def __exit__(self, *a): fcntl.flock(self.f, fcntl.LOCK_UN); self.f.close()


def load_index():
    try:
        with open(path("index.json")) as f: return json.load(f)
    except (OSError, ValueError):
        return {"assets": []}


def _write_json(p, data):
    tmp = p + ".tmp"
    with open(tmp, "w") as f: json.dump(data, f, indent=1, default=str)
    os.replace(tmp, p)


def files_from_result(res):
    """[(path, kind)] for every deliverable a MeshCraft result names (run_pipeline report,
    blockbench_import or mixamo_apply result)."""
    out = []
    def add(p, kind):
        if isinstance(p, str) and os.path.isfile(p) and p not in [x for x, _ in out]: out.append((p, kind))
    b = res.get("build", {}).get("blend") or res.get("blend")
    add(b["path"] if isinstance(b, dict) else b, "blend")
    for e in res.get("exports", []):
        add(e.get("path"), "export")
        for x in e.get("extras", []) + e.get("sidecars", []): add(x.get("path"), x.get("kind", "sidecar"))
        for p in (e.get("bake") or {}).get("maps", {}).values(): add(p, "sidecar")
    for r in res.get("previews", []): add(r.get("path") if isinstance(r, dict) else r, "preview")
    add(res.get("report"), "report")
    return out


def add_version(asset_id, res, meta):
    """Copy a result's deliverables into a new version. meta: tool, template, brief, inputs[], job, tags."""
    files = files_from_result(res)
    if not files: raise ValueError("nothing to add to the library: the result names no files")
    with _Lock():
        idx = load_index()
        entry = next((a for a in idx["assets"] if a["id"] == asset_id), None)
        ver = (entry["latest"] + 1) if entry else 1
        dest = path("assets", asset_id, f"v{ver}")
        os.makedirs(dest, exist_ok=True)
        recs = []
        for src, kind in files:
            sub = SUBDIR.get(kind, "exports")
            d = os.path.normpath(os.path.join(dest, sub, os.path.basename(src))); os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(src, d)
            h = sha256(d)
            if h != sha256(src): raise IOError(f"copy of {src} does not match its source")
            recs.append({"path": os.path.relpath(d, dest), "kind": kind, "bytes": os.path.getsize(d), "sha256": h,
                         "content": content_hash(d), "source": src})
        same_as = None
        if entry:
            prev = get(asset_id, entry["latest"])
            key = lambda rs: sorted((r["path"], r["content"]) for r in rs if r["kind"] in ("export", "lod", "collision", "sidecar"))
            if key(prev["files"]) and key(prev["files"]) == key(recs): same_as = entry["latest"]
        summary = (res.get("validation") or {}).get("summary") or {}
        status = "not validated" if not summary else ("pass" if summary.get("fail", 0) == 0 else "needs-fix")
        tri = next((c.get("tris") for c in (res.get("validation") or {}).get("checks", []) if c.get("check") == "triangle_budget"), None)
        clips = (res.get("build") or {}).get("actions") or [c["clip"] for c in res.get("clips", [])]
        md = {"id": asset_id, "version": ver, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "tool": meta.get("tool"), "template": meta.get("template"), "tags": meta.get("tags", []),
              "brief": meta.get("brief"), "job": meta.get("job"), "same_as": same_as,
              "inputs": [{"path": p, "sha256": sha256(p)} for p in meta.get("inputs", []) if isinstance(p, str) and os.path.isfile(p)],
              "validation": {"status": status, "summary": summary}, "triangles": tri, "clips": clips,
              "contract": (res.get("build") or {}).get("contract"), "files": recs}
        md.update({k: meta[k] for k in ANNOTATION_KEYS if k in meta})
        _write_json(os.path.join(dest, "asset.json"), md)
        thumb = next((r["path"] for r in recs if r["kind"] == "preview" and "three_quarter" in r["path"]),
                     next((r["path"] for r in recs if r["kind"] == "preview"), None))
        s = {"id": asset_id, "latest": ver, "versions": (entry["versions"] if entry else []) + [ver], "tool": md["tool"],
             "template": md["template"], "tags": md["tags"], "validation": status, "triangles": tri, "clips": clips,
             "thumbnail": f"assets/{asset_id}/v{ver}/{thumb}" if thumb else None, "updated": md["created"],
             "title": meta.get("title") or (md["brief"] or {}).get("title") or asset_id, "kind": meta.get("kind")}
        idx["assets"] = [a for a in idx["assets"] if a["id"] != asset_id] + [s]
        _write_json(path("index.json"), idx)
    return dict(md, dir=dest)


def get(asset_id, version=None):
    e = next((a for a in load_index()["assets"] if a["id"] == asset_id), None)
    if not e: raise KeyError(f"no asset `{asset_id}` in the library ({ROOT})")
    v = int(version or e["latest"])
    if v not in e["versions"]: raise KeyError(f"`{asset_id}` has versions {e['versions']}, not {v}")
    d = path("assets", asset_id, f"v{v}")
    with open(os.path.join(d, "asset.json")) as f: md = json.load(f)
    return dict(md, dir=d, versions=e["versions"])


def annotate(asset_id, version, info):
    """Merge orchestration info (ForgeCraft) into an existing version's asset.json and its index
    summary. Only ANNOTATION_KEYS and tags are accepted; produced files are never touched."""
    with _Lock():
        idx = load_index()
        e = next((a for a in idx["assets"] if a["id"] == asset_id), None)
        if not e or int(version) not in e["versions"]: raise KeyError(f"no version {version} of `{asset_id}`")
        p = path("assets", asset_id, f"v{int(version)}", "asset.json")
        with open(p) as f: md = json.load(f)
        bad = [k for k in info if k not in ANNOTATION_KEYS + ("tags",)]
        if bad: raise ValueError(f"annotate: unknown keys {bad}")
        for k, v in info.items():
            if k == "tags": md["tags"] = sorted(set(md.get("tags", [])) | set(v))
            else: md[k] = v
        _write_json(p, md)
        if int(version) == e["latest"]:
            for k in ("title", "kind", "source_tool"):
                if info.get(k): e[k] = info[k]
            if info.get("previews", {}).get("thumbnail"): e["thumbnail"] = f"assets/{asset_id}/v{int(version)}/{info['previews']['thumbnail']}"
            if "tags" in info: e["tags"] = md["tags"]
            if info.get("deliverable_validation"): e["deliverable_validation"] = info["deliverable_validation"].get("status")
            _write_json(path("index.json"), idx)
    return dict(md, dir=os.path.dirname(p))


def snapshot(dest, probe=None):
    """Copy the whole library (index, every asset version, job records, machine probe) to dest,
    without job scratch folders. Used to publish the department UI or archive a run."""
    if os.path.isdir(dest): shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, "jobs"))
    shutil.copy2(path("index.json"), dest)
    shutil.copytree(path("assets"), os.path.join(dest, "assets"))
    jd = path("jobs")
    for f in (os.listdir(jd) if os.path.isdir(jd) else []):
        if f.endswith(".json"): shutil.copy2(os.path.join(jd, f), os.path.join(dest, "jobs"))
    if probe is not None: _write_json(os.path.join(dest, "probe.json"), probe)
    return {"dest": dest, "assets": len(load_index()["assets"]),
            "bytes": sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dest) for f in fs)}


def unique_id(base):
    """`base`, or base_2, base_3… if an asset with that id already exists (new assets, not versions)."""
    ids = {a["id"] for a in load_index()["assets"]}
    if base not in ids: return base
    n = 2
    while f"{base}_{n}" in ids: n += 1
    return f"{base}_{n}"


def search(query="", template=None, tool=None, status=None, limit=50):
    words = (query or "").lower().split(); out = []
    for a in load_index()["assets"]:
        hay = " ".join(str(a.get(k) or "") for k in ("id", "title", "template", "tool", "kind", "source_tool")).lower() + " " + " ".join(a.get("tags", [])).lower()
        if words and not all(w in hay for w in words): continue
        if template and a.get("template") != template: continue
        if tool and tool not in (a.get("tool") or ""): continue
        if status and a.get("validation") != status: continue
        out.append(a)
    return {"library": ROOT, "count": len(out), "assets": sorted(out, key=lambda a: a["updated"], reverse=True)[:int(limit)]}


def export(asset_id, dest, version=None, kinds=None):
    """Copy a version into dest/<asset_id>_v<N>/ (keeping source/exports/previews), re-hash every copy."""
    md = get(asset_id, version)
    out = os.path.join(dest, f"{asset_id}_v{md['version']}")
    copied, bad = [], []
    for r in md["files"]:
        if kinds and r["kind"] not in kinds: continue
        s = os.path.join(md["dir"], r["path"]); d = os.path.normpath(os.path.join(out, r["path"]))
        os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copy2(s, d)
        h = sha256(d)
        (copied if h == r["sha256"] else bad).append({"path": d, "sha256": h})
    rec = {k: v for k, v in md.items() if k not in ("dir", "versions")}
    _write_json(os.path.join(out, "asset.json"), rec)
    if bad: raise IOError(f"{len(bad)} copied files do not match the library hashes: {bad[:3]}")
    return {"asset": asset_id, "version": md["version"], "dir": out, "files": copied, "verified": True}
