import json

import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens.cli import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    api._cache.clear()
    return TestClient(api.app)


def test_upload_analyse_page_report_compare(client, make_pdf):
    p1, _ = make_pdf(1)
    p2, _ = make_pdf(2, unsupported=1)
    r1 = client.post("/api/analyze", files={"file": ("a.pdf", p1.read_bytes(), "application/pdf")})
    r2 = client.post("/api/analyze", files={"file": ("b.pdf", p2.read_bytes(), "application/pdf")})
    assert r1.status_code == 200 and r1.json()["ledger"]
    a, b = r1.json()["id"], r2.json()["id"]
    assert client.get(f"/api/analyses/{a}").json()["reproducibility"]["score"] > 0
    img = client.get(f"/api/analyses/{a}/page/1.png?highlight=1,2")
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"
    assert client.get(f"/api/analyses/{a}/page/99.png").status_code == 404
    assert "Evidence Ledger" in client.get(f"/api/analyses/{a}/report.md").text
    assert client.get(f"/api/analyses/{a}/report.json").json()["id"] == a
    cmp = client.post("/api/compare", json={"a": a, "b": b}).json()
    assert cmp["verdict"]
    assert len(client.get("/api/analyses").json()) == 2


def test_rejects_non_pdf_and_bad_ids(client):
    assert client.post("/api/analyze", files={"file": ("x.pdf", b"hello", "application/pdf")}).status_code == 400
    assert client.get("/api/analyses/../../etc/passwd").status_code in (400, 404)
    assert client.get("/api/analyses/ZZZ").status_code == 400
    assert client.get("/api/analyses/aaaaaaaaaaaaaaaa").status_code == 404


def test_same_pdf_is_deduplicated(client, make_pdf):
    raw = make_pdf(3)[0].read_bytes()
    ids = {client.post("/api/analyze", files={"file": ("a.pdf", raw)}).json()["id"] for _ in range(2)}
    assert len(ids) == 1


def test_cli_analyze_and_compare(tmp_path, make_pdf, capsys):
    p1, _ = make_pdf(1); p2, _ = make_pdf(2)
    out = tmp_path / "out"
    assert main(["analyze", str(p1), "--out", str(out)]) == 0
    assert json.loads((out / "paper1.json").read_text())["ledger"]
    assert (out / "paper1.md").read_text().startswith("# PaperLens report")
    assert main(["compare", str(p1), str(p2), "--out", str(out)]) == 0
    assert (out / "comparison.json").exists()


def _raw_pdf(text=None):
    import pymupdf
    d = pymupdf.open()
    pg = d.new_page()
    if text:
        pg.insert_textbox((60, 90, 540, 300), text, fontsize=10)
    return d.tobytes()


def test_unreadable_pdf_is_reported_as_unreadable_not_as_a_poor_paper(client, make_pdf):
    # synthetic: a PDF with one empty page stands in for a scanned paper
    r = client.post("/api/analyze", files={"file": ("scan.pdf", _raw_pdf(), "application/pdf")})
    assert r.status_code == 200
    j = r.json()
    assert any("scanned" in w for w in j["document"]["warnings"])
    assert j["reproducibility"]["band"] == "not assessed" and j["reproducibility"]["disclaimer"].startswith("Not assessed")
    assert [g["kind"] for g in j["gaps"]] == ["document_unreadable"]
    assert j["ledger"] == []
    assert "document_unreadable" in client.get(f"/api/analyses/{j['id']}/report.md").text
    good = client.post("/api/analyze", files={"file": ("a.pdf", make_pdf(1)[0].read_bytes(), "application/pdf")}).json()
    cmp = client.post("/api/compare", json={"a": j["id"], "b": good["id"]}).json()
    assert len(cmp["verdict"]) == 1 and "could not be read" in cmp["verdict"][0] and "Paper A" in cmp["verdict"][0]


def test_corrupt_encrypted_and_odd_requests_fail_cleanly(client, make_pdf):
    import pymupdf
    assert client.post("/api/analyze", files={"file": ("x.pdf", b"%PDF-1.4 not really", "application/pdf")}).status_code == 422
    d = pymupdf.open(); d.new_page()
    locked = d.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="synthetic", owner_pw="synthetic2")
    assert client.post("/api/analyze", files={"file": ("x.pdf", locked, "application/pdf")}).status_code == 422
    assert client.post("/api/analyze", files={"file": ("x.pdf", b"", "application/pdf")}).status_code == 400
    a = client.post("/api/analyze", files={"file": ("a.pdf", make_pdf(1)[0].read_bytes(), "application/pdf")}).json()["id"]
    assert client.get(f"/api/analyses/{a}/page/1.png?highlight=0,abc,99999&zoom=nan").status_code == 200
    assert client.get(f"/api/analyses/{a}/page/0.png").status_code == 404
    assert client.get(f"/api/analyses/{a}/report.xml").status_code == 404
    assert client.post("/api/compare", json={"a": a, "b": "aaaaaaaaaaaaaaaa"}).status_code == 404
    assert client.post("/api/compare", json={"a": a}).status_code == 422
    assert client.post("/api/compare", json={"a": a, "b": a}).status_code == 200


def test_ledger_json_served_by_the_api_has_the_evidence_status_fields(client, make_pdf):
    j = client.post("/api/analyze", files={"file": ("b.pdf", make_pdf(2, unsupported=1)[0].read_bytes(), "application/pdf")}).json()
    assert j["version"] == "0.5.1-dev"
    assert sum(j["ledger_stats"]["evidence_status"].values()) == j["ledger_stats"]["n_claims"]
    for c in j["ledger"]:
        assert c["evidence_status"] in ("found", "no_supporting_evidence", "no_searchable_text")
        assert bool(c["evidence"]) == (c["evidence_status"] == "found")
        assert (c["evidence_note"] == "") == bool(c["evidence"])
