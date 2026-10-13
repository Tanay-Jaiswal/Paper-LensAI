# PaperLens AI session checkpoint (2026-10-13, sprint 7: tables without a grid; sprint 8: row-level table benchmark)

Written by the session that did the work, from commands it ran (`docs/TEST_REPORT.md` "0.6.0-dev", `docs/EVALUATION.md` section 13).
Previous checkpoint: `git show adce476:docs/SESSION_CHECKPOINT.md` (sprint 6, figure text and label carry-over).

## Sprint 8 (after `4d15ba8`): row-level benchmark on real development tables. No parser change.
- **Start verified:** branch `dev/reading-order-v0.5`, HEAD `4d15ba8`, tree clean, 217 tests passed, tags unmoved.
- **Added:** `eval/table_truth/` (11 tables, 71 rows, 333 cells; `PROTOCOL.md`; `VERIFICATION_SHEET.md`; lock file), `eval/table_rows_bench.py`
  (`check`, `score`, `sheet`, `render`), `tests/test_table_rows_bench.py` (5), results in `eval/results/table_rows_dev/`, docs/EVALUATION.md section 14.
- **Annotations are AI-transcribed** from page images, each cell confirmed in the PDF text layer, locked before scoring. **Not human-verified.**
  Five of the 11 tables are on pages read while writing 0.6.0-dev (optimistic for that version). Nothing was tuned on the benchmark.
- **Results (strict), 70 scored rows / 330 cells / 15 header rows:** 0.6.0-dev exact rows 43 (0.614), cells 249 (0.755), split 1, partial 13, missing 13 (1 glued),
  header rows 5, wrong heads 0 of 134. Parser of `adce476`: exact rows 8 (0.114), cells 33 (0.100), missing 62 (50 glued into prose). Tests: **222 passed**.
- **Main finding:** the running-header filter deletes every integer-only line on every page (pattern `#`, triggered by page numbers): 65 of 243 number-only lines
  in the SciFact paper, 394 of 1313 in GPT-3. Integer table cells vanish before table detection (both SciFact tables score 0 or partial for this reason).
- **Next recommended task (one change):** restrict the page-number pattern of `_running_headers` to the top and bottom page strips, add a synthetic layout with
  integer-only cells and a page number, then re-score with `python -m eval.table_rows_bench score` (do not tune on individual annotated rows).
  After that: word tables (T04), values split at super/subscripts (T09, T07), heads delivered as one line.
- **Owner:** check `eval/table_truth/VERIFICATION_SHEET.md` against the PDFs if a human-verified benchmark is wanted
  (`python -m eval.table_rows_bench render <folder>` writes the page crops locally; do not commit them).
- **Protected assets:** no held-out folder, raw output, sealed key or audit file was opened, listed or searched; no held-out scorer run; no tag moved; nothing pushed;
  `git diff --stat 4d15ba8 HEAD` over the held-out, audit and earlier result folders shows no change (names only).

## Verified state
- Folder `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`. Start: branch `dev/reading-order-v0.5`, commit `adce476`, tree clean, 189 tests passed (run, not assumed).
- Same branch continued; final commit is its tip (`git log -1`). Code version `0.6.0-dev`.
- Tags unmoved: `v0.1.0-frozen-heldout` = `d6951bf`, `v0.2.0-dev-frozen-heldout2` = `a549f25`. No remote; nothing pushed. No branch switch or reset.
- `PY` = `.venv\Scripts\python.exe`; `PYTHONIOENCODING=utf-8` for eval scripts; `paperlens/ingest.py` is CRLF in Git.
  Do not edit files with `sed` replacement text that contains `\n`, and do not build patch scripts in shell heredocs (backslashes are mangled): write the script to a file.

## What was done and why
1. **Failure measured first.** 8 synthetic layouts with a table that has no grid (`eval/layout_synth.py`, category `unruled_tables`) and a new count `table_leaks`.
   The 0.5.1-dev parser found none of the rows (recall 0.00), glued cells into 8 sentences and spliced 9.
2. **`_open_tables` in `paperlens/ingest.py`**: tables recognised from geometry (cells at wide gaps, rows by baseline, value columns that line up), taken out of the
   running text and emitted as rows where the table stands. Labelled data rows are `table`; heads, group labels and rows without a label are `meta`, with a warning for the latter.
3. **A table inside a sentence** (same column, text going on in lower case) is emitted after the sentence, ruled tables included.
4. **Checked against the development papers and corrected**: numbered headings, formulas, short prose lines of the next column, loosely justified lines and
   wrapped citation lists are not table cells. Each of these was a regression found by reading changed sentences and has a test.
5. Tests: `tests/test_unruled_tables.py` (20), 8 benchmark layouts under the existing floors plus `table_leaks == 0`.

## Numbers
| Item | 0.5.1-dev (`adce476`) | 0.6.0-dev |
|---|---|---|
| Tests | 189 passed | **217 passed, 0 failed** |
| Synthetic, 8 unruled-table layouts: row recall / glued-cell sentences / spliced / paragraph reconstruction | 0.00 / 8 / 9 / 0.91 | 1.00 / 0 / 0 / 1.00 |
| Synthetic, 21 earlier layouts | recorded | identical |
| Development papers: prose sentences with a run of 4+ numbers | 48 | 14 |
| Development papers: table sentences | 406 | 689 (283 new labelled rows; 56 rows without label kept as meta; 7 papers warned) |
| Development papers: claims | 144 | 144, all identical in text |
| Coverage / strict / lenient on 99 real claims (AI-assisted labels) | 61/99, 23/61 = 0.377, 49/61 = 0.803 | 59/99, 22/59 = 0.373, 48/59 = 0.814 |
| Abstract 16/16, headings 83/85, synthetic seed 7, SciFact dev | | unchanged |

**Honest reading:** on synthetic PDFs the failure is gone. On real development papers far less table text is read as prose, and some rows are read correctly and some
wrongly; row-level correctness was not measured. Evidence precision did not move in either direction (one or two passages out of about 60). Nothing was measured on unseen papers.

## Known problems, ranked by expected impact
1. Tables of words (ResNet architecture table) and the ten-score row in the protein-contact paper are still glued to prose: the two cases named in the last checkpoint are **not** fixed.
2. Row reading on real papers is unverified: merged value pairs, rows split in two, heads left as junk prose sentences ("System Dev Test EM F1 ...").
3. Real-paper evidence precision still rests on about 60 passages with AI-assisted labels from sessions that wrote the code; no human labels.
4. More table rows in the candidate pool cost two claims their passage; the abstention threshold was not revisited (and must not be tuned on development labels).
5. Held-out failures ("3 claims per paper") not reproduced; column with fewer than 3 lines not separated (synthetic `L13`).

## Next recommended task
Build a small **row-level ground truth for real tables on the development papers**: for about 10 tables, write the expected rows by hand from the PDF (label and values),
score `Table row` sentences against them (row recall, cell accuracy, wrong head attachments), and only then extend detection to word tables and single-line heads.
Without it, further table work is tuned by eye. Second: a human label of the pooled development sheet. Third (owner): a third unseen set, run once on a frozen version.

## Look here first
- `paperlens/ingest.py`: `_open_tables`, `_cells`, `_baseline_rows`, `_gutters`, `_prune_strays`, `_numeric_cell`, `_prose_cell`, and in `_build`: `place_table`, `emit_rows`, the placeholder branch (`block_no < 0`).
- `tests/test_unruled_tables.py`, `eval/layout_synth.py` (`_draw_open_table`, layouts `L14` to `L16`), `eval/layout_bench.py` (`table_leaks`), `eval/table_text_dev.py`,
  `eval/results/dev_v0.6.0/` (audit, `table_text_*.json`, `label_map/`), `eval/results/layout_bench/after_0.6.0-dev.json`.

## Protected assets: what was actually checked
- No command opened, listed or searched `eval/results/held_out*`, raw, sealed_key or any audit folder; `held_out_audit.csv` and the AI audit files were not opened; no held-out scorer was run.
  Searches were limited to `paperlens/`, `tests/`, `eval/*.py`, `docs/` and the development result folders.
- `git diff --stat adce476 HEAD` restricted to the held-out and audit folders, the earlier development result folders and `data`: no differences (names only).
  Both tags resolve to the commits above. Not re-run: raw-output hash checks, freeze verification.
- The two fresh labels are AI-assisted, by the session that changed the parser, in `eval/results/dev_v0.6.0/label_map/fresh_labels_ai_assisted.csv`; earlier label files are unchanged.

## Still the owner's actions
Label `eval/results/held_out_v0.2/held_out_audit.csv` by hand before opening the AI audit files, then `python -m eval.held_out_v2 score eval/results/held_out_v0.2`. Do not tune on either held-out set.
