"""The Production Director's own steps (everything else is a department's or the agent's).

  scaffold   create the project folder and its asset folders when missing; never writes a file
  integrate  copy every passed upstream output that ships (task `ship`: roles, formats, destination) into the
             project, hash-verified, each with a .license.json sidecar from its provenance record. Two tasks
             shipping different files to one path is an integration conflict (failed, nothing copied); an
             existing different file in the project is never overwritten without `replace_assets` (needs approval)
  licences   AssetCraft scan of the shipped folder, then its licence report (unknown / NC / ND licences fail)
"""
import hashlib, json, os, shutil
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


def scaffold(ctx):
    proj = ctx["project"]; made = []
    if not ctx["inside_roots"](proj): return {"status": "failed", "failure": "request", "error": f"GITCRAFT policy: project {proj} is outside the workspace roots"}
    if not os.path.isdir(proj): os.makedirs(proj); made.append(proj)
    for d in ctx["params"].get("dirs", []):
        p = os.path.join(proj, d)
        if not os.path.isdir(p): os.makedirs(p); made.append(p)
    return {"status": "ok", "outputs": [], "created": made, "checks": [{"name": "project folder exists inside the roots", "ok": os.path.isdir(proj)}]}


def integrate(ctx):
    prod, proj = ctx["prod"], ctx["project"]
    previous = {m["dest"]: m for m in (ctx.get("previous_manifest") or [])}
    plan, conflicts = {}, []
    for up in ctx["upstream"]:
        ship = up.get("ship")
        if not ship or up["state"] != "passed": continue
        dest_dir = ship["dest"].replace("$project", proj)
        if ship.get("library"):   # a 3D Department asset: ForgeCraft's hash-verified library export
            aid = (up.get("result") or {}).get("asset_id") or ((up.get("result") or {}).get("library") or {}).get("asset")
            if aid: plan[f"library:{aid}"] = {"task": up["id"], "library_asset": aid, "dest_dir": dest_dir}
            continue
        for o in select(up.get("outputs", []), ship.get("roles", ["*"]), ship.get("formats")):
            dest = os.path.join(dest_dir, os.path.basename(o["path"]))
            item = {"task": up["id"], "src": o["path"], "dest": dest, "sha256": o.get("sha256") or sha256(o["path"]), "role": o.get("role"), "format": o.get("format"),
                    "license": up.get("license"), "attribution": up.get("attribution"), "record": (up.get("result") or {}).get("record")}
            if dest in plan and plan[dest]["sha256"] != item["sha256"]:
                conflicts.append({"dest": os.path.relpath(dest, proj), "tasks": [plan[dest]["task"], up["id"]]})
            plan[dest] = item
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
            ok = r.get("status") not in ("failed", "blocked") and not r.get("error")
            checks.append({"name": f"3D asset {it['library_asset']} exported from the library (hash-verified)", "ok": ok, "detail": r.get("error") or r.get("reason")})
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        replaced = os.path.exists(dest) and sha256(dest) != it["sha256"]
        shutil.copy2(it["src"], dest)
        ok = sha256(dest) == it["sha256"]
        side = {"license": it.get("license") or "LicenseRef-Project-Owned", "attribution": it.get("attribution"),
                "source": {"production": prod["id"], "task": it["task"], "record": it.get("record")}}
        json.dump(side, open(dest + ".license.json", "w"), indent=1)
        rel = os.path.relpath(dest, proj)
        manifest.append({"dest": dest, "dest_rel": rel, "sha256": it["sha256"], "role": it["role"], "format": it["format"], "task": it["task"], "replaced": replaced})
        outs.append({"path": dest, "role": it["role"], "format": it["format"], "sha256": it["sha256"], "ok": ok})
        checks.append({"name": f"{rel} copied and hash-verified", "ok": ok})
    if not manifest and not checks:
        checks.append({"name": "something to integrate", "ok": True, "detail": "no shipped outputs (nothing upstream ships)"})
    json.dump(manifest, open(os.path.join(ctx["out_dir"], "integrated.json"), "w"), indent=1)
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
