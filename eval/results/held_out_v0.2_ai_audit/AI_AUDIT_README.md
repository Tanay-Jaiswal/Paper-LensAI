# AI-assisted audit of the second held-out sheet (PaperLens 0.2.0-dev)

**These are AI-generated labels. They are not human ground truth and they are not the result of the human audit that
`eval/results/held_out_v0.2/PROTOCOL.md` defines.** That audit is still open: the sheet
`eval/results/held_out_v0.2/held_out_audit.csv` is blank and unchanged.

**If you intend to label the blank sheet yourself, do it before opening the CSV and rationale files in this folder.**
Reading them first would bias your labels.

Made on 2026-10-12 at the owner's request. Rubric: `eval/results/held_out_v0.2/AUDIT_INSTRUCTIONS.md`, unchanged. All 33
rows of the sheet were labelled (the sheet holds every claim extracted from the 11 papers; there was no sampling).

## Contents

| Path | What it is |
|---|---|
| `pass1/held_out_audit_ai_assisted.csv` | Pass 1: labels by the AI assistant (Claude) that ran the evaluation. Locked by hash (`pass1/LABELS_LOCKED.txt`) before pass 2 was read |
| `pass1/rationales_pass1.md`, `pass1/ai_labels_pass1.py` | One rationale per row; the script that writes the file |
| `pass2_fresh_reviewer/held_out_audit_pass2.csv`, `rationales_pass2.md` | Pass 2: an independent labeller with a fresh context (also Claude), which saw only the instructions, the blank sheet and the PDFs |
| `consensus/held_out_audit_ai_consensus.csv` | Conservative combination: where the passes differ, the lower label, marked unsure |
| `consensus/DISAGREEMENTS.md`, `consensus/make_consensus.py` | The six disagreements and the rule that resolved them |
| `validate_and_summarise.py` | Validation and key-free measures |
| `SUMMARY_two_passes.txt`, `SUMMARY_consensus.txt` | Its output |

## How the labels were made

- For each row the claim page and the evidence page of the PDF in `data/held_out_v0.2_papers/` were read (text extracted
  with PyMuPDF) and the passage was judged by the rubric: only the passage shown; same number for a different quantity is
  `n`; a restatement without data, or support for only part of a claim, is `p`.
- Nothing under `eval/results/held_out_v0.2/sealed_key/` or `raw/` was opened for labelling, and the sealed key was not
  read at any time. The official scorer (`python -m eval.held_out_v2 score`) was **not** run on these files: it reads the
  sealed key, and the protocol reserves it for the human audit. The breakdown by PaperLens's support level is therefore
  not computed.
- Uncertainty is marked the way the rubric allows: "unsure" or "judgement call" in `notes`.

## Validation (all three files)

33 rows; row ids 1 to 33 in the original order; every original column identical to the blank sheet; labels only from the
permitted sets; `evidence_correct` blank exactly where the rubric requires; one rationale per row in each pass.

## Results (AI-assisted; 95% Wilson intervals)

| Measure | Pass 1 | Pass 2 | Conservative consensus |
|---|---|---|---|
| Claim precision | 0.818 (27/33; 0.66-0.91) | 0.788 (26/33; 0.62-0.89) | 0.788 (26/33; 0.62-0.89) |
| Coverage on real claims | 0.741 (20/27; 0.55-0.87) | 0.731 (19/26; 0.54-0.86) | 0.731 (19/26; 0.54-0.86) |
| Abstention rate on real claims | 0.259 (7/27; 0.13-0.45) | 0.269 (7/26; 0.14-0.46) | 0.269 (7/26; 0.14-0.46) |
| Evidence precision, strict (`y`) | 0.250 (5/20; 0.11-0.47) | 0.316 (6/19; 0.15-0.54) | 0.211 (4/19; 0.09-0.43) |
| Evidence precision, lenient (`y` or `p`) | 0.900 (18/20; 0.70-0.97) | 0.895 (17/19; 0.69-0.97) | 0.842 (16/19; 0.62-0.94) |
| Real claims with a fully supporting passage | 0.185 (5/27; 0.08-0.37) | 0.231 (6/26; 0.11-0.42) | 0.154 (4/26; 0.06-0.34) |
| End-to-end (real claim with `y`), all rows | 0.152 (5/33) | 0.182 (6/33) | 0.121 (4/33) |

Label counts. Pass 1: real claim y 27, n 6; evidence y 5, p 13, n 2; 4 rows marked unsure or judgement call.
Pass 2: real claim y 26, n 7; evidence y 6, p 11, n 2; 1 row marked unsure. Consensus: real claim y 26, n 7; evidence y 4,
p 12, n 3; 9 rows marked unsure (6 disagreements and 3 carried from pass 1).

Agreement between the passes: `is_real_claim` 32 of 33 (kappa 0.90); `evidence_correct` 14 of 19 rows both labelled
(kappa 0.51). The evidence labels are only moderately reproducible even between two labellers of the same model family:
five of the six disagreements are between `y` and `p` or between `p` and `n`.

## What this does and does not show

- By every version of the labels, **most returned passages do not fully support their claim**: strict precision is
  between 0.21 and 0.32, with intervals from about 0.1 to 0.5. Most passages are partial (a restatement, one part of a
  multi-part claim, a nearby value).
- Clearly wrong passages are few: 2 or 3 of 19 or 20.
- For reference only, the AI-assisted audit of version 0.1.0 on the first held-out set gave strict precision 0.16 (6/37)
  and lenient 0.62. Different papers, different sample, not paired: the intervals for strict precision overlap almost
  completely, so **these labels do not show that strict precision improved**. The lenient figure is higher here.
- 19 or 20 judged passages from 10 papers is a very small sample.

## Limitations

- Both passes are Claude models reading the same extracted text under the same rubric; their agreement is not independent
  validation and two AI passes are not a human audit.
- Pass 1 was made by the assistant that implemented the 0.2.0-dev fixes and ran this evaluation. Earlier in the same
  session it had seen the automatic summary of the run, including per-paper counts of support levels (not the per-row
  key). Pass 2 saw none of that.
- Labels were made from extracted page text, not from the rendered pages; figures and tables were not looked at.
- Whether an abstention was right, recall of claims, and whether a better passage existed are not measured.
- These labels must not be used to tune PaperLens: the 11 papers are a held-out set.
