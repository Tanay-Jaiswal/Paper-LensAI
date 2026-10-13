# Architecture

```
PDF ──ingest──▶ Document(sentences: page, section, kind) ──┬─▶ summarize   (facets, page-cited, extractive)
                                                           ├─▶ claims      (extract headline claims)
                                                           │      └─▶ link_evidence (BM25 + numeric agreement) ─▶ Research Evidence Ledger
                                                           ├─▶ reproducibility (weighted rubric, quoted evidence)
                                                           └─▶ gaps        (rules over claims + rubric + results text)
Analysis(A), Analysis(B) ──compare──▶ aligned claims, shared datasets/metrics, rubric diff, verdict
```

## Components

**ingest.py** (PyMuPDF). Lines are read with font size/boldness; headings are recognised by a vocabulary of canonical
paper sections plus typography. Tables are detected with `page.find_tables()` (ruled) or from cell geometry (`_open_tables`, tables without a grid) and turned into `Table row: Dataset: X; Method: Y; F1: 73.6`
sentences, removed from running prose so cells never pollute sentences. Running headers/footers (text repeated on ≥50% of pages),
page numbers and end-of-line hyphenation are cleaned. Every sentence keeps `page`, `section`, `kind` (text/table/caption).
Warnings are attached when text is scarce (scanned PDF) or no results section is found.

**claims.py**. *Extraction*: only sentences in abstract / introduction / conclusion / discussion are candidates (sentences inside
results/experiments are evidence, not claims to audit). Score = section prior + assertive-verb cues + quantitative result + comparison
+ superlative, minus background-literature and limitation cues; near-duplicates (Jaccard > 0.6) are merged. Types: contribution, result,
comparison, generalization, assertion; hedging is recorded.
*Linking*: candidates are body sentences in results/experiments/discussion/method/appendix (never the claim itself, never
abstract/intro/conclusion). `score = 0.55·BM25 + 0.35·numeric agreement + 0.10·section prior + 0.10·term Jaccard`, damped ×0.75 if the claim
has numbers but the passage shares none. Version strings, citation markers, table/figure numbers and dataset names like `Yelp-5` are stripped
before number matching. Support: **strong** = claim numbers appear in a results passage and score ≥ 0.45; **moderate** = numbers match
(or non-numeric claim with score ≥ 0.45); **weak** = some lexical overlap only; **none** otherwise. A claim citing figures that no passage
reproduces can never be rated better than *weak*.

**reproducibility.py**. 15 items × (weight, *full* regexes, *partial* regexes). credit 1 / 0.5 / 0; score = 100·Σ w·credit / Σ w. Statements in
Related Work are ignored. Each item returns up to 3 quotes with page numbers and remediation advice.

**gaps.py**. Rules, each emitting kind, severity, message, page, claim id and quote: `unsupported_claim`, `number_not_in_results`,
`superlative_without_baselines`, `superlative_unsupported`, `significance_without_test`, `improvement_without_variance`,
`generalization_narrow_evidence`, `no_code`, `no_hyperparameters`, `no_limitations`, `no_splits`, `comparison_without_baselines`.

**summarize.py**. Per facet (problem/approach/results/limitations) choose sentences by section prior + cue regex + TextRank centrality
(TF-IDF cosine graph), skipping near-duplicates. Output is verbatim text with page, so the summary cannot hallucinate.

**compare.py**. Greedy one-to-one claim alignment by TF-IDF cosine (≥0.35); flags aligned claims whose numbers differ; dataset/metric
overlap; rubric differences; a plain-language verdict that never declares which *method* is better.

**api.py / web/**. FastAPI endpoints: `POST /api/analyze`, `GET /api/analyses[/{id}]`, `GET /api/analyses/{id}/page/{n}.png?highlight=ids`,
`GET /api/analyses/{id}/report.{md,json,html}`, `POST /api/compare`, `POST /api/demo`. Uploads are checked (PDF magic bytes, 25 MB cap),
stored content-addressed, ids validated by regex. The UI uses `textContent`/escaping for all paper text.

## Why not an LLM?

Constraints were *free, offline, deterministic, testable*. Every output here can be traced to a rule and a quote, which suits an
auditing tool. An LLM verifier (NLI or Claude via API) can be added behind `claims.link_evidence` to upgrade "lexical support" to
"entailment"; see `docs/KNOWN_LIMITATIONS.md` for the planned extension point.
