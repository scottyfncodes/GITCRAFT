// 9 · Linocut Ink: a two-block relief print. Every shape is cut into an ink plate and a vermilion plate as masks,
// carved with tapered gouge marks (destination-out), then "printed": blurred and thresholded through noise so edges
// go rough and solids starve, and pressed onto cream paper with the colour plate slightly misregistered.
export const meta = { id: 'linocut' };
const INK = [33, 27, 25], RED = [206, 64, 38], PAPER = '#efe3c7';
const TAU = Math.PI * 2;

// ---- cutting tools ------------------------------------------------------------------------------------------------
function jpoly(pts, n, amp = 1.4, step = 7) {   // a hand-cut outline: every edge subdivided and nudged by noise
  const p = new Path2D(); let first = true;
  for (let i = 0; i < pts.length; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[(i + 1) % pts.length], k = Math.max(1, Math.round(Math.hypot(x1 - x0, y1 - y0) / step));
    for (let j = 0; j < k; j++) { const x = x0 + (x1 - x0) * j / k, y = y0 + (y1 - y0) * j / k, dx = (n(x / 9, y / 9 + 3) - 0.5) * 2 * amp, dy = (n(x / 9 + 5, y / 9) - 0.5) * 2 * amp;
      if (first) { p.moveTo(x + dx, y + dy); first = false; } else p.lineTo(x + dx, y + dy); } }
  p.closePath(); return p;
}
const rectPts = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
function taper(c, pts, w, wob = 0) {   // a gouge stroke along a polyline: thin at both ends, widest past the middle
  const n = pts.length; if (n < 2) return;
  for (let i = 0; i < n - 1; i++) { const t = (i + 0.5) / (n - 1), k = Math.pow(Math.sin(Math.PI * Math.min(1, t * 1.15)), 0.6);
    c.lineWidth = Math.max(0.35, w * k); c.beginPath(); c.moveTo(pts[i][0], pts[i][1] + wob * Math.sin(i)); c.lineTo(pts[i + 1][0], pts[i + 1][1]); c.stroke(); }
}
function line(x0, y0, x1, y1, step = 5, bend = 0) { const n = Math.max(2, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / step)), out = [];
  for (let i = 0; i <= n; i++) { const t = i / n; out.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t + Math.sin(t * Math.PI) * bend]); } return out; }
function along(pts, step = 4) {   // resample a polyline evenly
  const out = [pts[0]]; let carry = 0;
  for (let i = 0; i < pts.length - 1; i++) { const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], d = Math.hypot(x1 - x0, y1 - y0);
    for (let s = step - carry; s <= d; s += step) out.push([x0 + (x1 - x0) * s / d, y0 + (y1 - y0) * s / d]); carry = (carry + d) % step; }
  return out;
}
function farY(S, x) { const f = S.far; if (!f || !f.length) return Infinity; if (x <= f[0][0]) return f[0][1];
  for (let i = 0; i < f.length - 1; i++) if (x <= f[i + 1][0]) { const t = (x - f[i][0]) / ((f[i + 1][0] - f[i][0]) || 1); return f[i][1] + (f[i + 1][1] - f[i][1]) * t; }
  return f[f.length - 1][1]; }

// "printing": blur the cut mask a little, threshold it through noise (rough edges), starve the solids (paper shows)
function print(L, src, w, h, rgb, seed, blur, starve) {
  const [c, x] = L.offscreen(w, h); x.filter = `blur(${blur}px)`; x.drawImage(src, 0, 0); x.filter = 'none';
  const im = x.getImageData(0, 0, w, h), d = im.data, n = L.noise2(seed), m = L.noise2(seed + 17), r = L.rng(seed);
  for (let y = 0; y < h; y++) for (let X = 0; X < w; X++) {
    const i = (y * w + X) * 4, a = d[i + 3] / 255; if (a < 0.18) { d[i + 3] = 0; continue; }
    const t = 0.5 + (n(X / 5, y / 5) - 0.5) * 0.55 + (r() - 0.5) * 0.14;
    if (a < t) { d[i + 3] = 0; continue; }
    const s = m(X / 38, y / 38) * 0.62 + n(X / 1.7 + 91, y / 1.7) * 0.38;
    d[i] = rgb[0]; d[i + 1] = rgb[1]; d[i + 2] = rgb[2]; d[i + 3] = 255 * (s > starve ? 0.62 + (1 - s) * 0.5 : 0.99 - s * 0.06);
  }
  x.putImageData(im, 0, 0); return c;
}

export function game(ctx, S, L, W, H) {
  const sc = ctx.getTransform().a || 1, PW = Math.round(W * sc), PH = Math.round(H * sc);
  const plate = () => { const [c, x] = L.offscreen(PW, PH); x.setTransform(sc, 0, 0, sc, 0, 0); x.lineCap = 'round'; x.lineJoin = 'round'; x.fillStyle = '#000'; x.strokeStyle = '#000'; return [c, x]; };
  const [inkC, K] = plate(), [redC, R] = plate();
  const n = L.noise2(23), r = L.rng(41), hero = S.hero, mood = S.mood || 'day';
  const carve = (c, f) => { c.save(); c.globalCompositeOperation = 'destination-out'; f(c); c.restore(); };
  const horizon = S.far && S.far.length ? Math.min(...S.far.map((p) => p[1])) : (S.ground_y || H * 0.7);
  const hb = [hero.x, hero.y, hero.x + hero.size, hero.y + hero.size];

  // sky: ink left standing between carved sweeps, solid at the top and thinning toward the horizon
  const band = { night: 0.95, dusk: 0.6, dawn: 0.5, day: 0.34 }[mood] || 0.4;
  for (let y = 3, row = 0; y < horizon + 6; y += 6.4, row++) {
    const dk = Math.max(0, Math.min(1, 1 - y / (horizon * band))), w = 0.7 + dk * 5.6;
    for (let x = -30 + r() * 40; x < W + 20;) {
      const len = 26 + r() * (90 + 160 * dk), gap = 5 + (1 - dk) * (14 + r() * 110);
      if (dk > 0.02 || r() < 0.55) { const pts = line(x, y, x + len, y, 6).map(([px, py]) => [px, py + (n(px / 140, row * 0.7) - 0.5) * 3.4]); taper(K, pts, w * (0.75 + r() * 0.35)); }
      x += len + gap;
    }
  }
  // a vermilion glow band above the hills at dusk and dawn
  if ((mood === 'dusk' || mood === 'dawn') && S.far) {
    R.save(); const above = new Path2D(); above.moveTo(0, 0); above.lineTo(W, 0); for (let i = S.far.length - 1; i >= 0; i--) above.lineTo(S.far[i][0], S.far[i][1] + 2); above.lineTo(0, 0); R.clip(above);
    for (let y = horizon - 110, row = 0; y < horizon + 70; y += 5.2, row++) { const k = Math.max(0, Math.min(1, (y - (horizon - 110)) / 130)), w = 0.6 + k * 4.2;
      for (let x = -20 + r() * 30; x < W;) { const len = 40 + r() * 200; taper(R, line(x, y, x + len, y + (r() - 0.5) * 2, 6), w); x += len + 4 + (1 - k) * r() * 60; } }
    R.restore();
  }

  // negative space around the hero: both plates cleared in a soft oval so the figure is the first thing read
  { const hx = hero.x + hero.size / 2, hy = hero.y + hero.size / 2, rr = hero.size * 0.88;
    const clear = (c) => { c.beginPath(); for (let i = 0; i < 40; i++) { const a = i * TAU / 40, k = rr * (0.94 + n(Math.cos(a) * 2 + 9, Math.sin(a) * 2) * 0.16); c.lineTo(hx + Math.cos(a) * k * 1.12, hy + Math.sin(a) * k); } c.closePath(); c.fill(); };
    carve(K, clear); carve(R, clear); }
  // sun: a vermilion disc cut with concentric rings, framed by broken ink rings carved into the sky
  if (S.sun) { const { x, y, r: sr } = S.sun;
    carve(K, (c) => { c.beginPath(); c.arc(x, y, sr + 52, 0, TAU); c.fill(); });
    R.beginPath(); R.arc(x, y, sr, 0, TAU); R.fill(jpoly([...Array(48)].map((_, i) => [x + Math.cos(i * TAU / 48) * sr, y + Math.sin(i * TAU / 48) * sr]), n, 1.2));
    carve(R, (c) => { for (let k = 1; k <= 3; k++) { const rr = sr * (0.24 + k * 0.22); for (let a = r() * TAU, e = a + TAU; a < e;) { const sweep = 0.5 + r() * 1.4;
      taper(c, [...Array(12)].map((_, i) => [x + Math.cos(a + sweep * i / 11) * rr, y + Math.sin(a + sweep * i / 11) * rr]), 1.6 + k * 0.3); a += sweep + 0.15 + r() * 0.3; } } });
    [10, 21, 33, 46].forEach((d, k) => { const rr = sr + d; for (let a = r() * TAU, e = a + TAU; a < e;) { const sweep = 0.35 + r() * 1.1;
      taper(K, [...Array(14)].map((_, i) => [x + Math.cos(a + sweep * i / 13) * rr, y + Math.sin(a + sweep * i / 13) * rr]), 4.2 - k * 0.8); a += sweep + 0.12 + r() * 0.35 * (k + 1); } });
  }

  // far hills: an ink mass with gouges that follow the ridge, densest (lightest) near the top
  if (S.far && S.far.length) {
    const f = S.far.map(([x, y]) => [x, y]), poly = jpoly([[0, H + 5], ...f.map(([x, y]) => [x, y]), [W, H + 5]], n, 1.6, 8);
    carve(K, (c) => { c.lineWidth = 6; c.stroke(poly); });
    K.fill(poly);
    carve(K, (c) => { c.save(); c.clip(poly); const base = along(f, 5);
      const depth = H - horizon + 10;
      for (let k = 1, off = 9; off < depth; k++, off += 6 + Math.min(4, k * 0.12)) { const w = Math.max(1.5, 3.1 - k * 0.05);
        for (let i = Math.floor(r() * 8); i < base.length - 3;) { const len = 6 + Math.floor(r() * 18); const seg = base.slice(i, i + len).map(([x, y]) => [x, y + off + (n(x / 60, k) - 0.5) * 3]);
          if (r() < 0.9) taper(c, seg, w); i += len + 1 + Math.floor(r() * (2 + Math.min(k, 12) * 0.5)); } }
      c.restore(); });
  }

  // mid blocks: a carved halo, a solid block, window notches and vertical gouges on the lit side
  for (const [x, y, w, h] of L.buildings(S)) {
    const p = jpoly(rectPts(x, y, w, h + 6), n, 1.1, 8);
    carve(K, (c) => { c.lineWidth = 6; c.stroke(p); }); K.fill(p);
    carve(K, (c) => {
      for (let gx = x + 4; gx < x + w * 0.32; gx += 4.2) taper(c, line(gx, y + 4 + r() * 6, gx + (r() - 0.5) * 2, y + 14 + r() * h * 0.5, 5), 1.5);
      c.beginPath(); for (let wy = y + 14; wy < y + h - 14; wy += 18) for (let wx = x + w * 0.4; wx + 6 <= x + w - 5; wx += 12) if (n(wx / 7, wy / 7) > 0.42) c.rect(wx + (r() - 0.5), wy, 5, 8);
      c.fill(); });
  }

  // platforms: solid ground with a carved lip, chisel marks thinning downward and a cut edge on each side
  for (const [x, y, w, h] of S.platforms || []) {
    const p = jpoly(rectPts(x, y, w, h + 6), n, 1.3, 8);
    carve(K, (c) => { c.lineWidth = 7; c.stroke(p); }); K.fill(p);
    carve(K, (c) => { c.save(); c.clip(p);
      taper(c, line(x + 6, y + 6, x + w - 6, y + 6 + (r() - 0.5) * 2, 6), 2.6);
      for (let yy = y + 13, k = 0; yy < y + h; yy += 6.5 + Math.min(k, 8) * 0.9, k++)
        for (let xx = x + 4 + r() * 18; xx < x + w - 8;) { const len = 10 + r() * 46; if (r() < 0.9 - Math.min(k, 10) * 0.05) taper(c, line(xx, yy, xx + len, yy + (r() - 0.5) * 2.5, 5), Math.max(1.1, 2.1 - k * 0.1)); xx += len + 6 + Math.min(k, 10) * 7 + r() * 22; }
      for (let k = 0; k < 4; k++) { taper(c, line(x + 5 + k * 5, y + 14, x + 4 + k * 5, y + 14 + Math.min(h * 0.5, 40) - k * 6, 5), 1.4); taper(c, line(x + w - 5 - k * 5, y + 14, x + w - 4 - k * 5, y + 14 + Math.min(h * 0.5, 40) - k * 6, 5), 1.4); }
      c.restore(); });
  }

  // hazards: vermilion under an ink cut (teeth, posts), or a black carved shape (flying things)
  for (const z of S.hazards || []) {
    const p = L.hazardPath(z);
    if (z.kind === 'path') { carve(K, (c) => { c.lineWidth = 6; c.stroke(p); }); K.fill(p);
      carve(K, (c) => { c.save(); c.clip(p); taper(c, line(z.x + z.w * 0.12, z.y + z.h * 0.55, z.x + z.w * 0.88, z.y + z.h * 0.55, 4, -z.h * 0.28), 1.4); c.restore(); }); continue; }
    carve(K, (c) => { c.lineWidth = 6; c.stroke(p); });
    R.fill(p); K.lineWidth = 2.4; K.stroke(p);
    if (z.kind === 'spikes') { const k = Math.max(3, Math.round(z.w / 22)), tw = z.w / k;
      for (let i = 0; i < k; i++) taper(K, line(z.x + i * tw + tw / 2, z.y + 4, z.x + i * tw + tw * 0.62, z.y + z.h - 2, 4), 1.8);
      K.fillRect(z.x - 2, z.y + z.h - 5, z.w + 4, 6); }
    else { K.save(); K.clip(p); for (let t = -z.h; t < z.w + z.h; t += 14) { K.lineWidth = 4.5; K.beginPath(); K.moveTo(z.x + t, z.y + z.h); K.lineTo(z.x + t + z.h, z.y); K.stroke(); } K.restore(); }
  }

  // wind lines: long gouged strokes with a thinner echo
  for (const ln of S.lines || []) { if (ln.length < 2) continue; const pts = along(ln, 5);
    carve(K, (c) => taper(c, pts.map(([x, y]) => [x, y + 3]), 7));
    taper(K, pts, 3.2); taper(K, pts.slice(Math.floor(pts.length * 0.25)).map(([x, y]) => [x + 10, y + 7]), 1.6); }

  // the trail: tapered dashes growing toward the hero (arc), or a taut cut line (string)
  const t = S.trail || [];
  if (t.length > 1) { const pts = along(t, 4);
    if (L.trailKind(S) === 'string') { carve(K, (c) => { c.lineWidth = 6; c.beginPath(); pts.forEach(([x, y], i) => c[i ? 'lineTo' : 'moveTo'](x, y)); c.stroke(); });
      K.lineWidth = 1.9; K.beginPath(); pts.forEach(([x, y], i) => K[i ? 'lineTo' : 'moveTo'](x, y + (n(x / 30, y / 30) - 0.5) * 1.2)); K.stroke(); }
    else for (let i = 0, k = 0; i < pts.length - 3; i += 7, k++) { const seg = pts.slice(i, i + 5), w = 2 + (i / pts.length) * 4.4;
      carve(K, (c) => taper(c, seg, w + 4)); taper(K, seg, w); } }

  // pickups: vermilion tokens with an ink rim and a carved glint
  for (const c of S.pickups || []) { const p = L.pickupPath(S, c), rr = c.r || 11;
    carve(K, (k) => { k.lineWidth = 7; k.stroke(p); k.fill(p); });
    R.fill(p); K.lineWidth = 2.2; K.stroke(p);
    carve(R, (k) => taper(k, line(c.x - rr * 0.45, c.y - rr * 0.1, c.x - rr * 0.1, c.y - rr * 0.5, 2), 2.4)); }

  // the hero: a carved halo, the solid figure, highlight cuts that wrap its lit side, a cut eye and a red accent
  const hp = L.heroPath(hero), cx = hero.x + hero.size / 2, cy = hero.y + hero.size / 2, hs = hero.size;
  carve(K, (c) => { c.lineWidth = 16; c.stroke(hp); });
  K.fill(hp);
  carve(K, (c) => { c.save(); c.clip(hp); const ox = cx + hs * 0.08 * (hero.facing < 0 ? -1 : 1), oy = cy + hs * 0.1;
    for (let rr = hs * 0.2; rr < hs * 0.62; rr += hs * 0.065) { const a0 = hero.facing < 0 ? -1.15 : -2.35, a1 = a0 + 1.5;
      taper(c, [...Array(14)].map((_, i) => [ox + Math.cos(a0 + (a1 - a0) * i / 13) * rr, oy + Math.sin(a0 + (a1 - a0) * i / 13) * rr]), Math.max(1, hs * 0.028)); }
    c.restore(); });
  if (hero.accent) { const ap = L.heroPath(hero, 'accent'); carve(K, (c) => { c.save(); c.clip(hp); c.fill(ap); c.restore(); }); R.fill(ap); }
  const e = L.heroEye(hero);
  if (e) { carve(K, (c) => { c.beginPath(); c.arc(e.x, e.y, e.r * 1.75, 0, TAU); c.fill(); }); K.beginPath(); K.arc(e.x + e.r * 0.3, e.y, e.r * 0.85, 0, TAU); K.fill(); }

  // HUD: carved into ink blocks (score, lives) and a carved pause stamp; best is set in the slab face
  const hud = S.hud || {}, block = (x, y, w, h) => { const p = jpoly(rectPts(x, y, w, h), n, 1.2, 9); carve(K, (c) => { c.lineWidth = 8; c.stroke(p); }); K.fill(p); return p; };
  let sx = 24; if (S.sun && S.sun.x - S.sun.r - 50 < 230 && S.sun.y - S.sun.r - 50 < 140) sx = Math.min(W / 2 - 200, S.sun.x + S.sun.r + 54);
  block(sx, 22, 200, 112);
  carve(K, (c) => { c.translate(sx - 24, 0); c.textBaseline = 'alphabetic'; c.font = '600 16px "Crimson Pro"'; c.letterSpacing = '3px'; c.fillText((hud.score_label || 'SCORE').toUpperCase(), 40, 50);
    c.font = '52px "Alfa Slab One"'; c.letterSpacing = '1px'; c.fillText(String(hud.score ?? ''), 38, 103);
    taper(c, line(40, 58, 208, 58, 6), 1.4);
    if (hud.lives != null) { const k = Math.max(3, hud.lives); for (let i = 0; i < k; i++) { c.beginPath(); c.arc(46 + i * 22, 119, 6.5, 0, TAU); if (i < hud.lives) c.fill(); else { c.lineWidth = 2; c.stroke(); } } } });
  if (hud.pause) { const px = W - 54, py = 52; carve(K, (c) => { c.beginPath(); c.arc(px, py, 30, 0, TAU); c.fill(); });
    K.fill(jpoly([...Array(36)].map((_, i) => [px + Math.cos(i * TAU / 36) * 25, py + Math.sin(i * TAU / 36) * 25]), n, 0.9, 5));
    carve(K, (c) => { c.fillRect(px - 9, py - 11, 6, 22); c.fillRect(px + 3, py - 11, 6, 22); }); }
  if (hud.best) { const bx = W - 98; K.font = '26px "Alfa Slab One"'; K.textAlign = 'right'; K.textBaseline = 'middle'; K.letterSpacing = '1px';
    const bw = K.measureText(hud.best).width; block(bx - bw - 18, 34, bw + 32, 38);
    carve(K, (c) => { c.font = '22px "Alfa Slab One"'; c.textAlign = 'right'; c.textBaseline = 'middle'; c.letterSpacing = '1px'; c.fillText(hud.best, bx, 54); }); }

  // press: paper first, the vermilion plate a hair off register, then the ink plate
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
  const [mc, mx] = L.offscreen(160, 90), mi = mx.createImageData(160, 90), pn = L.noise2(5);
  for (let y = 0; y < 90; y++) for (let x = 0; x < 160; x++) { const v = pn(x / 14, y / 14) * 0.6 + pn(x / 4 + 30, y / 4) * 0.4, i = (y * 160 + x) * 4;
    mi.data[i] = 150; mi.data[i + 1] = 112; mi.data[i + 2] = 60; mi.data[i + 3] = Math.max(0, v - 0.42) * 70; }
  mx.putImageData(mi, 0, 0); ctx.imageSmoothingEnabled = true; ctx.drawImage(mc, 0, 0, W, H);
  ctx.lineCap = 'round'; for (let i = 0; i < 1400; i++) { const x = r() * W, y = r() * H, a = r() * TAU, l = 3 + r() * 11;
    ctx.strokeStyle = r() < 0.6 ? 'rgba(120,88,50,.10)' : 'rgba(255,250,236,.5)'; ctx.lineWidth = 0.4 + r() * 0.5;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.quadraticCurveTo(x + Math.cos(a + 0.6) * l * 0.5, y + Math.sin(a + 0.6) * l * 0.5, x + Math.cos(a) * l, y + Math.sin(a) * l); ctx.stroke(); }
  ctx.globalCompositeOperation = 'multiply';
  ctx.drawImage(print(L, redC, PW, PH, RED, 61, 1.3 * sc / 2, 0.84), 2.6, -1.8, W, H);
  ctx.drawImage(print(L, inkC, PW, PH, INK, 67, 1.1 * sc / 2, 0.83), 0, 0, W, H);
  ctx.globalCompositeOperation = 'source-over';
  L.grain(ctx, W, H, 0.045, 9);
}

// ---- the app ----------------------------------------------------------------------------------------------------
export const appCss = `
.app{--ink:#211b19;--paper:#efe3c7;--red:#b8391f;font-family:"Crimson Pro",serif;color:var(--ink);box-sizing:border-box;display:flex;flex-direction:column;
  padding:56px 22px 0;background:var(--paper)}
.app *{box-sizing:border-box}
.lino-paper{position:absolute;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}
.app>*:not(.lino-paper){position:relative;z-index:1}
.top{display:flex;justify-content:space-between;align-items:baseline;padding-bottom:12px}
.brand{font:400 30px/1 "Alfa Slab One",serif;letter-spacing:.01em}
.place{font:600 16px "Crimson Pro",serif;font-style:italic;color:#4a3f37}
.hero{margin-top:14px;min-height:262px;padding:22px 22px 22px;color:#f6ecd4;display:flex;flex-direction:column;align-items:flex-start}
.hero .label{font:600 15px "Crimson Pro",serif;letter-spacing:.18em;text-transform:uppercase;color:#f6ecd4}
.hero .value{font:400 88px/1 "Alfa Slab One",serif;white-space:nowrap;letter-spacing:.01em;margin:8px 0 6px;color:#f6ecd4}
.hero .sub{font:400 18px/1.3 "Crimson Pro",serif;max-width:62%;color:#f6ecd4}
.hero .status{margin-top:auto;font:600 15px "Crimson Pro",serif;letter-spacing:.12em;text-transform:uppercase;background:#f6ecd4;color:var(--red);padding:5px 12px 4px}
.rows-title{margin:26px 0 4px;font:400 19px "Alfa Slab One",serif;letter-spacing:.02em}
.rows{list-style:none;margin:0;padding:0}
.rows li{display:grid;grid-template-columns:76px 1fr auto;align-items:center;min-height:58px;padding:6px 0;background:var(--rule) left bottom/100% 7px no-repeat}
.rows .t{font:400 21px "Alfa Slab One",serif}
.rows .d{font:600 19px "Crimson Pro",serif}
.rows .s{font:600 16px "Crimson Pro",serif;font-style:italic;color:#3d5a2e}
.rows li[data-state=late] .s{color:var(--red)}
.rows li[data-state=few] .s{color:#7a4f0a}
.cta{margin:auto 0 26px;height:60px;border:0;border-radius:0;color:#f8eed8;cursor:pointer;font:400 22px "Alfa Slab One",serif;letter-spacing:.03em;background:var(--ctabg) center/100% 100% no-repeat,var(--red)}
.tabs{margin:0 -22px;display:grid;grid-template-columns:repeat(4,1fr);padding:14px 6px 30px;background:var(--tabrule) left top/100% 8px no-repeat,#e9dcbd}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:50px;font:600 14px "Crimson Pro",serif;letter-spacing:.06em;color:#4a3f37}
.tabs a.on{color:var(--red)}
.tabs a.on span{border-bottom:2px solid currentColor;line-height:1.1}
.ic{width:26px;height:26px;fill:none;stroke:currentColor;stroke-width:2.1;stroke-linecap:round;stroke-linejoin:round}
`;

export async function appDecor(root, A, L) {
  // the same plate-and-press machinery as the game, at phone size: paper, rules, a carved hero block, a printed button
  const dpr = 2, n = L.noise2(31), r = L.rng(3);
  const press = (w, h, draw, rgb, seed) => { const [c, x] = L.offscreen(w * dpr, h * dpr); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.lineCap = 'round'; x.lineJoin = 'round'; x.fillStyle = '#000'; x.strokeStyle = '#000';
    draw(x); return print(L, c, w * dpr, h * dpr, rgb, seed, 1.1, 0.9); };
  const carve = (c, f) => { c.save(); c.globalCompositeOperation = 'destination-out'; f(c); c.restore(); };
  const W = root.clientWidth, H = root.clientHeight;
  // paper
  const [pc, px] = L.offscreen(W * dpr, H * dpr); px.scale(dpr, dpr); px.fillStyle = PAPER; px.fillRect(0, 0, W, H); px.lineCap = 'round';
  for (let i = 0; i < 700; i++) { const x = r() * W, y = r() * H, a = r() * TAU, l = 3 + r() * 10; px.strokeStyle = r() < 0.6 ? 'rgba(120,88,50,.10)' : 'rgba(255,250,236,.55)'; px.lineWidth = 0.5;
    px.beginPath(); px.moveTo(x, y); px.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l); px.stroke(); }
  pc.className = 'lino-paper'; root.prepend(pc);
  const url = (c) => c.toDataURL();
  // carved rules for the rows and the tab bar
  root.style.setProperty('--rule', `url(${url(press(346, 7, (x) => { x.lineWidth = 2.6; x.beginPath(); x.moveTo(1, 3.5); x.lineTo(345, 3.5); x.stroke(); taper(x, line(0, 3.5, 346, 3.5, 6), 4.6); }, INK, 71))})`);
  root.style.setProperty('--tabrule', `url(${url(press(390, 8, (x) => { x.fillRect(0, 0, 390, 3); taper(x, line(0, 5, 390, 5, 6), 1.6); }, INK, 72))})`);
  // the hero block: ink with a carved border, a vermilion sun and a boat cut along the bottom edge
  const hero = root.querySelector('.hero'), val = root.querySelector('.hero .value');
  if (hero && val) { const room = hero.clientWidth - 44, fs = parseFloat(getComputedStyle(val).fontSize); if (val.scrollWidth > room) val.style.fontSize = Math.floor(fs * room / val.scrollWidth) + 'px'; }
  if (hero) { const w = hero.offsetWidth, h = hero.offsetHeight;
    const inkPlate = press(w, h, (x) => { x.fill(jpoly(rectPts(1, 1, w - 2, h - 2), n, 1.2, 9));
      carve(x, (c) => { c.lineWidth = 2; c.stroke(jpoly(rectPts(8, 8, w - 16, h - 16), n, 0.9, 9));
        const sx = w - 74, sy = h - 92; c.beginPath(); c.arc(sx, sy, 46, 0, TAU); c.fill();
        for (let k = 0; k < 4; k++) { const yy = h - 36 + k * 5; for (let xx = w * 0.5 + r() * 20; xx < w - 14;) { const len = 14 + r() * 40; taper(c, line(xx, yy, xx + len, yy, 5), 2.2 - k * 0.15); xx += len + 8 + r() * 14; } }
        for (let k = 0; k < 4; k++) taper(c, line(w * 0.56 + k * 5, 14, w - 18, 14 + k * 5, 6), 1.5); });
      for (const [d, wd] of [[8, 3], [17, 2.4], [27, 1.8], [38, 1.2]]) { const rr = 26 + d; for (let a = r() * TAU, e = a + TAU; a < e;) { const sw = 0.4 + r() * 0.9;
        taper(x, [...Array(10)].map((_, i) => [w - 74 + Math.cos(a + sw * i / 9) * rr, h - 92 + Math.sin(a + sw * i / 9) * rr]), wd); a += sw + 0.2 + r() * 0.3; } }
      const bx = w - 120, by = h - 74; x.beginPath(); x.moveTo(bx, by); x.lineTo(bx + 92, by); x.lineTo(bx + 80, by + 16); x.lineTo(bx + 10, by + 16); x.closePath(); x.fill();
      x.fillRect(bx + 22, by - 13, 44, 13); x.fillRect(bx + 30, by - 22, 26, 9); x.fillRect(bx + 50, by - 34, 7, 12); carve(x, (c) => { for (let i = 0; i < 5; i++) c.fillRect(bx + 25 + i * 8, by - 9, 4, 4); }); }, INK, 81);
    const redPlate = press(w, h, (x) => { x.beginPath(); x.arc(w - 74, h - 92, 25, 0, TAU); x.fill(); carve(x, (c) => { c.lineWidth = 1.6; [8, 16].forEach((rr) => { c.beginPath(); c.arc(w - 74, h - 92, rr, 0.3, 5.2); c.stroke(); }); }); }, RED, 82);
    const [hc, hx] = L.offscreen(w * dpr, h * dpr); hx.drawImage(redPlate, 3, -2); hx.globalCompositeOperation = 'source-over'; hx.drawImage(inkPlate, 0, 0);
    hero.style.background = `url(${url(hc)}) center/100% 100% no-repeat`; }
  const cta = root.querySelector('.cta'); if (cta) { const w = cta.offsetWidth, h = cta.offsetHeight;
    const pl = press(w, h, (x) => { x.fill(jpoly(rectPts(1, 1, w - 2, h - 2), n, 1.1, 9)); carve(x, (c) => { for (let k = 0; k < 3; k++) taper(c, line(10, h - 9 - k * 4, 10 + 50 - k * 12, h - 9 - k * 4, 5), 1.3); }); }, RED, 91);
    root.style.setProperty('--ctabg', `url(${url(pl)})`); cta.style.backgroundColor = 'transparent'; }
}
