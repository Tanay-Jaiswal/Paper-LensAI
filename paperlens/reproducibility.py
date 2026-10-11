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


def _scan(doc: Document, patterns: list[str], key: str):
    hits = []
    for s in doc.sentences:
        if s.section not in SEARCH_SECTIONS:
            continue
        if key == "limitations" and s.section == "limitations":
            hits.append(s)
            continue
        for pat in patterns:
            if re.search(pat, s.text, I):
                hits.append(s)
                break
    return hits


def assess(doc: Document) -> dict:
    items: list[RubricItem] = []
    trains = _trains_a_model(doc)
    for r in RUBRIC:
        if not trains and r["key"] in MODEL_ONLY_ITEMS:
            items.append(RubricItem(r["key"], r["label"], r["category"], r["weight"], "not_applicable", 0.0, [],
                                    "Not scored: no model training was detected in this paper."))
            continue
        full = _scan(doc, r["full"], r["key"])
        # for the 'related' section, statements about other people's work should not count
        full = [s for s in full if s.section != "related" or r["key"] in ("code",)]
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
    cats: dict[str, dict] = {}
    for i in scored:
        c = cats.setdefault(i.category, {"weight": 0.0, "earned": 0.0})
        c["weight"] += i.weight
        c["earned"] += i.weight * i.credit
    for c in cats.values():
        c["score"] = round(100 * c["earned"] / c["weight"], 1)
    band = "high" if score >= 75 else "moderate" if score >= 50 else "low"
    return {
        "score": round(score, 1), "band": band,
        "formula": "100 * sum(weight * credit) / sum(weight); credit: present=1, partial=0.5, missing=0; "
                   "not_applicable items are left out of both sums",
        "not_applicable": [i.key for i in items if i.status == "not_applicable"],
        "items": [i.to_dict() for i in items], "categories": cats,
        "disclaimer": "Measures what the paper reports (checklist coverage), not whether results actually reproduce.",
    }
