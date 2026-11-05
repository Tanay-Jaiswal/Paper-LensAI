import json

import pytest
from fastapi.testclient import TestClient

from paperlens import __version__, api
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


def test_reuploaded_pdf_moves_to_the_top_of_the_recent_list(client, make_pdf):
    # a re-upload rewrites files inside the folder, which does not change the folder's own mtime on Windows (NTFS),
    # so the paper stayed far down "Analysed earlier" and demo step 7 could not find it
    import os, time
    raw_a, raw_b = make_pdf(1)[0].read_bytes(), make_pdf(2)[0].read_bytes()
    a = client.post("/api/analyze", files={"file": ("a.pdf", raw_a)}).json()["id"]
    b = client.post("/api/analyze", files={"file": ("b.pdf", raw_b)}).json()["id"]
    for restarted in (False, True):
        now = time.time()
        os.utime(api.DATA_DIR / a, (now - 100, now - 100)); os.utime(api.DATA_DIR / b, (now - 50, now - 50))
        assert client.get("/api/analyses").json()[0]["id"] == b
        if restarted:
            api._cache.clear()
        client.post("/api/analyze", files={"file": ("a.pdf", raw_a)})
        assert client.get("/api/analyses").json()[0]["id"] == a


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
    assert j["version"] == __version__
    assert sum(j["ledger_stats"]["evidence_status"].values()) == j["ledger_stats"]["n_claims"]
    for c in j["ledger"]:
        assert c["evidence_status"] in ("found", "no_supporting_evidence", "no_searchable_text")
        assert bool(c["evidence"]) == (c["evidence_status"] == "found")
        assert (c["evidence_note"] == "") == bool(c["evidence"])


def test_cli_reports_bad_input_in_one_line_with_exit_code_2(tmp_path, capsys):
    txt = tmp_path / "notes.pdf"; txt.write_text("not a pdf")
    broken = tmp_path / "broken.pdf"; broken.write_bytes(b"%PDF-1.4 not really")
    for bad in (tmp_path / "missing.pdf", txt, broken):
        assert main(["analyze", str(bad), "--out", str(tmp_path / "o")]) == 2
    assert main(["compare", str(txt), str(broken), "--out", str(tmp_path / "o")]) == 2
    err = capsys.readouterr().err
    assert "file not found" in err and "not a PDF" in err and "could not read" in err and "Traceback" not in err


def test_html_report_is_standalone_and_escapes_paper_text(client, make_pdf):
    from paperlens.pipeline import analyze_pdf
    from paperlens.report import to_html
    a = analyze_pdf(make_pdf(1)[0])
    a.doc.title = "<script>alert(1)</script>"
    out = to_html(a)
    assert "<script" not in out and "&lt;script&gt;" in out
    assert "Research Evidence Ledger" in out and "Reproducibility checklist" in out


def test_ui_files_are_not_cached_and_health_reports_version(client):
    assert client.get("/static/app.js").headers["cache-control"] == "no-cache"
    assert client.get("/api/health").json() == {"ok": True, "version": __version__}


def test_highlight_falls_back_to_a_run_of_words_when_the_sentence_text_differs_from_the_page():
    import pymupdf
    d = pymupdf.open(); pg = d.new_page()
    pg.insert_text((72, 100), "Published research findings are sometimes refuted by subsequent evidence in later work.")
    # extracted text with a ligature gap, as seen in real papers ("fi ndings"): the full-sentence search finds nothing
    text = "Published research fi ndings are sometimes refuted by subsequent evidence in later work."
    assert pg.search_for(text[:50]) == []
    assert api._find_rects(pg, text), "a later run of words should still locate the sentence"
    assert api._find_rects(pg, "Something that is nowhere on this page at all, really, none of it.") == []


def test_serve_refuses_a_busy_port_with_a_clear_message(capsys):
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); s.listen(1)
        assert main(["serve", "--port", str(s.getsockname()[1])]) == 2
    assert "already in use" in capsys.readouterr().err


def test_mode_is_chosen_on_upload_and_kept_after_restart(client, make_pdf):
    raw = make_pdf(4)[0].read_bytes()
    auto = client.post("/api/analyze", files={"file": ("a.pdf", raw)}).json()
    gen = client.post("/api/analyze", files={"file": ("a.pdf", raw)}, data={"mode": "general"}).json()
    cse = client.post("/api/analyze", files={"file": ("a.pdf", raw)}, data={"mode": "cse"}).json()
    assert len({auto["id"], gen["id"], cse["id"]}) == 3
    assert gen["field"]["field"] == "general" and cse["field"]["field"] == "cse"
    assert any(i["key"].startswith("cs_") for i in cse["reproducibility"]["items"])
    api._cache.clear()                                   # a restart re-analyses from the stored PDF and mode
    assert client.get(f"/api/analyses/{cse['id']}").json()["field"]["mode"] == "cse"
    assert client.post("/api/compare", json={"a": gen["id"], "b": cse["id"]}).json()["verdict"]
    assert "(CS)" in client.get(f"/api/analyses/{cse['id']}/report.md").text
    bad = client.post("/api/analyze", files={"file": ("a.pdf", raw)}, data={"mode": "physics"})
    assert bad.status_code == 400


def test_cli_mode_flag(tmp_path, make_pdf, capsys):
    pdf = make_pdf(5)[0]
    assert main(["analyze", str(pdf), "--out", str(tmp_path), "--mode", "cse"]) == 0
    assert "Computer Science" in capsys.readouterr().out
    assert json.loads((tmp_path / f"{pdf.stem}.json").read_text(encoding="utf-8"))["field"]["field"] == "cse"
