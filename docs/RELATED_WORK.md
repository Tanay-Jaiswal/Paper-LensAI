# Related work and datasets considered

Sources were checked by web search on 2026-10-11 (title/venue confirmed; contents summarised from my knowledge of the papers, so verify details before citing).

**Scientific claim verification.** Wadden et al., *Fact or Fiction: Verifying Scientific Claims* (EMNLP 2020) introduces SciFact: expert-written claims labelled
SUPPORT/CONTRADICT/NOT-ENOUGH-INFO with sentence-level rationales in abstracts. PaperLens uses it as the real-data check for evidence ranking and
evidence-presence detection (see EVALUATION.md). Difference: SciFact verifies *external* claims against *other* papers' abstracts; PaperLens audits a paper's *own*
claims against *its own* body, tables and pages.

**Reproducibility reporting.** Pineau et al., *Improving Reproducibility in Machine Learning Research (NeurIPS 2019 Reproducibility Program)*, JMLR 22 (2021), is the
source of the ML Reproducibility Checklist that the rubric adapts. Dodge et al., *Show Your Work: Improved Reporting of Experimental Results* (EMNLP 2019) motivates the
variance/seeds/compute items. Gundersen & Kjensmo, *State of the Art: Reproducibility in Artificial Intelligence* (AAAI 2018) motivates scoring documented
method/data/experiment variables.

**Question answering over papers.** Qasper (Dasigi et al., NAACL 2021) pairs NLP papers with information-seeking questions and evidence spans; it is a candidate for a future
full-text evaluation of passage linking (not run; I did not verify its current download location).

**Summarisation.** Extractive TextRank-style ranking (Mihalcea & Tarau, 2004) is used deliberately: verbatim sentences cannot hallucinate. Abstractive scientific summarisation
datasets (e.g. arXiv/PubMed, SciTLDR) were considered but need model training/inference outside the free-and-offline constraint.

**Datasets reachable in this build environment:** none of the above could be downloaded from the cloud container (hosts blocked by policy), which is why SciFact and the audit
are provided as scripts to run on a machine with internet.
