"""Held-out human audit: draw a blinded claim sample, and score it once a person has labelled it.

    python -m eval.held_out_audit sample eval/results/held_out          # writes held_out_audit.csv + held_out_audit_key.csv
    python -m eval.held_out_audit score  eval/results/held_out          # refuses until every row is labelled
    python -m eval.held_out_audit score  eval/results/held_out --second second_annotator.csv   # adds agreement

`sample` reads the frozen raw output (raw/real_papers_audit.csv), never the PDFs, and never overwrites an existing
sheet. The sheet shown to the labeller does NOT contain PaperLens's support rating or score, so labels cannot be
influenced by them; the ratings live in the key file and are joined back only when scoring.

Labels: is_real_claim  y / n
        evidence_correct  y / p / n   (only when is_real_claim = y and an evidence passage is shown; otherwise leave blank)
See AUDIT_INSTRUCTIONS.md in the same folder. This script computes nothing from unlabelled or partly labelled sheets.
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20261011
TARGET = 45
MIN_PER_PAPER = 3
LEVELS = ("strong", "moderate", "weak", "none")
SHEET_COLS = ["row", "paper_id", "paper_file", "claim_id", "claim_page", "claim", "evidence_page", "evidence",
              "is_real_claim", "evidence_correct", "notes"]


def _largest_remainder(weights: dict, total: int, floor: int = 0, caps: dict | None = None) -> dict:
    """Integer allocation proportional to weights, each at least `floor` and at most caps[k]."""
    caps = caps or {k: total for k in weights}
    alloc = {k: min(caps[k], floor) for k in weights}
    left = total - sum(alloc.values())
    wsum = sum(weights.values())
    ideal = {k: total * weights[k] / wsum for k in weights}
    while left > 0:
        room = [k for k in weights if alloc[k] < caps[k]]
        if not room:
            break
        k = max(room, key=lambda k: (ideal[k] - alloc[k], weights[k], str(k)))
        alloc[k] += 1
        left -= 1
    return alloc


def sample(folder: str):
    out = Path(folder)
    sheet, key = out / "held_out_audit.csv", out / "held_out_audit_key.csv"
    if sheet.exists() or key.exists():
        print(f"{sheet.name} or {key.name} already exists; refusing to overwrite (it may contain labels)")
        return 1
    rows = list(csv.DictReader(open(out / "raw" / "real_papers_audit.csv", encoding="utf-8-sig")))
    ids = {}
    manifest = Path("data/held_out_papers/MANIFEST.csv")
    if manifest.exists():
        ids = {r["filename"]: r["identifier"] for r in csv.DictReader(open(manifest, encoding="utf-8-sig"))}
    by_paper = defaultdict(list)
    for r in rows:
        by_paper[r["paper"]].append(r)
    rng = random.Random(SEED)
    quota = _largest_remainder({p: len(v) for p, v in by_paper.items()}, min(TARGET, len(rows)), MIN_PER_PAPER,
                               {p: len(v) for p, v in by_paper.items()})
    chosen = []
    for paper in sorted(by_paper):
        by_level = defaultdict(list)
        for r in by_paper[paper]:
            by_level[r["support"]].append(r)
        per_level = _largest_remainder({lv: len(v) for lv, v in by_level.items()}, quota[paper], 0,
                                       {lv: len(v) for lv, v in by_level.items()})
        for lv in sorted(by_level):
            chosen.extend(rng.sample(by_level[lv], per_level[lv]))
    chosen.sort(key=lambda r: (r["paper"], int(r["claim_page"]), int(r["claim_id"][1:])))
    with open(sheet, "w", newline="", encoding="utf-8-sig") as f, open(key, "w", newline="", encoding="utf-8-sig") as g:
        w = csv.DictWriter(f, fieldnames=SHEET_COLS)
        k = csv.DictWriter(g, fieldnames=["row", "paper_file", "claim_id", "support", "type", "claim_section", "evidence_section"])
        w.writeheader(); k.writeheader()
        for i, r in enumerate(chosen, 1):
            w.writerow({"row": i, "paper_id": ids.get(r["paper"], r["paper"]), "paper_file": r["paper"], "claim_id": r["claim_id"],
                        "claim_page": r["claim_page"], "claim": r["claim"], "evidence_page": r["evidence_page"],
                        "evidence": r["evidence"], "is_real_claim": "", "evidence_correct": "", "notes": ""})
            k.writerow({"row": i, "paper_file": r["paper"], "claim_id": r["claim_id"], "support": r["support"], "type": r["type"],
                        "claim_section": r["claim_section"], "evidence_section": r["evidence_section"]})
    info = {"seed": SEED, "target": TARGET, "min_per_paper": MIN_PER_PAPER, "population_claims": len(rows), "sampled": len(chosen),
            "method": "per-paper quota by largest remainder (proportional to claim count, floor 3); within each paper, "
                      "quota split across support levels by largest remainder; simple random draw inside each cell",
            "per_paper": {p: {"claims": len(by_paper[p]), "sampled": quota[p]} for p in sorted(by_paper)},
            "support_population": dict(Counter(r["support"] for r in rows)),
            "support_sample": dict(Counter(r["support"] for r in chosen))}
    (out / "held_out_sample_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info, indent=2))
    return 0


def _wilson(k: int, n: int) -> str:
    if not n:
        return "n/a"
    z, p = 1.96, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{p:.3f} ({k}/{n}; 95% CI {max(0, c - h):.2f}-{min(1, c + h):.2f})"


def _load(path: Path) -> tuple[list[dict], list[str]]:
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    problems = []
    for r in rows:
        a = r["is_real_claim"].strip().lower()
        e = r["evidence_correct"].strip().lower()
        r["is_real_claim"], r["evidence_correct"] = a, e
        if a not in ("y", "n"):
            problems.append(f"row {r['row']}: is_real_claim must be y or n (found '{a}')")
        elif a == "y" and r["evidence"].strip() and e not in ("y", "p", "n"):
            problems.append(f"row {r['row']}: evidence_correct must be y, p or n (found '{e}')")
        elif e and not (a == "y" and r["evidence"].strip()):
            problems.append(f"row {r['row']}: evidence_correct must be blank when the claim is not real or no evidence is shown")
    return rows, problems


def _kappa(a: list[str], b: list[str]) -> str:
    n = len(a)
    if not n:
        return "n/a"
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return f"agreement {po:.3f}, Cohen's kappa {'n/a (no variation)' if pe == 1 else f'{(po - pe) / (1 - pe):.3f}'} (n={n})"


def score(folder: str, second: str | None = None):
    out = Path(folder)
    rows, problems = _load(out / "held_out_audit.csv")
    if problems:
        print(f"NOT SCORED: {len(problems)} of {len(rows)} rows are unlabelled or invalid. No metric is computed from a "
              f"partly labelled sheet.")
        for p in problems[:10]:
            print("  " + p)
        return 1
    key = {r["row"]: r for r in csv.DictReader(open(out / "held_out_audit_key.csv", encoding="utf-8-sig"))}
    for r in rows:
        r["support"] = key[r["row"]]["support"]
    real = [r for r in rows if r["is_real_claim"] == "y"]
    ev = [r for r in real if r["evidence"].strip()]
    print(f"rows labelled: {len(rows)}")
    print("claim precision (extracted sentence is a real claim of the paper): " + _wilson(len(real), len(rows)))
    print("evidence precision, strict  (y):      " + _wilson(sum(r["evidence_correct"] == "y" for r in ev), len(ev)))
    print("evidence precision, lenient (y or p): " + _wilson(sum(r["evidence_correct"] in ("y", "p") for r in ev), len(ev)))
    print("end-to-end (real claim AND evidence y), over all rows: "
          + _wilson(sum(r["evidence_correct"] == "y" for r in ev), len(rows)))
    print("by PaperLens support level (real claims with evidence shown):")
    for lv in LEVELS:
        sub = [r for r in ev if r["support"] == lv]
        print(f"  {lv:9} strict " + _wilson(sum(r["evidence_correct"] == "y" for r in sub), len(sub)))
    print("  -> the ratings are only meaningful if strict precision falls from strong to weak")
    print("by paper (claim precision):")
    for p in sorted({r["paper_file"] for r in rows}):
        sub = [r for r in rows if r["paper_file"] == p]
        print(f"  {p[:44]:44} " + _wilson(sum(r["is_real_claim"] == "y" for r in sub), len(sub)))
    print("Sample is small; read the intervals, not the point estimates. Precision only: recall is not measured.")
    if second:
        rows2, problems2 = _load(Path(second))
        if problems2 or len(rows2) != len(rows):
            print("second annotator sheet is incomplete or a different size; agreement not computed")
            return 1
        print("inter-annotator, is_real_claim: " + _kappa([r["is_real_claim"] for r in rows], [r["is_real_claim"] for r in rows2]))
        both = [(a["evidence_correct"], b["evidence_correct"]) for a, b in zip(rows, rows2) if a["evidence_correct"] and b["evidence_correct"]]
        print("inter-annotator, evidence_correct (rows both labelled): " + _kappa([x for x, _ in both], [y for _, y in both]))
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "sample":
        sys.exit(sample(sys.argv[2]))
    if len(sys.argv) >= 3 and sys.argv[1] == "score":
        sys.exit(score(sys.argv[2], sys.argv[4] if len(sys.argv) >= 5 and sys.argv[3] == "--second" else None))
    print(__doc__)
