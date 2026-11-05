"""PIXELCRAFT: the visual quality, UI/UX and interface efficiency department.

It audits the rendered application — not its source — in Chromium at iPhone-first viewports (iPhone 17, iPhone 13,
desktop, plus narrow, tablet and landscape), and scores three independent 100-point categories (Visual Quality,
Usability, Consistency) from measured evidence. Every finding carries its screen, viewport, selector, measurements,
severity, evidence kind, an annotated screenshot crop and a recommended correction.

Actions:
  profiles  the viewport profiles (CSS sizes, safe-area insets, touch) and the rubric
  discover  open the app and find its screens (links, nav, tabs) and how many taps each takes
  audit     discover + capture + measure + axe + states + journeys → scores, findings, plan, reports, history
  verify    replay a baseline audit exactly (same screens, viewports, journeys, method), diff screenshots, prove
            which defects are fixed, catch regressions and lost coverage
  history   the recorded audits of every app (trend per app; runs are never rewritten)

The app is never modified: the probe only loads, clicks, types and reads, and writes only to out_dir."""
import datetime, glob, hashlib, json, os, re, shutil, socket, subprocess, urllib.parse
import numpy as np
from PIL import Image
from core import runners, STUDIO_HOME, VERSION
from core.contract import StudioError, Blocked
import importlib.util as _ilu
HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    spec = _ilu.spec_from_file_location(f"pixelcraft_{name}", os.path.join(HERE, f"{name}.py")); m = _ilu.module_from_spec(spec); spec.loader.exec_module(m); return m


measure = _load("measure"); rubric = _load("rubric"); report = _load("report"); site = _load("site")

# iPhone-first viewport profiles (CSS pixels). Safe-area insets are the devices' own, emulated through CDP.
PROFILES = {
    "iphone17": {"name": "iphone17", "label": "iPhone 17", "width": 402, "height": 874, "mobile": True, "touch": True, "scale": 2, "safe": {"top": 62, "bottom": 34}, "ua_device": "iPhone 15 Pro"},
    "iphone13": {"name": "iphone13", "label": "iPhone 13", "width": 390, "height": 844, "mobile": True, "touch": True, "scale": 2, "safe": {"top": 47, "bottom": 34}, "ua_device": "iPhone 13"},
    "desktop": {"name": "desktop", "label": "Desktop", "width": 1440, "height": 900, "mobile": False, "touch": False, "scale": 1},
    "narrow": {"name": "narrow", "label": "Narrow mobile (iPhone SE 1st gen)", "width": 320, "height": 568, "mobile": True, "touch": True, "scale": 2, "safe": {"top": 20, "bottom": 0}, "ua_device": "iPhone SE"},
    "tablet": {"name": "tablet", "label": "Tablet (iPad Air)", "width": 820, "height": 1180, "mobile": True, "touch": True, "scale": 1, "safe": {"top": 24, "bottom": 20}, "ua_device": "iPad Pro 11"},
    "landscape": {"name": "landscape", "label": "iPhone 17 landscape", "width": 874, "height": 402, "mobile": True, "touch": True, "scale": 1, "safe": {"top": 0, "bottom": 21, "left": 62, "right": 62}, "ua_device": "iPhone 15 Pro"},
}
DEFAULT_VIEWPORTS = ["iphone17", "iphone13", "desktop", "narrow", "tablet", "landscape"]
REQUIRED = ["iphone17", "iphone13", "desktop"]   # iPhone-first is mandatory
BUILD_DIRS = ["dist", "build", "out", "public", "www", "site", "_site", "docs"]


def history_root():
    home = os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft")
    return os.environ.get("GITCRAFT_PIXELCRAFT_HISTORY") or os.path.join(home, "pixelcraft", "history")


# ---------------------------------------------------------------- targets
def _git(root, *args):
    try:
        r = subprocess.run(["git", "-c", "safe.directory=*", "-C", root, *args], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception: return None


def _git_state(root):
    if not root or not os.path.isdir(root): return None
    head = _git(root, "rev-parse", "HEAD")
    return {"head": head, "branch": _git(root, "rev-parse", "--abbrev-ref", "HEAD"), "dirty": bool(_git(root, "status", "--porcelain"))} if head else None


def _check_port(host, port):
    s = socket.socket(); s.settimeout(3)
    try: s.connect((host, port)); return None
    except PermissionError:
        return Blocked(f"the GITCRAFT sandbox blocks TCP to port {port} (no network by default)",
                       install=f"export GITCRAFT_ALLOW_LOCAL_PORTS={port} before starting Claude Code (then /mcp), or audit the built folder instead",
                       alternatives=["pixelcraft_audit {target: '<project>/dist'} — serves the build inside the sandbox", "run studio/cli.py outside the sandbox"])
    except OSError as e: return StudioError(f"nothing answers at {host}:{port} ({e.strerror or e}) — is the dev server running?", hint="start it (npm run dev / npm run preview) and retry")
    finally: s.close()


def resolve_target(ctx, p):
    """A running app (http URL) or a built folder (served inside the sandbox). Returns (target, app info)."""
    t, project = p.get("target"), p.get("project")
    root = ctx.need(project, "project") if project else None
    if t and re.match(r"^https?://", t):
        u = urllib.parse.urlparse(t)
        if u.hostname not in ("localhost", "127.0.0.1", "::1", "0.0.0.0") and not p.get("allow_remote"):
            raise StudioError(f"{u.hostname} is not a local address", hint="PIXELCRAFT audits local apps (dev server, preview, or a built folder); pass allow_remote: true for a deployed URL your environment can reach")
        err = _check_port(u.hostname if u.hostname != "0.0.0.0" else "127.0.0.1", u.port or (443 if u.scheme == "https" else 80))
        if err: raise err
        target = {"kind": "url", "url": t}
        label = t
    else:
        folder = ctx.need(t, "target") if t else None
        if not folder:
            if not root: raise StudioError("pass target (a built folder or a http://localhost URL) or project (a repo with a built folder)")
            cands = [os.path.join(root, d) for d in BUILD_DIRS if os.path.isfile(os.path.join(root, d, "index.html"))] + ([root] if os.path.isfile(os.path.join(root, "index.html")) else [])
            if not cands: raise StudioError(f"no built app found in {root} (looked for index.html in {', '.join(BUILD_DIRS)} and the root)",
                                            hint="build it first (npm run build), or start it and pass target: 'http://localhost:<port>'. Next.js server apps: next build && next start, then pass the URL")
            folder = cands[0]
        if os.path.isfile(folder): folder, entry = os.path.dirname(folder), os.path.basename(folder)
        else: entry = p.get("entry") or ""
        if not os.path.isfile(os.path.join(folder, entry or "index.html")): raise StudioError(f"no {entry or 'index.html'} in {folder}")
        target = {"kind": "folder", "root": folder, "entry": entry}
        label = folder
    name = p.get("app") or (os.path.basename(os.path.abspath(root)) if root else (os.path.basename(os.path.dirname(target["root"])) if target["kind"] == "folder" and os.path.basename(target["root"]) in BUILD_DIRS else
                            os.path.basename(target.get("root", "")) or urllib.parse.urlparse(label).netloc))
    return target, {"name": name, "target": label, "project": root, "git": _git_state(root or (target.get("root") if target["kind"] == "folder" else None))}


def _viewports(p):
    vs = []
    for v in p.get("viewports") or DEFAULT_VIEWPORTS:
        if isinstance(v, str):
            if v not in PROFILES: raise StudioError(f"unknown viewport profile {v!r}", hint=f"one of {', '.join(PROFILES)} or an object {{name, width, height, mobile}}")
            vs.append(dict(PROFILES[v]))
        else:
            if not all(k in v for k in ("name", "width", "height")): raise StudioError("a custom viewport needs name, width and height")
            vs.append(dict({"mobile": False, "touch": False, "scale": 1}, **v))
    missing = [r for r in REQUIRED if r not in [v["name"] for v in vs]]
    if missing and not p.get("allow_without_iphone"):
        raise StudioError(f"iPhone-first testing is mandatory: add {', '.join(missing)} to viewports", hint="or pass allow_without_iphone: true for a desktop-only tool (the report says so)")
    return vs


def _axe_path():
    for c in [os.path.join(STUDIO_HOME, "node", "node_modules", "axe-core", "axe.min.js"), "/opt/node-tools/node_modules/axe-core/axe.min.js"]:
        if os.path.exists(c): return c
    return None


def _probe(ctx, target, vps, p, screens=None, journeys=None):
    axe = _axe_path()
    req = {"target": target, "out_dir": ctx.out_dir, "viewports": vps, "axe_path": axe, "axe": p.get("axe", True),
           "screens": screens or p.get("screens") or None, "journeys": journeys if journeys is not None else (p.get("journeys") or None),
           "max_screens": p.get("max_screens", 8), "max_depth": p.get("max_depth", 2), "wait_ms": p.get("wait_ms", 600),
           "state_viewports": p.get("state_viewports") or [v["name"] for v in vps if v["name"] in ("iphone17", "desktop")] or [vps[0]["name"]],
           "toolbar_viewports": [v["name"] for v in vps if v.get("mobile") and v["height"] > v["width"]][:2],
           "reduced_motion": p.get("reduced_motion", False), "allow_origins": p.get("allow_origins") or []}
    ctx.used("studio_pixelcraft", "playwright", "chromium")
    if axe: ctx.used("axe-core")
    n = len(screens or p.get("screens") or []) or p.get("max_screens", 8)
    res = runners.node(os.path.join(HERE, "probe.mjs"), req, timeout=240 + n * len(vps) * 40)
    ctx.stage("probe", screens=len(res.get("screens", [])), captures=len(res.get("captures", [])), journeys=len(res.get("journeys", [])))
    return req, res


def _limits(vps, res, physical, target):
    L = ["Every viewport is browser emulation (Playwright + Chromium " + str(res.get("chromium") or "") + "); iPhone sizes are CSS pixels and safe-area insets are emulated through CDP (Emulation.setSafeAreaInsetsOverride). "
         "Safari-specific rendering (WebKit), the real on-screen keyboard and physical reach are not reproduced.",
         "Browser chrome: the first screen is re-measured with the viewport shortened by 120 px (Safari's toolbars); dynamic toolbar collapse is not reproduced.",
         "Keyboard interference: fields that would zoom on focus (font-size < 16 px) are measured; whether the on-screen keyboard covers a field is not testable in emulation.",
         "Hover/pressed/focus states are sampled once per visual variant of control; focus visibility comes from real Tab presses (desktop).",
         "Canvas-drawn interfaces (games): the DOM does not describe what is drawn, so DOM-geometry metrics cover only the HTML overlay (HUD, menus); use judgements for the canvas."]
    if physical: L.append("Physical-device evidence attached: " + ", ".join(d["label"] for d in physical) + " (shown in the gallery, recorded as screenshot evidence).")
    else: L.append("No physical-device evidence: findings are emulation results, not device results.")
    if res.get("blocked"): L.append(f"{len(res['blocked'])} request(s) outside the app's origin were blocked (no network): " + ", ".join(res["blocked"][:3]))
    if res.get("missing"): L.append(f"{len(res['missing'])} file(s) the app asked for were missing: " + ", ".join(res["missing"][:5]))
    if not _axe_path(): L.append("axe-core is not installed in the Studio runtime: accessibility rules did not run (scripts/install-studio.sh).")
    return L


def _context(vps, res, caps):
    js = res.get("journeys") or []
    return {"screens": len(res.get("screens") or []), "viewports": len(vps), "journeys": bool(js), "auto_journeys_only": bool(js) and all(j.get("auto") for j in js),
            "axe": any(c.raw.get("axe") and not c.raw["axe"].get("error") for c in caps), "canvas_heavy": any(c.canvas_heavy for c in caps)}


def _physical(ctx, p):
    out = []
    for i, d in enumerate(p.get("device_evidence") or []):
        src = ctx.need(d["path"], "device evidence")
        dst = ctx.path(os.path.join("gallery", f"physical_{i}{os.path.splitext(src)[1].lower()}")); shutil.copyfile(src, dst)
        out.append({"label": d.get("label") or d.get("device") or os.path.basename(src), "device": d.get("device"), "path": os.path.relpath(dst, ctx.out_dir), "note": d.get("note")})
    return out


def _judgements(p):
    out = []
    for j in p.get("judgements") or []:
        if j.get("area") not in rubric.AREA_CATEGORY: raise StudioError(f"judgement area {j.get('area')!r} is not a rubric area", hint=", ".join(rubric.AREA_CATEGORY))
        if not isinstance(j.get("score"), (int, float)) or not 0 <= j["score"] <= 1: raise StudioError("a judgement needs score 0..1")
        if j.get("evidence") == "measured": raise StudioError("judgements are screenshot-based visual judgements; they cannot claim 'measured'")
        out.append(dict(j, category=rubric.AREA_CATEGORY[j["area"]]))
    return out


def _assemble(ctx, app, vps, req, res, p, judgements, physical):
    if res.get("error"): raise StudioError(f"probe: {res['error']}")
    caps_ok = [c for c in res["captures"] if c.get("dom")]
    if not caps_ok:
        errs = sorted({c.get("error") or "" for c in res["captures"]})
        raise StudioError("no screen could be captured: " + "; ".join(errs)[:400], hint="check the target loads (missing files: " + ", ".join(res.get("missing", [])[:5]) + ")")
    caps, C = measure.analyse(res, vps, judgements)
    areas = rubric.area_scores(C.metrics)
    cats, overall = rubric.categories(areas, dict(_context(vps, res, caps), physical=bool(physical)))
    findings = rubric.prioritise(C.findings, len(caps_ok))
    report.annotate(findings, res["captures"], ctx.out_dir)
    report.thumbnails(res["captures"], ctx.out_dir)
    sheet = report.contact_sheet(res["captures"], ctx.path("contact_sheet.png"))
    primary = next((v["name"] for v in vps if v.get("mobile")), vps[0]["name"])
    for c in res["captures"]:   # paths relative to out_dir so the report folder can be moved/archived
        for k in ("shot", "full"):
            if c.get(k): c[k + "_rel"] = os.path.relpath(c[k], ctx.out_dir)
    A = {"pixelcraft": VERSION, "method": rubric.METHOD, "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "app": app,
         "viewports": vps, "primary_viewport": primary, "mobile_viewports": [v["name"] for v in vps if v.get("mobile")],
         "overall": overall, "categories": cats, "screens": res["screens"], "screens_ranked": rubric.screen_scores(C.metrics),
         "findings": findings, "metrics": C.metrics, "journeys": res.get("journeys", []),
         "gallery": [{"screen": c["screen"], "viewport": c["viewport"], "thumb": c.get("thumb"), "shot": c.get("shot_rel"), "full": c.get("full_rel")} for c in res["captures"] if c.get("thumb")],
         "captures": [{k: c.get(k) for k in ("screen", "viewport", "load_ms", "error", "page_errors", "console_errors", "cls", "shot_rel", "full_rel")} | {"axe": {"violations": [{"id": v["id"], "impact": v["impact"], "count": v["count"]} for v in (c.get("axe") or {}).get("violations", [])]} if c.get("axe") else None} for c in res["captures"]],
         "physical": physical, "judgements": judgements,
         "evidence_mix": _mix(C.metrics),
         "limits": _limits(vps, res, physical, req["target"]),
         "replay": {"target": req["target"], "viewports": vps, "screens": res["screens"], "journeys": res.get("journeys_used") or [], "max_screens": req["max_screens"],
                    "wait_ms": req["wait_ms"], "state_viewports": req["state_viewports"], "axe": req["axe"], "method": rubric.METHOD, "allow_origins": req["allow_origins"]}}
    json.dump(res, open(ctx.path("probe.json"), "w"), default=str)
    return A, caps, sheet


def _mix(metrics):
    out = {}
    for m in metrics: out[m["evidence"]] = out.get(m["evidence"], 0) + 1
    return out


def _write(ctx, A, sheet):
    outs = []
    p = ctx.path("audit.json"); json.dump(A, open(p, "w"), indent=1, default=str); outs.append({"path": p, "role": "audit", "format": "json"})
    p = ctx.path("report.md"); open(p, "w").write(report.markdown(A)); outs.append({"path": p, "role": "report", "format": "text"})
    p = ctx.path("report.html"); open(p, "w").write(report.html_report(A)); outs.append({"path": p, "role": "report", "format": "text"})
    if sheet: outs.append({"path": sheet, "role": "contact_sheet", "format": "png"})
    return outs


def _summary(A):
    return {"app": A["app"]["name"], "overall": A["overall"], "scores": {k: c["score"] for k, c in A["categories"].items()},
            "coverage": {k: c["coverage"] for k, c in A["categories"].items()},
            "screens": [s["name"] for s in A["screens"]], "viewports": [v["name"] for v in A["viewports"]],
            "top_findings": [{"title": f["title"], "severity": f["severity"], "frequency": f["frequency"], "evidence": f["evidence"], "fix": f["recommendation"]} for f in A["findings"][:8]],
            "findings": len(A["findings"])}


# ---------------------------------------------------------------- history (append-only)
def record(ctx, A, kind="audit"):
    root = history_root(); app = re.sub(r"[^a-z0-9]+", "-", A["app"]["name"].lower()).strip("-") or "app"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run = f"{stamp}-{kind}"; d = os.path.join(root, app, run)
    try:
        os.makedirs(d, exist_ok=False)
        for f in ("audit.json", "report.md", "report.html"):   # the contact sheet stays in out_dir (the gallery has the screens)
            if os.path.exists(os.path.join(ctx.out_dir, f)): shutil.copyfile(os.path.join(ctx.out_dir, f), os.path.join(d, f))
        for sub in ("gallery", "evidence", "diff"):
            if os.path.isdir(os.path.join(ctx.out_dir, sub)): shutil.copytree(os.path.join(ctx.out_dir, sub), os.path.join(d, sub))
        line = {"app": app, "name": A["app"]["name"], "run": run, "kind": kind, "created": A["created"], "method": A["method"], "overall": A["overall"]["score"],
                "confidence": A["overall"]["confidence"], "coverage": A["overall"]["coverage"], "scores": {k: c["score"] for k, c in A["categories"].items()},
                "findings": len(A["findings"]), "git": (A["app"].get("git") or {}).get("head"), "target": A["app"]["target"],
                "comparison": {k: v["delta"] for k, v in A["comparison"]["scores"].items()} if A.get("comparison") else None}
        with open(os.path.join(root, "index.jsonl"), "a") as f: f.write(json.dumps(line) + "\n")
        return {"recorded": d, "run": run}
    except OSError as e:
        ctx.note(f"history not recorded: {e}"); return {"recorded": None, "error": str(e)}


def _runs():
    p = os.path.join(history_root(), "index.jsonl")
    if not os.path.exists(p): return []
    return [json.loads(l) for l in open(p) if l.strip()]


# ---------------------------------------------------------------- actions
def profiles(ctx, p):
    data = {"viewports": PROFILES, "default": DEFAULT_VIEWPORTS, "required": REQUIRED, "method": rubric.METHOD,
            "categories": {k: {"title": v["title"], "areas": {a: {"title": t, "points": pts} for a, (t, pts) in v["areas"].items()}} for k, v in rubric.CATEGORIES.items()},
            "evidence_kinds": report.EVIDENCE_LABEL}
    out = ctx.path("profiles.json"); json.dump(data, open(out, "w"), indent=1)
    ctx.used("studio_pixelcraft")
    return {"outputs": [{"path": out, "role": "profiles", "format": "json"}], **data}


def discover(ctx, p):
    target, app = resolve_target(ctx, p)
    vps = _viewports(dict(p, viewports=p.get("viewports") or ["iphone17", "iphone13", "desktop"]))[:1]
    req, res = _probe(ctx, target, vps, dict(p, axe=False), journeys=[])
    if res.get("error"): raise StudioError(f"probe: {res['error']}")
    data = {"app": app, "screens": res["screens"], "blocked": res.get("blocked"), "missing": res.get("missing")}
    out = ctx.path("screens.json"); json.dump(data, open(out, "w"), indent=1)
    sheet = report.contact_sheet(res["captures"], ctx.path("screens.png"))
    outs = [{"path": out, "role": "screens", "format": "json"}] + ([{"path": sheet, "role": "contact_sheet", "format": "png"}] if sheet else [])
    return {"outputs": outs, "screens": res["screens"], "app": app,
            "checks": [{"name": "the app opened and at least one screen was captured", "ok": any(c.get("dom") for c in res["captures"]), "detail": [c.get("error") for c in res["captures"] if c.get("error")][:3]}]}


def audit(ctx, p):
    target, app = resolve_target(ctx, p)
    vps = _viewports(p); judgements = _judgements(p); physical = _physical(ctx, p)
    req, res = _probe(ctx, target, vps, p)
    A, caps, sheet = _assemble(ctx, app, vps, req, res, p, judgements, physical)
    outs = _write(ctx, A, sheet)
    hist = record(ctx, A) if p.get("record", True) else {"recorded": None}
    ctx.stage("report", findings=len(A["findings"]), overall=A["overall"]["score"])
    checks = [{"name": "screens captured at every viewport", "ok": all(c.get("dom") for c in res["captures"]), "detail": [f"{c['screen']}@{c['viewport']}: {c.get('error')}" for c in res["captures"] if not c.get("dom")][:5]},
              {"name": "iPhone viewports audited", "ok": all(any(v["name"] == r for v in vps) for r in REQUIRED) or bool(p.get("allow_without_iphone"))}]
    return {"outputs": outs, "checks": checks, "summary": _summary(A), "history": hist, "report": os.path.join(ctx.out_dir, "report.html")}


def _diff(a, b, out):
    A = Image.open(a).convert("RGB"); B = Image.open(b).convert("RGB")
    if A.size != B.size:
        h = min(A.size[1], B.size[1]); w = min(A.size[0], B.size[0]); A, B = A.crop((0, 0, w, h)), B.crop((0, 0, w, h))
    x, y = np.asarray(A, np.int16), np.asarray(B, np.int16)
    m = np.abs(x - y).max(axis=2) > 24
    pct = round(100 * float(m.mean()), 2)
    vis = (np.asarray(B, np.float32) * 0.35 + 255 * 0.65).astype(np.uint8); vis[m] = [230, 30, 60]
    im = Image.fromarray(vis); im.thumbnail((360, 860)); im.save(out, quality=80)
    return pct


def _key(m): return (m["area"], m["id"], m.get("screen"), m.get("viewport"), m.get("journey"))


def compare(before, after, out_dir):
    same = before.get("method") == after.get("method")
    bk = {_key(m): m for m in before["metrics"]}; ak = {_key(m): m for m in after["metrics"]}
    common = set(bk) & set(ak)
    lost = sorted({f"{k[1]}" + (f" ({k[2]} @ {k[3]})" if k[2] else "") for k in set(bk) - set(ak)})
    bs = rubric.area_scores([bk[k] for k in common]); as_ = rubric.area_scores([ak[k] for k in common])
    bc, _ = rubric.categories(bs, {}); ac, _ = rubric.categories(as_, {})
    scores = {}
    for k in rubric.CATEGORIES:
        b, a = bc[k]["score"], ac[k]["score"]
        scores[k] = {"title": rubric.CATEGORIES[k]["title"], "before": b, "after": a, "delta": round(a - b, 1) if a is not None and b is not None else None}
    ob = [v["before"] for v in scores.values() if v["before"] is not None]; oa = [v["after"] for v in scores.values() if v["after"] is not None]
    scores["overall"] = {"title": "Overall", "before": round(sum(ob) / len(ob), 1) if ob else None, "after": round(sum(oa) / len(oa), 1) if oa else None}
    scores["overall"]["delta"] = round(scores["overall"]["after"] - scores["overall"]["before"], 1) if ob and oa else None
    bf = {f["id"]: f for f in before["findings"]}; af = {f["id"]: f for f in after["findings"]}
    resolved = [{"id": k, "title": f["title"], "was": f["frequency"]} for k, f in bf.items() if k not in af]
    persisting = [{"id": k, "title": f["title"], "before": f["frequency"], "after": af[k]["frequency"]} for k, f in bf.items() if k in af]
    new = [{"id": k, "title": f["title"], "severity": f["severity"], "count": f["frequency"]} for k, f in af.items() if k not in bf]
    regressions = [f"new {n['severity']} finding: {n['title']} ({n['count']}×)" for n in new if n["severity"] in ("critical", "major")]
    for k in common:
        if bk[k]["value"] - ak[k]["value"] > 0.15 and bk[k]["evidence"] != "screenshot":
            regressions.append(f"{ak[k]['title']} on {k[2] or k[4] or 'app'} @ {k[3] or '—'}: {round(100 * bk[k]['value'])}% → {round(100 * ak[k]['value'])}%")
    shots = []
    bdir, adir = before.get("_dir"), after.get("_dir")
    gb = {(g["screen"], g["viewport"]): g for g in before.get("gallery", [])}
    os.makedirs(os.path.join(out_dir, "diff"), exist_ok=True)
    for g in after.get("gallery", []):
        o = gb.get((g["screen"], g["viewport"]))
        if not o or not o.get("shot") or not g.get("shot"): continue
        pa, pb = os.path.join(bdir, o["shot"]), os.path.join(adir, g["shot"])
        if not (os.path.exists(pa) and os.path.exists(pb)): continue
        name = f"{re.sub(r'[^a-z0-9]+', '-', g['screen'].lower())}__{g['viewport']}.jpg"
        pct = _diff(pa, pb, os.path.join(out_dir, "diff", name))
        shots.append({"screen": g["screen"], "viewport": g["viewport"], "changed_pct": pct, "diff": os.path.join("diff", name)})
    why = "same method, same screens, viewports and journeys; deltas use only metrics measured in both runs" if same else f"method changed ({before.get('method')} → {after.get('method')}): scores are not comparable"
    return {"comparable": same, "why": why, "scores": scores, "resolved": resolved, "persisting": persisting, "new": new, "regressions": regressions,
            "coverage_lost": lost, "screens": sorted(shots, key=lambda s: -s["changed_pct"]), "metrics_compared": len(common)}


def verify(ctx, p):
    bpath = ctx.need(p["baseline"], "baseline")
    if os.path.isdir(bpath): bpath = os.path.join(bpath, "audit.json")
    before = json.load(open(bpath)); before["_dir"] = os.path.dirname(bpath)
    rp = before["replay"]
    target = dict(rp["target"])
    if p.get("target"):   # a new build folder or URL for the same app (e.g. after rebuilding)
        t2, _ = resolve_target(ctx, {"target": p["target"], "project": p.get("project"), "allow_remote": p.get("allow_remote")}); target = t2
    elif target["kind"] == "url":
        u = urllib.parse.urlparse(target["url"]); err = _check_port(u.hostname if u.hostname != "0.0.0.0" else "127.0.0.1", u.port or 80)
        if err: raise err
    else: ctx.need(target["root"], "baseline target")
    app = dict(before["app"]); proj = p.get("project") or app.get("project")
    app["git"] = _git_state(proj or (target.get("root") if target["kind"] == "folder" else None)); app["target"] = target.get("url") or target.get("root")
    vps = rp["viewports"]
    # exactly the baseline's probe: same screens (with their steps), viewports, journeys, state sampling, method
    params = {"axe": rp.get("axe", True), "wait_ms": rp.get("wait_ms", 600), "state_viewports": rp.get("state_viewports"), "max_screens": rp.get("max_screens", 8), "allow_origins": rp.get("allow_origins")}
    screens = [{k: v for k, v in s.items() if k in ("name", "path", "steps", "depth", "via", "link_steps")} for s in rp["screens"]]
    req, res = _probe(ctx, target, vps, params, screens=screens, journeys=rp.get("journeys") or [])
    judgements = _judgements({"judgements": p.get("judgements") or before.get("judgements") or []}) if (p.get("judgements") or before.get("judgements")) else []
    A, caps, sheet = _assemble(ctx, app, vps, req, res, params, judgements, _physical(ctx, p))
    A["replay"]["journeys"] = rp.get("journeys") or []
    A["_dir"] = ctx.out_dir
    cmp = compare(before, A, ctx.out_dir); A.pop("_dir", None)
    A["comparison"] = cmp; A["baseline"] = {"path": bpath, "created": before.get("created"), "git": (before["app"].get("git") or {}).get("head"), "overall": before["overall"]["score"]}
    if p.get("changes"): A["changes"] = p["changes"]
    outs = _write(ctx, A, sheet)
    p2 = ctx.path("comparison.json"); json.dump(cmp, open(p2, "w"), indent=1); outs.append({"path": p2, "role": "comparison", "format": "json"})
    hist = record(ctx, A, "verify") if p.get("record", True) else {"recorded": None}
    checks = [{"name": "same PIXELCRAFT method as the baseline", "ok": cmp["comparable"], "detail": cmp["why"]},
              {"name": "no coverage lost (no check removed or weakened)", "ok": not cmp["coverage_lost"], "detail": cmp["coverage_lost"][:10]},
              {"name": "no regressions", "ok": not cmp["regressions"], "detail": cmp["regressions"][:10]}]
    return {"outputs": outs, "checks": checks, "summary": _summary(A), "comparison": {k: cmp[k] for k in ("scores", "resolved", "new", "regressions", "coverage_lost", "comparable")},
            "history": hist, "report": os.path.join(ctx.out_dir, "report.html")}


def history(ctx, p):
    runs = _runs()
    if p.get("app"): runs = [r for r in runs if r["app"] == p["app"] or r["name"] == p["app"]]
    apps = {}
    for r in runs: apps.setdefault(r["app"], []).append(r)
    lines = ["# PIXELCRAFT history", "", f"Store: `{history_root()}` (append-only)", ""]
    for a, rs in apps.items():
        lines += [f"## {rs[-1]['name']}", "", "| Run | Kind | Overall | Visual | Usability | Consistency | Confidence | Commit |", "|---|---|---|---|---|---|---|---|"]
        for r in rs: lines.append(f"| {r['run']} | {r['kind']} | {r['overall']} | {r['scores'].get('visual')} | {r['scores'].get('usability')} | {r['scores'].get('consistency')} | {r['confidence']} | {(r.get('git') or '')[:8]} |")
        lines.append("")
    o1 = ctx.path("history.json"); json.dump({"apps": apps}, open(o1, "w"), indent=1)
    o2 = ctx.path("history.md"); open(o2, "w").write("\n".join(lines) + "\n")
    ctx.used("studio_pixelcraft")
    return {"outputs": [{"path": o1, "role": "history", "format": "json"}, {"path": o2, "role": "history", "format": "text"}], "apps": {a: rs[-5:] for a, rs in apps.items()}, "store": history_root()}


ACTIONS = {"profiles": profiles, "discover": discover, "audit": audit, "verify": verify, "history": history}
