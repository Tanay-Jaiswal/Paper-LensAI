"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const words = (s) => String(s ?? "").replace(/_/g, " ");
const MAX_BYTES = 25 * 1024 * 1024;
let cur = null;      // current analysis
let recent = [];
let busy = false;
let supportFilter = "all";
let votes = {};
let aiConfig = {enabled: false};   // optional AI second opinion (paperlens/second_opinion.py); off unless the server enables it
let opinions = {};
// Online deployment (PAPERLENS_HOSTED=1): the server lists only the papers this browser uploaded, by id.
let hosted = false;
const MY_IDS = "paperlens-my-papers";
function myIds() { try { return JSON.parse(localStorage.getItem(MY_IDS) || "[]"); } catch (_) { return []; } }
function remember(id) { if (!hosted) return; const ids = [id, ...myIds().filter((x) => x !== id)].slice(0, 200); try { localStorage.setItem(MY_IDS, JSON.stringify(ids)); } catch (_) {} }
const idsQuery = (sep) => hosted ? `${sep}ids=${encodeURIComponent(myIds().join(","))}` : "";                 // stored AI answers for the current paper, by claim id      // feedback on findings for the current paper: {target: {vote, note, text}}

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
  const fd = new FormData(); fd.append("file", file); fd.append("mode", $("mode").value);
  try { await show(await api("/api/analyze", {method: "POST", body: fd})); status(`Analysed ${file.name}.`, "ok"); }
  catch (e) { status(`Could not analyse ${file.name}: ${e.message}`, "bad"); }
  finally { setBusy(false); $("file").value = ""; }
}
async function loadRecent() {
  try { recent = await api("/api/analyses" + idsQuery("?")); } catch (_) { recent = []; }
  const shown = recent.slice(0, 8);
  $("recent").innerHTML = '<div class="recent"><div class="recent-head"><h3 class="section-label" id="recent-label">Analysed earlier</h3>' +
    (recent.length > shown.length ? `<span class="small muted">latest ${shown.length} of ${recent.length}</span>` : "") + "</div>" +
    (shown.length ? '<ul class="recent-list" aria-labelledby="recent-label">' + shown.map((r) => {
      const name = r.name || r.title, sub = r.title && r.title !== name ? r.title : "";
      return `<li><a href="#" data-id="${esc(r.id)}" title="${esc(sub ? name + "\n" + sub : name)}" class="${cur && cur.id === r.id ? "cur" : ""}"${cur && cur.id === r.id ? ' aria-current="true"' : ""}>` +
        `<span class="r-text"><span class="r-name">${esc(name)}</span>${sub ? `<span class="r-title">${esc(sub)}</span>` : ""}</span>` +
        `<span class="r-count">${esc(r.claims)} claim${r.claims === 1 ? "" : "s"}</span></a></li>`;
    }).join("") + "</ul>" : '<p class="recent-empty">No papers analysed yet. Upload a PDF or load the synthetic demo to start.</p>') + "</div>";
  $("recent").querySelectorAll("a").forEach((a) => a.onclick = async (ev) => {
    ev.preventDefault();
    if (busy) return;
    setBusy(true); status("Opening …", "busy");
    try { await show(await api("/api/analyses/" + a.dataset.id)); status(""); }
    catch (e) { status(e.message, "bad"); }
    finally { setBusy(false); }
  });
}

async function show(a) {
  cur = a; supportFilter = "all";
  remember(a.id);
  $("dl-fb").href = "/api/feedback.csv" + idsQuery("?");
  await loadVotes(a.id);
  opinions = {};
  if (aiConfig.enabled) { try { opinions = await api(`/api/analyses/${a.id}/second-opinion`); } catch (_) {} }
  $("welcome").hidden = true;
  $("workspace").hidden = false;
  $("title").textContent = a.document.title;
  $("meta").textContent = `${a.document.source_name} · ${a.document.n_pages} pages · ${a.document.n_sentences} sentences read` +
    (a.field && a.field.label ? ` · checks: ${a.field.label}` : "");
  $("meta").title = a.field && a.field.reason ? a.field.reason : "";
  $("dl-md").href = `/api/analyses/${a.id}/report.md`; $("dl-json").href = `/api/analyses/${a.id}/report.json`; $("dl-html").href = `/api/analyses/${a.id}/report.html`;
  $("dl-card").href = `/api/analyses/${a.id}/scorecard.pdf`; $("dl-card-html").href = `/api/analyses/${a.id}/scorecard.html`;
  $("warnings").innerHTML = a.document.warnings.map((w) => `<div class="warn"><strong>Parsing warning.</strong> ${esc(w)}</div>`).join("");
  const st = a.ledger_stats.support, r = a.reproducibility, high = a.gaps.filter((g) => g.severity === "high").length;
  const assessed = r.band !== "not assessed";
  $("tiles").innerHTML =
    tile(a.ledger_stats.n_claims, "claims found", `${st.strong} strong · ${st.moderate} moderate · ${st.weak} weak · ${st.none} without evidence`, "ledger") +
    tile(assessed ? r.score : "n/a", assessed ? (r.field === "cse" ? "CS reporting checklist / 100" : "reporting checklist / 100") : "checklist not assessed", assessed ? `${r.items.filter((i) => i.status === "missing").length} of ${r.items.length} items not reported` : "too little text was extracted", "repro") +
    tile(a.gaps.length, "candidate evidence gaps", `${high} high severity`, "gaps") +
    (a.consistency && a.consistency.checks ? tile(a.consistency.n_inconsistent, "numbers that do not add up",
      `of ${a.consistency.n_checked} statements recomputed`, "numbers") : "");
  document.querySelectorAll("#tiles .tile").forEach((t) => t.onclick = () => tab(t.dataset.tab));
  renderCard(a); renderReview(a); renderSummary(a); renderLedger(a); renderRepro(a); renderGaps(a); renderNumbers(a); renderRevise(a); renderRefs(a); renderGlossary(a); renderBench(a, "builtin"); renderCompareTab();
  tab("card");
  loadRecent();
}
function tile(big, label, sub, t) { return `<button class="tile" data-tab="${t}"><div class="big">${esc(big)}</div><div>${esc(label)}</div><div class="muted small">${esc(sub)}</div></button>`; }
function tab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => { b.classList.toggle("on", b.dataset.tab === name); b.setAttribute("aria-pressed", b.dataset.tab === name); });
  document.querySelectorAll(".tab").forEach((t) => t.hidden = t.id !== "tab-" + name);
}
document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => tab(b.dataset.tab));

function renderCard(a) {
  const c = a.scorecard;
  if (!c) { $("tab-card").innerHTML = `<p class="empty">No score card for this analysis.</p>`; return; }
  const p = c.parts;
  let h = `<div class="card"><div class="card-grade"><div class="grade-letter">${esc(c.grade)}</div><div><strong>Reporting grade</strong></div>` +
    `<div class="muted small">${esc(c.grade_text)}${c.points !== null ? ` · ${c.points} points of 100` : ""}</div></div><div class="card-parts"><table><tbody>` +
    `<tr><td>Reporting checklist</td><td><strong>${p.checklist_score}</strong> / 100${p.standard_score !== p.checklist_score ? ` <span class="muted small">(standard 15 items: ${p.standard_score})</span>` : ""}</td></tr>` +
    `<tr><td>Evidence for numeric claims</td><td><strong>${p.evidence_score === null ? "n/a" : p.evidence_score + " / 100"}</strong>${p.evidence_score === null ? ' <span class="muted small">no claim with numbers</span>' : ""}</td></tr>` +
    `<tr><td>High-severity evidence gaps</td><td><strong>${p.high_severity_gaps}</strong></td></tr>` +
    `<tr><td>Numbers that do not add up</td><td><strong>${p.numbers_not_adding_up}</strong></td></tr></tbody></table></div></div>`;
  h += `<h4>Top 3 problems and the fix for each</h4>`;
  h += c.top.length ? `<table><thead><tr><th>#</th><th>Problem</th><th>Fix</th></tr></thead><tbody>` + c.top.map((t, i) =>
    `<tr><td>${i + 1}</td><td>${esc(t.problem)}<div class="cite">${esc(t.category)} · ${esc(t.priority)} priority${t.page ? " · p." + t.page : ""} · ${esc(t.id)} in the revision checklist</div></td><td><strong>${esc(t.fix)}</strong></td></tr>`).join("") + "</tbody></table>"
    : `<p class="empty">${c.assessed ? "No finding needs a revision." : "Not graded: too little text could be extracted from this PDF."}</p>`;
  h += `<p class="small"><a href="/api/analyses/${esc(a.id)}/scorecard.pdf">Download the score card as PDF</a> · <a href="/api/analyses/${esc(a.id)}/scorecard.html" target="_blank" rel="noopener">Open a printable page</a></p>`;
  h += `<p class="cite">How the grade is computed: ${esc(c.formula)}. This paper: penalty ${p.penalty}.</p><p class="muted small">${esc(c.caveat)}</p>`;
  $("tab-card").innerHTML = h;
}

// Reviewer mode (paperlens/review.py): every point is an existing finding, cited to a page.
async function renderReview(a) {
  const mine = a.id;
  $("tab-review").innerHTML = `<p class="muted small"><span class="spin"></span>Drafting …</p>`;
  let r;
  try { r = await api(`/api/analyses/${a.id}/review.json`); }
  catch (e) { $("tab-review").innerHTML = `<p class="empty">The review could not be drafted: ${esc(e.message)}</p>`; return; }
  if (!cur || cur.id !== mine) return;
  const pt = (p, i, kind) => `<li>${esc(p.text)}${p.quote ? `<blockquote>${esc(p.quote)}</blockquote>` : ""}<div class="cite">${esc(p.source)}</div>${fbButtons(`review:${kind}${i + 1}`, p.text)}</li>`;
  let h = `<h3>Review draft</h3><p class="muted small">${esc(r.method)} <a href="/api/analyses/${esc(a.id)}/review.md">Download as Markdown</a> · <a href="/api/analyses/${esc(a.id)}/review.html" target="_blank" rel="noopener">Open a printable page</a> · <button type="button" class="ghost showon" id="rv-copy">Copy as text</button> <span id="rv-st" class="small"></span></p>`;
  h += `<h4>Summary</h4>` + r.summary.map((s) => `<p>${esc(s)}</p>`).join("");
  if (r.assessed) {
    h += `<h4>Strengths</h4>` + (r.strengths.length ? `<ul class="rv">${r.strengths.map((p, i) => pt(p, i, "S")).join("")}</ul>` : `<p class="empty">None found by the rules.</p>`);
    h += `<h4>Weaknesses</h4>` + (r.weaknesses.length ? `<ul class="rv">${r.weaknesses.map((p, i) => pt(p, i, "W")).join("")}</ul>` : `<p class="empty">None found by the rules.</p>`);
    if (r.minor.count) h += `<p class="small muted">Plus ${r.minor.count} minor item(s). ${esc(r.minor.note)}</p>`;
    h += `<h4>Questions for the authors</h4>` + (r.questions.length ? `<ol class="rv">${r.questions.map((q, i) => `<li>${esc(q.text)}<div class="cite">${esc(q.source)}</div>${fbButtons("review:Q" + (i + 1), q.text)}</li>`).join("")}</ol>` : `<p class="empty">None.</p>`);
  }
  h += `<h4>What this draft does not cover</h4><p class="muted small">${esc(r.limits)}</p>`;
  $("tab-review").innerHTML = h;
  $("rv-copy").onclick = async () => {
    try {
      const md = await (await fetch(`/api/analyses/${a.id}/review.md`)).text();
      await navigator.clipboard.writeText(md); $("rv-st").textContent = "Copied.";
    } catch (_) { $("rv-st").textContent = "Copy failed; use Download instead."; }
  };
}

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

const THUMB = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M5 7v7H2V7h3zm1 7V7l3-5c1 0 2 .7 2 2l-.5 3H14c.7 0 1.2.7 1 1.4l-1.3 4.8c-.2.5-.6.8-1.1.8H6z" fill="currentColor"/></svg>';
// Thumbs up / down on one finding. Stored on this computer next to the analysis (paperlens/feedback.py).
function fbButtons(target, text) {
  const v = (votes[target] || {}).vote;
  return `<span class="fb" data-target="${esc(target)}" data-text="${esc(String(text || "").slice(0, 600))}">` +
    `<button type="button" class="fbb up${v === "up" ? " on" : ""}" aria-pressed="${v === "up"}" title="Useful / correct" aria-label="Thumbs up: this finding is useful">${THUMB}</button>` +
    `<button type="button" class="fbb down${v === "down" ? " on" : ""}" aria-pressed="${v === "down"}" title="Not useful / wrong" aria-label="Thumbs down: this finding is wrong or not useful">${THUMB}</button></span>`;
}
async function loadVotes(id) {
  try { votes = (await api(`/api/analyses/${id}/feedback`)).votes || {}; } catch (_) { votes = {}; }
}
document.addEventListener("click", async (ev) => {
  const b = ev.target.closest(".fbb"); if (!b || !cur) return;
  ev.stopPropagation(); ev.preventDefault();
  const box = b.closest(".fb"), target = box.dataset.target, want = b.classList.contains("up") ? "up" : "down";
  const vote = (votes[target] || {}).vote === want ? "clear" : want;
  try {
    const r = await api(`/api/analyses/${cur.id}/feedback`, {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target, vote, text: box.dataset.text})});
    votes = r.votes || {};
    document.querySelectorAll(`.fb[data-target="${CSS.escape(target)}"]`).forEach((el) => {
      const v = (votes[target] || {}).vote;
      el.querySelector(".up").classList.toggle("on", v === "up"); el.querySelector(".up").setAttribute("aria-pressed", v === "up");
      el.querySelector(".down").classList.toggle("on", v === "down"); el.querySelector(".down").setAttribute("aria-pressed", v === "down");
    });
  } catch (e) { status("Could not save the feedback: " + e.message, "bad"); }
}, true);

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
    h += `<tr class="claim" data-id="${esc(c.id)}" tabindex="0"><td>${esc(c.id)}</td><td>${esc(c.text)}<div class="cite">${esc(c.claim_type)}${c.hedged ? " · hedged" : ""}</div></td><td>${c.page}</td><td>${pill(c.support, SUPPORT_LABEL[c.support])}${fbButtons("claim:" + c.id, c.support + ": " + c.text)}</td></tr>`;
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
    h += `<div class="ev"><div><strong>Evidence ${i + 1} for ${esc(c.id)}</strong> <span class="cite">p.${e.page} · ${esc(e.section)}</span></div><blockquote>${esc(e.quote)}</blockquote>` +
      `<div class="small muted"><strong>Why this passage:</strong> ${why.join("; ")}. Match score ${e.score} (wording relevance ${e.lexical}).</div>` +
      `<div class="small fbline">Does this passage support the claim? ${fbButtons(`evidence:${c.id}-${i + 1}`, `${c.text} || p.${e.page}: ${e.quote}`)}</div>` +
      `<div class="small"><button type="button" class="ghost showon" data-sid="${e.sentence_id}" data-page="${e.page}">Show on page ${e.page}</button> ` +
      `<a href="/api/analyses/${esc(cur.id)}/highlighted.pdf?claim=${esc(c.id)}#page=${e.page}" target="_blank" rel="noopener">open in the PDF</a> <span class="loc muted" id="loc-${e.sentence_id}"></span></div></div>`;
  });
  if (aiConfig.enabled) h += `<div class="ai" id="ai-box">${opinionHtml(c)}</div>`;
  const pages = [...new Set([c.page, ...ev.map((e) => e.page)])];
  h += `<h4>Source page${pages.length > 1 ? "s" : ""}</h4><p class="small muted">Highlighted: the claim (yellow, labelled C) and its evidence (labelled E1, E2 ...). Use "Show on page" to enlarge a page at a passage, or open the original PDF with the same highlights: <a href="/api/analyses/${esc(cur.id)}/highlighted.pdf?claim=${esc(c.id)}#page=${c.page}" target="_blank" rel="noopener">highlighted PDF, p.${c.page}</a>. If a passage is not highlighted, the page number is still its citation: its wording could not be located automatically on the page.</p><div class="pages">${pages.map((p) => {
    const ids = [c.sentence_id, ...ev.filter((e) => e.page === p).map((e) => e.sentence_id)].join(",");
    const src = `/api/analyses/${cur.id}/page/${p}.png?highlight=${ids}`;
    return `<figure data-page="${p}"><figcaption class="cite">Page ${p} of ${cur.document.n_pages}</figcaption><div class="pagebox"><a href="${src}&zoom=2.4" target="_blank" rel="noopener"><img loading="lazy" alt="Page ${p} with highlights" src="${src}"></a></div></figure>`;
  }).join("")}</div>`;
  const v = $("viewer");
  v.dataset.claim = id; v.innerHTML = h; v.scrollTop = 0;
  v.querySelectorAll("img").forEach((img) => img.onerror = () => { img.closest("figure").innerHTML = `<p class="empty">The image of this page could not be loaded.</p>`; });
  v.querySelectorAll("button.showon").forEach((b) => b.onclick = () => showOnPage(+b.dataset.sid, +b.dataset.page));
  const ab = $("ai-ask"); if (ab) ab.onclick = () => askOpinion(c);
  markPassages(c, id);
}
const VERDICT = {supported: "supported", partly_supported: "partly supported", not_supported: "not supported", not_checked: "not checked"};
function opinionHtml(c) {
  const o = opinions[c.id];
  let h = `<div class="ai-head"><span class="tag ai-tag">AI-assisted</span> <strong>Second opinion for evidence in other words</strong></div>` +
    `<p class="small muted">Optional. A language model (${esc(aiConfig.model)}) reads ${esc(aiConfig.sends)} and says whether any passage supports the claim. This sends that text to Anthropic. It does not change the rule-based rating above or any score.</p>`;
  if (!o) return h + `<button type="button" class="ghost" id="ai-ask">Ask an AI second opinion</button> <span id="ai-status" class="small"></span>`;
  h += `<p><strong>AI verdict: ${esc(VERDICT[o.verdict] || o.verdict)}</strong> <span class="muted small">(rule-based rating: ${esc(SUPPORT_LABEL[o.rule_based_support] || o.rule_based_support)}; ${o.n_passages_sent} passages sent; ${esc(o.model)}, ${esc(o.at)})</span></p><p class="small">${esc(o.explanation)}</p>`;
  h += o.supporting.map((x) => `<div class="ev ai-ev"><div class="small"><strong>Passage the AI points to</strong> <span class="cite">p.${x.page} · ${esc(x.section)}${x.also_found_by_rules ? " · also returned by the rules" : " · not returned by the rules"}</span></div><blockquote>${esc(x.quote)}</blockquote></div>`).join("");
  return h + `<p class="small muted">The quote is copied from the paper by PaperLens, not written by the AI. Check it on the page before relying on it. <button type="button" class="ghost" id="ai-ask">Ask again</button> <span id="ai-status" class="small"></span></p>`;
}
async function askOpinion(c) {
  const b = $("ai-ask"); b.disabled = true; $("ai-status").innerHTML = '<span class="spin"></span>Asking …';
  try {
    opinions[c.id] = await api(`/api/analyses/${cur.id}/second-opinion`, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({claim: c.id})});
    if ($("viewer").dataset.claim === c.id) { $("ai-box").innerHTML = opinionHtml(c); const ab = $("ai-ask"); if (ab) ab.onclick = () => askOpinion(c); }
  } catch (e) { $("ai-status").className = "small bad"; $("ai-status").textContent = e.message; b.disabled = false; }
}
// Boxes and labels over the page images, from the same text search that draws the highlights (paperlens/highlight.py).
async function markPassages(c, id) {
  const sids = [c.sentence_id, ...c.evidence.map((e) => e.sentence_id)];
  let r;
  try { r = await api(`/api/analyses/${cur.id}/locate?ids=${sids.join(",")}`); } catch (_) { return; }
  if ($("viewer").dataset.claim !== id) return;
  const label = (sid) => sid === c.sentence_id ? "C" : "E" + (c.evidence.findIndex((e) => e.sentence_id === sid) + 1);
  for (const L of r.located) {
    const box = document.querySelector(`#viewer figure[data-page="${L.page}"] .pagebox`);
    const st = $("loc-" + L.sentence_id);
    if (st) st.textContent = L.method === "exact" ? "· located on the page" : L.method === "partial" ? "· located in part (some of its words)" : "· could not be located on the page; the page number is its citation";
    if (!box) continue;
    L.rects.forEach((q, k) => {
      const d = document.createElement("div");
      d.className = "hl " + (label(L.sentence_id) === "C" ? "hl-claim" : "hl-ev");
      d.dataset.sid = L.sentence_id;
      Object.assign(d.style, {left: q[0] * 100 + "%", top: q[1] * 100 + "%", width: (q[2] - q[0]) * 100 + "%", height: (q[3] - q[1]) * 100 + "%"});
      if (k === 0) { const t = document.createElement("span"); t.className = "hl-tag"; t.textContent = label(L.sentence_id); d.appendChild(t); }
      box.appendChild(d);
    });
  }
}
function showOnPage(sid, page) {
  const fig = document.querySelector(`#viewer figure[data-page="${page}"]`); if (!fig) return;
  document.querySelectorAll("#viewer figure").forEach((f) => f.classList.toggle("focus", f === fig));
  document.querySelectorAll("#viewer .hl").forEach((d) => d.classList.toggle("pulse", +d.dataset.sid === sid));
  const first = fig.querySelector(`.hl[data-sid="${sid}"]`);
  (first || fig).scrollIntoView({block: "center", behavior: "smooth"});
}

function renderRepro(a) {
  const r = a.reproducibility, assessed = r.band !== "not assessed";
  const missing = r.items.filter((i) => i.status === "missing"), na = r.items.filter((i) => i.status === "not_applicable");
  const cse = r.field === "cse";
  let h = `<h3>Reproducibility reporting checklist${cse ? ": Computer Science &amp; Engineering" : ""}</h3><div class="warn"><strong>What this score means.</strong> ${esc(r.disclaimer)} A high score is not proof that the study reproduces, and a low score is not proof that it does not.</div>`;
  if (a.field && a.field.reason) h += `<p class="muted small">Checks used: ${esc(a.field.label)}. ${esc(a.field.reason)}` +
    (cse ? ` The score covers the 15 standard items and ${r.cse_items.length} CS items (marked CS); the standard 15-item score is <strong>${esc(r.standard_score)}</strong>, which is the one to compare with papers checked in the general mode.` : "") + `</p>`;
  h += `<div class="row"><div class="scorebox"><div class="score">${assessed ? r.score : "n/a"}</div><div class="muted">${assessed ? "/ 100 · " + esc(r.band) + " coverage" : "not assessed"}</div></div><div style="flex:1;min-width:240px">`;
  for (const [k, v] of Object.entries(r.categories)) h += `<div class="cat"><span>${esc(k)}</span> <span class="muted small">${v.score}</span><div class="bar"><i style="width:${Math.max(0, Math.min(100, v.score))}%"></i></div></div>`;
  h += `</div></div>`;
  if (assessed) h += `<p><strong>Not reported (${missing.length}):</strong> ${missing.length ? esc(missing.map((i) => i.label).join("; ")) : "none of the checklist items is missing"}.` +
    (na.length ? ` <span class="muted">Not applicable to this paper and left out of the score: ${esc(na.map((i) => i.label).join("; "))}.</span>` : "") + `</p>`;
  h += "<table><thead><tr><th>Item</th><th>Status</th><th>Weight</th><th>Quote that earned the credit, or what to add</th></tr></thead><tbody>";
  for (const i of r.items) {
    const ev = i.evidence[0];
    h += `<tr><td>${esc(i.label)}<div class="cite">${esc(i.category)}${i.key.startsWith("cs_") ? " · CS" : ""}</div></td><td>${pill(i.status)}${fbButtons("repro:" + i.key, i.label + ": " + i.status)}</td><td>${i.weight}</td><td>` +
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
    h += `<tr><td>${pill(g.severity)}${fbButtons("gap:" + g.id, g.kind + ": " + g.message)}</td><td>${esc(words(g.kind))}</td><td>${esc(g.message)}` +
      (g.quote ? `<blockquote>${esc(g.quote)}</blockquote>` : "") +
      (g.claim_id ? `<a href="#" class="small jump" data-id="${esc(g.claim_id)}">Open claim ${esc(g.claim_id)} in the ledger</a>` : "") + `</td><td>${g.page ?? "—"}</td></tr>`;
  }
  $("tab-gaps").innerHTML = h + "</tbody></table>";
  $("tab-gaps").querySelectorAll("a.jump").forEach((l) => l.onclick = (ev) => {
    ev.preventDefault(); supportFilter = "all"; renderLedger(cur); tab("ledger"); openClaim(l.dataset.id);
    const tr = document.querySelector(`tr.claim[data-id="${l.dataset.id}"]`); if (tr) tr.scrollIntoView({block: "center"});
  });
}

const NUM_STATUS = {inconsistent: ["none", "does not add up"], not_reproduced: ["partial", "not reproduced"], consistent: ["strong", "checks out"]};
function renderNumbers(a) {
  const c = a.consistency;
  if (!c || !c.checks) { $("tab-numbers").innerHTML = `<p class="empty">This analysis was made by an older version. Upload the PDF again to run the numbers check.</p>`; return; }
  let h = `<h3>${c.n_checked} statement${c.n_checked === 1 ? "" : "s"} recomputed: ${c.n_inconsistent} do${c.n_inconsistent === 1 ? "es" : ""} not add up, ${c.n_not_reproduced} not reproduced, ${c.n_consistent} check out</h3>
    <p class="muted small">${esc(c.method)}</p><p class="muted small">${esc(c.caveat)}</p>`;
  if (!c.checks.length) { $("tab-numbers").innerHTML = h + `<p class="empty">No statement in this paper prints a result next to the numbers it is computed from in a form the checks recognise.</p>`; return; }
  const kinds = Object.entries(c.by_kind).map(([k, v]) => `${esc(c.labels[k] || words(k))}: ${v.checked}` + (v.inconsistent ? ` (${v.inconsistent} not adding up)` : "")).join(" · ");
  h += `<p class="cite">${kinds}</p><table><thead><tr><th>Result</th><th>Check</th><th>Detail and recomputation</th><th>Page</th></tr></thead><tbody>`;
  for (const x of c.checks) {
    const [cls, label] = NUM_STATUS[x.status];
    h += `<tr><td>${pill(cls, label)}${x.status === "inconsistent" ? `<div class="cite">${esc(x.severity)}</div>` : ""}${fbButtons("number:" + x.id, x.status + ": " + x.message)}</td><td>${esc(c.labels[x.kind] || words(x.kind))}</td>
      <td>${esc(x.message)}<div class="cite">Recomputed: ${esc(x.formula)} · printed: ${esc(x.stated)}</div><blockquote>${esc(x.quote)}</blockquote></td>
      <td><a href="/api/analyses/${esc(a.id)}/page/${x.page}.png?highlight=${x.sentence_id}" target="_blank" rel="noopener">p.${x.page}</a></td></tr>`;
  }
  $("tab-numbers").innerHTML = h + "</tbody></table>";
}

function renderRevise(a) {
  const r = a.revisions;
  if (!r) { $("tab-revise").innerHTML = `<p class="empty">This analysis was made by an older version. Upload the PDF again to build the checklist.</p>`; return; }
  const n = (p) => r.filter((x) => x.priority === p).length;
  let h = `<h3>${r.length} suggested revision${r.length === 1 ? "" : "s"} for the authors</h3><p class="muted small">${n("high")} high, ${n("medium")} medium, ${n("low")} low priority. Each item is one finding from the Numbers check, the evidence gaps or the reproducibility checklist, rewritten as a fix; the source column says which. Nothing is generated, so the same paper always gets the same list.</p>`;
  if (!r.length) { $("tab-revise").innerHTML = h + `<p class="empty">No finding needs a revision.</p>`; return; }
  h += `<table><thead><tr><th>Priority</th><th>Area</th><th>What to change and why</th><th>Page</th></tr></thead><tbody>`;
  for (const x of r) {
    h += `<tr><td>${pill(x.priority)}${fbButtons("revision:" + x.id, x.action)}</td><td>${esc(x.category)}</td><td><strong>${esc(x.action)}</strong><div class="small">${esc(x.why)}</div>` +
      (x.quote ? `<blockquote>${esc(x.quote)}</blockquote>` : "") + `<div class="cite">${esc(x.id)} · from ${esc(x.source)}</div></td><td>${x.page ? `p.${x.page}` : "—"}</td></tr>`;
  }
  $("tab-revise").innerHTML = h + "</tbody></table>";
}

const CITE_KIND = {cited_not_listed: "cited but not in the list", listed_not_cited: "in the list but never cited",
  duplicate_entry: "listed twice", entry_without_year: "entry without a year"};
function renderRefs(a) {
  const c = a.citations;
  if (!c || !c.method) { $("tab-refs").innerHTML = `<p class="empty">This analysis was made by an older version. Upload the PDF again to check the references.</p>`; return; }
  const f = c.findings;
  let h = `<h3>Citation and reference checks</h3><p class="muted small">${esc(c.method)} ${esc(c.caveat)}</p>`;
  h += `<p>${c.style === "none" ? "Citation style not recognised" : `Style: <strong>${esc(c.style)}</strong>`} · ${c.n_entries} reference entries read · ${c.n_citations} in-text citations found` +
    (c.checked ? ` · <strong>${f.filter((x) => x.kind === "cited_not_listed" || x.kind === "listed_not_cited").length}</strong> citation mismatches` : "") + `</p>`;
  if (c.note) h += `<div class="warn">${esc(c.note)}</div>`;
  const pr = c.profile || {};
  if (pr.n_entries) h += `<p class="small">List profile (information, not a problem): ${pr.with_year} of ${pr.n_entries} entries have a year` +
    (pr.median_year ? `; median year ${pr.median_year}, newest ${pr.newest_year}` : "") +
    (pr.last_5_years !== undefined ? `; ${pr.last_5_years} from the five years up to ${pr.reference_year}` : "") +
    `; ${pr.preprints} preprint${pr.preprints === 1 ? "" : "s"} (arXiv and similar); ${pr.with_doi_or_link} with a DOI or link.</p>`;
  if (!f.length) { $("tab-refs").innerHTML = h + `<p class="empty">${c.checked || pr.n_entries ? "No citation or reference problem was found by these rules." : "Nothing could be checked."}</p>`; return; }
  h += `<table><thead><tr><th>Severity</th><th>Check</th><th>Detail</th><th>Page</th></tr></thead><tbody>` + f.map((x) =>
    `<tr><td>${pill(x.severity)}${fbButtons("reference:" + x.id, x.kind + ": " + x.message)}</td><td>${esc(CITE_KIND[x.kind] || words(x.kind))}</td><td>${esc(x.message)}${x.quote ? `<blockquote>${esc(x.quote)}</blockquote>` : ""}</td>` +
    `<td>${x.page ? (x.sentence_id != null ? `<a href="/api/analyses/${esc(a.id)}/page/${x.page}.png?highlight=${x.sentence_id}" target="_blank" rel="noopener">p.${x.page}</a>` : "p." + x.page) : "—"}</td></tr>`).join("") + "</tbody></table>";
  h += `<p class="cite">Not checked: whether a cited work was retracted, whether a DOI resolves, or whether a work says what it is cited for (no online lookups).</p>`;
  $("tab-refs").innerHTML = h;
}

function renderGlossary(a) {
  const g = a.glossary;
  if (!g || !g.defined) { $("tab-glossary").innerHTML = `<p class="empty">This analysis was made by an older version. Upload the PDF again to build the glossary.</p>`; return; }
  let h = `<h3>${g.defined.length} abbreviation${g.defined.length === 1 ? "" : "s"} defined by the paper</h3><p class="muted small">${esc(g.note)} When claims are matched to evidence, an abbreviation and its long form count as the same words.</p>`;
  h += g.defined.length ? `<table><thead><tr><th>Abbreviation</th><th>Meaning (as the paper defines it)</th><th>Uses</th><th>Defined on</th></tr></thead><tbody>` +
    g.defined.map((d) => `<tr><td><strong>${esc(d.abbr)}</strong></td><td>${esc(d.long)} <span class="tag">paper</span><div class="cite">${esc(d.quote)}</div></td><td>${d.uses}</td><td>p.${d.page}</td></tr>`).join("") + "</tbody></table>"
    : `<p class="empty">The paper does not define any abbreviation in the form "long form (ABBR)".</p>`;
  if (g.dictionary_used) {
    const fd = g.from_dictionary || [];
    h += `<h4>${fd.length} meaning${fd.length === 1 ? "" : "s"} from the built-in CS dictionary</h4><p class="muted small">Not defined in the paper. These are standard Computer Science meanings, not the paper's own words, and the paper may mean something else. "Ambiguous" means the abbreviation has several common meanings and all are shown. Dictionary meanings are not used when matching claims to evidence.</p>` +
      (fd.length ? `<table><thead><tr><th>Abbreviation</th><th>Dictionary meaning</th><th>Uses</th><th>First on</th></tr></thead><tbody>` +
        fd.map((d) => `<tr><td><strong>${esc(d.abbr)}</strong></td><td>${esc(d.long)} <span class="tag dict">dictionary</span>${d.ambiguous ? ' <span class="tag">ambiguous</span>' : ""}<div class="cite">${esc(d.kind)}</div></td><td>${d.uses}</td><td>p.${d.page}</td></tr>`).join("") + "</tbody></table>"
        : `<p class="empty">No dictionary abbreviation is used without a definition.</p>`);
  }
  h += `<h4>Used but never defined in the paper</h4>` + (g.undefined.length ? `<p class="small">${g.undefined.map((u) => `<strong>${esc(u.abbr)}</strong> <span class="muted">×${u.uses}, first p.${u.page}</span>`).join(" · ")}</p><p class="muted small">These may be standard in the field (or names of instruments and software). PaperLens does not guess their meaning${g.dictionary_used ? "; they are not in the built-in CS dictionary either" : ""}.</p>` : `<p class="empty">None found.</p>`);
  $("tab-glossary").innerHTML = h;
}

const ITEM_STATUS = {present: "reported", partial: "partly", missing: "not reported", not_applicable: "not applicable"};
async function renderBench(a, which) {
  const mine = a.id;
  $("tab-bench").innerHTML = `<p class="muted small"><span class="spin"></span>Comparing …</p>`;
  let b;
  try { b = await api(`/api/analyses/${a.id}/benchmark?set=${which}${idsQuery("&")}`); }
  catch (e) { $("tab-bench").innerHTML = `<p class="empty">The comparison could not be made: ${esc(e.message)}</p>`; return; }
  if (!cur || cur.id !== mine) return;
  const pick = `<p class="small">Compare with: <select id="bench-set" aria-label="Comparison set"><option value="builtin"${which === "builtin" ? " selected" : ""}>Built-in set of development CS papers</option><option value="mine"${which === "mine" ? " selected" : ""}>My CS papers analysed on this computer</option></select></p>`;
  let h = `<h3>CS comparison: this paper's reporting against other Computer Science papers</h3>` + pick;
  if (!b.available) { $("tab-bench").innerHTML = h + `<p class="empty">${esc(b.reason)}</p>`; bindBench(a); return; }
  const sc = b.score;
  h += `<p class="muted small">${esc(b.set)} · ${b.n} paper${b.n === 1 ? "" : "s"}</p>`;
  if (b.warning) h += `<div class="warn">${esc(b.warning)}</div>`;
  h += `<div class="bench-head"><div><div class="big-num">${sc.percentile}<span>th</span></div><div class="small">percentile for the CS checklist score</div></div>` +
    `<div class="small">This paper <strong>${b.paper.score}</strong> / 100 · median of the set <strong>${sc.median}</strong> · range ${sc.min}–${sc.max} · rank ${sc.rank} of ${b.n + 1}` +
    `<br>Standard 15-item score: ${b.paper.standard_score} (percentile ${b.standard_score.percentile}, set median ${b.standard_score.median})` +
    (b.evidence_score ? `<br>Evidence for numeric claims: ${b.paper.evidence_score} (percentile ${b.evidence_score.percentile} of ${b.evidence_score.n} papers with numeric claims, median ${b.evidence_score.median})` : "") + `</div></div>`;
  // dot strip: every paper in the set as a tick, this paper as a marked dot
  const W = 600, x = (v) => 10 + (W - 20) * v / 100;
  h += `<svg class="strip" viewBox="0 0 ${W} 54" role="img" aria-label="CS checklist scores of the set with this paper marked at ${b.paper.score}">` +
    `<line x1="10" x2="${W - 10}" y1="26" y2="26" class="axis"/>` + [0, 25, 50, 75, 100].map((t) => `<text x="${x(t)}" y="50" text-anchor="middle">${t}</text>`).join("") +
    sc.values.map((v) => `<line x1="${x(v)}" x2="${x(v)}" y1="16" y2="36" class="tick"><title>${v}</title></line>`).join("") +
    `<circle cx="${x(b.paper.score)}" cy="26" r="7" class="me"><title>This paper: ${b.paper.score}</title></circle><text x="${x(b.paper.score)}" y="10" text-anchor="middle" class="me-label">this paper</text></svg>`;
  const notes = b.items.filter((i) => i.note);
  if (notes.length) h += `<h4>Where this paper differs from the set</h4><ul>${notes.map((i) => `<li><strong>${esc(i.label)}</strong>${i.cs ? ' <span class="tag">CS</span>' : ""}: ${esc(i.note)}</li>`).join("")}</ul>`;
  h += `<h4>Every checklist item</h4><table><thead><tr><th>Item</th><th>This paper</th><th>Papers in the set reporting it</th></tr></thead><tbody>` +
    b.items.map((i) => `<tr><td>${esc(i.label)}${i.cs ? ' <span class="tag">CS</span>' : ""}</td><td>${pill(i.status, ITEM_STATUS[i.status])}</td>` +
      `<td>${i.set_reporting_share === null ? '<span class="muted">not rated</span>' : `<span class="share"><i style="width:${i.set_reporting_share}%"></i></span> ${i.set_reporting_share}% <span class="muted small">of ${i.set_rated}</span>`}</td></tr>`).join("") + "</tbody></table>";
  h += `<details class="legend"><summary>Papers in this set</summary><ul class="small">${b.papers.map((p) => `<li>${esc(p.title)} · ${p.score}</li>`).join("")}</ul></details>`;
  h += `<p class="muted small">${esc(b.caveat)} "Reporting it" counts present and partly present.</p>`;
  $("tab-bench").innerHTML = h;
  bindBench(a);
}
function bindBench(a) { const s = $("bench-set"); if (s) s.onchange = () => renderBench(a, s.value); }

async function renderCompareTab() {
  const mine = cur.id;
  try { recent = await api("/api/analyses" + idsQuery("?")); } catch (_) {}
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
    remember(d.b);
    await show(await api("/api/analyses/" + d.a));
    status("Synthetic demo loaded (generated papers, not real studies). Open the Compare tab to contrast it with demo-overclaiming.pdf.", "ok");
  } catch (e) { status("Could not load the demo: " + e.message, "bad"); }
  finally { setBusy(false); }
};
const configReady = api("/api/config").then((c) => {
  aiConfig = c.ai_second_opinion || {enabled: false};
  hosted = !!c.hosted;
  if (hosted) $("drop-help").textContent = "PDF only, up to 25 MB. Text PDFs work best. The file is uploaded to this PaperLens server and stored there so it can be analysed; only this browser lists it.";
}).catch(() => {});
configReady.then(() => api("/api/health")).then((h) => {
  if (h.version) $("version").textContent = "version " + h.version + (hosted ? " · online server" : " · offline") + " · deterministic rules" +
    (aiConfig.enabled ? " · optional AI second opinion on" : " · no language model");
}).catch(() => {});
configReady.then(loadRecent);
