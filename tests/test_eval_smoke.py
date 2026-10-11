from run_eval import run


def test_synthetic_eval_meets_floor():
    """Regression floor on the synthetic benchmark (templated text: a plumbing check, not real-world accuracy)."""
    r = run(20, seed=3)
    assert r["rubric"]["micro_f1"] >= 0.95
    assert r["claims"]["headline_claim_recall"] >= 0.95
    assert r["evidence_linking"]["top1_evidence_hit_rate"] >= 0.95
    assert r["evidence_linking"]["unsupported_rated_none_or_weak"] >= 0.9
