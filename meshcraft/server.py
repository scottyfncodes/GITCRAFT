#!/usr/bin/env python3
"""MeshCraft: the GITCRAFT 3D Department as an MCP server (stdio, JSON-RPC 2.0, stdlib only).

Started by scripts/mcp.sh behind the same guard + Landlock sandbox as the other seven tools.
Long jobs (photogrammetry, AI generation) can run in the background: pass "wait": false and
poll job_get. Everything a tool returns is real output from a real run; failures and
"blocked" (tool unavailable here) come back as errors with the reason."""
import json, os, subprocess, sys, threading, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hardware, library, pipeline, routing
from backends import blockbench, mixamo

VERSION = "1.0.0"
S = lambda **p: {"type": "object", "properties": p}
STR, INT, BOOL, OBJ = {"type": "string"}, {"type": "integer"}, {"type": "boolean"}, {"type": "object"}
ARR = lambda t=STR: {"type": "array", "items": t}
GEN_OPTS = dict(name=STR, max_tris=INT, bake={"type": "integer", "description": "texture bake resolution (0 = keep materials, no bake)"},
                formats=ARR(), turntable=INT, asset_id={"type": "string", "description": "add the result as a new version of this asset"},
                handoff_dir={"type": "string", "description": "also copy the finished asset here (inside a GITCRAFT root)"},
                tags=ARR(), wait={"type": "boolean", "description": "false = run in the background and return the job id"})

TOOLS = {
 "hardware_probe": ("CPU/RAM/GPU, installed 3D backends (Blender, Blockbench, Mixamo, Meshroom, TripoSR, Hunyuan3D) with the exact reason any is unavailable, and job limits.", S()),
 "route": ("Show which tool MeshCraft would use for a brief (and optional reference images) on this machine, the fallbacks, and why. Does not generate.",
           S(brief=STR, images=ARR(), tool={"type": "string", "description": "force a preferred tool"})),
 "generate": ("Run the full 3D pipeline for a brief: route → generate (Blender procedural, Blockbench, TripoSR, Hunyuan3D or Meshroom) → clean → optimise → UV → bake textures → rig/animate → previews → GLB/glTF/FBX/OBJ/STL/.blend → validate → library.",
              S(brief=STR, images=ARR(), tool=STR, kind=STR, params=OBJ, clips=ARR(), **GEN_OPTS)),
 "process_mesh": ("Import an existing mesh (GLB/glTF/FBX/OBJ/STL/PLY/.bbmodel) and run it through cleanup, optimisation, UV, bake, previews, export and validation into the library.",
                  S(input=STR, keep_materials=BOOL, target_size={"type": "number", "description": "scale so the largest side is this many metres"}, **GEN_OPTS)),
 "photogrammetry": ("Reconstruct a textured mesh from overlapping photos with Meshroom/AliceVision (CUDA: full pipeline; CPU: draft meshing). Slow: defaults to running in the background.",
                    S(images=ARR(), meshroom_overrides=ARR(), crop={"type": "number", "description": "keep the centre of the capture: radius as a fraction of the scene half-width (e.g. 0.3)"},
                      target_size={"type": "number", "description": "rescale so the largest side is this many metres (scans have no real scale)"}, **GEN_OPTS)),
 "blockbench_build": ("Write an editable Blockbench project (.bbmodel) from a cube template (crate, chest, crab, lantern, boat). Open it in Blockbench to edit; import with process_mesh.",
                      S(template=STR, name=STR, out=STR)),
 "blockbench_inspect": ("Read a .bbmodel and report format version, elements, textures and problems.", S(path=STR)),
 "mixamo_guide": ("The supported Mixamo workflow (Mixamo has no API: a person uploads/downloads at mixamo.com) and the bone names MeshCraft matches.", S()),
 "mixamo_prepare_upload": ("Export a character asset as an unrigged T-pose FBX for Mixamo's auto-rigger.", S(asset=STR, out=STR)),
 "mixamo_apply": ("Merge Mixamo FBX animation downloads onto a Mixamo-skeleton character (library asset id or file) and add the result to the library.",
                  S(character=STR, animations=ARR(), **GEN_OPTS)),
 "compose_scene": ("Compose library assets into a scene in Blender (placements or socket attachments, ocean, lights, camera), render a hero image and export scene GLB + .blend.",
                   S(items={"type": "array", "items": OBJ, "description": "[{asset, version?, location[x,y,z], rotation[deg], scale, attach_to:'<host name>:<socket>'}]"},
                     camera=ARR({"type": "number"}), look_at=ARR({"type": "number"}), samples=INT, **GEN_OPTS)),
 "library_search": ("Search the 3D asset library by text, kind, source tool or validation status.", S(query=STR, kind=STR, tool=STR, status=STR)),
 "library_get": ("Full metadata for an asset version: geometry, textures, rig, animations, sockets, previews, files with hashes, licence, provenance, validation.", S(asset=STR, version=INT)),
 "library_export": ("Copy an asset version (exports, textures, previews, asset.json) into a folder inside a GITCRAFT root: the handoff to other tools and game repos.",
                    S(asset=STR, dest=STR, version=INT, formats=ARR())),
 "jobs_list": ("Recent pipeline jobs with status and stages.", S(limit=INT)),
 "job_get": ("One job: per-stage state/timing/errors, routing plan, compute needs, attempts.", S(job=STR)),
 "job_retry": ("Re-run a failed or blocked job with the same request.", S(job=STR, wait=BOOL)),
}


def _bg(spec, job_id=None):
    job = pipeline.Job(spec, job_id); job.save()
    threading.Thread(target=pipeline.run, args=(spec, job.id) if not job_id else (None, job_id), daemon=True).start()
    return {"job": job.id, "status": "started", "poll": "job_get"}


def _gen(spec, default_wait=True):
    wait = spec.pop("wait", default_wait)
    if not wait: return _bg(spec)
    rec = pipeline.run(spec)
    return _summ(rec)


def _summ(rec):
    out = {"job": rec["id"], "status": rec["status"], "error": rec["error"], "asset": rec.get("asset"),
           "route": {k: (rec.get("plan") or {}).get(k) for k in ("route", "chosen", "fallback_used", "explanation")},
           "stages": [f"{s['stage']}:{s['state']}" for s in rec["stages"] if s["attempt"] == len(rec["attempts"]) - 1]}
    if rec.get("asset"):
        md = library.get(rec["asset"]["id"], rec["asset"]["version"])
        out["files"] = {k: os.path.join(md["dir"], v["path"]) for k, v in md["files"].items()}
        out["thumbnail"] = os.path.join(md["dir"], md["previews"]["thumbnail"]) if md["previews"]["thumbnail"] else None
        out["geometry"] = md["geometry"]; out["animations"] = [a["name"] for a in md["animations"]]
    if rec.get("handoff"): out["handoff"] = rec["handoff"]["dir"]
    if rec["status"] == "blocked": out["alternatives"] = (rec.get("plan") or {}).get("alternatives")
    return out


def call(name, a):
    if name == "hardware_probe": return hardware.probe()
    if name == "route": return routing.route(a.get("brief", ""), a.get("images") or [], prefer=a.get("tool"))
    if name == "generate": return _gen(dict(a))
    if name == "process_mesh":
        spec = dict(a); spec["input_mesh"] = spec.pop("input"); spec.setdefault("brief", os.path.basename(spec["input_mesh"]))
        return _gen(spec)
    if name == "photogrammetry":
        spec = dict(a, tool="meshroom"); spec.setdefault("brief", "photogrammetry reconstruction"); return _gen(spec, default_wait=False)
    if name == "blockbench_build":
        out = a.get("out") or os.path.join(os.environ.get("GITCRAFT_ROOT", "."), f"{library.slugify(a.get('name', a['template']))}.bbmodel")
        return blockbench.build(a["template"], library.slugify(a.get("name", a["template"])), out)
    if name == "blockbench_inspect": return blockbench.inspect(a["path"])
    if name == "mixamo_guide": return {"steps": mixamo.GUIDE, "bones": ["mixamorig:" + b for b in mixamo.MIXAMO_CORE],
                                       "note": "MeshCraft never contacts mixamo.com; there is no official API."}
    if name == "mixamo_prepare_upload":
        md = library.get(a["asset"]); job = pipeline.Job({"tool": "mixamo_prep", "asset": md["id"]}); job.save()
        res = pipeline._blender(job, "mixamo_prep", os.path.join(job.work, "out"), 600, input=library.file_path(md, "glb"), slug=md["slug"])
        dest = a.get("out") or os.path.join(os.environ.get("GITCRAFT_ROOT", "."), os.path.basename(res["files"]["fbx"]))
        import shutil; shutil.copy2(res["files"]["fbx"], dest)
        return {"fbx": dest, "triangles": res["triangles"], "next": mixamo.GUIDE[1:]}
    if name == "mixamo_apply": return _gen(dict(a, tool="mixamo", brief=a.get("name") or "mixamo character"))
    if name == "compose_scene": return _gen(dict(a, tool="blender_scene", brief=(a.get("name") or "") + " scene"))
    if name == "library_search": return library.search(a.get("query", ""), a.get("kind"), a.get("tool"), a.get("status"))
    if name == "library_get": return library.get(a["asset"], a.get("version"))
    if name == "library_export": return library.export(a["asset"], a["dest"], a.get("version"), a.get("formats"))
    if name == "jobs_list":
        return [{"id": j["id"], "status": j["status"], "brief": (j.get("spec") or {}).get("brief"), "tool": (j.get("plan") or {}).get("chosen"),
                 "asset": j.get("asset"), "error": j.get("error"), "updated": j.get("updated")} for j in pipeline.jobs(a.get("limit", 20))]
    if name == "job_get": return pipeline.get_job(a["job"])
    if name == "job_retry":
        if a.get("wait", True): return _summ(pipeline.retry(a["job"]))
        return _bg(None, a["job"])
    raise KeyError(f"unknown tool {name}")


def main():
    out = sys.stdout
    lock = threading.Lock()

    def send(m):
        with lock: out.write(json.dumps(m, default=str) + "\n"); out.flush()
    for line in sys.stdin:
        try: msg = json.loads(line)
        except ValueError: continue
        mid, method, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None: continue  # notifications
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "meshcraft", "version": VERSION},
                  "instructions": "GITCRAFT 3D Department. Start with hardware_probe or route; generate runs the whole pipeline; library_export hands assets to other tools."}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s) in TOOLS.items()]}})
        elif method == "tools/call":
            name, args = p.get("name"), p.get("arguments") or {}

            def work(mid=mid, name=name, args=args):
                try:
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
