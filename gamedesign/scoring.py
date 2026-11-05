"""Phase 6: the 100-point DESIGNCRAFT assessment.

  Level design 15 · Mission design 15 · Narrative and storytelling 15 · Progression and pacing 15
  Player agency and choices 10 · Difficulty and balance 10 · Worldbuilding and immersion 10 · Variety and replayability 10

Each category is the mean of its criteria (0..1) times its points. A criterion whose data is missing is
`untested`: it earns nothing, and the category reports a ceiling (the score if every untested criterion were
perfect) and a lower coverage, so missing evidence lowers both score and confidence instead of being
assumed good. Confidence is `high` only with simulated or playtested evidence in the category; source facts
and inferred judgement alone give at most `medium`."""

CATEGORIES = [("level", "Level design", 15), ("mission", "Mission design", 15), ("narrative", "Narrative and storytelling", 15),
              ("progression", "Progression and pacing", 15), ("agency", "Player agency and choices", 10), ("difficulty", "Difficulty and balance", 10),
              ("worldbuilding", "Worldbuilding and immersion", 10), ("variety", "Variety and replayability", 10)]


def _c(cid, title, score, evidence, level="source_verified"):
    if score is not None: score = max(0.0, min(1.0, float(score)))
    return {"id": cid, "title": title, "score": None if score is None else round(score, 2), "evidence": evidence, "level": level if score is not None else "untested"}


def criteria(M, R, pc):
    L, Mi, S, P, E = (R[k]["metrics"] for k in ("levelcraft", "missioncraft", "storycraft", "progressioncraft", "experiencecraft"))
    kinds = {}
    for r in R.values():
        for f in r["findings"]: kinds.setdefault(f["kind"], []).append(f)
    sig = {}
    has_missions = Mi.get("missions", 0) > 0
    out = {}
    # ---------------------------------------------------------------- level
    named = L.get("named", 0); used = L.get("named_places_used_by_missions")
    u = (lambda a, b: a / b if b else None)(*map(int, used.split("/"))) if used else None
    empty = L.get("empty_cells")
    e_share = (lambda a, b: a / b)(*map(int, empty.split("/"))) if empty else None
    ret = L.get("return_to_hub")
    r_share = (lambda a, b: a / b if b else None)(*map(int, ret.split("/"))) if ret else None
    out["level"] = [
        _c("level.space", "Missions use the world's named places", u, f"named places used by missions: {used}" if used else "no missions with positioned targets, or no named places"),
        _c("level.density", "No large empty areas", None if e_share is None else 1 - max(0, e_share - 0.3) / 0.5, f"empty grid cells: {empty}" if empty else "no geometry"),
        _c("level.discovery", "Discoveries spread through the world", None if L.get("discovery_gini") is None else 1 - L["discovery_gini"],
           f"discovery Gini {L.get('discovery_gini')}" if L.get("discovery_gini") is not None else "no place contents in data"),
        _c("level.travel", "Missions end where the action is (no forced return legs)", None if r_share is None else 1 - r_share, f"return-to-hub endings: {ret}" if ret else "no mission paths"),
        _c("level.orientation", "Landmarks / navigation aids", None if not L.get("positioned") else (1 if L.get("landmarks", 0) >= 4 else 0.6 if L.get("landmarks", 0) >= 2 else 0.3),
           f"{L.get('landmarks', 0)} landmark-type features"),
        _c("level.variety", "Variety of place types", L.get("place_kind_variety"), f"place-kind variety {L.get('place_kind_variety')}" if L.get("place_kind_variety") is not None else "fewer than five named places"),
    ]
    # ---------------------------------------------------------------- mission
    us = Mi.get("unique_structures")
    out["mission"] = [
        _c("mission.verbs", "Variety of objective types", Mi.get("verb_variety") if has_missions else None, f"verb variety {Mi.get('verb_variety')}, {len(Mi.get('verbs', {}))} verbs"),
        _c("mission.structure", "Missions have distinct structures", (lambda a, b: a / b)(*map(int, us.split("/"))) if us else None, f"unique structures {us}"),
        _c("mission.travel", "Objectives are actions, not only travel", None if not has_missions else 1 - max(0, Mi.get("travel_share", 0) - 0.25) / 0.5, f"travel share {Mi.get('travel_share')}"),
        _c("mission.clarity", "Briefings are present and readable", None if not has_missions else (0.2 if not Mi.get("brief_words_median") else 1 if Mi["brief_words_median"] <= 45 else 0.6),
           f"median brief {Mi.get('brief_words_median')} words; {'missing briefs flagged' if 'missing_briefs' in kinds else 'briefs present'}"),
        _c("mission.failure", "Failure and recovery are designed", None if not has_missions else (1 if Mi.get("missions_with_fail_conditions") else 0.5 if "no_failure" in kinds and kinds["no_failure"][0]["data"].get("fail_signals") else 0.2),
           f"{Mi.get('missions_with_fail_conditions', 0)} missions with fail conditions"),
        _c("mission.rewards", "Rewards track effort", None if Mi.get("reward_effort_rank_corr") is None else (Mi["reward_effort_rank_corr"] + 1) / 2, f"reward/effort rank correlation {Mi.get('reward_effort_rank_corr')}"),
    ]
    # ---------------------------------------------------------------- narrative
    cast = R["storycraft"]["viz"].get("cast", [])
    data_cast = [c for c in cast if c["source"] != "text"]
    # development asks for real presence: mentions, spoken lines and missions, not just a definition
    devs = [min(1.0, (c["mentions"] + 2 * c["lines"] + 3 * c["missions"]) / 12) * (0.6 if c["source"] in ("text", "dialogue") else 1.0) for c in cast]
    dev = (sum(devs) / len(devs)) if devs else None
    in_m = [c for c in cast if c["missions"]]
    n_story = sum((S.get("story_entries") or {}).values())
    out["narrative"] = [
        _c("narrative.cast", "Characters are developed in the writing", dev, f"{len(data_cast)} characters from data, {len(cast) - len(data_cast)} inferred from text", "source_verified" if data_cast else "inferred"),
        _c("narrative.voice", "Dialogue has distinct, attributed voices", None if not S.get("dialogue_lines") else S.get("attributed_lines", 0) / S["dialogue_lines"] * min(1, len([c for c in cast if c["lines"]]) / 4),
           f"{S.get('attributed_lines')}/{S.get('dialogue_lines')} lines attributed, {len([c for c in cast if c['lines']])} speaking characters"),
        _c("narrative.depth", "Narrative content beyond briefs (beats, lines, clues, endings)", None if not S.get("authored_strings") else min(1, n_story / 40), f"{n_story} story entries"),
        _c("narrative.coherence", "References and documented counts are consistent", None if not S.get("authored_strings") else 1 - 0.25 * (len(kinds.get("dangling_reference", [])) + len(kinds.get("doc_contradiction", []))),
           f"{len(kinds.get('dangling_reference', []))} broken links, {len(kinds.get('doc_contradiction', []))} doc/data contradictions, {S.get('doc_claims_checked', 0)} claims checked"),
        _c("narrative.pacing", "Story builds toward the end", None if not S.get("story_words_by_third") else min(1, S["story_words_by_third"][2] / 0.33), f"story by third {S.get('story_words_by_third')}"),
        _c("narrative.payoff", "Characters recur and pay off", None if not in_m else sum(1 for c in in_m if c["missions"] >= 2) / max(3, len(in_m)), f"{sum(1 for c in in_m if c['missions'] >= 2)}/{len(in_m)} characters appear in 2+ missions (3 needed for full credit)"),
    ]
    # ---------------------------------------------------------------- progression
    spikes = len(kinds.get("difficulty_spike", []))
    obd = Mi.get("objectives_by_depth")
    out["progression"] = [
        _c("progression.curves", "Stage curves escalate without cliffs", None if not P.get("stage_tables") else 1 - 0.3 * spikes, f"{P.get('stage_tables', 0)} stage tables, {spikes} spikes"),
        _c("progression.economy", "Income and prices are in proportion", None if not P.get("campaign_income") else min(1, 2 / max(0.01, P["price_total"] / P["campaign_income"])),
           f"prices {P.get('price_total')} vs campaign income {P.get('campaign_income')} {P.get('currency') or ''}"),
        _c("progression.structure", "Unlocks have structure (tiers, prerequisites)", None if P.get("progression_entries", 0) < 6 else (0.4 if "flat_tree" in kinds else 1 if P.get("entries_with_prerequisites") else 0.7),
           f"{P.get('entries_with_prerequisites', 0)} entries with prerequisites"),
        _c("progression.escalation", "Missions escalate across the campaign", None if not obd or len(obd) < 2 else (1 if obd[-1] > obd[0] + 1 else 0.6 if obd[-1] > obd[0] else 0.2), f"objectives by depth {obd}"),
        _c("progression.longterm", "Long-term goals", None if not P.get("progression_entries") else (1 if P.get("long_term_goals", 0) >= 3 else 0.5 if P.get("long_term_goals") else 0.2), f"{P.get('long_term_goals', 0)} milestones/ranks/badges"),
        _c("progression.journey", "The journey has contrast (tension and release)", None if E.get("intensity_range") is None else min(1, E["intensity_range"] / 5), f"intensity range {E.get('intensity_range')}", "inferred"),
    ]
    # ---------------------------------------------------------------- agency
    ag = E.get("agency_sources") or {}
    dead = Mi.get("dead_end_missions")
    out["agency"] = [
        _c("agency.alternatives", "Objectives allow more than one solution", None if not has_missions else min(1, ag.get("alternative_objectives", 0) / max(1, 0.4 * Mi.get("objectives", 1))), f"{ag.get('alternative_objectives', 0)} of {Mi.get('objectives', 0)} objectives"),
        _c("agency.optional", "Optional goals", None if not has_missions else min(1, ag.get("optional_objectives", 0) / max(1, Mi["missions"])), f"{ag.get('optional_objectives', 0)} optional objectives"),
        _c("agency.story", "Story choices or endings", None if not S.get("authored_strings") else (1 if ag.get("endings", 0) >= 2 else 0.8 if ag.get("choices") else 0.2), f"{ag.get('endings', 0)} endings, {ag.get('choices', 0)} choices"),
        _c("agency.consequence", "Missions change the world", None if dead is None or not has_missions else 1 - dead / Mi["missions"], f"{dead} dead-end missions"),
    ]
    # ---------------------------------------------------------------- difficulty
    dsim = [c for c in (pc or {}).get("criteria", []) if c["category"] == "difficulty"]
    out["difficulty"] = [
        _c("difficulty.curve", "No difficulty spikes in stage tables", None if not P.get("stage_tables") else 1 - 0.35 * spikes, f"{spikes} spikes"),
        _c("difficulty.recovery", "Failure has fair recovery", None if not (has_missions or P.get("stage_tables")) else (0.3 if "checkpoints" in kinds else 0.7 if Mi.get("missions_with_fail_conditions") or P.get("stage_tables") else 0.4),
           "checkpoint gap flagged" if "checkpoints" in kinds else "no checkpoint gap flagged", "inferred"),
        _c("difficulty.plateaus", "Every stage changes something", None if not P.get("stage_tables") else 1 - 0.3 * len(kinds.get("plateau", [])) - 0.2 * len(kinds.get("no_new_threats", [])), "plateaus and stages without new threats"),
        _c("difficulty.simulated", "PLAYCRAFT difficulty checks (automated play)", None if not dsim else sum(1 for c in dsim if c["status"] == "pass") / len(dsim), f"{len(dsim)} PLAYCRAFT difficulty criteria", "simulated"),
    ]
    # ---------------------------------------------------------------- worldbuilding
    words = S.get("authored_words", 0); ms = max(1, Mi.get("missions", 0) or 1)
    out["worldbuilding"] = [
        _c("worldbuilding.places", "A world of named places", None if not L.get("places") else min(1, named / 10), f"{named} named places"),
        _c("worldbuilding.lore", "Places carry lore", None if not named else min(1, S.get("places_with_lore", 0) / max(1, 0.5 * named)), f"{S.get('places_with_lore', 0)} places with lore text"),
        _c("worldbuilding.writing", "Authored writing depth", None if not S.get("authored_strings") else min(1, words / 4000), f"{words} authored words"),
        _c("worldbuilding.simulated", "PLAYCRAFT presentation checks (automated play)", None if not [c for c in (pc or {}).get("criteria", []) if c["category"] == "worldbuilding"] else
           (lambda xs: sum(1 for c in xs if c["status"] == "pass") / len(xs))([c for c in pc["criteria"] if c["category"] == "worldbuilding"]), "PLAYCRAFT presentation criteria", "simulated"),
    ]
    # ---------------------------------------------------------------- variety
    from .departments.base import entropy_norm
    fam = Mi.get("families") or {}
    sg = E.get("missions_with_signature_action")
    rep = P.get("replay_sources") or {}
    out["variety"] = [
        _c("variety.families", "Mission families are balanced", None if len(fam) < 2 else entropy_norm(fam), f"families {fam}"),
        _c("variety.signature", "Missions have signature actions", (lambda a, b: a / b if b else None)(*map(int, sg.split("/"))) if sg else None, f"signature missions {sg}", "inferred"),
        _c("variety.replay", "Replay sources", min(1, sum(1 for k in ("repeatable_missions", "procedural", "daily", "best_scores") if rep.get(k)) / 3) if rep else None, f"replay sources {rep}"),
        _c("variety.order", "Variety over time (no long same-kind runs)", None if not has_missions else (0.5 if "same_kind_run" in kinds else 1), "same-kind runs flagged" if "same_kind_run" in kinds else "no long same-kind runs"),
    ]
    return out


def score(M, R, findings, pc):
    crit = criteria(M, R, pc)
    cats, total, ceiling = {}, 0.0, 0.0
    by_cat = {}
    for f in findings: by_cat.setdefault(f.get("category"), []).append(f)
    for cid, title, pts in CATEGORIES:
        cs = crit[cid]
        tested = [c for c in cs if c["score"] is not None]
        s = pts * sum(c["score"] for c in tested) / len(cs)
        ceil = pts * (sum(c["score"] for c in tested) + (len(cs) - len(tested))) / len(cs)
        cov = len(tested) / len(cs)
        strong = any(c["level"] in ("simulated", "playtested") for c in tested)
        conf = "high" if cov >= 0.8 and strong else "medium" if cov >= 0.6 else "low"
        weak = sorted(by_cat.get(cid, []), key=lambda f: {"critical": 0, "major": 1, "minor": 2, "info": 3}[f["severity"]])
        cats[cid] = {"title": title, "max": pts, "score": round(s, 1), "ceiling": round(ceil, 1), "coverage": round(cov, 2), "confidence": conf,
                     "criteria": cs, "weaknesses": [{"id": f["id"], "title": f["title"], "severity": f["severity"]} for f in weak],
                     "evidence_levels": sorted({c["level"] for c in cs})}
        total += s; ceiling += ceil
    cov_all = sum(c["coverage"] * c["max"] for c in cats.values()) / 100
    confs = [c["confidence"] for c in cats.values()]
    overall_conf = "high" if confs.count("high") >= 5 else "medium" if confs.count("low") <= 2 else "low"
    return {"overall": round(total), "ceiling": round(ceiling), "coverage": round(cov_all, 2), "confidence": overall_conf, "categories": cats,
            "note": "Untested criteria earn nothing; the ceiling is the score if they were all perfect. Confidence is high only where automated play or playtests back the source evidence."}
