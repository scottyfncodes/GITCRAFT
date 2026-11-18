// 5 · Swiss Grid: International Typographic Style. A 12-column grid left visible as hairlines, the score as a huge
// tight-set numeral, flush-left labels, black + off-white + one signal red (the hero), line-screen greys, thin rules.
export const meta = { id: 'swiss-grid' };
const C = { paper: '#f1eee7', ink: '#111111', red: '#e2231a', far: '#d9d4c9', far2: '#c9c3b6', rule: 'rgba(17,17,17,.075)' };
const M = 32, COLS = 12, GUT = 16;

function grid(W) { const cw = (W - 2 * M - (COLS - 1) * GUT) / COLS; return { cw, x: (i) => M + i * (cw + GUT) }; }

export function game(ctx, S, L, W, H) {
  const G = grid(W);
  ctx.fillStyle = C.paper; ctx.fillRect(0, 0, W, H);
  // the mood is said in type and in one quiet tone change, never in a gradient
  const mood = S.mood || 'day';
  if (mood === 'night') { ctx.fillStyle = '#e4e0d6'; ctx.fillRect(0, 0, W, H); }
  // the grid itself: column hairlines and a baseline every 24 px, faint
  ctx.fillStyle = C.rule;
  for (let i = 0; i < COLS; i++) { ctx.fillRect(Math.round(G.x(i)), 0, 1, H); ctx.fillRect(Math.round(G.x(i) + G.cw) - 1, 0, 1, H); }
  // sun / moon: concentric rules around a small solid disc (a Müller-Brockmann ring study)
  if (S.sun) {
    const { x, y, r } = S.sun; ctx.strokeStyle = C.ink; ctx.lineWidth = 1;
    for (let k = 0; k < 7; k++) { ctx.globalAlpha = 0.85 - k * 0.1; ctx.beginPath(); ctx.arc(x, y, r * 0.55 + k * r * 0.24, 0, Math.PI * 2); ctx.stroke(); }
    // the solid core only where it cannot fight the score numeral
    ctx.font = '400 132px "Archivo Black"'; const sw = ctx.measureText(String((S.hud || {}).score ?? '')).width + 40;
    const clash = x - r * 0.42 < M + sw && y - r * 0.42 < 170;
    ctx.globalAlpha = 1; ctx.fillStyle = C.ink; if (!clash) { ctx.beginPath(); ctx.arc(x, y, r * 0.42, 0, Math.PI * 2); ctx.fill(); }
  }
  // far: one flat grey plane with a single hairline crest
  if (S.far) {
    ctx.fillStyle = C.far; ctx.fill(L.farPolygon(S, W, H));
    ctx.strokeStyle = C.ink; ctx.lineWidth = 1; ctx.beginPath(); S.far.forEach(([x, y], i) => ctx[i ? 'lineTo' : 'moveTo'](x, y)); ctx.stroke();
  }
  // mid: line-screen blocks (horizontal rules every 5 px), a crisp edge on the left side only
  for (const [x, y, w, h] of L.buildings(S)) {
    ctx.fillStyle = C.paper; ctx.fillRect(x, y, w, h);
    ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); ctx.fillStyle = C.ink;
    for (let yy = y + 1; yy < y + h; yy += 5) ctx.fillRect(x, Math.round(yy), w, 1.6);
    ctx.restore(); ctx.fillRect(x, y, w, 3);
  }
  // platforms: solid black slabs
  ctx.fillStyle = C.ink;
  for (const [x, y, w, h] of S.platforms || []) ctx.fillRect(x, y, w, h);
  // the grid runs on through the black, reversed out
  ctx.save(); ctx.beginPath(); for (const [x, y, w, h] of S.platforms || []) ctx.rect(x, y, w, h); ctx.clip();
  ctx.fillStyle = 'rgba(241,238,231,.09)';
  for (let i = 0; i < COLS; i++) { ctx.fillRect(Math.round(G.x(i)), 0, 1, H); ctx.fillRect(Math.round(G.x(i) + G.cw) - 1, 0, 1, H); }
  ctx.restore();
  // hazards: black teeth on a red base rule; path hazards and blocks solid black with a red hairline
  for (const hz of S.hazards || []) {
    const p = L.hazardPath(hz); ctx.fillStyle = C.ink; ctx.fill(p);
    if (hz.kind === 'spikes') { ctx.fillStyle = C.red; ctx.fillRect(hz.x, hz.y + hz.h - 4, hz.w, 4); }
    else { ctx.strokeStyle = C.red; ctx.lineWidth = 1.5; ctx.stroke(p); }
  }
  // lines: plain hairlines
  ctx.strokeStyle = C.ink; ctx.lineWidth = 1; ctx.lineCap = 'butt';
  for (const ln of S.lines || []) { L.smooth(ctx, ln); ctx.stroke(); }
  // trail: a measured path, hairline with ticks every 18 px (an arc) or a taut 1.5 px string
  const t = S.trail || [];
  if (t.length > 1) {
    if (L.trailKind(S) === 'string') { ctx.lineWidth = 1.5; L.smooth(ctx, t); ctx.stroke(); }
    else {
      ctx.lineWidth = 1; L.smooth(ctx, t); ctx.stroke();
      let acc = 0;
      for (let i = 0; i < t.length - 1; i++) {
        const [ax, ay] = t[i], [bx, by] = t[i + 1], d = Math.hypot(bx - ax, by - ay), nx = -(by - ay) / d, ny = (bx - ax) / d;
        for (let s = (18 - acc % 18) % 18; s < d; s += 18) { const px = ax + (bx - ax) * s / d, py = ay + (by - ay) * s / d;
          ctx.beginPath(); ctx.moveTo(px - nx * 5, py - ny * 5); ctx.lineTo(px + nx * 5, py + ny * 5); ctx.stroke(); }
        acc += d;
      }
    }
  }
  // pickups: black rings with a solid core, each indexed 01, 02 … in small type
  ctx.font = '700 10px Archivo'; ctx.textBaseline = 'alphabetic';
  (S.pickups || []).forEach((c, i) => {
    const p = L.pickupPath(S, c); const r = c.r || 11;
    if (S.pickup_path) { ctx.fillStyle = C.ink; ctx.fill(p); }
    else { ctx.fillStyle = C.paper; ctx.fill(p); ctx.strokeStyle = C.ink; ctx.lineWidth = 2; ctx.stroke(p);
      ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(c.x, c.y, r * 0.32, 0, Math.PI * 2); ctx.fill(); }
    ctx.fillText(String(i + 1).padStart(2, '0'), c.x + r + 3, c.y - r + 2);
  });
  // hero: the only red thing in the picture; a paper knock-out keeps it clear of anything behind it
  const h = S.hero, hero = L.heroPath(h);
  ctx.save(); ctx.strokeStyle = C.paper; ctx.lineWidth = 6; ctx.lineJoin = 'round'; ctx.stroke(hero); ctx.restore();
  ctx.fillStyle = C.red; ctx.fill(hero);
  if (h.accent) { ctx.fillStyle = C.ink; ctx.fill(L.heroPath(h, 'accent')); }
  const e = L.heroEye(h); if (e) { ctx.fillStyle = C.paper; ctx.beginPath(); ctx.arc(e.x, e.y, e.r * 1.25, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = C.ink; ctx.beginPath(); ctx.arc(e.x + e.r * 0.2, e.y, e.r * 0.7, 0, Math.PI * 2); ctx.fill(); }

  // ---- typography, set on the grid ----
  const hud = S.hud || {};
  // top rule and the label row: flush-left, one label per column group
  ctx.fillStyle = C.ink; ctx.fillRect(M, 22, W - 2 * M, 2);
  ctx.font = '700 12px Archivo'; ctx.textAlign = 'left';
  ctx.fillText(hud.score_label || 'Score', G.x(0), 40);
  if (S.title) ctx.fillText(S.title, G.x(4), 40);
  ctx.font = '400 12px Archivo'; ctx.fillText((mood[0].toUpperCase() + mood.slice(1)), G.x(7), 40);
  // the score: a huge, tight black numeral hanging from the rule
  ctx.font = '400 132px "Archivo Black"'; ctx.letterSpacing = '-4px';
  const sc = String(hud.score ?? '');
  ctx.save(); ctx.strokeStyle = C.paper; ctx.lineWidth = 10; ctx.lineJoin = 'round'; ctx.strokeText(sc, G.x(0) - 6, 152); ctx.restore();
  ctx.fillText(sc, G.x(0) - 6, 152); ctx.letterSpacing = '0px';
  // right block: best, lives as red squares, pause as a black square
  if (hud.best) { ctx.font = '700 12px Archivo'; ctx.fillText(hud.best, G.x(9), 40); }
  if (hud.lives != null) {
    const n = Math.max(3, hud.lives);
    for (let i = 0; i < n; i++) { const x = G.x(9) + i * 18;
      if (i < hud.lives) { ctx.fillStyle = C.red; ctx.fillRect(x, 50, 12, 12); }
      else { ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5; ctx.strokeRect(x + .75, 50.75, 10.5, 10.5); } }
  }
  if (hud.pause) { const s = 44, x = W - M - s, y = 32; ctx.fillStyle = C.ink; ctx.fillRect(x, y, s, s);
    ctx.fillStyle = C.paper; ctx.fillRect(x + 15, y + 13, 5, 18); ctx.fillRect(x + 24, y + 13, 5, 18); }
}

export const appCss = `
.app{font-family:Archivo,sans-serif;background:#f1eee7;color:#111;display:grid;grid-template-columns:repeat(6,1fr);column-gap:10px;
  grid-template-rows:auto auto auto auto 1fr auto auto;padding:54px 20px 0;box-sizing:border-box;position:relative}
.app::before{content:'';position:absolute;inset:0 20px;pointer-events:none;
  background:repeating-linear-gradient(90deg,rgba(17,17,17,.06) 0 1px,transparent 1px calc((100% + 10px)/6));}
.app>*{position:relative}
.top{grid-column:1/-1;display:grid;grid-template-columns:subgrid;align-items:end;border-top:4px solid #111;padding-top:8px}
.brand{grid-column:1/4;font:400 22px/1 'Archivo Black';letter-spacing:-.02em}
.place{grid-column:4/-1;font-weight:700;font-size:14px;line-height:1.2}
.hero{grid-column:1/-1;display:grid;grid-template-columns:subgrid;margin-top:46px}
.label{grid-column:1/-1;font-weight:700;font-size:14px;border-top:1px solid #111;padding-top:6px}
.value{grid-column:1/-1;font:400 112px/.84 'Archivo Black';letter-spacing:-.045em;margin:18px 0 0 -5px;white-space:nowrap}
.sub{grid-column:3/-1;font-size:16px;line-height:1.3;margin-top:18px;font-weight:400}
.status{grid-column:1/3;grid-row:4;margin-top:14px;align-self:start;font-weight:700;font-size:14px;line-height:1.2;color:#111;display:flex;align-items:center;gap:7px}
.status::before{content:'';width:12px;height:12px;background:#d01c14;flex:none}
.rows-title{grid-column:1/-1;margin:46px 0 0;font-size:14px;font-weight:700;border-top:4px solid #111;padding-top:8px}
.rows{grid-column:1/-1;list-style:none;margin:6px 0 0;padding:0;counter-reset:r}
.rows li{counter-increment:r;display:grid;grid-template-columns:28px 70px 1fr auto;align-items:baseline;min-height:58px;padding:18px 0 0;
  border-bottom:1px solid #111;box-sizing:border-box;font-size:16px}
.rows li::before{content:counter(r,decimal-leading-zero);font-weight:700;font-size:12px}
.rows .t{font:400 20px 'Archivo Black';letter-spacing:-.03em}
.rows .d{font-size:16px}
.rows .s{font-size:14px;font-weight:700;text-align:right}
.rows li[data-state=late] .s{color:#c4160f}
.rows li[data-state=few] .s{font-weight:400}
.cta{grid-column:1/-1;grid-row:7;align-self:end;margin:24px 0 22px;height:60px;border:0;border-radius:0;background:#d01c14;color:#fff;font:700 18px Archivo;
  text-align:left;padding:0 18px;display:flex;justify-content:space-between;align-items:center}
.tabs{grid-column:1/-1;grid-row:8;display:grid;grid-template-columns:repeat(4,1fr);column-gap:10px;margin:0 -20px;padding:0 20px 30px;background:#f1eee7;
  border-top:0;position:relative}
.tabs::before{content:'';position:absolute;left:20px;right:20px;top:0;height:1px;background:#111}
.tabs a{display:flex;flex-direction:column;align-items:flex-start;gap:6px;padding-top:12px;min-height:48px;border-top:5px solid transparent;
  font-size:14px;font-weight:700;color:#111;position:relative;top:-2px}
.tabs a:not(.on){color:#4a4a4a;font-weight:400}
.tabs a.on{border-top-color:#d01c14}
.ic{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:square;stroke-linejoin:miter}
`;

// an arrow for the CTA and a running index column, drawn as plain SVG rules
export function appDecor(root) {
  const v = root.querySelector('.value'); let fs = 112;   // the figure always fits the measure
  while (v.scrollWidth > v.clientWidth + 1 && fs > 36) { fs -= 4; v.style.fontSize = fs + 'px'; }
  const cta = root.querySelector('.cta');
  cta.insertAdjacentHTML('beforeend', '<svg width="26" height="16" viewBox="0 0 26 16" aria-hidden="true" style="flex:none"><path d="M0 8h24M17 1l7 7-7 7" fill="none" stroke="#fff" stroke-width="2.2"/></svg>');
}
