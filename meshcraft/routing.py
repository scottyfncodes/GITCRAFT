"""Intelligent tool routing for the 3D Department.

route(brief, images=[], probe=None) → a plan: the parsed request, every candidate tool
with whether it is available on *this* machine and why, the chosen tool, and fallbacks.
The plan never substitutes a 2D image for a requested 3D model: when nothing that can
honour the request is available, `chosen` is None and `alternatives` lists what could
be done instead, each clearly labelled with how it differs from the request."""
import hashlib, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, "rules.json")))
COLORS = {"red": "crimson", "crimson": "crimson", "scarlet": "crimson", "blue": "sea", "navy": "midnight", "teal": "lagoon",
          "aqua": "aqua", "green": "palm", "seafoam": "#4fb39a", "gold": "gold", "golden": "gold", "yellow": "gold", "black": "black",
          "white": "cream", "cream": "cream", "purple": "dusk", "orange": "amber", "pink": "hibiscus", "brown": "timber",
          "coral": "coral", "copper": "copper", "grey": "stone", "gray": "stone"}


def _has(text, words):
    return any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) for w in words)


IMG_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".exr", ".webp")


def expand_images(images):
    """Folders count as every image inside them."""
    out = []
    for p in images or []:
        if os.path.isdir(p): out += sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(IMG_EXT))
        else: out.append(p)
    return out


def parse(brief, images=()):
    images = expand_images(images)
    t = (brief or "").lower()
    intents = sorted(k for k, v in RULES["intents"].items() if _has(t, v["words"]))
    kind = next((k for k, words in RULES["kinds"].items() if _has(t, words)), None)
    # "boat upgrade" / "sail for the boat" → upgrade beats boat
    if kind == "boat" and _has(t, RULES["kinds"]["upgrade"] + ["upgrade", "component", "module"]): kind = "upgrade"
    if kind == "boat" and _has(t, RULES["kinds"]["salvage"]): kind = "salvage"
    if kind is None and "character" in intents: kind = "character"
    params = {"seed": int(hashlib.sha1(t.encode()).hexdigest()[:6], 16) % 1000}

    def color_before(noun):
        m = re.search(r"([a-z]+)[ -](?:\w+ )?" + noun, t)
        return COLORS.get(m.group(1)) if m else None
    if kind == "boat":
        params["vessel"] = "dinghy" if _has(t, ["dinghy", "rowboat", "skiff"]) else "sloop"
        hull = color_before("hull"); sail = color_before("sails?")
        if hull: params["paint"] = [hull, "#f2ead8"]
        if sail: params["sail_colors"] = ["#f1e6cc", sail]
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
    if "crab" in t: params["bb_template"] = "crab"
    name = re.sub(r"\s+", " ", (brief or "asset").strip())[:60]
    return {"brief": brief, "intents": intents, "kind": kind, "params": params, "images": len(images or []), "name": name}


def _cond(expr, req):
    def atom(a):
        a = a.strip()
        if a == "true": return True
        m = re.match(r"images>=(\d+)$", a)
        if m: return req["images"] >= int(m.group(1))
        if a.startswith("intent:"): return a[7:] in req["intents"]
        if a == "kind:known": return req["kind"] is not None
        if a.startswith("kind:"): return req["kind"] == a[5:]
        raise ValueError(f"bad rule atom {a}")
    return any(all(atom(x) for x in clause.split(" and ")) for clause in expr.split(" or "))


def tool_status(tool, req, probe):
    spec = RULES["tools"][tool]; be = probe["backends"].get(spec["backend"], {})
    if not be.get("available"):
        return False, be.get("reason") or f"{spec['backend']} is not installed"
    if tool == "blender_procedural" and req["kind"] not in spec["kinds"]:
        return False, f"no procedural template for '{req['kind'] or 'this description'}'"
    if tool == "blockbench":
        from backends import blockbench
        tpl = blockbench.template_for(req)
        if not tpl: return False, "no Blockbench template for this kind of object"
    if tool == "triposr" and req["images"] < 1: return False, "TripoSR needs a reference image"
    if tool == "meshroom" and req["images"] < 3: return False, "photogrammetry needs several overlapping photos (≥8 recommended)"
    if tool == "meshroom":
        ram = probe["hardware"]["ram"]["total_gb"]
        if ram < probe["limits"]["meshroom_min_ram_gb"]: return False, f"Meshroom needs ≥{probe['limits']['meshroom_min_ram_gb']} GB RAM, this machine has {ram}"
    return True, spec["compute"]


def route(brief, images=(), probe=None, prefer=None):
    if probe is None:
        import hardware; probe = hardware.probe()
    req = parse(brief, images)
    rt = next(r for r in RULES["routes"] if _cond(r["when"], req))
    order = list(rt["tools"])
    if prefer:
        if prefer not in RULES["tools"]: raise ValueError(f"unknown tool {prefer}; choose from {sorted(RULES['tools'])}")
        order = [prefer] + [t for t in order if t != prefer]
    cands = []
    for t in order:
        ok, why = tool_status(t, req, probe)
        cands.append({"tool": t, "label": RULES["tools"][t]["label"], "available": ok, "detail": why})
    chosen = next((c["tool"] for c in cands if c["available"]), None)
    plan = {"request": req, "route": rt["id"], "why": rt["why"], "candidates": cands, "chosen": chosen,
            "preferred": order[0], "fallback_used": chosen is not None and chosen != order[0]}
    if chosen is None:
        plan["explanation"] = ("None of the tools that can honour this request are available here: " +
                               "; ".join(f"{c['label']}: {c['detail']}" for c in cands) +
                               ". MeshCraft will not substitute a 2D image or an unrelated model.")
        alts = []
        if req["images"] and req["kind"] in RULES["tools"]["blender_procedural"]["kinds"]:
            alts.append({"tool": "blender_procedural", "note": f"Build a stylized {req['kind']} procedurally from the text instead. It will NOT be derived from your image."})
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


if __name__ == "__main__":
    import sys
    print(json.dumps(route(" ".join(sys.argv[1:]) or "stylized low-poly boat"), indent=1))
