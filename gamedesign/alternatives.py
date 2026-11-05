"""Phase 3: the Design Alternatives engine.

For every significant finding (critical, major, minor) it writes three proposals:
  A. conservative  improve the existing design, keep its identity
  B. ambitious     a more meaningful redesign of the system involved
  C. wildcard      an unexpected alternative that could make the game more distinctive
Each proposal has: existing design, problem, why it matters, proposed change (concrete steps that cite the
game's own missions, places, characters, numbers and file:line), expected player experience, implementation
complexity, trade-offs and a validation method with a measurable criterion (metric, current value, target).

The engine is rule-based: design knowledge encoded per finding kind and filled with the game's real content.
Its expected outcomes are therefore labelled `inferred` until a PLAYCRAFT run or a playtest measures them.
For open-ended creative refinement, the Design Lab hands a proposal and its evidence to Claude Code."""
from .departments.base import names_list, pct

VARIANTS = ("conservative", "ambitious", "wildcard")
VLABEL = {"conservative": "A · Conservative", "ambitious": "B · Ambitious", "wildcard": "C · Wild card"}


class G:
    """The game's own vocabulary, so proposals can name real things."""
    def __init__(self, M, reports, title):
        self.title = title
        # people first: names used as proper nouns in the writing, then by presence
        cast = sorted(reports.get("storycraft", {}).get("viz", {}).get("cast", []), key=lambda c: (c["mentions"] == 0, -(2 * c["mentions"] + c["lines"] + 3 * c["missions"])))
        self.cast = [c["name"] for c in cast]
        self.lead = self.cast[0] if self.cast else None
        self.second = self.cast[1] if len(self.cast) > 1 else None
        mv = reports.get("missioncraft", {}).get("metrics", {}).get("verbs", {})
        from .departments.base import is_travel
        self.verbs = [v for v in mv if not is_travel(v)]
        self.vehicles = sorted({o2 for m in M["missions"] for o in m["objectives"] for o2 in (o.get("options") or [])} |
                               {(o.get("text") or "").split(" on the ")[-1].split()[0] for m in M["missions"] for o in m["objectives"] if o["verb"] == "mount" and " on the " in (o.get("text") or "")})
        self.places = [p["name"] for p in M["places"] if p.get("name") and "[" not in p["name"] and p.get("kind") != "interactable"]
        self.regions = sorted({p["region"] for p in M["places"] if p.get("region")}) or [w["name"] for w in M["worlds"]]
        self.missions = [m for m in M["missions"] if not m.get("chain")]
        self.hub = reports.get("levelcraft", {}).get("metrics", {}).get("hub")
        self.currency = reports.get("progressioncraft", {}).get("metrics", {}).get("currency") or reports.get("missioncraft", {}).get("metrics", {}).get("reward_currency")
        self.families = list(reports.get("missioncraft", {}).get("metrics", {}).get("families", {}))
        self.endings = reports.get("storycraft", {}).get("metrics", {}).get("endings", 0)

    def who(self, n=0, alt="a recurring character"):
        return self.cast[n] if len(self.cast) > n else alt

    def place(self, n=0, alt="a place the player already knows"):
        return self.places[n] if len(self.places) > n else alt

    def mission(self, title):
        return next((m for m in self.missions if m["title"] == title), None)


def P(variant, proposal, steps, experience, complexity, why_c, tradeoffs, metric, current, target, playtest):
    return {"variant": variant, "label": VLABEL[variant], "proposal": proposal, "changes": steps, "experience": experience,
            "complexity": complexity, "complexity_why": why_c, "tradeoffs": tradeoffs,
            "validation": {"metric": metric, "current": current, "target": target, "method": playtest}, "evidence_level": "inferred"}


def _ev_where(f):
    e = next((x for x in f["evidence"] if x.get("file")), None)
    return f"{e['file']}:{e['line']}" if e and e.get("line") else (e["file"] if e else "the data")


# --------------------------------------------------------------------------------------------- generators
def g_return_leg(f, g):
    d = f["data"]; ms = d["missions"]; hub = d["hub"]
    return [
        P("conservative", f"Complete missions on arrival at the objective, not on arrival at {hub}.",
          [f"In {', '.join(ms[:3])}: drop the final 'go to {hub}' objective ({_ev_where(f)}).", "Award the reward and play the completion line at the moment the last action succeeds.",
           f"Keep {hub} as the place players return to by choice (to upgrade, rest, pick the next call)."],
          "Missions end on their high point. Players keep momentum and start the next thing from where they are.", "low", "a data change to the objective lists",
          [f"{hub} is visited less, so anything that only happens there is seen less.", "Removes a slice of travel that some players enjoy as downtime."],
          "missions ending with a return leg", f"{len(ms)}/{round(len(ms) / d['share'])}", "0", "PLAYCRAFT pass before/after: time from final action to next mission start; 5-player playtest: ask which missions felt like they ended well."),
        P("ambitious", f"Chain jobs in the field: when a mission ends, the next call arrives where the player is.",
          [f"Replace the return leg in {', '.join(ms[:3])} with a radio hand-off that offers the nearest open mission.",
           "Give each mission an optional 'follow-up' that starts within a short distance of its last objective.",
           f"Make {hub} the place for the day's start and end, with a reason to go back (upgrades, debrief, rest) rather than an obligation."],
          "A session becomes a run of connected jobs across the map, with travel that leads somewhere new instead of back.", "medium",
          "mission selection logic and a few new short follow-up jobs",
          ["Needs a nearest-mission selector and follow-up content.", f"Changes the rhythm from hub-and-spoke to a roaming route; {hub} must earn its visits."],
          "average travel per completed mission", "baseline from LEVELCRAFT mission paths", "−30%", "Structured playtest (6 players, 20 min): count completed missions per session and voluntary returns to the hub."),
        P("wildcard", f"Make the trip home the reward: the return leg becomes a free-form 'run' scored on style or speed, optional.",
          [f"After each of {', '.join(ms[:2])}, offer an optional timed run back to {hub} with a best time per route.", "Skip it with one tap: the mission still completes.",
           "Show best times on the mission board."],
          "The dead trip becomes a self-chosen challenge; players who like the movement get a game inside the game.", "medium", "a timer, route records and UI",
          ["Adds a scoring layer that may not fit a calm tone.", "Must be truly optional or it becomes a chore again."],
          "share of players who take the optional run", "n/a (does not exist)", "≥ 40% at least once", "PLAYCRAFT measures run completion; playtest asks whether the run felt like a reward."),
    ]


def g_unused_space(f, g):
    pl = f["data"]["places"]; a, b = (pl + ["", ""])[:2]
    return [
        P("conservative", f"Route existing missions through the unused places.",
          [f"Move one objective of an existing mission to {a}" + (f" and one to {b}" if b else "") + " (same action, new location).",
           "Add a one-line reason in the brief for why it happens there."],
          f"Players discover {a} through a mission they were going to play anyway.", "low", "target changes in mission data",
          ["Changes travel distances; re-check mission length."], "named places reached by missions", f"{f['data']['used']}/{f['data']['total']}", f"{min(f['data']['total'], f['data']['used'] + 2)}/{f['data']['total']}",
          "LEVELCRAFT re-run (source verified); playtest: can players name the place afterwards?"),
        P("ambitious", f"Give each unused place a purpose: a short mission, a resident, a find.",
          [f"Write one small mission per place for {names_list(pl[:4])}, each using a different action the game already has ({names_list(g.verbs[:4]) or 'existing verbs'}).",
           "Put a cache or collectible at each so free exploration pays off too.", f"Mention each place once in an existing character's lines ({g.who()})."],
          "The world reads as inhabited everywhere, and exploring it becomes a reliable source of small rewards.", "medium", "new mission content and placement",
          ["More content to tune and test.", "Risk of filler if the missions are not distinct."], "named places reached by missions", f"{f['data']['used']}/{f['data']['total']}", f"{f['data']['total']}/{f['data']['total']}",
          "LEVELCRAFT re-run; PLAYCRAFT pass; playtest heat-map of where players go in free play."),
        P("wildcard", f"Hide something at {a} that changes how the player sees the rest of the world.",
          [f"Place one secret at {a} (a document, a view, a person) that reframes an existing mission or character.", "Do not point to it: let a line of dialogue hint at it once.",
           "Track how many players find it."],
          "A rumour-worthy secret: the place becomes a story players pass on.", "low", "one placed item and a few lines",
          ["Most players will never find it, by design."], "players who find the secret unprompted", "0", "10–25%", "Playtest without hints; log discovery."),
    ]


def g_empty_zone(f, g):
    q = f["data"]["quarter"]
    return [
        P("conservative", f"Add landmarks and small finds to the {q} of the map.",
          [f"Place 2–3 visible landmarks in the {q} quarter on lines players already travel.", "Put one small reward at each (a collectible, a view, a line of lore)."],
          "Crossing the area becomes a sequence of small discoveries instead of empty travel.", "low", "placement only",
          ["Adds rendering cost in that area."], "empty grid cells", f"{round(f['data']['share'] * 36)}/36", "≤ 50%", "LEVELCRAFT re-run; playtest: ask players to sketch the map from memory."),
        P("ambitious", f"Build a destination in the {q}: a place with a mission, a person and a reason to return.",
          [f"Design one new location in the {q} with its own mission chain of 2–3 jobs.", f"Connect it to {g.hub or 'the hub'} with a route that has something to see on the way."],
          "The map has a new pole; the empty quarter becomes the place players talk about.", "high", "new level content, art and missions",
          ["Significant art and design cost."], "mission targets in the quarter", "0", "≥ 3", "LEVELCRAFT re-run; PLAYCRAFT pass."),
        P("wildcard", f"Make the emptiness the point: a dangerous or forbidden zone in the {q}.",
          ["Turn the empty area into a hazard zone (weather, patrols, darkness) with one high-value reward at its centre.", "Let players see the reward from the edge."],
          "Emptiness becomes tension: an area players choose to cross for a prize.", "medium", "hazard rules and one reward",
          ["Can frustrate players who wander in by accident."], "players who attempt the crossing", "n/a", "≥ 50% of playtesters", "Playtest observation."),
    ]


def g_travel_spike(f, g):
    d = f["data"]
    return [
        P("conservative", f"Shorten {d['mission']} or add a midpoint.", [f"Move its farthest objective closer, or add a checkpoint/rest stop halfway ({d['distance']} units vs a median {d['median']}).",
                                                                           "Put something to do on the way (a find, a line of dialogue)."],
          "The long mission keeps the rhythm of the others.", "low", "target position changes", ["Loses the sense of a big journey."], "travel distance", str(d["distance"]), f"≤ {round(d['median'] * 2)}", "LEVELCRAFT re-run; PLAYCRAFT time-to-complete."),
        P("ambitious", f"Make {d['mission']} an expedition: the journey has stages and events.", ["Split the route into 2–3 legs, each with its own small event or choice.", "Let a vehicle choice change the route."],
          "The long haul becomes the content: an expedition mission players remember.", "medium", "new mid-route events", ["More content."], "events per 100 units of travel", "0", "≥ 1", "Playtest: perceived length vs actual length."),
        P("wildcard", f"Offer a shortcut that costs something.", [f"Add a risky shortcut on the route of {d['mission']} (faster, but dangerous or paid)."],
          "Players decide how to spend time vs risk.", "medium", "one shortcut route and its risk", ["Needs balancing."], "players who take the shortcut", "n/a", "30–70%", "Playtest choice split."),
    ]


def g_discovery_density(f, g):
    d = f["data"]; e = d.get("empty") or ["the empty places"]
    return [
        P("conservative", "Spread finds out: at least one small find in every named place.", [f"Move one cache from {names_list(d['top'])} to each of {names_list(e[:4])}."],
          "Every stop pays a little; exploring feels consistently worthwhile.", "low", "data placement", ["The richest places lose some of their pull."], "discovery Gini", f"{d['gini']:.2f}", "≤ 0.35", "LEVELCRAFT re-run."),
        P("ambitious", "Tie finds into collections that point across the map.", ["Group finds into sets whose last piece is in an under-visited place.", "Show set progress in the journal."],
          "Finds become a treasure trail; players have a reason to visit every place.", "medium", "set definitions and UI", ["More tracking UI."], "places with at least one find", "baseline", "all named places", "LEVELCRAFT re-run; playtest."),
        P("wildcard", "Let the world move the treasure.", ["Re-roll a few cache locations after each in-game day or storm, announced by a line from a character."],
          "Revisiting known places becomes worthwhile.", "medium", "re-placement logic", ["Less authored control."], "repeat visits per place", "n/a", "↑", "PLAYCRAFT/playtest visit logs."),
    ]


def g_orientation(f, g):
    return [P("conservative", "Add 3–4 tall landmarks visible from most of the map.", ["Place unique silhouettes at the edges and centre.", "Name them in briefs."], "Players navigate by sight.", "low", "art placement",
              ["Art cost."], "landmarks", "< 2", "≥ 4", "Playtest: point to where X is."),
            P("ambitious", "Add a lightweight navigation layer (compass ribbon or waypoint).", ["A compass ribbon with the current objective and named places."], "Players always know which way to go.", "medium", "UI system",
              ["Reduces exploration by eye."], "time lost heading the wrong way", "unmeasured", "−50%", "PLAYCRAFT pass + playtest."),
            P("wildcard", "Navigation through a character: they call out directions in-world.", [f"{g.who()} gives directions relative to landmarks over the radio."], "Navigation becomes characterisation.", "medium", "lines + triggers",
              ["Voice/line cost."], "players who reach the first objective without the map", "unmeasured", "≥ 80%", "Playtest.")]


def g_checkpoints(f, g):
    return [P("conservative", "Add a checkpoint before each fail-able section.", ["Save state at each objective boundary in missions that can fail."], "Failure costs a minute, not a mission.", "low", "save-state at objective boundaries",
              ["Lower stakes."], "replayed time after a failure", "whole mission", "≤ 1 objective", "Playtest with forced failures."),
            P("ambitious", "Failure branches instead of resetting.", ["When an objective fails, continue the mission with a complication (cost, delay, new route)."], "Failure becomes story.", "high", "branching mission logic",
              ["Much more content to author."], "missions that continue after a failure", "0", "≥ 3", "Playtest."),
            P("wildcard", "Let the player place their own checkpoint (a camp, a flare) once per mission.", ["One player-placed checkpoint per mission."], "A tactical decision about risk.", "medium", "checkpoint placement",
              ["Can be exploited."], "players who place it", "n/a", "≥ 70%", "Playtest.")]


def g_environment_variety(f, g):
    k = f["data"]["kind"]
    return [P("conservative", f"Re-dress two '{k}' places as a different kind.", [f"Change the kind/art set of two {k} places (e.g. abandoned, high ground, enclosed)."], "Routes have contrast.", "low", "art set swap", ["Art time."], "most common kind share", "≥ 70%", "≤ 50%", "LEVELCRAFT re-run."),
            P("ambitious", "Introduce one new place type with its own rules.", ["A place type that changes movement or visibility."], "A new space that plays differently.", "high", "new mechanics + art", ["Cost."], "place kinds", "≤ 2", "≥ 3", "LEVELCRAFT + playtest."),
            P("wildcard", f"Let time or weather transform the same {k} places.", ["Night, storm or season variants of existing places."], "Familiar places become new.", "medium", "lighting/weather states", ["Testing matrix grows."], "distinct place states", "1", "≥ 2", "Playtest.")]


def g_travel_heavy(f, g):
    d = f["data"]; ex = d["examples"][:2]; vb = d["verbs"] or g.verbs
    return [
        P("conservative", "Fold travel into the action: arrival completes on doing, not on reaching.",
          [f"Merge pure 'go to' steps into the action that follows (e.g. {ex[0] if ex else 'the first travel step'}).", "Show the destination on the action objective instead.",
           f"Keep separate travel steps only where the route itself is the challenge."],
          "Missions read as a list of things to do; the objective list gets shorter and sharper.", "low", "objective list edits",
          ["Less hand-holding for new players."], "travel share of objectives", pct(d["share"]), "≤ 30%", "MISSIONCRAFT re-run (source verified); PLAYCRAFT time spent travelling vs acting."),
        P("ambitious", "Make travel a verb: give every trip a choice of route, vehicle or risk.",
          [f"For travel steps, accept several vehicles or routes ({names_list(g.vehicles) if g.vehicles else 'foot / vehicle / shortcut'}) with different trade-offs (speed, noise, risk).",
           "Add one event on long routes (weather, a person in trouble, a shortcut).", f"Score routes so experts can optimise them."],
          "Travel becomes a decision, and the decision says something about the player.", "medium", "route events and multi-vehicle objectives",
          ["Balancing routes takes playtesting.", "More events to author."], "objectives with alternatives", "baseline", "≥ 40% of travel steps", "Structured playtest: route choices per player; PLAYCRAFT pass."),
        P("wildcard", f"Remove travel steps entirely and let the player start the action from the map.",
          ["Mission start drops the player at the scene; travel happens only in free play.", f"Use the saved time for one extra action from {names_list(vb[:3]) or 'the existing verbs'}."],
          "A tight, action-dense mission set; the open world is for wandering, missions are for doing.", "medium", "mission start rules",
          ["Loses the sense of a connected world.", "May undermine vehicles as a fantasy."], "action objectives per mission", "baseline", "+1 per mission", "A/B playtest of two mission sets."),
    ]


def g_skeleton_repetition(f, g):
    d = f["data"]; ms = d["missions"]; sk = " → ".join(d["skeleton"])
    v2 = [v for v in g.verbs if v not in d["skeleton"]][:3]
    return [
        P("conservative", f"Give each of {names_list(ms)} one objective the others do not have.",
          [f"Keep the shape ({sk}) but swap one step per mission for a different existing action: {names_list(v2) or 'a different verb'}.", "Write the brief around that one difference."],
          "Each mission has a distinct middle; players remember them separately.", "low", "objective edits", ["Some missions get slightly longer."],
          "missions sharing a structure", f"{len(ms)}", "0", "MISSIONCRAFT re-run; playtest recall: name each mission's key moment."),
        P("ambitious", "Add a mid-mission complication system.",
          [f"Every mission gets one complication after its first objective (new threat, changed target, someone else needs help), drawn from a small authored set.",
           f"Use the game's own world: weather, people ({names_list(g.cast[:3]) or 'characters'}), places ({names_list(g.places[:3])}).", "Complications can be declined for less reward."],
          "Same mission, different story each time; players stay alert because the plan changes.", "high", "a complication system plus 6–10 authored complications",
          ["Systemic content needs testing for bad combinations."], "unique structures", f"{len(set(ms))} share one", "every mission distinct", "PLAYCRAFT pass; playtest surprise rating."),
        P("wildcard", f"Turn the repetition into a ritual: one of these missions repeats deliberately and changes each time.",
          [f"Make {ms[0]} a recurring job whose details (time of day, weather, who is there) change every run, and whose last run pays off a thread."],
          "Repetition becomes meaning: players watch a place change across repeats.", "medium", "variants of one mission", ["Repetition must be clearly intentional."],
          "players who notice the change", "n/a", "≥ 60%", "Playtest interview."),
    ]


def g_objective_repetition(f, g):
    d = f["data"]; v = d["verb"]; alt = [x for x in g.verbs if x != v][:3]
    return [P("conservative", f"Replace a third of the '{v}' objectives with other actions.", [f"Swap to {names_list(alt) or 'other verbs'} where the fiction allows."], "More varied play inside the same missions.", "low", "data edits", ["Fiction must still make sense."], f"'{v}' share", pct(d["share"]), "≤ 25%", "MISSIONCRAFT re-run."),
            P("ambitious", f"Give '{v}' depth: variants with different skill demands.", [f"Introduce 2–3 variants of {v} (timed, precise, under threat)."], f"'{v}' stays, but becomes a skill.", "medium", "variant mechanics", ["Tuning."], "distinct objective types", "baseline", "+3", "PLAYCRAFT + playtest."),
            P("wildcard", f"Retire '{v}' for one act of the game.", [f"Remove {v} from a stretch of missions so its return feels fresh."], "Absence makes it special.", "low", "content ordering", ["Odd if the fiction relies on it."], "consecutive missions without it", "0", "≥ 3", "Playtest.")]


def g_thin_missions(f, g):
    ms = f["data"]["missions"]
    return [P("conservative", f"Add a middle beat to {names_list(ms[:3])}.", ["Insert one action between arrival and completion (inspect, choose, protect)."], "Short missions gain a small story.", "low", "data edits", ["Longer missions."], "missions with ≤2 objectives", str(len(ms)), "≤ 1", "MISSIONCRAFT re-run."),
            P("ambitious", "Merge thin missions into one multi-stage event.", [f"Combine {names_list(ms[:3])} into one event with a shared cause."], "One memorable mission instead of several forgettable ones.", "medium", "rewrite", ["Fewer missions on the board."], "missions with ≤2 objectives", str(len(ms)), "0", "Playtest recall."),
            P("wildcard", "Make thin missions instant 'interruptions' that pop up during other missions.", ["They trigger nearby while doing something else; accept or ignore."], "The world feels alive and busy.", "medium", "interrupt trigger", ["Can feel naggy."], "accepted interruptions", "n/a", "≥ 50%", "PLAYCRAFT + playtest.")]


def g_family_imbalance(f, g):
    d = f["data"]; lone = d.get("lone") or []
    return [P("conservative", f"Add one mission to each under-served family ({names_list(lone) or 'the smaller families'}).", ["Reuse existing places and verbs."], "The promise of each family is kept.", "medium", "new missions", ["Content cost."], f"'{d['family']}' share", "≥ 50%", "≤ 40%", "MISSIONCRAFT re-run."),
            P("ambitious", "Make families converge: a late mission needs every family's skills.", ["A finale that combines all families."], "Every family pays off.", "high", "a finale mission", ["Big mission to build."], "families used by the finale", "1", "all", "Playtest."),
            P("wildcard", f"Let the player pick which family the campaign specialises in.", ["A choice early on weights the board toward one family."], "Personal campaign identity.", "high", "board weighting", ["Players miss content."], "replays with a different pick", "n/a", "≥ 20%", "Telemetry/playtest.")]


def g_single_solution(f, g):
    d = f["data"]
    return [
        P("conservative", "Give key objectives a second valid target or method.",
          ["For each mission's main action, add one alternative (another location, another vehicle, another verb) that also completes it.",
           f"Use the pattern already in the data where it exists ({names_list(d['examples']) or 'none yet'})."],
          "Players make small decisions inside missions; skilled players find their own lines.", "low", "objective data (mode: any / multiple targets)",
          ["Alternatives must be balanced or one will dominate."], "objectives with alternatives", f"{d['alt']}/{d['total']}", f"≥ {max(3, d['total'] // 3)}/{d['total']}", "MISSIONCRAFT re-run; playtest: count distinct solutions per mission."),
        P("ambitious", "Design missions as problems, not instructions.",
          ["State the goal and the constraint in the brief; list no steps.", "Offer three approaches per mission (fast/risky, slow/safe, clever/hidden) through the space and the tools the game already has.",
           "Reward the approach taken differently (money, reputation, a character's opinion)."],
          "Each player has their own story of how they did it; replaying a mission means trying a new approach.", "high", "level design per mission plus approach-aware rewards",
          ["Much more design and testing per mission.", "Harder to onboard."], "approaches used per mission (playtest)", "1", "≥ 2", "Structured playtest with 6+ players; log approach per mission."),
        P("wildcard", f"Hand the plan to a character: {g.who()} proposes a plan, the player can follow or ignore it.",
          [f"{g.who()} suggests an approach over the radio at mission start.", "Following it is safe; ignoring it can be faster and earns a reaction."],
          "Agency gets a social dimension: the player's choices have an audience.", "medium", "lines and two outcomes per mission", ["Writing cost."], "players who deviate from the plan", "n/a", "30–60%", "Playtest."),
    ]


def g_no_optional(f, g):
    return [P("conservative", "Add one optional bonus objective to each mission.", ["A bonus that uses an existing verb in the same place (no damage, under par time, find the extra item)."], "Experts set their own bar; everyone else is unaffected.", "low", "data + UI", ["UI clutter."], "optional objectives", "0", "1 per mission", "MISSIONCRAFT re-run; PLAYCRAFT."),
            P("ambitious", "Optional objectives that change the next mission.", ["Completing a bonus changes a later mission (an ally, a shortcut, a warning)."], "Optional play has consequences.", "medium", "flags between missions", ["State tracking."], "bonus objectives with consequences", "0", "≥ 3", "Playtest."),
            P("wildcard", f"Hidden optional objectives revealed only by {g.who()}'s offhand remarks.", ["Secret bonuses hinted in dialogue."], "Listening pays off.", "low", "lines + hidden checks", ["Few players find them."], "players who find one", "n/a", "≥ 30%", "Playtest.")]


def g_reward_effort(f, g):
    d = f["data"]; c = d["currency"]
    return [
        P("conservative", f"Re-price rewards by effort.",
          [f"Set {c} = base + per-objective + distance bonus. {d['low']} ({d['low_v']:g}) rises; {d['high']} ({d['high_v']:g}) stays or falls.", "Show the expected reward on the mission board."],
          "Players read the board as a set of fair offers; long missions stop feeling like a bad deal.", "low", "reward numbers",
          ["Shifts the economy; re-check upgrade prices."], "reward/effort rank correlation", f"{d['rho']:.2f}" if d.get("rho") is not None else "n/a", "≥ 0.6", "MISSIONCRAFT re-run; PROGRESSIONCRAFT economy check."),
        P("ambitious", "Pay in more than money: rewards that match the mission.",
          ["Each mission family pays a different kind of reward (reputation with a group, a tool, access to a place).", "Hard missions unlock something money cannot buy."],
          "Players choose missions for what they want next, which gives the board strategy.", "medium", "reward types and unlock hooks", ["More economy to balance."], "reward types", "1", "≥ 3", "Playtest: why did you pick that mission?"),
        P("wildcard", "Let the player set the price.", ["Before a mission, choose a harder version for a bigger reward (time limit, no vehicle, bad weather)."],
          "Self-chosen risk; experts make the game harder for themselves.", "medium", "difficulty modifiers per mission", ["Modifier balancing."], "missions played with a modifier", "n/a", "≥ 30%", "PLAYCRAFT + playtest."),
    ]


def g_no_failure(f, g):
    return [P("conservative", "Add a soft fail state to missions with a clock or a threat.", ["A timer or condition that, when missed, completes the mission with a worse outcome (less pay, a worse ending line)."], "Stakes without punishment.", "low", "condition + outcome variant", ["Players may feel judged."], "missions with a fail/soft-fail condition", "0", "≥ 1/3", "MISSIONCRAFT re-run; playtest tension rating."),
            P("ambitious", "Make outcomes graded: every mission can go well, OK or badly.", ["Three outcome tiers per mission with different follow-ups."], "Every mission has stakes and replay value.", "high", "outcome tiers and follow-ups", ["Content ×3 for outcomes."], "missions with graded outcomes", "0", "all", "Playtest."),
            P("wildcard", f"Let failure persist in the world: what goes wrong stays wrong.", ["A failed mission leaves a visible mark (a closed road, a person who remembers) until fixed by another mission."], "Failure becomes part of the world's story.", "high", "persistent world state", ["State complexity."], "persistent consequences", "0", "≥ 2", "Playtest.")]


def g_dangling(f, g):
    d = f["data"]
    return [P("conservative", f"Fix the reference: point '{d.get('missing')}' at an existing id.", [f"Edit {_ev_where(f)}."], "The content becomes reachable.", "low", "one-line fix", ["None."], "dangling references", "≥ 1", "0", "DESIGNCRAFT re-run (source verified)."),
            P("ambitious", "Validate references in the project's tests.", ["Add a unit test that every requires/link id exists."], "This class of bug cannot ship again.", "low", "a test", ["None."], "reference test", "absent", "present and passing", "Project test suite."),
            P("wildcard", "Make the missing link a deliberate secret.", ["If the referenced content was cut, replace it with a short hidden mission that restores it."], "Cut content becomes a discovery.", "medium", "new content", ["Scope."], "players who find it", "n/a", "≥ 10%", "Playtest.")]


def g_flat_escalation(f, g):
    seq = f["data"]["seq"]
    return [P("conservative", "Add one objective per unlock tier.", ["Late missions gain a complication or second action."], "Late game asks more of the player.", "low", "data edits", ["Longer late missions."], "objectives at max depth", f"{seq[-1]:.1f}", f"≥ {seq[0] + 2:.1f}", "MISSIONCRAFT re-run."),
            P("ambitious", "Introduce a new mechanic per act and combine them late.", ["Each tier teaches a new verb; the last tier combines them."], "Mastery pays off in a satisfying finale.", "high", "new mechanics", ["Cost."], "distinct verbs in final tier", "baseline", "≥ 3", "PLAYCRAFT + playtest."),
            P("wildcard", "Escalate the world, not the mission: conditions worsen as the campaign advances.", ["Weather, threat or scarcity grows with progress."], "The whole game tightens.", "medium", "global modifiers", ["Global balance."], "intensity at final tier", "flat", "highest", "EXPERIENCECRAFT journey re-run.")]


def g_no_consequence(f, g):
    ms = f["data"]["missions"]
    return [P("conservative", f"Give {names_list(ms[:3])} a visible after-effect.", ["Each completion changes one thing in the world (a road opens, a person thanks you elsewhere, a place changes)."], "Missions feel like they mattered.", "medium", "world state flags", ["State tracking."], "missions with consequences", f"{len(ms)} without", "0 without", "MISSIONCRAFT re-run; playtest."),
            P("ambitious", "Thread missions together: completions unlock follow-ups and change later briefs.", ["Each dead-end mission unlocks one follow-up or changes a later brief."], "A campaign instead of a list.", "medium", "requires edges + text variants", ["Writing."], "dead-end missions", str(len(ms)), "≤ 1", "MISSIONCRAFT re-run."),
            P("wildcard", "A town memory: characters reference what you did, good or bad.", [f"{g.who()} and others comment on finished missions."], "The world remembers.", "medium", "conditional lines", ["Many lines."], "lines referencing past missions", "0", "≥ 10", "Playtest.")]


def g_brief(f, g):
    return [P("conservative", "Lead each brief with the objective in one sentence.", ["First sentence: what and where. Second: why."], "Players act faster and still get the fiction.", "low", "text edits", ["Less mood text."], "brief words (median)", "baseline", "≤ 30", "MISSIONCRAFT re-run."),
            P("ambitious", "Split briefs into a one-line order and an optional dossier.", ["Tap for more: the long version lives behind a button."], "Readers and skimmers both served.", "medium", "UI", ["UI work."], "brief read-through rate", "unmeasured", "↑", "Playtest."),
            P("wildcard", "Deliver the brief in-world as it happens.", ["The objective is spoken while the player already moves."], "No reading wall.", "medium", "triggered lines", ["Missed lines."], "time to first input", "baseline", "−50%", "PLAYCRAFT.")]


def g_underdeveloped(f, g):
    n = f["data"]["names"]
    return [
        P("conservative", f"Give {names_list(n[:3])} a voice: one line each where the player meets them, one more later.",
          ["Write 2 lines per character tied to existing missions or places.", "Have each say something only they would say (their job, their worry)."],
          "Names become people; players start to recognise them.", "low", "a dozen lines", ["Writing time."], "characters with ≥ 2 mentions and a line", f"{len(n)} below", "0 below", "STORYCRAFT re-run; playtest: name three characters."),
        P("ambitious", f"Build a small arc around one of them ({n[0]}).",
          [f"Three beats across the campaign: {n[0]} asks, {n[0]} is in trouble, {n[0]} pays it back.", "Attach each beat to a mission the player already plays."],
          "A relationship that develops over hours; the payoff lands because the player was there for the setup.", "medium", "3 mission hooks and lines", ["Must fit existing missions' tone."],
          f"missions featuring {n[0]}", "≤ 1", "3", "STORYCRAFT re-run; playtest emotional rating at the payoff."),
        P("wildcard", f"Make {n[-1]} unreliable: what they say early turns out to be false.", ["Plant a claim; let a later mission reveal the truth."],
          "Players reread the world; characters gain depth through contradiction.", "medium", "a planted line and a reveal", ["Risk of feeling like a cheap twist."], "players who notice the reveal", "n/a", "≥ 50%", "Playtest."),
    ]


def g_cast_not_data(f, g):
    n = f["data"]["names"]
    return [P("conservative", f"Define the cast as data ({names_list(n[:4])}).", ["Add a characters file: id, name, role, home, voice notes."], "Writers and systems share one source of truth.", "low", "a data file", ["None."], "characters defined as data", "0", f"{len(n)}", "DESIGNCRAFT re-run."),
            P("ambitious", "Give characters state: what they think of the player.", [f"A per-character relationship value changed by missions; lines vary by it ({n[0]} first)."], "Characters react to how the player has treated them.", "medium", "state + line variants", ["Writing."], "lines that vary with relationship", "0", "≥ 10", "Playtest."),
            P("wildcard", f"Let {n[0]} be present in the world, not just the radio.", [f"{n[0]} appears at places the player visits, doing their own thing."], "A living world.", "high", "placement + animation", ["Art cost."], "in-world appearances", "0", "≥ 3", "Playtest.")]


def g_no_payoff(f, g):
    pairs = f["data"]["pairs"]
    a = pairs[0]
    return [P("conservative", f"Bring {a[0]} back once, remembering {a[1]}.", [f"One line in a later mission where {a[0]} references {a[1]}."], "A small payoff that makes the world feel continuous.", "low", "a line per character", ["None."], "characters in ≥ 2 missions", "baseline", f"+{len(pairs)}", "STORYCRAFT re-run."),
            P("ambitious", "A reunion mission: one late mission that brings back everyone helped earlier.", [f"Characters from {names_list([p[1] for p in pairs[:3]])} return to help."], "The campaign ends with the community the player built.", "high", "a new mission", ["Big content."], "returning characters in finale", "0", f"{len(pairs)}", "Playtest emotional rating."),
            P("wildcard", f"Make a one-scene character the secret antagonist or ally.", [f"{pairs[-1][0]} turns out to matter more than they seemed."], "A twist built from existing content.", "medium", "planted lines", ["Twist risk."], "players who remember them", "n/a", "≥ 60%", "Playtest.")]


def g_unattributed(f, g):
    return [P("conservative", "Assign a speaker to every line.", ["Add speaker ids; group lines by character."], "Voices players can recognise.", "low", "data edits", ["None."], "attributed lines", "< 30%", "≥ 90%", "STORYCRAFT re-run."),
            P("ambitious", "Write a voice guide per character and revise lines to it.", ["Vocabulary, rhythm, what they care about."], "Distinct voices.", "medium", "rewrite pass", ["Writing time."], "speakers", "few", "≥ 5", "Playtest: who said this?"),
            P("wildcard", "Let the town's chatter be the game's chorus on purpose.", ["Keep anonymity but give it a narrative role (rumour that reveals plot)."], "Anonymity as a device.", "low", "line edits", ["Must be clear it's intentional."], "rumours that pay off", "0", "≥ 3", "Playtest.")]


def g_doc_contradiction(f, g):
    d = f["data"]
    return [P("conservative", f"Make the document and the data agree ({d['stated']} vs {d['actual']} {d['noun']}s).", [f"Update {d['doc']} or the data, whichever is the intended design."], "No broken promises.", "low", "text edit", ["None."], "doc/data mismatches", "≥ 1", "0", "DESIGNCRAFT re-run (source verified)."),
            P("ambitious", "Generate design-doc counts from data.", ["A script that writes counts into the README."], "Docs never drift.", "low", "a script", ["None."], "manual counts in docs", "≥ 1", "0", "CI."),
            P("wildcard", "If the doc describes the better design, build it.", [f"Bring the {d['noun']} count to what the docs promise."], "The promise is kept.", "medium", "content", ["Scope."], f"{d['noun']}s", str(d["actual"]), str(d["stated"]), "DESIGNCRAFT re-run.")]


def g_linear_story(f, g):
    return [P("conservative", "Add one decision with two outcomes at the story's midpoint.", [f"A choice involving {g.who()} that changes one later mission's brief."], "The story acknowledges the player.", "medium", "one branch", ["Two versions of a mission."], "endings/choices", "0", "≥ 1 choice", "STORYCRAFT re-run."),
            P("ambitious", "Endings that reflect how the player played.", ["2–3 endings decided by accumulated choices or mission outcomes."], "Replay for a different ending.", "high", "endings and state", ["Content."], "endings", "0", "≥ 2", "STORYCRAFT re-run; playtest."),
            P("wildcard", "Let the player's reputation be the story.", ["Characters describe the player differently based on what they did."], "Emergent narrative.", "medium", "reputation lines", ["Writing."], "reputation-dependent lines", "0", "≥ 12", "Playtest.")]


def g_story_pacing(f, g):
    last = f["data"].get("last") or []
    return [P("conservative", f"Move story beats toward the end: {names_list(last)} get the payoff lines.", ["Shift 2–3 reveals from early briefs to late missions."], "The campaign builds to its end.", "low", "text moves", ["Early missions get thinner."], "story share in last third", pct(f["data"]["late"]), "≥ 35%", "STORYCRAFT re-run."),
            P("ambitious", "A late-campaign story arc with its own missions.", ["Two late missions whose purpose is a reveal."], "A climax.", "high", "new missions", ["Content."], "story share in last third", pct(f["data"]["late"]), "≥ 40%", "Playtest."),
            P("wildcard", "Tell the story backwards: the first mission is the end, and the campaign explains how it happened.", ["Open with the aftermath."], "Curiosity drives the campaign.", "high", "restructure", ["Large rewrite."], "players who want to continue after mission 1", "baseline", "↑", "Playtest.")]


def g_faceless(f, g):
    ms = f["data"]["missions"]; cast = f["data"]["cast"]
    return [P("conservative", f"Put a person in {names_list(ms[:3])}: who asked, who is helped.", [f"Name a requester or beneficiary from the cast ({names_list(cast[:3])})."], "Missions have someone to care about.", "low", "text edits", ["None."], "missions naming a character", "baseline", "≥ 70%", "STORYCRAFT re-run."),
            P("ambitious", "Every mission ends with a short scene with the person helped.", ["A two-line exchange on completion."], "Emotional payoff per mission.", "medium", "lines per mission", ["Writing."], "missions with a completion scene", "0", "all", "Playtest."),
            P("wildcard", "The player's companion has opinions about each job.", [f"{g.who()} comments on each faceless mission."], "Personality fills the gap.", "low", "lines", ["Could get repetitive."], "companion comments", "0", f"{len(ms)}", "Playtest.")]


def g_difficulty_spike(f, g):
    d = f["data"]
    return [
        P("conservative", f"Smooth the step: raise {d['field']} in {d['from']} or lower it in {d['to']}.",
          [f"{d['table']}.{d['field']}: {d['a']:g} → {d['b']:g} is ×{d['ratio']:.1f}. Set {d['to']} to about {d['a'] * 1.5:g} (×1.5) and move the rest of the jump to the following entry."],
          "The difficulty curve rises steadily; fewer players hit a wall.", "low", "numbers in one table", ["Late stages feel easier unless shifted too."],
          f"largest step in {d['field']}", f"×{d['ratio']:.1f}", "≤ ×1.8", "PROGRESSIONCRAFT re-run (source verified); PLAYCRAFT difficulty pass; playtest failure rate at that stage."),
        P("ambitious", f"Keep the jump, prepare the player for it.",
          [f"Before {d['to']}, add a stage or mission that teaches the skill {d['to']} demands.", "Give the player a new tool or upgrade right at the step so power rises with the threat."],
          "The spike becomes a milestone: a new challenge and a new answer arrive together.", "medium", "one teaching stage and an unlock timing change", ["One more stage to build."],
          "failure rate at the spike (playtest)", "unmeasured", "≤ 1.5× the previous stage", "Structured playtest: attempts per stage."),
        P("wildcard", f"Make the spike optional: {d['to']} at full strength is a challenge mode.",
          [f"Ship {d['to']} at a smoothed value; unlock the original values as a harder variant with a better reward."],
          "Experts get the wall they want; everyone else gets a curve.", "medium", "a variant flag and a reward", ["Two balance targets."],
          "players who try the hard variant", "n/a", "≥ 25%", "PLAYCRAFT + playtest."),
    ]


def g_plateau(f, g):
    d = f["data"]
    return [P("conservative", f"Differentiate {d['b']} from {d['a']} with a small numeric step.", ["Raise one difficulty value by 10–20%."], "Each stage feels like progress.", "low", "numbers", ["None."], "identical consecutive stages", "1", "0", "PROGRESSIONCRAFT re-run."),
            P("ambitious", f"Give {d['b']} a new rule instead of new numbers.", ["A modifier (darkness, a new enemy, a new objective)."], "A stage players remember for what changed.", "medium", "one modifier", ["Design time."], "stages with a unique rule", "0", "≥ 1", "Playtest."),
            P("wildcard", f"Make {d['b']} a breather on purpose and say so.", ["A calm stage with a reward for exploration."], "Pacing contrast.", "low", "framing", ["Must be clearly intentional."], "intensity drop", "0", "1 deliberate", "EXPERIENCECRAFT journey.")]


def g_no_new_threats(f, g):
    return [P("conservative", "Introduce one new enemy type in each stage that has none.", ["Reorder spawns so each stage debuts one type."], "Each stage is a new problem.", "low", "spawn tables", ["Earlier stages get harder."], "stages with a new type", "few", "all", "PROGRESSIONCRAFT re-run."),
            P("ambitious", "Design enemy pairs whose combination is the challenge.", ["Stages escalate by new combinations, not more of the same."], "Tactical variety.", "medium", "spawn design", ["Tuning."], "distinct combinations", "baseline", "+50%", "Playtest."),
            P("wildcard", "Let the threats learn from the player.", ["Enemies adapt to the player's most-used tactic."], "Each run escalates differently.", "high", "adaptive AI", ["Complex."], "tactic diversity", "unmeasured", "↑", "Playtest.")]


def g_economy_gap(f, g):
    d = f["data"]
    return [P("conservative", f"Bring prices and income closer: raise campaign rewards or lower top prices.", [f"Campaign pays {d['income']:g} {d['currency']}; prices total {d['prices']:g}. Target ≤ 2×."], "Less grinding.", "low", "numbers", ["Faster completion."], "prices ÷ campaign income", f"{d['prices'] / d['income']:.1f}", "≤ 2.0", "PROGRESSIONCRAFT re-run."),
            P("ambitious", "Make repeatable income interesting: dynamic jobs with variety and stakes.", [f"Repeatable jobs ({names_list(d['dynamic']) or 'new ones'}) get modifiers, rotations and a weekly special."], "The grind becomes content.", "medium", "dynamic job system", ["Design time."], "distinct repeatable variants", str(len(d["dynamic"])), "≥ 6", "Playtest."),
            P("wildcard", "Let players earn by mastery instead of repetition.", ["Big payouts for skilled completions (par time, no damage)."], "Skill shortens the grind.", "medium", "bonus rules", ["Skill gap."], "income from mastery bonuses", "0", "≥ 25%", "PLAYCRAFT.")]


def g_slow_unlocks(f, g):
    return [P("conservative", "Add cheaper intermediate unlocks.", ["Split expensive unlocks into steps."], "A new toy every couple of missions.", "low", "data", ["More entries."], "missions per unlock", f"{f['data']['ratio']:.1f}", "≤ 2.5", "PROGRESSIONCRAFT re-run."),
            P("ambitious", "Unlock by doing, not paying, for key tools.", ["Some unlocks granted by mission milestones."], "Progress tied to play.", "medium", "unlock hooks", ["Economy rebalance."], "unlocks via milestones", "0", "≥ 3", "Playtest."),
            P("wildcard", "Rent before you buy.", ["Try any unlock for one mission."], "Informed choices.", "medium", "trial system", ["Exploit risk."], "trials converted to purchases", "n/a", "≥ 40%", "Telemetry.")]


def g_flat_tree(f, g):
    return [P("conservative", f"Group {f['data']['collection']} into tiers with prerequisites.", ["Three tiers; tier 2 requires one tier-1 pick."], "Purchases become steps on a path.", "low", "requires fields", ["Less freedom early."], "entries with prerequisites", "0", "≥ 1/3", "PROGRESSIONCRAFT re-run."),
            P("ambitious", "Branches with exclusive picks.", ["Two paths per slot; choosing one locks the other until later."], "Builds and identity.", "medium", "exclusivity rules", ["Balance."], "exclusive choices", "0", "≥ 3", "Playtest."),
            P("wildcard", "Upgrades found in the world, not bought.", ["Place some upgrades as discoveries."], "Exploration and progression merge.", "medium", "placement", ["Some players miss them."], "found upgrades", "0", "≥ 3", "Playtest.")]


def g_no_long_goals(f, g):
    return [P("conservative", "Add milestones for mastery and exploration.", ["10–15 milestones tied to existing systems."], "Long-term goals.", "low", "data + UI", ["UI."], "milestones", "0", "≥ 10", "PROGRESSIONCRAFT re-run."),
            P("ambitious", "A rank or career track with rewards.", ["Ranks unlock new mission types."], "A sense of career.", "medium", "rank system", ["Design."], "ranks", "0", "≥ 4", "Playtest."),
            P("wildcard", "A collection the world itself displays.", ["Trophies appear at the hub."], "Visible history.", "medium", "display", ["Art."], "displayed items", "0", "≥ 8", "Playtest.")]


def g_low_replay(f, g):
    return [P("conservative", "Track best times or scores per mission.", ["A personal best per mission."], "A reason to replay.", "low", "save + UI", ["None."], "missions with a best score", "0", "all", "PLAYCRAFT."),
            P("ambitious", "Seeded daily variants.", ["A daily seed changes weather, targets or modifiers."], "Fresh runs every day.", "medium", "seeded variants", ["Testing."], "daily variants", "0", "1/day", "Playtest."),
            P("wildcard", "New game plus with a twist.", ["A second playthrough with changed rules or a new perspective."], "A reason to start again.", "high", "NG+ rules", ["Content."], "NG+ starts", "n/a", "≥ 15%", "Telemetry.")]


def g_flat_tension(f, g):
    t = f["data"]["titles"]
    return [P("conservative", f"Pick one mission per act to be the peak and push it: {names_list([t[len(t) // 2], t[-1]])}.", ["Add a threat, a clock or a fail state to those missions only."], "Clear peaks; the campaign has a shape.", "low", "edits to 2–3 missions", ["Peaks must be tuned."], "intensity range", f"{max(f['data']['ints']) - min(f['data']['ints']):.1f}", "≥ 4", "EXPERIENCECRAFT journey re-run; playtest tension rating per mission."),
            P("ambitious", "Design the campaign as acts with a rising line and a release after each peak.", ["Order missions by intended intensity; insert a calm mission after each peak."], "Rhythm: tension and relief.", "medium", "ordering + a few new missions", ["Reordering affects unlocks."], "peaks followed by a breather", "0", "every act", "Playtest."),
            P("wildcard", "An event that interrupts the campaign: everything changes for one mission.", [f"A crisis at {g.place()} that pre-empts the board."], "A moment players remember.", "medium", "one event mission", ["Disruptive by design."], "players who mention it unprompted", "n/a", "≥ 50%", "Playtest interview.")]


def g_no_release(f, g):
    return [P("conservative", "Insert a calm mission after the two hardest.", ["A low-stakes mission with a reward for curiosity."], "Breathing room.", "low", "one or two missions", ["Longer campaign."], "intensity drops", "0", "≥ 2", "EXPERIENCECRAFT re-run."),
            P("ambitious", "A hub moment between acts.", ["A scene at the hub with characters reacting to recent events."], "Release with meaning.", "medium", "scenes", ["Writing."], "breathers with story", "0", "≥ 2", "Playtest."),
            P("wildcard", "Let the player choose when to rest.", ["A rest action that skips time and shifts the world."], "Player-controlled pacing.", "medium", "rest system", ["Exploit risk."], "rest uses", "n/a", "≥ 1 per session", "Playtest.")]


def g_long_tutorial(f, g):
    d = f["data"]
    return [P("conservative", f"Cut {d['chain']} to its first five steps; teach the rest in context.", ["Keep steering, the first goal and the first reward; move the rest to just-in-time hints."], "Players choose for themselves sooner.", "low", "chain edits", ["Some players miss systems."], "guided steps", str(d["steps"]), "≤ 5", "EXPERIENCECRAFT re-run; PLAYCRAFT time to first free choice."),
            P("ambitious", "Make onboarding a mission with a goal, not a checklist.", ["One short mission whose objectives teach the core loop with a story reason."], "Learning feels like playing.", "medium", "one onboarding mission", ["Writing and tuning."], "time to first free choice", "unmeasured", "≤ 3 min", "Playtest."),
            P("wildcard", "No tutorial: an expert character shows off and the player copies.", [f"{g.who()} demonstrates; the player follows or not."], "Learning by watching.", "medium", "scripted demo", ["Some players won't copy."], "players completing the first loop unaided", "unmeasured", "≥ 80%", "Playtest.")]


def g_friction_stack(f, g):
    return [P("conservative", "Fix the cheapest part of the stack first: end missions on the action and pay by effort.", [f"Apply the conservative proposals of: {', '.join(f['data']['parts'])}."], "Noticeably less dead time per session.", "low", "data edits", ["Economy shifts."], "friction findings", str(len(f["data"]["parts"])), "≤ 1", "DESIGNCRAFT re-run; PLAYCRAFT session timing."),
            P("ambitious", "Redesign the session loop around momentum.", ["Field hand-offs, route choices, effort-based pay, and a hub you return to by choice."], "Sessions flow from job to job.", "high", "loop redesign", ["Large change."], "completed missions per 20-minute session", "unmeasured", "+50%", "Structured playtest."),
            P("wildcard", "Turn travel time into the game's signature: the journey has its own progression.", ["Travel skills, routes and vehicle mastery that make trips faster and more fun over time."], "What was friction becomes mastery.", "high", "travel progression", ["New system."], "player-rated fun of travel", "unmeasured", "≥ 4/5", "Playtest.")]


def g_agency_gap(f, g):
    return [P("conservative", "Add alternatives and optional goals to the five most-played missions.", ["One alternative method and one optional objective each."], "Small choices everywhere.", "low", "data", ["Balance."], "agency sources", "0", "≥ 10", "DESIGNCRAFT re-run."),
            P("ambitious", "A campaign-level choice with consequences.", [f"A decision involving {g.who()} that changes which missions appear."], "The player shapes the campaign.", "high", "branching", ["Content."], "branch points", "0", "≥ 1", "Playtest."),
            P("wildcard", "Player-authored goals: let the player set a goal for the day and reward it.", ["Pick a personal objective at the start of a session."], "Intentions of their own.", "medium", "goal picker", ["Unusual."], "sessions with a chosen goal", "n/a", "≥ 50%", "Playtest.")]


def g_story_split(f, g):
    rich = f["data"]["rich"]
    return [P("conservative", f"Give {names_list(rich)} a play moment that is the story beat.", ["Turn the key line into an action (find it, carry it, choose)."], "Story and play coincide.", "low", "objective edits", ["None."], "distinct verbs in story missions", "low", "+1", "MISSIONCRAFT re-run."),
            P("ambitious", "Write story into the verbs: each new mechanic arrives with a story reason.", ["Pair each reveal with a new action."], "Ludonarrative harmony.", "high", "restructure", ["Big."], "story-verb correlation", "negative", "≥ 0.3", "EXPERIENCECRAFT re-run."),
            P("wildcard", "Let the player discover the story only through play (no briefs).", ["Remove story text from briefs; put it in the world."], "Environmental storytelling.", "medium", "rewrite", ["Some players miss it."], "story found in the world", "low", "↑", "Playtest.")]


def g_no_signature(f, g):
    common = f["data"]["common"]
    return [P("conservative", "Give each mission one unique action.", [f"Beyond {names_list(common)}, add a one-off action per mission (a rescue lift, a repair under pressure, a photo)."], "Missions are remembered by their moment.", "medium", "small one-off mechanics", ["Implementation per action."], "missions with a signature action", "baseline", "≥ 50%", "EXPERIENCECRAFT re-run."),
            P("ambitious", "A set-piece per act.", ["One scripted spectacle mission per act."], "Peaks of spectacle.", "high", "set pieces", ["Art and code."], "set pieces", "0", "≥ 2", "Playtest."),
            P("wildcard", "Let players create the signature moment: physics or systemic chain reactions in missions.", ["Systems that can combine unexpectedly."], "Emergent stories.", "high", "systems", ["Unpredictable."], "unique events reported", "unmeasured", "↑", "Playtest.")]


def g_same_kind_run(f, g):
    return [P("conservative", f"Reorder unlocks so no more than two '{f['data']['kind']}' missions are consecutive.", ["Edit requires edges."], "Variety over time.", "low", "data", ["Unlock logic."], "longest same-kind run", str(f["data"]["n"]), "≤ 2", "EXPERIENCECRAFT re-run."),
            P("ambitious", "Offer two different-kind missions at every unlock.", ["The board always has a choice of kind."], "Players steer variety.", "medium", "board logic", ["Content."], "kinds on the board", "1", "≥ 2", "Playtest."),
            P("wildcard", "A themed run as an event: make the streak deliberate and escalate it.", ["Frame consecutive missions as one crisis."], "Repetition with purpose.", "low", "framing", ["Tone."], "players who notice", "n/a", "≥ 60%", "Playtest.")]


def g_slow_start(f, g):
    ms = f["data"]["ms"]
    return [P("conservative", "Let the player act during loading.", ["Make the title screen interactive or start input before all assets load."], "No dead wait.", "medium", "loading order", ["Engineering."], "time to first input", f"{ms / 1000:.1f} s", "≤ 3 s", "PLAYCRAFT pass (simulated)."),
            P("ambitious", "Stream the world: load what is near first.", ["Progressive asset loading."], "Fast start everywhere.", "high", "streaming", ["Engineering."], "time to first input", f"{ms / 1000:.1f} s", "≤ 2 s", "PLAYCRAFT pass."),
            P("wildcard", "Make the wait a moment of story.", ["A short in-world sequence that plays while loading."], "The wait becomes atmosphere.", "medium", "intro sequence", ["Repeat players need a skip."], "players who skip it", "n/a", "≤ 50%", "Playtest.")]


def g_generic(f, g):
    return [P("conservative", f"Address '{f['title']}' within the current design.", ["Apply the smallest data change that resolves the measured fact."], "The issue no longer shows in the next assessment.", "low", "small edits", ["Limited impact."], f["kind"], "present", "absent", "DESIGNCRAFT re-run."),
            P("ambitious", f"Redesign the system behind '{f['title']}'.", ["Rework the system with the player experience as the target."], "A stronger version of this system.", "medium", "system work", ["Cost."], f["kind"], "present", "absent", "PLAYCRAFT pass + playtest."),
            P("wildcard", f"Turn '{f['title']}' into a feature.", ["Lean into it deliberately and make it distinctive."], "A memorable quirk.", "medium", "framing + content", ["Risk."], "player reaction", "unmeasured", "positive", "Playtest.")]


GEN = {"return_leg": g_return_leg, "unused_space": g_unused_space, "empty_zone": g_empty_zone, "travel_spike": g_travel_spike, "discovery_density": g_discovery_density,
       "orientation": g_orientation, "checkpoints": g_checkpoints, "environment_variety": g_environment_variety, "travel_heavy": g_travel_heavy,
       "skeleton_repetition": g_skeleton_repetition, "objective_repetition": g_objective_repetition, "thin_missions": g_thin_missions, "family_imbalance": g_family_imbalance,
       "single_solution": g_single_solution, "no_optional": g_no_optional, "reward_effort": g_reward_effort, "no_failure": g_no_failure, "dangling_requires": g_dangling,
       "requires_cycle": g_dangling, "dangling_reference": g_dangling, "flat_escalation": g_flat_escalation, "no_consequence": g_no_consequence, "missing_briefs": g_brief,
       "long_briefs": g_brief, "underdeveloped_character": g_underdeveloped, "cast_not_data": g_cast_not_data, "no_payoff": g_no_payoff, "unattributed_dialogue": g_unattributed,
       "doc_contradiction": g_doc_contradiction, "linear_story": g_linear_story, "story_pacing": g_story_pacing, "faceless_missions": g_faceless,
       "difficulty_spike": g_difficulty_spike, "plateau": g_plateau, "no_new_threats": g_no_new_threats, "economy_gap": g_economy_gap, "slow_unlocks": g_slow_unlocks,
       "flat_tree": g_flat_tree, "no_long_goals": g_no_long_goals, "low_replay": g_low_replay, "flat_tension": g_flat_tension, "no_release": g_no_release,
       "long_tutorial": g_long_tutorial, "friction_stack": g_friction_stack, "agency_gap": g_agency_gap, "story_gameplay_split": g_story_split,
       "no_signature": g_no_signature, "same_kind_run": g_same_kind_run, "slow_start": g_slow_start}

IMPACT = {"critical": 5, "major": 4, "minor": 2.5, "info": 1}
COMPLEXITY_COST = {"low": 1, "medium": 2, "high": 3}


def for_finding(f, g):
    if f["severity"] == "info" or f["kind"] == "playcraft_fail": return []
    gen = GEN.get(f["kind"], g_generic)
    props = gen(f, g)
    for p in props:
        p["finding"] = f["id"]; p["existing"] = f["summary"]; p["problem"] = f["title"]; p["why"] = f["why"]
        p["id"] = f"{f['id']}:{p['variant']}"
        # wild cards are speculative: they rank below a grounded proposal of the same cost
        p["impact"] = IMPACT[f["severity"]] * {"conservative": 0.8, "ambitious": 1.0, "wildcard": 0.6}[p["variant"]]
        p["priority"] = round(p["impact"] / COMPLEXITY_COST[p["complexity"]], 2)
    return props


def for_mission(m, g, findings):
    """Design Lab: three alternatives for any mission, built from its own objectives (not tied to a finding)."""
    verbs = [o["verb"] for o in m["objectives"]]
    from .departments.base import is_travel
    act = [o for o in m["objectives"] if not is_travel(o["verb"]) and o["verb"] not in ("mount", "pet")]
    # the climax: the last real action, weighted toward ones that take time (hold) or many targets
    key = max(act, key=lambda o: (o.get("hold") or 0) + (o.get("count") or 0) + act.index(o) * 0.5) if act else (m["objectives"][0] if m["objectives"] else None)
    other = [v for v in g.verbs if v not in verbs][:2]
    who = next((c for c in m.get("characters", [])), None)
    who_name = m.get("giver") or next((n for n in g.cast if n.lower() == (who or "")), g.who())
    kt = (key.get("text") if key else None) or (key["verb"] if key else "the main action")
    rel = [f["id"] for f in findings if m["id"] in f.get("entities", [])]
    base = {"existing": f"{m['title']}: " + " → ".join(f"{o['verb']}" for o in m["objectives"]) + (f". Brief: \"{m['brief'][:160]}\"" if m.get("brief") else ""),
            "problem": "Mission-level alternatives (Design Lab)", "why": "Explore how this mission could play differently while keeping the original intact.", "finding": None, "related_findings": rel}
    props = [
        P("conservative", f"Add a twist to '{kt}': a second step using {other[0] if other else 'a new action'}.",
          [f"After '{kt}', add one objective using {other[0] if other else 'an existing verb'} at the same place.", "Pay 15–20% more for it."],
          "Same mission, with a middle beat that asks the player to adapt.", "low", "one objective added", ["Mission a minute longer."], "objectives", str(len(m["objectives"])), str(len(m["objectives"]) + 1), "MISSIONCRAFT re-run; playtest."),
        P("ambitious", f"Rebuild {m['title']} around a decision.",
          [f"At the midpoint, {who_name} asks for something that conflicts with the goal (time, route or risk).", "Both choices complete the mission; each changes the reward and a later line."],
          "The mission becomes a story the player authored.", "medium", "a branch with two outcomes", ["Two outcomes to write and test."], "choices in mission", "0", "1", "Playtest: which option did players pick and why?"),
        P("wildcard", f"Invert {m['title']}: the player causes the problem the mission normally solves, then deals with it.",
          ["Start with the player's action triggering the situation; the rest of the mission is the consequence."],
          "A surprising mission players retell.", "medium", "re-scripted start", ["Tone shift; must fit the fiction."], "player surprise rating", "unmeasured", "≥ 4/5", "Playtest."),
    ]
    for p in props:
        p.update(base); p["id"] = f"lab.{m['id']}:{p['variant']}"; p["impact"] = 2.0; p["priority"] = round(2.0 / COMPLEXITY_COST[p["complexity"]], 2)
    return props


def build(M, reports, findings, title):
    g = G(M, reports, title)
    props = []
    for f in findings: props.extend(for_finding(f, g))
    lab = {}
    for m in g.missions[:60]: lab[m["id"]] = for_mission(m, g, findings)
    return props, lab
