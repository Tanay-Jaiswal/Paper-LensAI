"""Two-paper comparison built on the single-paper analyses."""
from __future__ import annotations

import math
from collections import Counter

from .pipeline import Analysis
from .textutils import numbers_in, tokenize


def _vec(text):
    c = Counter(tokenize(text))
    n = math.sqrt(sum(v * v for v in c.values())) or 1.0
    return {k: v / n for k, v in c.items()}


def _cos(a, b):
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def compare(a: Analysis, b: Analysis, align_threshold: float = 0.35) -> dict:
    # claim alignment (greedy one-to-one by cosine similarity of claim text)
    va = [(c, _vec(c.text)) for c in a.claims]
    vb = [(c, _vec(c.text)) for c in b.claims]
    pairs = sorted(((_cos(x[1], y[1]), i, j) for i, x in enumerate(va) for j, y in enumerate(vb)), reverse=True)
    used_a, used_b, aligned = set(), set(), []
    for sim, i, j in pairs:
        if sim < align_threshold:
            break
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        ca, cb = va[i][0], vb[j][0]
        na, nb = set(ca.numbers), set(cb.numbers)
        aligned.append({
            "similarity": round(sim, 2),
            "a": {"id": ca.id, "text": ca.text, "page": ca.page, "support": ca.support, "numbers": ca.numbers},
            "b": {"id": cb.id, "text": cb.text, "page": cb.page, "support": cb.support, "numbers": cb.numbers},
            "numbers_differ": bool(na and nb and na != nb),
            "note": ("Similar claim, different reported numbers: check that datasets, splits and metrics match."
                     if na and nb and na != nb else "Similar claim."),
        })
    only_a = [{"id": va[i][0].id, "text": va[i][0].text, "support": va[i][0].support}
              for i in range(len(va)) if i not in used_a]
    only_b = [{"id": vb[j][0].id, "text": vb[j][0].text, "support": vb[j][0].support}
              for j in range(len(vb)) if j not in used_b]

    da, db = set(a.datasets), set(b.datasets)
    ma, mb = set(a.metrics), set(b.metrics)
    ra = {i["key"]: i for i in a.rubric["items"]}
    rb = {i["key"]: i for i in b.rubric["items"]}
    rubric_rows = []
    for key in ra:
        rubric_rows.append({"key": key, "label": ra[key]["label"], "a": ra[key]["status"], "b": rb[key]["status"],
                            "differs": ra[key]["status"] != rb[key]["status"]})

    def strength(an: Analysis):
        pts = {"strong": 1.0, "moderate": 0.6, "weak": 0.25, "none": 0.0}
        q = [c for c in an.claims if c.claim_type in ("result", "comparison")]
        return round(100 * sum(pts[c.support] for c in q) / len(q), 1) if q else None

    sa, sb = strength(a), strength(b)
    ga = sum(1 for g in a.gaps if g.severity == "high")
    gb = sum(1 for g in b.gaps if g.severity == "high")
    verdict = []
    ra_s, rb_s = a.rubric["score"], b.rubric["score"]
    if abs(ra_s - rb_s) >= 5:
        verdict.append(f"Reproducibility checklist coverage is higher for paper {'A' if ra_s > rb_s else 'B'} "
                       f"({max(ra_s, rb_s)} vs {min(ra_s, rb_s)}).")
    else:
        verdict.append(f"Reproducibility coverage is similar ({ra_s} vs {rb_s}).")
    if sa is not None and sb is not None and abs(sa - sb) >= 10:
        verdict.append(f"Quantitative claims are better evidenced in paper {'A' if sa > sb else 'B'} "
                       f"(evidence score {max(sa, sb)} vs {min(sa, sb)}).")
    if ga != gb:
        verdict.append(f"Paper {'A' if ga < gb else 'B'} has fewer high-severity evidence gaps ({min(ga, gb)} vs {max(ga, gb)}).")
    shared_ds = sorted(da & db)
    if not shared_ds:
        verdict.append("No evaluation dataset is shared, so reported numbers are not directly comparable.")
    else:
        verdict.append(f"Shared dataset(s): {', '.join(shared_ds)}; numbers can be compared if splits and metrics match.")
    return {
        "a": {"title": a.doc.title, "pages": a.doc.n_pages, "repro_score": ra_s, "evidence_score": sa,
              "n_claims": len(a.claims), "high_gaps": ga},
        "b": {"title": b.doc.title, "pages": b.doc.n_pages, "repro_score": rb_s, "evidence_score": sb,
              "n_claims": len(b.claims), "high_gaps": gb},
        "datasets": {"shared": shared_ds, "only_a": sorted(da - db), "only_b": sorted(db - da)},
        "metrics": {"shared": sorted(ma & mb), "only_a": sorted(ma - mb), "only_b": sorted(mb - ma)},
        "aligned_claims": aligned, "only_a_claims": only_a, "only_b_claims": only_b,
        "rubric": rubric_rows, "verdict": verdict,
        "caveat": "Comparison reflects what each paper reports and cites; it does not judge which method is better.",
    }
