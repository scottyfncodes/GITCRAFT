#!/usr/bin/env python3
"""MCP stdio guard: sits between Claude Code and one GITCRAFT tool server.

    guard.py --tool NAME --root DIR [--root DIR]... [--deny TOOL]... -- SERVER ARGS...

Every JSON-RPC message passes straight through, except `tools/call` requests:
  * path-like arguments (keys such as path/paths/dir/out/output/file, or any
    absolute string) are resolved and refused when they fall outside the roots,
    with a readable MCP error instead of a raw EACCES from deep in a tool;
  * tools named with --deny are refused (e.g. script runners);
  * each call is appended to ~/.gitcraft/logs/audit.jsonl with its duration,
    outcome and the size + SHA-256 of every file it referenced that exists
    afterwards (`files`), plus every file inside the roots that the tool
    names only in its result (`outputs`, e.g. renders written to an out_dir),
    so tool-to-tool handoffs can be traced and reproduced.

The real boundary is the Landlock sandbox (scripts/sandbox.py) the server runs
in; this layer adds clear errors, a deny list and the audit trail.
"""
import hashlib, json, os, re, subprocess, sys, threading, time
FILE_LIKE = re.compile(r"\.[A-Za-z0-9]{2,12}$")
ABS_PATH = re.compile(r"(/[^\s'\"`,;:()<>\[\]{}]+\.[A-Za-z0-9]{2,12})")

PATH_KEYS = {"path", "paths", "file", "files", "dir", "out", "out_dir", "output", "outputs", "input", "inputs",
             "src", "dst", "dest", "destination", "target", "filepath", "file_path", "project", "image", "images"}


def parse(argv):
    o = {"tool": "?", "roots": [], "deny": set(), "cmd": []}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--": o["cmd"] = argv[i + 1:]; break
        if a == "--tool": o["tool"] = argv[i + 1]; i += 2; continue
        if a == "--root": o["roots"].append(os.path.realpath(argv[i + 1])); i += 2; continue
        if a == "--deny": o["deny"].add(argv[i + 1]); i += 2; continue
        i += 1
    return o


def candidate_paths(obj, key=None):
    """Yield strings that are file paths by key name or by being absolute."""
    if isinstance(obj, dict):
        for k, v in obj.items(): yield from candidate_paths(v, k)
    elif isinstance(obj, list):
        for v in obj: yield from candidate_paths(v, key)
    elif isinstance(obj, str):
        k = (key or "").lower()
        # absolute paths always count; relative ones only under a path-ish key and with a file extension
        # (EffectCraft's `path` key also carries property paths such as "transform/scale")
        if obj.startswith("/") or obj.startswith("~/") or (k in PATH_KEYS and FILE_LIKE.search(obj.split("[")[0])):
            if "\n" not in obj and len(obj) < 4096 and not obj.startswith(("http://", "https://", "data:")):
                yield obj


def inside(path, roots):
    p = os.path.realpath(os.path.expanduser(path.split("[")[0] if "[#" in path else path))
    return any(p == r or p.startswith(r + os.sep) for r in roots), p


def digest(p):
    try:
        if os.path.isfile(p) and os.path.getsize(p) <= 512 * 2**20:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
            return {"path": p, "bytes": os.path.getsize(p), "sha256": h.hexdigest()}
        if os.path.isdir(p): return {"path": p, "dir": True}
    except OSError:
        pass
    return None


MAX_OUTPUTS = 200


def result_paths(res, roots, seen):
    """Absolute paths inside the roots that a tool names in its result text (JSON or plain)."""
    found = []
    for c in res.get("content", []) if isinstance(res, dict) else []:
        txt = c.get("text", "") if isinstance(c, dict) else ""
        if not txt or len(txt) > 4 * 2**20: continue
        try: cands = list(candidate_paths(json.loads(txt)))
        except Exception: cands = ABS_PATH.findall(txt)
        for p in cands:
            if not p.startswith("/"): continue
            ok, real = inside(p, roots)
            if ok and real not in seen:
                seen.add(real); found.append(real)
                if len(found) >= MAX_OUTPUTS: return found
    return found


def main():
    o = parse(sys.argv[1:])
    if not o["cmd"]:
        print("guard: no server command", file=sys.stderr); return 2
    logdir = os.path.expanduser(os.environ.get("GITCRAFT_LOG", "~/.gitcraft/logs"))
    os.makedirs(logdir, exist_ok=True)
    audit = open(os.path.join(logdir, "audit.jsonl"), "a", buffering=1)
    proc = subprocess.Popen(o["cmd"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
    out_lock = threading.Lock()
    pending = {}  # id -> (tool, args, t0, paths)

    def emit(obj_or_bytes):
        data = obj_or_bytes if isinstance(obj_or_bytes, bytes) else (json.dumps(obj_or_bytes) + "\n").encode()
        with out_lock:
            sys.stdout.buffer.write(data); sys.stdout.buffer.flush()

    def from_server():
        for line in proc.stdout:
            try:
                msg = json.loads(line)
                if isinstance(msg, dict) and msg.get("id") in pending:
                    tool, args, t0, paths = pending.pop(msg["id"])
                    res = msg.get("result") or {}
                    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "server": o["tool"], "tool": tool,
                           "ms": int((time.time() - t0) * 1000),
                           "ok": "error" not in msg and not res.get("isError", False),
                           "args": json.dumps(args)[:600], "files": [d for d in (digest(p) for p in paths) if d]}
                    outs = result_paths(res, o["roots"], set(paths)) if o["roots"] else []
                    if outs: rec["outputs"] = [d for d in (digest(p) for p in outs) if d and not d.get("dir")]
                    if not rec["ok"]:
                        txt = " ".join(c.get("text", "") for c in res.get("content", []) if isinstance(c, dict))
                        rec["error"] = (txt or json.dumps(msg.get("error")))[:600]
                    audit.write(json.dumps(rec) + "\n")
            except Exception:
                pass
            emit(line)
        rc = proc.wait()
        print(f"guard[diag45]: server stdout EOF; server exit status {rc}", file=sys.stderr, flush=True)
        os._exit(rc or 0)

    threading.Thread(target=from_server, daemon=True).start()
    for line in sys.stdin.buffer:
        try:
            msg = json.loads(line)
        except Exception:
            proc.stdin.write(line); proc.stdin.flush(); continue
        if isinstance(msg, dict) and msg.get("method") == "tools/call":
            p = msg.get("params") or {}
            name, args = p.get("name", ""), p.get("arguments") or {}
            inner = args.get("id") or args.get("command") or args.get("name") if name in ("command_run", "run_command", "execute", "execute_command", "tool_call") else None
            refusal = None
            if name in o["deny"] or (inner and inner in o["deny"]):
                refusal = f"GITCRAFT policy: `{inner or name}` is disabled for {o['tool']}."
            paths = []
            if not refusal and o["roots"]:
                for c in candidate_paths(args):
                    ok, real = inside(c, o["roots"])
                    if not ok:
                        refusal = (f"GITCRAFT policy: {o['tool']} may only read and write inside {', '.join(o['roots'])}; "
                                   f"`{c}` resolves to `{real}`. Copy the file into the workspace or set GITCRAFT_ROOT.")
                        break
                    paths.append(real)
            if refusal:
                audit.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "server": o["tool"], "tool": inner or name,
                                        "ok": False, "refused": True, "error": refusal, "args": json.dumps(args)[:600]}) + "\n")
                if "id" in msg:
                    emit({"jsonrpc": "2.0", "id": msg["id"], "result": {"isError": True, "content": [{"type": "text", "text": refusal}]}})
                continue
            if "id" in msg: pending[msg["id"]] = (inner or name, args, time.time(), paths)
        proc.stdin.write(line); proc.stdin.flush()
    print("guard[diag45]: client stdin EOF; closing server stdin", file=sys.stderr, flush=True)
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    sys.exit(main())
