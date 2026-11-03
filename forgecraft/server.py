#!/usr/bin/env python3
"""ForgeCraft: the GITCRAFT 3D Department's orchestrator, as an MCP server (stdio, JSON-RPC 2.0,
stdlib only). Started by scripts/mcp.sh behind the same guard + Landlock sandbox as every tool.

ForgeCraft decides how an asset gets made (routing), runs the external generators (Meshroom,
TripoSR, Hunyuan3D), has MeshCraft do every piece of Blender work (modelling, mesh processing,
materials, rigging, previews, export, validation), checks the deliverable in the engine, records
provenance and licensing on the asset's single library version, and hands it off. Tool names are
unchanged from ForgeCraft 1.0; blockbench_*, mixamo_* and the library/job tools delegate to the
one shared implementation. Long jobs can run in the background ("wait": false, poll job_get)."""
import json, os, sys, threading, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import _gitcraft3d  # noqa: F401  (loads gitcraft3d by path; see _gitcraft3d.py)
from gitcraft3d import hardware, jobs, library, routing, deferred
import meshcraft as mc
import pipeline

VERSION = "2.0.0"
S = lambda **p: {"type": "object", "properties": p}
STR, INT, BOOL, OBJ, NUM = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "object"}, {"type": "number"}
ARR = lambda t=STR: {"type": "array", "items": t}
GEN_OPTS = dict(name=STR, profiles=ARR(), formats={"type": "array", "items": STR, "description": "legacy: glb, gltf, fbx, obj, stl → MeshCraft export profiles"},
                max_tris=INT, bake={"type": "integer", "description": "PBR bake resolution (web-pbr)"},
                asset_id={"type": "string", "description": "add the result as a new version of this asset"},
                handoff_dir={"type": "string", "description": "also copy the finished asset here (inside a GITCRAFT root), hash-verified"},
                tags=ARR(), wait={"type": "boolean", "description": "false = run in the background and return the job id"})

TOOLS = {
 "hardware_probe": ("CPU/RAM/GPU/disk and every 3D capability (MeshCraft/Blender, Blockbench, Mixamo, Meshroom, TripoSR, Hunyuan3D) with the exact reason any is unavailable, and job limits. Same probe as MeshCraft's.", S()),
 "route": ("Which capability the 3D Department would use for a brief (and optional reference images) on this machine, the fallbacks, and why. Does not generate.",
           S(brief=STR, images=ARR(), tool={"type": "string", "description": "force a preferred tool"}, kind=STR, template=STR, params=OBJ)),
 "generate": ("The full production pipeline for a brief: route → generate (MeshCraft template, Blockbench via MeshCraft, Meshroom, TripoSR or Hunyuan3D) → MeshCraft builds/imports, cleans, colours and bakes, rigs/animates, renders previews, exports per engine profile and validates → engine check in three.js r170 → one library version with routing, licence and provenance → optional hand-off.",
              S(brief=STR, images=ARR(), tool=STR, kind=STR, template=STR, params=OBJ,
                template_params={"type": "object", "description": "extra parameters for the MeshCraft template (see MeshCraft list_templates)"}, **GEN_OPTS)),
 "process_mesh": ("Bring an existing mesh (GLB/glTF/FBX/OBJ/STL/PLY) into the library through MeshCraft process_mesh: optional scan crop, cleanup, decimation, rescale, PBR bake, previews, exports, validation, engine check.",
                  S(input=STR, crop=NUM, crop_floor=BOOL, target_size=NUM, **GEN_OPTS)),
 "photogrammetry": ("Reconstruct a mesh from overlapping photos with Meshroom/AliceVision (CUDA: full pipeline; CPU: draft meshing), then MeshCraft process_mesh (crop to subject, cleanup, rescale, PBR bake). Slow: runs in the background by default.",
                    S(images=ARR(), meshroom_overrides=ARR(), crop={"type": "number", "description": "keep the centre of the capture (fraction of the half-width, e.g. 0.25)"},
                      target_size={"type": "number", "description": "rescale so the largest side is this many metres (scans have no real scale)"}, **GEN_OPTS)),
 "blockbench_build": ("Write an editable Blockbench project (.bbmodel 5.0) from a cube template (boat, chest, crab, crate, lantern), coloured from the project palette. Delegates to MeshCraft.",
                      S(template=STR, name=STR, out=STR, palette=STR, roles=OBJ)),
 "blockbench_inspect": ("Read a .bbmodel and report format version, elements, textures and problems. Delegates to MeshCraft.", S(path=STR)),
 "mixamo_guide": ("The supported Mixamo workflow (no API: a person uses mixamo.com) and the bone names that are matched. Delegates to MeshCraft.", S()),
 "mixamo_prepare_upload": ("Export a character (library asset id or file) as a mesh-only T-pose FBX for Mixamo's auto-rigger. Delegates to MeshCraft.", S(asset=STR, input=STR, out=STR)),
 "mixamo_apply": ("Merge Mixamo FBX animation downloads onto a Mixamo-skeleton character (library asset id → new version, or a file) via MeshCraft mixamo_apply, then engine-check and record.",
                  S(character=STR, animations=ARR(), **GEN_OPTS)),
 "compose_scene": ("Compose library assets into a scene via MeshCraft compose_scene: items [{asset, version?, name, location, rotation, scale, attach_to:'<name>:<socket_*>'}], ocean, sun, sky, camera, hero render, scene GLB + .blend; engine-checked and recorded.",
                   S(items={"type": "array", "items": OBJ}, camera=ARR(NUM), look_at=ARR(NUM), lens=NUM, sun=ARR(NUM), sky=STR, samples=INT, resolution=ARR(INT), **GEN_OPTS)),
 "library_search": ("Search the shared 3D asset library (MeshCraft and ForgeCraft write the same one) by text, template/kind, tool or validation status.", S(query=STR, kind=STR, template=STR, tool=STR, status=STR)),
 "library_get": ("Full record of an asset version: files with SHA-256, MeshCraft validation, and ForgeCraft's routing, licence, provenance, previews, engine check.", S(asset=STR, version=INT)),
 "library_export": ("Copy an asset version into a folder inside a GITCRAFT root and verify every hash: the hand-off to other tools and game repos.",
                    S(asset=STR, dest=STR, version=INT, kinds=ARR())),
 "jobs_list": ("Recent jobs (ForgeCraft orchestration jobs and the MeshCraft jobs they started) with status.", S(limit=INT, status=STR)),
 "job_get": ("One job: attempts, stages with timing and errors, routing plan, compute needs, child jobs.", S(job=STR)),
 "job_retry": ("Re-run a failed or blocked job with its original request (ForgeCraft jobs re-run here; MeshCraft jobs in MeshCraft).", S(job=STR, wait=BOOL)),
}


def _roots(): return [r for r in os.environ.get("GITCRAFT_ROOTS", os.environ.get("GITCRAFT_ROOT", "")).split(":") if r]


def _gen(spec, default_wait=True):
    wait = spec.pop("wait", default_wait)
    if not wait: return {"job": pipeline.start(spec), "status": "started", "poll": "job_get"}
    return pipeline.summary(pipeline.run(spec))


def _source(asset):
    """A library asset's editable source (.blend), else its first export."""
    md = library.get(asset)
    f = next((f for f in md["files"] if f["kind"] == "blend"), None) or next(f for f in md["files"] if f["kind"] == "export")
    return os.path.join(md["dir"], f["path"])


def call(name, a):
    a = dict(a or {})
    if name == "hardware_probe": return hardware.probe(_roots())
    if name == "route": return routing.route(a.get("brief", ""), routing.expand_images(a.get("images") or []), hardware.probe(_roots()),
                                             prefer=a.get("tool"), kind=a.get("kind"), params=a.get("params"), template=a.get("template"))
    if name == "generate": return _gen(a)
    if name == "process_mesh":
        a["input_mesh"] = a.pop("input"); a.setdefault("brief", os.path.basename(a["input_mesh"])); return _gen(a)
    if name == "photogrammetry":
        a["tool"] = "meshroom"; a.setdefault("brief", "photogrammetry reconstruction"); return _gen(a, default_wait=False)
    if name == "compose_scene": return _gen(dict(a, tool="meshcraft_scene", brief=(a.get("name") or "") + " scene"))
    if name == "mixamo_apply": return _gen(dict(a, tool="mixamo", brief=a.get("name") or "mixamo character"))
    # delegated to MeshCraft (the one implementation); argument names from ForgeCraft 1.0 still accepted
    if name == "blockbench_build":
        out = a.get("out") or os.path.join(os.environ.get("GITCRAFT_ROOT", "."), f"{pipeline.slugify(a.get('name') or a['template'])}.bbmodel")
        return mc.call("blockbench_build", dict({k: v for k, v in a.items() if k != "name"}, out=out, palette=a.get("palette") or pipeline.PALETTE))
    if name == "blockbench_inspect": return mc.call("blockbench_inspect", a)
    if name == "mixamo_guide": return mc.call("mixamo_guide", a)
    if name == "mixamo_prepare_upload":
        src = a.get("input") or _source(a["asset"])
        out = a.get("out") or os.path.join(os.environ.get("GITCRAFT_ROOT", "."), f"{pipeline.slugify(a.get('asset') or os.path.basename(src))}_mixamo_upload.fbx")
        return mc.call("mixamo_prepare_upload", {"input": src, "out": out}, timeout=600)
    if name == "library_search":
        r = library.search(a.get("query", ""), a.get("template") or a.get("kind"), a.get("tool"), a.get("status"), a.get("limit", 50))
        return r
    if name == "library_get": return library.get(a["asset"], a.get("version"))
    if name == "library_export": return library.export(a["asset"], a["dest"], a.get("version"), a.get("kinds"))
    if name == "jobs_list": return jobs.list_jobs(a.get("limit", 20), a.get("status"))
    if name == "job_get": return jobs.get(a["job"])
    if name == "job_retry":
        rec = jobs.get(a["job"])
        if rec["tool"] != "generate":   # a MeshCraft job: MeshCraft re-runs it
            return mc.call("job_retry", {"job": rec["id"]})
        if not a.get("wait", True):
            threading.Thread(target=pipeline.retry, args=(rec["id"],), daemon=True).start(); return {"job": rec["id"], "status": "started"}
        return pipeline.summary(pipeline.retry(rec["id"]))
    raise KeyError(f"unknown tool {name}")


def main():
    out = sys.stdout
    lock = threading.Lock()
    # Before MeshCraft's Blender is installed, list only forgecraft_status and announce the full list once it is
    # (tools/list_changed): see gitcraft3d/deferred.py. Registered early, usable as soon as the install finishes.
    waiting = [not deferred.ready()]

    def send(m):
        with lock: out.write(json.dumps(m, default=str) + "\n"); out.flush()
    if waiting[0]:
        def blender_arrived():
            waiting[0] = False
            send({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})
        deferred.Watcher(blender_arrived)
    for line in sys.stdin:
        try: msg = json.loads(line)
        except ValueError: continue
        mid, method, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None: continue  # notifications
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {"listChanged": True}},
                  "serverInfo": {"name": "forgecraft", "version": VERSION},
                  "instructions": "GITCRAFT 3D Department orchestrator. Start with hardware_probe or route; generate runs the whole production pipeline (MeshCraft does the Blender work); library_export hands assets to other tools."}})
        elif method == "tools/list":
            listed = ([{"name": "forgecraft_status", "description": "ForgeCraft status. " + deferred.install_hint("ForgeCraft"),
                        "inputSchema": {"type": "object", "properties": {}}}] if waiting[0]
                      else [{"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()])
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": listed}})
        elif method == "tools/call":
            name, args = p.get("name"), p.get("arguments") or {}

            def work(mid=mid, name=name, args=args):
                try:
                    if waiting[0] and not deferred.ready():
                        if name != "forgecraft_status": raise RuntimeError(deferred.install_hint("ForgeCraft"))
                        r = deferred.status("ForgeCraft")
                        send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(r, indent=1)}]}})
                        return
                    r = call(name, args)
                    err = isinstance(r, dict) and r.get("status") in ("failed", "blocked")
                    send({"jsonrpc": "2.0", "id": mid, "result": {"isError": err, "content": [{"type": "text", "text": json.dumps(r, indent=1, default=str)}]}})
                except Exception as e:
                    send({"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}]}})
                    traceback.print_exc(file=sys.stderr)
            threading.Thread(target=work, daemon=True).start()
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})


if __name__ == "__main__":
    main()
