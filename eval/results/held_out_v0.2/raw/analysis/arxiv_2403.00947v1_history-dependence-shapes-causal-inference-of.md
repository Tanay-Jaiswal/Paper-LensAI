# PaperLens report: History-dependence shapes causal inference of brain-behaviour relationships

*24 pages · 2 claims · reproducibility 76.3/100 (high)*

## Summary

- Simple model systems are then simulated to show how different assumptions about history-dependence can lead to spurious correlations and statistical properties of data distributions that are typically unaccounted for. *(p.1)*
- We then consider this problem from an interventionist perspective, showing that interventions can only be guaranteed to remedy the spurious correlation problem when the latent dynamics between the intervention and measured processes are known a priori, and the effect of the intervention is invariant at the chosen level of analysis. *(p.1)*

**Problem**
- We then consider this problem from an interventionist perspective, showing that interventions can only be guaranteed to remedy the spurious correlation problem when the latent dynamics between the intervention and measured processes are known a priori, and the effect of the intervention is invariant at the chosen level of analysis. *(p.1)*
- When deconstructing the history-dependence of data that is traditionally aligned to a common event in a repeated task and treated as an ensemble, one is essentially asking to what degree observed variability can be explained by considering a given process not as a collection of independent events, but as different elements of unique sequences. *(p.2)*

**Approach**
- In doing so, we propose a fundamental limitation on the ability to falsify the distinction between inherent randomness and variability arising from history dependence. *(p.3)*

**Results**
- We use this approach to deducing causal relationships to ask if, and under what conditions, knowledge about the latent dynamics between an experimentally controlled intervention and a measured process can reduce the impact of spurious correlations in autocorrelated data. *(p.13)*
- Additionally, as can be seen in Fig 4C, when the experiment length is increased to 1000 trials, the number of significant mediation results increases, as was the case when correlating two independent random walks. *(p.13)*
- From this analysis, it can be seen that the inclusion of an experimentally controlled variable can reduce the problem of spurious correlations, but only if this variable (or any variables between the intervention and the causal effect on the measured variables) influences the measured processes through a path in the system that is itself not autocorrelated. *(p.13)*

**Limitations**
- Perhaps unsurprisingly, the problem of spurious regression was first analyzed in the context of econometrics (Granger and Newbold, 1974), where trends are not isolated and repeated in a laboratory, but analyzed and forecast as the system, which we concede cannot be controlled experimentally, evolves. *(p.16)*

## Research Evidence Ledger

| ID | Claim | Page | Type | Support | Best evidence |
|---|---|---|---|---|---|
| C1 | Here we argue that undecidability about the ground-truth of history-dependence is a general computational property of systems that exchange information with its environment, and show that the resulting uncertainty has a direct impact on causal inference. | 1 | assertion | 🟠 weak | p.16: In this paper, we have argued for the computational undecidability of ground-truth history… |
| C2 | We then consider this problem from an interventionist perspective, showing that interventions can only be guaranteed to remedy the spurious correlation problem when the latent dynamics between the intervention and measured processes are known a priori, and the effect of the intervention is invariant at the chosen level of analysis. | 1 | assertion | 🔴 none | No supporting evidence found |

## Reproducibility: 76.3/100

_100 * sum(weight * credit) / sum(weight); credit: present=1, partial=0.5, missing=0; not_applicable items are left out of both sums_

| Item | Status | Weight | Evidence |
|---|---|---|---|
| Code available | present | 3.0 | p.21: Code to run the simulations is available at https://github.com/BJCaie/Ergodicity… |
| Datasets named and accessible | present | 2.0 | p.21: Code to run the simulations is available at https://github.com/BJCaie/Ergodicity… |
| Train/validation/test splits specified | not_applicable | 2.0 | Not scored: no model training was detected in this paper. |
| Preprocessing described | missing | 1.0 | Describe cleaning, tokenisation and augmentation steps. |
| Hyperparameters reported | not_applicable | 2.0 | Not scored: no model training was detected in this paper. |
| Seeds / multiple runs | present | 2.0 | p.7: Theoretical Distribution Physical Process Sampled Process Position Time A 100 tr… |
| Variance / uncertainty reported | present | 2.0 | p.2: In neuroscience, it is common to collect many trials of a similar behaviour, upo… |
| Statistical significance test | present | 1.5 | p.12: Significance testing for mediation analyses can then be performed in several way… |
| Baselines described | present | 2.0 | p.13: To this end, we simulate N and B independently for 1000 experiments, and compute… |
| Ablation / component analysis | missing | 1.0 | Show which components drive the gains. |
| Evaluation metrics defined | partial | 1.0 | p.5: What are the consequences of this fundamental limitation in the accuracy of syst… |
| Compute / hardware reported | partial | 1.0 | p.13: To this end, we simulate N and B independently for 1000 experiments, and compute… |
| Software / library versions | missing | 1.0 | Pin library versions or provide an environment file. |
| Licence / ethics statement | missing | 0.5 | State data/model licences and ethical considerations. |
| Limitations discussed | present | 1.0 | p.3: In doing so, we propose a fundamental limitation on the ability to falsify the d… |

_Measures what the paper reports (checklist coverage), not whether results actually reproduce._

## Evidence gaps

- **[MEDIUM] unsupported_claim** (p.1): No strong supporting passage found in the paper body for this claim (only weak lexical overlap). — "Here we argue that undecidability about the ground-truth of history-dependence is a general computational property of systems that exchange information with its environment, and show that the resulting uncertainty has..."
- **[MEDIUM] unsupported_claim** (p.1): No strong supporting passage found in the paper body for this claim. — "We then consider this problem from an interventionist perspective, showing that interventions can only be guaranteed to remedy the spurious correlation problem when the latent dynamics between the intervention and mea..."
