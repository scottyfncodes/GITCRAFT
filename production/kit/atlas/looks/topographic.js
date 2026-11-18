// 13 · Topographic Map: the scene read as terrain. A height field is built from the scene (the far line is the
// coast and the land rises behind it, platforms are mesas, mid blocks are knolls, the sun is a peak, hazards are
// hollows, plus value noise), shaded with hypsometric tints and hillshade, and contoured with marching squares
// (every 5th line an index contour). Play objects sit on top as an orienteering overprint: course line, numbered
// controls, out-of-bounds hatching, a red "you are here" figure. Labels always carry a paper halo.
export const meta = { id: 'topographic' };
const TAU = Math.PI * 2;
const C = { paper: '#f5f0e1', ink: '#2b2622', brown: '#9a5f37', blue: '#3f7fab', mag: '#b02f86', red: '#d23a22', grid: 'rgba(63,127,171,.16)' };
const LAND = [[0, '#dce6c3'], [20, '#e6eac0'], [40, '#efe7b6'], [60, '#efdba4'], [80, '#e8ca93'], [100, '#deb887'], [125, '#d2a882'], [150, '#c99c85'], [180, '#d5c3b9'], [220, '#ece5df']];
const SEA = [[0, '#d7ecf1'], [-10, '#c8e3ec'], [-20, '#b8d9e6'], [-35, '#a7cee0'], [-55, '#98c3d9']];
const FONT = 'Overpass, sans-serif', DISP = '"Big Shoulders Display", sans-serif';
const hex = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));

function label(ctx, text, x, y, { size = 10, weight = 600, color = C.ink, align = 'left', spacing = 2, italic = false, halo = 4, font = FONT } = {}) {
  ctx.save(); ctx.font = `${italic ? 'italic ' : ''}${weight} ${size}px ${font}`; ctx.letterSpacing = spacing + 'px'; ctx.textAlign = align; ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round'; ctx.lineWidth = halo; ctx.strokeStyle = C.paper; ctx.strokeText(text, x, y); ctx.fillStyle = color; ctx.fillText(text, x, y); ctx.restore();
}

export function game(ctx, S, L, W, H) {
  const n = L.noise2(19), m = L.noise2(53), hero = S.hero;
  const far = S.far && S.far.length ? S.far : null, coastDefault = S.ground_y != null ? S.ground_y - 40 : H * 0.62;
  const farY = (x) => { if (!far) return coastDefault; if (x <= far[0][0]) return far[0][1];
    for (let i = 0; i < far.length - 1; i++) if (x <= far[i + 1][0]) { const t = (x - far[i][0]) / ((far[i + 1][0] - far[i][0]) || 1); return far[i][1] + (far[i + 1][1] - far[i][1]) * t; }
    return far[far.length - 1][1]; };
  const ridgeLow = far ? Math.max(...far.map((p) => p[1])) : coastDefault;
  const sm = (a, b, x) => { const t = Math.max(0, Math.min(1, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
  const plats = S.platforms || [], blds = L.buildings(S), hz = S.hazards || [];
  // ---- the height field --------------------------------------------------------------------------------------
  function elev(x, y) {
    const yf = farY(x) + (n(x / 70, 3.1) - 0.5) * 18, d = y - yf;
    let e;
    if (d < 0) e = d * 0.32 - 3 + (m(x / 90, y / 90) - 0.5) * 14;
    else { const amp = 46 + (ridgeLow - farY(x)) * 0.9; e = amp * (1 - Math.exp(-d / 80)) + (n(x / 120, y / 120) - 0.5) * 52 * sm(0, 60, d) + (m(x / 38, y / 38) - 0.5) * 14 * sm(0, 40, d); }
    for (const [px, py, pw, ph] of plats) { const dx = Math.max(px - x, 0, x - (px + pw)), dy = Math.max(py - y, 0, y - (py + ph)), dd = Math.hypot(dx, dy);
      e += (24 + (H - py) * 0.08) * (1 - sm(0, 34, dd)); }
    for (const [bx, by, bw, bh] of blds) { const cx = bx + bw / 2, cy = by + bh * 0.35, s2 = (bw * 0.75) ** 2; e += bh * 0.22 * Math.exp(-(((x - cx) ** 2) / s2 + ((y - cy) ** 2) / (s2 * 2.2))); }
    if (S.sun) { const dd = Math.hypot(x - S.sun.x, y - S.sun.y) / (S.sun.r * 2.9); if (dd < 1) e += 128 * Math.pow(1 - dd, 1.45) + (d < 0 ? 6 : 0); }
    for (const z of hz) { const cx = z.x + z.w / 2, cy = z.y + z.h / 2, rx = z.w * 0.6 + 14, ry = z.h * 0.6 + 14, dd = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2; if (dd < 1) e -= 22 * (1 - dd) ** 2; }
    return e;
  }
  const g = 3, nx = Math.ceil(W / g) + 1, ny = Math.ceil(H / g) + 1, E = new Float32Array(nx * ny);
  let lo = Infinity, hi = -Infinity;
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const v = elev(i * g, j * g); E[j * nx + i] = v; lo = Math.min(lo, v); hi = Math.max(hi, v); }
  const at = (x, y) => { const i = Math.max(0, Math.min(nx - 1, Math.round(x / g))), j = Math.max(0, Math.min(ny - 1, Math.round(y / g))); return E[j * nx + i]; };
  // ---- tints and hillshade --------------------------------------------------------------------------------------
  const tint = (e) => { const T = e >= 0 ? LAND : SEA; let c = T[0][1]; for (const [k, col] of T) if (e >= 0 ? e >= k : e <= k) c = col; return hex(c); };
  const [tc, tx] = L.offscreen(nx, ny), im = tx.createImageData(nx, ny);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const e = E[j * nx + i], c = tint(e), k = (j * nx + i) * 4;
    let sh = 1; if (e > 0) { const ex = E[j * nx + Math.min(nx - 1, i + 1)] - E[j * nx + Math.max(0, i - 1)], ey = E[Math.min(ny - 1, j + 1) * nx + i] - E[Math.max(0, j - 1) * nx + i]; sh = 1 + Math.max(-0.16, Math.min(0.12, (ex + ey) * 0.022)); }
    im.data[k] = c[0] * sh; im.data[k + 1] = c[1] * sh; im.data[k + 2] = c[2] * sh; im.data[k + 3] = 255; }
  tx.putImageData(im, 0, 0); ctx.imageSmoothingEnabled = true; ctx.drawImage(tc, 0, 0, nx * g, ny * g);
  // a faint survey grid
  ctx.strokeStyle = C.grid; ctx.lineWidth = 0.6; ctx.beginPath(); for (let x = 80; x < W; x += 80) { ctx.moveTo(x, 0); ctx.lineTo(x, H); } for (let y = 60; y < H; y += 80) { ctx.moveTo(0, y); ctx.lineTo(W, y); } ctx.stroke();
  // ---- contours (marching squares) ------------------------------------------------------------------------------
  const step = 10;
  for (let lev = Math.ceil(lo / step) * step; lev <= hi; lev += step) {
    const index = lev % (step * 5) === 0, sea = lev < 0, coast = lev === 0;
    ctx.beginPath();
    for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) {
      const a = E[j * nx + i], b = E[j * nx + i + 1], c = E[(j + 1) * nx + i + 1], d = E[(j + 1) * nx + i];
      const k = (a > lev ? 8 : 0) | (b > lev ? 4 : 0) | (c > lev ? 2 : 0) | (d > lev ? 1 : 0); if (k === 0 || k === 15) continue;
      const x = i * g, y = j * g, f = (p, q) => (lev - p) / ((q - p) || 1e-6);
      const T = [x + g * f(a, b), y], R = [x + g, y + g * f(b, c)], B = [x + g * f(d, c), y + g], Lf = [x, y + g * f(a, d)];
      const seg = (p, q) => { ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); };
      switch (k) { case 1: case 14: seg(Lf, B); break; case 2: case 13: seg(B, R); break; case 3: case 12: seg(Lf, R); break; case 4: case 11: seg(T, R); break;
        case 5: seg(Lf, T); seg(B, R); break; case 6: case 9: seg(T, B); break; case 7: case 8: seg(Lf, T); break; case 10: seg(T, R); seg(Lf, B); break; }
    }
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    if (coast) { ctx.strokeStyle = C.blue; ctx.globalAlpha = 0.95; ctx.lineWidth = 1.7; }
    else if (sea) { ctx.strokeStyle = C.blue; ctx.globalAlpha = index ? 0.6 : 0.35; ctx.lineWidth = index ? 1 : 0.55; }
    else { ctx.strokeStyle = C.brown; ctx.globalAlpha = index ? 0.85 : 0.5; ctx.lineWidth = index ? 1.35 : 0.6; }
    ctx.stroke(); ctx.globalAlpha = 1;
  }
  // index contour heights along the land
  if (far) for (let k = 0, x = 120; x < W - 120 && k < 4; x += 210) { for (let y = farY(x) + 20; y < H - 40; y += 2) { const e = at(x, y), lv = Math.round(e / 50) * 50;
      if (lv > 0 && Math.abs(e - lv) < 1.2) { label(ctx, String(lv), x, y, { size: 9, color: C.brown, spacing: 0.5, halo: 4 }); k++; break; } } }

  // ---- built-up areas, cliffs, hollows -------------------------------------------------------------------------
  { const rb = L.rng(77);
    for (const [x, y, w, h] of blds) {   // built-up area: a pale tint and a cluster of building footprints
      ctx.fillStyle = 'rgba(196,128,112,.16)'; L.rr(ctx, x + 2, y + 2, w - 4, h - 4, 6); ctx.fill();
      ctx.fillStyle = 'rgba(52,40,34,.78)';
      for (let yy = y + 7; yy < y + h - 8; yy += 11) for (let xx = x + 6; xx < x + w - 8; xx += 11) { if (rb() < 0.3) continue;
        const bw = 4 + rb() * 5, bh = 4 + rb() * 5; ctx.save(); ctx.translate(xx + bw / 2 + (rb() - 0.5) * 2, yy + bh / 2); ctx.rotate((rb() - 0.5) * 0.25); ctx.fillRect(-bw / 2, -bh / 2, bw, bh); ctx.restore(); } } }
  for (const [x, y, w, h] of plats) { ctx.strokeStyle = C.ink; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + w, y); ctx.stroke();
    ctx.lineWidth = 0.9; ctx.beginPath(); for (let u = x + 3; u < x + w - 1; u += 5) { ctx.moveTo(u, y); ctx.lineTo(u, y + 5); } ctx.stroke();
    ctx.setLineDash([5, 3]); ctx.lineWidth = 0.8; ctx.globalAlpha = 0.6; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x, Math.min(H, y + h)); ctx.moveTo(x + w, y); ctx.lineTo(x + w, Math.min(H, y + h)); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1; }
  // sun: a summit with its spot height
  if (S.sun) { const { x, y, r } = S.sun, top = Math.round(at(x, y));
    ctx.fillStyle = C.ink; ctx.beginPath(); ctx.moveTo(x, y - 6); ctx.lineTo(x + 5.5, y + 4); ctx.lineTo(x - 5.5, y + 4); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = C.ink; ctx.lineWidth = 1; for (let i = 0; i < 8; i++) { const a = i * TAU / 8; ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * 10, y + Math.sin(a) * 10); ctx.lineTo(x + Math.cos(a) * 14, y + Math.sin(a) * 14); ctx.stroke(); }
    label(ctx, S.mood === 'night' ? 'MOON HILL' : 'SUN HILL', x, y + r * 0.62 + 4, { size: 11, weight: 800, spacing: 2.5 }); label(ctx, String(top), x, y + r * 0.62 + 18, { size: 10, spacing: 0.5, italic: true, color: C.brown }); }

  // label placement: every label claims a box; a later label takes the first candidate spot that is free
  const taken = [[24, 24, 266, 174], [W - 300, 24, W - 24, 86], [24, H - 70, 236, H - 20], [W - 112, H - 122, W - 20, H - 20]];
  const free = (b) => !taken.some((t) => b[0] < t[2] && b[2] > t[0] && b[1] < t[3] && b[3] > t[1]) && b[0] > 22 && b[2] < W - 22 && b[1] > 22 && b[3] < H - 22;
  const place = (cands) => { for (const c of cands) if (free(c.box)) { taken.push(c.box); return c; } taken.push(cands[0].box); return cands[0]; };
  const tw = (text, size, sp) => { ctx.save(); ctx.font = `800 ${size}px ${FONT}`; ctx.letterSpacing = sp + 'px'; const w = ctx.measureText(text).width; ctx.restore(); return w; };
  taken.push([hero.x - 4, hero.y - 4, hero.x + hero.size + 4, hero.y + hero.size + 4]);
  for (const c of S.pickups || []) { const r = (c.r || 11) + 3; taken.push([c.x - r, c.y - r, c.x + r, c.y + r]); }
  // ---- overprint: hazards, wind, course, controls, the hero ---------------------------------------------------------
  for (const z of hz) { const p = L.hazardPath(z);
    if (z.kind === 'path') { ctx.lineJoin = 'round'; ctx.strokeStyle = C.paper; ctx.lineWidth = 4; ctx.stroke(p); ctx.fillStyle = C.ink; ctx.fill(p); }
    else { ctx.save(); ctx.clip(p); ctx.fillStyle = 'rgba(176,47,134,.18)'; ctx.fillRect(z.x, z.y, z.w, z.h); ctx.strokeStyle = C.mag; ctx.lineWidth = 1.4; ctx.beginPath(); for (let u = z.x + 3; u < z.x + z.w; u += 5) { ctx.moveTo(u, z.y); ctx.lineTo(u, z.y + z.h); } ctx.stroke(); ctx.restore();
      ctx.strokeStyle = C.mag; ctx.lineWidth = 1.6; ctx.stroke(p); } }
  const hzLabel = hz.length ? hz.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a)) : null;
  if (hzLabel) { const z = hzLabel, w = tw('OUT OF BOUNDS', 10, 1.5) + 6, cx = z.x + z.w / 2;
    const at2 = (x, y) => ({ x, y, box: [x - w / 2, y - 8, x + w / 2, y + 8] });
    const c = place([at2(cx, z.y + z.h + 12), at2(cx, z.y - 12), at2(z.x - w / 2 - 8, z.y + z.h / 2), at2(z.x + z.w + w / 2 + 8, z.y + z.h / 2), at2(z.x - w / 2 - 8, z.y + 14)]);
    label(ctx, 'OUT OF BOUNDS', c.x, c.y, { size: 10, weight: 800, color: C.mag, align: 'center', italic: true, spacing: 1.5 }); }
  ctx.lineCap = 'round';
  for (const ln of S.lines || []) { if (ln.length < 2) continue; ctx.strokeStyle = C.blue; ctx.lineWidth = 1.3; ctx.setLineDash([9, 4]); L.smooth(ctx, ln); ctx.stroke(); ctx.setLineDash([]);
    const [p, q] = [ln[ln.length - 2], ln[ln.length - 1]], a = Math.atan2(q[1] - p[1], q[0] - p[0]); ctx.fillStyle = C.blue; ctx.beginPath(); ctx.moveTo(q[0] + Math.cos(a) * 4, q[1] + Math.sin(a) * 4);
    ctx.lineTo(q[0] - Math.cos(a - 0.45) * 9, q[1] - Math.sin(a - 0.45) * 9); ctx.lineTo(q[0] - Math.cos(a + 0.45) * 9, q[1] - Math.sin(a + 0.45) * 9); ctx.fill(); }
  if ((S.lines || []).length) { const ln = S.lines[0], mid = ln[Math.floor(ln.length / 2)]; label(ctx, 'WIND', mid[0], mid[1] - 11, { size: 9, color: C.blue, weight: 800, align: 'center', spacing: 3, italic: true }); }
  const t = S.trail || [];
  if (t.length > 1) {
    if (L.trailKind(S) === 'string') { ctx.strokeStyle = C.mag; ctx.lineWidth = 1.6; ctx.setLineDash([2, 4]); L.smooth(ctx, t); ctx.stroke(); ctx.setLineDash([]);
      const [ax, ay] = t[t.length - 1]; ctx.strokeStyle = C.mag; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(ax - 7, ay - 7); ctx.lineTo(ax + 7, ay + 7); ctx.moveTo(ax + 7, ay - 7); ctx.lineTo(ax - 7, ay + 7); ctx.stroke(); }
    else { ctx.strokeStyle = C.paper; ctx.lineWidth = 4.5; L.smooth(ctx, t); ctx.stroke(); ctx.strokeStyle = C.mag; ctx.lineWidth = 2; L.smooth(ctx, t); ctx.stroke();
      const [sx, sy] = t[0], [qx, qy] = t[1], a = Math.atan2(qy - sy, qx - sx); ctx.fillStyle = C.paper; ctx.strokeStyle = C.mag; ctx.lineWidth = 2.2; ctx.beginPath();
      for (let i = 0; i < 3; i++) { const b = a + i * TAU / 3; ctx[i ? 'lineTo' : 'moveTo'](sx + Math.cos(b) * 11, sy + Math.sin(b) * 11); } ctx.closePath(); ctx.fill(); ctx.stroke();
      label(ctx, 'START', sx - 14, sy + 4, { size: 9, weight: 800, color: C.mag, align: 'right', spacing: 2 }); }
  }
  const elevTxt = `${Math.round(at(hero.x + hero.size / 2, hero.y + hero.size)) + Math.round(hero.size / 2)} m`, hw = tw('YOU ARE HERE', 10, 2.5) + 6;
  const hl = (x, y, align) => ({ x, y, align, box: align === 'left' ? [x - 2, y - 8, x + hw, y + 22] : [x - hw, y - 8, x + 2, y + 22] });
  const heroLab = place([hl(hero.x + hero.size + 12, hero.y + hero.size * 0.15, 'left'), hl(hero.x - 12, hero.y + hero.size * 0.15, 'right'),
    hl(hero.x + hero.size + 12, hero.y + hero.size * 0.75, 'left'), hl(hero.x - 12, hero.y + hero.size * 0.75, 'right'), hl(hero.x, hero.y + hero.size + 16, 'left')]);
  (S.pickups || []).forEach((c, i) => { const p = L.pickupPath(S, c), r = c.r || 11;
    ctx.lineJoin = 'round'; ctx.strokeStyle = C.paper; ctx.lineWidth = 5; ctx.stroke(p); ctx.fillStyle = 'rgba(176,47,134,.14)'; ctx.fill(p); ctx.strokeStyle = C.mag; ctx.lineWidth = 2; ctx.stroke(p);
    ctx.fillStyle = C.mag; ctx.beginPath(); ctx.arc(c.x, c.y, 1.6, 0, TAU); ctx.fill();
    const d = r * 0.8 + 8, nb = (x, y) => ({ x, y, box: [x - 6, y - 8, x + 6, y + 8] });
    const q = place([nb(c.x + d, c.y - d), nb(c.x - d, c.y - d), nb(c.x + d, c.y + d), nb(c.x - d, c.y + d), nb(c.x + d + 6, c.y)]);
    label(ctx, String(i + 1), q.x, q.y, { size: 13, weight: 800, color: C.mag, spacing: 0, halo: 4.5, align: 'center' }); });
  // hero: the one solid red thing on the sheet, haloed in paper, with its label
  const hp = L.heroPath(hero);
  ctx.save(); ctx.lineJoin = 'round'; ctx.strokeStyle = C.paper; ctx.lineWidth = 9; ctx.stroke(hp); ctx.shadowColor = 'rgba(60,30,10,.25)'; ctx.shadowBlur = 6; ctx.shadowOffsetY = 2; ctx.fillStyle = C.red; ctx.fill(hp); ctx.restore();
  if (hero.accent) { ctx.fillStyle = '#5b1209'; ctx.fill(L.heroPath(hero, 'accent')); }
  ctx.strokeStyle = '#7a1c0e'; ctx.lineWidth = 1.2; ctx.stroke(hp);
  const e = L.heroEye(hero); if (e) { ctx.fillStyle = C.paper; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.25, 0, TAU); ctx.fill(); ctx.fillStyle = '#3a0d06'; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 0.6, 0, TAU); ctx.fill(); }
  label(ctx, 'YOU ARE HERE', heroLab.x, heroLab.y, { size: 10, weight: 800, color: C.red, align: heroLab.align, spacing: 2.5 });
  label(ctx, elevTxt, heroLab.x, heroLab.y + 14, { size: 10, italic: true, color: C.brown, align: heroLab.align, spacing: 0.5 });
  // ---- marginalia: neatline with graticule, scale bar, compass rose ---------------------------------------------
  const M = 14; ctx.strokeStyle = C.ink; ctx.lineWidth = 1.6; ctx.strokeRect(M, M, W - 2 * M, H - 2 * M); ctx.lineWidth = 0.6; ctx.strokeRect(M + 5, M + 5, W - 2 * M - 10, H - 2 * M - 10);
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, M); ctx.fillRect(0, H - M, W, M); ctx.fillRect(0, 0, M, H); ctx.fillRect(W - M, 0, M, H);
  ctx.strokeStyle = C.ink; ctx.lineWidth = 1.6; ctx.strokeRect(M, M, W - 2 * M, H - 2 * M);
  for (let x = 80, k = 0; x < W - 40; x += 160, k++) { ctx.lineWidth = 0.8; ctx.beginPath(); ctx.moveTo(x, M); ctx.lineTo(x, M + 5); ctx.moveTo(x, H - M); ctx.lineTo(x, H - M - 5); ctx.stroke();
    ctx.font = `600 7px ${FONT}`; ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.letterSpacing = '0.5px'; ctx.fillText(`4°${String(12 + k * 4).padStart(2, '0')}′W`, x, M - 4); }
  const sbx = 40, sby = H - 42; ctx.fillStyle = 'rgba(245,240,225,.9)'; L.rr(ctx, sbx - 10, sby - 18, 196, 36, 3); ctx.fill();
  for (let i = 0; i < 4; i++) { ctx.fillStyle = i % 2 ? C.paper : C.ink; ctx.fillRect(sbx + i * 40, sby, 40, 5); } ctx.strokeStyle = C.ink; ctx.lineWidth = 0.8; ctx.strokeRect(sbx, sby, 160, 5);
  ctx.font = `600 8px ${FONT}`; ctx.fillStyle = C.ink; ctx.letterSpacing = '0.5px'; ctx.textAlign = 'center'; ['0', '100', '200', '300', '400 m'].forEach((s, i) => ctx.fillText(s, sbx + i * 40, sby - 5)); ctx.textAlign = 'left';
  label(ctx, 'CONTOUR INTERVAL 10 M', sbx, sby + 13, { size: 7, spacing: 1.2, halo: 0 });
  { const R = 26, busy = [[hero.x, hero.y, hero.x + hero.size, hero.y + hero.size], ...hz.map((z) => [z.x - 6, z.y - 6, z.x + z.w + 6, z.y + z.h + 6]), ...(S.pickups || []).map((c) => [c.x - 16, c.y - 16, c.x + 16, c.y + 16])];
    const cxs = [W - 62, W - 150, W - 238, W - 326], cy = H - 70, hit = (x) => busy.some((b) => x - R - 14 < b[2] && x + R + 14 > b[0] && cy - R - 26 < b[3] && cy + R + 14 > b[1]);
    const cx = cxs.find((x) => !hit(x)) ?? cxs[0]; ctx.fillStyle = 'rgba(245,240,225,.85)'; ctx.beginPath(); ctx.arc(cx, cy, R + 12, 0, TAU); ctx.fill();
    ctx.strokeStyle = C.ink; ctx.lineWidth = 0.7; ctx.beginPath(); ctx.arc(cx, cy, R * 0.72, 0, TAU); ctx.stroke(); ctx.beginPath(); ctx.arc(cx, cy, R + 4, 0, TAU); ctx.stroke();
    for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 - Math.PI / 2, l = i % 2 ? R * 0.55 : R, w = i % 2 ? 3 : 5;
      for (const side of [-1, 1]) { ctx.fillStyle = side < 0 ? C.ink : C.paper; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a) * l, cy + Math.sin(a) * l); ctx.lineTo(cx + Math.cos(a + side * Math.PI / 2) * w, cy + Math.sin(a + side * Math.PI / 2) * w); ctx.closePath(); ctx.fill(); ctx.strokeStyle = C.ink; ctx.lineWidth = 0.6; ctx.stroke(); } }
    label(ctx, 'N', cx, cy - R - 13, { size: 12, weight: 800, font: DISP, spacing: 0, align: 'center', halo: 0 }); }

  // ---- HUD: a title cartouche and a legend-style best/pause block -------------------------------------------------
  const hud = S.hud || {}, bx = 30, by = 30, bw = 226, bh = 134;
  ctx.save(); ctx.shadowColor = 'rgba(60,40,20,.18)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 2; ctx.fillStyle = C.paper; ctx.fillRect(bx, by, bw, bh); ctx.restore();
  ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5; ctx.strokeRect(bx, by, bw, bh); ctx.lineWidth = 0.6; ctx.strokeRect(bx + 4, by + 4, bw - 8, bh - 8);
  ctx.textBaseline = 'alphabetic'; ctx.textAlign = 'left'; ctx.fillStyle = C.ink; ctx.font = `800 17px ${DISP}`; ctx.letterSpacing = '3px'; ctx.fillText((S.title || 'Survey sheet').toUpperCase(), bx + 14, by + 26);
  ctx.lineWidth = 0.6; ctx.beginPath(); ctx.moveTo(bx + 14, by + 34); ctx.lineTo(bx + bw - 14, by + 34); ctx.stroke();
  ctx.font = `600 9px ${FONT}`; ctx.letterSpacing = '2.5px'; ctx.fillStyle = C.brown; ctx.fillText((hud.score_label || 'SCORE').toUpperCase(), bx + 14, by + 50);
  ctx.font = `900 50px ${DISP}`; ctx.letterSpacing = '1px'; ctx.fillStyle = C.ink; ctx.fillText(String(hud.score ?? ''), bx + 12, by + 98);
  if (hud.lives != null) { const k = Math.max(3, hud.lives); ctx.font = `600 9px ${FONT}`; ctx.letterSpacing = '2.5px'; ctx.fillStyle = C.brown; ctx.textAlign = 'right'; ctx.fillText('LIVES', bx + bw - 14, by + 50); ctx.textAlign = 'left';
    for (let i = 0; i < k; i++) { const tx = bx + bw - 22 - (k - 1 - i) * 20, ty = by + 72; ctx.beginPath(); ctx.moveTo(tx, ty - 8); ctx.lineTo(tx + 7.5, ty + 5); ctx.lineTo(tx - 7.5, ty + 5); ctx.closePath();
      if (i < hud.lives) { ctx.fillStyle = C.red; ctx.fill(); } else { ctx.strokeStyle = C.ink; ctx.lineWidth = 1.2; ctx.stroke(); } } }
  ctx.lineWidth = 0.6; ctx.strokeStyle = C.ink; ctx.beginPath(); ctx.moveTo(bx + 14, by + 108); ctx.lineTo(bx + bw - 14, by + 108); ctx.stroke();
  // legend strip
  ctx.font = `600 8px ${FONT}`; ctx.letterSpacing = '1.2px'; ctx.fillStyle = C.ink;
  ctx.fillStyle = C.red; ctx.fillRect(bx + 14, by + 115, 9, 9); ctx.fillStyle = C.ink; ctx.fillText('YOU', bx + 27, by + 123);
  ctx.strokeStyle = C.mag; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.arc(bx + 75, by + 119.5, 4.5, 0, TAU); ctx.stroke(); ctx.fillStyle = C.ink; ctx.fillText('CONTROL', bx + 84, by + 123);
  ctx.strokeStyle = C.brown; ctx.lineWidth = 1.3; ctx.beginPath(); ctx.moveTo(bx + 148, by + 120); ctx.bezierCurveTo(bx + 152, by + 114, bx + 156, by + 126, bx + 162, by + 119); ctx.stroke(); ctx.fillStyle = C.ink; ctx.fillText('100 M', bx + 166, by + 123);
  let rx = W - 30;
  if (hud.pause) { const s = 46; ctx.fillStyle = C.paper; ctx.fillRect(rx - s, 30, s, s); ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5; ctx.strokeRect(rx - s, 30, s, s); ctx.lineWidth = 0.6; ctx.strokeRect(rx - s + 4, 34, s - 8, s - 8);
    ctx.fillStyle = C.ink; ctx.fillRect(rx - s / 2 - 8, 42, 5, 22); ctx.fillRect(rx - s / 2 + 3, 42, 5, 22); rx -= s + 10; }
  if (hud.best) { ctx.font = `800 20px ${DISP}`; ctx.letterSpacing = '2px'; const w = ctx.measureText(hud.best.toUpperCase()).width + 28;
    ctx.fillStyle = C.paper; ctx.fillRect(rx - w, 30, w, 46); ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5; ctx.strokeRect(rx - w, 30, w, 46);
    ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.fillText(hud.best.toUpperCase(), rx - w / 2, 60); ctx.textAlign = 'left'; }
  ctx.letterSpacing = '0px';
  L.grain(ctx, W, H, 0.035, 13);
}

// ---- the app ----------------------------------------------------------------------------------------------------
export const appCss = `
.app{--ink:#2b2622;--brown:#8a5330;--paper:#f5f0e1;--mag:#a52a7c;--blue:#2f6c96;font-family:Overpass,sans-serif;color:var(--ink);box-sizing:border-box;display:flex;flex-direction:column;
  padding:54px 20px 0;background:var(--paper)}
.app *{box-sizing:border-box}
.topo-bg{position:absolute;inset:0;width:100%;height:100%;z-index:0;pointer-events:none}
.app>*:not(.topo-bg){position:relative;z-index:1}
.top{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:1.5px solid var(--ink);padding-bottom:8px}
.brand{font:900 34px/1 "Big Shoulders Display",sans-serif;letter-spacing:.08em;text-transform:uppercase}
.place{font-size:14px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--brown);text-align:right;line-height:1.2}
.hero{margin-top:18px;background:rgba(245,240,225,.94);border:1.5px solid var(--ink);outline:1px solid var(--ink);outline-offset:-6px;padding:20px 22px 20px;position:relative}
.hero::before{content:'57°12′N';position:absolute;top:-9px;left:16px;background:var(--paper);padding:0 6px;font-size:11px;font-weight:600;letter-spacing:.12em;color:var(--brown)}
.label{font-size:14px;font-weight:800;letter-spacing:.2em;text-transform:uppercase;color:var(--brown)}
.value{font:900 94px/0.95 "Big Shoulders Display",sans-serif;letter-spacing:.01em;margin:6px 0 6px}
.sub{font-size:15px;line-height:1.4;max-width:92%}
.status{display:inline-flex;align-items:center;gap:7px;margin-top:12px;font-size:14px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--mag)}
.status::before{content:'';width:12px;height:12px;border-radius:50%;border:2px solid currentColor}
.rows-title{margin:24px 0 6px;font:800 14px Overpass,sans-serif;letter-spacing:.24em;text-transform:uppercase;display:flex;align-items:center;gap:10px}
.rows-title::after{content:'';flex:1;border-top:1.5px solid var(--ink)}
.rows{list-style:none;margin:0;padding:0;background:rgba(245,240,225,.94);border:1.5px solid var(--ink)}
.rows li{display:grid;grid-template-columns:34px 64px 1fr auto;align-items:center;min-height:60px;padding:0 14px 0 10px;border-top:1px solid rgba(43,38,34,.25)}
.rows li:first-child{border-top:0}
.rows li::before{content:'';height:0;border-top:3px solid #3c7d4a;margin-right:10px}
.rows li[data-state=late]::before{border-top:3px dashed var(--mag)}
.rows li[data-state=few]::before{border-top:3px dotted #9a6a10}
.rows .t{font:800 24px "Big Shoulders Display",sans-serif;letter-spacing:.04em}
.rows .d{font-size:15px;font-weight:600}
.rows .s{font-size:14px;font-style:italic;font-weight:600;color:#2f6b3c}
.rows li[data-state=late] .s{color:var(--mag)}
.rows li[data-state=few] .s{color:#7a5208}
.cta{margin:auto 0 24px;height:58px;border:1.5px solid var(--ink);border-radius:0;background:var(--ink);color:var(--paper);cursor:pointer;
  font:900 24px "Big Shoulders Display",sans-serif;letter-spacing:.16em;text-transform:uppercase;box-shadow:0 0 0 4px var(--paper),0 0 0 5.5px var(--ink)}
.tabs{margin:0 -20px;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 8px 30px;background:var(--paper);border-top:1.5px solid var(--ink)}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:50px;font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#6b5f55}
.tabs a.on{color:var(--mag)}
.ic{width:25px;height:25px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}
`;

export function appDecor(root, A, L) {
  // faint contours behind the whole screen: a small height field run through marching squares
  const W = root.clientWidth, H = root.clientHeight, dpr = 2, [c, x] = L.offscreen(W * dpr, H * dpr); x.scale(dpr, dpr);
  const n = L.noise2(7), m = L.noise2(29), g = 4, nx = Math.ceil(W / g) + 1, ny = Math.ceil(H / g) + 1, E = new Float32Array(nx * ny);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const X = i * g, Y = j * g; E[j * nx + i] = n(X / 150, Y / 150) * 90 + m(X / 60, Y / 60) * 22 + 60 * Math.exp(-(((X - W * 0.82) / 90) ** 2 + ((Y - H * 0.36) / 120) ** 2)); }
  x.fillStyle = C.paper; x.fillRect(0, 0, W, H);
  for (let lev = 10, k = 1; lev < 180; lev += 6, k++) { x.beginPath();
    for (let j = 0; j < ny - 1; j++) for (let i = 0; i < nx - 1; i++) { const a = E[j * nx + i], b = E[j * nx + i + 1], cc = E[(j + 1) * nx + i + 1], d = E[(j + 1) * nx + i];
      const q = (a > lev ? 8 : 0) | (b > lev ? 4 : 0) | (cc > lev ? 2 : 0) | (d > lev ? 1 : 0); if (q === 0 || q === 15) continue;
      const X = i * g, Y = j * g, f = (p, r) => (lev - p) / ((r - p) || 1e-6), T = [X + g * f(a, b), Y], R = [X + g, Y + g * f(b, cc)], B = [X + g * f(d, cc), Y + g], Lf = [X, Y + g * f(a, d)];
      const s = (p, r) => { x.moveTo(p[0], p[1]); x.lineTo(r[0], r[1]); };
      switch (q) { case 1: case 14: s(Lf, B); break; case 2: case 13: s(B, R); break; case 3: case 12: s(Lf, R); break; case 4: case 11: s(T, R); break;
        case 5: s(Lf, T); s(B, R); break; case 6: case 9: s(T, B); break; case 7: case 8: s(Lf, T); break; case 10: s(T, R); s(Lf, B); break; } }
    x.strokeStyle = 'rgba(154,95,55,' + (k % 5 === 0 ? 0.42 : 0.2) + ')'; x.lineWidth = k % 5 === 0 ? 1.1 : 0.6; x.stroke(); }
  c.className = 'topo-bg'; root.prepend(c);
  // a tiny orienteering course beside the status: start triangle, leg, numbered control, finish
  const hero = root.querySelector('.hero'), st = root.querySelector('.hero .status'); if (hero && st) { const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 112 40'); svg.setAttribute('aria-hidden', 'true');
    svg.style.cssText = `position:absolute;right:20px;top:${st.offsetTop + st.offsetHeight / 2 - 22}px;width:112px;height:40px;overflow:visible`;
    const mg = '#a52a7c';
    svg.innerHTML = `<g fill="none" stroke="${mg}" stroke-width="1.8" stroke-linecap="round">
      <path d="M4 32l9-16 9 16z"/><path d="M24 25h22M64 25h20"/><circle cx="55" cy="25" r="8"/><circle cx="96" cy="25" r="9"/><circle cx="96" cy="25" r="5.2"/></g>
      <text x="51" y="10" fill="${mg}" font-family="Overpass" font-weight="800" font-size="13">1</text>`;
    hero.appendChild(svg); }
}
