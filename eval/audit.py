"""Human-audit protocol for REAL papers (the check that matters most for the final report).

    python -m eval.audit make  data/papers  eval/results/audit.csv     # run pipeline, write a sheet
    # open audit.csv, fill the two blank columns for every row (y / n / p for partial), save
    python -m eval.audit score eval/results/audit.csv                  # precision numbers

Columns to fill:
  is_real_claim      y if the sentence is a genuine headline claim of the paper
  evidence_correct   y if the top-ranked evidence passage really supports that claim,
                     p if it is related but incomplete, n if wrong; leave blank if the claim has no evidence listed
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paperlens.pipeline import analyze_pdf  # noqa: E402


def make(folder: str, out: str):
    rows = []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        a = analyze_pdf(pdf)
        for c in a.claims:
            ev = c.evidence[0] if c.evidence else None
            rows.append({"paper": pdf.name, "claim_id": c.id, "claim": c.text, "claim_page": c.page,
                         "type": c.claim_type, "support": c.support,
                         "evidence_page": ev.page if ev else "", "evidence": ev.quote if ev else "",
                         "is_real_claim": "", "evidence_correct": ""})
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["paper"])
        w.writeheader(); w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


def score(path: str):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    lab = [r for r in rows if r["is_real_claim"].strip()]
    real = [r for r in lab if r["is_real_claim"].strip().lower() == "y"]
    ev = [r for r in real if r["evidence_correct"].strip() and r["support"] != "none"]
    ok = [r for r in ev if r["evidence_correct"].strip().lower() == "y"]
    part = [r for r in ev if r["evidence_correct"].strip().lower() == "p"]
    out = {"rows_labelled": len(lab),
           "claim_precision": round(len(real) / len(lab), 3) if lab else None,
           "evidence_precision_strict": round(len(ok) / len(ev), 3) if ev else None,
           "evidence_precision_lenient": round((len(ok) + len(part)) / len(ev), 3) if ev else None}
    for lvl in ("strong", "moderate", "weak"):
        sub = [r for r in ev if r["support"] == lvl]
        if sub:
            out[f"evidence_precision_{lvl}"] = round(sum(r["evidence_correct"].strip().lower() == "y" for r in sub) / len(sub), 3)
    print(out)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "make":
        make(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "score":
        score(sys.argv[2])
    else:
        print(__doc__)
