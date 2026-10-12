# Second held-out paper set (for PaperLens 0.2.0-dev)

11 genuine open-access research papers (286 pages, 66.9 MB) retrieved on 2026-10-12 between 07:11 and 07:18 UTC, **after**
the code, the selection rules and the evaluation procedure were frozen (`eval/results/held_out_v0.2/FREEZE_MANIFEST.json`,
Git tag `v0.2.0-dev-frozen-heldout2`). None is in the development set `data/Papers/` or in the first held-out set
`data/held_out_papers/` (checked by identifier, DOI, title and SHA-256). **Do not use them to develop or tune anything.**

`MANIFEST.csv` has one row per file: title, source, identifier, DOI, licence, URLs, retrieval time (UTC), pages, bytes,
SHA-256 and the rule that selected it. All 11 are CC BY according to the source's own metadata. `.gitignore` excludes the
PDFs to keep the repository small.

## How the papers were chosen

By the rules of `eval/results/held_out_v0.2/PROTOCOL.md` section 2, implemented in `eval/held_out_v2_select.py`, both
committed before any listing was requested. Each rule takes the first paper that satisfies it. PaperLens was not run on
any candidate before the single frozen run. The full record is `eval/results/held_out_v0.2/SELECTION_LOG.json`.

| Rule | Source | Result |
|---|---|---|
| A1-A4 | arXiv, first CC BY 4.0 paper submitted from 2024-03-01 with primary category cs.CV, cond-mat.mtrl-sci, q-bio.NC, econ.EM | 4 papers |
| B1-B3 | ACL Anthology 2024.acl-long.150, 2023.emnlp-main.250, 2024.naacl-long.50 | 3 papers |
| C1-C3 | first CC BY research article of 2023 in PLoS Pathogens, PLoS ONE, PLoS Medicine (Europe PMC) | 2 papers; the PLoS ONE pick could not be downloaded |
| D1-D3 | first CC BY article of June 2023 in eLife, Nature Communications, Geoscientific Model Development (Crossref) | 2 papers; the Nature Communications pick could not be downloaded |

In every rule the first candidate examined was the one taken; no candidate was skipped by an exclusion criterion.

## Downloads that failed (not replaced)

- PLoS ONE, PMC10659152: `https://europepmc.org/articles/PMC10659152?pdf=render` returned HTTP 403. The Europe PMC record
  carried no DOI, so the second address named by the rule (the PLOS site, built from the DOI) was malformed and returned
  HTTP 404. That is a weakness of the selection script, found after the freeze; the script was not changed and the paper
  was not fetched another way.
- Nature Communications, doi:10.1038/s41467-023-37979-8: `https://www.nature.com/articles/s41467-023-37979-8.pdf` returned
  an HTML page instead of a PDF. Not bypassed.

Thirteen candidates were planned and eleven obtained. The two failures were not replaced, so the set is exactly what the
rules produced. Both failures remove a large mainstream journal, which narrows the set.

## Limits of this set

Eleven papers from five kinds of source. Seven come from sources whose layouts are also in the development set (arXiv, ACL,
PLOS). eLife is a publisher layout PaperLens had not been run on; Copernicus was in the first held-out set. Scanned
PDFs, non-English papers and most publishers are not represented. The rules pick the first paper of a period, not a random
one.
