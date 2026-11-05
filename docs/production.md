# The Production Director: one master prompt → a verified production

## Using it

Tell Claude Code what you want, in one message, as completely as you like:

> Build a polished, mobile-first, original game with a complete gameplay loop, progression, original visual
> identity, sound, levels, responsive controls and production-ready deployment.

That's all you have to do. Claude follows the `produce` skill:

1. `production_plan` with your prompt.
2. `production_run`.
3. Each work order handed to it (the code, wiring the assets in, the logo in VectorCraft), followed by `production_submit`.
4. Repeat until the acceptance report says READY, or a genuine blocker remains.

You'll be asked only what matters:

- **Essential questions:** rare, because most choices have a safe default, which the report lists as an assumption.
- **Approvals:** deploying, or replacing a file your project already has.

At the end you get the project, and a report listing every acceptance criterion with its measured evidence.

What you never need to know: which departments exist, which order they run in, which can run at the same time,
how files move between them, or which checks decide "done".

## The lifecycle

| Stage | What happens | Code |
|---|---|---|
| 1 Intake | The prompt becomes a spec: deliverable, 2D/3D, platform and viewports, engine, genres, features, the assets each department makes, a quality bar, authorisations (deploy, replacing assets, merging and spending are never pre-authorised), measurable acceptance criteria, assumptions, and questions (`essential` only when there's no safe default). `overrides` correct any field. | `intake.py`, `rules.json` |
| 2 Discovery | The project is read without running it: engine, entry, build folder, existing assets (an existing `jump.wav` means no new jump sound), tests, docs, git. The departments report what is ready on this machine (Studio `studio_status`, and ForgeCraft's probe for 3D). | `discovery.py` |
| 3 Analysis | Tasks that can't run here are known before anything starts (`blocked_up_front`, with the reason and the install command). | `planner.readiness` |
| 4 Planning | A task graph: stage, owner, department action and request, dependencies, hand-off references, what ships into the project, the gate, resources and retries. Parallel waves are computed from it. It is validated before running: unknown dependencies, cycles, unknown actions, and requests a department would refuse are all reported as `problems`. | `planner.py` |
| 5 Foundation | Project folders (never overwriting anything); the visual identity (agent + VectorCraft), whose palette the effects are tinted with. | `builtins.scaffold` |
| 6 Production | Department tasks run concurrently (4 workers; at most 2 browsers and 1 Blender at a time), each in its own process. | `engine.run`, `executors.py` |
| 7 Integration | Every passed output that ships is copied into the project, hash-verified, with a `.license.json` sidecar. Two different files for one path is a conflict (failed, nothing copied). Replacing a different existing file needs approval. Then the build work order lists every integrated asset. | `builtins.integrate` |
| 8 QA | TestCraft smoke (and perf when the bar asks for it), PLAYCRAFT (games), PIXELCRAFT (anything with a UI), DESIGNCRAFT (games; advisory), asset integrity (opens and is referenced by the build), and licences (AssetCraft). | `planner.py`, `gates.py` |
| 9 Release | The final regression smoke on the exact build, then the release report. Any QA evidence measured on an older project state is re-measured first. Deployment needs approval, and is only "verified" with a passing check against the live URL. | `engine._release` |
| 10 Memory | `production.json`, `events.jsonl`, hand-offs, work orders, every department's `.studio.json`, and `REPORT.md`. A run can be resumed at any time. | `store.py`, `report.py` |

## Task states

| State | Meaning |
|---|---|
| `pending` | Waiting for its dependencies (or for a retry) |
| `in_progress` | A department or built-in is working on it |
| `awaiting_agent` | A work order is out; Claude must do it and submit |
| `complete` | The tool finished and its outputs validated. Only the gate decides what happens next (`complete` never means done) |
| `passed` | The gate held: dependent work may start |
| `failed` | The gate or the department failed. `failure` says which: `quality` (measured problem → remediation), `execution` (crash/timeout, retried first), `request` (bad request, never retried), `handoff`, `conflict` |
| `blocked` | It cannot run here (missing runtime, with the install command), or an upstream task failed (`blocked_by`) |
| `needs_approval` | A person must decide (deploy, replacing assets) |
| `skipped` | Declined by a person, or superseded |

The production's own status is one of `planned`, `needs_input`, `running`, `in_progress`, `awaiting_agent`, `needs_approval`, `passed` (`passed_not_deployed` / `passed_deploy_unverified` when a deployment was requested), `failed` or `blocked`.

## Gates and remediation

A gate is a list of conditions. For a department task, `status_ok` means the department's own validation and
checks passed. `min` needs a measured value at or above the bar; a value that wasn't measured fails. `referenced`
means every integrated asset is used by the build. Agent submissions must have every expected file inside the
workspace, opening as its format, with the expected JSON keys. A fix must actually change the project.

When a QA gate fails, the engine:

1. Creates `fix.<check>.r1`, a work order listing the measured findings (failed checks, PLAYCRAFT's plan, PIXELCRAFT's findings) with links to the evidence.
2. Creates `<check>.r1`, the same check depending on that fix. Dependents now wait on the re-verification.
3. Stops after `quality.max_rounds` rounds (2 standard, 3 polished). The check stays failed, the release is blocked and the report says NOT READY.

## Departments and their contracts

`production_contracts` lists every department in one shape: what it accepts, produces and requires, how success
and failure are reported, where outputs go, and how provenance and licences are recorded. The Studio entries are
read from the manifests, so they can't drift from the code. Executors:

| Executor | Who | Called through |
|---|---|---|
| `studio` | AudioCraft, LevelCraft, FXCraft, MaterialCraft, WorldCraft, AnimCraft, CinematicCraft, TestCraft, AssetCraft, PLAYCRAFT, PIXELCRAFT | `studio/cli.py --call run` (the department contract) |
| `forgecraft` | the 3D Department (ForgeCraft → MeshCraft) | `forgecraft/cli.py call generate …`, then `library_export` at integration |
| `designcraft` | DESIGNCRAFT game-design review | `gamedesign` CLI, loaded by path |
| `builtin` | scaffold, integrate, licences, release | `production/builtins.py`, `engine._release` |
| `agent` | Claude: code, integration, the 2D ArtCraft tools | work orders + `production_submit` |

ForgeCraft keeps the 3D Department. The Director gives it a brief and records the result; it never reimplements routing, Blender work or the engine check.

## Correcting the plan

`production_plan` takes `overrides`, deep-merged into the spec. For example:

- `{"quality": {"playcraft_min": 60, "max_rounds": 2}}` raises the gameplay bar and limits remediation to two rounds.
- `{"assets": {"levels": {"kind": "dungeon", "count": 4, "by_levelcraft": true}}}` asks for four LevelCraft dungeons.
- `{"extra_tasks": [{"id": "audio.boss", "department": "audiocraft", "action": "music", "params": {"mood": "tense"}, "ship": {"dest": "$project/assets/audio", "roles": ["music"], "formats": ["ogg"]}}]}` adds a task. Extra tasks are validated, gated and integrated like the rest.
- `{"skip_tasks": ["qa.perf"]}` drops a task (the skip is recorded as a decision).

Request parameters can reference upstream results:

- `"$project/…"` is the project folder.
- `{"$from": "<task>", "role": …, "format": …}` is an upstream output's path.
- `{"$from": "<task>", "role": "palette", "json": "accent", "as": "rgb"}` is a value read from an upstream JSON output.

## Safety

- Everything runs inside the studiocraft sandbox: workspace roots, its state, the shared libraries, and no network. The sandbox now also reads (never writes) the code of the departments the Director delegates to: `production/`, `forgecraft/`, `gitcraft3d/`, `meshcraft/` and `gamedesign/`, as ForgeCraft's sandbox already did. The 3D Department's model cache is writable for the same reason.
- The production store and the project must be inside the roots. Submitted files outside the roots are refused, and the guard refuses relative paths, so submit absolute ones.
- Integration never silently overwrites a file, and two deliverables can never ship to one path.
- Deploying, replacing existing assets, merging and spending are never authorised by the intake. A deployment without evidence is never recorded as live.
- One runner per production (a file lock). A second one is refused with a clear message.

## CLI

```bash
python3 -m production plan "<master prompt>" [--project DIR] [--overrides JSON]
python3 -m production run <id>            # run or resume
python3 -m production status <id>
python3 -m production submit <id> <task> --files /abs/a /abs/b --notes "…" [--run]
python3 -m production approve <id> <task> [--decline]
python3 -m production report <id>
python3 -m production list | contracts
```

## Verification

- `tests/test_production.py` (~1 min) covers intake, planning, validation, gates, store, lock and fingerprints, plus a real production through the sandboxed server: plan, run, idempotent resume, and redoing a task whose output was deleted.
- `tests/acceptance_production.py` (~6 min) is the master-prompt run:
  - **Part A:** the Lantern Drift prompt, end to end. Interpretation, discovery, department selection, ordering, measured parallelism, the palette → effects hand-off, integration of 27 assets, a real defect caught by TestCraft and a real PLAYCRAFT shortfall (54 against a bar of 55, then 63 after the fix work order), re-verification, stale evidence re-measured, release on the exact build, deployment refused without evidence, and resume.
  - **Part B:** a refused plan, a missing runtime (blocked and propagated), a failed department (retried, then failed), an invalid agent output, an integration conflict, overwrite protection, a run killed mid-production and resumed, and a quality gate exhausted (NOT READY).

## Limits

- **Intake is rule-based** (`rules.json`) and deterministic. It records why it chose each value, but it can misread an unusual prompt. Claude is expected to read the spec and correct it with `overrides`.
- **Code is the agent's job.** The engine can't write a game. It hands Claude a work order with every input and verifies the result by measuring the build.
- **The 2D ArtCraft tools can't be driven from inside the studiocraft sandbox**, so their work is a work order for Claude to run with those MCP tools. The returned files are validated.
- **Deployment verification needs a check that ran against the live URL.** The default sandbox has no network, so in a default session a deployment is recorded as unverified rather than live.
- **Scores carry the departments' own noise.** PLAYCRAFT reports its confidence and measured noise band; the gate compares the measured overall against the bar exactly.
