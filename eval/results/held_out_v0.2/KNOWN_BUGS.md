# Problems seen in the held-out run of 0.2.0-dev (not fixed, not investigated)

Noticed in the automatic summary of the single frozen run of 2026-10-12. Nothing was fixed and nothing was re-run; the code
is unchanged since the freeze (`python -m eval.freeze_manifest verify eval/results/held_out_v0.2/FREEZE_MANIFEST.json`).
Causes were deliberately not investigated on these PDFs, because diagnosing them here would be tuning on the held-out set.
Any fix belongs to a later version, evaluated on yet another unseen set.

| # | Paper | What happened |
|---|---|---|
| 1 | all | Only 33 claims were extracted from 11 papers (286 pages): 3 per paper, against 10 per paper in the first held-out run and 9 on the development papers. Claim extraction was not changed between versions, so this is how the extractor behaves on these papers, not an effect of the evidence fixes |
| 2 | arxiv_2403.00458v2 (econ.EM, 55 pages) | No claim extracted at all. 17 pages produced no sentences; no "Abstract" heading was detected; 38 sentences were labelled front matter |
| 3 | acl_2023.emnlp-main.250 | 2 claims, both without a passage, although 147 sentences were labelled experiments |
| 4 | arxiv_2403.00209v2 (cs.CV) | 2 claims, both without a passage; no "Abstract" heading detected |
| 5 | doi_10.5194-gmd-16-3029-2023 (Copernicus, 53 pages) | No results or experiments section detected; 437 sentences labelled `other`; no "Abstract" heading detected (the same Copernicus layout problem as in the first held-out run) |
| 6 | doi_10.7554-elife.76927 | 1 claim from a 25-page paper; no "Abstract" heading detected |
| 7 | arxiv_2403.00204v1, arxiv_2403.00458v2 | The extracted title does not start like the manifest title (one has LaTeX markup in its metadata title; neither was examined further) |
| 8 | selection script | The second download address for a PLOS article is built from the DOI and is malformed when Europe PMC gives none (see `data/held_out_v0.2_papers/README.md`) |
