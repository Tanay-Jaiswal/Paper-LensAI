"use strict";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
let cur = null;      // current analysis
let recent = [];

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return r.json();
}
function status(msg, bad) { const el = $("status"); el.textContent = msg || ""; el.style.color = bad ? "var(--none)" : "var(--muted)"; }

async function upload(file) {
  if (!file) return;
  status("Analysing " + file.name + " …");
  const fd = new FormData(); fd.append("file", file);
  try { show(await api("/api/analyze", {method: "POST", body: fd})); status(""); loadRecent(); }
  catch (e) { status(e.message, true); }
}
async function loadRecent() {
  try { recent = await api("/api/analyses"); } catch (_) { recent = []; }
  $("recent").innerHTML = recent.length ? '<div class="recent muted">Recent: ' +
    recent.slice(0, 8).map((r) => `<a data-id="${esc(r.id)}">${esc(r.name || r.title)}</a>`).join("") + "</div>" : "";
  $("recent").querySelectorAll("a").forEach((a) => a.onclick = async () => show(await api("/api/analyses/" + a.dataset.id)));
}

function show(a) {
  cur = a;
  $("workspace").hidden = false;
  $("title").textContent = a.document.title;
  $("meta").textContent = `${a.document.n_pages} pages · ${a.ledger_stats.n_claims} claims · reproducibility ${a.reproducibility.score}/100 · ${a.gaps.length} gaps · ${a.document.source_name}`;
  $("dl-md").href = `/api/analyses/${a.id}/report.md`; $("dl-json").href = `/api/analyses/${a.id}/report.json`;
  $("warnings").innerHTML = a.document.warnings.map((w) => `<div class="warn">${esc(w)}</div>`).join("");
  renderSummary(a); renderLedger(a); renderRepro(a); renderGaps(a); renderCompareTab();
  tab("summary");
}
function tab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((t) => t.hidden = t.id !== "tab-" + name);
}
document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => tab(b.dataset.tab));

function renderSummary(a) {
  const s = a.summary; let h = "<h3>TL;DR</h3>";
  h += (s.tldr || []).map((t) => `<p>${esc(t.text)} <span class="cite">p.${t.page}</span></p>`).join("") || "<p class='muted'>No summary available.</p>";
  for (const [k, items] of Object.entries(s.facets || {})) {
    if (!items.length) continue;
    h += `<div class="facet"><h4>${esc(k)}</h4><ul>` +
      items.map((i) => `<li>${esc(i.text)} <span class="cite">p.${i.page}, ${esc(i.section)}</span></li>`).join("") + "</ul></div>";
  }
  h += `<p class="cite">${esc(s.method || "")}. Sentences are quoted verbatim from the paper.</p>`;
  $("tab-summary").innerHTML = h;
}

function renderLedger(a) {
  const st = a.ledger_stats.support;
  let h = `<h3>Research Evidence Ledger</h3><p class="muted">${a.ledger_stats.n_claims} claims · ` +
    ["strong", "moderate", "weak", "none"].map((k) => `${st[k]} ${k}`).join(" · ") + "</p>";
  h += "<table><thead><tr><th>ID</th><th>Claim</th><th>Page</th><th>Support</th></tr></thead><tbody>";
  for (const c of a.ledger) {
    h += `<tr class="claim" data-id="${esc(c.id)}"><td>${esc(c.id)}</td><td>${esc(c.text)}<div class="cite">${esc(c.claim_type)}${c.hedged ? " · hedged" : ""}</div></td><td>${c.page}</td><td><span class="pill ${c.support}">${c.support}</span></td></tr>`;
  }
  h += "</tbody></table>";
  $("ledger").innerHTML = h;
  $("ledger").querySelectorAll("tr.claim").forEach((tr) => tr.onclick = () => openClaim(tr.dataset.id));
}
function openClaim(id) {
  const c = cur.ledger.find((x) => x.id === id); if (!c) return;
  document.querySelectorAll("tr.claim").forEach((t) => t.classList.toggle("sel", t.dataset.id === id));
  const ev = c.evidence.filter((e) => c.support !== "none" || e.score > 0.15);
  let h = `<h3>${esc(c.id)} <span class="pill ${c.support}">${c.support}</span></h3><blockquote>${esc(c.text)}<div class="cite">p.${c.page}, ${esc(c.section)}</div></blockquote>`;
  if (!ev.length) h += `<p><strong>${esc(c.evidence_note || "No supporting evidence found")}.</strong></p>`;
  ev.forEach((e, i) => {
    h += `<p><strong>Evidence ${i + 1}</strong> <span class="cite">p.${e.page}, ${esc(e.section)}, score ${e.score}` +
      (e.shared_numbers.length ? `, shared numbers: ${esc(e.shared_numbers.join(", "))}` : "") + `</span></p><blockquote>${esc(e.quote)}</blockquote>`;
  });
  const pages = [...new Set([c.page, ...ev.map((e) => e.page)])];
  h += `<div class="row">${pages.map((p) => {
    const ids = [c.sentence_id, ...ev.filter((e) => e.page === p).map((e) => e.sentence_id)].join(",");
    return `<div><div class="cite">Page ${p}</div><img alt="Page ${p} with highlights" src="/api/analyses/${cur.id}/page/${p}.png?highlight=${ids}"></div>`;
  }).join("")}</div>`;
  $("viewer").innerHTML = h;
}

function renderRepro(a) {
  const r = a.reproducibility;
  let h = `<div class="row"><div><div class="score">${r.score}</div><div class="muted">/ 100 · ${esc(r.band)}</div></div><div style="flex:1;min-width:240px">`;
  for (const [k, v] of Object.entries(r.categories)) h += `<div>${esc(k)} <span class="muted">${v.score}</span><div class="bar"><i style="width:${v.score}%"></i></div></div>`;
  h += `</div></div><p class="cite">${esc(r.formula)}. ${esc(r.disclaimer)}</p>`;
  h += "<table><thead><tr><th>Item</th><th>Status</th><th>Weight</th><th>Evidence in paper / advice</th></tr></thead><tbody>";
  for (const i of r.items) {
    const ev = i.evidence[0];
    h += `<tr><td>${esc(i.label)}</td><td><span class="pill ${i.status}">${i.status}</span></td><td>${i.weight}</td><td>` +
      (ev ? `<span class="cite">p.${ev.page}</span> ${esc(ev.quote)}` : `<span class="muted">${esc(i.advice)}</span>`) + "</td></tr>";
  }
  $("tab-repro").innerHTML = h + "</tbody></table>";
}

function renderGaps(a) {
  if (!a.gaps.length) { $("tab-gaps").innerHTML = "<p>No evidence gaps detected by the current rules.</p>"; return; }
  let h = `<h3>${a.gaps.length} candidate evidence gaps</h3><table><thead><tr><th>Severity</th><th>Type</th><th>Detail</th><th>Page</th></tr></thead><tbody>`;
  for (const g of a.gaps) {
    h += `<tr><td><span class="pill ${g.severity}">${g.severity}</span></td><td>${esc(g.kind.replace(/_/g, " "))}</td><td>${esc(g.message)}` +
      (g.quote ? `<blockquote>${esc(g.quote)}</blockquote>` : "") + `</td><td>${g.page ?? "—"}</td></tr>`;
  }
  $("tab-gaps").innerHTML = h + "</tbody></table>";
}

async function renderCompareTab() {
  await loadRecent();
  const opts = recent.filter((r) => r.id !== cur.id).map((r) => `<option value="${esc(r.id)}">${esc(r.name || r.title)}</option>`).join("");
  $("tab-compare").innerHTML = `<h3>Compare with another analysed paper</h3><p class="muted">Upload a second PDF on the home panel first, or pick one analysed earlier.</p>
    <p><select id="cmp-b">${opts}</select> <button id="cmp-go">Compare</button> <span id="cmp-status" class="muted"></span></p><div id="cmp-out"></div>`;
  $("cmp-go").onclick = async () => {
    const b = $("cmp-b").value; if (!b) { $("cmp-status").textContent = "No other paper analysed yet."; return; }
    try { renderCompare(await api("/api/compare", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({a: cur.id, b})})); }
    catch (e) { $("cmp-status").textContent = e.message; }
  };
}
function renderCompare(c) {
  const col = (p, n) => `<div><h4>Paper ${n}</h4><div>${esc(p.title)}</div><div class="muted">${p.pages} pages · ${p.n_claims} claims</div>
    <div>Reproducibility <strong>${p.repro_score}</strong></div><div>Evidence score <strong>${p.evidence_score ?? "n/a"}</strong></div><div>High-severity gaps <strong>${p.high_gaps}</strong></div></div>`;
  let h = `<div class="grid2">${col(c.a, "A")}${col(c.b, "B")}</div><h4>Verdict</h4><ul>${c.verdict.map((v) => `<li>${esc(v)}</li>`).join("")}</ul>`;
  h += `<p class="muted">Datasets shared: ${esc(c.datasets.shared.join(", ") || "none")} · only A: ${esc(c.datasets.only_a.join(", ") || "—")} · only B: ${esc(c.datasets.only_b.join(", ") || "—")}</p>`;
  h += `<h4>Aligned claims</h4>` + (c.aligned_claims.length ? "<table><thead><tr><th>A</th><th>B</th><th>Note</th></tr></thead><tbody>" +
    c.aligned_claims.map((x) => `<tr><td>${esc(x.a.text)} <span class="pill ${x.a.support}">${x.a.support}</span></td><td>${esc(x.b.text)} <span class="pill ${x.b.support}">${x.b.support}</span></td><td>${esc(x.note)}</td></tr>`).join("") + "</tbody></table>" : "<p class='muted'>No similar claims found.</p>");
  h += `<h4>Reproducibility differences</h4><table><thead><tr><th>Item</th><th>A</th><th>B</th></tr></thead><tbody>` +
    c.rubric.filter((r) => r.differs).map((r) => `<tr><td>${esc(r.label)}</td><td><span class="pill ${r.a}">${r.a}</span></td><td><span class="pill ${r.b}">${r.b}</span></td></tr>`).join("") + "</tbody></table>";
  h += `<p class="cite">${esc(c.caveat)}</p>`;
  $("cmp-out").innerHTML = h;
}

$("file").onchange = (e) => upload(e.target.files[0]);
const drop = $("drop");
["dragover", "dragenter"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => upload(e.dataTransfer.files[0]));
drop.onclick = () => $("file").click();
$("demo").onclick = async () => {
  status("Generating demo papers …");
  try { const d = await api("/api/demo", {method: "POST"}); show(await api("/api/analyses/" + d.a)); status("Demo loaded: use Compare to contrast with the overclaiming demo."); await loadRecent(); }
  catch (e) { status(e.message, true); }
};
loadRecent();
