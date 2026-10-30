"""Fetch the CSE check set: fresh Computer Science papers that PaperLens was never developed on.

    python -m eval.cse_select data/cse_check_papers                     # first check set (2025-03-01, six categories)
    python -m eval.cse_select data/cse_check2_papers second              # second check set, after the fixes

Rule, fixed before any listing was requested: for each arXiv category below, the first paper (oldest first) whose
primary category is that category, submitted on or after the set's start date (SETS), with licence CC BY 4.0 (arXiv OAI-PMH arXivRaw
<license>) and 6 to 40 pages. Nothing is chosen by looking at the content. The papers are used once, to report how the
CSE mode behaves on unseen papers; no rule or threshold is changed after looking at them (see docs/CSE_MODE.md).
"""
from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import pymupdf

from . import held_out_v2_select as sel

SETS = {"first": (["cs.LG", "cs.CV", "cs.CL", "cs.SE", "cs.DC", "cs.CR"], "202503010000"),
        # chosen after the first check and its fixes: other CS areas, a later month, same rule otherwise
        "second": (["cs.AI", "cs.IR", "cs.NI", "cs.RO", "cs.DB", "cs.HC", "cs.LG", "cs.CL"], "202505010000"),
        # a larger reference collection: one paper from each of 16 areas, a later month, same rule
        "third": (["cs.LG", "cs.CV", "cs.CL", "cs.SE", "cs.DC", "cs.CR", "cs.AI", "cs.IR", "cs.NI", "cs.RO", "cs.DB",
                   "cs.HC", "cs.PL", "cs.AR", "cs.SD", "cs.CY"], "202507010000")}
MIN_PAGES, MAX_PAGES = 6, 40


def main(out: str, which: str = "first") -> None:
    categories, start = SETS[which]
    d = Path(out)
    if (d / "MANIFEST.csv").exists():
        sys.exit("MANIFEST.csv exists: the set is fixed, refusing to select again")
    d.mkdir(parents=True, exist_ok=True)
    sel.ARXIV_FROM, sel.ARXIV_TO = start, "202512312359"
    rows = []
    for cat in categories:
        for c in sel.arxiv_candidates(cat):
            try:
                raw = sel.get(c["pdf_urls"][0])
            except RuntimeError as e:
                print(f"  {cat}: skip {c['identifier']} ({e})")
                continue
            if not raw.startswith(b"%PDF"):
                continue
            with pymupdf.open(stream=raw, filetype="pdf") as pdf:
                pages = pdf.page_count
            if not MIN_PAGES <= pages <= MAX_PAGES:
                print(f"  {cat}: skip {c['identifier']} ({pages} pages)")
                continue
            name = f"{c['prefix']}_{sel.slug(c['title'])}.pdf"
            (d / name).write_bytes(raw)
            rows.append({"filename": name, "category": cat, "title": c["title"], "identifier": c["identifier"],
                         "license": c["license"], "license_evidence": c["license_evidence"],
                         "landing_url": c["landing_url"], "submitted": c["submitted"], "pages": pages,
                         "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            print(f"{cat}: {c['identifier']} {c['title'][:70]} ({pages} pages)")
            break
    with open(d / "MANIFEST.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(*sys.argv[1:3])
