"""PLAYCRAFT Game Quality History: the persistent, cross-repository record of how every game evolves.

Standard library only (also imported by the static site publisher, forgecraft/ui_server.py).

Where it lives
  store    $GITCRAFT_PLAYCRAFT_HISTORY (default ~/.gitcraft/playcraft/history), beside the AssetCraft catalogue and
           outside ~/.gitcraft/runtime, so GITCRAFT upgrades (which replace the runtime) never touch it. Writable by
           studiocraft/forgecraft through scripts/mcp.sh, like the catalogue.
  archive  <GITCRAFT>/history/playcraft, the same format committed to git (cloud containers are ephemeral; git is
           the durable medium). Imported into the store automatically and idempotently; never written by a run.

Layout (store and archive)
  games/<game_id>/game.json               identity, repository, paths seen, genres, the pinned baseline run
  games/<game_id>/runs/<run_id>.json      one PLAYCRAFT run: kind, timestamps, commit, method fingerprint, scores,
                                          verified-only scores, evidence counts, criteria, findings, metrics, compare
  games/<game_id>/runs/<run_id>.card.json.gz   the full PLAYCRAFT card, byte-for-byte as written (provenance)
  games/<game_id>/events.jsonl            append-only: deployments, PR links, notes

Rules
  * Runs are immutable and content-addressed (run_id = assessed time + kind + card hash): recording the same card
    twice is a no-op, a different card never overwrites an existing file.
  * The baseline is pinned when a game's first run is recorded and never changes.
  * Comparisons never treat measurement as improvement: on the same commit every change is measurement; a
    different PLAYCRAFT method fingerprint is a method change; a criterion that moved to or from "not tested" is a
    coverage change; only status changes at verified/observed level between different commits count as real,
    and inferred ones are reported as unverified code changes. Each game's own same-commit runs give its
    measured noise band.
  * Games are only compared with themselves (their own genre profile and weights); portfolio rankings use change
    against each game's own baseline, never raw scores across genres.
  * A deployment is "live-verified" only when PLAYCRAFT itself matched the fetched live page against the local
    build of that commit; "deploy-reported" when the hosting/CI reported success; otherwise only "merged"."""
import datetime, gzip, hashlib, importlib.util, json, os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
SCHEMA = 1
METHOD_FILES = ("rubric.py", "genres.json", "scan.py", "playprobe.mjs", "dept.py")
ASSESS_KINDS = ("assess", "pass", "full_pass")
LIVE_LEVELS = ("merged", "deploy-reported", "live-verified")


def _rubric():
    spec = importlib.util.spec_from_file_location("playcraft_rubric_h", os.path.join(HERE, "rubric.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


rubric = _rubric()


def store_root():
    home = os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft")
    return os.environ.get("GITCRAFT_PLAYCRAFT_HISTORY") or os.path.join(home, "playcraft", "history")


def archive_root():
    return os.environ.get("GITCRAFT_PLAYCRAFT_ARCHIVE") or os.path.join(REPO, "history", "playcraft")


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def method_fingerprint():
    h = hashlib.sha256()
    for f in METHOD_FILES:
        try: h.update(open(os.path.join(HERE, f), "rb").read())
        except OSError: pass
    return h.hexdigest()[:12]


def _sha(b): return hashlib.sha256(b).hexdigest()


def _atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp{os.getpid()}"
    with open(tmp, "wb") as f: f.write(data if isinstance(data, bytes) else data.encode())
    os.replace(tmp, path)


def _json(path, default=None):
    try: return json.load(open(path))
    except (OSError, ValueError): return default


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-c", "safe.directory=*", "-C", root, *args], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception: return None


# ---------------------------------------------------------------- identity
def normalize_remote(url):
    """https://github.com/Owner/Repo(.git), git@github.com:owner/repo.git, proxy URLs ending in owner/repo → github.com/owner/repo."""
    if not url: return None
    u = url.strip().rstrip("/")
    u = re.sub(r"\.git$", "", u)
    m = re.match(r"^[\w.-]+@([\w.-]+):(.+)$", u)
    if m: host, path = m.group(1), m.group(2)
    else:
        m = re.match(r"^\w+://(?:[^@/]+@)?([^/]+)/(.+)$", u)
        if not m: return None
        host, path = m.group(1), m.group(2)
    parts = [p for p in path.split("/") if p]
    if len(parts) < 2: return None
    if "github" not in host and "gitlab" not in host and "bitbucket" not in host:
        # a session's local git proxy (loopback) in front of GitHub: http://127.0.0.1:<port>/git/<owner>/<repo>
        host = "github.com" if ("github" in u or host.split(":")[0] in ("127.0.0.1", "localhost", "::1")) else host
    return f"{host.lower()}/{parts[-2].lower()}/{parts[-1].lower()}"


def identity(root, name=None):
    remote = _git(root, "remote", "get-url", "origin") if root and os.path.isdir(root) else None
    key = normalize_remote(remote)
    if key:
        host, owner, repo = key.split("/")
        gid = f"{owner}--{repo}" if host == "github.com" else f"{host.replace('.', '-')}--{owner}--{repo}"
        url = f"https://{key}"
        return {"id": gid, "repo": f"{owner}/{repo}", "host": host, "url": url, "remote_key": key}
    base = re.sub(r"[^a-z0-9]+", "-", (name or os.path.basename(root or "game")).lower()).strip("-") or "game"
    return {"id": f"local--{base}-{hashlib.sha1(os.path.realpath(root or base).encode()).hexdigest()[:8]}", "repo": None, "host": None, "url": None, "remote_key": None}


def git_state(root):
    if not root or not os.path.isdir(root): return None
    head = _git(root, "rev-parse", "HEAD")
    if not head: return None
    st = _git(root, "status", "--porcelain") or ""
    dirty = [l[3:] for l in st.splitlines() if not l[3:].startswith(("gitcraft-out/", ".gitcraft-work/"))]
    return {"head": head, "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"), "dirty": dirty[:50], "source": "recorded"}


# ---------------------------------------------------------------- summarising a PLAYCRAFT card
def _short(x, n=160):
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    return s if len(s) <= n else s[:n] + "…"


def verified_view(card, levels=("verified",)):
    """Scores recomputed from the criteria at the given evidence levels only (never blended with inferred)."""
    rs = [r for r in card.get("results", []) if r.get("level") in levels]
    mobile = bool((card.get("categories", {}).get("mobile") or {}).get("applicable"))
    cats, overall = rubric.score(rs, card.get("weights") or {}, mobile, played=bool((card.get("played") or {}).get("played")))
    return {"overall": overall.get("score"), "categories": {k: v.get("score") for k, v in cats.items()}, "criteria": len(rs)}


def summarize(card):
    res = card.get("results", [])
    m = card.get("metrics") or {}
    resp = m.get("responses") or []
    metrics = {"responded": f"{sum(1 for r in resp if r.get('responded'))}/{len(resp)}" if resp else None,
               "best_response_ms": m.get("best_response_ms"), "touch_best_response_ms": m.get("touch_best_response_ms"),
               "fps": m.get("fps"), "phone_fps": m.get("phone_fps"), "software_gl": m.get("software_gl"), "renderer": m.get("renderer"),
               "time_to_play_ms": m.get("time_to_play_ms"), "dead_time": m.get("dead_time"), "page_errors": len(m.get("page_errors") or []),
               "missing": len(m.get("missing") or []), "min_font_px": m.get("min_font_px"),
               "small_targets": ((m.get("phone") or {}).get("small_target_count")), "pause_works": (m.get("pause") or {}).get("works")}
    starts = {}
    for vp, v in (m.get("viewports") or {}).items():
        s = v.get("start") or {}; starts[vp] = s.get("chain") or ([s.get("text")] if s.get("text") else [])
    metrics["start_chain"] = starts or None
    cmp = card.get("compare")
    compare = None
    if cmp:
        compare = {k: cmp.get(k) for k in ("overall", "regressions", "warnings", "resolved", "new_findings", "changes", "confirmation_run", "guardrails")}
        compare["categories"] = {k: v for k, v in (cmp.get("categories") or {}).items()}
        compare["diff"] = {k: (cmp.get("diff") or {}).get(k) for k in ("stat", "changed_files", "deleted")}
    return {
        "title": (card.get("game") or {}).get("title") or (card.get("game") or {}).get("name"),
        "pitch": (card.get("game") or {}).get("pitch"),
        "engine": ((card.get("game") or {}).get("engine") or {}).get("engines"),
        "genres": [{"genre": g["genre"], "title": g.get("title"), "share": g.get("share")} for g in (card.get("genre") or {}).get("genres", [])],
        "hybrid": (card.get("genre") or {}).get("hybrid"), "weights": card.get("weights"),
        "mobile": bool(((card.get("game") or {}).get("mobile") or {}).get("intended")),
        "played": (card.get("played") or {}).get("played"), "viewports": (card.get("played") or {}).get("viewports"),
        "overall": card.get("overall"),
        "categories": {k: {"title": v.get("title"), "score": v.get("score"), "confidence": v.get("confidence"), "applicable": v.get("applicable"),
                           "strong": v.get("strong_evidence_share")} for k, v in (card.get("categories") or {}).items()},
        "verified": verified_view(card), "measured": verified_view(card, ("verified", "observed")),
        "evidence": {lv: sum(1 for r in res if r.get("level") == lv) for lv in ("verified", "observed", "inferred", "not_tested")},
        "criteria": {r["id"]: {"s": r.get("status"), "l": r.get("level"), "c": r.get("category"), "t": r.get("title"), "i": r.get("impact"), "g": r.get("genre"),
                               "d": _short(r.get("detail"), 140)} for r in res if r.get("id")},
        "findings": [{"id": f["id"], "title": f["title"], "type": f["type"], "level": f["level"], "status": f["status"], "category": f["category"],
                      "impact": f.get("impact"), "priority": f.get("priority"), "evidence": _short(f.get("evidence"), 160)} for f in card.get("findings", [])],
        "metrics": metrics, "compare": compare,
        "plan": [s.get("name") for s in (card.get("plan") or {}).get("stages", [])] if isinstance(card.get("plan"), dict) else None,
    }


# ---------------------------------------------------------------- the store
class Store:
    def __init__(self, root=None, archive=None, sync=True):
        self.root = root or store_root(); self.archive = archive if archive is not None else archive_root()
        os.makedirs(os.path.join(self.root, "games"), exist_ok=True)
        if sync and self.archive and os.path.isdir(os.path.join(self.archive, "games")) and os.path.realpath(self.archive) != os.path.realpath(self.root):
            self.sync_from(self.archive)

    def gdir(self, gid): return os.path.join(self.root, "games", gid)
    def games(self): return sorted(d for d in os.listdir(os.path.join(self.root, "games")) if os.path.isfile(os.path.join(self.root, "games", d, "game.json")))
    def game(self, gid): return _json(os.path.join(self.gdir(gid), "game.json"))

    def runs(self, gid):
        d = os.path.join(self.gdir(gid), "runs")
        out = [_json(os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".json") and not f.endswith(".card.json")] if os.path.isdir(d) else []
        return sorted([r for r in out if r], key=lambda r: (r.get("assessed_at") or "", r["run_id"]))

    def events(self, gid):
        p = os.path.join(self.gdir(gid), "events.jsonl")
        if not os.path.exists(p): return []
        out = []
        for l in open(p):
            try: out.append(json.loads(l))
            except ValueError: pass
        return out

    def card(self, gid, run_id):
        p = os.path.join(self.gdir(gid), "runs", f"{run_id}.card.json.gz")
        return json.loads(gzip.open(p).read()) if os.path.exists(p) else None

    # -- writing
    def record(self, card_bytes, kind, *, root=None, out_dir=None, record_path=None, source_file=None, commit=None, pr=None, annotations=None, recorded_by="playcraft"):
        """Record one PLAYCRAFT card (the bytes of playcraft.json / verify.json). Idempotent; never overwrites."""
        card = json.loads(card_bytes)
        root = root or (card.get("game") or {}).get("root")
        ident = identity(root, (card.get("game") or {}).get("name"))
        gid = ident["id"]
        card_sha = _sha(card_bytes)
        assessed = card.get("created") or now()
        run_id = f"{re.sub(r'[^0-9]', '', assessed)[:14]}-{kind}-{card_sha[:8]}"
        rdir = os.path.join(self.gdir(gid), "runs"); rpath = os.path.join(rdir, f"{run_id}.json")
        if os.path.exists(rpath):
            existing = _json(rpath)
            return {"game_id": gid, "run_id": run_id, "new": False, "baseline_run": (self.game(gid) or {}).get("baseline_run"), "card_sha256": existing.get("card_sha256")}
        git = card.get("git") or ((card.get("baseline") or {}).get("git"))
        if git: git = dict(git, source=git.get("source") or ("recorded" if card.get("git") else "baseline field of the card"))
        if commit: git = dict(commit, source=commit.get("source") or "provided by the caller")
        run = {"schema": SCHEMA, "run_id": run_id, "game_id": gid, "kind": kind, "assessed_at": assessed, "recorded_at": now(), "recorded_by": recorded_by,
               "commit": git, "method": card.get("method"), "playcraft_version": card.get("version"), "card_sha256": card_sha,
               "provenance": {"out_dir": out_dir, "record": record_path, "source_file": source_file, "project_root": root, "annotations": annotations or None},
               "pr": pr, **summarize(card)}
        _atomic(os.path.join(rdir, f"{run_id}.card.json.gz"), gzip.compress(card_bytes, mtime=0))
        _atomic(rpath, json.dumps(run, indent=1, default=str))
        g = self.game(gid) or {"schema": SCHEMA, "id": gid, "created": now(), "paths_seen": [], "baseline_run": None}
        g.update({k: v for k, v in ident.items() if k != "id"}, name=(card.get("game") or {}).get("name") or g.get("name"), title=run["title"] or g.get("title"),
                 pitch=run.get("pitch") or g.get("pitch"), engine=run.get("engine") or g.get("engine"), updated=now())
        if root and root not in g["paths_seen"]: g["paths_seen"].append(root)
        if kind in ASSESS_KINDS or kind == "verify":
            if not g.get("baseline_run"): g["baseline_run"] = run_id; g["baseline_pinned_at"] = now()   # pinned once, never moved
            latest = self.runs(gid)[-1] if self.runs(gid) else run
            g["genres"] = latest.get("genres"); g["latest_run"] = latest["run_id"]
        _atomic(os.path.join(self.gdir(gid), "game.json"), json.dumps(g, indent=1, default=str))
        return {"game_id": gid, "run_id": run_id, "new": True, "baseline_run": g["baseline_run"], "card_sha256": card_sha}

    def add_event(self, gid, event):
        if not self.game(gid): raise ValueError(f"unknown game {gid!r}: record a PLAYCRAFT run for it first")
        ev = dict(event, recorded_at=event.get("recorded_at") or now())
        ev["id"] = ev.get("id") or _sha(json.dumps({k: v for k, v in ev.items() if k != "recorded_at"}, sort_keys=True, default=str).encode())[:16]
        if any(e.get("id") == ev["id"] for e in self.events(gid)): return ev   # idempotent
        p = os.path.join(self.gdir(gid), "events.jsonl"); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a") as f: f.write(json.dumps(ev, default=str) + "\n")
        return ev

    def sync_from(self, other):
        """Import every game/run/event of another store (the committed archive) that this store lacks."""
        n = 0
        for gid in sorted(os.listdir(os.path.join(other, "games"))):
            src = os.path.join(other, "games", gid)
            if not os.path.isfile(os.path.join(src, "game.json")): continue
            sg = _json(os.path.join(src, "game.json")) or {}
            for f in sorted(os.listdir(os.path.join(src, "runs")) if os.path.isdir(os.path.join(src, "runs")) else []):
                dst = os.path.join(self.gdir(gid), "runs", f)
                if not os.path.exists(dst): _atomic(dst, open(os.path.join(src, "runs", f), "rb").read()); n += 1
            g = self.game(gid)
            if not g: g = dict(sg)
            else:
                g["paths_seen"] = sorted(set(g.get("paths_seen", [])) | set(sg.get("paths_seen", [])))
                if sg.get("baseline_run") and (not g.get("baseline_run") or sg["baseline_run"] < g["baseline_run"]) and os.path.exists(os.path.join(self.gdir(gid), "runs", sg["baseline_run"] + ".json")):
                    g["baseline_run"] = sg["baseline_run"]   # the archive holds the original baseline
            rs = self.runs(gid)
            if rs: g["latest_run"] = rs[-1]["run_id"]; g["genres"] = rs[-1].get("genres")
            _atomic(os.path.join(self.gdir(gid), "game.json"), json.dumps(g, indent=1, default=str))
            for ev in [json.loads(l) for l in open(os.path.join(src, "events.jsonl"))] if os.path.exists(os.path.join(src, "events.jsonl")) else []:
                self.add_event(gid, ev)
        return n

    def export(self, dest):
        """Copy the store into dest (another store layout, e.g. the committed archive). Adds; never deletes or rewrites runs."""
        dst = Store(dest, archive="", sync=False); n = dst.sync_from(self.root)
        return {"dest": dest, "runs_added": n, "games": dst.games()}


# ---------------------------------------------------------------- analysis
RANK = {"pass": 2, "partial": 1, "fail": 0}
STRONG = ("verified", "observed")


def _short_sha(c): return ((c or {}).get("head") or "")[:7] or None


def same_commit(a, b):
    ca, cb = (a.get("commit") or {}), (b.get("commit") or {})
    if not ca.get("head") or not cb.get("head"): return None
    own = ("gitcraft-out/", ".gitcraft-work/")   # GITCRAFT's own reports in the game folder are not changes to the game
    dirty = lambda c: [d for d in c.get("dirty") or [] if not d.startswith(own)]
    return ca["head"] == cb["head"] and not dirty(ca) and not dirty(cb)


def compare_runs(a, b, noise=None):
    """a → b. Every criterion change is classified; nothing on an unchanged commit counts as improvement."""
    sc = same_commit(a, b)
    method_same = (a.get("method") == b.get("method")) if a.get("method") and b.get("method") else None
    changes = []
    ids = sorted(set(a["criteria"]) | set(b["criteria"]))
    for cid in ids:
        x, y = a["criteria"].get(cid), b["criteria"].get(cid)
        if x and y and x["s"] == y["s"] and x["l"] == y["l"]: continue
        rec = {"id": cid, "title": (y or x)["t"], "category": (y or x)["c"], "from": {"status": (x or {}).get("s"), "level": (x or {}).get("l")},
               "to": {"status": (y or {}).get("s"), "level": (y or {}).get("l")}, "detail": (y or x).get("d")}
        if not x or not y: rec["class"] = "coverage"; rec["why"] = "criterion " + ("added" if not x else "removed") + " (genre or method)"
        elif "not_tested" in (x["l"], y["l"]) or x["s"] == "unknown" or y["s"] == "unknown": rec["class"] = "coverage"; rec["why"] = "measured in only one run"
        elif x["s"] == y["s"]: rec["class"] = "evidence"; rec["why"] = f"same result, evidence {x['l']} → {y['l']}"
        else:
            up = RANK.get(y["s"], 0) > RANK.get(x["s"], 0)
            if sc: rec["class"] = "measurement"; rec["why"] = "same commit: the game did not change"
            elif x["l"] in STRONG and y["l"] in STRONG: rec["class"] = ("improved" if up else "regressed") + f" ({y['l']})"
            else: rec["class"] = "code change (unverified)"; rec["why"] = f"inferred from source: {'appeared' if up else 'disappeared'}"
            rec["direction"] = "up" if up else "down"
        changes.append(rec)
    d_all = (b["overall"].get("score") or 0) - (a["overall"].get("score") or 0) if b.get("overall") and a.get("overall") else None
    va, vb = (a.get("verified") or {}).get("overall"), (b.get("verified") or {}).get("overall")
    d_ver = (vb - va) if va is not None and vb is not None else None
    real_up = [c for c in changes if c.get("class", "").startswith("improved")]
    real_down = [c for c in changes if c.get("class", "").startswith("regressed")]
    unver = [c for c in changes if c.get("class") == "code change (unverified)"]
    band = noise if noise is not None else 3
    if sc: verdict = "measurement only (same commit)"
    elif real_up and not real_down: verdict = "genuine improvement"
    elif real_down and not real_up: verdict = "genuine regression"
    elif real_up and real_down: verdict = "mixed"
    elif unver: verdict = "code changed; not verified by measurement"
    elif d_all is not None and abs(d_all) <= band: verdict = "no measured change (within noise)"
    else: verdict = "score moved without a measured criterion change (method or coverage)"
    cats = {}
    for k in set(a.get("categories", {})) | set(b.get("categories", {})):
        sa, sb = (a["categories"].get(k) or {}).get("score"), (b["categories"].get(k) or {}).get("score")
        cats[k] = {"title": (b["categories"].get(k) or a["categories"].get(k) or {}).get("title"), "from": sa, "to": sb,
                   "delta": (sb - sa) if sa is not None and sb is not None else None,
                   "verified_from": (a.get("verified") or {}).get("categories", {}).get(k), "verified_to": (b.get("verified") or {}).get("categories", {}).get(k)}
    return {"from": a["run_id"], "to": b["run_id"], "same_commit": sc, "method_same": method_same,
            "commits": [_short_sha(a.get("commit")), _short_sha(b.get("commit"))],
            "overall": {"from": a["overall"].get("score"), "to": b["overall"].get("score"), "delta": d_all, "noise_band": band},
            "verified_overall": {"from": va, "to": vb, "delta": d_ver}, "categories": cats, "verdict": verdict,
            "counts": {"improved": len(real_up), "regressed": len(real_down), "unverified_code": len(unver),
                       "measurement": sum(1 for c in changes if c.get("class") == "measurement"), "coverage": sum(1 for c in changes if c.get("class") == "coverage")},
            "changes": changes}


def attribute_steps(vs, steps):
    """Re-classify a baseline→latest comparison by where each criterion actually changed: a flip that happened between
    two runs of the same commit is measurement (or a PLAYCRAFT method change), even if the endpoints' commits differ."""
    if not vs: return vs
    flips = {}
    for st in steps:
        for c in st["changes"]:
            if c.get("class") not in ("coverage", "evidence"): flips.setdefault(c["id"], []).append(st["same_commit"])
    for c in vs["changes"]:
        f = flips.get(c["id"])
        if f and all(x is True for x in f) and c.get("class") not in ("coverage", "evidence"):
            c["class"] = "measurement"; c["why"] = "changed between two runs of the same commit (measurement or PLAYCRAFT method), not by the game"
    real_up = [c for c in vs["changes"] if c.get("class", "").startswith("improved")]; real_down = [c for c in vs["changes"] if c.get("class", "").startswith("regressed")]
    vs["counts"] = {"improved": len(real_up), "regressed": len(real_down), "unverified_code": sum(1 for c in vs["changes"] if c.get("class") == "code change (unverified)"),
                    "measurement": sum(1 for c in vs["changes"] if c.get("class") == "measurement"), "coverage": sum(1 for c in vs["changes"] if c.get("class") == "coverage")}
    if not vs["same_commit"]:
        if real_up and not real_down: vs["verdict"] = "genuine improvement"
        elif real_down and not real_up: vs["verdict"] = "genuine regression"
        elif real_up and real_down: vs["verdict"] = "mixed"
        elif vs["counts"]["unverified_code"]: vs["verdict"] = "code changed; not verified by measurement"
        elif vs["overall"]["delta"] is not None and abs(vs["overall"]["delta"]) <= vs["overall"]["noise_band"]: vs["verdict"] = "no measured change (within noise)"
        else: vs["verdict"] = "score moved without a measured criterion change (method or coverage)"
    return vs


def noise_band(assess_runs):
    """Largest overall move between consecutive runs of the same commit and the same method: this game's measured noise."""
    deltas, pairs = [], []
    for a, b in zip(assess_runs, assess_runs[1:]):
        # noise = the same commit measured twice by the same PLAYCRAFT (an unrecorded or different method is a method change)
        if same_commit(a, b) and a.get("method") and a.get("method") == b.get("method"):
            if a["overall"].get("score") is not None and b["overall"].get("score") is not None:
                deltas.append(abs(b["overall"]["score"] - a["overall"]["score"])); pairs.append([a["run_id"], b["run_id"]])
    return {"band": max(deltas + [3]), "measured": bool(deltas), "samples": len(deltas), "pairs": pairs,
            "note": None if deltas else "no repeat runs of one commit with the same PLAYCRAFT method yet: default ±3"}


def track_findings(runs):
    """Every finding across the game's history: first/last seen, resolved (with the evidence level that showed it),
    reopened (it came back after being resolved)."""
    T = {}; prev = None
    for r in runs:
        crit = r.get("criteria", {})
        open_ids = {f["id"]: f for f in r.get("findings", [])}
        for fid, f in open_ids.items():
            t = T.setdefault(fid, {"id": fid, "title": f["title"], "category": f["category"], "type": f["type"], "first_seen": r["run_id"], "occurrences": 0,
                                   "state": "open", "resolved_in": None, "reopened": 0, "history": []})
            if t["state"] == "resolved": t["reopened"] += 1; t["history"].append({"run": r["run_id"], "event": "reopened", "level": f["level"]})
            elif not t["history"]: t["history"].append({"run": r["run_id"], "event": "found", "level": f["level"]})
            t.update(state="open", last_seen=r["run_id"], level=f["level"], status=f["status"], evidence=f.get("evidence"), impact=f.get("impact"))
            if f["type"] == "defect": t["type"] = "defect"
            t["occurrences"] += 1
        for fid, t in T.items():
            if fid in open_ids or t["state"] != "open": continue
            c = crit.get(fid)
            if c and c["s"] == "pass" and c["l"] != "not_tested":
                by = "measurement (same commit)" if prev is not None and same_commit(prev, r) else "change"
                t.update(state="resolved", resolved_in=r["run_id"], resolved_level=c["l"], resolved_by=by); t["history"].append({"run": r["run_id"], "event": "resolved", "level": c["l"], "by": by})
            elif not c or c["l"] == "not_tested":
                t["unmeasured_in"] = r["run_id"]
        prev = r
    last = runs[-1]["run_id"] if runs else None
    for t in T.values():
        if t["state"] == "open" and t.get("last_seen") != last: t["state"] = "not measured in latest"
    return sorted(T.values(), key=lambda t: ({"open": 0, "not measured in latest": 1, "resolved": 2}[t["state"]], -(t.get("impact") or 0)))


def regressions(runs):
    """Regression history: verify runs' confirmed regressions, plus criteria that got worse between assessments of
    different commits at verified/observed level."""
    out = []
    for r in runs:
        cmp = r.get("compare") or {}
        for x in cmp.get("regressions") or []:
            out.append({"run": r["run_id"], "kind": "verify", "what": x, "commit": _short_sha(r.get("commit")), "confirmed": bool(cmp.get("confirmation_run")) or None})
        for x in (cmp.get("confirmation_run") or {}).get("not_reproduced") or []:
            out.append({"run": r["run_id"], "kind": "verify (not reproduced: noise)", "what": x, "commit": _short_sha(r.get("commit")), "confirmed": False})
    assess = [r for r in runs if r["kind"] in ASSESS_KINDS]
    for a, b in zip(assess, assess[1:]):
        for c in compare_runs(a, b)["changes"]:
            if c.get("class", "").startswith("regressed"):
                out.append({"run": b["run_id"], "kind": "assessment", "what": f"{c['title']}: {c['from']['status']} → {c['to']['status']} ({c['to']['level']})", "criterion": c["id"],
                            "commit": _short_sha(b.get("commit")), "confirmed": True})
    counts = {}
    for x in out:
        if x.get("confirmed") is False: continue
        key = x.get("criterion") or re.sub(r":.*", "", x["what"])
        counts[key] = counts.get(key, 0) + 1
    return out, sorted([{"what": k, "times": v} for k, v in counts.items() if v >= 2], key=lambda x: -x["times"])


def improvement_passes(runs):
    out = []
    for r in runs:
        if r["kind"] != "verify" or not r.get("compare"): continue
        cmp = r["compare"]
        resolved = cmp.get("resolved") or []
        measured = [x for x in resolved if re.search(r"\((verified|observed) →", x)]
        out.append({"run": r["run_id"], "at": r["assessed_at"], "commit": _short_sha(r.get("commit")), "pr": r.get("pr"), "changes": cmp.get("changes") or [],
                    "resolved": resolved, "measurable": measured, "unmeasured": [x for x in resolved if x not in measured],
                    "regressions": cmp.get("regressions") or [], "not_reproduced": (cmp.get("confirmation_run") or {}).get("not_reproduced") or [],
                    "guardrails_ok": all(g.get("ok") for g in cmp.get("guardrails") or []) if cmp.get("guardrails") else None,
                    "overall": cmp.get("overall"), "diff": (cmp.get("diff") or {}).get("stat")})
    return out


def deployment_status(game, runs, events):
    deps = [e for e in events if e.get("type") == "deployment"]
    prs = [e for e in events if e.get("type") == "pr"]
    best = None
    for d in sorted(deps, key=lambda e: e.get("observed_at") or e["recorded_at"]):
        best = d
    latest_assessed = next((r for r in reversed(runs) if r["kind"] in ASSESS_KINDS), None)
    a_sha = ((latest_assessed or {}).get("commit") or {}).get("head")
    out = {"deployments": deps, "prs": prs, "latest_assessed_commit": a_sha[:7] if a_sha else None}
    if best:
        out.update(level=best.get("level"), url=best.get("url"), commit=(best.get("commit") or "")[:7] or None, observed_at=best.get("observed_at"), evidence=best.get("evidence"))
        out["assessed_is_deployed"] = bool(a_sha and best.get("commit") and a_sha.startswith(best["commit"][:7])) if a_sha and best.get("commit") else None
    else:
        out.update(level=None, note="no deployment recorded: nothing is claimed live")
    mains = sorted([e for e in events if e.get("type") == "main"], key=lambda e: e.get("observed_at") or e["recorded_at"])
    if mains:
        mc = mains[-1]["commit"]; out["main_commit"] = mc[:7]; out["main_observed_at"] = mains[-1].get("observed_at")
        out["assessed_is_main"] = bool(a_sha and a_sha.startswith(mc[:7])) if a_sha else None
        if best and best.get("commit"): out["deployed_is_main"] = best["commit"][:7] == mc[:7]
    return out


def game_report(store, gid, stale_days=14):
    g = store.game(gid); runs = store.runs(gid); events = store.events(gid)
    if not g or not runs: return None
    base = next((r for r in runs if r["run_id"] == g.get("baseline_run")), runs[0])
    assess = [r for r in runs if r["kind"] in ASSESS_KINDS or r["kind"] == "verify"]
    latest = assess[-1] if assess else runs[-1]
    nb = noise_band([r for r in runs if r["kind"] in ASSESS_KINDS])
    steps = [compare_runs(a, b, nb["band"]) for a, b in zip(assess, assess[1:])]
    vs_base = attribute_steps(compare_runs(base, latest, nb["band"]), steps) if latest["run_id"] != base["run_id"] else None
    findings = track_findings(assess)
    regs, recurring = regressions(runs)
    timeline = [{"run": r["run_id"], "kind": r["kind"], "at": r["assessed_at"], "commit": _short_sha(r.get("commit")), "method": r.get("method") or "unrecorded",
                 "overall": r["overall"].get("score"), "confidence": r["overall"].get("confidence"), "verified": (r.get("verified") or {}).get("overall"),
                 "measured": (r.get("measured") or {}).get("overall"), "categories": {k: v.get("score") for k, v in r["categories"].items()},
                 "evidence": r.get("evidence"), "played": r.get("played"), "start_chain": (r.get("metrics") or {}).get("start_chain"),
                 "is_baseline": r["run_id"] == base["run_id"]} for r in runs]
    age_days = None
    try: age_days = round((datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(latest["assessed_at"])).total_seconds() / 86400, 1)
    except Exception: pass
    return {"game": g, "baseline": base["run_id"], "latest": latest["run_id"], "runs": len(runs), "timeline": timeline, "vs_baseline": vs_base, "steps": steps,
            "noise": nb, "findings": findings, "regressions": regs, "recurring_regressions": recurring, "improvement_passes": improvement_passes(runs),
            "deployment": deployment_status(g, runs, events), "age_days": age_days, "stale": age_days is not None and age_days > stale_days,
            "genres": latest.get("genres"), "latest_summary": {"overall": latest["overall"], "verified": latest.get("verified"), "evidence": latest.get("evidence"),
                                                                "played": latest.get("played"), "metrics": latest.get("metrics")}}


def portfolio(store, stale_days=14):
    games = [game_report(store, gid, stale_days) for gid in store.games()]
    games = [g for g in games if g]
    rows = []
    for G in games:
        vb = G["vs_baseline"] or {}
        open_f = [f for f in G["findings"] if f["state"] == "open"]
        defects = [f for f in open_f if f["type"] == "defect"]
        strong_open = [f for f in open_f if f.get("level") in STRONG and (f.get("impact") or 0) >= 3]
        verdict = vb.get("verdict") or "baseline only"
        reasons, attention = [], 0.0
        if defects: attention += 4 * len(defects); reasons.append(f"{len(defects)} open defect(s): " + "; ".join(f["title"] for f in defects[:3]))
        if verdict in ("genuine regression", "mixed"): attention += 5; reasons.append(f"{verdict} since baseline")
        if G["recurring_regressions"]: attention += 3 * len(G["recurring_regressions"]); reasons.append("recurring regressions: " + ", ".join(x["what"] for x in G["recurring_regressions"][:3]))
        if G["stale"]: attention += 2; reasons.append(f"not assessed for {G['age_days']} days")
        if G["latest_summary"]["overall"].get("confidence") == "low": attention += 1.5; reasons.append("low-confidence assessment (mostly source evidence)")
        if not G["latest_summary"].get("played"): attention += 2; reasons.append("latest assessment did not play the game")
        if strong_open: attention += min(4, len(strong_open)); reasons.append(f"{len(strong_open)} measured issue(s) open, e.g. " + "; ".join(f"{f['title']} ({f['level']})" for f in strong_open[:2]))
        dep = G["deployment"]
        if dep.get("level") is None: attention += 0.5; reasons.append("no deployment evidence recorded")
        elif dep.get("assessed_is_deployed") is False: attention += 1; reasons.append(f"latest assessment ({dep.get('latest_assessed_commit')}) is not the deployed commit ({dep.get('commit')})")
        if dep.get("assessed_is_main") is False: attention += 2; reasons.append(f"main has moved to {dep.get('main_commit')} since the latest assessment ({dep.get('latest_assessed_commit')})")
        if not G["improvement_passes"]: attention += 1; reasons.append("no improvement pass yet")
        rows.append({"id": G["game"]["id"], "title": G["game"].get("title"), "repo": G["game"].get("repo"), "genres": G["genres"], "runs": G["runs"],
                     "overall": G["latest_summary"]["overall"].get("score"), "confidence": G["latest_summary"]["overall"].get("confidence"),
                     "verified_overall": (G["latest_summary"].get("verified") or {}).get("overall"),
                     "delta": (vb.get("overall") or {}).get("delta"), "verified_delta": (vb.get("verified_overall") or {}).get("delta"), "verdict": verdict,
                     "improved_criteria": (vb.get("counts") or {}).get("improved", 0), "regressed_criteria": (vb.get("counts") or {}).get("regressed", 0),
                     "noise_band": G["noise"]["band"], "age_days": G["age_days"], "stale": G["stale"], "open_defects": len(defects), "open_findings": len(open_f),
                     "resolved_findings": sum(1 for f in G["findings"] if f["state"] == "resolved" and f.get("resolved_by") == "change"), "recurring": G["recurring_regressions"],
                     "passes": len(G["improvement_passes"]), "deployment": {k: dep.get(k) for k in ("level", "url", "commit", "observed_at", "assessed_is_deployed", "main_commit", "assessed_is_main", "deployed_is_main", "latest_assessed_commit")},
                     "attention": round(attention, 1), "reasons": reasons})
    order_improved = sorted([r for r in rows if r["verdict"] == "genuine improvement"], key=lambda r: (-(r["improved_criteria"]), -(r["verified_delta"] or 0)))
    answers = {
        "improved_most": [{"game": r["title"], "verdict": r["verdict"], "improved_criteria": r["improved_criteria"], "verified_delta": r["verified_delta"], "delta": r["delta"]} for r in order_improved],
        "declined": [{"game": r["title"], "verdict": r["verdict"], "regressed_criteria": r["regressed_criteria"], "delta": r["delta"]} for r in rows if r["verdict"] in ("genuine regression", "mixed")],
        "not_assessed_recently": [{"game": r["title"], "age_days": r["age_days"], "why": "older than the stale threshold" if r["stale"] else f"main moved to {r['deployment'].get('main_commit')} after the latest assessment"}
                                  for r in rows if r["stale"] or r["deployment"].get("assessed_is_main") is False],
        "unresolved_defects": [{"game": G["game"].get("title"), "defects": [{"title": f["title"], "since": f["first_seen"], "level": f.get("level"), "evidence": f.get("evidence")} for f in G["findings"] if f["state"] == "open" and f["type"] == "defect"]} for G in games if any(f["state"] == "open" and f["type"] == "defect" for f in G["findings"])],
        "recurring_regressions": [{"game": r["title"], "recurring": r["recurring"]} for r in rows if r["recurring"]],
        "measurable_improvements": [{"game": G["game"].get("title"), "run": p["run"], "pr": p.get("pr"), "measurable": p["measurable"], "unmeasured": p["unmeasured"], "changes": [c.get("title") for c in p["changes"]]}
                                    for G in games for p in G["improvement_passes"] if p["measurable"]],
        "needs_attention_next": [{"game": r["title"], "attention": r["attention"], "reasons": r["reasons"]} for r in sorted(rows, key=lambda r: -r["attention"])],
        "same_commit_measurement": [{"game": G["game"].get("title"), "noise_band": G["noise"]["band"], "samples": G["noise"]["samples"]} for G in games if G["noise"]["measured"]],
    }
    return {"generated": now(), "games": sorted(rows, key=lambda r: -r["attention"]), "answers": answers,
            "rules": ["Each game is compared only with its own baseline under its own genre profile; raw scores are never ranked across games.",
                      "On an unchanged commit every change is measurement. Improvements count only when a criterion changed at verified/observed level between different commits.",
                      "Verified-only scores are kept separately and never blended with inferred evidence.",
                      "A deployment is live-verified only when PLAYCRAFT matched the live page against the local build of that commit."]}, games


# ---------------------------------------------------------------- deployment evidence
def verify_live(live_html_path, build_dir):
    """Compare a fetched live index.html with the local build of a commit: every hashed asset reference (Vite/webpack
    fingerprints) and script/style URL in the live page must be present in the build's index.html, and the build's
    referenced files must exist. Returns (ok, detail)."""
    live = open(live_html_path, encoding="utf-8", errors="ignore").read()
    local_index = os.path.join(build_dir, "index.html")
    if not os.path.exists(local_index): return False, f"no index.html in {build_dir}"
    local = open(local_index, encoding="utf-8", errors="ignore").read()
    refs = lambda h: sorted(set(re.findall(r'(?:src|href)=["\']([^"\']+\.(?:js|mjs|css))(?:\?[^"\']*)?["\']', h)))
    lr, br = refs(live), refs(local)
    strip = lambda u: re.sub(r"^(?:https?://[^/]+)?/?(?:[A-Za-z0-9_-]+/)?(?=assets/|src/)", "", u).lstrip("./")
    ln, bn = sorted(map(strip, lr)), sorted(map(strip, br))
    hashed = [u for u in bn if re.search(r"[-.][A-Za-z0-9_]{8,}\.(?:js|mjs|css)$", u)]
    if not bn: return False, "the local build references no scripts or styles to compare"
    same = ln == bn
    detail = {"live_refs": ln[:12], "build_refs": bn[:12], "fingerprinted": len(hashed), "identical_html": _sha(live.encode()) == _sha(local.encode())}
    if not same: return False, dict(detail, why="the live page references different scripts/styles than this build")
    if not hashed and not detail["identical_html"]:
        return False, dict(detail, why="same file names but no content fingerprints: cannot tell which commit is live")
    return True, detail


# ---------------------------------------------------------------- the static site view (forgecraft/ui_server.py --publish)
def site_view(store):
    """Everything the Games page renders, from recorded runs only (no new measurement, no network)."""
    P, games = portfolio(store)
    out = {"generated": P["generated"], "rules": P["rules"], "portfolio": P["games"], "answers": P["answers"], "games": {}}
    for G in games:
        gid = G["game"]["id"]
        vb = G["vs_baseline"]
        out["games"][gid] = {
            "id": gid, "title": G["game"].get("title"), "repo": G["game"].get("repo"), "url": G["game"].get("url"), "pitch": G["game"].get("pitch"),
            "engine": G["game"].get("engine"), "genres": G["genres"], "baseline": G["baseline"], "latest": G["latest"], "runs": G["runs"], "noise": G["noise"],
            "timeline": G["timeline"], "age_days": G["age_days"], "deployment": G["deployment"],
            "vs_baseline": None if not vb else {k: vb[k] for k in ("verdict", "same_commit", "commits", "overall", "verified_overall", "categories", "counts")}
                           | {"changes": [{k: c.get(k) for k in ("id", "title", "category", "class", "from", "to", "why")} for c in vb["changes"]]},
            "steps": [{k: s[k] for k in ("from", "to", "verdict", "same_commit", "commits", "overall", "counts")} for s in G["steps"]],
            "findings": [{k: f.get(k) for k in ("id", "title", "category", "type", "state", "level", "first_seen", "last_seen", "resolved_in", "resolved_level", "resolved_by",
                                                 "reopened", "occurrences", "impact", "evidence")} for f in G["findings"]],
            "regressions": G["regressions"], "recurring": G["recurring_regressions"], "passes": G["improvement_passes"],
            "events": [{k: e.get(k) for k in ("type", "url", "commit", "level", "observed_at", "recorded_at", "evidence", "note", "state", "title", "live_check")} for e in store.events(gid)],
            "provenance": [{"run": r["run_id"], "kind": r["kind"], "assessed_at": r["assessed_at"], "recorded_at": r["recorded_at"], "recorded_by": r.get("recorded_by"),
                            "commit": (r.get("commit") or {}).get("head"), "commit_source": (r.get("commit") or {}).get("source"), "method": r.get("method"),
                            "card_sha256": r["card_sha256"], "pr": r.get("pr")} for r in store.runs(gid)]}
    return out


def publish_site(archive, dist_games, ui_dir=None):
    """Write the Games page (UI + data.json) for a store/archive folder into dist_games. Returns the number of games."""
    import shutil
    ui_dir = ui_dir or os.path.join(HERE, "ui")
    if os.path.isdir(dist_games): shutil.rmtree(dist_games)
    shutil.copytree(ui_dir, dist_games)
    st = Store(archive, archive="", sync=False) if os.path.isdir(os.path.join(archive, "games")) else None
    view = site_view(st) if st else {"generated": now(), "rules": [], "portfolio": [], "answers": {}, "games": {}}
    view["source"] = {"archive": os.path.relpath(archive, REPO) if archive.startswith(REPO) else archive, "note": "a snapshot of the committed Game Quality History"}
    _atomic(os.path.join(dist_games, "data.json"), json.dumps(view, default=str))
    return len(view["games"])
