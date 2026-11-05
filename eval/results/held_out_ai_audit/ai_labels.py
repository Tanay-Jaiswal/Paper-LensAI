"""AI-ASSISTED labels for the 45 held-out claims. NOT a human audit.

Labels were decided by the AI assistant (Claude) from the PDF text of the cited pages (see page_context.txt), following
eval/results/held_out/AUDIT_INSTRUCTIONS.md. This script only copies the blank sheet and writes those labels into the copy:

    python eval/results/held_out_ai_audit/ai_labels.py

It reads eval/results/held_out/held_out_audit.csv (never modified) and writes held_out_audit.csv next to this file.
Format: row -> (is_real_claim, evidence_correct, note). evidence_correct is "" when the rules say to leave it blank.
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "held_out" / "held_out_audit.csv"

L = {
    1: ("y", "p", "Contribution (proposes the framework). Evidence is only the Figure 2 caption naming the framework: points to it, no detail."),
    2: ("y", "p", "Claim about own method. Evidence says a case study is run to verify order-confounder and error-propagation; states intent not result, and says nothing on decoding efficiency."),
    3: ("n", "", "Sentence cut at 'w/o.' before it asserts anything (splitter error); the assertion itself is missing."),
    4: ("y", "p", "Contribution statement. Evidence is the Figure 2 caption only: points to the framework without describing it."),
    5: ("y", "y", "Contribution (Inverse Generation Training). Evidence is the method-section sentence that introduces and motivates that training task."),
    6: ("y", "p", "Result (outperforms SOTA on five datasets, 3x faster). Evidence supports only the 3x speed part (Table 7), not the accuracy part."),
    7: ("y", "y", "Finding (forcing longer outputs helps the attack). Evidence is the results sentence stating longer-output methods attack better and that this confirms the assumption."),
    8: ("y", "y", "Contribution (proposes the attack method). Evidence is the method-section sentence describing the proposed white-box attack with multi-objective optimisation and adaptive search."),
    9: ("y", "p", "Result claim. Evidence is the Table 3 caption: points to where the comparison is, contains no result itself."),
    10: ("y", "p", "Contribution plus result (higher attack success rate). Evidence only lists the evaluation metrics incl. ASR; same experiment, no result. Borderline p/n: unsure."),
    11: ("y", "n", "Contribution (designs testing/isolation strategies). Evidence is a single step of an appendix proof about a lower bound in an example; shares the words 'cumulative infections' only."),
    12: ("y", "n", "Result claim (necessity of exploration shown by proof and simulation). Evidence is a proof-step heading fragment ('(64) Step 4. ...'), not a statement that supports the claim."),
    13: ("y", "n", "Statement of what the approach is and what tradeoffs are observed (contrasted with [51],[52]); counted as a claim about own work. Evidence is an unrelated appendix proof sentence about quarantined nodes."),
    14: ("y", "n", "Minor contribution (proposes the alpha-linking backward update). Evidence is a proof step about Algorithm 4, not about the alpha-linking algorithm."),
    15: ("y", "n", "Conclusion restating a proved result. Evidence is a procedural sentence from a worked example; does not show sub-optimality or the constant-factor gain."),
    16: ("n", "", "Unsure. A remark about computational cost in the discussion of assumptions, with no result shown; treated as method/limitation description."),
    17: ("n", "", "Unsure. Same kind of remark as row 16, and the sentence is cut at a page break (ends with a comma)."),
    18: ("y", "n", "Result (outer-wind outflow rate and ionized mass). Evidence is about extinction E(B-V) and equivalent width: a different quantity."),
    19: ("y", "n", "Result (momentum-driven flow, boost ~7). Evidence gives a 7 Myr starburst age: same number, different quantity."),
    20: ("y", "n", "Borderline claim: a flux-calibration measurement reported in the methods section (26% / 80% offset vs SDSS). Counted y because it states a measurement of this paper. Evidence is the [O II]/H-alpha ratio vs radius: unrelated."),
    21: ("y", "n", "Borderline claim: a fit result reported in the methods section (stellar attenuation in ap1). Evidence gives electron densities in ap1.1: a different quantity."),
    22: ("y", "n", "Measurement (velocity and width offsets of the broad [O I] component). Claim text starts with a stray parenthetical from the previous sentence. Evidence is a Na I vs Fe II velocity difference: different lines, coincidental 200 km/s."),
    23: ("y", "p", "Hedged interpretation of own results (lower velocity / density at large radius). Evidence gives low electron density in ap4 and ap5 only: related to the density part, does not address ap6/ap8 line ratios. Unsure between p and n."),
    24: ("y", "p", "Result (line ratios of component ap1.2 at 0-5 kpc). Evidence is a sentence fragment giving the interpretation for the same region (fast shocks plus precursor), not the ratios."),
    25: ("y", "n", "Borderline claim: a robustness statement about the authors' own calculation (higher post-shock density does not change results). Evidence is about high-velocity gas not contributing to mass: different point."),
    26: ("y", "p", "Result (Method 1a gives a 15-20x lower flow rate). Evidence only defines Method 1: same analysis, no result. Borderline p/n: unsure."),
    27: ("y", "p", "Result (predicted H-alpha luminosity is 3-4x the observed 9.4e42). Evidence gives the observed total luminosity 9.4e42 only: one side of the comparison."),
    28: ("y", "n", "Result (momentum rate is 7x the stellar plus radiation input). Evidence is about a linear fit with 0.3 dex RMS: unrelated."),
    29: ("y", "n", "Sensitivity statement about own analysis (factor ~50). Evidence describes how electron density is calculated and a parabolic-fit aside: does not support the factor."),
    30: ("y", "n", "Result (Episode I energy rate is 0.003 of shock luminosity). Evidence is about the starburst ejecta energy being under 4% of the Episode II rate: a different comparison."),
    31: ("y", "y", "Conclusion (flow energy is 0.003 of the radiated flux). Evidence is the results sentence giving the same 0.003 ratio for Episode I."),
    32: ("y", "y", "Result (average 1.7 +/- 0.5 permil). Evidence gives the same average for the same quantity; the passage is cut at 'Mt.' and does not cover 'higher than most existing data'."),
    33: ("y", "p", "Conclusion. Evidence restates it in nearly the same words in the discussion, with no data in the passage itself."),
    34: ("y", "p", "Result/comparison; the start of the sentence is cut at 'Mt.' but the claim is clear on the page. Evidence gives the mid-latitude value 1.0 +/- 0.7 that the claim compares against, not the Everest value."),
    35: ("n", "", "Statement of need / motivation, not a finding of the study."),
    36: ("n", "", "Background about WHO policy, not the authors' own work."),
    37: ("y", "p", "Discussion sentence mixing background figures with the study's finding (most cases in forest areas with lower GDP and urbanisation). Evidence only gives Brazil's area and number of municipalities: backs the background part, not the finding."),
    38: ("n", "", "General context about transport in the Amazon, not a finding of the study. No evidence shown."),
    39: ("y", "p", "Conclusion. Evidence is the discussion sentence that repeats the same statement almost word for word; no data on the finding in the passage."),
    40: ("n", "", "Background on prior evidence, not the authors' own finding."),
    41: ("y", "p", "Contribution (develops the extended SEIR model). Evidence is the Author Summary restating the aim, not the model description in the body."),
    42: ("n", "", "Figure caption text (colour key), not a claim."),
    43: ("y", "p", "Hedged conclusion (plus-end dynamics provide the force). Evidence is a discussion sentence about EB1/Map205 and Topoisomerase needs: related, but does not state the plus-end force conclusion."),
    44: ("y", "y", "Result (33% vs 14% telomeres opposed). Evidence is the results sentence with the same 14% and 33% for the same quantity; the 0% for unzipping is in the following sentence."),
    45: ("y", "p", "Result plus conclusion (Topoisomerase II knockdown increases failed separation). Evidence supports only the catenation part, citing earlier studies; it does not report the knockdown result."),
}

rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig")))
assert len(rows) == len(L) == 45 and all(not r["is_real_claim"] and not r["evidence_correct"] for r in rows)
for r in rows:
    a, e, note = L[int(r["row"])]
    assert a in ("y", "n") and (e in ("y", "p", "n") if (a == "y" and r["evidence"].strip()) else e == ""), r["row"]
    r["is_real_claim"], r["evidence_correct"], r["notes"] = a, e, "[AI-assisted label] " + note
with open(HERE / "held_out_audit.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
from collections import Counter
print("is_real_claim", dict(Counter(r["is_real_claim"] for r in rows)), "| evidence_correct", dict(Counter(r["evidence_correct"] or "blank" for r in rows)),
      "| flagged unsure/borderline", sum("nsure" in r["notes"] or "orderline" in r["notes"] for r in rows))
