import pymupdf
import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens.cli import main
from paperlens.models import Gap
from paperlens.pipeline import analyze_pdf
from paperlens.review import MAX_QUESTIONS, MAX_STRENGTHS, MAX_WEAKNESSES, build_review, to_review_html, \
    to_review_markdown


@pytest.fixture
def weak_paper(make_pdf):
    return analyze_pdf(make_pdf(23, items={"hyper": True, "metrics": True}, unsupported=1,
                                add_gaps=("overclaim_sota",))[0])


def test_every_point_comes_from_an_existing_finding(weak_paper):
    a = weak_paper
    r = build_review(a)
    assert r["assessed"] and r["weaknesses"] and r["questions"]
    gap_ids = {g.id for g in a.gaps}
    repro_keys = {i["key"] for i in a.rubric["items"]}
    claim_ids = {c.id for c in a.claims}
    for p in r["strengths"] + r["weaknesses"] + r["questions"]:
        kind, _, ident = p["key"].partition(":")
        assert kind in ("gap", "repro", "claim", "number", "reference"), p
        if kind == "gap":
            assert ident in gap_ids
        elif kind == "repro":
            assert ident in repro_keys
        elif kind == "claim":
            assert ident in claim_ids
        assert p["source"]
    assert len(r["strengths"]) <= MAX_STRENGTHS and len(r["weaknesses"]) <= MAX_WEAKNESSES
    assert len(r["questions"]) <= MAX_QUESTIONS
    assert "No language model" in r["method"] and "accepted" in r["limits"]


def test_strengths_are_reported_items_and_strong_claims(make_pdf):
    a = analyze_pdf(make_pdf(11)[0])          # a well-documented synthetic paper
    r = build_review(a)
    present = {i["key"] for i in a.rubric["items"] if i["status"] == "present"}
    for p in r["strengths"]:
        if p["key"].startswith("repro:"):
            assert p["key"][6:] in present and p["page"]
        if p["key"].startswith("claim:"):
            assert next(c for c in a.claims if c.id == p["key"][6:]).support == "strong"
    assert r["strengths"]


def test_weaknesses_ordered_by_severity_and_not_duplicated(weak_paper):
    a = weak_paper
    a.gaps = a.gaps + [Gap("G90", "superlative_unsupported", "medium", "Superlative claim with no comparison.", 3),
                       Gap("G91", "superlative_unsupported", "medium", "Superlative claim with no comparison.", 5),
                       Gap("G92", "no_code", "high", "No code or implementation link is given.")]
    r = build_review(a)
    sev = {"high": 0, "medium": 1, "low": 2, "": 3}
    order = [sev[p["severity"]] for p in r["weaknesses"]]
    assert order == sorted(order)
    texts = [p["text"] for p in r["weaknesses"]]
    assert sum("Superlative claim with no comparison" in t for t in texts) <= 1     # merged into one point
    assert not any("No code or implementation link" in t for t in texts)          # covered by the checklist item
    assert len({q["text"] for q in r["questions"]}) == len(r["questions"])


def test_same_paper_same_review(weak_paper):
    assert to_review_markdown(weak_paper) == to_review_markdown(weak_paper)


def test_unreadable_pdf_gets_no_review(tmp_path):
    d = pymupdf.open()
    d.new_page()
    p = tmp_path / "blank.pdf"
    d.save(p)
    r = build_review(analyze_pdf(p))
    assert not r["assessed"] and r["strengths"] == r["weaknesses"] == r["questions"] == []
    assert "no review could be drafted" in to_review_markdown(analyze_pdf(p))


def test_renderings(weak_paper):
    md = to_review_markdown(weak_paper)
    assert md.startswith("# Review draft") and "## Questions for the authors" in md
    page = to_review_html(weak_paper)
    assert "<script" not in page and "Strengths" in page


def test_review_api_and_cli(tmp_path, monkeypatch, make_pdf, capsys):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    api._cache.clear()
    client = TestClient(api.app)
    p, _ = make_pdf(2)
    aid = client.post("/api/analyze", files={"file": ("a.pdf", p.read_bytes())}).json()["id"]
    assert client.get(f"/api/analyses/{aid}/review.json").json()["title"]
    assert client.get(f"/api/analyses/{aid}/review.md").text.startswith("# Review draft")
    assert "Review draft" in client.get(f"/api/analyses/{aid}/review.html").text
    assert client.get(f"/api/analyses/{aid}/review.pdf").status_code == 404
    assert client.post(f"/api/analyses/{aid}/feedback", json={"target": "review:W1", "vote": "up"}).status_code == 200
    out = tmp_path / "r.md"
    assert main(["review", str(p), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# Review draft")
    assert "# Review draft" in capsys.readouterr().out
    assert main(["analyze", str(p), "--out", str(tmp_path / "rep")]) == 0
    assert (tmp_path / "rep" / "paper2.review.md").exists()
