# PaperLens AI session checkpoint (2026-10-12, sprint 2: abstract and section detection)

Written by the session that did the work, from commands it ran (`docs/TEST_REPORT.md`, section "0.4.0-dev").
The previous checkpoint is in Git: `git show 663bf4d:docs/SESSION_CHECKPOINT.md`.

## Verified state
- Folder `C:\Users\imcal\OneDrive\Desktop\PaperLens-AI`. Start: branch `dev/partial-support-v0.3`, commit `663bf4d`
  (code `a301d1a`), working tree clean, 119 tests passed (all as the previous sprint reported).
- New branch `dev/section-detection-v0.4` from `663bf4d`; the final commit is the tip of this branch (`git log -1`).
  Code version `0.4.0-dev`. `dev/partial-support-v0.3` is still `663bf4d`, `main` is `d6951bf`.
- Tags unmoved: `v0.1.0-frozen-heldout` = `d6951bf`, `v0.2.0-dev-frozen-heldout2` = `a549f25`.
- No remote is configured. Nothing was pushed or published.
- Use `.venv\Scripts\python.exe` (written `PY`); set `PYTHONIOENCODING=utf-8` for the eval scripts on Windows.
- `paperlens/ingest.py` is stored with CRLF line endings in Git; keep them (an editor or `sed -i` that rewrites them makes the diff the whole file).

## What was done and why (details: docs/EVALUATION.md section 10)
Root causes were found by dumping line geometry of the development PDFs first: headless-abstract fallback took the whole
page-1 front matter; footnote/venue lines extended abstracts; "Summary and Conclusions" became a second abstract;
italic or regular-type numbered headings were missed; appendices ("A", "A.1", split label) became references/other;
contents pages created fake sections; wrapped headings were split and fragments became headings; custom names
("4 User Evaluation") left no results section; ligatures and a sidebar rule dropped headings.
Changes in `paperlens/ingest.py`: `_heading_at` (explainable heading rules with sequence check, wrapped-heading join,
rejection of paragraphs, pull quotes, table header cells, captions), appendix tracking, contents-page detection, edge-strip
running headers, `keyword_section` fallback, headless-abstract choice by prose test, `NO_ABSTRACT` and over-long-abstract
warnings. Evidence linking, thresholds, ratings: untouched.
New: `tests/test_structure_v04.py` (17 tests incl. negatives), `eval/structure_dev.py`, `eval/dev_structure_labels.json`
(AI-assisted abstract boundaries, 16 dev papers), `eval/results/dev_v0.4/`.

## Commands and exact outcomes
| Command | Outcome |
|---|---|
| `PY -m pytest -q` | 119 passed before; **136 passed, 0 failed** after |
| `PY -m eval.structure_dev data/Papers eval/dev_structure_labels.json <out>` (before = `PAPERLENS_SRC` pointing at a `git archive 663bf4d paperlens` copy) | abstract start 15 to **16**/16, end 11 to **16**/16; bookmarked headings found 61 to **83**/85; detected headings that are bookmarks 61/94 to 83/113 |
| `PY -m eval.real_papers data/Papers eval/results/dev_v0.4` | 16 papers, 0 crashed, 147 claims (145 before); 142 of 144 common claims keep the top passage |
| labelled comparison (script, `score-labelled` cannot run: 3 new LIGO claims unlabelled) | strict 24/60 (was 24/59), lenient 49/60 (48/59); 1 dropped claim was labelled not-a-claim |
| `PY -m eval.run_eval --n 100 --seed 7`, `PY -m eval.scifact_eval` | identical to dev_v0.3 except timings (seed 99 not re-run) |
| Browser, LIGO dev paper | abstract warning, 9 claims, page/section labels, "1 of 3 claimed figures matched; not found: ..." and page images all displayed |

**Honest reading:** structure detection on the development papers improved clearly, but the labels are AI-assisted,
heading scores rest on 3 bookmarked papers, and the rules were tuned on these same papers. Evidence precision and
coverage did not measurably change. Nothing was measured on unseen papers.

## Known bugs, ranked by expected impact
1. Not yet reproduced on a layout like the failing held-out papers ("3 claims per paper", a 55-page paper with none; see
   `eval/results/held_out_v0.2/KNOWN_BUGS.md`, not opened this sprint). The new rules may or may not fix them; test on a third unseen set.
2. Run-in headings ("Methods. We ...") and regular-type unnumbered headings are not detected.
3. Partial support for claims without figures (experiment descriptions, table pointers, restatements) still returned as `weak`.
4. 59 of 143 claimed figures match no returned passage (tables, units, `91.2%` vs `0.912`).
5. Support ratings are not calibrated (`moderate`/`weak` right in about a quarter of cases or fewer).
6. Browser check covered one paper; a long paper (GPT-3) and a paper with no results section were checked only through the API.

## Next three tasks
1. Build a synthetic multi-column and 3-layout benchmark (two columns with spanning headings, side-by-side figures,
   rotated stamps) to test reading order; claim extraction collapse on odd layouts is the top open risk.
2. Reject "experiment announcement" passages for result claims (no figure, no outcome verb); measure on the dev labels
   and SciFact train before adopting.
3. Add run-in heading detection ("Methods." at the start of a paragraph) and label 3 to 5 more development papers' headings
   so heading precision is measured on more than 3 papers.

## Look here first
- `paperlens/ingest.py`: `_heading_at`, `_classify_heading` (via `_next_section`), `_is_toc_page`, `_style_run`, `_headless_abstract`, `_build`.
- `tests/test_structure_v04.py`, `tests/test_real_layout_fixes.py`, `eval/structure_dev.py`.

## Limitations of this session
- Browser: the pane's screenshot timed out once; the page was read through page text and DOM instead.
- Abstract labels were written by this session after seeing the parser output on the same papers (not independent).
- **Earlier slip, recorded as asked:** the previous sprint ran a repository-wide `git grep` for "flags" over `eval/`,
  which also searched tracked files under the first held-out set's `raw/analysis/` (30 lines of `"flags": [],` were shown;
  no label, key, claim or passage). Not repeated or investigated. This sprint opened, listed and searched nothing under
  `eval/results/held_out*` or its audit folders, and used narrowly scoped paths (`data/Papers`, `eval/results/dev_*`).

## Protected assets: what was actually checked
- `git diff --stat <start> HEAD -- eval/results/held_out eval/results/held_out_v0.2 eval/results/held_out_ai_audit eval/results/held_out_ai_audit_2 eval/results/held_out_v0.2_ai_audit eval/results/dev_v0.2 eval/results/dev_v0.3 data`:
  no differences (names only, no content opened).
- Both tags resolve to the commits listed above. Not re-run: raw-output hash checks, freeze verification, the official scorers.

## Still the owner's actions
Label `eval/results/held_out_v0.2/held_out_audit.csv` by hand before opening the AI audit files, then run
`python -m eval.held_out_v2 score eval/results/held_out_v0.2`. Do not tune on either held-out set or their labels.
`0.4.0-dev` needs a third unseen set before any unseen-data claim.
