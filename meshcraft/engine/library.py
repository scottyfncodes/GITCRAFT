"""MeshCraft's versioned asset library. Standard library only.

Layout ($GITCRAFT_MESHCRAFT_LIBRARY, default ~/.gitcraft/meshcraft-library; the sandbox gives
MeshCraft read-write access to it, like LightCraft's library):

  index.json                              one summary per asset (search reads only this)
  assets/<asset_id>/v<N>/asset.json       full record of that version: files with SHA-256,
                                          inputs, brief, validation, job, provenance
  assets/<asset_id>/v<N>/{source,exports,previews}/...
  jobs/<job_id>.json                      job records (engine/jobs.py)

Every run_pipeline / blockbench_import / mixamo_apply adds a version. A version whose content
matches the previous one says so (`same_as`), so a re-run is visibly a no-op. `export()` copies a
version into an authorized root and re-hashes every copied file: the handoff to a game repo.
Ported from the 3D Department proposal (GITCRAFT PR #9) and adapted to MeshCraft's reports.
"""
import fcntl, hashlib, json, os, shutil, struct, time

ROOT = os.path.expanduser(os.environ.get("GITCRAFT_MESHCRAFT_LIBRARY") or
                          os.path.join(os.environ.get("GITCRAFT_HOME", "~/.gitcraft"), "meshcraft-library"))
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
        _write_json(os.path.join(dest, "asset.json"), md)
        thumb = next((r["path"] for r in recs if r["kind"] == "preview" and "three_quarter" in r["path"]),
                     next((r["path"] for r in recs if r["kind"] == "preview"), None))
        s = {"id": asset_id, "latest": ver, "versions": (entry["versions"] if entry else []) + [ver], "tool": md["tool"],
             "template": md["template"], "tags": md["tags"], "validation": status, "triangles": tri, "clips": clips,
             "thumbnail": f"assets/{asset_id}/v{ver}/{thumb}" if thumb else None, "updated": md["created"],
             "title": (md["brief"] or {}).get("title") or asset_id}
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


def search(query="", template=None, tool=None, status=None, limit=50):
    words = (query or "").lower().split(); out = []
    for a in load_index()["assets"]:
        hay = " ".join(str(a.get(k) or "") for k in ("id", "title", "template", "tool")).lower() + " " + " ".join(a.get("tags", [])).lower()
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
