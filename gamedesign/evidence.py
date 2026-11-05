"""Phase 5: evidence levels. Every fact, finding, criterion and proposal carries one.

  source_verified  confirmed by reading the project's files (a count, a value, a missing reference)
  simulated        observed in an automated run (PLAYCRAFT's browser play, a project's own simulation report)
  playtested       observed while a person played (only from recorded human playtest notes)
  inferred         a reasoned design assessment: DESIGNCRAFT's judgement of what the facts mean for players
  untested         not evaluated: the data needed is missing

The rule DESIGNCRAFT never breaks: an inferred judgement is never presented as observed player behaviour.
A finding's facts can be source_verified while its claim about players stays inferred; both are shown."""

LEVELS = ["playtested", "simulated", "source_verified", "inferred", "untested"]
LABEL = {"source_verified": "Source verified", "simulated": "Simulated", "playtested": "Playtested", "inferred": "Inferred", "untested": "Untested"}
RANK = {k: i for i, k in enumerate(LEVELS)}


def strongest(levels):
    lv = [l for l in levels if l in RANK]
    return min(lv, key=lambda l: RANK[l]) if lv else "untested"


def ev(text, level="source_verified", file=None, line=None, symbol=None):
    return {"text": text, "level": level, "file": file, "line": line, "symbol": symbol}


def cite(e, text, level="source_verified"):
    """Evidence item citing an entity's `ev` record."""
    src = (e or {}).get("ev") or {}
    return ev(text, level, src.get("file"), src.get("line"), src.get("symbol"))
