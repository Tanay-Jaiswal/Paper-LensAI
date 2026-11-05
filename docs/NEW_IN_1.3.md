# What is new in 1.3.0, and what was checked

Eight additions. The rule-based core (claims, evidence ledger, checklist, gaps, numbers check) is unchanged: on the
frozen second CSE check set, the 80 CS checklist decisions are identical to the 1.2.0 run.

Kinds of result, as in `docs/EVALUATION.md`: **AI-checked** means Claude checked the output against the PDF text; it is
not a human label. **Human-verified** results still do not exist; item 1 is the tool to produce them.

## 1. Human labelling kit (`eval/labelling/`)

A blinded labelling sheet for classmates: `labeller.html` (offline page, saves as you go, exports a CSV),
`sheet.csv` for spreadsheet users, `INSTRUCTIONS.md`, and `score.py`, which compares people's answers with PaperLens
(majority answer, Cohen's kappa between two labellers). The ready-built sheet `eval/labelling/cse_check2/` has 100
questions on the 8 papers of the second CSE check: the same 80 CS checklist decisions behind the 69% figure, 10 claim and
passage pairs, and 10 claims PaperLens found no evidence for. PaperLens's answers are in `key.json` and never appear in
what labellers see (tested). **No label was filled in by PaperLens or by an AI.**

## 2. Online deployment (`Dockerfile`, `docker-compose.yml`, `render.yaml`, `docs/DEPLOY.md`)

Container setup and step-by-step instructions for Docker, Render and Hugging Face Spaces. Hosted mode
(`PAPERLENS_HOSTED=1`) changes the upload wording and lists only each browser's own papers; `PAPERLENS_PASSWORD` adds a
shared password. Tested: the app runs from exactly the files the image contains, the password and per-browser lists
work, the hosted page works in a browser. **Not tested: building the image (no Docker on this computer) and any real
host. Nothing was deployed.**

## 3. One-page score card (Score card tab, `/scorecard.pdf`, `/scorecard.html`, CLI writes both)

A letter grade A to E, the three most important problems and the fix for each, as a page and a one-page PDF. The grade
is computed from numbers already in the report with a fixed, printed formula (`paperlens/scorecard.py`):
`0.7 × checklist + 0.3 × evidence score − 5 per number that does not add up − 2 per high-severity gap (at most 15)`;
A ≥ 80, B ≥ 65, C ≥ 50, D ≥ 35. The weights were set on development papers only: a first version (0.6 / 0.4, 5 points
per gap) gave 9 of 16 development CS papers an E, mostly because an unsupported claim lowers both the evidence score and
the gap count. With the final weights the 16 get B 2, C 2, D 9, E 3. The grade is a summary of reporting, not of the
science, and the card says so.

## 4. Evidence on the original PDF page (Evidence Ledger)

Clicking a claim now draws labelled boxes (C for the claim, E1, E2 ... for evidence) over the page images, each passage
has "Show on page" and "open in the PDF", and the original PDF can be opened with the claim and evidence highlighted
and annotated (`/highlighted.pdf?claim=C3`). Each passage says whether it was located exactly, in part, or not at all.
Measured on 18 development papers (`python -m eval.highlight_rate`): of 124 evidence passages, 100 (81%) located
exactly, 14 (11%) in part, 10 (8%) not located; all 89 claims were located (82% exactly). This measures locating, not
whether the evidence is right. The browser pane used for testing downloads PDFs instead of showing them, so opening the
highlighted PDF at the right page was checked by reading its annotations, not by viewing it.

## 5. CS comparison view (CS comparison tab)

Shows where a CS paper's checklist score falls among (a) a built-in set of 16 development CS papers
(`paperlens/data/cs_reference.json`, rebuilt by `python -m eval.build_cs_reference`; stores scores and item statuses,
no paper text; refuses held-out and frozen check papers) or (b) the user's own CS papers. Percentile, median, a dot
strip, and for every checklist item the share of the set that reports it, with notes where this paper differs from
most. With 16 non-random papers the percentile is descriptive only; the page says so.

## 6. Citation and reference checks (References tab, report sections, revision checklist)

Numbered and author-year styles: cited but not in the list, in the list but never cited, duplicate entries, entries
without a year, plus an information-only profile of the list (how recent, preprints, DOIs). No online lookups.

Development (21 papers in `data/store`, two of them held-out, see below, and the 6 papers of `data/cse_check_papers`): false alarms found and fixed along
the way were intervals like "[256, 480]" read as citations, citations in footnotes, IEEE ranges "[11]–[13]", reference
entries the sentence parser dropped (fixed by reading the reference list straight from the PDF), and DOIs broken across
lines. After the fixes, the 19 findings on these papers were each checked against the PDF text (AI-checked): all 19 are
real (1 entry never cited, 1 duplicate entry, 17 entries without a year). 4 papers could not be checked (list or
citation style not read). **Disclosure:** two papers of the v0.2 held-out set (snakebite, peer-educator) were in the
local store and were read during this development; the held-out results and files were not changed, but these two
papers must not be used to evaluate the citation checks.

Fresh check, run once after development (`python -m eval.citation_check data/cse_check2_papers`): 7 of 8 papers checked,
0 findings. A separate script that counted bracketed citations in the full text found no uncited or missing numbered
reference in the 6 numbered-style papers either, so there were no false alarms; with nothing to find, this set says
nothing about how many real problems the checks would miss.

## 7. Thumbs up / down on every finding

On claims, evidence passages, checklist items, gaps, numbers checks, revisions and reference findings. Stored on this
computer next to the analysis (`feedback.json`), with the finding's text and the version, because ids can change
between versions. "Feedback CSV" exports all votes. Votes are opinions about usefulness, not labels.

## 8. Optional AI second opinion (`docs/AI_SECOND_OPINION.md`)

Off by default. When enabled, a reader can ask Claude whether any of the closest passages supports a claim in other
words. Shown in a separate box labelled AI-assisted; never changes the rule-based rating or any score; quotes are
PaperLens's copies of the paper's sentences. **Tested only with a fake client; not run against the real API.**

## Tests

375 tests (311 before), all passing, no network.
