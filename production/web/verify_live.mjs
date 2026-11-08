// GITCRAFT live check: open a deployed URL in headless Chromium (phone + desktop) and report what a visitor gets.
//   node verify_live.mjs request.json      request: {url, out_dir, _result}
// Runs OUTSIDE the tool sandbox (the agent's shell), through the session's HTTPS proxy when there is one.
// Never disables TLS verification.
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const done = (o) => { writeFileSync(req._result, JSON.stringify(o)); process.exit(0); };
const require = createRequire(import.meta.url);
const pw = [process.env.PLAYWRIGHT_MODULE, path.join(os.homedir(), '.gitcraft/studio/node/node_modules/playwright'), '/opt/node-tools/node_modules/playwright', 'playwright']
  .find((p) => { try { return p && require.resolve(p); } catch { return false; } });
if (!pw) done({ error: 'Playwright is not installed here (scripts/install-studio.sh installs it)' });
const { chromium } = require(pw);
const exe = [process.env.CHROMIUM_PATH].find((p) => p && existsSync(p));
const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
let browser;
const bypass = ['localhost', '127.0.0.1', ...String(process.env.NO_PROXY || process.env.no_proxy || '').split(',').map((h) => h.trim()).filter(Boolean)].join(',');
try { browser = await chromium.launch({ executablePath: exe, proxy: proxy ? { server: proxy, bypass } : undefined }); }
catch (e) { done({ error: `Chromium did not start: ${String(e).slice(0, 300)}` }); }
const out = { url: req.url, viewports: [] };
for (const [name, vp, mobile] of [['phone', { width: 390, height: 844 }, true], ['desktop', { width: 1280, height: 800 }, false]]) {
  const ctx = await browser.newContext({ viewport: vp, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const R = { viewport: name, page_errors: [], console_errors: [], failed: [] };
  page.on('pageerror', (e) => R.page_errors.push(String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error') R.console_errors.push(m.text().slice(0, 300)); });
  page.on('response', (r) => { if (r.status() >= 400) R.failed.push(`${r.status()} ${r.url()}`.slice(0, 300)); });
  page.on('requestfailed', (r) => R.failed.push(`failed ${r.url()} (${r.failure()?.errorText || ''})`.slice(0, 300)));
  try {
    const resp = await page.goto(req.url, { waitUntil: 'load', timeout: 45000 });
    await page.waitForTimeout(1500);
    R.status = resp ? resp.status() : null; R.final_url = page.url(); R.title = await page.title();
    R.text = (await page.evaluate(() => document.body ? document.body.innerText : '')).slice(0, 400);
    R.byline = await page.evaluate(() => { const e = document.querySelector('[data-haveanapp]'); return e ? e.innerText.trim().slice(0, 80) : null; });
    R.screenshot = path.join(req.out_dir, `live-${name}.png`); await page.screenshot({ path: R.screenshot });
  } catch (e) { R.error = String(e).slice(0, 300); }
  out.viewports.push(R); await ctx.close();
}
await browser.close();
done(out);
