"""Where does tabular text end up? Sentence-level counts on the DEVELOPMENT papers (no labels involved).

    python -m eval.table_text_dev data/Papers <out.json>

Set PAPERLENS_SRC to a folder holding another copy of the `paperlens` package to count for that version instead
(the previous commit: `git archive <commit> paperlens | tar -x -C <folder>`).

Per paper: sentences by kind; `number_run_prose` = sentences of kind text, outside the references and front matter,
that contain a run of four or more purely numeric tokens (the signature of table or axis text read as prose; a
citation list such as "[27, 29, 32, 35]" also matches, so the count is an upper bound, not an error count);
rows the parser marked "Table row / header / text"; warnings. Only counts are stored, no text of the papers.
Automatic counts only: they say nothing about whether a row was read correctly. Do not point this at held-out papers.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.environ.get("PAPERLENS_SRC") or str(Path(__file__).resolve().parent.parent))
import paperlens  # noqa: E402
from paperlens.ingest import parse_pdf  # noqa: E402

_NUM = re.compile(r"[\d.,%±+\-–−()/:*†‡x×]+")


def number_run(text: str, n: int = 4) -> bool:
    toks = text.split()
    if len(toks) < 8:
        return False
    run = best = 0
    for t in toks:
        if _NUM.fullmatch(t) and re.search(r"\d", t):
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best >= n


def main(folder: str, out: str) -> int:
    res, tot = {}, Counter()
    for pdf in sorted(Path(folder).glob("*.pdf")):
        doc = parse_pdf(pdf)
        kinds = Counter(s.kind for s in doc.sentences)
        sus = [s.text for s in doc.sentences if s.kind == "text" and s.section not in ("references", "front") and number_run(s.text)]
        marked = Counter(s.text.split(":")[0] for s in doc.sentences if s.kind in ("table", "meta") and s.text.startswith("Table "))
        res[pdf.name] = {"kinds": dict(kinds), "number_run_prose": len(sus), "marked_rows": dict(marked), "warnings": doc.warnings}
        tot.update({f"kind_{k}": v for k, v in kinds.items()})
        tot["number_run_prose"] += len(sus)
        tot["papers_with_table_warning"] += any("row labels" in w for w in doc.warnings)
        print(f"{pdf.name[:46]:46} text {kinds['text']:5} table {kinds['table']:4} meta {kinds['meta']:4} caption {kinds['caption']:3}"
              f"  number-run prose {len(sus):3}")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps({"version": paperlens.__version__, "total": dict(tot), "papers": res}, ensure_ascii=False),
                         encoding="utf-8")
    print(f"paperlens {paperlens.__version__}: {dict(tot)}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
