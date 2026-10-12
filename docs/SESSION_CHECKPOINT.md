# PaperLens AI session checkpoint (2026-10-13, sprint 6: validate reading-order changes on real development papers)

Written by the session that did the work, from commands it ran (`docs/TEST_REPORT.md` "0.5.1-dev", `docs/EVALUATION.md` section 12).
Previous checkpoint: `git show 7b3485f:docs/SESSION_CHECKPOINT.md` (sprint 4, reading-order benchmark; its benchmark description still applies).

## Verified state
- Folder `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`. Start: branch `dev/reading-order-v0.5`, commit `7b3485f`, tree clean, 175 tests (as reported).
- Same branch continued; final commit is its tip (`git log -1`). Code version `0.5.1-dev`. `dev/section-detection-v0.4` `d4862d2`, `main` `d6951bf`.
- Tags unmoved: `v0.1.0-frozen-heldout` = `d6951bf`, `v0.2.0-dev-frozen-heldout2` = `a549f25`. No remote; nothing pushed.
- `PY` = `.venv\Scripts\python.exe`; `PYTHONIOENCODING=utf-8` for eval scripts; `paperlens/ingest.py` is CRLF in Git. Do not launch an interpreter with a heredoc that has no body: it hangs.

## What was done and why
1. **Two splices reproduced and fixed at the cause** (`ingest.py`): (a) figure content: `_figure_boxes` finds drawings/images and keeps text inside them as `meta` (SciFact Figure 1 labels glued up to the caption);
   (b) a caption that starts its own block inside an unfinished sentence is held aside and the sentence continues after it (ATLAS Figure 12 between two columns). No paper-specific rule.
   6 tests in `tests/test_figure_text.py`, two of which fail when the fixes are disabled. A first caption rule also hit a wrapped "Table 1." and cost the synthetic table layout 2% recall; the benchmark test caught it; fixed.
2. **Label identity across versions** (`eval/claim_map.py`, 8 tests): identity = sha1(paper | claim text); labels carry only for identical text; changed text or a changed passage needs a fresh label; `merge` writes a new file, refuses conflicts and unmarked labels;
   `compare` scores both versions on the same claims and refuses precision while any returned passage is unlabelled. Original labels untouched (sha256 = `DEV_LABELS_LOCKED.txt`, tested).
3. **Fresh labels**: 12 items (5 claims, 7 passages), AI-assisted by the parser-editing session, with reasons, in `eval/results/dev_v0.5.1/label_map/fresh_labels_ai_assisted.csv`; merged file `dev_pairs_labelled_merged.csv`.

## Numbers (development papers; AI-assisted labels)
| Item | Result |
|---|---|
| Tests | 175 before, **189 passed, 0 failed** after (one benchmark failure on the way, fixed) |
| Claims 0.4.0-dev to 0.5.1-dev | 147 to 144: identical 141, partially changed 3 (fragments completed or clause added), materially changed 0, removed 3, added 0 |
| Labels | 139 claim labels and 54 pair judgments carried; 12 fresh labels needed and made |
| Common 141 claims (97 real, 59 returned each) | coverage 0.608 both; strict 22/59 = 0.373 both; lenient 48/59 = 0.814 vs 47/59 = 0.797; 135 of 141 same top passage |
| Whole 0.5.1-dev set | 99 real, 61 returned, strict 23/61 = 0.377, lenient 49/61 = 0.803, coverage 61/99 |
| Other | abstract 16/16, headings 83/85; seed 7 synthetic and SciFact dev identical to 0.4.0-dev; layout benchmark unchanged (macro 1.00, `L13` order 0.92) |

**Honest reading:** the two splices are gone and no precision change is demonstrated either way (one lenient loss on 59 passages: an Attention-paper claim whose passage became unrelated). The 0.4.0-dev whole-set figures are not computable
(one removed claim unlabelled), and the old whole-set numbers have a different denominator, so there is no improvement or regression claim. All labels are AI-assisted and not independent; nothing was measured on unseen papers.

## Known problems, ranked by expected impact
1. Unruled-table text and other non-drawn figure text still glue to nearby sentences (ResNet: "avg pool output size: 1 avg pool We evaluate our method ...", judged `p` for that reason).
2. Real-paper evidence precision rests on 59 passages and AI-assisted labels from sessions that wrote the code; a human label of the 16-paper sheet is still missing.
3. Column with fewer than 3 lines is not separated (synthetic `L13`), unflagged.
4. Held-out failures ("3 claims per paper") not reproduced.
5. Passages of changed claims (6 of 141 common) moved without a way to say whether that is better in general.

## Next three tasks
1. Detect unruled tables / aligned short-cell blocks (text blocks whose lines are short, share baselines and sit in several x-positions) and emit them as `table` rows, with synthetic layouts and the dev papers as checks (fixes the ResNet glue).
2. Human-label the pooled sheet (`eval/results/dev_v0.2/dev_pairs_blank.csv` plus `label_map/needs_fresh_labels.csv`) so that development precision no longer rests on AI-assisted labels.
3. Owner: provide a third unseen set and run the frozen 0.5.1-dev once; until then no unseen-data claim.

## Look here first
- `paperlens/ingest.py`: `_figure_boxes`, `release_held`, `_CAPTION_START`, `_reorder_columns`, `_build`.
- `eval/claim_map.py` (`map`, `merge`, `compare`), `eval/results/dev_v0.5.1/label_map/` (report, fresh labels, merged labels, comparison.json), `tests/test_figure_text.py`, `tests/test_claim_map.py`.

## Protected assets: what was actually checked
- No command opened, listed or searched `eval/results/held_out*`, raw, sealed_key or any audit folder; the audit rubric file under the held-out folder was not read (fresh labels follow the rubric as used in `dev_pairs`/EVALUATION section 6.5).
- `git diff --stat 7b3485f HEAD -- eval/results/held_out eval/results/held_out_v0.2 eval/results/held_out_ai_audit eval/results/held_out_ai_audit_2 eval/results/held_out_v0.2_ai_audit eval/results/dev_v0.2 eval/results/dev_v0.3 eval/results/dev_v0.4 eval/results/dev_v0.5 data`: no differences (names only). Both tags resolve to the commits above. Not re-run: raw-output hash checks, freeze verification, the official scorers.
- Earlier slip (sprint 1): a repository-wide `git grep` crossed into the first held-out set's `raw/analysis/`; not repeated.

## Still the owner's actions
Label `eval/results/held_out_v0.2/held_out_audit.csv` by hand before opening the AI audit files, then `python -m eval.held_out_v2 score eval/results/held_out_v0.2`. Do not tune on either held-out set.
