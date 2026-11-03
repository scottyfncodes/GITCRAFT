"""AudioCraft's synthesis engine: deterministic, seedable, numpy only (GITCRAFT's own code).

  sfx(preset, seed)        sfxr-style game sound effects (oscillator + pitch/duty sweeps +
                           envelope + filters), with seeded variations
  ambience(kind, seconds)  procedural soundscapes (spectrally shaped noise beds + scattered events),
                           rendered seamless: the tail is folded onto the head, so the file loops exactly
  music(...)               a short loopable piece as separate stems (drums, bass, pad, lead, arp) from a
                           mood's progression and scale, plus the note list (written as MIDI by midi.py)
"""
import numpy as np

SR = 44100


# ---------------------------------------------------------------- building blocks
def osc(wave, freq, sr=SR, duty=0.5, rng=None):
    """freq: per-sample array (Hz). duty may be an array. Returns samples in [-1, 1]."""
    ph = np.cumsum(freq / sr)
    frac = ph % 1.0
    if wave == "sine": return np.sin(2 * np.pi * ph)
    if wave == "square": return np.where(frac < duty, 1.0, -1.0)
    if wave == "saw": return 2 * frac - 1
    if wave == "triangle": return 1 - 4 * np.abs(frac - 0.5)
    if wave == "noise":   # sfxr-style: a new random value each oscillator cycle (pitched noise)
        rng = rng or np.random.default_rng(0)
        cyc = np.floor(ph * 8).astype(np.int64); vals = rng.uniform(-1, 1, int(cyc.max()) + 2)
        return vals[cyc - cyc.min()]
    raise ValueError(wave)


def onepole_lp(x, cutoff, sr=SR):
    """Time-varying one-pole low-pass. cutoff: Hz scalar or array."""
    c = np.broadcast_to(np.asarray(cutoff, float), x.shape)
    a = 1 - np.exp(-2 * np.pi * np.clip(c, 10, sr / 2.2) / sr)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)): s += a[i] * (x[i] - s); y[i] = s
    return y


def hp(x, cutoff, sr=SR):
    return x - onepole_lp(x, cutoff, sr)


def lp_static(x, cutoff, sr=SR):
    """Fixed low-pass for long signals (FFT; the one-pole loop is for short, swept SFX)."""
    return spectral(x, lambda f: 1 / np.sqrt(1 + (f / cutoff) ** 2), sr)


def spectral(x, fn, sr=SR):
    """Shape a signal's spectrum with fn(freqs) → gain (stationary filtering via FFT)."""
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / sr); return np.fft.irfft(X * fn(f), len(x))


def colored_noise(n, rng, tilt=-1.0, lo=20, hi=20000, sr=SR):
    """tilt: 0 white, -1 pink, -2 brown (power slope in dB/oct ~ 3*tilt)."""
    x = rng.standard_normal(n)
    y = spectral(x, lambda f: np.where((f > lo) & (f < hi), np.maximum(f, 1) ** (tilt / 2), 0), sr)
    return y / (np.abs(y).max() + 1e-9)


def band_noise(n, rng, center, q=1.0, sr=SR):
    x = rng.standard_normal(n)
    y = spectral(x, lambda f: np.exp(-0.5 * (np.log2(np.maximum(f, 1) / center) / (0.5 / q)) ** 2), sr)
    return y / (np.abs(y).max() + 1e-9)


def env_adsr(n, attack, decay, sustain_level, release, sr=SR):
    a, d, r = int(attack * sr), int(decay * sr), int(release * sr)
    s = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, a, endpoint=False), np.linspace(1, sustain_level, d, endpoint=False),
                        np.full(s, sustain_level), np.linspace(sustain_level, 0, r)])
    return np.pad(e, (0, max(0, n - len(e))))[:n]


def smooth_random(n, rng, rate_hz, sr=SR, lo=0.0, hi=1.0):
    """Slowly wandering control signal (cosine-interpolated random points)."""
    k = max(2, int(n / sr * rate_hz) + 2); pts = rng.uniform(lo, hi, k)
    t = np.linspace(0, k - 1, n); i = np.floor(t).astype(int); f = t - i
    f = (1 - np.cos(np.pi * f)) / 2; i = np.minimum(i, k - 2)
    return pts[i] * (1 - f) + pts[i + 1] * f


def reverb(x, seconds=1.2, mix=0.25, sr=SR, rng=None, predelay=0.01):
    rng = rng or np.random.default_rng(1)
    n = int(seconds * sr); t = np.arange(n) / sr
    ir = rng.standard_normal(n) * np.exp(-6.9 * t / seconds); ir[: int(predelay * sr)] = 0
    ir = spectral(ir, lambda f: 1 / (1 + (f / 6000) ** 2)); ir /= np.sqrt((ir ** 2).sum()) + 1e-9
    L = len(x) + n; N = 1 << int(np.ceil(np.log2(L)))
    wet = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]
    return (1 - mix) * x + mix * wet * 0.9


def mixadd(*parts):
    """Sum signals of different lengths (zero-padded to the longest)."""
    n = max(len(p) for p in parts); out = np.zeros(n)
    for p in parts: out[:len(p)] += p
    return out


def normalize(x, peak_db=-1.0):
    m = np.abs(x).max()
    return x if m == 0 else x * (10 ** (peak_db / 20) / m)


def fold_loop(x, length):
    """Render longer than `length`, then add the overhang onto the start: an exact seamless loop."""
    y = x[:length].copy(); tail = x[length:]
    while len(tail):
        k = min(len(tail), length); y[:k] += tail[:k]; tail = tail[k:]
    return y


def crossfade_loop(x, length, xfade):
    """Seamless loop of `length` samples from a longer render: the last `xfade` samples blend
    (equal power) from the continuation of the signal into its own beginning, so sample
    length-1 flows into sample 0. Needs len(x) >= length + xfade."""
    x = np.asarray(x, float); X = int(xfade)
    out = x[X:X + length].copy()
    w = np.sin(np.linspace(0, np.pi / 2, X)) ** 2
    a, b = np.sqrt(1 - w), np.sqrt(w)
    if x.ndim == 2: a, b = a[:, None], b[:, None]
    out[length - X:] = x[length:length + X] * a + x[:X] * b
    return out


# ---------------------------------------------------------------- SFX
SFX_PRESETS = ["coin", "jump", "laser", "explosion", "hit", "powerup", "blip", "footstep", "whoosh", "splash", "magic", "click", "alarm", "thud"]


def sfx(preset, seed=0, variation=0.15):
    r = np.random.default_rng(seed)
    j = lambda v, amt=variation: v * (1 + r.uniform(-amt, amt))   # seeded variation

    def render(wave, f0, dur, slide=0.0, vib=(0, 0), duty=0.5, duty_sweep=0.0, att=0.002, dec=None, sus=0.0, punch=0.0,
               lpf=None, lpf_sweep=0.0, hpf=None, arp=None, noise_mix=0.0):
        n = int(dur * SR); t = np.arange(n) / SR
        f = f0 * np.exp(slide * t)
        if vib[0]: f = f * (1 + vib[0] * np.sin(2 * np.pi * vib[1] * t))
        if arp: f = np.where(t > arp[1], f * arp[0], f)
        d = np.clip(duty + duty_sweep * t, 0.05, 0.95)
        x = osc(wave, np.clip(f, 20, 20000), duty=d, rng=r)
        if noise_mix: x = (1 - noise_mix) * x + noise_mix * osc("noise", np.clip(f * 4, 50, 20000), rng=r)
        dec = dur - att if dec is None else dec
        e = env_adsr(n, att, max(0.001, dec), sus, 0.0)
        if punch: e = e * (1 + punch * np.exp(-t / 0.03))
        x = x * e
        if lpf: x = onepole_lp(x, lpf * np.exp(lpf_sweep * t))
        if hpf: x = hp(x, hpf)
        return x

    p = preset
    if p == "coin": x = render("square", j(988), j(0.28), arp=(j(1.5, .05), j(0.06)), duty=0.5, dec=0.26, punch=0.6)
    elif p == "jump": x = render("square", j(260), j(0.32), slide=j(3.2), duty=j(0.3), duty_sweep=0.6, lpf=4500)
    elif p == "laser": x = render("saw", j(1500), j(0.22), slide=-j(9.0), duty=0.4, lpf=7000, hpf=200, punch=0.3)
    elif p == "explosion":
        x = render("noise", j(120), j(1.1), slide=-j(1.2), dec=1.05, punch=1.2, lpf=j(3200), lpf_sweep=-2.2)
        x = reverb(x, 1.4, 0.3, rng=r)
    elif p == "hit": x = render("noise", j(800), j(0.18), slide=-j(6.0), dec=0.17, punch=0.8, lpf=5000, noise_mix=0.0)
    elif p == "powerup": x = render("square", j(300), j(0.7), slide=j(1.6), vib=(0.06, j(14)), duty=0.35, duty_sweep=0.3, lpf=6000, sus=0.4)
    elif p == "blip": x = render("square", j(1200), j(0.08), duty=0.5, dec=0.07, punch=0.3)
    elif p == "click": x = render("triangle", j(2400), j(0.035), slide=-j(20), dec=0.03, hpf=400)
    elif p == "footstep":
        x = mixadd(render("noise", j(300), j(0.14), slide=-j(4), dec=0.12, punch=1.0, lpf=j(1800)) * 0.9,
                   render("sine", j(90), 0.14, slide=-6, dec=0.1) * 0.5)
    elif p == "whoosh":
        n = int(j(0.6) * SR); t = np.arange(n) / SR
        w = band_noise(n, r, j(900), q=0.8)
        sweep = np.sin(np.pi * t / t[-1]) ** 2
        x = onepole_lp(w * sweep, 400 + 5000 * sweep)
    elif p == "splash":
        x = render("noise", j(2000), j(0.7), slide=-j(1.5), dec=0.65, punch=0.8, lpf=j(6000), lpf_sweep=-1.5)
        n = len(x)
        for _ in range(14):   # droplets
            s = int(r.uniform(0.05, 0.6) * SR); dur = int(0.04 * SR)
            if s + dur < n:
                tt = np.arange(dur) / SR; x[s:s + dur] += 0.25 * np.sin(2 * np.pi * r.uniform(900, 2600) * (1 + 3 * tt) * tt) * np.exp(-tt / 0.012)
    elif p == "magic":
        x = mixadd(render("sine", j(660), j(0.9), slide=j(0.8), vib=(0.03, 7), sus=0.3, dec=0.8) * 0.6,
                   render("triangle", j(1320), 0.9, slide=0.8, vib=(0.05, 11), sus=0.2, dec=0.85) * 0.3)
        x = reverb(x, 1.8, 0.45, rng=r)
    elif p == "alarm": x = render("square", j(880), j(0.6), vib=(0.25, j(6)), duty=0.5, sus=0.8, dec=0.1, lpf=5000)
    elif p == "thud": x = mixadd(render("sine", j(110), j(0.35), slide=-j(5), dec=0.33, punch=1.5), 0.3 * render("noise", 200, 0.08, dec=0.07, lpf=900))
    else: raise ValueError(f"unknown preset {preset}; presets: {', '.join(SFX_PRESETS)}")
    x = x - x.mean()
    fade = min(len(x), int(0.004 * SR)); x[-fade:] *= np.linspace(1, 0, fade)
    return normalize(x, -1.0)


# ---------------------------------------------------------------- ambience
AMBIENCES = ["ocean", "wind", "rain", "forest", "cave", "fire", "night", "space", "city"]


def ambience(kind, seconds=20.0, seed=0, stereo=True):
    r = np.random.default_rng(seed); L = int(seconds * SR); n = L + int(2.5 * SR)   # overhang folded onto the head
    t = np.arange(n) / SR

    def events(fn, rate, gain=1.0):
        out = np.zeros(n)
        for _ in range(r.poisson(rate * n / SR)):
            s = int(r.uniform(0, n)); e = fn()
            k = min(len(e), n - s); out[s:s + k] += gain * e[:k]
        return out

    def chirp():   # a bird call: FM sine sweep syllables
        out = []
        for _ in range(r.integers(1, 5)):
            d = r.uniform(0.04, 0.14); m = int(d * SR); tt = np.arange(m) / SR
            f0 = r.uniform(2200, 4800); sweep = r.uniform(-1, 1) * 2500
            out += [np.sin(2 * np.pi * (f0 * tt + sweep * tt * tt / (2 * d)) + 2 * np.sin(2 * np.pi * 40 * tt)) * np.sin(np.pi * tt / d) ** 2,
                    np.zeros(int(r.uniform(0.02, 0.08) * SR))]
        return np.concatenate(out)

    def drip():
        m = int(0.5 * SR); tt = np.arange(m) / SR; f = r.uniform(700, 1500)
        return np.sin(2 * np.pi * f * (1 + 0.8 * np.exp(-tt / 0.01)) * tt) * np.exp(-tt / 0.05)

    def crackle():
        m = int(r.uniform(0.003, 0.02) * SR); return r.standard_normal(m) * np.exp(-np.arange(m) / (m / 3))

    def drop():
        m = int(0.02 * SR); return r.standard_normal(m) * np.exp(-np.arange(m) / (m / 5)) * r.uniform(0.2, 1)

    if kind == "ocean":
        swell = 0.35 + 0.65 * (0.5 + 0.5 * np.sin(2 * np.pi * t / r.uniform(6, 9) + r.uniform(0, 6))) ** 2 * smooth_random(n, r, 0.1, lo=0.6, hi=1.0)
        x = colored_noise(n, r, -1.6) * swell + 0.35 * colored_noise(n, r, -0.4, lo=1500) * swell ** 3
    elif kind == "wind":
        x = sum(band_noise(n, r, c, q=1.2) * smooth_random(n, r, 0.25, lo=0.0, hi=1.0) ** 2 for c in (250, 500, 900, 1600))
        x += 0.4 * colored_noise(n, r, -2.0)
    elif kind == "rain":
        x = 0.6 * colored_noise(n, r, -0.7, lo=300) + events(drop, 220, 0.5)
    elif kind == "forest":
        x = 0.35 * sum(band_noise(n, r, c, q=1.0) * smooth_random(n, r, 0.15, lo=0.2, hi=1.0) for c in (400, 900)) + events(chirp, 0.7, 0.35)
    elif kind == "cave":
        x = 0.25 * colored_noise(n, r, -2.2, hi=400) + events(drip, 0.6, 0.5)
        x = reverb(x, 3.0, 0.55, rng=r)
    elif kind == "fire":
        roar = colored_noise(n, r, -1.8, hi=2000) * smooth_random(n, r, 1.5, lo=0.5, hi=1.0)
        x = 0.6 * roar + events(crackle, 40, 0.8)
    elif kind == "night":
        cr = np.zeros(n)
        for _ in range(4):   # crickets: pulsed high sines
            f = r.uniform(3800, 5200); rate = r.uniform(12, 20); ph = r.uniform(0, 6)
            gate = (np.sin(2 * np.pi * rate * t + ph) > 0.3) * (np.sin(2 * np.pi * r.uniform(0.3, 0.6) * t + ph) > -0.2)
            cr += 0.12 * np.sin(2 * np.pi * f * t) * np.clip(lp_static(gate.astype(float), 60), 0, 1)
        x = cr + 0.15 * colored_noise(n, r, -1.5, hi=1200)
    elif kind == "space":
        x = sum(np.sin(2 * np.pi * f * t + r.uniform(0, 6)) * smooth_random(n, r, 0.08, lo=0.2, hi=1.0) for f in (55, 82.4, 110.2, 164.8))
        x = 0.5 * x + 0.2 * band_noise(n, r, 300, q=0.5) * smooth_random(n, r, 0.05)
        x = reverb(x, 4.0, 0.5, rng=r)
    elif kind == "city":
        x = 0.6 * colored_noise(n, r, -1.8, hi=1500) * smooth_random(n, r, 0.2, lo=0.6, hi=1.0)
        x += 0.15 * band_noise(n, r, 120, q=2) + events(lambda: band_noise(int(1.5 * SR), r, r.uniform(300, 700), 2) * np.hanning(int(1.5 * SR)), 0.15, 0.3)
    else: raise ValueError(f"unknown ambience {kind}; kinds: {', '.join(AMBIENCES)}")
    if stereo:   # decorrelated right channel: a short delay + different filtering
        d = int(0.013 * SR); right = np.roll(x, d) * 0.92 + 0.08 * lp_static(x, 3000) if kind != "space" else np.roll(x, d)
        y = np.stack([crossfade_loop(x, L, SR), crossfade_loop(right, L, SR)], 1)
    else:
        y = crossfade_loop(x, L, SR)
    y = y - y.mean(0)
    return normalize(y, -3.0)


# ---------------------------------------------------------------- music
NOTES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "dorian": [0, 2, 3, 5, 7, 9, 10],
          "mixolydian": [0, 2, 4, 5, 7, 9, 10], "pentatonic": [0, 2, 4, 7, 9], "harmonic_minor": [0, 2, 3, 5, 7, 8, 11]}
MOODS = {  # scale, chord degrees (0-based, one per bar), tempo, drum pattern, lead density
    "heroic": ("major", [0, 4, 5, 3], 120, "march", 0.7), "calm": ("major", [0, 5, 3, 4], 80, "soft", 0.35),
    "tense": ("harmonic_minor", [0, 5, 0, 4], 132, "drive", 0.55), "playful": ("mixolydian", [0, 3, 0, 4], 140, "bounce", 0.75),
    "mysterious": ("dorian", [0, 6, 3, 0], 92, "sparse", 0.4), "sad": ("minor", [0, 5, 2, 6], 72, "soft", 0.3),
    "adventure": ("dorian", [0, 3, 6, 4], 112, "drive", 0.6)}
LAYERS = ["drums", "bass", "pad", "lead", "arp"]


def mtof(m): return 440.0 * 2 ** ((m - 69) / 12)


def _tone(kind, freq, dur, vel, r):
    n = int(dur * SR); t = np.arange(n) / SR
    if kind == "pad":
        x = sum(np.sin(2 * np.pi * freq * k * (1 + dt) * t) / k ** 1.5 for k in range(1, 7) for dt in (-0.003, 0.003))
        e = env_adsr(n, min(0.3, dur / 3), 0.2, 0.8, min(0.6, dur / 2))
    elif kind == "bass":
        x = np.sin(2 * np.pi * freq * t) + 0.35 * np.sign(np.sin(2 * np.pi * freq * t)) * np.exp(-t / 0.08)
        e = env_adsr(n, 0.005, 0.15, 0.6, min(0.08, dur / 3))
    elif kind == "lead":
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.2, 0, 1)
        ph = np.cumsum(freq * vib / SR); x = (1 - 4 * np.abs(ph % 1 - 0.5)) * 0.8 + 0.2 * np.sin(2 * np.pi * 2 * ph)
        e = env_adsr(n, 0.01, 0.1, 0.7, min(0.12, dur / 3))
    elif kind == "arp":   # pluck: decaying harmonics, brighter at the start
        x = sum(np.sin(2 * np.pi * freq * k * t) * np.exp(-t * (3 + 4 * k)) / k for k in range(1, 9))
        e = env_adsr(n, 0.002, dur, 0.0, 0.0)
    return x * e * vel


def _drum(kind, r):
    if kind == "kick":
        n = int(0.35 * SR); t = np.arange(n) / SR
        return np.sin(2 * np.pi * (50 * t + 90 * 0.04 * (1 - np.exp(-t / 0.04)))) * np.exp(-t / 0.12) * 1.0
    if kind == "snare":
        n = int(0.25 * SR); t = np.arange(n) / SR
        return 0.55 * hp(r.standard_normal(n), 1200) * np.exp(-t / 0.06) + 0.4 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    if kind == "hat":
        n = int(0.06 * SR); t = np.arange(n) / SR
        x = np.diff(r.standard_normal(n + 1)); return 0.25 * x * np.exp(-t / 0.015)
    if kind == "tom":
        n = int(0.3 * SR); t = np.arange(n) / SR
        return 0.6 * np.sin(2 * np.pi * 120 * (1 - 0.3 * t) * t) * np.exp(-t / 0.1)


DRUMS = {  # 16 steps per bar
    "march": {"kick": "x...x...x...x...", "snare": "....x.......x.x.", "hat": "x.x.x.x.x.x.x.x."},
    "soft": {"kick": "x.......x.......", "snare": "........x.......", "hat": "..x...x...x...x."},
    "drive": {"kick": "x..x..x.x..x..x.", "snare": "....x.......x...", "hat": "xxxxxxxxxxxxxxxx"},
    "bounce": {"kick": "x.....x.x.......", "snare": "....x.......x...", "hat": "x.xxx.xxx.xxx.xx"},
    "sparse": {"kick": "x...........x...", "tom": "......x.......x.", "hat": "x.......x......."}}


def music(mood="adventure", key="D", bars=8, tempo=None, seed=0, layers=None):
    scale_name, prog, tempo0, pattern, density = MOODS[mood]
    tempo = tempo or tempo0; layers = layers or LAYERS
    r = np.random.default_rng(seed); scale = SCALES[scale_name]; root = 48 + NOTES[key]
    beat = 60.0 / tempo; bar = 4 * beat; step = bar / 16; L = int(round(bars * bar * SR))
    deg = lambda d, octv=0: root + 12 * (octv + d // len(scale)) + scale[d % len(scale)]
    notes = {k: [] for k in layers}
    chords = [prog[b % len(prog)] for b in range(bars)]
    for b, c in enumerate(chords):
        t0 = b * bar
        if "pad" in layers:
            for i in (0, 2, 4): notes["pad"].append((t0, bar, deg(c + i, 1), 0.22))
        if "bass" in layers:
            for s in range(0, 16, 4 if pattern in ("soft", "sparse") else 2):
                d = c if s % 8 == 0 else (c + 4 if r.random() < 0.3 else c)
                notes["bass"].append((t0 + s * step, step * (3.5 if pattern in ("soft", "sparse") else 1.7), deg(d, 0), 0.5))
        if "arp" in layers:
            seq = [0, 2, 4, 7, 4, 2]
            for s in range(0, 16, 2): notes["arp"].append((t0 + s * step, step * 2, deg(c + seq[(s // 2) % len(seq)], 2), 0.18))
    if "lead" in layers:   # a seeded melody: chord tones on strong beats, stepwise motion between
        cur = deg(chords[0] + 4, 2)
        tones = sorted(root + 12 * o + s for o in range(1, 4) for s in scale)
        for b, c in enumerate(chords):
            s = 0
            while s < 16:
                ln = r.choice([2, 2, 4, 4, 6, 8]) if b % 4 != 3 else r.choice([4, 8])
                if r.random() < density or s == 0:
                    if s % 4 == 0:
                        targets = [deg(c + i, 2) for i in (0, 2, 4)]; cur = min(targets, key=lambda m: abs(m - cur) + r.random())
                    else:
                        i = int(np.searchsorted(tones, cur)); cur = tones[int(np.clip(i + r.choice([-2, -1, 1, 2]), 0, len(tones) - 1))]
                    notes["lead"].append((b * bar + s * step, min(ln, 16 - s) * step * 0.95, int(cur), 0.32))
                s += ln
    stems = {}
    for k in layers:
        if k == "drums": continue
        buf = np.zeros(L + int(3 * SR))
        for (t0, d, m, v) in notes[k]:
            x = _tone(k, mtof(m), d + (0.5 if k == "pad" else 0.15), v, r); s = int(t0 * SR); buf[s:s + len(x)] += x
        stems[k] = fold_loop(buf, L)
    if "drums" in layers:
        buf = np.zeros(L + int(1 * SR)); notes["drums"] = []
        pat = DRUMS[pattern]; gm = {"kick": 36, "snare": 38, "hat": 42, "tom": 45}
        hits = {k: _drum(k, np.random.default_rng(seed + 9)) for k in pat}
        for b in range(bars):
            for k, p in pat.items():
                for s, ch in enumerate(p):
                    fill = (b % 4 == 3 and s >= 12 and k == "snare")
                    if ch == "x" or fill:
                        t0 = b * bar + s * step; v = 0.9 if s % 4 == 0 else 0.7
                        x = hits[k] * v; i = int(t0 * SR); buf[i:i + len(x)] += x
                        notes["drums"].append((t0, step, gm[k], v))
        stems["drums"] = fold_loop(buf, L)
    gains = {"drums": 0.8, "bass": 0.7, "pad": 0.55, "lead": 0.6, "arp": 0.45}
    for k in stems: stems[k] = stems[k] / (np.abs(stems[k]).max() + 1e-9) * gains[k]
    mix = sum(stems.values()); peak = np.abs(mix).max() + 1e-9
    scale_all = 10 ** (-1 / 20) / peak
    stems = {k: v * scale_all for k, v in stems.items()}
    return {"stems": stems, "mix": mix * scale_all, "notes": notes, "tempo": tempo, "bars": bars, "key": key, "scale": scale_name,
            "loop_samples": L, "seconds": L / SR, "chords": chords}
