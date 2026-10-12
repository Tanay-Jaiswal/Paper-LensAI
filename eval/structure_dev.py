"""Development benchmark for abstract and section-heading detection (DEVELOPMENT papers only).

    python -m eval.structure_dev data/Papers eval/dev_structure_labels.json <out_dir>

Two measures, neither of them a held-out result (the parser was tuned on these papers):

  abstract   For each paper in the label file: does the detected abstract start with the labelled first words and
             end with the labelled last words (letters and digits only; a trailing footnote number is allowed)?
             The labels are AI-assisted (see the file).
  headings   For each PDF that carries bookmarks (an outline written by its authors, so no labelling is involved):
             recall    = share of bookmark entries found as a detected heading on the same page (+-1),
             precision = share of detected headings, on the pages the bookmarks cover, that are bookmark entries.
             A detected heading is one that owns at least one sentence, so a parent heading followed directly by a
             sub-heading counts as missed for every version alike. Run-in sub-headings that authors leave out of the
             bookmarks lower precision without being errors.

Set PAPERLENS_SRC to a folder holding another copy of the `paperlens` package to score that version instead
(used to score the previous commit: `git archive <commit> paperlens | tar -x -C <folder>`).
Writes <out_dir>/structure_dev.json and prints one line per paper. Do not point this at held-out papers.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf

sys.path.insert(0, os.environ.get("PAPERLENS_SRC") or str(Path(__file__).resolve().parent.parent))
from paperlens.ingest import parse_pdf  # noqa: E402

_NUM = re.compile(r"^((?:\d{1,2}(?:\.\d{1,2})*)|[A-Z](?:\.\d{1,2})*)\.?\s+(?=\S)")


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", s).lower())


def _number(title: str) -> str:
    m = _NUM.match(title.strip())
    return m.group(1) if m else ""


def _same_heading(outline: str, detected: str) -> bool:
    a, b = _alnum(_NUM.sub("", outline.strip())), _alnum(_NUM.sub("", detected.strip()))
    na, nb = _number(outline), _number(detected)
    if na and nb:
        return na == nb
    return len(a) >= 4 and len(b) >= 4 and (a == b or a in b or b in a)


def abstract_row(doc, label: dict) -> dict:
    sents = [s for s in doc.sentences if s.section == "abstract" and s.kind == "text"]
    text = _alnum(" ".join(s.text for s in sents))
    start, end = _alnum(label["start"]), _alnum(label["end"])
    return {"n_sentences": len(sents), "pages": sorted({s.page for s in sents}),
            "start_ok": bool(text) and text.startswith(start), "end_ok": bool(re.search(re.escape(end) + r"\d{0,2}$", text)),   # a footnote mark may follow
            "contains_start": start in text, "contains_end": end in text}


def heading_row(doc, toc: list) -> dict:
    pages = [pg for _, _, pg in toc]
    lo, hi = min(pages), max(pages)
    seen: dict[tuple[str, int], None] = {}
    for s in doc.sentences:
        if s.heading and s.section != "references" and lo - 1 <= s.page <= hi + 1:
            seen.setdefault((s.heading, s.page), None)
    detected = list({h for h, _ in seen})                       # a heading continued on the next page counts once
    first_page = {h: min(p for hh, p in seen if hh == h) for h in detected}
    found = [any(_same_heading(t, h) and abs(first_page[h] - pg) <= 1 for h in detected) for _, t, pg in toc]
    matched = [any(_same_heading(t, h) and abs(first_page[h] - pg) <= 1 for _, t, pg in toc) for h in detected]
    return {"bookmarks": len(toc), "found": sum(found), "detected": len(detected), "detected_in_bookmarks": sum(matched),
            "missed": [t for (_, t, _), ok in zip(toc, found) if not ok][:40],
            "extra": [h for h, ok in zip(detected, matched) if not ok][:40]}


def run(folder: str, labels_path: str, out_dir: str) -> dict:
    labels = json.loads(Path(labels_path).read_text(encoding="utf-8"))["abstracts"]
    out = {"abstract": {}, "headings": {}}
    for pdf in sorted(Path(folder).glob("*.pdf")):
        doc = parse_pdf(pdf)
        if pdf.name in labels:
            out["abstract"][pdf.name] = r = abstract_row(doc, labels[pdf.name])
            r["abstract_warning"] = [w for w in doc.warnings if "bstract" in w]
            print(f"abstract  {pdf.name[:44]:44} start={'ok ' if r['start_ok'] else 'NO '} end={'ok ' if r['end_ok'] else 'NO '}"
                  f" n={r['n_sentences']:3} pages={r['pages']}")
        with pymupdf.open(pdf) as d:
            toc = [(lv, t, pg) for lv, t, pg in d.get_toc() if t.strip()]
        if len(toc) >= 5:
            out["headings"][pdf.name] = h = heading_row(doc, toc)
            print(f"headings  {pdf.name[:44]:44} recall={h['found']}/{h['bookmarks']} "
                  f"precision={h['detected_in_bookmarks']}/{h['detected']}")
    a = out["abstract"].values()
    hd = out["headings"].values()
    out["totals"] = {
        "papers": len(a),
        "abstract_start_ok": sum(r["start_ok"] for r in a), "abstract_end_ok": sum(r["end_ok"] for r in a),
        "abstract_both_ok": sum(r["start_ok"] and r["end_ok"] for r in a),
        "papers_with_bookmarks": len(hd),
        "bookmarks": sum(r["bookmarks"] for r in hd), "bookmarks_found": sum(r["found"] for r in hd),
        "headings_detected": sum(r["detected"] for r in hd),
        "headings_detected_in_bookmarks": sum(r["detected_in_bookmarks"] for r in hd),
    }
    t = out["totals"]
    print(f"TOTAL abstract: start {t['abstract_start_ok']}/{t['papers']}, end {t['abstract_end_ok']}/{t['papers']}, "
          f"both {t['abstract_both_ok']}/{t['papers']}")
    print(f"TOTAL headings ({t['papers_with_bookmarks']} papers with bookmarks): recall {t['bookmarks_found']}/{t['bookmarks']}, "
          f"precision {t['headings_detected_in_bookmarks']}/{t['headings_detected']}")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "structure_dev.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
    else:
        run(*sys.argv[1:])
