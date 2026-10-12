"""PDF -> structured Document (sentences with page, section, tables).

Uses PyMuPDF. Section detection combines font-size/boldness cues with a
vocabulary of standard paper headings; this is heuristic and the Document
carries warnings whenever extraction looks unreliable (e.g. scanned PDFs).
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from .models import Document, Sentence
from .textutils import UNMAPPED, split_sentences

CANONICAL = {
    "abstract": "abstract", "summary": "abstract",
    "introduction": "introduction",
    "background": "background",
    "related work": "related", "related works": "related", "literature review": "related",
    "preliminaries": "background",
    "method": "method", "methods": "method", "methodology": "method", "approach": "method",
    "model": "method", "proposed method": "method", "our approach": "method",
    "materials and methods": "method", "system": "method", "architecture": "method",
    "experiments": "experiments", "experimental setup": "experiments", "experiment": "experiments",
    "experimental settings": "experiments", "implementation details": "experiments",
    "setup": "experiments", "evaluation": "experiments", "experimental design": "experiments",
    "datasets": "experiments", "dataset": "experiments", "training details": "experiments",
    "results": "results", "results and discussion": "results", "main results": "results",
    "experimental results": "results", "findings": "results", "analysis": "results",
    "ablation": "results", "ablation study": "results", "ablation studies": "results",
    "discussion": "discussion",
    "limitations": "limitations", "limitation": "limitations", "threats to validity": "limitations",
    "conclusion": "conclusion", "conclusions": "conclusion", "conclusion and future work": "conclusion",
    "concluding remarks": "conclusion", "future work": "conclusion",
    "references": "references", "bibliography": "references",
    "acknowledgments": "acknowledgments", "acknowledgements": "acknowledgments",
    "appendix": "appendix", "supplementary material": "appendix",
    "ethics statement": "ethics", "ethical considerations": "ethics", "broader impact": "ethics",
    "reproducibility": "reproducibility", "reproducibility statement": "reproducibility",
    "code availability": "reproducibility", "data availability": "reproducibility",
}
BODY_SECTIONS = {"introduction", "background", "method", "experiments", "results", "discussion",
                 "limitations", "conclusion", "related", "reproducibility", "ethics", "other"}

# Labels of a structured abstract ("Objective / Methods / Results / Conclusion"). They are sub-headings of the
# abstract, not body sections, as long as each appears once and the first one directly follows "Abstract".
_SA_LABELS = {"objective", "objectives", "purpose", "aim", "aims", "background", "context", "motivation", "importance",
              "design", "setting", "participants", "measurements", "method", "methods", "methods and findings",
              "methodology/principal findings", "results", "main results", "findings", "conclusion", "conclusions",
              "conclusions/significance", "interpretation", "significance", "availability", "trial registration"}
_SA_OPENERS = {"objective", "objectives", "purpose", "aim", "aims", "motivation"}  # never a body heading

_NUM_PREFIX = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]+\.|[A-Z]\.)\s+")
_NUM_ONLY = re.compile(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]+\.|[A-Z]\.)$")
_HEADING_FULL = re.compile(r"^(?:(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]+\.)\s+)?[A-Z][A-Za-z0-9 ,:&\-()/]{2,70}$")
_BOLD_FONT = re.compile(r"bold|black|heavy|demi|[.\-_]B$", re.I)
# Publisher front-matter and identifiers: kept (the rubric reads them) but never a claim or evidence.
_FOOTNOTE_START = re.compile(r"^(?:[∗*†‡§¶]|\d{1,2}(?=[A-Z][a-z]))")
_META_RE = re.compile(r"^(?:Citation|Editor|Academic Editor|Received|Accepted|Published|Copyright|Funding|"
                      r"Competing [Ii]nterests|Abbreviations)\s*:|\bdoi:\s?10\.\d{4}|doi\.org/10\.\d{4}|©|"
                      r"\bOPEN ACCESS\b|^arXiv:\d{4}\.\d{4,5}")


def canonical_section(heading: str, exact: bool = False) -> str | None:
    h = _NUM_PREFIX.sub("", heading.strip()).strip().rstrip(":.").lower()
    if h in CANONICAL:
        return CANONICAL[h]
    if exact:
        return None
    for key in sorted(CANONICAL, key=len, reverse=True):
        if len(key) >= 6 and h.startswith(key + " "):
            return CANONICAL[key]
    return None


def _is_numbered_heading(text: str) -> bool:
    return bool(re.match(r"^(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]+\.)\s+[A-Z]", text)) and len(text) <= 80 and not text.endswith(".")


def _heading_number(text: str) -> list[str] | None:
    """'4.1. ImageNet' -> ['4', '1'];  'II. OBSERVATION' -> ['II'];  unnumbered -> None."""
    m = re.match(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s+\S", text)
    if m:
        return m.group(1).split(".")
    m = re.match(r"^([IVX]+)\.\s+\S", text)
    return [m.group(1)] if m else None


def _join_lines(lines: list[str]) -> str:
    """Join wrapped lines, repairing end-of-line hyphenation ("represen-" + "tation")."""
    out = ""
    for ln in lines:
        if out.endswith("-") and ln[:1].islower() and len(out) > 1 and out[-2].isalpha():
            out = out[:-1] + ln
        else:
            out = f"{out} {ln}" if out else ln
    return out


def _running_headers(pages) -> set[str]:
    """Lines repeated on many pages (running heads, footers)."""
    n = len(pages)
    if n < 4:
        return set()
    counts: dict[str, int] = {}
    for pg in pages:
        for t in {re.sub(r"\d+", "#", ln[0]) for ln in pg["lines"]}:
            counts[t] = counts.get(t, 0) + 1
    return {t for t, c in counts.items() if c >= max(3, int(0.5 * n)) and len(t) < 90}


def _clean(text: str) -> tuple[str, int]:
    """Normalise ligatures and control characters. Returns (text, n_unmapped_between_digits).

    A control character between two digits is a glyph the PDF's font could not map to text, very often the
    decimal point. It is NOT guessed: it becomes U+FFFD so that 13?4 is never read as 134, and the caller warns.
    """
    text = text.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff") \
               .replace("ﬃ", "ffi").replace("ﬄ", "ffl")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text, n = re.subn(r"(?<=\d)[\x00-\x08\x0b-\x1f](?=\d)", UNMAPPED, text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", " ", text)
    return re.sub(r"[ \t]+", " ", text), n


def _line_text(spans) -> str:
    """Concatenate a line's spans, keeping whitespace-only spans and restoring a space wherever two spans are
    separated by a visible horizontal gap (justified text often has no space character between word spans)."""
    out, prev = "", None
    for s in spans:
        t = s["text"]
        if not t:
            continue
        if prev is not None and t.strip() and out and not out[-1].isspace() and not t[0].isspace():
            if s["bbox"][0] - prev["bbox"][2] > 0.15 * min(s["size"], prev["size"]):
                out += " "
        out += t
        if t.strip():
            prev = s
    return out


def _page_lines(page) -> list[tuple]:
    """Horizontal text lines of a page as (text, size, bold, y0, block_no, bbox), in reading order."""
    out: list[tuple] = []
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            dx, dy = line.get("dir", (1.0, 0.0))
            if abs(dx - 1.0) > 0.05 or abs(dy) > 0.05:
                continue  # rotated text: arXiv margin stamp, vertical axis labels
            spans = [s for s in line.get("spans", []) if s["text"].strip()]
            if not spans:
                continue
            text = _line_text(line.get("spans", [])).strip()
            size = max(s["size"] for s in spans)
            bold = all((s["flags"] & 16) or _BOLD_FONT.search(s["font"]) for s in spans)
            bb = tuple(line["bbox"])
            if out:
                p = out[-1]
                # a section number set as its own line ("6.1" then "Machine Translation" on the same baseline)
                if _NUM_ONLY.match(p[0]) and abs(p[5][1] - bb[1]) < 3 and 0 <= bb[0] - p[5][2] < 3 * size:
                    out[-1] = (f"{p[0]} {text}", max(size, p[1]), bold and p[2], min(p[3], bb[1]), p[4],
                               (p[5][0], min(p[5][1], bb[1]), bb[2], max(p[5][3], bb[3])))
                    continue
            out.append((text, size, bold, bb[1], block["number"], bb))
    return out


UNREADABLE_WARNING = "Very little extractable text: the PDF may be scanned. OCR is not enabled."


def _margin_lines(lines: list[tuple], page_width: float) -> set[int]:
    """Indices of lines in a narrow strip left of the main text column (publisher sidebars, line numbers)."""
    if len(lines) < 8:
        return set()
    weight: Counter = Counter()
    for ln in lines:
        weight[round(ln[5][0] / 4) * 4] += len(ln[0])
    main_x0 = weight.most_common(1)[0][0]
    idx = [i for i, ln in enumerate(lines) if ln[5][2] < main_x0 - 4]
    if not idx:
        return set()
    chars = sum(len(lines[i][0]) for i in idx)
    span = max(lines[i][5][2] for i in idx) - min(lines[i][5][0] for i in idx)
    if span < 0.28 * page_width and chars < 0.45 * sum(len(ln[0]) for ln in lines):
        return set(idx)
    return set()  # a real text column (two-column layout), not a margin


def _tables(page) -> list[tuple[tuple, list[str]]]:
    """Return [(bbox, row_sentences)] for tables found on a page."""
    found = []
    try:
        for tab in page.find_tables().tables:
            data = tab.extract()
            if not data:
                continue
            header = [str(c or "").strip() for c in data[0]]
            rows = []
            for r in data[1:]:
                cells = [str(c or "").strip() for c in r]
                if not any(cells):
                    continue
                parts = [f"{h}: {c}" if h and c and i else c for i, (h, c) in enumerate(zip(header, cells))]
                rows.append("Table row: " + "; ".join(p for p in parts if p))
            found.append((tuple(tab.bbox), rows))
    except Exception:
        pass
    return found


def _inside(bbox, box, pad=2.0) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return box[0] - pad <= cx <= box[2] + pad and box[1] - pad <= cy <= box[3] + pad


def parse_pdf(path: str | Path, doc_id: str | None = None) -> Document:
    import pymupdf

    path = Path(path)
    raw = path.read_bytes()
    doc_id = doc_id or hashlib.sha1(raw).hexdigest()[:12]
    pdf = pymupdf.open(stream=raw, filetype="pdf")
    return _build(pdf, doc_id, path.name)


def _title(page0: dict, fallback: str) -> str:
    """Largest-font run of lines in the top half of page 1 (drop caps and one-word labels are ignored)."""
    cand = [ln for ln in page0["lines"] if ln[3] < 0.5 * page0["height"] and len(ln[0]) >= 8]
    if not cand:
        return fallback
    mx = max(ln[1] for ln in cand)
    top = [ln for ln in page0["lines"] if ln[3] < 0.5 * page0["height"] and abs(ln[1] - mx) <= 0.5 and len(ln[0]) >= 2]
    return " ".join(ln[0] for ln in top)[:200] or fallback


def _next_section(st: dict, text: str, canon: str | None, size: float, bold: bool, pno: int) -> str:
    """Section label for the text that follows a heading. Sub-headings inherit their parent's section."""
    label = _NUM_PREFIX.sub("", text).strip().rstrip(":.").lower()
    num = _heading_number(text)
    if num is None and label in _SA_LABELS and label not in st["sa_seen"]:
        in_abs = st["section"] == "abstract" and st["abs_n"] < 40 and (st["sa_seen"] or st["abs_n"] == 0)
        opens = st["section"] == "front" and pno <= 2 and label in _SA_OPENERS
        if in_abs or opens:
            st["sa_seen"].add(label)
            return "abstract"
    if num and len(num) >= 2:                      # "4.1 ..." belongs to whatever "4 ..." is
        parent = st["tops"].get(num[0])
        if parent and parent != "other":
            return parent
        # under a custom-named parent only an exact standard name counts ("5.5 Background modelling" is not Background)
        return canonical_section(text, exact=True) or parent or ("references" if st["ref"] else "other")
    if num:
        sec = canon or ("references" if st["ref"] else "other")
        st["tops"][num[0]] = sec
        st["top"] = (size, bold, True)
        return sec
    if canon:
        st["top"] = (size, bold, False)
        return canon
    if st["ref"]:
        return "references"
    top_size, top_bold, top_numbered = st["top"]
    smaller = size < top_size - 0.3 or (top_bold and not bold and size <= top_size + 0.1)
    if st["section"] not in ("front", "abstract") and (smaller or top_numbered):
        return st["section"]                       # lighter or unnumbered run-in heading inside a section
    st["top"] = (size, bold, False)
    return "other"


def _build(pdf, doc_id: str, name: str) -> Document:
    warnings: list[str] = []
    pages = []
    size_chars: Counter = Counter()
    for pno, page in enumerate(pdf, start=1):
        tables = _tables(page)
        lines = [ln for ln in _page_lines(page) if not any(_inside(ln[5], tb[0]) for tb in tables)]
        pages.append({"pno": pno, "tables": tables, "lines": lines,
                      "width": page.rect.width, "height": page.rect.height})
    repeated = _running_headers(pages)
    for pg in pages:
        if repeated:
            pg["lines"] = [ln for ln in pg["lines"] if re.sub(r"\d+", "#", ln[0]) not in repeated]
        margin = _margin_lines(pg["lines"], pg["width"])
        pg["margin"] = [ln for i, ln in enumerate(pg["lines"]) if i in margin]
        pg["lines"] = [ln for i, ln in enumerate(pg["lines"]) if i not in margin]
        for ln in pg["lines"]:
            size_chars[round(ln[1], 1)] += len(ln[0])
    total_chars = sum(len(ln[0]) for pg in pages for ln in pg["lines"])
    if total_chars < 40 * max(1, len(pdf)):
        warnings.append(UNREADABLE_WARNING)
    body = size_chars.most_common(1)[0][0] if size_chars else 10.0   # size carrying the most characters

    title = _clean(_title(pages[0], name))[0].strip() if pages else name

    sentences: list[Sentence] = []
    st = {"section": "front", "heading": "", "sid": 0, "ref": False, "tops": {}, "top": (0.0, False, False), "sa_seen": set(), "abs_n": 0, "unmapped": 0}

    for pg in pages:
        pno, tables, lines = pg["pno"], pg["tables"], pg["lines"]
        buf: list[str] = []

        def flush(section=None, force_kind=None):
            if not buf:
                return
            text, n_bad = _clean(_join_lines(buf))
            st["unmapped"] += n_bad
            buf.clear()
            sec = section or st["section"]
            for sent in split_sentences(text):
                if len(sent) < 25 and not re.search(r"\d", sent):
                    continue
                kind = force_kind or ("caption" if re.match(r"^(Table|Figure|Fig\.|FIG\.)\s*\d+", sent)
                                      else "meta" if _META_RE.search(sent) else "text")
                sentences.append(Sentence(st["sid"], sent, pno, sec, st["heading"], kind))
                st["sid"] += 1
                if sec == "abstract":
                    st["abs_n"] += 1

        pending_tables = sorted(tables, key=lambda t: t[0][1])

        def emit_tables(until_y):
            while pending_tables and pending_tables[0][0][1] <= until_y:
                _, rows = pending_tables.pop(0)
                flush()
                if st["section"] == "references":
                    continue
                sec = st["section"] if st["section"] != "front" else "results"
                for row in rows:
                    row, n_bad = _clean(row)
                    st["unmapped"] += n_bad
                    sentences.append(Sentence(st["sid"], row, pno, sec, st["heading"], "table"))
                    st["sid"] += 1

        prev_block = last_block = note_block = None
        notes: list[str] = []
        for text, size, bold, y, block_no, _bb in lines:
            emit_tables(y)
            if re.fullmatch(r"\d{1,3}", text) and (y < 60 or y > 700):
                continue  # page number
            if block_no != last_block:
                last_block = block_no
                # a small-print block in the lower half that opens with a footnote mark (author notes, URLs)
                note_block = block_no if (size <= body - 0.9 and y > 0.5 * pg["height"]
                                          and _FOOTNOTE_START.match(text)) else None
            if note_block == block_no:
                notes.append(text)
                continue
            if st["section"] == "acknowledgments" and re.match(r"^\[1\]\s", text):
                flush()  # reference list that has no "References" heading
                st["section"], st["heading"], st["ref"] = "references", "References", True
            canon = canonical_section(text) if len(text) < 80 else None
            is_head = False
            if not (text[:1].isupper() or text[:1].isdigit()):
                pass
            elif canon and (bold or size > body + 0.5 or _is_numbered_heading(text) or text.isupper()):
                is_head = True
            elif (size > body + 1.0 or bold) and _HEADING_FULL.match(text) and not text.endswith(".") \
                    and len(text.split()) <= 8 and st["section"] != "front" and size >= body - 0.1:
                is_head = True
            elif _is_numbered_heading(text) and (bold or size > body + 0.3):
                is_head = True
            if is_head:
                flush()
                st["section"] = _next_section(st, text, canon, size, bold, pno)
                st["heading"] = text
                if st["section"] == "references":
                    st["ref"] = True
                continue
            if prev_block is not None and block_no != prev_block and buf and buf[-1].endswith("."):
                flush()
            prev_block = block_no
            if st["section"] == "front" and size > body + 2:
                continue  # title lines
            buf.append(text)
        flush()
        emit_tables(1e9)
        if notes:
            buf.extend(notes)
            flush(force_kind="meta")
        if pg["margin"]:
            buf.extend(ln[0] for ln in pg["margin"])
            flush(section="front", force_kind="meta")

    if not any(s.section == "abstract" for s in sentences):
        front = [s for s in sentences if s.section == "front" and s.page == 1 and s.kind != "meta"]
        if front:
            for s in front:
                s.section = "abstract"
            warnings.append("No 'Abstract' heading detected; treated the front matter as the abstract.")
    if not any(s.section in ("results", "experiments") for s in sentences):
        warnings.append("No results/experiments section detected; evidence linking will be weak.")
    if st["unmapped"]:
        warnings.append(f"{st['unmapped']} number(s) contain a character this PDF's font does not map to text "
                        f"(often the decimal point). They are shown with '{UNMAPPED}' and excluded from numeric matching.")
    return Document(doc_id=doc_id, title=title, n_pages=len(pdf), sentences=sentences,
                    source_name=name, warnings=warnings)
