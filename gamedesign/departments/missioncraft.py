"""MISSIONCRAFT: objectives, variety, repetition, pacing, escalation, alternate solutions, optional goals,
rewards, failure and consequences — measured from mission/quest/job definitions."""
from collections import Counter
from .base import finding, entropy_norm, cv, spearman, median, mean, names_list, pct, topo_depth, words, is_travel
from ..evidence import cite, ev

NAME, TITLE, CATEGORY = "missioncraft", "MISSIONCRAFT", "mission"


def analyse(M, ctx):
    F, S = [], []
    ms = [m for m in M["missions"] if not m.get("chain")]
    chains = [m for m in M["missions"] if m.get("chain")]
    sig = ctx.get("signals", {})
    metrics = {"missions": len(ms), "guided_chains": len(chains)}
    cov = {"missions": bool(ms)}
    viz = {}
    if not ms:
        note = "No mission, quest or job definitions were found as data." + (f" {len(chains)} guided step chain(s) were found and are assessed by ExperienceCraft (onboarding)." if chains else "")
        return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": [], "strengths": [], "coverage": cov, "viz": viz, "note": note}
    objs = [(m, o) for m in ms for o in m["objectives"]]
    verbs = Counter(o["verb"] for _, o in objs)
    fams = Counter(m.get("kind") or "unlabelled" for m in ms)
    per = [len(m["objectives"]) for m in ms]
    metrics.update({"objectives": len(objs), "objectives_per_mission": [min(per), round(mean(per), 1), max(per)], "verbs": dict(verbs.most_common()),
                    "verb_variety": round(entropy_norm(verbs), 2), "families": dict(fams)})
    viz["verbs_by_mission"] = [{"id": m["id"], "title": m["title"], "kind": m.get("kind"), "verbs": [o["verb"] for o in m["objectives"]]} for m in ms]
    # ------------------------------------------------------- travel-heavy objectives
    travel = [(m, o) for m, o in objs if is_travel(o["verb"])]
    metrics["travel_share"] = round(len(travel) / max(1, len(objs)), 2)
    if len(objs) >= 8 and len(travel) / len(objs) >= 0.4:
        F.append(finding(NAME, "travel_heavy", f"{pct(len(travel) / len(objs))} of all objectives are 'go somewhere'",
                         "major" if len(travel) / len(objs) >= 0.5 else "minor",
                         f"{len(travel)} of {len(objs)} objectives across {len(ms)} missions are travel verbs ({', '.join(sorted({o['verb'] for _, o in travel}))}). Travel is the connective tissue, but here it is the most common thing a mission asks for.",
                         "Players remember missions by what they did when they arrived. When most steps are 'go to X', missions blur together and the interesting verbs get a small share of play time.",
                         [cite(m, f"{m['title']}: '{o.get('text') or o['verb']}'") for m, o in travel[:6]],
                         data={"share": len(travel) / len(objs), "examples": [f"{m['title']}: {o.get('text') or o['verb']}" for m, o in travel[:4]],
                               "verbs": [v for v, _ in verbs.most_common() if not is_travel(v)][:6]}, category="mission"))
    # ------------------------------------------------------- dominant verb
    top_v, top_n = verbs.most_common(1)[0]
    if len(objs) >= 6 and top_n / len(objs) >= 0.35 and not is_travel(top_v):
        F.append(finding(NAME, "objective_repetition", f"'{top_v}' is {pct(top_n / len(objs))} of all objectives", "minor",
                         f"{top_n} of {len(objs)} objectives use the verb '{top_v}'.", "One verb doing most of the work makes the mission set feel like one mission with different names.",
                         [cite(m, f"{m['title']}: {o.get('text') or top_v}") for m, o in objs if o["verb"] == top_v][:5], data={"verb": top_v, "share": top_n / len(objs)}, category="mission"))
    # ------------------------------------------------------- skeleton repetition
    sk = Counter(tuple("T" if is_travel(o["verb"]) else o["verb"] for o in m["objectives"]) for m in ms)
    dup = [(k, n) for k, n in sk.items() if n >= 2 and len(k) >= 1]
    shared = sum(n for _, n in dup)
    metrics["unique_structures"] = f"{len(sk)}/{len(ms)}"
    if dup and shared / len(ms) >= 0.25:
        k, n = max(dup, key=lambda x: x[1])
        same = [m for m in ms if tuple("T" if is_travel(o["verb"]) else o["verb"] for o in m["objectives"]) == k]
        F.append(finding(NAME, "skeleton_repetition", f"{n} missions share the same structure: {' → '.join('travel' if x == 'T' else x for x in k)}",
                         "major" if shared / len(ms) >= 0.4 else "minor",
                         f"{names_list([m['title'] for m in same])} have an identical sequence of objective types. {shared} of {len(ms)} missions repeat a structure another mission already uses.",
                         "When the structure repeats, players stop reading the brief: they already know what will happen. The fiction changes, the decisions do not.",
                         [cite(m, f"{m['title']}: {' → '.join(o['verb'] for o in m['objectives'])}") for m in same[:6]],
                         entities=[m["id"] for m in same], data={"skeleton": ["travel" if x == "T" else x for x in k], "missions": [m["title"] for m in same], "share": shared / len(ms), "key": "_".join(m["id"] for m in same[:2])}, category="mission"))
    else:
        S.append(f"{len(sk)} distinct objective structures across {len(ms)} missions.")
    # ------------------------------------------------------- short missions
    short = [m for m in ms if len(m["objectives"]) <= 2]
    if len(ms) >= 5 and len(short) / len(ms) >= 0.3:
        F.append(finding(NAME, "thin_missions", f"{len(short)} missions have two objectives or fewer", "minor",
                         f"{names_list([m['title'] for m in short])} are a single trip and a single action.",
                         "A one-beat mission has no middle: no complication, no decision, no reversal. It works as a palate cleanser, not as the bulk of a mission set.",
                         [cite(m, f"{m['title']}: {[o['verb'] for o in m['objectives']]}") for m in short[:6]], entities=[m["id"] for m in short],
                         data={"missions": [m["title"] for m in short]}, category="mission"))
    # ------------------------------------------------------- family balance
    if len(ms) >= 5 and len(fams) >= 2:
        lone = [f for f, n in fams.items() if n == 1]
        topf, nf = fams.most_common(1)[0]
        if nf / len(ms) >= 0.5:
            F.append(finding(NAME, "family_imbalance", f"Half the missions are '{topf}'", "minor", f"{nf} of {len(ms)} missions belong to '{topf}'; " + (f"{names_list(lone)} have one mission each." if lone else ""),
                             "Mission families are the player's mental menu of what this game is. An unbalanced menu under-delivers on the fantasies the others promise.",
                             [ev(f"families: {dict(fams)}")], data={"family": topf, "lone": lone}, category="variety"))
        elif lone:
            S.append(f"{len(fams)} mission families; " + ", ".join(f"{f} ({n})" for f, n in fams.most_common()) + ".")
    # ------------------------------------------------------- alternate solutions / optional objectives
    alt = [(m, o) for m, o in objs if (o.get("mode") == "any" and o.get("count", 0) > 1) or len(o.get("options") or []) > 1]
    opt = [(m, o) for m, o in objs if o.get("optional")]
    metrics["objectives_with_alternatives"] = len(alt); metrics["optional_objectives"] = len(opt)
    if len(objs) >= 6 and len(alt) / len(objs) < 0.2:
        F.append(finding(NAME, "single_solution", f"Only {len(alt)} of {len(objs)} objectives offer more than one way to complete them",
                         "major" if not alt else "minor",
                         "Almost every objective has exactly one target and one method in its definition" + (f"; the exceptions are {names_list([m['title'] for m, _ in alt])}." if alt else "."),
                         "Alternate solutions are where players express themselves. Without them, skill shows only as speed, and every player has the same story to tell.",
                         [cite(m, f"{m['title']}: {o.get('text') or o['verb']} (one target)") for m, o in objs if (m, o) not in alt][:5],
                         data={"alt": len(alt), "total": len(objs), "examples": [m["title"] for m, _ in alt][:3]}, category="agency"))
    elif alt:
        S.append(f"{len(alt)} objectives can be completed more than one way (any-of targets or a choice of vehicle).")
    if len(objs) >= 6 and not opt:
        F.append(finding(NAME, "no_optional", "No optional or bonus objectives", "minor",
                         f"None of the {len(objs)} objectives is marked optional or bonus.",
                         "Optional objectives let experts set their own bar and give curious players a reason to linger without forcing everyone to.",
                         [ev(f"{len(ms)} missions; 0 objectives with optional/bonus fields", file=ms[0]["ev"]["file"], line=ms[0]["ev"]["line"], symbol=ms[0]["collection"])], data={}, category="agency"))
    # ------------------------------------------------------- rewards
    rk = Counter(k for m in ms for k in m["reward"])
    if rk:
        cur = rk.most_common(1)[0][0]
        vals = [m["reward"].get(cur) for m in ms]
        effort = [len(m["objectives"]) + 0.5 * len({o["verb"] for o in m["objectives"]}) for m in ms]
        c, rho = cv(vals), spearman(vals, effort)
        metrics["reward_currency"] = cur; metrics["reward_cv"] = round(c, 2) if c is not None else None; metrics["reward_effort_rank_corr"] = round(rho, 2) if rho is not None else None
        viz["rewards"] = [{"id": m["id"], "title": m["title"], "reward": m["reward"].get(cur), "effort": e} for m, e in zip(ms, effort)]
        pairs = [(m, v, e) for m, v, e in zip(ms, vals, effort) if v is not None]
        if len(pairs) >= 4 and ((c is not None and c < 0.15) or (rho is not None and rho < 0.2)):
            ratio = sorted(pairs, key=lambda x: x[1] / x[2])
            low, high = ratio[0], ratio[-1]
            F.append(finding(NAME, "reward_effort", "Rewards do not track effort", "minor",
                             f"Across {len(pairs)} missions the {cur} reward " + (f"barely varies (CV {c:.2f})" if c is not None and c < 0.15 else f"is not ordered by effort (rank correlation {rho:.2f})") +
                             f". {low[0]['title']} pays {low[1]:g} for {len(low[0]['objectives'])} objectives; {high[0]['title']} pays {high[1]:g} for {len(high[0]['objectives'])}.",
                             "Players learn the economy fast. When the long mission pays like the short one, the optimal play is to skip the content the designers worked hardest on.",
                             [cite(m, f"{m['title']}: {cur} {v:g}, {len(m['objectives'])} objectives") for m, v, _ in pairs[:6]],
                             data={"currency": cur, "low": low[0]["title"], "low_v": low[1], "high": high[0]["title"], "high_v": high[1], "rho": rho, "cv": c}, category="progression"))
        elif len(pairs) >= 4:
            S.append(f"{cur} rewards scale with effort (rank correlation {rho:.2f})." if rho is not None else f"{cur} rewards vary across missions.")
    # ------------------------------------------------------- failure and recovery
    fail_defs = [m for m in ms if m.get("fails")]
    fail_sig = sig.get("game_over", {}).get("count", 0)
    metrics["missions_with_fail_conditions"] = len(fail_defs)
    if not fail_defs and len(ms) >= 4:
        F.append(finding(NAME, "no_failure", "Missions define no way to fail", "minor" if fail_sig else "major",
                         "No mission definition has a fail condition, time limit or loss state" + (f"; the source has {fail_sig} fail-state references, so failure may live in code outside the mission data." if fail_sig else "."),
                         "Stakes come from the possibility of losing something. Without a fail state, tension is only implied by the fiction, and players learn they can ignore it.",
                         [ev(f"{len(ms)} mission definitions, 0 with fail/timer/limit fields", file=ms[0]["ev"]["file"], line=ms[0]["ev"]["line"], symbol=ms[0]["collection"])],
                         level="inferred", data={"fail_signals": fail_sig}, category="difficulty"))
    # ------------------------------------------------------- dependency graph, escalation, consequences
    depth, dangling, cyc = topo_depth(ms)
    metrics["dependency_depth"] = max(depth.values()) if depth else 0
    metrics["roots"] = sum(1 for m in ms if not m["requires"])
    viz["graph"] = {"nodes": [{"id": m["id"], "title": m["title"], "kind": m.get("kind"), "depth": depth.get(m["id"], 0), "objectives": len(m["objectives"]),
                               "reward": next(iter(m["reward"].values()), None), "dynamic": m.get("dynamic")} for m in ms],
                    "edges": [[r, m["id"]] for m in ms for r in m["requires"]]}
    for mid, r in dangling:
        m = next(x for x in ms if x["id"] == mid)
        F.append(finding(NAME, "dangling_requires", f"{m['title']} requires '{r}', which does not exist", "critical",
                         f"Mission {mid} lists '{r}' in its prerequisites, but no mission has that id. If the game checks prerequisites, this mission can never unlock.",
                         "An unreachable mission is content players can see promised and never get.", [cite(m, f"requires: {m['requires']}")], level="source_verified",
                         entities=[mid], data={"mission": m["title"], "missing": r, "key": mid}, category="mission"))
    for mid in cyc:
        m = next(x for x in ms if x["id"] == mid)
        F.append(finding(NAME, "requires_cycle", f"{m['title']} is part of a prerequisite cycle", "critical", f"Following 'requires' from {mid} leads back to itself.",
                         "A cycle locks every mission in it.", [cite(m, f"requires: {m['requires']}")], level="source_verified", entities=[mid], data={"mission": m["title"], "key": mid}, category="mission"))
    if metrics["dependency_depth"] >= 2:
        by_d = {}
        for m in ms:
            if not m.get("dynamic"): by_d.setdefault(depth[m["id"]], []).append(len(m["objectives"]))
        seq = [mean(by_d[d]) for d in sorted(by_d)]
        metrics["objectives_by_depth"] = [round(x, 1) for x in seq]
        if len(seq) >= 3 and seq[-1] <= seq[0]:
            F.append(finding(NAME, "flat_escalation", "Missions do not grow more complex as the campaign advances", "minor",
                             f"Average objectives per mission by unlock depth: {', '.join(f'{x:.1f}' for x in seq)}. The deepest missions are no more involved than the first.",
                             "Escalation is the promise that mastery leads somewhere. If late missions ask no more than early ones, skill has nowhere to go.",
                             [ev(f"depth → mean objectives: {dict(zip(sorted(by_d), [round(x, 1) for x in seq]))}")], data={"seq": seq}, category="progression"))
        elif len(seq) >= 2 and seq[-1] > seq[0]:
            S.append(f"Missions grow from {seq[0]:.1f} to {seq[-1]:.1f} objectives on average as they unlock.")
    leaf = [m for m in ms if not any(m["id"] in x["requires"] for x in ms) and not m.get("flags") and not m.get("dynamic")]
    metrics["dead_end_missions"] = len(leaf)
    if len(ms) >= 5 and len(leaf) / len(ms) >= 0.5:
        F.append(finding(NAME, "no_consequence", f"{len(leaf)} missions change nothing when completed", "minor",
                         f"{names_list([m['title'] for m in leaf])} unlock no other mission and set no world state in their definitions (rewards aside).",
                         "Consequence is what makes a mission feel like it mattered. When the world is the same afterwards, the mission is a transaction.",
                         [cite(m, f"{m['title']}: no mission requires it, no flags") for m in leaf[:6]], entities=[m["id"] for m in leaf],
                         data={"missions": [m["title"] for m in leaf]}, category="agency"))
    # ------------------------------------------------------- briefing clarity
    bw = [(m, words(m.get("brief"))) for m in ms]
    long = [(m, w) for m, w in bw if w > 45]; none = [m for m, w in bw if w == 0]
    metrics["brief_words_median"] = median([w for _, w in bw])
    if none and len(none) / len(ms) >= 0.3:
        F.append(finding(NAME, "missing_briefs", f"{len(none)} missions have no briefing text", "minor", f"{names_list([m['title'] for m in none])} have no brief/description field.",
                         "The brief is the contract with the player: what, where, why. Without it, players guess.", [cite(m, "no brief") for m in none[:5]], data={}, category="mission"))
    if long:
        F.append(finding(NAME, "long_briefs", f"{len(long)} briefings run past 45 words", "info", f"{names_list([m['title'] for m, _ in long])} have long briefs ({', '.join(str(w) for _, w in long[:4])} words).",
                         "On a phone, players read about a sentence before they act. Long briefs hide the objective inside the fiction.", [cite(m, f"{w} words") for m, w in long[:4]], data={}, category="mission"))
    viz["timeline"] = [{"id": m["id"], "title": m["title"], "depth": depth.get(m["id"], 0), "objectives": len(m["objectives"]), "words": m.get("words", 0),
                        "characters": m.get("characters", []), "kind": m.get("kind"), "dynamic": m.get("dynamic")} for m in ms]
    return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": F, "strengths": S, "coverage": cov, "viz": viz}
