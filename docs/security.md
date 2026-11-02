# GITCRAFT security model

Every GITCRAFT tool is started by `scripts/mcp.sh`, and that launcher, not each
tool's own settings, decides what the tool may touch. Three layers apply, from
the outside in:

```
Claude Code ⇄ guard.py ⇄ sandbox.py (Landlock) ⇄ tool MCP server (+ its native roots)
```

| Layer | Enforced by | What it does | Can a tool bypass it? |
|---|---|---|---|
| **Kernel sandbox** | `scripts/sandbox.py` (Linux Landlock, ABI ≥ 1; network rules need ABI ≥ 4) | The tool process and **every child it spawns** can read system directories, read/write only the authorized roots plus its own state folder, and nothing else. TCP bind/connect is denied unless `GITCRAFT_ALLOW_NET=1`. | No. Landlock rules are irrevocable once applied and inherited across `exec`; `no_new_privs` is set. |
| **Guard** | `scripts/guard.py` (MCP stdio proxy) | Refuses tool calls whose path arguments resolve outside the roots, with a readable error; refuses denied tools (e.g. EffectCraft `run_script`, PhotoCraft `control_call`); writes the audit log. | It only sees arguments. Paths hidden inside documents (a project file that references media elsewhere) are stopped by the kernel layer instead. |
| **Native roots** | Each app's `--automation-*-root` / `--root` flags | Defence in depth for the five apps that have them. | n/a. FilmCraft and LightCraft have none; the sandbox is their fence. |

## What each tool can access

| Access | Paths |
|---|---|
| read + execute | `/usr`, `/lib*`, `/bin`, `/sbin`, `/opt`, `~/.gitcraft/bin`; for MeshCraft also its code (`meshcraft/`) and runtimes (`~/.gitcraft/meshcraft`: Blender, Meshroom, AI venv) |
| read only | `/etc`, `/proc`, `/sys`, system and user font folders |
| read + write | every root in `GITCRAFT_ROOTS`, the tool's own `~/.gitcraft/state/<tool>/` (its `TMPDIR` and XDG config/cache/data), `/dev`, for LightCraft its library, for MeshCraft its library (`~/.gitcraft/meshcraft-library`) and model cache (`~/.gitcraft/meshcraft/hf-cache`) |
| **denied** | everything else, including `~/.claude.json`, `~/.ssh`, credentials, `/tmp`, other repos outside the roots, and the network |

## Choosing the roots

- `GITCRAFT_ROOT` is the primary folder (it defaults to `$HOME`, or to the session workspace when that is outside `$HOME`). Tools with a single native root flag (PhotoCraft) get this one.
- `GITCRAFT_ROOTS` is a colon-separated list of every authorized folder, e.g. one per repo. It defaults to `GITCRAFT_ROOT`. Narrow it to scope tools to specific repositories:
  `GITCRAFT_ROOTS=/home/user/TIDEBREAKERS:/home/user/GITCRAFT`.
- Set these in the environment's variables (or before launching Claude Code); `mcp.sh` reads them each time a server starts.

## Modes

| `GITCRAFT_SANDBOX` | Behaviour |
|---|---|
| `landlock` (default) | Sandbox when the kernel supports it; otherwise run with guard + native roots and say so on stderr and in `doctor.sh`. |
| `require` | Refuse to start a tool when Landlock is unavailable. Use this on shared machines. |
| `off` | No kernel sandbox (guard and native roots still apply). Debugging only. |

## Audit log and handoffs

`~/.gitcraft/logs/audit.jsonl` gets one line per tool call: server, tool, duration, success, refusal reason, truncated arguments, and the **size and SHA-256 of every file the call referenced** that exists afterwards. A file's hash at the producing tool's export matches the hash at the consuming tool's import, so handoffs between tools can be traced and reproduced. `scripts/doctor.sh` summarises it.

## Verifying

`tests/test_policy.py` starts every installed tool through the launcher, does one real operation inside a scratch workspace, checks a path outside it is refused, and runs FilmCraft and LightCraft under the kernel sandbox **without** the guard to prove the kernel layer stops them on its own (`Permission denied (os error 13)`).

## MeshCraft specifics

- Blender, Meshroom and the engine check (Node + Chromium) all run as children of the sandboxed server, so the same fence applies to them. The three.js check serves files to Chromium through Playwright request interception rather than a local socket, so it works with network denied.
- Hunyuan3D's hosted mode and first-time weight downloads need network: set `GITCRAFT_ALLOW_NET=1` deliberately, for that session only.
- `meshcraft/ui_server.py` (the live UI) runs **outside** the sandbox as a local developer tool and binds to 127.0.0.1 only.

## Known limits

- Landlock needs Linux 5.13+ (network rules: 6.7+). macOS and Windows hosts get the guard and native roots only; `doctor.sh` reports this.
- Read access to `/etc` and `/proc` is allowed (tools need them for fonts, locale, CPU info). Secrets do not belong there.
- The guard's path detection is heuristic (keys such as `path`/`out`, or absolute strings). It exists for clear errors and the audit trail; the kernel sandbox is the boundary.
