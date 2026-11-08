#!/usr/bin/env python3
"""Regression tests for the technical-debt audit fixes (docs/tech-debt.md).

    python3 tests/test_hardening.py      (~10 s; no Blender, no Studio runtime needed)

  F1  the control room's /vendor/three/ route serves only files inside the three.js package (an absolute path
      after the prefix used to read any .js file on disk)
  F2  a malformed tools/call (non-object arguments, an object as id, a non-string command id) is refused with an
      answer; the guard, and the tool server behind it, keep serving the next request
  F3  a negative or non-numeric Content-Length is a 400, not a hung or dropped connection
  F4  /files never serves a dotfile or anything inside a dot-folder (credentials, config) even under the roots
  F13 an atomic JSON write that fails leaves no temp file behind"""
import http.client, json, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-hardening-"))
results = []


def check(label, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + label + ("" if ok else f"  [{str(detail)[:400]}]"), flush=True)


# ---------------------------------------------------------------- F2: the guard survives malformed requests
echo = os.path.join(ws, "echo_server.py")
open(echo, "w").write("import sys, json\nfor l in sys.stdin:\n    m = json.loads(l)\n    if 'id' in m: print(json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': {'echo': m.get('method')}}), flush=True)\n")
g = subprocess.Popen([sys.executable, os.path.join(REPO, "scripts", "guard.py"), "--tool", "probe", "--root", ws, "--", sys.executable, echo],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=dict(os.environ, GITCRAFT_HOME=os.path.join(ws, "home")))
def send(m): g.stdin.write(json.dumps(m) + "\n"); g.stdin.flush()
def recv(): return json.loads(g.stdout.readline())
send({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "x", "arguments": ["a"]}})
r1 = recv()
check("F2 non-object arguments: refused with an answer", r1.get("id") == 1 and r1["result"].get("isError") and "malformed" in r1["result"]["content"][0]["text"], r1)
send({"jsonrpc": "2.0", "id": {"x": 1}, "method": "tools/call", "params": {"name": "command_run", "arguments": {"id": {"x": 1}}}})
r2 = recv()
check("F2 an object as id: refused (id null), not a crash", r2.get("id") is None and r2["result"].get("isError"), r2)
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "command_run", "arguments": {"id": {"x": 1}}}})
r3 = recv()
check("F2 a non-string command id: refused", r3.get("id") == 3 and r3["result"].get("isError"), r3)
send({"jsonrpc": "2.0", "id": 4, "method": "ping"})
r4 = recv()
check("F2 the guard and its server still answer the next request", r4 == {"jsonrpc": "2.0", "id": 4, "result": {"echo": "ping"}}, r4)
send({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "read", "arguments": {"path": "/etc/passwd"}}})
r5 = recv()
check("F2 the path policy still applies", r5.get("id") == 5 and "may only read and write inside" in r5["result"]["content"][0]["text"], r5)
g.stdin.close(); g.wait(timeout=10)

# ---------------------------------------------------------------- F1, F3, F4: the control room
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_3D_LIBRARY=os.path.join(ws, "library"), GITCRAFT_MESHCRAFT_LIBRARY=os.path.join(ws, "library"))
urlfile = os.path.join(ws, "ui-url.txt")
srv = subprocess.Popen([sys.executable, os.path.join(REPO, "ui", "server.py"), "--port", "0", "--url-file", urlfile], env=env,
                       stdout=open(os.path.join(ws, "ui.log"), "w"), stderr=subprocess.STDOUT)
try:
    for _ in range(150):
        if os.path.exists(urlfile) and open(urlfile).read().strip(): break
        time.sleep(0.1)
    url = open(urlfile).read().strip(); base = url.split("/#")[0]; token = url.split("token=")[1]; port = int(base.rsplit(":", 1)[1])

    def get(path, headers=None, method="GET", body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request(method, path, body=body, headers=dict({"Host": f"127.0.0.1:{port}"}, **(headers or {})))
        r = c.getresponse(); data = r.read(); c.close(); return r.status, data, r

    secret = os.path.join(ws, "secret.js"); open(secret, "w").write("const leaked = 'not for the browser';")
    st, data, _ = get("/vendor/three/" + secret)
    check("F1 /vendor/three/<absolute path> does not read files outside three.js", st == 404 and b"leaked" not in data, (st, data[:80]))
    st, data, _ = get("/vendor/three/..%2F..%2F..%2F..%2F" + secret.lstrip("/").replace("/", "%2F"))
    check("F1 encoded ../ does not escape either", st == 404 and b"leaked" not in data, st)
    three = os.path.join(REPO, "meshcraft", "engine_check", "node_modules", "three", "build", "three.module.js")
    if os.path.isfile(three):
        st, _, _ = get("/vendor/three/build/three.module.js"); check("F1 the real three.js module is still served", st == 200, st)
    hdr = {"X-GITCRAFT-Token": token, "Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}"}
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest("POST", "/api/session", skip_host=True); c.putheader("Host", f"127.0.0.1:{port}")
    for k, v in hdr.items(): c.putheader(k, v)
    c.putheader("Content-Length", "-1"); c.endheaders()
    t0 = time.time()
    try: st = c.getresponse().status
    except Exception as e: st = repr(e)
    check("F3 a negative Content-Length is refused at once (400), not a hung connection", st == 400 and time.time() - t0 < 4, st)
    c.close()
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.putrequest("POST", "/api/session", skip_host=True); c.putheader("Host", f"127.0.0.1:{port}")
    for k, v in hdr.items(): c.putheader(k, v)
    c.putheader("Content-Length", "abc"); c.endheaders()
    try: st = c.getresponse().status
    except Exception as e: st = repr(e)
    check("F3 a non-numeric Content-Length is a 400", st == 400, st); c.close()
    st, _, r = get("/api/session", hdr, "POST", b"{}")
    cookie = (r.getheader("Set-Cookie") or "").split(";")[0]
    os.makedirs(os.path.join(ws, ".private")); open(os.path.join(ws, ".private", "creds.json"), "w").write('{"token": "x"}')
    open(os.path.join(ws, ".hidden.json"), "w").write('{"k": 1}'); open(os.path.join(ws, "visible.json"), "w").write('{"k": 1}')
    st1, _, _ = get("/files?path=" + os.path.join(ws, ".private", "creds.json"), {"Cookie": cookie})
    st2, _, _ = get("/files?path=" + os.path.join(ws, ".hidden.json"), {"Cookie": cookie})
    st3, _, _ = get("/files?path=" + os.path.join(ws, "visible.json"), {"Cookie": cookie})
    check("F4 /files refuses dotfiles and dot-folders under the roots, still serves ordinary files", st1 == 404 and st2 == 404 and st3 == 200, (st1, st2, st3))
finally:
    srv.kill()

# ---------------------------------------------------------------- F13: no temp files left by a failed atomic write
from production import store
d = os.path.join(ws, "atomic"); os.makedirs(d)
try: store.write_json(os.path.join(d, "x.json"), {"bad": object()} if False else {"bad": {1, 2}.__iter__()})
except Exception: pass
store.write_json(os.path.join(d, "y.json"), {"ok": True})
check("F13 a failed atomic write leaves no .tmp- file", not [f for f in os.listdir(d) if f.startswith(".tmp-")], os.listdir(d))

bad = len([r for r in results if not r])
print(f"\n{len(results) - bad}/{len(results)} passed")
shutil.rmtree(ws, ignore_errors=True)
sys.exit(1 if bad else 0)
