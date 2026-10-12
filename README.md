# PaperLens AI: Research Evidence & Reproducibility Auditor

PaperLens reads a research-paper PDF and answers four questions with checkable evidence:

1. **What does the paper say?** A page-cited extractive summary (every sentence is quoted verbatim).
2. **What does it claim, and where is the proof?** The **Research Evidence Ledger** links each headline claim to the
   passages and pages in the paper body (including table rows) that support it, with a support rating
   (`strong / moderate / weak / none`), the shared numbers, and a page image with both passages highlighted.
3. **How reproducible does it look?** A transparent 15-item rubric (code, data, splits, hyperparameters, seeds,
   variance, significance tests, baselines, compute, versions, ethics, limitations ...) with fixed weights and the quote
   that earned each credit.
4. **Where are the evidence gaps?** Rule-based flags such as "number in abstract never appears in results",
   "claims 'significant' with no statistical test", "state-of-the-art claim with no described baselines",
   "generalisation claim backed by ≤2 datasets".

It can also **compare two papers** (aligned claims, shared datasets/metrics, rubric differences, verdict).

It runs fully **offline and free**: no API keys, no GPU, no model downloads. Everything is deterministic, so results are
reproducible and testable. Trade-off: it is lexical/numeric, not a language model, so "support" means *the paper's own
numbers and wording agree*, not that a model judged the argument sound. See `docs/ARCHITECTURE.md` and the limits in
`docs/EVALUATION.md`.

## Quick start (Windows PowerShell)

```powershell
cd PaperLens-AI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m paperlens serve            # open http://127.0.0.1:8000  (click "Load demo papers" for an instant tour)
python -m paperlens analyze paper.pdf --out report          # JSON + Markdown + HTML report
python -m paperlens compare a.pdf b.pdf --out report
python -m pytest -q                  # automated tests (106 on the development branch)
```

Run every command with the virtual environment active (or as `.venv\Scripts\python.exe -m ...`): the system Python does not
have the dependencies.

**Versions.** `0.1.0` is tag `v0.1.0-frozen-heldout`, the version run on the held-out papers. Branch
`dev/evidence-linking-v0.2` is `0.2.0-dev`: the ledger can now answer "No supporting evidence found" instead of attaching
the best-scoring passage, numbers match only when they measure the same quantity, and unsuitable passages are filtered.
On development data it returns fewer wrong passages and covers fewer claims (`docs/EVALUATION.md` section 6); it was
frozen as tag `v0.2.0-dev-frozen-heldout2` and run on 11 unseen papers, whose human labels are still missing (section 8).
Branch `dev/partial-support-v0.3` is `0.3.0-dev`: for a claim that cites several figures the three returned passages are
chosen to cover different figures, and the ledger says which claimed figures were not found (section 9; development
data only, top-passage precision unchanged).

Python 3.10+ required. macOS/Linux: same commands with `source .venv/bin/activate`.

## Evaluation

```powershell
python -m eval.run_eval --n 100                       # controlled synthetic benchmark (fast, offline)
python -m eval.scifact_eval --download                # real data: SciFact dev (needs internet)
python -m eval.real_papers data/Papers eval/results   # real PDFs: diagnostics + human audit sheet (see data/Papers/README.md)
python -m eval.held_out_audit score eval/results/held_out   # held-out audit: works only after a person has labelled the sheet
python -m eval.abstention_curve --split train --out eval/results/dev_v0.2      # 0.2.0-dev: abstention threshold vs precision/coverage
python -m eval.real_papers data/Papers eval/results/dev_v0.2                   # 0.2.0-dev results are kept apart from 0.1.0
python -m eval.quantity_coverage data/Papers eval/results/dev_v0.3 eval/results/dev_v0.2/dev_pairs_labelled.csv   # 0.3.0-dev: figures covered per claim
```

Read `docs/EVALUATION.md` before quoting any number: it states exactly what each benchmark does and does not show.

## Layout

```
paperlens/   ingest.py claims.py reproducibility.py gaps.py summarize.py compare.py pipeline.py api.py cli.py report.py
web/         single-page UI (no build step)
eval/        synth.py (PDF generator) run_eval.py scifact_eval.py audit.py results/
tests/       pytest suite
docs/        ARCHITECTURE.md EVALUATION.md RELATED_WORK.md KNOWN_LIMITATIONS.md EVIDENCE_LINKING_FIX_PLAN.md
             TEST_REPORT.md SESSION_CHECKPOINT.md
```

## Known limitations (short list)

Scanned PDFs (no OCR), heavily multi-column layouts where PDF text order is scrambled, non-English papers, claims
expressed without cue words, and evidence living only in figures. Full list in `docs/KNOWN_LIMITATIONS.md`.
