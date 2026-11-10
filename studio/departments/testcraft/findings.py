"""TestCraft's own reading of its checks, for reports: every failed check becomes a finding a person can act on.

  describe(check, record) → {title, measured, threshold, do, effort, category, viewport, criterion, evidence}

  title      a human title ("Phone frame rate below 30 FPS"), never "testcraft perf failed"
  measured   the measured value against its threshold ("1 FPS (threshold ≥ 30)")
  do         what to do next
  effort     TestCraft's own estimate for that kind of fix (S / M / L)
  category   project      a defect in the project
             environment  the measurement says more about the machine than the project: WebGL drawn by a software
                          rasteriser (SwiftShader, llvmpipe), or a request the sandbox blocked (no network in tests).
                          Reported as environment-limited / UNVERIFIED, never as a failure, never scored
  criterion  the failed criterion without the viewport ("average FPS ≥ 30"): with the department and the check it is
             the de-duplication key, so two runs of the same check give one finding

Standard library only: the Production Report reads it on the system Python too."""
import importlib.util, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SOFTWARE_GL = re.compile(r"swiftshader|llvmpipe|softpipe|software|basic render|mesa offscreen|lavapipe", re.I)
EFFORT = {"fps": "L", "frame_time": "L", "heap": "M", "page_errors": "M", "console": "S", "missing": "S", "blank": "M", "overflow": "S",
          "canvas": "M", "visual": "S", "assets": "S", "animation": "M", "unit": "M", "play": "M", "external": None}
VP = {"phone": "Phone", "desktop": "Desktop", "tablet": "Tablet", "laptop": "Laptop", "android": "Android phone", "phone_landscape": "Phone (landscape)"}


def _netclass():
    p = os.path.join(os.path.dirname(os.path.dirname(HERE)), "core", "netclass.py")
    spec = importlib.util.spec_from_file_location("gitcraft_testcraft_netclass", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def software_renderer(gpu=None, notes=()):
    """True when software rasterised WebGL drew the frames, False on a hardware GPU, None when unknown. Records made
    before the renderer was recorded say so in their notes (TestCraft always launched Chromium on SwiftShader)."""
    if isinstance(gpu, dict) and gpu.get("renderer"): return bool(SOFTWARE_GL.search(str(gpu["renderer"])))
    if isinstance(gpu, dict) and gpu.get("webgl") is False: return True
    if any(re.search(r"SwiftShader|software", str(n), re.I) for n in notes or ()): return True
    return None


def _result(record, vp):
    for key in ("results",):
        for r in record.get(key) or []:
            if isinstance(r, dict) and r.get("viewport") == vp: return r
    return {}


def _num(x):
    try: return float(x)
    except (TypeError, ValueError): return None


def _fmt(x, nd=1):
    v = _num(x)
    return "—" if v is None else (str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:.{nd}f}")


def _vp_title(vp):
    return VP.get(vp, vp.replace("_", " ").capitalize() if vp else "")


def console_requests(record, vp):
    """The requests behind console errors in one viewport: [{url, method, failure|status, environment}], from the
    run's failed-request log, or (records made before it existed) from the hosts the harness blocked."""
    nc = _netclass(); r = _result(record, vp); out = []
    blocked = list(r.get("blocked") or [])
    for q in r.get("failed_requests") or []:
        env = (q.get("status") is None and (bool(nc.SANDBOX.search(str(q.get("failure") or ""))) or q.get("url") in blocked)) \
              or (q.get("status") in (401, 403, 407) and nc.host(q.get("url") or "") not in ("game.local", ""))
        out.append(dict(q, environment=bool(env)))
    if not out:
        for u in blocked: out.append({"url": u, "method": "GET", "failure": "blocked by the test harness (no network in tests)", "environment": True})
    return out


def _console(vp, detail, record):
    errs = [d for d in (detail if isinstance(detail, list) else [detail] if isinstance(detail, str) and detail else []) if isinstance(d, str)]
    nc = _netclass()
    reqs = console_requests(record, vp)
    net_only = errs and all(nc.BROWSER_NET_MSG.search(e) for e in errs)
    env = bool(net_only and reqs and all(q["environment"] for q in reqs))
    shown = "; ".join(f"{q.get('method', 'GET')} {q['url']} ({q.get('failure') or q.get('status')})" for q in reqs[:3])
    measured = f"{len(errs)} console error(s): " + "; ".join(e[:90] for e in errs[:2]) + (f" — request(s): {shown}" if shown else " — no failed request was recorded with it")
    if env:
        hosts = sorted({nc.host(q["url"]) for q in reqs if q.get("url")})
        return {"title": f"{_vp_title(vp)}: console error from a request the sandbox blocked ({', '.join(hosts)})", "measured": measured, "threshold": "0 console errors",
                "category": "environment", "kind": "console",
                "do": f"Nothing to fix in the project for this run: {', '.join(hosts)} was unreachable from the test sandbox (no network in tests). "
                      "Verify it where the network is available (verify-live on the deployment)."}
    target = next((q["url"] for q in reqs if not q["environment"]), None) or (reqs[0]["url"] if reqs else None)
    return {"title": f"{_vp_title(vp)}: console errors on load", "measured": measured, "threshold": "0 console errors", "category": "project", "kind": "console",
            "do": (f"Fix or remove the failing request {target}" if target else "Open the page with the console and fix the error (re-run testcraft_smoke: it now records the failing URL)")
                  + "; then re-run testcraft_smoke."}


def describe(check, record):
    """One failed check of a TestCraft record → a finding a person can act on (see the module docstring)."""
    name = str(check.get("name") or ""); det = check.get("detail"); action = record.get("action")
    m = re.match(r"^(?P<vp>[\w]+): (?P<rest>.*)$", name)
    vp, rest = (m.group("vp"), m.group("rest")) if m and m.group("vp") in VP or (m and "baseline" not in name and action in ("smoke", "perf", "play")) else ("", name)
    V = _vp_title(vp)
    out = {"viewport": vp or None, "criterion": rest, "category": "project", "kind": "other"}
    gpu = ((record.get("perf") or {}).get(vp) or {}).get("gpu") if vp else None
    soft = software_renderer(gpu, record.get("notes"))
    if check.get("category") == "unverified" and check.get("cause") == "environment_limited": soft = True
    if (x := re.match(r"average FPS ≥ ([\d.]+)", rest)):
        out.update(kind="fps", title=f"{V} frame rate below {_fmt(x.group(1))} FPS", measured=f"{_fmt(det)} FPS average (threshold ≥ {_fmt(x.group(1))})",
                   threshold=f"≥ {_fmt(x.group(1))} FPS",
                   do="Profile the frame on a real phone (Chrome remote debugging) and cut the most expensive pass (draw calls, shadows, post-processing, "
                      "per-frame allocations); then re-run testcraft_perf on hardware.")
    elif (x := re.match(r"p95 frame time ≤ ([\d.]+) ms", rest)):
        out.update(kind="frame_time", title=f"{V} frame time spikes above {_fmt(x.group(1))} ms (95th percentile)",
                   measured=f"{_fmt(det)} ms at the 95th percentile (threshold ≤ {_fmt(x.group(1))} ms)", threshold=f"≤ {_fmt(x.group(1))} ms",
                   do="Find the long frames in a performance trace (garbage collection, shader compiles, asset loads mid-game) and move that work out of the frame; re-run testcraft_perf.")
    elif (x := re.match(r"JS heap ≤ ([\d.]+) MB", rest)):
        used = det.get("used_mb") if isinstance(det, dict) else det
        out.update(kind="heap", title=f"{V} memory above {_fmt(x.group(1))} MB", measured=f"{_fmt(used)} MB JS heap (threshold ≤ {_fmt(x.group(1))} MB)", threshold=f"≤ {_fmt(x.group(1))} MB",
                   do="Take a heap snapshot and release what outlives a level (textures, geometries, listeners); re-run testcraft_perf.")
    elif rest.startswith("no page errors"):
        errs = (det if isinstance(det, list) else [det]) or ["(no message)"]
        out.update(kind="page_errors", title=f"{V}: uncaught errors on the page" + (" while playing" if "during play" in rest else ""), threshold="0 uncaught errors",
                   measured=f"{len(errs)} uncaught error(s): " + "; ".join(str(e)[:120] for e in errs[:2]),
                   do="Fix the exception at the top of the stack trace (open the page with the console); re-run the TestCraft check.")
    elif rest == "no console errors":
        out.update(_console(vp, det, record))
    elif rest == "no missing files":
        miss = (det if isinstance(det, list) else [det]) or ["a file"]
        out.update(kind="missing", title=f"{V}: files the page requests are missing", threshold="0 missing files", measured=f"{len(miss)} missing: " + ", ".join(map(str, miss[:4])),
                   do=f"Add {miss[0]} to the build (or fix the path that requests it); re-run testcraft_smoke.")
    elif rest.startswith("renders something"):
        out.update(kind="blank", title=f"{V}: blank screen after load", threshold="std > 0.01 and > 3 colours", measured=f"screen statistics {det}",
                   do="Open the build and check what the first frame waits for (a failed asset, a user gesture, an exception); re-run testcraft_smoke.")
    elif rest == "no horizontal overflow":
        sw, iw = (det + [None, None])[:2] if isinstance(det, list) else (None, None)
        out.update(kind="overflow", title=f"{V}: page scrolls sideways", threshold=f"content width ≤ {iw} px", measured=f"content {sw} px wide in a {iw} px viewport",
                   do="Find the element wider than the viewport (min-width, fixed widths, long words) and let it shrink or wrap; re-run testcraft_smoke.")
    elif rest == "has a sized canvas":
        out.update(kind="canvas", title=f"{V}: no visible game canvas", threshold="a canvas with a size", measured=f"canvases {det}",
                   do="Check the canvas is created and sized before the first frame; re-run testcraft_smoke.")
    elif rest.startswith("external service") and check.get("category") == "unverified":
        out.update(kind="external", category="environment", title=f"{V}: {rest.replace('external service ', '').replace(' verified', '')} not reachable from the test sandbox",
                   threshold="reachable", measured=str(det)[:200], do="Nothing to fix in the project for this run; verify the integration where the network is available (verify-live).")
    elif (x := re.match(r"(.+?) matches baseline \(≤ ([\d.]+)% pixels differ\)", name)):
        d = det if isinstance(det, dict) else {}
        regs = d.get("regions") or []
        where = "; ".join(f"x{r[0]} y{r[1]} {r[2]}×{r[3]}" for r in regs[:4]) if regs else None
        mm = _num(d.get("mismatch"))
        out.update(kind="visual", viewport=None, title=f"Visual change against the baseline: {x.group(1)}",
                   measured=(f"{mm * 100:.1f}% of pixels differ (threshold ≤ {_fmt(x.group(2), 2)}%)" if mm is not None else f"{det}") + (f"; changed regions {where}" if where else ""),
                   threshold=f"≤ {_fmt(x.group(2), 2)}% of pixels", diff=d.get("diff"), regions=regs, baseline=d.get("baseline"), current=d.get("current"),
                   do="Look at the diff image. If the change was intended, accept it as the new baseline (testcraft_visual_diff with update_baseline: true, "
                      "or replace the baseline image); otherwise fix the regression and re-run testcraft_visual_diff.")
    elif re.match(r"\d+ assets open and validate", name):
        bad = det if isinstance(det, list) else []
        out.update(kind="assets", title="Assets that fail to open or validate", threshold="0 failures", measured=f"{len(bad)} failing: " + ", ".join(str(b.get('path') if isinstance(b, dict) else b) for b in bad[:4]),
                   do="Re-export or replace the listed files; re-run testcraft_assets.")
    elif name.startswith("clip ") or "frames" in name:
        out.update(kind="animation", title=f"Animation does not play: {name}", threshold="pixels change mid-clip", measured=str(det)[:200],
                   do="Check the clip has keyframes on the animated bones/objects and is exported; re-run testcraft_animation.")
    elif name == "unit tests pass":
        d = det if isinstance(det, dict) else {}
        out.update(kind="unit", title="Unit tests failing", threshold="0 failing tests", measured=f"{d.get('failed', '?')} failed, {d.get('passed', '?')} passed (exit {d.get('exit')})",
                   do="Run the project's test suite locally and fix the failing tests; re-run testcraft_unit.")
    elif action == "play":
        out.update(kind="play", title=f"{V or 'Gameplay'}: scripted check failed: {rest}", threshold="assertion holds", measured=f"value {det!r}"[:200],
                   do="Re-run the scripted play (testcraft_play) and inspect the step that failed; fix the game behaviour or the test step.")
    else:
        out.update(title=f"Check failed: {name}", threshold="check passes", measured=str(det)[:200] if det not in (None, "", [], {}) else "no value recorded",
                   do=f"Inspect the {action} report beside the record and re-run testcraft_{action}.")
    if out["kind"] in ("fps", "frame_time") and soft:
        rend = (gpu or {}).get("renderer") if isinstance(gpu, dict) else None
        out.update(category="environment", title=out["title"] + " — environment-limited (software WebGL)",
                   measured=out["measured"] + f"; drawn by {rend or 'a software rasteriser (SwiftShader)'}, so this measures the sandbox, not the game",
                   do="Not a project failure: re-run testcraft_perf on a machine with a hardware GPU (GITCRAFT_WEBGL=hardware) or measure on a real phone; "
                      "only a hardware-rendered run can fail a performance gate.")
    out["effort"] = None if out["category"] == "environment" else EFFORT.get(out["kind"])
    return out
