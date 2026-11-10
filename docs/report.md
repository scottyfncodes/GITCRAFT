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
| TestCraft | its `.studio.json` records in the project and in its productions' task folders (the latest run of each check) | `quick`: `testcraft_smoke` on phone, the cheap check; `full`: `testcraft_smoke` on its default viewports; both only on an existing build folder, output in the report's run folder. A visual-diff record without changed regions is diffed again from its recorded images into the run folder |
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
  blocker makes the band *blocked* whatever the score. (The current weighting is under *Production Report* below.)
- **Stale** means older than 14 days, measured on a different commit than the project's HEAD, or older than newer
  commits recorded on main. Every `.studio.json` records what it measured (`measured`: the path, its content hash, the
  repository's commit, its date and whether the tree had local changes). A record measured at another commit is labelled
  **Stale (measured at `<sha>`, `<date>`)**; a record made before commits were recorded and dated before the project's latest
  commit is **Stale (measured at an unrecorded commit, `<date>`)**. A stale result has low confidence, its findings are capped
  at P2 and kept out of the Top 3 and the major findings, and the department's *Next* names the call that re-measures it
  (with the build command first when there is no build). A record the report itself just measured is never stale.
- **Environment-limited / UNVERIFIED** means the measurement describes the machine, not the project: a frame rate or frame
  time drawn by a software rasteriser (SwiftShader, llvmpipe; TestCraft perf records the WebGL renderer via
  `WEBGL_debug_renderer_info`), or a console error from a request the sandbox blocked (proxy refusal, the harness's block, no
  network). It is reported as *info*, never as a failure, and is left out of the TestCraft score. Only a hardware-rendered
  run (`GITCRAFT_WEBGL=hardware`, or a real phone) can fail a performance gate.
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
- **Runnable anywhere.** Reports go to `$GITCRAFT_REPORTS`, default `$GITCRAFT_HOME/reports` (`~/.gitcraft/reports`):
  never a workspace root, because in a cloud session the first root *is* the project and a report there would be refused
  by the read-only rule. Nobody has to set an env var to report. An explicit folder (`$GITCRAFT_REPORTS`, `out_dir`) inside
  the project is still refused. Reports made under the old default (`<root>/gitcraft-out/reports`) are still read for
  comparison. The studiocraft sandbox may write `$GITCRAFT_HOME/reports` (`scripts/mcp.sh`).
- **Comparable.** Reports go
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
| Maker departments | Asset validity (not scored) | 0 | files that open and validate ÷ files made, shown as *N/N files valid* (only when they made something) |

- **Not Evaluated**: the department applies but has no measured result. No score, no weight, the reason and the command
  that would produce one. Nothing is ever estimated.
- **Overall** (`gitcraft-score/3`): the weighted mean of the evaluated departments only, each weight scaled by that
  department's own confidence (high ×1, medium ×0.75, low ×0.5), so a low-confidence result (DESIGNCRAFT 31 at low
  confidence) cannot carry its full weight; the basis gives the score at full weight too. **Coverage** (evaluated nominal
  weight ÷ applicable weight) is part of the headline at the same prominence, e.g. **72.5 (57% measured)**, and is never
  folded into the number. Below 70 % coverage the band is at best **provisional** (a *healthy* or *needs attention* score
  reads *provisional*; *at risk* stays). A measured P0 makes the band *blocked*. `gitcraft-score/2` reports (plain weighted
  mean, makers included) are not compared across the change.
- **File validity is not quality.** AudioCraft, AnimCraft, CinematicCraft, FXCraft and the other makers are shown as
  *Asset validity: N/N files valid* and never averaged with gameplay, UI or design quality.
- **Findings a person can act on.** Every finding of every department carries a human title ("Phone frame rate below 30
  FPS", never "testcraft perf failed"), the measured value against its threshold, a **Do:** line and its evidence path
  (`project_report.finding_problems` is the contract; `tests/test_report_trust.py` rejects findings without them). TestCraft
  writes its own reading of each check (`studio/departments/testcraft/findings.py`, with its effort estimate): console errors
  name the failing request (URL, method, failure; `requestfailed` and responses ≥ 400 are recorded), a visual diff links its
  diff image and the changed regions with *Do: accept as new baseline if intended, otherwise fix*. Only the latest run of each
  check counts (department, action, viewports or compared image), and findings are de-duplicated by (department, check,
  failed criterion) before ranking, so the Top 3 holds distinct items.
- **Missing files and stubs.** A root-absolute reference (`/src/x.ts`) is resolved against every plausible serve root of
  its page (the Vite configs whose root contains it, the page's own folder, the project root, each with `public/`, and the
  path without its first segment, as a kit or sub-path build serves it); it is missing only when no root has it. A broken
  reference in a page that is not the shipped entry is minor. Stubs come from code only (`raise NotImplementedError`,
  `throw new Error("not implemented")`, `pass`-only functions, TODO/FIXME comments, open README checkboxes), never words
  inside a string literal or a document.
- **refresh=quick** re-runs Discovery, the engineering standard and DESIGNCRAFT, and smoke-tests an existing build with
  TestCraft. With no build it says which command builds the project (`vercel.json` buildCommand or `npm run build`); the
  summary names the exact `refresh: "full"` call that also plays (PLAYCRAFT) and audits (PIXELCRAFT) the build.
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
