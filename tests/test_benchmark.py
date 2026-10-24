import json

import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens.benchmark import REFERENCE_FILE, _percentile, compare_to_set, load_reference, profile


def _p(title, score, items, ev=None):
    return {"title": title, "name": title + ".pdf", "score": score, "standard_score": score, "items": items,
            "labels": {k: k.title() for k in items}, "evidence_score": ev, "grade": "C", "high_gaps": 0}


def test_percentile_counts_ties_as_half():
    assert _percentile(50, [10, 20, 30, 40]) == 100
    assert _percentile(5, [10, 20]) == 0
    assert _percentile(20, [10, 20, 30, 40]) == 38       # 1 below + half of 1 tie, of 4
    assert _percentile(1, []) == 0


def test_compare_to_set_items_and_notes():
    me = _p("me", 60, {"code": "missing", "seeds": "present", "cs_hardware": "present", "hyper": "not_applicable"})
    others = [_p(f"o{i}", s, {"code": "present", "seeds": "missing", "cs_hardware": "partial" if i == 0 else "missing",
                              "hyper": "present"}) for i, s in enumerate([40, 50, 70, 80])]
    r = compare_to_set(me, others, "test set")
    assert r["n"] == 4 and r["score"]["percentile"] == 50 and r["score"]["median"] == 60 and r["score"]["rank"] == 3
    by = {i["key"]: i for i in r["items"]}
    assert by["code"]["set_reporting_share"] == 100 and by["code"]["note"].startswith("Most papers")
    assert by["seeds"]["set_reporting_share"] == 0 and by["seeds"]["note"].startswith("Few papers")
    assert by["cs_hardware"]["set_reporting_share"] == 25 and by["cs_hardware"]["cs"]
    assert by["hyper"]["note"] == ""                    # not applicable to this paper: no comparison note
    assert r["items"][0]["note"]                        # differences are listed first
    assert "warning" in r                               # 4 papers is too few for a percentile


def test_profile_rejects_general_and_unreadable():
    base = {"document": {"title": "t", "source_name": "t.pdf"}, "gaps": [],
            "reproducibility": {"field": "general", "band": "low", "score": 10, "items": []}}
    assert profile(base) is None
    base["reproducibility"].update(field="cse", band="not assessed")
    assert profile(base) is None
    base["reproducibility"]["band"] = "low"
    assert profile(base)["score"] == 10
    assert profile({"nonsense": 1}) is None


def test_builtin_reference_set_is_development_only():
    ref = load_reference()
    assert REFERENCE_FILE.exists() and ref["n"] == len(ref["papers"]) >= 10
    import csv
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    protected = set()
    for m in ["data/held_out_papers/MANIFEST.csv", "data/held_out_v0.2_papers/MANIFEST.csv",
              "data/cse_check2_papers/MANIFEST.csv"]:
        with (root / m).open(encoding="utf-8-sig") as fh:
            protected |= {r["filename"] for r in csv.DictReader(fh)}
    names = {p["name"] for p in ref["papers"]}
    assert not names & protected
    assert all("quote" not in json.dumps(p) for p in ref["papers"])       # no paper text is stored


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    api._cache.clear()
    return TestClient(api.app)


def test_benchmark_api(client, make_pdf):
    ids = []
    for seed in (1, 2, 3):
        raw = make_pdf(seed)[0].read_bytes()
        ids.append(client.post("/api/analyze", files={"file": (f"p{seed}.pdf", raw)}, data={"mode": "cse"}).json()["id"])
    r = client.get(f"/api/analyses/{ids[0]}/benchmark").json()
    assert r["available"] and r["n"] >= 10 and 0 <= r["score"]["percentile"] <= 100
    mine = client.get(f"/api/analyses/{ids[0]}/benchmark?set=mine").json()
    assert mine["available"] and mine["n"] == 2 and {p["id"] for p in mine["papers"]} == set(ids[1:])
    assert client.get(f"/api/analyses/{ids[0]}/benchmark?set=other").status_code == 400
    gen = client.post("/api/analyze", files={"file": ("g.pdf", make_pdf(4)[0].read_bytes())},
                      data={"mode": "general"}).json()["id"]
    r = client.get(f"/api/analyses/{gen}/benchmark").json()
    assert not r["available"] and "Computer Science" in r["reason"]
