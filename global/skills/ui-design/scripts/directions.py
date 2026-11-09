#!/usr/bin/env python3
"""Build a side-by-side comparison page for design directions (standard library only).

    python3 directions.py <folder>            writes <folder>/index.html

<folder> holds one self-contained HTML file per direction (a.html, b.html, …), all showing the same real screen.
An optional directions.json adds names, the idea behind each, type notes, palettes and the recommendation:
    {"round": 1, "recommend": "b", "candidates": [{"file": "a.html", "name": "Trail sign", "idea": "…", "type": "…", "palette": ["#…"]}]}
Every direction is shown at phone (390×844) and desktop (1440×900, scaled) size in live iframes. The page itself is
neutral so it never competes with the candidates. Nothing is written outside <folder>."""
import html, json, os, re, sys


def main(folder):
    folder = os.path.abspath(folder)
    meta = {}
    mp = os.path.join(folder, "directions.json")
    if os.path.exists(mp):
        meta = json.load(open(mp))
    files = sorted(f for f in os.listdir(folder) if f.endswith(".html") and f != "index.html")
    by_file = {c.get("file"): c for c in meta.get("candidates", [])}
    order = [c["file"] for c in meta.get("candidates", []) if c.get("file") in files] + [f for f in files if f not in by_file]
    if len(order) < 2:
        sys.exit(f"directions: need at least two candidate HTML files in {folder} (found {len(order)})")
    rec = meta.get("recommend")
    e = html.escape
    cards = []
    for i, f in enumerate(order):
        c = by_file.get(f, {})
        title = c.get("name") or _title(os.path.join(folder, f)) or f
        is_rec = rec in (f, os.path.splitext(f)[0], c.get("name"))
        sw = "".join(f"<span class=sw style='background:{e(p)}' title='{e(p)}'></span>" for p in c.get("palette", []) if re.fullmatch(r"#[0-9a-fA-F]{3,8}", str(p)))
        cards.append(f"""<section class=dir>
  <header><h2>{chr(65 + i)} · {e(title)}{' <span class=rec>recommended</span>' if is_rec else ''}</h2>
  {f'<p>{e(c["idea"])}</p>' if c.get('idea') else ''}{f'<p class=meta>Type: {e(c["type"])}</p>' if c.get('type') else ''}{f'<p class=pal>{sw}</p>' if sw else ''}</header>
  <figure class=phone><div class=clip><iframe src="{e(f)}" width=390 height=844 loading=lazy title="{e(title)} at phone size"></iframe></div><figcaption>Phone 390×844 (actual size: open <a href="{e(f)}">{e(f)}</a>)</figcaption></figure>
  <figure class=desk><div class=clip><iframe src="{e(f)}" width=1440 height=900 loading=lazy title="{e(title)} at desktop size"></iframe></div><figcaption>Desktop 1440×900, scaled</figcaption></figure>
</section>""")
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width, initial-scale=1">
<title>Design directions{f" · round {e(str(meta['round']))}" if meta.get('round') else ''}</title>
<style>
:root {{ color-scheme: light; --bg: #f2f2f0; --fg: #1d1d1b; --muted: #5d5d58; --line: #d6d6d1; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 24px 0 48px; background: var(--bg); color: var(--fg); font: 15px/1.45 ui-sans-serif, system-ui, sans-serif; }}
.top {{ padding: 0 16px; }} h1 {{ font-size: 20px; margin: 0 0 4px; }} .lede {{ color: var(--muted); margin: 0 0 20px; max-width: 70ch; }}
.strip {{ display: flex; gap: 24px; overflow-x: auto; padding: 0 16px 12px; scroll-snap-type: x mandatory; scroll-padding: 16px; }}
.dir {{ flex: 0 0 434px; min-width: 0; scroll-snap-align: start; border-top: 1px solid var(--line); padding-top: 16px; display: grid; grid-template-columns: minmax(0, 1fr); grid-template-rows: subgrid; grid-row: span 3; }}
.strip {{ display: grid; grid-auto-flow: column; grid-auto-columns: 434px; grid-template-rows: auto auto auto; }}
.clip {{ max-width: 100%; }}
.dir h2 {{ font-size: 17px; margin: 0 0 6px; }} .dir p {{ margin: 0 0 6px; }} .meta {{ color: var(--muted); }}
.rec {{ font-size: 12px; font-weight: 600; padding: 2px 8px; border: 1px solid var(--fg); margin-left: 6px; vertical-align: 2px; white-space: nowrap; }}
.sw {{ display: inline-block; width: 22px; height: 22px; margin-right: 4px; border: 1px solid rgba(0,0,0,.15); }}
figure {{ margin: 0 0 16px; }} figcaption {{ font-size: 12px; color: var(--muted); margin-top: 6px; }}
.clip {{ overflow: hidden; border: 1px solid var(--line); background: #fff; }}
.phone .clip {{ width: 294px; height: 634px; }} .phone iframe {{ transform: scale(.75); transform-origin: 0 0; border: 0; }}
.desk .clip {{ width: 434px; height: 272px; }} .desk iframe {{ transform: scale(.3); transform-origin: 0 0; border: 0; }}
@media (max-width: 480px) {{ .strip {{ grid-auto-columns: calc(100vw - 32px); }} .desk .clip {{ width: 100%; height: auto; aspect-ratio: 1440 / 900; }} .desk iframe {{ transform: scale(.24); }} }}
</style></head><body>
<div class=top><h1>Design directions{f" · round {e(str(meta['round']))}" if meta.get('round') else ''}</h1>
<p class=lede>{len(order)} directions for the same screen, side by side. Pick one and say what you like or dislike in the others.</p></div>
<div class=strip>{''.join(cards)}</div>
</body></html>
"""
    out = os.path.join(folder, "index.html")
    open(out, "w").write(page)
    print(out)


def _title(p):
    m = re.search(r"<title>(.*?)</title>", open(p, errors="replace").read(), re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else None


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
