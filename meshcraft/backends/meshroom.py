"""Meshroom / AliceVision photogrammetry (MPL-2.0), run with meshroom_batch.

Hardware-aware: with an NVIDIA CUDA GPU the full `photogrammetry` pipeline (dense depth
maps) runs; without one, AliceVision's DepthMap node cannot run, so MeshCraft selects the
`photogrammetryDraft` template (SfM → Draft Meshing from the sparse point cloud →
Texturing), which works on CPU and produces a coarser but real, textured mesh."""
import glob, os, shutil, subprocess, time
import hardware

IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".JPG", ".JPEG", ".PNG")


def collect(images):
    out = []
    for p in images:
        if os.path.isdir(p): out += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(IMG_EXT))
        elif p.endswith(IMG_EXT): out.append(p)
    return out


def run(images, work, log, timeout=None, pipeline=None, overrides=None):
    st = hardware.meshroom()
    if not st.get("installed"): raise RuntimeError(st.get("reason"))
    imgs = collect(images)
    lim = hardware.limits({"ram": hardware.meminfo(), "gpus": hardware.gpus()})
    if len(imgs) < 3: raise RuntimeError(f"photogrammetry needs at least 3 overlapping images (got {len(imgs)}); 20–60 is typical")
    if len(imgs) > lim["photogrammetry_max_images"]:
        raise RuntimeError(f"{len(imgs)} images exceeds this machine's job limit of {lim['photogrammetry_max_images']}")
    src = os.path.join(work, "photos"); os.makedirs(src, exist_ok=True)
    for p in imgs:
        d = os.path.join(src, os.path.basename(p))
        if not os.path.exists(d): shutil.copy2(p, d)
    pipe = pipeline or st["pipeline"]
    out, cache = os.path.join(work, "meshroom_out"), os.path.join(work, "meshroom_cache")
    cmd = [st["batch"], "-i", src, "-p", pipe, "-o", out, "--cache", cache, "-v", "info"]
    if overrides: cmd += ["--paramOverrides", *overrides]   # e.g. CameraInit:defaultFieldOfView=54.4 for photos without EXIF
    env = dict(os.environ, TMPDIR=os.path.join(work, "tmp"), ALICEVISION_NB_THREADS=str(os.cpu_count() or 2))
    os.makedirs(env["TMPDIR"], exist_ok=True)
    t0 = time.time()
    with open(log, "a") as lf:
        lf.write("$ " + " ".join(cmd) + "\n"); lf.flush()
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, timeout=timeout or lim["timeouts_s"]["meshroom"])
    mesh = (glob.glob(os.path.join(out, "texturedMesh.obj")) or glob.glob(os.path.join(cache, "Texturing", "*", "texturedMesh.obj"))
            or glob.glob(os.path.join(cache, "Meshing", "*", "mesh.obj")))
    if r.returncode != 0 or not mesh:
        raise RuntimeError(f"meshroom_batch exited {r.returncode} without a mesh; see {log}")
    sfm = glob.glob(os.path.join(cache, "StructureFromMotion", "*", "cameras.sfm"))
    reconstructed = None
    if sfm:
        import json
        try: reconstructed = len(json.load(open(sfm[0])).get("poses", []))
        except Exception: pass
    return {"mesh": mesh[0], "pipeline": pipe, "images": len(imgs), "cameras_reconstructed": reconstructed,
            "seconds": round(time.time() - t0, 1), "version": st["version"], "textured": mesh[0].endswith("texturedMesh.obj")}
