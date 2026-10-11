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
