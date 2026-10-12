"""AI-ASSISTED labels (pass 1) for the second held-out audit of PaperLens 0.2.0-dev. NOT a human audit.

    python eval/results/held_out_v0.2_ai_audit/pass1/ai_labels_pass1.py

Reads the blank sheet eval/results/held_out_v0.2/held_out_audit.csv (never modified) and writes
held_out_audit_ai_assisted.csv and rationales_pass1.md next to this file. Labelled on 2026-10-12 by the AI assistant
(Claude) following eval/results/held_out_v0.2/AUDIT_INSTRUCTIONS.md, after reading the claim page and the evidence page
of each PDF in data/held_out_v0.2_papers/ with PyMuPDF. Nothing under sealed_key/ or raw/ was opened for labelling.
"""
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
BLANK = HERE.parents[1] / "held_out_v0.2" / "held_out_audit.csv"

# row: (is_real_claim, evidence_correct, note written to the sheet, rationale)
L = {
    1: ("y", "", "", "Abstract sentence stating what ATFormer achieves against the state of the art: a result claim of the paper. No passage shown."),
    2: ("y", "", "", "Conclusion sentence claiming faster-converged latency and better transferability than prior work. No passage shown."),
    3: ("n", "", "", "Abstract sentence about what recent works do and how they are limited: background on other people's work."),
    4: ("y", "p", "judgement call between y and p", "Contribution claim (the ItD framework). The passage is the opening sentence of the Framework section: it says the framework is introduced here, in nearly the claim's words, with no method detail in the passage itself. Near-restatement / pointer: p."),
    5: ("y", "y", "paper prints 36% in the abstract and 35% in this sentence", "Claim: relative improvement of 36% and 10% over previous SOTA on two benchmarks. The passage is the results sentence the claim comes from (Table 1): 35% and 10% over the previous SOTA (HS&R). Same quantity and comparison; the 36/35 mismatch is the paper's own."),
    6: ("y", "p", "", "Finding: fine-tuning with the IO prompt cannot effectively use the observed samples (Figure 5). The passage only defines the IO prompt and says previous works use it. Same object, backs the 'used in previous methods' part, not the finding."),
    7: ("y", "p", "unsure: y is arguable (results-section sentence)", "Conclusion claim that ItD is superior to existing methods. The passage is the closing sentence of the results paragraph, 'These results verify that ItD is better than previous methods ...': the same statement in almost the same words, with the data in the sentence before it, not in the passage. By the restatement rule: p."),
    8: ("y", "", "", "Abstract sentence listing three improvements over previous methods: a result/contribution claim. No passage shown."),
    9: ("y", "y", "", "Claim: improvements over text retrieval in single-document QA and few-shot learning. The passage is the summary of that comparison in the experiments: Neurocache excels in single-document and few-shot scenarios, text retrieval is better on multi-document tasks. Same finding, stated in the body with its qualification."),
    10: ("y", "y", "", "Abstract claim that antagonistic pairs can be used to make ternary compounds with low-dimensional motifs. The passage states this in the body and gives its basis (the La4Co4X family, a new structure type, as proof of principle)."),
    11: ("y", "p", "", "Claim gives T_N = 220 K (Pb), 153 K (Bi), 143 K (Sb) and contrasts 3D with low-dimensional behaviour. The passage gives T_N = 220, 155 and 146 K from the magnetisation derivative: the same quantity for the same compounds, one value equal and two slightly different (another determination), and nothing on dimensionality. Partial."),
    12: ("y", "p", "judgement call on is_real_claim (forward-looking conclusion)", "Hedged conclusion that the approach is a novel, generalizable design principle. The passage says the existence of the Co-Pb and Co-Bi compounds shows immiscibility can be overcome with a compatible third element: supports the principle for this case, not its generality. Weaker version: p."),
    13: ("y", "p", "", "Claim: discovery of a new family La4Co4X based on the immiscible pairs Co-Pb and Co-Bi. The passage says the family contains at least three new Co-based intermetallics with moment-bearing Co: backs 'new family', says nothing about the immiscible pairs. Partial."),
    14: ("y", "p", "judgement call on is_real_claim (significance statement)", "Claim: the work opens the door to a generalizable strategy. The passage calls the work a proof of principle that immiscible pairs can be leveraged: supports a weaker version of the claim."),
    15: ("y", "", "", "Contribution claim (ChartReformer). No passage shown."),
    16: ("y", "", "", "Contribution claim (edit categories and the ChartCraft dataset). No passage shown."),
    17: ("y", "p", "", "Abstract claim: 'we argue ... and show ...'. The passage is the first sentence of the Discussion, which says the paper has argued this and used model systems: a summary restatement with no argument or result in it."),
    18: ("y", "", "", "Abstract sentence stating what the paper shows about interventions. No passage shown."),
    19: ("n", "", "", "Licence line from the page header, not a sentence of the paper's prose."),
    20: ("n", "", "", "Describes how the model is configured (mesh resolutions): method description with no finding. Evidence not judged."),
    21: ("y", "", "", "Abstract finding: precipitation statistics improve with resolution and are negligibly affected by remapping. No passage shown."),
    22: ("n", "", "cut off and merged with the page footer", "The abstract sentence breaks off at 'Limited (~50% slower) through-' and is joined to the publisher's footer line: the assertion is missing. Evidence not judged."),
    23: ("n", "", "", "Speculation about what a coordinated project 'may' facilitate and 'could' accelerate: outlook, not a finding of this work."),
    24: ("y", "p", "passage is cut at '(e.g.'", "Claim: DDX39B controls expression of many MS susceptibility genes and important immune-related genes. The passage reports that 41 of 421 detected MS susceptibility genes were significantly altered by DDX39B depletion: backs the first half with data, not the immune-related genes. Partial."),
    25: ("n", "", "production note 'AU : Pleaseconfirm...' run into the sentence", "Background statistic about young people living with HIV in the region, prefixed by a typesetting query. Not a claim about this study. Evidence not judged."),
    26: ("y", "p", "", "Claim: 307 enrolled (150 intervention, 157 control), 218 [71%] female, median age 19 [IQR 17 to 22], with dates. The passage has the median age, IQR and 218 (71%) female but not the 307, the arm sizes or the dates (they are in the preceding sentences). Part of the claim."),
    27: ("y", "y", "claim text cut off after '95%'", "Claim: 99 of 150 (66%) vs 95 of 157 (61%) with viral suppression at 12 months, adjusted OR 1.27. The passage is the results sentence with exactly these figures, plus the CI and p-value."),
    28: ("y", "y", "", "Claim: no significant differences between arms in other secondary outcomes. The passage: favourable effect on most other secondary endpoints, differences not significant (Table 2). Same finding."),
    29: ("y", "n", "", "Claim: viral suppression rose from 166/307 (54%) to 194/307 (63%). The passage only says the baseline characteristics of the 307 participants are in Table 1: it shares the number 307 and contains neither figure of the claim nor the 12-month result."),
    30: ("y", "p", "", "Hedged finding: subgroup analysis suggests a direction of effect; interaction not significant (p 0.515). The passage reports no significant interaction for the prespecified effect modifiers (S4 Table): backs the non-significance, not the direction of effect or the p-value."),
    31: ("y", "n", "", "Claim: viral suppression rates increased by 9% in both groups. The passage: 9% of participants in both groups had a missing viral-load measurement. Same number, different quantity."),
    32: ("y", "p", "", "Claim: in IFN-competent cells H426A grew more robustly and showed delayed IFN-beta mRNA upregulation compared with E388A. The passage says E388A showed no detectable growth in IFN-competent A549 cells, unlike wild type and H426A: backs the growth half; the mRNA half is in the sentence before it."),
    33: ("y", "p", "passage is a sentence fragment", "Claim: H426A still suppressed IFN-beta promoter activation (88% of WT inhibition, Fig 4). The passage is only the fragment '88% of WT inhibition; Fig 4, left panel)': the right number and figure for the same quantity, but the fragment does not say which mutant or what was inhibited. Judged on the passage shown: partial."),
}


def main():
    rows = list(csv.DictReader(open(BLANK, encoding="utf-8-sig")))
    assert [int(r["row"]) for r in rows] == sorted(L) == list(range(1, 34))
    for r in rows:
        r["is_real_claim"], r["evidence_correct"], r["notes"] = L[int(r["row"])][:3]
    with open(HERE / "held_out_audit_ai_assisted.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    out = ["# Rationales, AI-assisted pass 1 (not human labels)", "",
           "| Row | Paper | Claim | is_real_claim | evidence_correct | Rationale |", "|---|---|---|---|---|---|"]
    for r in rows:
        a, e, _, why = L[int(r["row"])]
        out.append(f"| {r['row']} | {r['paper_file'][:28]} | {r['claim_id']} | {a} | {e or '(blank)'} | {why} |")
    (HERE / "rationales_pass1.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(rows)} rows written")


if __name__ == "__main__":
    main()
