"""The Production Director's own steps (everything else is a department's or the agent's).

  scaffold   create the project folder and its asset folders when missing; never writes a file
  integrate  copy every passed upstream output that ships (task `ship`: roles, formats, destination) into the
             project, hash-verified, each with a .license.json sidecar from its provenance record. Two tasks
             shipping different files to one path is an integration conflict (failed, nothing copied); an
             existing different file in the project is never overwritten without `replace_assets` (needs approval)
  licences   AssetCraft scan of the shipped folder, then its licence report (unknown / NC / ND licences fail)
"""
import hashlib, json, os, re, shutil, sys
from . import executors

PREVIEW_ROLES = {"preview", "source", "manifest", "engine_screenshot", "blockout", "blockout_render", "ldtk_project", "render", "contact_sheet", "waveform"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def _role_ok(role, roles):
    role = role or ""
    for r in roles:
        if r == "*" and role.split(":")[0] not in PREVIEW_ROLES and not role.startswith("stem"): return True
        if r.endswith("*") and r != "*" and role.startswith(r[:-1]): return True
        if r == role: return True
    return False


def select(outputs, roles=("*",), formats=None):
    return [o for o in outputs if o.get("ok", True) and _role_ok(o.get("role"), roles) and (not formats or o.get("format") in formats
                                                                                       or os.path.splitext(o["path"])[1].lstrip(".") in formats)]


STARTERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit", "starters")


def _copy_starter(name, proj, title):
    """Copy a starter into an empty project, filling {{TITLE}}/{{SHORT}}/{{SLUG}}; never overwrites a file."""
    src = os.path.join(STARTERS, name); made = []
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "app"
    for d, _, files in os.walk(src):
        for f in files:
            sp = os.path.join(d, f); rel = os.path.relpath(sp, src); dp = os.path.join(proj, rel)
            if os.path.exists(dp): continue
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            with open(sp, encoding="utf-8") as fh: t = fh.read()
            t = t.replace("{{TITLE}}", title).replace("{{SHORT}}", title[:12]).replace("{{SLUG}}", slug)
            with open(dp, "w", encoding="utf-8") as fh: fh.write(t)
            made.append(rel)
    return made


def scaffold(ctx):
    proj = ctx["project"]; made = []
    if not ctx["inside_roots"](proj): return {"status": "failed", "failure": "request", "error": f"GITCRAFT policy: project {proj} is outside the workspace roots"}
    empty = not os.path.isdir(proj) or not any(not n.startswith(".") for n in os.listdir(proj))
    if not os.path.isdir(proj): os.makedirs(proj); made.append(proj)
    starter = ctx["params"].get("starter")
    if starter and empty: made += [f"starter {starter}: {r}" for r in _copy_starter(starter, proj, ctx["params"].get("title") or "App")]
    for d in ctx["params"].get("dirs", []):
        p = os.path.join(proj, d)
        if not os.path.isdir(p): os.makedirs(p); made.append(p)
    return {"status": "ok", "outputs": [], "created": made, "checks": [{"name": "project folder exists inside the roots", "ok": os.path.isdir(proj)}]}


def integrate(ctx):
    if (ctx.get("params") or {}).get("v2"): return integrate_v2(ctx)
    prod, proj = ctx["prod"], ctx["project"]
    previous = {m["dest"]: m for m in (ctx.get("previous_manifest") or [])}
    plan, conflicts, noid = {}, [], []
    for up in ctx["upstream"]:
        ship = up.get("ship")
        if not ship or up["state"] != "passed": continue
        dest_dir = ship["dest"].replace("$project", proj)
        if ship.get("library"):   # a 3D Department asset: ForgeCraft's hash-verified library export
            res = up.get("result") or {}   # ForgeCraft reports the library asset as asset: {id, version}
            aid = res.get("asset_id") or (res.get("asset") or {}).get("id") or (res.get("library") or {}).get("asset")
            if not aid: noid.append(up["id"]); continue
            if aid: plan[f"library:{aid}"] = {"task": up["id"], "library_asset": aid, "dest_dir": dest_dir}
            continue
        for o in select(up.get("outputs", []), ship.get("roles", ["*"]), ship.get("formats")):
            dd = (ship.get("role_dest") or {}).get(o.get("role"), ship["dest"]).replace("$project", proj)
            dest = os.path.join(dd, o.get("rel") or os.path.basename(o["path"]))   # rel keeps a set's own folders (native icon sets)
            item = {"task": up["id"], "src": o["path"], "dest": dest, "folder_licence": o.get("role") in (ship.get("folder_licence_roles") or []), "set_root": dd, "sha256": o.get("sha256") or sha256(o["path"]), "role": o.get("role"), "format": o.get("format"),
                    "license": up.get("license"), "attribution": up.get("attribution"), "record": (up.get("result") or {}).get("record")}
            if dest in plan and plan[dest]["sha256"] != item["sha256"]:
                conflicts.append({"dest": os.path.relpath(dest, proj), "tasks": [plan[dest]["task"], up["id"]]})
            plan[dest] = item
    if noid:
        return {"status": "failed", "failure": "handoff", "error": f"{', '.join(noid)} passed but reported no 3D library asset to export; nothing was copied",
                "checks": [{"name": "every 3D task names its library asset", "ok": False, "detail": noid}], "outputs": []}
    if conflicts:
        return {"status": "failed", "failure": "conflict", "error": "integration conflict: different files ship to the same path; nothing was copied",
                "conflicts": conflicts, "checks": [{"name": "no two deliverables ship to the same path", "ok": False, "detail": conflicts}], "outputs": []}
    overwrite = []
    for dest, it in plan.items():
        if "library_asset" in it: continue
        if os.path.exists(dest) and sha256(dest) != it["sha256"]:
            prior = previous.get(dest)
            if not (prior and prior.get("sha256") == sha256(dest)):   # not our own earlier copy: someone's asset
                overwrite.append(os.path.relpath(dest, proj))
    if overwrite and not ctx["auth"].get("replace_assets") and not ctx.get("approved"):
        return {"status": "needs_approval", "approval": "replace_assets",
                "reason": f"{len(overwrite)} existing project file(s) would be replaced by different content", "files": overwrite,
                "checks": [{"name": "no existing asset overwritten without approval", "ok": False, "detail": overwrite}], "outputs": []}
    manifest, outs, checks = [], [], []
    for dest, it in plan.items():
        if "library_asset" in it:
            r = executors.forgecraft_call("library_export", {"asset": it["library_asset"], "dest": it["dest_dir"]}, timeout=600)
            ok = r.get("status") not in ("failed", "blocked") and not r.get("error") and bool(r.get("files"))
            checks.append({"name": f"3D asset {it['library_asset']} exported from the library (hash-verified)", "ok": ok, "detail": r.get("error") or r.get("reason")})
            lic = None
            try: lic = ((json.load(open(os.path.join(r["dir"], "asset.json"))).get("license") or {}).get("asset"))
            except (OSError, ValueError, KeyError, TypeError, AttributeError): pass
            for f in r.get("files") or []:   # the build is told about every exported file, like any other shipped asset
                ext = os.path.splitext(f["path"])[1].lower().lstrip(".")
                role = "model" if ext in ("glb", "gltf", "fbx", "obj") else "model_source"
                rel = os.path.relpath(f["path"], proj)
                if role == "model":
                    with open(f["path"] + ".license.json", "w") as fh:
                        json.dump({"license": lic or "LicenseRef-Project-Owned", "source": {"production": prod["id"], "task": it["task"], "library_asset": it["library_asset"]}}, fh, indent=1)
                manifest.append({"dest": f["path"], "dest_rel": rel, "sha256": f["sha256"], "role": role, "format": ext, "task": it["task"], "replaced": False})
                outs.append({"path": f["path"], "role": role, "format": ext, "sha256": f["sha256"], "ok": True})
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        replaced = os.path.exists(dest) and sha256(dest) != it["sha256"]
        shutil.copy2(it["src"], dest)
        ok = sha256(dest) == it["sha256"]
        side = {"license": it.get("license") or "LicenseRef-Project-Owned", "attribution": it.get("attribution"),
                "source": {"production": prod["id"], "task": it["task"], "record": it.get("record")}}
        if it.get("folder_licence"):   # platform folders (Android res/) reject stray files: one record at the set's root instead
            with open(os.path.join(it["set_root"], "LICENSE.assets.json"), "w") as f: json.dump(side, f, indent=1)
        else:
            with open(dest + ".license.json", "w") as f: json.dump(side, f, indent=1)
        rel = os.path.relpath(dest, proj)
        manifest.append({"dest": dest, "dest_rel": rel, "sha256": it["sha256"], "role": it["role"], "format": it["format"], "task": it["task"], "replaced": replaced})
        outs.append({"path": dest, "role": it["role"], "format": it["format"], "sha256": it["sha256"], "ok": ok})
        checks.append({"name": f"{rel} copied and hash-verified", "ok": ok})
    if not manifest and not checks:
        checks.append({"name": "something to integrate", "ok": True, "detail": "no shipped outputs (nothing upstream ships)"})
    with open(os.path.join(ctx["out_dir"], "integrated.json"), "w") as f: json.dump(manifest, f, indent=1)
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "outputs": outs, "checks": checks, "integrated": manifest,
            "replaced": [m["dest_rel"] for m in manifest if m["replaced"]]}


def licences(ctx):
    folder = ctx["params"]["folder"]
    if not os.path.isdir(folder): return {"status": "failed", "error": f"no asset folder {folder}", "checks": [{"name": "asset folder exists", "ok": False}], "outputs": []}
    base = {"out_dir": os.path.join(ctx["out_dir"], "scan"), "name": "scan", "register": False}
    s = executors.studio_run("assetcraft", "scan", dict(base, folder=folder, project=ctx["project"]))
    if s.get("status") == "blocked": return s
    r = executors.studio_run("assetcraft", "license_report", {"project": ctx["project"], "require_known": ctx["params"].get("require_known", True),
                                                              "out_dir": os.path.join(ctx["out_dir"], "report"), "name": "licences", "register": False})
    if r.get("status") == "blocked": return r
    outs = [dict(o, path=o["path"] if os.path.isabs(o["path"]) else os.path.join(r["out_dir"], o["path"])) for o in r.get("outputs", [])] if r.get("out_dir") else []
    return {"status": r.get("status"), "error": r.get("error"), "outputs": outs, "checks": (s.get("checks") or []) + (r.get("checks") or []),
            "record": r.get("record"), "scan": {k: s.get(k) for k in ("catalogued", "by_kind")}}


# ---------------------------------------------------------------- App Icon Studio and the app standards (production/icons.py, standards.py)
def _concepts_file(ctx):
    for up in ctx["upstream"]:
        for o in up.get("outputs", []):
            if os.path.basename(o["path"]) == "concepts.json": return o["path"]
    return None


def icon_select(ctx):
    """A person chooses the icon from a side-by-side sheet. Never chosen silently: without an approval it waits."""
    from . import icons
    cf = _concepts_file(ctx)
    if not cf: return {"status": "failed", "failure": "handoff", "error": "icon.concepts handed on no concepts.json", "outputs": []}
    data = json.load(open(cf)); base = os.path.dirname(cf); cs = data.get("concepts") or []
    sheet = icons.comparison_sheet(cs, base, os.path.join(ctx["out_dir"], "concepts.html"), ctx["spec"]["title"], data.get("recommended"))
    listing = [{"id": c.get("id"), "idea": c.get("idea"), "file": c["file"] if os.path.isabs(c["file"]) else os.path.join(base, c["file"])} for c in cs]
    if not ctx.get("approved"):
        return {"status": "needs_approval", "approval": "icon", "concepts": listing, "recommended": data.get("recommended"), "sheet": sheet,
                "reason": f"choose the app icon: open {sheet} and approve a concept (production_approve with choice; recommended: {data.get('recommended')}), "
                          "or decline with a note to ask for new concepts",
                "outputs": [{"path": sheet, "role": "icon_sheet", "format": "html"}], "checks": []}
    choice = ctx.get("choice") or data.get("recommended")
    pick = next((c for c in listing if c["id"] == choice), None)
    if not pick: return {"status": "failed", "failure": "request", "error": f"no concept {choice!r} (concepts: {[c['id'] for c in listing]})", "outputs": []}
    sel = {"choice": choice, "file": pick["file"], "idea": pick["idea"], "recommended": data.get("recommended"),
           "approved_by": "a person (production_approve)", "note": ctx.get("approval_note")}
    sp = os.path.join(ctx["out_dir"], "selection.json"); json.dump(sel, open(sp, "w"), indent=1)
    return {"status": "ok", "selection": sel, "outputs": [{"path": sp, "role": "selection", "format": "json"}, {"path": pick["file"], "role": "icon_concept", "format": "png"},
                                                          {"path": sheet, "role": "icon_sheet", "format": "html"}],
            "checks": [{"name": f"a person approved concept {choice}", "ok": True}]}


def icon_derivatives(ctx):
    from . import icons
    p = ctx["params"]; master = p.get("master")
    if not master or not os.path.isfile(master): return {"status": "failed", "failure": "handoff", "error": "no approved 1024 px master was handed on", "outputs": []}
    svg = next((o["path"] for up in ctx["upstream"] for o in up.get("outputs", []) if o["path"].endswith(".svg") and "icon" in os.path.basename(o["path"])), None)
    try:
        return icons.derivatives(master, ctx["out_dir"], background=p.get("background"), name=p.get("name") or "App",
                                 prefix=icons.href_prefix(ctx["spec"]["project"].get("asset_dir")), source_svg=svg,
                                 platforms=p.get("platforms") or ())
    except icons.PNGError as e:
        return {"status": "failed", "failure": "request", "error": f"the master cannot be decoded: {e}", "outputs": []}


def check_icons(ctx):
    from . import icons
    proj, mode = ctx["project"], ctx["params"].get("mode") or "new"
    r = icons.verify(proj, require_manifest=True, decision=mode)
    tasks = ctx.get("tasks") or {}
    if mode in ("new", "refine"):
        sel = tasks.get("icon.select") or {}
        r["checks"].append({"name": "the icon was chosen by a person (icon.select approved)", "ok": sel.get("state") == "passed" and bool(sel.get("approved")),
                            "detail": sel.get("state")})
        made = {os.path.basename(o["path"]): o.get("sha256") for up in ctx["upstream"] if up["id"].startswith("icon.derivatives") for o in up.get("outputs", [])}
        ed = os.path.dirname(icons._entry(proj) or proj)
        linked = [h for rels, h, _ in icons._links(open(icons._entry(proj), errors="ignore").read()) if "icon" in " ".join(rels)] if icons._entry(proj) else []
        mism = []
        for h in linked:
            f = icons._resolve(proj, ed, h)
            if f and os.path.isfile(f) and os.path.basename(f) in made and sha256(f) != made[os.path.basename(f)]: mism.append(h)
        ours = [h for h in linked if os.path.basename(re.sub(r"[?#].*$", "", h)) in made]
        r["checks"].append({"name": "the linked icons are the approved set (same bytes as icon.derivatives made)", "ok": bool(ours) and not mism,
                            "detail": (mism or None) if ours else "the page links none of the approved icon files"})
    else:
        r["checks"].append({"name": "keeping the existing icon was decided in the Decision Room", "ok": True})
    r["status"] = "ok" if all(c["ok"] for c in r["checks"]) else "failed"
    return _with_report(ctx, r, "icons.json")


def _with_report(ctx, r, name):
    """A measured check keeps its evidence as a file (so a failure is a quality finding, not a crash)."""
    rp = os.path.join(ctx["out_dir"], name)
    with open(rp, "w") as f: json.dump(r, f, indent=1)
    r["outputs"] = [{"path": rp, "role": "report", "format": "json"}]
    return r


def check_attribution(ctx):
    from . import standards
    return _with_report(ctx, standards.attribution(ctx["project"]), "attribution.json")


def check_standards(ctx):
    from . import standards
    p = ctx["params"]
    return _with_report(ctx, standards.check(ctx["project"], p.get("profile") or "personal", p.get("deliverable") or "app",
                                             analytics=p.get("analytics"), backend=p.get("backend"), analytics_decided=p.get("analytics_decided", True),
                                             accepted=(ctx.get("spec") or {}).get("accepted")), "standards.json")


def _test_command(proj):
    """How this project runs its own tests → (argv, why) or (None, reason). Detection only reads files."""
    pkg = os.path.join(proj, "package.json")
    if os.path.isfile(pkg):
        try: script = (json.load(open(pkg)).get("scripts") or {}).get("test") or ""
        except (OSError, ValueError): script = ""
        if script and "no test specified" not in script:
            return ["npm", "test", "--silent"], f"package.json scripts.test: {script[:80]}"
    py = []
    for d, dirs, files in os.walk(proj):
        dirs[:] = [x for x in dirs if x not in ("node_modules", ".git", ".venv", "venv", "__pycache__")]
        py += [os.path.join(d, f) for f in files if f.endswith(".py") and (f.startswith("test_") or f.endswith("_test.py"))]
    if py:
        import importlib.util
        toml = os.path.join(proj, "pyproject.toml")
        cfg = any(os.path.isfile(os.path.join(proj, f)) for f in ("pytest.ini", "conftest.py", "tox.ini")) or (os.path.isfile(toml) and "pytest" in open(toml).read())
        if importlib.util.find_spec("pytest") and (cfg or any("import pytest" in open(f, errors="ignore").read(20000) for f in py[:40])):
            return [sys.executable, "-m", "pytest", "-q"], "pytest (the tests import it or the project configures it)"
        start = os.path.relpath(os.path.commonpath([os.path.dirname(f) for f in py]), proj)
        return [sys.executable, "-m", "unittest", "discover", "-s", start, "-p", "*test*.py"], f"unittest discovery in {start}"
    return None, "no test command found (package.json scripts.test, or Python test_*.py files)"


def check_tests(ctx):
    """A tool is proven by its own tests: run them the way the project does and report exactly what happened.
    A project with no tests is `unverified` when tests were optional (an existing tool) and a failure when the work order required them."""
    import subprocess, time
    proj, required = ctx["project"], ctx["params"].get("required", True)
    cmd, why = _test_command(proj)
    if not cmd:
        r = {"status": "failed" if required else "ok", "checks": [{"name": "the project has tests to run", "ok": not required, "detail": why,
                                                                    **({} if required else {"category": "unverified", "cause": "no tests"})}]}
        return _with_report(ctx, r, "tests.json")
    if cmd[0] == "npm" and not os.path.isdir(os.path.join(proj, "node_modules")) and os.path.isfile(os.path.join(proj, "package-lock.json")):
        return {"status": "blocked", "reason": "the project's dependencies are not installed (node_modules missing)", "install": ["npm ci"], "outputs": []}
    t0 = time.time()
    try:
        pr = subprocess.run(cmd, cwd=proj, capture_output=True, text=True, timeout=ctx["task"].get("timeout", 900) - 30, stdin=subprocess.DEVNULL)
        code, tail = pr.returncode, (pr.stdout + "\n" + pr.stderr).strip()[-3000:]
    except subprocess.TimeoutExpired:
        code, tail = None, "timed out"
    except OSError as e:
        return {"status": "blocked", "reason": f"cannot run {cmd[0]}: {e}", "outputs": []}
    r = {"status": "ok" if code == 0 else "failed", "command": " ".join(cmd), "detected": why, "exit_code": code, "seconds": round(time.time() - t0, 1), "output_tail": tail,
         "checks": [{"name": f"the project's tests pass ({' '.join(cmd[-3:])})", "ok": code == 0, "detail": None if code == 0 else tail[-600:]}]}
    return _with_report(ctx, r, "tests.json")


def check_preserve(ctx):
    """An existing project's work survived the change (production/maturity.py baseline, taken at Discovery)."""
    from . import maturity
    p = ctx["params"]
    if not p.get("baseline") or not os.path.isfile(p["baseline"]):
        return {"status": "failed", "failure": "handoff", "error": "no preservation baseline was recorded at Discovery", "outputs": []}
    with open(p["baseline"]) as f: base = json.load(f)
    return _with_report(ctx, maturity.preserve_check(ctx["project"], base, p.get("allow") or (), p.get("kind") or "app"), "preserve.json")


def check_request(ctx):
    """Product QA (plan v2): the finished product against the person's request (production/qa.py)."""
    from . import qa
    return qa.check_request(ctx)


def check_features(ctx):
    """Every feature in tests/gitcraft.features.json, run in Chromium through TestCraft's scripted play (a fresh page each)."""
    from . import icons
    p = ctx["params"]; f = p.get("file")
    if not f or not os.path.isfile(f):
        if not p.get("required"):
            return _with_report(ctx, {"status": "ok", "checks": [{"name": "no feature checks in this project (optional here)", "ok": True}], "outputs": []}, "features.json")
        return _with_report(ctx, {"status": "failed", "checks": [{"name": "tests/gitcraft.features.json exists", "ok": False, "detail": "write one check per planned feature"}],
                                  "outputs": []}, "features.json")
    shape = icons.validate_features(f)
    if not all(c["ok"] for c in shape): return _with_report(ctx, {"status": "failed", "checks": shape, "outputs": []}, "features.json")
    feats = json.load(open(f))["features"]; checks, runs = list(shape), []
    for i, ft in enumerate(feats, 1):
        r = executors.studio_run("testcraft", "play", {"target": p.get("target") or ctx["project"], "steps": ft["steps"], "viewports": p.get("viewports") or ["phone"],
                                                       "out_dir": os.path.join(ctx["out_dir"], f"feature-{i}"), "name": f"feature_{i}", "register": False,
                                                       "min_change": 0})
        if r.get("status") == "blocked": return r
        failed = [f"{c['name']}" + (f" ({c.get('detail')})" if c.get("detail") not in (None, "", True) else "") for c in r.get("checks", []) if not c.get("ok")]
        ok = r.get("status") == "ok" and not failed
        checks.append({"name": f"feature: {ft['name']}", "ok": ok, "detail": None if ok else (failed[:4] or r.get("error"))})
        runs.append({"feature": ft["name"], "record": r.get("record"), "status": r.get("status")})
    return _with_report(ctx, {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks, "runs": runs, "outputs": []}, "features.json")


# ---------------------------------------------------------------- plan v2: one transactional integration per asset
MANIFEST = "gitcraft.assets.json"
JOURNAL = "integrate.journal.json"


def _atomic_json(path, data):
    tmp = f"{path}.gitcraft-tmp"
    with open(tmp, "w") as f: json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def read_manifest(proj):
    try:
        with open(os.path.join(proj, MANIFEST)) as f: m = json.load(f)
        return m if isinstance(m, dict) and isinstance(m.get("assets"), dict) else {"schema": "gitcraft-assets/1", "owner": "integration", "assets": {}}
    except (OSError, ValueError):
        return {"schema": "gitcraft-assets/1", "owner": "integration", "assets": {}}


def integrate_v2(ctx):
    """One upstream task's shipped outputs → the project, as one transaction:
      1 stage   every file (and its licence sidecar) is copied next to its destination as *.gitcraft-tmp and hash-verified
      2 check   overwriting a different existing file needs the production's consolidated replace_assets approval for that
                exact file and content (ctx["replace_auth"] {dest_rel: sha256}); anything else → needs_approval, nothing written
      3 commit  a journal (task folder) records each destination and its backup; every staged file is os.replace()d into place,
                then the asset manifest (owned by integration) is rewritten atomically; the journal is removed
      on any error during commit, every destination is restored from its backup (or removed if it was new) and the manifest
      is restored, so the project is left in its previous valid state. integrate_recover() does the same after a crash."""
    prod, proj, out = ctx["prod"], ctx["project"], ctx["out_dir"]
    auth = ctx.get("replace_auth") or {}
    items, checks = [], []
    for up in ctx["upstream"]:
        ship = up.get("ship")
        if not ship or up["state"] != "passed": continue
        dest_dir = ship["dest"].replace("$project", proj)
        if ship.get("library"):   # a 3D Department asset: export into the task folder, then commit like any other file
            res = up.get("result") or {}
            aid = res.get("asset_id") or (res.get("asset") or {}).get("id") or (res.get("library") or {}).get("asset")
            if not aid:
                return {"status": "failed", "failure": "handoff", "error": f"{up['id']} passed but reported no 3D library asset to export; nothing was copied",
                        "checks": [{"name": "the 3D task names its library asset", "ok": False}], "outputs": []}
            stage_dir = os.path.join(out, "library-export")
            r = executors.forgecraft_call("library_export", {"asset": aid, "dest": stage_dir}, timeout=600)
            if r.get("status") in ("failed", "blocked") or r.get("error") or not r.get("files"):
                return {"status": "failed", "error": f"3D asset {aid} could not be exported: {r.get('error') or r.get('reason')}",
                        "checks": [{"name": f"3D asset {aid} exported from the library (hash-verified)", "ok": False}], "outputs": []}
            lic = None
            try: lic = ((json.load(open(os.path.join(r["dir"], "asset.json"))).get("license") or {}).get("asset"))
            except (OSError, ValueError, KeyError, TypeError, AttributeError): pass
            for f in r["files"]:
                ext = os.path.splitext(f["path"])[1].lower().lstrip(".")
                role = "model" if ext in ("glb", "gltf", "fbx", "obj") else "model_source"
                items.append({"task": up.get("owner_task") or up["id"], "src": f["path"], "dest": os.path.join(dest_dir, os.path.relpath(f["path"], r.get("dir") or stage_dir)),
                              "sha256": f.get("sha256") or sha256(f["path"]), "role": role, "format": ext,
                              "sidecar": {"license": lic or "LicenseRef-Project-Owned", "source": {"production": prod["id"], "task": up["id"], "library_asset": aid}} if role == "model" else None})
            continue
        for o in select(up.get("outputs", []), ship.get("roles", ["*"]), ship.get("formats")):
            dd = (ship.get("role_dest") or {}).get(o.get("role"), ship["dest"]).replace("$project", proj)
            side = {"license": up.get("license") or "LicenseRef-Project-Owned", "attribution": up.get("attribution"),
                    "source": {"production": prod["id"], "task": up["id"], "record": (up.get("result") or {}).get("record")}}
            folder = o.get("role") in (ship.get("folder_licence_roles") or [])
            items.append({"task": up.get("owner_task") or up["id"], "src": o["path"], "dest": os.path.join(dd, o.get("rel") or os.path.basename(o["path"])), "sha256": o.get("sha256") or sha256(o["path"]),
                          "role": o.get("role"), "format": o.get("format"), "sidecar": None if folder else side, "folder_sidecar": (os.path.join(dd, "LICENSE.assets.json"), side) if folder else None})
    seen = {}
    for it in items:   # two outputs of this task for one path
        if it["dest"] in seen and seen[it["dest"]] != it["sha256"]:
            return {"status": "failed", "failure": "conflict", "error": "integration conflict: different files ship to the same path; nothing was copied",
                    "checks": [{"name": "no two outputs ship to the same path", "ok": False, "detail": os.path.relpath(it["dest"], proj)}], "outputs": []}
        seen[it["dest"]] = it["sha256"]
    man = read_manifest(proj)
    owned = {k: v for k, v in man["assets"].items() if v.get("task") not in {it["task"] for it in items}}
    for it in items:   # another task's integrated file at this path is an integration conflict, never a silent overwrite
        rel = os.path.relpath(it["dest"], proj)
        if rel in owned and owned[rel]["sha256"] != it["sha256"]:
            return {"status": "failed", "failure": "conflict", "error": f"integration conflict: {rel} is already integrated from {owned[rel]['task']}; nothing was copied",
                    "checks": [{"name": "no two deliverables ship to the same path", "ok": False, "detail": [rel, owned[rel]["task"]]}], "outputs": []}
    mine = {k: v for k, v in man["assets"].items() if v.get("task") in {it["task"] for it in items}}
    over = []
    for it in items:
        rel = os.path.relpath(it["dest"], proj)
        if os.path.exists(it["dest"]) and sha256(it["dest"]) != it["sha256"] and not (rel in mine and mine[rel]["sha256"] == sha256(it["dest"])):
            it["replaces"] = True
            if auth.get(rel) != it["sha256"]: over.append({"file": rel, "sha256": it["sha256"], "task": it["task"]})
    if over:
        return {"status": "needs_approval", "approval": "replace_assets", "consolidated": True,
                "reason": f"{len(over)} existing project file(s) would be replaced by different content", "files": over,
                "checks": [{"name": "no existing file overwritten without the production's replace_assets approval for that exact file", "ok": False,
                            "detail": [o["file"] for o in over]}], "outputs": []}
    # 1 stage
    staged, checks = [], []
    try:
        for it in items:
            os.makedirs(os.path.dirname(it["dest"]), exist_ok=True)
            tmp = it["dest"] + ".gitcraft-tmp"
            shutil.copy2(it["src"], tmp)
            staged.append(tmp)
            if sha256(tmp) != it["sha256"]: raise IOError(f"{os.path.relpath(it['dest'], proj)}: staged copy does not match its sha256")
            for sc in [(it["dest"] + ".license.json", it["sidecar"])] if it.get("sidecar") else ([it["folder_sidecar"]] if it.get("folder_sidecar") else []):
                with open(sc[0] + ".gitcraft-tmp", "w") as f: json.dump(sc[1], f, indent=1)
                staged.append(sc[0] + ".gitcraft-tmp")
    except (OSError, IOError) as e:
        for t in staged:
            try: os.remove(t)
            except OSError: pass
        return {"status": "failed", "error": f"staging failed, nothing was written: {e}", "checks": [{"name": "every file staged and hash-verified", "ok": False, "detail": str(e)}], "outputs": []}
    # 2 commit, journalled
    new_man = {"schema": "gitcraft-assets/1", "owner": "integration", "assets": dict(owned)}
    for it in items:
        new_man["assets"][os.path.relpath(it["dest"], proj)] = {"task": it["task"], "role": it["role"], "format": it["format"], "sha256": it["sha256"]}
    bdir = os.path.join(out, "backup"); os.makedirs(bdir, exist_ok=True)
    targets = [t[:-len(".gitcraft-tmp")] for t in staged] + [os.path.join(proj, MANIFEST)]
    journal = {"status": "committing", "project": proj, "entries": []}
    for n, d in enumerate(targets):
        e = {"dest": d, "backup": None, "staged": d + ".gitcraft-tmp" if d != targets[-1] else None}
        if os.path.exists(d):
            e["backup"] = os.path.join(bdir, f"{n}.bak"); shutil.copy2(d, e["backup"])
        journal["entries"].append(e)
    _atomic_json(os.path.join(out, JOURNAL), journal)
    try:
        if ctx.get("_fail_after"):   # tests: an interruption in the middle of the commit
            for e in journal["entries"][:ctx["_fail_after"]]:
                if e["staged"]: os.replace(e["staged"], e["dest"])
            raise OSError("simulated failure during commit")
        for e in journal["entries"]:
            if e["staged"]: os.replace(e["staged"], e["dest"])
        _atomic_json(os.path.join(proj, MANIFEST), new_man)
        bad = [os.path.relpath(it["dest"], proj) for it in items if sha256(it["dest"]) != it["sha256"]]
        if bad: raise OSError(f"after commit the hash does not match: {bad}")
    except OSError as e:
        rolled = integrate_recover(out)
        return {"status": "failed", "error": f"commit failed and was rolled back (the project is as it was): {e}", "rolled_back": rolled,
                "checks": [{"name": "every file committed and hash-verified", "ok": False, "detail": str(e)}], "outputs": []}
    os.remove(os.path.join(out, JOURNAL)); shutil.rmtree(bdir, ignore_errors=True)
    manifest, outs = [], []
    for it in items:
        rel = os.path.relpath(it["dest"], proj)
        manifest.append({"dest": it["dest"], "dest_rel": rel, "sha256": it["sha256"], "role": it["role"], "format": it["format"], "task": it["task"],
                         "replaced": bool(it.get("replaces"))})
        outs.append({"path": it["dest"], "role": it["role"], "format": it["format"], "sha256": it["sha256"], "ok": True})
        checks.append({"name": f"{rel} committed and hash-verified", "ok": True})
    if not items: checks.append({"name": "something to integrate", "ok": True, "detail": "the task shipped no outputs"})
    with open(os.path.join(out, "integrated.json"), "w") as f: json.dump(manifest, f, indent=1)
    return {"status": "ok", "outputs": outs, "checks": checks, "integrated": manifest, "replaced": [m["dest_rel"] for m in manifest if m["replaced"]],
            "manifest_sha256": sha256(os.path.join(proj, MANIFEST))}


def integrate_recover(out_dir):
    """Undo an interrupted or failed commit from its journal: restore each destination from its backup (or remove it if it
    was new), remove staged files. Returns what was done; nothing when there is no journal."""
    jp = os.path.join(out_dir, JOURNAL)
    try: j = json.load(open(jp))
    except (OSError, ValueError): return []
    done = []
    for e in j.get("entries", []):
        if e.get("backup") and os.path.exists(e["backup"]):
            shutil.copy2(e["backup"], e["dest"]); done.append(f"restored {e['dest']}")
        elif os.path.exists(e["dest"]) and not e.get("backup"):
            os.remove(e["dest"]); done.append(f"removed {e['dest']}")
        if e.get("staged") and os.path.exists(e["staged"]): os.remove(e["staged"])
    os.remove(jp); shutil.rmtree(os.path.join(out_dir, "backup"), ignore_errors=True)
    return done


def expected_manifest(ledger, inherited=None):
    """What the asset manifest must list, {path: sha256}: this production's ledger, plus the entries the project already
    carried when the production began (`inherited`: an earlier production's assets, still the project's), less any of those
    whose task this production has integrated again (integrate() replaces a task's entries as a set)."""
    again = {m.get("task") for m in ledger}
    exp = {k: v.get("sha256") for k, v in (inherited or {}).items() if v.get("task") not in again}
    exp.update({m["dest_rel"]: m["sha256"] for m in ledger})
    return exp


def integrate_final(ctx):
    """The final integration check: every artifact in the ledger (ctx["integrated"]) is in the project with its hash, the
    asset manifest lists exactly those files with those hashes (and, unchanged, whatever it listed before this production:
    ctx["inherited"]), and no staged or journalled integration is left behind."""
    proj, ledger = ctx["project"], ctx.get("integrated") or []
    checks = []
    bad = [m["dest_rel"] for m in ledger if not os.path.isfile(m["dest"]) or sha256(m["dest"]) != m["sha256"]]
    checks.append({"name": "every integrated file is in the project with its committed hash", "ok": not bad, "detail": bad[:20] or None})
    man = read_manifest(proj)["assets"]
    led = expected_manifest(ledger, ctx.get("inherited"))
    diff = sorted(k for k in set(man) | set(led) if man.get(k, {}).get("sha256") != led.get(k))
    checks.append({"name": f"{MANIFEST} lists exactly the integrated files and hashes", "ok": not diff, "detail": diff[:20] or None})
    left = []
    for d, ds, fs in os.walk(proj):
        ds[:] = [x for x in ds if x not in (".git", "node_modules")]
        left += [os.path.relpath(os.path.join(d, f), proj) for f in fs if f.endswith(".gitcraft-tmp")]
    checks.append({"name": "no staged integration left in the project", "ok": not left, "detail": left[:20] or None})
    return {"status": "ok" if all(c["ok"] for c in checks) else "failed", "checks": checks, "outputs": [],
            "integrated_count": len(ledger)}
