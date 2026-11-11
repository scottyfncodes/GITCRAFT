## GITCRAFT creative toolchain (installed globally)

GITCRAFT's creative tools are MCP servers registered at user scope, so they are
available in every project, whether or not the GITCRAFT repo is attached:
photocraft (raster/PSD), vectorcraft (vector/SVG), designcraft (layout/PDF),
pdfcraft (PDF ops), lightcraft (photo grading), filmcraft (video), effectcraft
(motion graphics), meshcraft (3D, Blender), forgecraft (3D Department
orchestrator) and studiocraft (the Studio departments: audio, animation and
rigging, terrain/skies/oceans, VFX, PBR materials, levels/tilemaps,
cinematics, browser QA, asset catalogue, PLAYCRAFT: game design and
gameplay quality, and PIXELCRAFT: visual quality and UI/UX). The `gitcraft` skill has the full tool-selection guide.

"Run GITCRAFT" (with an idea, a pasted prompt, a GitHub URL, or in an existing
project): follow the `produce` skill and call studiocraft `production_start` with
the person's words verbatim and the project folder. It detects new vs existing
and the project's maturity (partial, nearly complete, finished; game/app/site),
picks the workflow, names the assignment (a repair, a redesign, a gameplay pass,
an audit and a rebuild are different jobs), preserves existing work, and opens the
Decision Room. Assets alone come back as `direct` steps for the departments. A
repository URL that isn't cloned yet returns the clone command to run first.

"Run GITCRAFT report": call `production_start` the same way (or studiocraft
`production_project_report`). It reads the latest results of every department
for the project, refreshes the read-only analyses, reconciles them, and saves a
timestamped report (health, scorecards, blockers, P0–P3 plan, changes since the
last report). It is read-only: never edit code, merge or deploy as part of it.

For a WHOLE deliverable from one master prompt (a game, app, site or asset
pack: "build a polished mobile-first game with sound, levels and deployment"),
follow the `produce` skill: pass the prompt verbatim to studiocraft
`production_plan` (read-only Discovery + the Decision Room), get the person's
approval of the blueprint (`production_decide`), then `production_run`.
Ideas can be saved and researched first (`production_idea`, `production_recon`).
Every app gets an approved icon (App Icon Studio), the quiet "by HaveAnApp"
credit and a proportionate engineering standard (docs/app-standards.md). The Production Director picks the
departments, orders and parallelises them, gates every result, turns failed
gates into fix work orders and re-verifies, and writes the acceptance report.
You do its work orders (code, wiring assets, the 2D tools) and submit them
with `production_submit`; report READY only when its report says READY, and
leave approvals (deployment, replacing assets) to the person.

Before implementing creative, visual, design, game-development, 2D, 3D,
modelling, animation, illustration, texture, rendering or asset-generation work
in ANY project:

1. Inspect what GITCRAFT offers here: which `*craft` MCP tools are connected
   (list a server's commands rather than guessing ids).
2. Identify which tools are relevant to this task; do not run every tool.
3. Use them when they materially improve quality, speed or capability.
4. Chain tools by handing files between them (e.g. vectorcraft SVG/PNG →
   photocraft → designcraft; meshcraft previews → filmcraft/designcraft).
5. Integrate the results into the CURRENT project, following its conventions.
6. Validate the output (export and look at it; engine-check 3D) and keep the
   project's existing functionality working.

For game audio, animation, worlds, effects, materials, levels, cutscenes, QA
or asset bookkeeping, studiocraft's `route` (or forgecraft's
`department_route`) names the department and action; a `blocked` result
means a runtime is missing, so report it instead of faking the asset.

For how a game PLAYS (game feel, controls, touch, onboarding, progression,
difficulty, replayability) use PLAYCRAFT: "Run PLAYCRAFT on this game" and
"Run the full GITCRAFT + PLAYCRAFT pass" follow the `playcraft` skill
(studiocraft `playcraft_pass` / `playcraft_full_pass`, then `playcraft_verify`).
It plays the built game, scores 10 categories with evidence levels and ranks
improvements; never report a score or test that was not actually run. Every
run is kept in the Game Quality History (`playcraft_history`: one game's
progress or the whole portfolio); only measured changes between commits count
as improvement, and a deployment is recorded only with evidence.

For how an app or site LOOKS and how efficiently it is used (spacing, layout,
typography, buttons and touch targets, mobile ergonomics, safe areas, states,
accessibility, user journeys) use PIXELCRAFT: "Run PIXELCRAFT on this app"
follows the `pixelcraft` skill (studiocraft `pixelcraft_audit`, then
`pixelcraft_verify` after fixes). It audits the rendered app at iPhone 17,
iPhone 13 and desktop (plus narrow, tablet, landscape), scores Visual Quality,
Usability and Consistency with evidence and coverage, and never edits the app.
For games, run it beside PLAYCRAFT (it measures the HTML UI, not the canvas).

Before designing, redesigning or polishing an interface (screens, menus, HUD,
"make it look good", a generic-looking UI), follow the `ui-design` skill:
Explore distinct directions only when there is none, Build on the project's own
tokens, Audit the rendered result with PIXELCRAFT (incl. its advisory generic-
design tells), Refine what was found, then stop. The project's own art
direction always wins; never replace an established identity unasked.

"Run Creative Review" (only when the person asks for one): follow the
`creative-review` skill. An advisory, evidence-cited judgement of the rendered
product against its vision (studiocraft `production_vision`, then
`production_creative` pack → your review → submit), reusing existing PLAYCRAFT
and PIXELCRAFT captures. It never scores and never changes a department score,
gate, verdict or plan; fun is only ever a playtest hypothesis.

Project isolation:
- The active project is whatever repo you are working in. Never assume it is
  GITCRAFT, and never write generated assets into GITCRAFT or any other repo.
- Put outputs where this project keeps its assets; never overwrite an existing
  asset without a reason, and say what you replaced.
- Respect the project's art direction (palette, style, existing assets),
  architecture and conventions; derive briefs from them.
- Add no dependencies to the project just to use GITCRAFT; tool outputs are
  plain files (PNG, SVG, PDF, MP4, GLB…).
- GITCRAFT tools are sandboxed to the workspace and have no network. Never pass
  one project's secrets, env files or private paths to work for another.

If a `*craft` tool is missing, run `~/.gitcraft/runtime/scripts/doctor.sh`, then
`/mcp` to reconnect; if it isn't installed at all, run the setup script
(`curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash`).
