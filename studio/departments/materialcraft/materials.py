"""MaterialCraft generators: every function returns tileable maps on an n×n grid (numpy, 0..1):
  albedo (n,n,3) sRGB, height (n,n), roughness (n,n), metallic (n,n), optional emission (n,n,3).
Normal, AO and the packed ORM map are derived from these in dept.py. All noise wraps (tile=True)."""
import numpy as np
from core import noise as N

MATERIALS = ["stone", "cobblestone", "brick", "wood", "planks", "metal", "brushed_metal", "rust", "fabric", "leather",
             "sand", "grass", "dirt", "tiles", "ice", "lava", "water", "marble", "concrete", "bark", "snow"]


def _c(rgb): return np.array(rgb, float) / 255


def _mix(a, b, t): t = np.asarray(t)[..., None] if np.ndim(t) == 2 else t; return a * (1 - t) + b * t


def _ramp(t, stops):
    """Colour ramp: stops = [(pos, rgb255), ...]."""
    t = np.clip(t, 0, 1); out = np.zeros(t.shape + (3,))
    pos = [s[0] for s in stops]; cols = [_c(s[1]) for s in stops]
    for i in range(len(stops) - 1):
        m = (t >= pos[i]) & (t <= pos[i + 1]); f = ((t - pos[i]) / max(1e-9, pos[i + 1] - pos[i]))[m]
        out[m] = cols[i] * (1 - f[:, None]) + cols[i + 1] * f[:, None]
    out[t < pos[0]] = cols[0]; out[t > pos[-1]] = cols[-1]
    return out


def _uv(n):
    y, x = np.mgrid[0:n, 0:n] / n; return x, y


def generate(kind, n=512, seed=0, scale=1.0, color=None):
    sh = (n, n); s = max(1, int(round(4 * scale))); r = np.random.default_rng(seed)
    f = lambda per, oct=5, sd=0, **k: N.norm01(N.fbm(sh, max(1, int(per)), oct, seed=seed + sd, tile=True, **k))
    em = None; met = np.zeros(sh)
    if kind == "stone":
        F1, F2, _ = N.worley(sh, 3 * s, seed, second=True); cracks = np.clip((F2 - F1) * 6, 0, 1)
        h = 0.6 * f(s) + 0.25 * f(4 * s, 4, 3) + 0.15 * cracks; alb = _ramp(0.3 * f(2 * s, 4, 5) + 0.7 * h, [(0, (70, 66, 62)), (0.6, (128, 122, 114)), (1, (170, 164, 154))])
        rough = 0.75 + 0.2 * f(6 * s, 3, 7)
    elif kind == "cobblestone":
        F1, F2, cid = N.worley(sh, 5 * s, seed, second=True); edge = np.clip((F2 - F1) * 3.2, 0, 1)
        stone = edge ** 0.5; h = stone * (0.8 + 0.2 * f(8 * s, 3, 2)) * (edge > 0.08)
        tint = r.uniform(0.85, 1.15, cid.max() + 1)[cid]
        alb = _mix(_c((62, 56, 50)) * np.ones(sh + (3,)), _ramp(f(6 * s, 4, 9), [(0, (96, 92, 88)), (1, (150, 144, 136))]) * tint[..., None], (edge > 0.08).astype(float))
        rough = np.where(edge > 0.08, 0.7, 0.95)
    elif kind in ("brick", "tiles"):
        rows = 8 * s if kind == "brick" else 6 * s; cols = rows // 2 if kind == "brick" else rows
        x, y = _uv(n); ry = y * rows; row = np.floor(ry).astype(int)
        rx = x * cols + (0.5 * (row % 2) if kind == "brick" else 0); col = np.floor(rx).astype(int) % cols
        gx = np.abs(rx - np.round(rx)); gy = np.abs(ry - np.round(ry)); gw = 0.05 if kind == "brick" else 0.035
        mortar = np.clip(1 - np.minimum(gx * (cols / rows) * (2 if kind == "brick" else 1), gy) / gw, 0, 1) ** 2
        cid = (row % rows) * cols + col; tint = r.uniform(0.82, 1.12, rows * cols + 1)[cid]
        if kind == "brick":
            base = _ramp(f(10 * s, 4, 4), [(0, (130, 58, 40)), (1, (176, 88, 60))]) * tint[..., None]
            alb = _mix(base, _c((178, 170, 156)) * np.ones(sh + (3,)), mortar); h = (1 - mortar) * (0.85 + 0.15 * f(12 * s, 4, 6)); rough = 0.85 - 0.1 * (1 - mortar)
        else:
            base = (color if color is not None else _c((214, 222, 226))) * (0.95 + 0.05 * tint[..., None])
            alb = _mix(base * np.ones(sh + (3,)), _c((120, 118, 112)) * np.ones(sh + (3,)), mortar); h = 1 - mortar * 0.8; rough = 0.18 + 0.6 * mortar
    elif kind in ("wood", "planks", "bark"):
        x, y = _uv(n); dx, dy = N.warp(sh, 2, 0.08, seed); per = 2 * s
        if kind == "bark":
            ridges = N.norm01(N.fbm(sh, per, 5, seed=seed, tile=True, ridged=True, lacunarity=2))
            stretch = N.norm01(N.fbm((n, n), max(1, per // 3), 4, seed=seed + 5, tile=True))
            h = 0.6 * ridges + 0.4 * stretch; alb = _ramp(h, [(0, (40, 30, 22)), (0.5, (86, 66, 48)), (1, (122, 100, 76))]); rough = 0.9 * np.ones(sh)
        else:
            rings = np.sin((y + dy * 2 + 0.15 * np.sin(2 * np.pi * (x + dx))) * 2 * np.pi * 12 * s) * 0.5 + 0.5
            grain = f(16 * s, 3, 8)
            t = 0.65 * rings ** 3 + 0.35 * grain; h = 0.5 + 0.2 * t
            alb = _ramp(t, [(0, (150, 104, 62)), (0.6, (120, 80, 46)), (1, (82, 52, 30))]); rough = 0.6 + 0.2 * grain
            if kind == "planks":
                boards = 2 * s; bx = x * boards; bid = np.floor(bx).astype(int); seam = np.clip(1 - np.abs(bx - np.round(bx)) / 0.02, 0, 1)
                gap = seam; tint = r.uniform(0.85, 1.12, boards + 1)[bid % boards]
                alb = _mix(alb * tint[..., None], _c((30, 20, 14)) * np.ones(sh + (3,)), gap); h = h * (1 - gap * 0.9); rough = rough + 0.2 * gap
    elif kind in ("metal", "brushed_metal", "rust"):
        x, y = _uv(n)
        # brushing: fine streaks that vary down the texture and run along x
        brushed = np.repeat(N.norm01(N.fbm((8, n), 96, 4, seed=seed, tile=True)[0])[:, None], n, 1) if kind == "brushed_metal" else None
        base_col = color if color is not None else _c((176, 180, 186))
        if kind == "brushed_metal":
            streak = N.norm01(N.fbm((n, n), 2, 3, seed=seed + 1)) * 0.3 + 0.7 * N.norm01(brushed)
            alb = base_col * (0.85 + 0.15 * streak[..., None]); rough = 0.25 + 0.15 * streak; h = 0.5 + 0.02 * streak; met = np.ones(sh)
        else:
            v = f(3 * s, 5, 1); alb = base_col * (0.8 + 0.2 * v[..., None]); rough = 0.35 + 0.25 * f(8 * s, 4, 2); h = 0.5 + 0.05 * v; met = np.ones(sh)
        if kind == "rust":
            mask = np.clip((f(3 * s, 6, 11) - 0.45) * 5, 0, 1)
            rust_c = _ramp(f(10 * s, 4, 12), [(0, (92, 40, 20)), (0.5, (150, 72, 32)), (1, (190, 110, 52))])
            alb = _mix(alb, rust_c, mask); rough = _mix(rough[..., None], np.full(sh + (1,), 0.92), mask)[..., 0]; met = 1 - mask * 0.95
            h = h + 0.08 * mask * f(16 * s, 3, 13)
    elif kind == "fabric":
        x, y = _uv(n); k = 48 * s
        wx = np.sin(2 * np.pi * x * k) * 0.5 + 0.5; wy = np.sin(2 * np.pi * y * k) * 0.5 + 0.5
        checker = ((np.floor(x * k) + np.floor(y * k)) % 2)
        h = np.where(checker > 0, wx, wy) * 0.7 + 0.3 * f(32 * s, 3, 3)
        base = color if color is not None else _c((92, 104, 150)); alb = base * (0.75 + 0.3 * h[..., None]); rough = 0.85 + 0.1 * h
    elif kind == "leather":
        F1, F2, _ = N.worley(sh, 18 * s, seed, second=True); crease = np.clip((F2 - F1) * 4, 0, 1)
        h = 0.7 * crease ** 0.6 + 0.3 * f(10 * s, 4, 3); base = color if color is not None else _c((110, 64, 38))
        alb = base * (0.7 + 0.35 * h[..., None]); rough = 0.55 + 0.25 * (1 - crease)
    elif kind == "sand":
        x, y = _uv(n); dx, dy = N.warp(sh, 2, 0.15, seed)
        ripples = np.sin(2 * np.pi * (y + dy + 0.3 * dx) * 10 * s) * 0.5 + 0.5; grains = f(64 * s, 2, 4)
        h = 0.6 * ripples + 0.4 * grains; alb = _ramp(0.4 * ripples + 0.6 * f(4 * s, 4, 6), [(0, (196, 168, 118)), (1, (232, 210, 160))]) * (0.92 + 0.08 * grains[..., None]); rough = 0.9 * np.ones(sh)
    elif kind == "grass":
        blades = N.norm01(N.fbm(sh, 48 * s, 3, seed=seed, tile=True, ridged=True)); patch = f(3 * s, 4, 4)
        h = 0.6 * blades + 0.4 * patch; alb = _ramp(0.5 * blades + 0.5 * patch, [(0, (52, 92, 34)), (0.5, (86, 136, 50)), (1, (150, 176, 74))]); rough = 0.85 * np.ones(sh)
    elif kind == "dirt":
        F1 = N.worley(sh, 24 * s, seed); pebble = np.clip(1 - F1 * 2.5, 0, 1)
        h = 0.6 * f(4 * s, 6, 1) + 0.4 * pebble; alb = _mix(_ramp(f(4 * s, 5, 2), [(0, (70, 50, 34)), (1, (124, 94, 64))]), _c((140, 132, 120)) * np.ones(sh + (3,)), (pebble > 0.4) * 0.8); rough = 0.95 * np.ones(sh)
    elif kind == "ice":
        F1, F2, _ = N.worley(sh, 4 * s, seed, second=True); cracks = np.clip(1 - (F2 - F1) * 12, 0, 1)
        h = 0.7 - 0.4 * cracks + 0.1 * f(8 * s, 4, 3); alb = _mix(_ramp(f(3 * s, 4, 5), [(0, (150, 196, 222)), (1, (214, 238, 248))]), np.ones(sh + (3,)), cracks * 0.7); rough = 0.06 + 0.3 * cracks
    elif kind == "lava":
        F1, F2, _ = N.worley(sh, 5 * s, seed, second=True); gap = np.clip(1 - (F2 - F1) * 5, 0, 1) ** 2
        crust = f(6 * s, 5, 2); h = (1 - gap) * (0.6 + 0.4 * crust)
        alb = _mix(_ramp(crust, [(0, (28, 22, 20)), (1, (66, 54, 48))]), _c((255, 120, 20)) * np.ones(sh + (3,)), gap)
        em = _ramp(gap, [(0, (0, 0, 0)), (0.4, (180, 40, 0)), (1, (255, 190, 60))]) * (gap[..., None] > 0.02); rough = 0.9 - 0.5 * gap
    elif kind == "water":
        h = 0.6 * f(3 * s, 5, 1) + 0.4 * f(9 * s, 4, 2); alb = _ramp(h, [(0, (12, 54, 86)), (1, (28, 96, 130))]); rough = 0.04 + 0.04 * h
    elif kind == "marble":
        x, y = _uv(n); turb = N.fbm(sh, 2 * s, 6, seed=seed, tile=True)
        veins = np.abs(np.sin(2 * np.pi * (x * 2 * s + y * s + turb * 2.5))) ** 0.25
        alb = _ramp(veins, [(0, (90, 88, 92)), (0.5, (196, 194, 196)), (1, (244, 242, 238))]); h = 0.5 + 0.05 * veins; rough = 0.12 + 0.1 * (1 - veins)
    elif kind == "concrete":
        pores = np.clip(1 - N.worley(sh, 40 * s, seed) * 4, 0, 1) ** 3; v = f(6 * s, 6, 2)
        h = 0.7 * v - 0.3 * pores; alb = _ramp(v, [(0, (120, 120, 116)), (1, (168, 166, 160))]) * (1 - 0.3 * pores[..., None]); rough = 0.85 * np.ones(sh)
    elif kind == "snow":
        h = 0.7 * f(3 * s, 5, 1) + 0.3 * f(20 * s, 3, 2); alb = _ramp(h, [(0, (214, 224, 236)), (1, (250, 252, 255))]); rough = 0.6 + 0.2 * f(30 * s, 2, 3)
    else:
        raise ValueError(f"unknown material {kind}; one of {', '.join(MATERIALS)}")
    if color is not None and kind in ("stone", "cobblestone", "brick", "wood", "planks", "sand", "grass", "dirt", "marble", "concrete", "bark", "snow"):
        lum = alb.mean(-1, keepdims=True); alb = np.clip(alb * 0.35 + color * lum / max(color.mean(), 1e-3) * 0.65, 0, 1)
    return {"albedo": np.clip(alb, 0, 1), "height": N.norm01(h), "roughness": np.clip(rough, 0.02, 1), "metallic": np.clip(met, 0, 1), "emission": em}


def weather(m, dirt=0.0, moss=0.0, wear=0.0, wet=0.0, seed=0):
    """Weathering layers driven by the height field: dirt and moss collect in cavities, wear lightens peaks."""
    h = m["height"]; n = h.shape[0]; sh = h.shape
    cav = np.clip((N.blur(h, max(2, n // 64)) - h) * 6 + 0.5, 0, 1)
    if dirt:
        mask = np.clip((cav - 0.45) * 3 + (N.norm01(N.fbm(sh, 4, 5, seed=seed + 51)) - 0.5), 0, 1) * dirt
        m["albedo"] = _mix(m["albedo"], _c((74, 58, 40)) * np.ones(sh + (3,)), mask * 0.85); m["roughness"] = np.maximum(m["roughness"], 0.9 * mask)
        m["metallic"] = m["metallic"] * (1 - mask)
    if moss:
        mask = np.clip((N.norm01(N.fbm(sh, 3, 6, seed=seed + 61)) - (1 - moss)) * 4 * (0.4 + cav), 0, 1)
        m["albedo"] = _mix(m["albedo"], _ramp(N.norm01(N.fbm(sh, 24, 3, seed=seed + 62)), [(0, (52, 82, 30)), (1, (98, 128, 52))]), mask)
        m["roughness"] = _mix(m["roughness"][..., None], np.full(sh + (1,), 0.95), mask)[..., 0]; m["height"] = np.clip(m["height"] + 0.06 * mask, 0, 1)
        m["metallic"] = m["metallic"] * (1 - mask)
    if wear:
        peaks = np.clip((h - N.blur(h, max(2, n // 128))) * 10, 0, 1) * wear
        m["albedo"] = np.clip(m["albedo"] * (1 + 0.35 * peaks[..., None]), 0, 1); m["roughness"] = np.clip(m["roughness"] - 0.25 * peaks, 0.02, 1)
    if wet:
        m["albedo"] = m["albedo"] * (1 - 0.35 * wet); m["roughness"] = np.clip(m["roughness"] * (1 - 0.7 * wet), 0.03, 1)
    return m


def toonify(m, bands=4):
    a = m["albedo"]; lum = a.mean(-1, keepdims=True)
    q = np.round(lum * bands) / bands; m["albedo"] = np.clip(a * (q / np.maximum(lum, 1e-3)) * 0.5 + a * 0.5, 0, 1)
    m["albedo"] = np.round(m["albedo"] * (bands * 2)) / (bands * 2)
    m["height"] = N.blur(m["height"], 2); m["roughness"] = np.full_like(m["roughness"], 0.8)
    return m
