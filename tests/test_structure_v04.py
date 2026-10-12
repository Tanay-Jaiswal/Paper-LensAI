"""Regression and negative tests for abstract and section detection (0.4.0-dev).

Every PDF is drawn here with PyMuPDF from made-up text; no real paper and no held-out file is involved.
Each test names the failure it pins (first seen on a development paper, see docs/EVALUATION.md section 10).
"""
import pymupdf

from paperlens.ingest import (NO_ABSTRACT, NO_ABSTRACT_HEADING, _build, _seq_ok, canonical_section, keyword_section)

PROSE = ("The detector records every event that passes the trigger selection and each run is calibrated against a "
         "reference source before the analysis begins. ")
BODY = PROSE * 3


def _pdf(draw, pages=1):
    pdf = pymupdf.open()
    for n in range(pages):
        draw(pdf.new_page(), n)
    return _build(pdf, "t", "synthetic.pdf")


def _h(page, y, text, size=12, x=60):
    page.insert_text((x, y), text, fontsize=size, fontname="hebo")


def _p(page, y0, y1, text, size=10, x=60):
    page.insert_textbox((x, y0, 540, y1), text, fontsize=size)


def _sec(doc, needle):
    hits = [s for s in doc.sentences if needle in s.text]
    assert hits, needle
    return hits[0].section


# ---- abstracts ---------------------------------------------------------------------------------------------------

def test_labelled_abstract_ends_before_introduction():
    def draw(pg, n):
        _h(pg, 60, "A Synthetic Study of Abstracts", 17)
        _h(pg, 110, "Abstract")
        _p(pg, 120, 200, "We measure a synthetic quantity and report an improvement of 4.2 points. " + PROSE)
        _h(pg, 240, "1 Introduction")
        _p(pg, 250, 330, "The introduction sentence says something entirely different about the topic. " + PROSE)
    doc = _pdf(draw)
    assert _sec(doc, "improvement of 4.2") == "abstract"
    assert _sec(doc, "introduction sentence") == "introduction"
    assert not any("abstract" in w.lower() for w in doc.warnings)


def test_headless_abstract_skips_title_authors_and_dates():
    """LIGO-like front page: no 'Abstract' heading. Only the prose paragraph is the abstract."""
    def draw(pg, n):
        _h(pg, 60, "Observation of Synthetic Waves from a Made-up Merger", 14, x=80)
        pg.insert_text((200, 85), "A. Author et al.*", fontsize=10)
        pg.insert_text((150, 100), "(Made-up Collaboration and Other Collaboration)", fontsize=10)
        pg.insert_text((170, 112), "(Received 21 January 2016; published 11 February 2016)", fontsize=9)
        _p(pg, 125, 230, "On a made-up day the two synthetic detectors observed a transient signal with a peak strain. "
                          + PROSE + "The source lies at a made-up distance and the signal is highly significant. ", size=9.5, x=100)
        pg.insert_text((100, 250), "DOI: 10.0000/Synthetic.116.061102", fontsize=8)
        _h(pg, 290, "I. INTRODUCTION", 10.5)
        _p(pg, 300, 380, PROSE * 2)
    doc = _pdf(draw)
    ab = " ".join(s.text for s in doc.sentences if s.section == "abstract")
    assert "transient signal" in ab
    for junk in ("Received 21 January", "Collaboration", "A. Author", "DOI"):
        assert junk not in ab, junk
    assert NO_ABSTRACT_HEADING in doc.warnings


def test_no_abstract_is_reported_not_guessed():
    """Only author lines and affiliations before the introduction: nothing may be labelled abstract."""
    def draw(pg, n):
        _h(pg, 60, "A Title Without Any Abstract", 17)
        pg.insert_text((60, 90), "Jane Author, Joe Writer", fontsize=10)
        pg.insert_text((60, 102), "Department of Made-up Studies, Imaginary University, jane@example.org", fontsize=10)
        _h(pg, 150, "1 Introduction")
        _p(pg, 160, 260, BODY)
    doc = _pdf(draw)
    assert not [s for s in doc.sentences if s.section == "abstract"]
    assert NO_ABSTRACT in doc.warnings


def test_run_in_abstract_heading_and_keywords_line():
    def draw(pg, n):
        _h(pg, 60, "A Title With A Run-in Abstract", 17)
        _p(pg, 100, 160, "Abstract. We propose a synthetic method that reaches 91.2% accuracy on a made-up benchmark. " + PROSE)
        pg.insert_text((60, 180), "Keywords: synthetic, abstract, test", fontsize=10)
        _h(pg, 220, "1 Introduction")
        _p(pg, 230, 300, PROSE * 2)
    doc = _pdf(draw)
    assert _sec(doc, "91.2% accuracy") == "abstract"
    assert not any(s.section == "abstract" and "Keywords" in s.text for s in doc.sentences)
    assert "Abstract." not in " ".join(s.text for s in doc.sentences)


def test_footnote_and_venue_lines_do_not_extend_the_abstract():
    def draw(pg, n):
        _h(pg, 60, "A Title With Footnotes", 17)
        _h(pg, 110, "Abstract")
        _p(pg, 120, 190, "We show a synthetic result of 12 percent on a made-up task. " + PROSE)
        pg.insert_textbox((60, 690, 540, 710), "*Equal contribution. Listing order is random.", fontsize=8)
        pg.insert_textbox((60, 735, 540, 755), "31st Synthetic Conference (SC 2099), Nowhere, Land.", fontsize=8)
        pg.insert_text((60, 300), "1 Introduction", fontsize=12, fontname="hebo")
    doc = _pdf(draw)
    ab = [s.text for s in doc.sentences if s.section == "abstract"]
    assert ab and not any("Conference" in t or "Equal" in t for t in ab)


def test_summary_heading_late_in_paper_is_not_a_second_abstract():
    """'Summary and Conclusions' on page 11 of a PLOS-style paper became 13 abstract sentences."""
    def draw(pg, n):
        if n == 0:
            _h(pg, 60, "Abstract")
            _p(pg, 70, 150, "We study a synthetic effect of 3.5 percent. " + PROSE)
            _h(pg, 200, "Introduction")
            _p(pg, 210, 300, PROSE * 2)
        elif n == 3:
            _h(pg, 80, "Summary and Conclusions")
            _p(pg, 90, 170, "In summary the made-up effect is small. " + PROSE)
    doc = _pdf(draw, pages=4)
    assert _sec(doc, "In summary") == "conclusion"
    assert sum(s.section == "abstract" for s in doc.sentences) <= 3


def test_overlong_abstract_warns():
    def draw(pg, n):
        _h(pg, 60, "Abstract")
        for k in range(8):
            _p(pg, 70 + 90 * k, 150 + 90 * k, ("Sentence group %d of a very long abstract. " % k) + PROSE)
    doc = _pdf(draw)
    long = sum(s.section == "abstract" for s in doc.sentences) > 30
    assert long == any("unusually long" in w for w in doc.warnings)


# ---- numbered, split and unusual headings ------------------------------------------------------------------------

def test_numbered_headings_and_subsections_map_to_sections():
    def draw(pg, n):
        _h(pg, 60, "1 Introduction"); _p(pg, 70, 130, "Intro text here for the synthetic paper. " + PROSE)
        _h(pg, 150, "3 Experimental Setup"); _p(pg, 160, 220, "Setup text here for the synthetic paper. " + PROSE)
        _h(pg, 240, "3.1 Datasets and Metrics", 10); _p(pg, 250, 310, "Dataset text here for the synthetic paper. " + PROSE)
        _h(pg, 330, "4 User Evaluation"); _p(pg, 340, 400, "User study text here for the synthetic paper. " + PROSE)
        _h(pg, 420, "5 Summary and Conclusions"); _p(pg, 430, 490, "Closing text here for the synthetic paper. " + PROSE)
    doc = _pdf(draw)
    assert _sec(doc, "Setup text") == "experiments"
    assert _sec(doc, "Dataset text") == "experiments"
    assert _sec(doc, "User study text") == "experiments"      # custom name, standard word
    assert _sec(doc, "Closing text") == "conclusion"


def test_heading_wrapped_over_two_lines_is_one_heading():
    def draw(pg, n):
        _h(pg, 60, "1 Introduction"); _p(pg, 70, 130, PROSE)
        _h(pg, 160, "Claimed Research Findings May Often Be Simply Accurate", 10, x=60)
        _h(pg, 172, "Measures of the Prevailing Bias", 10, x=60)
        _p(pg, 182, 260, "Body after the wrapped heading begins here. " + PROSE)
    doc = _pdf(draw)
    s = [s for s in doc.sentences if "Body after" in s.text][0]
    assert s.heading == "Claimed Research Findings May Often Be Simply Accurate Measures of the Prevailing Bias"
    assert "Measures of the Prevailing Bias" not in " ".join(x.text for x in doc.sentences)


def test_appendix_letters_become_appendix_after_references():
    def draw(pg, n):
        if n == 0:
            _h(pg, 60, "1 Introduction"); _p(pg, 70, 130, PROSE)
            _h(pg, 160, "6 Conclusion"); _p(pg, 170, 230, "Closing words of the paper. " + PROSE)
            _h(pg, 260, "References")
            _p(pg, 270, 330, "[1] A. Author, Journal of Synthetic Results 12, 345 (1999).\n[2] B. Writer, Annals 7, 89 (2001).")
        else:
            _h(pg, 70, "A Model implementation details")
            _h(pg, 100, "A.1 Parameters for the final system", 10.9)
            _p(pg, 112, 180, "The synthetic appendix lists the parameters used in every run. " + PROSE)
            _h(pg, 200, "B Statistical analysis")
            _p(pg, 212, 280, "The synthetic appendix describes the statistics in detail. " + PROSE)
    doc = _pdf(draw, pages=2)
    assert _sec(doc, "lists the parameters") == "appendix"
    assert _sec(doc, "describes the statistics") == "appendix"
    assert _sec(doc, "Journal of Synthetic") == "references"


def test_appendix_letter_split_from_title_on_one_baseline():
    def draw(pg, n):
        _h(pg, 60, "6 Conclusion"); _p(pg, 70, 130, PROSE)
        _h(pg, 160, "A", 12, x=72); _h(pg, 160, "Details of Filtering", 12, x=94)
        _p(pg, 172, 240, "Filtering details sentence appears in the appendix. " + PROSE)
    doc = _pdf(draw)
    s = [s for s in doc.sentences if "Filtering details" in s.text][0]
    assert s.section == "appendix" and s.heading == "A Details of Filtering"


# ---- negatives: things that must not become headings or evidence structure ----------------------------------------

def test_bold_lead_sentence_and_paragraph_are_not_headings():
    def draw(pg, n):
        _h(pg, 60, "1 Introduction"); _p(pg, 70, 130, PROSE)
        _h(pg, 160, "We find that the synthetic effect is large and robust across every setting we tried.", 10)
        _p(pg, 172, 240, "Following text of the same paragraph continues here. " + PROSE)
    doc = _pdf(draw)
    s = [s for s in doc.sentences if "Following text" in s.text][0]
    assert s.heading == "1 Introduction" and s.section == "introduction"


def test_table_header_cells_and_captions_are_not_headings():
    def draw(pg, n):
        _h(pg, 60, "4 Results"); _p(pg, 70, 130, PROSE)
        _h(pg, 160, "Method", 10, x=60); _h(pg, 160, "Accuracy", 10, x=300)
        _h(pg, 190, "Table 3: Results of the synthetic model on the made-up test set.", 10)
        _p(pg, 202, 270, "After the table the results discussion continues with new text. " + PROSE)
    doc = _pdf(draw)
    heads = {s.heading for s in doc.sentences}
    assert heads <= {"4 Results"}, heads


def test_contents_page_is_not_read_as_structure():
    def draw(pg, n):
        if n == 0:
            _h(pg, 60, "Contents", 12)
            for k, (t, p) in enumerate([("1 Introduction", 3), ("2 Approach", 6), ("3 Results", 10), ("4 Limitations", 33),
                                        ("5 Broader Impacts", 34), ("6 Conclusion", 40), ("References", 41)]):
                pg.insert_text((60, 90 + 16 * k), t + " " + ". " * 20, fontsize=10)
                pg.insert_text((530, 90 + 16 * k), str(p), fontsize=10)
        else:
            _h(pg, 60, "1 Introduction"); _p(pg, 70, 130, "Real introduction text of the synthetic paper. " + PROSE)
            _h(pg, 160, "2 Approach"); _p(pg, 170, 230, "Real approach text of the synthetic paper. " + PROSE)
    doc = _pdf(draw, pages=2)
    assert _sec(doc, "Real introduction") == "introduction" and _sec(doc, "Real approach") == "method"
    assert not any(s.section == "limitations" for s in doc.sentences)


def test_running_header_on_alternating_pages_is_dropped():
    def draw(pg, n):
        pg.insert_text((60, 30), "A. Author and B. Writer" if n % 2 else "Synthetic Running Title", fontsize=9)
        _h(pg, 70, "%d Section Number %d" % (n + 1, n + 1)); _p(pg, 80, 150, "Body of page %d goes here. " % n + PROSE)
    doc = _pdf(draw, pages=6)
    assert not any("Running Title" in s.text or "A. Author and B. Writer" in s.text for s in doc.sentences)


def test_italic_numbered_heading_needs_sequence():
    """Numbered body-size italic lines are headings only when the number continues the sequence."""
    assert _seq_ok([4], ["4", "1"]) and _seq_ok([4, 1], ["4", "2"]) and _seq_ok([4, 2], ["5"])
    assert not _seq_ok([4, 1], ["9", "9"]) and not _seq_ok(None, ["7"])


def test_vocabulary_helpers():
    assert canonical_section("Summary and Conclusions") is None                # never the abstract ...
    assert keyword_section("Summary and Conclusions") == "conclusion"          # ... its last word names the section
    assert canonical_section("A B S T R A C T") == "abstract"
    assert canonical_section("Summary") == "abstract"
    assert keyword_section("4 User Evaluation") == "experiments"
    assert keyword_section("Our Awesome Idea") is None
    assert keyword_section("The results of our long and elaborate walk through the data") is None   # too long
