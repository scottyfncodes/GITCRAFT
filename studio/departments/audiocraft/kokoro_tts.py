"""Runs in the isolated voice venv (~/.gitcraft/studio/voice-venv): Kokoro-82M (Apache-2.0)
through kokoro-onnx (MIT) on CPU. Request: {model, voices, lines: [{id, text, voice, speed, lang, out}]}."""
import json, sys
req = json.load(open(sys.argv[-1])); res = {"lines": []}
try:
    from kokoro_onnx import Kokoro
    import soundfile as sf
    k = Kokoro(req["model"], req["voices"]); available = set(k.get_voices())
    for ln in req["lines"]:
        if ln["voice"] not in available and "+" not in ln["voice"]:
            raise ValueError(f"unknown voice {ln['voice']}; available: {', '.join(sorted(available))}")
        voice = ln["voice"]
        if "+" in voice:   # blend two voices: "af_bella+am_adam" (a new character timbre)
            a, b = voice.split("+"); voice = (k.get_voice_style(a) + k.get_voice_style(b)) / 2
        s, sr = k.create(ln["text"], voice=voice, speed=float(ln.get("speed", 1.0)), lang=ln.get("lang", "en-us"))
        sf.write(ln["out"], s, sr, subtype="PCM_16")
        res["lines"].append({"id": ln["id"], "out": ln["out"], "seconds": round(len(s) / sr, 3), "sample_rate": sr})
    res["voices"] = sorted(available)
except Exception as e:
    import traceback; traceback.print_exc(); res = {"error": f"{type(e).__name__}: {e}"}
json.dump(res, open(req["_result"], "w"))
