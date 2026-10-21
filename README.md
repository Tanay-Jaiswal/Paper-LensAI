# PaperLens AI: Research Evidence & Reproducibility Auditor

Reading a research paper, it is hard to see which claims are actually backed by the paper's own results, what is left
unsaid, and whether anyone could repeat the work from what is reported. PaperLens reads a paper PDF and answers four
questions with checkable evidence, so a reviewer can verify every statement against the source page.

1. **What does the paper say?** A page-cited extractive summary. Every sentence is quoted verbatim.
2. **What does it claim, and where is the proof?** The **Research Evidence Ledger** links each headline claim to passages
   in the paper body (including table rows) with a support rating (`strong / moderate / weak / none`), the figures the
   passage shares with the claim, the reason a passage was chosen, and a page image with claim and evidence highlighted.
   When nothing suitable exists it says **"No supporting evidence found"** instead of attaching the least-bad passage.
3. **How reproducible does it look?** A transparent 15-item reporting checklist (code, data, splits, hyperparameters,
   seeds, variance, significance tests, baselines, compute, versions, ethics, limitations ...) with fixed weights, the
   quote that earned each credit and the items that are missing. It measures what the paper *reports*, not whether the
   work reproduces.
4. **Where are the evidence gaps?** Rule-based flags for a reviewer, such as "number in abstract never appears in
   results" or "claims 'significant' with no statistical test".

5. **Do the paper's own numbers add up?** The **Numbers check** finds statements that print a result next to the numbers
   it is computed from and redoes the arithmetic: percentages of counts ("45 of 120 (37.5%)"), stated differences
   ("from 81.2 to 84.6 (+3.4)"), table row and column totals including subtotal rows, row averages, F1 from precision
   and recall, estimates inside their confidence intervals, and p-values from test statistics. Every check shows the
   formula, the printed value and the page, and the checks that pass are listed too. On 35 real papers it found two
   substantive errors in published papers (a wrong denominator, a regional subtotal that does not match its rows);
   see `eval/results/consistency_v1/README.md` for what that does and does not show.

It can also **compare two papers** (similar claims, shared datasets and metrics, checklist differences).

**How it differs from a generic summariser.** Nothing is generated or paraphrased. Each output is a quote with a page
number or a rule you can read in the source, unsupported claims are shown as unsupported, and unreadable PDFs are
reported as unreadable rather than scored as poor papers. It runs offline: no API key, no GPU, no model download.
The price is that it is lexical and numeric, not a language model: "support" means the paper's own numbers and wording
agree, not that the argument is sound.

## Install and run (Windows PowerShell)

Prerequisite: Python 3.10 or newer (`python --version`). Checked with Python 3.13 and 3.14 on Windows 11.

```powershell
cd PaperLens-AI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell refuses to run the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or
skip activation and prefix every command with `.venv\Scripts\python.exe` instead of `python`.

Start the web app (one process serves both the API and the web UI; there is no separate frontend build):

```powershell
python -m paperlens serve
```

Open <http://127.0.0.1:8000>. Stop with Ctrl+C. Use `--port 8001` if port 8000 is busy.

### Use the web app

1. Drop a text-based PDF (up to 25 MB) on the box, or click it to choose a file. Analysis takes a few seconds.
2. **Summary**: page-cited sentences. **Evidence Ledger**: click a claim to see its passages, why each was chosen and the
   highlighted source page (click an image to open it full size). **Reproducibility**: score, missing items and the quotes.
   **Evidence gaps**: flags for review. **Compare**: contrast the current paper with one analysed earlier.
3. "Report: HTML / Markdown / JSON" downloads the analysis. Results are stored under `data/store/` (git-ignored).
4. "Load synthetic demo papers" generates two fake papers for a first look. They are not real studies.

### Command line

```powershell
python -m paperlens analyze paper.pdf --out report      # writes report\paper.json, .md and .html
python -m paperlens compare a.pdf b.pdf --out report    # writes report\comparison.json and prints the verdict
python -m paperlens --version
```

A missing, non-PDF, damaged or password-protected file prints one line (`paperlens: ...`) and exits with code 2.

### API

`POST /api/analyze` (multipart field `file`), `GET /api/analyses`, `GET /api/analyses/{id}`,
`GET /api/analyses/{id}/page/{n}.png?highlight=<sentence ids>`, `GET /api/analyses/{id}/report.{html,md,json}`,
`POST /api/compare` (`{"a": id, "b": id}`), `POST /api/demo`, `GET /api/health`. Interactive docs: `/docs`.
Errors: 400 not a PDF, 413 over 25 MB, 422 damaged or encrypted PDF, 404 unknown id.

## Tests

```powershell
python -m pytest -q          # 277 tests, under two minutes, no network
```

## Demonstration

`docs/DEMO_GUIDE.md` has a repeatable walk-through with exact steps and what to expect.

## Evaluation: what the numbers mean

`docs/EVALUATION.md` is the full record and must be read before quoting any number. Three kinds of result exist and
they are not interchangeable:

| Kind | Examples | What it shows |
|---|---|---|
| **Synthetic** | `python -m eval.run_eval`, `python -m eval.layout_bench` (generated PDFs, written by the same project) | The code does what it was designed to do. **Not** accuracy on real papers. |
| **AI-assisted labels** | evidence precision on 16 development papers; row-level table benchmark in `eval/table_truth/` | Labels were written by AI sessions (some of them the sessions that edited the parser). Useful for finding faults. **Not** independent ground truth. The table annotations are locked and unchanged. |
| **Human-verified** | none | No result in this repository has been checked by an independent person. |

Held-out evaluations (`eval/results/held_out*`) belong to earlier sprints and are frozen; they were not touched or used
for this release.

## Known limitations (short list)

No OCR (scanned PDFs are reported as unreadable); multi-column layouts are reconstructed from geometry and can be wrong;
tables of words and values split around super/subscripts are read imperfectly; claims without cue words are missed;
evidence that exists only in a figure or an equation is invisible; English only; support ratings are lexical and
unverified by humans. Full list: `docs/KNOWN_LIMITATIONS.md`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `python` not found | Install Python 3.10+ from python.org and tick "Add to PATH", or use `py -3 -m venv .venv`. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or call `.venv\Scripts\python.exe` directly. |
| `ModuleNotFoundError: pymupdf` / `fastapi` | The virtual environment is not active or `pip install -r requirements.txt` was not run in it. |
| Port 8000 already in use | `python -m paperlens serve --port 8001`. |
| Page images do not show / UI looks old | Hard-refresh the page (Ctrl+F5). Static files are sent with `no-cache`, so this should not be needed after an update. |
| "Could not read this PDF" | The file is damaged or password-protected. Remove the password and retry. |
| Warning "Very little extractable text" | The PDF is scanned images. PaperLens has no OCR and refuses to score it. |
| Folder inside OneDrive is slow or locked | Move the project to a path outside OneDrive. |

## Layout

```
paperlens/   ingest.py claims.py reproducibility.py gaps.py consistency.py summarize.py compare.py pipeline.py api.py cli.py report.py
web/         single-page UI (plain HTML/CSS/JS, no build step)
eval/        generators, benchmarks and frozen results (see docs/EVALUATION.md)
tests/       pytest suite
data/Papers/ development PDFs are kept locally only (git-ignored); MANIFEST.csv records source and licence
docs/        ARCHITECTURE.md EVALUATION.md DEMO_GUIDE.md KNOWN_LIMITATIONS.md TEST_REPORT.md SESSION_CHECKPOINT.md RELATED_WORK.md
```

Stack: Python, PyMuPDF (PDF text and geometry), FastAPI + Uvicorn (API and static UI), NumPy and scikit-learn
(TF-IDF and TextRank), pytest. Architecture: `docs/ARCHITECTURE.md`.

## Version history

`1.1.0` adds the Numbers check (`paperlens/consistency.py`, web tab, report section, `eval/consistency_eval.py`).
`1.0.0` is the finalisation release (CLI and API error handling, standalone HTML report, reworked web UI, documentation);
the analysis engine is unchanged from `0.6.1-dev`. Earlier development versions on this branch: `0.5.0-dev` column-aware
reading order; `0.5.1-dev` figure text kept out of sentences; `0.6.0-dev` tables without a grid; `0.6.1-dev` numbers in
the page body no longer deleted as page numbers. `0.2.0-dev` added abstention in the Ledger and `0.3.0-dev` and `0.4.0-dev`
compound-claim coverage and section detection (`docs/EVALUATION.md`). Tags: `v0.1.0-frozen-heldout`,
`v0.2.0-dev-frozen-heldout2`.
