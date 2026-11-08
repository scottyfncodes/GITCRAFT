"""GITCRAFT Production command line (the same calls as studiocraft's production_* tools).

  python3 -m production start ["Run GITCRAFT: <anything>"] [--project DIR]   the one entry point (idea, spec, repo URL, project)
  python3 -m production idea "<idea>" [--project DIR]               save an idea (nothing read or built)
  python3 -m production recon <id> [--depth quick|deep] [--findings FILE]   Recon work order / submit findings
  python3 -m production promote <id>                               idea → read-only Discovery → Decision Room
  python3 -m production plan "<master prompt>" [--project DIR] [--overrides JSON] [--recon quick|deep]   New Build
  python3 -m production decide <id> [--answers JSON] [--approve|--decline] [--note TEXT]   the Decision Room
  python3 -m production revise <id> --overrides JSON --reason TEXT   change the plan (material → re-approval)
  python3 -m production discard <id> [--park]
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
    p = sp.add_parser("plan"); p.add_argument("prompt"); p.add_argument("--project"); p.add_argument("--overrides"); p.add_argument("--recon", choices=["quick", "deep"])
    st = sp.add_parser("start", help="Run GITCRAFT: any idea, spec, repo URL or project folder"); st.add_argument("text", nargs="?", default=""); st.add_argument("--project")
    i = sp.add_parser("idea"); i.add_argument("text"); i.add_argument("--project")
    rc = sp.add_parser("recon"); rc.add_argument("id"); rc.add_argument("--depth", default="quick", choices=["quick", "deep"]); rc.add_argument("--findings", help="JSON file of findings to submit")
    pm = sp.add_parser("promote"); pm.add_argument("id"); pm.add_argument("--overrides")
    dc = sp.add_parser("discard"); dc.add_argument("id"); dc.add_argument("--park", action="store_true"); dc.add_argument("--reason")
    de = sp.add_parser("decide"); de.add_argument("id"); de.add_argument("--answers", help="JSON {decision: value}"); de.add_argument("--approve", action="store_true")
    de.add_argument("--decline", action="store_true", help="decline a pending revision"); de.add_argument("--note")
    rv = sp.add_parser("revise"); rv.add_argument("id"); rv.add_argument("--overrides", required=True); rv.add_argument("--reason", required=True)
    r = sp.add_parser("run"); r.add_argument("id"); r.add_argument("--workers", type=int, default=4)
    s = sp.add_parser("status"); s.add_argument("id")
    sb = sp.add_parser("submit"); sb.add_argument("id"); sb.add_argument("task"); sb.add_argument("--files", nargs="*"); sb.add_argument("--notes")
    sb.add_argument("--url"); sb.add_argument("--evidence"); sb.add_argument("--license"); sb.add_argument("--run", action="store_true")
    a = sp.add_parser("approve"); a.add_argument("id"); a.add_argument("task"); a.add_argument("--decline", action="store_true"); a.add_argument("--note"); a.add_argument("--choice")
    rp = sp.add_parser("report"); rp.add_argument("id")
    sp.add_parser("list"); sp.add_parser("contracts")
    o = ap.parse_args(argv)
    if o.cmd == "plan":
        pr = engine.plan(o.prompt, o.project, json.loads(o.overrides) if o.overrides else None, recon=o.recon)
        out = pr if "recon_order" in pr else plan_summary(pr)
    elif o.cmd == "start":
        from . import entry
        out = entry.start(o.text, o.project)
    elif o.cmd == "idea": pr = engine.idea(o.text, o.project); out = dict(engine.lifecycle_view(pr), brief=pr["brief"])
    elif o.cmd == "recon": out = engine.submit_recon(o.id, json.load(open(o.findings))) if o.findings else engine.start_recon(o.id, o.depth)
    elif o.cmd == "promote": out = plan_summary(engine.promote(o.id, json.loads(o.overrides) if o.overrides else None))
    elif o.cmd == "discard": out = engine.discard(o.id, park=o.park, reason=o.reason)
    elif o.cmd == "decide": out = engine.decide(o.id, json.loads(o.answers) if o.answers else None, approve=o.approve and not o.decline, note=o.note)
    elif o.cmd == "revise": out = engine.revise(o.id, json.loads(o.overrides), o.reason)
    elif o.cmd == "run": out = engine.run(o.id, max_workers=o.workers)
    elif o.cmd == "status": out = engine.status(o.id)
    elif o.cmd == "submit": out = engine.submit(o.id, o.task, o.files, o.notes, o.url, o.evidence, o.license, run_after=o.run)
    elif o.cmd == "approve": out = engine.approve(o.id, o.task, approved=not o.decline, note=o.note, choice=o.choice)
    elif o.cmd == "report": print(report.markdown(store.load(o.id))); return 0
    elif o.cmd == "list": out = store.list_all()
    elif o.cmd == "contracts": out = contracts.all_contracts()
    print(json.dumps(out, indent=1, default=str))
    return 0


def plan_summary(pr):
    lv = engine.lifecycle_view(pr)
    return {"production": pr["id"], "status": pr["status"], "stage": lv["stage"], "summary": lv["summary"], "store": pr["store"],
            "decision_room": lv.get("decision_room"), "discovery_report": pr.get("discovery_report"), "spec": {k: pr["spec"].get(k) for k in
            ("title", "deliverable", "dimension", "platform", "genres", "assets", "quality", "project", "authorisations", "engineering", "icon", "attribution",
             "assumptions", "questions", "because")},
            "acceptance": pr["spec"]["acceptance"], "problems": pr["problems"], "unmeasured_criteria": pr.get("unmeasured_criteria"), "warnings": pr.get("warnings"), "blocked_up_front": pr["readiness"], "decisions": pr["decisions"],
            "parallel_groups": pr["parallel_groups"],
            "tasks": [{"id": t, "title": pr["tasks"][t]["title"], "owner": pr["tasks"][t]["owner"], "depends_on": pr["tasks"][t]["depends_on"]} for t in pr["order"]]}


if __name__ == "__main__":
    sys.exit(main())
