# Row-level table transcriptions: protocol (development papers only)

**Status of the annotations.** `tables.json` was transcribed on 2026-10-13 by an AI assistant from rendered images of the
PDF pages. It is **not human-verified** and must not be described as human ground truth. `VERIFICATION_SHEET.md` lists
every row so that a person can check it against the PDF; a table counts as human-verified only after that, and only then
may `human_verified` be set for it. The file was locked by hash (`ANNOTATIONS_LOCKED.txt`) before the parser was scored.

**What the transcription was made from.** The page image (to see rows, columns, spans and groups), then the PDF's own
text layer (`page.get_text("words")` of the table region) to confirm every cell string. Nothing was taken from PaperLens
output. `python -m eval.table_rows_bench check` repeats the text-layer check: every token of every cell must occur in
the text layer of the table's region.

**Scope.** 11 tables on 8 pages of 8 of the 16 development papers in `data/Papers/` (71 data rows, 333 non-empty cells).
They were chosen from caption listings read from the PDFs, to cover: numeric tables, a table of words (an architecture
table), wide tables, one-, two- and three-level column heads, group labels, empty cells, a table with no header, tables
inside a text column, a fully ruled journal table, and two sub-tables under one caption. The choice is not random, and
five of the tables (T01, T02, T03, T05, T06) are on pages whose parser output was read while 0.6.0-dev was being
written. Never add held-out papers here.

## Rules

1. **Unit.** One entry per table (or per sub-table that has its own grid): paper file, page (1-based), caption label,
   and two anchor strings from which the bounding box of the table region is computed in PDF points. The caption and
   table notes are not part of the table.
2. **Header rows** are listed top to bottom, each as its cells from left to right. A head that spans several columns is
   one cell with `span`. An empty corner cell is `""`.
3. **Data rows** are listed top to bottom, each as its cells from left to right, the row label first.
4. **Cell text** is written in the form the PDF's text layer has it, because no text parser can do better: a
   superscript or subscript appears flattened (`1.0 · 1020` for 1.0 · 10^20, `BERTBASE`), and a glyph the font maps
   wrongly appears as mapped (`36þ5 −4M⊙` for 36 +5/−4 M☉). Whenever this differs from what a reader sees, the printed
   reading is given in `printed`. Bold, italics and underlining are not recorded.
5. **Merged cells.** A label that spans several rows (a group label such as "Published") is recorded as `group` on each
   row it covers and is not a cell. A value that spans several columns is one cell with `span`, placed in its first column.
6. **Missing cells.** An empty cell is `""` in its position. A printed dash is recorded as the dash.
7. **Symbols and footnote marks** are kept in the cell as printed (`80 ± 7*`). Comparison is done twice: strict
   (NFKC, lower case, white space removed, dash variants unified) and lenient (also ignoring `* † ‡` and free-standing
   accent marks).
8. **Multi-line cells** are joined with one space into one cell; a row whose label wraps is one row. A cell made of
   several stacked lines with a multiplier (the building blocks of the architecture table) is one cell, lines top to
   bottom, the multiplier last.
9. **Ambiguous rows.** A row whose reading as a row is a matter of judgement carries `ambiguous` with the reason. It is
   scored but left out of every denominator and listed separately. One row is marked so (T04, the "3×3 max pool" line).
10. **What is not annotated:** cell boxes, alignment, the caption, notes under the table, and whether a value is bold.

## Measures

Defined in the docstring of `eval/table_rows_bench.py` with their denominators: exact-row accuracy, cell accuracy, the
outcome of every row (exact, exact but unusable, merged, split, partial, missing, glued into prose), header-row recall,
and errors and coverage of the column heads the parser attaches to values.

## Limits

- The annotations are AI-made. Reading errors in structure (a value put in the wrong column, a span missed) would not
  be caught by the text-layer check, which only confirms that the strings exist.
- 11 tables and 70 scored rows are a small sample; one table moves the total by several points.
- The tables come from development papers. Scores on them say nothing about unseen papers, and the parser must not be
  tuned on individual rows of this file.
- Cell text follows the text layer, so the loss of superscripts and mis-mapped glyphs is recorded but not scored.
