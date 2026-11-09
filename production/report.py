"""The acceptance report: every criterion from the spec, the evidence that decides it, and the verdict.

A criterion is `passed` only when every task that measures it passed (on its re-verification chain's latest
run); `failed`, `blocked`, `needs_approval` and `pending` say why not. Nothing is reported as done because a
tool returned: the report shows the measured values (scores, checks) next to each verdict."""
import os
from . import store


def _eff(prod, tid):
    t = prod["tasks"][tid]; seen = set()
    while t.get("superseded_by") and t["id"] not in seen: seen.add(t["id"]); t = prod["tasks"][t["superseded_by"]]
    return t


def acceptance(prod, exclude=()):
    roots_ = [i for i in prod["order"] if not prod["tasks"][i].get("reverifies") and not prod["tasks"][i].get("fix_for")]
    out = []
    for c in prod["spec"].get("acceptance", []):
        if c["id"] in exclude: continue
        ts = [_eff(prod, i) for i in roots_ if prod["tasks"][i].get("criterion") == c["id"]]
        if c["id"] == "release_ready":
            others = acceptance(prod, exclude={"release_ready", "deployment"})
            st = "passed" if others and all(o["status"] in PASSING for o in others) else \
                 "failed" if any(o["status"] == "failed" for o in others) else \
                 "not_planned" if any(o["status"] == "not_planned" for o in others) and not any(o["status"] in ("blocked", "unverified") for o in others) else \
                 "unverified" if any(o["status"] in ("blocked", "unverified") for o in others) else "pending"   # incomplete, not failed
            why = None if st == "passed" else [o["id"] for o in others if o["status"] not in PASSING]
            rel = [t for t in ts if t["state"] != "passed"]
            if st == "passed" and rel:   # the release gate itself must pass (e.g. evidence measured on the build released)
                r = rel[0]
                st = "blocked" if prod.get("unstable") or r["state"] == "blocked" else "pending" if r["state"] not in ("failed",) else "failed"
                why = [f"{r['id']}: {r['state']}" + (f" — {r.get('error') or r.get('reason')}" if r.get("error") or r.get("reason") else "")]
            out.append(dict(c, status=st, why=why, evidence=[])); continue
        if not ts:   # never dropped, never assumed: an unmeasured requirement blocks READY
            out.append(dict(c, status="not_planned", why=["NOT PLANNED: no task in this production measures this criterion"], evidence=[])); continue
        states = [t["state"] for t in ts]
        if c["id"] == "deployment":
            t = ts[0]; dep = t.get("deployment") or {}
            st = "passed" if t["state"] == "passed" and dep.get("verified") else "needs_approval" if t["state"] == "needs_approval" else \
                 "skipped" if t["state"] == "skipped" else "pending" if t["state"] in ("pending", "awaiting_agent", "in_progress") else "failed"
        elif all(s == "passed" for s in states): st = "passed"
        elif all(t.get("advisory") for t in ts) and all(s in ("passed", "skipped") or s == "failed" and not t.get("failure") for s, t in zip(states, ts)):
            st = "advisory"   # measured by advisory tasks only: their findings are recorded and never block (a crash measured nothing: not advisory)
        elif any(s == "failed" for s in states): st = "failed"
        elif any(s == "blocked" and t.get("unverified") for s, t in zip(states, ts)) and not any(s == "blocked" and not t.get("unverified") for s, t in zip(states, ts)):
            st = "passed" if _confirmed_live(prod, ts) else "unverified"   # the check ran but could not be completed (e.g. sandbox network)
        elif any(s == "blocked" and t.get("unavailable") for s, t in zip(states, ts)): st = "unavailable"   # a capability missing here, not a defect
        elif any(s == "blocked" for s in states): st = "blocked"
        elif any(s == "needs_approval" for s in states): st = "needs_approval"
        else: st = "pending"
        ev = []
        for t in ts:
            for g in t.get("gate_results") or []:
                ev.append({"task": t["id"], "condition": g["condition"], "ok": g["ok"], "measured": g.get("measured"), "detail": g.get("detail")})
            rec = (t.get("result") or {}).get("record")
            if rec: ev.append({"task": t["id"], "record": rec})
        why = [f"{t['id']}: {t['state']}" + (f" — {t.get('reason') or t.get('error')}" if (t.get('reason') or t.get('error')) else "") for t in ts if t["state"] != "passed"]
        if st == "passed" and any(t.get("unverified") for t in ts):
            why = None; ev.append({"condition": "verified independently in production (the live check reached every service the sandbox could not)", "ok": True})
        adv = [f"{ch['name']}: {str(ch.get('detail'))[:160]}" for t in ts for ch in ((t.get("result") or {}).get("checks") or []) if ch.get("category") == "advisory"]
        extra = {"cause": ", ".join(sorted({u.get("cause") or "unverified" for t in ts for u in t.get("unverified") or []}))} if st == "unverified" else {}
        if not c.get("required", True) and st not in ("passed", "advisory", "pending", "needs_approval"):
            # an optional criterion (a person made an implied extra optional) that ended without passing: listed, never a blocker
            why = [f"optional, not delivered ({st}): " + "; ".join(why or [])][:1]; st = "optional_missing"
        out.append(dict(c, status=st, why=why or None, evidence=ev[:30], advisories=adv[:12] or None, **extra))
    return out


PASSING = ("passed", "advisory", "optional_missing")   # optional_missing never blocks READY and is always listed (optional_not_delivered)


def optional_not_delivered(acc):
    return [a["id"] for a in acc if a["status"] == "optional_missing"]


def _confirmed_live(prod, ts):
    """An UNVERIFIED sandbox check is resolved only by independent production evidence: the live check (run with
    network, against the deployed release) reached every host the sandbox could not, and served this release."""
    hosts = {u.get("host") for t in ts for u in t.get("unverified") or []}
    if not hosts or None in hosts: return False
    from . import verification
    rec = verification.live_record(prod)
    if not rec or not (rec.get("deployment") or {}).get("serving"): return False
    return hosts <= set(rec.get("hosts_ok") or [])


INCOMPLETE_STATES = ("blocked", "pending", "needs_approval")


def verdict(acc):
    """READY (every criterion measured and passed), NOT READY (a criterion was measured and failed, or is NOT PLANNED),
    or INCOMPLETE (nothing failed, but a check could not run, could not be verified, or has not finished: blocked,
    unverified, pending, awaiting someone). An `advisory` criterion (measured by advisory tasks only) never blocks;
    an `unverified` one never reads as a failure and never as READY. The release status line, which also says
    whether the release is deployed, is verification.release_summary()."""
    s = {a["id"]: ("passed" if a["status"] in ("advisory", "optional_missing") else "blocked" if a["status"] in ("unverified", "unavailable") else a["status"]) for a in acc}
    core = {k: v for k, v in s.items() if k not in ("deployment", "release_ready")}
    if not acc or any(v == "not_planned" for v in s.values()): return "NOT READY"
    if all(v == "passed" for v in core.values()) and s.get("release_ready") in (None, "passed"):
        if s.get("deployment") in (None, "passed"): return "READY"
        return "READY — deployment " + s["deployment"].replace("_", " ")
    if any(v == "failed" for v in core.values()): return "NOT READY"
    if s.get("release_ready") == "failed" and all(v == "passed" for v in core.values()): return "NOT READY"   # the release gate itself failed
    return "INCOMPLETE"


def final(prod):
    """{verdict, reasons}: the verdict every run ends with, and in plain words why it is not READY."""
    acc = acceptance(prod)
    v = verdict(acc)
    reasons = []
    if prod.get("unstable"): reasons.append(prod["unstable"]["reason"])
    for a in acc:
        if a["status"] in PASSING or a["id"] == "release_ready" and any(x["status"] not in PASSING for x in acc if x["id"] not in ("release_ready", "deployment")): continue
        if a["id"] == "deployment" and v.startswith("READY"): continue
        label = {"failed": "failed", "blocked": "could not run", "unverified": "could not be verified (not an application failure)", "pending": "did not finish", "needs_approval": "waiting for a person",
                 "not_planned": "not planned", "skipped": "skipped",
                 "unavailable": "cannot run here (a capability is missing; not an application failure)"}.get(a["status"], a["status"])
        reasons.append(f"{a['id']} {label}: " + "; ".join(map(str, a.get("why") or []))[:400])
    for t in prod.get("tasks", {}).values():
        if t["state"] == "awaiting_agent" and not t.get("superseded_by"):
            reasons.append(f"{t['id']} is waiting for the agent's work order ({t.get('work_order_path')})")
    if v == "NOT READY" and not reasons: reasons.append("not every acceptance criterion passed")
    return {"verdict": v, "reasons": reasons}


def markdown(prod, release=False):
    acc = acceptance(prod)
    spec = prod["spec"]
    L = [f"# {'Release' if release else 'Production'} report — {spec['title']}", "",
         f"Production `{prod['id']}` · status **{prod.get('status')}** · verdict **{verdict(acc)}** · updated {store.now()}", "",
         *([f"Evaluation target: {(prod.get('evaluation') or {}).get('why')}", ""] if prod.get("evaluation") else []),
         f"> {spec['prompt'][:600]}", "",
         *([f"Production Report: `{(prod.get('production_report') or {}).get('html')}` (overall {(prod.get('production_report') or {}).get('overall')}, "
            f"method {(prod.get('production_report') or {}).get('method')})", ""] if (prod.get("production_report") or {}).get("status") == "ok" and not release else []),
         f"Deliverable: **{spec['deliverable']}** ({spec['dimension']}, {'mobile-first' if spec['platform']['mobile_first'] else 'desktop + phone'}) · "
         f"project `{spec['project']['path']}` · quality bar **{spec['quality']['level']}**", ""]
    bp = prod.get("blueprint")
    if bp or prod.get("lifecycle"):
        from . import lifecycle
        lv = lifecycle.summary(prod)
        L += ["## Where it stands", "", f"**{lv['stage']}** — {lv['summary']}", ""]
        if bp:
            L.append(f"Blueprint v{bp.get('version', 1)} approved {bp.get('approved_at')} (`{bp.get('hash')}`): "
                     + "; ".join(f"{d['title']}: **{d['answer']}**" for d in bp.get("decisions") or []))
            L.append("")
        if prod.get("recon"): L += [f"Recon ({prod['recon']['depth']}): **{prod['recon']['recommendation'].get('verdict')}** — `{prod['recon'].get('report')}`", ""]
    from . import verification
    L += verification.markdown(verification.release_summary(prod, acc))
    fin = final(prod)
    if fin["reasons"]: L += [f"## Why {fin['verdict']}", ""] + [f"- {r}" for r in fin["reasons"]] + [""]
    miss = [x for x in acc if x["status"] == "optional_missing"]
    if miss: L += ["## Optional, not delivered", "", "Made optional by a person in the Decision Room; the release does not wait for them, and they are never hidden:", ""] + \
                  [f"- {x['id']}: {'; '.join(map(str, x.get('why') or []))[:300]}" for x in miss] + [""]
    from . import qa
    L += qa.markdown(prod)
    L += ["## Acceptance criteria", "", "| Criterion | Status | Evidence |", "|---|---|---|"]
    for a in acc:
        seen = {}
        for e in a["evidence"]:
            if "condition" not in e: continue
            k = (e["condition"], e["ok"], str(e.get("measured")) if e.get("measured") not in (None, "") else None)
            seen[k] = seen.get(k, 0) + 1
        ev = "; ".join(f"{c}: {'✓' if ok else '✗'}" + (f" ({m})" if m else "") + (f" ×{n}" if n > 1 else "") for (c, ok, m), n in seen.items())[:400]
        if a.get("why") and a["status"] != "passed": ev = (ev + " · " if ev else "") + "; ".join(map(str, a["why"]))[:300]
        L.append(f"| {a['text']} | **{a['status']}** | {ev or '—'} |")
    L += ["", "## Tasks", "", "| Task | Owner | State | Attempts | Note |", "|---|---|---|---|---|"]
    for tid in prod["order"]:
        t = prod["tasks"][tid]
        note = t.get("reason") or t.get("error") or ""
        if t.get("superseded_by"): note = f"superseded by {t['superseded_by']}" + (f" — {note}" if note else "")
        L.append(f"| `{tid}` | {t['owner']} | {t['state']} | {len(t['attempts'])} | {str(note)[:160].replace('|', '/')} |")
    rem = [t for t in prod["tasks"].values() if t.get("fix_for")]
    if rem:
        L += ["", "## Remediation", ""]
        for t in rem:
            L.append(f"- `{t['id']}` (for `{t['fix_for']}`): **{t['state']}** — " + "; ".join((t.get("work_order") or {}).get("findings", [])[:4])[:400])
    blk = [t for t in prod["tasks"].values() if t["state"] in ("blocked", "needs_approval")]
    if blk:
        L += ["", "## Blockers and approvals", ""]
        for t in blk:
            L.append(f"- `{t['id']}` **{t['state']}**: {t.get('reason')}" + (f" · install: {', '.join(t['install'])}" if t.get("install") else ""))
    if spec.get("assumptions"): L += ["", "## Assumptions made at intake", ""] + [f"- {a}" for a in spec["assumptions"]]
    if prod.get("decisions"): L += ["", "## Decisions", ""] + [f"- {d}" for d in prod["decisions"]]
    L += ["", "## Provenance", "", "Every department output has a `.studio.json` record (request, tools and licences, SHA-256 of each file);",
          f"hand-offs are in `{os.path.join(prod['store'], 'handoffs')}`; the full event log is `events.jsonl`.", ""]
    return "\n".join(L) + "\n"


def write(prod):
    p = os.path.join(prod["store"], "REPORT.md")
    with open(p, "w") as f: f.write(markdown(prod))
    return p


def work_order_md(o):
    L = [f"# Work order: {o['title']}", "", f"Production `{o['production']}` · task `{o['task']}` · owner {o['owner']}", "",
         f"Project: `{o['project']}`  ", f"Write task files to: `{o['out_dir']}`", ""]
    if o.get("brief"): L += ["## Brief", "", o["brief"], ""]
    if o.get("findings"): L += ["## Findings to fix", ""] + [f"- {f}" for f in o["findings"]] + [""]
    if o.get("instructions"): L += ["## Instructions", ""] + [f"{i}. {x}" for i, x in enumerate(o["instructions"], 1)] + [""]
    if o.get("tools"): L += ["## Tools", ""] + [f"- {x}" for x in o["tools"]] + [""]
    if o.get("expected"): L += ["## Expected outputs (validated on submit)", ""] + [f"- `{e['path']}` ({e.get('format')})" + (f", keys {e['keys']}" if e.get("keys") else "") for e in o["expected"]] + [""]
    ia = (o.get("handoff") or {}).get("integrated_assets")
    if ia: L += ["## Integrated assets (use every one)", ""] + [f"- `{a['dest_rel']}` — {a['role']} from `{a['task']}`" for a in ia] + [""]
    L += ["## Submit", "", f"`{o['submit']}`", ""]
    return "\n".join(L)
