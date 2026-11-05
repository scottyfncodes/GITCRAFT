"""PIXELCRAFT audits page (static site, standard library only: the Vercel build runs it without the Studio venv).

  publish_site(archive, dist)   archive = a folder of recorded runs (<app>/<run>/audit.json + report.html + images),
                                e.g. the committed history/pixelcraft; dist = the output folder (dist/pixelcraft)
Each run's own report.html is copied as is; the index lists every app with its latest scores, its trend across
recorded runs and before/after deltas from verify runs."""
import html, json, os, shutil

CSS = """:root{--bg:#f6f7fb;--card:#fff;--ink:#141824;--mute:#5d6475;--line:#e3e6ee;--acc:#3d4ef0;--up:#18794e;--down:#c4172f}
@media (prefers-color-scheme:dark){:root{--bg:#0f1218;--card:#171b24;--ink:#e9ecf3;--mute:#a1a8b8;--line:#2a3040;--acc:#8b96ff;--up:#4cc38a;--down:#ff6b7f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1040px;margin:0 auto;padding:16px}h1{font-size:28px;margin:12px 0 4px}h2{font-size:20px;margin:0 0 4px}.sub{color:var(--mute);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;margin:16px 0}
.app{display:grid;grid-template-columns:minmax(0,1fr) 150px;gap:16px}@media (max-width:640px){.app{grid-template-columns:1fr}.app img{max-width:180px}}
.app img{width:100%;border-radius:10px;border:1px solid var(--line)}.nums{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}
.n{background:var(--bg);border-radius:10px;padding:8px}.n b{display:block;font-size:24px;line-height:1.1}.n span{font-size:12px;color:var(--mute)}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:7px 6px;border-bottom:1px solid var(--line)}.tbl{overflow-x:auto}
a{color:var(--acc)}.up{color:var(--up);font-weight:600}.down{color:var(--down);font-weight:600}.pill{font-size:12px;border:1px solid var(--line);border-radius:10px;padding:1px 8px;color:var(--mute)}"""


def _e(s): return html.escape(str("—" if s is None else s))


def _runs(archive):
    apps = {}
    if not os.path.isdir(archive): return apps
    for app in sorted(os.listdir(archive)):
        d = os.path.join(archive, app)
        if not os.path.isdir(d): continue
        for run in sorted(os.listdir(d)):
            p = os.path.join(d, run, "audit.json")
            if not os.path.isfile(p): continue
            try: A = json.load(open(p))
            except ValueError: continue
            apps.setdefault(app, []).append((run, A))
    return apps


def publish_site(archive, dist):
    apps = _runs(archive)
    if not apps: return 0
    if os.path.isdir(dist): shutil.rmtree(dist)
    os.makedirs(dist)
    H = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>PIXELCRAFT audits</title><style>{CSS}</style></head><body><main>",
         "<p class=sub>GITCRAFT · Studio department</p><h1>PIXELCRAFT audits</h1>",
         "<p class=sub>Visual quality, usability and consistency of rendered apps, measured in Chromium at iPhone 17, iPhone 13, desktop, narrow, tablet and landscape. "
         "Every number links to its evidence; coverage and confidence are shown beside the score, never folded into it.</p>"]
    n = 0
    for app, runs in apps.items():
        for run, _ in runs:
            shutil.copytree(os.path.join(archive, app, run), os.path.join(dist, app, run), ignore=shutil.ignore_patterns("probe.json")); n += 1
        run, A = runs[-1]
        o, c = A["overall"], A["categories"]
        thumb = next((g["thumb"] for g in A.get("gallery", []) if g["viewport"] == A.get("primary_viewport")), None)
        cmp = A.get("comparison")
        delta = ""
        if cmp:
            d = cmp["scores"]["overall"]["delta"]
            delta = f" · <span class={'up' if (d or 0) > 0 else 'down'}>{'+' if (d or 0) > 0 else ''}{_e(d)} vs baseline</span> (resolved {len(cmp['resolved'])}, regressions {len(cmp['regressions'])})"
        H.append(f"<section class='card app'><div><h2>{_e(A['app']['name'])}</h2><p class=sub>{_e(A['created'][:16].replace('T', ' '))} · {_e(run.split('-')[-1])} run{delta}</p>"
                 "<div class=nums>" + f"<div class=n><b>{_e(o['score'])}</b><span>Overall</span></div>" + "".join(f"<div class=n><b>{_e(v['score'])}</b><span>{_e(v['title'])}</span></div>" for v in c.values()) + "</div>"
                 f"<p class=sub>coverage {round(o['coverage'] * 100)}% · confidence {_e(o['confidence'])} · {len(A['findings'])} findings · {len(A['screens'])} screens × {len(A['viewports'])} viewports</p>"
                 f"<p><a href='{_e(app)}/{_e(run)}/report.html'>Open the full report →</a></p>")
        if len(runs) > 1:
            H.append("<div class=tbl><table><tr><th>Run</th><th>Overall</th><th>Visual</th><th>Usability</th><th>Consistency</th><th></th></tr>")
            for r, a in runs:
                H.append(f"<tr><td>{_e(r)}</td><td>{_e(a['overall']['score'])}</td>" + "".join(f"<td>{_e(v['score'])}</td>" for v in a["categories"].values()) + f"<td><a href='{_e(app)}/{_e(r)}/report.html'>report</a></td></tr>")
            H.append("</table></div>")
        H.append(f"</div><div>{('<img alt=screenshot src=' + chr(39) + _e(app) + '/' + _e(run) + '/' + _e(thumb) + chr(39) + '>') if thumb else ''}</div></section>")
    H.append("<p class=sub>Runs are recorded by <code>pixelcraft_audit</code> / <code>pixelcraft_verify</code> and never rewritten. Source: <code>history/pixelcraft/</code> in the GITCRAFT repository.</p></main></body></html>")
    open(os.path.join(dist, "index.html"), "w").write("".join(H))
    return n
