"""LevelCraft generators (numpy + stdlib; GITCRAFT's own code). Each returns a Level:
  grid (h, w) of tile ids, entities [{type, x, y, ...}] in tile coordinates, and metadata.
Validation helpers (flood fill, platformer reachability, collision rectangles) live here too."""
import heapq
from collections import deque
import numpy as np
from core import noise as N

TILES = {   # id: (name, rgb, solid)
    0: ("empty", (20, 22, 28), False), 1: ("floor", (120, 108, 92), False), 2: ("wall", (58, 52, 64), True), 3: ("door", (170, 110, 50), False),
    4: ("water", (46, 108, 170), True), 5: ("grass", (92, 150, 70), False), 6: ("sand", (214, 196, 140), False), 7: ("rock", (110, 106, 100), True),
    8: ("road", (176, 150, 110), False), 9: ("forest", (40, 100, 52), False), 10: ("building", (150, 70, 60), True), 11: ("ground", (122, 84, 56), True),
    12: ("spikes", (200, 200, 210), False), 13: ("platform", (160, 120, 80), True), 14: ("snow", (236, 240, 246), False), 15: ("bridge", (140, 96, 60), False),
    16: ("plaza", (190, 180, 160), False), 17: ("sky", (150, 200, 230), False)}
NAME = {v[0]: k for k, v in TILES.items()}


def solid(grid): return np.isin(grid, [k for k, v in TILES.items() if v[2]])


def flood(mask, start):
    h, w = mask.shape; seen = np.zeros_like(mask, bool); q = deque([start]); seen[start[1], start[0]] = True
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = x + dx, y + dy
            if 0 <= a < w and 0 <= b < h and mask[b, a] and not seen[b, a]: seen[b, a] = True; q.append((a, b))
    return seen


def bfs_dist(mask, start):
    h, w = mask.shape; d = np.full(mask.shape, -1); d[start[1], start[0]] = 0; q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = x + dx, y + dy
            if 0 <= a < w and 0 <= b < h and mask[b, a] and d[b, a] < 0: d[b, a] = d[y, x] + 1; q.append((a, b))
    return d


def rects(mask):
    """Greedy merge of True cells into axis-aligned rectangles (x, y, w, h): collision boxes / nav regions."""
    m = mask.copy(); h, w = m.shape; out = []
    for y in range(h):
        x = 0
        while x < w:
            if not m[y, x]: x += 1; continue
            x2 = x
            while x2 < w and m[y, x2]: x2 += 1
            y2 = y + 1
            while y2 < h and m[y2, x:x2].all(): y2 += 1
            m[y:y2, x:x2] = False; out.append((x, y, x2 - x, y2 - y)); x = x2
    return out


# ---------------------------------------------------------------- dungeon (BSP)
def dungeon(w, h, rng, min_room=5, enemies=1.0, loot=1.0):
    g = np.full((h, w), 2); leaves = []

    def split(x, y, ww, hh, depth):
        if depth > 6 or (ww < min_room * 2 + 3 and hh < min_room * 2 + 3): leaves.append((x, y, ww, hh)); return None
        horiz = hh > ww if abs(ww - hh) > 4 else rng.random() < 0.5
        if horiz and hh >= min_room * 2 + 3:
            s = int(rng.integers(min_room + 1, hh - min_room - 1)); a = split(x, y, ww, s, depth + 1); b = split(x, y + s, ww, hh - s, depth + 1)
        elif ww >= min_room * 2 + 3:
            s = int(rng.integers(min_room + 1, ww - min_room - 1)); a = split(x, y, s, hh, depth + 1); b = split(x + s, y, ww - s, hh, depth + 1)
        else:
            leaves.append((x, y, ww, hh)); return None
        return (a, b)
    tree = split(1, 1, w - 2, h - 2, 0)
    rooms = []
    for (x, y, ww, hh) in leaves:
        rw = int(rng.integers(min_room, max(min_room + 1, ww - 1))); rh = int(rng.integers(min_room, max(min_room + 1, hh - 1)))
        rx = x + int(rng.integers(0, max(1, ww - rw))); ry = y + int(rng.integers(0, max(1, hh - rh)))
        rw = min(rw, w - 1 - rx); rh = min(rh, h - 1 - ry); g[ry:ry + rh, rx:rx + rw] = 1; rooms.append((rx, ry, rw, rh))
    centre = lambda r: (r[0] + r[2] // 2, r[1] + r[3] // 2)

    def carve(a, b):
        (x1, y1), (x2, y2) = a, b
        if rng.random() < 0.5: g[y1, min(x1, x2):max(x1, x2) + 1] = np.where(g[y1, min(x1, x2):max(x1, x2) + 1] == 2, 8, g[y1, min(x1, x2):max(x1, x2) + 1]); g[min(y1, y2):max(y1, y2) + 1, x2] = np.where(g[min(y1, y2):max(y1, y2) + 1, x2] == 2, 8, g[min(y1, y2):max(y1, y2) + 1, x2])
        else: g[min(y1, y2):max(y1, y2) + 1, x1] = np.where(g[min(y1, y2):max(y1, y2) + 1, x1] == 2, 8, g[min(y1, y2):max(y1, y2) + 1, x1]); g[y2, min(x1, x2):max(x1, x2) + 1] = np.where(g[y2, min(x1, x2):max(x1, x2) + 1] == 2, 8, g[y2, min(x1, x2):max(x1, x2) + 1])
    order = sorted(range(len(rooms)), key=lambda i: (centre(rooms[i])[0] + centre(rooms[i])[1] * 0.5))
    for i in range(len(order) - 1): carve(centre(rooms[order[i]]), centre(rooms[order[i + 1]]))
    for _ in range(max(1, len(rooms) // 4)):   # a few loops so it's not a pure tree
        a, b = rng.choice(len(rooms), 2, replace=False); carve(centre(rooms[a]), centre(rooms[b]))
    # corridor tiles that touch a room become doors
    g[g == 8] = 9999
    room_mask = g == 1
    nb = np.zeros_like(room_mask)
    nb[1:] |= room_mask[:-1]; nb[:-1] |= room_mask[1:]; nb[:, 1:] |= room_mask[:, :-1]; nb[:, :-1] |= room_mask[:, 1:]
    door = (g == 9999) & nb & ~room_mask
    g[g == 9999] = 1; g[door] = 3
    walk = ~solid(g)
    start = centre(rooms[order[0]]); d = bfs_dist(walk, start)
    exit_ = max((centre(r) for r in rooms), key=lambda c: d[c[1], c[0]])
    ents = [{"type": "start", "x": start[0], "y": start[1]}, {"type": "exit", "x": exit_[0], "y": exit_[1]}]
    maxd = max(1, d.max())
    for r in rooms:
        c = centre(r)
        if c in (start, exit_): continue
        depth = d[c[1], c[0]] / maxd
        for _ in range(int(rng.poisson(enemies * (0.5 + 2 * depth)))):
            ents.append({"type": "enemy", "x": int(r[0] + rng.integers(0, r[2])), "y": int(r[1] + rng.integers(0, r[3])), "tier": 1 + int(depth * 3)})
        if rng.random() < 0.6 * loot: ents.append({"type": "chest", "x": int(r[0] + rng.integers(0, r[2])), "y": int(r[1] + rng.integers(0, r[3])), "tier": 1 + int(depth * 3)})
    return g, ents, {"rooms": len(rooms), "start": start, "exit": exit_, "path_length": int(d[exit_[1], exit_[0]])}


# ---------------------------------------------------------------- cave (cellular automata)
def cave(w, h, rng, fill=0.40, steps=4, enemies=1.0, loot=1.0):
    m = rng.random((h, w)) < fill; m[0] = m[-1] = True; m[:, 0] = m[:, -1] = True
    for _ in range(steps):
        p = np.pad(m, 1, constant_values=True); n = sum(np.roll(np.roll(p, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1))[1:-1, 1:-1]
        m = (n >= 5) | (n <= 1 if _ < 2 else False); m[0] = m[-1] = True; m[:, 0] = m[:, -1] = True
    open_ = ~m; ys, xs = np.nonzero(open_)
    best = None; left = open_.copy()
    while left.any():   # keep the largest connected region
        y0, x0 = np.argwhere(left)[0]; reg = flood(open_, (int(x0), int(y0))); left &= ~reg
        if best is None or reg.sum() > best.sum(): best = reg
    g = np.where(best, 1, 7)
    ys, xs = np.nonzero(best); s = (int(xs[np.argmin(xs + ys)]), int(ys[np.argmin(xs + ys)]))
    d = bfs_dist(best, s); e = np.unravel_index(np.argmax(d), d.shape); e = (int(e[1]), int(e[0]))
    ents = [{"type": "start", "x": s[0], "y": s[1]}, {"type": "exit", "x": e[0], "y": e[1]}]
    cand = np.argwhere(best)
    for (y, x) in cand[rng.choice(len(cand), min(len(cand), int(len(cand) * 0.012 * enemies)), replace=False)]:
        if abs(x - s[0]) + abs(y - s[1]) > 8: ents.append({"type": "enemy", "x": int(x), "y": int(y), "tier": 1 + int(3 * d[y, x] / max(1, d.max()))})
    # loot in dead-end pockets: open cells with 3 solid neighbours
    p = np.pad(~best, 1, constant_values=True); walls = (p[:-2, 1:-1].astype(int) + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
    pockets = np.argwhere(best & (walls >= 3))
    for (y, x) in pockets[rng.choice(len(pockets), min(len(pockets), int(6 * loot)), replace=False)] if len(pockets) else []:
        ents.append({"type": "chest", "x": int(x), "y": int(y)})
    return g, ents, {"open_cells": int(best.sum()), "start": s, "exit": e, "path_length": int(d[e[1], e[0]])}


# ---------------------------------------------------------------- platformer
def standable(g):
    s = solid(g); free = ~s
    st = np.zeros_like(s); st[:-1] = free[:-1] & s[1:]
    return st & (g[:] != 12)


def reachable(g, start, jump_h=4, jump_d=5):
    """Cells a player can stand on from `start`: walk, fall (with drift), jump (≤ jump_h up, ≤ jump_d across,
    head room checked). Returns (set of standable cells reached, edges [(a, b, kind)])."""
    h, w = g.shape; S = solid(g); st = standable(g); seen = {start}; q = deque([start]); edges = []
    while q:
        x, y = q.popleft(); nxt = []
        for dx in (-1, 1):   # walk / fall off a ledge
            a = x + dx
            if not (0 <= a < w) or S[y, a]: continue
            if st[y, a]: nxt.append(((a, y), "walk")); continue
            for drift in (0, dx, 2 * dx):
                aa = a + drift; yy = y
                if not (0 <= aa < w): continue
                while yy + 1 < h and not S[yy + 1, aa] and not S[yy, aa]: yy += 1
                if yy < h - 1 and st[yy, aa] and not S[yy, aa]: nxt.append(((aa, yy), "fall")); break
        head = 0
        while head < jump_h and y - head - 1 >= 0 and not S[y - head - 1, x]: head += 1
        for ty in range(max(0, y - head), min(h - 1, y + jump_h * 2) + 1):
            up = y - ty
            reach = jump_d if up <= 0 else max(1, int(jump_d * (1 - (up / (jump_h + 1)) ** 2) + 1))
            for tx in range(max(0, x - reach), min(w - 1, x + reach) + 1):
                if (tx, ty) == (x, y) or not st[ty, tx] or S[ty, tx]: continue
                top = min(ty, y) - (1 if up > 0 else 0); ok = True
                for cx in range(min(x, tx), max(x, tx) + 1):   # the arc's apex row must be clear between them
                    if top >= 0 and S[top, cx]: ok = False; break
                if ok: nxt.append(((tx, ty), "jump"))
        for c, kind in nxt:
            if c not in seen: seen.add(c); q.append(c); edges.append(((x, y), c, kind))
    return seen, edges


def platformer(w, h, rng, jump_h=4, jump_d=5, enemies=1.0, loot=1.0, tries=25):
    for attempt in range(tries):
        g = np.full((h, w), 17); ground = h - 3; x = 0; ents = []; segments = []
        g[ground:, :6] = 11; x = 6; level = ground
        while x < w - 8:
            kind = rng.choice(["flat", "gap", "step_up", "step_down", "platforms", "spikes"], p=[0.25, 0.2, 0.15, 0.12, 0.18, 0.1])
            ln = int(rng.integers(4, 9))
            if kind == "gap":
                gap = int(rng.integers(2, jump_d)); x += gap; kind = "flat"
            if kind == "step_up": level = max(h // 3, level - int(rng.integers(1, jump_h)))
            if kind == "step_down": level = min(h - 2, level + int(rng.integers(1, 3)))
            g[level:, x:x + ln] = 11
            if kind == "platforms":
                py = level - int(rng.integers(2, jump_h)); px = x + int(rng.integers(0, max(1, ln - 3)))
                g[py, px:px + 3] = 13; ents.append({"type": "coin", "x": px + 1, "y": py - 1})
            if kind == "spikes" and ln >= 5: g[level - 1, x + 2] = 12
            if rng.random() < 0.35 * enemies and ln >= 5: ents.append({"type": "enemy", "x": x + ln // 2, "y": level - 1, "patrol": [x, x + ln - 1]})
            if rng.random() < 0.5 * loot: ents.append({"type": "coin", "x": x + int(rng.integers(0, ln)), "y": level - 1 - int(rng.integers(0, 2))})
            segments.append(kind); x += ln
        g[level:, x:] = 11
        start = (2, ground - 1); exit_ = (w - 3, level - 1)
        for i in range(1, 4):   # checkpoints a quarter of the way along
            cx = int(w * i / 4); col = np.nonzero(standable(g)[:, cx])[0]
            if len(col): ents.append({"type": "checkpoint", "x": cx, "y": int(col[0])})
        seen, edges = reachable(g, start, jump_h, jump_d)
        if exit_ in seen:
            ents = [e for e in ents if e["type"] != "coin" or any(abs(e["x"] - a) + abs(e["y"] - b) <= 2 for a, b in seen)]
            ents = [{"type": "start", "x": start[0], "y": start[1]}, {"type": "exit", "x": exit_[0], "y": exit_[1]}] + ents
            return g, ents, {"attempts": attempt + 1, "start": start, "exit": exit_, "reachable_cells": len(seen), "segments": segments,
                             "physics": {"jump_height_tiles": jump_h, "jump_distance_tiles": jump_d}, "nav_edges": len(edges)}, edges
    raise RuntimeError(f"no completable level in {tries} attempts; loosen jump physics or lengthen the level")


# ---------------------------------------------------------------- overworld + roads
def astar(cost, a, b):
    h, w = cost.shape; openq = [(0, a)]; came = {a: None}; g = {a: 0}
    while openq:
        _, cur = heapq.heappop(openq)
        if cur == b: break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cur[0] + dx, cur[1] + dy)
            if not (0 <= n[0] < w and 0 <= n[1] < h) or not np.isfinite(cost[n[1], n[0]]): continue
            ng = g[cur] + cost[n[1], n[0]]
            if ng < g.get(n, 1e18): g[n] = ng; came[n] = cur; heapq.heappush(openq, (ng + abs(n[0] - b[0]) + abs(n[1] - b[1]), n))
    if b not in came: return None
    path = [b]
    while path[-1] != a: path.append(came[path[-1]])
    return path[::-1]


def overworld(w, h, rng, seed=0, settlements=6, enemies=1.0, loot=1.0):
    hgt = N.norm01(N.fbm((h, w), 3, 6, seed=seed, tile=False)); Y, X = np.mgrid[0:h, 0:w]
    hgt = hgt * np.clip(1.25 - np.hypot(X / w - 0.5, Y / h - 0.5) * 1.6, 0, 1)
    moist = N.norm01(N.fbm((h, w), 4, 4, seed=seed + 9, tile=False))
    g = np.full((h, w), 5); g[hgt < 0.32] = 4; g[(hgt >= 0.32) & (hgt < 0.36)] = 6; g[(hgt > 0.36) & (moist > 0.58)] = 9; g[hgt > 0.68] = 7; g[hgt > 0.8] = 14
    land = np.isin(g, [5, 6, 9])
    cand = np.argwhere((g == 5)); towns = []
    for (y, x) in cand[rng.permutation(len(cand))]:
        if all(abs(x - tx) + abs(y - ty) > (w + h) // (settlements + 2) for tx, ty in towns): towns.append((int(x), int(y)))
        if len(towns) >= settlements: break
    # connect towns with a minimum spanning tree of A* roads; water is crossable only as bridges (expensive)
    cost = np.where(g == 4, 14.0, np.where(g == 7, 6.0, np.where(g == 14, np.inf, np.where(g == 9, 2.0, 1.0))))
    connected = [0] if towns else []; roads = []
    while len(connected) < len(towns):
        best = min(((i, j) for i in connected for j in range(len(towns)) if j not in connected), key=lambda p: abs(towns[p[0]][0] - towns[p[1]][0]) + abs(towns[p[0]][1] - towns[p[1]][1]))
        path = astar(cost, towns[best[0]], towns[best[1]]); connected.append(best[1])
        if path:
            roads.append(path)
            for x, y in path: g[y, x] = 15 if g[y, x] == 4 else (8 if g[y, x] not in (10,) else g[y, x])
            for x, y in path: cost[y, x] = min(cost[y, x], 0.6)
    ents = []
    for i, (x, y) in enumerate(towns):
        g[max(0, y - 1):y + 2, max(0, x - 1):x + 2] = np.where(g[max(0, y - 1):y + 2, max(0, x - 1):x + 2] == 4, 4, 10); g[y, x] = 16
        ents.append({"type": "settlement", "x": x, "y": y, "name": f"town_{i + 1}", "size": "town" if i == 0 else "village"})
    ents.insert(0, {"type": "start", "x": towns[0][0], "y": towns[0][1] + 2}) if towns else None
    forest = np.argwhere(g == 9)
    for (y, x) in forest[rng.choice(len(forest), min(len(forest), int(4 * enemies)), replace=False)] if len(forest) else []:
        if min(abs(x - tx) + abs(y - ty) for tx, ty in towns) > 6: ents.append({"type": "enemy_camp", "x": int(x), "y": int(y)})
    for tile, res in ((7, "ore"), (9, "lumber"), (6, "shells")):
        c = np.argwhere(g == tile)
        for (y, x) in c[rng.choice(len(c), min(len(c), int(5 * loot)), replace=False)] if len(c) else []: ents.append({"type": "resource", "resource": res, "x": int(x), "y": int(y)})
    return g, ents, {"settlements": len(towns), "roads": len(roads), "road_tiles": int(np.isin(g, [8, 15]).sum()), "towns": towns}


def settlement(w, h, rng, block=10, enemies=0.0, loot=1.0):
    g = np.full((h, w), 5); xs = list(range(2, w - 2, block)); ys = list(range(2, h - 2, block))
    for x in xs: g[1:h - 1, x:x + 2] = 8
    for y in ys: g[y:y + 2, 1:w - 1] = 8
    cx, cy = xs[len(xs) // 2], ys[len(ys) // 2]; g[cy - 3:cy + 5, cx - 3:cx + 5] = 16
    ents = [{"type": "start", "x": cx, "y": cy + 1}, {"type": "well", "x": cx + 1, "y": cy + 1}]; buildings = 0
    for bx in xs[:-1]:
        for by in ys[:-1]:
            x0, y0, x1, y1 = bx + 3, by + 3, bx + block - 1, by + block - 1
            if (g[y0:y1, x0:x1] == 16).any(): continue
            for _ in range(int(rng.integers(1, 4))):
                bw, bh = int(rng.integers(3, 5)), int(rng.integers(3, 5))
                if x1 - x0 - bw < 1 or y1 - y0 - bh < 1: continue
                px, py = int(rng.integers(x0, x1 - bw)), int(rng.integers(y0, y1 - bh))
                if (g[py - 1:py + bh + 1, px - 1:px + bw + 1] != 5).any(): continue
                g[py:py + bh, px:px + bw] = 10; dx = px + bw // 2; g[py + bh - 1, dx] = 3
                p = py + bh   # path from the door down to the nearest road
                while p < h - 1 and g[p, dx] not in (8, 16): g[p, dx] = 8; p += 1
                buildings += 1; ents.append({"type": "building", "x": px, "y": py, "w": bw, "h": bh, "door": [dx, py + bh - 1]})
    g[0] = g[-1] = 9; g[:, 0] = g[:, -1] = 9
    for i in range(int(3 * loot)): ents.append({"type": "market_stall", "x": cx - 2 + i * 2, "y": cy - 2})
    return g, ents, {"buildings": buildings, "blocks": (len(xs) - 1) * (len(ys) - 1)}
