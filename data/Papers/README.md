# Real-paper test set

16 genuine research-paper PDFs (331 pages, 30.2 MB) retrieved on 2026-10-11 for testing PDF parsing and evidence
traceability. `MANIFEST.csv` has one row per file: title, source, identifier, DOI, licence, URLs, retrieval time (UTC),
page count, size and SHA-256.

## How each field was verified

- **Title, DOI, identifier**: read from the source's own metadata service at download time, not typed by hand
  (arXiv OAI-PMH and Atom API, ACL Anthology `.bib`, Crossref, Europe PMC REST API).
- **Licence**: arXiv from the OAI-PMH `<license>` field; PLOS from the Crossref licence field; `pmc_` files from the
  Europe PMC licence field; ACL Anthology from its copyright FAQ (pre-2016 material CC BY-NC-SA 3.0, 2016 onward CC BY 4.0).
- **File**: starts with `%PDF-`, opens in PyMuPDF, and the metadata title's words were searched for on pages 1 and 2
  (`title_words_found_on_p1_2`). One file scores 5/6 (`acl_2020.emnlp-main.609`) because of how the title is spaced in
  the text layer; the title was confirmed by reading the first page.
- **Duplicates**: SHA-256 of every file is unique. Papers that exist on both arXiv and another source were taken once.

## Usage terms

Five arXiv files carry arXiv's non-exclusive distribution licence, which lets arXiv distribute them but does not give
others the right to redistribute. They are here for local testing only; do not commit or re-host them. The other 11
files are Creative Commons (CC BY, or CC BY-NC-SA 3.0 for the 2002 BLEU paper). `.gitignore` excludes all PDFs in this
folder.

## Spread

| Group | Files | Why included |
|---|---|---|
| ML/NLP conference papers (arXiv, ACL) | 8 | single- and two-column layouts, dense result tables, one 75-page paper, one 2002 paper |
| Physics (arXiv) | 2 | journal two-column layout, very long author lists, heavy maths |
| Biomedicine and ecology (PLOS journals, all in PubMed Central) | 4 | structured abstracts, trial, meta-analysis, satellite study, computational biology |
| Meta-science (PLOS) | 2 | one essay with no experiments, one text-mining study |

## Downloads that failed

- `europepmc.org/articles/<PMCID>?pdf=render` returned HTTP 403 for all four PMC IDs tried. The response is a
  Cloudflare "Just a moment..." bot check, which was not bypassed.
- Three of those papers were then tried at the publisher (BMC Cancer `10.1186/s12885-018-5232-6`, Globalization and
  Health `10.1186/s12992-020-00589-w`, Nature Communications `10.1038/s41467-018-05760-x`). The Springer Nature PDF URLs
  returned an HTML page instead of a PDF to a script, so these three papers are **not** in the set.
- `elifesciences.org/articles/67995.pdf` also returned HTML and was dropped.
- The fourth PMC paper (PMC4963098) and three replacements were downloaded from `journals.plos.org`, which serves the
  PDF directly. So the `pmc_` files are PubMed Central open-access articles fetched from the publisher.
