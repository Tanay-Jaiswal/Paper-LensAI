# Second held-out audit (PaperLens 0.2.0-dev): how to label `held_out_audit.csv`

Up to 60 claims that PaperLens 0.2.0-dev extracted from papers it was never run on before (`data/held_out_v0.2_papers/`).
You fill two columns. Nothing is scored until every row is labelled. Expect about 2 to 3 minutes per row.

The labelling rules below are those of the first held-out audit, unchanged in substance, so that the two audits ask the
same questions. This version of PaperLens may answer "No supporting evidence found": those rows have an empty `evidence`
cell and need only the first column.

## Before you start

1. Open `held_out_audit.csv` in a spreadsheet. If you use Excel, import it as UTF-8 and save as CSV (not .xlsx).
2. For each row open the PDF named in `paper_file` from `data/held_out_v0.2_papers/` and go to `claim_page`.
3. **Label from the PDF, not from the tool.** The sheet deliberately hides PaperLens's support rating. Do not open
   anything under `sealed_key/` or `raw/` until you have finished.
4. Do not change any column except `is_real_claim`, `evidence_correct` and `notes`. Do not reorder or delete rows.
5. Label every row in one pass per paper. Do not go back and adjust labels after seeing a score.

## Column 1: `is_real_claim` (y or n)

Question: **is this sentence, as printed in the paper, an assertion by the authors about what their own work found, shows,
achieves or contributes?**

Label `y` when the sentence states
- a result or measurement of this paper (a number, an effect, a comparison, an observation);
- a conclusion the authors draw from their own results;
- a contribution ("we introduce / propose / release ...") that the paper is supposed to deliver.

Label `n` when the sentence is
- background or motivation, or a statement about other people's work, even if it contains numbers;
- a description of method, procedure, data collection or study design with no finding in it;
- a statement of aims, future work, or what "should" be done;
- not a sentence of the paper's prose: table cells, figure or axis text, a caption, a heading run into text, a footnote,
  author or publisher information, or text so garbled you cannot tell what it says;
- cut off so that the assertion itself is missing (for example the sentence ends at "w/o." before saying anything).

Rules for edge cases
- A hedged finding ("our results suggest that ...") is still `y`.
- A sentence that mixes background and a finding of this paper is `y` if the finding is stated.
- A slightly damaged sentence (a missing space, a broken hyphen, a wrong symbol) is `y` if you can still tell what is claimed
  by reading the page; write what is wrong in `notes`.
- If the claim text does not appear on `claim_page` at all, label `n` and write "not on page" in `notes`.
- If you truly cannot decide, choose `n` and write "unsure" in `notes`. Do not leave it blank.

Examples from the **development** papers (see `eval/results/real_papers_audit.csv`; none of these papers is in this sheet):
- Deep Residual Learning, C4: the abstract sentence giving the ensemble's ImageNet test error. A result of the paper: `y`.
- Attention Is All You Need, C1: the abstract sentence saying that the best existing models connect encoder and decoder
  with attention. It describes prior work: `n`.
- ATLAS Higgs paper, C5: a string of plot labels and luminosity values that begins like a sentence. Figure text: `n`.
- Deep Residual Learning, C1: "we present a residual learning framework ...". A contribution: `y`.

## Column 2: `evidence_correct` (y, p or n; sometimes blank)

Fill this **only if `is_real_claim` is `y` and the `evidence` cell is not empty**. Otherwise leave it blank.

Read the `evidence` passage on `evidence_page` of the PDF. Question: **would a careful reader accept this passage as showing
where in the paper the claim is backed up?**

- `y` (supports): the passage reports the same finding. For a numeric claim the passage contains the claim's key number(s)
  for the same quantity, or the table row or sentence they come from. For a non-numeric claim it states the same result or
  describes the delivered contribution in the body of the paper.
- `p` (partial): the passage is about the same experiment or quantity but backs only part of the claim, or it points to where
  the support is ("Table 2 summarizes ...") without containing it, or it supports a weaker version of the claim.
- `n` (wrong): the passage is about something else, only shares words or a number by coincidence, contradicts the claim, is
  not prose from the paper body (figure text, table fragments with no identifiable row, headers), or is not on `evidence_page`.

Rules for edge cases
- Judge only the passage shown, not what else is on that page.
- A passage that merely restates the claim in almost the same words, with no data, method detail or result behind it, is `p`.
- A caption counts as evidence only for what the caption itself states.
- A table row counts as `y` only if you can tell which row and column the numbers belong to and they match the claim.
- Same number, different quantity (for example the claim's 3.5 is days and the passage's 3.5 is a score): `n`.
- If the passage is unreadable, `n` with "unreadable" in `notes`.

Examples from the **development** papers:
- Deep Residual Learning, C4: claim gives the ensemble's test error; the passage is the results sentence reporting that same
  error and pointing to the table: `y`.
- Attention Is All You Need, C5: claim gives a BLEU score reached after 3.5 days of training; the passage only states the
  training time and hardware: `p` (part of the claim, not the score).
- Deep Residual Learning, C1: claim is the contribution of the framework; the passage is a remark about a learning-rate
  schedule: `n`.
- ATLAS Higgs paper, C3: claim gives the significance of the observation; the passage is a fragment of plot axis values: `n`.

## `notes`

Free text. Use it for "unsure", "not on page", "unreadable", and for any parsing damage you notice.

## Optional second annotator

For a stronger result, a second person labels a **copy** of the blank sheet independently, without seeing the first set of
labels. Then:

```powershell
python -m eval.held_out_v2 score eval/results/held_out_v0.2 --second path\to\second_copy.csv
```

This reports raw agreement and Cohen's kappa for both columns. Report the first annotator's precision figures together with
the agreement; do not merge or "reconcile" labels after seeing scores. If kappa is below about 0.6, say so: the labels are
then too subjective for the precision figures to be trusted.

## Scoring

```powershell
python -m eval.held_out_v2 score eval/results/held_out_v0.2
```

The script refuses to run until every row has a valid label. It prints claim precision, evidence precision (strict = `y`
only; lenient = `y` or `p`), the end-to-end rate, coverage and abstention rate on real claims, a breakdown by PaperLens's
hidden support level, and 95% Wilson intervals. Definitions: `PROTOCOL.md` section 5.

## What this audit can and cannot show

- It measures **precision** of what PaperLens output on a sample of the claims it extracted. It does not measure recall
  (claims the tool missed), whether a better evidence passage existed elsewhere in the paper, or whether an abstention
  was right (whether the paper really has no supporting passage).
- 60 rows give wide intervals (roughly plus or minus 0.13 around 0.5). Evidence precision rests only on the rows that are
  real claims **and** were given a passage, which will be fewer, so its interval is wider; per-level figures rest on a
  handful of rows each.
- One annotator's judgement is subjective; the second-annotator option quantifies that.
- At most 13 papers from four kinds of source are not a random sample of the scientific literature.
- These labels are yours. Nobody else, and no AI assistant, fills in this sheet.
