#!/usr/bin/env python3
"""Updating the runtime never breaks a server that is already running from it.

The failure this guards against (seen in a cloud session): the session-start self-update installed a new runtime
while that session's MCP servers were starting. The servers run under Landlock (scripts/sandbox.py), which binds
read access to the runtime's folders by inode when the server starts. The old installer replaced the folders
(`rm -rf runtime && mv new runtime`), so every running server got EACCES on the whole runtime
("PermissionError: ... runtime/production/__init__.py") until it was restarted.

  python3 tests/test_runtime_update.py

A sandboxed "server" starts from version 1, the runtime is updated to version 2 underneath it, then the server
imports a module it had not loaded yet: it must still work, on version 1. A control replays the old replacement
and must reproduce the EACCES, so the test is known to detect the bug."""
import os, shutil, subprocess, sys, tempfile, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(REPO, "scripts", "install-runtime.sh")
SANDBOX = os.path.join(REPO, "scripts", "sandbox.py")
results = []


def check(name, ok, detail=None):
    ok = bool(ok); results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"   -> {str(detail)[:400]}"))


def landlock():
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True); libc.syscall.restype = ctypes.c_long
    return libc.syscall(444, None, ctypes.c_size_t(0), ctypes.c_uint32(1)) > 0


MCP_HERE = next(l for l in open(os.path.join(REPO, "scripts", "mcp.sh")) if l.startswith("here="))


def source(root, version, extra=False):
    """A minimal checkout: production/ with a module loaded at start and one imported later, and scripts/where.sh,
    which resolves its folder with scripts/mcp.sh's own line (so this test follows how the real launcher does it)."""
    os.makedirs(os.path.join(root, "production"), exist_ok=True)
    os.makedirs(os.path.join(root, "scripts"), exist_ok=True)
    open(os.path.join(root, "scripts", "where.sh"), "w").write(MCP_HERE + 'dirname "$here"\n')
    open(os.path.join(root, "production", "__init__.py"), "w").write(f"VERSION = {version!r}\n")
    # the engine names its own version and the package's: a mixed import reads "engine v2 / package v1"
    open(os.path.join(root, "production", "engine.py"), "w").write(f"from . import VERSION\nENGINE = 'engine {version} / package ' + VERSION\n")
    if extra: open(os.path.join(root, "production", "added_in_v2.py"), "w").write("X = 1\n")
    return root


def install(home, src):
    return subprocess.run(["bash", INSTALL, src], env=dict(os.environ, GITCRAFT_HOME=home), capture_output=True, text=True, timeout=120)


SERVER = r"""
import importlib.util, os, sys, time
# production/ by its path, as studio/server.py loads it: inside the sandbox the runtime root is not listable
p = os.path.join(sys.argv[1], "production")
spec = importlib.util.spec_from_file_location("production", os.path.join(p, "__init__.py"), submodule_search_locations=[p])
production = importlib.util.module_from_spec(spec); sys.modules["production"] = production; spec.loader.exec_module(production)
go, out = sys.argv[2], sys.argv[3]
while not os.path.exists(go): time.sleep(0.05)
try:
    from production import engine         # imported lazily, after the update
    r = engine.ENGINE
except Exception as e:
    r = f"{type(e).__name__}: {e}"
open(out, "w").write(r)
"""


def launch_root(runtime):
    """The runtime folder a server launched through <runtime>/scripts/mcp.sh works from."""
    return subprocess.run(["bash", os.path.join(runtime, "scripts", "where.sh")], capture_output=True, text=True).stdout.strip()


def start_server(work, runtime):
    """A sandboxed process launched the way scripts/mcp.sh launches one: from the folder mcp.sh resolves, granted
    that folder's directories by path at start."""
    runtime = launch_root(runtime)
    go, out = os.path.join(work, "go"), os.path.join(work, "out")
    for p in (go, out):
        if os.path.exists(p): os.remove(p)
    script = os.path.join(work, "server.py"); open(script, "w").write(SERVER)
    grants = []
    for d in ("/usr", "/lib", "/lib64", "/lib32", "/bin", "/sbin", "/etc", "/opt", sys.prefix, sys.base_prefix):
        if os.path.isdir(d): grants += ["--rx", d]
    grants += ["--rx", os.path.join(runtime, "production"), "--rw", work]
    p = subprocess.Popen([sys.executable, SANDBOX, *grants, "--", sys.executable, "-I", script, runtime, go, out],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    time.sleep(1.0)                        # let it start and load production/__init__ under the sandbox
    return p, go, out


def finish(p, go, out):
    open(go, "w").close()
    try: p.wait(timeout=30)
    except subprocess.TimeoutExpired: p.kill(); return "timeout"
    return open(out).read() if os.path.exists(out) else f"no output (exit {p.returncode}): {p.stderr.read()[-300:]}"


if not landlock():
    print("SKIP Landlock is not available on this kernel: the sandbox cannot be exercised here")
    sys.exit(0)

# the server may write only `work` (its go/out files); the runtimes and sources live outside every grant, as
# ~/.gitcraft/runtime does for a real server (granted read-only by path, nothing more)
work = tempfile.mkdtemp(prefix="gitcraft-runtime-")
base = tempfile.mkdtemp(prefix="gitcraft-runtime-homes-")
try:
    home = os.path.join(base, "home"); runtime = os.path.join(home, "runtime")
    v1 = source(os.path.join(base, "src1"), "v1"); v2 = source(os.path.join(base, "src2"), "v2", extra=True)

    # ---- the fix: install v1, start a server, install v2 underneath it
    r = install(home, v1)
    check("install: v1 installed behind the runtime symlink", r.returncode == 0 and os.path.islink(runtime)
          and open(os.path.join(runtime, "production", "__init__.py")).read() == "VERSION = 'v1'\n", r.stderr or r.stdout)
    p, go, out = start_server(work, runtime)
    r = install(home, v2)
    check("install: v2 installed while the server runs", r.returncode == 0, r.stderr)
    got = finish(p, go, out)
    check("running server: still reads its runtime after the update (no EACCES)", got == "engine v1 / package v1", got)
    check("running server: imports one consistent version (no mix of v1 and v2 modules)", got == "engine v1 / package v1", got)
    check("new server: starts on v2", open(os.path.join(runtime, "production", "__init__.py")).read() == "VERSION = 'v2'\n"
          and os.path.exists(os.path.join(runtime, "production", "added_in_v2.py")))
    p, go, out = start_server(work, runtime)
    got = finish(p, go, out)
    check("new server: a sandboxed server started after the update runs v2", got == "engine v2 / package v2", got)

    # ---- migration: a runtime that is still a plain folder (installed by the old installer). Its running servers name
    # files by "<runtime>/...", so it is never replaced under them: the update is deferred, then applied once none runs
    home2 = os.path.join(base, "home2"); rt2 = os.path.join(home2, "runtime")
    shutil.copytree(v1, rt2)
    p, go, out = start_server(work, rt2)
    r = install(home2, v2)
    check("migration: with a server running from the plain-folder runtime, the update is deferred", r.returncode == 0
          and "deferred" in r.stdout and not os.path.islink(rt2), r.stdout + r.stderr)
    got = finish(p, go, out)
    check("migration: ...and that server keeps working, on its version", got == "engine v1 / package v1", got)
    r = install(home2, v2)
    check("migration: with nothing running from it, the plain folder is moved aside and the runtime becomes the symlink",
          r.returncode == 0 and os.path.islink(rt2) and open(os.path.join(rt2, "production", "__init__.py")).read() == "VERSION = 'v2'\n"
          and any(v.startswith("legacy-") for v in os.listdir(os.path.join(home2, "runtimes"))), r.stdout + r.stderr)

    # ---- idempotent from the runtime itself, and pruning keeps what may be in use
    r = subprocess.run(["bash", INSTALL, os.path.realpath(runtime)], env=dict(os.environ, GITCRAFT_HOME=home), capture_output=True, text=True)
    check("install: from the runtime itself is a no-op", r.returncode == 0 and "runtime ready" not in r.stdout, r.stdout)
    for _ in range(3): install(home, v2); time.sleep(1.1)
    vs = [v for v in os.listdir(os.path.join(home, "runtimes")) if not v.endswith(".partial")]
    check("prune: recent versions are kept (a server may still run from them)", len(vs) >= 5, vs)
    old = sorted(os.path.join(home, "runtimes", v) for v in vs)
    for v in old: os.utime(v, (time.time() - 30 * 86400,) * 2)
    install(home, v2)
    vs = [v for v in os.listdir(os.path.join(home, "runtimes")) if not v.endswith(".partial")]
    check("prune: old versions go, the current and the previous stay", len(vs) == 2 and os.path.realpath(runtime) in
          [os.path.realpath(os.path.join(home, "runtimes", v)) for v in vs], vs)

    # ---- control: the old replacement reproduces the failure, so the checks above can detect it
    home3 = os.path.join(base, "home3"); rt3 = os.path.join(home3, "runtime")
    shutil.copytree(v1, rt3)
    p, go, out = start_server(work, rt3)
    tmp = rt3 + ".new"; shutil.copytree(v2, tmp); shutil.rmtree(rt3); os.rename(tmp, rt3)
    got = finish(p, go, out)
    check("control: the old `rm -rf runtime && mv new runtime` denies the running server (EACCES / ImportError)",
          "PermissionError" in got or "ImportError" in got, got)
    # control: the old in-place overwrite (rsync --delete) lets a running server import a mix of versions
    home4 = os.path.join(base, "home4"); rt4 = os.path.join(home4, "runtime")
    shutil.copytree(v1, rt4)
    p, go, out = start_server(work, rt4)
    shutil.copytree(v2, rt4, dirs_exist_ok=True)
    got = finish(p, go, out)
    check("control: the old in-place overwrite mixes versions in a running server", got == "engine v2 / package v1", got)
finally:
    shutil.rmtree(work, ignore_errors=True); shutil.rmtree(base, ignore_errors=True)

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
