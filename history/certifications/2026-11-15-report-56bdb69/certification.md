# Certification: Run GITCRAFT report (scoring integrity, end to end)

**Verdict: PASS** · 2026-11-15T18:14:48Z · commit `56bdb6921eee`

Real evaluators on a real reference game, through `scripts/mcp.sh studiocraft` (guard + sandbox). Nothing is stubbed. Produced by `tests/certify_report.py`.

| Scenario | Required behaviour | Result | State | Overall score | Seconds |
|---|---|---|---|---|---|
| healthy | complete, evidence-backed evaluation | **PASS** | VALID | 81.0 | 111 |
| broken evaluator | identify the evaluator failure, not an application failure | **PASS** | INVALID | none | 3 |
| repeat | consistent results under equivalent conditions | **PASS** | VALID | 81.0 | 111 |
| recovery | normal evaluation after the dependency is restored | **PASS** | VALID | 81.0 | — |
| known application defect | detect the defect and attribute it to the application | **PASS** | VALID | 63.7 | 109 |
| partial evaluation | keep the valid findings, mark coverage incomplete, no overall score | **PASS** | PARTIAL | none | 6 |
| unavailable evaluator runtime | report an invalid evaluation, with no misleading score | **PASS** | INVALID | none | 0 |
| unavailable evaluator runtime (through the launcher) | no score: the tool refuses, or reports INVALID | **PASS** | — | none | 0 |

## healthy: PASS

`scripts/mcp.sh studiocraft → tools/call production_project_report {project: reference, refresh: full}`

- PASS — the report was produced through the sandboxed launcher
- PASS — evaluation VALID, with an overall score
- PASS — every mandatory evaluator measured this build (a score each, none stale)
- PASS — PLAYCRAFT really played the build (desktop and phone), not source reading
- PASS — evidence exists on disk for each measurement (PLAYCRAFT, PIXELCRAFT, TestCraft result files in the report's folder)
- PASS — no evaluator failed, and the dependency probe ran green
- PASS — a department with no evidence (DESIGNCRAFT: 0% of its rubric) is Not Evaluated, never a 0 in the score
- PASS — the report changed nothing in the project

What the report said: _Evaluation **VALID**: BLIP scores **81.0/100 (83% measured)** (blocked, medium confidence)._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 1 |
| playcraft | current | 61 | — | 35 |
| pixelcraft | refreshed | 82.7 | — | 6 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | current | 100.0 | — | 0 |

## broken evaluator: PASS

`scripts/mcp.sh studiocraft → tools/call production_project_report {project: reference, refresh: full}  [env CHROMIUM_PATH=/tmp/gc-cert-q3o5bll7/bin/chromium]`

- PASS — the report was produced
- PASS — evaluation INVALID
- PASS — NO overall score anywhere (health record, tool summary, summary lines, Markdown)
- PASS — each browser evaluator is reported as an evaluator failure with the real launch error
- PASS — nothing is held against the game: no finding, P0 or P1 from the broken evaluators; the band is not 'at risk'
- PASS — the report says so in words (failure of the evaluator, not a finding about the project)
- PASS — the dependency probe independently found the broken browser
- PASS — what could still be measured is kept and identical to the healthy run (engineering standard)

What the report said: _Evaluation **INVALID**: BLIP has **no overall score**. A required evaluator failed, so the project could not be evaluated: there is no overall score, and nothing here says the project is defective._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 1 |
| playcraft | evaluator_failed | — | evaluator_failed | 0 |
| pixelcraft | evaluator_failed | — | evaluator_failed | 0 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | evaluator_failed | — | evaluator_failed | 0 |

Evaluator failures reported:
- PLAYCRAFT: playcraft_assess failed: browser (/home/user/GITCRAFT/studio/departments/playcraft/playprobe.mjs): browserType.launch: Failed to launch: Error: spawn /tmp/gc-cert-q3o5bll7/bin/chromium EACCES
- PIXELCRAFT: pixelcraft_audit failed: browser (/home/user/GITCRAFT/studio/departments/pixelcraft/probe.mjs): browserType.launch: Failed to launch: Error: spawn /tmp/gc-cert-q3o5bll7/bin/chromium EACCES
- TestCraft: testcraft_smoke failed: browser (testcraft.mjs): browserType.launch: Failed to launch: Error: spawn /tmp/gc-cert-q3o5bll7/bin/chromium EACCES

## repeat: PASS

`scripts/mcp.sh studiocraft → tools/call production_project_report {project: reference, refresh: full}`

- PASS — the second run was produced
- PASS — same evaluation state
- PASS — identical department scores (production, PLAYCRAFT, PIXELCRAFT, TestCraft) and identical overall score
- PASS — identical findings

What the report said: _Evaluation **VALID**: BLIP scores **81.0/100 (83% measured)** (blocked, medium confidence)._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 1 |
| playcraft | current | 61 | — | 35 |
| pixelcraft | refreshed | 82.7 | — | 6 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | current | 100.0 | — | 0 |

## recovery: PASS

`the repeat run above, made after the broken-evaluator run`

- PASS — the run after the broken one (same project, same report store) is VALID again
- PASS — with the score it had before the failure
- PASS — the failure left no trace in it: no evaluator failure, no change claimed against the INVALID report

What the report said: _Evaluation **VALID**: BLIP scores **81.0/100 (83% measured)** (blocked, medium confidence)._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 1 |
| playcraft | current | 61 | — | 35 |
| pixelcraft | refreshed | 82.7 | — | 6 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | current | 100.0 | — | 0 |

## known application defect: PASS

`scripts/mcp.sh studiocraft → tools/call production_project_report {project: reference-defect, refresh: full}`

- PASS — the report was produced
- PASS — evaluation VALID: the evaluators worked, so the result is about the game
- PASS — the overall score is clearly lower than the healthy game's (at least 10 points)
- PASS — the missing file is found by measurement and named (sprites/hero.png), by more than one department
- PASS — the start-up crash is found by playing: the game does not react to input (a measured PLAYCRAFT finding)
- PASS — PLAYCRAFT's and TestCraft's scores fell against the healthy game
- PASS — the defects are blockers or P1 for the project

What the report said: _Evaluation **VALID**: BLIP scores **63.7/100 (83% measured)** (blocked, medium confidence)._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 2 |
| playcraft | current | 47 | — | 40 |
| pixelcraft | refreshed | 82.7 | — | 6 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | current | 50.0 | — | 9 |

## partial evaluation: PASS

`scripts/mcp.sh studiocraft → tools/call production_project_report {project: reference-quick, refresh: quick}`

- PASS — the report was produced
- PASS — evaluation PARTIAL
- PASS — NO overall score anywhere
- PASS — what was measured is kept with its own score (engineering standard and TestCraft's smoke test)
- PASS — the evaluators that did not run are named as not run (not failed, not 0), with how to run them
- PASS — coverage is stated

What the report said: _Evaluation **PARTIAL**: BLIP has **no overall score**. Coverage is incomplete: the department scores and findings below are real measurements, but there is no overall score._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 1 |
| playcraft | no_data | — | not_run | 0 |
| pixelcraft | no_data | — | not_run | 0 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | current | 100.0 | — | 0 |
| assetcraft | no_data | — | not_run | 0 |

## unavailable evaluator runtime: PASS

`GITCRAFT_STUDIO_HOME=no-studio-runtime python3 -m production project-report reference --refresh full --json --require-valid`

- PASS — the report was produced
- PASS — evaluation INVALID, and the gate refuses it (exit code 3)
- PASS — NO overall score anywhere
- PASS — every Studio evaluator is an evaluator failure that names the missing runtime and its install command
- PASS — nothing is held against the game

What the report said: _Evaluation **INVALID**: BLIP has **no overall score**. A required evaluator failed, so the project could not be evaluated: there is no overall score, and nothing here says the project is defective._

| Department | Status | Score | Why not scored | Findings |
|---|---|---|---|---|
| production | refreshed | 85.7 | — | 1 |
| playcraft | evaluator_failed | — | evaluator_failed | 0 |
| pixelcraft | evaluator_failed | — | evaluator_failed | 0 |
| designcraft | refreshed | — | insufficient_evidence | 0 |
| testcraft | evaluator_failed | — | evaluator_failed | 0 |
| assetcraft | evaluator_failed | — | evaluator_failed | 0 |

Evaluator failures reported:
- PLAYCRAFT: the Studio runtime is not installed (/tmp/gc-cert-q3o5bll7/no-studio-runtime/venv/bin/python); scripts/install-studio.sh
- PIXELCRAFT: the Studio runtime is not installed (/tmp/gc-cert-q3o5bll7/no-studio-runtime/venv/bin/python); scripts/install-studio.sh
- TestCraft: the Studio runtime is not installed (/tmp/gc-cert-q3o5bll7/no-studio-runtime/venv/bin/python); scripts/install-studio.sh
- AssetCraft: the Studio runtime is not installed (/tmp/gc-cert-q3o5bll7/no-studio-runtime/venv/bin/python); scripts/install-studio.sh

## unavailable evaluator runtime (through the launcher): PASS

`scripts/mcp.sh studiocraft → tools/call production_project_report {project: reference, refresh: full}  [env GITCRAFT_STUDIO_HOME=/tmp/gc-cert-q3o5bll7/no-studio-runtime]`

- PASS — the tool either refuses with the install instruction or returns an INVALID report with no score

Tool answer: `RuntimeError: The Studio runtime (~/.gitcraft/studio: numpy, Pillow, Node packages) isn't installed yet, so only this status tool is listed. Install it with `~/.gitcraft/runtime/scripts/install.sh studiocraft` (about a minute; the SessionStart hook also does it in the background). When it finishes, this server announces its full tool list (tools/list_changed) and this session sees the department t`
