"""CS comparison: where one paper's reporting stands against a set of other Computer Science papers.

Two sets can be used:

* the built-in set: development CS papers analysed once with this version (paperlens/data/cs_reference.json, rebuilt
  with `python -m eval.build_cs_reference`). Only summary numbers and item statuses are stored, never paper text;
* "your papers": every paper analysed in CS mode on this computer (data/store), read from the stored results.

The comparison is descriptive: a percentile among a small, non-random set says how this paper's *reporting* compares
with those papers, not whether it is good research. The set size is always shown with the result.
"""
from __future__ import annotations

import json
from pathlib import Path

REFERENCE_FILE = Path(__file__).resolve().parent / "data" / "cs_reference.json"
REPORTED = ("present", "partial")


def profile(d: dict) -> dict | None:
    """Comparable summary of one analysis (the to_dict()/API form). None if it is not a CS-mode analysis."""
    try:
        r = d["reproducibility"]
        if r.get("field") != "cse" or r.get("band") == "not assessed":
            return None
        card = d.get("scorecard") or {}
        return {
            "title": d["document"]["title"], "name": d["document"].get("source_name", ""),
            "score": r["score"], "standard_score": r.get("standard_score", r["score"]),
            "items": {i["key"]: i["status"] for i in r["items"]},
            "labels": {i["key"]: i["label"] for i in r["items"]},
            "evidence_score": (card.get("parts") or {}).get("evidence_score"),
            "grade": card.get("grade"),
            "high_gaps": sum(1 for g in d.get("gaps", []) if g.get("severity") == "high"),
        }
    except (KeyError, TypeError):
        return None


def load_reference() -> dict:
    if not REFERENCE_FILE.exists():
        return {"papers": [], "note": "The built-in reference set has not been built.", "version": None}
    return json.loads(REFERENCE_FILE.read_text(encoding="utf-8"))


def local_profiles(store: Path, exclude_id: str = "", only: set | None = None) -> list[dict]:
    """CS-mode analyses stored on this computer; one per paper name (the newest), the current paper left out."""
    out, seen = [], set()
    if not store.exists():
        return out
    for d in sorted(store.iterdir(), key=lambda p: -p.stat().st_mtime):
        f = d / "analysis.json"
        if d.name == exclude_id or not f.exists() or (only is not None and d.name not in only):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        p = profile(j)
        if p is None or not p["items"] or not any(k.startswith("cs_") for k in p["items"]):
            continue
        key = (p["name"] or p["title"]).lower()
        if key in seen:
            continue
        seen.add(key)
        p["id"] = d.name
        out.append(p)
    return out


def _percentile(value: float, others: list[float]) -> float:
    """Share of the set this paper is at or above (ties count half), in percent."""
    if not others:
        return 0.0
    below = sum(1 for v in others if v < value)
    ties = sum(1 for v in others if v == value)
    return round(100 * (below + 0.5 * ties) / len(others), 0)


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return round(s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2, 1)


def compare_to_set(me: dict, others: list[dict], set_name: str) -> dict:
    scores = [o["score"] for o in others]
    std = [o["standard_score"] for o in others]
    ev = [o["evidence_score"] for o in others if o.get("evidence_score") is not None]
    items = []
    for key, status in me["items"].items():
        rated = [o["items"][key] for o in others if o["items"].get(key) not in (None, "not_applicable")]
        share = round(100 * sum(1 for s in rated if s in REPORTED) / len(rated)) if rated else None
        note = ""
        if share is not None and status != "not_applicable":
            if status == "missing" and share >= 60:
                note = f"Most papers in the set report this ({share}%); this paper does not."
            elif status in REPORTED and share <= 40:
                note = f"Few papers in the set report this ({share}%); this paper does."
        items.append({"key": key, "label": me["labels"].get(key, key), "cs": key.startswith("cs_"), "status": status,
                      "set_reporting_share": share, "set_rated": len(rated), "note": note})
    # items where this paper differs most from common practice first
    items.sort(key=lambda i: (i["note"] == "", -(i["set_reporting_share"] or 0) if i["status"] == "missing" else 0))
    n = len(others)
    res = {
        "set": set_name, "n": n,
        "paper": {"title": me["title"], "score": me["score"], "standard_score": me["standard_score"],
                  "evidence_score": me.get("evidence_score"), "grade": me.get("grade")},
        "score": {"percentile": _percentile(me["score"], scores), "median": _median(scores),
                  "min": min(scores) if scores else None, "max": max(scores) if scores else None,
                  "rank": 1 + sum(1 for s in scores if s > me["score"]), "values": sorted(scores)},
        "standard_score": {"percentile": _percentile(me["standard_score"], std), "median": _median(std)},
        "evidence_score": ({"percentile": _percentile(me["evidence_score"], ev), "median": _median(ev), "n": len(ev)}
                           if me.get("evidence_score") is not None and ev else None),
        "items": items,
        "papers": [{"title": o["title"], "score": o["score"], "id": o.get("id")} for o in others],
    }
    if n < 5:
        res["warning"] = (f"Only {n} other CS paper{'s' if n != 1 else ''} in this set, too few for a percentile to "
                          "mean much.")
    res["caveat"] = (f"Compared with {n} CS papers that are not a random sample of the field. The percentile says how "
                     "completely this paper reports its work relative to them, not how good the research is.")
    return res


def benchmark(analysis_dict: dict, store: Path, which: str = "builtin", exclude_id: str = "",
              only: set | None = None) -> dict:
    me = profile(analysis_dict)
    if me is None:
        return {"available": False,
                "reason": "The CS comparison needs a paper checked in Computer Science & Engineering mode. Choose "
                          "\"Computer Science & Engineering\" under Field checks and upload the PDF again."}
    if which == "mine":
        others, name = local_profiles(store, exclude_id, only), "Your CS papers analysed on this computer"
    else:
        ref = load_reference()
        title = me["title"].strip().lower()
        others = [p for p in ref.get("papers", []) if p["title"].strip().lower() != title]
        name = f"Built-in set of {len(others)} development CS papers (PaperLens {ref.get('version')})"
    if not others:
        return {"available": False, "reason": "No other CS paper is in this set yet." + (
            " Analyse more CS papers, or compare with the built-in set." if which == "mine" else "")}
    out = compare_to_set(me, others, name)
    out["available"] = True
    return out
