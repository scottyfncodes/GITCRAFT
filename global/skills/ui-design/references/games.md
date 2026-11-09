# Games: interface vs art direction

A game has two visual layers, and they are owned differently.

| Layer | What | Owned by |
|---|---|---|
| **The world** | characters, environment, lighting, palette grade, VFX, the canvas | the game's art direction (art bible, style guide, `style.ts`/kit files); 3D through ForgeCraft/MeshCraft; how it feels through PLAYCRAFT |
| **The interface** | title, pause, settings, HUD, shop, map, dialogue boxes, results, onboarding overlays | this skill, inside the art direction's rules |

## Rules

1. **The interface is part of the world, not a website laid over it.** Derive its surfaces, type and ornament from
   the world's materials and the art bible (stencilled hull plates and sea-glass for a salvage game; trail-sign enamel
   and card stock for a ski patrol). Never SaaS components: no pill buttons, gradient CTAs, card grids or Inter by default.
2. **Read the game's own rules first** (its `CLAUDE.md`, art bible, `docs/art-direction*`, `docs/brand*`, CSS `:root`
   tokens, and anything retired). Many games test their tokens against the bible: change the bible and tokens together,
   in the same pull request, the way the project says to.
3. **Never redesign an established game's look** to fit general taste. Refine inside it: legibility, hierarchy,
   spacing, touch, states. A redesign needs the person's explicit request.
4. **HUD legibility over the world**: text and icons readable on the brightest and darkest frames (backing plates,
   not glow); numbers in tabular figures; the play area stays clear on phones (thumb zones bottom-left/right, nothing
   critical under the notch or home indicator); HUD scales with `dvh`/safe areas, not fixed pixels.
5. **Touch first**: controls ≥ 44 px, spaced so a thumb does not hit two; pause reachable but not accidental; no
   hover-only information.
6. **Motion**: menus and HUD panels follow `motion.md`; game-feel motion belongs to the game and PLAYCRAFT.
7. **Intentional "tells"**: glow, emoji or a single display face can be the game's identity (a neon arcade, an emoji
   puzzle). If the art direction chose it, pass it to PIXELCRAFT as `accept_tells` with the reason instead of removing it.

## Audit a game

- PLAYCRAFT for play and feel (`playcraft` skill); PIXELCRAFT for the HTML UI (title, menus, HUD overlay) at phone and
  desktop; screenshots for the canvas, judged against the art bible, recorded as screenshot evidence.
- Capture the states that matter: title, first ten seconds of play, pause, a fail and a success screen, on a phone.
