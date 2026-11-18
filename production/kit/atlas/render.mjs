// Render atlas looks to PNG in headless Chromium (no network: the atlas folder is served by request interception).
//   node render.mjs <out_dir> <look,look,...|all> [game,app] [scene.json]
// writes <out_dir>/<look>/<sample>.png and <out_dir>/render.json ({look: {sample: {ok, error?, ms}}}).
// The game sample is 960×540 CSS px at 2× (pixel looks: their own resolution, upscaled without smoothing);
// the app sample is a 390×844 phone screen at 2×.
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const { launch, serveGame } = await import(path.join(HERE, '..', '..', '..', 'studio', 'core', 'web', 'gamepage.mjs'));

const [out, which = 'all', samplesArg = 'game,app', sceneFile] = process.argv.slice(2);
const atlas = JSON.parse(readFileSync(path.join(HERE, 'atlas.json'), 'utf8'));
const looks = which === 'all' ? atlas.looks.map((l) => l.id) : which.split(',');
const samples = samplesArg.split(',');
const { browser } = await launch();
const report = {};
for (const id of looks) {
  report[id] = {};
  for (const sample of samples) {
    const t0 = Date.now();
    const vp = sample === 'game' ? { width: 960, height: 540 } : { width: 390, height: 844 };
    const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 2 });
    const R = { blocked: [], missing: [], requests: 0 };
    await serveGame(page, HERE, R);
    if (sceneFile) await page.route('**/__scene.json', (rt) => rt.fulfill({ status: 200, contentType: 'application/json', body: readFileSync(sceneFile) }));
    const errs = []; page.on('pageerror', (e) => errs.push(String(e))); page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    await page.goto(`http://game.local/stage.html?look=${id}&sample=${sample}` + (sceneFile ? '&scene=__scene.json' : ''));
    try { await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 }); } catch { errs.push('timed out'); }
    const err = await page.evaluate(() => window.__error || null).catch(() => 'page closed');
    if (err) errs.push(err);
    mkdirSync(path.join(out, id), { recursive: true });
    const file = path.join(out, id, `${sample}.png`);
    await page.screenshot({ path: file });
    report[id][sample] = { ok: !errs.length && !R.missing.length, errors: errs.slice(0, 5), missing: R.missing.slice(0, 5), ms: Date.now() - t0, file };
    await page.close();
    console.log(`${id}/${sample}: ${report[id][sample].ok ? 'ok' : 'FAILED ' + JSON.stringify(errs.concat(R.missing)).slice(0, 300)}`);
  }
}
await browser.close();
writeFileSync(path.join(out, 'render.json'), JSON.stringify(report, null, 1));
