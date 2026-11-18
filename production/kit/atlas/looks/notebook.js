// 14 · Notebook Sketch: the scene drawn on lined notebook paper. Every outline (including the scene's own SVG paths,
// flattened here) is redrawn as 2–3 jittered pencil or pen passes driven by L.noise2; fills are pencil hatching, marker
// scribbles and a yellow highlighter; the HUD is hand-lettered in Caveat. Deterministic: every wobble is seeded.
export const meta = { id: 'notebook' };
const P = { paper: '#fbf9f1', rule: '#b8cde6', margin: '#e59a9a', pencil: '#3b3b43', pen: '#1d2a5e', blue: '#2346a8', red: '#e0483a',
  hi: 'rgba(255,226,60,.62)', orange: '#f08a3a', green: '#4f8a4a' };

// ---- SVG path → polylines (M L H V C S Q T A Z, absolute and relative), mapped through f(x, y) ----
function flatten(d, f) {
  const tk = d.match(/[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:e[-+]?\d+)?/g) || [], out = []; let i = 0, cmd = '', cur = null, x = 0, y = 0, sx = 0, sy = 0, cx = 0, cy = 0, pc = '';
  const num = () => parseFloat(tk[i++]); const push = (px, py) => cur.push(f(px, py));
  const bez = (x0, y0, x1, y1, x2, y2, x3, y3) => { for (let t = 1; t <= 12; t++) { const u = t / 12, a = (1 - u) ** 3, b = 3 * u * (1 - u) ** 2, c = 3 * u * u * (1 - u), e = u ** 3; push(a * x0 + b * x1 + c * x2 + e * x3, a * y0 + b * y1 + c * y2 + e * y3); } };
  while (i < tk.length) {
    if (/[a-zA-Z]/.test(tk[i])) cmd = tk[i++]; else if (cmd === 'M') cmd = 'L'; else if (cmd === 'm') cmd = 'l';
    const rel = cmd === cmd.toLowerCase(), C = cmd.toUpperCase(), ox = rel ? x : 0, oy = rel ? y : 0;
    if (C === 'M') { x = ox + num(); y = oy + num(); sx = x; sy = y; cur = []; out.push(cur); push(x, y); }
    else if (C === 'Z') { if (cur) { push(sx, sy); cur.closed = true; } x = sx; y = sy; cur = null; }
    else { if (!cur) { cur = [f(x, y)]; out.push(cur); }
      if (C === 'L') { x = ox + num(); y = oy + num(); push(x, y); }
      else if (C === 'H') { x = (rel ? x : 0) + num(); push(x, y); }
      else if (C === 'V') { y = (rel ? y : 0) + num(); push(x, y); }
      else if (C === 'C') { const a = ox + num(), b = oy + num(), c = ox + num(), e = oy + num(), g = ox + num(), h = oy + num(); bez(x, y, a, b, c, e, g, h); cx = c; cy = e; x = g; y = h; }
      else if (C === 'S') { const a = /[CS]/i.test(pc) ? 2 * x - cx : x, b = /[CS]/i.test(pc) ? 2 * y - cy : y, c = ox + num(), e = oy + num(), g = ox + num(), h = oy + num(); bez(x, y, a, b, c, e, g, h); cx = c; cy = e; x = g; y = h; }
      else if (C === 'Q' || C === 'T') { const q = C === 'Q', a = q ? ox + num() : (/[QT]/i.test(pc) ? 2 * x - cx : x), b = q ? oy + num() : (/[QT]/i.test(pc) ? 2 * y - cy : y), g = ox + num(), h = oy + num();
        bez(x, y, x + 2 / 3 * (a - x), y + 2 / 3 * (b - y), g + 2 / 3 * (a - g), h + 2 / 3 * (b - h), g, h); cx = a; cy = b; x = g; y = h; }
      else if (C === 'A') { let rx = Math.abs(num()), ry = Math.abs(num()); const phi = num() * Math.PI / 180, fa = num(), fs = num(), x2 = ox + num(), y2 = oy + num();
        const cs = Math.cos(phi), sn = Math.sin(phi), dx = (x - x2) / 2, dy = (y - y2) / 2, x1p = cs * dx + sn * dy, y1p = -sn * dx + cs * dy;
        const lam = x1p * x1p / (rx * rx) + y1p * y1p / (ry * ry); if (lam > 1) { rx *= Math.sqrt(lam); ry *= Math.sqrt(lam); }
        const sg = fa === fs ? -1 : 1, num2 = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p, co = sg * Math.sqrt(Math.max(0, num2 / (rx * rx * y1p * y1p + ry * ry * x1p * x1p)));
        const cxp = co * rx * y1p / ry, cyp = -co * ry * x1p / rx, ccx = cs * cxp - sn * cyp + (x + x2) / 2, ccy = sn * cxp + cs * cyp + (y + y2) / 2;
        const ang = (ux, uy, vx, vy) => Math.atan2(ux * vy - uy * vx, ux * vx + uy * vy);
        const t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry); let dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry);
        if (!fs && dt > 0) dt -= 2 * Math.PI; if (fs && dt < 0) dt += 2 * Math.PI;
        for (let k = 1; k <= 20; k++) { const t = t1 + dt * k / 20; push(ccx + rx * Math.cos(t) * cs - ry * Math.sin(t) * sn, ccy + rx * Math.cos(t) * sn + ry * Math.sin(t) * cs); }
        x = x2; y = y2; }
      else i++;
    }
    pc = C;
  }
  return out.filter((p) => p.length > 1);
}

// resample a polyline every `step` px
function resample(pts, step, closed) {
  const src = closed && (pts[0][0] !== pts.at(-1)[0] || pts[0][1] !== pts.at(-1)[1]) ? [...pts, pts[0]] : pts, out = [src[0]];
  let carry = 0;
  for (let i = 0; i < src.length - 1; i++) { const [ax, ay] = src[i], [bx, by] = src[i + 1], d = Math.hypot(bx - ax, by - ay);
    let s = step - carry; while (s < d) { out.push([ax + (bx - ax) * s / d, ay + (by - ay) * s / d]); s += step; } carry = d - (s - step); }
  out.push(src.at(-1)); return out;
}

export function game(ctx, S, L, W, H) {
  let seed = 100;
  // a hand stroke: 2–3 passes, each point nudged by smooth noise, closed shapes overshoot their start a little
  const stroke = (pts, { color = P.pencil, width = 1.7, passes = 2, amp = 1.6, closed = false, alpha = 0.85, step = 5 } = {}) => {
    if (pts.length < 2) return; const rp = resample(pts, step, closed); seed++;
    for (let p = 0; p < passes; p++) { const n = L.noise2(seed * 7 + p * 13), ox = (n(p * 9.1, 3.3) - 0.5) * amp, oy = (n(4.4, p * 7.7) - 0.5) * amp;
      const q = rp.map(([x, y], i) => [x + ox + (n(i * 0.22, p * 5) - 0.5) * 2 * amp, y + oy + (n(i * 0.22 + 50, p * 5 + 9) - 0.5) * 2 * amp]);
      if (closed) q.push(...q.slice(1, 3 + p).map(([x, y]) => [x + amp * 0.6, y - amp * 0.4]));
      ctx.save(); ctx.globalAlpha = alpha * (p ? 0.7 : 1); ctx.strokeStyle = color; ctx.lineWidth = width * (p ? 0.75 : 1); ctx.lineCap = 'round'; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.moveTo(q[0][0], q[0][1]);
      for (let i = 1; i < q.length - 1; i++) ctx.quadraticCurveTo(q[i][0], q[i][1], (q[i][0] + q[i + 1][0]) / 2, (q[i][1] + q[i + 1][1]) / 2);
      ctx.lineTo(q.at(-1)[0], q.at(-1)[1]); ctx.stroke(); ctx.restore(); }
  };
  // hatching inside a Path2D: wobbly parallel lines at an angle
  const hatch = (path, box, { angle = -0.9, gap = 7, color = P.pencil, width = 1, alpha = 0.45, cross = false } = {}) => {
    const [x, y, w, h] = box, cx = x + w / 2, cy = y + h / 2, R = Math.hypot(w, h) / 2 + 4;
    ctx.save(); ctx.clip(path);
    for (const a of cross ? [angle, angle + 1.45] : [angle]) { const ca = Math.cos(a), sa = Math.sin(a);
      for (let d = -R; d <= R; d += gap) stroke([[cx + ca * -R - sa * d, cy + sa * -R + ca * d], [cx + ca * R - sa * d, cy + sa * R + ca * d]], { color, width, passes: 1, amp: 0.7, alpha, step: 12 }); }
    ctx.restore();
  };
  // a marker scribble: a tight zigzag filling the path
  const scribble = (path, box, { color = P.blue, width = 5, gap = 4, alpha = 0.9, angle = 0.5 } = {}) => {
    const [x, y, w, h] = box, cx = x + w / 2, cy = y + h / 2, R = Math.hypot(w, h) / 2 + 2, ca = Math.cos(angle), sa = Math.sin(angle), r = L.rng(seed++);
    const pts = []; let s = 1; for (let d = -R; d <= R; d += gap) { const j = (r() - 0.5) * 3; pts.push([cx + ca * -R * s - sa * d + j, cy + sa * -R * s + ca * d], [cx + ca * R * s - sa * d - j, cy + sa * R * s + ca * d]); s = -s; }
    ctx.save(); ctx.clip(path); ctx.globalAlpha = alpha; ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.beginPath(); pts.forEach(([a, b], i) => ctx[i ? 'lineTo' : 'moveTo'](a, b)); ctx.stroke(); ctx.restore();
  };
  const bbox = (polys) => { let a = Infinity, b = Infinity, c = -Infinity, d = -Infinity; for (const p of polys) for (const [x, y] of p) { a = Math.min(a, x); b = Math.min(b, y); c = Math.max(c, x); d = Math.max(d, y); } return [a, b, c - a, d - b]; };
  const rectPts = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]];
  const circlePts = (x, y, r, n = 28) => Array.from({ length: n + 1 }, (_, i) => [x + Math.cos(i / n * Math.PI * 2 - 2) * r, y + Math.sin(i / n * Math.PI * 2 - 2) * r]);
  const mood = S.mood || 'day';

  // ---- the page: lined paper, a red margin, punched holes ----
  ctx.fillStyle = P.paper; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = P.rule; for (let y = 52; y < H; y += 26) ctx.fillRect(0, y, W, 1);
  ctx.fillStyle = P.margin; ctx.fillRect(66, 0, 1.2, H); ctx.fillRect(70, 0, 0.8, H);
  for (const y of [H * 0.18, H * 0.5, H * 0.82]) { ctx.fillStyle = '#e9e5d8'; ctx.beginPath(); ctx.arc(28, y, 10, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,.08)'; ctx.lineWidth = 1; ctx.stroke(); }
  // the light: a coloured-pencil wash low in the sky at dawn and dusk, graphite at night
  const gy = S.ground_y || H * 0.8;
  if (mood === 'dusk' || mood === 'dawn') hatch(new Path2D(`M0 ${gy * 0.45}H${W}V${gy}H0Z`), [0, gy * 0.45, W, gy * 0.55], { color: P.orange, gap: 9, alpha: 0.22, angle: -0.5 });
  if (mood === 'night') hatch(new Path2D(`M0 0H${W}V${gy}H0Z`), [0, 0, W, gy], { color: P.pencil, gap: 6, alpha: 0.18, angle: -0.6, cross: true });

  // sun: highlighter disc, an orange outline, doodled rays
  if (S.sun) { const { x, y, r } = S.sun, c = new Path2D(); c.arc(x, y, r, 0, Math.PI * 2);
    scribble(c, [x - r, y - r, 2 * r, 2 * r], { color: 'rgb(255,214,40)', width: 9, gap: 6, alpha: 0.55, angle: -0.4 });
    stroke(circlePts(x, y, r), { color: P.orange, width: 2.2, passes: 2, amp: 1.8, closed: true });
    if (mood !== 'night') for (let k = 0; k < 12; k++) { const a = k / 12 * Math.PI * 2 + 0.2; stroke([[x + Math.cos(a) * (r + 9), y + Math.sin(a) * (r + 9)], [x + Math.cos(a) * (r + 22 + (k % 2) * 7), y + Math.sin(a) * (r + 22 + (k % 2) * 7)]], { color: P.orange, width: 2, passes: 1, amp: 0.8 }); } }
  // far hills: a pencil ridge with loose hatching under it
  if (S.far) { const fp = L.farPolygon(S, W, H); hatch(fp, [0, Math.min(...S.far.map((p) => p[1])), W, H], { gap: 10, alpha: 0.32, angle: -0.95 });
    stroke(S.far, { width: 1.6, passes: 2, amp: 1.4 }); }
  // mid blocks: pencil boxes, a hatched shady side, little window squares
  const Rw = L.rng(17);
  for (const [x, y, w, h] of L.buildings(S)) {
    const side = new Path2D(); side.rect(x + w * 0.62, y, w * 0.38, h);
    const body = new Path2D(); body.rect(x, y, w, h); ctx.save(); ctx.fillStyle = P.paper; ctx.fill(body); ctx.restore();
    hatch(side, [x + w * 0.62, y, w * 0.38, h], { gap: 4.5, alpha: 0.4, angle: -1.1 });
    stroke(rectPts(x, y, w, h), { width: 1.7, passes: 2, amp: 1.3, closed: true });
    for (let wy = y + 14; wy < y + h - 18; wy += 24) for (let wx = x + 8; wx < x + w * 0.55 - 6; wx += 15) if (Rw() < 0.55) stroke(rectPts(wx, wy, 7, 9), { width: 1.1, passes: 1, amp: 0.6, step: 4 });
  }
  // platforms: pen outline, cross-hatched body, a heavy top edge
  for (const [x, y, w, h] of S.platforms || []) { const p = new Path2D(); p.rect(x, y, w, h);
    ctx.save(); ctx.fillStyle = P.paper; ctx.fill(p); ctx.restore();
    hatch(p, [x, y, w, h], { gap: 7, alpha: 0.42, cross: true, angle: -0.8 });
    stroke(rectPts(x, y, w, h), { color: P.pen, width: 2, passes: 2, amp: 1.2, closed: true });
    stroke([[x, y + 1], [x + w, y + 1]], { color: P.pen, width: 3.2, passes: 2, amp: 1 }); }
  // hazards: red marker
  for (const hz of S.hazards || []) {
    let polys;
    if (hz.kind === 'spikes') { const n = Math.max(3, Math.round(hz.w / 22)), tw = hz.w / n; polys = Array.from({ length: n }, (_, i) => [[hz.x + i * tw, hz.y + hz.h], [hz.x + i * tw + tw / 2, hz.y], [hz.x + (i + 1) * tw, hz.y + hz.h]]); }
    else if (hz.kind === 'path' && hz.path) { const [bw, bh] = hz.box || [hz.w, hz.h]; polys = flatten(hz.path, (px, py) => [hz.x + px * hz.w / bw, hz.y + py * hz.h / bh]); }
    else polys = [rectPts(hz.x, hz.y, hz.w, hz.h)];
    scribble(L.hazardPath(hz), bbox(polys), { color: P.red, width: 3.2, gap: 3.5, alpha: 0.75, angle: 1.2 });
    for (const p of polys) stroke(p, { color: '#b42a20', width: 1.9, passes: 2, amp: 1, closed: true, step: 4 });
  }
  // wind lines: quick pencil swooshes
  for (const ln of S.lines || []) stroke(ln, { width: 1.5, passes: 2, amp: 1.2, alpha: 0.7 });
  // trail: dashed pencil (a jump arc) or a wobbly string
  const t = S.trail || [];
  if (t.length > 1) { if (L.trailKind(S) === 'string') stroke(t, { width: 1.5, passes: 2, amp: 1.5 });
    else { const rp = resample(t, 4, false); for (let i = 0; i < rp.length - 3; i += 5) stroke(rp.slice(i, i + 3), { width: 1.6, passes: 1, amp: 0.5, step: 3 }); } }
  // pickups: highlighter-yellow, outlined in pen
  for (const c of S.pickups || []) { const r = c.r || 11; let polys;
    if (S.pickup_path) polys = flatten(S.pickup_path, (px, py) => [c.x - r + px * r / 12, c.y - r + py * r / 12]);
    else if (S.pickup_shape === 'diamond') polys = [[[c.x, c.y - r * 1.25], [c.x + r, c.y], [c.x, c.y + r * 1.25], [c.x - r, c.y], [c.x, c.y - r * 1.25]]];
    else if (S.pickup_shape === 'star') polys = [Array.from({ length: 11 }, (_, i) => { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.48 : r * 1.15; return [c.x + Math.cos(a) * rr, c.y + Math.sin(a) * rr]; })];
    else polys = [circlePts(c.x, c.y, r, 18)];
    scribble(L.pickupPath(S, c), bbox(polys), { color: 'rgb(255,206,30)', width: 5, gap: 3.5, alpha: 0.8, angle: -0.6 });
    for (const p of polys) stroke(p, { color: P.pen, width: 1.6, passes: 2, amp: 0.8, closed: true, step: 3 }); }
  // hero: dense blue ballpoint scribble, a firm three-pass pen outline, a red marker accent, a white eye
  const h = S.hero, k = h.size / 64, fx = (px, py) => [h.x + (h.facing < 0 ? h.size - px * k : px * k), h.y + py * k];
  const hp = L.heroPath(h), hpolys = flatten(h.path || '', fx), hb = bbox(hpolys);
  ctx.save(); ctx.fillStyle = P.paper; ctx.fill(hp); ctx.restore();
  scribble(hp, hb, { color: P.blue, width: 3.6, gap: 2.6, alpha: 0.95, angle: 0.7 });
  if (h.accent) { const ap = L.heroPath(h, 'accent'), apolys = flatten(h.accent, fx);
    scribble(ap, bbox(apolys), { color: P.red, width: 4, gap: 2.4, alpha: 0.95, angle: -0.3 });
    for (const p of apolys) stroke(p, { color: '#9e1e16', width: 1.4, passes: 1, amp: 0.6, closed: true, step: 3 }); }
  for (const p of hpolys) stroke(p, { color: P.pen, width: 2.4, passes: 3, amp: 1.1, closed: !!p.closed, step: 3.5 });
  const e = L.heroEye(h); if (e) { ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.5, 0, Math.PI * 2); ctx.fill();
    stroke(circlePts(e.x, e.y, e.r * 1.5, 10), { color: P.pen, width: 1.2, passes: 1, amp: 0.3, closed: true, step: 2 });
    ctx.fillStyle = P.pen; ctx.beginPath(); ctx.arc(e.x + e.r * 0.35, e.y + e.r * 0.1, e.r * 0.75, 0, Math.PI * 2); ctx.fill(); }

  // ---- hand-lettered HUD ----
  const hud = S.hud || {};
  // the score block sits top-left, unless the sun is there: then it moves just past the sun, so neither hides the other
  let hx = 92; if (S.sun && S.sun.x - S.sun.r - 30 < 330 && S.sun.y - S.sun.r - 30 < 150) hx = Math.max(hx, S.sun.x + S.sun.r + 44);
  ctx.textBaseline = 'alphabetic'; ctx.fillStyle = P.pencil; ctx.font = '700 26px Caveat'; ctx.fillText((hud.score_label || 'score').toLowerCase() + ':', hx, 44);
  const sc = String(hud.score ?? ''); ctx.font = '700 70px Caveat'; const sw = ctx.measureText(sc).width;
  ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.strokeStyle = P.hi; ctx.lineCap = 'butt'; ctx.lineWidth = 30;
  ctx.beginPath(); ctx.moveTo(hx - 8, 92); ctx.lineTo(hx + 4 + sw + 10, 86); ctx.stroke(); ctx.restore();
  ctx.fillStyle = P.pen; ctx.fillText(sc, hx + 2, 100);
  if (hud.lives != null) { const n = Math.max(3, hud.lives);
    for (let i = 0; i < n; i++) { const cx = hx + 12 + i * 30, cy = 128;
      const heart = Array.from({ length: 25 }, (_, j) => { const a = j / 24 * Math.PI * 2; return [cx + 0.62 * 16 * Math.sin(a) ** 3 * 0.75, cy - 0.62 * (13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)) * 0.75]; });
      if (i < hud.lives) { const hpth = new Path2D(); heart.forEach(([a, b], j) => hpth[j ? 'lineTo' : 'moveTo'](a, b)); hpth.closePath(); scribble(hpth, bbox([heart]), { color: P.red, width: 3, gap: 2.5, alpha: 0.9 }); }
      stroke(heart, { color: i < hud.lives ? '#9e1e16' : P.pencil, width: 1.6, passes: 2, amp: 0.6, closed: true, step: 3 }); } }
  // right: best, underlined; pause as a doodled circle with two bars
  let rx = W - 40;
  if (hud.pause) { const cx = W - 62, cy = 54, r = 22; ctx.save(); ctx.fillStyle = P.paper; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.fill(); ctx.restore();
    stroke(circlePts(cx, cy, r, 22), { color: P.pen, width: 2.2, passes: 2, amp: 1, closed: true });
    stroke([[cx - 6, cy - 9], [cx - 6, cy + 9]], { color: P.pen, width: 3.4, passes: 2, amp: 0.6 }); stroke([[cx + 6, cy - 9], [cx + 6, cy + 9]], { color: P.pen, width: 3.4, passes: 2, amp: 0.6 });
    rx = cx - r - 20; }
  if (hud.best) { ctx.font = '700 32px Caveat'; ctx.fillStyle = P.pencil; ctx.textAlign = 'right'; const s = String(hud.best).toLowerCase(); ctx.fillText(s, rx, 62);
    const bw = ctx.measureText(s).width; ctx.textAlign = 'left'; stroke([[rx - bw, 70], [rx - bw * 0.4, 72], [rx + 2, 68]], { color: P.red, width: 2, passes: 2, amp: 1 }); }
  if (S.title) { ctx.font = '400 26px Caveat'; ctx.fillStyle = 'rgba(59,59,67,.75)'; ctx.textAlign = 'center'; ctx.fillText(S.title, W / 2, 40); ctx.textAlign = 'left'; }
  L.grain(ctx, W, H, 0.03, 12);
}

export const appCss = `
.app{font-family:'Patrick Hand',cursive;background-color:#fbf9f1;color:#20294f;display:flex;flex-direction:column;padding:52px 20px 0 58px;box-sizing:border-box;position:relative;
  background-image:linear-gradient(90deg,transparent 43px,#e59a9a 43px,#e59a9a 44.5px,transparent 44.5px,transparent 47px,#e59a9a 47px,#e59a9a 48px,transparent 48px),
  repeating-linear-gradient(180deg,transparent 0 31px,#bcd0e8 31px 32px);background-position:0 0,0 12px}
.app>*{position:relative;z-index:1}
.sk{position:absolute;inset:0;pointer-events:none;z-index:2;overflow:visible}
.top{display:flex;justify-content:space-between;align-items:baseline;height:52px}
.brand{font:700 40px/1 Caveat;color:#1d2a5e}
.place{font-size:17px;color:#3b3b43}
.hero{position:relative;margin:14px 0 0;padding:6px 10px 14px 8px}
.label{font:700 25px/32px Caveat;color:#3b3b43}
.value{font:700 112px/.9 Caveat;color:#1d2a5e;display:inline-block;padding:0 10px;margin-left:-8px;white-space:nowrap;
  background:linear-gradient(176deg,transparent 30%,rgba(255,226,60,.6) 31%,rgba(255,226,60,.6) 82%,transparent 83%)}
.sub{font-size:19px;line-height:26px;margin-top:4px;color:#20294f}
.status{display:inline-block;margin-top:10px;font:700 22px/1 Caveat;color:#2c6a2b;padding:5px 12px 6px;
  border:2px solid #2c6a2b;border-radius:255px 15px 225px 15px/15px 225px 15px 255px;transform:rotate(-2deg)}
.rows-title{font:700 28px/32px Caveat;margin:20px 0 0;color:#1d2a5e}
.rows{list-style:none;margin:6px 0 0;padding:0}
.rows li{display:grid;grid-template-columns:30px 62px 1fr auto;align-items:center;min-height:60px;font-size:19px}
.rows li::before{content:'';width:17px;height:17px;border:2px solid #3b3b43;border-radius:3px 6px 2px 5px;transform:rotate(-3deg)}
.rows .t{font:700 26px Caveat;color:#1d2a5e}
.rows .s{font-size:17px;padding:0 2px}
.rows li[data-state=ok] .s{color:#2c6a2b}
.rows li[data-state=late] .s{color:#b42a20;text-decoration:underline wavy #e0483a;text-underline-offset:4px}
.rows li[data-state=few] .s{color:#7a4c00;background:linear-gradient(transparent 45%,rgba(255,226,60,.6) 45% 90%,transparent 90%)}
.cta{margin:auto 4px 24px 0;height:60px;border:2.5px solid #1d2a5e;border-radius:255px 18px 225px 18px/18px 225px 18px 255px;background:#ffd84a;color:#1d2a5e;
  font:700 31px Caveat;transform:rotate(-1deg);box-shadow:4px 5px 0 -1px #1d2a5e}
.tabs{display:grid;grid-template-columns:repeat(4,1fr);margin:0 -20px 0 -58px;padding:6px 8px 30px;background:#fbf9f1;border-top:2px solid #3b3b43}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-height:50px;font-size:17px;color:#4a4a55;position:relative}
.tabs a.on{color:#1d2a5e;font-weight:400}
.tabs a.on::after{content:'';position:absolute;inset:-1px 4px -6px;border:2px solid #e0483a;border-radius:50% 45% 55% 40%/55% 45% 50% 45%;transform:rotate(-4deg)}
.ic{width:25px;height:25px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
`;

// pencil marks over the markup: a wobbly box round the lead, an underline under the name, ticks in the done boxes
export function appDecor(root, A, L) {
  const v = root.querySelector('.value'), max = v.parentElement.clientWidth; let fs = 112;
  while (v.scrollWidth > max && fs > 40) { fs -= 4; v.style.fontSize = fs + 'px'; }
  const R = root.getBoundingClientRect(), box = (el) => { const b = el.getBoundingClientRect(); return [b.left - R.left, b.top - R.top, b.width, b.height]; };
  let s = 40; const n = (k) => L.noise2(k);
  const wob = (pts, amp = 1.6, passes = 2, color = '#1d2a5e', w = 1.8) => { let out = '';
    for (let p = 0; p < passes; p++) { const f = n(s++ * 3 + p);
      const q = pts.map(([x, y], i) => [x + (f(i * 0.5, p) - 0.5) * 2 * amp, y + (f(i * 0.5 + 9, p + 3) - 0.5) * 2 * amp]);
      out += `<path d="M${q.map((a) => a.map((v) => v.toFixed(1)).join(' ')).join(' L')}" stroke="${color}" stroke-width="${(w * (p ? 0.7 : 1)).toFixed(2)}" fill="none" stroke-linecap="round" stroke-linejoin="round" opacity="${p ? 0.65 : 0.9}"/>`; }
    return out; };
  const seg = (a, b, k = 10) => Array.from({ length: k + 1 }, (_, i) => [a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k]);
  let svg = '';
  const [hx, hy, hw, hh] = box(root.querySelector('.hero'));
  svg += wob([...seg([hx - 4, hy + 2], [hx + hw + 2, hy - 2], 14), ...seg([hx + hw + 2, hy - 2], [hx + hw - 2, hy + hh + 2], 10), ...seg([hx + hw - 2, hy + hh + 2], [hx - 2, hy + hh - 1], 14), ...seg([hx - 2, hy + hh - 1], [hx - 4, hy + 6], 10)], 1.8, 2, '#3b3b43', 1.6);
  const [bx, by, bw, bh] = box(root.querySelector('.brand'));
  svg += wob(seg([bx, by + bh + 4], [bx + bw + 6, by + bh + 1], 12), 1.4, 2, '#e0483a', 2.2);
  root.querySelectorAll('.rows li[data-state=ok]').forEach((li) => { const [x, y, , h] = box(li); const cy = y + h / 2;
    svg += wob([[x + 2, cy - 1], [x + 7, cy + 5], [x + 18, cy - 10]], 0.6, 2, '#2c6a2b', 2.6); });
  // a doodled arrow down the right-hand side towards the main action
  const [cx, cy, cw] = box(root.querySelector('.cta')), [, ry, , rh] = box(root.querySelector('.rows'));
  const top = ry + rh + 14, bot = cy - 12;
  if (bot - top > 50) { const ax = cx + cw - 40, p0 = [ax - 84, top], p1 = [ax + 6, top + (bot - top) * 0.15], p2 = [ax, bot];
    const curve = Array.from({ length: 18 }, (_, i) => { const t = i / 17, u = 1 - t; return [u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0], u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]]; });
    svg += wob(curve, 1, 2, '#3b3b43', 2.2); svg += wob([[ax - 11, bot - 13], [ax, bot + 1], [ax + 10, bot - 14]], 0.7, 2, '#3b3b43', 2.2); }
  const el = document.createElement('div'); el.className = 'sk';
  el.innerHTML = `<svg width="${R.width}" height="${R.height}" viewBox="0 0 ${R.width} ${R.height}" aria-hidden="true">${svg}</svg>`; root.appendChild(el);
}
