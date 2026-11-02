"""Hunyuan3D-2 text/image → textured mesh (Tencent, Tencent Hunyuan 3D 2.0 Community License).

Two execution modes, chosen by hardware.hunyuan3d():
  * local: the `hy3dgen` package from github.com/Tencent-Hunyuan/Hunyuan3D-2 in the AI venv,
    on an NVIDIA GPU (shape ≥6 GB VRAM with 2mini/2.0; texture painting ≥16 GB). Weights
    download from Hugging Face (tencent/Hunyuan3D-2, tencent/Hunyuan3D-2mini).
  * remote: the public Hugging Face Space (default tencent/Hunyuan3D-2) through gradio_client.
    Free ZeroGPU compute with quotas; needs network (GITCRAFT_ALLOW_NET=1) and optionally
    HF_TOKEN. The Space's endpoint signature is discovered at call time.
Licence gate: the Community License excludes the EU, UK and South Korea and needs a separate
licence above 1M MAU, so ForgeCraft refuses to run it until FORGECRAFT_HUNYUAN_LICENSE=accepted.
Tencent Cloud's paid Hunyuan 3D API is deliberately not wired in (no surprise costs)."""
import json, os, subprocess, time
import hardware

LOCAL_SCRIPT = r'''
import sys, json, torch
from PIL import Image
args = json.loads(sys.argv[1])
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.rembg import BackgroundRemover
model = args.get("model", "tencent/Hunyuan3D-2mini"); sub = args.get("subfolder", "hunyuan3d-dit-v2-mini")
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(model, subfolder=sub)
if args.get("image"):
    img = Image.open(args["image"]).convert("RGBA")
    if img.mode == "RGB" or args.get("rembg", True): img = BackgroundRemover()(img)
else:
    from hy3dgen.text2image import HunyuanDiTPipeline
    img = HunyuanDiTPipeline("Tencent-Hunyuan/HunyuanDiT-v1.1-Diffusers-Distilled")(args["prompt"])
    img = BackgroundRemover()(img)
mesh = pipe(image=img, num_inference_steps=args.get("steps", 30), octree_resolution=args.get("octree", 256),
            generator=torch.manual_seed(args.get("seed", 1234)))[0]
if args.get("texture") and torch.cuda.get_device_properties(0).total_memory > 15 * 2**30:
    from hy3dgen.texgen import Hunyuan3DPaintPipeline
    mesh = Hunyuan3DPaintPipeline.from_pretrained("tencent/Hunyuan3D-2")(mesh, image=img)
mesh.export(args["out"])
print(json.dumps({"out": args["out"]}))
'''

REMOTE_SCRIPT = r'''
import sys, json, shutil
from gradio_client import Client, handle_file
a = json.loads(sys.argv[1])
c = Client(a["space"], hf_token=a.get("token") or None)
api = c.view_api(return_format="dict", print_info=False)
eps = api.get("named_endpoints", {})
name = next((n for n in ("/generation_all", "/shape_generation") if n in eps), None)
if not name: raise SystemExit("Space exposes no known generation endpoint: " + ", ".join(eps))
kw = {}
for p in eps[name]["parameters"]:
    k = p["parameter_name"]
    if k in ("caption",) and a.get("prompt"): kw[k] = a["prompt"]
    elif k == "image" and a.get("image"): kw[k] = handle_file(a["image"])
    elif k == "seed": kw[k] = a.get("seed", 1234)
    elif k == "randomize_seed": kw[k] = False
res = c.predict(api_name=name, **kw)
files = [r for r in (res if isinstance(res, (list, tuple)) else [res]) if isinstance(r, (str, dict))]
paths = [f["value"] if isinstance(f, dict) and "value" in f else f for f in files]
mesh = next((p for p in paths if isinstance(p, str) and p.endswith((".glb", ".obj", ".ply"))), None)
if not mesh: raise SystemExit("no mesh in Space response: " + json.dumps(res, default=str)[:400])
shutil.copy(mesh, a["out"]); print(json.dumps({"out": a["out"], "endpoint": name}))
'''


def run(work, log, prompt=None, image=None, seed=1234, texture=True, timeout=None):
    st = hardware.hunyuan3d()
    if not st["available"]: raise RuntimeError("Hunyuan3D unavailable: " + st["reason"])
    py = os.path.join(hardware.MC_HOME, "ai-venv", "bin", "python")
    out = os.path.join(work, "hunyuan3d.glb")
    mode = "local" if st["local"]["available"] else "remote"
    args = {"prompt": prompt, "image": image, "seed": seed, "out": out, "texture": texture and st["local"]["texture_ok"]}
    if mode == "remote": args.update(space=st["remote"]["space"], token=os.environ.get("HF_TOKEN"))
    t0 = time.time()
    with open(log, "a") as lf:
        lf.write(f"$ hunyuan3d {mode} {json.dumps({k: v for k, v in args.items() if k != 'token'})}\n"); lf.flush()
        r = subprocess.run([py, "-c", LOCAL_SCRIPT if mode == "local" else REMOTE_SCRIPT, json.dumps(args)], stdout=lf, stderr=subprocess.STDOUT,
                           timeout=timeout or 1800)
    if r.returncode != 0 or not os.path.exists(out): raise RuntimeError(f"Hunyuan3D ({mode}) failed with exit {r.returncode}; see {log}")
    return {"mesh": out, "mode": mode, "seconds": round(time.time() - t0, 1),
            "license": "Tencent Hunyuan 3D 2.0 Community License: label outputs as AI-generated; not licensed in EU/UK/South Korea"}
