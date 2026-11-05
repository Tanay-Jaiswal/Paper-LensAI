# CSE mode results (1.2.0)

Method, results and known mistakes: `docs/CSE_MODE.md`. All correctness labels are AI-assisted (written by Claude), not
human-verified.

| File | What it is |
|---|---|
| `before_1.1.0.json`, `after_dev.json` | 16 development papers before and after the CSE mode (scores, glossary, gaps) |
| `FREEZE.json` | code hashes before the first fresh-paper run |
| `check/` | first fresh set (6 papers), run once; `cs_items.csv` and `dictionary.csv` carry the labels |
| `check_after_fixes/` | the same 6 papers after the fixes (development data from then on) |
| `FREEZE_2.json` | code hashes before the second fresh-paper run |
| `check2/` | second fresh set (8 papers), run once with the frozen fixed code |

Paper lists: `data/cse_check_papers/MANIFEST.csv`, `data/cse_check2_papers/MANIFEST.csv` (PDFs are not committed).
