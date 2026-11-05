"""PROGRESSIONCRAFT: difficulty curves, stage escalation, unlock trees, reward pacing, economy, long-term
motivation and replayability — measured from stage tables (waves, eras, levels, nights), upgrade/unlock/item
definitions, milestone conditions and mission rewards."""
import re
from collections import Counter
from .base import finding, median, mean, names_list, pct
from ..evidence import cite, ev

NAME, TITLE, CATEGORY = "progressioncraft", "PROGRESSIONCRAFT", "progression"
DIFF_FIELD = re.compile(r"hp|health|resolve|growth|need|spawn|count|speed|drain|damage|enemies|duration|target|cost|threshold|mutations|population|at$|level", re.I)


def curves(M):
    by = {}
    for s in M["stages"]: by.setdefault(s["collection"], []).append(s)
    out = []
    for sym, st in by.items():
        st = sorted(st, key=lambda s: s["order"])
        if len(st) < 3: continue
        fields = [k for k in st[0]["stats"] if all(k in s["stats"] for s in st) and k not in ("id", "index", "number", "order", "seed")]
        series = {}
        for k in fields:
            vals = [s["stats"][k] for s in st]
            if len(set(vals)) <= 1: continue
            series[k] = vals
        if series:
            out.append({"collection": sym, "labels": [s["name"] for s in st], "series": series, "ev": st[0]["ev"], "mix": [s.get("mix") for s in st]})
    return out


SENTINEL = {99, 999, 9999, 99999}


def _spikes(vals):
    """Steps much larger than the table's typical step. The first step (out of an intro/tutorial entry) and
    steps into sentinel values (99, 999, ... used as 'never' / 'last stage') are not counted."""
    ratios = [(vals[i + 1] / vals[i]) if vals[i] > 0 and vals[i + 1] not in SENTINEL and vals[i + 1] < 1e6 else None for i in range(len(vals) - 1)]
    rr = [r for r in ratios[1:] if r is not None and r > 0]
    if len(rr) < 2: return [], ratios
    md = median(rr)
    sp = [i for i, r in enumerate(ratios) if i > 0 and r is not None and r >= max(1.6, 1.9 * md) and vals[i] > 0]
    return sp, ratios


def analyse(M, ctx):
    F, S = [], []
    sig = ctx.get("signals", {})
    prog = M["progression"]
    metrics = {"stage_tables": 0, "progression_entries": len(prog), "progression_collections": dict(Counter(p["collection"] for p in prog))}
    cov = {"curves": False, "economy": False, "unlocks": bool(prog)}
    viz = {"curves": []}
    # ------------------------------------------------------- difficulty and stage curves
    cs = curves(M)
    metrics["stage_tables"] = len(cs); cov["curves"] = bool(cs)
    for c in cs:
        viz["curves"].append({"collection": c["collection"], "labels": c["labels"], "series": c["series"]})
        for k, vals in c["series"].items():
            if not DIFF_FIELD.search(k): continue
            sp, ratios = _spikes(vals)
            for i in sp[:1]:
                F.append(finding(NAME, "difficulty_spike", f"{c['collection']}: '{k}' jumps {ratios[i]:.1f}× from {c['labels'][i]} to {c['labels'][i + 1]}",
                                 "major" if ratios[i] >= 2.5 else "minor",
                                 f"{k} goes {vals[i]:g} → {vals[i + 1]:g}; the typical step in this table is ×{median([r for r in ratios if r]):.2f}.",
                                 "Players tolerate steady escalation and punish cliffs. A step far larger than the ones before it is where retention curves drop: the player meets a wall, not a challenge.",
                                 [cite({"ev": c["ev"]}, f"{k}: {vals}")], data={"table": c["collection"], "field": k, "from": c["labels"][i], "to": c["labels"][i + 1],
                                                                                "a": vals[i], "b": vals[i + 1], "ratio": ratios[i], "key": f"{c['collection']}_{k}"}, category="difficulty"))
        flat = [i for i in range(len(c["labels"]) - 1) if all(v[i] == v[i + 1] for v in c["series"].values())]
        if flat:
            F.append(finding(NAME, "plateau", f"{c['collection']}: {c['labels'][flat[0]]} and {c['labels'][flat[0] + 1]} are numerically identical", "minor",
                             f"Every tracked value is the same in consecutive entries ({', '.join(c['series'])}).", "A stage that changes no number must change something else (a new mechanic, a new space), or it is repetition.",
                             [cite({"ev": c["ev"]}, "identical rows")], data={"table": c["collection"], "a": c["labels"][flat[0]], "b": c["labels"][flat[0] + 1]}, category="difficulty"))
        mono = [k for k, v in c["series"].items() if all(v[i] <= v[i + 1] for i in range(len(v) - 1)) or all(v[i] >= v[i + 1] for i in range(len(v) - 1))]
        if mono and not any(f["kind"] == "difficulty_spike" and f["data"].get("table") == c["collection"] for f in F):
            S.append(f"{c['collection']} escalates smoothly across {len(c['labels'])} entries ({', '.join(mono[:4])}).")
        mixes = [m for m in c["mix"] if m]
        if len(mixes) >= 3:
            new = [len(set(mixes[i]) - set().union(*mixes[:i])) for i in range(len(mixes))]
            metrics.setdefault("new_enemy_types_per_stage", {})[c["collection"]] = new
            if sum(1 for n in new[1:] if n == 0) >= max(2, len(new) // 2):
                F.append(finding(NAME, "no_new_threats", f"{c['collection']}: most stages introduce no new enemy type", "minor",
                                 f"New enemy types per stage: {new}.", "Escalation by numbers alone feels like the game turning a dial. A new threat per stage gives players a new problem to solve.",
                                 [cite({"ev": c["ev"]}, f"spawn mix per stage: {[sorted(m) for m in mixes]}")], data={"table": c["collection"], "new": new}, category="difficulty"))
    # ------------------------------------------------------- economy: mission income vs prices
    ms = [m for m in M["missions"] if not m.get("chain")]
    cur = Counter(k for m in ms for k in m["reward"]).most_common(1)
    priced = [p for p in prog if p.get("cost")]
    if cur and priced:
        cur = cur[0][0]
        story_income = sum(m["reward"].get(cur, 0) for m in ms if not m.get("dynamic"))
        med_r = median([m["reward"].get(cur) for m in ms if m["reward"].get(cur)])
        costs = sorted(p["cost"] for p in priced)
        metrics.update({"currency": cur, "campaign_income": story_income, "price_range": [costs[0], costs[-1]], "price_total": sum(costs),
                        "missions_per_purchase_median": round(median(costs) / med_r, 1) if med_r else None})
        cov["economy"] = True
        viz["economy"] = {"income": [{"title": m["title"], "v": m["reward"].get(cur, 0), "dynamic": m.get("dynamic")} for m in ms], "prices": [{"name": p["name"], "v": p["cost"], "collection": p["collection"]} for p in priced][:60]}
        if story_income and sum(costs) > 3 * story_income:
            dyn = [m for m in ms if m.get("dynamic")]
            F.append(finding(NAME, "economy_gap", f"Buying everything costs {sum(costs) / story_income:.1f}× what the campaign pays", "major" if not dyn else "minor",
                             f"The non-repeating missions pay {story_income:g} {cur} in total; the {len(priced)} priced unlocks cost {sum(costs):g}." +
                             (f" The gap is meant to be filled by {len(dyn)} repeatable mission(s) ({names_list([m['title'] for m in dyn])})." if dyn else " No repeatable income source was found in the mission data."),
                             "A large gap between income and prices turns the late game into grinding. If repeatable content fills it, that content carries the game's pacing and must be the best-designed part.",
                             [ev(f"campaign income {story_income:g} {cur}"), cite(priced[0], f"{len(priced)} priced entries, {costs[0]:g}–{costs[-1]:g}")],
                             data={"income": story_income, "prices": sum(costs), "currency": cur, "dynamic": [m["title"] for m in dyn]}, category="progression"))
        if med_r and median(costs) / med_r > 4:
            F.append(finding(NAME, "slow_unlocks", f"A typical unlock costs {median(costs) / med_r:.1f} missions of income", "minor",
                             f"Median price {median(costs):g} {cur} against a median mission reward of {med_r:g}.",
                             "Players want a new toy every two or three sessions of play. Four or more missions per unlock reads as a dry spell.",
                             [ev(f"median price {median(costs):g}; median reward {med_r:g}")], data={"ratio": median(costs) / med_r}, category="progression"))
    # ------------------------------------------------------- unlock tree
    if len(prog) >= 6:
        with_req = [p for p in prog if p.get("requires")]
        tiers = {p.get("tier") for p in prog if p.get("tier") is not None} | {p.get("category") for p in prog if p.get("category")}
        metrics["entries_with_prerequisites"] = len(with_req)
        viz["tree"] = {"nodes": [{"id": p["id"], "name": p["name"], "cost": p.get("cost"), "collection": p["collection"], "category": p.get("category")} for p in prog][:120],
                       "edges": [[r, p["id"]] for p in prog for r in p.get("requires", [])]}
        cats = Counter(p["collection"] for p in prog)
        biggest = cats.most_common(1)[0][0]
        grp = [p for p in prog if p["collection"] == biggest]
        if len(grp) >= 6 and not any(p.get("requires") for p in grp) and len({p.get("category") for p in grp}) <= 1 and not any(p.get("tier") is not None for p in grp):
            F.append(finding(NAME, "flat_tree", f"{biggest}: {len(grp)} unlocks with no structure", "minor",
                             f"No entry in {biggest} requires another, and they have no tiers or categories: the order is decided by price alone.",
                             "Structure (tiers, branches, mutually exclusive picks) is what makes an upgrade a decision. A flat price list makes it shopping.",
                             [cite(grp[0], f"{len(grp)} entries, 0 prerequisites")], data={"collection": biggest, "n": len(grp)}, category="progression"))
        elif with_req:
            S.append(f"{len(with_req)} unlocks have prerequisites, so progression has structure beyond price.")
    # ------------------------------------------------------- long-term motivation
    longterm = [p for p in prog if re.search(r"milestone|badge|rank|achiev|goal", p["collection"], re.I)]
    metrics["long_term_goals"] = len(longterm)
    if prog and not longterm and len(ms) >= 4:
        F.append(finding(NAME, "no_long_goals", "No milestones, ranks or badges beyond the mission list", "minor",
                         "Progression data has unlocks but nothing that tracks mastery or long-term goals.", "Long-term goals give the session after the campaign a reason to exist.",
                         [ev(f"progression collections: {sorted({p['collection'] for p in prog})}")], data={}, category="variety"))
    elif longterm:
        S.append(f"{len(longterm)} long-term goals ({names_list(sorted({p['collection'] for p in longterm}))}).")
    # ------------------------------------------------------- replayability
    dyn = [m for m in ms if m.get("dynamic")]
    rep = {"repeatable_missions": len(dyn), "randomness": sig.get("randomness", {}).get("count", 0), "procedural": sig.get("procedural", {}).get("count", 0),
           "daily": sig.get("daily_challenge", {}).get("count", 0), "best_scores": sig.get("highscore", {}).get("count", 0), "seeded": sig.get("determinism", {}).get("count", 0)}
    metrics["replay_sources"] = rep
    has_game_data = bool(ms or M["stages"] or prog)
    if not has_game_data: metrics["replay_sources"] = None
    elif not dyn and not rep["procedural"] and not rep["daily"] and not rep["best_scores"]:
        F.append(finding(NAME, "low_replay", "Little reason to replay after the content is done", "minor",
                         "No repeatable missions, procedural content, daily challenge or best-score tracking were found.", "Replay value comes from variation or from mastery goals. With neither, the game is finished the first time it is finished.",
                         [ev(f"replay sources: {rep}")], data=rep, category="variety"))
    elif any(rep.values()):
        S.append("Replay sources: " + ", ".join(f"{k.replace('_', ' ')} ({v})" for k, v in rep.items() if v) + ".")
    return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": F, "strengths": S, "coverage": cov, "viz": viz}
