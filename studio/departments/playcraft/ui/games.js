// Game Quality History: renders data.json (written by forgecraft/ui_server.py --publish from the committed history).
// Static: no API, no network beyond this folder. Routes: #/ (portfolio), #/g/<game id> (one game).
(() => {
  const app = document.getElementById("app"), foot = document.getElementById("foot");
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const sha = (s) => (s ? esc(String(s).slice(0, 7)) : "—");
  const day = (s) => (s ? new Date(s).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—");
  const sign = (d) => (d == null ? "—" : d > 0 ? `+${d}` : `${d}`);
  const dcls = (d) => (d == null ? "flat" : d > 0 ? "up" : d < 0 ? "down" : "flat");
  let DATA = null;

  const VERDICT = {
    "genuine improvement": ["genuine", "Genuine improvement"], "genuine regression": ["attn", "Measured regression"], mixed: ["attn", "Mixed"],
    "measurement only (same commit)": ["measure", "Measurement only"], "code changed; not verified by measurement": ["code", "Code changed · unverified"],
    "no measured change (within noise)": ["measure", "Within noise"], "score moved without a measured criterion change (method or coverage)": ["measure", "Method / coverage"],
    "baseline only": ["base", "Baseline only"],
    "unconfirmed (PLAYCRAFT method changed): re-measure the baseline commit": ["code", "Unconfirmed · method changed"],
    "unconfirmed (noisy measurement): repeat the run": ["code", "Unconfirmed · noisy"],
  };
  const verdict = (v) => VERDICT[v] || ["measure", v || "—"];
  // a score move is coloured only when the history says it is real; otherwise it is grey and labelled as measurement
  const REAL = new Set(["genuine improvement", "genuine regression", "mixed"]);
  const deltaPill = (d, v, label) => (d == null ? "" : REAL.has(v) ? `<span class="delta ${dcls(d)}">${label === "verified" ? "verified " + sign(d) : sign(d) + " " + label}</span>`
    : `<span class="delta flat">${label === "verified" ? "verified " + sign(d) : sign(d) + " " + label}${d ? " · measurement" : ""}</span>`);
  const DEP = { "live-verified": ["gold", "Live · verified"], "deploy-reported": ["teal", "Deployed · reported"], merged: ["slate", "Merged"] };

  // ---------------------------------------------------------------- charts
  function trail(timeline, w = 320, h = 76) {
    const pts = timeline.filter((t) => t.overall != null && !t.is_remeasure);   // progression of the code; controls are on the game page
    if (!pts.length) return "";
    const vals = pts.flatMap((t) => [t.overall, t.verified]).filter((v) => v != null);
    const lo = Math.max(0, Math.min(...vals) - 6), hi = Math.min(100, Math.max(...vals) + 6);
    const x = (i) => (pts.length === 1 ? w / 2 : 10 + (i * (w - 20)) / (pts.length - 1));
    const y = (v) => h - 8 - ((v - lo) / (hi - lo || 1)) * (h - 16);
    const line = (k) => pts.map((t, i) => (t[k] == null ? null : `${x(i)},${y(t[k])}`)).filter(Boolean).join(" ");
    const dots = pts.map((t, i) => `<circle cx="${x(i)}" cy="${y(t.overall)}" r="${t.is_baseline ? 5 : 4}" fill="${t.is_baseline ? "#081a30" : "#fbefd5"}" stroke="#fbefd5" stroke-width="2"/>`).join("");
    return `<svg class="trail" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Overall score across ${pts.length} runs">
      <polyline points="${line("verified")}" fill="none" stroke="#f4c542" stroke-width="2" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>
      <polyline points="${line("overall")}" fill="none" stroke="#fbefd5" stroke-width="3" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>${dots}</svg>`;
  }

  function chart(G) {
    const tl = G.timeline, w = Math.round(Math.max(300, Math.min(760, app.clientWidth - 64))), h = w < 500 ? 200 : 230, L = 32, R = 26, T = 14, B = 36;
    const vals = tl.flatMap((t) => [t.overall, t.verified]).filter((v) => v != null);
    const lo = Math.max(0, Math.floor((Math.min(...vals) - 8) / 10) * 10), hi = Math.min(100, Math.ceil((Math.max(...vals) + 4) / 10) * 10);
    const x = (i) => (tl.length === 1 ? (L + w - R) / 2 : L + (i * (w - L - R)) / (tl.length - 1));
    const y = (v) => T + (1 - (v - lo) / (hi - lo || 1)) * (h - T - B);
    const base = tl.find((t) => t.is_baseline) || tl[0], band = G.noise?.band ?? 3;
    let g = `<rect x="${L}" y="${y(Math.min(hi, base.overall + band))}" width="${w - L - R}" height="${Math.max(1, y(Math.max(lo, base.overall - band)) - y(Math.min(hi, base.overall + band)))}" fill="rgba(138,155,179,.16)"/>`;
    for (let v = lo; v <= hi; v += 10) g += `<line x1="${L}" x2="${w - R}" y1="${y(v)}" y2="${y(v)}" stroke="#24497a" stroke-width="1"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end" fill="#6f88a8" font-size="11">${v}</text>`;
    const path = (k) => tl.map((t, i) => (t[k] == null || t.is_remeasure ? null : `${x(i)},${y(t[k])}`)).filter(Boolean).join(" ");   // controls are dots, not progress
    g += `<polyline points="${path("verified")}" fill="none" stroke="#f4c542" stroke-width="2.5" stroke-dasharray="6 5"/>`;
    g += `<polyline points="${path("overall")}" fill="none" stroke="#fbefd5" stroke-width="3.5" stroke-linejoin="round"/>`;
    let lastLabel = -1e9;
    tl.forEach((t, i) => {
      const same = i > 0 && tl[i - 1].commit && t.commit === tl[i - 1].commit;
      g += `<circle cx="${x(i)}" cy="${y(t.overall)}" r="${t.is_baseline ? 7 : 5.5}" fill="${t.is_baseline ? "#081a30" : t.is_remeasure ? "#6f88a8" : t.kind === "verify" ? "#2ad0b8" : "#fbefd5"}" stroke="#fbefd5" stroke-width="2.5"><title>${esc(t.kind)} · ${esc(day(t.at))} · ${esc(t.commit || "?")} · ${t.overall}</title></circle>`;
      const gap = (w - L - R) / Math.max(1, tl.length - 1), special = t.is_baseline || t.is_remeasure || t.kind === "verify";
      if (!(!same || special || gap > 70) || x(i) - lastLabel < 62) return;   // the dot is drawn; skip a label that would collide
      lastLabel = x(i);
      g += `<text x="${x(i)}" y="${h - 16}" text-anchor="middle" fill="${same ? "#6f88a8" : "#a8bcd4"}" font-size="11" font-family="ui-monospace, Menlo, monospace">${sha(t.commit)}</text>`;
      if (special || gap > 70) g += `<text x="${x(i)}" y="${h - 3}" text-anchor="middle" fill="#6f88a8" font-size="10">${t.is_baseline ? "baseline" : t.is_remeasure ? "control" : esc(t.kind)}</text>`;
    });
    return `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Score progression for ${esc(G.title)}">${g}</svg>
      <div class="legend"><span><i style="border-color:#fbefd5"></i>Overall</span><span><i style="border-color:#f4c542;border-top-style:dashed"></i>Verified-only</span>
      <span><i style="border-color:rgba(138,155,179,.5);border-top-width:8px"></i>Baseline ± measured noise (${band})</span><span>Grey commit = same as previous run · grey dot = re-measure of an older commit (control)</span></div>`;
  }

  // ---------------------------------------------------------------- portfolio
  function cardHTML(r, G) {
    const [vc, vt] = verdict(r.verdict), dep = r.deployment || {};
    const warn = [];
    if (dep.assessed_is_main === false) warn.push(`main moved to ${sha(dep.main_commit)} after the last assessment (${sha(dep.latest_assessed_commit)})`);
    if (r.open_defects) warn.push(`${r.open_defects} open defect${r.open_defects > 1 ? "s" : ""}`);
    const [dc, dt] = DEP[dep.level] || ["ghost", "Not deployed (no evidence)"];
    return `<a class="cart" href="#/g/${encodeURIComponent(r.id)}">
      <div class="top"><div><h3 class="t">${esc(r.title)}</h3><div class="chips">${(r.genres || []).map((g, i) => `<span class="chip${i ? "" : " gold"}">${esc(g.title)}</span>`).join("")}</div></div>
      <div class="score num">${r.overall ?? "—"}<small>${esc(r.confidence || "")} conf.</small></div></div>
      <span class="stamp ${vc}">${esc(vt)}</span>
      ${trail(G.timeline)}
      <div class="chips">${deltaPill(r.delta, r.verdict, "since baseline")}${deltaPill(r.verified_delta, r.verdict, "verified")}<span class="chip ${dc}">${esc(dt)}</span></div>
      <div class="meta"><div><b class="num">${r.runs}</b><span>runs</span></div><div><b class="num">${r.open_findings}</b><span>open</span></div><div><b class="num">${r.resolved_findings}</b><span>fixed</span></div></div>
      ${warn.map((w) => `<div class="warn">${w}</div>`).join("")}</a>`;
  }

  function portfolio() {
    const P = DATA.portfolio, A = DATA.answers || {};
    if (!P.length) { app.innerHTML = `<p class="lede">No games recorded yet. Run PLAYCRAFT on a game and export the history.</p>`; return; }
    const next = P[0];
    const q = (title, ans, items) => `<details><summary><span>${title}</span><span class="ans">${ans}</span></summary><div class="body">${items || "<p>Nothing recorded.</p>"}</div></details>`;
    const li = (xs, f) => (xs && xs.length ? `<ul>${xs.map(f).join("")}</ul>` : "");
    app.innerHTML = `
      <div class="eyebrow">PLAYCRAFT · ${P.length} games · ${P.reduce((n, r) => n + r.runs, 0)} recorded runs</div>
      <h1>How our games are changing</h1>
      <p class="lede">Every PLAYCRAFT run, kept. Each game is measured against its own first assessment and its own genre. A change only counts as an improvement if the code changed and the game proved it on screen.</p>
      <section class="next" aria-label="Needs attention next"><div class="eyebrow">Needs attention next</div><h2>${esc(next.title)}</h2>
        <ul>${next.reasons.slice(0, 5).map((r) => `<li>${esc(r)}</li>`).join("")}</ul><a class="go" href="#/g/${encodeURIComponent(next.id)}">Open its history</a></section>
      <h2>The games</h2>
      <div class="carts">${P.map((r) => cardHTML(r, DATA.games[r.id])).join("")}</div>
      <h2>Ask the portfolio</h2>
      <div class="qa">
        ${q("Which games improved most?", A.improved_most?.length ? esc(A.improved_most[0].game) : "none measured yet", li(A.improved_most, (x) => `<li><b>${esc(x.game)}</b>: ${x.improved_criteria} criteria improved at verified/observed level (verified-only ${sign(x.verified_delta)}, overall ${sign(x.delta)})</li>`))}
        ${q("Which games declined?", A.declined?.length ? A.declined.map((x) => esc(x.game)).join(", ") : "none measured", li(A.declined, (x) => `<li><b>${esc(x.game)}</b>: ${esc(x.verdict)}</li>`))}
        ${q("Which have not been assessed recently?", A.not_assessed_recently?.length ? `${A.not_assessed_recently.length}` : "none", li(A.not_assessed_recently, (x) => `<li><b>${esc(x.game)}</b>: ${esc(x.why)}${x.age_days != null ? ` (last run ${x.age_days} days ago)` : ""}</li>`))}
        ${q("Which defects are unresolved?", A.unresolved_defects?.length ? `${A.unresolved_defects.reduce((n, g) => n + g.defects.length, 0)}` : "none", li(A.unresolved_defects, (x) => `<li><b>${esc(x.game)}</b>: ${x.defects.map((d) => esc(d.title)).join("; ")}</li>`))}
        ${q("Which games have recurring regressions?", A.recurring_regressions?.length ? `${A.recurring_regressions.length}` : "none", li(A.recurring_regressions, (x) => `<li><b>${esc(x.game)}</b>: ${x.recurring.map((r) => `${esc(r.what)} ×${r.times}`).join("; ")}</li>`))}
        ${q("Which improvements produced measurable results?", A.measurable_improvements?.length ? `${A.measurable_improvements.length} pass${A.measurable_improvements.length > 1 ? "es" : ""}` : "none yet", li(A.measurable_improvements, (x) => `<li><b>${esc(x.game)}</b>${x.pr ? ` (<a href="${esc(x.pr)}">PR</a>)` : ""}: ${x.measurable.map(esc).join("; ")}${x.unmeasured.length ? `<br><small>Source-only, not measured: ${x.unmeasured.map(esc).join("; ")}</small>` : ""}</li>`))}
        ${q("What needs attention next?", esc(next.title), `<ol>${(A.needs_attention_next || []).map((x) => `<li><b>${esc(x.game)}</b>: ${x.reasons.map(esc).join("; ")}</li>`).join("")}</ol>`)}
      </div>`;
  }

  // ---------------------------------------------------------------- one game
  function game(id) {
    const G = DATA.games[id];
    if (!G) { app.innerHTML = `<a class="back" href="#/">← All games</a><p class="lede">No history for that game.</p>`; return; }
    const r = DATA.portfolio.find((x) => x.id === id) || {}, vb = G.vs_baseline, dep = G.deployment || {};
    const [vc, vt] = verdict(r.verdict);
    const base = G.timeline.find((t) => t.is_baseline) || G.timeline[0], last = G.timeline.find((t) => t.run === G.latest) || G.timeline[G.timeline.length - 1];
    const when = (rid) => { const t = G.timeline.find((x) => x.run === rid); return t ? day(t.at) : esc((rid || "").slice(0, 12)); };
    const lvl = (l) => `<span class="lv ${esc(l || "unknown")}">${esc((l || "?").replace("_", " "))}</span>`;
    const clsOf = (c) => (c.includes("unconfirmed") || c.startsWith("code") ? "code" : c.startsWith("improved") ? "improved" : c.startsWith("regressed") ? "regressed" : c === "measurement" || c === "method" ? "measurement" : "");
    const [dc, dt] = DEP[dep.level] || ["ghost", "No deployment evidence"];
    const realIn = (k) => { const cs = (vb?.changes || []).filter((c) => c.category === k); return cs.some((c) => (c.class || "").startsWith("improved")) ? "up" : cs.some((c) => (c.class || "").startsWith("regressed")) ? "down" : null; };
    const cats = vb ? Object.entries(vb.categories).filter(([, c]) => c.from != null || c.to != null) : Object.entries(last.categories || {}).map(([k, v]) => [k, { title: k, from: v, to: v, delta: 0 }]);
    const open = G.findings.filter((f) => f.state === "open"), fixed = G.findings.filter((f) => f.state === "resolved"), unm = G.findings.filter((f) => f.state === "not measured in latest");
    app.innerHTML = `
      <a class="back" href="#/">← All games</a>
      <div class="eyebrow" style="margin-top:16px">${esc(G.repo || G.id)} · ${G.runs} runs · ${(G.engine || []).map(esc).join(", ")}</div>
      <h1>${esc(G.title)}</h1>
      <div class="chips">${(G.genres || []).map((g, i) => `<span class="chip${i ? "" : " gold"}">${esc(g.title)}${g.share ? ` · ${Math.round(g.share * 100)}%` : ""}</span>`).join("")}</div>
      ${G.pitch ? `<p class="lede" style="margin-top:12px">${esc(G.pitch)}</p>` : ""}

      <section class="panel" aria-label="Code and deployment">
        <h3>Where the code is</h3>
        <div class="pipeline">
          <div><span>Baseline</span><b>${sha(base.commit)}</b><em>${esc(day(base.at))}</em></div>
          <div><span>Last assessed</span><b>${sha(dep.latest_assessed_commit)}</b><em>${esc(day(last.at))}</em></div>
          <div><span>Main</span><b>${sha(dep.main_commit)}</b><em style="color:${dep.assessed_is_main === false ? "var(--coral)" : "var(--mute)"}">${dep.main_commit ? (dep.assessed_is_main ? "assessed" : "not assessed yet") : "not observed"}</em></div>
          <div><span>Deployed</span><b>${sha(dep.commit)}</b><em><span class="chip ${dc}">${esc(dt)}</span></em></div>
        </div>
        ${dep.url ? `<p class="mono" style="margin:10px 0 0"><a href="${esc(dep.url)}">${esc(dep.url)}</a> · ${esc(day(dep.observed_at))}</p>` : ""}
      </section>

      <section class="panel" aria-label="Baseline versus latest">
        <h3>Baseline vs latest</h3>
        <div class="verdict"><div class="big num">${base.overall} → ${last.overall}</div><span class="stamp ${vc}" style="margin:0">${esc(vt)}</span></div>
        <p class="lede" style="margin-top:8px">Verified-only ${base.verified ?? "—"} → ${last.verified ?? "—"}. Measured noise on this game: ±${G.noise.band}${G.noise.measured ? ` (${G.noise.samples} repeat run${G.noise.samples > 1 ? "s" : ""} of one commit)` : " (default; no repeat runs yet)"}.</p>
        ${vb?.controlled ? `<p class="lede" style="margin-top:8px">Confirmed by a controlled comparison: the baseline commit was re-measured with the current PLAYCRAFT (${esc(day((G.timeline.find((t) => t.run === vb.controlled.from) || {}).at))}), so method changes are not counted.</p>` : ""}
        ${vb ? `<div class="counts" style="margin-top:10px">${vb.counts.improved ? `<span class="chip teal">${vb.counts.improved} improved (measured)</span>` : ""}${vb.counts.regressed ? `<span class="chip coral">${vb.counts.regressed} regressed (measured)</span>` : ""}${vb.counts.unconfirmed ? `<span class="chip ghost">${vb.counts.unconfirmed} unconfirmed (method or noise)</span>` : ""}${vb.counts.method ? `<span class="chip slate">${vb.counts.method} PLAYCRAFT method, not the game</span>` : ""}${vb.counts.unverified_code ? `<span class="chip ghost">${vb.counts.unverified_code} code change, unverified</span>` : ""}${vb.counts.measurement ? `<span class="chip slate">${vb.counts.measurement} measurement only</span>` : ""}${vb.counts.coverage ? `<span class="chip ghost">${vb.counts.coverage} coverage</span>` : ""}</div>` : ""}
      </section>

      <section class="panel"><h3>Score progression</h3>${chart(G)}</section>

      <div class="two">
        <section class="panel"><h3>Category by category</h3><div class="cats">${cats.map(([k, c]) => `
          <div class="cat"><div class="row1"><span>${esc(c.title || k)}</span><span class="num">${c.from ?? "—"} → <b>${c.to ?? "—"}</b> <span class="delta ${realIn(k) && c.delta ? dcls(c.delta) : "flat"}" style="padding:1px 6px">${sign(c.delta)}</span></span></div>
          ${c.delta && !realIn(k) ? `<div class="note">moved without a measured change (method, coverage or source-only)</div>` : ""}
          <div class="track"><div class="base" style="width:${c.from ?? 0}%"></div><div class="now ${realIn(k) && c.delta ? dcls(c.delta) : ""}" style="width:${c.to ?? 0}%"></div>${c.verified_to != null ? `<div class="ver" style="left:calc(${c.verified_to}% - 2px)" title="verified-only ${c.verified_to}"></div>` : ""}</div></div>`).join("")}</div>
          <div class="legend"><span><i style="border-color:rgba(168,188,212,.5);border-top-width:8px"></i>Baseline</span><span><i style="border-color:#fbefd5"></i>Latest</span><span><i style="border-color:#f4c542;width:4px;border-top-width:12px"></i>Verified-only</span></div></section>
        <section class="panel"><h3>What changed, and why it counts (or not)</h3>
          ${vb ? `<ul class="list">${vb.changes.slice(0, 14).map((c) => `<li><div class="k"><b>${esc(c.title)}</b><span class="cls ${clsOf(c.class || "")}">${esc(c.class)}</span></div><p>${esc(c.from.status || "—")} ${lvl(c.from.level)} → ${esc(c.to.status || "—")} ${lvl(c.to.level)}${c.why ? ` · ${esc(c.why)}` : ""}</p></li>`).join("") || "<li>No criterion changed.</li>"}</ul>` : `<p class="lede">Only the baseline so far.</p>`}</section>
      </div>

      <section class="panel"><h3>Findings across runs</h3>
        <div class="tabs2" role="group" aria-label="Show findings"><button aria-pressed="true" aria-controls="flist" class="on" data-f="open">Open ${open.length}</button><button aria-pressed="false" aria-controls="flist" data-f="fixed">Fixed ${fixed.length}</button>${unm.length ? `<button aria-pressed="false" aria-controls="flist" data-f="unm">Not measured ${unm.length}</button>` : ""}</div>
        <ul class="list" id="flist"></ul></section>

      <div class="two">
        <section class="panel"><h3>Improvement passes</h3>${G.passes.length ? `<ul class="list">${G.passes.map((p) => `<li><div class="k"><b>${esc(day(p.at))} · ${sha(p.commit)}</b>${p.pr ? `<a href="${esc(p.pr)}">PR</a>` : ""}</div>
          <p>${p.changes.map((c) => esc(c.title)).join(" · ")}</p><p><b style="color:var(--teal)">Measured:</b> ${p.measurable.map(esc).join("; ") || "none"}</p>${p.unmeasured.length ? `<p>Source only: ${p.unmeasured.map(esc).join("; ")}</p>` : ""}
          <p>Regressions: ${p.regressions.length ? p.regressions.map(esc).join("; ") : "none"}${p.not_reproduced.length ? ` · not reproduced (noise): ${p.not_reproduced.map(esc).join("; ")}` : ""} · guardrails ${p.guardrails_ok ? "clean" : p.guardrails_ok === false ? "FAILED" : "—"}</p></li>`).join("")}</ul>` : `<p class="lede">No improvement pass recorded yet.</p>`}</section>
        <section class="panel"><h3>Regression history</h3>${G.regressions.length ? `<ul class="list">${G.regressions.map((x) => `<li><div class="k"><b>${esc(x.what)}</b><span class="cls ${x.confirmed === false ? "measurement" : "regressed"}">${esc(x.kind)}</span></div><p>commit ${sha(x.commit)} · ${when(x.run)}</p></li>`).join("")}</ul>` : `<p class="lede">None recorded.</p>`}</section>
      </div>

      <section class="panel"><h3>Runs and provenance</h3><div class="scroll"><table class="prov"><thead><tr><th>Assessed</th><th>Kind</th><th>Commit</th><th>Overall</th><th>Verified</th><th>Evidence v/o/i/n</th><th>Method</th></tr></thead><tbody>
        ${G.timeline.map((t, i) => { const pv = G.provenance[i] || {}; const e = t.evidence || {}; return `<tr><td>${esc(day(t.at))}${t.is_baseline ? ` <span class="chip gold">baseline</span>` : t.is_remeasure ? ` <span class="chip">re-measure (control)</span>` : ""}</td><td>${esc(t.kind)}</td><td class="mono" title="${esc(pv.commit_source || "")}">${sha(t.commit)}</td><td class="n">${t.overall}</td><td class="n">${t.verified ?? "—"}</td><td class="n">${e.verified || 0}/${e.observed || 0}/${e.inferred || 0}/${e.not_tested || 0}</td><td class="mono">${esc(t.method)}</td></tr>`; }).join("")}
      </tbody></table></div><p class="lede" style="font-size:13px;margin-top:8px">Every run keeps its full PLAYCRAFT card (SHA-256 recorded). The baseline is pinned and never overwritten.</p></section>`;
    const show = (k) => {
      const xs = k === "open" ? open : k === "fixed" ? fixed : unm;
      document.getElementById("flist").innerHTML = xs.map((f) => `<li><div class="k"><b>${esc(f.title)}</b><span>${f.type === "defect" ? `<span class="cls regressed">defect</span> ` : ""}${lvl(f.state === "resolved" ? f.resolved_level : f.level)}</span></div>
        <p>${f.state === "resolved" ? `fixed in the run of ${when(f.resolved_in)}${f.resolved_by && f.resolved_by !== "change" ? " · by measurement on an unchanged commit, not credited" : ""}` : `seen in ${f.occurrences} run${f.occurrences > 1 ? "s" : ""} since ${when(f.first_seen)}`}${f.reopened ? ` · reopened ${f.reopened}×` : ""}${f.evidence ? ` · ${esc(String(f.evidence).slice(0, 140))}` : ""}</p></li>`).join("") || "<li>None.</li>";
      document.querySelectorAll("[data-f]").forEach((b) => { b.classList.toggle("on", b.dataset.f === k); b.setAttribute("aria-pressed", String(b.dataset.f === k)); });
    };
    document.querySelectorAll("[data-f]").forEach((b) => (b.onclick = () => show(b.dataset.f)));
    show("open");
  }

  function route() {
    const h = location.hash.replace(/^#\/?/, "");
    if (h.startsWith("g/")) game(decodeURIComponent(h.slice(2))); else portfolio();
    window.scrollTo(0, 0);
  }
  fetch("data.json", { cache: "no-cache" }).then((r) => r.json()).then((d) => {
    DATA = d;
    foot.innerHTML = `<p>Snapshot of the committed history (${esc(d.source?.archive || "")}), built ${esc(day(d.generated))}. Static page: it shows recorded runs, it does not measure anything.</p>${(d.rules || []).map((r) => `<p>${esc(r)}</p>`).join("")}`;
    route();
  }).catch((e) => { app.innerHTML = `<p class="lede">Could not load the history: ${esc(e)}</p>`; });
  window.addEventListener("hashchange", route);
})();
