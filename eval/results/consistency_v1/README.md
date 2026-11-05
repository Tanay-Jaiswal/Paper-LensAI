# Numbers check (1.1.0): results on 35 real papers

Command (run from the repository, PDFs kept outside it):

```powershell
python -m eval.consistency_eval ..\data\Papers ..\data\held_out_papers ..\data\held_out_v0.2_papers --out eval\results\consistency_v1
```

Files: `checks.csv` (every recomputed statement), `summary.json` (counts), `heldout_run_frozen_c9dd441.txt` (the first
run on the held-out folders, before any fix; `c9dd441` is the start of the SHA-256 of `paperlens/consistency.py` at
that moment).

## Protocol and what changed after looking

1. The checks were written while looking only at the 16 development papers in `data/Papers`.
2. The code was frozen (hash above) and run once on the 19 held-out PDFs (`held_out_papers`, `held_out_v0.2_papers`).
   That run is saved unchanged.
3. Reviewing that run found false alarms of three kinds, and the rules were changed:
   - a "Level: 1" category column was added into a row total (fix: retry without the first cell);
   - a table with region subtotal rows was summed twice (fix: read the column as groups closed by subtotal rows, and
     never sum columns of averages, rates or percentages);
   - F1 values averaged over runs differ slightly from the harmonic mean of the averaged P and R (fix: a gap of at
     most 1 point is reported as "not reproduced", not as an error).
4. **Because of step 3, the held-out folders are development data for this feature from now on.** The numbers below
   are after the fixes and are not a held-out result.

## Results after the fixes (35 papers: 16 development + 19 formerly held-out)

| | Papers | Papers with ≥1 check | Checks | Check out | Not reproduced | Do not add up |
|---|---|---|---|---|---|---|
| `data/Papers` | 16 | 3 | 25 | 22 | 3 | 0 |
| `held_out_papers` | 8 | 3 | 50 | 41 | 8 | 1 |
| `held_out_v0.2_papers` | 11 | 2 | 26 | 23 | 0 | 3 |
| **All** | **35** | **8** | **101** | **86** | **11** | **4** |

Checks by kind: F1 from P and R 34, column totals 23, percentages of counts 15, confidence intervals 11, row totals 10,
row averages 8. No stated change, fold change or p-value statement in these 35 papers matched the patterns.

## Review of every flag (by the AI session that wrote the code, against the PDF text; not an independent person)

| Paper | Flag | Verdict |
|---|---|---|
| PLOS Med, PEBRA trial (`pmc_PMC9810159`), p.11 | Table 2 footnote: "22/307 (8.5%)". 22 of 307 is 7.2%. Page 8 says "Of all 258 participants in care, 22 (8.5%)". | **Real inconsistency**: the footnote uses the wrong denominator (258 gives 8.5%). |
| same paper, p.2 and p.10 | "23 of 157 (14.7%)": 23/157 = 14.6497%, which rounds to 14.6%. | **Real but trivial** rounding slip, reported with low severity. |
| PLoS NTD, snakebite in Brazil (`pmc_PMC7875335`), p.7 | Table 1, "No. snakebites": the seven North-region states add up to 45,585, the "North region" row says 45,492. The other four regions and the Brazil total agree. Checked in the raw PDF text. | **Real inconsistency** of 93 cases (Roraima and Amapá print identical counts, 1,842 and 368, with different rates, which suggests a copied cell). |
| GPT-3 (`arxiv_2005.14165`), p.19 | SuperGLUE "Average" is not the mean of the 5 columns shown. | Correctly **not reproduced**: the table is split and the average covers columns not on that row. |
| SetGNER (`acl_2022.emnlp-main.200`), p.6 | 8 F1 values 0.02 to 0.57 points from the harmonic mean of P and R. | Correctly **not reproduced**: consistent with F1 averaged over runs. |

So: 4 of 4 "does not add up" flags are real inconsistencies in the published PDFs (2 substantive, 2 trivial rounding),
and the 11 "not reproduced" results have a legitimate explanation. Consistent checks were spot-read, not reviewed one
by one.

## What this does not show

- **Coverage is low**: 27 of 35 papers produced no check at all, because their arithmetic is not written in a form the
  patterns recognise (most ML papers state numbers without the operands next to them).
- **Recall is unknown**: nobody listed every inconsistency in these papers. One known miss: in the same snakebite table,
  "% deaths" for Alagoas is printed as 0.01 although 1 death in 1,607 cases is 0.06%; ratio-of-columns checks do not
  exist yet.
- 4 flags in 35 papers is far too few to quote a precision figure; it is evidence that the checks can find real errors,
  not a measured error rate.
- No result here was checked by an independent person.
