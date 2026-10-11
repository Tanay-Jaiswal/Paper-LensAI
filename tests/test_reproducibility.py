from conftest import ALL, NONE
from paperlens.ingest import parse_pdf
from paperlens.reproducibility import RUBRIC, assess


def test_full_paper_scores_high_and_empty_scores_low(make_pdf):
    hi = assess(parse_pdf(make_pdf(1, ALL)[0]))
    lo = assess(parse_pdf(make_pdf(1, NONE)[0]))
    assert hi["score"] > 85 and lo["score"] < 45
    assert hi["score"] > lo["score"] + 40


def test_every_present_item_cites_a_page_and_quote(make_pdf):
    r = assess(parse_pdf(make_pdf(2, ALL)[0]))
    for it in r["items"]:
        if it["status"] == "present":
            assert it["evidence"] and it["evidence"][0]["page"] >= 1 and it["evidence"][0]["quote"]


def test_score_matches_documented_formula(make_pdf):
    r = assess(parse_pdf(make_pdf(3)[0]))
    w = sum(i["weight"] for i in r["items"])
    e = sum(i["weight"] * i["credit"] for i in r["items"])
    assert abs(r["score"] - 100 * e / w) < 0.06


def test_related_work_statements_do_not_count_as_own_code():
    from paperlens.models import Document, Sentence
    d = Document("x", "t", 1, [Sentence(0, "Smith et al. released their code at https://github.com/smith/x.", 1, "related")])
    items = {i["key"]: i for i in assess(d)["items"]}
    assert items["code"]["status"] in ("present", "partial", "missing")  # code links anywhere count; others must not
    assert items["hyper"]["status"] == "missing"


def test_rubric_keys_unique():
    keys = [r["key"] for r in RUBRIC]
    assert len(keys) == len(set(keys))
