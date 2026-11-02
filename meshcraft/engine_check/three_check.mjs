// Load a GLB into three@0.170 (the TIDEBREAKERS version) in headless Chromium, the way a game would.
//   node three_check.mjs --glb FILE --out shot.png [--clip NAME --time SECONDS] [--material game-toon|authored]
//                        [--contract contract.json] [--size 640]
// Prints a JSON report: nodes, clips, bounds (Y-up metres), vertex colours, contract checks.
import { createRequire } from 'node:module';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a), []));
const require = createRequire(import.meta.url);
const pwPath = [process.env.PLAYWRIGHT_MODULE, '/opt/node-tools/node_modules/playwright', 'playwright'].find((p) => { try { require.resolve(p); return true; } catch { return false; } });
const { chromium } = require(pwPath);
const execPath = ['/opt/pw-browsers/chromium', process.env.CHROMIUM_PATH].find((p) => p && existsSync(p));

const glb = path.resolve(args.glb);
const contract = args.contract ? JSON.parse(readFileSync(args.contract, 'utf8')) : null;
const size = Number(args.size || 640);
const MIME = { '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.html': 'text/html', '.png': 'image/png' };
const page_html = `<!doctype html><html><head><script type="importmap">{"imports":{"three":"http://gc.local/three/build/three.module.js","three/addons/":"http://gc.local/three/examples/jsm/"}}</script></head>
<body style="margin:0;background:#d6ecee"><canvas id="c" width="${size}" height="${size}"></canvas>
<script type="module">
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
const opts = ${JSON.stringify({ clip: args.clip || null, time: Number(args.time || 0), material: args.material || 'game-toon' })};
const renderer = new THREE.WebGLRenderer({ canvas: document.getElementById('c'), antialias: true, preserveDrawingBuffer: true });
renderer.setSize(${size}, ${size}, false); renderer.setClearColor(0xd6ecee);
const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xfff1d6, 0x6a8fb0, 1.4));
const sun = new THREE.DirectionalLight(0xffe2b0, 2.2); sun.position.set(-4, 7, 5); scene.add(sun);
// TIDEBREAKERS vcMat(): MeshToonMaterial with vertex colours and a 4-band gradient (src/world/materials.ts)
const grad = new THREE.DataTexture(new Uint8Array([90,90,90,255,150,150,150,255,210,210,210,255,255,255,255,255]), 4, 1, THREE.RGBAFormat);
grad.minFilter = grad.magFilter = THREE.NearestFilter; grad.needsUpdate = true;
const report = { ok: true };
try {
  const gltf = await new GLTFLoader().loadAsync('http://gc.local/asset.glb');
  const root = gltf.scene; scene.add(root);
  let meshes = 0, withColor = 0, tris = 0;
  root.traverse((o) => {
    if (!o.isMesh) return; meshes++;
    const g = o.geometry; if (g.attributes.color) withColor++;
    tris += (g.index ? g.index.count : g.attributes.position.count) / 3;
    if (opts.material === 'game-toon') o.material = new THREE.MeshToonMaterial({ vertexColors: !!g.attributes.color, gradientMap: grad, color: g.attributes.color ? 0xffffff : 0xcccccc });
  });
  const mixer = new THREE.AnimationMixer(root);
  report.clips = gltf.animations.map((c) => ({ name: c.name, seconds: +c.duration.toFixed(3), tracks: c.tracks.map((t) => t.name) }));
  if (opts.clip) {
    const clip = gltf.animations.find((c) => c.name === opts.clip);
    if (!clip) throw new Error('clip not found: ' + opts.clip);
    const a = mixer.clipAction(clip); a.setLoop(THREE.LoopOnce); a.clampWhenFinished = true; a.play();
    mixer.setTime(Math.min(opts.time, clip.duration));
  }
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const nodes = []; root.traverse((o) => nodes.push(o.name));
  const named = {}; for (const n of ['chest_lid', 'glow_anchor', 'lantern_body', 'figurehead', 'flag_cloth', 'biscuit']) { const o = root.getObjectByName(n); if (o) { const p = new THREE.Vector3(); o.getWorldPosition(p); named[n] = { position: p.toArray().map((v) => +v.toFixed(4)), rotationX: +o.rotation.x.toFixed(4) }; } }
  Object.assign(report, { meshes, meshesWithVertexColor: withColor, triangles: Math.round(tris), nodes, named,
    bounds: { min: box.min.toArray().map((v) => +v.toFixed(3)), max: box.max.toArray().map((v) => +v.toFixed(3)), size: box.getSize(new THREE.Vector3()).toArray().map((v) => +v.toFixed(3)) },
    skinned: gltf.scene.getObjectsByProperty ? root.getObjectsByProperty('isSkinnedMesh', true).length : 0 });
  const c = box.getCenter(new THREE.Vector3()), r = box.getSize(new THREE.Vector3()).length() * 0.62;
  const cam = new THREE.OrthographicCamera(-r, r, r, -r, 0.01, 100);
  cam.position.set(c.x + r * 1.6, c.y + r * 1.1, c.z + r * 2.4); cam.lookAt(c);
  renderer.render(scene, cam);
} catch (e) { report.ok = false; report.error = String(e && e.stack || e); }
window.__report = report;
</script></body></html>`;

const browser = await chromium.launch({ executablePath: execPath, headless: true, args: ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox'] });
const page = await browser.newPage({ viewport: { width: size, height: size } });
const logs = []; page.on('console', (m) => logs.push(m.text())); page.on('pageerror', (e) => logs.push(String(e)));
await page.route('http://gc.local/**', async (route) => {
  const u = new URL(route.request().url());
  if (u.pathname === '/' || u.pathname === '/index.html') return route.fulfill({ body: page_html, contentType: 'text/html' });
  if (u.pathname === '/asset.glb') return route.fulfill({ body: readFileSync(glb), contentType: 'model/gltf-binary' });
  const f = path.join(here, 'node_modules', u.pathname);
  if (!f.startsWith(path.join(here, 'node_modules')) || !existsSync(f)) return route.fulfill({ status: 404, body: 'not found' });
  return route.fulfill({ body: readFileSync(f), contentType: MIME[path.extname(f)] || 'application/octet-stream' });
});
await page.goto('http://gc.local/');
await page.waitForFunction(() => window.__report, null, { timeout: 60000 });
const report = await page.evaluate(() => window.__report);
if (args.out) await page.locator('#c').screenshot({ path: args.out });
await browser.close();

// contract checks (engine side)
const checks = [];
const add = (check, ok, detail) => checks.push({ check, level: ok ? 'pass' : 'fail', detail });
add('engine_load', report.ok, report.ok ? 'GLTFLoader (three@0.170) loaded the file' : report.error);
if (report.ok) {
  add('engine_vertex_colors', report.meshesWithVertexColor === report.meshes, `${report.meshesWithVertexColor}/${report.meshes} meshes carry COLOR_0 for the toon material`);
  // assets that hang or mount (contract.ground === false) are anchored elsewhere, so only grounded assets get this check
  if (!contract || contract.ground !== false) add('engine_base_on_ground', Math.abs(report.bounds.min[1]) < 0.02 || !!args.clip, `lowest point y=${report.bounds.min[1]} m`);
  if (contract) {
    for (const n of Object.values(contract.nodes || {})) add(`engine_node:${n}`, report.nodes.includes(n), report.nodes.includes(n) ? 'found' : 'missing');
    if (contract.lid_hinge_yup && report.named.chest_lid) {
      const d = Math.hypot(...report.named.chest_lid.position.map((v, i) => v - contract.lid_hinge_yup[i]));
      add('engine_lid_hinge', d < 0.01, `lid pivot at ${report.named.chest_lid.position} (expected ${contract.lid_hinge_yup})`);
    }
    if (contract.lid_open && args.clip === contract.lid_open.clip && report.named.chest_lid) {
      const want = contract.lid_open.radians;
      add('engine_lid_open_rotation', Math.abs(report.named.chest_lid.rotationX - want) < 0.02, `lid rotation.x = ${report.named.chest_lid.rotationX} at end of ${args.clip} (game uses ${want})`);
    }
    for (const c of contract.clips || []) add(`engine_clip:${c}`, report.clips.some((x) => x.name === c), 'clip present');
  }
}
const errs = logs.filter((l) => /error|warn/i.test(l));
process.stdout.write(JSON.stringify({ ...report, checks, console: errs.slice(0, 10), screenshot: args.out || null }, null, 1));
