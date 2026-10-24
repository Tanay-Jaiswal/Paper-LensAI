"""Find a claim and its evidence on the original PDF page, and mark them there.

`locate` says where a sentence is on its page and how it was found: "exact" (the start of the sentence matched the
page's own text layer), "partial" (only some runs of its words matched, so the box may cover part of the sentence) or
"none" (the wording could not be found, for example in a table rebuilt from cells; the page number is still its
citation). `highlighted_pdf` returns a copy of the paper with the claim and its evidence highlighted and labelled,
for opening in any PDF viewer.
"""
from __future__ import annotations

import pymupdf

# claim, then evidence 1, 2, 3 (yellow, blue, green, as in the page images)
COLORS = [(1, 0.85, 0.2), (0.4, 0.8, 1), (0.6, 1, 0.5), (1, 0.6, 0.8)]


def locate(pg, text: str, kind: str = "text") -> tuple[list, str]:
    """(rectangles, method) for one sentence on one page. The extracted text can differ from the page's own text layer
    (a ligature that became 'fi ', a hyphenated line end, a table row rebuilt from cells), so after the full-sentence
    search the last cell of a table row, then the first and last words and other short runs of words, are tried; the
    first search that finds something wins."""
    rects = pg.search_for(text[:110]) or pg.search_for(text[:50])
    if rects:
        return rects, "exact"
    if kind == "table":
        rects = pg.search_for(text.rsplit(":", 1)[-1].strip())
        if rects:
            return rects, "partial"
    w = text.split()
    if len(w) >= 8:
        runs = [w[:5], w[-5:]] + [w[i:i + 5] for i in range(5, len(w) - 5, 5)]
        for run in runs:
            rects = pg.search_for(" ".join(run))
            if rects:
                return rects, "partial"
    return [], "none"


def locate_sentences(pdf_path, sentences) -> list[dict]:
    """[{sentence_id, page, method, rects: [[x0, y0, x1, y1] as fractions of the page]}] for the given sentences."""
    out = []
    with pymupdf.open(pdf_path) as pdf:
        for s in sentences:
            if not 1 <= s.page <= len(pdf):
                out.append({"sentence_id": s.id, "page": s.page, "method": "none", "rects": []})
                continue
            pg = pdf[s.page - 1]
            w, h = pg.rect.width, pg.rect.height
            rects, method = locate(pg, s.text, s.kind)
            out.append({"sentence_id": s.id, "page": s.page, "method": method,
                        "rects": [[round(r.x0 / w, 4), round(r.y0 / h, 4), round(r.x1 / w, 4), round(r.y1 / h, 4)]
                                  for r in rects[:20]]})
    return out


def highlighted_pdf(pdf_path, analysis, claim_id: str) -> tuple[bytes, int, dict]:
    """(PDF bytes, the claim's page, {sentence_id: method}) with the claim and its evidence highlighted.

    Each highlight carries a note ("Claim C3 ..." / "Evidence 1 for C3, support strong ...") that PDF viewers show on
    hover or click. Raises KeyError for an unknown claim id."""
    claim = next((c for c in analysis.claims if c.id == claim_id), None)
    if claim is None:
        raise KeyError(claim_id)
    by_id = {s.id: s for s in analysis.doc.sentences}
    marks = [(claim.sentence_id, f"Claim {claim.id} (support: {claim.support}). Rated by PaperLens rules.")]
    marks += [(e.sentence_id, f"Evidence {i} for claim {claim.id}, match score {e.score}"
                              + (f"; shares {', '.join(e.shared_numbers)}" if e.shared_numbers else ""))
              for i, e in enumerate(claim.evidence, 1)]
    found: dict[int, str] = {}
    with pymupdf.open(pdf_path) as pdf:
        for n, (sid, note) in enumerate(marks):
            s = by_id.get(sid)
            if s is None or not 1 <= s.page <= len(pdf):
                continue
            pg = pdf[s.page - 1]
            rects, method = locate(pg, s.text, s.kind)
            found[sid] = method
            for k, r in enumerate(rects):
                a = pg.add_highlight_annot(r)
                a.set_colors(stroke=COLORS[min(n, len(COLORS) - 1)])
                if k == 0:
                    a.set_info(title="PaperLens", content=note)
                a.update()
        data = pdf.tobytes(garbage=0)
    return data, claim.page, found
