"""DISCOVERY: what already exists, and what can really run here.

Reads the project (never runs its code): engine and framework, entry HTML and build folder, asset folders
and the assets already in them, tests, docs, git state. Asks the departments what is ready on this
machine (studio_status through the Studio executor; ForgeCraft's hardware probe for 3D work). The planner
reuses what exists (an existing `jump.wav` means no new jump sound) and plans honest `blocked` tasks for
what cannot run, instead of discovering it halfway through production."""
import json, os, re, subprocess
from . import executors

SKIP = {".git", "node_modules", "dist", "build", ".next", "out", "__pycache__", ".venv", "venv", "gitcraft-out", ".cache"}
KIND = {".wav": "audio", ".ogg": "audio", ".mp3": "audio", ".flac": "audio", ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image",
        ".gif": "image", ".svg": "vector", ".glb": "model", ".gltf": "model", ".fbx": "model", ".obj": "model", ".tmj": "level", ".ldtk": "level",
        ".mp4": "video", ".webm": "video", ".ttf": "font", ".woff": "font", ".woff2": "font"}
ASSET_DIRS = ["public/assets", "assets", "src/assets", "static", "public", "res", "resources"]


def _walk(root, limit=20000):
    n = 0
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP and not x.startswith(".")]
        for f in files:
            n += 1
            if n > limit: return
            yield os.path.join(d, f)


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def project(path):
    if not path: return {"exists": False, "path": None}
    if not os.path.isdir(path): return {"exists": False, "path": path}
    info = {"exists": True, "path": path, "name": os.path.basename(path.rstrip("/"))}
    files = list(_walk(path))
    rel = [os.path.relpath(f, path) for f in files]
    info["files"] = len(files)
    pkg = os.path.join(path, "package.json")
    deps = {}
    if os.path.exists(pkg):
        try:
            pj = json.load(open(pkg)); deps = {**pj.get("dependencies", {}), **pj.get("devDependencies", {})}
            info["package"] = {"name": pj.get("name"), "scripts": sorted(pj.get("scripts", {})), "dependencies": sorted(deps)}
        except (OSError, ValueError) as e:
            info["package"] = {"error": f"package.json unreadable: {e}"}
    code = [f for f in files if f.endswith((".js", ".mjs", ".ts", ".tsx", ".jsx", ".html"))][:200]
    src = " ".join(open(f, errors="ignore").read(200000) for f in code)
    engines = [e for e, pat in (("phaser", r"phaser"), ("three", r"\bthree\b|THREE\."), ("pixi", r"pixi"), ("react", r"\breact\b"), ("babylon", r"babylon"))
               if e in deps or re.search(pat, src, re.I)]
    if not engines and re.search(r"getContext\(\s*['\"]2d", src): engines = ["canvas"]
    info["engines"] = engines
    info["entry"] = next((r for r in ("index.html", "public/index.html", "src/index.html") if r in rel), None)
    info["build_dir"] = next((d for d in ("dist", "build", "out") if os.path.isfile(os.path.join(path, d, "index.html"))), None)
    assets = {}
    for r in rel:
        k = KIND.get(os.path.splitext(r)[1].lower())
        if k: assets.setdefault(k, []).append(r)
    info["assets"] = {k: {"count": len(v), "examples": v[:8]} for k, v in assets.items()}
    info["asset_stems"] = sorted({os.path.splitext(os.path.basename(r))[0].lower() for v in assets.values() for r in v})
    info["asset_dir"] = next((d for d in ASSET_DIRS if os.path.isdir(os.path.join(path, d))), None)
    info["tests"] = [r for r in rel if re.search(r"(^|/)(tests?|__tests__)/|\.(test|spec)\.[jt]sx?$", r)][:40]
    info["docs"] = [r for r in rel if r.lower().endswith(".md")][:40]
    if os.path.isdir(os.path.join(path, ".git")) or _git(path, "rev-parse", "--git-dir"):
        info["git"] = {"branch": _git(path, "rev-parse", "--abbrev-ref", "HEAD"), "commit": _git(path, "rev-parse", "--short", "HEAD"),
                       "dirty": bool(_git(path, "status", "--porcelain")), "remote": _git(path, "remote", "get-url", "origin")}
    return info


def runtimes(need_3d=False):
    """Every Studio action ready/blocked here (+ the 3D Department's probe when 3D work is planned)."""
    st = executors.studio_status()
    out = {"studio": st}
    if need_3d: out["three_d"] = executors.forgecraft_call("hardware_probe", {}, timeout=300)
    return out


def ready(disc, dept, action):
    """(True, None) or (False, reason) for one Studio action, from the discovery snapshot."""
    st = disc.get("runtimes", {}).get("studio") or {}
    if st.get("status") == "blocked": return False, st.get("reason")
    for d in st.get("departments", []):
        if d["department"] == dept:
            s = d["actions"].get(action)
            if s is None: return False, f"{dept} has no action {action}"
            return (True, None) if s == "ready" else (False, s.replace("blocked: ", "", 1))
    return False, f"department {dept} not found"


def run(spec):
    p = spec["project"]["path"]
    return {"project": project(p), "runtimes": runtimes(need_3d=spec["dimension"] == "3d" and bool(spec["assets"].get("models")))}
