// KITE LINE: hold to climb into the wind, let go to glide. Collect ribbons, dodge gulls, never touch the ground.
// Everything is drawn as pencil and pen on the page of a notebook; the strokes re-draw ("boil") eight times a second.
(() => {
  'use strict';
  const root = document.documentElement, Q = new URLSearchParams(location.search);
  if (/^[abc]$/.test(Q.get('theme') || '')) root.dataset.theme = Q.get('theme');
  const $ = (id) => document.getElementById(id);
  const cv = $('sky'), cx = cv.getContext('2d');

  // ------------------------------------------------------------ feel: every tuned number in one place (direction.json play.feel)
  const FEEL = { lift: 1350, gravity: 780, firstFlightGravity: 0.1, firstRibbonAhead: 300, maxUp: 360, maxDown: 430, scroll: 200, scrollGain: 3.2, kiteX: 0.36,
                 hitStopMs: 110, invulnMs: 1100, shakePx: 7, boilMs: 125, ribbonEvery: 1.05, gullFrom: 9, gustFrom: 22, groundPad: 18, catchR: 30, hitR: 24 };

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
                hit: () => tone(180, 60, 220, 'square', 0.1), ground: () => tone(220, 50, 520, 'sawtooth', 0.09) };
  const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ------------------------------------------------------------ deterministic randomness (the same seed draws the same flight)
  const seed = parseInt(Q.get('seed') || '7', 10);
  function rng(s) { let a = s >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const hash = (n) => { let x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
  const noise = (x) => { const i = Math.floor(x), f = x - i, s = f * f * (3 - 2 * f); return hash(i) * (1 - s) + hash(i + 1) * s; };

  // ------------------------------------------------------------ theme tokens (CSS custom properties are the source of truth)
  let C = {};
  function readTheme() { const s = getComputedStyle(root); for (const k of ['paper', 'surface', 'ink', 'pen', 'mark', 'kite', 'rule', 'margin', 'muted']) C[k] = s.getPropertyValue('--' + k).trim(); C.theme = root.dataset.theme; }
  const NIGHT = { paper: '#1f232b', ink: '#f1ede4', pen: '#f1ede4', mark: '#f5c04a', kite: '#ff6b5e', rule: '#2c313b', muted: '#b7b2a8' };

  // ------------------------------------------------------------ the page
  let W = 0, H = 0, DPR = 1, paper = null;
  function resize() {
    DPR = Math.min(2, window.devicePixelRatio || 1); W = innerWidth; H = innerHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR); cx.setTransform(DPR, 0, 0, DPR, 0, 0);
    paper = drawPaper(C); if (G.state !== 'playing') draw();
  }
  function drawPaper(P, night, avoid) {
    const o = document.createElement('canvas'); o.width = cv.width; o.height = cv.height; const g = o.getContext('2d'); g.scale(DPR, DPR);
    g.fillStyle = P.paper; g.fillRect(0, 0, W, H);
    const r = rng(11);
    if (!night && C.theme === 'a') {          // ruled lines and the red margin
      g.strokeStyle = P.rule; g.lineWidth = 1.2; for (let y = 96; y < H; y += 34) { g.beginPath(); g.moveTo(0, y + 0.5); g.lineTo(W, y + 0.5); g.stroke(); }
      g.strokeStyle = P.margin; g.lineWidth = 1.6; g.beginPath(); g.moveTo(52.5, 0); g.lineTo(52.5, H); g.stroke();
      g.fillStyle = 'rgba(0,0,0,.05)'; for (const y of [H * 0.2, H * 0.5, H * 0.8]) { g.beginPath(); g.arc(22, y, 9, 0, 7); g.fill(); }
    } else if (!night && C.theme === 'b') {   // graph paper, every fifth line stronger
      for (let i = 0, x = 0; x < W; x += 22, i++) { g.strokeStyle = P.rule; g.globalAlpha = i % 5 ? 0.55 : 1; g.lineWidth = i % 5 ? 0.8 : 1.3; g.beginPath(); g.moveTo(x + 0.5, 0); g.lineTo(x + 0.5, H); g.stroke(); }
      for (let i = 0, y = 0; y < H; y += 22, i++) { g.strokeStyle = P.rule; g.globalAlpha = i % 5 ? 0.55 : 1; g.lineWidth = i % 5 ? 0.8 : 1.3; g.beginPath(); g.moveTo(0, y + 0.5); g.lineTo(W, y + 0.5); g.stroke(); }
      g.globalAlpha = 1;
    } else {                                  // black paper: tooth and a few chalk stars
      for (let i = 0; i < W * H / 260; i++) { g.fillStyle = `rgba(255,255,255,${0.025 + r() * 0.03})`; g.fillRect(r() * W, r() * H, 1, 1); }
      g.strokeStyle = P.ink; g.globalAlpha = 0.55; g.lineWidth = 1.4;
      for (let i = 0; i < 14; i++) { const x = r() * W, y = r() * H * 0.55, s = 3 + r() * 4; if (avoid && x > avoid.left - 18 && x < avoid.right + 18 && y > avoid.top - 18 && y < avoid.bottom + 18) continue; g.beginPath(); g.moveTo(x - s, y); g.lineTo(x + s, y); g.moveTo(x, y - s); g.lineTo(x, y + s); g.stroke(); }
      g.globalAlpha = 1;
    }
    return o;
  }

  // ------------------------------------------------------------ the pencil: every line is drawn twice, slightly off, and boils
  let boil = 0;
  function wob(x, y, k, amt) { return [x + (hash(x * 0.37 + y * 0.11 + k + boil * 13.1) - 0.5) * amt, y + (hash(y * 0.29 - x * 0.17 + k + boil * 7.3) - 0.5) * amt]; }
  function line(pts, color, width, passes = 2, amt = 2.2, closed = false) {
    cx.strokeStyle = color; cx.lineCap = 'round'; cx.lineJoin = 'round';
    for (let p = 0; p < passes; p++) {
      cx.lineWidth = width * (p ? 0.7 : 1); cx.globalAlpha = p ? 0.55 : 1; cx.beginPath();
      pts.forEach(([x, y], i) => { const [a, b] = wob(x, y, p * 3.7 + i * 0.1, amt); i ? cx.lineTo(a, b) : cx.moveTo(a, b); });
      if (closed) cx.closePath(); cx.stroke();
    }
    cx.globalAlpha = 1;
  }
  function hatch(poly, color, gap = 7, angle = -0.9, width = 1.3) {   // scribble fill clipped to a shape
    cx.save(); cx.beginPath(); poly.forEach(([x, y], i) => i ? cx.lineTo(x, y) : cx.moveTo(x, y)); cx.closePath(); cx.clip();
    const xs = poly.map((p) => p[0]), ys = poly.map((p) => p[1]), x0 = Math.min(...xs) - 40, x1 = Math.max(...xs) + 40, y0 = Math.min(...ys) - 40, y1 = Math.max(...ys) + 40;
    cx.strokeStyle = color; cx.lineWidth = width; cx.globalAlpha = 0.85; cx.beginPath();
    const dx = Math.cos(angle), dy = Math.sin(angle), nx = -dy, ny = dx, cxm = (x0 + x1) / 2, cym = (y0 + y1) / 2, R = Math.hypot(x1 - x0, y1 - y0) / 2 + 10;
    for (let t = -R; t < R; t += gap) { const j = (hash(t * 1.7 + boil) - 0.5) * 2.4, ox = cxm + nx * (t + j), oy = cym + ny * (t + j); cx.moveTo(ox - dx * R, oy - dy * R); cx.lineTo(ox + dx * R, oy + dy * R); }
    cx.stroke(); cx.restore(); cx.globalAlpha = 1;
  }
  const circle = (x, y, r, n = 14) => Array.from({ length: n + 1 }, (_, i) => [x + Math.cos(i / n * 6.283) * r, y + Math.sin(i / n * 6.283) * r]);

  // ------------------------------------------------------------ state
  const G = window.__game = { state: 'title', score: 0, time: 0, lives: 3, best: 0, revealed: false, moment: null, note: null, first_ribbon_at: null, kiteY: 0, vy: 0, speed: FEEL.scroll };
  try { G.best = parseInt(localStorage.getItem('kiteline.best') || '0', 10) || 0; } catch {}
  let rand = rng(seed), things = [], path = [], worldX = 0, holding = false, hitStop = 0, invuln = 0, shake = 0, nextRibbon = 0, nextGull = 0, nextGust = 0, last = 0, raf = 0, hintT = 0;
  const kx = () => W * FEEL.kiteX, groundY = (x) => H - 70 - noise((x + worldX) * 0.004) * 60 - noise((x + worldX) * 0.013) * 18;
  const flyer = () => ({ x: Math.max(70, W * 0.1), y: groundY(Math.max(70, W * 0.1)) - 2 });

  // ------------------------------------------------------------ drawing the world
  function hills(P, far = true) {
    const pts = []; for (let x = -10; x <= W + 20; x += 18) pts.push([x, groundY(x)]);
    hatch([...pts, [W + 20, H + 10], [-10, H + 10]], P.rule === '#2c313b' ? '#3a404c' : P.muted, 8, -1.0, 1);
    line(pts, P.ink, 2.2, 2, 1.8);
    if (!far) return;
    const fl = []; for (let x = -10; x <= W + 20; x += 24) fl.push([x, H - 150 - noise((x + worldX * 0.4) * 0.003 + 9) * 90]);
    cx.globalAlpha = 0.5; line(fl, P.muted, 1.4, 1, 1.5); cx.globalAlpha = 1;
  }
  function person(P, at) {
    const fx = at ?? flyer().x, x = fx, y = groundY(fx) - 2;
    line([[x, y - 34], [x, y - 12]], P.ink, 2.4); line(circle(x, y - 42, 7, 10), P.ink, 2.2, 2, 1.4, true);
    line([[x, y - 12], [x - 7, y]], P.ink, 2.2); line([[x, y - 12], [x + 7, y]], P.ink, 2.2);
    line([[x, y - 28], [x + 13, y - 36]], P.ink, 2.2); line([[x, y - 28], [x - 10, y - 20]], P.ink, 2.2);
    return [x + 13, y - 36];
  }
  function kite(P, x, y, s = 1, tilt = 0, bows = 0) {
    const k = (a, b) => [x + (a * Math.cos(tilt) - b * Math.sin(tilt)) * s, y + (a * Math.sin(tilt) + b * Math.cos(tilt)) * s];
    const body = [k(0, -34), k(24, -6), k(0, 38), k(-24, -6)];
    hatch(body, P.kite, 5, -0.7, 2.1);
    line(body, P.ink, 2.6, 2, 2, true); line([k(0, -34), k(0, 38)], P.ink, 1.6, 1); line([k(-24, -6), k(24, -6)], P.ink, 1.6, 1);
    const tail = []; for (let i = 0; i <= 8; i++) tail.push(k(Math.sin(i * 0.9 + G.time * 6) * 9, 38 + i * 12));
    line(tail, P.ink, 1.6, 1, 1.5);
    for (let i = 0; i < Math.min(bows, 8); i++) { const [bx, by] = tail[i + 1]; line([[bx - 8, by - 5], [bx + 8, by + 5], [bx + 8, by - 5], [bx - 8, by + 5], [bx - 8, by - 5]], P.mark, 2.6, 1, 1.2); }
    return k(0, 10);
  }
  const tieOf = (x, y, s, tilt) => [x + (-26 * Math.sin(tilt)) * s, y + 26 * Math.cos(tilt) * s];   // the bridle point, below the cross spar
  function ribbon(P, x, y) {   // a bow with two trailing tails, in the highlighter colour, outlined in pen
    const bow = [[x, y], [x - 14, y - 9], [x - 14, y + 9], [x, y], [x + 14, y - 9], [x + 14, y + 9], [x, y]];
    hatch(bow.slice(0, 4), P.mark, 3, 0.9, 2.4); hatch(bow.slice(3), P.mark, 3, 0.9, 2.4);
    line(bow, P.ink, 1.8, 2, 1.2, true);
    for (const s of [-1, 1]) { const t = []; for (let i = 0; i <= 5; i++) t.push([x + s * (2 + i * 3), y + 4 + i * 4 + Math.sin(i + G.time * 8) * 2]); line(t, P.ink, 1.5, 1, 1); }
  }
  function gull(P, x, y, flap) { const f = Math.sin(flap) * 7; line([[x - 18, y - 4 - f], [x - 8, y - 9 - f * 0.4], [x, y], [x + 8, y - 9 - f * 0.4], [x + 18, y - 4 - f]], P.ink, 2.6, 2, 1.6); }
  function gust(P, x, y, w) { cx.globalAlpha = 0.75; for (let j = 0; j < 3; j++) { const pts = []; for (let i = 0; i <= 10; i++) pts.push([x + i * w / 10, y + j * 12 + Math.sin(i * 0.8 + G.time * 3 + j) * 4]); line(pts, P.muted, 1.6, 1, 1.4); } cx.globalAlpha = 1; }
  function stringTo(P, hand, tie) {
    const mx = (hand[0] + tie[0]) / 2, my = Math.max(hand[1], tie[1]) - Math.abs(tie[0] - hand[0]) * 0.05 + 30;
    const pts = []; for (let i = 0; i <= 16; i++) { const t = i / 16; pts.push([(1 - t) * (1 - t) * hand[0] + 2 * (1 - t) * t * mx + t * t * tie[0], (1 - t) * (1 - t) * hand[1] + 2 * (1 - t) * t * my + t * t * tie[1]]); }
    line(pts, P.pen, 1.4, 1, 1.0);
  }

  function draw(now = performance.now()) {
    boil = REDUCED ? 0 : Math.floor(now / FEEL.boilMs);
    const P = G.state === 'over' ? NIGHT : C;
    cx.setTransform(DPR, 0, 0, DPR, 0, 0);
    if (G.state === 'over') return drawResults(now);
    cx.drawImage(paper, 0, 0, W, H);
    if (shake > 0) cx.translate((hash(now) - 0.5) * shake * 2, (hash(now + 3) - 0.5) * shake * 2);
    if (G.state === 'title' || G.state === 'loading') return drawTitle(now);
    hills(C);
    for (const t of things) { if (t.kind === 'gust') gust(C, t.x, t.y, t.w); }
    for (const t of things) { if (t.kind === 'ribbon' && !t.got) ribbon(C, t.x, t.y); if (t.kind === 'gull') gull(C, t.x, t.y, G.time * 9 + t.x * 0.02); }
    if (path.length > 2) { cx.setLineDash([2, 7]); line(path.slice(-60).map(([wx, y]) => [kx() - (worldX - wx), y]), C.muted, 1.4, 1, 0.6); cx.setLineDash([]); }
    const hand = person(C);
    const blink = invuln > 0 && Math.floor(now / 90) % 2;
    if (!blink) { const tilt = Math.max(-0.4, Math.min(0.4, G.vy / 900)); stringTo(C, hand, tieOf(kx(), G.kiteY, 1, tilt)); kite(C, kx(), G.kiteY, 1, tilt, G.score); }
    if (G.note && now - G.note.at < 1600) {   // the margin note for the first ribbon
      cx.font = `700 28px Caveat, cursive`; cx.fillStyle = C.pen; const nx = kx() + 46, ny = G.kiteY - 40;
      cx.save(); cx.translate(nx, ny); cx.rotate(-0.08); cx.fillText(G.note.text, 0, 0); cx.restore();
      line([[nx - 4, ny + 8], [nx + 128, ny + 4]], C.mark, 5, 1, 1.5);
    }
  }

  let titleT0 = performance.now();
  function drawTitle(now) {
    const t = Math.min(1, (now - titleT0) / 900), e = 1 - Math.pow(1 - t, 3);   // the title reveal: the kite climbs off the hand
    // design A: the flyer stands right of the text column, so the string climbs the right side and the words sit on clean paper
    const a = C.theme === 'a', fx = a ? Math.min(W - 70, Math.max(W * 0.62, 300)) : undefined;
    hills(C, !a); const hand = person(C, fx);
    let tx, ty, s = 1.6;
    if (C.theme === 'a') { tx = Math.min(W - 90, W * 0.78); ty = Math.max(110, H * 0.2); }
    else if (C.theme === 'b') { tx = W * 0.78; ty = Math.max(H * 0.42, 330); s = 1.3; }
    else { tx = W * 0.5; ty = H * 0.28; s = 1.9; }
    const x = hand[0] + (tx - hand[0]) * e, y = hand[1] + (ty - hand[1]) * e;
    if (C.theme === 'b') {   // the flight plan: a dotted course across the page that ends at the kite
      cx.setLineDash([3, 9]); const pts = []; for (let i = 0; i <= 30; i++) { const u = i / 30; pts.push([hand[0] + (tx - hand[0]) * u, hand[1] + (ty - hand[1]) * u - Math.sin(u * Math.PI) * H * 0.18 + Math.sin(u * 9) * 14]); }
      line(pts.slice(0, Math.max(2, Math.round(30 * e))), C.pen, 1.8, 1, 0.8); cx.setLineDash([]);
      cx.font = `400 20px "Patrick Hand"`; cx.fillStyle = C.pen; cx.fillText('wind  →  SW 18', tx - 230, ty + 70);
    }
    const tilt = -0.15 + Math.sin(now / 700) * 0.05; stringTo(C, hand, tieOf(x, y, s, tilt)); kite(C, x, y, s, tilt, C.theme === 'c' ? 5 : 2);
    if (t >= 1 && !G.revealed) { G.revealed = true; $('title').dataset.ready = '1'; }
  }

  function drawResults(now) {   // the results page is night paper (the person liked design C's night): the whole flight as one chalk line
    cx.drawImage(nightPaper, 0, 0, W, H);
    const P = NIGHT, n = path.length; if (n < 2) return;
    // the drawing sits in the band above the log text, measured from the page, on every screen size
    const textTop = $('over').querySelector('.plan').getBoundingClientRect().top;
    const x0 = path[0][0], x1 = path[n - 1][0], pad = 40, top = Math.max(28, H * 0.06), bot = Math.max(top + 50, textTop - 36);
    const ys = path.map((p) => p[1]), ymin = Math.min(...ys), ymax = Math.max(...ys);
    const map = ([wx, y]) => [pad + (wx - x0) / Math.max(1, x1 - x0) * (W - pad * 2), top + (y - ymin) / Math.max(1, ymax - ymin) * (bot - top)];
    const k = Math.min(1, (now - overT0) / 1200), m = Math.max(2, Math.round(n * k));
    const step = Math.max(1, Math.floor(n / 220)); const pts = []; for (let i = 0; i < m; i += step) pts.push(map(path[i]));
    line(pts, P.ink, 2, 2, 1.2);
    for (const r of ribbonsAt) { const [x, y] = map(r); if (r[0] <= path[m - 1][0]) { line(circle(x, y, 6, 10), P.mark, 3, 1, 1, true); } }
    const [ex, ey] = map(path[m - 1]); line([[ex - 8, ey - 8], [ex + 8, ey + 8]], P.kite, 3); line([[ex + 8, ey - 8], [ex - 8, ey + 8]], P.kite, 3);
  }

  // ------------------------------------------------------------ the run
  let ribbonsAt = [], overT0 = 0, nightPaper = null;
  function start() {
    rand = rng(seed); things = []; path = []; ribbonsAt = []; worldX = 0; G.score = 0; G.time = 0; G.lives = 3; G.note = null; G.first_ribbon_at = null; G.moment = null;
    G.kiteY = H * 0.36; G.vy = 0; G.speed = FEEL.scroll; nextRibbon = 0.05; nextGull = FEEL.gullFrom; nextGust = FEEL.gustFrom; hitStop = 0; invuln = 0; shake = 0; hintT = 0;
    G.state = 'playing'; $('title').hidden = true; $('over').hidden = true; $('paused').hidden = true; $('hud').hidden = false; $('hint').hidden = false;
    lives(); $('score').textContent = '0';
    last = performance.now(); cancelAnimationFrame(raf); raf = requestAnimationFrame(loop);
  }
  function lives() { $('lives').innerHTML = [0, 1, 2].map((i) => `<i class="${i < G.lives ? '' : 'lost'}"></i>`).join(''); }
  function spawn(dt) {
    nextRibbon -= dt; nextGull -= dt; nextGust -= dt;
    if (nextRibbon <= 0) {   // the first ribbon always sits on the line the kite will glide along: the first ten seconds teach by play
      const first = !things.some((t) => t.kind === 'ribbon');
      if (first) {   // on screen already, on the kite's predicted glide line, whatever the screen width
        const ta = FEEL.firstRibbonAhead / G.speed, y = G.kiteY + G.vy * ta + 0.5 * FEEL.gravity * FEEL.firstFlightGravity * ta * ta;
        things.push({ kind: 'ribbon', x: kx() + FEEL.firstRibbonAhead, y }); nextRibbon = 1.4;
      } else {
        things.push({ kind: 'ribbon', x: W + 30, y: Math.max(110, Math.min(groundY(W) - 90, H * 0.25 + rand() * H * 0.45)) }); nextRibbon = FEEL.ribbonEvery * (0.8 + rand() * 0.6);
      }
    }
    if (G.time > FEEL.gullFrom && nextGull <= 0) { things.push({ kind: 'gull', x: W + 40, y: 90 + rand() * H * 0.5, vy: (rand() - 0.5) * 40 }); nextGull = Math.max(0.9, 2.6 - G.time * 0.03) * (0.7 + rand() * 0.6); }
    if (G.time > FEEL.gustFrom && nextGust <= 0) { things.push({ kind: 'gust', x: W + 20, y: 90 + rand() * H * 0.45, w: 180 + rand() * 120, push: (rand() < 0.5 ? -1 : 1) * 420 }); nextGust = 3 + rand() * 2.5; }
  }
  function step(dt) {
    G.time += dt; hintT += dt; if (hintT > 3) $('hint').hidden = true;
    G.speed = FEEL.scroll + G.time * FEEL.scrollGain; worldX += G.speed * dt;
    const ff = FEEL.firstFlightGravity, since = G.first_ribbon_at == null ? (G.time < 6 ? 0 : 9) : G.time - G.first_ribbon_at;
    const gravity = FEEL.gravity * Math.min(1, ff + since / 1.5);   // the first flight hangs on the wind; full weight returns over 1.5 s
    G.vy += (holding ? -FEEL.lift : gravity) * dt;
    for (const t of things) if (t.kind === 'gust' && kx() > t.x && kx() < t.x + t.w && Math.abs(G.kiteY - t.y - 12) < 30) G.vy += t.push * dt;
    G.vy = Math.max(-FEEL.maxUp, Math.min(FEEL.maxDown, G.vy)); G.kiteY += G.vy * dt;
    if (G.kiteY < 70) { G.kiteY = 70; G.vy = Math.max(0, G.vy); }
    for (const t of things) { t.x -= G.speed * dt * (t.kind === 'gull' ? 1.25 : 1); if (t.vy) t.y += t.vy * dt; }
    things = things.filter((t) => t.x > -320);
    path.push([worldX, G.kiteY]);
    for (const t of things) {
      const d = Math.hypot(t.x - kx(), t.y - G.kiteY);
      if (t.kind === 'ribbon' && !t.got && d < FEEL.catchR) {
        t.got = true; G.score++; SFX.ribbon(G.score); ribbonsAt.push([worldX, G.kiteY]); $('score').textContent = G.score;
        if (G.first_ribbon_at == null) { G.first_ribbon_at = G.time; G.moment = 'first-ribbon'; G.note = { text: 'first ribbon!', at: performance.now() }; }
      }
      if (t.kind === 'gull' && !t.hit && invuln <= 0 && d < FEEL.hitR) {
        t.hit = true; G.lives--; lives(); SFX.hit(); hitStop = FEEL.hitStopMs / 1000; invuln = FEEL.invulnMs / 1000; shake = REDUCED ? 0 : FEEL.shakePx; G.vy = 160;
        if (G.lives <= 0) return end('Tangled in gulls');
      }
    }
    if (G.kiteY > groundY(kx()) - FEEL.groundPad) { SFX.ground(); return end('Grounded'); }
    spawn(dt);
  }
  function end(why) {
    G.state = 'over'; G.moment = 'results'; cancelAnimationFrame(raf);
    G.best = Math.max(G.best, G.score); try { localStorage.setItem('kiteline.best', String(G.best)); } catch {}
    $('hud').hidden = true; $('hint').hidden = true; $('overTitle').textContent = why; $('final').textContent = G.score; $('final').nextElementSibling.textContent = G.score === 1 ? 'ribbon' : 'ribbons';
    $('overNote').textContent = G.score >= G.best && G.score > 0 ? 'a new best line' : `best: ${G.best}`;
    $('over').hidden = false;   // laid out first, so the stars can keep off the log's text
    const box = [...$('over').children].map((el) => el.getBoundingClientRect()).reduce((a, b) => ({ left: Math.min(a.left, b.left), right: Math.max(a.right, b.right), top: Math.min(a.top, b.top), bottom: Math.max(a.bottom, b.bottom) }));
    nightPaper = drawPaper(NIGHT, true, box); overT0 = performance.now();
    (function anim(now) { draw(now); if (now - overT0 < 1300 && G.state === 'over') raf = requestAnimationFrame(anim); else G.results_drawn = true; })(overT0);
  }
  function loop(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    if (G.state !== 'playing') return;
    if (hitStop > 0) hitStop -= dt; else { step(dt); invuln -= dt; }
    shake = Math.max(0, shake - dt * 40);
    if (G.state === 'playing') { draw(now); raf = requestAnimationFrame(loop); }
  }
  function pause(on) {
    if (G.state !== 'playing' && G.state !== 'paused') return;
    G.state = on ? 'paused' : 'playing'; $('paused').hidden = !on;
    if (!on) { last = performance.now(); raf = requestAnimationFrame(loop); }
  }

  // ------------------------------------------------------------ input: one button (hold anywhere, or Space)
  const playing = () => G.state === 'playing';
  addEventListener('pointerdown', (e) => { if (e.target.closest('button')) return; if (G.state === 'title' && G.revealed) return start(); if (playing()) { if (!holding) SFX.lift(); holding = true; } });
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
    if (location.hash === '#play') {   // a frozen moment of play, the same every time (design renders and the shot list's play frame)
      start(); holding = false; const ribbonY = () => (things.find((t) => t.kind === 'ribbon' && !t.got && t.x > kx() - 10) || { y: H * 0.4 }).y;
      for (let i = 0; i < 60 * 12.6; i++) { holding = G.kiteY > ribbonY(); step(1 / 60); if (G.state !== 'playing') break; }
      cancelAnimationFrame(raf); G.frozen = true; draw(performance.now()); $('hint').hidden = true; return;
    }
    (function t(now) { if (G.state === 'title') { draw(now); requestAnimationFrame(t); } })(performance.now());
  });
})();
