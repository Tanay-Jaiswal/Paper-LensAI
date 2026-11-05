# Computer Science & Engineering mode (1.2.0)

PaperLens can run extra checks written for Computer Science & Engineering (CSE) papers. Everything stays rule-based,
deterministic and offline: no model, no network, the same PDF always gives the same report.

## What the mode adds

| Part | What it does | Code |
|---|---|---|
| Field detection | `--mode auto` (default) treats a paper as CSE when at least 9% of body sentences use computing vocabulary or at least 8% of reference entries (5 or more) cite computing venues (NeurIPS, ACL, CVPR, arXiv cs ...). Both shares are printed in the report. `--mode cse` / `--mode general` overrule it. | `paperlens/field.py` |
| CS dictionary | About 260 standard CS abbreviations (CNN, LSTM, BERT, GPU, F1, mAP, TCP, FPGA ...). Used **only** for abbreviations the paper uses without defining; the paper's own definition always wins. Every dictionary meaning is labelled "dictionary"; abbreviations with several common meanings (CV, MAP, SSD, LR ...) show all of them and are marked ambiguous. Dictionary meanings are not used for evidence matching. | `paperlens/cse_terms.py`, `paperlens/glossary.py` |
| 10 CS checklist items | Working code link (not a promise), dataset sources/versions, exact hardware model, training/running time or compute budget, hyperparameter search, model selection on validation data, model size, how baselines were obtained, spread over runs in the results tables, efficiency (runtime, memory, complexity). The three training items are "not applicable" unless the paper talks about training a model in at least 3 sentences. | `paperlens/reproducibility.py` (`CSE_RUBRIC`) |
| 5 CS evidence gaps | Choices made on the test set (high), baseline numbers copied from other papers (low), code promised but not linked (medium), a gain of about one point with no significance test (medium), a state-of-the-art claim with no seeds or spread (medium). Each becomes a revision-checklist item. | `paperlens/gaps.py` (`_cse_gaps`), `paperlens/revisions.py` |

Scores: in CSE mode the main score covers the 15 standard items plus the CS items. The 15-item score is kept as
`standard_score` and is identical to the general mode's score, so papers checked in different modes can still be
compared (Compare uses it automatically when the two papers were checked differently).

## How it was tested (read before quoting any number)

All labels below were written by an AI assistant (Claude) reading the quoted sentence and searching the PDF text. They
are **AI-assisted, not human-verified**. Every label is in the CSV files, with a note for each wrong or unclear row.

1. **Development set**: the 16 papers of `data/Papers/` (9 CS, 7 other fields). Rules and thresholds were written and
   adjusted while looking at these. The general-mode results on these papers are unchanged (`standard_score` equals the
   1.1.0 score on all 16; `eval/results/cse_v1/before_1.1.0.json`, `after_dev.json`).
2. **First fresh set**: 6 CC BY 4.0 arXiv papers (cs.LG, cs.CV, cs.CL, cs.SE, cs.DC, cs.CR), chosen by a fixed rule
   (`eval/cse_select.py`) and run once with the code frozen (`FREEZE.json`). Results: `eval/results/cse_v1/check/`.
3. **Fixes**: the mistakes in step 2 were grouped by cause and fixed in general form (see below). From then on these 6
   papers are development papers. Results after the fixes: `check_after_fixes/`.
4. **Second fresh set**: 8 more papers (cs.AI, cs.IR, cs.NI, cs.RO, cs.DB, cs.HC, cs.LG, cs.CL, May 2025), same rule,
   run once with the fixed code frozen (`FREEZE_2.json`). Results: `eval/results/cse_v1/check2/`. Nothing was changed
   after this run.

## Results

| | First fresh set (6 papers, before fixes) | Same 6 after fixes (now development) | Second fresh set (8 papers) |
|---|---|---|---|
| Detected as CS | 4 of 6 | 6 of 6 | 8 of 8 |
| CS checklist decisions right / wrong / unclear | 34 / 20 / 6 of 60 | 51 / 3 / 6 of 60 | **55 / 18 / 7 of 80 (69% right)** |
| Dictionary meanings that fit the paper | 40 of 41 | 40 of 41 | **45 of 49** (3 wrong, 1 unclear) |
| Abbreviations left unexplained (general → CSE mode) | 70 → 55 | 70 → 55 | 92 → 77 |
| CS evidence gaps raised | 2 (both plausible) | 3 (the new one, unlinked code, is right) | 1 (wrong: it quoted an assumption the paper argues against) |

The second fresh set is the fairest number: 69% of CS checklist decisions right on papers the rules were never
adjusted on. It is better than the 57% of the first fresh set, but it is not "perfect" and should not be described so.

Field detection was only tested on fresh **CS** papers; whether it wrongly labels fresh non-CS papers as CS has been
checked only on the 7 non-CS development papers (all correct). The frozen held-out sets were not used.

## Known mistakes (second fresh set)

- Training items applied to papers that use but do not train models (an LLM evaluation, an HCI tool, a survey): 9 of
  the 18 wrong decisions. The 3-sentence training test is still too loose.
- Sentences about other people's work in the introduction count as this paper's report (GPT-3's V100 GPUs, "high
  latency" in general): 4 wrong decisions.
- Running times written as "8.97 s" or "tokens/s" are not read as a compute budget; a user-study duration was.
- Dictionary: CNN as the news network, DB as the paper's short name for DBLP, LP in a non-programming sense.
- The CS evidence gaps are written to be cautious and rarely fire (0 times on the 9 CS development papers).

## Fixes made after the first fresh set

Project pages (`github.io`) and "we open-sourced our code" without a link are partial, not a code link; whole words
only for data mentions; `NVIDIA 4090` without "RTX" counts as exact hardware; "runtime" and "compute" as plain words
are not a compute budget, a stated running time is; table cells do not earn prose items; a code link in a footnote that
lands in Related Work counts when the sentence says "our", "we" or "code"; the training items need sentences about
training; the venue-share threshold was lowered from 20% to 8% (non-CS development papers have at most 0.4%).
