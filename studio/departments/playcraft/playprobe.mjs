// PLAYCRAFT play probe (Playwright + Chromium). node playprobe.mjs request.json
// request: { root, entry, out_dir, viewports: [{name, device? | width,height,mobile?}], wait_ms, keys: [...],
//            pointer: bool, start_steps: [...], auto_start: bool, monkey_ms, hooks: [global names], _result }
//
// It plays the game instead of reading it. An init script samples the game's main canvas every animation frame
// (a 96x54 grey thumbnail; the change measure is the share of its pixels that changed; WebGL contexts are created with preserveDrawingBuffer so they can be read) and counts
// DOM mutations, so the probe knows, frame by frame, whether the screen changed. With that it measures:
//   idle     how much the screen moves with no input (is the world alive? is the game waiting?)
//   inputs   each control (keys from the source, click/drag, tap/hold/swipe on touch): how long until the screen
//            differs from what it would have done anyway (the idle curve measured just before), i.e. response time
//   monkey   N seconds of mixed inputs: frame times (FPS, p95), share of frames where nothing changes (dead
//            time), page errors, and which numbers on exposed game objects (window.game…) changed (score, state)
//   pause    the pause key (Escape/P) stops the screen; pressing it again resumes
//   DOM      viewport meta, touch-action, visible touch targets under 44 px, the smallest visible text,
//            horizontal overflow, the start button it pressed
import { writeFileSync, mkdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { launch, serveGame, contextOptions } from '../../core/web/gamepage.mjs';

const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const done = (o) => { writeFileSync(req._result, JSON.stringify(o)); process.exit(0); };

const SAMPLER = () => {
  const orig = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, attrs) {
    if (/webgl/.test(String(type))) attrs = Object.assign({}, attrs || {}, { preserveDrawingBuffer: true });
    return orig.call(this, type, attrs);
  };
  const W = 96, H = 54; let S = null, sx = null, prev = null, ref = null, muts = 0;
  const P = window.__pc = { frames: [], markT: 0, label: '', inputs: [] };
  new MutationObserver((l) => { muts += l.length; }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class', 'style'] });
  for (const ev of ['keydown', 'pointerdown', 'touchstart', 'mousedown']) window.addEventListener(ev, (e) => { P.inputs.push([ev, performance.now(), e.isTrusted]); }, true);
  const main = () => { let best = null, area = 0; for (const c of document.querySelectorAll('canvas')) { const r = c.getBoundingClientRect(); const a = r.width * r.height; if (a > area && r.width > 40) { area = a; best = c; } } return best; };
  const grab = () => {
    const c = main(); if (!c) return null;
    if (!S) { S = document.createElement('canvas'); S.width = W; S.height = H; sx = S.getContext('2d', { willReadFrequently: true }); }
    try { sx.drawImage(c, 0, 0, W, H); } catch { return null; }
    const d = sx.getImageData(0, 0, W, H).data, g = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) g[i] = (d[4 * i] * 0.299 + d[4 * i + 1] * 0.587 + d[4 * i + 2] * 0.114) / 255;
    return g;
  };
  // share of thumbnail pixels that changed visibly (robust to a small sprite or reticle moving, unlike a mean)
  const diff = (a, b) => { if (!a || !b) return 0; let s = 0; for (let i = 0; i < a.length; i++) if (Math.abs(a[i] - b[i]) > 0.05) s++; return s / a.length; };
  P.every = 1; P.dts = []; let n = 0;
  P.mark = (label, every) => { P.markT = performance.now(); P.label = label; P.every = every || 1; ref = grab(); P.frames = []; P.dts = []; muts = 0; n = 0; };
  let last = performance.now();
  const tick = (t) => {
    // every frame is timed (FPS); the canvas is read only every P.every frames (reading a big WebGL canvas costs time)
    if (P.dts.length < 20000) P.dts.push(+(t - last).toFixed(2));
    if (n++ % P.every === 0) {
      const g = grab();
      if (P.frames.length < 4000) P.frames.push([+(t - P.markT).toFixed(1), +(t - last).toFixed(2), +diff(g, prev).toFixed(5), +diff(g, ref).toFixed(5), muts]);
      muts = 0; prev = g;
    }
    last = t; requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
};

const KEYNAMES = { Space: ' ' };
try {
  const { browser, devices } = await launch();
  mkdirSync(req.out_dir, { recursive: true });
  const results = [];
  for (const vp of req.viewports) {
    const ctxOpts = contextOptions(vp, devices);
    const context = await browser.newContext(ctxOpts);
    const page = await context.newPage();
    const touch = !!ctxOpts.hasTouch;
    const R = { viewport: vp.name, touch, size: ctxOpts.viewport, console_errors: [], page_errors: [], blocked: [], missing: [], requests: 0, screenshots: [], probes: [] };
    page.on('console', (m) => { if (m.type() === 'error') R.console_errors.push(m.text().slice(0, 300)); });
    page.on('pageerror', (e) => R.page_errors.push(String(e).slice(0, 300)));
    await page.addInitScript(SAMPLER);
    await serveGame(page, req.root, R);
    const cdp = touch ? await context.newCDPSession(page) : null;
    const shot = async (name) => { const p = path.join(req.out_dir, `${vp.name}_${name}.png`); try { await page.screenshot({ path: p }); R.screenshots.push(p); } catch (e) { R.page_errors.push('screenshot: ' + String(e).slice(0, 120)); } return p; };
    const frames = async () => page.evaluate(() => window.__pc.frames.slice());
    const mark = async (l, every) => page.evaluate(([l, e]) => window.__pc.mark(l, e), [l, every || 1]);
    const dts = async () => page.evaluate(() => window.__pc.dts.slice());
    const t0 = Date.now();
    try { await page.goto('http://game.local/' + (req.entry || 'index.html'), { waitUntil: 'load', timeout: 45000 }); R.load_ms = Date.now() - t0; R.loaded = true; }
    catch (e) { R.loaded = false; R.page_errors.push('navigation: ' + String(e).slice(0, 200)); }
    await page.waitForTimeout(req.wait_ms || 1500);
    await shot('loaded');
    if (!R.loaded) { await context.close(); results.push(R); continue; }
    const canvasBox = async () => page.evaluate(() => {
      let best = null, area = 0; for (const c of document.querySelectorAll('canvas')) { const r = c.getBoundingClientRect(); if (r.width * r.height > area) { area = r.width * r.height; best = r; } }
      return best ? { x: best.x, y: best.y, w: best.width, h: best.height } : { x: 0, y: 0, w: innerWidth, h: innerHeight };
    });
    const audit = async () => page.evaluate(() => {
      const vis = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
      const inter = [...document.querySelectorAll('button, a[href], [role=button], input, select, [onclick], [data-action]')].filter(vis);
      const small = inter.map((el) => { const r = el.getBoundingClientRect(); return { text: (el.innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height) }; }).filter((t) => (t.w < 44 || t.h < 44) && t.w >= 8 && t.h >= 8);   // < 8 px: visually-hidden labels, not targets
      let minFont = null, minText = null; const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) { const n = walker.currentNode; const el = n.parentElement; if (!el || !n.textContent.trim() || !vis(el)) continue; const f = parseFloat(getComputedStyle(el).fontSize); if (minFont === null || f < minFont) { minFont = f; minText = n.textContent.trim().slice(0, 40); } }
      const c = [...document.querySelectorAll('canvas')].sort((a, b) => b.clientWidth * b.clientHeight - a.clientWidth * a.clientHeight)[0];
      const meta = document.querySelector('meta[name=viewport]');
      return { viewport_meta: meta ? meta.content : null, canvas_touch_action: c ? getComputedStyle(c).touchAction : null, body_touch_action: getComputedStyle(document.body).touchAction,
        interactive: inter.length, small_targets: small.slice(0, 12), small_target_count: small.length, min_font_px: minFont, min_font_text: minText,
        scroll_width: document.documentElement.scrollWidth, inner_width: innerWidth, inner_height: innerHeight, canvases: [...document.querySelectorAll('canvas')].map((x) => [x.width, x.height]), title: document.title };
    });
    R.renderer = await page.evaluate(() => { try { const g = document.createElement('canvas').getContext('webgl'); const e = g && g.getExtension('WEBGL_debug_renderer_info'); return e ? g.getParameter(e.UNMASKED_RENDERER_WEBGL) : (g ? g.getParameter(g.RENDERER) : null); } catch { return null; } });
    R.dom_loaded = await audit();
    // ---- get past the title screen: explicit steps, else the most likely start button
    R.start = { method: null };
    const ts = Date.now();
    for (const s of req.start_steps || []) {
      try {
        if (s.click) await page.mouse.click(s.click[0], s.click[1]);
        else if (s.tap) { if (touch) await page.touchscreen.tap(s.tap[0], s.tap[1]); else await page.mouse.click(s.tap[0], s.tap[1]); }
        else if (s.press) await page.keyboard.press(s.press);
        else if (s.text) await page.getByText(s.text, { exact: false }).first().click({ timeout: 3000 });
        else if (s.selector) await page.locator(s.selector).first().click({ timeout: 3000 });
        else if (s.wait) await page.waitForTimeout(s.wait);
        R.start.method = 'steps';
      } catch (e) { R.start.error = String(e).slice(0, 160); }
    }
    if (!R.start.method && req.auto_start !== false) {
      const hit = await page.evaluate(() => {
        const re = /^\s*(▶\s*)?(play|start|new game|new run|continue|tap to (play|start)|press start|begin|go!?|let'?s go|start game|play now|start run|launch)\b/i;
        const cands = [...document.querySelectorAll('button, [role=button], a, div, span')].filter((el) => {
          const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
          return r.width > 10 && r.height > 10 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05 && re.test(el.innerText || '') && (el.innerText || '').length < 40;
        });
        cands.sort((a, b) => (a.tagName === 'BUTTON' ? -1 : 0) - (b.tagName === 'BUTTON' ? -1 : 0) || a.innerText.length - b.innerText.length);
        let el = cands[0];
        if (!el) {   // no start wording: the dominant button on the title screen (at least twice the area of any other)
          const bs = [...document.querySelectorAll('button, [role=button]')].map((b) => [b, b.getBoundingClientRect()]).filter(([b, r]) => r.width > 40 && r.height > 24 && getComputedStyle(b).visibility !== 'hidden' && (b.innerText || '').trim().length < 24).sort((a, b) => b[1].width * b[1].height - a[1].width * a[1].height);
          if (bs.length && (bs.length === 1 || bs[0][1].width * bs[0][1].height >= 2 * bs[1][1].width * bs[1][1].height)) el = bs[0][0];
        }
        if (!el) return null; const r = el.getBoundingClientRect(); return { text: el.innerText.trim().slice(0, 40), x: r.x + r.width / 2, y: r.y + r.height / 2 };
      });
      if (hit) {
        if (touch) await page.touchscreen.tap(hit.x, hit.y); else await page.mouse.click(hit.x, hit.y);
        R.start = { method: 'button', text: hit.text };
      } else R.start = { method: 'none', note: 'no start button found; probes run on the first screen' };
    }
    await page.waitForTimeout(900);
    R.start.ms = Date.now() - ts;
    await shot('started');
    R.dom = await audit();
    const box = await canvasBox();
    const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
    // ---- input actions
    const touchAt = async (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });
    const actions = [];
    if (!touch) for (const k of (req.keys || []).slice(0, 7)) actions.push({ name: `key ${k}`, kind: 'key', key: k });
    if (req.pointer !== false) {
      if (touch) {
        actions.push({ name: 'tap centre', kind: 'tap', x: cx, y: cy });
        actions.push({ name: 'hold centre', kind: 'hold', x: cx, y: cy });
        actions.push({ name: 'swipe / pull back', kind: 'swipe', x: cx, y: cy, dx: 0, dy: Math.min(140, box.h / 4) });
        actions.push({ name: 'tap left third', kind: 'tap', x: box.x + box.w / 6, y: cy + box.h / 4 });
        actions.push({ name: 'tap right third', kind: 'tap', x: box.x + box.w * 5 / 6, y: cy + box.h / 4 });
      } else {
        actions.push({ name: 'click centre', kind: 'click', x: cx, y: cy });
        actions.push({ name: 'drag / pull back', kind: 'drag', x: cx, y: cy, dx: 0, dy: Math.min(160, box.h / 4) });
      }
    }
    const act = async (a, holdMs = 280) => {
      if (a.kind === 'key') { await page.keyboard.down(a.key); await page.waitForTimeout(holdMs); await page.keyboard.up(a.key); }
      else if (a.kind === 'click') { await page.mouse.click(a.x, a.y); }
      else if (a.kind === 'drag') { await page.mouse.move(a.x, a.y); await page.mouse.down(); for (let i = 1; i <= 6; i++) await page.mouse.move(a.x + a.dx * i / 6, a.y + a.dy * i / 6); await page.waitForTimeout(80); await page.mouse.up(); }
      else if (a.kind === 'tap') { await touchAt('touchStart', a.x, a.y); await page.waitForTimeout(60); await touchAt('touchEnd'); }
      else if (a.kind === 'hold') { await touchAt('touchStart', a.x, a.y); await page.waitForTimeout(holdMs + 120); await touchAt('touchEnd'); }
      else if (a.kind === 'swipe') { await touchAt('touchStart', a.x, a.y); for (let i = 1; i <= 6; i++) { await touchAt('touchMove', a.x + a.dx * i / 6, a.y + a.dy * i / 6); await page.waitForTimeout(16); } await page.waitForTimeout(80); await touchAt('touchEnd'); }
    };
    const errBefore = () => R.page_errors.length;
    // idle baseline once (the report uses it for "is the world alive")
    await mark('idle'); await page.waitForTimeout(1200); R.idle = await frames();
    for (let trial = 0; trial < (req.trials || 2); trial++) for (const a of actions) {   // two rounds: one miss in a live game is not evidence
      await mark('idle-before'); await page.waitForTimeout(700); const idle = await frames();
      const e0 = errBefore();
      await mark('input'); const tIn = await page.evaluate(() => performance.now());
      await act(a); await page.waitForTimeout(450);
      const fr = await frames();
      const seen = await page.evaluate((t) => window.__pc.inputs.filter((x) => x[1] >= t - 5).length, tIn);
      R.probes.push({ name: a.name, kind: a.kind, trial, idle, frames: fr, events_seen: seen, errors: R.page_errors.slice(e0) });
      await page.waitForTimeout(250);
    }
    // ---- hooks: numbers on exposed game objects, before and after the mixed session
    const readHooks = async () => page.evaluate((names) => {
      const out = {};
      for (const n of names) {
        let o; try { o = window[n]; } catch { continue; }
        if (o === null || o === undefined) continue;
        if (typeof o === 'number' || typeof o === 'string' || typeof o === 'boolean') { out[n] = o; continue; }
        if (typeof o !== 'object') continue;
        const walk = (obj, pre, depth) => {
          let keys = []; try { keys = Object.keys(obj).slice(0, 60); } catch { return; }
          for (const k of keys) {
            let v; try { v = obj[k]; } catch { continue; }
            if (typeof v === 'number' && isFinite(v)) out[pre + k] = +v.toFixed(3);
            else if (typeof v === 'string' && v.length < 40) out[pre + k] = v;
            else if (typeof v === 'boolean') out[pre + k] = v;
            else if (v && typeof v === 'object' && depth < 1 && !Array.isArray(v) && !(v instanceof Node)) walk(v, pre + k + '.', depth + 1);
          }
        };
        walk(o, n + '.', 0);
      }
      return out;
    }, req.hooks || []);
    R.hooks_before = await readHooks();
    // ---- mixed session ("monkey"): every input again, in a seeded shuffled order, for monkey_ms
    const ms = req.monkey_ms || 8000; let seed = 1234567;
    const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    await mark('monkey', 4); const e0 = errBefore(); const tm = Date.now(); let n = 0;
    const pool = actions.filter((a) => a.kind !== 'drag' || rnd() < 0.5);
    while (Date.now() - tm < ms && pool.length) {
      const a = pool[Math.floor(rnd() * pool.length)];
      try { await act(a, 120 + Math.floor(rnd() * 400)); } catch (e) { R.page_errors.push('input: ' + String(e).slice(0, 120)); }
      n++; await page.waitForTimeout(120 + Math.floor(rnd() * 380));
      if (n === 4) await shot('playing');
    }
    if (!pool.length) await page.waitForTimeout(ms);
    R.monkey = { ms: Date.now() - tm, inputs: n, frames: await frames(), dts: await dts(), errors: R.page_errors.slice(e0) };
    R.hooks_after = await readHooks();
    await mark('perf', 1e9); await page.waitForTimeout(req.perf_ms || 3000); R.perf_dts = await dts();
    await shot('after_play');
    // ---- pause, last (a pause menu must not swallow the other probes): a primary action first so the game is moving
    const pk = (req.pause_keys || []).find(Boolean);
    if (pk && !touch && actions.length) {
      await act(actions[0], 200); await page.waitForTimeout(120);
      await mark('pre-pause'); await page.waitForTimeout(400); const before = await frames();
      await page.keyboard.press(pk); await page.waitForTimeout(200);
      await mark('paused'); await page.waitForTimeout(700); const during = await frames();
      await shot('paused');
      await page.keyboard.press(pk); await page.waitForTimeout(300);
      R.pause = { key: pk, after_action: actions[0].name, before, during };
    }
    R.dom_end = await audit();
    await context.close();
    results.push(R);
  }
  await browser.close();
  done({ results, keynames: KEYNAMES });
} catch (e) { done({ error: String(e && e.stack || e).slice(0, 2000) }); }
