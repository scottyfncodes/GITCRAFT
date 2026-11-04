"""Runs in ACE-Step 1.5's own venv (~/.gitcraft/studio/ace-step/.venv, MIT): text → music with the DiT only
(no 5Hz LM: `thinking` off), fully offline from the checkpoints the installer downloaded.
Request: {root, model, caption, lyrics, duration, bpm, keyscale, seed, steps, device, offload, out_dir}."""
import json, os, sys
req = json.load(open(sys.argv[-1])); res = {}
try:
    os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("ACESTEP_INIT_LLM", "false"); os.environ.setdefault("HF_HOME", os.path.join(req["root"], "hf-cache"))
    os.chdir(req["root"])   # ACE-Step finds ./checkpoints from the working directory
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationParams, GenerationConfig, generate_music
    dit = AceStepHandler()
    msg, ok = dit.initialize_service(project_root=req["root"], config_path=req["model"], device=req.get("device", "auto"),
                                     offload_to_cpu=bool(req.get("offload")))
    if not ok: raise RuntimeError(f"ACE-Step could not initialise: {msg}")
    lyrics = req.get("lyrics") or ""
    params = GenerationParams(caption=req["caption"], lyrics=lyrics, instrumental=not lyrics, bpm=req.get("bpm"), keyscale=req.get("keyscale") or "",
                              duration=float(req["duration"]), seed=int(req["seed"]), inference_steps=int(req["steps"]), thinking=False,
                              use_cot_metas=False, use_cot_caption=False, use_cot_language=False)
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(req["seed"])], audio_format="wav")
    r = generate_music(dit, None, params, config, save_dir=req["out_dir"])
    if not r.success: raise RuntimeError(f"ACE-Step generation failed: {r.error or r.status_message}")
    res = {"audios": [{"path": a.get("path"), "seed": (a.get("params") or {}).get("seed")} for a in r.audios], "status": r.status_message,
           "device": str(getattr(dit, "device", req.get("device")))}
except Exception as e:
    import traceback; traceback.print_exc(); res = {"error": f"{type(e).__name__}: {e}"}
json.dump(res, open(req["_result"], "w"), default=str)
