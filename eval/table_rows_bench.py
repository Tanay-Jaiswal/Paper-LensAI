"""Row-level benchmark on real tables of the DEVELOPMENT papers (annotations: eval/table_truth/, protocol: PROTOCOL.md there).

    python -m eval.table_rows_bench check                      # every annotated cell must occur in the PDF text layer of its table region
    python -m eval.table_rows_bench score <out.json>           # score the parser against the annotations
    python -m eval.table_rows_bench sheet <out.md>             # a sheet for a person to verify or correct the annotations
    python -m eval.table_rows_bench render <folder>            # page-image crops of the tables (for the person; not committed)

PAPERLENS_SRC=<folder holding another copy of the `paperlens` package> scores that version instead
(`git archive <commit> paperlens | tar -x -C <folder>`); the working tree is not touched.

What the parser returns for a table is every sentence on the table's page that starts with "Table row:", "Table header:"
or "Table text:"; its cells are the parts between "; ", with or without a leading "column head: ". Text is compared
after NFKC, lower-casing, removing white space and unifying dashes (strict); the lenient comparison also ignores the
footnote marks * † ‡ and free-standing accent marks. Each annotated cell is in the PDF's text-layer form, so super- and
subscripts and mis-mapped glyphs that no text parser can recover are not counted against the parser.

Per annotated data row (rows marked ambiguous are scored but kept out of every denominator):
  exact          one parser row of kind `table` holds exactly the annotated non-empty cells, in order, and nothing else
  exact_unusable the same, but the parser row is kind `meta` (kept, never used as evidence: usually no row label seen)
  merged         a parser row holds all the row's cells in order plus further cells (another row or other text)
  split          no parser row holds all the cells, but two or three parser rows together hold them all
  partial        the best parser row holds at least two of the cells (one, for a row of one or two cells), not all
  missing        none of the above; `glued` if the first two cells stand run together in a prose or caption sentence
Measures (denominators in brackets):
  exact_row_accuracy   exact / annotated data rows                      [non-ambiguous data rows]
  usable_or_exact      (exact + exact_unusable) / annotated data rows
  cell_accuracy        annotated non-empty cells found, in order, in the single best parser row of their row / cells
                       [non-empty cells of non-ambiguous data rows]
  header_row_recall    annotated header rows returned as one "Table header" with exactly their non-empty cells / header rows
  head_errors          column heads attached to a value ("EM: 81.2") that are not a head of that value's column /
                       heads attached to matched values; head_coverage = correctly headed values / annotated values
                       that have a column head (row labels excluded)
Not measured: table boundaries as boxes, cell alignment to columns beyond the attached heads, anything on unseen papers.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get("PAPERLENS_SRC") or str(ROOT))
TRUTH = ROOT / "eval" / "table_truth" / "tables.json"
PAPERS = ROOT / "data" / "Papers"
_DASH = str.maketrans({c: "-" for c in "−–—‐‑‒"})
_MARKS = re.compile(r"[*†‡¯˙.´`^~]")           # lenient: footnote marks and free-standing accents; "." only via _lenient
OUTCOMES = ["exact", "exact_unusable", "merged", "split", "partial", "missing"]


def norm(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s).translate(_DASH).lower())


def lenient(s: str) -> str:
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return re.sub(r"[*†‡¯˙´`]", "", norm(s))


def load() -> dict:
    return json.loads(TRUTH.read_text(encoding="utf-8"))


def cell_text(c) -> str:
    return c["t"] if isinstance(c, dict) else c


def expand(row: list) -> list[str]:
    """Cells laid out on the column grid: a cell spanning k columns sits in its first column, the others are ''."""
    out = []
    for c in row:
        out.append(cell_text(c))
        out += [""] * ((c.get("span", 1) - 1) if isinstance(c, dict) else 0)
    return out


def column_heads(table: dict) -> list[set]:
    """For every column: the header texts that stand over it, at any level (normalised, lenient)."""
    n = max([len(expand(r)) for r in table["header_rows"]] + [len(expand(r["cells"])) for r in table["rows"]])
    heads = [set() for _ in range(n)]
    for hr in table["header_rows"]:
        col = 0
        for c in hr:
            span = c.get("span", 1) if isinstance(c, dict) else 1
            if cell_text(c):
                for k in range(col, min(n, col + span)):
                    heads[k].add(lenient(cell_text(c)))
            col += span
    return heads


def region(table: dict):
    """(page object owner, bbox) of the table from its anchors; the document stays open for the caller."""
    import pymupdf
    doc = pymupdf.open(PAPERS / table["paper"])
    pg = doc[table["page"] - 1]
    a = table["anchors"]
    x0, x1 = a["x"]
    floor = 0.0
    if a.get("top_after"):
        floor = max(r.y1 for r in pg.search_for(a["top_after"]))
    tops = [r for r in pg.search_for(a["top"]) if x0 - 5 <= r.x0 <= x1 and r.y0 >= floor]
    top = min(r.y0 for r in tops) - a.get("top_pad", 3)
    bots = [r for r in pg.search_for(a["bottom"]) if x0 - 5 <= r.x0 <= x1 and r.y1 > top + 5]
    bot = min(r.y1 for r in bots) + a.get("bottom_pad", 3)
    return doc, pg, (x0, top, x1, bot)


def check() -> int:
    bad = 0
    for t in load()["tables"]:
        doc, pg, box = region(t)
        words = {lenient(w[4]) for w in pg.get_text("words", clip=box)}
        joined = lenient(" ".join(w[4] for w in pg.get_text("words", clip=box)))
        miss = []
        for row in t["header_rows"] + [r["cells"] for r in t["rows"]]:
            for c in row:
                for tok in cell_text(c).split():
                    if lenient(tok) and lenient(tok) not in words and lenient(tok) not in joined:
                        miss.append(tok)
        cells = sum(1 for r in t["rows"] for c in r["cells"] if cell_text(c))
        print(f"{t['id']:5} p{t['page']:<3} bbox {[round(v, 1) for v in box]}  rows {len(t['rows']):2}  cells {cells:3}  "
              + ("all cell tokens found in the text layer" if not miss else f"NOT IN TEXT LAYER: {miss}"))
        bad += len(miss)
        doc.close()
    return 1 if bad else 0


def _lcs(g: list[str], parts: list[set]) -> list[tuple[int, int]]:
    """Longest common subsequence between annotated cells and parser parts (a part matches if any of its forms equals the cell)."""
    n, m = len(g), len(parts)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if g[i] in parts[j] else max(dp[i + 1][j], dp[i][j + 1])
    out, i, j = [], 0, 0
    while i < n and j < m:
        if g[i] in parts[j] and dp[i][j] == dp[i + 1][j + 1] + 1:
            out.append((i, j)); i += 1; j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return out


def parser_rows(doc, page: int, f) -> list[dict]:
    rows = []
    for s in doc.sentences:
        m = re.match(r"^Table (row|header|text):\s*(.*)$", s.text)
        if s.page != page or not m:
            continue
        parts = []
        for p in m.group(2).split("; "):
            forms, head = {f(p)}, None
            if ": " in p:
                head, val = p.split(": ", 1)
                forms.add(f(val))
            parts.append({"forms": forms, "raw": p, "head": head})
        rows.append({"what": m.group(1), "kind": s.kind, "parts": parts, "text": s.text})
    return rows


def score_table(t: dict, doc, f) -> dict:
    prs = parser_rows(doc, t["page"], f)
    data_rows = [r for r in prs if r["what"] == "row"]
    heads = column_heads(t)
    prose = [f(s.text) for s in doc.sentences if s.page == t["page"] and s.kind in ("text", "caption")]
    all_cells = {f(c) for r in t["rows"] for c in expand(r["cells"]) if c}
    res = {"id": t["id"], "label": t["label"], "paper": t["paper"], "page": t["page"], "tags": t["tags"], "rows": [],
           "parser_rows_on_page": len(data_rows)}
    c = Counter()
    for ri, row in enumerate(t["rows"]):
        grid = expand(row["cells"])
        cols = [k for k, x in enumerate(grid) if x]
        g = [f(grid[k]) for k in cols]
        best, best_m = None, []
        for pr in data_rows:
            m = _lcs(g, [p["forms"] for p in pr["parts"]])
            if len(m) > len(best_m) or (len(m) == len(best_m) and best is not None and m and len(pr["parts"]) < len(best["parts"])):
                best, best_m = pr, m
        n = len(g)
        outcome, glued = "missing", False
        if best is not None and len(best_m) == n:
            if len(best["parts"]) == n:
                outcome = "exact" if best["kind"] == "table" else "exact_unusable"
            else:
                outcome = "merged"
        else:
            covered = set()
            used = 0
            for pr in data_rows:
                m = _lcs(g, [p["forms"] for p in pr["parts"]])
                new = {i for i, _ in m} - covered
                if new:
                    covered |= new
                    used += 1
            if len(covered) == n and 2 <= used <= 3:
                outcome = "split"
            elif len(best_m) >= (2 if n > 2 else 1):
                outcome = "partial"
        if outcome == "missing" and n >= 2:
            glued = any(g[0] + g[1] in p for p in prose)
        # column heads the parser attached to matched values
        attached = wrong = right = 0
        if best is not None:
            for i, j in best_m:
                p = best["parts"][j]
                if p["head"] is not None and f(p["raw"]) != g[i] and cols[i] > 0:
                    attached += 1
                    ok = lenient(p["head"]) in heads[cols[i]]
                    right += ok
                    wrong += not ok
        headed = sum(1 for k in cols if k > 0 and heads[k])
        amb = bool(row.get("ambiguous"))
        res["rows"].append({"label": grid[cols[0]] if cols else "", "cells": n, "matched_cells": len(best_m), "outcome": outcome,
                            "glued_in_prose": glued, "ambiguous": amb, "parser_row": best["text"] if best is not None and best_m else "",
                            "heads_attached": attached, "heads_wrong": wrong})
        if amb:
            c["ambiguous_rows"] += 1
            continue
        c["rows"] += 1
        c[outcome] += 1
        c["glued"] += glued
        c["cells"] += n
        c["cells_found"] += len(best_m)
        c["heads_attached"] += attached
        c["heads_wrong"] += wrong
        c["heads_right"] += right
        c["values_with_head"] += headed
    hdr_found = 0
    for hr in t["header_rows"]:
        g = [f(x) for x in expand(hr) if x]
        hdr_found += any(r["what"] == "header" and len(r["parts"]) == len(g) and len(_lcs(g, [p["forms"] for p in r["parts"]])) == len(g) for r in prs)
    c["header_rows"] = len(t["header_rows"])
    c["header_rows_found"] = hdr_found
    # parser rows on the page that hold no annotated cell of this table are not counted here: a page can hold other tables
    res["counts"] = dict(c)
    return res


def _rate(a, b):
    return round(a / b, 3) if b else None


def summarise(c: Counter) -> dict:
    return {"data_rows": c["rows"], **{k: c[k] for k in OUTCOMES}, "missing_glued_in_prose": c["glued"],
            "exact_row_accuracy": _rate(c["exact"], c["rows"]), "usable_or_exact": _rate(c["exact"] + c["exact_unusable"], c["rows"]),
            "cells": c["cells"], "cells_found": c["cells_found"], "cell_accuracy": _rate(c["cells_found"], c["cells"]),
            "header_rows": c["header_rows"], "header_rows_found": c["header_rows_found"],
            "header_row_recall": _rate(c["header_rows_found"], c["header_rows"]),
            "heads_attached": c["heads_attached"], "heads_wrong": c["heads_wrong"],
            "head_error_rate": _rate(c["heads_wrong"], c["heads_attached"]),
            "values_with_head": c["values_with_head"], "head_coverage": _rate(c["heads_right"], c["values_with_head"]),
            "ambiguous_rows_excluded": c["ambiguous_rows"]}


def score(out: str) -> int:
    import paperlens
    from paperlens.ingest import parse_pdf
    truth = load()
    docs = {}
    res = {"version": paperlens.__version__, "paperlens_file": str(Path(paperlens.__file__).parent).replace("\\", "/"),
           "annotations": {"file": "eval/table_truth/tables.json", "human_verified": truth["human_verified"], "annotator": truth["annotator"]},
           "strict": {}, "lenient": {}}
    for mode, f in (("strict", norm), ("lenient", lenient)):
        total, tables = Counter(), []
        for t in truth["tables"]:
            if t["paper"] not in docs:
                docs[t["paper"]] = parse_pdf(PAPERS / t["paper"])
            r = score_table(t, docs[t["paper"]], f)
            total.update(r["counts"])
            r["summary"] = summarise(Counter(r["counts"]))
            tables.append(r)
        res[mode] = {"total": summarise(total), "tables": tables}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    for mode in ("strict", "lenient"):
        print(f"paperlens {res['version']}  [{mode}]  annotations: AI-transcribed, human_verified={truth['human_verified']}")
        print(f"{'table':6}{'rows':>5}{'exact':>6}{'unus.':>6}{'merged':>7}{'split':>6}{'part.':>6}{'miss.':>6}{'glued':>6}  {'cells':>9}  {'hdr rows':>8}  {'heads wrong/att.':>16}  amb")
        for r in res[mode]["tables"] + [{"id": "ALL", "summary": res[mode]["total"]}]:
            s = r["summary"]
            print(f"{r['id']:6}{s['data_rows']:5}{s['exact']:6}{s['exact_unusable']:6}{s['merged']:7}{s['split']:6}{s['partial']:6}{s['missing']:6}"
                  f"{s['missing_glued_in_prose']:6}  {s['cells_found']:4}/{s['cells']:<4}  {s['header_rows_found']:3}/{s['header_rows']:<4}  "
                  f"{s['heads_wrong']:7}/{s['heads_attached']:<8}  {s['ambiguous_rows_excluded']}")
        s = res[mode]["total"]
        print(f"exact-row accuracy {s['exact']}/{s['data_rows']} = {s['exact_row_accuracy']}; exact incl. unusable {s['usable_or_exact']}; "
              f"cell accuracy {s['cells_found']}/{s['cells']} = {s['cell_accuracy']}; header-row recall {s['header_rows_found']}/{s['header_rows']}; "
              f"head errors {s['heads_wrong']}/{s['heads_attached']}; head coverage {s['head_coverage']}")
    return 0


def sheet(out: str) -> int:
    truth = load()
    L = ["# Table transcriptions to verify (development papers)", "",
         "These rows were transcribed by an AI assistant from images of the PDF pages. They are **not human-verified**.",
         "To verify: open the PDF in `data/Papers/`, go to the page, compare every cell, and write `ok` or the correction in the",
         "last column. Rules: `eval/table_truth/PROTOCOL.md`. Cells are given in the form the PDF's text layer has them; where the",
         "printed page differs (superscripts, subscripts, symbols) the printed reading is given in the notes.", ""]
    for t in truth["tables"]:
        L += [f"## {t['id']}: {t['label']}, page {t['page']}, `{t['paper']}`", "", f"{t['title']}. Tags: {', '.join(t['tags'])}.", ""]
        for k, hr in enumerate(t["header_rows"], 1):
            L.append(f"- header row {k}: " + " | ".join(f"{cell_text(c) or '(empty)'}" + (f" [spans {c['span']}]" if isinstance(c, dict) and c.get("span", 1) > 1 else "") for c in hr))
        if not t["header_rows"]:
            L.append("- no header row")
        L += ["", "| # | group | cells, left to right | notes | verified? (ok / correction) |", "|---|---|---|---|---|"]
        for i, r in enumerate(t["rows"], 1):
            cells = " ¦ ".join((cell_text(c) or "(empty)") + (f" [spans {c['span']}]" if isinstance(c, dict) and c.get("span", 1) > 1 else "") for c in r["cells"])
            notes = "; ".join([f"printed: {v}" for v in r.get("printed", {}).values()] + ([r["note"]] if r.get("note") else [])
                              + ([f"AMBIGUOUS: {r['ambiguous']}"] if r.get("ambiguous") else []))
            L.append(f"| {i} | {r.get('group', '')} | {cells} | {notes} | |")
        L.append("")
    Path(out).write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(truth['tables'])} tables -> {out}")
    return 0


def render(folder: str) -> int:
    import pymupdf
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    for t in load()["tables"]:
        doc, pg, box = region(t)
        clip = pymupdf.Rect(max(0, box[0] - 30), max(0, box[1] - 60), min(pg.rect.width, box[2] + 30), min(pg.rect.height, box[3] + 60))
        pg.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip).save(out / f"{t['id']}_p{t['page']}.png")
        doc.close()
    print(f"crops written to {out} (do not commit: several papers may not be redistributed)")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a == ["check"]:
        sys.exit(check())
    if len(a) == 2 and a[0] in ("score", "sheet", "render"):
        sys.exit({"score": score, "sheet": sheet, "render": render}[a[0]](a[1]))
    print(__doc__)
    sys.exit(2)
