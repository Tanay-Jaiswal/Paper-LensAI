"""The labelling kit: the sheet is blinded and the scorer counts correctly. The labels here are made-up test fixtures
written to a temporary folder; they are not labels of any paper."""
import csv
import json

from eval.labelling import make_sheet
from eval.labelling.score import kappa, score, to_markdown


def _key(tmp_path):
    answers = {
        "Q001": {"type": "checklist", "paper": "P1", "item": "cs_code_link", "paperlens": "present"},
        "Q002": {"type": "checklist", "paper": "P1", "item": "cs_model_size", "paperlens": "missing"},
        "Q003": {"type": "evidence", "paper": "P1", "claim_id": "C1", "paperlens": "strong"},
        "Q004": {"type": "search", "paper": "P1", "claim_id": "C2", "paperlens": "none"},
        "Q005": {"type": "checklist", "paper": "P1", "item": "cs_efficiency", "paperlens": "partial"},
    }
    (tmp_path / "key.json").write_text(json.dumps({"meta": {"name": "t", "paperlens_version": "x", "n": 5, "seed": 1},
                                                   "answers": answers}), encoding="utf-8")


def _labels(tmp_path, who, ans):
    p = tmp_path / f"labels-{who}.csv"
    with p.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "paper", "type", "labeller", "answer", "page_found", "note"])
        for qid, a in ans.items():
            w.writerow([qid, "P1", "", who, a, "", ""])
    return p


def test_kappa():
    assert kappa(["yes", "no", "yes", "no"], ["yes", "no", "yes", "no"]) == 1.0
    assert kappa([], []) is None
    assert kappa(["yes", "yes"], ["yes", "yes"]) is None       # no variation: undefined


def test_one_labeller(tmp_path):
    _key(tmp_path)
    f = _labels(tmp_path, "ann", {"Q001": "yes", "Q002": "yes", "Q003": "partly", "Q004": "yes, I found support",
                                  "Q005": "can't tell"})
    r = score(tmp_path, [f])
    c = r["by_type"]["checklist"]
    assert (c["agree"], c["disagree"], c["cant_tell"]) == (1, 1, 1)
    assert r["by_type"]["evidence"]["agree"] == 1                 # strong + "partly" counts as support found
    assert r["by_type"]["search"]["disagree"] == 1                # the person found support PaperLens missed
    md = to_markdown(r)
    assert "Human-labelled by 1 labeller(s): ann" in md and "one person's judgement" in md


def test_majority_and_inter_annotator(tmp_path):
    _key(tmp_path)
    a = _labels(tmp_path, "ann", {"Q001": "yes", "Q002": "no", "Q003": "yes", "Q004": "no support in the paper",
                                  "Q005": "partly"})
    b = _labels(tmp_path, "bob", {"Q001": "yes", "Q002": "yes", "Q003": "yes", "Q004": "no support in the paper",
                                  "Q005": "partly"})
    r = score(tmp_path, [a, b])
    assert r["by_type"]["checklist"]["no_majority"] == 1          # Q002: one yes, one no
    assert r["by_type"]["checklist"]["agree"] == 2
    assert r["inter"]["n"] == 5 and r["inter"]["percent"] == 80.0


def test_sheet_is_blinded(tmp_path, monkeypatch, make_pdf):
    papers = tmp_path / "papers"
    papers.mkdir()
    for seed in (1, 2):
        (papers / f"paper{seed}.pdf").write_bytes(make_pdf(seed)[0].read_bytes())
    monkeypatch.setattr(make_sheet, "HERE", tmp_path / "out_root")
    (tmp_path / "out_root").mkdir()
    (tmp_path / "out_root" / "labeller_template.html").write_text(
        (make_sheet.Path(make_sheet.__file__).parent / "labeller_template.html").read_text(encoding="utf-8"),
        encoding="utf-8")
    out = make_sheet.build(papers, "t", seed=7)
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))["answers"]
    page = (out / "labeller.html").read_text(encoding="utf-8")
    sheet = (out / "sheet.csv").read_text(encoding="utf-8-sig")
    assert key and set(key) == {row.split(",")[0] for row in sheet.splitlines()[1:] if row.startswith("Q")}
    for leak in ("paperlens", "present", "missing", "strong", "moderate", "weak"):
        assert f'"{leak}"' not in page.split("const DATA = ")[1].split(";\n")[0]
        assert leak not in sheet.lower().replace("paperlens labelling", "")
    # same seed, same sheet
    again = make_sheet.build(papers, "t2", seed=7)
    assert (again / "sheet.csv").read_text(encoding="utf-8-sig") == sheet
