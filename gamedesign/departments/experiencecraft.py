"""EXPERIENCECRAFT: the combined player experience. It reads the other four departments' reports and the
model, builds a player journey (the campaign in unlock order, with intensity, story density and reward per
step), and reports problems that only appear when systems are considered together. It also imports PLAYCRAFT's
automated play evidence (simulated) where a run exists."""
import re
from collections import Counter
from .base import finding, names_list, pct, topo_depth, spearman, mean, is_travel, words
from ..evidence import cite, ev

NAME, TITLE, CATEGORY = "experiencecraft", "EXPERIENCECRAFT", "experience"
TENSION = re.compile(r"\b(storm|lost|avalanche|fire|danger|chase|hunt|trapped|injur|hurt|dead|die|kill|alarm|cops?|police|seen|caught|raid|attack|boss|night|dark|missing|rescue|stuck|crash|flood|escape|threat|camera)", re.I)


def journey(M):
    ms = [m for m in M["missions"] if not m.get("chain")]
    if not ms: return []
    depth, _, _ = topo_depth(ms)
    order = sorted(ms, key=lambda m: (bool(m.get("dynamic")), depth.get(m["id"], 0), m.get("number") or 0, m["order"]))
    out = []
    for i, m in enumerate(order):
        text = " ".join(filter(None, [m.get("brief"), m.get("alert"), m.get("threat")] + [o.get("text") or "" for o in m["objectives"]]))
        verbs = [o["verb"] for o in m["objectives"]]
        act = [v for v in verbs if not is_travel(v)]
        tension = len(TENSION.findall(text))
        intensity = min(10, round(1.2 * len(set(act)) + 0.6 * len(act) + 1.5 * min(3, tension) + (1 if m.get("fails") else 0), 1))
        out.append({"step": i + 1, "id": m["id"], "title": m["title"], "kind": m.get("kind"), "depth": depth.get(m["id"], 0), "intensity": intensity,
                    "tension_words": tension, "verbs": verbs, "new_verbs": [], "story_words": m.get("words", 0), "characters": m.get("characters", []),
                    "reward": next(iter(m["reward"].values()), None), "dynamic": m.get("dynamic")})
    seen = set()
    for j in out:
        j["new_verbs"] = sorted(set(j["verbs"]) - seen); seen |= set(j["verbs"])
    return out


def analyse(M, ctx):
    F, S = [], []
    R = ctx["reports"]
    pc = ctx.get("playcraft")
    J = journey(M)
    metrics = {"journey_steps": len(J)}
    viz = {"journey": J}
    cov = {"journey": bool(J), "playcraft": bool(pc)}
    kinds = {f["kind"] for r in R.values() for f in r["findings"]}
    # ------------------------------------------------------- tension and release across the journey
    story = [j for j in J if not j["dynamic"]]
    if len(story) >= 4:
        ints = [j["intensity"] for j in story]
        rng = max(ints) - min(ints)
        peak = max(story, key=lambda j: j["intensity"])
        metrics["intensity_range"] = round(rng, 1); metrics["peak"] = peak["title"]
        drops = sum(1 for i in range(1, len(ints)) if ints[i] < ints[i - 1] - 1)
        if rng < 2.5:
            F.append(finding(NAME, "flat_tension", "The campaign has no clear peaks: every mission sits at a similar intensity", "major",
                             f"Estimated intensity per mission (distinct actions, objective count, threat language, fail states) stays within {rng:.1f} points: {', '.join(j['title'] + ' ' + str(j['intensity']) for j in story[:6])}.",
                             "Players feel pacing as contrast. Without quiet missions and spikes, even good missions blend into a flat line, and nothing becomes the moment players tell friends about.",
                             [ev(f"intensity by step {ints}", "inferred")], level="inferred", data={"ints": ints, "titles": [j["title"] for j in story]}, category="progression"))
        elif drops == 0 and len(story) >= 5:
            F.append(finding(NAME, "no_release", "Intensity only climbs: there are no breathers", "minor",
                             f"Mission intensity never drops between consecutive steps ({ints}).", "Tension needs release: a calm mission after a hard one is when players consolidate what they learned.",
                             [ev(f"intensity by step {ints}", "inferred")], level="inferred", data={"ints": ints}, category="progression"))
        else:
            S.append(f"The journey has contrast (intensity range {rng:.1f}); its peak is {peak['title']}.")
        # first impression
        first = story[0]
        metrics["first_mission"] = {"title": first["title"], "objectives": len(first["verbs"]), "distinct_actions": len({v for v in first["verbs"] if not is_travel(v)})}
    # ------------------------------------------------------- onboarding chains
    chains = [m for m in M["missions"] if m.get("chain")]
    for c in chains:
        n = len(c["objectives"]); hints = sum(1 for o in c["objectives"] if o.get("hint"))
        metrics.setdefault("guided_chains", []).append({"name": c["title"], "steps": n, "with_hints": hints})
        if n >= 10:
            F.append(finding(NAME, "long_tutorial", f"The guided chain {c['title']} is {n} steps long", "minor",
                             f"{c['title']} walks the player through {n} sequential steps ({', '.join((o.get('text') or o['verb'])[:30] for o in c['objectives'][:4])}…).",
                             "A long, strictly ordered tutorial delays the moment the player chooses for themselves. Most players decide whether they like a game in that window.",
                             [cite(c, f"{n} steps, {hints} hints")], entities=[c["id"]], data={"chain": c["title"], "steps": n, "first": [o.get("text") for o in c["objectives"][:3]]}, category="experience"))
        elif n:
            S.append(f"Onboarding chain {c['title']}: {n} steps, {hints} with hints.")
    # ------------------------------------------------------- compound friction (needs two departments)
    fr = [k for k in ("return_leg", "travel_heavy", "travel_spike", "reward_effort", "economy_gap") if k in kinds]
    if any(k in kinds for k in ("return_leg", "travel_heavy", "travel_spike")) and any(k in kinds for k in ("reward_effort", "economy_gap")):
        F.append(finding(NAME, "friction_stack", "Travel and reward problems compound", "major",
                         f"Separately minor, together they multiply: {', '.join(fr)}. Players spend their time travelling, and the pay does not recognise the long trips.",
                         "Friction is felt as a total, not per system. A player who rides home after every job and earns the same either way concludes the game does not value their time.",
                         [ev(f"{k} (from {next(r['title'] for r in R.values() if any(f['kind'] == k for f in r['findings']))})", "source_verified") for k in fr],
                         level="inferred", data={"parts": fr}, category="experience"))
    # ------------------------------------------------------- agency across systems
    alt = R.get("missioncraft", {}).get("metrics", {}).get("objectives_with_alternatives", 0)
    opt = R.get("missioncraft", {}).get("metrics", {}).get("optional_objectives", 0)
    endings = R.get("storycraft", {}).get("metrics", {}).get("endings", 0)
    choices = R.get("storycraft", {}).get("metrics", {}).get("scripted_choices", 0)
    free = ctx.get("signals", {}).get("sandbox_mode", {}).get("count", 0)
    metrics["agency_sources"] = {"alternative_objectives": alt, "optional_objectives": opt, "endings": endings, "choices": choices, "free_play_signals": free}
    if J and alt + opt + endings + choices == 0:
        F.append(finding(NAME, "agency_gap", "The player decides how fast, never what or how", "major",
                         "No objective offers alternatives, none is optional, and the story has no endings or choices in the data" + (f"; free play exists ({free} references) but is separate from the missions." if free else "."),
                         "Agency is the difference between playing a game and operating it. Players who cannot choose anything that matters stop forming intentions of their own.",
                         [ev(f"agency sources: {metrics['agency_sources']}", "source_verified")], level="inferred", data=metrics["agency_sources"], category="agency"))
    # ------------------------------------------------------- story vs gameplay
    if len(story) >= 5:
        rho = spearman([j["story_words"] for j in story], [len(set(j["verbs"])) for j in story])
        metrics["story_vs_variety_corr"] = round(rho, 2) if rho is not None else None
        if rho is not None and rho <= -0.3:
            rich = sorted(story, key=lambda j: -j["story_words"])[:2]
            F.append(finding(NAME, "story_gameplay_split", "The most story-heavy missions are the least varied to play", "minor",
                             f"Across the campaign, missions with more story text use fewer kinds of objective (rank correlation {rho:.2f}). {names_list([j['title'] for j in rich])} carry the most words.",
                             "When the story happens in the text and the play happens elsewhere, players skip one of them. The best moments are where a story beat is also a new thing to do.",
                             [ev(f"story words vs distinct verbs per mission: {[(j['story_words'], len(set(j['verbs']))) for j in story]}")], level="inferred",
                             data={"rich": [j["title"] for j in rich]}, category="narrative"))
    # ------------------------------------------------------- memorable moments: signature verbs
    if len(story) >= 4:
        allv = Counter(v for j in story for v in set(j["verbs"]))
        sig_ = [j for j in story if any(allv[v] == 1 and not is_travel(v) for v in j["verbs"])]
        metrics["missions_with_signature_action"] = f"{len(sig_)}/{len(story)}"
        if len(sig_) / len(story) < 0.34:
            F.append(finding(NAME, "no_signature", f"Only {len(sig_)} of {len(story)} missions has an action no other mission uses", "minor",
                             "Most missions are built from the same small set of objective types; few contain a one-off action.",
                             "Memorable missions usually have one thing that happens only there. That is what players name the mission by.",
                             [ev(f"verb use across missions: {dict(allv.most_common(10))}")], level="inferred", data={"common": [v for v, _ in allv.most_common(4)]}, category="variety"))
        else:
            S.append(f"{len(sig_)} of {len(story)} missions contain an action unique to them ({names_list([j['title'] for j in sig_], 3)}).")
        runs = 1; worst = (1, story[0]["kind"])
        for a, b in zip(story, story[1:]):
            runs = runs + 1 if a["kind"] == b["kind"] and a["kind"] else 1
            if runs > worst[0]: worst = (runs, b["kind"])
        if worst[0] >= 3:
            F.append(finding(NAME, "same_kind_run", f"{worst[0]} '{worst[1]}' missions in a row", "minor", f"In unlock order, {worst[0]} consecutive missions are '{worst[1]}'.",
                             "Players need variety over time, not just in total.", [ev(f"kinds in order: {[j['kind'] for j in story]}", "source_verified")], data={"kind": worst[1], "n": worst[0]}, category="variety"))
    # ------------------------------------------------------- PLAYCRAFT evidence (simulated)
    if pc:
        fails = [c for c in pc["criteria"] if c["status"] == "fail"]
        passes = [c for c in pc["criteria"] if c["status"] == "pass"]
        metrics["playcraft"] = {"run": pc["run_id"], "overall": pc["overall"], "simulated_criteria": len(pc["criteria"]), "fail": len(fails), "pass": len(passes)}
        m = pc.get("metrics") or {}
        if m.get("time_to_play_ms") and m["time_to_play_ms"] > 4000:
            F.append(finding(NAME, "slow_start", f"PLAYCRAFT measured {m['time_to_play_ms'] / 1000:.1f} s from load to first input", "minor",
                             f"In PLAYCRAFT run {pc['run_id']} the game took {m['time_to_play_ms'] / 1000:.1f} s before it accepted play (software renderer; real devices are usually faster).",
                             "The first seconds decide whether a mobile player stays. Anything between tap and play should be part of the experience, not a wait.",
                             [ev(f"PLAYCRAFT {pc['run_id']}: time_to_play_ms={m['time_to_play_ms']}", "simulated", pc["file"])], level="simulated", data={"ms": m["time_to_play_ms"]}, category="experience"))
        for c in [c for c in fails if not re.match(r"^(px\.(text|loads)|tech\.|mob\.)", c["id"])][:3]:
            if c["category"] in ("experience", "progression", "difficulty", "variety"):
                F.append(finding(NAME, "playcraft_fail", f"PLAYCRAFT: {c['title']}", "minor", c.get("detail") or c["title"],
                                 "Measured by PLAYCRAFT's automated play of the built game; DESIGNCRAFT reports it beside the design findings so both are read together.",
                                 [ev(f"PLAYCRAFT {pc['run_id']} criterion {c['id']}: {c['status']}", "simulated", pc["file"])], level="simulated",
                                 data={"criterion": c["id"], "key": c["id"]}, category=c["category"]))
    else:
        metrics["playcraft"] = None
    return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": F, "strengths": S, "coverage": cov, "viz": viz}
