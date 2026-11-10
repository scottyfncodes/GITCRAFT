"""RUN GITCRAFT: one entry point for whatever the person brings.

  start(text, project=None)
    text      anything: a sentence, a rough idea, a detailed spec, a pasted master prompt, a GitHub URL, a local
              path, or nothing but "Run GITCRAFT" while a project is open
    project   the project folder, when the agent already knows it (the session's repository)

  1. Where is the project?   a local path in the text or `project`; a repository URL → an existing clone in the
                             workspace roots (matched by its git remote), else `needs_checkout` with the exact
                             clone command (the sandbox has no network: the agent clones, then calls again)
  2. What state is it in?    maturity.assess: new | partial | nearly_complete | finished, game | app | site,
                             with evidence and a confidence level (read-only)
  3. What was asked?         maturity.intent: build | continue | complete | update | fix | review
  4. Which workflow?         a new idea → the New Build (optional Recon, Discovery, Decision Room...); an existing
                             project → the same lifecycle in its maturity's mode: nothing is scaffolded, rebranded,
                             re-iconed or redesigned unless the Decision Room approves it, and qa.preserve checks
                             that existing files, secrets, CI/deploy, game assets and saves survived the change
  5. Only what is required   a finished project with no change named gets one essential question; everything
                             else has a recommended default in the Decision Room

Returns the lifecycle view (stage, summary, Decision Room, Discovery Report) plus the routing it chose and why."""
import os, re
from . import roots, inside_roots, engine, maturity, store, understanding

REPO = re.compile(r"(?:https?://)?(?:www\.)?github\.com[/:]([\w.-]+)/([\w.-]+?)(?:\.git)?(?=[/#?\s]|$)", re.I)
PATH = re.compile(r"(?<![\w:/])(/[\w.@~+-]+(?:/[\w.@~+-]+)+)")
TRIGGER = re.compile(r"^\s*(?:please\s+)?run\s+gitcraft\b[\s:,.!-]*", re.I)


def _find_clone(owner, name):
    """A clone of owner/name already in the workspace roots (one level deep), matched by its git remote."""
    want = f"{owner}/{name}".lower()
    for r in roots():
        cands = [r] + [os.path.join(r, d) for d in sorted(os.listdir(r)) if os.path.isdir(os.path.join(r, d, ".git"))] if os.path.isdir(r) else []
        for c in cands:
            url = maturity._git(c, "remote", "get-url", "origin") or ""
            if re.sub(r"\.git$", "", url.lower()).endswith(want): return c
    return None


def route(text, project=None):
    """→ {project, repository, source, request, problem?}: where the project is and what the person said, nothing created."""
    raw = text or ""
    request = TRIGGER.sub("", raw).strip()
    out = {"text": raw, "request": request, "repository": None, "project": project, "source": None}
    m = REPO.search(raw)
    if m:
        out["repository"] = f"{m.group(1)}/{m.group(2)}"
        request = (request.replace(m.group(0), " ")).strip(" .,:;-")
        if not project:
            found = _find_clone(m.group(1), m.group(2))
            if found: out["project"] = found
            else:
                dest = os.path.join(roots()[0], m.group(2))
                out["problem"] = "needs_checkout"
                out["next"] = (f"clone the repository into the workspace, then run GITCRAFT again with project={dest}: "
                               f"git clone https://github.com/{m.group(1)}/{m.group(2)} {dest} (attach it to the session first if access is needed)")
        out["source"] = "repository"
    if not out["project"]:
        pm = PATH.search(raw)
        if pm and os.path.isdir(pm.group(1)):
            out["project"] = pm.group(1); request = request.replace(pm.group(1), " ").strip(" .,:;-"); out["source"] = "path"
    if out["project"] and not inside_roots(out["project"]):
        out["problem"] = "outside_roots"; out["next"] = f"GITCRAFT policy: {out['project']} is outside the workspace roots ({':'.join(roots())}); copy it into the workspace"
    out["request"] = " ".join(request.split())
    out["source"] = out["source"] or ("project" if out["project"] else "idea")
    return out


def _vague(request):
    """True when the person named no change (e.g. just 'Run GITCRAFT', a URL, 'take a look')."""
    r = re.sub(r"\b(on|for|this|the|my|it|project|repo|repository|app|game|site|please|now|here)\b", " ", (request or "").lower())
    return len(r.split()) < 2


def _issues(issues):
    """Open GitHub issues the agent fetched (number, title, labels, body?) → defects (bugs) and requests (the rest)."""
    out = {"defects": [], "requests": []}
    for i in issues or []:
        if not isinstance(i, dict) or not i.get("title"): continue
        labels = [str(l.get("name") if isinstance(l, dict) else l).lower() for l in i.get("labels") or []]
        item = {"what": f"#{i.get('number', '?')} {i['title'][:100]}", "where": "GitHub issue", "evidence": ", ".join(labels) or "open issue"}
        (out["defects"] if any(re.search(r"bug|defect|crash|regression|broken", l) for l in labels) or re.search(r"\b(bug|crash|broken|error|fails?)\b", i["title"], re.I)
         else out["requests"]).append(item)
    return out


REPORT = re.compile(r"^(?:a\s+|the\s+|full\s+|project\s+)*report\b", re.I)


def report(r, refresh="quick"):
    """"Run GITCRAFT report": the read-only project report across every department (project_report.generate)."""
    from . import project_report
    target = r["project"] or r["repository"]
    if not target:
        return {"status": "needs_input", "routing": dict(r, workflow="report"), "question": "Which project should the report cover? Give its folder or GitHub repository.",
                "why": "a report reads one project's results from every department"}
    R = project_report.generate(target, refresh=refresh)
    note = (f"Reported from the departments' recorded histories only; for Discovery and refreshed analysis, {r['next']}" if r.get("problem") == "needs_checkout" else None)
    return {"status": "report", "note": note, "routing": dict(r, workflow="report", why="Run GITCRAFT report: read-only, every department, nothing built, changed, merged or deployed"),
            "report": summary(R), "markdown": project_report.markdown(R)}


def summary(R):
    return {"report_id": R["report_id"], "title": R["title"], "health": R["health"], "summary": R["summary"],
            "departments": [{"id": d["id"], "status": d["status"], "score": (d.get("score") or {}).get("value"), "findings": len(d["findings"])} for d in R["departments"]],
            "actions": {p: [a["title"] for a in R["actions"] if a["priority"] == p][:8] for p in ("P0", "P1", "P2", "P3")},
            "next_actions": R["next_actions"], "changes": R["changes"], "paths": R["paths"]}


def _stated_kind(text):
    """'my e-reader app', 'this game', 'our website': the kind the person named, if exactly one."""
    t = text or ""
    found = {k for k, pat in (("game", r"\b(game|platformer|roguelike|shooter)\b"), ("app", r"\b(app|application|web app|tool|dashboard)\b"),
                              ("site", r"\b(website|web site|landing page|homepage|blog)\b"),
                              ("tool", r"\b(cli|command[- ]line tool|library|toolchain|toolkit|sdk|mcp server)\b")) if re.search(pat, t, re.I)}
    if found == {"app", "tool"} and not re.search(r"\b(app|application|web app|dashboard)\b", t, re.I): found = {"tool"}   # "a CLI tool" is a tool
    return found.pop() if len(found) == 1 else None


def start(text, project=None, store_dir=None, overrides=None, issues=None):
    r = route(text, project)
    if REPORT.match(r["request"] or ""):   # a repository that is not cloned is reported from the departments' histories
        if r.get("problem") == "outside_roots": return {"status": r["problem"], "routing": r, "next": r["next"]}
        return report(r, (overrides or {}).get("refresh", "quick") if isinstance(overrides, dict) else "quick")
    if r.get("problem"):
        return {"status": r["problem"], "routing": r, "next": r["next"]}
    proj = r["project"]
    a = maturity.assess(proj) if proj else {"existing": False, "maturity": "new", "confidence": "high", "evidence": ["no project: a new idea"]}
    if issues is not None and a.get("existing"):
        iss = _issues(issues)
        a["inventory"]["defects"] += iss["defects"]; a["inventory"]["requests"] = iss["requests"]
        a["evidence"].append(f"GitHub: {len(issues)} open issues read ({len(iss['defects'])} bugs, {len(iss['requests'])} requests)")
        a["issues_read"] = True
    if not a["existing"]:
        if len((r["request"] or "").strip()) < 12:
            return {"status": "needs_input", "routing": r, "question": "What would you like to make? A sentence is enough: who it is for and what it should do.",
                    "why": "a new project needs an idea to plan from"}
        alone = understanding.standalone(r["request"])
        if alone and not (overrides or {}).get("deliverable"):   # assets and nothing else: the departments make them, no production around them
            return direct(r, alone)
        pr = engine.plan(r["request"], proj, overrides, store_dir=store_dir)
        u = understanding.model(r["request"], a, {"assignment": "build", "workflow": "build", "focus": None, "because": "a new project"}, kind=pr["spec"]["deliverable"])
        return dict(engine.lifecycle_view(pr), understanding=u, routing=dict(r, maturity="new", assignment="build", workflow="build", why=maturity.WORKFLOW["build"]))
    reading = understanding.classify(r["request"], a["maturity"])
    intent, because = reading["workflow"], reading["because"]
    question = reading.get("question")
    if intent == "update" and _vague(r["request"]) and a["maturity"] == "finished":
        question = "This project looks finished. What should change? (GITCRAFT changes only what you name, plus the fixes it needs.)"
    stated = _stated_kind(r["request"])   # the person's own words beat the heuristic
    kind = stated or a["kind"]
    if reading.get("focus") == "gameplay" and kind != "game":   # "the controls feel sluggish" in an app is about the interface
        reading = dict(reading, assignment="polish" if reading["assignment"] == "gameplay" else reading["assignment"], focus="visual")
    prompt =(r["request"] if len(r["request"]) >= 12 else "") or f"{maturity.WORKFLOW[intent].split(':')[0].capitalize()} this existing {kind}"
    if kind and not re.search(r"\b(game|app|application|site|website|tool|toolkit|dashboard|library|cli)\b", prompt, re.I): prompt += f" (an existing {kind})"
    u = understanding.model(r["request"], a, reading, kind=kind)
    mode = {"existing": True, "maturity": a["maturity"], "kind": kind, "workflow": intent, "because": because, "confidence": a["confidence"],
            "assignment": reading["assignment"], "focus": reading.get("focus"), "preserve": u["preserve"], "done_when": u["done_when"],
            "kind_confidence": "stated" if stated else a.get("kind_confidence"),
            "kind_evidence": [f"you called it {'an' if stated == 'app' else 'a'} {stated}"] if stated else a.get("kind_evidence"),
            "request": r["request"] if not _vague(r["request"]) else None, "question": question, "repository": r["repository"]}
    ov = {"mode": mode, "deliverable": kind or "app"}
    if a.get("name"): ov["title"] = a["name"]   # an existing project is called what it calls itself
    if kind == "game" and a.get("engines"): ov["platform"] = {"engine": next((e for e in a["engines"] if e != "canvas"), a["engines"][0])}
    if overrides:
        from .intake import merge
        ov = merge(ov, overrides)
    pr = engine.plan(prompt, proj, ov, store_dir=store_dir, assessment=a)
    return dict(engine.lifecycle_view(pr), understanding=u,
                routing=dict(r, maturity=a["maturity"], kind=kind, confidence=a["confidence"], assignment=reading["assignment"], focus=reading.get("focus"),
                             workflow=intent, because=because, why=understanding.SAY.get(reading["assignment"]) or maturity.WORKFLOW[intent], question=question))


CRAFT = [(r"\b(logos?|icons?|wordmarks?|illustrations?|vector art|svg)\b", "vectorcraft", "draw it as vectors, export SVG and PNG, then look at the export"),
         (r"\b(posters?|flyers?|brochures?|business cards?|menus?|layouts?)\b", "designcraft", "lay it out, export PDF and a page render, then look at it"),
         (r"\b(photos?|retouch|image edit|composite|psd)\b", "photocraft", "edit the raster, export PNG, then look at it"),
         (r"\b(animated titles?|motion graphics?|lower thirds?|title sequence)\b", "effectcraft", "animate it, render a preview, then watch it")]


def direct(r, alone):
    """Assets and nothing else: no production, no scaffold, no icon. The Studio's router names the department and action
    for each; the agent calls them, looks at the result, and stops."""
    import sys
    from . import REPO
    if os.path.join(REPO, "studio") not in sys.path: sys.path.insert(0, os.path.join(REPO, "studio"))
    try:
        from core import routing
        res = routing.route(r["request"], limit=4)
    except Exception as e:   # the router is advice: without it the agent still knows what kind of job this is
        res = {"suggestions": [], "error": f"{type(e).__name__}: {e}"}
    # only what the request actually names: an action matched by its own words or by a value it accepts (a department's
    # keyword alone is a guess), and one step for each named value ("a jump sound and a coin sound" is two sounds)
    steps = []
    for sg in res.get("suggestions", []):
        why, params = sg.get("why") or {}, sg.get("params") or {}
        if not (why.get("action_words") or why.get("parameter_values")): continue
        vals = why.get("parameter_values") or []
        key = next((k for k, v in params.items() if v in vals), None)
        for v in (vals if key and len(params) == 1 else [None]):
            steps.append({"tool": f"{sg['department']}_{sg['action']}", "params": dict(params, **({key: v} if v else {})),
                          "because": ", ".join((why.get("action_words") or []) + vals)})
    if res.get("three_d"):   # a model is the 3D Department's: it routes, builds with MeshCraft, engine-checks and records the licence
        steps = [{"tool": "forgecraft route, then forgecraft generate", "params": {"brief": r["request"]}, "because": ", ".join(res["three_d"].get("matched") or [])}]
    for pat, tool, what in CRAFT:   # the 2D ArtCraft tools are not Studio departments, so the Studio's router does not know them
        m = re.search(pat, r["request"], re.I)
        if m and not any(st["tool"].startswith(tool.split()[0]) for st in steps):
            steps.append({"tool": tool, "params": {}, "because": m.group(0), "note": what})
    return {"status": "direct", "assignment": "asset", "request": r["request"],
            "routing": dict(r, assignment="asset", workflow="direct", because=alone["because"],
                            why="a request for assets alone: the departments make them directly; nothing is scaffolded, branded or deployed around them"),
            "understanding": {"assignment": "asset", "workflow": "direct", "focus": "asset", "because": alone["because"], "desired": r["request"], "preserve": [],
                              "done_when": "each asset opens as its format, has been looked at or listened to, and has its provenance record (.studio.json)",
                              "proof": "the department's own validation plus the exported file, inspected"},
            "steps": steps,
            "next": "Call the suggested department tool for each asset (studiocraft; ForgeCraft for 3D), check the output yourself, and hand the files over. "
                    "To build a product around them instead, say what the product is."}
