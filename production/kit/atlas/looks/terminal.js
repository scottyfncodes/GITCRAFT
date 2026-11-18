// 6 · Terminal Phosphor: the scene rasterised to a 7×12 character grid. Every role (sky, sun, hills, blocks, ground,
// hazards, trail, pickups, hero) is drawn into its own coverage map, sampled 4×4 per cell; full cells get the role's fill
// glyph, edge cells get a glyph picked from which quadrants are covered (/ \ _ [ ] ' . ,), and the hero is set in
// reverse video. Green phosphor on near-black with bloom, scanlines and a bordered TUI HUD.
export const meta = { id: 'terminal' };
const CW = 7, CH = 12, SUB = 4;
const LV = ['#020603', '#1f6e37', '#36ad57', '#62f285', '#d2ffdc'];   // phosphor brightness levels 0–4
const BG = '#020603';
// quadrant pattern (tl,tr,bl,br as bits 8,4,2,1) → edge glyph
const EDGE = { 0b0011: '_', 0b1100: '"', 0b1010: '[', 0b0101: ']', 0b0111: '/', 0b1011: '\\', 0b1101: '\\', 0b1110: '/',
  0b1000: '`', 0b0100: "'", 0b0010: ',', 0b0001: '.', 0b1001: '\\', 0b0110: '/', 0b0000: '.', 0b1111: '#' };

export function game(ctx, S, L, W, H) {
  const cols = Math.ceil(W / CW), rows = Math.ceil(H / CH), N = cols * rows;
  const [rc, r] = L.offscreen(cols * SUB, rows * SUB);
  // paint one role in white and return per-cell quadrant coverage [tl,tr,bl,br] × N
  const cover = (paint) => {
    r.setTransform(1, 0, 0, 1, 0, 0); r.clearRect(0, 0, rc.width, rc.height);
    r.setTransform(SUB / CW, 0, 0, SUB / CH, 0, 0); r.fillStyle = '#fff'; r.strokeStyle = '#fff'; paint(r);
    const d = r.getImageData(0, 0, rc.width, rc.height).data, q = new Float32Array(N * 4), h = SUB / 2;
    for (let cy = 0; cy < rows; cy++) for (let cx = 0; cx < cols; cx++) {
      const o = (cy * cols + cx) * 4;
      for (let sy = 0; sy < SUB; sy++) for (let sx = 0; sx < SUB; sx++) {
        const a = d[(((cy * SUB + sy) * rc.width) + cx * SUB + sx) * 4 + 3] / 255;
        q[o + (sy < h ? 0 : 2) + (sx < h ? 0 : 1)] += a / (h * h);
      }
    }
    return q;
  };
  const cov = (q, i) => (q[i * 4] + q[i * 4 + 1] + q[i * 4 + 2] + q[i * 4 + 3]) / 4;
  const pat = (q, i, t = 0.5) => (q[i * 4] > t) << 3 | (q[i * 4 + 1] > t) << 2 | (q[i * 4 + 2] > t) << 1 | (q[i * 4 + 3] > t);
  const ch = new Array(N).fill(' '), lv = new Uint8Array(N), inv = new Uint8Array(N);
  const set = (i, c, l, v = 0) => { ch[i] = c; lv[i] = l; inv[i] = v; };
  const n2 = L.noise2(11), R = L.rng(5);
  const mood = S.mood || 'day';

  // sky: stars for dusk and night, faint haze dashes for dawn and day
  const starP = mood === 'night' ? 0.05 : mood === 'dusk' ? 0.022 : 0.006;
  for (let i = 0; i < N; i++) { const x = i % cols, y = (i / cols) | 0; const v = R();
    if (y < rows * 0.55 && v < starP) set(i, v < starP * 0.25 ? '+' : v < starP * 0.6 ? '.' : '`', v < starP * 0.15 ? 2 : 1);
    else if ((mood === 'day' || mood === 'dawn') && y < rows * 0.42 && n2(x * 0.08, y * 0.6) > 0.86 && x % 2) set(i, '-', 1); }
  // sun / moon: a dotted halo, a dim disc, a bright ASCII rim
  if (S.sun) { const { x, y, r: sr } = S.sun;
    const halo = cover((g) => { g.beginPath(); g.arc(x, y, sr + 22, 0, 7); g.fill(); });
    const disc = cover((g) => { g.beginPath(); g.arc(x, y, sr, 0, 7); g.fill(); });
    for (let i = 0; i < N; i++) { const c = cov(disc, i);
      if (c > 0.85) set(i, ((i * 7) % 3) ? ':' : '.', 2); else if (c > 0.08) set(i, EDGE[pat(disc, i, 0.4)] || 'o', 3);
      else if (cov(halo, i) > 0.3 && ((i + ((i / cols) | 0)) % 2)) set(i, '.', 1); } }
  // far hills: dotted fill, a brighter ridge drawn with slope glyphs
  if (S.far) { const q = cover((g) => g.fill(L.farPolygon(S, W, H)));
    for (let i = 0; i < N; i++) { const c = cov(q, i); const x = i % cols, y = (i / cols) | 0;
      if (c > 0.85) { if ((x + (y % 2)) % 2 === 0) set(i, n2(x * 0.25, y * 0.25) > 0.68 ? ':' : '.', 1); else set(i, ' ', 0); }
      else if (c > 0.12) set(i, EDGE[pat(q, i, 0.4)] || '.', 2); } }
  // mid blocks: hollow outlines (| and _) that knock out the hills behind, a grid of lit and dark windows
  const B = L.buildings(S);
  if (B.length) { const q = cover((g) => { for (const [x, y, w, h] of B) g.fillRect(x, y, w, h); });
    for (let i = 0; i < N; i++) { const c = cov(q, i); if (c < 0.3) continue; const x = i % cols, y = (i / cols) | 0;
      const up = y > 0 ? cov(q, i - cols) : 0, lf = x > 0 ? cov(q, i - 1) : 0, rt = x < cols - 1 ? cov(q, i + 1) : 0;
      if (up < 0.3) set(i, '_', 2); else if (lf < 0.3 || rt < 0.3) set(i, '|', 2);
      else if (y % 2 === 0 && x % 2 === 1) { const v = n2(x * 0.7, y * 0.7); set(i, v > 0.62 ? '#' : v > 0.4 ? '=' : '.', v > 0.62 ? 3 : 1); }
      else set(i, ' ', 0); } }
  // platforms: a bright = surface, a dim # body
  if ((S.platforms || []).length) { const q = cover((g) => { for (const [x, y, w, h] of S.platforms) g.fillRect(x, y, w, h); });
    for (let i = 0; i < N; i++) { const c = cov(q, i); if (c < 0.35) continue; const y = (i / cols) | 0, x = i % cols;
      const up = y > 0 ? cov(q, i - cols) : 0;
      if (up < 0.35) set(i, '=', 3); else if (y > 0 && cov(q, i - cols) >= 0.35 && (y < 2 || cov(q, i - 2 * cols) < 0.35)) set(i, '#', 2);
      else set(i, (y % 2 === 0 && x % 2 === 0) ? '#' : (y % 2 ? ' ' : '.'), 1); } }
  // hazards: spikes as ^, path hazards (birds, saws) in edge glyphs, blocks as a column of !
  for (const hz of S.hazards || []) { const q = cover((g) => g.fill(L.hazardPath(hz)));
    const ty = Math.max(0, Math.floor(hz.y / CH)), x0 = Math.floor(hz.x / CW), x1 = Math.ceil((hz.x + hz.w) / CW);
    if (hz.kind === 'spikes') { for (let y = ty; y < Math.min(rows - 1, Math.ceil((hz.y + hz.h) / CH)); y++) for (let x = Math.max(0, x0); x < Math.min(cols, x1); x++)
      set(y * cols + x, y === ty ? ((x - x0) % 2 ? ' ' : '^') : ((x - x0) % 2 ? '\\' : '/'), 4); continue; }
    for (let i = 0; i < N; i++) { const c = cov(q, i); if (c < 0.18) continue;
      else if (hz.kind === 'block') set(i, c > 0.5 ? '!' : '|', 4);
      else set(i, c > 0.7 ? 'W' : (EDGE[pat(q, i, 0.3)] || 'v'), 4); } }
  // a polyline walked in small steps; f(cellIndex, step, dx, dy)
  const walk = (pts, f, step = 3) => { for (let k = 0; k < pts.length - 1; k++) { const [ax, ay] = pts[k], [bx, by] = pts[k + 1], d = Math.hypot(bx - ax, by - ay);
    for (let s = 0; s < d; s += step) { const x = ax + (bx - ax) * s / d, y = ay + (by - ay) * s / d; const cx = Math.floor(x / CW), cy = Math.floor(y / CH);
      if (cx >= 0 && cx < cols && cy >= 0 && cy < rows) f(cy * cols + cx, Math.round((k * 1000 + s) / step), (bx - ax) / d, (by - ay) / d); } } };
  const slope = (dx, dy) => { const a = Math.atan2(dy, dx * CH / CW) * 180 / Math.PI; const t = ((a % 180) + 180) % 180;
    return t < 22 || t > 158 ? '-' : t < 68 ? '\\' : t < 112 ? '|' : '/'; };
  // wind lines and the trail
  for (const ln of S.lines || []) walk(ln, (i, s, dx, dy) => set(i, slope(dx, dy) === '-' ? '-' : slope(dx, dy), 3));
  const t = S.trail || [];
  if (t.length > 1) { if (L.trailKind(S) === 'string') walk(t, (i, s, dx, dy) => set(i, slope(dx, dy), 3), 2);
    else { let last = -1, n = 0; walk(t, (i) => { if (i !== last) { last = i; n++; set(i, n % 2 ? '.' : ' ', n % 2 ? 3 : 0); } }, 2); } }
  // pickups: $ for coins, * for stars and diamonds, ~ for the scene's own shape
  const pc = S.pickup_path ? '~' : ({ star: '*', diamond: '*' })[S.pickup_shape] || '$';
  for (const p of S.pickups || []) { const cx = Math.floor(p.x / CW), cy = Math.floor(p.y / CH); if (cy < 0 || cy >= rows) continue;
    [['(', 3], [pc, 4], [')', 3]].forEach(([c, l], k) => { const x = cx - 1 + k; if (x >= 0 && x < cols) set(cy * cols + x, c, l); }); }
  // hero: reverse video for the body, bright edge glyphs on black around it, the accent knocked back to normal video
  const h = S.hero, hq = cover((g) => g.fill(L.heroPath(h))), aq = h.accent ? cover((g) => g.fill(L.heroPath(h, 'accent'))) : null;
  for (let i = 0; i < N; i++) { const c = cov(hq, i); if (c < 0.14) continue;
    if (aq && cov(aq, i) > 0.3) set(i, '=', 4, 2);
    else if (c > 0.5) set(i, '#', 4, 1); else set(i, EDGE[pat(hq, i, 0.35)] || '.', 4); }
  const e = L.heroEye(h); if (e) { const cx = Math.floor(e.x / CW), cy = Math.floor(e.y / CH); if (cx >= 0 && cy >= 0 && cx < cols && cy < rows) set(cy * cols + cx, 'o', 4); }

  // ---- HUD rows: the top four rows and the last row belong to the interface ----
  const hudRows = 4;
  for (let i = 0; i < N; i++) { const y = (i / cols) | 0; if (y < hudRows || y >= rows - 1) set(i, ' ', 0); }

  // ---- paint glyphs onto a layer, then composite with bloom ----
  const [gc, g] = L.offscreen(W * 2, H * 2); g.scale(2, 2);
  g.font = '15px VT323'; const fs = 15 * CW / g.measureText('M').width;
  g.font = `${fs}px VT323`; g.textAlign = 'center'; g.textBaseline = 'middle';
  for (let i = 0; i < N; i++) { if (ch[i] === ' ' && !inv[i]) continue; const x = (i % cols) * CW, y = ((i / cols) | 0) * CH;
    if (inv[i] === 1) { g.fillStyle = '#2a8a48'; g.fillRect(x, y, CW, CH); }   // hero body: a lit cell under a bright glyph
    else if (inv[i] === 2) { g.fillStyle = '#0a2412'; g.fillRect(x, y, CW, CH); }
    g.fillStyle = LV[lv[i]];
    if (ch[i] !== ' ') g.fillText(ch[i], x + CW / 2, y + CH / 2 + 1); }
  hud(g, S, L, W, H, rows, cols);

  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  ctx.save(); ctx.globalCompositeOperation = 'lighter';
  ctx.filter = 'blur(9px)'; ctx.globalAlpha = 0.55; ctx.drawImage(gc, 0, 0, W, H);
  ctx.filter = 'blur(2.5px)'; ctx.globalAlpha = 0.7; ctx.drawImage(gc, 0, 0, W, H);
  ctx.filter = 'none'; ctx.globalAlpha = 1; ctx.drawImage(gc, 0, 0, W, H);
  ctx.restore();
  // scanlines, a soft vignette and the curved glass edge
  ctx.fillStyle = 'rgba(0,0,0,.30)'; for (let y = 0; y < H; y += 3) ctx.fillRect(0, y + 2, W, 1);
  const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, W * 0.66);
  vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.55)'); ctx.fillStyle = vg; ctx.fillRect(0, 0, W, H);
}

function hud(g, S, L, W, H, rows, cols) {
  const hd = S.hud || {}, x0 = CW + 0.5, y0 = 5.5, x1 = W - CW - 0.5, y1 = 4 * CH - 3.5;
  const glowText = (s, x, y, font, l, align = 'left') => { g.font = font; g.textAlign = align; g.textBaseline = 'alphabetic'; g.fillStyle = LV[l]; g.fillText(s, x, y); };
  // double-ruled box
  g.strokeStyle = LV[2]; g.lineWidth = 1; g.strokeRect(x0, y0, x1 - x0, y1 - y0); g.strokeRect(x0 + 3, y0 + 3, x1 - x0 - 6, y1 - y0 - 6);
  // title tab on the top border
  if (S.title) { const s = ` ${S.title.toUpperCase()} `; g.font = '18px VT323'; const w = g.measureText(s).width;
    g.fillStyle = BG; g.fillRect(W / 2 - w / 2 - 4, y0 - 4, w + 8, 9); glowText(s, W / 2, y0 + 5, '18px VT323', 3, 'center'); }
  const my = y1 - 9;
  glowText((hd.score_label || 'SCORE') + ':', 22, my, '20px VT323', 2);
  g.font = '20px VT323'; const lw = g.measureText((hd.score_label || 'SCORE') + ':').width;
  glowText(String(hd.score ?? ''), 30 + lw, my + 4, '44px VT323', 4);
  g.font = '44px VT323'; let x = 30 + lw + g.measureText(String(hd.score ?? '')).width + 34;
  if (hd.lives != null) { glowText('LIVES', x, my, '20px VT323', 2); x += 48;
    for (let i = 0; i < Math.max(3, hd.lives); i++) { if (i < hd.lives) { g.fillStyle = LV[4]; g.fillRect(x + i * 16, my - 14, 11, 15); }
      else { g.strokeStyle = LV[2]; g.strokeRect(x + i * 16 + 0.5, my - 13.5, 10, 14); } } }
  let rx = x1 - 14;
  if (hd.pause) { const bw = 46, bh = 26, bx = rx - bw, by = y0 + (y1 - y0 - bh) / 2; g.fillStyle = LV[3]; g.fillRect(bx, by, bw, bh);
    g.fillStyle = BG; g.fillRect(bx + 17, by + 6, 4, 14); g.fillRect(bx + 25, by + 6, 4, 14); rx = bx - 16; }
  if (hd.best) glowText(String(hd.best), rx, my, '24px VT323', 3, 'right');
  // the prompt on the last row
  const py = H - 3, slug = (S.title || 'game').toLowerCase().replace(/[^a-z0-9]+/g, '-');
  const cmd = `$ ./${slug} --mood=${S.mood || 'day'}`;
  glowText(cmd, CW + 2, py, '19px VT323', 3); g.font = '19px VT323'; const cw = g.measureText(cmd).width;
  g.fillStyle = LV[4]; g.fillRect(CW + 6 + cw, py - 12, 8, 13);
}

export const appCss = `
.app{font-family:VT323,monospace;background:#030a05;color:#62f285;display:flex;flex-direction:column;padding:50px 16px 0;box-sizing:border-box;
  text-shadow:0 0 6px rgba(98,242,133,.55),0 0 1px rgba(98,242,133,.9);font-size:20px;line-height:1.15;position:relative}
.app::after{content:'';position:absolute;inset:0;pointer-events:none;z-index:5;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.28) 0 1px,transparent 1px 3px),radial-gradient(120% 90% at 50% 45%,transparent 60%,rgba(0,0,0,.55));}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:20px}
.brand{text-transform:lowercase;color:#d2ffdc}
.brand::before{content:'guest@';color:#62f285}
.brand::after{content:':~$ status';color:#62f285}
.place{color:#9dd9ab;font-size:17px}
.place::before{content:'['}.place::after{content:']'}
.hero{position:relative;margin-top:24px;border:2px solid #36ad57;outline:1px solid #36ad57;outline-offset:3px;padding:26px 16px 22px;margin-left:4px;margin-right:4px}
.label{position:absolute;top:-12px;left:12px;background:#030a05;padding:0 6px;font-size:20px;color:#d2ffdc;text-transform:uppercase}
.label::before{content:'[ '}.label::after{content:' ]'}
.value{font-size:140px;line-height:.82;white-space:nowrap;color:#d2ffdc;letter-spacing:-.02em;margin:6px 0 4px -4px;
  text-shadow:0 0 14px rgba(98,242,133,.7),0 0 2px #fff}
.sub{font-size:20px;color:#9dd9ab}
.sub::before{content:'> ';color:#62f285}
.status{display:inline-block;margin-top:10px;background:#62f285;color:#03140a;text-shadow:none;padding:1px 8px;font-size:20px;text-transform:uppercase;
  box-shadow:0 0 12px rgba(98,242,133,.6)}
.rows-title{font-weight:400;font-size:20px;margin:30px 0 8px;color:#d2ffdc}
.rows-title::before{content:'$ ls --later  # ';color:#62f285}
.rows{list-style:none;margin:0;padding:0;border:1px solid #36ad57}
.rows li{display:grid;grid-template-columns:64px 1fr auto;align-items:center;min-height:54px;padding:0 10px;font-size:20px;border-top:1px dashed #1f6e37}
.rows li:first-child{border-top:0}
.rows .t{color:#d2ffdc}
.rows .d{color:#9dd9ab;border-left:1px solid #1f6e37;padding-left:10px}
.rows .s{text-transform:uppercase;font-size:18px}
.rows .s::before{content:'['}.rows .s::after{content:']'}
.rows li[data-state=late] .s{background:#62f285;color:#03140a;text-shadow:none;padding:0 4px}
.rows li[data-state=late] .s::before,.rows li[data-state=late] .s::after{content:''}
.rows li[data-state=few] .s{color:#d2ffdc}
.cta{margin:26px 4px 0;height:60px;border:0;border-radius:0;background:#62f285;color:#03140a;font:400 26px VT323;letter-spacing:.06em;text-transform:uppercase;
  box-shadow:0 0 18px rgba(98,242,133,.55),inset 0 0 0 2px #030a05,inset 0 0 0 3px #62f285}
.cta::before{content:'[ '}.cta::after{content:' ]'}
.prompt{margin:auto 0 14px;padding-top:16px;font-size:20px;color:#62f285}
.prompt b{display:inline-block;width:10px;height:18px;background:#d2ffdc;vertical-align:-3px;font-weight:400;box-shadow:0 0 8px #62f285}
.tabs{display:grid;grid-template-columns:repeat(4,1fr);margin-left:-16px;margin-right:-16px;padding:0 6px 30px;background:#0c2814;border-top:1px solid #36ad57}
.tabs a{display:flex;align-items:center;justify-content:center;min-height:48px;font-size:20px;color:#9dd9ab;gap:0}
.tabs a .ic{display:none}
.tabs a span::before{content:attr(data-n) ':';color:#36ad57}
.tabs a.on{color:#03140a;text-shadow:none}
.tabs a.on span{background:#62f285;padding:0 6px}
.tabs a.on span::before{color:#03140a}
.tabs a.on span::after{content:'*'}
`;

export function appDecor(root) {
  const v = root.querySelector('.value'); let fs = 140;   // the big figure fits its box whatever the value
  while (v.scrollWidth > v.clientWidth + 1 && fs > 40) { fs -= 4; v.style.fontSize = fs + 'px'; }
  const b = root.querySelector('.brand'); b.textContent = b.textContent.toLowerCase().replace(/\s+/g, '-');
  root.querySelectorAll('.tabs a span').forEach((s, i) => { s.dataset.n = i; s.textContent = s.textContent.toLowerCase(); });
  const p = document.createElement('div'); p.className = 'prompt'; p.innerHTML = 'guest@harbour:~$ <b></b>';
  p.firstChild.textContent = `guest@${b.textContent || 'app'}:~$ `;
  root.querySelector('.cta').after(p);
}
