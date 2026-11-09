"""ARCHITECTURE AND PLANNING: spec + discovery → a task graph.

Every task names its stage, executor (who does it), the department action and request, what it depends on,
how its outputs are handed on (`ship`: which roles/formats go into the project, where), the gate that decides
whether it passed, the resources it holds (one Blender at a time, two browsers), and its retry budget.

Request parameters may reference upstream results, resolved when the task starts (structured hand-offs):
  "$project", "$project/sub/dir"                 the project folder (source: structural review, asset folders)
  "$target"                                      the evaluation target every browser check measures: the built app
                                                 or the source, by the source-vs-build policy (production/artifacts.py)
  {"$from": "<task>", "role": r, "format": f}   the path of an upstream output (first match; "all": true for a list)
  {"$from": "<task>", "role": r, "json": "key", "as": "rgb"}   a value read from an upstream JSON output

validate(plan) refuses a plan with an unknown dependency, a cycle, an unknown department action or a
request its department would reject, before anything runs.

Plan versions (stored on the production record as `plan_version`; a revision keeps the version it was planned with):
  1  assets → integrate.assets → build → QA: the build waits for every asset and the app icon.
  2  the code build starts after the foundation (scaffold, identity, and any design-stage task) with placeholders;
     each asset is integrated as soon as it passes (integrate.<task>, transactional), integrate.final checks the
     ledger and the asset manifest, build.wire wires every integrated asset and the approved icon into the app,
     and QA measures that final wired build. The icon choice is off the code path and on the release path.
     The v2 graph is built from the v1 graph (_graph_v2), so v1 stays exactly what it was."""
import copy, os, sys
from . import REPO
from . import discovery as _disc

STUDIO_DIR = os.path.join(REPO, "studio")
PLAN_VERSION = 2   # new productions; records without plan_version are 1
MANIFEST = "gitcraft.assets.json"   # the asset manifest in the project: owned by integration, never by the agent
PREVIEW_ROLES = {"preview", "source", "manifest", "engine_screenshot", "blockout", "blockout_render", "ldtk_project", "render", "contact_sheet"}



def _playcraft_hints(spec):
    """What PLAYCRAFT is told about the game: only what the person stated. An intake default ("genre not named:
    arcade", no mobile words) is an assumption, not a fact about the game; passing it would override PLAYCRAFT's
    own detection from the game (an exploration game scored as arcade, its mobile category not scored at all)."""
    pf = spec["platform"]
    stated = pf.get("mobile_stated", pf["mobile_first"] or None)   # specs made before mobile_stated: only a 'yes' was ever stated
    return {"genres": None if spec.get("genres_assumed") else (spec["genres"][:3] or None), "mobile": stated}

def T(tid, title, stage, kind, *, department=None, action=None, params=None, deps=(), gate=None, ship=None, resources=(), retries=1,
      timeout=1800, owner=None, work_order=None, advisory=False, criterion=None):
    return {"id": tid, "title": title, "stage": stage, "kind": kind, "department": department, "action": action, "params": params or {},
            "depends_on": list(deps), "gate": gate or ([{"type": "status_ok"}] if kind != "agent" else []),   # a built-in (integration, scaffold) is gated too: all([]) passed a partial failure
            "ship": ship, "resources": list(resources), "retries": retries, "timeout": timeout, "owner": owner or _owner(kind, department),
            "work_order": work_order, "advisory": advisory, "criterion": criterion, "state": "pending", "attempts": []}


def _owner(kind, dept):
    return {"studio": f"Studio · {dept}", "forgecraft": "3D Department (ForgeCraft → MeshCraft)", "designcraft": "DESIGNCRAFT (game design)",
            "builtin": "Production Director", "agent": "Claude (agent)"}.get(kind, kind)


def _hex_from(t): return {"$from": t, "role": "palette", "json": "accent", "as": "rgb"}


def build(spec, disc, version=1):
    q, a, d = spec["quality"], spec["assets"], spec["deliverable"]
    proj = disc["project"]
    tasks, decisions = [], []
    add = tasks.append
    stems = set(proj.get("asset_stems") or [])
    starter = _starter(spec, proj)
    asset_dir = spec["project"].get("asset_dir") or proj.get("asset_dir") or ("public/assets" if starter == "vite-react" else "assets")
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
          action="scaffold", params={"dirs": [] if existing else [f"{asset_dir}/{s}" for s in ("audio", "levels", "fx", "brand", "materials", "models", "icons")],
                                     "starter": starter, "title": spec["title"]}))
    if starter: decisions.append(f"starter: {starter} (production/kit/starters) copied into the new, empty project: the standards are wired in from the first file")
    if spec.get("backend", {}).get("provider") == "postgres":
        add(T("backend.provision", "Hosted Postgres for development and production (needs your approval)", "foundation", "agent", deps=["foundation.scaffold"],
              criterion="backend", work_order={"approval": "infrastructure", "tools": ["Neon (connected): create_project / create_branch / get_connection_string", "Vercel (connected): create_project_env"],
                "brief": f"The data behind {spec['title']}: one Postgres database with separate development and production branches.",
                "instructions": ["Create (or reuse, if the blueprint names one) a Neon project for this app; a 'development' branch for building and testing and the default branch for production.",
                                 "Put each connection string only where it is used: the hosting provider's environment variables (DATABASE_URL per environment) and a local .env that .gitignore excludes. Never in the repository, a work order or a submission.",
                                 "Write backend.json: {\"provider\": \"neon\", \"project\": \"<name>\", \"environments\": {\"development\": \"<branch>\", \"production\": \"<branch>\"}, \"env_vars\": [\"DATABASE_URL\"]} (names only, no secrets)."],
                "expected": [{"path": "backend.json", "format": "json", "keys": ["provider", "environments", "env_vars"], "validate": "no_secrets"}]}))
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
        if w.get("ocean"):
            prod.append("world.ocean")
            add(T("world.ocean", "Ocean: seamless time-looping FFT surface", "production", "studio", department="worldcraft", action="ocean", params={"name": "ocean"},
                  deps=["foundation.scaffold"], resources=["browser"], ship={"dest": adir("models"), "roles": ["mesh", "normal_map", "normal_flipbook", "foam_flipbook", "manifest"]},
                  criterion="asset_world"))
    for i, brief in enumerate(a.get("models", []), 1):
        tid = f"models.{i}"; prod.append(tid)
        add(T(tid, f"3D model: {brief}", "production", "forgecraft", action="generate", params={"brief": brief, "name": f"model_{i}"},
              deps=["foundation.scaffold"], resources=["blender"], timeout=3600, ship={"dest": adir("models"), "library": True}, criterion="asset_models"))
    # animated characters: the 3D Department's model → AnimCraft rig → AnimCraft clips → TestCraft proves every clip moves
    for an in a.get("animate", []):
        i = an["model"]; src, rig, clips = f"models.{i}", f"anim.{i}.rig", f"anim.{i}.clips"
        if src not in {x["id"] for x in tasks}: continue
        prod += [rig, clips, f"anim.{i}.check"]
        add(T(rig, f"Rig model {i} ({an['rig']}, heat-map weights)", "production", "studio", department="animcraft", action="autorig",
              params={"input": {"$from": src, "role": "model", "format": "glb"}, "rig": an["rig"], "name": f"model_{i}_rigged"}, deps=[src], resources=["blender", "browser"],
              criterion="asset_animation"))
        add(T(clips, f"Animate model {i}: {', '.join(an['clips'])}", "production", "studio", department="animcraft", action="animate",
              params={"input": {"$from": rig, "role": "rigged_mesh", "format": "glb"}, "clips": an["clips"], "name": f"model_{i}_animated"}, deps=[rig], resources=["blender", "browser"],
              ship={"dest": adir("models"), "roles": ["animated_mesh"], "formats": ["glb"]}, criterion="asset_animation"))
        add(T(f"anim.{i}.check", f"TestCraft: model {i}'s clips play and really move", "production", "studio", department="testcraft", action="animation",
              params={"input": {"$from": clips, "role": "animated_mesh", "format": "glb"}, "name": f"model_{i}_animation"}, deps=[clips], resources=["browser"],
              criterion="asset_animation"))

    # ---------------------------------------------------------------- tasks the agent added to the spec (validated like the rest)
    for x in _extra_tasks(spec, add, tasks):
        if x.get("stage", "production") == "production" and not x.get("replaces"): prod.append(x["id"])

    # ---------------------------------------------------------------- integration
    shipping = [t["id"] for t in tasks if t.get("ship")]
    if web:
        add(T("integrate.assets", "Integrate every passed asset into the project (hash-verified, no silent overwrite)", "integration", "builtin",
              action="integrate", deps=shipping or ["foundation.scaffold"], criterion="asset_integrity"))
        build_deps = ["integrate.assets"] + ([identity] if identity else []) + [x for x in ("icon.derivatives", "backend.provision") if x in {t["id"] for t in tasks}]
        kind = {"game": "game", "app": "app", "site": "site"}[d]
        add(T("build", f"Build the {kind}: {spec['title']}", "integration", "agent", deps=build_deps,
              work_order={"brief": spec["prompt"],
                          "instructions": _build_instructions(spec),
                          "expected": [{"path": "$project/" + (proj.get("entry") or "index.html"), "format": "html"}]
                                      + ([{"path": "$project/tests/gitcraft.features.json", "format": "json", "keys": ["features"], "validate": "features"}] if _features_required(spec) else []),
                          "inputs": "the integrated-assets manifest (handoff) lists every asset path with its role",
                          "license": "owned by the project"}))
    # ---------------------------------------------------------------- quality assurance (parallel; each failure spawns a fix + re-verification)
    qa = []
    if web:
        tgt = "$target"   # the evaluation target: one folder for every browser check (production/artifacts.py)
        qa.append("qa.smoke")
        add(T("qa.smoke", "TestCraft smoke: loads on every viewport, no errors, no missing files", "qa", "studio", department="testcraft", action="smoke",
              params={"target": "$target", "viewports": q["viewports"], "expect_canvas": d == "game", "name": "smoke"}, deps=["build"], resources=["browser"], criterion="loads_everywhere"))
        if q.get("perf"):
            qa.append("qa.perf")
            add(T("qa.perf", "TestCraft performance profile", "qa", "studio", department="testcraft", action="perf",
                  params={"target": tgt, "seconds": 4, "min_fps": q["min_fps"], "max_p95_ms": q["max_p95_ms"], "name": "perf"}, deps=["build"], resources=["browser", "exclusive"],
                  criterion="performance"))
        if q.get("playcraft"):
            qa.append("qa.playcraft")
            add(T("qa.playcraft", "PLAYCRAFT: play the build and score gameplay quality", "qa", "studio", department="playcraft", action="pass",
                  params={"project": "$project", "target": "$target", **_playcraft_hints(spec), "name": "playcraft"},
                  deps=["build"], resources=["browser"], timeout=1200, criterion="gameplay_quality", advisory=small_change,
                  gate=[{"type": "status_ok"}, {"type": "min", "path": "summary.overall.score", "min": q["playcraft_min"], "label": "PLAYCRAFT overall"}]))
        if q.get("pixelcraft"):
            qa.append("qa.pixelcraft")
            add(T("qa.pixelcraft", "PIXELCRAFT: visual quality and usability at iPhone 17, iPhone 13, desktop", "qa", "studio", department="pixelcraft", action="audit",
                  params={"project": "$project", "target": "$target", "viewports": ["iphone17", "iphone13", "desktop"], "name": "pixelcraft"},
                  deps=["build"], resources=["browser"], timeout=1200, criterion="interface_quality", advisory=small_change,
                  gate=[{"type": "status_ok"}, {"type": "min", "path": "summary.overall.score", "min": q["pixelcraft_min"], "label": "PIXELCRAFT overall"}]))
        if q.get("designcraft"):
            qa.append("qa.designcraft")
            add(T("qa.designcraft", "DESIGNCRAFT: structural game-design review (advisory)", "qa", "designcraft", action="assess", params={"project": "$project"},
                  deps=["build"], advisory=True, criterion="design_review"))
        if _features_required(spec) or existing:
            qa.append("qa.features")
            add(T("qa.features", "Feature checks: every planned feature works in a browser (tests/gitcraft.features.json)", "qa", "builtin", action="check_features",
                  params={"file": "$project/tests/gitcraft.features.json", "target": "$target", "required": _features_required(spec), "viewports": ["phone"] if spec["platform"]["mobile_first"] else ["desktop"]},
                  deps=["build"], resources=["browser"], criterion="features_work" if _features_required(spec) else None, gate=[{"type": "status_ok"}],
                  advisory=not _features_required(spec)))
        if spec.get("icon", {}).get("required"):
            qa.append("qa.icons")
            add(T("qa.icons", "App icon: approved, wired in, right sizes and formats, readable small", "qa", "builtin", action="check_icons",
                  params={"mode": mode}, deps=["build"] + (["icon.derivatives"] if "icon.derivatives" in {t["id"] for t in tasks} else []),
                  criterion="app_icon", gate=[{"type": "status_ok"}]))
        if spec.get("attribution", {}).get("required"):
            qa.append("qa.attribution")
            add(T("qa.attribution", "HaveAnApp attribution: the maker's credit is in the app", "qa", "builtin", action="check_attribution",
                  deps=["build"], criterion="attribution", gate=[{"type": "status_ok"}]))
        if a.get("trailer"):   # cut from the build that QA measures: title card + gameplay capture (+ the music), never shipped into the app
            qa += ["trailer.title", "trailer.capture", "trailer.assemble"]
            add(T("trailer.title", "Trailer title card", "qa", "studio", department="cinematiccraft", action="title_card",
                  params={"text": spec["title"], **({"accent": _hex_from(identity)} if identity else {}), "name": "trailer_title"}, deps=[identity] if identity else ["foundation.scaffold"],
                  criterion="asset_trailer"))
            add(T("trailer.capture", "Trailer: gameplay capture from the running build", "qa", "studio", department="cinematiccraft", action="capture",
                  params={"target": "$target", "steps": [{"wait": 1500}, {"press": "Space"}, {"wait": 4000}], "name": "trailer_capture"}, deps=["build"], resources=["browser"],
                  criterion="asset_trailer"))
            add(T("trailer.assemble", "Trailer: title + gameplay" + (" + music" if a.get("music") else "") + ", crossfaded, loudness-normalised", "qa", "studio",
                  department="cinematiccraft", action="assemble",
                  params={"clips": [{"path": {"$from": "trailer.title", "role": "title", "format": "mp4"}}, {"path": {"$from": "trailer.capture", "role": "capture", "format": "mp4"}}],
                          **({"music": {"$from": "audio.music", "role": "music", "format": "ogg"}} if a.get("music") else {}), "name": "trailer"},
                  deps=["trailer.title", "trailer.capture"] + (["audio.music"] if a.get("music") else []), criterion="asset_trailer"))
        qa.append("qa.standards")
        add(T("qa.standards", f"Engineering standard ({spec.get('engineering', {}).get('profile', 'personal')}): measured checks"
              + (" (advisory: findings in existing code are reported, not imposed)" if existing else ""), "qa", "builtin", action="check_standards",
              params={"profile": spec.get("engineering", {}).get("profile", "personal"), "deliverable": d, "analytics": (spec.get("analytics") or {}).get("provider"),
                      "analytics_decided": not existing or (spec.get("analytics") or {}).get("source") == "decision_room",
                      "backend": (spec.get("backend") or {}).get("provider")}, deps=["build"], criterion="engineering_standards",
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
              params={"target": "$target", "viewports": q["viewports"], "expect_canvas": d == "game", "name": "regression"}, deps=qa, resources=["browser"],
              criterion="loads_everywhere"))
        rel_deps = qa + ["release.regression"]
    else:
        rel_deps = prod
    add(T("release.report", "Release report: every acceptance criterion with its evidence", "release", "builtin", action="release", deps=rel_deps,
          criterion="release_ready", gate=[{"type": "status_ok"}]))
    if spec["features"].get("deploy"):
        add(T("release.deploy", "Deploy and verify the live URL", "release", "agent", deps=["release.report"], criterion="deployment",
              work_order={"approval": "deploy", "brief": "Deploy the verified release and prove the live URL serves it.",
                          "instructions": _deploy_instructions(spec), "expected": [], "requires": ["url", "evidence"]}))
    if version >= 2: _graph_v2(spec, tasks, decisions)
    rproblems = _skip_and_replace(spec, tasks, decisions)   # applied last, so any task (QA and release included) can be skipped or replaced
    plan = {"tasks": {t["id"]: t for t in tasks}, "order": [t["id"] for t in tasks], "decisions": decisions, "replacement_problems": rproblems,
            "plan_version": version}
    plan["parallel_groups"] = parallel_groups(plan)
    return plan


def _graph_v2(spec, tasks, decisions):
    """The v1 web graph → v2 (in place): the code build no longer waits for assets, the icon choice or the database.
    Required release criteria are untouched: every asset task keeps its criterion, every integration measures
    asset_integrity, and QA waits for the final, wired build."""
    ids = {t["id"]: t for t in tasks}
    if "integrate.assets" not in ids or "build" not in ids: return   # not a web build: nothing to restructure
    ia, b = ids["integrate.assets"], ids["build"]
    shipping = [d for d in ia["depends_on"] if (ids.get(d) or {}).get("ship")]
    per = [T(f"integrate.{s}", f"Integrate {s} into the project (staged, hash-verified, committed atomically)", "integration", "builtin",
             action="integrate", params={"v2": True}, deps=[s], resources=["integration"], criterion="asset_integrity") for s in shipping]
    # optional assets (a person made an implied extra optional in the Decision Room): their integration is waited for
    # (settles: passed, failed, blocked or skipped), never required, so a missing optional asset cannot block the release
    req = {c["id"]: c.get("required", True) for c in spec.get("acceptance") or []}
    opt = {s for s in shipping if ids[s].get("criterion") and not req.get(ids[s]["criterion"], True)}
    for x in per:
        if x["depends_on"][0] in opt:   # it measures the optional asset's own criterion, never the required asset_integrity
            x["optional"] = True; x["criterion"] = ids[x["depends_on"][0]]["criterion"]; ids[x["depends_on"][0]]["optional"] = True
    final = T("integrate.final", "Final integration: every artifact committed, hashes and the asset manifest consistent", "integration", "builtin",
              action="integrate_final", deps=[x["id"] for x in per if not x.get("optional")] or ["foundation.scaffold"], resources=["integration"],
              criterion="asset_integrity")
    if opt: final["settles"] = [x["id"] for x in per if x.get("optional")]
    i = tasks.index(ia); tasks[i:i + 1] = per + [final]
    # the code build: the foundation, the identity and any design-stage task (the hook for pre-build design deliverables)
    design = [t["id"] for t in tasks if t["stage"] == "design"]
    identity = "foundation.identity" if "foundation.identity" in ids else None
    b["depends_on"] = ["foundation.scaffold"] + ([identity] if identity else []) + design
    b["consumes"] = shipping   # used through placeholders until build.wire; never blocks
    b["work_order"]["instructions"] = _build_instructions(spec, v2=True)
    b["work_order"]["inputs"] = "planned_assets in the hand-off: every asset being produced, its roles and its destination folder"
    after_build = ["build"]
    if "backend.provision" in ids:   # build against a local mock; switch to the approved database once it exists
        bw = T("backend.wire", "Switch the data layer from the local mock to the approved Postgres", "integration", "agent", deps=["backend.provision", "build"],
               work_order={"brief": "The database is provisioned (backend.json in the hand-off). Replace the local mock with the real data layer.",
                           "instructions": ["Read DATABASE_URL from the environment; keep the mock only for tests.", "Add the migrations to the repository; an index for every "
                                            "column a query filters or joins on.", "No secret in the repository, the work order or the submission.", "Submit the files you changed."],
                           "expected": []})
        tasks.insert(tasks.index(b) + 1, bw); after_build = ["backend.wire"]
    wires = bool(shipping) or "icon.derivatives" in ids
    if wires:
        bwire = T("build.wire", "Wire every integrated asset and the approved app icon into the application", "integration", "agent",
                  deps=after_build + ["integrate.final"],
                  work_order={"brief": "Every asset is integrated (integrated_assets in the hand-off). Replace the placeholders with them in the real application.",
                              "instructions": _wire_instructions(spec, "icon.derivatives" in ids),
                              "expected": [{"path": "$project/" + ((spec.get("project") or {}).get("entry") or "index.html"), "format": "html"}],
                              "inputs": "integrated_assets in the hand-off: every integrated file with its role and producing task"})
        tasks.insert(tasks.index(final) + 1, bwire)
    ready = "build.wire" if wires else after_build[-1]
    for t in tasks:   # QA and release measure the final, wired build (and the final integration)
        if t["id"] in ("build", "build.wire", "backend.wire") or t["stage"] not in ("qa", "release"): continue
        if "build" in t["depends_on"]:
            t["depends_on"] = [ready if d == "build" else d for d in t["depends_on"]]
            if not wires and "integrate.final" not in t["depends_on"]: t["depends_on"].append("integrate.final")
    for t in tasks:   # anything added that named the v1 integration step depends on the final integration
        t["depends_on"] = ["integrate.final" if d == "integrate.assets" else d for d in t["depends_on"]]
    if any(t["id"] == "qa.assets" for t in tasks):
        for g in next(t for t in tasks if t["id"] == "qa.assets")["gate"]:
            if g["type"] == "referenced": g["strict"] = True   # real loads only: no comments, no unrelated JSON, never the manifest
    _layered_qa(spec, tasks, ids, ready, wires)
    decisions.append("plan v2: the code build starts after the foundation with placeholders; assets are integrated as they pass; build.wire wires them "
                     "and the approved icon in; QA measures the final wired build" + ("; the build uses a local data mock until backend.wire" if "backend.provision" in ids else ""))


def _layered_qa(spec, tasks, ids, ready, wires):
    """Plan v2's layered QA (production/qa.py): department QA before hand-off and Product QA against the request.
    Integration QA is the integration tasks and the existing checks of the assembled build; nothing else is added."""
    from . import qa
    for t in tasks:   # department QA: a shipping department's own deliverables exist and validate before integration takes them
        sh = t.get("ship") or {}
        if t["stage"] == "production" and t["kind"] in ("studio", "agent") and sh.get("roles") and not any(g["type"] == "deliverables" for g in t["gate"] or []):
            t["gate"] = (t["gate"] or []) + [{"type": "deliverables", "roles": list(sh["roles"]), **({"formats": list(sh["formats"])} if sh.get("formats") else {})}]
    existing = bool((spec.get("mode") or {}).get("existing"))
    deps = [ready] + ([] if wires else ["integrate.final"])
    rq = T("qa.request", "Product QA: the finished product against the request (requested features, unrequested additions, coherence)"
           + (" (advisory: an existing project's code is reported, not imposed)" if existing else ""), "qa", "builtin", action="check_request",
           params=qa.params_for(spec), deps=deps, criterion="request_fulfilled", gate=[{"type": "status_ok"}], advisory=existing)
    reg = next((t for t in tasks if t["id"] == "release.regression"), None)
    tasks.insert(tasks.index(reg) if reg else len(tasks), rq)
    for t in tasks:   # the final regression and the release wait for it like every other QA check
        if t["id"] in ("release.regression", "release.report") and "qa.request" not in t["depends_on"]: t["depends_on"].append("qa.request")


def _wire_instructions(spec, icon):
    ins = ["Load every asset listed in integrated_assets through its real path, from the code or markup that uses it (a filename in a comment, or in a JSON "
           "file nothing loads, does not count: qa.assets checks real references). Remove each placeholder it replaces.",
           f"Do not edit {MANIFEST} or any integrated asset file: integration owns them, and a submission that changes them is rejected."]
    if icon:
        ins.append("App icon: wire in the icon set from icon.derivatives exactly as its icons.snippet.json says (the head tags, and the manifest's icons; "
                   "merge into an existing manifest). Remove every older, placeholder or framework-default icon reference.")
    return ins + ["Run no build step that needs the network. Submit the files you changed."]


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
              params={"target": "$target", "viewports": q["viewports"], "expect_canvas": d == "game", "name": "smoke"}, resources=["browser"], criterion="loads_everywhere"))
        if q.get("playcraft"):
            add(T("qa.playcraft", "PLAYCRAFT: play the game and score it", "qa", "studio", department="playcraft", action="pass",
                  params={"project": "$project", "target": "$target", **_playcraft_hints(spec), "name": "playcraft"},
                  resources=["browser"], timeout=1200, criterion="gameplay_quality", advisory=True))
        if q.get("pixelcraft"):
            add(T("qa.pixelcraft", "PIXELCRAFT: visual quality and usability", "qa", "studio", department="pixelcraft", action="audit",
                  params={"project": "$project", "target": "$target", "viewports": ["iphone17", "iphone13", "desktop"], "name": "pixelcraft"},
                  resources=["browser"], timeout=1200, criterion="interface_quality", advisory=True))
        if q.get("designcraft"):
            add(T("qa.designcraft", "DESIGNCRAFT: structural game-design review (advisory)", "qa", "designcraft", action="assess", params={"project": "$project"},
                  advisory=True, criterion="design_review"))
        if q.get("perf"):
            add(T("qa.perf", "TestCraft performance profile", "qa", "studio", department="testcraft", action="perf",
                  params={"target": "$target", "seconds": 4, "min_fps": q["min_fps"], "max_p95_ms": q["max_p95_ms"], "name": "perf"},
                  resources=["browser", "exclusive"], criterion="performance", advisory=True))
    add(T("qa.standards", f"Engineering standard ({spec.get('engineering', {}).get('profile', 'personal')}): measured checks (advisory)", "qa", "builtin",
          action="check_standards", params={"profile": spec.get("engineering", {}).get("profile", "personal"), "deliverable": d,
                                            "analytics": (spec.get("analytics") or {}).get("provider"), "analytics_decided": False}, criterion="engineering_standards",
          gate=[{"type": "status_ok"}], advisory=True))
    add(T("release.report", "Review report: the project as it is, measured; nothing changed", "release", "builtin", action="release", deps=[t["id"] for t in tasks],
          criterion="release_ready", gate=[{"type": "status_ok"}]))
    decisions.append("review only: the evaluators measure the project as it is; nothing is built, scaffolded or changed")
    _extra_tasks(spec, add, tasks, default_deps=())
    rel = next(t for t in tasks if t["id"] == "release.report")   # the review report comes last and waits for every check, added ones included
    tasks.remove(rel); rel["depends_on"] = [t["id"] for t in tasks]; tasks.append(rel)
    rproblems = _skip_and_replace(spec, tasks, decisions)
    plan = {"tasks": {t["id"]: t for t in tasks}, "order": [t["id"] for t in tasks], "decisions": decisions, "replacement_problems": rproblems}
    plan["parallel_groups"] = parallel_groups(plan)
    return plan


def _starter(spec, proj):
    """A starter for a new, empty web project (production/kit/starters), or None."""
    if (spec.get("mode") or {}).get("existing") or proj.get("exists") and proj.get("files") or spec["deliverable"] not in ("game", "app", "site"): return None
    eng = (spec["platform"].get("engine") or "").lower()
    if spec["deliverable"] == "game": return "canvas-game" if eng in ("", "canvas", "vanilla") and spec["dimension"] == "2d" else None
    return "vite-react" if eng == "react" else ("static-app" if eng in ("", "vanilla", "canvas") else None)


def _features_required(spec):
    """New apps and sites prove each planned feature in a browser; games are played by PLAYCRAFT instead."""
    m = spec.get("mode") or {}
    return spec["deliverable"] in ("app", "site") and not m.get("existing")


def _deploy_instructions(spec):
    t = (spec.get("deploy") or {}).get("target") or "vercel"
    how = {"vercel": ["Deploy with Vercel (the connected account): link or create the project for this repository; production deploys from the merged main branch.",
                      "Make sure visitors can open it: no deployment protection on the production URL unless the blueprint says the app is private."],
           "github_pages": ["Deploy with GitHub Pages from the repository (Settings → Pages, or a pages workflow the person approved). The URL has a /<repo>/ subpath: "
                            "the starters and the icon set use relative URLs, so nothing else changes."],
           "existing": [f"Use the project's own pipeline ({', '.join((spec.get('deploy') or {}).get('found') or []) or 'as configured'}): merge through its PR convention "
                        "and wait for its deploy; change nothing in its CI or hosting."]}.get(t, [])
    return ["Deploy only to the target the person approved (blueprint: " + t + ")."] + how + [
        "Prove it from your own shell (it has network; the tool sandbox does not): python3 -m production verify-live <production> <url> --submit. "
        "It compares the live page and every file it references with this release, checks the manifest and icons, opens it on a phone and a desktop, "
        "and submits the evidence. A login wall, an older deployment or a page error fails it.",
        "If it fails, fix the deployment (not the check) and run it again."]


def _build_instructions(spec, v2=False):
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
           ("Assets are produced in parallel and integrated by the Production Director as each passes (planned_assets in the hand-off: roles and destination "
            "folders). Build now against placeholders (generated tones, simple shapes, inline level data) behind a small loader, kept outside the asset "
            f"folders; build.wire swaps the real files in. Never write into the asset folders or {MANIFEST}." if v2 else
            "Use the integrated assets (paths in the handoff manifest) — every one must be referenced by the build.")]
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
    if spec.get("icon", {}).get("required") and v2 and (spec.get("icon") or {}).get("mode") != "keep":
        ins.append("App icon: a person chooses it in parallel; leave the icon tags to build.wire (a placeholder favicon is fine).")
    elif spec.get("icon", {}).get("required"):
        mode = (spec.get("icon") or {}).get("mode")
        ins.append("App icon: " + ("wire in the icon set from icon.derivatives exactly as its icons.snippet.json says (the head tags, and the manifest's icons; "
                                   "merge into an existing manifest). Remove every older or framework-default icon reference." if mode != "keep" else
                                   "keep the project's existing icon; make sure index.html links a favicon, a 180 px opaque apple-touch-icon and a manifest with 192 and 512 px icons."))
    if _features_required(spec):
        ins.append("Feature checks: write tests/gitcraft.features.json with one entry per feature in the brief (name, requirement, steps a person takes "
                   "ending in what they see: click/fill/press/expect). qa.features runs each in Chromium; a feature without a check is not done.")
    if (spec.get("analytics") or {}).get("provider") == "pulse":
        from . import standards as _s2
        ins.append("Analytics (approved): add HaveAnApp Pulse to the entry page: " + _s2.pulse_snippet(spec["title"]) + " (anonymous, cookieless).")
    be = (spec.get("backend") or {}).get("provider")
    if be == "postgres" and v2:
        ins.append("Backend (approved): a small API (serverless functions on the deploy target) behind one data-access interface. Until backend.wire, "
                   "back it with a local mock (in memory or a local file) so the app runs and is testable without a database; backend.wire switches it to the "
                   "provisioned Postgres (DATABASE_URL). Migrations in the repository with an index for every column a query filters or joins on; validate every "
                   "input; authenticate every route that reads or writes someone's data; parameterised SQL only.")
    elif be == "postgres":
        ins.append("Backend (approved): a small API (serverless functions on the deploy target) over the Postgres from backend.provision, reading DATABASE_URL "
                   "from the environment; migrations in the repository with an index for every column a query filters or joins on; validate every input; "
                   "authenticate every route that reads or writes someone's data; parameterised SQL only.")
    elif be == "local":
        ins.append("Data stays on the device (approved): localStorage/IndexedDB with a versioned key, and an export so a person can keep their data.")
    if spec["platform"].get("native"):
        ins.append("Native icon sets for " + " and ".join(spec["platform"]["native"]) + " are in native-icons/ (ios/AppIcon.appiconset, android/res): "
                   "leave them for the native wrapper; the web build does not reference them.")
    if v2:
        from . import qa as _qa
        req = _qa.requested(spec)
        ins.append("Product QA (qa.request) checks the finished product against the request: the entry page has a <title> naming the product"
                   + ("; " + "; ".join({"sound": "the requested sound plays (Audio/AudioContext)", "accounts": "a sign-in surface for the requested accounts",
                                         "mobile": "a viewport meta" + (" and touch/pointer controls" if spec["deliverable"] == "game" else ""),
                                         "accessibility": "<html lang> and alt text on every image"}[r] for r in req) if req else "")
                   + ". Add nothing that was not asked for (unrequested additions are reported).")
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
    params = {"master": {"$from": "icon.master", "role": "icon_master"}, "name": spec["title"], "platforms": list(spec["platform"].get("native") or [])}
    if identity: params["background"] = {"$from": identity, "role": "*", "format": "json", "json": "background"}
    deriv = T("icon.derivatives", "App icon set: PWA 192/512, maskable, Apple touch 180, favicons (from the approved master)", "foundation", "builtin",
              action="icon_derivatives", params=params, deps=["icon.master"] + ([identity] if identity else []),
              ship={"dest": adir("icons"), "roles": ["icon", "favicon", "icon_master", "icon_native"], "role_dest": {"icon_native": "$project/native-icons"},
                    "folder_licence_roles": ["icon_native"]}, gate=[{"type": "status_ok"}], criterion="app_icon")
    return [concepts, select, master, deriv]


def _reaches(tasks, a, b, seen=None):
    """True when task a depends (directly or not) on task b."""
    seen = seen if seen is not None else set()
    for d in tasks[a]["depends_on"] + list(tasks[a].get("settles") or []):
        if d == b: return True
        if d in tasks and d not in seen:
            seen.add(d)
            if _reaches(tasks, d, b, seen): return True
    return False


def parallel_groups(plan):
    """Waves of tasks that can run at the same time (every dependency in an earlier wave)."""
    level, tasks = {}, plan["tasks"]

    def lv(t, seen=()):
        if t in level: return level[t]
        if t in seen: raise ValueError(f"dependency cycle through {t}")
        deps = tasks[t]["depends_on"] + [x for x in tasks[t].get("settles") or [] if x in tasks]   # a settles edge orders like a dependency
        for x in tasks[t].get("consumes") or []:   # a soft edge never orders the schedule, but it must not close a cycle
            if x in tasks and _reaches(tasks, x, t): raise ValueError(f"dependency cycle through {t} (consumes {x}, which depends on it)")
        level[t] = 0 if not deps else 1 + max(lv(x, seen + (t,)) for x in deps)
        return level[t]
    for t in tasks: lv(t)
    waves = {}
    for t, n in level.items(): waves.setdefault(n, []).append(t)
    return [sorted(waves[k]) for k in sorted(waves)]


def _strip_refs(v):
    if isinstance(v, dict) and "$from" in v: return "/placeholder"   # inside a list or object: a path stands in (top-level hand-offs are left out by validate)
    if v == "$target" or isinstance(v, str) and v.startswith("$project"): return "/placeholder"
    if isinstance(v, dict): return {k: _strip_refs(x) for k, x in v.items()}
    if isinstance(v, list): return [_strip_refs(x) for x in v]
    return v


def _extra_tasks(spec, add, tasks, default_deps=("foundation.scaffold",)):
    """Add the tasks the agent asked for in the spec (validated like the rest); returns their specs."""
    xs = spec.get("extra_tasks") or []
    for x in xs:
        add(T(x["id"], x.get("title") or f"{x.get('department')}.{x.get('action')}", x.get("stage", "production"), x.get("kind", "studio"),
              department=x.get("department"), action=x.get("action"), params=x.get("params"), deps=x.get("depends_on") or list(default_deps),
              ship=x.get("ship"), resources=x.get("resources", ()), retries=x.get("retries", 1), timeout=x.get("timeout", 1800),
              work_order=x.get("work_order"), criterion=x.get("criterion")))
        if x.get("replaces"): tasks[-1]["replaces"] = x["replaces"]
    return xs


def _skip_and_replace(spec, tasks, decisions):
    """Apply skip_tasks and `replaces` (in place); returns the replacement problems for validate()."""
    skip = set(spec.get("skip_tasks") or [])
    replaced, rproblems = _replacements(tasks, spec.get("extra_tasks") or [], skip, decisions)
    gone = skip | set(replaced)
    if gone:
        unknown = sorted(skip - {t["id"] for t in tasks})
        tasks[:] = [t for t in tasks if t["id"] not in gone]
        for t in tasks:   # a dependency on a replaced task becomes a dependency on its replacement; a skipped one is dropped
            deps = []
            for d in t["depends_on"]:
                d = replaced.get(d, d)
                if d not in gone and d != t["id"] and d not in deps: deps.append(d)
            t["depends_on"] = deps
        plain = sorted(skip - set(unknown) - set(replaced))
        if plain or unknown:
            decisions.append(f"skipped at the agent's request: {', '.join(plain) or 'nothing'}" + (f" (not in the plan: {', '.join(unknown)})" if unknown else ""))
    return rproblems


REPLACE_INHERIT = ("criterion", "stage", "advisory", "gate", "resources")


def _replacements(tasks, extras, skip, decisions):
    """({replaced id: replacement id}, problems) for extra tasks that declare `replaces`.

    An extra task may stand in for a planned check that cannot run as planned (e.g. a smoke test pointed at the
    built app instead of the source). It must be the same check: the same kind, department and action. It then
    measures what the original measured: it inherits the original's criterion, stage, advisory flag, gate and
    resources (an explicit, different criterion is refused), the original is skipped, and every task that
    depended on the original depends on the replacement. Nothing is inferred: without `replaces`, an extra task
    measures only the criterion it names. The revision that adds it is material and needs a person's approval."""
    by = {t["id"]: t for t in tasks}
    out, problems = {}, []
    for x in extras:
        rid, nid = x.get("replaces"), x.get("id")
        if not rid: continue
        new, old = by.get(nid), by.get(rid)
        if old is None:
            problems.append(f"{nid}: replaces {rid}, which is not in the plan"); continue
        if rid in out:
            problems.append(f"{nid}: {rid} is already replaced by {out[rid]}"); continue
        same = (old["kind"], old.get("department"), old.get("action")) == (new["kind"], new.get("department"), new.get("action"))
        if not same:
            problems.append(f"{nid}: replaces {rid} but is not the same check ({new['kind']} {new.get('department')}.{new.get('action')} "
                            f"vs {old['kind']} {old.get('department')}.{old.get('action')})"); continue
        if x.get("criterion") and old.get("criterion") and x["criterion"] != old["criterion"]:
            problems.append(f"{nid}: replaces {rid}, which measures {old['criterion']}, but names criterion {x['criterion']}"); continue
        for k in REPLACE_INHERIT:
            if k not in x or k == "criterion" and not x.get("criterion"): new[k] = copy.deepcopy(old.get(k))
        if not x.get("depends_on"): new["depends_on"] = list(old["depends_on"])
        out[rid] = nid
        decisions.append(f"{nid} replaces {rid}: the same {old.get('department')}.{old.get('action')} check"
                         + (f", measuring {old['criterion']}" if old.get("criterion") else "") + " (approved revision)")
    return out, problems


def validate(plan, disc=None):
    """Problems that would make the plan fail before it starts. Empty list = the plan is sound."""
    problems, tasks = [], plan["tasks"]
    for t in tasks.values():
        for dep in t["depends_on"]:
            if dep not in tasks: problems.append(f"{t['id']}: unknown dependency {dep}")
        for dep in t.get("consumes") or []:
            if dep not in tasks: problems.append(f"{t['id']}: consumes an unknown task {dep}")
        for dep in t.get("settles") or []:
            if dep not in tasks: problems.append(f"{t['id']}: settles on an unknown task {dep}")
    problems = list(plan.get("replacement_problems") or []) + problems
    if len(problems) > len(plan.get("replacement_problems") or []): return problems   # the graph itself is broken: ordering it would be meaningless
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
            # a value handed on from an upstream task ({"$from": ...}) is checked when it is resolved, not here: it is left
            # out, and so is its `required` entry (otherwise every hand-off of a required input, e.g. the voice
            # task's lines from the script, makes the plan unapprovable)
            refs = {k for k, v in (t["params"] or {}).items() if isinstance(v, dict) and "$from" in v}
            params = {k: v for k, v in (_strip_refs(t["params"]) or {}).items() if v is not None and k not in refs}
            schema = copy.deepcopy(m["actions"][t["action"]].get("params", {}))
            if refs and schema.get("required"): schema["required"] = [r for r in schema["required"] if r not in refs]
            contract.validate_params(schema, params)
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
