#!/usr/bin/env python3
"""Long tool calls never hit the client's timeout (gitcraft3d/calls.py).

Claude Code gives up on an MCP tool call after MCP_TOOL_TIMEOUT (60 s in cloud sessions); a PIXELCRAFT verify took
3-6 minutes and was cut off, while the work went on with nobody to read the result. Every GITCRAFT server now answers
within its budget: inline when the call is done, otherwise {status: running, call_id}; call_result collects it.

  1. the call registry itself: inline answers, detaching after the budget, call_result waiting and returning the
     tool's own result (errors stay errors), unknown ids, the list, the budget from MCP_TOOL_TIMEOUT
  2. the real servers through scripts/mcp.sh (guard + sandbox) with a tiny budget: a call is answered with a call_id,
     call_result returns exactly what the tool returns inline, call_result is listed, and MeshCraft answers ping and
     call_result while Blender is busy on its main thread
  3. the clients follow it: tests/mcp_client.py returns the final result

    python3 tests/test_long_calls.py"""
import importlib.util, json, os, shutil, sys, tempfile, threading, time
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from mcp_client import Client
spec = importlib.util.spec_from_file_location("gitcraft_calls", os.path.join(REPO, "gitcraft3d", "calls.py"))
calls = importlib.util.module_from_spec(spec); spec.loader.exec_module(calls)
results = []


def check(label, cond, detail=""):
    results.append((label, bool(cond))); print(("PASS " if cond else "FAIL ") + label + (f"  [{str(detail)[:400]}]" if detail and not cond else ""), flush=True)


def text(r): return json.loads(r["content"][0]["text"])


# ---------------------------------------------------------------- 1. the registry
os.environ["GITCRAFT_MCP_INLINE_SECONDS"] = "0.3"
sent = []
reply = lambda v, e=None: {"isError": e is not None, "content": [{"type": "text", "text": json.dumps({"error": str(e)} if e else v)}]}
C = calls.Calls(sent.append, reply)
C.run(1, "fast", lambda: {"ok": 1}); time.sleep(0.15)
check("registry: a call that finishes within the budget is answered inline, with its result", sent and sent[-1]["id"] == 1 and text(sent[-1]["result"]) == {"ok": 1}, sent)
check("registry: ...and leaves nothing to collect", text(C.result({}))["calls"] == [], C.result({}))
sent.clear()
C.run(2, "slow", lambda: (time.sleep(1.0), {"done": True})[1]); time.sleep(0.6)
run = text(sent[-1]["result"]) if sent else {}
check("registry: a call past the budget is answered with status running and a call_id", sent and sent[-1]["id"] == 2 and calls.is_running(run) and run["tool"] == "slow", sent)
check("registry: ...the list shows it running", [r["status"] for r in text(C.result({}))["calls"]] == ["running"], C.result({}))
t0 = time.time(); r1 = C.result({"call_id": run["call_id"], "wait_seconds": 0.05})
check("registry: call_result answers 'running' again while it is not done (and waits no longer than asked)", calls.is_running(text(r1)) and time.time() - t0 < 0.3, r1)
r2 = C.result({"call_id": run["call_id"]})
while calls.is_running(text(r2)): r2 = C.result({"call_id": run["call_id"]})
check("registry: call_result waits and returns the tool's own result", text(r2) == {"done": True} and not r2["isError"], r2)
check("registry: the request is never answered twice", [m["id"] for m in sent] == [2], sent)
sent.clear()
def boom(): time.sleep(0.6); raise ValueError("bad brief")
C.run(3, "bad", boom); time.sleep(0.4)
r3 = C.result({"call_id": text(sent[-1]["result"])["call_id"]})
check("registry: a detached call that fails returns its error as an error", r3["isError"] and "bad brief" in r3["content"][0]["text"], r3)
check("registry: an unknown call_id is an error that says why", C.result({"call_id": "c-nope"})["isError"])
os.environ.pop("GITCRAFT_MCP_INLINE_SECONDS")
os.environ["MCP_TOOL_TIMEOUT"] = "60000"
check("budget: the client's MCP_TOOL_TIMEOUT less 15 s (60 s → 45 s)", calls.budget() == 45.0, calls.budget())
os.environ["MCP_TOOL_TIMEOUT"] = "8000"
check("budget: never under 5 s", calls.budget() == 5.0, calls.budget())
os.environ.pop("MCP_TOOL_TIMEOUT")
check("budget: 45 s when the client says nothing", calls.budget() == 45.0)

# ---------------------------------------------------------------- 2. the real servers
ws = os.path.realpath(tempfile.mkdtemp(prefix="gitcraft-longcalls-"))
env = dict(os.environ, GITCRAFT_ROOT=ws, GITCRAFT_ROOTS=ws, GITCRAFT_ASSET_CATALOG=os.path.join(ws, "c.sqlite"), GITCRAFT_3D_LIBRARY=os.path.join(ws, "3d"),
           GITCRAFT_PLAYCRAFT_HISTORY=os.path.join(ws, "ph"), GITCRAFT_PIXELCRAFT_HISTORY=os.path.join(ws, "pxh"), GITCRAFT_MCP_INLINE_SECONDS="0.05")
TRY = {"studiocraft": ("studio_status", {}), "forgecraft": ("departments", {}), "meshcraft": ("list_templates", {})}
for name, (tool, args) in TRY.items():
    try: c = Client([os.path.join(REPO, "scripts", "mcp.sh"), name], env=env, log=os.path.join(ws, name + ".log"))
    except Exception as e:
        check(f"{name}: starts through scripts/mcp.sh", False, e); continue
    try:
        names = [t["name"] for t in c.tools()]
        if tool not in names:
            print(f"SKIP {name}: {tool} not listed (runtime not installed here: {names[:3]})"); continue
        check(f"{name}: call_result is listed", "call_result" in names, names[-5:])
        r = c.req("tools/call", {"name": tool, "arguments": args}, 600); first = text(r)
        check(f"{name}: a call longer than the budget is answered at once with a call_id", calls.is_running(first), str(first)[:300])
        if name == "meshcraft" and calls.is_running(first):
            t0 = time.time(); c.req("ping", {}, 30)
            check("meshcraft: ping is answered while the tool runs on the main thread", time.time() - t0 < 5)
        if calls.is_running(first):
            fin = first
            while calls.is_running(fin):
                r = c.req("tools/call", {"name": "call_result", "arguments": {"call_id": fin["call_id"]}}, 600); fin = text(r)
            check(f"{name}: call_result returns the tool's result", not r.get("isError") and fin and not calls.is_running(fin), str(fin)[:300])
        ok, via = c.call(tool, args, timeout=600)
        check(f"{name}: tests/mcp_client.py returns the final result" + (" (followed a call_id)" if c.detached else " (answered inline)"), ok and via and not calls.is_running(via), str(via)[:300])
    finally:
        c.close()

shutil.rmtree(ws, ignore_errors=True)
bad = [l for l, ok in results if not ok]
print(f"\n{len(results) - len(bad)}/{len(results)} passed" + (f"; FAILED: {bad}" if bad else ""))
sys.exit(1 if bad else 0)
