"""GITCRAFT Production command line (the same calls as studiocraft's production_* tools).

  python3 -m production start ["Run GITCRAFT: <anything>"] [--project DIR]   the one entry point (idea, spec, repo URL, project)
  python3 -m production verify-live <id> <url> [--submit]   after deploying: prove the live URL serves this release
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
import argparse, json, os, sys
from . import engine, store, report, contracts


def main(argv=None):
    ap = argparse.ArgumentParser(prog="production")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("prompt"); p.add_argument("--project"); p.add_argument("--overrides"); p.add_argument("--recon", choices=["quick", "deep"])
    st = sp.add_parser("start", help="Run GITCRAFT: any idea, spec, repo URL or project folder"); st.add_argument("text", nargs="?", default=""); st.add_argument("--project")
    vl = sp.add_parser("verify-live", help="after deploying: prove the live URL serves this release (run from your own shell)")
    vl.add_argument("id"); vl.add_argument("url"); vl.add_argument("--submit", action="store_true"); vl.add_argument("--no-browser", action="store_true")
    vl.add_argument("--commit", help="the commit the deployment was built from (e.g. Vercel's githubCommitSha): build provenance compared with the project's HEAD")
    i = sp.add_parser("idea"); i.add_argument("text"); i.add_argument("--project")
    rc = sp.add_parser("recon"); rc.add_argument("id"); rc.add_argument("--depth", default="quick", choices=["quick", "deep"]); rc.add_argument("--findings", help="JSON file of findings to submit")
    pm = sp.add_parser("promote"); pm.add_argument("id"); pm.add_argument("--overrides")
    dc = sp.add_parser("discard"); dc.add_argument("id"); dc.add_argument("--park", action="store_true"); dc.add_argument("--reason")
    de = sp.add_parser("decide"); de.add_argument("id"); de.add_argument("--answers", help="JSON {decision: value}"); de.add_argument("--approve", action="store_true")
    de.add_argument("--decline", action="store_true", help="decline a pending revision"); de.add_argument("--note")
    rv = sp.add_parser("revise"); rv.add_argument("id"); rv.add_argument("--overrides", required=True); rv.add_argument("--reason", required=True)
    r = sp.add_parser("run"); r.add_argument("id"); r.add_argument("--workers", type=int, default=4)
    r.add_argument("--retry", action="append", default=[], help="a failed check to run again first (execution/request failures only)")
    r.add_argument("--retry-reason", help="why it runs again (required with --retry)")
    s = sp.add_parser("status"); s.add_argument("id")
    sb = sp.add_parser("submit"); sb.add_argument("id"); sb.add_argument("task"); sb.add_argument("--files", nargs="*"); sb.add_argument("--notes")
    sb.add_argument("--url"); sb.add_argument("--evidence"); sb.add_argument("--license"); sb.add_argument("--run", action="store_true")
    a = sp.add_parser("approve"); a.add_argument("id"); a.add_argument("task"); a.add_argument("--decline", action="store_true"); a.add_argument("--note"); a.add_argument("--choice")
    rp = sp.add_parser("report"); rp.add_argument("id")
    sp.add_parser("list"); sp.add_parser("contracts")
    gr = sp.add_parser("project-report", help="Run GITCRAFT report: one report across every department (read-only)")
    gr.add_argument("project", help="project folder, GitHub owner/repo or URL, or history id (owner--repo)")
    gr.add_argument("--refresh", default="quick", choices=["none", "quick", "full"])
    gr.add_argument("--save", default="store", choices=["store", "archive", "none"], help="archive: history/reports (committed, published at /reports/)")
    gr.add_argument("--out", help="write this report into this folder instead"); gr.add_argument("--json", action="store_true", help="print the JSON instead of Markdown")
    vi = sp.add_parser("vision", help="the product vision contract (a reference for the Creative Review)")
    vi.add_argument("action", choices=["draft", "approve", "show"]); vi.add_argument("project"); vi.add_argument("--fields", help="JSON object or file of vision fields (draft)")
    vi.add_argument("--version", type=int, help="the draft version to approve"); vi.add_argument("--by", help="who approved it (approve) or drafted it")
    cr = sp.add_parser("creative", help="Creative Review: pack existing evidence, submit a review, show the latest (advisory, never scored)")
    cr.add_argument("action", choices=["pack", "submit", "show"]); cr.add_argument("target", help="pack/show: the project; submit: the pack.json")
    cr.add_argument("--capture", action="append", default=[], help="a PLAYCRAFT or PIXELCRAFT output folder (repeatable)"); cr.add_argument("--review", help="submit: the review JSON file")
    pu = sp.add_parser("publish-reports", help="build the /reports/ site from an archive"); pu.add_argument("archive", nargs="?"); pu.add_argument("dist")
    o = ap.parse_args(argv)
    if o.cmd == "plan":
        pr = engine.plan(o.prompt, o.project, json.loads(o.overrides) if o.overrides else None, recon=o.recon)
        out = pr if "recon_order" in pr else plan_summary(pr)
    elif o.cmd == "start":
        from . import entry
        out = entry.start(o.text, o.project)
    elif o.cmd == "verify-live":
        from . import live
        rec = live.verify(store.load(o.id), o.url, browser=not o.no_browser, deployed_commit=o.commit)
        out = {"status": rec["status"], "release_status": rec.get("release_status"), "record": rec["record"], "summary": rec.get("summary"),
               "blockers": [c for c in rec["checks"] if c.get("category") == "blocker"] or None,
               "unverified": [c for c in rec["checks"] if c.get("category") == "unverified"] or None,
               "advisories": [c for c in rec["checks"] if c.get("category") == "advisory"] or None}
        if o.submit:
            pr = store.load(o.id); t = pr["tasks"].get("release.deploy")
            if not t: out["submit"] = "this production has no deployment task"
            elif t["state"] != "awaiting_agent": out["submit"] = f"release.deploy is {t['state']}, not waiting for the deployment (approve it first)"
            else: out["submit"] = engine.submit(o.id, "release.deploy", url=o.url, evidence=rec["record"], notes="verify-live")["submission"]
    elif o.cmd == "idea": pr = engine.idea(o.text, o.project); out = dict(engine.lifecycle_view(pr), brief=pr["brief"])
    elif o.cmd == "recon": out = engine.submit_recon(o.id, json.load(open(o.findings))) if o.findings else engine.start_recon(o.id, o.depth)
    elif o.cmd == "promote": out = plan_summary(engine.promote(o.id, json.loads(o.overrides) if o.overrides else None))
    elif o.cmd == "discard": out = engine.discard(o.id, park=o.park, reason=o.reason)
    elif o.cmd == "decide": out = engine.decide(o.id, json.loads(o.answers) if o.answers else None, approve=o.approve and not o.decline, note=o.note)
    elif o.cmd == "revise": out = engine.revise(o.id, json.loads(o.overrides), o.reason)
    elif o.cmd == "run":
        if o.retry: engine.retry(o.id, o.retry, o.retry_reason)
        out = engine.run(o.id, max_workers=o.workers)
    elif o.cmd == "status": out = engine.status(o.id)
    elif o.cmd == "submit": out = engine.submit(o.id, o.task, o.files, o.notes, o.url, o.evidence, o.license, run_after=o.run)
    elif o.cmd == "approve": out = engine.approve(o.id, o.task, approved=not o.decline, note=o.note, choice=o.choice)
    elif o.cmd == "report": print(report.markdown(store.load(o.id))); return 0
    elif o.cmd == "list": out = store.list_all()
    elif o.cmd == "contracts": out = contracts.all_contracts()
    elif o.cmd == "project-report":
        from . import project_report
        R = project_report.generate(o.project, refresh=o.refresh, save=o.save, out_dir=o.out)
        if not o.json:
            print(project_report.markdown(R)); print(f"\nSaved: {R['paths'].get('html') or 'not saved (--save none)'}", file=sys.stderr); return 0
        out = R
    elif o.cmd == "vision":
        from . import vision
        if o.action == "draft":
            f = json.load(open(o.fields)) if o.fields and os.path.isfile(o.fields) else json.loads(o.fields) if o.fields else None
            out = vision.summary(vision.draft(o.project, f, by=o.by))
        elif o.action == "approve": out = vision.summary(vision.approve(o.project, o.version, o.by))
        else:
            from . import project_report
            out = vision.summary(vision.latest(project_report.resolve(o.project)["id"]))
    elif o.cmd == "creative":
        from . import creative
        if o.action == "pack":
            K = creative.pack(o.target, o.capture); out = {k: K[k] for k in ("fingerprint", "counts", "warnings", "paths", "vision")}
        elif o.action == "submit":
            Rv = creative.submit(o.target, o.review); out = {"review_id": Rv["review_id"], "dir": Rv["_dir"], "bound_to": Rv["bound_to"]}
        else:
            from . import project_report
            out = creative.for_report(project_report.resolve(o.target))
    elif o.cmd == "publish-reports":
        from . import project_report
        n = project_report.publish_site(o.archive or project_report.archive_root(), o.dist); print(f"published {n} report(s) to {o.dist}"); return 0
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
