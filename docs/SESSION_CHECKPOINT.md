# PaperLens AI session checkpoint (2026-10-13, sprint 4: PDF reading-order benchmark)

Written by the session that did the work, from commands it ran (`docs/TEST_REPORT.md`, section "0.5.0-dev").
Previous checkpoint: `git show d4862d2:docs/SESSION_CHECKPOINT.md` (sprint 2, abstract and section detection).

## Verified state
- Folder `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`. Start: branch `dev/section-detection-v0.4`, commit `d4862d2`, tree clean, 136 tests passed (as reported).
- New branch `dev/reading-order-v0.5` from `d4862d2`; the final commit is its tip (`git log -1`). Code version `0.5.0-dev`.
  `dev/section-detection-v0.4` is still `d4862d2`, `dev/partial-support-v0.3` `663bf4d`, `main` `d6951bf`.
- Tags unmoved: `v0.1.0-frozen-heldout` = `d6951bf`, `v0.2.0-dev-frozen-heldout2` = `a549f25`. No remote; nothing pushed.
- Use `.venv\Scripts\python.exe` (`PY`); set `PYTHONIOENCODING=utf-8` for eval scripts. `paperlens/ingest.py` is CRLF in Git: edit with a tool that keeps CRLF.
- The full suite now takes about 170 s (the benchmark fixture parses 21 PDFs).

## What was done and why (details: docs/EVALUATION.md section 11)
1. **Benchmark first.** `eval/layout_synth.py` makes 21 deterministic synthetic PDFs (13 categories) and independent truth files from a
   logical document + a flow engine; only the content-stream order varies (`natural`, `blocks_y`, `lines_y`, `shuffled`).
   `eval/layout_bench.py` scores them (metric definitions in its docstring). The baseline of `d4862d2` is saved
   (`eval/results/layout_bench/baseline_d4862d2.json`, committed before any parser change; re-run on the final generator).
2. **Baseline failures were genuine**: stream order trusted (columns interleaved by line or block, headings after their text, claims and evidence lost),
   sentences cut at page breaks (tail dropped), a running head leaking into text. Macro: order 0.93, paragraph reconstruction 0.75, 52 spliced sentences.
3. **Fix** in `paperlens/ingest.py`: XY-cut column ordering (`_reorder_columns`), page-spanning sentences (`flush(keep_tail=...)`), ambiguity flag for grid pages
   (`AMBIGUOUS_LAYOUT`), per-column table placement, drop caps, abstract end at a wide white band, publisher boxes as notes, alternating running heads, footnote marks with a space.
   Thresholds, ratings, evidence linking: untouched.
4. 39 new tests (`tests/test_layout_bench.py`): generator determinism and independence, truth consistency, per-layout floors, hand-made geometry cases incl. negatives
   (table-like cells, page number alone, column ending early, merged line cut at the gutter), page-break and furniture cases.

## Commands and exact outcomes
| Command | Outcome |
|---|---|
| `PY -m pytest -q` | 136 passed before; **175 passed, 0 failed** after |
| `PAPERLENS_SRC=<git archive d4862d2 paperlens> PY -m eval.layout_bench --out ...baseline_d4862d2.json` | macro: block recall 0.92, reading order 0.93, paragraph recon 0.75, evidence 0.79, 52 spliced, ambiguity handled 0 of 1 |
| `PY -m eval.layout_bench --out ...after_0.5.0-dev.json` | macro: recall 1.00, order 0.996, paragraph recon 0.995, evidence 1.00, 0 spliced, ambiguity handled 1 of 1, 0 false layout warnings; one imperfect layout (`L13`, sparse column) |
| `PY -m eval.structure_dev data/Papers eval/dev_structure_labels.json <out>` | abstract 16/16 (start and end), headings 83/85: unchanged from 0.4.0-dev |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.5` | 16 papers, 0 crashed, 146 claims (147 before); 135 of 141 common claims keep the top passage; still-labelled rows strict 21/54, lenient 43/54 (24/60, 49/60 before); 7 claims lost their label because their text changed |
| `PY -m eval.run_eval --n 100 --seed 7`, `PY -m eval.scifact_eval` | identical to 0.4.0-dev except timings |
| Browser + API with synthetic `L02_twocol_lines_y`, `L04_pagebreak_twocol`, `L10_grid_lines_y` | order, pages, evidence page 2, coverage line, page images and the grid layout warning all displayed |

**Honest reading:** the synthetic gains are large because the baseline trusted stream order and the layouts were built to vary it; the same session wrote both, so the 1.00 is a
regression guard, not an accuracy figure. On real development papers abstracts and headings are unchanged, at least 2 claims that were sentence fragments now appear as whole sentences (5 claims changed text), evidence precision
cannot be compared (labels lost), and two new splices of figure text into claims were seen. Nothing was measured on unseen papers.

## Bugs found on the way (and a process lesson)
- `layout_bench` first imported the *current* parser even with `PAPERLENS_SRC`, so a "baseline" was produced with the patched code (it came out perfect, which exposed it). Fixed; the baseline file records the imported package path.
- The page-carry code crashed on real papers (empty buffer) and the synthetic benchmark did not see it: always run the 16 development PDFs after touching `_build`.

## Known problems, ranked by expected impact
1. Real-paper layouts are not covered: figure text and unruled tables glue to nearby sentences (2 new claims on ATLAS and SciFact), publisher boxes and sidebars vary.
2. Column with fewer than 3 lines is not separated (`L13`), and nothing is flagged for it.
3. Held-out failures ("3 claims per paper", a 55-page paper with none) were not reproduced; they may or may not be layout-related.
4. Evidence precision on real papers is not re-measured: 7 development claims need new labels.
5. Rows-before-columns rule can misread a normal two-column page that has a figure band across both columns.

## Next three tasks
1. Label the 7 development claims whose text changed and the 4 returned passages, then run `eval.dev_pairs score-labelled` so evidence precision of 0.5.0-dev is comparable with 0.4.0-dev.
2. Add a figure/unruled-table guard: text blocks inside the bounding box of a drawn figure or of a grid of short cells should become `table`/`caption`-like units, not prose (fixes the two glued claims); measure with new synthetic layouts and the dev papers.
3. Build a third unseen set (owner) and run the frozen 0.5.0-dev once; until then make no unseen-data claim.

## Look here first
- `paperlens/ingest.py`: `_reorder_columns`, `_order_region`, `_vertical_cut`, `_leaf`, `_build` (`flush(keep_tail=...)`, `emit_tables`, drop-cap and abstract-gap rules).
- `eval/layout_synth.py` (`LAYOUTS`, `make`), `eval/layout_bench.py` (`evaluate`), `tests/test_layout_bench.py`.

## Protected assets: what was actually checked
- No command opened, listed or searched `eval/results/held_out*`, its raw or sealed_key folders, or any audit folder; all searches and runs used `data/Papers`, `eval/results/dev_*`, `eval/results/layout_bench`, `eval/*.py`, `paperlens`, `tests`, `docs`.
- `git diff --stat d4862d2 HEAD -- eval/results/held_out eval/results/held_out_v0.2 eval/results/held_out_ai_audit eval/results/held_out_ai_audit_2 eval/results/held_out_v0.2_ai_audit eval/results/dev_v0.2 eval/results/dev_v0.3 eval/results/dev_v0.4 data`: no differences (names only). Both tags resolve to the commits above. Not re-run: raw-output hash checks, freeze verification, the official scorers.
- Earlier slip (sprint 1, recorded earlier): a repository-wide `git grep` crossed into the first held-out set's `raw/analysis/` folder; not repeated.

## Still the owner's actions
Label `eval/results/held_out_v0.2/held_out_audit.csv` by hand before opening the AI audit files, then `python -m eval.held_out_v2 score eval/results/held_out_v0.2`.
Do not tune on either held-out set. `0.5.0-dev` needs a third unseen set before any unseen-data claim.
