"""Figure text must not enter prose sentences (0.5.1-dev). Reproduces two failures first seen on development papers
(a diagram's labels glued to its caption; a figure caption in the middle of a sentence that runs from one column to the next)
with small synthetic PDFs. No real text is used."""
import pymupdf

from paperlens.claims import extract_claims
from paperlens.ingest import _build, _figure_boxes

PROSE = ("The detector records every event that passes the trigger selection and each run is calibrated against a "
         "reference source before the analysis begins. ")


def _doc(draw, pages=1):
    pdf = pymupdf.open()
    for k in range(pages):
        draw(pdf.new_page(), k)
    return _build(pdf, "t", "synthetic.pdf"), pdf


def _diagram(pg, x0, y0, labels):
    """A box-and-arrow diagram: five boxes with a label in each, joined by lines."""
    for i, label in enumerate(labels):
        r = pymupdf.Rect(x0 + 20, y0 + 12 + 34 * i, x0 + 190, y0 + 38 + 34 * i)
        pg.draw_rect(r, color=(0, 0, 0), width=0.8)
        pg.insert_text((r.x0 + 6, r.y0 + 17), label, fontsize=7.5)
        if i:
            pg.draw_line((x0 + 105, y0 + 12 + 34 * i - 8), (x0 + 105, y0 + 12 + 34 * i), color=(0, 0, 0), width=0.8)


def test_diagram_labels_are_not_glued_into_the_caption_or_the_claim():
    labels = ["Decision: SUPPORTS", "Fact-checker reads the abstract", "Corpus of cited abstracts",
              "More severe infection raises troponin (SMD 0.53, p < 0.001)", "Rationale sentences"]

    def draw(pg, n):
        pg.insert_text((60, 70), "Abstract", fontsize=12, fontname="hebo")
        pg.insert_textbox((60, 80, 540, 150), "We improve accuracy from 80.1% to 85.2% on a synthetic benchmark. " + PROSE, fontsize=10)
        _diagram(pg, 150, 170, labels)
        pg.insert_textbox((150, 360, 450, 390), "Figure 1: A synthetic claim supported by evidence found by the system.", fontsize=8.5)
        pg.insert_textbox((60, 400, 540, 470), "The next paragraph states a result of 12 percent in plain words. " + PROSE, fontsize=10)
    doc, pdf = _doc(draw)
    assert _figure_boxes(pdf[0])
    prose = [s for s in doc.sentences if s.kind in ("text", "caption")]
    assert not any("Corpus of cited" in s.text or "Decision: SUPPORTS" in s.text or "troponin" in s.text for s in prose)
    assert [s for s in doc.sentences if s.kind == "caption"][0].text.startswith("Figure 1: A synthetic claim")
    assert "Corpus of cited abstracts" in " ".join(s.text for s in doc.sentences if s.kind == "meta")   # kept, not claim or evidence
    assert any("12 percent in plain words" in s.text for s in prose)                                      # text near the figure survives
    assert all("troponin" not in c.text for c in extract_claims(doc))


def test_caption_between_two_columns_does_not_break_or_join_the_sentence():
    def draw(pg, n):
        pg.insert_text((56, 70), "Abstract", fontsize=11, fontname="hebo")
        pg.insert_textbox((56, 80, 556, 120), "We report a synthetic result of 7 percent on a made-up task. " + PROSE, fontsize=9)
        pg.insert_textbox((56, 140, 294, 400), PROSE * 4 + "The excess is driven", fontsize=9)
        pg.insert_textbox((318, 140, 556, 175), "Figure 12: Likelihood contours for a synthetic channel including the branching ratio.", fontsize=8)
        pg.insert_textbox((318, 192, 556, 400), "by the two channels with the highest mass resolution, and the equally sensitive third channel. " + PROSE * 3, fontsize=9)
    doc, _ = _doc(draw)
    whole = [s for s in doc.sentences if s.text.startswith("The excess is driven")]
    assert len(whole) == 1 and whole[0].text.startswith("The excess is driven by the two channels")
    assert "Figure 12" not in whole[0].text
    cap = [s for s in doc.sentences if s.text.startswith("Figure 12")]
    assert cap and cap[0].kind == "caption" and "by the two channels" not in cap[0].text


def test_caption_that_follows_a_finished_sentence_is_untouched():
    def draw(pg, n):
        pg.insert_text((60, 70), "Abstract", fontsize=12, fontname="hebo")
        pg.insert_textbox((60, 80, 540, 150), "We study a synthetic effect of 3 percent. " + PROSE, fontsize=10)
        pg.insert_textbox((60, 160, 540, 190), "Figure 2: A caption that follows a finished sentence in the same column.", fontsize=9)
        pg.insert_textbox((60, 200, 540, 260), "Text after the caption stays a separate paragraph of its own. " + PROSE, fontsize=10)
    doc, _ = _doc(draw)
    assert [s.text for s in doc.sentences if s.kind == "caption"] == ["Figure 2: A caption that follows a finished sentence in the same column."]
    assert any(s.text.startswith("Text after the caption") for s in doc.sentences)


# ---- negatives: what is not a figure -------------------------------------------------------------------------------

def test_ruled_table_header_rules_and_backgrounds_are_not_figures():
    def draw(pg, n):
        pg.draw_rect(pymupdf.Rect(0, 0, 612, 792), fill=(0.98, 0.98, 0.98), color=None)      # page background
        pg.draw_line((56, 62), (556, 62), width=0.5)                                          # header rule
        for y in (100, 112, 124, 136, 148, 160):                                              # booktabs: only horizontal rules
            pg.draw_line((100, y), (400, y), width=0.4)
        pg.insert_textbox((60, 170, 540, 260), "The synthetic result of 12 percent was observed in every condition. " + PROSE * 2, fontsize=10)
        pg.insert_text((110, 109), "Model    Accuracy    Error", fontsize=8)
    doc, pdf = _doc(draw)
    assert _figure_boxes(pdf[0]) == []
    assert any("12 percent was observed" in s.text and s.kind == "text" for s in doc.sentences)


def test_prose_near_but_outside_a_figure_is_prose():
    def draw(pg, n):
        _diagram(pg, 150, 100, ["a", "b", "c", "d", "e"])
        pg.insert_textbox((60, 300, 540, 380), "A statement of 41.8 points directly under the figure remains a sentence. " + PROSE, fontsize=10)
    doc, pdf = _doc(draw)
    s = [s for s in doc.sentences if "41.8 points" in s.text]
    assert s and s[0].kind == "text"


def test_a_wrapped_table_reference_is_not_taken_for_a_caption():
    """"... as shown in" / "Table 1." wraps onto its own line; it continues the sentence (found by the table benchmark layout)."""
    def draw(pg, n):
        pg.insert_text((60, 70), "Abstract", fontsize=12, fontname="hebo")
        pg.insert_text((60, 90), "On the synthetic benchmark the method improves accuracy from 80.1% to 85.2%, as shown in", fontsize=10)
        pg.insert_text((60, 102), "Table 1. The next sentence is ordinary text of the same paragraph written here.", fontsize=10)
    doc, _ = _doc(draw)
    s = [s for s in doc.sentences if s.text.startswith("On the synthetic benchmark")]
    assert len(s) == 1 and s[0].text.endswith("Table 1.") and s[0].kind == "text"
