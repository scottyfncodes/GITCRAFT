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

## Fixed in the follow-up (gap closure)

| ID | Was | Fix |
|---|---|---|
| F5 | `test_netgate.py` failed on every standard install (the CC0 allow-list) | `GITCRAFT_ALLOW_HOSTS[_TOOL]=none` is an explicit no-network run (the allow-hosts file is not read); the test uses it. 8/8 |
| F6 | `--no-net` dropped silently on Landlock ABI < 4 | a warning, and `--require` refuses to run with network access |
| F7 | audit hashing delayed every response | the response goes out first; hashes are cached by path, size and mtime |
| F8 | the UI's pool lock was held while a tool server started | a per-tool start lock; the pool lock guards only the dictionary |
| CI | `testcraft: FPS profile` failed at 50.1 ms on a runner (PR #49) | the test checks that the profiler measures and gates, at the production "standard" budget (100 ms) |
| L3 | the live browser check routed `127.0.0.1` through the HTTPS proxy (405) | localhost and `NO_PROXY` hosts bypass the proxy |

## Remaining, prioritised (not changed: low risk or out of this upgrade's scope)

| ID | P | Where | Problem | Evidence | Suggested fix |
|---|---|---|---|---|---|
| P1 | P2 | `production/discovery.py` | Up to 200 code files × 200 KB are read into one string to detect engines (up to 40 MB of memory). | Hypothetical | Stop reading at the first match per engine |
| F9 | P3 | `tests/test_policy.py` | Crashes when ForgeCraft is in its deferred (Blender not yet installed) state, so the later network checks never run. | Demonstrated | Skip with a reason when the tool lists only its status tool |
| F10–F12 | P3 | `ui/server.py`, `guard.py` | A file descriptor leaks per restarted UI client; duplicate `Cache-Control` headers on vendor files; the last guard response could be lost when stdin closes (F12 fixed with the reader join). | Partly demonstrated | Close the client's log handle; let callers override headers |
| F14 | P3 | `scripts/mcp.sh`, `guard.py` | All of `/dev` is writable in the sandbox. The deny list doesn't check `command_batch` steps. No denied command was reachable that way. | Not demonstrated | Restrict `/dev` to null/shm/urandom; check batch step ids |

## What held up

The production store's atomic `production.json` and per-production `flock`, the UI's constant-time token check and
Host/Origin checks, the static-file and library path validation, the department contract's validation and
`blocked` semantics, and every existing suite that doesn't need Blender (`test_production.py` 43/43,
`test_stdio_isolation.py` apart from the Blender server).

## Known environment-dependent failures

`tests/test_ui.py` fails 10 of 54 checks on a machine where MeshCraft's local three.js and Blender library are not fully
installed. The same 10 fail on `main` before these changes. The suite is not part of CI.

## Test status at the time of the assessment

Suites that need Blender (`test_policy.py` network section, `test_ui.py` bake, the forgecraft part of
`test_stdio_isolation.py`) fail in a session where the 400 MB `bpy` wheel isn't installed yet. That is an environment
state, not a code defect, and each such failure says "Blender (bpy) isn't installed yet".
