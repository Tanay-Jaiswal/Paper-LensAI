"""Page numbers and running heads are removed; numbers in the page body are not (0.6.1-dev).

Before this change every line that consisted only of an integer was deleted on every page of a document of four or more
pages, because the page numbers made the pattern "a bare number" a repeated line. Every PDF here is SYNTHETIC (drawn
with PyMuPDF); the failure was first measured on development papers.
"""
import pymupdf

from paperlens.ingest import (_bare_numbers, _build, _drop_furniture, _loose_numbers, _page_number_lines, _page_lines,
                              _running_headers)

PROSE = ("The detector records every event that passes the trigger selection and each run is calibrated against a "
         "reference source before the analysis begins. ")
COUNTS = [["Split", "Supports", "Refutes", "Neutral", "All"], ["Train", "332", "173", "304", "809"],
          ["Dev", "124", "64", "112", "300"], ["Test", "100", "100", "100", "300"], ["Total", "556", "337", "516", "1409"]]


def _doc(draw, pages, height=792):
    pdf = pymupdf.open()
    for k in range(pages):
        draw(pdf.new_page(width=612, height=height), k)
    return _build(pdf, "t", "synthetic.pdf"), pdf


def _table(pg, x, y, rows, w=300.0, fs=8.5, rh=13.0):
    cw = (w - 0.3 * w) / (len(rows[0]) - 1)
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            cx = x + 3 if ci == 0 else x + 0.3 * w + ci * cw - 4 - pymupdf.get_text_length(cell, fontname="helv", fontsize=fs)
            pg.insert_text((cx, y + ri * rh + 9.5), cell, fontsize=fs, fontname="helv")
    return y + len(rows) * rh


WORDS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]


def _body(word, n=2):
    """Prose in which every line carries the page's own word, so that no line repeats from page to page."""
    return (f"The {word} detector records the {word} events of the {word} trigger and the {word} run is calibrated "
            f"against the {word} source before the {word} analysis of the {word} sample begins. ") * n


def _page(pg, k, number_at, table_on=1, extra=None):
    """One page of a synthetic paper; `number_at` is the baseline of the page number (None: no page number)."""
    if k == 0:
        pg.insert_text((60, 70), "Abstract", fontsize=12, fontname="hebo")
        pg.insert_textbox((60, 80, 540, 130), "We improve accuracy from 80.1% to 85.2% on a synthetic benchmark. " + PROSE, fontsize=10)
        pg.insert_text((60, 150), "1 Results", fontsize=12, fontname="hebo")
    pg.insert_textbox((60, 160, 540, 250), f"Paragraph {WORDS[k]} of the synthetic body text. " + _body(WORDS[k]), fontsize=10)
    if k == table_on:
        _table(pg, 60, 260, COUNTS)
    if extra:
        extra(pg, k)
    pg.insert_textbox((60, 360, 540, 440), f"The closing paragraph of page {WORDS[k]} ends here. " + _body(WORDS[k], 1), fontsize=10)
    if number_at is not None:
        pg.insert_text((300, number_at), str(k + 1), fontsize=9)


def _texts(doc, kinds=("text", "caption")):
    return [s.text for s in doc.sentences if s.kind in kinds]


def _assert_no_page_numbers(doc, pages):
    for n in range(1, pages + 1):
        assert not any(s.text.strip() == str(n) for s in doc.sentences), n
        assert not any(s.text.endswith(f"ends here. {n}") or s.text.endswith(f"begins. {n}") for s in doc.sentences), n


# ---- the bug: integer cells in the body of a document with page numbers -------------------------------------------

def test_integer_table_cells_survive_in_a_document_with_page_numbers_at_the_bottom():
    doc, _ = _doc(lambda pg, k: _page(pg, k, number_at=765), pages=6)
    rows = [s.text for s in doc.sentences if s.kind == "table"]
    assert rows == ["Table row: Train; Supports: 332; Refutes: 173; Neutral: 304; All: 809",
                    "Table row: Dev; Supports: 124; Refutes: 64; Neutral: 112; All: 300",
                    "Table row: Test; Supports: 100; Refutes: 100; Neutral: 100; All: 300",
                    "Table row: Total; Supports: 556; Refutes: 337; Neutral: 516; All: 1409"]
    assert all(s.page == 2 for s in doc.sentences if s.kind == "table")
    _assert_no_page_numbers(doc, 6)
    assert sum(t.startswith("Paragraph") for t in _texts(doc)) == 6 and sum(t.startswith("The closing paragraph") for t in _texts(doc)) == 6


def test_page_numbers_at_the_top_are_removed_and_body_integers_kept():
    doc, _ = _doc(lambda pg, k: _page(pg, k, number_at=40), pages=5)
    assert len([s for s in doc.sentences if s.kind == "table"]) == 4
    _assert_no_page_numbers(doc, 5)
    assert not any(t.startswith(("2 Paragraph", "3 Paragraph")) for t in _texts(doc))


def test_page_numbers_outside_the_edge_strip_are_found_by_their_sequence():
    """Seen on a development paper: the number sits at 87% of the page height, the lowest line of every page."""
    doc, pdf = _doc(lambda pg, k: _page(pg, k, number_at=690), pages=6)      # 690 / 792 = 0.87: not in the 8% strip
    pages = [{"lines": _page_lines(p), "height": p.rect.height} for p in pdf]
    assert len(_page_number_lines(pages)) == 6
    _assert_no_page_numbers(doc, 6)
    assert len([s for s in doc.sentences if s.kind == "table"]) == 4


def test_a_lone_integer_in_the_body_is_content_not_a_page_number():
    def extra(pg, k):
        if k == 3:
            pg.insert_text((60, 300), "The number of clusters that were enrolled in the synthetic trial was", fontsize=10)
            pg.insert_text((60, 313), "20", fontsize=10)
            pg.insert_text((60, 326), "and all of them completed the follow-up period.", fontsize=10)
    doc, _ = _doc(lambda pg, k: _page(pg, k, number_at=765, table_on=1, extra=extra), pages=6)
    s = [t for t in _texts(doc) if t.startswith("The number of clusters")]
    assert s == ["The number of clusters that were enrolled in the synthetic trial was 20 and all of them completed the follow-up period."]
    _assert_no_page_numbers(doc, 6)


def test_short_document_page_number_removed_and_integer_low_on_the_page_kept():
    """Fewer than four pages: no repeated-line test. A bare number at 91% of the page height used to be dropped."""
    def extra(pg, k):
        if k == 0:
            pg.insert_text((60, 700), "The synthetic count of valid runs after all exclusions were applied is", fontsize=10)
            pg.insert_text((60, 714), "147", fontsize=10)
            pg.insert_text((60, 728), "which is the denominator of every rate in this report.", fontsize=10)
    doc, _ = _doc(lambda pg, k: _page(pg, k, number_at=770, table_on=1, extra=extra), pages=2)
    assert any("is 147 which is the denominator" in t for t in _texts(doc))
    _assert_no_page_numbers(doc, 2)
    assert len([s for s in doc.sentences if s.kind == "table"]) == 4


def test_table_row_in_the_bottom_strip_is_not_taken_for_page_numbers():
    def extra(pg, k):
        if k == 2:
            _table(pg, 60, 720, [["Late row", "311", "412", "513", "614"], ["Last row", "321", "422", "523", "624"]])
    doc, _ = _doc(lambda pg, k: _page(pg, k, number_at=None, table_on=1, extra=extra), pages=6)
    late = [s.text for s in doc.sentences if s.text.startswith("Table row: Late row") or s.text.startswith("Table row: Last row")]
    assert late == ["Table row: Late row; 311; 412; 513; 614", "Table row: Last row; 321; 422; 523; 624"]


# ---- what must still be removed ------------------------------------------------------------------------------------

def test_running_heads_and_a_journal_footer_with_an_identifier_are_still_removed():
    def page(pg, k):
        _page(pg, k, number_at=None)
        pg.insert_text((56, 36), "A. Writer and B. Author" if k % 2 else "Synthetic Layout Benchmark", fontsize=8.5)
        pg.insert_text((56, 770), "0031-9007=16=116(6)=061102(16)", fontsize=8)        # an identifier and a page code,
        pg.insert_text((300, 770), f"061102-{k + 1}", fontsize=8)                          # both without a single letter
        pg.insert_text((420, 770), "Published by the Synthetic Society", fontsize=8)
    doc, _ = _doc(page, pages=6)
    joined = " ".join(s.text for s in doc.sentences)
    assert "A. Writer and B. Author" not in joined and "Synthetic Layout Benchmark" not in joined
    assert "061102-" not in joined and "Published by the Synthetic Society" not in joined
    assert sum(t.startswith("Paragraph") for t in _texts(doc)) == 6


def test_drop_furniture_rules_on_hand_made_lines():
    def ln(text, y, x0=56, x1=None):
        return (text, 9.0, False, y, 0, (x0, y, x1 or x0 + 6 * len(text), y + 9), False, [])
    lines = [ln("Synthetic Layout Benchmark", 30), ln("332", 300), ln("7", 765), ln("Body text of this page.", 320),
             ln("311", 760, 100), ln("412", 760, 200), ln("513", 760, 300)]
    out = _drop_furniture(lines, {"Synthetic Layout Benchmark", "#"}, 792)
    kept = [x[0] for x in out]
    assert "Synthetic Layout Benchmark" not in kept          # worded pattern: removed wherever it stands
    assert "332" in kept                                      # bare number in the body: content
    assert "7" not in kept                                    # bare number alone in the bottom strip: page number
    assert {"311", "412", "513"} <= set(kept)                 # a row of numbers in the strip: a table row
    assert "Body text of this page." in kept


def test_page_number_sequence_needs_position_and_count():
    def pg(n, y, text=None, extra_low=False):
        lines = [("Body text unique to page %d." % n, 10.0, False, 300, 1, (56, 300, 500, 310), False, []),
                 (text or str(n), 9.0, False, y, 2, (300, y, 310, y + 9), False, [])]
        if extra_low:
            lines.append(("A footnote below the number.", 8.0, False, y + 20, 3, (56, y + 20, 300, y + 28), False, []))
        return {"lines": lines, "height": 792}
    assert len(_page_number_lines([pg(n, 700) for n in range(1, 7)])) == 6                  # lowest line, counting up
    assert _page_number_lines([pg(n, 700, text="300") for n in range(1, 7)]) == set()        # the same number everywhere
    assert _page_number_lines([pg(n, 400) for n in range(1, 7)]) == set()                    # mid-page: not a page number
    assert _page_number_lines([pg(n, 700, extra_low=True) for n in range(1, 7)]) == set()    # not the lowest line
    assert _page_number_lines([pg(n, 700) for n in range(1, 3)]) == set()                    # too few pages to tell
    assert _running_headers([pg(n, 700) for n in range(1, 7)]) >= {"#"}                      # the pattern is still "repeated"


# ---- numbers that are neither a table nor a page number ------------------------------------------------------------

def test_axis_tick_numbers_are_not_glued_into_the_sentence_before_them():
    def extra(pg, k):
        if k == 2:
            pg.insert_text((60, 280), "The purpose of the synthetic schedule is to reduce the mismatch between pre-training", fontsize=10)
            for j, tick in enumerate(["84", "82", "80", "78", "76"]):
                pg.insert_text((40, 292 + 11 * j), tick, fontsize=7)
    doc, _ = _doc(lambda pg, k: _page(pg, k, number_at=765, extra=extra), pages=6)
    s = [t for t in _texts(doc) if t.startswith("The purpose of the synthetic schedule")]
    assert len(s) == 1 and "84" not in s[0] and "76" not in s[0]
    assert "84 82 80 78 76" in " ".join(x.text for x in doc.sentences if x.kind == "meta")     # kept, never a claim or evidence


def test_loose_number_rule_leaves_single_values_and_citation_lists_alone():
    def ln(text, block=0):
        return (text, 9.0, False, 100, block, (56, 100, 200, 109), False, [])
    lines = [ln("the scaling factor of"), ln("1"), ln("over the root, with references [27, 29,"), ln("35, 37, 43, 46, 47,"),
             ln("50] in the text."), ln("60"), ln("40"), ln("20"), ln("after the axis.")]
    keep, loose = _loose_numbers(lines)
    assert [x[0] for x in loose] == ["60", "40", "20"]
    assert [x[0] for x in keep] == ["the scaling factor of", "1", "over the root, with references [27, 29,", "35, 37, 43, 46, 47,",
                                    "50] in the text.", "after the axis."]
    assert _bare_numbers("0.2 0.4 0.6") == 3 and _bare_numbers("35, 37, 43,") == 0 and _bare_numbers("Tok 1") == 0
