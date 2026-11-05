/* DESIGNCRAFT web app. Static: reads data/index.json and data/<game>.json written by `python3 -m gamedesign publish`.
   Nothing here edits a game. The Design Lab keeps saved alternatives in this browser (localStorage) and exports specs. */
"use strict";
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const NS = "http://www.w3.org/2000/svg";
  const TABS = [
    ["overview", "Overview"], ["map", "Game map"], ["levelcraft", "LevelCraft"], ["missioncraft", "MissionCraft"], ["storycraft", "StoryCraft"],
    ["progression", "Progression"], ["experience", "Experience"], ["lab", "Design Lab"], ["reports", "Reports"]];
  const DEPT_OF_TAB = { levelcraft: "levelcraft", missioncraft: "missioncraft", storycraft: "storycraft", progression: "progressioncraft", experience: "experiencecraft" };
  const TAB_OF_DEPT = { levelcraft: "levelcraft", missioncraft: "missioncraft", storycraft: "storycraft", progressioncraft: "progression", experiencecraft: "experience" };
  const LV = { source_verified: "Source verified", simulated: "Simulated", playtested: "Playtested", inferred: "Inferred", untested: "Untested" };
  const SEV = { critical: "Critical", major: "Major", minor: "Minor", info: "Note" };
  const KCOL = ["--k1", "--k2", "--k3", "--k4", "--k5", "--k6", "--k7", "--k8"];
  const S = { index: null, A: null, cache: {}, open: {} };

  // ------------------------------------------------------------------ dom helpers
  function h(tag, attrs) {
    const el = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      const v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "class") el.className = v; else if (k === "text") el.textContent = v;
      else if (k.startsWith("on")) el.addEventListener(k.slice(2), v); else el.setAttribute(k, v === true ? "" : v);
    }
    for (let i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) { c.forEach((x) => add(el, x)); return; }
    el.appendChild(typeof c === "string" || typeof c === "number" ? document.createTextNode(String(c)) : c);
  }
  function s(tag, attrs) {
    const el = document.createElementNS(NS, tag);
    if (attrs) for (const k in attrs) {
      const v = attrs[k]; if (v == null) continue;
      if (k === "text") el.textContent = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v); else el.setAttribute(k, v);
    }
    for (let i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const kc = (i) => `var(${KCOL[((i % KCOL.length) + KCOL.length) % KCOL.length]})`;
  const fmt = (x, d) => x == null ? "—" : (typeof x === "number" ? (Math.abs(x) >= 1000 ? Math.round(x).toLocaleString() : (+x.toFixed(d == null ? 1 : d)).toString()) : String(x));
  const pct = (x) => x == null ? "—" : Math.round(x * 100) + "%";
  const trunc = (t, n) => !t ? "" : t.length > n ? t.slice(0, n - 1) + "…" : t;
  function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._t); t._t = setTimeout(() => t.classList.remove("on"), 2600); }
  function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k) || "null"); localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }

  function srcLink(e) {
    if (!e || !e.file) return e && e.symbol ? h("span", { class: "ref" }, e.symbol) : null;
    const g = S.A && S.A.game; const label = e.file + (e.line ? ":" + e.line : "");
    if (g && g.remote && g.commit && !/^history\//.test(e.file)) {
      return h("a", { class: "ref", href: `https://github.com/${g.remote}/blob/${g.commit}/${e.file}${e.line ? "#L" + e.line : ""}`, target: "_blank", rel: "noopener" }, label);
    }
    return h("code", null, label);
  }
  const lv = (l) => h("span", { class: "lv lv-" + l, title: LV[l] + " evidence" }, LV[l] || l);
  const sev = (x) => h("span", { class: "chip sev-" + x }, SEV[x] || x);
  const conf = (c) => h("span", { class: "conf " + c, title: "Confidence in this score" }, c + " confidence");
  const cx = (c) => h("span", { class: "cx cx-" + c, title: "Implementation complexity" }, c + " effort");

  // ------------------------------------------------------------------ data
  async function getJSON(u) { const r = await fetch(u, { cache: "no-cache" }); if (!r.ok) throw new Error(u + ": " + r.status); return r.json(); }
  async function loadGame(id) {
    if (!S.cache[id]) S.cache[id] = await getJSON("data/" + encodeURIComponent(id) + ".json");
    S.A = S.cache[id]; return S.A;
  }
  function route() {
    const p = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
    if (p[0] !== "g" || !p[1]) return { game: null, tab: "overview", sub: null };
    return { game: p[1], tab: p[2] || "overview", sub: p.slice(3).join("/") || null };
  }
  const link = (tab, sub) => "#/g/" + encodeURIComponent(S.A.game.id) + "/" + tab + (sub ? "/" + encodeURIComponent(sub) : "");

  // ------------------------------------------------------------------ shell
  function renderTabs(r) {
    const nav = $("#tabs"); nav.innerHTML = "";
    if (!S.A) return;
    const byDept = {}; S.A.findings.forEach((f) => { byDept[f.dept] = (byDept[f.dept] || 0) + (f.severity === "info" ? 0 : 1); });
    TABS.forEach(([id, label]) => {
      const n = DEPT_OF_TAB[id] ? byDept[DEPT_OF_TAB[id]] : null;
      const a = h("a", { href: link(id), "aria-current": r.tab === id ? "page" : null }, label, n ? h("span", { class: "n", "aria-label": n + " findings" }, String(n)) : null);
      nav.appendChild(a);
    });
    const cur = nav.querySelector('[aria-current="page"]');
    if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  function renderPicker(r) {
    const sel = $("#game"); sel.innerHTML = "";
    (S.index.games || []).forEach((g) => sel.appendChild(h("option", { value: g.id, selected: S.A && g.id === S.A.game.id ? true : null }, g.title)));
    sel.onchange = () => { location.hash = "#/g/" + encodeURIComponent(sel.value) + "/" + (r.tab || "overview"); };
  }

  async function render() {
    const r = route(); const main = $("#main");
    try {
      if (!S.index) S.index = await getJSON("data/index.json");
      const games = S.index.games || [];
      if (!games.length) { main.innerHTML = ""; main.appendChild(h("p", { class: "empty" }, "No assessments have been recorded yet. Run `python3 -m gamedesign assess <repo> --record`, then publish.")); return; }
      if (!r.game) { S.A = null; renderPicker(r); renderTabs(r); main.innerHTML = ""; main.appendChild(viewPortfolio(games)); document.title = "DESIGNCRAFT"; return; }
      await loadGame(r.game);
      renderPicker(r); renderTabs(r);
      main.innerHTML = "";
      const V = { overview: viewOverview, map: viewMap, levelcraft: viewLevel, missioncraft: viewMission, storycraft: viewStory, progression: viewProgression,
        experience: viewExperience, lab: viewLab, reports: viewReports }[r.tab] || viewOverview;
      main.appendChild(V(r));
      main.appendChild(footer());
      document.title = (TABS.find((t) => t[0] === r.tab) || ["", "Overview"])[1] + " · " + S.A.game.title + " · DESIGNCRAFT";
      if (r.sub && r.tab !== "lab") { const el = document.getElementById(r.sub); if (el) { el.scrollIntoView({ block: "start" }); const b = el.querySelector(".f-h"); if (b && b.getAttribute("aria-expanded") === "false") b.click(); } }
      else window.scrollTo(0, 0);
    } catch (e) {
      main.innerHTML = ""; main.appendChild(h("div", { class: "note" }, h("b", null, "Could not load this assessment. "), String(e.message || e)));
    }
  }
  function footer() {
    const A = S.A;
    return h("footer", { class: "foot" },
      h("span", null, "DESIGNCRAFT " + A.designcraft_version + " · method " + A.method),
      h("span", null, "Assessed " + A.assessed_at.slice(0, 16).replace("T", " ") + " UTC"),
      A.game.commit ? h("span", null, "Game commit " + A.game.commit.slice(0, 10)) : null,
      h("span", null, "The game repository is read, never changed or run."));
  }

  // ------------------------------------------------------------------ portfolio (no game selected)
  function viewPortfolio(games) {
    const wrap = h("div");
    wrap.appendChild(h("p", { class: "eyebrow" }, "Game design intelligence"));
    wrap.appendChild(h("h1", null, "What would make these games better to play?"));
    wrap.appendChild(h("p", { class: "lede" }, "DESIGNCRAFT reads each game's own files (missions, places, characters, dialogue, progression tables, design docs), measures the design, and proposes three alternatives for every significant weakness. Scores show their evidence, coverage and confidence; missing data lowers them instead of being assumed."));
    const list = h("div", { class: "rows sec" });
    games.forEach((g) => {
      const L = g.latest;
      list.appendChild(h("a", { class: "row", href: "#/g/" + encodeURIComponent(g.id) + "/overview" },
        h("span", { class: "t" }, g.title),
        h("span", null, h("b", { style: "font:600 22px var(--serif)" }, String(L.overall)), h("span", { class: "sub" }, " / 100")),
        h("span", { class: "d" }, `coverage ${pct(L.coverage)} · confidence ${L.confidence} · ${L.findings} findings · ceiling ${L.ceiling}` + (g.genres && g.genres.length ? " · " + g.genres.slice(0, 2).join(", ") : "")),
        g.top && g.top.length ? h("span", { class: "d" }, "Top: " + g.top[0].title) : null));
    });
    wrap.appendChild(list);
    wrap.appendChild(h("p", { class: "sub sec" }, "Sorted by evidence coverage: games whose design lives in data can be assessed in depth; games whose design lives in code get honest, low-coverage scores."));
    return wrap;
  }

  // ------------------------------------------------------------------ shared blocks
  function rangeBar(score, ceil, max) {
    return h("div", { class: "range", role: "img", "aria-label": `score ${score} of ${max}, ceiling ${ceil}` },
      h("i", { class: "ceil", style: `width:${(ceil / max) * 100}%` }), h("i", { class: "val", style: `width:${(score / max) * 100}%` }));
  }
  function catList(cats, onPick) {
    const box = h("div", { class: "cats" });
    Object.entries(cats).forEach(([k, c]) => {
      const col = c.score / c.max >= 0.67 ? "var(--prop)" : c.score / c.max >= 0.4 ? "var(--gold)" : "var(--accent)";
      const el = h(onPick ? "button" : "div", { class: "cat", onclick: onPick ? () => onPick(k) : null, "aria-label": onPick ? `${c.title}: ${c.score} of ${c.max}. Show criteria` : null },
        h("span", { class: "nm" }, c.title), h("span", { class: "v" }, fmt(c.score), h("small", null, " / " + c.max)),
        h("span", { class: "bar" }, h("i", { class: "ceil", style: `width:${(c.ceiling / c.max) * 100}%;background:repeating-linear-gradient(135deg,var(--line2) 0 4px,transparent 4px 8px)` }),
          h("i", { style: `width:${(c.score / c.max) * 100}%;background:${col}` })),
        h("span", { class: "meta" }, conf(c.confidence), h("span", null, "coverage " + pct(c.coverage)), c.weaknesses.length ? h("span", null, c.weaknesses.length + " weakness" + (c.weaknesses.length > 1 ? "es" : "")) : null));
      box.appendChild(el);
    });
    return box;
  }
  function criteriaSheet(k) {
    const c = S.A.score.categories[k];
    const body = h("div", null, h("p", { class: "eyebrow" }, "Scoring"), h("h2", { id: "sheet-title" }, c.title),
      h("p", { class: "sub" }, `${fmt(c.score)} of ${c.max} · ceiling ${fmt(c.ceiling)} · coverage ${pct(c.coverage)} · confidence ${c.confidence}`),
      h("div", { class: "tbl sec" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Criterion"), h("th", { class: "num" }, "Score"), h("th", null, "Evidence"))),
        h("tbody", null, c.criteria.map((x) => h("tr", null, h("td", null, x.title, h("div", null, lv(x.level))), h("td", { class: "num" }, x.score == null ? "untested" : pct(x.score)), h("td", null, x.evidence)))))),
      c.weaknesses.length ? h("div", { class: "sec" }, h("h3", null, "Weaknesses in this category"), h("div", { class: "rows", style: "margin-top:8px" },
        c.weaknesses.map((w) => { const f = S.A.findings.find((x) => x.id === w.id); return h("a", { class: "row", href: link(TAB_OF_DEPT[f.dept], f.id), onclick: closeSheet }, h("span", { class: "t" }, w.title), sev(w.severity)); }))) : null,
      h("p", { class: "sub sec" }, "An untested criterion earns nothing; the ceiling shows what the category could reach if it were tested and perfect."));
    openSheet(body);
  }
  function openSheet(body) { const sh = $("#sheet"); $("#sheet-body").innerHTML = ""; $("#sheet-body").appendChild(body); sh.hidden = false; $("#sheet-x").focus(); }
  function closeSheet() { $("#sheet").hidden = true; if (S.dirty) { S.dirty = false; render(); } }

  function findingCard(f, opts) {
    opts = opts || {};
    const props = (f.proposals || []).map((id) => S.A.proposals.find((p) => p.id === id)).filter(Boolean);
    const open = !!S.open[f.id] || opts.open;
    const body = h("div", { class: "f-b", hidden: open ? null : true });
    const btn = h("button", { class: "f-h", "aria-expanded": open ? "true" : "false", onclick: () => {
      const o = body.hidden; body.hidden = !o; btn.setAttribute("aria-expanded", o ? "true" : "false"); S.open[f.id] = o;
    } },
      h("span", { class: "f-top" }, sev(f.severity), h("span", { class: "chip" }, (S.A.departments[f.dept] || {}).title || f.dept), lv(f.level), props.length ? h("span", { class: "chip" }, props.length + " alternatives") : null),
      h("span", { class: "f-t" }, f.title), h("span", { class: "f-s" }, f.summary));
    body.appendChild(h("p", { class: "why" }, h("b", null, "Why it matters to players. "), f.why));
    body.appendChild(h("h4", null, "Evidence"));
    body.appendChild(h("ul", { class: "evs" }, f.evidence.map((e) => h("li", null, lv(e.level), h("span", null, e.text, " ", srcLink(e))))));
    if (f.level === "inferred") body.appendChild(h("p", { class: "sub", style: "margin-top:8px" }, "The facts above are measured; the claim about players is DESIGNCRAFT's design judgement, not observed behaviour."));
    if (props.length) {
      body.appendChild(h("h4", null, "Three alternatives"));
      body.appendChild(h("div", { class: "props" }, props.map((p) => propCard(p))));
    }
    return h("article", { class: "finding", id: f.id }, btn, body);
  }
  function propCard(p, extra) {
    return h("div", { class: "prop v-" + p.variant },
      h("span", { class: "pl" }, p.label), h("span", { class: "pt" }, p.proposal),
      h("ul", null, p.changes.map((c) => h("li", null, c))),
      h("dl", null, h("dt", null, "Expect"), h("dd", null, p.experience), h("dt", null, "Effort"), h("dd", null, cx(p.complexity), " ", p.complexity_why),
        h("dt", null, "Trade-off"), h("dd", null, p.tradeoffs.join(" ")), h("dt", null, "Validate"), h("dd", null, `${p.validation.metric}: ${p.validation.current} → ${p.validation.target}. ${p.validation.method}`)),
      h("div", { class: "acts" },
        h("a", { class: "btn sm", href: link("lab", "p:" + p.id) }, "Open in Design Lab"),
        h("button", { class: "btn sm", onclick: () => downloadSpec(p) }, "Export spec"), extra || null));
  }
  function findingsBlock(dept, title) {
    const fs = S.A.findings.filter((f) => f.dept === dept);
    const D = S.A.departments[dept];
    const wrap = h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, title || "Findings"), h("span", { class: "sub" }, fs.length + " finding" + (fs.length === 1 ? "" : "s"))));
    if (D.note) wrap.appendChild(h("div", { class: "note" }, h("b", null, "Not measured. "), D.note));
    if (!fs.length && !D.note) wrap.appendChild(h("p", { class: "sub" }, "No weaknesses found by this department's checks."));
    fs.forEach((f) => wrap.appendChild(findingCard(f)));
    if (D.strengths && D.strengths.length) wrap.appendChild(h("div", { class: "card sec" }, h("h3", null, "Working well"), h("ul", { class: "limits", style: "margin-top:10px" }, D.strengths.map((x) => h("li", null, x)))));
    return wrap;
  }
  function metricsBlock(m, keys) {
    const box = h("div", { class: "kpis" });
    keys.forEach(([k, label, f]) => { if (m[k] == null) return; box.appendChild(h("div", { class: "kpi" }, h("b", null, f ? f(m[k]) : fmt(m[k])), h("span", null, label))); });
    return box;
  }
  function deptHead(dept, lede) {
    const D = S.A.departments[dept];
    return h("div", null, h("p", { class: "eyebrow" }, S.A.game.title), h("h1", null, D.title), h("p", { class: "lede" }, lede));
  }
  function vizBox(svg, cap, tools) { return h("figure", { class: "viz", style: "margin:0" }, tools || null, svg, cap ? h("figcaption", { class: "cap" }, cap) : null); }
  function tipFor(box) {
    let t = box.querySelector(".tip"); if (!t) { t = h("div", { class: "tip", role: "tooltip" }); box.appendChild(t); }
    return { show(evt, text) { t.textContent = text; t.classList.add("on"); const r = box.getBoundingClientRect(); const x = (evt.clientX || r.left + r.width / 2) - r.left, y = (evt.clientY || r.top) - r.top;
      t.style.left = Math.max(4, Math.min(r.width - 244, x + 12)) + "px"; t.style.top = Math.max(4, y - 10) + "px"; }, hide() { t.classList.remove("on"); } };
  }

  // ------------------------------------------------------------------ OVERVIEW
  function viewOverview() {
    const A = S.A, SC = A.score, g = A.game;
    const wrap = h("div");
    wrap.appendChild(h("p", { class: "eyebrow" }, [g.genres && g.genres.length ? g.genres.slice(0, 3).join(" · ") : null, g.engine ? g.engine.join(", ") : null].filter(Boolean).join("  ·  ") || "Assessment"));
    wrap.appendChild(h("h1", null, g.title));
    if (g.pitch) wrap.appendChild(h("p", { class: "lede" }, trunc(g.pitch, 320)));
    const levels = {}; A.findings.forEach((f) => f.evidence.forEach((e) => { levels[e.level] = (levels[e.level] || 0) + 1; }));
    const hero = h("div", { class: "grid g-hero sec" },
      h("div", { class: "card" },
        h("p", { class: "eyebrow" }, "DESIGNCRAFT score"),
        h("div", { class: "hero" }, h("div", { class: "score" }, String(SC.overall), h("small", null, "/100")),
          h("div", null, conf(SC.confidence), h("div", { class: "sub", style: "margin-top:6px" }, "coverage " + pct(SC.coverage)), h("div", { class: "sub" }, "ceiling " + SC.ceiling))),
        rangeBar(SC.overall, SC.ceiling, 100),
        h("div", { class: "legend" }, h("span", null, h("i", { class: "sw", style: "background:var(--ink)" }), "measured score"), h("span", null, h("i", { class: "sw", style: "background:repeating-linear-gradient(135deg,var(--line2) 0 3px,transparent 3px 6px)" }), "ceiling if untested criteria were perfect")),
        h("p", { class: "sub", style: "margin-top:12px" }, SC.note),
        A.compare ? h("p", { class: "sub" }, `vs previous run: ${A.compare.overall.from} → ${A.compare.overall.to} (${A.compare.kind})`) : null,
        h("h3", { style: "margin-top:18px" }, "What the findings rest on"),
        h("div", { class: "rows", style: "margin-top:8px" }, ["playtested", "simulated", "source_verified", "inferred"].map((l) => h("div", { class: "row", style: "padding:9px 12px" }, lv(l), h("b", null, String(levels[l] || 0))))),
        h("p", { class: "sub", style: "margin-top:8px" }, A.playcraft ? `Simulated evidence: PLAYCRAFT run ${A.playcraft.run_id} (automated play of the built game). Nothing is playtested yet.` : "No PLAYCRAFT run exists for this game, so nothing here was observed in play.")),
      h("div", { class: "card" }, h("div", { class: "sec-h" }, h("h2", null, "Categories"), h("span", { class: "sub" }, "tap for criteria")), catList(SC.categories, criteriaSheet)));
    wrap.appendChild(hero);
    // opportunities
    const ranked = A.findings.filter((f) => f.proposals && f.proposals.length).sort((a, b) => b.priority - a.priority).slice(0, 5);
    const opp = h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, "Biggest opportunities"), h("a", { href: link("reports") }, "Full priority list →")));
    const rows = h("div", { class: "rows" });
    ranked.forEach((f, i) => {
      const best = f.proposals.map((id) => A.proposals.find((p) => p.id === id)).filter(Boolean).sort((a, b) => b.priority - a.priority)[0];
      rows.appendChild(h("a", { class: "row", href: link(TAB_OF_DEPT[f.dept], f.id) },
        h("span", { class: "t" }, (i + 1) + ". " + f.title), sev(f.severity),
        h("span", { class: "d" }, best ? h("span", null, h("b", null, best.label + ": "), best.proposal, " ", cx(best.complexity)) : null)));
    });
    if (!ranked.length) rows.appendChild(h("p", { class: "sub" }, "No significant weaknesses were found in the data that was available."));
    opp.appendChild(rows); wrap.appendChild(opp);
    // departments
    const dep = h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, "Departments")));
    const dg = h("div", { class: "grid g3" });
    A.departments_order.forEach((k) => {
      const D = A.departments[k]; const fs = A.findings.filter((f) => f.dept === k);
      const c = { critical: 0, major: 0, minor: 0, info: 0 }; fs.forEach((f) => c[f.severity]++);
      dg.appendChild(h("a", { class: "row", href: link(TAB_OF_DEPT[k]) }, h("span", { class: "t" }, D.title), h("span", { class: "sub" }, fs.length + " findings"),
        h("span", { class: "d" }, D.note ? "Not measured: missing data" : [c.critical ? c.critical + " critical" : null, c.major ? c.major + " major" : null, c.minor ? c.minor + " minor" : null].filter(Boolean).join(" · ") || "no weaknesses found")));
    });
    dep.appendChild(dg); wrap.appendChild(dep);
    // evidence + limits + history
    const ev = h("section", { class: "sec" },
      h("div", { class: "card" }, h("h3", null, "Limitations"), h("ul", { class: "limits", style: "margin-top:10px" }, A.inspection.limitations.map((l) => h("li", null, h("b", null, l.area + ": "), l.text)))));
    wrap.appendChild(ev);
    const hist = A.history || [];
    wrap.appendChild(h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, "Recent assessments"), h("a", { href: link("reports", "history") }, "History →")),
      h("div", { class: "rows" }, hist.slice(-4).reverse().map((r) => h("div", { class: "row" }, h("span", { class: "t" }, r.assessed_at.slice(0, 16).replace("T", " ")),
        h("span", null, h("b", null, String(r.overall)), h("span", { class: "sub" }, " / 100")), h("span", { class: "d" }, `method ${r.method} · content ${r.content} · ${r.findings} findings · confidence ${r.confidence}`))))));
    return wrap;
  }

  // ------------------------------------------------------------------ GAME MAP
  function viewMap() {
    const A = S.A, G = A.graph;
    const wrap = h("div", null, h("p", { class: "eyebrow" }, A.game.title), h("h1", null, "Game map"),
      h("p", { class: "lede" }, "The game model DESIGNCRAFT built from the repository: game → worlds → levels → missions → characters. Tap a node to see where it came from and what it connects to."));
    const types = [["game", "Game"], ["world", "Worlds"], ["level", "Levels"], ["mission", "Missions"], ["character", "Characters"]];
    const showAll = !!store("dc.map.all");
    const linked = new Set(); G.edges.forEach((e) => { linked.add(e[0]); linked.add(e[1]); });
    let nodes = G.nodes.filter((n) => showAll || n.type !== "level" || G.edges.some((e) => (e[0] === n.id && e[1].startsWith("m:")) || (e[1] === n.id && false)));
    const levelsAll = G.nodes.filter((n) => n.type === "level").length;
    const cols = types.map(([t]) => nodes.filter((n) => n.type === t));
    const W = 980, colW = W / types.length, rowH = 30, maxRows = Math.max(...cols.map((c) => c.length), 1);
    const H = Math.max(220, maxRows * rowH + 50);
    const pos = {};
    cols.forEach((c, ci) => { const off = (H - 40 - c.length * rowH) / 2 + 30; c.forEach((n, i) => { pos[n.id] = [ci * colW + 8, off + i * rowH]; }); });
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Game model graph" });
    types.forEach(([t, label], ci) => svg.appendChild(s("text", { x: ci * colW + 8, y: 14, "font-size": 12, "font-weight": 700, fill: "var(--mute)", text: `${label.toUpperCase()} (${cols[ci].length})` })));
    const eg = s("g"); svg.appendChild(eg);
    const ng = s("g"); svg.appendChild(ng);
    const detail = h("div", { class: "card detail" }, h("p", { class: "sub" }, "Select a node."));
    const edgeEls = [];
    G.edges.forEach((e) => {
      const a = pos[e[0]], b = pos[e[1]]; if (!a || !b) return;
      const x1 = a[0] + colW - 24, y1 = a[1] + 11, x2 = b[0], y2 = b[1] + 11;
      const same = Math.abs(a[0] - b[0]) < 1;
      const back = x2 < x1; const p = same ? `M${a[0]} ${y1} C${a[0] - 34} ${y1} ${b[0] - 34} ${y2} ${b[0]} ${y2}` : back ? `M${a[0]} ${y1} C${a[0] - 40} ${y1} ${b[0] + colW - 24 + 40} ${y2} ${b[0] + colW - 24} ${y2}` : `M${x1} ${y1} C${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}`;
      const el = s("path", { d: p, fill: "none", stroke: e[2] === "unlocks" ? "var(--accent)" : e[2] === "features" ? "var(--k4)" : "var(--line2)", "stroke-width": e[2] === "unlocks" ? 1.6 : 1, opacity: 0.75 });
      el._e = e; eg.appendChild(el); edgeEls.push(el);
    });
    const colorOf = { game: "var(--ink)", world: "var(--k5)", level: "var(--k2)", mission: "var(--k3)", character: "var(--k4)" };
    function select(n) {
      const nb = new Set([n.id]); G.edges.forEach((e) => { if (e[0] === n.id) nb.add(e[1]); if (e[1] === n.id) nb.add(e[0]); });
      ng.querySelectorAll(".node").forEach((el) => el.setAttribute("opacity", nb.has(el._n.id) ? 1 : 0.28));
      edgeEls.forEach((el) => el.setAttribute("opacity", el._e[0] === n.id || el._e[1] === n.id ? 1 : 0.12));
      detail.innerHTML = "";
      const outs = G.edges.filter((e) => e[0] === n.id).map((e) => [e[2], G.nodes.find((x) => x.id === e[1])]);
      const ins = G.edges.filter((e) => e[1] === n.id).map((e) => [e[2], G.nodes.find((x) => x.id === e[0])]);
      detail.appendChild(h("p", { class: "eyebrow" }, n.type));
      detail.appendChild(h("h3", null, n.label));
      if (n.ev) detail.appendChild(h("p", { class: "sub" }, "Defined in ", srcLink(n.ev), n.ev.symbol ? " (" + n.ev.symbol + ")" : ""));
      const ul = h("ul", { class: "limits", style: "margin-top:8px" });
      ins.concat(outs).forEach(([rel, x]) => { if (x) ul.appendChild(h("li", null, h("b", null, rel + ": "), x.label + " (" + x.type + ")")); });
      detail.appendChild(ul);
      if (n.type === "mission") detail.appendChild(h("p", null, h("a", { class: "btn sm", href: link("lab", "m:" + n.id.slice(2)) }, "Open in Design Lab")));
    }
    nodes.forEach((n) => {
      const p = pos[n.id]; if (!p) return;
      const g = s("g", { class: "node", tabindex: 0, role: "button", "aria-label": n.type + ": " + n.label, transform: `translate(${p[0]},${p[1]})`, onclick: () => select(n), onkeydown: (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n); } } });
      g._n = n;
      g.appendChild(s("rect", { width: colW - 24, height: 22, rx: 6, fill: "var(--surface)", stroke: colorOf[n.type], "stroke-width": 1.4 }));
      g.appendChild(s("rect", { width: 4, height: 22, rx: 2, fill: colorOf[n.type] }));
      g.appendChild(s("text", { x: 10, y: 15, "font-size": 12, text: trunc(n.label, 22) }));
      ng.appendChild(g);
    });
    const tools = h("div", { class: "viz-tools" },
      h("button", { class: "btn sm", "aria-pressed": showAll ? "true" : "false", onclick: () => { store("dc.map.all", !showAll); render(); } }, showAll ? `Showing all ${levelsAll} levels` : `Show all ${levelsAll} levels`),
      h("span", { class: "legend" }, h("span", null, h("i", { class: "sw", style: "background:var(--accent)" }), "unlocks"), h("span", null, h("i", { class: "sw", style: "background:var(--k4)" }), "features character"), h("span", null, h("i", { class: "sw", style: "background:var(--line2)" }), "contains / located")));
    const scroller = h("div", { style: "overflow-x:auto" }, h("div", { style: "min-width:760px" }, svg));
    wrap.appendChild(h("div", { class: "sec" }, vizBox(scroller, showAll ? "All levels shown." : "Levels shown are those missions take place in; use the button to show every placed location.", tools), detail));
    // inventory
    const M = A.model;
    wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "What the model contains"), h("div", { class: "kpis", style: "margin-top:12px" },
      [["missions", "missions"], ["places", "places"], ["worlds", "worlds / regions"], ["characters", "characters"], ["story", "story entries"], ["encounters", "encounter types"], ["progression", "progression entries"], ["stages", "stage rows"]]
        .map(([k, l]) => h("div", { class: "kpi" }, h("b", null, String((M[k] || []).length)), h("span", null, l)))),
      h("div", { class: "tbl sec" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Collection"), h("th", null, "Read as"), h("th", { class: "num" }, "Items"), h("th", null, "Source"))),
        h("tbody", null, A.inspection.collections.map((c) => h("tr", null, h("td", null, c.symbol), h("td", null, c.as + (c.also ? " + " + c.also : "")), h("td", { class: "num" }, String(c.items)), h("td", null, srcLink(c)))))))));
    if (A.inspection.unclassified.length) wrap.appendChild(h("p", { class: "sub" }, "Not recognised as design data (left out rather than guessed): " + A.inspection.unclassified.map((c) => c.symbol).join(", ") + "."));
    return wrap;
  }

  // ------------------------------------------------------------------ LEVELCRAFT
  function spatial(V, opts) {
    const places = V.places || []; if (!places.length) return null;
    const paths = V.paths || [];
    let xs = places.map((p) => p.x), ys = places.map((p) => p.y);
    paths.forEach((p) => p.points.forEach((q) => { xs.push(q[0]); ys.push(q[1]); }));
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const W = 760, pad = 26, sc = (W - 2 * pad) / Math.max(1, x1 - x0); const H = Math.max(260, Math.min(760, (y1 - y0) * sc + 2 * pad));
    const scy = (H - 2 * pad) / Math.max(1, y1 - y0); const k = Math.min(sc, scy);
    const X = (x) => pad + (x - x0) * k, Y = (y) => pad + (y - y0) * k;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Level layout: placed locations and mission routes" });
    if (V.grid) {
      const [gx0, gy0, gx1, gy1] = V.grid.bounds, n = V.grid.n;
      V.grid.cells.forEach(([i, j, c]) => {
        const cx0 = X(gx0 + (gx1 - gx0) * i / n), cy0 = Y(gy0 + (gy1 - gy0) * j / n);
        svg.appendChild(s("rect", { x: cx0, y: cy0, width: (gx1 - gx0) / n * k, height: (gy1 - gy0) / n * k, fill: c ? "var(--prop-soft)" : "none", stroke: "var(--line)", "stroke-dasharray": c ? null : "3 3", opacity: c ? Math.min(1, 0.35 + c / 8) : 1 }));
      });
    }
    const kinds = [...new Set(places.map((p) => p.kind))];
    const box = h("div");
    const sel = opts && opts.mission;
    paths.forEach((p, i) => {
      if (p.points.length < 2) return;
      const on = !sel || sel === p.id;
      svg.appendChild(s("polyline", { points: p.points.map((q) => X(q[0]) + "," + Y(q[1])).join(" "), fill: "none", stroke: on ? (p.return_leg ? "var(--accent)" : kc(i)) : "var(--line2)", "stroke-width": on && sel ? 3 : 1.6, opacity: on ? 0.9 : 0.3, "stroke-linejoin": "round" }));
      if (on && sel) p.points.forEach((q, j) => svg.appendChild(s("text", { x: X(q[0]) + 6, y: Y(q[1]) - 6, "font-size": 11, "font-weight": 700, fill: "var(--ink)", text: String(j + 1) })));
    });
    const tip = { show() {}, hide() {} };
    places.forEach((p) => {
      const r = p.named ? 5 : 2.6;
      const c = s("circle", { cx: X(p.x), cy: Y(p.y), r, fill: kc(kinds.indexOf(p.kind)), stroke: "var(--surface)", "stroke-width": 1.2, class: p.named ? "node" : null, tabindex: p.named ? 0 : null });
      if (p.named) {
        c.appendChild(s("title", { text: `${p.name} · ${p.kind}${p.content ? " · " + p.content + " finds" : ""}` }));
        svg.appendChild(c);
      } else svg.appendChild(c);
    });
    places.filter((p) => p.named).slice(0, 18).forEach((p) => svg.appendChild(s("text", { x: X(p.x) + 7, y: Y(p.y) + 4, "font-size": 10.5, text: trunc(p.name, 20), opacity: 0.85 })));
    if (V.hub && V.hub.x != null) {
      svg.appendChild(s("rect", { x: X(V.hub.x) - 7, y: Y(V.hub.y) - 7, width: 14, height: 14, fill: "var(--ink)", rx: 3, transform: `rotate(45 ${X(V.hub.x)} ${Y(V.hub.y)})` }));
      svg.appendChild(s("text", { x: X(V.hub.x) + 12, y: Y(V.hub.y) + 16, "font-size": 11, "font-weight": 700, fill: "var(--ink)", text: "HUB · " + V.hub.label }));
    }
    box.appendChild(svg);
    box.appendChild(h("div", { class: "legend", style: "margin-top:8px" }, kinds.slice(0, 10).map((kd, i) => h("span", null, h("i", { class: "sw", style: `background:${kc(i)};border-radius:50%` }), kd)),
      h("span", null, h("i", { class: "sw", style: "background:var(--accent)" }), "route ends with a return to the hub"), V.grid ? h("span", null, h("i", { class: "sw", style: "border:1px dashed var(--line2)" }), "empty grid cell") : null));
    return box;
  }
  function viewLevel(r) {
    const A = S.A, D = A.departments.levelcraft, m = D.metrics;
    const wrap = h("div", null, deptHead("levelcraft", "Spatial layout, navigation, discovery and travel friction, measured from placed locations and the routes missions send the player along."));
    wrap.appendChild(h("div", { class: "sec" }, metricsBlock(m, [["named", "named places"], ["regions", "regions"], ["named_places_used_by_missions", "named places used by missions"], ["empty_cells", "empty grid cells"],
      ["return_to_hub", "missions ending at the hub"], ["mission_travel_median", "median route length"], ["landmarks", "landmark features"], ["secrets_and_caches", "secrets and caches"]])));
    const V = D.viz;
    const missionSel = store("dc.lv.m." + A.game.id);
    if (V.places && V.places.length) {
      const tools = h("div", { class: "viz-tools" });
      const sel = h("select", { class: "btn sm", "aria-label": "Highlight a mission route", onchange: (e) => { store("dc.lv.m." + A.game.id, e.target.value || null); render(); } },
        h("option", { value: "" }, "All mission routes"), (V.paths || []).filter((p) => p.points.length > 1).map((p) => h("option", { value: p.id, selected: missionSel === p.id ? true : null }, p.title)));
      tools.appendChild(sel);
      const path = (V.paths || []).find((p) => p.id === missionSel);
      wrap.appendChild(h("div", { class: "sec" }, vizBox(spatial(V, { mission: missionSel }), path ? `${path.title}: ${path.points.length} positioned objectives, about ${fmt(path.distance, 0)} units of travel${path.return_leg ? ", ending back at the hub" : ""}.` : "Every placed location (large dots are named places) with the routes missions take between their objectives. Coordinates come straight from the game's data.", tools)));
    } else wrap.appendChild(h("div", { class: "note sec" }, h("b", null, "No geometry. "), D.note || "No placed locations were found."));
    wrap.appendChild(findingsBlock("levelcraft"));
    return wrap;
  }

  // ------------------------------------------------------------------ MISSIONCRAFT
  function dag(G, onPick, selected) {
    const byD = {}; G.nodes.forEach((n) => { (byD[n.depth] = byD[n.depth] || []).push(n); });
    const depths = Object.keys(byD).map(Number).sort((a, b) => a - b);
    const W = 900, colW = Math.max(170, W / Math.max(1, depths.length)), rowH = 56;
    const H = Math.max(...depths.map((d) => byD[d].length)) * rowH + 40;
    const svgW = Math.max(W, depths.length * colW);
    const svg = s("svg", { viewBox: `0 0 ${svgW} ${H}`, role: "img", "aria-label": "Mission dependency graph" });
    const pos = {}; const kinds = [...new Set(G.nodes.map((n) => n.kind))];
    depths.forEach((d, ci) => byD[d].forEach((n, i) => { pos[n.id] = [ci * colW + 10, 26 + i * rowH + (H - 40 - byD[d].length * rowH) / 2]; }));
    depths.forEach((d, ci) => svg.appendChild(s("text", { x: ci * colW + 10, y: 14, "font-size": 11.5, "font-weight": 700, fill: "var(--mute)", text: d === 0 ? "AVAILABLE AT START" : "UNLOCK DEPTH " + d })));
    G.edges.forEach(([a, b]) => { const p = pos[a], q = pos[b]; if (!p || !q) return;
      svg.appendChild(s("path", { d: `M${p[0] + colW - 30} ${p[1] + 20} C${p[0] + colW} ${p[1] + 20} ${q[0] - 20} ${q[1] + 20} ${q[0]} ${q[1] + 20}`, fill: "none", stroke: "var(--line2)", "stroke-width": 1.5, "marker-end": "url(#ah)" })); });
    svg.appendChild(s("defs", null, s("marker", { id: "ah", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 7, markerHeight: 7, orient: "auto" }, s("path", { d: "M0 0L8 4L0 8z", fill: "var(--line2)" }))));
    G.nodes.forEach((n) => { const p = pos[n.id];
      const g = s("g", { class: "node", transform: `translate(${p[0]},${p[1]})`, tabindex: 0, role: "button", "aria-label": `${n.title}: ${n.objectives} objectives`, onclick: () => onPick(n), onkeydown: (e) => { if (e.key === "Enter") onPick(n); } });
      g.appendChild(s("rect", { width: colW - 30, height: 40, rx: 8, fill: selected === n.id ? "var(--prop-soft)" : "var(--surface)", stroke: kc(kinds.indexOf(n.kind)), "stroke-width": selected === n.id ? 2.5 : 1.4, "stroke-dasharray": n.dynamic ? "4 3" : null }));
      g.appendChild(s("text", { x: 10, y: 17, "font-size": 12.5, "font-weight": 600, fill: "var(--ink)", text: trunc(n.title, Math.floor((colW - 40) / 7)) }));
      g.appendChild(s("text", { x: 10, y: 32, "font-size": 11, fill: "var(--mute)", text: `${n.objectives} obj · ${n.kind || "—"}${n.reward != null ? " · " + fmt(n.reward, 0) : ""}` }));
      svg.appendChild(g); });
    const box = h("div", null, h("div", { style: "overflow-x:auto" }, h("div", { style: `min-width:${Math.min(svgW, 900)}px` }, svg)),
      h("div", { class: "legend", style: "margin-top:8px" }, kinds.map((k, i) => h("span", null, h("i", { class: "sw", style: `border:2px solid ${kc(i)}` }), k || "unlabelled")), h("span", null, h("i", { class: "sw", style: "border:2px dashed var(--mute)" }), "repeatable")));
    return box;
  }
  function verbMatrix(rows) {
    const verbs = []; rows.forEach((r) => r.verbs.forEach((v) => { if (!verbs.includes(v)) verbs.push(v); }));
    const t = h("table", null, h("thead", null, h("tr", null, h("th", null, "Mission"), verbs.map((v) => h("th", { class: "num", style: "writing-mode:vertical-rl;transform:rotate(180deg);padding:8px 4px" }, v)))),
      h("tbody", null, rows.map((r) => h("tr", null, h("td", null, trunc(r.title, 34)), verbs.map((v) => { const n = r.verbs.filter((x) => x === v).length;
        return h("td", { class: "num", title: n ? `${r.title}: ${v} ×${n}` : null }, n ? h("span", { style: `display:inline-block;width:${8 + n * 5}px;height:${8 + n * 5}px;border-radius:50%;background:var(--prop);opacity:${0.45 + n * 0.18}` }) : h("span", { style: "color:var(--line2)" }, "·")); })))));
    return h("div", { class: "tbl" }, t);
  }
  function scatter(pts, xl, yl) {
    const W = 560, H = 300, p = 44;
    const xs = pts.map((d) => d.x), ys = pts.map((d) => d.y);
    const x0 = 0, x1 = Math.max(...xs) * 1.1 || 1, y0 = 0, y1 = Math.max(...ys) * 1.1 || 1;
    const X = (x) => p + (x - x0) / (x1 - x0) * (W - p - 12), Y = (y) => H - p + 10 - (y - y0) / (y1 - y0) * (H - p - 10);
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${yl} against ${xl}` });
    [0, 0.5, 1].forEach((f) => { const yy = Y(y0 + f * (y1 - y0)); svg.appendChild(s("line", { x1: p, x2: W - 12, y1: yy, y2: yy, class: "gridln" })); svg.appendChild(s("text", { x: p - 6, y: yy + 4, "text-anchor": "end", "font-size": 11, text: fmt(y0 + f * (y1 - y0), 0) })); });
    svg.appendChild(s("text", { x: W / 2, y: H - 4, "text-anchor": "middle", "font-size": 11.5, fill: "var(--mute)", text: xl }));
    svg.appendChild(s("text", { x: 12, y: 16, "font-size": 11.5, fill: "var(--mute)", text: yl }));
    pts.forEach((d) => { const c = s("circle", { cx: X(d.x), cy: Y(d.y), r: 6, fill: "var(--prop)", opacity: 0.85, stroke: "var(--surface)", "stroke-width": 1.5 }); c.appendChild(s("title", { text: `${d.label}: ${yl} ${fmt(d.y, 0)}, ${xl} ${fmt(d.x)}` })); svg.appendChild(c);
      svg.appendChild(s("text", { x: X(d.x) + 8, y: Y(d.y) + 4, "font-size": 10.5, text: trunc(d.label, 18) })); });
    return svg;
  }
  function viewMission(r) {
    const A = S.A, D = A.departments.missioncraft, m = D.metrics;
    const wrap = h("div", null, deptHead("missioncraft", "Objectives, variety, repetition, escalation, alternate solutions, rewards, failure and consequences, measured from the mission definitions."));
    wrap.appendChild(h("div", { class: "sec" }, metricsBlock(m, [["missions", "missions"], ["objectives", "objectives"], ["verb_variety", "objective variety (0–1)"], ["unique_structures", "distinct structures"],
      ["travel_share", "travel share", pct], ["objectives_with_alternatives", "objectives with alternatives"], ["optional_objectives", "optional objectives"], ["dependency_depth", "unlock depth"]])));
    if (D.viz.graph) {
      const sel = store("dc.ms.sel." + A.game.id);
      const detail = h("div", { class: "card detail" });
      const showDetail = (n) => {
        store("dc.ms.sel." + A.game.id, n.id);
        const mm = A.model.missions.find((x) => x.id === n.id); detail.innerHTML = "";
        if (!mm) return;
        detail.appendChild(missionOriginal(mm));
        detail.appendChild(h("p", { style: "margin-top:10px" }, h("a", { class: "btn sm pri", href: link("lab", "m:" + mm.id) }, "Explore alternatives in the Design Lab")));
      };
      wrap.appendChild(h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, "Mission dependencies"), h("span", { class: "sub" }, "tap a mission")),
        vizBox(dag(D.viz.graph, (n) => { showDetail(n); }, sel), "Missions placed by how many prerequisites stand before them. Dashed: repeatable or dynamic jobs."), detail));
      const first = sel && D.viz.graph.nodes.find((n) => n.id === sel); if (first) showDetail(first); else detail.appendChild(h("p", { class: "sub" }, "Select a mission to read its original definition."));
    }
    if (D.viz.verbs_by_mission) wrap.appendChild(h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, "Mission variety"), h("span", { class: "sub" }, "objective types per mission")), verbMatrix(D.viz.verbs_by_mission)));
    if (D.viz.rewards && D.viz.rewards.some((x) => x.reward != null)) wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Reward against effort"),
      h("div", { style: "margin-top:12px" }, vizBox(scatter(D.viz.rewards.filter((x) => x.reward != null).map((x) => ({ x: x.effort, y: x.reward, label: x.title })), "effort (objectives + distinct actions)", m.reward_currency || "reward"),
        `Rank correlation between reward and effort: ${fmt(m.reward_effort_rank_corr, 2)}. A fair economy rises left to right.`))));
    wrap.appendChild(findingsBlock("missioncraft"));
    return wrap;
  }
  function missionOriginal(mm) {
    return h("div", null, h("p", { class: "lock" }, "Original design · read-only"), h("h3", null, mm.title),
      h("p", { class: "sub" }, [mm.kind, mm.giver ? "from " + mm.giver : null, mm.requires.length ? "requires " + mm.requires.join(", ") : "available at start"].filter(Boolean).join(" · ")),
      mm.brief ? h("p", null, mm.brief) : null,
      h("ol", { class: "objs" }, mm.objectives.map((o) => h("li", null, h("span", null, h("span", { class: "tag " + (/^(goto|go|get to|head|ride|fly|return|reach|land)/.test(o.verb) ? "trv" : "act") }, o.verb), " ", o.text || "", o.targets && o.targets[0] && o.targets[0].label ? h("span", { class: "sub" }, " → " + o.targets[0].label) : null,
        o.options && o.options.length ? h("span", { class: "sub" }, " (by " + o.options.join(" / ") + ")") : null)))),
      h("p", { class: "sub", style: "margin-top:8px" }, Object.keys(mm.reward || {}).length ? "Reward: " + Object.entries(mm.reward).map(([k, v]) => k + " " + fmt(v, 0)).join(", ") + " · " : "", "Source: ", srcLink(mm.ev)));
  }

  // ------------------------------------------------------------------ STORYCRAFT
  function castChart(cast) {
    const rows = cast.slice().sort((a, b) => (b.mentions + b.lines * 2 + b.missions * 3) - (a.mentions + a.lines * 2 + a.missions * 3)).slice(0, 18);
    const mx = Math.max(1, ...rows.map((c) => c.mentions + c.lines + c.missions));
    const W = 640, rh = 26, H = rows.length * rh + 30, lx = 150;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Character presence" });
    const cols = [["mentions", "var(--k1)"], ["lines", "var(--k2)"], ["missions", "var(--k3)"]];
    rows.forEach((c, i) => { const y = 10 + i * rh; let x = lx;
      svg.appendChild(s("text", { x: lx - 8, y: y + 13, "text-anchor": "end", "font-size": 12, text: trunc(c.name, 20) + (c.inferred ? " *" : "") }));
      cols.forEach(([k, col]) => { const w = (c[k] / mx) * (W - lx - 60); if (w > 0) { const rr = s("rect", { x, y: y + 2, width: w, height: 16, fill: col, rx: 3 }); rr.appendChild(s("title", { text: `${c.name}: ${c[k]} ${k}` })); svg.appendChild(rr); x += w + 1; } });
      svg.appendChild(s("text", { x: x + 6, y: y + 14, "font-size": 11, fill: "var(--mute)", text: `${c.mentions}·${c.lines}·${c.missions}` })); });
    return h("div", null, svg, h("div", { class: "legend" }, cols.map(([k, col]) => h("span", null, h("i", { class: "sw", style: `background:${col}` }), k)), h("span", null, "* inferred from recurring names in the writing")));
  }
  function relGraph(rel, cast) {
    const names = [...new Set(rel.flatMap((r) => [r[0], r[1]]))].slice(0, 16);
    if (names.length < 2) return null;
    const W = 520, H = 400, cx0 = W / 2, cy0 = H / 2, R = 150;
    const pos = {}; names.forEach((n, i) => { const a = -Math.PI / 2 + i * 2 * Math.PI / names.length; pos[n] = [cx0 + R * Math.cos(a), cy0 + R * Math.sin(a)]; });
    const mx = Math.max(...rel.map((r) => r[2]));
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Character relationships by co-mention" });
    rel.forEach(([a, b, n]) => { if (!pos[a] || !pos[b]) return; const l = s("line", { x1: pos[a][0], y1: pos[a][1], x2: pos[b][0], y2: pos[b][1], stroke: "var(--k4)", "stroke-width": 1 + 5 * n / mx, opacity: 0.35 + 0.5 * n / mx }); l.appendChild(s("title", { text: `${a} & ${b}: ${n} shared lines` })); svg.appendChild(l); });
    names.forEach((n) => { const p = pos[n]; const deg = rel.filter((r) => r[0] === n || r[1] === n).reduce((t, r) => t + r[2], 0);
      svg.appendChild(s("circle", { cx: p[0], cy: p[1], r: 6 + Math.min(12, deg), fill: "var(--surface)", stroke: "var(--k4)", "stroke-width": 2 }));
      const right = p[0] >= cx0; svg.appendChild(s("text", { x: p[0] + (right ? 16 : -16), y: p[1] + 4, "text-anchor": right ? "start" : "end", "font-size": 12, "font-weight": 600, fill: "var(--ink)", text: n })); });
    return svg;
  }
  function storyTimeline(rows, cast) {
    const W = 760, H = 230, p = 36, mx = Math.max(1, ...rows.map((r) => r.words));
    const bw = (W - p - 10) / rows.length;
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Story words per mission in campaign order" });
    svg.appendChild(s("line", { x1: p, x2: W - 10, y1: H - 50, y2: H - 50, class: "ax" }));
    rows.forEach((r, i) => { const hh = (r.words / mx) * (H - 90); const x = p + i * bw + 4;
      const b = s("rect", { x, y: H - 50 - hh, width: Math.max(6, bw - 8), height: hh, rx: 3, fill: "var(--k5)", opacity: 0.85 }); b.appendChild(s("title", { text: `${r.title}: ${r.words} words, ${r.characters} characters` })); svg.appendChild(b);
      for (let k = 0; k < r.characters; k++) svg.appendChild(s("circle", { cx: x + Math.max(6, bw - 8) / 2, cy: H - 50 - hh - 8 - k * 9, r: 3.2, fill: "var(--k4)" }));
      svg.appendChild(s("text", { x: x + 2, y: H - 34, "font-size": 10.5, transform: `rotate(28 ${x + 2} ${H - 34})`, text: trunc(r.title, 16) })); });
    svg.appendChild(s("text", { x: 4, y: 14, "font-size": 11.5, fill: "var(--mute)", text: "words of story text per mission, campaign order · dots: characters named" }));
    return svg;
  }
  function viewStory() {
    const A = S.A, D = A.departments.storycraft, m = D.metrics;
    const wrap = h("div", null, deptHead("storycraft", "Cast, voice, coherence, pacing and payoffs, measured from every authored string the game ships: briefs, lines, clues, endings and place text."));
    wrap.appendChild(h("div", { class: "sec" }, metricsBlock(m, [["characters", "characters"], ["authored_words", "authored words"], ["dialogue_lines", "dialogue lines"], ["endings", "endings"],
      ["scripted_choices", "scripted choices"], ["doc_claims_checked", "doc claims checked"], ["places_with_lore", "places with lore"]])));
    const V = D.viz;
    if (V.cast && V.cast.length) wrap.appendChild(h("section", { class: "sec grid g2" },
      h("div", null, h("h2", null, "Cast presence"), h("div", { style: "margin-top:12px" }, vizBox(castChart(V.cast), "Mentions in authored text, spoken lines and missions each character appears in."))),
      h("div", null, h("h2", null, "Relationships"), h("div", { style: "margin-top:12px" }, V.relations && V.relations.length ? vizBox(relGraph(V.relations, V.cast), "Characters linked when the same line or brief names both. Thicker: more shared lines.") : h("p", { class: "sub" }, "No two characters are named in the same line.")))));
    if (V.story_density && V.story_density.length) wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Story timeline"), h("div", { style: "margin-top:12px" }, vizBox(storyTimeline(V.story_density, V.cast), m.story_words_by_third ? `Story text by campaign third: ${m.story_words_by_third.map(pct).join(" · ")}.` : null))));
    const cats = m.story_entries || {};
    if (Object.keys(cats).length) wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Narrative content"), h("div", { class: "kpis", style: "margin-top:12px" }, Object.entries(cats).map(([k, v]) => h("div", { class: "kpi" }, h("b", null, String(v)), h("span", null, k))))));
    wrap.appendChild(findingsBlock("storycraft"));
    return wrap;
  }

  // ------------------------------------------------------------------ PROGRESSION
  function curveChart(c) {
    const W = 640, H = 260, p = 40, keys = Object.keys(c.series).slice(0, 6), n = c.labels.length;
    const X = (i) => p + i * (W - p - 20) / Math.max(1, n - 1);
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${c.collection} curves` });
    [0, 0.5, 1].forEach((f) => { const y = H - 50 - f * (H - 80); svg.appendChild(s("line", { x1: p, x2: W - 20, y1: y, y2: y, class: "gridln" })); svg.appendChild(s("text", { x: p - 6, y: y + 4, "text-anchor": "end", "font-size": 10.5, fill: "var(--mute)", text: f === 1 ? "max" : f === 0 ? "min" : "" })); });
    keys.forEach((k, ki) => { const v = c.series[k]; const lo = Math.min(...v), hi = Math.max(...v); const Y = (x) => H - 50 - (hi === lo ? 0.5 : (x - lo) / (hi - lo)) * (H - 80);
      svg.appendChild(s("polyline", { points: v.map((x, i) => X(i) + "," + Y(x)).join(" "), fill: "none", stroke: kc(ki), "stroke-width": 2.2, "stroke-linejoin": "round" }));
      v.forEach((x, i) => { const d = s("circle", { cx: X(i), cy: Y(x), r: 3.6, fill: kc(ki) }); d.appendChild(s("title", { text: `${c.labels[i]} · ${k}: ${fmt(x, 2)}` })); svg.appendChild(d); }); });
    c.labels.forEach((l, i) => svg.appendChild(s("text", { x: X(i), y: H - 30, "text-anchor": i === 0 ? "start" : i === n - 1 ? "end" : "middle", "font-size": 10.5, text: trunc(l, 14) })));
    return h("div", null, svg, h("div", { class: "legend" }, keys.map((k, i) => h("span", null, h("i", { class: "sw", style: `background:${kc(i)}` }), k))));
  }
  function viewProgression() {
    const A = S.A, D = A.departments.progressioncraft, m = D.metrics;
    const wrap = h("div", null, deptHead("progressioncraft", "Difficulty curves, stage escalation, unlock structure, reward pacing and the economy, measured from stage tables, unlocks and mission rewards."));
    wrap.appendChild(h("div", { class: "sec" }, metricsBlock(m, [["stage_tables", "stage tables"], ["progression_entries", "unlocks / items / goals"], ["campaign_income", "campaign income"], ["price_total", "cost of everything"],
      ["missions_per_purchase_median", "missions per unlock"], ["entries_with_prerequisites", "unlocks with prerequisites"], ["long_term_goals", "long-term goals"]])));
    (D.viz.curves || []).forEach((c) => {
      const tbl = h("div", { class: "tbl", style: "margin-top:10px" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Entry"), Object.keys(c.series).map((k) => h("th", { class: "num" }, k)))),
        h("tbody", null, c.labels.map((l, i) => h("tr", null, h("td", null, l), Object.values(c.series).map((v) => h("td", { class: "num" }, fmt(v[i], 2))))))));
      wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Curve: " + c.collection), h("div", { style: "margin-top:12px" }, vizBox(curveChart(c), "Each series normalised to its own range so their shapes compare; exact values in the table."), tbl)));
    });
    if (D.viz.economy) {
      const E = D.viz.economy; const inc = E.income.filter((x) => !x.dynamic); const pr = E.prices.slice().sort((a, b) => a.v - b.v);
      const mx = Math.max(...pr.map((x) => x.v), ...inc.map((x) => x.v), 1);
      const W = 640, rh = 18; const rows = inc.length + pr.length; const H = rows * rh + 60;
      const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Income per mission and unlock prices" });
      let y = 18; svg.appendChild(s("text", { x: 0, y: 12, "font-size": 11.5, "font-weight": 700, fill: "var(--mute)", text: "INCOME PER MISSION (" + (m.currency || "") + ")" }));
      inc.forEach((x) => { svg.appendChild(s("text", { x: 170, y: y + 12, "text-anchor": "end", "font-size": 11, text: trunc(x.title, 26) })); svg.appendChild(s("rect", { x: 176, y: y + 2, width: (x.v / mx) * (W - 240), height: 12, rx: 3, fill: "var(--prop)" })); svg.appendChild(s("text", { x: 180 + (x.v / mx) * (W - 240), y: y + 12, "font-size": 10.5, fill: "var(--mute)", text: fmt(x.v, 0) })); y += rh; });
      y += 18; svg.appendChild(s("text", { x: 0, y: y - 4, "font-size": 11.5, "font-weight": 700, fill: "var(--mute)", text: "PRICES" }));
      pr.forEach((x) => { svg.appendChild(s("text", { x: 170, y: y + 12, "text-anchor": "end", "font-size": 11, text: trunc(x.name, 26) })); svg.appendChild(s("rect", { x: 176, y: y + 2, width: (x.v / mx) * (W - 240), height: 12, rx: 3, fill: "var(--accent)", opacity: 0.8 })); svg.appendChild(s("text", { x: 180 + (x.v / mx) * (W - 240), y: y + 12, "font-size": 10.5, fill: "var(--mute)", text: fmt(x.v, 0) })); y += rh; });
      wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Economy"), h("div", { style: "margin-top:12px" }, vizBox(svg, `The non-repeating campaign pays ${fmt(m.campaign_income, 0)}; everything priced costs ${fmt(m.price_total, 0)}.`))));
    }
    if (D.viz.tree && D.viz.tree.nodes.length) {
      const by = {}; D.viz.tree.nodes.forEach((n) => { (by[n.collection] = by[n.collection] || []).push(n); });
      wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Progression trees"), h("div", { class: "grid g2", style: "margin-top:12px" }, Object.entries(by).map(([k, ns]) => h("div", { class: "card" }, h("h3", null, k), h("p", { class: "sub" }, ns.length + " entries"),
        h("div", { style: "margin-top:8px" }, ns.slice(0, 40).map((n) => { const req = D.viz.tree.edges.filter((e) => e[1] === n.id).map((e) => e[0]);
          return h("span", { class: "tag", title: req.length ? "requires " + req.join(", ") : null }, n.name + (n.cost != null ? " · " + fmt(n.cost, 0) : "") + (req.length ? " ←" + req.length : "")); })))))));
    }
    wrap.appendChild(findingsBlock("progressioncraft"));
    return wrap;
  }

  // ------------------------------------------------------------------ EXPERIENCE
  function journeyChart(J) {
    const W = 780, H = 300, p = 36; const n = J.length; const X = (i) => p + (i + 0.5) * (W - p - 10) / n;
    const mw = Math.max(1, ...J.map((j) => j.story_words));
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Player journey: intensity and story by step" });
    [0, 5, 10].forEach((v) => { const y = 30 + (10 - v) / 10 * 170; svg.appendChild(s("line", { x1: p, x2: W - 10, y1: y, y2: y, class: "gridln" })); svg.appendChild(s("text", { x: p - 6, y: y + 4, "text-anchor": "end", "font-size": 10.5, fill: "var(--mute)", text: String(v) })); });
    J.forEach((j, i) => { const bh = (j.story_words / mw) * 60; svg.appendChild(s("rect", { x: X(i) - 9, y: 200 - bh, width: 18, height: bh, fill: "var(--k5)", opacity: 0.35, rx: 3 })); });
    svg.appendChild(s("polyline", { points: J.map((j, i) => X(i) + "," + (30 + (10 - j.intensity) / 10 * 170)).join(" "), fill: "none", stroke: "var(--accent)", "stroke-width": 2.5, "stroke-linejoin": "round" }));
    J.forEach((j, i) => { const y = 30 + (10 - j.intensity) / 10 * 170;
      const c = s("circle", { cx: X(i), cy: y, r: 5, fill: j.dynamic ? "var(--surface)" : "var(--accent)", stroke: "var(--accent)", "stroke-width": 2 }); c.appendChild(s("title", { text: `${j.step}. ${j.title} · intensity ${j.intensity} · ${j.story_words} story words${j.new_verbs.length ? " · new: " + j.new_verbs.join(", ") : ""}` })); svg.appendChild(c);
      if (j.new_verbs.length) svg.appendChild(s("text", { x: X(i), y: y - 10, "text-anchor": "middle", "font-size": 10, fill: "var(--prop)", "font-weight": 700, text: "+" + j.new_verbs.length }));
      svg.appendChild(s("text", { x: X(i) - 4, y: 218, "font-size": 10.5, transform: `rotate(32 ${X(i) - 4} 218)`, text: trunc(j.title, 16) })); });
    return h("div", null, svg, h("div", { class: "legend" }, h("span", null, h("i", { class: "sw", style: "background:var(--accent)" }), "estimated intensity (inferred)"), h("span", null, h("i", { class: "sw", style: "background:var(--k5);opacity:.5" }), "story words"), h("span", null, h("b", { style: "color:var(--prop)" }, "+n"), " new objective types introduced"), h("span", null, "hollow: repeatable")));
  }
  function viewExperience() {
    const A = S.A, D = A.departments.experiencecraft, m = D.metrics;
    const wrap = h("div", null, deptHead("experiencecraft", "The combined player experience: what only shows when levels, missions, story and progression are read together, plus PLAYCRAFT's automated play where it exists."));
    const J = D.viz.journey || [];
    if (J.length) wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Player journey"), h("div", { style: "margin-top:12px" }, vizBox(journeyChart(J),
      "Missions in unlock order. Intensity is DESIGNCRAFT's estimate from distinct actions, objective count, threat language and fail states; it is a model of pacing, not a measurement of players."))));
    else wrap.appendChild(h("div", { class: "note sec" }, h("b", null, "No journey. "), "No missions were found as data, so the campaign's pacing cannot be traced."));
    const ag = m.agency_sources || {};
    wrap.appendChild(h("section", { class: "sec grid g2" },
      h("div", { class: "card" }, h("h3", null, "Where the player decides"), h("div", { class: "rows", style: "margin-top:10px" }, Object.entries(ag).map(([k, v]) => h("div", { class: "row" }, h("span", null, k.replace(/_/g, " ")), h("b", null, String(v)))))),
      h("div", { class: "card" }, h("h3", null, "PLAYCRAFT evidence"), A.playcraft ? h("div", null,
        h("p", { class: "sub" }, `Run ${A.playcraft.run_id} · played ${A.playcraft.viewports ? A.playcraft.viewports.join(" + ") : ""} · PLAYCRAFT score ${A.playcraft.overall}`),
        h("div", { class: "tbl", style: "margin-top:8px;max-height:280px" }, h("table", null, h("tbody", null, A.playcraft.criteria.map((c) => h("tr", null, h("td", null, lv(c.level)), h("td", null, c.title), h("td", null, c.status))))))) :
        h("p", { class: "sub" }, "No PLAYCRAFT run is recorded for this game. Run PLAYCRAFT on it to add simulated evidence; DESIGNCRAFT will import it on the next assessment."))));
    wrap.appendChild(findingsBlock("experiencecraft"));
    return wrap;
  }

  // ------------------------------------------------------------------ DESIGN LAB
  const labKey = () => "dc.lab." + S.A.game.id;
  const labState = () => store(labKey()) || { saved: [], threads: {} };
  const labSave = (st) => store(labKey(), st);
  function allProposals() {
    const out = S.A.proposals.slice(); Object.values(S.A.lab || {}).forEach((ps) => out.push(...ps)); return out;
  }
  function currentVersion(p, st) { const th = st.threads[p.id]; return th && th.versions.length ? th.versions[th.versions.length - 1] : p; }
  function viewLab(r) {
    const A = S.A; const st = labState();
    const wrap = h("div", null, h("p", { class: "eyebrow" }, A.game.title), h("h1", null, "Design Lab"),
      h("p", { class: "lede" }, "Pick a mission or a finding, read the original design (never modified), compare alternatives side by side, refine one through conversation, save it, and export an implementation-ready spec."));
    const missions = A.model.missions.filter((m) => !m.chain);
    const fwith = A.findings.filter((f) => f.proposals && f.proposals.length);
    let sub = r.sub || (missions[0] ? "m:" + missions[0].id : fwith[0] ? "f:" + fwith[0].id : null);
    if (sub && sub.startsWith("p:")) { const p = allProposals().find((x) => x.id === sub.slice(2)); if (p) sub = p.finding ? "f:" + p.finding + "|" + p.id : "m:" + p.id.slice(4).split(":")[0] + "|" + p.id; }
    const [target, focusPid] = (sub || "").split("|");
    const list = h("div", { class: "lab-list", role: "list" });
    if (missions.length) { list.appendChild(h("p", { class: "eyebrow", style: "margin:4px 0" }, "Missions")); missions.forEach((m) => { const n = A.findings.filter((f) => f.entities.includes(m.id)).length;
      list.appendChild(h("a", { class: "pick", href: link("lab", "m:" + m.id), "aria-current": target === "m:" + m.id ? "true" : null, role: "listitem" }, h("span", null, m.title, h("br"), h("small", null, (m.kind || "") + " · " + m.objectives.length + " objectives")), n ? h("span", { class: "chip sev-minor" }, n) : null)); }); }
    if (fwith.length) { list.appendChild(h("p", { class: "eyebrow", style: "margin:12px 0 4px" }, "Findings")); fwith.forEach((f) => list.appendChild(h("a", { class: "pick", href: link("lab", "f:" + f.id), "aria-current": target === "f:" + f.id ? "true" : null, role: "listitem" }, h("span", null, trunc(f.title, 70), h("br"), h("small", null, (A.departments[f.dept] || {}).title)), sev(f.severity)))); }
    if (st.saved.length) { list.appendChild(h("p", { class: "eyebrow", style: "margin:12px 0 4px" }, "Saved here (" + st.saved.length + ")")); }
    const pane = h("div");
    const wide = window.innerWidth >= 1000;
    const cur = target && target.startsWith("m:") ? (missions.find((m) => "m:" + m.id === target) || {}).title : target && target.startsWith("f:") ? (A.findings.find((f) => "f:" + f.id === target) || {}).title : null;
    const picker = h("details", { class: "lab-pick", open: wide || !r.sub ? true : null }, h("summary", { class: "btn", style: "width:100%;justify-content:space-between" }, h("span", null, "Working on: ", h("b", null, trunc(cur || "choose", 44))), h("span", { class: "sub" }, (missions.length + fwith.length) + " options")), list);
    const lab = h("div", { class: "lab sec" }, picker, pane); wrap.appendChild(lab);
    let props = [], original = null, weak = [];
    if (target && target.startsWith("m:")) {
      const m = A.model.missions.find((x) => x.id === target.slice(2));
      if (m) { original = h("div", { class: "card orig" }, missionOriginal(m)); weak = A.findings.filter((f) => f.entities.includes(m.id));
        props = (A.lab[m.id] || []).slice(); weak.forEach((f) => (f.proposals || []).forEach((id) => { const p = A.proposals.find((x) => x.id === id); if (p) props.push(p); })); }
    } else if (target && target.startsWith("f:")) {
      const f = A.findings.find((x) => x.id === target.slice(2));
      if (f) { original = h("div", { class: "card orig" }, h("p", { class: "lock" }, "Existing design · read-only"), h("h3", null, f.title), h("p", null, f.summary), h("ul", { class: "evs" }, f.evidence.map((e) => h("li", null, lv(e.level), h("span", null, e.text, " ", srcLink(e)))))); weak = [f];
        props = (f.proposals || []).map((id) => A.proposals.find((x) => x.id === id)).filter(Boolean); }
    }
    if (!original) { pane.appendChild(h("p", { class: "sub" }, "Nothing to work on: no missions or findings with alternatives were found for this game.")); return wrap; }
    pane.appendChild(original);
    if (weak.length) pane.appendChild(h("section", { class: "sec" }, h("h2", null, "Identified weaknesses"), h("div", { class: "rows", style: "margin-top:10px" }, weak.map((f) => h("a", { class: "row", href: link(TAB_OF_DEPT[f.dept], f.id) }, h("span", { class: "t" }, f.title), sev(f.severity), h("span", { class: "d" }, f.summary))))));
    const cmpSel = new Set((store("dc.cmp." + A.game.id) || []).filter((id) => props.some((p) => p.id === id)));
    const altBox = h("div", { class: "props" });
    const compareBox = h("div", { class: "sec" });
    const drawCompare = () => {
      compareBox.innerHTML = "";
      const chosen = props.filter((p) => cmpSel.has(p.id)).map((p) => currentVersion(p, labState()));
      if (chosen.length < 2) { compareBox.appendChild(h("p", { class: "sub" }, "Select two or three alternatives to compare them side by side.")); return; }
      const rows = [["Proposal", (p) => p.proposal], ["Approach", (p) => p.label], ["Effort", (p) => p.complexity + " (" + p.complexity_why + ")"], ["Expected experience", (p) => p.experience],
        ["Trade-offs", (p) => p.tradeoffs.join(" ")], ["Measure", (p) => `${p.validation.metric}: ${p.validation.current} → ${p.validation.target}`], ["Validate by", (p) => p.validation.method], ["Priority", (p) => fmt(p.priority, 2)]];
      compareBox.appendChild(h("h2", null, "Compare"));
      compareBox.appendChild(h("div", { class: "tbl", style: "margin-top:10px" }, h("table", null, h("thead", null, h("tr", null, h("th", null, ""), chosen.map((p) => h("th", null, p.label + (p.version ? " v" + p.version : ""))))),
        h("tbody", null, rows.map(([k, f]) => h("tr", null, h("th", { scope: "row", style: "position:static" }, k), chosen.map((p) => h("td", null, f(p)))))))));
    };
    const groups = {};
    props.forEach((p) => {
      const cur = currentVersion(p, st);
      const saved = st.saved.some((x) => x.id === p.id);
      const cmpBtn = h("button", { class: "btn sm", "aria-pressed": cmpSel.has(p.id) ? "true" : "false", onclick: () => {
        if (cmpSel.has(p.id)) cmpSel.delete(p.id); else { if (cmpSel.size >= 3) { toast("Compare up to three at a time"); return; } cmpSel.add(p.id); }
        store("dc.cmp." + A.game.id, [...cmpSel]); cmpBtn.setAttribute("aria-pressed", cmpSel.has(p.id) ? "true" : "false"); drawCompare(); } }, "Compare");
      const card = propCard(cur, [cmpBtn,
        h("button", { class: "btn sm", "aria-pressed": saved ? "true" : "false", onclick: (e) => { const s2 = labState(); const i = s2.saved.findIndex((x) => x.id === p.id);
          if (i >= 0) { s2.saved.splice(i, 1); toast("Removed from saved"); } else { s2.saved.push({ id: p.id, at: new Date().toISOString(), title: cur.proposal }); toast("Saved in this browser"); }
          labSave(s2); e.target.setAttribute("aria-pressed", i >= 0 ? "false" : "true"); } }, saved ? "Saved" : "Save"),
        h("button", { class: "btn sm pri", onclick: () => openRefine(p) }, "Refine")]);
      if (cur.version) card.insertBefore(h("span", { class: "chip" }, "refined v" + cur.version), card.children[1]);
      if (p.id === focusPid) card.style.boxShadow = "0 0 0 2px var(--prop)";
      const gk = target.startsWith("m:") && p.finding ? p.finding : "_main";
      (groups[gk] = groups[gk] || []).push(card);
    });
    (groups._main || []).forEach((c) => altBox.appendChild(c));
    const sec = h("section", { class: "sec" }, h("div", { class: "sec-h" }, h("h2", null, "Alternatives"), h("span", { class: "sub" }, props.length + " proposals · expected outcomes are inferred until validated")), altBox);
    Object.keys(groups).filter((k) => k !== "_main").forEach((fid) => { const f = A.findings.find((x) => x.id === fid);
      sec.appendChild(h("details", { class: "card", style: "margin-top:12px", open: focusPid && focusPid.startsWith(fid + ":") ? true : null }, h("summary", { style: "cursor:pointer;font-weight:600;min-height:28px" }, "For weakness: " + (f ? f.title : fid) + " (3)"), h("div", { class: "props", style: "margin-top:10px" }, groups[fid]))); });
    pane.appendChild(sec);
    pane.appendChild(compareBox); drawCompare();
    if (st.saved.length) pane.appendChild(h("section", { class: "sec" }, h("h2", null, "Saved alternatives"), h("div", { class: "rows", style: "margin-top:10px" }, st.saved.map((x) => { const p = allProposals().find((q) => q.id === x.id); if (!p) return null; const cur = currentVersion(p, st);
      return h("div", { class: "row" }, h("span", { class: "t" }, cur.proposal), h("span", null, h("button", { class: "btn sm", onclick: () => downloadSpec(cur) }, "Spec")), h("span", { class: "d" }, (p.finding ? (A.findings.find((f) => f.id === p.finding) || {}).title : "Mission alternative") + " · saved " + x.at.slice(0, 10))); })),
      h("div", { class: "acts", style: "margin-top:10px;display:flex;gap:8px;flex-wrap:wrap" }, h("button", { class: "btn sm", onclick: exportSaved }, "Export all saved as JSON"))));
    return wrap;
  }

  // refinement: a deterministic, rule-based editor of proposals. It records each instruction, makes the changes it
  // understands, says plainly when it did not understand, and never touches the original proposal or the game.
  const INTENTS = [
    [/cheap|simpl|small|less work|smaller|minimal|quick|low effort|easier to build/i, "simpler"],
    [/bold|ambitious|bigger|more radical|go further|expand|scale up/i, "bolder"],
    [/keep|preserv|don'?t change|do not change|without changing|protect/i, "preserve"],
    [/mobile|phone|touch|thumb|iphone/i, "mobile"],
    [/story|character|narrative|dialog|emotion/i, "story"],
    [/test|validat|measur|playtest|metric|prove/i, "validate"],
    [/no combat|non-?violent|without violence|no violence/i, "nonviolent"],
    [/accessib|colou?r ?blind|deaf|subtitle|motor/i, "accessible"],
    [/new player|beginner|onboard|first time|casual/i, "newplayer"],
    [/expert|hardcore|mastery|speedrun|challenge/i, "expert"]];
  function refine(p, text) {
    const q = JSON.parse(JSON.stringify(p)); q.version = (p.version || 0) + 1; q.changes = q.changes.slice(); q.tradeoffs = q.tradeoffs.slice();
    const hits = INTENTS.filter(([rx]) => rx.test(text)).map(([, k]) => k); const did = [];
    const cast = (S.A.departments.storycraft.viz.cast || []).filter((c) => c.mentions > 0).map((c) => c.name);
    const named = cast.find((n) => new RegExp("\\b" + n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\b", "i").test(text));
    hits.forEach((k) => {
      if (k === "simpler") { const lv2 = { high: "medium", medium: "low", low: "low" }[q.complexity]; if (lv2 !== q.complexity) did.push(`lowered effort ${q.complexity} → ${lv2}`); q.complexity = lv2; if (q.changes.length > 2) { did.push(`kept the first ${2} of ${q.changes.length} changes`); q.changes = q.changes.slice(0, 2); } q.tradeoffs.push("Reduced scope: the effect will be smaller than the full proposal."); }
      if (k === "bolder") { const lv2 = { low: "medium", medium: "high", high: "high" }[q.complexity]; did.push(`raised ambition (effort ${q.complexity} → ${lv2})`); q.complexity = lv2; q.changes.push("Apply the same change to every mission or system with the same pattern, not only the examples named."); q.tradeoffs.push("Wider scope: more content to build and test."); }
      if (k === "preserve") { const what = (text.match(/(?:keep|preserve|don'?t change|do not change|protect)\s+(?:the\s+)?([^.,;]+)/i) || [])[1]; if (what) { q.changes.unshift(`Constraint: preserve ${what.trim()} exactly as it is.`); did.push(`added a constraint to preserve ${what.trim()}`); } }
      if (k === "mobile") { q.changes.push("On phone: every new action works with one thumb, needs no precision taps, and shows its objective in one line."); did.push("added a phone-first requirement"); }
      if (k === "story") { const who = named || cast[0]; q.changes.push(who ? `Carry the change through ${who}: give them one line that sets it up and one that pays it off.` : "Give the change a story reason in one line of the brief."); did.push(who ? `tied it to ${who}` : "added a story reason"); }
      if (k === "validate") { q.validation = Object.assign({}, q.validation, { method: q.validation.method + " Then: DESIGNCRAFT re-run (source verified), a PLAYCRAFT pass before/after (simulated), and a 5-player playtest with a think-aloud protocol (playtested)." }); did.push("expanded the validation plan to all three evidence levels"); }
      if (k === "nonviolent") { q.changes.push("Constraint: no combat or harm; resolve with movement, timing, tools or conversation."); did.push("added a non-violent constraint"); }
      if (k === "accessible") { q.changes.push("Accessibility: never signal only by colour or sound; offer a hold-to-confirm alternative for timed inputs."); did.push("added accessibility requirements"); }
      if (k === "newplayer") { q.changes.push("First encounter: introduce the change in a low-stakes context with one hint, before it matters."); did.push("added a first-encounter onboarding step"); }
      if (k === "expert") { q.changes.push("Mastery: add a par or best record for players who optimise it."); did.push("added a mastery target"); }
    });
    if (named && !hits.includes("story")) { q.changes.push(`Involve ${named} directly in the change.`); did.push(`involved ${named}`); }
    q.notes = (p.notes || []).concat([text]);
    const reply = did.length ? "Done: " + did.join("; ") + ". The original stays unchanged; this is version " + q.version + "." :
      "I recorded that as a designer note on version " + q.version + ", but this refiner is rule-based and did not find a change it knows how to make (it understands: simpler, bolder, keep/preserve X, mobile, story or a character's name, validate, non-violent, accessibility, new players, experts). For open-ended rewrites, use “Copy for Claude Code”.";
    return [q, reply];
  }
  function openRefine(p) {
    const st = labState(); const th = st.threads[p.id] || { versions: [], chat: [] };
    const chat = h("div", { class: "chat", "aria-live": "polite" });
    const draw = () => { chat.innerHTML = ""; if (!th.chat.length) chat.appendChild(h("div", { class: "msg dc" }, "Tell me how to change this proposal, e.g. “make it simpler”, “keep the radio dispatch”, “tie it to a character”, “make it work on a phone”.")); th.chat.forEach((m) => chat.appendChild(h("div", { class: "msg " + m.who }, m.text))); };
    const vers = h("div", { class: "vers" });
    const drawV = () => { vers.innerHTML = ""; vers.appendChild(h("span", { class: "chip" }, "original")); th.versions.forEach((v) => vers.appendChild(h("button", { class: "btn sm", onclick: () => downloadSpec(v) }, "v" + v.version + " spec"))); };
    const input = h("input", { type: "text", placeholder: "Refine this proposal…", "aria-label": "Refinement instruction", enterkeyhint: "send" });
    const send = (txt) => { const t = (txt || input.value).trim(); if (!t) return; const base = th.versions.length ? th.versions[th.versions.length - 1] : p; const [q, reply] = refine(base, t);
      S.dirty = true; th.versions.push(q); th.chat.push({ who: "me", text: t }, { who: "dc", text: reply }); const s2 = labState(); s2.threads[p.id] = th; labSave(s2); input.value = ""; draw(); drawV(); preview.innerHTML = ""; preview.appendChild(propCard(q)); };
    const preview = h("div", { class: "sec" }, propCard(th.versions.length ? th.versions[th.versions.length - 1] : p));
    const body = h("div", null, h("p", { class: "eyebrow" }, "Refine · " + p.label), h("h2", { id: "sheet-title" }, p.proposal),
      h("p", { class: "sub" }, "Every refinement is a new version. The original proposal and the original design are never changed."), vers, chat,
      h("div", { class: "suggest" }, ["Make it simpler", "Bolder", "Tie it to a character", "Make it work on a phone", "How do we validate it?"].map((t) => h("button", { class: "btn sm", onclick: () => send(t) }, t))),
      h("form", { class: "ask", onsubmit: (e) => { e.preventDefault(); send(); } }, input, h("button", { class: "btn pri", type: "submit" }, "Send")),
      h("div", { style: "display:flex;gap:8px;flex-wrap:wrap;margin-top:12px" },
        h("button", { class: "btn sm", onclick: () => copyClaude(th.versions.length ? th.versions[th.versions.length - 1] : p, th.chat) }, "Copy for Claude Code"),
        h("button", { class: "btn sm", onclick: () => { th.versions = []; th.chat = []; const s2 = labState(); delete s2.threads[p.id]; labSave(s2); draw(); drawV(); preview.innerHTML = ""; preview.appendChild(propCard(p)); } }, "Discard refinements")),
      preview);
    draw(); drawV(); openSheet(body); setTimeout(() => input.focus(), 50);
  }
  function specMd(p) {
    const A = S.A; const f = A.findings.find((x) => x.id === p.finding);
    const L = [`# Design spec: ${p.proposal}`, "", `Game: ${A.game.title} · proposal \`${p.id}\` (${p.label}${p.version ? ", refined v" + p.version : ""}) · DESIGNCRAFT assessment ${A.run_id || A.assessed_at}`, "",
      "## Existing design (preserved)", "", p.existing, "", "## Problem", "", p.problem, "", "## Why it matters to players", "", p.why, ""];
    if (f) { L.push("## Evidence", ""); f.evidence.forEach((e) => L.push(`- [${LV[e.level]}] ${e.text}${e.file ? " (`" + e.file + (e.line ? ":" + e.line : "") + "`)" : ""}`)); L.push(""); }
    L.push("## Change", ""); p.changes.forEach((c, i) => L.push(`${i + 1}. ${c}`));
    L.push("", "## Expected player experience (inferred until validated)", "", p.experience, "", "## Implementation", "", `Complexity: **${p.complexity}** (${p.complexity_why})`, "", "Trade-offs:", "");
    p.tradeoffs.forEach((t) => L.push("- " + t));
    L.push("", "## Validation", "", `- Metric: ${p.validation.metric}`, `- Current: ${p.validation.current}`, `- Target: ${p.validation.target}`, `- Method: ${p.validation.method}`, "",
      "## Acceptance", "", "- [ ] Implemented without removing the original until validated", "- [ ] DESIGNCRAFT re-run shows the metric at target", "- [ ] PLAYCRAFT pass recorded (simulated)", "- [ ] Playtest notes recorded (playtested)", "");
    if (p.notes && p.notes.length) { L.push("## Designer notes", ""); p.notes.forEach((n) => L.push("- " + n)); L.push(""); }
    L.push("DESIGNCRAFT makes no change to the game's source; implement only with the owner's approval.");
    return L.join("\n");
  }
  function download(name, text, type) { const b = new Blob([text], { type: type || "text/markdown" }); const a = h("a", { href: URL.createObjectURL(b), download: name }); document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
  function downloadSpec(p) { download(`designcraft-spec-${S.A.game.id}-${p.id.replace(/[^a-z0-9]+/gi, "-")}${p.version ? "-v" + p.version : ""}.md`, specMd(p)); toast("Spec downloaded"); }
  function exportSaved() { const st = labState(); const out = st.saved.map((x) => { const p = allProposals().find((q) => q.id === x.id); return p ? Object.assign({ saved_at: x.at }, currentVersion(p, st)) : null; }).filter(Boolean);
    download(`designcraft-saved-${S.A.game.id}.json`, JSON.stringify({ game: S.A.game, assessment: S.A.run_id, saved: out }, null, 1), "application/json"); }
  async function copyClaude(p, chat) {
    const txt = "Here is a DESIGNCRAFT design proposal for " + S.A.game.title + ". Please refine it with me as a game designer; do not change the game's code until I approve a final version.\n\n" + specMd(p) +
      (chat && chat.length ? "\n\n## Conversation so far\n" + chat.map((m) => (m.who === "me" ? "Designer: " : "DESIGNCRAFT: ") + m.text).join("\n") : "");
    try { await navigator.clipboard.writeText(txt); toast("Copied: paste it into Claude Code"); } catch (e) { download("designcraft-prompt.md", txt); toast("Clipboard blocked: downloaded instead"); }
  }

  // ------------------------------------------------------------------ REPORTS
  function mdToHtml(md) {
    const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const inl = (t) => esc(t).replace(/`([^`]+)`/g, "<code>$1</code>").replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>").replace(/\*([^*]+)\*/g, "<i>$1</i>").replace(/_([^_]+)_/g, "<i>$1</i>");
    const lines = md.split("\n"); const out = []; let i = 0;
    while (i < lines.length) {
      const l = lines[i];
      if (/^\|/.test(l)) { const rows = []; while (i < lines.length && /^\|/.test(lines[i])) { rows.push(lines[i]); i++; }
        const cells = (r) => r.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const head = cells(rows[0]); const body = rows.slice(2).map(cells);
        out.push('<div class="tbl"><table><thead><tr>' + head.map((c) => "<th>" + inl(c) + "</th>").join("") + "</tr></thead><tbody>" + body.map((r) => "<tr>" + r.map((c) => "<td>" + inl(c) + "</td>").join("") + "</tr>").join("") + "</tbody></table></div>"); continue; }
      if (/^#{1,3} /.test(l)) { const n = l.match(/^#+/)[0].length; out.push(`<h${n}>${inl(l.slice(n + 1))}</h${n}>`); i++; continue; }
      if (/^> /.test(l)) { out.push("<blockquote>" + inl(l.slice(2)) + "</blockquote>"); i++; continue; }
      if (/^- /.test(l)) { const it = []; while (i < lines.length && /^- /.test(lines[i])) { it.push("<li>" + inl(lines[i].slice(2)) + "</li>"); i++; } out.push("<ul>" + it.join("") + "</ul>"); continue; }
      if (/^---$/.test(l)) { out.push("<hr>"); i++; continue; }
      if (l.trim()) out.push("<p>" + inl(l) + "</p>");
      i++;
    }
    return out.join("");
  }
  function viewReports(r) {
    const A = S.A;
    const wrap = h("div", null, h("p", { class: "eyebrow" }, A.game.title), h("h1", null, "Reports"),
      h("p", { class: "lede" }, "The complete assessment: scores with evidence and confidence, priorities, every finding with its three alternatives, validation steps, history and the evidence inventory."));
    wrap.appendChild(h("div", { style: "display:flex;gap:8px;flex-wrap:wrap", class: "sec" },
      h("a", { class: "btn pri", href: "data/" + encodeURIComponent(A.game.id) + ".report.md", download: "designcraft-" + A.game.id + ".md" }, "Download report (.md)"),
      h("a", { class: "btn", href: "data/" + encodeURIComponent(A.game.id) + ".json", download: "designcraft-" + A.game.id + ".json" }, "Download assessment (.json)"),
      h("button", { class: "btn", onclick: () => window.print() }, "Print")));
    // history
    const H = A.history || [];
    const hs = h("section", { class: "sec", id: "history" }, h("h2", null, "History"), h("p", { class: "sub" }, "A change counts as measured only when the method is the same and the game's content changed. Runs are append-only."));
    hs.appendChild(h("div", { class: "tbl", style: "margin-top:10px" }, h("table", null, h("thead", null, h("tr", null, h("th", null, "Assessed"), h("th", { class: "num" }, "Score"), h("th", { class: "num" }, "Ceiling"), h("th", null, "Confidence"), h("th", null, "Method"), h("th", null, "Content"), h("th", { class: "num" }, "Findings"))),
      h("tbody", null, H.slice().reverse().map((x) => h("tr", null, h("td", null, x.assessed_at.slice(0, 16).replace("T", " ")), h("td", { class: "num" }, String(x.overall)), h("td", { class: "num" }, String(x.ceiling)), h("td", null, x.confidence), h("td", null, h("code", null, x.method)), h("td", null, h("code", null, x.content)), h("td", { class: "num" }, String(x.findings))))))));
    if (A.compare) hs.appendChild(h("p", { class: "note", style: "margin-top:10px" }, h("b", null, "Latest vs previous: "), `${A.compare.overall.from} → ${A.compare.overall.to} (${A.compare.kind}). ${A.compare.note} Resolved ${A.compare.resolved.length}, new ${A.compare.new.length}.`));
    wrap.appendChild(hs);
    // inventory
    const I = A.inspection;
    wrap.appendChild(h("section", { class: "sec" }, h("h2", null, "Evidence inventory"), h("div", { class: "kpis", style: "margin-top:12px" },
      [["files_read", "source & data files read"], ["docs", "design documents"], ["tests", "test files (listed, not run)"], ["screenshots", "screenshots / captures"]].map(([k, l]) => h("div", { class: "kpi" }, h("b", null, String(Array.isArray(I[k]) ? I[k].length : I[k])), h("span", null, l)))),
      I.docs.length ? h("details", { class: "card sec" }, h("summary", null, "Design documents read (" + I.docs.length + ")"), h("ul", { class: "limits", style: "margin-top:10px" }, I.docs.map((d) => h("li", null, h("code", null, d.file), " ", d.title)))) : null,
      I.tests.length ? h("details", { class: "card", style: "margin-top:10px" }, h("summary", null, "Tests in the project (" + I.tests.length + "), listed as existing evidence; DESIGNCRAFT does not run them"), h("ul", { class: "limits", style: "margin-top:10px" }, I.tests.map((t) => h("li", null, h("code", null, t.file), ` ${t.cases} cases`, t.names.length ? ": " + t.names.slice(0, 4).join("; ") : "")))) : null,
      I.screenshots.length ? h("details", { class: "card", style: "margin-top:10px" }, h("summary", null, "Visual evidence in the repository (" + I.screenshots.length + ")"), h("ul", { class: "limits", style: "margin-top:10px" }, I.screenshots.map((x) => h("li", null, srcLink({ file: x }))))) : null,
      Object.keys(I.unsupported || {}).length ? h("p", { class: "note", style: "margin-top:10px" }, h("b", null, "Unsupported formats: "), Object.entries(I.unsupported).map(([k, v]) => `${v} ${k}`).join(", ")) : null));
    // full report
    const rep = h("section", { class: "sec md" }, h("p", { class: "sub" }, "Loading the full report…"));
    wrap.appendChild(rep);
    fetch("data/" + encodeURIComponent(A.game.id) + ".report.md").then((x) => x.text()).then((t) => { rep.innerHTML = mdToHtml(t); }).catch(() => { rep.innerHTML = "<p class='sub'>The report file could not be loaded.</p>"; });
    wrap.appendChild(h("section", { class: "sec card" }, h("h3", null, "Evidence levels"), h("div", { class: "rows", style: "margin-top:10px" },
      [["source_verified", "Confirmed by reading the project's files."], ["simulated", "Observed in automated play (PLAYCRAFT) or a project's simulation."], ["playtested", "Observed while a person played (recorded playtest)."], ["inferred", "DESIGNCRAFT's reasoned design judgement."], ["untested", "Not evaluated: the data is missing."]]
        .map(([k, d]) => h("div", { class: "row" }, lv(k), h("span", { class: "d", style: "grid-column:auto" }, d))))));
    return wrap;
  }

  // ------------------------------------------------------------------ boot
  window.addEventListener("hashchange", render);
  $("#sheet-x").addEventListener("click", closeSheet);
  $("#sheet").addEventListener("click", (e) => { if (e.target.id === "sheet") closeSheet(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#sheet").hidden) closeSheet(); });
  render();
})();
