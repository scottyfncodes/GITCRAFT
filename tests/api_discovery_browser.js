// Browser half of tests/test_api_discovery.py: drives the published /apis/ page and prints one JSON object.
//   node api_discovery_browser.js <base url> <queries.json>
const fs = require('fs');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { console.log(JSON.stringify({ skip: 'playwright is not installed' })); process.exit(0); }

(async () => {
  const [base, qfile] = process.argv.slice(2);
  const Q = JSON.parse(fs.readFileSync(qfile, 'utf8'));
  const out = { parity: {}, errors: [] };
  const exe = ['/opt/pw-browsers/chromium', process.env.CHROMIUM_PATH].find((p) => p && fs.existsSync(p));
  const b = await chromium.launch(exe && fs.statSync(exe).isFile() ? { executablePath: exe } : {});
  const open = async (path, w, h, route) => {
    const p = await b.newPage({ viewport: { width: w, height: h }, hasTouch: w < 500, isMobile: w < 500 });
    p.on('pageerror', (e) => out.errors.push(String(e)));
    await p.route('**/raw.githubusercontent.com/**', route || ((r) => r.abort()));   // the live refresh: unavailable unless a test serves it
    await p.goto(base + path);
    return p;
  };
  const metrics = (p) => p.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - innerWidth,
    small: [...document.querySelectorAll('button, a.btn, select, input[type=search], summary, label.check, .seg span, .chip, .api header a')]
      .filter((e) => e.offsetWidth > 0 && e.offsetHeight > 0 && (e.offsetHeight < 44 || e.offsetWidth < 44))   // layout size: the pressed state scales a button briefly
      .map((e) => e.tagName + ' ' + e.textContent.trim().slice(0, 20) + ' ' + e.offsetWidth + 'x' + e.offsetHeight),
    inputFont: Math.min(...[...document.querySelectorAll('input[type=search], select')].map((e) => parseFloat(getComputedStyle(e).fontSize))),
  }));

  // 1. the catalogue loads with the live refresh unavailable; phone layout
  let p = await open('/', 390, 844);
  await p.waitForSelector('.browse', { timeout: 20000 });
  out.home = Object.assign(await metrics(p), { categories: await p.locator('.cats .chip').count(), foot: await p.locator('#foot').innerText() });

  // 2. search parity with apidiscovery/search.py, and the statements and guides with intel.py / guide.py
  for (const q of Q.queries) {
    out.parity[q.q] = await p.evaluate(({ q, f }) => { const r = window.__apiDiscovery.search(q, f, 12); return { ids: r.results.map((x) => x.e.id), total: r.total, notes: r.notes, related: r.related.map((g) => [g.need, g.results.map((x) => x.e.id)]) }; }, { q: q.q, f: q.f || {} });
  }
  out.rendered = await p.evaluate((ids) => ids.map((id) => {
    const A = window.__apiDiscovery, e = A.state.byId.get(id); if (!e) return null;
    const langs = Object.keys(A.state.data.templates.languages), g = {};
    for (const pf of ['server', 'browser', 'mobile']) for (const l of langs) { const x = A.guide(e, l, pf); g[pf + '|' + l] = { code: x.code, runs_on: x.runs_on, sections: x.sections.map((s) => [s.title, s.body]) }; }
    return { id, criteria: A.criteria(e, null).map((c) => [c.key, c.finding, c.basis]), summary: A.summary(e), guides: g };
  }), Q.entries);

  // 3. the workflow on a phone: describe → discover → compare → guide
  await p.fill('#q', 'A free weather API for a mobile hiking app'); await p.press('#q', 'Enter');
  await p.waitForSelector('article.api');
  out.results = Object.assign(await metrics(p), {
    cards: await p.locator('#out > .list').first().locator('article.api').count(), heading: await p.locator('.rhead h2').innerText(), notes: await p.locator('.note').allInnerTexts(),
    firstCard: await p.locator('article.api').first().innerText(), platform: await p.evaluate(() => document.querySelector('input[name=platform]:checked').value),
    also: await p.locator('h2.also').allInnerTexts(), url: p.url() });
  const pick = p.locator('article.api button[aria-pressed]');
  await pick.nth(0).tap(); await pick.nth(1).tap();
  out.tray = { text: await p.locator('#trayText').innerText(), visible: await p.locator('#tray').isVisible() };
  await p.locator('#trayGo').tap(); await p.waitForSelector('.cmp');
  out.compare = Object.assign(await metrics(p), { text: await p.locator('#dlgBody').innerText(), rows: await p.locator('.cmp .crow').count(),
    dialogFits: await p.evaluate(() => { const r = document.getElementById('dlg').getBoundingClientRect(); return r.width <= innerWidth && r.height <= innerHeight + 1; }) });
  await p.locator('#dlgClose').tap();
  await p.locator('article.api .btn.primary').first().tap(); await p.waitForSelector('.crit');
  out.detail = Object.assign(await metrics(p), { text: await p.locator('#dlgBody').innerText(), code: await p.locator('#dlgBody pre').innerText(),
    preScrolls: await p.evaluate(() => { const e = document.querySelector('#dlgBody pre'); return e.scrollWidth > e.clientWidth && getComputedStyle(e).overflowX !== 'visible'; }) });
  await p.locator('#dlgClose').tap();

  // 4. empty and no-match states, filters
  await p.fill('#q', 'xyzzyplugh'); await p.press('#q', 'Enter'); await p.waitForSelector('.state');
  out.nomatch = { text: await p.locator('#out').innerText(), cards: await p.locator('#out article.api').count() };
  await p.fill('#q', 'weather'); await p.press('#q', 'Enter'); await p.waitForSelector('article.api');
  await p.locator('#filters summary').tap(); await p.selectOption('#fAuth', 'apiKey'); await p.locator('label.check', { hasText: 'HTTPS' }).tap();
  out.filtered = { auths: await p.locator('#out > .list').first().locator('.fact:nth-child(1) dd').allInnerTexts(), count: await p.locator('#filterCount').innerText(), url: p.url() };
  await p.close();

  // 5. a shared link restores the need and the filters
  p = await open('/?q=currency&auth=none&cors=1&for=browser&lang=python', 390, 844); await p.waitForSelector('article.api');
  out.restored = { q: await p.inputValue('#q'), auth: await p.inputValue('#fAuth'), cors: await p.isChecked('#fCors'), lang: await p.inputValue('#lang'), platform: await p.evaluate(() => document.querySelector('input[name=platform]:checked').value),
    corsValues: await p.locator('#out > .list').first().locator('.fact:nth-child(3) dd').allInnerTexts() };
  await p.close();

  // 6. desktop
  p = await open('/?q=flight%20tracking', 1280, 900); await p.waitForSelector('article.api');
  out.desktop = Object.assign(await metrics(p), { columns: await p.evaluate(() => getComputedStyle(document.querySelector('#out > .list')).gridTemplateColumns.split(' ').length) });
  await p.close();

  // 7. a newer valid catalogue on the data branch is adopted; a broken one is ignored
  const bundled = JSON.parse(fs.readFileSync(Q.data, 'utf8'));
  const newer = Object.assign({}, bundled, { built: '2999-01-01T00:00:00Z', entries: bundled.entries.map((r, i) => (i ? r : [r[0], 'LIVE-REFRESH-MARKER', r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11]])) });
  p = await open('/', 390, 844, (r) => r.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(newer) }));
  await p.waitForFunction(() => window.__apiDiscovery.state.origin === 'live', null, { timeout: 15000 }).catch(() => {});
  out.live = { origin: await p.evaluate(() => window.__apiDiscovery.state.origin), marker: await p.evaluate(() => window.__apiDiscovery.state.entries[0].name), foot: await p.locator('#foot').innerText() };
  await p.close();
  for (const [name, body] of [['garbage', '<html>rate limited</html>'], ['tiny', JSON.stringify(Object.assign({}, newer, { entries: newer.entries.slice(0, 5) }))], ['hostile', JSON.stringify({ schema: 1, built: '2999', entries: 'x' })]]) {
    p = await open('/', 390, 844, (r) => r.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body }));
    await p.waitForSelector('.browse'); await p.waitForTimeout(700);
    out['live_' + name] = { origin: await p.evaluate(() => window.__apiDiscovery.state.origin), entries: await p.evaluate(() => window.__apiDiscovery.state.entries.length) };
    await p.close();
  }

  // 8. the bundled catalogue itself is unreadable: an error state with a retry, never a blank or crashed page
  p = await b.newPage({ viewport: { width: 390, height: 844 } });
  const perr = []; p.on('pageerror', (e) => perr.push(String(e)));
  let fail = true;
  await p.route('**/data/apis.json', (r) => (fail ? r.fulfill({ status: 200, contentType: 'application/json', body: '{"schema":1,"entries":[]}' }) : r.continue()));
  await p.route('**/raw.githubusercontent.com/**', (r) => r.abort());
  await p.goto(base + '/'); await p.waitForSelector('.state.error');
  out.broken = { text: await p.locator('.state.error').innerText(), pageErrors: perr.slice(), formStillThere: await p.locator('#q').isVisible() };
  fail = false; await p.locator('.state.error button').click(); await p.waitForSelector('.browse');
  out.broken.recovered = await p.locator('.cats .chip').count() > 10;
  await p.close();

  // 9. hostile catalogue text is shown as text, never run
  const evil = Object.assign({}, bundled, { entries: bundled.entries.concat([['evil-1', '<img src=x onerror="window.__pwned=1">Weather<script>window.__pwned=2</script>', '<b onclick="window.__pwned=3">weather</b> `${alert(1)}`', 'Weather', 'javascript:window.__pwned=4', 'apiKey', '"><script>window.__pwned=5</script>', 'yes', 'yes', 0, [], null]]) });
  p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.route('**/data/apis.json', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(evil) }));
  await p.route('**/raw.githubusercontent.com/**', (r) => r.abort());
  await p.goto(base + '/?q=onerror%20weather'); await p.waitForSelector('article.api[data-id="evil-1"]');
  await p.locator('article.api[data-id="evil-1"] .btn.primary').click(); await p.waitForSelector('.crit');
  out.xss = { pwned: await p.evaluate(() => window.__pwned || null), injected: await p.evaluate(() => document.querySelectorAll('#out img, #out script, #dlgBody img, #dlgBody script, [onclick], [onerror]').length),
    jsLinks: await p.evaluate(() => [...document.querySelectorAll('a')].filter((a) => !/^https?:/.test(a.href) && !a.getAttribute('href').startsWith('.')).length),
    code: await p.locator('#dlgBody pre').innerText(), external: await p.evaluate(() => [...document.querySelectorAll('#out a[target=_blank], #dlgBody a[target=_blank]')].every((a) => /noopener/.test(a.rel) && /noreferrer/.test(a.rel))) };
  await p.close();
  await b.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ fatal: String(e && e.stack || e) })); process.exit(1); });
