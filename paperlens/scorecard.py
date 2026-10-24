"""One-page score card: a letter grade, the three most important problems and the fix for each.

The grade summarises how completely the paper *reports* its work and backs its claims; it is not a judgement of the
science. It is computed from four numbers that are already in the full report, with a fixed formula printed on the
card, so anyone can recompute it:

    points = 0.6 x reporting checklist score + 0.4 x evidence score      (checklist score only, if no claim has numbers)
             - 5 for each high-severity evidence gap or number that does not add up (at most 20 off)
    A >= 80, B >= 65, C >= 50, D >= 35, otherwise E

The problems and fixes are the first three items of the revision checklist (already ordered by priority), so the card
adds no finding of its own.
"""
from __future__ import annotations

import html
from datetime import date

from . import __version__
from .pipeline import NOT_ASSESSED, Analysis
from .revisions import revision_checklist

W_REPRO, W_EVIDENCE = 0.6, 0.4
PENALTY, MAX_PENALTY = 5, 20
GRADES = ((80, "A"), (65, "B"), (50, "C"), (35, "D"))
GRADE_TEXT = {"A": "very complete reporting", "B": "mostly complete reporting", "C": "partly complete reporting",
              "D": "many reporting gaps", "E": "most checks not met"}
_SUPPORT_POINTS = {"strong": 1.0, "moderate": 0.6, "weak": 0.25, "none": 0.0}
FORMULA = (f"points = {W_REPRO} x checklist score + {W_EVIDENCE} x evidence score (checklist only if no claim has "
           f"numbers), minus {PENALTY} per high-severity gap or number that does not add up (at most {MAX_PENALTY}); "
           "A >= 80, B >= 65, C >= 50, D >= 35, else E")


def evidence_score(a: Analysis) -> float | None:
    """Mean support of result and comparison claims (strong 1, moderate 0.6, weak 0.25, none 0), as in compare.py."""
    q = [c for c in a.claims if c.claim_type in ("result", "comparison")]
    return round(100 * sum(_SUPPORT_POINTS[c.support] for c in q) / len(q), 1) if q else None


def grade_of(points: float) -> str:
    return next((g for cut, g in GRADES if points >= cut), "E")


def build_scorecard(a: Analysis) -> dict:
    rubric = a.rubric
    repro = rubric["score"]
    ev = evidence_score(a)
    high_gaps = sum(1 for g in a.gaps if g.severity == "high")
    bad_numbers = (a.consistency or {}).get("n_inconsistent", 0)
    penalty = min(MAX_PENALTY, PENALTY * (high_gaps + bad_numbers))
    base = repro if ev is None else W_REPRO * repro + W_EVIDENCE * ev
    points = round(max(0.0, base - penalty), 1)
    assessed = rubric.get("band") != NOT_ASSESSED
    rev = revision_checklist(a)
    top = [{"problem": x["why"], "fix": x["action"], "page": x["page"], "priority": x["priority"],
            "category": x["category"], "source": x["source"], "id": x["id"]} for x in rev[:3]]
    return {
        "title": a.doc.title, "source_name": a.doc.source_name, "pages": a.doc.n_pages,
        "field": (a.mode or {}).get("label", "General"),
        "assessed": assessed,
        "grade": grade_of(points) if assessed else "n/a",
        "grade_text": GRADE_TEXT[grade_of(points)] if assessed else "not graded: too little text could be extracted",
        "points": points if assessed else None,
        "parts": {"checklist_score": repro, "standard_score": rubric.get("standard_score", repro),
                  "evidence_score": ev, "high_severity_gaps": high_gaps, "numbers_not_adding_up": bad_numbers,
                  "penalty": penalty, "n_claims": len(a.claims), "n_revisions": len(rev)},
        "top": top if assessed else [],
        "formula": FORMULA,
        "caveat": ("The grade describes how completely the paper reports its methods and backs its claims with its own "
                   "results, using fixed text rules. It is not a verdict on whether the research is correct or "
                   "reproducible. Check each item against the cited page."),
        "method": "rule-based (no AI model involved)",
        "version": __version__, "date": date.today().isoformat(),
    }


_CSS = """
body{font-family:sans-serif;font-size:10.5pt;color:#1d1f1c;margin:0}
h1{font-size:15pt;margin:0 0 2pt 0}
.m{color:#5c615a;font-size:8.5pt}
.grade{font-size:44pt;font-weight:bold;color:#1f5a4b;text-align:center}
td,th{vertical-align:top;text-align:left;padding:3pt 5pt;border-bottom:0.5pt solid #d8d0bf;font-size:9.5pt}
th{font-size:8pt;color:#5c615a;text-transform:uppercase}
table{border-collapse:collapse;width:100%}
h2{font-size:11pt;margin:10pt 0 3pt 0;border-bottom:1pt solid #1d1f1c}
.box{border:0.8pt solid #b3a98f;padding:5pt}
"""


def to_scorecard_html(a: Analysis, printable: bool = True) -> str:
    """Self-contained one-page HTML (no scripts). With printable=True it opens the print dialog hint and A4 CSS."""
    c = build_scorecard(a)
    e = html.escape
    p = c["parts"]
    ev = "n/a (no claim with numbers)" if p["evidence_score"] is None else f"{p['evidence_score']} / 100"
    rows = "".join(
        f"<tr><td><b>{i}</b></td><td>{e(t['problem'])}<div class=m>{e(t['category'])} · {e(t['priority'])} priority"
        f"{' · p.' + str(t['page']) if t['page'] else ''}</div></td><td>{e(t['fix'])}</td></tr>"
        for i, t in enumerate(c["top"], 1))
    if not rows:
        rows = ("<tr><td colspan=3>" + ("No finding needs a revision." if c["assessed"] else
                                         "Not graded: too little text could be extracted from this PDF.") + "</td></tr>")
    note = ('<p class="m noprint">Use your browser&#39;s Print command (Ctrl+P) and choose "Save as PDF" to keep a copy, '
            'or download the ready-made PDF from PaperLens.</p>' if printable else "")
    print_css = ("@page{size:A4;margin:14mm}@media print{.noprint{display:none}}"
                 "body{max-width:180mm;margin:12mm auto}" if printable else "")
    return f"""<!doctype html><html lang=en><meta charset=utf-8><title>Score card: {e(c['title'])}</title>
<style>{_CSS}{print_css}</style><body>
{note}<p class=m>PaperLens AI score card · {e(c['date'])} · version {e(c['version'])} · {e(c['method'])}</p>
<h1>{e(c['title'])}</h1>
<p class=m>{e(c['source_name'])} · {c['pages']} pages · checks: {e(c['field'])}</p>
<table><tr><td style="width:28%" class=box><div class=grade>{e(c['grade'])}</div>
<div style="text-align:center"><b>Reporting grade</b><br><span class=m>{e(c['grade_text'])}</span>
{'<br><span class=m>' + str(c['points']) + ' points of 100</span>' if c['points'] is not None else ''}</div></td>
<td><table>
<tr><td>Reporting checklist</td><td><b>{p['checklist_score']}</b> / 100{(' (standard 15 items: ' + str(p['standard_score']) + ')') if p['standard_score'] != p['checklist_score'] else ''}</td></tr>
<tr><td>Evidence for numeric claims</td><td><b>{e(ev)}</b></td></tr>
<tr><td>High-severity evidence gaps</td><td><b>{p['high_severity_gaps']}</b></td></tr>
<tr><td>Numbers that do not add up</td><td><b>{p['numbers_not_adding_up']}</b></td></tr>
<tr><td>Claims checked · revisions suggested</td><td>{p['n_claims']} · {p['n_revisions']}</td></tr>
</table></td></tr></table>
<h2>Top 3 problems and the fix for each</h2>
<table><tr><th>#</th><th>Problem</th><th>Fix</th></tr>{rows}</table>
<h2>How the grade is computed</h2>
<p class=m>{e(c['formula'])}. This card: penalty {p['penalty']}.</p>
<p class=m>{e(c['caveat'])}</p>
</body></html>"""


def to_scorecard_pdf(a: Analysis) -> bytes:
    """The same card as a one-page A4 PDF, laid out by PyMuPDF (no extra dependency)."""
    import io

    import pymupdf

    body = to_scorecard_html(a, printable=False)
    story = pymupdf.Story(html=body, user_css=_CSS)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    page_rect = pymupdf.paper_rect("a4")
    where = page_rect + (40, 40, -40, -40)
    more = True
    while more:                     # a long title or long problems can spill onto a second page; never cut text
        dev = writer.begin_page(page_rect)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()
