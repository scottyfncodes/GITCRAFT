# GITCRAFT security model

Every GITCRAFT tool is started by `scripts/mcp.sh`, and that launcher, not each
tool's own settings, decides what the tool may touch. Three layers apply, from
the outside in:

```
Claude Code ⇄ guard.py ⇄ sandbox.py (Landlock) ⇄ tool MCP server (+ its native roots)
```

| Layer | Enforced by | What it does | Can a tool bypass it? |
|---|---|---|---|
| **Kernel sandbox** | `scripts/sandbox.py` (Linux Landlock, ABI ≥ 1; network rules need ABI ≥ 4) | The tool process and **every child it spawns** can read system directories, read/write only the authorized roots plus its own state folder, and nothing else. TCP bind/connect is denied unless `GITCRAFT_ALLOW_NET=1`, or narrowed to named hosts with `GITCRAFT_ALLOW_HOSTS` (below). | No. Landlock rules are irrevocable once applied and inherited across `exec`; `no_new_privs` is set. |
| **Guard** | `scripts/guard.py` (MCP stdio proxy) | Refuses tool calls whose path arguments resolve outside the roots or name a repository control file (below), with a readable error; refuses denied tools (e.g. EffectCraft `run_script`, PhotoCraft `control_call`); runs the control-file tripwire; writes the audit log. | It only sees arguments. Paths hidden inside documents (a project file that references media elsewhere) are stopped by the kernel layer instead; control files changed by other means are caught by the tripwire. |
| **Native roots** | Each app's `--automation-*-root` / `--root` flags | Defence in depth for the five apps that have them. | n/a. FilmCraft and LightCraft have none; the sandbox is their fence. |

## What each tool can access

| Access | Paths |
|---|---|
| read + execute | `/usr`, `/lib*`, `/bin`, `/sbin`, `/opt`, `~/.gitcraft/bin` (and MeshCraft's venv when installed) |
| read only | `/etc`, `/proc`, `/sys`, system and user font folders |
| read + write | every root in `GITCRAFT_ROOTS`, the tool's own `~/.gitcraft/state/<tool>/` (its `TMPDIR` and XDG config/cache/data), `/dev`, and for LightCraft its library |
| **denied** | everything else, including `~/.claude.json`, `~/.claude/`, `~/.ssh`, shell start-up files, GITCRAFT's runtime and binaries, `/tmp`, other repos outside the roots, and the network. This holds because no root may be `$HOME` or contain those folders (`scripts/mcp.sh` refuses to start a tool otherwise: "Choosing the roots") |
| **inside a root, defended by the guard** | repository control files: `.git/`, `.claude/`, `.mcp.json`, the scripts a repository's Claude Code hooks run, `.husky/`, `.vscode/`, `.envrc`, `.npmrc`… (next section). Landlock cannot carve them out of a writable root, so the guard refuses calls that name them and undoes changes to them |

## Control files inside the workspace

Some files in a repository are run or obeyed **outside** the sandbox later: git hooks and git config (`core.hooksPath`,
`core.fsmonitor`), Claude Code's `.claude/settings*.json` and the scripts its hooks run (GITCRAFT's own SessionStart
hook runs `scripts/session-start.sh`), `.mcp.json`, editor auto-run tasks (`.vscode/`), hook managers (`.husky/`,
`.pre-commit-config.yaml`, lefthook), `.envrc`, `.npmrc`/`.yarnrc*` and shell start-up files. A tool that could write
them would escape the sandbox at the next commit or session. `gitcraft3d/policy.py` lists them; three layers defend them:

| Layer | What it does |
|---|---|
| Guard: arguments | A tool call whose path argument names a control file (or the folder of a hook script) is refused. |
| Guard: tripwire | When a server goes from idle to busy, the guard snapshots every control file of the repositories under the roots (each root and its sub-folders); when the server is idle again (a long call counts until its `call_result` is collected) it compares. Any change is undone: new or changed content is moved to `<file>.gitcraft-quarantine-<time>` (mode 600, never executable), the original content and mode are put back, a deleted file is restored. The call's answer becomes an error naming each file, and `audit.jsonl` records it (`"tool": "tripwire"`). |
| Kernel: `run_script` | MeshCraft's `run_script` (arbitrary Python in Blender) runs in a child Blender with one more Landlock layer that can write **only** its outputs (next sections). |

Limits, stated plainly: the tripwire watches the repositories it finds at each root and one level below; a process a
tool leaves running after its call ends could change a control file between calls, and such a change is then treated
like one the person made. Changing a control file yourself while a tool is running gets your change moved aside
(it is kept in the quarantine file). Tools never write these files: nothing in GITCRAFT does so legitimately.
`tests/test_security_hardening.py` plants a git hook, a Claude Code hook and a hook-script change through a stand-in
server (harmless content, never run) and checks each is refused or undone.

## Updates and binaries

- **No unreviewed update runs.** The user-level SessionStart hook only fetches `~/.gitcraft/repo` and reports when
  `main` has moved. `scripts/update.sh` shows the commits and the security-relevant files they change and installs only
  with `--yes`, only a commit contained in `origin/main` (never a fork or unmerged branch); `--rollback --yes` returns
  to the previous commit. `GITCRAFT_AUTO_UPDATE=1` restores the old pull-and-run (not recommended: a compromised `main`
  would then run in every session, outside the sandbox, with the session's credentials).
- **Binaries are pinned.** The seven ArtCraft CLIs are built from upstream commits pinned in `scripts/tools.sh`
  (never a branch head). `install.sh` installs a prebuilt from the `bin` branch only when its SHA-256 is listed in
  `scripts/bin.sha256` on the checkout doing the install; anything else is refused before it is decompressed, the
  installed binary is kept and `status.json` records `integrity: mismatch` or `unpinned`. A mismatch is never papered
  over with a source build.
- **Publishing needs a reviewed pin.** `build.yml` only builds and gates; `publish-bin.yml` replaces `bin` only when a
  change to `scripts/bin.sha256` lands on main, and only with the files of the successful main build that file names,
  each matching its checksum. Steps: docs/install.md, "Releases". The trust anchor is therefore the protected `main`
  branch, not the `bin` branch. Protect `bin` too (a ruleset so only GitHub Actions can update it).
- **CI.** Every third-party action is pinned to a commit SHA (Dependabot proposes updates); Claude Code, uv, Playwright
  and the Rust toolchain are pinned to versions.

## Approvals

Deploying and creating infrastructure use the session's credentials on live systems, so the agent that would do them
cannot approve them. `production_approve` and the blueprint's `authorisations` are refused for `deploy` and
`infrastructure` (a decline is accepted). A person approves in GitHub: the project's
`.github/workflows/gitcraft-approval.yml` (template: `production/kit/release/gitcraft-approval.yml`) runs a job in the
environment `production` or `infrastructure`, which must have **Required reviewers** and must **not** let
administrators bypass it. `python3 -m production approve-external <production> <task> --run <url>` then checks with
GitHub's API that this run (of that workflow, in the project's repository, named for this production and task)
finished, that the environment requires reviewers, and that a GitHub *user* approved it. Anything it cannot verify
(no network, a private repository without `GITHUB_TOKEN`, no approval) is refused.

What makes this independent is GitHub: the agent can start the workflow but not approve it, **provided** its GitHub
credentials cannot review deployments and administrators cannot bypass the environment. Check both (the Claude GitHub
App's permissions; Settings > Environments). Note also that the agent can still deploy directly with a connected
Vercel account or merge to a branch that deploys: GITCRAFT's approval stops GITCRAFT from treating its word as
yours, and the platforms must stop the rest (restrict who can deploy production, require reviews on the production
branch). GITCRAFT's own records are not a security boundary against code with shell access.

## ForgeCraft

- ForgeCraft (`forgecraft/server.py`, stdlib Python) runs behind the same guard and sandbox. Every Blender step it orders runs as a MeshCraft child process (`meshcraft/server.py --call`), and Meshroom and the AI backends also run as its children, so the same fence applies to all of them.
- It can read and execute its code, `~/.gitcraft/forgecraft` (Meshroom, AI venv) and MeshCraft's Blender venv. It can write the shared 3D library (`$GITCRAFT_3D_LIBRARY`, default `~/.gitcraft/3d-library`, the same one MeshCraft writes) and its model cache.
- The engine check serves files to Chromium by request interception, not a socket, so it works with network denied.
- Hunyuan3D's hosted mode and the model downloads need network: prefer a per-host allowance (`forgecraft: huggingface.co` in `~/.gitcraft/allow-hosts`, below) over `GITCRAFT_ALLOW_NET=1`.
- ForgeCraft has no web server. `forgecraft/ui_server.py` only publishes a static snapshot (`--publish`); its former live mode was removed because it ran jobs outside the guard and sandbox and accepted unauthenticated, cross-site and DNS-rebinding requests. Browser access to every tool goes through the control room (`scripts/ui.sh`, see `docs/ui.md`). `tests/test_forgecraft_web.py` covers each finding.

## MeshCraft

MeshCraft runs Blender in-process and can execute Python (`run_script`, templates). It is safe to offer that because:
- it runs under the **same Landlock sandbox**, with extra read and execute access to its venv, its own code, Node and Chromium;
- it **checks paths itself** against `GITCRAFT_ROOTS`, on top of the guard;
- `run_script` runs the script in a **child Blender with one more Landlock layer** (`gitcraft3d/landlock.py`): it reads
  what MeshCraft can, but writes only its outputs: `write_dirs`, the `.blend`'s folder when it is saved, paths in `args`
  that do not exist yet, and existing paths under output keys (`out`, `out_dir`, `output`, `dest`, `export`...). Inputs
  (a palette, a GLB to import) stay read-only. A folder that holds control files (a repository root, `.git`, a hook
  script's folder) is refused before the script starts. Without Landlock, `run_script` is refused (unless
  `GITCRAFT_SANDBOX=off`). The script no longer changes the server's open scene; it works on its own `.blend` or outputs;
- the headless Chromium used by `engine_check` runs inside the sandbox too, with requests served through Playwright routing, so no network is needed.

`tests/test_meshcraft.py` proves it. A hostile `run_script` tries three escapes, and each is stopped by the kernel with `PermissionError`:
- reading `~/.claude.json`;
- writing `/tmp`;
- opening a TCP connection.

## Per-host network allowances (netgate)

Landlock can deny all TCP but cannot filter by host. To let a tool reach only named hosts (model downloads from
Hugging Face, for example), list them; everything else stays blocked:

```
# ~/.gitcraft/allow-hosts   (read by scripts/mcp.sh each time a tool starts; `#` comments)
forgecraft:  huggingface.co
forgecraft:  *.hf.co
studiocraft: huggingface.co
```

or `GITCRAFT_ALLOW_HOSTS_<TOOL>=host,host` / `GITCRAFT_ALLOW_HOSTS=...` (all tools) in the environment that starts Claude Code.

**Default allowance (CC0 libraries).** GITCRAFT's setup adds one marked block for StudioCraft's CC0 library actions
(`materialcraft_fetch`, `worldcraft_hdri`, `worldcraft_fetch_model`): `api.polyhaven.com`, `dl.polyhaven.org`, `ambientcg.com` and
`acg-download.struffelproductions.com` (where ambientCG's downloads redirect), HTTPS only and logged like any other netgate traffic.
Delete the `# gitcraft:cc0-sources` block to revoke it; `GITCRAFT_CC0_SOURCES=0` keeps setup from adding it. The environment's
own network policy must allow the same hosts. Downloads are treated as untrusted: size caps, Poly Haven md5 checks, zips read
member by member (no extraction paths), images decoded only by Pillow, and a minimal Radiance `.hdr` decoder.

How it works: `scripts/mcp.sh` starts `scripts/netgate.py`, an HTTPS CONNECT proxy on a random `127.0.0.1` port,
outside the sandbox. The tool's `HTTPS_PROXY` points at it, and the sandbox gets `--no-net --allow-connect <port>`:
the kernel allows TCP to that one port and nothing else, so the tool cannot reach any other host, nor the
environment's own proxy directly. netgate lets a CONNECT through only for listed hosts on port 443, tunnels it
(through the environment's `HTTPS_PROXY` when there is one, so TLS stays end to end and netgate never sees
content), logs every decision to `~/.gitcraft/logs/net.jsonl`, and exits with the tool. Patterns: exact host, or
`*.domain` for its subdomains. The tool reports its allowance (`GITCRAFT_SANDBOX` ends in `+netgate`;
studiocraft's `studio_status` shows `network.allowed_hosts`). `tests/test_netgate.py` proves the allowed host
works, others are refused (403), direct connections are refused by the kernel, and decisions are logged.

**The environment comes first.** netgate can only narrow what the environment allows. In Claude Code cloud
sessions, `huggingface.co` is blocked by the environment's network policy: allow it in the environment's settings
(cloud environment menu in the session's title bar ▸ Edit ▸ Network access: a broader level, or `huggingface.co`
under Allowed domains, keeping *Allow package managers* ticked; steps:
https://code.claude.com/docs/en/cloud-environments#network-access). Until then an allowed-but-blocked host fails
cleanly with 502 and `allowed-failed` in `net.jsonl`.

## Choosing the roots

- `GITCRAFT_ROOT` is the primary folder. It defaults to the session's project folder (`$CLAUDE_PROJECT_DIR`, else the current folder); a session opened in `$HOME` itself (or `/`) gets `~/gitcraft-work` instead. Before November 2026 the local default was `$HOME`, which made `~/.claude`, `~/.ssh` and shell start-up files writable from inside the sandbox. Tools with a single native root flag (PhotoCraft) get this one.
- **Refused roots.** `scripts/mcp.sh` does not start a tool whose roots include `/`, `$HOME` or a folder containing it, `~/.gitcraft` itself or its runtime, code, binaries, clone, logs, venvs or `allow-hosts`, or anything inside `~/.ssh`, `~/.claude`, `~/.config` and similar (`gitcraft3d/policy.py`). There is no override: Landlock cannot fence those files once their folder is writable. GITCRAFT's shared stores (`~/.gitcraft/productions`, `reports`, `3d-library`...) remain usable.
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

`tests/test_security_hardening.py` covers the controls above with local fixtures: pinned and tampered binaries, the
update path, refused roots, the guard's control-file refusals and tripwire, `run_script`'s write layer, and every
refusal of the approval check. `tests/test_policy.py` starts every installed tool through the launcher, does one real operation inside a scratch workspace, checks a path outside it is refused, and runs FilmCraft and LightCraft under the kernel sandbox **without** the guard to prove the kernel layer stops them on its own (`Permission denied (os error 13)`).

## Known limits

- Landlock needs Linux 5.13+ (network rules: 6.7+). macOS and Windows hosts get the guard and native roots only; `doctor.sh` reports this.
- Read access to `/etc` and `/proc` is allowed (tools need them for fonts, locale, CPU info). Secrets do not belong there.
- The guard's path detection is heuristic (keys such as `path`/`out`, or absolute strings). It exists for clear errors and the audit trail; the kernel sandbox is the boundary.
