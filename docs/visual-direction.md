# Visual direction, picture-first

Art direction used to be a text file the person never saw, taste ran only when asked, and the captures often missed the
real product. Plan v3 makes the look an intentional, picture-first stage of every production that builds or reshapes a
product. The person does three things: gives references if they have them, picks a style, picks a design. GITCRAFT does
the rest.

```
production/visual.py            scope, work orders, validators, the pick pages, the review pack and rules, the look page
production/atlas.py             render the atlas samples; publish the atlas page (python3 -m production.atlas render|publish)
production/kit/atlas/           atlas.json (the looks), looks/<id>.js (painters), scenes/, fonts/ (OFL), samples/ (committed renders)
studio/core/web/shots.mjs       the shot list runner (TestCraft `shots`, PIXELCRAFT `shots`, PLAYCRAFT `shots`)
acceptance/visual/kite-line/    a whole production through this path, published beside the atlas
tests/test_visual.py
```

Live: the atlas is `/atlas/` on the GITCRAFT site; KITE LINE's style pick, design pick and look page are under `/atlas/kite-line/`.

## What the person sees

1. **Style pick.** Before anything is built: six to eight looks from the atlas, each rendered as the same key scene from
   *this* product (a moment of play for a game, the main screen for an app). One is recommended with a one-line reason
   that names the product. The person picks one, two to compare (`choice: "a,b"`), or "surprise me" (`choice: "surprise"`,
   which takes the shortlist's `wildcard`, never the recommendation).
2. **Design pick.** Three designs of the real first screen inside the chosen style (two in each style when two are
   compared), at phone and desktop size, plus a play frame for a game. They differ in composition, type, palette and
   flavour, not just colour. The person picks one and may say what they liked in the others. **That is the approval:**
   the build depends on it. The chosen frame is saved in the project as the target.
3. A request that already names a style ("neon vector arcade", "like atlas look 7 but warmer") skips step 1: the style is
   recorded from the request with its modifier. An existing project with an established identity and no new look asked
   for skips both: its current best screen is the target.
4. When it ships: the live link plus the **look page**, the chosen frame beside the shipped screens.

Two picks, no more. Declining a pick (with a note) asks for new options with that note; it never adds a question. The app
icon keeps its own existing approval (App Icon Studio).

## The atlas

Fourteen looks GITCRAFT produces well with its own tools, across five families: 2D vector (Flat Geometric, Blueprint,
Linocut Ink, Isometric Diorama, Notebook Sketch), raster (Pixel Art, Risograph Print, Halftone Comic), type (Swiss Grid,
Terminal Phosphor, Editorial Serif), 3D (Low-Poly 3D, rendered by MeshCraft's Blender) and shader (Neon Vector,
Topographic Map). Each is rendered as the same two samples (`scenes/atlas.json`: a small game scene and a phone app
screen), with a plain name, what it suits, an honest note on what is hard, its tools and fonts, and the PIXELCRAFT tells it
chooses on purpose. A section lists what we cannot do well today (painterly, photoreal, detailed characters, frame-by-frame
animation, anime illustration) and why. The atlas is a menu of what is possible, never a house style.

A look is a painter (`looks/<id>.js`) that paints **any** scene in the scene format (`production/kit/atlas/SCENE.md`):
sky and sun, far and mid layers, platforms, hazards, the hero's silhouette as an SVG path, pickups, trails, wind lines and
the HUD. That is what lets a production render its own scene in every look. The 3D look pre-renders the scene in Blender
through MeshCraft's sandboxed launcher (`looks/low-poly-3d.sh`) and draws the HUD over it.

## The stage in the plan (v3)

```
design.styles (agent) → design.style_pick (person) → design.designs (agent) → design.design_pick (person)
  → design.direction (agent, written from the chosen design) → design.moments (expands) → build …
build.wire → build.moment.<id> (agent, one per moment) → capture.shots → review.pack → review.creative (agent) → review.gaps
  → [fix.visual.rN → capture.shots.rN → review.pack.rN → review.creative.rN → review.gaps.rN] × at most 2 → QA → release
release.report → release.shots → release.look (the look page)
```

- `design.direction` (production/direction.py's gate, plus): `art.style` {look, name, design, from: picked|named|kept,
  modifier?}, `art.target` (the frame saved in the project), `art.references` (what it takes from and leaves out of every
  reference image), `art.accept_tells` (the PIXELCRAFT tells this style makes deliberate, each with its reason: QA's
  PIXELCRAFT audit lists them as accepted instead of questioning them), `art.moments` (two or three signature moments),
  and the shot list in the project. The gate refuses a direction that ignores a reference image in the project, or a moment
  with no shot.
- **Signature moments** (for example the title reveal, the first win, the results screen) are added to the plan once the
  direction names them: each is its own work order and its own shot.
- Everything after the build is **advisory to the verdict**: no visual task carries an acceptance criterion or a gate on
  the release, and no score is computed differently. QA waits for the visual rounds so it measures the reviewed build.
- v1 and v2 records keep their graphs: nothing here runs in them.

## References

Drop images in `<art-direction folder>/references/` (the project's existing `docs/art-direction/` if it has one, otherwise
`art-direction/references/`); an optional `references/notes.json` ({file: note}) says what each is. Images pasted in chat
are saved there by the agent. They shape the shortlist and the designs; the direction records what it takes from each and
what it leaves. A reference's layout or assets are never copied wholesale. No references is fine.

## The shot list

`<art-direction>/shots.json` names the shots that matter and how to reach each with real content on screen:

```json
{"version": 1, "product": "game", "viewports": ["phone", "desktop"], "shots": [
  {"id": "title", "name": "Title, fully loaded", "kind": "title", "moment": "title-reveal", "steps": [],
   "wait_for": {"selector": "#title[data-ready]", "timeout_ms": 8000}},
  {"id": "mid-play", "name": "Mid-play", "kind": "play", "steps": [{"press": "Space"}, {"hold": {"key": "Space", "ms": 260}}],
   "wait_for": {"js": "window.__game.state === 'playing' && window.__game.time > 1.6"}}]}
```

- Kinds: title, play, moment, fail, results, screen, other. A game needs title, play, fail and results; an app its screens.
- Steps use PIXELCRAFT's journey vocabulary (click, tap, selector, fill, press, goto, back, wait, expect) plus `hold` and
  `eval` for games. Every shot needs a `wait_for` (a selector, text or JS condition): a fixed delay over a loading screen is
  refused by the gate.
- A shot whose content never appears is **not seen**, with the reason; only a diagnostic image is kept, and nothing ever
  judges it. TestCraft `shots` captures the list; PIXELCRAFT audits its title, screen and results shots as its screens
  (its scoring method is unchanged; a shot it cannot reach is listed and not audited); PLAYCRAFT captures the list beside
  its play frames (never scored); the visual review and Creative Review packs index only reached shots.

## The automatic visual review (Creative Review with teeth)

In a production with an art direction, after the build: the shot list is captured, packed with the chosen frame, the style
sample, the references and the moments (each item hashed), and reviewed by the agent against them. Every visible gap is
`{id, shot, against: target|style|moment:<id>|reference:<file>, gap, fix, evidence, basis: observed_render, severity}`.
Gaps become a fix work order, then a fresh capture and a fresh review; at most two rounds. What remains after the second
round is listed for the person on a page with the screenshots it was seen in, and on the look page.

The rules it keeps from Creative Review: no score, rating or points anywhere; it never produces or changes a score, a
release gate, an acceptance criterion or the verdict; "observed" needs a capture it cites and listed as viewed; fun and
engagement are playtest hypotheses only; "assessment", never "verdict". The two rules it changes on purpose: it runs
automatically in productions with an art direction, and its gaps become work orders. The person-asked Creative Review
(`production_creative`, history/creative/) is unchanged and still runs only when asked.

## Proof

`acceptance/visual/kite-line/`: KITE LINE, a tiny original one-button game, through the real Production Director: seven
looks rendered as its scene, a recorded style pick, three designs of its title screen, a recorded design pick (with a note
on what was liked in another design, which became the night results page), three signature moments as work orders, a shot
list that reaches real play in Chromium, an automatic review that issued work orders in two rounds (three gaps, then one,
then one left for the person), real QA (TestCraft, PLAYCRAFT, PIXELCRAFT, DESIGNCRAFT, attribution, standards, request) and a
READY release, and the look page. The picks were recorded by the acceptance run standing in for the person, and say so.
`publish_proof.py` regenerates the published pages from the production record.
