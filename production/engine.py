"""The production engine: plan once, then run until the deliverable is genuinely ready or a real blocker remains.

  plan(prompt, project)    intake → discovery → planner → validation; persisted as a new production
  run(id)                  schedule every ready task (dependencies passed, resources free) on parallel workers;
                           retry execution failures, never retry bad requests, block dependents of what failed;
                           a failed QA gate spawns a fix work order + a re-verification of the modified project
                           (up to quality.max_rounds); stops when nothing more can progress without someone
  submit(id, task, ...)    the agent hands back a work order's result; it is validated before it counts
  approve(id, task, ...)   a person's decision on something that needs approval (deploy, replacing assets)
  status(id) / report(id)  where every task stands; the acceptance report

Resuming is the same call as running: a task interrupted mid-run starts again, a passed task is reused only
while its outputs still exist with the hashes it recorded, and QA evidence is re-measured when the project
changed after it passed (checked by a fingerprint of the project's files before release).

Evaluation never feeds itself (production/artifacts.py): the store is kept outside the evaluated project, the
fingerprint skips every evaluation artifact, every browser check measures one target chosen by the
source-vs-build policy, re-measurement is bounded (STALE_ROUNDS), and every run ends with a verdict:
READY, NOT READY, or INCOMPLETE with the reasons the evaluation could not finish."""
import concurrent.futures as cf, copy, hashlib, json, os, sys, threading, time, traceback
from . import PENDING, IN_PROGRESS, AWAITING_AGENT, COMPLETE, PASSED, FAILED, BLOCKED, NEEDS_APPROVAL, SKIPPED, TERMINAL, VERSION
from . import inside_roots, roots, store_root, store_root_for
from . import intake, discovery, planner, executors, builtins, gates, store, report as _report
from . import lifecycle, recon, icons, maturity, artifacts

RESOURCES = {"browser": 2, "blender": 1, "exclusive": 1, "integration": 1}   # integration: one writer of the asset manifest at a time (plan v2)
# "exclusive": a timing measurement (frame rate) is only valid with the machine to itself, so such a task starts
# only when nothing else runs, and nothing else starts while it runs
FINGERPRINT_SKIP = artifacts.VCS_AND_CACHE   # plus every evaluation artifact folder (artifacts.is_artifact_dir)
# without an agent submission in between, the project should not change while it is evaluated: after this many
# automatic re-measurements the evaluation stops re-measuring and ends INCOMPLETE, naming what kept changing
STALE_ROUNDS = 2


# ---------------------------------------------------------------- helpers
def fingerprint(project, exclude=()):
    """SHA-256 over every source file in the project (path + content hash): what a QA measurement was taken on.
    Evaluation artifacts (gitcraft-out/, marked folders, the production store) are not source and never count."""
    return artifacts.digest(artifacts.snapshot(project, exclude))


def _fp(prod):
    """The project's fingerprint now; its file list is kept in the store so a later change can be named."""
    snap = artifacts.snapshot(_project(prod), [prod.get("store")])
    fp = artifacts.digest(snap)
    if fp:
        p = os.path.join(prod["store"], "snapshots", fp + ".json")
        if not os.path.exists(p): store.write_json(p, snap)
    return fp


def _changed_since(prod, fp):
    try: was = json.load(open(os.path.join(prod["store"], "snapshots", fp + ".json")))
    except (OSError, ValueError, TypeError): return []
    return artifacts.diff(was, artifacts.snapshot(_project(prod), [prod.get("store")]))


def eff(prod, tid):
    """A task's effective version: the end of its re-verification chain."""
    t = prod["tasks"][tid]; seen = set()
    while t.get("superseded_by") and t["id"] not in seen:
        seen.add(t["id"]); t = prod["tasks"][t["superseded_by"]]
    return t


def _dep_state(prod, tid):
    t = eff(prod, tid)
    if t["state"] == PASSED or (t.get("advisory") and t["state"] in TERMINAL): return "ok"
    if t["state"] in (FAILED, BLOCKED, SKIPPED): return "dead"
    return "wait"


def _set(prod, t, state, **info):
    old = t["state"]; t["state"] = state; t["updated"] = store.now()
    if old != state:   # notes belong to the state they explain
        for k in ("reason", "error", "failure", "blocked_by"):
            if k not in info: t.pop(k, None)
    for k, v in info.items(): t[k] = v
    if old != state: store.event(prod, "task", task=t["id"], state=state, was=old, **{k: v for k, v in info.items() if k in ("reason", "error", "blocked_by", "failure")})


def _project(prod): return prod["spec"]["project"]["path"]


def _task_dir(prod, tid):
    return store.task_dir(prod, tid)   # outside the evaluated project, whatever store the production record sits in


def _hex_rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


class HandoffError(Exception): pass


class TargetMissing(Exception): pass


def eval_target(prod):
    """The one folder every browser check measures (artifacts.target_policy), or TargetMissing with the reason."""
    pol = prod.get("evaluation") or artifacts.target_policy(prod["spec"], _project(prod))
    d, why = artifacts.resolve_target(_project(prod), pol)
    if not d: raise TargetMissing(why)
    return d


def resolve(prod, v):
    if v == "$target": return eval_target(prod)
    if isinstance(v, str) and v.startswith("$project"): return _project(prod) + v[len("$project"):]
    if isinstance(v, dict) and "$from" in v:
        if v["$from"] not in prod["tasks"]:   # a stale reference (e.g. to a replaced check): a hand-off error, never a crash
            raise HandoffError(f"{v['$from']} is not a task in this plan, so it has nothing to hand on")
        src = eff(prod, v["$from"])
        outs = builtins.select(src.get("outputs", []), [v.get("role", "*")], [v["format"]] if v.get("format") else None)
        if not outs: raise HandoffError(f"{v['$from']} produced no {v.get('role', '*')} output to hand on")
        if v.get("json"):
            data = json.load(open(outs[0]["path"]))
            val = data.get(v["json"])
            if val is None: raise HandoffError(f"{outs[0]['path']} has no {v['json']!r}")
            return _hex_rgb(val) if v.get("as") == "rgb" else val
        return [o["path"] for o in outs] if v.get("all") else outs[0]["path"]
    if isinstance(v, dict): return {k: x for k, x in ((k, resolve(prod, x)) for k, x in v.items()) if x is not None}
    if isinstance(v, list): return [resolve(prod, x) for x in v]
    return v


def _upstream(prod, t):
    out = []
    for d in t["depends_on"]:
        e = eff(prod, d)
        out.append({"id": e["id"], "state": e["state"], "ship": e.get("ship"), "outputs": e.get("outputs", []), "result": e.get("result"), "owner_task": e.get("rework_of") or e["id"],
                    "license": (e.get("result") or {}).get("output_license") or (e.get("work_order") or {}).get("license"),
                    "attribution": (e.get("result") or {}).get("attribution")})
    return out


def _handoff(prod, t, params):
    h = {"task": t["id"], "params": params, "upstream": [{"task": u["id"], "state": u["state"],
         "outputs": [{k: o.get(k) for k in ("path", "role", "format", "sha256")} for o in u["outputs"]]} for u in _upstream(prod, t)]}
    store.write_json(os.path.join(prod["store"], "handoffs", t["id"] + ".json"), h)
    return h


def _norm_outputs(res):
    base = res.get("out_dir") or ""
    outs = []
    for o in res.get("outputs") or []:
        p = o["path"] if os.path.isabs(o["path"]) else os.path.join(base, o["path"])
        outs.append({"path": p, "role": o.get("role"), "format": o.get("format"), "ok": o.get("ok", True), **({"rel": o["rel"]} if o.get("rel") else {}),
                     "sha256": o.get("sha256") or (builtins.sha256(p) if os.path.isfile(p) else None)})
    return outs


def _forge_outputs(r):
    """A finished ForgeCraft job as outputs the next department can take: its exports, from the hash-verified copy in
    the task's own folder (the hand-off) when there is one, else from the library. Without these, a model never
    reaches AnimCraft or the integration manifest."""
    if r.get("outputs"): return r
    files, base = r.get("files") or {}, r.get("handoff")
    outs = []
    for rel, lib_path in files.items():
        p = os.path.join(base, rel) if base and os.path.isfile(os.path.join(base, rel)) else lib_path
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        outs.append({"path": p, "role": "source" if ext == "blend" else "model", "format": ext})
    asset = r.get("asset") or {}
    return dict(r, outputs=outs, asset_id=asset.get("id"), asset_version=asset.get("version"))


def _slim(res):
    """What the production record keeps of a department result (the full record stays in its .studio.json)."""
    drop = {"outputs", "stages", "request", "tools", "dependencies", "stderr", "catalog"}
    return {k: v for k, v in res.items() if k not in drop}


# ---------------------------------------------------------------- the lifecycle: idea → recon → discovery → decisions → approved
def idea(text, project=None, overrides=None, store_dir=None, source=None):
    """Save an idea (any size: a sentence to a master prompt, a GitHub URL, a project folder). Nothing is read or built."""
    spec = intake.parse(text, project, overrides)
    if not spec["project"]["path"] and spec["deliverable"] in ("game", "app", "site"):
        spec["project"]["path"] = os.path.join(roots()[0], store.slugify(spec["title"]))
    p = spec["project"]["path"]
    if p and not inside_roots(p):
        raise PermissionError(f"GITCRAFT policy: project {p} is outside the workspace roots ({':'.join(roots())})")
    prod = {"id": store.new_id(spec["title"]), "spec": spec, "brief": lifecycle.brief(text, p, source), "overrides": overrides or {},
            "tasks": {}, "order": [], "decisions": [], "parallel_groups": [], "problems": [], "status": "idea", "plan_version": planner.PLAN_VERSION}
    lifecycle.move(prod, "idea")
    why = None
    if not store_dir: store_dir, why = store_root_for(p)
    if why: prod["decisions"].append(f"evaluation output isolated from the project: {why}")
    store.create(prod, store_dir)
    return prod


def plan(prompt, project=None, overrides=None, store_dir=None, recon=None, assessment=None):
    """New Build: idea → (optional Recon) → read-only Discovery → the Decision Room. Building waits for decide(approve).
    An existing project (entry.start) arrives with its maturity assessment and is planned in its workflow's mode."""
    prod = idea(prompt, project, overrides, store_dir)
    if assessment and assessment.get("existing"):
        prod["maturity"] = assessment; store.save(prod)
    if recon: return start_recon(prod["id"], recon, store_dir=store_dir)
    return promote(prod["id"], store_dir=store_dir)


def _discover_and_plan(prod):
    """Read-only Discovery and planning into an existing record. Never writes to the project."""
    spec = intake.parse(prod["spec"]["prompt"], prod["spec"]["project"]["path"] if prod["spec"]["project"].get("path") else None, prod.get("overrides") or None)
    if not spec["project"]["path"]: spec["project"]["path"] = prod["spec"]["project"]["path"]
    p = spec["project"]["path"]
    spec["project"]["exists"] = bool(p and os.path.isdir(p))
    if prod.get("recon"): spec["recon"] = {k: prod["recon"].get(k) for k in ("depth", "at")} | {"verdict": (prod["recon"].get("recommendation") or {}).get("verdict")}
    lifecycle.move(prod, "discovery")
    disc = discovery.run(spec)
    existing = bool(spec.get("mode", {}).get("existing"))
    if existing and not prod.get("maturity"): prod["maturity"] = maturity.assess(p)
    icon_state = icons.inspect(p) if (spec.get("icon", {}).get("required") or existing) else {"status": "n/a"}
    if spec.get("icon", {}).get("required") and not spec["icon"].get("mode"):
        spec["icon"]["mode"] = "keep" if icon_state["status"] == "candidate" else "new"
        spec["icon"]["existing"] = icon_state.get("best")
    essential = [q for q in spec["questions"] if q.get("essential")]
    if spec.get("mode", {}).get("question") and not spec["mode"].get("request"): essential.append({"id": "request"})
    pl = planner.build(spec, disc, version=prod.get("plan_version", 1))   # a record keeps the graph version it was created with
    # Every acceptance criterion from the intake stays in the spec. One that no planned task measures is reported
    # `not_planned`: it is visible in the plan and the report, and it prevents READY (the release gate fails on it).
    measured = {t.get("criterion") for t in pl["tasks"].values()}
    have = {c["id"] for c in spec["acceptance"]}
    for cid, text in (("asset_integrity", "Every integrated asset opens as its format and is referenced by the build"),
                      ("licensing", "Every shipped asset has a recorded licence; nothing non-commercial or no-derivatives"),
                      ("request_fulfilled", "Product QA: the finished product delivers what was asked (every requested feature shows in the build); "
                                            "unrequested additions and coherence suggestions are listed, never blocking")):
        if cid in measured and cid not in have:   # planning may add criteria (the project's existing assets), never remove one
            spec["acceptance"].insert(-1, {"id": cid, "text": text, "measured_by": "qa.request" if cid == "request_fulfilled" else "planning: the project has assets",
                                           "required": True, "source": "standard"})
    unmeasured = [c["id"] for c in spec["acceptance"] if c["id"] not in measured and c["id"] != "release_ready"]
    problems = planner.validate(pl, disc) + [f"optional_criteria: {c} was named in the prompt or is a GITCRAFT release standard, so it stays required "
                                             "(only extras GITCRAFT added can be made optional)" for c in spec.get("optional_refused") or []]
    # an existing project may already carry an asset manifest from the production that made it: those entries are the project's,
    # not this production's. Recorded once, before anything is integrated, so the manifest checks expect them unchanged
    if "inherited_assets" not in prod: prod["inherited_assets"] = _manifest_now(p)
    if "qa.preserve" in pl["tasks"]:   # the baseline lives in the production store; the project is only read
        bp = os.path.join(prod["store"], "baseline.json")
        if not os.path.exists(bp): store.write_json(bp, maturity.baseline(p))
        pl["tasks"]["qa.preserve"]["params"]["baseline"] = bp
    pol = artifacts.target_policy(spec, p)
    pl["decisions"].append(f"evaluation target: {'the built app ' + pol['dir'] + '/' if pol['chosen'] == 'build' else 'the project source'} ({pol['why']})")
    prod.update({"evaluation": pol, "spec": spec, "discovery": disc, "icon_state": icon_state, "tasks": pl["tasks"], "order": pl["order"],
                 "decisions": pl["decisions"], "parallel_groups": pl["parallel_groups"], "problems": problems,
                 "readiness": planner.readiness(pl, disc), "unmeasured_criteria": unmeasured,
                 "warnings": [f"acceptance criterion {c} is not measured by any planned task: it will report NOT PLANNED and the "
                              "production cannot be READY (plan the task, or drop the requirement from the spec with overrides)" for c in unmeasured],
                 "status": "planned" if not problems and not essential else "needs_input"})
    answered = {d["id"]: d for d in prod.get("decision_room") or [] if d.get("answer") is not None}
    room = lifecycle.decisions(spec, disc, icon_state)
    for d in room:
        if d["id"] in answered: d.update(answer=answered[d["id"]]["answer"], status=answered[d["id"]]["status"])
    prod["decision_room"] = room
    lifecycle.move(prod, "decisions")
    prod["discovery_report"] = lifecycle.discovery_report(prod)
    return prod


def promote(pid, overrides=None, store_dir=None):
    """An idea (saved, recon'd or parked) becomes a build: read-only Discovery, then the Decision Room."""
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        st = lifecycle.stage(prod)
        if st not in ("idea", "recon", "parked", "decisions"):
            raise ValueError(f"{pid} is at {st}: only an idea (or one still in the Decision Room) can be promoted; use production_revise to change an approved blueprint")
        if overrides: prod["overrides"] = intake.merge(prod.get("overrides") or {}, overrides)
        if st == "recon": prod.setdefault("lifecycle", {})["recon_skipped"] = True
        _discover_and_plan(prod)
        store.save(prod)
        store.event(prod, "planned", tasks=len(prod["tasks"]), problems=prod["problems"] or None, blocked_up_front=list(prod["readiness"]) or None,
                    decisions=len(prod["decision_room"]))
    return prod


def start_recon(pid, depth="quick", store_dir=None):
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        if lifecycle.stage(prod) not in ("idea", "parked", "recon"): raise ValueError(f"recon runs on an idea, and {pid} is at {lifecycle.stage(prod)}")
        order = recon.order(prod, depth)
        d = os.path.join(prod["store"], "recon"); os.makedirs(d, exist_ok=True)
        store.write_json(os.path.join(d, "work_order.json"), order)
        prod["recon_order"] = order; lifecycle.move(prod, "recon", note=depth)
        store.save(prod); store.event(prod, "recon_started", depth=depth)
    return dict(lifecycle_view(prod), recon_order=order)


def submit_recon(pid, findings, store_dir=None):
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        if lifecycle.stage(prod) != "recon": raise ValueError(f"{pid} has no Recon waiting (stage {lifecycle.stage(prod)}): start one with production_recon {{depth}}")
        depth = prod["recon_order"]["depth"]
        checks = recon.validate(findings, depth)
        ok = all(c["ok"] for c in checks)
        if ok:
            rec = {"depth": depth, "at": store.now(), "findings": findings, "recommendation": findings["recommendation"]}
            p = os.path.join(prod["store"], "recon", "RECON.md")
            with open(p, "w") as f: f.write(recon.markdown(prod["spec"]["title"], rec))
            store.write_json(os.path.join(prod["store"], "recon", "findings.json"), findings)
            rec["report"] = p; prod["recon"] = rec
            lifecycle.move(prod, "idea", note=f"recon {depth}: {findings['recommendation']['verdict']}")
        store.save(prod); store.event(prod, "recon_submitted", accepted=ok)
    return dict(lifecycle_view(prod), recon_accepted=ok, checks=[c for c in checks if not c["ok"]] or "all passed",
                next="production_promote to build it, production_discard {park: true} to park it" if ok else "fix the findings and submit again")


def discard(pid, park=False, reason=None, store_dir=None):
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        if lifecycle.stage(prod) not in ("idea", "recon", "decisions", "parked"):
            raise ValueError(f"{pid} is at {lifecycle.stage(prod)}: an approved build is not discarded from here")
        lifecycle.move(prod, "parked" if park else "discarded", note=reason); prod["status"] = "parked" if park else "discarded"
        store.save(prod); store.event(prod, "parked" if park else "discarded", reason=reason)
    return lifecycle_view(prod)


def decide(pid, answers=None, approve=False, note=None, store_dir=None):
    """The Decision Room: answer decisions (a changed answer re-plans, read-only), and approve the blueprint.
    With a material revision pending, approve applies it (preserving finished work) and declines discard it."""
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        lc = prod.setdefault("lifecycle", {"history": []})
        if lc.get("revision"):
            rv = lc["revision"]
            if approve:
                if rv.get("problems"):   # same rule as the first approval: a plan with problems cannot be approved
                    raise ValueError("the revision's plan has problems; send a corrected production_revise (or decline this one): " + "; ".join(rv["problems"][:4]))
                _apply_revision(prod, rv["overrides"])
                if prod.get("blueprint"): prod.setdefault("blueprint_history", []).append(prod["blueprint"])   # every approved version is kept
                prod["blueprint"] = dict(lifecycle.blueprint(prod), version=(prod.get("blueprint") or {}).get("version", 1) + 1, revision=rv)
                prod.setdefault("decisions", []).append(f"approved revision: {rv['reason']} ({', '.join(rv['changed'])})")
                store.event(prod, "revision_approved", changed=rv["changed"])
            else:
                prod.setdefault("decisions", []).append(f"declined revision: {rv['reason']}" + (f" — {note}" if note else ""))
                store.event(prod, "revision_declined")
            prod["lifecycle"].pop("revision", None); prod["status"] = overall(prod) if any(t.get("attempts") for t in prod["tasks"].values()) else "planned"
            store.save(prod); return lifecycle_view(prod)
        st = lifecycle.stage(prod)
        if st not in ("decisions",):
            raise ValueError(f"{pid} is at {st}: the Decision Room is open only before approval (use production_revise for a change after it)")
        if answers:
            room = {d["id"]: d for d in prod["decision_room"]}
            unknown = [k for k in answers if k not in room]
            if unknown: raise ValueError(f"no decision {unknown} (decisions: {sorted(room)})")
            ov = lifecycle.overrides_for(prod["decision_room"], answers)
            for k, v in answers.items(): room[k].update(answer=v, status="answered")
            if ov:
                prod["overrides"] = intake.merge(prod.get("overrides") or {}, ov)
                _discover_and_plan(prod)
            store.event(prod, "decisions_answered", answers=answers)
        if approve:
            if prod.get("problems"): raise ValueError("the plan has problems; correct them (answers or production_revise) before approving: " + "; ".join(prod["problems"][:4]))
            open_q = [d["id"] for d in prod["decision_room"] if d["kind"] == "question" and "essential" in (d.get("why") or "") and d.get("answer") is None]
            if open_q: raise ValueError(f"essential questions need an answer first: {open_q}")
            if any(d["id"] == "scope" and d.get("answer") == "revise" for d in prod["decision_room"]):
                raise ValueError("the scope is marked for revision: send production_revise with the change, then approve")
            # approving the recommendations means applying them: a default that differs from the plan re-plans first
            pending = {d["id"]: d["recommended"] for d in prod["decision_room"] if d.get("answer") is None and d["kind"] == "choice"
                       and d["recommended"] in [o["value"] for o in d["options"]]}
            ov = lifecycle.overrides_for(prod["decision_room"], pending)
            for d in prod["decision_room"]:
                if d.get("answer") is None: d.update(answer=d["recommended"], status="approved (recommended)")
            if ov and lifecycle.material(prod["spec"], intake.merge(prod["spec"], ov)):
                prod["overrides"] = intake.merge(prod.get("overrides") or {}, ov)
                _discover_and_plan(prod)
                if prod.get("problems"): raise ValueError("the recommended defaults produce a plan with problems: " + "; ".join(prod["problems"][:4]))
                for d in prod["decision_room"]:
                    if d.get("answer") is None: d.update(answer=d["recommended"], status="approved (recommended)")
            for d in prod["decision_room"]:
                if d["status"] != "approved (recommended)": d["status"] = "approved"
            prod["blueprint"] = dict(lifecycle.blueprint(prod), version=1, note_from_person=note)
            prod.setdefault("decisions", []).append("blueprint approved" + (f" — {note}" if note else ""))
            lifecycle.move(prod, "approved"); prod["status"] = "planned"; lc["stage"] = None
            store.event(prod, "blueprint_approved", hash=prod["blueprint"]["hash"])
        store.save(prod)
    return lifecycle_view(prod)


DECISION_HISTORY = ("approved revision:", "declined revision:", "non-material revision applied:", "evaluation output isolated")
TASK_DEF = ("kind", "department", "action", "params", "depends_on", "ship", "work_order", "gate", "criterion")


def _apply_revision(prod, overrides):
    """Re-plan with the revision, keeping every task whose definition did not change (passed work is not redone)."""
    old = prod["tasks"]
    prod["overrides"] = intake.merge(prod.get("overrides") or {}, overrides)
    keep_lc = copy.deepcopy(prod.get("lifecycle")); room = copy.deepcopy(prod.get("decision_room"))
    # what people decided (approved, declined or applied revisions; isolation notes) is history: re-planning regenerates the
    # planning notes but never drops these
    history = [d for d in prod.get("decisions") or [] if d.startswith(DECISION_HISTORY)]
    _discover_and_plan(prod)
    prod["lifecycle"] = keep_lc; prod["decision_room"] = room
    prod["decisions"] = history + [d for d in prod["decisions"] if d not in history]
    new, order, dropped = prod["tasks"], [], []
    for tid in list(prod["order"]):
        n = new[tid]; o = old.get(tid)
        if o and all(json.dumps(o.get(k), sort_keys=True) == json.dumps(n.get(k), sort_keys=True) for k in TASK_DEF):
            new[tid] = o
        order.append(tid)
        chain = [x for x in old.values() if x.get("chain") == tid]   # its remediation history stays with it
        if new[tid] is o:
            for x in sorted(chain, key=lambda x: (x.get("round") or 0, 0 if x["id"].startswith("fix.") else 1)):
                new[x["id"]] = x; order.append(x["id"])
    for tid, o in old.items():
        if tid not in new and not o.get("chain"): dropped.append(tid)
    prod["order"] = order
    changed = {t for t in order if t in old and new[t] is not old[t]}
    for t in [new[x] for x in order]:   # anything downstream of a changed task is redone
        if t["state"] != PENDING and any(d in changed or (new.get(d) and new[d]["state"] == PENDING and d in old and new[d] is not old[d]) for d in t["depends_on"]):
            _invalidate(prod, t, "the approved revision changed something it depends on")
    if dropped: prod.setdefault("decisions", []).append(f"revision removed: {', '.join(dropped)}")


def _revision_effect(prod, overrides):
    """What a pending revision would do to the acceptance criteria, shown to the person before they approve it:
    criteria no task would measure any more (NOT PLANNED: the production could not be READY), criteria it would start
    measuring, and plan problems (e.g. a `replaces` that is not the same check). Planned on a copy in a scratch
    folder: the production and its store are not touched."""
    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="gitcraft-revision-")
    try:
        trial = copy.deepcopy(prod); trial["store"] = tmp
        before = set(prod.get("unmeasured_criteria") or [])
        _apply_revision(trial, overrides)
        after = set(trial.get("unmeasured_criteria") or [])
        return {"unmeasured_after": sorted(after), "would_lose": sorted(after - before), "would_measure": sorted(before - after),
                "problems": trial.get("problems") or []}
    except Exception as e:   # the preview never blocks a revision; the approved plan is validated when it is applied
        return {"preview_error": f"{type(e).__name__}: {e}"}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def revise(pid, overrides, reason, store_dir=None):
    """Change the plan. Before approval it re-plans; after, a material deviation pauses the build until it is approved."""
    if not reason: raise ValueError("say why the plan changes (reason)")
    prod = store.load(pid, store_dir)
    st = lifecycle.stage(prod)
    if st in ("idea", "recon", "parked", "decisions"):
        return lifecycle_view(promote(pid, overrides=overrides, store_dir=store_dir))
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        new = intake.parse(prod["spec"]["prompt"], prod["spec"]["project"]["path"], intake.merge(prod.get("overrides") or {}, overrides))
        for k in ("icon", "project"):   # resolved at discovery
            if k not in overrides: new[k] = copy.deepcopy(prod["spec"].get(k))
        changed = lifecycle.material(prod["spec"], new)
        if not changed:
            _apply_revision(prod, overrides)
            prod.setdefault("decisions", []).append(f"non-material revision applied: {reason}")
            store.event(prod, "revision_applied", material=False)
        else:
            prod["lifecycle"]["revision"] = {"overrides": overrides, "reason": reason, "changed": changed, "at": store.now(),
                                             **_revision_effect(prod, overrides)}
            prod["status"] = "paused"
            store.event(prod, "revision_requested", changed=changed, reason=reason)
        store.save(prod)
    return dict(lifecycle_view(prod), material=changed or None,
                next="a person approves or declines the change (production_decide approve=true|false)" if changed else "production_run")


def lifecycle_view(prod):
    v = lifecycle.summary(prod)
    out = {"production": prod["id"], "title": prod["spec"]["title"], "stage": v["stage"], "summary": v["summary"], "status": prod.get("status"),
           "store": prod["store"]}
    if v["stage"] == "decisions" or (prod.get("lifecycle") or {}).get("revision"):
        out["decision_room"] = [{k: d.get(k) for k in ("id", "title", "question", "recommended", "options", "why", "answer", "status")} for d in prod.get("decision_room") or []]
        out["discovery_report"] = prod.get("discovery_report")
        if (prod.get("lifecycle") or {}).get("revision"): out["revision"] = prod["lifecycle"]["revision"]
    if prod.get("blueprint"): out["blueprint"] = {k: prod["blueprint"].get(k) for k in ("status", "version", "hash", "approved_at")}
    if prod.get("recon"): out["recon"] = {"depth": prod["recon"]["depth"], "verdict": prod["recon"]["recommendation"].get("verdict"), "report": prod["recon"].get("report")}
    return out


# ---------------------------------------------------------------- run
def _recover(prod):
    """Make a resumed production consistent: interrupted tasks restart; passed work is reused only if intact."""
    for t in prod["tasks"].values():
        if t["kind"] == "builtin" and t.get("action") == "integrate" and (t.get("params") or {}).get("v2"):
            undone = builtins.integrate_recover(_task_dir(prod, t["id"]))   # an interrupted commit leaves the previous valid state
            if undone: store.event(prod, "integration_rolled_back", task=t["id"], actions=undone[:20])
        if t["state"] in (IN_PROGRESS, COMPLETE) and t["kind"] != "agent":
            if t["attempts"] and not t["attempts"][-1].get("finished"):
                t["attempts"][-1].update(finished=store.now(), status="interrupted")
            _set(prod, t, PENDING, reason="interrupted: the run stopped while this task was running; it runs again")
    _release_built(prod)
    # department artifacts live in the production store and must still be what passed; files in the project
    # (the build, integrated copies) legitimately change under remediation: their freshness is the release's
    # fingerprint check, not this one
    owned = tuple({os.path.realpath(prod["store"]) + os.sep, os.path.realpath(store.output_root(prod, create=False)) + os.sep})
    for t in list(prod["tasks"].values()):
        if t["state"] != PASSED: continue
        bad = [o["path"] for o in t.get("outputs", []) if o.get("sha256") and os.path.realpath(o["path"]).startswith(owned)
               and (not os.path.isfile(o["path"]) or builtins.sha256(o["path"]) != o["sha256"])]
        if bad: _invalidate(prod, t, f"outputs missing or changed since they passed: {', '.join(os.path.basename(b) for b in bad[:4])}")


def _blocked_on_target(prod, t):
    """Blocked only because the evaluation target was missing (the app was not built). Productions recorded before
    the reason was kept are recognised by what they were told to run: the build command and nothing else."""
    if t["state"] != BLOCKED or t.get("blocked_by"): return False
    if t.get("blocked_on") == "target": return True
    cmd = (prod.get("evaluation") or {}).get("build_command")
    return bool(cmd) and t.get("blocked_on") is None and t.get("install") == [cmd]


def _release_built(prod):
    """A check that was blocked because the app was not built runs again once it is. Its message says "run the build,
    then run again", so running again has to do it: nothing was measured, so there is nothing to protect, and without
    this the only way forward was a plan revision that swapped the check for a copy of itself. Whatever was blocked
    behind it is released too. Still unbuilt: it stays blocked, with the same reason."""
    waiting = [t for t in prod["tasks"].values() if _blocked_on_target(prod, t)]
    if not waiting: return 0
    try: eval_target(prod)
    except TargetMissing: return 0
    for t in waiting:
        _set(prod, t, PENDING, reason="the app is built now: this check runs again", outputs=[], result=None, gate_results=None)
        for k in ("install", "alternatives", "blocked_on", "unavailable"): t.pop(k, None)
    store.event(prod, "target_built", tasks=[t["id"] for t in waiting])
    _release_blocked(prod)
    return len(waiting)


RETRYABLE = ("execution", "request")   # the check could not run: nothing about the project was measured


def retry(pid, tasks, reason, store_dir=None):
    """Re-run checks that failed without measuring the project (an executor that could not run, a request GITCRAFT
    itself refused, e.g. DESIGNCRAFT's output path before task output was isolated). Explicit and recorded: the earlier
    attempts stay in the task's history, an event names who asked and why, and dependants that were failed or blocked
    on it run again. A check that ran and failed its gate (quality) cannot be retried: that is remediation's job,
    so a retry can never turn a measured failure into a pass."""
    if not reason: raise ValueError("say why the check should run again (reason)")
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        for tid in tasks:
            t = prod["tasks"].get(tid)
            if not t: raise ValueError(f"{tid}: no such task in {pid}")
            if t["state"] != FAILED: raise ValueError(f"{tid} is {t['state']}: only a failed check can be retried")
            last = (t["attempts"] or [{}])[-1]
            if t.get("failure") == "quality" or last.get("outcome") not in RETRYABLE:
                raise ValueError(f"{tid} ran and failed its gate ({t.get('failure') or last.get('outcome')}): a measured failure is fixed in the "
                                 "project (its fix work order), never retried")
        reopened = set()
        for tid in tasks:
            t = prod["tasks"][tid]
            t["attempts"][-1]["retry_requested"] = {"at": store.now(), "reason": reason}
            _invalidate(prod, t, f"retry requested: {reason} (previous: {t.get('error') or t.get('failure')})")
            store.event(prod, "retry_requested", task=tid, reason=reason, previous=t.get("error"))
            reopened.add(tid)
        changed = True
        while changed:   # whatever was failed or blocked because of a reopened check waits for it again
            changed = False
            for t in prod["tasks"].values():
                if t["id"] in reopened or t["state"] not in (BLOCKED, FAILED): continue
                if set(t.get("blocked_by") or []) & reopened or (t["state"] == FAILED and set(t["depends_on"]) & reopened):
                    _set(prod, t, PENDING, reason="upstream is running again: " + ", ".join(sorted(set(t["depends_on"]) & reopened or set(t.get("blocked_by") or []) & reopened)),
                         outputs=[], result=None, gate_results=None)
                    reopened.add(t["id"]); changed = True
        _release_blocked(prod)   # ...and whatever was blocked further down the chain (an agent's task is never invalidated, only released)
        prod["status"] = "planned" if not any(t.get("attempts") for t in prod["tasks"].values()) else "running"
        store.save(prod)
    return status(prod)


def _release_blocked(prod):
    """A task blocked only because an upstream task was dead waits again once none of its dependencies is dead (the upstream
    is being redone, or has since passed). Without this an agent's task two steps below a retried check stayed blocked for
    good: _invalidate leaves agent tasks alone, and retry() reopened only the direct dependants of what it reset. A task
    blocked for its own reasons (no blocked_by: a missing runtime, an unverified deployment) is not touched."""
    changed, n = True, 0
    while changed:
        changed = False
        for t in prod["tasks"].values():
            if t["state"] != BLOCKED or not t.get("blocked_by"): continue
            if any(_dep_state(prod, d) == "dead" for d in t["depends_on"]): continue
            _set(prod, t, PENDING, reason="upstream is no longer blocked: " + ", ".join(t["blocked_by"]), outputs=[], result=None, gate_results=None)
            changed = True; n += 1
    return n


def _invalidate(prod, t, why):
    _set(prod, t, PENDING, reason=why, outputs=[], result=None, gate_results=None)
    if t.get("superseded_by"):   # its re-verification chain measured inputs that are being redone
        nxt = prod["tasks"].get(t.pop("superseded_by"))
        if nxt and nxt["state"] not in (AWAITING_AGENT,): _set(prod, nxt, SKIPPED, reason=f"superseded: {t['id']} is being redone")
    for d in prod["tasks"].values():
        if t["id"] in d["depends_on"] and d["state"] in (PASSED, COMPLETE, FAILED, BLOCKED) and d["kind"] != "agent":
            _invalidate(prod, d, f"upstream {t['id']} is being redone")


def _ready_tasks(prod):
    ready = []
    _release_blocked(prod)
    for tid in prod["order"]:
        t = prod["tasks"][tid]
        if t["state"] != PENDING: continue
        states = {d: _dep_state(prod, d) for d in t["depends_on"]}
        dead = [d for d, s in states.items() if s == "dead"]
        if dead:
            _set(prod, t, BLOCKED, blocked_by=[eff(prod, d)["id"] for d in dead],
                 reason="upstream did not pass: " + ", ".join(f"{eff(prod, d)['id']} ({eff(prod, d)['state']})" for d in dead))
            continue
        settled = all(eff(prod, d)["state"] in TERMINAL for d in t.get("settles") or [] if d in prod["tasks"])   # optional work: any end state
        if all(s == "ok" for s in states.values()) and settled: ready.append(t)
    return ready


def _stale_qa(prod, t):
    """Before a release task starts: QA evidence measured on an older project state is re-measured, a bounded
    number of times. Only project source counts (artifacts are excluded), so evaluation output cannot cause this;
    if the source still keeps changing with no agent submission in between, re-measuring stops and the release
    reports the evidence as stale (INCOMPLETE) with the files that changed."""
    if t["stage"] != "release": return False
    fp = _fp(prod)
    stale = [q for q in (eff(prod, tid) for tid in prod["order"]) if q["kind"] != "agent" and q["stage"] in ("qa", "release") and q["state"] == PASSED
             and q.get("measured_fingerprint") and q["measured_fingerprint"] != fp and q["id"] != t["id"]]
    if not stale: return False
    changed = _changed_since(prod, stale[0]["measured_fingerprint"])
    n = prod.get("stale_rounds", 0) + 1
    if n > STALE_ROUNDS:
        if not prod.get("unstable"):
            prod["unstable"] = {"rounds": n - 1, "changed": changed[:20], "at": store.now(),
                                "reason": f"the project kept changing while it was evaluated ({n - 1} re-measurements with no submission in between): "
                                          + (", ".join(changed[:6]) or "unknown files") + ". Re-measuring stopped; the evidence is stale."}
            store.event(prod, "evaluation_unstable", rounds=n - 1, changed=changed[:20])
        return False
    prod["stale_rounds"] = n
    for q in stale:
        q["attempts"].append({"n": len(q["attempts"]) + 1, "status": "stale", "note": "the project changed after this passed: re-measuring", "at": store.now(),
                              "changed": changed[:10]})
        _set(prod, q, PENDING, reason="stale evidence: the project changed after this check passed (" + (", ".join(changed[:4]) or "?") + ")",
             outputs=[], result=None, gate_results=None)
    store.event(prod, "stale_evidence", round=n, tasks=[q["id"] for q in stale], changed=changed[:20])
    return True


def run(pid, max_workers=4, max_seconds=None, store_dir=None, on_event=None):
    prod = store.load(pid, store_dir)
    if prod.get("problems"):
        return dict(status(prod), refused="the plan has problems; correct the spec (production_plan with overrides) before running")
    gate = _build_authorised(prod)
    if gate: return dict(status(prod), refused=gate)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        _recover(prod); prod["status"] = "running"; prod.pop("crash", None); store.save(prod)
        store.event(prod, "run_started", workers=max_workers)
        t0, running, in_use = time.time(), {}, {k: 0 for k in RESOURCES}
        lock = threading.Lock()
        with cf.ThreadPoolExecutor(max_workers=max_workers) as pool:
            while True:
                with lock:
                    for t in _ready_tasks(prod):
                        if t["id"] in running: continue
                        if _stale_qa(prod, t): store.save(prod); break
                        if t["kind"] == "agent": _issue(prod, t); continue
                        if any(in_use[r] >= RESOURCES[r] for r in t["resources"]): continue
                        if in_use["exclusive"] or ("exclusive" in t["resources"] and running): continue
                        if len(running) >= max_workers: break
                        try: work, early = _prepare(prod, t)
                        except Exception as e:   # one task's hand-off can never take the whole run (and its record) down with it
                            work, early = None, {"status": "failed", "failure": "crash", "error": f"{type(e).__name__}: {e}",
                                                 "trace": traceback.format_exc(limit=4)}
                        if early is not None: _finish(prod, t, early); continue
                        for r in t["resources"]: in_use[r] += 1
                        running[t["id"]] = pool.submit(_timed, work)
                    store.save(prod)
                if not running:
                    if not _ready_tasks(prod): break
                    if max_seconds and time.time() - t0 > max_seconds: break   # the time budget ends a run even while tasks keep becoming ready
                    continue
                done, _ = cf.wait(list(running.values()), return_when=cf.FIRST_COMPLETED, timeout=5)
                for fut in done:
                    tid = next(k for k, v in running.items() if v is fut)
                    t = prod["tasks"][tid]
                    try: res = fut.result()
                    except Exception as e:
                        res = {"status": "failed", "failure": "crash", "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc(limit=4)}
                    with lock:
                        del running[tid]
                        for r in t["resources"]: in_use[r] -= 1
                        _finish(prod, t, res); store.save(prod)
                        if on_event: on_event(t)
                if max_seconds and time.time() - t0 > max_seconds and not running: break
        prod["status"] = overall(prod); prod["verdict"] = _report.final(prod); store.save(prod)
        store.event(prod, "run_stopped", status=prod["status"], verdict=prod["verdict"]["verdict"], reasons=prod["verdict"]["reasons"] or None)
        production_report(prod)
        _report.write(prod)
        return status(prod)


def run_recorded(pid, **kw):
    """run() for a background thread. If the run itself dies, the production says so: its tasks are put back as an
    interrupted run leaves them, its status stops reading "running", and the error is in the record, the event log and
    production_status. Before this a background run that hit an unexpected error ended with its thread: nothing was
    written, and the production read "running" for good."""
    try: return run(pid, **kw)
    except Exception as e:
        err, trace = f"{type(e).__name__}: {e}", traceback.format_exc(limit=6)
        try:
            prod = store.load(pid, kw.get("store_dir"))
            _recover(prod)
            prod["status"] = overall(prod); prod["crash"] = {"at": store.now(), "error": err, "trace": trace}
            store.event(prod, "run_crashed", error=err)
            store.save(prod)
        except Exception: pass   # the record cannot be written either: the error below still reaches the caller's log
        print(f"gitcraft: production {pid} run crashed: {err}\n{trace}", file=sys.stderr, flush=True)
        return {"production": pid, "status": "crashed", "error": err}


def production_report(prod):
    """Every run ends with a Production Report (project_report.generate, refresh none: it reads what the departments
    recorded and re-measures nothing). It is written to the report store, outside the project, and linked from the
    run's status and REPORT.md. A report that cannot be made is recorded with its reason and never fails the run.
    GITCRAFT_PRODUCTION_REPORT=0 turns it off."""
    if os.environ.get("GITCRAFT_PRODUCTION_REPORT", "1") == "0": return None
    info = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        path = _project(prod)
        if not path or not os.path.isdir(path): info.update(status="skipped", why="the project folder does not exist yet")
        else:
            from . import project_report
            R = project_report.generate(path, refresh="none", save="store")
            info.update(status="ok", report_id=R["report_id"], html=R["paths"].get("html"), json=R["paths"].get("json"), markdown=R["paths"].get("markdown"),
                        overall=R["health"].get("score"), method=R["health"].get("method"), verdict=R["gates"].get("verdict"))
    except Exception as e:   # the report never fails the run it describes
        info.update(status="failed", why=f"{type(e).__name__}: {e}"[:300])
    prod["production_report"] = info; store.save(prod)
    store.event(prod, "production_report", status=info["status"], report=info.get("html"), why=info.get("why"))
    return info


def _build_authorised(prod):
    """None, or why building may not start: Discovery approval is not build approval; only an approved blueprint is."""
    if "lifecycle" not in prod: return None   # made before the lifecycle existed: its plan was its authorisation
    st = lifecycle.stage(prod)
    if st == "revision": return "a material change to the approved blueprint is waiting for a person (production_decide)"
    if (prod.get("blueprint") or {}).get("status") != "approved":
        return f"the blueprint is not approved (stage: {st}): review the Decision Room and approve it (production_decide approve=true) before building"
    return None


def _issue(prod, t):
    wo = t["work_order"] or {}
    if wo.get("approval") and not prod["spec"]["authorisations"].get(wo["approval"]) and not t.get("approved"):
        _set(prod, t, NEEDS_APPROVAL, reason=f"{wo['approval']} needs a person's approval (production_approve)"); return
    d = _task_dir(prod, t["id"])
    h = _handoff(prod, t, {})
    if t["id"] == "build" or t["stage"] == "integration":
        h["integrated_assets"] = [{k: m[k] for k in ("dest_rel", "role", "format", "task")} for m in _integrated(prod)]
    if t.get("consumes"):   # plan v2: what is being produced in parallel, for the placeholders
        h["planned_assets"] = [{"task": c, "title": prod["tasks"][c]["title"], "roles": (prod["tasks"][c].get("ship") or {}).get("roles"),
                                "dest": (prod["tasks"][c].get("ship") or {}).get("dest", "").replace("$project", _project(prod)),
                                "state": eff(prod, c)["state"]} for c in t["consumes"] if c in prod["tasks"]]
        h["manifest"] = os.path.join(_project(prod), planner.MANIFEST)
    if t["id"] == "build.wire" and "icon.derivatives" in prod["tasks"]:   # v2: the icon set is not upstream of the wiring step, so name it
        h["icon_snippet"] = next((o["path"] for o in eff(prod, "icon.derivatives").get("outputs") or [] if o.get("role") == "icon_snippet"), None)
    if prod.get("plan_version", 1) >= 2 and t["kind"] == "agent":   # what the agent must not write (checked on submit)
        h["integration_owned"] = [planner.MANIFEST] + [m["dest_rel"] for m in _integrated(prod)]
    order = {"production": prod["id"], "task": t["id"], "title": t["title"], "owner": t["owner"], "out_dir": d, "project": _project(prod),
             **{k: v for k, v in wo.items() if k != "approval"}, "handoff": h,
             **({"existing_project": {k: (prod.get("maturity") or {}).get(k) for k in ("maturity", "kind", "confidence", "inventory", "save_keys", "deploy", "tests")},
                 "workflow": prod["spec"].get("mode", {}).get("workflow"), "request": prod["spec"].get("mode", {}).get("request")}
                if prod["spec"].get("mode", {}).get("existing") and t["kind"] == "agent" else {}),
             "blueprint": {"decisions": (prod.get("blueprint") or {}).get("decisions"), "engineering": prod["spec"].get("engineering", {}).get("profile"),
                           "rule": "settled: build to these decisions; a material change needs production_revise and a person's approval"},
             "submit": f"production_submit {{\"production\": \"{prod['id']}\", \"task\": \"{t['id']}\", \"files\": [absolute paths], \"notes\": \"...\"}}"}
    if wo.get("expected"):
        order["expected"] = [dict(e, path=e["path"].replace("$project", _project(prod)) if e["path"].startswith("$project") else os.path.join(d, e["path"])) for e in wo["expected"]]
    store.write_json(os.path.join(d, "work_order.json"), order)
    with open(os.path.join(d, "WORK_ORDER.md"), "w") as f: f.write(_report.work_order_md(order))
    t["work_order_path"] = os.path.join(d, "WORK_ORDER.md")
    _set(prod, t, AWAITING_AGENT, reason="waiting for the agent to do this work and submit it")


def _prepare(prod, t):
    """Main thread: record the attempt, resolve the hand-off, snapshot what a QA check measures. Returns the
    work for a worker (a closure over plain values) or a failed result when the hand-off cannot be made."""
    att = {"n": len(t["attempts"]) + 1, "started": store.now(), "t0": round(time.time(), 3)}
    t["attempts"].append(att)
    _set(prod, t, IN_PROGRESS)
    out_dir = _task_dir(prod, t["id"])
    try:
        params = resolve(prod, copy.deepcopy(t["params"]))
    except TargetMissing as e:   # cannot be evaluated here: an explicit, reasoned blocked state (never the source instead)
        return None, {"status": "blocked", "reason": str(e), "blocked_on": "target",
                      "install": [c for c in [(prod.get("evaluation") or {}).get("build_command")] if c]}
    except (HandoffError, OSError, ValueError) as e:
        # a comparison whose "before" could not be measured here was not run: unavailable, never a defect in the project
        src = [eff(prod, v["$from"]) for v in (t["params"] or {}).values()
               if isinstance(v, dict) and v.get("$from", "").startswith("baseline.") and v["$from"] in prod["tasks"]]
        lost = next((x for x in src if x["state"] in (BLOCKED, FAILED, SKIPPED)), None)
        if lost: return None, {"status": "blocked", "reason": f"no before/after comparison: {lost['id']} could not measure the project before the change "
                                                               f"({lost.get('reason') or lost.get('error') or lost['state']})"}
        return None, {"status": "failed", "failure": "handoff", "error": f"hand-off: {e}"}
    _handoff(prod, t, params)
    if "$target" in json.dumps(t["params"]): t["evaluated_target"] = eval_target(prod)
    if t["stage"] in ("qa", "release"): t["measured_fingerprint"] = _fp(prod)
    kind, dept, action, timeout = t["kind"], t["department"], t["action"], t["timeout"]
    if kind == "studio":
        req = dict({k: v for k, v in params.items() if v is not None}, out_dir=out_dir, tags=[f"production:{prod['id']}"])
        req.setdefault("name", t["id"].replace(".", "_"))
        return (lambda: executors.studio_run(dept, action, req, timeout=timeout)), None
    if kind == "forgecraft":
        req = dict(params, handoff_dir=out_dir, wait=True)
        def forge():
            r = executors.forgecraft_call(action, req, timeout=timeout)
            return _forge_outputs(dict(r, status="ok")) if r.get("status") in ("done", "done_with_fallback") else r
        return forge, None
    if kind == "designcraft":
        return (lambda: executors.designcraft_assess(params["project"], os.path.join(out_dir, "designcraft.json"), timeout=timeout)), None
    if kind == "builtin":
        if action == "release": return None, _release(prod, t, out_dir)   # reads the whole production: main thread
        ctx = {"prod": {"id": prod["id"]}, "task": copy.deepcopy(t), "project": _project(prod), "params": params, "out_dir": out_dir,
               "upstream": copy.deepcopy(_upstream(prod, t)), "auth": dict(prod["spec"]["authorisations"]), "approved": t.get("approved"),
               "spec": copy.deepcopy(prod["spec"]), "choice": t.get("choice"), "approval_note": t.get("approval_note"),
               "tasks": {k: {"state": eff(prod, k)["state"], "approved": eff(prod, k).get("approved")} for k in prod["tasks"]},
               "inside_roots": inside_roots, "previous_manifest": copy.deepcopy((t.get("last_result") or {}).get("integrated")),
               "replace_auth": dict((prod.get("replace_assets") or {}).get("authorized") or {}), "integrated": copy.deepcopy(_integrated(prod)),
               "inherited": copy.deepcopy(_inherited(prod))}
        return (lambda: getattr(builtins, action)(ctx)), None
    return None, {"status": "failed", "failure": "request", "error": f"unknown executor {kind}"}


def _timed(work):
    t0 = time.time(); r = work(); r = r if isinstance(r, dict) else {"status": "failed", "failure": "crash", "error": "the executor returned nothing"}
    r.setdefault("_seconds", round(time.time() - t0, 2)); return r


def _finish(prod, t, res):
    att = t["attempts"][-1]; att["finished"] = store.now(); att["t1"] = round(time.time(), 3); att["seconds"] = res.pop("_seconds", None)
    cls = gates.classify(res) if res.get("status") != "needs_approval" else "approval"
    att.update(status=res.get("status"), outcome=cls, error=(res.get("error") or res.get("reason") or None) and str(res.get("error") or res.get("reason"))[:1500])
    t["outputs"] = _norm_outputs(res)
    t["result"] = _slim(res)
    if cls == "approval" and res.get("consolidated"):   # plan v2: one replace_assets approval for the whole production
        ra = prod.setdefault("replace_assets", {"authorized": {}, "pending": {}, "history": []})
        for f in res.get("files") or []: ra["pending"][f["file"]] = {"sha256": f["sha256"], "task": f["task"]}
        _set(prod, t, NEEDS_APPROVAL, reason="waiting for the production's one replace_assets approval (production_approve task=replace_assets): "
             + ", ".join(f["file"] for f in res.get("files") or [])[:600], approval="replace_assets", consolidated=True); return
    if cls == "approval":
        _set(prod, t, NEEDS_APPROVAL, reason=res.get("reason"), approval=res.get("approval")); return
    if cls == "blocked":   # a department that reports blocked lacks a runtime or capability here: unavailable, never a defect
        _set(prod, t, BLOCKED, reason=res.get("reason"), install=res.get("install"), alternatives=res.get("alternatives"),
             blocked_on=res.get("blocked_on"), unavailable=t["kind"] in ("studio", "forgecraft", "designcraft") or bool(res.get("install"))); return
    if cls in ("execution",) and len([a for a in t["attempts"] if a.get("outcome") == "execution"]) <= t["retries"]:
        _set(prod, t, PENDING, reason=f"retrying after an execution failure: {att['error']}"); return
    if cls in ("execution", "request") or res.get("failure") in ("handoff", "conflict"):
        _set(prod, t, FAILED, failure=res.get("failure") or cls, error=att["error"],
             reason="not retried: the request itself is the problem" if cls == "request" else None); return
    # the department ran: the task is complete; only its gate decides passed
    _set(prod, t, COMPLETE)
    gr = gates.evaluate(t, res, {"project": _project(prod), "integrated": _integrated(prod), "outputs": t["outputs"]})
    t["gate_results"] = gr
    if t.get("advisory"):   # recorded evidence that never blocks (and is never "remediated")
        _set(prod, t, PASSED if res.get("status") == "ok" else FAILED, reason="advisory"); return
    if all(g["ok"] for g in gr):
        _set(prod, t, PASSED); return
    if all(g.get("category") == "unverified" for g in gr if not g["ok"]):   # could not be verified: incomplete, never a defect to "fix"
        unv = [u for g in gr if not g["ok"] for u in g.get("unverified") or []]
        _set(prod, t, BLOCKED, unverified=unv, reason="verification incomplete (not an application failure): "
             + "; ".join(f"{u['check']} [{u['cause']}]" for u in unv)[:1200]); return
    _set(prod, t, FAILED, failure="quality", error="; ".join(f"{g['condition']}: {g.get('detail') or g.get('measured')}" for g in gr if not g["ok"])[:1500])
    _remediate(prod, t, res, gr)


def _manifest_now(project):
    """The project's asset manifest entries as they stand, {path: {task, sha256}} ({} when it has none)."""
    if not project or not os.path.isfile(os.path.join(project, planner.MANIFEST)): return {}
    return {k: {"task": v.get("task"), "sha256": v.get("sha256")} for k, v in builtins.read_manifest(project)["assets"].items()}


def _inherited(prod):
    """The manifest entries the project carried before this production integrated anything (recorded at planning).
    A record planned before that was recorded recovers them when it safely can: nothing integrated yet, and the manifest
    file still has the hash the preservation baseline took at Discovery, so what it lists now is what it listed then."""
    if "inherited_assets" not in prod:
        proj, got = _project(prod), None
        mp, bp = os.path.join(proj or "", planner.MANIFEST), os.path.join(prod.get("store") or "", "baseline.json")
        if proj and os.path.isfile(mp) and os.path.isfile(bp) and not _integrated(prod):
            try:
                with open(bp) as f: was = (json.load(f).get("files") or {}).get(planner.MANIFEST)
            except (OSError, ValueError): was = None
            if was and was == builtins.sha256(mp): got = _manifest_now(proj)
        if got is None: return {}   # unknown: the checks stay as strict as they were
        prod["inherited_assets"] = got
    return prod["inherited_assets"]


def _integrated(prod):
    """The integration ledger: every file integration committed into the project (v1: integrate.assets; v2: each integrate.<task>
    that passed, in plan order, a later commit of the same path replacing an earlier one)."""
    if "integrate.assets" in prod["tasks"]:
        return (eff(prod, "integrate.assets").get("result") or {}).get("integrated") or []
    led = {}
    for tid in prod["order"]:
        t = prod["tasks"][tid]
        if t["kind"] == "builtin" and t.get("action") == "integrate" and not t.get("reverifies") and eff(prod, tid)["state"] == PASSED:
            for m in (eff(prod, tid).get("result") or {}).get("integrated") or []: led[m["dest_rel"]] = m
    return list(led.values())


def _remediate(prod, t, res, gr):
    """A failed QA gate becomes a fix work order and a re-verification of the modified project. Plan v2 routes a failure to the
    department that owns it (_route): a department's own output failing its gate, or QA finding a defective file that
    department produced, goes back to that department; everything else is the agent's (code)."""
    if (prod["spec"].get("mode") or {}).get("workflow") == "review": return   # review measures; it never orders changes
    if prod.get("plan_version", 1) >= 2:
        r = _route(prod, t, res)
        if r: return _department_rework(prod, t, r)
    if t["stage"] not in ("qa", "release") or t["kind"] == "builtin" and t["action"] == "release": return
    root = t.get("chain") or t["id"]; rnd = (t.get("round") or 0) + 1
    maxr = prod["spec"]["quality"].get("max_rounds", 2)
    t["routed"] = {"to": ["agent"]}
    if rnd > maxr:
        t["exhausted"] = True
        store.event(prod, "quality_gate_exhausted", task=t["id"], rounds=rnd - 1); return
    fix_id, rv_id = f"fix.{root}.r{rnd}", f"{root}.r{rnd}"
    design = None   # DESIGNCRAFT runs beside PLAYCRAFT (static, seconds) and is nearly always done when a gameplay fix is written
    if t.get("department") == "playcraft" and "qa.designcraft" in prod["tasks"]:
        design = (eff(prod, "qa.designcraft").get("result") or {}).get("proposals")
    items = gates.remediation(t, res, gr, design)
    fix = planner.T(fix_id, f"Fix what {root} found (round {rnd})", t["stage"], "agent", deps=[],
                    work_order={"brief": f"{t['title']} failed its gate. Fix the project so it passes; the check then runs again on the modified files.",
                                "findings": items, "instructions": ["Change the project to address the findings (keep every existing feature).",
                                                                    "Submit the files you changed; the re-verification measures the new project state."],
                                "expected": []})
    fix.update(fix_for=t["id"], failed_fingerprint=t.get("measured_fingerprint"), chain=root, round=rnd, routed_to="agent",
               routed_because="a code or wiring finding (no department output is at fault)")
    rv = planner.T(rv_id, f"{t['title']} — re-verification {rnd}", t["stage"], t["kind"], department=t["department"], action=t["action"],
                   params=copy.deepcopy(t["params"]), deps=[fix_id], gate=copy.deepcopy(t["gate"]), resources=t["resources"], retries=t["retries"],
                   timeout=t["timeout"], criterion=t.get("criterion"))
    rv.update(chain=root, round=rnd, reverifies=t["id"])
    prod["tasks"][fix_id] = fix; prod["tasks"][rv_id] = rv
    i = prod["order"].index(t["id"]) + 1
    prod["order"][i:i] = [fix_id, rv_id]
    t["superseded_by"] = rv_id
    store.event(prod, "remediation", task=t["id"], fix=fix_id, reverify=rv_id, round=rnd, findings=len(items))


REWORK_SEED = 1009   # a department re-run varies its seed by this per round (every Studio action accepts `seed`): deterministic
DEPARTMENT_ROUNDS = 2   # D5: two re-runs per owning department, then a person decides; never an unbounded automatic loop


def _route(prod, t, res):
    """(producer task ids, why) when a department owns the failure, else None (the agent's).
      - a production-stage department task whose own gate failed: that department
      - qa.assets (TestCraft) failing on files that integration committed: the department that produced each file"""
    if t["stage"] == "production" and t["kind"] in ("studio", "forgecraft"):
        return [t.get("chain") or t["id"]], f"{t['owner']}'s own output failed its gate"
    if t.get("department") == "testcraft" and t.get("action") == "assets":
        folder = os.path.relpath((t.get("params") or {}).get("folder", "").replace("$project", _project(prod)), _project(prod))
        bad = [row.get("path") for c in res.get("checks") or [] if not c.get("ok") for row in (c.get("detail") or []) if isinstance(row, dict)]
        led = {m["dest_rel"]: m["task"] for m in _integrated(prod)}
        owners = [led.get(os.path.normpath(os.path.join(folder, b))) for b in bad if b]
        if owners and all(owners):   # every defective file is a department's output: route to them; anything else is the agent's
            return sorted(set(owners)), "qa.assets found defective files produced by " + ", ".join(sorted({prod["tasks"][o]["owner"] for o in owners}))
    return None


def _rework_round(prod, root):
    return 1 + sum(1 for x in prod["tasks"].values() if x.get("rework_of") == root)


def _department_rework(prod, t, route, force=False):
    """Send the work back to the producing department(s): a re-run of the same action with its seed varied, re-integrated when it
    had shipped, then the failed check again. At most max_rounds re-runs per producer; after that a required criterion is
    escalated to a person (an optional one is recorded as not delivered), never retried automatically."""
    producers, why = route
    maxr = DEPARTMENT_ROUNDS
    t["routed"] = {"to": sorted({prod["tasks"][p]["owner"] for p in producers}), "producers": list(producers), "because": why}   # read by qa.findings
    qa_root = None if t["stage"] == "production" else (t.get("chain") or t["id"])
    new_integrations = []
    for p in producers:
        rnd = _rework_round(prod, p)
        src = prod["tasks"][p]
        if rnd > maxr and not force:
            _escalate(prod, p, src, f"{why}; {maxr} re-run(s) by {src['owner']} did not fix it", origin=t["id"]); continue
        rid = f"{p}.r{rnd}"
        params = copy.deepcopy(src["params"])
        if src["kind"] == "studio": params["seed"] = int(params.get("seed") or 0) + REWORK_SEED * rnd
        rv = planner.T(rid, f"{src['title']} — rework {rnd} by its department", src["stage"], src["kind"], department=src.get("department"), action=src.get("action"),
                       params=params, deps=list(src["depends_on"]), gate=copy.deepcopy(src["gate"]), ship=copy.deepcopy(src.get("ship")),
                       resources=src["resources"], retries=src["retries"], timeout=src["timeout"], criterion=src.get("criterion"))
        rv.update(chain=p, round=rnd, reverifies=eff(prod, p)["id"], rework_of=p, routed_to=src["owner"], routed_because=why, optional=src.get("optional"))
        cur = eff(prod, p)
        prod["tasks"][rid] = rv; prod["order"].insert(prod["order"].index(cur["id"]) + 1, rid); cur["superseded_by"] = rid
        integ = f"integrate.{p}"
        if qa_root and integ in prod["tasks"]:   # the old file is in the project: integrate the re-made one (same transactional path)
            iid = f"{integ}.r{rnd}"
            it = planner.T(iid, f"Re-integrate {p} after its rework", "integration", "builtin", action="integrate", params={"v2": True}, deps=[p],
                           resources=["integration"], criterion="asset_integrity")
            it.update(reintegrates=integ, routed_to="Production Director", routed_because=f"re-made by {src['owner']}")
            prod["tasks"][iid] = it; prod["order"].insert(prod["order"].index(integ) + 1, iid); new_integrations.append(iid)
        store.event(prod, "rework", task=p, rework=rid, round=rnd, owner=src["owner"], because=why)
    if qa_root and new_integrations:   # the failed check measures again once every re-made file is integrated
        rnd = (t.get("round") or 0) + 1
        rv_id = f"{qa_root}.r{rnd}"
        rv = planner.T(rv_id, f"{t['title']} — re-verification {rnd}", t["stage"], t["kind"], department=t["department"], action=t["action"],
                       params=copy.deepcopy(t["params"]), deps=new_integrations, gate=copy.deepcopy(t["gate"]), resources=t["resources"], retries=t["retries"],
                       timeout=t["timeout"], criterion=t.get("criterion"))
        rv.update(chain=qa_root, round=rnd, reverifies=t["id"], routed_to=t["owner"], routed_because=why)
        prod["tasks"][rv_id] = rv; prod["order"].insert(prod["order"].index(t["id"]) + 1, rv_id); t["superseded_by"] = rv_id


def _escalate(prod, p, src, why, origin=None):
    """A required criterion a department could not fix in max_rounds: one decision for a person (retry once more, or leave it
    failed). An optional one is not escalated: it is recorded as not delivered and the release can still be READY."""
    crit = src.get("criterion")
    req = next((c.get("required", True) for c in prod["spec"]["acceptance"] if c["id"] == crit), True)
    if not req:
        prod.setdefault("decisions", []).append(f"optional not delivered: {crit} ({why})")
        store.event(prod, "optional_not_delivered", task=p, criterion=crit, because=why); return
    eid = f"escalate.{p}"
    if eid in prod["tasks"] and prod["tasks"][eid]["state"] == NEEDS_APPROVAL: return
    e = planner.T(eid, f"Decide: {src['title']} still fails after its department's re-runs", src["stage"], "builtin", action="escalate")
    e.update(escalates=p, origin=origin, routed_to="person", routed_because=why, gate=[])
    prod["tasks"][eid] = e; prod["order"].append(eid)
    _set(prod, e, NEEDS_APPROVAL, reason=f"{why}. Approve to let {src['owner']} try once more (production_approve task={eid}); decline to leave {crit} failed "
         "(the release cannot be READY). Changing the department is a plan revision (production_revise).")
    store.event(prod, "escalated", task=p, criterion=crit, because=why)


# ---------------------------------------------------------------- agent hand-back and approvals
def submit(pid, task, files=None, notes=None, url=None, evidence=None, license=None, store_dir=None, run_after=False, max_workers=4):
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        t = prod["tasks"].get(task)
        if not t: raise KeyError(f"production {pid} has no task {task}")
        if t["kind"] != "agent": raise ValueError(f"{task} is done by {t['owner']}, not submitted by the agent")
        if t["state"] != AWAITING_AGENT: raise ValueError(f"{task} is {t['state']}, not waiting for a submission")
        wo, d, proj = t["work_order"] or {}, _task_dir(prod, task), _project(prod)
        att = {"n": len(t["attempts"]) + 1, "started": store.now(), "finished": store.now(), "notes": notes, "files": files or []}
        t["attempts"].append(att)
        # A work order tells the agent to write its task files in the production's own task folder. When the project is
        # the only workspace root that folder is in GITCRAFT's isolated home, outside the roots: it is still GITCRAFT's
        # own, the same exception store.create makes. Anything else outside the roots is refused as before.
        own = {os.path.realpath(prod["store"]), os.path.realpath(store.output_root(prod, create=False))}
        allowed = lambda p: inside_roots(p) or any(artifacts.inside(p, r) for r in own)
        checks, outs = gates.check_expected(wo.get("expected", []), d, proj, allowed)
        for f in files or []:
            p = f if os.path.isabs(f) else next((c for c in (os.path.join(d, f), os.path.join(proj or d, f)) if os.path.exists(c)), os.path.join(proj or d, f))
            if not allowed(p): checks.append({"name": f"{f} is inside the workspace roots", "ok": False, "detail": p}); continue
            if not os.path.exists(p): checks.append({"name": f"{f} exists", "ok": False, "detail": "the submission names a file that is not there"}); continue
            if os.path.isfile(p) and not any(o["path"] == p for o in outs):
                v = executors.validate_file(p)
                checks.append({"name": f"{os.path.relpath(p, proj) if proj and p.startswith(proj) else f} opens as {v.get('format')}", "ok": v.get("ok", False), "detail": v.get("error")})
                if v.get("ok"): outs.append({"path": p, "role": "submitted", "format": v.get("format"), "ok": True})
        if prod.get("plan_version", 1) >= 2 and proj:   # disjoint write ownership: integration's files are not the agent's to change
            bad = _scope_violations(prod, files or [])
            checks.append({"name": "integration-owned files are untouched (the asset manifest and every integrated file)", "ok": not bad,
                           "detail": bad[:12] or None})
        if t.get("fix_for"):
            now_fp = _fp(prod)
            checks.append({"name": "the project changed since the failed check measured it", "ok": now_fp != t.get("failed_fingerprint"),
                           "detail": None if now_fp != t.get("failed_fingerprint") else "no file in the project differs: nothing was fixed"})
        verified = None
        if "url" in (wo.get("requires") or []):
            checks.append({"name": "a URL was submitted", "ok": bool(url)})
            verified = _verify_deploy(url, evidence)
            checks.append({"name": "the live URL was checked (evidence: a passing check run against that URL)", "ok": verified["ok"], "detail": verified["detail"]})
            t["deployment"] = {"url": url, "evidence": evidence, "verified": verified["ok"], "detail": verified["detail"]}
        for o in outs:
            if o.get("sha256") is None and os.path.isfile(o["path"]): o["sha256"] = builtins.sha256(o["path"])
        t["outputs"] = outs
        t["result"] = {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks, "notes": notes,
                       "output_license": license or wo.get("license"), "submitted": store.now()}
        t["gate_results"] = [{"condition": c["name"], "ok": c["ok"], "detail": c.get("detail")} for c in checks]
        att.update(status=t["result"]["status"], outcome="ok" if t["result"]["status"] == "ok" else "quality")
        if all(c["ok"] for c in checks):
            _set(prod, t, PASSED); prod["stale_rounds"] = 0; prod.pop("unstable", None)   # the agent changed the project: re-measuring is expected
        else:
            # an agent submission that does not validate stays open: the work order is still owed
            _set(prod, t, AWAITING_AGENT, reason="submission rejected: " + "; ".join(c["name"] + (f" ({c['detail']})" if c.get("detail") else "") for c in checks if not c["ok"])[:1200])
        store.event(prod, "submitted", task=task, accepted=t["state"] == PASSED, files=len(files or []))
        store.save(prod)
    if run_after and t["state"] == PASSED: return run(pid, max_workers=max_workers, store_dir=store_dir)
    return dict(status(prod), submission={"task": task, "accepted": t["state"] == PASSED, "checks": checks})


def _scope_violations(prod, files):
    """Integration-owned paths the agent changed or submitted: every integrated file must still have its committed hash, and the
    asset manifest must list exactly the ledger plus what the project carried before this production (_inherited), unchanged.
    A submission naming an owned path is refused too."""
    proj = _project(prod)
    led = {m["dest_rel"]: m for m in _integrated(prod)}
    out = [f"{r} (changed after integration)" for r, m in led.items() if not os.path.isfile(m["dest"]) or builtins.sha256(m["dest"]) != m["sha256"]]
    man = builtins.read_manifest(proj)["assets"] if os.path.exists(os.path.join(proj, planner.MANIFEST)) else {}
    if os.path.exists(os.path.join(proj, planner.MANIFEST)) or led:
        if {k: v.get("sha256") for k, v in man.items()} != builtins.expected_manifest(list(led.values()), _inherited(prod)):
            out.append(f"{planner.MANIFEST} (does not match what integration committed)")
    owned = set(led) | {planner.MANIFEST}
    for f in files:
        rel = os.path.relpath(f, proj) if os.path.isabs(f) else f
        if rel in owned: out.append(f"{rel} (submitted, but owned by integration)")
    return out


def _verify_deploy(url, evidence):
    if not evidence: return {"ok": False, "detail": "no evidence: a deployment is never recorded as live without a check against it"}
    p = evidence if os.path.isabs(evidence) else None
    if not p or not os.path.isfile(p): return {"ok": False, "detail": f"evidence {evidence!r} is not a file"}
    try: rec = json.load(open(p))
    except ValueError: return {"ok": False, "detail": "evidence is not a check record (JSON)"}
    target = json.dumps(rec.get("request") or {})
    if rec.get("status") == "incomplete":   # deployed and serving, but some live checks could not be verified: never recorded as verified live
        return {"ok": False, "incomplete": True, "detail": "DEPLOYED · VERIFICATION INCOMPLETE: " + "; ".join(
            f"{c['name']} [{c.get('cause') or 'unverified'}]" for c in rec.get("checks", []) if c.get("category") == "unverified")[:600]}
    if rec.get("status") != "ok": return {"ok": False, "detail": f"the evidence check did not pass ({rec.get('status')})"}
    if url not in target: return {"ok": False, "detail": "the evidence check ran against a different target than the submitted URL"}
    return {"ok": True, "detail": f"{rec.get('department')}.{rec.get('action')} passed against {url}"}


def replace_assets_request(prod):
    """The consolidated replace_assets approval (plan v2): {files, ready, waiting_on}. It is presented only when the overwrite set
    is complete: every asset task and every integration has settled, so the person sees every file at once."""
    ra = prod.get("replace_assets") or {}
    pending = ra.get("pending") or {}
    if not pending: return None
    shipping = [i for i in prod["order"] if prod["tasks"][i].get("ship") and not prod["tasks"][i].get("reverifies")]
    integ = [i for i in prod["order"] if prod["tasks"][i]["kind"] == "builtin" and prod["tasks"][i].get("action") == "integrate"]
    waiting = [i for i in shipping if eff(prod, i)["state"] not in TERMINAL] + \
              [i for i in integ if eff(prod, i)["state"] not in TERMINAL and not (eff(prod, i)["state"] == NEEDS_APPROVAL and eff(prod, i).get("consolidated"))]
    return {"files": [{"file": k, **v} for k, v in sorted(pending.items())], "ready": not waiting, "waiting_on": waiting}


def approve(pid, task, approved=True, note=None, store_dir=None, choice=None):
    prod = store.load(pid, store_dir)
    if task == "replace_assets": return _approve_replace(pid, approved, note, store_dir)
    if task.startswith("escalate."): return _approve_escalation(pid, task, approved, note, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        t = prod["tasks"].get(task)
        if not t or t["state"] != NEEDS_APPROVAL: raise ValueError(f"{task} is not waiting for approval")
        options = [c.get("id") for c in (t.get("result") or {}).get("concepts") or []]
        if approved and choice is not None and options and choice not in options:
            raise ValueError(f"{choice!r} is not one of the concepts {options}")
        store.event(prod, "approval", task=task, approved=approved, note=note, choice=choice)
        prod.setdefault("decisions", []).append(f"{'approved' if approved else 'declined'}: {task}" + (f" ({choice})" if choice else "") + (f" — {note}" if note else ""))
        if approved:
            t["approved"] = True; t["last_result"] = t.get("result"); t["choice"] = choice; t["approval_note"] = note
            _set(prod, t, PENDING, reason="approved" + (f": {choice}" if choice else ""))
        elif task == "icon.select":   # not these: new concepts with the person's feedback, then the choice again
            c = prod["tasks"]["icon.concepts"]
            c["work_order"] = dict(c["work_order"] or {}, feedback=(c["work_order"] or {}).get("feedback", []) + [note or "make different concepts"])
            _set(prod, c, PENDING, reason="the person asked for new concepts" + (f": {note}" if note else ""), outputs=[], result=None)
            _set(prod, t, PENDING, reason="waiting for the new concepts", outputs=[], result=None)
        else:
            _set(prod, t, SKIPPED, reason=f"declined by a person{': ' + note if note else ''}")
        store.save(prod)
    return status(prod)


def _approve_escalation(pid, task, approved, note, store_dir):
    """A person's decision on an escalated failure: approved → its department re-runs once more (recorded as granted by a
    person, beyond max_rounds); declined → the criterion stays failed. Never a pass."""
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        e = prod["tasks"].get(task)
        if not e or e["state"] != NEEDS_APPROVAL: raise ValueError(f"{task} is not waiting for a decision")
        p = e["escalates"]; src = prod["tasks"][p]
        if approved:
            o = eff(prod, e.get("origin") or p)   # the check that failed: the department's own gate, or the QA check that found the file
            _department_rework(prod, o, ([p], f"a person asked for one more re-run{': ' + note if note else ''}"), force=True)
            _set(prod, e, PASSED, reason="a person granted one more re-run")
        else:
            _set(prod, e, SKIPPED, reason=f"declined by a person: {src.get('criterion')} stays failed" + (f" — {note}" if note else ""))
        prod.setdefault("decisions", []).append(f"{'approved' if approved else 'declined'}: {task}" + (f" — {note}" if note else ""))
        store.event(prod, "approval", task=task, approved=approved, note=note)
        store.save(prod)
    return status(prod)


def _approve_replace(pid, approved, note, store_dir):
    """A person's decision on the consolidated overwrite set. Approval authorises exactly the listed files with exactly the listed
    content; any other overwrite later (a different file, or new content for a listed one) asks again. Declining skips the
    integrations that would overwrite (their files are untouched); the release criteria they carry then cannot pass."""
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        req = replace_assets_request(prod)
        if not req: raise ValueError("no replace_assets approval is pending")
        if not req["ready"]:
            raise ValueError("the overwrite set is not complete yet (still producing or integrating: " + ", ".join(req["waiting_on"][:8])
                             + "); the approval is presented once every asset has settled")
        ra = prod["replace_assets"]
        files = {f["file"]: f["sha256"] for f in req["files"]}
        waiting = [t for t in prod["tasks"].values() if t["state"] == NEEDS_APPROVAL and t.get("consolidated")]
        ra["history"].append({"at": store.now(), "approved": approved, "files": files, "note": note})
        if approved:
            ra["authorized"].update(files)
            for t in waiting: _set(prod, t, PENDING, reason=f"replace_assets approved for {len(files)} listed file(s)")
        else:
            for t in waiting: _set(prod, t, SKIPPED, reason="declined by a person: existing files are not replaced" + (f" — {note}" if note else ""))
        ra["pending"] = {}
        prod.setdefault("decisions", []).append(f"{'approved' if approved else 'declined'}: replace_assets for {', '.join(sorted(files))}" + (f" — {note}" if note else ""))
        store.event(prod, "approval", task="replace_assets", approved=approved, files=sorted(files), note=note)
        store.save(prod)
    return status(prod)


# ---------------------------------------------------------------- release, status
def _release(prod, t, out_dir):
    acc = _report.acceptance(prod, exclude={"release_ready", "deployment"})
    fp = _fp(prod)
    stale = [q["id"] for q in (eff(prod, i) for i in prod["order"]) if q["stage"] in ("qa", "release") and q["state"] == PASSED
             and q.get("measured_fingerprint") not in (None, fp)]
    checks = [{"name": f"criterion {a['id']}: {a['text']}", "ok": a["status"] in _report.PASSING, "detail": a.get("why") or a.get("advisories"),
               **({"category": "unverified", "cause": a.get("cause") or a["status"]} if a["status"] in ("unverified", "blocked", "unavailable") else
                  {"category": "advisory"} if a["status"] == "advisory" else {})} for a in acc]
    checks.append({"name": "every QA result was measured on the build being released", "ok": not stale,
                   "detail": (stale + ([prod["unstable"]["reason"]] if prod.get("unstable") else [])) if stale else None})
    tg = sorted({q["evaluated_target"] for q in (eff(prod, i) for i in prod["order"]) if q.get("evaluated_target") and q["state"] == PASSED})
    checks.append({"name": "every browser check measured the same target (" + ((prod.get("evaluation") or {}).get("why") or "evaluation policy") + ")",
                   "ok": len(tg) <= 1, "detail": tg if len(tg) > 1 else None})
    rel = os.path.join(out_dir, "RELEASE.md")
    prod["release"] = {"fingerprint": fp, "at": store.now(), "criteria": acc}
    with open(rel, "w") as f: f.write(_report.markdown(prod, release=True))
    att = _attribution(prod)
    outs = [{"path": rel, "role": "release_report", "format": "text"}] + ([{"path": att, "role": "attribution", "format": "text"}] if att else [])
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "outputs": outs, "checks": checks, "fingerprint": fp}


def _attribution(prod):
    for tid in prod["order"]:
        t = eff(prod, tid)
        for o in t.get("outputs", []):
            if o.get("role") == "attribution": return o["path"]
    return None


def overall(prod):
    states = [eff(prod, i)["state"] for i in prod["order"] if not prod["tasks"][i].get("superseded_by")]
    if any(s in (IN_PROGRESS, COMPLETE) for s in states): return "in_progress"
    if any(s == AWAITING_AGENT for s in states): return "awaiting_agent"
    if any(s == NEEDS_APPROVAL for s in states): return "needs_approval"
    if any(s == PENDING for s in states): return "in_progress"
    rel = prod["tasks"].get("release.report")
    if rel and eff(prod, "release.report")["state"] == PASSED:
        dep = prod["tasks"].get("release.deploy")
        if dep and dep["state"] == SKIPPED: return "passed_not_deployed"
        if dep and not (dep.get("deployment") or {}).get("verified"): return "passed_deploy_unverified"
        return "passed"
    return "blocked" if any(s == BLOCKED for s in states) and not any(s == FAILED for s in states) else "failed"


def status(prod_or_id, store_dir=None):
    prod = store.load(prod_or_id, store_dir) if isinstance(prod_or_id, str) else prod_or_id
    tasks = []
    counts = {}
    for tid in prod["order"]:
        t = prod["tasks"][tid]
        counts[t["state"]] = counts.get(t["state"], 0) + 1
        tasks.append({k: t.get(k) for k in ("id", "title", "stage", "owner", "state", "depends_on", "reason", "error", "blocked_by", "superseded_by",
                                             "work_order_path", "install") if t.get(k) not in (None, [], "")})
    nxt = []
    for tid in prod["order"]:
        t = prod["tasks"][tid]
        if t["state"] == AWAITING_AGENT: nxt.append(f"agent: do {tid} ({t.get('work_order_path')}) then production_submit")
        if t["state"] == NEEDS_APPROVAL and not t.get("consolidated"): nxt.append(f"person: approve or decline {tid} — {t.get('reason')}")
    rr = replace_assets_request(prod)
    if rr and rr["ready"]:
        nxt.append(f"person: approve or decline replacing {len(rr['files'])} existing file(s) (production_approve task=replace_assets): "
                   + ", ".join(f["file"] for f in rr["files"])[:600])
    elif rr: nxt.append(f"waiting: the replace_assets approval is presented once {', '.join(rr['waiting_on'][:5])} settle(s)")
    lv = lifecycle.summary(prod)
    for d in ((prod.get("lifecycle") or {}).get("revision") and ["revision"]) or []: nxt.insert(0, "person: approve or decline the pending revision (production_decide)")
    if lv["stage"] == "decisions": nxt.insert(0, "person: review the Decision Room and approve the blueprint (production_decide)")
    v = _report.final(prod)
    from . import verification
    rs = verification.release_summary(prod)
    crash = prod.get("crash")
    if crash: nxt.insert(0, f"the last run stopped on an error in GITCRAFT itself ({crash['error']}): production_run resumes it; report it if it repeats")
    return {**({"crash": crash} if crash else {}), "production": prod["id"], "title": prod["spec"]["title"], "status": prod.get("status"), "stage": lv["stage"], "summary": lv["summary"],
            "verdict": v["verdict"], "verdict_reasons": v["reasons"] or None, "release_status": rs["release_status"],
            "release": {k: rs[k] for k in ("deployment", "functional", "security", "visual", "blockers", "unverified", "advisories", "verification_complete")}, "evaluation_target": (prod.get("evaluation") or {}).get("why"),
            "store": prod["store"], "project": _project(prod), "counts": counts, "next": nxt, "problems": prod.get("problems") or None, "tasks": tasks,
            "report": os.path.join(prod["store"], "REPORT.md"), "production_report": prod.get("production_report"),
            "plan_version": prod.get("plan_version", 1), "replace_assets": replace_assets_request(prod), "qa": _qa_view(prod)}


def _qa_view(prod):
    from . import qa
    A = qa.assurance(prod)
    return {"line": A["line"], "layers": A["layers"], "findings": [f for f in qa.findings(prod) if not f["status"].startswith("resolved")][:30]}
