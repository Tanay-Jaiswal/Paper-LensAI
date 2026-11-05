"""Real-data evaluation on SciFact (Wadden et al., EMNLP 2020), dev split.

    python -m eval.scifact_eval --download            # fetch + extract data (needs internet)
    python -m eval.scifact_eval --data-dir data/scifact --out eval/results

SciFact: 1,409 expert-written scientific claims paired with evidence abstracts
(SUPPORT / CONTRADICT rationales, or NOT-ENOUGH-INFO). We use it to test the two
sub-tasks PaperLens depends on, on real scientific text:

 1. Rationale selection  - given a claim and its cited abstract, does the evidence
    scorer rank a gold rationale sentence at the top? (hit@1, hit@3, MRR)
 2. Evidence-gap detection - does the best passage score separate claims that
    DO have rationale in the cited abstract from NOT-ENOUGH-INFO claims? (AUROC)
 3. Abstract retrieval   - BM25 over the corpus: recall@10 / @100 of cited docs.

Baselines are reported next to the PaperLens scorer so the numbers can be read in
context: random order, first-sentence, and plain BM25 (no numeric agreement).
Nothing here is hard-coded; numbers are produced by running the script.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import tarfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paperlens.claims import rank_passages  # noqa: E402
from paperlens.models import Sentence  # noqa: E402
from paperlens.textutils import BM25, numbers_in, tokenize  # noqa: E402

URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"


def download(dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    tgz = dest / "data.tar.gz"
    print("downloading", URL)
    urllib.request.urlretrieve(URL, tgz)
    with tarfile.open(tgz) as t:
        for m in t.getmembers():
            name = Path(m.name).name
            if m.isfile() and name.endswith(".jsonl"):
                m.name = name
                t.extract(m, dest)
    print("extracted to", dest)


def read_jsonl(p: Path):
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def auroc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney AUROC with tie handling."""
    if not pos or not neg:
        return float("nan")
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks, i = {}, 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        for k in range(i, j):
            ranks[k] = (i + j + 1) / 2
        i = j
    rsum = sum(ranks[k] for k, (_, lab) in enumerate(allv) if lab == 1)
    n1, n0 = len(pos), len(neg)
    return (rsum - n1 * (n1 + 1) / 2) / (n1 * n0)


def abstract_sentences(doc) -> list[Sentence]:
    return [Sentence(i, t, 1, "results") for i, t in enumerate(doc["abstract"])]


def run(data_dir: Path, limit: int | None = None, seed: int = 0, retrieval: bool = True) -> dict:
    corpus = {d["doc_id"]: d for d in read_jsonl(data_dir / "corpus.jsonl")}
    claims = read_jsonl(data_dir / "claims_dev.jsonl")
    if limit:
        claims = claims[:limit]
    rng = random.Random(seed)

    hit = {m: {1: 0, 3: 0, "mrr": 0.0} for m in ("paperlens", "bm25_only", "first_sentence", "random")}
    n_rat = 0
    pos_scores, neg_scores = [], []
    for c in claims:
        nums = numbers_in(c["claim"])
        for did_str, ev_list in (c.get("evidence") or {}).items():
            gold = {i for e in ev_list for i in e["sentences"]}
            doc = corpus[int(did_str)]
            sents = abstract_sentences(doc)
            if not gold or not sents:
                continue
            n_rat += 1
            orders = {}
            orders["paperlens"] = [x[3].id for x in rank_passages(c["claim"], nums, sents)]
            q = tokenize(c["claim"])
            bm = BM25([tokenize(s.text) for s in sents])
            orders["bm25_only"] = [i for i, _ in sorted(((i, bm.score(q, i)) for i in range(len(sents))), key=lambda x: -x[1])]
            orders["first_sentence"] = list(range(len(sents)))
            rnd = list(range(len(sents))); rng.shuffle(rnd); orders["random"] = rnd
            for m, order in orders.items():
                rank = next((r for r, i in enumerate(order, 1) if i in gold), None)
                if rank:
                    hit[m]["mrr"] += 1 / rank
                    for k in (1, 3):
                        hit[m][k] += int(rank <= k)
        # evidence-gap detection: best passage score over cited abstracts
        cited = c.get("cited_doc_ids") or []
        best = 0.0
        for did in cited:
            if did in corpus:
                r = rank_passages(c["claim"], nums, abstract_sentences(corpus[did]))
                if r:
                    best = max(best, r[0][0])
        if cited:
            (pos_scores if c.get("evidence") else neg_scores).append(best)
    rat_summary = ({m: {"hit@1": round(v[1] / n_rat, 3), "hit@3": round(v[3] / n_rat, 3),
                        "mrr": round(v["mrr"] / n_rat, 3)} for m, v in hit.items()} if n_rat else {})
    res = {
        "dataset": "SciFact dev", "n_claims": len(claims),
        "rationale_selection": {
            "n_claim_abstract_pairs": n_rat,
            **rat_summary,
        },
        "evidence_gap_detection": {
            "n_with_evidence": len(pos_scores), "n_not_enough_info": len(neg_scores),
            "auroc_evidence_present_vs_NEI": round(auroc(pos_scores, neg_scores), 3) if pos_scores and neg_scores else None,
        },
    }
    if retrieval:
        ids = list(corpus)
        bm = BM25([tokenize(corpus[i]["title"] + " " + " ".join(corpus[i]["abstract"])) for i in ids])
        r10 = r100 = n = 0
        for c in claims:
            gold = {int(d) for d in (c.get("evidence") or {})}
            if not gold:
                continue
            n += 1
            ranked = [ids[i] for i, _ in bm.rank(tokenize(c["claim"]), k=100)]
            r10 += int(bool(gold & set(ranked[:10])))
            r100 += int(bool(gold & set(ranked[:100])))
        res["abstract_retrieval_bm25"] = {"n": n, "recall@10": round(r10 / n, 3), "recall@100": round(r100 / n, 3)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/scifact")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no-retrieval", action="store_true")
    ap.add_argument("--out", default="eval/results")
    args = ap.parse_args()
    d = Path(args.data_dir)
    if args.download:
        download(d)
    res = run(d, args.limit, retrieval=not args.no_retrieval)
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / "scifact_dev.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
