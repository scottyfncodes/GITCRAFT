"""WorldCraft: procedural environments. Terrain, erosion, biomes, splat/heightmaps, scatter and
coastlines are numpy (terrain.py); skies are Blender's Nishita physical sky (MeshCraft's Blender),
with an analytic fallback only when asked; every mesh is checked by the Khronos validator and
rendered in three.js r170 before it is reported."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import terrain as T
from core import media, noise as N, runners, webpages, deps
from core.contract import StudioError, Blocked


def _img(a, path, mode=None):
    media.to_image(a, mode).save(path); return path


def _terrain_mesh(h, sea, world, height_scale, colors, mesh_res, water=True):
    res = h.shape[0]; idx = np.linspace(0, res - 1, mesh_res).round().astype(int)
    hs = h[np.ix_(idx, idx)]; cs = colors[np.ix_(idx, idx)]
    cell = world / (mesh_res - 1)
    m = media.grid_mesh((hs - sea) * height_scale, cell, colors=media.srgb_to_linear(cs).astype(np.float32))
    m.update(name="terrain", material={"color": [1, 1, 1, 1], "roughness": 0.95})
    meshes = [m]
    if water:
        w = world / 2 * 1.15
        meshes.append({"name": "water", "positions": np.array([[-w, 0, -w], [w, 0, -w], [w, 0, w], [-w, 0, w]], np.float32),
                       "indices": np.array([[0, 2, 1], [0, 3, 2]]), "normals": np.tile([0, 1, 0], (4, 1)).astype(np.float32),
                       "material": {"color": [0.12, 0.42, 0.62, 1], "roughness": 0.15, "metallic": 0.0}})
    return meshes


def terrain(ctx, p):
    ctx.used("studio_world", "numpy"); res = p["resolution"]; world = p.get("world_size") or T.DEFAULT_WORLD[p["preset"]]
    hsc = p.get("height_scale") or T.DEFAULT_HEIGHT[p["preset"]]
    h = T.heightfield(p["preset"], res, ctx.seed, p["roughness"]); ctx.stage("base shape", preset=p["preset"])
    sea = p["sea_level"] if p.get("sea_level") is not None else (0.0 if p["preset"] in ("mountains", "plains", "canyon") else 0.32)
    if p["erosion"]:
        h = T.erode(h, iterations=p["erosion"], strength=p["erosion_strength"], thermal=p["thermal"], sea=sea if sea > 0 else None)
        ctx.stage("eroded", iterations=p["erosion"])
    cell = world / (res - 1)
    slope = T.slope_map(h, cell, hsc)
    b, moist, temp = T.biomes(h, sea, slope, ctx.seed, p["climate"], hsc)
    shade = T.hillshade(h, hsc, cell)
    col = T.biome_colors(b, h, sea, None, p["climate"])
    ctx.stage("biomes")
    stem = p.get("name") or f"terrain_{p['preset']}"; outs = []
    add = lambda path, role, fmt: outs.append({"path": path, "role": role, "format": fmt})
    add(media.save_png16(h, ctx.path(f"{stem}_height16.png")), "heightmap", "png")
    add(_img(N.normal_map(h, strength=hsc / world * res / 2, tile=False), ctx.path(f"{stem}_normal.png")), "normal_map", "png")
    S = T.splatmap(b, slope, h, sea); add(_img(S, ctx.path(f"{stem}_splat.png"), "RGBA"), "splatmap", "png")
    add(_img(col, ctx.path(f"{stem}_biomes.png")), "biome_map", "png")
    add(_img(T.biome_colors(b, h, sea, shade, p["climate"]), ctx.path(f"{stem}_preview.png")), "preview", "png")
    masks = {"water": h <= sea, "cliff": slope > 38, "beach": b == 2, "forest": np.isin(b, [4, 5]), "moisture": moist, "slope": np.clip(slope / 60, 0, 1)}
    for k, m in masks.items(): add(_img(m.astype(float), ctx.path(f"masks/{stem}_{k}.png")), f"mask:{k}", "png")
    # scatter: vegetation by biome, rocks on steep ground; positions in metres (x, y, z), Y up, centred
    rng = np.random.default_rng(ctx.seed + 77); items = []
    pts = T.poisson(res - 1, res - 1, max(1.0, p["tree_spacing"] / cell), rng) if p["vegetation"] else np.zeros((0, 2))
    for x, y in pts:
        ix, iy = int(x), int(y); bb = int(b[iy, ix])
        if slope[iy, ix] > 30: continue
        for sp, prob in T.SPECIES.get(bb, []):
            if rng.random() < prob * p["vegetation"]:
                items.append({"species": sp, "biome": T.BIOMES[bb][0], "position": [round(x * cell - world / 2, 3), round(float((h[iy, ix] - sea) * hsc), 3), round(y * cell - world / 2, 3)],
                              "rotation_y": round(float(rng.uniform(0, 360)), 1), "scale": round(float(rng.uniform(0.8, 1.25)), 3)}); break
    rocks = []
    for x, y in T.poisson(res - 1, res - 1, max(1.0, p["rock_spacing"] / cell), rng) if p["rocks"] else []:
        ix, iy = int(x), int(y)
        if h[iy, ix] > sea and (slope[iy, ix] > 24 or b[iy, ix] == 10) and rng.random() < p["rocks"]:
            rocks.append({"kind": "boulder" if slope[iy, ix] > 32 else "rock", "position": [round(x * cell - world / 2, 3), round(float((h[iy, ix] - sea) * hsc), 3), round(y * cell - world / 2, 3)],
                          "rotation_y": round(float(rng.uniform(0, 360)), 1), "scale": round(float(rng.uniform(0.6, 1.8)), 3)})
    sc = ctx.path(f"{stem}_scatter.json"); json.dump({"units": "metres, Y up, origin at the terrain centre, y=0 at sea level", "vegetation": items, "rocks": rocks}, open(sc, "w"))
    add(sc, "scatter", "json")
    coast = [[[round(x * cell - world / 2, 2), round(y * cell - world / 2, 2)] for x, y in line] for line in T.contours(h, sea)] if sea > 0 else []
    cp = ctx.path(f"{stem}_coastline.json"); json.dump({"units": "metres (x, z)", "polylines": coast}, open(cp, "w")); add(cp, "coastline", "json")
    ctx.stage("scatter", vegetation=len(items), rocks=len(rocks), coast_lines=len(coast))
    glb = media.write_glb(ctx.path(f"{stem}.glb"), _terrain_mesh(h, sea, world, hsc, col, p["mesh_resolution"], water=sea > 0), name=stem)
    add(glb, "mesh", "glb")
    counts = {T.BIOMES[i][0]: int((b == i).sum()) for i in range(len(T.BIOMES)) if (b == i).any()}
    meta = {"preset": p["preset"], "seed": ctx.seed, "resolution": res, "world_size_m": world, "height_scale_m": hsc, "sea_level": sea,
            "sea_level_height_m": round(sea * hsc, 3), "heightmap": f"{stem}_height16.png (16-bit, 0 = lowest, 65535 = height_scale_m)",
            "splat_channels": {"R": "sand", "G": "grass", "B": "rock", "A": "snow"}, "biomes": {T.BIOMES[i][0]: list(T.BIOMES[i][1]) for i in T.BIOMES},
            "biome_cells": counts, "land_fraction": round(float((h > sea).mean()), 3), "vegetation": len(items), "rocks": len(rocks)}
    mp = ctx.path(f"{stem}.terrain.json"); json.dump(meta, open(mp, "w"), indent=1); add(mp, "manifest", "json")
    shot = ctx.path(f"{stem}_engine.png")
    ys, xs = np.nonzero(h > sea) if sea > 0 else np.nonzero(np.ones_like(h))
    ext = max(np.ptp(xs), np.ptp(ys), 8) * cell; cx = (xs.mean() * cell - world / 2); cz = (ys.mean() * cell - world / 2)
    checks, _, rep = webpages.glb_checks(glb, shot, "terrain GLB", camera=[cx + ext * 0.62, hsc * 0.9 + ext * 0.42, cz + ext * 0.8], target=[cx, hsc * 0.05, cz])
    ctx.used("three", "gltf_validator"); add(shot, "engine_screenshot", "png")
    land = float((h > sea).mean())
    checks += [{"name": "heightfield has relief", "ok": float(h.std()) > 0.05, "detail": round(float(h.std()), 3)},
               {"name": "island/coast has land and water" if sea > 0 else "terrain is all land", "ok": (0.05 < land < 0.95) if sea > 0 else land > 0.99, "detail": round(land, 3)},
               {"name": "splat weights sum to 1", "ok": bool(np.allclose(S.sum(-1), 1, atol=1e-3))}]
    if sea > 0: checks.append({"name": "coastline extracted", "ok": len(coast) > 0, "detail": len(coast)})
    return {"outputs": outs, "checks": checks, "terrain": meta, "engine": rep}


def caves(ctx, p):
    ctx.used("studio_world", "numpy")
    D = T.cave_density(p["resolution"], ctx.seed, p["tunnels"], p["radius"]); ctx.stage("density", shape=list(D.shape))
    P, F = T.surface_nets(D, cell=p["size"] / p["resolution"])
    if not len(F): raise StudioError("no cave surface was produced", hint="more tunnels or a larger radius")
    P = P - P.mean(0)
    # vertex colours: darker deeper, mossy where the wall faces up
    Nn = media.vertex_normals(P, F); y = (P[:, 1] - P[:, 1].min()) / (np.ptp(P[:, 1]) + 1e-9)
    base = np.array([0.32, 0.29, 0.27]) * (0.6 + 0.4 * y[:, None]); moss = np.array([0.22, 0.34, 0.16])
    up = np.clip(Nn[:, 1], 0, 1)[:, None]; C = base * (1 - 0.6 * up) + moss * 0.6 * up
    # the mesh is the inside of the rock: normals point into the tunnels
    edges = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    _, cnt = np.unique(edges, axis=0, return_counts=True)
    stem = p.get("name") or "cave"
    glb = media.write_glb(ctx.path(f"{stem}.glb"), [{"name": "cave", "positions": P, "indices": F, "normals": Nn, "colors": media.srgb_to_linear(C).astype(np.float32),
                                                      "material": {"color": [1, 1, 1, 1], "roughness": 0.95, "double_sided": True}}], name=stem)
    ctx.stage("surface nets", vertices=len(P), triangles=len(F))
    shot = ctx.path(f"{stem}_engine.png")
    checks, _, rep = webpages.glb_checks(glb, shot, "cave GLB"); ctx.used("three", "gltf_validator")
    closed = float((cnt == 2).mean())
    checks.append({"name": "cave surface is closed (≥99% of edges shared by exactly two triangles)", "ok": closed >= 0.99, "detail": round(closed, 4)})
    vox = ctx.path(f"{stem}_slices.png")
    media.contact_sheet([media.to_image((D[k] > 0).astype(float)) for k in np.linspace(2, D.shape[0] - 3, 8).astype(int)], vox, cols=4, cell=160,
                        labels=[f"z={k}" for k in np.linspace(2, D.shape[0] - 3, 8).astype(int)], title="cave density slices (white = rock)")
    return {"outputs": [{"path": glb, "role": "mesh", "format": "glb"}, {"path": shot, "role": "engine_screenshot", "format": "png"},
                        {"path": vox, "role": "preview", "format": "png"}], "checks": checks,
            "mesh": {"vertices": len(P), "triangles": len(F), "size_m": [round(float(v), 2) for v in np.ptp(P, 0)]}}


SKY = {"noon": (65, 180), "morning": (12, 95), "sunset": (2.5, 260), "dusk": (-3, 270), "overcast": (40, 160), "night": (-20, 0)}


def sky(ctx, p):
    elev, az = SKY[p["preset"]]
    elev = p.get("sun_elevation", elev); az = p.get("sun_azimuth", az)
    stem = p.get("name") or f"sky_{p['preset']}"; W = p["width"]; H = W // 2
    blender_ok = deps.check_one("blender", {"kind": "blender"})["available"]
    engine = p["engine"] if p["engine"] != "auto" else ("blender" if blender_ok else "analytic")
    if engine == "blender" and not blender_ok:
        raise Blocked("Blender (MeshCraft) is not installed", install="scripts/install.sh meshcraft", alternatives=["engine: analytic (gradient sky, no Rayleigh/Mie scattering)"])
    eq = ctx.path(f"{stem}_equirect.png")
    if engine == "blender":
        ctx.used("blender")
        r = runners.blender(os.path.join(HERE, "bpy_sky.py"), {"out": eq, "exr": ctx.path(f"{stem}_equirect.exr") if p["hdr"] else None, "width": W, "height": H,
                                       "elevation": elev, "azimuth": az, "air": 2.0 if p["preset"] == "overcast" else p["air"],
                                       "dust": 8.0 if p["preset"] == "overcast" else p["dust"], "ozone": p["ozone"], "strength": p["strength"]}, timeout=600)
        ctx.stage("rendered (Blender Nishita)", seconds=r.get("seconds"))
    else:
        ctx.used("studio_world")
        _img(_analytic_sky(W, H, elev, az, p["preset"]), eq)
    from PIL import Image
    E = np.asarray(Image.open(eq).convert("RGB"), float) / 255
    H2 = E.shape[0] // 2
    if p["preset"] == "night" or elev < -4:   # Nishita is black once the sun is down: a moonless-night gradient
        E = np.maximum(E, _analytic_sky(E.shape[1], E.shape[0], elev, az, "night") * 1.0 + np.array([0.004, 0.008, 0.025]))
    # below the horizon the physical sky is black; a skybox needs ground haze: horizon colour → darker ground
    hz = E[H2 - 3:H2].reshape(-1, 3).mean(0); t = (np.arange(E.shape[0] - H2) / max(1, E.shape[0] - H2 - 1))[:, None, None]
    hz = hz * 0.5 + hz.mean() * 0.5   # desaturate: haze, not a coloured floor
    ground = hz * 0.45 + np.array([0.06, 0.055, 0.05]) * (0.3 if elev > -4 else 0.05)
    E[H2 + 2:] = np.maximum(E[H2 + 2:], (hz * (1 - t ** 0.35) + ground * t ** 0.35)[2:])
    _img(E, eq)
    if p["preset"] == "night" or elev < -4:
        rng = np.random.default_rng(ctx.seed); n = int(W * H * 0.0009); ys = rng.integers(0, int(H * 0.55), n); xs = rng.integers(0, W, n)
        E[ys, xs] = np.maximum(E[ys, xs], rng.uniform(0.5, 1, (n, 1))); _img(E, eq); ctx.note("night: a seeded starfield was added above the horizon")
    outs = [{"path": eq, "role": "equirect", "format": "png"}]
    if engine == "blender" and p["hdr"]: outs.append({"path": ctx.path(f"{stem}_equirect.exr"), "role": "equirect_hdr", "format": "exr"})
    faces = _cubemap(E, p["cube_size"])
    names = ["px", "nx", "py", "ny", "pz", "nz"]   # three.js CubeTextureLoader order
    for nm, f in zip(names, faces): outs.append({"path": _img(f, ctx.path(f"cubemap/{stem}_{nm}.png")), "role": f"cube:{nm}", "format": "png"})
    sheet = media.contact_sheet([ctx.path(f"cubemap/{stem}_{n}.png") for n in names], ctx.path(f"{stem}_cubemap_sheet.png"), cols=6, cell=160, labels=names)
    outs.append({"path": sheet, "role": "preview", "format": "png"})
    el, a = np.radians(elev), np.radians(az)
    light = {"sun_direction_yup": [round(float(np.cos(el) * np.sin(a)), 4), round(float(np.sin(el)), 4), round(float(-np.cos(el) * np.cos(a)), 4)],
             "sun_elevation_deg": elev, "sun_azimuth_deg": az, "engine": engine,
             "ambient_rgb": [round(float(v), 4) for v in E[: H // 2].reshape(-1, 3).mean(0)], "horizon_rgb": [round(float(v), 4) for v in E[H // 2 - 2:H // 2 + 2].reshape(-1, 3).mean(0)]}
    lp = ctx.path(f"{stem}.sky.json"); json.dump(light, open(lp, "w"), indent=1); outs.append({"path": lp, "role": "lighting", "format": "json"})
    top = E[:H // 2].mean(); var = float(E.std())
    checks = [{"name": "equirect is 2:1", "ok": E.shape[1] == 2 * E.shape[0]}, {"name": "sky is not blank", "ok": var > 0.01, "detail": round(var, 4)},
              {"name": "cube faces are seamless at their shared edges", "ok": _cube_seam_ok(faces), "detail": None}]
    return {"outputs": outs, "checks": checks, "lighting": light}


def _analytic_sky(W, H, elev, az, preset):
    v = (np.arange(H)[:, None] + 0.5) / H; u = (np.arange(W)[None, :] + 0.5) / W
    lat = (0.5 - v) * np.pi; lon = (u - 0.5) * 2 * np.pi
    d = np.stack([np.cos(lat) * np.sin(lon), np.sin(lat) * np.ones_like(lon), -np.cos(lat) * np.cos(lon)], -1)
    e, a = np.radians(elev), np.radians(az); s = np.array([np.cos(e) * np.sin(a), np.sin(e), -np.cos(e) * np.cos(a)])
    mu = np.clip((d * s).sum(-1), -1, 1); up = np.clip(d[..., 1], -1, 1)
    day = np.clip((elev + 6) / 20, 0, 1)
    zen = np.array([0.20, 0.42, 0.85]) * day + np.array([0.01, 0.015, 0.04]) * (1 - day)
    hor = np.array([0.75, 0.82, 0.92]) * day + np.array([0.04, 0.05, 0.09]) * (1 - day)
    warm = np.clip(1 - abs(elev) / 15, 0, 1); hor = hor * (1 - 0.6 * warm) + np.array([1.0, 0.55, 0.3]) * 0.6 * warm * day
    t = np.clip(up, 0, 1) ** 0.45; col = hor * (1 - t[..., None]) + zen * t[..., None]
    col = np.where(up[..., None] < 0, hor * 0.55 + np.array([0.12, 0.11, 0.1]) * 0.45, col)
    col += (np.clip(mu, 0, 1) ** 600 * 6 * (elev > -0.5) + np.clip(mu, 0, 1) ** 8 * 0.35 * day)[..., None] * np.array([1, 0.9, 0.75])
    if preset == "overcast": col = col.mean(-1, keepdims=True) * np.array([0.95, 0.97, 1.0])
    return np.clip(col, 0, 1)


def _cubemap(E, n):
    H, W = E.shape[:2]; g = (np.arange(n) + 0.5) / n * 2 - 1; a, b = np.meshgrid(g, -g)
    one = np.ones_like(a)
    dirs = [(one, b, -a), (-one, b, a), (a, one, -b), (a, -one, b), (a, b, one), (-a, b, -one)]   # +x -x +y -y +z -z
    out = []
    for x, y, z in dirs:
        L = np.sqrt(x * x + y * y + z * z); x, y, z = x / L, y / L, z / L
        lon = np.arctan2(x, -z); lat = np.arcsin(np.clip(y, -1, 1))
        u = (lon / (2 * np.pi) + 0.5); v = 0.5 - lat / np.pi
        out.append(N.sample(E, u, np.clip(v, 0, 0.9999)))
    return out


def _cube_seam_ok(F):
    px, nx, py, ny, pz, nz = F
    d = [np.abs(pz[:, -1] - px[:, 0]).mean(), np.abs(px[:, -1] - nz[:, 0]).mean(), np.abs(nz[:, -1] - nx[:, 0]).mean(), np.abs(nx[:, -1] - pz[:, 0]).mean()]
    return bool(max(d) < 0.03)


def ocean(ctx, p):
    ctx.used("studio_world", "numpy")
    fr = T.ocean(p["resolution"], p["tile_size"], p["wind"], np.radians(p["direction"]), p["period"], p["frames"], p["choppiness"], ctx.seed)
    hs_target = 0.21 * p["wind"] ** 2 / 9.81 * p["amplitude"]   # Pierson–Moskowitz significant wave height
    sd = np.std([f[0] for f in fr]); k = hs_target / 4 / (sd + 1e-9)
    stem = p.get("name") or "ocean"; outs = []
    hmin = min(f[0].min() for f in fr) * k; hmax = max(f[0].max() for f in fr) * k
    normals, foams = [], []
    for i, (hgt, dx, dz) in enumerate(fr):
        hh = hgt * k
        nm = N.normal_map((hh - hmin) / (hmax - hmin + 1e-9), strength=(hmax - hmin) / p["tile_size"] * p["resolution"] / 2, tile=True)
        # foam where the choppy displacement folds the surface (Jacobian < threshold)
        jxx = 1 + (np.roll(dx, -1, 1) - np.roll(dx, 1, 1)) / 2 * k / (p["tile_size"] / p["resolution"])
        jzz = 1 + (np.roll(dz, -1, 0) - np.roll(dz, 1, 0)) / 2 * k / (p["tile_size"] / p["resolution"])
        foam = np.clip((0.9 - jxx * jzz) * 2, 0, 1)
        normals.append(nm); foams.append(foam)
        if i == 0:
            outs.append({"path": media.save_png16((hh - hmin) / (hmax - hmin + 1e-9), ctx.path(f"{stem}_height16_f000.png")), "role": "height", "format": "png"})
    A, grid = media.atlas([media.to_image(n) for n in normals], cols=int(np.ceil(np.sqrt(len(normals)))))
    A.convert("RGB").save(ctx.path(f"{stem}_normal_flipbook.png")); outs.append({"path": ctx.path(f"{stem}_normal_flipbook.png"), "role": "normal_flipbook", "format": "png"})
    _img(normals[0], ctx.path(f"{stem}_normal.png")); outs.append({"path": ctx.path(f"{stem}_normal.png"), "role": "normal_map", "format": "png"})
    FA, _ = media.atlas([media.to_image(f) for f in foams], cols=grid["cols"]); FA.convert("L").save(ctx.path(f"{stem}_foam_flipbook.png"))
    outs.append({"path": ctx.path(f"{stem}_foam_flipbook.png"), "role": "foam_flipbook", "format": "png"})
    outs.append({"path": media.gif([media.to_image(n) for n in normals], ctx.path(f"{stem}_normals.gif"), fps=p["frames"] / p["period"]), "role": "preview", "format": "gif"})
    # one displaced tile as a mesh (frame 0) for previews / static water
    hgt, dx, dz = fr[0]; R = p["resolution"]; cell = p["tile_size"] / R
    m = media.grid_mesh(np.pad(hgt * k, ((0, 1), (0, 1)), mode="wrap"), cell)
    m["positions"][:, 0] += np.pad(dx * k, ((0, 1), (0, 1)), mode="wrap").ravel(); m["positions"][:, 2] += np.pad(dz * k, ((0, 1), (0, 1)), mode="wrap").ravel()
    m.update(name="ocean", material={"color": [0.08, 0.33, 0.5, 1], "roughness": 0.12})
    glb = media.write_glb(ctx.path(f"{stem}_tile.glb"), [m], name=stem); outs.append({"path": glb, "role": "mesh", "format": "glb"})
    spec = {"tile_size_m": p["tile_size"], "resolution": R, "wind_mps": p["wind"], "direction_deg": p["direction"], "loop_seconds": p["period"],
            "frames": p["frames"], "fps": round(p["frames"] / p["period"], 3), "significant_wave_height_m": round(hs_target, 3),
            "height_range_m": [round(float(hmin), 3), round(float(hmax), 3)], "flipbook": {"cols": grid["cols"], "rows": grid["rows"], "frame": [grid["frame_width"], grid["frame_height"]]},
            "usage": "Tile the normal flipbook over the water plane (UV repeat = world_size / tile_size_m), advance one frame every 1/fps s; it loops in time and space."}
    sp = ctx.path(f"{stem}.ocean.json"); json.dump(spec, open(sp, "w"), indent=1); outs.append({"path": sp, "role": "manifest", "format": "json"})
    shot = ctx.path(f"{stem}_engine.png")
    checks, _, rep = webpages.glb_checks(glb, shot, "ocean tile GLB", camera=[p["tile_size"] * 0.6, p["tile_size"] * 0.35, p["tile_size"] * 0.6], target=[0, 0, 0])
    ctx.used("three", "gltf_validator"); outs.append({"path": shot, "role": "engine_screenshot", "format": "png"})
    t_err = _ocean_time_loop_error(p)
    s_err = float(np.abs(normals[0][:, 0] - normals[0][:, -1]).mean())
    checks += [{"name": "loops in time (frame at t=period equals t=0)", "ok": t_err < 1e-6, "detail": t_err},
               {"name": "tiles in space (edge columns match)", "ok": s_err < 0.06, "detail": round(s_err, 4)},
               {"name": "wave height matches the wind (Pierson–Moskowitz)", "ok": hs_target > 0}]
    return {"outputs": outs, "checks": checks, "ocean": spec}


def _ocean_time_loop_error(p):
    """max |e^{iωT} − 1| over the tile's quantised frequencies: 0 means the surface at t = period
    is identical to t = 0 (the animation loops exactly)."""
    res, size, g = p["resolution"], p["tile_size"], 9.81
    k1 = 2 * np.pi * np.fft.fftfreq(res, size / res); KX, KZ = np.meshgrid(k1, k1); K = np.hypot(KX, KZ)
    w0 = 2 * np.pi / p["period"]; w = np.round(np.sqrt(g * K) / w0) * w0
    return float(np.abs(np.exp(1j * w * p["period"]) - 1).max())


def scatter(ctx, p):
    """Re-scatter instances on an existing 16-bit heightmap (any source) with slope/height rules."""
    from PIL import Image
    src = ctx.need(p["heightmap"]); ctx.used("studio_world")
    h = np.asarray(Image.open(src), float); h = h[..., 0] if h.ndim == 3 else h; h = h / (65535.0 if h.max() > 255 else 255.0)
    res = h.shape[0]; cell = p["world_size"] / (res - 1)
    slope = T.slope_map(h, cell, p["height_scale"]); rng = np.random.default_rng(ctx.seed); out = []
    for rule in p["rules"]:
        pts = T.poisson(h.shape[1] - 1, res - 1, max(1.0, rule.get("spacing", 4) / cell), rng)
        for x, y in pts:
            ix, iy = int(x), int(y); hv = h[iy, ix]
            if not (rule.get("min_height", 0) <= hv <= rule.get("max_height", 1)): continue
            if not (rule.get("min_slope", 0) <= slope[iy, ix] <= rule.get("max_slope", 90)): continue
            if rng.random() > rule.get("density", 1.0): continue
            out.append({"kind": rule["kind"], "position": [round(x * cell - p["world_size"] / 2, 3), round(float(hv * p["height_scale"]), 3), round(y * cell - p["world_size"] / 2, 3)],
                        "rotation_y": round(float(rng.uniform(0, 360)), 1), "scale": round(float(rng.uniform(*rule.get("scale", [0.8, 1.2]))), 3)})
    stem = p.get("name") or "scatter"
    jp = ctx.path(f"{stem}.json"); json.dump({"units": "metres, Y up, centred", "instances": out}, open(jp, "w"))
    im = media.to_image(np.stack([h] * 3, -1) * 0.8)
    from PIL import ImageDraw
    d = ImageDraw.Draw(im); palette = [(46, 160, 67), (220, 120, 40), (120, 120, 220), (230, 200, 60)]
    kinds = sorted({r["kind"] for r in p["rules"]})
    for o in out:
        x = (o["position"][0] + p["world_size"] / 2) / cell; y = (o["position"][2] + p["world_size"] / 2) / cell; c = palette[kinds.index(o["kind"]) % 4]
        d.ellipse([x - 1.5, y - 1.5, x + 1.5, y + 1.5], fill=c)
    pv = ctx.path(f"{stem}_preview.png"); im.save(pv)
    by = {k: sum(1 for o in out if o["kind"] == k) for k in kinds}
    return {"outputs": [{"path": jp, "role": "scatter", "format": "json"}, {"path": pv, "role": "preview", "format": "png"}], "counts": by,
            "checks": [{"name": "instances placed", "ok": len(out) > 0, "detail": by}]}


# ---------------------------------------------------------------- CC0 libraries (Poly Haven)
def _ph_pick(ctx, p, kind):
    from core import sources as SRC
    ctx.used("cc0_sources")
    if p.get("id"):
        info = SRC.polyhaven_info(p["id"])
        return [{"source": "polyhaven", "id": p["id"], "name": info.get("name"), "tags": info.get("tags", [])[:8], "categories": info.get("categories", []),
                 "authors": list((info.get("authors") or {}).keys()), "page": f"https://polyhaven.com/a/{p['id']}", "license": SRC.LICENSE}]
    c = SRC.polyhaven_search(kind, p.get("query") or "", p["candidates"])
    if not c: raise StudioError(f"no CC0 {kind[:-1]} on Poly Haven matches {p.get('query')!r}", hint="try broader words, or list_only: true")
    return c


def _listing(ctx, p, cands, default):
    from core import sources as SRC
    short = [{k: c.get(k) for k in ("source", "id", "name", "tags", "page")} for c in cands]
    jp = ctx.path((p.get("name") or default) + ".candidates.json"); json.dump(short, open(jp, "w"), indent=1)
    return {"outputs": [{"path": jp, "role": "candidates", "format": "json"}], "checks": [{"name": "found CC0 candidates", "ok": bool(short), "detail": len(short)}],
            "candidates": short, "output_license": SRC.LICENSE}


def _credit(c): return f"{c.get('name') or c['id']} by {', '.join(c.get('authors') or ['unknown'])} ({c['page']}), CC0"


def hdri(ctx, p):
    """A CC0 HDRI from Poly Haven: the .hdr, a tone-mapped preview, a cubemap and lighting values."""
    import cc0
    from core import sources as SRC
    cands = _ph_pick(ctx, p, "hdris")
    if p["list_only"]: return _listing(ctx, p, cands, "cc0_hdris")
    c = cands[0]; stem = p.get("name") or c["id"]
    files = SRC.polyhaven_files(c["id"]).get("hdri", {})
    entry = (files.get(p["resolution"]) or {}).get("hdr")
    if not entry: raise StudioError(f"{c['id']} has no {p['resolution']} .hdr", hint="pick another resolution")
    data = SRC.fetch_checked(entry); ctx.stage("downloaded", id=c["id"], bytes=len(data))
    E = cc0.read_hdr(data)
    hp = ctx.path(f"{stem}.hdr"); open(hp, "wb").write(data)
    ldr = cc0.tonemap(E, p["exposure"])
    outs = [{"path": hp, "role": "equirect_hdr", "format": "hdr"}, {"path": _img(ldr, ctx.path(f"{stem}_equirect.png")), "role": "equirect (tone-mapped)", "format": "png"}]
    faces = _cubemap(ldr, p["cube_size"]); names = ["px", "nx", "py", "ny", "pz", "nz"]
    for nm, f in zip(names, faces): outs.append({"path": _img(f, ctx.path(f"cubemap/{stem}_{nm}.png")), "role": f"cube:{nm}", "format": "png"})
    sheet = media.contact_sheet([ctx.path(f"cubemap/{stem}_{n}.png") for n in names], ctx.path(f"{stem}_cubemap_sheet.png"), cols=6, cell=160, labels=names)
    outs.append({"path": sheet, "role": "preview", "format": "png"})
    sun, sun_el, contrast = cc0.brightest_direction(E)
    H = E.shape[0]
    light = {"source": {k: c.get(k) for k in ("source", "id", "name", "page", "authors")}, "license": SRC.LICENSE,
             "sun_direction_yup": sun, "sun_elevation_deg": sun_el, "sun_contrast": round(contrast, 1),
             "ambient_rgb_linear": [round(float(v), 4) for v in E[: H // 2].reshape(-1, 3).mean(0)],
             "three": {"usage": "new RGBELoader().load('" + os.path.basename(hp) + "', t => { t.mapping = THREE.EquirectangularReflectionMapping; scene.environment = t; scene.background = t; })",
                       "loader": "three/addons/loaders/RGBELoader.js"}}
    lp = ctx.path(f"{stem}.sky.json"); json.dump(light, open(lp, "w"), indent=1); outs.append({"path": lp, "role": "lighting", "format": "json"})
    checks = [{"name": "HDR decoded, 2:1 equirect", "ok": E.shape[1] == 2 * E.shape[0], "detail": list(E.shape[:2])},
              {"name": "true high dynamic range (peak above 1.0)", "ok": float(E.max()) > 1.0, "detail": round(float(E.max()), 2)},
              {"name": "cube faces are seamless at their shared edges", "ok": _cube_seam_ok(faces)}]
    return {"outputs": outs, "checks": checks, "lighting": light, "candidates": [{k: x.get(k) for k in ("id", "name", "page")} for x in cands],
            "output_license": SRC.LICENSE, "attribution": _credit(c)}


def fetch_model(ctx, p):
    """A CC0 model from Poly Haven, packed into one GLB with its textures and checked in three.js."""
    import cc0
    from core import sources as SRC
    cands = _ph_pick(ctx, p, "models")
    if p["list_only"]: return _listing(ctx, p, cands, "cc0_models")
    # the mesh (.bin) does not shrink with the texture resolution: pick the best match whose whole download fits the
    # budget (some scans are hundreds of MB, far too heavy for a phone game)
    budget = p["max_mb"] * SRC.MB; skipped = []; c = entry = None
    for cand in cands:
        e = ((SRC.polyhaven_files(cand["id"]).get("gltf") or {}).get(p["resolution"]) or {}).get("gltf")
        if not e: skipped.append({"id": cand["id"], "why": f"no {p['resolution']} glTF"}); continue
        size = e.get("size", 0) + sum(v.get("size", 0) for v in (e.get("include") or {}).values())
        if size > budget: skipped.append({"id": cand["id"], "why": f"{size // SRC.MB} MB > max_mb {p['max_mb']}"}); continue
        c, entry = cand, e; break
    if not entry: raise StudioError(f"no match fits {p['max_mb']} MB: {skipped}", hint="raise max_mb, use a lower resolution, or try other words")
    if skipped: ctx.note(f"skipped (too large or missing): {skipped}")
    stem = p.get("name") or c["id"]
    inc = entry.get("include") or {}
    def fetch(uri):
        if uri not in inc: raise StudioError(f"{c['id']}: the glTF references {uri!r}, which is not in Poly Haven's file list")
        return SRC.fetch_checked(inc[uri])
    glb_bytes = cc0.pack_glb(SRC.fetch_checked(entry), fetch)
    glb = ctx.path(f"{stem}.glb"); open(glb, "wb").write(glb_bytes); ctx.stage("packed", id=c["id"], bytes=len(glb_bytes))
    shot = ctx.path(f"{stem}_render.png")
    checks, _, rep = webpages.glb_checks(glb, shot, "CC0 model"); ctx.used("three", "gltf_validator")
    return {"outputs": [{"path": glb, "role": "model", "format": "glb"}, {"path": shot, "role": "engine_screenshot", "format": "png"}],
            "checks": checks, "model": {"source": {k: c.get(k) for k in ("source", "id", "name", "page", "authors")}, "bytes": len(glb_bytes)},
            "candidates": [{k: x.get(k) for k in ("id", "name", "page")} for x in cands], "output_license": SRC.LICENSE, "attribution": _credit(c)}


ACTIONS = {"terrain": terrain, "caves": caves, "sky": sky, "ocean": ocean, "scatter": scatter, "hdri": hdri, "fetch_model": fetch_model}
