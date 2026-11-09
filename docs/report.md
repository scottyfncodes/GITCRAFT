# Run GITCRAFT report — the Production Report

One command, one project report, built from the latest analysis of **every department GITCRAFT defines**. Since report 2.0
every production run also ends with one (see *Production Report* below), so each run has a visual report beside its acceptance report.

```
Run GITCRAFT report                                     # in a session: production_start passes it here
studiocraft production_project_report {project, refresh: quick|full|none, save: store|none}
python3 -m production project-report <folder | owner/repo | owner--repo> [--refresh quick|full|none] [--save store|archive|none]
python3 -m production publish-reports [history/reports] <dist>   # the /reports/ site (run by the Vercel build)
tests/test_report.py                                    # 59 checks
```

## Why it is a reader, not a new system

Before this, GITCRAFT already had reports: one per department (PLAYCRAFT's Game Quality History, PIXELCRAFT's audits,
DESIGNCRAFT's assessments, TestCraft's HTML reports, AssetCraft's licence report) and the Production Director's
*acceptance* report for each production. Nothing combined them for a project. `production/project_report.py` adds only
that combining layer. It reads each department's results where the department already keeps them and re-implements
no analysis. The department list is read from the code: the Studio manifests (`studio/departments/*/manifest.json`),
DESIGNCRAFT (`gamedesign/`), the 3D Department (`gitcraft3d/`) and the Production Director. A new Studio department
appears in the report automatically.

| Department | Read from | Refreshed by the report |
|---|---|---|
| PLAYCRAFT | Game Quality History: local store + `history/playcraft` (`game_report`) | `refresh=full` only, on an existing build (`playcraft_assess`, not recorded). The department is then scored from that measurement, labelled "measured for this report, not recorded in the Game Quality History"; a delta against an earlier report only under the same rubric and PLAYCRAFT method |
| PIXELCRAFT | `history/pixelcraft` + `$GITCRAFT_PIXELCRAFT_HISTORY` (`audit.json`) | `refresh=full` only, on an existing build (`pixelcraft_audit`, not recorded) |
| DESIGNCRAFT | `history/designcraft` | `quick`/`full`: `gamedesign.engine.assess` (read-only, not recorded) |
| TestCraft | its `.studio.json` records in the project and in its productions' task folders | `refresh=full` only: `testcraft_smoke` on an existing build folder, output in the report's run folder |
| AudioCraft, AnimCraft, WorldCraft, FXCraft, MaterialCraft, LevelCraft, CinematicCraft | their `.studio.json` records in the project and in its productions' task folders | no: they make things, and re-running them would create outputs |
| AssetCraft | the catalogue (SQLite, opened read-only) | `refresh=full` only: `assetcraft_scan` + `assetcraft_license_report` into a **private** catalogue in the report's run folder (the shared catalogue and the project are never written); scored from it |
| 3D Department | the job store (`$GITCRAFT_3D_LIBRARY/jobs`) | no |
| Production Director | the production store (acceptance verdicts), Discovery (`maturity.assess`), the engineering standard (`standards.check`) | `quick`/`full`: Discovery and the standard |

## What a report contains

Executive summary and overall health · department scorecards · critical issues and blockers · cross-department findings ·
prioritised action plan (P0–P3) · changes since the previous report · recommended next actions · evidence and limits.
It is written as `report.json` (for tools), `report.md` and `report.html` (self-contained, phone-first, light/dark).

## Rules

- **Read-only.** Nothing is written inside the project. A report folder inside it is refused. Nothing is built,
  committed, merged or deployed. PLAYCRAFT, PIXELCRAFT and TestCraft are refreshed only against a build folder that already
  exists (no build: Not Evaluated, with how to build). Refreshed results are not recorded in the departments' histories, and
  every refresh writes only into the report's run folder.
- **Reach.** The departments a report runs get the session's roots plus exactly the project being reported on and the
  report's run folder (`_dept_env`), so a project cloned beside the GITCRAFT checkout can be reported on without widening
  anything else: other repositories stay outside, as in every session (`docs/security.md`).
- **No silent failures.** A refresh that does not produce a result says why: the department's own error (e.g.
  `GITCRAFT policy: … outside the workspace roots`), its failing checks, or the install command for a missing runtime. Never
  just "failed".
- **Never manufactured.** A department with no results has status *No data* and no score. The report gives the command
  that would produce its results. A missing runtime is *Unavailable*, with its reason. Every finding keeps its
  department's evidence level: **verified** (measured by a tool, or a fact parsed from source), **observed** (seen in
  play or simulated) or **inferred** (a judgement, to be confirmed). Whatever was not refreshed is listed with the reason.
- **Health** is the mean of the department scores that were actually measured: PLAYCRAFT, PIXELCRAFT, DESIGNCRAFT, the
  TestCraft check pass rate, and the share of a run production's acceptance criteria that passed. It is shown with its
  coverage (measured / applicable) and a confidence level, which drops when coverage is low or a result is stale. A P0
  blocker makes the band *blocked* whatever the score.
- **Stale** means older than 14 days, measured on a different commit than the project's HEAD, or older than newer
  commits recorded on main.
- **Unverified** means the project is not checked out where the report runs, so the analysed commit could not be
  compared with the current one. It is never reported as current; it lowers confidence like a stale result.
- **Reconciliation.** Findings are grouped into problem areas (text, touch, accessibility, performance, difficulty,
  progression, …), first by the words of their title, then by their department's own category. One area flagged by several
  departments becomes a single action and moves up one priority. A large disagreement between DESIGNCRAFT and PLAYCRAFT
  on the same category (progression, difficulty, variety) is reported as a conflict. So is PLAYCRAFT scoring mobile high
  while PIXELCRAFT reports major mobile UI problems. Stale inputs and blocked productions are listed as dependencies.
  Applicable departments with no data are listed as gaps.
- **Priorities.** P0: a critical finding or blocker with measured evidence. P1: a measured major finding, a refresh of
  stale scores, or an area several departments flag. P2: an inferred major finding, a measured minor one, or a gap.
  P3: everything else.
- **Comparable.** Reports go to `$GITCRAFT_REPORTS` (default `<first root>/gitcraft-out/reports`), in
  `<project>/<UTC stamp>/`, and are never overwritten. Each one names the department run ids it used. The next report
  says whether a department changed because it was re-measured, or because the method changed on the same run. To keep
  a report (cloud containers are ephemeral), use `--save archive`, which writes to `history/reports/` (committed,
  append-only). The site publishes every archived report at `/reports/`.

## Production Report (report 2.0)

The same report, extended so every run has a polished, comparable record. Nothing here is a parallel system:
`production/project_report.py` still gathers, reconciles and saves; `production/scoring.py` adds the rubrics.

**Every run.** `engine.run` ends with `engine.production_report(prod)`: `project_report.generate(<project>, refresh="none")`
(it reads what the departments recorded and re-measures nothing), saved to the report store outside the project. The
paths are on the production (`production_report`), in `production_status` / `production_run` results, and in `REPORT.md`.
A report that cannot be made is recorded with its reason and never fails the run. `GITCRAFT_PRODUCTION_REPORT=0` turns it off.

**What it shows.** Identity (project, run date, release/version from `package.json` or `git describe`, commit with its
source, production), the Director's verdict, an executive summary, the three highest-impact next actions, every
applicable department's 0–100 score with its rubric, evidence, criteria, previous score and delta, trend charts,
release gates and approvals, major findings, regressions, unresolved blockers (with the report they first appeared in),
then the existing reconciliation, P0–P3 plan, changes, scoring method and evidence limits. The HTML is self-contained
(no script, no external font), phone-first, light and dark; `report.json` and `report.md` sit beside it to download.

**Department rubrics** (`scoring.RUBRICS`, each versioned):

| Department | Score | Weight | Source |
|---|---|---|---|
| PLAYCRAFT | Gameplay quality | 25 | its overall score (Game Quality History) |
| PIXELCRAFT | Visual quality and usability | 20 | its audit score (mean over audited UIs) |
| DESIGNCRAFT | Game design | 15 | its 100-point design score |
| TestCraft | Automated QA | 15 | passed checks ÷ all checks |
| Production Director | Engineering standard | 15 | ok/accepted 1, advisory 0.5, review/failed 0, over applicable checks |
| AssetCraft | Asset licensing | 5 | assets with a known licence ÷ catalogued assets |
| 3D Department | 3D jobs succeeded | 5 | succeeded ÷ finished jobs (only when it worked on the project) |
| Maker departments | Output checks passed | 5 | passed ÷ all output checks (only when they made something) |

- **Not Evaluated**: the department applies but has no measured result. No score, no weight, the reason and the command
  that would produce one. Nothing is ever estimated.
- **Overall** (`gitcraft-score/2`): weighted mean of the evaluated departments only. **Coverage** (evaluated weight ÷
  applicable weight) and confidence sit beside it and are never folded into it. A measured P0 makes the band *blocked*.
- **Gates are not scores.** Acceptance criteria and the Director's verdict (READY / NOT READY / INCOMPLETE) are pass/fail
  states shown in their own panel. They were part of the plain mean before 2.0; they are not part of any score now.
- **Comparisons.** A previous score and delta are shown only when the rubric version and the department's own method are
  unchanged, and only when today's measurement is not older than the previous one (a recorded run read after a
  re-analysis is not a regression). Reports made before 2.0 (`mean/1`) keep their recorded number; the overall delta
  across the method change is shown as *not comparable*, and trend lines break where the method changed.
- **Impact and effort** for the top three actions: impact follows the priority rule (P0/P1 high, P2 medium, P3 low);
  effort is the owning department's own estimate (PLAYCRAFT effort, PIXELCRAFT cost, DESIGNCRAFT complexity) or
  *not estimated*.
- **Regressions** are measured only: a comparable score that fell on a new measurement, PLAYCRAFT's recurring
  regressions, and critical/major measured findings that are new since the previous report.
