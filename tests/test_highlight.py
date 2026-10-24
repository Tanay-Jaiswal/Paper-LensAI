import pymupdf
import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens.highlight import highlighted_pdf, locate, locate_sentences
from paperlens.models import Sentence
from paperlens.pipeline import analyze_pdf


def _page(text):
    d = pymupdf.open()
    pg = d.new_page()
    pg.insert_textbox((60, 90, 540, 400), text, fontsize=10)
    return d, pg


def test_locate_reports_how_a_sentence_was_found():
    d, pg = _page("The model reaches 91.2 percent accuracy on the held out split of the benchmark data.")
    rects, how = locate(pg, "The model reaches 91.2 percent accuracy on the held out split of the benchmark data.")
    assert rects and how == "exact"
    rects, how = locate(pg, "Completely different opening words here then accuracy on the held out split of the benchmark data.")
    assert rects and how == "partial"
    assert locate(pg, "Nothing like this sentence appears anywhere on the page at all today.") == ([], "none")


def test_locate_sentences_gives_page_fractions(tmp_path):
    d, pg = _page("Our result is 42.0 points on the test set, which is the claim being checked.")
    p = tmp_path / "x.pdf"
    d.save(p)
    out = locate_sentences(p, [Sentence(0, "Our result is 42.0 points on the test set", 1, "results"),
                               Sentence(1, "Missing words nowhere else to be seen", 1, "results"),
                               Sentence(2, "Page out of range", 9, "results")])
    assert out[0]["method"] == "exact" and all(0 <= v <= 1 for v in out[0]["rects"][0])
    assert out[0]["rects"][0][0] < out[0]["rects"][0][2]
    assert out[1]["method"] == "none" and out[1]["rects"] == []
    assert out[2]["method"] == "none"


def test_highlighted_pdf_marks_claim_and_evidence(make_pdf):
    p, _ = make_pdf(1)
    a = analyze_pdf(p)
    c = next(c for c in a.claims if c.evidence)
    data, page, found = highlighted_pdf(p, a, c.id)
    assert page == c.page and found[c.sentence_id] in ("exact", "partial")
    doc = pymupdf.open(stream=data, filetype="pdf")
    notes = [an.info["content"] for pg in doc for an in pg.annots() if an.info["content"]]
    assert any(n.startswith(f"Claim {c.id}") for n in notes)
    assert any(n.startswith(f"Evidence 1 for claim {c.id}") for n in notes)
    with pytest.raises(KeyError):
        highlighted_pdf(p, a, "C999")


def test_locate_and_pdf_endpoints(tmp_path, monkeypatch, make_pdf):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    api._cache.clear()
    client = TestClient(api.app)
    p, _ = make_pdf(2)
    j = client.post("/api/analyze", files={"file": ("a.pdf", p.read_bytes())}).json()
    aid, c = j["id"], next(c for c in j["ledger"] if c["evidence"])
    ids = [c["sentence_id"]] + [e["sentence_id"] for e in c["evidence"]]
    r = client.get(f"/api/analyses/{aid}/locate?ids={','.join(map(str, ids))},999999,x").json()
    assert [x["sentence_id"] for x in r["located"]] == ids
    assert all(x["method"] in ("exact", "partial", "none") for x in r["located"])
    h = client.get(f"/api/analyses/{aid}/highlighted.pdf?claim={c['id']}")
    assert h.status_code == 200 and h.content[:4] == b"%PDF" and "inline" in h.headers["content-disposition"]
    assert client.get(f"/api/analyses/{aid}/highlighted.pdf?claim=C999").status_code == 404
    assert client.get(f"/api/analyses/{aid}/paper.pdf").content == p.read_bytes()
