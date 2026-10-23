"""Run the CSE mode once on a folder of papers and write what it found, next to the general mode.

    python -m eval.cse_check data/cse_check_papers eval/results/cse_v1/check

Writes summary.json (per paper: detected field, both scores, glossary counts, CS items, CS gaps) and two sheets for
labelling whether each decision is right: cs_items.csv (one row per CS checklist item, with the quote that earned it)
and dictionary.csv (one row per dictionary meaning, with the first sentence that uses it). The label columns are blank.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from paperlens.pipeline import analyze_pdf  # noqa: E402

CSE_GAPS = {"test_set_tuning", "baseline_numbers_copied", "code_promised_not_linked", "small_gain_without_test",
            "sota_single_run"}


def run(folder: str, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary, items, terms = {}, [], []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        auto, gen = analyze_pdf(pdf), analyze_pdf(pdf, mode="general")
        a, g = auto.to_dict(), gen.to_dict()
        cse = analyze_pdf(pdf, mode="cse").to_dict() if a["field"]["field"] != "cse" else a
        r = cse["reproducibility"]
        summary[pdf.name] = {
            "detected_field": a["field"]["field"], "detection": a["field"]["detected"],
            "general_score": g["reproducibility"]["score"], "cse_score": r["score"],
            "cse_standard_score": r["standard_score"],
            "glossary_general": {"defined": len(g["glossary"]["defined"]), "undefined": len(g["glossary"]["undefined"])},
            "glossary_cse": {"defined": len(cse["glossary"]["defined"]), "undefined": len(cse["glossary"]["undefined"]),
                             "from_dictionary": len(cse["glossary"]["from_dictionary"]),
                             "ambiguous": sum(d["ambiguous"] for d in cse["glossary"]["from_dictionary"])},
            "cs_items": {i["key"]: i["status"] for i in r["items"] if i["key"].startswith("cs_")},
            "cs_gaps": [x for x in cse["gaps"] if x["kind"] in CSE_GAPS],
            "revisions_general": len(g["revisions"]), "revisions_cse": len(cse["revisions"]),
        }
        for i in r["items"]:
            if i["key"].startswith("cs_"):
                ev = i["evidence"][0] if i["evidence"] else {}
                items.append({"paper": pdf.name, "item": i["key"], "status": i["status"], "page": ev.get("page", ""),
                              "quote": ev.get("quote", ""), "status_correct": "", "note": ""})
        for d in cse["glossary"]["from_dictionary"]:
            first = next((s for s in auto.doc.sentences if s.page == d["page"] and d["abbr"] in s.text), None)
            terms.append({"paper": pdf.name, "abbr": d["abbr"], "dictionary_meaning": d["long"],
                          "ambiguous": d["ambiguous"], "uses": d["uses"], "page": d["page"],
                          "first_use": first.text[:240] if first else "", "meaning_fits_paper": "", "note": ""})
        print(f"{pdf.name[:50]:50} {a['field']['field']:8} general {g['reproducibility']['score']:5} "
              f"cse {r['score']:5} dict {len(cse['glossary']['from_dictionary'])}", flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    for name, rows in (("cs_items.csv", items), ("dictionary.csv", terms)):
        with open(out / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
