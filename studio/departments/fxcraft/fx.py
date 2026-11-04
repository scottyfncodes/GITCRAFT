"""FXCraft effect simulations (numpy; GITCRAFT's own code). Each effect is a small 2D particle
system advected through a curl-noise field and splatted to RGBA frames.

Looping effects (fire, smoke, magic, energy, rain, snow) are exactly periodic: particles are emitted
with parameters that repeat every N frames and the velocity field is periodic in time, so after a
warm-up longer than any particle's life, frame t+N == frame t. One-shots start and end empty."""
import numpy as np
from core import noise as N

EFFECTS = {"fire": True, "smoke": True, "magic": True, "energy": True, "rain": True, "snow": True,
           "explosion": False, "sparks": False, "dust": False, "splash": False, "lightning": False, "debris": False}   # name: loops


def _ramp(t, stops):
    t = np.clip(t, 0, 1); out = np.zeros(t.shape + (len(stops[0][1]),))
    for i in range(len(stops) - 1):
        (p0, c0), (p1, c1) = stops[i], stops[i + 1]; m = (t >= p0) & (t <= p1); f = ((t - p0) / max(p1 - p0, 1e-9))[m][:, None]
        out[m] = np.array(c0) * (1 - f) + np.array(c1) * f
    out[t > stops[-1][0]] = stops[-1][1]; return out


class Field:
    """Curl of a periodic noise potential: divergence-free swirling velocity, periodic in time."""
    def __init__(self, seed, res=48, frames=32, scale=3):
        sh = (res, res); self.res = res
        self.pots = [N.fbm(sh, scale, 3, seed=seed + 17 * k, tile=True) for k in range(4)]
        self.frames = frames
        gy, gx = np.gradient(self.pots[0]); self.norm = 1.0 / (np.sqrt((gx ** 2 + gy ** 2).mean()) * res + 1e-9)   # unit RMS speed

    def vel(self, x, y, f):
        ph = (f % self.frames) / self.frames * 2 * np.pi
        w = [np.cos(ph) ** 2, np.sin(ph) ** 2]   # blend two potentials smoothly around the loop
        P = self.pots[0] * w[0] + self.pots[1] * w[1]
        gy, gx = np.gradient(P)
        vx = N.sample(gy, x, y); vy = -N.sample(gx, x, y)
        return vx * self.res * self.norm, vy * self.res * self.norm


def splat(S, x, y, inten, size_px, color=None):
    """Bilinear point splats, blurred in two size buckets. x, y in 0..1 (y down). Returns (S, S) or (S, S, 3)."""
    ch = 3 if color is not None else 1
    out = np.zeros((S, S, ch))
    sizes = np.asarray(size_px) * np.ones_like(x)
    for lo, hi in ((0, 3), (3, 7), (7, 1e9)):
        m = (sizes >= lo) & (sizes < hi) & (x >= 0) & (x < 1) & (y >= 0) & (y < 1)
        if not m.any(): continue
        acc = np.zeros((S, S, ch)); px = x[m] * S - 0.5; py = y[m] * S - 0.5
        x0 = np.floor(px).astype(int); y0 = np.floor(py).astype(int); fx = px - x0; fy = py - y0
        val = (inten[m][:, None] * (color[m] if color is not None else 1.0)) if np.ndim(inten) else inten
        for dx, dy, wgt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            xi = np.clip(x0 + dx, 0, S - 1); yi = np.clip(y0 + dy, 0, S - 1)
            np.add.at(acc, (yi, xi), val * wgt[:, None])
        r = int(max(1, (sizes[m].mean() if hi < 1e9 else sizes[m].mean()) / 2.2))
        for _ in range(1):
            acc = np.stack([N.blur(acc[..., c], r, tile=False) for c in range(ch)], -1)
        out += acc * (r * r * 1.6)
    return out if ch == 3 else out[..., 0]


def simulate(effect, S=128, frames=32, seed=0, color=None, intensity=1.0, extra=0):
    """extra: render this many frames past the loop (to verify frame N == frame 0)."""
    rng_master = np.random.default_rng(seed); loops = EFFECTS[effect]
    field = Field(seed, frames=frames)
    per = {"fire": 30, "smoke": 10, "magic": 14, "energy": 0, "rain": 0, "snow": 0}.get(effect, 0)   # particles per frame
    life = {"fire": 22, "smoke": 60, "magic": 30}.get(effect, 0)
    tint = np.array(color, float) / 255 if color is not None else None
    out = []
    if effect in ("fire", "smoke", "magic"):
        # emission table repeats every `frames` frames → exactly periodic after warm-up
        warm = life + 2; P = {k: np.zeros(0) for k in ("x", "y", "vx", "vy", "age", "life", "size", "phase")}
        for f in range(warm + frames + extra):
            r = np.random.default_rng(seed * 7919 + f % frames); n = per   # same emission every `frames` frames
            if effect == "fire": nx = 0.5 + r.normal(0, 0.07, n); ny = np.full(n, 0.88) + r.normal(0, 0.015, n); nvx = r.normal(0, 0.1, n); nvy = -r.uniform(0.6, 1.2, n); nl = r.uniform(0.6, 1.0, n) * life; ns = r.uniform(6, 12, n)
            elif effect == "smoke": nx = 0.5 + r.normal(0, 0.04, n); ny = np.full(n, 0.9); nvx = r.normal(0, 0.05, n); nvy = -r.uniform(0.25, 0.45, n); nl = r.uniform(0.7, 1.0, n) * life; ns = r.uniform(6, 10, n)
            else:
                a = r.uniform(0, 2 * np.pi, n); rad = r.uniform(0.18, 0.3, n); nx = 0.5 + rad * np.cos(a); ny = 0.55 + rad * np.sin(a) * 0.5
                nvx = -np.sin(a) * 0.35; nvy = np.cos(a) * 0.2 - 0.35; nl = r.uniform(0.5, 1.0, n) * life; ns = r.uniform(3, 7, n)
            P = {k: np.concatenate([P[k], v]) for k, v in zip(P, (nx, ny, nvx, nvy, np.zeros(n), nl, ns, r.uniform(0, 6.28, n)))}
            fx, fy = field.vel(P["x"], P["y"], f)
            turb = {"fire": 0.35, "smoke": 0.3, "magic": 0.2}[effect]
            P["x"] = P["x"] + (P["vx"] + fx * turb) / frames * 1.0; P["y"] = P["y"] + (P["vy"] + fy * turb) / frames * 1.0
            P["age"] += 1
            if effect == "smoke": P["size"] *= 1.02
            if effect == "fire": P["vy"] *= 0.98
            keep = P["age"] < P["life"]; P = {k: v[keep] for k, v in P.items()}
            if f < warm: continue
            t = P["age"] / P["life"]
            if effect == "fire":
                heat = np.clip(1 - t, 0, 1) ** 1.3
                dens = splat(S, P["x"], P["y"], heat * 0.9, P["size"] * (1 - 0.5 * t))
                temp = np.clip(dens * 0.9, 0, 1.5)
                rgb = _ramp(np.clip(temp / 1.2, 0, 1), [(0, (0.5, 0.05, 0.0)), (0.35, (1.0, 0.35, 0.02)), (0.7, (1.0, 0.75, 0.2)), (1, (1.0, 0.98, 0.85))])
                a = np.clip(dens * 1.4, 0, 1)
            elif effect == "smoke":
                dens = splat(S, P["x"], P["y"], np.sin(np.pi * t) * 0.35, P["size"])
                base = tint if tint is not None else np.array([0.55, 0.55, 0.58]); rgb = np.ones((S, S, 3)) * base * (0.75 + 0.25 * np.clip(dens, 0, 1))[..., None]
                a = np.clip(dens, 0, 0.9)
            else:
                tw = 0.6 + 0.4 * np.sin(P["phase"] + 2 * np.pi * 4 * f / frames)   # periodic twinkle
                c = tint if tint is not None else np.array([0.55, 0.4, 1.0])
                dens = splat(S, P["x"], P["y"], np.sin(np.pi * t) * tw, P["size"]) * 3.0
                glow = splat(S, P["x"], P["y"], np.sin(np.pi * t) * 0.25, P["size"] * 3)
                rgb = np.clip(c * np.clip(dens + glow, 0, 1)[..., None] * 1.4 + np.clip(dens - 0.5, 0, 1)[..., None], 0, 1); a = np.clip(dens * 1.8 + glow * 1.2, 0, 1)
            out.append(np.concatenate([rgb, a[..., None]], -1))
    elif effect == "energy":
        Y, X = (np.mgrid[0:S, 0:S] + 0.5) / S - 0.5; R = np.hypot(X, Y); A = np.arctan2(Y, X)
        n1 = N.fbm((S, S), 4, 4, seed=seed, tile=True)
        c = tint if tint is not None else np.array([0.3, 0.8, 1.0])
        for f in range(frames + extra):
            ph = 2 * np.pi * f / frames
            ring = np.exp(-((R - 0.3 - 0.03 * np.sin(6 * A + ph * 2)) / 0.035) ** 2)
            swirl = np.clip(np.sin(5 * A - 3 * ph + 12 * R + 3 * n1) * 0.5 + 0.5, 0, 1) ** 3 * np.exp(-((R - 0.22) / 0.12) ** 2)
            core = np.exp(-(R / 0.08) ** 2) * (0.6 + 0.4 * np.sin(ph * 2))
            d = np.clip(ring + 0.8 * swirl + core, 0, 1.5)
            rgb = np.clip(c * d[..., None] + np.clip(d - 0.8, 0, 1)[..., None], 0, 1); out.append(np.concatenate([rgb, np.clip(d, 0, 1)[..., None]], -1))
    elif effect in ("rain", "snow"):
        r = rng_master; n = 140 if effect == "rain" else 110
        x0 = r.random(n); y0 = r.random(n); k = r.integers(1, 3 if effect == "rain" else 2, n)   # whole tiles per loop: wraps exactly
        sz = r.uniform(0.8, 2.2, n); sway = r.uniform(0, 6.28, n)
        for f in range(frames + extra):
            t = f / frames
            y = (y0 + k * t) % 1.0
            if effect == "rain":
                img = np.zeros((S, S))
                for j in range(6):   # streak: several samples along the motion
                    yy = (y - j * 0.012 * k) % 1.0; img += splat(S, x0, yy, np.full(n, 0.12), np.full(n, 1.0))
                img = np.clip(img, 0, 1); rgb = np.ones((S, S, 3)) * np.array([0.75, 0.85, 1.0])
            else:
                x = (x0 + 0.02 * np.sin(2 * np.pi * t + sway)) % 1.0
                img = np.clip(splat(S, x, y, np.full(n, 0.9), sz * 1.6), 0, 1); rgb = np.ones((S, S, 3))
            out.append(np.concatenate([rgb, img[..., None]], -1))
    else:   # one-shots
        r = rng_master
        if effect == "explosion":
            n = 600; a = r.uniform(0, 2 * np.pi, n); sp = r.uniform(0.2, 1.0, n) ** 0.7; x = np.full(n, 0.5); y = np.full(n, 0.6)
            vx = np.cos(a) * sp * 0.9; vy = np.sin(a) * sp * 0.7 - 0.15; size = r.uniform(5, 10, n)
            for f in range(frames):
                t = f / (frames - 1); fx, fy = field.vel(x, y, f)
                x = x + (vx * (1 - t) ** 2 + fx * 0.1) / frames * 2; y = y + (vy * (1 - t) ** 2 + fy * 0.1 - 0.15 * t) / frames * 2
                fire_amt = np.clip(1 - t * 2.2, 0, 1); smoke_amt = (1 - t) ** 1.2 * np.clip(t * 4, 0, 1)   # rises behind the fireball, fades by the last frame
                dens = splat(S, x, y, np.full(n, 0.5), size * (0.7 + 1.6 * t))
                hot = _ramp(np.clip(dens * fire_amt, 0, 1), [(0, (0.15, 0.13, 0.12)), (0.3, (0.9, 0.3, 0.05)), (0.7, (1, 0.7, 0.2)), (1, (1, 1, 0.85))])
                smoke = np.array([0.22, 0.2, 0.2])
                rgb = hot * fire_amt + smoke * (1 - fire_amt); a = np.clip(dens * (fire_amt * 1.4 + smoke_amt * 0.8), 0, 1)
                out.append(np.concatenate([np.clip(rgb, 0, 1), a[..., None]], -1))
        elif effect in ("sparks", "debris", "splash", "dust"):
            n = {"sparks": 160, "debris": 60, "splash": 220, "dust": 260}[effect]
            if effect == "dust":
                a = np.where(r.random(n) < 0.5, r.uniform(-0.3, 0.3, n) + np.pi, r.uniform(-0.3, 0.3, n)); sp = r.uniform(0.15, 0.5, n)
            elif effect == "splash":
                a = -np.pi / 2 + r.normal(0, 0.45, n); sp = r.uniform(0.5, 1.3, n)
            else:
                a = r.uniform(-np.pi, 0, n) if effect == "debris" else r.uniform(0, 2 * np.pi, n); sp = r.uniform(0.4, 1.4, n)
            x = np.full(n, 0.5) + r.normal(0, 0.01, n); y = np.full(n, 0.85 if effect in ("splash", "dust", "debris") else 0.5)
            vx = np.cos(a) * sp; vy = np.sin(a) * sp; g = {"sparks": 1.6, "debris": 2.6, "splash": 2.8, "dust": -0.08}[effect]
            size = r.uniform(*{"sparks": (1, 2), "debris": (3.5, 6.5), "splash": (1.5, 3.5), "dust": (6, 11)}[effect], n)
            for f in range(frames):
                t = f / (frames - 1); dt = 1.0 / frames
                if effect == "dust": vx *= 0.9; vy *= 0.9
                vy = vy + g * dt; px, py = x, y; x = x + vx * dt; y = y + vy * dt
                if effect in ("debris", "splash"): y = np.minimum(y, 0.9)
                fade = (1 - t) ** (0.6 if effect != "dust" else 1.2)
                if effect == "sparks":
                    img = sum(splat(S, px + (x - px) * s, py + (y - py) * s, np.full(n, 0.35 * fade), size) for s in np.linspace(0, 1, 5))
                    rgb = _ramp(np.clip(img, 0, 1), [(0, (1, 0.4, 0.05)), (0.5, (1, 0.8, 0.3)), (1, (1, 1, 0.9))]); a = np.clip(img * 1.5, 0, 1)
                elif effect == "dust":
                    img = splat(S, x, y, np.full(n, 0.25 * fade * np.clip(t * 6, 0, 1)), size * (1 + 1.5 * t))
                    base = tint if tint is not None else np.array([0.62, 0.53, 0.42]); rgb = np.ones((S, S, 3)) * base; a = np.clip(img, 0, 0.85)
                else:
                    img = splat(S, x, y, np.full(n, 0.8 * fade), size)
                    base = tint if tint is not None else (np.array([0.75, 0.9, 1.0]) if effect == "splash" else np.array([0.68, 0.55, 0.42]))
                    rgb = np.ones((S, S, 3)) * base * (0.8 + 0.2 * np.clip(img, 0, 1))[..., None]; a = np.clip(img * 1.5, 0, 1)
                out.append(np.concatenate([np.clip(rgb, 0, 1), a[..., None]], -1))
        elif effect == "lightning":
            def bolt(x0, y0, x1, y1, d, rg):
                if d == 0: return [(x0, y0, x1, y1)]
                mx, my = (x0 + x1) / 2 + rg.normal(0, 0.06 * (d / 6)), (y0 + y1) / 2 + rg.normal(0, 0.02)
                segs = bolt(x0, y0, mx, my, d - 1, rg) + bolt(mx, my, x1, y1, d - 1, rg)
                if d >= 4 and rg.random() < 0.35: segs += bolt(mx, my, mx + rg.normal(0, 0.2), my + rg.uniform(0.1, 0.25), d - 2, rg)
                return segs
            for f in range(frames):
                t = f / (frames - 1); rg = np.random.default_rng(seed + f // 3)
                segs = bolt(0.5, 0.02, 0.5 + rg.normal(0, 0.1), 0.98, 6, rg); pts = []
                for x0, y0, x1, y1 in segs: pts += [(x0 + (x1 - x0) * s, y0 + (y1 - y0) * s) for s in np.linspace(0, 1, 6)]
                pts = np.array(pts); flick = (1 - t) ** 1.5 * (0.6 + 0.4 * (f % 3 == 0))
                core = splat(S, pts[:, 0], pts[:, 1], np.full(len(pts), 0.5 * flick), np.full(len(pts), 1.0))
                glow = splat(S, pts[:, 0], pts[:, 1], np.full(len(pts), 0.08 * flick), np.full(len(pts), 9.0))
                c = tint if tint is not None else np.array([0.6, 0.75, 1.0])
                rgb = np.clip(c * np.clip(glow * 3, 0, 1)[..., None] + np.clip(core, 0, 1)[..., None], 0, 1); a = np.clip(core + glow * 2, 0, 1)
                out.append(np.concatenate([rgb, a[..., None]], -1))
    frames_ = [np.clip(f * np.array([1, 1, 1, intensity]), 0, 1) for f in out]
    return frames_, loops
