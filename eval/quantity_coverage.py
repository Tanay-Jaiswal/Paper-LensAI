"""Quantity coverage of compound claims on a folder of development PDFs (automatic; no labels are written).

    python -m eval.quantity_coverage data/Papers eval/results/dev_v0.3 [dev_pairs_labelled.csv]

For every extracted claim that cites figures (claims.quantity_coverage) it reports how many of them are matched by
  - the top passage alone,
  - the first three accepted passages in rank order (the 0.2.0-dev selection),
  - the three passages chosen by claims._complementary (the current selection).
With a labelled development sheet (eval/dev_pairs.py) it also cross-tabulates the label of the TOP passage against
whether the top passage / the returned set covers every claimed figure. The labels describe the top passage only:
nobody has judged whether a set of passages supports a claim, so set coverage is a count of matched figures, not
evidence precision. Development papers only; never run this on a held-out folder.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paperlens import claims as C  # noqa: E402
from paperlens.pipeline import analyze_pdf  # noqa: E402


def run(folder: str, out_dir: str, labelled: str | None = None):
    lab = {}
    if labelled:
        for r in csv.DictReader(open(labelled, encoding="utf-8-sig")):
            lab[(r["kind"], r["id"])] = r["label"].strip().lower()
    h = lambda *xs: hashlib.sha1("|".join(xs).encode("utf-8")).hexdigest()[:10]  # noqa: E731
    rows, tot = [], Counter()
    cross = {"top_covers_all": Counter(), "top_misses_some": Counter(), "set_covers_all": Counter(),
             "set_misses_some": Counter(), "no_figures": Counter()}
    for pdf in sorted(Path(folder).glob("*.pdf")):
        a = analyze_pdf(pdf)
        claim_sentences = frozenset(c.sentence_id for c in a.claims)
        for c in a.claims:
            if not c.evidence:
                continue
            pool = C._eligible_evidence(a.doc, c, claim_sentences)
            accepted, _ = C.select_passages(c.text, c.numbers, pool, k=10 ** 6)   # every accepted passage, by rank
            # k above the number of accepted passages returns them in complementary order; restore rank order
            ranked = sorted(accepted, key=lambda x: (x[3].section in C.CLAIM_ZONE, -x[0]))
            old = C.quantity_coverage(c.text, c.numbers, [x[2] for x in ranked[:3]])
            new = c.quantity_coverage
            label = lab.get(("pair", h(pdf.name, c.text, c.evidence[0].quote)), "") if lab.get(("claim", h(pdf.name, c.text))) == "y" else ""
            n = len(new["claimed"])
            if not n:
                cross["no_figures"][label] += 1
                continue
            tot["claims_with_figures"] += 1
            tot["figures_claimed"] += n
            tot["figures_top"] += len(new["top"])
            tot["figures_rank_order_set"] += len(old["found"])
            tot["figures_complementary_set"] += len(new["found"])
            tot["claims_fully_covered_by_top"] += len(new["top"]) == n
            tot["claims_fully_covered_rank_order_set"] += len(old["found"]) == n
            tot["claims_fully_covered_complementary_set"] += not new["missing"]
            tot["claims_top_matches_nothing"] += not new["top"]
            cross["top_covers_all" if len(new["top"]) == n else "top_misses_some"][label] += 1
            cross["set_covers_all" if not new["missing"] else "set_misses_some"][label] += 1
            rows.append({"paper": pdf.name, "claim_id": c.id, "support": c.support, "top_label": label,
                         "claimed": " ".join(new["claimed"]), "top": " ".join(new["top"]),
                         "rank_order_set": " ".join(old["found"]), "complementary_set": " ".join(new["found"]),
                         "missing": " ".join(new["missing"])})
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    with open(out / "quantity_coverage.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    res = {"totals": dict(tot), "top_label_by_coverage": {k: dict(v) for k, v in cross.items()},
           "note": "labels (y/p/n, '' = not a real claim or unlabelled) are AI-assisted and describe the top passage only"}
    (out / "quantity_coverage.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        print(__doc__)
    else:
        run(*sys.argv[1:])
