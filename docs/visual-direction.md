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
   compared), each with a plain name and a one-line idea, drawn **at the real phone size** (390×664: an iPhone browser with
   its toolbars up) as well as full screen and desktop, plus a play frame for a game, plus **the app icon options drawn
   from that design**. The person picks the look and the icon together (`choice: "a:kite"`) and may say what they liked in
   the others. **That is the approval:** the build depends on it. The chosen frame and icon are saved in the project as the
   target. There is no separate icon approval: still two picks in total.

   **Range is gated.** Three colourways of one layout are one design. Any two designs must differ in composition AND type AND
   palette, and each title and each play frame is shrunk to 120 px wide in grayscale and compared: `same_picture` measures
   where the ink sits whatever the colours (a light and a dark colourway of one layout correlate near 1); two frames at or
   above 0.6 read as the same picture and are refused. `python3 -m production same-picture a.png b.png` runs the same check.
   The measure sees layout, not meaning: it cannot tell that three different arrangements of the same objects are one idea,
   so the agent still looks at the thumbnails and replaces a design that is not its own.
3. A request that already names a style ("neon vector arcade", "like atlas look 7 but warmer") skips step 1: the style is
   recorded from the request with its modifier. An existing project with an established identity and no new look asked
   for skips both: its current best screen is the target.
4. When it ships: the live link plus the **look page**, the chosen frame beside the shipped screens.

Two picks, no more. Declining a pick (with a note) asks for new options with that note; it never adds a question. The app
icon is chosen on the design pick page (App Icon Studio's master, derivatives and `qa.icons` follow from it unchanged; v2
records and productions without a design pick keep `icon.concepts → icon.select`).

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

**Pasted in chat:** when the person pastes or attaches images during a run, the agent saves them itself
(`python3 -m production reference <project> <image> [--note "…"]`: never overwrites another picture, keeps the same picture
once) and tells the person it did and where. If a pasted image reaches the agent only as pixels, with no file to copy, it
says so and asks for the file instead of pretending.

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
- **A moment is a sequence, not a still.** A shot with `moment` (or `sequence`) is captured as three frames: *before* (the
  instant its steps end, or once `sequence.before` holds), *peak* (`wait_for`) and *after* (`sequence.after_ms`, default 900).
- **The fail shot is the instant of failing.** Its `wait_for` must differ from every results shot's (the gate refuses a list
  where they match), and a fail capture that shows the same picture as the results screen must be raised as a gap.
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

**The bar, every shot, every round** (the review is refused unless it does all of this):

- every capture of every reached shot is opened (`coverage.viewed`), and four checks are answered per shot (`checks`), each
  `{ok, note}`: text is readable where it sits (text on textured or hatched ground has the contrast or backing it needs);
  nothing is rotated, clipped or tiny without a reason from the style; the thing the player controls is never hidden by the
  HUD; credits and bylines sit somewhere deliberate. A failed check must have a gap on that shot.
- each signature moment is judged from its sequence as an event at phone size (`moments`: `reads_as_event`, `why`, the three
  frames cited and opened). A small label appearing is not a moment; one that does not land must have a gap against
  `moment:<id>`, which is a work order.
- after a round of fixes every shot is shot again, and the review answers every earlier gap (`previous`: closed or not; one
  still open must be a gap again) and looks at every shot for new gaps the fixes caused.

The rules it keeps from Creative Review: no score, rating or points anywhere; it never produces or changes a score, a
release gate, an acceptance criterion or the verdict; "observed" needs a capture it cites and listed as viewed; fun and
engagement are playtest hypotheses only; "assessment", never "verdict". The two rules it changes on purpose: it runs
automatically in productions with an art direction, and its gaps become work orders. The person-asked Creative Review
(`production_creative`, history/creative/) is unchanged and still runs only when asked.

## Proof

`acceptance/visual/kite-line/`: KITE LINE, a tiny original one-button game, through the real Production Director: seven
looks rendered as its scene, a recorded style pick, three designs that pass the range gate (Margin doodle: a pen-lettered
school-book page; Logbook cover: a green cloth cover with a typed label and play as a plotted chart; Night sketchbook: a
chalk kite filling a black page with the count as a giant numeral), each with its icon options, one recorded pick of look
and icon (with a note on what was liked in another design, which became the night results page), three signature moments
as work orders and as before/peak/after sequences, a fail shot that is the instant of failing, a shot list that reaches
real play in Chromium, an automatic review at the bar above that issued work orders in two rounds (three gaps, then one,
then none), real QA (TestCraft, PLAYCRAFT, PIXELCRAFT, DESIGNCRAFT, icons, attribution, standards, request) and a READY
release, and the look page (chosen frame and shipped screen at the same phone size). The picks were recorded by the acceptance run standing in for the person, and say so.
`publish_proof.py` regenerates the published pages from the production record.
