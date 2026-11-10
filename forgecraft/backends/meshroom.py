"""Meshroom / AliceVision photogrammetry (MPL-2.0), run with meshroom_batch.

Hardware-aware: with an NVIDIA CUDA GPU the full `photogrammetry` pipeline (dense depth
maps) runs; without one, AliceVision's DepthMap node cannot run, so ForgeCraft selects the
`photogrammetryDraft` template (SfM → Draft Meshing from the sparse point cloud →
Texturing), which works on CPU and produces a coarser but real, textured mesh."""
import glob, os, shutil, subprocess, time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _gitcraft3d  # noqa: F401
from gitcraft3d import hardware

# A reconstruction this sparse is not the photographed subject: draft meshing from too few landmarks gives a handful of
# shards (a 36-photo synthetic chest gave 410 faces, 75 after cropping). Real scans are thousands of faces.
MIN_FACES = int(os.environ.get("FORGECRAFT_PHOTOGRAMMETRY_MIN_FACES") or 1000)

IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".JPG", ".JPEG", ".PNG")


def collect(images):
    out = []
    for p in images:
        if os.path.isdir(p): out += sorted(os.path.join(p, f) for f in os.listdir(p) if f.endswith(IMG_EXT))
        elif p.endswith(IMG_EXT): out.append(p)
    return out


def mesh_faces(path):
    """Faces in an OBJ (a polygon line starts with 'f ')."""
    n = 0
    with open(path, errors="ignore") as f:
        for line in f:
            if line.startswith("f "): n += 1
    return n


def sparse_reason(faces, images, cameras, pipeline):
    """Why a reconstruction is refused, and what gives a real one (None when it is dense enough)."""
    if faces >= MIN_FACES: return None
    how = ("CPU draft meshing works from the sparse point cloud only: use 40-60 sharp photos of a strongly textured, matte subject "
           "(varied surface detail, no plain or shiny areas, the subject filling most of each frame), or run on an NVIDIA CUDA GPU "
           "for the dense pipeline") if pipeline == "photogrammetryDraft" else "use more, sharper, overlapping photos of a textured subject"
    return (f"reconstruction too sparse to be the subject: {faces} faces from {images} photos ({cameras if cameras is not None else '?'} cameras placed; "
            f"a usable scan has at least {MIN_FACES}). Nothing was added to the library. {how}.")


def run(images, work, log, timeout=None, pipeline=None, overrides=None):
    st = hardware.meshroom()
    if not st.get("installed"): raise RuntimeError(st.get("reason"))
    imgs = collect(images)
    lim = hardware.limits(hardware.meminfo()["total_gb"], bool(hardware.gpus()[0]))
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
    sfm = glob.glob(os.path.join(cache, "StructureFromMotion", "*", "cameras.sfm"))
    reconstructed = None
    if sfm:
        import json
        try: reconstructed = len(json.load(open(sfm[0])).get("poses", []))
        except Exception: pass
    if r.returncode != 0 or not mesh:
        tail = ""
        try:
            with open(log, errors="ignore") as lf: lf.seek(max(0, os.path.getsize(log) - 400000)); tail = lf.read()
        except OSError: pass
        if "No valid mesh was generated" in tail:   # AliceVision's mesher found no surface in the point cloud: the same cause as a sparse mesh
            why = sparse_reason(0, len(imgs), reconstructed, pipe)
            with open(log, "a") as lf: lf.write(f"\nGITCRAFT: {why}\n")
            raise RuntimeError(why)
        raise RuntimeError(f"meshroom_batch exited {r.returncode} without a mesh; see {log}")
    faces = mesh_faces(mesh[0])
    why = sparse_reason(faces, len(imgs), reconstructed, pipe)
    if why:
        with open(log, "a") as lf: lf.write(f"\nGITCRAFT: {why}\n")
        raise RuntimeError(why)
    return {"mesh": mesh[0], "pipeline": pipe, "images": len(imgs), "cameras_reconstructed": reconstructed, "raw_faces": faces,
            "seconds": round(time.time() - t0, 1), "version": st["version"], "textured": mesh[0].endswith("texturedMesh.obj")}
