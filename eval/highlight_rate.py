"""How often PaperLens can place a claim or evidence passage on its PDF page (development papers only).

    python -m eval.highlight_rate                      # data/cse_check_papers and development papers in data/store
    python -m eval.highlight_rate a.pdf b.pdf

Counts, for every claim sentence and every evidence passage the ledger returns, whether highlight.locate found it
exactly, in part, or not at all. It measures locating, not whether the evidence is right.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.build_cs_reference import default_sources, protected_names  # noqa: E402
from paperlens.highlight import locate_sentences  # noqa: E402
from paperlens.pipeline import analyze_pdf  # noqa: E402


def main(argv: list[str]) -> int:
    sources = [(Path(a), Path(a).name) for a in argv] if argv else default_sources()
    blocked = protected_names()
    total = {"claim": Counter(), "evidence": Counter()}
    for path, name in sources:
        if name in blocked:
            continue
        a = analyze_pdf(path)
        by_id = {s.id: s for s in a.doc.sentences}
        for kind, sids in (("claim", [c.sentence_id for c in a.claims]),
                           ("evidence", [e.sentence_id for c in a.claims for e in c.evidence])):
            res = locate_sentences(path, [by_id[i] for i in sids if i in by_id])
            c = Counter(r["method"] for r in res)
            total[kind] += c
        print(f"  {name[:70]}")
    for kind, c in total.items():
        n = sum(c.values())
        print(f"{kind}: {n} passages; exact {c['exact']} ({100 * c['exact'] / n:.0f}%), partial {c['partial']} "
              f"({100 * c['partial'] / n:.0f}%), not located {c['none']} ({100 * c['none'] / n:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
