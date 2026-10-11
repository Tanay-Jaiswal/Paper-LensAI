"""Sentence splitting, tokenisation and BM25 retrieval (no external models)."""
from __future__ import annotations

import math
import re
from collections import Counter

_ABBREV = {
    "et al", "e.g", "i.e", "fig", "figs", "eq", "eqs", "tab", "sec", "no", "vs", "cf",
    "etc", "approx", "dr", "prof", "al", "ref", "refs", "resp", "ca", "st", "inc", "ltd",
}
_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")

STOPWORDS = frozenset(
    """a an the and or of to in on for with by from at as is are was were be been being this that these those
    it its we our us they their them which who whom whose than then so such can could may might will would shall
    should do does did done has have had having not no nor but if while when where how what why also both each
    other more most some any all per via into over under between among within without across using used use based
    paper results result show shown shows however thus therefore""".split()
)

UNMAPPED = "�"   # stands for a glyph the PDF could not map to text (see ingest._clean)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-]*[A-Za-z]|[A-Za-z]|\d+(?:\.\d+)?")
NUMBER_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?%)?")


def split_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries, guarding common scholarly abbreviations."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = _SPLIT_RE.split(text)
    merged: list[str] = []
    for part in parts:
        if merged:
            prev = merged[-1]
            m = re.search(r"([A-Za-z]+(?: [a-z]+)?)\.$", prev)
            tail = m.group(1).lower() if m else ""
            last_word = tail.split(" ")[-1] if tail else ""
            if tail in _ABBREV or last_word in _ABBREV or re.search(r"\b[A-Z]\.$", prev):
                merged[-1] = prev + " " + part
                continue
        merged.append(part)
    return [s.strip() for s in merged if s.strip()]


def stem(tok: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "ied", "edly", "ed", "es", "s"):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            base = tok[: -len(suf)]
            return base + "y" if suf in ("ies", "ied") else base
    return tok


def tokenize(text: str, keep_stop: bool = False) -> list[str]:
    toks = [t.lower() for t in _TOKEN_RE.findall(text)]
    if not keep_stop:
        toks = [t for t in toks if t not in STOPWORDS]
    return [stem(t) for t in toks]


_VERSION_RE = re.compile(r"\b(?:python|pytorch|tensorflow|cuda|cudnn|version|ver\.?|v|torch|keras|numpy|scikit-learn|"
                         r"jax|ubuntu|windows)\s*v?\d+(?:\.\d+)*", re.I)
_CITE_RE = re.compile(r"\[\d+(?:[,\-–]\s*\d+)*\]")


def numbers_in(text: str) -> list[str]:
    """Normalised numeric literals (commas stripped, trailing zeros trimmed).

    Software versions ("Python 3.10"), citation markers ("[12]") and table/figure
    numbers are removed first, because they would create spurious numeric matches.
    """
    text = re.sub(r"\d+(?:" + UNMAPPED + r"\d+)+\s?%?", " ", text)       # 13?4: digits around an unmapped glyph
    text = re.sub(r"[×·]\s?10\s?[−\-–]?\d+", " ", text)                 # powers of ten: 1.7×10−9 is not "10" and "9"
    text = re.sub(r"[A-Za-z][A-Za-z0-9]*-\d+(?:\.\d+)?\b", " ", text)   # dataset/model names: Yelp-5, CIFAR-10
    text = _VERSION_RE.sub(" ", text)
    text = _CITE_RE.sub(" ", text)
    text = re.sub(r"\b(?:Table|Tab\.|Figure|Fig\.|Section|Sec\.|Eq\.|Equation|Appendix)\s*\d+(?:\.\d+)*", " ", text)
    out = []
    for m in NUMBER_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        if "." in raw:
            raw = raw.rstrip("0").rstrip(".")
        out.append(raw)
    return out


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class BM25:
    """Small Okapi BM25 index over pre-tokenised documents."""

    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.N = len(docs)
        self.avgdl = (sum(len(d) for d in docs) / self.N) if self.N else 0.0
        df: Counter = Counter()
        for d in docs:
            df.update(set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [Counter(d) for d in docs]

    def score(self, query: list[str], i: int) -> float:
        tf, dl = self.tf[i], len(self.docs[i])
        s = 0.0
        for t in set(query):
            f = tf.get(t, 0)
            if not f:
                continue
            denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
            s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
        return s

    def self_score(self, query: list[str]) -> float:
        """Upper-ish bound used for normalising scores into 0..1."""
        s = 0.0
        for t in set(query):
            idf = self.idf.get(t, math.log(1 + self.N + 0.5))
            s += idf * (self.k1 + 1) / (1 + self.k1) * 1.0
        return s or 1.0

    def rank(self, query: list[str], exclude: set[int] | None = None, k: int = 5):
        scored = [
            (i, self.score(query, i))
            for i in range(self.N)
            if not exclude or i not in exclude
        ]
        scored = [x for x in scored if x[1] > 0]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
