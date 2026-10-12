"""Reading order, columns, page breaks and furniture (0.5.0-dev), and the synthetic layout benchmark itself.

Everything is synthetic: the layout documents come from eval/layout_synth.py (seeded, independent of the parser) and the
small cases are drawn here with PyMuPDF or built as line tuples by hand. Passing says the parser handles these
geometries, not that it handles real papers (docs/EVALUATION.md section 11).
"""
import hashlib
import json
import math
import re
from pathlib import Path

import pymupdf
import pytest

from eval import layout_bench, layout_synth
from paperlens.ingest import (AMBIGUOUS_LAYOUT, _build, _FOOTNOTE_START, _make_line, _reorder_columns, _running_headers,
                              _side_by_side)

PROSE = ("The detector records every event that passes the trigger selection and each run is calibrated against a "
         "reference source before the analysis begins. ")


# ---- the benchmark ---------------------------------------------------------------------------------------------

def test_generator_is_deterministic_and_independent_of_the_parser(tmp_path):
    src = Path(layout_synth.__file__).read_text(encoding="utf-8")
    assert "paperlens" not in src.replace("PaperLens", "")            # the truth is built without the parser
    a = layout_synth.write_all(tmp_path / "a")
    b = layout_synth.write_all(tmp_path / "b")
    assert a == b and len(a) == len(layout_synth.LAYOUTS) >= 21
    assert {v["category"] for v in a.values()} >= {"single_column", "two_column", "two_column_spanning", "page_boundaries",
                                                  "captions_tables", "quantities", "furniture", "mixed_columns",
                                                  "tight_gutter", "ambiguous"}


def test_ground_truth_is_complete_and_consistent(tmp_path):
    layout_synth.write_all(tmp_path)
    for spec in layout_synth.LAYOUTS:
        t = json.loads((tmp_path / f"{spec[0]}.truth.json").read_text(encoding="utf-8"))
        ids = [b["id"] for b in t["blocks"]]
        assert len(ids) == len(set(ids))
        for b in t["blocks"]:
            assert b["text"] == " ".join(u["text"] for u in b["units"] if u["text"]) or b["kind"] in ("table", "figure")
            assert all(1 <= u["page"] <= t["n_pages"] for u in b["units"])
        for c in t["claims"]:                         # every claim and its evidence sit in the designated blocks
            blocks = {b["id"]: b["text"] for b in t["blocks"]}
            assert c["text"] in blocks[c["block"]] and c["evidence_text"] in blocks[c["evidence_block"]]
            assert 1 <= c["page"] <= t["n_pages"] and 1 <= c["evidence_page"] <= t["n_pages"]


def test_pagebreak_layouts_really_break_sentences_and_headings(tmp_path):
    layout_synth.write_all(tmp_path)
    t = json.loads((tmp_path / "L04_pagebreak_single.truth.json").read_text(encoding="utf-8"))
    crossing = [b for b in t["blocks"] if len({u["page"] for u in b["units"] if u["text"]}) > 1]
    assert crossing and all(not b["units"][0]["text"].rstrip().endswith(".") for b in crossing)   # cut mid-sentence
    pages = {b["id"]: b["units"][0]["page"] for b in t["blocks"]}
    assert pages["meth0"] > pages["h_meth"]                                   # heading alone at the end of a page


@pytest.fixture(scope="module")
def bench(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    layout_synth.write_all(out)
    res = {}
    for spec in layout_synth.LAYOUTS:
        truth = json.loads((out / f"{spec[0]}.truth.json").read_text(encoding="utf-8"))
        analysis = layout_bench.analyze_pdf(out / f"{spec[0]}.pdf")
        res[spec[0]] = layout_bench.evaluate(truth, analysis)
    return res


# minimum scores per layout, set from the post-change run (a regression test, not a claim about real papers)
FLOORS = {"block_recall": 0.99, "block_precision": 0.99, "order_acc": 0.99, "para_recon": 0.99, "page_acc": 0.99,
          "claim_recall": 0.99, "evidence_rate": 0.99, "heading_recall": 0.99, "section_acc": 0.99,
          "quantity_recall": 0.99, "table_recall": 0.99, "title_ok": 1.0}
KNOWN_WEAK = {"L13_sparse_column_blocks_y": {"order_acc": 0.9, "para_recon": 0.85}}   # documented limitation


@pytest.mark.parametrize("doc_id", [s[0] for s in layout_synth.LAYOUTS])
def test_layout_scores_do_not_regress(bench, doc_id):
    m = bench[doc_id]
    floors = {**FLOORS, **KNOWN_WEAK.get(doc_id, {})}
    for k, floor in floors.items():
        if m[k] == m[k]:                              # NaN: not applicable to this layout
            assert m[k] >= floor, (doc_id, k, m[k])
    assert m["spliced"] == 0 and m["furniture_leaks"] == 0 and m["spurious_claims"] == 0 and m["evidence_mixed"] == 0, m


def test_only_the_ambiguous_layout_is_flagged(bench):
    flagged = {k for k, m in bench.items() if m["layout_warning"]}
    assert flagged == {"L10_grid_lines_y"}
    assert bench["L10_grid_lines_y"]["ambiguity_safe"] == 1.0


# ---- reordering lines (hand-made geometry) ------------------------------------------------------------------------

def _span(text, x0, y0, x1, y1, size=9.0):
    return {"text": text, "bbox": (x0, y0, x1, y1), "size": size, "flags": 0, "font": "Synthetic"}


def _line(text, x0, y0, x1=None, size=9.0, block=0):
    x1 = x1 or x0 + 5 * len(text)
    sp = _span(text, x0, y0, x1, y0 + size + 2, size)
    return (text, size, False, y0, block, sp["bbox"], False, [sp])


def _col(x0, y0, n, tag, width=230):
    return [_line(f"{tag} line {i} of a column with some running text", x0, y0 + 11 * i, x0 + width, block=hash(tag) % 97)
            for i in range(n)]


def test_columns_are_read_one_after_the_other_whatever_the_stream_order():
    left, right = _col(56, 100, 8, "L"), _col(318, 100, 8, "R")
    interleaved = [x for pair in zip(left, right) for x in pair]
    for stream in (left + right, interleaved, right + left, list(reversed(left + right))):
        out, info = _reorder_columns(list(stream))
        assert info["columns"] and not info["ambiguous"]
        assert [ln[0].split()[0] for ln in out] == ["L"] * 8 + ["R"] * 8


def test_full_width_strip_is_read_before_and_after_the_columns():
    top = [_line("T full width title line spanning both columns %d" % i, 56, 60 + 11 * i, 540) for i in range(3)]
    cols = _col(56, 120, 6, "L") + _col(318, 120, 6, "R")
    bottom = [_line("B full width paragraph at the foot of the page %d" % i, 56, 300 + 11 * i, 540) for i in range(2)]
    shuffled = bottom + cols[6:] + top + cols[:6]
    out, info = _reorder_columns(shuffled)
    assert [ln[0].split()[0] for ln in out] == ["T"] * 3 + ["L"] * 6 + ["R"] * 6 + ["B"] * 2


def test_one_column_page_is_left_exactly_as_delivered_unless_the_stream_runs_upwards():
    ok = [_line("single column paragraph line number %d with text" % i, 56, 100 + 11 * i, 540) for i in range(12)]
    out, info = _reorder_columns(list(ok))
    assert out == ok and not info["columns"]
    shuffled = ok[6:] + ok[:6]                          # an out-of-order stream of one column is sorted by position
    assert [ln[3] for ln in _reorder_columns(list(shuffled))[0]] == [ln[3] for ln in ok]


def test_short_cells_side_by_side_are_not_taken_for_columns():
    rows = []
    for i in range(8):
        rows += [_line("Model %d" % i, 56, 100 + 12 * i, 100), _line("91.%d" % i, 200, 100 + 12 * i, 230),
                 _line("0.0%d" % i, 330, 100 + 12 * i, 360)]
    out, info = _reorder_columns(list(rows))
    assert out == rows and not info["columns"]
    assert _side_by_side(rows)


def test_two_by_two_grid_is_flagged_and_read_in_rows_without_mixing():
    cells = []
    for r, y in enumerate((100, 300)):
        for c, x in enumerate((56, 318)):
            cells += _col(x, y, 12, "ABCD"[2 * r + c])
    out, info = _reorder_columns(list(reversed(cells)))
    assert info["ambiguous"]
    order = [ln[0].split()[0] for ln in out]
    assert order == ["A"] * 12 + ["B"] * 12 + ["C"] * 12 + ["D"] * 12


def test_a_page_number_alone_does_not_make_a_page_ambiguous():
    left, right = _col(56, 100, 10, "L"), _col(318, 100, 10, "R")
    number = _line("2", 300, 760, 306)
    out, info = _reorder_columns(left + right + [number])
    assert info["columns"] and not info["ambiguous"]


def test_a_column_that_ends_early_is_not_an_ambiguity():
    left = _col(56, 100, 10, "L") + _col(56, 400, 6, "M")
    right = _col(318, 100, 10, "R")                      # the right column stops; the left continues below
    out, info = _reorder_columns(left + right)
    assert not info["ambiguous"]


def test_a_line_carrying_both_columns_is_cut_at_the_gutter():
    left, right = _col(56, 100, 8, "L"), _col(318, 100, 8, "R")
    merged = []
    for a, b in zip(left, right):
        sps = a[7] + b[7]
        merged.append(_make_line(sps, a[4]))
    assert merged[0][0].startswith("L") and "R line" in merged[0][0]
    out, info = _reorder_columns(merged)
    assert [ln[0].split()[0] for ln in out] == ["L"] * 8 + ["R"] * 8


# ---- sentences over a page break, furniture, drop caps -----------------------------------------------------------

def _pages(draw, n=2):
    pdf = pymupdf.open()
    for k in range(n):
        draw(pdf.new_page(), k)
    return _build(pdf, "t", "synthetic.pdf")


def test_sentence_over_a_page_break_is_one_sentence_on_its_first_page():
    def draw(pg, n):
        if n == 0:
            pg.insert_text((60, 80), "Abstract", fontsize=12, fontname="hebo")
            pg.insert_textbox((60, 90, 540, 150), PROSE + "The calibration of the instrument was repeated under the same", fontsize=10)
        else:
            pg.insert_textbox((60, 70, 540, 160), "operating conditions for every selected run. " + PROSE, fontsize=10)
    doc = _pages(draw)
    hit = [s for s in doc.sentences if "calibration of the instrument" in s.text]
    assert len(hit) == 1 and hit[0].text.endswith("every selected run.") and hit[0].page == 1
    assert not any(s.text.startswith("operating conditions") for s in doc.sentences)


def test_unfinished_text_before_a_heading_is_not_glued_to_the_next_page():
    def draw(pg, n):
        if n == 0:
            pg.insert_text((60, 80), "Abstract", fontsize=12, fontname="hebo")
            pg.insert_textbox((60, 90, 540, 150), PROSE + "A list of items that is never finished", fontsize=10)
        else:
            pg.insert_text((60, 80), "1 Introduction", fontsize=12, fontname="hebo")
            pg.insert_textbox((60, 90, 540, 160), "Next section text that starts a new idea. " + PROSE, fontsize=10)
    doc = _pages(draw)
    s = [s for s in doc.sentences if "never finished" in s.text][0]
    assert s.page == 1 and "Next section" not in s.text
    assert [x for x in doc.sentences if "Next section" in x.text][0].section == "introduction"


def test_drop_cap_is_joined_to_its_word_and_ends_the_summary_box():
    def draw(pg, n):
        pg.insert_text((60, 70), "Summary", fontsize=11, fontname="hebo")
        pg.insert_textbox((60, 80, 300, 200), "We show a synthetic effect of 12 percent on a made-up task. " + PROSE, fontsize=9)
        pg.insert_text((60, 250), "P", fontsize=42, fontname="hebo")
        pg.insert_textbox((90, 232, 300, 330), "ublished synthetic findings are sometimes refuted by later work in the field. " + PROSE, fontsize=9)
    doc = _pages(draw, 1)
    assert any(s.text.startswith("Published synthetic findings") for s in doc.sentences)
    pub = [s for s in doc.sentences if s.text.startswith("Published")][0]
    assert pub.section != "abstract"
    assert any(s.section == "abstract" and "12 percent" in s.text for s in doc.sentences)


def test_alternating_running_heads_seen_twice_are_dropped_but_body_lines_are_not():
    def page(text, y=30):
        return {"lines": [(text, 8.5, False, y, 0, (56, y, 300, y + 9)), ("Body text unique to this page %d." % id(text), 10.0,
                                                                         False, 300, 1, (56, 300, 500, 310))],
                "height": 792}
    pages = [page("A. Writer and B. Author" if i % 2 else "Synthetic Layout Benchmark") for i in range(4)]
    words = ["alpha", "bravo", "charlie", "delta"]
    for i, p in enumerate(pages):
        p["lines"][1] = ("Body text for the %s page." % words[i], 10.0, False, 300, 1, (56, 300, 500, 310))
    out = _running_headers(pages)
    assert "A. Writer and B. Author" in out and "Synthetic Layout Benchmark" in out
    assert not any("Body text" in t for t in out)


def test_footnote_mark_followed_by_a_space_is_recognised():
    assert _FOOTNOTE_START.match("1 The made-up institute is not a real institution.")
    assert _FOOTNOTE_START.match("1The made-up institute") and _FOOTNOTE_START.match("*Equal contribution")
    assert not _FOOTNOTE_START.match("12 of the samples were measured")


# ---- table and caption stay where they are, existing behaviour --------------------------------------------------------

def test_ambiguous_layout_warning_text_names_the_pages():
    msg = AMBIGUOUS_LAYOUT.format(pages="2, 4")
    assert "2, 4" in msg and "ambiguous" in msg and re.search(r"layout", msg, re.I)
    assert math.isnan(float("nan"))
