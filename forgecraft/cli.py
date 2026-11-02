#!/usr/bin/env python3
"""Command line for the 3D Department (same calls as the MCP tools).

  forgecraft/cli.py probe
  forgecraft/cli.py route "stylized low-poly boat" [image ...]
  forgecraft/cli.py generate "stylized low-poly boat with a red hull"      # or a JSON spec: '{"brief": ..., "kind": ...}'
  forgecraft/cli.py compose '{"name": "...", "items": [...]}'
  forgecraft/cli.py process path/to/mesh.glb [name]
  forgecraft/cli.py jobs | job <id> | retry <id>
  forgecraft/cli.py search [query] | get <asset> | export <asset> <dest_dir>
  forgecraft/cli.py snapshot <dir>                                            # copy the library (no scratch) for publishing
  forgecraft/cli.py serve [--port 8765]                                      # the UI, live
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)


def main(a):
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0
    cmd, rest = a[0], a[1:]
    import server
    spec = lambda s: json.loads(s) if s.strip().startswith("{") else {"brief": s}
    if cmd == "probe": r = server.call("hardware_probe", {})
    elif cmd == "route": r = server.call("route", {"brief": rest[0], "images": rest[1:]})
    elif cmd == "generate": r = server.call("generate", spec(" ".join(rest)))
    elif cmd == "compose": r = server.call("compose_scene", json.loads(rest[0]))
    elif cmd == "process": r = server.call("process_mesh", {"input": rest[0], "name": rest[1] if len(rest) > 1 else None})
    elif cmd == "jobs": r = server.call("jobs_list", {})
    elif cmd == "job": r = server.call("job_get", {"job": rest[0]})
    elif cmd == "retry": r = server.call("job_retry", {"job": rest[0]})
    elif cmd == "search": r = server.call("library_search", {"query": " ".join(rest)})
    elif cmd == "get": r = server.call("library_get", {"asset": rest[0]})
    elif cmd == "export": r = server.call("library_export", {"asset": rest[0], "dest": rest[1]})
    elif cmd == "snapshot":
        import hardware, library; r = library.snapshot(rest[0], hardware.probe())
    elif cmd == "serve":
        os.execv(sys.executable, [sys.executable, os.path.join(HERE, "ui_server.py"), *rest])
    else: print(__doc__); return 2
    print(json.dumps(r, indent=1, default=str))
    return 1 if isinstance(r, dict) and r.get("status") in ("failed", "blocked") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
