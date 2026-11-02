#!/usr/bin/env python3
"""3D Department UI: live server and static snapshot publisher (standard library only).

  python3 forgecraft/ui_server.py [--port 8765]           live: the UI runs real pipeline jobs on this machine
  python3 forgecraft/ui_server.py --publish <library> <dist> [--source LABEL]
                                                          snapshot: static site (UI + state.json + asset files)

Live API: GET /api/state · POST /api/generate · /api/compose · /api/retry · /api/mixamo_prepare.
It binds to 127.0.0.1 only: it can run Blender and write files, so it is not for the internet."""
import base64, http.server, json, os, shutil, socketserver, sys, threading, time, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hardware, library, pipeline, routing
from backends import blockbench, mixamo

UI = os.path.join(HERE, "ui")
JOB_KEYS = ("id", "spec", "status", "created", "updated", "attempts", "stages", "error", "asset", "plan", "compute")


def state(lib_root, base_url, probe=None, mode="live", source=""):
    idx = json.load(open(os.path.join(lib_root, "index.json"))) if os.path.exists(os.path.join(lib_root, "index.json")) else {"assets": []}
    assets = []
    for e in idx["assets"]:
        vs = {}
        for v in e["versions"]:
            p = os.path.join(lib_root, "assets", e["id"], f"v{v}", "asset.json")
            if not os.path.exists(p): continue
            md = json.load(open(p)); md["base"] = f"{base_url}assets/{e['id']}/v{v}/"
            vs[str(v)] = md
        if vs: assets.append({"id": e["id"], "latest": str(max(map(int, vs))), "versions": vs})
    jobs = []
    jd = os.path.join(lib_root, "jobs")
    if os.path.isdir(jd):
        for f in sorted(os.listdir(jd), reverse=True):
            if f.endswith(".json"):
                try:
                    j = json.load(open(os.path.join(jd, f)))
                    if j.get("spec") and j["spec"].get("uploads"): j["spec"] = dict(j["spec"], uploads=f"{len(j['spec']['uploads'])} file(s)")
                    jobs.append({k: j.get(k) for k in JOB_KEYS})
                except ValueError: pass
    return {"mode": mode, "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": source,
            "probe": probe or hardware.probe(), "rules": routing.RULES, "bb_templates": sorted(blockbench.TEMPLATES),
            "mixamo": {"steps": mixamo.GUIDE, "bones": ["mixamorig:" + b for b in mixamo.MIXAMO_CORE]}, "assets": assets, "jobs": jobs}


def publish(lib_root, dist, source=""):
    """Write a static snapshot: UI + data/state.json + the library's asset files (no job work dirs)."""
    if os.path.isdir(dist): shutil.rmtree(dist)
    shutil.copytree(UI, dist, ignore=shutil.ignore_patterns("dist"))
    data = os.path.join(dist, "data"); os.makedirs(data)
    if os.path.isdir(os.path.join(lib_root, "assets")): shutil.copytree(os.path.join(lib_root, "assets"), os.path.join(data, "assets"))
    probe_file = os.path.join(lib_root, "probe.json")
    probe = json.load(open(probe_file)) if os.path.exists(probe_file) else hardware.probe()
    st = state(lib_root, "data/", probe, mode="snapshot", source=source)
    json.dump(st, open(os.path.join(data, "state.json"), "w"), default=str)
    total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(dist) for f in fs)
    print(f"published {len(st['assets'])} assets, {len(st['jobs'])} jobs to {dist} ({total / 2**20:.1f} MB)")


RUNNING = {}


def start(spec):
    job = pipeline.Job(spec); job.save()
    t = threading.Thread(target=pipeline.run, args=(None, job.id), daemon=True); t.start()
    RUNNING[job.id] = t
    return job.id


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=UI, **k)

    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, default=str).encode()
        self.send_response(code); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def translate_path(self, path):
        p = urllib.parse.unquote(urllib.parse.urlparse(path).path)
        if p.startswith("/library/"):
            full = os.path.realpath(os.path.join(library.ROOT, p[len("/library/"):]))
            return full if full.startswith(os.path.realpath(library.ROOT) + os.sep) else "/nonexistent"
        return super().translate_path(path)

    def do_GET(self):
        if self.path.startswith("/api/state"): return self._json(state(library.ROOT, "/library/", mode="live", source="this machine"))
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("content-length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path == "/api/generate":
                spec = {k: v for k, v in body.items() if v not in (None, "") and k != "uploads"}
                if body.get("uploads"):
                    up = os.path.join(library.ROOT, "uploads", time.strftime("%Y%m%d-%H%M%S")); os.makedirs(up, exist_ok=True)
                    spec["images"] = []
                    for u in body["uploads"]:
                        fn = os.path.join(up, os.path.basename(u["name"]))
                        open(fn, "wb").write(base64.b64decode(u["data"].split(",", 1)[1])); spec["images"].append(fn)
                return self._json({"job": start(spec)})
            if self.path == "/api/compose":
                return self._json({"job": start(dict(body, tool="blender_scene", brief=body.get("name", "") + " scene"))})
            if self.path == "/api/retry":
                job_id = body["job"]; t = threading.Thread(target=pipeline.retry, args=(job_id,), daemon=True); t.start(); return self._json({"job": job_id})
            if self.path == "/api/mixamo_prepare":
                import server; r = server.call("mixamo_prepare_upload", {"asset": body["asset"], "out": os.path.join(library.ROOT, "uploads", body["asset"] + "_mixamo_upload.fbx")})
                return self._json({"job": "-", "fbx": r["fbx"]})
        except Exception as e:
            return self._json({"error": f"{type(e).__name__}: {e}"}, 400)
        self._json({"error": "unknown endpoint"}, 404)


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--publish" in a:
        i = a.index("--publish"); src = a[a.index("--source") + 1] if "--source" in a else ""
        publish(a[i + 1], a[i + 2], src)
    else:
        port = int(a[a.index("--port") + 1]) if "--port" in a else 8765
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        with socketserver.ThreadingTCPServer(("127.0.0.1", port), H) as srv:
            print(f"GITCRAFT 3D Department (live): http://127.0.0.1:{port}  library: {library.ROOT}")
            srv.serve_forever()
