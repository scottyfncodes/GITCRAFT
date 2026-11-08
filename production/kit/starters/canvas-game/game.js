// {{TITLE}}: the build work order fills this in. A loop, input, pause, mute, saved best score, and visible errors.
const cv = document.getElementById('game'), cx = cv.getContext('2d');
const S = { state: 'title', paused: false, muted: false, best: Number(localStorage.getItem('{{SLUG}}_best') || 0) };
const errorBox = document.getElementById('error');
addEventListener('error', (e) => { errorBox.textContent = `Something went wrong: ${e.message}`; errorBox.hidden = false; });
function resize() { cv.width = innerWidth * devicePixelRatio; cv.height = innerHeight * devicePixelRatio; }
addEventListener('resize', resize); resize();
function start() { if (S.state !== 'play') { S.state = 'play'; document.getElementById('title').hidden = true; } }
addEventListener('keydown', (e) => { if (e.key === ' ') start(); if (e.key === 'p') S.paused = !S.paused; });
cv.addEventListener('pointerdown', start);
document.getElementById('pause').onclick = () => { S.paused = !S.paused; };
document.getElementById('mute').onclick = (e) => { S.muted = !S.muted; e.target.textContent = S.muted ? 'Sound off' : 'Sound on'; };
document.addEventListener('visibilitychange', () => { if (document.hidden) S.paused = true; });
function frame() { cx.fillStyle = '#14161f'; cx.fillRect(0, 0, cv.width, cv.height); requestAnimationFrame(frame); }
window.game = S;
requestAnimationFrame(frame);
