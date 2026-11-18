// 12 · Editorial Serif: a magazine spread. The scene is an editorial plate (ink, bone, ochre, deep green and rust, flat
// shapes with engraved hairline detail) set in generous margins beside a Fraunces headline score, ruled stat lines in
// Newsreader and an italic figure caption. The plate is the whole world, scaled into its frame, so any scene fits.
export const meta = { id: 'editorial-serif' };
const INK = '#1d2326', BONE = '#f2ecdf', PAPER = '#efe8da', OCHRE = '#c8913a', GREEN = '#2f4a3a', SAGE = '#8d9a80', RUST = '#a5482c', MUTE = '#6a6457';
const SKY = { dawn: ['#e9d8c8', '#efe2cf'], day: ['#dfe2d6', '#ebe8da'], dusk: ['#d8c39d', '#eadab7'], night: ['#2c3741', '#3c4750'] };

function plate(ctx, S, L, W, H) {
  const mood = S.mood || 'day', night = mood === 'night', [s0, s1] = SKY[mood] || SKY.day;
  const g = ctx.createLinearGradient(0, 0, 0, S.ground_y || H); g.addColorStop(0, s0); g.addColorStop(1, s1);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // a soft wash: low-alpha noise clouds, like ink on damp paper
  const n = L.noise2(21), n2 = L.noise2(5), [wc, w] = L.offscreen(120, 68), img = w.createImageData(120, 68);
  for (let y = 0; y < 68; y++) for (let x = 0; x < 120; x++) { const v = n(x / 17, y / 9) * 0.7 + n2(x / 6, y / 4) * 0.3, a = Math.max(0, v - 0.5) * 2 * (1 - y / 68);
    const o = (y * 120 + x) * 4; img.data[o] = 255; img.data[o + 1] = 250; img.data[o + 2] = 238; img.data[o + 3] = a * (night ? 30 : 150); }
  w.putImageData(img, 0, 0); ctx.imageSmoothingEnabled = true; ctx.drawImage(wc, 0, 0, W, H);
  if (night) { const r = L.rng(4); ctx.fillStyle = BONE; for (let i = 0; i < 70; i++) { ctx.globalAlpha = 0.3 + r() * 0.6; ctx.fillRect(r() * W, r() * H * 0.55, 1.4, 1.4); } ctx.globalAlpha = 1; }
  // sun / moon: a flat ochre disc with an engraved lower half
  if (S.sun) { const { x, y, r } = S.sun; ctx.fillStyle = night ? '#e8dfc8' : OCHRE; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    ctx.save(); ctx.clip(); ctx.strokeStyle = night ? 'rgba(29,35,38,.25)' : 'rgba(165,72,44,.55)'; ctx.lineWidth = 0.9;
    for (let k = 0; k < 9; k++) { const yy = y + r * 0.1 + k * r * 0.11; ctx.beginPath(); ctx.moveTo(x - r, yy); ctx.lineTo(x + r, yy); ctx.stroke(); }
    ctx.restore(); }
  // far hills: sage plane engraved with contour lines that follow the ridge
  if (S.far) { const fp = L.farPolygon(S, W, H); ctx.fillStyle = night ? '#46524f' : SAGE; ctx.fill(fp);
    ctx.save(); ctx.clip(fp); ctx.strokeStyle = night ? 'rgba(242,236,223,.12)' : 'rgba(47,74,58,.38)'; ctx.lineWidth = 0.8;
    for (let k = 1; k < 26; k++) { ctx.beginPath(); S.far.forEach(([x, y], i) => ctx[i ? 'lineTo' : 'moveTo'](x, y + k * 5.5 + Math.sin(x / 40 + k) * 1.2)); ctx.stroke(); }
    ctx.restore(); ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.beginPath(); S.far.forEach(([x, y], i) => ctx[i ? 'lineTo' : 'moveTo'](x, y)); ctx.stroke(); }
  // mid blocks: deep green, an engraved shaded side, hairline outlines, a few warm windows
  const R = L.rng(9);
  for (const [x, y, w, h] of L.buildings(S)) {
    ctx.fillStyle = night ? '#25352d' : GREEN; ctx.fillRect(x, y, w, h);
    ctx.save(); ctx.beginPath(); ctx.rect(x + w * 0.64, y, w * 0.36, h); ctx.clip(); ctx.strokeStyle = 'rgba(29,35,38,.6)'; ctx.lineWidth = 0.8;
    for (let k = -h; k < w + h; k += 3.2) { ctx.beginPath(); ctx.moveTo(x + k, y); ctx.lineTo(x + k - h, y + h); ctx.stroke(); } ctx.restore();
    ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
    for (let wy = y + 14; wy < y + h - 16; wy += 20) for (let wx = x + 8; wx < x + w * 0.58 - 6; wx += 13) {
      const lit = R() < 0.32; ctx.fillStyle = lit ? '#e2b765' : 'rgba(29,35,38,.35)'; ctx.fillRect(wx, wy, 5, 8); }
  }
  // platforms: ink slabs with a bone hairline edge and faint strata
  for (const [x, y, w, h] of S.platforms || []) {
    ctx.fillStyle = INK; ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = 'rgba(242,236,223,.10)'; ctx.lineWidth = 0.8; for (let yy = y + 9; yy < y + h; yy += 7) { ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke(); }
    ctx.fillStyle = 'rgba(242,236,223,.55)'; ctx.fillRect(x, y + 2, w, 1);
  }
  // hazards: rust, outlined in ink
  for (const hz of S.hazards || []) { const p = L.hazardPath(hz); ctx.fillStyle = RUST; ctx.fill(p); ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.stroke(p); }
  // wind lines: fine ink hairlines
  ctx.strokeStyle = night ? 'rgba(242,236,223,.5)' : 'rgba(29,35,38,.55)'; ctx.lineWidth = 1; ctx.lineCap = 'round';
  for (const ln of S.lines || []) { L.smooth(ctx, ln); ctx.stroke(); }
  // trail: a dotted ink arc, or a hairline string
  const t = S.trail || [];
  if (t.length > 1) { ctx.strokeStyle = night ? BONE : INK; ctx.lineWidth = 1.2;
    if (L.trailKind(S) === 'string') { ctx.lineWidth = 1.1; L.smooth(ctx, t); ctx.stroke(); }
    else { ctx.setLineDash([1, 6]); ctx.lineWidth = 2; L.smooth(ctx, t); ctx.stroke(); ctx.setLineDash([]); } }
  // pickups: ochre with an ink hairline and a bone glint
  for (const c of S.pickups || []) { const p = L.pickupPath(S, c), r = c.r || 11;
    ctx.fillStyle = OCHRE; ctx.fill(p); ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.stroke(p);
    if (!S.pickup_path) { ctx.strokeStyle = BONE; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(c.x, c.y, r * 0.6, Math.PI * 1.1, Math.PI * 1.55); ctx.stroke(); } }
  // hero: ink, with a bone hairline keeping it off dark ground, ochre accent, a bone eye
  const h = S.hero, hp = L.heroPath(h);
  ctx.save(); ctx.strokeStyle = night ? OCHRE : BONE; ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.stroke(hp); ctx.restore();
  ctx.fillStyle = night ? BONE : INK; ctx.fill(hp);
  if (h.accent) { ctx.fillStyle = OCHRE; ctx.fill(L.heroPath(h, 'accent')); }
  const e = L.heroEye(h); if (e) { ctx.fillStyle = night ? INK : BONE; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.2, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = night ? BONE : INK; ctx.beginPath(); ctx.arc(e.x + e.r * 0.25, e.y, e.r * 0.55, 0, Math.PI * 2); ctx.fill(); }
}

const PHRASE = { dawn: 'at dawn', day: 'by day', dusk: 'at dusk', night: 'by night' };

export function game(ctx, S, L, W, H) {
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
  const hud = S.hud || {}, mood = S.mood || 'day';
  // the plate: the whole world, scaled into a frame on the right-hand page
  const px = 252, py = 62, pw = W - px - 36, k = pw / W, ph = H * k;
  ctx.save(); ctx.translate(px, py); ctx.scale(k, k); ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip(); plate(ctx, S, L, W, H); ctx.restore();
  ctx.strokeStyle = INK; ctx.lineWidth = 0.8; ctx.strokeRect(px - 0.5, py - 0.5, pw + 1, ph + 1);
  ctx.lineWidth = 0.5; ctx.strokeRect(px - 5.5, py - 5.5, pw + 11, ph + 11);
  // running head: a hairline, the title in spaced capitals, the pause control at the far right
  ctx.fillStyle = INK; ctx.fillRect(36, 34, W - 72, 0.8);
  ctx.font = '600 11px Newsreader'; ctx.letterSpacing = '2.4px'; ctx.textBaseline = 'alphabetic';
  ctx.fillText((S.title || 'Game').toUpperCase(), 36, 24);
  ctx.fillStyle = MUTE; ctx.textAlign = 'center'; ctx.fillText(mood.toUpperCase(), W / 2, 24); ctx.textAlign = 'left'; ctx.letterSpacing = '0px';
  if (hud.pause) { const cx = W - 52, cy = 20; ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, 12, 0, Math.PI * 2); ctx.stroke();
    ctx.fillStyle = INK; ctx.fillRect(cx - 4, cy - 5, 2.4, 10); ctx.fillRect(cx + 1.6, cy - 5, 2.4, 10);
    ctx.font = 'italic 400 13px Newsreader'; ctx.textAlign = 'right'; ctx.fillText('pause', cx - 18, cy + 4); ctx.textAlign = 'left'; }
  // left column: kicker, a headline numeral, ruled stat lines
  const cx0 = 36, cw = px - 36 - 32;
  ctx.fillStyle = RUST; ctx.font = '600 12px Newsreader'; ctx.letterSpacing = '2.2px'; ctx.fillText((hud.score_label || 'Score').toUpperCase(), cx0, 82); ctx.letterSpacing = '0px';
  let fs = 112; const sc = String(hud.score ?? ''); ctx.font = `900 ${fs}px Fraunces`;
  while (ctx.measureText(sc).width > cw && fs > 40) { fs -= 4; ctx.font = `900 ${fs}px Fraunces`; }
  ctx.fillStyle = INK; ctx.letterSpacing = '-2px'; ctx.fillText(sc, cx0 - 3, 92 + fs * 0.74); ctx.letterSpacing = '0px';
  let y = 92 + fs * 0.74 + 26;
  const row = (label, draw) => { ctx.fillStyle = INK; ctx.fillRect(cx0, y, cw, 0.8); y += 26;
    ctx.font = 'italic 400 16px Newsreader'; ctx.fillStyle = MUTE; ctx.fillText(label, cx0, y); draw(cx0 + cw, y); y += 14; };
  if (hud.best) { const m = String(hud.best).match(/^(.*?)\s*([\d.,:]+)$/);
    row(m ? m[1].charAt(0).toUpperCase() + m[1].slice(1).toLowerCase() : 'Best', (rx, ry) => { ctx.font = '600 22px Fraunces'; ctx.fillStyle = INK; ctx.textAlign = 'right'; ctx.fillText(m ? m[2] : hud.best, rx, ry + 1); ctx.textAlign = 'left'; }); }
  if (hud.lives != null) row('Lives', (rx, ry) => { const n = Math.max(3, hud.lives);
    for (let i = 0; i < n; i++) { const x = rx - 6 - (n - 1 - i) * 18; ctx.beginPath(); ctx.arc(x, ry - 6, 5.5, 0, Math.PI * 2);
      if (i < hud.lives) { ctx.fillStyle = RUST; ctx.fill(); } else { ctx.strokeStyle = INK; ctx.lineWidth = 1; ctx.stroke(); } } });
  ctx.fillStyle = INK; ctx.fillRect(cx0, y, cw, 0.8);
  // a short italic deck at the foot of the column
  ctx.font = 'italic 400 15px Newsreader'; ctx.fillStyle = INK;
  const deck = [`${S.title || 'The game'},`, `as seen ${PHRASE[mood] || 'by day'}.`];
  deck.forEach((s, i) => ctx.fillText(s, cx0, py + ph - 24 + i * 20));
  // caption under the plate and a folio
  ctx.font = 'italic 400 15px Newsreader'; ctx.fillStyle = INK;
  ctx.fillText(`Fig. 1 — ${S.title || 'The scene'}, ${PHRASE[mood] || 'by day'}.`, px, py + ph + 32);
  ctx.font = '600 11px Newsreader'; ctx.letterSpacing = '2px'; ctx.fillStyle = MUTE; ctx.textAlign = 'right';
  ctx.fillText('PLATE I', px + pw, py + ph + 32); ctx.textAlign = 'left'; ctx.letterSpacing = '0px';
  ctx.fillStyle = INK; ctx.fillRect(36, H - 22, W - 72, 0.8);
  L.grain(ctx, W, H, 0.035, 8);
}

export const appCss = `
.app{font-family:Newsreader,serif;background:#f3eee3;color:#1d2326;display:flex;flex-direction:column;padding:56px 24px 0;box-sizing:border-box;position:relative}
.top{display:flex;flex-direction:column;align-items:center;border-top:3px double #1d2326;border-bottom:1px solid #1d2326;padding:10px 0 9px}
.brand{font:600 32px/1 Fraunces;letter-spacing:-.01em}
.place{order:-1;font:600 14px Newsreader;letter-spacing:.14em;text-transform:uppercase;color:#5d574b;margin-bottom:7px}
.orn{display:flex;justify-content:center;margin:20px 0 6px}
.hero{display:flex;flex-direction:column;align-items:flex-start}
.label{font:600 14px Newsreader;letter-spacing:.14em;text-transform:uppercase;color:#8e3b22}
.value{font:900 124px/.9 Fraunces;letter-spacing:-.035em;margin:6px 0 0 -4px;padding-bottom:.13em;white-space:nowrap}
.sub{font-style:italic;font-size:19px;line-height:1.35;max-width:300px}
.status{margin-top:12px;font:600 15px Newsreader;color:#2f4a3a;display:flex;align-items:center;gap:10px}
.status::before{content:'';width:26px;height:1px;background:#2f4a3a}
.rows-title{font:600 22px Fraunces;margin:30px 0 0;padding-bottom:8px;border-bottom:1px solid #1d2326;display:flex;justify-content:space-between;align-items:baseline}
.rows{list-style:none;margin:0;padding:0}
.rows li{display:grid;grid-template-columns:76px 1fr auto;align-items:baseline;min-height:56px;padding-top:15px;box-sizing:border-box;border-bottom:1px solid rgba(29,35,38,.22)}
.rows .t{font:600 22px Fraunces;font-variant-numeric:lining-nums}
.rows .d{font-size:18px}
.rows .s{font-style:italic;font-size:15px;color:#2f4a3a}
.rows li[data-state=late] .s{color:#8e3b22}
.rows li[data-state=few] .s{color:#5d574b}
.cta{margin:auto 0 22px;height:56px;border:0;border-radius:1px;background:#1d2326;color:#f3eee3;font:600 15px Newsreader;letter-spacing:.18em;text-transform:uppercase}
.tabs{display:grid;grid-template-columns:repeat(4,1fr);margin:0 -24px;padding:0 12px 30px;border-top:1px solid #1d2326}
.tabs a{display:flex;flex-direction:column;align-items:center;gap:5px;min-height:48px;padding-top:11px;font-size:14px;color:#5d574b;position:relative}
.tabs a.on{color:#1d2326;font-weight:600}
.tabs a.on::before{content:'';position:absolute;top:-1px;left:30%;right:30%;height:2px;background:#8e3b22}
.ic{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.3;stroke-linecap:round;stroke-linejoin:round}
`;

export function appDecor(root) {
  const v = root.querySelector('.value'); let fs = 124;
  const max = v.parentElement.clientWidth;   // the hero is a flex column: measure against it, not the shrink-wrapped figure
  while (v.scrollWidth > max + 2 && fs > 40) { fs -= 4; v.style.fontSize = fs + 'px'; }
  // a small engraved ornament between the masthead and the lead
  const o = document.createElement('div'); o.className = 'orn'; o.setAttribute('aria-hidden', 'true');
  o.innerHTML = '<svg width="120" height="10" viewBox="0 0 120 10"><path d="M0 5h48M72 5h48" stroke="#1d2326" stroke-width=".8"/><path d="M60 0l5 5-5 5-5-5z" fill="#8e3b22"/><circle cx="51" cy="5" r="1.2" fill="#1d2326"/><circle cx="69" cy="5" r="1.2" fill="#1d2326"/></svg>';
  root.querySelector('.top').after(o);
}
