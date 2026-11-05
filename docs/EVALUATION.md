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

## 6. Development version 0.2.0-dev (evidence linking; development data only)

Branch `dev/evidence-linking-v0.2`, code version `0.2.0-dev`. Sections 1 to 5 describe version 0.1.0 (tag
`v0.1.0-frozen-heldout`) and are unchanged. **Nothing in this section is a held-out result.** The 8 held-out papers were
not re-run, their key and raw outputs were not opened, and because the three fixes were motivated by failure types seen in
the held-out audit, those papers can no longer serve as an unseen test for this version. All files are in
`eval/results/dev_v0.2/`.

What changed (plan and risks: `docs/EVIDENCE_LINKING_FIX_PLAN.md`): (1) abstention: a passage is returned only if it
passes a relevance test, otherwise the claim shows "No supporting evidence found" (or "Evidence search not possible" when
no body text was extracted); (2) a number counts only when value, unit and/or neighbouring words agree; (3) passages that
cannot substantiate a claim (label-only captions, fragments, step headings, symbol dumps, boilerplate, near-copies of the
claim) are rejected with a recorded reason. In addition, abstract, introduction and conclusion sentences are now searched
(0.1.0 excluded them outright): one is returned only if it adds a specific or unit-bearing figure the claim does not
contain, is not itself an extracted claim, and no body passage was preferred. Body passages are ranked separately, so
this can add a passage but cannot change which body passage is returned.

### 6.1 Kinds of evidence in this section

| Kind | What it is here | Human-verified? |
|---|---|---|
| Synthetic | templated PDFs with planted facts (seeds 7, 99); synthetic unit-test fixtures | by construction |
| Human-labelled public data | SciFact train/dev rationale sentences (biomedical abstracts) | yes, by the SciFact authors |
| Automatic checks on real papers | counts on the 16 development papers; no judgement of correctness | no |
| AI-assisted labels | evidence correctness on the 16 development papers, labelled by the AI assistant | **no** |

No human has labelled PaperLens output on real papers for either version.

### 6.2 Synthetic benchmark (n=100 per seed)

| Seed | Measure | 0.1.0 | 0.2.0-dev |
|---|---|---|---|
| 7 | top-1 evidence hit / evidence page / supported rated strong or moderate | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 |
| 7 | unsupported rated none or weak | 1.0 | 1.0 |
| 99 | top-1 evidence hit / evidence page / supported rated strong or moderate | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 |
| 99 | unsupported rated none or weak; `unsupported_claim` gap F1 | 0.975; 0.987 | 1.0; 1.0 |

All other synthetic measures (rubric, claim recall and page, remaining gap rules) are identical to 0.1.0.

The first rerun of 0.2.0-dev was **worse**: top-1 hit 0.969, page accuracy 0.962, strong/moderate 0.987 (seed 7) and 0.981
(seed 99). Three causes were found and fixed, each with a regression test: the symbol-density rule counted short function
words ("as", "in", "of") as non-prose and rejected results sentences dense with figures; `89.1% F1` did not match `89.1 F1`;
and in "from 85.6 to 89.1" only the first number carried the metric. The table above is after those fixes. The synthetic
papers are templates, so this is a plumbing check, not accuracy on real papers.

### 6.3 SciFact (human labels)

Ranking metrics on SciFact dev, 209 claim-abstract pairs: hit@1 0.488 -> 0.493, hit@3 0.813 -> 0.818, MRR 0.667 -> 0.672;
BM25 alone is unchanged at 0.498 / 0.813 / 0.673, so PaperLens is still not better than BM25 at ranking rationale sentences.
AUROC for evidence present vs NOT-ENOUGH-INFO: 0.804 -> 0.810. Differences of this size are within noise for n=209.

Abstention curve (`eval/abstention_curve.py`): each claim is paired with each abstract it cites; a returned top passage is
correct if it is a gold rationale sentence; a pair without a rationale can only be answered correctly by abstaining.

| `MIN_LEXICAL` | train coverage | train precision | train recall | dev coverage | dev precision | dev recall |
|---|---|---|---|---|---|---|
| 0.0 (never abstain) | 1.000 | 0.322 | 0.525 | 1.000 | 0.303 | 0.493 |
| 0.20 | 0.653 | 0.420 | 0.447 | 0.632 | 0.419 | 0.431 |
| 0.25 | 0.529 | 0.471 | 0.406 | 0.524 | 0.472 | 0.402 |
| **0.30 (used)** | 0.431 | 0.500 | 0.351 | 0.424 | 0.521 | 0.359 |
| 0.35 | 0.333 | 0.542 | 0.294 | 0.335 | 0.535 | 0.292 |
| 0.40 | 0.263 | 0.574 | 0.246 | 0.276 | 0.596 | 0.268 |
| 0.50 | 0.171 | 0.611 | 0.170 | 0.191 | 0.662 | 0.206 |

Train: 919 pairs, 564 with a rationale. Dev: 340 pairs, 209 with a rationale. At 0.30 the linker abstains on more than half
of the pairs and is right about half the time when it answers; it also drops a third of the rationales it would otherwise
have found (train recall 0.525 -> 0.351). "Correct" here means "is a rationale sentence", not "fully supports the claim",
and SciFact abstracts are about nine sentences long, so the curve transfers to full papers only roughly.

**How the threshold was chosen, stated plainly.** The plan was to pick `MIN_LEXICAL` from the SciFact train curve. The
curve has no knee: precision rises and coverage falls smoothly, so any value is a judgement. The file times show this
history: the train curve was saved with the constant at 0.30; the development pairs were labelled at 0.30; a sweep over
those AI-labelled development pairs (`dev_threshold_sweep.json`) was then run; and 25 seconds later the constant in the code
was changed to 0.35, with no SciFact-based reason recorded. That last step is tuning on the development labels. It was
undone: the constant is 0.30 again, the value in place before the development labels were consulted, and a test pins it.
Whether 0.30 itself was read off the train curve or set beforehand cannot be established from the files. No further sweep
was run on the development papers. `dev_threshold_sweep.json` and `prev_at_0.35/` are kept as a record and are not results
of this version.

### 6.4 The 16 development papers: automatic counts

| Measure (145 extracted claims) | 0.1.0 | 0.2.0-dev |
|---|---|---|
| Claims with at least one returned passage | 142 | 83 |
| Abstentions ("No supporting evidence found") | n/a | 62 |
| "Evidence search not possible" | n/a | 0 |
| Support strong / moderate / weak / none | 44 / 32 / 32 / 37 | 29 / 23 / 31 / 62 |
| Top evidence quote found on its cited page (yes / no) | 135 / 7 | 82 / 1 |
| Claim text found on its cited page (yes / no) | 144 / 1 | 144 / 1 |
| Gaps reported (all kinds); `unsupported_claim` | 112; 56 | 137; 80 |
| Crashes | 0 | 0 |

**Worse:** 24 more `unsupported_claim` flags. A flag now also appears whenever the linker abstains, and section 6.5
indicates that some of those claims do have support in the paper. Top evidence by section: results 45, other 16,
discussion 10, experiments 8, method 2, introduction 1, conclusion 1. The two passages from the introduction and
conclusion belong to sentences that were not labelled real claims, so they do not enter section 6.5; read by the AI
assistant, one is related but indirect and one is not support. Searching the claim zone therefore added almost nothing on
these papers. Rejected candidates by reason (candidates, not claims, counted over a wider scan than before): below the
relevance threshold 2491, abstract/introduction/conclusion sentence without new data 2256, table row without a matching
value 624, fragment 265, label-only caption 108, symbols or numbers 88, boilerplate 88, summary section 21, step or proof
heading 15, table row for another quantity 5, restatement 1.

### 6.5 The 16 development papers: AI-assisted evidence labels (not human; not unseen)

Read this before the table.
- The labels were made by the AI assistant, not by a person. They are an estimate, not ground truth.
- They were made by the same session that wrote the fixes, from the claim and passage text alone, without re-opening the
  pages, in about two minutes for 414 rows. The fresh, blind labeller that was planned was not used. The sheet hid which
  version produced a pair, but the labeller had just written both versions.
- The pairs were pooled when `MIN_LEXICAL` was 0.30 (`DEV_LABELS_LOCKED.txt`; the recorded sha256 was re-checked and matches).
- The 16 papers were used to tune the parser and linker of 0.1.0, and the fixes were developed while looking at their
  output. These numbers say nothing about unseen papers.
- After the labels were locked the code changed (section 6.2). One top passage of the final version therefore has no
  label; it is left out of precision and counted. It was not labelled afterwards. (It is a results sentence giving the
  same two percentages as its claim, so it is probably correct; the ranges in the table cover both cases.)

97 of the 145 extracted claims were labelled real claims. On those 97:

| Measure | 0.1.0 | 0.2.0-dev | Direction |
|---|---|---|---|
| Coverage: real claims with a returned passage | 0.979 (95/97; 95% CI 0.93-0.99) | 0.619 (60/97; 0.52-0.71) | **worse** |
| Evidence precision, strict (fully supports) | 0.295 (28/95; 0.21-0.39) | 0.407 (24/59; 0.29-0.53); 0.400 to 0.417 with the unlabelled pair | better, intervals overlap |
| Evidence precision, lenient (full or partial) | 0.632 (60/95; 0.53-0.72) | 0.814 (48/59; 0.70-0.89) | better |
| Real claims with fully supporting evidence | 0.289 (28/97; 0.21-0.39) | 0.247 (24/97; 0.17-0.34); 0.258 if the unlabelled pair is correct | **worse** |
| Returned passages labelled wrong | 35 | 11 | better |
| Strict precision of `strong` | 0.714 (20/28) | 0.750 (15/20) | about the same |
| Strict precision of `moderate` | 0.105 (2/19) | 0.200 (3/15) | still poor |
| Strict precision of `weak` | 0.167 (5/30) | 0.250 (6/24) | still poor |

Source: `dev_precision_coverage_final.txt` (`python -m eval.dev_pairs score-labelled ...`). The earlier file
`dev_precision_coverage_at_0.30.txt` is the same comparison before the fixes of section 6.2 (coverage 0.639, strict 0.403,
fully supported 0.258).

What the comparison shows, within the limits above:
- The new version returns a passage for 35 fewer real claims. For 22 of them the old passage was labelled wrong, for 11
  partial and for 2 fully supporting. So about two thirds of the abstentions removed a wrong passage and about one third
  removed something useful.
- It returns a passage for no claim that the old version left empty; 49 real claims have the same top passage in both
  versions. The gain in precision comes almost entirely from removing passages, not from finding better ones.
- The number of claims shown with fully supporting evidence did not rise. A reader gets fewer wrong passages, not more
  right ones.
- Strict precision is about 0.41: most returned passages still do not fully support their claim. `moderate` and `weak`
  remain unreliable; only `strong` is right more often than not.
- The strict-precision intervals of the two versions overlap. On 60 to 95 passages with AI labels, the improvement in
  strict precision is not established; the drop in wrong passages (35 to 11) and in coverage is clear.

### 6.6 Not measured

- Precision or coverage of 0.2.0-dev on unseen papers. This needs a new held-out set, frozen code and a frozen procedure.
- Any human-labelled precision, for either version.
- Each fix on its own (no ablation was run).
- Whether the quantity matcher wrongly rejects true matches on real papers; only synthetic cases are tested.
- The web UI text, beyond a test that the script reads the field the API sends; the JavaScript is not executed in tests.

### 6.7 Automated tests for 0.2.0-dev

`python -m pytest -q`: **106 passed** (the 44 tests of 0.1.0, 59 in `tests/test_evidence_linking_v02.py` on synthetic
sentences, and 3 API tests for unreadable, corrupt and encrypted PDFs and for the new ledger fields). Commands and outcomes
are in `docs/TEST_REPORT.md`. One existing test was edited, `test_meta_sentences_and_fragments_are_not_evidence`: it used to check
that front-matter and fragment sentences are absent from the candidate pool, and now checks that they are absent from the
evidence returned by `link_evidence`, because 0.2.0-dev rejects them in the suitability filter. The same sentences must
still be excluded and the same two must still be returned, so the test was not weakened.

### 6.8 Other changes on this branch (not evidence linking)

- A PDF with almost no extractable text (a scan, an empty file) used to get a reproducibility score of 0 "low" and gaps
  such as "No code link is given". It now gets the band "not assessed", one gap `document_unreadable`, and a comparison
  that says the paper could not be read. Checked on a synthetic empty PDF; no scanned real paper was tested.
- The page-image endpoint now closes the PDF after rendering; `zoom=nan` falls back to the default.
- The API reports the package version instead of a fixed "0.1.0".
- Checked in a browser against the two built-in synthetic demo papers: upload/demo, ledger, the "No supporting evidence
  found" text on an abstained claim, page images with highlights, gaps and comparison all rendered. No real paper was
  tested in the browser.

## 7. Next validation plan for the revised version (not started)

Nothing below has been run. It is the procedure to follow once the owner decides the fixes are stable.

1. **Freeze first.** Decide `MIN_LEXICAL` from the SciFact train curve alone and write down why. Commit, tag the commit,
   and record `python -m eval.freeze write <new folder>/FREEZE.json`. No code change after that counts for this test.
2. **Freeze the procedure before any data is fetched:** the selection rule for papers, the number of papers and sampled
   claims, the seed, the labelling instructions (reuse `AUDIT_INSTRUCTIONS.md` unchanged), the measures (claim precision,
   coverage, strict and lenient evidence precision, share of real claims with fully supporting evidence, precision per
   support level, all with 95% intervals), and what result would count as "no better than 0.1.0".
3. **A new unseen set.** The 8 existing held-out papers cannot be reused: the fixes were motivated by their failures.
   Candidate open-access sources, the same kinds as before so that results are comparable: ACL Anthology (CC BY),
   arXiv papers under a CC licence, PLOS journals (CC BY), the PubMed Central open-access subset. Choose by a rule fixed in
   advance (for example the first N papers of a stated venue and month that are not in `data/Papers` or
   `data/held_out_papers`), not by looking at them. Nothing has been downloaded.
4. **Run both versions on the same new papers** (0.1.0 from the tag, 0.2.0 frozen), pool their top passages into one
   blind sheet with the version hidden (`eval/dev_pairs.py` does this), and label once.
5. **Labels.** Human labels by the owner are the only ground truth. An AI-assisted pass may be added but must be
   reported separately, made by a labeller that did not write the code, and never merged with human labels.
6. **Report** every measure with its interval, the abstention cost next to the precision gain, and the failure cases,
   in a new numbered section. Earlier sections stay as they are.

What exists today, by kind: synthetic tests (pass); human-labelled public data, SciFact (ranking no better than BM25;
abstention curve in 6.3); automatic counts on 16 development papers; AI-assisted labels on development papers (6.5) and on
the old held-out sample for 0.1.0 (section 5). Human-verified results for PaperLens output: none.

## 8. Second held-out evaluation: 0.2.0-dev on 11 unseen papers (automatic measures only; precision not yet computed)

Carried out on 2026-10-12 under a protocol written and frozen before any paper was searched for
(`eval/results/held_out_v0.2/PROTOCOL.md`; freeze `FREEZE_MANIFEST.json`, tag `v0.2.0-dev-frozen-heldout2`; threshold 0.30).
The first held-out evaluation (section 4) and its audits (section 5) were not touched or re-used. Full account, failures
and reproduction commands: `eval/results/held_out_v0.2/RESULTS.md`.

- 13 candidates planned by fixed first-match rules, 11 obtained (4 arXiv, 3 ACL Anthology, 2 PLOS, 1 eLife, 1 Copernicus;
  286 pages; all CC BY). Two downloads failed and were not replaced.
- One run, raw outputs hashed and committed before anything was read. 0 crashes.
- **33 claims extracted**, far fewer than expected (the plan was to sample 60); one 55-page paper yielded none.
- Automatic: a passage was returned for 23 of 33 claims (0.697; 95% CI 0.53-0.83); 10 abstentions (0.303; 0.17-0.47); no
  "search not possible". All 33 claim texts and all 23 evidence quotes were found on their cited pages.
- A blinded sheet with all 33 claims awaits the owner's labels (`held_out_audit.csv`). **No precision figure exists.** No
  label was produced by the tool or by an AI assistant.

For comparison only, and not paired: on the first held-out set version 0.1.0 returned a passage for 78 of 80 claims. The
two runs are on different papers.

Limits: evidence precision will rest on at most 23 passages (interval about plus or minus 0.2); 11 papers from five kinds
of source; abstention correctness and claim recall are not measured. Problems seen in the run are listed, unfixed and
uninvestigated, in `eval/results/held_out_v0.2/KNOWN_BUGS.md`.

### 8.1 AI-assisted audit of the second held-out sheet (not human ground truth)

At the owner's request the 33 rows were labelled twice by AI on 2026-10-12: by the assistant that ran the evaluation, and
independently by a fresh-context labeller that saw only the instructions, the blank sheet and the PDFs. Files, rationales,
disagreements and limitations: `eval/results/held_out_v0.2_ai_audit/AI_AUDIT_README.md`. The blank sheet, the sealed key and
the raw outputs were not modified, and the key was not read; the official scorer was not run, so there is no breakdown by
support level. **The human audit defined by the protocol is still open.**

| Measure (AI-assisted, 95% CI) | Pass 1 | Pass 2 | Conservative consensus |
|---|---|---|---|
| Claim precision | 0.818 (27/33) | 0.788 (26/33) | 0.788 (26/33; 0.62-0.89) |
| Coverage on real claims | 0.741 (20/27) | 0.731 (19/26) | 0.731 (19/26; 0.54-0.86) |
| Evidence precision, strict | 0.250 (5/20) | 0.316 (6/19) | 0.211 (4/19; 0.09-0.43) |
| Evidence precision, lenient | 0.900 (18/20) | 0.895 (17/19) | 0.842 (16/19; 0.62-0.94) |
| Real claims with a fully supporting passage | 0.185 (5/27) | 0.231 (6/26) | 0.154 (4/26; 0.06-0.34) |

The passes agree on `is_real_claim` in 32 of 33 rows (kappa 0.90) and on `evidence_correct` in 14 of 19 (kappa 0.51).

Reading: on unseen papers most returned passages still do not fully support their claim (strict precision 0.21 to 0.32);
most are partial, and 2 or 3 of about 20 are wrong. Against the AI-assisted figures for 0.1.0 on the first held-out set
(strict 0.16, lenient 0.62; section 5) the lenient figure is higher, but the strict intervals overlap almost completely and
the two audits are on different papers, so an improvement in strict precision is **not shown**. Two AI passes, both Claude,
are not human validation; pass 1 was made by the assistant that wrote the fixes.

## 9. Development version 0.3.0-dev: compound claims (development data only)

Branch `dev/partial-support-v0.3`, started from `45b2ca2`. Nothing here was measured on unseen papers, and the two
held-out sets and their labels were not used. The labels quoted are the AI-assisted development labels of section 6.5
(not human, not unseen), and they describe the **top passage only**.

### 9.1 Diagnosis: why a returned passage is only partial support

The 0.2.0-dev run on the 16 development papers has 24 top passages labelled `p` (partial) among 59 labelled ones.
Reading the labeller's notes for all 24:

| Cause | Count | Example note |
|---|---|---|
| Compound claim: the passage supports one of several figures, tasks or parts | 13 | "one of three scores", "only the training-time part" |
| The passage describes the experiment, points to a table, or gives one example, without stating the result | 7 | "describes the experiment, no result", "pointer to Table 4" |
| The passage restates the claim without data | 4 | "near-restatement without data" |

Compound claims are the largest single cause. Of the 24, 8 are claims that cite figures and 16 are not. For claims
with figures, the top passage matching every claimed figure separates the labels well: `y` 11, `p` 1, `n` 1 when it
does; `y` 6, `p` 7, `n` 7 when it does not (`eval/results/dev_v0.3/quantity_coverage.json`).

### 9.2 Change

- `claims._complementary`: the first returned passage is unchanged (best-ranked accepted passage). The second and third
  places go first to accepted passages that match a claimed figure not yet matched, then to the next by rank. No passage
  is accepted that 0.2.0-dev would have rejected.
- `claims.quantity_coverage`, stored on every claim as `quantity_coverage` (`claimed`, `top`, `found`, `missing`), and a
  `partial_quantity_coverage` flag when a claimed figure has no returned passage. The Markdown report and the web UI
  show "k of n claimed figures matched; not found: ...".
- Support levels, thresholds and the abstention rule are unchanged.

### 9.3 Results (16 development papers; `python -m eval.quantity_coverage data/Papers eval/results/dev_v0.3 eval/results/dev_v0.2/dev_pairs_labelled.csv`)

51 claims cite figures and have a passage; they cite 143 figures.

| Automatic count | 0.2.0-dev selection | 0.3.0-dev selection |
|---|---|---|
| Claimed figures matched by the top passage | 68 / 143 | 68 / 143 (same passage) |
| Claimed figures matched by the three returned passages | 78 / 143 | 84 / 143 |
| Claims with every figure matched by the returned passages | 20 / 51 | 22 / 51 |

These are counts of matched figures, **not evidence precision**: nobody has judged whether a set of passages supports
a claim. 59 of 143 claimed figures are still matched by no returned passage, and 10 claims with figures have a top
passage that matches none.

Unchanged, as intended (`eval/results/dev_v0.3/dev_precision_coverage_v0.2_vs_v0.3.txt`): all 145 audit rows are
identical to 0.2.0-dev, so coverage 0.619 (60/97), strict precision 0.407 (24/59), lenient 0.814 (48/59), wrong
passages 11, abstentions and the support distribution are the same. Synthetic seeds 7 and 99 and SciFact dev are
identical to section 6 apart from run times. There is no regression and **no gain in top-passage precision**.

**Experiment not adopted.** Requiring the top passage to match every claimed figure before rating a claim `strong`
would move 5 labelled claims from `strong` to `moderate`: 3 labelled `y`, 1 `p`, 1 `n`. Strict precision of `strong`
would go from 15/20 to 12/15, well inside the interval. The evidence does not justify changing the rating rule, so
coverage is reported next to the rating instead of altering it. A test pins this.

### 9.4 Not measured, not fixed

- Whether the complementary passages are correct. They pass the same tests as any returned passage, whose strict
  precision on these papers is about 0.4.
- The 16 partial passages of claims without figures (experiment descriptions, pointers, restatements, one of several
  named tasks). Nothing in this version addresses them.
- Anything on unseen papers. A third unseen set would be needed to evaluate this version.

## 10. Development version 0.4.0-dev: abstract and section detection (development data only)

Branch `dev/section-detection-v0.4`, started from `663bf4d`. Only the 16 development papers (`data/Papers`) and
synthetic PDFs were used. Neither held-out set, their raw outputs, keys, labels or scores were opened or used; the
parser was tuned on the 16 development papers, so the numbers below are development numbers, not evidence of accuracy
on unseen papers.

### 10.1 Root causes (found by dumping line geometry of the development PDFs before changing code)

| # | Failure seen | Cause in `paperlens/ingest.py` |
|---|---|---|
| 1 | LIGO-style first page: authors, dates and DOI became the "abstract" | the fallback relabelled all page-1 front matter |
| 2 | Abstract ran into a footnote or venue line (Attention, GPT-3) | only the first small-print block of a page was footnote text |
| 3 | PLOS "Summary and Conclusions" on page 11 became a second abstract (13 sentences) | prefix match to the key "summary" |
| 4 | Headings in body-size italic or regular type not found (ATLAS: 18 of 31 bookmarks missed) | heading needed bold or larger type |
| 5 | Appendices became `references` or `other` (SciFact, BERT, ResNet, GPT-3) | appendix letters ("A", "A.1") and the split label/title were not recognised |
| 6 | Contents page (GPT-3) created sections "2 Approach", "6 Broader Impacts" on page 2 | page was read as structure |
| 7 | Wrapped headings split in two; fragments such as "O2peak)" became headings | no multi-line heading logic, no bracket check |
| 8 | Custom names such as "4 User Evaluation" and "3 The BLEU Evaluation" left no results/experiments section (4 papers warned) | exact-name vocabulary only |
| 9 | Ligatures broke heading matching; a bold standard heading beside a reference list was dropped as a margin sidebar | text compared before normalising; sidebar test |
| 10 | Bold paragraphs, pull quotes and table header cells risked being read as headings | not previously covered |

### 10.2 Change (explainable rules, conservative fallbacks)

Headings are decided by `_heading_at`: a typographically marked standard name; a numbered heading that is bold, larger or
italic with a number that continues the sequence (`_seq_ok`); an appendix label that follows the last one; a short bold
or large line with no sentence shape. Wrapped lines are joined only when they continue in the same style. Rejected:
bold paragraphs (5+ lines), pull quotes (kept as `meta`), table header cells, caption labels, contents entries and
dotted leaders, unbalanced brackets, dangling last words. A contents page is kept as front matter and read for no
structure. A custom heading takes a standard section only through a first or last content word
(`keyword_section`, four words at most) and only as a fallback.

Abstract: exact "Abstract"/"Summary"/spaced capitals, run-in "Abstract. ..." and structured labels as before. Without a
heading the first prose paragraph of page 1 (40+ words, mostly lower case, no e-mail address) and directly following
paragraphs of the same size are used, and the document warns "No 'Abstract' heading detected ...". If there is no such
paragraph nothing is labelled abstract and the document says so (`NO_ABSTRACT`). Keyword lines and display text end an
abstract; an abstract above 30 sentences warns.

### 10.3 Results on the 16 development papers (`python -m eval.structure_dev data/Papers eval/dev_structure_labels.json <out>`)

Abstract labels are AI-assisted (written by the session that changed the parser, from the PDF text layer), not human.
Heading scores use the authors' own PDF bookmarks, available for 3 papers only (ATLAS, Attention, GPT-3; 85 entries).

| Measure | 0.3.0-dev (`663bf4d`) | 0.4.0-dev |
|---|---|---|
| Abstract start correct | 15 / 16 | 16 / 16 |
| Abstract end correct | 11 / 16 | 16 / 16 |
| Bookmarked headings found (recall) | 61 / 85 | 83 / 85 |
| Detected headings that are bookmarks (precision) | 61 / 94 | 83 / 113 |
| Papers warned "no results/experiments section" | 5 | 3 |

The 30 extra detected headings are mostly run-in sub-headings that authors leave out of bookmarks (GPT-3: 23), so
precision here is a lower bound. Missed: ATLAS "6 H->WW(*)->evmuv channel" and Attention "Results" (a bookmark with no
heading line).

Evidence pipeline (`eval.real_papers` to `eval/results/dev_v0.4`, compared with the existing development labels):
147 claims (145 before). 144 are common and 142 keep the same top passage; 1 old claim dropped (labelled not a claim:
"Recommendations ...", PLOS) and 3 new LIGO claims are unlabelled. On labelled rows: 61 of 97 real claims have a
passage (60 before), strict 24/60 (24/59), lenient 49/60 (48/59). `eval.dev_pairs score-labelled` cannot run because
of the 3 unlabelled claims, so this was compared by script. No change in strict precision can be shown. Synthetic seed 7
and SciFact dev are identical to 0.3.0-dev apart from run times.

### 10.4 Not measured, not fixed

- Nothing on unseen papers. Abstract and heading rules were tuned on the 16 papers that score them.
- Multi-column order depends on PyMuPDF; no layout engine was added, and no test uses a 3-column or rotated layout.
- Heading precision against a labelled set (only 3 papers have bookmarks).
- Run-in headings inside a paragraph ("Methods. We ...").

## 11. Development version 0.5.0-dev: reading order on synthetic layouts (synthetic and development data only)

Branch `dev/reading-order-v0.5`, started from `d4862d2`. Held-out data, raw outputs, keys and labels were not opened or
used. The benchmark is **synthetic**: the text is template-made and the layouts were drawn by the same session that
changed the parser, so a perfect score here shows that the parser handles these geometries and nothing about real
papers. Three stress layouts were added after seeing the first results, to test limits the parser was not written against.

### 11.1 How the documents and their truth are made (`eval/layout_synth.py`)

1. A seeded generator writes a *logical document* (title, front matter, abstract with two result claims, numbered
   sections, optional table, figure and captions, references) and, for each claim, the sentence in the results section that
   states the same figures. Every document id has a fixed seed (a hash of the id).
2. A flow engine places the blocks line by line into page regions (columns, full-width areas, grids), using PyMuPDF only to
   measure text widths. A paragraph that does not fit continues in the next region, re-wrapped for that region's width.
   Mid-sentence page breaks, an orphaned heading at the end of a page, running headers, page numbers and footnotes are
   produced on purpose.
3. Only the order in which lines reach the content stream varies (`stream`): `natural` (reading order), `blocks_y`
   (blocks sorted by vertical position), `lines_y` (lines sorted by vertical position, so two columns alternate line by
   line) or `shuffled`. A parser that trusts the stream order is right only for the first.
4. The truth file `<id>.truth.json` is written from the logical document and the positions the engine chose: `blocks`
   (id, kind, section, text, `units` = the pieces of the block with their page, quantities, table rows) in reading order,
   `claims` (sentence, block, page, evidence sentence, evidence block and page), `headings`, `excluded` furniture,
   `ambiguous` and `accepted_orders` for the grid. Nothing is copied from parser output; `tests/test_layout_bench.py`
   checks that the generator does not import the parser and that two generations are byte-identical (`MANIFEST.json`
   holds the sha256 of every PDF and truth file). The PDFs are generated on demand and are not committed.

Layouts (21 documents, 13 categories): single column (control); two columns with the stream natural, block-sorted, line-sorted
and shuffled; two columns with full-width paragraphs; page boundaries (sentence cut across a page, heading alone at the bottom,
single and two-column); captions and tables between text; scientific quantities and units; furniture (alternating running heads,
page numbers, footnotes, references); mixed single and double column pages; 6 pt gutter; a 2 x 2 grid of independent notes
(ambiguous); and the stress layouts: three columns, unequal columns, a nearly empty second column.

### 11.2 Metrics (`eval/layout_bench.py`; the definitions are in its docstring)

Matching uses letters and digits only. Block recall and precision are character shares; reading order is the share of
block pairs, among blocks covered at least 50%, whose first sentence appears in the true order (the best of the accepted
orders for the ambiguous layout); paragraph reconstruction needs the matched sentences of a block to equal it exactly
with no foreign sentence in between; page attribution uses the page where the sentence starts. A missing block counts
as missing, never out of the denominator. Not-applicable metrics (no table, no claim) are left out of the mean of that metric only.

### 11.3 Results (`python -m eval.layout_bench --out <file>`; baseline = the parser of `d4862d2` via `PAPERLENS_SRC`)

Macro mean over 21 documents, baseline / after:

| Metric | baseline `d4862d2` | 0.5.0-dev |
|---|---|---|
| block recall | 0.92 | 1.00 |
| block precision | 0.92 | 1.00 |
| reading-order accuracy | 0.93 | 1.00 |
| paragraph reconstruction | 0.75 | 0.99 |
| page attribution | 1.00 | 1.00 |
| claim recall | 0.95 | 1.00 |
| claim page correct | 1.00 | 1.00 |
| evidence passage correct (inside the designated block, right page) | 0.79 | 1.00 |
| heading recall | 0.90 | 1.00 |
| section accuracy | 0.78 | 1.00 |
| abstract precision | 0.74 | 1.00 |
| abstract recall | 0.95 | 1.00 |
| quantity recall | 1.00 | 1.00 |
| table row recall | 1.00 | 1.00 |
| title exact | 1.00 | 1.00 |
| ambiguous layout handled safely (no splice, or flagged) | 0.00 | 1.00 |
| spliced sentences (text of two blocks in one sentence) | 52 | 0 |
| running header / page number / footnote returned as text | 1 | 0 |
| extracted claims that splice two blocks | 7 | 0 |
| evidence passages that splice two blocks | 0 | 0 |
| layout warnings on layouts that are not ambiguous | 0 | 0 |

Per category (documents), baseline / after:

| Category | block recall | reading order | paragraph recon | spliced | evidence |
|---|---|---|---|---|---|
| single_column (1) | 1.00 / 1.00 | 1.00 / 1.00 | 0.89 / 1.00 | 0 / 0 | 1.00 / 1.00 |
| two_column (4) | 0.87 / 1.00 | 0.82 / 1.00 | 0.75 / 1.00 | 26 / 0 | 0.67 / 1.00 |
| two_column_spanning (2) | 0.99 / 1.00 | 0.98 / 1.00 | 0.65 / 1.00 | 1 / 0 | 1.00 / 1.00 |
| page_boundaries (2) | 1.00 / 1.00 | 0.97 / 1.00 | 0.78 / 1.00 | 0 / 0 | 0.50 / 1.00 |
| captions_tables (2) | 0.98 / 1.00 | 0.95 / 1.00 | 0.91 / 1.00 | 2 / 0 | 0.50 / 1.00 |
| quantities (2) | 0.99 / 1.00 | 0.95 / 1.00 | 0.86 / 1.00 | 1 / 0 | 1.00 / 1.00 |
| furniture (1) | 1.00 / 1.00 | 1.00 / 1.00 | 0.67 / 1.00 | 1 / 0 | 1.00 / 1.00 |
| mixed_columns (1) | 1.00 / 1.00 | 0.92 / 1.00 | 0.89 / 1.00 | 0 / 0 | 1.00 / 1.00 |
| tight_gutter (2) | 1.00 / 1.00 | 0.96 / 1.00 | 0.83 / 1.00 | 0 / 0 | 0.50 / 1.00 |
| stress_three_columns (1) | 0.98 / 1.00 | 0.89 / 1.00 | 0.56 / 1.00 | 1 / 0 | 1.00 / 1.00 |
| stress_unequal_columns (1) | 1.00 / 1.00 | 0.92 / 1.00 | 0.89 / 1.00 | 0 / 0 | 1.00 / 1.00 |
| stress_sparse_column (1) | 0.98 / 1.00 | 0.89 / 0.92 | 0.78 / 0.89 | 1 / 0 | 1.00 / 1.00 |
| ambiguous (1) | 0.00 / 1.00 | n/a / 1.00 | 0.00 / 1.00 | 19 / 0 | n/a / n/a |

Files: `eval/results/layout_bench/baseline_d4862d2.json`, `after_0.5.0-dev.json`. Both runs reproduce (the baseline was run twice
with identical output; its file records which `paperlens` it imported). Remaining imperfection: `L13_sparse_column_blocks_y`
(reading order 0.92, paragraph reconstruction 0.89): a right column with a single line is not separable from the left, so the PDF's
own order is kept and the line lands in the wrong place. Nothing is flagged for it.

### 11.4 What changed (`paperlens/ingest.py`)

- Column-aware reading order (`_reorder_columns`, XY-cut): a gutter of at least 4 pt that no text crosses, with 3 or more prose
  lines (25+ characters) on each side, splits a region into columns; otherwise the region is cut at its widest white band and
  read top to bottom; a region that cannot be cut keeps the PDF's order if it runs downwards. A page without a gutter is left
  as delivered. A white band across both columns with 3+ lines of each above and below makes the page ambiguous: rows are read
  first and the document carries a `Layout warning`.
- A sentence that runs over a page break is completed on the next page and gets the page where it started (it used to be cut
  in two and the tail dropped when shorter than 25 characters).
- Tables are placed in the column they sit in; drop caps are joined to their word and end a summary box; a wide white band after the
  abstract ends it; small-print publisher boxes and footnote marks followed by a space are notes; running heads that alternate
  between pages are removed after two sightings.

### 11.5 Effect on the 16 development papers (real PDFs, no ground truth beyond earlier AI-assisted labels)

Abstract start/end 16/16 and 16/16 (unchanged), bookmarked headings 83/85 (unchanged). The line order changed on 59 of 320 pages (page-number lines ignored; the first difference is usually a publisher header or footer line, or figure text,
moving to the geometric position; not otherwise classified). The sentence count per paper changed by -8 to +10 (fragments split by a page break are now
whole sentences). Evidence pipeline: 147 to 146 claims; 141 common, 135 of them with the same top passage; 6 old claims dropped
(2 labelled real: both were fragments of sentences that now appear whole and unlabelled) and 5 new ones (all unlabelled). On rows that still have a
label: strict 21/54, lenient 43/54 (before 24/60 and 49/60); the 7 claims and 4 returned passages that lost their label are not scored,
so no change in evidence precision can be claimed in either direction. Two new splices of figure text into a claim on real papers
were seen (ATLAS figure legend, SciFact figure text). Seed-7 synthetic and SciFact dev identical.

### 11.6 Not measured, not fixed

- Nothing on unseen papers; the held-out failures (few claims from some layouts) were not reproduced or examined.
- Real three-column, rotated, scanned-with-OCR-text and right-to-left layouts; text in figures.
- Unruled tables whose cells sit side by side are read in the PDF's order and can be glued to nearby text.
- The sparse-column case above, and any column with fewer than 3 lines.

## 12. Development version 0.5.1-dev: figure text, and a valid comparison on real development papers

Branch `dev/reading-order-v0.5`, continued from `7b3485f`. Development papers and synthetic PDFs only; no held-out data.
Labels quoted are AI-assisted (written by the session that edits the parser, so not independent) and are not human ground truth.

### 12.1 The two splices: root causes and fixes (`paperlens/ingest.py`)

| Case | What entered the claim | Cause | Fix |
|---|---|---|---|
| SciFact page 1, Figure 1 | the diagram's labels ("Decision: SUPPORTS Fact-checker Corpus ...") up to the caption | the parser had no notion of a figure: text inside a drawing was read as prose and glued into one sentence that ended at the caption | `_figure_boxes`: clusters of vector drawing items and images (4+ items, 60 x 40 pt or more, not only thin horizontal rules, not a found table, under 70% of the page); lines inside such a box are kept as `meta` sentences (never a claim or evidence). Captions lie outside the box and stay captions |
| ATLAS page 21, Figure 12 | the caption of a figure that floats at the top of the second column, glued to "The excess is driven" at the end of the first column | a sentence that continues from one column to the next had a caption in between; the running text had no terminal punctuation, so the caption lines were appended to it | a caption that starts its own block in the middle of an unfinished sentence is held aside, closed as its own caption, and the sentence continues after it (`release_held`) |

Before: both were extracted as claims (one `none`, one `moderate`) with figure text inside. After: the SciFact labels are `meta`, the caption is a caption and the
ATLAS sentence reads "The excess is driven by the two channels with the highest mass resolution, ... channel." with the caption separate; neither is a claim.
No exception names a paper or a string. A first version of the caption rule also fired on a table reference wrapped onto its own line ("... as shown in" / "Table 1.")
and cost the synthetic table layout 2% recall (caught by `tests/test_layout_bench.py`); it now needs a block of its own and more than a bare label.
Tests: `tests/test_figure_text.py` (6; the first two fail when the two fixes are disabled; negatives: rules-only table, page background, header rule, text under a figure,
a wrapped "Table 1.").

Not fixed: unruled-table text glued to a nearby sentence (ResNet: "avg pool output size: 1 avg pool We evaluate our method on ..."), and any figure drawn without vector items or images.

### 12.2 Claim identity across versions (`eval/claim_map.py`)

Claim ids renumber between runs, so identity is `sha1(paper | claim text)` as in `eval.dev_pairs`; a pair is `sha1(paper | claim | passage)`.
`python -m eval.claim_map map <old> <new> <labels> <out_dir>` writes a mapping report (`eval/results/dev_v0.5.1/label_map/claim_map.csv`: old and new text, relation
`identical / partially_changed / materially_changed / removed / added`, whether the old evidence judgment is still valid, whether a fresh label is needed) and a blank sheet of
only the items that need labels. Nothing carries over except for identical text; a changed passage of an identical claim keeps the claim label but needs a new pair label;
a passage of a claim labelled "not a claim" needs none. `merge` writes a **new** labels file (refuses conflicts, rows not marked AI-assisted, and overwriting). The original
`eval/results/dev_v0.2/dev_pairs_labelled.csv` is unchanged (its sha256 equals `DEV_LABELS_LOCKED.txt`; a test checks it).

0.4.0-dev (147 claims) to 0.5.1-dev (144): 141 identical, 3 partially changed (a fragment completed to its sentence, or a clause added), 0 materially changed, 3 removed (two
labelled not-a-claim, one never labelled), 0 added. 139 claim labels and 54 pair judgments stay valid. Fresh labels were needed for 5 claims and 7 passages; all 12 were
judged (claims: `y` 4, `n` 1; two of the four `y` are the completed versions of fragments that were already `y`, two are LIGO claims that were never labelled; passages: `y` 2, `p` 4, `n` 1) and kept in `fresh_labels_ai_assisted.csv` with their reasons; the merged file is `dev_pairs_labelled_merged.csv`.

### 12.3 Comparison (`python -m eval.claim_map compare ...`, `comparison.json`)

On the 141 claims that are identical in both versions (same denominators; 97 real claims, 59 returned passages each, no unlabelled item):

| | 0.4.0-dev | 0.5.1-dev |
|---|---|---|
| coverage (real claims with a passage) | 59/97 = 0.608 | 59/97 = 0.608 |
| strict precision (y) | 22/59 = 0.373 (95% CI 0.26 to 0.50) | 22/59 = 0.373 (0.26 to 0.50) |
| lenient precision (y or p) | 48/59 = 0.814 (0.70 to 0.89) | 47/59 = 0.797 (0.68 to 0.88) |
| same top passage | 135 of 141 | |

The one lenient loss is a claim in the Attention paper whose top passage changed from a partial one to an unrelated one; there are no gains. **No improvement or loss is demonstrated**
(one passage out of 59, intervals overlap completely). Whole claim sets, each version alone: 0.5.1-dev has 144 claims, 99 real, 61 returned, strict 23/61 = 0.377, lenient 49/61 = 0.803, coverage 61/99;
0.4.0-dev's whole-set figures are not computed because one removed claim has no label (the tool refuses to guess). The whole-set numbers have different denominators from the
0.4.0-dev numbers quoted in section 10 (3 claims then unlabelled), so they are not comparable with them.

Confounders: the 12 fresh labels were written knowing the system output and by the session that edited the parser; the old labels by the session that wrote 0.2.0-dev; neither is human;
59 passages is a small denominator; the 5 fragment-to-sentence claims are new items that were previously judged on their fragments. Synthetic seed 7 and SciFact dev are identical to 0.4.0-dev.
Synthetic reading-order benchmark: unchanged by the figure fixes (macro 1.00, `L13` still 0.92 for order).

## 13. Development version 0.6.0-dev: tables without a grid (synthetic and development data only)

Branch `dev/reading-order-v0.5`, continued from `adce476`. Synthetic PDFs and the 16 development papers only; no held-out
data was opened. Labels quoted are AI-assisted and not human ground truth.

### 13.1 The failure (`paperlens/ingest.py` before the change)

Tables were found only by `page.find_tables()`, which needs drawn rules. A table set with white space only, or with a few
horizontal rules, reached the parser as ordinary lines. Seen on the development papers: a whole table as one `text`
sentence (GLUE and SQuAD tables in the BERT paper, the model and result tables of the GPT-3 paper, the BLEU table of the
Attention paper, two event-count tables of the ATLAS paper); a row running into the next paragraph ("... 78.7 81.9 80.0
83.1 tuning data, we only lose ...") or into a caption ("... 87.7 79.3 Figure 3.2: ..."). Such text could be chosen as an
evidence passage. A sentence with a (ruled) table in its middle was also cut in two.

### 13.2 What was added

`_open_tables` recognises a table from geometry: lines are cut into cells at wide gaps; cells on one baseline form a row; a
row with at least two values (or a label and one value) is a data row; data rows whose values stand above each other form a
table; the rows of column heads above and short lines between the rows belong to it. Never a cell: a line of running prose
(five or more mostly lower-case words), a numbered heading, a formula, an equation number, a contents entry, a wrapped
citation list. A row never crosses a column gutter unless both sides hold at least two values. Data rows with a row label
become `table` sentences in the format of ruled tables; column heads, group labels and rows without a label become `meta`
(never a claim, never evidence), and rows without a label raise a warning. Each row leaves a placeholder so that reading
order is computed with the table in place and the rows are emitted where the table stands. A table inside an unfinished
sentence (same column, text continuing in lower case) is emitted after that sentence; this also applies to ruled tables.

### 13.3 Synthetic benchmark (`python -m eval.layout_bench`; 8 new layouts, 29 in all)

New layouts, category `unruled_tables`: a 6 x 5 table with right-aligned numbers, a unit, an error bar and a dash, with no
grid, in a single column and in one column of a two-column page, with the page stream in natural, block, line and shuffled
order; the same with three horizontal rules; and with the cells written column by column or shuffled. New count
`table_leaks`: prose or caption sentences containing two neighbouring cells of one table row.

| Measure, mean over the 8 new layouts | parser of `adce476` (0.5.1-dev) | 0.6.0-dev |
|---|---|---|
| table-row recall (rows found as one table sentence with all their cells) | 0.00 | 1.00 |
| sentences with glued table cells (`table_leaks`, total) | 8 | 0 |
| spliced sentences (total) | 9 | 0 |
| block precision | 0.96 | 1.00 |
| paragraph reconstruction | 0.91 | 1.00 |
| block recall | 0.98 | 1.00 |
| reading order, page accuracy, claim recall, evidence rate | 1.00 | 1.00 |

Over all 29 layouts the table-row recall goes from 0.20 to 1.00. The 21 earlier layouts score exactly as recorded for
0.5.1-dev (`after_0.5.1-dev.json`), so nothing regressed there. Files: `eval/results/layout_bench/after_0.6.0-dev.json`,
`baseline_adce476_29_layouts.json`. The layouts and the parser change were written by the same session, and the table is a
template: **these scores say the geometry is handled, not that real tables are.**

### 13.4 The 16 development papers (real PDFs; automatic counts, `python -m eval.table_text_dev`)

| Count over the 16 papers | 0.5.1-dev | 0.6.0-dev |
|---|---|---|
| sentences of kind text / table / meta / caption | 8257 / 406 / 483 / 189 | 8263 / 689 / 607 / 191 |
| prose sentences with a run of four or more numbers (an upper bound on table text read as prose; citation lists also match) | 48 | 14 |
| rows newly marked as table content | | 407: 283 labelled `table` rows, 56 rows without a label (`meta`), 52 column-head rows, 16 other |
| papers with the new "rows without labels" warning | 0 | 7 |
| crashes | 0 | 0 |

Read by the assistant, not labelled: of the 80 `text` sentences that disappeared, 32 looked like prose by a word-count
test; all of them were table or figure text mixed with prose, or sentences that are now re-formed without the table text.
9 papers changed, 7 did not. Abstract detection (16/16) and heading detection (83/85) are unchanged.

What these counts cannot show: whether a row was read correctly (cells in the right order, heads attached to the right
values). Reading samples shows correct rows (BERT GLUE table, SciFact tables, ResNet error table) and wrong ones (rows
split in two, a value pair merged into one cell, heads left as prose). No row-level ground truth exists for real papers.

### 13.5 Claims and evidence on the development papers (`python -m eval.claim_map compare`, AI-assisted labels)

All 144 claims are identical in text to 0.5.1-dev, so every claim label carries over. 139 of 144 top passages are the
same. Two new passages needed labels (both judged partial, by the session that changed the parser, so not independent).

| On the 144 common claims (99 real) | 0.5.1-dev | 0.6.0-dev |
|---|---|---|
| coverage (real claims with a passage) | 61/99 = 0.616 (95% CI 0.52 to 0.71) | 59/99 = 0.596 (0.50 to 0.69) |
| strict precision (y) | 23/61 = 0.377 (0.27 to 0.50) | 22/59 = 0.373 (0.26 to 0.50) |
| lenient precision (y or p) | 49/61 = 0.803 (0.69 to 0.88) | 48/59 = 0.814 (0.70 to 0.89) |

The five changes: two claims lost their passage (old labels: one wrong, one partial; the pool of candidate passages
changed, which shifts the lexical scores); one passage went from a glued sentence labelled `y` to a single table row
labelled `p` (the row holds one of the claim's two quantities; the other is now in a separate row); one went from a
partial sentence to a partial table row; one belongs to a sentence that is not a claim. **No improvement and no loss in
evidence precision is demonstrated**: one or two passages out of about 60, intervals overlapping completely.
Synthetic claim benchmark (seed 7) and SciFact dev are identical to 0.5.1-dev.

### 13.6 Not measured, not fixed

- Row-level correctness on real papers; anything on unseen papers; any human-labelled figure.
- Two development cases that motivated the work are still glued: a ResNet architecture table whose cells are words
  ("... output size: 1 avg pool We evaluate our method ..."), and a row of ten scores in the protein-contact paper that
  follows "protein of 182" (the new single-row rule covers the synthetic version of this, not this page).
- Tables whose cells are sentences or long phrases (the CheckList paper) stay prose; only their number columns are removed.
- Column heads that PyMuPDF delivers as one line of words stay prose ("System Dev Test EM F1 ...").

## 14. Row-level benchmark on real tables of the development papers (AI-transcribed annotations; first results, no tuning)

Annotations, protocol and sheet: `eval/table_truth/` (`tables.json`, `PROTOCOL.md`, `VERIFICATION_SHEET.md`,
`ANNOTATIONS_LOCKED.txt`). Scorer: `python -m eval.table_rows_bench`. Results: `eval/results/table_rows_dev/`.

**Read first.** The annotations were transcribed by the AI assistant from images of the PDF pages and each cell string was
confirmed in the PDF text layer. They are **not human-verified**. They were locked by hash before any scoring, and the
parser was not changed in this step. The 11 tables are from development papers, were not chosen at random, and five of
them (T01, T02, T03, T05, T06) are on pages whose output was read while 0.6.0-dev was written, so the 0.6.0-dev figures
are optimistic for those. Nothing here is a result on unseen papers.

Sample: 11 tables, 71 data rows (1 marked ambiguous and left out), **70 scored rows, 330 non-empty cells, 15 header rows**.

### 14.1 Totals (strict comparison; lenient in brackets where it differs)

| Measure | Denominator | parser of `adce476` (0.5.1-dev) | 0.6.0-dev |
|---|---|---|---|
| Exact-row accuracy | 70 rows | 8 = 0.114 | 43 = 0.614 (lenient 46 = 0.657) |
| Cell accuracy | 330 cells | 33 = 0.100 | 249 = 0.755 (lenient 252 = 0.764) |
| Rows returned exactly but unusable (no row label) | 70 | 0 | 0 |
| Merged rows | 70 | 0 | 0 |
| Split rows | 70 | 0 | 1 (lenient 2) |
| Partial rows | 70 | 0 | 13 (lenient 9) |
| Missing rows | 70 | 62, of which 50 glued into prose | 13, of which 1 glued into prose |
| Header rows returned | 15 | 0 | 5 |
| Wrong column heads / heads attached | attached heads | 0 / 25 | 0 / 134 |
| Values carrying their correct column head | 255 values that have a head | 0.098 | 0.525 |

### 14.2 Per table, 0.6.0-dev, strict (rows: exact / split / partial / missing)

| Table | Kind | Rows | Exact | Split | Partial | Missing | Cells found | Header rows |
|---|---|---|---|---|---|---|---|---|
| T01 BERT Table 2 | two-level head, group labels | 10 | 10 | 0 | 0 | 0 | 50/50 | 0/2 |
| T02 BERT Table 5 | three-level head, near prose | 4 | 4 | 0 | 0 | 0 | 24/24 | 2/3 |
| T03 Attention Table 2 | empty cells, exponents | 10 | 10 | 0 | 0 | 0 | 41/41 | 1/2 |
| T04 ResNet Table 1 | architecture table of words | 7 (+1 ambiguous) | 0 | 0 | 0 | 7 | 0/39 | 0/1 |
| T05 ResNet Table 2 | small, in a text column | 2 | 2 | 0 | 0 | 0 | 6/6 | 1/1 |
| T06 GPT-3 Table 2.1 | wide, units | 8 | 8 | 0 | 0 | 0 | 64/64 | 1/1 |
| T07 ATLAS Table 2 | ± values, group labels | 6 | 1 | 1 | 4 | 0 | 13/18 | 0/2 |
| T08a SciFact Table 2 (a) | integers only | 4 | 0 | 0 | 0 | 4 | 0/20 | 0/1 |
| T08b SciFact Table 2 (b) | integers, dashes | 4 | 0 | 0 | 3 | 1 | 12/20 | 0/1 |
| T09 GW Table I | label and value, no header | 6 | 0 | 0 | 6 | 0 | 6/12 | 0/0 |
| T10 PMC4930190 Table 1 | fully ruled | 9 | 8 | 0 | 0 | 1 | 33/36 | 0/1 |

With the `adce476` parser only T10 (found by the ruled-table finder) scores: 8 exact rows of 9; every other row is missing.
Lenient comparison changes only T07 (4 exact, 2 split): three of its rows differ from the page only in the position of a
bar accent ("tt¯" for "t¯t").

### 14.3 Error patterns (read from the non-exact rows; causes checked, nothing fixed)

1. **Integer cells are deleted before table detection (T08a, T08b; 24 cells on that page).** The running-header filter
   replaces digits by `#` and removes every line whose pattern repeats on half the pages. A page number makes `#` such a
   pattern, so **every line that consists only of an integer is removed from every page**: 65 of 243 number-only lines in
   the SciFact paper, 394 of 1313 in the GPT-3 paper, 29 of 165 in the BERT paper. Run on the unfiltered lines of that
   page, `_open_tables` returns both SciFact tables with every cell. The filter predates 0.6.0-dev (it is in 0.1.0), and
   the deleted cells are in no sentence at all: this is silent loss of table values, not a misreading.
2. **A table of words is not recognised (T04, 7 rows, 39 cells).** Known limit of the numeric-column rule.
3. **One printed value becomes two cells (T09: 6 rows; T07: parts of 5 rows).** A value with a superscript and
   subscript ("36 +5/−4 M☉") or with separate uncertainty parts ("0.3± 0.1 ±0.1") is cut at the gap between its pieces, or
   its second piece is dropped.
4. **Group labels detach rows from their labels (T07).** After a group line ("2e2µ") a row loses its label and is
   returned as a number-only row.
5. **Column heads (10 of 15 header rows not returned).** Heads delivered as one line of words stay prose (T01); upper
   levels of multi-level heads are not attached. No wrongly attached head was found (0 of 134).
6. **One row of the ruled table is missing (T10)**: the row whose label contains a letter with a dot above.

### 14.4 Recommendation (one change)

Stop the running-header filter from deleting integer-only lines inside the page body: treat a number-only line as a page
number only in the top or bottom strip of the page (or when it stands alone on its baseline there). It is the largest
single loss seen (hundreds of table cells per paper, silently), it is upstream of table detection, and its effect can be
measured with this benchmark and the synthetic layouts without tuning on individual rows.

### 14.5 Not measured

Human-verified accuracy (no human has checked the transcriptions); table boundaries as boxes; anything on unseen papers;
rows of the tables that were not annotated (the remaining tables of these papers).

## 15. Development version 0.6.1-dev: page numbers and running heads no longer delete numbers in the page body

Branch `dev/reading-order-v0.5`, continued from `3109556`. Synthetic PDFs and development papers only. The row-level
table annotations (section 14) are AI-transcribed, not human-verified; they are used here as a diagnostic, their file
and locked hash are unchanged, and nothing was adjusted to individual annotated rows.

### 15.1 The fault, measured (`paperlens/ingest.py` at `3109556`)

`_running_headers` masks digits and collects the patterns that occur on half the pages; `_build` then deleted **every**
line with such a pattern, wherever it stood. Page numbers make the bare-number pattern qualify, so every integer-only
line was deleted; other short patterns qualified too (single letters of formulas, decimals, control characters).
On the 16 development papers (331 pages) the filter removed 1401 lines whose pattern has fewer than four letters: 284 in
the top or bottom 8% of the page, **1117 in the page body** (GPT-3 320, ATLAS 283, Adam 197, ResNet 186), and 420 worded
lines (running heads, journal footers).

### 15.2 The change

- A repeated pattern with at least four letters is removed wherever it stands, as before (420 lines before and after).
- A repeated pattern with fewer letters is removed only (a) in the top or bottom 8% of the page, unless two or more
  other letterless lines share its baseline (a table row at the page edge), or (b) if it is a page number by sequence:
  the lowest or highest line of the page, a bare number in the outer fifth, whose value runs with the page count on at
  least half the pages (three at least). Rule (b) was added after the first version leaked the page numbers of two
  development papers into sentences (they sit at 87% and 91% of the page height).
- The separate rule for short documents ("a number of up to three digits below y = 700 is a page number") now uses the
  same 8% strip; it used to drop bare numbers in the lowest 12 to 17% of the body.
- Bare numbers that are now kept but belong to no table: a run of number-only lines holding three or more numbers (the
  tick labels of a plot axis) is kept as `meta` and never joined into a sentence; one or two bare numbers stay in the
  text (the numerator of a fraction, a value on its own line).

Letterless lines removed on the development papers: 1401 before, **335 after** (284 in the edge strip, 51 page numbers
found by sequence in ATLAS and Adam); nothing is removed now that was kept before; worded lines unchanged.

### 15.3 Synthetic checks

`tests/test_page_numbers.py` (11 tests): integer table cells in a six-page document with page numbers at the bottom, at
the top, and outside the 8% strip; a lone integer inside a sentence; a short document; a table row inside the bottom strip;
running heads and a letterless journal footer still removed; axis ticks not glued; fraction numerators and citation
lists untouched. Two new benchmark layouts (`integer_tables`: an integer-only table in a document of four or more pages):

| Layout, measure | parser of `3109556` | 0.6.1-dev |
|---|---|---|
| `L17_integer_table_single`, `_twocol`: table-row recall | 0.00, 0.00 | 1.00, 1.00 |
| sentences with glued table cells / spliced sentences (both layouts) | 2 / 2 | 0 / 0 |
| paragraph reconstruction | 0.91 | 1.00 |

The 29 earlier layouts score exactly as recorded for 0.6.0-dev. Files: `eval/results/layout_bench/after_0.6.1-dev.json`,
`baseline_3109556_31_layouts.json`.

### 15.4 Row-level table benchmark, before and after (annotations unchanged; 70 rows, 330 cells, 15 header rows)

| Measure | Denominator | 0.6.0-dev (`3109556`) | 0.6.1-dev |
|---|---|---|---|
| Exact rows, strict | 70 | 43 = 0.614 | 51 = 0.729 |
| Exact rows, lenient | 70 | 46 = 0.657 | 54 = 0.771 |
| Cells found, strict | 330 | 249 = 0.755 | 277 = 0.839 |
| Partial rows / missing rows, strict | 70 | 13 / 13 | 10 / 8 |
| Header rows returned | 15 | 5 | 6 |
| Wrong heads / heads attached | attached | 0 / 134 | 0 / 150 |
| Values carrying their correct column head | 255 | 0.525 | 0.588 |

The whole change is in two tables: T08a (0/4 rows, 0/20 cells before; 4/4, 20/20 after) and T08b (0/4, 12/20 before; 4/4,
20/20 after). The other nine tables are unchanged row for row. Still failing: the word table (T04, 7 rows), values split
at superscript or uncertainty parts (T09, T07), one row of the ruled table (T10). This is a diagnostic on 11 development
tables with AI-made annotations; it does not establish real-world accuracy.

### 15.5 The 16 development papers

| Count | 0.6.0-dev | 0.6.1-dev |
|---|---|---|
| sentences of kind text / table / meta / caption | 8263 / 689 / 607 / 191 | 8267 / 722 / 632 / 191 |
| prose sentences with a run of four or more numbers (upper bound on table text in prose) | 14 | 12 |
| papers with a "rows without labels" warning | 7 | 9 |
| claims extracted | 144 | 144, identical in text |
| top evidence passage unchanged | | 143 of 144 |
| coverage / strict / lenient on 99 real claims (AI-assisted labels) | 59/99, 22/59, 48/59 | 59/99, 22/59, 48/59 |

One passage changed (a partial passage replaced by another partial one; one fresh AI-assisted label). Abstract 16/16 and
headings 83/85 unchanged; synthetic claim benchmark (seed 7) and SciFact dev identical. No crash.

Reading the changed sentences (8 of 16 papers changed; 58 `text` sentences replaced by 62):
- gains: restored table cells (SciFact, GPT-3: 35 and 75 new or completed rows), restored values inside sentences
  ("... the scaling factor of 1 √dk", answers such as "A: 48" in the GPT-3 appendix), restored parts of formulas (Adam);
- regressions, all small: a few restored tick labels or legend numbers of figures appear as short junk sentences or are
  attached to figure text that was already junk ("20", "[GeV] 12 m", "18-layer 34-layer 50 Table 2."); restored formula
  fragments make some already unreadable display equations longer;
- no page number is left in any sentence of the 16 papers, and no sentence lost prose.

### 15.6 Not measured, not fixed

Unseen papers; human-verified table rows; page numbers that are neither in the edge strip nor the lowest or highest line
(for example beside a footer line set lower), or that do not count with the pages (roman numerals, "A-3"); documents of
fewer than four pages rely on the strip rule alone.

## 16. Version 1.1.0: Numbers check on 35 real papers (AI-reviewed, not human-verified)

Full record: `eval/results/consistency_v1/README.md`. The rules were written on the 16 development papers, frozen, and
run once on the 19 held-out PDFs (raw output kept). That run showed three kinds of false alarm (a category column added
into a row total, a table with subtotal rows summed twice, F1 averaged over runs), and the rules were fixed, so **the
held-out folders are now development data for this feature**. After the fixes: 101 checks in 8 of 35 papers; 86 check
out, 11 are "not reproduced" (all with a legitimate explanation), 4 "do not add up". All 4 were confirmed against the PDF
text by the AI session that wrote the code: a wrong denominator in a PLOS Medicine trial ("22/307 (8.5%)", where the
text uses 258), a regional subtotal 93 cases off its states in a PLoS NTD table, and two trivial rounding slips (14.6497%
printed as 14.7%). Four flags are too few for a precision figure, recall is unknown, and coverage is the main limitation.

## 17. Version 1.1.0: re-evaluation after the glossary change (development data only)

Full record: `eval/results/dev_v1.1/README.md`. Claim-to-evidence ranking now expands abbreviations the paper defines;
the parser is unchanged. Synthetic seed 7 and SciFact dev are identical to 0.6.1-dev. On the 16 development papers the
144 claims are identical and 131 top passages unchanged; coverage of the 99 real claims went from 59 to 63, strict
precision from 22/59 = 0.373 to 24/63 = 0.381, lenient precision from 48/59 = 0.814 to 50/63 = 0.794. The 8 new passages
carry AI-assisted labels by the session that made the change (1 y, 4 p, 3 n). Intervals overlap; no improvement or loss
is demonstrated.
