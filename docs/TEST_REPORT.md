# Test report: 0.2.0-dev (2026-10-12)

Commands actually run in this session on branch `dev/evidence-linking-v0.2`, with their outcomes. Environment: Windows 11,
Python 3.13.7 in `.venv`, PyMuPDF 1.28.2, FastAPI 0.143.0, pytest 9.1.1. `PY` stands for `.venv\Scripts\python.exe`.

## Automated tests

| When | Command | Outcome |
|---|---|---|
| Before any change | `python -m pytest -q` (system Python) | **could not run**: `No module named pytest` |
| Before any change | `PY -m pytest -q` | 44 passed |
| New regression tests, first run | `PY -m pytest -q tests/test_evidence_linking_v02.py` | 52 passed, **2 failed**: both were wrong synthetic fixtures (a table row whose number did not match; a caption one word short of the length rule). Fixtures corrected, code unchanged |
| After the fixes of the number parser | `PY -m pytest -q` | 98 passed |
| After the symbol-density and `% F1` fixes | `PY -m pytest -q` | 101 passed |
| After searching abstract/introduction/conclusion, first run | `PY -m pytest -q` | 99 passed, **2 failed**: two tests written earlier in this session pinned the old rule (those sections never returned). The rule changed on the owner's instruction, so the tests were rewritten to the new rule; the "no body text" test was kept and passes again after the status logic was corrected |
| Final | `PY -m pytest -q` | **106 passed, 0 failed, 0 skipped** (1 third-party deprecation warning) |

No test was deleted or skipped. One 0.1.0 test was edited by the earlier session (`test_meta_sentences_and_fragments_are_not_evidence`,
see docs/EVALUATION.md 6.7); checked against the tag, it was not weakened.

Defects found by tests or reruns and fixed, each with a regression test:
`1e-3` read as "1"; `10^-3` read as "10" and "3"; the first number of "3.5 to 4.2%" or "125.3 ± 0.6 GeV" had no unit;
results sentences dense with figures rejected as symbols; `89.1% F1` not matching `89.1 F1`; "from 85.6 to 89.1" carrying
the metric on one number only; two abstract claims returned as evidence for each other.

## Evaluations (development data only)

| Command | Outcome |
|---|---|
| `PY -m eval.run_eval --n 100 --seed 7 --out eval/results/dev_v0.2/seed7` | first run top-1 evidence hit 0.969 (worse than 0.1.0); after fixes 1.0 |
| `PY -m eval.run_eval --n 100 --seed 99 --out eval/results/dev_v0.2/seed99` | first run 0.969; after fixes 1.0; unsupported rated none/weak 1.0 (0.975 in 0.1.0) |
| `PY -m eval.scifact_eval --out eval/results/dev_v0.2` | hit@1 0.493, hit@3 0.818, MRR 0.672, AUROC 0.810 |
| `PY -m eval.abstention_curve --split train --out eval/results/dev_v0.2` | at 0.30: coverage 0.431, precision 0.500, recall 0.351 |
| `PY -m eval.abstention_curve --split dev --out eval/results/dev_v0.2` | at 0.30: coverage 0.424, precision 0.521, recall 0.359 |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.2` | 16 papers, 0 crashed, 145 claims, 83 with a passage |
| `PY -m eval.dev_pairs score eval/results/real_papers_audit.csv eval/results/dev_v0.2/real_papers_audit.csv eval/results/dev_v0.2` | **refused**: 1 returned pair has no label |
| same with `score-labelled` | coverage 0.619, strict 0.407 (24/59), lenient 0.814, wrong 11; output in `dev_precision_coverage_final.txt` |

Rerunning the synthetic, SciFact and development-paper evaluations at the end reproduced the committed files (only run
times differ). Not run: `eval/dev_threshold_sweep.py` (deliberately, see docs/EVALUATION.md 6.3) and anything on the
held-out papers.

## Manual checks

| Check | Outcome |
|---|---|
| API with a synthetic empty PDF, a corrupt file, an encrypted PDF, an empty upload, a missing field, an unknown id, a bad page, `zoom=nan`, comparing a paper with itself | all return a clean status code; the empty PDF was reported as a poor paper (fixed, now "not assessed") |
| Web UI in a browser, `PY -m paperlens serve --port 8765`, built-in synthetic demo papers | page loads; ledger, abstention text, page images with highlights, gaps and comparison render |
| Web UI with a real paper | **not checked** |

## Protected files

| Check | Outcome |
|---|---|
| `git diff v0.1.0-frozen-heldout` on `eval/results/held_out`, both AI audit folders, `data/held_out_papers`, the 0.1.0 result files | no differences |
| 10 files under `eval/results/held_out/raw/` against `RAW_OUTPUT_HASHES.json` (hashed, not read) | 10 match |
| 8 held-out PDFs against the sha256 column of their `MANIFEST.csv` | 8 match |
| Code at tag `v0.1.0-frozen-heldout` against `FREEZE.json` | 14 of 14 files match |
| `PY -m eval.freeze verify eval/results/held_out/FREEZE.json` on this branch | reports 10 changed files, as intended: the held-out results do not describe this version |
| `dev_pairs_labelled.csv` against `DEV_LABELS_LOCKED.txt` | matches |
| PDFs tracked by Git | 0; largest tracked file 140 KB |

## 0.3.0-dev (2026-10-12, branch `dev/partial-support-v0.3`)

| Command | Outcome |
|---|---|
| `PY -m pytest -q` before any change | 106 passed |
| `PY -m eval.real_papers data/Papers <scratch>` before any change | output file identical (sha256) to `eval/results/dev_v0.2/real_papers_audit.csv` |
| `PY -m pytest -q tests/test_compound_claims_v03.py`, first run | 7 passed, **6 failed**: two synthetic fixture sentences were shorter than the 6-content-word rule and were rejected as fragments; one assertion in a test was wrong. Fixtures lengthened and the assertion removed; code unchanged |
| `PY -m pytest -q` after the version bump | 118 passed, **1 failed**: `test_api_cli` pins the version string; updated to `0.3.0-dev` |
| `PY -m pytest -q` final | **119 passed, 0 failed, 0 skipped** (1 third-party deprecation warning) |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.3` | 16 papers, 0 crashed, 145 claims; audit rows identical to 0.2.0-dev |
| `PY -m eval.dev_pairs score-labelled eval/results/dev_v0.2/real_papers_audit.csv eval/results/dev_v0.3/real_papers_audit.csv eval/results/dev_v0.2` | both columns: coverage 0.619, strict 0.407 (24/59), lenient 0.814, wrong 11; same top passage for 60 of 60 |
| `PY -m eval.run_eval --n 100 --seed 7` and `--seed 99`, `--out eval/results/dev_v0.3/seedN` | identical to `dev_v0.2` apart from timings |
| `PY -m eval.scifact_eval --out eval/results/dev_v0.3` | identical to `dev_v0.2` apart from timings (hit@1 0.493, AUROC 0.810) |
| `PY -m eval.quantity_coverage data/Papers eval/results/dev_v0.3 eval/results/dev_v0.2/dev_pairs_labelled.csv` | figures matched by the returned passages 78 -> 84 of 143; claims fully covered 20 -> 22 of 51 |

Not run: the official held-out scorers, `eval/dev_threshold_sweep.py`, the web UI in a browser (the UI line added in
`web/app.js` is untested), and anything on either held-out folder.

## 0.4.0-dev (2026-10-12, branch `dev/section-detection-v0.4`)

| Command | Outcome |
|---|---|
| `PY -m pytest -q` before any change | 119 passed |
| `PY -m pytest -q tests/test_structure_v04.py`, first run | 13 passed, **4 failed**: fixture sentences under 25 characters (dropped by the existing filter), a 39-word abstract under the 40-word minimum, a wrong assertion about `canonical_section`, and one real finding: `keyword_section` accepted 6 content words, tightened to 4. The front-matter paragraph gap was also loosened from 1.45 to 1.7 line heights (synthetic leading is 1.48) |
| `PY -m pytest -q` final | **136 passed, 0 failed** (17 new tests; the version-string test updated to `0.4.0-dev`) |
| `PAPERLENS_SRC=<copy of 663bf4d> PY -m eval.structure_dev data/Papers eval/dev_structure_labels.json <out>` | abstract start 15/16, end 11/16; bookmarked headings 61/85, precision 61/94 |
| `PY -m eval.structure_dev data/Papers eval/dev_structure_labels.json <out>` | abstract start 16/16, end 16/16; headings 83/85, precision 83/113 |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.4` | 16 papers, 0 crashed, 147 claims |
| `PY -m eval.dev_pairs score-labelled ...` on dev_v0.4 | **failed** (KeyError: 3 new claims have no label); compared by a script instead: strict 24/60 vs 24/59, lenient 49/60 vs 48/59, 142 of 144 common claims keep the top passage |
| `PY -m eval.run_eval --n 100 --seed 7`, `PY -m eval.scifact_eval` to `eval/results/dev_v0.4` | identical to `dev_v0.3` apart from timings. Seed 99 not re-run |
| Browser (built-in pane, `python -m paperlens serve`, data folder in a scratch directory) | LIGO development paper: abstract warning shown, 9 claims; claim detail shows page, section, "1 of 3 claimed figures matched; not found: 1e-21, 250" and three loaded page images. GPT-3 (75 pages) was analysed through the API only, not opened in the browser; no missing-section paper was opened in the browser |

Not run: official held-out scorers, `eval/dev_threshold_sweep.py`, anything on either held-out folder.

## 0.5.0-dev (2026-10-12/13, branch `dev/reading-order-v0.5`)

| Command | Outcome |
|---|---|
| `PY -m pytest -q` at the start (`d4862d2`) | 136 passed |
| `PAPERLENS_SRC=<copy of d4862d2> PY -m eval.layout_bench --out eval/results/layout_bench/baseline_d4862d2.json` | 21 documents, 0 crashed; macro block recall 0.92, order 0.93, paragraph reconstruction 0.75, 52 spliced sentences. Run twice, identical. An earlier baseline file of this branch had been produced with the *patched* parser (import order bug in `layout_bench`), was found when its numbers came out perfect, and was replaced; the first 18 layouts were also run before any parser change and match the replacement |
| first run of the patched parser on real development papers | **crash** (`IndexError` in the page-carry code on an empty buffer) found only when the 16 real development papers were parsed (`eval.structure_dev`), not by the synthetic layouts; fixed, and the real-PDF comparison is not part of the test suite |
| `PY -m pytest -q tests/test_layout_bench.py` first run | 1 failed: generator truth for the grid layout listed "Note A" as a section heading (changed the truth, not the parser); then a test of running heads used a body line that repeated after digit normalisation (test fixed) |
| `PY -m eval.layout_bench --out eval/results/layout_bench/after_0.5.0-dev.json` | 21 documents, 0 crashed; macro 1.00 on all metrics except paragraph reconstruction 0.99 and order 0.996 (`L13`); 0 spliced; 1 layout warning (the grid) and 0 false warnings |
| `PY -m pytest -q` final | **175 passed, 0 failed** (39 new tests in `tests/test_layout_bench.py`; the version test updated to `0.5.0-dev`); about 170 s |
| `PY -m eval.structure_dev data/Papers eval/dev_structure_labels.json eval/results/dev_v0.5` | abstract 16/16, 16/16; headings 83/85, precision 83/113 (unchanged) |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.5` | 16 papers, 0 crashed, 146 claims; `score-labelled` not run (unlabelled claims); compared by script: strict 21/54, lenient 43/54 on still-labelled rows (24/60, 49/60 before), 135 of 141 common claims keep the top passage |
| `PY -m eval.run_eval --n 100 --seed 7`, `PY -m eval.scifact_eval` to `eval/results/dev_v0.5` | identical to `dev_v0.4` apart from timings |
| Browser (built-in pane, `python -m paperlens serve`, scratch data folder) with synthetic `L02_twocol_lines_y`, `L04_pagebreak_twocol`, `L10_grid_lines_y` | extraction in reading order; claim C1 "strong", evidence on page 2, "2 of 2 claimed figures matched", two page images loaded; grid layout shows the layout warning in the warning bar. Claims of the synthetic documents were checked through the API for all three |

Not run: official held-out scorers, `eval/dev_threshold_sweep.py`, anything on the held-out folders.

## 0.5.1-dev (2026-10-13, branch `dev/reading-order-v0.5`)

| Command | Outcome |
|---|---|
| `PY -m pytest -q` at the start (`7b3485f`) | 175 passed |
| reproduction (scratch script, development PDFs) | ATLAS p21 claim "The excess is driven SM Best fit ... Figure 12: ..." and SciFact p1 "Decision: SUPPORTS Fact-checker Corpus More severe ..." both present as `text` sentences |
| `PY -m pytest -q tests/test_figure_text.py` with `_figure_boxes` and the caption rule disabled | the two reproduction tests fail (the other four are negatives); with the fixes: 6 passed |
| first full run after the fixes | 179 passed, **1 failed**: `L05_tables_natural` block recall 0.977 (< 0.99); cause: a table reference wrapped onto its own line ("Table 1.") was taken for a caption; rule tightened, test added |
| a hung `python -` process from a malformed shell command was killed | no effect on files |
| `PY -m pytest -q` final | **189 passed, 0 failed** (14 new: 6 figure text, 8 claim map) |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.5.1` | 16 papers, 0 crashed, 144 claims; `eval.structure_dev`: abstract 16/16, headings 83/85 (unchanged) |
| `PY -m eval.claim_map map ...dev_v0.4... ...dev_v0.5.1... ...dev_v0.2/dev_pairs_labelled.csv eval/results/dev_v0.5.1/label_map` | 141 identical, 3 partially changed, 3 removed; 12 items need fresh labels |
| `PY -m eval.claim_map merge` then `compare` | strict 22/59 vs 22/59, lenient 48/59 vs 47/59 on the 141 common claims |
| `PY -m eval.layout_bench --out eval/results/layout_bench/after_0.5.1-dev.json` | identical aggregate to 0.5.0-dev |
| `PY -m eval.run_eval --n 100 --seed 7`, `PY -m eval.scifact_eval` | identical to 0.4.0-dev except timings |

Not run: the application in the browser this sprint (parser-only change on top of the sprint-4 check), official held-out scorers, anything on the held-out folders.

## 0.6.0-dev (2026-10-13, branch `dev/reading-order-v0.5`)

| Command | Outcome |
|---|---|
| `PY -m pytest -q` at the start (`adce476`) | 189 passed |
| `PY -m eval.layout_bench` with the parser of `adce476` on the 8 new unruled-table layouts | table-row recall 0.00, 8 sentences with glued cells, 9 spliced sentences, paragraph reconstruction 0.91 (the failure, measured before the parser was touched) |
| first run with detection | new layouts 1.00 except `L15` paragraph reconstruction 0.91: the last word of a reference line in the next column was taken into a table row, and two values in a narrow column were merged into one cell; fixed (stray-cell rule, cell gap 0.7) |
| `PY -m pytest -q tests/test_unruled_tables.py`, first run | 14 passed, **4 failed**: table emitted after the text below it on a two-column page (fixed: rows keep a placeholder during reading-order analysis); "F1" counted as a number; display equations read as a table; all fixed in the parser, no test changed |
| development papers, first comparison | regressions found by reading the changed sentences: numbered headings ("4 Experiments") read as rows, short prose lines of the neighbouring column pulled into tables, a loosely justified line cut into cells, a table bridging two unrelated text fragments; each fixed at its cause |
| single-row rule, first version | cut wrapped citation lists ("35, 37-43, 46,") out of their sentences in one development paper; restricted, regression test added |
| a test-file edit made with `sed` wrote a literal `\n` | collection error on the next run; repaired by hand, no assertion lost |
| `PY -m pytest -q` final | **217 passed, 0 failed, 0 skipped** (28 new: 20 in `tests/test_unruled_tables.py`, 8 benchmark layouts) |
| `PY -m eval.layout_bench --out eval/results/layout_bench/after_0.6.0-dev.json` | 29 layouts, 0 crashed; all measures 1.00 on the new layouts; the 21 earlier layouts identical to `after_0.5.1-dev.json` |
| `PAPERLENS_SRC=<adce476> PY -m eval.layout_bench --out .../baseline_adce476_29_layouts.json` | table-row recall 0.20 over 29 layouts, `table_leaks` 8 |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.6.0` | 16 papers, 0 crashed, 144 claims |
| `PY -m eval.table_text_dev data/Papers ...` for both versions | number-run prose sentences 48 -> 14; table sentences 406 -> 689 |
| `PY -m eval.claim_map map / merge / compare` (0.5.1-dev vs 0.6.0-dev) | 144 identical claims; 2 fresh pair labels; strict 23/61 vs 22/59, lenient 49/61 vs 48/59, coverage 61/99 vs 59/99 |
| `PY -m eval.structure_dev`, `PY -m eval.run_eval --n 100 --seed 7`, `PY -m eval.scifact_eval` | abstract 16/16, headings 83/85; synthetic and SciFact identical to 0.5.1-dev |

Not run: the application in the browser (parser-only change), the official held-out scorers, anything on the held-out
folders or audit files. `git stash` was used twice during the work and restored at once; no file was lost.
