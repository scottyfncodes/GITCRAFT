"""LEVELCRAFT: level architecture, navigation, exploration, discovery, travel friction and environmental variety.

Measured from placed locations (x/y or x/z in data, Tiled/LDtk objects) and the positions missions send the
player to. Facts are source_verified; what they mean for players is inferred."""
import math, re
from collections import Counter
from .base import finding, entropy_norm, gini, median, names_list, pct, is_travel
from ..evidence import cite, ev

NAME, TITLE, CATEGORY = "levelcraft", "LEVELCRAFT", "level"
HUB_WORDS = re.compile(r"\b(hq|home|base|station|harbou?r|camp|lodge|hub|town|dock|tent|garage|driftholm)\b", re.I)


def _named(p): return p.get("name") and not re.search(r"\[\d+\]$", p["name"]) and p.get("kind") != "interactable"


def hub_of(M):
    labels = Counter()
    for m in M["missions"]:
        seen = set()
        for o in m["objectives"]:
            for t in o["targets"]:
                if t.get("label") and t["label"] not in seen: labels[t["label"]] += 1; seen.add(t["label"])
    for lab, n in labels.most_common(5):
        if n >= 3 and HUB_WORDS.search(lab): return lab, n
    if labels and labels.most_common(1)[0][1] >= max(3, 0.4 * len(M["missions"])): return labels.most_common(1)[0]
    return None, 0


def _dist(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])


def mission_paths(M, hub_label):
    hub_pos = None
    for m in M["missions"]:
        for o in m["objectives"]:
            for t in o["targets"]:
                if t.get("label") == hub_label and t.get("x") is not None: hub_pos = (t["x"], t["y"])
    out = []
    for m in M["missions"]:
        pts = [(t["x"], t["y"], t.get("label")) for o in m["objectives"] for t in o["targets"][:1] if t.get("x") is not None]
        start = hub_pos if hub_pos and not m.get("dynamic") else (pts[0][:2] if pts else None)
        legs, cur = [], start
        for x, y, lab in pts:
            if cur is not None: legs.append(_dist(cur, (x, y)))
            cur = (x, y)
        last = m["objectives"][-1] if m["objectives"] else None
        ret = bool(last and is_travel(last["verb"]) and last["targets"] and (last["targets"][0].get("label") == hub_label or
                   (hub_pos and last["targets"][0].get("x") is not None and _dist(hub_pos, (last["targets"][0]["x"], last["targets"][0]["y"])) < 60)))
        out.append({"id": m["id"], "title": m["title"], "distance": round(sum(legs)) if legs else None, "legs": [round(l) for l in legs],
                    "return_leg": ret, "return_distance": round(legs[-1]) if ret and legs else None, "points": [[round(x), round(y), lab] for x, y, lab in pts]})
    return out, hub_pos


def analyse(M, ctx):
    F, S = [], []
    places = [p for p in M["places"] if p.get("x") is not None]
    named = [p for p in M["places"] if _named(p)]
    regions = Counter(p.get("region") for p in M["places"] if p.get("region"))
    sig = ctx.get("signals", {})
    metrics = {"places": len(M["places"]), "positioned": len(places), "named": len(named), "regions": len(regions), "maps": len(M.get("maps", []))}
    cov = {"geometry": bool(places), "missions_positioned": any(t.get("x") is not None for m in M["missions"] for o in m["objectives"] for t in o["targets"])}
    viz = {"places": [{"id": p["id"], "name": p["name"], "x": p["x"], "y": p["y"], "kind": p.get("kind"), "region": p.get("region"),
                       "r": p.get("radius"), "content": sum(p.get("contents", {}).values()), "named": _named(p)} for p in places][:400]}
    if not places and not M.get("maps"):
        return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": [], "strengths": [], "coverage": cov, "viz": viz,
                "note": "No level geometry or placed locations were found, so nothing here was measured."}
    xs, ys = [p["x"] for p in places], [p["y"] for p in places]
    if places:
        bx, by = (min(xs), max(xs)), (min(ys), max(ys))
        metrics["extent"] = [round(bx[1] - bx[0]), round(by[1] - by[0])]
        nn = []
        for p in places:
            d = [math.hypot(p["x"] - q["x"], p["y"] - q["y"]) for q in places if q is not p]
            if d: nn.append(min(d))
        metrics["nearest_neighbour_median"] = round(median(nn) or 0, 1)
        # occupancy grid over the bounding box, including mission targets
        pts = [(p["x"], p["y"]) for p in places] + [(t["x"], t["y"]) for m in M["missions"] for o in m["objectives"] for t in o["targets"] if t.get("x") is not None]
        G = 6
        w = max(1e-6, bx[1] - bx[0]); h = max(1e-6, by[1] - by[0])
        occ = Counter((min(G - 1, int((x - bx[0]) / w * G)), min(G - 1, int((y - by[0]) / h * G))) for x, y in pts if bx[0] <= x <= bx[1] and by[0] <= y <= by[1])
        empty = [(i, j) for i in range(G) for j in range(G) if (i, j) not in occ]
        metrics["empty_cells"] = f"{len(empty)}/{G * G}"
        viz["grid"] = {"n": G, "bounds": [bx[0], by[0], bx[1], by[1]], "cells": [[i, j, occ.get((i, j), 0)] for i in range(G) for j in range(G)]}
        if len(pts) >= 12 and len(empty) / (G * G) >= 0.45:
            # where is the largest empty band?
            quad = Counter(("north" if j < G / 2 else "south") + ("-west" if i < G / 2 else "-east") for i, j in empty)
            q, nq = quad.most_common(1)[0]
            F.append(finding(NAME, "empty_zone", f"{pct(len(empty) / (G * G))} of the mapped area holds nothing to find or do",
                             "major" if len(empty) / (G * G) >= 0.6 else "minor",
                             f"Dividing the playable extent ({metrics['extent'][0]}×{metrics['extent'][1]} units) into a {G}×{G} grid, {len(empty)} cells contain no placed location and no mission target; the emptiest quarter is the {q} ({nq} of {G * G // 4} cells empty).",
                             "Players read empty space as either a promise or a waste. Without a landmark, a cache or a reason to cross it, a large empty area becomes travel time between the parts of the game that matter.",
                             [ev(f"{len(pts)} positioned locations and targets; {len(empty)} empty grid cells", file=places[0]["ev"]["file"], line=places[0]["ev"]["line"], symbol="positions across " + ", ".join(sorted({p['collection'] for p in places})[:5]))],
                             data={"quarter": q, "share": len(empty) / (G * G), "extent": metrics["extent"]}, category="level"))
    # ------------------------------------------------ mission destinations vs the world
    hub, hub_n = hub_of(M)
    metrics["hub"] = hub
    paths, hub_pos = mission_paths(M, hub) if M["missions"] else ([], None)
    viz["paths"] = paths; viz["hub"] = {"label": hub, "x": hub_pos[0] if hub_pos else None, "y": hub_pos[1] if hub_pos else None}
    targets = [t for m in M["missions"] for o in m["objectives"] for t in o["targets"]]
    if M["missions"] and named and targets:
        visited = set()
        for p in named:
            for t in targets:
                if (t.get("label") and p["name"] and (t["label"].lower() in p["name"].lower() or p["name"].lower() in t["label"].lower())) or \
                        (t.get("x") is not None and p.get("x") is not None and math.hypot(t["x"] - p["x"], t["y"] - p["y"]) <= max(40, (p.get("radius") or 0) * 1.2)):
                    visited.add(p["id"]); break
        unused = [p for p in named if p["id"] not in visited]
        metrics["named_places_used_by_missions"] = f"{len(visited)}/{len(named)}"
        if len(named) >= 5 and len(unused) / len(named) >= 0.4:
            F.append(finding(NAME, "unused_space", f"{len(unused)} of {len(named)} named places are never a mission destination",
                             "major" if len(unused) / len(named) >= 0.6 else "minor",
                             f"No mission objective targets {names_list([p['name'] for p in unused], 5)}. They exist in the world data but the mission structure never asks the player to go there.",
                             "Named places are authored promises. When no objective, story beat or reward points at them, most players never discover they exist, and the world feels smaller than the map.",
                             [cite(p, f"{p['name']} ({p['collection']}) is not targeted by any of {len(M['missions'])} missions") for p in unused[:6]],
                             entities=[p["id"] for p in unused], data={"places": [p["name"] for p in unused][:8], "used": len(visited), "total": len(named)}, category="level"))
        elif named:
            S.append(f"Missions reach {len(visited)} of {len(named)} named places: the mission structure uses most of the world.")
    if paths:
        rets = [p for p in paths if p["return_leg"]]
        if hub: metrics["return_to_hub"] = f"{len(rets)}/{len(paths)}"
        dists = [p["distance"] for p in paths if p["distance"]]
        metrics["mission_travel_median"] = round(median(dists)) if dists else None
        if hub and len(rets) >= max(2, 0.3 * len(paths)):
            avg = round(sum(p["return_distance"] or 0 for p in rets) / len(rets))
            F.append(finding(NAME, "return_leg", f"{len(rets)} of {len(paths)} missions end by sending the player back to {hub}",
                             "major" if len(rets) / len(paths) >= 0.5 else "minor",
                             f"The final objective of {names_list([p['title'] for p in rets], 4)} is a travel leg back to {hub}" + (f" (about {avg} units each)." if avg else "."),
                             "A mandatory trip home after the climax is pure travel with no new decision in it. It deflates the moment the mission peaks, and on repeat play it is the part players learn to resent.",
                             [cite(next(m for m in M["missions"] if m["id"] == p["id"]), f"{p['title']}: last objective returns to {hub}") for p in rets[:6]],
                             entities=[p["id"] for p in rets], data={"hub": hub, "missions": [p["title"] for p in rets], "avg": avg, "share": len(rets) / len(paths)}, category="level"))
        if len(dists) >= 4:
            md = median(dists); mx = max(paths, key=lambda p: p["distance"] or 0)
            if md and mx["distance"] > 2.5 * md:
                F.append(finding(NAME, "travel_spike", f"{mx['title']} asks for {round(mx['distance'] / md, 1)}× the median travel of other missions",
                                 "minor", f"Measured along its objective targets, {mx['title']} covers about {mx['distance']} units; the median mission covers {round(md)}.",
                                 "A sudden long haul changes the rhythm of play from doing to commuting. Unless the journey itself is the content, it reads as padding.",
                                 [cite(next(m for m in M["missions"] if m["id"] == mx["id"]), f"legs {mx['legs']}")], entities=[mx["id"]],
                                 data={"mission": mx["title"], "distance": mx["distance"], "median": round(md)}, category="level"))
    # ------------------------------------------------ discovery and rewards in space
    with_contents = [p for p in M["places"] if p.get("contents")]
    if with_contents:
        totals = [sum(p["contents"].values()) for p in with_contents]
        g = gini(totals)
        metrics["discovery_gini"] = round(g, 2)
        empty_named = [p for p in with_contents if sum(p["contents"].values()) == 0]
        if g >= 0.5 and len(with_contents) >= 4:
            top = sorted(with_contents, key=lambda p: -sum(p["contents"].values()))[:2]
            F.append(finding(NAME, "discovery_density", "Discoveries are concentrated in a few places",
                             "minor", f"Caches, finds and landmarks are unevenly spread (Gini {g:.2f}); {names_list([t['name'] for t in top])} hold the most, while {len(empty_named)} places hold none.",
                             "Exploration is rewarded by a steady rhythm of small finds. When most finds cluster in one or two spots, the rest of the world teaches players that looking around is not worth it.",
                             [cite(p, f"{p['name']}: {p['contents']}") for p in with_contents[:5]], data={"top": [t["name"] for t in top], "empty": [p["name"] for p in empty_named][:6], "gini": g}, category="level"))
        else:
            S.append(f"Discoveries are spread across {len(with_contents)} places (Gini {g:.2f}).")
    secrets = sum(1 for p in M["places"] if p.get("secret")) + sum(p.get("contents", {}).get("caches", 0) + p.get("contents", {}).get("secrets", 0) for p in M["places"])
    metrics["secrets_and_caches"] = secrets
    # ------------------------------------------------ orientation and checkpoints (signals reused from PLAYCRAFT's scan)
    orient = sig.get("exploration", {}).get("count", 0)
    landmarks = sum(p.get("contents", {}).get("landmarks", 0) for p in M["places"]) + sum(1 for p in M["places"] if re.search(r"peak|tower|light|landmark|spire|rig|ridge", (p.get("name") or "") + (p.get("kind") or ""), re.I))
    metrics["landmarks"] = landmarks
    if len(named) >= 6 and landmarks < 2 and not orient:
        F.append(finding(NAME, "orientation", "Few landmarks to navigate by", "minor",
                         f"{len(named)} named places but {landmarks} landmark-type features and no minimap / compass / waypoint system found in source.",
                         "Players orient by tall, unique silhouettes and by tools that point the way. Without either, they navigate by menu, which breaks immersion.",
                         [ev("no exploration/navigation signals in PLAYCRAFT's scan of the source", "source_verified")], data={"named": len(named)}, category="level"))
    fails = sig.get("game_over", {}).get("count", 0); cps = sig.get("checkpoint", {}).get("count", 0) + sum(1 for p in M["places"] if p.get("checkpoint"))
    metrics["checkpoints_in_source"] = cps
    saves = sig.get("save", {}).get("count", 0)
    metrics["save_references"] = saves
    if fails and not cps and not saves and (M["missions"] or M["stages"]):
        F.append(finding(NAME, "checkpoints", "Failure exists but no checkpoints were found", "minor",
                         f"The source has fail states ({fails} references) but no checkpoint or respawn-point system.",
                         "Without checkpoints, a late failure replays content the player already mastered. That is the single most common reason players quit a run.",
                         [ev(w, "source_verified") for w in sig.get("game_over", {}).get("where", [])[:2]], data={}, category="difficulty"))
    # ------------------------------------------------ environmental variety
    kinds = Counter(p.get("kind") for p in named)
    explicit = sum(1 for p in named if p.get("kind_explicit")) >= 0.5 * max(1, len(named)) or len({p["collection"] for p in named}) >= 3
    if len(named) >= 5 and explicit:
        e = entropy_norm(kinds)
        metrics["place_kind_variety"] = round(e, 2)
        top, n = kinds.most_common(1)[0]
        if n / len(named) >= 0.7 and len(kinds) <= 2:
            F.append(finding(NAME, "environment_variety", f"{pct(n / len(named))} of named places are the same kind ({top})", "minor",
                             f"{n} of {len(named)} named places share the kind '{top}'.", "Variety of place type (open, enclosed, high, low, inhabited, abandoned) is what makes a route memorable.",
                             [ev(f"kinds: {dict(kinds)}")], data={"kind": top}, category="worldbuilding"))
        elif len(kinds) >= 3:
            S.append(f"{len(kinds)} kinds of place across {len(named)} named locations (variety {e:.2f}).")
    if regions:
        S.append(f"The world is organised into {len(regions)} regions: " + ", ".join(f"{r} ({n})" for r, n in regions.most_common(5)) + ".")
    for mp in M.get("maps", []):
        metrics.setdefault("tile_maps", []).append({"file": mp["file"], "size": [mp.get("width"), mp.get("height")], "layers": len(mp.get("layers", []))})
        if mp.get("grid") and mp.get("width"):
            filled = sum(1 for v in mp["grid"] if v); metrics.setdefault("solid_share", {})[mp["file"]] = round(filled / max(1, len(mp["grid"])), 2)
    return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": F, "strengths": S, "coverage": cov, "viz": viz}
