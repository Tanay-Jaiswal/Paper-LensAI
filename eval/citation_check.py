"""Run the citation and reference checks over a folder of PDFs and print every finding, for checking by hand.

    python -m eval.citation_check data/cse_check_papers
    python -m eval.citation_check data/cse_check2_papers

Prints, per paper, the citation style found, how many entries and in-text citations were read, and each finding with
the text it quotes. It does not decide whether a finding is right: that needs a person (or is marked AI-checked).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from paperlens.citations import check_citations, reference_text  # noqa: E402
from paperlens.ingest import parse_pdf  # noqa: E402


def main(argv: list[str]) -> int:
    paths = [p for a in argv for p in (sorted(Path(a).glob("*.pdf")) if Path(a).is_dir() else [Path(a)])]
    totals = {"papers": 0, "checked": 0, "findings": 0}
    for p in paths:
        d = parse_pdf(p)
        d.source_name = p.name
        r = check_citations(d, reference_text(p))
        totals["papers"] += 1
        totals["checked"] += r["checked"]
        totals["findings"] += len(r["findings"])
        print(f"== {p.name}: {r['style']}, {r['n_entries']} entries, {r['n_citations']} citations, "
              f"checked={r['checked']} {r['counts']} {r['note']}")
        for f in r["findings"]:
            print(f"   {f['id']} {f['kind']} | {f['message']} | {f['quote'][:160]}")
    print(totals)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
