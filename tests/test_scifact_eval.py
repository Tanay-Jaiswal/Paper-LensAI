"""Exercises the SciFact evaluation code on a tiny hand-made fixture in the real SciFact file format.
(This validates the code path only; real numbers need the real dataset: see docs/EVALUATION.md.)"""
import json

from scifact_eval import auroc, run


def test_auroc_basic():
    assert auroc([0.9, 0.8], [0.1, 0.2]) == 1.0
    assert auroc([0.1], [0.9]) == 0.0
    assert auroc([0.5], [0.5]) == 0.5


def test_run_on_fixture(tmp_path):
    corpus = [
        {"doc_id": 1, "title": "Aspirin trial", "abstract": [
            "We enrolled 200 patients in a randomised study.",
            "Aspirin reduced the risk of stroke by 25% compared with placebo.",
            "Side effects were mild."]},
        {"doc_id": 2, "title": "Unrelated", "abstract": ["Rocks are hard.", "Volcanoes erupt."]},
    ]
    claims = [
        {"id": 1, "claim": "Aspirin reduces stroke risk by 25%.", "cited_doc_ids": [1],
         "evidence": {"1": [{"sentences": [1], "label": "SUPPORT"}]}},
        {"id": 2, "claim": "Volcano chemistry predicts moon tides.", "cited_doc_ids": [2], "evidence": {}},
    ]
    (tmp_path / "corpus.jsonl").write_text("\n".join(json.dumps(x) for x in corpus))
    (tmp_path / "claims_dev.jsonl").write_text("\n".join(json.dumps(x) for x in claims))
    r = run(tmp_path)
    assert r["rationale_selection"]["paperlens"]["hit@1"] == 1.0
    assert r["evidence_gap_detection"]["auroc_evidence_present_vs_NEI"] == 1.0
    assert r["abstract_retrieval_bm25"]["recall@10"] == 1.0
