"""Extractive, page-cited summarisation.

Every summary sentence is copied verbatim from the paper and carries its page,
so the summary cannot introduce statements the paper did not make. Sentences
are chosen per facet (problem / approach / results / limitations) by cue
patterns, then ranked with a TextRank-style centrality over TF-IDF vectors.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .models import Document, Sentence
from .textutils import numbers_in, tokenize

FACETS = {
    "problem": dict(sections={"abstract": 1.0, "introduction": 0.8},
                    cues=r"\b(problem|challenge|task|however|despite|limited|difficult|remains|fail|lack|struggle|"
                         r"we study|we address|motivat\w+|central|important)\b", max=2),
    "approach": dict(sections={"abstract": 1.0, "introduction": 0.7, "method": 0.6},
                     cues=r"\b(we (propose|introduce|present|develop|design)|our (method|approach|model|framework)|"
                          r"consists? of|novel|architecture|learns?|combines?|adaptive|objective)\b", max=2),
    "results": dict(sections={"abstract": 1.0, "conclusion": 0.7, "results": 0.6, "introduction": 0.5},
                    cues=r"\b(achiev\w+|outperform\w*|improv\w+|reach\w*|obtain\w*|results|state[- ]of[- ]the[- ]art|"
                         r"gain|reduc\w+|accuracy|f1|bleu|rouge)\b", max=3),
    "limitations": dict(sections={"limitations": 1.0, "discussion": 0.5, "conclusion": 0.4},
                        cues=r"\b(limitation|limited to|only evaluate|does not|cannot|future work|fail|"
                             r"extra hyperparameters|restricted)\b", max=2),
}


def _tfidf(sents: list[Sentence]):
    toks = [tokenize(s.text) for s in sents]
    df = Counter()
    for t in toks:
        df.update(set(t))
    n = max(len(sents), 1)
    vecs = []
    for t in toks:
        tf = Counter(t)
        v = {w: (1 + math.log(c)) * math.log(1 + n / df[w]) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / norm for w, x in v.items()})
    return vecs


def _cos(a, b):
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def _textrank(vecs, d=0.85, iters=30):
    n = len(vecs)
    if n == 0:
        return []
    sim = [[_cos(vecs[i], vecs[j]) if i != j else 0.0 for j in range(n)] for i in range(n)]
    rowsum = [sum(r) or 1.0 for r in sim]
    r = [1.0 / n] * n
    for _ in range(iters):
        r = [(1 - d) / n + d * sum(sim[j][i] / rowsum[j] * r[j] for j in range(n)) for i in range(n)]
    mx = max(r) or 1.0
    return [x / mx for x in r]


def summarize(doc: Document, tldr_sentences: int = 2) -> dict:
    pool = [s for s in doc.sentences
            if s.kind == "text" and s.section not in ("references", "acknowledgments", "front", "related")
            and 40 <= len(s.text) <= 400]
    if not pool:
        return {"tldr": [], "facets": {}, "note": "No summarisable text was extracted."}
    vecs = _tfidf(pool)
    central = _textrank(vecs)
    facets_out = {}
    used: set[int] = set()
    for name, spec in FACETS.items():
        cue = re.compile(spec["cues"], re.I)
        scored = []
        for i, s in enumerate(pool):
            if s.section not in spec["sections"] or s.id in used:
                continue
            c = len(cue.findall(s.text))
            if not c:
                continue
            sc = spec["sections"][s.section] * 0.5 + min(c, 3) * 0.2 + central[i] * 0.3
            if name == "results" and numbers_in(s.text):
                sc += 0.25
            scored.append((sc, i))
        scored.sort(reverse=True)
        picks = []
        for sc, i in scored:
            if len(picks) >= spec["max"]:
                break
            if any(_cos(vecs[i], vecs[j]) > 0.7 for j in picks):
                continue
            picks.append(i)
        picks.sort(key=lambda i: pool[i].id)
        facets_out[name] = [{"text": pool[i].text, "page": pool[i].page, "section": pool[i].section,
                             "sentence_id": pool[i].id} for i in picks]
        used.update(pool[i].id for i in picks)
    # TL;DR: most central abstract/conclusion sentences
    absent = [i for i, s in enumerate(pool) if s.section in ("abstract", "conclusion")]
    absent.sort(key=lambda i: -central[i])
    tl = sorted(absent[:tldr_sentences], key=lambda i: pool[i].id)
    return {
        "tldr": [{"text": pool[i].text, "page": pool[i].page, "section": pool[i].section} for i in tl],
        "facets": facets_out,
        "method": "extractive: verbatim sentences, cue-based facet selection + TextRank centrality",
    }
