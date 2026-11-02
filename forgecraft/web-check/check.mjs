// Engine-compatibility check for ForgeCraft exports.
//
//   node forgecraft/web-check/check.mjs out.json shot.png file1.glb [file2.glb ...]
//
// 1. Khronos glTF-Validator on every file (errors fail the file).
// 2. Loads every file with three.js r170's GLTFLoader (the version TIDEBREAKERS ships) in
//    headless Chromium, adds them to one scene, plays each animation clip with an
//    AnimationMixer, renders a WebGL frame and screenshots it. Reports per-file meshes,
//    triangles, textures, clips and Y-up bounding boxes as three.js sees them.
// 3. Plays every clip on its own and compares the pose at the start and part-way through, so a
//    clip whose keyframes did not survive export (it loads but nothing moves) is reported.
// Modules (three, gltf-validator) come from $FORGECRAFT_WEB_MODULES when set (the pipeline sets it:
// ForgeCraft's own install, or MeshCraft's identical engine_check install), else ./node_modules.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const here = path.dirname(new URL(import.meta.url).pathname);
const MODULES = process.env.FORGECRAFT_WEB_MODULES || path.join(here, "node_modules");
const validator = require(path.join(MODULES, "gltf-validator"));
const { chromium } = require("playwright");

const [outJson, shot, ...files] = process.argv.slice(2);
const report = { files: {}, three: null };

for (const f of files) {
  const bytes = new Uint8Array(fs.readFileSync(f));
  const r = await validator.validateBytes(bytes, { uri: path.basename(f), maxIssues: 50,
    externalResourceFunction: (uri) => Promise.resolve(new Uint8Array(fs.readFileSync(path.join(path.dirname(f), decodeURIComponent(uri))))) });
  report.files[f] = { validator: { errors: r.issues.numErrors, warnings: r.issues.numWarnings, infos: r.issues.numInfos,
    messages: r.issues.messages.filter((m) => m.severity <= 1).slice(0, 8).map((m) => `${m.code}: ${m.message}`),
    generator: r.info?.generator, animations: r.info?.animationCount, materials: r.info?.materialCount, triangles: r.info?.totalTriangleCount } };
}

// Files are served to the page by Playwright request interception (no sockets: this runs
// inside GITCRAFT's Landlock sandbox, which denies TCP).
const ORIGIN = "http://forgecraft.local";
const served = files.map((f, i) => ({ url: `/asset/${i}${path.extname(f)}`, file: f }));
function resolve(u) {
  if (u.startsWith("/three/")) return path.join(MODULES, "three", u.slice(7));
  const s = served.find((x) => x.url === u); if (s) return s.file;
  const i = served.find((x) => u.startsWith(x.url.replace(/\.[^.]+$/, "") + "/") || u.startsWith("/asset/"));
  return i ? path.join(path.dirname(i.file), u.split("/").slice(3).join("/")) : null;
}
const PAGE = `<!doctype html><html><body style="margin:0;background:#7ccbf2">
<script type="importmap">{"imports":{"three":"/three/build/three.module.js","three/addons/":"/three/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const files = ${JSON.stringify(served.map((s) => s.url))};
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setSize(960, 540); document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color('#7ccbf2');
scene.add(new THREE.HemisphereLight(0xffffff, 0x335577, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 2.2); sun.position.set(10, 20, 10); scene.add(sun);
const loader = new GLTFLoader(); const out = []; const mixers = [];
let x = 0;
for (const url of files) {
  const rec = { url };
  try {
    const g = await loader.loadAsync(url);
    let meshes = 0, tris = 0, tex = new Set(), skinned = 0;
    g.scene.traverse((o) => { if (o.isMesh) { meshes++; if (o.isSkinnedMesh) skinned++;
      const geo = o.geometry; tris += (geo.index ? geo.index.count : geo.attributes.position.count) / 3;
      for (const m of [].concat(o.material)) for (const k of ['map','metalnessMap','roughnessMap','normalMap']) if (m[k]) tex.add(m[k].uuid); } });
    const box = new THREE.Box3().setFromObject(g.scene); const size = box.getSize(new THREE.Vector3());
    g.scene.position.x = x - box.min.x; x += size.x + 2; scene.add(g.scene);
    // every clip on its own: does the pose change between the start and part-way through?
    const pose = () => { const v = []; g.scene.traverse((o) => { v.push(...o.position.toArray(), ...o.quaternion.toArray(), ...o.scale.toArray()); }); return v; };
    const played = g.animations.map((clip) => {
      const mx = new THREE.AnimationMixer(g.scene); const act = mx.clipAction(clip); act.play();
      mx.setTime(0); const a = pose(); mx.setTime(Math.max(clip.duration * 0.4, 1 / 30)); const b = pose();
      act.stop(); mx.uncacheRoot(g.scene);
      let d = 0; for (let i = 0; i < a.length; i++) d = Math.max(d, Math.abs(a[i] - b[i]));
      return { name: clip.name, max_delta: +d.toFixed(5), moves: d > 1e-4 };
    });
    if (g.animations.length) { const mx = new THREE.AnimationMixer(g.scene); const a = mx.clipAction(g.animations.find(c => /walk|bob/i.test(c.name)) || g.animations[0]); a.play(); mx.update(0.35); mixers.push(mx); }
    rec.ok = true; Object.assign(rec, { meshes, skinned, triangles: tris, textures: tex.size,
      clips: g.animations.map((c, i) => ({ name: c.name, seconds: +c.duration.toFixed(3), tracks: c.tracks.length, moves: played[i].moves, max_delta: played[i].max_delta })),
      size_yup: [size.x, size.y, size.z].map((v) => +v.toFixed(3)), nodes: g.parser.json.nodes.length,
      sockets: g.parser.json.nodes.filter((n) => (n.name || '').startsWith('socket_')).map((n) => n.name) });
  } catch (e) { rec.ok = false; rec.error = String(e); }
  out.push(rec);
}
// frame the content, not the ocean plane a composed scene carries
const all = new THREE.Box3(); scene.updateMatrixWorld(true);
scene.traverse((o) => { if (o.isMesh && !/ocean/i.test(o.name)) all.expandByObject(o); });
const c = all.getCenter(new THREE.Vector3()); const s = all.getSize(new THREE.Vector3());
const cam = new THREE.PerspectiveCamera(40, 960 / 540, 0.1, 5000); const r = Math.max(s.x, s.y, s.z);
cam.position.set(c.x + r * 0.55, c.y + r * 0.42, c.z + r * 0.85); cam.lookAt(c);
renderer.render(scene, cam);
window.__result = { three: THREE.REVISION, renderer: renderer.getContext().getParameter(renderer.getContext().VERSION), files: out };
</script></body></html>`;
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width: 960, height: 540 } });
const logs = []; page.on("console", (m) => logs.push(m.text())); page.on("pageerror", (e) => logs.push(String(e)));
await page.route(ORIGIN + "/**", (route) => {
  const u = decodeURIComponent(new URL(route.request().url()).pathname);
  if (u === "/") return route.fulfill({ status: 200, contentType: "text/html", body: PAGE });
  const p = resolve(u);
  if (!p || !fs.existsSync(p)) return route.fulfill({ status: 404, body: "" });
  const type = p.endsWith(".js") ? "text/javascript" : p.endsWith(".glb") ? "model/gltf-binary" : p.endsWith(".gltf") ? "model/gltf+json" : p.endsWith(".png") ? "image/png" : "application/octet-stream";
  return route.fulfill({ status: 200, contentType: type, body: fs.readFileSync(p) });
});
await page.goto(ORIGIN + "/");
await page.waitForFunction(() => window.__result, null, { timeout: 120000 });
const res = await page.evaluate(() => window.__result);
await page.screenshot({ path: shot });
await browser.close();
report.three = { revision: res.three, gl: res.renderer, screenshot: shot, console: logs.slice(0, 20) };
res.files.forEach((r, i) => { report.files[files[i]].three = r; });
report.ok = Object.values(report.files).every((f) => f.validator.errors === 0 && f.three && f.three.ok);
fs.writeFileSync(outJson, JSON.stringify(report, null, 1));
console.log(JSON.stringify({ ok: report.ok, three: report.three.revision, files: Object.fromEntries(Object.entries(report.files).map(([k, v]) => [path.basename(k), { errors: v.validator.errors, warnings: v.validator.warnings, loaded: v.three?.ok, tris: v.three?.triangles, clips: v.three?.clips?.length, textures: v.three?.textures, size: v.three?.size_yup }])) }, null, 1));
process.exit(report.ok ? 0 : 1);
