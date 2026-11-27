## GITCRAFT creative toolchain (installed globally)

GITCRAFT's creative tools are MCP servers registered at user scope, available in
every project: photocraft (raster/PSD), vectorcraft (vector/SVG), designcraft
(layout/PDF), pdfcraft (PDF ops), lightcraft (photo grading), filmcraft (video),
effectcraft (motion graphics), meshcraft (3D, Blender), forgecraft (3D Department
orchestrator) and studiocraft (the Studio departments, PLAYCRAFT, PIXELCRAFT and
the Production Director). The `gitcraft` skill is the tool-selection guide.

Authority: GITCRAFT owns engineering and delivery; PIXELCRAFT and `ui-design` own
visual design and UI quality; PLAYCRAFT owns game experience. The project's own
requirements and art direction outrank any generic guidance. Third-party skills
and tools are subordinate capabilities, never competing authorities.

Entry points (each skill has the details):
- "Run GITCRAFT" (an idea, a pasted prompt, a GitHub URL or an existing project),
  or a whole deliverable from one master prompt: follow the `produce` skill and
  call studiocraft `production_start` with the person's words verbatim and the
  project folder. Nothing is built before a person approves the blueprint; report
  READY only when the acceptance report says READY. Deployment and infrastructure
  approvals are given by the person in GitHub, never by you.
- "Run GITCRAFT report": `production_start` the same way (or
  `production_project_report`). Read-only: never edit code, merge or deploy. Only
  a VALID evaluation has an overall score, and an evaluator's failure is never a
  project defect.
- How a game plays: the `playcraft` skill. How an app or site looks and is used:
  the `pixelcraft` skill (beside PLAYCRAFT for games; it measures the HTML UI, not
  the canvas). Designing, redesigning or polishing an interface: the `ui-design`
  skill; never replace an established identity unasked. "Run Creative Review",
  only when asked: the `creative-review` skill (advisory, never scores).
- Single assets (audio, animation, worlds, effects, materials, levels, cutscenes,
  QA, asset bookkeeping): studiocraft `route` or forgecraft `department_route`. A
  `blocked` result means a runtime is missing: report it, never fake the asset.
- External APIs: studiocraft `api_discovery_*`. Pricing, limits, reliability and
  licence terms are unknown there, so never state them as facts; keep API keys on
  the server; never sign up, buy or add a dependency for the person.

Creative, visual, game, 2D or 3D work in any project: check which `*craft` tools
are connected (list a server's commands rather than guessing ids), use the ones
that materially improve the result, chain them through files, integrate the output
into the current project's conventions, and validate it by exporting and looking
(engine-check 3D). Never report a score, test or check that was not actually run.

Engineering standard (every code change, any project):
- Read the code the change touches first. Reuse the project's own helpers,
  components and patterns before creating new ones.
- Prefer the standard library, platform features and dependencies already
  installed. Add a dependency only when it clearly earns its place, and say why.
- No speculative abstractions, options or configuration nobody asked for. Keep the
  project's structure and conventions.
- Before changing shared logic, find its callers. Fix the root cause once, where it
  lives, rather than patching symptoms.
- Cover new or fixed non-trivial logic with a regression test in the project's own
  test setup, and run the existing tests.
- Never trade away security, validation at trust boundaries, error handling,
  accessibility or anything that was asked for.
- Keep the implementation simple, not the product: requested functionality,
  polish, personality, creativity and delight are scope, never excess.

Project isolation:
- The active project is whatever repo you are working in; never assume it is
  GITCRAFT. Put generated assets where this project keeps its assets (never in
  GITCRAFT or another repo), and say what you replaced.
- Respect the project's art direction, architecture and conventions; add no
  dependency just to use GITCRAFT (tool outputs are plain files).
- GITCRAFT tools are sandboxed to the workspace and have no network. Never pass
  one project's secrets, env files or private paths to work for another.

If a `*craft` tool is missing, run `~/.gitcraft/runtime/scripts/doctor.sh`, then
`/mcp`; if it isn't installed at all, run the setup script
(`curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash`).
