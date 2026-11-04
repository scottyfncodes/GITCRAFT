"""PLAYCRAFT reports: Markdown (for PRs and chat) and a self-contained HTML page (screenshots inlined)."""
import base64, html, io, json, os

LEVEL_BADGE = {"verified": "#1f7a4d", "observed": "#2f6db3", "inferred": "#8a6d1f", "not_tested": "#7a7f87"}
STATUS_MARK = {"pass": "✅", "partial": "🟡", "fail": "❌", "unknown": "⬜"}


def _thumb(p, size=360):
    from PIL import Image
    im = Image.open(p).convert("RGB"); im.thumbnail((size, size)); b = io.BytesIO(); im.save(b, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def bar(s):
    if s is None: return "—"
    n = int(round(s / 10)); return "█" * n + "░" * (10 - n)


def markdown(card, plan=None, compare=None):
    g = card["genre"]; o = card["overall"]
    L = [f"# PLAYCRAFT assessment: {card['game']['title'] or card['game']['name']}", ""]
    if card["game"].get("pitch"): L += [f"> {card['game']['pitch']}", ""]
    L += [f"**Genres:** {', '.join(x['title'] + (f' ({int(x['share'] * 100)}%)' if x.get('share') else '') for x in g['genres'])}" + ("  · hybrid" if g["hybrid"] else ""),
          f"**Engine:** {', '.join(card['game']['engine']['engines'] + card['game']['engine']['physics'])}  ·  **Mobile:** {'yes' if card['game']['mobile']['intended'] else 'no'}  ·  "
          f"**Played:** {'yes, ' + ', '.join(card['played']['viewports']) if card['played']['played'] else 'no (source and docs only)'}", "",
          f"## Overall: {o['score'] if o['score'] is not None else 'n/a'}/100 · confidence {o['confidence']} · coverage {int(o['coverage'] * 100)}% · strong evidence {int(o['strong_evidence_share'] * 100)}%", ""]
    if o.get("note"): L += [f"_{o['note']}_", ""]
    L += ["| Category | Score | Confidence | Evidence (verified/observed/inferred/not tested) |", "|---|---|---|---|"]
    for k, c in card["categories"].items():
        lv = c.get("levels") or {}
        sc = "n/a" if not c.get("applicable") else ("not tested" if c["score"] is None else f"{c['score']} `{bar(c['score'])}`" + (" (capped: inferred only)" if c.get("capped_inferred_only") else ""))
        L.append(f"| {c['title']} | {sc} | {c.get('confidence') or '—'} | {lv.get('verified', 0)}/{lv.get('observed', 0)}/{lv.get('inferred', 0)}/{lv.get('not_tested', 0)} |")
    L += ["", "Evidence levels: **verified** = measured on the running game by an automated check; **observed** = seen in the running game (approximate, or recorded by the player); "
          "**inferred** = from source/docs only; **not tested** = no evidence, not scored.", ""]
    if card.get("genre_focus"):
        L += ["## What matters for this game", ""] + [f"- **{x['title']}**: " + "; ".join(x["priorities"]) for x in card["genre_focus"]] + [""]
    F = card["findings"]
    L += [f"## Highest-impact opportunities ({len(F)} total)", ""]
    for f in F[:12]:
        L += [f"{f['rank']}. **{f['title']}** — {f['type']}, {f['category'].replace('_', ' ')}, {f['level']} · impact {f['impact']}/5 · effort {f['effort']}/5 · risk {f['risk']}/3",
              f"   - Evidence: {_short(f['evidence'])}" + (f" ({'; '.join(f['where'][:2])})" if f.get("where") else ""),
              f"   - Do: {f['recommendation']}"]
    L.append("")
    if plan:
        L += ["## Implementation plan", ""]
        for stage in plan["stages"]:
            L += [f"**{stage['name']}** — {stage['why']}", ""] + [f"- [{i['owner']}] {i['title']} → {i['recommendation']}" for i in stage["items"]] + [""]
    L += ["## Disciplines", ""]
    for d in card["disciplines"]:
        L += [f"### {d['title']}", ""]
        if d.get("answers"): L += [f"- **{k.replace('_', ' ')}:** {v}" for k, v in d["answers"].items()]
        L += [f"- {STATUS_MARK.get(r['status'], '?')} {r['title']} — _{r['level']}_: {_short(r['detail'])}" for r in d["results"]]
        if d.get("questions"): L += ["", "Questions to answer by playing:"] + [f"- {q}" for q in d["questions"]]
        L.append("")
    if compare:
        L += before_after_md(compare)
    L += ["", f"_GITCRAFT PLAYCRAFT {card.get('version', '')} · {card['created']}_"]
    return "\n".join(L) + "\n"


def before_after_md(cmp):
    L = ["## Before and after", "", "| Category | Before | After | Change |", "|---|---|---|---|"]
    for k, v in cmp["categories"].items():
        if v["before"] is None and v["after"] is None: continue
        d = v.get("delta"); L.append(f"| {v['title']} | {v['before'] if v['before'] is not None else '—'} | {v['after'] if v['after'] is not None else '—'} | {('+' if d and d > 0 else '') + str(d) if d is not None else '—'} |")
    o = cmp["overall"]; L += [f"| **Overall** | **{o['before']}** | **{o['after']}** | **{('+' if (o.get('delta') or 0) > 0 else '') + str(o.get('delta'))}** |", ""]
    if cmp.get("metrics"):
        L += ["Measured on the running game (same probe, same machine):", ""] + [f"- {m['name']}: {m['before']} → {m['after']}" for m in cmp["metrics"]] + [""]
    if cmp.get("resolved"): L += ["**Fixed since the baseline:**", ""] + [f"- {x}" for x in cmp["resolved"]] + [""]
    if cmp.get("new_findings"): L += ["**New issues:**", ""] + [f"- {x}" for x in cmp["new_findings"]] + [""]
    if cmp.get("confirmation_run"):
        cr = cmp["confirmation_run"]
        L += [f"A confirmation run replayed the build: {len(cr['reproduced'])} of {len(cr['first_run_regressions'])} first-run regressions reproduced"
              + (f"; not reproduced (run-to-run noise): {'; '.join(cr['not_reproduced'])}" if cr["not_reproduced"] else "") + ".", ""]
    if cmp.get("regressions"): L += ["**Regressions:**", ""] + [f"- ❌ {x}" for x in cmp["regressions"]] + [""]
    else: L += ["No regressions detected by the probe.", ""]
    if cmp.get("changes"):
        L += ["**What changed and why:**", ""] + [f"- **{c.get('title')}** — {c.get('why', '')}" + (f" (`{'`, `'.join(os.path.basename(f) if os.path.isabs(f) else f for f in c.get('files', []))}`)" if c.get("files") else "") for c in cmp["changes"]] + [""]
    if cmp.get("guardrails"):
        L += ["**Guardrails on the diff:**", ""] + [f"- {'✅' if g['ok'] else '❌'} {g['name']}: {_short(g.get('detail'))}" for g in cmp["guardrails"]] + [""]
    if cmp.get("remaining"): L += ["**Still open (top):**", ""] + [f"- {x}" for x in cmp["remaining"][:8]] + [""]
    return L


def _short(x, n=240):
    s = x if isinstance(x, str) else json.dumps(x, default=str)
    return s if len(s) <= n else s[:n] + "…"


def html_page(card, md_text, images=(), title=None):
    o = card["overall"]
    rows = ""
    for k, c in card["categories"].items():
        if not c.get("applicable"): continue
        s = c.get("score"); w = 0 if s is None else s
        col = "#1f7a4d" if w >= 75 else "#b7791f" if w >= 55 else "#c0392b"
        rows += (f"<tr><td>{html.escape(c['title'])}</td><td class=n>{'—' if s is None else s}</td><td><div class=bar><i style='width:{w}%;background:{col}'></i></div></td>"
                 f"<td>{html.escape(str(c.get('confidence')))}</td></tr>")
    items = ""
    for r in card["results"]:
        items += (f"<tr><td>{STATUS_MARK.get(r['status'], '?')}</td><td>{html.escape(r['title'])}<div class=s>{html.escape(r['category'].replace('_', ' '))}"
                  f"{(' · ' + html.escape(r['genre'])) if r.get('genre') else ''}</div></td><td><span class=lv style='background:{LEVEL_BADGE.get(r['level'], '#777')}'>{r['level']}</span></td>"
                  f"<td class=d>{html.escape(_short(r.get('detail'), 300))}</td></tr>")
    fnd = "".join(f"<li><b>{html.escape(f['title'])}</b> <span class=s>{f['type']} · {f['level']} · impact {f['impact']} · effort {f['effort']}</span><br>{html.escape(f['recommendation'])}</li>" for f in card["findings"][:15])
    imgs = "".join(f"<figure><img src='{_thumb(p)}'><figcaption>{html.escape(os.path.basename(p))}</figcaption></figure>" for p in images if os.path.exists(p))
    genres = ", ".join(html.escape(g["title"]) for g in card["genre"]["genres"])
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>{html.escape(title or 'PLAYCRAFT assessment')}</title>
<style>:root{{--bg:#f6f7f9;--fg:#1d2330;--card:#fff;--line:#e3e6ea;--mut:#667}}@media (prefers-color-scheme:dark){{:root{{--bg:#14171c;--fg:#e6e8ec;--card:#1d2128;--line:#2c313a;--mut:#9aa}}}}
body{{font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;background:var(--bg);color:var(--fg)}}main{{max-width:980px;margin:auto}}h1{{font-size:22px;margin:4px 0}}
.big{{font-size:44px;font-weight:700}}section{{background:var(--card);border-radius:10px;padding:14px;margin:14px 0;overflow-x:auto}}table{{border-collapse:collapse;width:100%}}
td{{border-bottom:1px solid var(--line);padding:6px;vertical-align:top}}.n{{text-align:right;font-weight:700;width:3em}}.bar{{background:var(--line);height:10px;border-radius:5px;min-width:80px}}
.bar i{{display:block;height:10px;border-radius:5px}}.lv{{color:#fff;border-radius:4px;padding:1px 6px;font-size:12px;white-space:nowrap}}.s{{color:var(--mut);font-size:12px}}.d{{font-size:13px;word-break:break-word}}
.g{{display:flex;flex-wrap:wrap;gap:8px}}figure{{margin:0;max-width:100%}}img{{max-width:100%;border-radius:6px}}figcaption{{font-size:12px;color:var(--mut)}}li{{margin:8px 0}}
pre{{white-space:pre-wrap;font-size:13px}}</style></head><body><main>
<h1>{html.escape(title or 'PLAYCRAFT assessment')}</h1><div class=s>{genres} · {html.escape(', '.join(card['game']['engine']['engines']))} · {'played: ' + ', '.join(card['played']['viewports']) if card['played']['played'] else 'not played (source only)'}</div>
<section><div class=big>{o['score'] if o['score'] is not None else 'n/a'}<span style="font-size:18px">/100</span></div><div class=s>confidence {o['confidence']} · coverage {int(o['coverage'] * 100)}% · strong evidence {int(o['strong_evidence_share'] * 100)}%</div>
<table>{rows}</table></section>
<section><h2>Highest-impact opportunities</h2><ol>{fnd}</ol></section>
{f'<section><h2>Screens</h2><div class=g>{imgs}</div></section>' if imgs else ''}
<section><h2>Every criterion and its evidence</h2><table>{items}</table></section>
<section><h2>Full report</h2><pre>{html.escape(md_text)}</pre></section>
<p class=s>GITCRAFT PLAYCRAFT · Playwright + Chromium probe · evidence levels: verified (automated, on the running game), observed (seen running), inferred (source/docs), not tested</p></main></body></html>"""
    return page
