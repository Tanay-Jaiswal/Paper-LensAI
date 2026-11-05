from conftest import ALL, NONE
from paperlens.compare import compare
from paperlens.pipeline import analyze_pdf


def kinds(a):
    return {g.kind for g in a.gaps}


def test_planted_unsupported_claim_and_missing_artifacts_flagged(make_pdf):
    a = analyze_pdf(make_pdf(1, NONE, unsupported=1)[0])
    assert {"unsupported_claim", "no_code", "no_limitations", "no_hyperparameters"} <= kinds(a)
    assert all(g.quote or g.claim_id is None for g in a.gaps)


def test_sota_without_baselines_flagged(make_pdf):
    a = analyze_pdf(make_pdf(2, NONE, unsupported=0, add_gaps=("overclaim_sota",))[0])
    assert "superlative_without_baselines" in kinds(a)


def test_significance_without_test_only_when_test_missing(make_pdf):
    bad = analyze_pdf(make_pdf(3, NONE, unsupported=0, add_gaps=("overclaim_significant",))[0])
    ok = analyze_pdf(make_pdf(3, ALL, unsupported=0, add_gaps=("overclaim_significant",))[0])
    assert "significance_without_test" in kinds(bad) and "significance_without_test" not in kinds(ok)


def test_clean_complete_paper_has_no_high_severity_gaps(make_pdf):
    a = analyze_pdf(make_pdf(4, ALL, unsupported=0)[0])
    assert not [g for g in a.gaps if g.severity == "high"]


def test_compare_prefers_better_documented_paper(make_pdf):
    good = analyze_pdf(make_pdf(5, ALL, unsupported=0)[0])
    bad = analyze_pdf(make_pdf(6, NONE, unsupported=1, add_gaps=("overclaim_sota",))[0])
    c = compare(good, bad)
    assert c["a"]["repro_score"] > c["b"]["repro_score"]
    assert c["a"]["high_gaps"] < c["b"]["high_gaps"]
    assert any("Paper A" in v or "paper A" in v for v in c["verdict"])
    assert "caveat" in c


def test_compare_aligns_same_paper_with_itself(make_pdf):
    a = analyze_pdf(make_pdf(7, ALL, unsupported=0)[0])
    c = compare(a, a)
    assert len(c["aligned_claims"]) == len(a.claims) and not c["only_a_claims"]
