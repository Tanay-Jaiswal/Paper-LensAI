# Known limitations and extension points

- **Lexical, not semantic.** Support ratings rely on shared words and numbers. A paraphrased result with different numbers will be rated weak;
  a passage that shares numbers but contradicts the claim will be rated strong. Mitigation: always shows the quote and page for human review.
- **Claim detection is cue-based.** Claims without assertive cue words or numbers can be missed; background sentences with cue words can be
  included. On 16 real papers some abstracts yield only 2 claims (`docs/EVALUATION.md` section 3). Precision on real papers is
  unmeasured until the audit sheet is labelled.
- **PDF layout.** Two-column papers rely on PyMuPDF block order, which is correct for most LaTeX output but not guaranteed. No OCR for scanned PDFs
  (a warning is shown). Equations and figures are not read; evidence that lives only in a figure is invisible.
- **Figure and plot text.** Axis labels, legends and tables that PyMuPDF does not detect as tables are read as prose. On the real
  papers this produced one junk claim and several junk evidence passages, some rated `strong`.
- **Support ratings on real papers are unverified.** After the parser fixes, 108 of 145 claims from 16 real PDFs get a rating
  (37 `none`, down from 88 of 123), but no person has checked that the linked passages actually support the claims. The fixes were
  tuned on those same 16 papers, so performance on other papers is unknown.
- **Characters the PDF does not map.** If a font has no text mapping for a glyph, PaperLens cannot recover it. A missing character
  between digits (usually the decimal point) is shown as `�`, excluded from numeric matching and reported as a warning; other
  mis-mapped glyphs (`þ` for `+` in one paper) pass through unchanged.
- **Line-end hyphenation** is repaired by a simple rule that wrongly joins real hyphenated compounds broken at a line end.
- **Tables of contents and pull quotes** can be read as section headings.
- **English only.** Patterns and stopwords are English.
- **Rubric = reporting, not reproducibility.** A paper can tick every box and still fail to reproduce; a good paper may legitimately omit items.
  Hyperparameters and data splits are marked `not_applicable` (and left out of the score) when a full-length paper shows almost no
  model-training vocabulary. This is a vocabulary test checked on 16 papers only; the other items are still scored for every paper,
  including ones (ablation, seeds) that fit non-ML work poorly.
- **Gap rules are candidates for a reviewer**, not accusations.
- **Dataset/metric extraction** uses a gazetteer plus "X dataset" patterns and will miss unusual names.

## Extension point

`claims.rank_passages` returns scored passages; `link_evidence` turns them into a support level. A verifier (NLI model or an LLM) can re-score the
top-3 passages there and replace the lexical thresholds, keeping the same ledger schema and UI.

## Added for 0.2.0-dev (evidence linking)

Measured on development data only; see `docs/EVALUATION.md` section 6.

- **Abstention costs coverage.** On the 16 development papers a passage is returned for 81 of 145 claims (142 before). By
  AI-assisted labels about one third of the removed passages were fully or partly supporting. True evidence phrased in
  other words is lost, because the relevance test is lexical.
- **More `unsupported_claim` flags.** Every abstention on a result or comparison claim raises the flag (81, up from 56 on
  the development papers). "No supporting evidence found" means the linker found none, not that the paper has none.
- **Most returned passages are still not full support.** AI-assisted strict precision on the development papers is about
  0.41; `moderate` and `weak` ratings are right in a quarter of cases or fewer.
- **One global threshold** (`MIN_LEXICAL` = 0.30) taken from a curve on short biomedical abstracts (SciFact). The curve has
  no natural cut-off, the value is a judgement, and it may suit long papers or other fields badly.
- **Quantity matching is rule-based.** The unit list is finite. A true match with no unit and no shared neighbouring word
  is missed. `91.2%` and `0.912` are not reconciled. Superscripts flattened by the PDF (`10−9` printed as `109`) are read
  correctly only in the explicit `×10` and `10^` forms. A unit is carried across "to", "and", "or", "-" and "±" between two
  numbers, which can be wrong for lists such as "12 patients and 30".
- **Suitability rules can reject real evidence.** Equation-heavy results (more than half the tokens without two adjacent
  letters) are dropped; a one-sentence result in a discussion section that repeats the claim without a new number is
  treated as a restatement; a caption without the claimed number needs high word overlap to be kept.
- **Abstract, introduction and conclusion sentences are returned only when they add a figure the claim lacks.** A valid
  qualitative statement there is still not returned, and "adds a figure" is a crude test: on the development papers it
  let through two passages, neither of them full support.
- **Unreadable PDFs are detected by character count only** (fewer than 40 characters per page). A scan with a text layer
  of garbage, or a paper where only some pages are images, is not detected.
- **No unseen-data result exists for this version**, and no human-labelled result exists for any version.
