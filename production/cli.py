"""GITCRAFT Production command line (the same calls as studiocraft's production_* tools).

  python3 -m production plan "<master prompt>" [--project DIR] [--overrides JSON]
  python3 -m production run <id> [--workers N]          run (or resume) until done or waiting on someone
  python3 -m production status <id>
  python3 -m production submit <id> <task> [--files a b] [--notes TEXT] [--url URL --evidence FILE]
  python3 -m production approve <id> <task> [--decline] [--note TEXT]
  python3 -m production report <id>                     the acceptance report (Markdown)
  python3 -m production list
  python3 -m production contracts                       every department's contract

The store is $GITCRAFT_PRODUCTION_HOME or <first GITCRAFT root>/gitcraft-out/production."""
import argparse, json, sys
from . import engine, store, report, contracts


def main(argv=None):
    ap = argparse.ArgumentParser(prog="production")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("prompt"); p.add_argument("--project"); p.add_argument("--overrides")
    r = sp.add_parser("run"); r.add_argument("id"); r.add_argument("--workers", type=int, default=4)
    s = sp.add_parser("status"); s.add_argument("id")
    sb = sp.add_parser("submit"); sb.add_argument("id"); sb.add_argument("task"); sb.add_argument("--files", nargs="*"); sb.add_argument("--notes")
    sb.add_argument("--url"); sb.add_argument("--evidence"); sb.add_argument("--license"); sb.add_argument("--run", action="store_true")
    a = sp.add_parser("approve"); a.add_argument("id"); a.add_argument("task"); a.add_argument("--decline", action="store_true"); a.add_argument("--note")
    rp = sp.add_parser("report"); rp.add_argument("id")
    sp.add_parser("list"); sp.add_parser("contracts")
    o = ap.parse_args(argv)
    if o.cmd == "plan":
        pr = engine.plan(o.prompt, o.project, json.loads(o.overrides) if o.overrides else None)
        out = plan_summary(pr)
    elif o.cmd == "run": out = engine.run(o.id, max_workers=o.workers)
    elif o.cmd == "status": out = engine.status(o.id)
    elif o.cmd == "submit": out = engine.submit(o.id, o.task, o.files, o.notes, o.url, o.evidence, o.license, run_after=o.run)
    elif o.cmd == "approve": out = engine.approve(o.id, o.task, approved=not o.decline, note=o.note)
    elif o.cmd == "report": print(report.markdown(store.load(o.id))); return 0
    elif o.cmd == "list": out = store.list_all()
    elif o.cmd == "contracts": out = contracts.all_contracts()
    print(json.dumps(out, indent=1, default=str))
    return 0


def plan_summary(pr):
    return {"production": pr["id"], "status": pr["status"], "store": pr["store"], "spec": {k: pr["spec"][k] for k in
            ("title", "deliverable", "dimension", "platform", "genres", "assets", "quality", "project", "authorisations", "assumptions", "questions", "because")},
            "acceptance": pr["spec"]["acceptance"], "problems": pr["problems"], "blocked_up_front": pr["readiness"], "decisions": pr["decisions"],
            "parallel_groups": pr["parallel_groups"],
            "tasks": [{"id": t, "title": pr["tasks"][t]["title"], "owner": pr["tasks"][t]["owner"], "depends_on": pr["tasks"][t]["depends_on"]} for t in pr["order"]]}


if __name__ == "__main__":
    sys.exit(main())
