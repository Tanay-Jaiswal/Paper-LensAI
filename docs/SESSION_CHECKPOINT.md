# PaperLens AI session checkpoint (2026-10-12, pre-reset sprint)

Written by the session that did the work, from commands it ran (`docs/TEST_REPORT.md`, section "0.3.0-dev").
The previous checkpoint is in Git: `git show 45b2ca2:docs/SESSION_CHECKPOINT.md`.

## Verified state
- Folder `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`. Working tree was clean at the start (`git status`), no stash.
- New branch `dev/partial-support-v0.3`, created from `dev/evidence-linking-v0.2` at `45b2ca2`. Code commit `a301d1a`
  (this file is in the commit after it). Code version `0.3.0-dev`.
- `dev/evidence-linking-v0.2` is still `45b2ca2`; `main` is `d6951bf`.
- Tags unmoved: `v0.1.0-frozen-heldout` = `d6951bf`, `v0.2.0-dev-frozen-heldout2` = `a549f25`.
- No remote is configured. Nothing was pushed or published.
- Use `.venv\Scripts\python.exe` (written `PY` below); the system Python has no pytest.

## What was done and why
1. **Diagnosis** (docs/EVALUATION.md 9.1). Of the 24 top passages labelled partial on the 16 development papers
   (AI-assisted labels), 13 are compound claims where the passage supports one part, 7 describe an experiment or point
   to a table without the result, 4 restate the claim. Compound claims are the largest single cause.
2. **Change** (`paperlens/claims.py`): `_complementary` keeps the top passage and gives places 2 and 3 first to
   accepted passages that match a claimed figure not matched yet. `quantity_coverage` records per claim which claimed
   figures were found (`Claim.quantity_coverage`, flag `partial_quantity_coverage`); the Markdown report and
   `web/app.js` show "k of n claimed figures matched; not found: ...". Thresholds, abstention and ratings unchanged.
3. **Experiment not adopted**: making `strong` require full coverage by the top passage would demote 3 `y`, 1 `p`,
   1 `n` (15/20 to 12/15 strict). Not justified; a test pins the unchanged rule.
4. New script `eval/quantity_coverage.py`; 13 regression tests in `tests/test_compound_claims_v03.py` (negative cases
   included); docs updated (README versions, EVALUATION 9, KNOWN_LIMITATIONS, TEST_REPORT).

## Commands and exact outcomes
| Command | Outcome |
|---|---|
| `PY -m pytest -q` | 106 passed before; **119 passed, 0 failed** after |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.3` | 16 papers, 0 crashed, 145 claims; rows identical to 0.2.0-dev |
| `PY -m eval.dev_pairs score-labelled eval/results/dev_v0.2/real_papers_audit.csv eval/results/dev_v0.3/real_papers_audit.csv eval/results/dev_v0.2` | before = after: coverage 0.619 (60/97), strict 0.407 (24/59), lenient 0.814 (48/59), wrong passages 11, abstentions on real claims 37 |
| `PY -m eval.quantity_coverage data/Papers eval/results/dev_v0.3 eval/results/dev_v0.2/dev_pairs_labelled.csv` | claimed figures matched by the 3 returned passages **78 to 84 of 143**; claims fully covered **20 to 22 of 51** |
| `PY -m eval.run_eval --n 100 --seed 7 --out eval/results/dev_v0.3/seed7` (and seed 99) | identical to dev_v0.2 except timings |
| `PY -m eval.scifact_eval --out eval/results/dev_v0.3` | identical to dev_v0.2 except timings |

**Honest reading:** no regression, and no gain in top-passage precision (the top passage is the same by design). The
gain is 6 more claimed figures shown with a passage, plus an explicit list of unmatched figures. Whether the added
passages are correct is unlabelled. Nothing was measured on unseen papers.

## Known bugs, ranked by expected impact
1. Claim extraction collapses on some layouts: 3 claims per paper on the second held-out run, none for one 55-page
   paper; "Abstract" heading not detected in 5 papers (`eval/results/held_out_v0.2/KNOWN_BUGS.md` items 1 to 6). Not
   investigated on those PDFs on purpose.
2. Section classification: Copernicus layout yields no results section (437 sentences `other`).
3. Partial support for claims without figures (16 of 24 partial passages): experiment descriptions, table pointers and
   restatements still returned as `weak` evidence.
4. 59 of 143 claimed figures on development papers match no returned passage (figures only in tables or figures,
   unit or wording mismatch, `91.2%` vs `0.912`).
5. `moderate` and `weak` are right in a quarter of cases or fewer; ratings are not calibrated.
6. One development pair is still unlabelled, so `eval.dev_pairs score` refuses and `score-labelled` is needed.

## Next three tasks
1. Reproduce the abstract-detection and section failures on **development or synthetic** PDFs with the same layouts
   (never the held-out files), fix in `paperlens/ingest.py`, add layout tests like `tests/test_real_layout_fixes.py`.
2. Reject "experiment announcement" passages for result claims: a passage with no figure and no outcome verb
   ("we conduct", "we evaluate ... on", "Table N provides") should not be returned as support. Measure on the dev
   labels (7 partial cases) and SciFact train before adopting.
3. Extend coverage to non-numeric parts: split a claim on its coordinated objects ("on both A and B") and report which
   named parts appear in the returned passages. Start in `claims.quantity_coverage`.

## Look here first
- `paperlens/claims.py`: `select_passages`, `_complementary`, `quantity_coverage`, `link_evidence`, `evidence_unsuitable`.
- `paperlens/textutils.py`: `quantities_in`, `Quantity.matches`.
- `paperlens/ingest.py`: heading and abstract detection (bugs 1 and 2).
- `eval/quantity_coverage.py`, `eval/dev_pairs.py`, `eval/results/dev_v0.3/quantity_coverage.csv` (per-claim missing figures).

## Limitations of this session
- The UI line in `web/app.js` was not opened in a browser.
- Labels used are AI-assisted and from the session that wrote the 0.2.0-dev fixes; no human label exists for any version.
- **One slip to know about:** a repository-wide `git grep` for the word "flags" over `eval/` also searched the tracked
  files under the held-out result folders. The only output shown was 30 lines reading `"flags": [],` with file names
  from `eval/results/held_out/raw/analysis/` (first held-out set). No label, key, claim or passage was displayed, and
  nothing from it was used. No other command opened, listed or searched `sealed_key/` or `raw/`.

## Protected assets: what was actually checked
- `git diff --stat 45b2ca2 HEAD` and `git status --porcelain` on `eval/results/held_out*`, both AI-audit folders,
  `eval/results/dev_v0.2`, `data/` and the 0.1.0 result files: no differences, no untracked files.
- Both tags resolve to the commits listed above.
- Not re-run: the raw-output hash checks and freeze-manifest verifications of the earlier session; the official scorers.

## Still the owner's actions
Label `eval/results/held_out_v0.2/held_out_audit.csv` by hand before opening the AI audit files, then run
`python -m eval.held_out_v2 score eval/results/held_out_v0.2`. Do not tune on either held-out set or their labels.
`0.3.0-dev` needs a third unseen set before any unseen-data claim.
