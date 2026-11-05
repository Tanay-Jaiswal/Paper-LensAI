"""Controlled evaluation on synthetic papers with known ground truth.

    python -m eval.run_eval --n 60 --out eval/results

What this measures: whether the pipeline recovers facts that were deliberately
planted in generated PDFs (page attribution, claim->evidence linking, rubric
items, injected gaps). It does NOT measure performance on real papers; see
eval/scifact_eval.py and eval/audit.py for real-data protocols.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from synth import ITEMS, make_paper  # noqa: E402

from paperlens.pipeline import analyze_pdf  # noqa: E402
from paperlens.textutils import jaccard, tokenize  # noqa: E402

SCENARIOS = [
    # (name, kwargs-builder)
    ("clean", lambda r: dict(unsupported=0, add_gaps=())),
    ("one_unsupported", lambda r: dict(unsupported=1, add_gaps=())),
    ("overclaim_sota", lambda r: dict(unsupported=0, add_gaps=("overclaim_sota",))),
    ("overclaim_significant", lambda r: dict(unsupported=0, add_gaps=("overclaim_significant",))),
    ("overclaim_general_single", lambda r: dict(unsupported=0, add_gaps=("overclaim_general", "single_dataset"))),
]


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return round(p, 3), round(r, 3), round(f, 3)


def match_claim(pred_claims, truth_text):
    tt = set(tokenize(truth_text))
    best, bj = None, 0.0
    for c in pred_claims:
        j = jaccard(tt, set(tokenize(c.text)))
        if j > bj:
            best, bj = c, j
    return best if bj >= 0.8 else None


def run(n: int, seed: int):
    rng = random.Random(seed)
    tp = {k: 0 for k in ITEMS}; fp = dict(tp); fn = dict(tp)
    claim_found = claim_total = 0
    page_ok = page_total = 0
    ev_hit = ev_total = 0
    ev_page_ok = 0
    unsup_detect = unsup_total = 0
    sup_strong_or_mod = sup_total = 0
    extras = []
    gap_counts = {}
    for i in range(n):
        name, build = SCENARIOS[i % len(SCENARIOS)]
        kw = build(rng)
        items = {k: rng.random() < 0.55 for k in ITEMS}
        raw, truth = make_paper(seed * 1000 + i, items=items, **kw)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(raw)
        a = analyze_pdf(f.name)
        Path(f.name).unlink()
        status = {x["key"]: x["status"] for x in a.rubric["items"]}
        for k in ITEMS:
            pred = status[k] == "present"
            if pred and truth.items_present[k]: tp[k] += 1
            elif pred and not truth.items_present[k]: fp[k] += 1
            elif not pred and truth.items_present[k]: fn[k] += 1
        matched = 0
        for tc in truth.claims:
            claim_total += 1
            c = match_claim(a.claims, tc["text"])
            if not c:
                continue
            matched += 1
            claim_found += 1
            page_total += 1
            page_ok += int(c.page == tc["page"])
            if tc["supported"]:
                sup_total += 1
                sup_strong_or_mod += int(c.support in ("strong", "moderate"))
                ev_total += 1
                top = c.evidence[0] if c.evidence else None
                ok = any(tc["number"] and tc["number"] in e.quote and tc["dataset"] and tc["dataset"] in e.quote
                         or (tc["evidence_text"][:40] in e.quote) for e in c.evidence[:1])
                ev_hit += int(ok)
                ev_page_ok += int(bool(top) and top.page == tc["evidence_page"] or
                                  any(e.page == tc["evidence_page"] for e in c.evidence[:1]))
            else:
                unsup_total += 1
                unsup_detect += int(c.support in ("none", "weak"))
        extras.append(len(a.claims) - matched)
        kinds = {g.kind for g in a.gaps}
        T = truth.items_present
        g = kw["add_gaps"]
        has_unsup = any(not c["supported"] for c in truth.claims)           # includes planted overclaims
        has_unsup_num = any(not c["supported"] and c["number"] for c in truth.claims)
        expected = {
            "unsupported_claim": has_unsup,
            "number_not_in_results": has_unsup_num,
            "superlative_without_baselines": "overclaim_sota" in g and not T["baselines"],
            "superlative_unsupported": "overclaim_sota" in g and T["baselines"],
            "significance_without_test": "overclaim_significant" in g and not T["stat_test"],
            # rule: a generalisation phrase ("generalizes", "across all settings") with <=2 evaluation datasets;
            # the planted significance overclaim also says "across all settings", so it legitimately triggers it
            "generalization_narrow_evidence": "overclaim_general" in g or "overclaim_significant" in g,
            "improvement_without_variance": not T["variance"] and not T["seeds"],
            "no_code": not T["code"],
            "no_limitations": not T["limitations"],
            "no_hyperparameters": not T["hyper"],
        }
        for kind, exp in expected.items():
            c = gap_counts.setdefault(kind, {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
            got = kind in kinds
            c["tp" if got and exp else "fp" if got else "fn" if exp else "tn"] += 1
    per_item = {k: dict(zip(("precision", "recall", "f1"), prf(tp[k], fp[k], fn[k])), tp=tp[k], fp=fp[k], fn=fn[k])
                for k in ITEMS}
    micro = prf(sum(tp.values()), sum(fp.values()), sum(fn.values()))
    res = {
        "n_papers": n, "seed": seed,
        "scope": "synthetic template papers; plumbing/regression check, not real-world performance",
        "rubric": {"micro_precision": micro[0], "micro_recall": micro[1], "micro_f1": micro[2], "per_item": per_item},
        "claims": {
            "headline_claim_recall": round(claim_found / claim_total, 3) if claim_total else None,
            "claim_page_accuracy": round(page_ok / page_total, 3) if page_total else None,
            "extra_claims_per_paper": round(sum(extras) / len(extras), 2),
        },
        "evidence_linking": {
            "supported_claims": sup_total,
            "top1_evidence_hit_rate": round(ev_hit / ev_total, 3) if ev_total else None,
            "evidence_page_accuracy": round(ev_page_ok / ev_total, 3) if ev_total else None,
            "supported_rated_strong_or_moderate": round(sup_strong_or_mod / sup_total, 3) if sup_total else None,
            "unsupported_rated_none_or_weak": round(unsup_detect / unsup_total, 3) if unsup_total else None,
            "n_unsupported": unsup_total,
        },
        "gap_detection": {k: dict(zip(("precision", "recall", "f1"), prf(v["tp"], v["fp"], v["fn"])), **v)
                          for k, v in gap_counts.items()},
    }
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args()
    res = run(args.n, args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "synthetic.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
