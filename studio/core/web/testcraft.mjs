// TestCraft browser runner (Playwright + Chromium). node testcraft.mjs request.json
// request: { root, entry, out_dir, viewports: [{name, width, height, mobile?, device?}], wait_ms,
//            steps?: [...], perf_ms?, record_video?, _result }
// The game folder `root` is served at http://game.local/ through request interception (no sockets,
// works inside the GITCRAFT sandbox); any other host is blocked and reported.
// Steps: {press: key} {hold: key, ms} {down: key} {up: key} {click: [x, y]} {tap: [x, y]} {wait: ms}
//        {screenshot: name} {eval: "js expr", as: name} {assert: "js expr", name} {type: text}
import { readFileSync, writeFileSync, existsSync, mkdirSync, renameSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { launch, serveGame, contextOptions } from './gamepage.mjs';

const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const done = (o) => { writeFileSync(req._result, JSON.stringify(o)); process.exit(0); };
try {
  const { browser, devices } = await launch();
  const root = path.resolve(req.root);
  mkdirSync(req.out_dir, { recursive: true });
  const results = [];
  for (const vp of req.viewports) {
    const ctxOpts = contextOptions(vp, devices);
    if (req.record_video) ctxOpts.recordVideo = { dir: path.join(req.out_dir, 'video-' + vp.name), size: ctxOpts.viewport };
    const context = await browser.newContext(ctxOpts);
    const page = await context.newPage();
    const R = { viewport: vp.name, size: ctxOpts.viewport, console_errors: [], page_errors: [], blocked: [], missing: [], requests: 0, screenshots: [], steps: [], asserts: [], values: {} };
    page.on('console', (m) => { if (m.type() === 'error') R.console_errors.push(m.text().slice(0, 300)); });
    page.on('pageerror', (e) => R.page_errors.push(String(e).slice(0, 300)));
    await page.addInitScript(() => {   // frame timing for perf: every rAF tick
      window.__frames = []; let last = performance.now();
      const tick = (t) => { window.__frames.push(t - last); last = t; requestAnimationFrame(tick); }; requestAnimationFrame(tick);
    });
    await serveGame(page, root, R);
    const t0 = Date.now();
    try { await page.goto('http://game.local/' + (req.entry || 'index.html'), { waitUntil: 'load', timeout: 30000 }); R.load_ms = Date.now() - t0; }
    catch (e) { R.page_errors.push('navigation: ' + String(e).slice(0, 200)); }
    await page.waitForTimeout(req.wait_ms || 1500);
    const shot = async (name) => { const p = path.join(req.out_dir, `${vp.name}_${name}.png`); await page.screenshot({ path: p }); R.screenshots.push(p); return p; };
    await shot('loaded');
    R.layout = await page.evaluate(() => ({ scroll_width: document.documentElement.scrollWidth, inner_width: innerWidth, scroll_height: document.documentElement.scrollHeight,
      inner_height: innerHeight, canvases: [...document.querySelectorAll('canvas')].map((c) => [c.width, c.height]), title: document.title }));
    for (const s of req.steps || []) {
      const rec = { step: s }; const t = Date.now();
      try {
        if (s.press) await page.keyboard.press(s.press);
        else if (s.hold) { await page.keyboard.down(s.hold); await page.waitForTimeout(s.ms || 500); await page.keyboard.up(s.hold); }
        else if (s.down) await page.keyboard.down(s.down);
        else if (s.up) await page.keyboard.up(s.up);
        else if (s.click) await page.mouse.click(s.click[0], s.click[1]);
        else if (s.tap) { if (ctxOpts.hasTouch) await page.touchscreen.tap(s.tap[0], s.tap[1]); else await page.mouse.click(s.tap[0], s.tap[1]); }
        else if (s.type) await page.keyboard.type(s.type);
        else if (s.wait) await page.waitForTimeout(s.wait);
        else if (s.screenshot) rec.path = await shot(s.screenshot);
        else if (s.eval) { const v = await page.evaluate(s.eval); R.values[s.as || s.eval] = v; rec.value = v; }
        else if (s.assert) { const v = await page.evaluate(s.assert); const ok = !!v; R.asserts.push({ name: s.name || s.assert, expr: s.assert, ok, value: v }); rec.ok = ok; }
        rec.ms = Date.now() - t;
      } catch (e) { rec.error = String(e).slice(0, 300); R.asserts.push({ name: s.name || JSON.stringify(s), ok: false, error: rec.error }); }
      R.steps.push(rec);
    }
    if (req.perf_ms) {
      await page.evaluate(() => { window.__frames = []; });
      await page.waitForTimeout(req.perf_ms);
      R.perf = await page.evaluate(() => {
        const f = window.__frames.slice(1).sort((a, b) => a - b), n = f.length, sum = f.reduce((a, b) => a + b, 0);
        const q = (p) => (n ? f[Math.min(n - 1, Math.floor(p * n))] : null);
        const mem = performance.memory ? { used_mb: +(performance.memory.usedJSHeapSize / 1048576).toFixed(1), total_mb: +(performance.memory.totalJSHeapSize / 1048576).toFixed(1) } : null;
        return { frames: n, fps: n ? +(1000 * n / sum).toFixed(1) : 0, frame_ms_p50: q(0.5), frame_ms_p95: q(0.95), frame_ms_p99: q(0.99), frame_ms_max: n ? f[n - 1] : null,
          long_frames_over_50ms: f.filter((x) => x > 50).length, heap: mem, dom_nodes: document.getElementsByTagName('*').length };
      });
    }
    await shot('final');
    await context.close();
    if (req.record_video) {
      const d = path.join(req.out_dir, 'video-' + vp.name); const v = existsSync(d) ? readdirSync(d).find((f) => f.endsWith('.webm')) : null;
      if (v) { const dest = path.join(req.out_dir, `${vp.name}_session.webm`); renameSync(path.join(d, v), dest); R.video = dest; }
    }
    results.push(R);
  }
  await browser.close();
  done({ results });
} catch (e) { done({ error: String(e && e.stack || e).slice(0, 2000) }); }
