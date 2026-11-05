// DESIGNCRAFT browser checks: serves a published site and drives it in Chromium as an iPhone 13 and a desktop.
// usage: node tests/designcraft_browser.js <dist> <game-id> <shots-dir>   -> prints a JSON report
const { chromium, devices } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const [root, game, shots] = process.argv.slice(2);
const TABS = ['overview', 'map', 'levelcraft', 'missioncraft', 'storycraft', 'progression', 'experience', 'lab', 'reports'];
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.md': 'text/markdown' };
const srv = http.createServer((q, r) => {
  let p = decodeURIComponent(q.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  fs.readFile(path.join(root, p), (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'Content-Type': types[path.extname(p)] || 'application/octet-stream' }); r.end(d); });
});
srv.listen(0, async () => {
  const port = srv.address().port, base = `http://127.0.0.1:${port}/`;
  const R = { errors: [], overflow: [], tabs: {}, checks: {} };
  const b = await chromium.launch();
  for (const [name, opt] of [['phone', devices['iPhone 13']], ['desktop', { viewport: { width: 1360, height: 900 } }]]) {
    const ctx = await b.newContext(Object.assign({ acceptDownloads: true }, opt)); const pg = await ctx.newPage();
    pg.on('pageerror', (e) => R.errors.push(`${name}: ${e.message}`));
    pg.on('console', (m) => { if (m.type() === 'error') R.errors.push(`${name} console: ${m.text()}`); });
    await pg.goto(base); await pg.waitForSelector('.row');
    R.checks[name + '_portfolio_lists_games'] = await pg.locator('main a.row').count();
    for (const t of TABS) {
      await pg.goto(`${base}#/g/${game}/${t}`); await pg.waitForFunction(() => !document.querySelector('.loading'));
      await pg.waitForTimeout(250);
      const ov = await pg.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (ov > 1) R.overflow.push(`${name} ${t}: ${ov}px`);
      R.tabs[`${name}:${t}`] = await pg.evaluate(() => ({ h1: (document.querySelector('main h1') || {}).textContent, svgs: document.querySelectorAll('main svg').length, findings: document.querySelectorAll('.finding').length }));
      if (shots) await pg.screenshot({ path: path.join(shots, `${name}-${t}.png`) });
    }
    // overview: category criteria sheet
    await pg.goto(`${base}#/g/${game}/overview`); await pg.waitForSelector('button.cat');
    await pg.locator('button.cat').first().click(); await pg.waitForSelector('#sheet:not([hidden]) table');
    R.checks[name + '_criteria_sheet'] = await pg.locator('#sheet table tbody tr').count();
    await pg.keyboard.press('Escape');
    // finding expands to evidence + three alternatives
    await pg.goto(`${base}#/g/${game}/missioncraft`); await pg.waitForSelector('.finding .f-h');
    await pg.locator('.finding .f-h').first().click();
    R.checks[name + '_finding_alternatives'] = await pg.locator('.finding .f-b:not([hidden]) .prop').count();
    // game map node selection
    await pg.goto(`${base}#/g/${game}/map`); await pg.waitForSelector('.node');
    await pg.locator('g.node').nth(1).click();
    R.checks[name + '_map_detail'] = (await pg.locator('.detail h3').textContent()) || '';
    // design lab: refine -> v1, original unchanged, save, compare, spec export
    await pg.goto(`${base}#/g/${game}/lab`); await pg.waitForSelector('.prop');
    const origBefore = await pg.locator('.orig').innerText();
    const firstTitle = await pg.locator('.prop .pt').first().innerText();
    await pg.locator('.prop button:has-text("Refine")').first().click();
    await pg.waitForSelector('#sheet:not([hidden]) .ask input');
    await pg.fill('#sheet .ask input', 'make it simpler and keep the opening brief');
    await pg.locator('#sheet .ask button[type=submit]').click();
    await pg.waitForSelector('#sheet .msg.dc');
    R.checks[name + '_refine_reply'] = await pg.locator('#sheet .msg.dc').last().innerText();
    await pg.fill('#sheet .ask input', 'add a dragon'); await pg.locator('#sheet .ask button[type=submit]').click();
    await pg.waitForTimeout(100);
    R.checks[name + '_refine_unknown_reply'] = await pg.locator('#sheet .msg.dc').last().innerText();
    await pg.locator('#sheet-x').click(); await pg.waitForSelector('.prop');
    R.checks[name + '_refined_chip'] = await pg.locator('.prop .chip:has-text("refined v")').count();
    R.checks[name + '_original_unchanged'] = (await pg.locator('.orig').innerText()) === origBefore;
    R.checks[name + '_proposal_title_kept'] = firstTitle.length > 0;
    await pg.locator('.prop button:has-text("Save")').first().click();
    await pg.locator('.prop button:has-text("Compare")').nth(0).click(); await pg.locator('.prop button:has-text("Compare")').nth(1).click();
    R.checks[name + '_compare_columns'] = await pg.locator('table thead th').count();
    const [dl] = await Promise.all([pg.waitForEvent('download'), pg.locator('.prop button:has-text("Export spec")').first().click()]);
    const p = await dl.path(); const spec = fs.readFileSync(p, 'utf8');
    R.checks[name + '_spec_sections'] = ['## Existing design (preserved)', '## Change', '## Validation', '## Acceptance'].every((s) => spec.includes(s));
    await pg.reload(); await pg.waitForSelector('.prop');
    R.checks[name + '_saved_persists'] = await pg.locator('h2:has-text("Saved alternatives")').count();
    await ctx.close();
  }
  await b.close(); srv.close();
  console.log(JSON.stringify(R));
});
