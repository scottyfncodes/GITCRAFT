"""Vectorised, seedable, tileable noise for terrain, materials and effects (numpy only).

All 2D functions take a resolution and a period in lattice cells; with tile=True the result
wraps seamlessly at the edges (materials, water, flipbook tiles)."""
import numpy as np


def _grad_table(rng, n):
    a = rng.uniform(0, 2 * np.pi, n); return np.stack([np.cos(a), np.sin(a)], -1)


def perlin(shape, period, seed=0, tile=True, offset=(0.0, 0.0)):
    """Gradient noise in about [-1, 1]. shape=(h, w); `period` lattice cells across the width."""
    h, w = shape; rng = np.random.default_rng(seed)
    px = period; py = max(1, int(round(period * h / w)))
    G = _grad_table(rng, (py + 1) * (px + 1)).reshape(py + 1, px + 1, 2)
    if tile: G[-1, :] = G[0, :]; G[:, -1] = G[:, 0]
    y = (np.arange(h) / h) * py + offset[1]; x = (np.arange(w) / w) * px + offset[0]
    X, Y = np.meshgrid(x, y)
    xi = np.floor(X).astype(int); yi = np.floor(Y).astype(int); xf = X - xi; yf = Y - yi
    xi %= px; yi %= py

    def g(ix, iy, dx, dy):
        gg = G[iy, ix]; return gg[..., 0] * dx + gg[..., 1] * dy
    n00 = g(xi, yi, xf, yf); n10 = g(xi + 1, yi, xf - 1, yf); n01 = g(xi, yi + 1, xf, yf - 1); n11 = g(xi + 1, yi + 1, xf - 1, yf - 1)
    u = xf ** 3 * (xf * (xf * 6 - 15) + 10); v = yf ** 3 * (yf * (yf * 6 - 15) + 10)
    return ((n00 * (1 - u) + n10 * u) * (1 - v) + (n01 * (1 - u) + n11 * u) * v) * 1.41421


def fbm(shape, period=4, octaves=6, lacunarity=2, gain=0.5, seed=0, tile=True, ridged=False, offset=(0, 0)):
    out = np.zeros(shape); amp = 1.0; total = 0; p = period
    for o in range(octaves):
        n = perlin(shape, int(p), seed + 101 * o, tile, offset)
        if ridged: n = 1 - np.abs(n); n = n * n
        out += amp * n; total += amp; amp *= gain; p *= lacunarity
    return out / total


def norm01(a):
    lo, hi = float(a.min()), float(a.max()); return (a - lo) / (hi - lo + 1e-12)


def worley(shape, cells=8, seed=0, tile=True, second=False):
    """Cellular noise with one jittered feature point per grid cell; each pixel checks only the
    3×3 neighbouring cells (wrapping when tile=True). Returns F1, or (F1, F2, cell id)."""
    h, w = shape; rng = np.random.default_rng(seed)
    cx = max(1, int(cells)); cy = max(1, int(round(cells * h / w)))
    jit = rng.random((cy, cx, 2))
    Y, X = np.mgrid[0:h, 0:w]; u = X / w * cx; v = Y / h * cy
    ix = np.floor(u).astype(int); iy = np.floor(v).astype(int)
    d1 = np.full(shape, np.inf); d2 = np.full(shape, np.inf); cid = np.zeros(shape, int)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            nx, ny = ix + ox, iy + oy
            wx, wy = (nx % cx, ny % cy) if tile else (np.clip(nx, 0, cx - 1), np.clip(ny, 0, cy - 1))
            px = nx + jit[wy, wx, 0]; py = ny + jit[wy, wx, 1]
            d = np.sqrt((px - u) ** 2 + (py - v) ** 2)
            closer = d < d1
            d2 = np.where(closer, d1, np.minimum(d2, d)); cid = np.where(closer, wy * cx + wx, cid); d1 = np.where(closer, d, d1)
    return (d1, d2, cid) if second else d1


def warp(shape, period=4, strength=0.1, seed=0, tile=True):
    """Domain-warp offsets (dx, dy) in UV units."""
    return fbm(shape, period, 4, seed=seed + 7, tile=tile) * strength, fbm(shape, period, 4, seed=seed + 13, tile=tile) * strength


def sample(img, u, v):
    """Bilinear, wrapping lookup of img (h, w[, c]) at UV arrays."""
    h, w = img.shape[:2]; x = (u % 1) * w - 0.5; y = (v % 1) * h - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    x0 %= w; y0 %= h; x1 = (x0 + 1) % w; y1 = (y0 + 1) % h
    if img.ndim == 3: fx = fx[..., None]; fy = fy[..., None]
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x1] * fx * (1 - fy) + img[y1, x0] * (1 - fx) * fy + img[y1, x1] * fx * fy)


def value3d(shape, period, seed=0):
    """Smooth 3D value noise (d, h, w) in [-1, 1] (caves)."""
    rng = np.random.default_rng(seed); d, h, w = shape
    L = rng.uniform(-1, 1, (period + 2, period + 2, period + 2))
    z, y, x = [np.linspace(0, period, n, endpoint=False) for n in shape]
    Z, Y, X = np.meshgrid(z, y, x, indexing="ij")
    zi, yi, xi = Z.astype(int), Y.astype(int), X.astype(int)
    fz, fy, fx = [t - t.astype(int) for t in (Z, Y, X)]
    fz, fy, fx = [t * t * (3 - 2 * t) for t in (fz, fy, fx)]
    out = 0
    for dz in (0, 1):
        for dy in (0, 1):
            for dx in (0, 1):
                wgt = (fz if dz else 1 - fz) * (fy if dy else 1 - fy) * (fx if dx else 1 - fx)
                out = out + wgt * L[zi + dz, yi + dy, xi + dx]
    return out


def normal_map(height, strength=4.0, tile=True):
    """Height (0..1) → tangent-space normal map (OpenGL / glTF convention, +Y up), RGB 0..1."""
    if tile:
        dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / 2; dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / 2
    else:
        dy, dx = np.gradient(height)
    s = strength * height.shape[1] / 256
    n = np.stack([-dx * s, dy * s, np.ones_like(height)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def blur(a, r=2, tile=True):
    """Separable box blur (3 passes ≈ gaussian)."""
    out = a.astype(np.float64)
    for _ in range(3):
        for ax in (0, 1):
            acc = np.zeros_like(out)
            for k in range(-r, r + 1):
                acc += np.roll(out, k, ax) if tile else np.take(out, np.clip(np.arange(out.shape[ax]) + k, 0, out.shape[ax] - 1), axis=ax)
            out = acc / (2 * r + 1)
    return out
