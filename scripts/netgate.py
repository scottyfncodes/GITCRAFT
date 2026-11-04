#!/usr/bin/env python3
"""netgate: per-host network allowances for sandboxed GITCRAFT tools.

The Landlock sandbox can deny all TCP but cannot filter by host. With GITCRAFT_ALLOW_HOSTS set, scripts/mcp.sh
starts this tiny HTTPS (CONNECT) proxy on a random 127.0.0.1 port, points the tool's HTTPS_PROXY at it, and
adds a Landlock rule that allows TCP connect to that one port and nothing else. The proxy lets a CONNECT through
only when its host matches the allowlist, tunnels it (through the environment's own HTTPS_PROXY when there is
one), and logs every decision to ~/.gitcraft/logs/net.jsonl. TLS stays end to end: the proxy never sees content.

    netgate.py --allow "huggingface.co,*.hf.co,cdn-lfs.huggingface.co" --tool forgecraft --parent PID --port-file F

Patterns: exact host, or *.domain (any subdomain, not the domain itself; list both when you want both).
Only port 443 is allowed. The proxy exits when PID (the tool's launcher) exits."""
import argparse, datetime, json, os, select, socket, sys, threading, time, urllib.parse


def matches(host, patterns):
    host = host.lower().rstrip(".")
    for p in patterns:
        p = p.lower().strip()
        if not p: continue
        if p.startswith("*.") and host.endswith(p[1:]) and host != p[2:]: return True
        if host == p: return True
    return False


def log(path, **rec):
    rec["time"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    try:
        with open(path, "a") as f: f.write(json.dumps(rec) + "\n")
    except OSError: pass


def pipe(a, b):
    socks = [a, b]
    try:
        while True:
            r, _, x = select.select(socks, [], socks, 300)
            if x or not r: return
            for s in r:
                data = s.recv(65536)
                if not data: return
                (b if s is a else a).sendall(data)
    except OSError:
        return
    finally:
        for s in socks:
            try: s.close()
            except OSError: pass


def upstream_connect(host, port):
    """Connect to host:port, through the environment's own HTTPS proxy when it has one."""
    up = os.environ.get("NETGATE_UPSTREAM") or ""
    if up:
        u = urllib.parse.urlparse(up if "://" in up else "http://" + up)
        s = socket.create_connection((u.hostname, u.port or 8080), timeout=30)
        s.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = s.recv(4096)
            if not chunk: raise OSError("upstream proxy closed the connection")
            resp += chunk
        if b" 200" not in resp.split(b"\r\n", 1)[0]:
            raise OSError("upstream proxy refused: " + resp.split(b"\r\n", 1)[0].decode(errors="replace"))
        return s
    return socket.create_connection((host, port), timeout=30)


def handle(conn, a, logfile):
    try:
        conn.settimeout(30)
        head = b""
        while b"\r\n\r\n" not in head and len(head) < 16384:
            chunk = conn.recv(4096)
            if not chunk: return conn.close()
            head += chunk
        line = head.split(b"\r\n", 1)[0].decode(errors="replace")
        parts = line.split()
        if len(parts) < 2 or parts[0].upper() != "CONNECT":
            log(logfile, tool=a.tool, decision="refused", request=line[:200], reason="only HTTPS CONNECT is supported")
            conn.sendall(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n"); return conn.close()
        host, _, port = parts[1].rpartition(":")
        port = int(port or 0); host = host.strip("[]")
        if port != 443 or not matches(host, a.allow):
            log(logfile, tool=a.tool, decision="refused", host=host, port=port, reason="not in GITCRAFT_ALLOW_HOSTS" if port == 443 else "only port 443")
            msg = f"GITCRAFT policy: {host}:{port} is not in GITCRAFT_ALLOW_HOSTS for {a.tool}".encode()
            conn.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nContent-Length: " + str(len(msg)).encode() + b"\r\n\r\n" + msg)
            return conn.close()
        try:
            up = upstream_connect(host, port)
        except OSError as e:
            log(logfile, tool=a.tool, decision="allowed-failed", host=host, port=port, reason=str(e)[:200])
            conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"); return conn.close()
        log(logfile, tool=a.tool, decision="allowed", host=host, port=port)
        conn.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        conn.settimeout(None); up.settimeout(None)
        pipe(conn, up)
    except Exception as e:
        try: conn.close()
        except OSError: pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow", required=True); ap.add_argument("--tool", default="?")
    ap.add_argument("--parent", type=int, default=0); ap.add_argument("--port-file", required=True)
    ap.add_argument("--log", default=os.path.join(os.environ.get("GITCRAFT_HOME") or os.path.expanduser("~/.gitcraft"), "logs", "net.jsonl"))
    a = ap.parse_args(); a.allow = [p for p in a.allow.replace(" ", ",").split(",") if p]
    os.makedirs(os.path.dirname(a.log), exist_ok=True)
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0)); srv.listen(64)
    tmp = a.port_file + ".tmp"; open(tmp, "w").write(str(srv.getsockname()[1])); os.replace(tmp, a.port_file)
    log(a.log, tool=a.tool, decision="started", allow=a.allow, port=srv.getsockname()[1])

    def watch_parent():
        while a.parent:
            try: os.kill(a.parent, 0)
            except ProcessLookupError: os._exit(0)
            except PermissionError: pass
            time.sleep(1)
    threading.Thread(target=watch_parent, daemon=True).start()
    while True:
        c, _ = srv.accept()
        threading.Thread(target=handle, args=(c, a, a.log), daemon=True).start()


if __name__ == "__main__":
    main()
