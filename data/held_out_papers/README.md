# Held-out paper set

8 genuine open-access research papers (200 pages, 25.2 MB) retrieved on 2026-10-11, **after** the PaperLens code was frozen
(`eval/results/held_out/FREEZE.json`). None is in the development set `data/Papers/` (checked by identifier, DOI, title and
SHA-256). They exist to test PaperLens on papers it was never tuned on. **Do not use them to develop or tune anything.**

`MANIFEST.csv` has one row per file: title, source, identifier, DOI, licence, URLs, retrieval time (UTC), page count, size,
SHA-256 and the selection rule that picked it. All 8 are CC BY, so they may be redistributed with attribution; `.gitignore`
still excludes the PDFs to keep the repository small.

## How the papers were chosen

Selection rules were fixed in a script before anything was downloaded, and each rule takes the **first** paper that meets
it, so the choice could not depend on how PaperLens handles a paper. PaperLens was not run on any candidate before the
frozen run.

| Rule | Source | Rule text | Result |
|---|---|---|---|
| A | arXiv | For each of `cs.LG`, `astro-ph.GA`, `stat.AP`: first paper submitted from 2023-03-01 whose primary category is that one and whose arXiv licence is CC BY | 2 papers; the `stat.AP` pick could not be downloaded |
| B | ACL Anthology | Paper number 100 of the ACL 2023 long papers and number 200 of EMNLP 2022 main | 2 papers |
| C | PLOS via Europe PMC | For each of PLOS Genetics, PLOS Neglected Tropical Diseases, PLOS Computational Biology: first CC BY research article of 2021 by publication date | 3 papers |
| D | Crossref | First CC BY article published in June 2021 in Atmospheric Chemistry and Physics (Copernicus) and in PeerJ | 1 paper; the PeerJ pick could not be downloaded |

Metadata (title, DOI, licence) was read from the sources' own services (arXiv OAI-PMH, ACL Anthology `.bib`, Europe PMC,
Crossref), not typed by hand. Each file starts with `%PDF-`, opens in PyMuPDF, and every word of its metadata title was
found on pages 1 and 2.

## Downloads that failed

- arXiv:2303.00288v2 (the `stat.AP` pick): `https://arxiv.org/pdf/2303.00288v2` returned HTTP 404. No replacement was chosen.
- PeerJ `10.7717/peerj.11551`: `https://peerj.com/articles/11551.pdf` returned HTTP 403. Not bypassed; no replacement chosen.
- The arXiv listing request for `astro-ph.GA` timed out once and was repeated with the same rule.

Ten candidates were selected and eight were obtained. The two failures were not replaced, so that the set stays exactly
what the rules produced.

## Limits of this set

Eight papers from four sources. Seven of the eight come from sources whose layouts are also in the development set (arXiv,
ACL, PLOS); only the Copernicus paper is a new publisher layout. Scanned PDFs, non-English papers and most publishers are not represented.
