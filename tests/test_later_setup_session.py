"""End-to-end test of GITCRAFT_MESHCRAFT=later, the way a cloud environment's setup script uses it.

  python3 tests/test_later_setup_session.py [--work DIR]     (commit first: setup clones the committed branch)

1. Fresh HOME (empty ~/.gitcraft, ~/.claude, pip/uv caches), then scripts/setup-env.sh with GITCRAFT_MESHCRAFT=later,
   cloning this checkout's committed branch, exactly as `curl ... setup-env.sh | GITCRAFT_MESHCRAFT=later bash` does.
2. A real Claude Code session (`claude -p`, stream-json) in a separate project, not GITCRAFT:
   - MeshCraft and ForgeCraft are registered and connected at session start, each with its status tool;
   - the user-level SessionStart hook starts the Blender build in the background (the repo's own hook can't: GITCRAFT
     isn't the project);
   - the build's duration is measured (cold download);
   - when it lands, the SAME session uses MeshCraft's and ForgeCraft's full tools (tools/list_changed, no /mcp).
--mode mcp (the default when `claude` isn't installed or there's no API key, as in CI): the same checks without
Claude Code. MCP clients connect to the registered MeshCraft and ForgeCraft servers before Blender exists, the global
hook runs the way Claude Code runs it, and the same server processes must list and run their full tools afterwards.
Exit 1 on any failure. Downloads the prebuilt tools (~400 MB) and Blender (~400 MB).
"""
import argparse, json, os, queue, shutil, subprocess, sys, tempfile, threading, time

ap = argparse.ArgumentParser()
ap.add_argument("--work", default=None)
ap.add_argument("--build-timeout", type=int, default=1800)
ap.add_argument("--mode", choices=["auto", "session", "mcp"], default="auto")
a = ap.parse_args()
if a.mode == "auto":
    a.mode = "session" if shutil.which("claude") and (os.environ.get("ANTHROPIC_API_KEY") or os.path.exists(os.path.expanduser("~/.claude/.credentials.json"))
                                                       or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("CLAUDECODE")) else "mcp"
print(f"mode: {a.mode}", flush=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
branch = subprocess.check_output(["git", "-C", repo, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
fails, report = [], {}


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""), flush=True)
    if not ok: fails.append(name)


work = a.work or tempfile.mkdtemp(prefix="gitcraft-later-")
home, proj = os.path.join(work, "home"), os.path.join(work, "project")
shutil.rmtree(work, ignore_errors=True)
for d in (home, proj, os.path.join(home, ".claude")): os.makedirs(d)
# cloud containers point SSL_CERT_FILE etc. at $HOME/.ccr (the agent proxy's CA); keep it reachable from the fresh HOME
if os.path.isdir(os.path.expanduser("~/.ccr")): os.symlink(os.path.expanduser("~/.ccr"), os.path.join(home, ".ccr"))
env = dict(os.environ, HOME=home, PIP_CACHE_DIR=os.path.join(work, "pip-cache"), UV_CACHE_DIR=os.path.join(work, "uv-cache"),
           PATH=f"{os.path.dirname(shutil.which('uv') or '/usr/bin/uv')}:{os.environ['PATH']}")
for k in ("GITCRAFT_HOME", "GITCRAFT_ROOT", "GITCRAFT_ROOTS", "GITCRAFT_3D_LIBRARY", "GITCRAFT_MESHCRAFT", "CLAUDE_CONFIG_DIR",
          "CLAUDE_PROJECT_DIR", "FORGECRAFT_HOME", "FORGECRAFT_BLENDER_PY"):
    env.pop(k, None)
gc = os.path.join(home, ".gitcraft")

# 1) the setup script, as the environment runs it
t0 = time.time()
setup = subprocess.run(["bash", os.path.join(repo, "scripts", "setup-env.sh")], cwd=home, capture_output=True, text=True,
                       env=dict(env, GITCRAFT_MESHCRAFT="later", GITCRAFT_REPO_URL=repo, GITCRAFT_REF=branch), timeout=3600)
report["setup_seconds"] = round(time.time() - t0, 1)
st = json.load(open(os.path.join(gc, "status.json")))["tools"] if os.path.exists(os.path.join(gc, "status.json")) else {}
reg = json.load(open(os.path.join(home, ".claude.json"))).get("mcpServers", {}) if os.path.exists(os.path.join(home, ".claude.json")) else {}
hooks = json.load(open(os.path.join(home, ".claude", "settings.json"))).get("hooks", {}).get("SessionStart", []) \
    if os.path.exists(os.path.join(home, ".claude", "settings.json")) else []
check(f"setup (GITCRAFT_MESHCRAFT=later) finishes without Blender ({report['setup_seconds']} s)",
      setup.returncode == 0 and st.get("meshcraft", {}).get("state") == "later" and not os.path.exists(os.path.join(gc, "meshcraft", "venv")),
      setup.stdout[-800:] + setup.stderr[-800:] if setup.returncode else {k: v.get("state") for k, v in st.items()})
check("setup registers all nine servers, MeshCraft and ForgeCraft included", {"meshcraft", "forgecraft", "photocraft"} <= set(reg) and len(reg) >= 9, sorted(reg))
check("setup installs the user-level SessionStart hook", any("session-start.sh" in h.get("command", "") and "--global" in h.get("command", "")
                                                              for g in hooks for h in g.get("hooks", [])), hooks)


class Session:
    def __init__(self):
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--allowedTools", "mcp__meshcraft", "mcp__forgecraft", "mcp__studiocraft", "--max-turns", "8"]
        self.p = subprocess.Popen(cmd, cwd=proj, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.q = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            try: self.q.put(json.loads(line))
            except ValueError: pass
        self.q.put(None)

    def ask(self, text, timeout=900):
        self.p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"); self.p.stdin.flush()
        got, end = [], time.time() + timeout
        while time.time() < end:
            try: ev = self.q.get(timeout=5)
            except queue.Empty: continue
            if ev is None: break
            got.append(ev)
            if ev.get("type") == "result": break
        return got

    def close(self):
        try: self.p.stdin.close(); self.p.wait(timeout=60)
        except Exception: self.p.kill()


def calls(evs):
    uses, out = {}, []
    for ev in evs:
        msg = ev.get("message")
        for c in (msg.get("content") or [] if isinstance(msg, dict) else []):
            if not isinstance(c, dict): continue
            if c.get("type") == "tool_use": uses[c["id"]] = c["name"]
            if c.get("type") == "tool_result":
                t = c.get("content"); t = "".join(x.get("text", "") for x in t) if isinstance(t, list) else str(t)
                out.append((uses.get(c.get("tool_use_id"), "?"), t, bool(c.get("is_error"))))
    return out


if a.mode == "session":
    # 2) a session in another project, started before Blender exists
    s = Session()
    ev1 = s.ask("Call mcp__meshcraft__meshcraft_status and quote its state field.")
    init = next((e for e in ev1 if e.get("type") == "system" and e.get("subtype") == "init"), {})
    servers = {m["name"]: m.get("status") for m in init.get("mcp_servers", [])}
    tools = init.get("tools", [])
    check("session start: MeshCraft and ForgeCraft connected (project is not GITCRAFT)",
          servers.get("meshcraft") == "connected" and servers.get("forgecraft") == "connected", servers)
    check("session start: each lists only its status tool while Blender is missing",
          [t for t in tools if t.startswith("mcp__meshcraft__")] == ["mcp__meshcraft__meshcraft_status"]
          and [t for t in tools if t.startswith("mcp__forgecraft__")] == ["mcp__forgecraft__forgecraft_status"],
          [t for t in tools if "craft__" in t and ("meshcraft" in t or "forgecraft" in t)])
    log = os.path.join(gc, "logs", "install.log")
    started = open(log).read().splitlines()[0] if os.path.exists(log) else ""
    check("the global SessionStart hook started the Blender build in the background", "background build started" in started and "global" in started
          and "meshcraft" in started, started)
    # StudioCraft: connected at session start, or (a slower first start) connects during the session and runs
    studio_init = servers.get("studiocraft")
    if studio_init == "connected":
        check("session start: studiocraft connected", True)
    else:
        evs = s.ask("Call mcp__studiocraft__studio_status and say how many departments it lists.")
        ran = [r for r in calls(evs) if r[0] == "mcp__studiocraft__studio_status" and not r[2]]
        check(f"studiocraft connects in the same session and runs studio_status (status at session start: {studio_init})",
              bool(ran) and '"departments"' in ran[0][1], [r[:1] + (r[1][:120],) for r in calls(evs)])

else:
    # 2) MCP clients stand in for Claude Code: they connect to the registered servers before Blender exists
    from mcp_client import Client
    log = os.path.join(gc, "logs", "install.log")
    clients = {}
    for name in ("meshcraft", "forgecraft"):
        r = reg.get(name, {})
        clients[name] = Client([r.get("command", "")] + r.get("args", []), env=dict(env, **r.get("env", {})), cwd=proj)
    names = {n: sorted(t["name"] for t in c.tools()) for n, c in clients.items()}
    check("start: MeshCraft and ForgeCraft connect, each with only its status tool while Blender is missing",
          names == {"meshcraft": ["meshcraft_status"], "forgecraft": ["forgecraft_status"]}, names)
    hook = next((h["command"] for g in hooks for h in g.get("hooks", []) if "--global" in h.get("command", "")), "")
    hr = subprocess.run(hook, shell=True, cwd=proj, env=env, capture_output=True, text=True, timeout=60)  # as Claude Code runs it
    started = open(log).read().splitlines()[0] if os.path.exists(log) else ""
    check("the global SessionStart hook returns at once and starts the Blender build in the background",
          hr.returncode == 0 and "background build started" in started and "global" in started and "meshcraft" in started, (hr.stdout + hr.stderr)[-500:] or started)
    r = reg.get("studiocraft", {})
    sc = Client([r.get("command", "")] + r.get("args", []), env=dict(env, **r.get("env", {})), cwd=proj)
    ok, sst = sc.call("studio_status"); sc.close()
    check("studiocraft is registered and its studio_status runs from the other project", ok and len((sst or {}).get("departments", [])) == 9,
          str(sst)[:200])

# 3) wait for the build; time it
t_hook = time.time()
ready = lambda: os.path.isdir(os.path.join(gc, "meshcraft", "venv")) and any(
    n.startswith("bpy-") and n.endswith(".dist-info") for r, ds, _ in os.walk(os.path.join(gc, "meshcraft", "venv", "lib")) for n in ds)
done = lambda: (json.load(open(os.path.join(gc, "status.json")))["tools"].get("forgecraft", {}).get("state") == "ok") if os.path.exists(os.path.join(gc, "status.json")) else False
while time.time() - t_hook < a.build_timeout and not (ready() and done()):
    time.sleep(5)
first = os.path.getmtime(log) if os.path.exists(log) else time.time()
report["blender_build_seconds_after_hook"] = round(time.time() - t_hook, 1)
tail = open(log).read()[-1500:] if os.path.exists(log) else ""
check(f"background build finished: Blender + engine check + ForgeCraft ({report['blender_build_seconds_after_hook']} s, cold caches)",
      ready() and done(), tail)
report["install_log"] = [l for l in open(log).read().splitlines() if l.startswith("gitcraft: ")][-8:] if os.path.exists(log) else []
time.sleep(8)  # the servers poll every 3 s, then announce tools/list_changed

if a.mode == "session":
    # 4) the same session now has the full tools
    ev2 = s.ask("MeshCraft and ForgeCraft may have new tools now. Call mcp__meshcraft__list_templates and say how many templates "
                "it returns; then call mcp__forgecraft__hardware_probe and quote its blender capability.")
    c2 = calls(ev2)
    lt = next((t for n, t, err in c2 if n.endswith("list_templates") and not err), "")
    hp = next((t for n, t, err in c2 if n.endswith("hardware_probe") and not err), "")
    check("same session, no /mcp: MeshCraft's full tools (list_templates ran)", "boat" in lt and "chest" in lt, [n for n, _, _ in c2])
    check("same session, no /mcp: ForgeCraft's full tools (hardware_probe ran)", "blender" in hp.lower(), [n for n, _, _ in c2])
    s.close()

else:
    # 4) the same server processes now list and run their full tools (tools/list_changed; no reconnect)
    full = {}
    for _ in range(20):
        full = {n: [t["name"] for t in c.tools()] for n, c in clients.items()}
        if "list_templates" in full["meshcraft"] and "hardware_probe" in full["forgecraft"]: break
        time.sleep(1)
    ok_lt, lt = clients["meshcraft"].call("list_templates")
    ok_hp, hp = clients["forgecraft"].call("hardware_probe")
    check(f"same MeshCraft server, no reconnect: full tools ({len(full['meshcraft'])}) and list_templates ran",
          ok_lt and "boat" in json.dumps(lt) and "chest" in json.dumps(lt), full["meshcraft"][:8])
    check(f"same ForgeCraft server, no reconnect: full tools ({len(full['forgecraft'])}) and hardware_probe ran",
          ok_hp and "blender" in json.dumps(hp).lower(), full["forgecraft"][:8])
    for c in clients.values(): c.p.kill()

print(json.dumps({"work": work, "report": report, "failed": fails}, indent=1))
sys.exit(1 if fails else 0)
