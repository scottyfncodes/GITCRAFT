// Browser half of tests/test_ui.py: drives the control room like a person on an iPhone, then checks
// dark mode and the desktop layout. Prints one JSON line per check; screenshots go to OUT.
//   node tests/ui_browser.js URL OUT
const { chromium, devices } = require('playwright');
const [url, out, palette, expected] = process.argv.slice(2);
const results = [];
const check = (name, ok, detail) => { results.push({ name, ok: !!ok, detail: detail == null ? '' : String(detail).slice(0, 300) }); };

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ...devices['iPhone 14'] });
  const p = await ctx.newPage(); const errors = [];
  p.on('pageerror', (e) => errors.push(String(e)));
  p.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  const overflow = () => p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const shot = async (n) => { await p.waitForTimeout(450); await p.screenshot({ path: `${out}/${n}.png` }); };
  const step = async (name, fn) => { try { await fn(); } catch (e) { check(name, false, e.message); } };

  await step('home', async () => {
    await p.goto(url); await p.waitForSelector('.grid .card');
    await p.waitForFunction(() => document.body.innerText.includes('CPU threads'), null, { timeout: 60000 });
    const txt = await p.innerText('main');
    check(`home: all ${expected} tools, sandbox and network state shown`, (await p.$$('.grid .card')).length === Number(expected) && /Landlock ABI \d/.test(txt) && txt.includes('Network denied'), txt.slice(0, 200));
    check('home: capabilities distinguish available from not available', txt.includes('Available') && txt.includes('Not available'));
    check('token removed from the address bar', !p.url().includes('token='), p.url());
    const tabs = await p.$$eval('.tabbar a', (as) => as.map((a) => a.getBoundingClientRect().height));
    check('tab bar targets are at least 44 px tall', tabs.length === 5 && tabs.every((hh) => hh >= 44), tabs);
    check('home: no horizontal scroll at iPhone width', (await overflow()) <= 0); await shot('01-home');
  });

  await step('library', async () => {
    await p.click('.tabbar a[data-page=library]'); await p.waitForSelector('.asset-card');
    check('library: assets listed with thumbnails', (await p.$$('.asset-card img')).length > 0); await shot('02-library');
    await p.fill('#lib-q', 'ui_lantern'); await p.waitForTimeout(200);
    await p.click('.asset-card >> nth=0'); await p.waitForSelector('.sheet .files');
    const t = await p.innerText('.sheet');
    check('asset: versions, fingerprints, inputs and checks shown', /v1/.test(t) && /sha256 [0-9a-f]{12}/.test(t) && t.includes('Inputs') && /Checks · \d+ pass/.test(t), t.slice(0, 300));
    check('asset: identical re-run marked', t.includes('identical to v1') || t.includes('first version'));
    await shot('03-asset');
    await p.click('.sheet button:has-text("3D:") >> nth=0');
    await p.waitForSelector('.viewer canvas', { timeout: 30000 }); await p.waitForTimeout(1500);
    const lit = await p.$eval('.viewer canvas', (c) => c.width > 0 && c.height > 0);
    check('asset: GLB opens in the 3D viewer (local three@0.170)', lit); await shot('04-asset-3d');
    // export through MeshCraft into the workspace
    await p.click('.sheet button:has-text("Export and verify")');
    await p.waitForSelector('.sheet .banner.info, .sheet .banner.bad', { timeout: 120000 });
    const ex = await p.innerText('.sheet');
    check('asset: export to the workspace is verified', /Verified: \d+ files/.test(ex), ex.slice(-300)); await shot('05-export');
    await p.click('.sheet header button');
  });

  await step('jobs', async () => {
    await p.click('.tabbar a[data-page=jobs]'); await p.waitForSelector('.item');
    await p.click('.filters button:has-text("Fallback")'); await p.waitForSelector('.item');
    await p.click('.item >> nth=0'); await p.waitForSelector('.timeline');
    const t = await p.innerText('.sheet');
    check('job: fallback explained with every attempt', t.includes('Finished with a fallback') && t.includes('Attempt 1') && t.includes('Attempt 2') && t.includes('512'), t.slice(0, 300));
    await shot('06-job-fallback'); await p.click('.sheet header button');
    await p.click('.filters button:has-text("Failed")'); await p.waitForSelector('.item'); await p.click('.item >> nth=0'); await p.waitForSelector('.timeline');
    const f = await p.innerText('.sheet');
    check('job: failure reason shown, not retried automatically', f.includes('Failed') && f.includes('unknown template') && f.includes('not retried'), f.slice(0, 300));
    await shot('07-job-failed'); await p.click('.sheet header button');
  });

  await step('advice', async () => {
    await p.click('.tabbar a[data-page=run]'); await p.click('.seg button:has-text("Advice")');
    await p.fill('#r-req', 'turn this concept art into a ship'); await p.fill('#r-img', '1'); await p.click('button:has-text("Get advice")');
    await p.waitForSelector('.advice');
    const t = await p.innerText('main');
    check('advice: unavailable capability is labelled unavailable, alternative labelled as not the same',
      t.includes('NOT AVAILABLE HERE') && t.includes('ALTERNATIVE') && t.includes('NOT derived'), t.slice(-300));
    await shot('08-advice-unavailable');
    await p.fill('#r-req', 'a blocky voxel lifeboat'); await p.fill('#r-img', '0'); await p.click('button:has-text("Get advice")');
    await p.waitForFunction(() => document.body.innerText.includes('AVAILABLE HERE') && !document.body.innerText.includes('NOT AVAILABLE'), null, { timeout: 20000 });
    check('advice: available path recommended with its tool steps', (await p.innerText('main')).includes('blockbench_build')); await shot('09-advice-available');
  });

  await step('pipeline', async () => {
    await p.click('.seg button:has-text("Pipeline")'); await p.waitForSelector('#p-template', { timeout: 60000 });
    await p.fill('#p-asset', 'ui_form_lantern'); await p.fill('#p-palette', palette); await p.selectOption('#p-template', 'lantern'); await p.selectOption('#p-size', '256');
    await shot('10-pipeline-form');
    await p.click('button:has-text("Run pipeline")');
    await p.waitForSelector('main .card.stripe.ok, main .card.stripe.bad', { timeout: 300000 });
    const t = await p.innerText('main');
    check('pipeline: run from the form finishes with checks and a library version', t.includes('Done') && /\d+ pass/.test(t) && t.includes('library v1'), t.slice(-400));
    check('pipeline: no horizontal scroll', (await overflow()) <= 0); await shot('11-pipeline-done');
  });

  await step('tools', async () => {
    await p.click('.tabbar a[data-page=tools]'); await p.waitForSelector('.grid .card');
    await p.click('.grid .card:has-text("effectcraft")'); await p.waitForSelector('.sheet .list .card', { timeout: 90000 });
    const t = await p.innerText('.sheet');
    check('tools: discovery lists a server\'s tools and marks policy-blocked ones', /\d+ tools/.test(t) && t.includes('blocked by policy'), t.slice(0, 200));
    await shot('12-tools'); await p.click('.sheet header button');
  });

  check('no page errors on iPhone', errors.length === 0, errors.join(' | '));

  // dark mode + desktop
  for (const [name, opts] of [['13-dark-iphone', { ...devices['iPhone 14'], colorScheme: 'dark' }], ['14-desktop', { viewport: { width: 1360, height: 860 } }]]) {
    await step(name, async () => {
      const c = await browser.newContext(opts); const q = await c.newPage();
      await q.goto(url); await q.waitForSelector('.grid .card');
      await q.goto(url.replace(/#.*/, '#library')); await q.reload(); await q.waitForSelector('.asset-card');
      check(`${name}: renders with no horizontal scroll`, (await q.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 0);
      await q.screenshot({ path: `${out}/${name}.png` }); await c.close();
    });
  }
  await browser.close();
  for (const r of results) console.log(JSON.stringify(r));
})().catch((e) => { console.log(JSON.stringify({ name: 'browser run', ok: false, detail: String(e) })); process.exit(1); });
