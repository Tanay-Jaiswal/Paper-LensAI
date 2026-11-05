"""Revision checklist: the analysis findings rewritten as concrete, page-cited fixes for the authors.

Nothing here is new analysis or generated text. Each item is one finding from the Numbers check, the evidence-gap rules,
the reproducibility checklist or the reference checks, turned into "what to change, why, where" with fixed wording per finding type, so the
same paper always gets the same list and every item points back to the finding it came from.
"""
from __future__ import annotations

# gap kinds that the reproducibility checklist already covers item by item; listing both would repeat the advice
_COVERED_BY_RUBRIC = {"no_code", "no_hyperparameters", "no_limitations", "no_splits", "code_promised_not_linked"}

_GAP_FIX = {
    "unsupported_claim": ("Back this claim with a result in the paper, or soften it",
                          "No passage in the results, tables or discussion supports it as written."),
    "number_not_in_results": ("Show where the figure in this claim comes from",
                              "The value is stated here but never appears in the results text or tables."),
    "superlative_without_baselines": ("Describe the baselines behind the 'best / state-of-the-art' wording, or drop it",
                                      "A superlative needs a comparison, and no baselines are described."),
    "superlative_unsupported": ("Add the head-to-head comparison that supports the superlative, or tone it down",
                                "The results do not show a clear comparison backing it."),
    "significance_without_test": ("Name the statistical test and give the p-value or confidence interval",
                                  "'Significant' is used, but no test is reported."),
    "improvement_without_variance": ("Report variance (standard deviation, several seeds or a confidence interval) for this gain",
                                     "A single number cannot show the improvement is larger than run-to-run noise."),
    "generalization_narrow_evidence": ("Evaluate on more datasets, or narrow the claim to the datasets tested",
                                       "The claim is general, but the evidence covers few datasets."),
    "comparison_without_baselines": ("Describe the baselines used in the comparisons",
                                     "Comparative claims are made without saying what is compared against."),
    # Computer Science & Engineering mode
    "test_set_tuning": ("Choose hyperparameters and checkpoints on a validation set and re-report the test results",
                        "Choices made on the test set make the test numbers optimistic."),
    "baseline_numbers_copied": ("State that copied baseline numbers use the same dataset version, split and metric, "
                                "or re-run the baselines",
                                "Numbers from other papers are only comparable under an identical setup."),
    "code_promised_not_linked": ("Replace the promise to release code with a working repository link",
                                 "Reviewers and readers cannot check or rerun code that is not linked."),
    "small_gain_without_test": ("Report a significance test or the spread over several seeds for this small gain",
                                "A gain of about one point or less can come from random seeds alone."),
    "sota_single_run": ("Report results over several seeds with standard deviation before claiming state of the art",
                        "A single run cannot show the method is reliably the best."),
}
_SEV_RANK = {"high": 0, "medium": 1, "low": 2}
_CITATION_FIX = {
    "cited_not_listed": "Add the missing entry to the reference list, or correct the citation",
    "listed_not_cited": "Cite this entry where it is used, or remove it from the reference list",
    "duplicate_entry": "Remove the duplicate reference entry",
    "entry_without_year": "Add the year of publication (or an access date) to this reference",
}


def _numbers_item(c: dict) -> dict:
    where = f"p.{c['page']}"
    if c["kind"] == "percent_of_count":
        action = f"Correct the percentage on {where}: {c['formula']}, but {c['stated']} is printed"
    elif c["kind"] in ("table_row_total", "table_column_total"):
        action = f"Correct the table total on {where}: {c['formula']}, but {c['stated']} is printed"
    elif c["kind"] == "p_value":
        action = f"Check the reported {c['stated']} on {where}: {c['formula']}"
    elif c["kind"] == "ci_contains_estimate":
        action = f"Check the estimate and interval on {where}: the estimate lies outside {c['stated']}"
    else:
        action = f"Correct the arithmetic on {where}: {c['formula']}, but {c['stated']} is printed"
    return {"priority": c["severity"], "category": "Numbers", "action": action + ".",
            "why": c["message"], "page": c["page"], "quote": c["quote"], "source": f"Numbers check {c['id']}"}


def revision_checklist(analysis) -> list[dict]:
    """Ordered list of fixes; empty when the paper could not be read."""
    items: list[dict] = []
    for c in (analysis.consistency or {}).get("checks", []):
        if c["status"] == "inconsistent":
            items.append(_numbers_item(c))
    for g in analysis.gaps:
        if g.kind in _COVERED_BY_RUBRIC or g.kind not in _GAP_FIX:
            continue
        action, why = _GAP_FIX[g.kind]
        items.append({"priority": g.severity, "category": "Claims", "action": action + (f" (p.{g.page})." if g.page else "."),
                      "why": why + " " + g.message, "page": g.page, "quote": g.quote,
                      "source": f"Evidence gap {g.id}" + (f", claim {g.claim_id}" if g.claim_id else "")})
    if analysis.rubric.get("band") != "not assessed":
        for it in analysis.rubric.get("items", []):
            if it["status"] not in ("missing", "partial"):
                continue
            ev = it["evidence"][0] if it["evidence"] else None
            prio = "high" if it["status"] == "missing" and it["weight"] >= 2 else "medium" if it["status"] == "missing" else "low"
            items.append({"priority": prio, "category": "Reproducibility", "action": it["advice"],
                          "why": f"Checklist item '{it['label']}' is {it['status']}"
                                 + (" (only mentioned in passing)." if it["status"] == "partial" else " (not found in the paper)."),
                          "page": ev["page"] if ev else None, "quote": ev["quote"] if ev else "",
                          "source": f"Reproducibility item '{it['key']}' (weight {it['weight']})"})
    for f in (getattr(analysis, "citations", None) or {}).get("findings", []):
        items.append({"priority": f["severity"], "category": "References", "action": _CITATION_FIX[f["kind"]] + ".",
                      "why": f["message"], "page": f["page"], "quote": f["quote"], "source": f"Reference check {f['id']}"})
    cat = {"Numbers": 0, "Claims": 1, "Reproducibility": 2, "References": 3}
    items.sort(key=lambda x: (_SEV_RANK[x["priority"]], cat[x["category"]], x["page"] or 0))
    for i, x in enumerate(items, 1):
        x["id"] = f"R{i}"
    return items
