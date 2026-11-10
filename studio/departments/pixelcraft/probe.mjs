// PIXELCRAFT probe (Playwright + Chromium). node probe.mjs request.json
//
// It looks at the rendered application, not its source. For a running app (url) or a built folder (served at
// http://app.local/ through request interception, SPA fallback to index.html), it:
//   discover   loads the entry screen and follows same-origin links and navigation-like controls (nav, tabs, tab
//              bars), breadth first, to find the app's screens and how many taps each takes to reach
//   capture    for every viewport x screen: viewport + full-page screenshots, and a DOM geometry snapshot of every
//              visible element (rect, text rect, icon rect, typography, colours, padding, radius, position, the
//              element really hit at its centre = obscured or not, clipped text), page overflow, safe-area insets
//              (emulated through CDP so env(safe-area-inset-*) resolves like on the phone)
//   axe        axe-core (WCAG 2.2 AA rules) on every screen
//   states     hover / pressed (mouse down then away, so nothing is clicked) / disabled styles on a sample of
//              controls, and a real keyboard Tab traversal: what receives focus, and whether focus is visible
//   toolbar    mobile only: the first screen again with the viewport shortened by the browser's toolbars
//   journeys   scripted or automatic user journeys: taps, typing, navigation depth, confirmation dialogs, time
//              to feedback after each action (DOM mutation, URL change), actions with no visible effect
// The probe never changes the app: it only loads, clicks, types and reads. Nothing outside the app's origin is
// fetched (blocked requests are listed).
import { writeFileSync, mkdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { launch, MIME } from '../../core/web/gamepage.mjs';

const req = JSON.parse(readFileSync(process.argv[2], 'utf8'));
const done = (o) => { writeFileSync(req._result, JSON.stringify(o)); process.exit(0); };
const OUT = req.out_dir; mkdirSync(path.join(OUT, 'screens'), { recursive: true });
const BASE = req.target.kind === 'url' ? new URL(req.target.url) : new URL('http://app.local/' + (req.target.entry || ''));
const ORIGIN = BASE.origin;
const WAIT = req.wait_ms ?? 600;
const AXE = req.axe_path && existsSync(req.axe_path) ? readFileSync(req.axe_path, 'utf8') : null;
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40) || 'screen';

// ------------------------------------------------------------------ serving
async function route(page, R) {
  const root = req.target.kind === 'folder' ? path.resolve(req.target.root) : null;
  const allowed = new Set([ORIGIN, ...(req.allow_origins || [])]);
  const find = (rel) => {
    const tries = [rel]; const parts = rel.split('/').filter(Boolean);
    if (parts.length > 1) tries.push('/' + parts.slice(1).join('/'));   // a build for a sub-path (Vite base: '/APP/')
    for (const t of tries) {
      for (const cand of [t, t + '.html', t.replace(/\/?$/, '/index.html')]) {   // Next.js static export: /about → about.html
        const f = path.join(root, cand);
        if (f.startsWith(root) && existsSync(f) && statSync(f).isFile()) return f;
      }
    }
    if (!path.extname(rel)) { const f = path.join(root, 'index.html'); if (existsSync(f)) return f; }   // SPA fallback
    return null;
  };
  await page.route('**/*', async (rt) => {
    const u = new URL(rt.request().url());
    if (u.protocol === 'data:' || u.protocol === 'blob:') return rt.continue();
    if (!allowed.has(u.origin)) { if (R.blocked.length < 40) R.blocked.push(u.href.slice(0, 160)); return rt.abort(); }
    if (!root) return rt.continue();
    let rel = decodeURIComponent(u.pathname); if (rel.endsWith('/')) rel += 'index.html';
    const file = find(rel);
    if (!file) { if (R.missing.length < 40) R.missing.push(rel); return rt.fulfill({ status: 404, body: 'not found' }); }
    return rt.fulfill({ status: 200, contentType: MIME[path.extname(file).toLowerCase()] || 'application/octet-stream', body: readFileSync(file) });
  });
}

// ------------------------------------------------------------------ in-page measurement
// Everything below runs in the page. Coordinates are CSS pixels in document space (scroll offsets added).
const SNAPSHOT = (opts) => {
  const MAX = opts.max || 1400;
  const sx = scrollX, sy = scrollY, VW = innerWidth, VH = innerHeight;
  const INTERACTIVE = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],[role=radio],[role=switch],[role=option],[tabindex]:not([tabindex="-1"]),[onclick],label[for]';
  const isInter = (el) => el.matches(INTERACTIVE) || getComputedStyle(el).cursor === 'pointer' && !el.parentElement?.closest(INTERACTIVE) && el.children.length <= 3 && (el.textContent || '').trim().length < 60 && el.tagName !== 'BODY' && el.tagName !== 'HTML';
  const kindOf = (el) => {
    const t = el.tagName.toLowerCase(), r = el.getAttribute('role'), ty = (el.getAttribute('type') || '').toLowerCase();
    if (r === 'tab' || r === 'checkbox' || r === 'radio' || r === 'switch' || r === 'menuitem' || r === 'option') return r;
    if (t === 'input') return ['checkbox', 'radio', 'range', 'color', 'file'].includes(ty) ? ty : (['submit', 'button', 'reset', 'image'].includes(ty) ? 'button' : 'input');
    if (t === 'select' || t === 'textarea') return t === 'select' ? 'select' : 'input';
    if (t === 'a') return 'link';
    if (t === 'button' || r === 'button' || t === 'summary') return 'button';
    if (r === 'link') return 'link';
    if (t === 'label') return 'label';
    if (el.hasAttribute('tabindex') && getComputedStyle(el).cursor !== 'pointer' && !el.hasAttribute('onclick')) return 'region';   // a focusable scroll region / widget, not a fake button
    return 'clickable';
  };
  const sel = (el) => {
    if (el.id && /^[A-Za-z][\w-]*$/.test(el.id) && document.querySelectorAll('#' + el.id).length === 1) return '#' + el.id;
    const tid = el.getAttribute('data-testid'); if (tid) return `[data-testid="${tid}"]`;
    const parts = []; let e = el;
    for (let i = 0; e && e.nodeType === 1 && i < 4 && e.tagName !== 'BODY'; i++) {
      let s = e.tagName.toLowerCase();
      if (e.id && /^[A-Za-z][\w-]*$/.test(e.id)) { parts.unshift('#' + e.id); break; }
      const cls = [...e.classList].filter((c) => /^[A-Za-z_-][\w-]*$/.test(c) && c.length < 30).slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
      const p = e.parentElement;
      if (p) { const same = [...p.children].filter((c) => c.tagName === e.tagName); if (same.length > 1) s += `:nth-of-type(${same.indexOf(e) + 1})`; }
      parts.unshift(s); e = e.parentElement;
    }
    return parts.join(' > ');
  };
  const px = (v) => parseFloat(v) || 0;
  const rgba = (c) => { const m = String(c).match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const effBg = (el) => {   // the colour behind an element: first opaque background up the tree (images/gradients → null = unknown)
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') return null;
      const c = rgba(cs.backgroundColor); if (c && c[3] > 0.85) return c.slice(0, 3);
    }
    const c = rgba(getComputedStyle(document.documentElement).backgroundColor); return c && c[3] > 0 ? c.slice(0, 3) : [255, 255, 255];
  };
  const textRect = (el) => {
    let r = null;
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, { acceptNode: (n) => n.textContent.trim() ? 1 : 2 });
    for (let n = w.nextNode(), k = 0; n && k < 20; n = w.nextNode(), k++) {
      const rg = document.createRange(); rg.selectNodeContents(n); const b = rg.getBoundingClientRect();
      if (b.width < 1 || b.height < 1) continue;
      r = r ? { l: Math.min(r.l, b.left), t: Math.min(r.t, b.top), r: Math.max(r.r, b.right), b: Math.max(r.b, b.bottom) } : { l: b.left, t: b.top, r: b.right, b: b.bottom };
    }
    return r && [r.l + sx, r.t + sy, r.r - r.l, r.b - r.t];
  };
  const ownText = (el) => { let s = ''; for (const n of el.childNodes) if (n.nodeType === 3) s += n.textContent; return s.replace(/\s+/g, ' ').trim(); };
  const visible = (el, cs, b) => {
    if (b.width < 1 || b.height < 1) return false;
    if (cs.visibility === 'hidden' || cs.display === 'contents') return false;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true })) return false;
    if (b.right + sx < 0 || b.bottom + sy < 0) return false;
    const clip = cs.clip && cs.clip !== 'auto' && /rect\(0/.test(cs.clip); if (clip) return false;
    return true;
  };
  const els = [], index = new Map();
  const all = document.body ? document.body.querySelectorAll('*') : [];
  for (const el of all) {
    if (els.length >= MAX) break;
    const tag = el.tagName.toLowerCase();
    if (['script', 'style', 'noscript', 'template', 'meta', 'link', 'br', 'source', 'track', 'path', 'g', 'defs', 'use', 'circle', 'rect', 'line', 'polygon', 'polyline', 'ellipse', 'stop', 'lineargradient', 'clippath', 'mask', 'symbol'].includes(tag)) continue;
    if (el instanceof SVGElement && el.tagName.toLowerCase() !== 'svg') continue;   // drawing internals (chart labels, paths) are not layout
    const b = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!visible(el, cs, b)) continue;
    const inter = isInter(el);
    const ot = ownText(el);
    const bg = rgba(cs.backgroundColor);
    const styled = (bg && bg[3] > 0.05) || px(cs.borderTopWidth) + px(cs.borderBottomWidth) + px(cs.borderLeftWidth) > 0 || cs.boxShadow !== 'none' || cs.backgroundImage !== 'none';
    const media = ['img', 'svg', 'canvas', 'video', 'picture', 'iframe'].includes(tag);
    const block = /^(block|flex|grid|list-item|table|flow-root)$/.test(cs.display);
    const parent = el.parentElement && index.has(el.parentElement) ? index.get(el.parentElement) : null;
    const e = { i: els.length, p: parent, tag, sel: '', r: [Math.round(b.left + sx), Math.round(b.top + sy), Math.round(b.width), Math.round(b.height)],
      d: (() => { let k = 0; for (let x = el; x && x !== document.body; x = x.parentElement) k++; return k; })() };
    if (inter || ot || styled || media || block || cs.position === 'fixed' || cs.position === 'sticky' || /^h[1-6]$/.test(tag)) {
      e.sel = sel(el);
      e.disp = cs.display; e.pos = cs.position;
      if (cs.position === 'fixed' || cs.position === 'sticky') e.r = [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)], e.vr = true;   // viewport space
      if (ot || inter) {
        e.fs = px(cs.fontSize); e.fw = parseInt(cs.fontWeight) || 400; e.lh = cs.lineHeight === 'normal' ? +(px(cs.fontSize) * 1.2).toFixed(1) : px(cs.lineHeight);
        e.ff = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(); e.col = rgba(cs.color); e.tt = cs.textTransform !== 'none' ? cs.textTransform : undefined;
      }
      if (ot) { e.t = ot.slice(0, 80); e.tl = ot.length; e.trect = textRect(el); }
      if (bg && bg[3] > 0.05) e.bg = bg;
      e.ebg = effBg(el);
      const pad = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft].map(px); if (pad.some((v) => v)) e.pad = pad;
      const mar = [cs.marginTop, cs.marginRight, cs.marginBottom, cs.marginLeft].map(px); if (mar.some((v) => v)) e.mar = mar;
      if (styled) e.st = 1;
      const brd = px(cs.borderTopWidth); if (brd) { e.bw = brd; e.bc = rgba(cs.borderTopColor); }
      const rad = px(cs.borderTopLeftRadius); if (rad) e.rad = Math.min(rad, 999);
      if (cs.boxShadow !== 'none') e.sh = 1;
      if (media) e.media = tag;
      if (/^h[1-6]$/.test(tag) || el.getAttribute('role') === 'heading') e.h = +(tag[1] || el.getAttribute('aria-level') || 2);
      if (parseFloat(cs.opacity) < 1) e.op = +parseFloat(cs.opacity).toFixed(2);
      if (cs.gap && cs.gap !== 'normal') e.gap = px(cs.rowGap) || px(cs.columnGap) || undefined;
      if (/flex|grid/.test(cs.display)) e.dir = cs.display.includes('grid') ? 'grid' : (cs.flexDirection.startsWith('column') ? 'col' : 'row');
      if (cs.overflowX === 'hidden' || cs.overflow === 'hidden' || cs.textOverflow === 'ellipsis') { if (el.scrollWidth > el.clientWidth + 2 && ot) e.clip = [el.scrollWidth, el.clientWidth]; }
      if (inter) {
        e.k = kindOf(el); e.inter = 1;
        e.name = (el.getAttribute('aria-label') || el.getAttribute('title') || el.innerText || el.value || el.getAttribute('alt') || el.getAttribute('placeholder') || '').replace(/\s+/g, ' ').trim().slice(0, 60);
        if (el.disabled || el.getAttribute('aria-disabled') === 'true') e.dis = 1;
        if (el.getAttribute('aria-current') || el.getAttribute('aria-selected') === 'true' || el.classList.contains('active') || el.getAttribute('aria-pressed') === 'true') e.cur = 1;
        if (!e.trect) e.trect = textRect(el);
        const ic = el.querySelector('svg,img,i[class*=icon],span[class*=icon]');
        if (ic) { const ib = ic.getBoundingClientRect(); if (ib.width > 2) e.icon = [Math.round(ib.left + sx), Math.round(ib.top + sy), Math.round(ib.width), Math.round(ib.height)]; }
        e.cur_ptr = cs.cursor === 'pointer' ? 1 : 0;
        e.outline = cs.outlineStyle !== 'none' && px(cs.outlineWidth) > 0 ? 1 : 0;
        e.sig = [cs.backgroundColor, cs.color, cs.borderTopColor, cs.boxShadow, cs.outlineStyle + px(cs.outlineWidth), cs.textDecorationLine, cs.transform, cs.opacity, cs.filter].join('|');
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') e.ifs = px(cs.fontSize);
        if (el.labels && el.labels.length) {   // a label makes the hit area bigger (tapping it toggles the control)
          let u = { l: b.left, t: b.top, r: b.right, b: b.bottom };
          for (const lb of el.labels) { const q = lb.getBoundingClientRect(); if (q.width > 0) u = { l: Math.min(u.l, q.left), t: Math.min(u.t, q.top), r: Math.max(u.r, q.right), b: Math.max(u.b, q.bottom) }; }
          if (u.r - u.l > b.width + 1 || u.b - u.t > b.height + 1) e.hit = [Math.round(u.l + sx), Math.round(u.t + sy), Math.round(u.r - u.l), Math.round(u.b - u.t)];
        }
        el.setAttribute('data-pxc', String(e.i));
      }
    }
    index.set(el, e.i); els.push(e);
  }
  // obscured controls: what is really under the centre of each control (scrolling it into view first)
  const ctrls = els.filter((e) => e.inter && !e.dis).slice(0, opts.max_obscured || 150);
  for (const e of ctrls) {
    const el = document.querySelector(`[data-pxc="${e.i}"]`); if (!el) continue;
    if (!e.vr) { const b0 = el.getBoundingClientRect(); if (b0.top < 0 || b0.bottom > innerHeight) el.scrollIntoView({ block: 'center', behavior: 'instant' }); }
    const b = el.getBoundingClientRect(); const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) { e.off = 1; continue; }
    let hit = document.elementFromPoint(cx, cy);
    const covered = (h) => h && h !== el && !el.contains(h) && !h.contains(el) && !(h.closest('label') && (h.closest('label').control === el || h.closest('label').contains(el)));
    if (covered(hit) && !e.vr) {
      el.scrollIntoView({ block: 'center', behavior: 'instant' }); const c2 = el.getBoundingClientRect();
      hit = document.elementFromPoint(c2.left + c2.width / 2, c2.top + c2.height / 2);
    }
    if (covered(hit)) {
      const lab = hit.closest('label'); if (!(lab && (lab.control === el || lab.contains(el)))) e.obs = sel(hit).slice(0, 80);
    }
  }
  window.scrollTo(sx, sy);
  const de = document.documentElement;
  const meta = document.querySelector('meta[name=viewport]');
  const canvases = els.filter((e) => e.media === 'canvas').map((e) => e.r[2] * e.r[3]);
  return { els, vw: VW, vh: VH, sw: de.scrollWidth, sh: de.scrollHeight, cw: de.clientWidth, title: document.title, url: location.pathname + location.search + location.hash,
    meta: meta ? meta.getAttribute('content') : null, lang: de.getAttribute('lang'), canvas_area: canvases.length ? Math.max(...canvases) / (VW * VH) : 0,
    text: (document.body ? document.body.innerText : '').replace(/\s+/g, ' ').slice(0, 4000), dpr: devicePixelRatio,
    root_vars: (() => { let n = 0; try { for (const s of document.styleSheets) { try { for (const r of s.cssRules) if (r.selectorText === ':root' || r.selectorText === 'html') n += [...r.style].filter((p) => p.startsWith('--')).length; } catch {} } } catch {} return n; })(),
    safe_css: (() => { try { for (const s of document.styleSheets) { try { for (const r of s.cssRules) if (/safe-area-inset/.test(r.cssText)) return true; } catch {} } } catch {} return false; })() };
};

// Generic design tells: the defaults an unguided build reaches for, read from the rendered page. Advisory only:
// tells.py turns them into questions for the report; they never become metrics, findings or score.
const TELLS = () => {
  const out = {}, MAXEX = 5;
  const add = (id, el, detail) => {
    const t = out[id] || (out[id] = { count: 0, examples: [] }); t.count++;
    if (t.examples.length < MAXEX && el) {
      const b = el.getBoundingClientRect();
      let s = el.tagName.toLowerCase(); if (el.id) s += '#' + el.id; else if (el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
      t.examples.push({ sel: s.slice(0, 80), text: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 50), r: [Math.round(b.left + scrollX), Math.round(b.top + scrollY), Math.round(b.width), Math.round(b.height)], detail });
    }
  };
  const px = (v) => parseFloat(v) || 0;
  const cols = (s) => [...String(s).matchAll(/rgba?\(([^)]+)\)/g)].map((m) => m[1].split(/[ ,/]+/).filter(Boolean).map(Number)).filter((c) => c.length < 4 || c[3] > 0.2);
  const hsl = ([r, g, b]) => {
    r /= 255; g /= 255; b /= 255; const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
    if (!d) return [0, 0, l];
    const s = d / (1 - Math.abs(2 * l - 1)); let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [(h * 60 + 360) % 360, s, l];
  };
  const shown = (el, cs, b) => b.width >= 1 && b.height >= 1 && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.05;
  const isCard = (el, cs, b) => px(cs.borderTopLeftRadius) >= 6 && b.width >= 120 && b.height >= 60 && Math.min(px(cs.paddingTop), px(cs.paddingLeft)) >= 12
    && (cs.boxShadow !== 'none' || px(cs.borderTopWidth) >= 1 || (cols(cs.backgroundColor)[0] || [0, 0, 0, 0])[3] > 0.05) && !el.matches('a,button,input,select,textarea,[role=button]');
  const EMOJI = /^\s*\p{Extended_Pictographic}|\p{Extended_Pictographic}️?\s*$/u;
  const VW = innerWidth, VH = innerHeight;
  const cards = new Set(), fams = new Map();
  for (const el of document.body ? document.body.querySelectorAll('*') : []) {
    if (el instanceof SVGElement || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|CANVAS)$/.test(el.tagName)) continue;
    const cs = getComputedStyle(el), b = el.getBoundingClientRect();
    if (!shown(el, cs, b)) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const bgi = cs.backgroundImage;
    if (own) { const f = cs.fontFamily.split(',')[0].replace(/["']/g, '').trim().toLowerCase(); fams.set(f, (fams.get(f) || 0) + 1); }
    // gradient text: a gradient painted through the glyphs
    if (/gradient/.test(bgi) && (cs.webkitBackgroundClip === 'text' || cs.backgroundClip === 'text') && (el.innerText || '').trim()) add('gradient_text', el, { background: bgi.slice(0, 120) });
    // the default purple/violet/blue gradient on a large surface or a button
    if (/gradient/.test(bgi) && (b.width * b.height > 0.12 * VW * VH || el.matches('button,a,[role=button]'))) {
      const hs = cols(bgi).map(hsl).filter(([, s]) => s > 0.35);
      if (hs.length >= 2 && hs.every(([h]) => h >= 200 && h <= 330) && hs.some(([h]) => h >= 250) && Math.max(...hs.map((x) => x[0])) - Math.min(...hs.map((x) => x[0])) >= 15) add('violet_gradient', el, { hues: hs.map((x) => Math.round(x[0])) });
    }
    // a coloured zero-offset halo used as depth
    if (cs.boxShadow !== 'none') {
      for (const part of cs.boxShadow.split(/,(?![^(]*\))/)) {
        const c = cols(part)[0]; const nums = part.replace(/rgba?\([^)]*\)/, '').trim().split(/\s+/).map(px);
        if (!c || /inset/.test(part) || nums.length < 3) continue;
        const [x, y, blur] = nums, [, s] = hsl(c);
        if (Math.abs(x) < 1 && Math.abs(y) < 1 && blur >= 8 && s > 0.4 && (c[3] ?? 1) > 0.25) { add('glow_shadow', el, { shadow: part.trim().slice(0, 80) }); break; }
      }
    }
    // a thick coloured stripe down one side of a card, list item or callout
    const bl = px(cs.borderLeftWidth), br = px(cs.borderRightWidth), bt = px(cs.borderTopWidth), bb = px(cs.borderBottomWidth);
    const side = bl >= 3 && br <= 1 ? cs.borderLeftColor : br >= 3 && bl <= 1 ? cs.borderRightColor : null;
    if (side && bt <= 1 && bb <= 1 && b.height >= 32 && b.width >= 120 && cs.borderLeftStyle !== 'none' && !/^(BLOCKQUOTE|INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) {
      const c = cols(side)[0]; if (c && hsl(c)[1] > 0.3) add('accent_stripe', el, { border: `${Math.max(bl, br)}px ${side}` });
    }
    if (isCard(el, cs, b)) cards.add(el);
    // emoji standing in for an icon system (controls and headings)
    if (el.matches('button,a,[role=button],[role=tab],h1,h2,h3,h4,li,label') && EMOJI.test(el.innerText || '') && (el.innerText || '').trim().length < 60) add('emoji_icons', el, {});
    // a small, tracked-out uppercase label sitting directly on top of a heading
    if (/^H[1-3]$/.test(el.tagName)) {
      const p = el.previousElementSibling;
      if (p && !p.matches('h1,h2,h3,h4,h5,h6,img,svg,nav')) {
        const pc = getComputedStyle(p), t = (p.innerText || '').trim(), fs = px(pc.fontSize);
        const caps = pc.textTransform === 'uppercase' || (t.length > 2 && t === t.toUpperCase() && /[A-Z]/.test(t));
        if (t && t.length <= 40 && caps && fs <= Math.min(14, px(cs.fontSize) * 0.6) && px(pc.letterSpacing) >= 0.05 * fs) add('eyebrow', p, { above: el.tagName.toLowerCase() });
      }
    }
  }
  for (const c of cards) { for (let a = c.parentElement, k = 0; a && k < 4; a = a.parentElement, k++) if (cards.has(a)) { add('nested_cards', c, { inside: (a.className && String(a.className).split(' ')[0]) || a.tagName.toLowerCase() }); break; } }
  // one default sans for everything
  const DEFAULT = /^(inter|roboto|arial|helvetica|helvetica neue|system-ui|-apple-system|blinkmacsystemfont|segoe ui|sans-serif|open sans|ui-sans-serif)$/;
  const total = [...fams.values()].reduce((a, b) => a + b, 0);
  const top = [...fams.entries()].sort((a, b) => b[1] - a[1]);
  if (total >= 8 && top.length && top[0][1] / total >= 0.9 && DEFAULT.test(top[0][0])) out.default_type = { count: 1, examples: [{ sel: 'body', text: '', r: null, detail: { family: top[0][0], share: +(top[0][1] / total).toFixed(2) } }] };
  return out;
};

const STYLE_SIG = (i) => {
  const el = document.querySelector(`[data-pxc="${i}"]`); if (!el) return null; const cs = getComputedStyle(el);
  return [cs.backgroundColor, cs.color, cs.borderTopColor, cs.boxShadow, cs.outlineStyle + parseFloat(cs.outlineWidth || 0), cs.textDecorationLine, cs.transform, cs.opacity, cs.filter].join('|');
};
const FOCUS_INFO = () => {
  const el = document.activeElement; if (!el || el === document.body || el === document.documentElement) return null;
  const cs = getComputedStyle(el), b = el.getBoundingClientRect();
  return { pxc: el.getAttribute('data-pxc'), tag: el.tagName.toLowerCase(), name: (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().slice(0, 40),
    sig: [cs.backgroundColor, cs.color, cs.borderTopColor, cs.boxShadow, cs.outlineStyle + parseFloat(cs.outlineWidth || 0), cs.textDecorationLine, cs.transform, cs.opacity, cs.filter].join('|'),
    outline: cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0, ring: cs.boxShadow !== 'none', r: [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)],
    inview: b.bottom > 0 && b.top < innerHeight };
};

// ------------------------------------------------------------------ helpers
async function settle(page, ms = WAIT) {
  try { await page.waitForLoadState('load', { timeout: 15000 }); } catch {}
  try { await page.evaluate(() => document.fonts && document.fonts.ready); } catch {}
  await page.waitForTimeout(ms);
}

function resolveUrl(p) { return new URL(p || '', BASE).href; }

async function findTarget(page, step) {
  if (step.selector) { const l = page.locator(step.selector).first(); return (await l.count()) ? l : null; }
  const text = step.click ?? step.tap ?? step.text;
  if (text == null) return null;
  for (const l of [page.getByRole('button', { name: text, exact: true }), page.getByRole('link', { name: text, exact: true }), page.getByRole('tab', { name: text, exact: true }),
    page.getByRole('button', { name: text }), page.getByRole('link', { name: text }), page.getByText(text, { exact: true }), page.getByText(text)]) {
    try { const f = l.first(); if (await f.count() && await f.isVisible()) return f; } catch {}
  }
  return null;
}

// one action; returns what happened (feedback time = first DOM mutation or URL change after the action)
async function act(page, step, touch) {
  const before = page.url();
  await page.evaluate(() => { window.__pxm = 0; window.__pxt = 0; if (!window.__pxo) { window.__pxo = new MutationObserver(() => { if (!window.__pxt) window.__pxt = performance.now(); window.__pxm++; }); window.__pxo.observe(document, { subtree: true, childList: true, characterData: true, attributes: true }); } window.__pxt0 = performance.now(); window.__pxt = 0; window.__pxm = 0; }).catch(() => {});
  const rec = { step, ok: true };
  try {
    if (step.goto != null) { await page.goto(resolveUrl(step.goto)); rec.kind = 'goto'; }
    else if (step.back) { await page.goBack(); rec.kind = 'back'; rec.tap = true; }
    else if (step.press) { await page.keyboard.press(step.press); rec.kind = 'key'; }
    else if (step.fill) { const l = await findTarget(page, { selector: step.fill.selector, text: step.fill.label }); if (!l) throw new Error('field not found'); await l.fill(String(step.fill.value ?? '')); rec.kind = 'type'; rec.chars = String(step.fill.value ?? '').length; rec.rect = await l.boundingBox(); }
    else if (step.wait) { await page.waitForTimeout(step.wait); rec.kind = 'wait'; }
    else if (step.expect != null) { rec.kind = 'expect'; rec.ok = (await page.getByText(step.expect).count()) > 0; }
    else {
      const l = await findTarget(page, step); if (!l) throw new Error(`control not found: ${step.selector || step.click || step.tap}`);
      rec.rect = await l.boundingBox(); rec.kind = 'tap'; rec.tap = true;
      if (touch) await l.tap({ timeout: 4000 }); else await l.click({ timeout: 4000 });
    }
  } catch (e) { rec.ok = false; rec.error = String(e.message || e).split('\n')[0].slice(0, 200); }
  if (rec.kind !== 'expect' && rec.kind !== 'wait') {
    await page.waitForTimeout(step.settle_ms ?? 700);
    try { await page.waitForLoadState('load', { timeout: 8000 }); } catch {}
    const m = await page.evaluate(() => ({ t: window.__pxt ? window.__pxt - window.__pxt0 : null, n: window.__pxm || 0 })).catch(() => ({ t: null, n: 0 }));
    rec.url_changed = page.url() !== before; rec.mutations = m.n;
    rec.feedback_ms = m.t != null ? Math.max(0, Math.round(m.t)) : (rec.url_changed ? 0 : null);
    if (rec.url_changed && m.t == null) rec.feedback_ms = null, rec.navigated = true;   // a full page load: the observer is gone; time = load
  }
  return rec;
}

async function reach(page, screen, touch) {
  await page.goto(resolveUrl(screen.path)); await settle(page);
  for (const s of screen.steps || []) { const r = await act(page, s, touch); if (!r.ok) return r.error; }
  if (screen.steps?.length) await settle(page, 300);
  return null;
}

const NAV_CANDIDATES = () => {
  const out = [], seen = new Set();
  const vis = (el) => { const b = el.getBoundingClientRect(); return b.width > 2 && b.height > 2 && (!el.checkVisibility || el.checkVisibility({ visibilityProperty: true })); };
  const label = (el) => (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim().slice(0, 50);
  for (const a of document.querySelectorAll('a[href]')) {
    if (!vis(a)) continue; const u = new URL(a.href, location.href);
    if (u.origin !== location.origin || a.target === '_blank' || a.hasAttribute('download') || /\.(pdf|zip|png|jpe?g|glb|mp4|json)$/i.test(u.pathname)) continue;
    const key = u.pathname + u.search + u.hash; if (seen.has(key) || (key === location.pathname + location.search + location.hash)) continue;
    if (u.hash && u.pathname === location.pathname && document.getElementById(u.hash.slice(1))) continue;   // an in-page anchor, not a screen
    seen.add(key); out.push({ kind: 'link', path: key, label: label(a) });
  }
  for (const el of document.querySelectorAll('nav button, [role=tab], [role=tablist] button, header button, footer button, [class*=tab] button, [class*=nav] button, button[data-view], button[data-tab], button[data-screen], button[data-route]')) {
    if (!vis(el) || el.disabled) continue; const l = label(el); if (!l || seen.has('b:' + l)) continue;
    seen.add('b:' + l); out.push({ kind: 'button', label: l });
  }
  return out.slice(0, 30);
};

const pat = (p) => p.replace(/\/(\d+|[0-9a-f]{8,}|[0-9a-f-]{36})(?=\/|$|\?)/gi, '/:id');
const STRUCT = () => [...document.querySelectorAll('h1,h2,h3,button,a,input,textarea,select,[role=button],label')].map((e) => e.tagName + '.' + [...e.classList].slice(0, 2).join('.')).slice(0, 200);
const jacc = (a, b) => { const A = new Set(a), B = new Set(b); let i = 0; for (const x of A) if (B.has(x)) i++; return i / Math.max(1, A.size + B.size - i); };
const overlap = (a, b) => { const A = a.split(' '), B = new Set(b.split(' ')); const sa = new Set(A); return [...sa].filter((w) => B.has(w)).length / Math.max(1, Math.max(sa.size, B.size)); };

async function discover(browser, ctxOpts, R) {
  const ctx = await browser.newContext(ctxOpts); const page = await ctx.newPage(); await route(page, R);
  const errs = []; page.on('pageerror', (e) => errs.push(String(e).slice(0, 300)));
  page.on('dialog', (d) => d.dismiss().catch(() => {}));
  const max = req.max_screens || 8;
  const screens = [{ name: 'home', path: BASE.pathname + BASE.search + BASE.hash, steps: [], depth: 0, via: 'entry' }];
  const sigs = new Set();
  const signature = async () => page.evaluate(() => location.pathname + location.hash + '|' + (document.body?.innerText || '').replace(/\s+/g, ' ').slice(0, 600));
  await reach(page, screens[0], false); sigs.add(await signature());
  screens[0]._text = await page.evaluate(() => (document.body?.innerText || '').replace(/\s+/g, ' ').slice(0, 3000)); screens[0]._pat = pat(screens[0].path); screens[0]._struct = await page.evaluate(STRUCT);
  const textOf = async () => page.evaluate(() => (document.body?.innerText || '').replace(/\s+/g, ' ').slice(0, 3000));
  for (let qi = 0; qi < screens.length && screens.length < max; qi++) {
    const from = screens[qi]; if (from.depth >= (req.max_depth || 2)) continue;
    const err = await reach(page, from, false); if (err) continue;
    const base = await textOf();
    const cands = await page.evaluate(NAV_CANDIDATES);
    for (const c of cands) {
      if (screens.length >= max) break;
      const err2 = await reach(page, from, false); if (err2) break;
      const step = c.kind === 'link' ? { click: c.label || undefined, selector: c.label ? undefined : `a[href="${c.path}"]` } : { click: c.label };
      const r = await act(page, step, false); if (!r.ok) continue;
      await settle(page, 300);
      const sig = await signature(); if (sigs.has(sig)) continue;
      const now = await textOf(); const urlNow = new URL(page.url());
      const sameUrl = urlNow.pathname + urlNow.search + urlNow.hash === from.path;
      // the same screen under another URL (/#/ and /), or another instance of a template already found (/task/1, /task/2)
      const pattern = pat(urlNow.pathname + urlNow.hash); const struct = await page.evaluate(STRUCT);
      const twin = screens.find((x) => x._text && overlap(x._text, now) > 0.9) || (!sameUrl && screens.find((x) => x._pat === pattern && x._struct && jacc(x._struct, struct) > 0.8));
      if (twin) { twin.instances = (twin.instances || 1) + (twin._text && overlap(twin._text, now) > 0.9 ? 0 : 1); sigs.add(sig); continue; }
      // a new screen: a new URL, or (same URL) most of the visible text changed — not a toggled detail
      const a = new Set(base.split(' ')), b = now.split(' '); const shared = b.filter((w) => a.has(w)).length / Math.max(1, b.length);
      if (sameUrl && shared > 0.7) continue;
      sigs.add(sig);
      const nm = slug(c.kind === 'link' && !sameUrl && pattern !== urlNow.pathname + urlNow.hash ? pattern.replace(/:id/g, 'item') : (c.label || urlNow.pathname));
      const s = sameUrl || !c.path ? { name: nm, path: from.path, steps: [...from.steps, step], depth: from.depth + 1, via: c.label }
        : { name: nm, path: urlNow.pathname + urlNow.search + urlNow.hash, steps: [], depth: from.depth + 1, via: c.label,
            link_steps: [...(from.link_steps || []), ...from.steps, step] };   // the whole path from the entry: a page two links deep keeps the first click
      if (screens.some((x) => x.name === s.name)) s.name += '-' + screens.length;
      s._text = now; s._pat = pattern; s._struct = struct;
      screens.push(s);
    }
  }
  await ctx.close();
  for (const x of screens) { delete x._text; delete x._struct; delete x._pat; }
  return { screens, errors: errs };
}

function shotName(vp, sc, kind) { return path.join(OUT, 'screens', `${slug(sc.name)}__${vp.name}${kind ? '__' + kind : ''}.png`); }

// layout stability while the screen loads (CLS: unexpected shifts without user input), measured by Chromium itself
const CLS_INIT = () => { window.__pxcls = 0; window.__pxshifts = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__pxcls += e.value; window.__pxshifts++; } }).observe({ type: 'layout-shift', buffered: true }); } catch {} };

async function capture(browser, ctxOpts, vp, screens, R) {
  const ctx = await browser.newContext(ctxOpts); await ctx.addInitScript(CLS_INIT);
  const out = [];
  for (const sc of screens) {
    const page = await ctx.newPage(); await route(page, R);
    const rec = { screen: sc.name, viewport: vp.name, page_errors: [], console_errors: [] };
    page.on('pageerror', (e) => rec.page_errors.push(String(e).slice(0, 300)));
    page.on('console', (m) => { if (m.type() === 'error' && rec.console_errors.length < 10) rec.console_errors.push(m.text().slice(0, 300)); });
    page.on('dialog', (d) => d.dismiss().catch(() => {}));
    if (vp.safe) { try { const s = await ctx.newCDPSession(page); await s.send('Emulation.setSafeAreaInsetsOverride', { insets: { top: vp.safe.top || 0, bottom: vp.safe.bottom || 0, left: vp.safe.left || 0, right: vp.safe.right || 0 } }); rec.safe_area = vp.safe; } catch (e) { rec.safe_area_error = String(e.message).slice(0, 120); } }
    const t0 = Date.now();
    const err = await reach(page, sc, vp.mobile);
    rec.load_ms = Date.now() - t0;
    if (err) { rec.error = err; out.push(rec); await page.close(); continue; }
    rec.shot = shotName(vp, sc); await page.screenshot({ path: rec.shot });
    rec.full = shotName(vp, sc, 'full'); await page.screenshot({ path: rec.full, fullPage: true });
    rec.cls = await page.evaluate(() => ({ cls: +(window.__pxcls || 0).toFixed(4), shifts: window.__pxshifts || 0 })).catch(() => null);
    rec.dom = await page.evaluate(SNAPSHOT, { max: req.max_elements || 1400 });
    if (req.tells !== false) rec.tells = await page.evaluate(TELLS).catch((e) => ({ _error: String(e.message || e).slice(0, 160) }));
    if (AXE && req.axe !== false) {
      try {
        await page.addScriptTag({ content: AXE });
        rec.axe = await page.evaluate(async () => {
          const r = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] }, resultTypes: ['violations'] });
          return { violations: r.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, url: v.helpUrl, tags: v.tags.filter((t) => /wcag/.test(t)),
            nodes: v.nodes.slice(0, 8).map((n) => { let rect = null; try { const el = document.querySelector(n.target.join(' ')); const b = el && el.getBoundingClientRect(); if (b && b.width) rect = [Math.round(b.left + scrollX), Math.round(b.top + scrollY), Math.round(b.width), Math.round(b.height)]; } catch {} return { target: n.target.join(' '), rect, summary: (n.failureSummary || '').slice(0, 240) }; }), count: v.nodes.length })), passes: r.passes.length, incomplete: r.incomplete.length, version: window.axe.version };
        });
      } catch (e) { rec.axe = { error: String(e.message || e).slice(0, 200) }; }
    }
    if (req.states !== false && (!req.state_viewports || req.state_viewports.includes(vp.name))) rec.states = await states(page, rec.dom, vp);
    if (vp.mobile && sc.depth === 0 && req.toolbar !== false && (!req.toolbar_viewports || req.toolbar_viewports.includes(vp.name))) {   // the browser's toolbars take height: does the first screen still work?
      const short = Math.max(300, vp.height - (vp.toolbar ?? 120));
      await page.setViewportSize({ width: vp.width, height: short }); await page.waitForTimeout(400);
      rec.toolbar = { height: short, shot: shotName(vp, sc, 'toolbar'), dom: await page.evaluate(SNAPSHOT, { max: 600, max_obscured: 40 }) };
      await page.screenshot({ path: rec.toolbar.shot });
      await page.setViewportSize({ width: vp.width, height: vp.height });
    }
    out.push(rec); await page.close();
  }
  await ctx.close();
  return out;
}

async function states(page, dom, vp) {
  const ctrls = dom.els.filter((e) => e.inter && e.k !== 'region').filter((e) => !e.off && !e.obs);
  // one sample per visual variant (style signature + kind), so equivalent controls are tested once
  const seen = new Set(), sample = [];
  for (const e of ctrls) { if (['checkbox', 'radio', 'range', 'color', 'file'].includes(e.k) && /^(input)$/.test(e.tag)) continue; const k = e.k + '|' + e.sig + '|' + (e.r[3] > 0 ? Math.round(e.r[3] / 4) : 0); if (seen.has(k)) continue; seen.add(k); sample.push(e); if (sample.length >= (req.max_state_samples || 10)) break; }
  const res = { hover: [], pressed: [], focus: [], disabled: [] };
  for (const e of sample) {
    if (e.dis) continue;
    const loc = page.locator(`[data-pxc="${e.i}"]`).first(); if (!(await loc.count())) continue;
    const before = await page.evaluate(STYLE_SIG, e.i);
    let box; try { await loc.scrollIntoViewIfNeeded({ timeout: 1500 }); box = await loc.boundingBox(); } catch { continue; }
    if (!box) continue;
    if (!vp.mobile) {
      await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.waitForTimeout(260);
      const h = await page.evaluate(STYLE_SIG, e.i); res.hover.push({ i: e.i, sel: e.sel, k: e.k, name: e.name, changed: h !== before });
    }
    // pressed: press, read, then move away before releasing so no click (and no navigation) happens
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2); await page.mouse.down(); await page.waitForTimeout(120);
    const p = await page.evaluate(STYLE_SIG, e.i);
    await page.mouse.move(2, 2); await page.mouse.up(); await page.waitForTimeout(200);
    res.pressed.push({ i: e.i, sel: e.sel, k: e.k, name: e.name, changed: p !== before && p !== null });
  }
  for (const e of dom.els.filter((x) => x.inter && x.dis).slice(0, 6)) res.disabled.push({ i: e.i, sel: e.sel, k: e.k, name: e.name, op: e.op || 1, sig: e.sig, cur_ptr: e.cur_ptr });
  // keyboard: real Tab presses from the top of the page
  if (!vp.mobile || req.keyboard_on_mobile) {
    await page.mouse.click(1, 1).catch(() => {});
    await page.evaluate(() => { document.activeElement && document.activeElement.blur && document.activeElement.blur(); window.scrollTo(0, 0); });
    const seenF = new Set();
    for (let k = 0; k < (req.max_tabs || 40); k++) {
      await page.keyboard.press('Tab'); await page.waitForTimeout(60);
      const f = await page.evaluate(FOCUS_INFO); if (!f) continue;
      const key = (f.pxc || f.tag + f.name); if (seenF.has(key)) break; seenF.add(key);
      const base = f.pxc ? dom.els[+f.pxc] : null;
      res.focus.push({ i: f.pxc ? +f.pxc : null, sel: base?.sel, name: f.name, visible: f.outline || (base ? f.sig !== base.sig : f.ring), outline: f.outline, inview: f.inview });
    }
    res.tab_stops = res.focus.length;
  }
  return res;
}

async function journeys(browser, ctxOpts, vp, list, R) {
  const out = [];
  for (const j of list) {
    const ctx = await browser.newContext(ctxOpts); const page = await ctx.newPage(); await route(page, R);
    const rec = { name: j.name, viewport: vp.name, auto: !!j.auto, expected_taps: j.expected_taps, steps: [], confirmations: 0, errors: [] };
    page.on('dialog', (d) => { rec.confirmations++; d.accept().catch(() => {}); });
    page.on('pageerror', (e) => rec.errors.push(String(e).slice(0, 200)));
    const t0 = Date.now();
    await page.goto(resolveUrl(j.start || BASE.pathname + BASE.search + BASE.hash)); await settle(page);
    const urls = [new URL(page.url()).pathname + new URL(page.url()).hash];
    for (const s of j.steps) {
      const before = await page.evaluate(() => (document.body?.innerText || '').length).catch(() => 0);
      const r = await act(page, s, vp.mobile);
      const after = await page.evaluate(() => ({ len: (document.body?.innerText || '').length, dialog: !!document.querySelector('dialog[open],[role=dialog],[role=alertdialog],[aria-modal=true]'),
        confirm: /\b(are you sure|confirm|really)\b/i.test((document.querySelector('dialog[open],[role=dialog],[role=alertdialog],[aria-modal=true]')?.innerText) || '') })).catch(() => ({}));
      r.dialog = after.dialog; if (after.confirm) { r.confirm_dialog = true; rec.confirmations++; }
      r.text_delta = (after.len || 0) - before;
      const u = new URL(page.url()); const key = u.pathname + u.hash; if (key !== urls[urls.length - 1]) urls.push(key);
      rec.steps.push(r);
      if (!r.ok && s.expect == null) break;
    }
    rec.ms = Date.now() - t0;
    rec.taps = rec.steps.filter((s) => s.tap).length; rec.typed = rec.steps.filter((s) => s.kind === 'type').length;
    rec.screens_visited = urls; rec.depth = urls.length - 1;
    rec.ok = rec.steps.every((s) => s.ok);
    rec.no_effect = rec.steps.filter((s) => s.tap && s.ok && !s.url_changed && !s.mutations).length;
    rec.shot = path.join(OUT, 'screens', `journey-${slug(j.name)}__${vp.name}.png`); await page.screenshot({ path: rec.shot }).catch(() => {});
    out.push(rec); await ctx.close();
  }
  return out;
}

// ------------------------------------------------------------------ main
try {
  const { browser, devices } = await launch();
  const R = { blocked: [], missing: [] };
  const opts = (vp) => ({ viewport: { width: vp.width, height: vp.height }, isMobile: !!vp.mobile, hasTouch: !!vp.touch, deviceScaleFactor: vp.scale || 1,
    userAgent: vp.mobile ? (devices[vp.ua_device || 'iPhone 13']?.userAgent) : undefined, reducedMotion: req.reduced_motion ? 'reduce' : 'no-preference' });
  const vps = req.viewports; const primary = vps.find((v) => v.mobile) || vps[0];
  let screens = req.screens;
  let disc = null;
  if (!screens || !screens.length) { disc = await discover(browser, opts(primary), R); screens = disc.screens; }
  else screens = screens.map((s, i) => ({ depth: s.depth ?? (i === 0 ? 0 : 1), steps: [], ...s }));
  const caps = [];
  for (const vp of vps) caps.push(...await capture(browser, opts(vp), vp, screens, R));
  // journeys: given ones, else automatic ones (reach each discovered screen; the entry screen's most prominent action)
  let js = req.journeys && req.journeys.length ? req.journeys : screens.filter((s) => s.depth > 0).map((s) => ({ name: `reach ${s.name}`, auto: true, steps: s.steps.length ? s.steps : (s.link_steps || [{ goto: s.path }]) }));
  const jvps = vps.filter((v) => req.journey_viewports ? req.journey_viewports.includes(v.name) : (v === primary || (!v.mobile && v.width >= 1200))).slice(0, 2);
  const jr = [];
  for (const vp of jvps) jr.push(...await journeys(browser, opts(vp), vp, js, R));
  const version = browser.version(); await browser.close();
  done({ screens, discovery: disc && { errors: disc.errors }, captures: caps, journeys: jr, journeys_used: js, blocked: R.blocked, missing: R.missing, base: BASE.href, chromium: version });
} catch (e) {
  done({ error: String(e && e.stack || e).slice(0, 2000) });
}
