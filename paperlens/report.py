"""Markdown and standalone-HTML renderers for an Analysis."""
from __future__ import annotations

import html

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
        evs = f"p.{ev.page}: {ev.quote[:90]}…" if ev and c.support != "none" else "—"
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


def to_html(a: Analysis) -> str:
    md = html.escape(to_markdown(a))
    return ("<!doctype html><meta charset=utf-8><title>PaperLens report</title>"
            "<body style='font:14px/1.5 system-ui;max-width:960px;margin:2rem auto;padding:0 1rem'>"
            f"<pre style='white-space:pre-wrap'>{md}</pre></body>")
