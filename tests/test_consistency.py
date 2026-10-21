"""Numeric Consistency Audit: each check must pass correct arithmetic and flag wrong arithmetic."""
import pytest

from paperlens.consistency import audit, parse_row
from paperlens.models import Document, Sentence


def run(*texts, kind="text"):
    doc = Document("t", "T", 1, [Sentence(i, t, 1, "results", kind=kind) for i, t in enumerate(texts)])
    return audit(doc)


def statuses(rep, kind):
    return [c["status"] for c in rep["checks"] if c["kind"] == kind]


# ---- percentages of a count ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Of these, 45 of 120 patients (37.5%) responded.",
    "We observed 45/120 (37.5%) responders.",
    "In total 45 (37.5%) of 120 patients responded.",
    "Overall 99 of 150 (66%) participants were suppressed.",       # 66.0 printed without decimals
    "A total of 2 of 3 (66.6%) raters agreed.",                     # truncation instead of rounding is accepted
])
def test_percent_consistent(text):
    assert statuses(run(text), "percent_of_count") == ["consistent"]


def test_percent_wrong_denominator_flagged_high():
    # the real case found on a held-out paper: the text says 22 of 258 (8.5%), a footnote says 22/307 (8.5%)
    rep = run("Approximately 22/307 (8.5%), 11 in control and 11 in intervention, did not have a viral load.")
    (c,) = rep["checks"]
    assert c["status"] == "inconsistent" and c["severity"] == "high"
    assert "22 / 307" in c["formula"] and "7.1661" in c["computed"]


def test_percent_rounding_slip_is_low_severity():
    (c,) = run("23 of 157 (14.7%) had transferred out.")["checks"]   # 14.6497 rounds to 14.6
    assert c["status"] == "inconsistent" and c["severity"] == "low" and "rounding slip" in c["message"]


def test_percent_ignores_years_and_impossible_counts():
    assert run("Between 2019 of 2020 (50%) there was no change.")["n_checked"] == 0
    assert run("We saw 130 of 120 (108%) in the log.")["n_checked"] == 0   # x > y is not a share of a count


# ---- stated changes ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Accuracy improved from 81.2 to 84.6 (+3.4).",
    "Accuracy improved from 81.2% to 84.6%, an increase of 3.4 points.",
    "The error was reduced by 25% from 40 to 30.",                   # relative reading
    "Latency fell from 120 ms to 90 ms, a reduction of 25%.",
    "F1 rose from 70.1 to 72.3 (2.2 point gain).",
])
def test_change_consistent(text):
    assert statuses(run(text), "stated_change") == ["consistent"]


def test_change_wrong_difference_flagged():
    rep = run("Accuracy improved from 81.2 to 84.6 (+4.4).")
    (c,) = [c for c in rep["checks"] if c["kind"] == "stated_change"]
    assert c["status"] == "inconsistent" and "3.4" in c["formula"]


def test_change_direction_flagged():
    rep = run("The error rate increased from 12.0 to 9.0, an increase of 3.0 points.")
    assert "inconsistent" in statuses(rep, "change_direction")


def test_ranges_years_and_citations_are_not_changes():
    assert run("Interventions lasting from 2 to 6 weeks are inconsistent [12, 13].")["n_checked"] == 0
    assert run("Deforestation from 1989 to 2013 was largest in Cameroon (16.9%).")["n_checked"] == 0


def test_fold_change():
    assert statuses(run("Throughput rose 3-fold from 10 to 30 queries per second."), "fold_change") == ["consistent"]
    assert statuses(run("Throughput rose 5-fold from 10 to 30 queries per second."), "fold_change") == ["inconsistent"]


# ---- confidence intervals ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,status", [
    ("The adjusted OR was 1.27 (95% CI 0.79 to 2.03).", "consistent"),
    ("Mean difference −0.5 (95% CI −1.2 to 0.2).", "consistent"),
    ("The hazard ratio was 1.52 (95% CI: 1.21–1.90).", "consistent"),
    ("The hazard ratio was 2.52 (95% CI: 1.21–1.90).", "inconsistent"),
])
def test_ci(text, status):
    assert statuses(run(text), "ci_contains_estimate") == [status]


# ---- p-values (statcheck-style) ------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,status", [
    ("The groups differed, t(28) = 2.20, p = .036.", "consistent"),
    ("The groups differed, t(28) = 2.20, p < .05.", "consistent"),
    ("There was an effect, F(2, 57) = 3.95, p = .025.", "consistent"),
    ("Association was found, χ2(1) = 4.20, p = .040.", "consistent"),
    ("The groups differed, t(28) = 1.20, p = .036.", "inconsistent"),
    ("The groups differed, t(28) = 1.20, p < .05.", "inconsistent"),
])
def test_p_values(text, status):
    assert statuses(run(text), "p_value") == [status]


def test_p_value_decision_flip_is_high():
    (c,) = run("The groups differed, t(28) = 1.20, p = .036.")["checks"]
    assert c["severity"] == "high" and "changes the conclusion" in c["message"]


# ---- tables --------------------------------------------------------------------------------------------------------
def test_parse_row():
    assert parse_row("Table row: BERT; MNLI: 84.6/83.4; Average: 79.6") == ("BERT", [("MNLI", "84.6/83.4"), ("Average", "79.6")])
    assert parse_row("Not a row") is None


def test_row_total_and_category_code():
    ok = run("Table row: Train; SUPPORTS: 332; NOINFO: 304; REFUTES: 173; All: 809", kind="table")
    bad = run("Table row: Train; SUPPORTS: 332; NOINFO: 304; REFUTES: 173; All: 819", kind="table")
    code = run("Table row: Level: 1; Total: 81 (26.4); Control: 46 (29.3); Intervention: 35 (23.3)", kind="table")
    assert statuses(ok, "table_row_total") == ["consistent"]
    assert statuses(bad, "table_row_total") == ["inconsistent"]
    assert statuses(code, "table_row_total") == ["consistent"]


def test_row_average_including_split_cells():
    # BERT Table 1: the GLUE average counts MNLI-m and MNLI-mm separately
    row = ("Table row: BERTBASE; MNLI-(m/mm): 84.6/83.4; QQP: 71.2; QNLI: 90.5; SST-2: 93.5; CoLA: 52.1; "
           "STS-B: 85.8; MRPC: 88.9; RTE: 66.4; Average: 79.6")
    assert statuses(run(row, kind="table"), "table_row_average") == ["consistent"]
    off = row.replace("Average: 79.6", "Average: 81.0")
    assert statuses(run(off, kind="table"), "table_row_average") == ["not_reproduced"]   # could be weighted


def test_f1_harmonic_mean():
    assert statuses(run("Table row: FEVER; P: 41.5; R: 57.9; F1: 48.4", kind="table"), "f1_harmonic_mean") == ["consistent"]
    assert statuses(run("Table row: FEVER; P: 41.5; R: 57.9; F1: 58.4", kind="table"), "f1_harmonic_mean") == ["inconsistent"]
    # a small gap is what averaging F1 over runs produces, so it is not called an error
    assert statuses(run("Table row: X; P: 83.3; R: 77.0; F1: 80.2", kind="table"), "f1_harmonic_mean") == ["not_reproduced"]


def test_column_total_and_subtotals():
    rows = ["Table row: Train; A: 10; B: 5", "Table row: Dev; A: 3; B: 2", "Table row: Test; A: 4; B: 1",
            "Table row: Total; A: 17; B: 8"]
    assert statuses(run(*rows, kind="table"), "table_column_total") == ["consistent", "consistent"]
    bad = rows[:3] + ["Table row: Total; A: 18; B: 8"]
    assert sorted(statuses(run(*bad, kind="table"), "table_column_total")) == ["consistent", "inconsistent"]
    # subtotal rows: the total matches the subtotals, and each subtotal is checked against its own rows
    sub = ["Table row: S1; A: 3", "Table row: S2; A: 4", "Table row: North; A: 7",
           "Table row: S3; A: 50", "Table row: S4; A: 50", "Table row: South; A: 100", "Table row: Total; A: 107"]
    assert statuses(run(*sub, kind="table"), "table_column_total") == ["consistent"] * 3
    # the real case on a held-out paper: one region's rows do not add up to its subtotal row
    bad_sub = sub[:5] + ["Table row: South; A: 99", "Table row: Total; A: 106"]
    rep = run(*bad_sub, kind="table")
    assert statuses(rep, "table_column_total").count("inconsistent") == 1
    (c,) = [c for c in rep["checks"] if c["status"] == "inconsistent"]
    assert c["details"]["row"] == "South" and c["stated"] == "99" and c["computed"] == "100"
    # averages, rates and percentages are not additive, so their columns are not summed
    avg = ["Table row: S1; Avg. cases: 3", "Table row: S2; Avg. cases: 4", "Table row: Total; Avg. cases: 8"]
    assert run(*avg, kind="table")["n_checked"] == 0


# ---- report shape --------------------------------------------------------------------------------------------------
def test_report_lists_consistent_checks_and_sorts_problems_first():
    rep = run("Accuracy improved from 81.2 to 84.6 (+3.4).", "Approximately 22/307 (8.5%) were missing.")
    assert rep["n_checked"] == 2 and rep["n_inconsistent"] == 1 and rep["n_consistent"] == 1
    assert rep["checks"][0]["status"] == "inconsistent" and rep["checks"][0]["id"] == "N1"
    assert all(c["formula"] and c["quote"] and c["page"] == 1 for c in rep["checks"])


def test_meta_text_is_skipped_but_table_rows_are_checked():
    assert run("Figure: 45 of 120 (50%) shown.", kind="meta")["n_checked"] == 0
    assert run("Table row: Train; A: 1; B: 2; Total: 3", kind="meta")["n_checked"] == 1


def test_pipeline_includes_consistency(make_pdf):
    from paperlens.pipeline import analyze_pdf
    a = analyze_pdf(make_pdf(1)[0])
    d = a.to_dict()
    assert "consistency" in d and d["consistency"]["n_checked"] == len(d["consistency"]["checks"])


# ---- revision checklist --------------------------------------------------------------------------------------------
def test_revision_checklist_turns_findings_into_page_cited_fixes(make_pdf):
    from conftest import NONE
    from paperlens.pipeline import analyze_pdf
    from paperlens.report import to_html, to_markdown
    a = analyze_pdf(make_pdf(1, NONE, unsupported=1)[0])
    a.consistency = run("Approximately 22/307 (8.5%) were missing.")
    rev = a.to_dict()["revisions"]
    assert rev[0]["category"] == "Numbers" and "22 / 307" in rev[0]["action"] and rev[0]["priority"] == "high"
    assert {x["category"] for x in rev} == {"Numbers", "Claims", "Reproducibility"}
    assert [x["id"] for x in rev] == [f"R{i}" for i in range(1, len(rev) + 1)]
    assert all(x["action"] and x["why"] and x["source"] for x in rev)
    # the checklist item replaces the matching paper-level gap instead of repeating it
    assert not any(x["source"].startswith("Evidence gap") and "code" in x["action"].lower() for x in rev)
    assert "Revision checklist" in to_markdown(a) and "Revision checklist" in to_html(a)


def test_revision_checklist_empty_for_unreadable_paper():
    from paperlens.pipeline import analyze_document
    doc = Document("t", "T", 1, [])
    doc.warnings.append(__import__("paperlens.ingest", fromlist=["UNREADABLE_WARNING"]).UNREADABLE_WARNING)
    a = analyze_document(doc)
    assert not [x for x in a.to_dict()["revisions"] if x["category"] == "Reproducibility"]
