# Technical debt assessment (November 2026)

This assessment came from reading the code and running the suites on a cloud session, rather than from the docs. Each finding says
whether it was **demonstrated** (reproduced, or shown by a failing test) or is **hypothetical** (read from the code, not reproduced).
Priorities:
- **P0**: critical security, data-integrity or operational failure.
- **P1**: significant reliability, performance or maintainability problem.
- **P2**: moderate.
- **P3**: cosmetic or speculative.

Regression tests for the fixed items: `tests/test_hardening.py`. Each test was confirmed to fail on the code before the fix.

## Fixed in this upgrade

| ID | P | Where | Problem | Evidence | Fix |
|---|---|---|---|---|---|
| F1 | P1 | `ui/server.py` `/vendor/three/` | Any `.js` file on disk could be read without the token. An absolute path after the prefix made `os.path.join` discard the three.js folder. | Demonstrated: `GET /vendor/three//tmp/x.js` → 200 with the file | Resolve with `realpath` and require the result to be inside the package, as the static route already does |
| F2 | P1 | `scripts/guard.py` | One malformed `tools/call` killed the guard, and the tool server with it: an `arguments` that isn't an object, an object as `id`, or a non-string command id. Later requests were never answered. | Demonstrated: no reply to the next `ping`; through the UI, `pdfcraft alive: False` | Validate in `check_call`. A malformed call gets a refusal answer, and the guard keeps serving. The reader thread is joined on exit so the last responses are delivered |
| F3 | P2 | `ui/server.py` POST | `Content-Length: -1` held a thread until the client gave up. `abc` dropped the connection with no response. | Demonstrated | 400 for a non-integer or negative length |
| F4 | P2 | `ui/server.py` `/files` | Dotfiles and anything in dot-folders under the roots could be served (with the default root `$HOME`, that includes `~/.claude.json` and credentials). It still needed the session cookie. | Demonstrated (`.private/creds.json` → 200) | `file_allowed` refuses any path component that starts with `.` |
| F13 | P3 | `production/store.py`, `builtins.py` | A failed atomic write left a `.tmp-` file behind. Two writes used unclosed file handles. | Demonstrated | Clean up the temp file; use `with` for the handles |
| L1 | P1 | `production/engine.py` | Approving Discovery was the same as authorising the build: `production_plan` → `production_run` built with no human approval of the plan's material choices, and a later change of scope was applied silently. | By design (no approval step existed) | The Decision Room and blueprint (`production_decide`): `run` refuses until a blueprint is approved, and a material revision pauses the build until it is approved again (docs/production.md) |
| L2 | P2 | `production/builtins.py` | A measured QA built-in that returned no output file was classed as an execution failure. It was retried and never remediated. | Demonstrated while adding `qa.attribution` | Built-in checks write their evidence (`_with_report`), so a failure is a quality finding with a fix work order |

## Remaining, prioritised (not changed: low risk or out of this upgrade's scope)

| ID | P | Where | Problem | Evidence | Suggested fix |
|---|---|---|---|---|---|
| F5 | P2 | `tests/test_netgate.py` vs `scripts/install-global.sh` | The installer allows four CC0 hosts by default, but the test expects no network. It fails on every standard install. The UI shows "network denied" while netgate allows hosts. | Demonstrated (7/8) | Run the test with a temp `GITCRAFT_HOME` or `GITCRAFT_CC0_SOURCES=0`; have the UI show the netgate allowances |
| F6 | P2 | `scripts/sandbox.py` | On kernels with Landlock ABI < 4 (before Linux 6.7), `--no-net` is dropped without a warning, even with `GITCRAFT_SANDBOX=require`. | Hypothetical (this kernel is ABI 7) | Warn, and refuse under `--require` |
| F7 | P2 | `scripts/guard.py` | The audit hashes every output file (up to 512 MB × 200) before the response goes out, so large outputs can push a call past the client's timeout. | Hypothetical | Respond first and hash in a worker, or cache hashes by mtime and size |
| F8 | P2 | `ui/server.py` `Pool.get` | The pool lock is held while a tool server starts (up to 60 s), which blocks every other call. | Hypothetical | Start the client outside the lock |
| P1 | P2 | `production/discovery.py` | Up to 200 code files × 200 KB are read into one string to detect engines (up to 40 MB of memory). | Hypothetical | Stop reading at the first match per engine |
| F9 | P3 | `tests/test_policy.py` | Crashes when ForgeCraft is in its deferred (Blender not yet installed) state, so the later network checks never run. | Demonstrated | Skip with a reason when the tool lists only its status tool |
| F10–F12 | P3 | `ui/server.py`, `guard.py` | A file descriptor leaks per restarted UI client; duplicate `Cache-Control` headers on vendor files; the last guard response could be lost when stdin closes (F12 fixed with the reader join). | Partly demonstrated | Close the client's log handle; let callers override headers |
| F14 | P3 | `scripts/mcp.sh`, `guard.py` | All of `/dev` is writable in the sandbox. The deny list doesn't check `command_batch` steps. No denied command was reachable that way. | Not demonstrated | Restrict `/dev` to null/shm/urandom; check batch step ids |

## What held up

The production store's atomic `production.json` and per-production `flock`, the UI's constant-time token check and
Host/Origin checks, the static-file and library path validation, the department contract's validation and
`blocked` semantics, and every existing suite that doesn't need Blender (`test_production.py` 43/43,
`test_stdio_isolation.py` apart from the Blender server).

## Test status at the time of the assessment

Suites that need Blender (`test_policy.py` network section, `test_ui.py` bake, the forgecraft part of
`test_stdio_isolation.py`) fail in a session where the 400 MB `bpy` wheel isn't installed yet. That is an environment
state, not a code defect, and each such failure says "Blender (bpy) isn't installed yet".
