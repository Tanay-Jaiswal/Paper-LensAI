"""Markdown and standalone-HTML renderers for an Analysis."""
from __future__ import annotations

import html

from .claims import coverage_text
from .pipeline import Analysis

BADGE = {"strong": "🟢 strong", "moderate": "🟡 moderate", "weak": "🟠 weak", "none": "🔴 none"}


def to_markdown(a: Analysis) -> str:
    d = a.to_dict()
    out = [f"# PaperLens report: {a.doc.title}", "",
           f"*{a.doc.n_pages} pages · {len(a.claims)} claims · reproducibility {a.rubric['score']}/100 ({a.rubric['band']})*", ""]
    if a.doc.warnings:
        out += ["> **Warnings:** " + " ".join(a.doc.warnings), ""]
    out += ["## Summary", ""]
    for t in a.summary.get("tldr", []):
        out.append(f"- {t['text']} *(p.{t['page']})*")
    for facet, items in a.summary.get("facets", {}).items():
        if items:
            out += ["", f"**{facet.capitalize()}**"] + [f"- {i['text']} *(p.{i['page']})*" for i in items]
    out += ["", "## Research Evidence Ledger", "",
            "| ID | Claim | Page | Type | Support | Best evidence |", "|---|---|---|---|---|---|"]
    for c in a.claims:
        ev = c.evidence[0] if c.evidence else None
        evs = f"p.{ev.page}: {ev.quote[:90]}…" if ev else (c.evidence_note or "No supporting evidence found")
        cov = coverage_text(c.quantity_coverage) if ev else ""
        if cov and c.quantity_coverage["missing"]:
            evs += f" ({cov})"
        out.append(f"| {c.id} | {c.text} | {c.page} | {c.claim_type} | {BADGE[c.support]} | {evs} |".replace("\n", " "))
    out += ["", f"## Reproducibility: {a.rubric['score']}/100", "", f"_{a.rubric['formula']}_", "",
            "| Item | Status | Weight | Evidence |", "|---|---|---|---|"]
    for i in a.rubric["items"]:
        ev = i["evidence"][0] if i["evidence"] else None
        out.append(f"| {i['label']} | {i['status']} | {i['weight']} | " +
                   (f"p.{ev['page']}: {ev['quote'][:80]}…" if ev else i["advice"]) + " |")
    out += ["", f"_{a.rubric['disclaimer']}_", "", "## Evidence gaps", ""]
    if not a.gaps:
        out.append("No gaps detected by the current rules.")
    for g in a.gaps:
        loc = f" (p.{g.page})" if g.page else ""
        out.append(f"- **[{g.severity.upper()}] {g.kind}**{loc}: {g.message}" + (f' — "{g.quote}"' if g.quote else ""))
    return "\n".join(out) + "\n"


_CSS = ("body{font:15px/1.5 system-ui,Segoe UI,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#16202a}"
        "h1{font-size:22px}h2{font-size:18px;margin-top:2rem;border-bottom:1px solid #e2e6ea;padding-bottom:4px}"
        "table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;vertical-align:top;"
        "padding:6px 8px;border-bottom:1px solid #e2e6ea}.m{color:#5d6b7a;font-size:13px}"
        ".w{background:#fff6d6;border:1px solid #a67c00;border-radius:6px;padding:8px 12px;margin:8px 0}"
        ".p{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;color:#fff;white-space:nowrap}"
        ".strong,.present,.low{background:#1a7f4b}.moderate,.partial,.medium{background:#a67c00}.weak{background:#c4620d}"
        ".none,.missing,.high{background:#b3261e}.not_applicable{background:#5d6b7a}")


def to_html(a: Analysis) -> str:
    """Standalone HTML report (no scripts, no external files); the same content as the Markdown report."""
    e = html.escape

    def pill(k: str) -> str:
        return f"<span class='p {e(k)}'>{e(k.replace('_', ' '))}</span>"

    out = ["<!doctype html><html lang=en><meta charset=utf-8>", f"<title>PaperLens report: {e(a.doc.title)}</title>",
           f"<style>{_CSS}</style><body>", f"<h1>PaperLens report: {e(a.doc.title)}</h1>",
           f"<p class=m>{a.doc.n_pages} pages · {len(a.claims)} claims · reproducibility checklist "
           f"{a.rubric['score']}/100 ({e(a.rubric['band'])}) · {len(a.gaps)} candidate evidence gaps</p>"]
    out += [f"<div class=w>{e(w)}</div>" for w in a.doc.warnings]
    out.append("<h2>Summary</h2><ul>")
    out += [f"<li>{e(t['text'])} <span class=m>p.{t['page']}</span></li>" for t in a.summary.get("tldr", [])]
    out.append("</ul>")
    for facet, items in a.summary.get("facets", {}).items():
        if items:
            out.append(f"<p><b>{e(facet.capitalize())}</b></p><ul>" +
                       "".join(f"<li>{e(i['text'])} <span class=m>p.{i['page']}</span></li>" for i in items) + "</ul>")
    out.append("<h2>Research Evidence Ledger</h2><table><tr><th>ID</th><th>Claim</th><th>Support</th><th>Evidence</th></tr>")
    for c in a.claims:
        if c.evidence:
            ev = "".join(f"<div><span class=m>p.{x.page}, {e(x.section)}, score {x.score}</span><br>{e(x.quote)}</div>"
                         for x in c.evidence)
            cov = coverage_text(c.quantity_coverage)
            if cov:
                ev += f"<div class=m>{e(cov)}</div>"
        else:
            ev = f"<b>{e(c.evidence_note or 'No supporting evidence found')}</b>"
        out.append(f"<tr><td>{e(c.id)}</td><td>{e(c.text)}<div class=m>p.{c.page}, {e(c.section)}, {e(c.claim_type)}"
                   f"{', hedged' if c.hedged else ''}</div></td><td>{pill(c.support)}</td><td>{ev}</td></tr>")
    out.append(f"</table><h2>Reproducibility checklist: {a.rubric['score']}/100 ({e(a.rubric['band'])})</h2>"
               f"<p class=w>{e(a.rubric['disclaimer'])}</p><p class=m>{e(a.rubric['formula'])}</p>"
               "<table><tr><th>Item</th><th>Status</th><th>Weight</th><th>Evidence in paper / advice</th></tr>")
    for i in a.rubric["items"]:
        ev = i["evidence"][0] if i["evidence"] else None
        out.append(f"<tr><td>{e(i['label'])}</td><td>{pill(i['status'])}</td><td>{i['weight']}</td><td>" +
                   (f"<span class=m>p.{ev['page']}</span> {e(ev['quote'])}" if ev else f"<span class=m>{e(i['advice'])}</span>") +
                   "</td></tr>")
    out.append("</table><h2>Evidence gaps (candidates for a reviewer)</h2>")
    if not a.gaps:
        out.append("<p>No gaps detected by the current rules.</p>")
    else:
        out.append("<table><tr><th>Severity</th><th>Type</th><th>Detail</th><th>Page</th></tr>")
        for g in a.gaps:
            out.append(f"<tr><td>{pill(g.severity)}</td><td>{e(g.kind.replace('_', ' '))}</td><td>{e(g.message)}" +
                       (f"<div class=m>“{e(g.quote)}”</div>" if g.quote else "") + f"</td><td>{g.page or '—'}</td></tr>")
        out.append("</table>")
    out.append("<p class=m>Generated by PaperLens AI. Ratings are lexical and numeric heuristics for a human reviewer, "
               "not verdicts; check every quote against the cited page.</p></body></html>")
    return "\n".join(out)
