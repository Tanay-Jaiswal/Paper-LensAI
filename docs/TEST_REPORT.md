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
