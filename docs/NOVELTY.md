# What is new in PaperLens

## In one sentence

PaperLens does not only read a paper: it **redoes the paper's own arithmetic** and shows, with the formula and the page,
which of the paper's numbers do not add up.

## Five points to say aloud

1. **It checks the paper against itself, with a calculator.** When a paper prints a result next to the numbers it came
   from ("22/307 (8.5%)", a table "Total" row, an F1 beside its precision and recall, an odds ratio with its confidence
   interval), PaperLens recomputes it and says whether it matches, allowing for rounding.
2. **Every flag can be checked by hand in seconds.** Each result shows the formula ("22 / 307 × 100 = 7.17%, printed
   8.5%"), the quote and the page with the sentence highlighted. Nothing has to be trusted.
3. **It shows what passed, not only what failed,** and it separates real mismatches from results a normal convention can
   explain (a weighted average, an F1 averaged over runs), so it does not cry wolf.
4. **It found real errors in published papers.** On 35 real papers it flagged a wrong denominator in a PLOS Medicine
   trial (the text uses 258, a table footnote 307 for the same 8.5%) and a regional subtotal in a PLoS NTD table that is
   93 cases off the states listed under it. Both were confirmed against the PDF text.
5. **It runs offline, free, and gives the same answer every time.** A chatbot asked "are there errors in this paper?"
   gives a different answer each run, can invent errors, and does not show its arithmetic; PaperLens is deterministic
   and every claim it makes is a calculation.

## How it compares (honestly)

| Tool | What it checks | How |
|---|---|---|
| statcheck | p-values from APA-style test statistics (psychology) | deterministic recomputation |
| GRIM / SPRITE | whether reported means are possible for integer data | deterministic arithmetic |
| Black Spatula, YesNoError | any error an LLM can spot | LLM prompts, paid per paper, flags need expert review |
| ChatPDF, SciSpace, Elicit | summaries and Q&A, not error checking | LLM |
| **PaperLens Numbers check** | percentages of counts, stated differences, fold changes, table row/column totals with subtotals, row averages, F1, estimates inside CIs, and p-values (statcheck idea) | deterministic recomputation, every check shown with formula and page, combined with the evidence ledger and reproducibility checklist |

The p-value check is not new (statcheck does it). What is new is putting general table and text arithmetic checks into
one offline paper reader and showing every recomputation next to the page.

## What to admit if asked

Coverage is low: only 8 of the 35 papers contained arithmetic written in a form the checks recognise. 4 flags are too
few to claim an error rate, recall is unknown, and no independent person has verified the results. Details:
`eval/results/consistency_v1/README.md`.
