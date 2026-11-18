// 4 · Risograph Print: the scene is separated into three spot-ink plates (fluoro pink, medium blue, yellow). Each plate
// keeps a solid layer and a tone layer; tones are screened through a rotated dot screen (a different angle per ink), the
// plates are misregistered by a few pixels and multiplied onto off-white paper, with uneven ink density, speckle voids
// and paper grain. Overprints make the extra colours (pink+yellow = vermilion, pink+blue = violet).
export const meta = { id: 'risograph' };

const INK = { pink: '#ff48b0', blue: '#3255a4', yellow: '#ffe14a' };
const PAPER = '#f4eee1';
const PLATES = ['yellow', 'pink', 'blue'];
const SCREEN = { pink: [75, 7.5], blue: [15, 7], yellow: [0, 8] };      // angle (deg), cell (device px)
const SHIFT = { pink: [3, -2], blue: [0, 0], yellow: [-2, 3] };          // misregistration (device px)

export function game(ctx, S, L, W, H) {
  const s = ctx.getTransform().a || 1, cw = Math.round(W * s), ch = Math.round(H * s);
  const P = {};
  for (const k of PLATES) { const mk = () => { const [c, g] = L.offscreen(cw, ch); g.scale(s, s); g.lineCap = 'round'; g.lineJoin = 'round'; return g; }; P[k] = { solid: mk(), tone: mk() }; }
  const ink = (d) => `rgba(0,0,0,${d})`;
  const all = (fn) => { for (const k of PLATES) for (const g of [P[k].solid, P[k].tone]) { g.save(); fn(g); g.restore(); } };
  const knock = (path) => all((g) => { g.globalCompositeOperation = 'destination-out'; g.fillStyle = '#000'; g.fill(path); });
  // paint an area: knock out what is under it on every plate, then lay each ink at its density (1 = solid, < 1 = screened tone)
  const area = (path, inks, keep = false) => { if (!keep) knock(path);
    for (const [k, d] of Object.entries(inks)) { if (!d) continue; const g = d >= 1 ? P[k].solid : P[k].tone; g.fillStyle = typeof d === 'number' ? ink(Math.min(1, d)) : d(g); g.fill(path); } };
  const stroke = (k, w, draw, solid = true) => { const g = solid ? P[k].solid : P[k].tone; g.save(); g.strokeStyle = '#000'; g.lineWidth = w; draw(g); g.restore(); };
  const rect = (x, y, w, h) => { const p = new Path2D(); p.rect(x, y, w, h); return p; };
  const r = L.rng(17), gy = S.ground_y != null ? S.ground_y : H * 0.8, mood = S.mood || 'day';

  // sky: screened tone ramps; dusk is pink over yellow, day is a light blue screen, night is dense blue
  const sky = rect(0, 0, W, H);
  const ramp = (a, b) => (g) => { const gr = g.createLinearGradient(0, 0, 0, gy); gr.addColorStop(0, ink(a)); gr.addColorStop(1, ink(b)); return gr; };
  if (mood === 'night') area(sky, { blue: ramp(0.85, 0.55), pink: ramp(0.05, 0.3) });
  else if (mood === 'day') area(sky, { blue: ramp(0.24, 0.04), yellow: ramp(0, 0.38) });
  else area(sky, { pink: ramp(0.04, 0.55), yellow: ramp(0.12, 0.72) });

  if (S.sun) {   // a solid disc: vermilion (pink over yellow) by day and dusk, a paper moon at night
    const { x, y, r: R } = S.sun, p = new Path2D(); p.arc(x, y, R, 0, Math.PI * 2);
    if (mood === 'night') area(p, {}); else area(p, { pink: 1, yellow: 1 });
    const halo = new Path2D(); halo.arc(x, y, R + 18, 0, Math.PI * 2); halo.arc(x, y, R + 6, 0, Math.PI * 2, true);
    area(halo, mood === 'night' ? { yellow: 0.35 } : { yellow: 0.9 }, true);
  }
  if (S.far && S.far.length) area(L.farPolygon(S, W, H), { blue: 0.42, pink: 0.38 });

  // mid blocks: violet (blue tone over pink tone), paper window knock-outs printed yellow
  const blocks = L.buildings(S).map(([x, y, w, h]) => { let b = y + h;
    for (const [qx, qy, qw] of S.platforms || []) if (qx < x + w && qx + qw > x && qy < b && qy > y + h * 0.5) b = qy; return [x, y, w, b - y]; });
  for (const [x, y, w, h] of blocks) {
    area(rect(x, y, w, h), { blue: 0.72, pink: 0.5 });
    area(rect(x + w * 0.64, y, w * 0.36, h), { blue: 0.9, pink: 0.62 });
    for (let wy = y + 14; wy < y + h - 14; wy += 20) for (let wx = x + 8; wx < x + w * 0.58; wx += 14) if (r() < 0.4) area(rect(wx, wy, 6, 9), { yellow: 1 });
  }
  // platforms: solid blue slabs with a vermilion lip and a stippled pink depth tone
  for (const [x, y, w, h] of S.platforms || []) {
    area(rect(x, y, w, h), { blue: 1, pink: (g) => { const gr = g.createLinearGradient(0, y, 0, y + h); gr.addColorStop(0, ink(0)); gr.addColorStop(1, ink(0.55)); return gr; } });
    area(rect(x, y, w, 9), { pink: 1, yellow: 1 });
    for (let k = y + 30, row = 0; k < y + h - 6; k += 30, row++) for (let bx = x + (row % 2) * 36; bx < x + w - 30; bx += 72) knock(rect(bx + 12, k, 22, 2.5));
  }
  for (const hz of S.hazards || []) {
    const p = L.hazardPath(hz); area(p, { pink: 1 });
    stroke('blue', 2.2, (g) => g.stroke(p));
    if (hz.kind !== 'path') area(p, { yellow: 0.5 }, true);
  }
  for (const ln of S.lines || []) stroke('blue', 3, (g) => { L.smooth(g, ln); g.stroke(); });
  const t = S.trail || [];
  if (t.length > 1) {
    if (L.trailKind(S) === 'string') stroke('blue', 2, (g) => { L.smooth(g, t); g.stroke(); });
    else stroke('pink', 5, (g) => { g.setLineDash([0.1, 14]); L.smooth(g, t); g.stroke(); });
  }
  for (const c of S.pickups || []) {
    const p = L.pickupPath(S, c), halo = L.pickupPath(S, { ...c, r: (c.r || 11) + 5 });
    area(halo, {}); area(p, { yellow: 1 }); stroke('blue', 2.6, (g) => g.stroke(p));
  }
  // hero: unprinted paper, a solid blue key line, a pink accent and a pink misregistered shadow plate
  const hero = L.heroPath(S.hero);
  P.pink.tone.save(); P.pink.tone.translate(7, 6); P.pink.tone.fillStyle = ink(0.75); P.pink.tone.fill(hero); P.pink.tone.restore();
  knock(hero);
  if (S.hero.accent) { const a = L.heroPath(S.hero, 'accent'); area(a, { pink: 1 }); }
  stroke('blue', 4, (g) => g.stroke(hero));
  const e = L.heroEye(S.hero); if (e) { const p = new Path2D(); p.arc(e.x, e.y, e.r * 1.05, 0, Math.PI * 2); area(p, { blue: 1 }); }

  // HUD on a paper label (knocked out of every plate), type in solid ink
  const hud = S.hud || {};
  const label = (x, y, w, h) => { const p = new Path2D(); p.roundRect(x, y, w, h, 4); knock(p); stroke('blue', 1.6, (g) => g.stroke(p)); };
  const txt = (k, str, x, y, font, align = 'left') => { const g = P[k].solid; g.save(); g.font = font; g.textAlign = align; g.fillStyle = '#000'; g.fillText(str, x, y); g.restore(); };
  P.blue.solid.font = '800 46px "Bricolage Grotesque"'; const sw = P.blue.solid.measureText(String(hud.score ?? '')).width;
  label(22, 22, Math.max(sw + 34, 130), hud.lives != null ? 122 : 92);
  if (hud.score_label) txt('pink', String(hud.score_label), 36, 46, '800 14px "Bricolage Grotesque"');
  if (hud.score != null) { txt('pink', String(hud.score), 37, 92, '800 46px "Bricolage Grotesque"'); txt('blue', String(hud.score), 34, 89, '800 46px "Bricolage Grotesque"'); }
  if (hud.lives != null) for (let i = 0; i < Math.max(3, hud.lives); i++) {
    const p = new Path2D(); p.arc(44 + i * 24, 118, 8, 0, Math.PI * 2);
    if (i < hud.lives) area(p, { pink: 1 }, true); else stroke('blue', 1.6, (g) => g.stroke(p));
  }
  if (hud.pause) { const p = new Path2D(); p.arc(W - 58, 54, 25, 0, Math.PI * 2); area(p, { blue: 1 }); area(rect(W - 66, 43, 6, 22), {}); area(rect(W - 56, 43, 6, 22), {}); }
  if (hud.best) { P.blue.solid.font = '700 16px "Bricolage Grotesque"'; const bw = P.blue.solid.measureText(String(hud.best)).width;
    label(W - 108 - bw - 12, 38, bw + 24, 32); txt('blue', String(hud.best), W - 108, 60, '700 16px "Bricolage Grotesque"', 'right'); }

  // print: screen each plate's tone, union with its solids, shift it, vary the ink, multiply onto paper
  const data = {}; for (const k of PLATES) data[k] = [P[k].solid.getImageData(0, 0, cw, ch).data, P[k].tone.getImageData(0, 0, cw, ch).data];
  const out = ctx.createImageData(cw, ch), o = out.data, paper = L.hex(PAPER), inks = {};
  for (const k of PLATES) { const [a, cell] = SCREEN[k], rad = a * Math.PI / 180; inks[k] = { rgb: L.hex(INK[k]).map((v) => v / 255), cos: Math.cos(rad) * 2 * Math.PI / cell, sin: Math.sin(rad) * 2 * Math.PI / cell, sh: SHIFT[k] }; }
  const n1 = L.noise2(4), n2 = L.noise2(9), rr = L.rng(23);
  for (let y = 0; y < ch; y++) for (let x = 0; x < cw; x++) {
    const i = (y * cw + x) * 4; let R = paper[0], G = paper[1], B = paper[2];
    const blotch = 0.8 + 0.2 * n1(x * 0.012, y * 0.012), fibre = n2(x * 0.5, y * 0.04), speck = rr();
    for (const k of PLATES) {
      const q = inks[k], sx = x - q.sh[0], sy = y - q.sh[1];
      if (sx < 0 || sy < 0 || sx >= cw || sy >= ch) continue;
      const j = (sy * cw + sx) * 4 + 3, solid = data[k][0][j] / 255, tone = data[k][1][j] / 255;
      let c = solid;
      if (tone > 0.01) { const u = x * q.cos - y * q.sin, v = x * q.sin + y * q.cos, scr = 0.5 + 0.25 * (Math.cos(u) + Math.cos(v));
        c = Math.max(c, Math.min(1, Math.max(0, (tone - scr) * 5 + 0.5))); }
      if (c <= 0) continue;
      c *= blotch * (k === 'blue' ? 0.97 : 0.93) * (speck < 0.018 ? 0.35 : 1) * (0.94 + 0.06 * fibre);
      R *= 1 - c * (1 - q.rgb[0]); G *= 1 - c * (1 - q.rgb[1]); B *= 1 - c * (1 - q.rgb[2]);
    }
    o[i] = R; o[i + 1] = G; o[i + 2] = B; o[i + 3] = 255;
  }
  ctx.putImageData(out, 0, 0);
  L.grain(ctx, W, H, 0.06, 31);
}

const GRAIN = "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .2 0 0 0 0 .18 0 0 0 0 .15 0 0 0 .55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")";
const DOTS = (c, s = 7, r = 1.9) => `radial-gradient(circle at center,${c} ${r}px,transparent ${r + 0.6}px) 0 0/${s}px ${s}px`;
export const appCss = `
.app{--pink:#ff48b0;--blue:#3255a4;--yellow:#ffe14a;--paper:#f4eee1;--ink:#1f1d3d;
  font-family:'Bricolage Grotesque',sans-serif;background:var(--paper);color:var(--ink);display:flex;flex-direction:column;padding:56px 22px 0;box-sizing:border-box;isolation:isolate}
.app::before{content:'';position:absolute;inset:0;background:${GRAIN};mix-blend-mode:multiply;opacity:.55;z-index:-1;pointer-events:none}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;position:relative}
.brand{font-weight:800;font-size:32px;letter-spacing:-.03em;color:var(--blue)}
.place{font-size:14px;font-weight:700;color:var(--ink);background:var(--yellow);padding:7px 12px;border-radius:3px;mix-blend-mode:multiply;transform:rotate(-1.5deg)}
.hero{position:relative;margin-top:22px;background:var(--pink);color:var(--ink);padding:20px 20px 22px;border-radius:4px;isolation:isolate}
.plate{position:absolute;pointer-events:none;border-radius:4px;background:${DOTS('#3255a4', 6, 1.7)};z-index:-1}
.label{font-size:15px;font-weight:700;letter-spacing:.02em}
.value{position:relative;font-weight:800;font-size:86px;line-height:.95;letter-spacing:-.05em;margin:8px 0 10px;color:var(--blue);mix-blend-mode:multiply}
.value .ghost{position:absolute;left:-5px;top:-4px;color:var(--yellow);z-index:-1;mix-blend-mode:multiply;pointer-events:none}
.sub{font-size:16px;font-weight:400}
.status{display:inline-block;margin-top:14px;background:var(--paper);color:var(--blue);font-weight:800;font-size:14px;padding:6px 12px;border-radius:3px}
.rows-title{font-weight:800;font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:#b5136f;margin:30px 0 4px}
.rows{list-style:none;margin:0;padding:0}
.rows li{display:grid;grid-template-columns:72px 1fr auto;align-items:center;min-height:58px;font-size:16px;border-bottom:2px dashed rgba(50,85,164,.55)}
.rows .t{font-weight:800;font-size:21px;color:var(--blue);letter-spacing:-.02em}
.rows .s{font-size:13px;font-weight:700;padding:5px 9px;border-radius:3px;border:2px solid var(--blue);color:var(--blue)}
.rows li[data-state=late] .s{background:var(--pink);border-color:var(--pink);color:var(--ink)}
.rows li[data-state=few] .s{background:var(--yellow);border-color:var(--yellow);color:var(--ink)}
.cta{position:relative;margin:22px 0 0;height:58px;border:0;border-radius:4px;background:var(--blue);color:var(--paper);font:800 20px 'Bricolage Grotesque';box-shadow:5px 5px 0 var(--pink);isolation:isolate}
.tabs{position:relative;margin:auto -22px 0;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 6px 30px;border-top:2.5px solid var(--blue);background:var(--paper);isolation:isolate}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:48px;font-size:13px;font-weight:700;color:#4a4870;position:relative}
.tabs a.on{color:var(--ink)}
.tabs a.on::before{content:'';position:absolute;top:-2px;width:38px;height:38px;border-radius:50%;background:var(--yellow);mix-blend-mode:multiply;transform:translate(3px,-4px);z-index:-1}
.tabs a.on .ic{color:var(--blue)}
.ic{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.deco{position:absolute;pointer-events:none;mix-blend-mode:multiply;z-index:0}
`;

// the overprinted hero number (a yellow plate under the blue one, out of register), and a halftone sun in the corner
export function appDecor(root) {
  const v = root.querySelector('.value');
  if (v) { const g = document.createElement('span'); g.className = 'ghost'; g.textContent = v.textContent; g.setAttribute('aria-hidden', 'true'); v.append(g); }
  // a blue halftone plate printed out of register behind the pink hero block
  const hero = root.querySelector('.hero');
  if (hero) { const b = document.createElement('div'); b.className = 'plate';
    b.style.cssText = `left:${hero.offsetLeft + 9}px;top:${hero.offsetTop + 9}px;width:${hero.offsetWidth}px;height:${hero.offsetHeight}px`; root.prepend(b); }
  // a halftone sun rising behind the tab bar: pink dots over a solid yellow disc, slightly out of register
  const tabs = root.querySelector('.tabs'), top = tabs ? tabs.offsetTop : 760;
  const sun = document.createElement('div'); sun.className = 'deco';
  sun.style.cssText = `left:50%;top:${top - 94}px;width:240px;height:240px;margin-left:-114px;border-radius:50%;background:${DOTS('#ff48b0', 6, 1.9)};z-index:-1`;
  const sun2 = document.createElement('div'); sun2.className = 'deco';
  sun2.style.cssText = `left:50%;top:${top - 82}px;width:200px;height:200px;margin-left:-104px;border-radius:50%;background:#ffe14a;z-index:-1`;
  root.prepend(sun2, sun);
}
