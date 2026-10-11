"""Evidence-gap detection.

A gap is a specific, checkable shortfall between what a paper asserts and what
it shows. Every gap cites a claim or page and states the rule that fired, so
it can be reviewed rather than trusted. Rules are deliberately conservative;
they flag *candidate* weaknesses for a human reviewer.
"""
from __future__ import annotations

import re

from .claims import GENERAL_RE, SUPER_RE
from .models import Claim, Document, Gap
from .textutils import numbers_in

SIGNIF_RE = re.compile(r"\bsignificant(ly)?\b", re.I)
IMPROVE_RE = re.compile(r"\b(outperform\w*|improv\w+|better|gain|surpass\w*|exceed\w*|boost\w*|reduc\w+)\b", re.I)
DATASET_PAT = re.compile(r"\b(?:on|using|across|over)\s+(?:the\s+)?([A-Z][A-Za-z0-9\-/\.]{2,}(?:\s?[A-Z0-9][A-Za-z0-9\-]*)?)")


def _quote(t: str) -> str:
    return t if len(t) <= 220 else t[:217] + "..."


def detect_gaps(doc: Document, claims: list[Claim], rubric: dict) -> list[Gap]:
    gaps: list[Gap] = []
    n = 0

    def add(kind, sev, msg, page=None, claim=None, quote=""):
        nonlocal n
        n += 1
        gaps.append(Gap(f"G{n}", kind, sev, msg, page, claim.id if claim else None, _quote(quote)))

    status = {i["key"]: i["status"] for i in rubric["items"]}
    body_text = " ".join(s.text for s in doc.sentences if s.section in ("experiments", "results", "discussion"))
    body_nums = set(numbers_in(body_text))

    for c in claims:
        if c.claim_type in ("contribution",) and not c.numbers:
            continue
        # 1. unsupported quantitative / comparative claims
        if c.claim_type != "contribution" and c.support in ("none", "weak"):
            quant = c.claim_type in ("result", "comparison")
            add("unsupported_claim", ("high" if c.support == "none" else "medium") if quant else "medium",
                "No strong supporting passage found in the paper body for this claim"
                + ("" if c.support == "none" else " (only weak lexical overlap)")
                + (f"; its numbers ({', '.join(c.numbers[:4])}) do not appear in results text." if c.numbers else "."),
                c.page, c, c.text)
        # 2. numbers cited in the abstract/intro that appear nowhere in results
        missing = [x for x in c.numbers if x not in body_nums and ("." in x or float(x) >= 10)]
        if c.section in ("abstract", "introduction", "conclusion") and missing and body_nums \
                and c.claim_type in ("result", "comparison"):
            add("number_not_in_results", "high",
                f"Reported value(s) {', '.join(missing[:4])} never appear in the experiments/results text or tables "
                "(possible abstract-body mismatch, or derived value that is not shown).", c.page, c, c.text)
        # 3. superlatives without a baseline comparison
        if SUPER_RE.search(c.text) and status.get("baselines") != "present":
            add("superlative_without_baselines", "high",
                "Claims best/state-of-the-art performance but the paper does not describe baselines it compares against.",
                c.page, c, c.text)
        elif SUPER_RE.search(c.text) and c.support in ("none", "weak"):
            add("superlative_unsupported", "medium",
                "Superlative claim with no clear head-to-head comparison in the results.", c.page, c, c.text)
        # 4. 'significant' without a test
        if SIGNIF_RE.search(c.text) and status.get("stat_test") != "present":
            add("significance_without_test", "high",
                "Uses 'significant' but no statistical test (t-test, bootstrap, p-value, CI) is reported.",
                c.page, c, c.text)
        # 5. improvements without variance
        if IMPROVE_RE.search(c.text) and c.numbers and status.get("variance") == "missing" \
                and status.get("seeds") != "present":
            add("improvement_without_variance", "medium",
                "Improvement is reported as a single number with no variance, seeds or confidence interval.",
                c.page, c, c.text)
        # 6. generalisation claims with narrow evidence
        if c.claim_type == "generalization" or GENERAL_RE.search(c.text):
            ev_text = " ".join(e.quote for e in c.evidence)
            dsets = _datasets(doc)
            if len(dsets) <= 2:
                add("generalization_narrow_evidence", "medium",
                    f"Generalisation/robustness claim, but only {len(dsets)} evaluation dataset(s) detected "
                    f"({', '.join(sorted(dsets)) or 'none named'}).", c.page, c, c.text)

    # paper-level gaps
    if status.get("limitations") != "present":
        add("no_limitations", "medium", "No limitations section or discussion of failure cases was found.")
    if status.get("code") == "missing":
        add("no_code", "high", "No code or implementation link is given.")
    if status.get("hyper") not in ("present", "not_applicable"):
        add("no_hyperparameters", "high" if status.get("hyper") == "missing" else "medium",
            "Training hyperparameters are not reported." if status.get("hyper") == "missing"
            else "Hyperparameters are only mentioned in passing; concrete values (learning rate, batch size, epochs) are not given.")
    if status.get("splits") == "missing":
        add("no_splits", "medium", "Data splits are not described.")
    if claims and status.get("baselines") == "missing" and any(c.claim_type == "comparison" for c in claims):
        add("comparison_without_baselines", "high", "Comparative claims are made but baselines are not described.")
    order = {"high": 0, "medium": 1, "low": 2}
    gaps.sort(key=lambda g: (order[g.severity], g.page or 0))
    # de-duplicate identical kind+claim
    seen, out = set(), []
    for g in gaps:
        key = (g.kind, g.claim_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
    for i, g in enumerate(out, 1):
        g.id = f"G{i}"
    return out


_NOT_DATASET = {"the", "this", "that", "each", "both", "our", "these", "those", "same", "test", "training",
                "validation", "benchmark", "new", "another", "standard", "public", "large", "small", "full"}


def _datasets(doc: Document) -> set[str]:
    found = set()
    known = ["ImageNet", "CIFAR-10", "CIFAR-100", "MNIST", "Fashion-MNIST", "COCO", "SQuAD", "GLUE", "SuperGLUE",
             "WMT14", "WMT16", "IWSLT15", "SST-2", "IMDB", "CoNLL-2003", "OntoNotes", "LibriSpeech", "TIMIT",
             "PubMed", "XSum", "CNN/DailyMail", "TriviaQA", "NaturalQuestions", "Yelp-5", "WNUT-17", "LVIS",
             "PASCAL-VOC", "CommonVoice", "Multi30k", "SciFact", "Qasper", "MultiNLI", "SNLI", "CelebA", "Cityscapes"]
    text = " ".join(s.text for s in doc.sentences if s.section in ("experiments", "results", "abstract", "method"))
    for k in known:
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(k) + r"(?![A-Za-z0-9])", text):
            found.add(k)
    for m in re.finditer(r"\b([A-Z][A-Za-z0-9\-]{2,})\s+(?:dataset|benchmark|corpus|test set)", text):
        if m.group(1).lower() not in _NOT_DATASET:
            found.add(m.group(1))
    return found


detected_datasets = _datasets
