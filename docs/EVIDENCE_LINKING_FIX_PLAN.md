# Evidence-linking fix plan (development version 0.2.0-dev)

Written before any code was changed. Goal: **make returned evidence more often correct, even if fewer claims get a
passage.** Evidence correctness is prioritised over coverage.

## Baseline and where the work happens

- The version evaluated on the held-out papers is preserved in Git as tag `v0.1.0-frozen-heldout` (commit `d6951bf`). Its
  `paperlens/` files match `eval/results/held_out/FREEZE.json`. Restore it with `git checkout v0.1.0-frozen-heldout`.
- All changes are made on branch `dev/evidence-linking-v0.2`. `paperlens.__version__` becomes `0.2.0-dev`.
- `python -m eval.freeze verify eval/results/held_out/FREEZE.json` will report changed files on the development branch.
  That is intended: it shows that the held-out results do not describe this version.
- Not touched: `eval/results/held_out/`, `eval/results/held_out_ai_audit/`, `eval/results/held_out_ai_audit_2/`, the
  existing result files under `eval/results/`, and the existing numbered sections of `docs/EVALUATION.md`. New results go
  to `eval/results/dev_v0.2/` and a new section of the evaluation document.
- Not opened during this work: `held_out_audit_key.csv`, `held_out_sample_info.json`, `eval/results/held_out/raw/`.
- Development data: the 16 papers in `data/Papers/`, the SciFact **train** split (already downloaded; human-labelled), and
  synthetic unit-test fixtures. The 8 held-out papers and their labels are not used.

## Why these three changes

In the AI-assisted audit of the frozen version, 31 of 37 top passages were not full support. The recorded reasons fall
into three groups: a passage was attached although nothing relevant existed; a passage was matched on a bare number that
meant something else; and the passage was a kind of text that cannot substantiate a claim (a caption that only names a
figure, a proof-step heading, a near-copy of the claim). The changes below address those groups in general terms. They
are not written against the specific held-out sentences.

## Fix 1: allow abstention

**Now.** `link_evidence` keeps the top 3 passages scoring above 0.12, where the score includes a section prior of up to
0.10. Almost every claim therefore gets a passage, including claims rated `none`.

**Change.**
- A passage is returned only if it clears a documented relevance test: `lexical >= MIN_LEXICAL`, or it has at least one
  quantity match (Fix 2) together with `lexical >= MIN_LEXICAL_WITH_QUANTITY`. `lexical` is the normalised BM25 score of the
  passage for the claim; the section prior no longer helps a passage get returned. Both constants live at the top of
  `claims.py` and are reported in the output.
- Each claim gets an `evidence_status`:
  - `found`: at least one passage cleared the test;
  - `no_supporting_evidence`: the paper body was searched and nothing cleared the test. Shown as "No supporting evidence found";
  - `no_searchable_text`: there were no eligible body passages at all (a parsing or document problem, not a finding about
    the claim). Shown as "Evidence search not possible".
- A claim without a returned passage has `support = "none"` and an empty evidence list. The ledger keeps its fields; one
  field is added.
- Report, web UI and gap messages use the status text.

**Choosing the threshold.** On SciFact train, each claim is paired with its cited abstract; a returned top passage is
correct if it is a gold rationale sentence, and any passage returned for a NOT-ENOUGH-INFO pair is wrong. Sweeping
`MIN_LEXICAL` gives a precision/coverage curve from human labels. The threshold is picked from that curve and then checked
(not re-tuned) on SciFact dev and on the 16 development papers.

**Expected behaviour.** Fewer claims with a passage; among returned passages a higher share relevant.

**Tests.** A supported claim still gets its passage; a claim with no relevant passage gets `no_supporting_evidence` and an
empty list; a document with no body text gets `no_searchable_text`; report text shows the right message.

**Risks.**
- Coverage may drop sharply; true evidence phrased in different words will be lost (the method is lexical).
- SciFact abstracts are short and well written, so a threshold chosen there may transfer badly to full papers.
- A single global threshold cannot suit every paper length.

## Fix 2: match numbers to the right quantity

**Now.** Any equal numeric literal in claim and passage counts as a shared number and can make a link `strong`.

**Change.** Add `quantities_in(text)` to `textutils.py`. Each number becomes a quantity with:
- a normalised value (`1,200` = `1200`, `3.50` = `3.5`, `1.7×10−9` = `1.7e-9`);
- a unit when one follows or precedes it (`%`, time units, physical units, `x`/`times`, metric names such as BLEU or F1);
- context: the content words within two tokens on each side.

Two quantities match only if the values are equal **and** the units are compatible **and** they share a unit or at least
one context word. A percentage does not match a bare count; `7 Myr` does not match a factor of 7. A shared number with no
shared unit or context is ignored. Years, citation markers, table and figure numbers and dataset names are excluded as before.
`rank_passages` uses matched quantities in place of shared literals; its signature is unchanged.

**Expected behaviour.** Fewer `strong`/`moderate` ratings caused by coincidental numbers; true numeric restatements still match.

**Tests.** Same number, different quantity (factor vs duration; two unrelated velocities; percentage vs score; days vs
score); same quantity in different formats (`3.50` vs `3.5`, `1,200` vs `1200`, scientific notation, `41.8 BLEU` vs
`BLEU of 41.8`, `%` vs `percent`); a bare shared integer alone is not evidence.

**Risks.**
- A true match whose surrounding words differ completely (and has no unit) will be missed.
- The unit list is finite; unknown units fall back to context words.
- Flattened superscripts (`10−9` printed as `109`) are ambiguous; handled for the explicit `×10` form only.
- Percentage vs fraction (`91.2%` vs `0.912`) is not reconciled.

## Fix 3: filter unsuitable evidence passages

**Now.** Any sentence in an eligible section can be evidence if it has 4 or more tokens.

**Change.** Each candidate gets a suitability verdict with a recorded reason. Unsuitable passages are not returned.
- **Label-only captions:** a caption is suitable only if it carries a matched quantity or states a result in a full
  sentence that clears a stricter lexical bar. "Figure 2: An overview of the framework" is rejected; "Table 4: ... 91.3 F1"
  for a claim citing 91.3 F1 is kept.
- **Headings and fragments:** fewer than 6 content words, or step/lemma/proof headers.
- **Derivations and number dumps:** passages where most tokens are symbols, single letters or numbers (proof lines,
  flattened tables, figure text). Applies in any section; appendix prose is still eligible.
- **Boilerplate:** publisher front matter (already tagged `meta`), and summary sections that restate the abstract
  (for example "Author Summary").
- **Restatements:** a passage that nearly repeats the claim, adds no number the claim lacks, and is not in a results or
  experiments section, is rejected as a restatement. A results sentence that repeats the claim's numbers is kept.

Nothing is excluded by section alone: captions, appendices and discussion text remain eligible when they pass the checks.

**Expected behaviour.** Captions, proof steps, figure text and echoes of the claim stop appearing as top evidence.

**Tests.** For each category one false match that must be rejected and one legitimate passage that must be kept.

**Risks.**
- The symbol-density rule may reject legitimate equation-heavy results in maths and physics papers.
- The restatement rule may reject a genuine one-sentence result in a discussion section.
- More filtering lowers coverage further (compounds with Fix 1).

## Evaluation after implementation (development data only)

1. All automated tests, plus new regression tests for each fix.
2. SciFact train: precision/coverage curve used to pick the threshold. SciFact dev: same measures at the chosen threshold,
   and the existing ranking metrics re-run to see whether anything changed.
3. Synthetic benchmark, seeds 7 and 99: must stay above the existing floor; any change is reported.
4. The 16 development papers: baseline vs new version on coverage (claims with a returned passage), support distribution,
   abstentions, and the automatic page checks. Output in `eval/results/dev_v0.2/`.
5. Evidence precision on the development papers needs labels, and none exist. The top passages of both versions will be
   labelled by the AI assistant under the rules of `AUDIT_INSTRUCTIONS.md`, with the version hidden during labelling. This
   is an AI-assisted estimate on papers the system was tuned on. It is not human precision and not a measure of unseen performance.

## What this plan does not do

- No new held-out download. The existing held-out results are not re-run and do not measure the new version. Because the
  three fixes were motivated by failure types seen in the held-out audit, those 8 papers can no longer serve as an unseen
  test for this version; a fresh set is required.
- Compound claims, recalibrating the support levels and section-labelling robustness (items 4 to 6 of the earlier list) are
  out of scope.

## Implementation status (2026-10-12)

The plan above is unchanged. What was done, and where it differs from the plan:

| Item | Status |
|---|---|
| Fix 1 abstention, status field, report/UI text | implemented; tested |
| Fix 2 quantity matching | implemented; tested. Added after the plan: `1e-3` and `10^-3`, the unit of a range or error bar, `89.1% F1` vs `89.1 F1` |
| Fix 3 suitability filter | implemented; tested. The symbol-density rule was corrected (it rejected results sentences dense with figures) |
| Threshold from SciFact train, checked not re-tuned on dev | **deviation found and undone**: the constant had been raised to 0.35 after a sweep on the development labels; it is 0.30 again (docs/EVALUATION.md 6.3) |
| Dev labels by a labeller with the version hidden | **deviation**: labelled by the session that wrote the fixes, from text alone; no fresh blind labeller |
| "Nothing is excluded by section alone" | abstract, introduction and conclusion were still excluded outright in the first implementation; now searched under a strict rule |
| Regression tests for each fix | 59 tests in `tests/test_evidence_linking_v02.py` |
| Synthetic, SciFact, development-paper reruns | done; results in docs/EVALUATION.md section 6 |

Outcome on development data: fewer wrong passages (35 to 11 by AI-assisted labels), lower coverage (0.979 to 0.619), and
no increase in claims shown with fully supporting evidence. The goal stated at the top, "more often correct, even if fewer
claims get a passage", is met only in that sense.
