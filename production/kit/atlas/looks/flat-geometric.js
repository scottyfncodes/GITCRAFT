// 1 · Flat Geometric: flat colour bands, hard-edged shapes, long 45° shadows, no gradients, no outlines.
export const meta = { id: 'flat-geometric' };
const C = { sky: '#ffe2b8', sky2: '#ffd09a', sun: '#ff6b4a', far: '#f39a74', mid: '#2f5d7c', mid2: '#244a63', ground: '#14263a', top: '#1d3a55',
  hero: '#fffaf2', scarf: '#ff6b4a', coin: '#ffc23c', coinS: '#e09a12', spike: '#e8484c', ink: '#14263a', shadow: 'rgba(10,22,36,.28)' };

function longShadow(ctx, path, len = 46, color = C.shadow) {
  ctx.save(); ctx.fillStyle = color;
  for (let i = 1; i <= len; i += 1.5) { ctx.save(); ctx.translate(i, i); ctx.fill(path); ctx.restore(); }
  ctx.restore();
}

export function game(ctx, S, L, W, H) {
  // sky in three flat bands
  ctx.fillStyle = C.sky; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = C.sky2; ctx.fillRect(0, 190, W, 200);
  if (S.sun) { ctx.fillStyle = '#ffc9a3'; ctx.beginPath(); ctx.arc(S.sun.x, S.sun.y, S.sun.r + 26, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.sun; ctx.beginPath(); ctx.arc(S.sun.x, S.sun.y, S.sun.r, 0, Math.PI * 2); ctx.fill(); }
  if (S.far) { ctx.fillStyle = C.far; ctx.fill(L.farPolygon(S, W, H)); }
  // buildings: flat blocks with one lit face and window grids
  for (const [x, y, w, h] of L.buildings(S)) {
    ctx.fillStyle = C.mid; ctx.fillRect(x, y, w, h);
    ctx.fillStyle = C.mid2; ctx.fillRect(x + w * 0.62, y, w * 0.38, h);
    ctx.fillStyle = '#ffd58a';
    for (let wy = y + 16; wy < y + h - 20; wy += 22) for (let wx = x + 9; wx < x + w * 0.55; wx += 16) if (((wx * 7 + wy * 3) % 5) < 2) ctx.fillRect(wx, wy, 7, 9);
  }
  // platforms
  for (const [x, y, w, h] of S.platforms || []) {
    const p = new Path2D(); p.rect(x, y, w, h);
    ctx.fillStyle = C.ground; ctx.fill(p); ctx.fillStyle = C.top; ctx.fillRect(x, y, w, 10);
  }
  // hazards
  for (const hz of S.hazards || []) { ctx.fillStyle = C.spike; ctx.fill(L.hazardPath(hz)); if (hz.kind === 'spikes') { ctx.fillStyle = '#b8323a'; ctx.fillRect(hz.x, hz.y + hz.h - 8, hz.w, 8); } }
  // wind / motion streaks: flat rounded bars
  ctx.strokeStyle = 'rgba(255,250,242,.8)'; ctx.lineCap = 'round'; ctx.lineWidth = 5;
  for (const ln of S.lines || []) { L.smooth(ctx, ln); ctx.stroke(); }
  // the trail: dotted jump arc, or a taut string
  const t = S.trail || [];
  if (L.trailKind(S) === 'string' && t.length) { ctx.strokeStyle = C.ink; ctx.lineWidth = 2.5; L.smooth(ctx, t); ctx.stroke(); }
  else { ctx.fillStyle = 'rgba(255,250,242,.75)';
    for (let i = 0; i < t.length - 1; i++) for (let k = 0; k < 3; k++) {
      const a = k / 3, x = t[i][0] + (t[i + 1][0] - t[i][0]) * a, y = t[i][1] + (t[i + 1][1] - t[i][1]) * a;
      ctx.beginPath(); ctx.arc(x, y, 2 + (i * 3 + k) * 0.35, 0, Math.PI * 2); ctx.fill(); } }
  // pickups: flat shapes with a hard offset shadow
  for (const c of S.pickups || []) {
    const p = L.pickupPath(S, c);
    ctx.save(); ctx.translate(2, 2); ctx.fillStyle = C.coinS; ctx.fill(p); ctx.restore();
    ctx.fillStyle = C.coin; ctx.fill(p);
    ctx.fillStyle = '#fff1c2'; ctx.fillRect(c.x - 2, c.y - 6, 3, 9);
  }
  // hero: a hard flat shadow offset down-right, then the silhouette
  const hero = L.heroPath(S.hero);
  longShadow(ctx, hero, 6, 'rgba(20,38,58,.10)');
  ctx.fillStyle = C.hero; ctx.fill(hero);
  if (S.hero.accent) { ctx.fillStyle = C.scarf; ctx.fill(L.heroPath(S.hero, 'accent')); }
  const e = L.heroEye(S.hero); if (e) { ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2); ctx.fill(); }
  // HUD: flat pills, one heavy geometric face
  ctx.font = '800 15px Outfit'; ctx.fillStyle = C.ink; ctx.globalAlpha = .7; ctx.fillText(S.hud.score_label, 36, 46); ctx.globalAlpha = 1;
  ctx.font = '800 44px Outfit'; ctx.fillText(S.hud.score, 34, 90);
  for (let i = 0; i < (S.hud.lives != null ? 3 : 0); i++) { ctx.fillStyle = i < S.hud.lives ? C.sun : 'rgba(20,38,58,.2)'; ctx.beginPath(); ctx.arc(46 + i * 26, 116, 8, 0, Math.PI * 2); ctx.fill(); }
  L.rr(ctx, W - 84, 28, 50, 50, 25); ctx.fillStyle = C.ink; ctx.fill();
  ctx.fillStyle = '#fffaf2'; ctx.fillRect(W - 66, 42, 6, 22); ctx.fillRect(W - 56, 42, 6, 22);
  ctx.font = '600 15px Outfit'; ctx.fillStyle = C.ink; ctx.textAlign = 'right'; ctx.fillText(S.hud.best, W - 100, 59); ctx.textAlign = 'left';
}

export const appCss = `
.app{font-family:Outfit,sans-serif;background:#ffe2b8;color:#14263a;display:flex;flex-direction:column;padding:56px 22px 0;box-sizing:border-box}
.top{display:flex;justify-content:space-between;align-items:baseline}
.brand{font-weight:800;font-size:28px;letter-spacing:-.02em}
.place{font-weight:600;font-size:14px;opacity:.7}
.hero{position:relative;margin-top:22px;background:#2f5d7c;color:#fffaf2;border-radius:28px;padding:22px 22px 24px;overflow:hidden}
.hero::after{content:'';position:absolute;right:-40px;top:-40px;width:170px;height:170px;border-radius:50%;background:#ff6b4a}
.hero::before{content:'';position:absolute;right:30px;bottom:-60px;width:120px;height:120px;background:#244a63;transform:rotate(45deg)}
.hero>*{position:relative;z-index:1}
.label{font-weight:600;font-size:15px;opacity:.85}
.value{font-weight:800;font-size:76px;line-height:1;letter-spacing:-.04em;margin:6px 0 8px}
.sub{font-size:15px;opacity:.9}
.status{display:inline-block;margin-top:14px;background:#ffc23c;color:#14263a;font-weight:800;font-size:13px;padding:6px 12px;border-radius:99px}
.rows-title{font-size:15px;font-weight:800;margin:26px 0 8px;text-transform:none}
.rows{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.rows li{display:grid;grid-template-columns:64px 1fr auto;align-items:center;background:#fffaf2;border-radius:18px;padding:14px 16px;font-size:16px}
.rows .t{font-weight:800;font-size:19px}
.rows .s{font-size:13px;font-weight:600;padding:4px 9px;border-radius:99px;background:#e7f0e9;color:#1f6a43}
.rows li[data-state=late] .s{background:#ffd9d2;color:#b8323a}
.rows li[data-state=few] .s{background:#ffefc6;color:#8a5a00}
.cta{margin:18px 0 0;height:58px;border:0;border-radius:20px;background:#ff6b4a;color:#fffaf2;font:800 19px Outfit;box-shadow:0 6px 0 #c44a31}
.tabs{margin-top:auto;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 0 30px;background:#fffaf2;margin-left:-22px;margin-right:-22px;border-radius:26px 26px 0 0}
.tabs a{display:flex;flex-direction:column;align-items:center;gap:4px;font-size:12px;font-weight:600;color:#14263a;opacity:.5}
.tabs a.on{opacity:1;color:#ff6b4a}
.ic{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
`;
