"""DESIGNCRAFT command line.

  python3 -m gamedesign assess <game-repo> [--out a.json] [--report r.md] [--record] [--history DIR] [--no-playcraft]
  python3 -m gamedesign report <assessment.json>                  Markdown report to stdout
  python3 -m gamedesign spec <assessment.json> <proposal-id>      implementation-ready spec to stdout
  python3 -m gamedesign history [<game-id>]                       recorded runs
  python3 -m gamedesign publish [history-dir] [dist-dir]          build the static web app (default dist: forgecraft/ui/dist/designcraft)

The game repository is opened read-only. Outputs may not be written inside it."""
import argparse, json, os, sys
from . import engine, history, report


def _inside(p, root):
    p, root = os.path.realpath(p), os.path.realpath(root)
    return p == root or p.startswith(root + os.sep)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="designcraft")
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("assess"); a.add_argument("repo"); a.add_argument("--out"); a.add_argument("--report"); a.add_argument("--record", action="store_true")
    a.add_argument("--history"); a.add_argument("--no-playcraft", action="store_true")
    r = sp.add_parser("report"); r.add_argument("assessment")
    s = sp.add_parser("spec"); s.add_argument("assessment"); s.add_argument("proposal")
    h = sp.add_parser("history"); h.add_argument("game", nargs="?"); h.add_argument("--history")
    pb = sp.add_parser("publish"); pb.add_argument("archive", nargs="?"); pb.add_argument("dist", nargs="?")
    o = ap.parse_args(argv)
    if o.cmd == "assess":
        for p in (o.out, o.report, o.history):
            if p and _inside(p, o.repo):
                print(f"refused: {p} is inside the game repository; DESIGNCRAFT keeps the game read-only", file=sys.stderr); return 2
        A = engine.assess(o.repo, playcraft=not o.no_playcraft)
        if o.record:
            path = history.record(A, o.history); print(f"recorded {path}", file=sys.stderr)
        if o.out: json.dump(A, open(o.out, "w"), indent=1, default=str)
        if o.report: open(o.report, "w").write(report.assessment_md(A))
        S = A["score"]
        print(json.dumps({"game": A["game"]["id"], "overall": S["overall"], "ceiling": S["ceiling"], "coverage": S["coverage"], "confidence": S["confidence"],
                          "categories": {k: v["score"] for k, v in S["categories"].items()}, "findings": len(A["findings"]), "proposals": len(A["proposals"]),
                          "run_id": A.get("run_id"), "compare": (A.get("compare") or {}).get("kind")}, indent=1))
        return 0
    if o.cmd == "report":
        print(report.assessment_md(json.load(open(o.assessment)))); return 0
    if o.cmd == "spec":
        print(report.spec_md(json.load(open(o.assessment)), o.proposal)); return 0
    if o.cmd == "history":
        root = o.history or history.store()
        games = [o.game] if o.game else sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))) if os.path.isdir(root) else []
        for gid in games:
            for run in history.runs(gid, root):
                s = history.summary(run); print(f"{gid}  {s['run_id']}  {s['overall']}/100 (ceiling {s['ceiling']}, {s['confidence']})  method {s['method']}")
        return 0
    if o.cmd == "publish":
        from . import site
        n = site.publish(o.archive or history.store(), o.dist or os.path.join(history.REPO, "forgecraft", "ui", "dist", "designcraft"))
        print(f"published {n} games"); return 0
    return 1
