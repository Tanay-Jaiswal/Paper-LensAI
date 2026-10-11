"""Write held_out_audit.csv from blank_sheet.csv plus the labels below (row -> is_real_claim, evidence_correct, note)."""
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent

L = {
    1: ("y", "p", "Abstract contribution: 'we propose a novel entity set generation framework'. Evidence is only the Figure 2 caption 'An overview of the proposed Entity Set Generation framework'; it points to the framework without describing it."),
    2: ("y", "p", "Abstract assertion about what the method achieves (no predefined order, no error propagation, efficient decoding). Evidence (sec 4.6.2, starts with heading fragment 'and Error Propagation') says a CADEC case study is run 'to verify that SetGNER ... can overcome the Entity Order Confounder and the Error Propagation problem'; no outcome stated and nothing on decoding efficiency."),
    3: ("n", "", "Cut off at 'our model (w/o.' before the assertion; the page continues 'Inverse Generation Training) outperforms state-of-the-art generative NER models'."),
    4: ("y", "p", "Contribution bullet: 'We propose SetGNER, a novel Entity Set Generation framework' (list lead-in run into the sentence). Evidence is only the Figure 2 caption, which points to the framework."),
    5: ("y", "y", "Contribution bullet on Inverse Generation Training. Evidence is the sec 3.4 body sentence 'we propose to help our model learn better right-to-left semantic structure via inverse generation training', i.e. the delivered contribution."),
    6: ("y", "p", "Result bullet: outperforms SOTA seq2seq on five datasets 'while being 3 times faster'. Evidence 'SetGNER is about 3 times faster than the seq2seq NER model' (Table 7) backs the speed part only, not the accuracy part."),
    7: ("y", "y", "Abstract observation that forcing longer outputs benefits attack effectiveness. Evidence (sec 3.2) reports BLEU, ROUGE-L and ASR 'much better than the four accuracy-based methods, proving ... adversarial samples forcing longer outputs also induce worse generation accuracy'."),
    8: ("y", "y", "Contribution: 'we propose a white-box multi-objective attack method called DGSlow'. Evidence is the body sentence 'we propose a white-box targeted DG adversarial attack that integrates multi-objective optimization and adaptive search'."),
    9: ("y", "p", "Abstract result (DGSlow degrades DG models with higher success rate). Evidence is only the caption 'Table 3: Evaluation of attack methods on three victim models in four DG benchmark datasets'; it points to the table without the numbers."),
    10: ("y", "p", "Introduction contribution/result: DGSlow 'achieves a higher attack success rate'. Evidence only lists the metrics ('generation accuracy ... generation length (GL) ... attack success rate (ASR)'); same experiment but no result in it."),
    11: ("y", "n", "Abstract contribution: 'we design testing and isolation strategies ... under a given test budget'. Evidence 'The cumulative infections is at least min{aN, N} in the end' is a step of an appendix proof about Example 2, only sharing the words 'cumulative infections'."),
    12: ("y", "n", "Abstract result: necessity of exploration shown provably and by simulations. Evidence '(64) Step 4.The exploitation process of the specific exploration policy.' is an equation number plus a proof-step heading, not a statement of the result."),
    13: ("y", "n", "Mixes prior work [51],[52] with own finding 'we observe novel exploration-exploitation tradeoffs'. Evidence is an appendix proof sentence about positive nodes being quarantined (page 41); unrelated to the tradeoff."),
    14: ("y", "n", "Contribution: 'we propose an α-linking backward updating algorithm in Appendix A'. Evidence 'Step 3: Consider the computation of {ui(t)}i based on Algorithm 4' is a proof step that only shares 'Algorithm 4'."),
    15: ("y", "n", "Conclusion: reward based policies 'can be arbitrarily sub-optimal' and exploration helps 'by a constant factor'. Evidence 'Repeating the process, we can compute the estimated probability vectors ...' is a procedural remark, not this result."),
    16: ("n", "", "unsure. 'But increase in g significantly increases the computation time' is given as the reason for choosing g = 1 ('for computational tractability ... we use g = 1'), with no measurement; read as method justification rather than a finding."),
    17: ("n", "", "unsure. Sentence ends at a comma at the page break ('significantly increases the computation time,') and concerns a hypothetical extension to symptom states that the paper does not carry out; read as limitation/future-work discussion."),
    18: ("y", "n", "Abstract result: 'dM/dtHII I ~ 10 Msun/yr' and 'M HII I = 5 x 10^9 Msun'. Evidence is about 'E(B-V) = 0.6-1.0 in ap1 and ap2' and '5-10x higher Weq' (Na I D absorption), a different quantity."),
    19: ("y", "n", "Abstract conclusion: momentum-driven flow, 'p boost ~7'. Evidence 'just below the estimated 7 Myr estimate of the most recent burst' is a starburst age; the 7 matches only by coincidence."),
    20: ("y", "n", "Measurement: SDSS spectrum '26% higher in flux over 6500-9000 A ... 80% at 4000 A'. Evidence is about the [O II]/Halpha ratio rising 'from about 1/3 in the center, to unity at 20 kpc', a different quantity."),
    21: ("y", "n", "Fit result: only ap1 has non-zero stellar attenuation, 'E(B-V)* = 0.3'. Evidence gives electron densities 'log(ne/cm-3) = 2.3' in ap1.1, a different quantity."),
    22: ("y", "n", "Result (preceded by a parenthetical sentence): broad [O I] in ap1 redshifted by 'Δv = 350 km/s' and narrower by 'Δσ = 200 km/s'. Evidence 'vNaI − vFeII ~ −200 km/s' is a Na I vs Fe II absorption offset, a different quantity."),
    23: ("y", "n", "Hedged interpretation: lower velocity consistent with 'lower line ratios in ap6 and ap8 compared to ap3-ap5'. Evidence 'For ap4 and ap5, log(ne/cm-3) < 1' says nothing about ap6/ap8 line ratios or a decrease of density with radius."),
    24: ("y", "p", "Result: ap1.2 at r = 0-5 kpc shows elevated [O III]/Hβ, [N II]/Hα, [O III]/[O II]. Evidence '(the outflow at radii 0-5 kpc), high shock velocities (300-400 km s-1) and an ionized precursor are needed' is the interpretation for the same region but does not state the line ratios; starts mid-sentence."),
    25: ("y", "n", "Assertion that higher post-shock densities 'do not significantly change the results, as the lower-density pre-shock gas dominates the mass'. Evidence is about 'high-velocity gas' not contributing to the mass or outflow rate, a different point."),
    26: ("y", "p", "Result: 'Method 1a ... yields a flow rate 15-20x lower'. Evidence defines Method 1 ('single-radius wind ... RI = 40 kpc and RII = 15 kpc'); same calculation but no 15-20x figure."),
    27: ("y", "p", "Result: predicted 'LSFR Hα = (2.6-3.5) x 10^43', '3-4x larger than' observed '9.4 x 10^42 erg s-1 (Section 3)'. Evidence gives the observed 'Ltot Hα = (9.4+6.0-3.0) x 10^42 erg s-1' only, not the predicted value or the ratio."),
    28: ("y", "n", "Result: 'dp/dtHII+H2 II = 7 x (dp/dt* + dp/dtrad) for τeff,IR = 0'. Evidence 'We fit a linear relationship between 0 and 35 kpc (Figure 4) with an RMS of 0.3 dex' concerns the [O II]/Hα bootstrap, unrelated."),
    29: ("y", "n", "Assertion: putting all Hα emission in the post-shock region 'would lower the mass, momenta, and energy ... by a factor ~50'. Evidence is about a parabolic fit raising luminosity 'by 15%' and how electron density is calculated; no factor 50."),
    30: ("y", "n", "Result: 'dE/dtHII I = 0.003 Lshock,I' (Episode I). Evidence 'dE/dt* is ≲4% of dE/dtHII+H2 II' is the Episode II starburst energy budget, a different quantity."),
    31: ("y", "y", "Summary result 'dE/dtI = 0.003 Lrad'. Evidence is the sec 4.5 sentence 'Thus, dE/dtHII I = 0.003 Lshock,I, a significant discrepancy', the same number for the same quantity."),
    32: ("y", "y", "Abstract result: Δ17O of non-dust sulfate averages '1.7‰ ± 0.5‰' (Δ printed as '1' in the extracted text). Evidence, a fragment cut at 'in the Mt.', reads 'The high Δ17O(SO4)SAS values with an average of 1.7‰±0.5‰'; same number, same quantity."),
    33: ("y", "p", "Abstract conclusion: 'observational constraint on atmospheric acidity in altering sulfate formation pathways, particularly in dust-rich environments'. Evidence (starts mid-sentence at 'Everest region, in turn,') restates this in nearly the same words with no data in the passage."),
    34: ("y", "p", "Sentence start is cut (page reads 'The average Δ17O(SO4)SAS value of 1.7‰ ± 0.5‰ observed from the Mt. Everest region is higher than ...') but the claim is still clear. Evidence gives the mid-latitude value 'averaged at 1.0‰ ± 0.7‰, n = 225' only, not the Everest value or the comparison."),
    35: ("n", "", "Abstract motivation: 'There is an urgent need to identify higher risk areas' is a statement of need, not a finding of the study."),
    36: ("n", "", "Background about WHO actions in 2017 and 2019 with citations [3, 7]; not the paper's own work."),
    37: ("y", "p", "Discussion sentence mixing background figures with the study's finding 'the majority of cases are in areas with forest major habitat type with lower GDP and a lower percentage of urbanization'. Evidence gives only the area '8,515,767.049 km2' and '5,570 municipalities' from Methods, not the finding or the ampoule figures."),
    38: ("n", "", "General statement about boat transport in the Legal Amazon Region and what it could lead to; context/speculation, not a result of this study. Evidence cell is empty."),
    39: ("y", "p", "Conclusion: 'This study brings evidence that saving the lives of snakebite victims in Brazil is a major activity of the health system ...'. Evidence is the Discussion sentence with '234,194 ampoules were distributed to 2,212 hospitals' for the first half; the 'majority of cases ... forest ... lower GDP' half is only repeated in the same words."),
    40: ("n", "", "Abstract background: 'There is increasing evidence supporting a prolonged viral shedding window ... transmissibility in this phase is unclear'; about the state of knowledge, not this paper's finding."),
    41: ("y", "p", "Contribution: 'we develop a generalized ... (SEIR) model including an additional compartment of chronically infected individuals'. Evidence is the author-summary sentence 'Here we investigate the plausibility of a population of chronically infected individuals ...', a near restatement with no model detail."),
    42: ("n", "", "Figure caption text (Fig 3, followed by '...pcbi.1008609.g003'): 'highlighted in blue, red, and pink, respectively'; not prose of the paper."),
    43: ("y", "p", "Abstract conclusion: 'we propose that ... microtubule plus-end dynamics provide the force to resolve DNA catenations'. Evidence says 'EB1 and Map205 may be required to establish microtubule interactions with the acentric' and Topoisomerase resolves catenations; a weaker version that does not say plus-end dynamics provide the force."),
    44: ("y", "y", "Result: telomeres opposed in '33% compared to 14% and 0% for sliding and unzipping'. Evidence: '14% and 33% of acentric sisters that separated by sliding and dissociating, respectively, aligned with their telomeres opposed'."),
    45: ("y", "p", "Result: reducing Topoisomerase II increases failed sister acentric separation, supporting catenation holding sisters after cohesin removal. Evidence only gives the catenation statement, attributed to 'studies of intact chromosomes ... [52,55,56]'; it has no Topoisomerase II knockdown result."),
}

with open(HERE / "blank_sheet.csv", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

assert len(rows) == 45
assert sorted(L) == list(range(1, 46))
assert [int(r["row"]) for r in rows] == list(range(1, 46))
for r in rows:
    real, ev, note = L[int(r["row"])]
    assert real in ("y", "n") and note.strip()
    if real == "y" and r["evidence"].strip():
        assert ev in ("y", "p", "n"), r["row"]
    else:
        assert ev == "", r["row"]
    r["is_real_claim"], r["evidence_correct"], r["notes"] = real, ev, note

with open(HERE / "held_out_audit.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

print("is_real_claim", Counter(r["is_real_claim"] for r in rows))
print("evidence_correct", Counter(r["evidence_correct"] or "blank" for r in rows))
print("empty evidence rows", [r["row"] for r in rows if not r["evidence"].strip()])
