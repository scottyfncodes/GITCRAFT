"""The style atlas: render its samples and publish its page (docs/visual-direction.md).

  python3 -m production.atlas render [id,id,...]     every look's two samples → production/kit/atlas/samples/<id>/{game,app}.webp
  python3 -m production.atlas publish <dist>          the atlas page → <dist>/index.html (+ samples, + the proof productions)

The 3D look is rendered with MeshCraft first (looks/low-poly-3d.sh); every other look is painted in Chromium by its
painter (looks/<id>.js). The page lists what each look suits, what is hard in it, which tools make it, and the looks
GITCRAFT cannot do well today. It is a menu, never a house style. Standard library (+ Pillow for webp when present)."""
import html, json, os, shutil, subprocess, sys, tempfile
from . import REPO
from . import visual

ATLAS = visual.ATLAS_DIR
SAMPLES = os.path.join(ATLAS, "samples")
PROOF = os.path.join(REPO, "acceptance", "visual")   # acceptance productions whose pick and look pages are published beside the atlas


def _webp(src, dst, width):
    try:
        from PIL import Image
        im = Image.open(src).convert("RGB")
        if im.width > width: im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst, "WEBP", quality=86, method=6)
    except ImportError:   # no Pillow: keep the PNG (the page takes either)
        shutil.copyfile(src, os.path.splitext(dst)[0] + ".png")


def render(ids=None, scene=None, out=None):
    A = visual.atlas()
    want = [l for l in A["looks"] if not ids or l["id"] in ids]
    tmp = tempfile.mkdtemp(prefix="atlas-")
    for l in want:
        sh = os.path.join(ATLAS, "looks", l["id"] + ".sh")
        if os.path.isfile(sh):   # a pre-rendered look (3D: MeshCraft/Blender) renders its scene first
            sc = scene or os.path.join(ATLAS, "scenes", "atlas.json")
            slug = visual._slug((json.load(open(sc)).get("game") or {}).get("title") or "scene")
            cache = os.path.join(ATLAS, "looks", "_renders", slug)
            if os.path.isfile(os.path.join(cache, "game3d.png")) and os.path.isfile(os.path.join(cache, "render3d.json")) and not os.environ.get("ATLAS_RERENDER"): continue
            r = subprocess.run(["bash", sh, sc, cache, "64"], capture_output=True, text=True, timeout=1800)
            if r.returncode: print(f"{l['id']}: pre-render failed: {(r.stderr or r.stdout)[-600:]}", file=sys.stderr)
    args = ["node", os.path.join(ATLAS, "render.mjs"), tmp, ",".join(l["id"] for l in want), "game,app"] + ([scene] if scene else [])
    subprocess.run(args, check=True, timeout=1800)
    rep = json.load(open(os.path.join(tmp, "render.json")))
    bad = {k: v for k, v in rep.items() if not all(s["ok"] for s in v.values())}
    for l in want:
        for s, w in (("game", 1440), ("app", 780)):
            p = os.path.join(tmp, l["id"], f"{s}.png")
            if os.path.isfile(p): _webp(p, os.path.join(out or SAMPLES, l["id"], f"{s}.webp"), w)
    shutil.rmtree(tmp, ignore_errors=True)
    if bad: print("not rendered cleanly: " + json.dumps(bad)[:1500], file=sys.stderr)
    return {"rendered": [l["id"] for l in want], "problems": bad}


CSS = visual.CSS + """
.hero{padding:36px 0 18px;max-width:780px}.hero h1{font-size:40px;letter-spacing:-.02em}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 26px}.nav button{font:600 14px ui-sans-serif,system-ui;min-height:40px;padding:0 14px;border-radius:99px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
.nav button[aria-pressed=true]{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.look{display:grid;gap:14px 22px;grid-template-columns:minmax(0,2.3fr) minmax(0,1fr);grid-template-areas:"head head" "game phone" "text phone";grid-template-rows:auto auto 1fr;align-items:start;padding:30px 0;border-top:1px solid var(--line)}
.look .head{grid-area:head;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px}.look .game{grid-area:game;margin:0}.look .phone{grid-area:phone;margin:0}
.look img{display:block;width:100%;height:auto;border-radius:10px;border:1px solid var(--line);background:var(--line)}
.look .text{grid-area:text;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px 22px}
.look h2{font-size:24px;margin:0}.num{color:var(--muted);font-variant-numeric:tabular-nums;margin-right:8px}
.k{font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 4px}
.cannot{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));margin-top:12px}
.cannot div{border:1px dashed var(--line);border-radius:12px;padding:14px 16px}
.proof{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(100%,260px),1fr));margin:10px 0 0}
.proof a{display:block;border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:var(--card);text-decoration:none}
.proof a b{display:block;font-size:17px}
@media (max-width:760px){.look{grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-areas:"head head" "game game" "phone text"}.look .text{grid-template-columns:minmax(0,1fr)}.hero h1{font-size:30px}}
@media (max-width:480px){.look{grid-template-columns:minmax(0,1fr);grid-template-areas:"head" "game" "phone" "text"}.look .phone{max-width:240px}}"""


def publish(dist):
    """The atlas page and its samples at <dist>/ (dist is the site's /atlas/ folder), plus each proof production's
    style pick, design pick and look pages at <dist>/<proof>/<page>/."""
    A = visual.atlas(); e = html.escape
    os.makedirs(dist, exist_ok=True)
    fams = A["families"]
    proofs = []
    if os.path.isdir(PROOF):
        for name in sorted(os.listdir(PROOF)):
            src = os.path.join(PROOF, name)
            if not os.path.isfile(os.path.join(src, "proof.json")): continue
            meta = json.load(open(os.path.join(src, "proof.json")))
            dst = os.path.join(dist, name)
            if os.path.isdir(dst): shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("proof.json", "*.md"))
            proofs.append((name, meta))
    secs = []
    for l in A["looks"]:
        imgs = {}
        for s in ("game", "app"):
            for ext in (".webp", ".png"):
                p = os.path.join(SAMPLES, l["id"], s + ext)
                if os.path.isfile(p):
                    os.makedirs(os.path.join(dist, "samples", l["id"]), exist_ok=True)
                    shutil.copyfile(p, os.path.join(dist, "samples", l["id"], s + ext)); imgs[s] = f"samples/{l['id']}/{s}{ext}"; break
        tells = "".join(f"<li>{e(t['id'])}: {e(t['reason'])}</li>" for t in l.get("tells") or [])
        secs.append(f"""<section class=look id="{e(l['id'])}" data-family="{e(l['family'])}">
<div class=head><h2><span class=num>{l['n']:02d}</span>{e(l['name'])}</h2><p class=meta>{e(fams.get(l['family'], l['family']))}</p></div>
<figure class=game>{f'<img src="{e(imgs["game"])}" alt="{e(l["name"])}: the game scene" loading=lazy width=1440 height=810>' if imgs.get('game') else '<div class=notseen>not rendered</div>'}<figcaption>Game scene, 960×540</figcaption></figure>
<figure class=phone>{f'<img src="{e(imgs["app"])}" alt="{e(l["name"])}: the app screen" loading=lazy width=780 height=1688>' if imgs.get('app') else '<div class=notseen>not rendered</div>'}<figcaption>App screen, phone 390×844</figcaption></figure>
<div class=text><div><p class=k>Suits</p><p style="margin:0">{e(l['suits'])}</p></div><div><p class=k>Hard</p><p style="margin:0">{e(l['hard'])}</p></div>
<div><p class=k>Made with</p><p class=meta style="margin:0">{e(', '.join(l['tools']))} · type: {e(', '.join(l['fonts']))}</p></div>
{f'<div><p class=k>Tells it chooses on purpose</p><ul class=meta style="margin:0;padding-left:18px">{tells}</ul></div>' if tells else ''}</div>
</section>""")
    chips = "<button type=button aria-pressed=true data-f=all>All</button>" + "".join(f"<button type=button aria-pressed=false data-f='{e(k)}'>{e(k)}</button>" for k in fams)
    proof_html = ""
    if proofs:
        proof_html = "<h2 style='margin-top:40px'>The atlas in a production</h2><p class=lede>A real production that went through the picture-first path: its style pick, its design pick and the shipped look.</p>" + "".join(
            f"<p class=meta style='margin:14px 0 6px'><b>{e(m.get('title', n))}</b>: {e(m.get('about', ''))}</p><div class=proof>"
            + "".join(f"<a href='{e(n)}/{e(page)}/'><b>{e(label)}</b><span class=meta>{e(m.get('pages', {}).get(page, ''))}</span></a>"
                      for page, label in (("style-pick", "Style pick"), ("design-pick", "Design pick"), ("look", "Look page")) if os.path.isdir(os.path.join(dist, n, page)))
            + "</div>" for n, m in proofs)
    cannot = "".join(f"<div><b>{e(c['name'])}</b><p class=meta style='margin:6px 0 0'>{e(c['why'])}</p></div>" for c in A["cannot"])
    body = f"""<p class=crumbs><a href="../">GITCRAFT</a> / Style atlas</p>
<div class=hero><h1>Style atlas</h1><p class=lede>{len(A['looks'])} looks GITCRAFT can produce well with its own tools, each rendered as the same small game scene and the
same phone screen. When a production starts, six to eight of these are rendered as <i>that</i> product's key scene for the style pick. A menu of what is possible,
never a house style.</p></div>
<nav class=nav aria-label="Filter by family">{chips}</nav>
{''.join(secs)}
<h2 style="margin-top:40px">What we cannot do well today</h2><p class=lede>Never offered at the style pick, and why.</p><div class=cannot>{cannot}</div>
{proof_html}
<script>document.querySelectorAll('.nav button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('.nav button').forEach(x=>x.setAttribute('aria-pressed',x===b));
document.querySelectorAll('.look').forEach(s=>s.hidden=!(b.dataset.f==='all'||s.dataset.family===b.dataset.f));}});</script>"""
    with open(os.path.join(dist, "index.html"), "w") as f: f.write(visual._page("Style atlas", body, "The looks GITCRAFT can produce, each rendered as the same two samples").replace(visual.CSS, CSS))
    return len(A["looks"]), len(proofs)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["render"]: print(json.dumps(render(a[1].split(",") if len(a) > 1 else None), indent=1))
    elif a[:1] == ["publish"] and len(a) == 2: print("atlas: %d looks, %d proof production(s)" % publish(a[1]))
    else: sys.exit(__doc__)
