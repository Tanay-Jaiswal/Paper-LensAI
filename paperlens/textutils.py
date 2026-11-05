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


# ---- quantities: a number together with what it measures -----------------------------------------------------------
# A shared numeric literal is not evidence on its own ("a factor of 7" vs "7 Myr"). A Quantity keeps the unit and the
# neighbouring content words so that two numbers are only matched when they plausibly measure the same thing.

_UNIT_ALIASES = {
    "%": "%", "percent": "%", "percentage": "%", "pct": "%",
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s", "ms": "ms", "msec": "ms", "milliseconds": "ms",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min", "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "day": "day", "days": "day", "week": "week", "weeks": "week", "month": "month", "months": "month",
    "year": "year", "years": "year", "yr": "year", "yrs": "year", "myr": "myr", "gyr": "gyr", "kyr": "kyr",
    "km": "km", "m": "m", "cm": "cm", "mm": "mm", "nm": "nm", "kpc": "kpc", "mpc": "mpc", "pc": "pc",
    "kg": "kg", "g": "g", "mg": "mg", "ml": "ml", "mol": "mol", "k": "k", "hz": "hz", "khz": "khz", "mhz": "mhz", "ghz": "ghz",
    "ev": "ev", "kev": "kev", "mev": "mev", "gev": "gev", "tev": "tev", "db": "db", "kw": "kw", "fb": "fb", "pb": "pb",
    "x": "x", "×": "x", "times": "x", "fold": "x", "-fold": "x",
    "point": "point", "points": "point", "pp": "point",
    "bleu": "bleu", "rouge": "rouge", "rouge-l": "rouge", "f1": "f1", "accuracy": "accuracy", "auc": "auc", "auroc": "auc",
    "map": "map", "wer": "wer", "perplexity": "perplexity", "ppl": "perplexity", "mrr": "mrr", "ndcg": "ndcg",
    "gpus": "gpu", "gpu": "gpu", "layers": "layer", "layer": "layer", "epochs": "epoch", "epoch": "epoch",
    "patients": "patient", "participants": "participant", "samples": "sample", "studies": "study",
}
# metric names also identify a quantity when they come just BEFORE the number ("BLEU of 41.8", "F1 = 73.2")
_METRIC_UNITS = {"bleu", "rouge", "f1", "accuracy", "auc", "map", "wer", "perplexity", "mrr", "ndcg"}
_SCI = r"(?:\s?[×·]\s?10\s?\^?\s?(?P<exp>[−\-–]?\d{1,3})|\s?x\s?10\s?(?:\^\s?|(?=[−\-–]))(?P<exp2>[−\-–]?\d{1,3})|e(?P<exp3>[−\-–]?\d{1,3})\b)"
_QTOKEN_RE = re.compile(
    r"(?P<pow>(?<![\w.])10\s?\^\s?\{?(?P<pexp>[−\-–]?\d{1,3})\}?)|"        # a bare power of ten: 10^-3 is 1e-3
    r"(?P<num>(?<![\w.])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?))" + _SCI + r"?(?P<pct>\s?%)?"
    r"|(?P<word>[A-Za-z×][A-Za-z0-9\-]*)")


_RANGE_LINK = re.compile(r"\s*(?:[-–−]|to|and|or|±|\+/-|\+-)\s*")


class Quantity:
    """value: normalised literal ('3.5', '1200', '1.7e-9'); unit: canonical unit or ''; context: nearby stemmed words."""
    __slots__ = ("value", "unit", "context")

    def __init__(self, value: str, unit: str, context: frozenset):
        self.value, self.unit, self.context = value, unit, context

    def __repr__(self):
        return f"Quantity({self.value!r}, {self.unit!r}, {sorted(self.context)})"

    @property
    def specific(self) -> bool:
        """A value unlikely to recur by chance: has a decimal part, an exponent, or three or more digits."""
        return "." in self.value or "e" in self.value or len(self.value) >= 3

    def matches(self, other: "Quantity") -> bool:
        if self.value != other.value:
            return False
        shared_context = bool(self.context & other.context)
        if self.unit and other.unit:
            if {self.unit, other.unit} & {"%"} and {self.unit, other.unit} & _METRIC_UNITS:
                return shared_context  # "89.1% F1" and "89.1 F1": a score written as a percentage; the words must agree
            # same unit: enough for a specific value; a round small value also needs a shared word
            return self.unit == other.unit and (self.specific or shared_context)
        return shared_context          # at most one side names a unit: the surrounding words must agree


def _clean_numeric_noise(text: str) -> str:
    text = re.sub(r"\d+(?:" + UNMAPPED + r"\d+)+\s?%?", " ", text)
    # CIFAR-10 stays a word; the look-behind keeps the exponent of 1e-3 from being read as a name
    text = re.sub(r"(?<![0-9])[A-Za-z][A-Za-z0-9]*-\d+(?:\.\d+)?\b", lambda m: re.sub(r"\d", "#", m.group(0)), text)
    text = _VERSION_RE.sub(" ", text)
    text = _CITE_RE.sub(" ", text)
    return re.sub(r"\b(?:Table|Tab\.|Figure|Fig\.|Section|Sec\.|Eq\.|Equation|Appendix)\s*\d+(?:\.\d+)*", " ", text)


def quantities_in(text: str, window: int = 2) -> list[Quantity]:
    """Numbers in `text` with their unit and nearby words. Years (1900-2099 with no unit) are dropped."""
    toks = []   # (kind, value, unit_from_token)
    spans = []  # where each token sits in the cleaned text
    text = _clean_numeric_noise(text)
    for m in _QTOKEN_RE.finditer(text):
        spans.append(m.span())
        if m.group("pow"):
            toks.append(("num", f"1e{int(m.group('pexp').replace('−', '-').replace('–', '-'))}", ""))
        elif m.group("num"):
            raw = m.group("num").replace(",", "")
            if "." in raw:
                raw = raw.rstrip("0").rstrip(".")
            exp = m.group("exp") or m.group("exp2") or m.group("exp3")
            if exp:
                raw = f"{raw}e{int(exp.replace('−', '-').replace('–', '-'))}"
            toks.append(("num", raw, "%" if m.group("pct") else ""))
        else:
            toks.append(("word", m.group("word").lower(), ""))
    units = {}
    for i, (kind, val, unit) in enumerate(toks):
        if kind == "num":
            nxt = toks[i + 1][1] if i + 1 < len(toks) and toks[i + 1][0] == "word" else ""
            units[i] = unit or _UNIT_ALIASES.get(nxt, "")
    # a range or an error bar states its unit once, after the last number: "3.5 to 4.2%", "125.3 ± 0.6 GeV"
    nums = sorted(units)
    for a, b in zip(nums[-2::-1], nums[:0:-1]):
        if not units[a] and units[b] and _RANGE_LINK.fullmatch(text[spans[a][1]:spans[b][0]]):
            units[a] = units[b]
    for a, b in zip(nums, nums[1:]):       # ... or before the first one: "improves F1 from 85.6 to 89.1"
        if units[a] and not units[b] and _RANGE_LINK.fullmatch(text[spans[a][1]:spans[b][0]]):
            units[b] = units[a]
    out = []
    for i, (kind, val, unit) in enumerate(toks):
        if kind != "num":
            continue
        unit = units[i]
        left = [t[1] for t in toks[max(0, i - 2 * window):i] if t[0] == "word" and t[1] not in STOPWORDS][-window:]
        right = [t[1] for t in toks[i + 1:i + 1 + 2 * window] if t[0] == "word" and t[1] not in STOPWORDS][:window]
        if not unit:
            near = [w for w in left[::-1] + right if _UNIT_ALIASES.get(w) in _METRIC_UNITS]
            if near:
                unit = _UNIT_ALIASES[near[0]]
        ctx = frozenset(stem(w) for w in left + right if len(w) > 1 and w not in ("x", "×"))
        if not unit and re.fullmatch(r"(19|20)\d\d", val):
            continue
        out.append(Quantity(val, unit, ctx))
    return out


def match_quantities(claim_qs: list[Quantity], passage_qs: list[Quantity]) -> list[str]:
    """Values of claim quantities that some passage quantity matches in value, unit and/or context."""
    return sorted({c.value for c in claim_qs if any(c.matches(p) for p in passage_qs)})


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
