# GITCRAFT reports archive

Reports written by `Run GITCRAFT report` with `--save archive` (`production/project_report.py`, `docs/report.md`), one
folder per run: `<project>/<UTC stamp>/report.{json,md,html}`. `index.jsonl` has one line per report. The archive is
**append-only**, like the other archives in `history/`: never rewrite or delete a report. A later run is a new folder,
and the next report compares against the latest. The site publishes every report here at `/reports/`.
