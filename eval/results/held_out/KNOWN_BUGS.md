# Bugs and weaknesses seen in the held-out run (not fixed)

Noticed while reading the raw output of the frozen run of 2026-10-11 (`raw/real_papers_summary.json`,
`raw/real_papers_audit.csv`). Nothing here has been fixed and nothing was re-run: the code in `paperlens/` is unchanged since
the freeze (`python -m eval.freeze verify eval/results/held_out/FREEZE.json`). Causes marked "not investigated" were left
alone on purpose, because diagnosing them on these PDFs would be tuning on the held-out set.

Any fix must be evaluated as a **separate, later run** written to a new folder (for example `eval/results/held_out_v2/`), and
reported next to these original results, never in place of them. Once a fix has been developed against these 8 papers they
are no longer held out for that version; a new unseen set is needed to measure it.

| # | Paper | What happened | Cause |
|---|---|---|---|
| 1 | arxiv_2303.00194v1 (astro-ph) | Title is extracted with trailing text "Submitted to A..." appended | A journal note is set in the same font size as the title (title picker takes every line of the largest size in the top half) |
| 2 | arxiv_2303.00141v2 (cs.LG, 66 pages) | 559 sentences labelled introduction, 404 appendix, none results or experiments; 10 of 13 claims rated `none` | Body section headings were not recognised after the introduction. Not investigated |
| 3 | pmc_PMC7875335, pmc_PMC7875355 (PLOS) | No section labelled method or results; 183 and 215 sentences labelled `other`; "no results/experiments section" warning | Not investigated. The same journals' layout parsed correctly in the development set |
| 4 | pmc_PMC7886193 (PLOS Genetics) | 324 sentences `other`, only 29 results | Not investigated |
| 5 | copernicus_acp-21-8357-2021 | "No 'Abstract' heading detected"; front matter used as the abstract | Copernicus prints "Abstract." run into the first line of the abstract instead of as a heading |
| 6 | acl_2022.emnlp-main.200 | A claim is cut at "our model (w/o." | The sentence splitter treats "w/o." as the end of a sentence |
| 7 | arxiv_2303.00194v1 | Page 6 yields no sentences | Not investigated (probably a full-page figure or table) |
| 8 | 5 of 8 papers | Hyperparameters and data splits marked not applicable, including a computational modelling paper (pmc_PMC7875355) | The rule is a vocabulary test for model training; whether it is right for a simulation paper is a judgement call |
| 9 | 2 claims (arxiv_2303.00141v2 C3, pmc_PMC7875335 C7) | No evidence passage attached at all (rated `none`) | Not investigated |

Automatic checks on this run: 0 crashes; 7 of 8 titles match the manifest; 80 of 80 claim texts are on the cited page; 78
claims have a top evidence passage and all 78 quotes are on the cited page. These checks say nothing about whether claims are real or evidence is relevant.
