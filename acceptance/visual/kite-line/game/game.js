// KITE LINE: hold to climb into the wind, let go to glide. Collect ribbons, dodge gulls, never touch the ground.
// Design A (shipped) draws everything as pen and pencil on a school-book page; the strokes re-draw ("boil") eight times a second.
// Designs B and C (the other two of the design pick) are kept as themes: ?theme=b|c.
(() => {
  'use strict';
  const root = document.documentElement, Q = new URLSearchParams(location.search);
  if (/^[abc]$/.test(Q.get('theme') || '')) root.dataset.theme = Q.get('theme');
  const $ = (id) => document.getElementById(id);
  const cv = $('sky'), cx = cv.getContext('2d');

  // ------------------------------------------------------------ feel: every tuned number in one place (direction.json play.feel)
  const FEEL = { lift: 1350, gravity: 780, firstFlightGravity: 0.1, firstRibbonAhead: 300, maxUp: 360, maxDown: 430, scroll: 200, scrollGain: 3.2, kiteX: 0.36,
                 hitStopMs: 110, invulnMs: 1100, shakePx: 7, boilMs: 125, ribbonEvery: 1.05, gullFrom: 9, gustFrom: 22, groundPad: 18, catchR: 30, hitR: 24,
                 weightBackS: 3, momentKick: 210, momentStopMs: 160, momentMs: 1500, momentSlow: 0.35, failMs: 700 };

  // ------------------------------------------------------------ sound: every feedback event answers in the same frame (WebAudio, no files)
  let AC = null, muted = false;
  try { muted = localStorage.getItem('kiteline.muted') === '1'; } catch {}
  function tone(f0, f1, ms, type = 'triangle', vol = 0.12) {
    if (muted) return;
    try { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); } catch { return; }
    const o = AC.createOscillator(), g = AC.createGain(), t = AC.currentTime;
    o.type = type; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(Math.max(30, f1), t + ms / 1000);
    g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + ms / 1000); o.connect(g).connect(AC.destination); o.start(t); o.stop(t + ms / 1000 + 0.02);
  }
  const SFX = { lift: () => tone(240, 420, 120, 'sine', 0.05), ribbon: (n) => { tone(660 + n * 20, 990 + n * 20, 160); setTimeout(() => tone(990, 1320, 140), 70); },
                first: () => [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => tone(f, f * 1.02, 220, 'triangle', 0.13), i * 90)),
                hit: () => tone(180, 60, 220, 'square', 0.1), ground: () => { tone(220, 50, 520, 'sawtooth', 0.09); tone(90, 40, 300, 'square', 0.08); } };
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ------------------------------------------------------------ deterministic randomness (the same seed draws the same flight)
  const seed = parseInt(Q.get('seed') || '7', 10);
  function rng(s) { let a = s >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const hash = (n) => { let x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const noise = (x) => { const i = Math.floor(x), f = x - i, s = f * f * (3 - 2 * f); return hash(i) * (1 - s) + hash(i + 1) * s; };

  // ------------------------------------------------------------ theme tokens (CSS custom properties are the source of truth)
  let C = {};
  function readTheme() { const s = getComputedStyle(root); for (const k of ['paper', 'surface', 'ink', 'pen', 'mark', 'kite', 'rule', 'margin', 'muted']) C[k] = s.getPropertyValue('--' + k).trim();
    C.theme = root.dataset.theme; C.ceiling = parseFloat(s.getPropertyValue('--ceiling')) || 60; }
  const NIGHT = { paper: '#1f232b', ink: '#f1ede4', pen: '#f1ede4', mark: '#f5c04a', kite: '#ff6b5e', rule: '#2c313b', muted: '#b7b2a8' };
  const A = () => C.theme === 'a', B = () => C.theme === 'b', N = () => C.theme === 'c';

  // ------------------------------------------------------------ the page
  let W = 0, H = 0, DPR = 1, paper = null, cover = null;
  function resize() {
    DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H = innerHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); cx.setTransform(DPR, 0, 0, DPR, 0, 0);
    paper = drawPaper(C); cover = B() ? drawCover() : null; if (G.state !== 'playing') draw();
  }
  function sheet() { const o = document.createElement('canvas'); o.width = cv.width; o.height = cv.height; const g = o.getContext('2d'); g.scale(DPR, DPR); return [o, g]; }
  function drawPaper(P, night, avoid) {
    const [o, g] = sheet(); g.fillStyle = P.paper; g.fillRect(0, 0, W, H);
    const r = rng(11);
    if (!night && A()) {          // ruled lines, the red margin, punch holes
      g.strokeStyle = P.rule; g.lineWidth = 1.2; for (let y = 96; y < H; y += 34) { g.beginPath(); g.moveTo(0, y + 0.5); g.lineTo(W, y + 0.5); g.stroke(); }
      g.strokeStyle = P.margin; g.lineWidth = 1.6; g.beginPath(); g.moveTo(52.5, 0); g.lineTo(52.5, H); g.stroke();
      g.fillStyle = 'rgba(0,0,0,.05)'; for (const y of [H * 0.2, H * 0.5, H * 0.8]) { g.beginPath(); g.arc(22, y, 9, 0, 7); g.fill(); }
    } else if (!night && B()) {   // chart paper: a fine grid, every fifth line stronger, an altitude ruler down the right edge
      for (let i = 0, x = 0; x < W; x += 20, i++) { g.strokeStyle = P.rule; g.globalAlpha = i % 5 ? 0.5 : 1; g.lineWidth = i % 5 ? 0.7 : 1.2; g.beginPath(); g.moveTo(x + 0.5, 0); g.lineTo(x + 0.5, H); g.stroke(); }
      for (let i = 0, y = 4; y < H; y += 20, i++) { g.strokeStyle = P.rule; g.globalAlpha = i % 5 ? 0.5 : 1; g.lineWidth = i % 5 ? 0.7 : 1.2; g.beginPath(); g.moveTo(0, y + 0.5); g.lineTo(W, y + 0.5); g.stroke(); }
      g.globalAlpha = 1; g.fillStyle = P.pen; g.fillRect(W - 34, 64, 34, H - 64);
      g.strokeStyle = '#fffaf0'; g.fillStyle = '#fffaf0'; g.font = '700 9px "Space Mono", monospace'; g.lineWidth = 1.2;
      for (let i = 0, y = H - 80; y > 84; y -= 20, i++) { g.beginPath(); g.moveTo(W - 34, y + 0.5); g.lineTo(W - (i % 5 ? 26 : 18), y + 0.5); g.stroke(); if (i % 5 === 0) g.fillText(String(i * 2), W - 16, y + 3); }
    } else {                      // black paper: tooth and a few chalk stars (kept off any text block passed in)
      for (let i = 0; i < W * H / 260; i++) { g.fillStyle = `rgba(255,255,255,${0.025 + r() * 0.03})`; g.fillRect(r() * W, r() * H, 1, 1); }
      g.strokeStyle = P.ink; g.globalAlpha = 0.55; g.lineWidth = 1.4;
      for (let i = 0; i < 16; i++) { const x = r() * W, y = r() * H * 0.6, s = 3 + r() * 4;
        if (avoid && x > avoid.left - 48 && x < avoid.right + 48 && y > avoid.top - 40 && y < avoid.bottom + 40) continue;
        g.beginPath(); g.moveTo(x - s, y); g.lineTo(x + s, y); g.moveTo(x, y - s); g.lineTo(x, y + s); g.stroke(); }
      g.globalAlpha = 1;
      if (!night && N()) { g.fillStyle = '#f1ede4'; g.globalAlpha = 0.9; g.beginPath(); g.arc(W - 70, 120, 34, 0, 7); g.fill(); g.fillStyle = P.paper; g.globalAlpha = 1; g.beginPath(); g.arc(W - 84, 112, 30, 0, 7); g.fill(); }
    }
    return o;
  }
  function drawCover() {   // design B's title: a green cloth logbook cover, a cream label, a rubber-stamped kite, an elastic band
    const [o, g] = sheet(), r = rng(5);
    g.fillStyle = C.pen; g.fillRect(0, 0, W, H);
    g.globalAlpha = 0.09; g.strokeStyle = '#000'; g.lineWidth = 1; for (let y = 0; y < H; y += 3) { g.beginPath(); g.moveTo(0, y + r()); g.lineTo(W, y + r()); g.stroke(); }
    g.strokeStyle = '#fff'; for (let x = 0; x < W; x += 3) { g.beginPath(); g.moveTo(x + r(), 0); g.lineTo(x + r(), H); g.stroke(); }
    g.globalAlpha = 1; g.fillStyle = '#17463a'; g.fillRect(0, 0, Math.max(18, W * 0.05), H);                 // the spine
    g.fillStyle = '#12362c'; g.fillRect(W - Math.max(34, W * 0.09), 0, 12, H);                                // the elastic band
    const lw = Math.min(W * 0.8, 520), lx = (W - lw) / 2, ly = H * 0.085, lh = Math.min(H * 0.42, 330);
    g.fillStyle = 'rgba(0,0,0,.18)'; g.fillRect(lx + 3, ly + 4, lw, lh); g.fillStyle = C.surface; g.fillRect(lx, ly, lw, lh);
    g.strokeStyle = C.pen; g.lineWidth = 2; g.strokeRect(lx + 8, ly + 8, lw - 16, lh - 16); g.lineWidth = 1; g.strokeRect(lx + 13, ly + 13, lw - 26, lh - 26);
    const sx = W / 2, sy = ly + lh + (H - ly - lh) * 0.36, sr = Math.min(W * 0.2, 92);                         // the stamp
    g.strokeStyle = '#e9e2cc'; g.fillStyle = '#e9e2cc'; g.globalAlpha = 0.92; g.lineWidth = 3; g.beginPath(); g.arc(sx, sy, sr, 0, 7); g.stroke(); g.lineWidth = 1.2; g.beginPath(); g.arc(sx, sy, sr - 7, 0, 7); g.stroke();
    g.beginPath(); g.moveTo(sx, sy - sr * 0.62); g.lineTo(sx + sr * 0.42, sy - sr * 0.1); g.lineTo(sx, sy + sr * 0.62); g.lineTo(sx - sr * 0.42, sy - sr * 0.1); g.closePath(); g.fill();
    g.strokeStyle = C.pen; g.lineWidth = 2; g.beginPath(); g.moveTo(sx, sy - sr * 0.62); g.lineTo(sx, sy + sr * 0.62); g.moveTo(sx - sr * 0.42, sy - sr * 0.1); g.lineTo(sx + sr * 0.42, sy - sr * 0.1); g.stroke();
    g.globalAlpha = 1; return o;
  }

  // ------------------------------------------------------------ the pencil: every line is drawn twice, slightly off, and boils (design B rules its lines straight)
  let boil = 0;
  function wob(x, y, k, amt) { return [x + (hash(x * 0.37 + y * 0.11 + k + boil * 13.1) - 0.5) * amt, y + (hash(y * 0.29 - x * 0.17 + k + boil * 7.3) - 0.5) * amt]; }
  function line(pts, color, width, passes = 2, amt = 2.2, closed = false) {
    if (B()) { passes = 1; amt = 0; }
    cx.strokeStyle = color; cx.lineCap = 'round'; cx.lineJoin = 'round';
    for (let p = 0; p < passes; p++) {
      cx.lineWidth = width * (p ? 0.7 : 1); cx.globalAlpha = p ? 0.55 : 1; cx.beginPath();
      pts.forEach(([x, y], i) => { const [a, b] = wob(x, y, p * 3.7 + i * 0.1, amt); i ? cx.lineTo(a, b) : cx.moveTo(a, b); });
      if (closed) cx.closePath(); cx.stroke();
    }
    cx.globalAlpha = 1;
  }
  function poly(pts) { cx.beginPath(); pts.forEach(([x, y], i) => i ? cx.lineTo(x, y) : cx.moveTo(x, y)); cx.closePath(); }
  function hatch(pts, color, gap = 7, angle = -0.9, width = 1.3) {   // scribble fill clipped to a shape (a flat fill in design B)
    if (B()) { poly(pts); cx.fillStyle = color; cx.fill(); return; }
    cx.save(); poly(pts); cx.clip();
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]), x0 = Math.min(...xs) - 40, x1 = Math.max(...xs) + 40, y0 = Math.min(...ys) - 40, y1 = Math.max(...ys) + 40;
    cx.strokeStyle = color; cx.lineWidth = width; cx.globalAlpha = 0.85; cx.beginPath();
    const dx = Math.cos(angle), dy = Math.sin(angle), nx = -dy, ny = dx, mx = (x0 + x1) / 2, my = (y0 + y1) / 2, R = Math.hypot(x1 - x0, y1 - y0) / 2 + 10;
    for (let t = -R; t < R; t += gap) { const j = (hash(t * 1.7 + boil) - 0.5) * 2.4, ox = mx + nx * (t + j), oy = my + ny * (t + j); cx.moveTo(ox - dx * R, oy - dy * R); cx.lineTo(ox + dx * R, oy + dy * R); }
    cx.stroke(); cx.restore(); cx.globalAlpha = 1;
  }
  const circle = (x, y, r, n = 14) => Array.from({ length: n + 1 }, (_, i) => [x + Math.cos(i / n * 6.283) * r, y + Math.sin(i / n * 6.283) * r]);

  // ------------------------------------------------------------ state
  const G = window.__game = { state: 'title', score: 0, time: 0, lives: 3, best: 0, revealed: false, moment: null, note: null, first_ribbon_at: null, kiteY: 0, vy: 0, speed: FEEL.scroll, fail: null };
  try { G.best = parseInt(localStorage.getItem('kiteline.best') || '0', 10) || 0; } catch {}
  let rand = rng(seed), things = [], path = [], worldX = 0, holding = false, hitStop = 0, invuln = 0, shake = 0, nextRibbon = 0, nextGull = 0, nextGust = 0, last = 0, raf = 0, hintT = 0, fx = null, slow = 0;
  const kx = () => W * FEEL.kiteX, groundY = (x) => H - 70 - noise((x + worldX) * 0.004) * 60 - noise((x + worldX) * 0.013) * 18;
  const flyerX = () => Math.max(70, W * 0.1);
  const ceiling = () => C.ceiling + 46;   // the kite's top edge never goes under the HUD

  // ------------------------------------------------------------ drawing the world
  function ground(P, far = true) {
    const pts = []; for (let x = -10; x <= W + 20; x += 18) pts.push([x, groundY(x)]);
    if (A()) hatch([...pts, [W + 20, H + 10], [-10, H + 10]], P.muted, 8, -1.0, 1);
    if (B()) { cx.fillStyle = P.rule; poly([...pts, [W + 20, H + 10], [-10, H + 10]]); cx.globalAlpha = 0.55; cx.fill(); cx.globalAlpha = 1;
      for (let x = (-(worldX % 40) + 40) % 40; x < W; x += 40) { const y = groundY(x); line([[x, y], [x, y + 8]], P.pen, 1.4, 1, 0); } }
    line(pts, B() ? P.pen : P.ink, 2.2, 2, 1.8);
    if (far && A()) { const fl = []; for (let x = -10; x <= W + 20; x += 24) fl.push([x, H - 150 - noise((x + worldX * 0.4) * 0.003 + 9) * 90]); cx.globalAlpha = 0.5; line(fl, P.muted, 1.4, 1, 1.5); cx.globalAlpha = 1; }
  }
  function person(P, at) {
    const x = at ?? flyerX(), y = groundY(x) - 2;
    if (B()) { line(circle(x, y - 8, 5, 10), P.pen, 2, 1, 0, true); line([[x, y - 3], [x, y]], P.pen, 2, 1, 0); return [x, y - 8]; }   // a map pin
    line([[x, y - 34], [x, y - 12]], P.ink, 2.4); line(circle(x, y - 42, 7, 10), P.ink, 2.2, 2, 1.4, true);
    line([[x, y - 12], [x - 7, y]], P.ink, 2.2); line([[x, y - 12], [x + 7, y]], P.ink, 2.2);
    line([[x, y - 28], [x + 13, y - 36]], P.ink, 2.2); line([[x, y - 28], [x - 10, y - 20]], P.ink, 2.2);
    return [x + 13, y - 36];
  }
  const tieOf = (x, y, s, tilt) => [x + (-26 * Math.sin(tilt)) * s, y + 26 * Math.cos(tilt) * s];   // the bridle point, below the cross spar
  function kite(P, x, y, s = 1, tilt = 0, bows = 0, bowPop = 1) {
    const k = (a, b) => [x + (a * Math.cos(tilt) - b * Math.sin(tilt)) * s, y + (a * Math.sin(tilt) + b * Math.cos(tilt)) * s];
    const body = [k(0, -34), k(24, -6), k(0, 38), k(-24, -6)];
    hatch(body, P.kite, 5, -0.7, 2.1);
    line(body, P.ink, 2.6, 2, 2, true); line([k(0, -34), k(0, 38)], P.ink, 1.6, 1); line([k(-24, -6), k(24, -6)], P.ink, 1.6, 1);
    const tail = []; for (let i = 0; i <= 8; i++) tail.push(k(Math.sin(i * 0.9 + G.time * 6) * 9, 38 + i * 12));
    line(tail, P.ink, 1.6, 1, 1.5);
    for (let i = 0; i < Math.min(bows, 8); i++) { const [bx, by] = tail[i + 1], z = (i === bows - 1 ? bowPop : 1) * s;
      line([[bx - 8 * z, by - 5 * z], [bx + 8 * z, by + 5 * z], [bx + 8 * z, by - 5 * z], [bx - 8 * z, by + 5 * z], [bx - 8 * z, by - 5 * z]], P.mark, 2.6 * Math.min(2, z), 1, 1.2); }
  }
  function ribbon(P, x, y) {   // a bow with two trailing tails, in the highlighter colour, outlined in pen
    const bow = [[x, y], [x - 14, y - 9], [x - 14, y + 9], [x, y], [x + 14, y - 9], [x + 14, y + 9], [x, y]];
    hatch(bow.slice(0, 4), P.mark, 3, 0.9, 2.4); hatch(bow.slice(3), P.mark, 3, 0.9, 2.4);
    line(bow, P.ink, 1.8, 2, 1.2, true);
    for (const s of [-1, 1]) { const t = []; for (let i = 0; i <= 5; i++) t.push([x + s * (2 + i * 3), y + 4 + i * 4 + Math.sin(i + G.time * 8) * 2]); line(t, P.ink, 1.5, 1, 1); }
  }
  function gull(P, x, y, flap) { const f = Math.sin(flap) * 7; line([[x - 18, y - 4 - f], [x - 8, y - 9 - f * 0.4], [x, y], [x + 8, y - 9 - f * 0.4], [x + 18, y - 4 - f]], P.ink, 2.6, 2, 1.6); }
  function gust(P, x, y, w) { cx.globalAlpha = 0.75; for (let j = 0; j < 3; j++) { const pts = []; for (let i = 0; i <= 10; i++) pts.push([x + i * w / 10, y + j * 12 + Math.sin(i * 0.8 + G.time * 3 + j) * 4]); line(pts, P.muted, 1.6, 1, 1.4); } cx.globalAlpha = 1; }
  function stringTo(P, hand, tie, slack = 0) {
    const mx = (hand[0] + tie[0]) / 2, my = Math.max(hand[1], tie[1]) - Math.abs(tie[0] - hand[0]) * 0.05 + 30 + slack;
    const pts = []; for (let i = 0; i <= 16; i++) { const t = i / 16; pts.push([(1 - t) * (1 - t) * hand[0] + 2 * (1 - t) * t * mx + t * t * tie[0], (1 - t) * (1 - t) * hand[1] + 2 * (1 - t) * t * my + t * t * tie[1]]); }
    line(pts, P.pen, 1.4, 1, 1.0);
  }
  function trail(P) {
    if (path.length < 3) return;
    const pts = path.slice(-60).map(([wx, y]) => [kx() - (worldX - wx), y]);
    if (B()) { line(pts, P.pen, 2, 1, 0); for (let i = 0; i < pts.length; i += 12) { cx.fillStyle = P.pen; cx.beginPath(); cx.arc(pts[i][0], pts[i][1], 3, 0, 7); cx.fill(); } return; }   // the flight, plotted
    cx.setLineDash([2, 7]); line(pts, P.muted, 1.4, 1, 0.6); cx.setLineDash([]);
  }
  function ghostCount(P) {   // design C: the count is the page (a giant chalk numeral behind the play)
    cx.save(); cx.font = `700 ${Math.min(W * 0.62, H * 0.5)}px "Space Mono", monospace`; cx.textAlign = 'center'; cx.textBaseline = 'middle';
    cx.strokeStyle = P.ink; cx.globalAlpha = 0.3; cx.lineWidth = 4; cx.strokeText(String(G.score), W / 2, H * 0.42); cx.restore();
  }

  // ------------------------------------------------------------ the first-ribbon moment: an event, not a label
  // 160 ms freeze on the catch, then for 1.5 s: pen rays burst from the kite, a highlighter swipe crosses the whole page, "first ribbon!" is lettered across it
  // letter by letter, the new bow pops onto the tail at three times its size, and the count is circled in pen. Play runs at 35 % speed meanwhile.
  function momentFx(now) {
    const t = (now - fx.at) / FEEL.momentMs; if (t >= 1) { fx = null; G.note = null; return; }
    const e = Math.min(1, t / 0.22), ease = 1 - Math.pow(1 - e, 3), out = t > 0.8 ? 1 - (t - 0.8) / 0.2 : 1;
    cx.save(); cx.globalAlpha = out;
    for (let i = 0; i < 14; i++) { const a = i / 14 * 6.283 + 0.2, r0 = 54 + ease * 14, r1 = r0 + 26 + ease * (i % 2 ? 46 : 78);   // rays
      line([[kx() + Math.cos(a) * r0, G.kiteY + Math.sin(a) * r0], [kx() + Math.cos(a) * r1, G.kiteY + Math.sin(a) * r1]], i % 2 ? C.pen : C.mark, i % 2 ? 2.4 : 5, 1, 1.6); }
    const by = Math.min(H * 0.6, Math.max(ceiling() + 70, G.kiteY - 150)), text = 'first ribbon!';
    cx.font = '700 100px Caveat, cursive'; const fs = Math.min(84, 100 * W * 0.8 / cx.measureText(text).width);   // the lettering takes at most 80 % of the page width
    cx.globalAlpha = 0.9 * out; cx.fillStyle = C.mark; cx.save(); cx.translate(W / 2, by); cx.rotate(-0.05);
    cx.beginPath(); cx.roundRect(-W * 0.5 * ease - 8, -fs * 0.38, W * ease + 16, fs * 0.84, 6); cx.fill();                                        // the swipe
    cx.globalAlpha = out; cx.font = `700 ${fs}px Caveat, cursive`; cx.textAlign = 'center'; cx.textBaseline = 'middle'; cx.fillStyle = C.ink;
    cx.fillText(text.slice(0, Math.ceil(text.length * Math.min(1, t / 0.3))), 0, 0); cx.restore();
    const hb = $('score').getBoundingClientRect();                                                                                                 // the count, circled
    if (hb.width) line(circle(hb.left + hb.width / 2, hb.top + hb.height / 2, Math.max(hb.width, hb.height) * 0.75 + 6, 18).slice(0, Math.ceil(19 * Math.min(1, t / 0.35))), C.kite, 3.4, 2, 2.4);
    cx.restore();
  }

  function draw(now = performance.now()) {
    boil = REDUCED ? 0 : Math.floor(now / FEEL.boilMs);
    cx.setTransform(DPR, 0, 0, DPR, 0, 0);
    if (G.state === 'over') return drawResults(now);
    if (G.state === 'title') return drawTitle(now);
    cx.drawImage(paper, 0, 0, W, H);
    if (shake > 0) cx.translate((hash(now) - 0.5) * shake * 2, (hash(now + 3) - 0.5) * shake * 2);
    if (N()) ghostCount(C);
    ground(C);
    for (const t of things) { if (t.kind === 'gust') gust(C, t.x, t.y, t.w); }
    for (const t of things) { if (t.kind === 'ribbon' && !t.got) ribbon(C, t.x, t.y); if (t.kind === 'gull') gull(C, t.x, t.y, G.time * 9 + t.x * 0.02); }
    trail(C);
    const hand = person(C);
    if (G.state === 'failing') return drawFail(now, hand);
    const blink = invuln > 0 && Math.floor(now / 90) % 2;
    if (!blink) { const tilt = Math.max(-0.4, Math.min(0.4, G.vy / 900)), pop = fx ? 1 + 2 * Math.max(0, 1 - (now - fx.at) / 500) : 1;
      stringTo(C, hand, tieOf(kx(), G.kiteY, 1, tilt)); kite(C, kx(), G.kiteY, 1, tilt, G.score, pop); }
    if (fx) momentFx(now);
  }

  // the instant of failing: the kite nose-down in the ground, an impact burst, the string gone slack, the page shaking; then the log
  function drawFail(now, hand) {
    const t = Math.min(1, (now - G.fail.at) / FEEL.failMs), gy = groundY(kx()), x = kx() + 6, y = gy - 20;
    stringTo(C, hand, [x - 10, y + 6], 60 * t);
    kite(C, x, y, 1, 2.2 + Math.sin(t * 9) * 0.06 * (1 - t), G.score);
    for (let i = 0; i < 9; i++) { const a = -Math.PI * (0.08 + i / 8 * 0.84), r0 = 30 + t * 10, r1 = r0 + 18 + (i % 2 ? 16 : 34) * Math.min(1, t * 3);
      line([[x + Math.cos(a) * r0, gy - 4 + Math.sin(a) * r0], [x + Math.cos(a) * r1, gy - 4 + Math.sin(a) * r1]], C.kite, 3, 1, 1.6); }
    const fs = Math.min(64, W * 0.15); cx.save(); cx.translate(Math.min(W - 90, x + 96), gy - 96); cx.rotate(0.09); cx.font = `700 ${fs}px Caveat, "Space Mono", cursive`; cx.textAlign = 'center';
    cx.fillStyle = C.kite; cx.fillText(G.fail.why === 'Grounded' ? 'thud!' : 'tangled!', 0, 0); cx.restore();
  }

  let titleT0 = performance.now();
  function drawTitle(now) {
    const t = Math.min(1, (now - titleT0) / 900), e = 1 - Math.pow(1 - t, 3);
    if (B()) { cx.drawImage(cover, 0, 0, W, H); }                                             // B: the cover is the title; nothing flies
    else if (N()) {                                                                           // C: the kite is the page
      cx.drawImage(paper, 0, 0, W, H);
      const s = Math.min(W / 150, H / 330) * 1.0, x = W / 2, y = H * 0.3 + (1 - e) * H * 0.2;
      line([[x, y + 30 * s], [x - W * 0.2, H + 20]], C.pen, 1.4, 1, 1); kite(C, x, y, s, -0.12 + Math.sin(now / 700) * 0.04, 6);
    } else {                                                                                  // A: the title reveal: the kite climbs off the flyer's hand to beside the wordmark
      cx.drawImage(paper, 0, 0, W, H);
      const fxp = Math.min(W - 70, Math.max(W * 0.62, 300)); ground(C, false); const hand = person(C, fxp);
      const tx = Math.min(W - 84, W * 0.8), ty = Math.max(ceiling() + 24, H * 0.2), x = hand[0] + (tx - hand[0]) * e, y = hand[1] + (ty - hand[1]) * e, tilt = -0.15 + Math.sin(now / 700) * 0.05;
      stringTo(C, hand, tieOf(x, y, 1.6, tilt)); kite(C, x, y, 1.6, tilt, 2);
    }
    if (t >= 1 && !G.revealed) { G.revealed = true; $('title').dataset.ready = '1'; }
  }

  function drawResults(now) {   // night paper (the person liked design C's night): the whole flight as one chalk line above the log
    cx.drawImage(nightPaper, 0, 0, W, H);
    const P = NIGHT, n = path.length; if (n < 2) return;
    const textTop = $('over').querySelector('.plan').getBoundingClientRect().top;
    const x0 = path[0][0], x1 = path[n - 1][0], pad = 40, top = Math.max(28, H * 0.06), bot = Math.max(top + 50, textTop - 44);
    const ys = path.map((p) => p[1]), ymin = Math.min(...ys), ymax = Math.max(...ys);
    const map = ([wx, y]) => [pad + (wx - x0) / Math.max(1, x1 - x0) * (W - pad * 2), top + (y - ymin) / Math.max(1, ymax - ymin) * (bot - top)];
    const k = Math.min(1, (now - overT0) / 1200), m = Math.max(2, Math.round(n * k));
    const step = Math.max(1, Math.floor(n / 220)); const pts = []; for (let i = 0; i < m; i += step) pts.push(map(path[i]));
    const th = C.theme; C.theme = 'a'; line(pts, P.ink, 2, 2, 1.2);
    for (const r of ribbonsAt) { const [x, y] = map(r); if (r[0] <= path[m - 1][0]) line(circle(x, y, 6, 10), P.mark, 3, 1, 1, true); }
    const [ex, ey] = map(path[m - 1]); line([[ex - 8, ey - 8], [ex + 8, ey + 8]], P.kite, 3); line([[ex + 8, ey - 8], [ex - 8, ey + 8]], P.kite, 3); C.theme = th;
  }

  // ------------------------------------------------------------ the run
  let ribbonsAt = [], overT0 = 0, nightPaper = null;
  function start() {
    rand = rng(seed); things = []; path = []; ribbonsAt = []; worldX = 0; G.score = 0; G.time = 0; G.lives = 3; G.note = null; G.first_ribbon_at = null; G.moment = null; G.fail = null; G.results_drawn = false;
    G.kiteY = H * 0.4; G.vy = 0; G.speed = FEEL.scroll; nextRibbon = 0.05; nextGull = FEEL.gullFrom; nextGust = FEEL.gustFrom; hitStop = 0; invuln = 0; shake = 0; hintT = 0; fx = null; slow = 0;
    G.state = 'playing'; $('title').hidden = true; $('over').hidden = true; $('paused').hidden = true; $('hud').hidden = false; $('hint').hidden = false;
    lives(); $('score').textContent = '0';
    last = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
  }
  function lives() { $('lives').innerHTML = [0, 1, 2].map((i) => `<i class="${i < G.lives ? '' : 'lost'}"></i>`).join(''); }
  function spawn(dt) {
    nextRibbon -= dt; nextGull -= dt; nextGust -= dt;
    if (nextRibbon <= 0) {
      if (!things.some((t) => t.kind === 'ribbon')) {   // the first ribbon: already on screen, on the kite's predicted glide line: the first seconds teach by play
        const ta = FEEL.firstRibbonAhead / G.speed, y = G.kiteY + G.vy * ta + 0.5 * FEEL.gravity * FEEL.firstFlightGravity * ta * ta;
        things.push({ kind: 'ribbon', x: kx() + FEEL.firstRibbonAhead, y }); nextRibbon = 1.4;
      } else { things.push({ kind: 'ribbon', x: W + 30, y: Math.max(ceiling() + 30, Math.min(groundY(W) - 90, H * 0.25 + rand() * H * 0.45)) }); nextRibbon = FEEL.ribbonEvery * (0.8 + rand() * 0.6); }
    }
    if (G.time > FEEL.gullFrom && nextGull <= 0) { things.push({ kind: 'gull', x: W + 40, y: ceiling() + 20 + rand() * H * 0.45, vy: (rand() - 0.5) * 40 }); nextGull = Math.max(0.9, 2.6 - G.time * 0.03) * (0.7 + rand() * 0.6); }
    if (G.time > FEEL.gustFrom && nextGust <= 0) { things.push({ kind: 'gust', x: W + 20, y: ceiling() + 20 + rand() * H * 0.4, w: 180 + rand() * 120, push: (rand() < 0.5 ? -1 : 1) * 420 }); nextGust = 3 + rand() * 2.5; }
  }
  function step(dt) {
    G.time += dt; hintT += dt; if (hintT > 3) $('hint').hidden = true;
    G.speed = FEEL.scroll + G.time * FEEL.scrollGain; worldX += G.speed * dt;
    const ff = FEEL.firstFlightGravity, since = G.first_ribbon_at == null ? (G.time < 6 ? 0 : 9) : G.time - G.first_ribbon_at;
    const gravity = FEEL.gravity * Math.min(1, ff + Math.pow(since / FEEL.weightBackS, 2));   // the first flight hangs on the wind; full weight eases back over 3 s, after the celebration
    G.vy += (holding ? -FEEL.lift : gravity) * dt;
    for (const t of things) if (t.kind === 'gust' && kx() > t.x && kx() < t.x + t.w && Math.abs(G.kiteY - t.y - 12) < 30) G.vy += t.push * dt;
    G.vy = Math.max(-FEEL.maxUp, Math.min(FEEL.maxDown, G.vy)); G.kiteY += G.vy * dt;
    if (G.kiteY < ceiling()) { G.kiteY = ceiling(); G.vy = Math.max(0, G.vy); }
    for (const t of things) { t.x -= G.speed * dt * (t.kind === 'gull' ? 1.25 : 1); if (t.vy) t.y += t.vy * dt; }
    things = things.filter((t) => t.x > -320);
    path.push([worldX, G.kiteY]);
    for (const t of things) {
      const d = Math.hypot(t.x - kx(), t.y - G.kiteY);
      if (t.kind === 'ribbon' && !t.got && d < FEEL.catchR) {
        t.got = true; G.score++; ribbonsAt.push([worldX, G.kiteY]); $('score').textContent = G.score;
        if (G.first_ribbon_at == null) { G.first_ribbon_at = G.time; G.moment = 'first-ribbon'; fx = { at: performance.now() }; G.note = { text: 'first ribbon!', at: fx.at };
          hitStop = FEEL.momentStopMs / 1000; slow = 0.6; G.vy = -FEEL.momentKick; SFX.first(); }   // the catch lifts the kite: it rises through the celebration else SFX.ribbon(G.score);
      }
      if (t.kind === 'gull' && !t.hit && invuln <= 0 && d < FEEL.hitR) {
        t.hit = true; G.lives--; lives(); SFX.hit(); hitStop = FEEL.hitStopMs / 1000; invuln = FEEL.invulnMs / 1000; shake = REDUCED ? 0 : FEEL.shakePx; G.vy = 160;
        if (G.lives <= 0) return fail('Tangled in gulls');
      }
    }
    if (G.kiteY > groundY(kx()) - FEEL.groundPad) return fail('Grounded');
    spawn(dt);
  }
  function fail(why) {   // the instant of failing is its own beat (state 'failing'), then the flight log
    G.state = 'failing'; G.fail = { why, at: performance.now() }; SFX.ground(); shake = REDUCED ? 0 : FEEL.shakePx * 1.6; fx = null; $('hint').hidden = true;
    cancelAnimationFrame(raf);
    (function beat(now) { shake = Math.max(0, shake - 0.5); draw(now); if (now - G.fail.at < FEEL.failMs) raf = requestAnimationFrame(beat); else end(why); })(G.fail.at);
  }
  function end(why) {
    G.state = 'over'; G.moment = 'results'; cancelAnimationFrame(raf);
    G.best = Math.max(G.best, G.score); try { localStorage.setItem('kiteline.best', String(G.best)); } catch {}
    $('hud').hidden = true; $('overTitle').textContent = why; $('final').textContent = G.score; $('final').nextElementSibling.textContent = G.score === 1 ? 'ribbon' : 'ribbons';
    $('overNote').textContent = G.score >= G.best && G.score > 0 ? 'a new best line' : `best: ${G.best}`;
    $('over').hidden = false;   // laid out first, so the stars can keep off the log's lettering
    const box = [...$('over').children].map((el) => el.getBoundingClientRect()).reduce((a, b) => ({ left: Math.min(a.left, b.left), right: Math.max(a.right, b.right), top: Math.min(a.top, b.top), bottom: Math.max(a.bottom, b.bottom) }));
    nightPaper = drawPaper(NIGHT, true, box); overT0 = performance.now();
    (function anim(now) { draw(now); if (now - overT0 < 1300 && G.state === 'over') raf = requestAnimationFrame(anim); else G.results_drawn = true; })(overT0);
  }
  function loop(now) {
    let dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (G.state !== 'playing') return;
    if (hitStop > 0) hitStop -= dt;
    else { if (slow > 0) { slow -= dt; dt *= FEEL.momentSlow; } step(dt); invuln -= dt; }
    shake = Math.max(0, shake - dt * 40);
    if (G.state === 'playing') { draw(now); raf = requestAnimationFrame(loop); }
  }
  function pause(on) {
    if (G.state !== 'playing' && G.state !== 'paused') return;
    G.state = on ? 'paused' : 'playing'; $('paused').hidden = !on; if (on) $('hint').hidden = true;
    if (!on) { last = performance.now(); raf = requestAnimationFrame(loop); }
  }

  // ------------------------------------------------------------ input: one button (hold anywhere, or Space)
  const playing = () => G.state === 'playing';
  addEventListener('pointerdown', (e) => { if (e.target.closest('button, a')) return; if (G.state === 'title' && G.revealed) return start(); if (playing()) { if (!holding) SFX.lift(); holding = true; } });
  addEventListener('pointerup', () => { holding = false; }); addEventListener('pointercancel', () => { holding = false; });
  addEventListener('keydown', (e) => {
    if (e.code === 'Space' || e.code === 'ArrowUp') { e.preventDefault(); if (G.state === 'title' || G.state === 'over') return start(); if (playing()) holding = true; }
    if (e.code === 'Escape' || e.code === 'KeyP') pause(G.state === 'playing');
  });
  addEventListener('keyup', (e) => { if (e.code === 'Space' || e.code === 'ArrowUp') holding = false; });
  const setMute = (m) => { muted = m; $('mute').setAttribute('aria-pressed', String(m)); $('mute').setAttribute('aria-label', m ? 'Sound off' : 'Sound on'); try { localStorage.setItem('kiteline.muted', m ? '1' : '0'); } catch {} };
  setMute(muted); $('mute').onclick = () => setMute(!muted);
  $('fly').onclick = start; $('again').onclick = start; $('pause').onclick = () => pause(true); $('resume').onclick = () => pause(false);
  document.addEventListener('visibilitychange', () => { if (document.hidden) pause(true); });
  addEventListener('resize', resize);

  // ------------------------------------------------------------ boot
  readTheme(); $('bestTitle').textContent = G.best;
  document.fonts.ready.then(() => {
    resize(); titleT0 = performance.now();
    if (location.hash === '#play') {   // a frozen moment of play, the same every time (the design pick's play frame)
      start(); holding = false;   // an autopilot that flies the ribbon line, well clear of the ground and the HUD, and stops before the first gull
      const aim = () => Math.max(ceiling() + 40, Math.min(groundY(kx() + 80) - 130, (things.find((t) => t.kind === 'ribbon' && !t.got && t.x > kx() - 10) || { y: H * 0.4 }).y));
      for (let i = 0; i < 60 * 7.6; i++) { holding = G.kiteY + G.vy * 0.12 > aim(); step(1 / 60); if (G.state !== 'playing') break; }
      cancelAnimationFrame(raf); fx = null; G.note = null; G.frozen = true; draw(performance.now()); $('hint').hidden = true; return;
    }
    (function t(now) { if (G.state === 'title') { draw(now); requestAnimationFrame(t); } })(performance.now());
  });
})();
