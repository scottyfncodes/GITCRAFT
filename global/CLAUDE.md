## GITCRAFT creative toolchain (installed globally)

GITCRAFT's creative tools are MCP servers registered at user scope, so they are
available in every project, whether or not the GITCRAFT repo is attached:
photocraft (raster/PSD), vectorcraft (vector/SVG), designcraft (layout/PDF),
pdfcraft (PDF ops), lightcraft (photo grading), filmcraft (video), effectcraft
(motion graphics), meshcraft (3D, Blender) and forgecraft (3D Department
orchestrator). The `gitcraft` skill has the full tool-selection guide.

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
