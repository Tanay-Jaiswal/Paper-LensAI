"""Claim extraction and evidence linking (the Research Evidence Ledger core).

Claim detection is cue-based and scored, not learned: a sentence in a
claim-bearing section (abstract / introduction / results / conclusion) earns
points for assertive-contribution verbs, quantitative results, comparisons and
superlatives. Evidence linking retrieves passages from the *body* of the paper
(experiments/results/method/tables) with BM25, then boosts passages that share
the claim's exact numbers. Every link carries its page, quote and scores so a
reader can verify it. Support levels are lexical/numeric agreement, not
entailment: "strong" means the cited numbers literally appear in a results
passage, not that a model judged the claim logically proven.
"""
from __future__ import annotations

import re

from .models import Claim, Document, EvidenceLink, Sentence
from .textutils import BM25, jaccard, numbers_in, tokenize

# Headline claims live in these sections. Sentences inside results/experiments are
# treated as evidence, not as claims to be audited.
CLAIM_SECTIONS = {"abstract": 1.25, "introduction": 0.7, "conclusion": 0.75, "discussion": 0.5}
# "other" = body sections with paper-specific names ("ImageNet Classification", "II. OBSERVATION"): real papers
# often report results there, so they are eligible with a low prior.
EVIDENCE_SECTIONS = {"results": 1.0, "experiments": 0.8, "discussion": 0.5, "method": 0.35,
                     "limitations": 0.3, "appendix": 0.5, "other": 0.3}

ASSERT_RE = re.compile(
    r"\b(we (?:propose|introduce|present|develop|show|demonstrate|find|observe|prove|establish|report|achieve|obtain|"
    r"design|build|release|contribute)|achiev\w+|outperform\w*|surpass\w*|improv\w+|reduc\w+|"
    r"increas\w+|boost\w*|yield\w*|reach\w*|attain\w*|obtain\w*|beat\w*|exceed\w*|demonstrat\w+|"
    r"show\w* that|results (?:show|indicate|suggest)|our (?:model|method|approach|system|framework)\b|"
    r"state[- ]of[- ]the[- ]art|sota|novel|first to|new (?:state|record)|significant\w*|robust\w*|"
    r"generaliz\w+|faster|better|superior|higher|lower)\b", re.I)
RESULT_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:%|percent|points?|pp|x|×|bleu|f1|auc|map|rouge|accuracy)", re.I)
COMPARE_RE = re.compile(r"\b(outperform\w*|surpass\w*|better than|superior|exceed\w*|beat\w*|compared (?:with|to)|"
                        r"over (?:the )?baseline|improv\w+ (?:over|upon|on)|from \d|than)\b", re.I)
SUPER_RE = re.compile(r"\b(state[- ]of[- ]the[- ]art|sota|best|new record|unprecedented|first to|outperforms? all)\b", re.I)
GENERAL_RE = re.compile(r"\b(generaliz\w+|robust\w*|wide range|broad(?:ly)?|across (?:all|many|diverse|various)|"
                        r"universally|any (?:domain|task)|in all settings)\b", re.I)
CONTRIB_RE = re.compile(r"\b(we (?:propose|introduce|present|develop|design|release|contribute|build)|"
                        r"our (?:main )?contributions?|novel|new (?:method|model|approach|framework|dataset))\b", re.I)
HEDGE_RE = re.compile(r"\b(may|might|could|can potentially|suggests?|appears?|seems?|likely|possibly|"
                      r"perhaps|tends? to|in some cases)\b", re.I)
NEG_RE = re.compile(r"\b(limitation|however|future work|we leave|not (?:evaluated|tested|studied)|"
                    r"beyond the scope|remains? (?:unclear|open))\b", re.I)
BACKGROUND_RE = re.compile(r"\b(prior work|previous(?:ly)?|existing (?:methods|approaches)|has been (?:proposed|studied)|"
                           r"have been proposed|is a (?:central|key|fundamental)|et al\.)", re.I)


def _is_number_row(t: str) -> bool:
    """A run of table cells that reached the prose stream ("Oracle 100.0 80.5 89.2 ...") is not a sentence."""
    toks = t.split()
    numeric = sum(1 for w in toks if re.fullmatch(r"[\d.,%±+\-−()/]+", w))
    words = sum(1 for w in toks if len(re.findall(r"[A-Za-z]", w)) >= 2)
    return words < 5 or words / len(toks) < 0.5 or numeric / len(toks) >= 0.4


def _claim_score(s: Sentence) -> tuple[float, str, bool]:
    t = s.text
    if s.kind != "text" or len(t) < 30 or len(t) > 420 or t.endswith("?"):
        return 0.0, "other", False
    if _is_number_row(t):
        return 0.0, "other", False
    if s.section not in CLAIM_SECTIONS:
        return 0.0, "other", False
    score = CLAIM_SECTIONS[s.section] * 0.4
    n_assert = len(ASSERT_RE.findall(t))
    score += min(n_assert, 3) * 0.18
    has_res = bool(RESULT_RE.search(t)) or len(numbers_in(t)) >= 1 and re.search(r"\d\.\d", t)
    if has_res:
        score += 0.30
    if COMPARE_RE.search(t):
        score += 0.15
    if SUPER_RE.search(t):
        score += 0.12
    if BACKGROUND_RE.search(t) and not re.search(r"\bwe\b|\bour\b", t, re.I):
        score -= 0.45
    if NEG_RE.search(t) and not has_res:
        score -= 0.3
    if s.section == "experiments" and not has_res:
        score -= 0.4
    if s.section == "introduction" and not (CONTRIB_RE.search(t) or has_res):
        score -= 0.25
    if s.section == "results" and not has_res and not COMPARE_RE.search(t):
        score -= 0.2
    hedged = bool(HEDGE_RE.search(t))
    if GENERAL_RE.search(t) and not BACKGROUND_RE.search(t):
        ctype = "generalization"
    elif has_res and COMPARE_RE.search(t):
        ctype = "comparison"
    elif has_res:
        ctype = "result"
    elif CONTRIB_RE.search(t):
        ctype = "contribution"
    elif SUPER_RE.search(t):
        ctype = "comparison"
    elif n_assert:
        ctype = "assertion"
    else:
        ctype = "other"
    return max(score, 0.0), ctype, hedged


def extract_claims(doc: Document, max_claims: int = 25, min_score: float = 0.62) -> list[Claim]:
    cands = []
    for s in doc.sentences:
        sc, ctype, hedged = _claim_score(s)
        if sc >= min_score and ctype != "other":
            cands.append((sc, s, ctype, hedged))
    cands.sort(key=lambda x: -x[0])
    chosen: list[tuple] = []
    for sc, s, ctype, hedged in cands:
        toks = set(tokenize(s.text))
        if any(jaccard(toks, set(tokenize(o[1].text))) > 0.6 for o in chosen):
            continue  # near-duplicate (e.g. abstract restated in conclusion)
        chosen.append((sc, s, ctype, hedged))
        if len(chosen) >= max_claims:
            break
    chosen.sort(key=lambda x: x[1].id)
    claims = []
    for i, (sc, s, ctype, hedged) in enumerate(chosen, 1):
        nums = [n for n in numbers_in(s.text) if not re.fullmatch(r"(19|20)\d\d", n)]
        claims.append(Claim(id=f"C{i}", sentence_id=s.id, text=s.text, page=s.page, section=s.section,
                            claim_type=ctype, hedged=hedged, numbers=nums, confidence=round(min(sc, 1.0), 2)))
    return claims


def _eligible_evidence(doc: Document, claim: Claim) -> list[Sentence]:
    out = []
    for s in doc.sentences:
        if s.id == claim.sentence_id or s.section not in EVIDENCE_SECTIONS or s.kind == "meta":
            continue
        if len(tokenize(s.text.removeprefix("Table row:"))) < 4:
            continue  # a fragment ("Table row: 10 µ") cannot support anything
        # a claim restated elsewhere in the claims zone is not independent evidence
        if s.section in ("abstract", "introduction", "conclusion"):
            continue
        out.append(s)
    return out


def _has_result_numbers(nums) -> bool:
    """True if the claim cites a figure that evidence should reproduce (decimal or >= 10)."""
    return any("." in n or float(n) >= 10 for n in nums)


def rank_passages(claim_text: str, claim_numbers: list[str], pool: list[Sentence]):
    """Score candidate evidence passages for a claim.

    Returns [(score, lexical, shared_numbers, sentence, shared_terms)] sorted best-first.
    score = 0.55*BM25(normalised) + 0.35*numeric agreement + 0.10*section prior + 0.10*term Jaccard,
    damped by 25% if the claim has numbers and the passage shares none.
    """
    if not pool:
        return []
    docs = [tokenize(s.text) for s in pool]
    bm = BM25(docs)
    q = tokenize(claim_text)
    qset = set(q)
    norm = bm.self_score(q)
    cnums = set(claim_numbers)
    wt = lambda n: 1.0 if "." in n or float(n) >= 100 else 0.4
    wsum = sum(wt(n) for n in cnums) or 1.0
    scored = []
    for i, s in enumerate(pool):
        lex = bm.score(q, i) / norm
        shared = sorted(cnums & set(numbers_in(s.text)))
        frac = (sum(wt(n) for n in shared) / wsum) if cnums else 0.0
        overlap = jaccard(qset, set(docs[i]))
        prior = EVIDENCE_SECTIONS.get(s.section, 0.3)
        if s.kind == "table":
            prior = max(prior, 0.9)
        total = 0.55 * min(lex, 1.0) + 0.35 * frac + 0.10 * prior + 0.1 * overlap
        if cnums and not shared:
            total *= 0.75
        scored.append((total, lex, shared, s, sorted(qset & set(docs[i]))))
    scored.sort(key=lambda x: -x[0])
    return scored


def link_evidence(doc: Document, claims: list[Claim], k: int = 3) -> list[Claim]:
    for claim in claims:
        pool = _eligible_evidence(doc, claim)
        if not pool:
            claim.support, claim.support_score = "none", 0.0
            claim.flags.append("no_body_passages")
            continue
        cnums = set(claim.numbers)
        best = [x for x in rank_passages(claim.text, claim.numbers, pool)[:k] if x[0] > 0.12]
        for total, lex, shared, s, terms in best:
            claim.evidence.append(EvidenceLink(s.id, s.page, s.section, s.text, round(total, 3),
                                               shared, terms[:8]))
        if not best:
            claim.support, claim.support_score = "none", 0.0
            continue
        top = best[0]
        claim.support_score = round(top[0], 3)
        shared_any = bool(top[2])
        if cnums and shared_any and top[0] >= 0.45:
            claim.support = "strong"
        elif cnums and shared_any:
            claim.support = "moderate"
        elif top[0] >= 0.45 and not _has_result_numbers(cnums):
            claim.support = "moderate"
        elif top[0] >= 0.25 or (top[0] >= 0.45 and _has_result_numbers(cnums)):
            claim.support = "weak"
        else:
            claim.support = "none"
    return claims


def build_ledger(doc: Document, max_claims: int = 25) -> list[Claim]:
    return link_evidence(doc, extract_claims(doc, max_claims=max_claims))
