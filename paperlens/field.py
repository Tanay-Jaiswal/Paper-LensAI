"""Which field-specific checks to run: Computer Science & Engineering (CSE) or the general checklist only.

The mode is chosen by the user ("cse", "general") or, by default ("auto"), from two counts that anyone can recompute
from the report: body sentences that use computing vocabulary, and reference-list entries that cite computing venues
(NeurIPS, ACL, CVPR, arXiv cs ...). The rule and its thresholds are fixed and listed in the output, so a decision can
be checked and overruled with --mode.
"""
from __future__ import annotations

import re

from .models import Document

MODES = ("auto", "cse", "general")

_CS_VOCAB = re.compile(
    r"\b(algorithms?|neural networks?|deep learning|machine learning|datasets?|benchmarks?|GPUs?|TPUs?|"
    r"(?:pre-?)?train(?:ed|ing)? (?:on|the|a|our) (?:model|network|data|dataset|corpus)\w*|fine-?tun\w+|transformers?|embeddings?|encoders?|decoders?|"
    r"classifiers?|state[- ]of[- ]the[- ]art|baseline (?:model|method|system)s?|source code|implementation|open[- ]source|runtime|latency|"
    r"throughput|compiler|software|hardware|computational (?:cost|complexity)|time complexity|"
    r"convolution\w*|recurrent|attention mechanism|language models?|tokens?|inference time|github|"
    r"machine translation|n-grams?|corpus|corpora|computers?|computational|programming|databases?|"
    r"quer(?:y|ies)|network protocols?|cache|processors?|parallel)\b", re.I)
_CS_VENUE = re.compile(
    r"\b(NeurIPS|NIPS|ICML|ICLR|CVPR|ICCV|ECCV|AAAI|IJCAI|ACL|EMNLP|NAACL|COLING|KDD|SIGIR|SIGCOMM|SIGMOD|VLDB|OSDI|"
    r"SOSP|NSDI|ISCA|MICRO|ASPLOS|PLDI|POPL|ICSE|FSE|CHI|UIST|WWW|ICRA|IROS|USENIX|Interspeech|ICASSP|"
    r"Transactions on (?:Pattern|Neural|Software|Computers|Knowledge|Information|Networking)|"
    r"Computational Linguistics|Neural Information Processing|Machine Learning|Computer Vision|Pattern Recognition|"
    r"Artificial Intelligence|Learning Representations|Data Mining|Information Retrieval|Computer Science|"
    r"Journal of Machine Learning Research|arXiv(?: preprint)? arXiv:\d{4}\.\d{4,5}|abs/\d{4}\.\d{4,5})\b")
_BODY = {"abstract", "introduction", "background", "method", "experiments", "results", "discussion", "conclusion",
         "related", "other", "front", "appendix", "limitations"}

# a paper is treated as CSE when either share is reached (see docs/CSE_MODE.md for how they were set)
VOCAB_SHARE = 0.09      # share of body sentences using computing vocabulary
VENUE_SHARE = 0.08      # share of reference entries citing computing venues
MIN_REFS = 5


def detect_field(doc: Document) -> dict:
    body = [s for s in doc.sentences if s.section in _BODY and s.kind != "meta"]
    refs = [s for s in doc.sentences if s.section == "references"]
    vocab = sum(1 for s in body if _CS_VOCAB.search(s.text))
    venue = sum(1 for s in refs if _CS_VENUE.search(s.text))
    v_share = vocab / len(body) if body else 0.0
    r_share = venue / len(refs) if len(refs) >= MIN_REFS else 0.0
    is_cse = v_share >= VOCAB_SHARE or r_share >= VENUE_SHARE
    return {"field": "cse" if is_cse else "general",
            "vocab_sentences": vocab, "body_sentences": len(body), "vocab_share": round(v_share, 3),
            "venue_references": venue, "reference_entries": len(refs), "venue_share": round(r_share, 3),
            "rule": f"CSE when at least {VOCAB_SHARE:.0%} of body sentences use computing vocabulary or at least "
                    f"{VENUE_SHARE:.0%} of reference entries (of {MIN_REFS} or more) cite computing venues."}


def resolve_mode(doc: Document, mode: str = "auto") -> dict:
    """{'mode': requested mode, 'field': 'cse' | 'general', 'detected': detect_field(...) or None, 'reason': str}"""
    mode = (mode or "auto").lower()
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; choose one of {', '.join(MODES)}")
    det = detect_field(doc)
    if mode == "auto":
        field, reason = det["field"], ("Detected automatically: " + (
            f"{det['vocab_share']:.0%} of body sentences use computing vocabulary, "
            f"{det['venue_share']:.0%} of references cite computing venues."))
    else:
        field, reason = mode, f"Chosen by the user (--mode {mode})."
    return {"mode": mode, "field": field, "detected": det, "reason": reason,
            "label": "Computer Science & Engineering" if field == "cse" else "General"}
