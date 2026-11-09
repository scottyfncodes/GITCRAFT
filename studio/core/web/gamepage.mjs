// Shared by the browser runners that play a game folder (TestCraft's testcraft.mjs, PLAYCRAFT's playprobe.mjs):
// launch headless Chromium the GITCRAFT way, and serve a local game folder at http://game.local/ through request
// interception (no sockets, works inside the sandbox; every other host is blocked and reported).
import { createRequire } from 'node:module';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';

export const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.svg': 'image/svg+xml', '.webp': 'image/webp', '.gif': 'image/gif', '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.wav': 'audio/wav',
  '.ogg': 'audio/ogg', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.wasm': 'application/wasm', '.tmj': 'application/json',
  '.ico': 'image/x-icon', '.txt': 'text/plain', '.webmanifest': 'application/manifest+json', '.ktx2': 'image/ktx2', '.bin': 'application/octet-stream' };

export async function launch() {
  const require = createRequire(import.meta.url);
  const pwPath = [process.env.PLAYWRIGHT_MODULE, '/opt/node-tools/node_modules/playwright', 'playwright'].find((p) => { try { return p && require.resolve(p); } catch { return false; } });
  if (!pwPath) throw new Error('Playwright module not found');
  const { chromium, devices } = require(pwPath);
  const exe = [process.env.CHROMIUM_PATH, '/opt/pw-browsers/chromium'].find((p) => p && existsSync(p));
  const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--no-proxy-server', '--disable-background-networking', '--disable-component-update', '--no-first-run',
    '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'] });
  return { browser, devices };
}

// Serve `root` at http://game.local/. A build made for a sub-path (e.g. Vite `base: '/GAME/'` for GitHub Pages)
// asks for /GAME/assets/...: when a path is missing, the first segment is dropped and tried again.
export async function serveGame(page, root, R) {
  root = path.resolve(root);
  const find = (rel) => {
    let file = path.join(root, rel);
    if (file.startsWith(root) && existsSync(file) && !file.endsWith(path.sep)) return file;
    const parts = rel.split('/').filter(Boolean);
    if (parts.length > 1) { file = path.join(root, parts.slice(1).join('/')); if (file.startsWith(root) && existsSync(file)) return file; }
    if (parts.length === 1 && existsSync(path.join(root, 'index.html')) && !path.extname(parts[0])) return path.join(root, 'index.html');   // /GAME/ → index
    return null;
  };
  await page.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.host !== 'game.local') { R.blocked.push(u.href.slice(0, 200)); (R.blocked_types ||= []).push(route.request().resourceType()); return route.abort(); }
    R.requests++;
    let rel = decodeURIComponent(u.pathname); if (rel.endsWith('/')) rel += 'index.html';
    const file = find(rel);
    if (!file) { R.missing.push(rel); return route.fulfill({ status: 404, body: 'not found' }); }
    return route.fulfill({ status: 200, contentType: MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', body: readFileSync(file) });
  });
}

export function contextOptions(vp, devices) {
  return vp.device && devices[vp.device] ? { ...devices[vp.device] }
    : { viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.mobile, hasTouch: !!vp.mobile, deviceScaleFactor: vp.scale || 1 };
}
