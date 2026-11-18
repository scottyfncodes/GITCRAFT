# The atlas scene format

A look paints whatever scene it is given. The atlas uses `scenes/atlas.json`; a production renders its own product's
key scene in the same format (the style shortlist: "each rendered as the same key scene from THIS product").
Coordinates are CSS pixels in `world` ([960, 540]). Every field except `world`, `hero` and `hud` is optional, and a
look must paint every field that is present and skip the ones that are not.

| field | meaning | helper in lib.js |
|---|---|---|
| `world` | [W, H] | |
| `mood` | `dawn`, `day`, `dusk`, `night`: the light the look should suggest in its own way | |
| `sun` | {x, y, r}: sun or moon | |
| `far` | [[x, y], …] distant skyline / hills polyline, closed to the bottom | `farPolygon(S, W, H)` |
| `mid` | [[x, w, h], …] mid-ground blocks standing on `ground_y` (buildings, trees, rocks: the look decides) | `buildings(S)` |
| `ground_y` | the horizon line the mid blocks stand on | |
| `platforms` | [[x, y, w, h], …] solid ground the hero can stand on | |
| `hazards` | [{kind: spikes, block or path, x, y, w, h, path?, box?}] | `hazardPath(hz)` |
| `hero` | {x, y, size, facing, path, eye: [x, y, r], accent?}: the player; `path`/`accent` are SVG paths in a 64-unit box | `heroPath(h)`, `heroPath(h, 'accent')`, `heroEye(h)` |
| `trail` | [[x, y], …] and `trail_kind`: `arc` (motion arc) or `string` (a line tied to the hero, e.g. a kite string) | `smooth(ctx, pts)`, `trailKind(S)` |
| `pickups` | [{x, y, r}] with `pickup_shape` (circle, diamond, star) or `pickup_path` (24-unit SVG path) | `pickupPath(S, p)` |
| `lines` | [[[x, y], …], …] motion or wind streaks | `smooth` |
| `hud` | {score, score_label, lives, best, pause} | |

Looks never read a field by position in an array or assume the atlas scene's layout: the same painter renders a runner,
a kite game or a puzzle board.
