"""ARCHITECTURE AND PLANNING: spec + discovery → a task graph.

Every task names its stage, executor (who does it), the department action and request, what it depends on,
how its outputs are handed on (`ship`: which roles/formats go into the project, where), the gate that decides
whether it passed, the resources it holds (one Blender at a time, two browsers), and its retry budget.

Request parameters may reference upstream results, resolved when the task starts (structured hand-offs):
  "$project", "$project/sub/dir"                 the project folder
  {"$from": "<task>", "role": r, "format": f}   the path of an upstream output (first match; "all": true for a list)
  {"$from": "<task>", "role": r, "json": "key", "as": "rgb"}   a value read from an upstream JSON output

validate(plan) refuses a plan with an unknown dependency, a cycle, an unknown department action or a
request its department would reject, before anything runs."""
import os, sys
from . import REPO
from . import discovery as _disc

STUDIO_DIR = os.path.join(REPO, "studio")
PREVIEW_ROLES = {"preview", "source", "manifest", "engine_screenshot", "blockout", "blockout_render", "ldtk_project", "render", "contact_sheet"}


def T(tid, title, stage, kind, *, department=None, action=None, params=None, deps=(), gate=None, ship=None, resources=(), retries=1,
      timeout=1800, owner=None, work_order=None, advisory=False, criterion=None):
    return {"id": tid, "title": title, "stage": stage, "kind": kind, "department": department, "action": action, "params": params or {},
            "depends_on": list(deps), "gate": gate or ([{"type": "status_ok"}] if kind in ("studio", "forgecraft", "designcraft") else []),
            "ship": ship, "resources": list(resources), "retries": retries, "timeout": timeout, "owner": owner or _owner(kind, department),
            "work_order": work_order, "advisory": advisory, "criterion": criterion, "state": "pending", "attempts": []}


def _owner(kind, dept):
    return {"studio": f"Studio · {dept}", "forgecraft": "3D Department (ForgeCraft → MeshCraft)", "designcraft": "DESIGNCRAFT (game design)",
            "builtin": "Production Director", "agent": "Claude (agent)"}.get(kind, kind)


def _hex_from(t): return {"$from": t, "role": "palette", "json": "accent", "as": "rgb"}


def build(spec, disc):
    q, a, d = spec["quality"], spec["assets"], spec["deliverable"]
    proj = disc["project"]
    tasks, decisions = [], []
    add = tasks.append
    stems = set(proj.get("asset_stems") or [])
    asset_dir = spec["project"].get("asset_dir") or proj.get("asset_dir") or "assets"
    spec["project"]["asset_dir"] = asset_dir
    adir = lambda sub: f"$project/{asset_dir}/{sub}"
    web = d in ("game", "app", "site")
    pmode = spec.get("mode") or {}
    existing, workflow = bool(pmode.get("existing")), pmode.get("workflow") or "build"
    if existing and workflow == "review": return _review_plan(spec, proj, decisions)
    # an update or a fix to an existing project is not a quality overhaul: the evaluators' scores are measured and
    # reported, and the gates that hold are the ones about the change (loads, regression, preservation)
    small_change = existing and workflow in ("update", "fix")
    if small_change: decisions.append(f"{workflow} of an existing project: PLAYCRAFT/PIXELCRAFT scores are reported (advisory), not imposed")

    # ---------------------------------------------------------------- foundation
    # a new project gets its folders; an existing one gets nothing it did not ask for (integration makes a folder
    # only when something ships into it)
    add(T("foundation.scaffold", "Prepare the project folder" + ("" if existing else " and asset folders") + " (never overwrites)", "foundation", "builtin",
          action="scaffold", params={"dirs": [] if existing else [f"{asset_dir}/{s}" for s in ("audio", "levels", "fx", "brand", "materials", "models", "icons")]}))
    identity = None
    if a.get("identity"):
        identity = "foundation.identity"
        add(T(identity, "Original visual identity: palette and logo", "foundation", "agent", deps=["foundation.scaffold"],
              work_order={"tools": ["vectorcraft (draw_shape, draw_path, add_text, export SVG/PNG)"],
                          "brief": f"An original visual identity for {spec['title']}: {spec['prompt'][:300]}",
                          "instructions": ["Derive the palette from the prompt's mood and setting; keep it original (no existing brand).",
                                           "Write palette.json as {\"background\": \"#rrggbb\", \"primary\": \"#rrggbb\", \"accent\": \"#rrggbb\", \"text\": \"#rrggbb\"}.",
                                           "Make logo.svg (wordmark + mark) with VectorCraft; export, then look at it. The app icon is the App Icon Studio's job (icon.concepts)."],
                          "expected": [{"path": "palette.json", "format": "json", "keys": ["background", "primary", "accent", "text"]},
                                       {"path": "logo.svg", "format": "svg"}],
                          "license": "owned by the project (made with GITCRAFT VectorCraft)"},
              ship={"dest": adir("brand"), "roles": ["*"]}, criterion="asset_identity"))
    script = None
    if a.get("voice"):
        script = "foundation.script"
        add(T(script, "Dialogue script for the voiced lines", "foundation", "agent", deps=["foundation.scaffold"],
              work_order={"brief": "Write the lines the game speaks (tutorial, story beats, barks).",
                          "instructions": ["Write script.json as {\"lines\": [{\"text\": \"…\", \"voice\": \"af_heart\"}, …]} (≤ 12 lines)."],
                          "expected": [{"path": "script.json", "format": "json", "keys": ["lines"]}]}))

    # ---------------------------------------------------------------- App Icon Studio (concepts → a person picks → master → platform set)
    icon_tasks = _icon_tasks(spec, proj, identity, adir) if web and spec.get("icon", {}).get("required") else []
    for x in icon_tasks: add(x)
    mode = (spec.get("icon") or {}).get("mode")
    if web and mode == "keep": decisions.append("app icon: the existing icon is kept (inspected; qa.icons verifies it is wired in correctly)")

    # ---------------------------------------------------------------- production (independent tasks run in parallel)
    prod = []
    for p in a.get("sfx", []):
        if p in stems: decisions.append(f"reuse: the project already has a '{p}' sound; no new one generated"); continue
        tid = f"audio.sfx.{p}"; prod.append(tid)
        add(T(tid, f"Sound effect: {p}", "production", "studio", department="audiocraft", action="sfx", params={"preset": p, "name": p, "formats": ["wav", "ogg"]},
              deps=["foundation.scaffold"], ship={"dest": adir("audio"), "roles": ["sfx"], "formats": ["ogg"]}, criterion="asset_sfx"))
    if a.get("music"):
        prod.append("audio.music")
        add(T("audio.music", f"Adaptive music ({a['music']['mood']})", "production", "studio", department="audiocraft", action="music",
              params={"mood": a["music"]["mood"], "bars": a["music"].get("bars", 16), "name": "music"}, deps=["foundation.scaffold"],
              ship={"dest": adir("audio"), "roles": ["music"], "formats": ["ogg"]}, criterion="asset_music"))
    for k in a.get("ambience", []):
        tid = f"audio.ambience.{k}"; prod.append(tid)
        add(T(tid, f"Ambience loop: {k}", "production", "studio", department="audiocraft", action="ambience", params={"kind": k, "name": f"ambience_{k}"},
              deps=["foundation.scaffold"], ship={"dest": adir("audio"), "roles": ["*"], "formats": ["ogg"]}, criterion="asset_ambience"))
    if script:
        prod.append("audio.voice")
        add(T("audio.voice", "Voice lines (Kokoro-82M)", "production", "studio", department="audiocraft", action="voice",
              params={"lines": {"$from": script, "role": "*", "format": "json", "json": "lines"}, "name": "voice"}, deps=[script],
              ship={"dest": adir("audio"), "roles": ["*"], "formats": ["ogg"]}, criterion="asset_voice"))
    lv = a.get("levels")
    if lv and lv.get("by_levelcraft"):
        for i in range(1, lv["count"] + 1):
            tid = f"levels.{i}"; prod.append(tid)
            add(T(tid, f"Level {i} ({lv['kind']}, solvability-checked)", "production", "studio", department="levelcraft", action="generate",
                  params={"kind": lv["kind"], "name": f"level_{i}", "seed": i * 7}, deps=["foundation.scaffold"], resources=["browser"],
                  ship={"dest": adir("levels"), "roles": ["level_data", "tiled_map", "tileset"]}, criterion="asset_levels"))
    elif lv:
        decisions.append(f"levels: no LevelCraft kind fits; the build task designs {lv['requested']} levels as data")
    for e in a.get("vfx", []):
        tid = f"vfx.{e}"; prod.append(tid)
        params = {"effect": e, "name": e}
        deps = ["foundation.scaffold"]
        if identity and e in ("magic", "energy", "smoke", "dust", "lightning", "debris", "splash"):
            params["color"] = _hex_from(identity); deps = [identity]   # tinted from the identity's palette: a real hand-off
        add(T(tid, f"Effect flipbook: {e}", "production", "studio", department="fxcraft", action="flipbook", params=params, deps=deps,
              ship={"dest": adir("fx"), "roles": ["flipbook", "flipbook_meta", "atlas*"]}, criterion="asset_vfx"))
    for m in a.get("materials", []):
        tid = f"materials.{m}"; prod.append(tid)
        add(T(tid, f"PBR material: {m}", "production", "studio", department="materialcraft", action="generate", params={"material": m, "name": m, "resolution": 512},
              deps=["foundation.scaffold"], resources=["browser"], ship={"dest": adir("materials"), "roles": ["*"], "formats": ["png", "json"]}, criterion="asset_materials"))
    w = a.get("world")
    if w:
        prod.append("world.terrain")
        add(T("world.terrain", f"Terrain: {w['terrain']}", "production", "studio", department="worldcraft", action="terrain", params={"preset": w["terrain"], "name": "terrain"},
              deps=["foundation.scaffold"], resources=["browser"], ship={"dest": adir("models"), "roles": ["*"], "formats": ["glb", "png", "json"]}, criterion="asset_world"))
        prod.append("world.sky")
        add(T("world.sky", f"Sky: {w['sky']}", "production", "studio", department="worldcraft", action="sky", params={"preset": w["sky"], "name": "sky"},
              deps=["foundation.scaffold"], ship={"dest": adir("materials"), "roles": ["*"], "formats": ["png", "hdr", "json"]}, criterion="asset_world"))
    for i, brief in enumerate(a.get("models", []), 1):
        tid = f"models.{i}"; prod.append(tid)
        add(T(tid, f"3D model: {brief}", "production", "forgecraft", action="generate", params={"brief": brief, "name": f"model_{i}"},
              deps=["foundation.scaffold"], resources=["blender"], timeout=3600, ship={"dest": adir("models"), "library": True}, criterion="asset_models"))

    # ---------------------------------------------------------------- tasks the agent added to the spec (validated like the rest)
    for x in spec.get("extra_tasks") or []:
        kind = x.get("kind", "studio")
        add(T(x["id"], x.get("title") or f"{x.get('department')}.{x.get('action')}", x.get("stage", "production"), kind, department=x.get("department"),
              action=x.get("action"), params=x.get("params"), deps=x.get("depends_on") or ["foundation.scaffold"], ship=x.get("ship"),
              resources=x.get("resources", ()), retries=x.get("retries", 1), timeout=x.get("timeout", 1800), work_order=x.get("work_order"),
              criterion=x.get("criterion")))
        if x.get("stage", "production") == "production": prod.append(x["id"])

    # ---------------------------------------------------------------- integration
    shipping = [t["id"] for t in tasks if t.get("ship")]
    if web:
        add(T("integrate.assets", "Integrate every passed asset into the project (hash-verified, no silent overwrite)", "integration", "builtin",
              action="integrate", deps=shipping or ["foundation.scaffold"], criterion="asset_integrity"))
        build_deps = ["integrate.assets"] + ([identity] if identity else []) + (["icon.derivatives"] if "icon.derivatives" in {t["id"] for t in tasks} else [])
        kind = {"game": "game", "app": "app", "site": "site"}[d]
        add(T("build", f"Build the {kind}: {spec['title']}", "integration", "agent", deps=build_deps,
              work_order={"brief": spec["prompt"],
                          "instructions": _build_instructions(spec),
                          "expected": [{"path": "$project/" + (proj.get("entry") or "index.html"), "format": "html"}],
                          "inputs": "the integrated-assets manifest (handoff) lists every asset path with its role",
                          "license": "owned by the project"}))
    # ---------------------------------------------------------------- quality assurance (parallel; each failure spawns a fix + re-verification)
    qa = []
    if web:
        tgt = "$project"
        qa.append("qa.smoke")
        add(T("qa.smoke", "TestCraft smoke: loads on every viewport, no errors, no missing files", "qa", "studio", department="testcraft", action="smoke",
              params={"target": tgt, "viewports": q["viewports"], "expect_canvas": d == "game", "name": "smoke"}, deps=["build"], resources=["browser"], criterion="loads_everywhere"))
        if q.get("perf"):
            qa.append("qa.perf")
            add(T("qa.perf", "TestCraft performance profile", "qa", "studio", department="testcraft", action="perf",
                  params={"target": tgt, "seconds": 4, "min_fps": q["min_fps"], "max_p95_ms": q["max_p95_ms"], "name": "perf"}, deps=["build"], resources=["browser", "exclusive"],
                  criterion="performance"))
        if q.get("playcraft"):
            qa.append("qa.playcraft")
            add(T("qa.playcraft", "PLAYCRAFT: play the build and score gameplay quality", "qa", "studio", department="playcraft", action="pass",
                  params={"project": "$project", "genres": spec["genres"][:3] or None, "mobile": spec["platform"]["mobile_first"], "name": "playcraft"},
                  deps=["build"], resources=["browser"], timeout=1200, criterion="gameplay_quality", advisory=small_change,
                  gate=[{"type": "status_ok"}, {"type": "min", "path": "summary.overall.score", "min": q["playcraft_min"], "label": "PLAYCRAFT overall"}]))
        if q.get("pixelcraft"):
            qa.append("qa.pixelcraft")
            add(T("qa.pixelcraft", "PIXELCRAFT: visual quality and usability at iPhone 17, iPhone 13, desktop", "qa", "studio", department="pixelcraft", action="audit",
                  params={"project": "$project", "target": "$project", "viewports": ["iphone17", "iphone13", "desktop"], "name": "pixelcraft"},
                  deps=["build"], resources=["browser"], timeout=1200, criterion="interface_quality", advisory=small_change,
                  gate=[{"type": "status_ok"}, {"type": "min", "path": "summary.overall.score", "min": q["pixelcraft_min"], "label": "PIXELCRAFT overall"}]))
        if q.get("designcraft"):
            qa.append("qa.designcraft")
            add(T("qa.designcraft", "DESIGNCRAFT: structural game-design review (advisory)", "qa", "designcraft", action="assess", params={"project": "$project"},
                  deps=["build"], advisory=True, criterion="design_review"))
        if spec.get("icon", {}).get("required"):
            qa.append("qa.icons")
            add(T("qa.icons", "App icon: approved, wired in, right sizes and formats, readable small", "qa", "builtin", action="check_icons",
                  params={"mode": mode}, deps=["build"] + (["icon.derivatives"] if "icon.derivatives" in {t["id"] for t in tasks} else []),
                  criterion="app_icon", gate=[{"type": "status_ok"}]))
        if spec.get("attribution", {}).get("required"):
            qa.append("qa.attribution")
            add(T("qa.attribution", "HaveAnApp attribution: the maker's credit is in the app", "qa", "builtin", action="check_attribution",
                  deps=["build"], criterion="attribution", gate=[{"type": "status_ok"}]))
        qa.append("qa.standards")
        add(T("qa.standards", f"Engineering standard ({spec.get('engineering', {}).get('profile', 'personal')}): measured checks"
              + (" (advisory: findings in existing code are reported, not imposed)" if existing else ""), "qa", "builtin", action="check_standards",
              params={"profile": spec.get("engineering", {}).get("profile", "personal"), "deliverable": d}, deps=["build"], criterion="engineering_standards",
              gate=[{"type": "status_ok"}], advisory=existing))
        if existing:
            qa.append("qa.preserve")
            add(T("qa.preserve", "Preservation: existing files, secrets, CI/deploy" + (", game assets and saves" if d == "game" else "") + " intact", "qa", "builtin",
                  action="check_preserve", params={"kind": d, "allow": pmode.get("allow") or []}, deps=["build"], criterion="preservation", gate=[{"type": "status_ok"}]))
        ships = bool(shipping) or bool(proj.get("assets"))
        if not ships: decisions.append("no asset integrity / licence QA: nothing ships and the project has no assets")
        if ships: qa.append("qa.assets")
        if ships: add(T("qa.assets", "Asset integrity: every integrated asset opens and is referenced by the build", "qa", "studio", department="testcraft", action="assets",
              params={"folder": f"$project/{asset_dir}", "name": "assets"}, deps=["build"], criterion="asset_integrity",
              gate=[{"type": "status_ok"}, {"type": "referenced"}]))
        if ships: qa.append("qa.licences")
        if ships: add(T("qa.licences", "Licences: every shipped asset has a recorded licence (AssetCraft)", "qa", "builtin", action="licences",
              params={"folder": f"$project/{asset_dir}", "require_known": q.get("require_known_licences", True)}, deps=["build"], criterion="licensing",
              gate=[{"type": "status_ok"}]))
    # ---------------------------------------------------------------- release
    if web:
        add(T("release.regression", "Final regression: smoke-test the exact build being released", "release", "studio", department="testcraft", action="smoke",
              params={"target": "$project", "viewports": q["viewports"], "expect_canvas": d == "game", "name": "regression"}, deps=qa, resources=["browser"],
              criterion="loads_everywhere"))
        rel_deps = qa + ["release.regression"]
    else:
        rel_deps = prod
    add(T("release.report", "Release report: every acceptance criterion with its evidence", "release", "builtin", action="release", deps=rel_deps,
          criterion="release_ready", gate=[{"type": "status_ok"}]))
    if spec["features"].get("deploy"):
        add(T("release.deploy", "Deploy and verify the live URL", "release", "agent", deps=["release.report"], criterion="deployment",
              work_order={"approval": "deploy", "brief": "Deploy the verified release and check the live URL.",
                          "instructions": ["Deploy only to the target the person approved.", "Open the live URL and confirm it serves this build (same commit/content).",
                                           "Submit the URL and the evidence (a check that ran against the live URL)."],
                          "expected": [], "requires": ["url", "evidence"]}))
    skip = set(spec.get("skip_tasks") or [])   # applied last, so any task (QA and release included) can be skipped
    if skip:
        unknown = sorted(skip - {t["id"] for t in tasks})
        tasks[:] = [t for t in tasks if t["id"] not in skip]
        for t in tasks: t["depends_on"] = [d for d in t["depends_on"] if d not in skip]
        decisions.append(f"skipped at the agent's request: {', '.join(sorted(skip - set(unknown)))}" + (f" (not in the plan: {', '.join(unknown)})" if unknown else ""))
    plan = {"tasks": {t["id"]: t for t in tasks}, "order": [t["id"] for t in tasks], "decisions": decisions}
    plan["parallel_groups"] = parallel_groups(plan)
    return plan


WORKFLOW_BRIEF = {
    "continue": "This is a partially built {kind}. Finish its unfinished features (the Discovery inventory lists them, with where each was found), "
                "most important first. Keep everything that already works; do not rebuild, rename or restructure it.",
    "complete": "This {kind} is nearly complete. Fix the genuine blockers (defects first, then the open items needed to call it done) and stop there; "
                "no new features, redesigns or refactors.",
    "update": "Implement only the requested change{req} in this existing {kind}, and the supporting fixes it needs. Everything else stays as it is.",
    "fix": "Fix the reported problem{req} in this {kind} and add a regression check for it. Change nothing else.",
}


def _existing_instructions(spec):
    mode, d = spec.get("mode") or {}, spec["deliverable"]
    req = f" ({mode['request']})" if mode.get("request") else ""
    ins = [WORKFLOW_BRIEF.get(mode.get("workflow"), WORKFLOW_BRIEF["update"]).format(kind=d, req=req),
           f"Work in the existing architecture and conventions ({spec['platform'].get('engine') or 'as found'}): same framework, file layout, style and naming; "
           "no migrations, new frameworks, scaffolding, rebranding, new icon or redesign unless the blueprint approved them.",
           "Never touch secrets or .env files, production data or user-created content. Keep the CI, deployment and environment configuration as they are "
           "unless the change cannot work without editing them (then say so in the submission notes).",
           "Commit on a feature branch in the project, following its own PR conventions."]
    if d == "game":
        ins.append("This is an existing game: preserve its gameplay, mechanics, controls, levels, art direction, audio and assets, and its saved data and "
                   "progression (the same storage keys and formats; a player's existing save must still load). Change them only where the blueprint says.")
    ins.append("qa.preserve checks this: no deleted files, untouched secrets/CI/deploy" + (", unchanged game assets and every save key still used" if d == "game" else "")
               + ". An approved exception goes in through production_revise (mode.allow).")
    return ins


def _review_plan(spec, proj, decisions):
    """Review only: measure the project as it is (read-only evaluators), change nothing, report."""
    q, d = spec["quality"], spec["deliverable"]
    tasks = []
    add = tasks.append
    if proj.get("entry") or proj.get("build_dir"):
        add(T("qa.smoke", "TestCraft smoke: loads on every viewport, no errors, no missing files", "qa", "studio", department="testcraft", action="smoke",
              params={"target": "$project", "viewports": q["viewports"], "expect_canvas": d == "game", "name": "smoke"}, resources=["browser"], criterion="loads_everywhere"))
        if q.get("playcraft"):
            add(T("qa.playcraft", "PLAYCRAFT: play the game and score it", "qa", "studio", department="playcraft", action="pass",
                  params={"project": "$project", "genres": spec["genres"][:3] or None, "mobile": spec["platform"]["mobile_first"], "name": "playcraft"},
                  resources=["browser"], timeout=1200, criterion="gameplay_quality", advisory=True))
        if q.get("pixelcraft"):
            add(T("qa.pixelcraft", "PIXELCRAFT: visual quality and usability", "qa", "studio", department="pixelcraft", action="audit",
                  params={"project": "$project", "target": "$project", "viewports": ["iphone17", "iphone13", "desktop"], "name": "pixelcraft"},
                  resources=["browser"], timeout=1200, criterion="interface_quality", advisory=True))
        if q.get("designcraft"):
            add(T("qa.designcraft", "DESIGNCRAFT: structural game-design review (advisory)", "qa", "designcraft", action="assess", params={"project": "$project"},
                  advisory=True, criterion="design_review"))
        if q.get("perf"):
            add(T("qa.perf", "TestCraft performance profile", "qa", "studio", department="testcraft", action="perf",
                  params={"target": "$project", "seconds": 4, "min_fps": q["min_fps"], "max_p95_ms": q["max_p95_ms"], "name": "perf"},
                  resources=["browser", "exclusive"], criterion="performance", advisory=True))
    add(T("qa.standards", f"Engineering standard ({spec.get('engineering', {}).get('profile', 'personal')}): measured checks (advisory)", "qa", "builtin",
          action="check_standards", params={"profile": spec.get("engineering", {}).get("profile", "personal"), "deliverable": d}, criterion="engineering_standards",
          gate=[{"type": "status_ok"}], advisory=True))
    add(T("release.report", "Review report: the project as it is, measured; nothing changed", "release", "builtin", action="release", deps=[t["id"] for t in tasks],
          criterion="release_ready", gate=[{"type": "status_ok"}]))
    decisions.append("review only: the evaluators measure the project as it is; nothing is built, scaffolded or changed")
    plan = {"tasks": {t["id"]: t for t in tasks}, "order": [t["id"] for t in tasks], "decisions": decisions}
    plan["parallel_groups"] = parallel_groups(plan)
    return plan


def _build_instructions(spec):
    q, a = spec["quality"], spec["assets"]
    if (spec.get("mode") or {}).get("existing"):
        ins = _existing_instructions(spec)
        from . import standards as _std
        ins += _std.instructions(spec.get("engineering", {}).get("profile", "personal"), spec["deliverable"])[1:2]
        if a.get("sfx") or a.get("music"): ins.append("Wire the new sounds in where the request says; existing sounds stay.")
        ins.append("Submit the files you changed.")
        return ins
    ins = [f"Implement a complete {spec['deliverable']} in the project folder (entry index.html), original in name, art and mechanics.",
           f"Platform: {'mobile-first, touch controls with ≥ 44 px targets, portrait and landscape' if spec['platform']['mobile_first'] else 'desktop and phone'}; "
           f"engine: {spec['platform']['engine'] or 'plain web'}; no new paid services.",
           "Use the integrated assets (paths in the handoff manifest) — every one must be referenced by the build."]
    if spec["deliverable"] == "game":
        ins += ["A full loop: start screen → play → fail/win → retry in one tap; clear objective; difficulty that ramps.",
                "Progression that is saved (localStorage), a best score or unlocks; pause; mute."]
    if a.get("levels"): ins.append(f"Load the {a['levels']['count']} level files (level_data JSON) in order; reaching the exit advances.")
    if a.get("sfx") or a.get("music"): ins.append("Play the sound effects on their events and loop the music after the first input (autoplay policy).")
    from . import standards as _std
    prof = spec.get("engineering", {}).get("profile", "personal")
    ins += _std.instructions(prof, spec["deliverable"])
    if spec.get("attribution", {}).get("required"):
        cfg = _std.attribution_config()
        ins.append("HaveAnApp attribution (production/kit/haveanapp): add the quiet byline \"by HaveAnApp\" beneath or beside the app's name in a footer, "
                   "About/Settings screen or a game's title/pause screen, marked data-haveanapp, styled small and muted in the app's own theme "
                   "(byline.css; Byline.tsx for React). Also <meta name=\"author\" content=\"HaveAnApp\"> and '<App> by HaveAnApp' in the manifest description. "
                   + (f"Link it to {cfg['url']}." if cfg.get("url") and cfg.get("url_verified") else "Do not link it: no official HaveAnApp URL is verified yet.")
                   + " Never put it in the app icon.")
    if spec.get("icon", {}).get("required"):
        mode = (spec.get("icon") or {}).get("mode")
        ins.append("App icon: " + ("wire in the icon set from icon.derivatives exactly as its icons.snippet.json says (the head tags, and the manifest's icons; "
                                   "merge into an existing manifest). Remove every older or framework-default icon reference." if mode != "keep" else
                                   "keep the project's existing icon; make sure index.html links a favicon, a 180 px opaque apple-touch-icon and a manifest with 192 and 512 px icons."))
    ins.append("Run no build step that needs the network. Submit the files you changed.")
    return ins


def _icon_tasks(spec, proj, identity, adir):
    """App Icon Studio: concepts → a person chooses (icon.select) → the 1024 master → the platform set (shipped)."""
    mode = (spec.get("icon") or {}).get("mode") or "new"
    if mode == "keep": return []
    pal = "palette.json from the identity (hand-off)" if identity else "the project's own colours"
    refine = mode == "refine"
    base = (spec.get("icon") or {}).get("existing")
    concepts = T("icon.concepts", "App icon concepts" + (" (refining the existing icon)" if refine else ""), "foundation", "agent",
                 deps=[identity or "foundation.scaffold"],
                 work_order={"tools": ["vectorcraft (draw_shape, draw_path, pathfinder, export PNG at 1024 px + SVG)", "photocraft (raster finishing)"],
                             "brief": (f"Refine the existing icon ({base}) for {spec['title']}" if refine else f"App icon concepts for {spec['title']}") + f": {spec['prompt'][:240]}",
                             "instructions": [
                                 "Make 3 meaningfully different concepts (2 minimum, 5 maximum): different ideas, not colour swaps." if not refine else
                                 "Make 2-3 refinements that keep the existing icon's idea and make it cleaner, bolder and readable at small size.",
                                 f"Use {pal}. One strong silhouette per concept; it must read at 32 px. No tiny text, no screenshot, no generic framework or "
                                 "stock imagery, no HaveAnApp branding. Each app's icon is its own: no shared GITCRAFT style.",
                                 "Export each concept as a square PNG of at least 512 px (1024 preferred) and its SVG source; look at each export.",
                                 'Write concepts.json: {"concepts": [{"id": "a", "file": "a.png", "source": "a.svg", "idea": "…", "rationale": "…"}], "recommended": "a"}.'],
                             "expected": [{"path": "concepts.json", "format": "json", "keys": ["concepts", "recommended"], "validate": "icon_concepts", "role": "concepts"}],
                             "license": "owned by the project (made with GITCRAFT VectorCraft)"})
    select = T("icon.select", "A person chooses the app icon (comparison sheet)", "foundation", "builtin", action="icon_select", deps=["icon.concepts"],
               gate=[{"type": "status_ok"}])
    master = T("icon.master", "Final app icon: the approved concept refined into a 1024 px master", "foundation", "agent", deps=["icon.select"],
               work_order={"tools": ["vectorcraft", "photocraft"], "brief": "Refine the approved concept (selection.json in the hand-off) into the final master icon.",
                           "instructions": ["Keep the approved idea; do not switch to another concept (that needs a new approval).",
                                            "Export icon-1024.png at exactly 1024 x 1024 (full-bleed square: platforms apply their own corner mask) and icon.svg.",
                                            "Check it at 32 px: the silhouette must still read."],
                           "expected": [{"path": "icon-1024.png", "format": "png", "validate": "icon_master", "role": "icon_master"}],
                           "license": "owned by the project (made with GITCRAFT VectorCraft)"})
    params = {"master": {"$from": "icon.master", "role": "icon_master"}, "name": spec["title"]}
    if identity: params["background"] = {"$from": identity, "role": "*", "format": "json", "json": "background"}
    deriv = T("icon.derivatives", "App icon set: PWA 192/512, maskable, Apple touch 180, favicons (from the approved master)", "foundation", "builtin",
              action="icon_derivatives", params=params, deps=["icon.master"] + ([identity] if identity else []),
              ship={"dest": adir("icons"), "roles": ["icon", "favicon", "icon_master"]}, gate=[{"type": "status_ok"}], criterion="app_icon")
    return [concepts, select, master, deriv]


def parallel_groups(plan):
    """Waves of tasks that can run at the same time (every dependency in an earlier wave)."""
    level, tasks = {}, plan["tasks"]

    def lv(t, seen=()):
        if t in level: return level[t]
        if t in seen: raise ValueError(f"dependency cycle through {t}")
        deps = tasks[t]["depends_on"]
        level[t] = 0 if not deps else 1 + max(lv(x, seen + (t,)) for x in deps)
        return level[t]
    for t in tasks: lv(t)
    waves = {}
    for t, n in level.items(): waves.setdefault(n, []).append(t)
    return [sorted(waves[k]) for k in sorted(waves)]


def _strip_refs(v):
    if isinstance(v, dict) and "$from" in v: return None
    if isinstance(v, str) and v.startswith("$project"): return "/placeholder"
    if isinstance(v, dict): return {k: _strip_refs(x) for k, x in v.items()}
    if isinstance(v, list): return [_strip_refs(x) for x in v]
    return v


def validate(plan, disc=None):
    """Problems that would make the plan fail before it starts. Empty list = the plan is sound."""
    problems, tasks = [], plan["tasks"]
    for t in tasks.values():
        for dep in t["depends_on"]:
            if dep not in tasks: problems.append(f"{t['id']}: unknown dependency {dep}")
    if problems: return problems   # the graph itself is broken: ordering it would be meaningless
    try: parallel_groups(plan)
    except ValueError as e: problems.append(str(e))
    if STUDIO_DIR not in sys.path: sys.path.insert(0, STUDIO_DIR)
    try:
        from core import contract
    except Exception as e:   # the contract itself is stdlib; a failure here is a broken checkout
        return problems + [f"cannot load the department contract: {e}"]
    for t in tasks.values():
        if t["kind"] != "studio": continue
        try:
            m = contract.manifest(t["department"])
            if t["action"] not in m["actions"]: problems.append(f"{t['id']}: {t['department']} has no action {t['action']}"); continue
            params = {k: v for k, v in (_strip_refs(t["params"]) or {}).items() if v is not None}
            contract.validate_params(m["actions"][t["action"]].get("params", {}), params)
        except Exception as e:
            problems.append(f"{t['id']}: {t['department']}.{t['action']} would refuse the request: {e}")
    return problems


def readiness(plan, disc):
    """Tasks that cannot run on this machine, known before production starts (they will report `blocked`)."""
    out = {}
    for t in plan["tasks"].values():
        if t["kind"] == "studio":
            ok, why = _disc.ready(disc, t["department"], t["action"])
            if not ok: out[t["id"]] = why
    return out
