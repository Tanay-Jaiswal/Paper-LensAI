"""Carry development labels from one version's claims to another's, conservatively (DEVELOPMENT papers only).

    python -m eval.claim_map map   <old_audit.csv> <new_audit.csv> <labels.csv> <out_dir>
    python -m eval.claim_map merge <labels.csv> <additions.csv> <out.csv>
    python -m eval.claim_map compare <old_audit.csv> <new_audit.csv> <labels.csv> <out.json>

Claim ids are not stable between runs (C1, C2 ... renumber), so a claim is identified by `sha1(paper | claim text)` exactly as
`eval.dev_pairs` does, and an evidence pair by `sha1(paper | claim | passage)`. A label is carried over **only** when that
identity is unchanged:

  identical          same paper and same claim text. Its claim label carries over. Its pair label carries over only if the
                     returned top passage is also unchanged; a different passage needs a fresh pair label.
  partially_changed  the texts differ but one contains the other, or they are >= 0.85 similar (a fragment completed, a clause added).
                     Nothing carries over: the claim needs a fresh claim label, and its pair a fresh pair label.
  materially_changed same paper, 0.5 to 0.85 similar. Reported as a candidate match only; nothing carries over.
  removed / added    no counterpart in the other version.

`map` writes <out_dir>/claim_map.csv (one row per old and per new claim), claim_map_summary.json and
needs_fresh_labels.csv (a blank sheet in the eval.dev_pairs format: only the claims and pairs that have no usable label).
`compare` scores both versions on exactly the claims that are identical in both (same denominators), and on each version's
whole claim set separately with the number of claims or returned passages that have no label; it refuses to print a
precision for a set that contains an unlabelled returned passage of a real claim.
`merge` appends the labelled additions to the original labels into a NEW file; the original label file is never modified and
a row id that already exists with a different label is refused. Labels must say who made them (the `notes` column).
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

PARTIAL = 0.85
MATERIAL = 0.50


def _read(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def cid(r):
    return hashlib.sha1((r["paper"] + "|" + r["claim"]).encode("utf-8")).hexdigest()[:10]


def pid(r):
    return hashlib.sha1((r["paper"] + "|" + r["claim"] + "|" + r["evidence"]).encode("utf-8")).hexdigest()[:10]


def alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKC", s).lower())


def relation(old_text: str, new_text: str) -> tuple[str, float]:
    a, b = alnum(old_text), alnum(new_text)
    if a == b:
        return "identical", 1.0
    ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    if (a in b or b in a) and min(len(a), len(b)) >= 0.4 * max(len(a), len(b)) or ratio >= PARTIAL:
        return "partially_changed", round(ratio, 3)
    if ratio >= MATERIAL:
        return "materially_changed", round(ratio, 3)
    return "unrelated", round(ratio, 3)


def build_map(old_rows, new_rows, labels):
    """Return (map_rows, summary, fresh_claims, fresh_pairs)."""
    new_by_c = {cid(r): r for r in new_rows}
    old_by_c = {cid(r): r for r in old_rows}
    used_new: set[str] = set()
    out = []
    for o in old_rows:
        oc = cid(o)
        n, rel, sim = None, "removed", 0.0
        if oc in new_by_c:
            n, rel, sim = new_by_c[oc], "identical", 1.0
        else:
            best = (0.0, None, "unrelated")
            for r in new_rows:
                if r["paper"] != o["paper"] or cid(r) in used_new or cid(r) in old_by_c:
                    continue
                rl, s = relation(o["claim"], r["claim"])
                if s > best[0] and rl != "unrelated":
                    best = (s, r, rl)
            if best[1] is not None:
                n, rel, sim = best[1], best[2], best[0]
        if n is not None:
            used_new.add(cid(n))
        old_claim_label = labels.get(("claim", oc), "")
        old_pair_label = labels.get(("pair", pid(o)), "") if o["evidence"].strip() else ""
        same_pair = n is not None and rel == "identical" and o["evidence"] == n["evidence"]
        out.append({
            "side": "old", "old_id": oc, "paper": o["paper"], "old_claim": o["claim"], "old_page": o["claim_page"],
            "old_claim_label": old_claim_label, "old_pair_label": old_pair_label,
            "relation": rel, "similarity": sim,
            "new_id": cid(n) if n else "", "new_claim": n["claim"] if n else "", "new_page": n["claim_page"] if n else "",
            "claim_label_carries": "yes" if rel == "identical" and old_claim_label else "no",
            "previous_evidence_judgment_valid": ("yes" if same_pair and old_pair_label else
                                                 "no_evidence_in_either" if rel == "identical" and not o["evidence"].strip()
                                                 and not n["evidence"].strip() else "no"),
            "fresh_claim_label_needed": "no" if rel == "identical" and old_claim_label else ("yes" if n else "n/a"),
            "fresh_pair_label_needed": ("no" if not (n and n["evidence"].strip()) or same_pair and old_pair_label
                                        or (rel == "identical" and old_claim_label == "n") else "yes") if n else "n/a",
        })
    for r in new_rows:
        if cid(r) not in used_new:
            out.append({"side": "new", "old_id": "", "paper": r["paper"], "old_claim": "", "old_page": "",
                        "old_claim_label": "", "old_pair_label": "", "relation": "added", "similarity": 0.0,
                        "new_id": cid(r), "new_claim": r["claim"], "new_page": r["claim_page"],
                        "claim_label_carries": "no", "previous_evidence_judgment_valid": "no",
                        "fresh_claim_label_needed": "yes",
                        "fresh_pair_label_needed": "yes" if r["evidence"].strip() else "no"})
    # what needs a fresh label, judged from the NEW rows: any new claim without a carried claim label, any returned pair without a label
    fresh_claims, fresh_pairs = {}, {}
    carried = {m["new_id"] for m in out if m["claim_label_carries"] == "yes"}
    for r in new_rows:
        c = cid(r)
        if c not in carried and ("claim", c) not in labels:
            fresh_claims[c] = r
        # a returned passage of a claim that is labelled "not a claim" is never scored, so it needs no label
        if r["evidence"].strip() and ("pair", pid(r)) not in labels and labels.get(("claim", c)) != "n":
            fresh_pairs[pid(r)] = r
    counts = {k: sum(1 for m in out if m["relation"] == k) for k in
              ("identical", "partially_changed", "materially_changed", "removed", "added")}
    summary = {"old_claims": len(old_rows), "new_claims": len(new_rows), **counts,
               "claim_labels_carried": sum(m["claim_label_carries"] == "yes" for m in out),
               "evidence_judgments_still_valid": sum(m["previous_evidence_judgment_valid"] == "yes" for m in out),
               "fresh_claim_labels_needed": len(fresh_claims), "fresh_pair_labels_needed": len(fresh_pairs)}
    return out, summary, fresh_claims, fresh_pairs


def cmd_map(old_path, new_path, labels_path, out_dir):
    labels = {(r["kind"], r["id"]): r["label"].strip().lower() for r in _read(labels_path)}
    out, summary, fc, fp = build_map(_read(old_path), _read(new_path), labels)
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "claim_map.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    (d / "claim_map_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    rows = [{"kind": "claim", "id": k, "paper": r["paper"], "claim_page": r["claim_page"], "claim": r["claim"],
             "evidence_page": "", "evidence": "", "label": "", "notes": ""} for k, r in fc.items()]
    rows += [{"kind": "pair", "id": k, "paper": r["paper"], "claim_page": r["claim_page"], "claim": r["claim"],
              "evidence_page": r["evidence_page"], "evidence": r["evidence"], "label": "", "notes": ""} for k, r in fp.items()]
    with open(d / "needs_fresh_labels.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["kind", "id", "paper", "claim_page", "claim", "evidence_page", "evidence", "label", "notes"])
        w.writeheader()
        w.writerows(rows)
    print(json.dumps(summary, indent=1))
    return 0


def cmd_merge(labels_path, add_path, out_path):
    base = _read(labels_path)
    have = {(r["kind"], r["id"]): r["label"].strip().lower() for r in base}
    add = _read(add_path)
    for r in add:
        key = (r["kind"], r["id"])
        if not r["label"].strip() or "AI-assisted" not in r.get("notes", ""):
            print(f"REFUSED: {key} is unlabelled or its notes do not say who labelled it")
            return 1
        if key in have and have[key] != r["label"].strip().lower():
            print(f"REFUSED: {key} already has label {have[key]!r}")
            return 1
    seen = set(have)
    rows = list(base) + [r for r in add if (r["kind"], r["id"]) not in seen]
    if Path(out_path).resolve() == Path(labels_path).resolve():
        print("REFUSED: the output must be a new file")
        return 1
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(base[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(base)} original rows + {len(rows) - len(base)} added -> {out_path}")
    return 0


def _wilson(k, n):
    import math
    if not n:
        return None
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(p, 3), round(max(0, c - h), 2), round(min(1, c + h), 2)]


def score_rows(rows, labels):
    """Coverage and evidence precision of `rows`; unlabelled items are counted, never guessed."""
    real = [r for r in rows if labels.get(("claim", cid(r))) == "y"]
    ret = [r for r in real if r["evidence"].strip()]
    lab = [r for r in ret if labels.get(("pair", pid(r)), "") != ""]
    y = sum(labels[("pair", pid(r))] == "y" for r in lab)
    yp = sum(labels[("pair", pid(r))] in ("y", "p") for r in lab)
    out = {"claims": len(rows), "claims_without_label": sum(("claim", cid(r)) not in labels for r in rows),
           "real_claims": len(real), "returned": len(ret), "returned_without_label": len(ret) - len(lab),
           "labelled_returned": len(lab), "strict_y": y, "lenient_yp": yp}
    if len(ret) == len(lab) and out["claims_without_label"] == 0:
        out["strict"], out["lenient"] = _wilson(y, len(lab)), _wilson(yp, len(lab))      # [value, ci_low, ci_high]
        out["coverage"] = _wilson(len(ret), len(real))
    else:
        out["strict"] = out["lenient"] = out["coverage"] = "not computed: unlabelled items remain"
    return out


def cmd_compare(old_path, new_path, labels_path, out_path):
    labels = {(r["kind"], r["id"]): r["label"].strip().lower() for r in _read(labels_path)}
    old, new = _read(old_path), _read(new_path)
    common = {cid(r) for r in old} & {cid(r) for r in new}
    res = {"common_claims": len(common),
           "common_set": {"old": score_rows([r for r in old if cid(r) in common], labels),
                          "new": score_rows([r for r in new if cid(r) in common], labels)},
           "whole_old": score_rows(old, labels), "whole_new": score_rows(new, labels),
           "same_top_passage_on_common": sum(1 for o in old for n in new
                                             if cid(o) == cid(n) and cid(o) in common and o["evidence"] == n["evidence"])}
    Path(out_path).write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "map":
        sys.exit(cmd_map(*sys.argv[2:]))
    if len(sys.argv) == 5 and sys.argv[1] == "merge":
        sys.exit(cmd_merge(*sys.argv[2:]))
    if len(sys.argv) == 6 and sys.argv[1] == "compare":
        sys.exit(cmd_compare(*sys.argv[2:]))
    print(__doc__)
