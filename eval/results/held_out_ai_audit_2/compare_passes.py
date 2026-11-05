"""Compare the two AI-assisted label sets (pass 1 vs pass 2). Agreement between two AI passes is NOT validation.

    python eval/results/held_out_ai_audit_2/compare_passes.py
"""
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
A = list(csv.DictReader(open(HERE.parent / "held_out_ai_audit" / "held_out_audit.csv", encoding="utf-8-sig")))
B = list(csv.DictReader(open(HERE / "held_out_audit.csv", encoding="utf-8-sig")))
assert len(A) == len(B) == 45 and all(a["row"] == b["row"] and a["claim"] == b["claim"] and a["evidence"] == b["evidence"] for a, b in zip(A, B))


def kappa(x, y):
    n = len(x)
    po = sum(p == q for p, q in zip(x, y)) / n
    cx, cy = Counter(x), Counter(y)
    pe = sum(cx[c] * cy[c] for c in set(cx) | set(cy)) / (n * n)
    k = "undefined (no variation)" if pe == 1 else f"{(po - pe) / (1 - pe):.3f}"
    return f"n={n}  raw agreement {sum(p == q for p, q in zip(x, y))}/{n} = {po:.3f}  Cohen's kappa {k}  | pass1 {dict(cx)}  pass2 {dict(cy)}"


g = lambda rows, c: [r[c].strip().lower() for r in rows]
print("is_real_claim:                  ", kappa(g(A, "is_real_claim"), g(B, "is_real_claim")))
blank = lambda rows: ["blank" if not r["evidence_correct"].strip() else "labelled" for r in rows]
print("evidence_correct blank or not:  ", kappa(blank(A), blank(B)))
both = [(a["evidence_correct"], b["evidence_correct"]) for a, b in zip(A, B) if a["evidence_correct"].strip() and b["evidence_correct"].strip()]
print("evidence_correct y/p/n (both):  ", kappa([x for x, _ in both], [y for _, y in both]))
s = lambda v: "y" if v == "y" else "not-y"
print("evidence_correct strict y vs not:", kappa([s(x) for x, _ in both], [s(y) for _, y in both]))
print("\nDisagreements:")
for a, b in zip(A, B):
    if (a["is_real_claim"], a["evidence_correct"]) != (b["is_real_claim"], b["evidence_correct"]):
        print(f"row {a['row']} ({a['paper_id']} {a['claim_id']}): pass1 claim={a['is_real_claim']} evidence={a['evidence_correct'] or 'blank'} | pass2 claim={b['is_real_claim']} evidence={b['evidence_correct'] or 'blank'}")
        print("   pass1 note:", a["notes"])
        print("   pass2 note:", b["notes"])
flag = lambda rows: [r["row"] for r in rows if "nsure" in r["notes"] or "orderline" in r["notes"]]
print("\nrows flagged unsure/borderline: pass1", flag(A), "| pass2", flag(B))
