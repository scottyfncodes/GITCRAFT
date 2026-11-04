"""PLAYCRAFT: the game-design and gameplay-quality department.

Actions (the PLAYCRAFT pass, phases 1-4 and 6-7; phase 5, implementing, is done in the game's own repo by the
caller with the plan this produces):
  discover   phase 1  read the repo: intent, engine, build, controls, systems (file:line), genres
  play       phase 2  play the built game in Chromium on desktop + phone: response to every control, dead time,
                      idle motion, FPS, pause, touch targets, text size, overflow, errors, screenshots
  assess     phase 3  10-category scorecard with evidence levels, genre-specific criteria, ranked findings
  pass       1-4      discover + play + assess + a staged implementation plan + a baseline for verify
  verify     6-7      play and assess again, compare with the baseline, regressions, guardrails on the git diff,
                      before/after report
  full_pass           GITCRAFT engineering (TestCraft smoke + asset integrity) and PLAYCRAFT in one run, one plan
  genres              the genre intelligence (criteria, testing strategies, what to avoid)
Nothing is written into the game: outputs go to the out_dir (default <root>/gitcraft-out/playcraft/<name>)."""
import datetime, json, os, re, statistics, subprocess
import numpy as np
from core import runners, VERSION
from core.contract import StudioError
HERE = os.path.dirname(os.path.abspath(__file__))
import importlib.util as _ilu


def _load(name):
    spec = _ilu.spec_from_file_location(f"playcraft_{name}", os.path.join(HERE, f"{name}.py")); m = _ilu.module_from_spec(spec); spec.loader.exec_module(m); return m


scan = _load("scan"); rubric = _load("rubric"); report = _load("report")
PROFILES = json.load(open(os.path.join(HERE, "genres.json")))["genres"]
VIEWPORTS = {"desktop": {"name": "desktop", "width": 1280, "height": 720}, "laptop": {"name": "laptop", "width": 1440, "height": 900},
             "phone": {"name": "phone", "device": "iPhone 13"}, "phone_landscape": {"name": "phone_landscape", "device": "iPhone 13 landscape"},
             "android": {"name": "android", "device": "Pixel 7"}, "tablet": {"name": "tablet", "device": "iPad (gen 7)"}}
PROBE_KEY_ORDER = ["Space", "ArrowUp", "ArrowRight", "ArrowLeft", "ArrowDown", "KeyW", "KeyD", "KeyA", "KeyS", "Enter", "KeyE", "KeyF", "KeyJ", "KeyK", "KeyZ", "KeyX", "ShiftLeft"]
NOT_PROBED = {"Escape", "KeyP", "Tab", "KeyM", "KeyR"}   # pause, menus, restart: not "play" inputs
RESPONSE_WINDOW_MS = 800   # a change later than this is the game drifting on, not a response to the input
DEAD_TIME_OK = {"physics_puzzle": 0.6, "strategy": 0.7, "management_builder": 0.5, "incremental": 0.5, "simulation": 0.35}
DEPLOY_FILES = re.compile(r"(^|/)(vercel\.json|netlify\.toml|CNAME|firebase\.json|\.firebaserc|wrangler\.toml|fly\.toml|app\.yaml|render\.yaml|Dockerfile|Procfile|now\.json)$|^\.github/workflows/")
SECRET_FILES = re.compile(r"(^|/)\.env($|\.)|\.pem$|\.key$|id_rsa|credentials\.json$|service-account.*\.json$")
SECRET_TEXT = re.compile(r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|\bghp_[A-Za-z0-9]{30,}|\bxox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|(?i:(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"])")
DATA_FILES = re.compile(r"\.(sqlite3?|db|dump)$|(^|/)(prod|production)[^/]*/|seed[-_]?prod")


# ---------------------------------------------------------------- shared helpers
def _profile_for(genres):
    """Blend the profiles of the detected genres: weights, overrides, dead-time tolerance, criteria."""
    ids = [g["genre"] for g in genres]
    prof = {"weights": rubric.blend_weights(genres, PROFILES), "overrides": {}, "dead_time_ok": max([DEAD_TIME_OK.get(i, 0.25) for i in ids] or [0.25])}
    for i in ids: prof["overrides"].update(PROFILES[i].get("overrides", {}))
    return prof


def _criteria(genres):
    out, seen = list(rubric.CORE), {c["id"] for c in rubric.CORE}
    for g in genres:
        for c in PROFILES[g["genre"]].get("criteria", []):
            if c["id"] in seen: continue
            seen.add(c["id"]); out.append(dict(c, kind="signal", genre=g["genre"], genre_share=g.get("share") or 0.6))
    return out


def _extra_patterns():
    return {c["id"]: c["patterns"] for g in PROFILES.values() for c in g.get("criteria", []) if c.get("patterns")}


def _discover(ctx, project):
    root = ctx.need(project, "project")
    if not os.path.isdir(root): raise StudioError(f"project must be a folder (the game's repository): {root}")
    ctx.used("studio_playcraft")
    info = scan.scan(root, _extra_patterns())
    info["genre"] = scan.detect_genres(info, PROFILES)
    ctx.stage("discover", files=info["counts"]["source"], genres=[g["genre"] for g in info["genre"]["genres"]])
    return info


def _public(info):
    return {k: v for k, v in info.items() if not k.startswith("_")}


def _write_json(ctx, name, data, role="report"):
    p = ctx.path(name); json.dump(data, open(p, "w"), indent=1, default=str); return {"path": p, "role": role, "format": "json"}


def _write_text(ctx, name, text, role="report", fmt="text"):
    p = ctx.path(name); open(p, "w").write(text); return {"path": p, "role": role, "format": fmt}


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-c", "safe.directory=*", "-C", root, *args], capture_output=True, text=True, timeout=60)
        return r.stdout if r.returncode == 0 else None
    except Exception: return None


def _git_state(root):
    head = (_git(root, "rev-parse", "HEAD") or "").strip() or None
    return {"head": head, "branch": (_git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip() or None,
            "dirty": [l[3:] for l in (_git(root, "status", "--porcelain") or "").splitlines()][:200]}


# ---------------------------------------------------------------- phase 1: discover
def discover(ctx, p):
    info = _discover(ctx, p["project"])
    pub = _public(info)
    lines = [f"# PLAYCRAFT discovery: {info['title'] or info['name']}", "", f"> {info['pitch']}" if info.get("pitch") else "", "",
             f"- Engine: {', '.join(info['engine']['engines'])}; physics: {', '.join(info['engine']['physics']) or 'none'}",
             f"- Build: {info['build']['bundler'] or 'static'}; playable now: {info['build']['playable_dir'] or 'no — ' + str(info['build']['note'])}",
             f"- Mobile intended: {info['mobile']['intended']} ({'; '.join(info['mobile']['reasons'])})",
             f"- Controls found: {', '.join(info['keys'][:10]) or 'no keyboard keys'}; touch: {bool(info['signals']['input_touch']['count'])}; gamepad: {bool(info['signals']['input_gamepad']['count'])}",
             f"- Exposed game objects (for automated playtests): {', '.join(info['hooks']) or 'none'}",
             f"- Source files {info['counts']['source']}, tests {info['counts']['tests']}, audio files {info['counts']['audio']}, images {info['counts']['images']}, models {info['counts']['models']}",
             "", "## Genres", ""] + [f"- **{g['title']}** ({g['score']}, {int((g['share'] or 0) * 100)}% of best): {', '.join(g['evidence'][:8])}" for g in info["genre"]["genres"]]
    lines += ["", "## Systems present (inferred from source)", ""] + [f"- {scan.SIGNALS[k][1] if k in scan.SIGNALS else k}: {v['count']} hits in {v['files']} files — {v['where'][0] if v['where'] else ''}"
                                                                         for k, v in info["signals"].items() if v["count"]]
    lines += ["", "## Not found", "", ", ".join(scan.SIGNALS[k][1] for k, v in info["signals"].items() if not v["count"] and k in scan.SIGNALS)]
    outs = [_write_json(ctx, "discovery.json", pub), _write_text(ctx, "discovery.md", "\n".join(lines) + "\n")]
    checks = [{"name": "the repository has game source to read", "ok": info["counts"]["source"] > 0, "detail": info["counts"]},
              {"name": "at least one genre identified", "ok": bool(info["genre"]["genres"]), "detail": info["genre"]["primary"]}]
    return {"outputs": outs, "checks": checks, "game": {k: pub[k] for k in ("name", "title", "pitch", "engine", "build", "mobile", "keys", "hooks")}, "genre": info["genre"]}


# ---------------------------------------------------------------- phase 2: play
def _keys_for(info, explicit):
    if explicit: return explicit
    ks = [k for k in (info or {}).get("keys", []) if k not in NOT_PROBED]
    ordered = [k for k in PROBE_KEY_ORDER if k in ks] + [k for k in ks if k not in PROBE_KEY_ORDER]
    return ordered[:6] or ["Space", "ArrowUp", "ArrowRight"]


def _pause_keys(info):
    ks = (info or {}).get("keys", []); sig = ((info or {}).get("signals") or {}).get("pause", {}).get("count", 0)
    if not sig: return []
    return [k for k in ("Escape", "KeyP") if k in ks][:1] or ["Escape"]


def _img_stats(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"), float) / 255
    return {"std": round(float(a.std()), 4), "colours": int(len(np.unique((a * 31).astype(int).reshape(-1, 3), axis=0)))}


def _response(probe):
    """When did the screen first differ from what idling would have shown? (ms after the input, or None)"""
    idle, fr = probe["idle"], [f for f in probe["frames"] if f[0] > 0]
    if not fr: return None, 0.0
    env, mx, cum, idle_cum = [], 0.0, 0, []
    for f in idle:
        mx = max(mx, f[3]); env.append((f[0], mx)); cum += f[4]; idle_cum.append((f[0], cum))
    level = mx; margin = 0.0015 + 0.3 * level   # ≈ 8 of 5184 thumbnail pixels above what idling changes
    dts = sorted(f[1] for f in fr if f[1] > 0); frame = dts[len(dts) // 2] if dts else 16.7
    window = max(RESPONSE_WINDOW_MS, 4 * frame)   # at 4 fps, 800 ms is only three frames

    def at(series, t, default):
        v = default
        for tt, x in series:
            if tt <= t: v = x
            else: break
        return v
    cum, best_excess, hit = 0, 0.0, None
    for f in fr:
        t = f[0]; cum += f[4]
        excess = f[3] - at(env, t, level)
        best_excess = max(best_excess, excess)
        dom_hit = cum > 1.5 * at(idle_cum, t, idle_cum[-1][1] if idle_cum else 0) + 3
        if hit is None and t <= window and (excess > margin or dom_hit): hit = t
    return (round(hit) if hit is not None else None), round(best_excess, 4)


def _fps(dts):
    dts = [d for d in dts[1:] if 0 < d < 5000]   # a heavy scene in software WebGL can take seconds per frame: still a measurement
    if len(dts) < 2: return None, None, None
    sd = sorted(dts); return round(1000 * len(dts) / sum(dts), 1), round(sd[int(0.95 * (len(sd) - 1))], 1), round(sd[len(sd) // 2], 1)


def _frame_stats(frames):
    dts = [f[1] for f in frames[1:] if 0 < f[1] < 1000]
    if len(dts) < 5: return None, None, None, None
    fps = round(1000 * len(dts) / sum(dts), 1); sd = sorted(dts); p95 = round(sd[int(0.95 * (len(sd) - 1))], 1); p50 = round(sd[len(sd) // 2], 1)
    static = sum(1 for f in frames if f[2] < 0.002 and f[4] == 0) / len(frames)
    return fps, p95, round(static, 3), p50


def analyse(results):
    """Turn the probe's raw frame series into the metrics the rubric reads."""
    m = {"viewports": {}, "page_errors": [], "console_errors": [], "missing": [], "responses": [], "input_errors": [], "blocked": []}
    for R in results:
        vp = R["viewport"]; st = _img_stats(R["screenshots"][-1]) if R.get("screenshots") else {"std": 0, "colours": 0}
        started = next((s for s in R.get("screenshots", []) if s.endswith("_started.png")), None)
        if started: st = _img_stats(started)
        v = {"loaded": R.get("loaded", False), "touch": R.get("touch"), "load_ms": R.get("load_ms"), "start": R.get("start"), "colours": st["colours"], "std": st["std"],
             "blank": st["std"] < 0.01 or st["colours"] <= 3}
        for e in R["page_errors"]:
            if e not in m["page_errors"]: m["page_errors"].append(e)
        m["console_errors"] += [e for e in R["console_errors"] if e not in m["console_errors"]][:20]
        m["missing"] += [x for x in R["missing"] if x not in m["missing"] and not x.endswith("favicon.ico")]
        m["blocked"] += [x for x in R["blocked"] if x not in m["blocked"]][:10]
        by = {}
        for pr in R.get("probes", []):   # trials of the same control: it responds if any trial did; latency is the fastest
            ms, ex = _response(pr); m["input_errors"] += pr.get("errors", [])
            b = by.setdefault(pr["name"], {"viewport": vp, "slow": None, "input": pr["name"], "kind": pr["kind"], "touch": bool(R.get("touch")), "trials": [], "events_seen": 0})
            b["trials"].append(ms); b["events_seen"] += pr["events_seen"]; b["excess"] = max(b.get("excess", 0), ex)
        for b in by.values():
            hits = [x for x in b["trials"] if x is not None]
            b.update(responded=bool(hits), response_ms=min(hits) if hits else None, responded_trials=f"{len(hits)}/{len(b['trials'])}")
            m["responses"].append(b)
        if R.get("monkey"):
            fps, p95, dead, p50 = _frame_stats(R["monkey"]["frames"])
            pf = _fps(R.get("perf_dts") or R["monkey"].get("dts") or [])   # FPS from the clean window (no canvas reads)
            if pf[0]: fps, p95, p50 = pf
            v.update(fps=fps, frame_p95=p95, frame_p50=p50, dead_time=dead, monkey_s=round(R["monkey"]["ms"] / 1000, 1), monkey_inputs=R["monkey"]["inputs"])
            m["input_errors"] += R["monkey"].get("errors", [])
        if R.get("idle"):
            v["idle_motion"] = round(float(np.mean([f[2] for f in R["idle"]])), 5) if R["idle"] else None
        b, a = R.get("hooks_before") or {}, R.get("hooks_after") or {}
        v["hooks_found"] = bool(b); v["state_changed"] = sorted(k for k in a if b.get(k) != a.get(k))[:30]
        if R.get("pause"):
            bm = np.mean([f[2] for f in R["pause"]["before"]] or [0]); dm = np.mean([f[2] for f in R["pause"]["during"]] or [0])
            bmut = sum(f[4] for f in R["pause"]["before"])
            if bm < 0.001 and bmut < 3: v["pause"] = {"works": None, "detail": "nothing was moving before pausing (inconclusive)"}
            else: v["pause"] = {"works": bool(dm < 0.3 * bm or dm < 0.0003), "detail": f"{R['pause']['key']}: motion {bm:.4f} → {dm:.4f} while paused"}
        dom = R.get("dom") or R.get("dom_loaded") or {}
        v.update({k: dom.get(k) for k in ("viewport_meta", "canvas_touch_action", "body_touch_action", "small_targets", "small_target_count", "interactive", "min_font_px", "min_font_text")})
        v["overflow_px"] = max(0, (dom.get("scroll_width") or 0) - (dom.get("inner_width") or 0))
        end = R.get("dom_end") or {}   # the screen after play too (game-over cards have buttons the start screen does not)
        seen = {(t["text"], t["w"], t["h"]) for t in v.get("small_targets") or []}
        extra = [dict(t, screen="after play") for t in end.get("small_targets") or [] if (t["text"], t["w"], t["h"]) not in seen]
        if extra: v["small_targets"] = (v.get("small_targets") or []) + extra; v["small_target_count"] = (v.get("small_target_count") or 0) + len(extra)
        if end.get("min_font_px") is not None and (v.get("min_font_px") is None or end["min_font_px"] < v["min_font_px"]):
            v["min_font_px"], v["min_font_text"] = end["min_font_px"], end.get("min_font_text")
        m["viewports"][vp] = v
        for x in m["responses"]:
            if x["viewport"] == vp: x["slow"] = bool(v.get("fps") and v["fps"] < 10)
    vs = m["viewports"]; desk = next((v for k, v in vs.items() if not v.get("touch")), None); phone = next((v for k, v in vs.items() if v.get("touch")), None)
    m["loaded_any"] = any(v["loaded"] for v in vs.values())
    if desk:
        m.update(fps=desk.get("fps"), frame_p95=desk.get("frame_p95"), frame_p50=desk.get("frame_p50"), dead_time=desk.get("dead_time"), monkey_s=desk.get("monkey_s"), idle_motion=desk.get("idle_motion"),
                 load_ms=desk.get("load_ms"), start_ms=(desk.get("start") or {}).get("ms"), pause=desk.get("pause"), hooks_found=desk.get("hooks_found"), state_changed=desk.get("state_changed"))
        if desk.get("load_ms") is not None: m["time_to_play_ms"] = desk["load_ms"] + ((desk.get("start") or {}).get("ms") or 0)
    if phone:
        m["phone"] = phone; m["phone_fps"] = phone.get("fps")
        if not desk: m.update(dead_time=phone.get("dead_time"), monkey_s=phone.get("monkey_s"), idle_motion=phone.get("idle_motion"), fps=phone.get("fps"), frame_p95=phone.get("frame_p95"))
    fv = phone if phone and phone.get("min_font_px") is not None else desk
    if fv: m.update(min_font_px=fv.get("min_font_px"), min_font_text=fv.get("min_font_text"), min_font_viewport="phone" if fv is phone else "desktop")
    d_ms = sorted(r["response_ms"] for r in m["responses"] if r["responded"] and not r["touch"])
    t_ms = sorted(r["response_ms"] for r in m["responses"] if r["responded"] and r["touch"])
    m["best_response_ms"] = d_ms[0] if d_ms else (t_ms[0] if t_ms and not desk else None)
    m["median_response_ms"] = statistics.median(d_ms) if d_ms else None
    m["touch_best_response_ms"] = t_ms[0] if t_ms else None
    m["input_errors"] = sorted(set(m["input_errors"]))[:10]
    return m


def _play(ctx, p, info, sub="play"):
    target = p.get("target") or (info or {}).get("build", {}).get("playable_dir")
    if not target:
        raise StudioError("nothing playable: the game is not built", hint=(info or {}).get("build", {}).get("note") or "pass target=<folder with index.html>")
    t = ctx.need(target, "target")
    root, entry = (t, p.get("entry") or "index.html") if os.path.isdir(t) else (os.path.dirname(t), os.path.basename(t))
    if not os.path.exists(os.path.join(root, entry)): raise StudioError(f"no {entry} in {root}", hint="point target at the built folder (e.g. dist/)")
    vps = [VIEWPORTS[v] if isinstance(v, str) else v for v in p.get("viewports") or (["desktop", "phone"] if (info or {}).get("mobile", {}).get("intended", True) else ["desktop"])]
    ctx.used("playwright", "chromium")
    req = {"root": root, "entry": entry, "out_dir": os.path.join(ctx.out_dir, sub), "viewports": vps, "wait_ms": p.get("wait_ms", 2000),
           "keys": _keys_for(info, p.get("keys")), "pointer": p.get("pointer", True), "start_steps": p.get("start_steps") or [], "auto_start": p.get("auto_start", True),
           "monkey_ms": int(p.get("play_seconds", 8) * 1000), "trials": p.get("trials", 2), "hooks": p.get("hooks") or (info or {}).get("hooks", []) + ["game", "__game", "GAME", "__GAME__", "app", "__app", "state"],
           "pause_keys": p.get("pause_keys") if p.get("pause_keys") is not None else _pause_keys(info)}
    res = runners.node(os.path.join(HERE, "playprobe.mjs"), req, timeout=180 + len(vps) * (90 + req["monkey_ms"] / 1000 * 2))["results"]
    ctx.stage("play", viewports=[r["viewport"] for r in res])
    return res, analyse(res), req


def _play_outputs(ctx, res, metrics, req):
    from core import media
    shots = [s for r in res for s in r.get("screenshots", []) if os.path.exists(s)]
    outs = []
    if shots:
        sheet = ctx.path("play_contact_sheet.png")
        media.contact_sheet(shots, sheet, cols=4, cell=320, labels=[os.path.basename(s)[:-4] for s in shots], title="PLAYCRAFT play probe")
        outs.append({"path": sheet, "role": "preview", "format": "png"})
    for s in shots:
        if s.endswith(("_started.png", "_playing.png")): outs.append({"path": s, "role": "screenshot", "format": "png"})
    slim = [{k: v for k, v in r.items() if k not in ("probes", "idle", "monkey", "perf_dts")} | {"probes": [{k: v for k, v in pr.items() if k not in ("idle", "frames")} for pr in r.get("probes", [])]} for r in res]
    outs.append(_write_json(ctx, "play.json", {"request": {k: v for k, v in req.items() if k != "_result"}, "metrics": metrics, "results": slim}))
    _write_json(ctx, "play_frames.json", res, role="data")   # full frame series (kept, not listed as a deliverable)
    return outs, shots


def play(ctx, p):
    info = _discover(ctx, p["project"]) if p.get("project") else None
    res, m, req = _play(ctx, p, info)
    outs, shots = _play_outputs(ctx, res, m, req)
    checks = [{"name": "the probe played the game on every requested viewport", "ok": len(res) == len(req["viewports"]), "detail": [r["viewport"] for r in res]}]
    return {"outputs": outs, "checks": checks, "metrics": {k: v for k, v in m.items() if k not in ("viewports",)}, "viewports": m["viewports"]}


# ---------------------------------------------------------------- phase 3: assess
def _evidence_files(ctx, items):
    from core.contract import sha256
    out = []
    for e in items or []:
        src = ctx.need(e["source"], "evidence source")
        out.append(dict(e, source=src, sha256=sha256(src)))
    return out


def build_card(ctx, p, info, metrics, played_vps):
    genres = info["genre"]["genres"]
    if p.get("genres"):   # caller override: the person knows the game
        genres = [{"genre": g, "title": PROFILES[g]["title"], "share": 1.0 if i == 0 else 0.7, "score": None, "evidence": ["given by the caller"]} for i, g in enumerate(p["genres"])]
    prof = _profile_for(genres); crit = _criteria(genres)
    mobile = p.get("mobile") if p.get("mobile") is not None else info["mobile"]["intended"]
    js = p.get("judgements") or []
    for j in js:
        if j.get("level") == "verified": raise StudioError("judgements cannot be 'verified'", hint="verified evidence comes from the probe or from an `evidence` file (a test report) that PLAYCRAFT hashes")
        if not (j.get("evidence") or "").strip(): raise StudioError("every judgement needs `evidence`: what was seen while playing")
    results = rubric.evaluate(info, metrics, crit, prof, js, _evidence_files(ctx, p.get("evidence")), mobile)
    cats, overall = rubric.score(results, prof["weights"], mobile, played=bool(metrics))
    finds = rubric.findings(results, prof["weights"])
    answers = p.get("loop_answers") or {}
    disc = []
    for d, title in rubric.DISCIPLINES.items():
        rs = [r for r in results if r["discipline"] == d]
        qs = list(rubric.DISCIPLINE_QUESTIONS.get(d, []))
        for g in genres: qs += PROFILES[g["genre"]].get("questions", {}).get(d, [])
        disc.append({"id": d, "title": title, "results": rs, "questions": qs, "answers": {k: answers[k] for k in rubric.LOOP_ANSWERS if k in answers} if d == "loop_designer" else {},
                     "findings": [f["id"] for f in finds if f["discipline"] == d]})
    focus = [{"genre": g["genre"], "title": PROFILES[g["genre"]]["title"], "priorities": PROFILES[g["genre"]]["priorities"], "testing": PROFILES[g["genre"]].get("testing", []),
              "avoid": PROFILES[g["genre"]].get("avoid", [])} for g in genres]
    return {"version": VERSION, "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "game": {k: info.get(k) for k in ("name", "title", "pitch", "root", "engine", "build", "mobile", "counts")},
            "genre": {"genres": genres, "primary": genres[0]["genre"], "hybrid": info["genre"]["hybrid"]}, "weights": prof["weights"], "genre_focus": focus,
            "played": {"played": bool(metrics), "viewports": played_vps}, "overall": overall, "categories": cats, "results": results, "findings": finds,
            "disciplines": disc, "metrics": {k: v for k, v in (metrics or {}).items() if k != "viewports"} if metrics else None}


def _card_outputs(ctx, card, shots, plan=None, compare=None, stem="playcraft"):
    md = report.markdown(card, plan, compare)
    outs = [_write_json(ctx, f"{stem}.json", dict(card, plan=plan, compare=compare)), _write_text(ctx, f"{stem}_report.md", md)]
    outs.append(_write_text(ctx, f"{stem}_report.html", report.html_page(card, md, [s for s in shots if s.endswith(("_started.png", "_playing.png", "_after_play.png"))][:6],
                                                                      title=f"PLAYCRAFT: {card['game']['title'] or card['game']['name']}"), fmt="html"))
    return outs


def _card_checks(card):
    o = card["overall"]
    return [{"name": "every applicable category has a score or is marked not tested", "ok": all(c.get("score") is not None or c.get("confidence") == "none" or not c.get("applicable") for c in card["categories"].values())},
            {"name": "every criterion carries an evidence level", "ok": all(r["level"] in ("verified", "observed", "inferred", "not_tested") for r in card["results"])},
            {"name": "an unplayed game cannot score high-confidence", "ok": card["played"]["played"] or o["confidence"] != "high", "detail": o["confidence"]}]


def _summary(card):
    return {"overall": card["overall"], "categories": {k: v.get("score") for k, v in card["categories"].items()}, "genres": [g["genre"] for g in card["genre"]["genres"]],
            "top_findings": [f"{f['rank']}. {f['title']} ({f['type']}, {f['level']})" for f in card["findings"][:8]]}


def assess(ctx, p):
    info = _discover(ctx, p["project"])
    metrics, shots, vps = None, [], []
    if p.get("play_report"):
        d = json.load(open(ctx.need(p["play_report"], "play_report"))); metrics = d["metrics"]; vps = list(metrics["viewports"])
        shots = [s for r in d.get("results", []) for s in r.get("screenshots", [])]
    elif p.get("target") or (p.get("play", True) and info["build"]["playable_dir"]):
        res, metrics, req = _play(ctx, p, info); vps = [r["viewport"] for r in res]
        o, shots = _play_outputs(ctx, res, metrics, req)
    else:
        ctx.note("not played: " + (info["build"]["note"] or "play disabled") + " — scores rest on source and docs and are capped")
    card = build_card(ctx, p, info, metrics, vps)
    return {"outputs": _card_outputs(ctx, card, shots), "checks": _card_checks(card), "summary": _summary(card)}


# ---------------------------------------------------------------- phases 1-4: the pass
OWNER = {"audio": "audiocraft", "particles": "fxcraft", "animation": "animcraft", "visual": "photocraft/vectorcraft"}


def _owner(f):
    t = (f["id"] + " " + f["title"]).lower()
    if f["type"] == "defect" and f["category"] == "technical": return "engineering (testcraft)"
    if "audio" in t or "sound" in t: return "playcraft + audiocraft"
    if "particle" in t or "destruction" in t: return "playcraft + fxcraft"
    if "animation" in t or "anticipation" in t: return "playcraft + animcraft"
    return "playcraft"


def make_plan(card, limit=12):
    F = card["findings"]
    now = [f for f in F if f["type"] == "defect"]
    quick = [f for f in F if f not in now and f["effort"] <= 2 and f["impact"] >= 3][:6]
    bigger = [f for f in F if f not in now and f not in quick and f["impact"] >= 3][:6]
    item = lambda f: {"id": f["id"], "title": f["title"], "owner": _owner(f), "discipline": f["discipline"], "category": f["category"], "recommendation": f["recommendation"],
                      "evidence": f["evidence"], "where": f.get("where", []), "impact": f["impact"], "effort": f["effort"], "risk": f["risk"], "level": f["level"]}
    stages = [{"name": "1. Fix defects", "why": "verified failures on the running game; everything else is measured on top of a working build", "items": [item(f) for f in now]},
              {"name": "2. High-impact, low-effort feel and flow", "why": "biggest player-visible gain for the least risk; each is reversible", "items": [item(f) for f in quick]},
              {"name": "3. Deeper design work", "why": "bigger changes: prototype behind a flag or in a branch and re-run PLAYCRAFT verify", "items": [item(f) for f in bigger]}]
    return {"stages": [s for s in stages if s["items"]], "rules": [
        "Preserve the game's identity: every change must serve the pitch and the genre priorities above.",
        "Keep changes scoped and reversible: one improvement per commit, on a branch, never on main.",
        "Do not touch deployment settings, secrets or production data; do not delete features to simplify.",
        "After implementing, run the project's own tests and build, then PLAYCRAFT verify against this baseline."]}


def pass_(ctx, p):
    info = _discover(ctx, p["project"])
    metrics, shots, vps = None, [], []
    if p.get("target") or info["build"]["playable_dir"]:
        res, metrics, req = _play(ctx, p, info); vps = [r["viewport"] for r in res]
        o, shots = _play_outputs(ctx, res, metrics, req)
    else:
        ctx.note("PLAY phase skipped: " + (info["build"]["note"] or "nothing playable"))
    card = build_card(ctx, p, info, metrics, vps)
    plan = make_plan(card)
    card["baseline"] = {"git": _git_state(info["root"]), "target": p.get("target") or info["build"]["playable_dir"], "request": {k: v for k, v in p.items() if k in ("viewports", "keys", "start_steps", "play_seconds", "pointer", "pause_keys", "genres", "mobile", "hooks", "trials")}}
    outs = _card_outputs(ctx, card, shots, plan) + [_write_json(ctx, "plan.json", plan)]
    ctx.stage("plan", items=sum(len(s["items"]) for s in plan["stages"]))
    return {"outputs": outs, "checks": _card_checks(card), "summary": _summary(card), "plan": [f"{s['name']}: " + "; ".join(i["title"] for i in s["items"]) for s in plan["stages"]],
            "baseline": os.path.join(ctx.out_dir, "playcraft.json"), "next": "implement the plan in the game repo (branch, small commits), run its tests and build, then playcraft_verify with baseline=<this playcraft.json>"}


# ---------------------------------------------------------------- phases 6-7: verify and report
def _guardrails(root, base_head, allow):
    if not base_head or _git(root, "rev-parse", "HEAD") is None:
        return [{"name": "git history available for the guardrails", "ok": False, "detail": "the project is not a git repository or the baseline has no commit"}], {}
    ns = (_git(root, "diff", "--name-status", base_head) or "").splitlines()
    untracked = (_git(root, "ls-files", "--others", "--exclude-standard") or "").splitlines()
    ours = ("gitcraft-out/", ".gitcraft-work/")   # GITCRAFT's own reports are not changes to the game
    ns = [l for l in ns if not l.split("\t")[-1].startswith(ours)]; untracked = [u for u in untracked if not u.startswith(ours)]
    changed = [l.split("\t")[-1] for l in ns] + untracked
    deleted = [l.split("\t")[1] for l in ns if l.startswith("D")]
    diff = _git(root, "diff", base_head, "--", ".", ":(exclude)gitcraft-out", ":(exclude)*.lock", ":(exclude)package-lock.json", ":(exclude)pnpm-lock.yaml") or ""
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    for u in untracked[:200]:
        try:
            if os.path.getsize(os.path.join(root, u)) < 400_000: added += open(os.path.join(root, u), errors="ignore").read().splitlines()
        except OSError: pass
    stat = (_git(root, "diff", "--shortstat", base_head) or "").strip()
    deploy = [f for f in changed if DEPLOY_FILES.search(f)]
    secrets_f = [f for f in changed if SECRET_FILES.search(f) and not f.endswith((".example", ".sample"))]
    secrets_t = sorted({m.group(0)[:12] + "…" for l in added for m in [SECRET_TEXT.search(l)] if m})
    data = [f for f in changed if DATA_FILES.search(f)]
    src_deleted = [f for f in deleted if os.path.splitext(f)[1] in scan.SRC_EXT and f not in (allow.get("deletions") or [])]
    g = [{"name": "no source files deleted (features kept)", "ok": not src_deleted, "detail": src_deleted or "none"},
         {"name": "deployment settings unchanged", "ok": not deploy or allow.get("deploy_changes", False), "detail": deploy or "none"},
         {"name": "no secret files or secrets added", "ok": not secrets_f and not secrets_t, "detail": (secrets_f + secrets_t) or "none"},
         {"name": "no production data touched", "ok": not data, "detail": data or "none"},
         {"name": "work is on a branch, not the default branch", "ok": (_git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip() not in ("main", "master"),
          "detail": (_git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()}]
    return g, {"changed_files": changed[:200], "deleted": deleted, "stat": stat}


def compare_cards(before, after, changes):
    cats = {}
    for k, a in after["categories"].items():
        b = before["categories"].get(k, {})
        cats[k] = {"title": a["title"], "before": b.get("score"), "after": a.get("score"),
                   "delta": (a["score"] - b["score"]) if a.get("score") is not None and b.get("score") is not None else None}
    ob, oa = before["overall"]["score"], after["overall"]["score"]
    bm, am = before.get("metrics") or {}, after.get("metrics") or {}
    metrics, regress = [], []
    def num(name, k, worse_if, tol, fmt="{}"):
        if bm.get(k) is None and am.get(k) is None: return
        metrics.append({"name": name, "before": bm.get(k), "after": am.get(k)})
        if bm.get(k) is not None and am.get(k) is not None and worse_if(bm[k], am[k], tol): regress.append(f"{name}: {bm[k]} → {am[k]}")
    num("FPS (desktop, software rendering)", "fps", lambda b, a, t: a < b * (1 - t), 0.25)
    num("FPS (phone)", "phone_fps", lambda b, a, t: a < b * (1 - t), 0.25)
    num("fastest visible response (ms)", "best_response_ms", lambda b, a, t: a > b + t and a > b * 1.5, 50)
    num("touch response (ms)", "touch_best_response_ms", lambda b, a, t: a > b + t and a > b * 1.5, 50)
    num("dead time during play", "dead_time", lambda b, a, t: a > b + t, 0.15)
    num("time to play (ms)", "time_to_play_ms", lambda b, a, t: a > b * 1.5 + t, 500)
    for name, k in (("page errors", "page_errors"), ("missing files", "missing"), ("input errors", "input_errors")):
        nb, na = len(bm.get(k) or []), len(am.get(k) or [])
        if bm or am: metrics.append({"name": name, "before": nb, "after": na})
        if na > nb: regress.append(f"{name}: {nb} → {na} ({(am.get(k) or [])[:2]})")
    rb = sum(r["responded"] for r in bm.get("responses") or []); ra = sum(r["responded"] for r in am.get("responses") or [])
    if bm.get("responses") and am.get("responses"):
        metrics.append({"name": "probed inputs with a visible response", "before": f"{rb}/{len(bm['responses'])}", "after": f"{ra}/{len(am['responses'])}"})
        # a control that responded before and failed every trial now (one miss in a live game is not a regression)
        lost = [r["input"] + " (" + r["viewport"] + ")" for r in bm["responses"] if r["responded"] and any(x["input"] == r["input"] and x["viewport"] == r["viewport"] and not x["responded"] for x in am["responses"])]
        if lost: regress.append("inputs that no longer change the screen: " + ", ".join(lost))
    bf = {f["id"]: f for f in before["findings"]}; af = {f["id"]: f for f in after["findings"]}
    resolved = [f"{bf[i]['title']} ({bf[i]['level']} → now passing)" for i in bf if i not in af]
    new = [f"{af[i]['title']} ({af[i]['level']}): {report._short(af[i]['evidence'], 120)}" for i in af if i not in bf]
    for i in af:
        if i in bf and af[i]["level"] == "verified" and bf[i]["status"] == "partial" and af[i]["status"] == "fail": regress.append(f"{af[i]['title']} got worse")
    return {"categories": cats, "overall": {"before": ob, "after": oa, "delta": (oa - ob) if oa is not None and ob is not None else None},
            "metrics": metrics, "regressions": regress, "resolved": resolved, "new_findings": new, "changes": changes or [],
            "remaining": [f"{f['title']} ({f['type']}, {f['level']})" for f in after["findings"][:10]]}


NOISY = ("FPS", "fastest visible response", "touch response", "dead time", "inputs that no longer", "time to play")


def merge_runs(a, b):
    """Two plays of the same build: the best of each noisy measurement, a control responds if it did in either run."""
    m = dict(a)
    for k in ("fps", "phone_fps"): m[k] = max([x for x in (a.get(k), b.get(k)) if x is not None], default=None)
    for k in ("best_response_ms", "touch_best_response_ms", "dead_time", "time_to_play_ms"): m[k] = min([x for x in (a.get(k), b.get(k)) if x is not None], default=None)
    by = {(x["viewport"], x["input"]): dict(x) for x in a.get("responses", [])}
    for x in b.get("responses", []):
        y = by.setdefault((x["viewport"], x["input"]), dict(x))
        if y is not x:
            y["trials"] = y.get("trials", []) + x.get("trials", [])
            hits = [t for t in y["trials"] if t is not None]
            y.update(responded=bool(hits), response_ms=min(hits) if hits else None, responded_trials=f"{len(hits)}/{len(y['trials'])}")
    m["responses"] = list(by.values()); m["runs"] = 2
    for k in ("page_errors", "missing", "input_errors"): m[k] = sorted(set(a.get(k) or []) | set(b.get(k) or []))
    return m


def verify(ctx, p):
    base = json.load(open(ctx.need(p["baseline"], "baseline")))
    req = dict(base.get("baseline", {}).get("request") or {}); req.update({k: v for k, v in p.items() if v is not None})
    info = _discover(ctx, p.get("project") or base["game"]["root"])
    target = p.get("target") or base.get("baseline", {}).get("target")
    req["target"] = target
    metrics, shots, vps = None, [], []
    if target:
        res, metrics, preq = _play(ctx, req, info); vps = [r["viewport"] for r in res]
        o, shots = _play_outputs(ctx, res, metrics, preq)
    if not req.get("genres"): req["genres"] = [g["genre"] for g in base["genre"]["genres"]]   # same lens as the baseline
    card = build_card(ctx, req, info, metrics, vps)
    cmp = compare_cards(base, card, p.get("changes"))
    if metrics and any(r.startswith(NOISY) for r in cmp["regressions"]):
        # software-rendered FPS, latency and a control missing both trials vary between identical runs: replay once
        # more and keep only what reproduces (errors and missing files are never retried away)
        first = list(cmp["regressions"])
        res2, m2, _ = _play(ctx, req, info, sub="play_confirm")
        metrics = merge_runs(metrics, m2); card = build_card(ctx, req, info, metrics, vps)
        cmp = compare_cards(base, card, p.get("changes"))
        cmp["confirmation_run"] = {"first_run_regressions": first, "reproduced": cmp["regressions"],
                                   "not_reproduced": [r for r in first if r not in cmp["regressions"]]}
        ctx.stage("confirm", reproduced=len(cmp["regressions"]))
    allow = {"deletions": p.get("allow_deletions") or [], "deploy_changes": p.get("allow_deploy_changes", False)}
    guard, diff = _guardrails(info["root"], (base.get("baseline") or {}).get("git", {}).get("head"), allow)
    cmp["guardrails"] = guard; cmp["diff"] = diff
    ctx.stage("compare", regressions=len(cmp["regressions"]))
    outs = _card_outputs(ctx, card, shots, compare=cmp, stem="verify")
    lines = ["# PLAYCRAFT pass report", "", f"Game: **{card['game']['title'] or card['game']['name']}** · baseline {base['created']} · now {card['created']}", "",
             f"Changed: {diff.get('stat') or 'n/a'}", ""] + report.before_after_md(cmp)
    outs.append(_write_text(ctx, "pass_report.md", "\n".join(lines) + "\n"))
    checks = [{"name": "game played again with the baseline's probe", "ok": bool(metrics) or not (base.get("metrics")), "detail": vps},
              {"name": "no gameplay regressions", "ok": not cmp["regressions"], "detail": cmp["regressions"][:6]}] + guard
    return {"outputs": outs, "checks": checks, "compare": {k: cmp.get(k) for k in ("overall", "regressions", "resolved", "new_findings", "metrics", "confirmation_run")}, "guardrails": guard,
            "summary": _summary(card)}


# ---------------------------------------------------------------- GITCRAFT + PLAYCRAFT
def full_pass(ctx, p):
    """Engineering (TestCraft smoke on desktop/phone/tablet, asset integrity) and gameplay (the PLAYCRAFT pass) in one
    run. Overlaps are measured once: PLAYCRAFT's probe owns frame rate and input; TestCraft owns load errors per
    viewport and asset validity. The plan merges both, engineering defects first, with one owner per item."""
    from core import contract
    info = _discover(ctx, p["project"])
    target = p.get("target") or info["build"]["playable_dir"]
    eng = {}
    if target:
        mob = info["mobile"]["intended"]
        sm = contract.run("testcraft", "smoke", {"target": target, "viewports": ["desktop", "phone", "tablet"] if mob else ["desktop", "laptop"],
                                                 "out_dir": os.path.join(ctx.out_dir, "engineering", "smoke"), "allow_console_errors": True}, register=False)
        eng["smoke"] = {"status": sm.get("status"), "failed": [c for c in sm.get("checks", []) if not c["ok"]], "record": sm.get("record"), "reason": sm.get("reason")}
        tgt = ctx.need(target)
        if os.path.isdir(tgt):
            asr = contract.run("testcraft", "assets", {"folder": tgt, "out_dir": os.path.join(ctx.out_dir, "engineering", "assets"), "max_texture": p.get("max_texture", 4096)}, register=False)
            eng["assets"] = {"status": asr.get("status"), "failures": (asr.get("failures") or [])[:20], "by_format": asr.get("by_format"), "record": asr.get("record"), "reason": asr.get("reason")}
        ctx.used("playwright", "chromium"); ctx.stage("engineering")
    else:
        eng["note"] = info["build"]["note"]
    metrics, shots, vps = None, [], []
    if target:
        res, metrics, req = _play(ctx, dict(p, target=target), info); vps = [r["viewport"] for r in res]
        o, shots = _play_outputs(ctx, res, metrics, req)
    card = build_card(ctx, p, info, metrics, vps)
    plan = make_plan(card)
    # engineering items first; drop PLAYCRAFT items that duplicate a TestCraft failure (same symptom, one owner)
    eng_items = []
    for c in (eng.get("smoke") or {}).get("failed", []):
        eng_items.append({"id": "eng." + re.sub(r"\W+", "_", c["name"])[:40], "title": c["name"], "owner": "engineering (testcraft)", "recommendation": "fix before gameplay work: " + report._short(c.get("detail"), 160),
                          "evidence": c.get("detail"), "level": "verified", "category": "technical", "impact": 5, "effort": 2, "risk": 1})
    for f in (eng.get("assets") or {}).get("failures", [])[:8]:
        eng_items.append({"id": "eng.asset." + f["path"][:40], "title": f"asset fails validation: {f['path']}", "owner": "engineering (testcraft/assetcraft)", "recommendation": str(f.get("error")),
                          "evidence": f, "level": "verified", "category": "technical", "impact": 3, "effort": 1, "risk": 1})
    dup = {"tech.errors", "tech.missing", "tech.loads", "mob.overflow", "mob.renders"} if eng_items else set()
    for s in plan["stages"]: s["items"] = [i for i in s["items"] if i["id"] not in dup]
    if eng_items: plan["stages"].insert(0, {"name": "0. Engineering (GITCRAFT TestCraft)", "why": "the build must load cleanly on every target before feel and design work", "items": eng_items})
    plan["stages"] = [s for s in plan["stages"] if s["items"]]
    plan["coordination"] = ["One owner per item; overlapping symptoms are reported once (engineering wins for load/missing/overflow, PLAYCRAFT for input and frame pacing).",
                            "Stages are sequential: engineering fixes land first, then feel, then design; each stage is re-verified before the next.",
                            "Items that touch the same files (see `where`) go in one commit to avoid conflicting edits."]
    card["engineering"] = eng
    card["baseline"] = {"git": _git_state(info["root"]), "target": target, "request": {k: v for k, v in p.items() if k in ("viewports", "keys", "start_steps", "play_seconds", "pointer", "pause_keys", "genres", "mobile", "hooks", "trials")}}
    outs = _card_outputs(ctx, card, shots, plan, stem="playcraft") + [_write_json(ctx, "plan.json", plan), _write_json(ctx, "engineering.json", eng)]
    checks = _card_checks(card) + [{"name": "engineering checks ran (or were reported blocked)", "ok": bool(eng), "detail": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in eng.items()}}]
    return {"outputs": outs, "checks": checks, "summary": _summary(card), "engineering": {k: (v.get("status") if isinstance(v, dict) else v) for k, v in eng.items()},
            "plan": [f"{s['name']}: " + "; ".join(i["title"] for i in s["items"]) for s in plan["stages"]], "baseline": os.path.join(ctx.out_dir, "playcraft.json")}


def genres(ctx, p):
    ids = [p["genre"]] if p.get("genre") else list(PROFILES)
    L = ["# PLAYCRAFT genre intelligence", ""]
    for i in ids:
        g = PROFILES[i]
        L += [f"## {g['title']} (`{i}`)", "", "**Priorities:** " + "; ".join(g["priorities"]), "",
              "**Category weights:** " + (", ".join(f"{k} ×{v}" for k, v in g.get("weights", {}).items() if v != 1.0) or "neutral"), "", "**Genre criteria:**", ""]
        L += [f"- {c['title']} ({c['category']}) — {c['recommendation']}" for c in g.get("criteria", [])]
        L += ["", "**How to test it:** " + "; ".join(g.get("testing", [])), "", "**Do not bolt on:** " + "; ".join(g.get("avoid", [])), ""]
    ctx.used("studio_playcraft")
    return {"outputs": [_write_text(ctx, "genres.md", "\n".join(L)), _write_json(ctx, "genres.json", {i: PROFILES[i] for i in ids})],
            "checks": [{"name": "genre profiles have criteria, priorities and testing strategies", "ok": all(PROFILES[i].get("criteria") and PROFILES[i].get("priorities") and PROFILES[i].get("testing") for i in ids)}],
            "genres": {i: PROFILES[i]["title"] for i in ids}}


ACTIONS = {"discover": discover, "play": play, "assess": assess, "pass": pass_, "verify": verify, "full_pass": full_pass, "genres": genres}
