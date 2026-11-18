// 2 · Neon Vector: a vector-arcade monitor. Every shape is an outline that emits light: strokes are drawn on a light
// layer and composited additively ('lighter') in several blurred passes (wide haze, halo, tight bloom) plus the sharp
// core. Solid near-black occluders keep depth readable; small text is a solid fill, never glowed.
export const meta = { id: 'neon-vector' };

const C = { void: '#05030b', deep: '#0d0620', haze: '#2a0b3d', mag: '#ff3df0', cyan: '#3ef2ff', amber: '#ffb43a', hot: '#ff2a5f',
  violet: '#8f5bff', ice: '#e9fdff', mint: '#5dffb0', occ: '#07040f' };

// paint with `draw` on a light layer, then add it to the canvas as glow
function light(ctx, W, H, draw, passes = [[22, 0.45], [8, 0.75], [2.5, 0.9]]) {
  const s = ctx.getTransform().a || 1;
  const [c, g] = offscreen(W * s, H * s); g.scale(s, s); g.lineCap = 'round'; g.lineJoin = 'round';
  draw(g);
  ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalCompositeOperation = 'lighter';
  for (const [b, a] of passes) { ctx.filter = `blur(${b * s}px)`; ctx.globalAlpha = a; ctx.drawImage(c, 0, 0); }
  ctx.filter = 'none'; ctx.globalAlpha = 1; ctx.drawImage(c, 0, 0);
  ctx.restore();
}
let offscreen, mix;

// a neon tube: coloured stroke with a whiter core
function tube(g, path, color, w = 2.4, core = 0.55) {
  g.strokeStyle = color; g.lineWidth = w; path ? g.stroke(path) : g.stroke();
  g.strokeStyle = mix(color, '#ffffff', core); g.lineWidth = Math.max(0.8, w * 0.38); path ? g.stroke(path) : g.stroke();
}

export function game(ctx, S, L, W, H) {
  offscreen = L.offscreen; mix = L.mix;
  const r = L.rng(11), gy = S.ground_y != null ? S.ground_y : H * 0.8;
  const night = S.mood === 'night', day = S.mood === 'day';

  // the dark tube face, with a faint coloured horizon haze
  const bg = ctx.createLinearGradient(0, 0, 0, H);
  bg.addColorStop(0, C.void); bg.addColorStop(0.55, day ? '#0b0a2a' : C.deep); bg.addColorStop(gy / H, day ? '#1a1240' : C.haze); bg.addColorStop(1, C.void);
  ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
  const hz = ctx.createRadialGradient(W / 2, gy, 10, W / 2, gy, W * 0.6);
  hz.addColorStop(0, 'rgba(255,61,240,.22)'); hz.addColorStop(1, 'rgba(255,61,240,0)');
  ctx.fillStyle = hz; ctx.fillRect(0, 0, W, H);

  // pass 1: stars, sun or moon, wireframe hills, the floor grid
  light(ctx, W, H, (g) => {
    for (let i = 0; i < 70; i++) { const x = r() * W, y = r() * gy * 0.75, s = r();
      g.fillStyle = s > 0.9 ? C.cyan : 'rgba(233,253,255,.55)'; g.fillRect(x, y, s > 0.85 ? 1.8 : 1, s > 0.85 ? 1.8 : 1); }
    if (S.sun) {
      const { x, y, r: R } = S.sun;
      if (night) {   // a crescent moon, two arcs
        g.beginPath(); g.arc(x, y, R, Math.PI * 0.35, Math.PI * 1.65); g.arc(x + R * 0.45, y, R * 0.8, Math.PI * 1.45, Math.PI * 0.55, true); g.closePath();
        tube(g, null, C.ice, 2.4, 0.4);
      } else {       // a striped synth sun: horizontal tubes inside the disc, amber at the top to magenta at the base
        for (let k = 0; k < 14; k++) {
          const t = k / 13, yy = y - R + t * 2 * R, half = Math.sqrt(Math.max(0, R * R - (yy - y) ** 2));
          if (t > 0.5 && (k % 2)) continue;
          g.beginPath(); g.moveTo(x - half, yy); g.lineTo(x + half, yy); tube(g, null, mix(C.amber, C.mag, t), t > 0.5 ? 2.6 : 1.8, 0.35);
        }
        g.beginPath(); g.arc(x, y, R + 9, 0, Math.PI * 2); g.globalAlpha = 0.5; tube(g, null, C.amber, 1.4, 0.2); g.globalAlpha = 1;
      }
    }
    if (S.far && S.far.length) {   // wire mountains: the ridge, contour copies falling to the horizon, vertex struts
      const base = Math.max(gy, ...S.far.map((p) => p[1]) ) + 6;
      for (const [k, a] of [[0.36, 0.55], [0.7, 0.32]]) {
        g.globalAlpha = a; g.beginPath(); S.far.forEach(([x, y], i) => g[i ? 'lineTo' : 'moveTo'](x, y + (base - y) * k)); tube(g, null, C.violet, 1.4, 0.2);
      }
      g.globalAlpha = 0.38; for (const [x, y] of S.far) { g.beginPath(); g.moveTo(x, y); g.lineTo(x + (x - W / 2) * 0.08, base); tube(g, null, C.violet, 1.2, 0.2); }
      g.globalAlpha = 1; g.beginPath(); S.far.forEach(([x, y], i) => g[i ? 'lineTo' : 'moveTo'](x, y)); tube(g, null, C.mag, 2.2, 0.45);
    }
    // the floor grid below the horizon: receding rows and rays from a vanishing point
    const vx = W / 2, vy = gy - 120;
    g.save(); g.beginPath(); g.rect(0, gy, W, H - gy); g.clip();
    g.globalAlpha = 0.34; g.lineWidth = 1.1;
    for (let i = -14; i <= 14; i++) { const bx = vx + i * 90; g.beginPath(); g.moveTo(vx + (bx - vx) * ((gy - vy) / (H + 400 - vy)), gy); g.lineTo(bx, H + 400); g.strokeStyle = C.mag; g.stroke(); }
    for (let i = 0; i < 9; i++) { const y = gy + (H - gy) * Math.pow(i / 8, 1.9); g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.strokeStyle = C.mag; g.stroke(); }
    g.restore(); g.globalAlpha = 1;
    g.beginPath(); g.moveTo(0, gy); g.lineTo(W, gy); g.globalAlpha = 0.7; tube(g, null, C.mag, 1.6, 0.4); g.globalAlpha = 1;
  });

  // pass 2: mid blocks as outlined towers with lit window dots (dark occluders first so the grid stays behind them)
  // a block stops at the top of a platform that stands in front of its base
  const blocks = L.buildings(S).map(([x, y, w, h]) => {
    let b = y + h;
    for (const [px, py, pw] of S.platforms || []) if (px < x + w && px + pw > x && py < b && py > y + h * 0.5) b = py;
    return [x, y, w, b - y];
  });
  if (blocks.length) {
    ctx.fillStyle = C.occ; for (const [x, y, w, h] of blocks) ctx.fillRect(x, y, w, h);
    light(ctx, W, H, (g) => {
      for (const [x, y, w, h] of blocks) {
        g.beginPath(); g.moveTo(x, y + h); g.lineTo(x, y); g.lineTo(x + w, y); g.lineTo(x + w, y + h); tube(g, null, C.violet, 1.6, 0.35);
        if (h > 150 && r() > 0.3) { g.beginPath(); g.moveTo(x + w * 0.5, y); g.lineTo(x + w * 0.5, y - 18); tube(g, null, C.violet, 1.2, 0.3);
          g.fillStyle = C.hot; g.fillRect(x + w * 0.5 - 1.5, y - 21, 3, 3); }
        for (let wy = y + 14; wy < y + h - 12; wy += 18) for (let wx = x + 8; wx < x + w - 8; wx += 12) {
          if (r() < 0.32) { g.fillStyle = r() < 0.7 ? 'rgba(62,242,255,.75)' : 'rgba(255,180,58,.8)'; g.fillRect(wx, wy, 4, 2); }
        }
      }
    }, [[14, 0.35], [4, 0.6]]);
  }

  // pass 3: platforms: dark slabs with a bright walkable rim and a perspective grid inside
  const plats = S.platforms || [];
  if (plats.length) {
    for (const [x, y, w, h] of plats) { ctx.fillStyle = C.occ; ctx.fillRect(x, y, w, h); }
    light(ctx, W, H, (g) => {
      for (const [x, y, w, h] of plats) {
        g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
        const vx = x + w / 2, far = y - 340;
        g.globalAlpha = 0.42; g.lineWidth = 1.1; g.strokeStyle = C.cyan;
        for (let i = -20; i <= 20; i++) { const tx = vx + i * 34; g.beginPath(); g.moveTo(tx, y); g.lineTo(vx + (tx - vx) * ((y + 600 - far) / (y - far)), y + 600); g.stroke(); }
        for (let i = 1; i < 12; i++) { const yy = y + 6 + Math.pow(i / 11, 1.7) * h; g.beginPath(); g.moveTo(x, yy); g.lineTo(x + w, yy); g.stroke(); }
        g.restore(); g.globalAlpha = 1;
        g.beginPath(); g.moveTo(x, y + h); g.lineTo(x, y); g.lineTo(x + w, y); g.lineTo(x + w, y + h); tube(g, null, C.cyan, 1.8, 0.4);
        g.beginPath(); g.moveTo(x + 1, y + 1); g.lineTo(x + w - 1, y + 1); tube(g, null, C.cyan, 3.4, 0.7);
      }
    });
  }

  // pass 4: the action layer: streaks, hazards, trail, pickups, hero
  const hero = L.heroPath(S.hero), accent = S.hero.accent ? L.heroPath(S.hero, 'accent') : null;
  for (const hz of S.hazards || []) { ctx.fillStyle = 'rgba(255,42,95,.10)'; ctx.fill(L.hazardPath(hz)); }
  ctx.fillStyle = C.occ; ctx.fill(hero);
  ctx.fillStyle = 'rgba(62,242,255,.10)'; ctx.fill(hero);
  light(ctx, W, H, (g) => {
    g.globalAlpha = 0.6; for (const ln of S.lines || []) { L.smooth(g, ln); g.setLineDash([40, 10, 6, 10]); tube(g, null, C.cyan, 1.4, 0.4); } g.setLineDash([]); g.globalAlpha = 1;
    for (const hz of S.hazards || []) {
      const p = L.hazardPath(hz); tube(g, p, C.hot, 2.2, 0.45);
      if (hz.kind === 'block') { g.save(); g.clip(p); g.globalAlpha = 0.6; g.strokeStyle = C.hot; g.lineWidth = 1;
        for (let k = -hz.w - hz.h; k < hz.w + hz.h; k += 12) { g.beginPath(); g.moveTo(hz.x + k, hz.y); g.lineTo(hz.x + k + hz.h, hz.y + hz.h); g.stroke(); } g.restore(); g.globalAlpha = 1; }
      if (hz.kind === 'spikes') { g.beginPath(); g.moveTo(hz.x, hz.y + hz.h); g.lineTo(hz.x + hz.w, hz.y + hz.h); tube(g, null, C.hot, 2.6, 0.5); }
    }
    const t = S.trail || [];
    if (t.length > 1) {
      if (L.trailKind(S) === 'string') { L.smooth(g, t); tube(g, null, C.ice, 1.2, 0.3); }
      else { L.smooth(g, t); g.setLineDash([2, 13]); g.lineWidth = 3.4; g.strokeStyle = C.amber; g.stroke(); g.setLineDash([]);
        L.smooth(g, t); g.globalAlpha = 0.25; tube(g, null, C.amber, 1, 0.2); g.globalAlpha = 1; }
    }
    for (const c of S.pickups || []) {
      tube(g, L.pickupPath(S, c), C.amber, 2.2, 0.55);
      g.globalAlpha = 0.65; tube(g, L.pickupPath(S, { ...c, r: (c.r || 11) * 0.45 }), C.amber, 1.4, 0.6); g.globalAlpha = 1;
    }
    tube(g, hero, C.cyan, 3, 0.6);
    if (accent) tube(g, accent, C.mag, 2.6, 0.5);
    const e = L.heroEye(S.hero); if (e) { g.fillStyle = C.ice; g.beginPath(); g.arc(e.x, e.y, e.r * 0.9, 0, Math.PI * 2); g.fill(); }
  }, [[26, 0.5], [9, 0.85], [3, 1]]);

  // HUD: big numerals glow; labels are solid fills
  const hud = S.hud || {};
  ctx.textBaseline = 'alphabetic';
  // a dark bezel plate behind the score cluster keeps it clear of whatever the scene puts there
  ctx.font = '400 46px Audiowide'; const sw = Math.max(110, ctx.measureText(String(hud.score ?? '')).width + 28, 26 * Math.max(3, hud.lives || 0) + 30);
  ctx.save(); ctx.beginPath(); ctx.roundRect(20, 22, sw + 12, hud.lives != null ? 116 : 86, 12);
  ctx.fillStyle = 'rgba(5,3,11,.84)'; ctx.fill(); ctx.strokeStyle = 'rgba(143,91,255,.45)'; ctx.lineWidth = 1; ctx.stroke(); ctx.restore();
  if (hud.score_label) { ctx.font = '600 14px "Chakra Petch"'; ctx.fillStyle = '#b8f6ff'; ctx.fillText(String(hud.score_label).split('').join(' '), 36, 44); }
  if (hud.score != null) light(ctx, W, H, (g) => { g.font = '400 46px Audiowide'; g.lineWidth = 1.6; g.strokeStyle = C.mag; g.strokeText(hud.score, 34, 92);
    g.fillStyle = '#e04cd6'; g.fillText(hud.score, 34, 92); g.lineWidth = 0.8; g.strokeStyle = '#ffd6fb'; g.strokeText(hud.score, 34, 92); }, [[14, 0.6], [4, 0.8]]);
  const lives = hud.lives;
  if (lives != null) light(ctx, W, H, (g) => {
    for (let i = 0; i < Math.max(3, lives); i++) {
      const x = 44 + i * 26, y = 116; g.beginPath(); g.moveTo(x, y - 8); g.lineTo(x + 8, y); g.lineTo(x, y + 8); g.lineTo(x - 8, y); g.closePath();
      if (i < lives) { tube(g, null, C.cyan, 2, 0.5); g.fillStyle = 'rgba(62,242,255,.35)'; g.fill(); } else { g.globalAlpha = 0.3; tube(g, null, C.violet, 1.2, 0.1); g.globalAlpha = 1; }
    }
  }, [[8, 0.6]]);
  if (hud.pause) light(ctx, W, H, (g) => { g.beginPath(); g.roundRect(W - 82, 30, 48, 48, 10); tube(g, null, C.cyan, 2, 0.45);
    g.fillStyle = C.ice; g.fillRect(W - 65, 43, 4, 22); g.fillRect(W - 55, 43, 4, 22); }, [[10, 0.6], [3, 0.8]]);
  if (hud.best) { ctx.font = '600 15px "Chakra Petch"'; ctx.textAlign = 'right'; ctx.fillStyle = '#ffd28a'; ctx.fillText(String(hud.best), W - 100, 60); ctx.textAlign = 'left'; }

  // the tube's vignette
  const v = ctx.createRadialGradient(W / 2, H / 2, H * 0.45, W / 2, H / 2, W * 0.75);
  v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.55)'); ctx.fillStyle = v; ctx.fillRect(0, 0, W, H);
}

export const appCss = `
.app{--mag:#ff3df0;--cyan:#3ef2ff;--amber:#ffb43a;--hot:#ff4f7a;--ink:#ecf6ff;--dim:#a7b0d6;
  font-family:'Chakra Petch',sans-serif;color:var(--ink);background:#06040d;display:flex;flex-direction:column;padding:54px 20px 0;box-sizing:border-box;isolation:isolate}
.app::before{content:'';position:absolute;inset:0;z-index:-1;background:radial-gradient(120% 50% at 50% 0%,#1c0a33 0%,rgba(6,4,13,0) 60%),radial-gradient(90% 40% at 50% 100%,#1a0730 0%,rgba(6,4,13,0) 70%)}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px}
.brand{font-family:Audiowide;font-size:26px;letter-spacing:.04em;color:#bff9ff;text-shadow:0 0 6px rgba(62,242,255,.9),0 0 18px rgba(62,242,255,.55)}
.place{font-size:14px;font-weight:600;color:var(--dim);border:1px solid rgba(143,91,255,.6);border-radius:8px;padding:6px 10px}
.hero{position:relative;margin-top:20px;padding:20px 20px 22px;border:1.5px solid var(--cyan);border-radius:16px;overflow:hidden;
  background:linear-gradient(180deg,rgba(62,242,255,.06),rgba(255,61,240,.05));
  box-shadow:0 0 0 1px rgba(62,242,255,.15),0 0 18px rgba(62,242,255,.45),inset 0 0 22px rgba(62,242,255,.18)}
.hero>*{position:relative;z-index:1}
.hero .deco{position:absolute;right:0;bottom:0;width:100%;height:100%;z-index:0;pointer-events:none}
.label{font-size:14px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:#9fefff}
.value{font-family:Audiowide;font-size:78px;line-height:1;margin:10px 0 10px;color:rgba(255,61,240,.12);-webkit-text-stroke:2px #ff7df4;
  text-shadow:0 0 8px rgba(255,61,240,.95),0 0 26px rgba(255,61,240,.6),0 0 60px rgba(255,61,240,.35)}
.sub{font-size:15px;color:var(--ink)}
.status{display:inline-flex;align-items:center;gap:8px;margin-top:14px;font-size:14px;font-weight:600;color:#7dffc4;border:1.5px solid #5dffb0;border-radius:8px;padding:6px 12px;
  box-shadow:0 0 10px rgba(93,255,176,.45),inset 0 0 8px rgba(93,255,176,.2)}
.status::before{content:'';width:7px;height:7px;border-radius:50%;background:#5dffb0;box-shadow:0 0 8px #5dffb0}
.rows-title{font-family:Audiowide;font-weight:400;font-size:15px;letter-spacing:.12em;text-transform:uppercase;color:#d8b6ff;margin:24px 0 6px}
.rows{list-style:none;margin:0;padding:0}
.rows li{display:grid;grid-template-columns:70px 1fr auto;align-items:center;min-height:58px;font-size:16px;position:relative}
.rows li+li::before{content:'';position:absolute;left:0;right:0;top:0;height:1px;background:linear-gradient(90deg,rgba(143,91,255,0),rgba(143,91,255,.8),rgba(143,91,255,0));box-shadow:0 0 6px rgba(143,91,255,.8)}
.rows .t{font-family:Audiowide;font-size:19px;color:#bff9ff}
.rows .d{color:var(--ink)}
.rows .s{font-size:13px;font-weight:600;padding:5px 10px;border-radius:7px;border:1.5px solid #5dffb0;color:#7dffc4}
.rows li[data-state=late] .s{border-color:#ff4f7a;color:#ff8ba6}
.rows li[data-state=few] .s{border-color:#ffb43a;color:#ffcf7d}
.cta{margin:16px 0 0;height:56px;border:0;border-radius:12px;background:#ff3df0;color:#1a0420;font:400 19px Audiowide;letter-spacing:.06em;
  box-shadow:0 0 0 2px #ffb8f8 inset,0 0 18px rgba(255,61,240,.8),0 0 44px rgba(255,61,240,.4)}
.floor{position:absolute;left:0;right:0;bottom:0;width:100%;height:300px;z-index:-1;pointer-events:none}
.tabs{margin:auto -20px 0;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 4px 30px;background:rgba(8,5,18,.92);border-top:1px solid rgba(62,242,255,.55);box-shadow:0 -1px 14px rgba(62,242,255,.35)}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:48px;font-size:12px;font-weight:600;letter-spacing:.06em;color:#a7b0d6}
.tabs a.on{color:#bff9ff}
.tabs a.on .ic{filter:drop-shadow(0 0 4px #3ef2ff) drop-shadow(0 0 10px rgba(62,242,255,.7))}
.ic{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
`;

// a wireframe sun and perspective grid inside the hero panel, behind the text on the right
export function appDecor(root) {
  const hero = root.querySelector('.hero'); if (!hero) return;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg'); svg.setAttribute('class', 'deco'); svg.setAttribute('viewBox', '0 0 350 230'); svg.setAttribute('preserveAspectRatio', 'xMaxYMax slice');
  let s = '<defs><filter id="nvg" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>' +
    '<linearGradient id="nvf" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ff3df0" stop-opacity="0"/><stop offset="1" stop-color="#ff3df0" stop-opacity=".6"/></linearGradient></defs><g filter="url(#nvg)" fill="none" stroke-linecap="round" opacity=".55">';
  for (let k = 0; k < 6; k++) { const y = 16 + k * 8, hw = Math.sqrt(Math.max(0, 26 * 26 - (y - 40) ** 2)); if (k > 3 && k % 2) continue; s += `<path d="M${312 - hw} ${y}H${312 + hw}" stroke="${k < 4 ? '#ffb43a' : '#ff3df0'}" stroke-width="1.6"/>`; }
  s += '<path d="M200 150 240 118 270 136 310 104 350 128" stroke="#8f5bff" stroke-width="1.4"/>';
  for (let i = -6; i <= 6; i++) s += `<path d="M${280 + i * 10} 150 L${280 + i * 46} 230" stroke="url(#nvf)" stroke-width="1"/>`;
  for (let i = 0; i < 5; i++) { const y = 150 + 80 * Math.pow(i / 4, 1.8); s += `<path d="M160 ${y}H350" stroke="#ff3df0" stroke-opacity="${0.25 + i * 0.1}" stroke-width="1"/>`; }
  svg.innerHTML = s + '</g>'; hero.prepend(svg);
  // a receding floor grid fills the dark below the list, behind the button and the tab bar
  const floor = document.createElementNS(ns, 'svg'); floor.setAttribute('class', 'floor'); floor.setAttribute('viewBox', '0 0 390 260'); floor.setAttribute('preserveAspectRatio', 'none');
  let f = '<defs><linearGradient id="nvh" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#ff3df0" stop-opacity="0"/><stop offset=".6" stop-color="#ff3df0" stop-opacity=".35"/><stop offset="1" stop-color="#ff3df0" stop-opacity=".55"/></linearGradient></defs><g fill="none" stroke="url(#nvh)" stroke-width="1">';
  for (let i = -12; i <= 12; i++) f += `<path d="M${195 + i * 14} 40 L${195 + i * 70} 260"/>`;
  for (let i = 0; i < 8; i++) { const y = 40 + 220 * Math.pow(i / 7, 1.9); f += `<path d="M0 ${y}H390"/>`; }
  floor.innerHTML = f + '</g>'; root.prepend(floor);
}
