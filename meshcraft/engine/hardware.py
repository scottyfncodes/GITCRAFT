"""What this machine can do for 3D work. Standard library only, so it answers without loading Blender.

Reports CPU, RAM, NVIDIA GPUs, free disk at the authorized roots, and each 3D capability with
whether it is available here and, when not, exactly why. Nothing is downloaded or contacted:
inside the GITCRAFT sandbox the network is closed.
"""
import glob, os, platform, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _meminfo():
    try:
        kv = dict(l.split(":", 1) for l in open("/proc/meminfo"))
        g = lambda k: round(int(kv[k].split()[0]) / 1024 / 1024, 1)
        return {"total_gb": g("MemTotal"), "available_gb": g("MemAvailable")}
    except Exception:
        return {"total_gb": None, "available_gb": None}


def _cpu():
    model = None
    try:
        model = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None)
    except Exception:
        pass
    try: usable = len(os.sched_getaffinity(0))
    except Exception: usable = os.cpu_count()
    return {"model": model or platform.processor() or None, "threads": usable, "arch": platform.machine()}


def _gpus():
    smi = shutil.which("nvidia-smi")
    if not smi:
        return [], "no NVIDIA driver (nvidia-smi not found): Cycles renders and bakes on the CPU"
    try:
        r = subprocess.run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        out = []
        for line in r.stdout.strip().splitlines():
            name, mem, drv = [x.strip() for x in line.split(",")]
            out.append({"name": name, "vram_gb": round(int(mem) / 1024, 1), "driver": drv})
        return out, None if out else "nvidia-smi found no GPU"
    except Exception as e:
        return [], f"nvidia-smi failed: {type(e).__name__}"


def _bpy_version():
    if "bpy" in sys.modules:
        return sys.modules["bpy"].app.version_string
    di = glob.glob(os.path.join(sys.prefix, "lib", "python*", "site-packages", "bpy-*.dist-info"))
    return di[0].rsplit("bpy-", 1)[1].replace(".dist-info", "") if di else None


def _disk(roots):
    out = []
    for r in roots:
        try:
            st = os.statvfs(r); out.append({"root": r, "free_gb": round(st.f_bavail * st.f_frsize / 2**30, 1)})
        except Exception:
            out.append({"root": r, "free_gb": None})
    return out


def probe(roots=()):
    gpus, gpu_note = _gpus()
    net = os.environ.get("GITCRAFT_ALLOW_NET") == "1"
    sandbox = os.environ.get("GITCRAFT_SANDBOX", "not sandboxed")
    engine_check = bool(shutil.which("node")) and os.path.isdir(os.path.join(HERE, "engine_check", "node_modules", "three"))
    bv = _bpy_version()
    caps = {
        "blender": {"available": bool(bv), "version": bv, "how": "bpy wheel, headless, in this process",
                    "reason": None if bv else "bpy is not installed in this Python (scripts/install.sh meshcraft)"},
        "texture_bake": {"available": bool(bv), "device": "CUDA available to Cycles" if gpus else "CPU",
                         "how": "Cycles EMIT bakes (web-pbr profile)"},
        "blockbench": {"available": True, "how": "file level: writes and reads .bbmodel (format 5.0), imports through Blender",
                       "note": "the Blockbench app has no headless mode, so it is never run; open the .bbmodel files in Blockbench to edit"},
        "mixamo": {"available": True, "how": "manual workflow: prepares the upload FBX and merges downloaded clips",
                   "note": "a person uses mixamo.com (Adobe ID); MeshCraft never contacts it"},
        "engine_check": {"available": engine_check, "how": "three@0.170 in headless Chromium",
                         "reason": None if engine_check else "needs node and `npm ci` in meshcraft/engine_check"},
        "photogrammetry": {"available": False, "reason": "not integrated yet (roadmap phase 3: Meshroom, optional install)"},
        "image_to_3d": {"available": False, "reason": "not integrated yet (roadmap phase 5: TripoSR / Hunyuan3D, opt-in, needs approval)"},
    }
    return {"cpu": _cpu(), "ram": _meminfo(), "gpus": gpus, "gpu_note": gpu_note, "disk": _disk(roots),
            "python": sys.version.split()[0], "os": f"{platform.system()} {platform.release()}",
            "sandbox": sandbox, "network": "allowed (GITCRAFT_ALLOW_NET=1)" if net else "denied by the sandbox",
            "capabilities": caps}
