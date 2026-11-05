"""Precision vs coverage of the evidence linker's abstention threshold, on human-labelled SciFact data.

    python -m eval.abstention_curve --split train          # used to CHOOSE claims.MIN_LEXICAL
    python -m eval.abstention_curve --split dev            # check only, not used for tuning

Each claim is paired with each abstract it cites. The linker (claims.select_passages: suitability filter, quantity
matching and the relevance test) is run over the abstract's sentences.
  returned  = the linker returned a top passage for the pair
  correct   = that passage is one of the expert-marked rationale sentences for the pair
  A pair with no rationale (the abstract does not address the claim) can only be answered correctly by abstaining.
coverage  = returned / all pairs;   precision = correct / returned;
recall    = correct / pairs that have a rationale.

Limits: abstracts have ~9 sentences, so BM25 statistics differ from a full paper; "correct" means "is a rationale
sentence", not "fully supports the claim"; SciFact is biomedical. The curve guides the threshold, it does not certify it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paperlens import claims as C  # noqa: E402
from paperlens.models import Sentence  # noqa: E402
from paperlens.textutils import numbers_in  # noqa: E402

GRID = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]


def read_jsonl(p: Path):
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def pairs(data_dir: Path, split: str):
    corpus = {d["doc_id"]: d for d in read_jsonl(data_dir / "corpus.jsonl")}
    for c in read_jsonl(data_dir / f"claims_{split}.jsonl"):
        ev = c.get("evidence") or {}
        for did in c.get("cited_doc_ids") or []:
            if did not in corpus:
                continue
            gold = {i for e in ev.get(str(did), []) for i in e["sentences"]}
            sents = [Sentence(i, t, 1, "results") for i, t in enumerate(corpus[did]["abstract"])]
            if sents:
                yield c["claim"], sents, gold


def measure(data_dir: Path, split: str, min_lex: float, min_lex_q: float) -> dict:
    n = returned = correct = answerable = 0
    for claim, sents, gold in pairs(data_dir, split):
        n += 1
        answerable += bool(gold)
        best, _ = C.select_passages(claim, numbers_in(claim), sents, 1, min_lex, min_lex_q)
        if best:
            returned += 1
            correct += best[0][3].id in gold
    return {"min_lexical": min_lex, "min_lexical_with_quantity": min_lex_q, "pairs": n, "pairs_with_rationale": answerable,
            "returned": returned, "correct": correct, "coverage": round(returned / n, 3),
            "precision": round(correct / returned, 3) if returned else None,
            "recall": round(correct / answerable, 3) if answerable else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/scifact")
    ap.add_argument("--split", default="train", choices=["train", "dev"])
    ap.add_argument("--out", default="eval/results/dev_v0.2")
    args = ap.parse_args()
    d = Path(args.data_dir)
    rows = [measure(d, args.split, t, min(t, C.MIN_LEXICAL_WITH_QUANTITY)) for t in GRID]
    chosen = measure(d, args.split, C.MIN_LEXICAL, C.MIN_LEXICAL_WITH_QUANTITY)
    res = {"dataset": f"SciFact {args.split}", "note": "top passage vs expert rationale sentences; see module docstring",
           "curve": rows, "at_module_constants": chosen}
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / f"abstention_curve_scifact_{args.split}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"{'min_lex':>8} {'coverage':>9} {'precision':>10} {'recall':>7} {'returned':>9} {'correct':>8}")
    for r in rows + [chosen]:
        print(f"{r['min_lexical']:>8} {r['coverage']:>9} {r['precision']!s:>10} {r['recall']!s:>7} {r['returned']:>9} {r['correct']:>8}")
    print("last row = current module constants; pairs:", chosen["pairs"], "with rationale:", chosen["pairs_with_rationale"])


if __name__ == "__main__":
    main()
