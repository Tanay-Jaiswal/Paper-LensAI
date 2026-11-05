import csv
import io

import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens import feedback as fb


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    api._cache.clear()
    return TestClient(api.app)


def test_record_clear_and_summary(tmp_path):
    d = tmp_path / "abc"
    d.mkdir()
    assert fb.load(d) == {}
    fb.record(d, "claim:C1", "up", text="strong: our method wins")
    fb.record(d, "gap:G2", "down", note="the test is reported on p.6")
    data = fb.record(d, "repro:cs_code_link", "up")
    assert data["claim:C1"]["vote"] == "up" and data["claim:C1"]["text"] == "strong: our method wins"
    assert data["gap:G2"]["note"].startswith("the test")
    assert fb.summary(data) == {"up": 2, "down": 1, "by_kind": {"claim": {"up": 1, "down": 0},
                                                                "gap": {"up": 0, "down": 1},
                                                                "repro": {"up": 1, "down": 0}}}
    data = fb.record(d, "claim:C1", "clear")
    assert "claim:C1" not in data and "claim:C1" not in fb.load(d)


@pytest.mark.parametrize("target", ["", "claim", "claim:", "other:C1", "claim:C1;rm", "claim:" + "x" * 65,
                                    "../claim:C1"])
def test_rejects_bad_targets(tmp_path, target):
    with pytest.raises(ValueError):
        fb.record(tmp_path, target, "up")


def test_rejects_bad_vote_and_survives_damaged_file(tmp_path):
    with pytest.raises(ValueError):
        fb.record(tmp_path, "claim:C1", "maybe")
    (tmp_path / fb.FILE).write_text("{not json", encoding="utf-8")
    assert fb.load(tmp_path) == {}
    assert fb.record(tmp_path, "claim:C1", "up")["claim:C1"]["vote"] == "up"


def test_feedback_api_roundtrip_and_csv(client, make_pdf):
    raw = make_pdf(1)[0].read_bytes()
    aid = client.post("/api/analyze", files={"file": ("paper one.pdf", raw)}).json()["id"]
    assert client.get(f"/api/analyses/{aid}/feedback").json() == {"votes": {}, "summary": {"up": 0, "down": 0,
                                                                                          "by_kind": {}}}
    r = client.post(f"/api/analyses/{aid}/feedback", json={"target": "claim:C1", "vote": "down", "text": "x"})
    assert r.status_code == 200 and r.json()["summary"]["down"] == 1
    assert client.post(f"/api/analyses/{aid}/feedback", json={"target": "bad", "vote": "up"}).status_code == 400
    assert client.post("/api/analyses/aaaaaaaaaaaaaaaa/feedback", json={"target": "claim:C1", "vote": "up"}).status_code == 404
    # the vote is on disk, so it survives a restart (cache cleared)
    api._cache.clear()
    assert client.get(f"/api/analyses/{aid}/feedback").json()["votes"]["claim:C1"]["vote"] == "down"
    rows = list(csv.DictReader(io.StringIO(client.get("/api/feedback.csv").text)))
    assert rows == [{**rows[0], "analysis_id": aid, "paper": "paper one.pdf", "finding": "claim:C1", "kind": "claim",
                     "vote": "down", "finding_text": "x"}]
