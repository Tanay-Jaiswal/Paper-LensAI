import pymupdf
import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens.cli import main
from paperlens.models import Gap
from paperlens.pipeline import analyze_pdf
from paperlens.revisions import revision_checklist
from paperlens.scorecard import build_scorecard, evidence_score, grade_of, to_scorecard_html, to_scorecard_pdf


@pytest.mark.parametrize("points,grade", [(100, "A"), (80, "A"), (79.9, "B"), (65, "B"), (50, "C"), (35, "D"),
                                          (34.9, "E"), (0, "E")])
def test_grade_cut_points(points, grade):
    assert grade_of(points) == grade


def test_points_follow_the_printed_formula(make_pdf):
    a = analyze_pdf(make_pdf(1)[0])
    c = build_scorecard(a)
    p = c["parts"]
    ev = evidence_score(a)
    base = p["checklist_score"] if ev is None else 0.7 * p["checklist_score"] + 0.3 * ev
    assert p["penalty"] == min(15, 5 * p["numbers_not_adding_up"] + 2 * p["high_severity_gaps"])
    assert c["points"] == round(max(0, base - p["penalty"]), 1)
    assert c["grade"] == grade_of(c["points"])


def test_top_three_are_the_first_revision_items(make_pdf):
    a = analyze_pdf(make_pdf(23, items={"hyper": True, "metrics": True}, unsupported=1,
                             add_gaps=("overclaim_sota",))[0])
    rev = revision_checklist(a)
    c = build_scorecard(a)
    assert len(rev) >= 3
    assert [t["fix"] for t in c["top"]] == [x["action"] for x in rev[:3]]
    assert [t["problem"] for t in c["top"]] == [x["why"] for x in rev[:3]]


def test_penalty_is_capped(make_pdf):
    a = analyze_pdf(make_pdf(1)[0])
    a.gaps = [Gap(f"G{i}", "unsupported_claim", "high", "x") for i in range(9)]
    assert build_scorecard(a)["parts"]["penalty"] == 15


def test_unreadable_pdf_is_not_graded(tmp_path):
    d = pymupdf.open()
    d.new_page()
    p = tmp_path / "blank.pdf"
    d.save(p)
    c = build_scorecard(analyze_pdf(p))
    assert c["grade"] == "n/a" and c["points"] is None and c["top"] == []
    assert "Not graded" in to_scorecard_html(analyze_pdf(p))


def test_html_and_pdf_render_the_card(make_pdf):
    a = analyze_pdf(make_pdf(2)[0])
    c = build_scorecard(a)
    page = to_scorecard_html(a)
    assert "<script" not in page and c["grade"] in page and "Top 3 problems" in page
    doc = pymupdf.open(stream=to_scorecard_pdf(a), filetype="pdf")
    text = doc[0].get_text()
    assert len(doc) == 1 and "Reporting grade" in text and c["top"][0]["fix"][:30] in text.replace("\n", " ")


def test_scorecard_api_and_cli(tmp_path, monkeypatch, make_pdf):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    api._cache.clear()
    client = TestClient(api.app)
    p, _ = make_pdf(1)
    aid = client.post("/api/analyze", files={"file": ("a.pdf", p.read_bytes())}).json()["id"]
    j = client.get(f"/api/analyses/{aid}").json()
    assert j["scorecard"]["grade"] in "ABCDE"
    assert client.get(f"/api/analyses/{aid}/scorecard.json").json()["grade"] == j["scorecard"]["grade"]
    assert client.get(f"/api/analyses/{aid}/scorecard.html").text.startswith("<!doctype html>")
    r = client.get(f"/api/analyses/{aid}/scorecard.pdf")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert client.get(f"/api/analyses/{aid}/scorecard.doc").status_code == 404
    out = tmp_path / "out"
    assert main(["analyze", str(p), "--out", str(out)]) == 0
    assert (out / "paper1.scorecard.pdf").read_bytes()[:4] == b"%PDF"
    assert "Reporting grade" in (out / "paper1.scorecard.html").read_text(encoding="utf-8")
