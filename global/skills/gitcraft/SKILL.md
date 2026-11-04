---
name: gitcraft
description: Choose and chain GITCRAFT's creative MCP tools (photocraft, vectorcraft, designcraft, pdfcraft, lightcraft, filmcraft, effectcraft, meshcraft, forgecraft, studiocraft) for visual, design, game-asset, 2D, 3D, audio, animation, rigging, terrain, VFX, material, level, cinematic, QA, asset-management, video or rendering work in the current project. Use before making or improving images, icons, logos, illustrations, textures, layouts, PDFs, sounds, music, voice lines, animations, levels, effects, videos, motion graphics or 3D models, or testing a web game, in any repository.
---

# Using GITCRAFT in any project

GITCRAFT's tools are user-scope MCP servers launched from `~/.gitcraft/runtime`
(not from any project). Each runs in a kernel sandbox that can read and write
only the session's workspace (the current project; in multi-repo sessions, the
folder holding them), its own state and, for the 3D tools, the shared 3D asset
library. They have no network.

## 1. Look before you build

- Read the project first: where it keeps assets (`public/`, `assets/`,
  `src/assets/`, `static/`…), its palette and fonts (CSS variables, theme files,
  brand docs), formats it already uses, and the engine or framework that will
  load the output.
- Check which tools are connected. Each server lists its commands
  (`command_list`, `list_commands`, `menu_list`, `tool_search`); describe a
  command before running it instead of guessing ids or parameters.

## 2. Pick tools by the job

| Work | Start with | Often chained with |
|---|---|---|
| Logo, icon set, UI illustration, SVG | vectorcraft | photocraft (raster variants, effects), designcraft (brand sheet) |
| Bitmap edits, textures, sprites, PSD, mockups | photocraft | vectorcraft (shapes), lightcraft (grading) |
| Poster, flyer, social card, one-pager, print PDF | designcraft | vectorcraft (art), photocraft (images), pdfcraft (merge/secure) |
| PDF merge, split, reorder, inspect, render | pdfcraft | designcraft |
| Photo batches, raw development, consistent grading | lightcraft | photocraft |
| Trailer, gameplay or turntable video | filmcraft | effectcraft (titles), meshcraft previews |
| Animated titles, motion graphics, lower thirds | effectcraft | filmcraft |
| 3D asset from a brief (props, characters, ships, islands, scenes) | forgecraft `route` → `generate` | meshcraft (templates, profiles), filmcraft/designcraft (showcase) |
| Precise 3D build with a project palette and engine profile | meshcraft `run_pipeline` | forgecraft `library_export` |
| Sound effects, ambience loops, adaptive music + MIDI, voice lines, loudness, loops, OGG/MP3 | studiocraft `audiocraft_*` | cinematiccraft (trailer music bed) |
| Rig a character, procedural clips, retarget Mixamo/BVH, mocap from video or a photo, physics, sprite sheets | studiocraft `animcraft_*` | meshcraft/forgecraft (the model), testcraft (playback) |
| Terrain/islands, heightmaps + splatmaps, scatter, caves, skyboxes, ocean normals; CC0 HDRIs and models (`worldcraft_hdri`, `worldcraft_fetch_model`: Poly Haven) | studiocraft `worldcraft_*` | materialcraft (ground textures), cinematiccraft (flyover) |
| Fire/smoke/explosion flipbooks, three.js emitters, destruction | studiocraft `fxcraft_*` | photocraft (touch-ups) |
| Seamless PBR materials, weathering, toon ramps, make an image tile; real CC0 scanned materials (`materialcraft_fetch`: Poly Haven, ambientCG) | studiocraft `materialcraft_*` | meshcraft (apply/bake) |
| Dungeons, platformer levels, overworld maps, towns (Tiled + blockout GLB) | studiocraft `levelcraft_*` | photocraft/vectorcraft (real tileset art) |
| Camera moves, storyboards, title cards, teaser assembly, gameplay capture | studiocraft `cinematiccraft_*` | filmcraft (hand edit), effectcraft (titles) |
| Smoke/gameplay/FPS/visual-regression/asset tests of a web game | studiocraft `testcraft_*` | — |
| Catalogue, duplicates, unused assets, licences/ATTRIBUTION.md, safe import | studiocraft `assetcraft_*` | every department registers its outputs |
| Not sure which department | studiocraft `route` / forgecraft `department_route` | — |

Typical projects:
- **New game:** decide 2D vs 3D from the engine; then key art, sprites or 3D
  models, textures, UI icons, a trailer.
- **Existing game:** inspect current assets first; propose specific
  improvements (consistency, resolution, missing animations) instead of
  replacing the style.
- **App redesign:** icons, illustrations, empty states, social/OG images, in the
  app's palette.
- **Marketing/showcase:** key art, store screenshots framed in designcraft, a
  short video in filmcraft/effectcraft.

Use one tool when one is enough. Chain several only when the combination is
materially better.

## 3. Hand files between tools

Tools never call each other: a hand-off is a file in the project. Export from
one (SVG, PNG, PSD, PDF, MP4, GLB) into a work folder, open it in the next.
Every hand-off's SHA-256 is logged in `~/.gitcraft/logs/audit.jsonl`.
3D assets go through `library_export` (hash-verified) into the project.

## 4. Land the result in THIS project

- Write final files where the project keeps that kind of asset, named in its
  style. Keep scratch work in a temporary folder and do not commit it.
- Never write into GITCRAFT or another repository. Never overwrite an existing
  asset unless the task calls for it; say what was replaced.
- Wire the asset in the way the project already does (imports, manifests,
  `<img>`/CSS, loaders). Add no new dependencies just for GITCRAFT.
- Validate: render or export and look at the file; run the project's build or
  tests; for 3D, run the engine check and confirm the game still loads.

## 5. When something is missing

- A tool not listed: `~/.gitcraft/runtime/scripts/doctor.sh`, then `/mcp`.
- Not installed: `curl -fsSL https://raw.githubusercontent.com/scottyfncodes/GITCRAFT/main/scripts/setup-env.sh | bash`, then a new session.
- A `GITCRAFT policy:` refusal means the path is outside the workspace: copy the
  input into the project rather than widening the roots.
- A 3D job `blocked` means no installed tool can honour it: report the reason
  and alternatives. Never substitute a 2D image for a 3D model.
- A studiocraft action `blocked` names the missing runtime and its install
  command (e.g. Blender for animcraft); report it rather than improvising.
  `studio_status` shows which actions can run on this machine.
- Studio outputs default to `<workspace>/gitcraft-out/<department>/`; move or
  `assetcraft_integrate` them into the project. Each run writes a
  `.studio.json` record (tools, licences, hashes) next to its outputs.
