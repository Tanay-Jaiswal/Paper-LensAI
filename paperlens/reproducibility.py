"""Transparent reproducibility rubric.

Each item has a fixed weight, a set of *full* patterns (explicit statement) and
*partial* patterns (a weaker hint). An item scores 1.0 credit for a full match,
0.5 for a partial match and 0 otherwise. The final score is
    100 * sum(weight_i * credit_i) / sum(weight_i)
Items that only make sense for trained models (hyperparameters, train/validation/test
splits) are marked "not_applicable" and left out of both sums when the paper shows
no sign of model training; the test is deliberately conservative (see _trains_a_model).
The rubric is adapted from the ML Reproducibility Checklist (Pineau et al.) and
common venue checklists (NeurIPS/ACL). It measures what the paper *states*, not
whether the work actually reproduces. Matches are reported with page and quote
so a reader can overrule any individual decision.

In the Computer Science & Engineering mode (field="cse") ten more items are scored (CSE_RUBRIC): a working code link
rather than a promise, dataset sources, exact hardware, compute budget, hyperparameter search, model selection on
validation data, model size, how baselines were obtained, uncertainty in the results tables, and efficiency. The main
score then covers all items; "standard_score" keeps the 15-item score so papers stay comparable across modes.
"""
from __future__ import annotations

import re

from .models import Document, RubricItem

I = re.I
RUBRIC = [
    dict(key="code", label="Code available", category="Artifacts", weight=3.0,
         full=[r"github\.com/\S+", r"gitlab\.com/\S+", r"huggingface\.co/\S+", r"zenodo\.org/\S+",
               r"(code|implementation|source code|models?) (is|are|will be) (publicly )?(available|released|open[- ]sourced)",
               r"we (release|open[- ]source|make available|publish) (our|the) (code|implementation|models?)"],
         partial=[r"code (is )?available (upon|on) request", r"supplementary (material|code)", r"anonymi[sz]ed (repository|code)"],
         advice="Publish code (with a permanent link) and trained checkpoints."),
    dict(key="data", label="Datasets named and accessible", category="Data", weight=2.0,
         full=[r"publicly available", r"(open|freely|openly) (available|accessible)", r"benchmark dataset",
               r"data (is|are) available", r"available (at|from|through) https?://",
               r"standard (benchmark|dataset)s?"],
         partial=[r"\bdatasets?\b", r"\bcorpus\b", r"\bbenchmarks?\b"],
         advice="Name every dataset with version/source and state how to obtain it."),
    dict(key="splits", label="Train/validation/test splits specified", category="Data", weight=2.0,
         full=[r"train(ing)?[/,\- ]+(and )?(validation|val|dev)[/,\- ]+(and )?test", r"\b\d{2}\s?/\s?\d{2}\s?/\s?\d{2}\b",
               r"(standard|official|predefined) (train|split)", r"(validation|dev|held[- ]out) (set|split)",
               r"cross[- ]validation"],
         partial=[r"\btest set\b", r"\btraining set\b", r"\bsplit\b"],
         advice="State exact split sizes/seeds and what was used for tuning."),
    dict(key="preprocessing", label="Preprocessing described", category="Data", weight=1.0,
         full=[r"preprocess\w*", r"tokeni[sz]\w+", r"normali[sz]ed? (the )?(input|image|data|text)", r"data augmentation",
               r"filter(ed|ing) (out )?", r"resiz\w+ (to|the)"],
         partial=[r"\baugment\w*"], advice="Describe cleaning, tokenisation and augmentation steps."),
    dict(key="hyper", label="Hyperparameters reported", category="Method", weight=2.0,
         full=[r"learning[- ]rate", r"batch[- ]size", r"\bepochs?\b", r"\b(adam|adamw|sgd|rmsprop)\b", r"weight decay",
               r"dropout (rate|of|probability)?\s*\d"],
         partial=[r"\boptimi[sz]er\b", r"\btrained? for\b", r"hyper-?parameter"],
         advice="Report all hyperparameters, how they were tuned and the search ranges."),
    dict(key="seeds", label="Seeds / multiple runs", category="Statistics", weight=2.0,
         full=[r"random seeds?", r"\b(\d+|three|five|ten|several) (independent )?(runs|trials|seeds|repetitions)\b",
               r"averaged over \d+", r"mean (over|across) \d+"],
         partial=[r"\bseed\b", r"\bruns?\b.{0,30}\b(mean|average)\b"],
         advice="Run with several seeds and report how many."),
    dict(key="variance", label="Variance / uncertainty reported", category="Statistics", weight=2.0,
         full=[r"standard deviation", r"standard error", r"std\.?\b", r"confidence interval", r"±", r"\+/-",
               r"error bars?", r"\bvariance\b"],
         partial=[r"\bstable\b.{0,20}\bacross\b"],
         advice="Report standard deviation or confidence intervals, not single numbers."),
    dict(key="stat_test", label="Statistical significance test", category="Statistics", weight=1.5,
         full=[r"t-test", r"wilcoxon", r"\bp\s?[<=]\s?0?\.\d+", r"p-value", r"bootstrap(ping)?", r"permutation test",
               r"mann[- ]whitney", r"significance test", r"anova"],
         partial=[r"statistically significant"],
         advice="Back 'significant' claims with a named test and p-value or CI."),
    dict(key="baselines", label="Baselines described", category="Evaluation", weight=2.0,
         full=[r"\b(compare|compared|comparing|comparison)\b[^.]{0,30}\b(against|with|to)\s+(the\s+)?(\w+\s+){0,2}[A-Z][A-Za-z\-]+", r"\bbaselines?\b",
               r"re-?(trained|implemented|run)"],
         partial=[r"(outperform\w*|surpass\w*|better than)\s+[A-Z]"],
         advice="Describe each baseline, its source and how it was tuned."),
    dict(key="ablation", label="Ablation / component analysis", category="Evaluation", weight=1.0,
         full=[r"ablation", r"(removing|without|w/o) (the )?[a-z\- ]{3,30}(reduces|decreases|degrades|hurts)"],
         partial=[r"component analysis", r"sensitivity analysis"],
         advice="Show which components drive the gains."),
    dict(key="metrics", label="Evaluation metrics defined", category="Evaluation", weight=1.0,
         full=[r"evaluat\w+ (metric|measure)", r"(primary|main|standard) metric", r"we (report|use|measure) [\w\- ]{0,30}"
               r"(accuracy|f1|bleu|rouge|auc|map|precision|recall|wer|perplexity|exact match)",
               r"metrics? (is|are|include)"],
         partial=[r"\b(accuracy|f1|bleu|rouge|auc|mAP|precision|recall|wer|perplexity)\b"],
         advice="Define every metric and the averaging scheme (micro/macro)."),
    dict(key="hardware", label="Compute / hardware reported", category="Resources", weight=1.0,
         full=[r"\b(gpus?|tpus?|nvidia|a100|v100|rtx|titan|cpu)\b", r"gpu[- ]hours", r"training time"],
         partial=[r"\bhours?\b", r"\bcompute\b"],
         advice="State hardware, runtime and total compute budget."),
    dict(key="software", label="Software / library versions", category="Resources", weight=1.0,
         full=[r"(pytorch|tensorflow|jax|keras|scikit-learn|python|cuda|transformers)\s*v?\d+(\.\d+)*",
               r"requirements\.txt", r"docker", r"conda environment"],
         partial=[r"\b(pytorch|tensorflow|jax|keras|scikit-learn)\b"],
         advice="Pin library versions or provide an environment file."),
    dict(key="license", label="Licence / ethics statement", category="Ethics", weight=0.5,
         full=[r"licen[sc]e", r"cc[- ]by", r"\bmit license\b", r"apache", r"ethic\w+ (statement|considerations)",
               r"informed consent", r"personal (information|data)", r"irb"],
         partial=[r"\bprivacy\b", r"broader impact"],
         advice="State data/model licences and ethical considerations."),
    dict(key="limitations", label="Limitations discussed", category="Honesty", weight=1.0,
         full=[r"\blimitations?\b", r"threats? to validity", r"(does|do) not generali[sz]e", r"fail(s|ure)? (cases?|when)",
               r"shortcomings?"],
         partial=[r"\bhowever\b.{0,60}\b(only|not|cannot)\b"],
         advice="Add a limitations section naming settings where the method fails."),
]
_GPU_MODEL = (r"(?:a100|v100|h100|h200|p100|p40|k80|k40|t4|a10g?|a40|a6000|l4|l40s?|mi\d{3}x?|"
              r"rtx\s?(?:a?\d{4})(?:\s?ti)?|gtx\s?\d{3,4}(?:\s?ti)?|titan\s?(?:x|xp|v|rtx|black)|tpu\s?v\d\w*)")
CSE_RUBRIC = [
    dict(key="cs_code_link", label="Working link to the code", category="Artifacts", weight=1.0,
         full=[r"https?://(?!\S*github\.io)\S*(github|gitlab|bitbucket|huggingface|zenodo|codeocean|4open\.science|sourceforge)\S*",
               r"\b(github|gitlab)\.com/\S+"],
         partial=[r"(code|implementation|models?|checkpoints?)[^.]{0,40}\bwill be (made )?(publicly )?(available|released|open[- ]sourced)",
                  r"\b(open[- ]sourced?|released?|publish(ed)?) (our|the) (code|implementation|tool|library|software|plugin)",
                  r"https?://\S*github\.io\S*",
                  r"(code|implementation) (is )?available (upon|on) request", r"anonymi[sz]ed (repository|code)"],
         advice="Give a permanent link to the code (a repository or archive), not a promise to release it later."),
    dict(key="cs_data_access", label="Dataset sources or versions given", category="Data", weight=1.0,
         full=[r"\b(datasets?|data|corpus|corpora|benchmarks?)\b[^.]{0,80}(https?://|available (at|from)|download\w*)",
               r"https?://\S*(dataset|kaggle|huggingface\.co/datasets|archive\.ics\.uci|paperswithcode)",
               r"(dataset|corpus|benchmark)[^.]{0,30}\b(version|v)\s?\d",
               r"\b(official|standard|public|publicly available) (train(ing)?|test|dev|development|validation)?\s?(splits?|release|version)"],
         partial=[r"\b[A-Z][A-Za-z0-9\-]{2,} (dataset|corpus|benchmark)\b"],
         advice="For every dataset give its source (link or citation), the version and the split used."),
    dict(key="cs_hardware_spec", label="Exact hardware model", category="Resources", weight=1.0,
         full=[r"\b(?:nvidia\s+)?(?:tesla\s+)?(?:geforce\s+)?" + _GPU_MODEL + r"\b", r"\bnvidia\s+(geforce\s+)?\d{4}\b",
               r"\b(xeon|epyc|ryzen|core i\d|apple m\d|arm cortex|raspberry pi|jetson)\b"],
         partial=[r"\b(gpus?|tpus?|cpus?|accelerators?)\b"],
         advice="Name the exact hardware (for example '8 NVIDIA V100 32 GB GPUs' or the CPU model) and how many units."),
    dict(key="cs_compute_budget", label="Training or running time / compute budget", category="Resources", weight=1.0,
         full=[r"\b[gt]pu[- ](hours?|days?)\b", r"petaflop", r"wall[- ]clock", r"compute budget",
               r"\b(train(ed|ing)?|took|takes|ran|runs?|running time|converge[sd]?)\b[^.]{0,60}?\b\d+(\.\d+)?\s*"
               r"(hours?|days?|minutes?|weeks?|hrs?)\b",
               r"\b\d+(\.\d+)?\s*(hours?|days?|minutes?)\s+(on|using|with)\b",
               r"\b(running|training|inference|execution|reconstruction|average) (time|running)\b[^.]{0,120}"
               r"\b\d+(\.\d+)?\s*(seconds?|minutes?|hours?|days?|ms)\b"],
         partial=[r"training time", r"running time", r"\bFLOPs?\b", r"computational cost"],
         advice="Report training and inference time on the stated hardware, and the total compute (for example GPU-hours)."),
    dict(key="cs_hyper_search", label="Hyperparameter search described", category="Method", weight=1.0, model_only=True,
         full=[r"grid search", r"random(ised|ized)? search", r"bayesian optimi[sz]ation", r"search (space|range)",
               r"(hyper-?parameters?|learning rates?)[^.]{0,60}\b(tuned|selected|chosen|searched|swept)\b[^.]{0,40}"
               r"\b(on|using|over|from|among|in)\b",
               r"\b(selected|chosen|tuned|swept|searched) (from|among|over|in) (\{|\d)",
               r"(tun\w+|select\w*|chose\w*|search\w*)[^.]{0,30}hyper-?parameters?[^.]{0,60}(validation|dev|development)",
               r"\b(is|are|was|were) tuned on the (validation|dev|development)",
               r"(learning rates?|batch sizes?|dropout|weight decay|\blr\b)[^.]{0,40}(\{|∈|\bin \[)\s*\d[\d.e\-]*\s*,"],
         partial=[r"(?<!fine-)(?<!fine )(?<!fine)\b(tuned|tuning)\b", r"hyper-?parameter (tuning|search|optimi[sz]ation|sweep)"],
         advice="Say how hyperparameters were chosen: the search method, the ranges tried and the data used to choose."),
    dict(key="cs_model_selection", label="Model selection on validation data, not test", category="Evaluation",
         weight=1.0, model_only=True,
         full=[r"early stopping",
               r"(best|selected?|chose|choose|pick\w*) (the )?(checkpoint|model|epoch|run)[^.]{0,50}"
               r"(validation|dev|development|held[- ]out)",
               r"(validation|dev|development|held[- ]out) (set|split|data|performance|accuracy|loss)[^.]{0,60}"
               r"(select|choose|chose|tun|pick|early|stop)",
               r"(select\w*|choose|chose|chosen|tun\w+|pick\w*)[^.]{0,60}(on|using|based on|according to) (the )?"
               r"(validation|dev|development|held[- ]out)"],
         partial=[r"\bcheckpoints?\b", r"\b(validation|dev) (set|split)\b"],
         advice="State which data chose the final model or checkpoint (a validation set, not the test set)."),
    dict(key="cs_model_size", label="Model size (number of parameters)", category="Method", weight=0.5, model_only=True,
         full=[r"\b\d+(\.\d+)?\s?[MBK]\s+(trainable\s+)?(parameters|params)\b",
               r"\b\d+(\.\d+)?\s?(million|billion|thousand) (trainable )?(parameters|params)\b",
               r"(number of|#)\s?(trainable\s+)?(parameters|params)\b", r"\bparams\b\W{0,3}\d",
               r"\bparams\b[^.;]{0,20}(×|x)\s*10"],      # a table column "params ×10^6"
         partial=[r"model size", r"parameter count"],
         advice="Report the number of trainable parameters of each model compared."),
    dict(key="cs_baseline_setup", label="How baselines were obtained", category="Evaluation", weight=1.0,
         full=[r"(official|publicly available|released|authors'?) (code|implementation|checkpoints?)",               r"\b(we|were|was|are|is|been) re-?(implement|train|ran|run)\w*",
               r"\bre-?(implemented|trained|ran|run) (the |all |each |their |these |those )?(baselines?|models?|methods?|systems?)",
               r"(numbers|results|scores) (are |were )?(taken|copied|quoted) from",
               r"(results?|numbers|scores|accuracy|accuracies|baselines?|performance)[^.]{0,60}\b(as )?reported "
               r"(in|by) (the )?(original|\[|\(|\w+ et al)",
               r"same (hyper-?parameters|training (budget|setup|data|protocol|schedule)|budget|settings?|setup|protocol)",
               r"\bfair comparison\b"],
         partial=[r"\bbaselines?\b"],
         advice="For each baseline say whether it was re-run (with which code and tuning budget) or its numbers were copied."),
    dict(key="cs_table_uncertainty", label="Uncertainty shown in the results tables", category="Statistics", weight=1.0,
         full=[], partial=[],
         advice="Show the spread over runs (± standard deviation or a confidence interval) in the main results tables."),
    dict(key="cs_efficiency", label="Efficiency reported (runtime, memory or complexity)", category="Resources",
         weight=0.5,
         full=[r"time complexity", r"space complexity", r"\bO\([^)]{0,20}[nNkKdDmMT][^)]{0,20}\)",
               r"\b(latency|throughput|inference (speed|cost)|inference time (of|is|was|per)|memory (usage|footprint|consumption|cost)|speed-?ups?|"
               r"(tokens|images|frames|samples|queries|requests) per second|fps|ms per|msec)\b"],
         partial=[r"\b(faster|efficien(t|cy)|cheaper|lightweight)\b"],
         advice="Report runtime, memory use or computational complexity next to accuracy, so cost can be weighed."),
]
CSE_ITEM_KEYS = tuple(r["key"] for r in CSE_RUBRIC)
_UNC_TABLE = re.compile(r"±|\+/-|\+-\s?\d|\bstd\.?\b|standard deviation|standard error|confidence interval|"
                        r"\b(mean|average[sd]?) (over|of|across) \d+ (runs|seeds|trials)|error bars?", re.I)

SEARCH_SECTIONS = {"abstract", "introduction", "background", "method", "experiments", "results", "discussion",
                   "limitations", "conclusion", "reproducibility", "ethics", "appendix", "related", "other", "front"}


# Items that presuppose a trained model, and the vocabulary that shows a paper trains one.
MODEL_ONLY_ITEMS = ("hyper", "splits")
_TRAINING_RE = re.compile(
    r"\b(neural networks?|deep learning|machine learning|learning rate|batch size|training (?:set|data|examples|loss)|"
    r"test set|validation set|dev set|fine-?tun\w+|pre-?train\w+|gradient descent|back-?propagation|classifiers?|"
    r"hyper-?parameters?|epochs?|language models?|embeddings?|convolutional|we train(?:ed)?)\b", re.I)


def _trains_a_model(doc: Document) -> bool:
    """Conservative: only say 'no' for a full-length paper (60+ sentences) in which fewer than 3 sentences use
    any model-training vocabulary. Short or partially parsed documents are always scored on every item.

    On the 16 real papers of docs/EVALUATION.md the count is 0-2 for the physics, medical, ecology and meta-science
    papers and 13 or more for every paper that trains a model.
    """
    body = [s for s in doc.sentences if s.section in SEARCH_SECTIONS and s.kind != "meta"]
    if len(body) < 60:
        return True
    return sum(1 for s in body if _TRAINING_RE.search(s.text)) >= 3


_FITS_A_MODEL = re.compile(
    r"\b(learning rates?|batch sizes?|epochs?|optimi[sz]er|fine-?tun\w+|pre-?train\w+|we train(?:ed)?|"
    r"(?:is|are|was|were|be) trained|trained (?:on|for|with|using)|training (?:set|data|loss|split)|gradient descent|"
    r"hyper-?parameters?)\b", re.I)


def _fits_a_model(doc: Document) -> bool:
    """Stricter than _trains_a_model, for the CS items about training (search, model selection, model size): at
    least 3 body sentences that talk about training a model, not only about models in general."""
    body = [s for s in doc.sentences if s.section in SEARCH_SECTIONS and s.section != "related" and s.kind == "text"]
    return sum(1 for s in body if _FITS_A_MODEL.search(s.text)) >= 3


# CS items read prose and captions only: a table cell ("Downloaded", "params") is not a statement about the method
_CS_TABLE_ITEMS = ("cs_model_size", "cs_table_uncertainty")


def _scan(doc: Document, patterns: list[str], key: str):
    hits = []
    for s in doc.sentences:
        if s.section not in SEARCH_SECTIONS:
            continue
        if key.startswith("cs_") and key not in _CS_TABLE_ITEMS and s.kind == "table":
            continue
        if key == "limitations" and s.section == "limitations":
            hits.append(s)
            continue
        for pat in patterns:
            if re.search(pat, s.text, I):
                hits.append(s)
                break
    return hits


def _table_uncertainty(doc: Document, text_has_variance: bool):
    """Results tables (rows and captions) that show spread over runs; None when the paper has no results table."""
    tab = [s for s in doc.sentences if s.kind in ("table", "caption") and s.section in SEARCH_SECTIONS
           and s.section != "related"]
    if not any(s.kind == "table" and re.search(r"\d\.\d", s.text) for s in tab):
        return None
    hits = [s for s in tab if _UNC_TABLE.search(s.text)]
    if hits:
        return "present", hits
    return ("partial", []) if text_has_variance else ("missing", [])


def assess(doc: Document, field: str = "general") -> dict:
    items: list[RubricItem] = []
    trains = _trains_a_model(doc)
    fits = field == "cse" and trains and _fits_a_model(doc)
    for r in RUBRIC + (CSE_RUBRIC if field == "cse" else []):
        if r["key"] == "cs_table_uncertainty":
            var = next((i for i in items if i.key == "variance"), None)
            res = _table_uncertainty(doc, var is not None and var.status == "present")
            if res is None:
                items.append(RubricItem(r["key"], r["label"], r["category"], r["weight"], "not_applicable", 0.0, [],
                                        "Not scored: no results table with decimal numbers was found."))
                continue
            status, ev = res
            advice = "" if status == "present" else r["advice"] + (
                " Spread is mentioned in the text but not in the tables." if status == "partial" else "")
            items.append(RubricItem(r["key"], r["label"], r["category"], r["weight"], status,
                                    {"present": 1.0, "partial": 0.5, "missing": 0.0}[status],
                                    [{"page": s.page, "section": s.section, "quote": s.text[:240], "sentence_id": s.id}
                                     for s in ev[:3]], advice))
            continue
        if (not trains and r["key"] in MODEL_ONLY_ITEMS) or (r.get("model_only") and not fits):
            items.append(RubricItem(r["key"], r["label"], r["category"], r["weight"], "not_applicable", 0.0, [],
                                    "Not scored: no model training was detected in this paper."))
            continue
        full = _scan(doc, r["full"], r["key"])
        # for the 'related' section, statements about other people's work should not count
        full = [s for s in full if s.section != "related" or r["key"] == "code"
                or (r["key"] == "cs_code_link" and re.search(r"\b(our|we|code)\b", s.text, I))]
        part = [] if full else [s for s in _scan(doc, r["partial"], r["key"]) if s.section != "related"]
        if full:
            status, credit, ev = "present", 1.0, full
        elif part:
            status, credit, ev = "partial", 0.5, part
        else:
            status, credit, ev = "missing", 0.0, []
        evidence = [{"page": s.page, "section": s.section, "quote": s.text[:240], "sentence_id": s.id}
                    for s in ev[:3]]
        items.append(RubricItem(r["key"], r["label"], r["category"], r["weight"], status, credit, evidence,
                                "" if status == "present" else r["advice"]))
    scored = [i for i in items if i.status != "not_applicable"]
    total_w = sum(i.weight for i in scored)
    score = 100.0 * sum(i.weight * i.credit for i in scored) / total_w
    base = [i for i in scored if i.key not in CSE_ITEM_KEYS]
    standard = 100.0 * sum(i.weight * i.credit for i in base) / sum(i.weight for i in base)
    cats: dict[str, dict] = {}
    for i in scored:
        c = cats.setdefault(i.category, {"weight": 0.0, "earned": 0.0})
        c["weight"] += i.weight
        c["earned"] += i.weight * i.credit
    for c in cats.values():
        c["score"] = round(100 * c["earned"] / c["weight"], 1)
    band = "high" if score >= 75 else "moderate" if score >= 50 else "low"
    return {
        "score": round(score, 1), "band": band, "field": field, "standard_score": round(standard, 1),
        "cse_items": [i.key for i in items if i.key in CSE_ITEM_KEYS],
        "formula": "100 * sum(weight * credit) / sum(weight); credit: present=1, partial=0.5, missing=0; "
                   "not_applicable items are left out of both sums",
        "not_applicable": [i.key for i in items if i.status == "not_applicable"],
        "items": [i.to_dict() for i in items], "categories": cats,
        "disclaimer": "Measures what the paper reports (checklist coverage), not whether results actually reproduce.",
    }
