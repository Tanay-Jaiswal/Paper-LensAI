"""Regression tests for failures first seen on the real papers in data/Papers (docs/EVALUATION.md section 3).

Every input here is a SMALL SYNTHETIC edge case built in the test (hand-made span dicts or a one-page PDF drawn with
PyMuPDF). None of it is text from a real paper; the real PDFs are not needed to run these tests.
"""
import pymupdf

from paperlens.claims import _claim_score, _eligible_evidence, extract_claims
from paperlens.ingest import (_build, _clean, _is_numbered_heading, _line_text, _margin_lines, _next_section,
                              _title, canonical_section)
from paperlens.models import Claim, Document, Sentence
from paperlens.reproducibility import assess
from paperlens.textutils import UNMAPPED, numbers_in

BODY = ("The detector records every event that passes the trigger selection. "
        "Each run is calibrated against a reference source before analysis. ")


def _span(text, x0, x1, size=10.0):
    return {"text": text, "bbox": (x0, 100.0, x1, 110.0), "size": size, "flags": 0, "font": "Synthetic"}


def _pdf(draw) -> Document:
    pdf = pymupdf.open()
    draw(pdf.new_page())
    return _build(pdf, "t", "synthetic.pdf")


def _state(**kw):
    st = {"section": "front", "heading": "", "ref": False, "tops": {}, "top": (0.0, False, False),
          "sa_seen": set(), "abs_n": 0}
    st.update(kw)
    return st


# ---- (1) titles: rotated margin stamp, drop caps, short last line -------------------------------------------------

def test_rotated_margin_stamp_is_not_title_or_text():
    def draw(page):
        page.insert_text((60, 90), "A Synthetic Study of Margin Stamps", fontsize=17, fontname="hebo")
        page.insert_text((25, 600), "arXiv:0000.00000v1 [cs.XX] 1 Jan 2000", fontsize=20, rotate=90)
        page.insert_text((60, 140), "Abstract", fontsize=12, fontname="hebo")
        page.insert_textbox((60, 150, 540, 400), BODY * 3, fontsize=10)
    doc = _pdf(draw)
    assert doc.title == "A Synthetic Study of Margin Stamps"
    assert not any("arXiv" in s.text for s in doc.sentences)


def test_title_ignores_drop_cap_and_keeps_short_last_line():
    ln = lambda text, size, y: (text, size, True, y, 0, (50, y, 400, y + size))  # noqa: E731
    page = {"height": 800, "lines": [ln("Essay", 12, 40), ln("Why Synthetic Titles Wrap in", 25, 60),
                                     ln("Tests", 25, 90), ln("P", 42, 500), ln("body text of the page here", 9, 520)]}
    assert _title(page, "fallback.pdf") == "Why Synthetic Titles Wrap in Tests"


# ---- (2) lost word spaces ----------------------------------------------------------------------------------------

def test_line_text_restores_spaces_between_word_spans():
    # justified text: one span per word, no space character; a visible gap separates them
    assert _line_text([_span("It", 50, 58), _span("obtains", 61, 90), _span("new", 93, 110)]) == "It obtains new"
    # whitespace-only spans are kept, and no second space is added
    assert _line_text([_span("It", 50, 58), _span(" ", 58, 61), _span("obtains", 61, 90)]) == "It obtains"
    # a superscript that touches its base stays attached
    assert _line_text([_span("fb", 50, 60), _span("−1", 60.2, 68, size=7)]) == "fb−1"


# ---- (3) sections ------------------------------------------------------------------------------------------------

def test_numbered_subsection_inherits_parent_section():
    st = _state(section="method")
    assert _next_section(st, "4 Experiments", "experiments", 12, True, 3) == "experiments"
    st["section"] = "experiments"
    assert _next_section(st, "4.1 Machine Translation", None, 10, True, 3) == "experiments"
    # a sub-heading under a custom-named parent is not promoted by a loose prefix match
    assert _next_section(st, "5 Search Channels", None, 12, True, 4) == "other"
    assert canonical_section("5.5 Background modelling") == "background"
    assert _next_section(st, "5.5 Background modelling", "background", 10, True, 4) == "other"


def test_lighter_unnumbered_subheading_inherits_and_abstract_does_not():
    st = _state(section="introduction", top=(12, True, False))
    assert _next_section(st, "Results", "results", 12, True, 4) == "results"
    st["section"] = "results"
    assert _next_section(st, "Overall performance", None, 12, False, 5) == "results"   # same size, not bold
    assert _next_section(st, "Supporting Information", None, 12, True, 9) == "other"   # same weight: new section
    st2 = _state(section="abstract", top=(14.5, False, False), abs_n=6)
    assert _next_section(st2, "Author Summary", None, 12, False, 2) == "other"


def test_structured_abstract_labels_stay_in_abstract_until_repeated():
    st = _state(section="abstract", top=(16, False, False))
    for label in ("Objective", "Methods", "Results", "Conclusion"):
        assert _next_section(st, label, canonical_section(label), 11.5, True, 1) == "abstract"
    assert _next_section(st, "Introduction", "introduction", 12, True, 2) == "introduction"
    st["section"] = "introduction"
    assert _next_section(st, "Methods", "method", 12, True, 3) == "method"       # second time: the body section
    # an ordinary abstract followed by a body heading is not treated as structured
    st3 = _state(section="abstract", top=(12, True, False), abs_n=7)
    assert _next_section(st3, "Methods", "method", 12, True, 2) == "method"


def test_section_number_on_its_own_line_and_roman_numerals():
    def draw(page):
        page.insert_text((60, 80), "6", fontsize=12, fontname="hebo")
        page.insert_text((78, 80), "Results", fontsize=12, fontname="hebo")
        page.insert_textbox((60, 90, 540, 160), BODY, fontsize=10)
        page.insert_text((60, 190), "6.1", fontsize=10, fontname="hebo")
        page.insert_text((82, 190), "Synthetic Translation Task", fontsize=10, fontname="hebo")
        page.insert_textbox((60, 200, 540, 300), "The synthetic system reaches 41.8 points on the made-up task. " + BODY,
                            fontsize=10)
    doc = _pdf(draw)
    sub = [s for s in doc.sentences if "41.8" in s.text]
    assert sub and sub[0].section == "results" and sub[0].heading == "6.1 Synthetic Translation Task"
    assert _is_numbered_heading("II. OBSERVATION")
    assert not _is_numbered_heading("2003. Introduction to the shared task")     # a reference line, not a heading


def test_reference_list_without_heading_leaves_acknowledgments():
    def draw(page):
        page.insert_text((60, 80), "ACKNOWLEDGMENTS", fontsize=10, fontname="hebo")
        page.insert_textbox((60, 90, 540, 130), "The authors thank the synthetic funding agency for its support.", fontsize=10)
        page.insert_textbox((60, 140, 540, 220), "[1] A. Author and B. Writer, Journal of Synthetic Results 12, 345 (1999).\n"
                                                 "[2] C. Person, Annals of Made-up Physics 7, 89 (2001).", fontsize=10)
    doc = _pdf(draw)
    assert [s.section for s in doc.sentences if "Journal of Synthetic" in s.text] == ["references"]


# ---- (4) non-claims ----------------------------------------------------------------------------------------------

def test_number_rows_stamps_and_meta_are_not_claims():
    row = Sentence(0, "Oracle rationale 100.0 80.5 89.2 89.6 72.2 79.9 Zero-shot 42.5 45.1 43.8 36.1 38.4 37.2", 7, "abstract")
    stamp = Sentence(1, "arXiv:0000.00000v1 [cs.XX] 1 Jan 2000 improves results significantly", 1, "abstract", kind="meta")
    real = Sentence(2, "Our approach improves F1 on WNUT-17 from 78.6 to 83.2.", 1, "abstract")
    assert _claim_score(row)[0] == 0.0 and _claim_score(stamp)[0] == 0.0
    doc = Document("d", "t", 1, [row, stamp, real])
    assert [c.text for c in extract_claims(doc)] == [real.text]


def test_footnote_block_becomes_meta():
    def draw(page):
        page.insert_text((60, 80), "Abstract", fontsize=12, fontname="hebo")
        page.insert_textbox((60, 90, 540, 200), "We propose a synthetic method that improves accuracy by 3.5%. " + BODY,
                            fontsize=10)
        page.insert_textbox((60, 700, 540, 760), "*Equal contribution. The second author designed the novel model variants "
                                                 "and greatly improved the results.", fontsize=8)
    doc = _pdf(draw)
    note = [s for s in doc.sentences if "second author" in s.text]
    assert note and all(s.kind == "meta" for s in note)
    assert not any("second author" in c.text for c in extract_claims(doc))


# ---- (5) evidence ------------------------------------------------------------------------------------------------

def test_meta_sentences_and_fragments_are_not_evidence():
    sents = [Sentence(0, "The method improves accuracy to 91.2% on the benchmark.", 1, "abstract"),
             Sentence(1, "Accuracy on the benchmark reached 91.2% with the full model.", 5, "results"),
             Sentence(2, "PLoS ONE 11(7): e0000000. doi:10.1371/journal.pone.0000000 Editor: A. Person", 1, "results", kind="meta"),
             Sentence(3, "Table row: 10 µ", 5, "results", kind="table"),
             Sentence(4, "The custom-named section also reports 91.2% accuracy overall.", 6, "other")]
    claim = Claim("C1", 0, sents[0].text, 1, "abstract", "result", False, ["91.2"])
    assert [s.id for s in _eligible_evidence(Document("d", "t", 6, sents), claim)] == [1, 4]


def test_margin_sidebar_detected_but_text_column_is_not():
    def col(x0, x1, n, text):
        return [(text, 9.0, False, 100 + 12 * i, 0, (x0, 100 + 12 * i, x1, 110 + 12 * i)) for i in range(n)]
    sidebar = col(48, 190, 12, "Citation: sidebar text")
    main = col(200, 560, 40, "main column text " * 4)
    assert _margin_lines(sidebar + main, 612) == set(range(12))
    left, right = col(50, 295, 30, "left column text " * 3), col(310, 560, 40, "right column text " * 3)
    assert _margin_lines(left + right, 612) == set()                              # two-column page


# ---- (6) rubric --------------------------------------------------------------------------------------------------

def _doc(texts):
    return Document("d", "t", 1, [Sentence(i, t, 1, "results") for i, t in enumerate(texts)])


def test_model_only_items_not_applicable_without_training_vocabulary():
    obs_texts = ["The signal was observed in two detectors with a significance above 5 sigma.",
                 "The source lies at a distance of 410 megaparsecs.", "Data are publicly available from the observatory."]
    assert all(i["status"] != "not_applicable" for i in assess(_doc(obs_texts))["items"])   # too short to judge
    r = assess(_doc(obs_texts * 25))
    st = {i["key"]: i for i in r["items"]}
    assert st["hyper"]["status"] == st["splits"]["status"] == "not_applicable"
    assert r["not_applicable"] == ["splits", "hyper"]
    scored = [i for i in r["items"] if i["status"] != "not_applicable"]
    assert r["score"] == round(100 * sum(i["weight"] * i["credit"] for i in scored) / sum(i["weight"] for i in scored), 1)

    ml = _doc(["We train a neural network classifier on the training set.", "The learning rate is not stated here.",
               "We fine-tune the language model for three epochs."] + obs_texts * 25)
    assert all(i["status"] != "not_applicable" for i in assess(ml)["items"])


# ---- (7) corrupted decimals --------------------------------------------------------------------------------------

def test_unmapped_glyph_between_digits_is_marked_not_dropped():
    text, n = _clean("prevalence of 13\x014% (11\x017 to 15\x011%) with I2 = 99.9%")
    assert n == 3 and f"13{UNMAPPED}4%" in text and "134" not in text
    assert numbers_in(text) == ["99.9"]                       # 13?4 is never read as 134, 13 or 4
    assert numbers_in("a probability of 1.7×10−9 was found") == ["1.7"]
