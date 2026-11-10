#!/usr/bin/env python3
"""MeshCraft's engine check finds its Node packages wherever they were installed, and slow optional installs can be
queued for the session instead of a setup script.

  python3 tests/test_engine_check_deps.py

Checks (standard library; the node checks run when node and an installed three@0.170 are present):
  - nodemods.find: a checkout without node_modules falls back to $GITCRAFT_HOME/meshcraft/engine_check; a wrong version
    is never used; MESHCRAFT_NODE_MODULES wins
  - validate.mjs and meshopt_decode.mjs load their packages from MESHCRAFT_NODE_MODULES
  - gitcraft_engine_check_ready: needs both packages and the success marker for this exact lockfile
  - install-later.sh: queues only install-3d.sh / install-studio.sh with plain component names; run-later.sh drops a
    job for any other script and keeps a failed job for the next session
"""
import importlib.util, json, os, shutil, subprocess, sys, tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("nodemods", os.path.join(REPO, "meshcraft", "engine", "nodemods.py"))
nodemods = importlib.util.module_from_spec(spec); spec.loader.exec_module(nodemods)
PINS = nodemods.pinned()
results = []


def check(name, ok, detail=""):
    results.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [{detail}]"))


def fake_modules(root, versions):
    for pkg, v in versions.items():
        os.makedirs(os.path.join(root, pkg), exist_ok=True)
        json.dump({"name": pkg, "version": v}, open(os.path.join(root, pkg, "package.json"), "w"))
    return root


tmp = tempfile.mkdtemp(prefix="gc_ecdeps_")
saved = {k: os.environ.get(k) for k in ("GITCRAFT_HOME", "MESHCRAFT_NODE_MODULES")}
try:
    os.environ.pop("MESHCRAFT_NODE_MODULES", None)
    home = os.path.join(tmp, "home"); os.environ["GITCRAFT_HOME"] = home
    local = os.path.join(nodemods.ENGINE_CHECK, "node_modules")
    has_local = os.path.isdir(local)
    installed = os.path.join(home, "meshcraft", "engine_check", "node_modules")

    check("pins: package.json pins three and gltf-validator", PINS.get("three") and PINS.get("gltf-validator"), PINS)
    if not has_local:
        check("find: nothing installed anywhere → None (engine check reports how to install)", nodemods.find() is None, nodemods.candidates())
    fake_modules(installed, {"three": "0.1.0", "gltf-validator": PINS["gltf-validator"]})
    if not has_local:
        check("find: a wrong three version is never used", nodemods.find() is None, nodemods.find())
    fake_modules(installed, PINS)
    want = local if has_local else installed
    check(f"find: {'the checkout' if has_local else 'a checkout without node_modules falls back to $GITCRAFT_HOME'}",
          nodemods.find() == os.path.realpath(want), (nodemods.find(), want))
    over = fake_modules(os.path.join(tmp, "override"), PINS)
    os.environ["MESHCRAFT_NODE_MODULES"] = over
    check("find: MESHCRAFT_NODE_MODULES comes first", nodemods.find() == os.path.realpath(over), nodemods.find())
    os.environ.pop("MESHCRAFT_NODE_MODULES")

    # the scripts themselves, against a real install (the one this machine has, if any)
    os.environ["GITCRAFT_HOME"] = saved["GITCRAFT_HOME"] or os.path.expanduser("~/.gitcraft")
    real = nodemods.find()
    if shutil.which("node") and real:
        work = os.path.join(tmp, "copy"); shutil.copytree(nodemods.ENGINE_CHECK, work, ignore=shutil.ignore_patterns("node_modules"))
        glb = os.path.join(tmp, "tri.glb")
        # smallest valid GLB: one triangle
        import struct
        pos = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        js = json.dumps({"asset": {"version": "2.0"}, "scenes": [{"nodes": [0]}], "scene": 0, "nodes": [{"mesh": 0}],
                         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
                         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0]}],
                         "bufferViews": [{"buffer": 0, "byteLength": 36}], "buffers": [{"byteLength": 36}]}).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        open(glb, "wb").write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + 36) + struct.pack("<II", len(js), 0x4E4F534A) + js
                              + struct.pack("<II", 36, 0x004E4942) + pos)
        env = nodemods.env(real)
        r = subprocess.run(["node", os.path.join(work, "validate.mjs"), glb], capture_output=True, text=True, env=env, timeout=120)
        ok = r.returncode == 0 and json.loads(r.stdout or "{}").get("issues", {}).get("numErrors") == 0
        check("validate.mjs (copy without node_modules) loads gltf-validator from MESHCRAFT_NODE_MODULES", ok, r.stderr[-400:] or r.stdout[:200])
        out = os.path.join(tmp, "plain.glb")
        r = subprocess.run(["node", os.path.join(work, "meshopt_decode.mjs"), glb, out], capture_output=True, text=True, env=env, timeout=120)
        check("meshopt_decode.mjs (copy without node_modules) loads three from MESHCRAFT_NODE_MODULES", r.returncode == 0 and os.path.getsize(out) > 0, r.stderr[-400:])
    else:
        print("skip node checks: node or an installed three@0.170 not found (scripts/install.sh meshcraft)")

    # shell side
    sh = os.path.join(REPO, "scripts")
    home2 = os.path.join(tmp, "home2"); ec = os.path.join(home2, "meshcraft", "engine_check")
    def ready():
        return subprocess.run(["bash", "-c", f'source "{sh}/tools.sh"; gitcraft_engine_check_ready "{REPO}"'],
                              env=dict(os.environ, GITCRAFT_HOME=home2)).returncode == 0
    fake_modules(os.path.join(ec, "node_modules"), PINS)
    check("ready: packages without the success marker are not ready (an npm ci cut off part-way)", not ready())
    shutil.copy(os.path.join(nodemods.ENGINE_CHECK, "package-lock.json"), os.path.join(ec, ".installed-lock"))
    check("ready: packages + the marker for this lockfile", ready())
    open(os.path.join(ec, ".installed-lock"), "a").write("\n")
    check("ready: a marker from another lockfile is not ready (reinstall on a dependency change)", not ready())

    env3 = dict(os.environ, GITCRAFT_HOME=os.path.join(tmp, "home3"))
    q = os.path.join(tmp, "home3", "later")
    run = lambda *a: subprocess.run(["bash", os.path.join(sh, a[0]), *a[1:]], capture_output=True, text=True, env=env3)
    check("install-later: refuses a script other than install-3d.sh / install-studio.sh", run("install-later.sh", "install.sh", "x").returncode == 2)
    check("install-later: refuses a component that is not a plain word", run("install-later.sh", "install-3d.sh", "ai;rm").returncode == 2)
    r = run("install-later.sh", "install-studio.sh", "nosuchpart")
    check("install-later: queues a job", r.returncode == 0 and os.path.exists(os.path.join(q, "install-studio-nosuchpart.job")), r.stderr)
    open(os.path.join(q, "evil.job"), "w").write("install.sh meshcraft\n")
    r = run("run-later.sh")
    check("run-later: drops a job naming another script without running it", not os.path.exists(os.path.join(q, "evil.job")) and "dropped" in r.stdout, r.stdout)
    check("run-later: a failed job stays queued with its attempt counted",
          os.path.exists(os.path.join(q, "install-studio-nosuchpart.job")) and open(os.path.join(q, "install-studio-nosuchpart.tries")).read().strip() == "1", r.stdout)
    run("run-later.sh"); r = run("run-later.sh")
    check("run-later: dropped after 3 failed attempts", not os.path.exists(os.path.join(q, "install-studio-nosuchpart.job")) and "failed 3 times" in r.stdout, r.stdout)
finally:
    for k, v in saved.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    shutil.rmtree(tmp, ignore_errors=True)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
