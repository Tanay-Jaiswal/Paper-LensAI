"""Tables without a grid (0.6.0-dev): their cells must not be read as prose or glued to the text around them.

Every PDF here is SYNTHETIC, drawn in the test with PyMuPDF; no text comes from a real paper. The failures they
reproduce were first seen on development papers (a whole table read as one sentence; a table row running into the
next paragraph or into a caption). Passing says the parser handles these geometries, not that it handles real papers.
"""
import pymupdf
import pytest

from paperlens.claims import build_ledger, extract_claims
from paperlens.ingest import UNLABELLED_ROWS, _build, _numeric_cell, _open_tables, _page_lines, _prose_cell

PROSE = ("The detector records every event that passes the trigger selection and each run is calibrated against a "
         "reference source before the analysis begins. ")
ROWS = [["Model", "Accuracy", "Error", "Params"],
        ["Baseline", "80.1", "19.9 ± 0.4", "12.4M"],
        ["Kestrel", "85.2", "14.8 ± 0.2", "48.0M"],
        ["Ablation", "83.9", "16.1 ± 0.3", "47.1M"],
        ["No pretraining", "75.9", "-", "48.0M"]]


def _doc(draw, pages=1, width=612, height=792):
    pdf = pymupdf.open()
    for k in range(pages):
        draw(pdf.new_page(width=width, height=height), k)
    return _build(pdf, "t", "synthetic.pdf"), pdf


def _table(pg, x, y, rows, w=300.0, fs=8.5, rh=13.0, order="rows", bold_head=True, first=0.34):
    """Cells drawn one by one with white space only: first column left-aligned, the others right-aligned."""
    n = max(len(r) for r in rows)
    cw = (w - first * w) / (n - 1)
    ops = []
    for ri, row in enumerate(rows):
        for ci, cell in enumerate(row):
            if cell is None:
                continue
            font = "hebo" if (ri == 0 and bold_head) else "helv"
            cx = x + 3 if ci == 0 else x + first * w + ci * cw - 4 - pymupdf.get_text_length(cell, fontname=font, fontsize=fs)
            ops.append((ri, ci, cx, y + ri * rh + 9.5, cell, font))
    if order == "cols":
        ops.sort(key=lambda o: (o[1], o[0]))
    for _, _, cx, cy, cell, font in ops:
        pg.insert_text((cx, cy), cell, fontsize=fs, fontname=font)
    return y + len(rows) * rh


def _abstract(pg, text="We improve accuracy from 80.1% to 85.2% on a synthetic benchmark. "):
    pg.insert_text((60, 70), "Abstract", fontsize=12, fontname="hebo")
    pg.insert_textbox((60, 80, 540, 130), text + PROSE, fontsize=10)
    pg.insert_text((60, 150), "1 Results", fontsize=12, fontname="hebo")


def _kinds(doc, kind):
    return [s.text for s in doc.sentences if s.kind == kind]


def _prose(doc):
    return [s for s in doc.sentences if s.kind in ("text", "caption")]


def _no_cells_in_prose(doc, rows=ROWS):
    for s in _prose(doc):
        for row in rows:
            cells = [c for c in row if c]
            for a, b in zip(cells, cells[1:]):
                assert f"{a} {b}" not in s.text and f"{a}{b}" not in s.text, (s.text, a, b)


# ---- the table itself --------------------------------------------------------------------------------------------

def test_unruled_table_between_two_paragraphs_becomes_table_rows():
    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 215), "The first paragraph ends before the table and reports 12 runs. " + PROSE, fontsize=10)
        pg.insert_textbox((60, 222, 540, 240), "Table 1: Accuracy and error of the synthetic systems.", fontsize=8.5)
        end = _table(pg, 60, 242, ROWS)
        pg.insert_textbox((60, end + 12, 540, end + 70), "The paragraph after the table starts a new thought here. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    assert _kinds(doc, "table") == [
        "Table row: Baseline; Accuracy: 80.1; Error: 19.9 ± 0.4; Params: 12.4M",
        "Table row: Kestrel; Accuracy: 85.2; Error: 14.8 ± 0.2; Params: 48.0M",
        "Table row: Ablation; Accuracy: 83.9; Error: 16.1 ± 0.3; Params: 47.1M",
        "Table row: No pretraining; Accuracy: 75.9; Error: -; Params: 48.0M"]
    assert "Table header: Model; Accuracy; Error; Params" in _kinds(doc, "meta")
    assert _kinds(doc, "caption") == ["Table 1: Accuracy and error of the synthetic systems."]
    _no_cells_in_prose(doc)
    texts = [s.text for s in doc.sentences]
    order = [next(i for i, t in enumerate(texts) if t.startswith(p)) for p in
             ("The first paragraph ends", "Table 1:", "Table row: Baseline", "Table row: No pretraining", "The paragraph after the table")]
    assert order == sorted(order)                                   # reading order: paragraph, caption, rows, paragraph
    assert all(s.page == 1 and s.section == "results" for s in doc.sentences if s.kind == "table")
    assert doc.warnings == []


def test_table_rows_are_usable_as_evidence_and_never_a_claim():
    def draw(pg, n):
        _abstract(pg, "Our Kestrel system improves accuracy from 80.1 to 85.2 on the synthetic benchmark. ")
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        _table(pg, 60, 210, ROWS)
    doc, _ = _doc(draw)
    claims = build_ledger(doc)
    assert all(not c.text.startswith("Table") and "Baseline 80.1" not in c.text for c in claims)
    c = next(c for c in claims if "85.2" in c.text)
    assert any(e.quote.startswith("Table row: Kestrel") and "85.2" in e.shared_numbers for e in c.evidence)


@pytest.mark.parametrize("order", ["rows", "cols"])
def test_table_in_one_column_leaves_the_other_column_alone(order):
    right = "The right column is ordinary prose that shares its baselines with the table rows on the left. " + PROSE * 3

    def draw(pg, n):
        pg.insert_text((56, 70), "Abstract", fontsize=11, fontname="hebo")
        pg.insert_textbox((56, 80, 556, 120), "We report a synthetic result of 7 percent on a made-up task. " + PROSE, fontsize=9)
        pg.insert_textbox((56, 140, 294, 230), PROSE * 2, fontsize=9)
        end = _table(pg, 56, 236, ROWS, w=238.0, fs=7.5, order=order, first=0.30)
        pg.insert_textbox((56, end + 10, 294, 520), "Text under the table in the left column continues the section. " + PROSE * 2, fontsize=9)
        pg.insert_textbox((318, 140, 556, 520), right, fontsize=9)
    doc, _ = _doc(draw)
    assert len(_kinds(doc, "table")) == 4 and _kinds(doc, "table")[1].startswith("Table row: Kestrel; Accuracy: 85.2")
    _no_cells_in_prose(doc)
    whole = [s for s in doc.sentences if s.text.startswith("The right column is ordinary prose")]
    assert len(whole) == 1 and whole[0].text.endswith("on the left.") and whole[0].kind == "text"
    texts = [s.text for s in doc.sentences]
    i_tab = next(i for i, t in enumerate(texts) if t.startswith("Table row: Baseline"))
    i_under = next(i for i, t in enumerate(texts) if t.startswith("Text under the table"))
    i_right = next(i for i, t in enumerate(texts) if t.startswith("The right column"))
    assert i_tab < i_under < i_right                                # left column, top to bottom, then the right column


def test_full_width_table_on_a_two_column_page():
    wide = [["System", "Dev EM", "Dev F1", "Test EM", "Test F1", "Params", "Steps"],
            ["Reference system", "81.2", "87.9", "82.3", "88.5", "110M", "1.0M"],
            ["Larger system", "84.1", "90.9", "85.1", "91.8", "340M", "1.0M"],
            ["Ensemble system", "85.8", "91.8", "86.7", "92.4", "680M", "2.0M"]]

    def draw(pg, n):
        pg.insert_text((56, 70), "Abstract", fontsize=11, fontname="hebo")
        pg.insert_textbox((56, 80, 556, 120), "We report a synthetic result of 7 percent on a made-up task. " + PROSE, fontsize=9)
        end = _table(pg, 56, 130, wide, w=500.0, fs=8.5, first=0.25)
        pg.insert_textbox((56, end + 14, 294, 500), "The left column starts under the wide table and goes on. " + PROSE * 3, fontsize=9)
        pg.insert_textbox((318, end + 14, 556, 500), "The right column starts under the wide table as well. " + PROSE * 3, fontsize=9)
    doc, _ = _doc(draw)
    rows = _kinds(doc, "table")
    assert len(rows) == 3
    assert rows[1] == "Table row: Larger system; Dev EM: 84.1; Dev F1: 90.9; Test EM: 85.1; Test F1: 91.8; Params: 340M; Steps: 1.0M"
    _no_cells_in_prose(doc, wide)
    texts = [s.text for s in doc.sentences]
    assert next(i for i, t in enumerate(texts) if t.startswith("The left column")) < \
        next(i for i, t in enumerate(texts) if t.startswith("The right column"))


def test_table_with_horizontal_rules_only():
    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        end = _table(pg, 60, 210, ROWS)
        for y in (208.5, 222.5, end + 0.5):
            pg.draw_line((60, y), (360, y), width=0.6)
        pg.insert_textbox((60, end + 12, 540, end + 60), "Text below the ruled table is a paragraph. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    assert len(_kinds(doc, "table")) == 4
    _no_cells_in_prose(doc)
    assert any(s.text.startswith("Text below the ruled table") and s.kind == "text" for s in doc.sentences)


def test_two_level_header_and_a_missing_cell_are_not_guessed():
    rows = [[None, "Dev", None, "Test", None],
            ["System", "EM", "F1", "EM", "F1"],
            ["Reference system", "81.2", "87.9", "82.3", "88.5"],
            ["Published system", "-", "85.6", None, "85.8"],
            ["Larger system", "84.1", "90.9", "85.1", "91.8"]]

    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        _table(pg, 60, 210, rows, w=320.0, bold_head=False)
    doc, _ = _doc(draw)
    tab = _kinds(doc, "table")
    assert tab[0] == "Table row: Reference system; EM: 81.2; F1: 87.9; EM: 82.3; F1: 88.5"
    # the row with a missing cell keeps its own cells in their own order; no value is moved into the empty place
    assert tab[1] == "Table row: Published system; EM: -; F1: 85.6; F1: 85.8"
    assert "Table header: Dev; Test" in _kinds(doc, "meta") and "Table header: System; EM; F1; EM; F1" in _kinds(doc, "meta")
    _no_cells_in_prose(doc, [[c for c in r if c] for r in rows])


# ---- the text around it ------------------------------------------------------------------------------------------

def test_table_in_the_middle_of_a_sentence_does_not_cut_the_sentence():
    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 200), PROSE + "The gain is largest for the two systems that", fontsize=10)
        end = _table(pg, 60, 205, ROWS)
        pg.insert_textbox((60, end + 10, 540, end + 60), "were trained with the synthetic schedule, as the table shows. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    whole = [s for s in doc.sentences if s.text.startswith("The gain is largest")]
    assert len(whole) == 1 and whole[0].text == ("The gain is largest for the two systems that were trained with the synthetic "
                                                 "schedule, as the table shows.")
    assert len(_kinds(doc, "table")) == 4
    texts = [s.text for s in doc.sentences]
    assert texts.index(whole[0].text) < next(i for i, t in enumerate(texts) if t.startswith("Table row: Baseline"))
    _no_cells_in_prose(doc)


def test_caption_without_a_full_stop_is_not_joined_to_the_text_after_the_table():
    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        pg.insert_textbox((60, 204, 540, 220), "Table 2: Accuracy and error of the synthetic systems", fontsize=8.5)
        end = _table(pg, 60, 224, ROWS)
        pg.insert_textbox((60, end + 12, 540, end + 60), "The paragraph after the table starts with a capital letter. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    cap = [s for s in doc.sentences if s.text.startswith("Table 2")]
    assert len(cap) == 1 and cap[0].text == "Table 2: Accuracy and error of the synthetic systems"
    assert any(s.text.startswith("The paragraph after the table starts") for s in doc.sentences)


def test_single_numeric_row_is_not_glued_to_the_sentence_below_it():
    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        _table(pg, 60, 205, [["Score", "0.61", "0.47", "0.52", "0.53", "0.65"]], bold_head=False)
        pg.insert_textbox((60, 226, 540, 290), "We evaluate the method on a synthetic collection of 500 documents. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    assert _kinds(doc, "table") == ["Table row: Score; 0.61; 0.47; 0.52; 0.53; 0.65"]
    s = [s for s in doc.sentences if s.text.startswith("We evaluate the method")]
    assert len(s) == 1 and s[0].kind == "text" and "0.61" not in s[0].text


def test_numeric_row_typed_with_ordinary_spaces_is_not_glued_to_the_sentence_before_it():
    """Seen on a development paper: a line "label 0.61 0.47 ..." under a paragraph whose last line has no full stop."""
    def draw(pg, n):
        _abstract(pg)
        pg.insert_text((60, 170), "Our synthetic server folded the hardest target, a made-up protein of 182", fontsize=10)
        pg.insert_text((60, 190), "Score 0.61 0.47 0.52 0.53 0.65 0.34 0.71 0.48 0.61 0.35", fontsize=8)
        pg.insert_textbox((60, 205, 540, 270), "The next paragraph is ordinary prose about the measurement. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    s = [s for s in doc.sentences if s.text.startswith("Our synthetic server")]
    assert len(s) == 1 and "0.61" not in s[0].text and s[0].kind == "text"
    assert _kinds(doc, "table") == ["Table row: Score; 0.61; 0.47; 0.52; 0.53; 0.65; 0.34; 0.71; 0.48; 0.61; 0.35"]
    assert all("0.61 0.47" not in x.text for x in _prose(doc))


def test_rows_without_a_label_are_kept_but_flagged_and_never_evidence():
    ticks = [["50", "60", "70", "80", "90", "100"], ["0.2", "0.4", "0.6", "0.8", "1.0", "1.2"]]

    def draw(pg, n):
        _abstract(pg, "We measure a synthetic efficiency of 0.8 at a mass of 80 units. ")
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        _table(pg, 60, 205, ticks, bold_head=False)
        pg.insert_textbox((60, 240, 540, 300), "The next paragraph is ordinary prose about the measurement. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    assert _kinds(doc, "table") == []
    assert "Table row: 50; 60; 70; 80; 90; 100" in _kinds(doc, "meta")
    assert doc.warnings == [UNLABELLED_ROWS.format(pages="1")]
    for c in build_ledger(doc):
        assert all(not e.quote.startswith("Table row: 50") and not e.quote.startswith("Table row: 0.2") for e in c.evidence)
    assert all("60 70" not in s.text for s in _prose(doc))


# ---- what is not a table -----------------------------------------------------------------------------------------

def _no_table(doc):
    assert _kinds(doc, "table") == [] and not any(t.startswith("Table ") for t in _kinds(doc, "meta")), \
        [s.text for s in doc.sentences if s.kind in ("table", "meta")]
    assert not any("Table text" in w for w in doc.warnings)


def test_a_paragraph_full_of_numbers_stays_prose():
    text = ("In 12 of the 48 runs the error fell from 19.9% to 14.8%, in 30 runs it stayed within 0.5 points, and in 6 runs "
            "it rose by 1.2 to 3.4 points. The 95% interval is 13.9 to 15.7 and the p-value is 0.003 for 48 runs. ")

    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 300), text * 3 + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    _no_table(doc)
    assert sum(s.text.startswith("In 12 of the 48 runs") and s.kind == "text" for s in doc.sentences) == 3


def test_numbered_list_equation_with_number_and_reference_list_are_not_tables():
    def draw(pg, n):
        _abstract(pg)
        for k in range(4):
            pg.insert_text((60, 170 + 14 * k), f"{k + 1}. The step number {k + 1} of the synthetic procedure is carried out.", fontsize=10)
        for k in range(3):                                           # display equations with their numbers at the right
            pg.insert_text((200, 250 + 22 * k), f"y = {k + 2}.5 x + 0.{k + 1}", fontsize=10)
            pg.insert_text((520, 250 + 22 * k), f"({k + 1})", fontsize=10)
        pg.insert_text((60, 340), "References", fontsize=12, fontname="hebo")
        for k in range(5):
            pg.insert_text((60, 358 + 12 * k), f"[{k + 1}] A. Author and B. Writer, A synthetic title, Journal of Results {10 + k}, {100 + k}-{110 + k} (20{10 + k}).", fontsize=8.5)
    doc, _ = _doc(draw)
    _no_table(doc)
    assert sum(s.section == "references" for s in doc.sentences) == 5


def test_two_column_prose_and_an_author_block_in_columns_are_not_tables():
    def draw(pg, n):
        pg.insert_text((140, 60), "A Synthetic Title About Layout", fontsize=16, fontname="hebo")
        for k, name in enumerate(["Ada Writer", "Ben Author", "Cleo Scribe"]):
            pg.insert_text((80 + 170 * k, 90), name, fontsize=10)
            pg.insert_text((80 + 170 * k, 103), f"Institute {k + 1} of Synthetic Studies", fontsize=9)
            pg.insert_text((80 + 170 * k, 115), f"writer{k + 1}@example.org", fontsize=9)
        pg.insert_text((56, 150), "Abstract", fontsize=11, fontname="hebo")
        pg.insert_textbox((56, 160, 556, 200), "We report a synthetic result of 7 percent on a made-up task. " + PROSE, fontsize=9)
        pg.insert_textbox((56, 220, 294, 500), "In 2019 we ran 48 trials. " + PROSE * 4, fontsize=9)
        pg.insert_textbox((318, 220, 556, 500), "In 2020 we ran 52 trials. " + PROSE * 4, fontsize=9)
    doc, _ = _doc(draw)
    _no_table(doc)
    assert any(s.text == "In 2019 we ran 48 trials." for s in doc.sentences) and any(s.text == "In 2020 we ran 52 trials." for s in doc.sentences)


def test_contents_page_is_still_a_contents_page():
    def draw(pg, n):
        if n == 0:
            pg.insert_text((60, 70), "Contents", fontsize=14, fontname="hebo")
            for k in range(10):
                pg.insert_text((60, 100 + 14 * k), f"{k + 1} Section number {k + 1} of the synthetic report", fontsize=10)
                pg.insert_text((520, 100 + 14 * k), str(3 + 2 * k), fontsize=10)
        else:
            _abstract(pg)
            pg.insert_textbox((60, 160, 540, 300), PROSE * 2, fontsize=10)
    doc, _ = _doc(draw, pages=2)
    _no_table(doc)


# ---- the pieces --------------------------------------------------------------------------------------------------

def test_cell_classification():
    for t in ("80.1", "19.9 ± 0.4", "12.4M", "3.5 h", "68.0a", "80.6/80.1", "6.0 × 10−4", "1,024", "45%"):
        assert _numeric_cell(t), t
    for t in ("Baseline", "GPT-3", "(8)", "(12a)", "-", "Top systems", "ResNet-50 v2"):
        assert not _numeric_cell(t), t
    assert _prose_cell("The detector records every event that passes the trigger")
    assert not _prose_cell("No pretraining") and not _prose_cell("12 15 18 21 24 27 30 33")


def test_open_tables_returns_the_untouched_lines_when_there_is_no_table():
    pdf = pymupdf.open()
    pg = pdf.new_page()
    pg.insert_textbox((60, 80, 540, 300), PROSE * 4, fontsize=10)
    lines = _page_lines(pg)
    found, rest, unlabelled = _open_tables(lines, pg.rect.width)
    assert found == [] and rest is lines and unlabelled is False


def test_no_claim_is_made_of_table_text():
    def draw(pg, n):
        _abstract(pg)
        pg.insert_textbox((60, 160, 540, 200), PROSE, fontsize=10)
        end = _table(pg, 60, 210, [["System", "Accuracy", "Gain"], ["Ours improves", "85.2", "5.1"], ["We achieve", "86.0", "5.9"],
                                   ["Baseline outperforms", "80.1", "0.0"]])
        pg.insert_textbox((60, end + 12, 540, end + 60), PROSE, fontsize=10)
    doc, _ = _doc(draw)
    assert all("85.2 5.1" not in c.text and not c.text.startswith("Ours improves") for c in extract_claims(doc))
    assert len(_kinds(doc, "table")) == 3


def test_wrapped_citation_list_made_of_numbers_stays_in_its_sentence():
    """A line that holds only reference numbers ("35, 37-43, 46, 47,") continues a sentence; it is not a row of values."""
    def draw(pg, n):
        _abstract(pg)
        pg.insert_text((60, 170), "Thirty-eight synthetic studies reported a higher prevalence in the first group [27, 29, 32,", fontsize=10)
        pg.insert_text((60, 183), "35, 37, 43, 46, 47, 50, 56, 60, 63, 65, 71, 73, 84, 86, 91, 98, 102, 106, 111, 113, 116, 118,", fontsize=10)
        pg.insert_text((60, 196), "121, 122] with the pattern reversed in thirteen of the remaining studies.", fontsize=10)
    doc, _ = _doc(draw)
    _no_table(doc)
    s = [s for s in doc.sentences if s.text.startswith("Thirty-eight synthetic studies")]
    assert len(s) == 1 and "35, 37, 43" in s[0].text and s[0].text.endswith("remaining studies.")
