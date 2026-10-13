"""The row-level table benchmark (eval/table_rows_bench.py): scorer logic on SYNTHETIC parser output, and the integrity
of the annotation file. No PDF is opened here, and no parser result is asserted: the benchmark measures, it is not a floor."""
import hashlib
import re
from pathlib import Path

from eval import table_rows_bench as B
from paperlens.models import Document, Sentence

ROOT = Path(__file__).resolve().parent.parent
TABLE = {"id": "S1", "label": "Synthetic", "paper": "synthetic.pdf", "page": 3, "tags": [],
         "header_rows": [["System", {"t": "Dev", "span": 2}], ["", "EM", "F1"]],
         "rows": [{"cells": ["Alpha (Single)", "81.2", "87.9"]},
                  {"cells": ["Beta", "-", "85.6"]},
                  {"cells": ["Gamma", "", "90.5"]},
                  {"cells": ["Delta", "70.0*", "71.0"]},
                  {"cells": ["Epsilon", "60.0", "61.0"]},
                  {"cells": ["Zeta", "50.0", "51.0"]},
                  {"cells": ["Eta", "40.0", "41.0"], "ambiguous": "synthetic ambiguous row"}]}


def _doc(*sents):
    return Document("d", "t", 5, [Sentence(i, text, page, "results", "", kind) for i, (text, kind, page) in enumerate(sents)])


def _score(*sents, mode=B.norm):
    return B.score_table(TABLE, _doc(*sents), mode)


def test_normalisation():
    assert B.norm("0.3± 0.1 −0.1") == B.norm("0.3 ±0.1 -0.1")
    assert B.norm("BERT Base") == "bertbase" and B.norm("ﬁne") == "fine"
    assert B.lenient("80 ± 7*") == B.lenient("80 ± 7") and B.norm("80 ± 7*") != B.norm("80 ± 7")
    assert B.lenient("t¯t") == B.lenient("tt¯") == "tt"


def test_outcomes_and_denominators():
    r = _score(("Table header: EM; F1", "meta", 3),
               ("Table row: Alpha (Single); EM: 81.2; F1: 87.9", "table", 3),          # exact, heads right
               ("Table row: Beta; -; EM: 85.6", "table", 3),                            # exact cells, one head on the wrong column
               ("Table row: Gamma; 90.5; Delta; 70.0*; 71.0", "table", 3),              # two rows in one: merged (both)
               ("Table row: 60.0; 61.0", "meta", 3),                                    # Epsilon without its label: partial
               ("Zeta 50.0 51.0 and the text goes on.", "text", 3),                     # glued into prose
               ("Table row: Alpha (Single); 81.2; 87.9", "table", 4))                   # another page: ignored
    by = {x["label"]: x for x in r["rows"]}
    assert [by[k]["outcome"] for k in ("Alpha (Single)", "Beta", "Gamma", "Delta", "Epsilon", "Zeta")] == \
        ["exact", "exact", "merged", "merged", "partial", "missing"]
    assert by["Zeta"]["glued_in_prose"] and by["Eta"]["ambiguous"]
    c = r["counts"]
    assert c["rows"] == 6 and c["ambiguous_rows"] == 1                    # the ambiguous row is in no denominator
    assert c["exact"] == 2 and c["merged"] == 2 and c["partial"] == 1 and c["missing"] == 1 and c["glued"] == 1
    assert c["cells"] == 3 + 3 + 2 + 3 + 3 + 3 and c["cells_found"] == 3 + 3 + 2 + 3 + 2 + 0
    assert c["heads_attached"] == 3 and c["heads_wrong"] == 1             # "EM: 85.6" stands in the F1 column
    assert c["header_rows"] == 2 and c["header_rows_found"] == 1          # "EM; F1" found, "System; Dev" not
    s = B.summarise(__import__("collections").Counter(c))
    assert s["exact_row_accuracy"] == round(2 / 6, 3) and s["cell_accuracy"] == round(13 / 17, 3)


def test_split_row_and_unusable_row():
    r = _score(("Table row: Alpha (Single); 81.2", "table", 3), ("Table row: 87.9", "meta", 3),
               ("Table row: Beta; -; 85.6", "meta", 3))
    by = {x["label"]: x for x in r["rows"]}
    assert by["Alpha (Single)"]["outcome"] == "split" and by["Beta"]["outcome"] == "exact_unusable"


def test_lenient_mode_ignores_footnote_marks_only():
    strict = _score(("Table row: Delta; 70.0; 71.0", "table", 3))
    loose = _score(("Table row: Delta; 70.0; 71.0", "table", 3), mode=B.lenient)
    assert {x["label"]: x["outcome"] for x in strict["rows"]}["Delta"] == "partial"
    assert {x["label"]: x["outcome"] for x in loose["rows"]}["Delta"] == "exact"


def test_annotation_file_is_well_formed_and_matches_its_lock():
    truth = B.load()
    assert truth["human_verified"] is False and "AI" in truth["annotator"]          # never presented as human ground truth
    ids = [t["id"] for t in truth["tables"]]
    assert len(ids) == len(set(ids)) == 11
    for t in truth["tables"]:
        assert t["paper"].endswith(".pdf") and "held_out" not in t["paper"] and t["page"] >= 1
        width = {len(B.expand(r["cells"])) for r in t["rows"]} | {len(B.expand(h)) for h in t["header_rows"]}
        assert len(width) == 1, (t["id"], width)                                    # every row fills the same column grid
        assert all(B.cell_text(c) == B.cell_text(c).strip() for r in t["rows"] for c in r["cells"])
    assert sum(len(t["rows"]) for t in truth["tables"]) == 71
    lock = (ROOT / "eval" / "table_truth" / "ANNOTATIONS_LOCKED.txt").read_text(encoding="utf-8")
    sha = re.search(r"sha256: ([0-9a-fA-F]{64})", lock).group(1).lower()
    assert hashlib.sha256((ROOT / "eval" / "table_truth" / "tables.json").read_bytes()).hexdigest() == sha
