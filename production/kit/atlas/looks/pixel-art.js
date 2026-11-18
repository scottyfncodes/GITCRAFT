// 3 · Pixel Art: a 320×180 indexed framebuffer in a 16-colour dusk palette. Every shape is rasterised to a hard mask
// (alpha thresholded, never antialiased), filled with palette indices, shaded and outlined pixel by pixel; skies are
// Bayer-dithered bands; text is Press Start 2P on its 8-pixel grid, thresholded the same way.
export const meta = { id: 'pixel-art', pixel: true, res: 1 / 3 };

const PAL = ['#0f0b1e', '#24183d', '#3d2459', '#63306e', '#9a3f74', '#d1576b', '#f2866a', '#f9b77a',
  '#ffe4a1', '#fffbe6', '#1f2e4f', '#2f4f75', '#4c7ea0', '#8fc6cf', '#e83b4d', '#ffd23f'];
const K = { ink: 0, night: 1, plum: 2, mauve: 3, rose: 4, coral: 5, peach: 6, apricot: 7, butter: 8, cream: 9, navy: 10, slate: 11, steel: 12, ice: 13, red: 14, gold: 15 };
const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5].map((v) => (v + 0.5) / 16);
const SKY = { dusk: [K.night, K.plum, K.mauve, K.rose, K.coral, K.peach, K.apricot], dawn: [K.navy, K.slate, K.mauve, K.rose, K.peach, K.apricot, K.butter],
  day: [K.slate, K.steel, K.steel, K.ice, K.ice, K.cream, K.cream], night: [K.ink, K.ink, K.night, K.night, K.navy, K.plum, K.mauve] };

export function game(ctx, S, L, W, H) {
  const res = meta.res, bw = Math.round(W * res), bh = Math.round(H * res);
  const B = new Uint8Array(bw * bh), r = L.rng(5);
  const at = (x, y) => (x >= 0 && y >= 0 && x < bw && y < bh ? y * bw + x : -1);
  const put = (x, y, c) => { const i = at(Math.round(x), Math.round(y)); if (i >= 0) B[i] = c; };
  const [mc, m] = L.offscreen(bw, bh);
  // rasterise world-space drawing to a hard 1-bit mask
  const mask = (draw) => { m.setTransform(1, 0, 0, 1, 0, 0); m.clearRect(0, 0, bw, bh); m.setTransform(res, 0, 0, res, 0, 0);
    m.fillStyle = '#fff'; m.strokeStyle = '#fff'; draw(m); const d = m.getImageData(0, 0, bw, bh).data, o = new Uint8Array(bw * bh);
    for (let i = 0; i < o.length; i++) o[i] = d[i * 4 + 3] >= 128 ? 1 : 0; return o; };
  const fill = (M, col) => { for (let i = 0; i < M.length; i++) if (M[i]) B[i] = typeof col === 'function' ? col(i % bw, (i / bw) | 0) : col; };
  const edge = (M, x, y) => M[at(x, y)] !== 1;
  const outline = (M, col = K.ink) => { for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) { const i = y * bw + x; if (M[i]) continue;
    if (M[at(x + 1, y)] === 1 || M[at(x - 1, y)] === 1 || M[at(x, y + 1)] === 1 || M[at(x, y - 1)] === 1) B[i] = col; } };
  const dith = (x, y, t) => t > BAYER[(y & 3) * 4 + (x & 3)];
  const px = (v) => Math.round(v * res);
  const gy = S.ground_y != null ? S.ground_y : H * 0.85;

  // sky: solid bands with a short Bayer-dithered seam between each pair
  const ramp = SKY[S.mood] || SKY.dusk, horizon = px(gy) || bh;
  for (let y = 0; y < bh; y++) {
    const f = Math.min(ramp.length - 1.001, (y / horizon) * (ramp.length - 1)), i = Math.floor(f), t = (f - i - 0.62) / 0.38;
    for (let x = 0; x < bw; x++) B[y * bw + x] = dith(x, y, t) ? ramp[Math.min(i + 1, ramp.length - 1)] : ramp[i];
  }
  // stars in the dark upper bands, a few flat cloud strips lower down
  if (S.mood !== 'day') for (let n = 0; n < 34; n++) { const x = (r() * bw) | 0, y = (r() * horizon * 0.35) | 0; put(x, y, r() < 0.25 ? K.butter : K.mauve); }
  for (let n = 0; n < 4; n++) {
    const cy = Math.round(horizon * (0.25 + r() * 0.35)), cx = (r() * bw) | 0, len = 16 + ((r() * 26) | 0);
    for (let x = 0; x < len; x++) { put(cx + x, cy, S.mood === 'day' ? K.cream : K.rose); if (x > 3 && x < len - 5) put(cx + x + 2, cy - 1, S.mood === 'day' ? K.cream : K.coral); }
  }
  // sun or moon: a disc with a dithered halo and a bright core
  if (S.sun) {
    const sx = px(S.sun.x), sy = px(S.sun.y), sr = Math.max(3, px(S.sun.r));
    for (let y = -sr - 6; y <= sr + 6; y++) for (let x = -sr - 6; x <= sr + 6; x++) {
      const d = Math.hypot(x, y);
      if (d <= sr) put(sx + x, sy + y, d > sr - 1.2 ? K.butter : (S.mood === 'night' ? K.ice : (y > sr * 0.35 && (y & 1) ? K.apricot : K.cream)));
      else if (d <= sr + 6 && dith(sx + x, sy + y, 0.55 - (d - sr) / 12)) put(sx + x, sy + y, S.mood === 'night' ? K.navy : K.apricot);
    }
    if (S.mood === 'night') for (let y = -sr; y <= sr; y++) for (let x = -sr; x <= sr; x++) if (Math.hypot(x - sr * 0.5, y - sr * 0.2) < sr * 0.85 && Math.hypot(x, y) <= sr) put(sx + x, sy + y, ramp[1]);
  }
  // far hills: one flat mass with a lit rim and a dithered foot
  if (S.far && S.far.length) {
    const M = mask((g) => g.fill(L.farPolygon(S, W, H)));
    fill(M, (x, y) => (edge(M, x, y - 1) ? K.rose : (dith(x, y, (y - horizon + 18) / 30) ? K.plum : K.mauve)));
  }
  // mid blocks: two-tone towers, ink outline, lit windows, a roof detail
  const blocks = L.buildings(S).map(([x, y, w, h]) => { let b = y + h;   // a block stops at a platform standing in front of its base
    for (const [qx, qy, qw] of S.platforms || []) if (qx < x + w && qx + qw > x && qy < b && qy > y + h * 0.5) b = qy; return [x, y, w, b - y]; });
  for (const [x, y, w, h] of blocks) {
    const x0 = px(x), y0 = px(y), x1 = px(x + w) - 1, y1 = px(y + h);
    for (let yy = y0; yy < y1; yy++) for (let xx = x0; xx <= x1; xx++) {
      const side = xx > x0 + (x1 - x0) * 0.62;
      put(xx, yy, xx === x0 || xx === x1 || yy === y0 ? K.ink : side ? K.navy : (yy === y0 + 1 ? K.steel : K.slate));
    }
    for (let wy = y0 + 3; wy < y1 - 3; wy += 4) for (let wx = x0 + 2; wx < x0 + (x1 - x0) * 0.6 - 1; wx += 3) if (r() < 0.38) { const c = r() < 0.7 ? K.apricot : K.butter; put(wx, wy, c); put(wx, wy + 1, c); }
    if (h > 140) { const ax = x0 + ((x1 - x0) >> 1); for (let k = 1; k < 5; k++) put(ax, y0 - k, K.ink); put(ax, y0 - 5, K.red); }
    else if (w > 60) { for (let xx = x0 + 3; xx < x0 + 8; xx++) for (let k = 1; k < 4; k++) put(xx, y0 - k, k === 3 || xx === x0 + 3 || xx === x0 + 7 ? K.ink : K.navy); }
  }
  // platforms: a sunlit lip, brick courses with mortar, the bricks darkening with depth
  for (const [x, y, w, h] of S.platforms || []) {
    const x0 = px(x), y0 = px(y), x1 = px(x + w) - 1, y1 = Math.min(bh - 1, px(y + h) - 1), depth = Math.max(1, y1 - y0);
    for (let yy = y0; yy <= y1; yy++) for (let xx = x0; xx <= x1; xx++) {
      const ly = yy - y0; let c;
      if (ly === 0) c = K.apricot; else if (ly === 1) c = K.peach; else if (ly === 2) c = K.ink;
      else { const row = Math.floor((ly - 3) / 4), mortar = (ly - 3) % 4 === 3 || (xx - x0 + (row & 1) * 4) % 8 === 0;
        const deep = dith(xx, yy, (ly - 6) / depth * 1.4);
        c = mortar ? K.night : deep ? K.plum : ((xx * 7 + row * 13) % 11 === 0 ? K.rose : K.mauve); }
      if (xx === x0 || xx === x1) c = K.ink;
      put(xx, yy, c);
    }
    for (let xx = x0 + 2; xx < x1 - 1; xx += 5) if (r() < 0.5) put(xx, y0, K.butter);
  }
  // hazards: red masses with a cream glint and an ink outline
  for (const hz of S.hazards || []) {
    const M = mask((g) => g.fill(L.hazardPath(hz)));
    fill(M, (x, y) => (edge(M, x - 1, y) || edge(M, x, y - 1) ? K.butter : (edge(M, x + 1, y) || edge(M, x, y + 1) ? K.rose : K.red)));
    if (hz.kind === 'block') fill(M, (x, y) => (((x + y) % 6) < 2 ? K.ink : B[y * bw + x]));
    outline(M);
  }
  // wind streaks: broken 1-pixel dashes
  for (const ln of S.lines || []) {
    for (let i = 0; i < ln.length - 1; i++) { const [ax, ay] = ln[i], [bx, by] = ln[i + 1], n = Math.ceil(Math.hypot(bx - ax, by - ay) * res);
      for (let k = 0; k < n; k++) if ((k + i * 3) % 7 < 4) put(px(ax + (bx - ax) * k / n), px(ay + (by - ay) * k / n), S.mood === 'day' ? K.cream : K.butter); }
  }
  // the trail: a dotted arc (every third pixel), or a 1-pixel string
  const t = S.trail || [];
  if (t.length > 1) {
    const kind = L.trailKind(S); let step = 0;
    for (let i = 0; i < t.length - 1; i++) { const [ax, ay] = t[i], [bx, by] = t[i + 1], n = Math.ceil(Math.hypot(bx - ax, by - ay) * res);
      for (let k = 0; k < n; k++, step++) { const X = px(ax + (bx - ax) * k / n), Y = px(ay + (by - ay) * k / n);
        if (kind === 'string') put(X, Y, K.cream); else if (step % 3 === 0) { put(X, Y, K.cream); if (step % 6 === 0) put(X, Y + 1, K.apricot); } } }
  }
  // pickups: gold with a highlight pixel, a shaded rim and an outline
  for (const c of S.pickups || []) {
    const M = mask((g) => g.fill(L.pickupPath(S, c)));
    fill(M, (x, y) => (edge(M, x + 1, y) || edge(M, x, y + 1) ? K.peach : K.gold));
    put(px(c.x - (c.r || 11) * 0.35), px(c.y - (c.r || 11) * 0.35), K.cream);
    outline(M);
  }
  // hero: cream body shaded on the lower-right, accent, a 2×2 eye, a bold outline and a drop shadow on what it stands over
  const hero = S.hero, HM = mask((g) => g.fill(L.heroPath(hero)));
  const AM = hero.accent ? mask((g) => g.fill(L.heroPath(hero, 'accent'))) : null;
  fill(HM, (x, y) => (edge(HM, x + 1, y) || edge(HM, x, y + 1) ? K.ice : (edge(HM, x - 1, y) || edge(HM, x, y - 1) ? K.cream : K.cream)));
  for (let i = 0; i < HM.length; i++) if (HM[i]) { const x = i % bw, y = (i / bw) | 0; if (!edge(HM, x, y) && edge(HM, x + 2, y + 1) && !edge(HM, x + 1, y)) B[i] = K.ice; }
  if (AM) fill(AM, (x, y) => (edge(AM, x, y + 1) ? K.rose : K.red));
  const e = L.heroEye(hero);
  if (e) { const ex = px(e.x), ey = px(e.y); put(ex, ey, K.ink); put(ex, ey - 1, K.ink); put(ex - 1, ey, K.ink); put(ex - 1, ey - 1, K.ink); }
  const HMx = HM.slice(); if (AM) for (let i = 0; i < AM.length; i++) HMx[i] |= AM[i];
  outline(HMx);

  // HUD: Press Start 2P on its own 8-pixel grid, thresholded; a bevelled panel behind the score
  const text = (str, x, y, size, col, shadow = K.ink) => {
    const M = mask((g) => { g.setTransform(1, 0, 0, 1, 0, 0); g.font = `400 ${size}px "Press Start 2P"`; g.textBaseline = 'top'; g.fillText(str, x, y); });
    if (shadow != null) for (let yy = bh - 1; yy >= 0; yy--) for (let xx = bw - 1; xx >= 0; xx--) if (M[yy * bw + xx]) put(xx + 1, yy + 1, shadow);
    fill(M, col); return M;
  };
  const panel = (x0, y0, w, h) => { for (let y = y0; y < y0 + h; y++) for (let x = x0; x < x0 + w; x++) {
    const bx = x === x0 || x === x0 + w - 1, by = y === y0 || y === y0 + h - 1;
    if ((x === x0 || x === x0 + w - 1) && (y === y0 || y === y0 + h - 1)) continue;
    put(x, y, bx || by ? K.ink : (x === x0 + 1 || y === y0 + 1 ? K.mauve : (x === x0 + w - 2 || y === y0 + h - 2 ? K.night : K.plum))); } };
  const hud = S.hud || {};
  m.font = '400 16px "Press Start 2P"'; const sw = Math.ceil(m.measureText(String(hud.score ?? '')).width);
  m.font = '400 8px "Press Start 2P"'; const lw = Math.ceil(m.measureText(String(hud.score_label ?? '')).width);
  panel(6, 6, Math.max(sw, lw, 3 * 10) + 12, hud.lives != null ? 46 : 36);
  if (hud.score_label) text(String(hud.score_label), 12, 11, 8, K.butter);
  if (hud.score != null) text(String(hud.score), 12, 21, 16, K.cream);
  if (hud.lives != null) {
    const HEART = ['.##.##.', '#######', '#######', '.#####.', '..###..', '...#...'];
    for (let n = 0; n < Math.max(3, hud.lives); n++) HEART.forEach((row, yy) => [...row].forEach((ch, xx) => {
      if (ch === '#') put(12 + n * 10 + xx, 40 + yy, n < hud.lives ? (yy === 1 && xx === 1 ? K.cream : K.red) : K.night); }));
  }
  if (hud.pause) { const x0 = bw - 22, y0 = 7; panel(x0, y0, 16, 16);
    for (let y = y0 + 4; y < y0 + 12; y++) { put(x0 + 5, y, K.cream); put(x0 + 6, y, K.cream); put(x0 + 9, y, K.cream); put(x0 + 10, y, K.cream); } }
  if (hud.best) { m.font = '400 8px "Press Start 2P"'; const w = Math.ceil(m.measureText(String(hud.best)).width); text(String(hud.best), bw - 28 - w, 12, 8, K.butter); }

  // write the indexed buffer through the palette, pixel for pixel
  const img = ctx.createImageData(bw, bh), d = img.data, rgb = PAL.map((c) => L.hex(c));
  for (let i = 0; i < B.length; i++) { const c = rgb[B[i]]; d[i * 4] = c[0]; d[i * 4 + 1] = c[1]; d[i * 4 + 2] = c[2]; d[i * 4 + 3] = 255; }
  ctx.putImageData(img, 0, 0);
}

// the app: a phone UI built from the same palette, with stepped pixel borders (no radii) and bevelled blocks
const px4 = (c) => `0 -4px 0 0 ${c},0 4px 0 0 ${c},-4px 0 0 0 ${c},4px 0 0 0 ${c}`;
export const appCss = `
.app{font-family:'Pixelify Sans',sans-serif;background:#24183d;color:#fffbe6;display:flex;flex-direction:column;padding:56px 24px 0;box-sizing:border-box;isolation:isolate;
  background-image:linear-gradient(45deg,rgba(255,255,255,.025) 25%,transparent 25%,transparent 75%,rgba(255,255,255,.025) 75%),linear-gradient(45deg,rgba(255,255,255,.025) 25%,transparent 25%,transparent 75%,rgba(255,255,255,.025) 75%);
  background-size:8px 8px;background-position:0 0,4px 4px}
.banner{position:absolute;left:0;top:0;width:100%;height:150px;image-rendering:pixelated;z-index:-1}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:44px}
.brand{font-weight:600;font-size:28px;color:#fffbe6;text-shadow:3px 3px 0 #0f0b1e}
.place{font-size:15px;font-weight:600;color:#0f0b1e;background:#ffe4a1;padding:6px 10px;box-shadow:${px4('#0f0b1e')}}
.hero{position:relative;margin-top:40px;background:#fffbe6;color:#24183d;padding:18px 18px 20px;
  box-shadow:${px4('#0f0b1e')},inset 4px 4px 0 #ffffff,inset -4px -4px 0 #f9b77a}
.label{font-size:16px;font-weight:600;color:#63306e}
.value{font-family:'Press Start 2P';font-size:44px;line-height:1;margin:14px 0 14px;color:#3d2459;text-shadow:4px 4px 0 #f9b77a}
.sub{font-size:16px;color:#24183d}
.status{display:inline-block;margin-top:14px;background:#8fc6cf;color:#0f0b1e;font-weight:600;font-size:15px;padding:6px 12px;box-shadow:${px4('#0f0b1e')},inset -3px -3px 0 #4c7ea0}
.hero .sprite{position:absolute;right:14px;top:-26px;width:48px;height:48px;image-rendering:pixelated}
.rows-title{font-family:'Pixelify Sans';font-weight:600;font-size:18px;color:#ffe4a1;margin:28px 0 12px;text-shadow:2px 2px 0 #0f0b1e}
.rows{list-style:none;margin:0;padding:0 4px;display:grid;gap:16px}
.rows li{display:grid;grid-template-columns:76px 1fr auto;align-items:center;min-height:52px;padding:0 12px;background:#3d2459;font-size:16px;
  box-shadow:${px4('#0f0b1e')},inset 0 4px 0 #63306e,inset 0 -4px 0 #24183d}
.rows .t{font-family:'Press Start 2P';font-size:13px;color:#ffe4a1}
.rows .s{font-size:14px;font-weight:600;padding:3px 8px;background:#8fc6cf;color:#0f0b1e}
.rows li[data-state=late] .s{background:#e83b4d;color:#fffbe6}
.rows li[data-state=few] .s{background:#ffd23f;color:#0f0b1e}
.cta{margin:26px 4px 0;height:60px;border:0;border-radius:0;background:#f2866a;color:#0f0b1e;font:600 21px 'Pixelify Sans';
  box-shadow:${px4('#0f0b1e')},inset 4px 4px 0 #f9b77a,inset -4px -6px 0 #9a3f74}
.strip{display:block;margin:auto -24px 0;width:calc(100% + 48px);height:36px;image-rendering:pixelated}
.tabs{margin:0 -24px 0;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 8px 30px;background:#0f0b1e;box-shadow:0 -4px 0 #3d2459}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:48px;font-size:14px;font-weight:600;color:#c7a6d9}
.tabs a.on{color:#ffd23f}
.tabs canvas{width:28px;height:28px;image-rendering:pixelated}
.ic{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:square;stroke-linejoin:miter}
.tabs canvas+.ic{display:none}
`;

// a pixel dusk strip behind the header, the hero sprite peeking over the card, and the tab icons re-rasterised to 12 px
export async function appDecor(root, A, L) {
  const r = L.rng(9), rgb = PAL.map((c) => L.hex(c));
  const draw = (w, h, fn) => { const [c, g] = L.offscreen(w, h); const img = g.createImageData(w, h);
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { const k = fn(x, y); if (k == null) continue; const i = (y * w + x) * 4, v = rgb[k]; img.data[i] = v[0]; img.data[i + 1] = v[1]; img.data[i + 2] = v[2]; img.data[i + 3] = 255; }
    g.putImageData(img, 0, 0); return c; };
  const ramp = [K.night, K.plum, K.mauve, K.rose, K.coral];
  const hills = (x) => 34 + Math.round(4 * Math.sin(x / 9) + 3 * Math.sin(x / 4.3 + 1));
  const towers = []; for (let x = 0; x < 130;) { const w = 5 + ((r() * 7) | 0), h = 6 + ((r() * 12) | 0); towers.push([x, w, h]); x += w + ((r() * 4) | 0); }
  const banner = draw(130, 50, (x, y) => {
    for (const [tx, tw, th] of towers) if (x >= tx && x < tx + tw && y >= 50 - th) return x === tx || y === 50 - th ? K.ink : ((x + y * 3) % 7 === 0 && r() < 0.6 ? K.apricot : K.navy);
    if (y >= hills(x)) return y === hills(x) ? K.rose : K.mauve;
    const d = Math.hypot(x - 104, y - 30); if (d < 7) return d > 6 ? K.butter : K.cream;
    const f = (y / 40) * (ramp.length - 1), i = Math.min(ramp.length - 2, Math.floor(f)), t = f - i;
    return t > BAYER[(y & 3) * 4 + (x & 3)] ? ramp[i + 1] : ramp[i];
  });
  banner.className = 'banner'; root.prepend(banner);
  // a fade from the strip into the page, stepped like pixels
  const fade = draw(130, 50, () => null); fade.remove();
  // a gold pixel star on the hero card's corner
  const SPR = ['.......##.......', '......#gg#......', '......#gg#......', '.....#gggg#.....', '######gwgg######', '#ggggggwggggggg#', '.#gggggggggggo#.', '..#gggggggggo#..',
    '...#ggggggggo#..', '...#gggggggoo#..', '..#gggg##gggo#..', '..#ggg#..#ggo#..', '.#ggg#....#go#..', '.#gg#......#o#..', '.###........##..', '................'];
  const spr = draw(16, 16, (x, y) => ({ '#': K.ink, g: K.gold, w: K.cream, o: K.peach }[SPR[y][x]] ?? null));
  spr.className = 'sprite'; root.querySelector('.hero')?.append(spr);
  // a strip of rooftop bricks above the tab bar, the game's ground carried into the app
  const strip = draw(130, 12, (x, y) => (y === 0 ? K.apricot : y === 1 ? K.peach : y === 2 ? K.ink
    : ((y - 3) % 4 === 3 || (x + (Math.floor((y - 3) / 4) & 1) * 4) % 8 === 0) ? K.night : ((x * 7 + y * 13) % 11 === 0 ? K.rose : K.mauve)));
  strip.className = 'strip'; root.querySelector('.tabs')?.before(strip);
  // tab icons: draw each SVG at 12 px, threshold it, paint it in the tab's colour
  for (const a of root.querySelectorAll('.tabs a')) {
    const svg = a.querySelector('svg'); if (!svg) continue;
    const col = a.classList.contains('on') ? K.gold : 13;
    const src = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#000" stroke-width="2.4" stroke-linecap="square">${svg.innerHTML}</svg>`;
    const im = new Image(); im.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(src);
    try { await im.decode(); } catch { continue; }
    const [c, g] = L.offscreen(14, 14); g.drawImage(im, 0, 0, 14, 14);
    const d = g.getImageData(0, 0, 14, 14), v = L.hex(a.classList.contains('on') ? PAL[K.gold] : '#c7a6d9');
    for (let i = 0; i < d.data.length; i += 4) { const on = d.data[i + 3] >= 110; d.data[i] = v[0]; d.data[i + 1] = v[1]; d.data[i + 2] = v[2]; d.data[i + 3] = on ? 255 : 0; }
    g.putImageData(d, 0, 0); void col; a.insertBefore(c, svg);
  }
}
