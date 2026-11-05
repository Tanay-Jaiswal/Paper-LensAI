# AI-assisted audit of the 45 held-out claims

**This is not a human audit.** The labels in this folder were produced by an AI assistant (Claude), at the project owner's
request, on 2026-10-11. They are not independent human judgements and must not be reported as human precision or ground
truth. The human sheet `eval/results/held_out/held_out_audit.csv` is still blank and human-labelled precision is still
not computed.

## What was done

1. Read `eval/results/held_out/AUDIT_INSTRUCTIONS.md` and applied its rules as written.
2. For each of the 45 rows, extracted the text of the cited claim page and evidence page from the original PDF with plain
   PyMuPDF (PaperLens was not run), located the claim and the evidence passage on those pages, and read them in context.
   What was read for each row is saved in `page_context.txt`.
3. Decided `is_real_claim`, then `evidence_correct` only where the rules require it (real claim and an evidence passage
   shown), and wrote a note giving the reason for every row. Labels and notes are in `ai_labels.py`, which writes them into a
   **copy** of the sheet (`held_out_audit.csv` in this folder).
4. Recorded the SHA-256 of the labelled copy in `LABELS_LOCKED.txt` **before** scoring. No label was changed after scoring.
5. Ran `python -m eval.held_out_audit score eval/results/held_out_ai_audit`; output saved in `score_output.txt`.

## Files read and not read

- Read: `AUDIT_INSTRUCTIONS.md`, the blank `held_out_audit.csv`, the 8 PDFs in `data/held_out_papers/`.
- Not opened during labelling: `held_out_audit_key.csv`, `held_out_sample_info.json`, anything under `raw/`.
- `held_out_audit_key.csv` in this folder is a byte-identical file copy made without displaying it, because the scoring
  script joins it. Per-row support ratings were never shown to the labeller; only the aggregated score output was.

## Integrity

- Original blank sheet SHA-256 before and after: `6E0530B348CEB19332569F281CA1D53BE288B534CECD821F56D5016595BEE37C` (unchanged).
- `python -m eval.freeze verify eval/results/held_out/FREEZE.json`: no frozen file has changed.
- Raw outputs match `RAW_OUTPUT_HASHES.json`.
- Nothing under `paperlens/` or `eval/results/held_out/` was modified.

## Label distribution

| | Count |
|---|---|
| `is_real_claim` = y | 37 |
| `is_real_claim` = n | 8 |
| `evidence_correct` = y | 6 |
| `evidence_correct` = p | 17 |
| `evidence_correct` = n | 14 |
| `evidence_correct` blank (claim not real, or no evidence shown) | 8 |
| Rows whose note is flagged "unsure" or "borderline" | 8 (rows 10, 16, 17, 20, 21, 23, 25, 26) |
| Claim or evidence not found on the cited page | 0 |
| Unreadable passages | 0 |

## Results (AI-assisted labels; 95% Wilson intervals)

| Measure | Value |
|---|---|
| Claim precision | 0.822 (37/45; 0.69 to 0.91) |
| Evidence precision, strict (y) | 0.162 (6/37; 0.08 to 0.31) |
| Evidence precision, lenient (y or p) | 0.622 (23/37; 0.46 to 0.76) |
| End to end (real claim and evidence y), over all rows | 0.133 (6/45; 0.06 to 0.26) |

| PaperLens support level | Strict evidence precision |
|---|---|
| strong | 0.250 (3/12) |
| moderate | 0.000 (0/5) |
| weak | 0.250 (2/8) |
| none | 0.083 (1/12) |

Reading: under these labels most extracted sentences are real claims, but the top evidence passage fully supports the claim
in only about one case in six, and is at least related in about six in ten. Strict precision does **not** fall from strong
to weak, so on this sample the support ratings show no sign of being calibrated. The per-level counts (5 to 12 rows) are too
small to say more than that.

Per paper, claim precision ranged from 0.33 to 1.00 (3 to 14 rows each); see `score_output.txt`.

## What the eight uncertain rows would change

- Rows 16 and 17 were labelled `n` under the "if you cannot decide, choose n" rule. Rows 20, 21 and 25 are methods-section
  measurements or robustness statements labelled `y`. If all five flipped, claim precision would range from 34/45 (0.76) to
  39/45 (0.87).
- Rows 10, 23 and 26 are `p`, borderline with `n`. Strict evidence precision does not depend on them; lenient precision
  would be 20/37 (0.54) if all three were `n`.

## Limitations

- **AI-assisted, not human.** One AI labeller. No second annotator, so no agreement figure.
- **Not independent and not fully blind.** The same assistant wrote and tuned the extraction and linking rules, built the
  audit sheet and wrote the labelling instructions. Before labelling it had seen the per-paper counts of support levels and
  knew that the two sampled claims with no evidence passage are rated `none` (which the blank evidence cell implies anyway).
  It had not seen the rating of any other sampled claim.
- **Text layer only.** Pages were read as extracted text, not as rendered images, so figures and table layout were not
  inspected visually. No row depended on reading a figure; the one table-row evidence passage belongs to a row labelled `n`
  for the claim, so it was not judged.
- **Judgement calls.** The line between "partial" and "wrong", and between a claim and a methods remark, is subjective. A
  human may reasonably label several rows differently.
- **Small sample.** 45 rows from 8 papers and 4 sources; precision only, no recall.
- **Strictness of `y`.** The rules count a passage as `y` only if it reports the same finding. Many passages rated `p` are
  captions, restatements, or sentences that support one part of a compound claim.

## How to reproduce or replace

- Rebuild the labelled copy: `python eval/results/held_out_ai_audit/ai_labels.py`, then compare its SHA-256 with `LABELS_LOCKED.txt`.
- A human audit remains the reference: label `eval/results/held_out/held_out_audit.csv`, score it, and optionally compare
  with these labels using `python -m eval.held_out_audit score eval/results/held_out --second eval/results/held_out_ai_audit/held_out_audit.csv`.
