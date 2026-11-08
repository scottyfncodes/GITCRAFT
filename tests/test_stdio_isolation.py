#!/usr/bin/env python3
"""The MCP servers' JSON-RPC pipes are private: no child process can read, write or re-flag them (#45).

The bug: every child of studiocraft/forgecraft/meshcraft (Node/Chromium, FFmpeg, Blender, department CLIs)
inherited fd 0 and fd 1, the protocol pipes. FFmpeg reads keystrokes from stdin; a child that sets O_NONBLOCK on
the shared pipe makes the server's next read return EAGAIN, which ends `for line in sys.stdin` as if the client
had gone. The server then exited 0 in the middle of a request (CI: "server exited").

  1. behaviour, per server: a minimal server built from that server's own private_stdio() keeps answering while a
     hostile child sets O_NONBLOCK on its stdin/stdout and reads stdin; a CONTROL server with the old plain
     `for line in sys.stdin` must stop under the same child (proves this test detects the bug)
  2. the real servers, launched by scripts/mcp.sh: fd 0 is /dev/null, fd 1 is stderr's target, every descriptor
     still on a protocol pipe is close-on-exec, and the server answers real calls

    python3 tests/test_stdio_isolation.py"""
import ast, json, os, subprocess, sys, tempfile, textwrap, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from mcp_client import Client
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:300]}]" if detail and not cond else ""), flush=True)


SERVERS = {"studiocraft": "studio/server.py", "forgecraft": "forgecraft/server.py", "meshcraft": "meshcraft/server.py"}

# the hostile child: what FFmpeg / Node did to the inherited protocol pipe
HOSTILE = textwrap.dedent('''
    import fcntl, os, select
    for fd in (0, 1):
        try: fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)
        except OSError: pass
    if select.select([0], [], [], 0.2)[0]:
        try: os.read(0, 1)            # FFmpeg-style keystroke read
        except OSError: pass
''')

MINI = textwrap.dedent('''
    import os, subprocess, sys, json
    {helper}
    HOSTILE = {hostile!r}
    if {private}:
        rin, rout = private_stdio()
    else:
        rin, rout = sys.stdin, sys.stdout
    n = 0
    for line in rin:
        n += 1
        if line.strip() == "spawn":
            subprocess.run([sys.executable, "-c", HOSTILE])          # inherits fd 0/1, as department children did
        rout.write(json.dumps({{"n": n, "got": line.strip()}}) + "\\n"); rout.flush()
    sys.stderr.write("loop ended\\n")
''')


def helper_source(path):
    tree = ast.parse(open(os.path.join(REPO, path)).read())
    fn = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "private_stdio"), None)
    return ast.get_source_segment(open(os.path.join(REPO, path)).read(), fn) if fn else None


def converse(helper, private):
    """Send spawn, then (after the child has re-flagged the pipe) more requests with gaps; count answers."""
    code = MINI.format(helper=helper or "", hostile=HOSTILE, private=private)
    p = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    answers = []
    def ask(s):
        try:
            p.stdin.write((s + "\n").encode()); p.stdin.flush()
        except BrokenPipeError:
            return
        line = p.stdout.readline()
        if line: answers.append(json.loads(line))
    ask("spawn")
    for i in range(4):
        time.sleep(0.3)        # the pipe is empty between requests: where a non-blocking read returns EAGAIN
        ask(f"req{i}")
    alive = p.poll() is None
    p.stdin.close(); p.wait(timeout=10)
    return len(answers), alive


# ---- 1. behaviour: each server's own helper, and the control that reproduces the bug
n, alive = converse(None, False)
check("control: the old plain stdin loop is broken by a child that re-flags the shared pipe (bug reproduced)", not (n == 5 and alive), (n, alive))
for name, path in SERVERS.items():
    src = helper_source(path)
    check(f"{name}: defines private_stdio()", src is not None)
    if not src: continue
    n, alive = converse(src, True)
    check(f"{name}: keeps answering after a hostile child (5/5 answered, still running)", n == 5 and alive, (n, alive))

# ---- 2. the real servers through the launcher
def descendants(pid):
    out, todo = [], [pid]
    while todo:
        p = todo.pop()
        try: kids = open(f"/proc/{p}/task/{p}/children").read().split()
        except OSError: kids = []
        for k in kids: out.append(int(k)); todo.append(int(k))
    return out


def comm(pid):
    try: return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode()
    except OSError: return ""


ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-stdio-"))
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "c.sqlite"),
           GITCRAFT_3D_LIBRARY=os.path.join(ws, "3d"), GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"))
calls = {"studiocraft": ("studio_status", {}), "forgecraft": ("hardware_probe", {}), "meshcraft": ("meshcraft_status", {})}
for name, path in SERVERS.items():
    try:
        c = Client([os.path.join(REPO, "scripts", "mcp.sh"), name], env=env, log=os.path.join(ws, name + ".log"))
    except Exception as e:
        check(f"{name}: starts through scripts/mcp.sh", False, e); continue
    try:
        c.tools()
        srv = next((p for p in descendants(c.p.pid) if path in comm(p)), None)
        if srv is None:
            print(f"SKIP {name}: no server process found under the guard ({[comm(p)[:80] for p in descendants(c.p.pid)]})"); continue
        fd0 = os.readlink(f"/proc/{srv}/fd/0"); fd1 = os.readlink(f"/proc/{srv}/fd/1"); fd2 = os.readlink(f"/proc/{srv}/fd/2")
        check(f"{name}: fd 0 is /dev/null (children inherit nothing to read or re-flag)", fd0 == "/dev/null", fd0)
        check(f"{name}: fd 1 is stderr's target (a child's stray output cannot enter the protocol)", fd1 == fd2, (fd1, fd2))
        protocol = set()
        for fd in os.listdir(f"/proc/{srv}/fd"):
            try: tgt = os.readlink(f"/proc/{srv}/fd/{fd}")
            except OSError: continue
            if tgt.startswith("pipe:") and int(fd) > 2 and tgt != fd2: protocol.add(int(fd))
        flags = {fd: int(next(l for l in open(f"/proc/{srv}/fdinfo/{fd}") if l.startswith("flags:")).split()[1], 8) for fd in protocol}
        check(f"{name}: the protocol pipes are held only on close-on-exec descriptors", protocol and all(f & 0o2000000 for f in flags.values()),
              {fd: oct(f) for fd, f in flags.items()})
        tool, args = calls[name]
        ok, r = c.call(tool, args, timeout=300)
        check(f"{name}: still answers a real call over the private pipes ({tool})", ok, str(r)[:200])
    finally:
        c.p.kill()

bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
