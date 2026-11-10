"""What this machine can do for 3D work: the single hardware/capability probe for the 3D
Department (MeshCraft's hardware_probe and ForgeCraft's hardware_probe both return this).
Standard library only, no Blender import, no downloads; answers in well under a second.

Merged from MeshCraft's probe (CPU model, disk at the roots, sandbox, capability view) and
ForgeCraft's (photogrammetry and AI backends, job limits). Nothing is reported available
unless its code, runtime and (for AI models) weights or reachable endpoint are present."""
import glob, os, platform, shutil, socket, subprocess, sys

GITCRAFT_HOME = os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft"))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESHCRAFT_DIR = os.path.join(REPO, "meshcraft")
# One Blender for the whole department: MeshCraft's bpy venv (scripts/install.sh meshcraft).
BLENDER_PY = os.environ.get("FORGECRAFT_BLENDER_PY", os.path.join(GITCRAFT_HOME, "meshcraft", "venv", "bin", "python"))
# ForgeCraft's external generators (Meshroom, TripoSR/Hunyuan3D venv, model cache).
FORGE_HOME = os.environ.get("FORGECRAFT_HOME", os.path.join(GITCRAFT_HOME, "forgecraft"))
AI_VENV = os.path.join(FORGE_HOME, "ai-venv")


# ------------------------------------------------------------------ machine
def meminfo():
    try:
        kv = dict(l.split(":", 1) for l in open("/proc/meminfo"))
        g = lambda k: round(int(kv[k].split()[0]) / 1024 / 1024, 1)
        return {"total_gb": g("MemTotal"), "available_gb": g("MemAvailable")}
    except Exception:
        return {"total_gb": None, "available_gb": None}


def cpu():
    model = None
    try: model = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
    except Exception: pass
    try: usable = len(os.sched_getaffinity(0))
    except Exception: usable = os.cpu_count()
    return {"model": model or platform.processor() or None, "threads": usable, "arch": platform.machine()}


def gpus():
    """NVIDIA GPUs (CUDA is what Hunyuan3D, fast TripoSR and Meshroom's dense DepthMap need)."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return [], "no NVIDIA driver (nvidia-smi not found): Cycles renders and bakes on the CPU"
    try:
        r = subprocess.run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        out = []
        for line in r.stdout.strip().splitlines():
            name, mem, drv = [x.strip() for x in line.split(",")]
            out.append({"name": name, "vram_gb": round(int(mem) / 1024, 1), "driver": drv, "cuda": True})
        return out, None if out else "nvidia-smi found no GPU"
    except Exception as e:
        return [], f"nvidia-smi failed: {type(e).__name__}"


def disk(roots):
    out = []
    for r in roots:
        try: st = os.statvfs(r); out.append({"root": r, "free_gb": round(st.f_bavail * st.f_frsize / 2**30, 1)})
        except Exception: out.append({"root": r, "free_gb": None})
    return out


def net_ok(host, port=443, timeout=2):
    """True if a TLS connection is possible (through the session proxy when one is set).
    Inside the GITCRAFT sandbox (no network) this fails immediately."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    try:
        if proxy:
            h, p = proxy.split("://", 1)[-1].rstrip("/").rsplit(":", 1)
            s = socket.create_connection((h, int(p)), timeout=timeout)
            s.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
            ok = b" 200" in s.recv(200).split(b"\r\n", 1)[0]; s.close(); return ok
        socket.create_connection((host, port), timeout=timeout).close(); return True
    except Exception:
        return False


def _dist(venv, pkg):
    """Version of `pkg` installed in a venv, from its dist-info (no import: fast)."""
    hits = glob.glob(os.path.join(venv, "lib", "python*", "site-packages", f"{pkg}-*.dist-info"))
    return hits[0].rsplit(f"{pkg}-", 1)[1].replace(".dist-info", "") if hits else None


def bpy_version():
    if "bpy" in sys.modules and hasattr(sys.modules["bpy"], "app"):
        return sys.modules["bpy"].app.version_string
    return _dist(os.path.dirname(os.path.dirname(BLENDER_PY)), "bpy") or _dist(sys.prefix, "bpy")


def hf_cached(repo):
    hub = os.path.expanduser(os.environ.get("HF_HUB_CACHE", os.path.join(os.environ.get("HF_HOME", os.path.join(FORGE_HOME, "hf-cache")), "hub")))
    return bool(glob.glob(os.path.join(hub, "models--" + repo.replace("/", "--"), "snapshots", "*", "*")))


def meshcraft_templates():
    """Template ids from meshcraft/engine/templates/*.py without importing Blender."""
    import re
    out = []
    for f in sorted(glob.glob(os.path.join(MESHCRAFT_DIR, "engine", "templates", "*.py"))):
        if os.path.basename(f).startswith("_"): continue
        m = re.search(r'META\s*=\s*\{\s*"id"\s*:\s*"([a-z0-9_]+)"', open(f).read())
        if m: out.append(m.group(1))
    return out


# ------------------------------------------------------------------ backends
def blender():
    v = bpy_version()
    if not v:
        return {"installed": False, "available": False, "reason": "Blender (bpy) is not installed: scripts/install.sh meshcraft"}
    return {"installed": True, "available": True, "version": v, "python": BLENDER_PY,
            "render": "Cycles " + ("CUDA" if gpus()[0] else "CPU"), "note": "MeshCraft's bpy venv, shared by the whole department; EEVEE/Workbench need OpenGL, so headless work uses Cycles"}


def meshcraft():
    b = blender()
    if not os.path.exists(os.path.join(MESHCRAFT_DIR, "engine", "core.py")):
        return {"installed": False, "available": False, "reason": "meshcraft/engine not found"}
    return {"installed": b["installed"], "available": b["available"], "reason": b.get("reason"), "templates": meshcraft_templates(),
            "mode": "MeshCraft engine (templates, mesh processing, PBR bake, export profiles, validation)"}


def meshroom():
    found = sorted(glob.glob(os.path.join(FORGE_HOME, "Meshroom-*", "meshroom_batch")))
    if not found:
        return {"installed": False, "available": False, "reason": "Meshroom not installed: scripts/install-3d.sh meshroom"}
    root = os.path.dirname(found[-1]); cuda = bool(gpus()[0])
    return {"installed": True, "available": True, "version": os.path.basename(root).split("-", 1)[1], "batch": found[-1],
            "pipeline": "photogrammetry" if cuda else "photogrammetryDraft",
            "note": "full dense photogrammetry (CUDA DepthMap)" if cuda else "no CUDA GPU: Draft Meshing from the SfM point cloud (coarser)"}


def triposr():
    code = os.path.isfile(os.path.join(FORGE_HOME, "TripoSR", "run.py")); torch = bool(_dist(AI_VENV, "torch"))
    weights = os.environ.get("FORGECRAFT_TRIPOSR_WEIGHTS") or ("stabilityai/TripoSR" if hf_cached("stabilityai/TripoSR") else None)
    st = {"code": code, "torch": torch, "weights": bool(weights), "weights_source": weights, "device": "cuda" if gpus()[0] else "cpu"}
    if not weights and code and torch: st["weights_downloadable"] = net_ok("huggingface.co")
    st["available"] = code and torch and (bool(weights) or st.get("weights_downloadable", False))
    missing = [k for k in ("code", "torch") if not st[k]]
    if not (weights or st.get("weights_downloadable")): missing.append("weights (huggingface.co/stabilityai/TripoSR unreachable and not cached)")
    st["reason"] = None if st["available"] else "missing: " + ", ".join(missing) + " (scripts/install-3d.sh ai weights)"
    return st


def hunyuan3d():
    g = gpus()[0]; vram = max([x["vram_gb"] or 0 for x in g], default=0)
    local = {"hy3dgen": bool(_dist(AI_VENV, "hy3dgen")), "cuda_gpu": bool(g), "vram_gb": vram, "shape_ok": bool(g) and vram >= 6, "texture_ok": bool(g) and vram >= 16}
    local["available"] = local["hy3dgen"] and local["shape_ok"]
    remote = {"gradio_client": bool(_dist(AI_VENV, "gradio_client")), "space": os.environ.get("FORGECRAFT_HUNYUAN_SPACE", "tencent/Hunyuan3D-2")}
    remote["reachable"] = net_ok("huggingface.co") if remote["gradio_client"] else False
    remote["available"] = remote["gradio_client"] and remote["reachable"]
    accepted = os.environ.get("FORGECRAFT_HUNYUAN_LICENSE") == "accepted"
    st = {"local": local, "remote": remote, "license_accepted": accepted, "available": (local["available"] or remote["available"]) and accepted}
    why = []
    if not local["available"]: why.append("local needs hy3dgen + an NVIDIA GPU with ≥6 GB VRAM (≥16 GB with texture)" + ("" if g else "; no CUDA GPU here"))
    if not remote["available"]: why.append("remote HF Space needs gradio_client and network access to huggingface.co" + ("" if remote["reachable"] else " (unreachable)"))
    if not accepted: why.append("set FORGECRAFT_HUNYUAN_LICENSE=accepted after confirming the Tencent Hunyuan 3D Community License (not licensed in the EU, UK or South Korea)")
    st["reason"] = None if st["available"] else "; ".join(why)
    return st


def limits(ram_gb, has_gpu):
    ram = ram_gb or 0
    return {"max_concurrent_heavy_jobs": 1,
            "max_bake_resolution": 2048 if ram >= 15 else 1024 if ram >= 6 else 512,
            "max_triangles": 200000 if ram >= 15 else 80000,
            "timeouts_s": {"blender": 1200, "meshroom": 3600 if has_gpu else 5400, "triposr": 300 if has_gpu else 1800, "hunyuan3d": 1800},
            "meshroom_min_ram_gb": 8, "photogrammetry_max_images": 400 if has_gpu else 120}


def _engine_check_modules():
    """MeshCraft's resolver (meshcraft/engine/nodemods.py), loaded by path: it is standard library only."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_meshcraft_nodemods", os.path.join(MESHCRAFT_DIR, "engine", "nodemods.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.find()


# ------------------------------------------------------------------ probe
def probe(roots=()):
    g, gnote = gpus(); ram = meminfo(); c = cpu()
    net = os.environ.get("GITCRAFT_ALLOW_NET") == "1"
    engine_check = bool(shutil.which("node")) and bool(_engine_check_modules())
    b, mr, ts, hy = blender(), meshroom(), triposr(), hunyuan3d()
    backends = {"meshcraft": meshcraft(),
                "blockbench": {"installed": True, "available": True, "mode": "MeshCraft blockbench_* (.bbmodel 5.0 read/write, import through Blender)",
                               "note": "the Blockbench app has no headless mode; open the .bbmodel files in Blockbench to edit"},
                "mixamo": {"installed": True, "available": True, "mode": "MeshCraft mixamo_* (upload prep, bone-name clip merge with rest-pose checks)",
                           "note": "Mixamo has no public API; a person uploads and downloads at mixamo.com (free Adobe ID)"},
                "meshroom": mr, "triposr": ts, "hunyuan3d": hy}
    image3d = ts["available"] or hy["available"]
    capabilities = {   # MeshCraft's view (its tests and clients read these keys)
        "blender": {"available": b["available"], "version": b.get("version"), "how": "bpy wheel, headless", "reason": b.get("reason")},
        "texture_bake": {"available": b["available"], "device": "CUDA available to Cycles" if g else "CPU", "how": "Cycles EMIT bakes (web-pbr profile)"},
        "blockbench": {"available": True, "how": "file level: writes and reads .bbmodel (format 5.0), imports through Blender",
                       "note": backends["blockbench"]["note"]},
        "mixamo": {"available": True, "how": "manual workflow: prepares the upload FBX and merges downloaded clips", "note": backends["mixamo"]["note"]},
        "engine_check": {"available": engine_check, "how": "three@0.170 in headless Chromium",
                         "reason": None if engine_check else "needs node and three@0.170 + gltf-validator: scripts/install.sh meshcraft"},
        "photogrammetry": {"available": mr["available"], "how": "ForgeCraft photogrammetry: Meshroom → MeshCraft process_mesh",
                           "reason": mr.get("reason"), "note": mr.get("note")},
        "image_to_3d": {"available": image3d, "how": "ForgeCraft generate with a reference image: TripoSR / Hunyuan3D → MeshCraft process_mesh",
                        "reason": None if image3d else f"TripoSR: {ts['reason']}; Hunyuan3D: {hy['reason']}"},
    }
    dk = disk(roots or [GITCRAFT_HOME if os.path.isdir(GITCRAFT_HOME) else "/"])
    return {"cpu": c, "ram": ram, "gpus": g, "gpu_note": gnote, "disk": dk, "python": sys.version.split()[0],
            "os": f"{platform.system()} {platform.release()}", "sandbox": os.environ.get("GITCRAFT_SANDBOX", "not sandboxed"),
            "network": "allowed (GITCRAFT_ALLOW_NET=1)" if net else "denied by the sandbox",
            "capabilities": capabilities, "backends": dict(backends, blender=b), "limits": limits(ram["total_gb"], bool(g)),
            # compact machine summary (ForgeCraft UI)
            "hardware": {"cpu_threads": c["threads"], "ram": ram, "gpus": g, "disk_free_gb": dk[0]["free_gb"] if dk else None,
                         "network": {"allowed_by_gitcraft": net}}}


if __name__ == "__main__":
    import json; print(json.dumps(probe(), indent=1))
