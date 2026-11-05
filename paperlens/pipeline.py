"""End-to-end analysis: PDF -> Analysis (summary, ledger, rubric, gaps, numeric consistency)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .citations import check_citations, reference_text
from .claims import THRESHOLDS, build_ledger
from .consistency import audit as consistency_audit
from .field import resolve_mode
from .glossary import build_glossary
from .gaps import detect_gaps, detected_datasets
from .ingest import UNREADABLE_WARNING, parse_pdf
from .models import Claim, Document, Gap
from .reproducibility import assess
from .revisions import revision_checklist
from .summarize import summarize


@dataclass
class Analysis:
    doc: Document
    summary: dict
    claims: list[Claim]
    rubric: dict
    gaps: list[Gap]
    datasets: list[str]
    metrics: list[str]
    consistency: dict = field(default_factory=dict)   # see consistency.audit
    glossary: dict = field(default_factory=dict)      # see glossary.build_glossary
    mode: dict = field(default_factory=dict)          # see field.resolve_mode (which field-specific checks ran)
    citations: dict = field(default_factory=dict)     # see citations.check_citations

    def to_dict(self) -> dict:
        support = {k: sum(1 for c in self.claims if c.support == k) for k in ("strong", "moderate", "weak", "none")}
        return {
            "version": __version__,
            "document": self.doc.to_dict(),
            "summary": self.summary,
            "ledger": [c.to_dict() for c in self.claims],
            "ledger_stats": {"n_claims": len(self.claims), "support": support,
                             "evidence_status": {k: sum(1 for c in self.claims if c.evidence_status == k)
                                                 for k in ("found", "no_supporting_evidence", "no_searchable_text")},
                             "thresholds": THRESHOLDS},
            "reproducibility": self.rubric,
            "gaps": [g.to_dict() for g in self.gaps],
            "datasets": self.datasets,
            "metrics": self.metrics,
            "consistency": self.consistency,
            "revisions": revision_checklist(self),
            "glossary": self.glossary,
            "field": self.mode,
            "citations": self.citations,
        }


NOT_ASSESSED = "not assessed"

METRIC_TERMS = ["accuracy", "F1", "BLEU", "ROUGE-L", "ROUGE", "mAP", "AUC", "precision", "recall", "WER", "perplexity",
                "exact match", "MRR", "NDCG", "RMSE", "MAE", "IoU", "top-1", "top-5", "pass@1"]


def detect_metrics(doc: Document) -> list[str]:
    import re
    text = " ".join(s.text for s in doc.sentences if s.section in ("abstract", "experiments", "results"))
    out = []
    for m in METRIC_TERMS:
        if re.search(r"(?<![A-Za-z])" + re.escape(m) + r"(?![A-Za-z])", text, re.I if m.islower() else 0):
            out.append(m)
    return out


def analyze_document(doc: Document, mode: str = "auto", raw_refs: str = "") -> Analysis:
    fld = resolve_mode(doc, mode)
    cse = fld["field"] == "cse"
    glossary = build_glossary(doc, use_dictionary=cse)
    claims = build_ledger(doc, glossary=glossary)
    rubric = assess(doc, fld["field"])
    if UNREADABLE_WARNING in doc.warnings:
        # almost no text came out of the PDF: "no code link" or a score of 0 would describe the extraction, not the paper
        rubric["band"] = NOT_ASSESSED
        rubric["disclaimer"] = ("Not assessed: too little text could be extracted from this PDF, so the score below "
                                "says nothing about the paper. " + rubric["disclaimer"])
        gaps = [Gap("G1", "document_unreadable", "high",
                    "Too little text could be extracted from this PDF (it may be scanned). Claims, evidence, the "
                    "reproducibility rubric and evidence gaps could not be assessed.")]
    else:
        gaps = detect_gaps(doc, claims, rubric, fld["field"])
    return Analysis(doc, summarize(doc), claims, rubric, gaps, sorted(detected_datasets(doc)), detect_metrics(doc),
                    consistency_audit(doc), glossary, fld, check_citations(doc, raw_refs))


def analyze_pdf(path: str | Path, doc_id: str | None = None, mode: str = "auto") -> Analysis:
    return analyze_document(parse_pdf(path, doc_id), mode, reference_text(path))


def save_json(a: Analysis, path: str | Path) -> None:
    Path(path).write_text(json.dumps(a.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
