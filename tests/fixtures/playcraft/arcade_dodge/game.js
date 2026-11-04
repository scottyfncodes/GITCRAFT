// BLIP fixture: one-button arcade. Ramp, high score (saved), instant restart, near-miss bonus, particles.
// Deliberate gaps for PLAYCRAFT's tests: no pause, a 28 px mute button.
const cv = document.getElementById('c'), cx = cv.getContext('2d');
let W, H; const resize = () => { W = cv.width = innerWidth; H = cv.height = innerHeight; }; resize(); addEventListener('resize', resize);
const game = window.game = { score: 0, best: +(localStorage.getItem('blip.highScore') || 0), y: 0, vy: 0, speed: 180, alive: true, runs: 1 };
let held = false, walls = [], sparks = [], t0 = 0, paused = false;
const down = () => { held = true; if (!game.alive) restart(); }, up = () => { held = false; };
addEventListener('keydown', (e) => { if (e.code === 'Space' || e.code === 'ArrowUp') down(); });
addEventListener('keyup', (e) => { if (e.code === 'Space' || e.code === 'ArrowUp') up(); });
cv.addEventListener('pointerdown', down); addEventListener('pointerup', up);
document.getElementById('mute').onclick = () => { document.getElementById('mute').classList.toggle('off'); };
function restart() { game.alive = true; game.score = 0; game.speed = 180; game.y = H / 2; game.vy = 0; walls = []; game.runs++; }
function spawn() { const gap = 170, gy = 80 + Math.random() * (H - 160 - gap); walls.push({ x: W + 40, gy, gap, passed: false }); }
game.y = H / 2; let last = performance.now(), since = 0;
function frame(t) {
  const dt = Math.min(0.05, (t - last) / 1000); last = t;
  if (game.alive && !paused) {
    game.speed += dt * 6;   // ramp
    game.vy += (held ? -900 : 700) * dt; game.vy = Math.max(-320, Math.min(420, game.vy)); game.y += game.vy * dt;
    since += dt; if (since > 1.4) { since = 0; spawn(); }
    for (const w of walls) {
      w.x -= game.speed * dt;
      if (!w.passed && w.x < 80) { w.passed = true; const near = Math.min(game.y - w.gy, w.gy + w.gap - game.y) < 18; game.score += near ? 3 : 1;
        for (let i = 0; i < (near ? 16 : 6); i++) sparks.push({ x: 90, y: game.y, vx: Math.random() * 200 - 100, vy: Math.random() * 200 - 100, t: 0.5 }); }
      if (w.x < 96 && w.x > 64 && (game.y < w.gy || game.y > w.gy + w.gap)) game.alive = false;
    }
    if (game.y < 0 || game.y > H) game.alive = false;
    if (!game.alive && game.score > game.best) { game.best = game.score; localStorage.setItem('blip.highScore', game.best); }
    walls = walls.filter((w) => w.x > -60);
  }
  for (const s of sparks) { s.x += s.vx * dt; s.y += s.vy * dt; s.t -= dt; } sparks = sparks.filter((s) => s.t > 0);
  cx.fillStyle = '#20163a'; cx.fillRect(0, 0, W, H);
  cx.fillStyle = '#6ee7b7'; for (const w of walls) { cx.fillRect(w.x, 0, 32, w.gy); cx.fillRect(w.x, w.gy + w.gap, 32, H); }
  cx.fillStyle = game.alive ? '#fbbf24' : '#ef4444'; cx.beginPath(); cx.arc(80, game.y, 14, 0, 7); cx.fill();
  cx.fillStyle = '#fff'; for (const s of sparks) cx.fillRect(s.x, s.y, 3, 3);
  document.getElementById('hud').textContent = `${game.score}  ·  best ${game.best}` + (game.alive ? '' : '  ·  press to restart');
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
