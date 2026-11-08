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
            st = "passed" if others and all(o["status"] == "passed" for o in others) else \
                 "not_planned" if any(o["status"] == "not_planned" for o in others) and not any(o["status"] in ("failed", "blocked") for o in others) else \
                 "pending" if any(o["status"] == "pending" for o in others) else "failed"
            out.append(dict(c, status=st, why=None if st == "passed" else [o["id"] for o in others if o["status"] != "passed"], evidence=[])); continue
        if not ts:   # never dropped, never assumed: an unmeasured requirement blocks READY
            out.append(dict(c, status="not_planned", why=["NOT PLANNED: no task in this production measures this criterion"], evidence=[])); continue
        states = [t["state"] for t in ts]
        if c["id"] == "deployment":
            t = ts[0]; dep = t.get("deployment") or {}
            st = "passed" if t["state"] == "passed" and dep.get("verified") else "needs_approval" if t["state"] == "needs_approval" else \
                 "skipped" if t["state"] == "skipped" else "pending" if t["state"] in ("pending", "awaiting_agent", "in_progress") else "failed"
        elif all(s == "passed" for s in states): st = "passed"
        elif any(s == "failed" for s in states): st = "failed"
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
        out.append(dict(c, status=st, why=why or None, evidence=ev[:30]))
    return out


def verdict(acc):
    s = {a["id"]: a["status"] for a in acc}
    core = {k: v for k, v in s.items() if k != "deployment"}
    if not acc or any(v == "not_planned" for v in s.values()): return "NOT READY"
    if all(v == "passed" for v in core.values()):
        if s.get("deployment") in (None, "passed"): return "READY"
        return "READY — deployment " + s["deployment"].replace("_", " ")
    return "NOT READY"


def markdown(prod, release=False):
    acc = acceptance(prod)
    spec = prod["spec"]
    L = [f"# {'Release' if release else 'Production'} report — {spec['title']}", "",
         f"Production `{prod['id']}` · status **{prod.get('status')}** · verdict **{verdict(acc)}** · updated {store.now()}", "",
         f"> {spec['prompt'][:600]}", "",
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
