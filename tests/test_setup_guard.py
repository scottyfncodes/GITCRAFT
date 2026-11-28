#!/usr/bin/env python3
"""Setup always finishes fast: 3D is on demand, and nothing over the size limit is downloaded during setup.

  python3 tests/test_setup_guard.py            offline: the real scripts against an empty HOME, downloaders stubbed
  python3 tests/test_setup_guard.py --timed    also a clean run of scripts/setup-env.sh (fresh HOME, cold caches,
                                               this checkout's committed branch), which must finish in under a minute

Checks:
  - the default: GITCRAFT_MESHCRAFT is on demand (0); install.sh installs no 3D component and still registers the two
    3D servers; naming meshcraft/forgecraft is what installs them
  - "during setup" is GITCRAFT_SETUP=1, or setup-env.sh's marker until the first session: never inside a session,
    never after an hour, never with GITCRAFT_SETUP=0; the SessionStart hook removes the marker
  - the guard: over the limit means skipped, with exactly one line, logged, exit 0, and no downloader started; at or
    under the limit, or outside setup, nothing is skipped
  - every large component of install-3d.sh and install-studio.sh is guarded, and install.sh's Blender and voice model
  - the 3D capability summary: never probed or printed during setup; outside setup one line, printed once
"""
import json, os, shutil, stat, subprocess, sys, tempfile, time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SH = os.path.join(REPO, "scripts")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{str(detail)[-700:]}]"), flush=True)


tmp = tempfile.mkdtemp(prefix="gc_setup_guard_")
stubs = os.path.join(tmp, "stubs"); os.makedirs(stubs)
calls = os.path.join(tmp, "downloads.log")
for tool in ("curl", "wget", "pip", "uv", "npm"):   # anything that could download: record the call and fail
    p = os.path.join(stubs, tool)
    open(p, "w").write(f'#!/bin/sh\necho "{tool} $*" >> "{calls}"\nexit 97\n'); os.chmod(p, 0o755)


def downloads():
    return open(calls).read() if os.path.exists(calls) else ""


def base_env(home, **extra):
    """No Claude Code CLI or session, no terminal: what a setup script's process sees."""
    path = ":".join([stubs] + [d for d in os.environ.get("PATH", "").split(":") if d and not os.path.exists(os.path.join(d, "claude"))])
    env = dict(os.environ, HOME=home, PATH=path, GITCRAFT_GLOBAL_INSTRUCTIONS="0", GITCRAFT_GLOBAL_HOOK="0", GITCRAFT_CC0_SOURCES="0")
    for k in ("GITCRAFT_HOME", "GITCRAFT_ROOT", "GITCRAFT_ROOTS", "GITCRAFT_MESHCRAFT", "GITCRAFT_STUDIO", "GITCRAFT_STUDIO_VOICE", "GITCRAFT_SETUP",
              "GITCRAFT_SETUP_MAX_MB", "GITCRAFT_3D_LIBRARY", "FORGECRAFT_HOME", "GITCRAFT_STUDIO_HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR",
              "CLAUDECODE", "CLAUDE_CODE_SESSION_ID"):
        env.pop(k, None)
    env.update(extra)
    return env


def run(args, env, cwd=None):
    return subprocess.run(args, env=env, cwd=cwd or tmp, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=600)


def tools(snippet, env):
    return run(["bash", "-c", f'source "{SH}/tools.sh"; {snippet}'], env)


def new_home(name):
    h = os.path.join(tmp, name); os.makedirs(os.path.join(h, ".gitcraft", "logs")); return h, os.path.join(h, ".gitcraft")


# --- the default, and what counts as "during setup"
home, gc = new_home("h1")
check("default: 3D is on demand (GITCRAFT_MESHCRAFT=0)", tools('echo "$GITCRAFT_MESHCRAFT"', base_env(home)).stdout.strip() == "0")
in_setup = lambda **e: tools("gitcraft_in_setup", base_env(home, **e)).returncode == 0
marker = os.path.join(gc, "setup-phase")
check("setup: not by default", not in_setup())
check("setup: GITCRAFT_SETUP=1 (what setup-env.sh exports)", in_setup(GITCRAFT_SETUP="1"))
open(marker, "w").write("now\n")
check("setup: setup-env.sh's marker covers later lines of a setup script", in_setup())
check("setup: the marker never applies inside a Claude Code session", not in_setup(CLAUDECODE="1") and not in_setup(CLAUDE_CODE_SESSION_ID="x"))
check("setup: GITCRAFT_SETUP=0 turns the guard off", not in_setup(GITCRAFT_SETUP="0"))
old = time.time() - 2 * 3600; os.utime(marker, (old, old))
check("setup: a marker older than an hour no longer counts", not in_setup())
os.remove(marker)

# --- the guard itself
r = tools('gitcraft_setup_allows "a big thing" 101 "run it later"; echo "rc=$?"', base_env(home, GITCRAFT_SETUP="1"))
lines = r.stdout.strip().splitlines()
check("guard: over the limit during setup is refused with exactly one line that says how to get it later",
      lines[-1] == "rc=1" and len(lines) == 2 and "setup skipped a big thing" in lines[0] and "run it later" in lines[0] and "100 MB" in lines[0], r.stdout)
log = os.path.join(gc, "logs", "setup-skipped.log")
check("guard: the skip is logged", os.path.exists(log) and "setup skipped a big thing" in open(log).read())
check("guard: at the limit is allowed, silently", tools('gitcraft_setup_allows x 100 y; echo "rc=$?"', base_env(home, GITCRAFT_SETUP="1")).stdout.strip() == "rc=0")
check("guard: outside setup nothing is refused", tools('gitcraft_setup_allows x 99999 y; echo "rc=$?"', base_env(home)).stdout.strip() == "rc=0")
check("guard: GITCRAFT_SETUP_MAX_MB moves the limit",
      tools('gitcraft_setup_allows x 101 y >/dev/null; echo "rc=$?"', base_env(home, GITCRAFT_SETUP="1", GITCRAFT_SETUP_MAX_MB="500")).stdout.strip() == "rc=0")
check("guard: direct downloads get curl's size cap during setup, and none outside it",
      tools("gitcraft_curl_cap", base_env(home, GITCRAFT_SETUP="1")).stdout.strip() == f"--max-filesize {100 * 1024 * 1024}"
      and tools("gitcraft_curl_cap", base_env(home)).stdout.strip() == "")

# --- every large component, called the way a setup script's extra lines call them
for label, extra in (("GITCRAFT_SETUP=1", {"GITCRAFT_SETUP": "1"}), ("the setup-phase marker", {})):
    home, gc = new_home("h-" + ("env" if extra else "marker"))
    if not extra: open(os.path.join(gc, "setup-phase"), "w").write("now\n")
    env = base_env(home, **extra)
    r3 = run([os.path.join(SH, "install-3d.sh"), "core", "meshroom", "ai", "weights"], env)
    rs = run([os.path.join(SH, "install-studio.sh"), "voice", "mocap", "music", "unirig"], env)
    out = (r3.stdout + r3.stderr + rs.stdout + rs.stderr).strip().splitlines()
    check(f"{label}: Blender, Meshroom, the AI runtimes, weights, voice, mocap, music and UniRig are each skipped with one line, exit 0",
          r3.returncode == 0 and rs.returncode == 0 and len(out) == 8 and all("setup skipped" in l for l in out), out)
    made = sorted(os.listdir(os.path.join(gc, "forgecraft")) if os.path.isdir(os.path.join(gc, "forgecraft")) else []) + \
        sorted(os.listdir(os.path.join(gc, "studio")) if os.path.isdir(os.path.join(gc, "studio")) else [])
    check(f"{label}: no downloader was started and nothing was installed", downloads() == "" and made == [] and not os.path.exists(os.path.join(gc, "meshcraft", "venv")),
          (downloads(), made))
    check(f"{label}: no 3D capability probe and no capability line", not os.path.exists(os.path.join(gc, "forgecraft", "probe.json"))
          and "gitcraft-3d: ready" not in r3.stdout, r3.stdout)

# --- install.sh, the default install path (the seven tools present, Studio off: no network needed)
def seeded_home(name):
    home, gc = new_home(name)
    os.makedirs(os.path.join(gc, "bin"))
    for t in ("photocraft", "vectorcraft", "filmcraft", "lightcraft", "pdfcraft", "effectcraft", "designcraft"):
        p = os.path.join(gc, "bin", t + "-cli"); open(p, "w").write("#!/bin/sh\n"); os.chmod(p, 0o755)
    return home, gc


def states(gc):
    return {k: v["state"] for k, v in json.load(open(os.path.join(gc, "status.json")))["tools"].items()}


home, gc = seeded_home("h-install")
r = run([os.path.join(SH, "install.sh")], base_env(home, GITCRAFT_STUDIO="0"))
st = states(gc); reg = json.load(open(os.path.join(home, ".claude.json")))["mcpServers"]
check("install.sh (default): no 3D component is installed or downloaded; MeshCraft and ForgeCraft are recorded off",
      r.returncode == 0 and st.get("meshcraft") == "off" and st.get("forgecraft") == "off" and downloads() == ""
      and not os.path.exists(os.path.join(gc, "meshcraft", "venv")) and "meshcraft" not in r.stdout.replace("registered meshcraft", ""), r.stdout + r.stderr)
check("install.sh (default): the two 3D servers are still registered, so a session can install them on demand", {"meshcraft", "forgecraft", "photocraft"} <= set(reg), sorted(reg))
check("install.sh (default): no capability report", "gitcraft-3d" not in r.stdout + r.stderr and not os.path.exists(os.path.join(gc, "forgecraft", "probe.json")))
r = run([os.path.join(SH, "install.sh")], base_env(home, GITCRAFT_STUDIO="0", GITCRAFT_MESHCRAFT="1", GITCRAFT_SETUP="1"))
skipped = [l for l in r.stdout.splitlines() if "setup skipped" in l]
check("install.sh during setup with GITCRAFT_MESHCRAFT=1: Blender is skipped with one line, exit 0, nothing downloaded",
      r.returncode == 0 and len(skipped) == 1 and "Blender" in skipped[0] and "install-3d.sh" in skipped[0] and states(gc).get("meshcraft") == "off" and downloads() == "",
      r.stdout + r.stderr)
r = run([os.path.join(SH, "install.sh"), "meshcraft", "forgecraft"], base_env(home, GITCRAFT_STUDIO="0"))
check("install.sh meshcraft forgecraft (named, outside setup) does start the Blender install",
      "installing meshcraft" in r.stdout and any(l.startswith(("uv ", "pip ")) for l in downloads().splitlines()), r.stdout + r.stderr + downloads())
if os.path.exists(calls): os.remove(calls)

# --- the voice model: over the limit, so setup leaves it to the first session (decided before any download)
home, gc = seeded_home("h-voice")
r = run([os.path.join(SH, "install.sh")], base_env(home, GITCRAFT_SETUP="1"))   # Studio core fails here (stubbed downloaders): not what is checked
skipped = [l for l in r.stdout.splitlines() if "setup skipped" in l]
check("install.sh during setup: the voice model is left to the first session, with one line",
      len(skipped) == 1 and "voice model" in skipped[0] and states(gc).get("studiocraft-voice") == "later" and "kokoro" not in downloads(), r.stdout + r.stderr)
if os.path.exists(calls): os.remove(calls)

# --- the SessionStart hook ends the setup phase (nothing missing here, so it starts nothing)
home, gc = seeded_home("h-hook")
open(os.path.join(gc, "setup-phase"), "w").write("now\n")
r = run([os.path.join(SH, "session-start.sh"), "--global"], base_env(home, GITCRAFT_STUDIO="0", CLAUDECODE="1"))
check("session start: the setup-phase marker is removed, and no 3D build is started by default",
      r.returncode == 0 and not os.path.exists(os.path.join(gc, "setup-phase")) and r.stdout.strip() == "" and not os.path.exists(os.path.join(gc, "meshcraft")), r.stdout + r.stderr)

# --- the capability summary: one line, once (a component that is already there: nothing to download)
home, gc = seeded_home("h-report")
mr = os.path.join(gc, "forgecraft", "Meshroom-0.0.0"); os.makedirs(mr)
open(os.path.join(mr, "meshroom_batch"), "w").write("#!/bin/sh\n"); os.chmod(os.path.join(mr, "meshroom_batch"), 0o755)
env = base_env(home, GITCRAFT_STUDIO="0")
first = run([os.path.join(SH, "install-3d.sh"), "meshroom"], env)
second = run([os.path.join(SH, "install-3d.sh"), "meshroom"], env)
n = lambda r: sum(l.startswith("gitcraft-3d: ready: ") for l in r.stdout.splitlines())
check("capability summary: one line the first time", first.returncode == 0 and n(first) == 1 and len(first.stdout.strip().splitlines()) == 2, first.stdout + first.stderr)
check("capability summary: printed once (a second run with nothing new is silent about it)", n(second) == 0, second.stdout)
check("capability summary: the probe is saved for the tools", os.path.exists(os.path.join(gc, "forgecraft", "probe.json")))
during = run([os.path.join(SH, "install-3d.sh"), "meshroom"], dict(env, GITCRAFT_SETUP="1", FORGECRAFT_HOME=os.path.join(gc, "fresh-forge")))
check("capability summary: never during setup", n(during) == 0 and not os.path.exists(os.path.join(gc, "fresh-forge", "probe.json")), during.stdout)

# --- a clean, timed run of the real setup
if "--timed" in sys.argv:
    work = os.path.join(tmp, "timed"); home = os.path.join(work, "home"); os.makedirs(home)
    if os.path.isdir(os.path.expanduser("~/.ccr")): os.symlink(os.path.expanduser("~/.ccr"), os.path.join(home, ".ccr"))   # the cloud proxy's CA
    branch = subprocess.check_output(["git", "-C", REPO, "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    env = base_env(home, PATH=os.environ["PATH"], PIP_CACHE_DIR=os.path.join(work, "pip"), UV_CACHE_DIR=os.path.join(work, "uv"), npm_config_cache=os.path.join(work, "npm"),
                   GITCRAFT_REPO_URL=REPO, GITCRAFT_REF=branch)
    for k in ("GITCRAFT_GLOBAL_INSTRUCTIONS", "GITCRAFT_GLOBAL_HOOK", "GITCRAFT_CC0_SOURCES"): env.pop(k)
    t0 = time.time()
    r = subprocess.run(["bash"], stdin=open(os.path.join(SH, "setup-env.sh")), env=env, cwd=home, capture_output=True, text=True, timeout=1800)
    secs = time.time() - t0
    gc = os.path.join(home, ".gitcraft"); st = states(gc) if os.path.exists(os.path.join(gc, "status.json")) else {}
    limit = float(os.environ.get("GITCRAFT_TEST_SETUP_LIMIT", "60"))
    check(f"timed: a clean default setup finishes in {secs:.1f} s (limit {limit:.0f} s)", r.returncode == 0 and secs < limit, r.stdout[-900:] + r.stderr[-400:])
    check("timed: the seven tools and the Studio core are installed and all ten servers registered",
          all(st.get(t) == "ok" for t in ("photocraft", "vectorcraft", "filmcraft", "lightcraft", "pdfcraft", "effectcraft", "designcraft", "studiocraft"))
          and len(json.load(open(os.path.join(home, ".claude.json")))["mcpServers"]) == 10, st)
    check("timed: no 3D component, no capability probe or report", st.get("meshcraft") == "off" and not os.path.exists(os.path.join(gc, "meshcraft", "venv"))
          and not os.path.exists(os.path.join(gc, "forgecraft", "probe.json")) and "gitcraft-3d" not in r.stdout, st)
    print(f"  setup took {secs:.1f} s; skipped: " + "; ".join(l.split("setup skipped ")[1].split(" (")[0] for l in r.stdout.splitlines() if "setup skipped" in l))

shutil.rmtree(tmp, ignore_errors=True)
print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
