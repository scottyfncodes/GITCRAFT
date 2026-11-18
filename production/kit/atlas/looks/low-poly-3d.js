// 8 · Low-Poly 3D: the scene is built and lit in 3D by MeshCraft (headless Blender, looks/low-poly-3d.py) and the
// canvas only lays the HUD over the render. Faceted, flat-shaded, toy-like; Fredoka on soft chunky panels.
//
// The game sample draws a pre-rendered image: ?render3d=<url> on the stage URL, else
// looks/_renders/<scene title slug>/game3d.png. The app's hero card shows ?hero3d=<url>, else the same folder's
// hero3d.png. Render them with:  looks/low-poly-3d.sh <scene.json> looks/_renders/<slug>
// A missing render is shown as missing (and the stage reports the 404); nothing is faked in 2D.
export const meta = { id: 'low-poly-3d', prerender: 'meshcraft' };

export const slug = (s) => String(s || 'scene').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'scene';
function renderUrl(param, file, title) {
  const q = new URLSearchParams(location.search);
  return q.get(param) || `looks/_renders/${slug(title)}/${file}`;
}
function loadImage(src) {
  return new Promise((ok) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => ok(null); i.src = src; });
}

// HUD inks per mood: a cream toy panel with a coloured lip, ink from the scene's own night/day palette
const HUD = {
  dusk: { panel: '#fff7ef', lip: '#d8c3d6', ink: '#25305c', soft: 'rgba(37,48,92,.62)', accent: '#ff5a4c', shadow: 'rgba(24,20,60,.38)' },
  night: { panel: '#f1f3ff', lip: '#a9b2e0', ink: '#1a2350', soft: 'rgba(26,35,80,.62)', accent: '#ff5a4c', shadow: 'rgba(0,0,20,.5)' },
  day: { panel: '#ffffff', lip: '#b9d8ee', ink: '#1d3557', soft: 'rgba(29,53,87,.62)', accent: '#ff5a4c', shadow: 'rgba(20,60,110,.28)' },
  dawn: { panel: '#fffaf5', lip: '#e2c6d0', ink: '#2b2f5c', soft: 'rgba(43,47,92,.62)', accent: '#ff5a4c', shadow: 'rgba(60,30,70,.3)' },
};

function toyPanel(ctx, L, x, y, w, h, r, c) {
  // a chunky toy block: soft cast shadow, a darker lip below, then the face with a faint top highlight
  ctx.save(); ctx.shadowColor = c.shadow; ctx.shadowBlur = 22; ctx.shadowOffsetY = 10;
  L.rr(ctx, x, y + 5, w, h, r); ctx.fillStyle = c.lip; ctx.fill(); ctx.restore();
  L.rr(ctx, x, y, w, h, r); ctx.fillStyle = c.panel; ctx.fill();
  const g = ctx.createLinearGradient(0, y, 0, y + h); g.addColorStop(0, 'rgba(255,255,255,.9)'); g.addColorStop(0.5, 'rgba(255,255,255,0)');
  ctx.save(); L.rr(ctx, x + 3, y + 3, w - 6, h * 0.5, r - 3); ctx.fillStyle = g; ctx.globalAlpha = 0.5; ctx.fill(); ctx.restore();
}

function heart(ctx, x, y, s) {   // a chunky heart, centred on x,y, s = width
  const k = s / 24; ctx.beginPath();
  ctx.moveTo(x, y + 9 * k);
  ctx.bezierCurveTo(x - 14 * k, y, x - 12 * k, y - 12 * k, x - 5.5 * k, y - 10 * k);
  ctx.bezierCurveTo(x - 2.5 * k, y - 9 * k, x - 0.8 * k, y - 7 * k, x, y - 5 * k);
  ctx.bezierCurveTo(x + 0.8 * k, y - 7 * k, x + 2.5 * k, y - 9 * k, x + 5.5 * k, y - 10 * k);
  ctx.bezierCurveTo(x + 12 * k, y - 12 * k, x + 14 * k, y, x, y + 9 * k);
  ctx.closePath();
}

function drawHud(ctx, S, L, W, H) {
  const c = HUD[S.mood] || HUD.day, hud = S.hud || {};
  // score block (top left)
  ctx.font = '700 40px Fredoka'; const sw = ctx.measureText(String(hud.score ?? '')).width;
  ctx.font = '600 13px Fredoka'; const lw = ctx.measureText(String(hud.score_label || '')).width + 4;
  const pw = Math.max(132, Math.max(sw, lw) + 44);
  toyPanel(ctx, L, 24, 22, pw, 82, 22, c);
  ctx.fillStyle = c.soft; ctx.font = '600 13px Fredoka';
  if ('letterSpacing' in ctx) ctx.letterSpacing = '1.5px';
  ctx.fillText(String(hud.score_label || ''), 46, 50);
  if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
  ctx.fillStyle = c.ink; ctx.font = '700 40px Fredoka'; ctx.fillText(String(hud.score ?? ''), 44, 89);
  // lives: hearts on a small pill under the score
  if (hud.lives != null) {
    const n = Math.max(3, hud.lives), lwid = 20 + n * 28;
    toyPanel(ctx, L, 24, 116, lwid, 38, 19, c);
    for (let i = 0; i < n; i++) {
      heart(ctx, 24 + 24 + i * 28, 136, 22);
      ctx.fillStyle = i < hud.lives ? c.accent : 'rgba(37,48,92,.16)'; ctx.fill();
      if (i < hud.lives) { ctx.fillStyle = 'rgba(255,255,255,.55)'; ctx.beginPath(); ctx.arc(24 + 24 + i * 28 - 4.5, 131, 2.4, 0, Math.PI * 2); ctx.fill(); }
    }
  }
  // pause (top right) and best, on the same baseline
  let right = W - 24;
  if (hud.pause) {
    toyPanel(ctx, L, right - 56, 22, 56, 56, 18, c);
    ctx.fillStyle = c.ink; L.rr(ctx, right - 36, 37, 6, 26, 3); ctx.fill(); L.rr(ctx, right - 26, 37, 6, 26, 3); ctx.fill();
    right -= 56 + 12;
  }
  if (hud.best) {
    ctx.font = '600 16px Fredoka'; const bw = ctx.measureText(String(hud.best)).width + 36;
    toyPanel(ctx, L, right - bw, 30, bw, 40, 20, c);
    ctx.fillStyle = c.ink; ctx.textAlign = 'center'; ctx.fillText(String(hud.best), right - bw / 2, 56); ctx.textAlign = 'left';
  }
}

function missing(ctx, S, L, W, H, src) {
  // say so plainly: there is no 2D stand-in for a 3D render
  ctx.fillStyle = '#20263f'; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = 'rgba(255,255,255,.12)'; ctx.lineWidth = 1;
  for (let x = 0; x <= W; x += 48) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 0; y <= H; y += 48) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  ctx.textAlign = 'center'; ctx.fillStyle = '#fff7ef'; ctx.font = '700 30px Fredoka';
  ctx.fillText('3D render missing: run MeshCraft', W / 2, H / 2 - 12);
  ctx.font = '400 16px Fredoka'; ctx.fillStyle = 'rgba(255,247,239,.75)';
  ctx.fillText(`looks/low-poly-3d.sh <scene.json> looks/_renders/${slug(S.title)}`, W / 2, H / 2 + 22);
  ctx.fillText(`(looked for ${src})`, W / 2, H / 2 + 46); ctx.textAlign = 'left';
}

export async function game(ctx, S, L, W, H) {
  const src = renderUrl('render3d', 'game3d.png', S.title);
  const img = await loadImage(src);
  if (!img) { missing(ctx, S, L, W, H, src); return; }
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, W, H);
  drawHud(ctx, S, L, W, H);
}

export const appCss = `
.app{font-family:Fredoka,sans-serif;color:#24305a;display:flex;flex-direction:column;padding:56px 20px 0;box-sizing:border-box;
  background:radial-gradient(120% 60% at 100% 0%,#ffe1cf 0%,rgba(255,225,207,0) 60%),radial-gradient(90% 50% at 0% 100%,#e3e2ff 0%,rgba(227,226,255,0) 70%),#fbf3ec}
.top{display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:700;font-size:30px;letter-spacing:-.01em;color:#24305a}
.place{font-weight:600;font-size:14px;color:#24305a;background:#fff;padding:8px 14px;border-radius:99px;box-shadow:0 3px 0 #e6d7cd,0 8px 16px rgba(60,40,90,.08)}
.hero{position:relative;margin-top:20px;border-radius:30px;padding:22px 22px 22px;color:#fff7ef;
  background:linear-gradient(160deg,#2c3668 0%,#4d4a8a 55%,#8a5b8f 100%);box-shadow:0 8px 0 #1d2550,0 20px 32px rgba(36,30,90,.28)}
.hero::before{content:'';position:absolute;right:14px;top:22px;width:132px;height:132px;border-radius:50%;
  background:radial-gradient(circle at 50% 45%,rgba(255,190,150,.55),rgba(255,140,120,.18) 55%,rgba(255,140,120,0) 72%)}
.hero>*{position:relative;z-index:1}
.hero .hero3d{position:absolute;right:6px;top:4px;width:150px;height:150px;z-index:2;pointer-events:none}
.hero .missing3d{position:absolute;right:16px;top:20px;width:118px;font-size:14px;line-height:1.25;color:#fff7ef;opacity:.9;text-align:center;
  border:2px dashed rgba(255,247,239,.5);border-radius:18px;padding:16px 8px}
.label{font-weight:600;font-size:16px;color:#ffd9c4}
.value{font-weight:700;font-size:70px;line-height:1;letter-spacing:-.02em;margin:8px 0 22px}
.sub{font-size:16px;line-height:1.3;color:#fff7ef}
.status{display:inline-block;margin-top:14px;background:#8ff0e1;color:#0d3b36;font-weight:600;font-size:14px;padding:7px 14px;border-radius:99px;box-shadow:0 3px 0 #4fc2b2}
.rows-title{font-size:18px;font-weight:700;margin:26px 2px 12px;color:#24305a}
.rows{list-style:none;margin:0;padding:0;display:grid;gap:12px}
.rows li{display:grid;grid-template-columns:72px 1fr auto;align-items:center;gap:6px;background:#fff;border-radius:22px;padding:12px 14px 12px 12px;
  min-height:44px;font-size:16px;box-shadow:0 5px 0 #eadbd2,0 12px 20px rgba(60,40,90,.08)}
.rows .t{font-weight:700;font-size:18px;background:#f1edff;color:#2e2a6e;border-radius:14px;padding:9px 0;text-align:center}
.rows .d{font-weight:600;padding-left:6px}
.rows .s{font-size:14px;font-weight:600;padding:6px 11px;border-radius:99px;background:#d9f6e6;color:#17613c;white-space:nowrap}
.rows li[data-state=late] .s{background:#ffe1dc;color:#a8261f}
.rows li[data-state=few] .s{background:#fff0c4;color:#6e4a00}
.cta{margin:20px 0 0;min-height:58px;border:0;border-radius:22px;background:#d63f33;color:#fff;font:700 20px Fredoka;letter-spacing:.01em;
  box-shadow:0 6px 0 #9e2a22,0 16px 24px rgba(214,63,51,.3)}
.tabs{margin-top:auto;display:grid;grid-template-columns:repeat(4,1fr);padding:10px 12px 30px;background:#fff;margin-left:-20px;margin-right:-20px;
  border-radius:28px 28px 0 0;box-shadow:0 -6px 24px rgba(60,40,90,.10)}
.tabs a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:52px;font-size:14px;font-weight:600;color:#5d6488;border-radius:18px}
.tabs a.on{color:#b3302a;background:#ffe6e0}
.ic{width:24px;height:24px;fill:none;stroke:currentColor;stroke-width:2.3;stroke-linecap:round;stroke-linejoin:round}
.tabs a.on .ic{fill:rgba(214,63,51,.14)}
`;

export async function appDecor(root, A, L) {
  const q = new URLSearchParams(location.search);
  let title = null;
  try { const sc = await fetch(q.get('scene') || 'scenes/atlas.json').then((r) => r.json()); title = sc.game && sc.game.title; } catch { /* no scene: default slug */ }
  const src = renderUrl('hero3d', 'hero3d.png', title);
  const card = root.querySelector('.hero');
  const img = await loadImage(src);
  if (img) { img.className = 'hero3d'; img.alt = ''; card.appendChild(img); }
  else { const m = document.createElement('div'); m.className = 'missing3d'; m.textContent = '3D render missing: run MeshCraft'; card.appendChild(m); }
  // the big value shares its row with the 3D hero: shrink a long value (e.g. "18 mph") until it clears the figure
  await document.fonts.ready;
  const v = card.querySelector('.value'), cs = getComputedStyle(card);
  const avail = card.clientWidth - parseFloat(cs.paddingLeft) - 156;
  v.style.display = 'inline-block';
  const w = v.getBoundingClientRect().width;
  if (w > avail) { const fs = Math.max(40, Math.floor(70 * avail / w)); v.style.fontSize = fs + 'px'; v.style.marginBottom = (22 + 70 - fs) + 'px'; }
  v.style.display = '';
}
