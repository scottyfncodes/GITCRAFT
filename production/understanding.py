"""PROJECT UNDERSTANDING: which assignment this is, before anything is planned.

"Add a jump sound", "it looks dated", "the player falls through the floor", "is this any good?" and "start over in
Phaser" are five different jobs. Reading them all as "update the project" loses what the person wanted, what must
survive the work and what would prove it done. This module names the assignment and keeps that reading in one model:

  classify(text, maturity)      what was asked of an EXISTING project → {assignment, workflow, focus, because, question?}
  standalone(text)              a request for assets alone, with no product to build → {kinds, because} or None
  model(request, a, reading)    the understanding the Decision Room shows and every work order carries: current state,
                                desired state, what is preserved, what "done" means and how it is proven

  assignment   what the job is             workflow (how the engine runs it)   focus (what the evaluators compare)
  ----------   -------------------------   ---------------------------------   ----------------------------------
  continue     build what is unfinished    continue
  complete     get it to done              complete
  feature      one named change            update
  repair       something is broken         fix
  redesign     how it looks                update                              visual:   PIXELCRAFT before / after
  gameplay     how it plays                update                              gameplay: PLAYCRAFT before / after
  polish       the same thing, better      update                              polish:   both
  integrate    make an asset, wire it in   update                              asset
  audit        judge it, change nothing    review
  rebuild      replace what exists         update, and only after a person confirms what may be thrown away

Deterministic and inspectable, like the intake: `because` quotes the words that decided the reading, and the Decision
Room lets the person correct it. A heuristic never gets the last word: an uncertain or destructive reading asks."""
import re

_ASSET = (r"sound effects?|sounds?|sfx|jingles?|music|soundtrack|ambien(?:ce|t loop)|voice ?(?:line|over)s?|sprites?|sprite ?sheets?|textures?|"
          r"materials?|3d models?|models?|mesh(?:es)?|icons?|logos?|illustrations?|backgrounds?|skybox(?:es)?|tilesets?|particles?|"
          r"particle effects?|vfx|animations?|trailers?|title cards?|fonts?|hdri")
_MAKE = r"make|create|generate|produce|compose|record|draw|design|model|sculpt|render|add|need|want|give me|get me"
# an asset someone wants made: "make an explosion sound", "I need a logo". Not "make the animation smoother" (a change to how it feels)
ASSET_ASK = re.compile(rf"\b({_MAKE})\b(?:\s+[\w'-]+){{0,5}}?\s+({_ASSET})\b(?!\s+(?:\w+\s+)?(?:\w+er|more|less|better|worse|nicer)\b)", re.I)
ASSET_LEAD = re.compile(rf"^(?:an?|the|some|new|\d+|two|three|four|five|six)?\s*(?:[\w'-]+\s+){{0,4}}?({_ASSET})\b", re.I)
PRODUCT = re.compile(r"\b(game|app|application|website|web site|site|landing page|dashboard|platformer|roguelike|shooter|puzzler|tracker|tool|cli|"
                     r"utility|library|pwa|editor|planner|calculator|store|shop|blog|portfolio)\b", re.I)
FOR_ELSEWHERE = re.compile(r"\bfor (?:my|our|the|a|an) (?:[\w'-]+\s+){0,3}?(game|app|site|website|project|bakery|band|shop|company|brand|channel|podcast|team|store|"
                           r"business|startup|club|studio|cafe|restaurant)\b", re.I)

CHANGE = (r"add|fix|make|change|update|improve|implement|build|remove|replace|redesign|rewrite|rebuild|finish|complete|polish|tweak|adjust|"
          r"continue|ship|rename|upgrade|migrate|support|create")
READINGS = [
    # replacing what exists is never inferred from a default and never started without a person saying what may go
    ("rebuild", "update", None, r"\b(rebuild|rewrite|re-?do (?:it|this|everything|the whole)|start(?:ing)? (?:over|again|from scratch)|from scratch|"
                                r"throw (?:it|this) (?:away|out)|scrap (?:it|this)|port (?:it|this|the \w+) to|re-?implement (?:it|this) in)\b"),
    ("audit", "review", None, r"\b(review|audit|assess|evaluate|critique|what state|how complete|inspect|feedback on|what do you think|"
                              rf"thoughts on|how good|any good|worth (?:shipping|releasing))\b(?!.*\b(?:fix|add|build|implement|finish)\b)"),
    ("repair", "fix", None, r"\b(fix|bug|bugs|broken|breaks?|crash(?:es|ed|ing)?|error|errors|doesn'?t work|not working|repair|regression|glitch(?:es|y)?|"
                            r"falls? through|clips? through|gets? stuck|stuck on|freez(?:es|ing)|froze|does nothing|nothing happens|unresponsive|"
                            r"won'?t (?:load|start|open|save|run|play|move|scroll|submit|close)|can'?t (?:click|tap|save|load|move|scroll|log ?in|submit)|"
                            r"stops? (?:working|responding)|stopped working|no longer (?:works?|loads?|saves?)|blank (?:screen|page)|(?:black|white) screen|"
                            r"not (?:saving|loading|showing|responding|rendering|playing)|fails? to|keeps? (?:crashing|dying|resetting|reloading)|"
                            r"cut off|overlaps?|overlapping|disappears?|goes missing|404|laggy?|stutters?|janky?)\b"),
    ("complete", "complete", None, r"\b(finish|complete|ship|launch|release|get it (?:done|live)|ready for (?:release|launch)|polish (?:it )?for release)\b"),
    ("continue", "continue", None, r"\b(continue|keep (?:building|going|working)|pick up where|carry on|next steps?|remaining features)\b"),
    ("integrate", "update", "asset", ASSET_ASK.pattern),
    ("redesign", "update", "visual", r"\b(redesign|restyle|re-?skin|new look|visual overhaul|make ?over|looks? (?:ugly|bad|dated|old|generic|boring|cheap|amateur(?:ish)?|"
                                     r"plain|off|bland|messy|cluttered|unfinished|like ai)|(?:look|looks|looking) (?:better|nicer|good|great|amazing|beautiful|"
                                     r"professional|modern|clean(?:er)?|premium|polished|more \w+)|visuals?|visually|art (?:style|direction)|graphics|prettier|"
                                     r"beautiful|aesthetics?|typography|colou?r (?:scheme|palette)|palette)\b"),
    ("gameplay", "update", "gameplay", r"\b(gameplay|game ?feel|mechanics?|more fun|not fun|isn'?t fun|boring|dull|repetitive|too (?:hard|easy|slow|fast|short|long)|"
                                       r"difficulty|balanc(?:e|ing)|pacing|replay(?:ability|able)?|juic(?:e|y|ier)|controls?|feels? (?:bad|floaty|sluggish|stiff|"
                                       r"slow|off|flat|clunky|unfair|boring|weightless|unresponsive)|tighter|snappier|more (?:responsive|satisfying|challenging|"
                                       r"engaging|rewarding)|onboarding|tutorial|enemy (?:ai|behaviou?r)|game design)\b"),
    ("polish", "update", "polish", r"\b(polish|refine|finishing touch(?:es)?|make it (?:better|shine|pop|great|amazing|feel premium)|improve (?:it|this|everything)|"
                                   r"improve$|next level|level it up|tighten (?:it|this) up|quality pass)\b"),
    ("feature", "update", None, r"\b(add|change|update|improve|tweak|adjust|replace|remove|rename|redesign|support|make it|implement|upgrade|migrate)\b"),
]
ASKING = re.compile(r"^(?:so |and |hey |ok |okay )?(?:is|are|does|do|did|how|what|why|which|should|would|could|can|will)\b[^?]*\?\s*$", re.I)

# one line per assignment, for the routing's `why` and the Decision Room
SAY = {"redesign": "redesign how it looks: what it does stays exactly as it is, judged by a before/after comparison",
       "gameplay": "improve how it plays: the look, the assets and saves stay, judged by a before/after play comparison",
       "polish": "polish: the same product executed better; no new features, no redesign",
       "integrate": "make the requested asset with its department and wire it in beside what exists",
       "rebuild": "rebuild: replaces existing work, so nothing starts until you say what may go and what carries over",
       "repair": "fix what is broken: the defect and a regression check; nothing else changes",
       "audit": "review only: the project measured as it is; nothing is changed",
       "feature": "one change to an existing project: only what was named and the fixes it needs"}
DEFAULTS = {"partial": ("continue", "continue"), "nearly_complete": ("complete", "complete"), "finished": ("feature", "update")}
REBUILD_Q = ("That replaces work that already exists here. What may be thrown away, and what must carry over (saved progress, content, "
             "art, the address it is deployed at)? Nothing is deleted until you answer.")

PRESERVE = {
    "continue": ["everything that already works: it is built on, not rebuilt, renamed or restructured"],
    "complete": ["the features and the design as they are: no new features, redesigns or refactors"],
    "feature": ["everything the request does not name"],
    "repair": ["everything except the defect: no redesign, no refactor, no new feature"],
    "redesign": ["what it does: features, mechanics, controls, content and saved data behave exactly as before", "the project's identity where it has one (name, logo, icon), unless you asked to change it"],
    "gameplay": ["how it looks: the art direction, assets and audio stay", "saved progress: an existing save still loads", "the mechanics you did not name"],
    "polish": ["what it is: the same features, mechanics and identity, executed better"],
    "integrate": ["every existing asset: the new one is added, nothing is replaced without your approval", "the code around the place it is wired in"],
    "audit": ["everything: a review measures and reports, it changes nothing"],
    "rebuild": ["whatever you say must carry over (asked first)"],
    "build": [],
}
DONE = {
    "continue": "the unfinished items in the Discovery inventory are built, most important first, and what worked before still works",
    "complete": "the blockers are fixed, the completion criteria are met and the release checks pass",
    "feature": "the named change works and is checked in a browser, and nothing else changed",
    "repair": "the defect is reproduced, fixed and covered by a regression check; nothing else changed",
    "redesign": "PIXELCRAFT measures the interface before and after on the same screens: better or equal on every score, no regression, and a person has looked at both",
    "gameplay": "PLAYCRAFT plays the game before and after with the same probe: no regression, the named problem measurably addressed, and a person has played both",
    "polish": "PIXELCRAFT (and PLAYCRAFT for a game) before and after: no regression on either, the top findings resolved",
    "integrate": "the asset opens as its format, is referenced by the build, has a recorded licence, and the build still loads clean",
    "audit": "a report of the project as it is, every claim measured or marked as not evaluated",
    "rebuild": "decided with you once you have said what carries over",
    "build": "every acceptance criterion measured on the final build",
}
PROOF = {"visual": "screens captured before and after at iPhone 17, iPhone 13 and desktop (PIXELCRAFT verify)",
         "gameplay": "the game played before and after with the same probe (PLAYCRAFT verify); whether it is more fun is a playtest question for a person",
         "polish": "before and after captures and play (PIXELCRAFT verify, and PLAYCRAFT verify for a game)",
         "asset": "the asset validated by its department and referenced by the build (TestCraft assets)"}


def classify(text, maturity):
    """What was asked of an existing project. `maturity` only decides when the person named nothing."""
    t = " ".join((text or "").lower().split())
    if maturity == "new": return {"assignment": "build", "workflow": "build", "focus": None, "because": "a new project"}
    # a question about the project is a request for a judgement, not for changes ("is this any good?", "how far along is it?")
    if ASKING.match(t) and not re.search(rf"\b(?:can|could|would|will) you (?:please )?(?:{CHANGE})\b", t):
        return {"assignment": "audit", "workflow": "review", "focus": None, "because": "a question about the project, not a change"}
    for name, workflow, focus, pat in READINGS:
        m = re.search(pat, t)
        if m:
            out = {"assignment": name, "workflow": workflow, "focus": focus, "because": f"'{m.group(0)}'"}
            if name == "rebuild": out["question"] = REBUILD_Q
            return out
    name, workflow = DEFAULTS.get(maturity, ("feature", "update"))
    return {"assignment": name, "workflow": workflow, "focus": None, "because": f"no request named: the {maturity.replace('_', ' ')} default"}


def standalone(text):
    """A request for assets and nothing else ("a jump sound and a coin sound", "a logo for my bakery", "a 3D model of a
    barrel for my game"): the departments make them directly. No app is scaffolded around a sound effect."""
    t = " ".join((text or "").lower().split())
    lead, ask = ASSET_LEAD.match(t), ASSET_ASK.search(t)
    if not (lead or ask): return None
    elsewhere = FOR_ELSEWHERE.search(t)
    rest = t.replace(elsewhere.group(0), " ") if elsewhere else t   # "for my game" names where it goes, not what to build
    rest = re.sub(r"\b(sound|title|store|app) (effects?|cards?|icons?|videos?)\b", " ", rest)
    if PRODUCT.search(rest): return None
    kinds = sorted({m.group(1 if m.re is ASSET_LEAD else 2).lower() for m in [x for x in (lead, ask) if x]})
    return {"kinds": kinds, "because": f"asks for {' and '.join(kinds)} only" + (f", {elsewhere.group(0)}" if elsewhere else "")}


def model(request, assessment=None, reading=None, kind=None):
    """The understanding everything downstream works from. Read-only; every field is derived from the request, the
    assessment's evidence, or stated as unknown."""
    a = assessment or {}
    inv = a.get("inventory") or {}
    reading = reading or classify(request, a.get("maturity") or "new")
    asg = reading["assignment"]
    kind = kind or a.get("kind")
    preserve = list(PRESERVE.get(asg, []))
    if a.get("existing"):
        if a.get("save_keys"): preserve.append("saved data (" + ", ".join(a["save_keys"][:4]) + "): the same keys and formats")
        if a.get("deploy"): preserve.append("the deployment and CI configuration (" + ", ".join(map(str, a["deploy"][:3])) + ")")
    return {"assignment": asg, "workflow": reading["workflow"], "focus": reading.get("focus"), "because": reading["because"],
            "product": {"kind": kind, "maturity": a.get("maturity") or "new", "confidence": a.get("confidence")},
            "current": {"working": [w["what"] for w in (inv.get("working") or [])[:8]], "unfinished": [u["what"] for u in (inv.get("unfinished") or [])[:8]],
                        "defects": [d["what"] for d in (inv.get("defects") or [])[:8]], "engines": a.get("engines") or []} if a.get("existing") else None,
            "desired": (request or "").strip() or None, "preserve": preserve, "done_when": DONE.get(asg), "proof": PROOF.get(reading.get("focus")),
            "question": reading.get("question")}
