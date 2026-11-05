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

**Checking a paper's own numbers.** statcheck (Nuijten & Epskamp) recomputes p-values from APA-formatted test statistics;
GRIM (Brown & Heathers, 2016) and its relatives (GRIMMER, SPRITE) test whether reported means are possible for integer
data and a given n. The Black Spatula project and YesNoError (2024-25) prompt large language models to look for errors in
papers; by their own reports these runs cost cents to dollars per paper and a share of flagged errors are false, so
each flag needs expert review. PaperLens's Numbers check reuses the statcheck idea for p-values and adds plain-arithmetic
checks that those tools do not cover in one place (percentages of counts, stated differences and fold changes, table row
and column totals with subtotals, row averages, F1 from P and R, estimates inside confidence intervals). Its difference
from the LLM projects is that every check is deterministic, offline and free, shows its formula, and lists what passed as
well as what failed. These descriptions come from a web search on 2026-10-21 (secondary sources for Black Spatula and
YesNoError); verify before citing.
