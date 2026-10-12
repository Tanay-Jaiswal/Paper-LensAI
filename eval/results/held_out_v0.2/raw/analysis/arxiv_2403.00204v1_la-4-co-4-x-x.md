# PaperLens report: La4Co4X (X = Pb, Bi, Sb): a demonstration of antagonistic pairs as a route to quasi-low dimensional ternary compounds

*25 pages · 5 claims · reproducibility 13.2/100 (low)*

## Summary

- The Co is moment bearing in each La4Co4X compound studied, and we show that whereas La4Co4Pb behaves as a three dimensional antiferromagnet with T N = 220 K, La4Co4Bi and La4Co4Sb have behavior consistent with low dimensional magnetic coupling and ordering, with T N = 153 K and 143 K respectively. *(p.1)*
- As a demonstration, we present the discovery of a new family of intermetallic compounds, La4Co4X (X = Pb, Bi, Sb), that are based on the immiscible pairs Co-Pb and Co-Bi. *(p.9)*

**Problem**
- We use the term “antagonistic pairs” to refer to such pairs of elements with similarly extreme levels of immiscibility,1 of which other examples include, but are not limited to, Ba-Fe and La-Cr. *(p.1)*

**Approach**
- As proof of principle, we present the discovery, crystal growth, and basic physical properties of La4Co4X (X = Pb, Bi, Sb), a new family of intermetallic compounds based on the antagonistic pairs Co-Pb and Co-Bi. *(p.1)*
- As a demonstration, we present the discovery of a new family of intermetallic compounds, La4Co4X (X = Pb, Bi, Sb), that are based on the immiscible pairs Co-Pb and Co-Bi. *(p.9)*

**Results**
- Here, we demonstrate how strongly immiscible pairs of elements can be leveraged to synthesize ternary compounds with reduced or quasi-reduced dimensional motifs such as 2D sheets, 1D chains, or 0D clusters intrinsically built into their crystal structures. *(p.1)*
- As shown in Figure 4b, the H ∥ b and H ∥ c magnetization of La4Co4Pb first increases on cooling and reaches a peak near 220 K, characteristic of antiferromagnetic order in which the moments are aligned along the b-axis. *(p.7)*
- Likewise, instead of a sharp peak like that observed in La4Co4Pb, the magnetization of La4Co4Bi and La4Co4Sb reaches a very broad maximum centered respectively at 195 K and 170 K in each material. *(p.7)*

## Research Evidence Ledger

| ID | Claim | Page | Type | Support | Best evidence |
|---|---|---|---|---|---|
| C1 | We outline how pairs of strongly immiscible elements, referred to here as antagonistic pairs, can be used to synthesize ternary compounds with low or quasi-reduced dimensional motifs intrinsically built into their crystal structures. | 1 | assertion | 🟠 weak | p.6: As the La4Co4X family are new materials that adopt a new structure type, this work serves … |
| C2 | The Co is moment bearing in each La4Co4X compound studied, and we show that whereas La4Co4Pb behaves as a three dimensional antiferromagnet with T N = 220 K, La4Co4Bi and La4Co4Sb have behavior consistent with low dimensional magnetic coupling and ordering, with T N = 153 K and 143 K respectively. | 1 | assertion | 🟡 moderate | p.8: The inferred T N agree well with the transition temperatures determined from the resistivi… |
| C3 | We anticipate that identifying and using mutually compatible third elements together with an antagonistic pair represents a novel and generalizable design principle for discovering new materials and new structure types containing low-dimensional substructures. | 1 | generalization | 🟠 weak | p.6: The existence of stable ternary compounds containing the pairs Co-Pb and Co-Bi demonstrate… |
| C4 | As a demonstration, we present the discovery of a new family of intermetallic compounds, La4Co4X (X = Pb, Bi, Sb), that are based on the immiscible pairs Co-Pb and Co-Bi. | 9 | contribution | 🟠 weak | p.9: More generally, the La4Co4X family contains at least three new Co-based intermetallic comp… |
| C5 | This work opens the door to a generalizable strategy of exploiting strongly immiscible pairs to target materials with low dimensional structural motifs. | 9 | generalization | 🟠 weak | p.6: As the La4Co4X family are new materials that adopt a new structure type, this work serves … |

## Reproducibility: 13.2/100

_100 * sum(weight * credit) / sum(weight); credit: present=1, partial=0.5, missing=0; not_applicable items are left out of both sums_

| Item | Status | Weight | Evidence |
|---|---|---|---|
| Code available | missing | 3.0 | Publish code (with a permanent link) and trained checkpoints. |
| Datasets named and accessible | missing | 2.0 | Name every dataset with version/source and state how to obtain it. |
| Train/validation/test splits specified | not_applicable | 2.0 | Not scored: no model training was detected in this paper. |
| Preprocessing described | missing | 1.0 | Describe cleaning, tokenisation and augmentation steps. |
| Hyperparameters reported | not_applicable | 2.0 | Not scored: no model training was detected in this paper. |
| Seeds / multiple runs | missing | 2.0 | Run with several seeds and report how many. |
| Variance / uncertainty reported | missing | 2.0 | Report standard deviation or confidence intervals, not single numbers. |
| Statistical significance test | missing | 1.5 | Back 'significant' claims with a named test and p-value or CI. |
| Baselines described | present | 2.0 | p.8: However, the transition in the X = Bi and Sb compounds appears substantially bro… |
| Ablation / component analysis | missing | 1.0 | Show which components drive the gains. |
| Evaluation metrics defined | partial | 1.0 | p.5: The DFT calculations were performed by using the Perdew-Burke-Ernzerhof (PBE) ex… |
| Compute / hardware reported | missing | 1.0 | State hardware, runtime and total compute budget. |
| Software / library versions | missing | 1.0 | Pin library versions or provide an environment file. |
| Licence / ethics statement | missing | 0.5 | State data/model licences and ethical considerations. |
| Limitations discussed | missing | 1.0 | Add a limitations section naming settings where the method fails. |

_Measures what the paper reports (checklist coverage), not whether results actually reproduce._

## Evidence gaps

- **[HIGH] no_code**: No code or implementation link is given.
- **[MEDIUM] no_limitations**: No limitations section or discussion of failure cases was found.
- **[MEDIUM] unsupported_claim** (p.1): No strong supporting passage found in the paper body for this claim (only weak lexical overlap). — "We outline how pairs of strongly immiscible elements, referred to here as antagonistic pairs, can be used to synthesize ternary compounds with low or quasi-reduced dimensional motifs intrinsically built into their cry..."
- **[MEDIUM] unsupported_claim** (p.1): No strong supporting passage found in the paper body for this claim (only weak lexical overlap). — "We anticipate that identifying and using mutually compatible third elements together with an antagonistic pair represents a novel and generalizable design principle for discovering new materials and new structure type..."
- **[MEDIUM] generalization_narrow_evidence** (p.1): Generalisation/robustness claim, but only 0 evaluation dataset(s) detected (none named). — "We anticipate that identifying and using mutually compatible third elements together with an antagonistic pair represents a novel and generalizable design principle for discovering new materials and new structure type..."
- **[MEDIUM] unsupported_claim** (p.9): No strong supporting passage found in the paper body for this claim (only weak lexical overlap). — "This work opens the door to a generalizable strategy of exploiting strongly immiscible pairs to target materials with low dimensional structural motifs."
- **[MEDIUM] generalization_narrow_evidence** (p.9): Generalisation/robustness claim, but only 0 evaluation dataset(s) detected (none named). — "This work opens the door to a generalizable strategy of exploiting strongly immiscible pairs to target materials with low dimensional structural motifs."
