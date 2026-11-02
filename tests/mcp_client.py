"""Minimal stdio MCP client used by the GITCRAFT tests and pipelines."""
import json, os, queue, subprocess, threading, time

class Client:
    def __init__(self, cmd, env=None, log=None):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=open(log or os.devnull, "ab"), env=env, bufsize=0)
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
        """Returns (ok, parsed_or_text)."""
        r = self.req("tools/call", {"name": tool, "arguments": args or {}}, timeout)
        txt = "\n".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
        try: val = json.loads(txt)
        except Exception: val = txt
        return (not r.get("isError")), val

    def tools(self): return self.req("tools/list")["tools"]

    def close(self):
        try: self.p.stdin.close(); self.p.wait(10)
        except Exception: self.p.kill()
