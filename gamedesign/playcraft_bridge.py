"""Reuse PLAYCRAFT's recorded play evidence instead of duplicating it.

PLAYCRAFT plays a built game in Chromium (desktop + phone) and keeps every run in the Game Quality History
(history/playcraft/games/<owner--repo>/runs/*.json). Its `verified` and `observed` criteria were measured by
automated play, so DESIGNCRAFT imports them at evidence level `simulated` (an automated scenario, not a
person). Nothing is imported as `playtested`. If no run exists for a game, the bridge says so."""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LEVEL_MAP = {"verified": "simulated", "observed": "simulated"}
CATEGORY_MAP = {"core_gameplay": "mission", "progression": "progression", "difficulty": "difficulty", "player_experience": "experience",
                "replayability": "variety", "game_feel": "experience", "controls": "experience", "presentation": "worldbuilding", "mobile": "experience", "technical": None}


def archive():
    return os.environ.get("GITCRAFT_PLAYCRAFT_ARCHIVE") or os.path.join(REPO, "history", "playcraft")


def find_game(name, remote=None):
    """Match by repo name (case-insensitive) against <owner>--<repo> folders."""
    root = os.path.join(archive(), "games")
    if not os.path.isdir(root): return None
    key = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    for d in sorted(os.listdir(root)):
        repo = d.split("--", 1)[-1]
        if repo == key or (remote and d == remote): return os.path.join(root, d)
    return None


def latest(name):
    d = find_game(name)
    if not d: return None
    runs = sorted(glob.glob(os.path.join(d, "runs", "*.json")))
    if not runs: return None
    try: r = json.load(open(runs[-1]))
    except ValueError: return None
    crit = r.get("criteria") or {}
    imported = []
    for cid, c in crit.items():
        lvl = LEVEL_MAP.get(c.get("l"))
        if not lvl: continue
        imported.append({"id": cid, "title": c.get("t"), "status": c.get("s"), "level": lvl, "category": CATEGORY_MAP.get(c.get("c")), "pc_category": c.get("c"), "detail": c.get("d")})
    return {"game_id": r.get("game_id"), "run_id": r.get("run_id"), "assessed_at": r.get("assessed_at"), "commit": (r.get("commit") or {}).get("head"),
            "played": r.get("played"), "viewports": r.get("viewports"), "overall": (r.get("overall") or {}).get("score"), "metrics": r.get("metrics") or {},
            "evidence_counts": r.get("evidence"), "criteria": imported, "file": os.path.relpath(runs[-1], REPO)}
