"""Deterministic synthetic PDFs with hard page layouts, and their ground truth (reading-order benchmark).

    python -m eval.layout_synth <out_dir>      # writes <id>.pdf and <id>.truth.json for every layout, plus MANIFEST.json

How a document is made (nothing here reads PaperLens or any parser output):

1. A *logical document* is generated from a seeded random generator: a list of blocks in the order a human would read
   them (title, front matter, headings, paragraphs, captions, tables, reference list). Sentences, numbers, claims and the
   evidence sentence of each claim are generated from templates, so the expected text is known before any PDF exists.
2. A *flow engine* places the blocks into page regions (columns, full-width areas) line by line, using PyMuPDF only to
   measure string widths. A paragraph that does not fit is continued in the next region, mid-sentence if need be.
3. The lines are drawn into the PDF. Only the order in which they are written to the content stream varies
   (`stream`): natural reading order, blocks sorted by vertical position, lines sorted by vertical position, or shuffled.
   Real producers differ exactly here, and a parser that trusts the stream order is right only on the first.
4. The ground truth is written from the logical document and the positions the engine chose.

The text is template-made. Scores on these files describe how the parser handles the geometry, not real papers.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

PAGE_W, PAGE_H = 612.0, 792.0
Y0, Y1 = 64.0, 718.0            # content area; header above, footnote and page number below
FONT, BOLD = "helv", "hebo"

METHODS = ["Zetanet", "Orbiter", "Kestrel", "Lumen", "Quasar", "Helixnet", "Marlin", "Tessera", "Corvid", "Alderon"]
BENCH = ["ALPHABENCH", "DELTASET", "MERIDIAN", "FJORD-9", "TUNDRA", "COBALT-12", "NIMBUS", "VERDANT", "OSPREY", "LATTICE"]
_DET = ["The", "Each", "This", "Every"]
_ADJ = ["calibrated", "regularised", "stratified", "robust", "sparse", "balanced", "adaptive", "nominal", "reference",
        "auxiliary", "pooled", "resampled", "normalised", "layered"]
_NOUN = ["estimator", "detector array", "sample", "protocol", "sensor network", "classifier", "baseline run",
         "control group", "measurement series", "reference source", "training schedule", "validation split",
         "calibration step", "transfer pipeline"]
_VERB = ["is compared with", "is repeated for", "is reported alongside", "is checked against", "is drawn from",
         "is combined with", "is processed before", "is analysed after"]
_TAIL = ["before the analysis begins", "in every experimental condition", "for all of the selected runs",
         "using the settings listed above", "under the same operating conditions", "without any manual adjustment",
         "as described in the previous section", "with the order of the runs randomised"]


@dataclass
class Item:
    kind: str                       # title front heading para caption table figure reference break
    text: str = ""
    section: str = ""               # canonical section label the parser should assign
    tag: str = ""                   # "full": place in a full-width region
    size: float = 0.0
    bold: bool = False
    rows: list = field(default_factory=list)
    orphan: bool = False            # a heading may be left alone at the bottom of a region
    break_after: bool = False
    quantities: list = field(default_factory=list)
    bid: str = ""
    grid: str = ""                  # grid cell name for the ambiguous layout
    split_lines: int = 0            # break the region after this many lines of the paragraph (a page or column break mid-text)


@dataclass
class Region:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    no_flow: bool = False           # text never flows into it from a previous region; only tagged items go here
    tag: str = "col"


@dataclass
class Unit:
    page: int
    x: float
    y: float
    lines: list
    size: float
    bold: bool
    block: str
    kind: str
    rows: list = field(default_factory=list)
    w: float = 0.0
    h: float = 0.0


# ---------------------------------------------------------------------------------------------------- text content

class Content:
    """Seeded sentence source. Every sentence is at least 40 characters and has no abbreviation or inner full stop."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        r = self.rng
        self.method = r.choice(METHODS) + "-" + str(r.randint(2, 9))
        self.b1, self.b2 = r.sample(BENCH, 2)
        self.a0 = round(r.uniform(70, 88), 1)
        self.a1 = round(self.a0 + r.uniform(2.1, 6.9), 1)
        self.red = r.randint(12, 48)
        self.k = r.randint(2, 9)

    def sentence(self) -> str:
        r = self.rng
        return (f"{r.choice(_DET)} {r.choice(_ADJ)} {r.choice(_NOUN)} {r.choice(_VERB)} the {r.choice(_ADJ)} "
                f"{r.choice(_NOUN)} {r.choice(_TAIL)}.")

    def paragraph(self, n: int) -> str:
        return " ".join(self.sentence() for _ in range(n))

    # the two headline claims and the sentences in the results section that support them
    def claims(self):
        m = self.method
        c1 = f"The {m} improves accuracy on the {self.b1} benchmark from {self.a0}% to {self.a1}%."
        c2 = (f"It also reduces the mean error on {self.b2} by {self.red}% while using {self.k} times fewer parameters.")
        e1 = (f"On the {self.b1} benchmark the {m} improves accuracy from {self.a0}% to {self.a1}%, "
              f"as shown in Table 1.")
        e2 = (f"The mean error on {self.b2} falls by {self.red}% and the model uses {self.k} times fewer "
              f"parameters than the baseline.")
        return (c1, e1), (c2, e2)

    def quantity_paragraph(self):
        r = self.rng
        conc, temp, hours = round(r.uniform(0.2, 0.9), 1), r.randint(25, 40), r.randint(6, 48)
        rate, expo = round(r.uniform(1.1, 9.8), 1), r.randint(3, 7)
        p, lo, hi = r.choice(["0.01", "0.001", "0.05"]), round(r.uniform(1.0, 1.9), 1), round(r.uniform(2.5, 4.4), 1)
        mass, err = round(r.uniform(12, 99), 1), round(r.uniform(0.2, 1.4), 1)
        sents = [
            f"The reagent was prepared at {conc} mg/mL and incubated at {temp} °C for {hours} h.",
            f"The rate constant was {rate} × 10-{expo} s-1 (p < {p}, 95% CI {lo} to {hi}).",
            f"The measured mass was {mass} ± {err} µg per sample, with the dose set to {conc} mmol/L.",
            self.sentence(),
        ]
        qs = [f"{conc} mg/mL", f"{temp} °C", f"{hours} h", f"{rate} × 10-{expo} s-1", f"p < {p}",
              f"{lo} to {hi}", f"{mass} ± {err} µg", f"{conc} mmol/L"]
        return " ".join(sents), qs


def logical_items(seed: int, n_filler: int, tables: bool = False, quantities: bool = False,
                  intro_after_abstract_break: bool = True) -> tuple[list[Item], Content]:
    """The logical document: title, abstract with two claims, four numbered sections, references."""
    c = Content(seed)
    (c1, e1), (c2, e2) = c.claims()
    it: list[Item] = []
    title = f"A Synthetic Study of {c.method} on {c.b1}"
    it.append(Item("title", title, tag="full", size=17, bold=True, bid="title"))
    it.append(Item("front", "Ada Writer, Ben Author and Cleo Scribe, Synthetic Institute of Layout Studies",
                   tag="full", size=10, bid="front"))
    it.append(Item("heading", "Abstract", section="abstract", tag="full", bid="h_abs"))
    abstract = " ".join([c.sentence(), c1, c2, c.sentence()])
    it.append(Item("para", abstract, section="abstract", tag="full", bid="abstract"))
    if intro_after_abstract_break:
        it.append(Item("break"))
    it.append(Item("heading", "1 Introduction", section="introduction", bid="h_intro"))
    for k in range(2):
        it.append(Item("para", c.paragraph(5 + n_filler), section="introduction", bid=f"intro{k}"))
    it.append(Item("heading", "2 Methods", section="method", bid="h_meth"))
    for k in range(2):
        it.append(Item("para", c.paragraph(5 + n_filler), section="method", bid=f"meth{k}"))
    if quantities:
        text, qs = c.quantity_paragraph()
        it.append(Item("para", text, section="method", quantities=qs, bid="quant0"))
        text, qs = c.quantity_paragraph()
        it.append(Item("para", text, section="method", quantities=qs, bid="quant1"))
    it.append(Item("heading", "3 Results", section="results", bid="h_res"))
    it.append(Item("para", c.paragraph(3) + " " + e1 + " " + c.sentence() + " " + e2 + " " + c.sentence(),
                   section="results", bid="results0"))
    if tables:
        rows = [["Model", "Accuracy", "Error"], ["Baseline", f"{c.a0}", f"{c.red + 10}.1"],
                [c.method, f"{c.a1}", f"{c.red}.4"], ["Ablation", f"{round(c.a1 - 1.3, 1)}", f"{c.red + 3}.7"]]
        it.append(Item("caption", f"Table 1: Accuracy and error of the baseline and the {c.method} on {c.b1}.",
                       section="results", size=8.5, bid="cap_t1"))
        it.append(Item("table", rows=rows, section="results", bid="table1"))
        it.append(Item("figure", section="results", bid="fig1"))
        it.append(Item("caption", f"Figure 1: Training curves of the {c.method} for three random seeds on {c.b1}.",
                       section="results", size=8.5, bid="cap_f1"))
    it.append(Item("para", c.paragraph(4 + n_filler), section="results", bid="results1"))
    it.append(Item("heading", "4 Conclusion", section="conclusion", bid="h_conc"))
    it.append(Item("para", c.paragraph(4), section="conclusion", bid="conc0"))
    refs = "\n".join(f"[{i}] A. Author and B. Writer, {" ".join(c.sentence().split()[:6])} Journal of Made-up Results {10 + i}, "
                     f"{100 + 7 * i}-{110 + 7 * i} (20{10 + i})." for i in range(1, 6 + n_filler))
    it.append(Item("heading", "References", section="references", bid="h_ref"))
    it.append(Item("reference", refs, section="references", size=8.5, bid="refs"))
    return it, c


# ---------------------------------------------------------------------------------------------------- flow engine

def _wrap(text: str, width: float, size: float, bold: bool) -> list[str]:
    font = BOLD if bold else FONT
    lines, cur = [], ""
    for word in text.split(" "):
        trial = f"{cur} {word}" if cur else word
        if cur and pymupdf.get_text_length(trial, fontname=font, fontsize=size) > width:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


class Flow:
    """Places items into regions in reading order and records exactly what went where."""

    def __init__(self, template, body: float, lead: float):
        self.template, self.body, self.lead = template, body, lead
        self.regions: list[Region] = []
        self.units: list[Unit] = []
        self.blocks: dict[str, dict] = {}
        self.order: list[str] = []
        self.ri = -1
        self.y = 0.0
        self.n_pages = 0
        self._next_page()
        self.ri = 0
        self.y = self.regions[0].y0

    def _next_page(self):
        self.n_pages += 1
        self.regions += self.template(self.n_pages)

    def _advance(self, flow: bool = True):
        self.ri += 1
        for _ in range(200):
            if self.ri >= len(self.regions):
                self._next_page()
            if flow and self.regions[self.ri].no_flow:
                self.ri += 1
                continue
            break
        else:
            raise RuntimeError("flow engine ran out of regions")
        self.y = self.regions[self.ri].y0

    def _goto_tag(self, tag: str):
        for _ in range(60):
            if self.ri >= len(self.regions):
                self._next_page()
            if self.regions[self.ri].tag == tag and (self.regions[self.ri].y0 <= self.y or self.y == self.regions[self.ri].y0):
                return
            if self.regions[self.ri].tag == tag:
                self.y = self.regions[self.ri].y0
                return
            self.ri += 1
            if self.ri < len(self.regions):
                self.y = self.regions[self.ri].y0
        raise RuntimeError(f"no region tagged {tag!r} reachable")

    def place(self, it: Item):
        r = self.regions
        if it.kind == "break":
            self._advance()
            return
        if it.tag:
            if r[self.ri].tag != it.tag:
                self._goto_tag(it.tag)
        elif r[self.ri].no_flow:
            self._advance()
        reg = r[self.ri]
        size = it.size or (11.0 if it.kind == "heading" else self.body)
        bold = it.bold or it.kind == "heading"
        lead = self.lead * size / self.body
        if it.orphan:                      # land on the last line of the region; the text that belongs to it follows elsewhere
            self.y = max(self.y, reg.y1 - 1.6 * lead)
            it.break_after = True
        if it.kind == "heading" and self.y > reg.y0:
            self.y += 8
        if it.kind in ("heading",) and not it.orphan and self.y + 3 * lead > reg.y1:
            self._advance(flow=not it.tag)
            reg = self.regions[self.ri]
        if it.kind in ("table", "figure"):
            h = (len(it.rows) * 13.0 + 2) if it.kind == "table" else 70.0
            if self.y + h > reg.y1:
                self._advance()
                reg = self.regions[self.ri]
            self.units.append(Unit(reg.page, reg.x0, self.y, [], size, False, it.bid, it.kind, it.rows,
                                   reg.x1 - reg.x0, h))
            self._record(it, reg.page, "")
            self.y += h + 6
            return
        lines = _wrap(it.text.replace("\n", "\n").replace("\n", " \n "), reg.x1 - reg.x0, size, bold) \
            if it.kind != "reference" else self._wrap_refs(it, reg, size)
        unit_lines: list[str] = []
        first_page = reg.page
        for n_ln, ln in enumerate(lines):
            if (self.y + lead > reg.y1 + 0.01) or (it.split_lines and n_ln == it.split_lines and unit_lines):
                if unit_lines:
                    self.units.append(Unit(reg.page, reg.x0, self.y - lead * len(unit_lines), unit_lines, size, bold,
                                           it.bid, it.kind))
                    self._record(it, reg.page, unit_lines)
                    unit_lines = []
                self._advance()
                reg = self.regions[self.ri]
            unit_lines.append(ln)
            self.y += lead
        if unit_lines:
            self.units.append(Unit(reg.page, reg.x0, self.y - lead * len(unit_lines), unit_lines, size, bold,
                                   it.bid, it.kind))
            self._record(it, reg.page, unit_lines)
        self.y += 4 if it.kind == "heading" else 5
        if it.break_after:
            self._advance()

    def _wrap_refs(self, it: Item, reg: Region, size: float):
        out = []
        for entry in it.text.split("\n"):
            out += _wrap(entry, reg.x1 - reg.x0, size, False)
        return out

    def _record(self, it: Item, page: int, lines):
        b = self.blocks.setdefault(it.bid, {"id": it.bid, "kind": it.kind, "section": it.section, "units": [],
                                            "quantities": it.quantities, "rows": it.rows})
        text = " ".join(lines) if lines else ""
        b["units"].append({"page": page, "text": text})
        if it.bid not in self.order:
            self.order.append(it.bid)


# ---------------------------------------------------------------------------------------------------- page templates

def _cols(n: int, gutter: float, y0: float = Y0, y1: float = Y1, x0: float = 56.0, x1: float = 556.0):
    w = (x1 - x0 - gutter) / 2
    return [Region(n, x0, y0, x0 + w, y1), Region(n, x0 + w + gutter, y0, x1, y1)]


def _cols_w(n: int, widths, gutter: float, y0: float = Y0, y1: float = Y1, x0: float = 56.0):
    out, x = [], x0
    for w in widths:
        out.append(Region(n, x, y0, x + w, y1))
        x += w + gutter
    return out


def tpl_three(gutter=14.0, top_full: float = 300.0):
    w = (500.0 - 2 * gutter) / 3
    def t(n):
        if n == 1:
            return [Region(n, 56, Y0, 556, top_full, no_flow=True, tag="full")] + _cols_w(n, [w] * 3, gutter, top_full + 10)
        return _cols_w(n, [w] * 3, gutter)
    return t


def tpl_unequal(gutter=24.0, top_full: float = 300.0):
    widths = [300.0, 500.0 - 300.0 - gutter]
    def t(n):
        if n == 1:
            return [Region(n, 56, Y0, 556, top_full, no_flow=True, tag="full")] + _cols_w(n, widths, gutter, top_full + 10)
        return _cols_w(n, widths, gutter)
    return t


def tpl_sparse(gutter=24.0, top_full: float = 300.0):
    """Page 2 has a full left column and only two lines in the right one (the end of a section, a short float)."""
    def t(n):
        if n == 1:
            return [Region(n, 56, Y0, 556, top_full, no_flow=True, tag="full")] + _cols(n, gutter, top_full + 10)
        if n == 2:
            c = _cols(n, gutter)
            c[1].y1 = Y0 + 24
            return c
        return _cols(n, gutter)
    return t


def tpl_single(n):
    return [Region(n, 56, Y0, 556, Y1, tag="full")]


def tpl_two(gutter=24.0, top_full: float = 300.0):
    def t(n):
        if n == 1:
            return [Region(n, 56, Y0, 556, top_full, no_flow=True, tag="full")] + _cols(n, gutter, top_full + 10)
        return _cols(n, gutter)
    return t


def tpl_spanning(gutter=24.0):
    def t(n):
        if n == 1:
            return [Region(n, 56, Y0, 556, 290, no_flow=True, tag="full")] + _cols(n, gutter, 300)
        if n == 2:      # columns, then a full-width block, then columns again
            return (_cols(n, gutter, Y0, 380) + [Region(n, 56, 392, 556, 470, no_flow=True, tag="full")]
                    + _cols(n, gutter, 482))
        return _cols(n, gutter)
    return t


def tpl_mixed(gutter=24.0):
    def t(n):
        if n == 1:
            return [Region(n, 56, Y0, 556, 290, no_flow=True, tag="full")] + [Region(n, 56, 300, 556, Y1)]
        if n % 2 == 0:
            return _cols(n, gutter)
        return [Region(n, 56, Y0, 556, Y1)]
    return t


# ---------------------------------------------------------------------------------------------------- drawing

def _stream(units: list[Unit], mode: str, seed: int) -> list[tuple]:
    """Drawing operations in content-stream order: (page, x, baseline_y, text, size, bold, unit_index, line_index)."""
    ops = []
    for ui, u in enumerate(units):
        lead = u.size * 1.22
        for li, ln in enumerate(u.lines):
            ops.append((u.page, u.x, u.y + u.size * 0.85 + li * lead, ln, u.size, u.bold, ui, li))
    rng = random.Random(seed)
    if mode == "natural":
        return ops
    out = []
    for page in sorted({o[0] for o in ops}):
        po = [o for o in ops if o[0] == page]
        if mode == "lines_y":
            po.sort(key=lambda o: (round(o[2], 1), o[1]))
        elif mode == "blocks_y":
            top = {}
            for o in po:
                top.setdefault(o[6], (units[o[6]].y, units[o[6]].x))
            po.sort(key=lambda o: (top[o[6]], o[7]))
        elif mode == "shuffled":
            ids = sorted({o[6] for o in po})
            rng.shuffle(ids)
            rank = {u: i for i, u in enumerate(ids)}
            po.sort(key=lambda o: (rank[o[6]], o[7]))
        out += po
    return out


def draw(units, n_pages, stream, seed, furniture) -> bytes:
    pdf = pymupdf.open()
    for _ in range(n_pages):
        pdf.new_page(width=PAGE_W, height=PAGE_H)
    for p in range(1, n_pages + 1):
        pg = pdf[p - 1]
        h, num = furniture.get("header"), furniture.get("pagenum", True)
        if h:
            pg.insert_text((56, 36), h(p), fontsize=8.5, fontname=FONT)
        if num:
            pg.insert_text((PAGE_W / 2 - 4, 765), str(p), fontsize=9, fontname=FONT)
        fn = furniture.get("footnotes", {}).get(p)
        if fn:
            pg.insert_text((56, 733), fn, fontsize=7.5, fontname=FONT)
    for u in units:
        if u.kind == "table":
            pg = pdf[u.page - 1]
            cw, rh = u.w / len(u.rows[0]), 13.0
            for ri, row in enumerate(u.rows):
                for ci, cell in enumerate(row):
                    rect = pymupdf.Rect(u.x + ci * cw, u.y + ri * rh, u.x + (ci + 1) * cw, u.y + (ri + 1) * rh)
                    pg.draw_rect(rect, color=(0, 0, 0), width=0.6)
                    pg.insert_text((rect.x0 + 3, rect.y0 + 9.5), cell, fontsize=8.5,
                                   fontname=BOLD if ri == 0 else FONT)
        elif u.kind == "figure":
            pdf[u.page - 1].draw_rect(pymupdf.Rect(u.x + 20, u.y, u.x + u.w - 20, u.y + u.h), color=(0.5, 0.5, 0.5),
                                        fill=(0.93, 0.93, 0.93), width=0.8)
    for page, x, y, text, size, bold, _ui, _li in _stream([u for u in units if u.lines], stream, seed):
        pdf[page - 1].insert_text((x, y), text, fontsize=size, fontname=BOLD if bold else FONT)
    pdf.set_metadata({})
    return pdf.tobytes(deflate=True, no_new_id=True)


# ---------------------------------------------------------------------------------------------------- ground truth

def _alnum(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", s).lower() if ch.isascii() and ch.isalnum())


def build_truth(doc_id, category, stream, seed, flow: Flow, items, content, extra) -> dict:
    blocks = []
    for bid in flow.order:
        b = flow.blocks[bid]
        text = " ".join(u["text"] for u in b["units"] if u["text"])
        blocks.append({"id": bid, "kind": b["kind"], "section": b["section"], "text": text, "units": b["units"],
                       "quantities": b["quantities"], "rows": b["rows"]})
    by = {b["id"]: b for b in blocks}
    claims = []
    for n, ((c, e), cb, eb) in enumerate(zip(content.claims(), ("abstract", "abstract"), ("results0", "results0"))):
        claims.append({"id": f"K{n + 1}", "text": c, "block": cb, "evidence_text": e, "evidence_block": eb})
    for c in claims:
        for key, bk in (("page", "block"), ("evidence_page", "evidence_block")):
            txt = c["text"] if key == "page" else c["evidence_text"]
            want, acc, found = _alnum(txt), 0, None
            full = _alnum(by[c[bk]]["text"])
            pos = full.find(want)
            for u in by[c[bk]]["units"]:
                acc += len(_alnum(u["text"]))
                if pos < acc and found is None:
                    found = u["page"]
            c[key] = found
    mid = [i for i, b in enumerate(blocks) if len({u["page"] for u in b["units"] if u["text"]}) > 1]
    t = {"id": doc_id, "category": category, "stream": stream, "seed": seed, "n_pages": flow.n_pages,
         "title": next(b["text"] for b in blocks if b["kind"] == "title"), "blocks": blocks, "claims": claims,
         "headings": [{"text": b["text"], "section": b["section"]} for b in blocks if b["kind"] == "heading"],
         "multi_unit_blocks": [blocks[i]["id"] for i in mid]}
    t.update(extra)
    return t


# ---------------------------------------------------------------------------------------------------- layouts

def _decorate(truth, furniture, flow):
    """Furniture that the parser must not return as body text: running headers, page numbers, footnotes."""
    ex = []
    h = furniture.get("header")
    for p in range(1, flow.n_pages + 1):
        if h:
            ex.append({"id": f"header{p}", "kind": "header", "section": "", "text": h(p), "units": [{"page": p, "text": h(p)}],
                       "quantities": [], "rows": []})
        if furniture.get("pagenum", True):
            ex.append({"id": f"pagenum{p}", "kind": "pagenum", "section": "", "text": str(p),
                       "units": [{"page": p, "text": str(p)}], "quantities": [], "rows": []})
        fn = furniture.get("footnotes", {}).get(p)
        if fn:
            ex.append({"id": f"footnote{p}", "kind": "footnote", "section": "", "text": fn,
                       "units": [{"page": p, "text": fn}], "quantities": [], "rows": []})
    truth["excluded"] = ex


def _grid_layout(seed: int, stream: str):
    """Four independent paragraphs in a 2 x 2 grid whose rows share baselines: row-major and column-major reading
    are both defensible. Blocks A B / C D."""
    c = Content(seed)
    gutter, colw = 14.0, 243.0
    cells = {"A": (56, 150), "B": (56 + colw + gutter, 150), "C": (56, 330), "D": (56 + colw + gutter, 330)}
    units, blocks = [], []
    title = f"Four Independent Notes on {c.method}"
    units.append(Unit(1, 56, 70, [title], 15, True, "title", "title"))
    blocks.append({"id": "title", "kind": "title", "section": "", "text": title, "units": [{"page": 1, "text": title}],
                   "quantities": [], "rows": []})
    for name, (x, y) in cells.items():
        head = f"Note {name}"
        units.append(Unit(1, x, y - 22, [head], 11, True, f"h_{name}", "heading"))
        blocks.append({"id": f"h_{name}", "kind": "heading", "section": "other", "text": head,
                       "units": [{"page": 1, "text": head}], "quantities": [], "rows": []})
        text = c.paragraph(6)
        lines = _wrap(text, colw, 9.5, False)[:12]
        text = " ".join(lines)
        units.append(Unit(1, x, y, lines, 9.5, False, f"note{name}", "para"))
        blocks.append({"id": f"note{name}", "kind": "para", "section": "other", "text": text,
                       "units": [{"page": 1, "text": text}], "quantities": [], "rows": []})
    return units, blocks, c


LAYOUTS = [
    # id, category, stream, builder kwargs
    ("L01_single_natural", "single_column", "natural", dict(tpl="single", fill=3)),
    ("L02_twocol_natural", "two_column", "natural", dict(tpl="two", fill=3)),
    ("L02_twocol_blocks_y", "two_column", "blocks_y", dict(tpl="two", fill=3)),
    ("L02_twocol_lines_y", "two_column", "lines_y", dict(tpl="two", fill=3)),
    ("L02_twocol_shuffled", "two_column", "shuffled", dict(tpl="two", fill=3)),
    ("L03_spanning_natural", "two_column_spanning", "natural", dict(tpl="spanning", fill=9, span=True)),
    ("L03_spanning_blocks_y", "two_column_spanning", "blocks_y", dict(tpl="spanning", fill=9, span=True)),
    ("L04_pagebreak_single", "page_boundaries", "natural", dict(tpl="single", fill=3, pagebreak=True)),
    ("L04_pagebreak_twocol", "page_boundaries", "blocks_y", dict(tpl="two", fill=3, pagebreak=True)),
    ("L05_tables_natural", "captions_tables", "natural", dict(tpl="two", fill=3, tables=True)),
    ("L05_tables_blocks_y", "captions_tables", "blocks_y", dict(tpl="two", fill=3, tables=True)),
    ("L06_quantities_natural", "quantities", "natural", dict(tpl="two", fill=3, quantities=True)),
    ("L06_quantities_blocks_y", "quantities", "blocks_y", dict(tpl="two", fill=3, quantities=True)),
    ("L07_furniture_single", "furniture", "natural", dict(tpl="single", fill=26, furniture=True)),
    ("L08_mixed_blocks_y", "mixed_columns", "blocks_y", dict(tpl="mixed", fill=4)),
    ("L09_tight_natural", "tight_gutter", "natural", dict(tpl="two_tight", fill=3)),
    ("L09_tight_blocks_y", "tight_gutter", "blocks_y", dict(tpl="two_tight", fill=3)),
    # stress layouts, added after the first baseline run to test limits the parser was not written against
    ("L11_threecol_blocks_y", "stress_three_columns", "blocks_y", dict(tpl="three", fill=4)),
    ("L12_unequal_blocks_y", "stress_unequal_columns", "blocks_y", dict(tpl="unequal", fill=3)),
    ("L13_sparse_column_blocks_y", "stress_sparse_column", "blocks_y", dict(tpl="sparse", fill=3)),
    ("L10_grid_lines_y", "ambiguous", "lines_y", dict(tpl="grid")),
]


def make(doc_id: str) -> tuple[bytes, dict]:
    spec = next(s for s in LAYOUTS if s[0] == doc_id)
    _, category, stream, kw = spec
    seed = int(hashlib.sha1(doc_id.encode()).hexdigest()[:8], 16)
    if kw["tpl"] == "grid":
        units, blocks, c = _grid_layout(seed, stream)
        pdf_units = units
        by = {b["id"]: b for b in blocks}
        pdf = draw(pdf_units, 1, stream, seed, {"pagenum": True})
        truth = {"id": doc_id, "category": category, "stream": stream, "seed": seed, "n_pages": 1,
                 "title": by["title"]["text"], "blocks": blocks, "claims": [],
                 "headings": [{"text": b["text"], "section": ""} for b in blocks if b["kind"] == "heading"],
                 "multi_unit_blocks": [], "ambiguous": True,
                 "accepted_orders": [["noteA", "noteB", "noteC", "noteD"], ["noteA", "noteC", "noteB", "noteD"]],
                 "excluded": [{"id": "pagenum1", "kind": "pagenum", "section": "", "text": "1",
                               "units": [{"page": 1, "text": "1"}], "quantities": [], "rows": []}]}
        return pdf, truth
    items, c = logical_items(seed, kw.get("fill", 3), tables=kw.get("tables", False), quantities=kw.get("quantities", False))
    furniture: dict = {"pagenum": True}
    if kw.get("furniture"):
        furniture["header"] = lambda p: "A. Writer and B. Author" if p % 2 == 0 else "Synthetic Layout Benchmark"
    if kw.get("pagebreak"):
        # a heading left alone at the bottom of a page: the paragraph that belongs to it starts on the next page
        for i, it in enumerate(items):
            if it.bid == "h_meth":
                it.orphan = True
            if it.bid in ("intro1", "results0"):
                it.split_lines = 5
    if kw.get("span"):
        span_text = Content(seed + 1).paragraph(4)
        pos = next(i for i, it in enumerate(items) if it.bid == "meth1")
        items.insert(pos + 1, Item("para", span_text, section="method", tag="full", bid="spanning0"))
    tpl = {"single": tpl_single, "two": tpl_two(), "spanning": tpl_spanning(), "mixed": tpl_mixed(),
           "two_tight": tpl_two(gutter=6.0), "three": tpl_three(), "unequal": tpl_unequal(),
           "sparse": tpl_sparse()}[kw["tpl"]]
    two = kw["tpl"] != "single"
    flow = Flow(tpl, body=8.5 if kw["tpl"] == "three" else 9.0 if two else 10.0,
                lead=10.2 if kw["tpl"] == "three" else 11.0 if two else 12.5)
    if kw.get("pagebreak") and not two:
        # leave only the heading's own line at the bottom of page 1 by padding its region before it
        pass
    for it in items:
        flow.place(it)
    if kw.get("furniture"):
        furniture["footnotes"] = {1: "*Equal contribution. The author order was assigned at random.",
                                  3: "1 The made-up institute is not a real institution."}
    pdf = draw(flow.units, flow.n_pages, stream, seed, furniture)
    truth = build_truth(doc_id, category, stream, seed, flow, items, c, {"ambiguous": False})
    _decorate(truth, furniture, flow)
    return pdf, truth


def write_all(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for spec in LAYOUTS:
        pdf, truth = make(spec[0])
        (out / f"{spec[0]}.pdf").write_bytes(pdf)
        (out / f"{spec[0]}.truth.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False), encoding="utf-8")
        manifest[spec[0]] = {"pdf_sha256": hashlib.sha256(pdf).hexdigest(),
                             "truth_sha256": hashlib.sha256(json.dumps(truth, sort_keys=True).encode()).hexdigest(),
                             "pages": truth["n_pages"], "category": spec[1], "stream": spec[2]}
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
    else:
        m = write_all(Path(sys.argv[1]))
        print(f"{len(m)} layouts written to {sys.argv[1]}")
