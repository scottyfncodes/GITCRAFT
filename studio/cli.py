#!/usr/bin/env python3
"""GITCRAFT Studio command line (also how ForgeCraft calls the departments).

  studio/cli.py list                                 departments and which actions can run here
  studio/cli.py describe <department>                the manifest + dependency status
  studio/cli.py route "<brief>"                      which department/action fits a request
  studio/cli.py run <department> <action> '<json>'   run an action (or @request.json)
  studio/cli.py --call <tool> '<json>'               one MCP tool, JSON result on stdout (ForgeCraft)

Run it with the studio venv (~/.gitcraft/studio/venv/bin/python) or scripts/studio.sh, which also
applies the GITCRAFT sandbox."""
import contextlib, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)


def _arg(s):
    if s is None: return {}
    if s.startswith("@"): return json.load(open(s[1:]))
    return json.loads(s)


def main(argv):
    import server
    if not argv or argv[0] in ("-h", "--help"): print(__doc__); return 0
    cmd = argv[0]
    if cmd == "--call":
        with contextlib.redirect_stdout(sys.stderr): r = server.call(argv[1], _arg(argv[2] if len(argv) > 2 else None))
        print(json.dumps(r, default=str)); return 0
    with contextlib.redirect_stdout(sys.stderr):
        if cmd == "list": r = server.call("studio_status", {})
        elif cmd == "describe": r = server.call("department_describe", {"department": argv[1]})
        elif cmd == "route": r = server.call("route", {"brief": " ".join(argv[1:])})
        elif cmd == "run": r = server.call("run", {"department": argv[1], "action": argv[2], "params": _arg(argv[3] if len(argv) > 3 else None)})
        else: print(__doc__, file=sys.stderr); return 2
    print(json.dumps(r, indent=1, default=str))
    return 0 if not (isinstance(r, dict) and r.get("status") in ("failed", "blocked")) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
