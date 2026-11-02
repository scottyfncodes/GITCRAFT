#!/usr/bin/env python3
"""GITCRAFT control room: a local web UI for every GITCRAFT tool. Standard library only.

    scripts/ui.sh [--port 8765]                   serve on 127.0.0.1 and print the URL (with its token)
    python3 ui/server.py --snapshot DIR           write a read-only snapshot (data + files) for previews

It is an additional interface, not a new engine:
  * every action is an MCP call through scripts/mcp.sh, exactly as Claude Code makes it, so
    the guard (paths, deny list, audit log) and the Landlock sandbox apply unchanged;
  * reads that need no tool (job records, the MeshCraft library index, the audit counters) are
    read-only file reads; file previews are served only from the workspace roots and the
    library, only for an allowlist of media types, with a sandboxing CSP;
  * it listens on 127.0.0.1 only. Each launch makes a random token; every /api request must
    carry it, come from this origin (Origin and Host are checked, which stops other web pages
    and DNS-rebinding), and post JSON. Previews use a SameSite=Strict cookie.
"""
import argparse, base64, hashlib, hmac, http.server, json, mimetypes, os, queue, re, secrets, shutil, socketserver
import subprocess, sys, threading, time, urllib.parse, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATIC = os.path.join(HERE, "static")
MCP = os.path.join(REPO, "scripts", "mcp.sh")
THREE = os.path.join(REPO, "meshcraft", "engine_check", "node_modules", "three")
FILE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
              ".svg": "image/svg+xml", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".bin": "application/octet-stream",
              ".json": "application/json", ".txt": "text/plain", ".pdf": "application/pdf", ".mp4": "video/mp4"}
QUICK = {"route", "hardware_probe", "jobs_list", "job_get", "library_search", "library_get", "library_export",
         "blockbench_build", "blockbench_inspect", "mixamo_guide"}      # MeshCraft tools that never load Blender
MAX_BODY = 1 << 20


# ------------------------------------------------------------------ configuration (from scripts/tools.sh)
def gitcraft_config():
    """Tool list, roots, policy and paths, exactly as the launcher computes them."""
    script = r'''
source "$1/scripts/tools.sh"
printf 'HOME=%s\nBIN=%s\nLOG=%s\nROOT=%s\nROOTS=%s\nSANDBOX=%s\nNET=%s\nMESH=%s\n' "$GITCRAFT_HOME" "$GITCRAFT_BIN" "$GITCRAFT_LOG" \
  "$GITCRAFT_ROOT" "$GITCRAFT_ROOTS" "$GITCRAFT_SANDBOX" "$GITCRAFT_ALLOW_NET" "$GITCRAFT_MESHCRAFT"
for e in "${GITCRAFT_TOOLS[@]}" ${GITCRAFT_EXTRA_TOOLS[@]+"${GITCRAFT_EXTRA_TOOLS[@]}"}; do
  IFS=: read -r n r p <<<"$e"; printf 'TOOL=%s:%s:%s:%s\n' "$n" "$r" "$p" "$(gitcraft_denied "$n")"
done'''
    out = subprocess.run(["bash", "-c", script, "_", REPO], capture_output=True, text=True, timeout=20, env=os.environ).stdout
    cfg = {"tools": []}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        if k == "TOOL":
            n, r, p, d = (v.split(":") + ["", "", "", ""])[:4]
            cfg["tools"].append({"name": n, "repo": r, "package": p, "denied": d.split()})
        elif k: cfg[k.lower()] = v
    cfg["roots"] = [os.path.realpath(r) for r in cfg.get("roots", "").split(":") if r]
    cfg["library"] = os.path.realpath(os.environ.get("GITCRAFT_MESHCRAFT_LIBRARY") or os.path.join(cfg["home"], "meshcraft-library"))
    return cfg


# ------------------------------------------------------------------ MCP clients through scripts/mcp.sh
class Client:
    def __init__(self, tool, log):
        self.tool = tool; self.lock = threading.Lock(); self.used = time.time(); self.id = 0; self.q = queue.Queue()
        self.p = subprocess.Popen([MCP, tool], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=open(log, "ab"), bufsize=0)
        threading.Thread(target=self._read, daemon=True).start()
        self.info = self.req("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "gitcraft-ui", "version": "1"}}, 60)
        self.p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')

    def _read(self):
        for line in self.p.stdout:
            try: self.q.put(json.loads(line))
            except Exception: pass
        self.q.put(None)

    def alive(self): return self.p.poll() is None

    def req(self, method, params=None, timeout=300):
        self.id += 1; i = self.id
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}) + "\n").encode())
        end = time.time() + timeout
        while True:
            try: m = self.q.get(timeout=max(1, end - time.time()))
            except queue.Empty: raise TimeoutError(f"{self.tool} did not answer {method} within {timeout} s")
            if m is None: raise RuntimeError(f"{self.tool} exited (see the UI log)")
            if m.get("id") == i:
                if "error" in m: raise RuntimeError(json.dumps(m["error"]))
                return m["result"]

    def close(self):
        try: self.p.stdin.close(); self.p.wait(10)
        except Exception: self.p.kill()


class Pool:
    """One MCP client per tool (plus a second MeshCraft client for tools that never load Blender,
    so browsing and advice stay responsive while a pipeline runs). Idle clients are closed."""
    def __init__(self, log, idle=900):
        self.log, self.idle, self.clients, self.lock = log, idle, {}, threading.Lock()
        self.tools_cache = {}
        threading.Thread(target=self._reaper, daemon=True).start()

    def get(self, key):
        tool = key.split("#")[0]
        with self.lock:
            c = self.clients.get(key)
            if c is None or not c.alive():
                c = self.clients[key] = Client(tool, self.log)
            c.used = time.time()
            return c

    def _reaper(self):
        while True:
            time.sleep(30)
            with self.lock:
                for k, c in list(self.clients.items()):
                    if time.time() - c.used > self.idle and not c.lock.locked():
                        c.close(); del self.clients[k]

    def tools(self, tool):
        c = self.get(tool)
        with c.lock:
            t = c.req("tools/list", timeout=60)["tools"]
        self.tools_cache[tool] = {"tools": t, "server": c.info.get("serverInfo", {}), "instructions": c.info.get("instructions"), "at": time.time()}
        return self.tools_cache[tool]

    def call(self, tool, name, args, timeout=3600):
        key = tool + ("#quick" if tool == "meshcraft" and name in QUICK else "")
        c = self.get(key)
        with c.lock:
            r = c.req("tools/call", {"name": name, "arguments": args or {}}, timeout)
        txt = "\n".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
        try: val = json.loads(txt)
        except Exception: val = txt
        return {"ok": not r.get("isError"), "result": val}

    def status(self):
        with self.lock:
            return {k: {"alive": c.alive(), "busy": c.lock.locked(), "idle_s": int(time.time() - c.used)} for k, c in self.clients.items()}

    def close(self):
        with self.lock:
            for c in self.clients.values(): c.close()
            self.clients.clear()


class Calls:
    """Tool calls run in the background; the page polls them."""
    def __init__(self, pool):
        self.pool, self.items, self.lock = pool, {}, threading.Lock()

    def start(self, tool, name, args):
        cid = "call-" + uuid.uuid4().hex[:10]
        rec = {"id": cid, "tool": tool, "name": name, "args": args, "status": "running", "started": time.time()}
        with self.lock:
            self.items[cid] = rec
            for k in sorted(self.items, key=lambda k: self.items[k]["started"])[:-200]: self.items.pop(k)
        def run():
            try:
                r = self.pool.call(tool, name, args)
                rec.update(status="done" if r["ok"] else "error", result=r["result"])
            except Exception as e:
                rec.update(status="error", result=f"{type(e).__name__}: {e}")
            rec["finished"] = time.time()
        threading.Thread(target=run, daemon=True).start()
        return rec

    def get(self, cid):
        r = self.items.get(cid)
        if r is None: raise KeyError(f"no call {cid}")
        return r

    def recent(self):
        return sorted(({k: v for k, v in r.items() if k != "result"} for r in self.items.values()), key=lambda r: -r["started"])[:50]


# ------------------------------------------------------------------ read-only views of state on disk
def _json(p, default=None):
    try:
        with open(p) as f: return json.load(f)
    except (OSError, ValueError):
        return default


def registered():
    cj = _json(os.path.expanduser("~/.claude.json"), {}) or {}
    names = set(cj.get("mcpServers", {}))
    for proj in (cj.get("projects") or {}).values():
        names |= set((proj or {}).get("mcpServers", {}))
    return names


def audit_counts(cfg):
    p = os.path.join(cfg["log"], "audit.jsonl"); c = f = r = 0; per = {}
    try:
        with open(p) as fh:
            for line in fh:
                try: d = json.loads(line)
                except ValueError: continue
                c += 1; s = d.get("server", "?"); per.setdefault(s, {"calls": 0, "failed": 0, "refused": 0}); per[s]["calls"] += 1
                if d.get("refused"): r += 1; per[s]["refused"] += 1
                elif not d.get("ok", True): f += 1; per[s]["failed"] += 1
    except OSError:
        pass
    return {"calls": c, "failed": f, "refused": r, "per_tool": per, "path": p}


def landlock():
    try:
        import ctypes
        libc = ctypes.CDLL(None, use_errno=True)
        abi = libc.syscall(444, None, 0, 1)
        return abi if abi > 0 else None
    except Exception:
        return None


def overview(cfg, pool):
    status = _json(os.path.join(cfg["home"], "status.json"), {}) or {}
    reg = registered(); tools = []
    for t in cfg["tools"]:
        n = t["name"]
        inst = os.path.exists(os.path.join(cfg["home"], "meshcraft", "venv", "bin", "python")) if n == "meshcraft" else os.path.exists(os.path.join(cfg["bin"], t["package"]))
        ver = None
        try:
            with open(os.path.join(cfg["bin"], n + ".version")) as f: ver = f.read().strip()
        except OSError:
            pass
        cache = pool.tools_cache.get(n)
        tools.append({**t, "installed": inst, "registered": n in reg, "version": ver, "install_state": (status.get("tools", {}).get(n) or {}).get("state"),
                      "tool_count": len(cache["tools"]) if cache else None, "server": (cache or {}).get("server")})
    abi = landlock()
    return {"tools": tools, "roots": cfg["roots"], "library": cfg["library"], "sandbox": {"mode": cfg["sandbox"], "landlock_abi": abi},
            "network": "allowed (GITCRAFT_ALLOW_NET=1)" if cfg.get("net") == "1" else "denied", "audit": audit_counts(cfg),
            "status_updated": status.get("updated"), "clients": pool.status(), "repo": REPO}


def jobs_list(cfg, limit=100):
    d = os.path.join(cfg["library"], "jobs"); out = []
    for f in (os.listdir(d) if os.path.isdir(d) else []):
        if f.endswith(".json"):
            r = _json(os.path.join(d, f))
            if r: out.append({k: r.get(k) for k in ("id", "tool", "asset_id", "status", "created", "updated", "error", "fallback", "library")} |
                             {"attempts": len(r.get("attempts", []))})
    return {"jobs": sorted(out, key=lambda r: r.get("created") or "", reverse=True)[:limit]}


def job_get(cfg, jid):
    if not re.fullmatch(r"job-[\w-]+", jid or ""): raise KeyError("bad job id")
    r = _json(os.path.join(cfg["library"], "jobs", jid + ".json"))
    if r is None: raise KeyError(f"no job {jid}")
    return r


def library_index(cfg):
    idx = _json(os.path.join(cfg["library"], "index.json"), {"assets": []}) or {"assets": []}
    return {"library": cfg["library"], "assets": sorted(idx.get("assets", []), key=lambda a: a.get("updated") or "", reverse=True)}


def library_asset(cfg, aid, version=None):
    if not re.fullmatch(r"[\w-]+", aid or ""): raise KeyError("bad asset id")
    e = next((a for a in library_index(cfg)["assets"] if a["id"] == aid), None)
    if not e: raise KeyError(f"no asset {aid}")
    v = int(version or e["latest"])
    if v not in e["versions"]: raise KeyError(f"{aid} has no v{v}")
    d = os.path.join(cfg["library"], "assets", aid, f"v{v}")
    md = _json(os.path.join(d, "asset.json"), {}) or {}
    rep = next((os.path.join(d, f["path"]) for f in md.get("files", []) if f["kind"] == "report"), None)
    checks = (_json(rep, {}) or {}).get("validation", {}).get("checks", []) if rep else []
    for f in md.get("files", []): f["abs"] = os.path.join(d, f["path"])
    return dict(md, dir=d, versions=e["versions"], checks=checks)


def list_dir(cfg, path, exts=None):
    real = os.path.realpath(path or cfg["roots"][0])
    if not any(real == r or real.startswith(r + os.sep) for r in cfg["roots"]): raise PermissionError("outside the workspace roots")
    ents = []
    for n in sorted(os.listdir(real))[:500]:
        if n.startswith("."): continue
        p = os.path.join(real, n); isd = os.path.isdir(p)
        if not isd and exts and os.path.splitext(n)[1].lower() not in exts: continue
        ents.append({"name": n, "path": p, "dir": isd, "bytes": None if isd else os.path.getsize(p)})
    parent = os.path.dirname(real)
    up = parent if any(parent == r or parent.startswith(r + os.sep) for r in cfg["roots"]) else None
    return {"path": real, "parent": up, "entries": ents}


def file_allowed(cfg, path):
    real = os.path.realpath(path)
    ext = os.path.splitext(real)[1].lower()
    ok = ext in FILE_TYPES and os.path.isfile(real) and any(real == r or real.startswith(r + os.sep) for r in cfg["roots"] + [cfg["library"]])
    return real if ok else None


# ------------------------------------------------------------------ HTTP
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "gitcraft-ui"

    def log_message(self, fmt, *a):
        self.server.app["access"].write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % a)); self.server.app["access"].flush()

    # --- security gates
    def _host_ok(self):
        h = (self.headers.get("Host") or "").lower(); port = self.server.server_address[1]
        return h in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _origin_ok(self):
        o = self.headers.get("Origin")
        if o is None: return True                      # same-origin GETs and non-browser clients send none
        port = self.server.server_address[1]
        return o in (f"http://127.0.0.1:{port}", f"http://localhost:{port}")

    def _token_ok(self):
        t = self.headers.get("X-GITCRAFT-Token") or ""
        return hmac.compare_digest(t, self.server.app["token"])

    def _cookie_ok(self):
        m = re.search(r"(?:^|;\s*)gc_session=([A-Za-z0-9_-]+)", self.headers.get("Cookie") or "")
        return bool(m) and hmac.compare_digest(m.group(1), self.server.app["cookie"])

    def _send(self, code, body=b"", ctype="application/json", headers=None):
        if isinstance(body, (dict, list)): body = json.dumps(body, default=str).encode()
        elif isinstance(body, str): body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD": self.wfile.write(body)

    def _err(self, code, msg): self._send(code, {"error": msg})

    def _page_headers(self):
        return {"Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; "
                                           "connect-src 'self' blob:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
                "X-Frame-Options": "DENY"}

    # --- routing
    def do_GET(self):
        if not self._host_ok(): return self._err(421, "unexpected Host header (the UI only answers on 127.0.0.1)")
        u = urllib.parse.urlparse(self.path); q = urllib.parse.parse_qs(u.query)
        if u.path.startswith("/api/"):
            if not (self._origin_ok() and self._token_ok()): return self._err(403, "missing or wrong token")
            return self._api_get(u.path, q)
        if u.path == "/files":
            if not self._cookie_ok(): return self._err(403, "open the UI with its token first")
            real = file_allowed(self.server.app["cfg"], (q.get("path") or [""])[0])
            if not real: return self._err(404, "not a previewable file inside the workspace roots or the library")
            with open(real, "rb") as f: data = f.read()
            return self._send(200, data, FILE_TYPES[os.path.splitext(real)[1].lower()],
                              {"Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox", "Cache-Control": "private, max-age=60"})
        if u.path.startswith("/vendor/three/"):
            rel = os.path.normpath(u.path[len("/vendor/three/"):])
            p = os.path.join(THREE, rel)
            if rel.startswith("..") or not p.endswith(".js") or not os.path.isfile(p): return self._err(404, "not found")
            src = open(p, encoding="utf-8").read().replace("from 'three'", "from '/vendor/three/build/three.module.js'")
            return self._send(200, src, "text/javascript; charset=utf-8", {"Cache-Control": "max-age=3600"})
        name = "index.html" if u.path in ("/", "/index.html") else u.path.lstrip("/")
        p = os.path.normpath(os.path.join(STATIC, name))
        if not p.startswith(STATIC + os.sep) or not os.path.isfile(p): return self._err(404, "not found")
        ct = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
              ".svg": "image/svg+xml", ".png": "image/png", ".webmanifest": "application/manifest+json"}.get(os.path.splitext(p)[1], "application/octet-stream")
        with open(p, "rb") as f: data = f.read()
        self._send(200, data, ct, self._page_headers())

    do_HEAD = do_GET

    def do_POST(self):
        if not self._host_ok(): return self._err(421, "unexpected Host header")
        if not self._origin_ok(): return self._err(403, "cross-origin request refused")
        if not self._token_ok(): return self._err(403, "missing or wrong token")
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            return self._err(415, "send application/json")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY: return self._err(413, "request too large")
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except ValueError: return self._err(400, "invalid JSON")
        if not isinstance(body, dict): return self._err(400, "send a JSON object")
        u = urllib.parse.urlparse(self.path).path; app = self.server.app
        try:
            if u == "/api/session":    # trade the token for the preview cookie
                return self._send(200, {"ok": True}, headers={"Set-Cookie": f"gc_session={app['cookie']}; Path=/files; HttpOnly; SameSite=Strict"})
            if u == "/api/call":
                tool, name = body.get("tool"), body.get("name")
                if tool not in {t["name"] for t in app["cfg"]["tools"]}: return self._err(400, f"unknown tool {tool}")
                if not isinstance(name, str) or not name: return self._err(400, "name required")
                args = body.get("arguments") or {}
                if not isinstance(args, dict): return self._err(400, "arguments must be an object")
                return self._send(202, app["calls"].start(tool, name, args))
            if u == "/api/discover":
                tool = body.get("tool")
                names = [tool] if tool else [t["name"] for t in app["cfg"]["tools"]]
                res, ths = {}, []
                def one(n):
                    try: res[n] = {"ok": True, **app["pool"].tools(n)}
                    except Exception as e: res[n] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                for n in names:
                    if n not in {t["name"] for t in app["cfg"]["tools"]}: return self._err(400, f"unknown tool {n}")
                    th = threading.Thread(target=one, args=(n,)); th.start(); ths.append(th)
                for th in ths: th.join(120)
                return self._send(200, res)
            return self._err(404, "no such endpoint")
        except Exception as e:
            return self._err(500, f"{type(e).__name__}: {e}")

    def _api_get(self, path, q):
        app = self.server.app; cfg = app["cfg"]; g = lambda k, d=None: (q.get(k) or [d])[0]
        try:
            if path == "/api/overview": return self._send(200, overview(cfg, app["pool"]))
            if path == "/api/tools":
                t = g("tool"); c = app["pool"].tools_cache.get(t) or app["pool"].tools(t)
                return self._send(200, dict(c, denied=next((x["denied"] for x in cfg["tools"] if x["name"] == t), [])))
            if path == "/api/calls": return self._send(200, {"calls": app["calls"].recent()})
            if path.startswith("/api/calls/"): return self._send(200, app["calls"].get(path.rsplit("/", 1)[1]))
            if path == "/api/jobs": return self._send(200, jobs_list(cfg))
            if path.startswith("/api/jobs/"): return self._send(200, job_get(cfg, path.rsplit("/", 1)[1]))
            if path == "/api/library": return self._send(200, library_index(cfg))
            if path.startswith("/api/library/"): return self._send(200, library_asset(cfg, path.rsplit("/", 1)[1], g("version")))
            if path == "/api/fs": return self._send(200, list_dir(cfg, g("path"), set((g("ext") or "").split(",")) - {""} or None))
            return self._err(404, "no such endpoint")
        except KeyError as e: return self._err(404, str(e).strip("'\""))
        except PermissionError as e: return self._err(403, str(e))
        except Exception as e: return self._err(500, f"{type(e).__name__}: {e}")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True


def serve(port, open_url_file=None):
    cfg = gitcraft_config()
    log_dir = cfg["log"]; os.makedirs(log_dir, exist_ok=True)
    pool = Pool(os.path.join(log_dir, "ui-tools.log"))
    httpd = Server(("127.0.0.1", port), Handler)
    token = secrets.token_urlsafe(24)
    httpd.app = {"cfg": cfg, "pool": pool, "calls": Calls(pool), "token": token, "cookie": secrets.token_urlsafe(24),
                 "access": open(os.path.join(log_dir, "ui-access.log"), "a")}
    url = f"http://127.0.0.1:{httpd.server_address[1]}/#token={token}"
    print(f"GITCRAFT control room: {url}", flush=True)
    print(f"  roots: {', '.join(cfg['roots'])}   library: {cfg['library']}   (Ctrl-C stops it)", flush=True)
    if open_url_file:
        with open(open_url_file, "w") as f: f.write(url)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: pool.close()


# ------------------------------------------------------------------ read-only snapshot (for previews)
def snapshot(dest, discover=True, max_assets=40):
    """Write the UI with real data as static files: data/*.json and files/<sha>.<ext>. Actions are disabled."""
    cfg = gitcraft_config(); pool = Pool(os.devnull)
    if os.path.isdir(dest): shutil.rmtree(dest)
    os.makedirs(os.path.join(dest, "data", "library"), exist_ok=True); os.makedirs(os.path.join(dest, "data", "jobs")); os.makedirs(os.path.join(dest, "files"))
    files = {}
    def keep(p):
        real = file_allowed(cfg, p)
        if not real: return None
        if real not in files:
            ext = os.path.splitext(real)[1].lower(); h = hashlib.sha256(real.encode()).hexdigest()[:16]
            shutil.copy2(real, os.path.join(dest, "files", h + ext)); files[real] = f"files/{h}{ext}"
        return files[real]
    w = lambda name, data: json.dump(data, open(os.path.join(dest, "data", name), "w"), default=str)
    tools = {}
    if discover:
        def one(n):
            try: tools[n] = {"ok": True, **pool.tools(n)}
            except Exception as e: tools[n] = {"ok": False, "error": str(e)}
        ths = [threading.Thread(target=one, args=(t["name"],)) for t in cfg["tools"]]
        for t in ths: t.start()
        for t in ths: t.join(120)
    for n, v in tools.items(): v["denied"] = next(x["denied"] for x in cfg["tools"] if x["name"] == n)
    ov = overview(cfg, pool); ov["clients"] = {}
    try: hw = pool.call("meshcraft", "hardware_probe", {})["result"]
    except Exception as e: hw = {"error": str(e)}
    routes = {}
    for req, n in (("a blocky voxel lifeboat", 0), ("treasure chest for the cove", 0), ("animated pirate captain walking", 0),
                   ("turn this concept art into a ship", 1), ("scan of the old dock", 24), ("a stone well", 0)):
        try: routes[f"{req}|{n}"] = pool.call("meshcraft", "route", {"request": req, "images": n})["result"]
        except Exception as e: routes[f"{req}|{n}"] = {"error": str(e)}
    pool.close()
    w("overview.json", ov); w("tools.json", tools); w("hardware.json", hw); w("routes.json", routes)
    lib = library_index(cfg); lib["assets"] = lib["assets"][:max_assets]
    for a in lib["assets"]:
        if a.get("thumbnail"): a["thumbnail_file"] = keep(os.path.join(cfg["library"], a["thumbnail"]))
        for v in a["versions"]:
            md = library_asset(cfg, a["id"], v)
            for f in md["files"]:     # preview images for the latest version only (older versions list their files without them)
                if v == a["latest"] and f["kind"] == "preview": f["file"] = keep(f["abs"])   # no GLBs: static hosts often refuse them
            w(f"library/{a['id']}.v{v}.json", md)
    w("library.json", lib)
    jl = jobs_list(cfg, 200); w("jobs.json", jl)
    for j in jl["jobs"]: w(f"jobs/{j['id']}.json", job_get(cfg, j["id"]))
    w("meta.json", {"snapshot": True, "created": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "files": len(files)})
    # one self-contained page (styles and script inline, as static hosts like Claude artifacts require)
    css = open(os.path.join(STATIC, "app.css"), encoding="utf-8").read(); js = open(os.path.join(STATIC, "app.js"), encoding="utf-8").read()
    page = ('<title>GITCRAFT Control Room</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
            f'<style>\n{css}\n</style>\n'
            '<div id="app"><aside class="rail" aria-label="Sections"><div class="brand"><span class="mark" aria-hidden="true"></span><span>GITCRAFT</span></div>'
            '<nav id="nav-rail"></nav><div class="rail-foot" id="rail-foot"></div></aside><main id="main" tabindex="-1"></main>'
            '<nav class="tabbar" id="nav-tabs" aria-label="Sections"></nav></div><div id="sheet-root"></div><div id="toasts" role="status" aria-live="polite"></div>\n'
            f'<script>window.GITCRAFT_SNAPSHOT = true;</script>\n<script>\n{js}\n</script>\n')
    open(os.path.join(dest, "index.html"), "w", encoding="utf-8").write(page)
    return {"dest": dest, "assets": len(lib["assets"]), "jobs": len(jl["jobs"]), "files": len(files)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("GITCRAFT_UI_PORT", 8765)))
    ap.add_argument("--url-file", help="also write the URL (with its token) to this file")
    ap.add_argument("--snapshot", metavar="DIR", help="write a read-only snapshot instead of serving")
    a = ap.parse_args()
    if a.snapshot: print(json.dumps(snapshot(a.snapshot)))
    else: serve(a.port, a.url_file)
