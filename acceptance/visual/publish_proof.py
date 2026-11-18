#!/usr/bin/env python3
"""Copy a finished picture-first production into acceptance/visual/<name>/ so the site can publish it beside the atlas:
its style pick page, its design pick page, its look page, its open-gaps page and the built game itself.

    python3 acceptance/visual/publish_proof.py <production id> <name> [--about "..."]

Every page is regenerated from the production record (the same functions the engine used), with links back to the
atlas; every image is a copy of a file the production made. Nothing is re-rendered or re-captured here."""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
from production import store, visual

GAME_FILES = (".html", ".css", ".js", ".webmanifest", ".woff2", ".md", ".png", ".json")


def eff(P, tid):
    t = P["tasks"][tid]
    while t.get("superseded_by"): t = P["tasks"][t["superseded_by"]]
    return t


def out(P, tid, role):
    return next((o["path"] for o in eff(P, tid).get("outputs") or [] if o.get("role") == role), None)


def _webp_pages(d, width=1200):
    from PIL import Image
    if not os.path.isdir(d): return
    names = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            if f.lower().endswith(".png"):
                src = os.path.join(r, f); im = Image.open(src).convert("RGB")
                w = width if im.width > im.height else 600
                if im.width > w: im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
                im.save(src[:-4] + ".webp", "WEBP", quality=84, method=6); os.remove(src); names[f] = f[:-4] + ".webp"
    page = os.path.join(d, "index.html")
    if os.path.isfile(page):
        t = open(page).read()
        for a, b in names.items(): t = t.replace(a, b)
        open(page, "w").write(t)


def main(pid, name, about):
    P = store.load(pid)
    dest = os.path.join(HERE, name)
    os.makedirs(dest, exist_ok=True)
    title, proj = P["spec"]["title"], P["spec"]["project"]["path"]
    crumbs = lambda depth: f"<p class=crumbs><a href='{'../' * depth}'>Style atlas</a> / {title}</p>"
    sp = P["tasks"]["design.style_pick"]["result"]["selection"]
    styles_json = os.path.join(os.path.dirname(sp["scene"]), "styles.json")
    visual.style_page(json.load(open(styles_json)), os.path.dirname(styles_json), os.path.join(dest, "style-pick"), title,
                      chosen=sp["styles"], how=sp["how"], crumbs=crumbs(2))
    dp = P["tasks"]["design.design_pick"]["result"]["selection"]
    dj = next(o["path"] for o in P["tasks"]["design.designs"]["outputs"] if o["path"].endswith("designs.json"))
    visual.design_page(json.load(open(dj)), os.path.dirname(dj), os.path.join(dest, "design-pick"), title, chosen=dp["design"], note=dp.get("liked_in_others"), crumbs=crumbs(2), icon=(dp.get("icon") or {}).get("choice"))
    tdir = os.path.join(proj, visual.art_dir(proj), "target")
    target = {k: os.path.join(tdir, f) for f in os.listdir(tdir) for k in ("phone", "browser", "desktop", "play", "icon") if f.startswith(k + ".")}
    rep = json.load(open(out(P, "release.shots", "shots_report")))
    G = json.load(open(out(P, "review.gaps", "visual_gaps")))
    visual.look_page(target, rep, os.path.join(dest, "look"), title, style=dp.get("look_name"), live_url="../game/",
                     remaining=G["gaps"] if G.get("round", 0) >= visual.ROUNDS else [], crumbs=crumbs(2))
    rem = out(P, "review.gaps", "remaining_page")
    if rem:
        if os.path.isdir(os.path.join(dest, "open-gaps")): shutil.rmtree(os.path.join(dest, "open-gaps"))
        shutil.copytree(os.path.dirname(rem), os.path.join(dest, "open-gaps"))
    gd = os.path.join(dest, "game")
    if os.path.isdir(gd): shutil.rmtree(gd)
    for d, ds, fs in os.walk(proj):
        ds[:] = [x for x in ds if x not in ("art-direction", "tests", ".git", "node_modules", "native-icons")]
        for f in fs:
            if f.endswith(GAME_FILES + (".ico",)) and f != "gitcraft.assets.json" and not f.endswith(".license.json") and f != "icon-1024.png":
                rel = os.path.relpath(os.path.join(d, f), proj); os.makedirs(os.path.dirname(os.path.join(gd, rel)), exist_ok=True)
                shutil.copyfile(os.path.join(d, f), os.path.join(gd, rel))
    for page in ("style-pick", "design-pick", "look", "open-gaps"):   # published copies at screen size (webp); the production keeps the originals
        _webp_pages(os.path.join(dest, page))
    rec = os.path.join(dest, "record"); os.makedirs(rec, exist_ok=True)   # the decisions as files: direction, shot list, target record
    shutil.copyfile(next(o["path"] for o in P["tasks"]["design.direction"]["outputs"] if o["path"].endswith("direction.json")), os.path.join(rec, "direction.json"))
    for f in ("shots.json", "target/target.json"): shutil.copyfile(os.path.join(proj, visual.art_dir(proj), f), os.path.join(rec, os.path.basename(f)))
    for k in [k for k in P["order"] if k.startswith("review.creative")]:
        shutil.copyfile(next(o["path"] for o in eff(P, k)["outputs"] if o["role"] == "review"), os.path.join(rec, k.replace("review.creative", "review") + ".json"))
    rounds = sorted(k for k in P["tasks"] if k.startswith("fix.visual.r"))
    reviews = [eff(P, k) for k in P["order"] if k.startswith("review.creative")]
    record = {"title": title, "about": about, "production": P["id"], "plan_version": P["plan_version"], "status": P.get("status"),
              "verdict": (P.get("verdict") or {}).get("verdict"), "style": sp, "design": {**{k: dp[k] for k in ("design", "style", "look_name", "liked_in_others", "approved_by")}, "icon": (dp.get("icon") or {}).get("choice")},
              "moments": [k for k in P["order"] if P["tasks"][k].get("moment")], "visual_rounds": rounds,
              "review_gaps": [len(json.load(open(next(o["path"] for o in r["outputs"] if o["role"] == "review"))).get("gaps") or []) for r in reviews],
              "remaining": [g["id"] for g in G["gaps"]] if G.get("round", 0) >= visual.ROUNDS else [],
              "tasks": {k: P["tasks"][k]["state"] for k in P["order"]},
              "pages": {"style-pick": "the shortlist, rendered as this game's scene", "design-pick": "three designs of the real title screen",
                        "look": "the chosen frame beside the shipped screens", "game": "the shipped game (phone or desktop: hold to climb)"}}
    json.dump(record, open(os.path.join(dest, "proof.json"), "w"), indent=1)
    return record


if __name__ == "__main__":
    a = sys.argv[1:]
    about = a[a.index("--about") + 1] if "--about" in a else ""
    r = main(a[0], a[1], about)
    print(json.dumps({k: r[k] for k in ("title", "verdict", "visual_rounds", "review_gaps", "remaining")}, indent=1))
