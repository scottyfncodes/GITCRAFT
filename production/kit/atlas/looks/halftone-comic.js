// 11 · Halftone Comic: a printed comic panel. Flat process colours with Ben-Day screens (real dots whose size follows the
// tone), bold black ink outlines with a heavier weight on the shadow side, an action burst and speed lines behind the
// hero, a panel border on a cream page, caption boxes for the HUD and one small onomatopoeia on the hero's path.
export const meta = { id: 'halftone-comic' };

const C = { ink: '#141018', paper: '#fbf3df', yellow: '#ffd21f', red: '#e4252b', magenta: '#e6007e', cyan: '#17a6e3', sky: '#ffe68a',
  blue: '#2457a6', purple: '#4a3a8c', hill: '#8fd3f0', white: '#fffdf6', orange: '#f7941d' };

// Ben-Day screen: dots on a rotated grid, radius from tone(x, y) in [0, 1], clipped to `clip`
function screen(g, clip, color, tone, cell = 9, angle = 0.26, box = null) {
  g.save(); g.clip(clip); g.fillStyle = color; g.beginPath();
  const [x0, y0, x1, y1] = box || [0, 0, 960, 540], ca = Math.cos(angle), sa = Math.sin(angle), R = Math.hypot(x1 - x0, y1 - y0);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  for (let v = -R / 2; v < R / 2; v += cell) for (let u = -R / 2; u < R / 2; u += cell) {
    const x = cx + u * ca - v * sa, y = cy + u * sa + v * ca;
    if (x < x0 - cell || x > x1 + cell || y < y0 - cell || y > y1 + cell) continue;
    const t = tone(x, y); if (t <= 0.02) continue;
    const r = cell * 0.62 * Math.sqrt(Math.min(1, t)); g.moveTo(x + r, y); g.arc(x, y, r, 0, Math.PI * 2);
  }
  g.fill(); g.restore();
}
// ink line with weight: a heavier pass offset to the lower right, then the even line
function ink(g, path, w = 3.5, heavy = 2.5) {
  g.save(); g.strokeStyle = C.ink; g.lineJoin = 'round'; g.lineCap = 'round';
  g.lineWidth = w + heavy; g.translate(heavy * 0.5, heavy * 0.6); g.stroke(path); g.restore();
  g.save(); g.strokeStyle = C.ink; g.lineJoin = 'round'; g.lineCap = 'round'; g.lineWidth = w; g.stroke(path); g.restore();
}
const rectP = (x, y, w, h) => { const p = new Path2D(); p.rect(x, y, w, h); return p; };
// a tapered stroke (speed line): a thin triangle from a to b
function taper(g, ax, ay, bx, by, w) {
  const dx = bx - ax, dy = by - ay, l = Math.hypot(dx, dy) || 1, nx = -dy / l * w / 2, ny = dx / l * w / 2;
  g.moveTo(ax + nx, ay + ny); g.lineTo(bx, by); g.lineTo(ax - nx, ay - ny); g.closePath();
}

export function game(ctx, S, L, W, H) {
  const r = L.rng(21), gy = S.ground_y != null ? S.ground_y : H * 0.8, mood = S.mood || 'day';
  // the page and the panel: the scene is set inside a black-bordered frame
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H);
  const m = 12, k = (W - 2 * m) / W, ky = (H - 2 * m) / H;
  ctx.save(); ctx.translate(m, m); ctx.scale(k, ky);
  ctx.save(); ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  const all = rectP(0, 0, W, H);

  // sky: a flat base with a Ben-Day screen that grows toward the horizon
  const skyBase = { dusk: C.sky, dawn: '#ffe0c2', day: '#bfe8fa', night: '#1f2b66' }[mood] || C.sky;
  const skyDot = { dusk: C.red, dawn: C.magenta, day: C.cyan, night: C.cyan }[mood] || C.red;
  ctx.fillStyle = skyBase; ctx.fillRect(0, 0, W, H);
  screen(ctx, all, skyDot, (x, y) => (mood === 'day' ? 0.12 + 0.3 * (y / gy) : mood === 'night' ? 0.25 * (1 - y / gy) : Math.max(0, (y / gy - 0.15)) * 0.85), 10, 0.26, [0, 0, W, gy + 20]);

  // the action burst: radiating speed lines from the hero, then a jagged starburst behind it
  const h = S.hero, hc = [h.x + h.size / 2, h.y + h.size / 2];
  ctx.fillStyle = C.ink; ctx.globalAlpha = 0.85; ctx.beginPath();
  for (let i = 0; i < 46; i++) { const a = (i / 46) * Math.PI * 2 + r() * 0.06, r0 = h.size * (1.05 + r() * 0.35), r1 = h.size * (2.4 + r() * 2.2);
    taper(ctx, hc[0] + Math.cos(a) * r1, hc[1] + Math.sin(a) * r1, hc[0] + Math.cos(a) * r0, hc[1] + Math.sin(a) * r0, 2 + r() * 3.5); }
  ctx.fill(); ctx.globalAlpha = 1;

  if (S.sun) {
    const { x, y, r: R } = S.sun, p = new Path2D(); p.arc(x, y, R, 0, Math.PI * 2);
    ctx.fillStyle = mood === 'night' ? C.white : C.yellow; ctx.fill(p);
    screen(ctx, p, mood === 'night' ? '#b9c3e6' : C.red, (xx, yy) => Math.max(0, (yy - y) / R) * 0.9, 7, 0.4, [x - R, y - R, x + R, y + R]);
    ink(ctx, p, 3.5, 2);
  }
  if (S.far && S.far.length) {
    const p = L.farPolygon(S, W, H); ctx.fillStyle = mood === 'night' ? '#3c4f99' : C.hill; ctx.fill(p);
    screen(ctx, p, mood === 'night' ? '#26346e' : C.cyan, (x, y) => 0.25 + 0.35 * ((y - 280) / 200), 8, 0.78);
    ink(ctx, p, 3, 1.5);
  }
  // mid blocks: blue towers, a dotted shadow side, yellow windows, ink outline
  const blocks = L.buildings(S).map(([x, y, w, hh]) => { let b = y + hh;
    for (const [qx, qy, qw] of S.platforms || []) if (qx < x + w && qx + qw > x && qy < b && qy > y + hh * 0.5) b = qy; return [x, y, w, b - y]; });
  for (const [x, y, w, hh] of blocks) {
    const p = rectP(x, y, w, hh); ctx.fillStyle = C.blue; ctx.fill(p);
    screen(ctx, rectP(x + w * 0.62, y, w * 0.38, hh), C.ink, () => 0.55, 6, 0.78, [x, y, x + w, y + hh]);
    ctx.fillStyle = C.yellow;
    for (let wy = y + 14; wy < y + hh - 14; wy += 22) for (let wx = x + 8; wx < x + w * 0.56; wx += 14) if (r() < 0.42) { ctx.fillRect(wx, wy, 7, 10); }
    ink(ctx, p, 3, 2);
  }
  // the starburst behind the hero sits over the town but under every platform
  const burst = new Path2D(), n = 18;
  for (let i = 0; i < n * 2; i++) { const a = (i / (n * 2)) * Math.PI * 2, rad = h.size * (i % 2 ? 0.62 : 0.95 + r() * 0.2); burst[i ? 'lineTo' : 'moveTo'](hc[0] + Math.cos(a) * rad, hc[1] + Math.sin(a) * rad); }
  burst.closePath(); ctx.fillStyle = C.yellow; ctx.fill(burst); ink(ctx, burst, 2.5, 0);
  // platforms: purple slabs, a yellow lip, a reversed (paper-coloured) dot screen deepening downward, heavy ink
  for (const [x, y, w, hh] of S.platforms || []) {
    const p = rectP(x, y, w, hh); ctx.fillStyle = C.purple; ctx.fill(p);
    screen(ctx, p, C.ink, (xx, yy) => Math.min(0.8, (yy - y - 14) / 140), 8, 0.78, [x, y, x + w, y + hh]);
    ctx.fillStyle = C.orange; ctx.fillRect(x, y, w, 10);
    ctx.fillStyle = C.ink; ctx.fillRect(x, y + 10, w, 3);
    ink(ctx, p, 4, 2.5);
  }
  for (const hz of S.hazards || []) {
    const p = L.hazardPath(hz); ctx.fillStyle = C.red; ctx.fill(p);
    if (hz.kind === 'block') screen(ctx, p, C.ink, () => 0.4, 6, 0.78, [hz.x, hz.y, hz.x + hz.w, hz.y + hz.h]);
    const md = Math.min(hz.w, hz.h); ink(ctx, p, md < 40 ? 2 : 3, md < 40 ? 1 : 2);
    if (hz.kind === 'spikes') { ctx.fillStyle = C.white; const n = Math.max(3, Math.round(hz.w / 22)), sw = hz.w / n;
      for (let i = 0; i < n; i++) { ctx.beginPath(); ctx.moveTo(hz.x + i * sw + sw / 2 - 1, hz.y + 8); ctx.lineTo(hz.x + i * sw + sw * 0.32, hz.y + hz.h * 0.7); ctx.lineTo(hz.x + i * sw + sw * 0.42, hz.y + hz.h * 0.7); ctx.closePath(); ctx.fill(); } }
  }
  // wind / motion streaks: tapered ink lines
  ctx.fillStyle = C.ink; ctx.beginPath();
  for (const ln of S.lines || []) for (let i = 0; i < ln.length - 1; i++) taper(ctx, ln[i][0], ln[i][1], ln[i + 1][0], ln[i + 1][1], 4);
  ctx.fill();
  // the trail: chunky motion dashes along an arc, or a plain ink string
  const t = S.trail || [];
  if (t.length > 1) {
    if (L.trailKind(S) === 'string') { ctx.strokeStyle = C.ink; ctx.lineWidth = 2.5; L.smooth(ctx, t); ctx.stroke(); }
    else { ctx.save(); ctx.strokeStyle = C.white; ctx.lineWidth = 9; ctx.lineCap = 'round'; ctx.setLineDash([16, 14]); L.smooth(ctx, t); ctx.stroke();
      ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.setLineDash([16, 14]); L.smooth(ctx, t); ctx.stroke(); ctx.restore(); }
  }
  for (const c of S.pickups || []) {
    const p = L.pickupPath(S, c), rr = c.r || 11; ctx.fillStyle = C.yellow; ctx.fill(p);
    screen(ctx, p, C.orange, (x, y) => ((x - c.x) + (y - c.y)) / rr * 0.6, 4, 0.4, [c.x - rr * 1.3, c.y - rr * 1.3, c.x + rr * 1.3, c.y + rr * 1.3]);
    ink(ctx, p, rr < 14 ? 2 : 2.5, rr < 14 ? 1 : 1.5);
    ctx.fillStyle = C.white; ctx.beginPath(); ctx.ellipse(c.x - rr * 0.35, c.y - rr * 0.35, rr * 0.18, rr * 0.32, 0.7, 0, Math.PI * 2); ctx.fill();
  }
  // the hero: paper white, red accent, ink with a heavier shadow side
  const hero = L.heroPath(h); ctx.fillStyle = C.white; ctx.fill(hero);
  screen(ctx, hero, '#b9c3e6', (x, y) => Math.max(0, ((x - h.x) / h.size + (y - h.y) / h.size - 1.1)) * 0.9, 5, 0.78, [h.x, h.y, h.x + h.size, h.y + h.size]);
  if (h.accent) { const a = L.heroPath(h, 'accent'); ctx.fillStyle = C.red; ctx.fill(a); ink(ctx, a, 2, 0); }
  ink(ctx, hero, 3.2, 2);
  const e = L.heroEye(h); if (e) { ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.15, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.white; ctx.beginPath(); ctx.arc(e.x - e.r * 0.35, e.y - e.r * 0.4, e.r * 0.38, 0, Math.PI * 2); ctx.fill(); }
  // one small onomatopoeia on the hero's path
  if (t.length > 1) {
    const mid = t[Math.max(0, Math.floor(t.length / 2) - 1)], word = L.trailKind(S) === 'string' ? 'WHOOSH!' : 'HOP!';
    ctx.save(); ctx.translate(mid[0] - 70, mid[1] - 18); ctx.rotate(-0.16); ctx.font = '400 34px Bangers'; ctx.lineJoin = 'round';
    ctx.strokeStyle = C.ink; ctx.lineWidth = 8; ctx.strokeText(word, 0, 0); ctx.fillStyle = C.yellow; ctx.fillText(word, 0, 0);
    ctx.lineWidth = 1.5; ctx.strokeText(word, 0, 0); ctx.restore();
  }
  ctx.restore();   // end clip

  // HUD: caption boxes inside the panel (yellow, ink border, a hard offset shadow)
  const hud = S.hud || {};
  const caption = (x, y, w, hh, fill = C.yellow) => { ctx.fillStyle = C.ink; ctx.fillRect(x + 5, y + 5, w, hh); ctx.fillStyle = fill; ctx.fillRect(x, y, w, hh);
    ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.strokeRect(x, y, w, hh); };
  ctx.font = '400 50px Bangers'; const sw = ctx.measureText(String(hud.score ?? '')).width;
  ctx.font = '400 18px Bangers'; const lw = ctx.measureText(String(hud.score_label ?? '')).width;
  const cw = Math.max(sw + 32, lw + 32, (hud.lives != null ? Math.max(3, hud.lives) * 26 + 30 : 0), 120);
  caption(18, 16, cw, hud.lives != null ? 112 : 84);
  ctx.textBaseline = 'alphabetic';
  if (hud.score_label) { ctx.font = '400 18px Bangers'; ctx.fillStyle = C.ink; ctx.fillText(String(hud.score_label), 32, 40); }
  if (hud.score != null) { ctx.font = '400 50px Bangers'; ctx.lineJoin = 'round'; ctx.strokeStyle = C.ink; ctx.lineWidth = 6; ctx.strokeText(String(hud.score), 32, 88);
    ctx.fillStyle = C.red; ctx.fillText(String(hud.score), 32, 88); }
  if (hud.lives != null) for (let i = 0; i < Math.max(3, hud.lives); i++) {
    const x = 40 + i * 26, y = 108, p = new Path2D();
    p.moveTo(x, y + 8); p.bezierCurveTo(x - 14, y - 2, x - 7, y - 12, x, y - 4); p.bezierCurveTo(x + 7, y - 12, x + 14, y - 2, x, y + 8); p.closePath();
    ctx.fillStyle = i < hud.lives ? C.red : C.white; ctx.fill(p); ctx.strokeStyle = C.ink; ctx.lineWidth = 2.5; ctx.stroke(p);
  }
  if (hud.pause) { const x = W - 50, y = 50; ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(x + 4, y + 4, 25, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.white; ctx.beginPath(); ctx.arc(x, y, 25, 0, Math.PI * 2); ctx.fill(); ctx.strokeStyle = C.ink; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = C.ink; ctx.fillRect(x - 9, y - 11, 6, 22); ctx.fillRect(x + 3, y - 11, 6, 22); }
  if (hud.best) { ctx.font = '400 22px Bangers'; const bw = ctx.measureText(String(hud.best)).width;
    caption(W - 96 - bw - 24, 32, bw + 24, 36, C.white); ctx.fillStyle = C.ink; ctx.fillText(String(hud.best), W - 96 - bw - 12, 59); }
  ctx.restore();   // end panel transform

  // the panel border, then a little paper grain over everything
  ctx.strokeStyle = C.ink; ctx.lineWidth = 6; ctx.strokeRect(m, m, W - 2 * m, H - 2 * m);
  L.grain(ctx, W, H, 0.035, 41);
}

const DOT = (c, s = 10, r = 2.6) => `radial-gradient(circle,${c} ${r}px,transparent ${r + 0.7}px) 0 0/${s}px ${s}px`;
export const appCss = `
.app{--ink:#141018;--paper:#fbf3df;--yellow:#ffd21f;--red:#d1121a;--cyan:#17a6e3;--blue:#2457a6;
  font-family:'Comic Neue',sans-serif;background:var(--paper);color:var(--ink);display:flex;flex-direction:column;padding:54px 18px 0;box-sizing:border-box;isolation:isolate}
.app::before{content:'';position:absolute;left:0;right:0;top:0;height:240px;background:${DOT('rgba(23,166,227,.35)', 11, 2.4)};z-index:-1;
  -webkit-mask:linear-gradient(#000,transparent);mask:linear-gradient(#000,transparent)}
.top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.brand{font-family:Bangers;font-size:40px;letter-spacing:.03em;color:var(--yellow);-webkit-text-stroke:2px var(--ink);paint-order:stroke fill;text-shadow:3px 3px 0 var(--ink);transform:rotate(-2deg)}
.place{font-size:15px;font-weight:700;background:#fff;border:3px solid var(--ink);padding:6px 10px;box-shadow:3px 3px 0 var(--ink)}
.hero{position:relative;margin-top:26px;background:var(--yellow);border:4px solid var(--ink);padding:30px 18px 20px;box-shadow:6px 6px 0 var(--ink);isolation:isolate}
.hero .burst{position:absolute;z-index:-1;pointer-events:none}
.hero::before{content:'';position:absolute;inset:0;background:${DOT('#e4252b', 10, 3)};z-index:-1;
  -webkit-mask:radial-gradient(circle at 100% 100%,#000 0,transparent 36%);mask:radial-gradient(circle at 100% 100%,#000 0,transparent 36%)}
.label{position:absolute;left:-4px;top:-18px;background:#fff;border:3px solid var(--ink);padding:3px 10px;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:.04em}
.value{font-family:Bangers;font-size:92px;line-height:.95;letter-spacing:.02em;color:var(--red);-webkit-text-stroke:3px var(--ink);paint-order:stroke fill;text-shadow:4px 4px 0 var(--ink);margin:4px 0 8px}
.sub{font-size:16px;font-weight:700;background:rgba(255,253,246,.0)}
.status{position:relative;display:inline-block;margin-top:18px;background:#fff;border:3px solid var(--ink);border-radius:22px;padding:7px 16px;font-weight:700;font-size:15px}
.status::after{content:'';position:absolute;left:22px;top:-13px;width:16px;height:13px;background:#fff;border:3px solid var(--ink);border-bottom:0;border-right:0;transform:skewX(35deg);clip-path:polygon(0 0,100% 100%,0 100%)}
.rows-title{font-family:Bangers;font-weight:400;font-size:26px;letter-spacing:.04em;margin:28px 0 10px;color:var(--ink)}
.rows{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.rows li{display:grid;grid-template-columns:70px 1fr auto;align-items:center;min-height:54px;padding:0 12px;background:#fff;border:3px solid var(--ink);font-size:16px;font-weight:700}
.rows li:nth-child(2){transform:rotate(-.6deg)}
.rows .t{font-family:Bangers;font-weight:400;font-size:26px;letter-spacing:.03em;color:var(--blue)}
.rows .s{font-size:14px;font-weight:700;padding:4px 9px;border:2.5px solid var(--ink);background:#bfe8fa}
.rows li[data-state=late] .s{background:var(--red);color:#fff}
.rows li[data-state=few] .s{background:var(--yellow)}
.cta{margin:20px 0 0;height:60px;border:4px solid var(--ink);border-radius:0;background:var(--red);color:#fff;font:400 28px Bangers;letter-spacing:.06em;box-shadow:6px 6px 0 var(--ink);
  -webkit-text-stroke:1.5px var(--ink);paint-order:stroke fill}
.tabs{margin:auto -18px 0;display:grid;grid-template-columns:repeat(4,1fr);gap:6px;padding:10px 12px 30px;background:#fff;border-top:4px solid var(--ink)}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:50px;font-size:14px;font-weight:700;color:#3d3747;border:3px solid transparent}
.tabs a.on{background:var(--yellow);border-color:var(--ink);color:var(--ink);box-shadow:3px 3px 0 var(--ink)}
.ic{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
.speed{position:absolute;left:0;width:100%;pointer-events:none;z-index:-1}
`;

// a starburst behind the hero number, and speed lines filling the page above the tab bar
export function appDecor(root) {
  const ns = 'http://www.w3.org/2000/svg', hero = root.querySelector('.hero');
  if (hero) {
    let d = ''; for (let i = 0; i < 34; i++) { const a = (i / 34) * Math.PI * 2, r = i % 2 ? 58 : 74 - (i % 4) * 3; d += (i ? 'L' : 'M') + (75 + Math.cos(a) * r).toFixed(1) + ' ' + (75 + Math.sin(a) * r).toFixed(1); }
    const b = document.createElementNS(ns, 'svg'); b.setAttribute('class', 'burst'); b.setAttribute('viewBox', '0 0 150 150'); b.setAttribute('preserveAspectRatio', 'none');
    // fit the burst to the number's own ink box so it never runs under the body text
    const v = hero.querySelector('.value');
    if (v && v.firstChild) { const rg = document.createRange(); rg.selectNodeContents(v); const tr = rg.getBoundingClientRect(), hr = hero.getBoundingClientRect();
      const w = Math.min(tr.width + 56, hr.width - 16), hh = v.offsetHeight + 10;
      b.style.cssText = `left:${tr.left - hr.left - 26}px;top:${v.offsetTop - 6}px;width:${w}px;height:${hh}px`; }
    b.innerHTML = `<path d="${d}Z" fill="#fff" stroke="#141018" stroke-width="3" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>`;
    hero.prepend(b);
  }
  const tabs = root.querySelector('.tabs'), cta = root.querySelector('.cta');
  if (tabs && cta) {
    const top = cta.offsetTop + cta.offsetHeight + 14, hgt = tabs.offsetTop - top; if (hgt < 40) return;
    const sv = document.createElementNS(ns, 'svg'); sv.setAttribute('class', 'speed'); sv.style.top = top + 'px'; sv.style.height = hgt + 'px';
    sv.setAttribute('viewBox', `0 0 390 ${hgt}`); sv.setAttribute('preserveAspectRatio', 'none');
    let s = ''; for (let i = 0; i < 9; i++) { const y = 10 + i * (hgt - 20) / 8, x0 = 20 + ((i * 53) % 90), w = 2 + (i % 3) * 1.4; s += `<path d="M${x0} ${y - w / 2}L${x0 + 240 + (i % 4) * 22} ${y}L${x0} ${y + w / 2}Z" fill="#141018" opacity=".8"/>`; }
    sv.innerHTML = s; root.prepend(sv);
  }
}
