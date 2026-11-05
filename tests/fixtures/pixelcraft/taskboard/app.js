// Taskboard: a tiny hash-routed task app (PIXELCRAFT's sample application; no framework, no network).
const tasks = [
  { id: 1, title: 'Draft the onboarding copy for the new signup flow', due: 'Today', tag: 'Writing' },
  { id: 2, title: 'Review pull request #42', due: 'Today', tag: 'Code' },
  { id: 3, title: 'Book the team offsite venue', due: 'Tomorrow', tag: 'Ops' },
  { id: 4, title: 'Export Q3 numbers', due: 'Fri', tag: 'Finance' },
];
const projects = [{ name: 'Website relaunch', open: 12 }, { name: 'Mobile app', open: 7 }, { name: 'Hiring', open: 3 }];
const view = document.getElementById('view');
const T = (s) => s.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

function home() {
  view.innerHTML = `
  <section class="summary"><p class="kicker">Thursday</p><h2>4 tasks today</h2><p class="muted">2 overdue, 1 shared with you</p>
    <div class="actions"><button class="btn primary" id="add">Add task</button><button class="btn primary alt" id="plan">Plan my day</button></div></section>
  <form class="quick" onsubmit="event.preventDefault(); add()"><input id="q" placeholder="Quick add…" aria-label="Quick add"><button class="btn small">Add</button></form>
  <ul class="list">${tasks.map((t) => `<li class="task" data-id="${t.id}"><input type="checkbox" class="check" aria-label="Done"><div class="body"><a class="title" href="#/task/${t.id}">${T(t.title)}</a><span class="meta">${t.due} · ${t.tag}</span></div><button class="more" aria-label="More">⋯</button><button class="del" aria-label="Delete" onclick="del(${t.id})">✕</button></li>`).join('')}</ul>
  <button class="fab" aria-label="New task" onclick="add()">+</button>`;
}
function task(id) {
  const t = tasks.find((x) => x.id === +id) || tasks[0];
  view.innerHTML = `<article class="detail"><a href="#/" class="back">‹ Back</a><h2>${T(t.title)}</h2><p class="muted">Due ${t.due} · ${t.tag}</p>
    <label class="field">Notes<textarea rows="4" placeholder="Add notes"></textarea></label>
    <div class="row"><button class="btn primary" onclick="done(${t.id})">Mark done</button><button class="btn ghost" onclick="del(${t.id})">Delete</button><button class="btn ghost tall">Share</button></div></article>`;
}
function projectsView() {
  view.innerHTML = `<section class="projects"><h2>Projects</h2><div class="grid">${projects.map((p) => `<div class="card"><h3>${T(p.name)}</h3><p class="muted">${p.open} open tasks</p><button class="btn small">Open</button></div>`).join('')}</div>
  <table class="wide"><tr><th>Project</th><th>Owner</th><th>Status</th><th>Updated</th></tr>${projects.map((p) => `<tr><td>${T(p.name)}</td><td>Sam Lee</td><td>On track</td><td>2026-11-02</td></tr>`).join('')}</table></section>`;
}
function settings() {
  view.innerHTML = `<section class="settings"><h2>Settings</h2>
  <label class="field">Display name<input value="Sam Lee"></label>
  <label class="toggle"><input type="checkbox" checked> Daily summary email</label>
  <label class="toggle"><input type="checkbox"> Weekend reminders</label>
  <div class="row"><button class="btn primary">Save</button><button class="btn" disabled>Reset</button></div>
  <button class="btn danger" onclick="if (confirm('Sign out?')) location.hash = '#/'">Sign out</button></section>`;
}
function add() { const q = document.getElementById('q'); const v = (q && q.value.trim()) || 'New task'; tasks.unshift({ id: Date.now(), title: v, due: 'Today', tag: 'Inbox' }); render(); }
function del(id) { if (!confirm('Delete this task?')) return; if (!confirm('This cannot be undone. Really delete?')) return; const i = tasks.findIndex((t) => t.id === id); if (i >= 0) tasks.splice(i, 1); location.hash = '#/'; render(); }
function done(id) { del(id); }
function render() {
  const h = location.hash.replace(/^#/, '') || '/';
  const tab = h.startsWith('/projects') ? 'projects' : h.startsWith('/settings') ? 'settings' : 'home';
  document.querySelectorAll('.tab').forEach((a) => a.classList.toggle('active', a.dataset.tab === tab));
  if (h.startsWith('/task/')) task(h.split('/')[2]); else if (tab === 'projects') projectsView(); else if (tab === 'settings') settings(); else home();
  document.title = 'Taskboard';
}
window.addEventListener('hashchange', render); render();
