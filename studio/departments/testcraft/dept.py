"""TestCraft: automated QA for web games and assets. Browser work is Playwright + Chromium
(core/web/testcraft.mjs); image comparison, asset integrity and reports are Python. Every run writes
a JSON report and a self-contained HTML report next to its screenshots."""
import html, json, os, subprocess, sys, base64
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
from core import media, runners, validate as V, webpages
from core.contract import StudioError

VIEWPORTS = {"desktop": {"name": "desktop", "width": 1280, "height": 720}, "laptop": {"name": "laptop", "width": 1440, "height": 900},
             "phone": {"name": "phone", "device": "iPhone 13"}, "phone_landscape": {"name": "phone_landscape", "device": "iPhone 13 landscape"},
             "android": {"name": "android", "device": "Pixel 7"}, "tablet": {"name": "tablet", "device": "iPad (gen 7)"}}


def _target(ctx, p):
    t = ctx.need(p["target"], "target")
    if os.path.isdir(t): return t, p.get("entry") or "index.html"
    return os.path.dirname(t), os.path.basename(t)


def _img_stats(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert("RGB"), float) / 255
    return {"std": round(float(a.std()), 4), "distinct_colours": int(len(np.unique((a * 31).astype(int).reshape(-1, 3), axis=0)))}


def _browser(ctx, p, steps=None, perf_ms=0, record=False):
    root, entry = _target(ctx, p); ctx.used("playwright", "chromium")
    vps = [VIEWPORTS[v] if isinstance(v, str) else v for v in p["viewports"]]
    return runners.node("testcraft.mjs", {"root": root, "entry": entry, "out_dir": ctx.out_dir, "viewports": vps, "wait_ms": p["wait_ms"],
                                          "steps": steps or [], "perf_ms": perf_ms, "record_video": record}, timeout=120 + len(vps) * (60 + perf_ms / 1000))["results"]


def _report(ctx, title, sections, checks):
    """Self-contained HTML report (screenshots inlined as data URIs, scaled)."""
    from PIL import Image
    import io
    def thumb(p):
        im = Image.open(p).convert("RGB"); im.thumbnail((480, 480)); b = io.BytesIO(); im.save(b, "JPEG", quality=80)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    ok = all(c["ok"] for c in checks)
    lab = lambda c: c["category"].upper() if c.get("category") in ("unverified", "advisory") else "PASS" if c["ok"] else "FAIL"
    rows = "".join(f"<tr class='{'ok' if c['ok'] else 'bad'}'><td>{lab(c)}</td><td>{html.escape(c['name'])}</td><td><code>{html.escape(json.dumps(c.get('detail'), default=str)[:300])}</code></td></tr>" for c in checks)
    body = ""
    for s in sections:
        imgs = "".join(f"<figure><img src='{thumb(i)}'><figcaption>{html.escape(os.path.basename(i))}</figcaption></figure>" for i in s.get("images", []) if os.path.exists(i))
        body += f"<section><h2>{html.escape(s['title'])}</h2><pre>{html.escape(json.dumps(s.get('data', {}), indent=1, default=str)[:4000])}</pre><div class='g'>{imgs}</div></section>"
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>body{{font:14px system-ui,sans-serif;margin:16px;background:#f6f7f9;color:#1d2330}}h1{{font-size:20px}}.badge{{padding:2px 8px;border-radius:4px;color:#fff;background:{'#1f8a4c' if ok else '#c0392b'}}}
table{{border-collapse:collapse;width:100%;background:#fff}}td{{border-bottom:1px solid #e3e6ea;padding:6px;vertical-align:top}}tr.bad td:first-child{{color:#c0392b;font-weight:700}}tr.ok td:first-child{{color:#1f8a4c}}
code{{font-size:12px;word-break:break-all}}section{{background:#fff;margin:16px 0;padding:12px;border-radius:6px}}pre{{font-size:12px;overflow:auto;max-height:240px;background:#f0f2f5;padding:8px}}
.g{{display:flex;flex-wrap:wrap;gap:8px}}figure{{margin:0;max-width:100%}}img{{max-width:100%;border:1px solid #ddd}}figcaption{{font-size:12px;color:#667}}</style></head>
<body><h1>{html.escape(title)} <span class="badge">{'PASS' if ok else 'INCOMPLETE' if all(c.get('category') == 'unverified' for c in checks if not c['ok']) else 'FAIL'} {sum(c['ok'] for c in checks)}/{len(checks)}</span></h1><table>{rows}</table>{body}
<p style="color:#889">GITCRAFT TestCraft · Playwright + Chromium</p></body></html>"""
    path = ctx.path(f"{ctx.params.get('name') or ctx.action}_report.html"); open(path, "w").write(page); return path


def _console_checks(vp, r, p):
    """The smoke test's console-error policy (core/netclass.py). Never a global ignore:
      * errors the browser raised for requests the harness blocked (no network in tests) are explained, and each
        blocked host becomes an UNVERIFIED check: its integration was not tested here, which is not a defect;
      * errors matched by a documented exception ({pattern, reason, host?}) are listed with their reason;
      * anything else fails the check, or with the deprecated allow_console_errors is an ADVISORY (still listed).
    Page exceptions and missing files are separate checks and are never excepted."""
    from core import netclass
    cons = netclass.classify_console(r["console_errors"], r.get("console_error_sources"), r.get("blocked"), p.get("console_error_exceptions"))
    out = []
    if cons["unexplained"] and p.get("allow_console_errors"):
        out.append({"name": f"{vp}: no console errors", "ok": True, "category": "advisory",
                    "detail": {"unexplained (allow_console_errors: reported, not ignored)": cons["unexplained"][:3]}})
    else:
        out.append({"name": f"{vp}: no console errors", "ok": not cons["unexplained"],
                    "detail": cons["unexplained"][:3] or ({"explained": [e["text"][:120] for e in cons["sandbox"] + cons["excepted"]][:4]} if cons["sandbox"] or cons["excepted"] else [])})
    if cons["excepted"]:
        out.append({"name": f"{vp}: console errors covered by documented exceptions", "ok": True, "category": "advisory",
                    "detail": [f"{e['text'][:100]} — {e['reason']}" for e in cons["excepted"]][:5]})
    if cons["refused_exceptions"]:
        out.append({"name": f"{vp}: console-error exceptions are narrow and documented", "ok": False,
                    "detail": [f"{x['why']}: {x['exception']}" for x in cons["refused_exceptions"]][:3]})
    types = {}
    for i, u in enumerate(r.get("blocked") or []):
        h = netclass.host(u)
        if h: types.setdefault(h, set()).add((r.get("blocked_types") or [])[i] if i < len(r.get("blocked_types") or []) else "other")
    for h, ts in sorted(types.items()):
        if ts & DEPENDENCY_TYPES or "other" in ts:   # data, scripts, sockets: the app depends on it → its integration is unverified
            out.append({"name": f"{vp}: external service {h} verified", "ok": False, "category": "unverified", "cause": "sandbox_network", "host": h,
                        "detail": f"blocked by the test harness (no network here; {', '.join(sorted(ts))}): the integration is not verified here, "
                                  "which is not a defect; verify it in production (verify-live)"})
        else:   # fonts, styles, images, media from a CDN: presentation, not an integration
            out.append({"name": f"{vp}: external resources from {h} loaded", "ok": True, "category": "advisory",
                        "detail": f"blocked by the test harness ({', '.join(sorted(ts))}): not loaded here; the page was checked without them"})
    return out


DEPENDENCY_TYPES = {"fetch", "xhr", "script", "websocket", "eventsource", "document"}


def smoke(ctx, p):
    res = _browser(ctx, p); checks = []; outs = []; sections = []
    for r in res:
        vp = r["viewport"]; st = _img_stats(r["screenshots"][0])
        checks += [{"name": f"{vp}: no page errors", "ok": not r["page_errors"], "detail": r["page_errors"][:3]}] + _console_checks(vp, r, p) + [
                   {"name": f"{vp}: no missing files", "ok": not r["missing"], "detail": r["missing"][:5]},
                   {"name": f"{vp}: renders something (not a blank screen)", "ok": st["std"] > 0.01 and st["distinct_colours"] > 3, "detail": st},
                   {"name": f"{vp}: no horizontal overflow", "ok": r["layout"]["scroll_width"] <= r["layout"]["inner_width"] + 1, "detail": [r["layout"]["scroll_width"], r["layout"]["inner_width"]]}]
        if p["expect_canvas"]: checks.append({"name": f"{vp}: has a sized canvas", "ok": any(w > 0 and h > 0 for w, h in r["layout"]["canvases"]), "detail": r["layout"]["canvases"]})
        if r["blocked"]: ctx.note(f"{vp}: blocked external requests (no network in tests): {r['blocked'][:3]}")
        outs += [{"path": s, "role": f"screenshot:{vp}", "format": "png"} for s in r["screenshots"]]
        sections.append({"title": f"viewport {vp} {r['size']}", "data": {k: r[k] for k in ("load_ms", "layout", "requests", "blocked", "console_errors", "page_errors")}, "images": r["screenshots"]})
    jp = ctx.path(f"{p.get('name') or 'smoke'}_report.json"); json.dump({"results": res, "checks": checks}, open(jp, "w"), indent=1, default=str)
    outs += [{"path": jp, "role": "report", "format": "json"}, {"path": _report(ctx, f"Smoke test: {os.path.basename(p['target'].rstrip('/'))}", sections, checks), "role": "report", "format": "html"}]
    return {"outputs": outs, "checks": checks, "results": res}


def play(ctx, p):
    res = _browser(ctx, p, steps=p["steps"], record=p["record_video"]); checks, outs, sections = [], [], []
    for r in res:
        vp = r["viewport"]
        checks.append({"name": f"{vp}: no page errors during play", "ok": not r["page_errors"], "detail": r["page_errors"][:3]})
        checks += [{"name": f"{vp}: {a['name']}", "ok": a["ok"], "detail": a.get("value", a.get("error"))} for a in r["asserts"]]
        if len(r["screenshots"]) >= 2 and p["min_change"] > 0:   # 0 = an app's feature check: its own expect/assert steps are the evidence
            from PIL import Image
            a = np.asarray(Image.open(r["screenshots"][0]).convert("L"), float); b = np.asarray(Image.open(r["screenshots"][-1]).convert("L"), float)
            changed = float((np.abs(a - b) > 8).mean()) if a.shape == b.shape else 1.0
            checks.append({"name": f"{vp}: the screen changed while playing (game responds)", "ok": changed > p["min_change"], "detail": round(changed, 4)})
        outs += [{"path": s, "role": f"screenshot:{vp}", "format": "png"} for s in r["screenshots"]]
        if r.get("video"):
            mp4 = os.path.splitext(r["video"])[0] + ".mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", r["video"], "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", mp4], timeout=300)
            outs += [{"path": r["video"], "role": "capture", "format": "webm"}] + ([{"path": mp4, "role": "capture", "format": "mp4"}] if os.path.exists(mp4) else [])
            ctx.used("ffmpeg")
        sections.append({"title": f"play on {vp}", "data": {"steps": r["steps"], "values": r["values"]}, "images": r["screenshots"]})
    jp = ctx.path(f"{p.get('name') or 'play'}_report.json"); json.dump({"results": res, "checks": checks}, open(jp, "w"), indent=1, default=str)
    outs += [{"path": jp, "role": "report", "format": "json"}, {"path": _report(ctx, "Gameplay test", sections, checks), "role": "report", "format": "html"}]
    return {"outputs": outs, "checks": checks, "values": {r["viewport"]: r["values"] for r in res}}


def perf(ctx, p):
    res = _browser(ctx, p, steps=p.get("steps"), perf_ms=int(p["seconds"] * 1000)); checks, outs, sections = [], [], []
    for r in res:
        pf = r.get("perf") or {}; vp = r["viewport"]
        checks += [{"name": f"{vp}: average FPS ≥ {p['min_fps']}", "ok": (pf.get("fps") or 0) >= p["min_fps"], "detail": pf.get("fps")},
                   {"name": f"{vp}: p95 frame time ≤ {p['max_p95_ms']} ms", "ok": (pf.get("frame_ms_p95") or 1e9) <= p["max_p95_ms"], "detail": pf.get("frame_ms_p95")},
                   {"name": f"{vp}: no page errors", "ok": not r["page_errors"], "detail": r["page_errors"][:2]}]
        if p.get("max_heap_mb") and pf.get("heap"): checks.append({"name": f"{vp}: JS heap ≤ {p['max_heap_mb']} MB", "ok": pf["heap"]["used_mb"] <= p["max_heap_mb"], "detail": pf["heap"]})
        outs += [{"path": s, "role": f"screenshot:{vp}", "format": "png"} for s in r["screenshots"]]
        sections.append({"title": f"performance on {vp} ({p['seconds']} s)", "data": pf, "images": r["screenshots"][-1:]})
    ctx.note("Headless Chromium renders WebGL in software (SwiftShader): absolute FPS is lower than on a real GPU; compare runs on the same machine.")
    jp = ctx.path(f"{p.get('name') or 'perf'}_report.json"); json.dump({"results": res, "checks": checks}, open(jp, "w"), indent=1, default=str)
    outs += [{"path": jp, "role": "report", "format": "json"}, {"path": _report(ctx, "Performance profile", sections, checks), "role": "report", "format": "html"}]
    return {"outputs": outs, "checks": checks, "perf": {r["viewport"]: r.get("perf") for r in res}}


def diff_images(a_path, b_path, out_path, threshold=0.1):
    """Per-pixel YIQ colour distance (pixelmatch's perceptual metric, normalised so 1 = the largest
    possible difference); writes a diff image with differing pixels in red."""
    from PIL import Image
    A = np.asarray(Image.open(a_path).convert("RGB"), float) / 255; B = np.asarray(Image.open(b_path).convert("RGB"), float) / 255
    if A.shape != B.shape: return {"same_size": False, "a": list(A.shape), "b": list(B.shape), "mismatch": 1.0}
    yiq = lambda X: np.stack([X @ [0.299, 0.587, 0.114], X @ [0.596, -0.274, -0.322], X @ [0.211, -0.523, 0.312]], -1)
    d = yiq(A) - yiq(B); dist = np.sqrt(0.5053 * d[..., 0] ** 2 + 0.299 * d[..., 1] ** 2 + 0.1957 * d[..., 2] ** 2) / 0.35
    bad = dist > threshold
    out = (np.stack([A.mean(-1)] * 3, -1) * 0.3 + 0.7)
    out[bad] = [1.0, 0.1, 0.3]; media.to_image(out).save(out_path)
    return {"same_size": True, "mismatch": round(float(bad.mean()), 6), "pixels": int(bad.sum())}


def visual_diff(ctx, p):
    ctx.used("studio_testcraft"); outs, checks, comps = [], [], []
    if p.get("baseline") and p.get("current"):
        pairs = [(ctx.need(p["baseline"]), ctx.need(p["current"]))]
    else:   # snapshot mode: screenshot the target now and compare against (or create) the baseline folder
        if not p.get("target"): raise StudioError("give baseline + current images, or target + baseline_dir")
        res = _browser(ctx, p); base = os.path.abspath(p.get("baseline_dir") or os.path.join(ctx.out_dir, "baseline")); os.makedirs(base, exist_ok=True)
        pairs = []
        for r in res:
            cur = r["screenshots"][0]; b = os.path.join(base, os.path.basename(cur))
            if not os.path.exists(b) or p["update_baseline"]:
                import shutil; shutil.copy(cur, b); ctx.note(f"baseline {'updated' if p['update_baseline'] else 'created'}: {b}")
            pairs.append((b, cur))
    for b, c in pairs:
        dp = ctx.path(f"diff_{os.path.basename(c)}"); r = diff_images(b, c, dp, p["threshold"]); comps.append(dict(r, baseline=b, current=c, diff=dp))
        outs.append({"path": dp, "role": "diff", "format": "png"})
        checks.append({"name": f"{os.path.basename(c)} matches baseline (≤ {p['max_mismatch'] * 100:.2f}% pixels differ)", "ok": r["same_size"] and r["mismatch"] <= p["max_mismatch"], "detail": r})
    sections = [{"title": os.path.basename(x["current"]), "data": x, "images": [x["baseline"], x["current"], x["diff"]]} for x in comps]
    outs.append({"path": _report(ctx, "Visual regression", sections, checks), "role": "report", "format": "html"})
    return {"outputs": outs, "checks": checks, "comparisons": comps}


def assets(ctx, p):
    """Open every asset in a folder the way its consumer would; GLBs also go through the Khronos validator."""
    root = ctx.need(p["folder"]); ctx.used("studio_testcraft"); rows = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in ("node_modules", ".git")]
        for f in sorted(files):
            pth = os.path.join(d, f); fmt = V.sniff(pth)
            if fmt in ("binary", "text") or f.endswith(".studio.json"): continue
            r = V.check(pth); row = {"path": os.path.relpath(pth, root), "format": fmt, "ok": r["ok"], "error": r.get("error"), "bytes": os.path.getsize(pth)}
            if fmt == "glb" and r["ok"] and p["khronos"]:
                k = webpages.khronos(pth); row["khronos_errors"] = k.get("errors"); row["ok"] = k.get("errors") == 0; ctx.used("gltf_validator")
                if not row["ok"]: row["error"] = (k.get("messages") or [k.get("error")])[:2]
            if fmt in ("png", "jpeg", "webp") and r["ok"] and p["max_texture"]:
                big = max(r["width"], r["height"]) > p["max_texture"]; pot = all((v & (v - 1)) == 0 for v in (r["width"], r["height"]))
                row.update(width=r["width"], height=r["height"], power_of_two=pot)
                if big: row["ok"] = False; row["error"] = f"larger than {p['max_texture']} px"
            rows.append(row)
    bad = [r for r in rows if not r["ok"]]
    jp = ctx.path(f"{p.get('name') or 'assets'}_report.json"); json.dump({"assets": rows}, open(jp, "w"), indent=1)
    checks = [{"name": f"{len(rows)} assets open and validate", "ok": not bad and len(rows) > 0, "detail": bad[:10]}]
    by = {}
    for r in rows: by[r["format"]] = by.get(r["format"], 0) + 1
    outs = [{"path": jp, "role": "report", "format": "json"}, {"path": _report(ctx, f"Asset integrity: {os.path.basename(root)}", [{"title": "by format", "data": by}, {"title": "failures", "data": bad}], checks), "role": "report", "format": "html"}]
    return {"outputs": outs, "checks": checks, "by_format": by, "failures": bad}


def animation(ctx, p):
    """Every clip in a GLB really moves in three.js (frame at t=0 vs mid-clip), or a sprite atlas's frames differ."""
    src = ctx.need(p["input"]); checks, outs = [], []
    if src.lower().endswith(".glb"):
        ctx.used("three")
        info = V.check(src); clips = info.get("animations") or []
        if not clips: raise StudioError("the GLB has no animation clips")
        from PIL import Image
        for i, clip in enumerate(clips):
            a = ctx.path(f"clip{i}_t0.png"); b = ctx.path(f"clip{i}_mid.png")
            js_only = f"if (mixer) {{ mixer.stopAllAction(); const act = mixer.clipAction(gltf.animations[{i}]); act.reset().play(); mixer.update(0.0001); }}"
            r0 = webpages.glb_view(src, a, size=(480, 480), play=0.0001, extra_js=js_only)
            dur = next((c[1] for c in (r0.get("report") or {}).get("clips", []) if c[0] == clip), 1.0)
            js_mid = f"if (mixer) {{ mixer.stopAllAction(); const act = mixer.clipAction(gltf.animations[{i}]); act.reset().play(); mixer.update({dur / 2}); }}"
            webpages.glb_view(src, b, size=(480, 480), play=0.0001, extra_js=js_mid)
            A = np.asarray(Image.open(a).convert("L"), float); B = np.asarray(Image.open(b).convert("L"), float)
            moved = float((np.abs(A - B) > 6).mean())
            checks.append({"name": f"clip '{clip}' plays (pixels change mid-clip)", "ok": moved > 0.001, "detail": {"changed": round(moved, 4), "seconds": dur}})
            outs += [{"path": a, "role": "frame", "format": "png"}, {"path": b, "role": "frame", "format": "png"}]
    else:   # sprite atlas JSON (TexturePacker hash) + image
        meta = json.load(open(src)); img = os.path.join(os.path.dirname(src), meta["meta"]["image"])
        from PIL import Image
        im = np.asarray(Image.open(img).convert("RGBA"), float); frames = []
        for k, f in meta["frames"].items():
            r = f["frame"]; frames.append(im[r["y"]:r["y"] + r["h"], r["x"]:r["x"] + r["w"]])
        diffs = [float(np.abs(frames[i] - frames[i + 1]).mean()) for i in range(len(frames) - 1)]
        empty = [i for i, f in enumerate(frames) if f[..., 3].max() == 0]
        checks += [{"name": "no empty frames", "ok": not empty, "detail": empty[:5]}, {"name": "consecutive frames differ (it animates)", "ok": bool(diffs) and min(diffs) > 0.05, "detail": round(min(diffs), 3) if diffs else None}]
        sheet = ctx.path("frames.png"); media.contact_sheet([media.to_image(f / 255) for f in frames[:16]], sheet, cols=8, cell=96); outs.append({"path": sheet, "role": "preview", "format": "png"})
    jp = ctx.path("animation_report.json"); json.dump({"checks": checks}, open(jp, "w"), indent=1); outs.append({"path": jp, "role": "report", "format": "json"})
    return {"outputs": outs, "checks": checks}


def unit(ctx, p):
    """Run the project's own Vitest (or Jest) suite with JSON output, if the project has one installed."""
    proj = ctx.need(p["project"]); ctx.used("vitest")
    vt = os.path.join(proj, "node_modules", ".bin", "vitest"); jest = os.path.join(proj, "node_modules", ".bin", "jest")
    if os.path.exists(vt): cmd = [vt, "run", "--reporter=json", f"--outputFile={ctx.path('vitest.json')}"]; out = ctx.path("vitest.json")
    elif os.path.exists(jest): cmd = [jest, "--json", f"--outputFile={ctx.path('jest.json')}"]; out = ctx.path("jest.json")
    else: raise StudioError("the project has no Vitest or Jest installed (node_modules/.bin)", hint="npm i -D vitest in the project, then rerun; TestCraft never installs into a project")
    r = subprocess.run(cmd, cwd=proj, capture_output=True, text=True, timeout=p["timeout"])
    d = json.load(open(out)) if os.path.exists(out) else {}
    passed, failed = d.get("numPassedTests", 0), d.get("numFailedTests", 0)
    return {"outputs": [{"path": out, "role": "report", "format": "json"}] if os.path.exists(out) else [],
            "checks": [{"name": "unit tests pass", "ok": r.returncode == 0 and failed == 0, "detail": {"passed": passed, "failed": failed, "exit": r.returncode, "tail": r.stdout[-300:] + r.stderr[-300:]}}]}


def report(ctx, p):
    """Collect every department record (.studio.json) under a folder into one HTML QA report."""
    root = ctx.need(p["folder"]); recs = []
    for d, dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".studio.json"):
                try: recs.append(json.load(open(os.path.join(d, f))))
                except Exception: pass
    checks = [{"name": f"{r['department']}.{r['action']} — {c['name']}", "ok": c["ok"], "detail": c.get("detail")} for r in recs for c in r.get("checks", [])]
    checks += [{"name": f"{r['department']}.{r['action']} status", "ok": r.get("status") == "ok", "detail": r.get("error")} for r in recs]
    sections = [{"title": f"{r['department']} · {r['action']} · {os.path.relpath(r['out_dir'], root)}", "data": {"seconds": r.get("seconds"), "outputs": [o["path"] for o in r.get("outputs", [])][:20]},
                 "images": [os.path.join(r["out_dir"], o["path"]) for o in r.get("outputs", []) if o.get("format") == "png" and ("preview" in (o.get("role") or "") or "screenshot" in (o.get("role") or "") or "render" in (o.get("role") or ""))][:4]} for r in recs]
    return {"outputs": [{"path": _report(ctx, f"GITCRAFT Studio QA: {os.path.basename(root)}", sections, checks), "role": "report", "format": "html"}],
            "checks": [{"name": f"{len(recs)} runs collected", "ok": len(recs) > 0}], "summary": {"runs": len(recs), "checks": len(checks), "failed": sum(not c["ok"] for c in checks)}}


ACTIONS = {"smoke": smoke, "play": play, "perf": perf, "visual_diff": visual_diff, "assets": assets, "animation": animation, "unit": unit, "report": report}
