# Held-out evaluation of PaperLens 0.2.0-dev: protocol

Written and committed on 2026-10-12 **before** any candidate paper was searched for, listed or downloaded. This file is part
of the freeze (`FREEZE_MANIFEST.json`): if it changes, `python -m eval.freeze_manifest verify` reports it.

Scope: a test of the frozen 0.2.0-dev code on papers it has never been run on. It is separate from the first held-out
evaluation (`eval/results/held_out/`, version 0.1.0), which is not touched, re-run or re-used.

## 1. What is frozen

- Code: every file listed in `FREEZE_MANIFEST.json` (`paperlens/`, `eval/`, `web/`, `tests/`, `requirements.txt`,
  `.gitignore`), with SHA-256 hashes, the Git commit they were taken from, and the installed package versions.
- Configuration: the linker constants in `paperlens/claims.py`, copied into the manifest. Abstention threshold
  `MIN_LEXICAL` = **0.30** (owner's decision of 2026-10-12), `MIN_LEXICAL_WITH_QUANTITY` = 0.12.
- Procedure and metric definitions: this file and `AUDIT_INSTRUCTIONS.md`.

No application code is changed during the evaluation. If a defect is found it is written to `KNOWN_BUGS.md` in this folder
and left unfixed.

## 2. Paper selection (fixed before searching)

Implemented in `eval/held_out_v2_select.py`. Every rule takes the **first** paper that satisfies it in a stated order, so
the choice cannot depend on the content of a paper or on how PaperLens handles it. PaperLens is not run on any candidate
before the single frozen run. The rules name sources, venues, categories and dates that were chosen without looking at
any listing.

Planned: **13 candidates**. The evaluation proceeds if at least 8 are obtained; with fewer it stops and the shortfall is
reported as a blocker.

| Rule | Source | Rule |
|---|---|---|
| A1-A4 | arXiv | For each of `cs.CV`, `cond-mat.mtrl-sci`, `q-bio.NC`, `econ.EM`: papers whose **primary** category is that one, submitted from 2024-03-01 00:00 UTC, in ascending order of submission (arXiv API); the first whose arXiv licence (OAI-PMH `arXivRaw`) is exactly CC BY 4.0. At most 60 candidates per category are examined. The latest version listed at retrieval time is downloaded. |
| B1-B3 | ACL Anthology | Paper `2024.acl-long.150`, paper `2023.emnlp-main.250`, paper `2024.naacl-long.50` (CC BY 4.0, as for all Anthology material from 2016). |
| C1-C3 | PLOS via Europe PMC | For each of PLoS Pathogens, PLoS ONE, PLoS Medicine: open-access articles of publication type `research-article` with licence CC BY and first publication date in 2023; the earliest date, and among articles of that date the lowest PMCID. |
| D1-D3 | Crossref | For each of eLife (ISSN 2050-084X), Nature Communications (2041-1723), Geoscientific Model Development (1991-9603): `journal-article` records published 2023-06-01 to 2023-06-30 with a CC BY licence in the Crossref record; the earliest publication date, and among those the DOI that sorts first. PDF address: the `application/pdf` link of the Crossref record, else the publisher's standard PDF address for that DOI. |

**Inclusion criteria** (all mechanical): the rule above selects it; licence CC BY as stated by the source's own metadata;
the file starts with `%PDF-` and opens in PyMuPDF; it has 6 to 80 pages; at least 60% of the words of the metadata title
are found on pages 1 and 2 (a check that the right file was fetched).

**Exclusion criteria**: already in `data/Papers/` or `data/held_out_papers/` (identifier, DOI, normalised title or
SHA-256); a title beginning with Correction, Author Correction, Publisher Correction, Erratum, Corrigendum, Retraction,
Editorial, Comment or Reply; fewer than 6 or more than 80 pages.

**What happens when a candidate fails**
- Excluded by a criterion in the previous paragraph, known from metadata or from opening the file: the next paper under
  the same rule is taken (at most 3 attempts per rule). This is part of the rule, and every skipped candidate is logged.
- The download fails (HTTP error, time-out after 3 tries, not a PDF, wrong file): the candidate is logged as failed and
  **not replaced**. A second address for the *same* article is tried only where the rule names one (Europe PMC, then the
  PLOS site; the Crossref link, then the publisher's address).

Everything examined, chosen, skipped or failed is written to `SELECTION_LOG.json`. Papers go to
`data/held_out_v0.2_papers/` with a `MANIFEST.csv` (title, source, identifier, DOI, licence, URLs, retrieval time, pages,
bytes, SHA-256, rule).

## 3. The run

One run, in this order, with nothing repeated or edited afterwards:

1. `python -m eval.freeze_manifest verify eval/results/held_out_v0.2/FREEZE_MANIFEST.json` must report no change.
2. `python -m eval.real_papers data/held_out_v0.2_papers eval/results/held_out_v0.2/raw`
3. `python -m paperlens analyze <each pdf> --out eval/results/held_out_v0.2/raw/analysis`
4. `python -m eval.freeze_manifest hash-outputs eval/results/held_out_v0.2/raw eval/results/held_out_v0.2/RAW_OUTPUT_HASHES.json`
5. The raw files and their hashes are committed **before** any aggregate is computed or any output is read.

A crash on a paper is a result and is reported; the paper is not dropped or re-run.

## 4. Audit sample and blinding

`python -m eval.held_out_v2 sample eval/results/held_out_v0.2`

- Population: every claim PaperLens extracted from the selected papers.
- Sample: **60 claims** (all of them if fewer were extracted), seed 20261012. Each paper contributes at least 3;
  quotas are proportional to each paper's claim count; within a paper the draw is proportional across PaperLens's support
  levels. This is the sampling method of the first held-out audit with a larger target, because abstention leaves fewer
  rows with a passage to judge.
- The sheet `held_out_audit.csv` shows paper, claim, claim page, the top evidence passage and its page, and blank label
  columns. It does **not** show the support rating, the scores, the evidence status or the section labels.
- The key (`held_out_audit_key.csv`) and the sample description (`held_out_sample_info.json`) are moved to the subfolder
  `sealed_key/`. The annotator does not open `sealed_key/` or `raw/` until labelling is finished.
- Labelling rules: `AUDIT_INSTRUCTIONS.md` (the rules of the first audit, unchanged in substance).
- Only a person's labels count as ground truth. No label is written by the tool or by an AI assistant. If an AI-assisted
  pass is ever made it goes in a separate folder and is reported separately.

## 5. Measures

Automatic, over **all** extracted claims, available immediately (`python -m eval.held_out_v2 auto ...`):

| Measure | Definition |
|---|---|
| Coverage | claims with at least one returned passage / extracted claims |
| Abstention rate | claims with status `no_supporting_evidence` / extracted claims |
| Unsearchable rate | claims with status `no_searchable_text` / extracted claims |
| Support distribution | count of strong / moderate / weak / none |
| Page checks | claim text, and top evidence quote, found on the cited page |
| Crashes, parse warnings | per paper |

These say how often PaperLens answers, not whether its answers are right.

From the human-labelled sample, available only when every row is labelled (`python -m eval.held_out_v2 score ...`):

| Measure | Definition |
|---|---|
| Claim precision | rows labelled real claim / rows |
| Coverage on real claims | real claims shown with a passage / real claims |
| Abstention rate on real claims | real claims shown without a passage / real claims |
| Evidence precision, strict | passages labelled `y` / real claims shown with a passage |
| Evidence precision, lenient | passages labelled `y` or `p` / real claims shown with a passage |
| End-to-end | rows that are a real claim with a `y` passage / rows |
| Strict precision by support level | as strict precision, within strong, moderate, weak |

Every proportion is reported with a 95% Wilson score interval and its counts. With an optional second annotator: raw
agreement and Cohen's kappa for both label columns.

**Fixed in advance about interpretation**
- The comparison with 0.1.0 is between two different sets of papers (8 then, up to 13 now) and, for 0.1.0, AI-assisted
  labels only. It is not a paired comparison and cannot by itself show that 0.2.0-dev is better or worse.
- Reference values from the 0.1.0 held-out sample (AI-assisted, not human): claim precision 0.82, strict evidence
  precision 0.16, lenient 0.62.
- Whether an abstention was right (the paper really has no supporting passage) is **not** measured: the sheet does not ask
  the annotator to search the paper.
- Recall of claims is not measured.

## 6. What may not happen

- No tuning, re-running or code change in response to these papers or their labels.
- No use of the first held-out set, its key, its raw outputs or its AI audits.
- No replacement of a paper because its output looks bad.
- No reporting of these results as covering scanned PDFs, non-English papers or publishers not in the sample.
