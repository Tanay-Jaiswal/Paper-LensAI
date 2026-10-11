# Evaluation

Three complementary protocols. **Read the "what it shows" column before quoting a number.**

| Protocol | Data | What it shows | What it does NOT show | Status |
|---|---|---|---|---|
| Synthetic benchmark (`eval/run_eval.py`) | Template-generated PDFs with planted facts | Pipeline plumbing: parsing, page attribution, claim→evidence linking, rubric & gap rules behave as designed | Accuracy on real papers (text is templated, rules were tuned while looking at it) | Run, results below |
| SciFact (`eval/scifact_eval.py`) | 1,409 expert-written claims + abstracts (Wadden et al., 2020), dev split | Evidence-passage ranking and "is evidence present?" on **real scientific prose**, against baselines | Full-PDF parsing; reproducibility rubric; gap rules | Run, results below |
| Real-paper run (`eval/real_papers.py`) | 16 real PDFs listed in `data/Papers/MANIFEST.csv` | Whether parsing, page references and verbatim quoting hold on real layouts; where they fail | Claim or evidence correctness (needs the human labels) | Run twice (baseline, then after parser fixes); both reported below. The fixes were tuned on these 16 papers |
| Human audit (`eval/audit.py`) | The same 16 PDFs | Claim precision and evidence precision on real PDF layouts | Recall (it only labels what the tool outputs) | Sheet generated (145 rows); **labels not yet filled in by a person** |
| Held-out audit (`eval/held_out_audit.py`) | 8 new PDFs in `data/held_out_papers/`, fetched after the code was frozen | Claim and evidence precision on papers the system was never tuned on | Recall; anything beyond 8 papers from 4 sources | Frozen run saved; 45-claim blinded sheet ready; **precision NOT yet computed (no labels)** |

## 1. Synthetic benchmark (n=100 papers, seed 7; held-out seed 99)

Five scenarios cycle: clean, one unsupported claim, "state-of-the-art" overclaim, "significant" overclaim, generalisation overclaim on one dataset.
Rubric items are randomly present/absent per paper. Ground truth is planted by the generator (`eval/synth.py`).

| Metric | seed 7 | seed 99 (run after rules were frozen) |
|---|---|---|
| Rubric item detection, micro F1 (14 items) | 1.00 | 1.00 |
| Headline-claim recall | 0.996 | 0.996 |
| Claim page accuracy | 1.00 | 1.00 |
| Supported claims: top-1 evidence is the planted passage | 1.00 (159) | 1.00 (159) |
| Evidence on correct page | 1.00 | 1.00 |
| Unsupported claims rated none/weak | 1.00 (80) | 0.975 (80) |
| Gap rules, paper-level precision | 1.00 for all 10 rules | 1.00 for all 10 rules |
| Gap rules, recall (lowest) | 0.925 (generalisation) | 0.95 (generalisation) |

Raw JSON: `eval/results/synthetic.json`, `eval/results/synthetic_seed99_holdout.json`.

**How to read this honestly.** Near-perfect scores are expected: the generated text uses a limited phrasing set and I fixed
rules after seeing failures on seed 7 (e.g. numbers inside `Yelp-5`, "Python 3.10" matching "3.1", a table header named "Method"
being parsed as a heading). Seed 99 was run afterwards without further tuning, but it comes from the same generator, so it is a
regression guard, not evidence of real-world accuracy. The value of this benchmark is that it caught real bugs and will catch regressions
(`tests/test_eval_smoke.py` enforces a floor).

## 2. SciFact (real data, dev split, 300 claims)

```powershell
python -m eval.scifact_eval --download      # ~3 MB from the official release
```

Rationale selection (rank a gold rationale sentence within the cited abstract; n=209 claim-abstract pairs):

| Scorer | hit@1 | hit@3 | MRR |
|---|---|---|---|
| PaperLens | 0.488 | 0.813 | 0.667 |
| BM25-only | 0.498 | 0.813 | 0.673 |
| First-sentence | 0.057 | 0.263 | 0.262 |
| Random | 0.182 | 0.483 | 0.400 |

| Other metrics | Value |
|---|---|
| Evidence-gap detection, AUROC of PaperLens best-passage score (188 claims with evidence vs. 112 NOT-ENOUGH-INFO) | 0.804 |
| BM25 abstract retrieval, recall@10 (n=188) | 0.931 |
| BM25 abstract retrieval, recall@100 (n=188) | 0.984 |

Raw JSON: `eval/results/scifact_dev.json` (single run, random baseline seed 0).

**How to read this honestly.** PaperLens is far above the random and first-sentence baselines, but plain BM25 is slightly *better* at
hit@1 (0.498 vs. 0.488) and MRR (0.673 vs. 0.667) and ties at hit@3, so on SciFact the numeric-agreement component adds nothing over
BM25 for rationale ranking; the AUROC of 0.804 was computed for the PaperLens score only, with no baseline to compare it against.

## 3. Real papers (16 PDFs, 331 pages)

```powershell
python -m eval.real_papers data/Papers eval/results
```

The set is 6 arXiv, 4 ACL Anthology and 6 PLOS papers (ML/NLP, physics, biomedicine, ecology, meta-science; 6 to 75 pages).
Sources, licences and checksums are in `data/Papers/MANIFEST.csv`.

The run was done twice on 2026-10-11: once on the code as first written (**baseline**), and once after the parser and linker
were fixed against the failures the baseline exposed (**after fixes**). Raw output of both runs is kept:
`eval/results/real_papers_summary.json` and `real_papers_audit.csv` (after fixes), and `real_papers_summary_baseline.json`
and `real_papers_audit_baseline.csv` (baseline).

### 3.1 Automatic checks, before and after (no human judgement)

| Check | Baseline | After fixes |
|---|---|---|
| Papers analysed without a crash | 16 / 16 | 16 / 16 |
| Page count equals PyMuPDF's | 16 / 16 | 16 / 16 |
| Title equals the manifest title (ignoring case and punctuation) | 9 / 16 | 16 / 16 |
| Sentences extracted | 7,137 | 9,337 |
| Sentences labelled results or experiments | 124 | 2,151 |
| Papers warned "no results/experiments section detected" | 6 | 5 |
| Papers with at least one claim | 15 | 16 |
| Claims extracted | 123 | 145 |
| Claim text found verbatim on the cited page | 118 / 123 | 144 / 145 |
| Claims that received a top evidence passage | 60 | 142 |
| Top evidence quote found on the cited page | 54 / 60 | 135 / 142 |
| Support rating: none / weak / moderate / strong | 88 / 8 / 20 / 7 | 37 / 32 / 32 / 44 |
| Claims rated `none` | 71.5% | 25.5% |
| Papers where every claim is rated `none` | 10 | 2 (CheckList, BLEU: 2 claims each) |
| Slowest paper | 7.8 s | 15.8 s |

"Found verbatim" compares letters and digits only, after re-opening the PDF, so it confirms the page reference and that the
quote is real text from the paper. **It says nothing about whether the sentence is a genuine claim or whether the evidence
supports it. The rise in moderate and strong ratings shows that the linker now finds passages; it does not show that those
ratings are correct.** That needs the human labels in section 3.4.

Got worse: the slowest paper (75 pages) takes twice as long because far more passages are now eligible as evidence, and the
number of evidence quotes that cannot be found on the cited page rose from 6 to 7 (all seven are figure or table text, see 3.3).
The synthetic benchmark (section 1) and SciFact (section 2) were rerun after the fixes and every number is unchanged.

### 3.2 What was fixed

Each fix targets a failure visible in the baseline run; none is keyed to a particular file. Each has a test in
`tests/test_real_layout_fixes.py` built from a small synthetic edge case.

| Baseline failure | Cause found | Fix |
|---|---|---|
| arXiv margin stamp used as the title (5 papers) and extracted as a claim (2 papers) | Rotated text was read like body text | Lines that are not horizontal are skipped |
| Title fell back to the filename; title truncated | A drop cap was the largest font on the page | Title is the largest-font run in the top half of page 1, ignoring very short lines when choosing the size |
| Words run together (`Itobtainsnewstate-of-the-art`) | Whitespace-only spans were being dropped, and some PDFs have no space character between word spans | Whitespace spans are kept; a space is restored where two spans are separated by a visible gap |
| Subsections labelled `other`; whole sections missing | The number and the heading text are separate lines in many PDFs; sub-headings did not inherit | Number and heading are merged; `4.1` inherits from `4`; a lighter or unnumbered sub-heading inherits its parent; Roman-numeral headings are recognised |
| Structured abstracts (Objective / Methods / Results) became body sections | Abstract labels matched body heading names | Labels stay in the abstract until one repeats or a body heading appears |
| 617 sentences assigned to Acknowledgments in the gravitational-wave paper | No headings were recognised, so the body stayed in the front matter and everything after Acknowledgments stayed there | Headings are now found (21 introduction, 201 body, 4 conclusion sentences); a reference list that starts with `[1]` and has no heading ends the acknowledgments. The author and affiliation list that follows the references in this PDF is still labelled references |
| Evidence never found in custom-named sections (`4.1 ImageNet Classification`, `II. OBSERVATION`) | Only standard section names were eligible | Body sections with paper-specific names are eligible with a low prior (0.3) |
| Table-number rows and author footnotes extracted as claims | No check that a sentence is prose | Sentences that are mostly numbers or have under 5 words are rejected; small-print footnote blocks are tagged `meta` |
| Citation line and sidebar fragment used as evidence | Publisher sidebar read as body text | A narrow strip left of the main column, and sentences that look like citation or copyright lines, are tagged `meta`: still read by the rubric, never a claim or evidence. Fragments under 4 tokens cannot be evidence |
| `13.4%` read as `134%` | The PDF's font does not map its decimal point to a character | Not guessed. The character is shown as `�`, the number is excluded from numeric matching, and the paper gets a warning (126 numbers in the CKD paper) |
| Hyperparameters and data splits scored as missing on physics, medical and essay papers | Rubric assumed every paper trains a model | Both items are `not_applicable` and left out of the score when a paper of 60+ sentences has fewer than 3 sentences with model-training vocabulary. Applied to 8 of 16 papers (counts were 0 to 2 there, 13 or more in every paper that trains a model) |
| `1.7×10−9` matched table rows containing "10" | Powers of ten were read as separate numbers | Exponent parts are ignored in numeric matching |

### 3.3 Failures that remain

Observed by reading the after-fixes sheet; not scored labels.

- **Figure and plot text leaks into sentences.** Axis labels and legends are read as prose. In the ATLAS paper one such string
  is extracted as a claim, and figure text is the top evidence for three claims, two of them rated `strong`. In the GPT-3 paper
  an appendix table that was not detected as a table is the top evidence for two claims. These are the 7 quotes that fail
  the page check.
- **Support ratings are unverified and probably optimistic.** Making custom-named sections eligible raised the number of
  rated claims, and lexical overlap will sometimes attach a merely related passage.
- **Few claims in some papers.** CheckList and BLEU yield 2 claims each, all `none`; BERT has 3 of 5 and the SciFact paper
  7 of 9 rated `none`. Claim detection is cue-based and these abstracts state contributions without numbers.
- **Glyph-mapping errors in the PDF itself.** The gravitational-wave PDF yields `þ` for `+` and `¼` for `=` (`36þ5 −4`).
  The CKD paper's decimal points are flagged rather than recovered, so its numeric claims cannot be matched on those numbers.
- **Hyphenation at line ends.** `English-to-German` broken after the first hyphen is rejoined as `Englishto-German`;
  `SCI-` / `FACT` stays split.
- **Table of contents and pull quotes.** The GPT-3 table of contents is read as headings (later headings override it), and a
  pull quote in the PLOS Medicine essay is read as a heading.
- **The rubric's "not applicable" rule is a vocabulary test.** It also fires on the BLEU paper (an evaluation-metric paper
  with no training), which seems right, but it has only been checked on these 16 papers.
- **Five papers still have no section named results or experiments** (CheckList, BLEU, the gravitational-wave paper and the
  two meta-science papers). Their evidence now comes from custom-named sections.

**How to read this honestly.** The fixes were developed while looking at these 16 papers, so the after-fixes column is a
measure of fit to this set, not of accuracy on unseen papers; a fresh set of PDFs is needed for that. What the numbers do
establish is that parsing (titles, word spacing, sections, page references) now holds on these layouts and that the ledger
is populated. Whether the ledger is *right* is still unmeasured.

### 3.4 Human audit (not yet labelled)

`eval/results/real_papers_audit.csv` has the 145 claims with the two label columns blank. Fill `is_real_claim` (y/n) and
`evidence_correct` (y/p/n), then run `python -m eval.audit score eval/results/real_papers_audit.csv` for claim precision and
evidence precision (overall and per support level). No precision figure is reported here because nobody has labelled the sheet.
If the *strong* level is not clearly more precise than *weak*, the support ratings are not calibrated and should be reported as such.

## 4. Held-out evaluation (8 unseen papers; precision not yet computed)

The 16 papers of section 3 are the **development set**: the parser and linker were tuned on them. This section is the test on
papers the system has never seen.

**Protocol, in the order it was carried out on 2026-10-11**

1. **Freeze.** SHA-256 of every file in `paperlens/` written to `eval/results/held_out/FREEZE.json` at 19:42:55 UTC, with all
   44 tests passing. `python -m eval.freeze verify eval/results/held_out/FREEZE.json` shows whether any frozen file has changed.
2. **Select and fetch.** Ten papers chosen by fixed first-match rules written before downloading (`data/held_out_papers/README.md`);
   eight downloaded (2 arXiv, 2 ACL Anthology, 3 PLOS, 1 Copernicus; 200 pages; all CC BY). Two failed to download (HTTP 404 and
   403) and were not replaced. None is in the development set.
3. **Run once.** `python -m eval.real_papers data/held_out_papers eval/results/held_out/raw` plus one full analysis JSON per
   paper in `raw/analysis/`. Hashes of the raw files are in `RAW_OUTPUT_HASHES.json`. Nothing was re-run or edited afterwards.
4. **Sample.** 45 of the 80 extracted claims, seed 20261011: every paper contributes at least 3, quotas are proportional to
   each paper's claim count, and within a paper the draw is proportional across support levels (`held_out_sample_info.json`).
5. **Blind sheet.** `held_out_audit.csv` shows paper, claim, page, evidence and evidence page, with `is_real_claim` and
   `evidence_correct` blank. PaperLens's support rating is kept out of the sheet, in `held_out_audit_key.csv`, so it cannot
   influence the labels. Labelling rules: `AUDIT_INSTRUCTIONS.md`.
6. **Score, later.** `python -m eval.held_out_audit score eval/results/held_out` refuses to run until every row is labelled.

**Descriptive statistics of the frozen run** (automatic; none of this is precision)

| Paper | Pages | Claims | none / weak / moderate / strong | Sampled | Parse warnings |
|---|---|---|---|---|---|
| ACL:2022.emnlp-main.200 | 12 | 11 | 4 / 6 / 0 / 1 | 6 | |
| ACL:2023.acl-long.100 | 15 | 7 | 5 / 2 / 0 / 0 | 4 | |
| arXiv:2303.00141v2 (cs.LG) | 66 | 13 | 10 / 1 / 0 / 2 | 7 | no results/experiments section |
| arXiv:2303.00194v1 (astro-ph.GA) | 27 | 25 | 6 / 0 / 7 / 12 | 14 | |
| Copernicus acp-21-8357-2021 | 20 | 6 | 0 / 2 / 1 / 3 | 3 | no Abstract heading |
| PMC7875335 (PLOS NTD) | 18 | 8 | 1 / 3 / 2 / 2 | 5 | no results/experiments section |
| PMC7875355 (PLOS Comput Biol) | 19 | 6 | 1 / 2 / 2 / 1 | 3 | no results/experiments section |
| PMC7886193 (PLOS Genetics) | 23 | 4 | 0 / 3 / 0 / 1 | 3 | |
| **Total** | 200 | 80 | 27 / 19 / 12 / 22 | 45 | |

| Automatic check | Held-out | Development set after fixes (section 3) |
|---|---|---|
| Crashes | 0 / 8 | 0 / 16 |
| Title equals the manifest title | 7 / 8 | 16 / 16 |
| Claim text found verbatim on the cited page | 80 / 80 | 144 / 145 |
| Claims with a top evidence passage | 78 / 80 | 142 / 145 |
| Evidence quote found on the cited page | 78 / 78 | 135 / 142 |
| Claims rated `none` | 33.8% | 25.5% |
| Papers warned "no results/experiments section" | 3 / 8 | 5 / 16 |

Section labelling is visibly weaker than on the development set: in four of the eight papers most of the body is labelled
`other` or `introduction` rather than method or results. These and the other problems noticed are listed in
`eval/results/held_out/KNOWN_BUGS.md`. They have **not** been fixed and the run has not been repeated.

**Not yet available.** Claim precision, evidence precision and whether `strong` is more precise than `weak` are **not
computed**, because no person has labelled the sheet. No labels were generated by the tool or by an AI assistant.

**Limitations.** Precision only (no recall). 45 rows give intervals of roughly plus or minus 0.15, and per-level figures will
rest on 6 to 14 rows. Eight papers from four sources, seven of them from sources also present in the development set.
One annotator unless the second-annotator option is used. If a bug is fixed later, that version must be run into a new
folder and reported separately, and these eight papers are then no longer unseen for it.

## 5. AI-assisted audit of the held-out sample (not human ground truth)

At the project owner's request the 45 held-out claims of section 4 were also labelled by an AI assistant (Claude), following
`AUDIT_INSTRUCTIONS.md`, on a separate copy of the sheet. **These are not human labels.** The human sheet is still blank and
human-labelled precision is still not computed. Method, per-row reasons and limitations: `eval/results/held_out_ai_audit/AI_AUDIT_README.md`.

| Measure (AI-assisted labels, n = 45, 95% Wilson interval) | Value |
|---|---|
| Claim precision | 0.822 (37/45; 0.69 to 0.91) |
| Evidence precision, strict (passage reports the same finding) | 0.162 (6/37; 0.08 to 0.31) |
| Evidence precision, lenient (same finding, or partial) | 0.622 (23/37; 0.46 to 0.76) |
| Real claim with fully supporting evidence, over all rows | 0.133 (6/45; 0.06 to 0.26) |
| Strict evidence precision by support level: strong / moderate / weak / none | 3/12, 0/5, 2/8, 1/12 |

What this suggests, with the caveats below: on unseen papers PaperLens mostly extracts sentences that are real claims, but its
top evidence passage fully supports the claim in roughly one case in six. Seventeen of the 37 passages are only partial
(captions, restatements, or support for one part of a compound claim) and 14 are unrelated. The support ratings show no sign
of calibration: `strong` is not more precise than `weak` on this sample.

Caveats that must travel with these numbers:
- The labeller is an AI, and the same one that wrote and tuned the system, built the sheet and wrote the instructions. It is
  not independent. It did not see per-row support ratings, but it had seen their per-paper counts.
- One labeller, no agreement measure; 8 of 45 rows are flagged as uncertain in the notes.
- Pages were read as extracted text, not as rendered images.
- 45 rows, 8 papers, precision only.

### 5.1 Second AI pass and agreement (still not human validation)

A second AI labelling pass was run by a fresh sub-agent that had no access to the first pass's conversation, labels or
results (`eval/results/held_out_ai_audit_2/AI_AUDIT_2_README.md`). Its labels were hashed before any comparison.

| Column | Rows | Raw agreement | Cohen's kappa |
|---|---|---|---|
| `is_real_claim` | 45 | 45/45 | 1.000 |
| `evidence_correct` (y / p / n) | 37 | 36/37 | 0.957 |
| `evidence_correct`, strict y vs not y | 37 | 37/37 | 1.000 |

The second pass gives the same claim precision (0.822) and strict evidence precision (0.162), and a lenient evidence precision
of 0.595 instead of 0.622. The single disagreement is one passage labelled partial by the first pass and wrong by the second.

**Agreement between two AI passes is not proof of correctness and is not independent human validation.** Both passes are
Claude models following rules written by the first labeller and reading the same extracted text, so they share the same
biases; near-perfect agreement is what correlated annotators produce. The first pass flagged 8 rows as judgement calls and the
second only 2, yet they gave the same labels, which points to a shared tendency rather than easy rows. Restricting the
sub-agent's file access could not be technically enforced; it reported opening none of the excluded files. Human-labelled
precision is still not computed.

## Automated tests

`python -m pytest -q`: 44 tests. 30 cover text utilities, ingestion (sections, tables, scanned-PDF warning), claim extraction and linking,
rubric formula and quotes, every gap rule (positive and negative case), comparison, API (upload, page render, reports, validation, dedup),
CLI, the SciFact evaluation code path on a fixture, and the synthetic regression floor. 14 in `tests/test_real_layout_fixes.py` cover the
real-paper fixes of section 3.2 using small synthetic edge cases (hand-made spans and one-page PDFs), not text from real papers.
