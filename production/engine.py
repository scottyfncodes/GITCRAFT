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
changed after it passed (checked by a fingerprint of the project's files before release)."""
import concurrent.futures as cf, copy, hashlib, json, os, threading, time, traceback
from . import PENDING, IN_PROGRESS, AWAITING_AGENT, COMPLETE, PASSED, FAILED, BLOCKED, NEEDS_APPROVAL, SKIPPED, TERMINAL, VERSION
from . import inside_roots, roots, store_root
from . import intake, discovery, planner, executors, builtins, gates, store, report as _report

RESOURCES = {"browser": 2, "blender": 1}
FINGERPRINT_SKIP = {".git", "node_modules", "__pycache__", ".cache"}


# ---------------------------------------------------------------- helpers
def fingerprint(project):
    """SHA-256 over every file in the project (path + content hash): what a QA measurement was taken on."""
    if not project or not os.path.isdir(project): return None
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(project)):
        dirs[:] = sorted(x for x in dirs if x not in FINGERPRINT_SKIP)
        for f in sorted(files):
            p = os.path.join(d, f)
            try: h.update(os.path.relpath(p, project).encode() + b"\0" + builtins.sha256(p).encode() + b"\n")
            except OSError: pass
    return h.hexdigest()


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
    d = os.path.join(prod["store"], "tasks", tid); os.makedirs(d, exist_ok=True); return d


def _hex_rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


class HandoffError(Exception): pass


def resolve(prod, v):
    if isinstance(v, str) and v.startswith("$project"): return _project(prod) + v[len("$project"):]
    if isinstance(v, dict) and "$from" in v:
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
        out.append({"id": e["id"], "state": e["state"], "ship": e.get("ship"), "outputs": e.get("outputs", []), "result": e.get("result"),
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
        outs.append({"path": p, "role": o.get("role"), "format": o.get("format"), "ok": o.get("ok", True),
                     "sha256": o.get("sha256") or (builtins.sha256(p) if os.path.isfile(p) else None)})
    return outs


def _slim(res):
    """What the production record keeps of a department result (the full record stays in its .studio.json)."""
    drop = {"outputs", "stages", "request", "tools", "dependencies", "stderr", "catalog"}
    return {k: v for k, v in res.items() if k not in drop}


# ---------------------------------------------------------------- plan
def plan(prompt, project=None, overrides=None, store_dir=None):
    spec = intake.parse(prompt, project, overrides)
    if not spec["project"]["path"] and spec["deliverable"] in ("game", "app", "site"):
        spec["project"]["path"] = os.path.join(roots()[0], store.slugify(spec["title"]))
    p = spec["project"]["path"]
    if p and not inside_roots(p):
        raise PermissionError(f"GITCRAFT policy: project {p} is outside the workspace roots ({':'.join(roots())})")
    spec["project"]["exists"] = bool(p and os.path.isdir(p))
    essential = [q for q in spec["questions"] if q.get("essential")]
    disc = discovery.run(spec)
    pl = planner.build(spec, disc)
    measured = {t.get("criterion") for t in pl["tasks"].values()}
    dropped = [c["id"] for c in spec["acceptance"] if c["id"] not in measured and c["id"] != "release_ready"]
    if dropped:   # a criterion no task can measure is not silently "passed": it is removed with the reason recorded
        spec["acceptance"] = [c for c in spec["acceptance"] if c["id"] not in dropped]
        pl["decisions"].append(f"criteria not applicable to this plan (nothing measures them): {', '.join(dropped)}")
    problems = planner.validate(pl, disc)
    prod = {"id": store.new_id(spec["title"]), "spec": spec, "discovery": disc, "tasks": pl["tasks"], "order": pl["order"],
            "decisions": pl["decisions"], "parallel_groups": pl["parallel_groups"], "problems": problems,
            "readiness": planner.readiness(pl, disc), "status": "planned" if not problems and not essential else "needs_input"}
    store.create(prod, store_dir)
    store.event(prod, "planned", tasks=len(pl["tasks"]), problems=problems or None, blocked_up_front=list(prod["readiness"]) or None)
    return prod


# ---------------------------------------------------------------- run
def _recover(prod):
    """Make a resumed production consistent: interrupted tasks restart; passed work is reused only if intact."""
    for t in prod["tasks"].values():
        if t["state"] in (IN_PROGRESS, COMPLETE) and t["kind"] != "agent":
            if t["attempts"] and not t["attempts"][-1].get("finished"):
                t["attempts"][-1].update(finished=store.now(), status="interrupted")
            _set(prod, t, PENDING, reason="interrupted: the run stopped while this task was running; it runs again")
    # department artifacts live in the production store and must still be what passed; files in the project
    # (the build, integrated copies) legitimately change under remediation: their freshness is the release's
    # fingerprint check, not this one
    st = os.path.realpath(prod["store"]) + os.sep
    for t in list(prod["tasks"].values()):
        if t["state"] != PASSED: continue
        bad = [o["path"] for o in t.get("outputs", []) if o.get("sha256") and os.path.realpath(o["path"]).startswith(st)
               and (not os.path.isfile(o["path"]) or builtins.sha256(o["path"]) != o["sha256"])]
        if bad: _invalidate(prod, t, f"outputs missing or changed since they passed: {', '.join(os.path.basename(b) for b in bad[:4])}")


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
    for tid in prod["order"]:
        t = prod["tasks"][tid]
        if t["state"] != PENDING: continue
        states = {d: _dep_state(prod, d) for d in t["depends_on"]}
        dead = [d for d, s in states.items() if s == "dead"]
        if dead:
            _set(prod, t, BLOCKED, blocked_by=[eff(prod, d)["id"] for d in dead],
                 reason="upstream did not pass: " + ", ".join(f"{eff(prod, d)['id']} ({eff(prod, d)['state']})" for d in dead))
            continue
        if all(s == "ok" for s in states.values()): ready.append(t)
    return ready


def _stale_qa(prod, t):
    """Before a release task starts: QA evidence measured on an older project state is re-measured."""
    if t["stage"] != "release": return False
    fp = fingerprint(_project(prod)); stale = False
    for tid in prod["order"]:
        q = eff(prod, tid)
        if q["kind"] != "agent" and q["stage"] in ("qa", "release") and q["state"] == PASSED and q.get("measured_fingerprint") and q["measured_fingerprint"] != fp and q["id"] != t["id"]:
            q["attempts"].append({"n": len(q["attempts"]) + 1, "status": "stale", "note": "the project changed after this passed: re-measuring", "at": store.now()})
            _set(prod, q, PENDING, reason="stale evidence: the project changed after this check passed", outputs=[], result=None, gate_results=None)
            stale = True
    return stale


def run(pid, max_workers=4, max_seconds=None, store_dir=None, on_event=None):
    prod = store.load(pid, store_dir)
    if prod.get("problems"):
        return dict(status(prod), refused="the plan has problems; correct the spec (production_plan with overrides) before running")
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        _recover(prod); prod["status"] = "running"; store.save(prod)
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
                        if len(running) >= max_workers: break
                        work, early = _prepare(prod, t)
                        if early is not None: _finish(prod, t, early); continue
                        for r in t["resources"]: in_use[r] += 1
                        running[t["id"]] = pool.submit(_timed, work)
                    store.save(prod)
                if not running:
                    if not _ready_tasks(prod): break
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
        prod["status"] = overall(prod); store.save(prod)
        store.event(prod, "run_stopped", status=prod["status"])
        _report.write(prod)
        return status(prod)


def _issue(prod, t):
    wo = t["work_order"] or {}
    if wo.get("approval") and not prod["spec"]["authorisations"].get(wo["approval"]) and not t.get("approved"):
        _set(prod, t, NEEDS_APPROVAL, reason=f"{wo['approval']} needs a person's approval (production_approve)"); return
    d = _task_dir(prod, t["id"])
    h = _handoff(prod, t, {})
    if t["id"] == "build" or t["stage"] == "integration":
        integ = eff(prod, "integrate.assets") if "integrate.assets" in prod["tasks"] else None
        h["integrated_assets"] = [{k: m[k] for k in ("dest_rel", "role", "format", "task")} for m in ((integ or {}).get("result") or {}).get("integrated", [])]
    order = {"production": prod["id"], "task": t["id"], "title": t["title"], "owner": t["owner"], "out_dir": d, "project": _project(prod),
             **{k: v for k, v in wo.items() if k != "approval"}, "handoff": h,
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
    except (HandoffError, OSError, ValueError) as e:
        return None, {"status": "failed", "failure": "handoff", "error": f"hand-off: {e}"}
    _handoff(prod, t, params)
    if t["stage"] in ("qa", "release"): t["measured_fingerprint"] = fingerprint(_project(prod))
    kind, dept, action, timeout = t["kind"], t["department"], t["action"], t["timeout"]
    if kind == "studio":
        req = dict({k: v for k, v in params.items() if v is not None}, out_dir=out_dir, tags=[f"production:{prod['id']}"])
        req.setdefault("name", t["id"].replace(".", "_"))
        return (lambda: executors.studio_run(dept, action, req, timeout=timeout)), None
    if kind == "forgecraft":
        req = dict(params, handoff_dir=out_dir, wait=True)
        def forge():
            r = executors.forgecraft_call(action, req, timeout=timeout)
            return dict(r, status="ok") if r.get("status") in ("done", "done_with_fallback") else r
        return forge, None
    if kind == "designcraft":
        return (lambda: executors.designcraft_assess(params["project"], os.path.join(out_dir, "designcraft.json"), timeout=timeout)), None
    if kind == "builtin":
        if action == "release": return None, _release(prod, t, out_dir)   # reads the whole production: main thread
        ctx = {"prod": {"id": prod["id"]}, "task": copy.deepcopy(t), "project": _project(prod), "params": params, "out_dir": out_dir,
               "upstream": copy.deepcopy(_upstream(prod, t)), "auth": dict(prod["spec"]["authorisations"]), "approved": t.get("approved"),
               "inside_roots": inside_roots, "previous_manifest": copy.deepcopy((t.get("last_result") or {}).get("integrated"))}
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
    if cls == "approval":
        _set(prod, t, NEEDS_APPROVAL, reason=res.get("reason"), approval=res.get("approval")); return
    if cls == "blocked":
        _set(prod, t, BLOCKED, reason=res.get("reason"), install=res.get("install"), alternatives=res.get("alternatives")); return
    if cls in ("execution",) and len([a for a in t["attempts"] if a.get("outcome") == "execution"]) <= t["retries"]:
        _set(prod, t, PENDING, reason=f"retrying after an execution failure: {att['error']}"); return
    if cls in ("execution", "request") or res.get("failure") in ("handoff", "conflict"):
        _set(prod, t, FAILED, failure=res.get("failure") or cls, error=att["error"],
             reason="not retried: the request itself is the problem" if cls == "request" else None); return
    # the department ran: the task is complete; only its gate decides passed
    _set(prod, t, COMPLETE)
    gr = gates.evaluate(t, res, {"project": _project(prod), "integrated": _integrated(prod)})
    t["gate_results"] = gr
    if t.get("advisory"):   # recorded evidence that never blocks (and is never "remediated")
        _set(prod, t, PASSED if res.get("status") == "ok" else FAILED, reason="advisory"); return
    if all(g["ok"] for g in gr):
        _set(prod, t, PASSED); return
    _set(prod, t, FAILED, failure="quality", error="; ".join(f"{g['condition']}: {g.get('detail') or g.get('measured')}" for g in gr if not g["ok"])[:1500])
    _remediate(prod, t, res, gr)


def _integrated(prod):
    if "integrate.assets" not in prod["tasks"]: return []
    return (eff(prod, "integrate.assets").get("result") or {}).get("integrated") or []


def _remediate(prod, t, res, gr):
    """A failed QA gate becomes a fix work order and a re-verification of the modified project."""
    if t["stage"] not in ("qa", "release") or t["kind"] == "builtin" and t["action"] == "release": return
    root = t.get("chain") or t["id"]; rnd = (t.get("round") or 0) + 1
    maxr = prod["spec"]["quality"].get("max_rounds", 2)
    if rnd > maxr:
        t["exhausted"] = True
        store.event(prod, "quality_gate_exhausted", task=t["id"], rounds=rnd - 1); return
    fix_id, rv_id = f"fix.{root}.r{rnd}", f"{root}.r{rnd}"
    items = gates.remediation(t, res, gr)
    fix = planner.T(fix_id, f"Fix what {root} found (round {rnd})", t["stage"], "agent", deps=[],
                    work_order={"brief": f"{t['title']} failed its gate. Fix the project so it passes; the check then runs again on the modified files.",
                                "findings": items, "instructions": ["Change the project to address the findings (keep every existing feature).",
                                                                    "Submit the files you changed; the re-verification measures the new project state."],
                                "expected": []})
    fix.update(fix_for=t["id"], failed_fingerprint=t.get("measured_fingerprint"), chain=root, round=rnd)
    rv = planner.T(rv_id, f"{t['title']} — re-verification {rnd}", t["stage"], t["kind"], department=t["department"], action=t["action"],
                   params=copy.deepcopy(t["params"]), deps=[fix_id], gate=copy.deepcopy(t["gate"]), resources=t["resources"], retries=t["retries"],
                   timeout=t["timeout"], criterion=t.get("criterion"))
    rv.update(chain=root, round=rnd, reverifies=t["id"])
    prod["tasks"][fix_id] = fix; prod["tasks"][rv_id] = rv
    i = prod["order"].index(t["id"]) + 1
    prod["order"][i:i] = [fix_id, rv_id]
    t["superseded_by"] = rv_id
    store.event(prod, "remediation", task=t["id"], fix=fix_id, reverify=rv_id, round=rnd, findings=len(items))


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
        checks, outs = gates.check_expected(wo.get("expected", []), d, proj, inside_roots)
        for f in files or []:
            p = f if os.path.isabs(f) else next((c for c in (os.path.join(d, f), os.path.join(proj or d, f)) if os.path.exists(c)), os.path.join(proj or d, f))
            if not inside_roots(p): checks.append({"name": f"{f} is inside the workspace roots", "ok": False, "detail": p}); continue
            if not os.path.exists(p): checks.append({"name": f"{f} exists", "ok": False, "detail": "the submission names a file that is not there"}); continue
            if os.path.isfile(p) and not any(o["path"] == p for o in outs):
                v = executors.validate_file(p)
                checks.append({"name": f"{os.path.relpath(p, proj) if proj and p.startswith(proj) else f} opens as {v.get('format')}", "ok": v.get("ok", False), "detail": v.get("error")})
                if v.get("ok"): outs.append({"path": p, "role": "submitted", "format": v.get("format"), "ok": True})
        if t.get("fix_for"):
            now_fp = fingerprint(proj)
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
            _set(prod, t, PASSED)
        else:
            # an agent submission that does not validate stays open: the work order is still owed
            _set(prod, t, AWAITING_AGENT, reason="submission rejected: " + "; ".join(c["name"] + (f" ({c['detail']})" if c.get("detail") else "") for c in checks if not c["ok"])[:1200])
        store.event(prod, "submitted", task=task, accepted=t["state"] == PASSED, files=len(files or []))
        store.save(prod)
    if run_after and t["state"] == PASSED: return run(pid, max_workers=max_workers, store_dir=store_dir)
    return dict(status(prod), submission={"task": task, "accepted": t["state"] == PASSED, "checks": checks})


def _verify_deploy(url, evidence):
    if not evidence: return {"ok": False, "detail": "no evidence: a deployment is never recorded as live without a check against it"}
    p = evidence if os.path.isabs(evidence) else None
    if not p or not os.path.isfile(p): return {"ok": False, "detail": f"evidence {evidence!r} is not a file"}
    try: rec = json.load(open(p))
    except ValueError: return {"ok": False, "detail": "evidence is not a check record (JSON)"}
    target = json.dumps(rec.get("request") or {})
    if rec.get("status") != "ok": return {"ok": False, "detail": f"the evidence check did not pass ({rec.get('status')})"}
    if url not in target: return {"ok": False, "detail": "the evidence check ran against a different target than the submitted URL"}
    return {"ok": True, "detail": f"{rec.get('department')}.{rec.get('action')} passed against {url}"}


def approve(pid, task, approved=True, note=None, store_dir=None):
    prod = store.load(pid, store_dir)
    with store.lock(prod):
        prod = store.load(pid, store_dir)
        t = prod["tasks"].get(task)
        if not t or t["state"] != NEEDS_APPROVAL: raise ValueError(f"{task} is not waiting for approval")
        store.event(prod, "approval", task=task, approved=approved, note=note)
        prod.setdefault("decisions", []).append(f"{'approved' if approved else 'declined'}: {task}" + (f" — {note}" if note else ""))
        if approved:
            t["approved"] = True; t["last_result"] = t.get("result"); _set(prod, t, PENDING, reason="approved")
        else:
            _set(prod, t, SKIPPED, reason=f"declined by a person{': ' + note if note else ''}")
        store.save(prod)
    return status(prod)


# ---------------------------------------------------------------- release, status
def _release(prod, t, out_dir):
    acc = _report.acceptance(prod, exclude={"release_ready", "deployment"})
    fp = fingerprint(_project(prod))
    stale = [q["id"] for q in (eff(prod, i) for i in prod["order"]) if q["stage"] in ("qa", "release") and q["state"] == PASSED
             and q.get("measured_fingerprint") not in (None, fp)]
    checks = [{"name": f"criterion {a['id']}: {a['text']}", "ok": a["status"] == "passed", "detail": a.get("why")} for a in acc]
    checks.append({"name": "every QA result was measured on the build being released", "ok": not stale, "detail": stale or None})
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
        if t["state"] == NEEDS_APPROVAL: nxt.append(f"person: approve or decline {tid} — {t.get('reason')}")
    return {"production": prod["id"], "title": prod["spec"]["title"], "status": prod.get("status"), "store": prod["store"], "project": _project(prod),
            "counts": counts, "next": nxt, "problems": prod.get("problems") or None, "tasks": tasks,
            "report": os.path.join(prod["store"], "REPORT.md")}
