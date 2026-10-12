# PaperLens report: Effectiveness of a peer educator-coordinated preference-based differentiated service delivery model on viral suppression among young people living with HIV in Lesotho: The PEBRA cluster-randomized tri

*16 pages · 7 claims · reproducibility 63.2/100 (moderate)*

## Summary

- The cluster-randomized trial compared PEBRA model versus standard clinic care (no PE and ART refill done by nurses) in 3 districts in Lesotho. *(p.1)*
- In the 10 clinics randomized to the intervention arm, participants were offered the PEBRA model, coordinated by a trained PE and supported by an eHealth application (PEBRApp). *(p.1)*

**Problem**
- The main limitation was that the data collectors in the control clusters were also young peers; however, they used a restricted version of the PEBRApp to collect data and thus were not able to provide the PEBRA model. *(p.2)*
- In Lesotho, similar to other countries in the region, efforts to adapt HIV care to adolescents and young adults are promoted [7], but young peers still only play a limited role in providing services. *(p.3)*

**Results**
- Several systematic reviews concluded that evidence for interventions to improve engagement in HIV care among adolescents and young adults in low-resource settings is of low quality [6,8,9], and in general, DSD models are not designed for young people nor led by young people [10]. *(p.3)*
- At the 12-month follow-up, 99 of 150 (66%) participants in the intervention versus 95 of 157 (61%) participants in the control arm achieved viral suppression below 20 copies/mL (adjusted OR 1.27; 95% CI [0.79 to 2.03]; p = 0.327; Table 2). *(p.8)*
- The primary analysis indicated that participants from Mokhotlong district were less likely to reach viral suppression. *(p.10)*

**Limitations**
- Third, the data collectors in the control clusters were also young peers, who used the same data collection tool (a restricted version of the PEB- RApp). *(p.13)*

## Research Evidence Ledger

| ID | Claim | Page | Type | Support | Best evidence |
|---|---|---|---|---|---|
| C1 | AU : Pleaseconfirmthatallheadinglevelsarerepresentedcorrectly: Southern and Eastern Africa is home to more than 2.1 million young people aged 15 to 24 years living with HIV. | 1 | comparison | 🟢 strong | p.8: Between November 6, 2019 and February 4, 2020, 315 young people (aged 15 to 24 years) livi… |
| C2 | From November 6, 2019 to February 4, 2020, we enrolled 307 individuals (150 intervention, 157 control; 218 [71%] female, median age 19 years [interquartile range, IQR, 17 to 22]). | 1 | result | 🟢 strong | p.8: The median age was 19 years (interquartile range [IQR] 17 to 22), 218 (71%) female, 93 (30… |
| C3 | At 12 months, 99 of 150 (66%) participants in the intervention versus 95 of 157 (61%) participants in the control arm had viral suppression (adjusted odds ratio (OR) 1.27; 95% | 1 | result | 🟢 strong | p.8: At the 12-month follow-up, 99 of 150 (66%) participants in the intervention versus 95 of 1… |
| C4 | There were no significant differences between arms in other secondary outcomes. | 2 | assertion | 🟡 moderate | p.10: The PEBRA model had a favorable effect on most other secondary endpoints, but the differen… |
| C5 | Overall, viral suppression increased from 166/307 (54%) at baseline to 194/307 (63%) at 12 months of follow-up. | 10 | result | 🟡 moderate | p.8: The baseline characteristics of the 307 participants are shown in Table 1.… |
| C6 | Our pre-planned subgroup analysis suggests such a direction of effect (S4 Table), although this effect has to be interpreted with caution and the interaction term was not significant (p-interaction 0.515). | 12 | result | 🟠 weak | p.10: We found no significant interaction of the prespecified effect modifiers on the primary en… |
| C7 | During the study period of the PEBRA trial, viral suppression rates in both groups increased by 9%. | 13 | result | 🟢 strong | p.13: First, in both groups, 9% of participants in care at 12 months had a missing VL measuremen… |

## Reproducibility: 63.2/100

_100 * sum(weight * credit) / sum(weight); credit: present=1, partial=0.5, missing=0; not_applicable items are left out of both sums_

| Item | Status | Weight | Evidence |
|---|---|---|---|
| Code available | present | 3.0 | p.2: Peer educator-coordinated preference-based HIV care model for adolescents living… |
| Datasets named and accessible | partial | 2.0 | p.1: Data Availability Statement: A key pseudoanonymized individual participant datas… |
| Train/validation/test splits specified | not_applicable | 2.0 | Not scored: no model training was detected in this paper. |
| Preprocessing described | missing | 1.0 | Describe cleaning, tokenisation and augmentation steps. |
| Hyperparameters reported | not_applicable | 2.0 | Not scored: no model training was detected in this paper. |
| Seeds / multiple runs | missing | 2.0 | Run with several seeds and report how many. |
| Variance / uncertainty reported | present | 2.0 | p.2: confidence interval [CI] [0.79 to 2.03]; p = 0.327); 4 of 150 (2.7%) versus 1 of… |
| Statistical significance test | present | 1.5 | p.2: confidence interval [CI] [0.79 to 2.03]; p = 0.327); 4 of 150 (2.7%) versus 1 of… |
| Baselines described | present | 2.0 | p.1: As compared with other age groups, this population group has poorer outcomes alo… |
| Ablation / component analysis | partial | 1.0 | p.10: This effect was no longer observed when we adjusted for baseline VL in the presp… |
| Evaluation metrics defined | missing | 1.0 | Define every metric and the averaging scheme (micro/macro). |
| Compute / hardware reported | partial | 1.0 | p.12: Nevertheless, 2 reviews cautiously suggest that youth-friendly services and open… |
| Software / library versions | missing | 1.0 | Pin library versions or provide an environment file. |
| Licence / ethics statement | present | 0.5 | p.1: The editorial history of this article is available here: https://doi.org/10.1371… |
| Limitations discussed | present | 1.0 | p.2: The main limitation was that the data collectors in the control clusters were al… |

_Measures what the paper reports (checklist coverage), not whether results actually reproduce._

## Evidence gaps

- **[MEDIUM] unsupported_claim** (p.12): No strong supporting passage found in the paper body for this claim (only weak lexical overlap); its numbers (0.515) do not appear in results text. — "Our pre-planned subgroup analysis suggests such a direction of effect (S4 Table), although this effect has to be interpreted with caution and the interaction term was not significant (p-interaction 0.515)."
