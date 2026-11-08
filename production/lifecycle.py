"""THE PROJECT LIFECYCLE: Idea → Recon (optional) → Discovery → Decisions → Approved → Building → Verified → Delivered.

One record per project, in the production store (production.json), whichever stage it is in. Nothing here runs a
department; it decides what a person must see and approve, and what the engine may do.

  brief(text)          the person's idea in their words → objective, outcome, requirements, constraints, open questions
                       (a sentence, a rough idea, a full spec, a pasted master prompt, a GitHub URL or a project folder)
  decisions(...)       the Decision Room: only material choices (scope, architecture, design and icon direction,
                       engineering profile, cost, deployment), each with a plain-language question, a recommended
                       default, the options and their trade-offs, and what in the spec it changes
  discovery_report()   the read-only Discovery Report (8 sections), written to DISCOVERY.md
  blueprint(prod)      the approved decisions + scope, frozen with a hash: the source of truth for the build
  material(old, new)   whether a change to the spec is a material deviation (needs renewed approval)
  stage(prod)          where the project is, in the lifecycle's words, and a one-line summary a person can read

The engine enforces the boundaries: `run` refuses until the blueprint is approved, and a material revision pauses
the build until it is approved again. docs/production.md describes the workflow."""
import copy, hashlib, json, os, re
from . import store

STAGES = ["idea", "recon", "discovery", "decisions", "approved", "building", "verified", "delivered"]
SIDE_STATES = ["parked", "discarded", "paused", "revision", "blocked", "failed"]

REQ = re.compile(r"\b(must|should|needs? to|has to|have to|require[sd]?|want|include|support|with)\b", re.I)
CON = re.compile(r"\b(no |not |never|without|only|budget|deadline|by (monday|tuesday|wednesday|thursday|friday|next)|offline|free|cheap|privacy|private)\b", re.I)


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+\s*(?:[-*•]|\d+[.)])?\s*", text.strip())
    return [" ".join(p.split()) for p in parts if p and len(p.split()) >= 2]


def brief(text, project=None, source=None):
    """The idea in the person's own terms. Never invents a requirement: every item is a sentence they wrote."""
    t = text.strip()
    s = _sentences(t)
    repo = re.search(r"(?:https?://)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?(?:[/#?\s]|$)", t)
    kind = ("repository" if repo else "project" if project and os.path.isdir(project) else
            "master prompt" if len(t) > 1200 or len(s) > 12 else "specification" if len(s) > 4 else "idea" if len(s) > 1 else "sentence")
    return {"text": t, "kind": source or kind, "objective": s[0] if s else t[:200],
            "outcome": next((x for x in s if re.search(r"\b(so that|so I can|so we can|goal|outcome|result|in order to)\b", x, re.I)), None),
            "requirements": [x for x in s[1:] if REQ.search(x)][:20] or ([s[0]] if s else []),
            "constraints": [x for x in s if CON.search(x)][:12],
            "repository": f"{repo.group(1)}/{repo.group(2)}" if repo else None, "project": project}


# ---------------------------------------------------------------- the Decision Room
def _d(did, title, question, recommended, options, sets, why, kind="choice"):
    return {"id": did, "title": title, "question": question, "recommended": recommended, "options": options, "sets": sets,
            "why": why, "kind": kind, "status": "open", "answer": None}


def decisions(spec, disc, icon_state=None):
    """Material decisions only. Each maps an answer to spec overrides (`sets`: {answer: overrides})."""
    d, proj = spec["deliverable"], disc.get("project") or {}
    web = d in ("game", "app", "site")
    out = []
    feats = [k for k, v in spec["features"].items() if v and k not in ("deploy",)]
    assets = [k for k, v in spec["assets"].items() if v]
    mode = spec.get("mode") or {}
    existing = bool(mode.get("existing"))
    if existing:
        from .maturity import WORKFLOW
        mat = (mode.get("maturity") or "").replace("_", " ")
        wf = mode.get("workflow") or "update"
        opts = [{"value": w, "label": WORKFLOW[w].split(":")[0], "tradeoff": WORKFLOW[w].split(":", 1)[1].strip()} for w in ("continue", "complete", "update", "fix", "review")]
        opts.sort(key=lambda o: o["value"] != wf)
        if mode.get("question") and not mode.get("request"):
            out.append(_d("request", "What should change", mode["question"], None, [], {"$answer": {"mode": {"request": "$answer"}}},
                          "essential: the project looks finished, so GITCRAFT changes only what you name", kind="question"))
        out.append(_d("scope", "What GITCRAFT will do", f"This looks like a {mat} {mode.get('kind') or spec['deliverable']} ({mode.get('confidence')} confidence). "
                      f"{WORKFLOW[wf].split(':', 1)[1].strip().capitalize()}" + (f": {mode['request']}" if mode.get("request") else "") + "?",
                      wf, opts, {o["value"]: {"mode": {"workflow": o["value"]}} for o in opts},
                      f"read as '{wf}' because of {mode.get('because')}; the Discovery Report shows the evidence. Existing work is preserved (qa.preserve)."))
    else:
        out.append(_d("scope", "What gets built", f"Build {spec['title']} as a {spec['dimension'].upper()} {d}"
                      + (f" ({', '.join(spec['genres'])})" if spec.get("genres") else "") + f" with {', '.join(feats + assets) or 'the core features'}?",
                      "as_interpreted", [{"value": "as_interpreted", "label": "Yes, as described", "tradeoff": "what the plan below makes"},
                                         {"value": "revise", "label": "Change the scope", "tradeoff": "answer with overrides (production_revise) before approving"}],
                      {}, "The scope decides every department's work; the assumptions list what was filled in.", kind="confirm"))
    if web:
        eng = spec["platform"].get("engine")
        found = proj.get("engines") or []
        rec = found[0] if found else (eng or ("three" if spec["dimension"] == "3d" else "canvas" if d == "game" else "vanilla"))
        opts = [{"value": rec, "label": f"{rec} (recommended)", "tradeoff": "keeps the existing code" if found else "no framework dependency; smallest, fastest load" if rec in ("canvas", "vanilla") else "suits what was asked"}]
        for alt, tr in (("vanilla", "plain HTML/JS: nothing to install, simplest to host"), ("react", "component model for larger UIs; adds a build step"),
                        ("phaser", "game framework: physics, scenes, input; ~1 MB"), ("three", "3D rendering")):
            if alt != rec and not (d != "game" and alt == "phaser") and not (spec["dimension"] != "3d" and alt == "three"): opts.append({"value": alt, "label": alt, "tradeoff": tr})
        if existing: opts = opts[:1] + [dict(o, tradeoff=o["tradeoff"] + " — a migration of working code: needs a strong reason") for o in opts[1:]]
        out.append(_d("architecture", "How it is built", f"{'Keep building' if existing else 'Build it'} with {rec}?", rec, opts[:4],
                      {o["value"]: {"platform": {"engine": o["value"]}} for o in opts[:4]},
                      "Existing code is reused, never rewritten." if found else "The lightest stack that does the job is the default."))
        keep_design = existing or bool(proj.get("assets", {}).get("vector"))
        ident = bool(spec["assets"].get("identity"))
        out.append(_d("design", "Design direction", "Give it an original visual identity (palette, logo) derived from the idea?" if not keep_design
                      else "Keep the project's existing look and brand (no redesign)?",
                      ("original" if ident else "keep") if not keep_design else "keep",
                      [{"value": "original", "label": "Original identity", "tradeoff": "a palette and logo made for this app with VectorCraft"},
                       {"value": "keep", "label": "Keep it simple" if not keep_design else "Keep what the project has",
                        "tradeoff": "no separate brand work; the build picks a clean palette" if not keep_design else "no new brand work; the build follows existing assets"}],
                      {"original": {"assets": {"identity": True}}, "keep": {"assets": {"identity": False}}},
                      "Every app keeps its own identity; there is no shared GITCRAFT style."))
        st = (icon_state or {}).get("status", "none")
        if existing:   # an existing project's icon is never replaced unless the person asks
            out.append(_d("app_icon", "App icon", f"Leave the project's icon as it is? ({(icon_state or {}).get('reason') or 'no change'})", "leave",
                          [{"value": "leave", "label": "Leave it", "tradeoff": "no icon work"},
                           {"value": "new", "label": "Design a new icon", "tradeoff": "concepts to choose from, then the full PWA/Apple/favicon set"}]
                          + ([{"value": "refine", "label": "Refine the existing icon", "tradeoff": "keeps its idea; a clean 1024 master and the full set"}] if st == "candidate" else []),
                          {"leave": {"icon": {"required": False}}, "new": {"icon": {"required": True, "mode": "new"}},
                           "refine": {"icon": {"required": True, "mode": "refine", "existing": (icon_state or {}).get("best")}}},
                          "Existing projects keep their icon unless you ask."))
        else:
            rec_icon = "keep" if st == "candidate" else "new"
            out.append(_d("app_icon", "App icon", {"candidate": f"The project has an icon that could be kept ({(icon_state or {}).get('best')}). Keep it, refine it, or design a new one?",
                                                   "weak": "The project's icon files are too small or not square. Design a new icon?",
                                                   "generic": "The project only has a framework's default icon. Design a new one?"}.get(st, "Design a new app icon: a few concepts to choose from, then the full set?"),
                          rec_icon, [{"value": "new", "label": "New icon", "tradeoff": "2-4 concepts shown side by side; you pick one before it is finalised"},
                                     {"value": "refine", "label": "Refine the existing icon", "tradeoff": "keeps its idea; redrawn as a 1024 px master"},
                                     {"value": "keep", "label": "Keep the existing icon", "tradeoff": "only verified and wired in; nothing redrawn"}][: 3 if st == "candidate" else 1],
                          {"new": {"icon": {"mode": "new"}}, "refine": {"icon": {"mode": "refine"}}, "keep": {"icon": {"mode": "keep"}}},
                          (icon_state or {}).get("reason") or "No icon yet."))
        prof = spec.get("engineering", {}).get("profile", "personal")
        out.append(_d("engineering", "Who uses it and what it holds", "Engineering standard: " + {"personal": "a private app for a few people, no accounts or sensitive data?",
                      "public": "a public app (anyone can open it, or it has accounts)?", "sensitive": "an app handling payments, health, financial or personal data?"}[prof],
                      prof, [{"value": "personal", "label": "Personal / small group", "tradeoff": "simple: no servers, accounts or extra infrastructure"},
                             {"value": "public", "label": "Public", "tradeoff": "adds input validation, error handling, pinned dependencies"},
                             {"value": "sensitive", "label": "Sensitive data", "tradeoff": "adds auth on every route, rate limits, safe storage, separate environments"}],
                      {p: {"engineering": {"profile": p}} for p in ("personal", "public", "sensitive")},
                      "because: " + (", ".join(spec.get("engineering", {}).get("because") or []) or "nothing in the idea suggests accounts or sensitive data")))
    out.append(_d("cost", "Cost", "Use only free tools and the accounts already connected (no new paid services)?", "free",
                  [{"value": "free", "label": "No new costs (recommended)", "tradeoff": "everything runs on what is already here"},
                   {"value": "allow_paid", "label": "Paid services allowed", "tradeoff": "each one still needs your approval when it comes up"}],
                  {"free": {"authorisations": {"spend": False}}, "allow_paid": {}}, "Spending is never pre-authorised."))
    if web:
        pth = (spec.get("project") or {}).get("path") or ""
        found = [f for f in ("vercel.json", ".vercel/project.json", "netlify.toml", "CNAME", "firebase.json", "fly.toml", "render.yaml") if pth and os.path.exists(os.path.join(pth, f))]
        wf = os.path.join(pth, ".github", "workflows") if pth else ""
        if wf and os.path.isdir(wf): found += [f".github/workflows/{f}" for f in os.listdir(wf) if re.search(r"deploy|pages|release|publish", f, re.I)]
        asked = bool(spec["features"].get("deploy"))
        opts = ([{"value": "existing", "label": "The project's own pipeline", "tradeoff": f"uses what is already set up ({', '.join(found[:3])})"}] if found else []) + [
            {"value": "vercel", "label": "Vercel", "tradeoff": "the connected Vercel account; a preview per PR and production from main"},
            {"value": "github_pages", "label": "GitHub Pages", "tradeoff": "free static hosting from the repository; static sites and games only"},
            {"value": "no_deploy", "label": "Don't deploy", "tradeoff": "you get the verified project and report only"}]
        rec = "existing" if found else ("vercel" if asked else "no_deploy")   # an existing pipeline is how this project delivers
        if (spec.get("mode") or {}).get("workflow") != "review": out.append(_d("deployment", "Where it goes live", "Deploy it once every check passes? You approve the deploy itself at release; it counts as live only after "
                      "GITCRAFT opens the live URL and finds this exact build there.", rec, opts,
                      {o["value"]: ({"features": {"deploy": False}, "deploy": {"target": None}} if o["value"] == "no_deploy" else
                                    {"features": {"deploy": True}, "deploy": {"target": o["value"], "found": found}}) for o in opts},
                      ("you asked for it to go live" if asked else "you didn't ask for deployment") + (f"; found {', '.join(found[:3])}" if found else "")))
        if spec.get("backend", {}).get("needed"):
            out.append(_d("backend", "Where its data lives", "It needs shared data (" + ", ".join((spec["backend"].get("because") or [])[:3]) + "). Use a hosted Postgres database "
                          "with a small API, set up separately for development and production?", "postgres",
                          [{"value": "postgres", "label": "Hosted Postgres + API", "tradeoff": "real accounts and sync; uses the connected Neon account; you approve the setup"},
                           {"value": "local", "label": "On the device only", "tradeoff": "no server or cost; data stays in one browser and does not sync"}],
                          {"postgres": {"backend": {"provider": "postgres"}}, "local": {"backend": {"provider": "local"}}},
                          "Infrastructure is never created without your approval; secrets never go in the repository."))
        if not existing:
            prof = spec.get("engineering", {}).get("profile", "personal")
            rec_a = "pulse" if prof == "public" or d == "site" else "none"
            out.append(_d("analytics", "Usage counts", "Count visits with HaveAnApp Pulse (anonymous and cookieless, as in HangarBook)?", rec_a,
                          [{"value": "pulse", "label": "HaveAnApp Pulse", "tradeoff": "anonymous page counts; no cookies, no personal data; one script tag"},
                           {"value": "none", "label": "No analytics", "tradeoff": "nothing is counted"}],
                          {"pulse": {"analytics": {"provider": "pulse"}}, "none": {"analytics": {"provider": None}}},
                          "recommended for public apps and sites; a private app does not need it"))
        if spec["platform"].get("native"):
            out.append(_d("native", "Native app icons", f"Also produce the {' and '.join(spec['platform']['native'])} icon sets from the approved master?", "yes",
                          [{"value": "yes", "label": "Yes", "tradeoff": "iOS asset catalog (1024, opaque) and Android mipmaps + adaptive icon"},
                           {"value": "no", "label": "Web icons only", "tradeoff": "PWA, Apple touch and favicons"}],
                          {"yes": {}, "no": {"platform": {"native": []}}}, "GITCRAFT builds web apps; the native icon sets are ready for a native wrapper or app project."))
    if web and proj.get("exists"):
        out.append(_d("attribution", "HaveAnApp credit", "Add the quiet 'by HaveAnApp' credit to this existing app?", "leave",
                      [{"value": "add", "label": "Add it", "tradeoff": "a small byline in the footer or About screen"},
                       {"value": "leave", "label": "Leave it out", "tradeoff": "the app is not GITCRAFT-generated; its branding stays as it is"}],
                      {"add": {"attribution": {"required": True}}, "leave": {"attribution": {"required": False}}},
                      "New apps always carry it; an existing app is your call."))
    for q in spec.get("questions") or []:
        if q["id"] == "deploy_target" and any(x["id"] == "deployment" for x in out): continue
        out.append(_d(f"q.{q['id']}", q["id"].replace("_", " ").title(), q["question"], q.get("default"), [{"value": q.get("default"), "label": str(q.get("default")), "tradeoff": "the safe default"}],
                      {}, "essential: no safe default" if q.get("essential") else "has a safe default", kind="question"))
    return out


def overrides_for(decs, answers):
    """Answers → spec overrides. Unknown answers are refused (a typo must not silently become the default)."""
    ov = {}
    from .intake import merge
    for d in decs:
        if d["id"] not in answers: continue
        a = answers[d["id"]]
        vals = [o["value"] for o in d["options"]]
        if d["kind"] in ("choice", "confirm") and a not in vals:
            raise ValueError(f"decision {d['id']}: {a!r} is not one of {vals}")
        if "$answer" in d["sets"]:
            ov = merge(ov, json.loads(json.dumps(d["sets"]["$answer"]).replace('"$answer"', json.dumps(str(a)))))
        else: ov = merge(ov, d["sets"].get(a, {}))
    return ov


# ---------------------------------------------------------------- the blueprint and deviations
MATERIAL_KEYS = ("deliverable", "dimension", "platform", "genres", "features", "assets", "authorisations", "engineering", "icon", "attribution",
                 "deploy", "analytics", "backend",
                 "extra_tasks", "skip_tasks", "project")


def _h(x): return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:16]


def blueprint(prod):
    spec = prod["spec"]
    scope = {k: spec.get(k) for k in MATERIAL_KEYS}
    return {"status": "approved", "approved_at": store.now(), "hash": _h(scope), "scope_hash": _h(scope),
            "decisions": [{"id": d["id"], "title": d["title"], "answer": d["answer"]} for d in prod.get("decision_room", [])],
            "tasks": list(prod["order"]), "acceptance": [c["id"] for c in spec["acceptance"]],
            "authorised": {k: v for k, v in spec["authorisations"].items()},
            "note": "the source of truth for the build: settled decisions are not reopened; a material change needs production_revise and a new approval"}


def material(old_spec, new_spec):
    """[changed key] for every material difference (an empty list = only the quality bar or wording changed)."""
    return [k for k in MATERIAL_KEYS if json.dumps(old_spec.get(k), sort_keys=True, default=str) != json.dumps(new_spec.get(k), sort_keys=True, default=str)]


# ---------------------------------------------------------------- where the project is
def stage(prod):
    lc = prod.get("lifecycle") or {}
    st = lc.get("stage")
    if st in ("idea", "recon", "parked", "discarded", "discovery", "decisions"): return st
    if lc.get("revision"): return "revision"
    status = prod.get("status")
    bp = (prod.get("blueprint") or {}).get("status")
    if st is None and bp is None and prod.get("tasks"): bp = "approved"   # a production made before the lifecycle existed
    if bp != "approved": return "decisions"
    started = any(t.get("attempts") for t in (prod.get("tasks") or {}).values())
    if not started: return "approved"
    if status in ("passed",): return "delivered"
    if status in ("passed_not_deployed", "passed_deploy_unverified"): return "verified"
    if status == "blocked": return "blocked"
    if status == "failed": return "failed"
    return "building"


SAY = {"idea": "Saved as an idea. Next: optional Recon (production_recon) or turn it into a build (production_promote).",
       "recon": "Recon is out: research the idea and submit the findings (production_recon with findings).",
       "parked": "Parked. It can be revisited and promoted any time.", "discarded": "Discarded (kept for the record).",
       "discovery": "Discovery is reading the project (read-only).",
       "decisions": "Waiting in the Decision Room: approve the blueprint (production_decide) to start building.",
       "approved": "Blueprint approved. Next: production_run builds it.",
       "revision": "Paused: a material change to the approved blueprint is waiting for approval (production_decide).",
       "building": "Building.", "verified": "Built and verified; deployment is not verified live yet.",
       "delivered": "Delivered: every criterion passed" , "blocked": "Blocked: something cannot run here (see the report).",
       "failed": "Not ready: a check still fails after its fix rounds (see the report)."}


def summary(prod):
    st = stage(prod); tasks = prod.get("tasks") or {}
    done = sum(1 for t in tasks.values() if t["state"] in ("passed", "skipped") and not t.get("superseded_by"))
    live = [t for t in tasks.values() if not t.get("superseded_by")]
    waiting = [t["id"] for t in live if t["state"] in ("awaiting_agent", "needs_approval")]
    line = SAY.get(st, st)
    if st == "building" and live: line = f"Building: {done}/{len(live)} steps done" + (f"; waiting on {', '.join(waiting[:3])}" if waiting else "")
    if st == "delivered":
        dep = next((t.get("deployment") for t in tasks.values() if t.get("deployment")), None)
        line = SAY["delivered"] + (f"; live at {dep['url']}" if dep and dep.get("verified") else "") + "."
    return {"stage": st, "summary": line, "stages": STAGES, "history": (prod.get("lifecycle") or {}).get("history", [])}


def move(prod, to, note=None):
    lc = prod.setdefault("lifecycle", {"history": []})
    lc.setdefault("history", []).append({"at": store.now(), "stage": to, **({"note": note} if note else {})})
    lc["stage"] = to


# ---------------------------------------------------------------- the Discovery Report (read-only)
def discovery_report(prod):
    spec, disc = prod["spec"], prod["discovery"]
    proj = disc.get("project") or {}
    st = (disc.get("runtimes") or {}).get("studio") or {}
    ready = sum(1 for d in st.get("departments", []) for s in d["actions"].values() if s == "ready")
    total = sum(len(d["actions"]) for d in st.get("departments", []))
    tasks = prod["tasks"]
    owners = {}
    for t in tasks.values(): owners.setdefault(t["owner"], []).append(t["id"])
    b = prod.get("brief") or {}
    L = [f"# Discovery Report: {spec['title']}", "",
         "Read-only: nothing was built, changed, deployed or created during Discovery.", "",
         "## 1. Understanding of the request", "",
         f"- **Objective:** {b.get('objective') or spec['prompt'][:200]}",
         f"- **Deliverable:** {spec['dimension'].upper()} {spec['deliverable']}" + (f" ({', '.join(spec['genres'])})" if spec.get("genres") else "")
         + f"; {'mobile-first' if spec['platform']['mobile_first'] else 'desktop and phone'}",
         f"- **Engineering standard:** {spec.get('engineering', {}).get('profile', 'personal')}"]
    L += [f"- **Requirement:** {r}" for r in (b.get("requirements") or [])[:8]]
    L += [f"- **Constraint:** {c}" for c in (b.get("constraints") or [])[:6]]
    if prod.get("recon"):
        r = prod["recon"]; L += [f"- **Recon ({r.get('depth')}):** {r.get('recommendation', {}).get('verdict')} — {r.get('recommendation', {}).get('reasoning', '')[:300]}"]
    L += ["", "## 2. Existing resources", ""]
    if proj.get("exists"):
        L += [f"- Project `{proj.get('path')}`: {proj.get('files')} files; engines {', '.join(proj.get('engines') or []) or 'none detected'}; entry {proj.get('entry') or 'none'}",
              f"- Assets: " + (", ".join(f"{k} {v['count']}" for k, v in (proj.get("assets") or {}).items()) or "none"),
              f"- Tests: {len(proj.get('tests') or [])}; docs: {len(proj.get('docs') or [])}"]
        if proj.get("git"): L.append(f"- Git: branch {proj['git'].get('branch')} at {proj['git'].get('commit')}" + (" (uncommitted changes)" if proj['git'].get('dirty') else "") + (f", remote {proj['git'].get('remote')}" if proj['git'].get('remote') else ""))
    else: L.append(f"- New project (will be created at `{spec['project']['path']}` when the build starts)")
    ic = prod.get("icon_state") or {}
    L.append(f"- App icon: {ic.get('status', 'none')} — {ic.get('reason', '')}")
    m = prod.get("maturity")
    if m and m.get("existing"):
        mode = spec.get("mode") or {}
        L += ["", f"**Project state: {m['maturity'].replace('_', ' ')} {m.get('kind') or ''}** (confidence {m['confidence']}; a reading of the files, not of a run)."
              f" Workflow: **{mode.get('workflow')}** ({mode.get('because')}).", ""]
        L += [f"  - evidence: {e}" for e in m.get("evidence", [])]
        inv = m.get("inventory") or {}
        for key, head, why in (("working", "Working (keep as it is)", "evidence"), ("unfinished", "Unfinished", None), ("defects", "Defects", None),
                               ("requests", "Requests from open issues (done only if the blueprint includes them)", None),
                               ("improvements", "Optional improvements (not done unless approved)", None)):
            items = inv.get(key) or []
            if not items: continue
            L.append(f"- **{head}** ({len(items)}):")
            L += [f"  - {x['what']}" + (f" — `{x['where']}`" if x.get("where") else "") + (f" ({x['evidence']})" if why and x.get("evidence") else "") for x in items[:12]]
            if len(items) > 12: L.append(f"  - … and {len(items) - 12} more")
        if m.get("save_keys"): L.append(f"- **Saved data** (preserved): storage keys {', '.join(m['save_keys'][:10])}")
        L.append("- Open GitHub issues: " + ("read (in the inventory above)." if m.get("issues_read") else "not read (pass them to production_start as issues; the sandbox has no network).")
                 + " The live deployment is checked at release (verify-live).")
    L.append(f"- GITCRAFT departments ready on this machine: {ready}/{total} actions" + (f" (Studio: {st.get('reason')})" if st.get("status") == "blocked" else ""))
    L += ["", "## 3. Recommended approach", ""]
    for o, ids in owners.items(): L.append(f"- **{o}:** {len(ids)} task(s) — {', '.join(ids[:6])}{'…' if len(ids) > 6 else ''}")
    L += ["", "## 4. Meaningful alternatives", ""]
    alts = [f"{d['title']}: " + "; ".join(f"{o['label']} ({o['tradeoff']})" for o in d["options"][1:]) for d in prod.get("decision_room", []) if len(d["options"]) > 1 and d["kind"] == "choice"]
    L += [f"- {a}" for a in alts] or ["- None material: the request has one sensible approach."]
    L += ["", "## 5. Risks and constraints", ""]
    risks = [f"Cannot run here: {k} — {v}" for k, v in (prod.get("readiness") or {}).items()] + [f"Plan problem: {p}" for p in prod.get("problems") or []] + list(prod.get("warnings") or [])
    if proj.get("git", {}).get("dirty"): risks.append("The project has uncommitted changes: commit or stash before the build starts.")
    risks += [f"Assumption: {a}" for a in spec.get("assumptions", [])[:8]]
    L += [f"- {r}" for r in risks] or ["- None found."]
    L += ["", "## 6. Decisions requiring your input", ""]
    for d in prod.get("decision_room", []):
        L.append(f"- **{d['title']}** — {d['question']} Recommended: **{d['recommended']}**." + (f" ({d['why']})" if d.get("why") else ""))
    L += ["", "## 7. Proposed implementation plan", ""]
    for i, wave in enumerate(prod.get("parallel_groups") or [], 1):
        L.append(f"{i}. " + ", ".join(wave))
    L += ["", "## 8. Acceptance and verification criteria", ""]
    L += [f"- {c['text']} (measured by {c['measured_by']})" for c in spec["acceptance"]]
    L += ["", "Approve or revise the decisions with `production_decide`; nothing is built until the blueprint is approved."]
    p = os.path.join(prod["store"], "DISCOVERY.md")
    with open(p, "w") as f: f.write("\n".join(L) + "\n")
    return p
