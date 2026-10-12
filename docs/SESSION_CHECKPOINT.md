# PaperLens AI session checkpoint (2026-10-12)

Written by the session working in the repository, after running the commands in `docs/TEST_REPORT.md`.

## State
- Location `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`; branch `dev/evidence-linking-v0.2`; code version `0.2.0-dev`.
- Tag `v0.1.0-frozen-heldout` = commit `d6951bf` (version 0.1.0, the one run on the held-out papers). Not moved.
- Everything is committed locally. Nothing was pushed, published or deleted.
- Use the project environment: `.venv\Scripts\python.exe -m pytest -q` (the system Python has no pytest).

## What the earlier checkpoint got wrong
- It listed the dev audit as not done; the WIP commit already held pooled dev pairs, AI labels and a threshold sweep.
- The dev labels came from the session that wrote the fixes, not from a fresh blind labeller.
- `MIN_LEXICAL` had been raised from 0.30 to 0.35 right after a sweep on the dev labels. It is 0.30 again.
- No regression tests for the fixes existed.

## PASS (run in this session)
- `pytest`: 44 passed before any change; **106 passed, 0 failed** at the end.
- Synthetic benchmark seeds 7 and 99: all evidence measures 1.0.
- SciFact dev: hit@1 0.493 (0.488 in 0.1.0), AUROC 0.810 (0.804).
- 16 development papers: 0 crashes.
- Protected files: tracked held-out and audit files identical to the tag; raw held-out outputs match their recorded
  hashes (10/10); held-out PDFs match their manifest (8/8); tagged code matches `FREEZE.json` (14/14). The key, the sample
  info and the contents of `raw/` were not opened.
- Web UI renders with the synthetic demo papers, including the abstention text.

## WORSE than 0.1.0 (measured on development papers)
- Real claims with a returned passage: 0.979 -> 0.619.
- Real claims with fully supporting evidence: 0.289 -> 0.247 (0.258 if the one unlabelled pair is correct).
- `unsupported_claim` flags: 56 -> 80.

## BETTER (AI-assisted labels on development papers; not human, not unseen)
- Returned passages labelled wrong: 35 -> 11. Strict precision 0.295 -> 0.407 (intervals overlap). Lenient 0.632 -> 0.814.

## NOT VERIFIED
- Anything about unseen papers for 0.2.0-dev. No held-out result exists for this version.
- Any human-labelled figure for any version. The human audit sheet is still blank.
- Whether 0.30 was originally read off the SciFact train curve.
- The web UI and the "not assessed" handling on a real scanned paper.
- Each fix on its own (no ablation).

## Next steps, in order
1. Owner: keep `MIN_LEXICAL` at 0.30 or choose another value from the SciFact train curve alone (docs/EVALUATION.md 6.3).
2. Owner: label the existing held-out sheet by hand (never filled in by the assistant).
3. Optional: a fresh blind labeller for the development pairs, including the one unlabelled pair.
4. When the owner says the fixes are stable: follow docs/EVALUATION.md section 7 (freeze code and procedure, then a new
   unseen set). Do not download anything before that.

## Must remain untouched
`eval/results/held_out/` (including the key, sample info and `raw/`), `eval/results/held_out_ai_audit/`,
`eval/results/held_out_ai_audit_2/`, `data/held_out_papers`, the tag `v0.1.0-frozen-heldout`, the 0.1.0 result files in
`eval/results/`, and sections 1 to 5 of docs/EVALUATION.md.
