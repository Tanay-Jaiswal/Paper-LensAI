# Held-out evaluation of PaperLens 0.2.0-dev: results so far (2026-10-12)

**Status: automatic measures only. No precision figure exists yet, because no person has labelled the sheet.**
No label was written by the tool or by an AI assistant.

## What was done, in order

| Step | When (UTC) | Record |
|---|---|---|
| Protocol, selection rules and tooling committed | before 07:11 | commit `60b02f8`, `PROTOCOL.md` |
| Freeze: 46 files, constants, package versions | 07:11:52 | `FREEZE_MANIFEST.json`, tag `v0.2.0-dev-frozen-heldout2` (commit `a549f25`) |
| Selection and download by the frozen rules | 07:11:57 to 07:18:03 | `SELECTION_LOG.json`, `data/held_out_v0.2_papers/MANIFEST.csv` |
| Single run on the 11 papers | after 07:18 | `raw/` (37 files), `RAW_OUTPUT_HASHES.json`, commit `a2246fb`, made before any output was read |
| Blinded sheet | after the raw commit | `held_out_audit.csv`; key in `sealed_key/` |

13 candidates were planned and 11 obtained; 2 downloads failed and were not replaced. The freeze verified unchanged
before the run, after the run and at the end.

## Automatic measures (all 33 extracted claims; not precision)

| Measure | Value |
|---|---|
| Papers run / crashed | 11 / 0 |
| Pages | 286 |
| Claims extracted | 33 (one paper yielded none) |
| Coverage: claims with a returned passage | 0.697 (23/33; 95% CI 0.53-0.83) |
| Abstention rate: "No supporting evidence found" | 0.303 (10/33; 95% CI 0.17-0.47) |
| "Evidence search not possible" | 0.000 (0/33; 95% CI 0.00-0.10) |
| Claim text found on its cited page | 33 / 33 |
| Top evidence quote found on its cited page | 23 / 23 |
| Papers with a parse warning | 4 / 11 |

| Paper | Pages | Claims | With a passage | Abstained |
|---|---|---|---|---|
| ACL 2023.emnlp-main.250 | 15 | 2 | 0 | 2 |
| ACL 2024.acl-long.150 | 13 | 5 | 4 | 1 |
| ACL 2024.naacl-long.50 | 14 | 2 | 1 | 1 |
| arXiv 2403.00204v1 (cond-mat.mtrl-sci) | 25 | 5 | 5 | 0 |
| arXiv 2403.00209v2 (cs.CV) | 18 | 2 | 0 | 2 |
| arXiv 2403.00458v2 (econ.EM) | 55 | 0 | 0 | 0 |
| arXiv 2403.00947v1 (q-bio.NC) | 24 | 2 | 1 | 1 |
| Copernicus gmd-16-3029-2023 | 53 | 5 | 2 | 3 |
| eLife 76927 | 25 | 1 | 1 | 0 |
| PLoS Medicine PMC9810159 | 16 | 7 | 7 | 0 |
| PLoS Pathogens PMC9815661 | 28 | 2 | 2 | 0 |

These numbers say how often PaperLens answers. They say nothing about whether a returned passage supports its claim or
whether an abstention was justified.

The split of the 23 returned passages by support level (strong, moderate, weak) is deliberately **not** shown here: every
extracted claim is in the audit sheet, and the per-paper split could reveal the hidden rating of individual rows. It is in
`sealed_key/AUTOMATIC_MEASURES_full.txt`, to be opened after labelling.

## The audit sheet

- The protocol planned 60 sampled claims. Only 33 were extracted, so **the sheet contains all 33**; there is no sampling.
- 23 rows show an evidence passage and 10 show none.
- Columns: row, paper_id, paper_file, claim_id, claim_page, claim, evidence_page, evidence, and three blank columns to
  fill: `is_real_claim`, `evidence_correct`, `notes`. Support ratings, scores, statuses and section labels are not in it.
- Instructions: `AUDIT_INSTRUCTIONS.md`. Scoring: `python -m eval.held_out_v2 score eval/results/held_out_v0.2` (refuses
  until every row is labelled; checked: it refused with 33 of 33 rows unlabelled).

## What the labels will and will not be able to show

- Evidence precision will rest on at most 23 passages, fewer once rows that are not real claims are removed. With about
  20 passages a 95% interval is roughly plus or minus 0.2 (for example 8 of 20 gives 0.22 to 0.61). Per-level precision
  will rest on a handful of rows and should not be interpreted.
- Claim precision will rest on 33 rows (about plus or minus 0.15).
- The comparison with 0.1.0 is not paired: different papers (8 then, 11 now), and for 0.1.0 only AI-assisted labels exist
  (claim precision 0.82, strict evidence precision 0.16, lenient 0.62). With intervals this wide, only a large difference
  would be visible.
- Not measured: recall of claims; whether a better passage existed; whether each abstention was right.
- 11 papers chosen as "the first of a period" from five kinds of source are not a random sample of the literature. Two
  mainstream journals dropped out through failed downloads.
- The low number of extracted claims (see `KNOWN_BUGS.md`) is itself a result: on these papers the extractor finds few
  claims to audit, and one 55-page paper yields none.

## Reproduce

```powershell
git checkout v0.2.0-dev-frozen-heldout2
python -m venv .venv ; .venv\Scripts\Activate.ps1 ; pip install -r requirements.txt     # exact versions used: FREEZE_MANIFEST.json "packages"
python -m eval.freeze_manifest verify eval/results/held_out_v0.2/FREEZE_MANIFEST.json
python -m eval.held_out_v2_select <new empty papers folder> <new empty results folder>   # re-selects by the same rules; refuses to overwrite the recorded set
python -m eval.real_papers data/held_out_v0.2_papers <new results folder>/raw
python -m paperlens analyze data/held_out_v0.2_papers/<file>.pdf --out <new results folder>/raw/analysis     # once per PDF
python -m eval.freeze_manifest check-outputs eval/results/held_out_v0.2/raw eval/results/held_out_v0.2/RAW_OUTPUT_HASHES.json
python -m eval.held_out_v2 auto  eval/results/held_out_v0.2
python -m eval.held_out_v2 score eval/results/held_out_v0.2          # after the sheet is labelled
```

The tag holds the code, protocol and manifest; the selection log, raw outputs, sheet and this file are on branch
`dev/evidence-linking-v0.2`. Re-running the analysis reproduces the claims and passages; the two log files and the
`seconds` fields differ between runs, so `check-outputs` is a check of the stored files, not of a re-run. Source listings can
change over time (new arXiv versions, corrected metadata), so a later re-selection may not return the same 11 papers; the
recorded set is fixed by the SHA-256 column of the manifest.
