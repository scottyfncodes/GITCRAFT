"""PIXELCRAFT reports: annotated evidence crops, a contact sheet, report.md and a self-contained report.html
(relative image links, no scripts from the network) with the ten sections of the audit."""
import html, json, os
from PIL import Image, ImageDraw

AREA_GROUPS = {"spacing_layout": ("spacing", "layout", "typography"), "controls": ("controls",), "mobile": ("mobile",)}
EVIDENCE_LABEL = {"measured": "Measured (rendered DOM)", "accessibility": "Accessibility (axe-core)", "screenshot": "Screenshot-based visual judgement", "source": "Source-code-only observation"}


def _shot_for(caps_idx, occ):
    c = caps_idx.get((occ.get("screen"), occ.get("viewport")))
    if not c: return None, 1.0
    use_view = occ.get("fixed") or (occ.get("rect") and occ["rect"][1] + occ["rect"][3] <= c["dom"]["vh"])
    p = c.get("shot") if use_view else c.get("full")
    if occ.get("shot"): p = occ["shot"]
    if not p or not os.path.exists(p): return None, 1.0
    w = Image.open(p).size[0]
    page_w = c["dom"]["vw"] if use_view else max(c["dom"].get("sw") or c["dom"]["vw"], c["dom"]["vw"])
    return p, w / max(1, page_w)


def annotate(findings, caps, out_dir, per_finding=2):
    """Crop around each occurrence (first two per finding) and draw the measured box."""
    idx = {(c["screen"], c["viewport"]): c for c in caps if c.get("dom")}
    d = os.path.join(out_dir, "evidence"); os.makedirs(d, exist_ok=True)
    made = []
    for f in findings:
        for k, occ in enumerate(f["occurrences"][:per_finding]):
            p, s = _shot_for(idx, occ)
            if not p: continue
            im = Image.open(p).convert("RGB"); W, H = im.size
            r = occ.get("rect")
            if r:
                x0, y0, x1, y1 = r[0] * s, r[1] * s, (r[0] + r[2]) * s, (r[1] + r[3]) * s
                pad = 60 * s
                box = (max(0, int(x0 - pad * 2)), max(0, int(y0 - pad)), min(W, int(x1 + pad * 2)), min(H, int(y1 + pad)))
                if box[2] - box[0] < 320 * s: cx = (x0 + x1) / 2; box = (max(0, int(cx - 160 * s)), box[1], min(W, int(cx + 160 * s)), box[3])
                if box[2] > box[0] and box[3] > box[1]:
                    dr = ImageDraw.Draw(im)
                    for t in range(max(2, int(2 * s))): dr.rectangle([x0 - 3 - t, y0 - 3 - t, x1 + 3 + t, y1 + 3 + t], outline=(230, 30, 60))
                    im = im.crop(box)
                else:   # the element lies outside this screenshot (below a viewport shot, or zero-size): show the screen, never fail the audit
                    im = im.crop((0, 0, W, min(H, int(W * 1.6)))); occ["evidence_note"] = "the element is outside this screenshot"
            else:
                im = im.crop((0, 0, W, min(H, int(W * 1.6))))
            if im.size[0] > 720: im = im.resize((720, int(im.size[1] * 720 / im.size[0])))
            name = f"{f['id'].replace('.', '_')}_{k}.jpg"; out = os.path.join(d, name); im.save(out, quality=84, optimize=True)
            occ["evidence"] = os.path.join("evidence", name); made.append(out)
    return made


def contact_sheet(caps, out, cols=None):
    shots = [(c["screen"], c["viewport"], c["shot"]) for c in caps if c.get("shot") and os.path.exists(c["shot"])]
    if not shots: return None
    vps = sorted({v for _, v, _ in shots}, key=lambda v: [s[1] for s in shots].index(v)); scr = []
    for s, _, _ in shots:
        if s not in scr: scr.append(s)
    th = 300; cells = {}
    for s, v, p in shots:
        im = Image.open(p).convert("RGB"); im.thumbnail((int(th * 1.6), th)); cells[(s, v)] = im
    cw = {v: max([cells[k].size[0] for k in cells if k[1] == v] or [10]) for v in vps}
    W = sum(cw.values()) + 12 * (len(vps) + 1) + 140; H = (th + 12) * len(scr) + 40
    sheet = Image.new("RGB", (W, H), (245, 246, 250)); dr = ImageDraw.Draw(sheet)
    x = 152
    for v in vps: dr.text((x, 12), v, fill=(30, 30, 40)); x += cw[v] + 12
    for i, s in enumerate(scr):
        y = 34 + i * (th + 12); dr.text((10, y + 4), s[:20], fill=(30, 30, 40)); x = 152
        for v in vps:
            if (s, v) in cells: sheet.paste(cells[(s, v)], (x, y))
            x += cw[v] + 12
    sheet.save(out, optimize=True); return out


def thumbnails(caps, out_dir, width=360):
    d = os.path.join(out_dir, "gallery"); os.makedirs(d, exist_ok=True); out = []
    for c in caps:
        if not c.get("shot") or not os.path.exists(c["shot"]): continue
        im = Image.open(c["shot"]).convert("RGB"); im.thumbnail((width, width * 2.4))
        p = os.path.join(d, os.path.basename(c["shot"]).replace(".png", ".jpg")); im.save(p, quality=82, optimize=True)
        c["thumb"] = os.path.join("gallery", os.path.basename(p)); out.append(p)
    return out


# ------------------------------------------------------------------ markdown
def _fmt(v): return "—" if v is None else f"{v:g}"


def markdown(A):
    o, cats = A["overall"], A["categories"]
    L = [f"# PIXELCRAFT audit: {A['app']['name']}", "", f"Target: `{A['app']['target']}` · method {A['method']} · {A['created']}" + (f" · commit `{A['app']['git']['head'][:10]}`" if (A['app'].get('git') or {}).get('head') else ""), "",
         f"## 1. Overall PIXELCRAFT score: **{_fmt(o['score'])}** / 100 ({o['grade']})", "",
         f"Evidence coverage {round(o['coverage'] * 100)}% · confidence **{o['confidence']}** — " + "; ".join(o["confidence_reasons"]), "",
         "Coverage and confidence are reported separately from quality: an area with no evidence is *not tested*, never zero and never capped.", "",
         "## 2. Category scores", "", "| Category | Score | Coverage | Not tested |", "|---|---|---|---|"]
    for c in cats.values(): L.append(f"| {c['title']} | **{_fmt(c['score'])}** | {round(c['coverage'] * 100)}% | {', '.join(c['untested']) or '—'} |")
    for c in cats.values():
        L += ["", f"### {c['title']}", "", "| Area | Points | Awarded | Evidence | Weakest metric |", "|---|---|---|---|---|"]
        for a in c["areas"].values():
            wk = (a.get("detail") or [{}])[0]
            L.append(f"| {a['title']} | {a['points']} | {_fmt(a['awarded']) if a['score'] is not None else 'not tested'} | {', '.join(f'{k} ×{v}' for k, v in a['evidence'].items()) or '—'} | "
                     + (f"{wk.get('title')} ({round(100 * wk['value'])}%)" if wk else "—") + " |")
    ss = A["screens_ranked"]
    k = min(3, max(1, len(ss) // 2))
    L += ["", "## 3. Strongest screens", ""] + [f"- **{s['screen']}** — {s['score']}" for s in ss[:k]]
    L += ["", "## 4. Weakest screens", ""] + ([f"- **{s['screen']}** — {s['score']}" for s in list(reversed(ss[k:]))[:3]] if len(ss) > 1 else ["Only one screen was audited."])
    F = A["findings"]

    def block(title, fs):
        out = ["", f"## {title}", ""]
        if not fs: return out + ["None found."]
        for f in fs:
            out += [f"### {f['title']} — {f['severity']} · {EVIDENCE_LABEL.get(f['evidence'], f['evidence'])}", "",
                    f"{f['explanation']}", "", f"**Fix:** {f['recommendation']}", "",
                    f"Seen {f['frequency']}× — screens: {', '.join(f['screens'][:6])}; viewports: {', '.join(f['viewports'])} · priority {f['priority']} ({f['tier']})", ""]
            for occ in f["occurrences"][:3]:
                out.append(f"- `{occ.get('selector') or '—'}` on {occ.get('screen')} @ {occ.get('viewport')}: " + ", ".join(f"{k}={json.dumps(v)}" for k, v in (occ.get("measured") or {}).items())[:300]
                           + (f" — ![evidence]({occ['evidence']})" if occ.get("evidence") else ""))
        return out
    crit = [f for f in F if f["category"] == "usability" and f["severity"] in ("critical", "major")]
    L += block("5. Critical usability defects", crit)
    L += block("6. Spacing and layout defects", [f for f in F if f["area"] in AREA_GROUPS["spacing_layout"]])
    L += block("7. Button and control defects", [f for f in F if f["area"] in AREA_GROUPS["controls"] or f["id"].startswith("states.")])
    L += block("8. Mobile-specific findings", [f for f in F if f["area"] == "mobile" or (f["viewports"] and all(v in A["mobile_viewports"] for v in f["viewports"]) and f["area"] not in ("accessibility",))])
    L += ["", "## 9. Screenshot gallery", "", "Browser emulation (Playwright + Chromium); safe-area insets emulated through CDP. " + ("Physical-device evidence: " + ", ".join(d["label"] for d in A.get("physical", [])) if A.get("physical") else "No physical-device evidence."), ""]
    L += [f"- {c['screen']} @ {c['viewport']}: ![{c['screen']}]({c['thumb']})" for c in A["gallery"]]
    L += ["", "## 10. Prioritised improvement plan", "", "| # | Tier | Fix | Severity | Seen | Cost | Area |", "|---|---|---|---|---|---|---|"]
    for i, f in enumerate([f for f in F if f["severity"] != "cosmetic"][:15], 1):
        L.append(f"| {i} | {f['tier']} | **{f['title']}** — {f['recommendation']} | {f['severity']} | {f['frequency']}× | {'low' if f['cost'] == 1 else 'medium' if f['cost'] == 2 else 'high'} | {f['area']} |")
    rest = [f for f in F if f["severity"] == "cosmetic"] + [f for f in F if f["severity"] != "cosmetic"][15:]
    if rest: L += ["", f"Lower-priority items not listed: {len(rest)} (in audit.json)."]
    L += ["", "## Journeys", "", "| Journey | Viewport | Result | Taps | Expected | Confirmations | Feedback (ms) |", "|---|---|---|---|---|---|---|"]
    for j in A["journeys"]:
        L.append(f"| {j['name']}{' (auto)' if j.get('auto') else ''} | {j['viewport']} | {'ok' if j['ok'] else 'FAILED'} | {j['taps']} | {j.get('expected_taps') or '—'} | {j['confirmations']} | "
                 + ", ".join(str(s.get('feedback_ms')) for s in j['steps'] if s.get('tap')) + " |")
    L += _tells_md(A)
    L += ["", "## Evidence and limits", ""] + [f"- {x}" for x in A["limits"]]
    if A.get("comparison"): L += ["", comparison_md(A["comparison"])]
    return "\n".join(L) + "\n"


def _tells_md(A):
    import importlib.util as u
    spec = u.spec_from_file_location("pixelcraft_tells_r", os.path.join(os.path.dirname(os.path.abspath(__file__)), "tells.py")); m = u.module_from_spec(spec); spec.loader.exec_module(m)
    L = m.markdown(A.get("tells"))
    t = (A.get("comparison") or {}).get("tells")
    if t: L += ["", f"Tells since the baseline (informational): resolved {', '.join(t['resolved']) or 'none'} · persisting {', '.join(t['persisting']) or 'none'} · new {', '.join(t['new']) or 'none'}."]
    return L


def comparison_md(cmp):
    L = ["## Before / after", "", f"Comparable: **{'yes' if cmp['comparable'] else 'no'}** ({cmp['why']})", "", "| | Before | After | Δ (same metrics) |", "|---|---|---|---|"]
    for k, v in cmp["scores"].items(): L.append(f"| {v['title']} | {_fmt(v['before'])} | {_fmt(v['after'])} | {('+' if (v['delta'] or 0) > 0 else '') + _fmt(v['delta'])} |")
    L += ["", f"Resolved: {len(cmp['resolved'])} · persisting: {len(cmp['persisting'])} · new: {len(cmp['new'])} · regressions: {len(cmp['regressions'])} · coverage lost: {', '.join(cmp['coverage_lost']) or 'none'}", ""]
    for r in cmp["resolved"]: L.append(f"- ✅ resolved: {r['title']} ({r['was']}× before)")
    for r in cmp["regressions"]: L.append(f"- ❌ regression: {r}")
    for r in cmp["new"]: L.append(f"- ⚠️ new: {r['title']} ({r['severity']}, {r['count']}×)")
    L += ["", "| Screen @ viewport | Pixels changed | Diff |", "|---|---|---|"] + [f"| {d['screen']} @ {d['viewport']} | {d['changed_pct']}% | ![diff]({d['diff']}) |" for d in cmp["screens"]]
    return "\n".join(L)


# ------------------------------------------------------------------ html
CSS = """
:root{--bg:#f6f7fb;--card:#fff;--ink:#141824;--mute:#5d6475;--line:#e3e6ee;--acc:#3d4ef0;--crit:#c4172f;--maj:#d0650b;--min:#7b6a00;--ok:#18794e}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b24;--ink:#e9ecf3;--mute:#a1a8b8;--line:#2a3040;--acc:#8b96ff;--crit:#ff6b7f;--maj:#ffa657;--min:#e3c74a;--ok:#4cc38a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:26px;margin:8px 0 4px}h2{font-size:19px;margin:32px 0 12px}h3{font-size:16px;margin:0 0 6px}
.sub{color:var(--mute);font-size:13px}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:12px 0}
.scores{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.scores .card{margin:0}.ba{display:flex;flex-wrap:wrap;gap:8px 20px;align-items:baseline}.ba b{font-size:22px}.up{color:var(--ok);font-weight:700}.down{color:var(--crit);font-weight:700}.big{font-size:44px;font-weight:700;line-height:1}
.score .big{font-size:34px}.bar{height:8px;background:var(--line);border-radius:4px;overflow:hidden;margin:8px 0}.bar i{display:block;height:100%;background:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
.tbl{overflow-x:auto}.sev{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:10px;border:1px solid currentColor}
.critical{color:var(--crit)}.major{color:var(--maj)}.minor{color:var(--min)}.cosmetic{color:var(--mute)}
.f{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,320px);gap:16px}.f img{width:100%;border-radius:8px;border:1px solid var(--line)}
@media (max-width:720px){.f{grid-template-columns:1fr}}.meta{font-size:12px;color:var(--mute)}code{font-size:12px;word-break:break-all}
.gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}.gal figure{margin:0}.gal img{width:100%;border-radius:8px;border:1px solid var(--line)}
.gal figcaption{font-size:12px;color:var(--mute);margin-top:4px}.pill{font-size:12px;color:var(--mute);border:1px solid var(--line);border-radius:10px;padding:1px 8px;margin-right:4px;display:inline-block}
details summary{cursor:pointer;color:var(--acc)}
"""


def _e(s): return html.escape(str(s if s is not None else ""))


def html_report(A):
    o, cats = A["overall"], A["categories"]
    H = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>PIXELCRAFT · {_e(A['app']['name'])}</title><style>{CSS}</style></head><body><main>",
         f"<p class=sub>PIXELCRAFT visual quality audit · {_e(A['created'])} · method {_e(A['method'])}</p><h1>{_e(A['app']['name'])}</h1><p class=sub><code>{_e(A['app']['target'])}</code></p>",
         "<div class=scores>",
         f"<div class='card score'><div class=sub>1 · Overall PIXELCRAFT score</div><div class=big>{_fmt(o['score'])}</div><div class=sub>{_e(o['grade'])} · coverage {round(o['coverage'] * 100)}% · confidence <b>{_e(o['confidence'])}</b></div></div>"]
    for c in cats.values():
        H.append(f"<div class='card score'><div class=sub>{_e(c['title'])}</div><div class=big>{_fmt(c['score'])}</div><div class=bar><i style='width:{c['score'] or 0}%'></i></div><div class=sub>coverage {round(c['coverage'] * 100)}%" + (f" · not tested: {_e(', '.join(c['untested']))}" if c['untested'] else "") + "</div></div>")
    if A.get("comparison"):
        cmp = A["comparison"]; so = cmp["scores"]
        H.append("</div><div class=card><div class=sub>Before → after (verify; same screens, viewports, journeys and method)</div><div class=ba>" + "".join(
            f"<span>{_e(v['title'])} {_fmt(v['before'])} → <b>{_fmt(v['after'])}</b> <span class={'up' if (v['delta'] or 0) > 0 else 'down'}>{('+' if (v['delta'] or 0) > 0 else '') + _fmt(v['delta'])}</span></span>" for v in so.values())
            + f"</div><p class=sub>resolved {len(cmp['resolved'])} · new {len(cmp['new'])} · regressions {len(cmp['regressions'])} · coverage lost: {_e(', '.join(cmp['coverage_lost']) or 'none')} · details at the end of the report</p>")
    H.append("</div><p class=sub>Confidence: " + _e("; ".join(o["confidence_reasons"])) + ". Coverage and confidence are separate from quality; nothing is capped or awarded for code existing.</p>")
    H.append("<h2>2 · Category scores</h2><div class='card tbl'><table><tr><th>Category</th><th>Area</th><th>Points</th><th>Awarded</th><th>Weakest metric</th><th>Evidence</th></tr>")
    for c in cats.values():
        for a in c["areas"].values():
            wk = (a.get("detail") or [{}])[0]
            H.append(f"<tr><td>{_e(c['title'])}</td><td>{_e(a['title'])}</td><td>{a['points']}</td><td>{_fmt(a['awarded']) if a['score'] is not None else '<i>not tested</i>'}</td>"
                     f"<td>{_e(wk.get('title', '—'))}{(' · ' + str(round(100 * wk['value'])) + '%') if wk else ''}</td><td>{_e(', '.join(f'{k} ×{v}' for k, v in a['evidence'].items()))}</td></tr>")
    H.append("</table></div>")
    ss = A["screens_ranked"]
    thumbs = {c["screen"]: c for c in A["gallery"] if c["viewport"] == A["primary_viewport"]}
    def scr_list(lst):
        return "<div class=gal>" + "".join(f"<figure>{('<img loading=lazy src=' + chr(39) + _e(thumbs[s['screen']]['thumb']) + chr(39) + '>') if s['screen'] in thumbs else ''}<figcaption><b>{_e(s['screen'])}</b> · {s['score']}</figcaption></figure>" for s in lst) + "</div>"
    k = min(3, max(1, len(ss) // 2))
    H.append("<h2>3 · Strongest screens</h2>" + scr_list(ss[:k]) + "<h2>4 · Weakest screens</h2>" + scr_list(list(reversed(ss[k:]))[:3] if len(ss) > 1 else []))
    F = A["findings"]

    def fblock(title, fs):
        h = [f"<h2>{title}</h2>"]
        if not fs: return h + ["<p class=sub>None found.</p>"]
        for f in fs:
            ev = next((x.get("evidence") for x in f["occurrences"] if x.get("evidence")), None)
            rows = "".join(f"<li><code>{_e(x.get('selector') or '—')}</code> · {_e(x.get('screen'))} @ {_e(x.get('viewport'))} · " + _e(", ".join(f"{k}={json.dumps(v)}" for k, v in (x.get('measured') or {}).items())[:260]) + "</li>" for x in f["occurrences"][:4])
            h.append(f"<div class='card f'><div><h3>{_e(f['title'])}</h3><p><span class='sev {f['severity']}'>{f['severity']}</span> <span class=pill>{_e(EVIDENCE_LABEL.get(f['evidence'], f['evidence']))}</span>"
                     f"<span class=pill>seen {f['frequency']}×</span><span class=pill>{_e(f['tier'])}</span></p><p>{_e(f['explanation'])}</p><p><b>Fix:</b> {_e(f['recommendation'])}</p>"
                     f"<details><summary>Where and what was measured</summary><ul class=meta>{rows}</ul></details></div><div>{('<img loading=lazy alt=evidence src=' + chr(39) + _e(ev) + chr(39) + '>') if ev else ''}</div></div>")
        return h
    H += fblock("5 · Critical usability defects", [f for f in F if f["category"] == "usability" and f["severity"] in ("critical", "major")])
    H += fblock("6 · Spacing and layout defects", [f for f in F if f["area"] in AREA_GROUPS["spacing_layout"]])
    H += fblock("7 · Button and control defects", [f for f in F if f["area"] in AREA_GROUPS["controls"] or f["id"].startswith("states.")])
    H += fblock("8 · Mobile-specific findings", [f for f in F if f["area"] == "mobile"])
    H.append("<h2>9 · Screenshot gallery</h2><p class=sub>Browser emulation (Playwright + Chromium; iPhone safe areas emulated through CDP). "
             + (_e("Physical-device evidence: " + ", ".join(d["label"] for d in A["physical"])) if A.get("physical") else "No physical-device evidence was supplied.") + "</p><div class=gal>")
    for c in A["gallery"]: H.append(f"<figure><img loading=lazy src='{_e(c['thumb'])}' alt=''><figcaption>{_e(c['screen'])} · {_e(c['viewport'])}</figcaption></figure>")
    for d in A.get("physical", []): H.append(f"<figure><img loading=lazy src='{_e(d['path'])}' alt=''><figcaption>{_e(d['label'])} (physical device)</figcaption></figure>")
    H.append("</div><h2>10 · Prioritised improvement plan</h2><div class='card tbl'><table><tr><th>#</th><th>Tier</th><th>Fix</th><th>Severity</th><th>Seen</th><th>Cost</th></tr>")
    for i, f in enumerate([f for f in F if f["severity"] != "cosmetic"][:15], 1):
        H.append(f"<tr><td>{i}</td><td>{_e(f['tier'])}</td><td><b>{_e(f['title'])}</b><br><span class=sub>{_e(f['recommendation'])}</span></td><td><span class='sev {f['severity']}'>{f['severity']}</span></td><td>{f['frequency']}×</td><td>{['', 'low', 'medium', 'high'][f['cost']]}</td></tr>")
    H.append("</table></div><h2>Journeys</h2><div class='card tbl'><table><tr><th>Journey</th><th>Viewport</th><th>Result</th><th>Taps</th><th>Confirmations</th><th>Feedback ms</th></tr>")
    for j in A["journeys"]:
        H.append(f"<tr><td>{_e(j['name'])}{' <span class=pill>auto</span>' if j.get('auto') else ''}</td><td>{_e(j['viewport'])}</td><td>{'ok' if j['ok'] else '<b class=critical>failed</b>'}</td><td>{j['taps']}{(' / ' + str(j['expected_taps'])) if j.get('expected_taps') else ''}</td><td>{j['confirmations']}</td><td>{_e(', '.join(str(s.get('feedback_ms')) for s in j['steps'] if s.get('tap')))}</td></tr>")
    H.append("</table></div>")
    if A.get("comparison"):
        cmp = A["comparison"]
        H.append(f"<h2>Before / after</h2><div class='card tbl'><p>Comparable: <b>{'yes' if cmp['comparable'] else 'no'}</b> — {_e(cmp['why'])}</p><table><tr><th></th><th>Before</th><th>After</th><th>Δ (same metrics)</th></tr>")
        for v in cmp["scores"].values(): H.append(f"<tr><td>{_e(v['title'])}</td><td>{_fmt(v['before'])}</td><td>{_fmt(v['after'])}</td><td><b>{('+' if (v['delta'] or 0) > 0 else '') + _fmt(v['delta'])}</b></td></tr>")
        H.append(f"</table><p>Resolved {len(cmp['resolved'])} · persisting {len(cmp['persisting'])} · new {len(cmp['new'])} · regressions {len(cmp['regressions'])} · coverage lost: {_e(', '.join(cmp['coverage_lost']) or 'none')}</p><ul>")
        H += [f"<li>✅ {_e(r['title'])}</li>" for r in cmp["resolved"]] + [f"<li>❌ {_e(r)}</li>" for r in cmp["regressions"]] + [f"<li>⚠️ new: {_e(r['title'])}</li>" for r in cmp["new"]]
        H.append("</ul></div><div class=gal>" + "".join(f"<figure><img loading=lazy src='{_e(d['diff'])}'><figcaption>{_e(d['screen'])} · {_e(d['viewport'])} · {d['changed_pct']}% changed</figcaption></figure>" for d in cmp["screens"]) + "</div>")
    T = A.get("tells")
    if T:
        H.append("<h2>Generic design tells <span class=sub>(advisory, not scored)</span></h2><div class='card tbl'><p class=sub>Defaults unguided builds reach for, read from the rendered page. "
                 "Each is a question, not a defect: the project's own art direction wins. Accept a deliberate one with <code>accept_tells</code>.</p><ul>")
        H += [f"<li><b>{_e(r['title'])}</b> — {r['count']}× on {_e(', '.join(r['screens']))}. {_e(r['why'])} <i>Ask:</i> {_e(r['ask'])}"
              + "".join(f"<br><code>{_e(x['sel'])}</code> {_e(x.get('text'))} · {_e(x['screen'])} @ {_e(x['viewport'])}" for x in r["examples"][:3]) + "</li>" for r in T["raised"]]
        H += [f"<li>Accepted: <b>{_e(r['title'])}</b> ({r['count']}×) — {_e(r['accepted'])}</li>" for r in T["accepted"]]
        H.append(("<li>None raised.</li>" if not T["raised"] and not T["accepted"] else "") + "</ul></div>")
    H.append("<h2>Evidence and limits</h2><ul class=sub>" + "".join(f"<li>{_e(x)}</li>" for x in A["limits"]) + "</ul></main></body></html>")
    return "".join(H)
