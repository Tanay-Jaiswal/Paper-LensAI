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
_ITALIC_FONT = re.compile(r"ital|oblique|[.\-_]I$|[.\-_]It$|TI\d*$", re.I)
# an appendix label set as its own line: "A" or "A.1" next to "Model implementation details"
_APX_ONLY = re.compile(r"^[A-Z](?:\.\d{1,2})*$")
_APX_HEAD = re.compile(r"^([A-Z])((?:\.\d{1,2})+)?(\.?)\s+(?=[A-Z0-9(\"“])")
# a heading that may span lines: the single-line character set plus quotes, "?" and "_"
_HEADING_SHAPE = re.compile(r"^(?:(?:\d{1,2}(?:\.\d{1,2})*\.?|[IVX]+\.)\s+)?[A-Z][A-Za-z0-9 ,:&\-()/_?'’“”\"]{2,160}$")
_LIGATURES = str.maketrans({"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"})   # "Classiﬁcation" must match
_NOT_HEADING = re.compile(r"^(?:Table|Figure|Fig\.?|FIG\.?|Algorithm|Box|Scheme|Listing|Equation|Eq\.)\s*\d")
_LEADERS = re.compile(r"(?:\.\s?){5,}")
_DANGLING = {"a", "an", "the", "of", "for", "and", "or", "to", "in", "on", "with", "that", "by", "from", "at", "as",
             "is", "are", "be", "its", "their", "our", "vs", "vs.", "via", "using", "between", "into"}
_SENTENCE_OPENERS = {"we", "it", "this", "these", "there", "they", "he", "she", "here"}
_RUNIN_ABSTRACT = re.compile(r"^(abstract|summary)\s*[.:—–\-]\s*(\S.*)$", re.I)
_KEYWORDS_LINE = re.compile(r"^(?:key\s?words?|index terms)\s*[:—–\-.]", re.I)
_SPACED_CAPS = re.compile(r"^(?:[A-Z] ){3,}[A-Z]$")
# Words that name a standard section when they open or close a heading the vocabulary does not list
# ("4 User Evaluation", "Summary and Conclusions"). Weaker than an exact name and than sub-heading inheritance.
_HEAD_WORDS = {"conclusion": "conclusion", "conclusions": "conclusion", "concluding": "conclusion",
               "results": "results", "findings": "results",
               "experiment": "experiments", "experiments": "experiments", "experimental": "experiments",
               "evaluation": "experiments", "evaluations": "experiments",
               "discussion": "discussion", "discussions": "discussion",
               "limitations": "limitations", "methods": "method", "methodology": "method",
               "architecture": "method"}
_HEAD_STOP = {"the", "a", "an", "our", "of", "and", "on", "for", "in", "to", "with", "vs", "vs.", "main", "overall"}
ABSTRACT_MAX_SENTENCES = 30        # a longer "abstract" means its end was probably missed: warn, do not guess
NO_ABSTRACT_HEADING = "No 'Abstract' heading detected; treated the first prose paragraph of page 1 as the abstract."
NO_ABSTRACT = ("No abstract could be identified (no 'Abstract' heading and no prose paragraph before the first "
               "section heading); claims are taken from the other sections only.")
# Publisher front-matter and identifiers: kept (the rubric reads them) but never a claim or evidence.
_FOOTNOTE_START = re.compile(r"^(?:[∗*†‡§¶]|\d{1,2}(?=[A-Z][a-z]))")
_META_RE = re.compile(r"^(?:Citation|Editor|Academic Editor|Received|Accepted|Published|Copyright|Funding|"
                      r"Competing [Ii]nterests|Abbreviations)\s*:|\bdoi:\s?10\.\d{4}|doi\.org/10\.\d{4}|©|"
                      r"\bOPEN ACCESS\b|^arXiv:\d{4}\.\d{4,5}")


def canonical_section(heading: str, exact: bool = False) -> str | None:
    h = _NUM_PREFIX.sub("", heading.strip()).strip().rstrip(":.")
    if _SPACED_CAPS.match(h):                      # "A B S T R A C T"
        h = h.replace(" ", "")
    h = h.lower()
    if h in CANONICAL:
        return CANONICAL[h]
    if exact:
        return None
    for key in sorted(CANONICAL, key=len, reverse=True):
        # "Summary and Conclusions" is not the abstract: the abstract is only ever an exact name
        if len(key) >= 6 and h.startswith(key + " ") and CANONICAL[key] != "abstract":
            return CANONICAL[key]
    return None


def keyword_section(heading: str) -> str | None:
    """Standard section named by the first or last content word of a short heading, or None."""
    words = [w.strip(",:;()").lower() for w in _NUM_PREFIX.sub("", heading.strip()).rstrip(":.").split()]
    words = [w for w in words if w and w not in _HEAD_STOP]
    if not words or len(words) > 4:
        return None
    return _HEAD_WORDS.get(words[0]) or _HEAD_WORDS.get(words[-1])


def _appendix_letter(text: str) -> tuple[str, bool, bool] | None:
    """'A.1 Parameters' -> ('A', True, False);  'B. Proofs' -> ('B', False, True);  'A Details' -> ('A', False, False)."""
    m = _APX_HEAD.match(text)
    return (m.group(1), bool(m.group(2)), bool(m.group(3))) if m else None


def _seq_ok(last: list[int] | None, num: list[str]) -> bool:
    """Is section number `num` a plausible successor of the last numbered heading seen ('4' -> '4.1' or '5')?"""
    try:
        cur = [int(x) for x in num]
    except ValueError:
        return False
    if not last:
        return cur in ([1], [0])
    for k in range(1, len(last) + 1):              # next sibling at any level (one missed heading is tolerated)
        if len(cur) == k and cur[:-1] == last[:k - 1] and 1 <= cur[-1] - last[k - 1] <= 2:
            return True
    if cur[-1] in (0, 1):                          # first child of the last heading, or of its missed successor
        parent = cur[:-1]
        if parent == last:
            return True
        for k in range(1, len(last) + 1):
            if len(parent) == k and parent[:-1] == last[:k - 1] and 0 <= parent[-1] - last[k - 1] <= 1:
                return True
    return False


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
    edge: dict[str, int] = {}
    for pg in pages:
        for t in {re.sub(r"\d+", "#", ln[0]) for ln in pg["lines"]}:
            counts[t] = counts.get(t, 0) + 1
        h = pg.get("height") or 0
        # the same text in the top or bottom strip of several pages (alternating author / title heads)
        for t in {re.sub(r"\d+", "#", ln[0]) for ln in pg["lines"] if h and (ln[3] < 0.08 * h or ln[3] > 0.92 * h)}:
            edge[t] = edge.get(t, 0) + 1
    out = {t for t, c in counts.items() if c >= max(3, int(0.5 * n)) and len(t) < 90}
    return out | {t for t, c in edge.items() if c >= max(3, -(-n // 5)) and len(t) < 90}


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
    """Horizontal text lines of a page as (text, size, bold, y0, block_no, bbox, italic), in reading order."""
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
            text = _line_text(line.get("spans", [])).strip().translate(_LIGATURES)
            size = max(s["size"] for s in spans)
            # bold / italic by share of characters: one symbol or italic variable must not unbold a heading
            n_chars = sum(len(s["text"].strip()) for s in spans) or 1
            n_bold = sum(len(s["text"].strip()) for s in spans if (s["flags"] & 16) or _BOLD_FONT.search(s["font"]))
            n_ital = sum(len(s["text"].strip()) for s in spans if (s["flags"] & 2) or _ITALIC_FONT.search(s["font"]))
            bold, italic = n_bold >= 0.75 * n_chars, n_ital >= 0.75 * n_chars
            bb = tuple(line["bbox"])
            if out:
                p = out[-1]
                same_line = abs(p[5][1] - bb[1]) < 3 and 0 <= bb[0] - p[5][2] < 3 * size
                # a section number set as its own line ("6.1" then "Machine Translation" on the same baseline);
                # an appendix label ("A", "A.1") only when both parts are set in the same weight and size
                if same_line and (_NUM_ONLY.match(p[0]) or (_APX_ONLY.match(p[0]) and p[2] == bold
                                                             and abs(p[1] - size) <= 0.5 and text[:1].isupper())):
                    out[-1] = (f"{p[0]} {text}", max(size, p[1]), bold and p[2], min(p[3], bb[1]), p[4],
                               (p[5][0], min(p[5][1], bb[1]), bb[2], max(p[5][3], bb[3])), italic and p[6])
                    continue
            out.append((text, size, bold, bb[1], block["number"], bb, italic))
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
    sec = _classify_heading(st, text, canon, size, bold, pno)
    if sec in ("conclusion", "acknowledgments", "references"):
        st["tail"] = True                          # from here on a heading "A ..." can open the appendices
    if sec not in ("front", "abstract"):
        st["body_seen"] = True
    num = _heading_number(text)
    if num and num[0].isdigit():
        st["last_num"] = [int(x) for x in num]
    return sec


def _classify_heading(st: dict, text: str, canon: str | None, size: float, bold: bool, pno: int) -> str:
    label = _NUM_PREFIX.sub("", text).strip().rstrip(":.").lower()
    num = _heading_number(text)
    if num is None and label in _SA_LABELS and label not in st["sa_seen"]:
        in_abs = st["section"] == "abstract" and st["abs_n"] < 40 and (st["sa_seen"] or st["abs_n"] == 0)
        opens = st["section"] == "front" and pno <= 2 and label in _SA_OPENERS
        if in_abs or opens:
            st["sa_seen"].add(label)
            return "abstract"
    early = pno <= 2 and (not st.get("body_seen") or (label == "abstract" and st["abs_n"] == 0))
    if canon == "abstract" and not (st["section"] in ("front", "abstract") or early):
        # "Summary" after the body has started closes the paper; it is not a second abstract
        canon = "conclusion" if label.startswith("summary") else None
    apx = None if num else _appendix_letter(text)
    if apx:
        letter, sub, _dotted = apx
        last = st.get("apx", "")
        if sub:
            ok = st["section"] == "appendix" and (not last or letter == last)
        elif last:
            ok = st["section"] == "appendix" and last < letter <= chr(ord(last) + 3)
        else:                                      # the first appendix is "A", after the conclusion or references
            ok = letter == "A" and (st["ref"] or st.get("tail") or st["section"] == "appendix")
        if ok:
            st["apx"] = letter
            st["top"] = (size, bold, True)
            return "appendix"
    if st["section"] == "appendix" and st.get("tail") and canon not in ("references", "acknowledgments"):
        return "appendix"                          # appendix sub-headings, whatever they are called
    if num and len(num) >= 2:                      # "4.1 ..." belongs to whatever "4 ..." is
        parent = st["tops"].get(num[0])
        if parent and parent != "other":
            return parent
        # under a custom-named parent only an exact standard name counts ("5.5 Background modelling" is not Background)
        return canonical_section(text, exact=True) or parent or ("references" if st["ref"] else "other")
    if num:
        sec = canon or ("references" if st["ref"] else keyword_section(text) or "other")
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
    return keyword_section(text) or "other"


def _is_toc_page(lines: list[tuple], prev_toc: bool) -> bool:
    """A table-of-contents page: a 'Contents' title or dot leaders, and many lines that are only a page number."""
    if len(lines) < 6:
        return False
    marks = sum(1 for ln in lines if _LEADERS.search(ln[0]) or re.fullmatch(r"\d{1,3}|[ivxlc]{1,6}", ln[0]))
    leaders = sum(1 for ln in lines if _LEADERS.search(ln[0]))
    titled = any(re.fullmatch(r"(?:table of )?contents", ln[0].strip(), re.I) for ln in lines[:8])
    if titled and marks >= 5:
        return True
    if leaders >= 8 and marks >= 0.3 * len(lines):
        return True
    return prev_toc and marks >= 5 and marks >= 0.3 * len(lines)


def _style_run(lines: list[tuple], i: int, limit: int = 12) -> list[int]:
    """Indices of the lines that continue line i in the same size and weight, directly below it or on its baseline.

    One or two such lines are the rest of a wrapped heading; many are a paragraph set in bold or large type."""
    s0, b0 = lines[i][1], lines[i][2]
    run = [i]
    for k in range(i + 1, min(len(lines), i + limit)):
        a, b = lines[run[-1]], lines[k]
        if abs(b[1] - s0) > 0.2 or b[2] != b0:
            break
        dy = b[3] - a[3]
        below = 0.5 * s0 < dy <= 1.7 * s0 and b[5][0] < a[5][2] and b[5][2] > a[5][0]
        beside = abs(dy) <= 0.9 * s0 and b[5][0] >= a[5][0] - 2 and b[5][0] - a[5][2] <= 1.5 * s0
        if below and not beside and len(run) == 1 and b[0][:1].isupper() \
                and (_heading_number(a[0]) or _appendix_letter(a[0])):
            # under a numbered heading, a capitalised line whose first word had room on the line above is a second
            # heading stacked under the first ("C.1 Corpus" over "Source journals"), not the rest of a wrapped one
            col_right = max(o[5][2] for o in lines if o[5][0] <= a[5][0] + 5 and o[5][2] > a[5][0])
            first_word = (b[5][2] - b[5][0]) * len(b[0].split()[0]) / max(1, len(b[0]))
            below = a[5][2] + 0.25 * s0 + first_word > col_right
        if not (below or beside):
            break
        apx = _appendix_letter(b[0])
        if _heading_number(b[0]) or (apx and (apx[1] or apx[2])) or canonical_section(b[0], exact=True):
            break                                  # the next heading, not a continuation of this one
        run.append(k)
    return run


def _row_cell(lines: list[tuple], i: int) -> bool:
    """Is line i one cell of a row (a short neighbour on the same baseline, a clear gap away)? Table headers
    such as 'Method | Results' and contents entries with their page number are not headings."""
    text, size, _, y, _, bb = lines[i][:6]
    for j in (i - 1, i + 1):
        if 0 <= j < len(lines):
            o = lines[j]
            if abs(o[3] - y) < 0.4 * size and len(o[0]) < 40 and o[2] == lines[i][2] and abs(o[1] - size) <= 0.2:
                gap = o[5][0] - bb[2] if o[5][0] >= bb[2] else bb[0] - o[5][2]
                if gap > 1.5 * size:
                    return True
    return False


def _heading_ok(text: str, max_words: int) -> bool:
    """Shape tests every heading must pass: short, no sentence end, no open bracket, no dangling last word."""
    words = text.split()
    if not words or len(text) > 160 or len(words) > max_words or text.endswith((".", ",", ";", "-")):
        return False
    if text.count("(") != text.count(")"):
        return False                               # "O2peak)" is the tail of a heading, not a heading
    return words[-1].lower() not in _DANGLING or len(words) == 1


def _heading_at(lines: list[tuple], i: int, st: dict, body: float, pno: int, no_head: set) -> tuple | None:
    """Decide whether a heading (or a pull quote) starts at line i.

    Returns ("head", n_lines, text, canonical) or ("display", n_lines, text, None), or None for ordinary text.
    Rules, in order: a standard section name that is typographically marked; a numbered heading that is bold or
    larger; an appendix label ("A.1 ...", "B. ..."); an italic numbered heading whose number continues the
    sequence; a short bold or large line. Lines that wrap are joined before the shape tests.
    """
    ln = lines[i]
    text, size, bold = ln[0], ln[1], ln[2]
    italic = ln[6] if len(ln) > 6 else False
    if i in no_head or not (text[:1].isupper() or text[:1].isdigit()):
        return None
    if _NOT_HEADING.match(text) or _LEADERS.search(text) or _row_cell(lines, i):
        return None                                # caption label, contents entry, table header cell
    canon = canonical_section(text) if len(text) < 80 else None
    exact = canonical_section(text, exact=True) if canon else None
    numbered = _is_numbered_heading(text)
    emph = bold or size > body + 0.3
    run = _style_run(lines, i) if emph and not exact else [i]
    joined = None
    if 1 < len(run) <= 4:
        joined = _join_lines([lines[k][0] for k in run])
        if not _heading_ok(joined, 16):
            joined = None
    n, full = (len(run), joined) if joined else (1, text)

    plain_abstract = exact == "abstract" and st["section"] == "front" and pno <= 2 and len(text.split()) == 1
    if canon and (bold or size > body + 0.5 or numbered or text.isupper() or plain_abstract) \
            and text.count("(") == text.count(")"):
        return ("head", n, full, canon)
    if numbered and emph:
        return ("head", n, full, canonical_section(full) if len(full) < 80 else None)
    apx = None if numbered else _appendix_letter(text)
    if apx and emph and st["section"] != "front" and _heading_ok(full, 16):
        if apx[1] or apx[2]:
            return ("head", n, full, None)         # "A.1 Parameters", "B. Proofs"
        last = st.get("apx", "")
        follows = last < apx[0] <= chr(ord(last) + 3) if last else apx[0] == "A"
        if follows and (st.get("tail") or st["section"] == "appendix") and _HEADING_SHAPE.match(full):
            return ("head", n, full, None)         # "H Results on All Tasks for All Model Sizes"
    if numbered and italic and len(text) <= 70 and _seq_ok(st.get("last_num"), _heading_number(text) or []):
        return ("head", 1, text, None)             # same size as the body, set in italics ("4.1. Event selection")
    if not ((size > body + 1.0 or bold) and st["section"] != "front" and size >= body - 0.1):
        return None
    if len(run) > 1 and not joined:
        # bold or large text that runs on: a lead sentence, a bold paragraph or a pull quote, never a heading
        no_head.update(run)
        if 2 <= len(run) <= 6 and size >= body + 3:
            return ("display", len(run), _join_lines([lines[k][0] for k in run]), None)
        return None
    words = full.split()
    if words[0].lower() in _SENTENCE_OPENERS and len(words) >= 4:
        return None                                # "We find that ..." in bold is a sentence
    shape = _HEADING_SHAPE if joined else _HEADING_FULL
    if shape.match(full) and _heading_ok(full, 16 if joined else 8):
        return ("head", n, full, canonical_section(full) if len(full) < 80 else None)
    return None


def _is_prose(sents: list[Sentence], min_words: int) -> bool:
    """Running text rather than an author list, affiliations or dates: enough words, mostly lower-case ones."""
    if any(s.kind != "text" for s in sents):
        return False
    words = " ".join(s.text for s in sents).split()
    if len(words) < min_words or any("@" in w for w in words):
        return False
    return sum(1 for w in words if w[:1].islower()) >= 0.6 * len(words)


def _headless_abstract(chunks: list[tuple[list[Sentence], float]]) -> list[Sentence]:
    """With no 'Abstract' heading: the first prose paragraph of the page-1 front matter, plus the paragraphs
    that directly follow it in the same type size. Title, authors, affiliations and dates stay front matter."""
    for k, (sents, size) in enumerate(chunks):
        if _is_prose(sents, 40):
            out = list(sents)
            for more, msize in chunks[k + 1:]:
                if abs(msize - size) > 0.2 or not _is_prose(more, 12):
                    break
                out += more
            return out
    return []


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
    prev_toc = False
    for pg in pages:
        pg["toc"] = prev_toc = _is_toc_page(pg["lines"], prev_toc)
        if repeated:
            pg["lines"] = [ln for ln in pg["lines"] if re.sub(r"\d+", "#", ln[0]) not in repeated]
        # a bold standard heading left of a hanging-indent reference list is not a sidebar
        margin = {i for i in _margin_lines(pg["lines"], pg["width"])
                  if not (pg["lines"][i][2] and canonical_section(pg["lines"][i][0], exact=True))}
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
    st = {"section": "front", "heading": "", "sid": 0, "ref": False, "tops": {}, "top": (0.0, False, False),
          "sa_seen": set(), "abs_n": 0, "unmapped": 0, "tail": False, "body_seen": False, "apx": "", "last_num": None,
          "buf_size": 0.0}
    chunks: list[tuple[list[Sentence], float]] = []    # front-matter paragraphs of page 1, in order, with font size

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
            made = []
            for sent in split_sentences(text):
                if len(sent) < 25 and not re.search(r"\d", sent):
                    continue
                kind = force_kind or ("caption" if re.match(r"^(Table|Figure|Fig\.|FIG\.)\s*\d+", sent)
                                      else "meta" if _META_RE.search(sent) else "text")
                sentences.append(Sentence(st["sid"], sent, pno, sec, st["heading"], kind))
                made.append(sentences[-1])
                st["sid"] += 1
                if sec == "abstract":
                    st["abs_n"] += 1
            if sec == "front" and pno == 1 and not force_kind and made:
                chunks.append((made, st["buf_size"]))

        if pg["toc"]:
            # a contents page lists every heading again: keep its text as front matter, read no structure from it
            buf.extend(ln[0] for ln in lines)
            flush(section="front", force_kind="meta")
            continue

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
        prev_size = prev_y = note_y = None
        notes: list[str] = []
        no_head: set[int] = set()
        i = 0
        while i < len(lines):
            text, size, bold, y, block_no = lines[i][:5]
            i += 1
            emit_tables(y)
            if re.fullmatch(r"\d{1,3}", text) and (y < 60 or y > 700):
                continue  # page number
            if block_no != last_block:
                last_block = block_no
                # a small-print block in the lower half that opens with a footnote mark (author notes, URLs), and
                # the small print below it (venue line, "Author contributions listed at end of paper.")
                small_low = size <= body - 0.9 and y > 0.5 * pg["height"]
                note_block = block_no if small_low and (_FOOTNOTE_START.match(text)
                                                        or (note_y is not None and y > note_y)) else None
                if note_block is not None and note_y is None:
                    note_y = y
            if note_block == block_no:
                notes.append(text)
                continue
            if st["section"] == "acknowledgments" and re.match(r"^\[1\]\s", text):
                flush()  # reference list that has no "References" heading
                st["section"], st["heading"], st["ref"] = "references", "References", True
            if pno <= 2 and st["section"] in ("front", "abstract"):
                m = _RUNIN_ABSTRACT.match(text)
                if m and st["section"] == "front":
                    # "Abstract. We show ..." / "Abstract— We show ...": the heading and the text share a line
                    flush()
                    st["section"], st["heading"], st["top"] = "abstract", m.group(1), (size, True, False)
                    buf.append(m.group(2))
                    st["buf_size"], prev_block, prev_size, prev_y = size, block_no, size, y
                    continue
                if _KEYWORDS_LINE.match(text):
                    flush()                        # the keyword list closes the abstract and is not part of it
                    note_block = block_no
                    notes.append(text)
                    if st["section"] == "abstract":
                        st["section"], st["heading"] = "other", ""
                    continue
            found = _heading_at(lines, i - 1, st, body, pno, no_head)
            if found and found[0] == "head":
                _, n, htext, canon = found
                htext = _clean(htext)[0].strip()
                flush()
                st["section"] = _next_section(st, htext, canon, size, bold, pno)
                st["heading"] = htext
                if st["section"] == "references":
                    st["ref"] = True
                i += n - 1
                continue
            if found:                              # pull quote: repeats body text in display type
                flush()
                buf.append(found[2])
                flush(section="front" if st["section"] == "abstract" else None, force_kind="meta")
                if st["section"] == "abstract":
                    st["section"], st["heading"] = "other", ""      # display text ends the abstract
                i += found[1] - 1
                continue
            if prev_block is not None and block_no != prev_block and buf and buf[-1].endswith("."):
                flush()
            elif st["section"] == "front" and buf and prev_size is not None and (
                    abs(size - prev_size) > 0.3 or y - prev_y > 1.7 * size or y < prev_y - 2 * size):
                flush()                            # title, authors, dates and the abstract are separate paragraphs
            prev_block, prev_size, prev_y = block_no, size, y
            if st["section"] == "front" and size > body + 2:
                continue  # title lines
            if not buf:
                st["buf_size"] = size
            buf.append(text)
        flush()
        emit_tables(1e9)
        if notes:
            buf.extend(notes)
            flush(force_kind="meta")
        if pg["margin"]:
            buf.extend(ln[0] for ln in pg["margin"])
            flush(section="front", force_kind="meta")

    if not any(s.section == "abstract" for s in sentences) and sentences and UNREADABLE_WARNING not in warnings:
        picked = _headless_abstract(chunks)
        for s in picked:
            s.section, s.heading = "abstract", ""
        warnings.append(NO_ABSTRACT_HEADING if picked else NO_ABSTRACT)
    n_abs = sum(1 for s in sentences if s.section == "abstract" and s.kind == "text")
    if n_abs > ABSTRACT_MAX_SENTENCES:
        warnings.append(f"The detected abstract is unusually long ({n_abs} sentences); its end was probably not "
                        "detected, so part of it may be body text.")
    if not any(s.section in ("results", "experiments") for s in sentences):
        warnings.append("No results/experiments section detected; evidence linking will be weak.")
    if st["unmapped"]:
        warnings.append(f"{st['unmapped']} number(s) contain a character this PDF's font does not map to text "
                        f"(often the decimal point). They are shown with '{UNMAPPED}' and excluded from numeric matching.")
    return Document(doc_id=doc_id, title=title, n_pages=len(pdf), sentences=sentences,
                    source_name=name, warnings=warnings)
