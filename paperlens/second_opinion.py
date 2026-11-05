"""Optional AI second opinion for evidence written in other words (off by default).

The rule-based ledger matches claims to evidence by shared wording and numbers, so a passage that supports a claim in
different words can be missed ("no evidence found" or "weak"). When the person running PaperLens turns this on, a
reader can ask a language model (Claude, through the Anthropic API) to look at the claim and the closest passages the
rules already ranked, and say whether any of them supports the claim.

Guarantees:
* Off unless the server is started with PAPERLENS_AI_SECOND_OPINION=1 and the `anthropic` package is installed
  (requirements-ai.txt). Each request is made only when a reader clicks the button for one claim.
* It never changes the rule-based rating, the score card, the checklist or any report: the answer is shown next to
  the claim, labelled "AI-assisted", and stored separately (second_opinion.json in the analysis folder).
* The model can only point at passages by number. The quotes shown are PaperLens's own copies of the paper's
  sentences, so no generated text is presented as a quote from the paper; an answer that names a passage that was not
  offered is discarded.
* What is sent: the claim sentence and up to MAX_PASSAGES sentences from the paper, nothing else.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .claims import CLAIM_ZONE, _eligible_evidence, evidence_unsuitable, rank_passages
from .textutils import quantities_in, tokenize

ENV_FLAG = "PAPERLENS_AI_SECOND_OPINION"
ENV_MODEL = "PAPERLENS_AI_MODEL"
DEFAULT_MODEL = "claude-opus-5-5"
MAX_PASSAGES = 8
FILE = "second_opinion.json"
LABEL = "AI-assisted second opinion (not part of the rule-based rating)"
VERDICTS = ("supported", "partly_supported", "not_supported")
# reasons a candidate is not even worth showing to the model (a fragment, a licence line, an equation)
_SKIP = {"fragment", "boilerplate", "symbols_or_numbers", "caption_label_only"}

SYSTEM = ("You check whether passages from a research paper support a claim made in the same paper. Judge only from "
          "the passages given. A passage supports the claim if it reports the result, number or finding the claim "
          "states, even in different words. Background, motivation, or a restatement of the claim without results "
          "is not support. If no passage supports the claim, say so. Refer to passages only by their numbers.")

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": list(VERDICTS)},
        "supporting_passages": {"type": "array", "items": {"type": "integer"}},
        "explanation": {"type": "string"},
    },
    "required": ["verdict", "supporting_passages", "explanation"],
    "additionalProperties": False,
}


def status() -> dict:
    """Whether the feature can be used on this server, and why not."""
    if os.environ.get(ENV_FLAG, "") != "1":
        return {"enabled": False, "reason": f"Off. The person running PaperLens can turn it on by starting the server "
                                           f"with {ENV_FLAG}=1 (see docs/AI_SECOND_OPINION.md)."}
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return {"enabled": False, "reason": "Turned on, but the 'anthropic' package is not installed "
                                           "(pip install -r requirements-ai.txt)."}
    return {"enabled": True, "model": os.environ.get(ENV_MODEL, DEFAULT_MODEL), "label": LABEL,
            "sends": f"the claim and up to {MAX_PASSAGES} sentences of the paper"}


def candidates(analysis, claim) -> list:
    """The passages offered to the model: the best-ranked body sentences for the claim, including ones the rules
    rejected as too different in wording (the case this feature is for), minus fragments and boilerplate."""
    doc = analysis.doc
    pool = [s for s in _eligible_evidence(doc, claim, frozenset(c.sentence_id for c in analysis.claims))
            if s.section not in CLAIM_ZONE]
    ctoks = set(tokenize(claim.text))
    cvals = {q.value for q in quantities_in(claim.text)}
    out = []
    for total, lex, shared, s, _terms in rank_passages(claim.text, claim.numbers, pool):
        if evidence_unsuitable(s, ctoks, cvals, shared, lex) in _SKIP:
            continue
        out.append(s)
        if len(out) == MAX_PASSAGES:
            break
    return out


def build_prompt(claim_text: str, passages: list) -> str:
    lines = [f"Claim: {claim_text}", "", "Passages:"]
    lines += [f"[{i}] (page {s.page}, {s.section}) {s.text}" for i, s in enumerate(passages, 1)]
    lines += ["", "Which passages, if any, support the claim? Answer in the required JSON format."]
    return "\n".join(lines)


def _client():
    import anthropic
    return anthropic.Anthropic()


def ask(analysis, claim_id: str, client=None) -> dict:
    """Ask the model about one claim. Raises KeyError for an unknown claim, RuntimeError when the feature is off or
    the call fails (the message says why)."""
    st = status()
    if not st["enabled"] and client is None:
        raise RuntimeError(st["reason"])
    claim = next((c for c in analysis.claims if c.id == claim_id), None)
    if claim is None:
        raise KeyError(claim_id)
    passages = candidates(analysis, claim)
    model = os.environ.get(ENV_MODEL, DEFAULT_MODEL)
    base = {"claim_id": claim.id, "claim": claim.text, "rule_based_support": claim.support, "label": LABEL,
            "model": model, "version": __version__,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "n_passages_sent": len(passages)}
    if not passages:
        return {**base, "verdict": "not_checked", "explanation": "No body passage could be offered for this claim.",
                "supporting": []}
    client = client or _client()
    try:
        import anthropic
        errors = (anthropic.AnthropicError,)
    except ImportError:          # only in tests that pass a fake client
        errors = ()
    try:
        resp = client.beta.messages.create(
            model=model, max_tokens=2000, system=SYSTEM,
            messages=[{"role": "user", "content": build_prompt(claim.text, passages)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        )
    except errors as e:          # authentication, rate limit, network ... reported, never retried silently
        raise RuntimeError(f"The AI request failed: {type(e).__name__}: {getattr(e, 'message', e)}") from e
    except TypeError as e:       # the SDK raises TypeError when no API key or other credential is configured
        if "authentication" not in str(e):
            raise
        raise RuntimeError("The AI request failed: no Anthropic API key is configured on this server "
                           "(set ANTHROPIC_API_KEY before starting PaperLens).") from e
    if resp.stop_reason == "refusal":
        return {**base, "verdict": "not_checked", "explanation": "The model declined to answer.", "supporting": []}
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    try:
        data = json.loads(text)
        verdict = data["verdict"]
        picked = [int(i) for i in data["supporting_passages"]]
        explanation = str(data["explanation"])[:800]
    except (ValueError, KeyError, TypeError):
        return {**base, "verdict": "not_checked", "explanation": "The model's answer could not be read.",
                "supporting": []}
    if verdict not in VERDICTS or any(not 1 <= i <= len(passages) for i in picked):
        return {**base, "verdict": "not_checked",
                "explanation": "The answer referred to passages that were not offered, so it was discarded.",
                "supporting": []}
    if verdict == "not_supported":
        picked = []
    supporting = [{"passage": i, "sentence_id": passages[i - 1].id, "page": passages[i - 1].page,
                   "section": passages[i - 1].section, "quote": passages[i - 1].text,
                   "also_found_by_rules": any(e.sentence_id == passages[i - 1].id for e in claim.evidence)}
                  for i in dict.fromkeys(picked)]
    return {**base, "verdict": verdict, "explanation": explanation, "supporting": supporting}


def load(d: Path) -> dict:
    f = d / FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except ValueError:
        return {}


def save(d: Path, result: dict) -> dict:
    data = load(d)
    data[result["claim_id"]] = result
    tmp = d / (FILE + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / FILE)
    return data
