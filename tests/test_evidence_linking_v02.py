"""Regression tests for the three evidence-linking fixes of 0.2.0-dev (docs/EVIDENCE_LINKING_FIX_PLAN.md).

Every sentence, number and document here is SYNTHETIC: written for these tests, not taken from any real paper and not
from the development or held-out papers. The tests pin behaviour; they say nothing about accuracy on real papers.
"""
from pathlib import Path

import pytest

from paperlens import claims as C
from paperlens.claims import evidence_unsuitable, link_evidence
from paperlens.gaps import detect_gaps
from paperlens.models import Claim, Document, Sentence
from paperlens.pipeline import Analysis
from paperlens.report import to_markdown
from paperlens.textutils import match_quantities, numbers_in, quantities_in, tokenize

ROOT = Path(__file__).resolve().parent.parent

# synthetic filler: body sentences that have nothing to do with any claim below
FILLER = ["The detector records every event that passes the trigger selection.",
          "Each run is calibrated against a reference source before the analysis begins.",
          "Samples were stored in sealed containers at room temperature for the whole campaign.",
          "The questionnaire was translated by two independent reviewers and then compared."]


def _doc(claim_text, body, claim_section="abstract"):
    """A synthetic document: one claim sentence followed by body sentences given as (text, section[, kind[, heading]])."""
    sents = [Sentence(0, claim_text, 1, claim_section)]
    for i, b in enumerate(body, 1):
        text, section, kind, heading = (list(b) + ["text", ""])[:4] if len(b) < 4 else b
        sents.append(Sentence(i, text, 2 + i // 4, section, heading, kind))
    claim = Claim("C1", 0, claim_text, 1, claim_section, "result", False, numbers_in(claim_text))
    return Document("synthetic", "Synthetic test document", 9, sents), claim


def _fill(section="method"):
    return [(t, section) for t in FILLER]


def _matched(claim_text, passage_text):
    return match_quantities(quantities_in(claim_text), quantities_in(passage_text))


def _verdict(claim_text, sentence, lex=0.2):
    matched = _matched(claim_text, sentence.text)
    return evidence_unsuitable(sentence, set(tokenize(claim_text)), {q.value for q in quantities_in(claim_text)},
                               matched, lex)


# ---- Fix 1: abstention ---------------------------------------------------------------------------------------------

def test_threshold_constants_are_the_documented_ones():
    # changing these changes every number in docs/EVALUATION.md section 6; do it on purpose, not by accident
    assert (C.MIN_LEXICAL, C.MIN_LEXICAL_WITH_QUANTITY) == (0.30, 0.12)
    assert C.THRESHOLDS["min_lexical"] == C.MIN_LEXICAL


def test_supported_claim_keeps_its_passage():
    doc, claim = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.",
                      [("Accuracy on the benchmark reached 91.2% with the full synthetic model.", "results")] + _fill())
    link_evidence(doc, [claim])
    assert claim.evidence_status == "found" and claim.evidence_note == ""
    assert claim.evidence[0].sentence_id == 1 and claim.evidence[0].shared_numbers == ["91.2"]
    assert claim.support in ("strong", "moderate")
    assert all(e.sentence_id not in (2, 3, 4, 5) for e in claim.evidence)      # the filler is not attached as padding


def test_claim_with_no_relevant_passage_abstains():
    doc, claim = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.", _fill("results"))
    link_evidence(doc, [claim])
    assert claim.evidence == []
    assert claim.evidence_status == "no_supporting_evidence"
    assert claim.evidence_note == "No supporting evidence found"
    assert claim.support == "none" and claim.support_score == 0.0
    assert claim.rejected.get("below_relevance_threshold", 0) >= 1               # the reason is recorded


def test_document_without_body_text_is_reported_as_unsearchable():
    doc, claim = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.",
                      [("We conclude that the synthetic model reaches 91.2% accuracy.", "conclusion"),
                       ("A. Author, Journal of Synthetic Results 12, 345.", "references")])
    link_evidence(doc, [claim])
    assert claim.evidence == [] and claim.evidence_status == "no_searchable_text"
    assert claim.evidence_note.startswith("Evidence search not possible")
    # a document that could not be searched is a parsing problem, not an unsupported claim
    assert not [g for g in detect_gaps(doc, [claim], {"items": []}) if g.kind == "unsupported_claim"]


def test_relinking_does_not_accumulate_evidence():
    doc, claim = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.",
                      [("Accuracy on the benchmark reached 91.2% with the full synthetic model.", "results")] + _fill())
    link_evidence(doc, [claim])
    n = len(claim.evidence)
    link_evidence(doc, [claim])
    assert len(claim.evidence) == n


def test_a_matched_quantity_lowers_the_bar_but_does_not_remove_it():
    assert C.is_relevant(0.31, [])
    assert not C.is_relevant(0.29, [])
    assert C.is_relevant(0.13, ["91.2"])
    assert not C.is_relevant(0.11, ["91.2"])


def test_report_and_ledger_json_carry_the_abstention_text():
    found, c1 = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.",
                     [("Accuracy on the benchmark reached 91.2% with the full synthetic model.", "results")] + _fill())
    _, c2 = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.", _fill("results"))
    _, c3 = _doc("The synthetic model improves accuracy to 91.2% on the benchmark.", [])
    link_evidence(found, [c1])
    link_evidence(_doc(c2.text, _fill("results"))[0], [c2])
    link_evidence(_doc(c3.text, [])[0], [c3])
    c2.id, c3.id = "C2", "C3"
    rubric = {"score": 0, "band": "n/a", "formula": "synthetic", "items": [], "disclaimer": "synthetic"}
    a = Analysis(found, {}, [c1, c2, c3], rubric, [], [], [])
    rows = {line.split("|")[1].strip(): line for line in to_markdown(a).splitlines() if line.startswith("| C")}
    assert "p.2: Accuracy on the benchmark reached 91.2%" in rows["C1"]
    assert rows["C2"].rstrip(" |").endswith("No supporting evidence found")
    assert "Evidence search not possible" in rows["C3"]
    d = a.to_dict()
    assert d["ledger_stats"]["evidence_status"] == {"found": 1, "no_supporting_evidence": 1, "no_searchable_text": 1}
    assert d["ledger_stats"]["thresholds"]["min_lexical"] == C.MIN_LEXICAL
    assert [c["evidence_status"] for c in d["ledger"]] == ["found", "no_supporting_evidence", "no_searchable_text"]
    assert d["ledger"][1]["evidence"] == [] and d["ledger"][1]["evidence_note"] == "No supporting evidence found"


def test_web_ui_shows_the_status_text_from_the_ledger():
    # the UI is plain JavaScript and is not executed here; this only checks that it reads the field the API sends
    js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    assert 'c.evidence_note || "No supporting evidence found"' in js


# ---- Fix 2: a number matches only when the quantity matches --------------------------------------------------------

@pytest.mark.parametrize("claim, passage", [
    ("The new solver is 7x faster than the baseline.", "The cluster has an estimated age of 7 Myr."),
    ("The outflow reaches a velocity of 200 km/s.", "We simulated 200 particles in each run."),
    ("The method improves accuracy by 3.5% over the baseline.", "The model scores 3.5 BLEU on the test set."),
    ("Follow-up lasted 30 days.", "Participants reported a mean score of 30 on the scale."),
    ("The intervention reduces error by 28%.", "In total 28 participants completed the study."),
    ("We enrolled 12 patients.", "The encoder has 12 layers."),
    ("The learning rate is 1e-3.", "A smaller rate of 1e-4 was used for fine-tuning."),
    ("Error falls to between 3.5 and 4.2% on the benchmark.", "The system scores 3.5 BLEU and 4.2 ROUGE."),
    ("The measured mass is 125.3 ± 0.6 GeV.", "Runs lasted 125.3 seconds with a 0.6 mm gap."),
])
def test_same_number_different_quantity_does_not_match(claim, passage):
    assert _matched(claim, passage) == []


@pytest.mark.parametrize("claim, passage, values", [
    ("A gain of 3.50% in accuracy.", "Accuracy rose by 3.5%.", ["3.5"]),
    ("The model is trained on 1,200 samples.", "We use 1200 samples for training.", ["1200"]),
    ("The learning rate is 1e-3.", "The learning rate was set to 10^-3.", ["1e-3"]),
    ("The learning rate is 1e-3.", "The learning rate was set to 1 × 10^-3.", ["1e-3"]),
    ("The p-value is 1.7×10−9.", "We obtain a p-value of 1.7e-9.", ["1.7e-9"]),
    ("The system achieves 41.8 BLEU on the task.", "It reaches a BLEU of 41.8 on the test set.", ["41.8"]),
    ("The system achieves 41.8 BLEU on the task.", "BLEU 41.8", ["41.8"]),
    ("The accuracy is 91.2%.", "The model reaches 91.2 percent accuracy.", ["91.2"]),
    ("Error falls to between 3.5 and 4.2% on the benchmark.", "The error rate ranges from 3.5% to 4.2%.", ["3.5", "4.2"]),
    ("Error rates of 3.5–4.2% are observed.", "The error rate ranges from 3.5% to 4.2%.", ["3.5", "4.2"]),
    ("Accuracy rose from 88.1 to 91.2%.", "Accuracy improved from 88.1% to 91.2%.", ["88.1", "91.2"]),
    ("The measured mass is 125.3 ± 0.6 GeV.", "We find a mass of 125.3±0.6 GeV.", ["0.6", "125.3"]),
    ("The measured mass is 125.3 +/- 0.6 GeV.", "We find a mass of 125.3 ± 0.6 GeV.", ["0.6", "125.3"]),
    ("The outflow reaches a velocity of 200 km/s.", "The outflow velocity is 200 km/s.", ["200"]),
    # a score written as a percentage, and a range whose unit is named before its first number
    ("The tagger achieves 89.1% F1 on the corpus.", "The tagger obtains 89.1 F1 on the corpus.", ["89.1"]),
    ("Our approach improves F1 on the corpus from 85.6 to 89.1.", "The tagger obtains 89.1 F1 on the corpus.", ["89.1"]),
])
def test_same_quantity_in_another_format_matches(claim, passage, values):
    assert _matched(claim, passage) == values


def test_quantity_parsing_details():
    q = {x.value: x.unit for x in quantities_in("between 3.5 and 4.2% and 125.3 ± 0.6 GeV, lr 10^-3, 1,200 samples")}
    assert q == {"3.5": "%", "4.2": "%", "125.3": "gev", "0.6": "gev", "1e-3": "", "1200": "sample"}
    # numbers that merely stand next to each other do not share a unit (a flattened table row)
    assert {x.value: x.unit for x in quantities_in("row 3.5 4.2% 12 epochs")}["3.5"] == ""
    assert quantities_in("In 2017 the CIFAR-10 results in Table 3 [12] used PyTorch 2.1") == []


def test_percentage_versus_fraction_is_a_known_miss():
    # documented limit (docs/LIMITATIONS.md): 91.2% and 0.912 are the same quantity but are not reconciled
    assert _matched("The accuracy is 91.2%.", "The accuracy is 0.912.") == []


def test_coincidental_number_does_not_make_a_link_strong():
    claim_text = "The new solver is 7x faster than the baseline on large sparse systems."
    doc, claim = _doc(claim_text, [("The cluster has an estimated age of 7 Myr in the reference catalogue.", "results")]
                      + _fill())
    link_evidence(doc, [claim])
    assert claim.evidence == [] and claim.evidence_status == "no_supporting_evidence"
    doc, claim = _doc(claim_text, [("On large sparse systems the solver is 7 times faster than the baseline.", "results")]
                      + _fill())
    link_evidence(doc, [claim])
    assert claim.evidence and claim.evidence[0].shared_numbers == ["7"] and claim.support in ("strong", "moderate")


# ---- Fix 3: passages that cannot serve as evidence -----------------------------------------------------------------

CLAIM = "The synthetic encoder improves retrieval accuracy to 91.3 F1 on the benchmark."


@pytest.mark.parametrize("sentence, reason", [
    (Sentence(1, "Figure 2: An overview of the synthetic encoder framework.", 3, "results", kind="caption"), "caption_label_only"),
    (Sentence(1, "Retrieval accuracy on the benchmark", 3, "results"), "fragment"),
    (Sentence(1, "Step 2: Bound the retrieval error term.", 3, "appendix"), "step_or_proof_heading"),
    (Sentence(1, "Proof. The retrieval accuracy bound follows directly.", 3, "appendix"), "step_or_proof_heading"),
    (Sentence(1, "x = 0.4 y + 2.1 z ; 91.3 88.0 77.5 12 4 0.1 a b c", 3, "results"), "symbols_or_numbers"),
    (Sentence(1, "The synthetic encoder improves retrieval accuracy to 91.3 F1 on the benchmark overall.", 4, "discussion"),
     "restates_claim"),
    (Sentence(1, "Synthetic Journal 11(7): e0000000. Editor: A. Person, received and accepted.", 1, "results", kind="meta"),
     "boilerplate"),
    (Sentence(1, "The synthetic encoder improves retrieval accuracy on the benchmark for lay readers.", 1, "other",
              "Author Summary"), "summary_section"),
    (Sentence(1, "Table row: Latency; 91.3 F1; 38.2 F1", 5, "results", kind="table"), "table_row_for_another_quantity"),
    (Sentence(1, "Table row: Retrieval; 40.1; 38.2", 5, "results", kind="table"), "table_row_without_matching_value"),
])
def test_unsuitable_passages_are_rejected_with_a_reason(sentence, reason):
    assert _verdict(CLAIM, sentence) == reason


@pytest.mark.parametrize("sentence", [
    # a caption that carries the claimed quantity
    Sentence(1, "Table 4: Retrieval results; the synthetic encoder reaches 91.3 F1 on the benchmark.", 5, "results", kind="caption"),
    # appendix prose that carries the claimed quantity
    Sentence(1, "With the larger index the encoder reaches 91.3 F1 on the benchmark test split.", 9, "appendix"),
    # a results sentence may repeat the claim's numbers: that is what evidence looks like
    Sentence(1, "The synthetic encoder improves retrieval accuracy to 91.3 F1 on the benchmark.", 5, "results"),
    # a discussion sentence that adds a number the claim does not have is not a mere restatement
    Sentence(1, "The synthetic encoder improves retrieval accuracy to 91.3 F1 on the benchmark, from 84.6.", 6, "discussion"),
    # a table row whose label is what the claim is about and which holds the value
    Sentence(1, "Table row: Retrieval accuracy; 84.6 F1; 91.3 F1", 5, "results", kind="table"),
    # a long numbered step that states a result in prose is not a heading
    Sentence(1, "Step 2: the retrieval error is bounded because every query is matched against the full synthetic "
                "index before the scores are normalised.", 9, "appendix"),
])
def test_legitimate_passages_are_kept(sentence):
    assert _verdict(CLAIM, sentence) == ""


def test_results_sentence_dense_with_figures_is_not_mistaken_for_a_number_dump():
    # found by the synthetic benchmark: short function words were counted as non-prose and this kind of sentence,
    # the best evidence there is, was rejected as "symbols_or_numbers"
    text = "As shown in Table 1, the tagger obtains 89.1 F1 on the corpus, compared with 86.2 for T5, an improvement of 2.9 points."
    claim_text = "The tagger achieves 89.1% F1 on the corpus, outperforming T5 by 2.9 points."
    assert _verdict(claim_text, Sentence(1, text, 5, "results")) == ""
    doc, claim = _doc(claim_text, [(text, "results")] + _fill())
    link_evidence(doc, [claim])
    assert claim.evidence and claim.evidence[0].sentence_id == 1
    assert claim.evidence[0].shared_numbers == ["2.9", "89.1"] and claim.support == "strong"


def test_caption_without_the_number_needs_a_full_statement_and_high_overlap():
    cap = Sentence(1, "Figure 3: The synthetic encoder improves retrieval accuracy on the benchmark across all five "
                      "query lengths, document collections and index sizes tested.", 5, "results", kind="caption")
    assert _verdict(CLAIM, cap, lex=C.CAPTION_MIN_LEXICAL + 0.01) == ""
    assert _verdict(CLAIM, cap, lex=C.CAPTION_MIN_LEXICAL - 0.01) == "caption_label_only"


def test_filter_end_to_end_false_matches_are_skipped_and_real_evidence_is_returned():
    body = [("Figure 2: An overview of the synthetic encoder framework.", "results", "caption"),
            ("Retrieval accuracy on the benchmark", "results"),
            ("Step 2: Bound the retrieval error term.", "appendix"),
            ("The synthetic encoder improves retrieval accuracy to 91.3 F1 on the benchmark overall.", "discussion"),
            ("Table 4: Retrieval results; the synthetic encoder reaches 91.3 F1 on the benchmark.", "results", "caption"),
            ("With the larger index the encoder reaches 91.3 F1 on the benchmark test split.", "appendix")] + _fill()
    doc, claim = _doc(CLAIM, body)
    link_evidence(doc, [claim])
    assert sorted(e.sentence_id for e in claim.evidence) == [5, 6]
    assert all(e.shared_numbers == ["91.3"] for e in claim.evidence)
    for reason in ("caption_label_only", "fragment", "step_or_proof_heading", "restates_claim"):
        assert claim.rejected.get(reason) == 1, reason


def test_only_false_matches_means_abstention():
    body = [("Figure 2: An overview of the synthetic encoder framework.", "results", "caption"),
            ("Retrieval accuracy on the benchmark", "results"),
            ("Step 2: Bound the retrieval error term.", "appendix"),
            ("The synthetic encoder improves retrieval accuracy to 91.3 F1 on the benchmark overall.", "discussion")] + _fill()
    doc, claim = _doc(CLAIM, body)
    link_evidence(doc, [claim])
    assert claim.evidence == [] and claim.evidence_status == "no_supporting_evidence"


def test_abstract_and_conclusion_count_only_when_they_add_data():
    # 0.1.0 never searched the abstract, introduction or conclusion. They are now searched, but a sentence there is
    # returned only if it gives a figure the claim does not contain; otherwise it is the claim again in other words.
    body = [("In conclusion the encoder reaches 91.3 F1 on the benchmark in all our retrieval experiments.", "conclusion"),
            ("We show that the encoder reaches 91.3 F1 on the benchmark for retrieval.", "abstract"),
            ("Retrieval with the encoder reaches 91.3 F1 on the benchmark test split.", "results"),
            ("In conclusion the encoder reaches 91.3 F1 on the benchmark, against 84.6 F1 for the baseline.", "conclusion")] + _fill()
    doc, claim = _doc(CLAIM, body, claim_section="introduction")
    link_evidence(doc, [claim])
    assert [e.sentence_id for e in claim.evidence] == [3, 4]          # body text first, then the conclusion with new data
    assert claim.rejected.get("claim_zone_without_new_data") == 2


def test_conclusion_with_new_data_is_evidence_when_the_body_has_none():
    body = [("In conclusion the encoder reaches 91.3 F1 on the benchmark, against 84.6 F1 for the baseline.", "conclusion")] + _fill()
    doc, claim = _doc(CLAIM, body)
    link_evidence(doc, [claim])
    assert [e.section for e in claim.evidence] == ["conclusion"] and claim.evidence_status == "found"


def test_another_headline_claim_is_not_evidence():
    # found by the synthetic benchmark: two abstract claims with the same score were returned as evidence for each other
    a = "On the first corpus, the tagger reaches 89.4 F1, a gain of 1.8 over the baseline."
    b = "On the second corpus, the tagger reaches 89.4 F1, a gain of 3.5 over the baseline."
    sents = [Sentence(0, a, 1, "abstract"), Sentence(1, b, 1, "abstract"),
             Sentence(2, "As shown, the tagger obtains 89.4 F1 on the first corpus, compared with 87.6 for the baseline.", 4, "results")]
    sents += [Sentence(3 + i, t, 3, "method") for i, t in enumerate(FILLER)]
    claims = [Claim("C1", 0, a, 1, "abstract", "result", False, numbers_in(a)),
              Claim("C2", 1, b, 1, "abstract", "result", False, numbers_in(b))]
    link_evidence(Document("synthetic", "t", 5, sents), claims)
    assert [e.sentence_id for e in claims[0].evidence] == [2]
    assert all(e.sentence_id != 0 for e in claims[1].evidence)
