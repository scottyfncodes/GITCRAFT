# Certifications

End-to-end proof that a part of GITCRAFT does its job with the real tools, not with stand-ins. One folder per run,
append-only like the other archives in `history/`: never rewrite or delete one; a later run is a new folder.

Each folder holds what the run produced: `certification.md` (the verdict, every scenario, every check and what the
report said), `certification.json` (the same, for tools) and `run.log` (the commands and their results as they ran).
A scenario that could not be run is **NOT VERIFIED**, and so is the verdict: nothing here certifies what was not run.

| Run | What | Verdict |
|---|---|---|
| `2026-11-15-report-56bdb69` | "Run GITCRAFT report": scoring integrity (`python3 tests/certify_report.py`) | PASS, 8 of 8 scenarios |

## 2026-11-15: why the report was certified

Before the repair, on the same reference game (`tests/fixtures/playcraft/arcade_dodge`), same machine, same commands:

| Condition | What the report said |
|---|---|
| every evaluator working | **71.8/100 (95% measured)**, with a DESIGNCRAFT **0** (0 % of its rubric tested) averaged in as a measured score |
| the shared browser unable to start | **57.1/100 (32% measured), at risk**, "at full weight the score would be **42.9**"; PLAYCRAFT, PIXELCRAFT and TestCraft listed as "No data" with "Run PLAYCRAFT on this game" as the next action |
| the Studio runtime missing | the same **57.1 / 42.9** |

The game had not changed. The number fell 15 to 29 points because evaluators broke, and the report presented it as the
game's score. After the repair the same three conditions give: VALID 81.0 (the 0 is "too little evidence", not a score),
INVALID with no score and the browser named as the fault, INVALID with no score and the install command.
