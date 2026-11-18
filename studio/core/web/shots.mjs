// The shot list runner: reach each named shot of a product and capture it, only once real content is on screen.
//   node shots.mjs request.json
// request: { root | url, entry, out_dir, viewports: [{name, width, height, mobile?, device?}], shots: [...], timeout_ms?, _result }
// A shot: { id, name, kind, path?, steps: [...], wait_for: {selector?, text?, js?, timeout_ms?}, viewports? }
// Steps (the PIXELCRAFT journey vocabulary, plus keys and eval for games):
//   {click|tap: 'label'} {selector: 'css'} {fill: {selector|label, value}} {press: 'Space'} {hold: {key, ms}} {goto: '/x'} {back: true}
//   {wait: ms} {expect: 'text'} {eval: 'js'} {settle_ms}
// Every shot starts from a fresh page. After its steps, the runner waits for wait_for (bounded); if it never holds, the shot
// is NOT SEEN with the reason, and the frame that was on screen is kept only as <id>@<vp>.unreached.png for diagnosis:
// it is never offered as evidence. Nothing is fetched from the network (the folder is served by request interception).
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { launch, serveGame, contextOptions } from './gamepage.mjs';

const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const done = (o) => { writeFileSync(req._result, JSON.stringify(o)); process.exit(0); };

async function findTarget(page, step) {
  if (step.selector) { const l = page.locator(step.selector).first(); return (await l.count()) ? l : null; }
  const text = step.click ?? step.tap ?? step.text;
  if (text == null) return null;
  for (const l of [page.getByRole('button', { name: text }), page.getByRole('link', { name: text }), page.getByText(text, { exact: false })]) {
    try { const f = l.first(); if (await f.count() && await f.isVisible()) return f; } catch {}
  }
  return null;
}

async function act(page, step, touch) {
  if (step.goto != null) await page.goto(new URL(step.goto, page.url()).href);
  else if (step.back) await page.goBack();
  else if (step.press) await page.keyboard.press(step.press);
  else if (step.hold) { const k = step.hold.key || 'Space'; await page.keyboard.down(k); await page.waitForTimeout(step.hold.ms || 300); await page.keyboard.up(k); }
  else if (step.fill) { const l = await findTarget(page, { selector: step.fill.selector, text: step.fill.label }); if (!l) throw new Error('field not found'); await l.fill(String(step.fill.value ?? '')); }
  else if (step.wait != null) await page.waitForTimeout(Math.min(step.wait, 30000));
  else if (step.expect != null) { if (!(await page.getByText(step.expect).count())) throw new Error(`expected text not on screen: ${step.expect}`); }
  else if (step.eval != null) await page.evaluate(step.eval);
  else if (step.click != null || step.tap != null || step.selector) {
    const l = await findTarget(page, step); if (!l) throw new Error(`control not found: ${step.selector || step.click || step.tap}`);
    if (touch) await l.tap({ timeout: 4000 }); else await l.click({ timeout: 4000 });
  }
  if (step.settle_ms) await page.waitForTimeout(step.settle_ms);
}

async function waitFor(page, w) {
  const timeout = Math.min(w.timeout_ms || 8000, 30000);
  const what = w.selector ? `selector ${w.selector}` : w.text ? `text "${w.text}"` : `condition ${w.js}`;
  try {
    if (w.selector) await page.locator(w.selector).first().waitFor({ state: 'visible', timeout });
    if (w.text) await page.getByText(w.text, { exact: false }).first().waitFor({ state: 'visible', timeout });
    if (w.js) await page.waitForFunction(w.js, null, { timeout, polling: 100 });
  } catch (e) { throw new Error(`real content never appeared: waited ${timeout} ms for ${what}`); }
}

try {
  const { browser, devices } = await launch();
  const origin = req.url ? new URL(req.url).origin : null;
  mkdirSync(req.out_dir, { recursive: true });
  const out = [];
  for (const shot of req.shots) {
    const S = { id: shot.id, name: shot.name, kind: shot.kind, moment: shot.moment || null, captures: [] };
    for (const vp of req.viewports) {
      if (shot.viewports && !shot.viewports.includes(vp.name)) continue;
      const opts = contextOptions(vp, devices); const touch = !!(opts.hasTouch);
      const context = await browser.newContext(opts); const page = await context.newPage();
      const R = { blocked: [], missing: [], requests: 0, errors: [] };
      page.on('pageerror', (e) => R.errors.push(String(e).slice(0, 200)));
      if (origin) await page.route('**/*', (rt) => { const u = new URL(rt.request().url()); if (u.origin === origin || u.protocol === 'data:' || u.protocol === 'blob:') return rt.continue(); R.blocked.push(u.href.slice(0, 160)); return rt.abort(); });
      else await serveGame(page, req.root, R);
      const C = { viewport: vp.name, reached: false, reason: null, steps: 0 };
      const t0 = Date.now();
      try {
        const base = origin ? req.url.replace(/\/$/, '') : 'http://game.local';
        await page.goto(base + '/' + String(shot.path || req.entry || 'index.html').replace(/^\//, ''), { timeout: 20000 });
        try { await page.waitForLoadState('load', { timeout: 15000 }); } catch {}
        await page.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
        for (const st of shot.steps || []) { await act(page, st, touch); C.steps++; }
        await waitFor(page, shot.wait_for || {});
        await page.waitForTimeout(shot.settle_ms ?? 250);   // one more frame of paint after the condition holds
        C.image = path.join(req.out_dir, `${shot.id}@${vp.name}.png`);
        await page.screenshot({ path: C.image });
        C.reached = true;
      } catch (e) {
        C.reason = String(e && e.message || e).split('\n')[0].slice(0, 240);
        try { const p = path.join(req.out_dir, `${shot.id}@${vp.name}.unreached.png`); await page.screenshot({ path: p }); C.diagnostic = p; } catch {}
      }
      C.ms = Date.now() - t0; C.page_errors = R.errors.slice(0, 5); C.missing = R.missing.slice(0, 5); C.blocked = R.blocked.slice(0, 5);
      S.captures.push(C);
      await context.close();
    }
    out.push(S);
  }
  await browser.close();
  done({ shots: out });
} catch (e) { done({ error: String(e && e.stack || e) }); }
