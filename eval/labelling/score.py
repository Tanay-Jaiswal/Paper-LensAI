"""Score PaperLens against human labels from the blinded sheet.

    python -m eval.labelling.score eval/labelling/cse_check2 labels-alice.csv labels-bob.csv

Each CSV is a labeller's export from labeller.html (or a filled-in sheet.csv). Reports, per question type:
* how often PaperLens agrees with the people (with one labeller: that person; with several: the majority answer,
  questions without a majority are left out and counted);
* how often the labellers agree with each other (percent agreement and Cohen's kappa for the first two labellers),
  which says how hard the questions are and how far any agreement figure can be trusted.

"can't tell" answers are left out of the agreement figures and counted. Results are written to RESULTS.md next to the
key, marked as human-labelled with the number of labellers. Nothing here invents or fills in a label.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# what each PaperLens decision means in the labellers' answer options
CHECKLIST = {"present": "yes", "partial": "partly", "missing": "no", "not_applicable": "not applicable"}
SKIP = {"can't tell", ""}


def read_labels(path: Path) -> tuple[str, dict]:
    with path.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    who = next((r["labeller"] for r in rows if r.get("labeller")), path.stem)
    return who, {r["id"]: (r.get("answer") or "").strip().lower() for r in rows}


def paperlens_answer(k: dict) -> str:
    if k["type"] == "checklist":
        return CHECKLIST[k["paperlens"]]
    if k["type"] == "evidence":     # strong / moderate: PaperLens asserts the passage supports the claim
        return {"strong": "yes", "moderate": "yes", "weak": "partly"}.get(k["paperlens"], "no")
    return "no support in the paper"   # "search" questions: PaperLens found no passage


def agrees(kind: str, pl: str, human: str) -> bool:
    if kind == "checklist":
        # credit is given for "present" and "partial" alike in the score, so yes/partly differences are reported
        # separately; strict agreement is the headline
        return pl == human
    if kind == "evidence":
        return (pl == "yes" and human in ("yes", "partly")) or (pl != "yes" and human in (pl, "no", "partly"))
    return human == "no support in the paper"


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 2)


def score(key_dir: Path, label_files: list[Path]) -> dict:
    key = json.loads((key_dir / "key.json").read_text(encoding="utf-8"))
    answers = key["answers"]
    people = [read_labels(f) for f in label_files]
    if not people:
        raise SystemExit("give at least one labels CSV")
    by_type: dict[str, dict] = defaultdict(lambda: {"agree": 0, "disagree": 0, "no_majority": 0, "cant_tell": 0,
                                                    "unanswered": 0, "confusion": Counter(), "examples": []})
    for qid, k in answers.items():
        t = by_type[k["type"]]
        votes = [lab[qid] for _w, lab in people if lab.get(qid, "") not in ("",)]
        if not votes:
            t["unanswered"] += 1
            continue
        usable = [v for v in votes if v not in SKIP]
        if not usable:
            t["cant_tell"] += 1
            continue
        top, n = Counter(usable).most_common(1)[0]
        if len(people) > 1 and n <= len(usable) / 2:
            t["no_majority"] += 1
            continue
        pl = paperlens_answer(k)
        ok = agrees(k["type"], pl, top)
        t["agree" if ok else "disagree"] += 1
        t["confusion"][(pl, top)] += 1
        if not ok and len(t["examples"]) < 10:
            t["examples"].append({"id": qid, "paper": k["paper"], "item": k.get("item") or k.get("claim_id"),
                                  "paperlens": pl, "people": top})
    inter = None
    if len(people) >= 2:
        (wa, la), (wb, lb) = people[0], people[1]
        both = [q for q in answers if la.get(q, "") not in SKIP and lb.get(q, "") not in SKIP]
        inter = {"labellers": [wa, wb], "n": len(both),
                 "percent": round(100 * sum(la[q] == lb[q] for q in both) / len(both), 1) if both else None,
                 "kappa": kappa([la[q] for q in both], [lb[q] for q in both])}
    return {"meta": key["meta"], "labellers": [w for w, _ in people], "by_type": by_type, "inter": inter}


def to_markdown(r: dict) -> str:
    m = r["meta"]
    out = [f"# Human labels for {m['name']}", "",
           f"Human-labelled by {len(r['labellers'])} labeller(s): {', '.join(r['labellers'])}. PaperLens version "
           f"{m['paperlens_version']}, {m['n']} questions, seed {m['seed']}. These figures come from people's labels, "
           "not from an AI.", ""]
    names = {"checklist": "CS checklist decisions", "evidence": "Claim and passage pairs",
             "search": "Claims PaperLens found no evidence for"}
    for t, v in r["by_type"].items():
        n = v["agree"] + v["disagree"]
        pct = f"{100 * v['agree'] / n:.0f}%" if n else "n/a"
        out += [f"## {names.get(t, t)}", "",
                f"PaperLens agrees with the people on **{v['agree']} of {n}** ({pct}). Left out: {v['cant_tell']} "
                f"can't tell, {v['no_majority']} without a majority, {v['unanswered']} unanswered.", ""]
        if v["confusion"]:
            out += ["| PaperLens | People | Count |", "|---|---|---|"]
            out += [f"| {a} | {b} | {c} |" for (a, b), c in sorted(v["confusion"].items())]
            out.append("")
        if v["examples"]:
            out += ["Disagreements (first 10): " + "; ".join(
                f"{e['id']} {e['paper']} {e['item']} (PaperLens {e['paperlens']}, people {e['people']})"
                for e in v["examples"]), ""]
    if r["inter"]:
        i = r["inter"]
        out += ["## Agreement between labellers", "",
                f"{i['labellers'][0]} and {i['labellers'][1]} gave the same answer on {i['percent']}% of {i['n']} "
                f"questions both answered (Cohen's kappa {i['kappa']}).", ""]
    else:
        out += ["Only one labeller: agreement between people could not be measured, so these figures rest on one "
                "person's judgement.", ""]
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    key_dir, files = Path(argv[0]), [Path(a) for a in argv[1:]]
    r = score(key_dir, files)
    md = to_markdown(r)
    (key_dir / "RESULTS.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
