"""LevelCraft: procedural levels exported as Tiled maps (TMJ, read by Phaser, Godot, Unity via
SuperTiled2Unity, Defold, Excalibur, Construct…) with an embedded generated tileset, entity /
collision / navigation object layers, a generic JSON, a preview and a 3D blockout GLB. Every map is
structurally validated, solved (connectivity or platformer reachability) and loaded in Phaser 3."""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import gen as G
from core import media, webpages
from core.contract import StudioError

ENT_COLORS = {"start": (60, 220, 90), "exit": (240, 80, 200), "enemy": (230, 60, 50), "enemy_camp": (230, 60, 50), "chest": (250, 200, 40), "coin": (250, 220, 60),
              "checkpoint": (80, 180, 250), "settlement": (255, 255, 255), "resource": (180, 140, 255), "building": (255, 160, 90), "well": (90, 160, 255), "market_stall": (255, 120, 160)}


def tileset_png(path, ts):
    from PIL import Image, ImageDraw
    n = len(G.TILES); cols = 8; rows = int(np.ceil(n / cols))
    im = Image.new("RGBA", (cols * ts, rows * ts), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, (name, rgb, sol) in G.TILES.items():
        x, y = (i % cols) * ts, (i // cols) * ts
        if name == "empty": continue
        d.rectangle([x, y, x + ts - 1, y + ts - 1], fill=rgb + (255,))
        dark = tuple(int(c * 0.75) for c in rgb) + (255,)
        if sol: d.rectangle([x, y, x + ts - 1, y + ts - 1], outline=dark)
        if name in ("wall", "rock", "building"): d.line([x, y + ts // 2, x + ts, y + ts // 2], fill=dark); d.line([x + ts // 2, y, x + ts // 2, y + ts // 2], fill=dark)
        if name == "water": d.line([x + 2, y + ts // 2, x + ts // 2, y + ts // 2 - 2, x + ts - 2, y + ts // 2], fill=(150, 200, 240, 255))
        if name == "forest": d.ellipse([x + 3, y + 3, x + ts - 4, y + ts - 4], fill=(28, 74, 38, 255))
        if name == "door": d.rectangle([x + ts // 4, y + 2, x + 3 * ts // 4, y + ts - 1], fill=(110, 66, 30, 255))
        if name == "spikes": d.polygon([(x + 1, y + ts - 1), (x + ts // 4, y + 3), (x + ts // 2, y + ts - 1), (x + 3 * ts // 4, y + 3), (x + ts - 1, y + ts - 1)], fill=(220, 220, 230, 255))
        if name == "road": d.point([(x + 3, y + 5), (x + 10, y + 11), (x + 6, y + 9)], fill=(140, 116, 84, 255))
    im.save(path); return {"columns": cols, "imagewidth": im.width, "imageheight": im.height, "tilecount": cols * rows}


def to_tiled(grid, ents, meta, tileset_name, ts_info, ts, collision, nav, nav_edges=None, side_view=False):
    h, w = grid.shape; oid = [1]

    def obj(name, typ, x, y, wd=0, ht=0, point=False, props=None):
        o = {"id": oid[0], "name": name, "type": typ, "x": x, "y": y, "width": wd, "height": ht, "rotation": 0, "visible": True}
        if point: o["point"] = True
        if props: o["properties"] = [{"name": k, "type": "int" if isinstance(v, int) and not isinstance(v, bool) else ("bool" if isinstance(v, bool) else "string"), "value": v if isinstance(v, (int, bool)) else json.dumps(v) if not isinstance(v, str) else v} for k, v in props.items()]
        oid[0] += 1; return o
    layers = [{"id": 1, "name": "tiles", "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0, "opacity": 1, "visible": True,
               "data": [int(t) + 1 if t != 0 else 0 for t in grid.ravel()]}]
    layers.append({"id": 2, "name": "entities", "type": "objectgroup", "draworder": "topdown", "opacity": 1, "visible": True, "x": 0, "y": 0,
                   "objects": [obj(e.get("name", e["type"]), e["type"], e["x"] * ts + ts / 2, e["y"] * ts + ts / 2, point=True,
                                   props={k: v for k, v in e.items() if k not in ("type", "x", "y", "name")}) for e in ents]})
    layers.append({"id": 3, "name": "collision", "type": "objectgroup", "draworder": "topdown", "opacity": 1, "visible": False, "x": 0, "y": 0,
                   "objects": [obj("solid", "collision", x * ts, y * ts, wd * ts, ht * ts) for x, y, wd, ht in collision]})
    layers.append({"id": 4, "name": "navigation", "type": "objectgroup", "draworder": "topdown", "opacity": 1, "visible": False, "x": 0, "y": 0,
                   "objects": [obj("walkable", "nav", x * ts, y * ts, wd * ts, ht * ts) for x, y, wd, ht in nav]})
    props = [{"name": "generator", "type": "string", "value": "GITCRAFT LevelCraft"}, {"name": "meta", "type": "string", "value": json.dumps(meta, default=str)}]
    if nav_edges is not None: props.append({"name": "platformer_nav_edges", "type": "string", "value": json.dumps(nav_edges)})
    return {"compressionlevel": -1, "type": "map", "version": "1.10", "tiledversion": "1.10.2", "orientation": "orthogonal", "renderorder": "right-down",
            "width": w, "height": h, "tilewidth": ts, "tileheight": ts, "infinite": False, "nextlayerid": 5, "nextobjectid": oid[0], "layers": layers, "properties": props,
            "tilesets": [{"firstgid": 1, "name": "levelcraft", "image": tileset_name, "imagewidth": ts_info["imagewidth"], "imageheight": ts_info["imageheight"],
                          "tilewidth": ts, "tileheight": ts, "columns": ts_info["columns"], "tilecount": ts_info["tilecount"], "margin": 0, "spacing": 0,
                          "tiles": [{"id": i, "properties": [{"name": "name", "type": "string", "value": v[0]}, {"name": "solid", "type": "bool", "value": v[2]}]} for i, v in G.TILES.items()]}]}


def preview(grid, ents, path, cell=8, edges=None):
    from PIL import Image, ImageDraw
    lut = np.array([G.TILES[i][1] for i in range(len(G.TILES))], np.uint8)
    im = Image.fromarray(lut[grid]).resize((grid.shape[1] * cell, grid.shape[0] * cell), Image.NEAREST); d = ImageDraw.Draw(im)
    for a, b, kind in (edges or [])[:4000]:
        if kind == "jump": d.line([(a[0] * cell + cell / 2, a[1] * cell + cell / 2), (b[0] * cell + cell / 2, b[1] * cell + cell / 2)], fill=(255, 255, 255))
    for e in ents:
        c = ENT_COLORS.get(e["type"], (255, 255, 255)); x, y = e["x"] * cell + cell / 2, e["y"] * cell + cell / 2; r = cell * (0.9 if e["type"] in ("start", "exit", "settlement") else 0.5)
        d.ellipse([x - r, y - r, x + r, y + r], fill=c, outline=(0, 0, 0))
    im.save(path); return path


def blockout(grid, path, ts_m=1.0, side_view=False, wall_h=2.5):
    """Collision rectangles → boxes; walkable regions → floor slabs. Top-down maps extrude up (Y);
    platformers extrude in depth (Z). Vertex colours from the tile palette."""
    S = G.solid(grid); h, w = grid.shape; meshes = []
    def box(x0, y0, z0, x1, y1, z1, rgb, name):
        P = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], np.float32)
        quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (1, 2, 6, 5), (3, 0, 4, 7)]
        V, F, C = [], [], []
        for q in quads:   # flat-shaded faces (own vertices)
            b = len(V); V += [P[i] for i in q]; F += [[b, b + 1, b + 2], [b, b + 2, b + 3]]
        c = media.srgb_to_linear(np.array(rgb) / 255)
        return np.array(V), np.array(F), np.tile(c, (len(V), 1))
    allV, allF, allC = [], [], []; off = 0
    def add(v, f, c):
        nonlocal off; allV.append(v); allF.append(f + off); allC.append(c); off += len(v)
    for tid in np.unique(grid):
        m = grid == tid
        if tid == 0 or tid == 17: continue
        rgb = G.TILES[int(tid)][1]
        for x, y, wd, ht in G.rects(m):
            if side_view:
                if not S[y, x]: continue
                add(*box(x * ts_m, (h - y - ht) * ts_m, -1.5, (x + wd) * ts_m, (h - y) * ts_m, 1.5, rgb, G.TILES[int(tid)][0]))
            else:
                top = wall_h if S[y, x] else (0.05 if tid != 4 else -0.2)
                add(*box(x * ts_m, -0.2, y * ts_m, (x + wd) * ts_m, top, (y + ht) * ts_m, rgb, G.TILES[int(tid)][0]))
    V = np.concatenate(allV); V[:, 0] -= w * ts_m / 2
    if side_view: V[:, 1] -= 0
    else: V[:, 2] -= h * ts_m / 2
    m = {"name": "blockout", "positions": V, "indices": np.concatenate(allF), "colors": np.concatenate(allC).astype(np.float32), "material": {"color": [1, 1, 1, 1], "roughness": 0.9}}
    return media.write_glb(path, [m], name="blockout")


def phaser_check(tmj, tileset, shot, ts):
    html = f"""<!doctype html><html><head><script src="http://gc.local/phaser/dist/phaser.min.js"></script></head><body style="margin:0;background:#111">
<script>
const R = {{ ok: false }};
const map_url = {json.dumps(webpages.file_url(tmj))}, ts_url = {json.dumps(webpages.file_url(tileset))};
class S extends Phaser.Scene {{
  preload() {{ this.load.tilemapTiledJSON('m', map_url); this.load.image('t', ts_url); }}
  create() {{
    try {{
      const map = this.make.tilemap({{ key: 'm' }}); const set = map.addTilesetImage('levelcraft', 't');
      const layer = map.createLayer('tiles', set, 0, 0);
      const scale = Math.min(this.scale.width / map.widthInPixels, this.scale.height / map.heightInPixels); this.cameras.main.setZoom(scale).centerOn(map.widthInPixels / 2, map.heightInPixels / 2);
      let tiles = 0; layer.forEachTile((t) => {{ if (t.index > 0) tiles++; }});
      const obj = {{}}; for (const L of map.objects) obj[L.name] = L.objects.length;
      const g = this.add.graphics(); const ents = map.getObjectLayer('entities').objects;
      for (const e of ents) {{ g.fillStyle(e.type === 'start' ? 0x3cdc5a : e.type === 'exit' ? 0xf050c8 : 0xffd040, 1); g.fillCircle(e.x, e.y, {ts} * 0.45); }}
      layer.setCollisionByProperty({{ solid: true }});
      let colliding = 0; layer.forEachTile((t) => {{ if (t.collides) colliding++; }});
      Object.assign(R, {{ ok: true, width: map.width, height: map.height, tiles, colliding_tiles: colliding, object_layers: obj, phaser: Phaser.VERSION }});
    }} catch (e) {{ R.error = String(e); }}
    this.time.delayedCall(150, () => {{ window.__report = R; window.__done = true; }});
  }}
}}
new Phaser.Game({{ type: Phaser.CANVAS, width: 960, height: 540, backgroundColor: '#14161c', scene: S, banner: false }});
</script></body></html>"""
    return webpages.run(html, shot, (960, 540))


def generate(ctx, p):
    ctx.used("studio_levels", "numpy"); rng = np.random.default_rng(ctx.seed); kind = p["kind"]; w, h = p["width"], p["height"]; edges = None
    if kind == "dungeon": grid, ents, meta = G.dungeon(w, h, rng, p["min_room"], p["enemies"], p["loot"])
    elif kind == "cave": grid, ents, meta = G.cave(w, h, rng, enemies=p["enemies"], loot=p["loot"])
    elif kind == "platformer":
        try: grid, ents, meta, edges = G.platformer(w, h, rng, p["jump_height"], p["jump_distance"], p["enemies"], p["loot"])
        except RuntimeError as e: raise StudioError(str(e))
    elif kind == "overworld": grid, ents, meta = G.overworld(w, h, rng, ctx.seed, p["settlements"], p["enemies"], p["loot"])
    elif kind == "settlement": grid, ents, meta = G.settlement(w, h, rng, p["block"], p["enemies"], p["loot"])
    ctx.stage("generated", kind=kind)
    side = kind == "platformer"; ts = p["tile_size"]; S = G.solid(grid)
    collision = G.rects(S); nav = G.rects(~S & (grid != 17)) if not side else []
    stem = p.get("name") or f"{kind}"; outs = []
    tsname = f"{stem}_tileset.png"; tsi = tileset_png(ctx.path(tsname), ts)
    nav_edges = [[list(a), list(b), k] for a, b, k in edges] if edges else None
    tm = to_tiled(grid, ents, meta, tsname, tsi, ts, collision, nav, nav_edges, side)
    tmj = ctx.path(f"{stem}.tmj"); json.dump(tm, open(tmj, "w"))
    outs += [{"path": tmj, "role": "tiled_map", "format": "tiled"}, {"path": ctx.path(tsname), "role": "tileset", "format": "png"}]
    generic = {"kind": kind, "width": w, "height": h, "tile_size": ts, "legend": {str(k): v[0] for k, v in G.TILES.items()}, "solid": [k for k, v in G.TILES.items() if v[2]],
               "rows": ["".join(chr(48 + int(t)) if t < 10 else chr(55 + int(t)) for t in row) for row in grid], "entities": ents,
               "collision_rects": collision, "nav_rects": nav, "meta": meta}
    gp = ctx.path(f"{stem}.level.json"); json.dump(generic, open(gp, "w"), default=str); outs.append({"path": gp, "role": "level_data", "format": "json"})
    outs.append({"path": preview(grid, ents, ctx.path(f"{stem}_preview.png"), 8 if max(w, h) <= 128 else 4, edges), "role": "preview", "format": "png"})
    ldtk_doc = None
    if "ldtk" in p["formats"]:
        import ldtk as LD
        ldtk_doc = LD.build(grid, ents, tsname, tsi, ts, name=stem.title().replace("_", ""))
        lp = ctx.path(f"{stem}.ldtk"); json.dump(ldtk_doc, open(lp, "w"), indent=1)
        outs.append({"path": lp, "role": "ldtk_project", "format": "json"}); ctx.used("ldtk_format")
    glb = blockout(grid, ctx.path(f"{stem}_blockout.glb"), 1.0, side); outs.append({"path": glb, "role": "blockout", "format": "glb"})
    ctx.stage("exported", collision_rects=len(collision), nav_rects=len(nav))
    # ---- verification
    checks = []
    st = next(e for e in ents if e["type"] == "start") if any(e["type"] == "start" for e in ents) else None
    walk = ~S
    if kind in ("dungeon", "cave"):
        ex = next(e for e in ents if e["type"] == "exit"); reach = G.flood(walk, (st["x"], st["y"]))
        checks.append({"name": "exit reachable from start", "ok": bool(reach[ex["y"], ex["x"]]), "detail": meta.get("path_length")})
        floor = walk & (grid != 0); checks.append({"name": "every floor tile connected", "ok": bool((reach | ~floor).all()), "detail": int((floor & ~reach).sum())})
        bad = [e for e in ents if S[e["y"], e["x"]]]; checks.append({"name": "no entity inside a wall", "ok": not bad, "detail": bad[:3]})
    elif kind == "platformer":
        seen, _ = G.reachable(grid, (st["x"], st["y"]), p["jump_height"], p["jump_distance"]); ex = next(e for e in ents if e["type"] == "exit")
        checks.append({"name": f"completable: exit reachable with jump {p['jump_height']}×{p['jump_distance']} tiles", "ok": (ex["x"], ex["y"]) in seen, "detail": meta["attempts"]})
        cps = [e for e in ents if e["type"] == "checkpoint"]; checks.append({"name": "checkpoints reachable", "ok": all((c["x"], c["y"]) in seen for c in cps), "detail": len(cps)})
    elif kind == "overworld":
        rd = np.isin(grid, [8, 15, 10, 16, 3]); towns = meta["towns"]
        if towns:
            r = G.flood(rd, towns[0]); checks.append({"name": "every settlement connected by road", "ok": all(r[y, x] for x, y in towns), "detail": meta["settlements"]})
        checks.append({"name": "has settlements", "ok": meta["settlements"] >= 2, "detail": meta["settlements"]})
    elif kind == "settlement":
        rd = np.isin(grid, [8, 16, 3]); r = G.flood(rd, (st["x"], st["y"]))
        doors = [e["door"] for e in ents if e["type"] == "building"]
        checks.append({"name": "every building door reaches the plaza by road", "ok": all(r[d[1], d[0]] for d in doors), "detail": len(doors)})
    v = G.solid(grid); cov = np.zeros_like(v)
    for x, y, wd, ht in collision: cov[y:y + ht, x:x + wd] = True
    checks.append({"name": "collision rectangles cover exactly the solid tiles", "ok": bool((cov == v).all()), "detail": len(collision)})
    if ldtk_doc is not None:
        import ldtk as LD
        errs = LD.validate(ldtk_doc)
        checks.append({"name": "LDtk project validates against the official LDtk 1.5.3 JSON schema", "ok": not errs, "detail": errs[:3]})
        rg, rs, re_ = LD.read_back(json.load(open(ctx.path(f"{stem}.ldtk"))))
        checks.append({"name": "LDtk read-back: tiles, collision and entities match the level", "ok": bool((rg == grid).all()) and bool((rs == v).all()) and len(re_) == len(ents),
                       "detail": {"tiles_equal": bool((rg == grid).all()), "collision_equal": bool((rs == v).all()), "entities": [len(re_), len(ents)]}})
    shot = ctx.path(f"{stem}_phaser.png"); r = phaser_check(tmj, ctx.path(tsname), shot, ts); rep = r.get("report") or {}
    ctx.used("phaser"); outs.append({"path": shot, "role": "engine_screenshot", "format": "png"})
    checks.append({"name": "loads in Phaser 3 (tilemap, tileset, object layers, solid-tile collision)",
                   "ok": bool(rep.get("ok")) and rep.get("tiles") == int((grid != 0).sum()) and rep.get("colliding_tiles") == int(v.sum()) and not r.get("errors"),
                   "detail": {k: rep.get(k) for k in ("phaser", "tiles", "colliding_tiles", "object_layers", "error")} | {"errors": (r.get("errors") or [])[:2]}})
    bshot = ctx.path(f"{stem}_blockout.png")
    cam = [0, h * 0.9, h * 0.95] if not side else [w * 0.15, h * 0.6, max(w, h) * 0.55]
    bc, _, brep = webpages.glb_checks(glb, bshot, "blockout GLB", camera=cam if not side else None, target=[0, 0, 0] if not side else None)
    ctx.used("three", "gltf_validator"); checks += bc; outs.append({"path": bshot, "role": "blockout_render", "format": "png"})
    counts = {}
    for e in ents: counts[e["type"]] = counts.get(e["type"], 0) + 1
    return {"outputs": outs, "checks": checks, "level": dict(meta, entities=counts), "phaser": rep}


ACTIONS = {"generate": generate}
