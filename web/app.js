"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const words = (s) => String(s ?? "").replace(/_/g, " ");
const MAX_BYTES = 25 * 1024 * 1024;
let cur = null;      // current analysis
let recent = [];
let busy = false;
let supportFilter = "all";

// How each rating is decided (docs/ARCHITECTURE.md, claims.py). Shown next to the ledger.
const SUPPORT_HELP = {
  strong: "The claim's figures reappear in a results passage and the passage is clearly about the same thing.",
  moderate: "Figures match a passage, or a claim without figures has a clearly related passage.",
  weak: "Only some wording overlaps. Treat as a pointer, not as support.",
  none: "No passage passed the relevance test, so none is shown. The paper may still contain evidence in other words or in a figure.",
};
const SUPPORT_LABEL = {strong: "strong", moderate: "moderate", weak: "weak", none: "no evidence found"};
const REJECT_HELP = {
  below_relevance_threshold: "too little wording in common with the claim",
  claim_zone_without_new_data: "abstract, introduction or conclusion text that only restates the claim",
  table_row_without_matching_value: "table rows without the claimed value",
  table_row_for_another_quantity: "table rows whose matching number measures something else",
  caption_label_only: "captions with no content beyond their label",
  fragment: "fragments too short to be evidence",
  boilerplate: "boilerplate (acknowledgements, licence, references)",
  symbols_or_numbers: "mostly symbols or numbers (equations, axis text)",
  restatement: "restatements of the claim without new data",
};

async function api(path, opts) {
  let r;
  try { r = await fetch(path, opts); }
  catch (_) { throw new Error("The PaperLens server is not reachable. Is 'python -m paperlens serve' still running?"); }
  if (!r.ok) {
    let msg = r.statusText || ("HTTP " + r.status);
    try { const d = (await r.json()).detail; if (typeof d === "string") msg = d; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}
function status(msg, kind) {
  const el = $("status");
  el.className = kind || "";
  el.innerHTML = msg ? (kind === "busy" ? '<span class="spin"></span>' : "") + esc(msg) : "";
}
function setBusy(on) {
  busy = on;
  $("demo").disabled = on;
  $("drop").classList.toggle("disabled", on);
}

async function upload(file) {
  if (!file || busy) return;
  if (!/\.pdf$/i.test(file.name) && file.type !== "application/pdf") return status(`"${file.name}" is not a PDF file. Choose a file ending in .pdf.`, "bad");
  if (file.size > MAX_BYTES) return status(`"${file.name}" is larger than the 25 MB limit.`, "bad");
  setBusy(true);
  status(`Analysing ${file.name} … long papers can take several seconds.`, "busy");
  const fd = new FormData(); fd.append("file", file);
  try { show(await api("/api/analyze", {method: "POST", body: fd})); status(`Analysed ${file.name}.`, "ok"); }
  catch (e) { status(`Could not analyse ${file.name}: ${e.message}`, "bad"); }
  finally { setBusy(false); $("file").value = ""; }
}
async function loadRecent() {
  try { recent = await api("/api/analyses"); } catch (_) { recent = []; }
  $("recent").innerHTML = recent.length ? '<div class="recent"><span class="muted small">Analysed earlier:</span> ' +
    recent.slice(0, 8).map((r) => `<a href="#" data-id="${esc(r.id)}" title="${esc(r.title)}" class="${cur && cur.id === r.id ? "cur" : ""}">${esc(r.name || r.title)}</a>`).join("") + "</div>" : "";
  $("recent").querySelectorAll("a").forEach((a) => a.onclick = async (ev) => {
    ev.preventDefault();
    if (busy) return;
    setBusy(true); status("Opening …", "busy");
    try { show(await api("/api/analyses/" + a.dataset.id)); status(""); }
    catch (e) { status(e.message, "bad"); }
    finally { setBusy(false); }
  });
}

function show(a) {
  cur = a; supportFilter = "all";
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  $("title").textContent = a.document.title;
  $("meta").textContent = `${a.document.source_name} · ${a.document.n_pages} pages · ${a.document.n_sentences} sentences read`;
  $("dl-md").href = `/api/analyses/${a.id}/report.md`; $("dl-json").href = `/api/analyses/${a.id}/report.json`; $("dl-html").href = `/api/analyses/${a.id}/report.html`;
  $("warnings").innerHTML = a.document.warnings.map((w) => `<div class="warn"><strong>Parsing warning.</strong> ${esc(w)}</div>`).join("");
  const st = a.ledger_stats.support, r = a.reproducibility, high = a.gaps.filter((g) => g.severity === "high").length;
  const assessed = r.band !== "not assessed";
  $("tiles").innerHTML =
    tile(a.ledger_stats.n_claims, "claims found", `${st.strong} strong · ${st.moderate} moderate · ${st.weak} weak · ${st.none} without evidence`, "ledger") +
    tile(assessed ? r.score : "n/a", assessed ? "reporting checklist / 100" : "checklist not assessed", assessed ? `${r.items.filter((i) => i.status === "missing").length} of ${r.items.length} items not reported` : "too little text was extracted", "repro") +
    tile(a.gaps.length, "candidate evidence gaps", `${high} high severity`, "gaps");
  document.querySelectorAll("#tiles .tile").forEach((t) => t.onclick = () => tab(t.dataset.tab));
  renderSummary(a); renderLedger(a); renderRepro(a); renderGaps(a); renderCompareTab();
  tab("summary");
  loadRecent();
}
function tile(big, label, sub, t) { return `<button class="tile" data-tab="${t}"><div class="big">${esc(big)}</div><div>${esc(label)}</div><div class="muted small">${esc(sub)}</div></button>`; }
function tab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.hidden = t.id !== "tab-" + name);
}
document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => tab(b.dataset.tab));

function renderSummary(a) {
  const s = a.summary; let h = "<h3>Summary in the paper's own words</h3>";
  h += (s.tldr || []).map((t) => `<p>${esc(t.text)} <span class="cite">p.${t.page}</span></p>`).join("") || "<p class='empty'>No summary could be built: no abstract or body text was recognised in this PDF.</p>";
  for (const [k, items] of Object.entries(s.facets || {})) {
    if (!items.length) continue;
    h += `<div class="facet"><h4>${esc(k)}</h4><ul>` +
      items.map((i) => `<li>${esc(i.text)} <span class="cite">p.${i.page}, ${esc(i.section)}</span></li>`).join("") + "</ul></div>";
  }
  if (a.datasets.length || a.metrics.length) h += `<p class="muted small">Datasets recognised: ${esc(a.datasets.join(", ") || "none")} · Metrics recognised: ${esc(a.metrics.join(", ") || "none")}</p>`;
  h += `<p class="cite">${esc(s.method || "")}. Every sentence is quoted verbatim from the paper; nothing is paraphrased or generated.</p>`;
  $("tab-summary").innerHTML = h;
}

function pill(k, label) { return `<span class="pill ${esc(k)}">${esc(label || words(k))}</span>`; }

function renderLedger(a) {
  const st = a.ledger_stats.support;
  let h = `<h3>Research Evidence Ledger</h3>`;
  if (!a.ledger.length) {
    $("ledger").innerHTML = h + `<p class="empty">No claims were extracted. Claims are taken from the abstract, introduction, discussion and conclusion; see the warnings above if the PDF could not be read.</p>`;
    $("viewer").innerHTML = ""; return;
  }
  h += `<div class="filters">` + ["all", "strong", "moderate", "weak", "none"].map((k) =>
    `<button class="chip ${supportFilter === k ? "on" : ""}" data-k="${k}">${k === "all" ? "All " + a.ledger_stats.n_claims : esc(SUPPORT_LABEL[k]) + " " + st[k]}</button>`).join("") + `</div>`;
  const rows = a.ledger.filter((c) => supportFilter === "all" || c.support === supportFilter);
  h += "<table><thead><tr><th>ID</th><th>Claim (as written in the paper)</th><th>Page</th><th>Support</th></tr></thead><tbody>";
  for (const c of rows) {
    h += `<tr class="claim" data-id="${esc(c.id)}" tabindex="0"><td>${esc(c.id)}</td><td>${esc(c.text)}<div class="cite">${esc(c.claim_type)}${c.hedged ? " · hedged" : ""}</div></td><td>${c.page}</td><td>${pill(c.support, SUPPORT_LABEL[c.support])}</td></tr>`;
  }
  h += "</tbody></table>";
  if (!rows.length) h += `<p class="empty">No claim has this rating.</p>`;
  h += `<details class="legend"><summary>How the ratings are decided</summary><dl>` +
    Object.keys(SUPPORT_HELP).map((k) => `<dt>${pill(k, SUPPORT_LABEL[k])}</dt><dd>${esc(SUPPORT_HELP[k])}</dd>`).join("") +
    `</dl><p class="small muted">Matching is lexical and numeric, not a judgement of the argument. A passage that shares numbers but contradicts the claim can still be rated strong, so read the quote.</p></details>`;
  $("ledger").innerHTML = h;
  $("ledger").querySelectorAll("tr.claim").forEach((tr) => {
    tr.onclick = () => openClaim(tr.dataset.id);
    tr.onkeydown = (e) => { if (e.key === "Enter") openClaim(tr.dataset.id); };
  });
  $("ledger").querySelectorAll(".chip").forEach((b) => b.onclick = () => { supportFilter = b.dataset.k; renderLedger(cur); });
  if (!$("viewer").dataset.claim) $("viewer").innerHTML = `<p class="empty">Select a claim to see its evidence passages, why each was chosen, and the source page with claim and evidence highlighted.</p>`;
}
function openClaim(id) {
  const c = cur.ledger.find((x) => x.id === id); if (!c) return;
  document.querySelectorAll("tr.claim").forEach((t) => t.classList.toggle("sel", t.dataset.id === id));
  const ev = c.evidence;
  let h = `<h3>${esc(c.id)} ${pill(c.support, SUPPORT_LABEL[c.support])}</h3><blockquote class="claimq">${esc(c.text)}<div class="cite">Claim on p.${c.page}, ${esc(c.section)} · ${esc(c.claim_type)}${c.hedged ? " · hedged wording" : ""}</div></blockquote>`;
  h += `<p class="small muted">${esc(SUPPORT_HELP[c.support])}</p>`;
  if (!ev.length) {
    h += `<div class="warn"><strong>${esc(c.evidence_note || "No supporting evidence found")}.</strong> PaperLens does not show a passage it cannot justify.</div>`;
    const rej = Object.entries(c.rejected || {}).sort((x, y) => y[1] - x[1]);
    if (rej.length) h += `<p class="small"><strong>What was looked at and why it was not returned</strong> (top-ranked candidates):</p><ul class="small">` +
      rej.map(([k, n]) => `<li>${n} × ${esc(REJECT_HELP[k] || words(k))}</li>`).join("") + "</ul>";
  }
  const cov = c.quantity_coverage;
  if (ev.length && cov && cov.claimed && cov.claimed.length) {
    h += `<p class="small ${cov.missing.length ? "partial" : ""}"><strong>${cov.found.length} of ${cov.claimed.length} claimed figures</strong> reappear in the passages below` +
      (cov.missing.length ? `; <strong>not found: ${esc(cov.missing.join(", "))}</strong>` : "") + `.</p>`;
  }
  ev.forEach((e, i) => {
    const why = [];
    if (e.shared_numbers.length) why.push(`shares the figure${e.shared_numbers.length > 1 ? "s" : ""} <strong>${esc(e.shared_numbers.join(", "))}</strong> with the claim`);
    if (e.shared_terms && e.shared_terms.length) why.push(`shares the terms <em>${esc(e.shared_terms.join(", "))}</em>`);
    if (!why.length) why.push("overall wording overlap only");
    h += `<div class="ev"><div><strong>Evidence ${i + 1}</strong> <span class="cite">p.${e.page} · ${esc(e.section)}</span></div><blockquote>${esc(e.quote)}</blockquote>` +
      `<div class="small muted"><strong>Why this passage:</strong> ${why.join("; ")}. Match score ${e.score} (wording relevance ${e.lexical}).</div></div>`;
  });
  const pages = [...new Set([c.page, ...ev.map((e) => e.page)])];
  h += `<h4>Source page${pages.length > 1 ? "s" : ""}</h4><p class="small muted">Highlighted: the claim and its evidence. Click a page to open it full size. If a passage is not highlighted, the page number is still its citation: its wording could not be located automatically on the page.</p><div class="pages">${pages.map((p) => {
    const ids = [c.sentence_id, ...ev.filter((e) => e.page === p).map((e) => e.sentence_id)].join(",");
    const src = `/api/analyses/${cur.id}/page/${p}.png?highlight=${ids}`;
    return `<figure><figcaption class="cite">Page ${p} of ${cur.document.n_pages}</figcaption><a href="${src}&zoom=2.4" target="_blank" rel="noopener"><img loading="lazy" alt="Page ${p} with highlights" src="${src}"></a></figure>`;
  }).join("")}</div>`;
  const v = $("viewer");
  v.dataset.claim = id; v.innerHTML = h; v.scrollTop = 0;
  v.querySelectorAll("img").forEach((img) => img.onerror = () => { img.closest("figure").innerHTML = `<p class="empty">The image of this page could not be loaded.</p>`; });
}

function renderRepro(a) {
  const r = a.reproducibility, assessed = r.band !== "not assessed";
  const missing = r.items.filter((i) => i.status === "missing"), na = r.items.filter((i) => i.status === "not_applicable");
  let h = `<h3>Reproducibility reporting checklist</h3><div class="warn"><strong>What this score means.</strong> ${esc(r.disclaimer)} A high score is not proof that the study reproduces, and a low score is not proof that it does not.</div>`;
  h += `<div class="row"><div class="scorebox"><div class="score">${assessed ? r.score : "n/a"}</div><div class="muted">${assessed ? "/ 100 · " + esc(r.band) + " coverage" : "not assessed"}</div></div><div style="flex:1;min-width:240px">`;
  for (const [k, v] of Object.entries(r.categories)) h += `<div class="cat"><span>${esc(k)}</span> <span class="muted small">${v.score}</span><div class="bar"><i style="width:${Math.max(0, Math.min(100, v.score))}%"></i></div></div>`;
  h += `</div></div>`;
  if (assessed) h += `<p><strong>Not reported (${missing.length}):</strong> ${missing.length ? esc(missing.map((i) => i.label).join("; ")) : "none of the checklist items is missing"}.` +
    (na.length ? ` <span class="muted">Not applicable to this paper and left out of the score: ${esc(na.map((i) => i.label).join("; "))}.</span>` : "") + `</p>`;
  h += "<table><thead><tr><th>Item</th><th>Status</th><th>Weight</th><th>Quote that earned the credit, or what to add</th></tr></thead><tbody>";
  for (const i of r.items) {
    const ev = i.evidence[0];
    h += `<tr><td>${esc(i.label)}<div class="cite">${esc(i.category)}</div></td><td>${pill(i.status)}</td><td>${i.weight}</td><td>` +
      (ev ? `<span class="cite">p.${ev.page}</span> ${esc(ev.quote)}` : `<span class="muted">${esc(i.advice)}</span>`) + "</td></tr>";
  }
  h += `</tbody></table><p class="cite">Score = ${esc(r.formula)}. Items are found by fixed text patterns, so a quote can be a false match: read it before relying on the credit.</p>`;
  $("tab-repro").innerHTML = h;
}

function renderGaps(a) {
  let h = `<h3>${a.gaps.length} candidate evidence gap${a.gaps.length === 1 ? "" : "s"}</h3><p class="muted small">Rule-based flags for a reviewer to check, not accusations. "No supporting passage found" means the linker found none, not that the paper has none.</p>`;
  if (!a.gaps.length) { $("tab-gaps").innerHTML = h + `<p class="empty">No evidence gaps were flagged by the current rules.</p>`; return; }
  h += `<table><thead><tr><th>Severity</th><th>Type</th><th>Detail</th><th>Page</th></tr></thead><tbody>`;
  for (const g of a.gaps) {
    h += `<tr><td>${pill(g.severity)}</td><td>${esc(words(g.kind))}</td><td>${esc(g.message)}` +
      (g.quote ? `<blockquote>${esc(g.quote)}</blockquote>` : "") +
      (g.claim_id ? `<a href="#" class="small jump" data-id="${esc(g.claim_id)}">Open claim ${esc(g.claim_id)} in the ledger</a>` : "") + `</td><td>${g.page ?? "—"}</td></tr>`;
  }
  $("tab-gaps").innerHTML = h + "</tbody></table>";
  $("tab-gaps").querySelectorAll("a.jump").forEach((l) => l.onclick = (ev) => {
    ev.preventDefault(); supportFilter = "all"; renderLedger(cur); tab("ledger"); openClaim(l.dataset.id);
    const tr = document.querySelector(`tr.claim[data-id="${l.dataset.id}"]`); if (tr) tr.scrollIntoView({block: "center"});
  });
}

async function renderCompareTab() {
  const mine = cur.id;
  try { recent = await api("/api/analyses"); } catch (_) {}
  if (!cur || cur.id !== mine) return;
  const others = recent.filter((r) => r.id !== cur.id);
  let h = `<h3>Compare with another analysed paper</h3>`;
  if (!others.length) {
    $("tab-compare").innerHTML = h + `<p class="empty">No second paper has been analysed yet. Upload another PDF with the box at the top of the page, then return to this tab.</p>`;
    return;
  }
  h += `<p class="muted small">Paper A is the paper shown above. Choose paper B from the papers analysed earlier.</p>
    <p><select id="cmp-b" aria-label="Paper B">${others.map((r) => `<option value="${esc(r.id)}">${esc(r.name || r.title)}</option>`).join("")}</select> <button id="cmp-go">Compare</button> <span id="cmp-status" class="small"></span></p><div id="cmp-out"></div>`;
  $("tab-compare").innerHTML = h;
  $("cmp-go").onclick = async () => {
    const b = $("cmp-b").value, btn = $("cmp-go");
    btn.disabled = true; $("cmp-status").className = "small muted"; $("cmp-status").innerHTML = '<span class="spin"></span>Comparing …';
    try { renderCompare(await api("/api/compare", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({a: cur.id, b})})); $("cmp-status").textContent = ""; }
    catch (e) { $("cmp-status").className = "small bad"; $("cmp-status").textContent = "Comparison failed: " + e.message; }
    finally { btn.disabled = false; }
  };
}
function renderCompare(c) {
  const col = (p, n) => `<div class="cmpcol"><h4>Paper ${n}</h4><div>${esc(p.title)}</div><div class="muted small">${p.pages} pages · ${p.n_claims} claims</div>
    <div>Reporting checklist <strong>${p.repro_score}</strong> / 100</div><div>Evidence score <strong>${p.evidence_score ?? "n/a"}</strong></div><div>High-severity gaps <strong>${p.high_gaps}</strong></div></div>`;
  const list = (x) => esc(x.join(", ") || "none");
  let h = `<div class="grid2">${col(c.a, "A")}${col(c.b, "B")}</div><h4>Reading</h4><ul>${c.verdict.map((v) => `<li>${esc(v)}</li>`).join("")}</ul>`;
  h += `<p class="muted small">Datasets shared: ${list(c.datasets.shared)} · only A: ${list(c.datasets.only_a)} · only B: ${list(c.datasets.only_b)}<br>Metrics shared: ${list(c.metrics.shared)} · only A: ${list(c.metrics.only_a)} · only B: ${list(c.metrics.only_b)}</p>`;
  h += `<h4>Similar claims</h4>` + (c.aligned_claims.length ? "<table><thead><tr><th>Paper A</th><th>Paper B</th><th>Note</th></tr></thead><tbody>" +
    c.aligned_claims.map((x) => `<tr><td>${esc(x.a.text)} ${pill(x.a.support, SUPPORT_LABEL[x.a.support])}</td><td>${esc(x.b.text)} ${pill(x.b.support, SUPPORT_LABEL[x.b.support])}</td><td>${esc(x.note)}</td></tr>`).join("") + "</tbody></table>" : "<p class='empty'>No pair of claims is similar enough in wording to be aligned.</p>");
  const diff = c.rubric.filter((r) => r.differs);
  h += `<h4>Checklist items that differ</h4>` + (diff.length ? `<table><thead><tr><th>Item</th><th>A</th><th>B</th></tr></thead><tbody>` +
    diff.map((r) => `<tr><td>${esc(r.label)}</td><td>${pill(r.a)}</td><td>${pill(r.b)}</td></tr>`).join("") + "</tbody></table>" : "<p class='empty'>Both papers have the same status on every checklist item.</p>");
  h += `<p class="cite">${esc(c.caveat)} The evidence score averages the support ratings of result and comparison claims (strong 1, moderate 0.6, weak 0.25, none 0).</p>`;
  $("cmp-out").innerHTML = h;
}

$("file").onchange = (e) => upload(e.target.files[0]);
const drop = $("drop");
["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => upload(e.dataTransfer.files[0]));
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); } });
// a page dropped outside the box would otherwise be opened by the browser and replace the app
["dragover", "drop"].forEach((ev) => window.addEventListener(ev, (e) => e.preventDefault()));
$("demo").onclick = async () => {
  if (busy) return;
  setBusy(true); status("Generating and analysing two synthetic demo papers …", "busy");
  try {
    const d = await api("/api/demo", {method: "POST"});
    show(await api("/api/analyses/" + d.a));
    status("Synthetic demo loaded (generated papers, not real studies). Open the Compare tab to contrast it with demo-overclaiming.pdf.", "ok");
  } catch (e) { status("Could not load the demo: " + e.message, "bad"); }
  finally { setBusy(false); }
};
api("/api/health").then((h) => { if (h.version) $("version").textContent = "version " + h.version + " · offline, deterministic, no language model"; }).catch(() => {});
loadRecent();
