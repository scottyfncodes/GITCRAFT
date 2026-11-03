"""Proof test: MeshCraft and ForgeCraft connect in real Claude Code sessions even when Blender lands mid-session.

The bug: install.sh only registered the 3D servers once Blender was installed, and mcp.sh refused to start them
before that. Claude Code reads MCP servers when a session starts, so a session that began before the Blender
install (setup skipped 3D or ran out of time, install.sh run during the session, the background build still
running) never got them.

This test drives real Claude Code sessions (`claude -p`, stream-json) against an isolated GITCRAFT home and Claude
config, built from THIS checkout:
  1. Blender "not installed": a session starts. It must list the two status tools, with meshcraft/forgecraft
     connected.
  2. Blender lands while that same session is open (the venv is linked in, as install.sh leaves it). The session
     must see MeshCraft's full tool list (tools/list_changed) and run a Blender tool (the bridge).
  3. A fresh session: everything in-process (the normal path), every tool listed.

  python3 tests/test_mcp_deferred_session.py [--repo PATH] [--blender-venv ~/.gitcraft/meshcraft]
Needs a working `claude` CLI and an installed MeshCraft venv to link in (scripts/install.sh meshcraft).
Exit 1 on any failure.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, threading, time, queue

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ap.add_argument("--blender-venv", default=os.path.expanduser("~/.gitcraft/meshcraft"))
ap.add_argument("--bin", default=os.path.expanduser("~/.gitcraft/bin"), help="prebuilt 2D tools to reuse")
ap.add_argument("--work", default=None)
a = ap.parse_args()
fails = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)
    if not ok: fails.append(name)


work = a.work or tempfile.mkdtemp(prefix="gitcraft-deferred-")
home, cfg, proj = (os.path.join(work, d) for d in ("gitcraft-home", "claude-config", "project"))
for d in (home, cfg, proj): shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
os.symlink(a.bin, os.path.join(home, "bin"))
env = dict(os.environ, GITCRAFT_HOME=home, CLAUDE_CONFIG_DIR=cfg, GITCRAFT_ROOT=proj, GITCRAFT_ROOTS=proj, GITCRAFT_MESHCRAFT="0")
for k in ("CLAUDE_PROJECT_DIR", "GITCRAFT_3D_LIBRARY", "FORGECRAFT_BLENDER_PY"): env.pop(k, None)
# install the runtime + registration from this checkout, with no Blender (as a setup script with GITCRAFT_MESHCRAFT=0)
r = subprocess.run([os.path.join(a.repo, "scripts", "install-global.sh")], env=env, capture_output=True, text=True)
reg = json.load(open(os.path.join(cfg, ".claude.json"))).get("mcpServers", {}) if os.path.exists(os.path.join(cfg, ".claude.json")) else {}
check("meshcraft + forgecraft registered before Blender is installed", {"meshcraft", "forgecraft"} <= set(reg), sorted(reg))


class Session:
    """One live Claude Code session (stream-json in/out)."""

    def __init__(self):
        cmd = ["claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--allowedTools", "mcp__meshcraft", "mcp__forgecraft", "--max-turns", "6"]
        self.p = subprocess.Popen(cmd, cwd=proj, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.q = queue.Queue(); self.events = []
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.p.stdout:
            try: self.q.put(json.loads(line))
            except ValueError: pass
        self.q.put(None)

    def ask(self, text, timeout=600):
        self.p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"); self.p.stdin.flush()
        got, end = [], time.time() + timeout
        while time.time() < end:
            try: ev = self.q.get(timeout=5)
            except queue.Empty: continue
            if ev is None: break
            got.append(ev); self.events.append(ev)
            if ev.get("type") == "result": break
        return got

    def close(self):
        try: self.p.stdin.close(); self.p.wait(timeout=60)
        except Exception: self.p.kill()


def tool_calls(evs):
    """[(tool name, result text)] for every tool call in these events."""
    uses, out = {}, []
    for ev in evs:
        msg = ev.get("message")
        for c in (msg.get("content") or [] if isinstance(msg, dict) else []):
            if not isinstance(c, dict): continue
            if c.get("type") == "tool_use": uses[c["id"]] = c["name"]
            if c.get("type") == "tool_result":
                txt = c.get("content")
                txt = "".join(x.get("text", "") for x in txt) if isinstance(txt, list) else str(txt)
                out.append((uses.get(c.get("tool_use_id"), "?"), txt))
    return out


ASK_TOOLS = ("List every tool you have whose name starts with mcp__meshcraft__ or mcp__forgecraft__, one per line, "
             "exact names, nothing else.")

# 1. a session that starts before Blender is installed
s = Session()
ev1 = s.ask(ASK_TOOLS)
init = next((e for e in ev1 if e.get("type") == "system" and e.get("subtype") == "init"), {})
servers = {m["name"]: m.get("status") for m in init.get("mcp_servers", [])}
check("session 1: meshcraft and forgecraft connected at session start (no Blender yet)",
      servers.get("meshcraft") == "connected" and servers.get("forgecraft") == "connected", servers)
mc_tools = [t for t in init.get("tools", []) if t.startswith("mcp__meshcraft__")]
check("session 1: MeshCraft lists only its status tool while Blender is missing", mc_tools == ["mcp__meshcraft__meshcraft_status"], mc_tools)

# 2. Blender lands while session 1 is open (install.sh leaves the venv here)
# hard links: real files under this GITCRAFT home, like a real install (the sandbox fences resolved paths, so a symlink
# out to another home would be refused, as it should be)
os.makedirs(os.path.join(home, "meshcraft"), exist_ok=True)
subprocess.run(["cp", "-al", os.path.join(a.blender_venv, "venv"), os.path.join(home, "meshcraft", "venv")], check=True)
time.sleep(8)   # the servers poll every 3 s and announce tools/list_changed
ev2 = s.ask("Your MeshCraft tools may have changed. Call mcp__meshcraft__list_templates and tell me how many templates it "
            "returns, then call mcp__meshcraft__meshcraft_status and quote its blender and mode fields.")
calls = tool_calls(ev2)
names = [n for n, _ in calls]
lt = next((t for n, t in calls if n.endswith("list_templates")), "")
st = next((t for n, t in calls if n.endswith("meshcraft_status")), "")
check("session 1: after the install, the same session runs a Blender tool (list_templates)", "boat" in lt and "chest" in lt, names)
check("session 1: ... through the bridge (server started before Blender)", "bridge" in st and "blender" in st, st[:200])
s.close()

# 3. a fresh session: the normal, in-process path
s3 = Session()
ev3 = s3.ask("Call mcp__meshcraft__meshcraft_status and quote its blender and mode fields.")
init3 = next((e for e in ev3 if e.get("type") == "system" and e.get("subtype") == "init"), {})
tools3 = init3.get("tools", [])
servers3 = {m["name"]: m.get("status") for m in init3.get("mcp_servers", [])}
st3 = next((t for n, t in tool_calls(ev3) if n.endswith("meshcraft_status")), "")
check("fresh session: meshcraft + forgecraft connected", servers3.get("meshcraft") == "connected" and servers3.get("forgecraft") == "connected", servers3)
check("fresh session: every MeshCraft and ForgeCraft tool listed",
      sum(t.startswith("mcp__meshcraft__") for t in tools3) >= 25 and sum(t.startswith("mcp__forgecraft__") for t in tools3) >= 10,
      f"{sum(t.startswith('mcp__meshcraft__') for t in tools3)} meshcraft, {sum(t.startswith('mcp__forgecraft__') for t in tools3)} forgecraft")
check("fresh session: Blender runs in-process (the normal path, not one-shot)", '"mode": "in-process"' in st3 or "in-process" in st3, st3[:200])
s3.close()

print(json.dumps({"work": work, "failed": fails}))
sys.exit(1 if fails else 0)
