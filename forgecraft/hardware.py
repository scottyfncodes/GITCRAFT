"""Hardware and backend detection for the 3D Department. Standard library only.

Everything here is a probe of the real machine: no backend is reported available unless
its code, runtime and (for AI models) weights or reachable endpoint are actually present."""
import glob, json, os, shutil, socket, subprocess, time

GITCRAFT_HOME = os.path.expanduser(os.environ.get("GITCRAFT_HOME", "~/.gitcraft"))
MC_HOME = os.environ.get("FORGECRAFT_HOME", os.path.join(GITCRAFT_HOME, "forgecraft"))
# ForgeCraft drives the same Blender as MeshCraft (the bpy venv `scripts/install.sh meshcraft` creates), so Blender is installed once.
BLENDER_PY = os.environ.get("FORGECRAFT_BLENDER_PY", os.path.join(GITCRAFT_HOME, "meshcraft", "venv", "bin", "python"))
HERE = os.path.dirname(os.path.abspath(__file__))
MESHCRAFT_DIR = os.path.join(os.path.dirname(HERE), "meshcraft")   # MeshCraft's template engine, used as a backend


def _run(cmd, timeout=10):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None


def meminfo():
    out = {}
    try:
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1); out[k] = int(v.split()[0]) * 1024
    except OSError:
        pass
    return {"total_gb": round(out.get("MemTotal", 0) / 2**30, 1), "available_gb": round(out.get("MemAvailable", 0) / 2**30, 1)}


def gpus():
    """NVIDIA GPUs via nvidia-smi (CUDA is what Hunyuan3D, TripoSR-GPU and Meshroom DepthMap need)."""
    found = []
    if shutil.which("nvidia-smi"):
        r = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
        if r and r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                name, mem, drv = [x.strip() for x in line.split(",")]
                found.append({"name": name, "vram_gb": round(int(mem) / 1024, 1), "driver": drv, "cuda": True})
    if not found and glob.glob("/dev/nvidia[0-9]*"):
        found.append({"name": "NVIDIA device (nvidia-smi missing)", "vram_gb": None, "cuda": True})
    return found


def net_ok(host, port=443, timeout=3):
    """True if a TCP/TLS connection through the session's proxy policy is possible."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    try:
        if proxy:
            ph = proxy.split("://", 1)[-1].rstrip("/"); h, p = ph.rsplit(":", 1)
            s = socket.create_connection((h, int(p)), timeout=timeout)
            s.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
            ok = b" 200" in s.recv(200).split(b"\r\n", 1)[0]
            s.close(); return ok
        socket.create_connection((host, port), timeout=timeout).close(); return True
    except Exception:
        return False


def blender():
    if not os.access(BLENDER_PY, os.X_OK):
        return {"installed": False, "reason": f"{BLENDER_PY} missing; run scripts/install.sh meshcraft (ForgeCraft uses MeshCraft's Blender)"}
    r = _run([BLENDER_PY, "-c", "import bpy;print(bpy.app.version_string)"], 120)
    if not r or r.returncode != 0:
        return {"installed": False, "reason": "bpy failed to import: " + ((r.stderr if r else "timeout")[-300:])}
    return {"installed": True, "version": r.stdout.strip().splitlines()[-1], "python": BLENDER_PY,
            "render": "Cycles CPU" + (" + CUDA" if gpus() else ""), "note": "EEVEE/Workbench need OpenGL/EGL; not used headless"}


def meshcraft():
    """MeshCraft's template engine (meshcraft/, merged separately) used as a ForgeCraft backend."""
    eng = os.path.join(MESHCRAFT_DIR, "engine", "core.py")
    if not os.path.exists(eng): return {"installed": False, "available": False, "reason": "meshcraft/ engine not found"}
    if not os.access(BLENDER_PY, os.X_OK): return {"installed": False, "available": False, "reason": "MeshCraft's Blender venv missing: scripts/install.sh meshcraft"}
    d = os.path.join(MESHCRAFT_DIR, "engine", "templates")
    tpl = sorted(f[:-3] for f in os.listdir(d) if f.endswith(".py") and not f.startswith("_"))
    return {"installed": True, "available": True, "templates": tpl, "mode": "MeshCraft run_pipeline (brief → build → validate → export)"}


def meshroom():
    found = sorted(glob.glob(os.path.join(MC_HOME, "Meshroom-*", "meshroom_batch")))
    if not found:
        return {"installed": False, "reason": "Meshroom not installed; run scripts/install-3d.sh meshroom"}
    root = os.path.dirname(found[-1])
    cuda = bool(gpus())
    return {"installed": True, "version": os.path.basename(root).split("-", 1)[1], "batch": found[-1],
            "pipeline": "photogrammetry" if cuda else "photogrammetryDraft",
            "note": "full dense photogrammetry (CUDA DepthMap)" if cuda else "no CUDA GPU: Draft Meshing from the SfM point cloud (coarser)"}


def _venv_has(venv, module):
    py = os.path.join(venv, "bin", "python")
    if not os.access(py, os.X_OK): return False
    r = _run([py, "-c", f"import {module}"], 120)
    return bool(r and r.returncode == 0)


def hf_cached(repo):
    hub = os.path.expanduser(os.environ.get("HF_HUB_CACHE", os.path.join(os.environ.get("HF_HOME", "~/.cache/huggingface"), "hub")))
    d = os.path.join(hub, "models--" + repo.replace("/", "--"), "snapshots")
    return bool(glob.glob(os.path.join(d, "*", "*")))


def triposr():
    code = os.path.join(MC_HOME, "TripoSR")
    venv = os.path.join(MC_HOME, "ai-venv")
    weights = os.environ.get("FORGECRAFT_TRIPOSR_WEIGHTS") or ("stabilityai/TripoSR" if hf_cached("stabilityai/TripoSR") else None)
    st = {"code": os.path.isfile(os.path.join(code, "run.py")), "torch": _venv_has(venv, "torch"),
          "weights": bool(weights), "weights_source": weights, "device": "cuda" if gpus() else "cpu"}
    if not st["weights"] and st["code"] and st["torch"]:
        st["weights_downloadable"] = net_ok("huggingface.co")
    st["available"] = st["code"] and st["torch"] and (st["weights"] or st.get("weights_downloadable", False))
    missing = [k for k in ("code", "torch") if not st[k]]
    if not (st["weights"] or st.get("weights_downloadable")): missing.append("weights (huggingface.co/stabilityai/TripoSR unreachable and not cached)")
    st["reason"] = "ready" if st["available"] else "missing: " + ", ".join(missing)
    return st


def hunyuan3d():
    venv = os.path.join(MC_HOME, "ai-venv")
    g = gpus(); vram = max([x["vram_gb"] or 0 for x in g], default=0)
    local = {"hy3dgen": _venv_has(venv, "hy3dgen"), "cuda_gpu": bool(g), "vram_gb": vram,
             "shape_ok": bool(g) and vram >= 6, "texture_ok": bool(g) and vram >= 16}
    local["available"] = local["hy3dgen"] and local["shape_ok"]
    remote = {"gradio_client": _venv_has(venv, "gradio_client"), "space": os.environ.get("FORGECRAFT_HUNYUAN_SPACE", "tencent/Hunyuan3D-2"),
              "network": os.environ.get("GITCRAFT_ALLOW_NET") == "1" or None}
    remote["reachable"] = net_ok("huggingface.co") if remote["gradio_client"] else False
    remote["available"] = remote["gradio_client"] and remote["reachable"]
    accepted = os.environ.get("FORGECRAFT_HUNYUAN_LICENSE") == "accepted"
    st = {"local": local, "remote": remote, "license_accepted": accepted,
          "available": (local["available"] or remote["available"]) and accepted}
    why = []
    if not local["available"]:
        why.append("local needs hy3dgen + an NVIDIA GPU with ≥6 GB VRAM (≥16 GB with texture)" + ("" if g else "; no CUDA GPU here"))
    if not remote["available"]:
        why.append("remote HF Space needs gradio_client and network access to huggingface.co" + ("" if remote["reachable"] else " (unreachable)"))
    if not accepted:
        why.append("set FORGECRAFT_HUNYUAN_LICENSE=accepted after confirming the Tencent Hunyuan 3D Community License (not licensed in the EU, UK or South Korea)")
    st["reason"] = "ready" if st["available"] else "; ".join(why)
    return st


def probe(full=True):
    disk = shutil.disk_usage(GITCRAFT_HOME if os.path.isdir(GITCRAFT_HOME) else "/")
    hw = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cpu_threads": os.cpu_count(), "ram": meminfo(),
          "gpus": gpus(), "disk_free_gb": round(disk.free / 2**30, 1),
          "network": {"allowed_by_gitcraft": os.environ.get("GITCRAFT_ALLOW_NET") == "1"}}
    be = {"blender": blender(), "blockbench": {"installed": True, "available": True, "mode": "file format (.bbmodel read/write); the Blockbench desktop app has no headless API",
                                                "note": "open the .bbmodel in Blockbench to hand-edit; ForgeCraft converts it with Blender"},
          "mixamo": {"available": True, "mode": "import of Mixamo FBX downloads + Mixamo-named procedural rig",
                     "note": "Mixamo has no public API; uploads and downloads are done by a person at mixamo.com (free Adobe ID)"},
          "meshroom": meshroom(), "meshcraft": meshcraft()}
    if full:
        be["triposr"] = triposr(); be["hunyuan3d"] = hunyuan3d()
    for k, v in be.items():
        v.setdefault("available", v.get("installed", False))
    return {"hardware": hw, "backends": be, "limits": limits(hw)}


def limits(hw):
    ram = hw["ram"]["total_gb"]; g = hw["gpus"]
    return {"max_concurrent_heavy_jobs": 1,
            "max_bake_resolution": 2048 if ram >= 15 else 1024 if ram >= 6 else 512,
            "max_triangles": 200000 if ram >= 15 else 80000,
            "timeouts_s": {"blender": 1200, "meshroom": 5400 if not g else 3600, "triposr": 1800 if not g else 300, "hunyuan3d": 1800},
            "meshroom_min_ram_gb": 8, "photogrammetry_max_images": 120 if not g else 400}


if __name__ == "__main__":
    print(json.dumps(probe(), indent=1))
