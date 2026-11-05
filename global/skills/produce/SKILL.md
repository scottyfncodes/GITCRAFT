---
name: produce
description: Turn one master prompt into a finished, verified deliverable with GITCRAFT's Production Director (studiocraft production_* tools). Use when the person asks for a whole game, app, site or asset pack in one request ("build a polished mobile-first game with sound, levels and deployment", "make an original platformer", "create a landing page with a brand", "ship a sound pack") or says "run the production", "produce this", "continue the production". It interprets the prompt, discovers the project and what can run here, plans every department (audio, levels, effects, materials, worlds, 3D, testing, PLAYCRAFT, PIXELCRAFT, DESIGNCRAFT, licences) in dependency order with parallel waves, gates every result, turns failures into fix work orders, re-verifies the modified build and writes the acceptance report. Not for a single asset (use the gitcraft skill and the department tool directly).
---

# One master prompt → a verified production

The person should not have to pick tools, order them, or coordinate departments. The Production
Director does that; you do the work only you can do (code, wiring assets in, the 2D ArtCraft tools)
when it hands you a work order, and you never claim anything it did not measure.

## The loop

1. **Plan** — `production_plan {prompt: <the whole master prompt, verbatim>, project: <the repo folder, if one exists>}`.
   Read the returned spec: deliverable, platform, genres, assets, quality bar, acceptance criteria,
   `assumptions`, `questions`, `blocked_up_front`, `problems`.
   - Ask the person **only** the questions marked `essential` (usually none). Non-essential ones have a
     safe default; mention it in your summary instead of asking.
   - If the interpretation is wrong (wrong genre, a feature missed), plan again with `overrides`
     (deep-merged into the spec), e.g. `{"assets": {"levels": {"kind": "dungeon", "count": 4, "by_levelcraft": true}}}`,
     `{"quality": {"playcraft_min": 60}}`, `{"extra_tasks": [{id, department, action, params, depends_on, ship}]}`,
     `{"skip_tasks": ["qa.perf"]}`. A plan with `problems` does not run.
   - Tell the person in a few lines what will be made, by which departments, and what is blocked here.
2. **Run** — `production_run {production}`. It runs every ready task on parallel workers and stops when
   the deliverable is ready, or when it waits on you (`awaiting_agent`) or on a person (`needs_approval`).
3. **Work orders** — for each task in `awaiting_agent`, open its `WORK_ORDER.md` (path in `production_status`).
   It says what to make, with which tools, the inputs (the hand-off: upstream files with roles and hashes;
   for the build, every integrated asset), the findings to fix, and the expected outputs.
   - Do the work in the project, following its conventions. Use every integrated asset.
   - Commit on a feature branch in the project as you go (never the default branch).
   - `production_submit {production, task, files: [absolute paths], notes}`. The submission is validated
     (files exist, open as their format, expected keys; a fix must actually change the project). A rejected
     submission keeps the work order open: read the reason, fix, submit again. An accepted one continues the run.
4. **Quality gates** — a failed QA gate (TestCraft, PLAYCRAFT, PIXELCRAFT, asset integrity, licences)
   becomes a `fix.<check>.r<n>` work order with the measured findings, then the same check re-runs on the
   modified project. Fix the cause the findings name; never weaken a gate, edit a measurement, or
   skip a check to get green. After `quality.max_rounds` the gate stays failed and the report says NOT READY:
   tell the person what remains and why.
5. **Approvals** — `needs_approval` (deployment, replacing an existing asset) is the person's decision.
   Ask them; call `production_approve` only with their answer. A deployment counts as live only with
   `evidence`: a passing check record that ran against the live URL. Without it, say "deployed, not verified".
6. **Report** — `production_report {production}`: every criterion with its measured evidence and the verdict.
   Report exactly that: READY only when the report says READY. Give the person the project path, the
   verdict, the scores, what was fixed, and anything blocked with its install command.

## Resuming

Productions persist (`production_list`). After an interruption, `production_run` again: passed work is kept
(while its outputs still match their hashes), interrupted tasks run again, and QA evidence measured before the
project changed is re-measured before release. Never start a new production for work that already has one.

## Rules

- One master prompt, verbatim, into `production_plan`; don't pre-chop it into tool calls.
- Don't run departments by hand for work the production covers; add an `extra_tasks` entry instead, so it is
  gated, recorded and integrated like everything else.
- Never write generated assets into another project; integration copies only into this production's project
  and never overwrites a different existing file without approval.
- No paid services, no merges, no production deploys without the person's explicit approval.
