"""Glossary: the paper's own abbreviation definitions, and their use when matching claims to evidence."""
from paperlens.claims import rank_passages
from paperlens.glossary import CURRENT, build_glossary, expand_tokens, token_map
from paperlens.models import Document, Sentence
from paperlens.textutils import tokenize


def doc(*texts, section="method"):
    return Document("t", "T", 1, [Sentence(i, t, i + 1, section) for i, t in enumerate(texts)])


def test_both_definition_forms_are_found_with_page():
    g = build_glossary(doc("Stresses were computed with the finite element method (FEM) on a fine mesh.",
                           "Flow was solved with CFD (computational fluid dynamics) in OpenFOAM.",
                           "The FEM and CFD results agree within 3%."))
    by = {d["abbr"]: d for d in g["defined"]}
    assert by["FEM"]["long"] == "finite element method" and by["FEM"]["page"] == 1
    assert by["CFD"]["long"] == "computational fluid dynamics" and by["CFD"]["page"] == 2
    assert by["FEM"]["uses"] >= 2


def test_letters_must_match_and_figure_refs_are_not_abbreviations():
    g = build_glossary(doc("We used a coarse grid (FEM) here.", "Results are shown below (Fig. 3) and in (Table 2)."))
    assert not g["defined"]


def test_undefined_abbreviations_are_listed_not_guessed():
    g = build_glossary(doc("The HAZ was hardened.", "Cracks started in the HAZ near the weld."))
    assert [u["abbr"] for u in g["undefined"]] == ["HAZ"] and not g["defined"]
    assert "cannot be expanded" in g["note"]


def test_reference_list_initials_are_ignored():
    g = build_glossary(doc("Smith JP, Lee SJ. Paper one.", "Smith JP. Paper two.", section="references"))
    assert not g["undefined"]


def test_expansion_lets_abbreviation_match_long_form():
    tm = token_map({"defined": [{"abbr": "FEM", "long": "finite element method"}]})
    assert set(tokenize("finite element method")) <= set(expand_tokens(tokenize("FEM predicts"), tm))
    assert "fem" in expand_tokens(tokenize("the finite element method predicts"), tm)


def test_claim_with_abbreviation_ranks_long_form_passage_first():
    pool = [Sentence(0, "The finite element method predicted a peak stress of 212 MPa at the fillet.", 5, "results"),
            Sentence(1, "Specimens were polished and photographed before loading in the rig.", 5, "results")]
    claim = "FEM predicts the peak stress at the fillet."
    token = CURRENT.set(token_map({"defined": [{"abbr": "FEM", "long": "finite element method"}]}))
    try:
        with_g = rank_passages(claim, [], pool)
    finally:
        CURRENT.reset(token)
    without = rank_passages(claim, [], pool)
    assert with_g[0][3].id == 0
    assert with_g[0][1] > without[0][1]       # higher lexical score once FEM is read as finite element method
