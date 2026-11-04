"""LDtk 1.5.3 project writer (LDtk: MIT, https://ldtk.io) and reader for verification.

One level with three layers (LDtk lists the top layer first):
  Entities   one entity definition per entity type (start, exit, enemy, chest, coin, settlement, …)
  Collision  IntGrid: 1 = solid (the same tiles as the Tiled map's collision rectangles)
  Tiles      Tiles layer on the generated tileset; each tile's id is the LevelCraft tile id
Validated against the official JSON schema (ldtk-1.5.3.schema.json, from the LDtk repository) and read back."""
import json, os, uuid
import gen as G

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ldtk-1.5.3.schema.json")


def _iid(): return str(uuid.uuid4())


def _hex(rgb): return "#%02X%02X%02X" % tuple(rgb)


def build(grid, ents, tileset_name, ts_info, ts, name="Level_0"):
    h, w = grid.shape; uid = [1]
    def nxt():
        uid[0] += 1; return uid[0]
    ts_uid, ent_layer_uid, col_uid, tile_uid, level_uid = nxt(), nxt(), nxt(), nxt(), nxt()
    cols = ts_info["columns"]
    from dept import ENT_COLORS
    types = sorted({e["type"] for e in ents})
    edefs = {t: {"identifier": t.title().replace("_", ""), "uid": nxt(), "tags": [], "exportToToc": False, "allowOutOfBounds": False, "doc": None,
                 "width": ts, "height": ts, "resizableX": False, "resizableY": False, "minWidth": None, "maxWidth": None, "minHeight": None, "maxHeight": None,
                 "keepAspectRatio": False, "tileOpacity": 1, "fillOpacity": 0.08, "lineOpacity": 1, "hollow": False, "color": _hex(ENT_COLORS.get(t, (255, 255, 255))),
                 "renderMode": "Ellipse", "showName": True, "tilesetId": None, "tileRenderMode": "FitInside", "tileRect": None, "uiTileRect": None,
                 "nineSliceBorders": [], "maxCount": 0, "limitScope": "PerLevel", "limitBehavior": "MoveLastOne", "pivotX": 0.5, "pivotY": 0.5, "fieldDefs": []}
             for t in types}
    def layerdef(ident, typ, luid, extra):
        d = {"__type": typ, "identifier": ident, "type": typ, "uid": luid, "doc": None, "uiColor": None, "gridSize": ts, "guideGridWid": 0, "guideGridHei": 0,
             "displayOpacity": 1, "inactiveOpacity": 1, "hideInList": False, "hideFieldsWhenInactive": True, "canSelectWhenInactive": True, "renderInWorldView": True,
             "pxOffsetX": 0, "pxOffsetY": 0, "parallaxFactorX": 0, "parallaxFactorY": 0, "parallaxScaling": True, "requiredTags": [], "excludedTags": [],
             "autoTilesKilledByOtherLayerUid": None, "uiFilterTags": [], "useAsyncRender": False, "intGridValues": [], "intGridValuesGroups": [], "autoRuleGroups": [],
             "autoSourceLayerDefUid": None, "tilesetDefUid": None, "tilePivotX": 0, "tilePivotY": 0, "biomeFieldUid": None}
        d.update(extra); return d
    defs = {"layers": [layerdef("Entities", "Entities", ent_layer_uid, {}),
                       layerdef("Collision", "IntGrid", col_uid, {"intGridValues": [{"value": 1, "identifier": "solid", "color": "#3A3440", "tile": None, "groupUid": 0}]}),
                       layerdef("Tiles", "Tiles", tile_uid, {"tilesetDefUid": ts_uid})],
            "entities": list(edefs.values()), "enums": [], "externalEnums": [], "levelFields": [],
            "tilesets": [{"__cWid": cols, "__cHei": ts_info["imageheight"] // ts, "identifier": "LevelCraft", "uid": ts_uid, "relPath": tileset_name, "embedAtlas": None,
                          "pxWid": ts_info["imagewidth"], "pxHei": ts_info["imageheight"], "tileGridSize": ts, "spacing": 0, "padding": 0, "tags": [], "tagsSourceEnumUid": None,
                          "enumTags": [], "customData": [{"tileId": i, "data": json.dumps({"name": v[0], "solid": v[2]})} for i, v in G.TILES.items()], "savedSelections": [], "cachedPixelData": None}]}
    lvl_iid = _iid()
    S = G.solid(grid)
    def inst(ident, typ, luid, **kw):
        d = {"__identifier": ident, "__type": typ, "__cWid": w, "__cHei": h, "__gridSize": ts, "__opacity": 1, "__pxTotalOffsetX": 0, "__pxTotalOffsetY": 0,
             "__tilesetDefUid": None, "__tilesetRelPath": None, "iid": _iid(), "levelId": level_uid, "layerDefUid": luid, "pxOffsetX": 0, "pxOffsetY": 0,
             "visible": True, "optionalRules": [], "intGridCsv": [], "autoLayerTiles": [], "seed": 0, "overrideTilesetUid": None, "gridTiles": [], "entityInstances": []}
        d.update(kw); return d
    ent_insts = []
    for e in ents:
        dfn = edefs[e["type"]]
        ent_insts.append({"__identifier": dfn["identifier"], "__grid": [int(e["x"]), int(e["y"])], "__pivot": [0.5, 0.5], "__tags": [], "__tile": None,
                          "__smartColor": dfn["color"], "__worldX": int(e["x"]) * ts + ts // 2, "__worldY": int(e["y"]) * ts + ts // 2, "iid": _iid(),
                          "width": ts, "height": ts, "defUid": dfn["uid"], "px": [int(e["x"]) * ts + ts // 2, int(e["y"]) * ts + ts // 2], "fieldInstances": []})
    tiles = []
    for y in range(h):
        for x in range(w):
            t = int(grid[y, x])
            if t == 0: continue
            tiles.append({"px": [x * ts, y * ts], "src": [(t % cols) * ts, (t // cols) * ts], "f": 0, "t": t, "d": [y * w + x], "a": 1})
    layers = [inst("Entities", "Entities", ent_layer_uid, entityInstances=ent_insts),
              inst("Collision", "IntGrid", col_uid, intGridCsv=[int(v) for v in S.ravel()]),
              inst("Tiles", "Tiles", tile_uid, gridTiles=tiles, __tilesetDefUid=ts_uid, __tilesetRelPath=tileset_name)]
    level = {"identifier": name, "iid": lvl_iid, "uid": level_uid, "worldX": 0, "worldY": 0, "worldDepth": 0, "pxWid": w * ts, "pxHei": h * ts,
             "__bgColor": "#14161C", "bgColor": None, "useAutoIdentifier": False, "bgRelPath": None, "bgPos": None, "bgPivotX": 0.5, "bgPivotY": 0.5,
             "__smartColor": "#8A8F99", "__bgPos": None, "externalRelPath": None, "fieldInstances": [], "layerInstances": layers, "__neighbours": []}
    return {"__header__": {"fileType": "LDtk Project JSON", "app": "LDtk", "doc": "https://ldtk.io/json", "schema": "https://ldtk.io/files/JSON_SCHEMA.json",
                           "appAuthor": "Sebastien 'deepnight' Benard", "appVersion": "1.5.3", "url": "https://ldtk.io"},
            "iid": _iid(), "jsonVersion": "1.5.3", "appBuildId": 473703, "nextUid": uid[0] + 1, "identifierStyle": "Capitalize", "toc": [],
            "worldLayout": "Free", "worldGridWidth": w * ts, "worldGridHeight": h * ts, "defaultLevelWidth": w * ts, "defaultLevelHeight": h * ts,
            "defaultPivotX": 0, "defaultPivotY": 0, "defaultGridSize": ts, "defaultEntityWidth": ts, "defaultEntityHeight": ts, "bgColor": "#14161C",
            "defaultLevelBgColor": "#14161C", "minifyJson": False, "externalLevels": False, "exportTiled": False, "simplifiedExport": False,
            "imageExportMode": "None", "exportLevelBg": True, "pngFilePattern": None, "backupOnSave": False, "backupLimit": 10, "backupRelPath": None,
            "levelNamePattern": "Level_%idx", "tutorialDesc": None, "customCommands": [], "flags": [], "defs": defs, "levels": [level], "worlds": [],
            "dummyWorldIid": _iid()}


def validate(doc):
    """Errors from the official LDtk 1.5.3 JSON schema (empty list = valid)."""
    import jsonschema
    schema = json.load(open(SCHEMA))
    v = jsonschema.Draft7Validator(schema)
    return [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:160]}" for e in v.iter_errors(doc)][:20]


def read_back(doc):
    """Rebuild (tile grid, solid mask, entity list) from an LDtk project, as a game loader would."""
    import numpy as np
    lvl = doc["levels"][0]; L = {li["__identifier"]: li for li in lvl["layerInstances"]}
    w, h = L["Tiles"]["__cWid"], L["Tiles"]["__cHei"]; ts = L["Tiles"]["__gridSize"]
    grid = np.zeros((h, w), int)
    for t in L["Tiles"]["gridTiles"]: grid[t["px"][1] // ts, t["px"][0] // ts] = t["t"]
    solid = np.array(L["Collision"]["intGridCsv"], int).reshape(h, w) == 1
    ents = [(e["__identifier"], e["__grid"][0], e["__grid"][1]) for e in L["Entities"]["entityInstances"]]
    return grid, solid, ents
