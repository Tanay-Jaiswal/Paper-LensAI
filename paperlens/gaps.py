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


def detect_gaps(doc: Document, claims: list[Claim], rubric: dict, field: str = "general") -> list[Gap]:
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
        if c.evidence_status == "no_searchable_text":
            pass  # the document could not be searched: a parsing problem, not a gap in the paper
        elif c.claim_type != "contribution" and c.support in ("none", "weak"):
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
    if field == "cse":
        _cse_gaps(doc, claims, status, add)
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


# ---- Computer Science & Engineering rules (field="cse") -------------------------------------------------------------
TEST_TUNING_RE = re.compile(
    r"\b(tun(?:e|ed|ing)|select(?:ed|ing)?|chose|chosen|early[- ]stop\w*|pick(?:ed)?)\b[^.]{0,50}"
    r"\b(on|using|based on|according to) (the )?test (set|data|split|accuracy|performance|results?)\b", re.I)
NEGATION_RE = re.compile(r"\b(not|never|no|without)\b", re.I)
COPIED_RE = re.compile(
    r"\b((results|numbers|scores|figures) (of|for) (the |all |other )?(baselines?|prior|previous|other|competing)"
    r"[^.]{0,40}\b(are|were) (taken|copied|quoted|reported) from|(are|were) (taken|copied|quoted) from (the )?"
    r"(original|respective|corresponding|their|prior|previous)? ?(papers?|works?|publications?|\[|\())", re.I)
SMALL_GAIN_RE = re.compile(
    r"\b(by|of|\+)\s*(0?\.\d+|1(?:\.0+)?)\s*(%|points?|pp|percentage points?|absolute|BLEU|F1|accuracy)", re.I)


def _cse_gaps(doc: Document, claims: list[Claim], status: dict, add) -> None:
    sents = [s for s in doc.sentences if s.section not in ("references", "related", "acknowledgments")
             and s.kind != "meta"]
    for s in sents:
        m = TEST_TUNING_RE.search(s.text)
        if m and not NEGATION_RE.search(s.text[max(0, m.start() - 25):m.end()]):
            add("test_set_tuning", "high",
                "Hyperparameters, checkpoints or settings appear to be chosen using the test set; this makes test "
                "results optimistic. Check the wording: a held-out validation set should be used for choices.",
                s.page, None, s.text)
            break
    for s in sents:
        if COPIED_RE.search(s.text):
            add("baseline_numbers_copied", "low",
                "Baseline numbers are taken from earlier papers rather than re-run. That is common, but the comparison "
                "is only fair if dataset version, split, preprocessing and metric are the same.", s.page, None, s.text)
            break
    if status.get("cs_code_link") == "partial":
        ev = next((s for s in sents if re.search(r"will be (made )?(publicly )?(available|released|open[- ]sourced)", s.text, re.I)), None)
        add("code_promised_not_linked", "medium",
            "Code is promised or available on request, but no repository link is given.",
            ev.page if ev else None, None, ev.text if ev else "")
    no_spread = status.get("seeds") != "present" and status.get("cs_table_uncertainty") in ("missing", "partial", None) \
        and status.get("variance") != "present"
    for c in claims:
        if c.claim_type not in ("result", "comparison") or c.section not in ("abstract", "introduction", "conclusion"):
            continue
        m = SMALL_GAIN_RE.search(c.text)
        if m and IMPROVE_RE.search(c.text) and status.get("stat_test") != "present":
            add("small_gain_without_test", "medium",
                f"Claims an improvement of {m.group(2)} {m.group(3)}, a margin that run-to-run variation can produce, "
                "with no significance test reported.", c.page, c, c.text)
        elif SUPER_RE.search(c.text) and no_spread and not c.numbers:
            add("sota_single_run", "medium",
                "State-of-the-art or 'best' claim, but no seeds, repeated runs or spread are reported, so a single "
                "lucky run cannot be ruled out.", c.page, c, c.text)


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
