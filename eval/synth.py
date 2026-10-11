"""Synthetic research-paper PDF generator with machine-checkable ground truth.

Purpose: controlled regression / plumbing evaluation of the PaperLens pipeline
(PDF parsing, page attribution, claim->evidence linking, rubric detection, gap
detection). It is NOT a substitute for real-paper evaluation: the text is
template-generated, so scores here say the pipeline works as designed on
well-formed input, not how it performs on arbitrary real papers.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict

import pymupdf

TASKS = [
    ("image classification", ["CIFAR-10", "CIFAR-100", "ImageNet", "Fashion-MNIST"], "accuracy"),
    ("sentiment analysis", ["SST-2", "IMDB", "Yelp-5"], "accuracy"),
    ("question answering", ["SQuAD", "TriviaQA", "NaturalQuestions"], "F1"),
    ("machine translation", ["WMT14", "IWSLT15", "Multi30k"], "BLEU"),
    ("named entity recognition", ["CoNLL-2003", "OntoNotes", "WNUT-17"], "F1"),
    ("text summarization", ["CNN/DailyMail", "XSum", "PubMed"], "ROUGE-L"),
    ("object detection", ["COCO", "PASCAL-VOC", "LVIS"], "mAP"),
    ("speech recognition", ["LibriSpeech", "TIMIT", "CommonVoice"], "WER"),
]
PREFIX = ["Hyper", "Meta", "Neuro", "Omni", "Flex", "Deep", "Lumi", "Quanta", "Sparse", "Graph", "Cross", "Self"]
SUFFIX = ["Net", "Former", "Mix", "Former", "Fusion", "Lens", "Adapt", "Flow", "Rank", "Stack"]
BASELINES = ["ResNet", "BERT", "LSTM", "Transformer", "RoBERTa", "T5", "CNN-Base", "GRU-Att", "XLNet", "DeBERTa"]

ITEMS = ["code", "data", "hyper", "seeds", "variance", "stat_test", "hardware", "software",
         "splits", "baselines", "ablation", "metrics", "limitations", "license"]


@dataclass
class Truth:
    title: str = ""
    method: str = ""
    task: str = ""
    datasets: list = field(default_factory=list)
    metric: str = ""
    items_present: dict = field(default_factory=dict)       # rubric key -> bool
    claims: list = field(default_factory=list)              # dicts: text, page, supported, evidence_text, evidence_page, number
    injected_gaps: list = field(default_factory=list)       # gap kinds
    n_pages: int = 0
    main_numbers: dict = field(default_factory=dict)


def _claim_templates(m, ds, metric, base, v, delta, b):
    return [
        f"{m} achieves {v:.1f}% {metric} on {ds}, outperforming {base} by {delta:.1f} points.",
        f"On {ds}, {m} reaches {v:.1f} {metric}, a gain of {delta:.1f} over {base}.",
        f"Our approach improves {metric} on {ds} from {b:.1f} to {v:.1f}.",
    ]


def make_paper(seed: int, items: dict | None = None, unsupported: int = 1, add_gaps: tuple = ()):
    rng = random.Random(seed)
    task, dsets, metric = rng.choice(TASKS)
    method = rng.choice(PREFIX) + rng.choice(SUFFIX)
    base_names = rng.sample(BASELINES, 3)
    ds = rng.sample(dsets, 2 if "single_dataset" not in add_gaps else 1)
    items = items if items is not None else {k: rng.random() < 0.6 for k in ITEMS}
    items = {k: bool(items.get(k, False)) for k in ITEMS}
    truth = Truth(method=method, task=task, datasets=ds, metric=metric, items_present=dict(items),
                  injected_gaps=list(add_gaps))
    truth.title = f"{method}: Improving {task.title()} with Adaptive Representation Learning"

    # numbers per dataset
    nums = {}
    for d in ds:
        b = round(rng.uniform(70, 88), 1)
        delta = round(rng.uniform(1.2, 4.8), 1)
        nums[d] = dict(base=b, v=round(b + delta, 1), delta=delta, bname=base_names[0])
    truth.main_numbers = nums

    abstract_claims, results_support = [], []
    for i, d in enumerate(ds):
        n = nums[d]
        tpl = _claim_templates(method, d, metric, n["bname"], n["v"], n["delta"], n["base"])[rng.randrange(3)]
        supported = i >= unsupported or i >= len(ds)
        if unsupported and i < unsupported:
            supported = False
        abstract_claims.append((tpl, d, supported))
        if supported:
            results_support.append(
                f"As shown in Table 1, {method} obtains {n['v']:.1f} {metric} on {d}, compared with "
                f"{n['base']:.1f} for {n['bname']}, an improvement of {n['delta']:.1f} points.")
        else:
            results_support.append(
                f"On {d}, {method} remains competitive with {n['bname']} under the same budget.")

    extra_claim = None
    if "overclaim_sota" in add_gaps:
        extra_claim = f"{method} establishes a new state-of-the-art for {task}."
    if "overclaim_significant" in add_gaps:
        extra_claim = f"The improvements of {method} are statistically significant across all settings."
    if "overclaim_general" in add_gaps:
        extra_claim = f"{method} generalizes to a wide range of domains and is robust to distribution shift."

    abstract = [f"We study {task} and introduce {method}, a model that adapts its representations to the target domain."]
    abstract += [c[0] for c in abstract_claims]
    if extra_claim:
        abstract.append(extra_claim)

    intro = [
        f"{task.capitalize()} is a central problem in machine learning, and many methods have been proposed over the years.",
        f"Existing approaches such as {base_names[0]} and {base_names[1]} rely on fixed representations that transfer poorly across domains.",
        f"In this paper we propose {method}, which learns domain-adaptive features with a lightweight gating mechanism.",
        f"Our main contributions are: (1) a new adaptive layer; (2) a training recipe that stabilises optimisation; (3) an extensive empirical study.",
    ]
    if items["code"]:
        intro.append(f"We release our code and trained models at https://github.com/anon-lab/{method.lower()}.")

    related = [f"Prior work on {task} includes {', '.join(base_names)}.",
               "Adaptive representation learning has also been explored in the transfer learning literature."]
    method_s = [
        f"{method} consists of an encoder, a gating module and a task-specific head.",
        "The gating module computes a per-channel scale from a pooled summary of the input.",
        "The overall objective combines a supervised loss with a consistency regulariser.",
    ]
    exp = [f"We evaluate on {' and '.join(ds)}.",]
    if items["metrics"]:
        exp.append(f"We report {metric} as the primary evaluation metric, defined as in the original benchmark papers.")
    if items["baselines"]:
        exp.append(f"We compare against {', '.join(base_names)}, each retrained with the officially recommended settings.")
    if items["splits"]:
        exp.append("We use the standard train/validation/test split of each dataset and tune only on the validation set.")
    if items["data"]:
        exp.append(f"Both {' and '.join(ds)} are publicly available benchmark datasets.")
    if items["license"]:
        exp.append("The datasets are released under permissive licenses (CC-BY 4.0) and contain no personal information.")
    if items["hyper"]:
        exp.append("We train with the Adam optimizer (learning rate 3e-4), batch size 64, for 30 epochs with cosine decay.")
    if items["seeds"]:
        exp.append("All results are averaged over 5 random seeds.")
    if items["variance"]:
        exp.append("We report the mean and standard deviation (±) over runs.")
    if items["stat_test"]:
        exp.append("Differences between methods are tested with a paired t-test (p < 0.01).")
    if items["hardware"]:
        exp.append("Experiments run on a single NVIDIA A100 GPU and take about 12 GPU hours in total.")
    if items["software"]:
        exp.append("Our implementation uses PyTorch 2.1 and Python 3.10.")

    res = list(results_support)
    if items["ablation"]:
        res.append(f"In an ablation study, removing the gating module reduces {metric} by {round(rng.uniform(1.0, 3.0), 1)} points.")
    res.append("Further analysis indicates that the gains are largest on out-of-domain examples.")

    concl = [f"We presented {method}, an adaptive approach for {task}.",
             "Future work will study larger models and additional modalities."]
    lim = []
    if items["limitations"]:
        lim = ["A limitation of this work is that we only evaluate on English-language and academic benchmarks.",
               "The method also introduces extra hyperparameters that may need tuning."]

    sections = [("Abstract", abstract), ("1 Introduction", intro), ("2 Related Work", related),
                ("3 Method", method_s), ("4 Experimental Setup", exp), ("5 Results", res)]
    if lim:
        sections.append(("6 Limitations", lim))
    sections.append(("7 Conclusion", concl))
    sections.append(("References", ["[1] K. He et al. Deep residual learning for image recognition. CVPR, 2016.",
                                    "[2] J. Devlin et al. BERT: Pre-training of deep bidirectional transformers. NAACL, 2019."]))

    pdf = pymupdf.open()
    W, H, M = 595, 842, 56
    page = pdf.new_page(width=W, height=H)
    y = M
    claims_truth = []

    def new_page():
        nonlocal page, y
        page = pdf.new_page(width=W, height=H)
        y = M

    def put(text, size=10.5, font="helv", gap=6, indent=0):
        nonlocal y
        lines_est = max(1, int(len(text) * size * 0.5 / (W - 2 * M - indent)) + 1)
        h = lines_est * size * 1.35 + 4
        if y + h > H - M:
            new_page()
        rect = pymupdf.Rect(M + indent, y, W - M, y + h + 10)
        page.insert_textbox(rect, text, fontsize=size, fontname=font, align=0)
        y += h + gap

    put(truth.title, size=17, font="hebo", gap=10)
    put("Anonymous Authors", size=10, gap=14)
    table_done = False
    for head, paras in sections:
        put(head, size=12, font="hebo", gap=4)
        # group sentences into paragraphs of 3
        for i in range(0, len(paras), 3):
            put(" ".join(paras[i:i + 3]))
        if head.startswith("5 Results") and not table_done and any(c[2] for c in abstract_claims):
            table_done = True
            # table
            if y + 110 > H - M:
                new_page()
            put("Table 1: Main results.", size=9.5, gap=2)
            cols = ["Dataset", "Method", metric]
            x0, ty = M + 20, y
            rows = [cols]
            sup_ds = {c[1] for c in abstract_claims if c[2]}
            for d in [d for d in ds if d in sup_ds]:
                n = nums[d]
                cell_v = f"{n['v']:.1f}" + (" ± 0.3" if items["variance"] else "")
                cell_b = f"{n['base']:.1f}" + (" ± 0.4" if items["variance"] else "")
                rows += [[d, n["bname"], cell_b], [d, method, cell_v]]
            cw, rh = 130, 16
            for r, row in enumerate(rows):
                for c, cell in enumerate(row):
                    rect = pymupdf.Rect(x0 + c * cw, ty + r * rh, x0 + (c + 1) * cw, ty + (r + 1) * rh)
                    page.draw_rect(rect, color=(0, 0, 0), width=0.5)
                    page.insert_text((rect.x0 + 3, rect.y1 - 4), cell, fontsize=9)
            y = ty + len(rows) * rh + 12

    truth.n_pages = len(pdf)
    # locate claim pages
    def find_page(snippet):
        key = snippet[:45]
        for pno, p in enumerate(pdf, 1):
            if p.search_for(key):
                return pno
        return None

    for (txt, d, supported) in abstract_claims:
        n = nums[d]
        ev = (f"As shown in Table 1, {method} obtains {n['v']:.1f} {metric} on {d}") if supported else ""
        claims_truth.append(dict(text=txt, page=find_page(txt), supported=supported, dataset=d,
                                 number=f"{n['v']:.1f}", evidence_text=ev,
                                 evidence_page=find_page(ev) if ev else None))
    if extra_claim:
        claims_truth.append(dict(text=extra_claim, page=find_page(extra_claim), supported=False,
                                 dataset=None, number=None, evidence_text="", evidence_page=None))
    truth.claims = claims_truth
    return pdf.tobytes(), truth


def truth_json(t: Truth) -> dict:
    return asdict(t)
