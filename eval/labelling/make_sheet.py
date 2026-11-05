"""Build a blinded labelling sheet so that people (not PaperLens, not an AI) can check a sample of its decisions.

    python -m eval.labelling.make_sheet                                   # the 8 papers of the second CSE check set
    python -m eval.labelling.make_sheet --papers data/cse_check_papers --name cse_check1

Writes eval/labelling/<name>/:
  labeller.html   offline labelling page to hand to labellers (open it in any browser; no install, no internet)
  sheet.csv       the same questions as a spreadsheet, for people who prefer Excel or Google Sheets
  papers.csv      the papers and where to download each one
  key.json        PaperLens's own answers, for scoring only. Do not give this file to labellers.

Blinding: a question never shows what PaperLens decided. Checklist questions ask whether the paper reports something,
without the quote PaperLens found; evidence questions show a claim and a passage, without the support rating.
Questions are shuffled with a fixed seed, so the same command always builds the same sheet.

Nothing here writes a label. Labels come only from people, through labeller.html or sheet.csv.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from paperlens import __version__  # noqa: E402
from paperlens.pipeline import analyze_pdf  # noqa: E402

HERE = Path(__file__).resolve().parent

# plain questions for the 10 CS checklist items: what a labeller should look for in the paper
CS_QUESTIONS = {
    "cs_code_link": "Does the paper give a working link to its own code (a repository or archive), not only a promise "
                    "to release it later?",
    "cs_data_access": "For the datasets the paper uses, does it say where each comes from (a link or citation) and "
                      "which version or split was used?",
    "cs_hardware_spec": "Does the paper name the exact hardware used (for example '8 NVIDIA V100 GPUs' or a CPU model)?",
    "cs_compute_budget": "Does the paper report how long training or running took, or the total compute "
                         "(for example GPU-hours)?",
    "cs_hyper_search": "Does the paper say how hyperparameters were chosen (search method, ranges tried, or the data "
                       "used to choose)?",
    "cs_model_selection": "Does the paper say that the final model or checkpoint was chosen on validation data "
                          "(not on the test set)?",
    "cs_model_size": "Does the paper report the number of parameters of its model(s)?",
    "cs_baseline_setup": "For the baselines it compares with, does the paper say whether it re-ran them or copied "
                         "their numbers from other papers?",
    "cs_table_uncertainty": "Do the main results tables show spread over runs (± standard deviation, error bars or "
                            "confidence intervals)?",
    "cs_efficiency": "Does the paper report runtime, memory use or computational complexity of its method?",
}
CHECKLIST_OPTIONS = ["yes", "partly", "no", "not applicable", "can't tell"]
EVIDENCE_OPTIONS = ["yes", "partly", "no", "can't tell"]
SEARCH_OPTIONS = ["yes, I found support", "no support in the paper", "can't tell"]
MAX_EVIDENCE_PAIRS = 3       # per paper: claims with a passage
MAX_NO_EVIDENCE = 2          # per paper: claims PaperLens found no passage for


def _manifest(folder: Path) -> dict:
    f = folder / "MANIFEST.csv"
    if not f.exists():
        return {}
    with f.open(encoding="utf-8-sig") as fh:
        return {r["filename"]: r for r in csv.DictReader(fh)}


def build(papers_dir: Path, name: str, seed: int = 20261024) -> Path:
    out = HERE / name
    out.mkdir(parents=True, exist_ok=True)
    man = _manifest(papers_dir)
    items, key, paper_rows = [], {}, []
    for n, pdf in enumerate(sorted(papers_dir.glob("*.pdf")), 1):
        pid = f"P{n}"
        a = analyze_pdf(pdf, mode="cse")
        m = man.get(pdf.name, {})
        paper_rows.append({"paper": pid, "file": pdf.name, "title": m.get("title") or a.doc.title,
                           "link": m.get("landing_url", ""), "pages": a.doc.n_pages,
                           "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()})
        for it in a.rubric["items"]:
            if it["key"] not in CS_QUESTIONS:
                continue
            q = {"type": "checklist", "paper": pid, "question": CS_QUESTIONS[it["key"]], "options": CHECKLIST_OPTIONS,
                 "ask_page": True}
            items.append(q)
            key_entry = {"type": "checklist", "paper": pid, "item": it["key"], "paperlens": it["status"]}
            q["_key"] = key_entry
        with_ev = [c for c in a.claims if c.evidence][:MAX_EVIDENCE_PAIRS]
        without = [c for c in a.claims if not c.evidence and c.evidence_status == "no_supporting_evidence"][:MAX_NO_EVIDENCE]
        for c in with_ev:
            e = c.evidence[0]
            q = {"type": "evidence", "paper": pid, "claim": c.text, "claim_page": c.page, "passage": e.quote,
                 "passage_page": e.page,
                 "question": "Does the passage support the claim (does it report the result or finding the claim "
                             "states)?", "options": EVIDENCE_OPTIONS, "ask_page": False}
            q["_key"] = {"type": "evidence", "paper": pid, "claim_id": c.id, "paperlens": c.support}
            items.append(q)
        for c in without:
            q = {"type": "search", "paper": pid, "claim": c.text, "claim_page": c.page,
                 "question": "Is there a passage or table anywhere in the paper's results that supports this claim? "
                             "If yes, give its page.", "options": SEARCH_OPTIONS, "ask_page": True}
            q["_key"] = {"type": "search", "paper": pid, "claim_id": c.id, "paperlens": "none"}
            items.append(q)
        print(f"  {pid} {pdf.name}: {sum(1 for i in items if i['paper'] == pid)} questions")
    random.Random(seed).shuffle(items)
    for i, q in enumerate(items, 1):
        q["id"] = f"Q{i:03d}"
        key[q["id"]] = q.pop("_key")
    meta = {"name": name, "paperlens_version": __version__, "seed": seed, "n": len(items),
            "papers_dir": str(papers_dir.relative_to(ROOT)) if papers_dir.is_relative_to(ROOT) else str(papers_dir)}
    (out / "key.json").write_text(json.dumps({"meta": meta, "answers": key}, indent=1, ensure_ascii=False),
                                  encoding="utf-8")
    with (out / "papers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(paper_rows[0]))
        w.writeheader()
        w.writerows(paper_rows)
    with (out / "sheet.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "paper", "type", "question", "claim", "claim_page", "passage", "passage_page",
                    "allowed answers", "labeller", "answer", "page_found", "note"])
        for q in items:
            w.writerow([q["id"], q["paper"], q["type"], q["question"], q.get("claim", ""), q.get("claim_page", ""),
                        q.get("passage", ""), q.get("passage_page", ""), " / ".join(q["options"]), "", "", "", ""])
    public = {"meta": {k: meta[k] for k in ("name", "n", "seed")}, "papers": paper_rows, "items": items}
    page = (HERE / "labeller_template.html").read_text(encoding="utf-8")
    page = page.replace("/*__DATA__*/null", json.dumps(public, ensure_ascii=False).replace("</", "<\\/"))
    (out / "labeller.html").write_text(page, encoding="utf-8")
    print(f"wrote {out}: {len(items)} questions on {len(paper_rows)} papers")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--papers", default=str(ROOT / "data" / "cse_check2_papers"))
    ap.add_argument("--name", default="cse_check2")
    ap.add_argument("--seed", type=int, default=20261024)
    args = ap.parse_args(argv)
    build(Path(args.papers).resolve(), args.name, args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
