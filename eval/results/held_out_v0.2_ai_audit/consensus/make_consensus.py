"""Conservative combination of the two AI-assisted passes. NOT human labels.

    python eval/results/held_out_v0.2_ai_audit/consensus/make_consensus.py

Rule, fixed before the two passes were compared row by row:
- is_real_claim: where the passes differ the label is n with "unsure" in notes (the rubric says: if you cannot decide,
  choose n and write "unsure").
- evidence_correct: where the passes differ the lower label is taken (n below p below y) and "unsure" is written in notes.
- Where they agree the common label is kept. Neither pass is edited.
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1 = HERE.parent / "pass1" / "held_out_audit_ai_assisted.csv"
P2 = HERE.parent / "pass2_fresh_reviewer" / "held_out_audit_pass2.csv"
ORDER = {"n": 0, "p": 1, "y": 2}


def main():
    a = list(csv.DictReader(open(P1, encoding="utf-8-sig")))
    b = list(csv.DictReader(open(P2, encoding="utf-8-sig")))
    out, log = [], ["# Disagreements between the two AI-assisted passes and how each was resolved", "",
                    "Rule: the more conservative label, marked unsure (see make_consensus.py). Not human adjudication.", "",
                    "| Row | Pass 1 (real/evidence) | Pass 2 (real/evidence) | Consensus | Pass 1 reason | Pass 2 note |", "|---|---|---|---|---|---|"]
    for x, y in zip(a, b):
        assert x["row"] == y["row"]
        r = dict(x)
        notes = []
        real = x["is_real_claim"] if x["is_real_claim"] == y["is_real_claim"] else "n"
        shown = bool(x["evidence"].strip())
        if real == "y" and shown:
            ev = min(x["evidence_correct"], y["evidence_correct"], key=ORDER.get)
        else:
            ev = ""
        differ = (x["is_real_claim"], x["evidence_correct"]) != (y["is_real_claim"], y["evidence_correct"])
        if differ:
            notes.append(f"unsure: AI passes disagreed (pass 1 {x['is_real_claim']}/{x['evidence_correct'] or '-'}, "
                         f"pass 2 {y['is_real_claim']}/{y['evidence_correct'] or '-'}); conservative label taken")
            log.append(f"| {x['row']} | {x['is_real_claim']}/{x['evidence_correct'] or '-'} | {y['is_real_claim']}/{y['evidence_correct'] or '-'} "
                       f"| {real}/{ev or '-'} | {x['notes'] or '(see rationales_pass1.md)'} | {y['notes'] or '(see rationales_pass2.md)'} |")
        elif x["notes"]:
            notes.append(x["notes"])
        r["is_real_claim"], r["evidence_correct"], r["notes"] = real, ev, "; ".join(notes)
        out.append(r)
    with open(HERE / "held_out_audit_ai_consensus.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    (HERE / "DISAGREEMENTS.md").write_text("\n".join(log) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(out)} rows; {len(log) - 6} disagreements resolved conservatively")


if __name__ == "__main__":
    main()
