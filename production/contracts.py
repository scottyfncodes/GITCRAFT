"""Every department's contract in one shape, for the Director and for anyone reading the plan:

  accepts     the requests it takes (actions with their parameter schemas)
  produces    what it outputs (roles/formats per action, where declared)
  requires    runtime dependencies (each checked before running; missing → blocked, with the install command)
  success     how a result is judged (the department's own checks + the production gate)
  failure     how failure and blocked are reported
  storage     where outputs go
  provenance  how provenance and licensing are recorded

Studio departments are read from their manifests (studio/departments/<name>/manifest.json) so this never
drifts from the code; the 3D Department, DESIGNCRAFT, the 2D ArtCraft tools and the Director's built-ins are
described here."""
import json, os
from . import REPO

STUDIO_COMMON = {
    "success": "every output opens as its format and is SHA-256 hashed; every department check passes (status ok); then the production gate (e.g. a minimum score) decides passed",
    "failure": "status failed with error, hint and stage; status blocked with reason, install command and alternatives (never a substitute output)",
    "storage": "the task's out_dir inside the production store (<root>/gitcraft-out/production/<id>/tasks/<task>/); shipped outputs are copied into the project by integrate",
    "provenance": "<out_dir>/<name>.studio.json: request, tools used with licences, output licence, attribution, outputs with SHA-256, checks, timings; outputs registered in the AssetCraft catalogue",
}

OTHERS = {
    "forgecraft": {"title": "3D Department (ForgeCraft → MeshCraft)", "executor": "forgecraft",
                   "accepts": "brief (+ images, template, params, profiles); tools: generate, process_mesh, photogrammetry, compose_scene, mixamo_apply, library_export",
                   "produces": "one versioned library asset: .blend, previews, GLB/FBX/OBJ exports per engine profile, validation report",
                   "requires": "MeshCraft's Blender 5.2 (scripts/install.sh meshcraft); Meshroom/TripoSR/Hunyuan3D per route (hardware_probe says which)",
                   "success": "MeshCraft validation + Khronos glTF validator + the main GLB loaded and animated in three.js (engine check)",
                   "failure": "a job record with attempts and the stage that failed; `blocked` when no capability on this machine can honour the brief (never a 2D substitute)",
                   "storage": "the shared 3D library ($GITCRAFT_3D_LIBRARY); library_export copies it into the project, hash-verified",
                   "provenance": "the library version records routing, licences of every tool, provenance and the engine check; job records link parent/child"},
    "designcraft": {"title": "DESIGNCRAFT (game-design intelligence, gamedesign/)", "executor": "designcraft",
                    "accepts": "a game repository (read-only; never runs it)", "produces": "assessment JSON: design model, findings with evidence levels, proposals, scores",
                    "requires": "python3 (stdlib)", "success": "advisory in a production: recorded as evidence, never blocks",
                    "failure": "failed with the CLI error", "storage": "the task's out_dir (the committed history/designcraft is never written by a production)",
                    "provenance": "the assessment carries its method hash, the game's commit and content hash"},
    "agent": {"title": "Claude (the agent)", "executor": "agent",
              "accepts": "a work order: brief, instructions, findings to fix, tools to use (incl. the 2D ArtCraft MCP servers: vectorcraft, photocraft, designcraft, effectcraft, filmcraft, lightcraft, pdfcraft), expected outputs, the hand-off of upstream files",
              "produces": "the expected files and/or project changes, submitted with production_submit",
              "requires": "the work order's inputs (all upstream tasks passed)",
              "success": "every expected file exists inside the roots and opens as its format (JSON keys checked); a fix must actually change the project; a deployment must come with a passing check against the live URL",
              "failure": "a submission that does not validate is rejected and the work order stays open",
              "storage": "the task's out_dir, or the project for code", "provenance": "the submission (files, notes, licence) is in the production record and events.jsonl"},
    "builtin": {"title": "Production Director built-ins", "executor": "builtin",
                "accepts": "scaffold {dirs}; integrate (upstream outputs per `ship`); licences {folder}; release",
                "produces": "project folders; integrated assets + .license.json sidecars + integrated.json; licence report + ATTRIBUTION.md; RELEASE.md",
                "requires": "nothing beyond the Studio runtime for licences (AssetCraft)",
                "success": "integrate: every copy hash-verified, no conflicts, no unapproved overwrite; release: every acceptance criterion passed on the build being released",
                "failure": "integration conflict → failed; overwrite of a different existing file → needs_approval", "storage": "the project (integrate) and the production store",
                "provenance": "sidecars point at the producing task and its .studio.json record"},
}


def studio_contracts():
    base = os.path.join(REPO, "studio", "departments")
    out = {}
    for d in sorted(os.listdir(base)):
        mp = os.path.join(base, d, "manifest.json")
        if not os.path.isfile(mp): continue
        m = json.load(open(mp))
        out[d] = dict(STUDIO_COMMON, title=m.get("title", d), executor="studio",
                      accepts={a: {"summary": s["summary"], "required": s.get("params", {}).get("required", []), "params": sorted(s.get("params", {}).get("properties", {}))}
                               for a, s in m["actions"].items()},
                      produces={a: s.get("outputs") for a, s in m["actions"].items() if s.get("outputs")},
                      requires={k: {"kind": v.get("kind"), "install": v.get("install")} for k, v in m.get("dependencies", {}).items()},
                      output_license=m.get("output_license"))
    return out


def all_contracts():
    return {"studio": studio_contracts(), **OTHERS}
