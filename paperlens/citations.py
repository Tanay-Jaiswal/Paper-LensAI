"""Citation and reference-list checks.

Fixed text rules, run on the reference list and the in-text citations the parser already extracted:

* numbered style ("[12]", "[3-5]", a list numbered [1], [2] ... or 1., 2. ...): numbers cited in the text that have no
  entry in the list, and entries that are never cited;
* author-year style ("(Peters et al., 2018a)", "Devlin et al. (2019)"): citations whose author and year cannot be found
  anywhere in the reference list, and entries whose first author and year are never cited;
* both styles: duplicate entries, entries without a year, and a profile of the list (how recent, share of preprints,
  share with a DOI or link) that is reported as information, not as a problem.

What it cannot do: it does not look anything up online (retractions, wrong DOIs, whether a cited paper says what it is
cited for), it does not recognise superscript citation numbers, and it can misread a reference list whose entries the
PDF parser split in unusual places. Every finding quotes the text it is based on so it can be checked.
"""
from __future__ import annotations

import re
from collections import Counter

from .models import Document

_DASH = "–—−�-"           # en/em dash, minus, an unmapped glyph (usually a dash) and hyphen
_BRACKET = re.compile(r"\[(\d{1,3}(?:\s*[,;" + _DASH + r"]\s*\d{1,3})*)\]")
_YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20[0-4]\d)([a-z]?)(?!\d)")
_IEEE_RANGE = re.compile(r"\[(\d{1,3})\]\s*[" + _DASH + r"]\s*\[(\d{1,3})\]")     # "[11]–[13]" cites 11, 12 and 13
_PREPRINT = re.compile(r"\b(arxiv|biorxiv|medrxiv|corr\b|preprint|ssrn|openreview)", re.I)
_ARXIV_ID = re.compile(r"(?:arxiv|abs/|hep-|astro-ph|gr-qc|cond-mat)", re.I)
_LINK = re.compile(r"\b(doi|https?://|www\.)", re.I)

# author-year citations: "(Peters et al., 2018a; Radford et al., 2018)", "(Dolan and Brockett, 2005)", "Devlin et al. (2019)"
_NAME = r"(?:(?:[Vv]an|[Vv]on|[Dd]e|[Dd]er|[Dd]en|[Dd]i|[Dd]a|[Dd]el|[Dd]u|[Ll]e|[Ll]a)\s)*[A-Z][A-Za-z'’À-ſ\-]+"
_PAREN_ITEM = re.compile(r"(" + _NAME + r")(?:\s(?:and|&)\s" + _NAME + r"|\set\sal\.?)?,?\s(\d{4}[a-z]?)(?=[;,)\s]|$)")
_NARRATIVE = re.compile(r"(" + _NAME + r")(?:\s(?:and|&)\s" + _NAME + r"|\set\sal\.?)?\s\((\d{4}[a-z]?)(?:[;,][^)]*)?\)")
_PAREN = re.compile(r"\(([^()]{4,400})\)")
_NOT_AUTHOR = {"In", "Proceedings", "Journal", "Transactions", "URL", "Available", "Advances", "Conference", "The",
               "Table", "Figure", "Fig", "Section", "Eq", "Equation", "Appendix", "January", "February", "March",
               "April", "May", "June", "July", "August", "September", "October", "November", "December", "Spring",
               "Summer", "Fall", "Winter", "Version", "Accessed", "Retrieved", "Online", "Vol", "Volume", "IEEE",
               "ACM", "Association", "Springer", "Press", "University", "Neural", "International", "Annual",
               "Workshop", "Symposium", "Since", "Until", "Before", "After", "During", "From", "Year", "Step", "Phase"}
# a sentence that begins an author-year entry: "Abadi, M., Barham, P., ..." or "Iz Beltagy, Kyle Lo, and Arman Cohan."
_HEAD_SURNAME_FIRST = re.compile(r"^(" + _NAME + r"),\s(?:[A-Z]\.\s?-?)+")
_HEAD_NAME_FIRST = re.compile(r"^((?:[A-Z][a-zÀ-ſ'\-]+|[A-Z]\.)(?:\s(?:[A-Z]\.|[A-Z][a-zÀ-ſ'\-]+))*"
                              r"\s(" + _NAME + r"))(?:,|\sand\s|\.$|\s\()")

MIN_ENTRIES = 5          # fewer recognised entries: the list was not read well enough to check
MIN_CITATIONS = 3        # fewer in-text citations: the citation style was not recognised
NOT_A_CITATION_ABOVE = 10   # "[256, 480]" (an interval) is not a citation: a bracket citing far past the list is skipped
_HEADING = re.compile(r"^\s*(?:\d+\.?\s*|[A-Z]\.?\s+)?(References|REFERENCES|Bibliography|BIBLIOGRAPHY|Literature Cited|"
                      r"LITERATURE CITED|Works Cited|Reference List)\s*:?\s*$")


def reference_text(pdf_path) -> str:
    """The text after the last "References" heading, read straight from the PDF.

    The sentence parser can drop or move a few reference lines (a two-column page, a line it took for a page header);
    a citation that cannot be matched in the parsed list is checked against this raw text before it is reported."""
    import pymupdf
    lines: list[str] = []
    start = None
    with pymupdf.open(pdf_path) as pdf:
        for pg in pdf:
            for ln in pg.get_text().splitlines():
                if _HEADING.match(ln):
                    start = len(lines)
                lines.append(ln)
    if start is None:
        return ""
    text = "\n".join(lines[start + 1:])
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    return re.sub(r"\s+", " ", text)


def _expand(group: str) -> list[int]:
    out = []
    for part in re.split(r"\s*[,;]\s*", group):
        m = re.match(r"^(\d{1,3})\s*[" + _DASH + r"]\s*(\d{1,3})$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b <= a + 50:
                out.extend(range(a, b + 1))
        elif part.strip().isdigit():
            out.append(int(part))
    return out


def _numbered_entries(text: str) -> tuple[str, list[dict]]:
    """Find a run of entry markers 1, 2, 3 ... ("[1] ...", "1. ...") in the reference text; ([] if none)."""
    best: tuple[str, list[dict]] = ("", [])
    for style, pat in (("bracket", r"(?:^|\s)\[{n}\]\s"), ("dot", r"(?:^|\s){n}\.\s+(?=[A-Za-zÀ-ſ])")):
        pos, starts = 0, []
        n = 1
        while True:
            m = re.compile(pat.format(n=n)).search(text, pos)
            if not m:
                break
            starts.append((n, m.start(), m.end()))
            pos, n = m.end(), n + 1
        if len(starts) > len(best[1]):
            entries = []
            for i, (num, _s, e) in enumerate(starts):
                end = starts[i + 1][1] if i + 1 < len(starts) else len(text)
                entries.append({"n": num, "text": text[e:end].strip()})
            best = (style, entries)
    return best


def _author_year_entries(refs) -> list[dict]:
    entries: list[dict] = []
    for i, s in enumerate(refs):
        t = s.text.strip()
        m1, m2 = _HEAD_SURNAME_FIRST.match(t), _HEAD_NAME_FIRST.match(t)
        nxt = refs[i + 1].text.strip() if i + 1 < len(refs) else ""
        year_here = _YEAR.search(t)
        year_next = re.match(r"^\(?(\d{4}[a-z]?)\)?\.", nxt)
        surname = None
        if m1 and m1.group(1).split()[-1] not in _NOT_AUTHOR:
            surname = m1.group(1).split()[-1]
        elif m2 and m2.group(1).split()[0] not in _NOT_AUTHOR and m2.group(2) not in _NOT_AUTHOR \
                and (year_next or (year_here and t.endswith((").", ")")))):
            surname = m2.group(2).split()[-1]
        if not surname or not (year_here or year_next or m1):
            if entries:                      # continuation of the previous entry (title, venue, pages)
                entries[-1]["text"] += " " + t
            continue
        entries.append({"text": t, "page": s.page, "surname": surname})
    for e in entries:
        y = _YEAR.search(e["text"])
        e["year"] = y.group(1) if y else ""
    return entries


def _intext_author_year(body) -> list[dict]:
    out = []
    for s in body:
        found = set()
        for pm in _PAREN.finditer(s.text):
            for m in _PAREN_ITEM.finditer(pm.group(1)):
                found.add((m.group(1), m.group(2), m.group(0).strip()))
        for m in _NARRATIVE.finditer(s.text):
            found.add((m.group(1), m.group(2), m.group(0).strip()))
        for name, year, label in sorted(found):
            last = name.split()[-1]
            if last in _NOT_AUTHOR or not _YEAR.fullmatch(year):
                continue
            out.append({"surname": last, "year": year[:4], "label": label, "page": s.page,
                        "sentence_id": s.id, "quote": s.text})
    return out


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", t.lower())


def _profile(entries: list[dict], paper_year: int | None) -> dict:
    years = [int(_YEAR.search(e["text"]).group(1)) for e in entries if _YEAR.search(e["text"])]
    newest = paper_year or (max(years) if years else None)
    prof = {"n_entries": len(entries), "with_year": len(years),
            "preprints": sum(1 for e in entries if _PREPRINT.search(e["text"])),
            "with_doi_or_link": sum(1 for e in entries if _LINK.search(e["text"])),
            "newest_year": max(years) if years else None, "median_year": sorted(years)[len(years) // 2] if years else None}
    if newest and years:
        prof["last_5_years"] = sum(1 for y in years if y >= newest - 4)
        prof["reference_year"] = newest
    return prof


def _duplicates(entries: list[dict]) -> list[tuple[dict, dict]]:
    seen: dict[str, dict] = {}
    dups = []
    for e in entries:
        # the same text, or the same opening (authors, year, title) and the same DOI or arXiv id: one work listed twice.
        # An identifier alone is not enough: a DOI broken across lines leaves only its journal prefix ("10.1097/QAI."),
        # which many entries share; two volumes of one report share their opening but not their identifier.
        doi = re.search(r"\b10\.\d{4,9}/[^\s,;]+", e["text"])
        arx = re.search(r"(?<![\d.])(\d{4}\.\d{4,5})(?:v\d+)?(?![\d.])", e["text"])
        text = _norm(e["text"])
        head = text[:60]
        keys = [k for k in ("doi:" + doi.group(0).rstrip(".").lower() + "|" + head if doi else "",
                            "arxiv:" + arx.group(1) + "|" + head if arx else "",
                            "text:" + text if len(text) >= 40 else "") if k]
        hit = next((seen[k] for k in keys if k in seen), None)
        if hit is not None:
            dups.append((hit, e))
        for k in keys:
            seen.setdefault(k, e)
    return dups


def _paper_year(doc: Document) -> int | None:
    """Year of the paper, from an arXiv identifier in the file name or front matter (else None)."""
    m = re.search(r"(?<!\d)(\d{2})(\d{2})\.\d{4,5}(?:v\d)?(?!\d)", doc.source_name or "")
    if m and 7 <= int(m.group(1)) <= 40 and 1 <= int(m.group(2)) <= 12:
        return 2000 + int(m.group(1))
    return None


def check_citations(doc: Document, raw_refs: str = "") -> dict:
    """raw_refs: optional reference_text() of the PDF, used to segment a numbered list and to confirm a citation
    before reporting it as missing."""
    refs = [s for s in doc.sentences if s.section == "references" and s.kind in ("text", "meta")]
    body = [s for s in doc.sentences if s.section not in ("references", "acknowledgments")]
    findings: list[dict] = []
    res = {"style": "none", "n_entries": 0, "n_citations": 0, "findings": findings, "profile": {},
           "checked": False, "note": "", "counts": {},
           "method": "Fixed text rules over the reference list and the in-text citations; nothing is looked up online.",
           "caveat": ("A finding means the rule could not match a citation and an entry, which can also happen when the "
                      "PDF splits the reference list in unusual places. Check the quoted text before acting on it.")}
    if not refs:
        res["note"] = "No reference list was recognised in this PDF, so citations could not be checked."
        return res
    text = " ".join(s.text for s in refs)
    style, numbered = _numbered_entries(text)
    if raw_refs:
        raw_style, raw_numbered = _numbered_entries(raw_refs)
        if len(raw_numbered) >= len(numbered):      # same count: the raw text keeps each entry whole
            style, numbered = raw_style, raw_numbered
    page_of = refs[0].page

    def add(kind, severity, message, quote="", page=None, sentence_id=None):
        findings.append({"id": f"C{len(findings) + 1}", "kind": kind, "severity": severity, "message": message,
                         "quote": quote[:300], "page": page, "sentence_id": sentence_id})

    if len(numbered) >= MIN_ENTRIES:
        res["style"] = "numbered"
        entries = numbered
        cites: dict[int, list] = {}
        for s in body:
            for m in _IEEE_RANGE.finditer(s.text):
                a, b = int(m.group(1)), int(m.group(2))
                if 0 < a < b <= min(a + 50, len(numbered) + NOT_A_CITATION_ABOVE):
                    for n in range(a + 1, b):
                        cites.setdefault(n, []).append(s)
            for m in _BRACKET.finditer(s.text):
                nums = _expand(m.group(1))
                if not nums or 0 in nums or max(nums) > len(numbered) + NOT_A_CITATION_ABOVE:
                    continue        # an interval, an image size or a coordinate, not a citation
                for n in nums:
                    cites.setdefault(n, []).append(s)
        res["n_entries"], res["n_citations"] = len(entries), sum(len(v) for v in cites.values())
        if len(cites) < MIN_CITATIONS:
            res["note"] = ("The reference list is numbered, but too few bracketed citations like [3] were found in the "
                           "text (superscript numbers are not recognised), so citations were not matched to entries.")
        else:
            res["checked"] = True
            top = len(entries)
            beyond = sorted(k for k in cites if k > top)
            if len(beyond) > 3:     # many numbers past the end: the list was cut short in reading, not in the paper
                res["checked"] = False
                res["note"] = (f"Citations go up to [{beyond[-1]}] but only {top} numbered entries could be read from "
                               "the list, so the list was probably not read completely; citations were not matched.")
            else:
                for n in beyond:
                    s = cites[n][0]
                    add("cited_not_listed", "medium",
                        f"Reference [{n}] is cited in the text but the list has only {top} numbered entries.",
                        s.text, s.page, s.id)
                for e in entries:
                    if e["n"] not in cites:
                        add("listed_not_cited", "low", f"Entry [{e['n']}] in the reference list is never cited as "
                            f"[{e['n']}] in the text.", e["text"], page_of)
    else:
        entries = _author_year_entries(refs)
        intext = _intext_author_year(body)
        res["n_entries"], res["n_citations"] = len(entries), len(intext)
        if len(entries) < MIN_ENTRIES:
            res["note"] = "The entries of the reference list could not be told apart reliably, so citations were not checked."
            res["n_entries"] = 0
            entries = []
        elif len(intext) < MIN_CITATIONS:
            res["style"] = "author-year"
            res["note"] = ("Too few in-text citations like (Smith et al., 2020) were recognised, so citations were "
                           "not matched to entries.")
        else:
            res["style"], res["checked"] = "author-year", True
            low = (text + " " + raw_refs).lower()
            reported = set()
            for c in intext:
                key = (c["surname"], c["year"])
                if key in reported:
                    continue
                # matched when the surname occurs in the list with the year close behind it (any author position)
                ok = any(m for m in re.finditer(re.escape(c["surname"].lower()), low)
                         if c["year"] in low[m.start(): m.start() + 900])
                if not ok:
                    reported.add(key)
                    add("cited_not_listed", "medium",
                        f"\"{c['label']}\" is cited in the text but no entry by {c['surname']} from {c['year']} "
                        "was found in the reference list.", c["quote"], c["page"], c["sentence_id"])
            cited = {(c["surname"].lower(), c["year"]) for c in intext}
            cited_names = {c["surname"].lower() for c in intext}
            for e in entries:
                if e["year"] and (e["surname"].lower(), e["year"]) not in cited and e["surname"].lower() not in cited_names:
                    add("listed_not_cited", "low",
                        f"The entry by {e['surname']} ({e['year']}) is never cited in the text as "
                        f"\"{e['surname']} ... {e['year']}\".", e["text"], e["page"])
    if entries:
        for a, b in _duplicates(entries):
            add("duplicate_entry", "low", "The same reference appears twice in the list.", b["text"], b.get("page", page_of))
        # an arXiv-only entry carries its year in the identifier (arXiv:1207.7214), which is normal in some fields
        no_year = [e for e in entries if not _YEAR.search(e["text"]) and not _ARXIV_ID.search(e["text"])]
        if no_year and len(no_year) <= len(entries) // 2:
            for e in no_year[:10]:
                add("entry_without_year", "low", "This reference entry has no year.", e["text"], e.get("page", page_of))
        res["profile"] = _profile(entries, _paper_year(doc))
    kinds = Counter(f["kind"] for f in findings)
    res["counts"] = dict(kinds)
    return res
