// 10 · Isometric Diorama: the scene re-projected onto a 2:1 isometric grid and set on a floating base. World x runs
// along the iso u axis, height (H - y) becomes block height, and the depth axis is shallow: a back terrace for the
// mid blocks and a front row where the play happens. Upright things (hero, pickups, flyers) are billboards with a
// shadow on whatever surface is below them. The projection is fitted to the frame, so any scene fits.
export const meta = { id: 'isometric' };
const TAU = Math.PI * 2, KZ = 0.8;
const SKY = { dusk: ['#ffd9c4', '#d4c6ef', '#ffcf7a'], dawn: ['#ffe6d6', '#cfe0f6', '#ffd892'], day: ['#d8eeff', '#f7efe4', '#ffd36b'], night: ['#2b2c63', '#5d5a9f', '#f4f0d8'] };
const BACK = { dusk: ['#efaaa8', '#d98993'], dawn: ['#f3b9a7', '#de9a92'], day: ['#a8d9bd', '#82bfa0'], night: ['#6f6aa8', '#57538f'] };
const C = { baseT: '#6c63a8', baseL: '#4f4891', baseR: '#3b3575', terT: '#a199dc', terL: '#8178c4', terR: '#655ca8',
  bT: '#d3cdf6', bL: '#a49be3', bR: '#7e74c9', winL: '#ffe2a8', winR: '#ffd085', winOff: 'rgba(60,50,130,.28)',
  pT: '#fff3e4', pL: '#ffb48c', pR: '#ef8a6b', pLine: 'rgba(214,150,110,.35)', red: '#ff6274', redD: '#d73f59', redT: '#ff8a96',
  hero: '#2a2462', accent: '#ff5f6d', coin: '#ffc947', coinD: '#de9418', ink: '#2a2462' };

export function game(ctx, S, L, W, H) {
  const mood = SKY[S.mood] ? S.mood : 'dusk', sky = SKY[mood], back = BACK[mood];
  const hasMid = (S.mid || []).length > 0, VB = hasMid ? 100 : 30, GV = hasMid ? 22 : 10, VF = 120, V0 = -26, VT = VB + GV + VF, VM = VB + GV + VF / 2, T = 26;   // depth layout
  const zg = S.ground_y != null ? H - S.ground_y : 0, hero = S.hero, HK = 1.3;
  // ---- fit the projection to the frame ------------------------------------------------------------------------
  const raw = (u, v, z) => [u + v, (v - u) / 2 - z * KZ];
  const pts = [[0, V0, -T], [W, V0, -T], [0, VT, -T], [W, VT, -T], [0, V0, zg], [W, V0, zg]];
  for (const [x, y] of S.far || []) pts.push([x, V0, H - y]);
  for (const [x, , , h] of (S.mid || []).map(([x, w, h]) => [x, 0, w, h])) pts.push([x, VB * 0.5, zg + h]);
  for (const [x, y, w] of S.platforms || []) pts.push([x, VT, H - y], [x + w, VB + GV, H - y]);
  for (const p of S.pickups || []) pts.push([p.x, VM, H - p.y + (p.r || 11) * 1.6]);
  for (const [x, y] of S.trail || []) pts.push([x, VM, H - y]);
  for (const ln of S.lines || []) for (const [x, y] of ln) pts.push([x, VM, H - y]);
  for (const z of S.hazards || []) pts.push([z.x, VM, H - z.y], [z.x + z.w, VM, H - z.y]);
  pts.push([hero.x, VM, H - hero.y + hero.size * (HK - 1) / KZ + 8], [hero.x + hero.size, VM, H - hero.y + hero.size * (HK - 1) / KZ + 8]);
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const p of pts) { const [X, Y] = raw(...p); x0 = Math.min(x0, X); x1 = Math.max(x1, X); y0 = Math.min(y0, Y); y1 = Math.max(y1, Y); }
  const RX = [28, W - 28], RY = [86, H - 44], s = Math.min((RX[1] - RX[0]) / (x1 - x0), (RY[1] - RY[0]) / (y1 - y0));
  const ox = (RX[0] + RX[1]) / 2 - (x0 + x1) / 2 * s, oy = (RY[0] + RY[1]) / 2 - (y0 + y1) / 2 * s;
  const P = (u, v, z) => { const [X, Y] = raw(u, v, z); return [ox + X * s, oy + Y * s]; };
  const poly = (pp, fill) => { ctx.beginPath(); pp.forEach(([x, y], i) => ctx[i ? 'lineTo' : 'moveTo'](x, y)); ctx.closePath(); ctx.fillStyle = fill; ctx.fill(); };
  const quad = (a, b, c, d, fill) => poly([P(...a), P(...b), P(...c), P(...d)], fill);
  const edge = (a, b, color, w = 1) => { const A = P(...a), B = P(...b); ctx.strokeStyle = color; ctx.lineWidth = w; ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke(); };
  function box(u0, u1, v0, v1, z0, z1, top, left, right, rim = 'rgba(255,255,255,.55)') {   // visible faces: -u (left), +v (right), top
    quad([u0, v0, z0], [u0, v1, z0], [u0, v1, z1], [u0, v0, z1], left);
    quad([u0, v1, z0], [u1, v1, z0], [u1, v1, z1], [u0, v1, z1], right);
    quad([u0, v0, z1], [u1, v0, z1], [u1, v1, z1], [u0, v1, z1], top);
    ctx.lineCap = 'round'; edge([u0, v1, z1], [u1, v1, z1], rim, 1.1); edge([u0, v0, z1], [u0, v1, z1], rim, 1.1); edge([u0, v1, z0], [u0, v1, z1], 'rgba(255,255,255,.22)', 1);
  }
  // the surface height under a point of the front row
  const plats = (S.platforms || []).map(([x, y, w, h]) => ({ u0: x, u1: x + w, z0: Math.max(0, H - (y + h)), z1: H - y }));
  const surface = (u, z) => plats.filter((p) => u >= p.u0 && u <= p.u1 && p.z1 <= z + 1).reduce((m, p) => Math.max(m, p.z1), 0);
  const shadow = (u, v, z, rx, k = 1) => { const [X, Y] = P(u, v, z); ctx.save(); ctx.globalAlpha = 0.22 * k; ctx.fillStyle = '#231d5a'; ctx.beginPath(); ctx.ellipse(X, Y, rx * s, rx * s * 0.5, 0, 0, TAU); ctx.fill(); ctx.restore(); };

  // ---- backdrop: sky, sun, the far hills as a stage flat --------------------------------------------------------
  const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, sky[0]); g.addColorStop(1, sky[1]); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const rg = ctx.createRadialGradient(W / 2, H * 0.55, 20, W / 2, H * 0.55, W * 0.6); rg.addColorStop(0, 'rgba(255,255,255,.35)'); rg.addColorStop(1, 'rgba(255,255,255,0)'); ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H);
  if (S.sun) { let [X, Y] = P(S.sun.x, V0 - 70, H - S.sun.y); X = Math.max(70, Math.min(W - 70, X)); Y = Math.max(90, Math.min(H * 0.45, Y)); const r = Math.max(22, S.sun.r * s * 1.1);
    const sg = ctx.createRadialGradient(X, Y, r * 0.8, X, Y, r * 2.6); sg.addColorStop(0, 'rgba(255,214,140,.55)'); sg.addColorStop(1, 'rgba(255,214,140,0)'); ctx.fillStyle = sg; ctx.beginPath(); ctx.arc(X, Y, r * 2.6, 0, TAU); ctx.fill();
    ctx.fillStyle = sky[2]; ctx.beginPath(); ctx.arc(X, Y, r, 0, TAU); ctx.fill(); ctx.fillStyle = 'rgba(255,255,255,.35)'; ctx.beginPath(); ctx.arc(X - r * 0.25, Y - r * 0.25, r * 0.55, 0, TAU); ctx.fill(); }
  // the floating diorama's own soft shadow
  ctx.save(); ctx.filter = `blur(${16}px)`; ctx.globalAlpha = 0.28; const sh = [P(0, V0, -T - 40), P(W, V0, -T - 40), P(W, VT, -T - 40), P(0, VT, -T - 40)].map(([x, y]) => [x, y + 26]);
  poly(sh, '#2c2468'); ctx.restore();
  if (S.far && S.far.length) {
    const f = S.far, card = (dv, col) => poly([P(f[0][0], V0 + dv, 0), ...f.map(([x, y]) => P(x, V0 + dv, H - y)), P(f[f.length - 1][0], V0 + dv, 0)], col);
    card(-6, back[1]); card(0, back[0]);
    ctx.save(); ctx.globalAlpha = 0.5; ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.2; ctx.beginPath(); f.forEach(([x, y], i) => { const [X, Y] = P(x, V0, H - y); ctx[i ? 'lineTo' : 'moveTo'](X, Y); }); ctx.stroke(); ctx.restore();
  }
  // ---- base slab, back terrace, buildings --------------------------------------------------------------------
  box(0, W, V0, VT, -T, 0, C.baseT, C.baseL, C.baseR, 'rgba(255,255,255,.3)');
  for (let u = 40; u < W; u += 40) edge([u, V0, 0], [u, VT, 0], 'rgba(255,255,255,.06)', 1);
  if (hasMid) box(0, W, V0, VB, 0, Math.max(zg, 6), C.terT, C.terL, C.terR);
  const tz = Math.max(zg, 6);
  for (const [x, w, h] of (S.mid || []).slice().sort((a, b) => (b[0] + b[1]) - (a[0] + a[1]))) {
    const va = VB * 0.18, vb = VB * 0.86, z1 = tz + h;
    box(x + 2, x + w - 2, va, vb, tz, z1, C.bT, C.bL, C.bR);
    quad([x + 7, va + 6, z1], [x + w - 7, va + 6, z1], [x + w - 7, vb - 6, z1], [x + 7, vb - 6, z1], '#bdb5ee');   // roof inset
    for (let z = tz + 14; z < z1 - 12; z += 18) {
      for (let v = va + 10; v < vb - 12; v += 18) quad([x + 2, v, z], [x + 2, v + 9, z], [x + 2, v + 9, z + 9], [x + 2, v, z + 9], ((x + z + v) % 3) ? C.winL : C.winOff);
      for (let u = x + 9; u < x + w - 12; u += 15) quad([u, vb, z], [u + 7, vb, z], [u + 7, vb, z + 9], [u, vb, z + 9], ((u * 7 + z) % 4) ? C.winOff : C.winR);
    }
  }
  // ---- front row: platforms, hazards and billboards in depth order -----------------------------------------------
  const items = [];
  for (const p of plats) items.push({ k: -p.u1 - 0.5, draw() {   // depth order along u: far end first; ties go to the box
    if (p.z0 > 0) { ctx.save(); ctx.filter = 'blur(4px)'; ctx.globalAlpha = 0.2; const sz = surface((p.u0 + p.u1) / 2, p.z0 - 1); quad([p.u0, VB + GV, sz], [p.u1, VB + GV, sz], [p.u1, VT, sz], [p.u0, VT, sz], '#231d5a'); ctx.restore(); }
    box(p.u0, p.u1, VB + GV, VT, p.z0, p.z1, C.pT, C.pL, C.pR);
    for (let u = p.u0 + 32; u < p.u1 - 4; u += 32) edge([u, VB + GV, p.z1], [u, VT, p.z1], C.pLine, 1);
    edge([p.u0, VM, p.z1], [p.u1, VM, p.z1], C.pLine, 1);
    for (let z = p.z1 - 16; z > p.z0 + 6; z -= 16) edge([p.u0, VT, z], [p.u1, VT, z], 'rgba(160,70,60,.14)', 1);
  } });
  for (const z of S.hazards || []) {
    const zb = H - (z.y + z.h), zt = H - z.y;
    if (z.kind === 'spikes') { const n = Math.max(3, Math.round(z.w / 26)), tw = z.w / n, base = surface(z.x + z.w / 2, zb);
      for (const v of [VB + GV + VF * 0.3, VB + GV + VF * 0.7]) for (let i = 0; i < n; i++) { const u0 = z.x + i * tw, uc = u0 + tw / 2, vh = Math.min(tw, VF * 0.36) / 2;
        items.push({ k: -uc + v * 1e-3, draw() { const apex = [uc, v, base + (zt - zb)];
          poly([P(u0, v - vh, base), P(u0, v + vh, base), P(...apex)], C.red);
          poly([P(u0, v + vh, base), P(u0 + tw, v + vh, base), P(...apex)], C.redD);
          ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.lineWidth = 1; const A = P(...apex), B = P(u0, v + vh, base); ctx.beginPath(); ctx.moveTo(A[0], A[1]); ctx.lineTo(B[0], B[1]); ctx.stroke(); } }); } }
    else if (z.kind === 'block') { const d = Math.max(z.w, 14);
      items.push({ k: -(z.x + z.w) - 0.5, draw() { box(z.x, z.x + z.w, VM - d / 2, VM + d / 2, zb, zt, C.redT, C.red, C.redD);
        for (let zz = zb + 18; zz < zt - 6; zz += 36) { quad([z.x, VM - d / 2, zz], [z.x, VM + d / 2, zz], [z.x, VM + d / 2, zz + 12], [z.x, VM - d / 2, zz + 12], '#fff4ee'); quad([z.x, VM + d / 2, zz], [z.x + z.w, VM + d / 2, zz], [z.x + z.w, VM + d / 2, zz + 12], [z.x, VM + d / 2, zz + 12], '#f3dcd6'); } } }); }
    else { const cx = z.x + z.w / 2, cz = H - (z.y + z.h / 2);
      items.push({ k: -cx, draw() { shadow(cx, VM, surface(cx, cz), z.w * 0.35, 0.8);
        const [X, Y] = P(cx, VM, cz); ctx.save(); ctx.translate(X, Y); ctx.scale(s * 1.15, s * 1.15); ctx.translate(-cx, -(z.y + z.h / 2)); ctx.fillStyle = '#3a2f6b'; ctx.fill(L.hazardPath(z)); ctx.restore(); } }); }
  }
  for (const c of S.pickups || []) { const cz = H - c.y, r = c.r || 11;
    items.push({ k: -c.x, draw() { shadow(c.x, VM, surface(c.x, cz), r * 0.8, 0.7);
      const [X, Y] = P(c.x, VM, cz), p = L.pickupPath(S, c), k = s * 1.55;
      ctx.save(); ctx.translate(X, Y); ctx.scale(k, k); ctx.translate(-c.x, -c.y);
      ctx.save(); ctx.translate(2.6, 1); ctx.fillStyle = C.coinD; ctx.fill(p); ctx.restore(); ctx.fillStyle = C.coin; ctx.fill(p);
      ctx.fillStyle = 'rgba(255,255,255,.6)'; ctx.beginPath(); ctx.ellipse(c.x - r * 0.3, c.y - r * 0.35, r * 0.18, r * 0.32, 0.5, 0, TAU); ctx.fill(); ctx.restore(); } }); }
  const hc = hero.x + hero.size / 2, hz = H - (hero.y + hero.size);
  items.push({ k: -hc + 0.01, draw() {
    const sz = surface(hc, hz); shadow(hc, VM, sz, hero.size * 0.42, Math.max(0.35, 1 - (hz - sz) / 260));
    const [X, Y] = P(hc, VM, hz), k = s * HK; ctx.save(); ctx.translate(X, Y); ctx.scale(k, k); ctx.translate(-hc, -(hero.y + hero.size));
    const hp = L.heroPath(hero); ctx.lineJoin = 'round'; ctx.strokeStyle = '#fff'; ctx.lineWidth = 5 / k * s * 1.3; ctx.stroke(hp);
    ctx.fillStyle = C.hero; ctx.fill(hp);
    ctx.save(); ctx.clip(hp); ctx.fillStyle = 'rgba(255,255,255,.12)'; ctx.fillRect(hero.x, hero.y, hero.size * 0.45, hero.size); ctx.restore();
    if (hero.accent) { ctx.fillStyle = C.accent; ctx.fill(L.heroPath(hero, 'accent')); }
    const e = L.heroEye(hero); if (e) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.5, 0, TAU); ctx.fill(); ctx.fillStyle = C.hero; ctx.beginPath(); ctx.arc(e.x + e.r * 0.4 * (hero.facing < 0 ? -1 : 1), e.y, e.r * 0.8, 0, TAU); ctx.fill(); }
    ctx.restore(); } });
  items.sort((a, b) => a.k - b.k).forEach((it) => it.draw());
  // overlays in the hero's plane: the trail and wind lines
  const t = S.trail || [];
  if (t.length > 1) { const pp = t.map(([x, y]) => P(x, VM, H - y));
    if (L.trailKind(S) === 'string') { ctx.strokeStyle = C.ink; ctx.globalAlpha = 0.85; ctx.lineWidth = 1.6; L.smooth(ctx, pp); ctx.stroke(); ctx.globalAlpha = 1;
      const [ax, ay] = pp[pp.length - 1]; ctx.fillStyle = C.ink; ctx.beginPath(); ctx.ellipse(ax, ay, 5, 2.6, 0, 0, TAU); ctx.fill(); }
    else { ctx.fillStyle = '#fff'; for (let i = 0; i < pp.length - 1; i++) for (let k = 0; k < 4; k++) { const a = k / 4, x = pp[i][0] + (pp[i + 1][0] - pp[i][0]) * a, y = pp[i][1] + (pp[i + 1][1] - pp[i][1]) * a;
      ctx.globalAlpha = 0.45 + (i * 4 + k) / (pp.length * 4) * 0.5; ctx.beginPath(); ctx.arc(x, y, 1.6 + (i * 4 + k) * 0.18, 0, TAU); ctx.fill(); } ctx.globalAlpha = 1; } }
  ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineCap = 'round'; ctx.lineWidth = 3;
  for (const ln of S.lines || []) { if (ln.length > 1) { L.smooth(ctx, ln.map(([x, y]) => P(x, VM, H - y))); ctx.stroke(); } }

  // ---- HUD: soft cards in Lexend --------------------------------------------------------------------------------
  const hud = S.hud || {}, card = (x, y, w, h, r) => { ctx.save(); ctx.shadowColor = 'rgba(42,36,98,.22)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 6; L.rr(ctx, x, y, w, h, r); ctx.fillStyle = '#fff'; ctx.fill(); ctx.restore(); };
  card(24, 20, 176, 62, 18);
  ctx.fillStyle = '#7a74b3'; ctx.font = '600 11px Lexend'; ctx.letterSpacing = '2px'; ctx.textBaseline = 'alphabetic'; ctx.fillText((hud.score_label || 'SCORE').toUpperCase(), 40, 43);
  ctx.fillStyle = C.ink; ctx.font = '800 30px Lexend'; ctx.letterSpacing = '0px'; ctx.fillText(String(hud.score ?? ''), 39, 72);
  if (hud.lives != null) { const n = Math.max(3, hud.lives); for (let i = 0; i < n; i++) { const cx = 182 - (n - 1 - i) * 17, cy = 62;   // lives as little iso cubes
    const top = i < hud.lives ? '#ff8a96' : '#e3e0f4', lf = i < hud.lives ? C.red : '#d3cfee', rt = i < hud.lives ? C.redD : '#c3bee6';
    ctx.fillStyle = top; ctx.beginPath(); ctx.moveTo(cx, cy - 6); ctx.lineTo(cx + 6, cy - 3); ctx.lineTo(cx, cy); ctx.lineTo(cx - 6, cy - 3); ctx.fill();
    ctx.fillStyle = lf; ctx.beginPath(); ctx.moveTo(cx - 6, cy - 3); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + 7); ctx.lineTo(cx - 6, cy + 4); ctx.fill();
    ctx.fillStyle = rt; ctx.beginPath(); ctx.moveTo(cx + 6, cy - 3); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + 7); ctx.lineTo(cx + 6, cy + 4); ctx.fill(); } }
  let rx = W - 24;
  if (hud.pause) { card(W - 76, 24, 52, 52, 26); ctx.fillStyle = C.ink; L.rr(ctx, W - 57, 39, 5, 22, 2); ctx.fill(); L.rr(ctx, W - 48, 39, 5, 22, 2); ctx.fill(); rx = W - 88; }
  if (hud.best) { ctx.font = '600 15px Lexend'; ctx.letterSpacing = '0.5px'; const bw = ctx.measureText(hud.best).width + 32; card(rx - bw, 30, bw, 40, 20);
    ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.fillText(hud.best, rx - bw / 2, 55); ctx.textAlign = 'left'; }
  ctx.letterSpacing = '0px';
}

// ---- the app ----------------------------------------------------------------------------------------------------
export const appCss = `
.app{--ink:#272163;--soft:#615c9c;--bg:#f2effa;font-family:Lexend,sans-serif;color:var(--ink);box-sizing:border-box;display:flex;flex-direction:column;padding:56px 20px 0;
  background:radial-gradient(120% 60% at 80% 0%,#ffe6d8 0%,rgba(255,230,216,0) 60%),linear-gradient(#f6f2fb,#ece8f8)}
.app *{box-sizing:border-box}
.top{display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:800;font-size:27px;letter-spacing:-.02em;display:flex;align-items:center;gap:10px}
.place{font-size:14px;color:var(--soft);background:#fff;padding:8px 12px;border-radius:99px;box-shadow:0 6px 16px -8px rgba(60,50,140,.35)}
.hero{position:relative;margin-top:20px;background:#fff;border-radius:26px;padding:20px 20px 20px;min-height:252px;box-shadow:0 22px 40px -22px rgba(52,42,140,.45),0 2px 0 rgba(52,42,140,.04)}
.label{font-size:14px;font-weight:600;color:var(--soft)}
.value{font-weight:800;font-size:62px;line-height:1;letter-spacing:-.03em;margin:8px 0 8px;position:relative;z-index:1}
.sub{font-size:15px;line-height:1.4;color:#4a4585;max-width:55%;position:relative;z-index:1}
.status{display:inline-block;margin-top:16px;font-size:14px;font-weight:600;color:#14603f;background:#dcf4e7;padding:6px 12px;border-radius:10px;position:relative;z-index:1}
.iso-art{position:absolute;right:6px;bottom:8px;width:150px;height:134px;pointer-events:none}
.rows-title{font-size:16px;font-weight:800;margin:24px 2px 10px}
.rows{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.rows li{display:grid;grid-template-columns:38px 56px 1fr auto;align-items:center;gap:0 8px;background:#fff;border-radius:18px;padding:10px 14px 10px 10px;min-height:64px;box-shadow:0 10px 22px -16px rgba(52,42,140,.45)}
.rows .cube{width:38px;height:38px;display:block}
.rows .t{font-weight:800;font-size:17px}
.rows .d{font-size:15px;color:#3f3a7a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rows .s{font-size:14px;font-weight:600;padding:5px 9px;border-radius:9px;background:#dcf4e7;color:#14603f;white-space:nowrap}
.rows li[data-state=late] .s{background:#ffe0e3;color:#b0243c}
.rows li[data-state=few] .s{background:#fff0cf;color:#835400}
.cta{margin:auto 0 24px;height:58px;border:0;border-radius:18px;background:linear-gradient(#5a4fd6,#463bbf);color:#fff;font:700 18px Lexend,sans-serif;letter-spacing:.01em;
  box-shadow:0 6px 0 #2f2690,0 18px 28px -14px rgba(52,42,160,.7);cursor:pointer}
.tabs{margin:0 -20px;display:grid;grid-template-columns:repeat(4,1fr);padding:12px 8px 30px;background:#fff;border-radius:26px 26px 0 0;box-shadow:0 -10px 30px -18px rgba(52,42,140,.4)}
.tabs a{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:5px;min-height:50px;font-size:12px;font-weight:600;color:#6d68a6}
.tabs a.on{color:#463bbf}
.tabs a.on::before{content:'';position:absolute;top:-1px;left:50%;width:34px;height:34px;margin-left:-17px;background:#e9e5ff;border-radius:7px;transform:scaleY(.58) rotate(45deg);transform-origin:50% 50%;z-index:0;top:-4px}
.tabs a>*{position:relative;z-index:1}
.ic{width:25px;height:25px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
`;

// a tiny SVG iso kit: P(u, v, z) → 2:1 projection; box() returns the three visible faces
function isoKit(s, ox, oy) {
  const P = (u, v, z) => [ox + (u - v) * s, oy + ((u + v) / 2 - z) * s];
  const pts = (a) => a.map((p) => P(...p).map((n) => n.toFixed(1)).join(',')).join(' ');
  const box = (u0, u1, v0, v1, z0, z1, [t, l, r]) =>
    `<polygon points="${pts([[u0, v1, z0], [u1, v1, z0], [u1, v1, z1], [u0, v1, z1]])}" fill="${l}"/>` +
    `<polygon points="${pts([[u1, v0, z0], [u1, v1, z0], [u1, v1, z1], [u1, v0, z1]])}" fill="${r}"/>` +
    `<polygon points="${pts([[u0, v0, z1], [u1, v0, z1], [u1, v1, z1], [u0, v1, z1]])}" fill="${t}"/>`;
  return { P, pts, box };
}
export function appDecor(root) {
  // the hero card's diorama: a water tile, a pier with posts and the ferry alongside
  const hero = root.querySelector('.hero');
  if (hero) { const { box, pts } = isoKit(1.15, 74, 34);
    const water = ['#9fd0f2', '#6aa9dc', '#4d8cc4'], pier = ['#f5d4ad', '#d9a676', '#b8835a'], hull = ['#ffffff', '#e6e2f8', '#c9c3ec'], cab = ['#fff3e4', '#ffb48c', '#ef8a6b'];
    let svg = `<ellipse cx="88" cy="132" rx="70" ry="13" fill="#2c2468" opacity=".14"/>`;
    svg += box(0, 92, 0, 72, -10, 0, water);
    svg += `<polygon points="${pts([[8, 10, 0.2], [30, 10, 0.2], [30, 13, 0.2], [8, 13, 0.2]])}" fill="#fff" opacity=".55"/><polygon points="${pts([[52, 58, 0.2], [80, 58, 0.2], [80, 61, 0.2], [52, 61, 0.2]])}" fill="#fff" opacity=".55"/>`;
    svg += box(0, 92, 0, 18, 0, 10, pier);
    for (let u = 8; u < 92; u += 22) svg += box(u, u + 4, 16, 20, -6, 10, ['#d9a676', '#b8835a', '#9a6a46']);
    svg += box(14, 74, 30, 56, 0, 9, hull);
    svg += `<polygon points="${pts([[14, 56, 2], [74, 56, 2], [74, 56, 4.5], [14, 56, 4.5]])}" fill="#ff6274"/><polygon points="${pts([[74, 30, 2], [74, 56, 2], [74, 56, 4.5], [74, 30, 4.5]])}" fill="#d73f59"/>`;
    svg += box(26, 56, 34, 52, 9, 22, cab) + box(42, 50, 40, 46, 22, 34, ['#463bbf', '#5a4fd6', '#2f2690']);
    for (let u = 30; u < 54; u += 7) svg += `<polygon points="${pts([[u, 52, 13], [u + 4, 52, 13], [u + 4, 52, 18], [u, 52, 18]])}" fill="#3a3478" opacity=".75"/>`;
    const art = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); art.setAttribute('class', 'iso-art'); art.setAttribute('viewBox', '0 0 168 150'); art.innerHTML = svg; hero.appendChild(art); }
  // an iso cube in front of each row, tinted by its state
  const tint = { ok: ['#bfeed6', '#7fd3a9', '#4fb284'], late: ['#ffc2c9', '#ff7d8c', '#d9435a'], few: ['#ffe3a1', '#ffc24f', '#dc9a1c'] };
  root.querySelectorAll('.rows li').forEach((li) => { const { box } = isoKit(1, 20, 18), c = tint[li.dataset.state] || tint.ok;
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); el.setAttribute('class', 'cube'); el.setAttribute('viewBox', '0 0 40 40'); el.setAttribute('aria-hidden', 'true');
    el.innerHTML = `<ellipse cx="20" cy="37" rx="15" ry="3" fill="#2c2468" opacity=".12"/>` + box(0, 20, 0, 20, 0, 16, c); li.prepend(el); });
  // a small iso tile as the brand mark
  const brand = root.querySelector('.brand'); if (brand) { const { box } = isoKit(0.9, 14, 16); const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    el.setAttribute('viewBox', '0 0 28 30'); el.setAttribute('width', '28'); el.setAttribute('height', '30'); el.setAttribute('aria-hidden', 'true');
    el.innerHTML = box(0, 14, 0, 14, 0, 6, ['#9fd0f2', '#6aa9dc', '#4d8cc4']) + box(3, 11, 3, 11, 6, 14, ['#fff3e4', '#ffb48c', '#ef8a6b']); brand.prepend(el); }
}
