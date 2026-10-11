# Limitations and extension points

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
