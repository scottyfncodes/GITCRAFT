// Render an HTML file at phone (390×844) and desktop (1440×900) size, 2× pixels, offline.
//   node shoot.mjs <file.html> <out_dir> [--play]     writes <out_dir>/phone.png, <out_dir>/desktop.png (and play.png at 960×540 with --play)
// The HTML file's folder is served at http://game.local/ (fonts and images beside it load); no network.
import path from 'node:path';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const { launch, serveGame } = await import(path.join(HERE, '..', '..', '..', 'studio', 'core', 'web', 'gamepage.mjs'));
const [file, out, ...flags] = process.argv.slice(2);
if (!file || !out) { console.error('usage: node shoot.mjs <file.html> <out_dir> [--play]'); process.exit(2); }
mkdirSync(out, { recursive: true });
const { browser } = await launch();
const sizes = [['phone', 390, 844], ['desktop', 1440, 900]].concat(flags.includes('--play') ? [['play', 960, 540]] : []);
for (const [name, w, h] of sizes) {
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2, isMobile: name === 'phone', hasTouch: name === 'phone' });
  const R = { blocked: [], missing: [], requests: 0 };
  await serveGame(page, path.dirname(path.resolve(file)), R);
  await page.goto('http://game.local/' + path.basename(file) + (name === 'play' ? '#play' : ''));
  await page.evaluate(() => document.fonts && document.fonts.ready).catch(() => {});
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(out, name + '.png') });
  console.log(`${name}: ${path.join(out, name + '.png')}` + (R.missing.length ? ` (missing: ${R.missing.slice(0, 5).join(', ')})` : ''));
  await page.close();
}
await browser.close();
