"""Reading-order and layout benchmark on synthetic PDFs (see eval/layout_synth.py for how they and their truth are made).

    python -m eval.layout_bench [--out results.json] [--pdfs <dir to keep the PDFs in>] [--only <layout id>]

PAPERLENS_SRC=<folder containing a copy of the `paperlens` package> scores another version (the pre-change baseline:
`git archive <commit> paperlens | tar -x -C <folder>`).

Every metric is computed per document from the parser's `Sentence` list (text, page, section, kind, heading) and from the
claims and evidence links of `analyze_pdf`. Matching uses letters and digits only (NFKC, lower case), so line breaks,
ligatures and hyphenation do not matter. Definitions (the denominator is always stated; a missing item counts against
the parser, never out of the denominator):

  block_recall      alnum characters of ground-truth body blocks (abstract, body paragraphs, captions, reference list)
                    covered by parser sentences that lie inside that block / alnum characters of those blocks.
  block_precision   alnum characters of parser sentences of kind text or caption that lie inside ONE ground-truth
                    block that belongs in the text (body, abstract, caption, reference list, front matter, title) /
                    alnum characters of all parser sentences of kind text or caption. Spliced sentences (text from two
                    blocks), furniture (running headers, page numbers, footnotes) and stray cell text lower it.
  spliced           number of parser text/caption sentences (>= 8 alnum characters) that lie inside no single block.
  furniture_leaks   number of parser text/caption sentences that lie inside a header, page-number or footnote block.
  order_acc         over all pairs of recovered ground-truth blocks (>= 50% covered): share whose first sentence appears
                    in the ground-truth order. For the ambiguous layout the best of the accepted orders. Needs >= 2 blocks.
  para_recon        share of ground-truth body blocks whose matched sentences, joined, equal the block exactly and form
                    one run of sentences with no sentence of another block in between.
  page_acc          share of matched sentences whose page equals the page of the place in the block where the sentence starts.
  claim_recall      ground-truth claims for which the parser extracted a claim with exactly that sentence / claims.
  claim_page_ok     of the recovered claims, share with the right page.
  spurious_claims   extracted claims lying inside no single block (spliced).
  evidence_rate     recovered claims with at least one evidence passage inside the designated results block on the right page.
  evidence_mixed    evidence passages (over all claims) lying inside no single block.
  heading_recall    ground-truth headings found as the heading of some sentence / headings.
  section_acc       share of recovered body blocks whose majority section (by characters) is the ground-truth section.
  abstract_p / _r   precision / recall (characters) of the sentences labelled abstract against the abstract block.
  quantity_recall   ground-truth quantities (units, exponents, intervals) found in the sentences of their own block / quantities.
  table_recall      ground-truth table data rows found as one table sentence containing all their cells / rows.
  title_ok          the extracted title equals the ground-truth title.
  ambiguity_safe    (ambiguous layouts only) 1 if nothing was spliced OR the document carries a layout warning.
  layout_warning    1 if the document carries a warning about layout / reading order.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, os.environ.get("PAPERLENS_SRC") or str(ROOT))
sys.path.insert(0, str(ROOT))
from eval import layout_synth  # noqa: E402
from paperlens.pipeline import analyze_pdf  # noqa: E402

BODY_KINDS = {"para", "reference", "caption"}      # blocks whose text must be recovered
TEXT_OK = {"para", "reference", "caption", "front", "title"}   # blocks that parser text may legitimately come from
EXCLUDED = {"header", "pagenum", "footnote"}


def alnum(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKC", s).lower() if ch.isascii() and ch.isalnum())


def _unit_bounds(block: dict) -> list[tuple[int, int]]:
    out, acc = [], 0
    for u in block["units"]:
        n = len(alnum(u["text"]))
        out.append((acc, acc + n, u["page"]))
        acc += n
    return out


def _page_at(block: dict, pos: int) -> int | None:
    for a, b, page in _unit_bounds(block):
        if a <= pos < b:
            return page
    return None


def evaluate(truth: dict, analysis) -> dict:
    doc = analysis.doc
    blocks = truth["blocks"] + truth.get("excluded", [])
    norm = {b["id"]: alnum(b["text"]) for b in blocks}
    kind = {b["id"]: b["kind"] for b in blocks}
    body_ids = [b["id"] for b in truth["blocks"] if b["kind"] in BODY_KINDS]

    match: dict[int, tuple[str, int]] = {}      # sentence id -> (block id, position in block)
    spliced, leaks, unmatched_text = [], [], []
    text_chars = ok_chars = 0
    for s in doc.sentences:
        if s.kind == "table":
            continue
        ns = alnum(s.text)
        if len(ns) < 8:
            continue
        hits = [(bid, norm[bid].find(ns)) for bid in norm if norm[bid] and ns in norm[bid]]
        counted = s.kind in ("text", "caption")
        if counted:
            text_chars += len(ns)
        if hits:
            bid, pos = hits[0]
            match[s.id] = (bid, pos)
            if kind[bid] in EXCLUDED:
                if counted:
                    leaks.append(s)
            elif counted and kind[bid] in TEXT_OK:
                ok_chars += len(ns)
        elif counted:
            spliced.append(s)

    covered = defaultdict(int)
    for sid, (bid, _) in match.items():
        s = doc.sentences[sid] if sid < len(doc.sentences) and doc.sentences[sid].id == sid else next(x for x in doc.sentences if x.id == sid)
        covered[bid] += len(alnum(s.text))
    total_body = sum(len(norm[b]) for b in body_ids) or 1
    r: dict = {"block_recall": sum(min(covered[b], len(norm[b])) for b in body_ids) / total_body,
               "block_precision": ok_chars / text_chars if text_chars else 0.0,
               "spliced": len(spliced), "furniture_leaks": len(leaks)}

    # reading order
    first: dict[str, int] = {}
    for sid, (bid, _) in match.items():
        if bid in body_ids or kind[bid] in BODY_KINDS:
            first[bid] = min(first.get(bid, sid), sid)
    rec = [b for b in body_ids if b in first and covered[b] >= 0.5 * len(norm[b])]

    def pair_acc(order: list[str]) -> float:
        seq = [b for b in order if b in rec]
        n = ok = 0
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                n += 1
                ok += first[seq[i]] < first[seq[j]]
        return ok / n if n else float("nan")

    if truth.get("ambiguous"):
        accs = [pair_acc(o) for o in truth["accepted_orders"]]
        accs = [a for a in accs if a == a]
        r["order_acc"] = max(accs) if accs else float("nan")
    else:
        r["order_acc"] = pair_acc(body_ids)

    # paragraph reconstruction and page attribution
    sent_by_id = {s.id: s for s in doc.sentences}
    per_block = defaultdict(list)
    for sid, (bid, pos) in match.items():
        per_block[bid].append(sid)
    recon = 0
    for b in body_ids:
        ids = sorted(per_block.get(b, []))
        if not ids:
            continue
        joined = "".join(alnum(sent_by_id[i].text) for i in ids)
        between = [x for x in doc.sentences if ids[0] < x.id < ids[-1] and x.id not in ids
                   and x.kind in ("text", "caption") and len(alnum(x.text)) >= 8]
        recon += joined == norm[b] and not between
    r["para_recon"] = recon / len(body_ids) if body_ids else float("nan")
    pg_ok = pg_n = 0
    for sid, (bid, pos) in match.items():
        if kind[bid] in EXCLUDED:
            continue
        blk = next(b for b in blocks if b["id"] == bid)
        want = _page_at(blk, pos)
        pg_n += 1
        pg_ok += want == sent_by_id[sid].page
    r["page_acc"] = pg_ok / pg_n if pg_n else float("nan")

    # claims and evidence
    cl = truth["claims"]
    by = {b["id"]: b for b in blocks}
    found = ev_ok = page_ok = 0
    for g in cl:
        c = next((c for c in analysis.claims if alnum(c.text) == alnum(g["text"])), None)
        if not c:
            continue
        found += 1
        page_ok += c.page == g["page"]
        eb = by[g["evidence_block"]]
        ev_ok += any(alnum(e.quote) in norm[eb["id"]] and e.page == _page_at(eb, norm[eb["id"]].find(alnum(e.quote)))
                     for e in c.evidence)
    r["claim_recall"] = found / len(cl) if cl else float("nan")
    r["claim_page_ok"] = page_ok / found if found else float("nan")
    r["evidence_rate"] = ev_ok / found if found else float("nan")
    r["spurious_claims"] = sum(1 for c in analysis.claims if not any(alnum(c.text) in v for v in norm.values()))
    r["evidence_mixed"] = sum(1 for c in analysis.claims for e in c.evidence
                              if not e.quote.startswith("Table row") and not any(alnum(e.quote) in v for v in norm.values()))

    # headings, sections, abstract
    heads = {alnum(s.heading) for s in doc.sentences if s.heading}
    gt_heads = [h for h in truth["headings"] if h["text"]]
    r["heading_recall"] = sum(alnum(h["text"]) in heads for h in gt_heads) / len(gt_heads) if gt_heads else float("nan")
    sec_ok = sec_n = 0
    for b in body_ids:
        if not by[b]["section"] or b not in first:
            continue
        cnt: Counter = Counter()
        for i in per_block[b]:
            cnt[sent_by_id[i].section] += len(alnum(sent_by_id[i].text))
        sec_n += 1
        sec_ok += bool(cnt) and cnt.most_common(1)[0][0] == by[b]["section"]
    r["section_acc"] = sec_ok / sec_n if sec_n else float("nan")
    ab_chars = sum(len(alnum(s.text)) for s in doc.sentences if s.section == "abstract" and s.kind == "text")
    ab_in = sum(len(alnum(s.text)) for s in doc.sentences
                if s.section == "abstract" and s.kind == "text" and match.get(s.id, ("",))[0] == "abstract")
    if "abstract" in norm:
        r["abstract_p"] = ab_in / ab_chars if ab_chars else 0.0
        r["abstract_r"] = ab_in / len(norm["abstract"])
    else:
        r["abstract_p"] = r["abstract_r"] = float("nan")

    # quantities, tables, title
    qn = qf = 0
    for b in truth["blocks"]:
        if b["quantities"]:
            text = "".join(alnum(sent_by_id[i].text) for i in per_block.get(b["id"], []))
            for q in b["quantities"]:
                qn += 1
                qf += alnum(q) in text
    r["quantity_recall"] = qf / qn if qn else float("nan")
    rows = [(b, row) for b in truth["blocks"] if b["kind"] == "table" for row in b["rows"][1:]]
    tabs = [alnum(s.text) for s in doc.sentences if s.kind == "table"]
    r["table_recall"] = (sum(any(all(alnum(c) in t for c in row) for t in tabs) for _, row in rows) / len(rows)
                         if rows else float("nan"))
    r["title_ok"] = float(alnum(doc.title) == alnum(truth["title"]))
    warn = any(re.search(r"layout|reading order|column", w, re.I) for w in doc.warnings)
    r["layout_warning"] = float(warn)
    r["ambiguity_safe"] = float(not spliced or warn) if truth.get("ambiguous") else float("nan")
    return r


METRICS = ["block_recall", "block_precision", "order_acc", "para_recon", "page_acc", "claim_recall", "claim_page_ok",
           "evidence_rate", "heading_recall", "section_acc", "abstract_p", "abstract_r", "quantity_recall",
           "table_recall", "title_ok"]
COUNTS = ["spliced", "furniture_leaks", "spurious_claims", "evidence_mixed", "layout_warning"]


def _mean(xs):
    xs = [x for x in xs if x == x]
    return sum(xs) / len(xs) if xs else float("nan")


def run(out: str | None, keep: str | None, only: str | None) -> dict:
    tmp = Path(keep) if keep else Path(tempfile.mkdtemp(prefix="layout_bench_"))
    layout_synth.write_all(tmp)
    results = {}
    for spec in layout_synth.LAYOUTS:
        if only and spec[0] != only:
            continue
        truth = json.loads((tmp / f"{spec[0]}.truth.json").read_text(encoding="utf-8"))
        try:
            analysis = analyze_pdf(tmp / f"{spec[0]}.pdf")
            m = evaluate(truth, analysis)
            m["warnings"] = analysis.doc.warnings
        except Exception as e:                      # a crash is a result
            m = {"error": f"{type(e).__name__}: {e}"}
        m.update({"category": spec[1], "stream": spec[2]})
        results[spec[0]] = m
    cats: dict = defaultdict(list)
    for k, m in results.items():
        if "error" not in m:
            cats[m["category"]].append(m)
    per_cat = {c: {**{k: _mean([m[k] for m in ms]) for k in METRICS}, **{k: sum(m[k] for m in ms) for k in COUNTS},
                   "documents": len(ms)} for c, ms in cats.items()}
    allm = [m for m in results.values() if "error" not in m]
    agg = {**{k: _mean([m[k] for m in allm]) for k in METRICS}, **{k: sum(m[k] for m in allm) for k in COUNTS},
           "documents": len(allm), "crashed": sum("error" in m for m in results.values())}
    ambiguous = [m for m in allm if m["ambiguity_safe"] == m["ambiguity_safe"]]
    agg["ambiguity_safe"] = _mean([m["ambiguity_safe"] for m in ambiguous])
    nonamb = [m for m in allm if m["ambiguity_safe"] != m["ambiguity_safe"]]
    agg["false_layout_warnings"] = sum(m["layout_warning"] for m in nonamb)
    res = {"version": __import__("paperlens").__version__, "documents": results, "per_category": per_cat, "aggregate": agg}
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(res, indent=1, ensure_ascii=False, default=lambda x: None), encoding="utf-8")
    _print(res)
    return res


def _fmt(x):
    return "  n/a" if x != x else (f"{x:5.2f}" if isinstance(x, float) else f"{x:5d}")


def _print(res):
    cols = ["block_recall", "block_precision", "order_acc", "para_recon", "page_acc", "claim_recall", "evidence_rate"]
    print(f"paperlens {res['version']}")
    print(f"{'document':26}" + "".join(f"{c[:9]:>10}" for c in cols) + "   spl leak warn")
    for k, m in res["documents"].items():
        if "error" in m:
            print(f"{k:26} CRASH {m['error']}")
            continue
        print(f"{k:26}" + "".join(f"{_fmt(m[c]):>10}" for c in cols) + f"  {m['spliced']:3d} {m['furniture_leaks']:4d} {int(m['layout_warning']):4d}")
    print("-- per category (mean over documents)")
    for c, m in res["per_category"].items():
        print(f"{c:26}" + "".join(f"{_fmt(m[x]):>10}" for x in cols) + f"  {m['spliced']:3d} {m['furniture_leaks']:4d} {int(m['layout_warning']):4d}")
    a = res["aggregate"]
    print(f"{'ALL (macro)':26}" + "".join(f"{_fmt(a[x]):>10}" for x in cols) + f"  {a['spliced']:3d} {a['furniture_leaks']:4d} {int(a['layout_warning']):4d}")
    print("also: " + ", ".join(f"{k}={_fmt(a[k]).strip()}" for k in ["heading_recall", "section_acc", "abstract_p", "abstract_r",
                                                                    "quantity_recall", "table_recall", "title_ok", "claim_page_ok",
                                                                    "ambiguity_safe", "spurious_claims", "evidence_mixed",
                                                                    "false_layout_warnings"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out")
    ap.add_argument("--pdfs")
    ap.add_argument("--only")
    a = ap.parse_args()
    run(a.out, a.pdfs, a.only)
