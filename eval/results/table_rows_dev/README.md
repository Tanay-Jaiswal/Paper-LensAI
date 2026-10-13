# Row-level table benchmark: results (development papers)

`rows_0.6.0-dev.json` and `rows_baseline_adce476.json` are the output of `python -m eval.table_rows_bench score <file>`
for the working tree at commit `4d15ba8` and for the parser of commit `adce476` (exported with `git archive` into a
temporary folder and selected with `PAPERLENS_SRC`). Each file holds strict and lenient totals, per-table summaries and
the outcome of every annotated row with the parser row it was matched to.

The annotations (`eval/table_truth/tables.json`) are AI-transcribed and **not human-verified**; see
`eval/table_truth/PROTOCOL.md` and docs/EVALUATION.md section 14 before quoting any number. These are first results:
the parser was not changed after the annotations were made.
