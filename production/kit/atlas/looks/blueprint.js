// 7 · Blueprint: cyanotype paper, white line work only. Heavy lines for silhouettes, hairlines for construction,
// section hatching for solids, dimension lines with arrowheads, centre marks, and a title block that holds the HUD.
export const meta = { id: 'blueprint' };
const C = { paper: '#1b4d92', paper2: '#143c78', deep: '#0f3166', line: '#eef8ff', cyan: '#a6dcff', dim: '#cfeaff',
  red: '#ffb4a4', halo: '#184686' };
const TAU = Math.PI * 2;
const MONO = '"IBM Plex Mono", monospace', COND = '"Barlow Condensed", sans-serif';

// ---- drafting primitives -------------------------------------------------------------------------------------
function lw(ctx, w, a = 1, color = C.line) { ctx.lineWidth = w; ctx.globalAlpha = a; ctx.strokeStyle = color; }
function seg(ctx, x0, y0, x1, y1) { ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.stroke(); }
function arrow(ctx, x, y, ang, len = 8) {   // a slim filled draughting arrowhead whose tip is at x,y
  ctx.save(); ctx.translate(x, y); ctx.rotate(ang); ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-len, -len * 0.26); ctx.lineTo(-len, len * 0.26); ctx.closePath();
  ctx.fillStyle = C.line; ctx.globalAlpha = 0.95; ctx.fill(); ctx.restore();
}
function label(ctx, text, x, y, { font = `500 11px ${MONO}`, align = 'center', color = C.dim, halo = 5, rot = 0, spacing = '1px' } = {}) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rot); ctx.font = font; ctx.textAlign = align; ctx.textBaseline = 'middle';
  ctx.letterSpacing = spacing; ctx.globalAlpha = 1;
  if (halo) { ctx.lineJoin = 'round'; ctx.lineWidth = halo; ctx.strokeStyle = C.halo; ctx.strokeText(text, 0, 0); }
  ctx.fillStyle = color; ctx.fillText(text, 0, 0); ctx.restore();
}
function dimH(ctx, x0, x1, y, from0, from1, text) {   // horizontal dimension: extension lines from y=from0/from1 to y
  lw(ctx, 0.7, 0.75); const g = Math.sign(y - from0) || 1;
  seg(ctx, x0, from0 + g * 4, x0, y + g * 6); seg(ctx, x1, from1 + g * 4, x1, y + g * 6);
  lw(ctx, 0.9, 0.95); seg(ctx, x0, y, x1, y); arrow(ctx, x0, y, Math.PI); arrow(ctx, x1, y, 0);
  label(ctx, text, (x0 + x1) / 2, y - 9, { font: `500 12px ${MONO}`, color: C.line });
}
function dimV(ctx, x, y0, y1, from0, from1, text) {   // vertical dimension at x; extension lines from x=from0/from1
  lw(ctx, 0.7, 0.75); const g = Math.sign(x - from0) || -1;
  seg(ctx, from0 + g * 4, y0, x + g * 6, y0); seg(ctx, from1 + g * 4, y1, x + g * 6, y1);
  lw(ctx, 0.9, 0.95); seg(ctx, x, y0, x, y1); arrow(ctx, x, y0, y0 < y1 ? -Math.PI / 2 : Math.PI / 2); arrow(ctx, x, y1, y0 < y1 ? Math.PI / 2 : -Math.PI / 2);
  label(ctx, text, x - 10, (y0 + y1) / 2, { font: `500 12px ${MONO}`, color: C.line, rot: -Math.PI / 2 });
}
function centreMark(ctx, x, y, r, a = 0.8) {   // centre lines: a small cross plus long dash-dot arms past the outline
  lw(ctx, 0.6, a); ctx.setLineDash([]); seg(ctx, x - 4, y, x + 4, y); seg(ctx, x, y - 4, x, y + 4);
  ctx.setLineDash([10, 3, 2, 3]); seg(ctx, x - r - 8, y, x - 7, y); seg(ctx, x + 7, y, x + r + 8, y); seg(ctx, x, y - r - 8, x, y - 7); seg(ctx, x, y + 7, x, y + r + 8);
  ctx.setLineDash([]);
}
function hatch(ctx, clip, x0, y0, x1, y1, gap, ang = Math.PI / 4, w = 0.6, a = 0.4, rule = 'nonzero') {
  ctx.save(); ctx.clip(clip, rule); lw(ctx, w, a); ctx.beginPath();
  const d = Math.hypot(x1 - x0, y1 - y0), cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, c = Math.cos(ang), s = Math.sin(ang);
  for (let t = -d / 2; t <= d / 2; t += gap) { const px = cx - s * t, py = cy + c * t; ctx.moveTo(px - c * d, py - s * d); ctx.lineTo(px + c * d, py + s * d); }
  ctx.stroke(); ctx.restore();
}
function boxOf(path, pts) { let a = Infinity, b = Infinity, c = -Infinity, d = -Infinity; for (const [x, y] of pts) { a = Math.min(a, x); b = Math.min(b, y); c = Math.max(c, x); d = Math.max(d, y); } return [a, b, c, d]; }
function overlap(a, b) { const w = Math.min(a[2], b[2]) - Math.max(a[0], b[0]), h = Math.min(a[3], b[3]) - Math.max(a[1], b[1]); return w > 0 && h > 0 ? w * h : 0; }

// ---- the drawing ----------------------------------------------------------------------------------------------
export function game(ctx, S, L, W, H) {
  const hero = S.hero, hb = [hero.x, hero.y, hero.x + hero.size, hero.y + hero.size];
  // cyanotype paper: an uneven wash, darker at the edges where the print was exposed longest
  const g = ctx.createRadialGradient(W * 0.45, H * 0.42, 60, W * 0.5, H * 0.5, W * 0.72);
  g.addColorStop(0, C.paper); g.addColorStop(0.75, C.paper2); g.addColorStop(1, C.deep);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  const [mc, mx] = L.offscreen(96, 54), n = L.noise2(11), im = mx.createImageData(96, 54);
  for (let y = 0; y < 54; y++) for (let x = 0; x < 96; x++) { const v = n(x / 9, y / 9) * 0.65 + n(x / 3.5 + 40, y / 3.5) * 0.35, i = (y * 96 + x) * 4;
    im.data[i] = 150; im.data[i + 1] = 205; im.data[i + 2] = 255; im.data[i + 3] = Math.max(0, v - 0.45) * 90; }
  mx.putImageData(im, 0, 0); ctx.imageSmoothingEnabled = true; ctx.drawImage(mc, 0, 0, W, H);
  // drafting grid: 10-unit hairlines, 50-unit major lines
  ctx.beginPath(); for (let x = 0; x <= W; x += 10) { ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, H); } for (let y = 0; y <= H; y += 10) { ctx.moveTo(0, y + 0.5); ctx.lineTo(W, y + 0.5); }
  lw(ctx, 0.4, 0.09, C.cyan); ctx.stroke();
  ctx.beginPath(); for (let x = 0; x <= W; x += 50) { ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, H); } for (let y = 0; y <= H; y += 50) { ctx.moveTo(0, y + 0.5); ctx.lineTo(W, y + 0.5); }
  lw(ctx, 0.7, 0.16, C.cyan); ctx.stroke(); ctx.globalAlpha = 1;
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';

  // sheet frame with zone references
  lw(ctx, 1.6, 0.85); ctx.strokeRect(14, 14, W - 28, H - 28); lw(ctx, 0.6, 0.6); ctx.strokeRect(22, 22, W - 44, H - 44);
  for (let i = 1; i < 8; i++) { const x = 14 + (W - 28) * i / 8; lw(ctx, 0.6, 0.6); seg(ctx, x, 14, x, 22); seg(ctx, x, H - 22, x, H - 14); }
  for (let i = 1; i < 4; i++) { const y = 14 + (H - 28) * i / 4; seg(ctx, 14, y, 22, y); seg(ctx, W - 22, y, W - 14, y); }
  for (let i = 0; i < 8; i++) label(ctx, String(i + 1), 14 + (W - 28) * (i + 0.5) / 8, 18.5, { font: `500 7px ${MONO}`, halo: 0, color: C.cyan });
  for (let i = 0; i < 4; i++) label(ctx, 'ABCD'[i], 18, 14 + (H - 28) * (i + 0.5) / 4, { font: `500 7px ${MONO}`, halo: 0, color: C.cyan });

  const solids = new Path2D(); for (const [x, y, w, h] of S.platforms || []) solids.rect(x, y, w, h);
  const blds = L.buildings(S), bpath = new Path2D(); for (const [x, y, w, h] of blds) bpath.rect(x, y, w, h);
  const outside = (p) => { const q = new Path2D(); q.rect(-10, -10, W + 20, H + 20); q.addPath(p); return q; };

  // sun or moon: a drafted circle with its centre lines and a radius callout
  if (S.sun) { const { x, y, r } = S.sun, moon = S.mood === 'night';
    ctx.shadowColor = 'rgba(190,230,255,.6)'; ctx.shadowBlur = 4;
    lw(ctx, 1.8, 0.95); ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.stroke(); ctx.shadowBlur = 0;
    lw(ctx, 0.6, 0.55); ctx.setLineDash([4, 3]); ctx.beginPath(); ctx.arc(x, y, r * 0.64, 0, TAU); ctx.stroke(); ctx.setLineDash([]);
    if (moon) { ctx.save(); ctx.beginPath(); ctx.arc(x, y, r, 0, TAU); ctx.clip(); lw(ctx, 1.2, 0.9); ctx.beginPath(); ctx.arc(x + r * 0.45, y - r * 0.2, r * 0.9, 0, TAU); ctx.stroke(); ctx.restore(); }
    else for (let i = 0; i < 16; i++) { const a = i * TAU / 16, r0 = r + 9, r1 = r + (i % 2 ? 15 : 22); lw(ctx, i % 2 ? 0.6 : 1, 0.7); seg(ctx, x + Math.cos(a) * r0, y + Math.sin(a) * r0, x + Math.cos(a) * r1, y + Math.sin(a) * r1); }
    centreMark(ctx, x, y, r + 22, 0.55);
    const a = -Math.PI * 0.78, ex = x + Math.cos(a) * r, ey = y + Math.sin(a) * r;
    lw(ctx, 0.8, 0.9); seg(ctx, x, y, ex, ey); arrow(ctx, ex, ey, a, 7); seg(ctx, ex, ey, ex - 28, ey - 22); seg(ctx, ex - 28, ey - 22, ex - 62, ey - 22);
    label(ctx, `R${Math.round(r)}  ${moon ? 'MOON' : 'SUN'}`, ex - 64, ey - 31, { align: 'left', font: `500 11px ${MONO}`, color: C.line });
  }

  // far hills: a light profile with sparse section hatching, hidden behind the buildings
  if (S.far && S.far.length) {
    const fp = L.farPolygon(S, W, H), clip = new Path2D(fp);
    ctx.save(); ctx.clip(outside(bpath), 'evenodd'); ctx.clip(outside(solids), 'evenodd');
    hatch(ctx, clip, 0, 0, W, H, 9, -Math.PI / 4, 0.5, 0.22);
    ctx.beginPath(); ctx.moveTo(S.far[0][0], S.far[0][1]); for (const [x, y] of S.far) ctx.lineTo(x, y); lw(ctx, 1.1, 0.7); ctx.stroke();
    ctx.restore();
  }

  // mid buildings: medium outlines, window grids, hidden lines dashed where a solid covers them
  for (const [x, y, w, h] of blds) {
    const r = new Path2D(); r.rect(x, y, w, h);
    ctx.save(); ctx.clip(outside(solids), 'evenodd');
    lw(ctx, 1.3, 0.85); ctx.stroke(r);
    lw(ctx, 0.6, 0.6); seg(ctx, x - 3, y + 5, x + w + 3, y + 5);   // parapet
    lw(ctx, 0.5, 0.5); ctx.beginPath();
    for (let wy = y + 16; wy < y + h - 14; wy += 20) for (let wx = x + 8; wx + 8 <= x + w - 6; wx += 15) ctx.rect(wx, wy, 8, 10);
    ctx.stroke(); ctx.restore();
    ctx.save(); ctx.clip(solids); lw(ctx, 0.7, 0.45); ctx.setLineDash([5, 4]); ctx.stroke(r); ctx.setLineDash([]); ctx.restore();
  }
  if (blds.length) {   // a level marker on the tallest block
    const [x, y, w, h] = blds.reduce((a, b) => (b[3] > a[3] ? b : a));
    const lx = x + w / 2; lw(ctx, 0.8, 0.9); ctx.beginPath(); ctx.moveTo(lx - 6, y - 10); ctx.lineTo(lx + 6, y - 10); ctx.lineTo(lx, y - 2); ctx.closePath(); ctx.stroke();
    seg(ctx, lx - 6, y - 10, lx + 48, y - 10); label(ctx, `+${Math.round(h)}`, lx + 9, y - 18, { align: 'left', font: `500 10px ${MONO}` });
  }

  // hazards: cross-hatched solids with a heavy outline and a keep-clear callout
  const hz = S.hazards || [];
  for (const z of hz) {
    const p = L.hazardPath(z);
    hatch(ctx, p, z.x, z.y, z.x + z.w, z.y + z.h, 4, Math.PI / 4, 0.55, 0.55); hatch(ctx, p, z.x, z.y, z.x + z.w, z.y + z.h, 4, -Math.PI / 4, 0.55, 0.55);
    lw(ctx, 1.7, 0.95); ctx.stroke(p);
    if (z.kind === 'spikes') { lw(ctx, 1.2, 0.8); seg(ctx, z.x, z.y + z.h, z.x + z.w, z.y + z.h); }
  }
  if (hz.length) { const z = hz.reduce((a, b) => (b.w * b.h > a.w * a.h ? b : a)), ax = z.x + z.w * 0.5, ay = z.y + Math.min(z.h * 0.5, 12);
    const up = z.y > 120, tx = ax + (ax > W - 200 ? -70 : 60), ty = up ? z.y - 22 : z.y + z.h + 22;
    lw(ctx, 0.8, 0.9); ctx.beginPath(); ctx.arc(ax, ay, 2.2, 0, TAU); ctx.fillStyle = C.line; ctx.fill(); seg(ctx, ax, ay, tx, ty); seg(ctx, tx, ty, tx + (tx > ax ? 56 : -56), ty);
    label(ctx, 'KEEP CLEAR', tx + (tx > ax ? 2 : -2), ty - 8, { align: tx > ax ? 'left' : 'right', font: `600 10px ${MONO}`, color: C.red }); }

  // platforms: heavy profiles with section hatching, the walking surface heaviest
  for (const [x, y, w, h] of S.platforms || []) {
    const p = new Path2D(); p.rect(x, y, w, h);
    hatch(ctx, p, x, y, x + w, y + h, 7, Math.PI / 4, 0.6, 0.32);
    ctx.shadowColor = 'rgba(190,230,255,.45)'; ctx.shadowBlur = 3;
    lw(ctx, 1.9, 0.95); ctx.strokeRect(x, y, w, h); lw(ctx, 3, 1); seg(ctx, x, y, x + w, y); ctx.shadowBlur = 0;
    lw(ctx, 0.5, 0.5); seg(ctx, x + 4, y + 5, x + w - 4, y + 5);
  }

  // the dimension that matters most: the widest gap between neighbouring solids (else the biggest hazard)
  const all = (S.platforms || []).slice().sort((a, b) => a[0] - b[0]), grounded = all.filter(([, y, , h]) => y + h >= H - 4);
  const pl = grounded.length >= 2 ? grounded : all;
  let gap = null; for (let i = 0; i < pl.length - 1; i++) { const a = pl[i], b = pl[i + 1], d = b[0] - (a[0] + a[2]);
    if (d > 24 && (!gap || d > gap.d)) gap = { a, b, d }; }
  if (gap) { const { a, b, d } = gap, x0 = a[0] + a[2], x1 = b[0], y = Math.max(a[1], b[1]) + 42; dimH(ctx, x0, x1, y, a[1], b[1], `${Math.round(d)}`); label(ctx, 'GAP', (x0 + x1) / 2, y + 10, { font: `500 9px ${MONO}`, color: C.cyan }); }
  else if (hz.length) { const z = hz.reduce((a, b) => (Math.max(b.w, b.h) > Math.max(a.w, a.h) ? b : a));
    if (z.h > z.w) dimV(ctx, z.x - 22, z.y, z.y + z.h, z.x, z.x, `${Math.round(z.h)}`); else dimH(ctx, z.x, z.x + z.w, z.y - 22, z.y, z.y, `${Math.round(z.w)}`); }

  // wind / motion lines: dashed hairlines with an arrow
  for (const ln of S.lines || []) { if (ln.length < 2) continue; lw(ctx, 0.8, 0.7); ctx.setLineDash([7, 4]); L.smooth(ctx, ln); ctx.stroke(); ctx.setLineDash([]);
    const [p, q] = [ln[ln.length - 2], ln[ln.length - 1]]; arrow(ctx, q[0], q[1], Math.atan2(q[1] - p[1], q[0] - p[0]), 7); }

  // the trail: a dash-dot path with station points (arc) or a taut drawn line (string)
  const t = S.trail || [], kind = L.trailKind(S);
  if (t.length > 1) {
    if (kind === 'string') { lw(ctx, 1.2, 0.95); L.smooth(ctx, t); ctx.stroke(); const [ax, ay] = t[t.length - 1];
      lw(ctx, 1.1, 0.95); ctx.beginPath(); ctx.arc(ax, ay, 4, 0, TAU); ctx.stroke(); seg(ctx, ax - 9, ay, ax + 9, ay); }
    else { lw(ctx, 1, 0.9); ctx.setLineDash([12, 4, 2, 4]); L.smooth(ctx, t); ctx.stroke(); ctx.setLineDash([]);
      t.slice(0, -1).forEach(([x, y]) => { lw(ctx, 0.8, 0.85); ctx.beginPath(); ctx.arc(x, y, 2.6, 0, TAU); ctx.stroke(); });
      const [p, q] = [t[t.length - 2], t[t.length - 1]]; arrow(ctx, q[0] - 10, q[1], Math.atan2(q[1] - p[1], q[0] - p[0]), 9); }
    // the height dimension: the jump's rise (arc) or the hero's altitude over the ground (string)
    if (kind === 'string') { const cx = hero.x + hero.size / 2, cy = hero.y + hero.size / 2;
      const under = (S.platforms || []).filter(([x, y, w]) => cx >= x && cx <= x + w && y > cy).map((p) => p[1]);
      const gy = under.length ? Math.min(...under) : (S.ground_y || H); const dx = hero.x + hero.size + 26;
      if (gy - cy > 50) dimV(ctx, dx, cy, gy, cx + 6, cx + 6, `${Math.round(gy - cy)}`); }
    else { const y0 = t[0][1], ap = t.reduce((a, b) => (b[1] < a[1] ? b : a)), dx = Math.min(...t.map((p) => p[0])) - 26;
      if (y0 - ap[1] > 40 && dx > 40) dimV(ctx, dx, y0, ap[1], t[0][0], ap[0] - hero.size / 2, `${Math.round(y0 - ap[1])}`); }
  }

  // pickups: drafted outlines with centre marks and one quantity callout
  const pk = S.pickups || [];
  for (const c of pk) { const p = L.pickupPath(S, c); lw(ctx, 1.5, 0.95); ctx.stroke(p);
    lw(ctx, 0.5, 0.6); ctx.save(); ctx.clip(p); ctx.beginPath(); ctx.arc(c.x, c.y, (c.r || 11) * 0.55, 0, TAU); ctx.stroke(); ctx.restore();
    centreMark(ctx, c.x, c.y, (c.r || 11), 0.6); }
  if (pk.length) { const c = pk.reduce((a, b) => (b.y < a.y ? b : a)), r = c.r || 11, tx = c.x + r + 16, ty = c.y - r - 26;
    lw(ctx, 0.8, 0.9); seg(ctx, c.x + r * 0.7, c.y - r * 0.7, tx, ty); seg(ctx, tx, ty, tx + 66, ty);
    const shape = S.pickup_path ? 'ITEM' : `Ø${Math.round(2 * r)}`; label(ctx, `${pk.length}× ${shape}`, tx + 2, ty - 8, { align: 'left', font: `500 11px ${MONO}`, color: C.line }); }

  // the hero: the heaviest line on the sheet, a pale wash, a hatched accent and a balloon callout
  const hp = L.heroPath(hero);
  ctx.fillStyle = 'rgba(214,238,255,.2)'; ctx.fill(hp);
  hatch(ctx, hp, hb[0], hb[1], hb[2], hb[3], 5, -Math.PI / 4, 0.5, 0.35);
  if (hero.accent) { const ap = L.heroPath(hero, 'accent'); ctx.fillStyle = C.halo; ctx.fill(ap); hatch(ctx, ap, hb[0], hb[1], hb[2], hb[3], 2.4, Math.PI / 4, 0.8, 0.95); lw(ctx, 1.2, 1); ctx.stroke(ap); }
  ctx.shadowColor = 'rgba(200,236,255,.85)'; ctx.shadowBlur = 6; lw(ctx, 3.2, 1); ctx.stroke(hp); ctx.shadowBlur = 0;
  const e = L.heroEye(hero);
  if (e) { ctx.globalAlpha = 1; ctx.fillStyle = C.line; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.05, 0, TAU); ctx.fill(); lw(ctx, 0.5, 0.8); seg(ctx, e.x - e.r * 2.6, e.y, e.x + e.r * 2.6, e.y); seg(ctx, e.x, e.y - e.r * 2.6, e.x, e.y + e.r * 2.6); }
  { const left = hb[2] + 110 > W - 30, bx = left ? hb[0] - 34 : hb[2] + 34, by = hb[1] - 14;
    lw(ctx, 0.8, 0.95); seg(ctx, left ? hb[0] + hero.size * 0.15 : hb[2] - hero.size * 0.15, hb[1] + hero.size * 0.2, bx, by);
    ctx.fillStyle = C.halo; ctx.globalAlpha = 1; ctx.beginPath(); ctx.arc(bx, by, 11, 0, TAU); ctx.fill(); lw(ctx, 1.2, 1); ctx.stroke();
    label(ctx, '1', bx, by + 0.5, { font: `600 12px ${MONO}`, color: C.line, halo: 0, spacing: '0px' });
    label(ctx, 'HERO', bx + (left ? -16 : 16), by, { align: left ? 'right' : 'left', font: `600 11px ${MONO}`, color: C.line }); }

  // ---- HUD: the title block, placed in the emptiest lower/upper corner -----------------------------------------
  const BW = 280, BH = 100, cand = [[W - 22 - BW, H - 22 - BH], [22, 22], [22, H - 22 - BH]];
  const busy = [[hb, 12], ...pk.map((c) => [[c.x - 14, c.y - 14, c.x + 14, c.y + 14], 5]), ...hz.map((z) => [[z.x, z.y, z.x + z.w, z.y + z.h], 3]),
    ...(S.sun ? [[[S.sun.x - S.sun.r - 22, S.sun.y - S.sun.r - 22, S.sun.x + S.sun.r + 22, S.sun.y + S.sun.r + 22], 2]] : []), ...(t.length ? [[boxOf(null, t), 1]] : [])];
  const score = ([x, y]) => busy.reduce((s, [b, k]) => s + overlap([x, y, x + BW, y + BH], b) * k, 0);
  const [tx, ty] = cand.reduce((a, b) => (score(b) < score(a) - 1 ? b : a));
  ctx.globalAlpha = 1; ctx.fillStyle = C.paper2; ctx.fillRect(tx, ty, BW, BH);
  lw(ctx, 1.8, 1); ctx.strokeRect(tx, ty, BW, BH); lw(ctx, 0.7, 0.85);
  seg(ctx, tx, ty + 72, tx + BW, ty + 72); seg(ctx, tx + 150, ty, tx + 150, ty + 72); seg(ctx, tx + 150, ty + 36, tx + BW, ty + 36);
  seg(ctx, tx + 120, ty + 72, tx + 120, ty + BH); seg(ctx, tx + 200, ty + 72, tx + 200, ty + BH);
  const H_ = S.hud || {};
  label(ctx, (H_.score_label || 'SCORE').toUpperCase(), tx + 10, ty + 12, { align: 'left', font: `500 9px ${MONO}`, color: C.cyan, halo: 0 });
  ctx.font = `800 50px ${COND}`; ctx.fillStyle = C.line; ctx.textBaseline = 'alphabetic'; ctx.letterSpacing = '1px'; ctx.textAlign = 'left'; ctx.fillText(String(H_.score ?? ''), tx + 9, ty + 66);
  const [bl, ...bv] = String(H_.best || '').split(' ');
  label(ctx, bv.length ? bl.toUpperCase() : 'BEST', tx + 160, ty + 11, { align: 'left', font: `500 9px ${MONO}`, color: C.cyan, halo: 0 });
  label(ctx, bv.length ? bv.join(' ') : bl, tx + BW - 10, ty + 23, { align: 'right', font: `600 20px ${COND}`, color: C.line, halo: 0, spacing: '1px' });
  label(ctx, 'LIVES', tx + 160, ty + 47, { align: 'left', font: `500 9px ${MONO}`, color: C.cyan, halo: 0 });
  if (H_.lives != null) { const n = Math.max(3, H_.lives); for (let i = 0; i < n; i++) { const cx = tx + BW - 16 - (n - 1 - i) * 18, cy = ty + 58;
    ctx.globalAlpha = 1; ctx.beginPath(); ctx.arc(cx, cy, 5.5, 0, TAU); lw(ctx, 1.2, 1); ctx.stroke(); if (i < H_.lives) { ctx.fillStyle = C.line; ctx.fill(); } } }
  const title = (S.title || 'GAME SCENE').toUpperCase();
  label(ctx, 'DWG', tx + 8, ty + 80, { align: 'left', font: `500 7px ${MONO}`, color: C.cyan, halo: 0 });
  label(ctx, title.length > 16 ? title.slice(0, 15) + '…' : title, tx + 8, ty + 91, { align: 'left', font: `600 10px ${MONO}`, color: C.line, halo: 0, spacing: '0.5px' });
  label(ctx, 'SCALE', tx + 128, ty + 80, { align: 'left', font: `500 7px ${MONO}`, color: C.cyan, halo: 0 }); label(ctx, '1 : 1', tx + 128, ty + 91, { align: 'left', font: `600 10px ${MONO}`, color: C.line, halo: 0 });
  label(ctx, 'SHEET', tx + 208, ty + 80, { align: 'left', font: `500 7px ${MONO}`, color: C.cyan, halo: 0 }); label(ctx, '01 / 01', tx + 208, ty + 91, { align: 'left', font: `600 10px ${MONO}`, color: C.line, halo: 0 });
  // pause: a detail bubble in the free top corner
  if (H_.pause) { const px = (tx > W / 2 && ty < H / 2) ? 52 : W - 52, py = 52;
    ctx.globalAlpha = 1; ctx.fillStyle = C.paper2; ctx.beginPath(); ctx.arc(px, py, 22, 0, TAU); ctx.fill(); lw(ctx, 1.8, 1); ctx.stroke(); lw(ctx, 0.6, 0.7); ctx.beginPath(); ctx.arc(px, py, 26, 0, TAU); ctx.stroke();
    ctx.fillStyle = C.line; ctx.fillRect(px - 7, py - 9, 5, 18); ctx.fillRect(px + 2, py - 9, 5, 18); }
  ctx.globalAlpha = 1;
  L.grain(ctx, W, H, 0.05, 5);
}

// ---- the app ----------------------------------------------------------------------------------------------------
export const appCss = `
.app{--ink:#eef8ff;--cy:#a6dcff;--paper:#1b4d92;--deep:#143c78;font-family:"IBM Plex Mono",monospace;color:var(--ink);box-sizing:border-box;
  display:flex;flex-direction:column;padding:54px 20px 0;
  background:
    linear-gradient(rgba(166,220,255,.16) 1px,transparent 1px) -1px -1px/50px 50px,
    linear-gradient(90deg,rgba(166,220,255,.16) 1px,transparent 1px) -1px -1px/50px 50px,
    linear-gradient(rgba(166,220,255,.07) 1px,transparent 1px) -1px -1px/10px 10px,
    linear-gradient(90deg,rgba(166,220,255,.07) 1px,transparent 1px) -1px -1px/10px 10px,
    radial-gradient(120% 80% at 45% 35%,#1d529a 0%,#173f7b 70%,#10336a 100%)}
.app *{box-sizing:border-box}
.top{display:flex;justify-content:space-between;align-items:flex-end;padding-bottom:10px;border-bottom:1.5px solid var(--ink);position:relative}
.top::after{content:'';position:absolute;left:0;right:0;bottom:-6px;border-bottom:1px solid rgba(238,248,255,.5)}
.brand{font:800 32px/1 "Barlow Condensed",sans-serif;letter-spacing:.12em;text-transform:uppercase}
.place{font-size:14px;color:var(--cy);letter-spacing:.04em;text-align:right}
.place::before{content:'LOC ';font-size:10px;letter-spacing:.14em;opacity:.85}
.hero{position:relative;margin-top:30px;border:1.5px solid var(--ink);padding:18px 18px 20px;background:rgba(12,42,92,.42)}
.hero::before,.hero::after{content:'';position:absolute;width:14px;height:14px;border:0 solid var(--ink)}
.hero::before{left:-7px;top:-7px;border-width:0 1px 1px 0}
.hero::after{right:-7px;bottom:-7px;border-width:1px 0 0 1px}
.label{font-size:14px;letter-spacing:.16em;text-transform:uppercase;color:var(--cy)}
.value{font:800 112px/0.92 "Barlow Condensed",sans-serif;letter-spacing:.03em;color:transparent;-webkit-text-stroke:2px var(--ink);margin:12px 0 38px;display:inline-block}
.sub{font-size:14px;line-height:1.45;color:var(--ink)}
.status{position:absolute;top:14px;right:14px;font-size:14px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;border:1.5px solid var(--ink);padding:5px 10px 4px;background:var(--deep)}
.status::before{content:'✓ '}
.rows-title{margin:30px 0 0;font:600 14px "IBM Plex Mono",monospace;letter-spacing:.16em;text-transform:uppercase;display:flex;justify-content:space-between;
  border:1.5px solid var(--ink);border-bottom:0;padding:9px 12px 8px;background:rgba(12,42,92,.42)}
.rows-title::after{content:'SCHED · 02';color:var(--cy);font-weight:500;letter-spacing:.1em}
.rows{list-style:none;margin:0;padding:0;border:1.5px solid var(--ink);display:grid;grid-template-columns:72px 1fr auto}
.rows li{grid-column:1/-1;display:grid;grid-template-columns:subgrid;align-items:stretch;min-height:60px;border-top:1px solid rgba(238,248,255,.55)}
.rows li>span{display:flex;align-items:center;padding:0 12px}
.rows li>span+span{border-left:1px solid rgba(238,248,255,.55)}
.rows .t{font:600 24px "Barlow Condensed",sans-serif;letter-spacing:.04em}
.rows .d{font:600 18px "Barlow Condensed",sans-serif;letter-spacing:.04em}
.rows .s{font:600 16px/1.1 "Barlow Condensed",sans-serif;letter-spacing:.03em;white-space:nowrap;text-transform:uppercase;color:var(--cy)}
.rows li[data-state=late] .s{color:#ffb4a4}
.rows li[data-state=late] .s::before{content:'△';margin-right:5px}
.rows li[data-state=few] .s{color:#ffe08a}
.rows li[data-state=few] .s::before{content:'◇';margin-right:5px}
.rows li[data-state=ok] .s::before{content:'○';margin-right:5px}
.cta{position:relative;flex:none;margin:auto 4px 26px;height:58px;border:0;border-radius:0;background:var(--ink);color:#123a74;cursor:pointer;
  font:800 23px "Barlow Condensed",sans-serif;letter-spacing:.2em;text-transform:uppercase;box-shadow:0 0 0 4px #184686,0 0 0 5px rgba(238,248,255,.7)}
.cta::after{content:'→';margin-left:12px}
.tabs{margin:0 -20px 0;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 8px 30px;border-top:1.5px solid var(--ink);background:rgba(10,38,84,.72);position:relative}
.tabs::before{content:'';position:absolute;left:0;right:0;top:4px;border-top:1px solid rgba(238,248,255,.35)}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;min-height:52px;font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--cy);margin:0 6px;border:1px solid transparent}
.tabs a.on{color:var(--ink);border-color:var(--ink);background:rgba(238,248,255,.08)}
.ic{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round}
.bp-dim{position:absolute;pointer-events:none;overflow:visible}
`;

export function appDecor(root) {
  // a dimension line under the departure time: extension lines from the figure's ends, arrowheads and a note
  const hero = root.querySelector('.hero'), val = root.querySelector('.value'), sub = root.querySelector('.sub');
  if (!hero || !val) return;
  // fit the outlined figure to the card (long values shrink), then leave room under its lowest glyph for the dimension
  const cs = getComputedStyle(val), inner = hero.clientWidth - 36, text = val.textContent;
  const cv = document.createElement('canvas').getContext('2d'), fam = cs.fontFamily, size0 = parseFloat(cs.fontSize);
  cv.font = `800 ${size0}px ${fam}`; let size = size0, m = cv.measureText(text);
  if (m.width > inner - 8) { size = Math.floor(size0 * (inner - 8) / m.width); val.style.fontSize = size + 'px'; cv.font = `800 ${size}px ${fam}`; m = cv.measureText(text); }
  const lh = parseFloat(getComputedStyle(val).lineHeight) || size * 0.92, baseline = (lh - (m.fontBoundingBoxAscent + m.fontBoundingBoxDescent)) / 2 + m.fontBoundingBoxAscent;
  const below = m.actualBoundingBoxDescent - (lh - baseline);   // how far the glyphs hang below the line box
  val.style.marginBottom = Math.max(38, below + 40) + 'px';
  const hr = hero.getBoundingClientRect(), range = document.createRange(); range.selectNodeContents(val);
  const vr = range.getBoundingClientRect(), vb = val.getBoundingClientRect(), x0 = vr.left - hr.left + 2, x1 = vr.right - hr.left - 2;
  const yb = vb.top - hr.top + baseline + m.actualBoundingBoxDescent, y = yb + 24, room = hr.width - (vr.right - hr.left);
  const mm = /(\d+)\s*min/i.exec(sub ? sub.textContent : ''), note = mm ? `T − ${mm[1]} MIN` : 'DETAIL A';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'bp-dim');
  svg.setAttribute('width', hr.width); svg.setAttribute('height', hr.height); svg.style.left = '-1.5px'; svg.style.top = '-1.5px';
  const mid = (x0 + x1) / 2, ink = '#eef8ff';
  svg.innerHTML = `<g stroke="${ink}" fill="none" stroke-linecap="round">
      <path d="M${x0} ${yb + 4}V${y + 6}M${x1} ${yb + 4}V${y + 6}" stroke-width=".8" opacity=".8"/>
      <path d="M${x0} ${y}H${mid - 56}M${mid + 56} ${y}H${x1}" stroke-width="1"/></g>
    <g fill="${ink}"><path d="M${x0} ${y}l9 -2.4v4.8z"/><path d="M${x1} ${y}l-9 -2.4v4.8z"/></g>
    <text x="${mid}" y="${y + 4.5}" fill="${ink}" font-family="IBM Plex Mono" font-weight="600" font-size="13" letter-spacing="1.5" text-anchor="middle">${note.toUpperCase()}</text>
    ${room < 84 ? '' : `<g stroke="#a6dcff" stroke-width=".7" fill="none" opacity=".9"><circle cx="${hr.width - 44}" cy="${vb.top - hr.top + baseline - m.actualBoundingBoxAscent / 2}" r="13"/>
      <path d="M${hr.width - 64} ${vb.top - hr.top + baseline - m.actualBoundingBoxAscent / 2}h40M${hr.width - 44} ${vb.top - hr.top + baseline - m.actualBoundingBoxAscent / 2 - 20}v40" stroke-dasharray="6 2 1.5 2"/></g>`}`;
  hero.appendChild(svg);
}
