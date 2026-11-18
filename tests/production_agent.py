"""The acceptance test's stand-in for Claude: it carries out the production's agent work orders.

Everything here is real work, not a mocked result: the identity is drawn and exported by VectorCraft through
the sandboxed launcher (scripts/mcp.sh vectorcraft), and the game is real HTML/JS that loads the integrated
LevelCraft levels, AudioCraft sounds and FXCraft flipbooks. The engine then measures that game with TestCraft,
PLAYCRAFT, PIXELCRAFT and DESIGNCRAFT. What is scripted is only the coding Claude would do from the work order.

The first build carries a deliberate defect (a missing script file → console/missing-file errors on load) so
the QA gate fails for real; fix() repairs it so the re-verification passes on the modified files."""
import json, os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PALETTE = {"background": "#14122B", "primary": "#F2A541", "accent": "#3FC1C9", "text": "#F5F0E6"}


DIRECTION_ART = {"concept": "A paper lantern carried through a flooded night market: warm light on dark water, everything else in shadow",
                 "palette": {"background": PALETTE["background"], "surface": "#1F1C3D", "primary": PALETTE["primary"], "accent": PALETTE["accent"], "text": PALETTE["text"]},
                 "type": {"display": "a condensed slab, set in capitals", "body": "the system UI face", "why": "stamped market signage for names; nothing to download for reading"},
                 "shape": "soft-cornered blocks with a 4 px light outline; silhouettes readable at 24 px",
                 "motion": "the lantern bobs on a 2 s sine; UI panels slide 160 ms ease-out; nothing moves while paused",
                 "avoid": ["neon cyberpunk glow on everything", "flat grey SaaS cards", "pixel-art retro pastiche"]}
DIRECTION_PLAY = {"pillars": ["keep the light alive", "read the water ahead", "one more run"],
                  "loop": {"verb": "steer and hop the lantern", "challenge": "gaps and gusts that arrive faster", "feedback": "a splash, a dust puff and a chime on every landing",
                           "reward": "coins that extend the flame and a best distance", "seconds": 8},
                  "controls": {"desktop": "arrow keys to steer, Space to hop", "touch": "left and right thumb zones, tap to hop"},
                  "feel": {"run_speed_px_s": 220, "jump_height_px": 96, "jump_time_s": 0.42, "coyote_ms": 90, "input_buffer_ms": 110},
                  "feedback": [{"event": "jump", "response": "squash, jump sound, dust at the feet"}, {"event": "land", "response": "stretch back, soft thud, dust"},
                               {"event": "coin", "response": "chime rising in pitch with the streak, +1 pops from the coin"},
                               {"event": "hit", "response": "120 ms freeze, shake, the flame dims"}, {"event": "new best", "response": "the counter flashes the accent colour"}],
                  "curve": [{"at_seconds": 0, "introduces": "flat ground and single coins"}, {"at_seconds": 20, "introduces": "gaps that need a hop"},
                            {"at_seconds": 45, "introduces": "gusts that push sideways"}],
                  "fail": "the flame dims for a full second before it goes out, and the gap that did it is always visible two tiles ahead; retry is one tap",
                  "mastery": "chains hops across gaps without landing between coins, keeping the streak pitch climbing",
                  "playtest": ["Did you start a second run without being asked?", "Could you say why you failed each time?", "Did the hop feel like it obeyed you?"]}
DIRECTION_APP = {"primary_task": "see when the next high tide is at my beach", "taps_to_value": 0,
                 "screens": [{"name": "Today", "job": "the next high and low tide, large enough to read at arm's length"}, {"name": "Week", "job": "seven days of tides to plan around"}],
                 "states": {"empty": "no beach chosen yet: one field and the three nearest beaches", "loading": "the last known times, dimmed, with a tide line drawing in",
                            "error": "the last saved table with its date, and a retry that says what failed", "success": "the saved beach's name briefly underlined"},
                 "feedback": [{"event": "choose a beach", "response": "the table swaps in place within 100 ms"}, {"event": "pull to refresh", "response": "the tide line redraws"},
                              {"event": "tap a day", "response": "the day expands where it is, no navigation"}]}


def direction(order, game=True, **over):
    """design.direction: a real, complete creative direction (what Claude writes before any code)."""
    d = {"product": {"promise": "A calm run through a night market that asks for one more go" if game else "The next tide at my beach, before I have finished asking",
                     "audience": "someone with five minutes on a phone" if game else "a family deciding when to walk down to the beach",
                     "context": "one-handed, on a train or a sofa, sound often off" if game else "glanced at on a phone in a hallway, sandals in the other hand"},
         "art": DIRECTION_ART, **({"play": DIRECTION_PLAY} if game else {"interaction": DIRECTION_APP}),
         "done_when": ["a first-time player lands their first hop within five seconds" if game else "the next high tide is readable without touching the screen",
                       "every action in the feedback table answers on screen" if game else "every state in the states table has been seen on a phone",
                       "it is recognisably this product in a thumbnail"]}
    d.update(over)
    p = os.path.join(order["out_dir"], "direction.json")
    json.dump(d, open(p, "w"), indent=1)
    return [p]


def identity(order, env):
    """VectorCraft: a wordmark logo (SVG) in an original palette (the app icon is the App Icon Studio's work)."""
    from mcp_client import Client
    out = order["out_dir"]
    json.dump(PALETTE, open(os.path.join(out, "palette.json"), "w"), indent=1)
    steps = [
        ("run_command", {"command": "artboard.setProps", "params": {"index": 0, "width": 640, "height": 200, "name": "logo"}}),
        ("draw_shape", {"shape": "rectangle", "x": 0, "y": 0, "width": 640, "height": 200, "fill": PALETTE["background"], "stroke": "none", "radius": 24}),
        ("draw_shape", {"shape": "ellipse", "x": 34, "y": 36, "width": 128, "height": 128, "fill": PALETTE["primary"], "stroke": "none", "opacity": 35}),
        ("draw_shape", {"shape": "rectangle", "x": 72, "y": 62, "width": 52, "height": 78, "fill": PALETTE["primary"], "stroke": PALETTE["text"], "strokeWidth": 4, "radius": 12}),
        ("draw_shape", {"shape": "rectangle", "x": 84, "y": 48, "width": 28, "height": 14, "fill": PALETTE["accent"], "stroke": "none", "radius": 4}),
        ("add_text", {"text": "LANTERN DRIFT", "x": 186, "y": 118, "size": 46, "color": PALETTE["text"]}),
        ("export", {"path": os.path.join(out, "logo.svg"), "format": "svg", "artboard": 0, "outlineText": True}),
    ]
    _vectorcraft(steps, out, env)
    return [os.path.join(out, f) for f in ("palette.json", "logo.svg")]


def _vectorcraft(steps, out, env, log="vectorcraft_steps.json"):
    from mcp_client import Client
    c = Client([os.path.join(REPO, "scripts", "mcp.sh"), "vectorcraft"], env=env, log=os.path.join(out, "vectorcraft.log"))
    rec = []
    try:
        for tool, args in steps:
            ok, r = c.call(tool, args, timeout=120)
            rec.append({"tool": tool, "ok": ok, "result": str(r)[:200]})
            if not ok: raise RuntimeError(f"vectorcraft {tool} failed: {r}")
    finally:
        c.p.kill()
    json.dump(rec, open(os.path.join(out, log), "w"), indent=1)


def _concept(cid, ox, oy):
    """One icon concept on a 1024 artboard at (ox, oy): three different ideas, not colour swaps."""
    P, S = PALETTE, 1024
    tile = ("draw_shape", {"shape": "rectangle", "x": ox, "y": oy, "width": S, "height": S, "fill": P["background"], "stroke": "none"})
    if cid == "lantern":   # the lantern itself: a bold body, a cap and a glow
        return [tile, ("draw_shape", {"shape": "ellipse", "x": ox + 192, "y": oy + 192, "width": 640, "height": 640, "fill": P["primary"], "stroke": "none", "opacity": 28}),
                ("draw_shape", {"shape": "rectangle", "x": ox + 372, "y": oy + 300, "width": 280, "height": 440, "fill": P["primary"], "stroke": P["text"], "strokeWidth": 22, "radius": 64}),
                ("draw_shape", {"shape": "rectangle", "x": ox + 424, "y": oy + 222, "width": 176, "height": 82, "fill": P["accent"], "stroke": "none", "radius": 22})]
    if cid == "drift":     # a drifting flame over a wave: motion
        return [tile, ("draw_shape", {"shape": "ellipse", "x": ox + 352, "y": oy + 196, "width": 320, "height": 460, "fill": P["primary"], "stroke": "none"}),
                ("draw_shape", {"shape": "ellipse", "x": ox + 432, "y": oy + 330, "width": 160, "height": 240, "fill": P["text"], "stroke": "none"}),
                ("draw_shape", {"shape": "rectangle", "x": ox + 152, "y": oy + 720, "width": 720, "height": 96, "fill": P["accent"], "stroke": "none", "radius": 48})]
    return [tile, ("draw_shape", {"shape": "ellipse", "x": ox + 212, "y": oy + 212, "width": 600, "height": 600, "fill": P["accent"], "stroke": "none"}),   # "ember": a ring and a spark
            ("draw_shape", {"shape": "ellipse", "x": ox + 332, "y": oy + 332, "width": 360, "height": 360, "fill": P["background"], "stroke": "none"}),
            ("draw_shape", {"shape": "ellipse", "x": ox + 437, "y": oy + 437, "width": 150, "height": 150, "fill": P["primary"], "stroke": "none"})]


IDEAS = {"lantern": "the lantern itself: a bold glowing body under an accent cap", "drift": "a flame drifting over a wave of light",
         "ember": "an ember inside a ring: the collectible"}


def icon_concepts(order, env):
    """VectorCraft: three different 1024 px concepts, exported as PNG + SVG, and concepts.json with a recommendation."""
    out, steps = order["out_dir"], [("run_command", {"command": "artboard.setProps", "params": {"index": 0, "width": 1024, "height": 1024, "name": "lantern"}})]
    for i, cid in enumerate(IDEAS):
        if i: steps.append(("run_command", {"command": "artboard.new", "params": {"x": i * 1124, "y": 0, "width": 1024, "height": 1024, "name": cid}}))
        steps += _concept(cid, i * 1124, 0)
    for i, cid in enumerate(IDEAS):
        steps += [("export", {"path": os.path.join(out, f"{cid}.png"), "format": "png", "artboard": i, "scale": 1}),
                  ("export", {"path": os.path.join(out, f"{cid}.svg"), "format": "svg", "artboard": i})]
    _vectorcraft(steps, out, env, "vectorcraft_concepts.json")
    json.dump({"concepts": [{"id": c, "file": f"{c}.png", "source": f"{c}.svg", "idea": IDEAS[c], "rationale": "one silhouette that reads at 32 px"} for c in IDEAS],
               "recommended": "lantern"}, open(os.path.join(out, "concepts.json"), "w"), indent=1)
    return [os.path.join(out, "concepts.json")]


def icon_master(order, env):
    """VectorCraft: the approved concept (selection.json in the hand-off) redrawn as the 1024 master."""
    out = order["out_dir"]
    sel = next(json.load(open(o["path"])) for u in order["handoff"]["upstream"] for o in u["outputs"] if os.path.basename(o["path"]) == "selection.json")
    steps = [("run_command", {"command": "artboard.setProps", "params": {"index": 0, "width": 1024, "height": 1024, "name": "icon"}})] + _concept(sel["choice"], 0, 0) + [
        ("export", {"path": os.path.join(out, "icon-1024.png"), "format": "png", "artboard": 0, "scale": 1}),
        ("export", {"path": os.path.join(out, "icon.svg"), "format": "svg", "artboard": 0})]
    _vectorcraft(steps, out, env, "vectorcraft_master.json")
    return [os.path.join(out, "icon-1024.png"), os.path.join(out, "icon.svg")]


GAME_JS = r"""// Lantern Drift — an original mobile-first platformer (GITCRAFT production acceptance game)
const cv = document.getElementById('game'), cx = cv.getContext('2d');
const A = window.ASSETS, P = A.palette;
const S = {level: 0, best: +(localStorage.getItem('ld_best') || 0), unlocked: +(localStorage.getItem('ld_unlocked') || 1), state: 'title', coins: 0, muted: false, paused: false, t: 0};
const sounds = {}; for (const [k, f] of Object.entries(A.sfx)) { const a = new Audio(f); a.preload = 'auto'; sounds[k] = a; }
const music = new Audio(A.music); music.loop = true; music.volume = 0.4;
function play(k) { if (!S.muted && sounds[k]) { const a = sounds[k].cloneNode(); a.volume = 0.7; a.play().catch(() => {}); } }
const fx = {}; for (const [k, f] of Object.entries(A.fx)) { const i = new Image(); i.src = f.image; fx[k] = {img: i, meta: null}; fetch(f.meta).then(r => r.json()).then(m => fx[k].meta = m).catch(() => {}); }
const particles = [];
function burst(kind, x, y) { particles.push({kind, x, y, f: 0}); }
let levels = [], L = null, pl = null, cam = 0;
Promise.all(A.levels.map(f => fetch(f).then(r => r.json()))).then(ls => { levels = ls; resize(); draw(); });
// LevelCraft rows: one base-36 character per tile id (legend in the level file; 11 ground, 12 spikes, 17 sky)
const tid = c => parseInt(c, 36);
function solid(c) { return L && L.solid.includes(tid(c)); }
function cell(x, y) { if (!L || y < 0 || y >= L.height || x < 0 || x >= L.width) return 'B'; return L.rows[y][x]; }
function load(i) {
  L = levels[i]; const st = L.entities.find(e => e.type === 'start');
  pl = {x: st.x, y: st.y - 0.01, vx: 0, vy: 0, on: false, hp: 3};
  L.items = L.entities.filter(e => e.type === 'coin').map(e => ({...e, got: false}));
  L.foes = L.entities.filter(e => e.type === 'enemy').map(e => ({...e, d: 1}));
  L.exit = L.entities.find(e => e.type === 'exit'); S.coins = 0; S.state = 'play'; S.t = 0;
}
const keys = {}; const touch = {left: false, right: false, jump: false};
addEventListener('keydown', e => { keys[e.key] = true; if (e.key === ' ' || e.key === 'Enter') act(); if (e.key === 'p') S.paused = !S.paused; if (e.key === 'm') toggleMute(); });
addEventListener('keyup', e => keys[e.key] = false);
for (const [id, k] of [['bl', 'left'], ['br', 'right'], ['bj', 'jump']]) {
  const b = document.getElementById(id);
  b.addEventListener('pointerdown', e => { e.preventDefault(); touch[k] = true; if (k === 'jump') act(); });
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) b.addEventListener(ev, () => touch[k] = false);
}
document.getElementById('mute').addEventListener('click', toggleMute);
document.getElementById('pause').addEventListener('click', () => { S.paused = !S.paused; play('click'); });
cv.addEventListener('pointerdown', () => { if (S.state !== 'play') act(); });
function toggleMute() { S.muted = !S.muted; music.muted = S.muted; document.getElementById('mute').textContent = S.muted ? 'Sound off' : 'Sound on'; }
function act() {
  if (S.state === 'title' || S.state === 'over' || S.state === 'won') { play('click'); music.play().catch(() => {}); load(S.state === 'won' ? 0 : Math.min(S.level, S.unlocked - 1)); return; }
  if (S.state === 'play' && pl.on) { pl.vy = -0.52; pl.on = false; play('jump'); burst('dust', pl.x, pl.y); }
}
function step(dt) {
  if (S.state !== 'play' || S.paused || !L) return;
  S.t += dt; const left = keys.ArrowLeft || keys.a || touch.left, right = keys.ArrowRight || keys.d || touch.right;
  pl.vx = (right - left) * 0.16; pl.vy = Math.min(pl.vy + 0.035 * dt * 60, 0.6);
  let nx = pl.x + pl.vx * dt * 60; if (!solid(cell(Math.floor(nx + (pl.vx > 0 ? 0.8 : 0.1)), Math.floor(pl.y - 0.5)))) pl.x = nx;
  let ny = pl.y + pl.vy * dt * 60; pl.on = false;
  if (pl.vy > 0 && solid(cell(Math.floor(pl.x + 0.45), Math.floor(ny)))) { pl.y = Math.floor(ny); pl.vy = 0; pl.on = true; } else pl.y = ny;
  if (tid(cell(Math.floor(pl.x + 0.45), Math.floor(pl.y - 0.2))) === 12 || tid(cell(Math.floor(pl.x + 0.45), Math.floor(pl.y))) === 12 || pl.y > L.height) hurt();
  for (const c of L.items) if (!c.got && Math.abs(c.x - pl.x) < 0.9 && Math.abs(c.y - pl.y) < 1.2) { c.got = true; S.coins++; play('coin'); burst('sparks', c.x, c.y); }
  for (const f of L.foes) { f.x += f.d * 0.03 * dt * 60; if (f.x < f.patrol[0] || f.x > f.patrol[1]) f.d *= -1; if (Math.abs(f.x - pl.x) < 0.8 && Math.abs(f.y - pl.y) < 1) hurt(); }
  if (Math.abs(L.exit.x - pl.x) < 1 && Math.abs(L.exit.y - pl.y) < 1.5) win();
  cam += ((pl.x * tile() - cv.width / 2) - cam) * 0.1;
}
function hurt() { play('hit'); burst('energy', pl.x, pl.y); pl.hp--; if (pl.hp <= 0) { S.state = 'over'; } else { const st = L.entities.find(e => e.type === 'start'); pl.x = st.x; pl.y = st.y - 0.01; pl.vy = 0; } }
function win() {
  play('powerup'); S.level = Math.min(S.level + 1, levels.length - 1);
  S.unlocked = Math.max(S.unlocked, S.level + 1); localStorage.setItem('ld_unlocked', S.unlocked);
  S.best = Math.max(S.best, S.coins); localStorage.setItem('ld_best', S.best);
  S.state = 'won';
}
function tile() { return Math.max(16, Math.floor(cv.height / 18)); }
function resize() { cv.width = innerWidth * devicePixelRatio; cv.height = innerHeight * devicePixelRatio; }
addEventListener('resize', resize);
function draw() {
  const T = tile(); cx.fillStyle = P.background; cx.fillRect(0, 0, cv.width, cv.height);
  if (S.state === 'play' && L) {
    const y0 = pl.y * T - cv.height * 0.6;
    for (let y = 0; y < L.height; y++) for (let x = 0; x < L.width; x++) {
      const c = tid(L.rows[y][x]); if (c === 0 || c === 17) continue;
      cx.fillStyle = c === 12 ? P.accent : P.primary; cx.globalAlpha = c === 12 ? 1 : 0.55; cx.fillRect(x * T - cam, y * T - y0, T - 1, T - 1); cx.globalAlpha = 1;
    }
    for (const c of L.items) if (!c.got) { cx.fillStyle = P.primary; cx.beginPath(); cx.arc((c.x + .5) * T - cam, (c.y + .5) * T - y0, T * .3, 0, 7); cx.fill(); }
    for (const f of L.foes) { cx.fillStyle = P.accent; cx.fillRect(f.x * T - cam, (f.y - .2) * T - y0, T * .9, T * .9); }
    cx.fillStyle = P.text; cx.fillRect(L.exit.x * T - cam, (L.exit.y - 1) * T - y0, T, T * 2);
    cx.fillStyle = P.primary; cx.fillRect(pl.x * T - cam, (pl.y - 1) * T - y0, T * .8, T);
    for (const p of particles) { const F = fx[p.kind]; if (F && F.img.complete && F.meta) { const m = F.meta, fr = Math.min(p.f | 0, m.frames - 1), cs = m.cols, fw = m.frame_width, fh = m.frame_height;
      cx.drawImage(F.img, (fr % cs) * fw, Math.floor(fr / cs) * fh, fw, fh, p.x * T - cam - T, p.y * T - y0 - T * 2, T * 2, T * 2); } p.f += 0.5; }
    for (let i = particles.length - 1; i >= 0; i--) if (particles[i].f > 32) particles.splice(i, 1);
    hud(`Level ${S.level + 1}/${levels.length}  ·  Coins ${S.coins}  ·  Lives ${pl.hp}  ·  Best ${S.best}` + (S.paused ? '  ·  PAUSED' : ''));
  } else {
    cx.fillStyle = P.text; cx.textAlign = 'center'; cx.font = `bold ${Math.floor(cv.height / 12)}px system-ui`;
    cx.fillText(S.state === 'over' ? 'The lantern went out' : S.state === 'won' ? 'Level cleared!' : 'LANTERN DRIFT', cv.width / 2, cv.height * .4);
    cx.font = `${Math.floor(cv.height / 28)}px system-ui`;
    cx.fillText(S.state === 'title' ? 'Tap or press Space to start — reach the light, collect embers' : 'Tap to continue', cv.width / 2, cv.height * .52);
    cx.fillText(`Best: ${S.best} embers · Levels unlocked: ${S.unlocked}`, cv.width / 2, cv.height * .6);
  }
}
function hud(t) { cx.fillStyle = P.text; cx.textAlign = 'left'; cx.font = `${Math.floor(tile() * .7)}px system-ui`; cx.fillText(t, 16 * devicePixelRatio, tile() * 1.2); }
let last = performance.now();
function loop(now) { const dt = Math.min(0.05, (now - last) / 1000); last = now; step(dt); draw(); requestAnimationFrame(loop); }
requestAnimationFrame(loop);
"""


def _assets(order):
    """The integrated assets: the hand-off's list, or (plan v2, when the build starts before every asset is integrated) the
    project's asset manifest, which the agent may read but never writes."""
    ia = order["handoff"].get("integrated_assets") or []
    if any(a["dest_rel"].endswith("palette.json") for a in ia): return ia
    m = json.load(open(os.path.join(order["project"], "gitcraft.assets.json")))["assets"]
    return [{"dest_rel": k, "role": v.get("role"), "format": v.get("format"), "task": v.get("task")} for k, v in sorted(m.items())]


def _snippet(order):
    p = order["handoff"].get("icon_snippet") or next((o["path"] for u in order["handoff"].get("upstream") or [] for o in u["outputs"] if o["path"].endswith("icons.snippet.json")), None)
    return json.load(open(p)) if p else None


def wire(order, defect=True):
    """build.wire (plan v2): the same game, now with every integrated asset and the approved icon set wired in."""
    return build(order, defect)


def build(order, defect=True):
    """The game the build work order asks for, using every integrated asset (paths from the hand-off). In plan v2 the first
    build has no icon set yet (a person is still choosing it): it ships a placeholder favicon, and wire() adds the set."""
    proj = order["project"]
    ia = _assets(order)
    by = lambda role: [a["dest_rel"] for a in ia if a["role"] == role]
    sfx = {os.path.splitext(os.path.basename(p))[0]: p for p in by("sfx")}
    levels = sorted(p for p in by("level_data"))
    fxs = {}
    for a in ia:
        if a["role"] == "flipbook": fxs.setdefault(os.path.basename(a["dest_rel"]).split("_")[0], {})["image"] = a["dest_rel"]
        if a["role"] == "flipbook_meta": fxs.setdefault(os.path.basename(a["dest_rel"]).split("_")[0], {})["meta"] = a["dest_rel"]
    atlases = [a["dest_rel"] for a in ia if (a["role"] or "").startswith("atlas")]
    other = [a["dest_rel"] for a in ia if a["role"] in ("tiled_map", "tileset") or (a["role"] or "").startswith("atlas")]
    palette = json.load(open(next(os.path.join(proj, a["dest_rel"]) for a in ia if a["dest_rel"].endswith("palette.json"))))
    brand = [a["dest_rel"] for a in ia if "/brand/" in a["dest_rel"]]
    assets = {"palette": palette, "sfx": sfx, "music": by("music")[0], "levels": levels, "fx": fxs,
              "editor_sources": other, "atlases": atlases, "brand": brand}
    logo = next((b for b in brand if b.endswith(".svg")), "")
    snip = _snippet(order) or {"head": '<link rel="icon" href="data:,">', "manifest": {"name": "Lantern Drift", "icons": []}}
    json.dump(dict(snip["manifest"], description="Lantern Drift by HaveAnApp"), open(os.path.join(proj, "manifest.webmanifest"), "w"), indent=1)
    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,user-scalable=no">
<title>Lantern Drift</title><meta name="author" content="HaveAnApp">
{snip["head"]}
<style>
:root{{--bg:{palette['background']};--fg:{palette['text']};--accent:{palette['accent']};--primary:{palette['primary']}}}
html,body{{margin:0;height:100%;background:var(--bg);color:var(--fg);font:16px system-ui;overflow:hidden;touch-action:none}}
canvas{{position:fixed;inset:0;width:100%;height:100%}}
header{{position:fixed;top:env(safe-area-inset-top,0);left:0;right:0;display:flex;justify-content:space-between;align-items:center;padding:8px 16px}}
header img{{height:40px;display:block}}
.haveanapp-byline{{margin:2px 0 0;font-size:12px;font-weight:500;letter-spacing:.04em;line-height:1.2;color:inherit;opacity:.72}}
.tb{{display:flex;gap:8px}}
button{{min-width:48px;min-height:48px;padding:0 14px;border-radius:12px;border:2px solid var(--fg);background:rgba(20,18,43,.6);color:var(--fg);font:600 16px system-ui}}
.pad{{position:fixed;bottom:calc(env(safe-area-inset-bottom,0px) + 16px);display:flex;gap:16px}}
.pad button{{width:72px;height:72px;font-size:22px}}
#lp{{left:16px}} #rp{{right:16px}}
</style></head><body>
<canvas id="game" aria-label="Lantern Drift game"></canvas>
<header><div><img src="{logo}" alt="Lantern Drift"><p class="haveanapp-byline" data-haveanapp><a href="https://haveanapp.com" rel="noopener" target="_blank" style="color:inherit;text-decoration:none">by HaveAnApp</a></p></div><div class="tb"><button id="pause">Pause</button><button id="mute">Sound on</button></div></header>
<div class="pad" id="lp"><button id="bl" aria-label="Move left">◀</button><button id="br" aria-label="Move right">▶</button></div>
<div class="pad" id="rp"><button id="bj" aria-label="Jump">Jump</button></div>
<script>window.ASSETS = {json.dumps(assets)};</script>
<script src="{'js/game.js' if not defect else 'js/missing-boot.js'}"></script>
{'<script src="js/game.js"></script>' if defect else ''}
</body></html>
"""
    os.makedirs(os.path.join(proj, "js"), exist_ok=True)
    open(os.path.join(proj, "index.html"), "w").write(html)
    open(os.path.join(proj, "js", "game.js"), "w").write(GAME_JS)
    json.dump({"name": "lantern-drift", "private": True, "version": "1.0.0", "description": "Lantern Drift — GITCRAFT production acceptance game",
               "scripts": {}}, open(os.path.join(proj, "package.json"), "w"), indent=1)
    open(os.path.join(proj, "README.md"), "w").write("# Lantern Drift\n\nAn original mobile-first platformer: reach the light, collect embers, three levels, saved progress.\n\n"
                                                     "Controls: arrows/A-D + Space, or the on-screen pad. P pauses, M mutes.\n")
    return ["index.html", "js/game.js", "package.json", "README.md", "manifest.webmanifest"]


FEEL = [   # what PLAYCRAFT's plan asked for, as changes to js/game.js
 ("addEventListener('keydown', e => { keys[e.key] = true; if (e.key === ' ' || e.key === 'Enter') act();",
  "document.addEventListener('visibilitychange', () => { if (document.hidden) S.paused = true; });   // auto-pause when hidden\n"
  "addEventListener('keydown', e => { keys[e.key] = true; if (e.key === 'r' && S.state === 'play') load(S.level); if (e.key === ' ' || e.key === 'Enter') act();"),
 ("  if (S.state === 'play' && pl.on) { pl.vy = -0.52; pl.on = false; play('jump'); burst('dust', pl.x, pl.y); }",
  "  if (S.state === 'play') pl.buf = 0.15;   // jump buffering: a press just before landing still jumps"),
 ("  pl = {x: st.x, y: st.y - 0.01, vx: 0, vy: 0, on: false, hp: 3};",
  "  pl = {x: st.x, y: st.y - 0.01, vx: 0, vy: 0, on: false, hp: 3, buf: 0, coyote: 0, cp: {x: st.x, y: st.y}};"),
 ("  pl.vx = (right - left) * 0.16; pl.vy = Math.min(pl.vy + 0.035 * dt * 60, 0.6);",
  "  if (S.hitstop > 0) { S.hitstop -= dt; return; }   // hit-stop on key moments\n"
  "  const target = (right - left) * 0.16; pl.vx += (target - pl.vx) * Math.min(1, dt * (pl.on ? 14 : 7));   // acceleration + friction\n"
  "  pl.coyote = pl.on ? 0.1 : pl.coyote - dt; pl.buf -= dt;   // coyote time\n"
  "  if (pl.buf > 0 && pl.coyote > 0) { pl.vy = -0.52; pl.on = false; pl.coyote = 0; pl.buf = 0; play('jump'); burst('dust', pl.x, pl.y); }\n"
  "  const held = keys[' '] || keys.ArrowUp || keys.w || touch.jump; if (!held && pl.vy < -0.2) pl.vy *= 0.6;   // variable jump height\n"
  "  pl.vy = Math.min(pl.vy + 0.035 * dt * 60, 0.6);\n"
  "  for (const c of L.entities) if (c.type === 'checkpoint' && Math.abs(c.x - pl.x) < 1 && c.x > pl.cp.x) { pl.cp = {x: c.x, y: c.y}; play('click'); burst('sparks', c.x, c.y); }"),
 ("function hurt() { play('hit'); burst('energy', pl.x, pl.y); pl.hp--; if (pl.hp <= 0) { S.state = 'over'; } else { const st = L.entities.find(e => e.type === 'start'); pl.x = st.x; pl.y = st.y - 0.01; pl.vy = 0; } }",
  "function hurt() { play('hit'); burst('energy', pl.x, pl.y); S.shake = 0.3; S.hitstop = 0.08; pl.hp--; if (pl.hp <= 0) { S.state = 'over'; } else { pl.x = pl.cp.x; pl.y = pl.cp.y - 0.01; pl.vy = 0; pl.vx = 0; } }   // respawn at the last checkpoint"),
 ("  const T = tile(); cx.fillStyle = P.background; cx.fillRect(0, 0, cv.width, cv.height);",
  "  const T = tile(); cx.setTransform(1, 0, 0, 1, 0, 0); cx.fillStyle = P.background; cx.fillRect(0, 0, cv.width, cv.height);\n"
  "  if (S.shake > 0) { S.shake -= 1 / 60; cx.translate((Math.random() - .5) * T * .4, (Math.random() - .5) * T * .4); }   // screen shake"),
]


def improve(order):
    """PLAYCRAFT's findings: game feel (coyote time, buffering, variable jump, acceleration, shake, hit-stop),
    recovery (checkpoints, one-key restart) and auto-pause."""
    p = os.path.join(order["project"], "js", "game.js"); s = open(p).read()
    for a, b in FEEL:
        if a not in s: raise RuntimeError(f"game.js does not contain the code this fix changes: {a[:60]}")
        s = s.replace(a, b)
    open(p, "w").write(s)
    return ["js/game.js"]


def fix(order):
    """Repair what the QA gate found: the defective build references a script that does not exist."""
    proj = order["project"]
    p = os.path.join(proj, "index.html"); s = open(p).read()
    s = s.replace('<script src="js/missing-boot.js"></script>\n', "")
    open(p, "w").write(s)
    return ["index.html"]


# ---------------------------------------------------------------- plan v3: the visual stage (production/visual.py)
ATLAS = os.path.join(REPO, "production", "kit", "atlas")
SHORTLIST = ["risograph", "linocut", "pixel-art", "neon-vector", "editorial-serif", "topographic"]


def styles(order):
    """design.styles: six atlas looks rendered (for real, by the atlas painters in Chromium) as Lantern Drift's key scene."""
    import subprocess
    out = order["out_dir"]
    S = json.load(open(os.path.join(ATLAS, "scenes", "atlas.json")))
    S["game"].update(title="Lantern Drift", mood="night", hud={"score": "07", "score_label": "EMBERS", "lives": 3, "best": "BEST 12", "pause": True})
    json.dump(S, open(os.path.join(out, "scene.json"), "w"), indent=1)
    subprocess.run(["node", os.path.join(ATLAS, "render.mjs"), os.path.join(out, "styles"), ",".join(SHORTLIST), "game", os.path.join(out, "scene.json")],
                   check=True, capture_output=True, timeout=600)
    D = {"product": "game", "scene": "scene.json", "recommended": "risograph", "reason": "warm ink on dark paper is lantern light: two plates, one glow, and it stays readable on a phone",
         "wildcard": "topographic", "references": [],
         "styles": [{"look": l, "image": f"styles/{l}/game.png", "why": f"{l}: a lantern carried through a flooded market, drawn this way, keeps the light the hero"} for l in SHORTLIST]}
    p = os.path.join(out, "styles.json"); json.dump(D, open(p, "w"), indent=1)
    return [p]


DESIGNS = [("a", "Market poster", "a festival poster pasted on a market wall", "huge stacked title left, lantern bottom right", "Bricolage Grotesque", "#14122b", "#f2a541", "loud and warm"),
           ("b", "Lantern log", "a night-watch logbook page", "small header, the lantern path across the middle, button bottom right", "Space Mono", "#f3efe4", "#1f6f5c", "quiet and methodical"),
           ("c", "Ink sign", "an enamel shop sign on a whitewashed wall", "centred badge with the title inside, everything symmetrical", "Alfa Slab One", "#f4e9d8", "#b3261e", "solid and old-fashioned")]


def designs(order, env):
    """design.designs: three title screens that differ in composition, type and palette (their renders are different pictures at 120 px in
    grayscale), drawn as a phone browser shows them, full screen and at desktop size, each with an app icon option drawn by VectorCraft."""
    import subprocess
    out = order["out_dir"]; X = []
    icon_concepts({"out_dir": out}, env)   # lantern.png, flame.png, wave.png (+ SVG): one icon option per design
    icon_ids = list(IDEAS)
    LAYOUT = ["place-content:start start;padding:10vh 6vw", "place-content:end end;padding:8vh 8vw;text-align:right", "place-content:center;text-align:center"]
    EXTRA = ["", "<div style='position:fixed;left:0;top:0;width:100%;height:34vh;background:{p}'></div>", "<div style='position:fixed;inset:auto 0 0 0;height:18vh;background:{p}'></div>"]
    for i, (did, name, idea, comp, face, bg, prim, flav) in enumerate(DESIGNS):
        d = os.path.join(out, did); os.makedirs(os.path.join(d, "fonts"), exist_ok=True)
        f = next(x for x in os.listdir(os.path.join(ATLAS, "fonts")) if x.startswith(face.lower().replace(" ", "-")))
        shutil.copyfile(os.path.join(ATLAS, "fonts", f), os.path.join(d, "fonts", f))
        txt = "#f5f0e6" if i == 0 else "#1d1d1b"
        open(os.path.join(d, "index.html"), "w").write(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Lantern Drift</title><style>@font-face{{font-family:D;src:url(fonts/{f})}}html,body{{margin:0;height:100%;background:{bg};color:{txt};font-family:D}}
main{{position:relative;height:100%;box-sizing:border-box;display:grid;{LAYOUT[i]};gap:18px}}h1{{margin:0;font-size:{[19, 8, 12][i]}vw;line-height:.9;color:{prim if i != 1 else txt}}}
button{{font:inherit;font-size:20px;min-height:52px;padding:0 24px;border:3px solid {prim};background:none;color:{txt};justify-self:{['start', 'end', 'center'][i]}}}</style></head>
<body>{EXTRA[i].format(p=prim)}<main><h1>Lantern<br>Drift</h1><p>{idea}</p><button>Light the lantern</button></main></body></html>""")
        subprocess.run(["node", os.path.join(ATLAS, "shoot.mjs"), os.path.join(d, "index.html"), d, "--play"], check=True, capture_output=True, timeout=300)
        X.append({"id": did, "style": "risograph", "name": name, "idea": idea, "composition": comp, "type": {"display": face, "body": face},
                  "palette": {"background": bg, "surface": bg, "primary": prim, "accent": ["#3fc1c9", "#f28c28", "#e4572e"][i], "text": txt}, "flavor": flav,
                  "html": f"{did}/index.html", "browser": f"{did}/browser.png", "phone": f"{did}/phone.png", "desktop": f"{did}/desktop.png", "play": f"{did}/play.png",
                  "icons": [{"id": icon_ids[i], "file": f"{icon_ids[i]}.png", "idea": IDEAS[icon_ids[i]]}]})
    p = os.path.join(out, "designs.json")
    json.dump({"product": "game", "style": "risograph", "icons_required": True, "recommended": "a", "reason": "the poster puts the title where a market crowd would see it first", "designs": X},
              open(p, "w"), indent=1)
    return [p]


LANTERN_SHOTS = {"version": 1, "product": "game", "shots": [
    {"id": "title", "name": "Title", "kind": "title", "steps": [], "wait_for": {"js": "typeof S !== 'undefined' && S.state === 'title' && document.getElementById('game').width > 0"}},
    {"id": "play", "name": "Mid-play", "kind": "play", "moment": "first-ember", "steps": [{"press": "Space"}], "wait_for": {"js": "S.state === 'play' && S.t > 0.5"}},
    {"id": "fail", "name": "The hit that leaves one flicker of flame", "kind": "fail", "steps": [{"press": "Space"}, {"wait": 400}, {"eval": "hurt(); hurt();"}], "wait_for": {"js": "S.state === 'play' && pl.hp === 1"}, "settle_ms": 30},
    {"id": "results", "name": "The lantern went out", "kind": "results", "moment": "lantern-out", "sequence": {"after_ms": 300}, "steps": [{"press": "Space"}, {"wait": 400}, {"eval": "hurt(); hurt(); hurt();"}], "wait_for": {"js": "S.state === 'over'"}}]}


def visual_direction(order, project):
    """design.direction (plan v3): the direction written from the chosen design, plus the shot list in the project."""
    D = json.load(open(direction(order)[0]))
    D["art"].update(style={"look": "risograph", "name": "Risograph Print", "design": "a", "from": "picked"}, target="art-direction/target/phone.png", references=[], accept_tells=[],
                    moments=[{"id": "first-ember", "name": "First ember", "what": "the first ember lands in the lantern and its flame grows a size", "why": "the first reward"},
                             {"id": "lantern-out", "name": "The lantern goes out", "what": "the flame shrinks to a wick and the screen goes dark around it", "why": "a fair, readable end"}],
                    shots="art-direction/shots.json")
    p = os.path.join(order["out_dir"], "direction.json"); json.dump(D, open(p, "w"), indent=1)
    os.makedirs(os.path.join(project, "art-direction"), exist_ok=True)
    json.dump(LANTERN_SHOTS, open(os.path.join(project, "art-direction", "shots.json"), "w"), indent=1)
    return [p]


def review(order, pack, gaps=()):
    """review.creative: the stand-in reviewer opens every capture, answers the four checks for every shot and judges each moment from
    its sequence; gaps (if any) become work orders."""
    sys.path.insert(0, REPO)
    from production import visual
    K = json.load(open(pack))
    shots, seqs = visual.shots_in(K), visual.moment_sequences(K)
    first = next(iter(shots.values()))[0]
    R = {"reviewer": "acceptance stand-in", "pack": pack, "coverage": {"viewed": [i["id"] for i in K["items"] if i["kind"] in ("screenshot", "target", "style", "reference")],
                                                                      "not_seen": [n["shot"] for n in K["not_seen"]]},
         "summary": "an assessment of the built screens against the chosen poster design and the risograph look",
         "checks": [{"shot": sid, **{k: {"ok": not any(g["shot"] == sid for g in gaps), "note": "looked at the phone and desktop captures at full size"} for k in visual.CHECKS}} for sid in shots],
         "moments": [{"id": m, "reads_as_event": True, "why": "the frame changes visibly between before, peak and after", "evidence": f[0]} for m, f in seqs.items()],
         "previous": [{"id": g["id"], "closed": True, "note": "the new shot shows it fixed"} for g in K.get("previous_gaps") or []],
         "matches": [{"against": "target", "claim": "the title is the first thing on the screen, as in the chosen frame", "evidence": [first, "target:phone"], "basis": "observed_render"}],
         "gaps": [dict(g, evidence=[shots[g["shot"]][0]], basis="observed_render") for g in gaps]}
    p = os.path.join(order["out_dir"], "review.json"); json.dump(R, open(p, "w"), indent=1)
    return [p]
