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

## Added for 0.3.0-dev (compound claims)

Measured on development data only; see `docs/EVALUATION.md` section 9.

- **Coverage counts figures, not meaning.** "3 of 3 claimed figures matched" says the numbers reappear with a compatible
  unit or neighbouring word. It does not say the passages support the claim, and no one has labelled passage sets.
- **Only figures are tracked.** A compound claim without numbers ("state of the art on both A and B") gets no coverage
  line; 16 of the 24 partial top passages on the development papers belong to such claims.
- **Figures below 10 without a decimal are ignored** in coverage, so "eleven tasks" or "6 targets" is never reported missing.
- **The rating ignores coverage.** A claim can be `strong` with one of four figures matched; read the coverage line.
- **Most claimed figures are still unmatched:** 59 of 143 on the development papers after the change.

## Added for 0.4.0-dev (abstract and section detection)

Measured on development data only; `docs/EVALUATION.md` section 10.

- **Headings are heuristic.** Typography decides: a heading in body-size regular type with no number is missed; a bold
  lead-in line of one or two words can be taken as a heading. Run-in headings ("Methods. We ...") are not detected.
- **No abstract is better than a wrong one.** If page 1 has no 'Abstract' heading and no prose paragraph, nothing is
  labelled abstract and a warning says so. A prose paragraph that is not the abstract (a dedication, a significance
  statement) can still be chosen when there is no heading; the warning says it was a guess.
- **Contents pages** are skipped by a rule (dot leaders, or a "Contents" title with many page numbers); an unusual
  contents layout would still be read as headings.
- **Custom heading names** map to a standard section only through one of a few words ("evaluation", "results",
  "conclusion", "discussion", ...); other names stay `other`, which is searched for evidence at a low prior.
- Appendix detection needs the letter sequence A, B, C after a conclusion, references or acknowledgments; appendices
  labelled otherwise stay `other`.

## Added for 0.5.0-dev (reading order)

Synthetic layouts and development papers only; `docs/EVALUATION.md` section 11.

- **Columns are found from geometry**, not understood. A gutter needs 3+ prose lines on each side; a column that ends in one
  or two lines is not separated, and the PDF's own order is kept (the synthetic `L13` layout gets reading order 0.92 for this reason). It is not flagged.
- **Rows before columns when in doubt.** A white band across both columns (a figure, a boxed note, a grid) makes the page
  ambiguous: rows are read first and a `Layout warning` is attached. A two-column page whose columns happen to share such a band
  is read as rows and would be wrong if the text really flows down the columns.
- **Tables and figure text.** Ruled tables are found by PyMuPDF; unruled tables and text inside figures are read as lines
  and can be glued to the sentence next to them (two such claims were seen on development papers).
- **Sentences over page breaks** are joined only when the next page starts with a lower-case word or the text ends in a comma or semicolon;
  a sentence continued after a table, a heading or a figure at the top of the next page stays split.
- A synthetic score of 1.00 is not evidence for real papers: the layouts and the parser were written by the same session.

## Added for 0.5.1-dev (figure text, label carry-over)

- **Figure detection needs vector items or images.** A figure drawn as one big image is found, but a figure made of text only, or a cluster of fewer than 4 items, is not; its labels stay prose.
  Rules-only tables are deliberately not figures. Text of unruled tables can still be glued to the nearest sentence (ResNet development paper).
- **A caption inside an unfinished sentence** is separated only when it starts its own block and has more than a bare label.
- **Labels are AI-assisted.** `eval/claim_map.py` carries a label only across identical claim text; every other claim needs a fresh label, which so far came from the session that edited the parser.

## Added for 0.6.0-dev (tables without a grid)

- **Only tables with numeric columns are recognised.** A table needs rows with at least two values (or a label and one
  value) whose values line up. A table of words or phrases (an architecture table, a table of example sentences) is still
  read as prose and can still be glued to the text next to it.
- **Rows can be read wrongly.** Two values closer together than about 0.7 of the font size become one cell; a row label
  of seven or more words, or five mostly lower-case words, is taken for prose and left out; a value that stands alone in
  its column at the end of a row is left out. Cells are never re-ordered or guessed, but nothing checks them either.
- **Column heads are attached only when unambiguous** (one head over one cell). With two-level heads only the lower level
  is attached; heads delivered as a single line of words stay in the text as a short junk sentence.
- **Rows without a row label are not evidence.** They are kept as `meta` with a warning. This loses real evidence when
  the label sits in a merged cell or on another line.
- **Formulas.** A row with a mathematical operator is not table data, so equation arrays stay prose, as before.
- **A single row of values** is recognised only as "at most three label words, then four or more numbers and nothing
  else". Comma-separated number lists are deliberately excluded (wrapped citation lists).
- **A table inside a sentence** is moved behind the sentence only when the text before and after it is in the same column
  and continues in lower case; otherwise the sentence is still cut at the table.
- **More table rows change the evidence ranking.** Passages are ranked against the pool of candidates; on the development
  papers two claims lost their passage this way. No effect on evidence precision could be shown in either direction.
- **Synthetic scores are not real-paper accuracy.** The eight new layouts use one template table; row-level correctness
  on real papers has not been measured, and nothing was measured on unseen papers.

## Added with the row-level table benchmark (0.6.0-dev, no parser change)

- **Integer-only lines are deleted as page numbers on every page** (running-header filter, present since 0.1.0). Table
  cells that are bare integers therefore never reach the table detector or any sentence. Measured: 65 of 243 number-only
  lines in one development paper, 394 of 1313 in another. Not fixed yet (docs/EVALUATION.md 14.3).
- **Row-level accuracy on real tables is modest**: 43 of 70 annotated rows exact (0.61) on 11 development tables, with
  annotations that are AI-transcribed, not human-verified, and partly from pages used while writing the detector.
- **A value printed with superscript and subscript parts, or with separate uncertainty parts, is split into two cells.**
- **Rows under a group label can lose their row label** and are then kept only as unlabelled rows.
