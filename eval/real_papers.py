"""Run PaperLens on a folder of REAL PDFs and write a human-audit sheet plus automatic traceability checks.

    python -m eval.real_papers data/Papers eval/results

Writes:
  real_papers_summary.json   per-paper parsing diagnostics (pages, sections, tables, claims, support, warnings, errors)
  real_papers_audit.csv      one row per extracted claim, same label columns as eval/audit.py (score it with
                             `python -m eval.audit score eval/results/real_papers_audit.csv`) plus two automatic columns

The two automatic columns need no human judgement: they re-open the PDF with PyMuPDF and test whether the claim text /
top evidence quote really occurs on the page PaperLens cites (comparison on letters and digits only, so line breaks and
hyphenation do not matter). They check page references and verbatim quoting, NOT whether a sentence is a real claim or
whether the evidence supports it. Those two columns (is_real_claim, evidence_correct) are left blank for a person.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import traceback
import unicodedata
from collections import Counter
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paperlens.pipeline import analyze_pdf  # noqa: E402


def _alnum(s: str) -> str:
    # NFKC first so PDF ligatures (ﬁ, ﬂ) compare equal to the plain letters
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", s).lower())


def on_page(pages: list[str], page: int, text: str) -> str:
    """y = on the cited page, other = only on a different page, n = nowhere in the PDF text layer."""
    if text.startswith("Table row:"):
        # table rows are re-assembled from cells, so test each cell token instead of the whole string
        cells = [c for c in map(_alnum, text[len("Table row:"):].split()) if c]
        if not cells:
            return ""
        hit = lambda p: all(c in p for c in cells)  # noqa: E731
        if 1 <= page <= len(pages) and hit(pages[page - 1]):
            return "y"
        return "other" if any(hit(p) for p in pages) else "n"
    t = _alnum(text)
    if not t:
        return ""
    if 1 <= page <= len(pages) and t in pages[page - 1]:
        return "y"
    return "other" if any(t in p for p in pages) else "n"


def run(folder: str, out_dir: str):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    rows, summary = [], []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        rec: dict = {"paper": pdf.name}
        summary.append(rec)
        t0 = time.perf_counter()
        try:
            a = analyze_pdf(pdf)
        except Exception as e:  # a crash on a real paper is a result, record it
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback"] = traceback.format_exc().splitlines()[-6:]
            continue
        rec["seconds"] = round(time.perf_counter() - t0, 2)
        with pymupdf.open(pdf) as d:
            pages = [_alnum(p.get_text()) for p in d]
        doc = a.doc
        sec = Counter(s.section for s in doc.sentences)
        claim_chk = [on_page(pages, c.page, c.text) for c in a.claims]
        ev_chk = [on_page(pages, c.evidence[0].page, c.evidence[0].quote) if c.evidence else "" for c in a.claims]
        rec.update({
            "title_extracted": doc.title, "pages_paperlens": doc.n_pages, "pages_pymupdf": len(pages),
            "warnings": doc.warnings, "n_sentences": len(doc.sentences),
            "sections": dict(sec.most_common()),
            "headings": list(dict.fromkeys(s.heading for s in doc.sentences if s.heading))[:60],
            "kinds": dict(Counter(s.kind for s in doc.sentences)),
            "pages_with_no_sentences": [i + 1 for i in range(len(pages)) if i + 1 not in {s.page for s in doc.sentences}],
            "n_claims": len(a.claims),
            "claim_sections": dict(Counter(c.section for c in a.claims)),
            "support": dict(Counter(c.support for c in a.claims)),
            "evidence_status": dict(Counter(getattr(c, "evidence_status", "") or "n/a" for c in a.claims)),
            "rejected_candidates": dict(sum((Counter(getattr(c, "rejected", {})) for c in a.claims), Counter())),
            "claim_text_on_cited_page": dict(Counter(claim_chk)),
            "evidence_quote_on_cited_page": dict(Counter(x for x in ev_chk if x)),
            "reproducibility_score": a.rubric.get("score"),
            "rubric_not_applicable": a.rubric.get("not_applicable", []),
            "n_gaps": len(a.gaps), "gap_kinds": dict(Counter(g.kind for g in a.gaps)),
            "datasets": a.datasets, "metrics": a.metrics,
        })
        for c, cc, ec in zip(a.claims, claim_chk, ev_chk):
            ev = c.evidence[0] if c.evidence else None
            rows.append({"paper": pdf.name, "claim_id": c.id, "claim": c.text, "claim_page": c.page, "claim_section": c.section,
                         "type": c.claim_type, "support": c.support,
                         "evidence_status": getattr(c, "evidence_status", ""),
                         "evidence_page": ev.page if ev else "", "evidence_section": ev.section if ev else "",
                         "evidence": ev.quote if ev else "",
                         "auto_claim_on_cited_page": cc, "auto_evidence_on_cited_page": ec,
                         "is_real_claim": "", "evidence_correct": ""})
        print(f"{pdf.name[:48]:48} {rec['seconds']:6.1f}s pages={doc.n_pages:3} sents={len(doc.sentences):5} "
              f"claims={len(a.claims):3} support={rec['support']}")
    (out / "real_papers_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "real_papers_audit.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["paper"])
        w.writeheader(); w.writerows(rows)
    print(f"{len(summary)} papers, {sum('error' in r for r in summary)} crashed, {len(rows)} claim rows -> {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
    else:
        run(sys.argv[1], sys.argv[2])
