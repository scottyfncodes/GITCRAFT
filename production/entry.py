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
from . import roots, inside_roots, engine, maturity, store

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


def start(text, project=None, store_dir=None, overrides=None, issues=None):
    r = route(text, project)
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
        pr = engine.plan(r["request"], proj, overrides, store_dir=store_dir)
        return dict(engine.lifecycle_view(pr), routing=dict(r, maturity="new", workflow="build", why=maturity.WORKFLOW["build"]))
    intent, because = maturity.intent(r["request"], a["maturity"])
    question = None
    if intent == "update" and _vague(r["request"]) and a["maturity"] == "finished":
        question = "This project looks finished. What should change? (GITCRAFT changes only what you name, plus the fixes it needs.)"
    kind = a["kind"]
    prompt = (r["request"] if len(r["request"]) >= 12 else "") or f"{maturity.WORKFLOW[intent].split(':')[0].capitalize()} this existing {kind}"
    if kind and not re.search(r"\b(game|app|application|site|website|tool|dashboard)\b", prompt, re.I): prompt += f" (an existing {kind})"
    mode = {"existing": True, "maturity": a["maturity"], "kind": kind, "workflow": intent, "because": because, "confidence": a["confidence"],
            "request": r["request"] if not _vague(r["request"]) else None, "question": question, "repository": r["repository"]}
    ov = {"mode": mode, "deliverable": kind or "app"}
    if kind == "game" and a.get("engines"): ov["platform"] = {"engine": next((e for e in a["engines"] if e != "canvas"), a["engines"][0])}
    if overrides:
        from .intake import merge
        ov = merge(ov, overrides)
    pr = engine.plan(prompt, proj, ov, store_dir=store_dir, assessment=a)
    return dict(engine.lifecycle_view(pr), routing=dict(r, maturity=a["maturity"], kind=kind, confidence=a["confidence"], workflow=intent,
                                                       because=because, why=maturity.WORKFLOW[intent], question=question))
