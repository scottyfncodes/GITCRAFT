"""Minimal stdio MCP client used by the GITCRAFT tests and pipelines."""
import json, os, queue, subprocess, threading, time


def running(v):
    """The server's 'still running, collect it with call_result' answer (gitcraft3d/calls.py)."""
    return isinstance(v, dict) and v.get("status") == "running" and bool(v.get("call_id")) and "call_result" in str(v.get("next", ""))

class Client:
    def __init__(self, cmd, env=None, log=None, cwd=None):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=open(log or os.devnull, "ab"), env=env, bufsize=0, cwd=cwd)
        self.q, self.id = queue.Queue(), 0
        threading.Thread(target=self._read, daemon=True).start()
        self.info = self.req("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                            "clientInfo": {"name": "gitcraft-tests", "version": "1"}})
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode())

    def _read(self):
        for line in self.p.stdout:
            try: self.q.put(json.loads(line))
            except Exception: pass
        self.q.put(None)

    def req(self, method, params=None, timeout=300):
        self.id += 1; i = self.id
        self.p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": i, "method": method, "params": params or {}}) + "\n").encode())
        end = time.time() + timeout
        while True:
            m = self.q.get(timeout=max(1, end - time.time()))
            if m is None: raise RuntimeError("server exited")
            if m.get("id") == i:
                if "error" in m: raise RuntimeError(json.dumps(m["error"]))
                return m["result"]

    def call(self, tool, args=None, timeout=300):
        """Returns (ok, parsed_or_text). A call longer than the server's inline budget is answered {status: running,
        call_id} (gitcraft3d/calls.py): this follows it with call_result until the result arrives or timeout passes."""
        end = time.time() + timeout
        r = self.req("tools/call", {"name": tool, "arguments": args or {}}, timeout)
        ok, val = self._parse(r)
        self.detached = None
        while running(val) and tool != "call_result":
            self.detached = val["call_id"]
            if time.time() > end: return False, val
            r = self.req("tools/call", {"name": "call_result", "arguments": {"call_id": val["call_id"]}}, max(30, end - time.time()))
            ok, val = self._parse(r)
        return ok, val

    @staticmethod
    def _parse(r):
        txt = "\n".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        try: val = json.loads(txt)
        except Exception: val = txt
        return (not r.get("isError")), val

    def tools(self): return self.req("tools/list")["tools"]

    def close(self):
        try: self.p.stdin.close(); self.p.wait(10)
        except Exception: self.p.kill()
