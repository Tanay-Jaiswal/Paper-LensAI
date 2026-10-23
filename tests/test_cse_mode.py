"""Computer Science & Engineering mode: field detection, dictionary fallback, CS checklist items and CS gaps."""
import pytest

from paperlens.cse_terms import CSE_TERMS, lookup
from paperlens.field import detect_field, resolve_mode
from paperlens.gaps import detect_gaps
from paperlens.glossary import build_glossary
from paperlens.models import Claim, Document, Sentence
from paperlens.pipeline import analyze_document
from paperlens.reproducibility import CSE_ITEM_KEYS, assess
from paperlens.revisions import revision_checklist


def doc(*texts, section="method", kind="text"):
    return Document("t", "T", 1, [Sentence(i, t, 1, section, kind=kind) for i, t in enumerate(texts)])


def mixed(*pairs):
    """pairs of (text, section, kind)"""
    return Document("t", "T", 1, [Sentence(i, t, 1, sec, kind=k) for i, (t, sec, k) in enumerate(pairs)])


# ---- dictionary ------------------------------------------------------------------------------------------------------
def test_dictionary_lookup_handles_plural_and_case():
    assert lookup("CNN")[0] == "convolutional neural network"
    assert lookup("CNNs")[0] == "convolutional neural network"
    assert lookup("RESNET")[0] == "residual network"
    assert lookup("XYZQ") is None


def test_every_entry_has_a_meaning_and_a_known_kind():
    for k, (meaning, kind) in CSE_TERMS.items():
        assert meaning and kind in {"concept", "model", "method", "metric", "hardware", "software", "dataset",
                                    "venue", "field"}, k


def test_paper_definition_wins_over_dictionary_and_sources_are_marked():
    g = build_glossary(doc("We use a convolutional neural network (CNN) on a GPU.", "The CNN and an LSTM run on the GPU.",
                           "LSTMs and ResNet-50 features are combined; IoU is reported."), use_dictionary=True)
    defined = {d["abbr"]: d for d in g["defined"]}
    fromd = {d["abbr"]: d for d in g["from_dictionary"]}
    assert defined["CNN"]["source"] == "paper" and "CNN" not in fromd
    assert fromd["LSTM"]["long"] == "long short-term memory" and fromd["LSTM"]["source"] == "dictionary"
    assert fromd["LSTM"]["uses"] == 2          # "LSTM" and "LSTMs"
    assert {"GPU", "ResNet", "IoU"} <= set(fromd)
    assert "dictionary" in g["note"] and g["dictionary_used"]


def test_ambiguous_abbreviation_shows_all_meanings():
    g = build_glossary(doc("We report MAP on the test set.", "MAP improves."), use_dictionary=True)
    d = g["from_dictionary"][0]
    assert d["abbr"] == "MAP" and d["ambiguous"] and " / " in d["long"]


def test_general_mode_uses_no_dictionary():
    g = build_glossary(doc("The LSTM is trained.", "The LSTM is tested."))
    assert g["from_dictionary"] == [] and [u["abbr"] for u in g["undefined"]] == ["LSTM"]


def test_unknown_abbreviations_stay_undefined_in_cse_mode():
    g = build_glossary(doc("The QZXV module helps.", "QZXV again."), use_dictionary=True)
    assert [u["abbr"] for u in g["undefined"]] == ["QZXV"] and not g["from_dictionary"]


# ---- field detection -------------------------------------------------------------------------------------------------
CS_TEXT = ["We train a convolutional neural network on the ImageNet dataset with a GPU.",
           "Our implementation is open-source and the source code is on GitHub."]
BIO_TEXT = ["Patients were randomised to two exercise groups.", "Blood pressure fell after twelve weeks of training."]


def test_detects_cs_and_general_papers():
    assert detect_field(doc(*(CS_TEXT * 5 + BIO_TEXT)))["field"] == "cse"
    assert detect_field(doc(*(BIO_TEXT * 10)))["field"] == "general"


def test_user_choice_overrides_detection_and_bad_mode_is_rejected():
    d = doc(*(BIO_TEXT * 10))
    assert resolve_mode(d, "cse")["field"] == "cse"
    assert resolve_mode(doc(*CS_TEXT), "general")["field"] == "general"
    with pytest.raises(ValueError):
        resolve_mode(d, "physics")


# ---- CS checklist ----------------------------------------------------------------------------------------------------
TRAINING = ["We train the neural network with a learning rate of 0.001 and batch size 32 for 10 epochs."] * 3


def statuses(d, field="cse"):
    return {i["key"]: i["status"] for i in assess(d, field)["items"]}


def test_general_mode_has_no_cs_items_and_scores_are_unchanged():
    d = doc(*TRAINING)
    g, c = assess(d), assess(d, "cse")
    assert not any(i["key"] in CSE_ITEM_KEYS for i in g["items"])
    assert c["standard_score"] == g["score"] == g["standard_score"]
    assert len(c["items"]) == len(g["items"]) + len(CSE_ITEM_KEYS)


def test_code_link_versus_promise():
    assert statuses(doc(*TRAINING, "Code: https://github.com/a/b."))["cs_code_link"] == "present"
    assert statuses(doc(*TRAINING, "Our code will be made publicly available."))["cs_code_link"] == "partial"


def test_hardware_model_versus_generic_gpu():
    assert statuses(doc(*TRAINING, "Training used 8 NVIDIA V100 GPUs."))["cs_hardware_spec"] == "present"
    assert statuses(doc(*TRAINING, "Training used a GPU."))["cs_hardware_spec"] == "partial"


def test_compute_budget_and_hyperparameter_search_and_model_selection():
    s = statuses(doc(*TRAINING, "Training took 3.5 days on eight GPUs.",
                     "The learning rate was selected from {1e-5, 3e-5} by grid search.",
                     "We pick the checkpoint with the best validation accuracy."))
    assert s["cs_compute_budget"] == s["cs_hyper_search"] == s["cs_model_selection"] == "present"
    s = statuses(doc(*TRAINING, "We fine-tuned the model."))
    assert s["cs_hyper_search"] == "missing"      # "fine-tuned" is not hyperparameter tuning


def test_model_only_items_are_not_applicable_without_training():
    d = doc(*(["We prove a bound on the number of comparisons of the sorting algorithm."] * 70))
    s = statuses(d)
    assert s["cs_hyper_search"] == s["cs_model_selection"] == s["cs_model_size"] == "not_applicable"


def test_table_uncertainty_uses_tables_not_text():
    rows = [("Table row: Ours; accuracy: 91.2 ± 0.3", "results", "table")]
    assert statuses(mixed(*rows))["cs_table_uncertainty"] == "present"
    bare = [("Table row: Ours; accuracy: 91.2", "results", "table")]
    assert statuses(mixed(*bare))["cs_table_uncertainty"] == "missing"
    with_text = bare + [("Results are the mean and standard deviation of 5 runs.", "results", "text")]
    assert statuses(mixed(*with_text))["cs_table_uncertainty"] == "partial"
    assert statuses(doc("No tables here."))["cs_table_uncertainty"] == "not_applicable"


# ---- CS gaps and revisions -------------------------------------------------------------------------------------------
def claim(text, **kw):
    c = Claim("C1", 0, text, 1, "abstract", kw.get("claim_type", "result"), False, kw.get("numbers", []))
    c.support = "strong"
    return c


def test_test_set_tuning_is_flagged_and_negation_is_not():
    d = doc("We tuned the dropout rate on the test set.")
    r = assess(d, "cse")
    assert any(g.kind == "test_set_tuning" for g in detect_gaps(d, [], r, "cse"))
    d2 = doc("Hyperparameters were never tuned on the test set.")
    assert not any(g.kind == "test_set_tuning" for g in detect_gaps(d2, [], assess(d2, "cse"), "cse"))
    assert not any(g.kind == "test_set_tuning" for g in detect_gaps(d, [], r, "general"))


def test_copied_baselines_and_promised_code():
    d = doc("Results of the baselines are taken from the original papers.", "Code will be released.")
    kinds = {g.kind: g for g in detect_gaps(d, [], assess(d, "cse"), "cse")}
    assert kinds["baseline_numbers_copied"].severity == "low"
    assert kinds["code_promised_not_linked"].severity == "medium"


def test_small_gain_without_significance_test():
    d = doc("We report accuracy.")
    c = claim("Our method improves accuracy by 0.4 points over the baseline.", claim_type="comparison", numbers=["0.4"])
    gaps = detect_gaps(d, [c], assess(d, "cse"), "cse")
    assert any(g.kind == "small_gain_without_test" for g in gaps)


def test_cs_gaps_become_revision_items_without_duplicates():
    d = doc(*CS_TEXT * 5, "We tuned the dropout rate on the test set.", "Code will be released.")
    a = analyze_document(d, "cse")
    srcs = [x["source"] for x in revision_checklist(a)]
    acts = [x["action"] for x in revision_checklist(a)]
    assert any("validation set" in x for x in acts)
    assert sum("code" in x.lower() and "link" in x.lower() for x in acts) == 1    # gap and item not both listed
    assert any("cs_code_link" in s for s in srcs)


def test_pipeline_reports_mode():
    a = analyze_document(doc(*CS_TEXT * 5), "auto")
    d = a.to_dict()
    assert d["field"]["field"] == "cse" and d["reproducibility"]["field"] == "cse"
    assert d["glossary"]["dictionary_used"]
    a = analyze_document(doc(*CS_TEXT * 5), "general")
    assert a.to_dict()["field"]["field"] == "general" and not a.glossary["from_dictionary"]


# ---- fixes after the first fresh-paper check (docs/CSE_MODE.md) ------------------------------------------------------
def test_project_page_and_unlinked_release_are_partial_not_present():
    assert statuses(doc(*TRAINING, "Project page: https://example-3dgs.github.io/"))["cs_code_link"] == "partial"
    assert statuses(doc(*TRAINING, "We have open-sourced our implementation."))["cs_code_link"] == "partial"


def test_generic_runtime_words_are_not_a_compute_budget_but_stated_times_are():
    assert statuses(doc(*TRAINING, "Pyodide is a Python runtime.", "We compute a metric."))["cs_compute_budget"] == "missing"
    s = statuses(doc(*TRAINING, "The average running time for one scene at 800 x 800 resolution is around 2 minutes."))
    assert s["cs_compute_budget"] == "present"


def test_nvidia_model_number_without_rtx_counts_as_exact_hardware():
    assert statuses(doc(*TRAINING, "All code runs on an NVIDIA 4090 GPU."))["cs_hardware_spec"] == "present"


def test_table_cells_do_not_earn_prose_items():
    d = mixed(*[(t, "method", "text") for t in TRAINING], ("Table row: Downloaded packages; data: 0.91 0.88", "results", "table"))
    assert statuses(d)["cs_data_access"] != "present"


def test_training_items_need_training_not_just_ml_vocabulary():
    # a tool paper that mentions classifiers and models but trains nothing
    text = ["The classifier of prior work flags patches.", "Language models generate candidate patches.",
            "Our tool compares runtime values of the patches."] * 25
    s = statuses(doc(*text))
    assert s["cs_hyper_search"] == s["cs_model_selection"] == s["cs_model_size"] == "not_applicable"
