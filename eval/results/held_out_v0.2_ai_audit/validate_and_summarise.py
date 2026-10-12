"""Validate an AI-assisted copy of the second held-out sheet and summarise it WITHOUT the sealed key.

    python eval/results/held_out_v0.2_ai_audit/validate_and_summarise.py <labelled.csv> [<second labelled.csv>]

Checks: 33 rows, row ids 1..33 in the original order, every original column identical to the blank sheet, labels in the
permitted sets, evidence_correct blank exactly where the rubric requires. Then prints the label counts and the measures
of PROTOCOL.md section 5 that need no key (everything except the breakdown by PaperLens's hidden support level, which
needs sealed_key/ and is therefore not computed here). With a second file: agreement and Cohen's kappa.

These are AI-assisted figures. They are not human ground truth and are not the result of the protocol's human audit.
"""
import csv
import math
import sys
from collections import Counter
from pathlib import Path

BLANK = Path(__file__).resolve().parents[1] / "held_out_v0.2" / "held_out_audit.csv"
LABEL_COLS = ("is_real_claim", "evidence_correct", "notes")


def wilson(k, n):
    if not n:
        return "n/a"
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{p:.3f} ({k}/{n}; 95% CI {max(0, c - h):.2f}-{min(1, c + h):.2f})"


def load(path):
    blank = list(csv.DictReader(open(BLANK, encoding="utf-8-sig")))
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    problems = []
    if len(rows) != 33 or len(blank) != 33:
        problems.append(f"expected 33 rows, found {len(rows)}")
    if [r["row"] for r in rows] != [b["row"] for b in blank]:
        problems.append("row ids missing, duplicated or reordered")
    if rows and list(rows[0]) != list(blank[0]):
        problems.append("columns differ from the blank sheet")
    for r, b in zip(rows, blank):
        for c in b:
            if c not in LABEL_COLS and r.get(c) != b[c]:
                problems.append(f"row {b['row']}: column {c} differs from the blank sheet")
        a, e = r["is_real_claim"], r["evidence_correct"]
        needs = a == "y" and bool(r["evidence"].strip())
        if a not in ("y", "n"):
            problems.append(f"row {r['row']}: is_real_claim '{a}' not permitted")
        elif needs and e not in ("y", "p", "n"):
            problems.append(f"row {r['row']}: evidence_correct '{e}' not permitted")
        elif e and not needs:
            problems.append(f"row {r['row']}: evidence_correct must be blank")
    return rows, problems


def kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return f"agreement {po:.3f} ({sum(x == y for x, y in zip(a, b))}/{n}), Cohen's kappa " + ("n/a" if pe == 1 else f"{(po - pe) / (1 - pe):.3f}")


def summarise(path):
    rows, problems = load(path)
    print(f"== {path}")
    if problems:
        print("INVALID:", *problems, sep="\n  ")
        return None
    real = [r for r in rows if r["is_real_claim"] == "y"]
    shown = [r for r in real if r["evidence"].strip()]
    ev = Counter(r["evidence_correct"] for r in shown)
    print("valid: 33 rows, ids and original columns unchanged, labels permitted, blanks where required")
    print("is_real_claim:", dict(Counter(r["is_real_claim"] for r in rows)), "| evidence_correct:", dict(ev),
          "| blank:", sum(not r["evidence_correct"] for r in rows),
          "| notes with 'unsure' or 'judgement call':", sum(("unsure" in r["notes"].lower()) or ("judgement call" in r["notes"].lower()) for r in rows))
    print("AI-ASSISTED, not human ground truth:")
    print("  claim precision:                      " + wilson(len(real), len(rows)))
    print("  coverage on real claims:              " + wilson(len(shown), len(real)))
    print("  abstention rate on real claims:       " + wilson(len(real) - len(shown), len(real)))
    print("  evidence precision, strict  (y):      " + wilson(ev["y"], len(shown)))
    print("  evidence precision, lenient (y or p): " + wilson(ev["y"] + ev["p"], len(shown)))
    print("  end-to-end (real claim with y), rows: " + wilson(ev["y"], len(rows)))
    print("  real claims with a y passage:         " + wilson(ev["y"], len(real)))
    return rows


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    a = summarise(sys.argv[1])
    if len(sys.argv) > 2:
        b = summarise(sys.argv[2])
        if a and b:
            print("== agreement between the two files (two AI passes agreeing is not human validation)")
            print("  is_real_claim:    " + kappa([r["is_real_claim"] for r in a], [r["is_real_claim"] for r in b]))
            both = [(x["evidence_correct"], y["evidence_correct"]) for x, y in zip(a, b) if x["evidence_correct"] and y["evidence_correct"]]
            print("  evidence_correct (rows both labelled): " + kappa([x for x, _ in both], [y for _, y in both]))
            for x, y in zip(a, b):
                if (x["is_real_claim"], x["evidence_correct"]) != (y["is_real_claim"], y["evidence_correct"]):
                    print(f"  row {x['row']}: first {x['is_real_claim']}/{x['evidence_correct'] or '-'}  second {y['is_real_claim']}/{y['evidence_correct'] or '-'}")
    sys.exit(0 if a else 1)
