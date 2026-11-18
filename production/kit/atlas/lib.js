// Shared helpers for atlas look painters. A look module (looks/<id>.js) exports:
//   meta = { id, pixel?: true }                 pixel: the stage gives a low-resolution canvas and upscales it without smoothing
//   game(ctx, S, L, W, H)                       paint the game scene S (scenes/*.json "game") on a W×H canvas
//   appCss                                      the look's stylesheet for the shared app markup (stage.html builds it from A)
//   appDecor?(root, A, L)                       optional: add decoration (SVG, textures) to the app markup
// L is this module. Nothing here fetches from the network.

export function rng(seed = 7) {   // mulberry32: the same seed always paints the same picture
  let a = seed >>> 0;
  return () => { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export function noise2(seed = 1) {   // smooth value noise in [0, 1]
  const r = rng(seed), P = new Float32Array(512); for (let i = 0; i < 512; i++) P[i] = r();
  const h = (x, y) => P[((x * 73856093) ^ (y * 19349663)) & 511];
  const s = (t) => t * t * (3 - 2 * t);
  return (x, y) => { const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
    const a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1);
    return a + (b - a) * s(xf) + (c - a) * s(yf) + (a - b - c + d) * s(xf) * s(yf); };
}

// the hero's silhouette as a Path2D in world coordinates (its 64-unit box scaled to hero.size, mirrored by facing)
export function heroPath(h, which = 'path') {
  const p = new Path2D(), k = h.size / 64, m = new DOMMatrix();
  m.translateSelf(h.x + (h.facing < 0 ? h.size : 0), h.y); m.scaleSelf(k * (h.facing < 0 ? -1 : 1), k);
  if (h[which]) p.addPath(new Path2D(h[which]), m);
  return p;
}
export function heroEye(h) { if (h.eye === null) return null; const k = h.size / 64; const [ex, ey, er] = h.eye || [40, 38, 3.5];
  return { x: h.x + (h.facing < 0 ? h.size - ex * k : ex * k), y: h.y + ey * k, r: er * k }; }

export function farPolygon(S, W, H, lift = 0) {
  const p = new Path2D(); p.moveTo(0, H); for (const [x, y] of S.far) p.lineTo(x, y - lift); p.lineTo(W, H); p.closePath(); return p;
}
export function buildings(S) { return (S.mid || []).map(([x, w, h]) => [x, S.ground_y - h, w, h]); }

export function spikes(hz, n = 9, inset = 0) {
  const p = new Path2D(), w = hz.w / n;
  for (let i = 0; i < n; i++) { p.moveTo(hz.x + i * w + inset, hz.y + hz.h); p.lineTo(hz.x + i * w + w / 2, hz.y); p.lineTo(hz.x + (i + 1) * w - inset, hz.y + hz.h); p.closePath(); }
  return p;
}

export function rr(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }

export function smooth(ctx, pts) {   // a Catmull-Rom curve through the points, as the current path
  ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    ctx.bezierCurveTo(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6, p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1]);
  }
}

export function grain(ctx, W, H, amount = 0.08, seed = 3, mono = true) {   // film/paper grain over what is drawn
  const s = ctx.getTransform().a || 1, w = Math.round(W * s), h = Math.round(H * s);
  const img = ctx.getImageData(0, 0, w, h), d = img.data, r = rng(seed);
  for (let i = 0; i < d.length; i += 4) { const n = (r() - 0.5) * 255 * amount; d[i] += n; d[i + 1] += mono ? n : (r() - 0.5) * 255 * amount; d[i + 2] += mono ? n : (r() - 0.5) * 255 * amount; }
  ctx.putImageData(img, 0, 0);
}

export function hex(c) { const v = c.replace('#', ''); return [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16)); }
export function mix(a, b, t) { const A = hex(a), B = hex(b); return '#' + A.map((v, i) => Math.round(v + (B[i] - v) * t).toString(16).padStart(2, '0')).join(''); }

export function offscreen(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return [c, c.getContext('2d')]; }

// tab icons for the app sample: 24-unit stroke icons; a look restyles them with CSS (stroke, stroke-width, fill)
export const ICONS = {
  Today: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  Routes: '<path d="M5 18c4-1 4-11 8-12s4 7 6 6"/><circle cx="5" cy="18" r="1.8"/><circle cx="19" cy="12" r="1.8"/>',
  Tickets: '<path d="M4 8h16v2.5a1.5 1.5 0 0 0 0 3V16H4v-2.5a1.5 1.5 0 0 0 0-3Z"/><path d="M14 8v8" stroke-dasharray="1.6 1.6"/>',
  Me: '<circle cx="12" cy="9" r="3.5"/><path d="M5.5 19c1.2-3.4 3.6-5 6.5-5s5.3 1.6 6.5 5"/>',
};
export function icon(name, cls = '') { return `<svg class="ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ''}</svg>`; }

// pickups: circle (default), diamond, star, or the scene's own pickup_path (an SVG path in a 24-unit box centred on 12,12)
export function pickupPath(S, p) {
  const r = p.r || 11, path = new Path2D();
  if (S.pickup_path) { const m = new DOMMatrix().translateSelf(p.x - r, p.y - r).scaleSelf(r / 12, r / 12); path.addPath(new Path2D(S.pickup_path), m); return path; }
  const shape = S.pickup_shape || 'circle';
  if (shape === 'diamond') { path.moveTo(p.x, p.y - r * 1.25); path.lineTo(p.x + r, p.y); path.lineTo(p.x, p.y + r * 1.25); path.lineTo(p.x - r, p.y); path.closePath(); }
  else if (shape === 'star') { for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, rr = i % 2 ? r * 0.48 : r * 1.15; path[i ? 'lineTo' : 'moveTo'](p.x + Math.cos(a) * rr, p.y + Math.sin(a) * rr); } path.closePath(); }
  else path.arc(p.x, p.y, r, 0, Math.PI * 2);
  return path;
}

// hazards: spikes (a row of teeth), block (a rectangle), or path (the scene's SVG path in a w×h box at x,y; box size given by hz.box, default [w,h])
export function hazardPath(hz) {
  if (hz.kind === 'spikes') return spikes(hz, Math.max(3, Math.round(hz.w / 22)));
  const p = new Path2D();
  if (hz.kind === 'path' && hz.path) { const [bw, bh] = hz.box || [hz.w, hz.h]; p.addPath(new Path2D(hz.path), new DOMMatrix().translateSelf(hz.x, hz.y).scaleSelf(hz.w / bw, hz.h / bh)); return p; }
  p.rect(hz.x, hz.y, hz.w, hz.h); return p;
}

// the trail: 'arc' (a jump arc, the default) or 'string' (a line the hero is tied to, e.g. a kite string)
export function trailKind(S) { return S.trail_kind || 'arc'; }
