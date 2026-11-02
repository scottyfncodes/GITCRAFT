/* GITCRAFT control room. Vanilla JS, no build step, no third-party code except three.js for the 3D viewer
   (served from MeshCraft's own engine-check install locally). Every DOM node is built with h(), never
   innerHTML, so tool output cannot inject markup. */
"use strict";
(() => {
const SNAP = !!window.GITCRAFT_SNAPSHOT;
// DOM append/replaceChildren turn null into the text "null"; optional pieces here are often null, so drop them.
const clean = (a) => a.flat(Infinity).filter((x) => x != null && x !== false);
for (const P of [Element.prototype, DocumentFragment.prototype]) {
  const rc = P.replaceChildren, ap = P.append;
  P.replaceChildren = function (...a) { return rc.apply(this, clean(a)); };
  P.append = function (...a) { return ap.apply(this, clean(a)); };
}
const $ = (s, el = document) => el.querySelector(s);

// ---------------------------------------------------------------- tiny DOM helper
function h(tag, attrs, ...kids) {
  const el = tag === "svg" || tag === "path" || tag === "circle" || tag === "rect"
    ? document.createElementNS("http://www.w3.org/2000/svg", tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "class") el.setAttribute("class", v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k === "value" && "value" in el) el.value = v;
    else if (k === "checked" || k === "selected" || k === "disabled") el[k] = !!v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) el.append(kid instanceof Node ? kid : String(kid));
  return el;
}
const ICONS = {
  home: "M4 11l8-7 8 7v9a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1z",
  run: "M7 4l13 8-13 8z",
  jobs: "M4 6h16M4 12h16M4 18h10",
  library: "M4 5h4v15H4zM10 5h4v15h-4zM16.5 5.5l3.8-1 3.7 14.6-3.8 1z",
  tools: "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6-2.4-.6-.6-2.4z",
  close: "M6 6l12 12M18 6L6 18", copy: "M9 9h11v11H9zM5 15V4h11", cube: "M12 3l8 4.5v9L12 21l-8-4.5v-9zM12 12l8-4.5M12 12v9M12 12L4 7.5",
};
const icon = (n) => h("svg", { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.9", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
  h("path", { d: ICONS[n] }));

// ---------------------------------------------------------------- data layer (live API or read-only snapshot)
let TOKEN = "";
try {
  const m = location.hash.match(/token=([\w-]+)/);
  if (m) { TOKEN = m[1]; sessionStorage.setItem("gcToken", TOKEN); history.replaceState(null, "", location.pathname + "#home"); }
  else TOKEN = sessionStorage.getItem("gcToken") || "";
} catch (e) { /* storage blocked: token only lives in this page */ }

const snapCache = {};
async function snapJSON(p) { if (!(p in snapCache)) { const r = await fetch(p); if (!r.ok) throw new Error(`not in this snapshot (${p})`); snapCache[p] = await r.json(); } return snapCache[p]; }
const api = {
  async get(path) {
    if (SNAP) return snapGet(path);
    const r = await fetch(path, { headers: { "X-GITCRAFT-Token": TOKEN } });
    const d = await r.json().catch(() => ({ error: r.statusText }));
    if (!r.ok) throw new Error(d.error || r.statusText);
    return d;
  },
  async post(path, body) {
    if (SNAP) throw new Error("This is a read-only preview snapshot. Run scripts/ui.sh to use the live control room.");
    const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "X-GITCRAFT-Token": TOKEN }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({ error: r.statusText }));
    if (!r.ok) throw new Error(d.error || r.statusText);
    return d;
  },
};
async function snapGet(path) {
  const u = new URL(path, "http://x"); const p = u.pathname;
  if (p === "/api/overview") return snapJSON("data/overview.json");
  if (p === "/api/jobs") return snapJSON("data/jobs.json");
  if (p.startsWith("/api/jobs/")) return snapJSON(`data/jobs/${p.split("/").pop()}.json`);
  if (p === "/api/library") return snapJSON("data/library.json");
  if (p.startsWith("/api/library/")) {
    const id = p.split("/").pop(); let v = u.searchParams.get("version");
    if (!v) v = (await snapJSON("data/library.json")).assets.find((a) => a.id === id).latest;
    return snapJSON(`data/library/${id}.v${v}.json`);
  }
  if (p === "/api/tools") { const t = (await snapJSON("data/tools.json"))[u.searchParams.get("tool")]; if (!t || !t.ok) throw new Error("not discovered in this snapshot"); return t; }
  if (p === "/api/calls") return { calls: [] };
  throw new Error("not available in the read-only snapshot");
}
const fileURL = (f) => SNAP ? (f.file || null) : `/files?path=${encodeURIComponent(f.abs || f.path || f)}`;

// a tool call: start it, then poll until it finishes
async function callTool(tool, name, args, onTick) {
  const c = await api.post("/api/call", { tool, name, arguments: args || {} });
  for (;;) {
    await new Promise((r) => setTimeout(r, 900));
    const s = await api.get(`/api/calls/${c.id}`);
    if (onTick) onTick(s);
    if (s.status !== "running") return s;
  }
}

// ---------------------------------------------------------------- shared UI pieces
function toast(msg, bad) {
  const t = h("div", { class: "toast" + (bad ? " bad" : "") }, msg); $("#toasts").append(t);
  setTimeout(() => t.remove(), bad ? 7000 : 3200);
}
const STATUS = { done: ["ok", "Done"], done_with_fallback: ["warn", "Done with fallback"], failed: ["bad", "Failed"], running: ["run", "Running"],
  queued: ["run", "Queued"], error: ["bad", "Error"], pass: ["ok", "Checks pass"], "needs-fix": ["bad", "Needs fixes"], "not validated": ["", "Not validated"] };
const chip = (s, label) => { const [c, l] = STATUS[s] || ["", s]; return h("span", { class: `chip ${c}` }, label || l); };
const stripeOf = (s) => (STATUS[s] || [""])[0];
const ago = (iso) => { if (!iso) return ""; const t = typeof iso === "number" ? iso * 1000 : Date.parse(iso); const s = (Date.now() - t) / 1000;
  return s < 60 ? "just now" : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : new Date(t).toLocaleDateString(); };
const bytes = (n) => n == null ? "" : n < 1024 ? `${n} B` : n < 1 << 20 ? `${(n / 1024).toFixed(1)} KB` : `${(n / (1 << 20)).toFixed(1)} MB`;
const base = (p) => String(p || "").split("/").pop();
const breakable = (s) => String(s).split("_").flatMap((part, i) => i ? ["_", h("wbr"), part] : [part]);   // wrap ids at underscores only
const short = (sha) => sha ? `${sha.slice(0, 12)}…` : "";
function copyBtn(text, label) {
  return h("button", { class: "btn small ghost", type: "button", "aria-label": label || "Copy", onclick: async (e) => {
    e.stopPropagation();
    try { await navigator.clipboard.writeText(text); toast("Copied"); } catch (_) { prompt("Copy:", text); }
  } }, icon("copy"), label ? h("span", {}, label) : null);
}
function jsonBlock(v) { return h("pre", { class: "json" }, typeof v === "string" ? v : JSON.stringify(v, null, 2)); }
function img(f, alt) { const u = fileURL(f); return u ? h("img", { src: u, alt: alt || base(f.path), loading: "lazy", decoding: "async" }) : h("div", { class: "muted small" }, "not in snapshot"); }

let sheetStack = [];
function sheet(title, build, opts = {}) {
  const root = $("#sheet-root"); const prevFocus = document.activeElement;
  const close = () => { scrim.remove(); panel.remove(); sheetStack = sheetStack.filter((x) => x !== close); prevFocus && prevFocus.focus && prevFocus.focus(); opts.onclose && opts.onclose(); };
  const scrim = h("div", { class: "scrim", onclick: close });
  const content = h("div", { class: "content" });
  const panel = h("section", { class: "sheet", role: "dialog", "aria-modal": "true", "aria-label": title },
    h("header", {}, h("h2", {}, title), h("button", { class: "icon-btn", type: "button", "aria-label": "Close", onclick: close }, icon("close"))), content);
  root.append(scrim, panel); sheetStack.push(close);
  Promise.resolve(build(content, close)).catch((e) => content.replaceChildren(h("div", { class: "banner bad" }, String(e.message || e))));
  setTimeout(() => panel.querySelector("button").focus(), 30);
  return close;
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sheetStack.length) sheetStack[sheetStack.length - 1](); });

// ---------------------------------------------------------------- routing
const PAGES = [["home", "Home"], ["run", "Run"], ["jobs", "Jobs"], ["library", "Library"], ["tools", "Tools"]];
let current = null, pageTimer = null;
function nav() {
  const mk = () => PAGES.map(([id, label]) => h("a", { href: `#${id}`, dataset: { page: id } }, icon(id), h("span", {}, label)));
  $("#nav-tabs").replaceChildren(...mk()); $("#nav-rail").replaceChildren(...mk());
}
function route() {
  const id = (location.hash.slice(1) || "home").replace(/[^a-z]/g, "");
  const page = PAGES.find(([p]) => p === id) ? id : "home";
  document.querySelectorAll("[data-page]").forEach((a) => a.setAttribute("aria-current", a.dataset.page === page ? "page" : "false"));
  if (pageTimer) { clearInterval(pageTimer); pageTimer = null; }
  current = page; const main = $("#main"); main.replaceChildren();
  ({ home: pageHome, run: pageRun, jobs: pageJobs, library: pageLibrary, tools: pageTools })[page](main);
  window.scrollTo(0, 0);
}
function head(eyebrow, title, sub, ...actions) {
  return h("div", { class: "head" }, h("div", {}, h("div", { class: "eyebrow" }, eyebrow), h("h1", {}, title), sub ? h("p", { class: "sub" }, sub) : null),
    actions.length ? h("div", { class: "row" }, ...actions) : null);
}
const loading = (n = 3) => h("div", { class: "stack" }, ...Array.from({ length: n }, () => h("div", { class: "skeleton", style: "height:64px" })));
function failBox(e) { return h("div", { class: "banner bad" }, String(e.message || e)); }

// ---------------------------------------------------------------- Home
async function pageHome(main) {
  main.append(head(SNAP ? "Read-only preview" : "Local · 127.0.0.1", "Control room", "Every action goes through the same guard and kernel sandbox Claude Code uses. Nothing here has network access."));
  const body = loading(4); main.append(body);
  let ov; try { ov = await api.get("/api/overview"); } catch (e) { body.replaceChildren(failBox(e)); return; }
  const sb = ov.sandbox.landlock_abi ? ["ok", `Landlock ABI ${ov.sandbox.landlock_abi}`] : ["bad", "No kernel sandbox"];
  const ok = ov.tools.filter((t) => t.installed && t.registered).length;
  const status = h("div", { class: "card pad" },
    h("div", { class: "band" }, h("span", { class: `chip ${sb[0]}` }, sb[1]), h("span", { class: "chip ok" }, `Network ${ov.network}`),
      h("span", { class: `chip ${ok === ov.tools.length ? "ok" : "warn"}` }, `${ok}/${ov.tools.length} tools ready`)),
    h("dl", { class: "kv", style: "margin-top:14px" }, h("dt", {}, "Workspace roots"), h("dd", { class: "mono" }, ov.roots.join("  ·  ")),
      h("dt", {}, "3D library"), h("dd", { class: "mono" }, ov.library),
      h("dt", {}, "Audit log"), h("dd", {}, `${ov.audit.calls} calls · ${ov.audit.failed} failed · ${ov.audit.refused} refused by policy`)));
  const tools = h("div", { class: "grid" }, ov.tools.map((t) => toolCard(t)));
  const capsBox = h("div", { class: "card pad" }, h("div", { class: "skeleton" }));
  const jobsBox = h("div", { class: "list" }, h("div", { class: "skeleton", style: "height:56px" }));
  body.replaceChildren(status,
    h("div", { class: "section-title" }, h("h2", {}, "Tools"), SNAP ? null : h("button", { class: "btn small", type: "button", onclick: discoverAll }, "Discover all")), tools,
    h("div", { class: "section-title" }, h("h2", {}, "3D capabilities on this machine")), capsBox,
    h("div", { class: "section-title" }, h("h2", {}, "Recent jobs"), h("a", { href: "#jobs", class: "small" }, "All jobs")), jobsBox);
  async function discoverAll(e) {
    e.target.disabled = true; e.target.textContent = "Connecting…";
    try { const r = await api.post("/api/discover", {}); const bad = Object.entries(r).filter(([, v]) => !v.ok);
      toast(bad.length ? `${bad.length} tool(s) failed to connect: ${bad.map(([k]) => k).join(", ")}` : "All tools connected", bad.length > 0); route(); }
    catch (err) { toast(err.message, true); e.target.disabled = false; }
  }
  caps(capsBox);
  api.get("/api/jobs").then((j) => jobsBox.replaceChildren(...(j.jobs.length ? j.jobs.slice(0, 5).map(jobRow) : [h("div", { class: "empty" }, "No MeshCraft jobs yet. Run a pipeline from Run.")]))).catch((e) => jobsBox.replaceChildren(failBox(e)));
}
function toolCard(t) {
  const ready = t.installed && t.registered;
  return h("button", { class: `card stripe ${ready ? "ok" : "bad"}`, type: "button", onclick: () => openServer(t.name) },
    h("div", { class: "spread" }, h("span", { class: "tool-name" }, t.name), h("span", { class: `chip ${ready ? "ok" : "bad"}` }, ready ? "Ready" : !t.installed ? "Not installed" : "Not registered")),
    h("div", { class: "small muted", style: "margin-top:6px" }, t.version || "version unknown"),
    h("div", { class: "row small", style: "margin-top:8px" }, t.tool_count != null ? h("span", { class: "chip plain" }, `${t.tool_count} tools`) : h("span", { class: "chip plain" }, "not connected yet"),
      t.denied.length ? h("span", { class: "chip warn" }, `policy blocks ${t.denied.join(", ")}`) : null));
}
async function caps(box) {
  let hw;
  try { hw = SNAP ? await snapJSON("data/hardware.json") : (await callTool("meshcraft", "hardware_probe", {})).result; } catch (e) { box.replaceChildren(failBox(e)); return; }
  if (!hw || !hw.capabilities) { box.replaceChildren(failBox(typeof hw === "string" ? hw : "hardware_probe failed")); return; }
  const rows = Object.entries(hw.capabilities).map(([k, c]) => h("div", { class: "item", style: "padding:8px 0;border-top:1px solid var(--line)" },
    h("span", { class: "title" }, k.replace(/_/g, " ")), h("span", { class: `chip ${c.available ? "ok" : "warn"}` }, c.available ? "Available" : "Not available"),
    h("div", { class: "meta" }, c.available ? (c.how || "") + (c.note ? ` · ${c.note}` : "") : c.reason)));
  box.replaceChildren(h("div", { class: "band" }, h("span", { class: "chip plain" }, `${hw.cpu.threads} CPU threads`), h("span", { class: "chip plain" }, `${hw.ram.total_gb} GB RAM`),
    h("span", { class: `chip ${hw.gpus.length ? "ok" : "plain"}` }, hw.gpus.length ? hw.gpus.map((g) => g.name).join(", ") : "No GPU (CPU rendering)")), h("div", { style: "margin-top:8px" }, rows));
}

// ---------------------------------------------------------------- Run
let runMode = "pipeline";
function pageRun(main) {
  main.append(head("MeshCraft and every other tool", "Run", "Run a full MeshCraft pipeline, ask which path fits a request, or call any tool through the guarded launcher."));
  const seg = h("div", { class: "seg", role: "group", "aria-label": "Run mode" });
  const box = h("div", { class: "stack", style: "margin-top:16px" });
  const modes = [["pipeline", "Pipeline"], ["route", "Advice"], ["tool", "Any tool"]];
  const draw = () => { seg.replaceChildren(...modes.map(([m, l]) => h("button", { type: "button", "aria-pressed": String(runMode === m), onclick: () => { runMode = m; draw(); } }, l)));
    box.replaceChildren(); ({ pipeline: runPipeline, route: runRoute, tool: runAnyTool })[runMode](box); };
  main.append(seg, box); draw();
}
function snapNotice() { return SNAP ? h("div", { class: "banner info" }, "Read-only preview: forms are shown with sample values, but running needs the live control room (scripts/ui.sh).") : null; }

async function runPipeline(box) {
  box.append(snapNotice());
  const form = h("form", { class: "form card pad" }); box.append(form);
  let templates = [], profiles = {};
  if (!SNAP) {
    form.append(h("div", { class: "muted small" }, "Loading templates from MeshCraft…"));
    try { const [t, p] = await Promise.all([callTool("meshcraft", "list_templates"), callTool("meshcraft", "list_profiles")]);
      templates = t.result; profiles = p.result; } catch (e) { form.replaceChildren(failBox(e)); return; }
  } else {
    templates = ["chest", "crab", "flag", "lantern", "sail", "sun_figurehead"].map((id) => ({ id, params: {} }));
    profiles = Object.fromEntries(["three-web-toon", "three-web-atlas", "godot-glb", "unity-fbx", "obj-static", "web-pbr", "stl-print"].map((k) => [k, { description: "" }]));
  }
  const ov = SNAP ? await snapJSON("data/overview.json") : await api.get("/api/overview");
  const root = ov.roots[0];
  const f = {
    asset_id: h("input", { type: "text", id: "p-asset", value: "new_asset", autocapitalize: "off", autocorrect: "off", spellcheck: "false", required: true, pattern: "[A-Za-z0-9_\\-]+" }),
    template: h("select", { id: "p-template" }, templates.map((t) => h("option", { value: t.id }, t.id))),
    palette: h("input", { type: "text", id: "p-palette", placeholder: "palette .json / .css / .gpl / .ase" }),
    references: h("input", { type: "text", id: "p-refs", placeholder: "reference images, comma-separated (optional)" }),
    out_dir: h("input", { type: "text", id: "p-out", value: `${root}/gitcraft-out/new_asset` }),
    size: h("select", { id: "p-size" }, [256, 384, 640].map((s) => h("option", { value: s, selected: s === 384 }, `${s} px previews`))),
    library: h("input", { type: "checkbox", id: "p-lib", checked: true }),
  };
  const params = h("div", { class: "two" });
  const drawParams = () => { const t = templates.find((x) => x.id === f.template.value) || { params: {} };
    params.replaceChildren(...Object.entries(t.params || {}).map(([k, s]) => paramField(k, s))); };
  f.template.addEventListener("change", drawParams); drawParams();
  f.asset_id.addEventListener("input", () => { f.out_dir.value = `${root}/gitcraft-out/${f.asset_id.value || "asset"}`; });
  const profBoxes = Object.entries(profiles).map(([k, p]) => h("label", { class: "check", title: p.description || "" }, h("input", { type: "checkbox", value: k, checked: k === "three-web-toon" }), k));
  form.append(
    h("div", { class: "two" }, h("label", { class: "field", for: "p-asset" }, "Asset id", f.asset_id, h("span", { class: "hint" }, "letters, digits, _ and -")),
      h("label", { class: "field", for: "p-template" }, "Template", f.template)),
    params,
    h("label", { class: "field", for: "p-palette" }, "Brand palette", h("div", { class: "pick" }, f.palette, pickBtn(f.palette, [".json", ".css", ".gpl", ".ase"])),
      h("span", { class: "hint" }, "the project's palette file; templates take their colours from it")),
    h("label", { class: "field", for: "p-refs" }, "2D references", h("div", { class: "pick" }, f.references, pickBtn(f.references, [".png", ".jpg", ".jpeg", ".webp"], true))),
    h("label", { class: "field", for: "p-out" }, "Output folder", h("div", { class: "pick" }, f.out_dir, pickBtn(f.out_dir, null, false, true)), h("span", { class: "hint" }, "must be inside a workspace root")),
    h("fieldset", { style: "border:0;padding:0;margin:0" }, h("legend", { class: "small", style: "font-weight:600;margin-bottom:6px" }, "Export profiles"), h("div", { class: "grid tight" }, profBoxes)),
    h("div", { class: "two" }, h("label", { class: "field", for: "p-size" }, "Previews", f.size), h("label", { class: "check", style: "align-self:end" }, f.library, "Add to the 3D library")),
    h("button", { class: "btn primary block", type: "submit", disabled: SNAP }, "Run pipeline"));
  const out = h("div", { class: "stack" }); box.append(out);
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); if (!form.reportValidity()) return;
    const prm = {}; params.querySelectorAll("[data-param]").forEach((el) => { if (el.value !== "") prm[el.dataset.param] = el.type === "number" ? Number(el.value) : el.type === "checkbox" ? el.checked : el.value; });
    const brief = { asset_id: f.asset_id.value, template: f.template.value, out_dir: f.out_dir.value, params: prm,
      profiles: profBoxes.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value),
      preview: { size: Number(f.size.value) }, library: f.library.checked };
    if (f.palette.value) brief.palette = f.palette.value;
    if (f.references.value) brief.references = f.references.value.split(",").map((s) => s.trim()).filter(Boolean);
    if (!brief.profiles.length) { toast("Pick at least one export profile", true); return; }
    runAndShow(out, "meshcraft", "run_pipeline", { brief }, pipelineResult);
  });
}
function paramField(k, s) {
  const id = `prm-${k}`; const lab = (el) => h("label", { class: "field", for: id }, k.replace(/_/g, " "), el, s.description ? h("span", { class: "hint" }, s.description) : null);
  if (s.enum) return lab(h("select", { id, dataset: { param: k } }, s.enum.map((v) => h("option", { value: v, selected: v === s.default }, String(v)))));
  if (typeof s.default === "boolean") return h("label", { class: "check" }, h("input", { type: "checkbox", id, dataset: { param: k }, checked: s.default }), k.replace(/_/g, " "));
  if (typeof s.default === "number") return lab(h("input", { type: "number", id, step: "any", dataset: { param: k }, value: s.default }));
  return lab(h("input", { type: "text", id, dataset: { param: k }, value: s.default ?? "" }));
}
async function runAndShow(out, tool, name, args, render) {
  const card = h("div", { class: "card pad stripe run" }); out.prepend(card);
  const t0 = Date.now(); const st = h("span", { class: "chip run" }, "Running"); const el = h("span", { class: "small muted tabular" }, "0 s");
  card.append(h("div", { class: "spread" }, h("h2", {}, `${tool} · ${name}`), st), el);
  const tick = setInterval(() => { el.textContent = `${Math.round((Date.now() - t0) / 1000)} s · through scripts/mcp.sh (guard + sandbox)`; }, 500);
  try {
    const r = await callTool(tool, name, args);
    clearInterval(tick); const ok = r.status === "done";
    card.className = `card pad stripe ${ok ? "ok" : "bad"}`; st.replaceWith(chip(ok ? "done" : "failed", ok ? "Done" : "Failed"));
    el.textContent = `${Math.round((r.finished - r.started) * 10) / 10} s`;
    card.append(ok && render ? render(r.result) : resultView(r.result, ok));
  } catch (e) { clearInterval(tick); card.className = "card pad stripe bad"; st.replaceWith(chip("failed")); card.append(failBox(e)); }
}
function pipelineResult(r) {
  const s = r.validation?.summary || {}; const job = r.job || {}; const lib = r.library || {};
  const previews = (r.previews || []).filter((p) => /\.png$/.test(p.path));
  return h("div", { class: "stack", style: "margin-top:12px" },
    h("div", { class: "band" }, h("span", { class: `chip ${s.fail ? "bad" : "ok"}` }, `${s.pass || 0} pass · ${s.warn || 0} warn · ${s.fail || 0} fail`),
      job.status ? chip(job.status) : null, lib.version ? h("span", { class: "chip plain" }, `library v${lib.version}${lib.same_as ? ` = v${lib.same_as}` : ""}`) : null),
    job.fallback ? h("div", { class: "banner warn" }, `Fallback used: ${job.fallback}`) : null,
    previews.length ? h("div", { class: "gallery" }, previews.map((p) => h("figure", {}, h("div", { class: "thumb" }, img(p)), h("figcaption", {}, base(p.path))))) : null,
    h("div", { class: "list" }, (r.exports || []).map((e) => h("div", { class: "item card" }, h("span", { class: "title" }, base(e.path)), h("span", { class: "chip plain" }, e.profile),
      h("div", { class: "meta" }, h("span", {}, bytes(e.bytes)), h("span", { class: "hash" }, short(e.sha256)))))),
    h("div", { class: "row" }, lib.asset ? h("button", { class: "btn", type: "button", onclick: () => openAsset(lib.asset, lib.version) }, "Open in library") : null,
      job.id ? h("button", { class: "btn ghost", type: "button", onclick: () => openJob(job.id) }, "Job record") : null));
}
function resultView(v, ok) {
  const imgs = []; JSON.stringify(v, (k, x) => { if (typeof x === "string" && /^\/.+\.(png|jpe?g|webp)$/i.test(x) && !imgs.includes(x)) imgs.push(x); return x; });
  return h("div", { class: "stack", style: "margin-top:12px" }, !ok ? h("div", { class: "banner bad" }, typeof v === "string" ? v.split("\n")[0] : "The tool reported an error") : null,
    imgs.length ? h("div", { class: "gallery" }, imgs.slice(0, 12).map((p) => h("figure", {}, h("div", { class: "thumb" }, img({ abs: p, path: p })), h("figcaption", {}, base(p))))) : null,
    h("details", { open: !imgs.length }, h("summary", { class: "small muted" }, "Full result"), jsonBlock(v)));
}

// file / folder picker over the workspace roots
function pickBtn(input, exts, multi, folder) {
  return h("button", { class: "btn", type: "button", disabled: SNAP, "aria-label": folder ? "Choose folder" : "Choose file", onclick: () => picker(input, exts, multi, folder) }, "Browse");
}
function picker(input, exts, multi, folder) {
  sheet(folder ? "Choose a folder" : multi ? "Choose files" : "Choose a file", async (c, close) => {
    const chosen = new Set(multi ? input.value.split(",").map((s) => s.trim()).filter(Boolean) : []);
    const ov = await api.get("/api/overview");
    const draw = async (path) => {
      c.replaceChildren(loading(2));
      let d; try { d = await api.get(`/api/fs?path=${encodeURIComponent(path || ov.roots[0])}${exts ? `&ext=${exts.join(",")}` : ""}`); } catch (e) { c.replaceChildren(failBox(e)); return; }
      const rootsBar = ov.roots.length > 1 ? h("div", { class: "filters" }, ov.roots.map((r) => h("button", { type: "button", "aria-pressed": String(d.path.startsWith(r)), onclick: () => draw(r) }, base(r) || r))) : null;
      c.replaceChildren(rootsBar, h("div", { class: "mono small wrap muted" }, d.path),
        h("div", { class: "list" },
          d.parent ? h("button", { class: "card", type: "button", onclick: () => draw(d.parent) }, "↑ Up one folder") : null,
          d.entries.map((e) => h("button", { class: "card item", type: "button", onclick: () => {
            if (e.dir) return draw(e.path);
            if (multi) { chosen.has(e.path) ? chosen.delete(e.path) : chosen.add(e.path); input.value = [...chosen].join(", "); draw(d.path); }
            else { input.value = e.path; close(); } } },
            h("span", { class: "title" }, (e.dir ? "📁 " : "") + e.name), multi && chosen.has(e.path) ? h("span", { class: "chip ok" }, "Chosen") : h("span", { class: "small muted" }, e.dir ? "" : bytes(e.bytes))))),
        folder ? h("button", { class: "btn primary block", type: "button", onclick: () => { input.value = d.path; close(); } }, "Use this folder") : null,
        multi ? h("button", { class: "btn primary block", type: "button", onclick: close }, `Done (${chosen.size})`) : null);
    };
    draw(input.value && !multi ? input.value.replace(/\/[^/]*\.[^/]+$/, "") : null);
  });
}

// routing advice
const ROUTE_SAMPLES = [["a blocky voxel lifeboat", 0], ["treasure chest for the cove", 0], ["animated pirate captain walking", 0],
  ["turn this concept art into a ship", 1], ["scan of the old dock", 24], ["a stone well", 0]];
function runRoute(box) {
  const req = h("textarea", { id: "r-req", rows: "3", style: "font-family:var(--sans);font-size:16px", placeholder: "Describe the asset, e.g. “an animated deckhand who waves”" });
  const imgs = h("input", { type: "number", id: "r-img", min: "0", max: "500", value: "0", inputmode: "numeric" });
  const out = h("div", { class: "stack" });
  const go = async (text, n) => {
    out.replaceChildren(loading(1));
    try {
      const r = SNAP ? (await snapJSON("data/routes.json"))[`${text}|${n}`] : (await callTool("meshcraft", "route", { request: text, images: n })).result;
      if (!r) throw new Error("This preview has advice for the sample requests only. Tap one of them.");
      out.replaceChildren(adviceView(r));
    } catch (e) { out.replaceChildren(failBox(e)); }
  };
  box.append(h("form", { class: "form card pad", onsubmit: (e) => { e.preventDefault(); if (req.value.trim()) go(req.value.trim(), Number(imgs.value) || 0); } },
    h("label", { class: "field", for: "r-req" }, "What do you want to make?", req),
    h("label", { class: "field", for: "r-img" }, "Reference images or photos", imgs, h("span", { class: "hint" }, "how many you have; the advice changes when there are photos")),
    h("button", { class: "btn primary block", type: "submit" }, "Get advice"),
    h("div", { class: "filters", "aria-label": "Examples" }, ROUTE_SAMPLES.map(([t, n]) => h("button", { type: "button", "aria-pressed": "false", onclick: () => { req.value = t; imgs.value = n; go(t, n); } }, n ? `${t} (${n} img)` : t)))),
    h("p", { class: "small muted" }, "Advice only: nothing is built. Capabilities this machine does not have are shown as unavailable, never substituted."), out);
}
function adviceView(r) {
  const steps = (r.tools || []).flatMap((t, i) => [i ? h("span", { class: "arrow", "aria-hidden": "true" }, "→") : null, h("span", { class: "s" }, t)]);
  const main = r.available
    ? h("div", { class: "advice available" }, h("div", { class: "label" }, "Recommended · available here"), h("h2", {}, routeName(r)),
        r.why ? h("div", {}, r.why) : null, steps.length ? h("div", { class: "steps" }, steps) : null)
    : h("div", { class: "advice unavailable" }, h("div", { class: "label" }, "What you asked for · not available here"), h("h2", {}, routeName(r)), h("div", {}, r.reason || "unavailable on this machine"));
  const alts = (r.alternatives || []).map((a) => h("div", { class: "advice alternative" }, h("div", { class: "label" }, "Alternative · not the same thing"), h("h3", {}, a.route), h("div", {}, a.note)));
  return h("div", { class: "stack" }, main, ...alts);
}
const routeName = (r) => ({ template: `MeshCraft template: ${r.template}`, blockbench: "Blockbench project", mixamo: "Model it, then animate with Mixamo",
  run_script: "Assisted modelling (run_script)", photogrammetry: "Photogrammetry", image_to_3d: "Image-to-3D generation" })[r.route] || r.route;

// any tool, through a form generated from its input schema
let toolSel = { tool: "meshcraft", name: "" };
async function runAnyTool(box) {
  box.append(snapNotice());
  const ov = await api.get("/api/overview");
  const srv = h("select", { id: "t-srv" }, ov.tools.map((t) => h("option", { value: t.name, selected: t.name === toolSel.tool }, t.name)));
  const nameSel = h("select", { id: "t-name" }); const formBox = h("div"); const out = h("div", { class: "stack" });
  const card = h("div", { class: "card pad form" }, h("div", { class: "two" }, h("label", { class: "field", for: "t-srv" }, "Tool server", srv), h("label", { class: "field", for: "t-name" }, "Tool", nameSel)), formBox);
  box.append(card, out);
  let list = null;
  const loadServer = async () => {
    toolSel.tool = srv.value; nameSel.replaceChildren(h("option", {}, "Connecting…")); formBox.replaceChildren();
    try { list = await api.get(`/api/tools?tool=${srv.value}`); } catch (e) { formBox.replaceChildren(failBox(e)); nameSel.replaceChildren(); return; }
    nameSel.replaceChildren(...list.tools.map((t) => h("option", { value: t.name, selected: t.name === toolSel.name }, t.name + (list.denied.includes(t.name) ? " (blocked by policy)" : ""))));
    drawForm();
  };
  const drawForm = () => {
    const t = list.tools.find((x) => x.name === nameSel.value); toolSel.name = nameSel.value; if (!t) return;
    const denied = list.denied.includes(t.name);
    const sf = schemaForm(t.inputSchema || {});
    formBox.replaceChildren(h("p", { class: "small muted" }, t.description || ""), denied ? h("div", { class: "banner warn" }, `GITCRAFT policy blocks ${t.name} on ${srv.value}; the guard refuses it.`) : null,
      sf.el, h("button", { class: "btn primary block", type: "button", disabled: SNAP || denied, onclick: () => {
        let args; try { args = sf.value(); } catch (e) { toast(e.message, true); return; }
        runAndShow(out, srv.value, t.name, args);
      } }, `Run ${t.name}`));
  };
  srv.addEventListener("change", () => { toolSel.name = ""; loadServer(); }); nameSel.addEventListener("change", drawForm);
  loadServer();
}
function schemaForm(schema) {
  const props = schema.properties || {}; const req = new Set(schema.required || []); const getters = [];
  const fields = Object.entries(props).map(([k, s]) => {
    const id = `sf-${k}`; const type = s.type || (s.anyOf ? "json" : "string"); let el, get;
    if (s.enum) { el = h("select", { id }, h("option", { value: "" }, "—"), s.enum.map((v) => h("option", { value: v }, v))); get = () => el.value || undefined; }
    else if (type === "boolean") { el = h("input", { type: "checkbox", id }); get = () => el.checked; }
    else if (type === "number" || type === "integer") { el = h("input", { type: "number", id, step: "any" }); get = () => el.value === "" ? undefined : Number(el.value); }
    else if (type === "string") { el = h("input", { type: "text", id, autocapitalize: "off", autocorrect: "off", spellcheck: "false" }); get = () => el.value || undefined; }
    else { el = h("textarea", { id, rows: "3", placeholder: type === "array" ? "[ … ] JSON, or comma-separated values" : "{ … } JSON" });
      get = () => { const v = el.value.trim(); if (!v) return undefined; try { return JSON.parse(v); } catch (_) { if (type === "array") return v.split(",").map((x) => x.trim()); throw new Error(`${k}: not valid JSON`); } }; }
    getters.push([k, get]);
    const label = `${k}${req.has(k) ? " *" : ""}`;
    return type === "boolean" ? h("label", { class: "check" }, el, label) : h("label", { class: "field", for: id }, label, el, s.description ? h("span", { class: "hint" }, s.description) : null);
  });
  return { el: h("div", { class: "form" }, fields.length ? fields : h("p", { class: "small muted" }, "No parameters.")),
    value: () => { const o = {}; for (const [k, g] of getters) { const v = g(); if (v !== undefined) o[k] = v; } for (const k of req) if (!(k in o)) throw new Error(`${k} is required`); return o; } };
}

// ---------------------------------------------------------------- Jobs
let jobFilter = "all";
function pageJobs(main) {
  main.append(head("MeshCraft", "Jobs", "Every pipeline, Blockbench import and Mixamo merge is a job: each attempt, what was changed for a retry, and why it failed."));
  const filters = h("div", { class: "filters", role: "group", "aria-label": "Filter jobs" }); const list = h("div", { class: "list", style: "margin-top:12px" }, loading(4));
  main.append(filters, list);
  const F = [["all", "All"], ["running", "Running"], ["done", "Done"], ["done_with_fallback", "Fallback"], ["failed", "Failed"]];
  let data = null;
  const draw = () => {
    filters.replaceChildren(...F.map(([k, l]) => h("button", { type: "button", "aria-pressed": String(jobFilter === k), onclick: () => { jobFilter = k; draw(); } },
      l + (data ? ` ${k === "all" ? data.jobs.length : data.jobs.filter((j) => j.status === k).length}` : ""))));
    if (!data) return;
    const js = data.jobs.filter((j) => jobFilter === "all" || j.status === jobFilter);
    list.replaceChildren(...(js.length ? js.map(jobRow) : [h("div", { class: "empty" }, "No jobs here.")]));
  };
  const load = async () => { try { data = await api.get("/api/jobs"); draw(); } catch (e) { list.replaceChildren(failBox(e)); } };
  draw(); load(); if (!SNAP) pageTimer = setInterval(() => current === "jobs" && !sheetStack.length && load(), 4000);
}
function jobRow(j) {
  return h("button", { class: `card item stripe ${stripeOf(j.status)}`, type: "button", onclick: () => openJob(j.id) },
    h("span", { class: "title" }, j.asset_id || j.id), chip(j.status),
    h("div", { class: "meta" }, h("span", { class: "mono" }, j.tool), h("span", {}, `${j.attempts} attempt${j.attempts === 1 ? "" : "s"}`), h("span", {}, ago(j.created)),
      j.library && j.library.version ? h("span", {}, `library v${j.library.version}`) : null),
    j.status === "failed" && j.error ? h("div", { class: "meta", style: "color:var(--bad)" }, j.error.split("\n")[0].slice(0, 160)) : null);
}
function openJob(id) {
  sheet("Job", async (c, close) => {
    c.append(loading(3)); const j = await api.get(`/api/jobs/${id}`);
    const atts = j.attempts || [];
    const req = j.request || {}; const brief = req.brief || req;
    c.replaceChildren(
      h("div", { class: "spread" }, h("div", {}, h("div", { class: "eyebrow" }, j.tool), h("h2", {}, j.asset_id || j.id)), chip(j.status)),
      j.status === "done_with_fallback" ? h("div", { class: "banner warn" }, h("div", {}, h("b", {}, "Finished with a fallback. "), `The first attempt failed, so MeshCraft retried with: ${j.fallback}. The deliverables reflect that lighter setting.`)) : null,
      j.status === "failed" ? h("div", { class: "banner bad" }, h("div", {}, h("b", {}, "Failed. "), (j.error || "").split("\n")[0])) : null,
      h("dl", { class: "kv" }, h("dt", {}, "Job"), h("dd", { class: "mono" }, j.id), h("dt", {}, "Created"), h("dd", {}, `${j.created} (${ago(j.created)})`),
        brief.template ? [h("dt", {}, "Template"), h("dd", {}, brief.template)] : null,
        brief.profiles ? [h("dt", {}, "Profiles"), h("dd", {}, brief.profiles.join(", "))] : null,
        brief.out_dir ? [h("dt", {}, "Output"), h("dd", { class: "mono" }, brief.out_dir)] : null),
      h("h3", {}, "Attempts"),
      h("div", { class: "timeline" }, atts.map((a) => h("div", { class: `step ${a.status === "done" ? "ok" : a.status === "failed" ? "bad" : ""}` }, h("div", { class: "dot" }),
        h("div", { class: "body" }, h("div", { class: "spread" }, h("b", {}, `Attempt ${a.n}${a.manual ? " · manual retry" : ""}`), chip(a.status === "done" ? "done" : a.status === "failed" ? "failed" : "running")),
          h("div", { class: "small muted" }, `${a.seconds != null ? a.seconds + " s · " : ""}${a.started || ""}`),
          a.change ? h("div", { class: "small", style: "margin-top:4px" }, h("b", {}, "Changed for this attempt: "), a.change) : h("div", { class: "small muted", style: "margin-top:4px" }, "Original request"),
          a.error ? h("pre", { class: "json", style: "margin-top:6px;max-height:160px" }, a.error) : null,
          a.retry ? h("div", { class: "small", style: "margin-top:4px;color:var(--bad)" }, a.retry) : null,
          a.steps ? h("div", { class: "steps", style: "margin-top:6px" }, a.steps.map((s) => h("span", { class: "s", style: s.ok ? "" : "border-color:var(--bad);color:var(--bad)" }, `${s.step} ${s.seconds ?? ""}${s.seconds != null ? "s" : ""}`))) : null)))),
      h("div", { class: "row" },
        j.library && j.library.version ? h("button", { class: "btn", type: "button", onclick: () => { close(); openAsset(j.asset_id, j.library.version); } }, `Library v${j.library.version}`) : null,
        ["run_pipeline", "blockbench_import", "mixamo_apply"].includes(j.tool) ? h("button", { class: "btn primary", type: "button", disabled: SNAP, onclick: async (e) => {
          e.target.disabled = true; e.target.textContent = "Retrying…";
          try { const r = await callTool("meshcraft", "job_retry", { job: j.id }); toast(r.status === "done" ? "Retry finished" : "Retry failed: see the attempts", r.status !== "done"); close(); openJob(j.id); }
          catch (err) { toast(err.message, true); e.target.disabled = false; e.target.textContent = "Retry"; } } }, "Retry") : null),
      h("details", {}, h("summary", { class: "small muted" }, "Original request"), jsonBlock(j.request)));
  });
}

// ---------------------------------------------------------------- Library
let libQuery = "", libStatus = "all";
function pageLibrary(main) {
  main.append(head("MeshCraft", "3D library", "Every version MeshCraft produced, with the fingerprint of each file, the inputs it came from and its check results."));
  const search = h("input", { type: "search", id: "lib-q", placeholder: "Search assets", value: libQuery, "aria-label": "Search assets", autocapitalize: "off" });
  const filters = h("div", { class: "filters", role: "group", "aria-label": "Filter by checks" }); const grid = h("div", { class: "grid lib", style: "margin-top:12px" }, loading(3));
  main.append(h("div", { class: "stack" }, search, filters), grid);
  let data = null;
  const draw = () => {
    const F = [["all", "All"], ["pass", "Checks pass"], ["needs-fix", "Needs fixes"]];
    filters.replaceChildren(...F.map(([k, l]) => h("button", { type: "button", "aria-pressed": String(libStatus === k), onclick: () => { libStatus = k; draw(); } }, l)));
    if (!data) return;
    const q = libQuery.toLowerCase().split(/\s+/).filter(Boolean);
    const as = data.assets.filter((a) => (libStatus === "all" || a.validation === libStatus) && q.every((w) => `${a.id} ${a.title} ${a.template} ${a.tool} ${(a.tags || []).join(" ")}`.toLowerCase().includes(w)));
    grid.replaceChildren(...(as.length ? as.map(assetCard) : [h("div", { class: "empty", style: "grid-column:1/-1" }, data.assets.length ? "Nothing matches." : "The library is empty. Every pipeline run adds a version here.")]));
  };
  search.addEventListener("input", () => { libQuery = search.value; draw(); });
  draw(); api.get("/api/library").then((d) => { data = d; draw(); }).catch((e) => grid.replaceChildren(failBox(e)));
}
function assetCard(a) {
  const thumb = a.thumbnail ? (SNAP ? a.thumbnail_file : `/files?path=${encodeURIComponent(`${dataLib()}/${a.thumbnail}`)}`) : null;
  return h("button", { class: "card asset-card", type: "button", onclick: () => openAsset(a.id) },
    h("div", { class: "thumb" }, thumb ? h("img", { src: thumb, alt: "", loading: "lazy" }) : null),
    h("div", { class: "spread" }, h("b", {}, breakable(a.id)), h("span", { class: "chip plain" }, `v${a.latest}`)),
    h("div", { class: "row small muted", style: "margin-top:4px" }, chip(a.validation), a.template ? h("span", {}, a.template) : null, a.triangles ? h("span", { class: "tabular" }, `${a.triangles.toLocaleString()} tris`) : null));
}
let LIB = ""; const dataLib = () => LIB;
function openAsset(id, version) {
  sheet(id, async (c) => {
    c.append(loading(4));
    const md = await api.get(`/api/library/${id}${version ? `?version=${version}` : ""}`);
    const v = md.version; const files = md.files || []; const previews = files.filter((f) => f.kind === "preview");
    const glbs = files.filter((f) => f.kind === "export" && /\.glb$/.test(f.path));
    const sum = md.validation?.summary || {};
    const versions = h("div", { class: "filters", role: "group", "aria-label": "Versions" }, md.versions.map((n) =>
      h("button", { type: "button", "aria-pressed": String(n === v), onclick: () => { sheetStack[sheetStack.length - 1](); openAsset(id, n); } }, `v${n}`)));
    const viewerBox = h("div");
    const showGLB = (f) => { viewerBox.replaceChildren(h("div", { class: "viewer" }, h("div", { class: "note" }, `${base(f.path)} · drag to orbit, pinch to zoom`))); viewer(viewerBox.firstChild, fileURL(f)); };
    c.replaceChildren(
      versions,
      h("div", { class: "band" }, chip(md.validation?.status), md.same_as ? h("span", { class: "chip ok" }, `identical to v${md.same_as}`) : h("span", { class: "chip plain" }, v > 1 ? "changed since the previous version" : "first version"),
        md.tool ? h("span", { class: "chip plain" }, md.tool) : null),
      previews.length ? h("div", { class: "gallery" }, previews.map((p) => h("figure", {}, h("div", { class: "thumb" }, img(p)), h("figcaption", {}, base(p.path))))) : h("div", { class: "empty" }, "No preview renders in this version."),
      glbs.length ? h("div", { class: "row" }, glbs.map((g) => h("button", { class: "btn small", type: "button", disabled: SNAP && !g.file, onclick: () => showGLB(g) }, icon("cube"), `3D: ${base(g.path).replace(`${id}.`, "")}`)),
        SNAP && !glbs.some((g) => g.file) ? h("span", { class: "small muted" }, "The interactive 3D viewer runs in the local control room.") : null) : null,
      viewerBox,
      h("dl", { class: "kv" }, h("dt", {}, "Created"), h("dd", {}, `${md.created} (${ago(md.created)})`), md.template ? [h("dt", {}, "Template"), h("dd", {}, md.template)] : null,
        md.triangles ? [h("dt", {}, "Triangles"), h("dd", { class: "tabular" }, md.triangles.toLocaleString())] : null,
        md.clips && md.clips.length ? [h("dt", {}, "Clips"), h("dd", {}, md.clips.join(", "))] : null,
        md.job ? [h("dt", {}, "Job"), h("dd", {}, h("a", { href: "#jobs", onclick: (e) => { e.preventDefault(); openJob(md.job); } }, md.job))] : null),
      h("h3", {}, `Checks · ${sum.pass || 0} pass, ${sum.warn || 0} warn, ${sum.fail || 0} fail`),
      checksView(md.checks || []),
      h("h3", {}, `Files · ${files.length}`),
      h("div", { class: "card files" }, files.map((f) => h("div", { class: "f" }, h("span", { class: "n" }, f.path), h("span", { class: "chip plain" }, f.kind),
        h("div", { class: "h" }, h("span", { class: "small muted" }, bytes(f.bytes)), h("span", { class: "hash", title: f.sha256 }, `sha256 ${short(f.sha256)}`), copyBtn(f.sha256))))),
      h("h3", {}, "Inputs"),
      (md.inputs || []).length ? h("div", { class: "card files" }, md.inputs.map((i) => h("div", { class: "f" }, h("span", { class: "n" }, i.path), h("span"), h("div", { class: "h" }, h("span", { class: "hash" }, `sha256 ${short(i.sha256)}`), copyBtn(i.sha256)))))
        : h("p", { class: "small muted" }, "No recorded inputs."),
      exportForm(id, v));
  });
}
function checksView(checks) {
  if (!checks.length) return h("p", { class: "small muted" }, "No check details in this version.");
  const order = { fail: 0, warn: 1, pass: 2, info: 3 };
  const sorted = [...checks].sort((a, b) => order[a.level] - order[b.level]);
  const first = sorted.filter((c) => c.level !== "pass" && c.level !== "info");
  const row = (c) => h("div", { class: "item", style: "padding:8px 0;border-top:1px solid var(--line)" }, h("span", { class: "title mono small" }, c.check + (c.file ? ` · ${c.file}` : "")),
    h("span", { class: `chip ${c.level === "pass" ? "ok" : c.level === "fail" ? "bad" : c.level === "warn" ? "warn" : "plain"}` }, c.level), h("div", { class: "meta" }, c.detail));
  return h("div", { class: "card" }, first.length ? first.map(row) : h("div", { class: "small", style: "color:var(--ok)" }, "No warnings or failures."),
    h("details", {}, h("summary", { class: "small muted", style: "padding-top:8px" }, `All ${checks.length} checks`), sorted.map(row)));
}
function exportForm(id, v) {
  const box = h("div", { class: "card pad form" });
  const dest = h("input", { type: "text", id: "x-dest", placeholder: "folder inside a workspace root" });
  const kinds = [["export", "Exports", true], ["lod", "LODs", true], ["collision", "Collision", true], ["sidecar", "Textures / atlases", true], ["preview", "Previews", false], ["blend", ".blend source", false]]
    .map(([k, l, on]) => h("label", { class: "check" }, h("input", { type: "checkbox", value: k, checked: on }), l));
  const out = h("div");
  api.get("/api/overview").then((ov) => { if (!dest.value) dest.value = `${ov.roots[0]}/gitcraft-handoff`; }).catch(() => {});
  box.append(h("h3", {}, "Export to a project workspace"),
    h("p", { class: "small muted" }, "Copies this version into a workspace root through MeshCraft (guarded and audited) and re-checks every file's fingerprint."),
    h("label", { class: "field", for: "x-dest" }, "Destination", h("div", { class: "pick" }, dest, pickBtn(dest, null, false, true))),
    h("div", { class: "grid tight" }, kinds),
    h("button", { class: "btn primary block", type: "button", disabled: SNAP, onclick: async (e) => {
      const k = kinds.map((l) => l.querySelector("input")).filter((i) => i.checked).map((i) => i.value);
      e.target.disabled = true; out.replaceChildren(h("div", { class: "small muted" }, "Copying and verifying…"));
      try {
        const r = await callTool("meshcraft", "library_export", { asset: id, version: v, dest: dest.value, kinds: k });
        if (r.status !== "done") throw new Error(typeof r.result === "string" ? r.result.split("\n")[0] : "export failed");
        out.replaceChildren(h("div", { class: "banner info" }, h("div", {}, h("b", {}, `Verified: ${r.result.files.length} files `), "match their library fingerprints.", h("div", { class: "mono small wrap" }, r.result.dir))));
      } catch (err) { out.replaceChildren(failBox(err)); }
      e.target.disabled = false; } }, SNAP ? "Export (live control room only)" : "Export and verify"), out);
  return box;
}

// three.js viewer: MeshCraft's own three@0.170 locally, the same version from jsDelivr in the snapshot
async function viewer(el, url) {
  const V = SNAP ? ["https://cdn.jsdelivr.net/npm/three@0.170.0/+esm", "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/loaders/GLTFLoader.js/+esm",
                    "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js/+esm"]
                 : ["/vendor/three/build/three.module.js", "/vendor/three/examples/jsm/loaders/GLTFLoader.js", "/vendor/three/examples/jsm/controls/OrbitControls.js"];
  try {
    const [THREE, { GLTFLoader }, { OrbitControls }] = await Promise.all(V.map((u) => import(u)));
    const w = el.clientWidth, hh = el.clientHeight;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setSize(w, hh);
    renderer.outputColorSpace = THREE.SRGBColorSpace; el.prepend(renderer.domElement);
    const scene = new THREE.Scene(); scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.6)); const sun = new THREE.DirectionalLight(0xffffff, 1.8); sun.position.set(3, 5, 4); scene.add(sun);
    const cam = new THREE.PerspectiveCamera(35, w / hh, 0.01, 200); const ctl = new OrbitControls(cam, renderer.domElement); ctl.enableDamping = true;
    const gltf = await new GLTFLoader().loadAsync(url);
    gltf.scene.traverse((o) => { if (o.isMesh && o.geometry.attributes.color && o.material) { o.material.vertexColors = true; } });
    scene.add(gltf.scene);
    const box = new THREE.Box3().setFromObject(gltf.scene), size = box.getSize(new THREE.Vector3()).length(), c = box.getCenter(new THREE.Vector3());
    ctl.target.copy(c); cam.position.copy(c).add(new THREE.Vector3(size * .8, size * .55, size * 1.1)); cam.near = size / 100; cam.far = size * 20; cam.updateProjectionMatrix();
    const mixer = gltf.animations.length ? new THREE.AnimationMixer(gltf.scene) : null; if (mixer) mixer.clipAction(gltf.animations[0]).play();
    const clock = new THREE.Clock();
    (function loop() { if (!el.isConnected) { renderer.dispose(); return; } requestAnimationFrame(loop); mixer && mixer.update(clock.getDelta()); ctl.update(); renderer.render(scene, cam); })();
    if (gltf.animations.length) el.querySelector(".note").textContent += ` · playing “${gltf.animations[0].name}”`;
  } catch (e) { el.replaceChildren(h("div", { class: "banner warn", style: "margin:12px" }, `3D preview unavailable: ${e.message || e}`)); }
}

// ---------------------------------------------------------------- Tools
function pageTools(main) {
  main.append(head("All eight servers", "Tools", "Each server's own tool list, discovered live over MCP. Commands GITCRAFT policy blocks are marked; the guard refuses them."));
  const list = h("div", { class: "grid" }, loading(4)); main.append(list);
  api.get("/api/overview").then((ov) => { LIB = ov.library; list.replaceChildren(...ov.tools.map(toolCard)); }).catch((e) => list.replaceChildren(failBox(e)));
}
function openServer(name) {
  sheet(name, async (c, close) => {
    c.append(h("div", { class: "small muted" }, SNAP ? "" : "Connecting through scripts/mcp.sh…"), loading(4));
    const d = await api.get(`/api/tools?tool=${name}`);
    const q = h("input", { type: "search", placeholder: `Filter ${d.tools.length} tools`, "aria-label": "Filter tools", autocapitalize: "off" });
    const list = h("div", { class: "list" });
    const draw = () => { const w = q.value.toLowerCase();
      list.replaceChildren(...d.tools.filter((t) => !w || (t.name + " " + (t.description || "")).toLowerCase().includes(w)).map((t) => {
        const denied = (d.denied || []).includes(t.name);
        return h("button", { class: `card item ${denied ? "stripe warn" : ""}`, type: "button", onclick: () => { toolSel = { tool: name, name: t.name }; runMode = "tool"; close(); location.hash = "#run"; } },
          h("span", { class: "tool-name" }, t.name), denied ? h("span", { class: "chip warn" }, "blocked by policy") : h("span", { class: "small muted" }, Object.keys((t.inputSchema || {}).properties || {}).length + " params"),
          h("div", { class: "meta" }, (t.description || "").slice(0, 220)));
      })); };
    q.addEventListener("input", draw); draw();
    c.replaceChildren(h("div", { class: "band" }, d.server && d.server.version ? h("span", { class: "chip plain" }, `${d.server.title || d.server.name} ${d.server.version}`) : null,
      h("span", { class: "chip plain" }, `${d.tools.length} tools`), (d.denied || []).length ? h("span", { class: "chip warn" }, `policy: ${d.denied.join(", ")} refused`) : null),
      d.instructions ? h("p", { class: "small muted" }, d.instructions) : null, q, list);
  });
}

// ---------------------------------------------------------------- boot
async function boot() {
  nav();
  if (!SNAP && !TOKEN) {
    $("#main").replaceChildren(head("Local · 127.0.0.1", "Open the control room with its link"), h("div", { class: "banner warn" },
      "This page needs the one-time link scripts/ui.sh printed (it ends in #token=…). The token keeps other web pages and programs on this machine from driving your tools."));
    return;
  }
  try {
    if (!SNAP) await api.post("/api/session", {});
    const ov = await api.get("/api/overview"); LIB = ov.library;
    $("#rail-foot").replaceChildren(h("span", {}, SNAP ? "Read-only preview" : "127.0.0.1 only"), h("span", { class: "mono" }, ov.sandbox.landlock_abi ? `Landlock ABI ${ov.sandbox.landlock_abi}` : "no sandbox"));
  } catch (e) {
    $("#main").replaceChildren(head("Local", "Can't reach the control room"), failBox(e)); return;
  }
  if (SNAP) { const m = await snapJSON("data/meta.json").catch(() => null);
    document.body.prepend(h("div", { class: "banner info", style: "border-radius:0;justify-content:center;padding-top:calc(env(safe-area-inset-top, 0px) + 10px)" },
      `Read-only preview of the GITCRAFT control room with real data from ${m ? m.created : "a recent run"}. Running tools needs the local control room.`)); }
  window.addEventListener("hashchange", route); route();
}
boot();
})();
