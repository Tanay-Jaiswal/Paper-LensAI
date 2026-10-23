"""Glossary: the abbreviations a paper defines for itself, found with the Schwartz & Hearst (2003) algorithm.

"finite element method (FEM)" and "FEM (finite element method)" both define FEM. The long form is accepted only if the
letters of the abbreviation can be found, in order, in the words before it, with the first letter starting a word, so
"we used a mesh (FEM)" is rejected. In the general mode nothing comes from outside the paper: an abbreviation the paper
never spells out cannot be expanded and is listed as undefined instead. In the Computer Science & Engineering mode a
built-in offline dictionary (cse_terms.py) is the fallback for abbreviations the paper does not define; those meanings
are listed separately and labelled "dictionary", and the paper's own definition always wins.
"""
from __future__ import annotations

import contextvars
import re

from .cse_terms import CSE_TERMS, lookup
from .models import Document
from .textutils import stem

_SHORT = re.compile(r"^(?=[^ ]*[A-Za-z])[A-Za-z][A-Za-z0-9\-/&]{1,9}s?$")
_PAREN = re.compile(r"\(([^()]{2,80})\)")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/]*")
_CAPS = re.compile(r"(?<![A-Za-z0-9\-])([A-Z][A-Z0-9]{1,6}s?)(?![A-Za-z0-9\-])")
_SKIP_SECTIONS = {"references", "acknowledgments"}   # author initials and funders, not terms
_NOT_ABBR = {"fig", "figs", "eq", "eqs", "table", "ref", "refs", "see", "e.g", "i.e", "vs", "etc", "cf", "ie", "eg", "al", "et"}
# capitals that are words, units, numerals or common non-technical abbreviations, never reported as undefined
_COMMON = {"I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "A", "AND", "OR", "THE", "OF", "IN",
           "USA", "UK", "EU", "US", "PDF", "URL", "HTTP", "HTTPS", "DOI", "ID", "OK", "PM", "AM", "CI", "SD", "SE", "OR",
           "HR", "RR", "IQR", "GPU", "CPU", "RAM", "MB", "GB", "TB", "KB", "NA", "N/A", "ISBN", "ISSN", "PMC", "PMID",
           "CC", "BY", "IEEE", "ACM", "ACL", "AI", "ML", "TABLE", "FIG", "NO", "VS", "ET", "AL"}


def _long_form(short: str, words: list[str]) -> str | None:
    """Schwartz & Hearst: the shortest run of trailing `words` whose letters spell `short` in order."""
    s = re.sub(r"[^a-z0-9]", "", short.lower().rstrip("s") if short.endswith("s") and len(short) > 2 else short.lower())
    if not s or not s[0].isalpha():
        return None
    text = " ".join(words)
    si, li = len(s) - 1, len(text) - 1
    while si >= 0:
        c = s[si]
        while li >= 0 and (text[li].lower() != c or (si == 0 and li > 0 and text[li - 1].isalnum())):
            li -= 1
        if li < 0:
            return None
        li -= 1
        si -= 1
    start = text.rfind(" ", 0, li + 1) + 1
    long = text[start:].strip(" ,;:")
    n = len(long.split())
    if n < 2 and len(s) > 2 or n > min(len(s) + 5, 2 * len(s)) or len(long) <= len(short):
        return None
    if long.lower().split()[0] in {"the", "a", "an", "and", "or", "of", "in", "on", "for", "with", "to", "by"}:
        long = " ".join(long.split()[1:])
    return long or None


def _definitions(text: str):
    for m in _PAREN.finditer(text):
        inside = m.group(1).strip()
        before = text[max(0, m.start() - 160):m.start()].rstrip()
        first = inside.split(";")[0].split(",")[0].strip()
        if _SHORT.match(first) and first.lower().rstrip(".") not in _NOT_ABBR and any(ch.isupper() for ch in first):
            words = _WORD.findall(before)[-(min(len(first) + 5, 2 * len(first))):]
            lf = _long_form(first, words)
            if lf:
                yield first, lf, m
                continue
        # reverse form: "FEM (finite element method)"
        prev = re.search(r"([A-Za-z][A-Za-z0-9\-/&]{1,9})\s*$", before)
        if prev and len(inside.split()) >= 2 and any(ch.isupper() for ch in prev.group(1)) \
                and sum(ch.isupper() for ch in prev.group(1)) >= 2:
            lf = _long_form(prev.group(1), _WORD.findall(inside))
            if lf and lf.lower() == " ".join(_WORD.findall(inside)).lower()[-len(lf):]:
                yield prev.group(1), lf, m


# dictionary keys that _CAPS cannot see: mixed case (ResNet, IoU), or with punctuation inside (R-CNN, I/O, TF-IDF)
_DICT_OTHER = re.compile(r"(?<![A-Za-z0-9\-/])(" + "|".join(
    re.escape(k) for k in sorted((k for k in CSE_TERMS if not re.fullmatch(r"[A-Z][A-Z0-9]{1,6}", k)), key=len, reverse=True))
    + r")s?(?![A-Za-z0-9/]|-[A-Za-z])")     # "ResNet-50" counts as ResNet, "Adam-like" does not


def build_glossary(doc: Document, use_dictionary: bool = False) -> dict:
    """{'defined': [{abbr, long, page, sentence_id, quote, uses, source='paper'}], 'undefined': [{abbr, uses, page}],
    'from_dictionary': [{abbr, long, kind, ambiguous, uses, page, source='dictionary'}] (empty unless use_dictionary)}"""
    defined: dict[str, dict] = {}
    for s in doc.sentences:
        if s.kind == "meta" or s.section in _SKIP_SECTIONS:
            continue
        for short, long, m in _definitions(s.text):
            long = re.sub(r"[\s\d,;:]+$", "", long)
            if len(long.split()) < 2 and len(short) > 2:
                continue
            key = short.rstrip("s") if short.endswith("s") and short[:-1].isupper() else short
            if key not in defined:
                q0, q1 = max(0, m.start() - 90), min(len(s.text), m.end() + 30)
                defined[key] = {"abbr": key, "long": long, "page": s.page, "sentence_id": s.id,
                                "quote": ("…" if q0 else "") + s.text[q0:q1] + ("…" if q1 < len(s.text) else ""), "uses": 0,
                                "source": "paper"}
    caps: dict[str, dict] = {}
    known: dict[str, dict] = {}      # dictionary meanings for abbreviations the paper uses but does not define
    for s in doc.sentences:
        if s.kind == "meta" or s.section in _SKIP_SECTIONS:
            continue
        for m in _CAPS.finditer(s.text):
            a = m.group(1)
            a = a[:-1] if a.endswith("s") and a[:-1].isupper() and len(a) > 2 else a
            if a in defined:
                defined[a]["uses"] += 1
            elif use_dictionary and lookup(a):
                _count(known, a, s.page)
            elif a not in _COMMON and not a.isdigit() and sum(ch.isalpha() for ch in a) >= 2:
                c = caps.setdefault(a, {"abbr": a, "uses": 0, "page": s.page})
                c["uses"] += 1
        if use_dictionary:
            for m in _DICT_OTHER.finditer(s.text):
                a = m.group(1)
                if a not in defined:
                    _count(known, a, s.page)
    undefined = sorted((c for c in caps.values() if c["uses"] >= 2), key=lambda c: (-c["uses"], c["abbr"]))
    from_dict = sorted(known.values(), key=lambda d: (-d["uses"], d["abbr"].lower()))
    note = ("Definitions are taken from the paper itself (\"long form (ABBR)\" or \"ABBR (long form)\"). ")
    if use_dictionary:
        note += ("Abbreviations the paper uses without spelling them out are looked up in PaperLens's built-in Computer "
                 "Science & Engineering dictionary and listed separately as dictionary meanings: they are standard "
                 "meanings in the field, not the paper's own words, and the paper may mean something else. Where an "
                 "abbreviation has several common meanings all are shown. Anything not in the dictionary is listed "
                 "as undefined.")
    else:
        note += ("Abbreviations the paper never spells out cannot be expanded: the general mode uses no external "
                 "dictionary. They are listed as undefined so a reader can look them up.")
    return {"defined": sorted(defined.values(), key=lambda d: d["abbr"].lower()), "undefined": undefined[:40],
            "from_dictionary": from_dict[:80], "dictionary_used": use_dictionary, "note": note}


def _count(known: dict, a: str, page: int) -> None:
    hit = lookup(a)
    if not hit:
        return
    key = a[:-1] if a.endswith("s") and a not in CSE_TERMS and a[:-1] in CSE_TERMS else a
    d = known.setdefault(key, {"abbr": key, "long": hit[0], "kind": hit[1], "ambiguous": " / " in hit[0],
                               "uses": 0, "page": page, "source": "dictionary"})
    d["uses"] += 1


# ---- use in evidence matching ---------------------------------------------------------------------------------------
# set by claims.build_ledger for the paper being analysed; a ContextVar keeps parallel analyses apart
CURRENT: contextvars.ContextVar[dict] = contextvars.ContextVar("glossary_tokens", default={})


def token_map(glossary: dict) -> dict[str, list[str]]:
    """{'fem': ['finit', 'element', 'method']}: abbreviation token -> stemmed tokens of its long form."""
    out = {}
    for d in glossary.get("defined", []):
        toks = [stem(t.lower()) for t in re.findall(r"[A-Za-z][A-Za-z\-]*[A-Za-z]|[A-Za-z]", d["long"])]
        key = stem(d["abbr"].lower())
        if len(toks) >= 2 and key:
            out[key] = toks
    return out


def expand_tokens(tokens: list[str], tmap: dict[str, list[str]] | None = None) -> list[str]:
    """Add the long form after an abbreviation and the abbreviation after its long form, so either wording matches."""
    tmap = CURRENT.get() if tmap is None else tmap
    if not tmap:
        return tokens
    extra = []
    for t in tokens:
        if t in tmap:
            extra.extend(tmap[t])
    joined = " " + " ".join(tokens) + " "
    for abbr, long in tmap.items():
        if " " + " ".join(long) + " " in joined:
            extra.append(abbr)
    return tokens + extra
