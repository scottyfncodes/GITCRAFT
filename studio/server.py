#!/usr/bin/env python3
"""StudioCraft: the GITCRAFT Studio departments as one MCP server (stdio, JSON-RPC 2.0).

Started by scripts/mcp.sh behind the guard and the Landlock sandbox like every GITCRAFT tool.
Tools are generated from the department manifests: one `<department>_<action>` tool per action
(its input schema is the manifest's request schema), plus discovery and routing:

  studio_status        every department, its actions and whether each can run on this machine (why not)
  department_describe  one department's manifest: actions, request/output formats, dependencies, licences
  route                which department/action fits a brief (3D modelling goes to ForgeCraft)
  run                  run any department action by name (what ForgeCraft's department_run calls)

ForgeCraft exposes the same through `departments`, `department_route` and `department_run`."""
import json, os, platform, sys, threading, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from core import VERSION, contract, routing, roots

COMMON = {"out_dir": {"type": "string", "description": "output folder inside a GITCRAFT root (default <root>/gitcraft-out/<department>/<name>)"},
          "name": {"type": "string", "description": "file stem for the outputs"}, "seed": {"type": "integer", "description": "deterministic seed"},
          "license": {"type": "string", "description": "override the output licence recorded in the catalogue (SPDX id)"},
          "tags": {"type": "array", "items": {"type": "string"}}}


def _hardware():
    import shutil
    mem = None
    try:
        mem = round(int(next(l for l in open("/proc/meminfo") if l.startswith("MemTotal")).split()[1]) / 1048576, 1)
    except Exception: pass
    return {"cpu_count": os.cpu_count(), "ram_gb": mem, "gpu": bool(shutil.which("nvidia-smi")), "platform": platform.platform()}


def tools():
    out = [
        ("studio_status", "Every GITCRAFT Studio department (audiocraft, animcraft, worldcraft, fxcraft, materialcraft, levelcraft, cinematiccraft, testcraft, assetcraft), its actions and whether each can run on this machine, with the reason when not.", {"type": "object", "properties": {}}),
        ("department_describe", "One department's machine-readable manifest: actions with request schemas and outputs, dependencies with live status, acquired tools and licences, examples, limits.",
         {"type": "object", "required": ["department"], "properties": {"department": {"type": "string", "enum": contract.departments()}}}),
        ("route", "Which department and action fit a free-text brief, with proposed parameters. 3D modelling is pointed at ForgeCraft. Advice only.",
         {"type": "object", "required": ["brief"], "properties": {"brief": {"type": "string"}}}),
        ("run", "Run any department action: {department, action, params}. Same as the <department>_<action> tools.",
         {"type": "object", "required": ["department", "action"], "properties": {"department": {"type": "string", "enum": contract.departments()}, "action": {"type": "string"}, "params": {"type": "object"}}}),
    ]
    for d in contract.departments():
        m = contract.manifest(d)
        for a, spec in m["actions"].items():
            schema = json.loads(json.dumps(spec.get("params", {"type": "object", "properties": {}})))
            schema.setdefault("properties", {}).update({k: v for k, v in COMMON.items() if k not in schema["properties"]})
            out.append((f"{d}_{a}", f"[{d}] {spec['summary']}", schema))
    return out


def call(name, args):
    args = dict(args or {})
    if name == "studio_status":
        return {"studio": VERSION, "roots": roots(), "hardware": _hardware(), "departments": contract.overview()}
    if name == "department_describe": return contract.describe(args["department"])
    if name == "route": return routing.route(args.get("brief", ""))
    if name == "run": return contract.run(args["department"], args["action"], args.get("params") or {})
    for d in contract.departments():
        if name.startswith(d + "_") and name[len(d) + 1:] in contract.manifest(d)["actions"]:
            return contract.run(d, name[len(d) + 1:], args)
    raise KeyError(f"unknown tool {name}")


def main():
    out = sys.stdout; lock = threading.Lock()
    real_stdout = sys.stdout; sys.stdout = sys.stderr   # nothing but JSON-RPC on the real stdout

    def send(m):
        with lock: real_stdout.write(json.dumps(m, default=str) + "\n"); real_stdout.flush()
    for line in sys.stdin:
        try: msg = json.loads(line)
        except ValueError: continue
        mid, method, p = msg.get("id"), msg.get("method"), msg.get("params") or {}
        if mid is None: continue
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": p.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                  "serverInfo": {"name": "studiocraft", "version": VERSION},
                  "instructions": "GITCRAFT Studio departments (audio, animation, worlds, FX, materials, levels, cinematics, QA, assets). Start with studio_status or route; each <department>_<action> tool validates its request, reports `blocked` with the reason when a dependency is missing, validates and hashes every output, writes a .studio.json provenance record and registers outputs in the AssetCraft catalogue."}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": [{"name": n, "description": d, "inputSchema": s} for n, d, s in tools()]}})
        elif method == "tools/call":
            def work(mid=mid, name=p.get("name"), a=p.get("arguments") or {}):
                try:
                    r = call(name, a)
                    err = isinstance(r, dict) and r.get("status") in ("failed", "blocked")
                    send({"jsonrpc": "2.0", "id": mid, "result": {"isError": err, "content": [{"type": "text", "text": json.dumps(r, indent=1, default=str)}]}})
                except Exception as e:
                    traceback.print_exc(file=sys.stderr)
                    hint = getattr(e, "hint", None)
                    send({"jsonrpc": "2.0", "id": mid, "result": {"isError": True, "content": [{"type": "text", "text": f"{type(e).__name__}: {e}" + (f"\nhint: {hint}" if hint else "")}]}})
            threading.Thread(target=work, daemon=True).start()
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        else:
            send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"unknown method {method}"}})


if __name__ == "__main__":
    main()
