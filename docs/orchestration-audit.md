# Orchestration audit (before the Production Director)

An audit of how GITCRAFT coordinated work across its tools, made by reading the code rather than the docs,
before `production/` was built. Each finding names the file that shows it, followed by how it was addressed.

## 1. Orchestration that already existed

| Capability | Where | Scope |
|---|---|---|
| Per-action department contract: validate request → check dependencies (`blocked`, never a substitute) → run → validate + hash every output → `.studio.json` provenance → AssetCraft catalogue | `studio/core/contract.py` | one action at a time |
| 3D pipeline with a job store: route → MeshCraft → engine check → library version, stage records, retry ladder of lighter settings, parent/child jobs | `forgecraft/pipeline.py`, `gitcraft3d/jobs.py` | 3D only |
| Keyword routing of a brief to one action (plus a 3D pointer) | `studio/core/routing.py`, ForgeCraft `department_route` | picks a single "chosen" action |
| Quality evaluators: TestCraft (engineering), PLAYCRAFT (gameplay, with history), PIXELCRAFT (UI/UX, with history), DESIGNCRAFT (design structure) | `studio/departments/*`, `gamedesign/` | measure one build each |
| Cross-department entry from ForgeCraft (`departments`, `department_route`, `department_run`) | `forgecraft/studio.py` | pass-through |

## 2. Working but disconnected

- **DESIGNCRAFT (`gamedesign/`)** could not be reached from any MCP server or department. It was only available as `python3 -m gamedesign`, and Claude had to know it existed.
- **The three quality histories** (PLAYCRAFT, PIXELCRAFT, DESIGNCRAFT) each record runs, but nothing connected a score to a release decision.
- **The 2D ArtCraft tools** (vectorcraft, photocraft…) can't be called from another sandboxed server. Their output reached the departments only when Claude moved the files by hand.
- **The AssetCraft catalogue** registered every output, but nothing checked that shipped assets were catalogued with known licences before a release.

## 3. Duplication

- There are two job/record systems: `gitcraft3d/jobs.py` (3D job records) and `.studio.json` (Studio provenance). Both are kept: they record different things, and the production record links to both rather than adding a third format for department work.
- **A name collision:** "DesignCraft" is the page-layout MCP tool, and "DESIGNCRAFT" is game-design intelligence (`gamedesign/`). The production engine calls the latter `designcraft` in task kinds but labels it "DESIGNCRAFT (game design)" everywhere a person reads it.

## 4. Missing

- No interpretation of a whole request: deliverable, platform, features, quality bar, acceptance criteria.
- No production plan: no task graph, dependencies, parallel waves or ownership.
- No structured hand-offs: one department's output path had to be copied into the next request by hand.
- No integration step into the project, no conflict detection, and no overwrite protection beyond `assetcraft_integrate`.
- No quality gates between stages, and no remediation loop with re-verification of the modified build.
- No production-level state: progress, resume and history across sessions.
- No release decision and no acceptance report.

## 5. Order-of-operation problems

- Nothing stopped QA from running before integration, or a release being prepared while a QA check was failing.
- QA evidence was not tied to a build. A PLAYCRAFT pass measured before a later fix could still be quoted as the result.

## 6. Where Claude coordinated manually

These steps were all done by hand: choosing departments, ordering them, passing paths between them, deciding whether a score was good enough, re-running checks after a fix, and writing the final summary. The global instructions said "chain tools by handing files between them". That was the entire orchestration layer.

## 7. Paths to incomplete or falsely successful results

| Risk | Evidence |
|---|---|
| A low score reported as success | `playcraft_pass` returned `status: "ok"` for a game scoring 41/100 (measured on the fixture game). `ok` means the assessment ran, not that the game is good |
| A high score at low coverage | `pixelcraft_audit` returned 100/100 with 32% coverage and `confidence: "low"` (fixture game) |
| A rejected request losing its reason | a department raising `StudioError` during request validation exits the CLI with a traceback (no JSON), e.g. `params.color must be array` |
| An install status that looked healthy | `status.json` said `studiocraft: ok` while `doctor.sh` reported it unregistered in the same session |

## What was built (and where each finding is addressed)

| Finding | Addressed by |
|---|---|
| No request interpretation | `production/intake.py`: spec, assumptions, essential questions, acceptance criteria |
| No plan / dependencies / parallelism | `production/planner.py`: task graph, waves, hand-off references, plan-time validation against every department's own schema |
| Manual coordination | `production/engine.py`: scheduler with parallel workers, resource limits (2 browsers, 1 Blender), retries, failure propagation |
| Tool success ≠ deliverable success | `production/gates.py`: `complete` vs `passed`; measured minimums (a missing measurement fails); quality vs execution vs request failures |
| No remediation | a failed QA gate → `fix.<check>.r<n>` work order with the measured findings → re-verification on the modified project, up to `max_rounds` |
| Stale QA evidence | project fingerprint recorded per measurement; release re-measures anything taken on an older build and refuses to release otherwise |
| DESIGNCRAFT disconnected | executor `designcraft` (advisory QA task in every game production) |
| 2D tools unreachable | agent work orders name the tools (VectorCraft for identity) and validate the files that come back |
| No integration safety | `production/builtins.py` `integrate`: hash-verified copies with licence sidecars; conflicting deliverables → failed; overwriting a different file → needs approval |
| No production state | `production/store.py`: atomic `production.json`, `events.jsonl`, hand-offs, work orders, lock, resume |
| Bad requests lost their reason | the executor classifies a refused request as `request` (never retried) and keeps the department's message; the planner catches it before anything runs |
| Rejected deliverables reported as done | agent submissions are validated; a fix must change the project; a deployment needs a passing check against the live URL |
