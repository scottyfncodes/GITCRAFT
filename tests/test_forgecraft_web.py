#!/usr/bin/env python3
"""Security regression test for ForgeCraft's web exposure (PR #9 audit findings).

The original audit found that `forgecraft/ui_server.py` (live mode) ran pipeline jobs in its own
process and accepted requests from any web page:
  V1 no authentication (no token: any local program or page could drive it)
  V2 cross-site requests accepted (no Origin check; text/plain "simple" POSTs parsed as JSON)
  V3 DNS rebinding (no Host check: a hostile domain resolving to 127.0.0.1 could read /api/state)
  V4 jobs ran outside the guard and the Landlock sandbox, with no audit log
  V5 request specs could name any file on disk (e.g. images=["~/.ssh/id_rsa"]) because nothing checked roots
  V6 unbounded request bodies (base64 uploads written into the library)

ForgeCraft does not need a web server: every live action is an MCP tool (generate, compose_scene,
job_retry, mixamo_prepare_upload). So the fix removes the live server, and the control room
(scripts/ui.sh) is the one web front end, already acting only through scripts/mcp.sh.

This test checks:
  A  the live server cannot be started any more (both documented entry points), and no ForgeCraft
     code opens a listening socket or posts to a live API;
  B  every former live action, through the supported path, is refused for each attack (V1-V3, V6),
     a request naming a file outside the roots is refused by the guard (V5), and a legitimate call
     works and is audited (V4);
  C  the static snapshot publisher (used for the Vercel preview) still works and serves no API.

    tests/test_forgecraft_web.py
"""
import json, os, re, socket, subprocess, sys, tempfile, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE); FC = os.path.join(REPO, "forgecraft")
ws = tempfile.mkdtemp(prefix="forgecraft-web-ws-")
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_3D_LIBRARY=os.path.join(ws, "3d-library"),
           GITCRAFT_LIGHTCRAFT_LIBRARY=os.path.join(ws, "lc-library"))   # scratch libraries: the real ones are untouched
results = []
def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:500]}]"), flush=True)

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def listening(port, wait):
    end = time.time() + wait
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close(); return True
        except OSError:
            time.sleep(0.2)
    return False

def raw(port, method, path, body=b"", headers=None):
    h = {"Host": f"127.0.0.1:{port}"}; h.update(headers or {})
    r = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body if method == "POST" else None, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=20) as f: return f.status, f.read()[:300]
    except urllib.error.HTTPError as e: return e.code, e.read()[:300]
    except OSError as e: return 0, str(e).encode()

# ---------------------------------------------------------------- A: no live server
for label, cmd in (("forgecraft/ui_server.py", [sys.executable, os.path.join(FC, "ui_server.py")]),
                   ("forgecraft/cli.py serve", [sys.executable, os.path.join(FC, "cli.py"), "serve"])):
    port = free_port()
    p = subprocess.Popen(cmd + ["--port", str(port)], env=env, cwd=ws, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    up = listening(port, 6)
    evidence = {}
    if up:   # the old live server: show what any web page could do to it (scratch library only)
        evil = {"Origin": "https://evil.example", "Content-Type": "text/plain"}
        evidence["V2 cross-site text/plain POST /api/retry"] = raw(port, "POST", "/api/retry", b'{"job": "job-x"}', evil)[0]
        evidence["V3 rebinding Host GET /api/state"] = raw(port, "GET", "/api/state", headers={"Host": f"evil.example:{port}"})[0]
        evidence["V1 no token GET /api/state"] = raw(port, "GET", "/api/state")[0]
    p.terminate()
    try: out = p.communicate(timeout=10)[0].decode(errors="replace")
    except subprocess.TimeoutExpired: p.kill(); out = ""
    check(f"A: `{label}` no longer starts a live web server", not up, evidence or out[-300:])
    if not up: check(f"A: `{label}` explains the supported routes instead", "scripts/ui.sh" in out and "MCP" in out, out[-300:])

listen_re = re.compile(r"HTTPServer|TCPServer|serve_forever|\.listen\(|socket\.bind|\.bind\(\(")
offenders = []
for root, _, files in os.walk(FC):
    if "node_modules" in root or "/vendor" in root: continue
    for f in files:
        if f.endswith((".py", ".mjs")):
            p = os.path.join(root, f)
            if listen_re.search(open(p, encoding="utf-8", errors="replace").read()): offenders.append(os.path.relpath(p, REPO))
check("A: no ForgeCraft module opens a listening socket", not offenders, offenders)
app = open(os.path.join(FC, "ui", "app.js"), encoding="utf-8").read()
check("A: the ForgeCraft page never calls a live /api endpoint", "/api/" not in app, re.findall(r".{40}/api/.{40}", app)[:3])

# ---------------------------------------------------------------- B: the supported path is protected
urlfile = os.path.join(ws, "ui-url.txt")
srv = subprocess.Popen([os.path.join(REPO, "scripts", "ui.sh"), "--port", "0", "--url-file", urlfile], env=env,
                       stdout=open(os.path.join(ws, "ui.log"), "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(100):
        if os.path.exists(urlfile) and open(urlfile).read().strip(): break
        time.sleep(0.1)
    URL = open(urlfile).read().strip(); PORT = int(URL.split("/#")[0].rsplit(":", 1)[1]); TOKEN = URL.split("token=")[1]
    ok_h = {"X-GITCRAFT-Token": TOKEN, "Content-Type": "application/json"}
    actions = {"generate (/api/generate)": {"brief": "a wooden crate", "kind": "prop"},
               "compose_scene (/api/compose)": {"name": "cove", "items": []},
               "job_retry (/api/retry)": {"job": "job-x"},
               "mixamo_prepare_upload (/api/mixamo_prepare)": {"asset": "x", "out": f"{ws}/x.fbx"}}
    for name, args in actions.items():
        tool = name.split(" ")[0]
        body = json.dumps({"tool": "forgecraft", "name": tool, "arguments": args}).encode()
        attacks = {
            "V1 no token": raw(PORT, "POST", "/api/call", body, {"Content-Type": "application/json"})[0] == 403,
            "V2 cross-site Origin": raw(PORT, "POST", "/api/call", body, dict(ok_h, Origin="https://evil.example"))[0] == 403,
            "V2 text/plain simple request": raw(PORT, "POST", "/api/call", body, {"X-GITCRAFT-Token": TOKEN, "Content-Type": "text/plain"})[0] == 415,
            "V3 rebinding Host": raw(PORT, "POST", "/api/call", body, dict(ok_h, Host=f"evil.example:{PORT}"))[0] == 421,
        }
        check(f"B: forgecraft {name} refused for every attack", all(attacks.values()), attacks)
    import http.client
    hc = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20)
    hc.putrequest("POST", "/api/call"); hc.putheader("X-GITCRAFT-Token", TOKEN); hc.putheader("Content-Type", "application/json")
    hc.putheader("Content-Length", str(64 << 20)); hc.endheaders(); hc.send(b"{")
    check("B: V6 oversized upload bodies refused before they are read", hc.getresponse().status == 413); hc.close()
    st, _ = raw(PORT, "GET", "/api/overview", headers={"Host": f"evil.example:{PORT}", "X-GITCRAFT-Token": TOKEN})
    check("B: V3 state is not readable through a rebinding Host", st == 421, st)

    def call(tool, name, args):
        code, c = raw(PORT, "POST", "/api/call", json.dumps({"tool": tool, "name": name, "arguments": args}).encode(), ok_h)
        if code != 202: return {"status": "error", "result": c}
        cid = json.loads(c)["id"]
        for _ in range(600):
            time.sleep(0.5)
            _, s = 0, None
            r = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/calls/{cid}", headers={"X-GITCRAFT-Token": TOKEN})
            with urllib.request.urlopen(r, timeout=20) as f: s = json.loads(f.read())
            if s["status"] != "running": return s
        return {"status": "timeout"}
    r = call("forgecraft", "generate", {"brief": "a wooden crate", "images": ["/etc/hostname"]})
    check("B: V5 a request naming a file outside the roots is refused by the guard", r["status"] == "error" and "GITCRAFT policy" in str(r.get("result")), r)
    r = call("forgecraft", "route", {"brief": "stylized low-poly boat"})
    check("B: a legitimate ForgeCraft call works through the supported path", r["status"] == "done" and isinstance(r.get("result"), dict), r)
    time.sleep(0.3)
    log = os.path.join(os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft")), "logs", "audit.jsonl")
    tail = open(log).read().splitlines()[-40:]
    check("B: V4 ForgeCraft calls run under the guard and are audited",
          any('"server": "forgecraft"' in l and '"tool": "route"' in l for l in tail) and any('"server": "forgecraft"' in l and "/etc/hostname" in l and '"refused": true' in l for l in tail))
finally:
    srv.terminate()
    try: srv.wait(10)
    except Exception: srv.kill()

# ---------------------------------------------------------------- C: static snapshot still publishes
lib = os.path.join(ws, "snap-lib"); os.makedirs(os.path.join(lib, "assets"), exist_ok=True)
json.dump({"assets": []}, open(os.path.join(lib, "index.json"), "w"))
dist = os.path.join(ws, "dist")
pr = subprocess.run([sys.executable, os.path.join(FC, "ui_server.py"), "--publish", lib, dist, "--source", "test"], env=env, capture_output=True, text=True, timeout=120)
st = json.load(open(os.path.join(dist, "data", "state.json"))) if os.path.exists(os.path.join(dist, "data", "state.json")) else {}
check("C: the static snapshot publisher still works (Vercel preview)", pr.returncode == 0 and os.path.exists(os.path.join(dist, "index.html")) and st.get("mode") == "snapshot",
      pr.stdout[-200:] + pr.stderr[-300:])

print(f"\n{sum(results)}/{len(results)} checks passed   (workspace: {ws})")
sys.exit(0 if all(results) else 1)
