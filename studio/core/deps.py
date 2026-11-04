"""Dependency checks: what a department can really execute on this machine.

Each manifest dependency names a kind and how to find it. Checks never start a heavy runtime
(no Blender, no model load): they look for interpreters, wheels' metadata, binaries, model files
and node modules, so studio_status answers in milliseconds.

kinds: python (module in the studio venv), venv (module in another venv), binary (on PATH),
       blender (MeshCraft's bpy venv), node_module (a folder), playwright (module + Chromium),
       files (model weights etc.), gpu (an NVIDIA GPU), never (documented but not installable here)"""
import glob, os, shutil, subprocess
from . import GITCRAFT_HOME, REPO, STUDIO_HOME

_memo = {}
PW_CANDIDATES = [os.environ.get("PLAYWRIGHT_MODULE"), "/opt/node-tools/node_modules/playwright",
                 os.path.join(STUDIO_HOME, "node", "node_modules", "playwright")]
CHROMIUM = [os.environ.get("CHROMIUM_PATH"), "/opt/pw-browsers/chromium"]


def expand(s):
    return (s or "").replace("{STUDIO_HOME}", STUDIO_HOME).replace("{GITCRAFT_HOME}", GITCRAFT_HOME).replace("{REPO}", REPO)


def blender_python():
    return os.path.join(GITCRAFT_HOME, "meshcraft", "venv", "bin", "python")


def _site_has(py, module):
    root = os.path.dirname(os.path.dirname(py))
    pats = [f"{root}/lib/python*/site-packages/{module}", f"{root}/lib/python*/site-packages/{module}.py",
            f"{root}/lib/python*/site-packages/{module}-*.dist-info", f"{root}/lib/python*/site-packages/{module.replace('_', '-')}-*.dist-info"]
    return any(glob.glob(p) for p in pats)


WEIGHTS = ("model.safetensors", "model.safetensors.index.json", "pytorch_model.bin", "diffusion_pytorch_model.safetensors",
           "diffusion_pytorch_model.safetensors.index.json", "diffusion_pytorch_model.bin")


def _has_weights(d):
    return os.path.isdir(d) and any(os.path.exists(os.path.join(d, w)) for w in WEIGHTS)


def _has_lib(name):
    """A system shared library (lib<name>.so*) in the usual places; no ldconfig (it may not run in the sandbox)."""
    dirs = ["/lib", "/usr/lib", "/lib64", "/usr/lib64", "/usr/local/lib"] + glob.glob("/usr/lib/*-linux-gnu") + glob.glob("/lib/*-linux-gnu")
    dirs += [d for d in os.environ.get("LD_LIBRARY_PATH", "").split(":") if d]
    return any(glob.glob(os.path.join(d, f"lib{name}.so*")) for d in dirs)


def _version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip().splitlines()[0][:120]
    except Exception:
        return None


def check_one(dep_id, spec):
    key = (dep_id, repr(sorted(spec.items())))
    if key in _memo: return _memo[key]
    kind = spec["kind"]; r = {"kind": kind, "license": spec.get("license"), "install": spec.get("install")}
    if spec.get("alternatives"): r["alternatives"] = spec["alternatives"]
    if kind == "python":
        import importlib.util
        ok = importlib.util.find_spec(spec["module"]) is not None
        r.update(available=ok, reason=None if ok else f"Python module {spec['module']} is not installed in the studio venv")
    elif kind == "venv":
        py = expand(spec["python"]); ok = os.access(py, os.X_OK) and _site_has(py, spec["module"])
        files = [expand(f) for f in spec.get("files", [])]; missing = [f for f in files if not os.path.isfile(f)]
        libs = [l for l in spec.get("system_libs", []) if not _has_lib(l)]   # e.g. MediaPipe's libEGL/libGLESv2
        missing += [w for w in map(expand, spec.get("weights_dirs", [])) if not _has_weights(w)]   # e.g. ACE-Step checkpoints
        r.update(available=ok and not missing and not libs, python=py,
                 reason=None if ok and not missing and not libs else (f"{spec['module']} not installed in {os.path.dirname(os.path.dirname(py))}" if not ok
                                                         else f"model files missing: {', '.join(os.path.basename(m) for m in missing)}" if missing
                                                         else f"system libraries missing: {', '.join('lib' + l for l in libs)} ({spec.get('system_install', 'install them with the system package manager')})"))
    elif kind == "binary":
        p = shutil.which(spec["bin"])
        r.update(available=bool(p), path=p, version=_version(spec["version_cmd"]) if p and spec.get("version_cmd") else None,
                 reason=None if p else f"{spec['bin']} is not on PATH")
    elif kind == "blender":
        py = blender_python(); ok = os.access(py, os.X_OK) and _site_has(py, "bpy")
        di = glob.glob(os.path.join(os.path.dirname(os.path.dirname(py)), "lib/python*/site-packages/bpy-*.dist-info"))
        r.update(available=ok, python=py, version=("blender " + os.path.basename(di[0])[4:-10]) if di else None,
                 reason=None if ok else "MeshCraft's Blender (bpy) is not installed: scripts/install.sh meshcraft")
        r.setdefault("install", "scripts/install.sh meshcraft")
    elif kind == "node_module":
        p = expand(spec["path"]); ok = os.path.isdir(p) and bool(shutil.which("node"))
        ver = None
        try:
            import json; ver = json.load(open(os.path.join(p, "package.json"))).get("version")
        except Exception: pass
        r.update(available=ok, path=p, version=ver, reason=None if ok else (f"node module missing at {p}" if shutil.which("node") else "node is not on PATH"))
    elif kind == "playwright":
        pw = next((p for p in PW_CANDIDATES if p and os.path.isdir(p)), None)
        if not pw:
            try:
                g = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=10).stdout.strip()
                pw = os.path.join(g, "playwright") if os.path.isdir(os.path.join(g, "playwright")) else None
            except Exception: pw = None
        chrome = next((c for c in CHROMIUM if c and os.path.exists(c)), None)
        r.update(available=bool(pw and chrome and shutil.which("node")), module=pw, chromium=chrome,
                 reason=None if pw and chrome else ("Playwright module not found" if not pw else "Chromium not found (/opt/pw-browsers/chromium or CHROMIUM_PATH)"))
    elif kind == "files":
        files = [expand(f) for f in spec["files"]]; missing = [f for f in files if not os.path.isfile(f)]
        r.update(available=not missing, reason=f"missing: {', '.join(missing)}" if missing else None)
    elif kind == "hosts":
        # network for a sandboxed tool: netgate must allow every host (GITCRAFT_NETGATE lists the allowed patterns);
        # unsandboxed (cli, tests) the environment's own network policy decides at call time
        sandboxed = "nonet" in (os.environ.get("GITCRAFT_SANDBOX") or "")   # set by sandbox.py when TCP is denied
        allowed = [h for h in (os.environ.get("GITCRAFT_NETGATE") or "").split(",") if h]
        def ok_host(h): return any(h == a or (a.startswith("*.") and h.endswith(a[1:]) and h != a[2:]) for a in allowed)
        miss = [h for h in spec["hosts"] if not ok_host(h)] if sandboxed else []
        r.update(available=not miss, hosts=spec["hosts"],
                 reason=None if not miss else f"no network allowance for {', '.join(miss)} (studiocraft runs sandboxed: add them to ~/.gitcraft/allow-hosts as "
                                              f"`studiocraft: <host>` and to the environment's allowed domains, then start a new session)")
    elif kind == "gpu":
        ok = bool(shutil.which("nvidia-smi")) and _version(["nvidia-smi", "-L"]) not in (None, "")
        r.update(available=ok, reason=None if ok else "no NVIDIA GPU on this machine")
    elif kind == "never":
        r.update(available=False, reason=spec.get("reason", "not installable here"))
    else:
        r.update(available=False, reason=f"unknown dependency kind {kind}")
    if r["available"]: _memo[key] = r   # only cache what was found: a runtime installed later is seen on the next check
    return r


def check(manifest, ids):
    deps = manifest.get("dependencies", {})
    return {i: check_one(i, deps[i]) for i in ids}


def resolve_playwright():
    r = check_one("playwright", {"kind": "playwright"})
    return r.get("module"), r.get("chromium")
