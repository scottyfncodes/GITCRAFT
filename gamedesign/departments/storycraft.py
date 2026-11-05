"""STORYCRAFT: cast, dialogue, coherence, pacing of story across the campaign, payoffs, branching, lore.

Measured from character definitions (data, builder calls, dialogue scripts, or names that recur in authored
text — the last labelled inferred), every authored string (briefs, lines, clues, endings, place text) and the
design documents. Coherence checks are factual (a reference to an id that does not exist, a document that
states a count the data contradicts)."""
import re
from collections import Counter
from .base import finding, names_list, pct, words, topo_depth
from ..evidence import cite, ev

NAME, TITLE, CATEGORY = "storycraft", "STORYCRAFT", "narrative"
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
             "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30}
CLAIM_NOUNS = ["mission", "job", "quest", "level", "island", "era", "night", "wave", "ending", "upgrade", "region", "character", "contract", "chapter", "badge", "rank", "milestone"]
CLAIM_RE = re.compile(r"(?<![#\w.-])(\d{1,3}|" + "|".join(NUM_WORDS) + r")\s+(?:[a-z-]+\s)?(" + "|".join(CLAIM_NOUNS) + r")s\b", re.I)
CLAIM_SKIP = re.compile(r"(first|last|every|each|per|top|after|before|step|phase|stage|level|day|night|chapter|act|of the)\s*$", re.I)


def _mentions(corpus, name):
    parts = name.split(); first, last = parts[0], parts[-1]
    pats = [re.escape(name)] + ([re.escape(first)] if len(first) >= 4 and first.lower() not in ("mrs.", "the", "officer", "courier", "captain") else []) \
        + ([re.escape(last)] if len(parts) > 1 and len(last) >= 4 else [])
    rx = re.compile(r"(?<![\w])(" + "|".join(pats) + r")(?![\w])")
    return [c for c in corpus if rx.search(c["text"])]


def _claims(M, ctx):
    """Counts stated in the README / top-level docs vs the collections they describe."""
    out = []
    docs = [d for d in ctx.get("docs", []) if ("/" not in d["file"] and re.match(r"(readme|claude)\.md$", d["file"], re.I)) or re.search(r"^docs/[^/]*(game-design|gdd|design-doc)", d["file"], re.I)]
    seen = set()
    cols = {c["symbol"].lower(): c for c in M["collections"]}
    for d in docs:
        for m in CLAIM_RE.finditer(d["text"]):
            n_raw, noun = m.group(1).lower(), m.group(2).lower()
            n = int(n_raw) if n_raw.isdigit() else NUM_WORDS.get(n_raw)
            if not n or n < 2 or n > 200 or CLAIM_SKIP.search(d["text"][max(0, m.start() - 20):m.start()]): continue
            col = next((c for s, c in cols.items() if s.rstrip("s") == noun or s == noun + "s" or s.replace("_", "") == noun + "s"), None)
            if not col: continue
            actual = col["items"]
            ln = d["text"].count("\n", 0, m.start()) + 1
            ctx_txt = d["text"][max(0, m.start() - 60):m.end() + 60].replace("\n", " ")
            if (d["file"], n, noun) in seen: continue
            seen.add((d["file"], n, noun))
            out.append({"doc": d["file"], "line": ln, "stated": n, "noun": noun, "symbol": col["symbol"], "file": col["file"], "col_line": col["line"], "actual": actual, "context": ctx_txt.strip()})
    return out


def analyse(M, ctx):
    F, S = [], []
    corpus = M["corpus"]
    chars = M["characters"]
    data_chars = [c for c in chars if c.get("source") != "text"]
    metrics = {"characters": len(chars), "characters_from_data": len(data_chars), "authored_strings": len(corpus), "authored_words": sum(words(c["text"]) for c in corpus),
               "story_entries": dict(Counter(s["category"] for s in M["story"]))}
    cov = {"cast": bool(data_chars), "text": bool(corpus)}
    viz = {}
    if not corpus and not chars:
        return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": [], "strengths": [], "coverage": cov, "viz": viz,
                "note": "No authored story text or character data was found; narrative cannot be assessed from this repository."}
    # ------------------------------------------------------- cast development
    cast = []
    for c in chars:
        hits = [h for h in _mentions(corpus, c["name"]) if not h["src"].startswith(f"character {c['id']}")]
        spoken = [s for s in M["story"] if (s.get("speaker") or "").lower() in (c["name"].lower(), c["id"].lower())]
        missions = [m for m in M["missions"] if c["id"] in m.get("characters", [])]
        cast.append({"c": c, "mentions": len(hits), "lines": len(spoken) + len(c.get("lines") or []), "missions": len(missions), "mission_titles": [m["title"] for m in missions]})
    viz["cast"] = [{"id": x["c"]["id"], "name": x["c"]["name"], "role": x["c"].get("role"), "mentions": x["mentions"], "lines": x["lines"], "missions": x["missions"],
                    "source": x["c"].get("source"), "inferred": bool(x["c"].get("inferred"))} for x in cast]
    under = [x for x in cast if x["mentions"] <= 1 and x["lines"] == 0 and x["c"].get("source") != "text"]
    if under and len(data_chars) >= 3:
        F.append(finding(NAME, "underdeveloped_character", f"{len(under)} named characters are barely present in the writing",
                         "major" if len(under) / max(1, len(data_chars)) >= 0.5 else "minor",
                         f"{names_list([x['c']['name'] for x in under])} are defined as characters but appear in at most one authored line and never speak.",
                         "A named character the player meets once is set dressing with a name tag. Each one is an unpaid promise of a relationship.",
                         [cite(x["c"], f"{x['c']['name']}: {x['mentions']} mention(s), 0 lines") for x in under[:6]], entities=[x["c"]["id"] for x in under],
                         data={"names": [x["c"]["name"] for x in under], "roles": [x["c"].get("role") for x in under]}, category="narrative"))
    inferred = [x for x in cast if x["c"].get("source") == "text"]
    if inferred and not data_chars:
        F.append(finding(NAME, "cast_not_data", "The cast exists only in prose", "minor",
                         f"No character definitions were found. {names_list([x['c']['name'] + ' (' + str(x['c'].get('mentions_seen', x['mentions'])) + '×)' for x in inferred])} recur in briefs and lines, so DESIGNCRAFT infers them as the cast.",
                         "Characters that live only in strings cannot have state: they cannot remember the player, change, or react. That caps how much the story can respond to play.",
                         [ev(x["c"]["ev"]["symbol"], "inferred") for x in inferred[:5]], level="inferred", data={"names": [x["c"]["name"] for x in inferred]}, category="narrative"))
    one_scene = [x for x in cast if x["missions"] == 1]
    if len(M["missions"]) >= 4 and len(one_scene) >= 2:
        F.append(finding(NAME, "no_payoff", f"{len(one_scene)} characters appear in a single mission and never return", "minor",
                         "; ".join(f"{x['c']['name']} only in {x['mission_titles'][0]}" for x in one_scene[:5]) + ".",
                         "Recurring characters turn a list of jobs into a community. A second appearance, with a memory of the first, is the cheapest payoff in narrative design.",
                         [cite(x["c"], f"{x['c']['name']}: 1 mission") for x in one_scene[:5]], entities=[x["c"]["id"] for x in one_scene],
                         data={"pairs": [[x["c"]["name"], x["mission_titles"][0]] for x in one_scene][:6]}, category="narrative"))
    recurring = [x for x in cast if x["missions"] >= 2]
    if recurring: S.append(f"{names_list([x['c']['name'] for x in recurring])} recur across missions.")
    # ------------------------------------------------------- dialogue voice
    lines = [s for s in M["story"] if s["category"] in ("dialogue", "bark")]
    if lines:
        attributed = [s for s in lines if s.get("speaker")]
        metrics["dialogue_lines"] = len(lines); metrics["attributed_lines"] = len(attributed)
        spk = Counter(s["speaker"] for s in attributed)
        metrics["speakers"] = dict(spk.most_common(8))
        if len(lines) >= 8 and len(attributed) / len(lines) < 0.3:
            F.append(finding(NAME, "unattributed_dialogue", f"{pct(1 - len(attributed) / len(lines))} of dialogue lines have no speaker", "minor",
                             f"{len(lines) - len(attributed)} of {len(lines)} lines in {names_list(sorted({s['collection'] for s in lines}))} carry no speaker field.",
                             "Lines without a speaker are a chorus. Players attach to voices, and a voice needs a consistent owner.",
                             [cite(s, f"\"{s['texts'][0][:80]}\"") for s in lines if not s.get("speaker")][:4], data={"collections": sorted({s['collection'] for s in lines})}, category="narrative"))
        elif spk:
            S.append(f"{len(spk)} speaking characters; most lines: {', '.join(f'{k} ({v})' for k, v in spk.most_common(3))}.")
    # ------------------------------------------------------- coherence: references and claims
    ids = {s["id"] for s in M["story"]} | {m["id"] for m in M["missions"]} | {c["id"] for c in chars} | {p["id"] for p in M["places"]}
    ids |= {s["title"] for s in M["story"] if s.get("title")}
    broken, seenb = [], set()
    for s in M["story"]:
        for l in s.get("links", []):
            k = (s.get("title") or s["id"], l)
            if l not in ids and not l.startswith(("$", "-")) and k not in seenb: seenb.add(k); broken.append((s, l))
    for s, l in broken[:4]:
        F.append(finding(NAME, "dangling_reference", f"{s['category'].title()} '{s['id']}' points at '{l}', which is not defined", "major",
                         f"{s['collection']} entry {s['id']} references {l!r}; no story entry, mission, character or place has that id.",
                         "A broken story link means a beat that can never fire or a clue that leads nowhere.", [cite(s, f"links: {s.get('links')}")], level="source_verified",
                         entities=[s["id"]], data={"entry": s["id"], "missing": l, "key": s["id"]}, category="narrative"))
    claims = _claims(M, ctx)
    wrong = [c for c in claims if c["stated"] != c["actual"]]
    metrics["doc_claims_checked"] = len(claims)
    for c in wrong[:3]:
        F.append(finding(NAME, "doc_contradiction", f"{c['doc']} says {c['stated']} {c['noun']}s; the data defines {c['actual']}", "minor",
                         f"\"…{c['context']}…\" ({c['doc']}:{c['line']}) vs {c['actual']} entries in {c['symbol']} ({c['file']}:{c['col_line']}).",
                         "When the design document and the game disagree, one of them is wrong, and players notice the version they were promised.",
                         [ev(f"stated {c['stated']}", "source_verified", c["doc"], c["line"]), ev(f"{c['symbol']} has {c['actual']} entries", "source_verified", c["file"], c["col_line"], c["symbol"])],
                         level="source_verified", data={"doc": c["doc"], "stated": c["stated"], "actual": c["actual"], "noun": c["noun"], "key": f"{c['noun']}_{c['line']}"}, category="narrative"))
    if claims and not wrong: S.append(f"{len(claims)} counts stated in the docs match the data.")
    # ------------------------------------------------------- branching and endings
    endings = [s for s in M["story"] if s["category"] == "ending"]
    choices = sum(b.get("choices", 0) for b in M.get("branching", []))
    metrics["endings"] = len(endings); metrics["scripted_choices"] = choices
    agency_doc = sum(len(re.findall(r"\b(choice|choose|consequence|decide|branch)", d["text"], re.I)) for d in ctx.get("docs", [])[:12])
    if not endings and not choices and len(M["missions"]) >= 4:
        F.append(finding(NAME, "linear_story", "One story path: no endings, choices or branches in the data", "minor" if not agency_doc else "major",
                         "No ending definitions and no scripted choices were found" + (f", although the docs talk about choice or consequence {agency_doc} times." if agency_doc else "."),
                         "A fixed story is fine when it is the point. When the docs promise consequence, players will look for the fork and find none.",
                         [ev("0 endings, 0 choices in data; " + (f"{agency_doc} doc mentions of choice/consequence" if agency_doc else "docs do not promise branching"))],
                         data={"doc_mentions": agency_doc}, category="agency"))
    elif endings:
        S.append(f"{len(endings)} endings defined ({names_list([e.get('title') or e['id'] for e in endings])}).")
    # ------------------------------------------------------- pacing across the campaign
    ms = [m for m in M["missions"] if not m.get("chain")]
    if len(ms) >= 4:
        depth, _, _ = topo_depth(ms)
        order = sorted(ms, key=lambda m: (depth.get(m["id"], 0), m.get("number") or 0, m["order"]))
        w = [m.get("words", 0) for m in order]
        third = max(1, len(w) // 3)
        tot = sum(w) or 1
        early, mid, late = sum(w[:third]) / tot, sum(w[third:-third]) / tot, sum(w[-third:]) / tot
        metrics["story_words_by_third"] = [round(early, 2), round(mid, 2), round(late, 2)]
        viz["story_density"] = [{"id": m["id"], "title": m["title"], "words": m.get("words", 0), "characters": len(m.get("characters", []))} for m in order]
        if early >= 0.55 or late <= 0.15:
            F.append(finding(NAME, "story_pacing", "Story is front-loaded" if early >= 0.55 else "The campaign's last third carries little story",
                             "minor", f"Share of mission text by campaign third: {pct(early)} early, {pct(mid)} middle, {pct(late)} late.",
                             "Story should rise toward the end of a campaign: the late missions are where setups pay off. When the words run out early, the ending arrives without weight.",
                             [ev(f"mission words in order: {w}")], data={"early": early, "late": late, "last": [m["title"] for m in order[-2:]]}, category="narrative"))
    people_less = [m for m in ms if not m.get("characters")]
    if len(ms) >= 4 and chars and len(people_less) / len(ms) >= 0.6:
        F.append(finding(NAME, "faceless_missions", f"{len(people_less)} of {len(ms)} missions mention no character", "minor",
                         f"The briefs, objectives and completion text of {names_list([m['title'] for m in people_less])} name none of the {len(chars)} characters.",
                         "Players care about outcomes for people. A mission with nobody in it is a chore, however good the verbs are.",
                         [cite(m, f"{m['title']}: no character named") for m in people_less[:5]], entities=[m["id"] for m in people_less],
                         data={"missions": [m["title"] for m in people_less], "cast": [c["name"] for c in chars][:5]}, category="narrative"))
    # ------------------------------------------------------- relationships: co-mention in the same authored string
    pair = Counter()
    for c in corpus:
        present = [x["c"]["name"] for x in cast if re.search(r"(?<![\w])" + re.escape(x["c"]["name"].split()[0] if len(x["c"]["name"].split()[0]) >= 4 else x["c"]["name"]) + r"(?![\w])", c["text"])]
        for i in range(len(present)):
            for j in range(i + 1, len(present)): pair[tuple(sorted((present[i], present[j])))] += 1
    viz["relations"] = [[a, b, n] for (a, b), n in pair.most_common(40)]
    lore = [p for p in M["places"] if p.get("blurb")]
    metrics["places_with_lore"] = len(lore)
    return {"dept": NAME, "title": TITLE, "metrics": metrics, "findings": F, "strengths": S, "coverage": cov, "viz": viz}
