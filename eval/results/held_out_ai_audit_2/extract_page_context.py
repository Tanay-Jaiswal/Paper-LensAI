"""Dump, for each row of the blank held-out sheet, the PDF text around the claim and around the evidence.

Reads only the blank sheet and the PDFs (plain PyMuPDF). Does not import paperlens, does not read the key or raw/.
usage: ai_context.py <sheet_csv> <pdf_dir> <out_txt>
"""
import csv, re, sys, unicodedata
from pathlib import Path

import pymupdf

sheet, pdf_dir, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])


def squash(s):
    """letters+digits only, with a map back to original offsets"""
    s = unicodedata.normalize("NFKC", s)
    chars, idx = [], []
    for i, ch in enumerate(s):
        if ch.isascii() and ch.isalnum():
            chars.append(ch.lower()); idx.append(i)
    return s, "".join(chars), idx


def locate(doc, page_no, text, pad):
    """return (status, context) ; status: on-page / other-page N / partial / not-found"""
    if not text.strip():
        return "empty", ""
    if text.startswith("Table row:"):
        cells = [c for c in re.split(r"[;\s]+", text[len("Table row:"):]) if re.search(r"[A-Za-z0-9]", c)]
        if 1 <= page_no <= doc.page_count:
            page_text = doc[page_no - 1].get_text()
            _, sq, _ = squash(page_text)
            hit = sum(squash(c)[1] in sq for c in cells)
            return f"table row: {hit}/{len(cells)} cells on page", ""
        return "bad page", ""
    _, needle, _ = squash(text)
    order = [page_no - 1] + [i for i in range(doc.page_count) if i != page_no - 1]
    for pi in order:
        if not (0 <= pi < doc.page_count):
            continue
        orig, sq, idx = squash(doc[pi].get_text())
        j = sq.find(needle)
        if j >= 0 and needle:
            a, b = idx[j], idx[j + len(needle) - 1] + 1
            ctx = orig[max(0, a - pad):a] + " >>> " + orig[a:b] + " <<< " + orig[b:b + pad]
            return ("on cited page" if pi == page_no - 1 else f"NOT on cited page; found on page {pi + 1}"), re.sub(r"\s+", " ", ctx)
    # partial: first 40 squashed chars
    if 0 <= page_no - 1 < doc.page_count:
        orig, sq, idx = squash(doc[page_no - 1].get_text())
        j = sq.find(needle[:40])
        if j >= 0:
            a = idx[j]
            return "only the start matches on cited page", re.sub(r"\s+", " ", orig[max(0, a - pad):a] + " >>> " + orig[a:a + len(text) + pad])
    return "NOT FOUND in PDF text", ""


rows = list(csv.DictReader(open(sheet, encoding="utf-8-sig")))
docs = {}
lines = []
for r in rows:
    doc = docs.setdefault(r["paper_file"], pymupdf.open(pdf_dir / r["paper_file"]))
    cs, cc = locate(doc, int(r["claim_page"]), r["claim"], 450)
    lines.append(f"\n===== ROW {r['row']} | {r['paper_id']} | {r['claim_id']} | claim page {r['claim_page']} | evidence page {r['evidence_page'] or '-'}")
    lines.append(f"CLAIM: {r['claim']}")
    lines.append(f"CLAIM CHECK: {cs}")
    if cc:
        lines.append(f"CLAIM CONTEXT: {cc}")
    if r["evidence"].strip():
        es, ec = locate(doc, int(r["evidence_page"]), r["evidence"], 450)
        lines.append(f"EVIDENCE: {r['evidence']}")
        lines.append(f"EVIDENCE CHECK: {es}")
        if ec:
            lines.append(f"EVIDENCE CONTEXT: {ec}")
    else:
        lines.append("EVIDENCE: (none shown)")
out.write_text("\n".join(lines), encoding="utf-8")
print(len(rows), "rows ->", out)
