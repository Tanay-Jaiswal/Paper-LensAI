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
_CAPTION_START = re.compile(r"^(?:Table|Figure|Fig\.|FIG\.)\s*\d+\s*[:.]")
_SENTENCE_END = re.compile(r"[.?!:;)\]\"”’']\s*$")
ABSTRACT_END_GAP = 2.0             # white band (in font sizes) after abstract text that ends the abstract
ABSTRACT_MAX_SENTENCES = 30        # a longer "abstract" means its end was probably missed: warn, do not guess
NO_ABSTRACT_HEADING = "No 'Abstract' heading detected; treated the first prose paragraph of page 1 as the abstract."
NO_ABSTRACT = ("No abstract could be identified (no 'Abstract' heading and no prose paragraph before the first "
               "section heading); claims are taken from the other sections only.")
# Publisher front-matter and identifiers: kept (the rubric reads them) but never a claim or evidence.
_FOOTNOTE_START = re.compile(r"^(?:[∗*†‡§¶]|\d{1,2}\s?(?=[A-Z][a-z]))")
_META_START = re.compile(r"^(?:Citation|Editor|Academic Editor|Received|Accepted|Published|Copyright|Funding|"
                         r"Competing [Ii]nterests?|Abbreviations)\s*:")   # a small-print box of publisher data
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
    # alternating heads ("Author names" / "Short title") appear on every other page: two sightings are enough there
    return out | {t for t, c in edge.items() if c >= max(2, -(-n // 5)) and len(t) < 90 and len(re.findall("[A-Za-z]", t)) >= 4}


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
    """Horizontal text lines of a page as (text, size, bold, y0, block_no, bbox, italic, spans), in stream order."""
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
                               (p[5][0], min(p[5][1], bb[1]), bb[2], max(p[5][3], bb[3])), italic and p[6],
                               p[7] + spans)
                    continue
            out.append((text, size, bold, bb[1], block["number"], bb, italic, spans))
    return out


def _make_line(spans: list, block_no: int) -> tuple:
    """A line tuple from a subset of another line's spans (used when a line is cut at a column gutter)."""
    text = _line_text(spans).strip().translate(_LIGATURES)
    n = sum(len(s["text"].strip()) for s in spans) or 1
    bold = sum(len(s["text"].strip()) for s in spans if (s["flags"] & 16) or _BOLD_FONT.search(s["font"])) >= 0.75 * n
    ital = sum(len(s["text"].strip()) for s in spans if (s["flags"] & 2) or _ITALIC_FONT.search(s["font"])) >= 0.75 * n
    bb = (min(s["bbox"][0] for s in spans), min(s["bbox"][1] for s in spans),
          max(s["bbox"][2] for s in spans), max(s["bbox"][3] for s in spans))
    return (text, max(s["size"] for s in spans), bold, bb[1], block_no, bb, ital, spans)


# ---- column-aware reading order ----------------------------------------------------------------------------------
# The content stream of a PDF need not follow the reading order (word processors and some converters write lines or
# blocks sorted by position; layout tools write them in any order). The order is rebuilt from geometry, XY-cut style:
#   1. a vertical gutter (a strip of at least GUTTER_MIN points that no text crosses, with at least FLANK_MIN_LINES
#      prose lines on each side) splits the region into columns, read left to right;
#   2. otherwise the region is cut horizontally at its widest white band; the strips are read top to bottom;
#   3. a region that can be cut no further keeps its stream order if that order already runs downwards, and is
#      sorted by position otherwise.
# A page that has no gutter anywhere is left exactly as the PDF delivers it. If a white band crosses the whole
# width of a region that also has a gutter, rows or columns are both defensible: the rows are read first and the
# page is reported as ambiguous.
GUTTER_MIN = 4.0
FLANK_MIN_LINES = 3
FLANK_MIN_CHARS = 25
BAND_MIN = 1.5            # white band, in font sizes, across a region that also has a gutter


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0.0


def _vertical_cut(lines: list[tuple]):
    """(left, right) if a column gutter splits `lines`, else None. Lines that cross the gutter between their spans
    are cut in two; no line has a span over the gutter by construction."""
    iv = sorted((sp["bbox"][0], sp["bbox"][2]) for ln in lines for sp in ln[7])
    gaps, end = [], iv[0][1]
    for a, b in iv[1:]:
        if a - end >= GUTTER_MIN:
            gaps.append((end, a))
        end = max(end, b)
    best = None
    for g0, g1 in gaps:
        left = [[sp for sp in ln[7] if sp["bbox"][2] <= g0 + 0.01] for ln in lines]
        right = [[sp for sp in ln[7] if sp["bbox"][0] >= g1 - 0.01] for ln in lines]
        ln_l = [(i, sps) for i, sps in enumerate(left) if sps]
        ln_r = [(i, sps) for i, sps in enumerate(right) if sps]
        if len(ln_l) < FLANK_MIN_LINES or len(ln_r) < FLANK_MIN_LINES:
            continue
        if _median([sum(len(sp["text"].strip()) for sp in sps) for _, sps in ln_l]) < FLANK_MIN_CHARS                 or _median([sum(len(sp["text"].strip()) for sp in sps) for _, sps in ln_r]) < FLANK_MIN_CHARS:
            continue                                # a table or a list of short items, not two text columns
        if best is None or g1 - g0 > best[0]:
            best = (g1 - g0, left, right)
    if not best:
        return None
    _, left, right = best
    out_l, out_r = [], []
    for ln, ls, rs in zip(lines, left, right):
        if ls and rs:
            out_l.append(_make_line(ls, ln[4]))
            out_r.append(_make_line(rs, ln[4]))
        elif ls:
            out_l.append(ln)
        else:
            out_r.append(ln)
    return out_l, out_r


def _white_bands(lines: list[tuple], min_gap: float):
    """[(gap, y_cut)] for every horizontal white band >= min_gap between two groups of lines."""
    order = sorted(lines, key=lambda ln: ln[5][1])
    bands, reach = [], order[0][5][3]
    for ln in order[1:]:
        if ln[5][1] - reach >= min_gap:
            bands.append((ln[5][1] - reach, (reach + ln[5][1]) / 2))
        reach = max(reach, ln[5][3])
    return bands


def _leaf(lines: list[tuple]) -> list[tuple]:
    """Stream order if it already runs downwards (a superscript may sit a little higher), position order otherwise."""
    for a, b in zip(lines, lines[1:]):
        if b[5][1] < a[5][1] - 0.7 * a[1]:
            if _side_by_side(lines):
                return lines                        # columns we could not separate: sorting would interleave them
            return sorted(lines, key=lambda ln: (round(ln[5][1]), ln[5][0]))
    return lines


def _order_region(lines: list[tuple], info: dict) -> list[tuple]:
    if len(lines) < 2:
        return lines
    size = _median([ln[1] for ln in lines]) or 10.0
    cut = _vertical_cut(lines) if len(lines) >= 2 * FLANK_MIN_LINES else None
    if cut:
        # a band across both columns with plenty of text above and below it (a page number alone does not count):
        # read the rows first, and say that columns would be an equally valid reading
        for gap, cy in sorted(_white_bands(lines, BAND_MIN * size), reverse=True):
            top = [ln for ln in lines if ln[5][3] <= cy + 0.01]
            bot = [ln for ln in lines if ln[5][3] > cy + 0.01]
            # both columns must have text on both sides of the band; a column that ends above it is simply finished
            both = all(sum(1 for ln in side if ln[5][3] <= cy + 0.01) >= FLANK_MIN_LINES
                       and sum(1 for ln in side if ln[5][3] > cy + 0.01) >= FLANK_MIN_LINES for side in cut)
            if both and len(top) >= 2 * FLANK_MIN_LINES and len(bot) >= 2 * FLANK_MIN_LINES:
                info["ambiguous"] = True
                return _order_region(top, info) + _order_region(bot, info)
        info["columns"] = True
        return _order_region(cut[0], info) + _order_region(cut[1], info)
    bands = _white_bands(lines, 0.3 * size)
    if bands:
        cy = max(bands)[1]
        top = [ln for ln in lines if ln[5][3] <= cy + 0.01]
        bot = [ln for ln in lines if ln[5][3] > cy + 0.01]
        if top and bot:
            return _order_region(top, info) + _order_region(bot, info)
    return _leaf(lines)


def _reorder_columns(lines: list[tuple]) -> tuple[list[tuple], dict]:
    """Lines of a page in reading order, and {"columns": bool, "ambiguous": bool}."""
    info = {"columns": False, "ambiguous": False}
    if len(lines) < 2 * FLANK_MIN_LINES:
        return lines, info
    out = _order_region(lines, info)
    if info["columns"] or info["ambiguous"]:
        return out, info
    if _side_by_side(lines):
        return lines, info                          # columns we could not separate: keep the PDF's order
    return _leaf(lines), info                       # one column: an out-of-order stream is sorted by position


def _side_by_side(lines: list[tuple]) -> bool:
    """Do two lines share a baseline band with a horizontal gap between them (columns, table rows)?"""
    for i, a in enumerate(lines):
        for b in lines[i + 1:]:
            overlap = min(a[5][3], b[5][3]) - max(a[5][1], b[5][1])
            if overlap > 0.5 * min(a[5][3] - a[5][1], b[5][3] - b[5][1]) and                     (b[5][0] - a[5][2] >= GUTTER_MIN or a[5][0] - b[5][2] >= GUTTER_MIN):
                return True
    return False


UNREADABLE_WARNING = "Very little extractable text: the PDF may be scanned. OCR is not enabled."
AMBIGUOUS_LAYOUT = ("Layout warning: on page(s) {pages} the text blocks form a grid, so the reading order (rows or "
                    "columns) is ambiguous. Rows were read first; sentences were not mixed across blocks.")


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


# ---- tables without a grid ----------------------------------------------------------------------------------------
# `page.find_tables()` needs drawn rules. A table set with white space only (or with a few horizontal rules) reaches
# the parser as ordinary lines, and its cells used to be joined into "sentences" and glued to the prose around them.
# Such a table is recognised from geometry alone:
#   1. every line is cut into cells at gaps wider than CELL_GAP font sizes; cells on one baseline form a row;
#   2. a full line of prose (PROSE_WORDS words or more, mostly not numbers) is never a cell: it ends the row, so text
#      in the neighbouring column of a two-column page stays out;
#   3. a data row has at least two values, or a label followed by one value, and no mathematical operator; data rows
#      that follow each other and whose values stand above each other form a table. One row alone needs three values;
#   4. a cell at the end of a row that stands under or over nothing in the other rows and lies far from its
#      neighbour is not part of the table (the last words of a line in the next column that share the baseline);
#   5. the rows directly above (column heads) and short lines between the data rows (group labels) belong to it.
# What is found is taken out of the running text. A data row with a row label becomes a `table` sentence in the format
# of ruled tables; heads, group labels and rows without a label are kept as `meta` (never a claim, never evidence) and
# a row without a label is reported in a warning. Nothing is guessed: cells are never re-ordered or merged across rows.
# Each row leaves a placeholder line (block number below zero, no text) where it stood, so that the reading order is
# worked out with the table still occupying its space, and the rows are emitted at that place in the text.
CELL_GAP = 0.7            # font sizes between two spans of a line that separate two cells (a word space is about 0.3)
CELL_GAP_MIN = 4.0        # ... and at least this many points
PROSE_WORDS = 7
NUMERIC_ROW_LABEL = 3     # a line of at most this many label words ...
NUMERIC_ROW_VALUES = 4    # ... followed only by at least this many numbers is a row of values, whatever its spacing
ROW_LEAD = 3.2            # font sizes between the baselines of two data rows of one table (one label row may intervene)
HEAD_LEAD = 2.6           # font sizes from the first data row up to a row of column heads
_PLACEHOLDER = {"-", "–", "—", "--", "n/a", "N/A", "NA", "n.a.", "×", "✓", "✗"}
_EQ_NUMBER = re.compile(r"^\(\s*\d{1,3}[a-z]?\s*\)$")
_MATH = re.compile(r"[=≤≥≠∥√∑∏∫∞∈∂→←⊗⊕∀∃∇]")
UNLABELLED_ROWS = ("Table text without row labels on page(s) {pages}: the rows are kept, but they are not used as "
                   "evidence because the quantity each number belongs to could not be determined.")


def _numeric_cell(text: str) -> bool:
    """A cell that holds a value: it starts with a digit or a sign and has at least as many digits as letters
    ("19.9 ± 0.4", "12.4M", "3.5 h", "45%"). "F1", "GPT-3", an equation and an equation number are not values."""
    t = text.strip()
    if _EQ_NUMBER.match(t) or len(t) > 28 or "=" in t or not re.match(r"[\d+\-–−±<>≤≥~≈$.(]", t):
        return False
    digits = sum(ch.isdigit() for ch in t)
    return digits > 0 and digits >= sum(ch.isalpha() for ch in t)


def _prose_cell(text: str) -> bool:
    """A line of running text, not a cell: five or more words, mostly lower-case words, few numbers (narrow columns
    hold only five or six words a line), or PROSE_WORDS words of any kind as long as most are not numbers."""
    words = text.split()
    nums = sum(1 for w in words if re.search(r"\d", w))
    if len(words) >= 5 and nums < 0.3 * len(words) and sum(1 for w in words if w[:1].islower()) >= 0.6 * len(words):
        return True
    return len(words) >= PROSE_WORDS and nums < 0.5 * len(words)


def _cells(lines: list[tuple]) -> list[dict]:
    """Cells of a page: runs of spans on one line with no gap wider than CELL_GAP between them."""
    out = []
    for li, ln in enumerate(lines):
        spans = sorted(ln[7], key=lambda s: s["bbox"][0])
        if _prose_cell(ln[0]):
            # a loosely justified line of prose has wide gaps between its words: it is one piece of text, never cells
            out.append({"text": ln[0], "bbox": ln[5], "size": ln[1], "line": li, "spans": spans, "num": False, "prose": True})
            continue
        toks = ln[0].split()
        k = next((i for i, t in enumerate(toks) if _numeric_cell(t)), len(toks))
        listed = any(t[-1] in ",;]" or t[0] in "[(" for t in toks[k:])   # "35, 37–43, 46," is a wrapped citation list
        if k <= NUMERIC_ROW_LABEL and len(toks) - k >= NUMERIC_ROW_VALUES and not listed \
                and all(_numeric_cell(t) for t in toks[k:]):
            # a row of values typed with ordinary spaces ("Score 0.61 0.47 0.52 0.53"): no gap marks its cells, but
            # a short label followed by nothing except numbers is never a line of prose. Cell boxes are estimated.
            parts = ([" ".join(toks[:k])] if k else []) + toks[k:]
            x0, x1, pos, n = ln[5][0], ln[5][2], 0, sum(len(p) for p in parts) + len(parts) - 1
            for j, part in enumerate(parts):
                bb = (x0 + (x1 - x0) * pos / n, ln[5][1], x0 + (x1 - x0) * (pos + len(part)) / n, ln[5][3])
                out.append({"text": part, "bbox": bb, "size": ln[1], "line": li, "spans": spans,
                            "num": j > 0 or not k, "prose": False})
                pos += len(part) + 1
            continue
        run = []
        for sp in spans + [None]:
            if sp is not None and (not run or sp["bbox"][0] - run[-1]["bbox"][2] <= max(CELL_GAP * ln[1], CELL_GAP_MIN)):
                run.append(sp)
                continue
            if run:
                text = _line_text(run).strip().translate(_LIGATURES)
                bb = (min(s["bbox"][0] for s in run), min(s["bbox"][1] for s in run),
                      max(s["bbox"][2] for s in run), max(s["bbox"][3] for s in run))
                if text:
                    out.append({"text": text, "bbox": bb, "size": ln[1], "line": li, "spans": run,
                                "num": _numeric_cell(text), "prose": _prose_cell(text)})
            run = [sp] if sp is not None else []
    return out


def _gutters(cells: list[dict], page_width: float) -> list[tuple[float, float]]:
    """Column gutters of the page, from its prose lines alone: vertical strips that no prose line narrower than
    0.6 of the page crosses, with at least FLANK_MIN_LINES prose lines on each side."""
    iv = sorted((c["bbox"][0], c["bbox"][2]) for c in cells if c["prose"] and c["bbox"][2] - c["bbox"][0] < 0.6 * page_width)
    out, end = [], None
    for k, (a, b) in enumerate(iv):
        if end is not None and a - end >= GUTTER_MIN:
            left = sum(1 for x in iv if x[1] <= end + 0.01)
            right = sum(1 for x in iv if x[0] >= a - 0.01)
            if left >= FLANK_MIN_LINES and right >= FLANK_MIN_LINES:
                out.append((end, a))
        end = b if end is None else max(end, b)
    return out


def _baseline_rows(cells: list[dict], max_gap: float, gutters=()) -> list[list[dict]]:
    """Cells grouped by baseline, left to right, and cut at prose cells, at gaps wider than `max_gap`, and at a column
    gutter unless there are at least two values on each side of it (a table that spans the columns)."""
    rows: list[list[dict]] = []
    for c in sorted(cells, key=lambda c: ((c["bbox"][1] + c["bbox"][3]) / 2, c["bbox"][0])):
        yc = (c["bbox"][1] + c["bbox"][3]) / 2
        if rows and abs(yc - rows[-1][0]["yc"]) < 0.45 * min(c["size"], rows[-1][0]["size"]):
            rows[-1].append(c)
        else:
            c["yc"] = yc
            rows.append([c])
        c["yc"] = rows[-1][0]["yc"]
    segs = []
    for row in rows:
        seg: list[dict] = []
        for c in sorted(row, key=lambda c: c["bbox"][0]):
            if c["prose"] or (seg and c["bbox"][0] - seg[-1]["bbox"][2] > max_gap):
                if seg:
                    segs.append(seg)
                seg = []
            if not c["prose"]:
                seg.append(c)
        if seg:
            segs.append(seg)
    for g0, g1 in gutters:
        cut = []
        for seg in segs:
            left = [c for c in seg if c["bbox"][2] <= g0 + 1.0]
            right = [c for c in seg if c["bbox"][0] >= g1 - 1.0]
            if left and right and len(left) + len(right) == len(seg) \
                    and (sum(c["num"] for c in left) < 2 or sum(c["num"] for c in right) < 2):
                cut += [left, right]
            else:
                cut.append(seg)
        segs = cut
    return segs


def _x_overlap(a, b) -> float:
    return min(a[2], b[2]) - max(a[0], b[0])


def _seg_box(seg: list[dict]) -> tuple:
    return (min(c["bbox"][0] for c in seg), min(c["bbox"][1] for c in seg),
            max(c["bbox"][2] for c in seg), max(c["bbox"][3] for c in seg))


def _aligned_columns(rows: list[list[dict]]) -> int:
    """Number of x-positions at which numeric cells of at least two different rows stand above each other."""
    iv = sorted((c["bbox"][0], c["bbox"][2], ri) for ri, row in enumerate(rows) for c in row if c["num"])
    n, cur_end, members = 0, None, set()
    for x0, x1, ri in iv + [(float("inf"), float("inf"), -1)]:
        if cur_end is not None and x0 <= cur_end:
            members.add(ri)
            cur_end = max(cur_end, x1)
            continue
        if len(members) >= 2:
            n += 1
        cur_end, members = x1, {ri}
    return n


def _prune_strays(g: list[list[dict]]) -> list[list[dict]]:
    """Drop end cells that align with no cell of another row and lie apart from their neighbour; drop rows left with one cell."""
    if len(g) < 2:
        return g
    far = 1.5 * g[0][0]["size"]
    out = []
    for src in g:
        r = list(src)
        changed = True
        while changed and len(r) >= 2:
            changed = False
            for edge, nb in ((r[-1], r[-2]), (r[0], r[1])):
                alone = not any(_x_overlap(edge["bbox"], c["bbox"]) > 0 for o in g if o is not src for c in o)
                gap = max(edge["bbox"][0] - nb["bbox"][2], nb["bbox"][0] - edge["bbox"][2])
                if alone and gap > far:
                    r.remove(edge)
                    changed = True
                    break
        if len(r) >= 2 and any(c["num"] for c in r):
            out.append(r)
    return out


def _open_tables(lines: list[tuple], page_width: float) -> tuple[list[list[tuple]], list[tuple], bool]:
    """Tables without a grid among `lines`. Returns ([rows of table 0, rows of table 1, ...], the other lines with one
    placeholder per table row (block number -(table index + 1)), unlabelled rows present?). A row is (text, kind)."""
    if len(lines) < 2:
        return [], lines, False
    cells = _cells(lines)
    segs = _baseline_rows(cells, 0.45 * page_width, _gutters(cells, page_width))

    def is_data(seg):
        """At least two values, or a label followed by one value. A number followed by words is a numbered heading
        or a list item ("4 Experiments"), and a row with mathematical operators is part of a formula."""
        nums = sum(c["num"] for c in seg)
        if len(seg) < 2 or _CAPTION_START.match(seg[0]["text"]) \
                or any(_LEADERS.search(c["text"]) or _MATH.search(c["text"]) for c in seg):
            return False
        return nums >= 2 or (nums == 1 and seg[-1]["num"] and len(seg) == 2)

    data = sorted((s for s in segs if is_data(s)), key=lambda s: s[0]["yc"])
    groups: list[list[list[dict]]] = []
    for seg in data:
        box, size = _seg_box(seg), seg[0]["size"]
        for g in reversed(groups):
            last = _seg_box(g[-1])
            gbox = (min(_seg_box(r)[0] for r in g), 0, max(_seg_box(r)[2] for r in g), 0)
            if 0 < seg[0]["yc"] - g[-1][0]["yc"] <= ROW_LEAD * size \
                    and _x_overlap(box, gbox) > 0.5 * min(box[2] - box[0], gbox[2] - gbox[0]) and last is not None:
                g.append(seg)
                break
        else:
            groups.append([seg])
    found, used = [], {}
    unlabelled = False
    for g in groups:
        g = _prune_strays(g)
        if not g:
            continue
        cols = _aligned_columns(g)
        strong = [r for r in g if sum(c["num"] for c in r) >= 3]
        if not ((len(g) >= 2 and cols >= 2) or (len(g) >= 3 and cols >= 1) or (len(g) == 1 and strong)):
            continue
        if len(g) >= 2 and cols == 0:
            continue
        size = g[0][0]["size"]
        x0, x1 = min(_seg_box(r)[0] for r in g), max(_seg_box(r)[2] for r in g)
        y0, y1 = g[0][0]["yc"], g[-1][0]["yc"]
        ids = {id(r) for r in g}
        taken = {id(c) for r in g for c in r}
        # rows of column heads directly above, and short lines between the data rows (group labels, wrapped labels)
        heads, top = [], y0
        for seg in sorted((s for s in segs if id(s) not in ids and s[0]["yc"] < y0
                           and not any(id(c) in taken for c in s)), key=lambda s: -s[0]["yc"]):
            box = _seg_box(seg)
            if top - seg[0]["yc"] > HEAD_LEAD * size or len(heads) >= 3:
                break
            if len(seg) < 2 or _CAPTION_START.match(seg[0]["text"]) or box[0] < x0 - 2 * size or box[2] > x1 + 2 * size:
                if top - seg[0]["yc"] < 0.5 * size:
                    continue                       # something else on the same baseline, further left or right
                break
            heads.insert(0, seg)
            top = seg[0]["yc"]
        inner = [s for s in segs if id(s) not in ids and y0 < s[0]["yc"] < y1 and not any(id(c) in taken for c in s)
                 and _seg_box(s)[0] >= x0 - 2 * size and _seg_box(s)[2] <= x1 + 2 * size]
        rows = sorted(g + inner, key=lambda s: s[0]["yc"])
        head = heads[-1] if heads else None
        out = [("Table header: " + "; ".join(c["text"] for c in h), "meta") for h in heads]
        for seg in rows:
            if id(seg) not in ids:
                out.append(("Table text: " + "; ".join(c["text"] for c in seg), "meta"))
                continue
            parts = []
            for i, c in enumerate(seg):
                hs = [h for h in head if _x_overlap(h["bbox"], c["bbox"]) > 0] if head and i else []
                # a column head is attached only if it stands over this cell alone and the cell under it alone
                if len(hs) == 1 and sum(1 for o in seg if _x_overlap(hs[0]["bbox"], o["bbox"]) > 0) == 1:
                    parts.append(f"{hs[0]['text']}: {c['text']}")
                else:
                    parts.append(c["text"])
            labelled = not seg[0]["num"] and sum(ch.isalpha() for ch in seg[0]["text"]) >= 2
            unlabelled = unlabelled or not labelled
            out.append(("Table row: " + "; ".join(parts), "table" if labelled else "meta"))
        for r, seg in enumerate(heads + rows):
            box = _seg_box(seg)
            chars = sum(len(c["text"]) for c in seg)
            mark = ("", size, False, box[1], -(len(found) + 1), box, False,
                    [{"text": "x" * chars, "bbox": box, "size": size, "flags": 0, "font": ""}])
            for c in seg:
                for sp in c["spans"]:
                    used[id(sp)] = (len(found), r, mark)
        found.append(out)
    if not found:
        return [], lines, False
    rest, placed = [], set()
    for ln in lines:
        owners = [used.get(id(sp)) for sp in ln[7]]
        for o in owners:
            if o and o[:2] not in placed:          # the row's placeholder goes where its first cell stood
                placed.add(o[:2])
                rest.append(o[2])
        keep = [sp for sp, o in zip(ln[7], owners) if o is None]
        if len(keep) == len(ln[7]):
            rest.append(ln)
        elif keep:
            rest.append(_make_line(keep, ln[4]))   # prose that shares a line with a cell keeps its place
    return found, rest, unlabelled


FIGURE_PAD = 2.0
FIGURE_GAP = 6.0          # drawing items closer than this belong to one figure
FIGURE_MIN_ITEMS = 4
FIGURE_MIN_SIZE = (60.0, 40.0)


def _figure_boxes(page, table_boxes=()) -> list[tuple]:
    """Bounding boxes of figures: clusters of vector drawing items and images. Text inside such a box (axis labels,
    legends, diagram boxes) is figure content, not prose, and must not be glued into sentences. The caption sits outside.
    Clusters that are only thin horizontal rules (a ruled table), page-sized backgrounds and found tables are not figures."""
    try:
        rects = [tuple(d["rect"]) for d in page.get_drawings() if d.get("rect") is not None]
        rects += [tuple(i["bbox"]) for i in page.get_image_info()]
    except Exception:
        return []
    area = page.rect.width * page.rect.height
    rects = [r for r in rects if (r[2] - r[0]) * (r[3] - r[1]) < 0.5 * area and (r[2] - r[0] > 0.2 or r[3] - r[1] > 0.2)]
    clusters: list[list] = []                  # [bbox, n_items, n_non_rule_items]
    for r in sorted(rects):
        thin = (r[3] - r[1]) < 1.5 and (r[2] - r[0]) > 4 * (r[3] - r[1])
        hit = [c for c in clusters if r[0] <= c[0][2] + FIGURE_GAP and r[2] >= c[0][0] - FIGURE_GAP
               and r[1] <= c[0][3] + FIGURE_GAP and r[3] >= c[0][1] - FIGURE_GAP]
        box = list(r)
        n, m = 1, 0 if thin else 1
        for c in hit:
            clusters.remove(c)
            box = [min(box[0], c[0][0]), min(box[1], c[0][1]), max(box[2], c[0][2]), max(box[3], c[0][3])]
            n, m = n + c[1], m + c[2]
        clusters.append([tuple(box), n, m])
    out = []
    for box, n, m in clusters:
        w, h = box[2] - box[0], box[3] - box[1]
        if n < FIGURE_MIN_ITEMS or m < 2 or w < FIGURE_MIN_SIZE[0] or h < FIGURE_MIN_SIZE[1] or w * h > 0.7 * area:
            continue
        if any(_overlap(box, tb) > 0.5 for tb in table_boxes):
            continue
        out.append(box)
    return out


def _overlap(a, b) -> float:
    """Share of the smaller box that the two boxes have in common."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))


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
        figs = _figure_boxes(page, [tb[0] for tb in tables])
        figtext = [ln for ln in lines if any(_inside(ln[5], fb, FIGURE_PAD) for fb in figs)]
        lines = [ln for ln in lines if not any(ln is f for f in figtext)]
        pages.append({"pno": pno, "tables": tables, "lines": lines, "figtext": figtext,
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
        pg["open_tables"], pg["unlabelled"] = [], False
        if not pg["toc"]:
            pg["open_tables"], pg["lines"], pg["unlabelled"] = _open_tables(pg["lines"], pg["width"])
        pg["lines"], pg["layout"] = _reorder_columns(pg["lines"])
        for ln in pg["lines"]:
            size_chars[round(ln[1], 1)] += len(ln[0])
    total_chars = sum(len(ln[0]) for pg in pages for ln in pg["lines"])
    if total_chars < 40 * max(1, len(pdf)):
        warnings.append(UNREADABLE_WARNING)
    nolabel = [pg["pno"] for pg in pages if pg["unlabelled"]]
    if nolabel:
        warnings.append(UNLABELLED_ROWS.format(pages=", ".join(map(str, nolabel))))
    amb = [pg["pno"] for pg in pages if pg["layout"]["ambiguous"]]
    if amb:
        warnings.append(AMBIGUOUS_LAYOUT.format(pages=", ".join(map(str, amb))))
    body = size_chars.most_common(1)[0][0] if size_chars else 10.0   # size carrying the most characters

    title = _clean(_title(pages[0], name))[0].strip() if pages else name

    sentences: list[Sentence] = []
    st = {"section": "front", "heading": "", "sid": 0, "ref": False, "tops": {}, "top": (0.0, False, False),
          "sa_seen": set(), "abs_n": 0, "unmapped": 0, "tail": False, "body_seen": False, "apx": "", "last_num": None,
          "buf_size": 0.0}
    chunks: list[tuple[list[Sentence], float]] = []    # front-matter paragraphs of page 1, in order, with font size

    buf: list[str] = []                       # text of the running paragraph; may carry over a page break
    st["held"] = None                          # (lines, page, size) of a sentence interrupted by a caption
    st["cap_block"] = None
    st["buf_page"] = None                      # page on which the first text in `buf` started
    st["deferred"] = []                        # table rows met in the middle of a sentence: emitted once it is complete
    st["carried"] = False                      # `buf` holds the unfinished last sentence of the previous page

    for pg in pages:
        pno, tables, lines = pg["pno"], pg["tables"], pg["lines"]

        def flush(section=None, force_kind=None, lines=None, keep_tail=False):
            """Turn the running text (or `lines`) into sentences. With keep_tail an unfinished last sentence stays in
            `buf` so that it can be completed on the next page; its page is the page where it started."""
            src = buf if lines is None else lines
            if not src:
                return
            text, n_bad = _clean(_join_lines(src))
            st["unmapped"] += n_bad
            first_page = st["buf_page"] or pno if lines is None else pno
            if lines is None:
                buf.clear()
                st["buf_page"] = None
                st["carried"] = False
            sec = section or st["section"]
            sents = split_sentences(text)
            tail = ""
            if keep_tail and sents and sec not in ("references", "front") and not _SENTENCE_END.search(sents[-1]):
                tail = sents.pop()
            made = []
            for k, sent in enumerate(sents):
                if len(sent) < 25 and not re.search(r"\d", sent):
                    continue
                kind = force_kind or ("caption" if re.match(r"^(Table|Figure|Fig\.|FIG\.)\s*\d+", sent)
                                      else "meta" if _META_RE.search(sent) else "text")
                sentences.append(Sentence(st["sid"], sent, first_page if k == 0 else pno, sec, st["heading"], kind))
                made.append(sentences[-1])
                st["sid"] += 1
                if sec == "abstract":
                    st["abs_n"] += 1
            if sec == "front" and pno == 1 and not force_kind and made:
                chunks.append((made, st["buf_size"]))
            if tail:
                buf.append(tail)
                st["buf_page"] = first_page if not sents else pno
                st["carried"] = True
            elif lines is None and st["deferred"]:
                for rows, page, tsec, thead in st["deferred"]:
                    emit_rows(rows, page, tsec, thead)
                st["deferred"] = []

        def emit_rows(rows, page, sec, heading):
            for row in rows:
                row, kind = row if isinstance(row, tuple) else (row, "table")
                row, n_bad = _clean(row)
                st["unmapped"] += n_bad
                sentences.append(Sentence(st["sid"], row, page, sec, heading, kind))
                st["sid"] += 1

        def release_held():
            """Close the caption that interrupted a sentence and put the sentence back into the running text."""
            held = st["held"]
            st["held"] = None
            if not held:
                return
            flush()
            buf.extend(held[0])
            st["buf_page"], st["buf_size"] = held[1], held[2]

        if pg["toc"]:
            # a contents page lists every heading again: keep its text as front matter, read no structure from it
            flush()
            flush(section="front", force_kind="meta", lines=[ln[0] for ln in lines])
            continue

        pending_tables = sorted(tables, key=lambda t: t[0][1])

        def emit_tables(until_y, xc=None, next_line=None):
            """Tables are placed before the first line below their top edge in their own column (in the reading
            order a column-wise page has no single vertical position). A table that stands inside a sentence (the
            text before it is unfinished and the line after it goes on in lower case) is emitted after that sentence."""
            while pending_tables and pending_tables[0][0][1] <= until_y and (
                    xc is None or pending_tables[0][0][0] - 6 <= xc <= pending_tables[0][0][2] + 6):
                _, rows = pending_tables.pop(0)
                place_table(rows, next_line)

        def place_table(rows, next_line):
            """Emit table rows here, or after the current sentence if the table stands inside it: the text before
            is unfinished, the line after the table goes on in lower case, and both lines are in the same column."""
            sec = st["section"] if st["section"] != "front" else "results"
            last = st.get("last_bbox")
            same_col = bool(next_line and last and
                            _x_overlap(last, next_line[5]) > 0.5 * min(last[2] - last[0], next_line[5][2] - next_line[5][0]))
            if buf and same_col and next_line[0][:1].islower() and not st["held"] \
                    and st["section"] not in ("references", "front") and not _SENTENCE_END.search(buf[-1]):
                st["deferred"].append((rows, pno, sec, st["heading"]))
                return
            flush()
            if st["section"] != "references":
                emit_rows(rows, pno, sec, st["heading"])

        open_done: set[int] = set()
        prev_block = last_block = note_block = None
        prev_size = prev_y = note_y = None
        dropcap = ""
        notes: list[str] = []
        no_head: set[int] = set()
        i = 0
        while i < len(lines):
            text, size, bold, y, block_no = lines[i][:5]
            i += 1
            if block_no < 0:                       # the place of a row of a table without a grid
                if block_no not in open_done:
                    open_done.add(block_no)
                    place_table(pg["open_tables"][-block_no - 1], next((ln for ln in lines[i:] if ln[4] >= 0), None))
                continue
            emit_tables(y, (lines[i - 1][5][0] + lines[i - 1][5][2]) / 2, lines[i - 1])
            if re.fullmatch(r"\d{1,3}", text) and (y < 60 or y > 700):
                continue  # page number
            if block_no != last_block:
                last_block = block_no
                # a small-print block in the lower half that opens with a footnote mark (author notes, URLs), and
                # the small print below it (venue line, "Author contributions listed at end of paper.")
                small_low = size <= body - 0.9 and y > 0.5 * pg["height"]
                note_block = block_no if small_low and (_FOOTNOTE_START.match(text) or _META_START.match(text)
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
                    st["buf_page"] = pno
                    st["buf_size"], prev_block, prev_size, prev_y = size, block_no, size, y
                    continue
                if _KEYWORDS_LINE.match(text):
                    flush()                        # the keyword list closes the abstract and is not part of it
                    note_block = block_no
                    notes.append(text)
                    if st["section"] == "abstract":
                        st["section"], st["heading"] = "other", ""
                    continue
            if len(text) == 1 and text.isupper() and size >= 2.5 * body:
                # a drop cap: the first letter of the next line; it also starts the body, so an abstract ends here
                if st["section"] == "abstract":
                    flush()
                    st["section"], st["heading"] = "other", ""
                dropcap = text
                continue
            if st["section"] == "abstract" and (st["abs_n"] >= 2 or len(buf) >= 6) and i >= 2                     and lines[i - 1][5][1] - lines[i - 2][5][3] > ABSTRACT_END_GAP * size                     and lines[i - 1][5][0] <= lines[i - 2][5][2]:
                flush()                            # a wide white band after the abstract text: the body starts below
                st["section"], st["heading"] = "other", ""
            found = _heading_at(lines, i - 1, st, body, pno, no_head)
            if found and found[0] == "head":
                _, n, htext, canon = found
                htext = _clean(htext)[0].strip()
                release_held()
                flush()
                st["section"] = _next_section(st, htext, canon, size, bold, pno)
                st["heading"] = htext
                if st["section"] == "references":
                    st["ref"] = True
                i += n - 1
                continue
            if found:                              # pull quote: repeats body text in display type
                release_held()
                flush()
                flush(section="front" if st["section"] == "abstract" else None, force_kind="meta", lines=[found[2]])
                if st["section"] == "abstract":
                    st["section"], st["heading"] = "other", ""      # display text ends the abstract
                i += found[1] - 1
                continue
            if prev_block is not None and block_no != prev_block and buf and buf[-1].endswith("."):
                flush()
            elif st["section"] == "front" and buf and prev_size is not None and (
                    abs(size - prev_size) > 0.3 or y - prev_y > 1.7 * size or y < prev_y - 2 * size):
                flush()                            # title, authors, dates and the abstract are separate paragraphs
            new_block = block_no != prev_block
            prev_block, prev_size, prev_y = block_no, size, y
            if st["section"] == "front" and size > body + 2:
                continue  # title lines
            if st["held"] and block_no != st["cap_block"]:
                release_held()                     # the caption is over: the interrupted sentence goes on
            elif _CAPTION_START.match(text) and len(text) > 20 and new_block and buf and not st["held"]                     and not _SENTENCE_END.search(buf[-1]):
                # a figure or table caption in the middle of a sentence (a figure floats between two columns): the
                # caption is its own text; the sentence it interrupted continues after it
                st["held"] = (list(buf), st["buf_page"], st["buf_size"])
                buf.clear()
                st["cap_block"] = block_no
                st["buf_page"] = pno
            if st["carried"]:
                st["carried"] = False
                if buf and not (text[:1].islower() or buf[-1].endswith((",", ";"))):
                    flush()                        # the unfinished sentence was not continued: close it on its page
            if not buf:
                st["buf_size"] = size
                st["buf_page"] = pno
            buf.append(dropcap + text)
            st["last_bbox"] = lines[i - 1][5]
            dropcap = ""
        emit_tables(1e9)
        release_held()
        flush(keep_tail=pno < len(pages))
        if notes:
            flush(force_kind="meta", lines=notes)
        if pg["margin"]:
            flush(section="front", force_kind="meta", lines=[ln[0] for ln in pg["margin"]])
        if pg["figtext"]:                          # labels inside figures: kept, but never a claim or evidence
            flush(force_kind="meta", lines=[ln[0] for ln in pg["figtext"]])

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
