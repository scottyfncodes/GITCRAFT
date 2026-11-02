// GITCRAFT 3D Department UI.
// Live mode (meshcraft/ui_server.py on the department machine): buttons run real pipeline jobs.
// Snapshot mode (static deploy): browse the real assets/jobs captured from a run; actions show
// the exact MCP call or CLI command to run them, because Blender cannot run on a static host.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtB = (n) => (n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : (n / 1024).toFixed(0) + " KB");
const num = (n) => (n ?? 0).toLocaleString();
let S = null; // department state
let LIVE = false;

async function load() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    if (r.ok) { S = await r.json(); LIVE = true; return; }
  } catch {}
  S = await (await fetch("data/state.json", { cache: "no-store" })).json();
}

// ---------------------------------------------------------------- assets helpers
const versions = (a) => Object.keys(a.versions).map(Number).sort((x, y) => x - y);
const md = (a, v) => a.versions[v ?? a.latest];
const url = (m, rel) => (rel ? m.base + rel.split("/").map(encodeURIComponent).join("/") : null);
const allLatest = () => S.assets.map((a) => md(a)).sort((x, y) => (y.provenance?.created || "").localeCompare(x.provenance?.created || ""));
const isChar = (m) => !!m.rig;
const isScene = (m) => m.kind === "scene" || (m.tags || []).includes("blender_scene");

// ---------------------------------------------------------------- viewer
class Viewer {
  constructor(el) {
    this.el = el;
    this.r = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.r.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.r.outputColorSpace = THREE.SRGBColorSpace;
    el.prepend(this.r.domElement);
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xdff4ff, 0x1a3350, 1.7));
    const sun = new THREE.DirectionalLight(0xffffff, 2.4); sun.position.set(6, 10, 7); this.scene.add(sun);
    this.cam = new THREE.PerspectiveCamera(40, 1, 0.05, 5000);
    this.ctl = new OrbitControls(this.cam, this.r.domElement); this.ctl.enableDamping = true; this.ctl.autoRotate = true; this.ctl.autoRotateSpeed = 1.2;
    this.clock = new THREE.Clock(); this.mixer = null; this.clips = [];
    new ResizeObserver(() => this.size()).observe(el); this.size();
    const tick = () => { if (!this.el.isConnected) return this.dispose(); requestAnimationFrame(tick); const d = this.clock.getDelta(); this.mixer?.update(d); this.ctl.update(); this.r.render(this.scene, this.cam); };
    tick();
  }
  size() { const w = this.el.clientWidth, h = this.el.clientHeight || w * 0.75; this.r.setSize(w, h, false); this.cam.aspect = w / h; this.cam.updateProjectionMatrix(); }
  async load(src, onClips) {
    if (this.obj) this.scene.remove(this.obj);
    this.mixer = null;
    const msg = this.el.querySelector(".msg"); if (msg) msg.textContent = "Loading model…";
    try {
      const g = await new GLTFLoader().loadAsync(src);
      this.obj = g.scene; this.scene.add(g.scene);
      const box = new THREE.Box3().setFromObject(g.scene), c = box.getCenter(new THREE.Vector3()), s = box.getSize(new THREE.Vector3()).length() || 1;
      this.ctl.target.copy(c); this.cam.position.copy(c).add(new THREE.Vector3(s * 0.62, s * 0.38, s * 0.72)); this.cam.near = s / 500; this.cam.far = s * 50; this.cam.updateProjectionMatrix();
      this.clips = g.animations;
      if (this.clips.length) { this.mixer = new THREE.AnimationMixer(g.scene); this.play(this.clips.find((c) => /idle|bob/i.test(c.name))?.name || this.clips[0].name); }
      msg?.remove(); onClips?.(this.clips.map((c) => c.name));
    } catch (e) { if (msg) msg.textContent = "Could not load model: " + e; }
  }
  play(name) {
    if (!this.mixer) return; this.mixer.stopAllAction();
    const c = this.clips.find((x) => x.name === name); if (c) this.mixer.clipAction(c).reset().play(); this.current = name;
  }
  dispose() { this.r.dispose(); }
}

function viewerBox(m, { clips = true } = {}) {
  const box = document.createElement("div"); box.className = "viewer";
  box.innerHTML = `<div class="msg">${m.files.glb ? "Loading model…" : "No GLB export for this asset"}</div><div class="hud"></div>`;
  if (m.files.glb) setTimeout(() => {
    const v = new Viewer(box);
    v.load(url(m, m.files.glb.path), (names) => {
      const hud = box.querySelector(".hud");
      const rot = document.createElement("button"); rot.className = "btn small"; rot.textContent = "⟳ spin"; rot.onclick = () => (v.ctl.autoRotate = !v.ctl.autoRotate); hud.append(rot);
      if (clips) for (const n of names) {
        const b = document.createElement("button"); b.className = "btn small"; b.textContent = "▶ " + n;
        b.onclick = () => { v.play(n); hud.querySelectorAll(".clip").forEach((x) => x.classList.remove("primary")); b.classList.add("primary"); };
        b.classList.add("clip"); if (v.current === n) b.classList.add("primary"); hud.append(b);
      }
    });
  });
  return box;
}

// ---------------------------------------------------------------- routing (same rules file as meshcraft/routing.py)
const has = (t, words) => words.some((w) => new RegExp(`(?<![a-z])${w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?![a-z])`).test(t));
function parse(brief, images) {
  const R = S.rules, t = (brief || "").toLowerCase();
  const intents = Object.entries(R.intents).filter(([, v]) => has(t, v.words)).map(([k]) => k).sort();
  let kind = Object.entries(R.kinds).find(([, w]) => has(t, w))?.[0] ?? null;
  if (kind === "boat" && has(t, [...R.kinds.upgrade, "upgrade", "component", "module"])) kind = "upgrade";
  if (kind === "boat" && has(t, R.kinds.salvage)) kind = "salvage";
  if (!kind && intents.includes("character")) kind = "character";
  const params = {};
  if (kind === "upgrade") params.upgrade = Object.entries(R.upgrade_words).find(([, w]) => has(t, w))?.[0] || "cargo_crate";
  if (kind === "prop") params.prop = Object.entries(R.prop_words).find(([, w]) => has(t, w))?.[0] || "barrel";
  if (t.includes("crab")) params.bb_template = "crab";
  return { brief, intents, kind, params, images };
}
function cond(expr, q) {
  return expr.split(" or ").some((cl) => cl.split(" and ").every((a) => {
    a = a.trim(); if (a === "true") return true;
    let m = a.match(/^images>=(\d+)$/); if (m) return q.images >= +m[1];
    if (a.startsWith("intent:")) return q.intents.includes(a.slice(7));
    if (a === "kind:known") return q.kind != null;
    if (a.startsWith("kind:")) return q.kind === a.slice(5);
    return false;
  }));
}
function bbTemplate(q) {
  if (S.bb_templates.includes(q.params.bb_template)) return q.params.bb_template;
  if (q.kind === "boat") return "boat"; if (q.kind === "salvage") return "crate";
  if (q.kind === "prop") return { crate: "crate", chest: "chest", barrel: "crate" }[q.params.prop];
  return S.bb_templates.find((n) => (q.brief || "").toLowerCase().includes(n)) || null;
}
function route(brief, images = 0, prefer = "") {
  const R = S.rules, q = parse(brief, images), be = S.probe.backends;
  const rt = R.routes.find((r) => cond(r.when, q));
  let order = [...rt.tools]; if (prefer && R.tools[prefer]) order = [prefer, ...order.filter((x) => x !== prefer)];
  const cands = order.map((tool) => {
    const spec = R.tools[tool], b = be[spec.backend] || {};
    let ok = !!b.available, why = b.reason || (ok ? spec.compute : `${spec.backend} not installed`);
    if (ok && tool === "blender_procedural" && !spec.kinds.includes(q.kind)) { ok = false; why = `no procedural template for '${q.kind || "this description"}'`; }
    if (ok && tool === "blockbench" && !bbTemplate(q)) { ok = false; why = "no Blockbench template for this kind of object"; }
    if (ok && tool === "triposr" && q.images < 1) { ok = false; why = "TripoSR needs a reference image"; }
    if (ok && tool === "meshroom" && q.images < 3) { ok = false; why = "photogrammetry needs several overlapping photos (≥8 recommended)"; }
    if (ok) why = spec.compute;
    return { tool, label: spec.label, ok, why };
  });
  const chosen = cands.find((c) => c.ok);
  return { q, rt, cands, chosen, fallback: chosen && chosen.tool !== order[0] };
}
function routeHtml(p) {
  return `<div class="route"><b>${esc(p.rt.id.replace("_", " "))}</b> · ${esc(p.rt.why)}</div>
  <div>${p.cands.map((c) => `<div class="cand ${p.chosen?.tool === c.tool ? "chosen" : ""}"><span class="dot ${c.ok ? "y" : ""}"></span><div><b>${esc(c.label)}</b>${p.chosen?.tool === c.tool ? ' <span class="pill done">chosen</span>' : ""}<small>${esc(c.why)}</small></div></div>`).join("")}</div>
  ${p.chosen ? (p.fallback ? `<div class="note">Preferred tool unavailable here; falling back to <b>${esc(p.chosen.label)}</b>.</div>` : "")
    : `<div class="note"><b>Nothing here can honour this request.</b> MeshCraft will not substitute a 2D image or an unrelated model. Enable one of the tools above (reasons listed) or change the request.</div>`}`;
}

// ---------------------------------------------------------------- actions (live: run; snapshot: show how)
async function act(kind, payload, label) {
  if (LIVE) {
    const r = await fetch("/api/" + kind, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) });
    const j = await r.json();
    if (!r.ok) return dialog(`<h2>${esc(label)}</h2><p class="err">${esc(j.error || r.statusText)}</p>`);
    dialog(`<h2>${esc(label)}: started</h2><p>Job <code>${esc(j.job)}</code> is running. Follow it in the Pipeline Monitor.</p>`);
    location.hash = "#monitor/" + j.job; return;
  }
  const tool = { generate: "generate", compose: "compose_scene", retry: "job_retry" }[kind];
  const cli = kind === "retry" ? `python3 meshcraft/cli.py retry ${payload.job}` : `python3 meshcraft/cli.py ${kind} '${JSON.stringify(payload)}'`;
  dialog(`<h2>${esc(label)}</h2>
  <p>This page is a <b>snapshot</b> hosted on a static server, which cannot run Blender. To run this for real, use the department machine:</p>
  <h3>From Claude Code (MCP)</h3><pre>meshcraft · ${tool}\n${esc(JSON.stringify(payload, null, 1))}</pre>
  <h3>From a terminal</h3><pre>${esc(cli)}</pre>
  <h3>Or run this UI live</h3><pre>python3 meshcraft/ui_server.py   # http://127.0.0.1:8765</pre>`);
}
function dialog(html) { $("#dlgBody").innerHTML = html; $("#dlg").showModal(); }

// ---------------------------------------------------------------- shared bits
function card(m, sel) {
  return `<button class="card ${sel ? "on" : ""}" data-asset="${esc(m.id)}"><img loading="lazy" alt="" src="${esc(url(m, m.previews.thumbnail) || "")}">
  <div><b>${esc(m.name)}</b><small>${esc(m.kind || "asset")} · ${num(m.geometry.triangles)} tris · v${m.version}</small><br><span class="pill ${esc(m.validation.status)}">${esc(m.validation.status)}</span></div></button>`;
}
function bindCards(root, fn) { root.querySelectorAll("[data-asset]").forEach((b) => (b.onclick = () => fn(b.dataset.asset))); }
const COLORS = ["coral", "crimson", "gold", "lagoon", "sea", "midnight", "palm", "dusk", "cream", "timber", "black"];

// ---------------------------------------------------------------- pages
const pages = {};

pages.factory = (main) => {
  const items = allLatest().filter((m) => !isScene(m));
  main.innerHTML = `<div class="hero"><div><h1>3D Asset Factory</h1><p>Describe an object or add reference images. The router picks the best tool available on this machine, explains why, and falls back when a tool is missing. It never substitutes a 2D image.</p></div></div>
  <div class="grid2"><section class="panel"><h2>New asset</h2>
    <label for="brief">Brief</label><textarea id="brief" placeholder="e.g. stylized low-poly boat with a red hull">stylized low-poly boat with a red hull</textarea>
    <div class="chips" id="ex">${["stylized low-poly boat with a red hull", "detailed ship from concept art", "object from photograph", "animated human pirate character", "reconstructed real-world environment", "blocky voxel treasure chest", "floating salvage debris", "small tropical island", "complete game-ready scene"].map((x) => `<span class="chip">${x}</span>`).join("")}</div>
    <div class="row"><div><label for="imgs">Reference images</label><input id="imgs" type="file" accept="image/*" multiple ${LIVE ? "" : 'title="Uploads need the live department server"'}></div>
      <div><label for="nimg">…or count (planning)</label><input id="nimg" type="number" min="0" value="0"></div>
      <div><label for="tool">Tool</label><select id="tool"><option value="">Automatic</option>${Object.entries(S.rules.tools).filter(([k]) => !["import", "mixamo"].includes(k)).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join("")}</select></div></div>
    <div class="row"><div><label for="nm">Asset name</label><input id="nm" placeholder="optional"></div><div><label for="tris">Triangle budget</label><input id="tris" type="number" value="20000"></div><div><label for="bake">Texture bake</label><select id="bake"><option>1024</option><option>2048</option><option>512</option><option value="0">none</option></select></div></div>
    <div class="row" style="margin-top:14px"><button class="btn primary" id="go">Generate 3D asset</button></div>
    <h3 style="margin-top:18px">Routing plan</h3><div id="plan"></div>
  </section>
  <section class="panel"><h2>Generated assets</h2><p class="note" style="margin-top:0">Click to inspect. Regenerate from the Library to create a new version.</p><div class="cards" id="recent">${items.map((m) => card(m)).join("")}</div></section></div>`;
  const plan = () => { const n = Math.max(+$("#nimg").value || 0, $("#imgs").files.length); $("#plan").innerHTML = routeHtml(route($("#brief").value, n, $("#tool").value)); };
  ["#brief", "#nimg", "#tool", "#imgs"].forEach((s) => $(s).addEventListener("input", plan)); $("#imgs").addEventListener("change", plan);
  $("#ex").querySelectorAll(".chip").forEach((c) => (c.onclick = () => { $("#brief").value = c.textContent; $("#nimg").value = /photograph|concept/.test(c.textContent) ? 1 : /reconstructed/.test(c.textContent) ? 24 : 0; plan(); }));
  plan();
  bindCards(main, (id) => (location.hash = "#library/" + id));
  $("#go").onclick = async () => {
    const p = route($("#brief").value, Math.max(+$("#nimg").value || 0, $("#imgs").files.length), $("#tool").value);
    if (!p.chosen) return dialog(`<h2>Can't generate this here</h2>${routeHtml(p)}`);
    const images = LIVE ? await Promise.all([...$("#imgs").files].map((f) => new Promise((ok) => { const r = new FileReader(); r.onload = () => ok({ name: f.name, data: r.result }); r.readAsDataURL(f); }))) : undefined;
    act("generate", { brief: $("#brief").value, name: $("#nm").value || undefined, tool: $("#tool").value || undefined, max_tris: +$("#tris").value, bake: +$("#bake").value, ...(images?.length ? { uploads: images } : {}) }, "Generate 3D asset");
  };
};

pages.characters = (main, arg) => {
  const chars = allLatest().filter(isChar);
  const sel = chars.find((m) => m.id === arg) || chars[0];
  main.innerHTML = `<div class="hero"><div><h1>3D Character Studio</h1><p>Characters are built and rigged in Blender on a 22-bone skeleton that uses Mixamo's bone names, so clips downloaded from mixamo.com apply by name. Each clip exports as its own glTF animation.</p></div></div>
  <div class="grid2"><section class="panel">${sel ? `<h2>${esc(sel.name)} <span class="pill kind">v${sel.version}</span></h2><div id="cv"></div>
    <dl class="kv" style="margin-top:12px"><dt>Rig</dt><dd>${sel.rig.bones} bones · ${esc(sel.rig.convention || "")} naming</dd><dt>Clips</dt><dd>${sel.animations.map((a) => `${esc(a.name)} <small>(${a.seconds}s${a.loop ? ", loop" : ""})</small>`).join(" · ")}</dd>
    <dt>Geometry</dt><dd>${num(sel.geometry.triangles)} triangles · ${sel.geometry.dimensions_m.join(" × ")} m</dd><dt>Source</dt><dd>${esc(sel.source_tool)}</dd></dl>
    <details style="margin-top:10px"><summary>Bones</summary><p><small>${sel.rig.bone_names.map(esc).join(", ")}</small></p></details>` : "<p>No characters yet.</p>"}
    <h3 style="margin-top:16px">All characters</h3><div class="cards">${chars.map((m) => card(m, m === sel)).join("")}</div></section>
  <section><div class="panel"><h2>Create a character</h2>
    <div class="row"><div><label for="cn">Name</label><input id="cn" value="Deckhand"></div><div><label for="cb">Bandana</label><select id="cb">${COLORS.map((c) => `<option ${c === "coral" ? "selected" : ""}>${c}</option>`).join("")}</select></div>
    <div><label for="cvst">Vest</label><select id="cvst">${COLORS.map((c) => `<option ${c === "crimson" ? "selected" : ""}>${c}</option>`).join("")}</select></div><div><label for="cp">Trousers</label><select id="cp">${COLORS.map((c) => `<option ${c === "midnight" ? "selected" : ""}>${c}</option>`).join("")}</select></div></div>
    <label><input type="checkbox" id="cw" checked> Cutlass in right hand</label>
    <label>Clips</label><div class="chips" id="clips">${["Idle", "Walk", "Run", "Jump", "Interact", "Attack"].map((c) => `<span class="chip on">${c}</span>`).join("")}</div>
    <button class="btn primary" id="mk">Create, rig and animate</button></div>
  <div class="panel"><h2>Mixamo animations</h2><p class="note" style="margin-top:0">Mixamo has no public API, so MeshCraft never contacts mixamo.com. A person signs in (free Adobe ID), uploads and downloads. MeshCraft prepares the upload and merges the downloads.</p>
    <ol>${S.mixamo.steps.map((s) => `<li>${esc(s.replace(/^\d+\.\s*/, ""))}</li>`).join("")}</ol>
    ${sel ? `<div class="row"><button class="btn" id="mxu">Prepare Mixamo upload (FBX)</button><button class="btn" id="mxa">Apply downloaded clips…</button></div>` : ""}</div></section></div>`;
  if (sel) $("#cv").append(viewerBox(sel));
  bindCards(main, (id) => (location.hash = "#characters/" + id));
  $("#clips").querySelectorAll(".chip").forEach((c) => (c.onclick = () => c.classList.toggle("on")));
  $("#mk").onclick = () => act("generate", { brief: `animated pirate character ${$("#cn").value}`, name: $("#cn").value, kind: "character", tool: "blender_character",
    params: { colors: { bandana: $("#cb").value, vest: $("#cvst").value, pants: $("#cp").value }, weapon: $("#cw").checked },
    clips: [...$("#clips").querySelectorAll(".chip.on")].map((c) => c.textContent) }, "Create character");
  if (sel) {
    $("#mxu").onclick = () => LIVE ? act("mixamo_prepare", { asset: sel.id }, "Prepare Mixamo upload") : dialog(`<h2>Prepare Mixamo upload</h2><pre>meshcraft · mixamo_prepare_upload\n{"asset": "${esc(sel.id)}", "out": "&lt;workspace&gt;/${esc(sel.slug)}_mixamo_upload.fbx"}</pre>`);
    $("#mxa").onclick = () => dialog(`<h2>Apply Mixamo clips</h2><p>Put the downloaded FBX files inside a GITCRAFT root, then:</p><pre>meshcraft · mixamo_apply\n{"character": "${esc(sel.id)}", "animations": ["&lt;root&gt;/mixamo/Walking.fbx", "&lt;root&gt;/mixamo/Jump.fbx"]}</pre><p>Clips are matched on the ${sel.rig.bones} <code>mixamorig:*</code> bones and added as version ${sel.version + 1}.</p>`);
  }
};

pages.world = (main) => {
  const scenes = allLatest().filter(isScene), env = allLatest().filter((m) => ["island", "lighthouse"].includes(m.kind));
  const parts = allLatest().filter((m) => !isScene(m));
  main.innerHTML = `<div class="hero"><div><h1>3D World Builder</h1><p>Terrain, structures and full scenes. Scenes are assembled in Blender from library GLBs, including attaching upgrades to a boat's sockets. They get an ocean, a sun and sky, and a hero render, then export as one scene GLB plus a .blend file.</p></div></div>
  ${scenes.map((m) => `<section class="panel"><h2>${esc(m.name)} <span class="pill ${esc(m.validation.status)}">${esc(m.validation.status)}</span></h2>
    <div class="grid2"><img class="scene-hero" alt="Hero render of ${esc(m.name)}" src="${esc(url(m, m.previews.hero || m.previews.thumbnail))}"><div><div data-sv="${esc(m.id)}"></div>
    <dl class="kv" style="margin-top:10px"><dt>Placed assets</dt><dd>${(m.generation.items || []).map((i) => esc(i.name)).join(", ")}</dd><dt>Triangles</dt><dd>${num(m.geometry.triangles)}</dd><dt>Animations</dt><dd>${m.animations.map((a) => esc(a.name)).join(", ") || "none"}</dd></dl>
    <p><a class="btn small" href="#library/${esc(m.id)}">Inspect / download</a></p></div></div></section>`).join("")}
  <div class="grid2" style="margin-top:18px"><section class="panel"><h2>Terrain &amp; structures</h2>
    <div class="row"><div><label for="isz">Island size</label><select id="isz"><option value="15">small</option><option value="22" selected>medium</option><option value="30">large</option></select></div>
    <div><label for="ipm">Palms</label><input id="ipm" type="number" value="7" min="0" max="20"></div><div><label for="isd">Seed</label><input id="isd" type="number" value="7"></div></div>
    <div class="row" style="margin-top:12px"><button class="btn primary" id="mki">Generate island terrain</button><button class="btn" id="mkl">Generate lighthouse</button></div>
    <h3 style="margin-top:16px">Environment assets</h3><div class="cards">${env.map((m) => card(m)).join("")}</div></section>
  <section class="panel"><h2>Compose a scene</h2><p class="note" style="margin-top:0">Pick library assets. Upgrades attach to the first boat's matching socket; the rest are spaced along the shore.</p>
    <div class="chips" id="pick">${parts.map((m) => `<span class="chip ${["island", "boat"].includes(m.kind) ? "on" : ""}" data-id="${esc(m.id)}" data-kind="${esc(m.kind)}">${esc(m.name)}</span>`).join("")}</div>
    <h3>Lighting &amp; atmosphere</h3><div class="row"><div><label for="sun">Sun elevation (°)</label><input id="sun" type="range" min="5" max="85" value="48"></div><div><label for="sky">Sky</label><select id="sky"><option value="sky">Day</option><option value="#ffb27a">Golden hour</option><option value="#3b2350">Dusk</option></select></div></div>
    <div class="row"><div><label for="snm">Scene name</label><input id="snm" value="New Scene"></div></div>
    <button class="btn primary" id="cmp" style="margin-top:12px">Compose scene</button></section></div>`;
  main.querySelectorAll("[data-sv]").forEach((el) => el.append(viewerBox(S.assets.map((a) => md(a)).find((m) => m.id === el.dataset.sv), { clips: false })));
  bindCards(main, (id) => (location.hash = "#library/" + id));
  $("#pick").querySelectorAll(".chip").forEach((c) => (c.onclick = () => c.classList.toggle("on")));
  $("#mki").onclick = () => act("generate", { brief: "tropical island terrain", kind: "island", tool: "blender_procedural", name: "Island " + $("#isd").value, params: { radius: +$("#isz").value, palms: +$("#ipm").value, seed: +$("#isd").value }, bake: 2048, max_tris: 40000 }, "Generate island");
  $("#mkl").onclick = () => act("generate", { brief: "lighthouse on a rock", kind: "lighthouse", tool: "blender_procedural", name: "Lighthouse" }, "Generate lighthouse");
  $("#cmp").onclick = () => {
    const chosen = [...$("#pick").querySelectorAll(".chip.on")].map((c) => ({ id: c.dataset.id, kind: c.dataset.kind }));
    const SOCK = { sail_canvas: "socket_sail", cargo_crate: "socket_storage", compass_brass: "socket_navigation", rudder_ash: "socket_steering", hull_copper: "socket_hull" };
    const boat = chosen.find((c) => c.kind === "boat"); let x = -12;
    const items = chosen.map((c, i) => {
      const m = md(S.assets.find((a) => a.id === c.id));
      if (c.kind === "island") return { asset: c.id, name: "island" };
      if (c.kind === "boat" && c === boat) return { asset: c.id, name: "boat", location: [9, -27, 0.15], rotation: [0, 0, 28] };
      if (c.kind === "upgrade" && boat) return { asset: c.id, name: "upg" + i, attach_to: "boat:" + (SOCK[m.generation.params?.upgrade] || "socket_storage") };
      return { asset: c.id, name: "item" + i, location: [(x += 4), -30, 0] };
    });
    act("compose", { name: $("#snm").value, items, sun: [+$("#sun").value, 8, 140], sky: $("#sky").value }, "Compose scene");
  };
};

pages.library = (main, arg, ver) => {
  const all = allLatest();
  const kinds = [...new Set(all.map((m) => m.kind).filter(Boolean))].sort();
  main.innerHTML = `<div class="hero"><div><h1>3D Asset Library</h1><p>Every asset has an ID, versions, polygon and texture stats, rig and animation data, licence and provenance, validation results and downloadable exports.</p></div></div>
  <div class="stat"><div><b>${all.length}</b><span>assets</span></div><div><b>${S.assets.reduce((n, a) => n + versions(a).length, 0)}</b><span>versions</span></div>
  <div><b>${num(all.reduce((n, m) => n + (m.geometry.triangles || 0), 0))}</b><span>triangles</span></div><div><b>${all.filter((m) => /passed/.test(m.validation.status)).length}/${all.length}</b><span>validated</span></div></div>
  <div class="grid2"><section class="panel"><div class="row"><div style="flex:3 1 200px"><label for="q">Search</label><input id="q" placeholder="name, kind, tool, brief…"></div>
    <div><label for="fk">Kind</label><select id="fk"><option value="">all</option>${kinds.map((k) => `<option>${k}</option>`).join("")}</select></div></div>
    <div class="cards" id="grid" style="margin-top:14px"></div></section><section class="panel" id="detail"></section></div>`;
  const draw = () => {
    const q = $("#q").value.toLowerCase().split(/\s+/).filter(Boolean), k = $("#fk").value;
    const res = all.filter((m) => (!k || m.kind === k) && q.every((w) => [m.id, m.name, m.kind, m.source_tool, m.brief, ...(m.tags || [])].join(" ").toLowerCase().includes(w)));
    $("#grid").innerHTML = res.map((m) => card(m, m.id === arg)).join("") || "<p>No matches.</p>";
    bindCards($("#grid"), (id) => (location.hash = "#library/" + id));
  };
  $("#q").oninput = draw; $("#fk").onchange = draw; draw();
  const a = S.assets.find((x) => x.id === arg) || S.assets.find((x) => x.id === all[0]?.id);
  if (!a) return ($("#detail").innerHTML = "<p>The library is empty.</p>");
  const m = md(a, ver ? +ver : undefined);
  const d = $("#detail");
  d.innerHTML = `<h2>${esc(m.name)}</h2><div class="chips"><span class="pill kind">${esc(m.kind || "asset")}</span><span class="pill ${esc(m.validation.status)}">${esc(m.validation.status)}</span><span class="pill kind">${esc(m.id)}</span>
    ${versions(a).map((v) => `<a class="chip ${v === m.version ? "on" : ""}" href="#library/${esc(a.id)}/${v}">v${v}</a>`).join("")}</div><div id="dv"></div>
    <div class="subtabs">${["overview", "files", "provenance", "validation"].map((t, i) => `<button class="btn small ${i ? "" : "primary"}" data-st="${t}">${t}</button>`).join("")}<button class="btn small" id="regen">Regenerate (new version)</button></div><div id="st"></div>`;
  $("#dv").append(viewerBox(m));
  const tabs = {
    overview: () => `<dl class="kv"><dt>Brief</dt><dd>${esc(m.brief)}</dd><dt>Source tool</dt><dd>${esc(m.source_tool)}</dd><dt>Routing</dt><dd>${esc(m.route?.chosen || "")}${m.route?.fallback_used ? " (fallback)" : ""}: ${esc(m.route?.explanation || "")}</dd>
      <dt>Triangles</dt><dd>${num(m.geometry.triangles)} (${num(m.geometry.vertices)} vertices)</dd><dt>Size</dt><dd>${(m.geometry.dimensions_m || []).join(" × ")} m (Blender X×Y×Z; glTF is Y-up, forward +Z)</dd>
      <dt>Materials</dt><dd>${m.materials.map(esc).join(", ")}</dd><dt>Textures</dt><dd>${m.textures.map((t) => `${esc(t.name)} ${t.size.join("×")} (${esc(t.colorspace)})`).join("<br>") || "none"}</dd>
      <dt>Rig</dt><dd>${m.rig ? `${m.rig.bones} bones (${esc(m.rig.convention)})` : "none"}</dd><dt>Animations</dt><dd>${m.animations.map((x) => `${esc(x.name)} ${x.seconds}s`).join(", ") || "none"}</dd>
      <dt>Sockets</dt><dd>${m.sockets.map((s) => esc(s.name)).join(", ") || "none"}</dd><dt>Generation</dt><dd><pre>${esc(JSON.stringify(m.generation, null, 1))}</pre></dd></dl>
      ${m.previews.turntable?.length ? `<h3>Turntable</h3><div class="turn">${m.previews.turntable.map((p) => `<img loading="lazy" alt="" src="${esc(url(m, p))}">`).join("")}</div>` : ""}`,
    files: () => `<div class="files">${Object.entries(m.files).map(([f, v]) => `<a href="${esc(url(m, v.path))}" download><b>${esc(f)}</b><small>${fmtB(v.bytes)}</small></a>`).join("")}
      <a href="${esc(m.base)}asset.json" download><b>asset.json</b><small>metadata</small></a></div>
      <p class="note">Multi-file formats (glTF + .bin, OBJ + .mtl) also ship their companion files: ${m.companion_files.map(esc).join(", ")}</p>
      <h3>SHA-256</h3><pre>${Object.entries(m.files).map(([f, v]) => `${f.padEnd(8)} ${v.sha256}`).join("\n")}</pre>`,
    provenance: () => `<dl class="kv"><dt>Created</dt><dd>${esc(m.provenance.created)}</dd><dt>Job</dt><dd><a href="#monitor/${esc(m.job)}">${esc(m.job)}</a></dd><dt>Blender</dt><dd>${esc(m.provenance.blender)}</dd>
      <dt>Inputs</dt><dd><pre>${esc(JSON.stringify(m.provenance.inputs, null, 1))}</pre></dd><dt>Licence</dt><dd>${esc(m.license.asset)}${m.license.ai_generated ? " · <b>AI-generated</b>" : ""}<br>${m.license.tools.map((t) => `<small>${esc(t.tool)}: ${esc(t.license)}</small>`).join("<br>")}</dd>
      <dt>Pipeline</dt><dd>${m.stages.map((s) => `<span class="stg ${esc(s.state)}">${esc(s.stage)} ${s.seconds ?? ""}s</span>`).join(" ")}</dd></dl>`,
    validation: () => `<pre>${esc(JSON.stringify(m.validation, null, 1))}</pre>`,
  };
  const show = (t) => { $("#st").innerHTML = tabs[t](); d.querySelectorAll("[data-st]").forEach((b) => b.classList.toggle("primary", b.dataset.st === t)); };
  d.querySelectorAll("[data-st]").forEach((b) => (b.onclick = () => show(b.dataset.st))); show("overview");
  $("#regen").onclick = () => act("generate", { brief: m.brief, name: m.name, asset_id: m.id, kind: m.kind, params: m.generation.params, tool: m.route?.chosen }, "Regenerate " + m.name);
};

pages.monitor = (main, arg) => {
  const jobs = S.jobs, j = jobs.find((x) => x.id === arg) || jobs[0];
  const pb = S.probe;
  main.innerHTML = `<div class="hero"><div><h1>Pipeline Monitor</h1><p>Every job's routing decision, stage-by-stage timing, errors, retries and the compute it needs. Failed Blender stages retry automatically with lighter settings; blocked jobs explain what is missing.</p></div></div>
  <div class="stat"><div><b>${jobs.filter((x) => x.status === "done").length}</b><span>done</span></div><div><b>${jobs.filter((x) => x.status === "running" || x.status === "queued").length}</b><span>running</span></div>
  <div><b>${jobs.filter((x) => x.status === "failed").length}</b><span>failed</span></div><div><b>${jobs.filter((x) => x.status === "blocked").length}</b><span>blocked (tool unavailable)</span></div></div>
  <div class="grid2"><section class="panel" style="overflow:auto"><table class="jobs"><thead><tr><th>Status</th><th>Job</th><th class="hide-s">Tool</th><th class="hide-s">Stages</th></tr></thead><tbody>
    ${jobs.map((x) => `<tr class="${x === j ? "sel" : ""}" data-job="${esc(x.id)}" style="cursor:pointer"><td><span class="pill ${esc(x.status)}">${esc(x.status)}</span></td><td><b>${esc(x.spec?.name || x.spec?.brief || x.id)}</b><br><small>${esc(x.id)}</small></td>
    <td class="hide-s">${esc(x.plan?.chosen || x.spec?.tool || "")}</td><td class="hide-s"><div class="stages">${x.stages.filter((s) => s.attempt === x.attempts.length - 1).map((s) => `<span class="stg ${esc(s.state)}">${esc(s.stage.replace("blender:", ""))}</span>`).join("")}</div></td></tr>`).join("")}
  </tbody></table></section><section class="panel" id="jd"></section></div>
  <h2 style="margin-top:24px">Compute &amp; backends</h2>
  <div class="hw"><div class="panel"><h3>Machine</h3><dl class="kv"><dt>CPU</dt><dd>${pb.hardware.cpu_threads} threads</dd><dt>RAM</dt><dd>${pb.hardware.ram.total_gb} GB</dd><dt>GPU</dt><dd>${pb.hardware.gpus.map((g) => `${esc(g.name)} ${g.vram_gb} GB`).join(", ") || "none (CPU only)"}</dd>
    <dt>Network</dt><dd>${pb.hardware.network.allowed_by_gitcraft ? "allowed" : "denied to tools (GITCRAFT sandbox)"}</dd><dt>Limits</dt><dd>${pb.limits.max_concurrent_heavy_jobs} heavy job at a time · bake ≤ ${pb.limits.max_bake_resolution}px · ≤ ${num(pb.limits.max_triangles)} tris</dd></dl></div>
    ${Object.entries(pb.backends).map(([k, b]) => `<div class="panel"><h3>${esc(k)} <span class="pill ${b.available ? "available" : "unavailable"}">${b.available ? "available" : "unavailable"}</span></h3><p style="margin:0;font-size:13.5px">${esc(b.version || b.mode || "")}</p><p class="note">${esc(b.reason || b.note || "")}</p></div>`).join("")}</div>`;
  main.querySelectorAll("[data-job]").forEach((r) => (r.onclick = () => (location.hash = "#monitor/" + r.dataset.job)));
  if (!j) return ($("#jd").innerHTML = "<p>No jobs yet.</p>");
  const att = j.attempts.length - 1, st = j.stages.filter((s) => s.attempt === att), mx = Math.max(1, ...st.map((s) => s.seconds || 0));
  const secs = (s) => s.seconds ?? (s.started && s.finished ? (Date.parse(s.finished) - Date.parse(s.started)) / 1000 : 0);
  $("#jd").innerHTML = `<h2>${esc(j.spec?.name || j.spec?.brief || j.id)}</h2><div class="chips"><span class="pill ${esc(j.status)}">${esc(j.status)}</span><span class="pill kind">${j.attempts.length} attempt${j.attempts.length > 1 ? "s" : ""}</span>${j.asset ? `<a class="chip" href="#library/${esc(j.asset.id)}">asset ${esc(j.asset.id)} v${j.asset.version}</a>` : ""}</div>
    ${j.error ? `<p class="err">${esc(j.error)}</p>` : ""}
    ${j.plan ? `<h3>Routing</h3><p style="font-size:13.5px">${esc(j.plan.explanation)}</p>` : ""}
    <h3>Stages (attempt ${att + 1})</h3><div class="timeline">${st.map((s) => { const v = secs(s); return `<div class="tl ${esc(s.state)}"><span>${esc(s.stage)} <span class="pill ${esc(s.state)}">${esc(s.state)}</span></span><div><div class="bar" style="width:${Math.max(1, (100 * v) / Math.max(mx, ...st.map(secs)))}%"></div>${s.error ? `<div class="err">${esc(s.error)}</div>` : ""}</div><small>${v ? v.toFixed(1) + "s" : ""}</small></div>`; }).join("")}</div>
    ${j.attempts.length > 1 ? `<h3>Earlier attempts</h3>${j.attempts.slice(0, -1).map((a, i) => `<p style="font-size:13px">#${i + 1}: <span class="pill ${esc(a.status)}">${esc(a.status)}</span> ${esc(a.error || "")}</p>`).join("")}` : ""}
    ${j.compute ? `<h3>Compute</h3><p style="font-size:13.5px">${esc(j.compute.tool)}: ${esc(j.compute.needs || "")}</p>` : ""}
    <div class="row" style="margin-top:10px"><button class="btn ${/failed|blocked/.test(j.status) ? "primary" : ""}" id="rt">Retry job</button></div>`;
  $("#rt").onclick = () => act("retry", { job: j.id }, "Retry " + j.id);
  if (LIVE && /running|queued/.test(j.status)) setTimeout(async () => { if (location.hash.startsWith("#monitor")) { await load(); render(); } }, 2000);
};

// ---------------------------------------------------------------- router
function render() {
  const [tab, arg, ver] = (location.hash.slice(1) || "factory").split("/");
  const t = pages[tab] ? tab : "factory";
  document.querySelectorAll("#tabs a").forEach((a) => a.classList.toggle("on", a.dataset.tab === t));
  pages[t]($("#main"), arg, ver);
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", async () => { if (LIVE) await load(); render(); });
await load();
$("#mode").innerHTML = LIVE ? "<b>LIVE</b> · department server" : `<b>SNAPSHOT</b> · ${esc(S.source || "")}<br>${esc((S.generated || "").replace("T", " ").slice(0, 16))} UTC`;
render();
