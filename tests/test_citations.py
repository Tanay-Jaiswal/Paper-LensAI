from paperlens.citations import check_citations, _expand, _numbered_entries
from paperlens.models import Document, Sentence
from paperlens.revisions import revision_checklist


def _doc(body: list[str], refs: list[str], name="paper.pdf") -> Document:
    sents, i = [], 0
    for t in body:
        sents.append(Sentence(i, t, 1, "introduction"))
        i += 1
    for t in refs:
        sents.append(Sentence(i, t, 9, "references", "References"))
        i += 1
    return Document("d", "T", 9, sents, source_name=name)


def _kinds(res):
    return sorted((f["kind"], f["message"]) for f in res["findings"])


NUM_REFS = [f"[{n}] A. Author{n} and B. Writer. Title number {n} about things. In Proc. Venue, 20{10 + n}." for n in range(1, 7)]


def test_expand_ranges_and_lists():
    assert _expand("1, 3-5") == [1, 3, 4, 5]
    assert _expand("2–4") == [2, 3, 4]
    assert _expand("7;9") == [7, 9]
    assert _expand("5-2") == []                       # backwards range is not a citation


def test_numbered_list_is_segmented_in_order():
    style, entries = _numbered_entries(" ".join(NUM_REFS))
    assert style == "bracket" and [e["n"] for e in entries] == [1, 2, 3, 4, 5, 6]
    assert entries[2]["text"].startswith("A. Author3")


def test_numbered_clean_paper_has_no_findings():
    body = ["Prior work [1, 2] studied this.", "We follow [3]-[5] closely.", "See also [6]."]
    res = check_citations(_doc(body, NUM_REFS))
    assert res["style"] == "numbered" and res["checked"] and res["findings"] == []
    assert res["n_entries"] == 6 and res["profile"]["with_year"] == 6


def test_numbered_cited_not_listed_and_listed_not_cited():
    body = ["Prior work [1, 2] studied this.", "We follow [3] and [7].", "Results in [4]."]
    res = check_citations(_doc(body, NUM_REFS))
    assert _kinds(res) == [
        ("cited_not_listed", "Reference [7] is cited in the text but the list has only 6 numbered entries."),
        ("listed_not_cited", "Entry [5] in the reference list is never cited as [5] in the text."),
        ("listed_not_cited", "Entry [6] in the reference list is never cited as [6] in the text."),
    ]


def test_intervals_and_image_sizes_are_not_citations():
    body = ["Images are resized to [256, 480] pixels.", "Values lie in [0, 1].", "See [1]-[6]."]
    res = check_citations(_doc(body, NUM_REFS))
    assert res["findings"] == []


def test_list_read_short_is_not_reported_as_missing_references():
    body = [f"Claim {n} [{n}]." for n in range(1, 15)]
    res = check_citations(_doc(body, NUM_REFS))
    assert not res["checked"] and res["findings"] == [] and "not read completely" in res["note"]


def test_superscript_style_is_not_checked():
    res = check_citations(_doc(["No bracketed citations here.", "Only words."], NUM_REFS))
    assert not res["checked"] and "superscript" in res["note"]


AY_REFS = ["Ann Smith, Bob Jones, and Carl Brown.", "2019.", "A study of things.", "In Proceedings of ACL.",
           "Dana White.", "2020a.", "Another study.", "Journal of Studies, 3(2):1-9.",
           "Lee, K. and Park, J. (2018).", "Deep things.", "In NeurIPS.",
           "Golub, G. and Van Loan, C. (2013).", "Matrix computations.", "Johns Hopkins University Press.",
           "Erin Black and Fay Green.", "2017.", "Old study.", "In EMNLP.",
           "Gus Grey.", "2021.", "Never cited study.", "arXiv preprint arXiv:2101.00001."]


def test_author_year_matching():
    body = ["Earlier work (Smith et al., 2019; White, 2020a) found this.",
            "Lee and Park (2018) disagree.", "We use the SVD (Golub and Van Loan, 2013, pp. 4).",
            "Black and Green (2017) also tried.", "A missing one (Nobody et al., 2015) is cited here."]
    res = check_citations(_doc(body, AY_REFS))
    assert res["style"] == "author-year" and res["checked"] and res["n_entries"] == 6
    assert _kinds(res) == [
        ("cited_not_listed", "\"Nobody et al., 2015\" is cited in the text but no entry by Nobody from 2015 was found "
                             "in the reference list."),
        ("listed_not_cited", "The entry by Grey (2021) is never cited in the text as \"Grey ... 2021\"."),
    ]
    assert res["profile"]["preprints"] == 1


def test_raw_reference_text_rescues_an_entry_the_parser_dropped():
    body = ["Earlier work (Smith et al., 2019; White, 2020a) found this.", "Lee and Park (2018) disagree.",
            "Black and Green (2017) and (Golub and Van Loan, 2013) and Grey (2021).", "Cloze (Taylor, 1953)."]
    assert any(f["kind"] == "cited_not_listed" for f in check_citations(_doc(body, AY_REFS))["findings"])
    res = check_citations(_doc(body, AY_REFS), raw_refs="... Wilson L Taylor. 1953. Cloze procedure. ...")
    assert not any(f["kind"] == "cited_not_listed" for f in res["findings"])


def test_duplicates_need_same_opening_and_identifier():
    refs = NUM_REFS[:4] + [
        "[5] Ming Wen and Jun Chen. 2018. Context-aware patch generation. In ICSE 2018, ACM. doi:10.1145/3180155.3180233",
        "[6] Ming Wen and Jun Chen. 2018. Context-aware patch generation. In Proc. ICSE (ICSE 18). doi:10.1145/3180155.3180233",
        "[7] Group, Handbook of cross sections: 1. Inclusive. CERN-2011-002 (2011), arXiv:1101.0593.",
        "[8] Group, Handbook of cross sections: 2. Differential. CERN-2012-002 (2012), arXiv:1201.3084."]
    res = check_citations(_doc(["See [1]-[8]."], refs))
    assert [f["kind"] for f in res["findings"]] == ["duplicate_entry"]
    assert res["findings"][0]["quote"].startswith("Ming Wen")


def test_entries_without_year_skip_arxiv_ids():
    refs = NUM_REFS[:5] + ["[6] A. Tool. Software on GitHub. https://github.com/x/y",
                           "[7] B. Paper. Some title. arXiv:1207.7214 [hep-ex]."]
    res = check_citations(_doc(["See [1]-[7]."], refs))
    assert [f["kind"] for f in res["findings"]] == ["entry_without_year"]
    assert "GitHub" in res["findings"][0]["quote"]


def test_no_reference_list():
    res = check_citations(_doc(["Some text [1]."], []))
    assert res["style"] == "none" and not res["checked"] and "No reference list" in res["note"]


def test_findings_become_low_or_medium_revisions(make_pdf):
    from paperlens.pipeline import analyze_pdf
    a = analyze_pdf(make_pdf(1)[0])
    a.citations = check_citations(_doc(["We follow [3] and [7].", "Prior work [1, 2].", "Results in [4]."], NUM_REFS))
    refs = [x for x in revision_checklist(a) if x["category"] == "References"]
    assert [x["priority"] for x in refs] == ["medium", "low", "low"]
    assert refs[0]["action"].startswith("Add the missing entry") and refs[0]["source"] == "Reference check C1"
