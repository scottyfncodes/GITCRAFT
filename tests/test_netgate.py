#!/usr/bin/env python3
"""Per-host network allowances (scripts/netgate.py + the sandbox's --allow-connect rule).

1. A process in the Landlock sandbox with --no-net --allow-connect <netgate port>, HTTPS_PROXY at netgate:
   - an allowed host works; a host not on the list is refused by netgate (403, logged);
   - connecting anywhere directly (an outside address, the environment's own proxy) is refused by the kernel.
2. Through scripts/mcp.sh: GITCRAFT_ALLOW_HOSTS_STUDIOCRAFT starts netgate for that tool only, studiocraft
   reports the allowance, and without the variable it has no network.
3. An allowed host that the environment itself blocks fails cleanly (502) and is logged with the reason.

    tests/test_netgate.py            (needs outbound HTTPS to pypi.org; uses the environment's HTTPS_PROXY if set)"""
import json, os, socket, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE); sys.path.insert(0, HERE)
from mcp_client import Client
ws = tempfile.mkdtemp(prefix="gitcraft-netgate-"); home = os.path.join(ws, "gchome"); os.makedirs(os.path.join(home, "logs"))
NETLOG = os.path.join(home, "logs", "net.jsonl")
results = []
def check(label, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not cond else ""), flush=True)

upstream = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
pf = os.path.join(ws, "port")
gate = subprocess.Popen([sys.executable, os.path.join(REPO, "scripts", "netgate.py"), "--allow", "pypi.org,*.pythonhosted.org,huggingface.co",
                         "--tool", "test", "--parent", str(os.getpid()), "--port-file", pf, "--log", NETLOG],
                        env=dict(os.environ, NETGATE_UPSTREAM=upstream))
for _ in range(50):
    if os.path.exists(pf) and open(pf).read(): break
    time.sleep(0.1)
port = int(open(pf).read())
probe = r'''
import json, os, socket, ssl, sys, urllib.request, urllib.error
out = {}
def get(url):
    try: return urllib.request.urlopen(url, timeout=30).status
    except urllib.error.HTTPError as e: return e.code
    except Exception as e: return f"{type(e).__name__}: {e}"
out["allowed"] = get("https://pypi.org/simple/numpy/")
out["not_listed"] = get("https://example.com/")
out["hf"] = get("https://huggingface.co/api/models/hexgrad/Kokoro-82M")
def direct(host, port):
    try: socket.create_connection((host, port), timeout=10).close(); return "connected"
    except Exception as e: return f"{type(e).__name__}: {e}"
out["direct_outside"] = direct("1.1.1.1", 443)
up = os.environ.get("UPSTREAM_PORT")
out["direct_env_proxy"] = direct("127.0.0.1", int(up)) if up else "n/a"
print(json.dumps(out))
'''
up_port = upstream.rsplit(":", 1)[-1].strip("/") if upstream else ""
env = dict(os.environ, HTTPS_PROXY=f"http://127.0.0.1:{port}", https_proxy=f"http://127.0.0.1:{port}", NO_PROXY="", no_proxy="", UPSTREAM_PORT=up_port)
r = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "sandbox.py"), "--rx", "/usr", "--rx", "/lib", "--rx", "/lib64", "--rx", "/bin", "--ro", "/etc",
                    "--rx", sys.prefix, "--ro", "/proc", "--rw", "/dev", "--rw", ws, "--no-net", "--allow-connect", str(port), "--", sys.executable, "-c", probe],
                   capture_output=True, text=True, env=env, timeout=180)
try: out = json.loads(r.stdout.strip().splitlines()[-1])
except Exception: out = {"error": r.stderr[-500:]}
check("sandboxed process reaches an allowed host through netgate (pypi.org)", out.get("allowed") == 200, out)
check("a host not on the list is refused by netgate", "403" in str(out.get("not_listed")), out.get("not_listed"))
check("a direct connection to an outside address is refused by the kernel", "Permission" in str(out.get("direct_outside")) or "Errno 13" in str(out.get("direct_outside")), out.get("direct_outside"))
if up_port: check("a direct connection to the environment's own proxy is refused (no way around netgate)", "Permission" in str(out.get("direct_env_proxy")) or "Errno 13" in str(out.get("direct_env_proxy")), out.get("direct_env_proxy"))
log = [json.loads(l) for l in open(NETLOG)] if os.path.exists(NETLOG) else []
check("netgate logs allowed and refused connections", any(e.get("decision") == "allowed" and e.get("host") == "pypi.org" for e in log)
      and any(e.get("decision") == "refused" and e.get("host") == "example.com" for e in log), log[-4:])
hf = [e for e in log if e.get("host") == "huggingface.co"]
if hf and hf[-1]["decision"] == "allowed":
    check("huggingface.co allowed and reachable", out.get("hf") == 200, out.get("hf"))
else:
    check("an allowed host the environment blocks fails cleanly and is logged with the reason (huggingface.co)",
          bool(hf) and hf[-1]["decision"] == "allowed-failed" and out.get("hf") != 200, hf[-1:] or out.get("hf"))
gate.terminate()

# through the launcher
lenv = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ALLOW_HOSTS_STUDIOCRAFT="pypi.org")
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=lenv)
ok, st = c.call("studio_status"); c.close()
check("mcp.sh: GITCRAFT_ALLOW_HOSTS_STUDIOCRAFT gives studiocraft netgate (sandbox +netgate, allowance reported)",
      ok and (st.get("network") or {}).get("allowed_hosts") == ["pypi.org"] and "+netgate" in (st.get("sandbox") or ""), {k: st.get(k) for k in ("sandbox", "network")})
lenv["GITCRAFT_ALLOW_HOSTS_STUDIOCRAFT"] = "none"   # a standard install allows the CC0 hosts in ~/.gitcraft/allow-hosts; `none` is the explicit no-network run
c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "studiocraft"], env=lenv)
ok, st = c.call("studio_status"); c.close()
check("mcp.sh: with GITCRAFT_ALLOW_HOSTS_STUDIOCRAFT=none studiocraft has no network (the allow-hosts file is not read)", ok and not (st.get("network") or {}).get("allowed_hosts") and "+nonet" in (st.get("sandbox") or "") and "+netgate" not in st.get("sandbox", ""),
      {k: st.get(k) for k in ("sandbox", "network")})
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
