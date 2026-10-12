"""Second held-out audit (PaperLens 0.2.0-dev): blinded sample, automatic measures, and scoring of human labels.

    python -m eval.held_out_v2 sample <folder>     # sheet for the annotator; key and sample description go to sealed_key/
    python -m eval.held_out_v2 auto   <folder>     # automatic measures over all extracted claims (no labels needed)
    python -m eval.held_out_v2 score  <folder> [--second second_annotator.csv]    # refuses until every row is labelled

Procedure and metric definitions: eval/results/held_out_v0.2/PROTOCOL.md. Sampling and label checks are those of
eval/held_out_audit.py (used unchanged for the first held-out audit), with a larger target and a new seed.
Nothing here writes a label. `score` computes nothing from an unlabelled or partly labelled sheet.
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import held_out_audit as H  # noqa: E402

SEED = 20261012
TARGET = 60
SEALED = "sealed_key"
KEY_FILES = ("held_out_audit_key.csv", "held_out_sample_info.json")


def sample(folder: str) -> int:
    out = Path(folder)
    if (out / SEALED).exists() or (out / "held_out_audit.csv").exists():
        print("a sheet or sealed key already exists in this folder; refusing to overwrite (it may contain labels)")
        return 1
    H.SEED, H.TARGET = SEED, TARGET
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):      # the sample description shows the support mix: keep it off screen
        rc = H.sample(folder)
    if rc:
        return rc
    (out / SEALED).mkdir()
    for name in KEY_FILES:
        shutil.move(str(out / name), str(out / SEALED / name))
    n = sum(1 for _ in csv.DictReader(open(out / "held_out_audit.csv", encoding="utf-8-sig")))
    print(f"{n} rows -> {out / 'held_out_audit.csv'} (blank labels); key and sample description sealed in {out / SEALED}")
    return 0


def auto(folder: str) -> int:
    out = Path(folder)
    rows = list(csv.DictReader(open(out / "raw" / "real_papers_audit.csv", encoding="utf-8-sig")))
    summ = json.loads((out / "raw" / "real_papers_summary.json").read_text(encoding="utf-8"))
    n = len(rows)
    st = Counter(r["evidence_status"] for r in rows)
    print(f"papers run: {len(summ)}; crashed: {sum('error' in p for p in summ)}; extracted claims: {n}")
    if not n:
        return 0
    print("AUTOMATIC measures over all extracted claims (how often PaperLens answers, not whether it is right)")
    print("  coverage (claims with a returned passage):       " + H._wilson(st["found"], n))
    print("  abstention rate (no supporting evidence found):  " + H._wilson(st["no_supporting_evidence"], n))
    print("  unsearchable rate (no body text extracted):      " + H._wilson(st["no_searchable_text"], n))
    sup = Counter(r["support"] for r in rows)
    print("  support strong / moderate / weak / none:         " + " / ".join(str(sup[k]) for k in H.LEVELS))
    cp = Counter(r["auto_claim_on_cited_page"] for r in rows)
    ep = Counter(r["auto_evidence_on_cited_page"] for r in rows if r["evidence"].strip())
    print(f"  claim text found on its cited page:              {dict(cp)}")
    print(f"  top evidence quote found on its cited page:      {dict(ep)}")
    print("per paper: pages, claims, with passage, abstained, strong/moderate/weak/none, warnings")
    for p in summ:
        if "error" in p:
            print(f"  {p['paper'][:52]:52} CRASHED: {p['error']}")
            continue
        es, s = p.get("evidence_status", {}), p.get("support", {})
        print(f"  {p['paper'][:52]:52} {p['pages_pymupdf']:3} {p['n_claims']:3} {es.get('found', 0):3} "
              f"{es.get('no_supporting_evidence', 0) + es.get('no_searchable_text', 0):3}  "
              + "/".join(str(s.get(k, 0)) for k in H.LEVELS) + f"  {len(p.get('warnings', []))} warning(s)")
    return 0


def score(folder: str, second: str | None = None) -> int:
    out = Path(folder)
    rows, problems = H._load(out / "held_out_audit.csv")
    if problems:
        print(f"NOT SCORED: {len(problems)} of {len(rows)} rows are unlabelled or invalid. No metric is computed from a "
              f"partly labelled sheet.")
        for p in problems[:10]:
            print("  " + p)
        return 1
    with tempfile.TemporaryDirectory() as tmp:           # the scorer of the first audit expects sheet and key side by side
        shutil.copy(out / "held_out_audit.csv", tmp)
        shutil.copy(out / SEALED / "held_out_audit_key.csv", tmp)
        rc = H.score(tmp, second)
    real = [r for r in rows if r["is_real_claim"] == "y"]
    shown = [r for r in real if r["evidence"].strip()]
    print("coverage on real claims (shown with a passage):        " + H._wilson(len(shown), len(real)))
    print("abstention rate on real claims (shown without one):    " + H._wilson(len(real) - len(shown), len(real)))
    print("Whether an abstention was right is not measured: the sheet does not ask the annotator to search the paper.")
    return rc


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) == 2 and a[0] in ("sample", "auto"):
        sys.exit({"sample": sample, "auto": auto}[a[0]](a[1]))
    if len(a) >= 2 and a[0] == "score":
        sys.exit(score(a[1], a[3] if len(a) >= 4 and a[2] == "--second" else None))
    print(__doc__)
    sys.exit(2)
