# Second AI-assisted audit of the 45 held-out claims, and comparison with the first

**Neither pass is a human audit. Agreement between two AI passes is not proof that the labels are correct and is not
independent human validation.** Both passes were made by Claude models, following labelling rules written by the first
labeller, from the same extracted page text. They share the same blind spots, so they are expected to agree far more than
two independent people would. The human sheet `eval/results/held_out/held_out_audit.csv` is still blank.

## How the second pass was run (2026-10-11)

- A fresh sub-agent with no access to the earlier conversation did the labelling. Its prompt contained only: the labelling
  rules, a copy of the blank sheet, the PDF folder, a text-extraction helper, the output format, and a list of files it must
  not open. It was told nothing about how PaperLens performs or what the first pass found.
- It was told not to open `held_out_audit_key.csv`, `held_out_sample_info.json`, anything under `raw/`, the first audit's
  folder, other result files, or the evaluation docs. **This could not be technically enforced**: the sub-agent had normal
  read access to the project folder. It reported that it opened none of them.
- It labelled from the PyMuPDF text surrounding each claim and evidence passage on the cited pages (`page_context.txt`).
  It reported that it did not render any page as an image.
- Its labels (`labels_pass2.py` writes them into `held_out_audit.csv` here) were hashed into `LABELS_LOCKED.txt` before
  anything was scored or compared. The first audit's labels were not shown to it and were not changed.
- Not fully independent in two further ways: the helper that extracts page context was written by the first labeller, and
  so were the rules.

## Scores of the second pass (AI-assisted labels, 95% Wilson intervals)

| Measure | Pass 1 | Pass 2 |
|---|---|---|
| Claim precision | 0.822 (37/45; 0.69 to 0.91) | 0.822 (37/45; 0.69 to 0.91) |
| Evidence precision, strict | 0.162 (6/37; 0.08 to 0.31) | 0.162 (6/37; 0.08 to 0.31) |
| Evidence precision, lenient | 0.622 (23/37; 0.46 to 0.76) | 0.595 (22/37; 0.43 to 0.74) |
| Real claim with fully supporting evidence, all rows | 0.133 (6/45; 0.06 to 0.26) | 0.133 (6/45; 0.06 to 0.26) |
| Strict evidence precision: strong / moderate / weak / none | 3/12, 0/5, 2/8, 1/12 | 3/12, 0/5, 2/8, 1/12 |

## Agreement between the two passes

| Column | Rows | Raw agreement | Cohen's kappa |
|---|---|---|---|
| `is_real_claim` (y / n) | 45 | 45/45 = 1.000 | 1.000 |
| `evidence_correct` left blank or labelled | 45 | 45/45 = 1.000 | 1.000 |
| `evidence_correct` (y / p / n), rows both labelled | 37 | 36/37 = 0.973 | 0.957 |
| `evidence_correct` collapsed to strict y vs not y | 37 | 37/37 = 1.000 | 1.000 |

Kappa is computed on 37 to 45 rows with one category as small as 6 to 8 rows, so it is unstable; one changed label would
move it by several points.

**The one disagreement.** Row 23 (arXiv:2303.00194v1, C10): pass 1 labelled the evidence `p` and noted it was unsure between
`p` and `n`; pass 2 labelled it `n`. The passage gives a low electron density in two apertures, while the claim is about
line ratios in two other apertures and a probable fall of density with radius.

**Uncertainty flagged.** Pass 1 flagged 8 rows as unsure or borderline (10, 16, 17, 20, 21, 23, 25, 26). Pass 2 flagged 2
(16, 17). So six rows that the first pass considered judgement calls were labelled the same way by the second pass without
comment. That is consistent with the two passes sharing a tendency, not with those rows being easy.

## What can and cannot be concluded

- The first pass's labels are reproducible by a second run of the same kind of model under the same rules.
- That says nothing about whether a person would agree. The strict/partial boundary and the claim/method-remark boundary
  are exactly where a human may differ, and neither pass can reveal that.
- Both passes read extracted text, not rendered pages.
- 45 rows, 8 papers, precision only.

## Integrity (checked after both passes)

- Original blank sheet SHA-256 unchanged: `6E0530B348CEB19332569F281CA1D53BE288B534CECD821F56D5016595BEE37C`.
- First audit's labelled sheet unchanged: `C66EDABDFDF566DD8741A332A48CB63EB14032E5FFBEEC1247B7FEC67C9630EE`.
- `python -m eval.freeze verify eval/results/held_out/FREEZE.json`: no frozen file has changed.
- Raw outputs match `RAW_OUTPUT_HASHES.json`.
- Nothing under `paperlens/` was modified.

## Files here

`held_out_audit.csv` (second labels with notes), `labels_pass2.py`, `page_context.txt`, `LABELS_LOCKED.txt`,
`score_output.txt`, `compare_passes.py`, `comparison_output.txt`, `blank_sheet.csv` and `AUDIT_INSTRUCTIONS.md` (the copies the
sub-agent read), `extract_page_context.py` (the helper), `held_out_audit_key.csv` (byte-identical copy for the scorer, never displayed).
