# PaperLens AI session checkpoint (2026-10-12)

Written by the session working in the repository, after running the commands below. Supersedes the 2026-10-11 checkpoint,
which was written from thread records without access to the repository.

## State
- Location `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`; branch `dev/evidence-linking-v0.2`; code version `0.2.0-dev`.
- Tag `v0.1.0-frozen-heldout` = commit `d6951bf` (version 0.1.0, the one run on the held-out papers). Not moved.
- Nothing pushed; there is no remote activity from this session.
- Use the project environment: `.venv\Scripts\python.exe -m pytest -q` (the system Python has no pytest).

## Differences found between the earlier checkpoint and the repository
- The earlier checkpoint said the dev-only audit was "not done". The WIP commit `aeec14f` already contained pooled
  development pairs, AI labels for them, a SciFact train curve and a threshold sweep over the labelled development pairs.
- The labels were not made by a fresh blind labeller as planned; the same session that wrote the fixes labelled them.
- `MIN_LEXICAL` was 0.35 in the code, but the labels and the SciFact train curve were made at 0.30. File times show it was
  raised to 0.35 right after the sweep on the development labels. It is back at 0.30 (docs/EVALUATION.md section 6.3).
- No regression tests for the fixes existed (44 tests). There are now 101.

## PASS (run in this session)
- `python -m pytest -q`: 44 passed before any change; **101 passed** at the end.
- Synthetic benchmark, seeds 7 and 99, n=100: evidence measures all 1.0 (equal to or better than 0.1.0).
- SciFact dev ranking: hit@1 0.493 (0.488 before), AUROC 0.810 (0.804 before).
- `eval.real_papers` on the 16 development papers: 0 crashes.
- Tracked protected files identical to the tag (`git diff v0.1.0-frozen-heldout` is empty for `eval/results/held_out*`,
  both AI audit folders, the earlier result files and sections 1 to 5 of docs/EVALUATION.md). The key, sample info and
  `raw/` were not opened.
- `dev_pairs_labelled.csv` matches the sha256 in `DEV_LABELS_LOCKED.txt`.

## WORSE than 0.1.0 (measured)
- Coverage on the development papers: real claims with a passage 0.979 -> 0.619 (AI-assisted labels).
- Real claims with fully supporting evidence 0.289 -> 0.247 (0.258 if one unlabelled pair is correct).
- `unsupported_claim` gap flags on the development papers 56 -> 81.

## BETTER (measured, AI-assisted labels on development papers, not human, not unseen)
- Returned passages labelled wrong 35 -> 11; strict precision 0.295 -> 0.407; lenient 0.632 -> 0.814.

## NOT VERIFIED
- Anything about unseen papers for 0.2.0-dev. No held-out result exists for this version.
- Any human-labelled figure. The human audit sheet for the held-out papers is still blank.
- `data/held_out_papers/*.pdf` are not tracked by Git, so their integrity was not checked here.
- The web UI in a browser (only a text check of `web/app.js`).
- Whether 0.30 was originally read off the SciFact train curve.

## Next steps
1. Owner decision: keep `MIN_LEXICAL` at 0.30, or choose another value from the SciFact train curve alone (section 6.3)
   and say why. Do not choose it from the development labels.
2. Optional: a fresh blind labeller for the development pairs (the current labels are from the session that wrote the fixes),
   including the one unlabelled pair.
3. Only when the owner asks and the code and procedure are frozen: a new unseen set for a held-out test of this version.
4. The owner's human labels on the existing held-out sheet remain to be done; never fill that sheet in for them.

## Must remain untouched
`eval/results/held_out/` (including the key, sample info and `raw/`), `eval/results/held_out_ai_audit/`,
`eval/results/held_out_ai_audit_2/`, `data/held_out_papers`, the tag `v0.1.0-frozen-heldout`, the earlier result files in
`eval/results/`, and sections 1 to 5 of docs/EVALUATION.md.
