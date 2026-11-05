"""The optional AI second opinion, tested with a fake client: no network, no API key, no model is ever called."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from paperlens import api
from paperlens import second_opinion as so
from paperlens.pipeline import analyze_pdf


class FakeClient:
    def __init__(self, answer, stop_reason="end_turn"):
        self.answer, self.stop_reason, self.calls = answer, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        text = self.answer if isinstance(self.answer, str) else json.dumps(self.answer)
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def analysis(make_pdf):
    return analyze_pdf(make_pdf(1)[0])


def test_off_by_default(monkeypatch, analysis):
    monkeypatch.delenv(so.ENV_FLAG, raising=False)
    assert so.status()["enabled"] is False
    with pytest.raises(RuntimeError):
        so.ask(analysis, analysis.claims[0].id)


def test_request_shape_and_verified_quotes(analysis):
    c = analysis.claims[0]
    passages = so.candidates(analysis, c)
    assert 0 < len(passages) <= so.MAX_PASSAGES and all(p.id != c.sentence_id for p in passages)
    fake = FakeClient({"verdict": "supported", "supporting_passages": [2, 2], "explanation": "Passage 2 reports it."})
    r = so.ask(analysis, c.id, client=fake)
    kw = fake.calls[0]
    assert kw["model"] == so.DEFAULT_MODEL and kw["output_config"]["format"]["type"] == "json_schema"
    assert c.text in kw["messages"][0]["content"] and passages[1].text in kw["messages"][0]["content"]
    assert r["verdict"] == "supported" and r["label"] == so.LABEL and r["rule_based_support"] == c.support
    assert [x["sentence_id"] for x in r["supporting"]] == [passages[1].id]          # duplicates dropped
    assert r["supporting"][0]["quote"] == passages[1].text                          # PaperLens's own copy
    assert c.support == analysis.claims[0].support                                  # rule-based rating unchanged


@pytest.mark.parametrize("answer,why", [
    ({"verdict": "supported", "supporting_passages": [99], "explanation": "x"}, "not offered"),
    ({"verdict": "maybe", "supporting_passages": [], "explanation": "x"}, "not offered"),
    ("not json at all", "could not be read"),
    ({"verdict": "supported"}, "could not be read"),
])
def test_bad_answers_are_discarded(analysis, answer, why):
    r = so.ask(analysis, analysis.claims[0].id, client=FakeClient(answer))
    assert r["verdict"] == "not_checked" and why in r["explanation"] and r["supporting"] == []


def test_refusal_and_not_supported(analysis):
    r = so.ask(analysis, analysis.claims[0].id, client=FakeClient("", stop_reason="refusal"))
    assert r["verdict"] == "not_checked" and "declined" in r["explanation"]
    r = so.ask(analysis, analysis.claims[0].id,
               client=FakeClient({"verdict": "not_supported", "supporting_passages": [1], "explanation": "No."}))
    assert r["verdict"] == "not_supported" and r["supporting"] == []


def test_unknown_claim(analysis):
    with pytest.raises(KeyError):
        so.ask(analysis, "C999", client=FakeClient({}))


def test_api_off_by_default_and_on_with_fake(tmp_path, monkeypatch, make_pdf):
    monkeypatch.setattr(api, "DATA_DIR", tmp_path / "store")
    monkeypatch.delenv(so.ENV_FLAG, raising=False)
    api._cache.clear()
    client = TestClient(api.app)
    j = client.post("/api/analyze", files={"file": ("a.pdf", make_pdf(1)[0].read_bytes())}).json()
    aid, cid = j["id"], j["ledger"][0]["id"]
    assert client.get("/api/config").json()["ai_second_opinion"]["enabled"] is False
    assert client.post(f"/api/analyses/{aid}/second-opinion", json={"claim": cid}).status_code == 403
    # turned on, with the model call replaced by a fake
    monkeypatch.setenv(so.ENV_FLAG, "1")
    monkeypatch.setattr(so, "status", lambda: {"enabled": True, "model": "fake", "label": so.LABEL, "sends": "x"})
    fake = FakeClient({"verdict": "partly_supported", "supporting_passages": [1], "explanation": "Partly."})
    monkeypatch.setattr(so, "_client", lambda: fake)
    r = client.post(f"/api/analyses/{aid}/second-opinion", json={"claim": cid})
    assert r.status_code == 200 and r.json()["verdict"] == "partly_supported"
    assert client.post(f"/api/analyses/{aid}/second-opinion", json={"claim": "C999"}).status_code == 404
    stored = client.get(f"/api/analyses/{aid}/second-opinion").json()
    assert stored[cid]["verdict"] == "partly_supported"
    # the rule-based analysis and its reports are untouched
    assert client.get(f"/api/analyses/{aid}").json()["ledger"] == j["ledger"]
    assert "AI" not in client.get(f"/api/analyses/{aid}/report.md").text.split("## Summary")[0]


def test_missing_api_key_is_a_clear_error(analysis, monkeypatch):
    class NoKey(FakeClient):
        def _create(self, **kw):
            raise TypeError('"Could not resolve authentication method. Expected one of api_key ..."')
    with pytest.raises(RuntimeError, match="no Anthropic API key"):
        so.ask(analysis, analysis.claims[0].id, client=NoKey({}))
