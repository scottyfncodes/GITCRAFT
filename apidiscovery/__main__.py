"""python3 -m apidiscovery <command>

  search "<need>" [--category C] [--auth none|apiKey|oauth] [--https] [--cors] [--docs] [--limit N]
  compare <api> [<api> ...] [--need "<need>"]      2 to 4 APIs side by side; one API: its assessment and alternatives
  guide <api> [--language javascript|python|curl] [--platform server|browser|mobile] [--project DIR]
  recommend <project> [--need "<need>"]            read-only project-aware recommendations
  status                                           catalogue source, age, size; when links were last checked
  refresh                                          fetch the public-apis catalogue (needs network; keeps the old one on failure)
  check [--limit N]                                check every documentation link (needs network; one GET per API)
  build <file>                                     write the /apis/ page's data file
  publish <dir>                                    write the /apis/ page

Add --json for the raw result."""
import argparse, json, sys
from . import catalog, checks as CK, site, tools


def main(argv=None):
    ap = argparse.ArgumentParser(prog="apidiscovery", description="API Discovery (GITCRAFT)"); sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("search"); s.add_argument("need"); s.add_argument("--category"); s.add_argument("--auth", choices=["none", "apiKey", "oauth"])
    for f in ("https", "cors", "docs"): s.add_argument("--" + f, action="store_true")
    s.add_argument("--limit", type=int, default=8)
    c = sp.add_parser("compare"); c.add_argument("apis", nargs="+"); c.add_argument("--need")
    g = sp.add_parser("guide"); g.add_argument("api"); g.add_argument("--language"); g.add_argument("--platform"); g.add_argument("--project")
    r = sp.add_parser("recommend"); r.add_argument("project"); r.add_argument("--need")
    sp.add_parser("status"); sp.add_parser("refresh")
    k = sp.add_parser("check"); k.add_argument("--limit", type=int); k.add_argument("--workers", type=int, default=24)
    b = sp.add_parser("build"); b.add_argument("file")
    p = sp.add_parser("publish"); p.add_argument("dir")
    for x in (s, c, g, r, sp.choices["status"], sp.choices["refresh"], k): x.add_argument("--json", action="store_true")
    o = ap.parse_args(argv)
    if o.cmd == "refresh":
        R = catalog.refresh(); print(json.dumps(R, indent=1) if o.json else f"{R['status']}: {R['why']}")
        return 0 if R.get("usable") else 1   # an unreachable upstream with a working catalogue is not a failure
    if o.cmd == "check":
        C = catalog.load()
        if not C["entries"]: print("no catalogue to check: run refresh first", file=sys.stderr); return 1
        K = CK.run(C["entries"], workers=o.workers, limit=o.limit)
        if not CK.plausible(K):
            print(f"not saved: {K['counts'].get('unreachable', 0)} of {K['of']} links were unreachable, which says the checker has no network, not that the APIs are gone", file=sys.stderr); return 1
        CK.save(K); print(json.dumps({k: K[k] for k in ("checked", "counts", "of")}, indent=1) if o.json else f"checked {K['of']} links: " + ", ".join(f"{v} {k}" for k, v in sorted(K["counts"].items())))
        return 0
    if o.cmd == "build":
        D = site.data()
        with open(o.file, "w") as f: json.dump(D, f, ensure_ascii=False, separators=(",", ":"))
        print(f"wrote {len(D['entries'])} APIs to {o.file}"); return 0 if catalog.valid({"entries": catalog.load()["entries"]}) else 1
    if o.cmd == "publish":
        print(f"published {site.publish(o.dir)} APIs to {o.dir}"); return 0
    args = {"search": lambda: {"need": o.need, "category": o.category, "auth": o.auth, "https": o.https, "cors": o.cors, "docs": o.docs, "limit": o.limit},
            "compare": lambda: {"apis": o.apis, "need": o.need}, "guide": lambda: {"api": o.api, "language": o.language, "platform": o.platform, "project": o.project},
            "recommend": lambda: {"project": o.project, "need": o.need}, "status": lambda: {}}[o.cmd]()
    R = tools.call("api_discovery_" + o.cmd, args)
    if o.json: print(json.dumps(R, indent=1, ensure_ascii=False)); return 0
    print(text(o.cmd, R)); return 0


def text(cmd, R):
    L = []
    cat = R.get("catalogue") or {}
    def card(c):
        ck = c["checked"]
        return [f"  {c['name']}  [{c['category']}]  id: {c['id']}", f"    {c['description']}", f"    docs: {c['documentation']}",
                f"    catalogue (unverified): auth {c['catalogue']['auth']} · HTTPS {c['catalogue']['https']} · CORS {c['catalogue']['cors']}" + (" · sponsored listing" if c["catalogue"]["sponsored_listing"] else ""),
                "    checked: " + (f"documentation link {ck['documentation_link']} on {str(ck['on'])[:10]}" if ck.get("on") else "documentation link not checked"),
                "    unknown: " + ", ".join(c["unknown"])] + ([f"    matched: {'; '.join(c['why'])}"] if c.get("why") else []) + [""]
    if cmd == "search":
        L += [f"{R.get('total_matches', 0)} match(es)" + (f" for: {', '.join(R['understood']['terms'])}" if R.get("understood", {}).get("terms") else ""), ""] + [f"note: {n}" for n in R.get("notes") or []] + [""]
        for c in R.get("results") or []: L += card(c)
        for g in R.get("also_consider") or []:
            L += [f"Also consider, for {g['need']}:", ""]
            for c in g["results"]: L += card(c)
    elif cmd == "compare":
        if R["status"] != "ok": return "\n".join(map(str, R.get("why") or []))
        for a in R["apis"]:
            L += [f"{a['name']}  ({a['documentation']})"] + [f"  {x['criterion']}: {x['finding']}  [{x['basis']}]" for x in a["criteria"]] + [""]
        L += ["Trade-offs:"] + [f"  - {t}" for t in R["tradeoffs"]] + ["", R["method"]]
        for c in R.get("alternatives") or []: L += (["", "Alternatives:"] if c is R["alternatives"][0] else []) + card(c)
    elif cmd == "guide":
        return R["markdown"] if R["status"] == "ok" else str(R.get("why"))
    elif cmd == "recommend":
        P = R["project"]; L += [f"{P['name']}: {P.get('kind') or 'project'}, {P.get('language') or 'language not detected'}, {P.get('platform') or 'platform not detected'}", f"({R['changed']})", ""]
        if R.get("note"): L.append(R["note"])
        for g in R["recommendations"]:
            L += [f"For {g['need']} ({g['matches']} matches):", ""]
            for c in g["results"][:3]: L += card(c)
        for u in R["already_using"]:
            L += [f"Appears to use {u['api']} ({u['seen']}; {u['lead']}). Alternatives:", ""]
            for c in u["alternatives"][:3]: L += card(c)
    elif cmd == "status":
        L += [f"{cat.get('apis')} APIs in {len(R.get('categories') or [])} categories, from {cat.get('source')} ({cat.get('license')})", R["attribution"], R["refresh"]]
    L.append(f"Catalogue fetched {str(cat.get('fetched'))[:10]} · links checked {str(cat.get('links_checked'))[:10] if cat.get('links_checked') else 'never'} · {cat.get('read')}")
    return "\n".join(L)


if __name__ == "__main__":
    sys.exit(main())
