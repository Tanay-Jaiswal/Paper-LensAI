"""Label carry-over between versions (eval/claim_map.py). Synthetic rows only, plus a hash check of the locked development labels."""
import csv
import hashlib
from pathlib import Path

from eval import claim_map as cm

ROOT = Path(__file__).resolve().parent.parent


def row(paper, claim, evidence="", page="1"):
    return {"paper": paper, "claim": claim, "claim_page": "1", "evidence": evidence, "evidence_page": page if evidence else ""}


def labels_for(*rows, claim="y", pair=None):
    lab = {}
    for r in rows:
        lab[("claim", cm.cid(r))] = claim
        if r["evidence"] and pair:
            lab[("pair", cm.pid(r))] = pair
    return lab


C1 = "The model improves accuracy on the benchmark from 80.1% to 85.2% in every setting."


def test_relation_levels():
    assert cm.relation(C1, C1.upper())[0] == "identical"                      # case and punctuation do not matter
    assert cm.relation("from our contact prediction have TMscore above 0.5 for 208 of 398", "The 3D models built from our contact prediction have TMscore above 0.5 for 208 of 398")[0] == "partially_changed"
    assert cm.relation(C1, C1 + " which we attribute to better regularisation of the training data")[0] == "partially_changed"
    assert cm.relation("Alpha beta gamma delta epsilon zeta eta theta", "Completely different words about another topic entirely")[0] == "unrelated"


def test_identical_claim_keeps_its_claim_label_and_a_changed_passage_needs_a_fresh_pair_label():
    old = [row("p.pdf", C1, "Old passage that reports 85.2%.")]
    new = [row("p.pdf", C1, "A different passage that also reports 85.2%.")]
    lab = labels_for(old[0], pair="y")
    out, summary, fc, fp = cm.build_map(old, new, lab)
    m = out[0]
    assert m["relation"] == "identical" and m["claim_label_carries"] == "yes"
    assert m["previous_evidence_judgment_valid"] == "no" and m["fresh_pair_label_needed"] == "yes"
    assert not fc and len(fp) == 1 and summary["fresh_pair_labels_needed"] == 1


def test_unchanged_claim_and_passage_carry_everything():
    r = row("p.pdf", C1, "Same passage reporting 85.2%.")
    out, summary, fc, fp = cm.build_map([r], [dict(r)], labels_for(r, pair="p"))
    assert out[0]["previous_evidence_judgment_valid"] == "yes" and not fc and not fp and summary["identical"] == 1


def test_changed_text_never_inherits_a_label():
    old = [row("p.pdf", "from our contact prediction the models have TMscore above 0.5 for 208 of 398 proteins", "Passage A.")]
    new = [row("p.pdf", "The 3D models built from our contact prediction the models have TMscore above 0.5 for 208 of 398 proteins", "Passage A.")]
    out, summary, fc, fp = cm.build_map(old, new, labels_for(old[0], pair="y"))
    assert out[0]["relation"] == "partially_changed" and out[0]["claim_label_carries"] == "no"
    assert out[0]["fresh_claim_label_needed"] == "yes" and len(fc) == 1 and len(fp) == 1
    assert summary["claim_labels_carried"] == 0


def test_removed_and_added_claims_and_not_a_claim_pairs():
    gone = row("p.pdf", "Some sentence that is no longer extracted from the paper at all today.")
    added = row("p.pdf", "A wholly new claim sentence about quite another subject in the same paper.", "Some passage.")
    out, summary, fc, fp = cm.build_map([gone], [added], labels_for(gone))
    rels = sorted(m["relation"] for m in out)
    assert rels == ["added", "removed"] and summary["fresh_claim_labels_needed"] == 1
    n = row("p.pdf", C1, "Passage.")
    _, _, fc2, fp2 = cm.build_map([n], [n], labels_for(n, claim="n"))
    assert not fp2                                  # a passage of a claim labelled "not a claim" is never scored


def test_merge_refuses_conflicts_unmarked_labels_and_overwriting(tmp_path):
    def write(p, rows):
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["kind", "id", "paper", "claim_page", "claim", "evidence_page", "evidence", "label", "notes"])
            w.writeheader()
            w.writerows(rows)
    base = [{"kind": "claim", "id": "a1", "paper": "p", "claim_page": "1", "claim": "c", "evidence_page": "", "evidence": "", "label": "y", "notes": "[AI-assisted label]"}]
    ok = [{**base[0], "id": "b2", "label": "n", "notes": "[AI-assisted label, sprint 6]"}]
    conflict = [{**base[0], "label": "n", "notes": "[AI-assisted label]"}]
    unmarked = [{**base[0], "id": "c3", "notes": "looks fine"}]
    write(tmp_path / "base.csv", base); write(tmp_path / "ok.csv", ok); write(tmp_path / "conflict.csv", conflict); write(tmp_path / "un.csv", unmarked)
    assert cm.cmd_merge(str(tmp_path / "base.csv"), str(tmp_path / "ok.csv"), str(tmp_path / "out.csv")) == 0
    assert len(list(csv.DictReader(open(tmp_path / "out.csv", encoding="utf-8-sig")))) == 2
    assert cm.cmd_merge(str(tmp_path / "base.csv"), str(tmp_path / "conflict.csv"), str(tmp_path / "o2.csv")) == 1
    assert cm.cmd_merge(str(tmp_path / "base.csv"), str(tmp_path / "un.csv"), str(tmp_path / "o3.csv")) == 1
    assert cm.cmd_merge(str(tmp_path / "base.csv"), str(tmp_path / "ok.csv"), str(tmp_path / "base.csv")) == 1   # never the same file


def test_precision_is_not_computed_while_a_returned_passage_is_unlabelled():
    a, b = row("p.pdf", C1, "Passage one."), row("p.pdf", C1 + " Indeed.", "Passage two.")
    lab = labels_for(a, b, pair=None)
    lab[("pair", cm.pid(a))] = "y"
    s = cm.score_rows([a, b], lab)
    assert s["returned_without_label"] == 1 and isinstance(s["strict"], str)
    lab[("pair", cm.pid(b))] = "p"
    s = cm.score_rows([a, b], lab)
    assert s["strict"][0] == 0.5 and s["lenient"][0] == 1.0


def test_original_development_labels_are_unmodified():
    f = ROOT / "eval" / "results" / "dev_v0.2" / "dev_pairs_labelled.csv"
    lock = (ROOT / "eval" / "results" / "dev_v0.2" / "DEV_LABELS_LOCKED.txt").read_text(encoding="utf-8-sig")
    assert hashlib.sha256(f.read_bytes()).hexdigest().upper() in lock.upper()
