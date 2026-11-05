"""Precision/coverage of the abstention threshold on the DEVELOPMENT papers, using the pooled dev labels.

    python -m eval.dev_threshold_sweep data/Papers eval/results/dev_v0.2

For each MIN_LEXICAL value the linker is re-run and its top passage per real claim is looked up in
dev_pairs_labelled.csv. A passage that was never labelled (it only appears at that threshold) is counted separately
and left out of precision. Development papers only; labels are whatever dev_pairs_labelled.csv contains.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paperlens import claims as C  # noqa: E402
from paperlens.ingest import parse_pdf  # noqa: E402

GRID = [0.0, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


def main(folder: str, out_dir: str):
    out = Path(out_dir)
    lab_claim, lab_pair = {}, {}
    for r in csv.DictReader(open(out / "dev_pairs_labelled.csv", encoding="utf-8-sig")):
        if r["kind"] == "claim":
            lab_claim[(r["paper"], r["claim"])] = r["label"]
        elif r["label"]:
            lab_pair[(r["paper"], r["claim"], r["evidence"])] = r["label"]
    cases = []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        doc = parse_pdf(pdf)
        for c in C.extract_claims(doc):
            if lab_claim.get((pdf.name, c.text)) == "y":
                cases.append((pdf.name, c, C._eligible_evidence(doc, c)))
    rows = []
    for t in GRID:
        ret = y = yp = unl = 0
        for paper, c, pool in cases:
            best, _ = C.select_passages(c.text, c.numbers, pool, 1, t, min(t, C.MIN_LEXICAL_WITH_QUANTITY))
            if not best:
                continue
            ret += 1
            lab = lab_pair.get((paper, c.text, best[0][3].text))
            if lab is None:
                unl += 1
            else:
                y += lab == "y"
                yp += lab in ("y", "p")
        n = ret - unl
        rows.append({"min_lexical": t, "real_claims": len(cases), "returned": ret, "coverage": round(ret / len(cases), 3),
                     "labelled": n, "unlabelled": unl, "strict": round(y / n, 3) if n else None,
                     "lenient": round(yp / n, 3) if n else None, "fully_supported_claims": y})
    (out / "dev_threshold_sweep.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"{'min_lex':>8} {'coverage':>9} {'returned':>9} {'labelled':>9} {'strict':>7} {'lenient':>8} {'full y':>7} {'unlabelled':>11}")
    for r in rows:
        print(f"{r['min_lexical']:>8} {r['coverage']:>9} {r['returned']:>9} {r['labelled']:>9} {r['strict']!s:>7} {r['lenient']!s:>8} {r['fully_supported_claims']:>7} {r['unlabelled']:>11}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
