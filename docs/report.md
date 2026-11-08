# Run GITCRAFT report

One command, one project report, built from the latest analysis of **every department GITCRAFT defines**.

```
Run GITCRAFT report                                     # in a session: production_start passes it here
studiocraft production_project_report {project, refresh: quick|full|none, save: store|none}
python3 -m production project-report <folder | owner/repo | owner--repo> [--refresh quick|full|none] [--save store|archive|none]
python3 -m production publish-reports [history/reports] <dist>   # the /reports/ site (run by the Vercel build)
tests/test_report.py                                    # 31 checks
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
| PLAYCRAFT | Game Quality History: local store + `history/playcraft` (`game_report`) | `refresh=full` only, on an existing build (`playcraft_assess`, not recorded) |
| PIXELCRAFT | `history/pixelcraft` + `$GITCRAFT_PIXELCRAFT_HISTORY` (`audit.json`) | `refresh=full` only, on an existing build (`pixelcraft_audit`, not recorded) |
| DESIGNCRAFT | `history/designcraft` | `quick`/`full`: `gamedesign.engine.assess` (read-only, not recorded) |
| TestCraft, AudioCraft, AnimCraft, WorldCraft, FXCraft, MaterialCraft, LevelCraft, CinematicCraft | their `.studio.json` records in the project and in its productions' task folders | no: they make things, and re-running them would create outputs |
| AssetCraft | the catalogue (SQLite, opened read-only) | no: a scan writes to the catalogue (`assetcraft_scan` is recommended instead) |
| 3D Department | the job store (`$GITCRAFT_3D_LIBRARY/jobs`) | no |
| Production Director | the production store (acceptance verdicts), Discovery (`maturity.assess`), the engineering standard (`standards.check`) | `quick`/`full`: Discovery and the standard |

## What a report contains

Executive summary and overall health · department scorecards · critical issues and blockers · cross-department findings ·
prioritised action plan (P0–P3) · changes since the previous report · recommended next actions · evidence and limits.
It is written as `report.json` (for tools), `report.md` and `report.html` (self-contained, phone-first, light/dark).

## Rules

- **Read-only.** Nothing is written inside the project. A report folder inside it is refused. Nothing is built,
  committed, merged or deployed. PLAYCRAFT and PIXELCRAFT are refreshed only against a build folder that already exists.
  Refreshed results are not recorded in the departments' histories.
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
