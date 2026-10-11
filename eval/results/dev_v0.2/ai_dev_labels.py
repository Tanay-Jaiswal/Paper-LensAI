"""AI-ASSISTED labels for the development-set evidence audit (16 development papers). NOT a human audit.

Labelled by the AI assistant (Claude) from the claim and passage text in dev_pairs_blank.csv, following the rules of
eval/results/held_out/AUDIT_INSTRUCTIONS.md. The sheet hides which version produced a pair and how it was rated.
Unlike the held-out audit, pages were NOT re-opened: labels are from the two texts alone.

    python eval/results/dev_v0.2/ai_dev_labels.py      # writes dev_pairs_labelled.csv next to this file
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent

# is_real_claim for each distinct claim id
CLAIM_N = """3a4dd2951a 5bea35666f 31bda275c9 616f60c218 bad4415d12 a96505f9b1 527c581323 c384699146 1e13809b47 1fa1485e09
9268cb4a79 9603b9fffd a570546dcb a50e979751 c2cbc1d4bc 03ccd2bb18 e17d060d23 acb342adcd 4505f452cb 11ab6f90eb ab4ecf71f2
74cd807bb5 6651d0e5e0 d78e65542f 07bb45c09c a3687d29a7 1bfbe8366d ed4ee78534 28b23e1492 0e8b48f1e5 9934b3fb21 3b59a3f22f
19155a1c23 35b757b202 175db9c410 95d91b1335 d8ecac16af 6f34eea135 bf30622362 22564cff40 fd9d105a3e 0ea2c4acef 0b9b76bd2d
8c906d508d f25a2ed309 35f7989391 ca3f49160b 678edc5e25""".split()

# evidence_correct for each (claim, top passage) pair id whose claim is real: filled in below
PAIR = {}
PAIR_TEXT = """
47fe8c6f00 n  table row about fat mass, claim is about VO2peak in MET
79c53d558b p  caption naming the architecture only
d4e7a32b47 y  same conclusion incl. possible inflation of effect size
428cb08f9d n  loosely related sentence, does not describe the task
2f0e620852 y  same 5.9 sigma significance
180f26d8b5 y  same 3.57% error
ddeb682813 y  same statement about the bound, in the analysis section
7e8101d6ca n  regression associations, not the diabetes comparison
c23cb70b32 y  results sentence with the same PAES finding
e91eacff56 n  caption about 3D model quality, not contact accuracy
9fc9099d1f p  only the false-alarm bound of a three-part claim
d2aef1bc29 n  250 000 templates is a different quantity
2201cbf02b y  same 2% and 7%
7889c2f0ba n  caption about one CAMEO target
db23a4f438 p  pointer to Table 2
805d3006fc n  unrelated count of targets
b7e2dca927 p  near-restatement without data
131029f8d2 n  caption about a different frequency band
d34f78a8b1 n  unrelated
76b75bfd6d y  same finding in the experiments
d59b4f1147 p  only the radiated-energy part
e69fc263b2 n  different table row, coincidental 0.24
255fcf64bb p  caption states the finding, no data
38fcfaa7ad p  only the training-time part
342a08f967 p  one of three scores
0e2e214b50 n  table header fragment
a84708af68 n  different model's training time
b178ae6873 p  restates the conclusion
c5877d53c8 p  one of the listed targets
4c495acdc0 n  figure text
9805653cd5 y  parameter list with the same distance and redshift
f06757ea7e y  same 208 of 398 and 10
936dd61968 y  same result with ~60 layers
8277bf6220 y  same finding in the results
939afe5998 n  different explanation
402393019f p  restatement without data
aac6b14960 n  unrelated
d1259174fb p  restates one part
f77773d0bc p  discusses the hormone reduction, not the lipid result
219255fd3a y  same finding
68a9b448ed p  pointer to Table 4
b087f30479 p  near-restatement
96061174f0 n  table row for another country
0f64f1ab19 y  same 11 to 13% with how it was estimated
1b0c3b8ee3 n  different finding
0325601b41 n  fragment
7d4fac907b p  says the experiment was run, no result
91c1b6c5fc p  supervised methods beat DCA methods: related, indirect
50e9ba8281 p  related comparison, indirect
e95c0c205b p  hypothesis related to the claim
4bfb572639 p  complexity argument, cut off; unsure
7fc2fe0093 p  restatement without data
479ac62d25 y  same 203 of 579, 79 and 62
f87a6a13e1 n  a different study
ad22510c01 y  same 28% relative improvement
0ce0154874 n  describes another method
93b7137346 n  different finding about scale
388140ca42 p  part of the methodology
680f5fcee0 y  same 31%
60dc01c77a n  inclusion criteria
802db18155 y  same three accuracies
d0c1d0af72 p  one example protein
ee44c15d53 y  same stage breakdown
2615f8a3f8 p  one part of the claim
c8b26c69be y  same conclusion with added detail
66fcc5909f n  unrelated
14cd6dfb73 n  unrelated
31418e6169 p  one of several results
335b7cd4b4 p  one task family of several
935b45607e p  one example protein
9e3a798e43 n  method fragment
ecdb9a93d9 y  same 28.4 BLEU and margin
b97c4a7ddb y  same finding
074c5c38bc p  only the stages 3-5 figure, in a sensitivity test
e9f17baa08 p  one of the two tasks
69be8f7dd0 p  restates the conclusion
6ffe87d855 n  different finding
6dc9d4de44 p  gives the present study's finding, not the contrast
c4af40fbc2 y  equivalent statement in the results
d07493742d n  unrelated list
078874bf81 n  unrelated
396f382d9b p  pointer to Table 2
3f3d7dc530 n  procedure detail
a13727f244 y  same result and statistics
078255dbd5 y  parameter list with the same masses
95c20b5dfc y  table text with the three CoQA scores
26d585629a y  same mass measurement
806aecf369 y  same 45%
e2b87d17fa p  says the experiment was run, no result
6bfd4827b4 p  describes the experiment, no result
e77f82ba04 n  different table row
94e3196868 n  background on meta-analysis
629fa883bf p  near-restatement
1eea2f31d8 n  generic statement
baeed19f55 y  same comparison with FLOPs
510f29ca2a n  about enjoyment scores, not body composition
3239341f4c n  describes another experiment
812f959ee8 n  heart-rate ratio, different quantity
db3749d92e p  says the evaluation was done; unsure between p and y
b70fe4a58a n  0.17 is a different quantity
5056dc1c9d y  same reductions and p-values
0e9fd434f4 n  different comparison
1fb59eb83c n  different averages
0de9dcde3e p  one benchmark's summary
73513c5722 p  result statement without data; unsure between p and y
"""


def main():
    notes = {}
    for line in PAIR_TEXT.strip().splitlines():
        pid, lab, note = line.split(None, 2)
        PAIR[pid], notes[pid] = lab, note
    rows = list(csv.DictReader(open(HERE / "dev_pairs_blank.csv", encoding="utf-8-sig")))
    claim_lab = {}
    for r in rows:
        if r["kind"] == "claim":
            r["label"] = "n" if r["id"] in CLAIM_N else "y"
            claim_lab[(r["paper"], r["claim"])] = r["label"]
    missing = []
    for r in rows:
        if r["kind"] == "pair":
            if claim_lab[(r["paper"], r["claim"])] == "y":
                r["label"], r["notes"] = PAIR.get(r["id"], ""), notes.get(r["id"], "")
                if not r["label"]:
                    missing.append(r["id"])
            else:
                r["notes"] = "claim labelled not real; evidence not judged"
        r["notes"] = ("[AI-assisted label] " + r["notes"]).strip()
    assert len(set(CLAIM_N)) == len(CLAIM_N) and set(CLAIM_N) <= {r["id"] for r in rows if r["kind"] == "claim"}
    if missing:
        print(len(missing), "pairs of real claims still unlabelled")
        return rows, missing
    with open(HERE / "dev_pairs_labelled.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    from collections import Counter
    print("claims", dict(Counter(r["label"] for r in rows if r["kind"] == "claim")),
          "| pairs", dict(Counter(r["label"] or "not judged" for r in rows if r["kind"] == "pair")))
    return rows, missing


if __name__ == "__main__":
    rows, missing = main()
    if missing:   # print what still needs a label: id, claim, passage (no version, no rating)
        for r in rows:
            if r["kind"] == "pair" and r["id"] in missing:
                print(f"P {r['id']} | {r['claim'][:210]} || {r['evidence'][:330]}")
