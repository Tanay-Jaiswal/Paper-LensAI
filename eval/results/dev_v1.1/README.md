# 1.1.0 re-evaluation after the glossary change (development data only)

What changed in the engine since 0.6.1-dev: claim-to-evidence ranking now expands abbreviations the paper defines
("FEM" also matches "finite element method", and the reverse). The PDF parser (`paperlens/ingest.py`) is unchanged, and
the Numbers check, Revision checklist and Glossary only add outputs. Held-out folders, sealed keys and the held-out
scorer were not used.

Commands (PDFs kept outside the repository, in `../data/Papers`):

```powershell
python -m eval.run_eval --n 100 --seed 7 --out eval\results\dev_v1.1\seed7
python -m eval.scifact_eval --data-dir data\scifact --out eval\results\dev_v1.1
python -m eval.real_papers ..\data\Papers eval\results\dev_v1.1
python -m eval.claim_map map     eval\results\dev_v0.6.1\real_papers_audit.csv eval\results\dev_v1.1\real_papers_audit.csv eval\results\dev_v0.6.1\label_map\dev_pairs_labelled_merged.csv eval\results\dev_v1.1\label_map
python -m eval.claim_map merge   eval\results\dev_v0.6.1\label_map\dev_pairs_labelled_merged.csv eval\results\dev_v1.1\label_map\fresh_labels_ai_assisted.csv eval\results\dev_v1.1\label_map\dev_pairs_labelled_merged.csv
python -m eval.claim_map compare eval\results\dev_v0.6.1\real_papers_audit.csv eval\results\dev_v1.1\real_papers_audit.csv eval\results\dev_v1.1\label_map\dev_pairs_labelled_merged.csv eval\results\dev_v1.1\claim_compare.json
```

## Before and after

| Evaluation | 0.6.1-dev | 1.1.0 | Reading |
|---|---|---|---|
| Synthetic benchmark, seed 7 (100 generated papers, 168 measures) | as recorded | **identical, all 168 values** | the generated papers define no abbreviations |
| SciFact dev (rationale ranking, evidence presence, retrieval; 20 values) | as recorded | **identical, all 20 values** | scored on abstracts without a paper glossary |
| Development papers: claims extracted | 144 | 144, identical in text | |
| Development papers: top evidence passage unchanged | | 131 of 144 | 13 changed |
| Coverage (real claims with a passage) | 59/99 = 0.596 (95% CI 0.50 to 0.69) | **63/99 = 0.636** (0.54 to 0.72) | +4 claims answered |
| Strict precision (passage supports the claim) | 22/59 = 0.373 (0.26 to 0.50) | **24/63 = 0.381** (0.27 to 0.50) | |
| Lenient precision (supports or partly supports) | 48/59 = 0.814 (0.70 to 0.89) | **50/63 = 0.794** (0.68 to 0.88) | slightly lower |
| PDF parsing (tables, layout, sections) | | not re-run | `ingest.py` unchanged, so these cannot move |

**What this shows:** PaperLens now returns a passage for 4 more of the 99 real claims. Strict precision is about the same,
and lenient precision is 2 points lower, because 3 of the 8 new passages are wrong. Every confidence interval overlaps
the old one almost completely, so **no improvement and no loss is demonstrated**; the change is small on these 16 papers.

## Labels

The 8 passages that had no label (newly returned, or replaced for a real claim) were labelled y/p/n in
`label_map/fresh_labels_ai_assisted.csv`: 1 y, 4 p, 3 n. **These are AI-assisted labels by the same session that wrote
the glossary change, so not independent and not human.** All other labels are carried over unchanged from 0.6.1-dev by
`eval.claim_map` (identical claim and identical passage only). The original label file was not modified.
