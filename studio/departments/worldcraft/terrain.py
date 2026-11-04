"""WorldCraft terrain and environment generators (numpy only, GITCRAFT's own code).

heightfield(preset, ...)  base shape (island falloff, ridges, canyons, volcano cone) from fBm/ridged noise
erode(h, ...)             stream-power hydraulic erosion (D8 flow accumulation) + thermal (talus) erosion
biomes(h, ...)            temperature/moisture → Whittaker-style biome ids, colours, splat weights
poisson(...)              Bridson Poisson-disc sampling for vegetation and rocks
contours(h, level)        marching-squares coastlines as polylines
surface_nets(density)     smooth isosurface mesh for caves (dual contouring without normals)
ocean(...)                Tessendorf FFT ocean, frequencies quantised to the loop period: tiles in space AND time
"""
import numpy as np
from core import noise as N

# ---------------------------------------------------------------- base shapes
PRESETS = ["island", "archipelago", "mountains", "canyon", "plains", "volcano", "coast", "atoll"]


def heightfield(preset, res, seed=0, roughness=0.5):
    sh = (res, res)
    Y, X = np.mgrid[0:res, 0:res] / (res - 1) * 2 - 1
    R = np.sqrt(X ** 2 + Y ** 2)
    base = N.norm01(N.fbm(sh, 3, 7, gain=0.45 + 0.15 * roughness, seed=seed, tile=False))
    ridge = N.norm01(N.fbm(sh, 2, 6, gain=0.5, seed=seed + 1, tile=False, ridged=True))
    dx, dy = N.warp(sh, 2, 0.25, seed, tile=False)
    Rw = np.sqrt((X + dx) ** 2 + (Y + dy) ** 2)
    if preset == "island":
        fall = np.clip(1 - Rw / 0.98, 0, 1) ** 1.1
        h = fall * (0.55 * base + 0.45 * ridge * fall) + 0.08 * base
    elif preset == "archipelago":
        blobs = N.norm01(N.fbm(sh, 3, 3, seed=seed + 5, tile=False))
        fall = np.clip(1 - Rw / 1.1, 0, 1)
        h = np.clip(blobs - 0.45, 0, 1) * 1.8 * fall * (0.6 + 0.4 * base) + 0.1 * base
    elif preset == "mountains":
        h = 0.25 * base + 0.75 * ridge ** 1.5
    elif preset == "canyon":
        river = np.abs(Y + 0.35 * N.fbm(sh, 2, 3, seed=seed + 3, tile=False))
        mesa = np.clip((base - 0.35) * 3, 0, 1)
        h = 0.45 + 0.35 * np.round(mesa * 4) / 4 + 0.08 * base
        h = h * np.clip(river / 0.18, 0.15, 1) ** 0.8
    elif preset == "plains":
        h = 0.3 + 0.18 * base + 0.05 * ridge
    elif preset == "volcano":
        cone = np.clip(1 - Rw / 0.8, 0, 1) ** 1.6
        crater = np.exp(-(Rw / 0.13) ** 2)
        h = cone * 0.9 - crater * 0.35 + 0.12 * base * cone + 0.05 * base
    elif preset == "coast":
        land = np.clip(0.5 + X * 0.9 + 0.35 * (base - 0.5) * 2, 0, 1)
        h = land * (0.4 + 0.6 * ridge * land) * 0.9
    elif preset == "atoll":
        ring = np.exp(-((Rw - 0.55) / 0.09) ** 2)
        h = ring * (0.42 + 0.15 * base) + 0.12 * base * np.clip(1 - Rw, 0, 1)
    else:
        raise ValueError(preset)
    return N.norm01(h)


# ---------------------------------------------------------------- erosion
def flow_accumulation(h):
    """D8 receivers and drainage area (cells), processed from high to low."""
    H, W = h.shape; n = H * W
    pad = np.pad(h, 1, mode="edge")
    offs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    dist = np.array([np.hypot(a, b) for a, b in offs])
    drops = np.stack([(h - pad[1 + a:1 + a + H, 1 + b:1 + b + W]) / d for (a, b), d in zip(offs, dist)])
    k = drops.argmax(0); steep = drops.max(0)
    idx = np.arange(n).reshape(H, W)
    rr = np.clip(np.arange(H)[:, None] + np.array([o[0] for o in offs])[k], 0, H - 1)
    cc = np.clip(np.arange(W)[None, :] + np.array([o[1] for o in offs])[k], 0, W - 1)
    recv = np.where(steep > 0, rr * W + cc, idx).ravel()
    area = np.ones(n); order = np.argsort(-h.ravel(), kind="stable")
    rl = recv.tolist(); al = area.tolist()
    for i in order.tolist():
        j = rl[i]
        if j != i: al[j] += al[i]
    return np.array(al).reshape(H, W), np.maximum(steep, 0)


def erode(h, iterations=12, strength=0.5, thermal=20, talus=None, sea=None):
    h = h.copy(); res = h.shape[0]
    for _ in range(iterations):
        A, S = flow_accumulation(h)
        A = A / (res * res)
        inc = strength * 0.0025 * (A ** 0.5) * (S * res) ** 1.0 / max(1, res / 128)
        if sea is not None: inc *= (h > sea - 0.02)
        h -= np.minimum(inc, 0.02)
        # deposition: the eroded material settles in low-slope basins
        h = 0.92 * h + 0.08 * N.blur(h, 1, tile=False) * (S < 0.02 / res * 128) + 0.08 * h * (S >= 0.02 / res * 128)
    talus = talus or 4.0 / res
    for _ in range(thermal):   # material slides where the slope exceeds the talus angle
        for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
            nb = np.roll(h, sh, ax); d = h - nb
            move = np.where(d > talus, (d - talus) * 0.25, 0)
            h -= move; h += np.roll(move, -sh, ax)
    return N.norm01(h)


# ---------------------------------------------------------------- biomes
BIOMES = {   # id: (name, colour sRGB, splat channel: 0 sand 1 grass 2 rock 3 snow)
    0: ("deep_water", (24, 70, 120), 0), 1: ("shallow_water", (52, 136, 168), 0), 2: ("beach", (226, 205, 150), 0),
    3: ("grassland", (124, 170, 78), 1), 4: ("forest", (62, 122, 58), 1), 5: ("jungle", (38, 110, 52), 1),
    6: ("desert", (214, 186, 120), 0), 7: ("savanna", (176, 172, 90), 1), 8: ("swamp", (82, 104, 66), 1),
    9: ("tundra", (150, 160, 130), 1), 10: ("rock", (120, 112, 104), 2), 11: ("snow", (240, 244, 248), 3)}


def slope_map(h, cell, height_scale):
    gy, gx = np.gradient(h * height_scale, cell)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


DEFAULT_WORLD = {"island": 512, "archipelago": 1024, "mountains": 3000, "canyon": 1200, "plains": 1024, "volcano": 2400, "coast": 1024, "atoll": 512}
DEFAULT_HEIGHT = {"island": 45, "archipelago": 40, "mountains": 450, "canyon": 120, "plains": 30, "volcano": 280, "coast": 60, "atoll": 12}


def biomes(h, sea, slope_deg, seed=0, climate="temperate", height_scale=60.0):
    res = h.shape[0]
    land = h > sea; inland = N.blur(land.astype(float), max(2, res // 24), tile=False)   # ~1 deep inland, ~0.5 at the coast
    wet = {"tropical": 0.3, "temperate": 0.12, "arid": -0.3, "cold": 0.0}[climate]
    moist = np.clip(0.55 * N.norm01(N.fbm(h.shape, 3, 5, seed=seed + 31, tile=False)) + 0.35 * (1 - inland) + 0.1 + wet, 0, 1)
    elev = np.clip((h - sea) / max(1e-6, 1 - sea), 0, 1)
    lapse = 0.85 * float(np.clip(height_scale / 450.0, 0.08, 1.0))   # ~6.5 °C/km: only real height makes snow
    temp = {"tropical": 1.0, "temperate": 0.65, "arid": 0.9, "cold": 0.3}[climate] - elev * lapse
    b = np.full(h.shape, 3)
    b[(moist > 0.55) & (temp > 0.35)] = 4
    b[(moist > 0.75) & (temp > 0.65)] = 5
    b[(moist < 0.3) & (temp > 0.55)] = 6
    b[(moist >= 0.3) & (moist < 0.45) & (temp > 0.7)] = 7
    b[(moist > 0.85) & (elev < 0.12)] = 8
    b[temp < 0.25] = 9
    b[temp < 0.08] = 11
    b[(slope_deg > 38) & land] = 10
    b[(h > sea) & (h < sea + 0.025)] = 2
    b[h <= sea] = 1
    b[h < sea - 0.08] = 0
    return b, moist, temp


def biome_colors(b, h, sea, hillshade=None, climate="temperate"):
    lut = np.array([BIOMES[i][1] for i in range(len(BIOMES))], float) / 255
    if climate == "arid": lut[10] = np.array([178, 106, 72]) / 255   # red sandstone
    c = lut[b]
    depth = np.clip((sea - h) / max(sea, 1e-6), 0, 1)
    c[b <= 1] *= (1 - 0.5 * depth[b <= 1])[:, None]
    if hillshade is not None: c = c * (0.55 + 0.45 * hillshade[..., None])
    return np.clip(c, 0, 1)


def splatmap(b, slope_deg, h, sea):
    ch = np.array([BIOMES[i][2] for i in range(len(BIOMES))])[b]
    S = np.zeros(b.shape + (4,)); S[np.arange(b.shape[0])[:, None], np.arange(b.shape[1])[None, :], ch] = 1.0
    rocky = np.clip((slope_deg - 28) / 15, 0, 1)
    S = S * (1 - rocky[..., None]); S[..., 2] += rocky
    S = np.stack([N.blur(S[..., i], 1, tile=False) for i in range(4)], -1)
    return S / (S.sum(-1, keepdims=True) + 1e-9)


def hillshade(h, height_scale, cell, az=315, alt=45):
    gy, gx = np.gradient(h * height_scale, cell)
    slope = np.pi / 2 - np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
    az, alt = np.radians(az), np.radians(alt)
    return np.clip(np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect), 0, 1)


# ---------------------------------------------------------------- scatter
def poisson(w, h, r, rng, k=20, limit=20000):
    """Bridson's algorithm on a w×h rectangle with minimum distance r."""
    cell = r / np.sqrt(2); gw, gh = int(np.ceil(w / cell)), int(np.ceil(h / cell))
    grid = -np.ones((gh, gw), int); pts = []; active = []
    p0 = (rng.uniform(0, w), rng.uniform(0, h)); pts.append(p0); active.append(0); grid[int(p0[1] / cell), int(p0[0] / cell)] = 0
    while active and len(pts) < limit:
        i = active[rng.integers(len(active))]; px, py = pts[i]; found = False
        for _ in range(k):
            a = rng.uniform(0, 2 * np.pi); d = rng.uniform(r, 2 * r); x, y = px + d * np.cos(a), py + d * np.sin(a)
            if not (0 <= x < w and 0 <= y < h): continue
            gx, gy = int(x / cell), int(y / cell); ok = True
            for yy in range(max(0, gy - 2), min(gh, gy + 3)):
                for xx in range(max(0, gx - 2), min(gw, gx + 3)):
                    j = grid[yy, xx]
                    if j >= 0 and (pts[j][0] - x) ** 2 + (pts[j][1] - y) ** 2 < r * r: ok = False; break
                if not ok: break
            if ok:
                pts.append((x, y)); active.append(len(pts) - 1); grid[gy, gx] = len(pts) - 1; found = True; break
        if not found: active.remove(i)
    return np.array(pts)


SPECIES = {2: [("palm", 0.35)], 3: [("bush", 0.25), ("oak", 0.08), ("grass_tuft", 0.5)], 4: [("oak", 0.55), ("pine", 0.2), ("bush", 0.2)],
           5: [("palm", 0.3), ("jungle_tree", 0.6), ("fern", 0.4)], 6: [("cactus", 0.12), ("dry_bush", 0.12)], 7: [("acacia", 0.15), ("dry_bush", 0.25)],
           8: [("reed", 0.6), ("willow", 0.15)], 9: [("pine", 0.25), ("bush", 0.1)], 10: [], 11: []}


# ---------------------------------------------------------------- contours
def contours(h, level):
    """Marching squares → list of polylines in grid coordinates (x, y)."""
    H, W = h.shape; segs = []
    a = h[:-1, :-1]; b = h[:-1, 1:]; c = h[1:, 1:]; d = h[1:, :-1]
    code = (a > level) * 1 + (b > level) * 2 + (c > level) * 4 + (d > level) * 8
    t = lambda p, q: np.clip((level - p) / np.where(np.abs(q - p) < 1e-12, 1e-12, q - p), 0, 1)
    ys, xs = np.nonzero((code > 0) & (code < 15))
    for y, x in zip(ys.tolist(), xs.tolist()):
        A, B, C, D = h[y, x], h[y, x + 1], h[y + 1, x + 1], h[y + 1, x]
        top = (x + float(t(A, B)), y); right = (x + 1, y + float(t(B, C))); bottom = (x + float(t(D, C)), y + 1); left = (x, y + float(t(A, D)))
        cd = int(code[y, x])
        table = {1: [(left, top)], 2: [(top, right)], 3: [(left, right)], 4: [(right, bottom)], 5: [(left, top), (right, bottom)], 6: [(top, bottom)],
                 7: [(left, bottom)], 8: [(bottom, left)], 9: [(bottom, top)], 10: [(top, right), (bottom, left)], 11: [(bottom, right)],
                 12: [(right, left)], 13: [(right, top)], 14: [(top, left)]}
        segs += table[cd]
    # chain segments into polylines
    key = lambda p: (round(p[0], 4), round(p[1], 4))
    nbr = {}
    for i, (p, q) in enumerate(segs): nbr.setdefault(key(p), []).append((i, 1)); nbr.setdefault(key(q), []).append((i, 0))
    used = [False] * len(segs); lines = []
    for i in range(len(segs)):
        if used[i]: continue
        used[i] = True; line = [segs[i][0], segs[i][1]]
        for end in (1, 0):
            while True:
                tip = line[-1] if end else line[0]; nxt = None
                for j, side in nbr.get(key(tip), []):
                    if not used[j]: nxt = (j, side); break
                if not nxt: break
                j, side = nxt; used[j] = True; p = segs[j][side] if key(segs[j][1 - side]) == key(tip) else segs[j][1 - side]
                if end: line.append(p)
                else: line.insert(0, p)
        lines.append(line)
    return lines


# ---------------------------------------------------------------- caves (surface nets)
def surface_nets(D, cell=1.0):
    """Isosurface of D=0 (solid D>0). Returns vertices (n,3) in (x, y, z) world units and quads → tris."""
    nz, ny, nx = D.shape
    c = [D[z0:nz - 1 + z0, y0:ny - 1 + y0, x0:nx - 1 + x0] for z0 in (0, 1) for y0 in (0, 1) for x0 in (0, 1)]
    C = np.stack(c, -1)   # (nz-1, ny-1, nx-1, 8) corner order: z,y,x bits
    s = C > 0; mixed = s.any(-1) & ~s.all(-1)
    corners = np.array([(z, y, x) for z in (0, 1) for y in (0, 1) for x in (0, 1)], float)
    edges = [(i, j) for i in range(8) for j in range(i + 1, 8) if np.abs(corners[i] - corners[j]).sum() == 1]
    acc = np.zeros(C.shape[:3] + (3,)); cnt = np.zeros(C.shape[:3])
    for i, j in edges:
        a, b = C[..., i], C[..., j]; cross = (a > 0) != (b > 0)
        t = np.where(cross, a / np.where(a - b == 0, 1e-9, a - b), 0)
        p = corners[i] + (corners[j] - corners[i]) * t[..., None]
        acc += p * cross[..., None]; cnt += cross
    vid = -np.ones(C.shape[:3], int); zz, yy, xx = np.nonzero(mixed); vid[zz, yy, xx] = np.arange(len(zz))
    V = (np.stack([zz, yy, xx], -1) + acc[zz, yy, xx] / cnt[zz, yy, xx, None])
    tris = []
    for ax in range(3):   # an edge of the voxel grid along axis `ax` with a sign change → one quad of the 4 cells around it
        sl0 = [slice(1, -1)] * 3; sl0[ax] = slice(0, -1); sl1 = list(sl0); sl1[ax] = slice(1, None)
        a = D[tuple(sl0)] > 0; b = D[tuple(sl1)] > 0; edge = a != b
        idx = np.argwhere(edge)
        if not len(idx): continue
        base = idx.copy(); base[:, [k for k in range(3) if k != ax]] += 1   # voxel index of the edge's start in D
        o = [k for k in range(3) if k != ax]
        cellsets = []
        for d0, d1 in ((0, 0), (1, 0), (1, 1), (0, 1)):
            cc = base.copy(); cc[:, o[0]] -= d0; cc[:, o[1]] -= d1; cellsets.append(vid[cc[:, 0], cc[:, 1], cc[:, 2]])
        q = np.stack(cellsets, 1); flip = a[tuple(idx.T)]
        if ax == 1: flip = ~flip
        q = np.where(flip[:, None], q[:, ::-1], q)
        good = (q >= 0).all(1); q = q[good]
        tris.append(np.concatenate([q[:, [0, 1, 2]], q[:, [0, 2, 3]]]))
    F = np.concatenate(tris) if tris else np.zeros((0, 3), int)
    P = V[:, [2, 0, 1]] * cell   # (x, y=z-up-in-volume, z) → Y up: use volume z as height
    return P, F


def cave_density(res, seed=0, tunnels=6, radius=0.09):
    """Solid rock (D>0) with worm tunnels and noise chambers carved out; borders kept solid."""
    rng = np.random.default_rng(seed); nz = res // 2; sh = (nz, res, res)
    Z, Y, X = np.meshgrid(np.linspace(0, 0.5, nz), np.linspace(0, 1, res), np.linspace(0, 1, res), indexing="ij")
    D = np.ones(sh)
    nse = N.value3d(sh, 6, seed)
    for t in range(tunnels):
        p = np.array([rng.uniform(0.2, 0.8), rng.uniform(0.2, 0.8), rng.uniform(0.15, 0.35)]); d = rng.normal(size=3); d[2] *= 0.25; d /= np.linalg.norm(d)
        for step in range(40):
            rr = radius * (0.7 + 0.6 * rng.random())
            dist = np.sqrt((X - p[0]) ** 2 + (Y - p[1]) ** 2 + ((Z - p[2]) * 1.4) ** 2)
            D = np.minimum(D, (dist - rr) / rr)
            d = d + rng.normal(scale=0.35, size=3); d[2] *= 0.3; d /= np.linalg.norm(d); p = p + d * rr * 0.6
            p = np.clip(p, [0.12, 0.12, 0.1], [0.88, 0.88, 0.4])
    D = D + 0.35 * nse
    border = np.minimum.reduce([X, 1 - X, Y, 1 - Y, Z * 2, (0.5 - Z) * 2])
    D = np.where(border < 0.06, np.abs(D) + 1, D)
    return D


# ---------------------------------------------------------------- ocean
def ocean(res=128, size=64.0, wind=12.0, direction=0.0, period=8.0, frames=32, choppy=1.2, seed=0, amplitude=1.0):
    """Tessendorf (2001) spectrum on a size×size m tile. Each wave's angular frequency is rounded to
    a multiple of 2π/period, so frame `frames` equals frame 0: a seamless loop in time and space."""
    rng = np.random.default_rng(seed); g = 9.81
    k1 = 2 * np.pi * np.fft.fftfreq(res, size / res)
    KX, KZ = np.meshgrid(k1, k1); K = np.hypot(KX, KZ); K[0, 0] = 1e-6
    Lw = wind ** 2 / g; wdir = np.array([np.cos(direction), np.sin(direction)])
    kd = (KX * wdir[0] + KZ * wdir[1]) / K
    P = amplitude * 3e-3 * np.exp(-1 / (K * Lw) ** 2) / K ** 4 * kd ** 2 * np.exp(-(K * 0.05) ** 2)
    P[kd < 0] *= 0.07; P[0, 0] = 0
    h0 = (rng.normal(size=K.shape) + 1j * rng.normal(size=K.shape)) * np.sqrt(P / 2)
    h0c = np.conj(np.roll(np.flip(h0), 1, (0, 1)))
    w0 = 2 * np.pi / period; w = np.round(np.sqrt(g * K) / w0) * w0
    out = []
    for f in range(frames):
        t = period * f / frames
        hk = h0 * np.exp(1j * w * t) + h0c * np.exp(-1j * w * t)
        hgt = np.real(np.fft.ifft2(hk)) * res * res / 50
        dx = np.real(np.fft.ifft2(-1j * KX / K * hk)) * res * res / 50 * choppy
        dz = np.real(np.fft.ifft2(-1j * KZ / K * hk)) * res * res / 50 * choppy
        out.append((hgt, dx, dz))
    return out
