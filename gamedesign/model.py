"""Phase 2, the game model: GAME → WORLDS → LEVELS → MISSIONS → OBJECTIVES → ENCOUNTERS → CHARACTERS → STORY → PROGRESSION.

The evidence bundle (extract/repo.py) is a pile of named collections. This module decides what each one IS by
its shape (keys present across its items), its name and its TypeScript type, normalises the ones it recognises
into DESIGNCRAFT entities, and links them. Every entity keeps `ev`: the file, line and symbol it came from.
Collections it cannot place are listed as `unclassified`, and anything missing is listed as a limitation —
nothing is invented to fill a gap."""
import math, re
from collections import Counter

TYPES = ("mission", "questchain", "place", "world", "character", "story", "encounter", "progression", "stage")

NAME_HINTS = {
    "mission": ["mission", "quest", "job", "contract", "task", "challenge", "errand", "assignment", "bounty", "call", "objective"],
    "questchain": ["voyage", "tutorial", "onboarding", "chain", "first", "steps", "guide", "intro"],
    "place": ["level", "map", "place", "island", "area", "room", "site", "location", "poi", "pois", "settlement", "outpost", "landmark",
              "structure", "dungeon", "pad", "pads", "village", "peak", "spot", "spots", "station", "town", "district", "zone", "salvage"],
    "world": ["region", "world", "era", "chapter", "act", "biome", "district", "zone", "realm"],
    "character": ["cast", "character", "npc", "npcs", "crew", "people", "person", "villager", "companion", "castaway", "castaways", "hero", "heroes"],
    "story": ["dialogue", "dialog", "line", "lines", "bark", "barks", "radio", "story", "beat", "beats", "script", "cutscene", "ending", "endings",
              "clue", "clues", "thread", "threads", "lore", "codex", "talk", "conversation", "message", "log", "journal", "note", "deduction", "deductions", "voice", "look", "looks"],
    "encounter": ["enemy", "enemies", "archetype", "archetypes", "monster", "monsters", "foe", "raider", "raiders", "boss", "mob", "creature", "species", "predator", "threat", "hazard"],
    "progression": ["upgrade", "upgrades", "unlock", "unlocks", "milestone", "milestones", "achievement", "achievements", "badge", "badges", "trait", "traits",
                    "perk", "perks", "skill", "skills", "rank", "ranks", "recipe", "recipes", "tech", "goal", "goals", "form", "forms", "cosmetic", "cosmetics", "vessel", "vessels", "item", "items", "gift", "gifts"],
    "stage": ["wave", "waves", "night", "nights", "levels", "eras", "stage", "stages", "round", "rounds", "tier", "tiers", "difficulty", "escalation"],
}
KEY_HINTS = {
    "mission": {"steps": 3, "stages": 3, "objectives": 3, "objective": 2, "tasks": 2, "brief": 2, "briefing": 2, "reward": 1.5, "rewards": 1.5,
                "requires": 1, "prerequisites": 1, "alert": 1, "threat": 1, "giver": 1.5, "from": 0.5, "done": 0.5, "fail": 1, "quest": 1, "target": 0.5, "family": 0.5},
    "questchain": {"text": 1.5, "hint": 2.5, "check": 1, "help": 1},
    "place": {"x": 1.5, "z": 1, "y": 0.5, "pos": 1.5, "position": 1.5, "region": 1.5, "r": 0.5, "radius": 1, "landmarks": 2, "caches": 2, "finds": 2,
              "blurb": 1, "biome": 2, "style": 0.5, "name": 0.5, "rooms": 2, "spawn": 1, "loot": 1},
    "world": {"name": 1, "subtitle": 1, "blurb": 1, "danger": 1, "color": 0.5, "index": 0.5, "numeral": 1, "playable": 1},
    "character": {"role": 2, "bio": 2, "personality": 2, "voice": 1.5, "faction": 1.5, "backstory": 2, "perk": 1, "age": 1, "home": 1, "portrait": 1,
                  "name": 1, "greeting": 2, "lines": 1, "mood": 1},
    "story": {"text": 1.5, "lines": 2, "line": 2, "speaker": 2, "who": 1.5, "body": 1.5, "question": 1.5, "answered": 1.5, "say": 1.5, "phase": 0.5,
              "thread": 1, "beat": 1, "headline": 1, "caption": 1, "message": 1, "trigger": 1, "epilogue": 2, "clue": 1.5},
    "encounter": {"hp": 2, "health": 2, "resolve": 1.5, "damage": 2, "dmg": 2, "attack": 1.5, "armor": 1, "speed": 1, "walk": 1, "run": 1, "stun": 1,
                  "knockback": 1, "aggro": 1, "fear": 1, "steal": 1, "spawn": 1},
    "progression": {"cost": 2, "price": 2, "unlock": 1.5, "unlocks": 1.5, "requires": 1, "tier": 1.5, "xp": 1.5, "cond": 1.5, "reward": 1, "gold": 1,
                    "dna": 1, "cosmetic": 1, "slot": 1, "rank": 1, "threshold": 1.5, "min": 0.5, "effect": 1, "perk": 1, "rarity": 1, "category": 0.5},
    "stage": {"spawns": 2.5, "wave": 1, "night": 1, "count": 0.5, "index": 0.5, "number": 0.5, "duration": 1, "breather": 1.5, "growthNeeded": 2, "difficulty": 1.5},
}
STR_KEYS_NAME = ("name", "title", "label", "headline", "id")
STR_KEYS_TEXT = ("text", "body", "brief", "briefing", "desc", "description", "blurb", "line", "say", "answered", "question", "subtitle", "done", "alert", "hint", "greeting", "caption", "message", "lines", "epilogue", "pitch", "bio")
OBJ_LIST_KEYS = ("steps", "stages", "objectives", "tasks", "goals", "objective")
NUMERIC = (int, float)


def _isnum(v): return isinstance(v, NUMERIC) and not isinstance(v, bool)


def _tokens(s):
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", s or "")
    return [t for t in re.split(r"[^a-zA-Z]+", s.lower()) if t]


def _clean(v):
    """Drop parser bookkeeping for display."""
    if isinstance(v, dict): return {k: _clean(x) for k, x in v.items() if k not in ("_L", "_doc")}
    if isinstance(v, list): return [_clean(x) for x in v]
    return v


class Resolver:
    """Resolve $ref and id-lookup $call markers against literals found elsewhere in the repository."""

    def __init__(self, bundle):
        self.sym = bundle["symbols"]
        self.by_id = {}
        for c in bundle["collections"]:
            if c["kind"] not in ("array", "record"): continue
            for k, it in c["items"]:
                iid = it.get("id") if isinstance(it.get("id"), str) else (k if isinstance(k, str) and k else None)
                if iid and iid not in self.by_id: self.by_id[iid] = it

    def __call__(self, v, file=None, depth=0):
        if depth > 3 or not isinstance(v, dict): return v
        if "$ref" in v:
            name = v["$ref"].split(".")[0]
            cands = self.sym.get(name) or []
            pick = next((val for f, val in cands if f == file), None) if file else None
            if pick is None and len(cands) == 1: pick = cands[0][1]
            if pick is not None and not (isinstance(pick, dict) and ("$expr" in pick or "$call" in pick)):
                if "." in v["$ref"] and isinstance(pick, dict):
                    for part in v["$ref"].split(".")[1:]:
                        pick = pick.get(part) if isinstance(pick, dict) else None
                return self(pick, file, depth + 1) if isinstance(pick, dict) else pick
            return v
        if "$call" in v:
            args = v.get("args") or []
            if len(args) >= 1 and isinstance(args[0], str) and args[0] in self.by_id:
                r = dict(self.by_id[args[0]])
                if len(args) > 1 and isinstance(args[1], str): r["label"] = args[1]
                return r
            nums = [a for a in args if _isnum(a)]
            if len(nums) >= 2 and len(args) <= 3:   # pt(x, y) / vec(x, z)
                return {"x": nums[0], "y": nums[1], "_via": v["$call"]}
        return v


def _pos(it, res=None, file=None):
    """(x, y) on the ground plane from x/z, x/y, pos/position/at/where/start, or a resolved call."""
    if not isinstance(it, dict): return None
    def xy(d):
        if not isinstance(d, dict): return None
        if res: d = res(d, file)
        if not isinstance(d, dict): return None
        x = d.get("x"); y = d.get("z") if _isnum(d.get("z")) and not (_isnum(d.get("y")) and d.get("_via")) else d.get("y")
        if _isnum(x) and _isnum(y): return (float(x), float(y))
        for k in ("pos", "position", "at"):
            if isinstance(d.get(k), dict) and d is not it:
                r = xy(d[k])
                if r: return r
        return None
    r = xy(it)
    if r: return r
    for k in ("pos", "position", "at", "where", "start", "spawn", "loc", "location"):
        if k in it:
            r = xy(it[k]) if isinstance(it[k], dict) else None
            if r: return r
    return None


def _name(it, fallback=None):
    for k in STR_KEYS_NAME:
        v = it.get(k)
        if isinstance(v, str) and v.strip(): return v.strip()
    return fallback


def _text(it):
    out = []
    for k in STR_KEYS_TEXT:
        v = it.get(k)
        if isinstance(v, str) and len(v) > 3: out.append(v)
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v): out.extend(v)
    return out


def _all_strings(v, out, depth=0):
    if depth > 6: return out
    if isinstance(v, str):
        if len(v) > 12 and " " in v and not v.startswith(("#", "http", "/")): out.append(v)
    elif isinstance(v, dict):
        for k, x in v.items():
            if k not in ("_L", "_doc", "$expr", "$ref", "id", "kind", "type"): _all_strings(x, out, depth + 1)
    elif isinstance(v, list):
        for x in v: _all_strings(x, out, depth + 1)
    return out


def _nums(it):
    return {k: float(v) for k, v in it.items() if _isnum(v) and not k.startswith("_")}


# ------------------------------------------------------------------------------ classification
def classify(c):
    items = [it for _, it in c["items"] if isinstance(it, dict)]
    if not items or c["kind"] not in ("array", "record"): return None, 0, []
    n = len(items)
    share = Counter(k for it in items for k in it if not k.startswith(("_", "$")))
    present = {k for k, v in share.items() if v >= 0.4 * n}
    name_t = set(_tokens(c["symbol"]))
    type_t = set(_tokens(c.get("type") or ""))
    scores, why = {}, {}
    for t in TYPES:
        s, w = 0.0, []
        hints = NAME_HINTS[t]
        if name_t & set(hints): s += 3.5; w.append(f"name {c['symbol']}")
        if type_t & set(hints): s += 2; w.append(f"type {c.get('type')}")
        for k, kw in KEY_HINTS[t].items():
            if k in present: s += kw; w.append(k)
        scores[t], why[t] = s, w
    has_pos = sum(1 for it in items if _pos(it)) >= 0.5 * n
    has_text = sum(1 for it in items if _text(it)) >= 0.5 * n
    has_obj = any(k in present for k in OBJ_LIST_KEYS)
    numeric_fields = [k for k in present if sum(1 for it in items if _isnum(it.get(k))) >= 0.8 * n]
    # shape gates: a type is only possible when its defining evidence is there
    if not (has_obj or ("brief" in present or "briefing" in present)): scores["mission"] = 0
    if not ("hint" in present or "text" in present) or "reward" in present or n < 3: scores["questchain"] = 0
    if not (has_pos or "region" in present or "landmarks" in present): scores["place"] = 0
    if not any(k in present for k in ("name", "title", "label")): scores["character"] = scores["world"] = 0
    if "name" not in present: scores["character"] = 0   # a role table (label + perk) is not a person
    if not has_text and not (name_t & set(NAME_HINTS["story"]) and any(k in present for k in ("label", "title", "name"))): scores["story"] = 0
    if len(numeric_fields) < 2: scores["encounter"] = min(scores["encounter"], 0)
    if n < 3 or len(numeric_fields) < 1 and "spawns" not in present: scores["stage"] = 0
    if has_pos and scores["world"]: scores["world"] -= 2
    if scores["character"] and not any(k in present for k in ("role", "bio", "personality", "voice", "faction", "backstory", "perk", "greeting", "home", "lines")) \
            and not (name_t | type_t) & set(NAME_HINTS["character"]):
        scores["character"] = 0
    if scores["world"] and not (name_t | type_t) & set(NAME_HINTS["world"]): scores["world"] = 0
    best = max(scores, key=lambda t: scores[t])
    if scores[best] < 3: return None, scores[best], why[best]
    return best, scores[best], why[best]


# ------------------------------------------------------------------------------ normalisers
def _ev(c, it): return {"file": c["file"], "line": it.get("_L") or c.get("line"), "symbol": c["symbol"]}


def _objectives(it, res, file):
    for k in OBJ_LIST_KEYS:
        v = it.get(k)
        if isinstance(v, list) and v:
            out = []
            for st in v:
                if not isinstance(st, dict):
                    if isinstance(st, str): out.append({"verb": _verb(None, st), "text": st, "targets": [], "options": [], "mode": None})
                    continue
                pts = st.get("points") if isinstance(st.get("points"), list) else []
                targets = []
                for p in pts:
                    if isinstance(p, dict):
                        q = _pos(p, res, file); targets.append({"label": p.get("label") or p.get("id"), "x": q[0] if q else None, "y": q[1] if q else None})
                at = st.get("at") if "at" in st else st.get("target")
                if at is not None and not pts:
                    r = res(at, file) if isinstance(at, dict) else at
                    q = _pos({"at": r}) if isinstance(r, dict) else None
                    lab = (r.get("label") or r.get("name")) if isinstance(r, dict) else r
                    targets.append({"label": lab if isinstance(lab, str) else None, "x": q[0] if q else None, "y": q[1] if q else None})
                for lk in ("spots", "contacts", "trail"):
                    if isinstance(st.get(lk), list): targets.extend({"label": None, "x": None, "y": None} for _ in st[lk][:0])
                opts = st.get("by") if isinstance(st.get("by"), list) else []
                text = st.get("text") or st.get("verb") or st.get("label") or st.get("desc")
                out.append({"verb": _verb(st, text), "text": text if isinstance(text, str) else None, "targets": targets,
                            "mode": st.get("mode") if isinstance(st.get("mode"), str) else None, "options": [o for o in opts if isinstance(o, str)],
                            "count": len(pts) or len(st.get("spots") or []) or len(st.get("contacts") or []) or (1 if targets else 0),
                            "optional": bool(st.get("optional") or st.get("bonus")), "hold": st.get("hold") if _isnum(st.get("hold")) else None,
                            "line": st.get("_L")})
            return out
    return []


VERB_WORDS = ["goto", "go", "reach", "get", "ride", "fly", "head", "return", "interact", "talk", "find", "collect", "deliver", "photograph", "shoot",
              "hit", "destroy", "defend", "escort", "survive", "scan", "land", "track", "carry", "repair", "fire", "watch", "grind", "tag", "dig",
              "sell", "craft", "upgrade", "anchor", "steer", "read", "catalog", "mount", "rescue", "search"]


def _verb(st, text):
    if isinstance(st, dict):
        for k in ("kind", "type", "verb", "action"):
            v = st.get(k)
            if isinstance(v, str) and v.strip(): return v.strip().lower()
    if isinstance(text, str):
        w = re.findall(r"[a-zA-Z]+", text.lower())
        for x in w[:3]:
            if x in VERB_WORDS: return x
        return w[0] if w else "do"
    return "do"


def _reward(it):
    r = it.get("reward") if "reward" in it else it.get("rewards")
    if isinstance(r, dict): return {k: float(v) for k, v in r.items() if _isnum(v) and not k.startswith("_")}, [str(v) for k, v in r.items() if isinstance(v, str) and not k.startswith("_")]
    if _isnum(r): return {"reward": float(r)}, []
    flat = {k: float(it[k]) for k in ("xp", "gold", "funds", "money", "coins", "dna", "rep") if _isnum(it.get(k))}
    return flat, []


def _ids(v):
    if isinstance(v, list): return [x for x in v if isinstance(x, str)]
    if isinstance(v, str): return [v]
    return []


def build(bundle):
    res = Resolver(bundle)
    M = {"missions": [], "places": [], "worlds": [], "characters": [], "story": [], "encounters": [], "progression": [], "stages": [],
         "collections": [], "unclassified": [], "limitations": []}
    for c in bundle["collections"]:
        t, score, why = classify(c)
        entry = {"symbol": c["symbol"], "file": c["file"], "line": c.get("line"), "items": len(c["items"]), "kind": c["kind"], "doc": c.get("doc"),
                 "as": t, "score": round(score, 1), "why": why[:6]}
        if c["kind"] in ("array", "record") and len(c["items"]) >= 2:
            (M["collections"] if t else M["unclassified"]).append(entry)
        if not t: continue
        if t in ("world", "encounter", "progression") and c["kind"] == "array" and len(c["items"]) >= 3 and set(_tokens(c["symbol"])) & set(NAME_HINTS["stage"]):
            for order, (k, it) in enumerate(c["items"]):
                e = n_stage(c, k, it, res, order); e["ev"] = _ev(c, it); e["collection"] = c["symbol"]; M["stages"].append(e)
            entry["also"] = "stage"
        fn = NORMALISE[t]
        for order, (k, it) in enumerate(c["items"]):
            if not isinstance(it, dict): continue
            e = fn(c, k, it, res, order)
            if e: e["ev"] = _ev(c, it); e["collection"] = c["symbol"]; M[_BUCKET[t]].append(e)
    _builder_calls(bundle, M, res)
    _scripts(bundle, M)
    _maps(bundle, M)
    _dedupe(M)
    _inferred_cast(M)
    _link(M)
    _speakers(M)
    _limits(bundle, M)
    M["corpus"] = _corpus(bundle, M)
    return M


_BUCKET = {"mission": "missions", "questchain": "missions", "place": "places", "world": "worlds", "character": "characters", "story": "story",
           "encounter": "encounters", "progression": "progression", "stage": "stages"}


def n_mission(c, k, it, res, order):
    objs = _objectives(it, res, c["file"])
    rw, rw_items = _reward(it)
    where = it.get("where") or it.get("start") or it.get("location")
    where_r = res(where, c["file"]) if isinstance(where, dict) else where
    q = _pos({"at": where_r}) if isinstance(where_r, dict) else None
    fails = [x for x in ("fail", "failure", "failIf", "timeLimit", "time", "timer", "limit", "lose") if x in it]
    return {"id": str(it.get("id") or k or order), "title": _name(it, str(k)), "kind": next((it[x] for x in ("family", "kind", "type", "category") if isinstance(it.get(x), str)), None),
            "giver": it.get("from") or it.get("giver") if isinstance(it.get("from") or it.get("giver"), str) else None,
            "brief": next((it[x] for x in ("brief", "briefing", "desc", "description") if isinstance(it.get(x), str)), None),
            "alert": it.get("alert") if isinstance(it.get("alert"), str) else None, "done": it.get("done") if isinstance(it.get("done"), str) else None,
            "threat": it.get("threat") if isinstance(it.get("threat"), str) else None,
            "objectives": objs, "reward": rw, "reward_items": rw_items, "requires": _ids(it.get("requires") or it.get("prerequisites") or it.get("after")),
            "where": {"label": (where_r.get("label") or where_r.get("name")) if isinstance(where_r, dict) else None, "x": q[0] if q else None, "y": q[1] if q else None},
            "dynamic": bool(it.get("dynamic") or it.get("repeatable") or it.get("recurring")), "fails": fails,
            "number": it.get("number") if _isnum(it.get("number")) else None, "order": order,
            "par": it.get("target") if _isnum(it.get("target")) else (it.get("par") if _isnum(it.get("par")) else None),
            "flags": [x for x in ("controls", "unlocks", "sets", "flag", "consequence", "branch") if x in it]}


def n_questchain(c, k, it, res, order):
    # one entry per step; folded into a single mission in _dedupe
    return {"_chain": True, "id": str(it.get("id") or order), "text": it.get("text") if isinstance(it.get("text"), str) else None,
            "hint": it.get("hint") if isinstance(it.get("hint"), str) else None, "order": order}


def n_place(c, k, it, res, order):
    q = _pos(it, res, c["file"])
    contents = {}
    for ck in ("caches", "finds", "landmarks", "loot", "secrets", "pickups", "items", "rooms", "npcs", "enemies", "spawns"):
        if isinstance(it.get(ck), list): contents[ck] = len(it[ck])
    for ck in ("shells", "palms", "rocks"):
        pass
    return {"id": str(it.get("id") or k or order), "name": _name(it, str(k) if k != "" else None) or f"{c['symbol']}[{order}]",
            "x": q[0] if q else None, "y": q[1] if q else None, "region": it.get("region") if isinstance(it.get("region"), str) else None,
            "radius": float(it.get("r") if _isnum(it.get("r")) else it.get("radius")) if _isnum(it.get("r")) or _isnum(it.get("radius")) else None,
            "kind": next((it[x] for x in ("kind", "type", "style", "biome") if isinstance(it.get(x), str)), None) or c["symbol"].lower(),
            "kind_explicit": any(isinstance(it.get(x), str) for x in ("kind", "type", "style", "biome")),
            "contents": contents, "blurb": next((it[x] for x in ("blurb", "desc", "description") if isinstance(it.get(x), str)), None),
            "requires": _ids(it.get("requires") or it.get("requiresItem") or it.get("unlock")), "order": order}


def n_world(c, k, it, res, order):
    return {"id": str(it.get("id") or k or order), "name": _name(it, str(k)), "blurb": next(iter(_text(it)), None), "order": order,
            "numbers": _nums(it)}


def n_character(c, k, it, res, order):
    nm = _name(it, str(k) if k != "" else None)
    if not nm: return None
    role = next((it[x] for x in ("role", "title", "job", "faction", "perk") if isinstance(it.get(x), str) and it.get(x) != nm), None)
    desc = " ".join(_text(it))[:600] or None
    lines = it.get("lines") if isinstance(it.get("lines"), list) else []
    q = _pos(it, res, c["file"])
    return {"id": str(it.get("id") or k or nm), "name": nm, "role": role, "desc": desc, "lines": [x for x in lines if isinstance(x, str)][:20],
            "x": q[0] if q else None, "y": q[1] if q else None, "source": "data"}


def n_story(c, k, it, res, order):
    texts = _text(it)
    if not texts: texts = _all_strings(it, [])[:4]
    if not texts and isinstance(it.get("label") or it.get("title"), str): texts = [it.get("label") or it.get("title")]
    if not texts: return None
    sym = c["symbol"].lower()
    cat = "ending" if "ending" in sym else "clue" if "clue" in sym else "thread" if "thread" in sym else "beat" if "beat" in sym else \
        "bark" if "bark" in sym else "deduction" if "deduc" in sym else "dialogue" if any(x in sym for x in ("dialog", "talk", "line", "voice", "radio")) else "lore"
    speaker = next((it[x] for x in ("speaker", "who", "from", "by", "cast", "character", "npc", "voice", "source") if isinstance(it.get(x), str)), None)
    return {"id": str(it.get("id") or k or order), "title": _name(it), "speaker": speaker, "texts": texts[:8], "category": cat,
            "phase": next((it[x] for x in ("phase", "when", "trigger", "thread", "district") if isinstance(it.get(x), str)), None),
            "links": _ids(it.get("requires") or it.get("needs") or it.get("clues") or it.get("from_clues")), "order": order}


def n_encounter(c, k, it, res, order):
    nm = _name(it, str(k) if k != "" else None)
    return {"id": str(it.get("id") or k or order), "name": nm or f"{c['symbol']}[{order}]", "stats": _nums(it),
            "kind": next((it[x] for x in ("species", "kind", "type", "class") if isinstance(it.get(x), str)), None), "order": order}


def n_progression(c, k, it, res, order):
    nm = _name(it, str(k) if k != "" else None)
    cost = next((float(it[x]) for x in ("cost", "price", "xp", "threshold", "min", "dna", "need", "needed") if _isnum(it.get(x))), None)
    if cost is None and isinstance(it.get("cost"), dict):
        vals = [float(v) for v in it["cost"].values() if _isnum(v)]; cost = sum(vals) if vals else None
    cond = it.get("cond") if isinstance(it.get("cond"), dict) else None
    rw, _ = _reward(it)
    return {"id": str(it.get("id") or k or order), "name": nm or f"{c['symbol']}[{order}]", "cost": cost, "requires": _ids(it.get("requires") or it.get("after") or it.get("unlockedBy")),
            "reward": rw, "cond": _clean(cond) if cond else None, "category": next((it[x] for x in ("slot", "category", "tier", "kind", "type", "rarity") if isinstance(it.get(x), (str,))), None),
            "tier": it.get("tier") if _isnum(it.get("tier")) else (it.get("level") if _isnum(it.get("level")) else None),
            "desc": next(iter(_text(it)), None), "order": order}


def n_stage(c, k, it, res, order):
    spawns = it.get("spawns") if isinstance(it.get("spawns"), list) else None
    st = _nums(it)
    if spawns is not None:
        st["spawn_count"] = float(len(spawns))
        kinds = Counter(s.get("type") for s in spawns if isinstance(s, dict) and isinstance(s.get("type"), str))
        mix = dict(kinds)
    else:
        mix = {}
    return {"id": str(it.get("id") or k or order), "name": _name(it, None) or f"{c['symbol']} {order + 1}", "stats": st, "mix": mix, "order": order}


NORMALISE = {"mission": n_mission, "questchain": n_questchain, "place": n_place, "world": n_world, "character": n_character, "story": n_story,
             "encounter": n_encounter, "progression": n_progression, "stage": n_stage}

BUILDER = {"character": {"person", "npc", "character", "villager", "addNpc", "addPerson", "actor"},
           "place": {"place", "spot", "landmark", "room", "area", "zone", "poi", "addPlace"},
           "encounter": {"enemy", "spawn", "addEnemy", "foe", "monster"}}


def _builder_calls(bundle, M, res):
    for call in bundle["calls"]:
        kind = next((k for k, ms in BUILDER.items() if call["method"] in ms), None)
        if not kind: continue
        args = call["args"]; strs = [a for a in args if isinstance(a, str)]
        pos = next((res(a, call["file"]) for a in args if isinstance(a, dict) and ("$call" in a or "x" in a)), None)
        q = _pos({"at": pos}) if isinstance(pos, dict) else None
        opts = next((a for a in args if isinstance(a, dict) and "$call" not in a and "x" not in a), {}) or {}
        ev = {"file": call["file"], "line": call["line"], "symbol": f"{call['recv']}.{call['method']}()"}
        if kind == "character" and len(strs) >= 2:
            M["characters"].append({"id": strs[0], "name": strs[1], "role": strs[2] if len(strs) > 2 else None, "desc": None, "lines": [],
                                    "x": q[0] if q else None, "y": q[1] if q else None, "source": "builder",
                                    "hidden": opts.get("visible") is False, "moves": isinstance(opts.get("route"), list), "ev": ev, "collection": ev["symbol"]})
        elif kind == "place" and strs:
            M["places"].append({"id": strs[0], "name": strs[1] if len(strs) > 1 else strs[0], "x": q[0] if q else None, "y": q[1] if q else None,
                                "region": None, "radius": opts.get("reach") if _isnum(opts.get("reach")) else None, "kind": "interactable",
                                "contents": {}, "blurb": None, "requires": [], "hidden": opts.get("visible") is False, "order": len(M["places"]), "ev": ev, "collection": ev["symbol"]})
        elif kind == "encounter" and strs:
            M["encounters"].append({"id": strs[0], "name": strs[1] if len(strs) > 1 else strs[0], "stats": _nums(opts), "kind": None, "order": len(M["encounters"]), "ev": ev,
                                    "collection": ev["symbol"], "x": q[0] if q else None, "y": q[1] if q else None})


def _scripts(bundle, M):
    for s in bundle["scripts"]:
        for nd in s["nodes"]:
            for ln in nd["lines"]:
                M["story"].append({"id": f"{nd['id']}:{ln['line']}", "title": nd["id"], "speaker": ln["speaker"], "texts": [ln["text"]], "category": "dialogue",
                                   "phase": nd["id"], "links": nd["links"], "order": len(M["story"]), "ev": {"file": s["file"], "line": ln["line"], "symbol": f"{s['format']}:{nd['id']}"},
                                   "collection": s["file"], "choices": len(nd["choices"])})
            for spk in {ln["speaker"] for ln in nd["lines"] if ln["speaker"]}:
                if not any(c["name"].lower() == spk.lower() for c in M["characters"]):
                    M["characters"].append({"id": spk.lower(), "name": spk, "role": None, "desc": None, "lines": [], "x": None, "y": None, "source": s["format"],
                                            "ev": {"file": s["file"], "line": nd["line"], "symbol": f"{s['format']}:{nd['id']}"}, "collection": s["file"]})
        M.setdefault("branching", []).append({"file": s["file"], "format": s["format"], "nodes": len(s["nodes"]),
                                              "choices": sum(len(n["choices"]) for n in s["nodes"]),
                                              "edges": [[n["id"], t] for n in s["nodes"] for t in n["links"]]})


def _maps(bundle, M):
    M["maps"] = []
    for mp in bundle["maps"]:
        if mp["format"] == "tiled":
            m = mp["map"]
            M["maps"].append({"file": mp["file"], "format": "tiled", "width": m["width"], "height": m["height"], "layers": [{k: v for k, v in L.items() if k != "grid"} for L in m["layers"]],
                              "grid": next((L["grid"] for L in m["layers"] if L.get("grid") and re.search(r"wall|solid|collision|ground|terrain", L.get("name") or "", re.I)), None)})
            for i, o in enumerate(m["objects"]):
                kind = (o.get("type") or "").lower()
                ev = {"file": mp["file"], "line": None, "symbol": f"tiled object {o.get('name') or i}"}
                tgt = "encounters" if re.search(r"enemy|spawn|monster|foe", kind) else "places"
                if tgt == "encounters":
                    M["encounters"].append({"id": f"{mp['file']}#{i}", "name": o.get("name") or kind, "stats": {k: float(v) for k, v in o["props"].items() if _isnum(v)},
                                            "kind": kind, "x": o.get("x"), "y": o.get("y"), "order": i, "ev": ev, "collection": mp["file"]})
                else:
                    M["places"].append({"id": f"{mp['file']}#{i}", "name": o.get("name") or kind, "x": o.get("x"), "y": o.get("y"), "region": os.path.basename(mp["file"]) if False else mp["file"],
                                        "radius": None, "kind": kind or "object", "contents": {}, "blurb": None, "requires": [], "order": i, "ev": ev, "collection": mp["file"],
                                        "checkpoint": bool(re.search(r"checkpoint|save|respawn", kind)), "secret": bool(re.search(r"secret|hidden|chest|collectible|pickup", kind))})
        elif mp["format"] == "ldtk":
            for lv in mp["map"]["levels"]:
                M["places"].append({"id": lv["name"], "name": lv["name"], "x": lv["x"], "y": lv["y"], "region": mp["file"], "radius": None, "kind": "ldtk level",
                                    "contents": {"entities": len(lv["objects"])}, "blurb": None, "requires": [], "order": len(M["places"]),
                                    "ev": {"file": mp["file"], "line": None, "symbol": f"ldtk level {lv['name']}"}, "collection": mp["file"]})


import os  # noqa: E402  (used by _maps)


def _dedupe(M):
    # fold question-chain steps into one mission per collection
    chains = [m for m in M["missions"] if m.get("_chain")]
    if chains:
        M["missions"] = [m for m in M["missions"] if not m.get("_chain")]
        by = {}
        for s in chains: by.setdefault(s["collection"], []).append(s)
        for sym, steps in by.items():
            ev = dict(steps[0]["ev"])
            M["missions"].append({"id": sym.lower(), "title": sym.replace("_", " ").title(), "kind": "guided chain", "giver": None,
                                  "brief": steps[0].get("hint"), "alert": None, "done": None, "threat": None,
                                  "objectives": [{"verb": _verb(None, s["text"]), "text": s["text"], "targets": [], "mode": None, "options": [], "count": 1,
                                                  "optional": False, "hold": None, "hint": s["hint"], "line": s["ev"]["line"]} for s in steps],
                                  "reward": {}, "reward_items": [], "requires": [], "where": {"label": None, "x": None, "y": None}, "dynamic": False, "fails": [],
                                  "number": None, "order": -1, "par": None, "flags": [], "ev": ev, "collection": sym, "chain": True})
    for key in ("characters", "places"):
        seen, out = set(), []
        for e in M[key]:
            k = (e.get("name") or "").lower(), e.get("id")
            if (e.get("name") or "").lower() in seen and key == "characters": continue
            seen.add((e.get("name") or "").lower()); out.append(e)
        M[key] = out


STOP = set("""The A An And But Or If When Then This That These Those It Its You Your We Our They Their He She His Her I My Me Us
Head Ride Fly Get Go Take Find Bring Land Clear Say Hold Pick Keep Stay Use Tap Drag Press Make Let Watch Look Check Come Now New Good
Nothing Every Everyone Nobody Somebody Something No Not Yes OK One Two Three Four Five Six Seven Eight Nine Ten First Last Next Back Up
North South East West Morning Night Day Today Tonight Monday Tuesday Wednesday Thursday Friday Saturday Sunday Thanks Thank Hey Oh Well
Great Nice Right Left Done Dispatch Radio Station Mission Patrol Team Call Base Home What Who Where Why How Don Can Will""".split())


def _inferred_cast(M):
    """When no character data exists, recurring names in authored text are a cast the game implies (labelled inferred)."""
    if len([c for c in M["characters"] if c.get("source") != "text"]) >= 3: return
    labels = [p.get("name") for p in M["places"]] + [m["where"].get("label") for m in M["missions"]] + [m.get("title") for m in M["missions"]] \
        + [t.get("label") for m in M["missions"] for o in m["objectives"] for t in o["targets"]] + [w.get("name") for w in M["worlds"]]
    places = {t for lab in labels if isinstance(lab, str) for t in re.findall(r"[A-Z][a-z]+", lab)}
    counts, where = Counter(), {}
    texts = [m.get(k) for m in M["missions"] for k in ("brief", "alert", "done")] + [o.get("text") for m in M["missions"] for o in m["objectives"]] \
        + [t for s in M["story"] for t in s["texts"]]
    for t in filter(None, texts):
        for m in re.finditer(r"(?<=[a-z,;:] )([A-Z][a-z]{2,})(?![a-z])", t):
            w = m.group(1)
            if w in STOP or w in places: continue
            counts[w] += 1; where.setdefault(w, t[:120])
    known = {c["name"].split()[0] for c in M["characters"]}
    for w, n in counts.most_common(12):
        if n < 3 or w in known: continue
        M["characters"].append({"id": w.lower(), "name": w, "role": None, "desc": None, "lines": [], "x": None, "y": None, "source": "text",
                                "inferred": True, "mentions_seen": n, "ev": {"file": None, "line": None, "symbol": f"recurs {n}× in authored text, e.g. \"{where[w]}\""},
                                "collection": "authored text"})


def _link(M):
    """Edges of the game model graph, and per-mission links to places and characters."""
    names = {p["name"].lower(): p for p in M["places"] if p.get("name")}
    chars = [c for c in M["characters"] if c.get("name")]
    for m in M["missions"]:
        lab = (m["where"].get("label") or "").lower()
        place = names.get(lab)
        if not place and m["where"].get("x") is not None:
            cands = [p for p in M["places"] if p.get("x") is not None and p.get("kind") != "interactable" and not re.search(r"\[\d+\]$", p.get("name") or "[0]") and len(p.get("name") or "") > 2]
            if cands:
                place = min(cands, key=lambda p: math.hypot(p["x"] - m["where"]["x"], p["y"] - m["where"]["y"]))
                if math.hypot(place["x"] - m["where"]["x"], place["y"] - m["where"]["y"]) > max(150, (place.get("radius") or 0) * 2): place = None
        m["place"] = place["id"] if place else None
        text = " ".join(filter(None, [m.get("brief"), m.get("alert"), m.get("done"), m.get("giver")] + [o.get("text") or "" for o in m["objectives"]]))
        m["characters"] = sorted({c["id"] for c in chars if _mentions(text, c["name"])})
        m["words"] = len(re.findall(r"\w+", text))


def _mentions(text, name):
    if not text or not name: return False
    first = name.split()[0]
    pats = [re.escape(name)]
    if len(first) >= 4 and first.lower() not in ("the", "mrs.", "mr.", "officer", "courier", "doctor", "captain"): pats.append(re.escape(first))
    return bool(re.search(r"(?<![\w])(" + "|".join(pats) + r")(?![\w])", text, re.I if name.islower() else 0))


def _speakers(M):
    """Speaker ids used by dialogue but not defined as characters become characters (source: dialogue)."""
    known = {c["id"].lower() for c in M["characters"]} | {c["name"].lower() for c in M["characters"]}
    spk = Counter(s["speaker"] for s in M["story"] if s.get("speaker") and s["category"] in ("dialogue", "bark"))
    for name, n in spk.items():
        if name.lower() in known or n < 2: continue
        first = next(s for s in M["story"] if s.get("speaker") == name)
        M["characters"].append({"id": name.lower(), "name": name[:1].upper() + name[1:], "role": "speaker", "desc": None, "lines": [], "x": None, "y": None,
                                "source": "dialogue", "ev": first["ev"], "collection": first["collection"]})


def _corpus(bundle, M):
    """Every authored player-facing string we found, with where it came from (for the story department)."""
    out = []
    for m in M["missions"]:
        for k in ("brief", "alert", "done"):
            if m.get(k): out.append({"text": m[k], "src": f"mission {m['id']} {k}", "ev": m["ev"]})
        for o in m["objectives"]:
            if o.get("text"): out.append({"text": o["text"], "src": f"mission {m['id']} objective", "ev": m["ev"]})
    for s in M["story"]:
        for t in s["texts"]: out.append({"text": t, "src": f"{s['category']} {s['id']}", "ev": s["ev"]})
    for p in M["places"]:
        if p.get("blurb"): out.append({"text": p["blurb"], "src": f"place {p['id']}", "ev": p["ev"]})
    for c in M["characters"]:
        if c.get("desc"): out.append({"text": c["desc"], "src": f"character {c['id']}", "ev": c["ev"]})
        for t in c.get("lines") or []: out.append({"text": t, "src": f"character {c['id']} line", "ev": c["ev"]})
    return out


def _limits(bundle, M):
    L = M["limitations"]
    if not M["missions"]: L.append({"area": "missions", "text": "No mission, quest or objective definitions were found as data. Mission design can only be assessed from documentation, if at all."})
    if not M["places"] and not M["maps"]: L.append({"area": "levels", "text": "No level geometry, map files or placed locations were found. Level layout and navigation cannot be measured."})
    if not M["characters"]: L.append({"area": "story", "text": "No character definitions were found as data."})
    if not M["story"] and not any(c.get("lines") for c in M["characters"]): L.append({"area": "story", "text": "No dialogue, narrative beats or lore text were found as data."})
    if not M["progression"] and not M["stages"]: L.append({"area": "progression", "text": "No unlocks, upgrades, rewards or difficulty stages were found as data."})
    if not M["encounters"] and not M["stages"]: L.append({"area": "encounters", "text": "No enemy or encounter configuration was found as data."})
    for k, n in bundle["unsupported_counts"].items():
        L.append({"area": "formats", "text": f"{n} {k} file(s) present; DESIGNCRAFT cannot read this format yet, so their content is not in the model."})
    L.append({"area": "runtime", "text": "Behaviour that exists only in code (AI, spawn logic, physics) is not executed or simulated by DESIGNCRAFT; it is visible only through PLAYCRAFT evidence when present."})


def graph(M, title):
    """Nodes and edges for the Game Map: game → worlds/regions → places → missions → objectives, characters, progression."""
    nodes, edges = [{"id": "game", "type": "game", "label": title}], []
    regions = sorted({p["region"] for p in M["places"] if p.get("region")})
    for w in M["worlds"]:
        nodes.append({"id": f"w:{w['id']}", "type": "world", "label": w["name"], "ev": w["ev"]}); edges.append(["game", f"w:{w['id']}", "contains"])
    for r in regions:
        rid = f"w:{r}"
        if not any(n["id"] == rid for n in nodes):
            nodes.append({"id": rid, "type": "world", "label": r}); edges.append(["game", rid, "contains"])
    for p in M["places"]:
        if p.get("kind") == "interactable": continue
        nodes.append({"id": f"p:{p['id']}", "type": "level", "label": p["name"], "ev": p["ev"]})
        edges.append([f"w:{p['region']}" if p.get("region") else "game", f"p:{p['id']}", "contains"])
    for m in M["missions"]:
        nodes.append({"id": f"m:{m['id']}", "type": "mission", "label": m["title"], "ev": m["ev"]})
        edges.append([f"p:{m['place']}" if m.get("place") else "game", f"m:{m['id']}", "located"])
        for r in m["requires"]: edges.append([f"m:{r}", f"m:{m['id']}", "unlocks"])
        for c in m.get("characters", []): edges.append([f"m:{m['id']}", f"c:{c}", "features"])
    for c in M["characters"]:
        nodes.append({"id": f"c:{c['id']}", "type": "character", "label": c["name"], "ev": c["ev"]})
    ids = {n["id"] for n in nodes}
    edges = [e for e in edges if e[0] in ids and e[1] in ids]
    return {"nodes": nodes, "edges": edges}
