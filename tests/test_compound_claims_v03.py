"""Regression tests for compound claims (0.3.0-dev): complementary passage selection and figure coverage.

Every sentence and number here is SYNTHETIC, written for these tests. They pin behaviour; they say nothing about
accuracy on real papers (see docs/EVALUATION.md section 9 for what was measured on development papers).
"""
from paperlens import claims as C
from paperlens.claims import coverage_text, link_evidence, quantity_coverage
from paperlens.models import Claim, Document, Sentence
from paperlens.pipeline import Analysis
from paperlens.report import to_markdown
from paperlens.textutils import numbers_in

COMPOUND = ("The synthetic tagger reaches 91.2% accuracy on the Alpha corpus, 84.6% accuracy on the Beta corpus "
            "and 77.3% accuracy on the Gamma corpus.")
# three sentences that all restate the FIRST figure with heavy word overlap, then one sentence per remaining figure
ALPHA = ["On the Alpha corpus the synthetic tagger reaches 91.2% accuracy with the full feature set.",
         "The synthetic tagger reaches 91.2% accuracy on the Alpha corpus after ten training passes.",
         "With beam search the synthetic tagger still reaches 91.2% accuracy on the Alpha corpus."]
BETA = "For the Beta corpus we measured 84.6% accuracy under identical decoding parameters."
GAMMA = "Accuracy on the Gamma corpus was 77.3% when evaluated under identical decoding parameters."
FILLER = ["The detector records every event that passes the trigger selection.",
          "Each run is calibrated against a reference source before the analysis begins.",
          "Samples were stored in sealed containers at room temperature for the whole campaign."]


def _doc(claim_text, body):
    sents = [Sentence(0, claim_text, 1, "abstract")]
    sents += [Sentence(i, t, 2 + i // 4, "results") for i, t in enumerate(body, 1)]
    claim = Claim("C1", 0, claim_text, 1, "abstract", "result", False, numbers_in(claim_text))
    return Document("synthetic", "Synthetic test document", 9, sents), claim


def _linked(claim_text, body, k=3):
    doc, claim = _doc(claim_text, body)
    link_evidence(doc, [claim], k=k)
    return doc, claim


def test_rank_order_alone_would_show_the_same_figure_three_times():
    # the situation the fix is for: the three best-ranked accepted passages all carry 91.2 and nothing else
    doc, claim = _doc(COMPOUND, ALPHA + [BETA, GAMMA] + FILLER)
    ranked = C.rank_passages(claim.text, claim.numbers, doc.sentences[1:])
    assert [set(r[2]) for r in ranked[:3]] == [{"91.2"}] * 3


def test_compound_claim_gets_one_passage_per_figure():
    _, claim = _linked(COMPOUND, ALPHA + [BETA, GAMMA] + FILLER)
    assert claim.evidence[0].quote in ALPHA                       # the top passage is still the best-ranked one
    assert {e.quote for e in claim.evidence[1:]} == {BETA, GAMMA}
    assert claim.quantity_coverage == {"claimed": ["77.3", "84.6", "91.2"], "top": ["91.2"],
                                       "found": ["77.3", "84.6", "91.2"], "missing": []}
    assert "partial_quantity_coverage" not in claim.flags


def test_top_passage_is_the_same_with_and_without_complementary_selection():
    doc, claim = _doc(COMPOUND, ALPHA + [BETA, GAMMA] + FILLER)
    one, _ = C.select_passages(claim.text, claim.numbers, doc.sentences[1:], k=1)
    three, _ = C.select_passages(claim.text, claim.numbers, doc.sentences[1:], k=3)
    assert len(one) == 1 and one[0][3].id == three[0][3].id


def test_missing_figure_is_reported_not_papered_over():
    # nothing in the body states the Gamma result: the claim keeps its passages and says which figure is unmatched
    _, claim = _linked(COMPOUND, ALPHA + [BETA] + FILLER)
    assert claim.evidence_status == "found"
    assert claim.quantity_coverage["missing"] == ["77.3"] and claim.quantity_coverage["found"] == ["84.6", "91.2"]
    assert "partial_quantity_coverage" in claim.flags


def test_same_number_for_another_quantity_does_not_count_as_coverage():
    # 77.3 hours is not 77.3% accuracy; an unrelated sentence must not be pulled in to "cover" the figure
    wrong = "Annotation of the reference transcripts took 77.3 hours in total."
    _, claim = _linked(COMPOUND, ALPHA + [BETA, wrong] + FILLER)
    assert wrong not in [e.quote for e in claim.evidence]
    assert claim.quantity_coverage["missing"] == ["77.3"]


def test_complementary_selection_never_admits_a_rejected_passage():
    # a table-of-contents style fragment carrying a claimed figure is unsuitable, so it cannot be chosen for coverage
    fragment = "Gamma: 77.3% accuracy."
    _, claim = _linked(COMPOUND, ALPHA + [BETA, fragment] + FILLER)
    assert fragment not in [e.quote for e in claim.evidence]
    assert claim.quantity_coverage["missing"] == ["77.3"]


def test_without_new_figures_the_remaining_places_follow_rank_order():
    cand = lambda i, shared: (1.0 - i / 10, 0.5, shared, Sentence(i, f"s{i}", 1, "results"), [])  # noqa: E731
    a, b, c, d = cand(0, ["1.5"]), cand(1, ["1.5"]), cand(2, []), cand(3, ["1.5"])
    assert C._complementary([a, b, c, d], 3) == [a, b, c]
    e = cand(4, ["2.5"])
    assert C._complementary([a, b, c, d, e], 3) == [a, e, b]       # the passage adding 2.5 moves up, the rest keep rank
    assert C._complementary([a, b, c, d, e], 1) == [a]
    assert C._complementary([], 3) == []


def test_coverage_counts_only_figures_evidence_should_reproduce():
    cov = quantity_coverage("In 2019 we trained 3 models on 4 GPUs and reached 88.4 F1 with 120 epochs.",
                            numbers_in("In 2019 we trained 3 models on 4 GPUs and reached 88.4 F1 with 120 epochs."), [])
    assert cov["claimed"] == ["120", "88.4"]                       # the year and the small counts are not result figures
    assert quantity_coverage("We introduce a new method for tagging.", [], [["1.5"]])["claimed"] == []


def test_single_figure_claim_fully_covered_has_no_flag():
    _, claim = _linked("The synthetic model improves accuracy to 91.2% on the benchmark.",
                       ["Accuracy on the benchmark reached 91.2% with the full synthetic model."] + FILLER)
    assert claim.quantity_coverage["missing"] == [] and claim.flags == []


def test_abstention_lists_the_claimed_figures_without_the_partial_flag():
    _, claim = _linked(COMPOUND, FILLER)
    assert claim.evidence == [] and claim.support == "none"
    assert claim.quantity_coverage["found"] == [] and len(claim.quantity_coverage["missing"]) == 3
    assert "partial_quantity_coverage" not in claim.flags          # the abstention status already says nothing was found


def test_relinking_does_not_duplicate_flags():
    doc, claim = _doc(COMPOUND, ALPHA + [BETA] + FILLER)
    link_evidence(doc, [claim])
    link_evidence(doc, [claim])
    assert claim.flags == ["partial_quantity_coverage"]


def test_support_level_rule_is_unchanged_by_coverage():
    # measured on development papers: gating "strong" on full coverage was not justified (docs/EVALUATION.md 9.3)
    _, claim = _linked(COMPOUND, ALPHA + [BETA] + FILLER)
    assert claim.support == "strong"


def test_coverage_text_and_report_line():
    assert coverage_text({}) == "" and coverage_text({"claimed": [], "found": [], "missing": []}) == ""
    assert coverage_text({"claimed": ["1.5"], "found": ["1.5"], "missing": []}) == "the claimed figure is matched"
    doc, claim = _linked(COMPOUND, ALPHA + [BETA] + FILLER)
    assert coverage_text(claim.quantity_coverage) == "2 of 3 claimed figures matched; not found: 77.3"
    md = to_markdown(Analysis(doc=doc, claims=[claim], rubric={"score": 0, "band": "n/a", "formula": "", "items": [],
                                                              "disclaimer": ""}, gaps=[], summary={}, datasets=[], metrics=[]))
    assert "2 of 3 claimed figures matched; not found: 77.3" in md
