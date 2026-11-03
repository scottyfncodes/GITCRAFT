// GITCRAFT Studio browser harness: load a generated page in headless Chromium and collect its report.
//   node harness.mjs request.json
// request: { html, screenshot?, size: [w, h], timeout_ms, shots?: [{at_ms, path}], _result }
// The page is served at http://gc.local/ with:
//   /three/...   three@0.170.0 (studio node runtime)     /phaser/...  phaser@3.90.0
//   /files/<absolute path>  any file (the sandbox decides what is readable)
// The page sets window.__report = {...} and window.__done = true when finished.
// Nothing is fetched from the network: unmatched requests are aborted and listed in the report.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import path from 'node:path';

const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const out = { };
const finish = (o) => { writeFileSync(req._result, JSON.stringify(o)); process.exit(0); };
try {
  const require = createRequire(import.meta.url);
  const pwPath = [process.env.PLAYWRIGHT_MODULE, '/opt/node-tools/node_modules/playwright', 'playwright'].find((p) => { try { return p && require.resolve(p); } catch { return false; } });
  if (!pwPath) finish({ error: 'Playwright module not found' });
  const { chromium } = require(pwPath);
  const nm = process.env.STUDIO_NODE_MODULES;
  const exe = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'].find((p) => p && existsSync(p));
  const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--disable-background-networking', '--disable-component-update', '--no-first-run', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const [w, h] = req.size || [640, 480];
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const MIME = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.glb': 'model/gltf-binary', '.html': 'text/html', '.wav': 'audio/wav', '.ogg': 'audio/ogg', '.tmj': 'application/json', '.css': 'text/css' };
  const errors = [], blocked = [], logs = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); else if (logs.length < 50) logs.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));
  await page.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.host !== 'gc.local') { blocked.push(u.href); return route.abort(); }
    let file = null;
    if (u.pathname === '/' || u.pathname === '/index.html') return route.fulfill({ status: 200, contentType: 'text/html', body: req.html });
    if (u.pathname.startsWith('/three/')) file = path.join(nm, 'three', decodeURIComponent(u.pathname.slice(7)));
    else if (u.pathname.startsWith('/phaser/')) file = path.join(nm, 'phaser', decodeURIComponent(u.pathname.slice(8)));
    else if (u.pathname.startsWith('/files/')) file = decodeURIComponent(u.pathname.slice(6));
    if (!file || !existsSync(file)) return route.fulfill({ status: 404, body: 'not found' });
    return route.fulfill({ status: 200, contentType: MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', body: readFileSync(file) });
  });
  const t0 = Date.now();
  await page.goto('http://gc.local/');
  for (const s of req.shots || []) {
    const wait = s.at_ms - (Date.now() - t0); if (wait > 0) await page.waitForTimeout(wait);
    await page.screenshot({ path: s.path });
  }
  try { await page.waitForFunction(() => window.__done === true, null, { timeout: req.timeout_ms || 60000 }); }
  catch { errors.push('timed out waiting for the page to finish'); }
  out.report = await page.evaluate(() => window.__report || null);
  if (req.screenshot) await page.screenshot({ path: req.screenshot });
  out.errors = errors; out.blocked = blocked; out.logs = logs; out.ms = Date.now() - t0;
  await browser.close();
  finish(out);
} catch (e) {
  finish({ error: String(e && e.stack || e) });
}
