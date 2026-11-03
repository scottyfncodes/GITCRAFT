"""AudioCraft: game audio production. Synthesis is GITCRAFT's own deterministic engine
(synth.py); speech is Kokoro-82M (Apache-2.0) in its own venv; editing, loudness and
conversion are FFmpeg. Every output has a waveform preview and is measured after writing."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import synth, midi
from core import STUDIO_HOME
from core.contract import StudioError
from core import media, runners, deps

SR = synth.SR


def _measure(x, sr=SR):
    x = np.asarray(x); m = x.mean(1) if x.ndim == 2 else x
    peak = float(np.abs(x).max()); rms = float(np.sqrt((m ** 2).mean()))
    db = lambda v: round(20 * np.log10(max(v, 1e-9)), 2)
    thr = 10 ** (-50 / 20); nz = np.nonzero(np.abs(m) > thr)[0]
    return {"seconds": round(len(m) / sr, 4), "peak_dbfs": db(peak), "rms_dbfs": db(rms), "clipped_samples": int((np.abs(x) >= 0.9999).sum()),
            "dc_offset": round(float(m.mean()), 5), "lead_silence_s": round(nz[0] / sr, 3) if len(nz) else None,
            "tail_silence_s": round((len(m) - nz[-1]) / sr, 3) if len(nz) else None}


def _seam(x, loop=None):
    """How audible the loop point is: sample jump and spectral distance between the end and start."""
    x = np.asarray(x); m = x.mean(1) if x.ndim == 2 else x
    s, e = loop or (0, len(m))
    jump = float(abs(m[e - 1] - m[s])) if e > s else 1.0
    w = min(2048, (e - s) // 4)
    A = np.abs(np.fft.rfft(m[e - w:e] * np.hanning(w))); B = np.abs(np.fft.rfft(m[s:s + w] * np.hanning(w)))
    spec = float(np.abs(np.log1p(A) - np.log1p(B)).mean())
    # the loop step must look like an ordinary step of the audio either side of it
    local = float(max(np.abs(np.diff(m[s:s + 256])).max(), np.abs(np.diff(m[e - 256:e])).max()) * 1.25 + 1e-4)
    return {"jump": round(jump, 5), "local_max_step": round(local, 5), "spectral_distance": round(spec, 4),
            "seamless": bool(jump <= max(0.02, local) and spec < 1.0)}


def _write(ctx, stem, x, formats, role, loop=None, extra=None):
    wav = media.write_wav(ctx.path(stem + ".wav"), x, SR, loop=loop)
    outs = [dict({"path": wav, "role": role, "format": "wav"}, **(extra or {}))]
    for f in formats:
        if f == "wav": continue
        ctx.used("ffmpeg"); outs.append({"path": media.encode(wav, f, loop=loop), "role": role, "format": f})
    outs.append({"path": media.waveform_png(x, ctx.path(stem + "_waveform.png"), loop=loop, sr=SR), "role": "preview", "format": "png"})
    return outs


# ---------------------------------------------------------------- actions
def sfx(ctx, p):
    ctx.used("studio_synth"); outs, meas = [], []
    for v in range(p["variations"]):
        x = synth.sfx(p["preset"], seed=ctx.seed * 1000 + v, variation=p["variation"])
        stem = f"{p.get('name') or p['preset']}_{v + 1:02d}" if p["variations"] > 1 else (p.get("name") or p["preset"])
        outs += _write(ctx, stem, x, p["formats"], "sfx"); meas.append(dict(_measure(x), file=stem + ".wav"))
    ctx.stage("synthesised", files=len(outs))
    checks = [{"name": f"{m['file']} is audible and unclipped", "ok": m["peak_dbfs"] > -12 and m["clipped_samples"] == 0 and m["seconds"] > 0.02,
               "detail": f"peak {m['peak_dbfs']} dBFS, {m['seconds']} s"} for m in meas]
    return {"outputs": outs, "checks": checks, "measurements": meas}


def ambience(ctx, p):
    ctx.used("studio_synth")
    x = synth.ambience(p["kind"], p["seconds"], ctx.seed, stereo=p["stereo"]); ctx.stage("synthesised")
    loop = (0, len(x)); stem = p.get("name") or f"ambience_{p['kind']}"
    outs = _write(ctx, stem, x, p["formats"], "ambience", loop=loop)
    seam = _seam(x)
    return {"outputs": outs, "measurements": _measure(x), "seam": seam, "loop": {"start": 0, "end": len(x), "sample_rate": SR},
            "checks": [{"name": "loops seamlessly", "ok": seam["seamless"], "detail": seam},
                       {"name": "duration", "ok": abs(len(x) / SR - p["seconds"]) < 0.01}]}


def music(ctx, p):
    ctx.used("studio_synth")
    song = synth.music(p["mood"], p["key"], p["bars"], p.get("tempo"), ctx.seed, p.get("layers"))
    ctx.stage("composed", tempo=song["tempo"], bars=song["bars"])
    stem = p.get("name") or f"music_{p['mood']}"; L = song["loop_samples"]; outs = []
    for k, x in song["stems"].items():
        wav = media.write_wav(ctx.path(f"stems/{stem}_{k}.wav"), x, SR, loop=(0, L)); outs.append({"path": wav, "role": f"stem:{k}", "format": "wav"})
    outs += _write(ctx, stem, song["mix"], p["formats"], "music", loop=(0, L))
    mid = midi.write(ctx.path(stem + ".mid"), song["notes"], song["tempo"]); outs.append({"path": mid, "role": "source", "format": "midi"})
    # adaptive layering: which stems play at which intensity (crossfade gains in the game)
    levels = {"low": [k for k in ("pad", "bass") if k in song["stems"]], "mid": [k for k in ("pad", "bass", "drums", "arp") if k in song["stems"]],
              "high": list(song["stems"])}
    manifest = {"title": stem, "tempo": song["tempo"], "bars": song["bars"], "key": song["key"], "scale": song["scale"], "chords_degrees": song["chords"],
                "sample_rate": SR, "loop": {"start": 0, "end": L, "seconds": round(L / SR, 4)}, "stems": {k: f"stems/{stem}_{k}.wav" for k in song["stems"]},
                "intensity_levels": levels, "mix": f"{stem}.wav", "midi": f"{stem}.mid",
                "usage": "Start every stem together on one AudioContext clock (loop=true, loopEnd=loop.seconds); fade stem gains to the level's set."}
    mp = ctx.path(stem + ".layers.json"); json.dump(manifest, open(mp, "w"), indent=1); outs.append({"path": mp, "role": "manifest", "format": "json"})
    seam = _seam(song["mix"]); lens = {len(x) for x in song["stems"].values()}
    ctx.stage("rendered", stems=len(song["stems"]))
    return {"outputs": outs, "measurements": _measure(song["mix"]), "seam": seam, "adaptive": manifest,
            "checks": [{"name": "loops seamlessly", "ok": seam["seamless"], "detail": seam},
                       {"name": "stems are sample-aligned", "ok": lens == {L}, "detail": sorted(lens)},
                       {"name": "length is whole bars", "ok": abs(L / SR - song["bars"] * 4 * 60 / song["tempo"]) < 1e-3}]}


def voice(ctx, p):
    d = deps.check_one("kokoro", MANIFEST["dependencies"]["kokoro"])
    ctx.used("kokoro", "ffmpeg")
    m = os.path.join(STUDIO_HOME, "models", "kokoro")
    lines = []
    for i, ln in enumerate(p["lines"]):
        lid = ln.get("id") or f"line_{i + 1:02d}"
        voice_id = ln.get("voice") or p["cast"].get(ln.get("character", ""), p["voice"])
        lines.append({"id": lid, "text": ln["text"], "voice": voice_id, "speed": ln.get("speed", p["speed"]), "lang": ln.get("lang", p["lang"]),
                      "character": ln.get("character"), "out": ctx.path(f"raw/{lid}.wav")})
    r = runners.venv(d["python"], os.path.join(HERE, "kokoro_tts.py"),
                     {"model": os.path.join(m, "kokoro-v1.0.int8.onnx"), "voices": os.path.join(m, "voices-v1.0.bin"), "lines": lines}, timeout=900)
    ctx.stage("synthesised", lines=len(r["lines"]))
    outs, script, checks = [], [], []
    for ln, got in zip(lines, r["lines"]):
        x = media.read_audio(got["out"], sr=SR, mono=True)[:, 0]
        nz = np.nonzero(np.abs(x) > 10 ** (-45 / 20))[0]
        if len(nz): x = x[max(0, nz[0] - int(0.03 * SR)):nz[-1] + int(0.08 * SR)]
        x = synth.normalize(x, -1.0)
        outs += _write(ctx, ln["id"], x, p["formats"], "dialogue")
        sec = len(x) / SR; cps = len(ln["text"]) / max(sec, 1e-3)
        script.append({"id": ln["id"], "character": ln["character"], "voice": ln["voice"], "text": ln["text"], "file": ln["id"] + ".wav", "seconds": round(sec, 3)})
        checks.append({"name": f"{ln['id']}: speech present and plausibly paced", "ok": sec > 0.3 and 4 < cps < 40, "detail": f"{sec:.2f} s, {cps:.1f} chars/s"})
        os.remove(got["out"])
    try: os.rmdir(ctx.path("raw"))
    except OSError: pass
    sp = ctx.path((p.get("name") or "dialogue") + ".dialogue.json"); json.dump({"lines": script, "engine": "Kokoro-82M v1.0 (kokoro-onnx, int8)"}, open(sp, "w"), indent=1)
    outs.append({"path": sp, "role": "manifest", "format": "json"})
    return {"outputs": outs, "checks": checks, "script": script}


def process(ctx, p):
    src = ctx.need(p["input"]); ctx.used("ffmpeg")
    x = media.read_audio(src, sr=p["sample_rate"], mono=p["mono"])
    m = x.mean(1)
    if p["trim_silence"]:
        thr = 10 ** (p["silence_db"] / 20); nz = np.nonzero(np.abs(m) > thr)[0]
        if len(nz): x = x[max(0, nz[0] - int(0.01 * p["sample_rate"])):nz[-1] + int(0.02 * p["sample_rate"])]
    if p.get("start") is not None or p.get("end") is not None:
        a = int((p.get("start") or 0) * p["sample_rate"]); b = int(p["end"] * p["sample_rate"]) if p.get("end") else len(x); x = x[a:b]
    if p["fade_in"]: k = min(len(x), int(p["fade_in"] * p["sample_rate"])); x[:k] *= np.linspace(0, 1, k)[:, None]
    if p["fade_out"]: k = min(len(x), int(p["fade_out"] * p["sample_rate"])); x[-k:] *= np.linspace(1, 0, k)[:, None]
    x = x - x.mean(0)
    stem = p.get("name") or os.path.splitext(os.path.basename(src))[0] + "_processed"
    tmp = media.write_wav(ctx.path(stem + ".pre.wav"), x, p["sample_rate"])
    if p.get("lufs") is not None:   # two-pass EBU R128 loudness normalisation (FFmpeg loudnorm)
        meas = media.loudness(tmp)
        import subprocess
        af = (f"loudnorm=I={p['lufs']}:TP={p['true_peak']}:LRA=11:measured_I={meas['lufs']}:measured_TP={meas['true_peak_db']}"
              f":measured_LRA={meas['lra']}:linear=true")
        out = ctx.path(stem + ".wav")
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af", af, "-ar", str(p["sample_rate"]), "-c:a", "pcm_s16le", out], capture_output=True, text=True)
        if r.returncode: raise StudioError("loudnorm failed: " + r.stderr[-300:])
        x = media.read_audio(out, sr=p["sample_rate"], mono=p["mono"])
    elif p.get("peak_db") is not None:
        x = synth.normalize(x, p["peak_db"])
    os.remove(tmp)
    outs = _write(ctx, stem, x if not p["mono"] else x[:, 0], p["formats"], "processed")
    after = media.loudness(outs[0]["path"])
    checks = [{"name": "no clipping", "ok": _measure(x)["clipped_samples"] == 0}]
    if p.get("lufs") is not None: checks.append({"name": f"loudness {p['lufs']} LUFS ±1", "ok": abs(after["lufs"] - p["lufs"]) <= 1.0, "detail": after})
    return {"outputs": outs, "measurements": dict(_measure(x), **after), "checks": checks}


def convert(ctx, p):
    src = ctx.need(p["input"]); ctx.used("ffmpeg"); outs = []
    stem = p.get("name") or os.path.splitext(os.path.basename(src))[0]
    x = media.read_audio(src, sr=p["sample_rate"])
    from core.validate import read_smpl_loops
    lp = read_smpl_loops(src) if src.lower().endswith(".wav") else []
    loop = (lp[0]["start"], lp[0]["end"] + 1) if lp else None
    wav = media.write_wav(ctx.path(stem + ".wav"), x, p["sample_rate"], loop=loop)
    for f in p["formats"]:
        outs.append({"path": wav if f == "wav" else media.encode(wav, f, loop=loop), "format": f, "role": "converted"})
    if "wav" not in p["formats"]: os.remove(wav)
    checks = []
    for o in outs:
        from core.validate import check
        v = check(o["path"]); checks.append({"name": f"{os.path.basename(o['path'])} duration matches", "ok": v["ok"] and abs(v["seconds"] - len(x) / p["sample_rate"]) < 0.08,
                                              "detail": v.get("seconds")})
    return {"outputs": outs, "checks": checks}


def find_loop(m, sr, min_len, window=0.5, starts=24):
    """Best (start, end) pair: for candidate starts spread over the first 40% of the audio, the
    loop end whose `window`-second neighbourhood best matches the start's (normalised
    cross-correlation over the whole candidate region, FFT), snapped to zero crossings.
    Intros that never recur are skipped because no end matches them. Returns (start, end, ncc)."""
    W = int(window * sr); n = len(m)
    zc = np.nonzero((m[:-1] <= 0) & (m[1:] > 0))[0]
    snap = lambda i: int(zc[np.argmin(np.abs(zc - i))]) if len(zc) else int(i)
    nz = np.nonzero(np.abs(m) > 10 ** (-40 / 20))[0]; first = int(nz[0]) if len(nz) else 0
    last_start = max(first + 1, int(0.4 * n)); best = (-2, 0, 0)
    for s in sorted({snap(v) for v in np.linspace(first, last_start, starts)}):
        lo = s + int(min_len * sr); hi = n - W
        if hi <= lo: continue
        ref = m[s:s + W]; eref = float((ref ** 2).sum())
        if eref < 1e-6: continue
        region = m[lo:hi + W]; N = 1 << int(np.ceil(np.log2(len(region) + W)))
        corr = np.fft.irfft(np.fft.rfft(region, N) * np.conj(np.fft.rfft(ref, N)), N)[:len(region) - W + 1]
        c2 = np.concatenate([[0], np.cumsum(region ** 2)]); e2 = c2[W:W + len(corr)] - c2[:len(corr)]
        ncc = corr / (np.sqrt(np.maximum(e2, 1e-12) * eref))
        k = int(np.argmax(ncc))
        if ncc[k] > best[0]: best = (float(ncc[k]), s, lo + k)
    if best[0] == -2: raise StudioError("audio too short for the requested minimum loop length", hint="lower min_seconds")
    score, s, e = best
    return s, snap(e), score


def loop(ctx, p):
    src = ctx.need(p["input"]); ctx.used("studio_synth", "ffmpeg")
    x = media.read_audio(src, sr=SR); m = x.mean(1)
    s, e, score = find_loop(m, SR, p["min_seconds"])
    ctx.stage("loop found", start=s, end=e, score=round(score, 3))
    xf = int(p["crossfade"] * SR)
    body = x[s:e].copy()
    # seamless file: blend the material just past the end into the head, so end → start is continuous
    k = min(xf, len(x) - e, len(body) // 4)
    if k > 0:
        fade = np.linspace(0, 1, k)[:, None]
        body[:k] = body[:k] * fade + x[e:e + k] * (1 - fade)
    stem = p.get("name") or os.path.splitext(os.path.basename(src))[0] + "_loop"
    outs = _write(ctx, stem, body, p["formats"], "loop", loop=(0, len(body)))
    # the original with loop markers (intro kept): engines that read smpl / LOOPSTART play intro then loop
    marked = _write(ctx, stem + "_marked", x[:e], ["ogg"] if "ogg" in p["formats"] else [], "loop_marked", loop=(s, e))
    seam = _seam(body)
    info = {"start": s, "end": e, "seconds": round((e - s) / SR, 4), "correlation": round(score, 4), "sample_rate": SR, "crossfade_samples": k}
    jp = ctx.path(stem + ".loop.json"); json.dump(info, open(jp, "w"), indent=1)
    return {"outputs": outs + marked + [{"path": jp, "role": "manifest", "format": "json"}], "loop": info, "seam": seam,
            "checks": [{"name": "loops seamlessly", "ok": seam["seamless"], "detail": seam},
                       {"name": "loop match quality (correlation ≥ 0.5)", "ok": score >= 0.5, "detail": round(score, 3)}]}


def layer(ctx, p):
    ctx.used("studio_synth", "ffmpeg"); tracks = []
    for t in p["stems"]:
        x = media.read_audio(ctx.need(t["path"]), sr=SR); tracks.append((t, x))
    L = max(int(t.get("offset", 0) * SR) + len(x) for t, x in tracks) if p.get("length") is None else int(p["length"] * SR)
    mix = np.zeros((L, 2))
    for t, x in tracks:
        o = int(t.get("offset", 0) * SR); g = 10 ** (t.get("gain_db", 0) / 20)
        if t.get("loop"):
            reps = int(np.ceil((L - o) / len(x))); x = np.tile(x, (reps, 1))
        k = min(len(x), L - o); mix[o:o + k] += x[:k] * g
    clip = float(np.abs(mix).max())
    if clip > 0.98: mix *= 0.98 / clip; ctx.note(f"mix peaked at {clip:.2f}; scaled down to avoid clipping")
    stem = p.get("name") or "mixdown"
    outs = _write(ctx, stem, mix, p["formats"], "mix")
    man = {"stems": [{"path": t["path"], "gain_db": t.get("gain_db", 0), "offset": t.get("offset", 0), "loop": bool(t.get("loop"))} for t, _ in tracks],
           "seconds": round(L / SR, 3), "mix": stem + ".wav"}
    mp = ctx.path(stem + ".layers.json"); json.dump(man, open(mp, "w"), indent=1)
    return {"outputs": outs + [{"path": mp, "role": "manifest", "format": "json"}], "measurements": _measure(mix),
            "checks": [{"name": "no clipping", "ok": _measure(mix)["clipped_samples"] == 0}]}


def analyze(ctx, p):
    src = ctx.need(p["input"]); ctx.used("ffmpeg")
    x = media.read_audio(src, sr=SR)
    from core.validate import read_smpl_loops
    loops = read_smpl_loops(src) if src.lower().endswith(".wav") else []
    res = dict(_measure(x), **media.loudness(src))
    if loops: res["loop"] = loops[0]; res["seam"] = _seam(x, (loops[0]["start"], loops[0]["end"] + 1))
    stem = os.path.splitext(os.path.basename(src))[0]
    rp = ctx.path(stem + ".analysis.json"); json.dump(res, open(rp, "w"), indent=1)
    return {"outputs": [{"path": media.waveform_png(x, ctx.path(stem + "_waveform.png")), "role": "preview", "format": "png"},
                        {"path": rp, "role": "report", "format": "json"}], "analysis": res}


MANIFEST = json.load(open(os.path.join(HERE, "manifest.json")))
ACTIONS = {"sfx": sfx, "ambience": ambience, "music": music, "voice": voice, "process": process, "convert": convert,
           "loop": loop, "layer": layer, "analyze": analyze}
