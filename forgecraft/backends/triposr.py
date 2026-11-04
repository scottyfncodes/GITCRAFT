"""TripoSR single-image → mesh (VAST-AI-Research/TripoSR, code and weights MIT).

Runs the upstream `run.py` from a checkout at $FORGECRAFT_HOME/TripoSR in the AI venv
($FORGECRAFT_HOME/ai-venv). Weights come from the Hugging Face model `stabilityai/TripoSR`
(about 1.7 GB, cached under ~/.cache/huggingface) or from a local directory in
$FORGECRAFT_TRIPOSR_WEIGHTS. CPU works (minutes per image); a CUDA GPU with ~6 GB VRAM
takes about a second. Output is a vertex-coloured mesh that ForgeCraft then cleans,
UV-unwraps and bakes into texture maps in Blender."""
import glob, os, subprocess, time
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _gitcraft3d  # noqa: F401
from gitcraft3d import hardware


def run(image, work, log, resolution=256, timeout=None):
    st = hardware.triposr()
    if not st["available"]: raise RuntimeError("TripoSR unavailable: " + st["reason"])
    code = os.path.join(hardware.FORGE_HOME, "TripoSR"); py = os.path.join(hardware.FORGE_HOME, "ai-venv", "bin", "python")
    out = os.path.join(work, "triposr"); os.makedirs(out, exist_ok=True)
    cmd = [py, os.path.join(code, "run.py"), image, "--output-dir", out, "--model-save-format", "obj",
           "--mc-resolution", str(resolution), "--device", "cuda:0" if st["device"] == "cuda" else "cpu"]
    if st.get("weights_source") and os.path.isdir(st["weights_source"]): cmd += ["--pretrained-model-name-or-path", st["weights_source"]]
    # the weights and rembg's background-removal model were fetched at install time (install-3d.sh ai weights):
    # read them from ForgeCraft's caches, offline, so the sandboxed run never needs the network
    env = dict(os.environ)
    env.setdefault("HF_HOME", os.path.join(hardware.FORGE_HOME, "hf-cache"))
    env.setdefault("U2NET_HOME", os.path.join(hardware.FORGE_HOME, "u2net"))
    if hardware.hf_cached("stabilityai/TripoSR") and hardware.hf_cached("facebook/dino-vitb16"): env.setdefault("HF_HUB_OFFLINE", "1")
    t0 = time.time()
    with open(log, "a") as lf:
        lf.write("$ " + " ".join(cmd) + "\n"); lf.flush()
        r = subprocess.run(cmd, cwd=code, env=env, stdout=lf, stderr=subprocess.STDOUT,
                           timeout=timeout or hardware.limits(hardware.meminfo()["total_gb"], bool(hardware.gpus()[0]))["timeouts_s"]["triposr"])
    mesh = glob.glob(os.path.join(out, "*", "mesh.obj"))
    if r.returncode != 0 or not mesh: raise RuntimeError(f"TripoSR exited {r.returncode} without a mesh; see {log}")
    # TripoSR writes Z-up with the photographed side facing +X; the department's convention (and the OBJ importer's)
    # is Y-up, facing +Z. (x, y, z) -> (y, z, x) does both (a rotation, so normals and winding stay valid); vertex
    # colours are kept.
    fixed = os.path.join(os.path.dirname(mesh[0]), "mesh_yup.obj")
    conv = subprocess.run([py, "-I", "-c", "import sys, trimesh; m = trimesh.load(sys.argv[1], force='mesh', process=False); "
                           "m.vertices = m.vertices[:, [1, 2, 0]]; m.export(sys.argv[2])", mesh[0], fixed], capture_output=True, text=True)
    if conv.returncode != 0 or not os.path.exists(fixed): raise RuntimeError(f"TripoSR axis conversion failed: {conv.stderr[-400:]}")
    mesh = [fixed]
    return {"mesh": mesh[0], "device": st["device"], "seconds": round(time.time() - t0, 1), "mc_resolution": resolution}
