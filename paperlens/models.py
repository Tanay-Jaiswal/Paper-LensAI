"""Plain dataclasses shared across the pipeline. Everything is JSON-serialisable."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Sentence:
    id: int
    text: str
    page: int            # 1-based
    section: str         # canonical section label (see ingest.CANONICAL)
    heading: str = ""    # raw heading text
    kind: str = "text"   # text | table | caption | meta (publisher front-matter, identifiers)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Document:
    doc_id: str
    title: str
    n_pages: int
    sentences: list[Sentence]
    source_name: str = ""
    warnings: list[str] = field(default_factory=list)

    def by_section(self, *sections: str) -> list[Sentence]:
        return [s for s in self.sentences if s.section in sections]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id, "title": self.title, "n_pages": self.n_pages,
            "source_name": self.source_name, "warnings": self.warnings,
            "n_sentences": len(self.sentences),
        }


@dataclass
class EvidenceLink:
    sentence_id: int
    page: int
    section: str
    quote: str
    score: float
    shared_numbers: list[str] = field(default_factory=list)
    shared_terms: list[str] = field(default_factory=list)


@dataclass
class Claim:
    id: str
    sentence_id: int
    text: str
    page: int
    section: str
    claim_type: str            # contribution | result | comparison | generalization | assertion
    hedged: bool
    numbers: list[str]
    evidence: list[EvidenceLink] = field(default_factory=list)
    support: str = "none"      # strong | moderate | weak | none
    support_score: float = 0.0
    flags: list[str] = field(default_factory=list)
    confidence: float = 0.0    # confidence that this sentence is a genuine claim

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RubricItem:
    key: str
    label: str
    category: str
    weight: float
    status: str                # present | partial | missing | not_applicable (excluded from the score)
    credit: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    advice: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Gap:
    id: str
    kind: str
    severity: str              # high | medium | low
    message: str
    page: int | None = None
    claim_id: str | None = None
    quote: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
