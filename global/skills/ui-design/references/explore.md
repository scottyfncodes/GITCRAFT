# Explore: distinct directions, chosen by a person

Only when there is no direction to follow (§0 of SKILL.md). For an existing identity, skip to Build.

## 1. Read the product before the screen

- What is it, who uses it, where and when (a phone in a cold car park at dawn; a desktop at work; a sofa at night).
  Light or dark follows that scene, not the category.
- What it must do first. Pages people use (apps, tools, games) put the real content or the game on the first screen;
  only pages that persuade get a composed opening.
- Its world: the materials, places, objects, eras and words that belong to it. Write five concrete nouns.
  A salvage game has tarred rope, sun-bleached aluminium, rust, stencilled hull numbers; a ski-patrol game has trail
  signs, radio chatter, avalanche-beacon orange, a paper map. These are where palettes, type and texture come from.
- The category's defaults (what every competitor and every unguided build does). Name them so you can avoid them.

## 2. Two or three directions that really differ

Each direction is one sentence of intent plus decisions on four axes:

| Axis | Decide |
|---|---|
| Composition | what leads the first screen, density, grid or no grid, where the eye lands first |
| Type | a display face with character from the world, a text face for reading, a figure face if numbers matter; the scale |
| Colour | 1 ground, 1–2 surfaces, 1 accent used sparingly, text and muted text; derived from the world's nouns |
| Imagery / material | photographs, drawn art, 3D renders, texture, iconography style, or none |

Any two directions share **at most one** axis. If two thumbnails look alike when you squint, change the composition,
not the colours. Each direction names its source ("enamel trail signs and topo maps", "a deck log in grease pencil").
Never "minimal", "modern", "clean" or "bold" as the source: those are outcomes, not ideas.

Avoid as a starting point (unless the brief asks): a centred hero over a gradient, three equal icon cards, an eyebrow
over every heading, Inter/Roboto/system everywhere, purple-to-blue, glass panels, glow as depth.

## 3. Render the same real screen

- One HTML file per direction (`a.html`, `b.html`, `c.html`), showing the **same** screen with the same real content
  (the actual title screen, dashboard or form, not lorem ipsum), self-contained (inline CSS, fonts as files next to it).
- Put them in `<project>/gitcraft-out/design/directions/round-1/` (ignored output, never source). Optionally a
  `directions.json`: `{"round": 1, "recommend": "b", "candidates": [{"file": "a.html", "name": "Trail sign", "idea": "…", "type": "…", "palette": ["#…"]}]}`.
- Build the comparison page: `python3 <skill>/scripts/directions.py <that folder>` writes `index.html` with every
  direction at phone (390×844) and desktop (1440×900, scaled) side by side, with names, ideas and palettes.
- Look at it yourself first (screenshot it with Playwright). If one direction is clearly weaker, replace it rather
  than padding the choice.

## 4. The person chooses

Recommend one and say why in two lines. Show the comparison page (an artifact or the file). Their choice, plus what
they liked or disliked in the others, becomes the direction. Never choose silently, and never merge directions into
a compromise nobody asked for.

## 5. Record it where the project keeps such things

A short `DESIGN.md` (or the project's existing art-direction doc): the one-sentence idea, the tokens (colour, type,
spacing scale, radii, shadow, motion durations and easing), the components' rules, and **what is ruled out**.
Put the tokens in code (`:root` variables or the theme file) so Build and PIXELCRAFT's design-system checks read them.
In a GITCRAFT production this is the `foundation.identity` work: its `palette.json` and `logo.svg` follow from the
chosen direction.
