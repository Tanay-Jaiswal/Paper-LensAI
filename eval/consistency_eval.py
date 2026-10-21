"""Run the Numeric Consistency Audit over folders of real PDFs and write every check to a CSV for review.

    python -m eval.consistency_eval ../data/Papers ../data/held_out_papers ../data/held_out_v0.2_papers \
        --out eval/results/consistency_v1

Writes checks.csv (one row per recomputed statement, with an empty `review` column for a person to fill in)
and summary.json (counts per folder and per kind). It measures nothing by itself: the review column is the label.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from paperlens.consistency import audit
from paperlens.ingest import parse_pdf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("folders", nargs="+")
    ap.add_argument("--out", default="eval/results/consistency_v1")
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows, summary = [], {"folders": {}, "kinds": Counter(), "status": Counter()}
    for folder in args.folders:
        papers = sorted(Path(folder).glob("*.pdf"))
        f = summary["folders"][Path(folder).name] = {"papers": len(papers), "papers_with_checks": 0, "checks": 0,
                                                     "consistent": 0, "inconsistent": 0, "not_reproduced": 0}
        for pdf in papers:
            rep = audit(parse_pdf(pdf))
            f["papers_with_checks"] += bool(rep["checks"])
            for c in rep["checks"]:
                f["checks"] += 1
                f[c["status"]] += 1
                summary["kinds"][c["kind"]] += 1
                summary["status"][c["status"]] += 1
                rows.append({"folder": Path(folder).name, "paper": pdf.name, "id": c["id"], "status": c["status"],
                             "severity": c["severity"], "kind": c["kind"], "page": c["page"], "formula": c["formula"],
                             "stated": c["stated"], "quote": c["quote"], "review": ""})
    with (out / "checks.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["folder"])
        w.writeheader()
        w.writerows(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
