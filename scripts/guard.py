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
in; this layer adds clear errors, a deny list and the audit trail. It also
defends what Landlock cannot fence inside a writable root, the repository
control files that run outside the sandbox later (git hooks and config, Claude
Code settings and the scripts its hooks run, ...; gitcraft3d/policy.py):
  * a call whose path arguments name one is refused;
  * a tripwire snapshots them when the server goes from idle to busy and
    compares when it is idle again (long calls count as busy until their
    call_result is collected): any change is undone (the new content is moved
    to <file>.gitcraft-quarantine-<time>, the original put back), the call's
    answer becomes an error that says so, and the audit log records it.
"""
import hashlib, json, os, re, subprocess, sys, threading, time
import importlib.util
# gitcraft3d/policy.py, loaded by its path: the control-file policy shared with mcp.sh and MeshCraft
_spec = importlib.util.spec_from_file_location("gitcraft_policy", os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "gitcraft3d", "policy.py"))
policy = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(policy)
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


_DIGESTS = {}   # (path, size, mtime_ns) → sha256: an unchanged input is not re-hashed on every call


def digest(p):
    try:
        if os.path.isfile(p) and os.path.getsize(p) <= 512 * 2**20:
            st = os.stat(p); key = (p, st.st_size, st.st_mtime_ns)
            if key not in _DIGESTS:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
                if len(_DIGESTS) > 5000: _DIGESTS.clear()
                _DIGESTS[key] = h.hexdigest()
            return {"path": p, "bytes": st.st_size, "sha256": _DIGESTS[key]}
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


def check_call(msg, o):
    """(refusal or None, inner command, tool name, arguments, resolved paths) for one tools/call."""
    p = msg.get("params")
    if p is None: p = {}
    if not isinstance(p, dict): raise ValueError("params must be an object")
    name, args = p.get("name", ""), p.get("arguments")
    if args is None: args = {}
    if not isinstance(name, str): raise ValueError("params.name must be a string")
    if not isinstance(args, dict): raise ValueError("params.arguments must be an object")
    if "id" in msg and (not isinstance(msg["id"], (str, int)) or isinstance(msg["id"], bool)): raise ValueError("id must be a string or a number")
    inner = args.get("id") or args.get("command") or args.get("name") if name in ("command_run", "run_command", "execute", "execute_command", "tool_call") else None
    if inner is not None and not isinstance(inner, str): raise ValueError("the command id must be a string")
    if name in o["deny"] or (inner and inner in o["deny"]):
        return f"GITCRAFT policy: `{inner or name}` is disabled for {o['tool']}.", inner, name, args, []
    paths = []
    if o["roots"]:
        for c in candidate_paths(args):
            ok, real = inside(c, o["roots"])
            if not ok:
                return (f"GITCRAFT policy: {o['tool']} may only read and write inside {', '.join(o['roots'])}; "
                        f"`{c}` resolves to `{real}`. Copy the file into the workspace or set GITCRAFT_ROOT."), inner, name, args, []
            why = policy.protected(real, o["roots"])
            if why:
                return (f"GITCRAFT policy: {o['tool']} may not touch `{c}`: {why}. Tools never read or write repository "
                        f"control files; use a normal project folder."), inner, name, args, []
            paths.append(real)
    return None, inner, name, args, paths


class Tripwire:
    """Repository control files under the roots must be the same after a tool has run as before (see the docstring)."""
    LONG_TTL = 3600   # gitcraft3d/calls.py keeps a long call's result for an hour

    def __init__(self, roots, audit, tool):
        self.roots, self.audit, self.tool = roots, audit, tool
        self.lock = threading.Lock()
        self.busy, self.long, self.base = {}, {}, None   # request id -> call_result's call_id or None; call_id -> started

    def begin(self, mid, name, args):
        with self.lock:
            self._expire()
            if not self.busy and not self.long:
                self.base = policy.snapshot(self.roots)
            self.busy[mid] = args.get("call_id") if name == "call_result" and isinstance(args.get("call_id"), str) else None

    def _expire(self):
        now = time.time()
        for k in [k for k, t in self.long.items() if now - t > self.LONG_TTL]: self.long.pop(k, None)

    @staticmethod
    def _running(msg):
        """The call_id when this answer says the call is still running (gitcraft3d/calls.py), else None."""
        for c in ((msg.get("result") or {}).get("content") or []) if isinstance(msg.get("result"), dict) else []:
            try: d = json.loads(c.get("text", "")) if isinstance(c, dict) else None
            except Exception: d = None
            if isinstance(d, dict) and d.get("status") == "running" and isinstance(d.get("call_id"), str): return d["call_id"]
        return None

    def response(self, line):
        try: msg = json.loads(line)
        except Exception: return line
        if not isinstance(msg, dict) or "id" not in msg: return line
        with self.lock:
            if msg["id"] not in self.busy: return line
            asked = self.busy.pop(msg["id"])
            running = self._running(msg)
            if running: self.long.setdefault(running, time.time())
            elif asked: self.long.pop(asked, None)
            if self.busy or self.long or self.base is None: return line
            changes = self._check()
        if not changes: return line
        note = ("GITCRAFT policy: while this tool ran, repository control files changed, which no GITCRAFT tool may do "
                "(they run outside the sandbox: git hooks, Claude Code settings and hooks, ...). Each change was undone: "
                + "; ".join(f"{c['path']} {c['change']}" + (f" (moved aside to {c['quarantine']})" if c.get("quarantine") else "")
                            + ("" if c.get("restored") else " (NOT restored: check it by hand)") for c in changes)
                + ". Treat the tool's input (a script, a project, a document) as untrusted.")
        res = msg.get("result") if isinstance(msg.get("result"), dict) else {}
        msg["result"] = {"isError": True, "content": [{"type": "text", "text": note}] + list(res.get("content") or [])}
        msg.pop("error", None)
        return (json.dumps(msg) + "\n").encode()

    def _check(self):
        base, self.base = self.base, None
        changes = policy.compare_and_restore(base, self.roots, time.strftime("%Y%m%dT%H%M%S"))
        if changes:
            self.audit.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "server": self.tool, "tool": "tripwire", "ok": False,
                                         "integrity": changes}) + "\n")
            print(f"guard: {self.tool}: control files changed during a call and were restored: {[c['path'] for c in changes]}", file=sys.stderr)
        return changes

    def final(self):
        """The server ended: anything still running cannot be collected, so check now."""
        with self.lock:
            if self.base is not None: self._check()


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
    trip = Tripwire(o["roots"], audit, o["tool"])

    def emit(obj_or_bytes):
        data = obj_or_bytes if isinstance(obj_or_bytes, bytes) else (json.dumps(obj_or_bytes) + "\n").encode()
        with out_lock:
            sys.stdout.buffer.write(data); sys.stdout.buffer.flush()

    def from_server():
        for line in proc.stdout:
            try:
                line = trip.response(line)   # undo any control-file change made while the server was busy (may rewrite the answer)
            except Exception as e:
                print(f"guard: tripwire error: {type(e).__name__}: {e}", file=sys.stderr)
            emit(line)   # the client gets its answer first; the audit record (which hashes files) follows
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
        try: trip.final()
        except Exception: pass
        os._exit(proc.wait() or 0)

    reader = threading.Thread(target=from_server, daemon=True); reader.start()
    for line in sys.stdin.buffer:
        try:
            msg = json.loads(line)
        except Exception:
            proc.stdin.write(line); proc.stdin.flush(); continue
        if isinstance(msg, dict) and msg.get("method") == "tools/call":
            try:
                refusal, inner, name, args, paths = check_call(msg, o)
            except Exception as e:   # a malformed request is answered, never allowed to stop the guard (and the server with it)
                refusal, inner, name, args, paths = f"GITCRAFT policy: malformed tools/call refused ({type(e).__name__}: {e})", None, "?", {}, []
            if refusal:
                audit.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "server": o["tool"], "tool": inner or name,
                                        "ok": False, "refused": True, "error": refusal, "args": json.dumps(args, default=str)[:600]}) + "\n")
                if "id" in msg:
                    rid = msg["id"] if isinstance(msg["id"], (str, int)) and not isinstance(msg["id"], bool) else None
                    emit({"jsonrpc": "2.0", "id": rid, "result": {"isError": True, "content": [{"type": "text", "text": refusal}]}})
                continue
            if "id" in msg:
                pending[msg["id"]] = (inner or name, args, time.time(), paths)
                try: trip.begin(msg["id"], name, args)
                except Exception as e: print(f"guard: tripwire error: {type(e).__name__}: {e}", file=sys.stderr)
        proc.stdin.write(line); proc.stdin.flush()
    proc.stdin.close()
    proc.wait()
    reader.join(timeout=5)   # let the last responses reach the client before exiting


if __name__ == "__main__":
    sys.exit(main())
