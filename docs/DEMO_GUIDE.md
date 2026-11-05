# Demonstration guide (about 10 minutes)

Every "expected" value below was observed on version 1.0.0 with the development PDFs in `data/Papers/` (kept locally,
not in Git; see `data/Papers/MANIFEST.csv` for source and licence). Output is deterministic, so you should see the same
numbers. If a number differs, trust the screen and tell the audience the guide is out of date.

## 0. Set-up (before the audience arrives)

```powershell
cd PaperLens-AI
.venv\Scripts\Activate.ps1
python -m pytest -q                 # expect: 240 passed
python -m paperlens serve           # leave running, open http://127.0.0.1:8000
```

Have the PDF `data\Papers\arxiv_1706.03762v7_attention-is-all-you-need.pdf` open in a PDF reader for step 4.
Optional second paper for step 7: `data\Papers\acl_N19-1423_bert-pre-training-of-deep-bidirectional.pdf`.

## 1. Launch

The header shows "version 1.0.0 - offline, deterministic, no language model". Say: no API, no cloud, nothing leaves the
computer.

## 2. Upload a paper

Drag the Attention PDF onto the drop box. After a few seconds the page shows *Attention Is All You Need*, 15 pages and
three tiles: **10 claims found** (1 strong, 1 moderate, 5 weak, 3 without evidence), **63 reporting checklist / 100**
(6 of 15 items not reported), **17 candidate evidence gaps** (5 high severity).

## 3. Claims

Open **Evidence Ledger**. Ten claims are listed as written in the abstract, introduction and conclusion, each with the
page it came from and a rating. Use the filter chips to show only "no evidence found".

## 4. Check a citation against the source

Click **C4** ("Our model achieves 28.4 BLEU on the WMT 2014 English-to-German ... by over 2 BLEU", rated **strong**).
The right panel shows Evidence 1 from **page 8**, *why* it was chosen (it shares the figures 2 and 28.4 with the claim),
and the page image with the claim and the passage highlighted. Open page 8 of the PDF in the reader and find the same
sentence next to Table 2. This is the central point: every statement can be verified in one click.

## 5. Unsupported and partly supported claims

Click **C2** ("We propose a new simple network architecture ...", **no evidence found**). The panel says no passage
passed the relevance test and lists what was examined and why it was rejected. Say: the tool abstains instead of
inventing support, and "no evidence found" means the linker found none, not that the paper has none.
Click **C5** (41.8 BLEU, **moderate**): the passage returned shares only "3.5" (training days). The panel reports
"1 of 2 claimed figures ... not found: 41.8": the BLEU figure itself is not in that passage. Use this as the example of why the
rating is a pointer for a human, not a verdict.

## 6. Reproducibility and missing methodology

Open **Reproducibility**. Read the yellow box: the score is checklist coverage, not proof of reproducibility. Show
"Not reported (6)": preprocessing, seeds, significance test, ablation, licence, limitations. Show that "Code
available" is credited with the quote of the GitHub link. Then open **Evidence gaps** and read
"claims 'significant' with no statistical test" (p.1).

## 7. Compare two papers

Upload the BERT PDF, return to the Attention paper (click it under "Analysed earlier"), open **Compare**, choose the BERT
PDF and press Compare. Expected: checklist 63 vs 87, evidence score 39.2 vs 30, high-severity gaps 5 vs 2, no shared
dataset. Say: it does not declare which method is better; it compares what each paper reports.

## 8. How this differs from a generic summariser

Everything shown is a verbatim quote with a page, or a named rule. Nothing is paraphrased, ratings can be traced to the
shared numbers, and an unreadable file is refused rather than summarised.

## 9. Honest limitations (show at least one live)

- **Unreadable input.** Upload any non-PDF: a red message explains it. A scanned PDF is accepted but flagged
  ("Very little extractable text ... OCR is not enabled"), the checklist reads "not assessed" and the only gap is
  `document_unreadable`.
- **A false checklist match.** In the Attention paper "Variance / uncertainty reported" is credited with a footnote on page 4
  about dot products ("... mean 0 and variance 1"). The checklist uses text patterns, so every credit shows its quote
  for the reader to overrule.
- **Weak claims are weak.** C1 ("The best performing models also connect the encoder and decoder through an attention
  mechanism") gets two method passages with score about 0.27; the rating is **weak**, i.e. "wording overlap only".
- Tables of words, equations and figure contents are not understood (`docs/KNOWN_LIMITATIONS.md`).

## 10. Command-line equivalent (optional)

```powershell
python -m paperlens analyze data\Papers\arxiv_1706.03762v7_attention-is-all-you-need.pdf --out report
python -m paperlens compare data\Papers\arxiv_1706.03762v7_attention-is-all-you-need.pdf data\Papers\acl_N19-1423_bert-pre-training-of-deep-bidirectional.pdf --out report
```

Expected: `claims: 10  reproducibility: 63.0/100 (moderate)  gaps: 17`, and for compare a three-to-four line verdict.

## If something goes wrong

No internet is needed at any point. If the PDFs are missing, use **Load synthetic demo papers** (two generated papers,
clearly labelled as synthetic) and skip the page-citation check against a real paper.
