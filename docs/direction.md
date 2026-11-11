# Creative direction

A work order that says "implement a complete game" gets a game that runs. Whether it is worth playing or looking at is
decided by things nobody wrote down: one idea for the look, a loop that is satisfying to repeat, an answer on screen
for every action, a curve. GITCRAFT used to score those after the build (PLAYCRAFT, PIXELCRAFT). Now it decides them
first.

`design.direction` is the first work order of every production that builds or reshapes a product (plan v2,
`production/direction.py`). The agent writes `direction.json` for this product, a gate checks it, the identity and the
build depend on it, and the release hands its open questions to a person.

| Production | Direction covers |
|---|---|
| a new game | `art`, `play` |
| a new app or site | `art`, `interaction` |
| a redesign of an existing project | `art`, and `keeps` |
| a gameplay pass on an existing game | `play`, and `keeps` |
| a polish pass | `art` (and `play` for a game), and `keeps` |
| a feature, a repair, a continue, an audit, a tool, an asset pack | none |

There is no house style. Nothing in GITCRAFT names a palette, a typeface or a genre for you.

## The file

```json
{
 "product": {"promise": "...", "audience": "...", "context": "..."},
 "keeps": ["existing projects only: what stays exactly as it is"],
 "art": {
  "concept": "one idea from this product's world, not adjectives",
  "palette": {"background": "#rrggbb", "surface": "#rrggbb", "primary": "#rrggbb", "accent": "#rrggbb", "text": "#rrggbb"},
  "type": {"display": "...", "body": "...", "why": "..."},
  "shape": "radii, line weight, silhouettes",
  "motion": "what moves, how fast, what never moves",
  "avoid": ["at least two things it must never look like"]
 },
 "play": {
  "pillars": ["two to four"],
  "loop": {"verb": "...", "challenge": "...", "feedback": "...", "reward": "...", "seconds": 8},
  "controls": {"desktop": "...", "touch": "..."},
  "feel": {"run_speed_px_s": 220, "coyote_ms": 90, "hit_stop_ms": 110},
  "feedback": [{"event": "land", "response": "squash, thud, dust"}],
  "curve": [{"at_seconds": 0, "introduces": "..."}],
  "fail": "why losing is fair, and how fast the retry is",
  "mastery": "what a skilled player does that a new one cannot",
  "playtest": ["Did you start another run without being asked?"]
 },
 "interaction": {
  "primary_task": "...", "taps_to_value": 1,
  "screens": [{"name": "Today", "job": "..."}],
  "states": {"empty": "...", "loading": "...", "error": "...", "success": "..."},
  "feedback": [{"event": "...", "response": "..."}]
 },
 "done_when": ["at least three observable statements, beyond 'it runs'"]
}
```

## What the gate checks

Only what can be measured. The same file always gets the same answer.

- `product`: promise, audience and context are stated, and are not placeholders.
- `art.concept` is not made only of words that fit any product ("clean, modern and minimal" is refused).
- `art.palette`: five `#rrggbb` roles, at least four distinct; text on background at least 4.5:1; primary on background
  at least 3:1 (the measured ratio is reported).
- `art.type`, `art.shape`, `art.motion` decided; `art.avoid` has at least two entries.
- `play.pillars`: two to four. `play.loop`: verb, challenge, feedback, reward, and `seconds` of 60 or less.
- `play.feel`: at least three numbers. `play.feedback`: at least four event and response pairs.
- `play.curve`: at least three steps, each later than the last. `play.fail` and `play.mastery` decided.
- `play.playtest`: at least three questions.
- `interaction`: a primary task, `taps_to_value`, a job for every screen, at least three designed states, at least three
  feedback pairs.
- `done_when`: at least three statements.

## What it cannot check

Taste. A direction that passes is a decided one, not a good one. So:

- The build work order holds the build to it: the palette as named tokens, every `play.feedback` pair implemented, the
  `play.feel` numbers as named constants in one place, the curve at its times, `window.__game` exposed so PLAYCRAFT can
  read the run, and the build played at phone and desktop size before it is submitted.
- PIXELCRAFT and PLAYCRAFT measure the result. For a redesign, gameplay or polish pass they measure the project
  **before** the change as well, and the gate is the comparison.
- The release report lists the direction's `playtest` questions, its look question and its `done_when` statements under
  **Needs a person**, as open checkboxes. No report says a game is fun.

## A worked example

`acceptance/assignments/improve-game/direction.json` is the direction for a real gameplay pass on BLIP, a one-button
arcade game (the PLAYCRAFT fixture). The request was "it feels flat and unfair: deaths come out of nowhere, there is no
sound and no way to pause". Its `keeps` protects the one-button rule, the look, the scoring and the saved best score;
its `play` section turns "unfair" into things that can be built: every gap reachable from the last, a hitbox 4 px
kinder than the drawing, the edge that will kill you glowing as you drift toward it, and whatever killed you left red
during a 110 ms freeze. `ACCEPTANCE.json` beside it has what PLAYCRAFT measured before and after.
