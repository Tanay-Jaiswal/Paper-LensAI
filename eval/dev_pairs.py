"""Development-set evidence audit: pool the top (claim, passage) pairs of two versions, label them once, score both.

    python -m eval.dev_pairs pool  <baseline_audit.csv> <new_audit.csv> <out_dir>   # writes dev_pairs_blank.csv (version hidden, shuffled)
    python -m eval.dev_pairs score <baseline_audit.csv> <new_audit.csv> <out_dir>   # needs dev_pairs_labelled.csv
    python -m eval.dev_pairs score-labelled <baseline_audit.csv> <new_audit.csv> <out_dir>
        # as score, but a returned pair that was never labelled (the code changed after the labels were locked) is
        # left out of precision and counted, with the range precision could take if it were labelled

The pooled sheet lists each distinct claim once (label is_real_claim) and each distinct (claim, top passage) pair once
(label evidence_correct), in random order and without saying which version produced a pair or how it was rated, so one
set of labels scores both versions. Labels follow eval/results/held_out/AUDIT_INSTRUCTIONS.md.
Development papers only. Whoever labels this sheet must say so when reporting: AI-assisted labels are not human precision.
"""
from __future__ import annotations

import csv
import hashlib
import math
import random
import sys
from pathlib import Path

SEED = 20261012


def _read(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def _cid(r):
    return hashlib.sha1((r["paper"] + "|" + r["claim"]).encode("utf-8")).hexdigest()[:10]


def _pid(r):
    return hashlib.sha1((r["paper"] + "|" + r["claim"] + "|" + r["evidence"]).encode("utf-8")).hexdigest()[:10]


def pool(base, new, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    target = out / "dev_pairs_blank.csv"
    if target.exists():
        print(f"{target} exists; not overwritten")
        return 1
    claims, pairs = {}, {}
    for r in _read(base) + _read(new):
        claims.setdefault(_cid(r), r)
        if r["evidence"].strip():
            pairs.setdefault(_pid(r), r)
    rows = [{"kind": "claim", "id": k, "paper": r["paper"], "claim_page": r["claim_page"], "claim": r["claim"],
             "evidence_page": "", "evidence": "", "label": "", "notes": ""} for k, r in claims.items()]
    rows += [{"kind": "pair", "id": k, "paper": r["paper"], "claim_page": r["claim_page"], "claim": r["claim"],
              "evidence_page": r["evidence_page"], "evidence": r["evidence"], "label": "", "notes": ""} for k, r in pairs.items()]
    random.Random(SEED).shuffle(rows)
    rows.sort(key=lambda r: r["kind"])      # claims first, then pairs; random within each
    with open(target, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    print(f"{len(claims)} distinct claims, {len(pairs)} distinct (claim, top passage) pairs -> {target} (seed {SEED})")
    return 0


def _wilson(k, n):
    if not n:
        return "n/a (0 rows)"
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{p:.3f} ({k}/{n}; 95% CI {max(0, c - h):.2f}-{min(1, c + h):.2f})"


def score(base, new, out_dir, allow_unlabelled=False):
    lab = {(r["kind"], r["id"]): r["label"].strip().lower() for r in _read(Path(out_dir) / "dev_pairs_labelled.csv")}
    bad = [k for k, v in lab.items() if v not in (("y", "n") if k[0] == "claim" else ("y", "p", "n", ""))]
    if bad or any(v == "" for k, v in lab.items() if k[0] == "claim"):
        print("NOT SCORED: unlabelled or invalid rows:", len(bad))
        return 1
    for name, path in (("baseline", base), ("new", new)):
        rows = _read(path)
        real = [r for r in rows if lab[("claim", _cid(r))] == "y"]
        ret = [r for r in real if r["evidence"].strip()]
        missing = [r for r in ret if lab.get(("pair", _pid(r)), "") == ""]
        if missing and not allow_unlabelled:
            print(f"NOT SCORED ({name}): {len(missing)} returned pairs of real claims have no label")
            return 1
        n_ret = len(ret)
        ret = [r for r in ret if lab.get(("pair", _pid(r)), "") != ""]
        y = sum(lab[("pair", _pid(r))] == "y" for r in ret)
        yp = sum(lab[("pair", _pid(r))] in ("y", "p") for r in ret)
        print(f"== {name}: {len(rows)} claims extracted, {len(real)} labelled real")
        print("  coverage (real claims with a returned passage): " + _wilson(n_ret, len(real)))
        if missing:
            k = len(missing)
            print(f"  UNLABELLED returned pairs left out of the precision rows below: {k}; with them strict precision "
                  f"would lie between {sum(lab[('pair', _pid(r))] == 'y' for r in ret) / n_ret:.3f} and "
                  f"{(sum(lab[('pair', _pid(r))] == 'y' for r in ret) + k) / n_ret:.3f}")
        print("  evidence precision, strict  (y):      " + _wilson(y, len(ret)))
        print("  evidence precision, lenient (y or p): " + _wilson(yp, len(ret)))
        print("  real claims with fully supporting evidence:  " + _wilson(y, len(real)))
        print(f"  returned passages labelled wrong (n): {len(ret) - yp}")
        for lv in ("strong", "moderate", "weak", "none"):
            sub = [r for r in ret if r["support"] == lv]
            if sub:
                print(f"    {lv:9} strict " + _wilson(sum(lab[('pair', _pid(r))] == 'y' for r in sub), len(sub)))
    b = {_cid(r): r for r in _read(base)}
    n = {_cid(r): r for r in _read(new)}
    drop = [k for k in b if lab[("claim", k)] == "y" and b[k]["evidence"].strip() and not n[k]["evidence"].strip()]
    gain = [k for k in b if lab[("claim", k)] == "y" and not b[k]["evidence"].strip() and n[k]["evidence"].strip()]
    same = sum(1 for k in b if lab[("claim", k)] == "y" and b[k]["evidence"].strip() and b[k]["evidence"] == n[k]["evidence"])
    print(f"== real claims: same top passage in both versions: {same}; passage only in the new version: {len(gain)}")
    kinds = {v: sum(lab[("pair", _pid(b[k]))] == v for k in drop) for v in ("y", "p", "n")}
    print(f"== abstentions introduced by the new version on real claims: {len(drop)} "
          f"(baseline passage was y: {kinds['y']}, p: {kinds['p']}, n: {kinds['n']})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] in ("pool", "score"):
        sys.exit({"pool": pool, "score": score}[sys.argv[1]](*sys.argv[2:]))
    if len(sys.argv) == 5 and sys.argv[1] == "score-labelled":
        sys.exit(score(*sys.argv[2:], allow_unlabelled=True))
    print(__doc__)
