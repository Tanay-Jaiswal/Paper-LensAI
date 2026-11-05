from paperlens.claims import build_ledger
from paperlens.ingest import parse_pdf


def test_supported_claim_links_to_results_page_with_numbers(make_pdf):
    p, truth = make_pdf(3, unsupported=0)
    ledger = build_ledger(parse_pdf(p))
    quant = [c for c in ledger if c.claim_type in ("result", "comparison")]
    assert len(quant) == len(truth.claims)
    for c in quant:
        assert c.support in ("strong", "moderate")
        assert c.evidence and c.evidence[0].section in ("results", "experiments")
        assert c.evidence[0].shared_numbers


def test_unsupported_claim_is_not_rated_supported(make_pdf):
    p, truth = make_pdf(4, unsupported=1)
    ledger = build_ledger(parse_pdf(p))
    bad = truth.claims[0]
    claim = next(c for c in ledger if bad["number"] in c.text)
    assert claim.support in ("none", "weak")


def test_evidence_never_points_at_the_claim_itself(make_pdf):
    p, _ = make_pdf(5)
    for c in build_ledger(parse_pdf(p)):
        assert all(e.sentence_id != c.sentence_id for e in c.evidence)
        assert all(e.section not in ("abstract", "introduction", "conclusion") for e in c.evidence)


def test_claim_pages_match_truth(make_pdf):
    p, truth = make_pdf(6, unsupported=0)
    ledger = build_ledger(parse_pdf(p))
    for tc in truth.claims:
        c = next(c for c in ledger if tc["number"] in c.text)
        assert c.page == tc["page"]
