"""Build the built-in CS reference set used by the CS comparison view (paperlens/data/cs_reference.json).

    python -m eval.build_cs_reference                 # default development papers (see DEFAULT_SOURCES)
    python -m eval.build_cs_reference a.pdf b.pdf     # or name the PDFs

Only papers that PaperLens detects as Computer Science in automatic mode are kept, and only summary numbers are stored
(checklist item statuses, scores, grade), never paper text. Papers in a held-out set or in the frozen second CSE check
set are refused, so the comparison set never touches evaluation data.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from paperlens import __version__  # noqa: E402
from paperlens.benchmark import REFERENCE_FILE, profile  # noqa: E402
from paperlens.pipeline import analyze_pdf  # noqa: E402
from paperlens.scorecard import build_scorecard  # noqa: E402

PROTECTED_MANIFESTS = ["data/held_out_papers/MANIFEST.csv", "data/held_out_v0.2_papers/MANIFEST.csv",
                       "data/cse_check2_papers/MANIFEST.csv"]


def protected_names() -> set[str]:
    names = set()
    for m in PROTECTED_MANIFESTS:
        f = ROOT / m
        if f.exists():
            with f.open(encoding="utf-8-sig") as fh:
                names |= {r["filename"] for r in csv.DictReader(fh)}
    return names


def default_sources() -> list[tuple[Path, str]]:
    """Development CS papers: the first CSE check set and the development papers kept in data/store."""
    out = [(p, p.name) for p in sorted((ROOT / "data" / "cse_check_papers").glob("*.pdf"))]
    store = ROOT / "data" / "store"
    if store.exists():
        for d in sorted(store.iterdir()):
            name_f = d / "name.txt"
            if (d / "paper.pdf").exists() and name_f.exists():
                name = Path(name_f.read_text(encoding="utf-8").replace("\\", "/")).name
                if name.startswith(("arxiv_", "acl_")):
                    out.append((d / "paper.pdf", name))
    return out


def main(argv: list[str]) -> int:
    sources = [(Path(a), Path(a).name) for a in argv] if argv else default_sources()
    blocked = protected_names()
    papers, seen, skipped = [], set(), []
    for path, name in sources:
        if name in blocked or "held_out" in str(path) or "cse_check2" in str(path):
            skipped.append((name, "protected evaluation paper"))
            continue
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        if sha in seen:
            continue
        seen.add(sha)
        a = analyze_pdf(path, mode="auto")
        a.doc.source_name = name
        d = a.to_dict()
        d["scorecard"] = build_scorecard(a)
        p = profile(d)
        if p is None:
            skipped.append((name, f"not detected as CS ({a.mode['field']})"))
            continue
        p["sha256"] = sha
        papers.append(p)
        print(f"  kept {name}: score {p['score']}, grade {p['grade']}")
    for name, why in skipped:
        print(f"  skipped {name}: {why}")
    REFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_FILE.write_text(json.dumps({
        "version": __version__, "built": date.today().isoformat(), "n": len(papers),
        "note": "Development CS papers only (no held-out or frozen check papers); summary numbers, no paper text.",
        "papers": papers}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {REFERENCE_FILE.relative_to(ROOT)} with {len(papers)} papers")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
