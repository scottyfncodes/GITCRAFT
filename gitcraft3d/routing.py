"""Routing for the 3D Department (owner: ForgeCraft). Standard library only.

route(brief, images, probe) → a plan: the parsed request (kind, MeshCraft template, params),
every candidate tool with whether it is available on *this* machine and why, the chosen tool
and the fallbacks. advice() presents the same decision in MeshCraft's `route` format, so
MeshCraft's tool and ForgeCraft never disagree.

A 2D image is never substituted for a requested 3D model: when nothing that can honour the
request is available, `chosen` is None and `alternatives` say how each differs from the request."""
import hashlib, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, "rules.json")))
COLORS = {"red": "crimson", "crimson": "crimson", "scarlet": "crimson", "blue": "sea", "navy": "midnight", "teal": "lagoon",
          "aqua": "aqua", "green": "palm", "seafoam": "#4FB39A", "gold": "gold", "golden": "gold", "yellow": "gold", "black": "black",
          "white": "cream", "cream": "cream", "purple": "dusk", "orange": "amber", "pink": "hibiscus", "brown": "timber",
          "coral": "coral", "copper": "copper", "grey": "stone", "gray": "stone"}
IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".webp")


def canonical_tool(t): return RULES["aliases"].get(t, t) if t else t


def expand_images(images):
    """Folders count as every image inside them."""
    out = []
    for p in images or []:
        if os.path.isdir(p): out += sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(IMG_EXT))
        else: out.append(p)
    return out


def _has(text, words):
    return [w for w in words if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text)]


def parse(brief, images=()):
    images = expand_images(images)
    t = (brief or "").lower()
    intents = sorted(k for k, v in RULES["intents"].items() if _has(t, v["words"]))
    kind = next((k for k, words in RULES["kinds"].items() if _has(t, words)), None)
    if kind == "boat" and _has(t, RULES["kinds"]["upgrade"] + ["upgrade", "component", "module"]): kind = "upgrade"
    if kind == "boat" and _has(t, RULES["kinds"]["salvage"]): kind = "salvage"
    if kind is None and "character" in intents: kind = "character"
    params = {"seed": int(hashlib.sha1(t.encode()).hexdigest()[:6], 16) % 1000}

    def color_before(noun):
        m = re.search(r"([a-z]+)[ -](?:\w+ )?" + noun, t)
        return COLORS.get(m.group(1)) if m else None
    if kind == "boat":
        params["vessel"] = "dinghy" if _has(t, ["dinghy", "rowboat", "skiff", "lifeboat"]) else "sloop"
        hull, sail = color_before("hull"), color_before("sails?")
        if hull: params["paint"] = [hull, "#F2EAD8"]
        if sail: params["sail_colors"] = ["#F1E6CC", sail]
    elif kind == "upgrade":
        params["upgrade"] = next((u for u, w in RULES["upgrade_words"].items() if _has(t, w)), "cargo_crate")
    elif kind == "prop":
        params["prop"] = next((u for u, w in RULES["prop_words"].items() if _has(t, w)), "barrel")
    elif kind == "island":
        params["radius"] = 30 if _has(t, ["large", "big", "huge"]) else 15 if _has(t, ["small", "tiny", "little"]) else 22
        params["palms"] = 2 if _has(t, ["barren", "rocky"]) else 9 if _has(t, ["jungle", "lush", "forest"]) else 7
    elif kind == "character":
        cols = {k: c for k in ("vest", "shirt", "bandana", "pants") if (c := color_before(k))}
        if cols: params["colors"] = cols
        params["weapon"] = not _has(t, ["unarmed", "no sword", "civilian"])
    # which MeshCraft template: a named one (chest, crab, …) beats a generic kind template
    named = next((k for k, w in RULES["meshcraft_templates"].items() if _has(t, w)), None) if kind in (None, "prop") else None
    template = named or RULES["kind_templates"].get(kind)
    if template != "prop": params.pop("prop", None)
    name = re.sub(r"\s+", " ", (brief or "asset").strip())[:60]
    return {"brief": brief, "intents": intents, "kind": kind, "template": template, "params": params,
            "images": len(images), "name": name}


def _cond(expr, req):
    def atom(a):
        a = a.strip()
        if a == "true": return True
        m = re.match(r"images>=(\d+)$", a)
        if m: return req["images"] >= int(m.group(1))
        if a.startswith("intent:"): return a[7:] in req["intents"]
        if a == "kind:known": return req["kind"] is not None
        if a == "template:any": return bool(req.get("template"))
        if a.startswith("kind:"): return req["kind"] == a[5:]
        raise ValueError(f"bad rule atom {a}")
    return any(all(atom(x) for x in clause.split(" and ")) for clause in expr.split(" or "))


def blockbench_template(req):
    bb = RULES["blockbench_templates"]; t = (req.get("brief") or "").lower()
    if req.get("template") in bb: return req["template"]
    if req["kind"] == "boat": return "boat"
    if req["kind"] == "salvage": return "crate"
    if req["kind"] == "prop": return {"crate": "crate", "barrel": "crate"}.get(req["params"].get("prop"))
    return next((n for n in bb if n in t), None)


def tool_status(tool, req, probe):
    spec = RULES["tools"][tool]; be = probe["backends"].get(spec["backend"], {})
    if not be.get("available"):
        return False, be.get("reason") or f"{spec['backend']} is not installed"
    if tool == "meshcraft_template":
        if not req.get("template"): return False, "no MeshCraft template matches this request"
        if req["template"] not in be.get("templates", []): return False, f"MeshCraft has no `{req['template']}` template"
    if tool == "blockbench" and not blockbench_template(req): return False, "no Blockbench template for this kind of object"
    if tool == "triposr" and req["images"] < 1: return False, "TripoSR needs a reference image"
    if tool == "meshroom":
        if req["images"] < 3: return False, "photogrammetry needs several overlapping photos (≥8 recommended)"
        ram = probe["ram"]["total_gb"] or 0
        if ram < probe["limits"]["meshroom_min_ram_gb"]: return False, f"Meshroom needs ≥{probe['limits']['meshroom_min_ram_gb']} GB RAM, this machine has {ram}"
    return True, spec["compute"]


def route(brief, images=(), probe=None, prefer=None, kind=None, params=None, template=None):
    if probe is None:
        from . import hardware; probe = hardware.probe()
    req = parse(brief, images)
    if kind:   # an explicit kind/template from the caller beats keyword parsing
        req["kind"] = kind; req["template"] = RULES["kind_templates"].get(kind, req["template"] if kind == "prop" else None)
    if template: req["template"] = template
    if params: req["params"].update(params)
    rt = next(r for r in RULES["routes"] if _cond(r["when"], req))
    order = list(rt["tools"]); prefer = canonical_tool(prefer)
    if prefer:
        if prefer not in RULES["tools"]: raise ValueError(f"unknown tool {prefer}; choose from {sorted(RULES['tools'])}")
        order = [prefer] + [t for t in order if t != prefer]
    cands = []
    for t in order:
        ok, why = tool_status(t, req, probe)
        cands.append({"tool": t, "label": RULES["tools"][t]["label"], "owner": RULES["tools"][t]["owner"], "available": ok, "detail": why})
    chosen = next((c["tool"] for c in cands if c["available"]), None)
    plan = {"request": req, "route": rt["id"], "why": rt["why"], "candidates": cands, "chosen": chosen,
            "preferred": order[0], "fallback_used": chosen is not None and chosen != order[0]}
    if chosen is None:
        plan["explanation"] = ("None of the tools that can honour this request are available here: " +
                               "; ".join(f"{c['label']}: {c['detail']}" for c in cands) +
                               ". The department will not substitute a 2D image or an unrelated model.")
        alts = []
        if req["images"] and req.get("template"):
            alts.append({"tool": "meshcraft_template", "note": f"Model a stylized {req['template']} with MeshCraft instead. It will NOT be derived from your image: the image only guides proportions and colour."})
        elif req["images"]:
            alts.append({"tool": "meshcraft_template / blockbench", "note": "Model it with a MeshCraft template or Blockbench using the image as a reference. It will NOT be derived from the image."})
        if req["images"] and probe["backends"]["meshroom"].get("available") and req["images"] < 8:
            alts.append({"tool": "meshroom", "note": "Shoot 20–60 overlapping photos of the object and run photogrammetry."})
        for t in ("triposr", "hunyuan3d"):
            if not probe["backends"][t].get("available"):
                alts.append({"tool": t, "note": f"Enable {RULES['tools'][t]['label']}: {probe['backends'][t].get('reason')}"})
        plan["alternatives"] = alts
    elif plan["fallback_used"]:
        first = cands[0]
        plan["explanation"] = f"Preferred {first['label']} is unavailable ({first['detail']}); using {RULES['tools'][chosen]['label']}."
    else:
        plan["explanation"] = rt["why"]
    return plan


def advice(request, images=0, probe=None):
    """The routing decision in MeshCraft's `route` format (advice only; nothing is built)."""
    if probe is None:
        from . import hardware; probe = hardware.probe()
    p = route(request, ["image"] * int(images or 0), probe)
    req, out = p["request"], {"request": request, "advice_only": True, "decided_by": "gitcraft3d/routing.py (ForgeCraft's router)",
                              "plan": {k: p[k] for k in ("route", "chosen", "candidates", "explanation")}}
    if p["route"] == "photogrammetry":
        c = probe["capabilities"]["photogrammetry"]
        return dict(out, route="photogrammetry", available=c["available"], reason=c.get("reason"), tools=["forgecraft photogrammetry"],
                    alternatives=[{"route": "template or run_script", "note": "modelled by hand from the photos as reference: NOT reconstructed from them"}])
    if p["route"] in ("concept_image", "photo_image"):
        c = probe["capabilities"]["image_to_3d"]
        return dict(out, route="image_to_3d", available=c["available"], reason=c.get("reason"), tools=["forgecraft generate (with the image)"],
                    alternatives=[{"route": "template / Blockbench with the image as a reference", "note": "NOT derived from the image: the image only guides proportions and colour"}])
    if p["route"] == "voxel" or p["chosen"] == "blockbench":
        return dict(out, route="blockbench", available=True, template=blockbench_template(req),
                    tools=["blockbench_build", "(edit in Blockbench)", "blockbench_import"], why=p["why"])
    if p["route"] == "scene":
        return dict(out, route="scene", available=probe["backends"]["meshcraft"]["available"], tools=["compose_scene"], why=p["why"])
    if p["chosen"] == "meshcraft_template":
        tools = ["run_pipeline"] + (["mixamo_prepare_upload", "(mixamo.com)", "mixamo_apply"] if req["template"] == "deckhand" and "animated" in req["intents"] else [])
        return dict(out, route="template", template=req["template"], params=req["params"], available=True, tools=tools, why=p["why"])
    return dict(out, route="run_script", available=probe["backends"]["meshcraft"]["available"], tools=["run_script", "export_asset", "engine_check"],
                why="no template matches: model it with a Blender script in the workspace (assisted modelling), or extend a template"
                    + ("" if not p["chosen"] else f"; {RULES['tools'][p['chosen']]['label']} can also generate it"))
