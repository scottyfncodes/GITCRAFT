#!/usr/bin/env python3
"""End-to-end test of the GITCRAFT control room (ui/server.py, started by scripts/ui.sh).

  * security: token, Origin, Host, JSON-only posts, body size, file previews confined to the
    roots and the library with a sandboxing CSP, unknown tools refused;
  * every action goes through scripts/mcp.sh: the guard still refuses paths outside the roots
    and policy-blocked commands, and its audit log records the UI's calls;
  * discovery of all 8 tool servers; MeshCraft pipeline, job (done / fallback / failed),
    library versions and same_as, verified export, routing advice;
  * the iPhone / dark / desktop browser flow (tests/ui_browser.js, Playwright);
  * the read-only snapshot.

    tests/test_ui.py [--keep]       screenshots: <workspace>/ui-shots
"""
import json, os, re, shutil, subprocess, sys, tempfile, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
ws = os.environ.get("GITCRAFT_UI_TEST_WS") or tempfile.mkdtemp(prefix="gitcraft-ui-ws-")
os.makedirs(ws, exist_ok=True)
pal = os.path.join(ws, "palette.json")
json.dump({"Honey Timber": "#D9954F", "Timber": "#9A5A2E", "Deep Tide": "#0E3B66", "Midnight Swell": "#0A2142", "Doubloon Gold": "#F4C542",
           "Gold Deep": "#C98A12", "Sunlit Amber": "#FF9F2E", "Sailcloth Cream": "#F6EAD0"}, open(pal, "w"))
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_MESHCRAFT_LIBRARY=os.path.join(ws, "library"),
           GITCRAFT_LIGHTCRAFT_LIBRARY=os.path.join(ws, "lightcraft-library"))
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:400]}]"), flush=True)

urlfile = os.path.join(ws, "ui-url.txt")
srv = subprocess.Popen([os.path.join(REPO, "scripts", "ui.sh"), "--port", "0", "--url-file", urlfile], env=env,
                       stdout=open(os.path.join(ws, "ui-server.log"), "w"), stderr=subprocess.STDOUT)
for _ in range(100):
    if os.path.exists(urlfile) and open(urlfile).read().strip(): break
    time.sleep(0.1)
URL = open(urlfile).read().strip(); BASE = URL.split("/#")[0]; TOKEN = URL.split("token=")[1]; PORT = BASE.rsplit(":", 1)[1]

def req(path, method="GET", body=None, headers=None, token=True, raw=False):
    hd = {"X-GITCRAFT-Token": TOKEN} if token else {}
    if body is not None: hd["Content-Type"] = "application/json"
    hd.update(headers or {})
    data = body if isinstance(body, bytes) else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=hd)
    try:
        with urllib.request.urlopen(r, timeout=600) as f:
            b = f.read(); return f.status, (b if raw else json.loads(b)), dict(f.headers)
    except urllib.error.HTTPError as e:
        b = e.read()
        try: return e.code, json.loads(b), dict(e.headers)
        except ValueError: return e.code, b, dict(e.headers)

def call(tool, name, args=None):
    code, c, _ = req("/api/call", "POST", {"tool": tool, "name": name, "arguments": args or {}})
    if code != 202: return {"status": "error", "result": c}
    while True:
        time.sleep(0.5)
        _, s, _ = req(f"/api/calls/{c['id']}")
        if s["status"] != "running": return s

try:
    # ---------------- security gates
    check("serves on 127.0.0.1 only", BASE.startswith("http://127.0.0.1:"), BASE)
    code, _, h = req("/", token=False, raw=True)
    check("page has a strict CSP (scripts from self only) and refuses framing", code == 200 and "script-src 'self'" in h.get("Content-Security-Policy", "")
          and "frame-ancestors 'none'" in h.get("Content-Security-Policy", ""), h)
    check("API refuses requests without the token", req("/api/overview", token=False)[0] == 403)
    check("API refuses a wrong token", req("/api/overview", token=False, headers={"X-GITCRAFT-Token": "x" * 32})[0] == 403)
    check("API refuses other web pages (Origin check)", req("/api/call", "POST", {"tool": "meshcraft", "name": "route"}, headers={"Origin": "https://evil.example"})[0] == 403)
    check("API refuses DNS-rebinding Host names", req("/api/overview", headers={"Host": f"evil.example:{PORT}"})[0] == 421)
    check("API refuses form-encoded / text posts (no simple-request CSRF)",
          req("/api/call", "POST", b'{"tool":"meshcraft"}', headers={"Content-Type": "text/plain"})[0] == 415)
    import http.client
    hc = http.client.HTTPConnection("127.0.0.1", int(PORT), timeout=30)
    hc.putrequest("POST", "/api/call"); hc.putheader("X-GITCRAFT-Token", TOKEN); hc.putheader("Content-Type", "application/json")
    hc.putheader("Content-Length", str(8 << 20)); hc.endheaders(); hc.send(b"{")
    check("API refuses oversized bodies before reading them", hc.getresponse().status == 413); hc.close()
    check("API refuses unknown tools", req("/api/call", "POST", {"tool": "bash", "name": "x"})[0] == 400)
    check("file previews need the session cookie", req(f"/files?path={pal}", token=False, raw=True)[0] == 403)
    code, _, h = req("/api/session", "POST", {})
    cookie = (h.get("Set-Cookie") or "").split(";")[0]
    check("session cookie is HttpOnly + SameSite=Strict + scoped to /files", code == 200 and "HttpOnly" in h.get("Set-Cookie", "")
          and "SameSite=Strict" in h.get("Set-Cookie", "") and "Path=/files" in h.get("Set-Cookie", ""), h.get("Set-Cookie"))
    ck = {"Cookie": cookie}
    open(os.path.join(ws, "evil.svg"), "w").write('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
    code, _, h = req(f"/files?path={ws}/evil.svg", token=False, headers=ck, raw=True)
    check("previews are served with a sandboxing CSP (a hostile SVG cannot run)", code == 200 and "sandbox" in h.get("Content-Security-Policy", ""), h)
    check("previews outside the roots and library are refused", req("/files?path=/etc/hostname", token=False, headers=ck, raw=True)[0] == 404)
    check("path traversal is refused", req(f"/files?path={ws}/../../etc/passwd", token=False, headers=ck, raw=True)[0] == 404)
    os.symlink("/etc/hostname", os.path.join(ws, "link.txt"))
    check("symlinks out of the roots are refused", req(f"/files?path={ws}/link.txt", token=False, headers=ck, raw=True)[0] == 404)
    open(os.path.join(ws, "page.html"), "w").write("<script>alert(1)</script>")
    check("HTML is never served from the workspace", req(f"/files?path={ws}/page.html", token=False, headers=ck, raw=True)[0] == 404)
    check("folder browsing is limited to the roots", req("/api/fs?path=/etc")[0] == 403)

    # ---------------- discovery
    code, ov, _ = req("/api/overview")
    check("overview lists the 8 tools, installed and registered", code == 200 and len(ov["tools"]) == 8 and all(t["installed"] for t in ov["tools"]), ov)
    check("overview reports the kernel sandbox and the closed network", ov["sandbox"]["landlock_abi"] and ov["network"] == "denied", ov.get("sandbox"))
    code, d, _ = req("/api/discover", "POST", {})
    counts = {k: len(v.get("tools", [])) for k, v in d.items()}
    check("discovers every server's tools over MCP through scripts/mcp.sh", code == 200 and len(d) == 8 and all(v["ok"] and v["tools"] for v in d.values()), d if code != 200 else counts)
    check("policy-blocked commands are reported", req("/api/tools?tool=effectcraft")[1].get("denied") == ["run_script"])

    # ---------------- guard and sandbox still apply to UI calls
    r = call("meshcraft", "inspect_palette", {"path": "/etc/passwd"})
    check("guard refuses paths outside the roots for UI calls", r["status"] == "error" and "GITCRAFT policy" in str(r["result"]), r)
    r = call("effectcraft", "run_script", {"code": "1"})
    check("guard refuses policy-blocked commands for UI calls", r["status"] == "error" and "disabled" in str(r["result"]), r)
    time.sleep(0.3)
    log = os.path.join(os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft")), "logs", "audit.jsonl")
    tail = open(log).read().splitlines()[-50:]
    check("UI calls are recorded in the audit log", any("inspect_palette" in l and "/etc/passwd" in l and '"refused": true' in l for l in tail))

    # ---------------- MeshCraft through the UI: pipeline, jobs, library
    brief = {"asset_id": "ui_lantern", "template": "lantern", "palette": pal, "out_dir": os.path.join(ws, "ui_lantern"), "profiles": ["three-web-toon"],
             "preview": {"size": 256, "views": ["three_quarter", "front"]}}
    r1 = call("meshcraft", "run_pipeline", {"brief": brief}); r2 = call("meshcraft", "run_pipeline", {"brief": brief})
    ok = r1["status"] == "done" and r2["status"] == "done"
    check("run_pipeline through the UI: job done, library v1 then v2 same_as v1", ok and r1["result"]["library"]["version"] == 1 and r2["result"]["library"].get("same_as") == 1,
          (r1, r2) if not ok else (r1["result"]["library"], r2["result"]["library"]))
    fb = dict(brief, asset_id="ui_bake", out_dir=os.path.join(ws, "ui_bake"), profiles=["web-pbr"], bake={"resolution": 100000, "fallbacks": []})
    r3 = call("meshcraft", "run_pipeline", {"brief": fb})
    check("a failing bake shows as done_with_fallback", r3["status"] == "done" and r3["result"]["job"]["status"] == "done_with_fallback", r3)
    r4 = call("meshcraft", "run_pipeline", {"brief": dict(brief, asset_id="ui_bad", template="no_such_template")})
    check("a bad request shows as failed with the reason", r4["status"] == "error" and "unknown template" in str(r4["result"]), r4)
    code, jl, _ = req("/api/jobs")
    st = {j["asset_id"]: j["status"] for j in jl["jobs"]}
    check("jobs view: done, done_with_fallback and failed jobs", st.get("ui_lantern") == "done" and st.get("ui_bake") == "done_with_fallback" and st.get("ui_bad") == "failed", st)
    jid = next(j["id"] for j in jl["jobs"] if j["asset_id"] == "ui_bake")
    code, j, _ = req(f"/api/jobs/{jid}")
    check("job view: every attempt with what changed", code == 200 and len(j["attempts"]) == 2 and "512" in (j["attempts"][1].get("change") or ""), j)
    check("job view refuses odd ids", req("/api/jobs/..%2F..%2Fetc%2Fpasswd")[0] == 404)
    code, lib, _ = req("/api/library")
    check("library view lists assets", code == 200 and {"ui_lantern", "ui_bake"} <= {a["id"] for a in lib["assets"]}, lib)
    code, a, _ = req("/api/library/ui_lantern")
    check("asset view: version 2, same_as, files with SHA-256, inputs, checks", code == 200 and a["version"] == 2 and a["same_as"] == 1
          and all(len(f["sha256"]) == 64 for f in a["files"]) and a["inputs"] and a["checks"], {k: a.get(k) for k in ("version", "same_as")})
    prev = next(f for f in a["files"] if f["kind"] == "preview")
    code, b, h = req(f"/files?path={prev['abs']}", token=False, headers=ck, raw=True)
    check("library previews are viewable", code == 200 and b[:8] == b"\x89PNG\r\n\x1a\n" and h.get("Content-Type") == "image/png")
    code, b, h = req("/vendor/three/examples/jsm/loaders/GLTFLoader.js", token=False, raw=True)
    check("3D viewer uses MeshCraft's local three.js (no download)", code == 200 and b"/vendor/three/build/three.module.js" in b and b"from 'three'" not in b)
    r = call("meshcraft", "library_export", {"asset": "ui_lantern", "version": 1, "dest": os.path.join(ws, "handoff")})
    check("export into a workspace root is verified", r["status"] == "done" and r["result"]["verified"] and r["result"]["files"], r)
    r = call("meshcraft", "library_export", {"asset": "ui_lantern", "dest": "/tmp/gitcraft-ui-escape"})
    check("export outside the roots is refused by the guard", r["status"] == "error" and "GITCRAFT policy" in str(r["result"]) and not os.path.exists("/tmp/gitcraft-ui-escape"), r)
    r = call("meshcraft", "route", {"request": "turn this concept art into a ship", "images": 1})
    check("routing advice: unavailable capability and labelled alternative", r["status"] == "done" and r["result"]["available"] is False
          and "NOT derived" in r["result"]["alternatives"][0]["note"], r)

    # ---------------- browser (iPhone first)
    shots = os.path.join(ws, "ui-shots"); os.makedirs(shots, exist_ok=True)
    pr = subprocess.run(["node", os.path.join(HERE, "ui_browser.js"), URL, shots, pal], capture_output=True, text=True, timeout=1200)
    lines = [json.loads(l) for l in pr.stdout.splitlines() if l.startswith("{")]
    if not lines: check("browser run", False, pr.stdout[-500:] + pr.stderr[-500:])
    for l in lines: check("browser: " + l["name"], l["ok"], l["detail"])

    # ---------------- read-only snapshot
    snap = os.path.join(ws, "snapshot")
    sp = subprocess.run([os.path.join(REPO, "scripts", "ui.sh"), "--snapshot", snap], env=env, capture_output=True, text=True, timeout=600)
    info = json.loads(sp.stdout.strip().splitlines()[-1]) if sp.returncode == 0 else {}
    check("snapshot: real data, previews and job records written", info.get("assets", 0) >= 3 and info.get("jobs", 0) >= 4 and info.get("files", 0) > 0
          and os.path.exists(os.path.join(snap, "data", "tools.json")), sp.stdout[-300:] + sp.stderr[-300:])
finally:
    srv.terminate()
    try: srv.wait(10)
    except Exception: srv.kill()
    if "--keep" not in sys.argv and not os.environ.get("GITCRAFT_UI_TEST_WS"): pass   # keep the workspace for the screenshots

print(f"\n{sum(results)}/{len(results)} checks passed   (workspace: {ws})")
sys.exit(0 if all(results) else 1)
