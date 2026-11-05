"""Shared helpers for departments: findings, statistics, text measures."""
import math, re
from collections import Counter

SEV_RANK = {"critical": 0, "major": 1, "minor": 2, "info": 3}


def finding(dept, kind, title, severity, summary, why, evidence, level="inferred", entities=None, data=None, category=None, facts=None):
    """A design finding.
    level     the strength of the claim about players (usually inferred; source_verified for factual defects)
    evidence  the facts behind it (each with its own level and file:line)
    data      parameters the alternatives engine uses to write proposals that reference real content"""
    return {"id": f"{dept}.{kind}" + (f".{data.get('key')}" if data and data.get("key") else ""), "dept": dept, "kind": kind, "title": title,
            "severity": severity, "summary": summary, "why": why, "evidence": evidence, "level": level, "entities": entities or [],
            "data": data or {}, "category": category, "facts": facts or {}}


def entropy_norm(counts):
    """Shannon entropy of a distribution, 0 (one value) .. 1 (all equal)."""
    vals = [v for v in counts.values() if v > 0]
    n = sum(vals)
    if len(vals) <= 1 or not n: return 0.0
    h = -sum(v / n * math.log(v / n) for v in vals)
    return h / math.log(len(vals))


def gini(xs):
    xs = sorted(x for x in xs if x is not None)
    n = len(xs); s = sum(xs)
    if n < 2 or s == 0: return 0.0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * s) - (n + 1) / n


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def cv(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2: return None
    m = mean(xs)
    if not m: return None
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs)) / abs(m)


def spearman(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 4: return None
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v); i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]: j += 1
            for k in range(i, j + 1): r[order[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = rank([p[0] for p in pairs]), rank([p[1] for p in pairs])
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else None


def words(t): return len(re.findall(r"[\w']+", t or ""))


def names_list(xs, n=4):
    xs = [x for x in xs if x]
    if not xs: return ""
    if len(xs) <= n: return ", ".join(xs[:-1]) + (" and " if len(xs) > 1 else "") + xs[-1]
    return ", ".join(xs[:n]) + f" and {len(xs) - n} more"


def pct(x): return f"{round(100 * x)}%"


def topo_depth(missions):
    """Depth of each mission in its requires graph, plus dangling references and cycles."""
    by = {m["id"]: m for m in missions}
    depth, dangling, cyc = {}, [], set()
    def d(mid, stack):
        if mid in depth: return depth[mid]
        if mid in stack: cyc.add(mid); return 0
        m = by[mid]
        reqs = [r for r in m["requires"] if r in by]
        for r in m["requires"]:
            if r not in by: dangling.append((mid, r))
        v = 0 if not reqs else 1 + max(d(r, stack | {mid}) for r in reqs)
        depth[mid] = v; return v
    for m in missions: d(m["id"], frozenset())
    return depth, sorted(set(dangling)), sorted(cyc)


TRAVEL = {"goto", "go", "go to", "get to", "get out to", "reach", "ride", "fly", "head", "return", "travel", "move", "through", "land", "sail", "leave_dock", "reach_turtle", "return_harbor", "steer"}


def is_travel(verb): return (verb or "").lower() in TRAVEL or (verb or "").lower().startswith(("go", "get to", "head", "ride", "fly", "return", "reach"))
