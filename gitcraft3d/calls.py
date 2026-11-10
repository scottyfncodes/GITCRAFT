"""Long tool calls that never hit the client's timeout (standard library only).

An MCP client gives up on a tools/call after its timeout: Claude Code uses MCP_TOOL_TIMEOUT, 60 s in cloud sessions,
while a PIXELCRAFT verify, a PLAYCRAFT pass or a 3D build takes minutes. The call was cut off, but the work went on
with no one to read its result.

Every GITCRAFT server (studiocraft, forgecraft, meshcraft) answers a tools/call within an inline budget. A call that
finishes in time is answered as before. One that does not is answered with

    {"status": "running", "call_id": "...", "tool": "...", "elapsed_s": 45, "next": "call call_result with this call_id"}

and keeps running in the server. `call_result {call_id}` waits (up to the same budget) and returns the tool's own
result when it is done, or the same "running" answer while it is not. `call_result` with no call_id lists the calls.

Budget: GITCRAFT_MCP_INLINE_SECONDS, else the client's MCP_TOOL_TIMEOUT minus 15 s, else 45 s; never under 5 s.
Results stay in the server's memory for an hour (the last 100). A server that restarts loses the calls it was
running (the 3D Department's own jobs persist: forgecraft job_get / meshcraft jobs_list)."""
import json, os, threading, time, uuid

KEEP_S, KEEP_N = 3600, 100
TOOL = {"name": "call_result",
        "description": ("The result of a long tool call. A call that takes longer than this client allows answers at once with "
                        "{status: running, call_id} and keeps running here; pass that call_id to get its result (this waits up to "
                        "the client's limit and answers 'running' again if it is still going). Without call_id: the calls this "
                        "server is running or finished in the last hour."),
        "inputSchema": {"type": "object", "properties": {"call_id": {"type": "string"},
                                                          "wait_seconds": {"type": "number", "description": "how long to wait for it (capped at the client's limit)"}}}}


def budget():
    v = os.environ.get("GITCRAFT_MCP_INLINE_SECONDS")
    if v:
        try: return max(0.05, float(v))
        except ValueError: pass
    t = os.environ.get("MCP_TOOL_TIMEOUT")
    if t:
        try: return max(5.0, int(t) / 1000 - 15)
        except ValueError: pass
    return 45.0


class Calls:
    """send(msg) writes one JSON-RPC message; reply(result) turns a tool's return value (or exception) into an MCP
    tools/call result. Thread-safe."""

    def __init__(self, send, reply):
        self.send, self.reply, self.lock, self.items = send, reply, threading.Lock(), {}

    # ---------------------------------------------------------------- a call
    def begin(self, mid, name):
        """Register a call about to run; after the budget a still-running call is answered with its call_id."""
        rec = {"id": "c-" + uuid.uuid4().hex[:12], "mid": mid, "tool": name, "started": time.time(), "done": threading.Event(),
               "answered": False, "result": None, "finished": None}
        with self.lock:
            self._prune(); self.items[rec["id"]] = rec
        t = threading.Timer(budget(), self._detach, args=(rec,)); t.daemon = True; t.start(); rec["timer"] = t
        return rec

    def finish(self, rec, value=None, error=None):
        """The tool returned (or raised): answer its request, or keep the result for call_result."""
        result = self.reply(value, error)
        with self.lock:
            rec["result"], rec["finished"] = result, time.time()
            answered = rec["answered"]
            if not answered: rec["answered"] = True   # answered here: the timer will not detach it
        rec["timer"].cancel(); rec["done"].set()
        if not answered:
            with self.lock: self.items.pop(rec["id"], None)   # answered inline: nothing to collect
            self.send({"jsonrpc": "2.0", "id": rec["mid"], "result": result})

    def run(self, mid, name, fn):
        """Run fn() in a thread, answering inline or detached (studiocraft, forgecraft)."""
        rec = self.begin(mid, name)
        def work():
            try: v = fn()
            except Exception as e:
                import traceback, sys
                traceback.print_exc(file=sys.stderr); self.finish(rec, error=e)
            else: self.finish(rec, v)
        threading.Thread(target=work, daemon=True).start()

    def _detach(self, rec):
        with self.lock:
            if rec["answered"]: return
            rec["answered"] = True
        self.send({"jsonrpc": "2.0", "id": rec["mid"], "result": {"isError": False, "content": [{"type": "text", "text": json.dumps(self._running(rec), indent=1)}]}})

    def _running(self, rec):
        return {"status": "running", "call_id": rec["id"], "tool": rec["tool"], "elapsed_s": round(time.time() - rec["started"]),
                "next": f"still working: call call_result with {{\"call_id\": \"{rec['id']}\"}} for the result (it waits up to {round(budget())} s per call)",
                "why": "this call takes longer than the client waits for one tool call; it keeps running in the server"}

    # ---------------------------------------------------------------- call_result
    def result(self, args):
        args = args or {}
        cid = args.get("call_id")
        if not cid:
            with self.lock:
                self._prune()
                rows = [{"call_id": r["id"], "tool": r["tool"], "status": "done" if r["done"].is_set() else "running",
                         "elapsed_s": round((r["finished"] or time.time()) - r["started"])} for r in self.items.values()]
            return {"content": [{"type": "text", "text": json.dumps({"calls": rows}, indent=1)}]}
        with self.lock: rec = self.items.get(cid)
        if rec is None:
            return {"isError": True, "content": [{"type": "text", "text": f"no call {cid} in this server (finished more than an hour ago, "
                    "answered inline, or the server restarted); call_result with no call_id lists the calls it has"}]}
        try: w = float(args.get("wait_seconds", budget()))
        except (TypeError, ValueError): w = budget()
        if not rec["done"].wait(max(0.0, min(w, budget()))):
            return {"isError": False, "content": [{"type": "text", "text": json.dumps(self._running(rec), indent=1)}]}
        return rec["result"]

    def _prune(self):
        now = time.time()
        for k, r in list(self.items.items()):
            if r["finished"] and now - r["finished"] > KEEP_S: self.items.pop(k, None)
        done = sorted((r for r in self.items.values() if r["finished"]), key=lambda r: r["finished"])
        for r in done[:max(0, len(done) - KEEP_N)]: self.items.pop(r["id"], None)


def is_running(value):
    """True for the 'still running' answer (clients that follow it: tests/mcp_client.py, ui/server.py)."""
    return isinstance(value, dict) and value.get("status") == "running" and bool(value.get("call_id")) and "call_result" in str(value.get("next", ""))
